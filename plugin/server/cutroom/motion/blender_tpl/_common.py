"""Shared Blender helpers for Cutroom templates (Blender 5.x, run headless: blender -b -P <tpl>.py -- '<json>')."""
import json
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), "fonts")
PAPER = (0.953, 0.937, 0.902, 1)
ACCENT = (0.91, 0.69, 0.29, 1)
ACCENT2 = (0.37, 0.70, 0.63, 1)
INK = (0.043, 0.051, 0.063, 1)
MUTED = (0.60, 0.64, 0.68, 1)


def srgb_to_lin(c):
    def f(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), c[3] if len(c) > 3 else 1)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["{}"]
    return json.loads(a[0])


def setup(p, default_duration=4.5):
    """Fresh scene with Eevee, resolution/fps/transparency from params. Returns (scene, w, h, frames)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    try:
        sc.eevee.taa_render_samples = int(p.get("samples", 16))
    except AttributeError:
        pass
    for attr, val in (("use_raytracing", False), ("use_shadows", True)):
        try:
            setattr(sc.eevee, attr, val)
        except AttributeError:
            pass
    w, h = int(p.get("w", 1920)), int(p.get("h", 1080))
    fps = int(p.get("fps", 30))
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.render.fps = fps
    frames = max(2, int(round(float(p.get("duration", default_duration)) * fps)))
    sc.frame_start, sc.frame_end = 1, frames
    sc.render.film_transparent = bool(p.get("transparent", False))
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    try:
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
    except TypeError:
        try:
            sc.view_settings.view_transform = "Standard"
        except TypeError:
            pass
    world = bpy.data.worlds.new("w")
    sc.world = world
    try:
        world.use_nodes = True
    except AttributeError:
        pass
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = srgb_to_lin((0.035, 0.04, 0.05, 1))
        bg.inputs[1].default_value = 1.0
    sc.render.filepath = os.path.join(p["frames_dir"], "f")
    return sc, w, h, frames, fps


def font(name="inter-bold.ttf"):
    path = os.path.join(FONTS, name)
    if os.path.exists(path):
        return bpy.data.fonts.load(path, check_existing=True)
    return None


def material(name, color, emission=0.0, metallic=0.0, roughness=0.4, alpha=1.0):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    lin = srgb_to_lin(color)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = lin
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        for nm in ("Emission Color", "Emission"):
            if nm in bsdf.inputs:
                bsdf.inputs[nm].default_value = lin
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
            try:
                m.surface_render_method = "BLENDED"
            except AttributeError:
                pass
    return m


def text(body, size=1.0, fnt=None, extrude=0.0, bevel=0.0, mat=None, align="CENTER", loc=(0, 0, 0), name="txt"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = str(body)
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 3
    cu.align_x = align
    cu.align_y = "CENTER"
    if fnt:
        cu.font = fnt
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    if mat:
        cu.materials.append(mat)
    return ob


def dims(ob):
    bpy.context.view_layer.update()
    return ob.dimensions.copy()


def camera(loc, rot_deg, lens=50, ortho_scale=None):
    cd = bpy.data.cameras.new("cam")
    cd.sensor_fit = "AUTO"
    cd.lens = lens
    if ortho_scale:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho_scale
    cam = bpy.data.objects.new("cam", cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = [math.radians(a) for a in rot_deg]
    bpy.context.scene.camera = cam
    return cam


def visible_size(cam, dist, w, h):
    """World-space (width, height) visible at `dist` from a perspective camera (sensor_fit AUTO)."""
    span = 2 * dist * math.tan(cam.data.angle / 2)
    return (span, span * h / w) if w >= h else (span * w / h, span)


def area_light(loc, rot_deg, energy=400, size=6, color=(1, 1, 1)):
    ld = bpy.data.lights.new("l", "AREA")
    ld.energy = energy
    ld.size = size
    ld.color = color
    lo = bpy.data.objects.new("l", ld)
    bpy.context.scene.collection.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = [math.radians(a) for a in rot_deg]
    return lo


def key(ob, path, frame, value, interp="BEZIER"):
    setattr(ob, path, value) if not isinstance(path, tuple) else None
    ob.keyframe_insert(data_path=path, frame=frame)


def ease_all():
    """Make every keyframe ease in/out (cinematic)."""
    for a in bpy.data.actions:
        try:
            curves = a.fcurves
        except AttributeError:  # Blender 5 layered actions
            curves = [fc for layer in a.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]
        for fc in curves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "AUTO"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"


def render():
    bpy.ops.render.render(animation=True)
