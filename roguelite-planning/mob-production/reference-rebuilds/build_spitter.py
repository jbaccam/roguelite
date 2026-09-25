import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
out=reset('spitter-zombie')
skin=mat('Pale olive undead skin',(.29,.31,.15),.30,14)
shirtmat=mat('Rotten brown shirt',(.14,.092,.058),.38,17)
shortmat=mat('Dark worn shorts',(.084,.054,.035),.30,15)
dark=mat('Mouth and sockets',(.020,.013,.007),.14)
eye=mat('Clouded pale eyes',(.63,.56,.35),.05,rough=.44)
tooth=mat('Uneven teeth',(.53,.43,.23),.21)
pieces=[];extras=[]
def mass(p,s,name):pieces.append(ell(name,p,s,skin))
mass((0,0,3.74),(1.10,.64,1.05),'Heavy ribcage');mass((0,-.36,3.24),(1.10,.76,.98),'Round abdomen');mass((0,-.69,3.11),(.91,.59,.75),'Hanging belly');mass((0,.03,2.54),(.99,.60,.61),'Pelvis');mass((0,.02,4.55),(.49,.41,.41),'Neck')
for s in [-1,1]:
    mass((s*1.18,0,4.08),(.52,.50,.59),'Shoulder');mass((s*1.33,.01,3.72),(.43,.42,.61),'Upper arm');mass((s*1.44,-.025,3.26),(.35,.34,.33),'Elbow');mass((s*1.53,-.04,2.94),(.41,.40,.55),'Forearm');mass((s*1.59,-.08,2.60),(.28,.29,.28),'Wrist')
    pieces+=grip('Loose swollen hand',(s*1.60,-.17,2.38),(0,0,1),skin,s,.165)
    mass((s*.59,.03,2.26),(.50,.49,.65),'Thigh');mass((s*.63,-.015,1.70),(.38,.40,.35),'Knee');mass((s*.65,.05,1.10),(.42,.43,.70),'Calf');mass((s*.65,0,.54),(.32,.34,.32),'Ankle')
    pieces.append(cube('Bare foot',(s*.65,-.23,.28),(.86,1.19,.55),skin,.16))
    for k in range(3):mass((s*.65+(k-1)*.24,-.75,.23),(.16,.21,.20),'Toe')
body=fuse(pieces,'Continuous spitter anatomy',skin,.042,14000,5);body['smooth_skin']=True
for s in [-1,1]:
    for off in [-.12,.12]:cut(body,cube('Toe cleft',(s*.65+off,-.77,.23),(.025,.30,.34),None,.01))
# Garments are extracted from the body surface, so the ragged opening follows the belly.
def garment(name,material,select):
    source=body.data;faces=[];used=set()
    for p in source.polygons:
        if select(p.center):faces.append(tuple(p.vertices));used.update(p.vertices)
    # Separate disconnected face fans meeting at a single ragged hem vertex.
    # Solidifying those pinches otherwise creates four-face nonmanifold edges.
    incident={v:[] for v in used}
    for fi,face in enumerate(faces):
        for v in face:incident[v].append(fi)
    mapping={};verts=[]
    for v,fis in incident.items():
        unseen=set(fis)
        while unseen:
            seed=unseen.pop();stack=[seed];fan=[seed]
            while stack:
                current=stack.pop()
                for other in list(unseen):
                    if len(set(faces[current]) & set(faces[other]))>=2:unseen.remove(other);stack.append(other);fan.append(other)
            index=len(verts);verts.append(source.vertices[v].co+source.vertices[v].normal*.06)
            for fi in fan:mapping[(fi,v)]=index
    o=mesh(name,verts,[tuple(mapping[(fi,v)] for v in face) for fi,face in enumerate(faces)],material);bpy.context.view_layer.objects.active=o
    mod=o.modifiers.new('Fabric edge thickness','SOLIDIFY');mod.thickness=.042;bpy.ops.object.modifier_apply(modifier=mod.name);o['transfer_skin']=True;return o
