import bpy,bmesh,math,json,sys,shutil
from pathlib import Path
from mathutils import Vector,Quaternion,Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_utility as build
ROOT=Path(__file__).resolve().parents[2]
def asset_obs():return [o for o in bpy.context.scene.objects if o.type=='MESH' and any('export geometry' in c.name for c in o.users_collection)]
def select(obs):
 bpy.ops.object.select_all(action='DESELECT')
 for o in obs:o.select_set(True)
 bpy.context.view_layer.objects.active=obs[0]
def export(out,obs,rig=False):
 select(obs)
 bpy.ops.export_scene.fbx(filepath=str(out/'Model.fbx'),use_selection=True,object_types={'MESH','ARMATURE'} if rig else {'MESH'},bake_anim=False,add_leaf_bones=False,use_armature_deform_only=True,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
 bpy.ops.export_scene.gltf(filepath=str(out/'Model.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_skins=True,export_animations=False)
def clear_scene():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
def evaluated_points(o):
 deps=bpy.context.evaluated_depsgraph_get();ob=o.evaluated_get(deps);me=ob.to_mesh();pts=[ob.matrix_world@v.co for v in me.vertices];ob.to_mesh_clear();return pts
def measure_weights(mesh,rig):
 bones={b.name for b in rig.data.bones};groups={g.index:g.name for g in mesh.vertex_groups};bad=[];assign={name:[] for name in bones}
 for v in mesh.data.vertices:
  weights=[(groups[g.group],g.weight) for g in v.groups if groups[g.group] in bones and g.weight>1e-8]
  if len(weights)!=1 or abs(sum(w for n,w in weights)-1)>1e-6:bad.append(v.index)
  for n,w in weights:assign[n].append(v.index)
 return {'fully_rigid_vertices':len(mesh.data.vertices)-len(bad),'vertex_count':len(mesh.data.vertices),'bad_weight_vertices':bad,'per_bone_vertices':{k:len(v) for k,v in assign.items()}},assign
def posecheck(mesh,rig):
 for b in rig.pose.bones:b.rotation_mode='QUATERNION';b.rotation_quaternion=Quaternion()
 bpy.context.view_layer.update();rest=evaluated_points(mesh);weights,assign=measure_weights(mesh,rig)
 rig.pose.bones['Chain_01'].rotation_quaternion=Quaternion((0,0,1),-.26)
 rig.pose.bones['Chain_03'].rotation_quaternion=Quaternion((1,0,0),.18)
 rig.pose.bones['Chain_05'].rotation_quaternion=Quaternion((0,0,1),.15)
 bpy.context.view_layer.update();posed=evaluated_points(mesh);errors={};displacements={}
 for name,ids in assign.items():
  if not ids:continue
  a=ids[0];pairs=[(a,j) for j in ids[1:]]+[(ids[i],ids[i+1]) for i in range(len(ids)-1)]
  errors[name]=max((abs((rest[a]-rest[b]).length-(posed[a]-posed[b]).length) for a,b in pairs),default=0)
  displacements[name]=max((rest[i]-posed[i]).length for i in ids)
 joints={b.name:(b.head-b.parent.tail).length for b in rig.pose.bones if b.parent}
 result={'weights':weights,'max_per_bone_rigidity_error':errors,'max_per_bone_vertex_displacement':displacements,'fixed_handle_max_displacement':displacements.get('Handle_ROOT'),'payload_displacement':displacements.get('Weight_END'),'joint_anchor_gaps':joints,'test_pose_radians':{'Chain_01_localZ':-.26,'Chain_03_localX':.18,'Chain_05_localZ':.15}}
 return result,rest

def wrecking():
 out=ROOT/'assets'/'25-wrecking-ball';bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));scene=bpy.context.scene;obs=asset_obs();col=obs[0].users_collection[0];assignments={};parts={}
 for o in obs:
  if o.name.startswith('Heavy interlocked chain '):bone='Chain_'+str(7-int(o.name.rsplit(' ',1)[-1])).zfill(2)
  elif 'wrecking ball' in o.name or 'Ball top chain socket' in o.name:bone='Weight_END'
  else:bone='Handle_ROOT'
  vg=o.vertex_groups.get(bone) or o.vertex_groups.new(name=bone);vg.add(list(range(len(o.data.vertices))),1,'REPLACE');pg=o.vertex_groups.new(name='Part | '+o.name);pg.add(list(range(len(o.data.vertices))),1,'REPLACE');assignments[o.name]=bone
 select(obs);bpy.ops.object.join();mesh=bpy.context.object;mesh.name='WreckingBall_Skinned';scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
 arm=bpy.data.armatures.new('WreckingBall_Rig');rig=bpy.data.objects.new('WreckingBall_Rig',arm);col.objects.link(rig);rig.show_in_front=True;select([rig]);bpy.ops.object.mode_set(mode='EDIT')
 centers=[Vector((x,0,z)) for x,z in [(.66,3.04),(.40,3.16),(.10,3.08),(-.17,2.83),(-.42,2.58),(-.65,2.30),(-.86,2.02)]]
 anchors=[Vector((.68,0,2.95))]+[(a+b)*.5 for a,b in zip(centers,centers[1:])]+[Vector((-.96,0,1.93))]
 root=arm.edit_bones.new('Handle_ROOT');root.head=(1.07,0,2);root.tail=anchors[0];last=root
 for i in range(7):
  b=arm.edit_bones.new('Chain_'+str(i+1).zfill(2));b.head=anchors[i];b.tail=anchors[i+1];b.parent=last;b.use_connect=False;last=b
 b=arm.edit_bones.new('Weight_END');b.head=anchors[-1];b.tail=(-.96,0,.93);b.parent=last;b.use_connect=False
 bpy.ops.object.mode_set(mode='OBJECT');mod=mesh.modifiers.new('Rigid per-link skin','ARMATURE');mod.object=rig;mesh.parent=rig;mesh.matrix_parent_inverse=rig.matrix_world.inverted()
 for a in list(bpy.data.actions):bpy.data.actions.remove(a)
 result,rest=posecheck(mesh,rig);scene.camera.data.ortho_scale=5.1;scene.render.filepath=str(out/'Rig_Pose_Check.png');scene.cycles.samples=24;bpy.ops.render.render(write_still=True)
 for b in rig.pose.bones:b.rotation_quaternion=Quaternion()
 bpy.context.view_layer.update();restored=evaluated_points(mesh);result['rest_restore_max_vertex_error']=max((a-b).length for a,b in zip(rest,restored));result['hierarchy']=[{'bone':b.name,'parent':b.parent.name if b.parent else None,'head_armature_space':list(b.head_local),'tail_armature_space':list(b.tail_local),'deform':b.use_deform} for b in arm.bones];result['part_assignments']=assignments;result['animation_actions']=len(bpy.data.actions);result['animation_data_present']=bool(rig.animation_data);result['constraints']=sum(len(b.constraints) for b in rig.pose.bones)
 scene.camera.data.ortho_scale=4.6;scene.render.filepath=str(out/'Preview.png');export(out,[mesh,rig],True);select([rig]);bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
 st=build.stats([mesh]);st.update(index=25,name='Wrecking Ball',armatures=1,bones=len(arm.bones),notes='Rigid skinned assembly; each closed chain link has weight1 to one bone. Handle_ROOT is fixed when child links pose. No animation Actions or clips. No Studio import tested.')
 for ext in ['fbx','glb']:
  clear_scene()
  if ext=='fbx':bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
  else:bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
  rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];im=meshes[0];ir=rigs[0];check,_=posecheck(im,ir);check['armature_count']=len(rigs);check['mesh_count']=len(meshes);check['bone_names']=[b.name for b in ir.data.bones];check['armature_modifiers']=[m.object.name for m in im.modifiers if m.type=='ARMATURE'];check['animation_actions']=len(bpy.data.actions);check['unexpected_stage_objects']=[o.name for o in bpy.context.scene.objects if o.type not in ['MESH','ARMATURE']];check['geometry']=build.stats(meshes,ext=='glb');result[ext+'_roundtrip']=check;st[ext+'_reimport']=check['geometry']
 (out/'rig_validation.json').write_text(json.dumps(result,indent=2));(out/'validation.json').write_text(json.dumps(st,indent=2));(out/'README.md').write_text('# Wrecking Ball — rigid swing rig\n\nModel.blend, FBX and GLB contain one skinned mesh and the WreckingBall_Rig armature. Handle_ROOT holds the wooden stick; Chain_01 through Chain_07 run from the held end toward Weight_END (ball and socket). Each vertex has exactly one deform bone at weight 1.0, so every link stays rigid. Original part vertex groups remain for editing. Bone heads lie at connection anchors; chain hierarchy moves the downstream ball while the handle stays fixed.\n\nNo Actions, keyframes, animation clips, constraints or automatic swinging are included. Preview/Alternate show the unchanged rest geometry; Rig_Pose_Check.png is a temporary pose diagnostic, restored before saving/export. rig_validation.json records measured root stability, rigid distances, joint anchors, weights and fresh FBX/GLB skin roundtrips.\n\nExports contain only mesh+armature, no staging or leaf bones. Packed color atlas retained. No Studio edits or import tests. Hidden surfaces remain inferred; rigid components overlap at mechanical joints. Rebuild revision: Blender 5.2 --background --threads 4 --python ../../batches/juggler_utility/revise_motion.py -- wrecking. Run from the original static model when rebuilding rig.\n');print('RIG_COMPLETE',json.dumps(result),flush=True)
