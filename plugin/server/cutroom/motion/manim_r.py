"""Manim (Community) renderer: diagrams, charts and animated explanations.

render(scene_code, scene_name, out, w, h, fps) runs arbitrary Manim code (use Text, not Tex — no LaTeX installed).
render_template(template, params, out, w, h, fps) uses a built-in scene: bar_chart, line_chart, process.
Layouts read config.frame_width / frame_height so 16:9, 9:16 and 1:1 all work.
"""
import glob
import json
import os
import shutil
import sys
import tempfile

from .common import RenderError, cached, key, result, run, store, to_target

FONT = os.environ.get("CUTROOM_MANIM_FONT", "Avenir Next")

PRELUDE = f'''
from manim import *
import json
BG = "#0b0d10"; PAPER = "#f3efe6"; ACCENT = "#e8b04a"; ACCENT2 = "#5fb3a1"; MUTED = "#9aa3ad"
FONT = {FONT!r}
config.background_color = BG
def T(s, size=36, color=PAPER, weight=NORMAL):
    return Text(str(s), font=FONT, font_size=size, color=color, weight=weight)
'''

BAR_CHART = '''
class BarChartScene(Scene):
    def construct(self):
        P = json.loads(PARAMS)
        data = P.get("data", [])
        fw, fh = config.frame_width, config.frame_height
        portrait = fh > fw
        title = T(P.get("title", ""), size=44 if not portrait else 40, weight=BOLD).to_edge(UP, buff=0.7)
        unit = P.get("unit", "")
        mx = max([float(d["value"]) for d in data] + [1e-9])
        n = max(1, len(data))
        if portrait:  # horizontal bars stack better in a tall frame
            avail_w, row_h = fw * 0.55, min(0.9, (fh - 3.0) / n)
            rows = VGroup()
            for i, d in enumerate(data):
                lab = T(d["label"], size=26, color=MUTED)
                bar = Rectangle(width=max(0.02, avail_w * float(d["value"]) / mx), height=row_h * 0.55, stroke_width=0,
                                fill_color=ACCENT if i == int(P.get("highlight", -1)) else ACCENT2, fill_opacity=1)
                val = T(f"{d['value']}{unit}", size=24)
                row = VGroup(lab, bar, val)
                lab.next_to(bar, UP, buff=0.12, aligned_edge=LEFT)
                val.next_to(bar, RIGHT, buff=0.2)
                rows.add(row)
            rows.arrange(DOWN, buff=0.35, aligned_edge=LEFT).next_to(title, DOWN, buff=0.8)
            rows.set_x(-fw * 0.05)
            self.play(FadeIn(title, shift=DOWN * 0.2), run_time=0.8)
            for r in rows:
                lab, bar, val = r
                self.play(FadeIn(lab, shift=RIGHT * 0.2), GrowFromEdge(bar, LEFT), FadeIn(val), run_time=0.45)
        else:
            base_y = -fh / 2 + 1.3
            avail_h = fh - 3.6
            gap = fw * 0.75 / n
            axis = Line([-fw * 0.4, base_y, 0], [fw * 0.4, base_y, 0], color=MUTED, stroke_width=2)
            bars, labels, vals = VGroup(), VGroup(), VGroup()
            for i, d in enumerate(data):
                x = -fw * 0.375 + gap * (i + 0.5)
                hgt = max(0.02, avail_h * float(d["value"]) / mx)
                bar = Rectangle(width=gap * 0.55, height=hgt, stroke_width=0,
                                fill_color=ACCENT if i == int(P.get("highlight", -1)) else ACCENT2, fill_opacity=1)
                bar.move_to([x, base_y + hgt / 2, 0])
                bars.add(bar)
                labels.add(T(d["label"], size=24, color=MUTED).next_to([x, base_y, 0], DOWN, buff=0.25))
                vals.add(T(f"{d['value']}{unit}", size=26).next_to(bar, UP, buff=0.15))
            self.play(FadeIn(title, shift=DOWN * 0.2), Create(axis), run_time=0.9)
            self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in bars], lag_ratio=0.15), FadeIn(labels), run_time=1.6)
            self.play(LaggedStart(*[FadeIn(v, shift=UP * 0.15) for v in vals], lag_ratio=0.1), run_time=0.8)
        note = P.get("note")
        if note:
            self.play(FadeIn(T(note, size=26, color=ACCENT).to_edge(DOWN, buff=0.35)), run_time=0.6)
        self.wait(float(P.get("hold", 1.5)))
'''

