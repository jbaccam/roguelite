"""Verify that contact skin follows the same hand transform as the dagger."""
import bpy,json,sys,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;out=ROOT/'fire-goblin'
bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'))
rig=bpy.data.objects['Rig'];body=next(o for o in bpy.context.scene.objects if o.get('smooth_skin'))
meta=json.loads((out/'anatomy.json').read_text());g=meta['grips'][0];c=Vector(g['center']);axis=Vector(g['axis'])
contact=[]
for v in body.data.vertices:
    offset=v.co-c;along=offset.dot(axis);radial=(offset-axis*along).length
    if abs(along)<.27 and radial<.20:contact.append(v.index)
assert len(contact)>25
for track in rig.animation_data.nla_tracks:track.mute=True
rest=rig.data.bones['RightHand'].matrix_local.inverted();scene=bpy.context.scene;report={'contactVertices':len(contact),'clips':{}}
for name in ['Idle','Move','Attack','Hit','Death']:
    action=bpy.data.actions.get(name) or next(a for a in bpy.data.actions if a.name.endswith(name))
    rig.animation_data.action=action
    if action.slots:rig.animation_data.action_slot=action.slots[0]
    max_error=0
    for frame in range(int(action.frame_range[0]),int(action.frame_range[1])+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        obj=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=obj.to_mesh()
        transform=rig.matrix_world@rig.pose.bones['RightHand'].matrix@rest@rig.matrix_world.inverted()
        for i in contact:
            expected=transform@body.matrix_world@body.data.vertices[i].co
            actual=obj.matrix_world@me.vertices[i].co
            max_error=max(max_error,(expected-actual).length)
        obj.to_mesh_clear()
    report['clips'][name]={'frames':list(action.frame_range),'maxContactSkinDeviation':max_error}
report['passed']=all(c['maxContactSkinDeviation']<.0001 for c in report['clips'].values())
report['sha256']={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['Model.blend','Model.fbx','Model.glb']}
(out/'GripMotionChecks.json').write_text(json.dumps(report,indent=2))
print('GRIP_MOTION',json.dumps(report),flush=True)
assert report['passed'],report
