"""Reference comparison + ClawSlam impact render (Blender 5.2, headless, after animate_game.py):
    blender -b --factory-startup --python-exit-code 1 --python render_compare.py
Writes previews/Attack_ClawSlam_Impact.png and _work/compare_ours.png (front three-quarter at the
reference sheet's first-panel framing); the side-by-side is assembled by system python (PIL) afterwards.
"""
import bpy, json, math
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(OUT / 'DJCrab.blend'))
scene = bpy.context.scene
rig = bpy.data.objects['DJCrab_Rig']
cam = scene.camera
for eid in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
    try:
        scene.render.engine = eid
        break
    except TypeError:
        continue
scene.eevee.taa_render_samples = 32
scene.render.image_settings.file_format = 'PNG'


def aim(loc, tgt, lens):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


def shot(path, w, h):
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


gd = json.loads((OUT / 'exports' / 'game' / 'BossGameData.json').read_text())
rig.animation_data.action = bpy.data.actions['ClawSlam']
if rig.animation_data.action.slots:
    rig.animation_data.action_slot = rig.animation_data.action.slots[0]
scene.frame_set(1 + round(gd['attacks']['ClawSlam']['impact'] * 24))
aim((-9.5, -14.5, 4.9), (0, -2.2, 1.1), 45)
shot(OUT / 'previews' / 'Attack_ClawSlam_Impact.png', 1024, 768)
rig.animation_data.action = None
for pb in rig.pose.bones:
    pb.matrix_basis.identity()
bpy.context.view_layer.update()
aim((-5.0, -12.8, 5.2), (0, -0.9, 1.55), 50)
shot(OUT / '_work' / 'compare_ours.png', 627, 836)
print('COMPARE_DONE')
