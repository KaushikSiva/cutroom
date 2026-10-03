"""Cinematic 3D title card: bevelled serif title, gold kicker, subtitle, lit backdrop, drifting embers, slow dolly.
params: {title, subtitle?, kicker?, duration?, w, h, fps, transparent?, frames_dir}"""
import math
import os
import random
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

p = C.args()
sc, w, h, frames, fps = C.setup(p, 5.0)
portrait = h > w
random.seed(7)

D = 14.0
cam = C.camera((0, 0, D * 1.10), (0, 0, 0), lens=50)
vw, vh = C.visible_size(cam, D, w, h)

serif = C.font("fraunces-semibold.ttf")
sans = C.font("inter-medium.ttf")
paper = C.material("paper", C.PAPER, emission=0.18, roughness=0.3)
gold = C.material("gold", (0.95, 0.62, 0.16, 1), emission=1.6, metallic=0.6, roughness=0.25)
muted = C.material("muted", C.MUTED, emission=0.9)

title_txt = "\n".join(textwrap.wrap(str(p.get("title", "Untitled")), 12 if portrait else 22)) or " "
title = C.text(title_txt, size=1.0, fnt=serif, extrude=0.06, bevel=0.012, mat=paper, name="title")
title.data.space_line = 0.92
td = C.dims(title)
s = min((vw * 0.72) / max(td.x, 1e-3), (vh * 0.42) / max(td.y, 1e-3))
title.scale = (s, s, s)
th = td.y * s

kicker = C.text(str(p.get("kicker", "")).upper(), size=0.32, fnt=sans, mat=gold, name="kicker")
kicker.data.space_character = 1.35
kd = C.dims(kicker)
ks = min(1.0, (vw * 0.7) / max(kd.x, 1e-3))
kicker.scale = (ks, ks, ks)

sub_txt = "\n".join(textwrap.wrap(str(p.get("subtitle", "")), 30 if portrait else 60))
sub = C.text(sub_txt, size=0.42, fnt=sans, mat=muted, name="sub")
sd = C.dims(sub)
ss = min(1.0, (vw * 0.8) / max(sd.x, 1e-3))
sub.scale = (ss, ss, ss)

# vertical layout around the centre
gap = 0.55
kicker.location = (0, th / 2 + gap + 0.2, 0.05)
title.location = (0, 0, 0)
sub.location = (0, -th / 2 - gap - sd.y * ss / 2, 0.05)

# gold rule under the kicker
bpy = C.bpy
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, th / 2 + gap - 0.15, 0.02))
rule = bpy.context.active_object
rule.scale = (min(vw * 0.35, 4.0), 0.012, 1)
rule.data.materials.append(gold)

# backdrop with a pool of light
if not p.get("transparent"):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -3))
    back = bpy.context.active_object
    back.scale = (vw * 3, vh * 3, 1)
    back.data.materials.append(C.material("back", (0.06, 0.07, 0.085, 1), roughness=0.9))
    C.area_light((-vw * 0.25, vh * 0.3, 6), (0, 0, 0), energy=1600, size=10, color=(1.0, 0.86, 0.66))
    C.area_light((vw * 0.4, -vh * 0.35, 5), (0, 0, 0), energy=500, size=8, color=(0.55, 0.85, 0.8))
    # drifting embers
    ember_mats = [C.material("e1", C.ACCENT, emission=6.0), C.material("e2", C.ACCENT2, emission=5.0)]
    for i in range(70):
        x, y, z = random.uniform(-vw, vw), random.uniform(-vh, vh), random.uniform(-2.8, -0.5)
        bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(0.012, 0.04), segments=8, ring_count=6, location=(x, y, z))
        e = bpy.context.active_object
        e.data.materials.append(random.choice(ember_mats))
        e.keyframe_insert("location", frame=1)
        e.location = (x + random.uniform(-0.4, 0.4), y + random.uniform(0.3, 0.9), z)
        e.keyframe_insert("location", frame=frames)
else:
    C.area_light((0, 0, 8), (0, 0, 0), energy=900, size=12)

# animation
f_in = 1
title.location.y -= 0.6
title.rotation_euler = (math.radians(12), 0, 0)
title.keyframe_insert("location", frame=f_in)
title.keyframe_insert("rotation_euler", frame=f_in)
title.location.y += 0.6
title.rotation_euler = (0, 0, 0)
title.keyframe_insert("location", frame=f_in + int(1.2 * fps))
title.keyframe_insert("rotation_euler", frame=f_in + int(1.2 * fps))

for ob, start, dy in ((kicker, int(0.4 * fps), -0.25), (sub, int(1.1 * fps), -0.3)):
    y0 = ob.location.y
    ob.location.y = y0 + dy
    ob.scale = tuple(v * 0.001 for v in ob.scale) if False else ob.scale
    ob.keyframe_insert("location", frame=max(1, start))
    ob.location.y = y0
    ob.keyframe_insert("location", frame=start + int(0.8 * fps))
    ob.hide_render = True
    ob.keyframe_insert("hide_render", frame=1)
    ob.hide_render = False
    ob.keyframe_insert("hide_render", frame=max(2, start))

rx = rule.scale.x
rule.scale.x = 0.001
rule.keyframe_insert("scale", frame=int(0.5 * fps))
rule.scale.x = rx
rule.keyframe_insert("scale", frame=int(1.4 * fps))

cam.keyframe_insert("location", frame=1)
cam.location.z = D
cam.keyframe_insert("location", frame=frames)

C.ease_all()
C.render()
