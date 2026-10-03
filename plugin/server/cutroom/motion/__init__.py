"""Cutroom motion graphics: one entry point over four engines.

render(engine, out, w, h, fps=30, duration=None, template=None, params=None, source=None, scene_name=None)
  engine="hyperframes"   template in title_card | lower_third | data_callout | kinetic_quote, or source=HTML
  engine="manim"         template in bar_chart | line_chart | process, or source=python code + scene_name
  engine="motion_canvas" template in network | flow, or source=TSX scene
  engine="blender"       template in title_card | lower_third | map_route | timeline
out ending in .mov → ProRes 4444 with alpha (overlay); .mp4 → H.264. Returns {"path", "preview", "duration"}.
"""
from . import blender, hyperframes, manim_r, motion_canvas

TEMPLATES = {
    "hyperframes": hyperframes.TEMPLATES,
    "manim": sorted(manim_r.TEMPLATES),
    "motion_canvas": sorted(motion_canvas.TEMPLATES),
    "blender": list(blender.TEMPLATES),
}


def render(engine, out, w=1920, h=1080, fps=30, duration=None, template=None, params=None, source=None, scene_name=None):
    if engine == "hyperframes":
        return hyperframes.render(source=source, template=template, params=params, out=out, w=w, h=h, fps=fps, duration=duration)
    if engine == "manim":
        if source:
            return manim_r.render(source, scene_name or "Main", out, w, h, fps, duration)
        return manim_r.render_template(template, params, out, w, h, fps, duration)
    if engine == "motion_canvas":
        if source:
            return motion_canvas.render(source, out, w, h, fps, duration)
        return motion_canvas.render_template(template, params, out, w, h, fps, duration)
    if engine == "blender":
        return blender.render(template, params, out, w, h, fps, duration)
    raise ValueError(f"unknown engine {engine!r}; have {sorted(TEMPLATES)}")
