import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
out=reset('obsidian-ogre')
stone=mat('Obsidian stone',(.080,.068,.079),.24,24)
nodes=stone.node_tree.nodes;links=stone.node_tree.links
next(n for n in nodes if n.type=='VALTORGB').color_ramp.interpolation='CONSTANT'
grain=nodes.new('ShaderNodeTexNoise');grain.inputs['Scale'].default_value=105;grain.inputs['Detail'].default_value=3.2;grain.inputs['Roughness'].default_value=.8
crag=nodes.new('ShaderNodeBump');crag.inputs['Strength'].default_value=.52;crag.inputs['Distance'].default_value=.038
links.new(grain.outputs['Fac'],crag.inputs['Height']);links.new(crag.outputs['Normal'],nodes['Principled BSDF'].inputs['Normal'])
leather=mat('Worn hide',(.115,.072,.046),.36,8)
bone=mat('Tusk ivory',(.61,.50,.33),.12,8)
black=mat('Deep creases',(.008,.006,.008),.1)
ember=mat('Magma seams',(.85,.205,.035),.1)
eye=mat('Amber eyes',(.9,.49,.14),0)
pieces=[];extras=[]
def mass(p,s,name='Muscle'):pieces.append(ell(name,p,s,stone,12,8));return pieces[-1]
def block(name,p,s,bevel=.07):
    o=cube(name,p,s,stone,0);mod=o.modifiers.new('Chiseled edge','BEVEL');mod.width=bevel;mod.segments=1;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name);return o
# Anatomical blockout measured against the front/side/back reference proportions.
mass((0,.08,4.50),(1.40,.79,1.45),'Ribcage')
mass((0,.10,3.61),(1.10,.64,.80),'Waist')
mass((0,.11,3.01),(1.15,.67,.70),'Pelvis')
mass((0,.25,5.56),(1.18,.66,.63),'Upper back')
mass((0,.08,5.92),(.64,.55,.60),'Neck')
for s in [-1,1]:
    # Three irregular eight-sided rings form the fan of the pectoral, with a
    # broad front plane and a sloped lower edge instead of a rectangular slab.
    outline=[(.12,5.54),(.78,5.65),(1.32,5.44),(1.43,5.13),(1.24,4.85),(.61,4.83),(.10,4.96),(.04,5.30)]
    pv=[]
    for y,scale in [(-.32,1.0),(-.83,1.0),(-.96,.74)]:
        for x,z in outline:pv.append((s*(.72+(x-.72)*scale),y,5.23+(z-5.23)*scale))
    pf=[tuple(range(7,-1,-1)),tuple(range(16,24))]+[(j*8+k,j*8+(k+1)%8,(j+1)*8+(k+1)%8,(j+1)*8+k) for j in range(2) for k in range(8)]
    pieces.append(mesh('Chiseled pectoral fan',pv,pf,stone))
    mass((s*.82,.34,4.79),(.74,.57,1.03),'Latissimus')
    mass((s*.80,.10,5.62),(.91,.55,.46),'Trapezius')
    mass((s*1.56,.04,5.30),(.79,.75,.87),'Deltoid')
    mass((s*1.92,.08,4.68),(.62,.63,.76),'Upper arm')
    mass((s*1.95,-.27,4.73),(.49,.51,.64),'Biceps')
    mass((s*2.04,.32,4.58),(.43,.41,.60),'Triceps')
    mass((s*2.15,.005,4.06),(.47,.50,.43),'Elbow')
    mass((s*2.27,-.05,3.65),(.60,.59,.73),'Forearm')
    mass((s*2.38,-.10,3.16),(.46,.45,.49),'Wrist')
    handbone=('Left' if s<0 else 'Right')+'Hand'
    extras.append(rigid(block('Stone fist palm',(s*2.40,-.16,2.70),(.94,.84,.93),.17),handbone))
    for k in range(4):
        rise=[-.045,.035,.015,-.075][k];reach=[.025,.065,.035,-.025][k]
        extras.append(rigid(block('Squared knuckle',(s*2.40+(k-1.5)*.23,-.59-reach,2.70+rise),(.23,.33,.39),.065),handbone))
        extras.append(rigid(block('Folded finger tip',(s*2.40+(k-1.5)*.23,-.53,2.42+rise),(.215,.29,.23),.05),handbone))
    extras.append(rigid(tube('Opposing stone thumb',[(s*1.97,-.10,2.98),(s*1.81,-.38,2.80),(s*1.91,-.68,2.62),(s*2.13,-.73,2.61)],[.22,.23,.20,.16],stone,6),handbone))
    mass((s*.65,.08,2.76),(.68,.68,.92),'Thigh')
    mass((s*.65,-.29,2.60),(.54,.50,.71),'Quadriceps')
    mass((s*.74,-.07,1.84),(.53,.56,.50),'Knee')
    mass((s*.76,.13,1.23),(.54,.59,.73),'Calf')
    mass((s*.76,0,.65),(.43,.45,.43),'Ankle')
    pieces.append(block('Broad heel and instep',(s*.76,-.035,.34),(1.09,1.08,.63),.075))
    for k in range(3):
        reach=[.02,.09,-.035][k];toe=block('Square stone toe',(s*.76+(k-1)*.355,-.71-reach,.235),(.343,.60,.43),.075)
        extras.append(rigid(toe,('Left' if s<0 else 'Right')+'Foot'))
