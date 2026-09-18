import bpy,json
from pathlib import Path
from mathutils import Vector
out=Path(__file__).resolve().parents[2]/'assets'/'25-wrecking-ball'
bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'))
for c in list(bpy.data.collections):
 if 'REVIEW' in c.name:
  for o in list(c.objects):bpy.data.objects.remove(o,do_unlink=True)
  bpy.data.collections.remove(c)
rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
for screen in bpy.data.screens:
 for a in screen.areas:
  if a.type=='VIEW_3D':a.spaces.active.region_3d.view_perspective='PERSP';a.spaces.active.region_3d.view_location=(.1,0,1.8);a.spaces.active.region_3d.view_distance=6;a.spaces.active.shading.type='MATERIAL'
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'));v=json.loads((out/'rig_validation.json').read_text());v['source_scene_objects']={o.name:o.type for o in bpy.context.scene.objects};v['source_stage_objects']=0;(out/'rig_validation.json').write_text(json.dumps(v,indent=2));p=out/'Model.blend1'
if p.exists():p.unlink()
