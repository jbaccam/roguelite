import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
ID=sys.argv[sys.argv.index('--')+1];archer=ID=='bow-skeleton';out=reset(ID)
ivory=mat('Aged bone',(.59,.50,.34),.17,12)
shadow=mat('Bone recesses',(.16,.115,.065),.15)
dark=mat('Deep skull cavities',(.008,.006,.004),.1)
leather=mat('Worn leather',(.095,.052,.023),.32,15)
cloth=mat('Ochre cloth' if archer else 'Torn brown hide',(.43,.26,.075) if archer else (.13,.073,.037),.25,11)
steel=mat('Worn dull steel',(.25,.26,.25),.21,14,rough=.69)
stringmat=mat('Waxed flax bowstring',(.70,.61,.43),.04)
objects=[];bones={'Pelvis':[[0,0,2.40],[0,0,3.08],None],'Chest':[[0,0,3.08],[0,0,4.45],'Pelvis'],'Head':[[0,0,4.45],[0,0,5.80],'Chest']}
def add(o,g):objects.append(rigid(o,g));return o
def shaft(name,a,b,r,g):
    a=Vector(a);b=Vector(b)
    pieces=[tube('Bone shaft',[a,a.lerp(b,.13),a.lerp(b,.50),a.lerp(b,.87),b],[r*.81,r,r*.84,r*.86,r*.64],ivory,8)]
    return add(fuse(pieces,name,ivory,.030,650,2),g)
for s in [-1,1]:
    side='Left' if s<0 else 'Right';shoulder=(s*1.03,0,4.20);elbow=(s*1.25,-.035,3.47);wrist=(s*1.40,-.16,2.91)
    shaft('Humerus',shoulder,elbow,.26 if archer else .32,side+'UpperArm')
    shaft('Forearm bones',elbow,wrist,.23 if archer else .29,side+'Forearm')
    add(ell('Elbow joint',elbow,(.20,.21,.19),ivory),side+'Forearm')
    hip=(s*.48,0,2.57);knee=(s*.52,-.02,1.58);ankle=(s*.54,0,.52)
    shaft('Femur',hip,knee,.27 if archer else .34,side+'Thigh')
    shaft('Tibia',knee,ankle,.24 if archer else .31,side+'Shin')
    add(cube('Patella',(s*.52,-.285,1.60),(.36,.18,.32),ivory,.10),side+'Shin')
    add(cube('Tarsal foot',(s*.54,-.12,.28),(.63,.76,.52),ivory,.13),side+'Foot')
    for k in range(3):add(cube('Toe phalanx',(s*.54+(k-1)*.205,-.57,.19),(.18,.36,.31),ivory,.055),side+'Foot')
    # Curved ribs wrap the chest with real negative spaces between them.
    for z,w in [(3.29,.70),(3.59,.83),(3.90,.91),(4.20,.92)]:
        path=[(0,.28,z+.11),(s*w*.72,.32,z+.10),(s*w,.07,z+.03),(s*w*.88,-.26,z-.03),(s*.39,-.48,z-.08),(0,-.49,z-.03)]
        add(tube('Curved rib',path,[.115,.12,.125,.13,.125,.11],ivory,10),'Chest')
    add(tube('Clavicle',[(0,-.31,4.35),(s*.55,-.28,4.38),(s*.96,0,4.25)],[.11,.15,.13],ivory,10),'Chest')
    add(tube('Hip wing',[(0,.17,2.87),(s*.62,.11,2.88),(s*.76,-.04,2.59),(s*.40,-.30,2.47)],[.14,.18,.16,.12],ivory,10),'Pelvis')
    add(mesh('Scapula',[(s*.21,.37,4.17),(s*.77,.37,4.12),(s*.55,.45,3.70),(s*.20,.45,3.82),(s*.21,.47,4.17),(s*.77,.47,4.12),(s*.55,.55,3.70),(s*.20,.55,3.82)],[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],ivory),'Chest')
    for name,a,b,parent in [('UpperArm',shoulder,elbow,'Chest'),('Forearm',elbow,wrist,side+'UpperArm'),('Hand',wrist,(s*1.43,-.37,2.55),side+'Forearm'),('Thigh',hip,knee,'Pelvis'),('Shin',knee,ankle,side+'Thigh'),('Foot',ankle,(s*.54,-.57,.20),side+'Shin')]:bones[side+name]=[a,b,parent]
for z in [2.88,3.11,3.36,3.62,3.88,4.12,4.41]:add(cube('Vertebra',(0,.16,z),(.33,.39,.22),ivory,.06),'Pelvis' if z<3.1 else 'Chest')
add(cube('Sternum',(0,-.48,3.88),(.24,.18,.94),ivory,.055),'Chest')
# Broad cranium and angular inset eye orbits from the reference.
skull=fuse([cube('Skull',(0,0,5.20),(1.58,1.20,1.39),ivory,.25),cube('Upper jaw',(0,-.32,4.76),(1.13,.83,.39),ivory,.12)],'Skull',ivory,.030,3500,2)
for s in [-1,1]:
    cutter=cube('Angular orbit',(s*.35,-.53,5.17),(.56,.48,.50),None,.095);cutter.rotation_euler.y=-s*.13;cut(skull,cutter)
    add(ell('Socket darkness',(s*.35,-.322,5.17),(.23,.025,.21),dark),'Head')
    add(tube('Orbital brow',[(s*.10,-.621,5.41),(s*.33,-.645,5.48),(s*.62,-.537,5.48)],.064,ivory,8),'Head')