def shirtselect(p):
    x,y,z=p
    hem=2.77+.085*math.sin(x*15+y*11)
    if z<hem or z>4.60:return False
    if abs(x)>1.04 and z<3.65+.075*math.sin(y*14+x*10):return False
    if abs(x)<.66 and y<-.20 and z>4.24+.15*abs(x)/.66:return False
    theta=math.atan2((z-3.15)/.67,x/.94)
    if y<-.72 and (x/.94)**2+((z-3.15)/.67)**2<1+.075*math.sin(theta*9):return False
    return True
extras.append(garment('Tattered shirt fitted to belly',shirtmat,shirtselect))
extras.append(garment('Ragged shorts',shortmat,lambda p:abs(p.x)<1.10 and 1.70+.09*math.sin(p.x*17+p.y*11)<p.z<2.85))
headpieces=[cube('Tall cranium',(0,-.04,5.26),(1.65,1.28,1.48),skin,.26),ell('Lower jaw',(0,-.28,4.85),(.74,.52,.34),skin)]
for s in [-1,1]:
    headpieces.append(ell('Swollen cheek',(s*.59,-.66,4.99),(.38,.41,.46),skin))
    headpieces.append(cube('Ear',(s*.87,-.02,5.28),(.26,.32,.40),skin,.09))
    brow=cube('Heavy angry brow',(s*.34,-.69,5.54),(.74,.29,.21),skin,.07);brow.rotation_euler.y=-s*.20;headpieces.append(brow)
headpieces.append(ell('Nose',(0,-.73,5.19),(.18,.18,.20),skin))
head=fuse(headpieces,'Swollen zombie face',skin,.028,5000,4);rigid(head,'Head')
for s in [-1,1]:
    cut(head,ell('Eye socket',(s*.35,-.708,5.36),(.24,.26,.21),None))
    extras.append(rigid(ell('Sunken pale eyeball',(s*.35,-.635,5.36),(.17,.16,.163),eye),'Head'))
mouth=cube('Open mouth cavity',(0,-.785,4.99),(.78,.59,.43),None,.12);cut(head,mouth)
extras.append(rigid(cube('Mouth darkness',(0,-.51,4.99),(.69,.035,.37),dark,.075),'Head'))
for k in range(6):
    x=(k-2.5)*.114;h=.065+random.random()*.06
    t=cube('Upper broken tooth',(x,-.772,5.16-h/2),(.077,.13,h),tooth,.019);t.rotation_euler.y=random.uniform(-.18,.18);extras.append(rigid(t,'Head'))
for k in range(5):
    x=(k-2)*.12;h=.065+random.random()*.065
    t=cube('Lower broken tooth',(x,-.764,4.82+h/2),(.075,.12,h),tooth,.018);t.rotation_euler.y=random.uniform(-.2,.2);extras.append(rigid(t,'Head'))
bones={'Pelvis':[[0,0,2.49],[0,0,3.19],None],'Chest':[[0,0,3.19],[0,0,4.54],'Pelvis'],'Head':[[0,0,4.54],[0,0,5.89],'Chest']}
for side,s in [('Left',-1),('Right',1)]:
    for name,a,b,parent in [('UpperArm',(s*1.16,0,4.11),(s*1.44,-.025,3.26),'Chest'),('Forearm',(s*1.44,-.025,3.26),(s*1.59,-.08,2.61),side+'UpperArm'),('Hand',(s*1.59,-.08,2.61),(s*1.61,-.18,2.18),side+'Forearm'),('Thigh',(s*.58,0,2.56),(s*.63,0,1.70),'Pelvis'),('Shin',(s*.63,0,1.70),(s*.65,0,.47),side+'Thigh'),('Foot',(s*.65,0,.47),(s*.65,-.69,.23),side+'Shin')]:bones[side+name]=[a,b,parent]
(out/'anatomy.json').write_text(json.dumps({'status':'shape review before rigging','bones':bones},indent=2))
render(out,[body,head]+extras)
