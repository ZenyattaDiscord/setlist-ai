from typing import List, Dict
from backend.models import Track

# harmonic neighbors on Camelot wheel (same, ±1, ±7)
def camelot_neighbors(k: str) -> set[str]:
    num = int(k[:-1]); majmin = k[-1]   # e.g., 8A
    wraps = lambda n: ((n-1) % 12) + 1
    n1 = wraps(num+1); n_1 = wraps(num-1); n7 = wraps(num+7)
    # relative major/minor swap A<->B with same number
    rel = f"{num}{'B' if majmin=='A' else 'A'}"
    return {f"{num}{majmin}", f"{n1}{majmin}", f"{n_1}{majmin}", f"{n7}{majmin}", rel}

def edge_weight(a: Track, b: Track) -> float:
    # higher is better transition
    score = 0.0
    if a.key_camelot and b.key_camelot and b.key_camelot in camelot_neighbors(a.key_camelot):
        score += 1.0
    if a.bpm and b.bpm:
        diff = abs(a.bpm - b.bpm)
        score += 1.0 if diff <= 3 else 0.6 if diff <= 5 else 0.3 if diff <= 8 else 0
    return score

def build_energy_targets(total: int, curve: List[int]) -> List[float]:
    # spread a curve like [6,7,8,9,8,7] across N tracks
    if total <= len(curve): return curve[:total]
    # interpolate
    steps = []
    for i in range(total):
        idx = i*(len(curve)-1)/(total-1)
        lo, hi = int(idx), min(int(idx)+1, len(curve)-1)
        t = idx - lo
        steps.append(curve[lo]*(1-t) + curve[hi]*t)
    return steps

def compile_set(tracks: List[Track], minutes: int, avg_track_len_sec: int = 240, energy_curve=[7,8,9,10,9,8]) -> List[Dict]:
    target_count = max(3, min(len(tracks), int((minutes*60)/avg_track_len_sec)))
    targets = build_energy_targets(target_count, energy_curve)  # on 1..10 scale

    # seed: pick track closest to first target energy
    def e(t): return t.energy if t.energy is not None else 0.5
    pool = tracks[:]
    pool.sort(key=lambda t: abs((1 + 9*e(t)) - targets[0]))  # rough align
    setlist = [pool.pop(0)]

    # greedy selection with heuristic
    while len(setlist) < target_count and pool:
        prev = setlist[-1]
        scored = []
        for cand in pool[:64]:  # cap branching
            w = edge_weight(prev, cand)
            # penalize energy gap vs target
            target_e = targets[len(setlist)]
            cand_e = 1 + 9*(cand.energy or 0.5)
            w += max(0, 1.0 - abs(cand_e - target_e)/3.0)
            scored.append((w, cand))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        setlist.append(best)
        pool.remove(best)

    # produce transition notes
    out = []
    for i,t in enumerate(setlist):
        note = ""
        if i>0:
            a=setlist[i-1]; bpm_jump = (t.bpm or 0)-(a.bpm or 0)
            if t.key_camelot == a.key_camelot: note="Same key; long blend."
            elif t.key_camelot in camelot_neighbors(a.key_camelot): note="Harmonic neighbor; 16-bar mix."
            else: note="Non-harmonic; use filter/echo exit."
            if abs(bpm_jump) > 5: note += " Consider half/double-time or echo-out."
        out.append({"position": i+1, "name": t.name, "artist": t.artist, "bpm": t.bpm, "key": t.key_camelot, "note": note})
    return out
