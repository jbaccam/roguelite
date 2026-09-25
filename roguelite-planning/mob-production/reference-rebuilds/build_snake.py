import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
out=reset('snake')
olive=mat('Olive scales',(.235,.257,.090),.30,10)
greens=[mat('Scale tone '+str(i),c,.12,9) for i,c in enumerate([(.22,.25,.085),(.29,.31,.11),(.19,.23,.075),(.12,.16,.055),(.31,.32,.13)])]
belly=mat('Belly scutes',(.55,.48,.29),.13,12)
crease=mat('Scale seams',(.12,.14,.045),.14,10)
ivory=mat('Fang ivory',(.74,.66,.45),.06)
dark=mat('Glossy black eyes',(.010,.006,.002),0,rough=.24)
iris=mat('Amber iris',(.19,.11,.025),.12,rough=.32)
controls=[(0,-1.46,2.74),(0,-1.09,2.44),(.025,-.76,1.90),(-.06,-.70,1.12),(-.42,-.52,.51),(-.74,.10,.425),(-.68,.85,.40),(.06,1.46,.38),(.83,1.22,.31),(1.09,2.06,.25),(.57,2.86,.17),(-.20,3.12,.085),(-.67,3.40,.025)]
controls=[Vector(p) for p in controls]
def cat(t):
    q=t*(len(controls)-1);i=min(len(controls)-2,int(q));u=q-i
    p0=controls[max(i-1,0)];p1=controls[i];p2=controls[i+1];p3=controls[min(i+2,len(controls)-1)]
    return .5*((2*p1)+(-p0+p2)*u+(2*p0-5*p1+4*p2-p3)*u*u+(-p0+3*p1-3*p2+p3)*u*u*u)
count=145;path=[cat(i/(count-1)) for i in range(count)]
frames=[];prev=None
for i,p in enumerate(path):
    t=(path[min(count-1,i+1)]-path[max(0,i-1)]).normalized()
    u=Vector((1,0,0)) if prev is None else prev;u=(u-t*u.dot(t)).normalized();v=t.cross(u).normalized();prev=u;frames.append((u,v))
def radius(t):
    return .35+.07*math.sin(t*math.pi/.85) if t<.43 else .39*((1-t)/.57)**.80+.006
def point(t,a,offset=0):
    q=t*(count-1);i=min(count-2,int(q));f=q-i
    u=frames[i][0].lerp(frames[i+1][0],f).normalized();v=frames[i][1].lerp(frames[i+1][1],f).normalized();p=path[i].lerp(path[i+1],f)
    r=radius(t)+offset
    return p+u*math.cos(a)*r+v*math.sin(a)*r*(.84 if math.sin(a)>0 else 1.0)
# A continuous body with an unflipped transported frame, sufficient neck subdivision.
n=32;verts=[point(i/(count-1),k*math.tau/n) for i in range(count) for k in range(n)]
faces=[tuple(range(n-1,-1,-1))]
for j in range(count-1):
    for k in range(n):faces.append((j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k))
faces.append(tuple(range((count-1)*n,count*n)))
body=mesh('Continuous snake skin',verts,faces,crease);body['spine_skin']=True
for p in body.data.polygons:p.use_smooth=True
# Each scale is a shallow, closed, overlapping shield: visible in geometry and color.
scaleverts=[];scalefaces=[];scaleindices=[]
rows=82;around=24
for j in range(rows):
    t=.015+j*(.962/rows);half=.962/rows*.59
    for k in range(around):
        a=(k+(j%2)*.5)*math.tau/around;aa=(a-math.pi/2+math.pi)%math.tau-math.pi
        isbelly=abs(aa)<.66
        if isbelly:continue
        da=math.pi/around*.99
        outer=[point(max(.002,t-half),a,.009),point(t,a+da,.010),point(min(.994,t+half),a,.012),point(t,a-da,.010)]
        center=point(t,a,.014 if t<.80 else .010)
        inner=[point(max(.002,t-half),a,-.005),point(t,a+da,-.005),point(min(.994,t+half),a,-.005),point(t,a-da,-.005)]
        idx=len(scaleverts);scaleverts+=outer+[center]+inner
        ff=[(0,1,4),(1,2,4),(2,3,4),(3,0,4),(8,7,6,5),(0,5,6,1),(1,6,7,2),(2,7,8,3),(3,8,5,0)]
        scalefaces += [tuple(idx+x for x in f) for f in ff]
        tone=3 if math.sin(t*38+a*1.1)>.35 and math.sin(a)<.4 else random.choices([0,1,2,4],[5,3,3,1])[0]
        scaleindices += [tone]*len(ff)
