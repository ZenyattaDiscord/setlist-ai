def to_m3u(tracks: list[dict], spotify_ids: list[str]) -> str:
    lines = ["#EXTM3U"]
    for i, tid in enumerate(spotify_ids):
        meta = tracks[i]
        lines.append(f"#EXTINF:-1,{meta['artist']} - {meta['name']}")
        lines.append(f"spotify:track:{tid}")
    return "\n".join(lines)
