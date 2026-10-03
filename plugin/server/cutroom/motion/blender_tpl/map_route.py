"""Stylised map route: dark tilted plane with a glowing lat/lon grid, stops pop in as glowing beacons, an arcing route
draws between them (bevel_factor_end), labels face the camera, camera drifts.
params: {places: [{name, lat, lon}], title?, duration?, w, h, fps, transparent, frames_dir}"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

bpy = C.bpy
p = C.args()
places = p.get("places") or [{"name": "A", "lat": 0, "lon": 0}, {"name": "B", "lat": 10, "lon": 20}]
sc, w, h, frames, fps = C.setup(p, max(5.0, 1.8 + 1.1 * len(places)))
portrait = h > w

# equirectangular projection, fitted to a box with padding
lons = [float(x["lon"]) for x in places]
lats = [float(x["lat"]) for x in places]
cx, cy = (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2
span_x = max(max(lons) - min(lons), 8) * 1.5
span_y = max(max(lats) - min(lats), 6) * 1.5
box_w, box_h = (10.0, 10.0 * h / w * 0.85) if not portrait else (6.0, 9.0)
k = min(box_w / span_x, box_h / span_y)


def xy(lat, lon):
    return ((float(lon) - cx) * k, (float(lat) - cy) * k * 1.15)


bold = C.font("inter-bold.ttf")
med = C.font("inter-medium.ttf")
grid_m = C.material("grid", (0.37, 0.70, 0.63, 1), emission=0.9)
gold = C.material("gold", (0.95, 0.62, 0.16, 1), emission=6.0)
route_m = C.material("route", (0.98, 0.78, 0.35, 1), emission=8.0)
paper = C.material("paper", C.PAPER, emission=1.2)
ground_m = C.material("ground", (0.035, 0.045, 0.055, 1), roughness=0.8)

# ground + graticule
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -0.02))
g = bpy.context.active_object
g.scale = (40, 40, 1)
g.data.materials.append(ground_m)
step = 10 if span_x > 60 else 5 if span_x > 20 else 2
lo0 = math.floor((cx - span_x) / step) * step
la0 = math.floor((cy - span_y) / step) * step
for i in range(int(2 * span_x / step) + 2):
    x, _ = xy(cy, lo0 + i * step)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 0))
    ln = bpy.context.active_object
    ln.scale = (0.012, 40, 0.004)
    ln.data.materials.append(grid_m)
for j in range(int(2 * span_y / step) + 2):
    _, y = xy(la0 + j * step, cx)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, 0))
    ln = bpy.context.active_object
    ln.scale = (40, 0.012, 0.004)
    ln.data.materials.append(grid_m)

# route: smooth curve lifted into arcs between stops
pts = [xy(pl["lat"], pl["lon"]) for pl in places]
cu = bpy.data.curves.new("route", "CURVE")
cu.dimensions = "3D"
cu.bevel_depth = 0.035
cu.bevel_resolution = 4
spl = cu.splines.new("POLY")
samples = []
for a, b in zip(pts, pts[1:]):
    d = math.dist(a, b)
    for t in [i / 24 for i in range(24)]:
        samples.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, 0.05 + math.sin(math.pi * t) * d * 0.18))
samples.append((pts[-1][0], pts[-1][1], 0.05))
spl.points.add(len(samples) - 1)
for sp, (x, y, z) in zip(spl.points, samples):
    sp.co = (x, y, z, 1)
route = bpy.data.objects.new("route", cu)
sc.collection.objects.link(route)
cu.materials.append(route_m)

# camera: tilted perspective looking at the map
ext_x = max(abs(x) for x, _ in pts) + 1.5
ext_y = max(abs(y) for _, y in pts) + 1.5
dist = max(ext_x * (1.0 if not portrait else h / w), ext_y * 1.6) * 1.55 + 3
cam = C.camera((0, -dist * 0.75, dist * 0.75), (45, 0, 0), lens=40)
target = bpy.data.objects.new("target", None)
sc.collection.objects.link(target)
con = cam.constraints.new("TRACK_TO")
con.target = target
con.track_axis = "TRACK_NEGATIVE_Z"
con.up_axis = "UP_Y"

C.area_light((0, -4, 10), (25, 0, 0), energy=600, size=20)

# title
if p.get("title"):
    t = C.text(p["title"], size=0.7, fnt=bold, mat=paper, name="title")
    t.parent = cam
    td = C.dims(t)
    vis = C.visible_size(cam, 12, w, h)
    sc_t = min(1.0, vis[0] * 0.8 / max(td.x, 1e-3))
    t.scale = (sc_t, sc_t, sc_t)
    t.location = (0, vis[1] / 2 - 1.1, -12)
    t.rotation_euler = (0, 0, 0)

# timing
lead = int(0.6 * fps)
per = max(int(0.9 * fps), int((frames - lead - int(1.2 * fps)) / max(1, len(places))))
cu.bevel_factor_end = 0.0
cu.keyframe_insert("bevel_factor_end", frame=lead)
cu.bevel_factor_end = 1.0
cu.keyframe_insert("bevel_factor_end", frame=lead + per * (len(places) - 1))

for i, (pl, (x, y)) in enumerate(zip(places, pts)):
    f0 = lead + per * i
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.16, location=(x, y, 0.08))
    beacon = bpy.context.active_object
    beacon.data.materials.append(gold)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=1.4, location=(x, y, 0.7))
    pillar = bpy.context.active_object
    pillar.data.materials.append(route_m)
    lab = C.text(pl.get("name", ""), size=0.42, fnt=med, mat=paper, name=f"lab{i}")
    near = sum(1 for (qx, qy) in pts[:i] if math.dist((qx, qy), (x, y)) < 2.2)
    lab.location = (x, y + 0.2, 1.65 + 0.75 * near)
    pillar.scale.z = 1 + 0.55 * near
    pillar.location.z = 0.7 * pillar.scale.z
    lab.rotation_euler = (math.radians(55), 0, 0)
    for ob in (beacon, pillar, lab):
        s0 = tuple(ob.scale)
        ob.scale = (0.001, 0.001, 0.001)
        ob.keyframe_insert("scale", frame=max(1, f0 - 2))
        ob.scale = (s0[0] * 1.25, s0[1] * 1.25, s0[2] * 1.25)
        ob.keyframe_insert("scale", frame=f0 + int(0.25 * fps))
        ob.scale = s0
        ob.keyframe_insert("scale", frame=f0 + int(0.45 * fps))
    # camera target follows the route head
    target.location = (x * 0.15, y * 0.15, 0)
    target.keyframe_insert("location", frame=max(1, f0))

cam.keyframe_insert("location", frame=1)
cam.location.z -= dist * 0.08
cam.location.y += dist * 0.06
cam.keyframe_insert("location", frame=frames)

C.ease_all()
C.render()
