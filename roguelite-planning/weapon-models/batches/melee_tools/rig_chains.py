"""Rigid per-link FK rigs. No actions, animation clips, physics, or hidden constraints."""
import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector,Quaternion
ROOT=Path(__file__).resolve().parents[2]
INV=json.loads((ROOT/'inventory.json').read_text())

def evaluated_world(o):
 bpy.context.view_layer.update();e=o.evaluated_get(bpy.context.evaluated_depsgraph_get());return [o.matrix_world@v.co for v in e.data.vertices]
def reset(r):
 for p in r.pose.bones:p.matrix_basis.identity()
 bpy.context.view_layer.update()
def pose(r,variant):
 reset(r);chain=[p for p in r.pose.bones if p.name.startswith('Chain_')]
 for i,p in enumerate(chain):
  if variant==0:ang=math.radians(-13 if i==0 else (3 if i%2 else -2));axis=Vector((0,1,0))
  elif variant==1:ang=math.radians(9 if i==0 else (-3 if i%2 else 2));axis=Vector((1,0,0))
  else:ang=math.radians(-8 if i==0 else (2 if i%2 else -1));axis=Vector((0,0,1))
  p.rotation_mode='QUATERNION';local=p.bone.matrix_local.to_3x3().inverted()@axis;p.rotation_quaternion=Quaternion(local,ang)
 bpy.context.view_layer.update()
def junction_error(r):
 errors=[]
 for p in r.pose.bones:
  if p.parent:
   head=p.bone.head_local;parent_transform=p.parent.matrix@p.parent.bone.matrix_local.inverted();errors.append((parent_transform@head-p.matrix.translation).length)
 return max(errors,default=0)
def rig_tests(mesh,rig,weights):
 reset(rig);base=evaluated_world(mesh);root_ids=weights['Handle_ROOT'];terminal=next(n for n in weights if n.endswith('_END'));tests=[]
 for variant in range(3):
  pose(rig,variant);after=evaluated_world(mesh);rigid_error=0
  for name,ids in weights.items():
   anchor=ids[0]
   rigid_error=max(rigid_error,max(abs((base[i]-base[anchor]).length-(after[i]-after[anchor]).length) for i in ids))
  root_move=max((after[i]-base[i]).length for i in root_ids);end_move=max((after[i]-base[i]).length for i in weights[terminal]);joint_error=junction_error(rig)
  tests.append({'test':variant,'maximum_rigid_distance_error':rigid_error,'fixed_handle_max_displacement':root_move,'terminal_max_displacement':end_move,'joint_anchor_coincidence_error':joint_error,'passed':rigid_error<1e-4 and root_move<1e-4 and end_move>.01 and joint_error<1e-4})
 reset(rig);return tests
def roundtrip(out,ext,expected_bones,expected_triangles):
 for existing in list(bpy.context.scene.objects):bpy.data.objects.remove(existing,do_unlink=True)
 if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
 else:bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
 rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];helpers={p.custom_shape for r in rigs for p in r.pose.bones if p.custom_shape};meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o not in helpers];assert len(meshes)==len(rigs)==1,[(o.name,o.type) for o in bpy.context.scene.objects]
 m=meshes[0];r=rigs[0];bones={b.name for b in r.data.bones};assert bones==set(expected_bones),(ext,bones,expected_bones)
 weights={n:[] for n in bones};bad=0
 for v in m.data.vertices:
  deform=[(m.vertex_groups[g.group].name,g.weight) for g in v.groups if m.vertex_groups[g.group].name in bones and g.weight>1e-6]
  if len(deform)!=1 or abs(sum(w for _,w in deform)-1)>1e-6:bad+=1
  for n,w in deform:weights[n].append(v.index)
 tris=sum(len(p.vertices)-2 for p in m.data.polygons);tests=rig_tests(m,r,weights)
 result={'mesh_objects':len(meshes),'armature_objects':len(rigs),'bone_count':len(bones),'bones':sorted(bones),'invalid_deform_vertices':bad,'triangles':tris,'expected_triangles':expected_triangles,'armature_modifier_present':any(mod.type=='ARMATURE' and mod.object==r for mod in m.modifiers),'texture_present':any(n.type=='TEX_IMAGE' and n.image for mat in m.data.materials if mat and mat.use_nodes for n in mat.node_tree.nodes),'actions':len(bpy.data.actions),'unexpected_camera_or_light':sum(o.type in {'CAMERA','LIGHT'} for o in bpy.context.scene.objects),'pose_tests':tests}
 result['importer_only_bone_display_helpers']=[o.name for o in helpers]
 result['passed']=bad==0 and tris==expected_triangles and all(t['passed'] for t in tests) and result['armature_modifier_present'] and result['texture_present'] and result['actions']==0
 assert result['passed'],result
 return result
