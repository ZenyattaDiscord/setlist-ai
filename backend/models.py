from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

class Track(SQLModel, table=True):
    spotify_id: str = Field(primary_key=True)
    name: str = Field(default="")  # Ensure empty string defaults
    artist: str = Field(default="")
    bpm: float | None = None
    key_camelot: str | None = None   # e.g., "8A"
    mode: int | None = None          # 0 minor, 1 major (from Spotify)
    energy: float | None = None      # 0..1 (Spotify)
    danceability: float | None = None
    valence: float | None = None
    loudness: float | None = None
    analyzed_at: datetime | None = None
    genre: str | None = None         # placeholder; can infer later
