"""Voiceover with Gemini 3.8 TTS. `direction` goes into speech_metadata.style (sustained delivery); inline tags like
<short pause> or <sigh> may appear in the text itself. Fallback: macOS `say`."""
import base64
import re
from pathlib import Path

from .. import config
from ..config import log
from ..util import duration, ffmpeg, run

SAY_VOICE = "Daniel"


def tts(text: str, out: Path, direction: str = "", voice: str | None = None) -> dict:
    """-> {path, duration, engine}. Output is 24 kHz mono wav."""
    out = Path(out)
    key = config.get("GEMINI_API_KEY")
    if key:
        try:
            from google import genai
            client = genai.Client(api_key=key)
            content = {"type": "text", "text": text}
            if direction:
                content["annotations"] = [{"type": "speech_metadata", "style": direction}]
            it = client.interactions.create(
                model=config.get("CUTROOM_TTS_MODEL"),
                input=[{"type": "user_input", "content": [content]}],
                response_format={"type": "audio"},
                generation_config={"speech_config": [{"voice": voice or config.get("CUTROOM_TTS_VOICE")}]},
            )
            raw = out.with_suffix(".gemini.wav")
            raw.write_bytes(base64.b64decode(it.output_audio.data))
            ffmpeg("-i", raw, "-ar", "24000", "-ac", "1", out)
            raw.unlink(missing_ok=True)
            return {"path": str(out), "duration": duration(out), "engine": config.get("CUTROOM_TTS_MODEL")}
        except Exception as e:  # noqa: BLE001
            log("gemini tts failed, falling back to say:", repr(e)[:400])
    return say(text, out)


def say(text: str, out: Path, voice: str = SAY_VOICE) -> dict:
    clean = re.sub(r"<[^>]+>", " ", text)
    aiff = Path(out).with_suffix(".aiff")
    run(["say", "-v", voice, "-r", "165", "-o", aiff, clean])
    ffmpeg("-i", aiff, "-ar", "24000", "-ac", "1", out)
    aiff.unlink(missing_ok=True)
    return {"path": str(out), "duration": duration(out), "engine": f"say:{voice}"}
