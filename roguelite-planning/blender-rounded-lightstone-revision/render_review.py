"""Correct the stack closeup framing using final saved geometry/materials."""
import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'rounded-lightstone-revision.blend'))
names=json.loads((ROOT/'polygon-report.json').read_text())['modules']
for name in names:bpy.data.objects[name].hide_render=name!='09_Triple_Eroded_Terrace'
for obj in bpy.data.objects:
    if obj.type=='FONT':obj.hide_render=True
obj=bpy.data.objects['09_Triple_Eroded_Terrace'];target=obj.location+Vector((0,0,7));scene=bpy.context.scene;cam=scene.camera;cam.location=target+Vector((15,-36,19));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=37
scene.render.filepath=str(ROOT/'previews/asymmetric-stack-closeup.png');bpy.ops.render.render(write_still=True)
images=[i for i in bpy.data.images if i.name.endswith('_Color')]
print('PACKED_ATLASES',sum(bool(i.packed_file) for i in images),'TOTAL',len(images),flush=True)
