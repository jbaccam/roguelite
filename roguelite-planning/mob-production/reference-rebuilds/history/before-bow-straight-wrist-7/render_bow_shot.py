"""Inspect actual exported-rig motion; animate a separate arrow for review only."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;out=ROOT/'bow-skeleton'
bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['Rig']
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=bpy.data.actions['Attack']
with bpy.data.libraries.load(str(out/'ArrowProjectile.blend'),link=False) as (source,target):target.objects=['ArrowProjectile']
arrow=target.objects[0];scene.collection.objects.link(arrow)
arrow.rotation_mode='QUATERNION'
restbow=Vector((-1.44,-.40,2.72));back=Vector((.55,.835,0)).normalized();right=Vector((back.y,-back.x,0))
def arrow_pose():
    left=rig.pose.bones['LeftHand'];transform=left.matrix@left.bone.matrix_local.inverted()
    upper=transform@(restbow+back*.42+Vector((0,0,1.5)))
    nock=rig.pose.bones['BowDraw'].head.lerp(upper,.22)
    # Nock above the drawing fingers; shaft passes above the bow hand and
    # beside the wooden stave, rather than through the grip or through wood.
    rest=transform@(restbow+right*.18+Vector((0,0,.34)))
    return nock,(rest-nock).normalized()
scene.frame_set(15);release,direction=arrow_pose()
samples=[];resthand=Vector((1.44,-.33,2.67))
string_mesh=next(o for o in scene.objects if o.type=='MESH' and o.vertex_groups.get('BowDraw') and any(any(g.group==o.vertex_groups['BowDraw'].index and g.weight>.99 for g in v.groups) for v in o.data.vertices))
string_indices=[v.index for v in string_mesh.data.vertices if any(g.group==string_mesh.vertex_groups['BowDraw'].index and g.weight>.99 for g in v.groups)]
for frame in range(1,26):
    scene.frame_set(frame)
    nock=rig.pose.bones['BowDraw'].head.copy()
    hand=rig.pose.bones['RightHand'];grip=hand.matrix@hand.bone.matrix_local.inverted()@resthand
    arrow_nock,arrow_direction=arrow_pose()
    arrow.location=arrow_nock if frame<=15 else release+direction*((frame-15)*.62)
    arrow.rotation_quaternion=Vector((0,-1,0)).rotation_difference(arrow_direction if frame<=15 else direction)
    arrow.hide_render=frame<7 or frame>24
    arrow.keyframe_insert('location',frame=frame);arrow.keyframe_insert('rotation_quaternion',frame=frame);arrow.keyframe_insert('hide_render',frame=frame)
    evaluated=string_mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    actual=sum((evaluated.matrix_world@evaluated.data.vertices[i].co for i in string_indices),Vector())/len(string_indices)
    assert (actual-nock).length<.002,'String mesh does not follow its draw bone'
    samples.append({'frame':frame,'nock':list(nock),'drawHand':list(grip),'handStringGap':(nock-grip).length,'meshNockGap':(actual-nock).length,'arrow':list(arrow.location)})
assert max(s['handStringGap'] for s in samples if 7<=s['frame']<=15)<.001,'String detached from drawing hand'
left=rig.pose.bones['LeftHand'];restnock=rig.pose.bones['BowDraw'].bone.head_local
scene.frame_set(13);full=rig.pose.bones['BowDraw'].head.copy();neutral=left.matrix@left.bone.matrix_local.inverted()@restnock
assert (full-neutral).length>.55,'Insufficient bow draw'
scene.frame_set(17);neutral=left.matrix@left.bone.matrix_local.inverted()@restnock
assert (rig.pose.bones['BowDraw'].head-neutral).length<.001,'String failed to return to brace'
(out/'ShootingChecks.json').write_text(json.dumps({'passed':True,'fps':24,'releaseFrame':15,'drawDistance':(full-neutral).length,'nockFractionAlongUpperString':.22,'arrowRestAboveGrip':.34,'arrowRestBesideStave':.18,'samples':samples,'scope':'Blender rig and projectile preview; no Roblox gameplay integration'},indent=2))
scene.frame_start=1;scene.frame_end=25;scene.render.fps=24
# A three-quarter side view makes the plane of the bow and the release visible.
camera=scene.camera;center=Vector((-.20,-.20,3.05));camera.location=center+Vector((1.45,-2.15,.60))*6
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=7.25
scene.render.resolution_x=680;scene.render.resolution_y=680;scene.cycles.samples=16
for frame,label in [(13,'FullDraw'),(16,'Release'),(17,'ArrowFlight')]:
    scene.frame_set(frame);scene.render.filepath=str(out/(label+'.png'));bpy.ops.render.render(write_still=True)
scene.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(out/'ShootingDemo.blend'))
scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=600;scene.render.resolution_y=600
frames=out/'shot-frames';frames.mkdir(exist_ok=True)
for frame in range(1,26):
    scene.frame_set(frame);scene.render.filepath=str(frames/f'{frame:03}.png');bpy.ops.render.render(write_still=True)
print('SHOT_PREVIEW_COMPLETE',flush=True)