LINE_CHART = '''
class LineChartScene(Scene):
    def construct(self):
        P = json.loads(PARAMS)
        xs = [float(x) for x in P.get("x", [])]
        series = P.get("series", [])
        fw, fh = config.frame_width, config.frame_height
        title = T(P.get("title", ""), size=42, weight=BOLD).to_edge(UP, buff=0.6)
        ys = [float(v) for s in series for v in s["y"]] or [0, 1]
        ymin, ymax = min(0, min(ys)), max(ys) * 1.1
        ax = Axes(x_range=[min(xs), max(xs), max(1, (max(xs) - min(xs)) / 5)], y_range=[ymin, ymax, (ymax - ymin) / 4],
                  x_length=fw * 0.78, y_length=fh * 0.55,
                  axis_config={"color": MUTED, "stroke_width": 2, "include_tip": False, "font_size": 22},
                  x_axis_config={"numbers_to_include": xs[:: max(1, len(xs) // 6)], "decimal_number_config": {"num_decimal_places": 0, "group_with_commas": False}},
                  y_axis_config={"numbers_to_include": []}).next_to(title, DOWN, buff=0.6)
        self.play(FadeIn(title, shift=DOWN * 0.2), Create(ax), run_time=1.0)
        colors = [ACCENT, ACCENT2, "#c77dff", "#ff7b72"]
        for i, s in enumerate(series):
            pts = [ax.c2p(x, float(y)) for x, y in zip(xs, s["y"])]
            line = VMobject(color=colors[i % 4], stroke_width=6).set_points_smoothly(pts)
            dot = Dot(pts[-1], color=colors[i % 4], radius=0.09)
            lab = T(s.get("name", ""), size=26, color=colors[i % 4]).next_to(dot, UR, buff=0.12)
            self.play(Create(line), run_time=1.8, rate_func=smooth)
            self.play(FadeIn(dot, scale=0.5), FadeIn(lab), run_time=0.4)
        self.wait(float(P.get("hold", 1.5)))
'''

PROCESS = '''
class ProcessScene(Scene):
    def construct(self):
        P = json.loads(PARAMS)
        steps = P.get("steps", [])
        fw, fh = config.frame_width, config.frame_height
        portrait = fh > fw
        title = T(P.get("title", ""), size=42, weight=BOLD).to_edge(UP, buff=0.6)
        nodes = VGroup()
        for i, s in enumerate(steps):
            label = T(s, size=26 if len(steps) > 4 else 30)
            box = RoundedRectangle(corner_radius=0.18, width=max(label.width + 0.6, 2.2), height=label.height + 0.6,
                                   stroke_color=ACCENT if i == 0 else ACCENT2, stroke_width=3, fill_color="#141922", fill_opacity=1)
            num = T(str(i + 1), size=20, color=BG, weight=BOLD)
            badge = Circle(radius=0.2, fill_color=ACCENT, fill_opacity=1, stroke_width=0)
            g = VGroup(box, label)
            badge.move_to(box.get_corner(UL)); num.move_to(badge)
            nodes.add(VGroup(g, badge, num))
        if portrait:
            nodes.arrange(DOWN, buff=0.55)
        else:
            nodes.arrange(RIGHT, buff=0.7)
            if nodes.width > fw * 0.92:
                nodes.scale_to_fit_width(fw * 0.92)
        nodes.next_to(title, DOWN, buff=0.9 if portrait else 1.2)
        arrows = VGroup(*[Arrow(nodes[i].get_bottom() if portrait else nodes[i].get_right(),
                                nodes[i + 1].get_top() if portrait else nodes[i + 1].get_left(),
                                buff=0.12, color=MUTED, stroke_width=4, max_tip_length_to_length_ratio=0.25)
                          for i in range(len(nodes) - 1)])
        self.play(FadeIn(title, shift=DOWN * 0.2), run_time=0.8)
        for i, n in enumerate(nodes):
            self.play(FadeIn(n, shift=UP * 0.2, scale=0.95), run_time=0.5)
            if i < len(arrows):
                self.play(GrowArrow(arrows[i]), run_time=0.35)
        self.play(Indicate(nodes[-1], color=ACCENT, scale_factor=1.06), run_time=0.8)
        self.wait(float(P.get("hold", 1.5)))
'''

TEMPLATES = {"bar_chart": ("BarChartScene", BAR_CHART), "line_chart": ("LineChartScene", LINE_CHART),
             "process": ("ProcessScene", PROCESS)}


def render(scene_code, scene_name, out="manim.mp4", w=1920, h=1080, fps=30, duration=None, quality="h"):
    """Render Manim code. `scene_code` may omit imports; the house prelude (colors, T() text helper) is prepended."""
    code = scene_code if "from manim import" in scene_code else PRELUDE + "\n" + scene_code
    alpha = out.lower().endswith(".mov")
    k = key("manim", code, scene_name, w, h, fps, alpha)
    if cached(k, out):
        return result(out)
    d = tempfile.mkdtemp(prefix="cutroom-manim-")
    src = os.path.join(d, "scene.py")
    with open(src, "w") as fh:
        fh.write(code)
    cmd = [sys.executable, "-m", "manim", "render", "-q", quality, "-r", f"{w},{h}", "--fps", str(fps),
           "--media_dir", os.path.join(d, "media"), "--disable_caching", "--progress_bar", "none"]
    cmd += ["--format", "mov", "-t"] if alpha else ["--format", "mp4"]
    cmd += [src, scene_name]
    run(cmd, timeout=900)
    found = [f for f in glob.glob(os.path.join(d, "media", "videos", "**", f"{scene_name}.*"), recursive=True)
             if f.endswith((".mp4", ".mov"))]
    if not found:
        raise RenderError(f"manim produced no video for {scene_name}")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    to_target(found[0], out)
    shutil.rmtree(d, ignore_errors=True)
    store(k, out)
    return result(out)


def render_template(template, params, out="manim.mp4", w=1920, h=1080, fps=30, duration=None):
    if template not in TEMPLATES:
        raise ValueError(f"unknown manim template {template!r}; have {sorted(TEMPLATES)}")
    name, body = TEMPLATES[template]
    code = PRELUDE + f"\nPARAMS = {json.dumps(json.dumps(params or {}))}\n" + body
    return render(code, name, out, w, h, fps, duration)
