"""Skull lab: build only the sculpted skull bone from tiers/magical.py (same numpy functions
build() uses), decimate it the same way, drop it on a stand-in lid and render clay + a rough
colour pass from the reference angle, the front and the side. Read-only on the kit.

    blender --background --python work-magical/skull_lab.py -- <tag>
Writes work-magical/lab_<tag>.png (reference crop | 3/4 clay | 3/4 colour | front | side).
"""
import importlib.util
import math
import sys
import time
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Vector

KIT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TAG = ARGS[0] if ARGS else "lab"
spec = importlib.util.spec_from_file_location("tier_magical", KIT / "tiers" / "magical.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)

t0 = time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)
M, tv = T.skull_place(np)
cracks = T.skull_cracks(np)
lid = (M, tv, T.ZC, T.R)
V, Q = T.skull_surface(np, cracks, lid)
print("SURFACE", len(V), len(Q), round(time.time() - t0, 1), flush=True)
me = bpy.data.meshes.new("skull")
me.from_pydata(V.tolist(), [], Q.tolist())
me.validate()
ob = bpy.data.objects.new("skull", me)
bpy.context.collection.objects.link(ob)
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
dec = ob.modifiers.new("dec", "DECIMATE")
dec.ratio = T.SKULL_TRIS / (2 * len(Q))
dec.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier=dec.name)
bm = bmesh.new()
bm.from_mesh(me)
bmesh.ops.triangulate(bm, faces=bm.faces[:])
bm.normal_update()
bm.verts.ensure_lookup_table()
Vd = np.array([v.co[:] for v in bm.verts], np.float32)
Nd = np.array([v.normal[:] for v in bm.verts], np.float32)
a, b = T.skull_paint(np, Vd, Nd, cracks, lid)
print("DECIMATED", len(bm.faces), round(time.time() - t0, 1), flush=True)


def lerp(c0, c1, f):
    return [x + (y - x) * f for x, y in zip(c0, c1)]


def ramp(x, stops):
    for (ta, ca), (tb, cb) in zip(stops, stops[1:]):
        if x <= tb:
            return lerp(ca, cb, min(max((x - ta) / (tb - ta), 0), 1))
    return stops[-1][1]


P = T.PALETTE
warm = [(0, P["sk_void"]), (0.25, P["sk_warm_dark"]), (0.55, P["sk_warm"]), (0.9, P["sk_warm_light"])]
olive = [(0, P["sk_void"]), (0.22, P["bone_dark"]), (0.5, P["bone"]), (0.78, P["bone_light"]), (1.0, P["bone_hi"])]
cool = [(0, P["sk_void"]), (0.25, P["sk_cool_dark"]), (0.55, P["sk_cool"]), (0.9, P["sk_cool_light"])]
col = bm.loops.layers.color.new("Col")
for f in bm.faces:
    for lp in f.loops:
        i = lp.vert.index
        w, o, c = ramp(b[i], warm), ramp(b[i], olive), ramp(b[i], cool)
        rgb = lerp(w, o, a[i] / 0.5) if a[i] < 0.5 else lerp(o, c, (a[i] - 0.5) / 0.5)
        lp[col] = [(x / 255) ** 2.2 for x in rgb] + [1]
Mw = np.asarray(M, float)
for v in bm.verts:
    v.co = Vector((Mw @ np.array(v.co[:]) + tv).tolist())
bm.to_mesh(me)
bm.free()
for p in me.polygons:
    p.use_smooth = False

# stand-in lid + body
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=T.R, depth=2 * T.XLID, location=(0, 0, T.ZC), rotation=(0, math.pi / 2, 0))
lidob = bpy.context.object
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, (T.FOOT + T.ZC) / 2), scale=(2 * T.XLID, 2 * T.R, T.ZC - T.FOOT))
body = bpy.context.object
pm = bpy.data.materials.new("purple")
pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.06, 0.22, 1)
lidob.data.materials.append(pm)
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.66, depth=0.3, location=(0, -T.R - 0.3, T.Z_SEAMLOCK), rotation=(math.pi / 2, 0, 0))
bpy.context.object.data.materials.append(pm)
body.data.materials.append(pm)

