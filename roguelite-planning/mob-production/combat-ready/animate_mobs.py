"""Animation-only pass. Opens accepted meshes; never rebuilds geometry or weights.

Blender CLI: blender --background --threads 4 --python animate_mobs.py -- <id>
Exports a separate delivery directory and deterministic Roblox bone samples.
"""
import bpy, sys, json, math, shutil, hashlib
from pathlib import Path
from mathutils import Vector, Quaternion, Matrix
sys.path.insert(0,str(Path(__file__).resolve().parent))
import attack_design, creature_attacks

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent
ID=sys.argv[sys.argv.index('--')+1]
OVERRIDES={'obsidian-ogre','snake','rock-throwing-crab','skeleton','bow-skeleton','fire-goblin','lava-slime','ash-shaman','spitter-zombie','werewolf','frozen-knight'}
SOURCE=BASE/('reference-rebuilds' if ID in OVERRIDES else 'revisions')/ID
OUT=ROOT/ID;OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE/'Model.blend'))
scene=bpy.context.scene;rig=next(o for o in scene.objects if o.type=='ARMATURE')
meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
pb=rig.pose.bones
data=json.loads((SOURCE/'anatomy.json').read_text()) if (SOURCE/'anatomy.json').exists() else {}
HEAVY=ID in {'obsidian-ogre','frozen-knight','mummy','hermit-crab','spitter-zombie'}
FAST=ID in {'fire-goblin','werewolf','ember-spider','snake'}
HUM='Pelvis' in pb or 'LowerTorso' in pb
PELVIS='Pelvis' if 'Pelvis' in pb else 'LowerTorso'
CHEST='Chest' if 'Chest' in pb else 'UpperTorso'
def name(side,part):
    options={'Thigh':['Thigh','UpperLeg'],'Shin':['Shin','LowerLeg'],'Forearm':['Forearm','LowerArm']}.get(part,[part])
    return next((side+p for p in options if side+p in pb),side+options[0])
def fingerprint():
    h=hashlib.sha256()
    for o in sorted(meshes,key=lambda o:o.name):
        h.update(o.name.encode())
        for v in o.data.vertices:
            h.update(repr(tuple(v.co)).encode());h.update(repr(tuple((o.vertex_groups[g.group].name,round(g.weight,8)) for g in v.groups)).encode())
        for p in o.data.polygons:h.update(repr(tuple(p.vertices)).encode())
    return h.hexdigest()
source_geometry=fingerprint()
old_bow=None
if ID=='bow-skeleton':
    # Keep the reviewed draw solution (straight wrist and string contact).
    code=(BASE/'reference-rebuilds'/'rig_export.py').read_text()
    env={'bpy':bpy,'math':math,'Vector':Vector,'Quaternion':Quaternion,'Matrix':Matrix,'rig':rig,'scene':scene,'data':data,'ID':ID,'spec':{b.name:True for b in rig.data.bones}}
    exec('scene.render.fps=24'+code.split('scene.render.fps=24',1)[1].split('actions={};lengths=')[0],env)
    old_bow=env['pose']
rig.animation_data_clear()
for a in list(bpy.data.actions):bpy.data.actions.remove(a)
for p in pb:p.rotation_mode='QUATERNION'
scene.render.fps=24;scene.frame_start=1

def reset():
    for p in pb:p.location=(0,0,0);p.rotation_quaternion=(1,0,0,0);p.scale=(1,1,1)
def rot(n,angle,axis=(1,0,0),add=False):
    if n not in pb:return
    p=pb[n];a=p.bone.matrix_local.to_3x3().inverted()@Vector(axis)
    q=Quaternion(a.normalized(),math.radians(angle))
    p.rotation_quaternion=p.rotation_quaternion@q if add else q
def move(n,v):
    if n in pb:pb[n].location=pb[n].bone.matrix_local.to_3x3().inverted()@Vector(v)
def smooth(x):
    x=max(0,min(1,x));return x*x*(3-2*x)
