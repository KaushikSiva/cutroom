"""OpenAI direct: GPT Image 2.5 Sunburst for keyframes and references (Sora 2 was shut down on 2026-09-24).

Used when OPENAI_API_KEY is set and OpenRouter is unavailable (no key, or every OpenRouter model failed).
"""
import base64
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
