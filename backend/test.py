from spotify_client import make_spotify_from_cache, get_tracks_with_features

sp = make_spotify_from_cache()  # uses .cache
# by track IDs
data = get_tracks_with_features(sp, ["3n3Ppam7vgaVa1iaRUc9Lp"])  # example ID
print(data)

# by playlist (reuse your existing helper)
from spotify_client import get_playlist_tracks
items = get_playlist_tracks(sp, "YOUR_PLAYLIST_ID")
track_ids = [it["track"]["id"] for it in items if it.get("track") and it["track"].get("id")]
data = get_tracks_with_features(sp, track_ids[:50])  # Spotify limits; slice as needed
print(data)