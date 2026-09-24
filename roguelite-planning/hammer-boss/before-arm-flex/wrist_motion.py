"""Two-hand grip roll and elbow solve; the contact axis stays on the shaft."""
ELBOW_MIN=math.radians(8)
ELBOW_MAX=math.radians(130)

def elbow_hinge(side,shoulder,wrist,l1,l2,chest,swivel=0):
 # The elbow plane belongs to the upper arm/body, NEVER to the hand roll.
 # A down/out pole keeps the elbow below and outside the shoulder when the
 # grip is carried in front, and preserves the same anatomical bend branch.
 s=-1 if side=='Right' else 1
 pole=shoulder+chest.to_3x3()@Vector((s*2.2,.35,-3.5))
 v=wrist-shoulder;distance=v.length;u=v.normalized()
 low=math.sqrt(l1*l1+l2*l2+2*l1*l2*math.cos(ELBOW_MAX))
 high=math.sqrt(l1*l1+l2*l2+2*l1*l2*math.cos(ELBOW_MIN))
 d=max(low,min(high,distance));along=(l1*l1-l2*l2+d*d)/(2*d)
 bend=pole-shoulder;bend-=u*bend.dot(u);bend.normalize()
 bend=Matrix.Rotation(max(-math.radians(75),min(math.radians(75),swivel)),3,u)@bend
 elbow=shoulder+u*along+bend*math.sqrt(max(0,l1*l1-along*along))
 return elbow,abs(distance-d)

def hinge_frames(a,b,w,shoulder,elbow,wrist):
 # Transport ONE elbow hinge frame through both bones. Independently
 # shortest-arc rotating the two meshes had twisted the visible elbow.
 def frame(direction,normal):
  y=direction.normalized();z=normal.normalized();x=y.cross(z).normalized()
  return Matrix((x,y,z)).transposed()
 upper=b-a;lower=w-b;restAxis=upper.cross(lower).normalized()
 liveUpper=elbow-shoulder;liveLower=wrist-elbow
 liveAxis=liveUpper.cross(liveLower).normalized()
 U=frame(liveUpper,liveAxis)@frame(upper,restAxis).transposed()
 restFlex=upper.angle(lower);flex=liveUpper.angle(liveLower)
 L=U@Matrix.Rotation(flex-restFlex,3,restAxis)
 return T(shoulder)@U.to_4x4()@T(-a),T(elbow)@L.to_4x4()@T(-b)

def grip_arm(side,weapon,offset,chest,previous=None):
 s=-1 if side=='Right' else 1
 a=joints[side+'UpperArm']['head'];b=joints[side+'LowerArm']['head'];w=joints[side+'Hand']['head']
 shoulder=chest@a;l1=(b-a).length;l2=(w-b).length
 base=weapon@offset;H=weapon@HT
 localGrip=HT.inverted()@offset@HT@Vector((2.72 if s<0 else 8.05,0,0))
 center=H@localGrip;axis=(H.to_3x3()@Vector((1,0,0))).normalized()
 cuff=(HT.to_3x3()@Vector((0,0,1))).normalized()
 inv=chest.inverted();best=None
 for degrees in range(-180,181,2):
  angle=math.radians(degrees)
  hand=around(center,Matrix.Rotation(angle,4,axis))@base
  wrist=hand@w;direction=(hand.to_3x3()@cuff).normalized()
  elbow,err=elbow_hinge(side,shoulder,wrist,l1,l2,chest)
  bend=(elbow-wrist).normalized().angle(direction)
  clearance=0
  for k in range(9):
   p=inv@elbow.lerp(wrist,k/8)
   q=(p.x/2.25)**2+((p.y+.15)/1.7)**2+((p.z-6.5)/2.15)**2
   clearance+=max(0,1.3-q)**2
  score=bend*bend+err*err*40+clearance*12+angle*angle*.002
  if previous is not None:score+=math.radians(degrees-previous)**2*.002
  if best is None or score<best[0]:best=(score,hand,elbow,err,math.degrees(bend),degrees)
 return best[1:]

