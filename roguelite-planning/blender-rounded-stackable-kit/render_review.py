import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'rounded-stackable-cliff-kit.blend'))
names=list(json.loads((ROOT/'polygon-report.json').read_text())['modules'])
positions=[(-50,65),(-30,65),(-10,65),(12,65),(34,65),(56,65),(-40,32),(-8,32),(30,32),(-48,0),(-24,0),(0,0),(25,0),(49,0)]
for name,(x,y) in zip(names,positions):
    obj=bpy.data.objects[name];obj.location=(x,y,0);lab=bpy.data.objects['Label_'+name];lab.location=obj.location+Vector((0,-9,.02));lab.data.size=1.0
scene=bpy.context.scene;cam=scene.camera;target=Vector((3,30,5));cam.location=target+Vector((0,-70,66));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=143
scene.render.filepath=str(ROOT/'previews/rounded-stackable-lineup.png');bpy.ops.render.render(write_still=True)
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'rounded-stackable-cliff-kit.blend'))
for name in names:bpy.data.objects[name].hide_render=name!='09_Triple_Stack'
for obj in bpy.data.objects:
    if obj.type=='FONT':obj.hide_render=True
obj=bpy.data.objects['09_Triple_Stack'];target=obj.location+Vector((0,0,7));cam.location=target+Vector((20,-36,21));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=30
scene.render.filepath=str(ROOT/'previews/triple-stack-closeup.png');bpy.ops.render.render(write_still=True)
