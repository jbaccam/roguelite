"""True-scale lineup: every exported chest in ONE scene under ONE camera, so relative size
is honest (the per-tier previews pull their camera back for big chests, which made the
largest tiers look smallest when those images were placed side by side).

    blender --background --python lineup.py                 # every tier with a GLB, in ladder order
    blender --background --python lineup.py -- gold legendary

Writes previews/lineup-true-scale[-<tiers>].png (closed, 3/4 view) and ...-front.png. Read-only on every tier's files.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
ORDER = ["wooden", "silver", "gold", "magical", "legendary"]
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TIERS = ARGS or [t for t in ORDER if (ROOT / "exports/glb" / f"chest-{t}.glb").exists()]
GAP = 2.2
STEM = "lineup-true-scale" + ("-" + "-".join(ARGS) if ARGS else "")   # per-call name: parallel runs never clash

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
groups = []
for tier in TIERS:
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(ROOT / "exports/glb" / f"chest-{tier}.glb"))
    objs = [o for o in bpy.context.scene.objects if o not in before]
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    groups.append((tier, objs, lo, hi))

# Row along X, bases on the ground, fronts facing -Y.
x = 0.0
for tier, objs, lo, hi in groups:
    shift = Vector((x - lo.x, 0, 0))
    for o in objs:
        if o.parent is None:
            o.location += shift
    x += (hi.x - lo.x) + GAP
span = x - GAP
top = max(hi.z for _, _, _, hi in groups)

for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
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
bpy.ops.mesh.primitive_plane_add(size=400, location=(span / 2, 0, 0))
fm = bpy.data.materials.new("Floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.44, 0.45, 1)
bpy.context.object.data.materials.append(fm)
bpy.ops.object.camera_add()
cam = bpy.context.object
cam.data.type = "ORTHO"                     # orthographic: no perspective size distortion
scene.camera = cam


def shoot(name, direction, res):
    scene.render.resolution_x, scene.render.resolution_y = res
    target = Vector((span / 2, 0, top * 0.45))
    cam.location = target + Vector(direction).normalized() * 60
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    # Fit width AND height: ortho_scale is the horizontal extent, so tall horns/crowns need
    # the height converted through the aspect ratio or their tips get cropped.
    cam.data.ortho_scale = max(span * 1.08, top * 1.5 * res[0] / res[1])
    scene.render.filepath = str(ROOT / "previews" / name)
    bpy.ops.render.render(write_still=True)


shoot(f"{STEM}.png", (-0.35, -1.0, 0.55), (2400, 760))
shoot(f"{STEM}-front.png", (0, -1.0, 0.18), (2400, 700))
print("LINEUP", TIERS, round(span, 2), flush=True)
