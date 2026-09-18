"""Reference-authored stylized exterior props. No functional internals."""
import bpy,bmesh,math,json,random,sys,shutil
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
INVENTORY=json.loads((ROOT/'inventory.json').read_text())
random.seed(97)
def move(o,c):
    for old in list(o.users_collection):old.objects.unlink(o)
    c.objects.link(o)
def srgb(v):return ((v+.055)/1.055)**2.4 if v>.04045 else v/12.92
def mat(name,rgb,facets=True):
    m=bpy.data.materials.new(name);m.use_nodes=True
    base=tuple(srgb(v) for v in rgb);m.diffuse_color=(*base,1)
    nt=m.node_tree;bs=nt.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*base,1);bs.inputs['Roughness'].default_value=.78
    if facets:
        tex=nt.nodes.new('ShaderNodeTexCoord');vor=nt.nodes.new('ShaderNodeTexVoronoi');vor.inputs['Scale'].default_value=2.6
        nt.links.new(tex.outputs['Object'],vor.inputs['Vector']);bw=nt.nodes.new('ShaderNodeRGBToBW');nt.links.new(vor.outputs['Color'],bw.inputs[0]);r=nt.nodes.new('ShaderNodeValToRGB')
        r.color_ramp.elements[0].color=(*(v*.90 for v in base),1);r.color_ramp.elements[1].color=(*(min(1,v*1.09) for v in base),1)
        nt.links.new(bw.outputs[0],r.inputs[0]);nt.links.new(r.outputs[0],bs.inputs['Base Color'])
    return m
def finish(o,m,b=0):
    move(o,asset);o.data.materials.append(m)
    if b:
        q=o.modifiers.new('Broad one-step chamfer','BEVEL');q.width=b;q.segments=1
        bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=q.name)
    for p in o.data.polygons:p.use_smooth=False
    return o
def mesh(name,v,f,m,b=0):
    me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new(name,me);asset.objects.link(o)
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
    return finish(o,m,b)
def box(n,loc,dim,m,b=.035):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=n;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return finish(o,m,b)
def prism(n,p,w,m,b=.035,y=0):
    N=len(p);v=[(x,y+s*w/2,z) for s in [-1,1] for x,z in p];f=[tuple(range(N-1,-1,-1)),tuple(range(N,2*N))]+[(i,(i+1)%N,(i+1)%N+N,i+N) for i in range(N)]
    return mesh(n,v,f,m,b)
def ring(n,outer,inner,w,m,b=.02,y=0):
    N=len(outer);v=[(x,y+s*w/2,z) for s in [-1,1] for p in [outer,inner] for x,z in p];f=[]
    for i in range(N):
        j=(i+1)%N;f += [(i,j,N+j,N+i),(2*N+i,3*N+i,3*N+j,2*N+j),(i,2*N+i,2*N+j,j),(N+i,N+j,3*N+j,3*N+i)]
    return mesh(n,v,f,m,b)
def lathe(n,rings,m,N=10,y=0,z=0,caps=True):
    v=[(x,y+math.cos(2*math.pi*(i+.5)/N)*r,z+math.sin(2*math.pi*(i+.5)/N)*r) for x,r in rings for i in range(N)]
    f=[(k*N+i,k*N+(i+1)%N,(k+1)*N+(i+1)%N,(k+1)*N+i) for k in range(len(rings)-1) for i in range(N)]
    if caps:f += [tuple(range(N-1,-1,-1)),tuple(range((len(rings)-1)*N,len(rings)*N))]
    return mesh(n,v,f,m)
def barrel(n,xfront,xrear,r,m,z,y=0,N=10):
    d=1 if xrear>xfront else -1
    o=lathe(n,[(xrear,r*.95),(xfront+d*.07,r),(xfront,r*.93),(xfront,r*.72),(xfront+d*.30,r*.68)],m,N,y,z)
    o.data.materials.append(DARK)
    for p in o.data.polygons:
        if p.index>=3*N and p.index<4*N or p.index==4*N+1:p.material_index=1
    return o
def cyl(n,loc,r,depth,m,axis='X',N=10,b=.015):
    bpy.ops.mesh.primitive_cylinder_add(vertices=N,radius=r,depth=depth,location=loc);o=bpy.context.object;o.name=n
    if axis=='X':o.rotation_euler.y=math.pi/2
    if axis=='Y':o.rotation_euler.x=math.pi/2
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True);return finish(o,m,b)
def path(n,points,r,m,N=8):
    vv=[]
    for i,p in enumerate(points):
        tan=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)]);tan.normalize();a=tan.cross(Vector((0,1,0)))
        if a.length<.001:a=tan.cross(Vector((0,0,1)))
        a.normalize();bb=tan.cross(a).normalized()
        vv.extend([Vector(p)+r*(a*math.cos(2*math.pi*j/N)+bb*math.sin(2*math.pi*j/N)) for j in range(N)])
    ff=[(k*N+i,k*N+(i+1)%N,(k+1)*N+(i+1)%N,(k+1)*N+i) for k in range(len(points)-1) for i in range(N)]
    ff += [tuple(range(N-1,-1,-1)),tuple(range((len(points)-1)*N,len(points)*N))];return mesh(n,vv,ff,m)