scales=mesh('Overlapping dorsal scales',scaleverts,scalefaces,greens[0]);scales['spine_skin']=True
for m in greens[1:]:scales.data.materials.append(m)
for p,i in zip(scales.data.polygons,scaleindices):p.material_index=i
# Broad ventral scutes, individually curved around the belly; no detached beads.
v=[];f=[]
for j in range(74):
    t=.006+j*.986/74;dt=.986/74*.45;angles=[math.pi/2-.70+k*1.4/6 for k in range(7)];offset=len(v)
    for tt in [t-dt,t+dt]:
        for a in angles:v.append(point(max(.001,min(.998,tt)),a,.035))
    for tt in [t-dt,t+dt]:
        for a in angles:v.append(point(max(.001,min(.998,tt)),a,-.012))
    for k in range(6):f.extend([tuple(offset+x for x in p) for p in [(k,k+1,k+8,k+7),(k+21,k+22,k+15,k+14),(k+14,k+15,k+1,k),(k+7,k+8,k+22,k+21)]])
    f.extend([tuple(offset+x for x in p) for p in [(0,7,21,14),(6,20,27,13)]])
scutes=mesh('Ventral scutes',v,f,belly);scutes['spine_skin']=True
# Broad viper head and muzzle, blended rather than a rounded cube.
pieces=[ell('Cranium',(0,-1.49,2.84),(.57,.49,.30),olive),ell('Snout',(0,-1.91,2.78),(.43,.38,.19),olive)]
for s in [-1,1]:pieces.append(ell('Brow',(s*.37,-1.62,3.015),(.25,.26,.145),olive))
head=fuse(pieces,'Snake head',olive,.025,3600,3);rigid(head,'Head')
extras=[]
for s in [-1,1]:
    cut(head,ell('Eye socket',(s*.465,-1.71,2.91),(.185,.22,.18),None))
    extras.append(rigid(ell('Eye',(s*.458,-1.69,2.91),(.15,.175,.157),dark),'Head'))
    extras.append(rigid(ell('Narrow iris',(s*.514,-1.799,2.912),(.057,.035,.115),iris),'Head'))
    cut(head,ell('Nostril',(s*.19,-2.216,2.81),(.047,.077,.038),None,16,10))
    extras.append(rigid(tube('Mouth crease',[(s*.48,-1.69,2.69),(s*.42,-1.94,2.67),(s*.26,-2.15,2.67),(0,-2.24,2.67)],.018,crease,8),'Head'))
    extras.append(rigid(tube('Curved fang',[(s*.26,-2.15,2.63),(s*.27,-2.17,2.49),(s*.25,-2.13,2.40)],[.055,.037,.002],ivory,10),'Head'))
jaw=ell('Lower jaw',(0,-1.85,2.60),(.43,.42,.115),belly);rigid(jaw,'Head');extras.append(jaw)
objects=[body,scales,scutes,head]+extras
(out/'anatomy.json').write_text(json.dumps({'status':'shape review before rigging','spinePath':[list(p) for p in path],'spineBones':16,'headPosition':[0,-1.48,2.75],'reference':'../../snake/Reference.png'},indent=2))
render(out,objects,aim_at=(.10,.55,1.45),size=4.15)
