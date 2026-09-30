"""Validate ChargeStart / ChargeRun from the exported BossData, plus the joins
ChargeStart->ChargeRun, the ChargeRun loop seam and the runtime ChargeRun->Slam
blend (BossMotion.blend + constrainArms re-implemented in Roblox space, exactly
as the client samples). Writes finished/charge-checks.json."""
import bpy,math,json,os,hashlib
from pathlib import Path
from mathutils import Matrix,Vector,Quaternion
HERE=Path(__file__).resolve().parent;OUT=HERE/'finished'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'HammerBoss.blend'))
rig=bpy.data.objects['HammerBoss_Rig'];bones=rig.data.bones
d=json.loads((OUT/'BossData.json').read_text())
C=Matrix(((-1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)));T=Matrix.Translation;ROOT=d['rootHeight']
HT=T((-4.4,-2.65,2.65))@Matrix.Rotation(math.radians(-13),4,'Y')
def mat(v):return Matrix(((v[3],v[4],v[5],v[0]),(v[6],v[7],v[8],v[1]),(v[9],v[10],v[11],v[2]),(0,0,0,1)))
def unmat(m):return [m[0][3],m[1][3],m[2][3]]+[m[i][j] for i in range(3) for j in range(3)]
def delta(m):return T((0,0,ROOT))@C.inverted()@m@C@T((0,0,-ROOT))
SPEED=d['chargeSpeed'];DUTY=.40;RUN=d['clips']['ChargeRun'];START=d['clips']['ChargeStart'];SLAM=d['clips']['Slam']
GRIPS={'Right':2.72,'Left':8.05};ELBOW_MIN,ELBOW_MAX=12,130
def head(n):return bones[n].head_local

exec(compile((HERE/'charge_runtime.py').read_text(),str(HERE/'charge_runtime.py'),'exec'))

# ------------------------------------------------ informational: pivot-aware blend
# The shipped BossMotion.blend lerps each part's delta CFrame about the root
# origin. For parts far from the root (forearms, hands) that chord cuts inside the
# arc, so constrainArms re-derives a swivel that overshoots to its +-75 clamp and
# hands drift off the shaft. Lerping each part about its own joint pivot (hands
# about their grip point on the shaft) removes both effects. Simulated here only.
def lerp_about(a,b,pivot,t):
 pa=a@pivot;pb=b@pivot;q=a.to_quaternion().slerp(b.to_quaternion(),t)
 m=q.to_matrix().to_4x4();m.translation=pa.lerp(pb,t)-q.to_matrix()@pivot;return m
PIV={n:Vector(j['head'])-Vector((0,ROOT,0)) for n,j in d['joints'].items()}
GRIP_R={s:headRest@Vector((-GRIPS[s],0,0)) for s in GRIPS}
def rblend_pivot(a,b,t):
 r={n:lerp_about(m,b[n],PIV[n],t) for n,m in a.items()}
 ha=a['UpperTorso'].inverted()@a['Hammer']@gripPivot;hb=b['UpperTorso'].inverted()@b['Hammer']@gripPivot
 r['Hammer']=r['UpperTorso']@lerpcf(ha,hb,t)@gripPivot.inverted()
 for side in ('Right','Left'):
  n=side+'Hand';ra=a['Hammer'].inverted()@a[n];rb=b['Hammer'].inverted()@b[n]
  r[n]=r['Hammer']@lerp_about(ra,rb,GRIP_R[side],t)
 return r

# ------------------------------------------------ geometry for body checks
def outer_radius(name,a,b):
 o=bpy.data.objects[name];ab=b-a;best=0
 for v in list(o.data.vertices)[::7]:
  p=o.matrix_world@v.co;t=max(0,min(1,(p-a).dot(ab)/ab.length_squared));best=max(best,(p-a.lerp(b,t)).length)
 return best
TOE={s:Vector((( -1 if s=='Right' else 1)*1.947,-1.50,0.0)) for s in ('Right','Left')}
HEEL={s:Vector((( -1 if s=='Right' else 1)*1.947,.55,0.0)) for s in ('Right','Left')}
LEGR={}
for s in ('Right','Left'):
 a,b,w=head(s+'UpperLeg'),head(s+'LowerLeg'),head(s+'Foot')
 LEGR[s]=(outer_radius(s+'UpperLeg',a,b),outer_radius(s+'LowerLeg',b,w))