def smoothpath(n,points,r,m,N=8):
    pp=[Vector(p) for p in points];out=[]
    for i in range(len(pp)-1):
        p0=pp[max(0,i-1)];p1=pp[i];p2=pp[i+1];p3=pp[min(i+2,len(pp)-1)]
        for j in range(3):
            t=j/3;out.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t))
    out.append(pp[-1]);return path(n,out,r,m,N)
def bolt(n,x,z,y,m=None,r=.095):return cyl(n,(x,y,z),r,.06,m or EDGE,'Y',8,.01)
def grip(n,x,z,w=0.65,h=1.5,m=None,rake=.35):
    return prism(n,[(x-w/2,z),(x+w/2,z),(x+w/2+rake,z-h+.08),(x+w/2+rake-.12,z-h),(x-w/2+rake,z-h),(x-w/2-.08,z-.20)],.62,m or CHAR,.065)
def guard(n,x,z,w=.95,h=.75):
    out=[(x,z),(x+w,z),(x+w+.08,z-h+.2),(x+w-.08,z-h),(x+.08,z-h),(x-.06,z-h+.15)]
    inn=[(x+.16,z-.08),(x+w-.16,z-.08),(x+w-.11,z-h+.25),(x+w-.19,z-h+.18),(x+.19,z-h+.18),(x+.14,z-h+.24)]
    return ring(n,out,inn,.36,CHAR,.025)
def trigger(n,x,z,m=None):return prism(n,[(x,z),(x+.20,z),(x+.18,z-.24),(x+.05,z-.46),(x-.1,z-.52),(x-.20,z-.48),(x-.08,z-.28)],.23,m or CHAR,.02)
def sight(n,x,z):return prism(n,[(x-.20,z),(x+.20,z),(x+.13,z+.25),(x-.12,z+.27)],.28,CHAR,.025)

def draco():
    # Silhouette traced from the supplied compact rifle: no rear stock, curved magazine.
    box('Lower stamped receiver',(.72,0,2.75),(2.75,.70,.62),CHAR,.07)
    prism('Long beveled upper cover',[(-.61,3.10),(2.06,3.10),(1.97,3.48),(-.54,3.64)],.72,CHAR,.065)
    box('Upper front collar',(-.74,0,3.35),(.30,.73,.62),EDGE,.045)
    prism('Upper walnut handguard',[(-2.30,3.20),(-.86,3.16),(-.85,3.67),(-2.31,3.71)],.77,WOOD,.085)
    prism('Lower walnut handguard',[(-2.34,3.10),(-.74,3.04),(-.77,2.54),(-1.03,2.37),(-1.31,2.40),(-1.46,2.50),(-2.31,2.59)],.79,WOOD,.075)
    cyl('Handguard nose band',(-2.4,0,3.05),.45,.19,CHAR)
    barrel('Enlarged octagonal muzzle collar',-3.23,-2.90,.30,EDGE,3.20,N=8)
    cyl('Exposed front barrel',(-2.68,0,3.20),.225,.44,CHAR)
    ring('Raised open front sight',[(-2.99,3.48),(-2.54,3.48),(-2.55,4.01),(-2.88,4.07)],[(-2.88,3.57),(-2.66,3.57),(-2.68,3.84),(-2.82,3.86)],.22,CHAR,.025)
    for n,x,z in [('Rear notch',1.54,3.51),('Top rear sight rail',-.52,3.67)]:
        prism(n,[(x-.20,z),(x+.20,z),(x+.13,z+.17),(x-.12,z+.18)],.28,CHAR,.02)
    grip('Walnut pistol grip',1.52,2.47,.65,1.63,WOOD,.40)
    guard('Open trigger guard',.65,2.51,.77,.72);trigger('Curved dark trigger',1.05,2.47)
    mag=[(-.28,2.48),(.52,2.46),(.48,1.98),(.34,1.47),(.10,.93),(-.24,.41),(-.61,.01),(-1.36,.55),(-.97,.98),(-.62,1.49),(-.40,2.02)]
    magazine=prism('Curved segmented magazine',mag,.65,CHAR,.045)
    for side in [-1,1]:
        for dx in [0,.27]:
            p=[(.23-dx,2.23),(.33-dx,2.22),(.21-dx,1.69),(-.02-dx,1.14),(-.33-dx,.64),(-.45-dx,.69),(-.14-dx,1.18),(.08-dx,1.72)]
            cut=prism('Magazine channel cutter',p,.14,DARK,.005,side*.325)
            bpy.context.view_layer.objects.active=magazine;q=magazine.modifiers.new('Recessed stamped channel','BOOLEAN');q.operation='DIFFERENCE';q.object=cut;bpy.ops.object.modifier_apply(modifier=q.name);bpy.data.objects.remove(cut,do_unlink=True)
            prism('Dark recessed magazine channel',p,.008,DARK,.004,side*.258)
        prism('Selector lever',[(.54,2.99),(1.44,2.94),(1.56,2.82),(1.54,2.68),(1.41,2.65),(1.30,2.78),(.55,2.84)],.075,EDGE,.025,side*.405)
        box('Upper cover side boss',(-.12,side*.39,3.21),(.75,.07,.21),EDGE,.03)
        for x in [-.44,.56,1.85]:bolt('Receiver rivet',x,2.94,side*.385,r=.072)
    prism('Thick beveled magazine floorplate',[(-1.43,.61),(-.63,-.01),(-.51,.09),(-1.30,.74)],.76,EDGE,.04)

