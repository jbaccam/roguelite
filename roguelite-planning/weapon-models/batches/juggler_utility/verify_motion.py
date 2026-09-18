import bpy,sys,json,struct,hashlib
from pathlib import Path
from mathutils import Quaternion,Vector,kdtree
sys.path.insert(0,str(Path(__file__).resolve().parent))
import revise_motion as r
out=r.ROOT/'assets'/'25-wrecking-ball'
# Capture original static geometry from the pre-rig Blender backup for an actual shape comparison.
bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend1'));original=[o.matrix_world@v.co for o in r.asset_obs() for v in o.data.vertices];original_armatures=sum(o.type=='ARMATURE' for o in bpy.context.scene.objects)
bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));scene=bpy.context.scene;rig=next(o for o in scene.objects if o.type=='ARMATURE');mesh=next(o for o in r.asset_obs());rest=r.evaluated_points(mesh);tree=kdtree.KDTree(len(original))
for i,p in enumerate(original):tree.insert(p,i)
tree.balance();deviation=max(tree.find(p)[2] for p in rest)
result=json.loads((out/'rig_validation.json').read_text());test,rest=r.posecheck(mesh,rig);result.update(test);result['static_source_shape_max_deviation']=deviation;result['static_source_armature_count']=original_armatures
# A temporary diagnostic floor follows the lowest posed point so it cannot clip the ball.
cam=scene.camera;oldscale=cam.data.ortho_scale;cam.data.ortho_scale=5.8;ground=next(o for o in scene.objects if o.type=='MESH' and o!=mesh);oldz=ground.location.z;ground.location.z=min(p.z for p in r.evaluated_points(mesh))-.04;scene.render.filepath=str(out/'Rig_Pose_Check.png');bpy.ops.render.render(write_still=True);ground.location.z=oldz;cam.data.ortho_scale=oldscale
for b in rig.pose.bones:b.rotation_quaternion=Quaternion()
bpy.context.view_layer.update();result['rest_restore_max_vertex_error']=max((a-b).length for a,b in zip(rest,r.evaluated_points(mesh)));scene.render.filepath=str(out/'Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
st=json.loads((out/'validation.json').read_text())
for ext in ['fbx','glb']:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 if ext=='fbx':bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
 else:bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
 rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];helpers={b.custom_shape for arm in rigs for b in arm.pose.bones if b.custom_shape};meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o not in helpers];check,_=r.posecheck(meshes[0],rigs[0]);check.update(armature_count=len(rigs),mesh_count=len(meshes),bone_names=[b.name for b in rigs[0].data.bones],armature_modifiers=[m.object.name for m in meshes[0].modifiers if m.type=='ARMATURE'],animation_actions=len(bpy.data.actions),importer_only_bone_display_helpers=[o.name for o in helpers],unexpected_stage_objects=[o.name for o in bpy.context.scene.objects if o.type not in ['MESH','ARMATURE']],geometry=r.build.stats(meshes,ext=='glb'));result[ext+'_roundtrip']=check;st[ext+'_reimport']=check['geometry']
p=(out/'Model.glb').read_bytes();gl=json.loads(p[20:20+struct.unpack_from('<I',p,12)[0]]);result['glb_file_structure']={'meshes':len(gl.get('meshes',[])),'skins':len(gl.get('skins',[])),'joints':len(gl['skins'][0]['joints']),'animations':len(gl.get('animations',[]))};result['visual_pose_check_inspected']=False
(out/'rig_validation.json').write_text(json.dumps(result,indent=2));(out/'validation.json').write_text(json.dumps(st,indent=2));print('RIG_CHECKS',json.dumps(result))