body=fuse(pieces,'Continuous muscular body',stone,.042,6700,1)
# Broad shallow abdominal separation, preserving a continuous body.
cut(body,tube('Sternum groove',[(0,-1.057,5.53),(0,-1.06,5.14),(0,-.93,4.74)],[.037,.030,.016],None,8))
# Skull, brow, cheek and protruding lower jaw are blended into one sculpt.
headparts=[block('Cranium',(0,-.16,6.33),(1.56,1.29,1.44),.25)]
jaw=block('Protruding underbite',(0,-.69,5.96),(1.58,1.10,.69),.15)
for vertex in jaw.data.vertices:
    if vertex.co.z<0:vertex.co.x*=.84
headparts.append(jaw)
for s in [-1,1]:
    b=cube('Heavy brow',(s*.36,-.835,6.49),(.75,.34,.28),stone,.075);b.rotation_euler.y=-s*.14;headparts.append(b)
    headparts.append(ell('Cheek plane',(s*.61,-.65,6.14),(.26,.28,.32),stone))
    headparts.append(cube('Ear',(s*.83,-.01,6.42),(.30,.35,.45),stone,.11))
headparts.append(cube('Broad nose',(0,-.84,6.23),(.46,.38,.30),stone,.08))
head=fuse(headparts,'Carved ogre head',stone,.029,2500,1)
for s in [-1,1]:
    cut(head,ell('Eye recess',(s*.35,-.905,6.34),(.23,.26,.115),None))
    extras.append(rigid(ell('Socket shadow',(s*.35,-.713,6.36),(.20,.035,.125),black),'Head'))
    extras.append(rigid(ell('Deep amber eye',(s*.35,-.804,6.345),(.078,.085,.058),eye),'Head'))
    extras.append(rigid(tube('Lower tusk',[(s*.56,-1.17,6.12),(s*.59,-1.21,6.29),(s*.56,-1.20,6.47)],[.105,.076,.006],bone,8),'Head'))
