import bpy,json
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'assets'/'11-rocket-launcher'/'components'/'Rocket'
bpy.ops.wm.open_mainfile(filepath=str(p/'Model.blend'))
asset=next(o for c in bpy.data.collections if c.name.endswith('| EXPORT') for o in c.objects if o.type=='MESH')
for o in list(bpy.data.objects):
    if o!=asset:bpy.data.objects.remove(o,do_unlink=True)
for c in list(bpy.data.collections):
    if not c.all_objects:bpy.data.collections.remove(c)
asset.location=(0,0,0)
bpy.context.scene.camera=None
bpy.ops.object.select_all(action='DESELECT');asset.select_set(True);bpy.context.view_layer.objects.active=asset
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(p/'Model.blend'))
s=json.loads((p/'validation.json').read_text());s['blend_total_objects']=len(bpy.context.scene.objects);s['blend_total_meshes']=sum(o.type=='MESH' for o in bpy.context.scene.objects);s['blend_stage_removed']=True;s['pivot']['blend_world_location']=[0,0,0];(p/'validation.json').write_text(json.dumps(s,indent=2))
for meta in [p/'rig_validation.json',p.parents[1]/'rig_validation.json']:
    rig=json.loads(meta.read_text());rig['alignment']['rocket_blend_to_loaded_world_translation']=rig['alignment']['launcher_socket_world'];rig['alignment']['rocket_blend_root']=[0,0,0];rig['rocket']['blend_geometry_only']=True;meta.write_text(json.dumps(rig,indent=2))
readme=(p/'README.md').read_text();readme=readme.replace('Blender review staging is separate and excluded from exports.','The standalone Blender source contains exactly one asset mesh at a zero root transform, with no review floor, camera or lights. Existing Preview and Alternate renders are retained.');(p/'README.md').write_text(readme)
print('ROCKET_GEOMETRY_ONLY',[(o.name,o.type) for o in bpy.context.scene.objects])
