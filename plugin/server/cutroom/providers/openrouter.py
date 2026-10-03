"""OpenRouter: keyframes/reference images (GPT Image 2.5 Sunburst) and video shots (Seedance 2.5 for motion, Veo 3.1 otherwise).

Fallbacks: image → second image model → typographic placeholder card; video → fallback model → Ken Burns move on the keyframe.
"""
import base64
import mimetypes
import time
from pathlib import Path

import requests

from .. import config, db
from ..config import log
from ..util import dims, ffmpeg

API = "https://openrouter.ai/api/v1"
_video_models = {"t": 0, "data": {}}


def _key():
    return config.get("OPENROUTER_API_KEY")


def _headers():
    return {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json",
            "HTTP-Referer": "https://cutroom.vercel.app", "X-Title": "Cutroom"}


def data_url(path: str | Path) -> str:
    mt = mimetypes.guess_type(str(path))[0] or "image/png"
    return f"data:{mt};base64," + base64.b64encode(Path(path).read_bytes()).decode()


# ------------------------------------------------------------------ images
def gen_image(prompt: str, out: Path, aspect_ratio: str = "16:9", refs: list[str] | None = None) -> dict:
    """-> {path, model, fallback}"""
    out = Path(out)
    if _key():
        for model in (config.get("CUTROOM_IMAGE_MODEL"), config.get("CUTROOM_IMAGE_MODEL_FALLBACK")):
            body = {"model": model, "prompt": prompt, "aspect_ratio": aspect_ratio, "n": 1}
            if refs:
                body["input_references"] = [{"type": "image_url", "image_url": {"url": data_url(r)}} for r in refs if Path(r).exists()][:8]
            try:
                r = requests.post(f"{API}/images", headers=_headers(), json=body, timeout=300)
                if r.status_code >= 400:
                    log("image gen", model, r.status_code, r.text[:300])
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
                log("image gen error", model, repr(e)[:300])
    from . import openai_direct
    res = openai_direct.gen_image(prompt, out, aspect_ratio, refs)
    if res:
        return res
    placeholder_card(prompt, out, aspect_ratio)
    return {"path": str(out), "model": "placeholder", "fallback": True}


def placeholder_card(text: str, out: Path, aspect_ratio: str = "16:9") -> None:
    """A clean dark gradient card with the prompt — keeps animatics and fallbacks watchable."""
    from PIL import Image, ImageDraw, ImageFont
    w, h = dims(aspect_ratio)
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / h
        c = (int(14 + 20 * t), int(16 + 12 * t), int(28 + 40 * t))
        for x in range(w):
            px[x, y] = c
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Avenir Next.ttc", int(h * 0.04))
    except OSError:
        font = ImageFont.load_default()
    words, lines, line = text.split(), [], ""
    for wd in words:
        if len(line) + len(wd) > 42:
            lines.append(line); line = wd
        else:
            line = (line + " " + wd).strip()
    lines.append(line)
    lines = lines[:6]
    y = h / 2 - len(lines) * h * 0.03
    for ln in lines:
        tw = d.textlength(ln, font=font)
        d.text(((w - tw) / 2, y), ln, fill=(220, 225, 240), font=font)
        y += h * 0.06
    img.save(out)


# ------------------------------------------------------------------ video
def video_models() -> dict:
    if time.time() - _video_models["t"] > 3600 or not _video_models["data"]:
        try:
            d = requests.get(f"{API}/videos/models", timeout=30).json()["data"]
            _video_models["data"] = {m["id"]: m for m in d}
            _video_models["t"] = time.time()
        except Exception as e:  # noqa: BLE001
            log("video model list failed", repr(e)[:200])
    return _video_models["data"]


def _pick(values, want, numeric=False):
    if not values:
        return want
    if want in values:
        return want
    if numeric:
        return min(values, key=lambda v: (abs(v - want), -v))
    return values[0]


