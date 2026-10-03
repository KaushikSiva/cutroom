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
    if (config.get("CUTROOM_TTS_ENGINE") or "").lower() == "elevenlabs":
        r = _elevenlabs(text, out)
        if r:
            return r
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


def _elevenlabs(text: str, out: Path) -> dict | None:
    """ElevenLabs narrator (CUTROOM_ELEVEN_VOICE, default Eric - Smooth, Trustworthy). Gemini's inline pause tags
    become ellipses; other vocal tags are dropped, since this model reads text literally."""
    import requests
    key = config.get("ELEVENLABS_API_KEY")
    if not key:
        return None
    clean = re.sub(r"<long pause>", "... ", text)
    clean = re.sub(r"<short pause>", ", ", clean)
    clean = re.sub(r"<[^>]+>", "", clean).strip()
    voice_id = config.get("CUTROOM_ELEVEN_VOICE") or "cjVigY5qzO86Huf0OWal"
    try:
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
                          headers={"xi-api-key": key, "Content-Type": "application/json"}, timeout=120,
                          json={"text": clean, "model_id": config.get("CUTROOM_ELEVEN_MODEL") or "eleven_multilingual_v2",
                                "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True}})
        if r.status_code >= 400:
            log("elevenlabs tts", r.status_code, r.text[:300])
            return None
        mp3 = out.with_suffix(".el.mp3")
        mp3.write_bytes(r.content)
        ffmpeg("-i", mp3, "-ar", "24000", "-ac", "1", out)
        mp3.unlink(missing_ok=True)
        return {"path": str(out), "duration": duration(out), "engine": f"elevenlabs:{voice_id}"}
    except Exception as e:  # noqa: BLE001
        log("elevenlabs tts failed:", repr(e)[:300])
        return None


def say(text: str, out: Path, voice: str = SAY_VOICE) -> dict:
    clean = re.sub(r"<[^>]+>", " ", text)
    aiff = Path(out).with_suffix(".aiff")
    run(["say", "-v", voice, "-r", "165", "-o", aiff, clean])
    ffmpeg("-i", aiff, "-ar", "24000", "-ac", "1", out)
    aiff.unlink(missing_ok=True)
    return {"path": str(out), "duration": duration(out), "engine": f"say:{voice}"}
