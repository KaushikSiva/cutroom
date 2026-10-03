"""Per-project workspace on disk plus a state.json that mirrors the plan and every asset produced."""
import json
import os
import threading
import uuid
from pathlib import Path

from . import config, db
from .util import dims

SUBDIRS = ("refs", "keyframes", "shots", "clips", "gfx", "audio", "cuts", "frames")
_lock = threading.Lock()


def pdir(pid: str) -> Path:
    d = config.PROJECTS / pid
    for s in SUBDIRS:
        (d / s).mkdir(parents=True, exist_ok=True)
    return d


def load(pid: str) -> dict:
    f = pdir(pid) / "state.json"
    if f.exists():
        return json.loads(f.read_text())
    # project created elsewhere (web/worker): rebuild from Supabase
    row = db.get_project(pid) or {}
    st = {"id": pid, "brief": row.get("brief") or row.get("topic", ""), "aspect_ratio": row.get("aspect_ratio") or "16:9", "length_s": row.get("length_s", 60), "style": row.get("style") or "",
          "plan": row.get("script") or None, "assets": {}}
    st["width"], st["height"] = dims(st["aspect_ratio"])
    save(pid, st)
    return st


def save(pid: str, st: dict) -> None:
    with _lock:
        f = pdir(pid) / "state.json"
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, indent=1))
        tmp.replace(f)


def put_asset(pid: str, kind: str, key: str, value: dict) -> dict:
    """assets[kind][key] = value (kinds: refs, keyframes, shots, clips, graphics, voice, music, cuts)."""
    st = load(pid)
    st.setdefault("assets", {}).setdefault(kind, {})[key] = value
    save(pid, st)
    return st


def start(brief: str, aspect_ratio: str, length_s: int, style: str) -> dict:
    pid = os.environ.get("CUTROOM_PROJECT_ID") or config.get("CUTROOM_PROJECT_ID_OVERRIDE") or ""
    existing = db.get_project(pid) if pid else None
    if not pid:
        pid = str(uuid.uuid4())
    w, h = dims(aspect_ratio)
    st = {"id": pid, "brief": brief, "aspect_ratio": aspect_ratio, "length_s": length_s, "style": style,
          "width": w, "height": h, "plan": None, "assets": {}, "round": 0}
    f = pdir(pid) / "state.json"
    if f.exists():  # resume
        old = json.loads(f.read_text())
        old.update({k: v for k, v in st.items() if k not in ("plan", "assets", "round")})
        st = old
    save(pid, st)
    if existing:
        db.update(pid, status="running", stage="brief", progress=2)
        db.update(pid, brief=brief, aspect_ratio=aspect_ratio, style=style)
    else:
        row = {"id": pid, "topic": brief[:200], "brief": brief, "aspect_ratio": aspect_ratio, "style": style, "length_s": length_s,
               "source": "claude-code", "status": "running", "stage": "brief", "progress": 2, "is_public": True}
        if db.insert_project(row) is None and db.client() is not None:  # older schema without the 002 columns
            for k in ("brief", "aspect_ratio", "style"):
                row.pop(k)
            db.insert_project(row)
    return st
