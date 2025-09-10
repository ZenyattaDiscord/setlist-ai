import os
import sys

# Force UTF-8 encoding
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

from fastapi import FastAPI, HTTPException
from sqlmodel import SQLModel, create_engine, Session, select
from dotenv import load_dotenv
from backend.models import Track
from backend.spotify_client import make_spotify, get_playlist_tracks, get_audio_features,make_spotify_client_credentials
from backend.analysis import upsert_tracks
from backend.set_builder import compile_set
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
app = FastAPI()

# Add database configuration
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sqlite_file_name = os.path.join(base_dir, "db.sqlite3")
sqlite_url = f"sqlite:///{sqlite_file_name}"

# Clean up parameter formatting
engine = create_engine(
    sqlite_url, 
    connect_args={"check_same_thread": False},
    echo=False
)

# Configure CORS if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables on startup
@app.on_event("startup")
def on_startup():
    try:
        SQLModel.metadata.create_all(engine)
        print(f"Database initialized at {sqlite_file_name}")
    except Exception as e:
        print(f"Database initialization error: {e}")
        # You might want to exit the app here if the database is critical
        # import sys
        # sys.exit(1)

@app.get("/health")
def health():
    return {"ok": True}

# For endpoints that need user data (profile, private playlists)
@app.get("/auth/me")
def auth_me():
    try:
        sp = make_spotify()  # OAuth flow
        me = sp.current_user()
        return {"id": me["id"], "display_name": me.get("display_name")}
    except Exception as e:
        error_details = str(e)
        print(f"Spotify auth error details: {error_details}")
        # Check the specific error
        if "authentication" in error_details.lower():
            print("Authentication error detected")
        return {"error": error_details, "type": type(e).__name__}

# For endpoints that only need public data
@app.post("/import/{playlist_id}")
def import_playlist(playlist_id: str):
    try:
        # If only public playlists:
        sp = make_spotify_client_credentials()
        
        # Validate the ID shape to catch pasted URLs early
        if playlist_id.startswith("http"):
            raise HTTPException(status_code=400, detail="Pass only the playlist ID, not the full URL.")

        raw_tracks = get_playlist_tracks(sp, playlist_id)
        if not raw_tracks:
            raise HTTPException(status_code=404, detail="No tracks found (check playlist visibility or ID).")

        ids = [t["id"] for t in raw_tracks if t.get("id")]
        feats = get_audio_features(sp, ids)
        by_id = {f["id"]: f for f in feats if f}

        with Session(engine) as s:
            try:
                stored = upsert_tracks(s, raw_tracks, by_id)
                return {"imported": len(stored)}
            except UnicodeEncodeError as ue:
                print(f"Unicode error in track data: {ue}")
                # Handle the encoding error more gracefully
                raise HTTPException(status_code=500, detail="Track contains special characters that couldn't be processed")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Import error details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")

@app.post("/build")
def build_set(playlist_id: str, minutes: int = 60, profile: str = "peak"):
    curve_map = {
        "opening": [5,6,5,7,6,8],
        "peak":    [7,8,9,10,9,8],
        "closing": [8,7,6,5,4,3]
    }
    with Session(engine) as s:
        tracks = s.exec(select(Track).where(Track.spotify_id.in_(
            [t["track"]["id"] for t in []]  # simple: ignore; we’ll just use all analyzed tracks for POC
        ))).all()
        if not tracks: tracks = s.exec(select(Track)).all()
        setlist = compile_set(tracks, minutes=minutes, energy_curve=curve_map.get(profile, curve_map["peak"]))
        return {"count": len(setlist), "set": setlist}

@app.get("/spotify-test")
def spotify_test():
    try:
        sp = make_spotify()
        return {"status": "Spotify client created successfully"}
    except Exception as e:
        return {"error": str(e)}