def shotgun():
    box('Receiver',(1.04,0,1.63),(1.48,.75,1.0),CHAR,.075)
    barrel('Long upper barrel',-3.18,.40,.31,CHAR,1.82)
    cyl('Lower pump tube',(-1.4,0,1.24),.21,3.47,CHAR)
    cyl('Lower tube end cap',(-3.16,0,1.24),.205,.08,EDGE)
    rings=[(-2.45,.29),(-2.32,.38)]
    for x in [-1.98,-1.78,-1.58,-1.38,-1.18]:rings.extend([(x-.04,.38),(x-.025,.348),(x+.025,.348),(x+.04,.38)])
    rings += [(-.99,.38),(-.88,.30)]
    pump=lathe('Walnut pump foregrip with recessed flutes',rings,WOOD,10,z=1.24);pump.data.materials.append(WOODD)
    for p in pump.data.polygons:
        if p.index//10 in [3,7,11,15,19]:p.material_index=1
    p=[(1.70,2.06),(1.91,1.96),(2.34,1.51),(2.54,1.68),(3.30,1.38),(3.39,1.18),(3.39,.03),(3.13,.04),(2.44,.45),(2.30,.39),(2.07,.40),(1.94,1.09),(1.71,1.15)]
    prism('Faceted walnut shoulder stock',p,.65,WOOD,.10)
    prism('Dark broad butt pad',[(3.27,1.39),(3.43,1.33),(3.46,1.17),(3.46,.08),(3.34,.015),(3.25,.08)],.70,CHAR,.04)
    guard('Open squared guard',.90,1.20,.77,.61);trigger('Swept trigger',1.31,1.18)
    for side in [-1,1]:box('Receiver side rectangular inset',(1.09,side*.394,1.67),(.82,.07,.31),EDGE,.025)
    sight('Front blade',-2.83,2.10);sight('Rear blade',1.28,2.15)

def fartgun():
    body=lathe('Ivory body',[(-1.10,.68),(-.94,.77),(1.38,.77),(1.55,.61)],IVORY,10,z=2.17)
    lathe('Rear dark body cap',[(1.43,.64),(1.65,.63),(1.73,.50)],CHAR,10,z=2.17)
    lathe('Front charcoal band',[(-1.35,.69),(-1.24,.79),(-.98,.79),(-.91,.68)],CHAR,10,z=2.17)
    barrel('Flared lime loudspeaker muzzle',-2.54,-1.22,1.02,LIME,2.17)
    # Funnel narrows toward body, with a broad polygon lip and deep dark mouth.
    o=asset.objects.get('Flared lime loudspeaker muzzle');bpy.data.objects.remove(o,do_unlink=True)
    o=lathe('Flared lime loudspeaker muzzle',[(-1.24,.39),(-1.55,.49),(-2.38,1.0),(-2.55,1.01),(-2.60,.91),(-2.43,.83),(-1.70,.30)],LIME,10,z=2.17)
    o.data.materials.append(DARK)
    for p in o.data.polygons:
        if p.index>=5*10 and p.index<6*10 or p.index==61:p.material_index=1
    lathe('Central green speaker hub',[(-2.28,.0+0.10),(-2.38,.20),(-2.46,.17)],GREEN,8,z=2.17)
    grip('Charcoal handle',1.10,1.60,.72,1.57,CHAR,.36)
    prism('Handle heel',[(1.09,.10),(1.99,.14),(2.04,-.12),(1.10,-.12)],.78,CHAR,.045)
    guard('Open wide trigger guard',-.33,1.57,1.18,.79);trigger('Lime trigger',.25,1.56,LIME)
    lathe('Top lime tank',[(-.41,.39),(-.28,.48),(1.20,.48),(1.28,.42)],LIME,10,z=3.47)
    for x in [-.12,1.05]:
        lathe('Tank restraint',[(x-.14,.48),(x-.11,.54),(x+.15,.54),(x+.17,.48)],CHAR,10,z=3.47)
        box('Tank foot',(x,0,2.94),(.53,.61,.20),CHAR,.025)
        for s in [-1,1]:bolt('Lime tank bolt',x,3.47,s*.52,GREEN,.092)
    cyl('Ivory tank end',(1.39,0,3.47),.43,.22,IVORY)
    cyl('Tank hose coupling',(1.56,0,3.47),.24,.18,CHAR)
    path('Curved lime return hose',[(1.62,0,3.47),(1.91,0,3.38),(2.08,0,3.15),(2.15,0,2.89),(2.08,0,2.64),(1.88,0,2.45),(1.65,0,2.40)],.13,GREEN,8)
    for s in [-1,1]:
        for x in [.91,1.10,1.29]:
            cut=box('Vent cutter',(x,s*.71,2.26),(.12,.20,.48),DARK,.025)
            bpy.context.view_layer.objects.active=body;q=body.modifiers.new('Recessed green vent','BOOLEAN');q.operation='DIFFERENCE';q.object=cut;bpy.ops.object.modifier_apply(modifier=q.name);bpy.data.objects.remove(cut,do_unlink=True)
            box('Recessed green vent floor',(x,s*.626,2.26),(.105,.016,.46),GREEN,.015)
        for z in [1.91,2.49]:bolt('Front lime bolt',-1.16,z,s*.755,GREEN,.09)
        bolt('Grip lime bolt',1.18,1.42,s*.34,GREEN,.105)
        # Solid embossed puff emblem; modeled as one shaped extrusion.
        p=[(-.81,2.14),(-.35,2.29),(-.29,2.39),(-.23,2.45),(-.15,2.47),(-.07,2.44),(-.03,2.58),(.03,2.66),(.12,2.70),(.22,2.69),(.31,2.63),(.36,2.54),(.35,2.43),(.44,2.46),(.52,2.43),(.60,2.37),(.64,2.29),(.62,2.21),(.55,2.15),(.47,2.13),(.39,2.15),(.38,2.06),(.33,1.98),(.25,1.94),(.17,1.95),(.10,1.99),(.05,2.07),(-.04,2.03),(-.13,2.06),(-.20,2.12),(-.82,2.08)]
        prism('Dark green emblem border',[(.0+(x-.0)*1.06,2.32+(z-2.32)*1.06) for x,z in p],.038,GREEN,.013,s*.751)
        prism('Raised lime puff emblem',p,.040,LIME,.015,s*.779)
        prism('Second puff streak',[(-.81,2.04),(-.30,2.11),(-.14,2.10),(-.31,2.055),(-.81,2.01)],.045,LIME,.006,s*.775)

