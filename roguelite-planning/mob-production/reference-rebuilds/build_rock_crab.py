import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
out=reset('rock-throwing-crab')
shell=mat('Slate teal carapace',(.10,.20,.21),.32,9)
edge=mat('Shell rim',(.19,.29,.29),.21,12)
cream=mat('Segmented underside',(.49,.41,.24),.16,10)
joint=mat('Crustacean joint',(.071,.088,.075),.16,11)
tipmat=mat('Dark claw tips',(.066,.10,.12),.24,12)
eyes=mat('Glossy black eye',(.012,.007,.004),.05,rough=.22)
stone=mat('Beach rock',(.30,.29,.26),.31,11)
objects=[];bones={'Body':[[0,0,.91],[0,0,1.58],None]}
def add(o,g='Body'):objects.append(rigid(o,g));return o
# Broad angular oval carapace with pointed side extensions.
n=32;vv=[]
for j,(rx,ry,z) in enumerate([(1.28,.93,1.18),(1.49,1.02,1.34),(.93,.69,1.66),(.38,.33,1.75)]):
    for k in range(n):
        a=k*math.tau/n;rr=1+(.045*math.cos(8*a) if j==1 else .02*math.sin(5*a))
        vv.append((rx*math.cos(a)*rr,ry*math.sin(a)*rr,z+.035*math.sin(3*a+j)))
ff=[tuple(range(n-1,-1,-1))]
for j in range(3):
    for k in range(n):ff.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
ff.append(tuple(range(3*n,4*n)))
add(mesh('Broad armored carapace',vv,ff,shell))
add(ell('Abdominal underside',(0,.05,1.00),(1.10,.85,.43),cream,24,12))
for k in range(5):
    x=(k-2)*.31;add(ell('Front abdominal plate',(x,-.705,1.035),(.24,.10,.30),cream,8,5))
for k in range(3):add(ell('Lower ventral segment',(0,-.55,.83-k*.13),(.61-k*.13,.18,.13),cream,12,6))
add(tube('Carapace edge',vv[n:2*n]+[vv[n]],.034,edge,6))
for s in [-1,1]:
    for j in range(4):
        y=-.45+j*.39;root=Vector((s*.91,y,1.04));knee=Vector((s*(1.51+.10*math.sin(j)),y+(j-1.5)*.13,.98));ankle=Vector((s*(1.89+.09*math.sin(j)),y+(j-1.5)*.24,.38));end=Vector((s*(1.95+.10*math.sin(j)),y+(j-1.5)*.29,.055))
        side='Left' if s==1 else 'Right';upper=f'{side}Leg{j}Upper';lower=f'{side}Leg{j}Lower'
        bones[upper]=[list(root),list(knee),'Body'];bones[lower]=[list(knee),list(end),upper]
        add(ell('Hip joint',root,(.22,.22,.22),joint),upper)
        add(tube('Leg upper', [root,root.lerp(knee,.48)+Vector((0,0,.14)),knee],[.22,.25,.16],shell,10),upper)
        add(ell('Leg hinge',knee,(.18,.18,.18),joint),lower)
        add(tube('Leg lower',[knee,ankle,end],[.215,.16,.028],shell,10),lower)
        add(tube('Pointed dark foot',[ankle,end],[.16,.012],tipmat,8),lower)
    p=Vector((s*.48,-.49,1.72));q=Vector((s*.59,-.61,2.04))
    add(tube('Eye stalk',[p,q],[.105,.08],edge,10));add(ell('Eyeball',q+Vector((0,-.035,.09)),(.14,.125,.17),eyes,20,12))
    for j in range(3):
        p=(s*(1.11+.1*j),-.48+j*.36,1.43)
        add(tube('Shell spine',[p,(p[0]+s*.11,p[1],p[2]+.18)],[.11,.004],tipmat,5))
# Raised dominant claw: fingers wrap opposite sides of the rock, not its underside.
a=Vector((-1.05,-.54,1.21));b=Vector((-1.45,-.70,1.83));c=Vector((-1.76,-.79,2.41));rockcenter=Vector((-1.76,-.82,3.35))
bones['RightArm']=[list(a),list(b),'Body'];bones['RightForearm']=[list(b),list(c),'RightArm'];bones['RightClaw']=[list(c),[-1.76,-.79,3.05],'RightForearm'];bones['RightPincer']=[[-1.48,-.80,2.74],[-1.32,-.81,3.35],'RightClaw']
add(tube('Raised upper arm',[a,a.lerp(b,.5),b],[.27,.31,.23],shell,12),'RightArm');add(ell('Raised elbow',b,(.24,.24,.24),joint),'RightForearm')
add(tube('Raised forearm',[b,b.lerp(c,.6),c],[.26,.31,.25],shell,12),'RightForearm')
add(ell('Dominant claw palm',(-1.77,-.79,2.69),(.43,.36,.41),shell,20,12),'RightClaw')
fixed=[(-1.99,-.80,2.83),(-2.17,-.82,3.08),(-2.23,-.82,3.33),(-2.13,-.82,3.58),(-1.98,-.82,3.75)]
moving=[(-1.48,-.81,2.78),(-1.30,-.81,3.06),(-1.30,-.81,3.32),(-1.39,-.81,3.56),(-1.51,-.81,3.70)]
add(tube('Fixed enclosing pincer',fixed,[.26,.23,.19,.13,.028],shell,10),'RightClaw');add(tube('Opposing enclosing pincer',moving,[.23,.22,.18,.12,.025],shell,10),'RightPincer')
add(tube('Dark fixed tip',fixed[2:],[.195,.133,.029],tipmat,10),'RightClaw');add(tube('Dark opposing tip',moving[2:],[.185,.123,.026],tipmat,10),'RightPincer')
rock=ell('Held rock',rockcenter,(.39,.355,.405),stone,12,8)
for v in rock.data.vertices:v.co*=random.uniform(.91,1.09)
add(rock,'RightClaw');rock['held_projectile']=True
# Smaller free claw extends forward beside the body.
a=Vector((1.04,-.53,1.20));b=Vector((1.46,-.80,1.27));c=Vector((1.76,-1.08,1.32))
bones['LeftArm']=[list(a),list(b),'Body'];bones['LeftClaw']=[list(b),list(c),'LeftArm'];bones['LeftPincer']=[[1.61,-1.20,1.29],[1.55,-1.61,1.27],'LeftClaw']
add(tube('Free arm',[a,b],[.24,.24],shell,12),'LeftArm');add(ell('Free claw palm',c,(.34,.34,.31),shell,18,10),'LeftClaw')
add(tube('Free fixed finger',[(1.97,-1.16,1.33),(2.07,-1.48,1.34),(1.97,-1.79,1.30),(1.78,-1.96,1.26)],[.21,.19,.12,.018],shell,10),'LeftClaw')
add(tube('Free moving finger',[(1.59,-1.22,1.29),(1.49,-1.54,1.28),(1.57,-1.82,1.25),(1.72,-1.93,1.24)],[.18,.16,.10,.012],tipmat,10),'LeftPincer')
(out/'anatomy.json').write_text(json.dumps({'status':'shape review before rigging','bones':bones,'crab':True,'rockContact':{'rockCenter':list(rockcenter),'rockRadii':[.39,.355,.405],'fixedJawMid':fixed[2],'fixedJawRadius':.19,'movingJawMid':moving[2],'movingJawRadius':.18,'heldBone':'RightClaw','releaseRequiresProjectileSpawn':True}},indent=2))
render(out,objects,aim_at=(0,-.05,1.88),size=4.9)
