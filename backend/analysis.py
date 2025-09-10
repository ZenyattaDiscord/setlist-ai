import math
from datetime import datetime
from sqlmodel import Session, select
from backend.models import Track

# Camelot mapping by semitone → camelot key
# 0..11 major to XB, minor to XA
CAMELOT_MAJOR = ["8B","3B","10B","5B","12B","7B","2B","9B","4B","11B","6B","1B"]
CAMELOT_MINOR = ["5A","12A","7A","2A","9A","4A","11A","6A","1A","8A","3A","10A"]

def to_camelot(key: int | None, mode: int | None) -> str | None:
    if key is None or mode is None: return None
    return (CAMELOT_MAJOR if mode == 1 else CAMELOT_MINOR)[key % 12]

def energy_score(spotify_energy: float | None, danceability: float | None, loudness: float | None, bpm: float | None) -> float:
    # cheap composite 1..10
    e = (spotify_energy or 0)
    d = (danceability or 0)
    l = (min(max(( (loudness or -60) + 60 )/60.0, 0), 1))  # normalize rough loudness -60..0dB
    b = min((bpm or 0)/160.0, 1)                           # cap normalization at ~160 BPM
    score = 1 + 9 * (0.45*e + 0.25*d + 0.2*l + 0.10*b)
    return round(score, 2)

def upsert_tracks(session: Session, playlist_tracks, features_by_id: dict):
    stored = []
    for t in playlist_tracks:
        try:
            tid = t["id"]
            # Safe Unicode handling for artist names
            artists = ", ".join([str(a["name"]) for a in t.get("artists", []) if a.get("name")])
            f = features_by_id.get(tid) or {}
            camelot = to_camelot(f.get("key"), f.get("mode"))
            
            track = session.exec(select(Track).where(Track.spotify_id == tid)).first()
            if not track:
                track = Track(spotify_id=tid)
            
            # Ensure strings are properly handled
            track.name = str(t.get("name", ""))
            track.artist = artists
            track.bpm = f.get("tempo")
            track.mode = f.get("mode")
            track.key_camelot = camelot
            track.energy = f.get("energy")
            track.danceability = f.get("danceability")
            track.valence = f.get("valence")
            track.loudness = f.get("loudness")
            track.analyzed_at = datetime.utcnow()
            
            session.add(track)
            stored.append(track)
            
        except Exception as e:
            # Avoid printing problematic characters
            print(f"Error processing track ID {tid}: {type(e).__name__}")
            continue
    
    session.commit()
    return stored
