import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import os

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

def get_audio_features(sp, track_ids: list[str]):
    # Spotify batches up to 100
    feats = []
    for i in range(0, len(track_ids), 100):
        feats.extend(sp.audio_features(track_ids[i:i+100]))
    return feats

def get_current_user_json() -> dict:
    """Return the raw JSON (dict) from Spotify's current_user() endpoint.

    Uses the user-auth (OAuth) flow client. Any authentication/authorization
    errors will propagate so the caller can handle them (e.g., FastAPI route
    catching and returning a 401/400 response)."""
    sp = make_spotify()
    return sp.current_user()
