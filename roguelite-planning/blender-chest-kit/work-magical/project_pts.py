"""Project world points through compare_render.py's reference camera (yaw 34, elev 17,
dist 17.5, lens 42, target z 3.9; 800x820) and print pixel coords, which map onto the
reference painting at original (580 + px, 130 + py).

    blender --background --python work-magical/project_pts.py -- points.json
points.json: {"name": [x, y, z], ...}
"""
import json
import math
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:]
pts = json.loads(open(ARGS[0]).read())
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = 800, 820
yaw, elev, dist, lens, tz = 34.0, 17.0, 17.5, 42.0, 3.9
bpy.ops.object.camera_add()
cam = bpy.context.object
cam.data.lens = lens
scene.camera = cam
target = Vector((0.0, 0.0, tz))
d = Vector((-math.sin(math.radians(yaw)) * math.cos(math.radians(elev)), -math.cos(math.radians(yaw)) * math.cos(math.radians(elev)), math.sin(math.radians(elev))))
cam.location = target + d * dist
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.view_layer.update()
out = {}
for k, p in pts.items():
    c = world_to_camera_view(scene, cam, Vector(p))
    out[k] = (round(c.x * 800, 1), round((1 - c.y) * 820, 1))
print("PROJ", json.dumps(out), flush=True)
