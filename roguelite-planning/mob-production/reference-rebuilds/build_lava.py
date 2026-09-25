import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
out=reset('lava-slime')
lava=mat('Molten lava',(.95,.22,.012),.7,7)
ramp=next(n for n in lava.node_tree.nodes if n.type=='VALTORGB')
for e,c in zip(ramp.color_ramp.elements,[(.70,.045,.002,1),(.98,.16,.004,1),(1,.33,.012,1),(1,.58,.025,1)]):e.color=c
bs=lava.node_tree.nodes.get('Principled BSDF');lava.node_tree.links.new(ramp.outputs[0],bs.inputs['Emission Color']);bs.inputs['Emission Strength'].default_value=.16
rock=mat('Irregular cooled basalt',(.073,.051,.043),.35,13)
dark=mat('Burned eye recess',(.018,.008,.002),.05)
glow=mat('Hot amber core',(.98,.41,.018),.18,5)
glow.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value=(1,.23,.008,1);glow.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value=.45
n=48;levels=[(.045,1.38,1.09,0),(.18,1.64,1.22,0),(.56,1.50,1.17,.015),(1.03,1.31,1.05,.065),(1.53,1.13,.88,.12),(1.98,.88,.71,.15),(2.40,.55,.48,.13),(2.63,.13,.18,.09)]
verts=[]
for j,(z,rx,ry,cx) in enumerate(levels):
    for k in range(n):
        a=k*math.tau/n;wr=1+.045*math.sin(a*3+j*.27)+.028*math.sin(a*5-j*.31)
        verts.append((cx+rx*math.cos(a)*wr,ry*math.sin(a)*wr,z+.045*math.sin(a*3+j*.4)*(j>0)))
faces=[tuple(range(n-1,-1,-1))]
for j in range(len(levels)-1):
    for k in range(n):faces.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
faces.append(tuple(range((len(levels)-1)*n,len(levels)*n)))
core=mesh('Asymmetric molten body',verts,faces,lava)
body=fuse([core,ell('Molten basal lobe',(-1.01,-.38,.25),(.51,.55,.26),lava),ell('Molten basal lobe',(.99,.39,.25),(.52,.60,.27),lava)],'Molten continuous surface',lava,.035,6800,3)
body['slime_skin']=True;objects=[body]
# Organic basalt chunks conform to the molten surface with varied outlines and depth.
placements=[(.04,1.03,.47),(.46,1.61,.46),(.90,2.06,.44),(1.50,2.43,.49),(2.20,1.97,.48),(2.82,1.25,.44),(3.30,.62,.32),(3.70,1.67,.29),(4.02,2.16,.40),(4.57,2.40,.26),(5.48,1.96,.36),(5.89,.58,.35),(.91,.56,.32),(1.89,1.02,.51),(2.91,2.14,.31),(3.89,.40,.17),(5.5,.32,.19)]
for idx,(a,z,r) in enumerate(placements):
    direction=Vector((math.cos(a),math.sin(a),0));ok,p,normal,_=body.ray_cast(direction*4+Vector((0,0,z)),-direction)
    if not ok:continue
    u=normal.cross(Vector((0,0,1))).normalized();v=normal.cross(u).normalized();count=9;outline=[]
    for k in range(count):
        angle=k*math.tau/count;rr=r*random.uniform(.82,1.15);off=u*math.cos(angle)*rr+v*math.sin(angle)*rr*random.uniform(.74,1.02)
        hit,surface,nn,_=body.ray_cast(p+off+normal*2,-normal)
        outline.append((surface if hit else p+off)+normal*.035)
    top=[p+(q-p)*.65+normal*(r*.23+.045) for q in outline]
    center=p+normal*(r*.30+.045);back=[q-normal*.10 for q in outline];vv=outline+top+[center]+back;ff=[]
    for k in range(count):
        kk=(k+1)%count
        ff += [(k,kk,count+kk,count+k),(count+k,count+kk,count*2),(k,count*2+1+k,count*2+1+kk,kk)]
    ff.append(tuple(range(count*2+1,count*3+1)))
    stone=mesh('Basalt chunk '+str(idx),vv,ff,rock);stone['slime_skin']=True;objects.append(stone)
def onfront(x,z,offset=.018):
    hit,p,norm,_=body.ray_cast(Vector((x,-4,z)),Vector((0,1,0)))
    return p+norm*offset if hit else Vector((x,-.9,z))
for s in [-1,1]:
    # Rounded angry eye shape from the reference, with its outline sitting on the body.
    xz=[(s*.17,1.56),(s*.69,1.76),(s*.76,1.58),(s*.77,1.32),(s*.69,1.13),(s*.53,1.06),(s*.36,1.10),(s*.23,1.24)]
    # Project interior vertices as well as the outline. A flat polygon's center
    # otherwise disappears inside the convex molten body.
    cx=sum(p[0] for p in xz)/len(xz);cz=sum(p[1] for p in xz)/len(xz)
    vv=[onfront(cx,cz,.033)];ff=[];L=len(xz)
    for row in range(1,9):
        t=row/8
        vv += [onfront(cx+(x-cx)*t,cz+(z-cz)*t,.033) for x,z in xz]
    ff += [(0,1+k,1+(k+1)%L) for k in range(L)]
    for row in range(7):
        a=1+row*L;b=a+L
        ff += [(a+k,a+(k+1)%L,b+(k+1)%L,b+k) for k in range(L)]
    eye=mesh('Charred eye socket',vv,ff,dark);bpy.context.view_layer.objects.active=eye
    mod=eye.modifiers.new('Inset lining thickness','SOLIDIFY');mod.thickness=.015;bpy.ops.object.modifier_apply(modifier=mod.name)
    eye['slime_skin']=True;objects.append(eye)
    p=onfront(s*.47,1.37,.070);o=ell('Glowing pupil',p,(.074,.025,.135),glow,16,10);o['slime_skin']=True;objects.append(o)
mouth=tube('Frowning mouth',[onfront(-.25,.83,.025),onfront(-.13,.91,.025),onfront(0,.94,.025),onfront(.14,.91,.025),onfront(.26,.84,.025)],.035,dark,8);mouth['slime_skin']=True;objects.append(mouth)
(out/'anatomy.json').write_text(json.dumps({'status':'shape review before rigging','slime':True,'bones':{'Body':[[0,0,.15],[0,0,1.1],None],'Crown':[[0,0,1.1],[0,0,2.5],'Body']}},indent=2))
render(out,objects,aim_at=(0,0,1.28),size=3.5)