cut(skull,mesh('Nasal aperture',[(-.12,-.8,4.98),(.12,-.8,4.98),(0,-.8,5.21),(-.12,-.35,4.98),(.12,-.35,4.98),(0,-.35,5.21)],[(0,2,1),(3,4,5),(0,1,4,3),(1,2,5,4),(2,0,3,5)],None))
add(cube('Nasal darkness',(0,-.32,5.06),(.20,.02,.25),dark,.03),'Head')
add(skull,'Head')
for k in range(6):add(cube('Upper tooth',((k-2.5)*.164,-.702,4.76),(.145,.19,.24),ivory,.042),'Head')
add(cube('Mandible',(0,-.28,4.58),(1.05,.68,.21),ivory,.075),'Head')
# Ragged waist cloth and a hollow belt buckle.
add(cloth_shell('Waist wrap',[(2.00,.78,.49),(2.38,.76,.48),(2.86,.75,.46)],cloth,40,.13),'Pelvis')
add(cloth_shell('Belt',[(2.74,.79,.51),(2.96,.79,.51)],leather,48),'Pelvis')
for x in [-.19,.19]:add(cube('Buckle side',(x,-.551,2.85),(.055,.085,.30),steel,.013),'Pelvis')
for z in [2.70,3.00]:add(cube('Buckle crossbar',(0,-.551,z),(.42,.085,.055),steel,.013),'Pelvis')
grips=[]
if not archer:
    c=Vector((1.44,-.35,2.68));a=Vector((0,-.30,.954)).normalized();u=Vector((1,0,0));v=a.cross(u)
    objects+=grip('Sword hand',c,a,ivory,1,.108,'RightHand')
    add(tube('Sword handle',[c-a*.31,c+a*.31],.108,leather,12),'RightHand')
    guard=c+a*.36;add(tube('Guard',[guard-u*.40,guard+u*.40],.084,steel,8),'RightHand')
    pv=[c+a*.43-u*.24,c+a*.43+u*.24,c+a*1.45+u*.23,c+a*1.77,c+a*1.43-u*.25]
    verts=[p+v*.055 for p in pv]+[p-v*.055 for p in pv]
    add(mesh('Broad sword',verts,[(0,1,2,3,4),(9,8,7,6,5)]+[(i,(i+1)%5,(i+1)%5+5,i+5) for i in range(5)],steel),'RightHand')
    add(ell('Pommel',c-a*.37,(.16,.16,.13),steel,10,8),'RightHand')
    objects+=grip('Relaxed left hand',(-1.44,-.30,2.62),(0,0,1),ivory,-1,.045,'LeftHand')
    grips.append({'bone':'RightHand','center':list(c),'axis':list(a),'handleRadius':.108,'innerFingerRadius':.10384})
else:
    c=Vector((-1.44,-.40,2.72));objects+=grip('Bow grasp',c,(0,0,1),ivory,-1,.105,'LeftHand')
    back=Vector((.55,.835,0)).normalized()
    pts=[c+back*y+Vector((0,0,z)) for y,z in [(.42,-1.50),(-.08,-1.16),(-.19,-.74),(0,-.20),(0,.20),(-.19,.74),(-.08,1.16),(.42,1.50)]]
    add(tube('Recurve bow',pts,[.065,.09,.10,.105,.105,.10,.09,.065],leather,10),'LeftHand')
    bowstring=add(tube('Bowstring',[pts[0],c+back*.42,pts[-1]],.027,stringmat,8),'LeftHand');bowstring['bow_string']=True
    bones['BowDraw']=[list(c+back*.42),list(c+back*.42+Vector((0,0,.2))),'LeftHand']
    for z in [-.33,-.23,.23,.33]:
        pp=c+Vector((0,0,z));rr=[pp+Vector((math.cos(k*math.tau/16)*.115,math.sin(k*math.tau/16)*.115,0)) for k in range(17)]
        add(tube('Grip binding',rr,.025,ivory,6),'LeftHand')
    # The off hand is empty. Arrows are spawned by gameplay at release, not
    # permanently carried in the hand or embedded in the exported mesh.
    rc=Vector((1.44,-.33,2.67));aa=Vector((0,-.45,-.89)).normalized();objects+=grip('Empty drawing hand',rc,aa,ivory,1,.025,'RightHand')
    # Full shoulder shawl and a visible, open-topped quiver.
    add(cloth_shell('Ragged shoulder shawl',[(3.94,1.09,.73),(4.24,1.05,.71),(4.51,.48,.39)],cloth,48,.10),'Chest')
    q0=Vector((.40,.51,3.18));q1=Vector((.69,.73,4.52))
    add(tube('Quiver',[q0,q1],[.19,.24],leather,14),'Chest')
    add(ell('Quiver opening',q1+Vector((0,0,.014)),(.21,.21,.025),dark,16,6),'Chest')
    for k in range(3):
        p=q1+Vector(((k-1)*.13,0,0));add(tube('Stored arrow',[p-Vector((0,0,.3)),p+Vector((.08,0,.55))],.027,leather,8),'Chest')
        add(tube('Fletching',[p+Vector((.055,0,.28)),p+Vector((.08,0,.55))],[.09,.045],ivory,4),'Chest')
    grips += [{'bone':'LeftHand','center':list(c),'axis':[0,0,1],'handleRadius':.105}]
(out/'anatomy.json').write_text(json.dumps({'status':'shape review before rigging','bones':bones,'grips':grips},indent=2))
render(out,objects)
