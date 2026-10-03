"""Veo 3.1 through the Gemini API (google-genai), used when OpenRouter is unavailable.

Image-to-video from the keyframe; 4, 6 or 8 s; 16:9 or 9:16 (square is cropped from 16:9 at assembly).
"""
import time
from pathlib import Path

from .. import config
from ..config import log


def available() -> bool:
    return bool(config.get("GEMINI_API_KEY"))


def _seconds(duration_s: float) -> int:
    return min((4, 6, 8), key=lambda s: (abs(s - duration_s), -s))


def gen_video(prompt: str, out: Path, duration_s: float, aspect_ratio: str = "16:9", keyframe: str | None = None,
              motion: bool = False) -> dict | None:
    """-> {path, model, fallback, duration} or None when unavailable/failed"""
    if not available():
        return None
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.get("GEMINI_API_KEY"))
    out, seconds = Path(out), _seconds(duration_s)
    image = None
    if keyframe and Path(keyframe).exists():
        image = types.Image(image_bytes=Path(keyframe).read_bytes(), mime_type="image/png")
    for model in (config.get("CUTROOM_VEO_MODEL"), config.get("CUTROOM_VEO_MODEL_FALLBACK")):
        try:
            cfg = types.GenerateVideosConfig(aspect_ratio="9:16" if aspect_ratio == "9:16" else "16:9",
                                             duration_seconds=seconds, number_of_videos=1)
            op = client.models.generate_videos(model=model, prompt=prompt, image=image, config=cfg)
            deadline = time.time() + float(config.get("CUTROOM_VIDEO_TIMEOUT_S"))
            while not op.done and time.time() < deadline:
                time.sleep(8)
                op = client.operations.get(op)
            if not op.done:
                log("veo timed out", model)
                continue
            if op.error or not op.response or not op.response.generated_videos:
                log("veo failed", model, str(op.error)[:300])
                continue
            vid = op.response.generated_videos[0]
            client.files.download(file=vid.video)
            vid.video.save(str(out))
            return {"path": str(out), "model": model, "fallback": False, "duration": float(seconds)}
        except Exception as e:  # noqa: BLE001
            log("veo error", model, repr(e)[:300])
    return None