cut(head,cube('Underbite lip crease',(0,-1.21,6.165),(1.02,.26,.085),None,.016))
extras.append(rigid(cube('Mouth interior',(0,-1.16,6.165),(.96,.055,.056),black,.010),'Head'))
rigid(head,'Head')
# Hide wraps the waist and hangs in broad overlapping ragged pieces.
for j in range(13):
    a=j*math.tau/13;da=math.pi/13*1.18
    zlow=2.51+random.uniform(-.19,.15)
    angles=[a-da,a-da*.50,a,a+da*.45,a+da]
    verts=[]
    for row in range(5):
        t=row/4
        for k,aa in enumerate(angles):
            z=3.36*(1-t)+(zlow+(.15 if k%2 else -.06))*t
            direction=Vector((math.cos(aa),math.sin(aa),0))
            # Begin inside the arms' radius, so clothing can only hit pelvis/thighs.
            ok,p,n,idx=body.ray_cast(direction*1.55+Vector((0,0,z)),-direction)
            if ok:verts.append(tuple(p+direction*(.06+.035*t)))
            else:verts.append(((1.12+.28*t)*math.cos(aa),(.71+.20*t)*math.sin(aa),z))
    faces=[(row*5+k,row*5+k+1,(row+1)*5+k+1,(row+1)*5+k) for row in range(4) for k in range(4)]
    o=mesh('Ragged hide panel',verts,faces,leather);bpy.context.view_layer.objects.active=o
    mod=o.modifiers.new('Leather thickness','SOLIDIFY');mod.thickness=.06;bpy.ops.object.modifier_apply(modifier=mod.name)
    extras.append(rigid(o,'Pelvis'))
for z in [3.45,3.63]:
    pts=[(1.16*math.cos(k*math.tau/48),.76*math.sin(k*math.tau/48),z+.024*math.sin(k*.8)) for k in range(49)]
    extras.append(rigid(tube('Wrapped hide belt',pts,[(.115,.085)]*49,leather,8),'Pelvis'))
extras.append(rigid(cube('Stone buckle',(0,-.86,3.51),(.47,.17,.40),mat('Buckle',(.19,.14,.11),.3),.05),'Pelvis'))
# Crack lines are set into the shoulder surface using raycasts rather than floating strips.
for s in [-1,1]:
    for linepts in [
        [(1.32,5.92),(1.46,5.69),(1.39,5.52),(1.56,5.37),(1.61,5.10)],
        [(1.46,5.69),(1.72,5.70),(1.93,5.54)],
        [(1.56,5.37),(1.83,5.37),(2.04,5.17)],
    ]:
        pts=[]
        for x,z in linepts:
            ok,p,n,idx=body.ray_cast(Vector((s*x,-3,z)),Vector((0,1,0)))
            if ok:pts.append(p+n*.007)
        if len(pts)>1:
            cut(body,tube('Recessed crack',pts,.042,None,8))
            extras.append(tube('Shoulder fissure',pts,.022,ember,6))
objects=[body,head]+extras
body['smooth_skin']=True
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Sculpt.blend'))
(out/'anatomy.json').write_text(json.dumps({'body':'continuous voxel-blended muscular sculpt','reference':'../../obsidian-ogre/Reference.png','status':'shape review before rigging','bones':{
 'Pelvis':[[0,0,2.94],[0,0,3.72],None],
 'Chest':[[0,0,3.72],[0,0,5.55],'Pelvis'],
 'Head':[[0,0,5.55],[0,0,6.86],'Chest'],
 **{side+part:[a,b,parent] for side,s in [('Left',-1),('Right',1)] for part,a,b,parent in [
 ('UpperArm',[s*1.47,0,5.43],[s*2.13,0,4.10],'Chest'),
 ('Forearm',[s*2.13,0,4.10],[s*2.38,-.10,3.12],side+'UpperArm'),
 ('Hand',[s*2.38,-.10,3.12],[s*2.40,-.20,2.35],side+'Forearm'),
 ('Thigh',[s*.62,0,3.03],[s*.73,0,1.82],'Pelvis'),
 ('Shin',[s*.73,0,1.82],[s*.76,0,.58],side+'Thigh'),
 ('Foot',[s*.76,0,.58],[s*.76,-.80,.27],side+'Shin')]}
}},indent=2))
render(out,objects)