def cannon():
    # Reference points to +X. Bright blue body, white flared tube, red lower tank.
    prism('Blue faceted main receiver',[(-1.81,1.39),(-1.95,1.63),(-1.93,2.13),(-1.71,2.35),(.05,2.35),(.26,2.06),(.20,1.50),(-.04,1.14),(-.39,1.14),(-.58,1.44)],.88,BLUE,.10)
    lathe('Front receiver band',[(-.12,.57),(.10,.65),(.29,.65),(.38,.53)],CHAR,10,z=2.00)
    launch=barrel('Broad ivory launch tube',2.34,.25,.73,WHITE,2.00)
    for p in launch.data.polygons:
        if 20<=p.index<30:p.material_index=1
    o=lathe('Dark thick muzzle lip',[(2.19,.72),(2.28,.81),(2.60,.81),(2.68,.74),(2.68,.62),(2.29,.61)],CHAR,10,z=2.00)
    o.data.materials.append(DARK)
    for p in o.data.polygons:
        if p.index>=40 and p.index<50 or p.index==51:p.material_index=1
    grip('Dark angled grip',-1.06,1.43,.52,1.18,CHAR,-.32)
    prism('Grip broad heel',[(-1.62,.31),(-.97,.31),(-.95,.08),(-1.65,.13)],.65,CHAR,.05)
    trigger('Red exposed trigger',-.70,1.41,RED)
    box('Dark upper grip collar',(-1.07,0,1.40),(.93,.79,.15),CHAR,.03)
    box('Red shoulder stock beam',(-2.45,0,1.78),(1.03,.32,.31),RED,.025)
    prism('Open stock lower brace',[(-2.80,1.23),(-2.59,1.26),(-2.04,1.77),(-1.91,1.63),(-2.42,1.05),(-2.82,.96)],.33,CHAR,.035)
    box('Stock butt plate',(-2.9,0,1.39),(.25,.59,1.23),CHAR,.045)
    lathe('Lower red pressure tank',[(.42,.29),(.54,.40),(1.79,.40),(1.94,.30)],RED,10,z=.93)
    for x in [.72,1.57]:lathe('Tank charcoal belt',[(x-.13,.40),(x-.10,.455),(x+.10,.455),(x+.13,.40)],CHAR,10,z=.93)
    path('Bent lower coupling',[(.08,0,1.38),(.04,0,1.11),(.18,0,.96),(.46,0,.94)],.125,CHAR,8)
    lathe('Top rolled shirt cartridge',[(-1.46,.35),(-.41,.35),(-.28,.28)],RED,10,z=2.72)
    lathe('Back cartridge blue section',[(-1.76,.34),(-1.44,.34)],BLUE,10,z=2.72)
    lathe('Yellow cartridge plug',[(-1.96,.28),(-1.76,.31)],YELLOW,10,z=2.72)
    lathe('Rear top cartridge restraint',[(-2.10,.35),(-2.04,.41),(-1.94,.41)],CHAR,10,z=2.72)
    lathe('Open front top cartridge restraint',[(-.40,.35),(-.34,.41),(-.24,.41),(-.20,.35),(-.20,.30),(-.40,.30),(-.40,.35)],CHAR,10,z=2.72,caps=False)
    barrel('Rolled red shirt end',-.14,-.34,.295,RED,2.72)
    # White T-shirt icon on the exposed cartridge face, actual relief geometry.
    for s in [-1,1]:
        prism('White shirt emblem',[(-1.27,2.87),(-1.12,2.92),(-1.05,2.86),(-.98,2.91),(-.82,2.85),(-.88,2.72),(-.95,2.76),(-.96,2.52),(-1.17,2.52),(-1.18,2.75),(-1.25,2.72)],.018,WHITE,.005,s*.351)
        for x,z in [(-1.73,1.97),(-.25,1.95),(-.04,1.44)]:bolt('Silver chassis bolt',x,z,s*.46,SILVER,.095)

