"""Real footage from YouTube via yt-dlp: search, record the license, download only the needed seconds.

CUTROOM_FOOTAGE_LICENSE=cc (default) keeps Creative Commons only; =any searches all of YouTube."""
import urllib.parse
from pathlib import Path

from . import config, db
from .config import log
from .providers import jev

CC_FILTER = "EgIwAQ%3D%3D"  # YouTube search filter: Creative Commons
CACHE = config.REPO / "projects" / "_footage_cache"


def cc_only() -> bool:
    return (config.get("CUTROOM_FOOTAGE_LICENSE") or "cc").lower() != "any"


def transcript(youtube_id: str, contains: str | None = None, lang: str = "en") -> dict:
    """-> {lines: [{start, end, text}], source} from YouTube captions (json3), no media download."""
    import json as _json
    import urllib.request
    from yt_dlp import YoutubeDL
    with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 20}) as ydl:
        i = ydl.extract_info(f"https://www.youtube.com/watch?v={youtube_id}", download=False)
    lines, source = [], None
    for kind in ("subtitles", "automatic_captions"):
        tracks = i.get(kind) or {}
        key = next((k for k in tracks if k == lang), None) or next((k for k in tracks if k.startswith(lang)), None) \
            or next(iter(tracks), None)
        fmt = next((f for f in tracks.get(key) or [] if f.get("ext") == "json3"), None) if key else None
        if not fmt:
            continue
        with urllib.request.urlopen(fmt["url"], timeout=20) as r:
            data = _json.load(r)
        for ev in data.get("events", []):
            text = "".join(seg.get("utf8", "") for seg in ev.get("segs") or []).strip()
            if text:
                st = ev.get("tStartMs", 0) / 1000
                lines.append({"start": round(st, 2), "end": round(st + ev.get("dDurationMs", 0) / 1000, 2), "text": text})
        source = f"{kind}:{key}"
        break
    if contains:
        hits = {k for k, ln in enumerate(lines) if contains.lower() in ln["text"].lower()}
        keep = sorted({j for k in hits for j in range(max(0, k - 2), min(len(lines), k + 3))})
        lines = [lines[k] for k in keep]
    return {"youtube_id": youtube_id, "title": i.get("title"), "duration": i.get("duration"), "source": source,
            "lines": lines[:400], "truncated": len(lines) > 400}


def search(query: str, n: int = 6, shot_text: str | None = None, pid: str | None = None) -> list[dict]:
    """-> [{id, url, title, channel, license, duration, thumb, description, rank?}] (Creative Commons only)"""
    from yt_dlp import YoutubeDL
    cc_only = globals()["cc_only"]()
    url = "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query}) + ("&sp=" + CC_FILTER if cc_only else "")
    with YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True, "playlistend": n * 3}) as ydl:
        try:
            flat = ydl.extract_info(url, download=False).get("entries") or []
        except Exception as e:  # noqa: BLE001
            log("cc search failed, falling back to ytsearch:", repr(e)[:200])
            flat = ydl.extract_info(f"ytsearch{n * 3}:{query}" + (" creative commons" if cc_only else ""), download=False).get("entries") or []
    # metadata for every candidate in parallel (one request each); keep search order
    def meta(h):
        vid = h.get("id")
        if not vid or (h.get("duration") and h["duration"] > 4 * 3600):
            return None
        try:
            with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 20}) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
        except Exception as e:  # noqa: BLE001
            log("skip", vid, repr(e)[:120])
            return None
        lic = info.get("license") or ("" if cc_only else "Standard YouTube License")
        if cc_only and "creative commons" not in lic.lower():
            return None
        return {"id": vid, "url": info.get("webpage_url"), "title": info.get("title"), "channel": info.get("uploader"),
                "license": lic, "duration": info.get("duration"), "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "description": (info.get("description") or "")[:600],
                "chapters": [{"title": c.get("title"), "start": c.get("start_time"), "end": c.get("end_time")}
                             for c in (info.get("chapters") or [])][:30]}
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        out = [m for m in pool.map(meta, flat) if m][:n]
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
        # YouTube rate-limits and bot-checks heavy use from one machine; back off and retry rather than give up
        import time as _time
        for attempt in range(4):
            try:
                with YoutubeDL(opts | {"socket_timeout": 30, "retries": 3}) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={youtube_id}"])
                break
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                if attempt == 3 or not any(k in msg for k in ("429", "Too Many", "Sign in to confirm", "bot")):
                    raise
                wait = 15 * (attempt + 1)
                log(f"youtube throttled ({msg[:80]}), retrying in {wait}s")
                _time.sleep(wait)
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
