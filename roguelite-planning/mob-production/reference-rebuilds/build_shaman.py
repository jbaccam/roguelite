import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
out=reset('ash-shaman')
skin=mat('Ash gray skin',(.18,.16,.17),.12,10)
red=mat('Rust woven robe',(.32,.080,.041),.24,12)
hoodmat=mat('Charcoal hood cloth',(.052,.043,.038),.18,16)
hide=mat('Brown leather',(.14,.086,.049),.26,13)
trim=mat('Leather edges',(.23,.145,.073),.2,16)
bootmat=mat('Boot leather',(.056,.043,.035),.2,12)
dark=mat('Recesses',(.006,.004,.003),.1)
white=mat('Warm eye white',(.68,.57,.39),.07)
amber=mat('Amber iris',(.65,.215,.030),.13)
metal=mat('Buckle metal',(.25,.19,.13),.15,rough=.63)
flame=mat('Fire crystal',(.90,.22,.018),.3,5,rough=.65)
pieces=[];extras=[];bones={'Pelvis':[[0,0,2.05],[0,0,2.80],None],'Chest':[[0,0,2.80],[0,0,3.84],'Pelvis'],'Head':[[0,0,3.84],[0,0,5.17],'Chest']}
pieces += [ell('Torso',(0,0,3.16),(.89,.49,.84),skin),ell('Pelvis',(0,0,2.26),(.73,.44,.55),skin),ell('Neck',(0,0,3.91),(.38,.32,.39),skin)]
for side,s in [('Left',-1),('Right',1)]:
    shoulder=Vector((s*1.02,0,3.65));elbow=Vector((s*1.33,-.15,2.98));wrist=Vector((s*1.49,-.55 if s==-1 else -.40,2.78))
    pieces += [ell('Shoulder',shoulder,(.43,.42,.45),skin),tube('Upper arm',[shoulder,shoulder.lerp(elbow,.55),elbow],[.35,.34,.29],skin,16),ell('Elbow',elbow,(.29,.29,.29),skin),tube('Forearm',[elbow,elbow.lerp(wrist,.5),wrist],[.29,.33,.245],skin,16)]
    if s==1:extras+=grip('Staff grip',(1.53,-.47,2.71),(0,0,1),skin,1,.103,'RightHand')
    else:
        pieces.append(ell('Casting palm',(-1.52,-.76,2.84),(.27,.30,.12),skin))
        for k in range(4):
            xx=-1.52+(k-1.5)*.135
            pieces.append(tube('Open casting finger',[(xx,-.84,2.84),(xx,-1.04,2.90),(xx,-1.13,3.04)],[.081,.080,.055],skin,10))
        pieces.append(tube('Casting thumb',[(-1.26,-.73,2.86),(-1.17,-.88,2.94),(-1.22,-.99,3.02)],[.095,.095,.065],skin,10))
    # Short sturdy legs under loose trousers.
    pieces += [tube('Thigh',[(s*.45,0,2.27),(s*.46,0,1.74),(s*.46,0,1.40)],[.37,.40,.32],skin,16),tube('Shin',[(s*.46,0,1.40),(s*.46,0,.55)],[.31,.28],skin,16)]
    trouser=ell('Trouser leg',(s*.46,.01,1.62),(.43,.44,.72),hoodmat);extras.append(rigid(trouser,side+'Thigh'))
    # Broad toe, heel and overlapping boot shaft instead of rectangular blocks.
    bootparts=[cube('Toe',(s*.46,-.23,.27),(.82,1.06,.52),bootmat,.14),ell('Shaft',(s*.46,.04,.68),(.34,.34,.53),bootmat)]
    boot=fuse(bootparts,'Boot',bootmat,.035,1400,2);extras.append(rigid(boot,side+'Foot'))
    extras.append(rigid(cube('Boot sole',(s*.46,-.23,.075),(.84,1.08,.14),bootmat,.055),side+'Foot'))
    for zz,rr in [(1.03,.41),(.98,.42)]:
        pts=[(s*.46+rr*math.cos(k*math.tau/32),.02+rr*.90*math.sin(k*math.tau/32),zz) for k in range(33)]
        extras.append(rigid(tube('Boot cuff',pts,[(.07,.105)]*33,hide,8),side+'Shin'))
    # Full loose sleeve and a cuff oriented along the bent forearm.
    sleeve=tube('Robe sleeve',[shoulder+Vector((-s*.20,0,.23)),shoulder+Vector((-s*.05,0,.21)),shoulder.lerp(elbow,.55),elbow.lerp(shoulder,.12)],[.42,.54,.47,.40],red,20);extras.append(rigid(sleeve,side+'UpperArm'))
    cuff=tube('Leather forearm cuff',[elbow.lerp(wrist,.24),elbow.lerp(wrist,.79)],[.365,.33],hide,20);extras.append(rigid(cuff,side+'Forearm'))
    for t in [.23,.80]:
        p=elbow.lerp(wrist,t);a=(wrist-elbow).normalized();u=Vector((1,0,0));u=(u-a*u.dot(a)).normalized();v=a.cross(u)
        pts=[p+(u*math.cos(k*math.tau/24)+v*math.sin(k*math.tau/24))*(.375 if t<.5 else .34) for k in range(25)]
        extras.append(rigid(tube('Cuff edge',pts,.028,trim,8),side+'Forearm'))
    for name,p,q,parent in [('UpperArm',shoulder,elbow,'Chest'),('Forearm',elbow,wrist,side+'UpperArm'),('Hand',wrist,Vector((s*1.53,-.91 if s<0 else -.47,2.77)),side+'Forearm'),('Thigh',Vector((s*.45,0,2.20)),Vector((s*.46,0,1.39)),'Pelvis'),('Shin',Vector((s*.46,0,1.39)),Vector((s*.46,0,.47)),side+'Thigh'),('Foot',Vector((s*.46,0,.47)),Vector((s*.46,-.63,.22)),side+'Shin')]:bones[side+name]=[list(p),list(q),parent]