def _public_url(path: Path, pid: str | None) -> str:
    """Providers fetch frame/reference images by URL; use Supabase public storage, else a data URL."""
    if pid:
        url = db.upload(path, f"projects/{pid}/frames/{path.name}")
        if url:
            return url
    return data_url(path)


def gen_video(prompt: str, out: Path, duration_s: float, aspect_ratio: str = "16:9", keyframe: str | None = None,
              refs: list[str] | None = None, motion: bool = False, pid: str | None = None) -> dict:
    """-> {path, model, fallback, duration}"""
    out = Path(out)
    models = [config.get("CUTROOM_VIDEO_MODEL_MOTION") if motion else config.get("CUTROOM_VIDEO_MODEL"),
              config.get("CUTROOM_VIDEO_MODEL_FALLBACK")]
    if _key():
        catalog = video_models()
        frame_url = _public_url(Path(keyframe), pid) if keyframe and Path(keyframe).exists() else None
        ref_urls = [_public_url(Path(r), pid) for r in (refs or []) if Path(r).exists()][:3]
        for model in models:
            m = catalog.get(model, {})
            dur = _pick(m.get("supported_durations"), max(4, round(duration_s)), numeric=True)
            res = _pick(m.get("supported_resolutions"), "1080p" if "veo" in model else "720p")
            ar = _pick(m.get("supported_aspect_ratios"), aspect_ratio)
            body = {"model": model, "prompt": prompt, "duration": dur, "resolution": res, "aspect_ratio": ar, "generate_audio": False}
            if frame_url and "first_frame" in (m.get("supported_frame_images") or ["first_frame"]):
                body["frame_images"] = [{"type": "image_url", "image_url": {"url": frame_url}, "frame_type": "first_frame"}]
            elif ref_urls:
                body["input_references"] = [{"type": "image_url", "image_url": {"url": u}} for u in ref_urls]
            try:
                r = requests.post(f"{API}/videos", headers=_headers(), json=body, timeout=60)
                if r.status_code >= 400:
                    log("video submit", model, r.status_code, r.text[:400])
                    continue
                job = r.json()
                poll = job.get("polling_url") or f"{API}/videos/{job['id']}"
                deadline = time.time() + float(config.get("CUTROOM_VIDEO_TIMEOUT_S"))
                while time.time() < deadline:
                    time.sleep(6)
                    s = requests.get(poll, headers=_headers(), timeout=30).json()
                    if s.get("status") == "completed":
                        url = (s.get("unsigned_urls") or [f"{API}/videos/{job['id']}/content"])[0]
                        v = requests.get(url, headers=_headers(), timeout=300)
                        v.raise_for_status()
                        out.write_bytes(v.content)
                        return {"path": str(out), "model": model, "fallback": False, "duration": dur}
                    if s.get("status") in ("failed", "cancelled", "error"):
                        log("video job failed", model, str(s.get("error"))[:300])
                        break
                else:
                    log("video job timed out", model)
            except Exception as e:  # noqa: BLE001
                log("video gen error", model, repr(e)[:300])
    from . import openai_direct
    res = openai_direct.gen_video(prompt, out, duration_s, aspect_ratio, keyframe, motion)
    if res:
        return res
    if not keyframe or not Path(keyframe).exists():
        keyframe = str(out.with_suffix(".png"))
        placeholder_card(prompt, Path(keyframe), aspect_ratio)
    ken_burns(keyframe, out, duration_s, aspect_ratio, push_in=not motion)
    return {"path": str(out), "model": "ken-burns", "fallback": True, "duration": duration_s}


def ken_burns(image: str, out: Path, duration_s: float, aspect_ratio: str = "16:9", push_in: bool = True) -> None:
    w, h = dims(aspect_ratio)
    frames = max(1, int(duration_s * 30))
    z = "min(zoom+0.0009,1.18)" if push_in else "if(eq(on,1),1.18,max(zoom-0.0009,1.0))"
    ffmpeg("-loop", "1", "-i", image, "-t", f"{duration_s:.3f}",
           "-vf", f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
                  f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps=30,format=yuv420p",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-an", str(out))