def envelope(t,peak=.38,hit=.49,hold=.58):
    a=smooth(t/peak)*(1-smooth((t-peak)/(hit-peak)))
    b=smooth((t-peak)/(hit-peak))*(1-smooth((t-hold)/(1-hold)))
    return a,b
def absolute(n,pos,rotation):
    pb[n].matrix=Matrix.Translation(pos)@rotation.to_matrix().to_4x4()@pb[n].bone.matrix_local.to_3x3().to_4x4()
    bpy.context.view_layer.update()
def leg_ik(side,target):
    """Plant the ankle in world space while the pelvis shifts over the stance leg."""
    un,ln,fn=name(side,'Thigh'),name(side,'Shin'),side+'Foot'
    upper,lower,foot=pb[un],pb[ln],pb[fn]
    bpy.context.view_layer.update()
    a=upper.head.copy();b0=lower.bone.head_local.copy();a0=upper.bone.head_local.copy();c0=foot.bone.head_local.copy()
    d=Vector(target)-a;l1=(b0-a0).length;l2=(c0-b0).length
    distance=max(abs(l1-l2)+.001,min(l1+l2-.001,d.length));direction=d.normalized()
    along=(l1*l1-l2*l2+distance*distance)/(2*distance)
    height=math.sqrt(max(0,l1*l1-along*along))
    pole=Vector((-.10 if side=='Left' else .10,-1,0));pole=(pole-direction*pole.dot(direction)).normalized()
    knee=a+direction*along+pole*height;ankle=a+direction*distance
    absolute(un,a,(b0-a0).rotation_difference(knee-a))
    absolute(ln,knee,(c0-b0).rotation_difference(ankle-knee))
    absolute(fn,ankle,Quaternion((1,0,0,0)))

leg_length=(pb['LeftFoot'].bone.head_local-pb[name('Left','Thigh')].bone.head_local).length if HUM else 1
stride_amp=leg_length*(.46 if FAST else .44) if HUM else {'crab':.50,'hermit-crab':.50,'rock-throwing-crab':.40,'scorpion':.50,'ember-spider':.70}.get(ID,.26 if HEAVY else .42 if FAST else .34)
stance_fraction=.62 if HEAVY else .54 if FAST else .58
move_duration=1.25 if HEAVY else .67 if FAST else .88
move_frames=round(move_duration*24);move_duration=move_frames/24
stride_length=2*stride_amp/stance_fraction
attack_duration=1.6 if HEAVY else .79 if FAST else 1.08
if ID=='bow-skeleton':attack_duration=1.25
attack_frames=round(attack_duration*24);attack_duration=attack_frames/24
impact=(14/24 if ID=='bow-skeleton' else {**attack_design.IMPACT,**creature_attacks.IMPACT}.get(ID,.49)*attack_duration)
clips={'Idle':(72,True),'Move':(move_frames,True),'Attack':(attack_frames,False),'Hit':(10,False),'Death':(24,False)}

leg_tips={}
if not HUM:
    for n in pb.keys():
        if 'Leg' not in n or not n.endswith('Lower'):continue
        bone=pb[n].bone
        if bone.tail_local.z<bone.head_local.z-.1:leg_tips[n]=bone.tail_local.copy();continue
        points=[]
        for o in meshes:
            group=o.vertex_groups.get(n)
            if group:points.extend(o.matrix_world@v.co for v in o.data.vertices if any(g.group==group.index and g.weight>.5 for g in v.groups))
        if points:
            low=min(v.z for v in points);bottom=[v for v in points if v.z<low+.035]
            leg_tips[n]=sum(bottom,Vector())/len(bottom)