body=fuse(pieces,'Connected shaman body',skin,.035,10000,4);body['smooth_skin']=True
robe=cloth_shell('Fitted robe torso',[(2.49,.80,.50),(2.95,.88,.55),(3.48,.97,.54),(3.87,.82,.43)],red,48,.03,.17);extras.append(rigid(robe,'Chest'))
for s in [-1,1]:
    # Divided flared skirt panels, with real folded volume.
    verts=[(s*.04,-.53,2.64),(s*.78,-.38,2.64),(s*1.12,-.48,1.89),(s*.75,-.62,1.78),(s*.09,-.69,1.89)]
    o=mesh('Front robe panel',verts+[(x,y+.055,z) for x,y,z in verts],[(0,1,2,3,4),(9,8,7,6,5)]+[(i,(i+1)%5,(i+1)%5+5,i+5) for i in range(5)],red);extras.append(rigid(o,'Pelvis'))
rear=cloth_shell('Robe lower drape',[(1.86,1.07,.67),(2.19,.91,.58),(2.63,.79,.51)],red,44,.055);extras.append(rigid(rear,'Pelvis'))
belt=cloth_shell('Wide leather belt',[(2.52,.84,.55),(2.75,.84,.55)],hide,48);extras.append(rigid(belt,'Pelvis'))
for x in [-.19,.19]:extras.append(rigid(cube('Buckle vertical',(x,-.591,2.64),(.055,.08,.31),metal,.013),'Pelvis'))
for z in [2.49,2.79]:extras.append(rigid(cube('Buckle horizontal',(0,-.591,z),(.42,.08,.055),metal,.013),'Pelvis'))
# Adult face, tucked well inside the hood; carved eye sockets and soft jaw.
head=fuse([cube('Cranium',(0,-.035,4.61),(1.36,1.03,1.22),skin,.29),ell('Chin',(0,-.18,4.17),(.49,.42,.26),skin),ell('Nose',(0,-.574,4.49),(.10,.13,.12),skin)],'Shaman face',skin,.027,3000,3);rigid(head,'Head')
for s in [-1,1]:
    cut(head,ell('Socket',(s*.28,-.557,4.63),(.21,.18,.19),None))
    extras.append(rigid(ell('Eye white',(s*.28,-.49,4.62),(.173,.13,.15),white),'Head'))
    extras.append(rigid(ell('Iris',(s*.25,-.613,4.62),(.078,.020,.11),amber),'Head'))
    extras.append(rigid(ell('Pupil',(s*.25,-.631,4.62),(.033,.008,.077),dark),'Head'))
    extras.append(rigid(tube('Brow',[(s*.08,-.594,4.82),(s*.25,-.601,4.86),(s*.46,-.55,4.87)],.042,hoodmat,8),'Head'))
    extras.append(rigid(tube('Upper eyelid',[(s*.11,-.605,4.65),(s*.28,-.643,4.71),(s*.45,-.581,4.72)],[.03,.046,.024],skin,10),'Head'))
