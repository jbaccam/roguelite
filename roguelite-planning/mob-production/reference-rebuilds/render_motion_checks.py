import bpy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for mob in sys.argv[sys.argv.index('--')+1:]:
    out=ROOT/mob;bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));scene=bpy.context.scene;rig=bpy.data.objects['Rig']
    for track in rig.animation_data.nla_tracks:track.mute=True
    scene.cycles.samples=12;scene.render.resolution_x=600;scene.render.resolution_y=600
    for clip,frame in [('Move',7),('Death',25)]:
        rig.animation_data.action=bpy.data.actions[clip];scene.frame_set(frame);scene.render.filepath=str(out/(clip+'.png'));bpy.ops.render.render(write_still=True)
