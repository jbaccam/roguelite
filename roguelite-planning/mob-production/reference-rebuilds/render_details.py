import bpy,sys,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
args=sys.argv[sys.argv.index('--')+1:]
only=next((a.split('=',1)[1] for a in args if a.startswith('--detail=')),None)
for mob in [a for a in args if not a.startswith('--')]:
    out=ROOT/mob;bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'));scene=bpy.context.scene;rig=bpy.data.objects['Rig']
    rig.animation_data.action=None
    for track in rig.animation_data.nla_tracks:track.mute=True
    for p in rig.pose.bones:p.location=(0,0,0);p.rotation_quaternion=(1,0,0,0);p.scale=(1,1,1)
    data=json.loads((out/'anatomy.json').read_text());details=[(g['bone']+'Grip',g['center'],1.30) for g in data.get('grips',[])]
    if mob=='rock-throwing-crab':details=[('RockGrip',data['rockContact']['rockCenter'],1.65)]
    if mob=='bow-skeleton':details.append(('RightHandGrip',(1.44,-.33,2.67),1.30))
    if mob=='bow-skeleton':details.append(('BowStringDetail',(-1.44,-.40,2.72),3.50))
    if mob=='fire-goblin':
        details.append(('RightHandPalmGrip',data['grips'][0]['center'],1.50))
        details.append(('RightHandSideGrip',data['grips'][0]['center'],1.50))
        details.append(('LeftHandGrip',(-1.50,-.22,2.08),1.50))
        details.append(('LeftHandPalmGrip',(-1.50,-.22,2.08),1.50))
        details.append(('DaggerDetail',(2.01,-.39,1.87),2.40))
        details.append(('HandsDetail',(.46,-.14,2.14),5.10))
    if mob=='obsidian-ogre':details=[('ThumbGrip',(2.22,-.40,2.75),1.85),('ToesDetail',(0,-.5,.4),2.95),('UnderbiteDetail',(0,-.65,6.32),2.40),('TorsoDetail',(0,-.35,4.95),4.45)]
    camera=scene.camera;scene.cycles.samples=24;scene.render.resolution_x=700;scene.render.resolution_y=700
    for name,center,span in details:
        if only and name!=only:continue
        offset=(1.9,.8,-.75) if name in ['RightHandPalmGrip','LeftHandPalmGrip'] else (-1,-3,.8)
        if name=='RightHandSideGrip':offset=(3,-.25,.30)
        if name=='LeftHandPalmGrip':offset=(-1.9,.8,-.75)
        scene.render.resolution_x=1100 if name=='HandsDetail' else 700
        scene.render.resolution_y=650 if name=='HandsDetail' else 700
        if name=='HandsDetail':offset=(0,-3,.35)
        center=Vector(center);camera.location=center+Vector(offset)*span;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=span
        scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