def solve_grips(weapon,offsets,chest,history,grounded=False,sweepWeight=0):
 """Solve weapon placement and both wrist rolls together, with continuity."""
 inv=chest.inverted();cuff=HT.to_3x3()@Vector((0,0,1))
 def evaluate(values):
  W=weapon.copy();shift=chest.to_3x3()@Vector(values[:3])
  if grounded:shift.z=0
  W.translation+=shift;H=W@HT
  axis=(H.to_3x3()@Vector((1,0,0))).normalized();solutions={};score=sum(x*x for x in values[:3])*.03
  score+=(H.translation.z-4.6)**2*5000*sweepWeight*sweepWeight
  for i,(side,g) in enumerate([('Right',2.72),('Left',8.05)]):
   a=joints[side+'UpperArm']['head'];b=joints[side+'LowerArm']['head'];w=joints[side+'Hand']['head']
   center=W@offsets[side]@HT@Vector((g,0,0))
   hand=around(center,Matrix.Rotation(values[3+i],4,axis))@W@offsets[side]
   wrist=hand@w;direction=(hand.to_3x3()@cuff).normalized()
   elbow,err=elbow_hinge(side,chest@a,wrist,(b-a).length,(w-b).length,chest,values[5+i])
   bend=(elbow-wrist).normalized().angle(direction)
   score+=max(0,bend-math.radians(18))**2*120+bend*bend*.04+err*err*20000
   for k in range(9):
    p=inv@elbow.lerp(wrist,k/8);q=(p.x/2.25)**2+((p.y+.15)/1.7)**2+((p.z-6.5)/2.15)**2
    score+=max(0,1.3-q)**2*1000
   if side in history:
    score+=(inv@elbow-history[side]['elbow']).length_squared*4.0
    diff=(values[3+i]-history[side]['roll']+math.pi)%math.tau-math.pi
    score+=diff*diff*.025
   score+=values[5+i]**2*.02
   solutions[side]=(hand,elbow,err,bend,values[3+i],values[5+i])
  return score,W,solutions
 initial=list(history.get('_shift',[0.,0.,0.]))+[history.get(side,{}).get('roll',0.) for side in ('Right','Left')]+[history.get(side,{}).get('swivel',0.) for side in ('Right','Left')]
 # Independent coarse rolls are a second seed, avoiding a bad local branch.
 seeds=[initial]
 seeds.append([0.,0.,0.]+[math.radians(grip_arm(side,weapon,offsets[side],chest)[4]) for side in ('Right','Left')]+[0.,0.])
 best=None
 for values in seeds:
  current=evaluate(values)
  for positionStep,angleStep in [(.4,20),(.2,10),(.1,5),(.04,2),(.01,.5)]:
   for repeat in range(12):
    changed=False
    for index in range(7):
     if grounded and index==2:continue
     for sign in (-1,1):
      trial=values.copy();trial[index]+=sign*(positionStep if index<3 else math.radians(angleStep))
      if index<3 and abs(trial[index])>4.0:continue
      if index>=5 and abs(trial[index])>math.radians(75):continue
      result=evaluate(trial)
      if result[0]<current[0]:values,current=trial,result;changed=True
    if not changed:break
  if best is None or current[0]<best[0]:best=current;bestValues=values.copy()
 # Projection is mandatory, not a score penalty: preserve exact bone
 # lengths and joint limits even when the wrist objective is infeasible.
 W=best[1]
 for iteration in range(160):
  worst=0
  for side,g in [('Right',2.72),('Left',8.05)]:
   a=joints[side+'UpperArm']['head'];b=joints[side+'LowerArm']['head'];w=joints[side+'Hand']['head']
   axis=(W.to_3x3()@HT.to_3x3()@Vector((1,0,0))).normalized();center=W@offsets[side]@HT@Vector((g,0,0))
   hand=around(center,Matrix.Rotation(best[2][side][4],4,axis))@W@offsets[side]
   v=hand@w-chest@a;d=v.length;l1=(b-a).length;l2=(w-b).length
   low=math.sqrt(l1*l1+l2*l2+2*l1*l2*math.cos(ELBOW_MAX-.001))
   high=math.sqrt(l1*l1+l2*l2+2*l1*l2*math.cos(ELBOW_MIN+.001))
   correction=max(low,min(high,d))-d;worst=max(worst,abs(correction))
   direction=v.normalized()
   if grounded:direction.z=0
   W.translation+=direction*(correction/max(direction.length_squared,.001))
  if worst<.000001:break
 shift=chest.to_3x3().transposed()@(W.translation-weapon.translation)
 bestValues[:3]=list(shift);best=evaluate(bestValues)
 history['_shift']=bestValues[:3]
 for side,(hand,elbow,err,bend,roll,swivel) in best[2].items():history[side]={'roll':roll,'elbow':inv@elbow,'swivel':swivel}
 return best[1],best[2]