clay = bpy.data.materials.new("clay")
clay.use_nodes = True
clay.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.5, 1)
clay.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
paint = bpy.data.materials.new("paint")
paint.use_nodes = True
nt = paint.node_tree
attr = nt.nodes.new("ShaderNodeVertexColor")
attr.layer_name = "Col"
nt.links.new(attr.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
ob.data.materials.append(clay)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("Sky")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.52, 0.70, 0.92, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
scene.world = world
bpy.ops.object.light_add(type="SUN")
sun = bpy.context.object
sun.data.energy = 3.4
sun.data.angle = math.radians(10)
sun.rotation_euler = (math.radians(48), 0, math.radians(-38))
bpy.ops.object.light_add(type="POINT", location=(0, -3.6, 5.2))
bpy.context.object.data.energy = 150
bpy.context.object.data.color = (0.35, 0.65, 1.0)
# the camera fitted to the painting (fit_camera.py), cropped to the painting's skull box at 3x
CAMFIT = dict(yaw=38.2, elev=22.2, dist=25.0, focal_px=1994.0, cx=1013.0, cy=586.0)
BOX = (900, 235, 1180, 500)
cd = bpy.data.cameras.new("RefCam")
cam = bpy.data.objects.new("RefCam", cd)
scene.collection.objects.link(cam)
scene.camera = cam
cd.sensor_fit, cd.sensor_width = "HORIZONTAL", 36.0
cd.lens = CAMFIT["focal_px"] * 36.0 / 1920
cd.shift_x, cd.shift_y = -(CAMFIT["cx"] - 960) / 1920, (CAMFIT["cy"] - 540) / 1920
yy, ee = math.radians(CAMFIT["yaw"]), math.radians(CAMFIT["elev"])
dd = Vector((-math.sin(yy) * math.cos(ee), -math.cos(yy) * math.cos(ee), math.sin(ee)))
cam.location = Vector((0, 0, 3.0)) + dd * CAMFIT["dist"]
cam.rotation_euler = (Vector((0, 0, 3.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.view_layer.update()
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
KEYS = {"dome_top": (0.0, 0.1, 0.64), "eye_r": (-0.44, -0.86, -0.06), "eye_l": (0.44, -0.86, -0.06),
        "nose": (0.0, -1.02, -0.27), "jaw": (0.0, -0.84, -0.7)}
pix = {}
for kname, q in KEYS.items():
    w = Vector((Mw @ np.array(q) + tv).tolist())
    c = world_to_camera_view(scene, cam, w)
    pix[kname] = (c.x * 1920, (1 - c.y) * 1080)
# follow our skull: shift the painting's skull box so the eye midpoints line up
emx, emy = (pix["eye_r"][0] + pix["eye_l"][0]) / 2, (pix["eye_r"][1] + pix["eye_l"][1]) / 2
ox, oy = emx - (1040 + 1120) / 2, emy - (397 + 377) / 2
BOX = (BOX[0] + ox, BOX[1] + oy, BOX[2] + ox, BOX[3] + oy)
print("BOX_SHIFT", round(ox, 1), round(oy, 1), flush=True)
proj = {k: (round((x - BOX[0]) * 3), round((y - BOX[1]) * 3)) for k, (x, y) in pix.items()}
print("KEYS", proj, flush=True)
import json  # noqa: E402
(OUT / "_lab_keys.json").write_text(json.dumps(proj))
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
scene.render.resolution_percentage = 300
scene.render.use_border = scene.render.use_crop_to_border = True
scene.render.border_min_x, scene.render.border_max_x = BOX[0] / 1920, BOX[2] / 1920
scene.render.border_min_y, scene.render.border_max_y = 1 - BOX[3] / 1080, 1 - BOX[1] / 1080


def shoot(name):
    scene.render.filepath = str(OUT / f"_lab_{name}.png")
    bpy.ops.render.render(write_still=True)


shoot("34clay")
ob.data.materials[0] = paint
shoot("34col")
# orthographic-ish views for shape: front and side, full frame around the skull
scene.render.use_border = False
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 560, 520, 100
cd2 = bpy.data.cameras.new("Aux")
aux = bpy.data.objects.new("Aux", cd2)
scene.collection.objects.link(aux)
scene.camera = aux
cd2.lens = 60
ctr = Vector((Mw @ np.array((0, -0.1, 0.1)) + tv).tolist())
for name, yaw_, el_ in (("front", 0, 8), ("side", 90, 4), ("top", 20, 60)):
    dv = Vector((-math.sin(math.radians(yaw_)) * math.cos(math.radians(el_)), -math.cos(math.radians(yaw_)) * math.cos(math.radians(el_)), math.sin(math.radians(el_))))
    aux.location = ctr + dv * 8.5
    aux.rotation_euler = (ctr - aux.location).to_track_quat("-Z", "Y").to_euler()
    ob.data.materials[0] = paint if name == "front" else clay
    shoot(name)
print("LAB_DONE", round(time.time() - t0, 1), flush=True)