def yoyo():
 out=ROOT/'assets'/'21-yo-yo';bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));scene=bpy.context.scene;obs=asset_obs();removed=[]
 for o in list(obs):
  if 'cord strand' in o.name.lower():removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
 obs=asset_obs();sets={'FingerRing':[o for o in obs if 'finger loop' in o.name.lower() or 'cord end clamp' in o.name.lower()]};sets['YoYo']=[o for o in obs if o not in sets['FingerRing']];pivots={'YoYo':(-.55,0,1.1),'FingerRing':(1.43,-.96,.15)};joined={}
 for label,parts in sets.items():
  for o in parts:
   pg=o.vertex_groups.new(name='Part | '+o.name);pg.add(list(range(len(o.data.vertices))),1,'REPLACE')
  select(parts);bpy.ops.object.join();o=bpy.context.object;o.name=label;o.parent=None;scene.cursor.location=pivots[label];bpy.ops.object.origin_set(type='ORIGIN_CURSOR');joined[label]=o
 markers=bpy.data.collections.new('ATTACHMENT GUIDES | never exported');scene.collection.children.link(markers);attachment={}
 for name,label,local,axis in [('String_Axle','YoYo',(0,0,0),(0,1,0)),('String_Hand','FingerRing',(.37,.35,0),(1,1,0))]:
  e=bpy.data.objects.new(name,None);markers.objects.link(e);e.empty_display_type='ARROWS';e.empty_display_size=.16;e.parent=joined[label];e.location=local;e.rotation_mode='QUATERNION';e.rotation_quaternion=Vector(axis).to_track_quat('Z','Y');e.hide_render=True
  attachment[name]={'parent_mesh':label,'local_position_blender_xyz':list(e.location),'local_rotation_quaternion_wxyz':list(e.rotation_quaternion),'local_rotation_degrees_xyz':[math.degrees(a) for a in e.rotation_quaternion.to_euler()],'local_axis_Z':list(Vector(axis).normalized()),'world_position_blender_xyz':list(Vector(pivots[label])+Vector(local))}
 attachment['coordinate_system']='Blender right-handed XYZ; Z up. Values are relative to each named mesh origin. Standalone components use the same local marker coordinates. Convert coordinates with the import basis before making Studio Attachments; do not copy Blender XYZ blindly.'
 attachment['string_strategy']='No baked cord. Later create a Beam between Attachments named String_Hand and String_Axle for a visual line; adjust Beam curves for slack and move attachments for extension. A separate optional RopeConstraint can later enforce physical maximum length. No gameplay, animation, Beam or constraint created in this asset task.'
 (out/'attachment_points.json').write_text(json.dumps(attachment,indent=2))
 for label,o in joined.items():
  cs=bpy.data.scenes.new(label+'_Standalone');bpy.context.window.scene=cs;c=o.copy();c.data=o.data.copy();c.parent=None;c.location=(0,0,0);cs.collection.objects.link(c);dest=out/'components'/label;dest.mkdir(parents=True,exist_ok=True);shutil.copyfile(out/'BaseColor.png',dest/'BaseColor.png');export(dest,[c]);bpy.data.libraries.write(str(dest/'Model.blend'),{cs},fake_user=True);(dest/'README.md').write_text(label+' independent single mesh, no parent and no static cord. Pivot at '+('spool center' if label=='YoYo' else 'finger loop center')+'. Packed texture. Attachment local coordinates documented in ../../attachment_points.json.\n');bpy.context.window.scene=scene;bpy.data.objects.remove(c,do_unlink=True);bpy.data.scenes.remove(cs)
 export(out,list(joined.values()));select(list(joined.values()));scene.cycles.samples=24;cam=scene.camera;loc=cam.location.copy();target=(.30,-.15,1);scene.render.filepath=str(out/'Preview.png');bpy.ops.render.render(write_still=True);cam.location=(-loc.x,-loc.y,loc.z);build.aim(cam,target);scene.render.filepath=str(out/'Alternate.png');bpy.ops.render.render(write_still=True);cam.location=loc;build.aim(cam,target);scene.render.filepath=str(out/'Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
 st=build.stats(list(joined.values()));st.update(index=21,name='Yo-Yo',notes='Two independent unparented meshes: YoYo and FingerRing. Static cord removed. Named attachment Empty guides are only in Blender, never exports. No rig, physics or animation.',removed_cord_objects=removed,attachment_markers=list(attachment)[:2],components={})
 for label in ['YoYo','FingerRing']:
  dest=out/'components'/label;checks={}
  for ext in ['blend','fbx','glb']:
   if ext=='blend':bpy.ops.wm.open_mainfile(filepath=str(dest/'Model.blend'))
   else:
    clear_scene()
    if ext=='fbx':bpy.ops.import_scene.fbx(filepath=str(dest/'Model.fbx'))
    else:bpy.ops.import_scene.gltf(filepath=str(dest/'Model.glb'))
   meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];d=build.stats(meshes,ext=='glb');d['parents']=[o.parent.name if o.parent else None for o in meshes];d['origins']=[list(o.location) for o in meshes];d['unexpected_objects']=[o.name for o in bpy.context.scene.objects if o.type!='MESH'];checks[ext]=d
  st['components'][label]=checks;(dest/'validation.json').write_text(json.dumps(checks,indent=2))
 for ext in ['fbx','glb']:
  clear_scene()
  if ext=='fbx':bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
  else:bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
  meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];d=build.stats(meshes,ext=='glb');d['parents']=[o.parent.name if o.parent else None for o in meshes];d['unexpected_objects']=[o.name for o in bpy.context.scene.objects if o.type!='MESH'];st[ext+'_reimport']=d
 (out/'validation.json').write_text(json.dumps(st,indent=2));(out/'README.md').write_text('# Yo-Yo — dynamic-string preparation\n\nThe baked static cord is removed. Model.blend and root FBX/GLB contain two independent unparented meshes: YoYo (spool/body center pivot) and FingerRing (finger loop center pivot, including the red connector). Use components/YoYo/Model.blend, Model.fbx or Model.glb for the body alone; components/FingerRing provides the same three standalone files for the hand piece. Each standalone file has exactly one unparented mesh at the origin, with a packed/embedded atlas.\n\nThe Blender-only attachment guide collection contains String_Axle and String_Hand Empty markers parented to their respective mesh. attachment_points.json records local positions, orientations and coordinate conventions. They are excluded from FBX/GLB. Later in Studio, a Beam between corresponding Attachments can display a taut/slack/extending string; an optional RopeConstraint can impose a physical maximum length. No Beam, constraint, gameplay, rig or animation is created here.\n\nPreview and Alternate are real Blender renders. Source reference unchanged. Intentional component intersections and palette UV overlap retained; back geometry inferred from the source. No Studio changes or import testing. Revision script: ../../batches/juggler_utility/revise_motion.py -- yoyo; start from original static model to rebuild.\n');print('YOYO_COMPLETE',json.dumps(st),flush=True)
if __name__=='__main__':
 args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['wrecking','yoyo']
 if 'wrecking' in args:wrecking()
 if 'yoyo' in args:yoyo()

