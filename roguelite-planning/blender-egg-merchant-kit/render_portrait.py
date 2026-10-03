"""The Egg Merchant's portrait for the tutorial guide's text box (TutorialGuideUI): a 3/4 head-and-
shoulders bust on a transparent background, lit like the kit's previews (warm key sun, grey world),
plus a cool rim from behind. Renders the merchant already built and baked into merchant.blend
(build_merchant.py); it builds nothing itself.
    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" merchant.blend --background --python render_portrait.py
-> previews/merchant-portrait.png (512 x 512)
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "previews" / "merchant-portrait.png"

scene = bpy.context.scene
# Only the merchant: drop any preview helpers saved with the file.
for o in list(scene.objects):
    if o.name.startswith("Preview_") or o.type in {"LIGHT", "CAMERA"}:
        bpy.data.objects.remove(o, do_unlink=True)

for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.render.resolution_x = scene.render.resolution_y = 512
scene.render.film_transparent = True
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"

world = bpy.data.worlds.new("PortraitGrey")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.52, 0.52, 0.55, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
scene.world = world


def sun(name, energy, color, rot):
    data = bpy.data.lights.new(name, "SUN")
    data.energy = energy
    data.angle = math.radians(14)
    data.color = color
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.rotation_euler = [math.radians(a) for a in rot]
    return obj


sun("Portrait_Key", 3.2, (1.0, 0.96, 0.9), (50, 0, -35))
sun("Portrait_Rim", 2.2, (0.75, 0.88, 1.0), (60, 0, 150))

cam = bpy.data.objects.new("Portrait_Cam", bpy.data.cameras.new("Portrait_Cam"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.lens = 85
cam.location = Vector((-5.9, -14.2, 5.7))
target = Vector((0.25, 0.1, 4.6))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()

scene.render.filepath = str(OUT)
bpy.ops.render.render(write_still=True)
print("PORTRAIT", OUT, flush=True)