def crawler_leg(upper_name,target):
    lower_name=upper_name.replace('Upper','Lower')
    upper,lower=pb[upper_name],pb[lower_name]
    a0=upper.bone.head_local.copy();b0=lower.bone.head_local.copy();c0=leg_tips[lower_name]
    bpy.context.view_layer.update();a=upper.head.copy();delta=target-a;direction=delta.normalized()
    l1=(b0-a0).length;l2=(c0-b0).length;distance=max(abs(l1-l2)+.001,min(l1+l2-.001,delta.length))
    along=(l1*l1-l2*l2+distance*distance)/(2*distance);height=math.sqrt(max(0,l1*l1-along*along))
    pole=b0-a0;pole=(pole-direction*pole.dot(direction)).normalized()
    knee=a+direction*along+pole*height;tip=a+direction*distance
    absolute(upper_name,a,(b0-a0).rotation_difference(knee-a))
    absolute(lower_name,knee,(c0-b0).rotation_difference(tip-knee))

def footpath(phase):
    p=phase%1
    if p<stance_fraction:return -stride_amp+2*stride_amp*p/stance_fraction,0,True
    q=(p-stance_fraction)/(1-stance_fraction);m=2*stride_amp*(1-stance_fraction)/stance_fraction
    y=(2*q**3-3*q*q+1)*stride_amp+(q**3-2*q*q+q)*m+(-2*q**3+3*q*q)*(-stride_amp)+(q**3-q*q)*m
    z=math.sin(math.pi*q)**2*leg_length*(.105 if HEAVY else .19 if FAST else .15)
    return y,z,False

