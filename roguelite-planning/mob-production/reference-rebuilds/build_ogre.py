import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
out=reset('obsidian-ogre')
stone=mat('Obsidian stone',(.095,.083,.100),.28,7)
nodes=stone.node_tree.nodes;links=stone.node_tree.links
next(n for n in nodes if n.type=='VALTORGB').color_ramp.interpolation='EASE'
grain=nodes.new('ShaderNodeTexNoise');grain.inputs['Scale'].default_value=38;grain.inputs['Detail'].default_value=2.5;grain.inputs['Roughness'].default_value=.8
crag=nodes.new('ShaderNodeBump');crag.inputs['Strength'].default_value=.30;crag.inputs['Distance'].default_value=.018
links.new(grain.outputs['Fac'],crag.inputs['Height']);links.new(crag.outputs['Normal'],nodes['Principled BSDF'].inputs['Normal'])
leather=mat('Worn hide',(.115,.072,.046),.36,8)
bone=mat('Tusk ivory',(.61,.50,.33),.12,8)
black=mat('Deep creases',(.008,.006,.008),.1)
ember=mat('Magma seams',(.85,.205,.035),.1)
eye=mat('Amber eyes',(.9,.49,.14),0)
pieces=[];extras=[]
exec((ROOT/'ogre_anatomy.py').read_text())
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
    zlow=2.32+random.uniform(-.14,.14)
    angles=[a-da,a-da*.50,a,a+da*.45,a+da]
    verts=[]
    for row in range(5):
        t=row/4
        for k,aa in enumerate(angles):
            z=3.36*(1-t)+(zlow+(.15 if k%2 else -.06))*t
            # A hanging envelope clears both thighs and the expanded pelvis.
            # Individual ray hits on separate legs pinched the old skirt inward.
            co=math.cos(aa);si=math.sin(aa)
            verts.append(((1.25+.32*t)*math.copysign(abs(co)**.65,co),.10+(.99+.16*t)*math.copysign(abs(si)**.65,si),z))
    faces=[(row*5+k,row*5+k+1,(row+1)*5+k+1,(row+1)*5+k) for row in range(4) for k in range(4)]
    o=mesh('Ragged hide panel',verts,faces,leather);bpy.context.view_layer.objects.active=o
    mod=o.modifiers.new('Leather thickness','SOLIDIFY');mod.thickness=.06;bpy.ops.object.modifier_apply(modifier=mod.name)
    extras.append(rigid(o,'Pelvis'))
for z in [3.45,3.63]:
    pts=[]
    for k in range(49):
        a=k*math.tau/48;co=math.cos(a);si=math.sin(a)
        pts.append((1.28*math.copysign(abs(co)**.80,co),.10+1.0*math.copysign(abs(si)**.80,si),z+.024*math.sin(k*.8)))
    extras.append(rigid(tube('Wrapped hide belt',pts,[(.115,.085)]*49,leather,8),'Pelvis'))
extras.append(rigid(cube('Stone buckle',(0,-.99,3.51),(.47,.17,.40),mat('Buckle',(.19,.14,.11),.3),.05),'Pelvis'))
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
