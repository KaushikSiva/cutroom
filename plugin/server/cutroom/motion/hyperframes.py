"""HTML-grounded motion graphics, rendered with HeyGen's Hyperframes CLI (npm `hyperframes`).

A composition is an HTML page whose animation is a paused GSAP timeline registered on window.__timelines["main"].
Use a built-in template (title_card, lower_third, data_callout, kinetic_quote) or pass your own HTML.
If the Hyperframes CLI fails, a Playwright renderer seeks the same timeline frame by frame, so callers never break.
"""
import json
import os
import shutil
import subprocess
import tempfile

from . import hf_templates
from .common import RenderError, cached, encode_frames, key, result, run, store

HF_VERSION = os.environ.get("CUTROOM_HYPERFRAMES_VERSION", "0.8.115")


def _cli():
    exe = shutil.which("hyperframes")
    return [exe] if exe else ["npx", "--yes", f"hyperframes@{HF_VERSION}"]


def _project(html, w, h):
    d = tempfile.mkdtemp(prefix="cutroom-hf-")
    with open(os.path.join(d, "index.html"), "w") as fh:
        fh.write(html)
    with open(os.path.join(d, "hyperframes.json"), "w") as fh:
        json.dump({"paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
                   "media": {"autoProxy": True}}, fh)
    with open(os.path.join(d, "meta.json"), "w") as fh:
        json.dump({"id": "cutroom", "name": "cutroom"}, fh)
    return d


def _render_cli(d, out, fps, duration=None):
    fmt = "mov" if out.lower().endswith(".mov") else "mp4"
    tmp_out = os.path.join(d, "render." + fmt)
    env = dict(os.environ, HYPERFRAMES_SKIP_SKILLS="1", HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1")
    cmd = _cli() + ["render", "-o", tmp_out, "--fps", str(fps), "--format", fmt, "--quiet"]
    if fmt == "mp4":
        cmd += ["--quality", "high"]
    # a composition that never signals ready would hang the CLI; fall back to the Playwright renderer instead
    run(cmd, timeout=90 + 12 * float(duration or 8), cwd=d, env=env)
    if not os.path.exists(tmp_out):
        raise RenderError("hyperframes produced no output")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    shutil.move(tmp_out, out)
    return out


def _render_playwright(html, out, w, h, fps, duration, transparent):
    """Deterministic fallback: seek the GSAP timeline per frame and screenshot."""
    from playwright.sync_api import sync_playwright
    d = tempfile.mkdtemp(prefix="cutroom-pw-")
    page_path = os.path.join(d, "index.html")
    with open(page_path, "w") as fh:
        fh.write(html)
    n = max(1, int(round(duration * fps)))
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg.goto("file://" + page_path, wait_until="networkidle")
        pg.evaluate("document.fonts ? document.fonts.ready : null")
        pg.wait_for_function("window.__timelines && window.__timelines.main", timeout=20000)
        for i in range(n):
            pg.evaluate(f"window.__timelines.main.seek({i / fps:.5f}, false)")
            pg.screenshot(path=os.path.join(d, f"f{i:05d}.png"), omit_background=transparent)
        b.close()
    encode_frames(os.path.join(d, "f%05d.png"), out, fps, alpha=out.lower().endswith(".mov"))
    shutil.rmtree(d, ignore_errors=True)
    return out


def render(source=None, template=None, params=None, out="graphic.mp4", w=1920, h=1080, fps=30, duration=None,
           engine_fallback=True):
    """Render HTML motion graphics.

    source:   full Hyperframes HTML, or a fragment (markup + <script> that adds tweens to `tl`), or a path to an .html file
    template: one of title_card | lower_third | data_callout | kinetic_quote (params per template)
    out:      .mov → ProRes 4444 with alpha (overlay), .mp4 → H.264
    """
    if template:
        html, dur, _ = hf_templates.build(template, params, w, h, duration)
    elif source:
        if os.path.exists(str(source)) and str(source).endswith(".html"):
            with open(source) as fh:
                source = fh.read()
        dur = float(duration or 5)
        html = hf_templates.wrap_custom(source, w, h, dur)
    else:
        raise ValueError("hyperframes.render needs a template or source")
    if out.lower().endswith(".mov") and "background:transparent" not in html.replace(" ", ""):
        html = html.replace("html,body{", "html,body{background:transparent!important;", 1)
    k = key("hyperframes", html, w, h, fps, os.path.splitext(out)[1])
    if cached(k, out):
        return result(out)
    d = _project(html, w, h)
    try:
        _render_cli(d, out, fps, dur)
    except (RenderError, subprocess.TimeoutExpired, OSError) as err:
        if not engine_fallback:
            raise
        print(f"[hyperframes] CLI failed, using Playwright renderer: {str(err)[:300]}")
        _render_playwright(html, out, w, h, fps, dur, out.lower().endswith(".mov"))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    store(k, out)
    return result(out)


TEMPLATES = sorted(hf_templates.TEMPLATES)
