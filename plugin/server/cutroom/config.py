"""Settings from the repo-root .env, re-read when the file changes so keys pasted mid-session take effect."""
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[3]          # plugin/server/cutroom -> repo root
ENV_FILE = REPO / ".env"
PROJECTS = Path(os.environ.get("CUTROOM_PROJECTS", REPO / "projects"))
TOOLS = REPO / "tools"

_cache = {"mtime": None, "values": {}}

DEFAULTS = {
    "CUTROOM_IMAGE_MODEL": "openai/gpt-image-2.5-sunburst",
    "CUTROOM_IMAGE_MODEL_FALLBACK": "google/gemini-3.1-flash-image",
    "CUTROOM_VIDEO_MODEL": "google/veo-3.1",
    "CUTROOM_VIDEO_MODEL_MOTION": "bytedance/seedance-2.5",
    "CUTROOM_VIDEO_MODEL_FALLBACK": "google/veo-3.1-fast",
    "CUTROOM_TTS_MODEL": "gemini-3.8-flash-tts",
    "CUTROOM_TTS_VOICE": "Sulafat",
    "CUTROOM_ASR_MODEL": "mlx-community/whisper-large-v3-turbo",
    "CUTROOM_JEV_MODEL": "jev-latest",
    "CUTROOM_VIDEO_TIMEOUT_S": "600",
    "CUTROOM_OPENAI_IMAGE_MODEL": "gpt-image-2.5-sunburst",
    "CUTROOM_OPENAI_VIDEO_MODEL": "sora-2-pro",
}


def get(name: str, default: str | None = None) -> str | None:
    """Process env wins (the worker sets CUTROOM_PROJECT_ID), then .env, then defaults. Empty values count as unset."""
    v = os.environ.get(name)
    if v:
        return v
    try:
        m = ENV_FILE.stat().st_mtime
        if m != _cache["mtime"]:
            _cache["values"] = {k: (val or "").strip() for k, val in dotenv_values(ENV_FILE).items()}
            _cache["mtime"] = m
    except OSError:
        pass
    v = _cache["values"].get(name)
    if v:
        return v
    return default if default is not None else DEFAULTS.get(name)


import logging
for _n in ("httpx", "httpcore", "huggingface_hub", "typesafe_sdk", "hpack", "urllib3"):
    logging.getLogger(_n).setLevel(logging.WARNING)


def log(*a):
    print("[cutroom]", *a, file=sys.stderr, flush=True)
