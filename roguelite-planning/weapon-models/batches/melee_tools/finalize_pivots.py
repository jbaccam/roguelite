import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P={1:(2.30,0,.47),2:(.708,0,1.19),3:(.864,0,.567),4:(-.193,0,2.159),5:(.393,0,.863),6:(-.601,0,.623),26:(.164,0,2.468)}
for item in json.loads((ROOT/'inventory.json').read_text()):
 if item['index'] not in P:continue
 out=Path(item['output']);bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));scene=bpy.context.scene
 o=next(x for c in scene.collection.children if c.name.endswith('Export geometry') for x in c.objects if x.type=='MESH')
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;scene.cursor.location=P[item['index']];bpy.ops.object.origin_set(type='ORIGIN_CURSOR');o['pivot']='Handhold center';bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
 bpy.ops.export_scene.fbx(filepath=str(out/'Model.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
 bpy.ops.export_scene.gltf(filepath=str(out/'Model.glb'),use_selection=True,export_format='GLB',export_animations=False)
 stats=json.loads((out/'validation.json').read_text());stats['pivot']=list(P[item['index']]);stats['pivot_description']='Handhold center in reference presentation coordinates'
 for ext in ['glb','fbx']:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
  else:bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
  imported=[x for x in bpy.context.scene.objects if x.type=='MESH'];stats[ext+'_reimport']={'mesh_objects':len(imported),'triangles':sum(len(p.vertices)-2 for x in imported for p in x.data.polygons),'has_uv':all(len(x.data.uv_layers)>0 for x in imported),'has_image_texture':all(any(n.type=='TEX_IMAGE' and n.image for m in x.data.materials if m and m.use_nodes for n in m.node_tree.nodes) for x in imported),'unexpected_stage_objects':sum(x.type!='MESH' for x in bpy.context.scene.objects)}
 (out/'validation.json').write_text(json.dumps(stats,indent=2));print('PIVOT_FINALIZED',item['name'],flush=True)