def humanoid(clip,t):
    wave=math.sin(math.tau*t);moving=clip=='Move';breath=math.sin(math.tau*t)
    lean={'werewolf':8,'spitter-zombie':9,'obsidian-ogre':8,'mummy':8,'fire-goblin':10,'ash-shaman':5,'frozen-knight':4,'ice-elf':3}.get(ID,5)
    lower=leg_length*((.17 if HEAVY or FAST else .15) if moving else (.13 if HEAVY else .12 if FAST else .11))
    hipx=(.026*leg_length*math.cos(math.tau*t) if moving else .010*leg_length*breath)
    hipz=-lower+(.02*leg_length*math.cos(math.tau*2*t) if moving else .006*leg_length*breath)
    move(PELVIS,(hipx,.01*leg_length,hipz))
    rot(PELVIS,(-3 if HEAVY else -4)*wave if moving else .65*breath,(0,0,1))
    rot(CHEST,lean+(.6*breath if not moving else 1.5*math.sin(math.tau*2*t)))
    rot(CHEST,(-4 if HEAVY else 5)*wave if moving else .6*breath,(0,0,1),True)
    rot(CHEST,1.2*wave if moving else .4*breath,(0,1,0),True)
    rot('Head',-lean*.55+.7*math.sin(math.tau*t+.35))
    rot('Head',-2*wave if moving else .6*math.sin(math.tau*t),(0,0,1),True)
    for side,phase in [('Left',0),('Right',.5)]:
        n=name(side,'Forearm');s=-1 if side=='Left' else 1
        swing=footpath(t+phase)[0]/stride_amp if moving else math.sin(math.tau*(t+phase))
        # Forward arm opposes forward leg, independently verified from world positions.
        angle=(-7 if HEAVY else -9)+(-13 if HEAVY else -21)*swing if moving else -7+1.2*math.sin(math.tau*t+phase*2)
        if ID=='werewolf':angle-=10
        if ID=='bow-skeleton':angle*=.5
        if ID=='ash-shaman' and side=='Right':angle*=.3
        # Blade carriers hold the weapon arm ready instead of swinging it loose.
        ready=side=='Right' and ID in {'skeleton','frozen-knight','fire-goblin'}
        if ready:angle=angle*.35-12
        rot(side+'UpperArm',angle)
        rot(side+'UpperArm',s*(3 if HEAVY else 2),(0,1,0),True)
        rot(n,-13-(7*max(0,-swing) if moving else .9*breath)-(34 if ready else 0))
        # The rebuilt knight (2026-10-01) grips its sword diagonally with the
        # blade forward-down at rest; the ready lift alone carries it forward
        # and up, edge down, so the old 90-degree forearm roll is gone.
        rot(side+'Hand',2*math.sin(math.tau*(t+phase)-.4) if moving else .5*breath,(0,0,1))
        if ready and ID=='skeleton':
            # Hold the wrist at the sword's comfortable grip (as the attack solver
            # does) so the blade and guard stand off the forearm.
            f0=(pb[side+'Hand'].bone.head_local-pb[n].bone.head_local).normalized()
            b0=Vector(attack_design.HUMANOIDS[ID]['weapon'][side][0]).normalized()
            carry=float(__import__('os').environ.get('CARRY_GRIP',attack_design.HUMANOIDS[ID].get('carryGrip',attack_design.HUMANOIDS[ID]['weapon'][side][2])))
            rot(side+'Hand',-math.degrees(f0.angle(b0)-math.radians(carry)),f0.cross(b0).normalized(),True)
    if clip=='Attack':
        a,b=envelope(t)
        move(PELVIS,(.035*leg_length*a,.055*leg_length*a-.11*leg_length*b,-lower-.04*leg_length*a))
        rot(CHEST,lean-8*a+14*b)
        rot(CHEST,(-12*a+15*b) if ID in {'skeleton','fire-goblin','werewolf','frozen-knight'} else -3*a+4*b,(0,0,1),True)
        rot('Head',-lean*.55-4*a+3*b)
        if ID=='obsidian-ogre':
            for side in ['Left','Right']:
                rot(side+'UpperArm',-105*a-44*b);rot(name(side,'Forearm'),-33*a-10*b)
        elif ID=='ash-shaman':
            rot('LeftUpperArm',-40*a-75*b);rot(name('Left','Forearm'),-48*a-6*b)
            rot('RightUpperArm',-4+7*a-8*b)
        elif ID=='ice-elf':
            rot('RightUpperArm',-34*a-83*b);rot(name('Right','Forearm'),-48*a-6*b)
            rot('LeftUpperArm',-12*a+8*b)
        elif ID=='spitter-zombie':
            rot(CHEST,lean-13*a+15*b);rot('Head',-14*a+16*b)
            rot('LeftUpperArm',-8+10*a-14*b);rot('RightUpperArm',-8+10*a-14*b)
        elif ID!='bow-skeleton':
            rot('RightUpperArm',-7-52*a-69*b)
            rot('RightUpperArm',-20*a+27*b,(0,0,1),True)
            rot(name('Right','Forearm'),-13-43*a+9*b)
            rot('LeftUpperArm',-7+12*a-24*b);rot(name('Left','Forearm'),-17-8*a)
        if ID=='bow-skeleton':
            # A braced archer shifts weight subtly instead of lunging the torso
            # like a melee attack. The reviewed whole arm/bow solution follows it.
            move(PELVIS,(.01*leg_length*a,0,-lower-.01*leg_length*a))
            rot(CHEST,lean-2*a+2*b);rot(CHEST,-2*a+2*b,(0,0,1),True)
            rot('Head',-lean*.55)
    for side,offset in [('Left',0),('Right',.5)]:
        target=pb[side+'Foot'].bone.head_local.copy()
        if moving:
            y,z,planted=footpath(t+offset);target+=Vector((0,y,z))
        else:target.y+=(.025 if side=='Left' else -.025)*leg_length
        leg_ik(side,target)
    if 'Tail' in pb:
        # Bushy tail sways side to side, twice per stride while moving.
        rot('Tail',(7 if moving else 4)*math.sin(math.tau*t*(2 if moving else 1)-.6),(0,0,1))
        rot('Tail',(-3 if moving else -1.5)*math.cos(math.tau*t*(2 if moving else 1)),(1,0,0),True)

