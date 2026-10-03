---
name: motion-graphics
description: Make Cutroom motion graphics — titles, lower thirds, charts, maps, timelines, diagrams and kinetic text — choosing between Hyperframes (HTML), Manim, Motion Canvas and Blender. Use for every `graphic` shot and for overlays.
---

# Motion graphics

Call `motion_graphic(project_id, shot_id, engine, source | template, params)`. Every engine renders at the project's
aspect ratio and returns a video path. Overlays (lower thirds, callouts) render with transparency and are composited
over the shot below them at assembly.

## Choosing an engine

| Need | Engine | Why |
|---|---|---|
| Title cards, kinetic quotes, stat callouts, anything typographic or "web-like" | `hyperframes` | HTML/CSS/JS rendered frame by frame; best typography, fastest to iterate |
| Data: bar/line charts, comparisons, process diagrams, equations | `manim` | Precise, mathematical animation |
| Custom scenes with code-driven motion: diagrams that build, UI walk-throughs | `motion_canvas` | TypeScript scenes with tweened layouts |
| 3D: cinematic title, map route across the world, timeline in space | `blender` | Real 3D, lighting and depth |

Prefer a built-in template with params; write custom source only when no template fits.

## Templates

- hyperframes: `title_card {title, subtitle?}`, `lower_third {name, role?}`, `data_callout {value, label, context?}`,
  `kinetic_quote {quote, attribution?}`
- manim: `bar_chart {title, labels[], values[], unit?}`, `line_chart {title, x[], y[], unit?}`, `process {steps[]}`
- blender: `title_card {title, subtitle?}`, `lower_third {name, role?}`, `map_route {places:[{name,lat,lon}], title?}`,
  `timeline {events:[{date,label}], title?}`
- motion_canvas: custom `source` (a TSX scene) only

## Writing custom source

- **Hyperframes (HTML):** one self-contained HTML document. Drive every animation from CSS animations or from
  `window.__t` (seconds); the renderer advances time deterministically, so do not use `setTimeout` or real clocks.
  Size everything in `vw`/`vh` so it works at any aspect ratio. Keep text inside a 90% safe area.
- **Manim:** a `Scene` subclass; use `Text`, not `Tex` (no LaTeX installed). Pass `scene_name`.
- **Motion Canvas:** a `makeScene2D` TSX scene; keep it under the shot duration.

## Style

Match the film's look: one typeface family, two weights, a restrained palette taken from the keyframes. Motion should
ease in and out (no linear moves) and finish settling at least half a second before the shot ends so the cut is clean.
Put one idea on screen at a time; a chart shows one comparison, not five. A number on screen should be the same number
the narrator says.
