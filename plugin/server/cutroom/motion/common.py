"""Shared helpers for the motion-graphics engines: caching, ffmpeg encoding, previews, probing."""
import hashlib
import json
import os
import shutil
import subprocess

CACHE = os.path.expanduser(os.environ.get("CUTROOM_MOTION_CACHE", "~/workspace/cutroom/projects/.motion-cache"))


class RenderError(RuntimeError):
    pass


def run(cmd, timeout=900, cwd=None, env=None):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd, env=env)
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "").strip().splitlines()[-25:]
        raise RenderError(f"{cmd[0]} failed ({p.returncode}):\n" + "\n".join(tail))
    return p


def key(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def cached(k, out):
    """If a render with this key exists, copy it to `out` and return True."""
    os.makedirs(CACHE, exist_ok=True)
    src = os.path.join(CACHE, k + os.path.splitext(out)[1])
    if os.path.exists(src) and os.path.getsize(src) > 0:
        if os.path.abspath(src) != os.path.abspath(out):
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            shutil.copyfile(src, out)
        return True
    return False


def store(k, out):
    os.makedirs(CACHE, exist_ok=True)
    shutil.copyfile(out, os.path.join(CACHE, k + os.path.splitext(out)[1]))


def is_overlay(out):
    return out.lower().endswith(".mov")


def encode_frames(pattern, out, fps, alpha=None):
    """PNG sequence -> ProRes 4444 with alpha (.mov) or H.264 (.mp4)."""
    alpha = is_overlay(out) if alpha is None else alpha
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if alpha:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", pattern,
               "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", out]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", pattern,
               "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-movflags", "+faststart", out]
    run(cmd)
    return out


def to_target(src, out):
    """Convert whatever an engine produced into the requested container (.mov alpha / .mp4)."""
    if os.path.abspath(src) == os.path.abspath(out):
        return out
    if is_overlay(out):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-c:v", "prores_ks", "-profile:v", "4444",
               "-pix_fmt", "yuva444p10le", "-vendor", "apl0", "-an", out]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", "format=yuv420p", "-c:v", "libx264",
               "-crf", "16", "-preset", "medium", "-movflags", "+faststart", "-an", out]
    run(cmd)
    return out


def preview(path, max_side=640):
    """Small H.264 preview for the web UI; overlays are composited on a checker-free dark backdrop."""
    root, _ = os.path.splitext(path)
    out = root + ".preview.mp4"
    scale = f"scale='if(gt(iw,ih),{max_side},-2)':'if(gt(iw,ih),-2,{max_side})'"
    if is_overlay(path):
        vf = f"[0:v]{scale}[fg];color=c=0x101418:s=16x16[bgc];[bgc][fg]scale2ref[bg][fg2];[bg][fg2]overlay=shortest=1,format=yuv420p"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-filter_complex", vf, "-c:v", "libx264",
               "-crf", "26", "-preset", "veryfast", "-movflags", "+faststart", "-an", out]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vf", scale + ",format=yuv420p", "-c:v", "libx264",
               "-crf", "26", "-preset", "veryfast", "-movflags", "+faststart", "-an", out]
    run(cmd)
    return out


def duration(path):
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path])
    try:
        return round(float(p.stdout.strip()), 3)
    except ValueError:
        return 0.0


def result(path, make_preview=True):
    out = {"path": os.path.abspath(path), "duration": duration(path)}
    if make_preview:
        try:
            out["preview"] = preview(path)
        except RenderError:
            pass
    return out


def frame_png(path, t, out_png):
    """Grab one frame (for self-tests / critic contact sheets)."""
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", path, "-frames:v", "1", out_png])
    return out_png