# Trim the exposed eyes to the angled lid line rather than leaving white above it.
for eyeobj in [o for o in extras if o.name.startswith(('Eye white','Iris','Pupil'))]:
    s=1 if eyeobj.location.x>0 else -1
    cutter=cube('Lid trim',(s*.28,-.57,5.20),(1.0,.60,1.0),None,0);cutter.rotation_euler.y=-s*.16
    cut(eyeobj,cutter)
extras.append(rigid(tube('Mouth',[(-.13,-.574,4.29),(0,-.58,4.31),(.13,-.574,4.29)],.012,dark,6),'Head'))
# Enclosed, deep hood with a full face opening, thick rim and rear cap.
n=48;verts=[]
for j,(y,rx,rz) in enumerate([(-.78,.89,.80),(-.45,.95,.86),(0,.93,.89),(.43,.77,.78),(.68,.41,.52)]):
    for k in range(n):
        a=k*math.tau/n;fold=1+.022*math.sin(5*a+j*.6);z=4.59+rz*math.sin(a)*fold+.13*max(0,math.sin(a))**8
        verts.append((rx*math.cos(a)*fold,y,z))
# Shape the opening as tailored panels: pointed brow, long cheeks, angular lower
# drape. The former circular rim read as a helmet rather than cloth.
for k in range(n):
    a=k*math.tau/n;x,y,z=verts[k]
    if math.sin(a)>0:
        z=4.38+1.18*(1-abs(math.cos(a))**.70)
        x=.88*math.cos(a)
    else:
        z=3.95-.11*max(0,-math.sin(a));x=.88*math.cos(a)
    verts[k]=(x,y,z)
faces=[(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(4) for k in range(n)];faces.append(tuple(range(4*n,5*n)))
hood=mesh('Deep tailored hood',verts,faces,hoodmat);bpy.context.view_layer.objects.active=hood
mod=hood.modifiers.new('Thick cloth lining','SOLIDIFY');mod.thickness=.075;bpy.ops.object.modifier_apply(modifier=mod.name)
for s in [-1,1]:
    cut(hood,ell('Ear opening',(s*.85,-.05,4.70),(.30,.26,.23),None))
    p=[(s*.63,-.12,4.78),(s*1.25,-.02,4.86),(s*.88,-.13,4.41),(s*.66,-.16,4.40)]
    ear=mesh('Elven ear',p+[(x,y+.16,z) for x,y,z in p],[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],skin);extras.append(rigid(ear,'Head'))
extras.append(rigid(hood,'Head'));extras.append(rigid(tube('Hood stitched rim',verts[:n]+[verts[0]],.027,hide,8),'Head'))
pv=[(-.70,-.42,3.99),(.70,-.42,3.99),(.60,-.63,3.82),(0,-.76,3.52),(-.60,-.63,3.82)]
extras.append(rigid(mesh('Folded cowl',pv+[(x,y+.07,z) for x,y,z in pv],[(0,1,2,3,4),(9,8,7,6,5)]+[(i,(i+1)%5,(i+1)%5+5,i+5) for i in range(5)],hoodmat),'Chest'))
# Staff shaft passes through the closed grasp, with branching crown and fire crystal.
c=Vector((1.53,-.47,2.71))
points=[(c.x+.034*(math.sin(z*1.8)-math.sin(c.z*1.8)),c.y,z) for z in [.09,.8,1.8,2.40,2.71,3.00,3.80,4.35]]
extras.append(rigid(tube('Continuous staff shaft',points,[.072,.075,.087,.103,.103,.103,.105,.13],hide,10),'RightHand'))
for s in [-1,1]:extras.append(rigid(tube('Staff branch',[(c.x,c.y,4.17),(c.x+s*.28,c.y,4.51),(c.x+s*.21,c.y,4.88)],[.14,.10,.03],hide,7),'RightHand'))
gem=ell('Fire crystal',(c.x,c.y,4.69),(.23,.20,.49),flame,7,5);extras.append(rigid(gem,'RightHand'))
for z in [3.93,4.12]:extras.append(rigid(tube('Staff binding',[(c.x-.15,c.y,z),(c.x+.14,c.y,z+.045)],.09,trim,6),'RightHand'))
(out/'anatomy.json').write_text(json.dumps({'status':'shape review before rigging','bones':bones,'grips':[{'bone':'RightHand','center':list(c),'axis':[0,0,1],'handleRadius':.103,'innerFingerRadius':.098} ]},indent=2))
render(out,[body,head]+extras)
