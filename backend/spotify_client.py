import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import os
from typing import Optional, Iterable, List, Any

SPOTIFY_SCOPES = os.getenv(
    "SPOTIFY_SCOPES",
    "user-read-email user-read-private playlist-read-private playlist-read-collaborative"
)

def make_spotify():
    # For user authentication (needed for current_user())
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope="user-read-private user-read-email"
    ))

def make_spotify_client_credentials():
    # For non-user operations (public playlists, etc)
    try:
        return spotipy.Spotify(auth_manager=spotipy.SpotifyClientCredentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
        ))
    except Exception as e:
        print(f"Error creating Spotify client: {e}")
        return None

def get_playlist_tracks(sp, playlist_id: str):
    items = []
    results = sp.playlist_items(playlist_id, additional_types=("track",))
    while results:
        for it in results["items"]:
            t = it.get("track")
            if t and t.get("id"):
                items.append(t)
        results = sp.next(results) if results.get("next") else None
    return items

def get_audio_analysis(sp, track_ids: list[str]):
    # Spotify batches up to 100
    feats = []
    for i in range(0, len(track_ids), 100):
        feats.append(sp.audio_analysis(track_ids[i]))
    return feats

def get_current_user_json() -> dict:
    """Return the raw JSON (dict) from Spotify's current_user() endpoint.

    Uses the user-auth (OAuth) flow client. Any authentication/authorization
    errors will propagate so the caller can handle them (e.g., FastAPI route
    catching and returning a 401/400 response)."""
    sp = make_spotify()
    return sp.current_user()

def get_spotify_oauth() -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
        scope=SPOTIFY_SCOPES,
        cache_path=".cache",
        show_dialog=False
    )

def get_authorize_url() -> str:
    oauth = get_spotify_oauth()
    return oauth.get_authorize_url()

def exchange_code_for_token(code: str) -> dict:
    oauth = get_spotify_oauth()
    # Spotipy will also save to cache via its cache handler
    token_info = oauth.get_access_token(code)
    # Be explicit in case of version differences
    if hasattr(oauth, "cache_handler"):
        try:
            oauth.cache_handler.save_token_to_cache(token_info)
        except Exception:
            pass
    return token_info

def extract_track_ids(raw_tracks: Iterable[Any]) -> List[str]:
    """
    Accepts either playlist item dicts (with 'track') or raw track dicts.
    Ignores None/booleans/invalid shapes.
    """
    ids: List[str] = []
    for it in raw_tracks or []:
        if not isinstance(it, dict):
            continue
        track = it.get("track") if "track" in it else it
        if isinstance(track, dict):
            tid = track.get("id")
            if tid:
                ids.append(tid)
    return ids
