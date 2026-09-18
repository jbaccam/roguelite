import bpy,json,hashlib,bmesh
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for item in json.loads((ROOT/'inventory.json').read_text()):
 if item['batch']!='throwables':continue
 out=Path(item['output']);bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'))
 meshes=[o for o in bpy.data.objects if o.type=='MESH' and any('Export geometry' in c.name for c in o.users_collection)]
 stats=json.loads((out/'validation.json').read_text());images=[n.image for o in meshes for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
 stats['blend_packed_texture']=all(i.packed_file is not None and len(i.pixels)>0 and min(i.size)>0 for i in images)
 stats['named_component_groups']=sum(len(o.vertex_groups) for o in meshes)
 stats['all_source_faces_triangular']=all(len(p.vertices)==3 for o in meshes for p in o.data.polygons)
 stats['reference_sha256_matches']=hashlib.sha256((out/'Reference.png').read_bytes()).digest()==hashlib.sha256(Path(item['source']).read_bytes()).digest()
 for ext in ['glb','fbx']:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
  else:bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
  meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];images=[n.image for o in meshes for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
  check=stats[ext+'_reimport'];check['all_faces_triangular']=all(len(p.vertices)==3 for o in meshes for p in o.data.polygons);check['texture_pixels_loaded']=bool(images) and all(len(i.pixels)>0 and min(i.size)>0 for i in images);check['triangle_count_matches']=sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons)==stats['triangles'];check['unexpected_stage_objects']=sum(o.type!='MESH' for o in bpy.context.scene.objects)
 assert stats['blend_packed_texture'] and stats['reference_sha256_matches'] and stats['all_source_faces_triangular']
 assert all(stats[e+'_reimport']['all_faces_triangular'] and stats[e+'_reimport']['texture_pixels_loaded'] and stats[e+'_reimport']['triangle_count_matches'] and stats[e+'_reimport']['unexpected_stage_objects']==0 for e in ['fbx','glb'])
 assert stats['nonmanifold_edges']==stats['loose_vertices']==stats['zero_area_faces']==0
 (out/'validation.json').write_text(json.dumps(stats,indent=2));print('AUDIT_OK',item['index'],stats['triangles'],flush=True)
 if item['index']!=18:
  notes={12:'One curved solid boomerang. Cream bands and triangle motifs are closed shallow relief. The unseen back repeats the front decoration.',13:'One reusable kunai, following the revised user request rather than the three-item reference composition. Faceted blade, ivory spiral grip and genuinely open octagonal ring form one asset. The reverse blade is mirrored.',14:'One green bottle with an amber liquid-colored region, folded cloth and thick stylized flame geometry. Glass is intentionally opaque and flames use portable colors rather than alpha/transmission/emission. Unseen bottle surfaces and cloth folds are inferred.',15:'One reusable egg, following the revised user request rather than the three-egg reference composition. A closed faceted shell has broad tan patches baked into its cream base-color map. Unseen patch placement is inferred.',16:'One thick steak with a pale fat border, irregular red meat facets and unified branched bone shape. The unseen underside is plain and conservatively inferred.'}
  (out/'README.md').write_text('# '+item['name']+'\n\n'+notes[item['index']]+'\n\nModel.blend contains editable geometry with named component vertex groups and a packed base-color atlas. Model.fbx and Model.glb contain geometry only with embedded texture. Preview.png and Alternate.png are actual Blender renders. Reference.png is an unchanged copy of the supplied image. Review cameras, lights and floor remain in a separate non-exported collection.\n\nReproduce from the repository root with:\n\n```powershell\n& "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --threads 4 --python roguelite-planning/weapon-models/batches/throwables/build_throwables.py -- '+str(item['index'])+'\n```\n\nThe shared helper base.py is copied into the same batch directory. audit.py verifies packed textures, unchanged reference hashes, closed topology, triangle counts and FBX/GLB reimports. See validation.json for measured results. Separate assembled pieces intentionally overlap. No rigging, gameplay, or Roblox/Studio import testing is claimed.\n')

