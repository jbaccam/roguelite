import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
from goblin_hands import goblin_hand, finish_skin, GRIP_CENTER, GRIP_AXIS
out=reset('fire-goblin')
skin=mat('Red goblin skin',(.40,.090,.038),.29,11)
inner=mat('Ear folds',(.23,.046,.024),.20,10)
cloth=mat('Charcoal hide vest',(.061,.049,.042),.26,14)
leather=mat('Worn belt',(.14,.077,.036),.24,9)
ivory=mat('Ivory',(.67,.53,.30),.1)
dark=mat('Dark recesses',(.012,.006,.003),.08)
steel=mat('Chipped iron',(.20,.20,.18),.24,10,rough=.67)
white=mat('Warm eyes',(.70,.57,.34),.06)
iris=mat('Brown eyes',(.080,.025,.006),.12,rough=.3)
pieces=[];extras=[];hands=[]
def mass(p,s,name):pieces.append(ell(name,p,s,skin))
mass((0,0,3.13),(.94,.52,.88),'Stocky torso');mass((0,0,2.42),(.82,.47,.64),'Hips');mass((0,0,3.91),(.48,.39,.41),'Neck')
for s in [-1,1]:
    mass((s*1.01,.01,3.70),(.46,.48,.50),'Shoulder')
    mass((s*1.15,.02,3.28),(.38,.39,.57),'Upper arm')
    mass((s*1.28,-.05,2.94),(.31,.33,.34),'Elbow')
    mass((s*1.40,-.10,2.68),(.40,.40,.43),'Heavy forearm')
    mass((s*1.47,-.12,2.40),(.23,.24,.26),'Wrist')
    mass((s*.48,0,1.92),(.43,.43,.58),'Thigh')
    mass((s*.50,-.02,1.41),(.34,.35,.34),'Knee')
    mass((s*.51,.01,.93),(.36,.37,.55),'Shin')
    pieces.append(cube('Bare foot',(s*.51,-.21,.26),(.79,1.02,.51),skin,.16))
    for k in range(3):mass((s*.51+(k-1)*.225,-.66,.21),(.15,.19,.18),'Toe')
    hands.append(goblin_hand(s,skin))
body=fuse(pieces,'Stocky goblin anatomy',skin,.044,12000,4)
# The wrists and palms share one skin surface; there is no overlapping cuff.
body=fuse([body]+hands,'Stocky goblin anatomy',skin,.013,19500,3);body['smooth_skin']=True
cut(body,tube('Final leather grip clearance',[GRIP_CENTER-GRIP_AXIS*.48,GRIP_CENTER+GRIP_AXIS*.48],.136,None,32))
for s in [-1,1]:
    for off in [-.11,.11]:cut(body,cube('Toe cleft',(s*.51+off,-.69,.22),(.024,.23,.30),None,.008))
finish_skin(body)
headparts=[cube('Large skull',(0,-.06,4.56),(1.58,1.22,1.37),skin,.27),cube('Lower jaw',(0,-.27,4.10),(1.44,.99,.43),skin,.17)]
for s in [-1,1]:
    b=cube('Angled brow',(s*.34,-.635,4.80),(.73,.25,.19),skin,.065);b.rotation_euler.y=-s*.23;headparts.append(b)
    headparts.append(ell('Cheek',(s*.55,-.43,4.34),(.25,.32,.32),skin))
headparts.append(cube('Nose',(0,-.683,4.39),(.43,.35,.27),skin,.08))
head=fuse(headparts,'Goblin face',skin,.029,3900,3);rigid(head,'Head')
for s in [-1,1]:
    cut(head,ell('Recessed socket',(s*.34,-.644,4.61),(.24,.24,.205),None))
    extras.append(rigid(ell('Eye white',(s*.34,-.551,4.59),(.193,.161,.168),white),'Head'))
    extras.append(rigid(ell('Iris',(s*.31,-.704,4.59),(.080,.024,.112),iris),'Head'))
    extras.append(rigid(ell('Pupil',(s*.31,-.725,4.59),(.040,.008,.066),dark),'Head'))
    extras.append(rigid(tube('Tusk',[(s*.45,-.752,4.13),(s*.48,-.792,4.26),(s*.45,-.782,4.37)],[.086,.064,.003],ivory,10),'Head'))
    # A thick pointed ear rim enclosing an actual recessed inner surface.
    front=[(s*.63,-.07,4.77),(s*1.48,.035,4.88),(s*1.02,-.09,4.30),(s*.67,-.13,4.26)]
    back=[(x,y+.20,z) for x,y,z in front]
    ear=mesh('Pointed ear',front+back,[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],skin)
    cut(ear,ell('Ear hollow',(s*.93,-.098,4.57),(.31,.12,.18),None))
    extras.append(rigid(ear,'Head'))
    earfold=mesh('Inner ear',[(s*.78,-.015,4.68),(s*1.26,.05,4.78),(s*.98,-.005,4.43)],[(0,1,2)],inner)
    bpy.context.view_layer.objects.active=earfold
    mod=earfold.modifiers.new('Inner ear thickness','SOLIDIFY');mod.thickness=.018;bpy.ops.object.modifier_apply(modifier=mod.name)
    extras.append(rigid(earfold,'Head'))
    # Low angled lids cover the upper eyeball; the gaze is wary, not surprised.
    lid=tube('Sculpted heavy eyelid',[(s*.10,-.73,4.64),(s*.35,-.745,4.73),(s*.58,-.65,4.80)],[.055,.072,.04],skin,8)
    extras.append(rigid(lid,'Head'))