def rocket():
    lathe('Long olive tube',[(-2.55,.45),(-2.40,.53),(.55,.53),(.73,.60),(1.72,.60)],OLIVE,10,z=2.10)
    for x in [-2.09,-1.18,.34]:lathe('Charcoal tube clamp',[(x-.11,.54),(x-.085,.59),(x+.09,.59),(x+.115,.54)],CHAR,10,z=2.10)
    barrel('Rear flared shoulder opening',-2.85,-2.45,.75,CHAR,2.10)
    o=lathe('Front polygon flared collar',[(1.42,.61),(1.58,.81),(1.89,.87),(2.04,.79),(2.04,.67),(1.78,.62)],CHAR,10,z=2.10)
    o.data.materials.append(DARK)
    for p in o.data.polygons:
        if p.index>=40 and p.index<50 or p.index==51:p.material_index=1
    lathe('Olive rocket nose',[(1.64,.43),(1.91,.47),(2.42,.29)],OLIVE,10,z=2.10)
    lathe('Yellow nose band',[(1.86,.477),(1.91,.482),(1.99,.454)],YELLOW,10,z=2.10)
    lathe('Red conical tip',[(2.38,.30),(2.69,.065),(2.72,.025)],RED,10,z=2.10)
    grip('Rear dark grip',-1.02,1.64,.51,1.05,CHAR,-.30)
    for s in [-1,1]:prism('Inset walnut rear grip',[(-1.26,1.49),(-.91,1.46),(-1.08,.70),(-1.41,.82)],.025,WOOD,.018,s*.322)
    box('Lower grip mount',(-.95,0,1.56),(.58,.69,.23),CHAR,.045)
    guard('Open guard',-.82,1.56,.80,.52);trigger('Dark trigger',-.40,1.53)
    cyl('Front vertical walnut handle',(.92,0,.99),.205,.88,WOOD,'Z',8)
    for z in [.54,1.45]:cyl('Forward handle dark end',(.92,0,z),.25,.17,CHAR,'Z',8)
    for z in [.75,.91,1.07,1.23]:cyl('Forward grip shallow band',(.92,0,z),.208,.028,WOODD,'Z',8,b=.003)
    ring('Tall open rear aiming loop',[(-1.47,2.59),(-.90,2.59),(-.94,3.16),(-1.33,3.20)],[(-1.30,2.69),(-1.06,2.69),(-1.09,3.00),(-1.25,3.01)],.23,CHAR,.025)
    box('Rear aiming base',(-1.16,0,2.63),(.76,.50,.11),CHAR,.025)
    ring('Small open front sight',[(1.07,2.69),(1.39,2.69),(1.36,3.21),(1.10,3.22)],[(1.17,2.86),(1.29,2.86),(1.28,3.07),(1.18,3.07)],.20,CHAR,.015)
    box('Front sight mount',(1.24,0,2.67),(.48,.46,.14),CHAR,.025)
    for s in [-1,1]:
        for z in [1.89,2.12,2.35]:bolt('Rear clamp hex bolt',-2.1,z,s*.58,EDGE,.07)

