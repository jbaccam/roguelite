"""Render the exported magical chest through the camera fitted to the reference painting
(fit_camera.py -> ref_camera.json, dist 25: yaw 38.2, elev 22.2), in the painting's own
1920x1080 frame, so any crop of the painting can be compared pixel for pixel.

    blender --background --python work-magical/ref_render.py -- <tag> [--open] [--skull] [--pts pts.json]
Writes work-magical/ref_<tag>.png (full frame) and, with --skull, ref_<tag>_skull.png: the
painting's skull box (900,235)-(1180,500) rendered at 3x. --pts prints pixel positions.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

KIT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TAG = ARGS[0] if ARGS and not ARGS[0].startswith("--") else "latest"
CAMFIT = dict(yaw=38.2, elev=22.2, dist=25.0, focal_px=1994.0, cx=1013.0, cy=586.0)
SKULL_BOX = (900, 235, 1180, 500)

spec = importlib.util.spec_from_file_location("tier_magical", KIT / "tiers" / "magical.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
cam_data = bpy.data.cameras.new("RefCam")
cam = bpy.data.objects.new("RefCam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
cam_data.sensor_fit = "HORIZONTAL"
cam_data.sensor_width = 36.0
cam_data.lens = CAMFIT["focal_px"] * 36.0 / 1920
cam_data.shift_x = -(CAMFIT["cx"] - 960) / 1920
cam_data.shift_y = (CAMFIT["cy"] - 540) / 1920
y, e = math.radians(CAMFIT["yaw"]), math.radians(CAMFIT["elev"])
d = Vector((-math.sin(y) * math.cos(e), -math.cos(y) * math.cos(e), math.sin(e)))
target = Vector((0, 0, 3.0))
cam.location = target + d * CAMFIT["dist"]
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.view_layer.update()

if "--pts" in ARGS:
    pts = json.loads(open(ARGS[ARGS.index("--pts") + 1]).read())
    out = {}
    for k, p in pts.items():
        c = world_to_camera_view(scene, cam, Vector(p))
        out[k] = (round(c.x * 1920, 1), round((1 - c.y) * 1080, 1))
    print("PROJ", json.dumps(out), flush=True)
    if "--only-pts" in ARGS:
        raise SystemExit(0)

bpy.ops.import_scene.gltf(filepath=str(KIT / "exports/glb/chest-magical.glb"))
objs = [o for o in scene.objects if o.type == "MESH"]
if "--open" in ARGS:
    rep = json.loads((KIT / "polygon-report-magical.json").read_text())
    hz = Vector(rep["hinge_studs"])
    M = Matrix.Translation(hz) @ Matrix.Rotation(math.radians(-rep["open"]["rotate_x_deg"]), 4, "X") @ Matrix.Translation(-hz)
    for o in objs:
        if o.name.startswith("Chest_Lid"):
            o.matrix_world = M @ o.matrix_world
        if o.name.startswith("Chest_Glow"):
            o.hide_render = True

scene.render.engine = "BLENDER_EEVEE"
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("Sky")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.52, 0.70, 0.92, 1)
scene.world = world
bpy.ops.object.light_add(type="SUN")
sun = bpy.context.object
sun.data.energy = 3.2
sun.data.angle = math.radians(12)
sun.data.color = (1.0, 0.96, 0.88)
sun.rotation_euler = (math.radians(48), 0, math.radians(-38))
for pos, col, watts in getattr(T, "LIGHTS", []):
    bpy.ops.object.light_add(type="POINT", location=pos)
    L = bpy.context.object
    L.data.energy = watts
    L.data.color = tuple(c / 255 for c in col)
    L.data.shadow_soft_size = 0.4
bpy.ops.mesh.primitive_circle_add(vertices=48, radius=18, fill_type="NGON")
fm = bpy.data.materials.new("Floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.44, 0.45, 1)
bpy.context.object.data.materials.append(fm)

scene.render.filepath = str(OUT / f"ref_{TAG}.png")
bpy.ops.render.render(write_still=True)
if "--skull" in ARGS:
    import numpy as np
    Msk, tsk = T.skull_place(np)
    def px(q):
        c = world_to_camera_view(scene, cam, Vector((Msk @ np.array(q, np.float32) + tsk).tolist()))
        return c.x * 1920, (1 - c.y) * 1080
    er, el = px((-T.SK_EYE_C[0], -0.86, T.SK_EYE_C[2])), px((T.SK_EYE_C[0], -0.86, T.SK_EYE_C[2]))
    k = math.hypot(el[0] - er[0], el[1] - er[1]) / math.hypot(1120 - 1040, 377 - 397)   # our skull / painted
    mx, my = (er[0] + el[0]) / 2, (er[1] + el[1]) / 2                                     # follow our skull
    x0, y0 = mx + (SKULL_BOX[0] - 1080) * k, my + (SKULL_BOX[1] - 387) * k
    x1, y1 = mx + (SKULL_BOX[2] - 1080) * k, my + (SKULL_BOX[3] - 387) * k
    print("SKULL_SCALE_VS_PAINTING", round(k, 3), flush=True)
    scene.render.resolution_percentage = int(round(300 / k))
    scene.render.use_border = True
    scene.render.use_crop_to_border = True
    scene.render.border_min_x, scene.render.border_max_x = x0 / 1920, x1 / 1920
    scene.render.border_min_y, scene.render.border_max_y = 1 - y1 / 1080, 1 - y0 / 1080
    scene.render.filepath = str(OUT / f"ref_{TAG}_skull.png")
    bpy.ops.render.render(write_still=True)
if "--side" in ARGS:
    # orthographic side view from -x (hinge check) and a 3/4 back view
    scene.render.use_border = False
    scene.render.resolution_percentage = 100
    scene.render.resolution_x, scene.render.resolution_y = 1100, 900
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 15.0
    cam_data.shift_x = cam_data.shift_y = 0.0
    cam.location = Vector((-30.0, 1.2, 5.0))
    cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
    scene.render.filepath = str(OUT / f"ref_{TAG}_side.png")
    bpy.ops.render.render(write_still=True)
    cam_data.type = "PERSP"
    cam_data.lens = 40
    tgt = Vector((0, 1.5, 4.5))
    cam.location = Vector((-11.0, 13.0, 9.0))
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(OUT / f"ref_{TAG}_back.png")
    bpy.ops.render.render(write_still=True)
print("REF_RENDER_DONE", flush=True)
