"""Motion Canvas renderer (TypeScript, code-driven animation), headless.

The template project in mc_template/ registers a capture exporter; we copy it to a temp dir, write the scene to
src/scenes/main.tsx, start Vite, open render.html in Playwright and receive every frame as a PNG data URL.
render(scene_tsx, ...) runs your own scene (default export of makeScene2D). render_template(name, params, ...) uses a
built-in scene: network (hub-and-spoke concept map), flow (left-to-right pipeline).
Falls back to the Hyperframes renderer if Motion Canvas cannot render, so callers never break.
"""
import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time

from .common import RenderError, cached, encode_frames, key, result, store

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "mc_template")
FONT = "Avenir Next"

NETWORK = r'''
import {makeScene2D, Circle, Line, Txt, Rect} from '@motion-canvas/2d';
import {all, createRef, sequence, waitFor, easeOutCubic, easeInOutCubic, Vector2} from '@motion-canvas/core';
const P = __PARAMS__;
export default makeScene2D(function* (view) {
  const W = view.width(), H = view.height(), u = Math.min(W, H) / 1080;
  const portrait = H > W;
  const title = createRef<Txt>();
  view.add(<Txt ref={title} text={P.title || ''} fontFamily={'__FONT__'} fontWeight={700} fontSize={56 * u} fill={'#f3efe6'} y={-H / 2 + 110 * u} opacity={0} />);
  const nodes: string[] = P.nodes || [];
  const R = (portrait ? W * 0.34 : H * 0.30);
  const hub = createRef<Circle>();
  const hubLabel = createRef<Txt>();
  view.add(<Circle ref={hub} size={0} fill={'#e8b04a'} shadowColor={'#e8b04a'} shadowBlur={60 * u} y={20 * u} />);
  view.add(<Txt ref={hubLabel} text={P.center || ''} fontFamily={'__FONT__'} fontWeight={700} fontSize={34 * u} fill={'#0b0d10'} y={20 * u} opacity={0} />);
  const lines: Line[] = [], dots: Circle[] = [], labels: Txt[] = [];
  nodes.forEach((n, i) => {
    const a = -Math.PI / 2 + (i / nodes.length) * Math.PI * 2;
    const p = new Vector2(Math.cos(a) * R * (portrait ? 1 : 1.55), Math.sin(a) * R + 20 * u);
    const line = <Line points={[new Vector2(0, 20 * u), p]} stroke={'#5fb3a1'} lineWidth={4 * u} end={0} opacity={0.8} /> as Line;
    const dot = <Circle position={p} size={0} fill={'#141922'} stroke={'#5fb3a1'} lineWidth={4 * u} /> as Circle;
    const label = <Txt text={n} fontFamily={'__FONT__'} fontSize={30 * u} fill={'#f3efe6'} position={p.add(new Vector2(Math.cos(a), Math.sin(a)).scale(78 * u)).add(new Vector2(Math.abs(Math.cos(a)) > 0.3 ? Math.sign(Math.cos(a)) * 60 * u : 0, 0))} opacity={0} /> as Txt;
    view.add(line); view.add(dot); view.add(label);
    lines.push(line); dots.push(dot); labels.push(label);
  });
  hub().moveToTop(); hubLabel().moveToTop();
  yield* title().opacity(1, 0.6);
  yield* all(hub().size(210 * u, 0.8, easeOutCubic), hubLabel().opacity(1, 0.8));
  yield* sequence(0.18, ...nodes.map((_, i) => all(
    lines[i].end(1, 0.6, easeInOutCubic),
    dots[i].size(64 * u, 0.6, easeOutCubic),
    labels[i].opacity(1, 0.6),
  )));
  yield* sequence(0.08, ...dots.map(d => d.fill('#5fb3a1', 0.3)));
  yield* waitFor(P.hold ?? 1.5);
});
'''

FLOW = r'''
import {makeScene2D, Rect, Txt, Line} from '@motion-canvas/2d';
import {all, sequence, waitFor, easeOutCubic, Vector2} from '@motion-canvas/core';
const P = __PARAMS__;
export default makeScene2D(function* (view) {
  const W = view.width(), H = view.height(), u = Math.min(W, H) / 1080;
  const portrait = H > W;
  const steps: string[] = P.steps || [];
  const n = Math.max(1, steps.length);
  const title = <Txt text={P.title || ''} fontFamily={'__FONT__'} fontWeight={700} fontSize={54 * u} fill={'#f3efe6'} y={-H / 2 + 110 * u} opacity={0} /> as Txt;
  view.add(title);
  const span = portrait ? H * 0.62 : W * 0.80;
  const boxes: Rect[] = [], arrows: Line[] = [];
  steps.forEach((s, i) => {
    const t = -span / 2 + (span / n) * (i + 0.5);
    const pos = portrait ? new Vector2(0, t + 60 * u) : new Vector2(t, 40 * u);
    const box = <Rect position={pos} width={portrait ? W * 0.7 : (span / n) * 0.78} height={portrait ? (span / n) * 0.62 : 190 * u}
      radius={22 * u} fill={'#141922'} stroke={i === n - 1 ? '#e8b04a' : '#5fb3a1'} lineWidth={4 * u} scale={0.6} opacity={0}>
      <Txt text={s} fontFamily={'__FONT__'} fontSize={32 * u} fill={'#f3efe6'} textWrap textAlign={'center'} width={'86%'} />
    </Rect> as Rect;
    view.add(box); boxes.push(box);
  });
  for (let i = 0; i < n - 1; i++) {
    const a = boxes[i].position(), b = boxes[i + 1].position();
    const off = portrait ? new Vector2(0, (span / n) * 0.33) : new Vector2((span / n) * 0.41, 0);
    const ar = <Line points={[a.add(off), b.sub(off)]} stroke={'#9aa3ad'} lineWidth={5 * u} endArrow arrowSize={16 * u} end={0} /> as Line;
    view.add(ar); arrows.push(ar);
  }
  yield* title.opacity(1, 0.6);
  for (let i = 0; i < n; i++) {
    yield* all(boxes[i].opacity(1, 0.45), boxes[i].scale(1, 0.45, easeOutCubic));
    if (i < n - 1) yield* arrows[i].end(1, 0.35);
  }
  yield* boxes[n - 1].fill('#2a2312', 0.5);
  yield* waitFor(P.hold ?? 1.5);
});
'''

