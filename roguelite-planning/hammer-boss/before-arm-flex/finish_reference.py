"""Finish the reference rebuild: atlas, articulated rig, seven actions and exports."""
import bpy,bmesh,math,json
from pathlib import Path
from mathutils import Matrix,Vector
HERE=Path(__file__).resolve().parent
OUT=HERE/'finished';OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(HERE/'reference-rebuild/ReferenceBoss.blend'))
scene=bpy.context.scene;T=Matrix.Translation
def R(x=0,y=0,z=0):return Matrix.Rotation(math.radians(z),4,'Z')@Matrix.Rotation(math.radians(y),4,'Y')@Matrix.Rotation(math.radians(x),4,'X')
def around(p,r):return T(p)@r@T(-Vector(p))
HT=T((-4.4,-2.65,2.65))@R(y=-13)
mid=HT@Vector((5.385,0,0));ROOT=4.45
parts={};joints={}
def joint(n,parent,a,b):joints[n]={'parent':parent,'head':Vector(a),'tail':Vector(b)}
joint('LowerTorso','HumanoidRootPart',(0,.1,4.45),(0,.1,5.2))
joint('UpperTorso','LowerTorso',(0,.1,5.2),(0,.1,9.7))
joint('Head','UpperTorso',(-.16,-.28,9.71),(-.4,-.4,11.9))
for side,s in [('Right',-1),('Left',1)]:
 a=Vector((s*2.92,.02,9.13));b=Vector((s*3.61,-.08,6.87));w=HT@Vector((2.72 if s<0 else 8.05,.30,1.03))
 joint(side+'UpperArm','UpperTorso',a,b);joint(side+'LowerArm',side+'UpperArm',b,w);joint(side+'Hand',side+'LowerArm',w,w+Vector((0,0,-.7)))
 a=(s*1.50,.13,4.4);b=(s*1.815,.03,2.12);w=(s*1.947,-.12,.55)
 joint(side+'UpperLeg','LowerTorso',a,b);joint(side+'LowerLeg',side+'UpperLeg',b,w);joint(side+'Foot',side+'LowerLeg',w,(s*1.947,-.8,.3))
joint('Hammer','HumanoidRootPart',HT.translation,HT@Vector((1,0,0)))
for o in list(bpy.data.objects):
 if o.type!='MESH' or not o.parent or not o.parent.name.endswith('_CTRL'):continue
 group=o.parent.name[:-5]
 name={'Torso':'UpperTorso','Hips':'LowerTorso','RightForearm':'RightLowerArm','LeftForearm':'LeftLowerArm'}.get(group,group)
 if group in ('RightLeg','LeftLeg'):
  side=group[:-3]
  name=side+('Foot' if o.name.startswith('Large square') else 'LowerLeg' if o.name.startswith('Faceted green') else 'UpperLeg')
 world=o.matrix_world.copy();o.parent=None;o.matrix_world=world;parts.setdefault(name,[]).append(o)
# The head retains the existing family's face tile; no photographic projection.
family_material=parts['Head'][0].data.materials[0]
objects={}
for name,items in parts.items():
 bpy.ops.object.select_all(action='DESELECT')
 for o in items:o.select_set(True)
 bpy.context.view_layer.objects.active=items[0];bpy.ops.object.join();o=bpy.context.object;o.name=name
 bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
 scene.cursor.location=joints[name]['head'];bpy.ops.object.origin_set(type='ORIGIN_CURSOR');objects[name]=o
for o in list(bpy.data.objects):
 if o.type=='EMPTY' and (o.name.endswith('_CTRL') or o.name=='Boss_REFERENCE_RIG'):bpy.data.objects.remove(o,do_unlink=True)