def run(index):
 item=next(x for x in INV if x['index']==index);out=Path(item['output']);bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));scene=bpy.context.scene
 mesh=next(o for o in scene.objects if o.type=='MESH' and o.vertex_groups and 'Review' not in o.name)
 for oldrig in [o for o in scene.objects if o.type=='ARMATURE']:
  reset(oldrig);world=mesh.matrix_world.copy();mesh.parent=None;mesh.matrix_world=world
  for mod in list(mesh.modifiers):
   if mod.type=='ARMATURE':mesh.modifiers.remove(mod)
  for bone in oldrig.data.bones:
   if mesh.vertex_groups.get(bone.name):mesh.vertex_groups.remove(mesh.vertex_groups[bone.name])
  bpy.data.objects.remove(oldrig,do_unlink=True)
 original=[mesh.matrix_world@v.co for v in mesh.data.vertices];source_groups={}
 for g in mesh.vertex_groups:
  ids=[v.index for v in mesh.data.vertices if any(a.group==g.index and a.weight>.9 for a in v.groups)]
  if ids:source_groups[g.name]=ids
 centers={n:sum((original[i] for i in ids),Vector())/len(ids) for n,ids in source_groups.items()}
 root=Vector(mesh.location);parts={};heads={};parent={};bones=[]
 if index==2:
  chain_names=['Interlocked chain link '+str(i) for i in reversed(range(5))]
  roots=[n for n,c in centers.items() if n not in chain_names and c.x>0]
  terminals=[n for n,c in centers.items() if n not in chain_names and c.x<0]
  start_eye=centers['Terminal chain eye.001'];end_eye=centers['Terminal chain eye'];terminal_name='Baton_END'
  terminal_tail=Vector((-.708,0,1.19))
 else:
  chain_names=['Sickle interlocked chain '+str(i) for i in range(11)]
  terminals=['Weight attachment collar','Beveled twelve-facet iron chain weight'];roots=[n for n in centers if n not in chain_names+terminals]
  # Held sickle's bottom ferrule meets the first chain eye at this anchor.
  start_eye=Vector((-.5,0,1.11));end_eye=Vector((1.91,0,.88));terminal_name='Weight_END';terminal_tail=centers[terminals[-1]]
 parts['Handle_ROOT']=roots;heads['Handle_ROOT']=root;parent['Handle_ROOT']=None;bones.append('Handle_ROOT')
 previous='Handle_ROOT'
 for i,part in enumerate(chain_names):
  n='Chain_%02d'%(i+1);parts[n]=[part];heads[n]=(centers[part]+(start_eye if i==0 else centers[chain_names[i-1]]))/2;parent[n]=previous;bones.append(n);previous=n
 parts[terminal_name]=terminals;heads[terminal_name]=(centers[chain_names[-1]]+end_eye)/2;parent[terminal_name]=previous;bones.append(terminal_name)
 weights={n:sorted(set(i for part in pieces for i in source_groups[part])) for n,pieces in parts.items()};flat=[i for ids in weights.values() for i in ids];assert len(flat)==len(set(flat))==len(mesh.data.vertices)
 # Armature origin equals the existing handhold. Rest bone coordinates are armature-local.
 ad=bpy.data.armatures.new(item['name']+'_Skeleton');rig=bpy.data.objects.new(item['name'].replace(' ','_')+'_Rig',ad);mesh.users_collection[0].objects.link(rig);rig.location=root;rig.show_in_front=True;ad.display_type='OCTAHEDRAL'
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
 for i,n in enumerate(bones):
  b=ad.edit_bones.new(n);b.head=heads[n]-root
  if n=='Handle_ROOT':b.tail=b.head+Vector((0,0,.38))
  elif n==terminal_name:b.tail=terminal_tail-root
  else:b.tail=heads[bones[i+1]]-root
  if (b.tail-b.head).length<.05:b.tail=b.head+Vector((0,0,.1))
  b.use_deform=True
  if parent[n]:b.parent=ad.edit_bones[parent[n]];b.use_connect=False
 bpy.ops.object.mode_set(mode='OBJECT')
 saved_world=mesh.matrix_world.copy();mesh.parent=rig;mesh.matrix_world=saved_world
 for n,ids in weights.items():g=mesh.vertex_groups.new(name=n);g.add(ids,1.0,'REPLACE')
 modifier=mesh.modifiers.new('Rigid chain FK deformation','ARMATURE');modifier.object=rig;modifier.use_deform_preserve_volume=False
 for p in rig.pose.bones:
  p.rotation_mode='QUATERNION';p.lock_location=(True,True,True);p.lock_scale=(True,True,True)
 rig.pose.bones['Handle_ROOT'].lock_rotation=(True,True,True)
 rig['Controls']='Rotate Chain_01 onward in Pose Mode. Handle_ROOT stays fixed; animate whole prop with object transform. Terminal bone controls payload orientation. No actions.'
 mesh['rig_notes']='Each link and assembled payload has a single rigid deform weight. Original part vertex groups retained.'
 bpy.context.view_layer.update();rest=evaluated_world(mesh);rest_error=max((a-b).length for a,b in zip(original,rest));assert rest_error<1e-5,rest_error
 tests=rig_tests(mesh,rig,weights);assert all(t['passed'] for t in tests),tests
 # A posed still for review only; this is NOT an Action, clip, or keyframe.
 ground=next(o for o in scene.objects if o.name=='Review floor');oldground=ground.location.z;ground.location.z-=1
 pose(rig,0);oldpath=scene.render.filepath;scene.render.filepath=str(out/'Rig_Pose_Check.png');oldscale=scene.camera.data.ortho_scale;scene.camera.data.ortho_scale=oldscale*1.13;scene.cycles.samples=24;bpy.ops.render.render(write_still=True);reset(rig);scene.camera.data.ortho_scale=oldscale;scene.render.filepath=oldpath;ground.location.z=oldground
 for action in list(bpy.data.actions):bpy.data.actions.remove(action)
 bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
 bpy.ops.export_scene.fbx(filepath=str(out/'Model.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},use_armature_deform_only=True,add_leaf_bones=False,bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
 bpy.ops.export_scene.gltf(filepath=str(out/'Model.glb'),use_selection=True,export_format='GLB',export_skins=True,export_animations=False)
 rig_name=rig.name;triangles=sum(len(p.vertices)-2 for p in mesh.data.polygons)
 result={'name':item['name'],'rig_type':'Rigid FK linked chain; no IK, physics, constraints or animations','rest_geometry_max_error':rest_error,'bone_count':len(bones),'handhold_world':list(root),'hierarchy':[{'bone':n,'parent':parent[n],'head_world':list(heads[n]),'source_parts':parts[n],'rigid_vertices':len(weights[n])} for n in bones],'all_vertices_have_exactly_one_deform_bone':True,'deform_weight':1.0,'vertex_count':len(original),'triangles':triangles,'pose_tests':tests,'actions':0,'keyframes':0,'render':'Rig_Pose_Check.png is a temporary diagnostic pose, not a saved clip. Model.blend is saved in rest pose.','limitations':['No collision avoidance or chain physics solver; extreme rotations can interpenetrate.','Joint pivots maintain parent-child attachment; rigid interlocking meshes do not use stretchy blended weights.','Studio skeleton import and animation playback remain untested.']}
 result['glb_roundtrip']=roundtrip(out,'glb',bones,triangles);result['fbx_roundtrip']=roundtrip(out,'fbx',bones,triangles)
 (out/'rig_validation.json').write_text(json.dumps(result,indent=2))
 val=json.loads((out/'validation.json').read_text());val.update({'armature_objects':1,'bone_count':len(bones),'rig':'Rigid FK chain and terminal payload; one deform bone per vertex; no Actions/keyframes','rig_validation':'rig_validation.json','notes':'Reference geometry unchanged. Intentional assembled intersections. Studio import pending. Rigged FBX/GLB contain one mesh and one armature.'})
 for ext in ['glb','fbx']:
  val[ext+'_reimport'].update({'armature_objects':1,'bones':len(bones),'skeleton_and_skin_retained':True,'pose_deformation_verified':True,'unexpected_stage_objects':0})
 (out/'validation.json').write_text(json.dumps(val,indent=2))
 controls='# '+item['name']+' — rigid chain rig\n\nModel.blend contains the unchanged reference asset plus an exportable armature. BaseColor.png remains packed. Model.fbx and Model.glb include one mesh and one skeleton, with no lights, camera, floor, animation clips, Actions, keyframes, or FBX leaf bones. Preview.png and Alternate.png still show the unchanged rest model. Rig_Pose_Check.png is a temporary posed diagnostic still only.\n\nControls: select '+rig_name+', enter Pose Mode, and rotate `Chain_01` through `Chain_%02d` from the held end toward the moving end. `Handle_ROOT` is fixed at the handhold; move the entire armature object to place the weapon. `%s` rotates the terminal payload. Chain rotations move all downstream links and the payload. Translation/scale controls are locked to discourage opening joints or stretching links. Each whole link uses one weight of 1.0, with no blended-metal deformation.\n\n'%(len(chain_names),terminal_name)
 controls+='For nunchucks, the right baton in the reference rest pose is held, and the left baton is the terminal moving baton.\n\n' if index==2 else 'The sickle and its hand grip are held; the chain begins at its bottom ferrule and ends at the weight.\n\n'
 controls+='The FK rig supplies animation controls, not automatic swinging, physics, or collision avoidance. Avoid extreme rotations that make links intersect. Unseen surfaces are inferred from the reference. Original part vertex groups remain available. Geometry and color are preserved; rest and three temporary poses were numerically checked for rigid links, fixed held geometry, downstream motion and coincident joint anchors. Fresh FBX/GLB imports retained the complete skeleton and skin and passed pose-deformation checks. Studio import is still pending.\n\nReconstruction: ../../batches/melee_tools/build_melee.py; rig addition: ../../batches/melee_tools/rig_chains.py. Re-run rigging only on the unrigged build.\n'
 (out/'README.md').write_text(controls);print('RIG_COMPLETE',index,json.dumps(result),flush=True)
for index in [int(x) for x in sys.argv[sys.argv.index('--')+1:]] if '--' in sys.argv else [2,4]:run(index)

