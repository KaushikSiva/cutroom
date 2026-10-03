"""Timeline: a glowing line draws through the dates, each stop pops in with a serif date and a label, camera follows.
Horizontal in landscape/square, vertical in portrait.
params: {events: [{date, label}], title?, duration?, w, h, fps, transparent, frames_dir}"""
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

bpy = C.bpy
p = C.args()
events = p.get("events") or [{"date": "2020", "label": "Start"}, {"date": "2026", "label": "Now"}]
n = len(events)
sc, w, h, frames, fps = C.setup(p, max(5.0, 1.5 + 1.0 * n))
portrait = h > w

bold = C.font("inter-bold.ttf")
med = C.font("inter-medium.ttf")
serif = C.font("fraunces-semibold.ttf")
line_m = C.material("line", (0.37, 0.70, 0.63, 1), emission=1.4)
gold = C.material("gold", (0.98, 0.55, 0.12, 1), emission=1.5)
paper = C.material("paper", C.PAPER, emission=1.0)

gap = 4.0
length = gap * (n - 1)
start = -length / 2


def pos(i):
    t = start + gap * i
    return (0, -t, 0) if portrait else (t, 0, 0)


# the line: a poly curve revealed with bevel_factor_end
cu = bpy.data.curves.new("line", "CURVE")
cu.dimensions = "3D"
cu.bevel_depth = 0.035
spl = cu.splines.new("POLY")
spl.points.add(1)
a, b = pos(0), pos(n - 1)
pad = 0.8
spl.points[0].co = (a[0] - (0 if portrait else pad), a[1] + (pad if portrait else 0), 0, 1)
spl.points[1].co = (b[0] + (0 if portrait else pad), b[1] - (pad if portrait else 0), 0, 1)
line = bpy.data.objects.new("line", cu)
sc.collection.objects.link(line)
cu.materials.append(line_m)

# orthographic camera; visible extent along the timeline axis
S = max(11.0, length + 4.0) if not portrait else max(11.0, length + 5.0)
cam = C.camera((0, 0, 10), (0, 0, 0), ortho_scale=S)
vw, vh = (S, S * h / w) if w >= h else (S * w / h, S)
C.area_light((0, 0, 8), (0, 0, 0), energy=300, size=30)

if p.get("title"):
    t = C.text(p["title"], size=0.62, fnt=bold, mat=paper, name="title")
    td = C.dims(t)
    k = min(1.0, vw * 0.85 / max(td.x, 1e-3))
    t.scale = (k, k, k)
    t.parent = cam
    t.location = (0, vh / 2 - 0.9, -5)

Z = S / 11.0  # keep type size constant on screen when the frame widens
for ob in [o for o in bpy.data.objects if o.name.startswith('title')]:
    ob.scale = tuple(v * Z for v in ob.scale)
lead = int(0.5 * fps)
per = max(int(0.7 * fps), int((frames - lead - int(1.0 * fps)) / max(1, n)))
cu.bevel_factor_end = 0.0
cu.keyframe_insert("bevel_factor_end", frame=lead)
cu.bevel_factor_end = 1.0
cu.keyframe_insert("bevel_factor_end", frame=lead + per * (n - 1) + int(0.3 * fps))

for i, ev in enumerate(events):
    x, y, _ = pos(i)
    f0 = lead + per * i
    side = 1 if i % 2 == 0 else -1
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.17 * (Z if not portrait else 1), location=(x, y, 0.05))
    dot = bpy.context.active_object
    dot.data.materials.append(gold)
    wrap = 16 if portrait else 20
    if portrait:  # date + label to the right of the vertical line
        date = C.text(str(ev.get("date", "")), size=0.7, fnt=serif, mat=gold, align="LEFT", name=f"d{i}")
        date.location = (0.55, y + 0.35, 0.05)
        label = C.text("\n".join(textwrap.wrap(str(ev.get("label", "")), wrap)), size=0.34, fnt=med, mat=paper, align="LEFT", name=f"l{i}")
        ld = C.dims(label)
        label.location = (0.57, y - 0.35 - ld.y / 2 + 0.17, 0.05)
        for ob in (date, label):
            ob.location.x -= vw * 0.18
        dot.location.x -= vw * 0.18
    else:
        date = C.text(str(ev.get("date", "")), size=0.66 * Z, fnt=serif, mat=gold, name=f"d{i}")
        date.location = (x, side * 0.95 * Z, 0.05)
        label = C.text("\n".join(textwrap.wrap(str(ev.get("label", "")), wrap)), size=0.32 * Z, fnt=med, mat=paper, name=f"l{i}")
        ld = C.dims(label)
        label.location = (x, side * (1.6 * Z + ld.y / 2), 0.05)
    for ob in (dot, date, label):
        s0 = tuple(ob.scale)
        ob.scale = (0.001, 0.001, 0.001)
        ob.keyframe_insert("scale", frame=max(1, f0))
        ob.scale = tuple(v * 1.15 for v in s0)
        ob.keyframe_insert("scale", frame=f0 + int(0.25 * fps))
        ob.scale = s0
        ob.keyframe_insert("scale", frame=f0 + int(0.45 * fps))
    # follow the newest stop, clamped so the line's ends stay framed
    span = vh if portrait else vw
    if length > span * 0.7:
        lim = (length - span * 0.7) / 2
        c = max(-lim, min(lim, (y if portrait else x)))
        if portrait:
            cam.location = (-vw * 0.18 * 0 + 0, c, 10)
        else:
            cam.location = (c, 0, 10)
        cam.keyframe_insert("location", frame=max(1, f0))

if portrait:
    line.location.x -= vw * 0.18

C.ease_all()
C.render()