# Each section gets its own 1K map; a shared atlas lost skin detail after import.
texdir=OUT/'textures';texdir.mkdir(exist_ok=True)
scene.render.engine='CYCLES';scene.cycles.samples=1;scene.render.bake.use_pass_direct=False;scene.render.bake.use_pass_indirect=False;scene.render.bake.use_pass_color=True;scene.render.bake.margin=12
for name,o in objects.items():
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
 o.data.uv_layers.new(name='BossAtlas');o.data.uv_layers.active_index=len(o.data.uv_layers)-1
 bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.015);bpy.ops.object.mode_set(mode='OBJECT')
 atlas=bpy.data.images.new('HammerBoss_'+name+'_Color',width=1024,height=1024,alpha=False)
 for m in o.data.materials:
  if m.use_nodes:
   node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=atlas;m.node_tree.nodes.active=node
 bpy.ops.object.bake(type='DIFFUSE');atlas.filepath_raw=str(texdir/(name+'.png'));atlas.file_format='PNG';atlas.save();atlas.pack()
 material=bpy.data.materials.new('Painted '+name);material.use_nodes=True
 p=material.node_tree.nodes.get('Principled BSDF');p.inputs['Roughness'].default_value=.93;p.inputs['Specular IOR Level'].default_value=.12
 node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=atlas;material.node_tree.links.new(node.outputs['Color'],p.inputs['Base Color'])
 o.data.materials.clear();o.data.materials.append(material)
 for p in o.data.polygons:p.material_index=0
 for uv in list(o.data.uv_layers):
  if uv.name!='BossAtlas':o.data.uv_layers.remove(uv)
bpy.ops.object.select_all(action='DESELECT');bpy.ops.object.armature_add(location=(0,0,0));rig=bpy.context.object;rig.name='HammerBoss_Rig'
bpy.ops.object.mode_set(mode='EDIT');bones=rig.data.edit_bones;bones.remove(bones[0]);b=bones.new('HumanoidRootPart');b.head=(0,0,ROOT);b.tail=(0,0,ROOT+.5)
for name,j in joints.items():
 b=bones.new(name);b.head=j['head'];b.tail=j['tail'];b.parent=bones[j['parent']]
bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True
for name,o in objects.items():
 vg=o.vertex_groups.new(name=name);vg.add(list(range(len(o.data.vertices))),1.,'REPLACE');mod=o.modifiers.new('Articulated boss','ARMATURE');mod.object=rig;o.parent=rig
# hip yaw, chest yaw, crouch, chest lean, weapon yaw, weapon pitch, lift
exec(compile((HERE/'wrist_motion.py').read_text(),str(HERE/'wrist_motion.py'),'exec'))
exec(compile((HERE/'lever_motion.py').read_text(),str(HERE/'lever_motion.py'),'exec'))
wristHistory={}
neutral=[0,0,0,0,0,0,0]
KEYS={
 'Slam':[(0,neutral),(5,neutral),(12,[-8,-12,.3,-7,12,92,3.8]),(18,[-8,-12,.38,-8,15,112,4.1]),(20,[-2,-4,.45,0,20,75,3.2]),(23,[5,5,1.0,18,25,0,0]),(26,[6,6,1.08,20,25,0,0]),(31,[6,7,1.02,18,25,0,0]),(41,[2,4,.45,8,15,15,1.1]),(50,neutral)],
 'Swing':[(0,neutral),(6,neutral),(13,[-20,-35,.35,-3,-35,13,1.15]),(18,[-25,-42,.40,-3,-42,13,1.15]),(21,[0,-12,.42,4,0,13,1.15]),(23,[20,23,.48,8,75,13,1.15]),(25,[60,80,.53,10,155,13,1.15]),(30,[80,100,.62,11,185,10,1.0]),(37,[65,80,.45,7,164,0,.65]),(45,[24,30,.23,3,70,0,.3]),(54,neutral)],
 'Spin':[(0,neutral),(6,neutral),(14,[-32,-47,.50,4,-47,13,1.15]),(20,[-38,-54,.57,5,-54,13,1.15]),(21,[-32,-50,.54,5,-50,13,1.15]),(25,[56,41,.42,6,41,13,1.15]),(29,[148,133,.40,8,133,13,1.15]),(33,[240,225,.46,10,225,13,1.15]),(37,[325,310,.55,12,310,13,1.15]),(42,[371,375,.65,13,375,10,.9]),(51,[366,370,.40,7,370,0,.4]),(60,[360,363,.1,2,363,0,.05]),(66,[360,360,0,0,360,0,0])]
}
def channels(clip,f):
 for (a,v),(b,w) in zip(KEYS[clip],KEYS[clip][1:]):
  if a<=f<=b:
   t=(f-a)/(b-a)
   if not (clip=='Spin' and a>=21 and b<=37):t=t*t*(3-2*t)
   return [x+(y-x)*t for x,y in zip(v,w)]
 return KEYS[clip][-1][1]
