import json
import shlex
import subprocess
from pathlib import Path

from .config import log

ASPECTS = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}
FONT = "/System/Library/Fonts/Menlo.ttc"


def dims(aspect: str) -> tuple[int, int]:
    return ASPECTS.get(aspect, ASPECTS["16:9"])


def run(cmd, timeout=1800, check=True) -> subprocess.CompletedProcess:
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    cmd = [str(c) for c in cmd]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        log("command failed:", " ".join(cmd)[:400], "\n", p.stderr[-1500:])
        raise RuntimeError(f"{Path(cmd[0]).name} failed: {p.stderr.strip()[-600:]}")
    return p


def ffmpeg(*args, timeout=1800) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], timeout=timeout)


def duration(path) -> float:
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path], check=False)
    try:
        return float(json.loads(p.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001
        return 0.0


def has_audio(path) -> bool:
    p = run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path], check=False)
    return bool(p.stdout.strip())


def esc_drawtext(s: str) -> str:
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")
