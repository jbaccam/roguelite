"""Render one 256x256 transparent icon per armor piece (chest reveals, odds panel).

Opens each set's built .blend, hides everything but one piece's meshes (textured and glow), and
renders it from the front-left with the scene's own lights. Output: icons/<SetId>.<Piece>.png,
named like the game's piece ids ('Iron.Helmet').

  blender -b --factory-startup --python render_icons.py            (all sets)
  SETS=iron,ninja blender -b --factory-startup --python render_icons.py
"""
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "icons"
OUT.mkdir(exist_ok=True)
# folder/blend -> ArmorCatalog set id (also the mesh prefix)
SETS = {
    "iron": ("iron/iron.blend", "Iron"),
    "ninja": ("ninja/ninja.blend", "Ninja"),
    "viking": ("viking/viking.blend", "Viking"),
    "samurai": ("samurai/samurai.blend", "Samurai"),
    "spartan": ("spartan/spartan.blend", "Spartan"),
    "dragon-scale": ("dragon-scale.blend", "DragonScale"),
    "phoenix": ("phoenix/phoenix.blend", "Phoenix"),
}
PIECES = ["Helmet", "Chest", "Legs", "Boots"]
want = os.environ.get("SETS")
todo = [k for k in SETS if not want or k in want.split(",")]


def render_set(blend, prefix):
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / blend))
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [
        e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    cam_data = bpy.data.cameras.new("IconCam")
    cam_data.lens_unit = "FOV"
    cam_data.angle = math.radians(28)
    cam = bpy.data.objects.new("IconCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    meshes = [o for o in scene.objects if o.type == "MESH"]
    for piece in PIECES:
        mine = [o for o in meshes if o.name.startswith(f"{prefix}_{piece}_")]
        if not mine:
            print("ICON missing", prefix, piece)
            continue
        for o in meshes:
            o.hide_render = o not in mine
        lo = Vector((1e9, 1e9, 1e9))
        hi = -lo
        for o in mine:
            for c in o.bound_box:
                w = o.matrix_world @ Vector(c)
                lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
                hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
        centre = (lo + hi) / 2
        radius = (hi - lo).length / 2
        # The body faces -y; its left is +x. Look from the front, a little to its right and above.
        direction = Vector((-0.45, -1.0, 0.32)).normalized()
        cam.location = centre + direction * radius / math.sin(cam_data.angle / 2) * 1.02
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(OUT / f"{prefix}.{piece}.png")
        bpy.ops.render.render(write_still=True)
        print("ICON", prefix, piece)


for key in todo:
    blend, prefix = SETS[key]
    if not (ROOT / blend).exists():
        print("ICON skip (no blend)", key)
        continue
    render_set(blend, prefix)
print("ICONS DONE")