def creature(clip,t):
    w=math.sin(math.tau*t);a,b=envelope(t);moving=clip=='Move';attack=clip=='Attack'
    if ID=='snake':
        spines=sorted([n for n in pb.keys() if n.startswith('Spine')],key=lambda n:int(n[5:]))
        for j,n in enumerate(spines):
            rot(n,(2.8 if moving else .5)*math.sin(math.tau*t-j*.5),(0,0,1))
            if attack:rot(n,(-2*a+2.5*b)*(1-j/len(spines)),add=True)
        if attack:
            # In-place lunge; the server moves the root along its locked direction.
            rot('Spine0',-10*a+17*b,add=True);rot('Head',8*a-8*b)
            move('Root',(0,.13*a-.22*b,.11*b))
        else:rot('Head',.6*w)
    elif ID=='lava-slime':
        move('Crown',(.025*w,0,.06*w if not moving else .15*w))
        rot('Body',1.8*w,(0,1,0));rot('Crown',-1.8*w,(0,1,0))
        if moving:move('Root',(0,0,.10*max(0,w)**2))
        if attack:move('Crown',(0,.10*a-.16*b,-.23*a+.19*b));move('Root',(0,0,.16*b))
    elif ID=='frost-ghost':
        move('Body',(0,0,.065*w));rot('Body',5 if moving else 1.2*w)
        for side,s in [('Left',-1),('Right',1)]:
            rot(side+'Arm',-8+(4*w*s if moving else 1.5*w));rot(side+'Arm',s*5,(0,1,0),True)
        rot('Head',-2*w)
        if attack:
            rot('Body',-7*a+14*b)
            for side in ['Left','Right']:rot(side+'Arm',-8-18*a-43*b)
    else:
        # Alternating tripod / tetrapod gait, with stance paws held to the ground.
        move('Body',(.016*w if moving else 0,0,.012*math.cos(math.tau*2*t) if moving else .006*w))
        rot('Body',.7*w,(0,1,0))
        for n in pb.keys():
            if 'Leg' in n and n.endswith('Upper'):
                lower=n.replace('Upper','Lower');j=int(n.split('Leg')[1][0]);side=-1 if n.startswith('Left') else 1
                phase=(t+(j%2)*.5+(.5 if side>0 else 0))%1
                target=leg_tips[lower].copy()
                if moving:
                    y,z,planted=footpath(phase);target+=Vector((0,y,z*.75))
                crawler_leg(n,target)
        for side,s in [('Left',-1),('Right',1)]:
            rot(side+'Arm',-3+(1.2*w*s if moving else .6*w))
            rot(side+'Claw',1.5*w*s if moving else .6*w)
        if attack:
            if ID=='ember-spider':
                rot('Body',-7*a+10*b)
                for side in ['Left','Right']:rot(side+'Fang',-12*a+24*b)
            elif ID=='scorpion':
                rot('Body',-3*a+5*b)
                for n in pb.keys():
                    if n.startswith('Tail'):rot(n,-5*a+10*b)
            elif ID=='rock-throwing-crab':
                rot('RightArm',-35*a+24*b);rot('RightForearm',-25*a+22*b)
                rot('Body',-3*a+6*b)
            else:
                rot('RightArm',-17*a+23*b);rot('RightClaw',-23*a+31*b)
                rot('RightPincer',14*a-8*b,(0,0,1))

