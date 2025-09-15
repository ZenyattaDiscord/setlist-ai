import os, sys
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine
from fastapi.middleware.cors import CORSMiddleware

from backend.spotify_client import (
    make_spotify,
    get_playlist_tracks,
    extract_track_ids,
    extract_all_track_refs,
    get_audio_features,
    get_authorize_url,
    exchange_code_for_token,
    get_current_user_json,
)

load_dotenv()

app = FastAPI()

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sqlite_file_name = os.path.join(base_dir, "db.sqlite3")
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False}, echo=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    try:
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        print(f"DB init error: {e}")

@app.get("/health")
def health():
    return {"ok": True}

@app.api_route("/import/{playlist_id}", methods=["GET", "POST"])
def import_playlist(playlist_id: str, debug: bool = False):
    try:
        if playlist_id.startswith("http"):
            raise HTTPException(status_code=400, detail="Pass only the playlist ID.")
        sp = make_spotify()
        raw_tracks = get_playlist_tracks(sp, playlist_id)
        if not raw_tracks:
            raise HTTPException(status_code=404, detail="No tracks returned.")
        track_ids = extract_track_ids(raw_tracks, debug=debug)
        all_refs = extract_all_track_refs(raw_tracks, debug=debug)
        features = get_audio_features(sp, track_ids) if track_ids else []
        resp = {
            "raw_track_count": len(raw_tracks),
            "spotify_track_id_count": len(track_ids),
            "all_refs_count": len(all_refs),
            "feature_count": len(features),
        }
        if debug and raw_tracks:
            first = raw_tracks[0]
            resp["first_sample"] = {
                "name": first.get("name"),
                "id": first.get("id"),
                "is_local": first.get("is_local"),
                "keys": list(first.keys())
            }
        return resp
    except HTTPException:
        raise
    except Exception as e:
        print(f"/import error: {e}")
        raise HTTPException(status_code=500, detail="Import failed")

@app.post("/build")
def build_set(track_ids: list[str]):
    # Placeholder - implement your set building logic
    return {"received_ids": len(track_ids)}

@app.get("/auth/login")
def auth_login():
    return {"authorize_url": get_authorize_url()}

@app.get("/auth/callback")
def auth_callback(code: str, state: str | None = None):
    try:
        token_info = exchange_code_for_token(code)
        return {
            "ok": True,
            "scope": token_info.get("scope"),
            "expires_at": token_info.get("expires_at"),
            "has_refresh_token": bool(token_info.get("refresh_token")),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Auth callback failed: {e}")

@app.get("/auth/me")
def auth_me():
    try:
        return get_current_user_json()
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/spotify-test")
def spotify_test():
    try:
        me = get_current_user_json()
        return {"id": me.get("id"), "display_name": me.get("display_name")}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