TEMPLATES = {"network": NETWORK, "flow": FLOW}


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _ensure_deps():
    if not os.path.isdir(os.path.join(TEMPLATE_DIR, "node_modules", "@motion-canvas")):
        subprocess.run(["npm", "i", "--no-audit", "--no-fund"], cwd=TEMPLATE_DIR, check=True, capture_output=True, timeout=600)


def _render_mc(scene_tsx, out, w, h, fps):
    _ensure_deps()
    d = tempfile.mkdtemp(prefix="cutroom-mc-")
    for name in ("package.json", "vite.config.ts", "tsconfig.json", "render.html"):
        shutil.copy(os.path.join(TEMPLATE_DIR, name), d)
    shutil.copytree(os.path.join(TEMPLATE_DIR, "src"), os.path.join(d, "src"))
    os.symlink(os.path.join(TEMPLATE_DIR, "node_modules"), os.path.join(d, "node_modules"))
    with open(os.path.join(d, "src", "scenes", "main.tsx"), "w") as fh:
        fh.write(scene_tsx)
    port = _free_port()
    vite = subprocess.Popen(["npx", "vite", "--host", "127.0.0.1", "--port", str(port), "--strictPort"], cwd=d, env=dict(os.environ, MC_PORT=str(port)),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    frames, logs = {}, []
    try:
        from playwright.sync_api import sync_playwright
        deadline = time.time() + 60
        url = f"http://127.0.0.1:{port}/render.html"
        while time.time() < deadline:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                time.sleep(0.3)
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.on("console", lambda m: logs.append(m.text))
            pg.expose_function("__cutroomFrame", lambda f, u: frames.__setitem__(int(f), u))
            pg.goto(url)
            pg.wait_for_function("window.__cutroomReady === true", timeout=90000)
            res = pg.evaluate(f"window.__cutroomRender({{w:{w},h:{h},fps:{fps},transparent:{'true' if out.lower().endswith('.mov') else 'false'}}})")
            b.close()
        if res != 0 or not frames:
            raise RenderError("motion canvas render failed: " + " | ".join(l for l in logs if "[mc]" in l)[-800:])
        fd = os.path.join(d, "frames")
        os.makedirs(fd)
        for i, f in enumerate(sorted(frames)):
            with open(os.path.join(fd, f"f{i:05d}.png"), "wb") as fh:
                fh.write(base64.b64decode(frames[f].split(",", 1)[1]))
        encode_frames(os.path.join(fd, "f%05d.png"), out, fps)
    finally:
        vite.terminate()
        try:
            vite.wait(5)
        except subprocess.TimeoutExpired:
            vite.kill()
        shutil.rmtree(d, ignore_errors=True)
    return out


def render(scene_tsx, out="mc.mp4", w=1920, h=1080, fps=30, duration=None, fallback_template=None, fallback_params=None):
    """Render a Motion Canvas scene (TSX source with `export default makeScene2D(...)`)."""
    k = key("motion_canvas", scene_tsx, w, h, fps, os.path.splitext(out)[1])
    if cached(k, out):
        return result(out)
    try:
        _render_mc(scene_tsx, out, w, h, fps)
    except Exception as err:  # noqa: BLE001 — never break the pipeline; fall back to HTML motion graphics
        print(f"[motion_canvas] failed, falling back to hyperframes: {str(err)[:400]}")
        from . import hyperframes
        return hyperframes.render(template=fallback_template or "title_card",
                                  params=fallback_params or {"title": "", "subtitle": ""}, out=out, w=w, h=h, fps=fps, duration=duration)
    store(k, out)
    return result(out)


def render_template(template, params, out="mc.mp4", w=1920, h=1080, fps=30, duration=None):
    if template not in TEMPLATES:
        raise ValueError(f"unknown motion canvas template {template!r}; have {sorted(TEMPLATES)}")
    src = TEMPLATES[template].replace("__PARAMS__", json.dumps(params or {})).replace("__FONT__", FONT)
    fb = {"title": (params or {}).get("title", ""), "subtitle": " → ".join((params or {}).get("steps") or (params or {}).get("nodes") or [])}
    return render(src, out, w, h, fps, duration, fallback_template="title_card", fallback_params=fb)
