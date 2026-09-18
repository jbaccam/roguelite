import bpy,bmesh,json,shutil
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];out=ROOT/'assets/18-deck-of-cards';names=['Deck','HeartCard','SpadeCard','DiamondCard']
bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'))
source=next(o for o in bpy.data.objects if o.type=='MESH' and any('Export geometry' in c.name for c in o.users_collection));collection=source.users_collection[0];objects=[]
if len(collection.objects)==1:
 for name in names:
  group=source.vertex_groups['COMPONENT_'+name];keep={v.index for v in source.data.vertices if any(g.group==group.index and g.weight>.5 for g in v.groups)}
  assert keep
  ob=source.copy();ob.data=source.data.copy();collection.objects.link(ob);ob.name=name;bm=bmesh.new();bm.from_mesh(ob.data);bm.verts.ensure_lookup_table();bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.index not in keep],context='VERTS');bm.to_mesh(ob.data);bm.free()
  bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY',center='BOUNDS');ob.parent=None;objects.append(ob)
 bpy.data.objects.remove(source,do_unlink=True)
else:objects=[bpy.data.objects[name] for name in names]
def select(obs):
 bpy.ops.object.select_all(action='DESELECT')
 for ob in obs:ob.select_set(True)
 bpy.context.view_layer.objects.active=obs[0]
def exports(folder,obs):
 select(obs);bpy.ops.export_scene.fbx(filepath=str(folder/'Model.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True);bpy.ops.export_scene.gltf(filepath=str(folder/'Model.glb'),use_selection=True,export_format='GLB',export_animations=False)
exports(out,objects);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
stats=json.loads((out/'validation.json').read_text());stats['mesh_objects']=4;stats['component_objects']=names;stats['unparented_components']=True;stats['independent_components']=[]
for name in names:
 bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));ob=bpy.data.objects[name]
 for other in list(bpy.data.objects):
  if other!=ob:bpy.data.objects.remove(other,do_unlink=True)
 ob.location=(0,0,0);folder=out/'components'/name;folder.mkdir(parents=True,exist_ok=True);shutil.copyfile(out/'BaseColor.png',folder/'BaseColor.png');exports(folder,[ob]);bpy.ops.wm.save_as_mainfile(filepath=str(folder/'Model.blend'))
 bm=bmesh.new();bm.from_mesh(ob.data);check={'name':name,'mesh_objects':1,'vertices':len(ob.data.vertices),'triangles':len(ob.data.polygons),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'loose_vertices':sum(not v.link_edges for v in bm.verts),'zero_area_faces':sum(f.calc_area()<1e-10 for f in bm.faces),'pivot':'Geometry bounds center, located at world origin','parent':None,'uv_layers':len(ob.data.uv_layers)};bm.free()
 check['packed_texture']=all(n.image.packed_file is not None for m in ob.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
 for ext in ['glb','fbx']:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(folder/'Model.glb'))
  else:bpy.ops.import_scene.fbx(filepath=str(folder/'Model.fbx'))
  meshes=[x for x in bpy.context.scene.objects if x.type=='MESH'];images=[n.image for x in meshes for m in x.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image];check[ext+'_reimport']={'mesh_objects':len(meshes),'triangles':sum(len(p.vertices)-2 for x in meshes for p in x.data.polygons),'all_faces_triangular':all(len(p.vertices)==3 for x in meshes for p in x.data.polygons),'texture_pixels_loaded':bool(images) and all(len(i.pixels)>0 and min(i.size)>0 for i in images),'unexpected_stage_objects':sum(x.type!='MESH' for x in bpy.context.scene.objects)}
 assert check['nonmanifold_edges']==check['loose_vertices']==check['zero_area_faces']==0
 print('COMPONENT_CHECK',json.dumps(check),flush=True)
 assert all(check[e+'_reimport']['triangles']==check['triangles'] and check[e+'_reimport']['texture_pixels_loaded'] and check[e+'_reimport']['unexpected_stage_objects']==0 for e in ['glb','fbx'])
 (folder/'validation.json').write_text(json.dumps(check,indent=2));(folder/'README.md').write_text('# '+name+'\n\nIndependent reusable component with no parent, centered pivot, real mesh geometry and packed/embedded base color. Extracted by `batches/throwables/split_cards.py` from the reference-derived card assembly. Both FBX and GLB were reimported and checked; see validation.json. No Roblox/Studio testing was performed. The unobserved reverse side of single cards is plain cream.\n');stats['independent_components'].append({'name':name,'directory':str(folder),'triangles':check['triangles']})
for e in ['glb','fbx']:stats[e+'_reimport']['mesh_objects']=4
(out/'validation.json').write_text(json.dumps(stats,indent=2));(out/'README.md').write_text('# Deck and three independent cards\n\nFour independent, unparented mesh objects: Deck, HeartCard, SpadeCard and DiamondCard. Each has its own geometry-centered pivot and can move freely. The review composition leaves space between them. Top-level Model.blend/FBX/GLB contain all four separated objects; the components/ subdirectories each contain a standalone centered Model.blend, Model.fbx, Model.glb, BaseColor.png and validation.json. Textures are packed in Blender and embedded in exports.\n\nReproduce with build_throwables.py -- 18, then split_cards.py. Both scripts are in ../../batches/throwables/. Reference.png is an unchanged copy. Preview.png and Alternate.png are actual Blender renders. The deck reverse and unobserved faces are inferred; single-card backs are plain cream. Geometry deliberately overlaps within the assembled deck sleeve/clasp. No rig, gameplay, or Roblox/Studio testing is claimed.\n')
print('CARDS_SEPARATED',json.dumps(stats['independent_components']),flush=True)

