"""Blender (Eevee) 3D motion-graphics templates, rendered headless.

render(template, params, out, w, h, fps, duration):
  title_card  {title, subtitle?, kicker?}                       3D bevelled title, lit backdrop, embers, dolly
  lower_third {name, role?}                                     overlay (use .mov for alpha)
  map_route   {places: [{name, lat, lon}], title?}              dark map grid, glowing stops, animated route
  timeline    {events: [{date, label}], title?}                 line with dots revealing dates, camera pan
Renders are cached by a hash of (template, params, size, fps).
"""
import json
import os
import shutil
import tempfile

from .common import RenderError, cached, encode_frames, key, result, run, store

TPL_DIR = os.path.join(os.path.dirname(__file__), "blender_tpl")
TEMPLATES = ("title_card", "lower_third", "map_route", "timeline")
OVERLAY_DEFAULT = {"lower_third"}


def render(template, params=None, out="blender.mp4", w=1920, h=1080, fps=30, duration=None, samples=None):
    if template not in TEMPLATES:
        raise ValueError(f"unknown blender template {template!r}; have {list(TEMPLATES)}")
    p = dict(params or {})
    alpha = out.lower().endswith(".mov")
    p.update({"w": int(w), "h": int(h), "fps": int(fps), "transparent": alpha or template in OVERLAY_DEFAULT and alpha})
    if duration:
        p["duration"] = float(duration)
    if samples:
        p["samples"] = int(samples)
    src = "".join(open(os.path.join(TPL_DIR, f)).read() for f in (template + ".py", "_common.py"))
    k = key("blender", template, p, src)
    if cached(k, out):
        return result(out)
    frames_dir = tempfile.mkdtemp(prefix="cutroom-blender-")
    p["frames_dir"] = frames_dir
    exe = shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
    try:
        run([exe, "-b", "--factory-startup", "-noaudio", "-P", os.path.join(TPL_DIR, template + ".py"), "--", json.dumps(p)], timeout=1500)
        pngs = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
        if not pngs:
            raise RenderError(f"blender rendered no frames for {template}")
        first = pngs[0]
        digits = len(first) - len("f") - len(".png")
        encode_frames(os.path.join(frames_dir, f"f%0{digits}d.png"), out, fps, alpha=alpha)
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)
    store(k, out)
    return result(out)
