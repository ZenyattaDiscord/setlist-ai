import os
import sys

# Force UTF-8 encoding
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

from fastapi import FastAPI, HTTPException, Request
from sqlmodel import SQLModel, create_engine, Session, select
from dotenv import load_dotenv
from backend.models import Track
from backend.spotify_client import get_audio_analysis, make_spotify, get_playlist_tracks, make_spotify_client_credentials, get_current_user_json
from backend.spotify_client import get_authorize_url, exchange_code_for_token
from backend.spotify_client import extract_track_ids
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
    return get_current_user_json()

# For endpoints that only need public data
@app.post("/import/{playlist_id}")
def import_playlist(playlist_id: str):
    try:
        sp = make_spotify()
        if playlist_id.startswith("http"):
            raise HTTPException(status_code=400, detail="Pass only the playlist ID (not the full URL).")

        raw_tracks = get_playlist_tracks(sp, playlist_id)
        if not raw_tracks:
            raise HTTPException(status_code=404, detail="No tracks found (check playlist visibility or ID).")

        track_ids = extract_track_ids(raw_tracks)
        analyzed_tracks = get_audio_analysis(sp, track_ids)

        return {
            "count": len(raw_tracks),
            "track_id_count": len(track_ids),
            "analyzed_count": len(analyzed_tracks),
            "analyzed_sample": analyzed_tracks[:5]
        }
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

@app.get("/auth/login")
def auth_login():
    url = get_authorize_url()
    return {"authorize_url": url}

@app.get("/auth/callback")
def auth_callback(code: str, state: str | None = None):
    try:
        token_info = exchange_code_for_token(code)
        # token_info should include refresh_token and scope when auth code flow succeeds
        return {
            "ok": True,
            "scope": token_info.get("scope"),
            "expires_at": token_info.get("expires_at"),
            "has_refresh_token": bool(token_info.get("refresh_token"))
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Auth callback failed: {e}")

@app.get("/spotify-test")
def spotify_test():
    try:
        sp = make_spotify()  # use user-auth, not client credentials
        return sp.current_user()
    except Exception as e:
        return {"error": str(e)}
