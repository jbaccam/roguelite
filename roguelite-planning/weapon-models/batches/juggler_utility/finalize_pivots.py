import bpy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_utility as build
pivots={17:(0,0,0),20:(0,0,0),21:(-.55,0,1.1),22:(0,0,1.2),23:(0,0,0),25:(1.07,0,2),27:(.60,0,.60),28:(.86,0,2.07)}
for item in build.INV:
 if item['index'] not in pivots:continue
 out=Path(item['output']);bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));obs=[o for o in bpy.context.scene.objects if o.type=='MESH' and any('export geometry' in c.name for c in o.users_collection)]
 bpy.ops.object.select_all(action='DESELECT')
 for o in obs:o.select_set(True)
 bpy.context.view_layer.objects.active=obs[0];bpy.context.scene.cursor.location=pivots[item['index']];bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
 bpy.ops.export_scene.fbx(filepath=str(out/'Model.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
 bpy.ops.export_scene.gltf(filepath=str(out/'Model.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_animations=False)
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
 st=json.loads((out/'validation.json').read_text());st['pivot']=list(pivots[item['index']]);st['pivot_description']='Base center' if item['index'] in [17,20,23] else 'Ball/spool center' if item['index'] in [21,22] else 'Handhold center'
 for ext in ['glb','fbx']:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
  else:bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
  meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];st[ext+'_reimport']=build.stats(meshes,ext=='glb');st[ext+'_reimport']['unexpected_nonmesh_objects']=sum(o.type!='MESH' for o in bpy.context.scene.objects);st[ext+'_reimport']['topology_note']='GLB split normal/UV coordinate duplicates welded for topology measurement.'
 (out/'validation.json').write_text(json.dumps(st,indent=2));print('FINAL_PIVOT',item['index'],st['pivot'])
