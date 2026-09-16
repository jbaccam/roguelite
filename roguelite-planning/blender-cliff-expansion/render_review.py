"""Refresh focused scatter preview and organize saved blend labels without changing exports."""
import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'modular-cliff-expansion.blend'))
report=json.loads((ROOT/'polygon-report.json').read_text())['modules'];scene=bpy.context.scene;cam=scene.camera
saved={name:bpy.data.objects[name].location.copy() for name in report}
for name,spec in report.items():bpy.data.objects[name].hide_render=spec['group']!='Scatter_and_Fillers'
for o in bpy.data.objects:
    if o.type=='FONT':o.hide_render=True
names=[name for name,spec in report.items() if spec['group']=='Scatter_and_Fillers']
for i,name in enumerate(names):
    o=bpy.data.objects[name];o.location=((i%3-1)*24,(i//3)*22,0)
    lab=bpy.data.objects.get('Label_'+name);lab.location=o.location+Vector((0,-8,.03));lab.hide_render=False
target=Vector((0,22,2));cam.location=target+Vector((12,-68,75));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=87;scene.render.filepath=str(ROOT/'previews/scatter_and_fillers.png');bpy.ops.render.render(write_still=True)
for name,loc in saved.items():
    o=bpy.data.objects[name];o.location=loc;o.hide_render=False
    lab=bpy.data.objects.get('Label_'+name)
    if lab:lab.location=o.location+Vector((0,-10,.03));lab.hide_render=False
cam.location=(70,-130,140);cam.rotation_euler=(Vector((0,120,8))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=330
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'modular-cliff-expansion.blend'))
