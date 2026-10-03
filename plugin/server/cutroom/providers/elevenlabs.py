"""ElevenLabs: music generation (background score) and Scribe word-level transcription.
Fallback for music: a quiet ffmpeg-synthesised ambient pad."""
from pathlib import Path

import requests

from .. import config
from ..config import log
from ..util import duration, ffmpeg

API = "https://api.elevenlabs.io/v1"


def music(prompt: str, length_s: float, out: Path) -> dict:
    """-> {path (wav), duration, engine}"""
    out = Path(out)
    key = config.get("ELEVENLABS_API_KEY")
    if key:
        try:
            ms = int(min(600000, max(3000, length_s * 1000)))
            r = requests.post(f"{API}/music", headers={"xi-api-key": key},
                              json={"prompt": prompt, "music_length_ms": ms, "force_instrumental": True}, timeout=600)
            if r.status_code < 400 and r.content:
                mp3 = out.with_suffix(".mp3")
                mp3.write_bytes(r.content)
                ffmpeg("-i", mp3, "-ar", "48000", "-ac", "2", out)
                return {"path": str(out), "duration": duration(out), "engine": "elevenlabs-music"}
            log("elevenlabs music", r.status_code, r.text[:300])
        except Exception as e:  # noqa: BLE001
            log("elevenlabs music error", repr(e)[:300])
    return ambient_pad(length_s, out)


def ambient_pad(length_s: float, out: Path) -> dict:
    """Slow A-minor pad with gentle movement: soft enough to sit under a voice."""
    t = f"{length_s:.2f}"
    expr = ("0.08*sin(2*PI*110*t)*(0.6+0.4*sin(2*PI*0.07*t))"
            "+0.05*sin(2*PI*164.81*t)*(0.6+0.4*sin(2*PI*0.05*t+1))"
            "+0.05*sin(2*PI*130.81*t)*(0.6+0.4*sin(2*PI*0.09*t+2))"
            "+0.03*sin(2*PI*220*t)*(0.5+0.5*sin(2*PI*0.03*t))")
    ffmpeg("-f", "lavfi", "-i", f"aevalsrc='{expr}|{expr}':s=48000:d={t}",
           "-f", "lavfi", "-i", f"anoisesrc=color=brown:amplitude=0.02:d={t}:r=48000",
           "-filter_complex", "[1:a]lowpass=f=400,aformat=channel_layouts=stereo[n];[0:a][n]amix=inputs=2:normalize=0,"
                              "lowpass=f=2500,aecho=0.8:0.7:120|240:0.3|0.2,"
                              f"afade=t=in:d=3,afade=t=out:st={max(0, length_s - 4):.2f}:d=4",
           "-ar", "48000", "-ac", "2", out)
    return {"path": str(out), "duration": duration(out), "engine": "synth-pad"}


def scribe(audio_path: Path) -> list[dict] | None:
    key = config.get("ELEVENLABS_API_KEY")
    if not key:
        return None
    try:
        with open(audio_path, "rb") as fh:
            r = requests.post(f"{API}/speech-to-text", headers={"xi-api-key": key},
                              data={"model_id": "scribe_v2", "timestamps_granularity": "word"},
                              files={"file": (Path(audio_path).name, fh)}, timeout=600)
        r.raise_for_status()
        return [{"word": w["text"].strip(), "start": w["start"], "end": w["end"]}
                for w in r.json().get("words", []) if w.get("type", "word") == "word" and w["text"].strip()]
    except Exception as e:  # noqa: BLE001
        log("scribe error", repr(e)[:300])
        return None
