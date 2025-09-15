import os
from typing import Optional, Iterable, List, Any, Dict

import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials

# Config
SPOTIFY_SCOPES = os.getenv(
    "SPOTIFY_SCOPES",
    "user-read-email user-read-private playlist-read-private playlist-read-collaborative"
)
USER_CACHE_PATH = os.getenv("SPOTIFY_USER_CACHE", ".cache-user")


# Auth helpers

def make_spotify() -> spotipy.Spotify:
    """
    User-auth Spotify client (Authorization Code flow). Requires a cached token.
    """
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=SPOTIFY_SCOPES,
        cache_path=USER_CACHE_PATH,
        show_dialog=False,
    ))


def make_spotify_client_credentials() -> Optional[spotipy.Spotify]:
    """
    App-only client credentials (no user context).
    """
    try:
        return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        ))
    except Exception as e:
        print(f"Error creating Spotify client credentials: {e}")
        return None


def get_spotify_oauth() -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=SPOTIFY_SCOPES,
        cache_path=USER_CACHE_PATH,
        show_dialog=False,
    )


def get_authorize_url() -> str:
    return get_spotify_oauth().get_authorize_url()


def exchange_code_for_token(code: str) -> dict:
    oauth = get_spotify_oauth()
    # Spotipy versions differ on as_dict param; try both.
    try:
        token_info = oauth.get_access_token(code, as_dict=True)  # type: ignore[arg-type]
    except TypeError:
        token_info = oauth.get_access_token(code)  # returns dict on older versions
    # Persist via cache handler if available
    try:
        if hasattr(oauth, "cache_handler") and getattr(oauth, "cache_handler"):
            oauth.cache_handler.save_token_to_cache(token_info)  # type: ignore[attr-defined]
    except Exception:
        pass
    return token_info


def get_current_user_json() -> dict:
    sp = make_spotify()
    return sp.current_user()


# Data helpers

def get_playlist_tracks(sp: spotipy.Spotify, playlist_id: str, include_local: bool = True) -> List[Dict[str, Any]]:
    """
    Return a flat list of track dicts from a playlist.
    - Skips non-track items (e.g., episodes).
    - Keeps local tracks when include_local=True (adds 'local_id').
    """
    items: List[Dict[str, Any]] = []
    results = sp.playlist_items(playlist_id, additional_types=("track",), limit=100)
    while True:
        for it in (results or {}).get("items", []):
            t = (it or {}).get("track")
            # Some entries have track=None (unavailable)
            if not isinstance(t, dict):
                continue
            # Only keep proper tracks
            if t.get("type") != "track":
                continue
            if t.get("id"):
                items.append(t)
            elif include_local and t.get("is_local"):
                lt = dict(t)
                # stable synthetic id for local items
                artist_names = ",".join(a.get("name", "") for a in (lt.get("artists") or []))
                lt["local_id"] = f"local::{lt.get('name','unknown')}::{artist_names}"
                items.append(lt)
        # Pagination
        if results.get("next"):
            results = sp.next(results)
        else:
            break
    return items


def extract_track_ids(raw_tracks: Iterable[Any], debug: bool = False) -> List[str]:
    """
    Accepts either track dicts or playlist item dicts. Returns only real Spotify IDs.
    """
    items = list(raw_tracks or [])
    ids: List[str] = []
    skipped_samples = []
    for it in items:
        # Normalize to a track dict
        track = None
        if isinstance(it, dict):
            track = it.get("track") if "track" in it else it
        if not isinstance(track, dict):
            if debug and len(skipped_samples) < 5:
                skipped_samples.append({"reason": "track_not_dict", "type": str(type(it)), "keys": list(it.keys()) if isinstance(it, dict) else None})
            continue
        tid = track.get("id")
        if tid:
            ids.append(tid)
        else:
            if debug and len(skipped_samples) < 5:
                skipped_samples.append({
                    "reason": "no_id",
                    "name": track.get("name"),
                    "is_local": track.get("is_local"),
                })
    if debug:
        print(f"[extract_track_ids] total={len(items)} extracted={len(ids)} sample_skips={skipped_samples}")
    return ids


def extract_all_track_refs(raw_tracks: Iterable[Any], debug: bool = False) -> List[str]:
    """
    Like extract_track_ids but retains local tracks using local_id or a readable fallback.
    """
    items = list(raw_tracks or [])
    refs: List[str] = []
    for it in items:
        track = None
        if isinstance(it, dict):
            track = it.get("track") if "track" in it else it
        if not isinstance(track, dict):
            continue
        if track.get("id"):
            refs.append(track["id"])
        elif track.get("is_local"):
            refs.append(track.get("local_id") or f"local::{track.get('name','unknown')}")
    if debug:
        print(f"[extract_all_track_refs] total={len(items)} refs={len(refs)}")
    return refs


def get_audio_features(sp: spotipy.Spotify, track_ids: List[str]) -> List[dict]:
    """
    Batch fetch audio features (100 per call).
    """
    feats: List[dict] = []
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i:i+100]
        if batch:
            feats.extend([f for f in sp.audio_features(batch) if f])
    return feats


def get_audio_analysis(sp: spotipy.Spotify, track_ids: List[str]) -> List[dict]:
    """
    Per-track audio analysis (not batched by Spotify). Heavier than features.
    """
    analyses: List[dict] = []
    for tid in track_ids:
        try:
            analyses.append(sp.audio_analysis(tid))
        except Exception as e:
            analyses.append({"id": tid, "error": str(e)})
    return analyses
