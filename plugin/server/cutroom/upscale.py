"""4K upscaling with Real-ESRGAN (realesrgan-ncnn-vulkan, runs on the Apple GPU via MoltenVK).

upscale_4k(in_path, out_path, scale=2, on_progress=None, method="auto", budget_s=900)
  method="ai"    Real-ESRGAN on every frame (≈1.6 s/frame at 1080p→4K on an M4: a 60 s film takes ~48 min)
  method="fast"  ffmpeg lanczos + mild denoise + unsharp (seconds)
  method="auto"  "ai" when the estimate fits budget_s, otherwise "fast"
Output: H.265 (hvc1) with the long edge at 3840, original fps and audio. Falls back to "fast" if the AI pass fails.
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BIN = os.environ.get("CUTROOM_REALESRGAN", os.path.join(ROOT, "tools", "realesrgan", "realesrgan-ncnn-vulkan"))
SEC_PER_FRAME = float(os.environ.get("CUTROOM_UPSCALE_SPF", "1.6"))
LONG_EDGE = 3840


def _probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", path],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    st = d["streams"][0]
    num, den = st["r_frame_rate"].split("/")
    fps = float(num) / float(den or 1)
    dur = float(d["format"].get("duration") or 0)
    n = int(st.get("nb_frames") or 0) or int(dur * fps)
    return int(st["width"]), int(st["height"]), fps, st["r_frame_rate"], dur, n


def _has_audio(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout
    return bool(out.strip())


def _target(w, h):
    if w >= h:
        tw, th = LONG_EDGE, int(round(LONG_EDGE * h / w / 2) * 2)
    else:
        th, tw = LONG_EDGE, int(round(LONG_EDGE * w / h / 2) * 2)
    return tw, th


def _encode_args(path):
    return ["-c:v", "libx265", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-tag:v", "hvc1",
            "-movflags", "+faststart"] + (["-c:a", "aac", "-b:a", "192k"] if _has_audio(path) else [])


def _fast(in_path, out_path, on_progress=None):
    w, h, fps, rate, dur, n = _probe(in_path)
    tw, th = _target(w, h)
    vf = f"hqdn3d=1.2:1.2:4:4,scale={tw}:{th}:flags=lanczos,unsharp=5:5:0.6:5:5:0.0"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", in_path, "-vf", vf] + _encode_args(in_path) + [out_path]
    if on_progress:
        on_progress(5, "upscaling (fast lanczos)")
    subprocess.run(cmd, check=True, capture_output=True)
    if on_progress:
        on_progress(100, "4K ready")
    return out_path


def _ai(in_path, out_path, on_progress=None):
    if not os.path.exists(BIN):
        raise RuntimeError(f"realesrgan binary not found at {BIN}")
    w, h, fps, rate, dur, n = _probe(in_path)
    tw, th = _target(w, h)
    scale = 2 if max(w, h) * 2 >= LONG_EDGE else 4
    model = "realesr-animevideov3"
    d = tempfile.mkdtemp(prefix="cutroom-up-")
    src, dst = os.path.join(d, "in"), os.path.join(d, "out")
    os.makedirs(src)
    os.makedirs(dst)
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", in_path, "-qscale:v", "1", "-qmin", "1",
                        os.path.join(src, "f%06d.jpg")], check=True, capture_output=True)
        total = len(os.listdir(src))
        bindir = os.path.dirname(BIN)
        proc = subprocess.Popen([BIN, "-i", src, "-o", dst, "-n", model, "-s", str(scale), "-f", "jpg",
                                 "-m", os.path.join(bindir, "models")], cwd=bindir,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        while proc.poll() is None:
            time.sleep(2)
            done = len(os.listdir(dst))
            if on_progress and total:
                el = time.time() - t0
                eta = el / max(done, 1) * (total - done)
                on_progress(int(5 + 85 * done / total), f"AI upscaling {done}/{total} frames · ~{int(eta)}s left")
        if proc.returncode != 0 or len(os.listdir(dst)) < total:
            raise RuntimeError(f"realesrgan exited {proc.returncode} with {len(os.listdir(dst))}/{total} frames")
        if on_progress:
            on_progress(92, "encoding 4K")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", rate, "-i", os.path.join(dst, "f%06d.jpg"),
               "-i", in_path, "-map", "0:v", "-map", "1:a?", "-vf", f"scale={tw}:{th}:flags=lanczos"] + _encode_args(in_path) + ["-shortest", out_path]
        subprocess.run(cmd, check=True, capture_output=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if on_progress:
        on_progress(100, "4K ready")
    return out_path


def estimate_seconds(in_path):
    *_, n = _probe(in_path)
    return n * SEC_PER_FRAME


def upscale_4k(in_path, out_path, scale=2, on_progress=None, method="auto", budget_s=900):
    """Upscale to 4K. Returns {"path", "method", "seconds"}."""
    t0 = time.time()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    if method == "auto":
        method = "ai" if estimate_seconds(in_path) <= budget_s else "fast"
    used = method
    if method == "ai":
        try:
            _ai(in_path, out_path, on_progress)
        except Exception as err:  # noqa: BLE001
            print(f"[upscale] AI pass failed, using fast path: {err}")
            used = "fast"
            _fast(in_path, out_path, on_progress)
    else:
        _fast(in_path, out_path, on_progress)
    return {"path": os.path.abspath(out_path), "method": used, "seconds": round(time.time() - t0, 1)}


def upscale_4k_async(in_path, out_path, on_done, on_progress=None, method="ai"):
    """Run in a background thread (for the publish flow: 1080p ships first, 4K arrives later)."""
    def go():
        try:
            on_done(upscale_4k(in_path, out_path, on_progress=on_progress, method=method), None)
        except Exception as err:  # noqa: BLE001
            on_done(None, err)
    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t
