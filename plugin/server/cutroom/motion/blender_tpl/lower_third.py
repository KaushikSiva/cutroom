"""3D lower third (overlay): glowing accent bar, dark glass plate, name + role sliding in, out at the end.
params: {name, role?, duration?, w, h, fps, transparent, frames_dir}"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

bpy = C.bpy
p = C.args()
sc, w, h, frames, fps = C.setup(p, 4.5)
portrait = h > w

# orthographic camera: visible width = S (landscape) or S * w / h (portrait)
S = 16.0
cam = C.camera((0, 0, 10), (0, 0, 0), ortho_scale=S)
vw, vh = (S, S * h / w) if w >= h else (S * w / h, S)

bold = C.font("inter-bold.ttf")
med = C.font("inter-medium.ttf")
paper = C.material("paper", C.PAPER, emission=1.0)
gold = C.material("gold", (0.98, 0.55, 0.12, 1), emission=1.5)
plate_m = C.material("plate", (0.03, 0.035, 0.045, 1), emission=0.0, alpha=0.82, roughness=0.6)

name = C.text(p.get("name", ""), size=0.62, fnt=bold, mat=paper, align="LEFT", name="name")
role = C.text(str(p.get("role", "")).upper(), size=0.28, fnt=med, mat=gold, align="LEFT", name="role")
role.data.space_character = 1.3
nd, rd = C.dims(name), C.dims(role)
width = max(nd.x, rd.x) + 1.1
height = nd.y + rd.y + 0.85

left = -vw / 2 + (0.07 * vw if not portrait else 0.08 * vw)
bottom = -vh / 2 + (0.13 * vh if not portrait else 0.22 * vh)
cy = bottom + height / 2

bpy.ops.mesh.primitive_plane_add(size=1, location=(left + width / 2 + 0.25, cy, -0.05))
plate = bpy.context.active_object
plate.scale = (width, height, 1)
plate.data.materials.append(plate_m)

bpy.ops.mesh.primitive_cube_add(size=1, location=(left, cy, 0.05))
bar = bpy.context.active_object
bar.scale = (0.09, height, 0.09)
bar.data.materials.append(gold)

name.location = (left + 0.55, cy + rd.y / 2 + 0.12, 0.1)
role.location = (left + 0.57, cy - nd.y / 2 - 0.05, 0.1)
C.area_light((0, 0, 8), (0, 0, 0), energy=300, size=20)

# in
bar.scale.y = 0.001
bar.keyframe_insert("scale", frame=1)
bar.scale.y = height
bar.keyframe_insert("scale", frame=int(0.45 * fps))
px = plate.scale.x
plate.location.x -= px / 2
plate.scale.x = 0.001
plate.keyframe_insert("scale", frame=int(0.2 * fps))
plate.keyframe_insert("location", frame=int(0.2 * fps))
plate.scale.x = px
plate.location.x += px / 2
plate.keyframe_insert("scale", frame=int(0.85 * fps))
plate.keyframe_insert("location", frame=int(0.85 * fps))
for ob, start in ((name, int(0.45 * fps)), (role, int(0.65 * fps))):
    x0 = ob.location.x
    ob.location.x = x0 - 0.8
    ob.hide_render = True
    ob.keyframe_insert("hide_render", frame=1)
    ob.keyframe_insert("location", frame=start)
    ob.hide_render = False
    ob.keyframe_insert("hide_render", frame=start)
    ob.location.x = x0
    ob.keyframe_insert("location", frame=start + int(0.6 * fps))

# out: everything slides left and disappears
out_start = frames - int(0.55 * fps)
for ob in (bar, plate, name, role):
    ob.keyframe_insert("location", frame=out_start)
    ob.location.x -= vw * 0.6
    ob.keyframe_insert("location", frame=frames)

C.ease_all()
C.render()
