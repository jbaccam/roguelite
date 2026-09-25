"""Continuous Ogre volume construction, executed by build_ogre.py."""
def block(name,p,s,bevel=.07):
    o=cube(name,p,s,stone,0);mod=o.modifiers.new('Chiseled edge','BEVEL');mod.width=bevel;mod.segments=1;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name);return o

def loft(name,levels,side=1,exponent=.87,torso=False):
    # Profiles: height, center x/y, half-width, front depth, back depth.
    # Four Catmull-Rom samples per interval blend muscle volumes into one skin.
    rings=[]
    for j in range(len(levels)-1):
        p0=levels[max(0,j-1)];p1=levels[j];p2=levels[j+1];p3=levels[min(len(levels)-1,j+2)]
        for k in range(4):
            t=k/4
            rings.append([.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t) for a,b,c,d in zip(p0,p1,p2,p3)])
    rings.append(levels[-1]);verts=[];n=64
    for z,cx,cy,rx,front,back in rings:
        for k in range(n):
            a=k*math.tau/n;co=math.cos(a);si=math.sin(a)
            x=side*(cx+rx*math.copysign(abs(co)**exponent,co))
            y=cy+(back if si>=0 else front)*math.copysign(abs(si)**exponent,si)
            if torso:
                frontal=max(0,-si)**4;rear=max(0,si)**4;ax=abs(x)
                pec=.30*math.exp(-((ax-.73)/.65)**4-((z-5.12)/.47)**4)
                sternum=.050*math.exp(-(x/.12)**2-((z-5.13)/.57)**4)
                y-=frontal*(pec-sternum)
                y+=rear*(.19*math.exp(-((ax-.62)/.73)**2-((z-5.63)/.52)**2)+.12*math.exp(-((ax-.94)/.58)**2-((z-4.84)/.66)**2))
                y-=rear*.065*math.exp(-(x/.16)**2-((z-5.20)/.90)**4)
            verts.append((x,y,z))
    faces=[tuple(range(n-1,-1,-1))]+[(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(len(rings)-1) for k in range(n)]+[tuple(range((len(rings)-1)*n,len(rings)*n))]
    return mesh(name,verts,faces,stone)

pieces.append(loft('Deep torso and trapezius',[
 (2.83,0,.11,1.03,.66,.75),(3.25,0,.12,1.12,.72,.82),
 (3.70,0,.13,1.18,.79,.93),(4.12,0,.13,1.38,.90,1.03),
 (4.58,0,.13,1.56,.99,1.14),(5.05,0,.13,1.65,1.00,1.19),
 (5.43,0,.15,1.61,.90,1.18),(5.72,0,.18,1.42,.72,1.03),
 (5.98,0,.20,1.04,.55,.80),(6.22,0,.18,.55,.47,.57)
],torso=True))
for s in [-1,1]:
    pieces.append(loft('Shoulder arm and forearm',[
      (3.09,2.37,-.08,.44,.51,.46),(3.45,2.30,-.03,.57,.68,.60),
      (3.82,2.22,.02,.60,.68,.61),(4.17,2.12,.06,.48,.49,.52),
      (4.60,2.02,.10,.53,.61,.67),(4.96,1.94,.12,.59,.75,.79),
      (5.32,1.76,.15,.70,.86,.94),(5.65,1.62,.16,.67,.82,.91),
      (5.89,1.51,.17,.44,.56,.67),(6.00,1.46,.18,.12,.23,.29)
    ],side=s))
    handbone=('Left' if s<0 else 'Right')+'Hand'
    mitten=block('Single chamfered mitten',(s*2.42,-.17,2.66),(1.17,1.25,1.23),.21)
    for vertex in mitten.data.vertices:
        if vertex.co.z<0:
            vertex.co.x*=.91;vertex.co.y*=.88;vertex.co.z+=s*vertex.co.x*.15
    mitten.rotation_euler.y=s*.09
    thumb=block('Single tucked thumb',(s*1.83,-.44,2.92),(.48,.58,.65),.12);thumb.rotation_euler.y=s*.28
    fist=fuse([mitten,thumb],'Solid mitten fist',stone,.023,2200,2);extras.append(rigid(fist,handbone))
    pieces.append(loft('Thigh knee and shin',[
      (.37,.82,.08,.40,.39,.42),(.65,.82,.08,.43,.45,.45),
      (1.12,.81,.08,.50,.52,.60),(1.48,.80,.07,.52,.53,.66),
      (1.85,.78,.03,.50,.55,.54),(2.18,.77,.03,.58,.67,.62),
      (2.64,.74,.05,.67,.77,.70),(3.09,.69,.08,.66,.76,.71)
    ],side=s))
    pieces.append(block('Broad continuous foot',(s*.82,-.31,.32),(1.23,1.65,.64),.13))
body=fuse(pieces,'Continuous muscular body',stone,.032,18200,7)
for s in [-1,1]:
    for off in [-.20,.20]:cut(body,cube('Shallow toe division',(s*.82+off,-1.07,.22),(.035,.25,.65),None,.008))