def nailgun():
    motor=prism('Yellow broad motor shell',[(-.97,2.60),(-1.10,2.95),(-1.07,3.88),(-.86,4.03),(.98,3.96),(1.21,3.69),(1.26,2.95),(1.02,2.73),(.20,2.58)],.94,YELLOW,.14)
    prism('Rear charcoal bumper',[(.99,4.00),(1.28,3.98),(1.48,3.74),(1.49,2.97),(1.26,2.73),(1.07,2.78),(1.24,3.04),(1.23,3.71)],1.02,CHAR,.06)
    head=box('Front charcoal head',(-1.30,0,3.48),(.66,.85,.99),CHAR,.09)
    box('Front driving nose',(-1.81,0,3.51),(.46,.61,.64),CHAR,.07)
    cyl('Small front tip collar',(-2.12,0,3.51),.19,.27,CHAR)
    cyl('Visible stylized metal pin',(-2.47,0,3.51),.065,.50,SILVER,N=6,b=.0)
    cyl('Flat pin cap',(-2.74,0,3.51),.10,.055,SILVER,N=6,b=.0)
    grip('Yellow long rear handle',.64,2.79,.53,1.78,YELLOW,.25)
    prism('Rear rubber grip',[(.80,2.69),(1.01,2.58),(1.22,1.20),(1.03,1.16),(.80,2.30)],.66,CHAR,.03)
    prism('Finger shaped dark grip',[(.33,2.04),(.59,2.01),(.69,1.15),(.40,1.16),(.35,1.31),(.40,1.43),(.31,1.58),(.36,1.70),(.29,1.85)],.67,CHAR,.035)
    prism('Yellow battery base',[(.05,1.12),(1.32,1.16),(1.50,.87),(1.44,.60),(.02,.55),(-.14,.78)],1.0,YELLOW,.095)
    box('Dark battery foot',(.71,0,.54),(1.53,1.02,.37),CHAR,.08)
    box('Dark trigger housing',(.05,0,2.55),(.76,.73,.31),CHAR,.06)
    trigger('Broad dark trigger',.04,2.49)
    # The long diagonal visible fastener rail is carefully tapered, not a filled slab.
    a=Vector((-1.48,0,2.83));b=Vector((-.59,0,.38));v=b-a;perp=Vector((-v.z,0,v.x)).normalized()
    def pstrip(n,offset,width,depth,mm):
        q=a+perp*offset;r=b+perp*offset
        return prism(n,[(q.x+perp.x*width/2,q.z+perp.z*width/2),(r.x+perp.x*width/2,r.z+perp.z*width/2),(r.x-perp.x*width/2,r.z-perp.z*width/2),(q.x-perp.x*width/2,q.z-perp.z*width/2)],depth,mm,.025)
    pstrip('Recessed dark magazine bed',0,.73,.38,DARK)
    pstrip('Outer magazine left rail',-.35,.15,.57,CHAR);pstrip('Outer magazine right rail',.35,.15,.57,CHAR)
    for i in range(29):
        p=a+v*((i+.8)/30)
        ob=box('Visible silver fastener %02d'%i,(p.x,-.30,p.z),(.50,.10,.048),SILVER,.008);ob.rotation_euler.y=-math.atan2(perp.z,perp.x)
    for t in [.0,.88,1.0]:
        p=a+v*t;ob=box('Magazine end bracket',(p.x,0,p.z),(.91,.67,.29),CHAR,.05);ob.rotation_euler.y=-math.atan2(perp.z,perp.x)
    bolt('Large magazine end bolt',b.x,b.z,-.36,EDGE,.13)
    for s in [-1,1]:
        box('Inset blank brand plaque',(.23,s*.487,3.46),(1.03,.045,.55),CHAR,.06)
        for z in [3.1,3.34,3.58]:
            p=[(.97,z+.09),(1.12,z+.03),(1.12,z-.09),(.97,z-.03)]
            cut=prism('Rear vent cutter',p,.20,DARK,.003,s*.45)
            bpy.context.view_layer.objects.active=motor;q=motor.modifiers.new('Cut rear air vent','BOOLEAN');q.operation='DIFFERENCE';q.object=cut;bpy.ops.object.modifier_apply(modifier=q.name);bpy.data.objects.remove(cut,do_unlink=True)
            prism('Dark recessed rear vent',p,.015,DARK,.001,s*.35)
        for z in [3.33,3.62]:
            p=[(-1.46,z+.09),(-1.16,z-.015),(-1.16,z-.13),(-1.46,z-.035)]
            cut=prism('Front vent cutter',p,.20,DARK,.003,s*.43)
            bpy.context.view_layer.objects.active=head;q=head.modifiers.new('Cut front air vent','BOOLEAN');q.operation='DIFFERENCE';q.object=cut;bpy.ops.object.modifier_apply(modifier=q.name);bpy.data.objects.remove(cut,do_unlink=True)
            prism('Dark recessed front vent',p,.015,DARK,.001,s*.33)
        box('Battery release',(.88,s*.508,.83),(.38,.035,.21),CHAR,.03)

def washer():
    # Separate backpack tank, hose, and handheld washer in a coordinated set.
    box('Blue backpack reservoir',(-1.57,.39,1.76),(1.20,.85,1.43),BLUE,.14)
    box('Ivory tank upper housing',(-1.57,.39,2.80),(1.39,.98,.81),WHITE,.17)
    box('Ivory tank backplate',(-1.05,.75,1.95),(.20,.24,2.00),WHITE,.035)
    box('Visible white reservoir side frame',(-.94,.30,1.80),(.17,1.00,1.48),WHITE,.035)
    cyl('Blue refill cap',(-1.44,.39,3.28),.34,.21,BLUE,'Z',10,.035)
    ring('Backpack open top carry handle',[(-2.04,3.11),(-.99,3.11),(-1.06,3.66),(-1.94,3.66)],[(-1.87,3.19),(-1.17,3.19),(-1.23,3.48),(-1.81,3.48)],.23,CHAR,.045,y=.54)
    for x in [-1.97,-1.27]:
        box('Tank base protective clamp',(x,.33,1.12),(.34,1.06,.33),CHAR,.055)
        box('Tank standing foot',(x,.39,.90),(.26,.64,.18),CHAR,.03)
    prism('Washer yellow housing',[(-.86,2.23),(-.72,2.71),(-.43,2.85),(.67,2.88),(.93,2.66),(.94,2.21),(.62,2.00),(-.46,1.99)],.68,YELLOW,.10,y=-.28)
    cyl('Dark rear washer collar',(-.89,-.28,2.43),.39,.19,CHAR)
    cyl('Front wand collar',(.88,-.28,2.46),.26,.28,CHAR)
    cyl('Long dark spray wand',(1.62,-.28,2.46),.12,1.35,CHAR)
    lathe('Blue ribbed nozzle sleeve',[(2.25,.18),(2.31,.25),(2.75,.25),(2.83,.19)],BLUE,10,y=-.28,z=2.46)
    for i in range(10):
        ang=2*math.pi*(i+.5)/10
        ob=box('Nozzle blue radial rib',(2.55,-.28+math.cos(ang)*.25,2.46+math.sin(ang)*.25),(.32,.035,.035),BLUE,.005)
    lathe('Black tapered nozzle neck',[(2.77,.20),(2.92,.27),(3.13,.29)],CHAR,10,y=-.28,z=2.46)
    nozzle=lathe('Yellow flared spray head',[(3.04,.29),(3.22,.41),(3.61,.43),(3.68,.39),(3.68,.31),(3.40,.27)],YELLOW,10,y=-.28,z=2.46)
    nozzle.data.materials.append(DARK)
    for p in nozzle.data.polygons:
        if p.index>=40 and p.index<50 or p.index==51:p.material_index=1
    cyl('Dark inset spray center',(3.58,-.28,2.46),.18,.12,CHAR)
    cyl('Blue spray orifice',(3.648,-.28,2.46),.087,.02,BLUE,N=8)
    prism('Dark washer handle',[(-.62,2.09),(-.14,2.03),(-.52,.90),(-.88,1.04)],.49,CHAR,.06,y=-.28)
    prism('Yellow handle back stripe',[(-.68,2.06),(-.54,2.03),(-.90,1.05),(-.68,.87),(-.82,.78),(-1.06,1.04)],.52,YELLOW,.035,y=-.28)
    ring('Wide open washer guard',[(-.64,2.02),(.51,2.02),(.68,1.45),(.48,.81),(-.34,.68),(-.66,.86)],[(-.31,1.87),(.29,1.85),(.43,1.44),(.29,1.04),(-.25,.91),(-.43,1.02)],.43,CHAR,.055,y=-.28)
    prism('Long blue trigger',[(-.04,1.99),(.13,1.94),(-.12,1.17),(.0,1.11),(-.14,1.06),(-.31,1.21)],.27,BLUE,.02,y=-.28)
    smoothpath('Low polygon flexible hose',[(-2.14,.43,2.09),(-2.34,.37,1.56),(-2.41,.24,1.02),(-2.27,.1,.63),(-1.95,-.02,.39),(-1.53,-.15,.30),(-1.09,-.23,.35),(-.80,-.28,.53),(-.65,-.28,.80)],.12,CHAR,8)
    for s in [-1,1]:
        y=-.28+s*.352
        box('Black vent panel',(-.29,y,2.46),(.54,.025,.46),DARK,.012)
        for z in [2.32,2.46,2.60]:box('Horizontal vent louver',(-.29,y+s*.02,z),(.48,.035,.047),CHAR,.008)
        prism('Blue side accent badge',[(.12,2.34),(.48,2.34),(.42,2.55),(.16,2.55)],.021,BLUE,.012,y)

