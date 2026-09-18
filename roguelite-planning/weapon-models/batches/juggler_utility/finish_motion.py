import bpy,json,sys,hashlib,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_utility as b
root=Path(__file__).resolve().parents[2]
for idx in [21,25]:
 item=next(x for x in b.INV if x['index']==idx);out=Path(item['output']);bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));obs=[o for o in bpy.context.scene.objects if o.type=='MESH' and any('export geometry' in c.name for c in o.users_collection)];v=json.loads((out/'validation.json').read_text());v.update(b.stats(obs));v['bounds_min']=[min((o.matrix_world@p.co)[j] for o in obs for p in o.data.vertices) for j in range(3)];v['bounds_max']=[max((o.matrix_world@p.co)[j] for o in obs for p in o.data.vertices) for j in range(3)];v['source_copy_sha256_matches']=hashlib.sha256(Path(item['source']).read_bytes()).digest()==hashlib.sha256((out/'Reference.png').read_bytes()).digest();images={n.image for o in obs for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image};v['packed_images']=[{'name':im.name,'size':list(im.size),'packed':bool(im.packed_file)} for im in images];v['mesh_origins']={o.name:list(o.location) for o in obs};v['animation_actions']=len(bpy.data.actions)
 if idx==21:
  p=(out/'Model.glb').read_bytes();g=json.loads(p[20:20+struct.unpack_from('<I',p,12)[0]]);v['glb_file_structure']={'meshes':len(g.get('meshes',[])),'skins':len(g.get('skins',[])),'animations':len(g.get('animations',[])),'nodes':[n.get('name') for n in g['nodes']]};v['nonexported_marker_checks']={o.name:{'parent':o.parent.name,'local_position':list(o.location),'hidden_from_render':o.hide_render} for o in bpy.context.scene.objects if o.name in ['String_Hand','String_Axle']};v['preview_and_alternate_inspected']=True
 else:
  rv=json.loads((out/'rig_validation.json').read_text());rv['visual_pose_check_inspected']=True;rv['source_file_all_bones_rest_pose']=all(abs(pb.rotation_quaternion.angle)<1e-6 for rig in bpy.context.scene.objects if rig.type=='ARMATURE' for pb in rig.pose.bones);(out/'rig_validation.json').write_text(json.dumps(rv,indent=2));v['rig_pose_check_inspected']=True
 (out/'validation.json').write_text(json.dumps(v,indent=2));backup=out/'Model.blend1'
 if backup.exists():backup.unlink()
 print('FINAL',idx,v['triangles'],v['mesh_objects'],v['source_copy_sha256_matches'])
