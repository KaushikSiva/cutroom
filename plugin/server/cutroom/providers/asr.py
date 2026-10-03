"""Word-level transcription: mlx-whisper on Apple Silicon, ElevenLabs Scribe as fallback."""
from pathlib import Path

from .. import config
from ..config import log
from ..util import ffmpeg
from . import elevenlabs


def words(media_path: str | Path) -> dict:
    """-> {words: [{word,start,end}], text, engine}"""
    media_path = Path(media_path)
    wav = media_path.with_suffix(".asr.wav")
    ffmpeg("-i", media_path, "-vn", "-ar", "16000", "-ac", "1", wav)
    try:
        import mlx_whisper
        r = mlx_whisper.transcribe(str(wav), path_or_hf_repo=config.get("CUTROOM_ASR_MODEL"), word_timestamps=True, language="en", verbose=None)
        ws = [{"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])}
              for seg in r.get("segments", []) for w in seg.get("words", []) if w["word"].strip()]
        if ws:
            return {"words": ws, "text": r.get("text", "").strip(), "engine": "mlx-whisper"}
    except Exception as e:  # noqa: BLE001
        log("mlx-whisper failed:", repr(e)[:300])
    ws = elevenlabs.scribe(wav) or []
    return {"words": ws, "text": " ".join(w["word"] for w in ws), "engine": "elevenlabs-scribe" if ws else "none"}
