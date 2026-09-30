"""BossMotion runtime sampling re-implemented in Roblox data space (unscaled):
M.sample (frame lerp + hand-in-hammer-space lerp), M.blend and M.constrainArms.
Needs `d` (BossData) in globals; exec'd whole by validate_charge.py and
render_charge_review.py so the review video shows exactly what was validated."""
import math
from mathutils import Matrix,Vector
T=Matrix.Translation;ROOT=d['rootHeight'];ELBOW_MIN,ELBOW_MAX=12,130
C=Matrix(((-1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1)))
def mat(v):return Matrix(((v[3],v[4],v[5],v[0]),(v[6],v[7],v[8],v[1]),(v[9],v[10],v[11],v[2]),(0,0,0,1)))
def delta(m):return T((0,0,ROOT))@C.inverted()@m@C@T((0,0,-ROOT))
def rjoint(side,n):return Vector(d['joints'][side+n]['head'])-Vector((0,ROOT,0))
def hinge_frame(direction,normal):
 y=direction.normalized();z=normal.normalized();x=y.cross(z).normalized()
 return Matrix((x,y,z)).transposed().to_4x4()
ARMS={}
for side in ('Right','Left'):
 a,b,w=rjoint(side,'UpperArm'),rjoint(side,'LowerArm'),rjoint(side,'Hand');u=b-a;v=w-b;axis=u.cross(v).normalized()
 ARMS[side]=dict(a=a,b=b,w=w,l1=u.length,l2=v.length,axis=axis,restFlex=math.acos(max(-1,min(1,u.normalized().dot(v.normalized())))),frame=hinge_frame(u,axis),pole=Vector((2.2 if side=='Right' else -2.2,-3.5,.35)))
def constrain(P):
 chest=P['UpperTorso']
 for side,A in ARMS.items():
  hand=P[side+'Hand'];shoulder=chest@A['a'];wrist=hand@A['w'];v=wrist-shoulder
  u=v.normalized() if v.length>1e-6 else chest.to_3x3()@Vector((0,-1,0))
  low=math.sqrt(A['l1']**2+A['l2']**2+2*A['l1']*A['l2']*math.cos(math.radians(ELBOW_MAX)))
  high=math.sqrt(A['l1']**2+A['l2']**2+2*A['l1']*A['l2']*math.cos(math.radians(ELBOW_MIN)))
  dist=max(low,min(high,v.length));corrected=shoulder+u*dist
  P[side+'Hand']=T(corrected-wrist)@hand;wrist=corrected
  along=(A['l1']**2-A['l2']**2+dist*dist)/(2*dist)
  pole=chest.to_3x3()@A['pole'];pole-=u*pole.dot(u)
  if pole.length<1e-5:pole=chest.to_3x3()@Vector((1,0,0));pole-=u*pole.dot(u)
  req=P[side+'LowerArm']@A['b']-shoulder;req-=u*req.dot(u)
  sw=math.atan2(u.dot(pole.cross(req)),pole.dot(req));sw=max(-math.radians(75),min(math.radians(75),sw))
  bend=Matrix.Rotation(sw,3,u)@pole.normalized()
  elbow=shoulder+u*along+bend*math.sqrt(max(0,A['l1']**2-along*along))
  upper=elbow-shoulder;lower=wrist-elbow;ax=upper.cross(lower).normalized()
  rot=hinge_frame(upper,ax)@A['frame'].inverted()
  flex=math.acos(max(-1,min(1,upper.normalized().dot(lower.normalized()))))
  P[side+'UpperArm']=T(shoulder)@rot@T(-A['a'])
  P[side+'LowerArm']=T(elbow)@rot@Matrix.Rotation(flex-A['restFlex'],4,A['axis'])@T(-A['b'])
 return P
def lerpcf(a,b,t):
 q=a.to_quaternion().slerp(b.to_quaternion(),t)
 m=q.to_matrix().to_4x4();m.translation=a.translation.lerp(b.translation,t);return m
headRest=mat(d['hammerHeadRest']);gripPivot=headRest@T((-7.3,0,0))
def rblend(a,b,t):
 r={n:lerpcf(m,b[n],t) for n,m in a.items()}
 ha=a['UpperTorso'].inverted()@a['Hammer']@gripPivot;hb=b['UpperTorso'].inverted()@b['Hammer']@gripPivot
 r['Hammer']=r['UpperTorso']@lerpcf(ha,hb,t)@gripPivot.inverted()
 for n in ('RightHand','LeftHand'):r[n]=r['Hammer']@lerpcf(a['Hammer'].inverted()@a[n],b['Hammer'].inverted()@b[n],t)
 return r
FR={name:[{n:mat(v) for n,v in row.items()} for row in d['clips'][name]['frames']] for name in d['clips']}
def rsample(name,time,looped=False):
 clip=d['clips'][name];dur=clip['lastFrame']/clip['fps']
 if looped:time=time%dur
 f=max(0,min(clip['lastFrame'],time*clip['fps']));i=int(math.floor(f));j=min(i+1,len(FR[name])-1);alpha=f%1
 return constrain(rblend(FR[name][i],FR[name][j],alpha))


