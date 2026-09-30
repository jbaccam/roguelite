"""Charge clips (2026-09-30): ChargeStart (in-place wind-up + drive step) and
ChargeRun (seamless 2-step sprint loop), authored on the finished rig.

Runs as a new stage on finished/HammerBoss.blend. It does NOT regenerate the
seven existing clips: their exported rows are read back from BossData.json and
rewritten unchanged. Arm solving reuses the pipeline's own hinge/hand code
(wrist_motion.py elbow_hinge + hinge_frames, lever_motion.py blend_frame),
executed whole exactly as finish_reference.py does.

  CHARGE_STAGE=design  -> grid search for the trailing-carry hammer placement
  CHARGE_STAGE=build   -> author, key actions, export FBX, write BossData
"""
import bpy,math,json,os,hashlib
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
HERE=Path(__file__).resolve().parent;OUT=HERE/'finished'
STAGE=os.environ.get('CHARGE_STAGE','build')
bpy.ops.wm.open_mainfile(filepath=str(OUT/'HammerBoss.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['HammerBoss_Rig']
T=Matrix.Translation
def R(x=0,y=0,z=0):return Matrix.Rotation(math.radians(z),4,'Z')@Matrix.Rotation(math.radians(y),4,'Y')@Matrix.Rotation(math.radians(x),4,'X')
def around(p,r):return T(p)@r@T(-Vector(p))
HT=T((-4.4,-2.65,2.65))@R(y=-13);mid=HT@Vector((5.385,0,0));ROOT=4.45
joints={n:{'parent':b.parent.name,'head':b.head_local.copy(),'tail':b.tail_local.copy()} for n,b in rig.data.bones.items() if n!='HumanoidRootPart'}
objects={n:bpy.data.objects[n] for n in joints}
def ik(a,w,l1,l2,pole):
 v=w-a;distance=v.length;d=max(abs(l1-l2)+.001,min(distance,l1+l2-.001));u=v.normalized();along=(l1*l1-l2*l2+d*d)/(2*d)
 side=pole-a;side-=u*side.dot(u)
 return a+u*along+side.normalized()*math.sqrt(max(0,l1*l1-along*along)),max(0,distance-l1-l2)
def align(a,b,c,d):return T(c)@(b-a).rotation_difference(d-c).to_matrix().to_4x4()@T(-a)
for name in ('wrist_motion.py','lever_motion.py'):
 exec(compile((HERE/name).read_text(),str(HERE/name),'exec'))

C=Matrix(((-1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
def arr(m):return [round(m[i][3],6) for i in range(3)]+[round(m[i][j],6) for i in range(3) for j in range(3)]
def row_of(D):return {n:arr(C@T((0,0,-ROOT))@d@T((0,0,ROOT))@C.inverted()) for n,d in D.items()}
def delta(v):
 m=Matrix(((v[3],v[4],v[5],v[0]),(v[6],v[7],v[8],v[1]),(v[9],v[10],v[11],v[2]),(0,0,0,1)))
 return T((0,0,ROOT))@C.inverted()@m@C@T((0,0,-ROOT))
source=json.loads((OUT/'BossData.json').read_text())
IDLE0=source['clips']['Idle']['frames'][0]
carry={n:delta(v) for n,v in IDLE0.items()}

# ---------------------------------------------------------------- constants
FPS=30;START_LAST=18;RUN_FRAMES=16;CYCLE=RUN_FRAMES/FPS
DUTY=.40                      # each foot is on the ground 40% of the cycle (short flight)
SPEED=16.0                    # chargeSpeed, studs/s in unscaled BossData units
STANCE=SPEED*DUTY*CYCLE       # ground travel of a planted toe per contact
ROCK=.40                      # last 40% of contact rolls the heel up about the toe
TD_ANKLE_Y=-1.50              # ankle y at flat touchdown (Blender -Y is forward)
TOE_Y,TOE_Z=-1.50,0.0         # toe pivot on the sole (sole spans y -1.55..0.59)
OUT_TOE=5.0                   # brute stance, toes turned slightly out
GRIPS={'Right':2.72,'Left':8.05}
def side_sign(side):return -1 if side=='Right' else 1

# ---------------------------------------------------------------- curves
def hermite(p0,p1,m0,m1,t):
 t2=t*t;t3=t2*t
 return (2*t3-3*t2+1)*p0+(t3-2*t2+t)*m0+(-2*t3+3*t2)*p1+(t3-t2)*m1
def spline(keys,x,m0=0.0,m1=0.0):
 """Cardinal spline through (x,value) keys: interior keys keep their velocity
 (no stop-at-every-key), end tangents are given (default ease)."""
 if x<=keys[0][0]:return keys[0][1]
 if x>=keys[-1][0]:return keys[-1][1]
 n=len(keys);tangent=[]
 for i in range(n):
  if i==0:tangent.append(m0)
  elif i==n-1:tangent.append(m1)
  else:tangent.append((keys[i+1][1]-keys[i-1][1])/(keys[i+1][0]-keys[i-1][0]))
 for i in range(n-1):
  a,b=keys[i][0],keys[i+1][0]
  if a<=x<=b:
   h=b-a;return hermite(keys[i][1],keys[i+1][1],tangent[i]*h,tangent[i+1]*h,(x-a)/h)
def smooth01(a,b,x):
 t=max(0.0,min(1.0,(x-a)/(b-a)));return t*t*t*(t*(6*t-15)+10)
def wave(phi,k,phase):return math.cos(math.tau*k*(phi-phase))

# ---------------------------------------------------------------- body channels
ZERO={'px':0,'py':0,'pz':0,'pp':0,'pr':0,'pyaw':0,'cl':0,'cr':0,'ct':0,'hp':0,'hy':0,'lag':0,'lagy':0}
def run_channels(phi):
 """Periodic sprint body. Right contact phi 0..0.40, left 0.50..0.90; flights between."""
 bob=wave(phi,2,.45)                         # high in each flight, low at mid-contact
 pz=-.80+.25*bob+.035*wave(phi,4,.45+.06)-.045*wave(phi,1,.20)   # right (hammer) side sinks a bit deeper
 return {
  'px':-.15*wave(phi,1,.22),                 # weight over the planted foot
  'py':.06*wave(phi,2,.12),
  'pz':pz,
  'pp':8+2.0*wave(phi,2,.23),                # pelvis tips forward, more under load
  'pr':3.0*wave(phi,1,.22),                  # swing-side hip drops
  'pyaw':7.0*wave(phi,1,.03),                # hip follows the forward leg
  'cl':17+2.5*wave(phi,2,.27),               # chest keeps a 25 deg total lean, nods after the load
  'cr':-1.5*wave(phi,1,.28),
  'ct':-12.0*wave(phi,1,.06),                # shoulders counter-rotate against the hips
  'hp':-13+3.0*wave(phi,2,.31),              # face stays on the target; heavy head lags the bob
  'hy':8.0*wave(phi,1,.07),
  'lag':3.2*wave(phi,2,.55),                 # hammer head bounces after the body (weight)
  'lagy':2.0*wave(phi,1,.14),
 }
# ChargeStart anticipation beats (frame, value). Everything blends into the run
# channels (evaluated on the run's own clock) between frames 9 and 16.
START_KEYS={
 'px':[(0,0),(4,-.20),(9,-.24)],
 'py':[(0,0),(6,.26),(10,.18)],
 'pz':[(0,0),(4,-.45),(9,-1.08),(11,-1.02)],
 'pp':[(0,0),(5,7),(9,11)],
 'pr':[(0,0),(5,-2.5),(9,-2)],
 'pyaw':[(0,0),(6,7),(9,8)],
 'cl':[(0,0),(4,11),(9,20),(11,20)],
 'cr':[(0,0),(5,-3),(9,-3)],
 'ct':[(0,0),(5,-7),(9,-11)],
 'hp':[(0,0),(3,6),(7,-6),(10,-15)],
 'hy':[(0,0),(6,5),(9,7)],
 'lag':[(0,0),(9,0)],
 'lagy':[(0,0),(9,0)],
}
BLEND=(9,16)
def start_channels(f):
 w=smooth01(*BLEND,f);run=run_channels((f-START_LAST)/RUN_FRAMES)
 return {k:spline(START_KEYS[k],f)*(1-w)+run[k]*w for k in ZERO}

def body(ch):
 hips=T((ch['px'],ch['py'],ch['pz']))@around((0,.1,4.45),R(x=ch['pp'],y=ch['pr'],z=ch['pyaw']))
 chest=hips@around((0,.1,5.2),R(x=ch['cl'],y=ch['cr'],z=ch['ct']))
 head=chest@around(joints['Head']['head'],R(x=ch['hp'],z=ch['hy']))
 return hips,chest,head

# ---------------------------------------------------------------- feet
def toe_rest(side):return Vector((side_sign(side)*1.947,TOE_Y,TOE_Z))
def foot_from_toe(side,toe,pitch,yaw):
 return T(toe)@R(z=yaw)@R(x=pitch)@T(-toe_rest(side))
def foot_from_ankle(side,ankle,pitch,yaw):
 w=joints[side+'Foot']['head'];return T(ankle)@R(z=yaw)@R(x=pitch)@T(-w)
def foot_yaw(side):return side_sign(side)*OUT_TOE
TOE_TD={}
def run_toe_touchdown(side):
 # Flat touchdown with the ankle at TD_ANKLE_Y; the toe is where the sole meets ground.
 F=foot_from_ankle(side,Vector((side_sign(side)*1.947,TD_ANKLE_Y,.55)),0,foot_yaw(side))
 return F@toe_rest(side)
def stance_foot(side,s,toe0=None,moving=True):
 """Contact phase s in [0,1]: the toe point travels backward at SPEED (root-local)."""
 toe=(toe0 or run_toe_touchdown(side)).copy()
 if moving:toe.y+=STANCE*s
 q=max(0.0,(s-(1-ROCK))/ROCK);pitch=32*q*q
 return foot_from_toe(side,toe,pitch,foot_yaw(side)),pitch
def ankle_of(F,side):return F@joints[side+'Foot']['head']
SWING_Z=[(0,None),(.32,1.62),(.72,1.02),(1,.55)]
def swing_foot(side,u,start_F,start_vel,start_pitch,start_pitch_rate,end_vel_y,duration,end_ankle=None,end_yaw=None,start_yaw=None):
 """Swing u in [0,1]. Positions from Hermite/cardinal curves with velocities
 matched at lift-off and touchdown (studs per unit u)."""
 w=joints[side+'Foot']['head']
 a0=start_F@w
 a1=end_ankle if end_ankle is not None else Vector((side_sign(side)*1.947,TD_ANKLE_Y,.55))
 y=hermite(a0.y,a1.y,start_vel.y,end_vel_y,u)
 keys=[(0,a0.z),(.32,max(a0.z+.35,1.62)),(.72,1.02),(1,a1.z)]
 z=spline(keys,u,start_vel.z,-.8)
 x=hermite(a0.x,a1.x,start_vel.x,0,u)
 pk=[(0,start_pitch),(.28,58),(.62,18),(.88,-7),(1,0)]
 pitch=spline(pk,u,start_pitch_rate,0)
 y0=start_yaw if start_yaw is not None else foot_yaw(side);y1=end_yaw if end_yaw is not None else foot_yaw(side)
 yaw=y0+(y1-y0)*smooth01(0,1,u)
 return foot_from_ankle(side,Vector((x,y,z)),pitch,yaw)
def run_foot(side,phi):
 """Run cycle foot. Right contact starts at phi=0, left at phi=0.5."""
 local=(phi-(0 if side=='Right' else .5))%1.0
 if local<DUTY:return stance_foot(side,local/DUTY)[0]
 u=(local-DUTY)/(1-DUTY)
 F1,_=stance_foot(side,1.0);eps=1e-4
 F0,p0=stance_foot(side,1.0-eps)
 vel=(ankle_of(F1,side)-ankle_of(F0,side))/eps*(1-DUTY)/DUTY
 q=1.0;rate=32*2*q/ROCK*(1-DUTY)/DUTY
 return swing_foot(side,u,F1,vel,32.0,rate,SPEED*(1-DUTY)*CYCLE,(1-DUTY)*CYCLE)
# ChargeStart feet: the right foot stays planted, rolls and drives into the first
# contact; the left foot steps back during the drop, stays planted (root is still
# in place) and pushes off on the run's own clock.
L_TOE=run_toe_touchdown('Left')+Vector((0,STANCE,0))   # left toe at the run's push-off point
def start_foot(side,f):
 if side=='Left':
  toe_off=START_LAST-RUN_FRAMES*(1-(.5+DUTY))           # 16.4
  if f>=toe_off:return run_foot('Left',(f-START_LAST)/RUN_FRAMES)
  rock0=toe_off-ROCK*DUTY*RUN_FRAMES
  landing=foot_from_toe('Left',L_TOE,0,foot_yaw('Left'))
  if f>=7:
   q=max(0.0,(f-rock0)/(toe_off-rock0));return foot_from_toe('Left',L_TOE,32*q*q,foot_yaw('Left'))
  if f<=.5:return Matrix.Identity(4)
  u=(f-.5)/6.5;w=joints['Left'+'Foot']['head']
  a0=w.copy();a1=landing@w
  y=hermite(a0.y,a1.y,0,0,u);x=hermite(a0.x,a1.x,0,0,u)
  z=spline([(0,a0.z),(.4,1.25),(.8,.78),(1,a1.z)],u,0,-.4)
  pitch=spline([(0,0),(.3,16),(.75,-6),(1,0)],u)
  return foot_from_ankle('Left',Vector((x,y,z)),pitch,foot_yaw('Left')*smooth01(0,1,u))
 # Right: planted at rest, heel rolls up (drive), then swings to the first contact.
 lift=11.0
 if f<=8:return Matrix.Identity(4)
 toe=toe_rest('Right')
 if f<=lift:
  q=(f-8)/(lift-8);return foot_from_toe('Right',toe,30*q*q,0)
 F1=foot_from_toe('Right',toe,30,0);F0=foot_from_toe('Right',toe,30*(1-1e-4/3)**2,0)
 w=joints['RightFoot']['head'];dur=START_LAST-lift
 vel=(F1@w-F0@w)/(1e-4)*dur
 rate=30*2/(lift-8)*dur
 end=run_foot('Right',0.0)@w
 # lands pulling back at half the run's ground speed: the root is still in place,
 # and ChargeRun's first contact frame then carries it back at full chargeSpeed
 return swing_foot('Right',(f-lift)/dur,F1,vel,30.0,rate,.5*SPEED*dur/FPS,dur/FPS,end_ankle=end,start_yaw=0)

# ---------------------------------------------------------------- legs
def legs(D,hips,feet,yaw):
 for side in ('Right','Left'):
  s=side_sign(side);a=joints[side+'UpperLeg']['head'];b=joints[side+'LowerLeg']['head'];w=joints[side+'Foot']['head']
  F=feet[side];ankle=F@w;hip=hips@a
  pole=hip+R(z=yaw)@Vector((s*.5,-2.63,-2.4))
  knee,err=ik(hip,ankle,(b-a).length,(w-b).length,pole)
  D[side+'UpperLeg']=align(a,b,hip,knee);D[side+'LowerLeg']=align(b,w,knee,ankle);D[side+'Foot']=F
  D['_legerr_'+side]=err

# ---------------------------------------------------------------- hammer + arms
def hammer_world(Q,yaw,pitch,tilt=0.0):
 d=Vector((math.cos(math.radians(pitch))*math.cos(math.radians(yaw)),-math.cos(math.radians(pitch))*math.sin(math.radians(yaw)),math.sin(math.radians(pitch))))
 up=Vector((0,0,1));z=(up-d*up.dot(d)).normalized();z=Matrix.Rotation(math.radians(tilt),3,d)@z;y=z.cross(d)
 M=Matrix((d,y,z)).transposed().to_4x4();M.translation=Q-d*GRIPS['Right']
 return M@HT.inverted()
def hand_of(side,W,roll):
 H=W@HT;center=H@Vector((GRIPS[side],0,0));axis=(H.to_3x3()@Vector((1,0,0))).normalized()
 return around(center,Matrix.Rotation(roll,4,axis))@W
CUFF=(HT.to_3x3()@Vector((0,0,1))).normalized()
def arm_eval(side,chest,W,roll,sw):
 a,b,w=[joints[side+n]['head'] for n in ('UpperArm','LowerArm','Hand')]
 hand=hand_of(side,W,roll);shoulder=chest@a;wrist=hand@w
 elbow,err=elbow_hinge(side,shoulder,wrist,(b-a).length,(w-b).length,chest,sw)
 bend=(elbow-wrist).normalized().angle((hand.to_3x3()@CUFF).normalized())
 inv=chest.inverted();core=100
 for k in range(11):
  p=inv@elbow.lerp(wrist,k/10);core=min(core,(p.x/2.25)**2+((p.y+.15)/1.7)**2+((p.z-6.5)/2.15)**2)
 return hand,elbow,err,bend,core,shoulder,wrist
ROLL_WINDOW=math.radians(24);SWIVEL_SOFT=math.radians(68)
def anchor_cost(side,roll,sw):
 dr=abs(math.remainder(roll-CARRY_STATE[side][0],math.tau))
 return dr*dr*.1+max(0,dr-ROLL_WINDOW)**2*80+max(0,abs(sw)-SWIVEL_SOFT)**2*80
def arm_cost(side,chest,W,roll,sw,prev,cont=.6):
 hand,elbow,err,bend,core,_,_=arm_eval(side,chest,W,roll,sw)
 c=bend*bend+err*err*1e4+max(0,1.35-core)**2*60+sw*sw*.02+anchor_cost(side,roll,sw)
 if prev is not None:c+=(roll-prev[0])**2*cont+(sw-prev[1])**2*cont
 return c
def solve_arm(side,chest,W,prev,span=40,rstep=2,sstep=6,cont=.6):
 base=prev if prev is not None else (0.0,0.0);best=None
 for dr in range(-span,span+1,rstep):
  r=base[0]+math.radians(dr)
  for sd in range(-60,61,sstep):
   c=arm_cost(side,chest,W,r,math.radians(sd),prev,cont)
   if best is None or c<best[0]:best=(c,r,math.radians(sd))
 c,r,sw=best
 for step in (1.0,.25):
  improved=True
  while improved:
   improved=False
   for dr,ds in [(step,0),(-step,0),(0,step),(0,-step)]:
    rr=r+math.radians(dr);ss=max(-math.radians(75),min(math.radians(75),sw+math.radians(ds)))
    cc=arm_cost(side,chest,W,rr,ss,prev,cont)
    if cc<c:c,r,sw=cc,rr,ss;improved=True
 return r,sw
def roll_of(W,hand):
 A=HT.inverted()@W.inverted()@hand@HT;return math.atan2(A[2][1],A[1][1])
def swivel_of(side,chest,shoulder,wrist,elbow):
 s=side_sign(side);u=(wrist-shoulder).normalized()
 pole=chest.to_3x3()@Vector((s*2.2,.35,-3.5));pole-=u*pole.dot(u)
 bend=elbow-shoulder;bend-=u*bend.dot(u)
 return math.atan2(u.dot(pole.cross(bend)),pole.dot(bend))
def reach_project(W,chest,rolls,margin=.02):
 """Move the paired grip as a unit into both arms' hinge-limited reach."""
 for it in range(100):
  worst=0
  for side in ('Right','Left'):
   a,b,w=[joints[side+n]['head'] for n in ('UpperArm','LowerArm','Hand')]
   l1=(b-a).length;l2=(w-b).length
   low=math.sqrt(l1*l1+l2*l2+2*l1*l2*math.cos(ELBOW_MAX))+margin;high=math.sqrt(l1*l1+l2*l2+2*l1*l2*math.cos(ELBOW_MIN))-margin
   v=hand_of(side,W,rolls[side])@w-chest@a;d=v.length;corr=max(low,min(high,d))-d
   worst=max(worst,abs(corr));W=T(v.normalized()*corr)@W
  if worst<1e-7:break
 return W

def carry_arm_state():
 st={}
 W=carry['Hammer'];chest=carry['UpperTorso']
 for side in ('Right','Left'):
  a,b,w=[joints[side+n]['head'] for n in ('UpperArm','LowerArm','Hand')]
  st[side]=(roll_of(W,carry[side+'Hand']),swivel_of(side,chest,chest@a,carry[side+'Hand']@w,carry[side+'LowerArm']@b))
 return st
CARRY_STATE=carry_arm_state()

# Hammer lag rotates about the grip midpoint, around the head's own cross axis.
def lagged(Wloc,ch):
 pivot=HT@Vector((5.385,0,0));ay=HT.to_3x3()@Vector((0,1,0));az=HT.to_3x3()@Vector((0,0,1))
 return Wloc@around(pivot,Matrix.Rotation(math.radians(ch['lag']),4,ay)@Matrix.Rotation(math.radians(ch['lagy']),4,az))

REF=dict(ZERO,**{'pz':-.80,'pp':8,'cl':17,'hp':-13})
def ref_chest():return body(REF)[1]

# ================================================================ DESIGN
def leg_capsules(D):
 caps=[]
 for side in ('Right','Left'):
  a,b,w=[joints[side+n]['head'] for n in ('UpperLeg','LowerLeg','Foot')]
  hip=D[side+'UpperLeg']@a;knee=D[side+'LowerLeg']@b;ankle=D[side+'Foot']@w;toe=D[side+'Foot']@toe_rest(side)
  caps+=[(hip,knee,1.02),(knee,ankle,.88),(ankle,toe,.55)]
 return caps
def head_distance(H,p):
 q=H.inverted()@p;e=Vector((max(0,abs(q.x)-1.55),max(0,abs(q.y)-1.155),max(0,abs(q.z)-2.21)));return e.length
def hammer_leg_clearance(W,D):
 H=W@HT;worst=100
 for a,b,r in leg_capsules(D):
  for k in range(9):
   p=a.lerp(b,k/8);worst=min(worst,head_distance(H,p)-r)
   # shaft: head-local x in [1.45, 9.05], radius .3
   q=H.inverted()@p;x=max(1.45,min(9.05,q.x));worst=min(worst,(Vector((q.x-x,q.y,q.z))).length-.3-r)
 return worst
def head_ground(W):
 H=W@HT;return min((H@Vector((x,y,z))).z for x in (-1.55,1.55) for y in (-1.155,1.155) for z in (-2.21,2.21))
def shaft_core(W,chest):
 H=W@HT;inv=chest.inverted();best=100
 for k in range(41):
  p=inv@(H@Vector((1.45+k/40*7.6,0,0)));best=min(best,(p.x/2.25)**2+((p.y+.15)/1.7)**2+((p.z-6.5)/2.15)**2)
 return best

def run_body(phi):
 ch=run_channels(phi);hips,chest,head=body(ch)
 D={'LowerTorso':hips,'UpperTorso':chest,'Head':head}
 legs(D,hips,{s:run_foot(s,phi) for s in ('Right','Left')},ch['pyaw'])
 return D,ch

if STAGE=='design':
 chestR=ref_chest();inv=chestR.inverted()
 cyc=[run_body(k/RUN_FRAMES) for k in range(RUN_FRAMES)]
 print('LEGERR',max(max(D['_legerr_Right'],D['_legerr_Left']) for D,_ in cyc))
 results=[]
 import itertools
 # Hands keep (almost) the carry roll on the shaft, so the runtime blend back to
 # carry (hands lerped in hammer space) cannot slide the grip off the handle.
 def near_carry(side,chest,W):
  base=CARRY_STATE[side][0];best=None
  for dr in range(-24,25,3):
   for sd in range(-60,66,5):
    r=base+math.radians(dr);sw=math.radians(sd)
    hand,elbow,err,bend,core,_,_=arm_eval(side,chest,W,r,sw)
    c=bend*bend+err*err*1e4+max(0,1.35-core)**2*60+sw*sw*.03+math.radians(dr)**2*.1
    if best is None or c<best[0]:best=(c,r,sw,bend,core,err)
  return best
 for xr,yr,zr,yaw,pitch,tilt in itertools.product((-3.9,-4.2,-4.5),(-1.2,-.9,-.6,-.3),(3.8,4.0,4.2,4.4),(40,50,60),(0,4,8,12),(-30,-15,0,15,30)):
  Q=Vector((xr,yr,zr));Ww=hammer_world(Q,yaw,pitch,tilt);Wloc=inv@Ww
  H=Ww@HT;head=H.translation;left=Ww@HT@Vector((8.05,0,0))
  sol={s:near_carry(s,chestR,Ww) for s in ('Right','Left')}
  if any(v[5]>1e-6 for v in sol.values()) or max(math.degrees(v[3]) for v in sol.values())>24:continue
  bends={s:math.degrees(v[3]) for s,v in sol.items()};sws={s:math.degrees(v[2]) for s,v in sol.items()};cores={s:v[4] for s,v in sol.items()}
  dr={s:math.degrees(v[1]-CARRY_STATE[s][0]) for s,v in sol.items()}
  ground=min(head_ground(D['UpperTorso']@Wloc) for D,ch in cyc)
  if ground<.3:continue
  legc=min(hammer_leg_clearance(D['UpperTorso']@Wloc,D) for D,ch in cyc)
  sc=shaft_core(Ww,chestR)
  score=sum(b*b for b in bends.values())/50+sum(x*x for x in sws.values())/600+sum(x*x for x in dr.values())/400
  score+=max(0,1.3-head.y)**2*20+max(0,head.z-4.0)**2*10+max(0,3.3-head.z)**2*10+max(0,left.x)**2*5+abs(tilt)/60
  score+=max(0,.5-legc)**2*200+max(0,.6-ground)**2*200+max(0,1.2-sc)**2*200+sum(max(0,1.3-c)**2 for c in cores.values())*200
  results.append((round(score,3),[xr,yr,zr,yaw,pitch,tilt],{k:round(v,1) for k,v in bends.items()},{k:round(v,1) for k,v in sws.items()},{k:round(v,1) for k,v in dr.items()},{k:round(v,2) for k,v in cores.items()},round(legc,2),round(ground,2),round(sc,2),[round(c,2) for c in head],[round(c,2) for c in left]))
 results.sort(key=lambda r:r[0])
 for r in results[:25]:print('CAND',r)
 print('COUNT',len(results))

# ================================================================ BUILD
# Chosen by the design stage: right grip contact beside the right hip, shaft 50 deg
# forward of lateral and 4 deg up toward the left hand; head trails behind/outside
# the right hip. Run hands stay within ~24 deg of their carry roll on the shaft so the
# runtime's 0.12 s blend into Slam (hands lerped in hammer space) keeps contact.
# ChargeStart is free to roll further, in small per-frame steps. Stored in chest space so it rides the lean, bob and twist.
TRAIL=dict(Q=(-4.5,-0.9,4.4),yaw=50,pitch=4,tilt=-15)
WLOC=ref_chest().inverted()@hammer_world(Vector(TRAIL['Q']),TRAIL['yaw'],TRAIL['pitch'],TRAIL['tilt'])

def fourier(values,harmonics=3):
 n=len(values);co=[]
 for k in range(harmonics+1):
  a=sum(v*math.cos(math.tau*k*i/n) for i,v in enumerate(values))*2/n
  b=sum(v*math.sin(math.tau*k*i/n) for i,v in enumerate(values))*2/n
  co.append((a/2 if k==0 else a,b))
 return lambda phi:sum(a*math.cos(math.tau*k*phi)+b*math.sin(math.tau*k*phi) for k,(a,b) in enumerate(co))

def finish_arms(D,chest,W,state):
 rolls={s:state[s][0] for s in state}
 W=reach_project(W,chest,rolls)
 D['Hammer']=W
 for side in ('Right','Left'):
  a,b,w=[joints[side+n]['head'] for n in ('UpperArm','LowerArm','Hand')]
  hand,elbow,err,bend,core,shoulder,wrist=arm_eval(side,chest,W,state[side][0],state[side][1])
  D[side+'UpperArm'],D[side+'LowerArm']=hinge_frames(a,b,w,shoulder,elbow,wrist)
  D[side+'Hand']=hand
  D['_bend_'+side]=math.degrees(bend);D['_err_'+side]=err;D['_core_'+side]=core
 return D

def run_pose_parts(phi):
 D,ch=run_body(phi);W=D['UpperTorso']@lagged(WLOC,ch);return D,ch,W

def solve_run():
 samples=[run_pose_parts(k/RUN_FRAMES) for k in range(RUN_FRAMES)]
 states=[None]*RUN_FRAMES;prev={'Right':None,'Left':None}
 for sweep in range(3):
  for k,(D,ch,W) in enumerate(samples):
   # solve on the reach-projected grip, exactly as finish_arms will apply it
   guess=states[k] or (prev if prev['Right'] is not None else {s:(CARRY_STATE[s][0],0.0) for s in ('Right','Left')})
   Wp=reach_project(W,D['UpperTorso'],{s:guess[s][0] for s in ('Right','Left')})
   st={}
   for side in ('Right','Left'):
    st[side]=solve_arm(side,D['UpperTorso'],Wp,prev[side],span=180 if prev[side] is None else 40,cont=.08)
   states[k]=st;prev=dict(st)
 curves={}
 for side in ('Right','Left'):
  rolls=[states[k][side][0] for k in range(RUN_FRAMES)];sw=[states[k][side][1] for k in range(RUN_FRAMES)]
  for k in range(1,RUN_FRAMES):rolls[k]=rolls[k-1]+math.remainder(rolls[k]-rolls[k-1],math.tau)
  assert abs(rolls[-1]-rolls[0])<math.radians(40),('roll does not close on itself',side)
  curves[side]=(fourier(rolls,4),fourier(sw,4))
 return curves
RUN_CURVES=solve_run()
def run_state(phi):return {s:(RUN_CURVES[s][0](phi),RUN_CURVES[s][1](phi)) for s in ('Right','Left')}
def run_frame(phi):
 D,ch,W=run_pose_parts(phi);return finish_arms(D,D['UpperTorso'],W,run_state(phi))


def dp_arm(side,poses,first,last,rstep=3,sstep=5,rmax=18,smax=20,k=.25):
 """Whole-clip (roll, swivel) path for one hand, like polish_hinges' planner:
 per-frame wrist/clearance cost plus squared per-frame change, fixed endpoints."""
 rolls=[first[0]+math.radians(d) for d in range(-102,61,rstep)];sws=[math.radians(d) for d in range(-72,73,sstep)]
 states=[(r,w) for r in rolls for w in sws]
 def local(chest,W,r,w):
  hand,elbow,err,bend,core,_,wrist=arm_eval(side,chest,W,r,w)
  c=bend*bend+max(0,bend-math.radians(18))**2*80+err*err*1e4+max(0,1.35-core)**2*60+w*w*.02+max(0,abs(w)-SWIVEL_SOFT)**2*80
  if side=='Right':c+=max(0,CARRY_CUFF-cuff_clearance(W,elbow,wrist))**2*200
  return c
 def step(a,b):
  dr=math.remainder(b[0]-a[0],math.tau);return (dr*dr+(b[1]-a[1])**2)*k
 prev={first:0.0};back=[]
 for chest,W in poses:
  cur={};bk={}
  for st in states:
   best=None
   for p,c in prev.items():
    if abs(math.degrees(math.remainder(st[0]-p[0],math.tau)))>rmax+1e-6 or abs(math.degrees(st[1]-p[1]))>smax+1e-6:continue
    v=c+step(p,st)
    if best is None or v<best[0]:best=(v,p)
   if best is None:continue
   cur[st]=best[0]+local(chest,W,*st);bk[st]=best[1]
  prev=cur;back.append(bk)
 end=min(prev,key=lambda st:prev[st]+step(st,last));path=[end]
 for bk in reversed(back[1:]):path.append(bk[path[-1]])
 path.reverse()
 # unwrap relative to the fixed start so smoothing never averages across +-180
 out=[];ref=first[0]
 for r,w in path:r=ref+math.remainder(r-ref,math.tau);out.append((r,w));ref=r
 return out


# Forearm-cuff clearance from the hammer head (right hand grips 2.72 from the head
# centre). Proxy: distance of the wrist end of the forearm centreline to the head
# block; the approved carry pose defines the allowed minimum.
def cuff_clearance(W,elbow,wrist):
 Hi=(W@HT).inverted();best=100
 for t in (.7,.8,.9,1.0):
  q=Hi@elbow.lerp(wrist,t);best=min(best,Vector((max(0,abs(q.x)-1.55),max(0,abs(q.y)-1.155),max(0,abs(q.z)-2.21))).length)
 return best
def _carry_cuff():
 a,b,w=[joints['Right'+n]['head'] for n in ('UpperArm','LowerArm','Hand')]
 return cuff_clearance(carry['Hammer'],carry['RightLowerArm']@b,carry['RightHand']@w)
CARRY_CUFF=_carry_cuff()

# ChargeStart hammer: rotate about the grip midpoint in chest space, carry -> trail,
# lagging the body, overshooting a little behind the hip and settling.
PIVOT=HT@Vector((5.385,0,0))
SWING_KEYS=[(0,0),(2,.02),(4,.2),(6.5,.55),(8.5,.88),(10.5,1.045),(13.5,1.0)]
def start_hammer(f,chest,ch):
 Wc0=carry['UpperTorso'].inverted()@carry['Hammer'];Wc1=lagged(WLOC,ch)
 s=spline(SWING_KEYS,f)
 P0=Wc0@PIVOT;P1=Wc1@PIVOT
 q0=Wc0.to_quaternion();dq=q0.rotation_difference(Wc1.to_quaternion())
 axis,angle=dq.to_axis_angle()
 if angle>math.pi:angle-=math.tau
 Rm=(q0@Quaternion(axis,angle*s)).to_matrix().to_4x4()
 # lift and swing wide of the right leg while the head travels back
 P=P0.lerp(P1,s)+Vector((-.8,0,1.7))*math.sin(math.pi*min(1.0,max(0.0,s)))**.7
 return chest@T(P)@Rm@T(-PIVOT)

def solve_start():
 raw=[];frames=[]
 for f in range(START_LAST+1):
  ch=start_channels(f);hips,chest,head=body(ch)
  D={'LowerTorso':hips,'UpperTorso':chest,'Head':head}
  legs(D,hips,{s:start_foot(s,f) for s in ('Right','Left')},ch['pyaw'])
  W=start_hammer(f,chest,ch);raw.append((D,ch,W))
 HANDOFF=16;print('CARRY_STATE',{k:[math.degrees(x) for x in v] for k,v in CARRY_STATE.items()})
 ends={f:run_state((f-START_LAST)/RUN_FRAMES) for f in range(HANDOFF,START_LAST+1)}
 states=[dict(CARRY_STATE)]+[{} for f in range(1,START_LAST+1)]
 for f in range(HANDOFF,START_LAST+1):states[f]=ends[f]
 for side in ('Right','Left'):
  last=ends[HANDOFF][side];first=CARRY_STATE[side]
  path=dp_arm(side,[(raw[f][0]['UpperTorso'],raw[f][2]) for f in range(1,HANDOFF)],first,last)
  for f,st in zip(range(1,HANDOFF),path):states[f][side]=st
  print('DPRAW',side,[(round(math.degrees(r)),round(math.degrees(w)),round(math.degrees(arm_eval(side,raw[f][0]['UpperTorso'],raw[f][2],r,w)[3]),1)) for f,(r,w) in zip(range(1,HANDOFF),path)])
  # keep the handoff roll on the same branch as the path
  for f in range(HANDOFF,START_LAST+1):
   r,w=states[f][side];states[f][side]=(path[-1][0]+math.remainder(r-path[-1][0],math.tau),w)
 for sweep in range(2):
  new=[{s:tuple(v) for s,v in st.items()} for st in states]
  for f in range(1,HANDOFF):
   for side in ('Right','Left'):
    new[f][side]=tuple((states[f-1][side][i]+2*states[f][side][i]+states[f+1][side][i])/4 for i in (0,1))
  states=new
 for f,(D,ch,W) in enumerate(raw):
  frames.append(finish_arms(D,D['UpperTorso'],W,states[f]))
 return frames

if STAGE in ('build','preview'):
 print('CARRY_CUFF',CARRY_CUFF)
 runD=[run_frame(k/RUN_FRAMES) for k in range(RUN_FRAMES)]
 startD=solve_start()
 report={'ChargeRun':{},'ChargeStart':{}}
 for name,seq in (('ChargeStart',startD),('ChargeRun',runD)):
  r=report[name]
  r['maxWristBend']=max(max(D['_bend_Right'],D['_bend_Left']) for D in seq)
  r['maxReachErr']=max(max(D['_err_Right'],D['_err_Left']) for D in seq)
  r['minForearmCore']=min(min(D['_core_Right'],D['_core_Left']) for D in seq)
  r['maxLegErr']=max(max(D['_legerr_Right'],D['_legerr_Left']) for D in seq)
  r['minHeadGround']=min(head_ground(D['Hammer']) for D in seq)
  r['minShaftCore']=min(shaft_core(D['Hammer'],D['UpperTorso']) for D in seq)
  r['minLegHammer']=min(hammer_leg_clearance(D['Hammer'],D) for D in seq)
  r['bendsPerFrame']=[round(max(D['_bend_Right'],D['_bend_Left']),1) for D in seq]
 print('PREVIEW',json.dumps(report))
if STAGE=='preview':
 for f,D in enumerate(startD):
  H=D['Hammer']@HT
  print('SF',f,'sw',[round(math.degrees(swivel_of(s,D['UpperTorso'],D['UpperTorso']@joints[s+'UpperArm']['head'],D[s+'Hand']@joints[s+'Hand']['head'],D[s+'LowerArm']@joints[s+'LowerArm']['head'])),1) for s in ('Right','Left')],'rolls',[round(math.degrees(roll_of(D['Hammer'],D[s+'Hand'])),1) for s in ('Right','Left')],'ground',round(head_ground(D['Hammer']),2),'leg',round(hammer_leg_clearance(D['Hammer'],D),2),'head',[round(c,2) for c in H.translation],'bend',round(D['_bend_Right'],1),round(D['_bend_Left'],1),'pz',round(start_channels(f)['pz'],2),'s',round(spline(SWING_KEYS,f),2))
if STAGE=='preview' and os.environ.get('FREE'):
 for f,D in enumerate(startD):
  out=[]
  for side in ('Right','Left'):
   r,sw=solve_arm(side,D['UpperTorso'],D['Hammer'],None,span=180,rstep=4,sstep=6)
   out.append((round(math.degrees(math.remainder(r,math.tau)),1),round(math.degrees(sw),1),round(math.degrees(arm_eval(side,D['UpperTorso'],D['Hammer'],r,sw)[3]),1)))
  print('FREE',f,out)

# ================================================================ KEY / EXPORT / DATA
def action_digest(action):
 h=hashlib.sha256()
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in sorted(bag.fcurves,key=lambda c:(c.data_path,c.array_index)):
     h.update(f'{fc.data_path}{fc.array_index}'.encode())
     for k in fc.keyframe_points:h.update(('%.7f,%.7f;'%(k.co[0],k.co[1])).encode())
 return h.hexdigest()
if STAGE=='build':
 EXISTING=['Idle','Walk','Slam','Swing','Spin','Hit','Death']
 before={n:action_digest(bpy.data.actions['Boss_'+n]) for n in EXISTING}
 for n in ('Boss_ChargeStart','Boss_ChargeRun'):
  if n in bpy.data.actions:bpy.data.actions.remove(bpy.data.actions[n])
 prevQ={}
 def apply(D,frame=None):
  for name in joints:
   p=rig.pose.bones[name];p.rotation_mode='QUATERNION';p.matrix=D[name]@rig.data.bones[name].matrix_local;bpy.context.view_layer.update()
   if frame is not None:
    q=p.rotation_quaternion.copy()
    if name in prevQ and q.dot(prevQ[name])<0:q.negate();p.rotation_quaternion=q
    prevQ[name]=q.copy()
    for prop in ('location','rotation_quaternion','scale'):p.keyframe_insert(data_path=prop,frame=frame,group=name)
 def select():
  bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
  for o in objects.values():o.select_set(True)
  bpy.context.view_layer.objects.active=rig
 def export(name):
  select();bpy.ops.export_scene.fbx(filepath=str(OUT/name),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
 clean=lambda D:{n:m for n,m in D.items() if not n.startswith('_')}
 runRows=[row_of(clean(D)) for D in runD];runRows.append(runRows[0])
 startRows=[dict(IDLE0)]+[row_of(clean(D)) for D in startD[1:START_LAST]]+[runRows[0]]
 # Blender keys are built from the exact exported rows (frame 0 is Idle frame 0).
 clips={'ChargeStart':startRows,'ChargeRun':runRows}
 stages={'ChargeStart':{'START (CARRY)':0,'DROP':4,'COILED':9,'HEEL ROLL':8,'DRIVE STEP LIFT':11,'RUN CONTACT':18},
         'ChargeRun':{'RIGHT CONTACT':0,'RIGHT PUSH-OFF':6.4,'LEFT CONTACT':8,'LEFT PUSH-OFF':14.4,'LOOP':16}}
 scene.render.fps=FPS
 for clip,rows in clips.items():
  rig.animation_data_clear();prevQ.clear()
  for f,row in enumerate(rows):apply({n:delta(v) for n,v in row.items()},f+1)
  action=rig.animation_data.action;action.name='Boss_'+clip;action.use_fake_user=True
  action['StageFrames']=json.dumps(stages[clip])
  scene.frame_start=1;scene.frame_end=len(rows);scene.frame_set(1)
  export(clip+'.fbx')
 # data: existing clips are carried over from the file unchanged
 data={}
 for k,v in source.items():
  data[k]=v
  if k=='walkSpeed':data['chargeSpeed']=SPEED
 data['clips']=dict(source['clips'])
 data['clips']['ChargeStart']={'fps':FPS,'lastFrame':START_LAST,'frames':startRows}
 data['clips']['ChargeRun']={'fps':FPS,'lastFrame':RUN_FRAMES,'frames':runRows}
 (OUT/'BossData.json').write_text(json.dumps(data,separators=(',',':')))
 (OUT/'BossData.luau').write_text('return game:GetService("HttpService"):JSONDecode([====['+json.dumps(data,separators=(',',':'))+']====])\n')
 clipdir=OUT/'clips';clipdir.mkdir(exist_ok=True)
 metadata={k:v for k,v in data.items() if k!='clips'};metadata['clips']={}
 loader='local D=game:GetService("HttpService"):JSONDecode([====['+json.dumps(metadata,separators=(',',':'))+']====])\n'
 for name,clip in data['clips'].items():
  (clipdir/(name+'.luau')).write_text('return game:GetService("HttpService"):JSONDecode([====['+json.dumps(clip,separators=(',',':'))+']====])\n')
  loader+="D.clips."+name+"=require(script:WaitForChild('"+name+"'))\n"
 (OUT/'BossDataMain.luau').write_text(loader+'return D\n')
 # restore the saved scene state: Idle on the rig, original frame range
 rig.animation_data_clear();rig.animation_data_create();idle=bpy.data.actions['Boss_Idle']
 rig.animation_data.action=idle
 if getattr(rig.animation_data,'action_slot',None) is None and len(idle.slots):rig.animation_data.action_slot=idle.slots[0]
 scene.frame_start=1;scene.frame_end=97;scene.frame_set(1)
 rig['Actions']='Idle, Walk, Slam, Swing, Spin, Hit, Death, ChargeStart, ChargeRun'
 rig['ChargeSpeed']=SPEED
 after={n:action_digest(bpy.data.actions['Boss_'+n]) for n in EXISTING}
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'HammerBoss.blend'))
 build={'existingActionDigestsBefore':before,'existingActionsUnchangedInSession':before==after,
        'chargeSpeed':SPEED,'duty':DUTY,'stanceTravel':STANCE,'runFrames':RUN_FRAMES,'startLastFrame':START_LAST,
        'trailingCarry':TRAIL,'authoring':report}
 (OUT/'charge-build.json').write_text(json.dumps(build,indent=1))
 print('CHARGE_BUILD',json.dumps({k:v for k,v in build.items() if k!='authoring'}))
if STAGE=='preview' and os.environ.get('RUNDBG'):
 for k,D in enumerate(runD):
  st=run_state(k/RUN_FRAMES);out=[]
  for side in ('Right','Left'):
   r,sw=st[side];fr,fs=solve_arm(side,D['UpperTorso'],D['Hammer'],None,span=180,rstep=4,sstep=6,cont=0)
   out.append((side[0],round(math.degrees(r-CARRY_STATE[side][0]),1),round(math.degrees(sw),1),round(D['_bend_'+side],1),'free',round(math.degrees(math.remainder(fr-CARRY_STATE[side][0],math.tau)),1),round(math.degrees(fs),1),round(math.degrees(arm_eval(side,D['UpperTorso'],D['Hammer'],fr,fs)[3]),1)))
  print('RUN',k,out)