extras.append(rigid(tube('Mouth crease',[(-.47,-.756,4.15),(-.19,-.795,4.12),(.16,-.795,4.12),(.44,-.758,4.18)],.015,dark,8),'Head'))
vest=cloth_shell('Sleeveless ragged vest',[(2.61,.87,.51),(2.94,.94,.56),(3.40,.99,.58),(3.84,.87,.50)],cloth,48,.055,.42);rigid(vest,'Chest');extras.append(vest)
skirt=cloth_shell('Short torn tunic',[(1.96,1.0,.58),(2.21,.94,.54),(2.64,.85,.50)],cloth,40,.12,0);rigid(skirt,'Pelvis');extras.append(skirt)
belt=cloth_shell('Leather belt',[(2.54,.88,.55),(2.77,.89,.55)],leather,48);rigid(belt,'Pelvis');extras.append(belt)
for x in [-.20,.20]:extras.append(rigid(cube('Buckle side',(x,-.585,2.65),(.056,.09,.31),steel,.016),'Pelvis'))
for z in [2.50,2.80]:extras.append(rigid(cube('Buckle edge',(0,-.585,z),(.43,.09,.054),steel,.013),'Pelvis'))
for x in [.34,.48,.61]:extras.append(rigid(ell('Belt hole',(x,-.538,2.65),(.023,.013,.024),dark,12,8),'Pelvis'))
# Short chipped blade. Grip and handle share the same measured center and axis.
c=GRIP_CENTER.copy();a=GRIP_AXIS.copy();u=Vector((0,0,1));u=(u-a*a.dot(u)).normalized();v=a.cross(u)
extras.append(rigid(tube('Sword grip',[c-a*.30,c+a*.30],.108,leather,12),'RightHand'))
for j in range(5):
    p=c+a*(-.25+j*.10);pts=[p+(u*math.cos(k*math.tau/16)+v*math.sin(k*math.tau/16))*.114 for k in range(17)]
    extras.append(rigid(tube('Grip wrapping',pts,.020,cloth,6),'RightHand'))
guard=c+a*.375
extras.append(rigid(tube('Swept dagger guard',[guard-u*.30+a*.07,guard-u*.20,guard,guard+u*.20,guard+u*.30-a*.04],[.040,.061,.071,.061,.040],steel,8),'RightHand'))
extras.append(rigid(tube('Dagger pommel',[c-a*.30,c-a*.39],[.135,.105],steel,10),'RightHand'))
blade_metal=mat('Forged dagger steel',(.24,.265,.28),.09,35,rough=.38)
blade_metal.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value=.72
edge_metal=mat('Honed cutting bevel',(.49,.52,.53),.04,42,rough=.27)
edge_metal.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value=.78
# Diamond section with broad forged faces, narrow honed edges and a pointed tip.
verts=[]
for along,width,thick in [(.42,.16,.065),(.56,.195,.070),(1.06,.145,.051),(1.31,.067,.029)]:
    for x,y in [(-1,0),(-.78,.42),(0,1),(.78,.42),(1,0),(.78,-.42),(0,-1),(-.78,-.42)]:
        verts.append(c+a*along+u*(x*width)+v*(y*thick))
verts.append(c+a*1.51-u*.028)
faces=[tuple(range(7,-1,-1))]+[(j*8+k,j*8+(k+1)%8,(j+1)*8+(k+1)%8,(j+1)*8+k) for j in range(3) for k in range(8)]+[(24+k,24+(k+1)%8,32) for k in range(8)]
blade=mesh('Tapered ridge dagger',verts,faces,blade_metal);blade.data.materials.append(edge_metal)
for poly in blade.data.polygons:
    if poly.index>0 and (poly.index-1)%8 in (0,3,4,7):poly.material_index=1
extras.append(rigid(blade,'RightHand'))
bones={'Pelvis':[[0,0,2.18],[0,0,2.90],None],'Chest':[[0,0,2.90],[0,0,3.86],'Pelvis'],'Head':[[0,0,3.86],[0,0,5.13],'Chest']}
for side,s in [('Left',-1),('Right',1)]:
    for name,p,q,parent in [('UpperArm',(s*.96,0,3.73),(s*1.28,-.05,2.94),'Chest'),('Forearm',(s*1.28,-.05,2.94),(s*1.47,-.14,2.31),side+'UpperArm'),('Hand',(s*1.47,-.14,2.31),(s*1.49,-.24,1.98),side+'Forearm'),('Thigh',(s*.47,0,2.24),(s*.50,0,1.40),'Pelvis'),('Shin',(s*.50,0,1.40),(s*.51,0,.48),side+'Thigh'),('Foot',(s*.51,0,.48),(s*.51,-.60,.22),side+'Shin')]:bones[side+name]=[p,q,parent]
(out/'anatomy.json').write_text(json.dumps({'status':'shape review before rigging','bones':bones,'grips':[{'bone':'RightHand','center':list(c),'axis':list(a),'handleRadius':.108,'contactChannelRadius':.136}],'hands':'Continuous sculpted fists with transverse grasp, curled finger pads, integrated thumb web and wrist'},indent=2))
render(out,[body,head]+extras)