designed=None
def pose(clip,t):
    global designed
    if clip=='Attack' and ID in attack_design.HUMANOIDS:
        # Character-specific choreography replaces the shared placeholder swing.
        if designed is None:designed=attack_design.Humanoid(globals(),attack_design.HUMANOIDS[ID])
        designed.pose(t);return
    if clip=='Attack' and ID in creature_attacks.CREATURES:
        if designed is None:designed=creature_attacks.Creature(globals(),creature_attacks.CREATURES[ID])
        designed.pose(t);return
    reset()
    if HUM:humanoid(clip,t)
    else:creature(clip,t)
    if ID=='bow-skeleton' and clip=='Attack':
        # Restore the reviewed global arm solution after posing the grounded legs.
        lower={n:p.matrix_basis.copy() for n,p in pb.items() if n not in ['LeftUpperArm','LeftForearm','LeftHand','RightUpperArm','RightForearm','RightHand','BowDraw']}
        ready={n:pb[n].matrix_basis.copy() for n in ['LeftUpperArm','LeftForearm','LeftHand','RightUpperArm','RightForearm','RightHand','BowDraw']}
        # Matrix setters solve against evaluated parent matrices. Flush the reset
        # before the reviewed IK runs, otherwise the previously leaned chest is
        # used for the solve and then resets, translating the shoulders twice.
        reset();bpy.context.view_layer.update()
        seconds=t*attack_duration
        shot_time=seconds if seconds<=.79 else .79+(seconds-.79)*.21/(attack_duration-.79)
        old_bow('Attack',shot_time);bpy.context.view_layer.update()
        arm={n:pb[n].matrix.copy() for n in ['LeftUpperArm','LeftForearm','LeftHand','RightUpperArm','RightForearm','RightHand','BowDraw']}
        for n,m in lower.items():pb[n].matrix_basis=m
        bpy.context.view_layer.update()
        torso=pb[CHEST].matrix@pb[CHEST].bone.matrix_local.inverted()
        for n,m in arm.items():pb[n].matrix=torso@m;bpy.context.view_layer.update()
        # Enter IK from the relaxed stance rather than snapping an almost
        # straight resting elbow onto the IK pole in the first two frames.
        blend=smooth(shot_time/.25) if shot_time<.25 else smooth((1-shot_time)/.21) if shot_time>.79 else 1
        if blend<1:
            solved={n:pb[n].matrix_basis.copy() for n in arm}
            for n,m in solved.items():
                l0,q0,s0=ready[n].decompose();l1,q1,s1=m.decompose()
                pb[n].matrix_basis=Matrix.LocRotScale(l0.lerp(l1,blend),q0.slerp(q1,blend),s0.lerp(s1,blend))
    if clip=='Hit':
        rot(CHEST if HUM else 'Body' if 'Body' in pb else 'Spine0',-7*math.sin(math.pi*t)*(1-t),add=True)
    if clip=='Death':
        rot('Root',-78*smooth(t));move('Root',(0,0,.25*smooth(t)))
    bpy.context.view_layer.update()

if '--debug' in sys.argv:
    exec(Path(sys.argv[sys.argv.index('--debug')+2]).read_text());sys.exit(0)
if '--preview' in sys.argv:
    import attack_preview
    args=sys.argv[sys.argv.index('--preview')+1:]
    clip=args[1] if len(args)>1 else 'Attack';count=clips[clip][0]
    frames=[int(x) for x in args[2].split(',')] if len(args)>2 else sorted({0,round(count*.2),round(count*.36),round(count*.44),round(impact*24),round(count*.6),round(count*.8)})
    track={n:(lambda n=n:pb[n].head.copy()) for n in pb.keys() if n.endswith('Hand') or n.startswith('Tail') or n in ('Head','Body')}
    attack_preview.run(globals(),args[0],clip,count,frames,track)
    if hasattr(designed,'last_tail'):
        print('TAIL',[tuple(round(x,2) for x in p) for p in designed.last_tail])
    if hasattr(designed,'wrist_bend'):
        print('WRIST_BEND',designed.wrist_bend)
        for d in designed.diag:
            if d[3]>45 or d[2]>60 or (len(d)>4 and d[4]>.4):print('DIAG',*d)
        print('FLAT_LEAD',getattr(designed,'flat_lead',None))
    sys.exit(0)