def align(a,b,c,d):return T(c)@(b-a).rotation_difference(d-c).to_matrix().to_4x4()@T(-a)
def ik(a,w,l1,l2,pole):
 v=w-a;distance=v.length;d=max(abs(l1-l2)+.001,min(distance,l1+l2-.001));u=v.normalized();along=(l1*l1-l2*l2+d*d)/(2*d)
 side=pole-a;side-=u*side.dot(u)
 return a+u*along+side.normalized()*math.sqrt(max(0,l1*l1-along*along)),max(0,distance-l1-l2)
def pose(clip,f):
 if f==0:wristHistory.clear()
 sec=f/30;hip,torso,crouch,lean,yaw,pitch,lift=channels(clip,f) if clip in KEYS else neutral
 stride=math.sin(sec*2*math.pi/1.6) if clip=='Walk' else 0
 sway=0;roll=0
 if clip=='Idle':
  breath=math.sin(sec*2*math.pi/3.2);crouch=.035*breath;lean=.35*breath;lift=.025*breath
 if clip=='Walk':
  phase=(f/48)%1
  # Unequal footfalls: short dragging left step, longer right support.
  crouch=.25+keyed([(0,[.67]),(.09,[.79]),(.32,[.30]),(.43,[.48]),(.52,[.63]),(.79,[.23]),(1,[.67])],phase)[0]
  sway=.28*math.sin(phase*math.tau-.3);roll=3.2*math.sin(phase*math.tau)
  lean=4+2.5*math.sin(phase*math.tau+.6);hip=3*stride;torso=-3*stride;yaw=-2*stride
  lift=.8-crouch*.65+.10*math.sin(phase*math.tau-.5)
 if clip=='Hit':lean=-5*math.sin(math.pi*f/18);torso=3*math.sin(math.pi*f/18)
 death=f/84 if clip=='Death' else 0
 if death:
  t=min(1,death*1.4);crouch=2.6*t;lean=74*max(0,(death-.25)/.75);lift=-1.8*t
 hips=T((sway,0,-crouch))@around((0,.1,4.45),R(y=roll*.65,z=hip))
 chest=T((sway,0,-crouch))@around((0,.1,5.2),R(x=lean,y=roll,z=torso))
 D={'LowerTorso':hips,'UpperTorso':chest,'Head':chest@around(joints['Head']['head'],R(x=-lean*.18,z=-(torso-hip)*.2))}
 weapon=T((0,0,lift))@around(mid,R(z=yaw,y=pitch))
 handOffsets={side:Matrix.Identity(4) for side in ('Right','Left')}
 if clip in KEYS:weapon,handOffsets=attack_pose(clip,f,chest)
 # Idle, locomotion and death retain their relaxed carry grip.
 for iteration in range(0 if clip in KEYS else 40):
  for side in ('Right','Left'):
   a=joints[side+'UpperArm']['head'];b=joints[side+'LowerArm']['head'];w=joints[side+'Hand']['head']
   delta=weapon@w-chest@a;limit=(b-a).length+(w-b).length-.035
   if delta.length>limit:weapon.translation-=delta.normalized()*(delta.length-limit)
 if death:
  corners=[weapon@HT@Vector((x,y,z)) for x in [-1.55,1.55] for y in [-1.155,1.155] for z in [-2.21,2.21]]
  weapon.translation.z+=max(0,-min(p.z for p in corners))
 if clip in KEYS:
  sweepWeight=0;fixedHeight=clip=='Slam' and 23<=f<=29
  if clip in ('Swing','Spin'):
   start,end=(19,25) if clip=='Swing' else (21,37)
   sweepWeight=ease(14,start,f)*(1-ease(end,end+10,f))
   if start<=f<=end:
    weapon.translation.z+=4.6-(weapon@HT).translation.z;fixedHeight=True
  weapon,gripSolutions=solve_grips(weapon,handOffsets,chest,wristHistory,fixedHeight,sweepWeight)
 D['Hammer']=weapon;errors=[]
 for side,s in [('Right',-1),('Left',1)]:
  a=joints[side+'UpperArm']['head'];b=joints[side+'LowerArm']['head'];w=joints[side+'Hand']['head'];shoulder=chest@a;handPose=weapon@handOffsets[side];wrist=handPose@w
  if death:handPose=chest.copy();wrist=handPose@w
  # The upper arm and forearm share a bounded, one-way elbow hinge.
  elbow,err=elbow_hinge(side,shoulder,wrist,(b-a).length,(w-b).length,chest)
  if clip in KEYS:
   handPose,elbow,err,bend,roll,swivel=gripSolutions[side]
   wrist=handPose@w
  errors.append(err)
  D[side+'UpperArm'],D[side+'LowerArm']=hinge_frames(a,b,w,shoulder,elbow,wrist)
  D[side+'Hand']=handPose
  a=joints[side+'UpperLeg']['head'];b=joints[side+'LowerLeg']['head'];w=joints[side+'Foot']['head'];foot=R(z=hip*.85)@w
  foot.y+=stride*s*.52;foot.z=.55+max(0,stride*s)*.22
  if clip=='Walk':
   phase=(f/48-(0 if side=='Right' else .43))%1;stance=.60 if side=='Right' else .57
   travel=4.5*1.6*stance
   if phase<stance:foot.y=w.y+travel*(phase/stance-.5);foot.z=.55
   else:
    t=(phase-stance)/(1-stance);q=t*t*(3-2*t)
    foot.y=w.y+travel*(.5-q);foot.z=.55+(.64 if side=='Right' else .32)*math.sin(math.pi*t)**1.3
   foot.x=w.x
  knee,err=ik(hips@a,foot,(b-a).length,(w-b).length,R(z=hip*.85)@Vector((s*2,-2.5,2)))
  D[side+'UpperLeg']=align(a,b,hips@a,knee);D[side+'LowerLeg']=align(b,w,knee,foot);D[side+'Foot']=T(foot)@R(z=0 if clip=='Walk' else hip*.85)@T(-w)
 return D,max(errors)