VERTS={}
for n in ('UpperTorso','LowerTorso','Head','RightUpperLeg','RightLowerLeg','RightFoot','LeftUpperLeg','LeftLowerLeg','LeftFoot','RightUpperArm','LeftUpperArm','RightLowerArm','LeftLowerArm','RightHand','LeftHand'):
 o=bpy.data.objects[n];VERTS[n]=[o.matrix_world@v.co for v in list(o.data.vertices)[::max(1,len(o.data.vertices)//700)]]
def seg_dist(p,a,b):
 ab=b-a;t=max(0,min(1,(p-a).dot(ab)/ab.length_squared));return (p-a.lerp(b,t)).length

def check_pose(P):
 """P: Roblox-space pose dict. Returns metrics for one pose (Blender space)."""
 D={n:delta(m) for n,m in P.items()};r={}
 H=D['Hammer']@HT;Hi=H.inverted();chest=D['UpperTorso'];inv=chest.inverted()
 contact=0;axial=0;bends=[];flex=[];swiv=[];gaps=[];axisErr=0;core=100
 for side,s in (('Right',-1),('Left',1)):
  g=GRIPS[side];q=Hi@D[side+'Hand']@HT@Vector((g,0,0));contact=max(contact,math.hypot(q.y,q.z));axial=max(axial,abs(q.x-g))
  a,b,w=head(side+'UpperArm'),head(side+'LowerArm'),head(side+'Hand')
  U=D[side+'UpperArm'];L=D[side+'LowerArm'];Hd=D[side+'Hand']
  ru=(b-a).normalized();rl=(w-b).normalized();hinge=ru.cross(rl).normalized()
  li=U.to_3x3().transposed()@L.to_3x3()@rl
  flex.append(math.degrees(math.atan2(hinge.dot(ru.cross(li)),ru.dot(li))))
  axisErr=max(axisErr,(U.to_3x3()@hinge-L.to_3x3()@hinge).length)
  gaps+=[(U@b-L@b).length,(L@w-Hd@w).length,(U@a-chest@a).length]
  elbow=L@b;wrist=Hd@w;shoulder=U@a
  bends.append(math.degrees((elbow-wrist).angle(Hd.to_3x3()@HT.to_3x3()@Vector((0,0,1)))))
  u=(wrist-shoulder).normalized();pole=chest.to_3x3()@Vector((s*2.2,.35,-3.5));pole-=u*pole.dot(u);bd=elbow-shoulder;bd-=u*bd.dot(u)
  swiv.append(math.degrees(math.atan2(u.dot(pole.cross(bd)),pole.dot(bd))))
  for k in range(11):
   p=inv@elbow.lerp(wrist,k/10);core=min(core,(p.x/2.25)**2+((p.y+.15)/1.7)**2+((p.z-6.5)/2.15)**2)
 shaft=100
 for k in range(41):
  p=inv@(H@Vector((1.45+k/40*7.6,0,0)));shaft=min(shaft,(p.x/2.25)**2+((p.y+.15)/1.7)**2+((p.z-6.5)/2.15)**2)
 ground=min((H@Vector((x,y,z))).z for x in (-1.55,1.55) for y in (-1.155,1.155) for z in (-2.21,2.21))
 # legs
 hips=D['LowerTorso'];lat=hips.to_3x3()@Vector((1,0,0));fwd=hips.to_3x3()@Vector((0,-1,0))
 knees=[];kneeFwd=100;legGap=0;caps={}
 for side in ('Right','Left'):
  a,b,w=head(side+'UpperLeg'),head(side+'LowerLeg'),head(side+'Foot')
  hip=D[side+'UpperLeg']@a;knee=D[side+'LowerLeg']@b;ankle=D[side+'Foot']@w
  legGap=max(legGap,(hips@a-hip).length,(D[side+'UpperLeg']@b-knee).length,(D[side+'LowerLeg']@w-ankle).length)
  td=(knee-hip).normalized();sd=(ankle-knee).normalized()
  knees.append(math.degrees(math.atan2(lat.dot(td.cross(sd)),td.dot(sd))))
  line=ankle-hip;off=knee-hip-line*((knee-hip).dot(line)/line.length_squared)
  if knees[-1]>3:kneeFwd=min(kneeFwd,off.normalized().dot(fwd))
  caps[side]=[(hip,knee,LEGR[side][0]),(knee,ankle,LEGR[side][1]),(ankle,D[side+'Foot']@TOE[side],.55)]
 legLeg=min(min(seg_dist(a1.lerp(b1,k/8),a2,b2) for k in range(9))-r1-r2 for a1,b1,r1 in caps['Right'] for a2,b2,r2 in caps['Left'])
 # hammer vs body mesh (hands excluded; forearms only against the head block)
 inside=0;minHammer=100;insideParts={};forearmDepth=0
 for n,vs in VERTS.items():
  if n.endswith('Hand'):continue
  M=Hi@D[n]
  for v in vs:
   q=M@v
   if n.endswith('LowerArm'):
    # forearm cuffs sit next to the head block at the carry grip; measure depth
    if abs(q.x)<=1.55 and abs(q.y)<=1.155 and abs(q.z)<=2.21:forearmDepth=max(forearmDepth,min(1.55-abs(q.x),1.155-abs(q.y),2.21-abs(q.z)))
    continue
   e=Vector((max(0,abs(q.x)-1.55),max(0,abs(q.y)-1.155),max(0,abs(q.z)-2.21))).length
   x=max(1.45,min(9.05,q.x));dist=min(e,Vector((q.x-x,q.y,q.z)).length-.30)
   minHammer=min(minHammer,dist)
   if dist<=0:inside+=1;insideParts[n]=insideParts.get(n,0)+1
 # arms vs legs (forearm/hand mesh points against leg capsules of measured outer radius)
 armLeg=100
 for n in ('RightLowerArm','LeftLowerArm','RightHand','LeftHand'):
  M=D[n]
  for v in VERTS[n][::3]:
   p=M@v
   for side in ('Right','Left'):
    for a1,b1,r1 in caps[side][:2]:armLeg=min(armLeg,seg_dist(p,a1,b1)-r1)
 r.update(contact=contact,axial=axial,bend=max(bends),flexMin=min(flex),flexMax=max(flex),swivel=max(abs(x) for x in swiv),hingeAxis=axisErr,armGap=max(gaps),
  forearmCore=core,shaftCore=shaft,headGround=ground,kneeMin=min(knees),kneeMax=max(knees),kneeForwardDot=kneeFwd,legGap=legGap,legLeg=legLeg,
  hammerBodyInside=inside,hammerBodyMin=minHammer,forearmHeadDepth=forearmDepth,armLegMin=armLeg)
 r['_insideParts']=insideParts
 return r
LIMITS=dict(contact=('max',.001),axial=('max',.001),bend=('max',35),flexMin=('min',ELBOW_MIN-.1),flexMax=('max',ELBOW_MAX+.1),swivel=('max',75.01),
 hingeAxis=('max',.001),armGap=('max',.001),forearmCore=('min',1.0),shaftCore=('min',1.0),headGround=('min',0.0),kneeMin=('min',-.5),kneeMax=('max',150),
 kneeForwardDot=('min',0.0),legGap=('max',.001),legLeg=('min',0.0),hammerBodyInside=('max',0))
RUNTIME_LIMITS={'contact':('max',.08),'axial':('max',.01),'legGap':('max',None),'armGap':('max',.001)}
def summarize(metrics,label,runtime=False):
 out={};fails=[]
 for k in metrics[0]:
  if k.startswith('_'):continue
  vals=[m[k] for m in metrics];mode=LIMITS.get(k,('min' if k in ('hammerBodyMin','armLegMin') else 'max',None))[0]
  worst=min(vals) if mode=='min' else max(vals);idx=vals.index(worst);out[k]={'worst':round(worst,6),'at':idx}
  lim=(RUNTIME_LIMITS[k][1] if runtime and k in RUNTIME_LIMITS else LIMITS[k][1]) if k in LIMITS else None
  if lim is not None:
   if (mode=='max' and worst>lim) or (mode=='min' and worst<lim):fails.append(f'{label}:{k}={worst:.4f}@{idx}')
 return out,fails
def angstep(P0,P1,parts=None):
 best=(0,None)
 for n in (parts or P0):
  q0=P0[n].to_quaternion();q1=P1[n].to_quaternion();a=math.degrees(q0.rotation_difference(q1).angle);a=min(a,360-a)
  if a>best[0]:best=(a,n)
 return best
def local_rot(P,n):
 parent=d['joints'][n]['parent'];return (P[n] if parent=='HumanoidRootPart' else P[parent].inverted()@P[n])
def jointstep(P0,P1):
 best=(0,None)
 for n in d['joints']:
  a=math.degrees(local_rot(P0,n).to_quaternion().rotation_difference(local_rot(P1,n).to_quaternion()).angle);a=min(a,360-a)
  if a>best[0]:best=(a,n)
 return best

report={};failures=[]
CARRY_FOREARM=check_pose({n:mat(v) for n,v in d['clips']['Idle']['frames'][0].items()})['forearmHeadDepth']
LIMITS['forearmHeadDepth']=('max',CARRY_FOREARM+.05)
report['carryPoseForearmHeadDepth_baseline']=CARRY_FOREARM
print('CARRYBASE',CARRY_FOREARM)
# 1. authored frames
for name in ('ChargeStart','ChargeRun'):
 ms=[check_pose(P) for P in FR[name]];s,f=summarize(ms,name)
 report[name+'_hammerContactsByFrame']={i:m['_insideParts'] for i,m in enumerate(ms) if m['_insideParts']}
 report[name+'_forearmHeadDepthPerFrame']=[round(m['forearmHeadDepth'],3) for m in ms]
 print('FOREARM',name,report[name+'_forearmHeadDepthPerFrame'])
 print('INSIDE',name,report[name+'_hammerContactsByFrame']);report[name]={'frames':len(ms),'fps':d['clips'][name]['fps'],'lastFrame':d['clips'][name]['lastFrame'],'checks':s};failures+=f
 steps=[jointstep(FR[name][i],FR[name][i+1]) for i in range(len(FR[name])-1)]
 world=[angstep(FR[name][i],FR[name][i+1]) for i in range(len(FR[name])-1)]
 report[name]['maxJointStepDegPerFrame']={'value':round(max(s[0] for s in steps),3),'at':[steps.index(max(steps)),max(steps)[1]]}
 report[name]['maxWorldPartStepDegPerFrame']={'value':round(max(s[0] for s in world),3),'at':[world.index(max(world)),max(world)[1]]}
 report[name]['jointStepPerFrame']=[round(s[0],2) for s in steps]
# 2. runtime interpolation at 120 Hz (what the client/server actually sample)
for name,looped in (('ChargeStart',False),('ChargeRun',True)):
 dur=d['clips'][name]['lastFrame']/30;n=int(round(dur*120))
 ms=[check_pose(rsample(name,k/120,looped)) for k in range(n+1)];s,f=summarize(ms,name+'@120Hz',True);report[name+'_runtime120Hz']={'samples':len(ms),'checks':s};failures+=f
# 3. runtime must reproduce authored frames (constrainArms does not move them)
repro=0
for name in ('ChargeStart','ChargeRun'):
 for P in FR[name]:
  Q=constrain({n:m.copy() for n,m in P.items()})
  for n in P:repro=max(repro,(Q[n].translation-P[n].translation).length,max(abs(Q[n][i][j]-P[n][i][j]) for i in range(3) for j in range(3)))
report['runtimeReproductionMaxError']=repro
if repro>.002:failures.append('runtime reproduction %.5f'%repro)
# 4. joins
def rowdiff(a,b):return max(max(abs(x-y) for x,y in zip(a[n],b[n])) for n in a)
S=START['frames'];Rw=RUN['frames']
joins={'startLast_vs_runFirst_maxComponentDiff':rowdiff(S[-1],Rw[0]),'runLast_vs_runFirst_maxComponentDiff':rowdiff(Rw[-1],Rw[0]),
 'startFirst_vs_idleFirst_maxComponentDiff':rowdiff(S[0],d['clips']['Idle']['frames'][0])}
js=[jointstep(FR['ChargeRun'][i],FR['ChargeRun'][i+1])[0] for i in range(16)]
joins['runSeamJointStep']={'intoSeam(15->16)':round(js[15],3),'outOfSeam(0->1)':round(js[0],3),'runMedian':round(sorted(js)[8],3),'runMax':round(max(js),3)}
ss=[jointstep(FR['ChargeStart'][i],FR['ChargeStart'][i+1])[0] for i in range(18)]
joins['startToRunJointStep']={'start(17->18)':round(ss[17],3),'run(0->1)':round(js[0],3)}
# joint angular-acceleration spike at the joins (second difference of local rotations)
def accel(P0,P1,P2):
 best=0
 for n in d['joints']:
  a=local_rot(P0,n).to_quaternion();b=local_rot(P1,n).to_quaternion();c=local_rot(P2,n).to_quaternion()
  v1=a.rotation_difference(b);v2=b.rotation_difference(c);x=math.degrees(v1.rotation_difference(v2).angle);best=max(best,min(x,360-x))
 return best
runAcc=[accel(FR['ChargeRun'][i],FR['ChargeRun'][i+1],FR['ChargeRun'][i+2]) for i in range(15)]
seamAcc=accel(FR['ChargeRun'][15],FR['ChargeRun'][16],FR['ChargeRun'][1])
startAcc=[accel(FR['ChargeStart'][i],FR['ChargeStart'][i+1],FR['ChargeStart'][i+2]) for i in range(17)]
joinAcc=accel(FR['ChargeStart'][17],FR['ChargeStart'][18],FR['ChargeRun'][1])
joins['angularAccelDegPerFrame2']={'runSeam':round(seamAcc,3),'runInteriorMax':round(max(runAcc),3),'startToRunJoin':round(joinAcc,3),'startInteriorMax':round(max(startAcc),3)}
# 5. ChargeRun -> Slam: runtime blend over 0.12 s from every run phase, 60 Hz client frames
blendMs=[];blendStep=(0,None);blendSteps=[]
for k in range(16):
 A=rsample('ChargeRun',k/30,True);prev=A
 for i in range(1,9):
  t=i/60;B=rsample('Slam',t);w=min(1,t/.12)
  P=constrain(rblend(A,B,w));blendMs.append(check_pose(P))
  st=jointstep(prev,P);blendSteps.append(st[0]*2);prev=P
  if os.environ.get('BLENDDBG') and st[0]>25:print('BIGSTEP',k,i,round(st[0],1),st[1],{x:round(blendMs[-1][x],2) for x in ('bend','contact','swivel','forearmHeadDepth')})
print('INSIDE blend',[ (i,m['_insideParts']) for i,m in enumerate(blendMs) if m['_insideParts']][:12])
s,f=summarize(blendMs,'RunToSlamBlend',True);report['ChargeRunToSlam_blend']={'phases':16,'samplesPerPhase':8,'checks':s,'maxJointStepDegPer30HzFrame':round(max(blendSteps),3)};failures+=f
pivMs=[];pivSteps=[]
for k in range(16):
 A=rsample('ChargeRun',k/30,True);prev=A
 for i in range(1,9):
  t=i/60;P=constrain(rblend_pivot(A,rsample('Slam',t),min(1,t/.12)));pivMs.append(check_pose(P));pivSteps.append(jointstep(prev,P)[0]*2);prev=P
s2,f2=summarize(pivMs,'RunToSlamPivotBlend',True)
report['informational_RunToSlam_pivotAwareBlend']={'note':'NOT the shipped runtime; simulation of a joint-pivot lerp (recommended BossMotion.blend change)','checks':s2,'wouldFail':f2,'maxJointStepDegPer30HzFrame':round(max(pivSteps),3)}
print('PIVOTBLEND',json.dumps({m:v['worst'] for m,v in s2.items()}),f2,round(max(pivSteps),1))
# context: the same step metric on existing clips
ctx={}
for name in ('Walk','Slam','Swing'):
 F=[{n:mat(v) for n,v in row.items()} for row in d['clips'][name]['frames']];ctx[name]=round(max(jointstep(F[i],F[i+1])[0] for i in range(len(F)-1)),3)
report['referenceMaxJointStepDegPerFrame_existingClips']=ctx
walkBlend=[]
for k in range(0,48,3):
 A=rsample('Walk',k/30,True)
 for i in range(1,9):
  t=i/60;walkBlend.append(check_pose(constrain(rblend(A,rsample('Slam',t),min(1,t/.12)))))
report['referenceWalkToSlamBlend']={k:round(max(m[k] for m in walkBlend),5) for k in ('contact','bend','legGap','swivel')}
print('WALKBLEND',report['referenceWalkToSlamBlend'])
# context: runtime-interpolation grip/joint behaviour of the existing approved clips
ref={}
for name,looped in (('Walk',True),('Slam',False),('Swing',False),('Spin',False)):
 clip=d['clips'][name];n=int(round(clip['lastFrame']/clip['fps']*120))
 ms=[check_pose(rsample(name,k/120,looped)) for k in range(0,n+1,2)]
 ref[name]={k:round(max(m[k] for m in ms),5) for k in ('contact','bend','legGap')}
report['referenceRuntime120Hz_existingClips']=ref
print('REFRUNTIME',json.dumps(ref))
# 6. planted feet at chargeSpeed
drift={'run':0,'runToeHeight':0,'start':0,'startToeHeight':0};per=SPEED/30
for side,off in (('Right',0),('Left',8)):
 for k in range(16):
  local=((k-off)/16)%1;nxt=((k+1-off)/16)%1
  if local<DUTY-1e-6 and nxt<=DUTY+1e-6 and nxt>local:
   F0=delta(FR['ChargeRun'][k][side+'Foot']);F1=delta(FR['ChargeRun'][k+1][side+'Foot'])
   t0=F0@TOE[side];t1=F1@TOE[side];drift['run']=max(drift['run'],(t1-t0-Vector((0,per,0))).length);drift['runToeHeight']=max(drift['runToeHeight'],abs(t0.z),abs(t1.z))
   if local<DUTY*(1-.4)-1e-6 and nxt<=DUTY*.6+1e-6:
    h0=F0@HEEL[side];h1=F1@HEEL[side];drift['run']=max(drift['run'],(h1-h0-Vector((0,per,0))).length)
for side,frames in (('Right',range(0,11)),('Left',range(7,16))):
 for f in frames:
  t0=delta(FR['ChargeStart'][f][side+'Foot'])@TOE[side];t1=delta(FR['ChargeStart'][f+1][side+'Foot'])@TOE[side]
  drift['start']=max(drift['start'],(t1-t0).length);drift['startToeHeight']=max(drift['startToeHeight'],abs(t0.z),abs(t1.z))
drift['toeTravelPerContact']=SPEED*DUTY*16/30
report['plantedFeet']={k:(round(v,7) if isinstance(v,float) else v) for k,v in drift.items()}
report['plantedFeet']['note']='ChargeRun: planted toe (and heel while flat) moves backward exactly chargeSpeed/30 per frame relative to the root; ChargeStart plays in place, so planted toes must not move at all.'
if drift['run']>.001 or drift['start']>.001 or drift['runToeHeight']>.001 or drift['startToeHeight']>.001:failures.append('planted foot drift')
report['joins']=joins
if joins['startLast_vs_runFirst_maxComponentDiff']>0 or joins['runLast_vs_runFirst_maxComponentDiff']>0 or joins['startFirst_vs_idleFirst_maxComponentDiff']>0:failures.append('join mismatch')
# 7. existing content unchanged
before=json.loads((HERE/'before-charge'/'BossData.json').read_text())
same={c:before['clips'][c]==d['clips'][c] for c in before['clips']}
files={}
for f in (HERE/'before-charge'/'clips').glob('*.luau'):files[f.name]=f.read_bytes()==(OUT/'clips'/f.name).read_bytes()
def digest(action):
 h=hashlib.sha256()
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for fc in sorted(bag.fcurves,key=lambda c:(c.data_path,c.array_index)):
     h.update(f'{fc.data_path}{fc.array_index}'.encode())
     for k in fc.keyframe_points:h.update(('%.7f,%.7f;'%(k.co[0],k.co[1])).encode())
 return h.hexdigest()
built=json.loads((OUT/'charge-build.json').read_text())['existingActionDigestsBefore']
actions={n:digest(bpy.data.actions['Boss_'+n])==h for n,h in built.items()}
report['existingUnchanged']={'clipData':same,'clipLuauBytes':files,'blendActions':actions,'metadataOtherThanChargeSpeed':all(before[k]==d[k] for k in before if k!='clips'),
 'actionsInBlend':sorted(a.name for a in bpy.data.actions)}
if not (all(same.values()) and all(files.values()) and all(actions.values())):failures.append('existing content changed')
report['chargeSpeed']=SPEED
report['failures']=failures
(OUT/'charge-checks.json').write_text(json.dumps(report,indent=1))
print('CHARGE_CHECKS',json.dumps({'failures':failures,'joins':joins,'feet':report['plantedFeet'],'repro':repro}))
for k in ('ChargeStart','ChargeRun','ChargeStart_runtime120Hz','ChargeRun_runtime120Hz','ChargeRunToSlam_blend'):print('SUMMARY',k,json.dumps({m:v['worst'] for m,v in report[k]['checks'].items()}))
print('STEPS',json.dumps({k:report[k].get('maxJointStepDegPerFrame') for k in ('ChargeStart','ChargeRun')}),json.dumps(ctx),report['ChargeRunToSlam_blend']['maxJointStepDegPer30HzFrame'])
