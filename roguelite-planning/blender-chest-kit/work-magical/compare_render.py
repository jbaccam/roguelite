"""Render the exported magical chest framed like the reference painting (front-left 3/4,
slightly high), for side-by-side comparison. Read-only on the kit's files.

    blender --background --python work-magical/compare_render.py -- [tag] [--open] [--cam yaw elev dist lens tz]
Writes work-magical/render_<tag>.png (800x820).
"""
import importlib.util
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

KIT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TAG = ARGS[0] if ARGS and not ARGS[0].startswith("--") else "latest"
OPEN = "--open" in ARGS
CAM = [34.0, 17.0, 17.5, 42.0, 3.9, 0.0]
if "--cam" in ARGS:
    i = ARGS.index("--cam")
    vals = []
    for x in ARGS[i + 1:]:
        try:
            vals.append(float(x))
        except ValueError:
            break
    CAM[:len(vals)] = vals

spec = importlib.util.spec_from_file_location("tier_magical", KIT / "tiers" / "magical.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(KIT / "exports/glb/chest-magical.glb"))
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if OPEN:
    rep = __import__("json").loads((KIT / "polygon-report-magical.json").read_text())
    hz = Vector(rep["hinge_studs"])
    from mathutils import Matrix
    M = Matrix.Translation(hz) @ Matrix.Rotation(math.radians(-rep["open"]["rotate_x_deg"]), 4, "X") @ Matrix.Translation(-hz)
    for o in objs:
        if o.name.startswith("Chest_Lid"):
            o.matrix_world = M @ o.matrix_world
        if o.name.startswith("Chest_Glow"):
            o.hide_render = True

scene = bpy.context.scene
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

yaw, elev, dist, lens, tz, ty = CAM
bpy.ops.object.camera_add()
cam = bpy.context.object
cam.data.lens = lens
scene.camera = cam
target = Vector((0.0, ty, tz))
d = Vector((-math.sin(math.radians(yaw)) * math.cos(math.radians(elev)), -math.cos(math.radians(yaw)) * math.cos(math.radians(elev)), math.sin(math.radians(elev))))
cam.location = target + d * dist
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.render.resolution_x, scene.render.resolution_y = 800, 820
scene.render.filepath = str(OUT / f"render_{TAG}.png")
bpy.ops.render.render(write_still=True)
print("COMPARE_RENDER", scene.render.filepath, flush=True)
