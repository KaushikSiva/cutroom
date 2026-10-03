"""OpenAI direct: GPT Image 2.5 Sunburst for keyframes/references and Sora 2 for video shots.

Used when OPENAI_API_KEY is set and OpenRouter is unavailable (no key, or every OpenRouter model failed).
"""
import base64
import io
import time
from pathlib import Path

import requests

from .. import config
from ..config import log

API = "https://api.openai.com/v1"


def _key():
    return config.get("OPENAI_API_KEY")


def available() -> bool:
    return bool(_key())


def _auth():
    return {"Authorization": f"Bearer {_key()}"}


# GPT Image takes a fixed set of sizes; the assembler crops to the exact frame afterwards
def _image_size(aspect_ratio: str) -> str:
    return {"9:16": "1024x1536", "1:1": "1024x1024"}.get(aspect_ratio, "1536x1024")


def gen_image(prompt: str, out: Path, aspect_ratio: str = "16:9", refs: list[str] | None = None) -> dict | None:
    """-> {path, model, fallback} or None when unavailable/failed"""
    if not _key():
        return None
    out = Path(out)
    for model in (config.get("CUTROOM_OPENAI_IMAGE_MODEL"), "gpt-image-2"):
        try:
            refs_ok = [r for r in (refs or []) if Path(r).exists()][:8]
            if refs_ok:
                # references go through the edits endpoint so the subject stays consistent
                files = [("image[]", (Path(r).name, Path(r).read_bytes(), "image/png")) for r in refs_ok]
                r = requests.post(f"{API}/images/edits", headers=_auth(), files=files, timeout=300,
                                  data={"model": model, "prompt": prompt, "size": _image_size(aspect_ratio), "n": "1"})
            else:
                r = requests.post(f"{API}/images/generations", headers=_auth(), timeout=300,
                                  json={"model": model, "prompt": prompt, "size": _image_size(aspect_ratio), "n": 1})
            if r.status_code >= 400:
                log("openai image", model, r.status_code, r.text[:300])
                continue
            img = r.json()["data"][0]
            if img.get("b64_json"):
                out.write_bytes(base64.b64decode(img["b64_json"]))
            elif img.get("url"):
                out.write_bytes(requests.get(img["url"], timeout=120).content)
            else:
                continue
            return {"path": str(out), "model": model, "fallback": False}
        except Exception as e:  # noqa: BLE001
            log("openai image error", model, repr(e)[:300])
    return None


# Sora 2 takes 4/8/12 s and landscape or portrait sizes; square is generated landscape and cropped later
def _video_size(aspect_ratio: str) -> str:
    return "720x1280" if aspect_ratio == "9:16" else "1280x720"


def _seconds(duration_s: float) -> str:
    return str(min((4, 8, 12), key=lambda s: (abs(s - duration_s), -s)))


def _fit_reference(keyframe: str, size: str) -> bytes:
    """Sora requires the input reference to match the output size exactly."""
    from PIL import Image, ImageOps
    w, h = map(int, size.split("x"))
    img = ImageOps.fit(Image.open(keyframe).convert("RGB"), (w, h))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def gen_video(prompt: str, out: Path, duration_s: float, aspect_ratio: str = "16:9", keyframe: str | None = None,
              motion: bool = False) -> dict | None:
    """-> {path, model, fallback, duration} or None when unavailable/failed"""
    if not _key():
        return None
    out = Path(out)
    size, seconds = _video_size(aspect_ratio), _seconds(duration_s)
    for model in (config.get("CUTROOM_OPENAI_VIDEO_MODEL"), "sora-2"):
        try:
            data = {"model": model, "prompt": prompt, "seconds": seconds, "size": size}
            files = None
            if keyframe and Path(keyframe).exists():
                files = {"input_reference": ("keyframe.png", _fit_reference(keyframe, size), "image/png")}
            r = requests.post(f"{API}/videos", headers=_auth(), data=data, files=files, timeout=120)
            if r.status_code >= 400:
                log("sora submit", model, r.status_code, r.text[:400])
                continue
            vid = r.json()["id"]
            deadline = time.time() + float(config.get("CUTROOM_VIDEO_TIMEOUT_S"))
            while time.time() < deadline:
                time.sleep(8)
                s = requests.get(f"{API}/videos/{vid}", headers=_auth(), timeout=30).json()
                if s.get("status") == "completed":
                    v = requests.get(f"{API}/videos/{vid}/content", headers=_auth(), timeout=300)
                    v.raise_for_status()
                    out.write_bytes(v.content)
                    return {"path": str(out), "model": model, "fallback": False, "duration": float(seconds)}
                if s.get("status") == "failed":
                    log("sora job failed", model, str(s.get("error"))[:300])
                    break
            else:
                log("sora job timed out", model)
        except Exception as e:  # noqa: BLE001
            log("sora error", model, repr(e)[:300])
    return None
