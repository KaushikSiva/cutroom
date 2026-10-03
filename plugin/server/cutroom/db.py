"""Supabase (service role). Every call degrades to a stderr log when Supabase isn't configured, so the plugin works offline."""
import mimetypes
import threading
from pathlib import Path

from . import config
from .config import log

_client = {"c": None, "key": None}
_lock = threading.Lock()


def client():
    url, key = config.get("SUPABASE_URL") or config.get("NEXT_PUBLIC_SUPABASE_URL"), config.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    with _lock:
        if _client["c"] is None or _client["key"] != key:
            from supabase import create_client
            _client["c"], _client["key"] = create_client(url, key), key
        return _client["c"]


def _safe(fn):
    def wrap(*a, **k):
        c = client()
        if c is None:
            log("supabase off:", fn.__name__, str(a[1:2])[:120] if len(a) > 1 else "")
            return None
        try:
            return fn(c, *a, **k)
        except Exception as e:  # noqa: BLE001
            log("supabase error in", fn.__name__, repr(e)[:300])
            return None
    wrap.__name__ = fn.__name__
    return wrap


@_safe
def insert_project(c, row: dict):
    return c.table("projects").insert(row).execute().data[0]


@_safe
def get_project(c, pid: str):
    r = c.table("projects").select("*").eq("id", pid).limit(1).execute().data
    return r[0] if r else None


@_safe
def update(c, pid: str, **fields):
    c.table("projects").update(fields).eq("id", pid).execute()
    return True


@_safe
def emit(c, pid: str, kind: str, message: str, data: dict | None = None):
    log(f"{kind}: {message}")
    c.table("events").insert({"project_id": pid, "kind": kind, "message": message[:2000], "data": data or {}}).execute()
    return True


@_safe
def insert_clip(c, row: dict):
    return c.table("clips").insert(row).execute().data[0]


@_safe
def mark_clip_used(c, pid: str, youtube_id: str, start: float, end: float):
    c.table("clips").update({"used": True, "start_s": start, "end_s": end}).eq("project_id", pid).eq("youtube_id", youtube_id).execute()
    return True


@_safe
def upload(c, local: str | Path, key: str) -> str | None:
    """Upload to the public 'media' bucket and return its public URL. Large files are fine up to the project's limit."""
    local = Path(local)
    ctype = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
    with open(local, "rb") as fh:
        c.storage.from_("media").upload(key, fh.read(), {"content-type": ctype, "upsert": "true", "cache-control": "3600"})
    return c.storage.from_("media").get_public_url(key).rstrip("?")


def stage(pid: str, name: str, progress: int, message: str | None = None):
    update(pid, stage=name, progress=progress)
    emit(pid, "stage", message or name, {"stage": name, "progress": progress})