S=Matrix(((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
def cf(m):
    m=S@m@S
    return [round(x,7) for x in [m[0][3],m[1][3],m[2][3],m[0][0],m[0][1],m[0][2],m[1][0],m[1][1],m[1][2],m[2][0],m[2][1],m[2][2]]]
samples={'id':ID,'fps':24,'bones':{b.name:{'parent':b.parent.name if b.parent else None,'rest':cf(b.parent.matrix_local.inverted()@b.matrix_local if b.parent else b.matrix_local)} for b in rig.data.bones},'clips':{},'motion':{'strideLength':stride_length,'nominalSpeed':stride_length/move_duration,'attackImpact':impact,'attackRecovery':attack_duration*.58,'attackDuration':attack_duration}}
actions={};checks={'source':str(SOURCE.relative_to(BASE)),'geometryFingerprintBefore':source_geometry,'loopErrors':{},'gait':{},'bow':{}}
rig.animation_data_create()
for clip,(count,loop) in clips.items():
    rig.animation_data.action=None;action=bpy.data.actions.new(clip);rig.animation_data.action=action
    frames=[];world=[]
    for f in range(count+1):
        if ID=='bow-skeleton':rig.animation_data.action=None
        pose(clip,f/count)
        if ID=='bow-skeleton':rig.animation_data.action=action
        for p in pb:p.keyframe_insert('location',frame=f+1,group=p.name);p.keyframe_insert('rotation_quaternion',frame=f+1,group=p.name);p.keyframe_insert('scale',frame=f+1,group=p.name)
        frames.append({'time':f/24,'transforms':{p.name:cf(p.matrix_basis) for p in pb}})
        if HUM:world.append({n:list(pb[n].head) for n in ['LeftFoot','RightFoot','LeftHand','RightHand']})
        if ID=='bow-skeleton' and clip=='Attack' and 6<=f<=18:
            fore=pb['RightForearm'];hand=pb['RightHand'];angle=math.degrees((fore.tail-fore.head).angle(hand.tail-hand.head))
            checks['bow'][str(f+1)]={'wristDegrees':angle}
    action.use_fake_user=True;actions[clip]=action
    if clip=='Attack':action.pose_markers.new('Impact' if ID!='bow-skeleton' else 'Release').frame=1+round(impact*24)
    samples['clips'][clip]={'duration':count/24,'loop':loop,'frames':frames}
    if loop:checks['loopErrors'][clip]=max(abs(a-b) for n in frames[0]['transforms'] for a,b in zip(frames[0]['transforms'][n],frames[-1]['transforms'][n]))
    if clip=='Move' and HUM:
        # Opposing limbs must be visible in world coordinates, not just opposite Euler signs.
        def covariance(an,bn):
            aa=[w[an][1] for w in world[:-1]];bb=[w[bn][1] for w in world[:-1]];av=sum(aa)/len(aa);bv=sum(bb)/len(bb)
            return sum((a-av)*(b-bv) for a,b in zip(aa,bb))/len(aa)
        checks['gait']={'leftLegRightArmCovariance':covariance('LeftFoot','RightHand'),'rightLegLeftArmCovariance':covariance('RightFoot','LeftHand'),'sameSideCovariance':covariance('LeftFoot','LeftHand'),'strideLength':stride_length,'nominalSpeed':stride_length/move_duration}
        checks['gait']['opposingLimbs']=checks['gait']['leftLegRightArmCovariance']>0 and checks['gait']['rightLegLeftArmCovariance']>0 and checks['gait']['sameSideCovariance']<0
        errors=[]
        for i,w in enumerate(world):
            for side,offset in [('Left',0),('Right',.5)]:
                y,z,planted=footpath(i/count+offset)
                if planted:errors.append(abs(w[side+'Foot'][2]-pb[side+'Foot'].bone.head_local.z))
        checks['gait']['maxPlantedAnkleHeightError']=max(errors)
rig.animation_data.action=None;pose('Idle',0)
for clip,action in actions.items():
    track=rig.animation_data.nla_tracks.new();track.name=clip;track.strips.new(clip,1,action);track.mute=True
def select(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=rig
select([rig]+meshes);scene.frame_end=73
for name_ in ['BaseColor.png','Normal.png','ArrowProjectile.fbx','ArrowProjectile.glb','ArrowBaseColor.png','RockProjectile.fbx','RockProjectile.glb']:
    if (SOURCE/name_).exists():shutil.copy2(SOURCE/name_,OUT/name_)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Model.blend'))
bpy.ops.export_scene.fbx(filepath=str(OUT/'Model.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y',use_armature_deform_only=False)
(OUT/'animations').mkdir(exist_ok=True)
for clip,action in actions.items():
    rig.animation_data.action=action;scene.frame_end=clips[clip][0]+1;select([rig])
    bpy.ops.export_scene.fbx(filepath=str(OUT/'animations'/f'{clip}.fbx'),use_selection=True,object_types={'ARMATURE'},add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0,axis_forward='-Z',axis_up='Y')
rig.animation_data.action=None;pose('Idle',0);scene.frame_end=73;select([rig]+meshes)
for tr in rig.animation_data.nla_tracks:tr.mute=False
bpy.ops.export_scene.gltf(filepath=str(OUT/'Model.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_skins=True,export_all_influences=False)
for tr in rig.animation_data.nla_tracks:tr.mute=True
(OUT/'AnimationData.json').write_text(json.dumps(samples,separators=(',',':')))
# Blender-space source geometry for Mesh API importer: positions, per-face UVs, weights.
geometry={}
for o in meshes:
    me=o.data;me.calc_loop_triangles();uv=me.uv_layers.active
    geometry[o.name]={'vertices':[list(v.co) for v in me.vertices],'triangles':[list(t.vertices) for t in me.loop_triangles],'triangleUVs':[[list(uv.data[l].uv) for l in t.loops] for t in me.loop_triangles],'weights':[{o.vertex_groups[g.group].name:g.weight for g in v.groups if g.weight>0} for v in me.vertices]}
(OUT/'Geometry.json').write_text(json.dumps(geometry,separators=(',',':')))
checks['geometryFingerprintAfter']=fingerprint();checks['geometryUnchanged']=source_geometry==checks['geometryFingerprintAfter']
checks['passed']=checks['geometryUnchanged'] and max(checks['loopErrors'].values())<.00001 and (not HUM or (checks['gait']['opposingLimbs'] and checks['gait']['maxPlantedAnkleHeightError']<.002))
checks['fileHashes']={f:hashlib.sha256((OUT/f).read_bytes()).hexdigest() for f in ['Model.blend','Model.fbx','Model.glb','AnimationData.json','Geometry.json']}
(OUT/'AnimationChecks.json').write_text(json.dumps(checks,indent=2))
manifest={'id':ID,'source':str(SOURCE.relative_to(BASE)),'geometryUnchanged':checks['geometryUnchanged'],'clips':{n:{'duration':v['duration'],'loop':v['loop']} for n,v in samples['clips'].items()},'motion':samples['motion'],'studioVerified':False,'assetPublication':'Not published by this export script','notes':['Accepted geometry, UVs and weights preserved.','Animations sampled at 24 fps with exact loop closure.','Humanoid ankles solve to ground targets; movement cycle is distance driven in Roblox.']}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
scene.render.engine='CYCLES';scene.cycles.samples=8;scene.cycles.use_denoising=True;scene.render.resolution_x=480;scene.render.resolution_y=480;scene.render.resolution_percentage=100
for clip,f,label in [('Idle',1,'Stance'),('Move',1+round(move_frames*.25),'Walk'),('Attack',1+round(attack_frames*.37),'Anticipation'),('Attack',1+round(impact*24),'Impact')]:
    if '--movement-pass' in sys.argv and label!='Walk':continue
    rig.animation_data.action=actions[clip];scene.frame_set(f);scene.render.filepath=str(OUT/(label+'.png'));bpy.ops.render.render(write_still=True)
rig.animation_data.action=actions['Idle'];scene.frame_set(1);scene.frame_end=73
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Model.blend'))
checks['fileHashes']['Model.blend']=hashlib.sha256((OUT/'Model.blend').read_bytes()).hexdigest();(OUT/'AnimationChecks.json').write_text(json.dumps(checks,indent=2))
print('ANIMATION_COMPLETE',ID,json.dumps(checks),flush=True)