BUILDERS={7:draco,8:fartgun,9:shotgun,10:cannon,11:rocket,24:nailgun,29:washer}
def deliver(entry):
    global asset,stage,CHAR,EDGE,DARK,WOOD,WOODD,LIME,GREEN,IVORY,WHITE,BLUE,YELLOW,RED,SILVER,OLIVE
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    for data in list(bpy.data.materials):bpy.data.materials.remove(data)
    scene=bpy.context.scene;asset=bpy.data.collections.new(entry['name']+' | EXPORT');scene.collection.children.link(asset);stage=bpy.data.collections.new('REVIEW | non-exported');scene.collection.children.link(stage)
    CHAR=mat('Charcoal',(.24,.235,.24));EDGE=mat('Warm steel',(.32,.31,.31));DARK=mat('Cavity',(.055,.06,.07),False)
    WOOD=mat('Warm walnut',(.49,.29,.18));WOODD=mat('Walnut groove',(.30,.17,.10));LIME=mat('Lime',(.53,.76,.025));GREEN=mat('Leaf green',(.32,.55,.055));IVORY=mat('Warm ivory',(.72,.71,.65));WHITE=mat('Soft white',(.85,.85,.88));BLUE=mat('Cobalt blue',(.04,.40,.90));YELLOW=mat('Tool yellow',(.98,.69,.08));RED=mat('Coral red',(.84,.19,.20));SILVER=mat('Silver',(.65,.67,.70));OLIVE=mat('Olive',(.40,.44,.22))
    BUILDERS[entry['index']]()
    out=Path(entry['output']);out.mkdir(parents=True,exist_ok=True);shutil.copyfile(entry['source'],out/'Reference.png')
    bpy.ops.object.select_all(action='DESELECT');objects=list(asset.objects)
    for ob in objects:ob.select_set(True)
    bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join();ob=bpy.context.object;ob.name=entry['name'].replace(' ','_')
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    # Remove bevel collapses before UV and exports; all final triangles are explicit.
    bm=bmesh.new();bm.from_mesh(ob.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6);bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-6);bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free();ob.data.update()
    # Unique atlas carries actual broad material breakup into both exports.
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(55),island_margin=.009);bpy.ops.object.mode_set(mode='OBJECT')
    resolution=2048 if entry['index']==8 else 1024
    atlas=bpy.data.images.new(entry['name']+'_BaseColor',width=resolution,height=resolution,alpha=False);atlas.colorspace_settings.name='sRGB'
    scene.render.engine='CYCLES';scene.cycles.samples=1;scene.render.bake.margin=4
    for m in ob.data.materials:
        nt=m.node_tree;bs=nt.nodes.get('Principled BSDF');em=nt.nodes.new('ShaderNodeEmission')
        if bs.inputs['Base Color'].is_linked:nt.links.new(bs.inputs['Base Color'].links[0].from_socket,em.inputs['Color'])
        else:em.inputs['Color'].default_value=bs.inputs['Base Color'].default_value
        nt.links.new(em.outputs[0],nt.nodes.get('Material Output').inputs['Surface']);tx=nt.nodes.new('ShaderNodeTexImage');tx.image=atlas;nt.nodes.active=tx
    bpy.ops.object.bake(type='EMIT');atlas.filepath_raw=str(out/'BaseColor.png');atlas.file_format='PNG';atlas.save();atlas.pack()
    final=mat('Portable baked base color',(.5,.5,.5),False);tx=final.node_tree.nodes.new('ShaderNodeTexImage');tx.image=atlas;final.node_tree.links.new(tx.outputs['Color'],final.node_tree.nodes.get('Principled BSDF').inputs['Base Color']);ob.data.materials.clear();ob.data.materials.append(final)
    for p in ob.data.polygons:p.material_index=0
    # Lower to ground and center useful origin without modifying prop proportions.
    world=[ob.matrix_world@v.co for v in ob.data.vertices];lo=Vector(tuple(min(v[j] for v in world) for j in range(3)));hi=Vector(tuple(max(v[j] for v in world) for j in range(3)))
    ob.location.z-=lo.z;center=(lo+hi)/2;center.z-=lo.z;scene.cursor.location=center;bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    ob['SourceReference']=str(entry['source']);ob['Use']='Stylized non-functional exterior game prop';ob['StudioValidation']='Not imported into Studio'
    bpy.ops.export_scene.fbx(filepath=str(out/'Model.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(out/'Model.glb'),use_selection=True,export_format='GLB',export_animations=False)
    bm=bmesh.new();bm.from_mesh(ob.data)
    stats={'index':entry['index'],'name':entry['name'],'vertices':len(ob.data.vertices),'triangles':sum(len(p.vertices)-2 for p in ob.data.polygons),'mesh_objects':1,'materials':1,'UV':bool(ob.data.uv_layers),'texture':str(resolution)+'x'+str(resolution)+' packed BaseColor.png','nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'loose_vertices':sum(not v.link_edges for v in bm.verts),'zero_area_faces':sum(f.calc_area()<1e-10 for f in bm.faces),'bounds_dimensions':list(ob.dimensions),'limitations':['Single-view reconstruction: reverse details mirrored or inferred.','Assembly has intentional intersecting closed components.','No Studio import or gameplay integration performed.']};bm.free()
    def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
    floor=mat('Neutral review ground',(.52,.52,.52),False);bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.04));g=bpy.context.object;g.name='REVIEW ground';g.data.materials.append(floor);move(g,stage)
    for name,loc,power,size in [('Key',(-4,-6,9),1200,7),('Fill',(5,-5,6),750,6),('Rim',(1,5,8),1200,5)]:
        bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;o.data.energy=power;o.data.size=size;aim(o,center);move(o,stage)
    scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.35,.35,.35,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.65
    look=1 if entry['index'] in [10,11,29] else -1
    bpy.ops.object.camera_add(location=center+Vector((look*7,-18,7)));cam=bpy.context.object;cam.name='Reference comparison camera';aim(cam,center);cam.data.type='ORTHO';cam.data.ortho_scale=max(ob.dimensions.x*.99,ob.dimensions.z*1.20)*1.20;move(cam,stage);scene.camera=cam
    scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1100;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard';scene.view_settings.exposure=-.65
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL'
    scene.render.filepath=str(out/'Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'));bpy.ops.render.render(write_still=True)
    cam.location=center+Vector((-look*6,18,5));aim(cam,center);scene.render.filepath=str(out/'Alternate.png');bpy.ops.render.render(write_still=True)
    cam.location=center+Vector((look*7,-18,7));aim(cam,center);scene.render.filepath=str(out/'Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
    # Reimport each format into fresh scenes and audit actual triangle preservation.
    for ext in ['glb','fbx']:
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
        else:bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
        meshes=[x for x in bpy.context.scene.objects if x.type=='MESH'];count=sum(sum(len(p.vertices)-2 for p in x.data.polygons) for x in meshes)
        zeros=0
        for mm in meshes:
            mm.data.calc_loop_triangles()
            for tri in mm.data.loop_triangles:
                a,b,c=[mm.data.vertices[i].co for i in tri.vertices]
                zeros+=int((b-a).cross(c-a).length<2e-10)
        stats[ext+'_reimport']={'mesh_objects':len(meshes),'triangles':count,'matches_source':count==stats['triangles'],'zero_area_triangles':zeros,'UV':all(bool(x.data.uv_layers) for x in meshes)}
    (out/'validation.json').write_text(json.dumps(stats,indent=2));(out/'README.md').write_text('# '+entry['name']+'\n\nFaithfully reconstructed low-poly exterior game prop from the supplied reference.\n\nRegenerate using `batches/guns/build_guns.py -- '+str(entry['index'])+'` in Blender 5.2 background mode with --threads 4.\n\nOne mesh, portable packed base-color atlas; closed components may intersect intentionally. Unseen reverse details are mirrored/inferred from the visible side. Muzzle cavities are shallow closed visual recesses, without internal mechanisms. Review staging is excluded from FBX/GLB. Actual counts and round-trip checks are in validation.json. Roblox Studio import remains untested.\n')
    print('ASSET_COMPLETE',entry['name'],json.dumps(stats),flush=True)
if __name__=='__main__':
    ids=[int(x) for x in sys.argv[sys.argv.index('--')+1:]] if '--' in sys.argv else list(BUILDERS)
    for idx in ids:deliver(next(e for e in INVENTORY if e['index']==idx))
