"""Real Creative Commons footage from YouTube via yt-dlp: search, verify license, download only the needed seconds."""
import urllib.parse
from pathlib import Path

from . import config, db
from .config import log
from .providers import jev

CC_FILTER = "EgIwAQ%3D%3D"  # YouTube search filter: Creative Commons
CACHE = config.REPO / "projects" / "_footage_cache"


def search(query: str, n: int = 6, shot_text: str | None = None, pid: str | None = None) -> list[dict]:
    """-> [{id, url, title, channel, license, duration, thumb, description, rank?}] (Creative Commons only)"""
    from yt_dlp import YoutubeDL
    url = "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query}) + "&sp=" + CC_FILTER
    with YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True, "playlistend": n * 3}) as ydl:
        try:
            flat = ydl.extract_info(url, download=False).get("entries") or []
        except Exception as e:  # noqa: BLE001
            log("cc search failed, falling back to ytsearch:", repr(e)[:200])
            flat = ydl.extract_info(f"ytsearch{n * 3}:{query} creative commons", download=False).get("entries") or []
    out = []
    with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        for h in flat:
            if len(out) >= n:
                break
            vid = h.get("id")
            if not vid or (h.get("duration") and h["duration"] > 4 * 3600):
                continue
            try:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
            except Exception as e:  # noqa: BLE001
                log("skip", vid, repr(e)[:120])
                continue
            lic = info.get("license") or ""
            if "creative commons" not in lic.lower():
                continue
            out.append({"id": vid, "url": info.get("webpage_url"), "title": info.get("title"), "channel": info.get("uploader"),
                        "license": lic, "duration": info.get("duration"), "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                        "description": (info.get("description") or "")[:600],
                        "chapters": [{"title": c.get("title"), "start": c.get("start_time"), "end": c.get("end_time")}
                                     for c in (info.get("chapters") or [])][:30]})
    ranks = jev.rank_footage(shot_text or query, out) if out else None
    if ranks:
        by = {r["id"]: r for r in ranks}
        for c in out:
            c["rank"] = by.get(c["id"])
        out.sort(key=lambda c: -(c["rank"]["score"] if c.get("rank") else 0))
    if pid:
        for c in out:
            db.insert_clip({"project_id": pid, "youtube_id": c["id"], "title": c["title"], "channel": c["channel"],
                            "license": c["license"], "url": c["url"], "description": c["description"][:300]})
    return out


def download_section(youtube_id: str, start: float, end: float, out: Path) -> Path:
    """Downloads only [start, end] at <=1080p, re-encoded with clean keyframes at the cut points."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import download_range_func
    out = Path(out)
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{youtube_id}_{start:.2f}_{end:.2f}.mp4"
    if not cached.exists():
        opts = {"format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/bv*[height<=1080]+ba/b",
                "download_ranges": download_range_func(None, [(start, end)]), "force_keyframes_at_cuts": True,
                "merge_output_format": "mp4", "outtmpl": str(cached.with_suffix(".%(ext)s")), "quiet": True, "no_warnings": True, "noprogress": True}
        with YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={youtube_id}"])
        if not cached.exists():
            cands = sorted(CACHE.glob(cached.stem + ".*"))
            if not cands:
                raise RuntimeError(f"download produced no file for {youtube_id}")
            cands[0].rename(cached)
    out.write_bytes(cached.read_bytes())
    return out


def info(youtube_id: str) -> dict:
    from yt_dlp import YoutubeDL
    with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        i = ydl.extract_info(f"https://www.youtube.com/watch?v={youtube_id}", download=False)
    return {"id": youtube_id, "url": i.get("webpage_url"), "title": i.get("title"), "channel": i.get("uploader"),
            "license": i.get("license") or "", "duration": i.get("duration"), "thumb": f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg"}