def apply(D,frame=None):
 for name in joints:
  p=rig.pose.bones[name];p.rotation_mode='QUATERNION';p.matrix=D[name]@rig.data.bones[name].matrix_local;bpy.context.view_layer.update()
  if frame is not None:
   for prop in ('location','rotation_quaternion','scale'):p.keyframe_insert(data_path=prop,frame=frame,group=name)
def select():
 bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
 for o in objects.values():o.select_set(True)
 bpy.context.view_layer.objects.active=rig
def export(name,animated=False):
 select();bpy.ops.export_scene.fbx(filepath=str(OUT/name),use_selection=True,object_types={'MESH','ARMATURE'} if animated else {'MESH'},add_leaf_bones=False,bake_anim=animated,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
export('HammerBoss_Import.fbx')
C=Matrix(((-1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
def arr(m):return [round(m[i][3],6) for i in range(3)]+[round(m[i][j],6) for i in range(3) for j in range(3)]
data={'rootHeight':ROOT,'walkSpeed':4.5,'joints':{},'parts':{},'clips':{},'hammerHeadRest':arr(C@T((0,0,-ROOT))@HT@C.inverted()),'hammerHeadSize':[3.1,4.42,2.31]}
for name,j in joints.items():
 data['joints'][name]={'parent':j['parent'],'head':list(C@j['head'])[:3]}
 vs=[C@(objects[name].matrix_world@v.co) for v in objects[name].data.vertices];lo=Vector([min(v[i] for v in vs) for i in range(3)]);hi=Vector([max(v[i] for v in vs) for i in range(3)])
 data['parts'][name]={'center':list((lo+hi)/2),'size':list(hi-lo)}
checks={};scene.render.fps=30
for clip,last in {'Idle':96,'Walk':48,'Slam':50,'Swing':54,'Spin':66,'Hit':18,'Death':84}.items():
 rig.animation_data_clear();frames=[];maxerr=0;scene.render.fps=36 if clip=='Spin' else 30
 for f in range(last+1):
  D,error=pose(clip,f);maxerr=max(maxerr,error);apply(D,f+1)
  frames.append({n:arr(C@T((0,0,-ROOT))@d@T((0,0,ROOT))@C.inverted()) for n,d in D.items()})
 action=rig.animation_data.action;action.name='Boss_'+clip;action.use_fake_user=True;scene.frame_start=1;scene.frame_end=last+1;scene.frame_set(1)
 export(clip+'.fbx',True);data['clips'][clip]={'fps':scene.render.fps,'lastFrame':last,'frames':frames};checks[clip]={'frames':last+1,'maxArmOverreach':maxerr}
(OUT/'BossData.json').write_text(json.dumps(data,separators=(',',':')))
(OUT/'BossData.luau').write_text('return game:GetService("HttpService"):JSONDecode([====['+json.dumps(data,separators=(',',':'))+']====])\n')
clipdir=OUT/'clips';clipdir.mkdir(exist_ok=True)
metadata={k:v for k,v in data.items() if k!='clips'};metadata['clips']={}
loader='local D=game:GetService("HttpService"):JSONDecode([====['+json.dumps(metadata,separators=(',',':'))+']====])\n'
for name,clip in data['clips'].items():
 (clipdir/(name+'.luau')).write_text('return game:GetService("HttpService"):JSONDecode([====['+json.dumps(clip,separators=(',',':'))+']====])\n')
 loader+="D.clips."+name+"=require(script:WaitForChild('"+name+"'))\n"
(OUT/'BossDataMain.luau').write_text(loader+'return D\n')
(OUT/'authoring-checks.json').write_text(json.dumps(checks,indent=2))
rig.animation_data_clear();apply(pose('Idle',0)[0]);scene.render.fps=30;scene.frame_set(1);scene.frame_end=97
rig.animation_data_create();rig.animation_data.action=bpy.data.actions['Boss_Idle']
rig['Reference']='User supplied boss image, September 23 2026';rig['Actions']='Idle, Walk, Slam, Swing, Spin, Hit, Death';rig['HandleLength']=9.05;rig['GripSeparation']=5.33
scene.cycles.samples=32;scene.render.resolution_percentage=75
cam=scene.camera;cam.location=(.4,-30,11);cam.rotation_euler=(Vector((-.7,0,6.05))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=16.2
scene.render.filepath=str(OUT/'HammerBoss_Front.png');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'HammerBoss.blend'));bpy.ops.render.render(write_still=True)
cam.location=(13,-27,11);cam.rotation_euler=(Vector((-.8,0,6))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=17.5;scene.render.filepath=str(OUT/'HammerBoss_ThreeQuarter.png');bpy.ops.render.render(write_still=True)
# Contact sheets are native Blender renders of authored motion, not generated art.
scene.render.resolution_x=700;scene.render.resolution_y=700;scene.render.resolution_percentage=100;scene.cycles.samples=16;cam.data.ortho_scale=19
for clip,frame in [('Slam',18),('Slam',23),('Swing',23),('Spin',29),('Death',84)]:
 rig.animation_data.action=bpy.data.actions['Boss_'+clip];scene.frame_set(frame+1);scene.render.filepath=str(OUT/(clip+'_'+str(frame)+'.png'));bpy.ops.render.render(write_still=True)
print('FINISHED_REFERENCE_BOSS',json.dumps(checks))
