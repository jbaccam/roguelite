"""Frozen Knight reference rebuild (2026-10-01).

Source: ../../art-references/frozen-knight-redesign/frozen-knight-turnaround-v1.png
(user-supplied). Fully rigid hard-surface armour: every piece is voxel-fused
from its own sub-volumes, decimated to a faceted low-poly surface and bound to
one bone. Navy undersuit volumes with ball ends overlap every joint; plates
(pauldrons, couters, knee cops, tassets) ride the bone they cover. Colours are
assigned per face from the nearest source volume, so snow caps and plate edges
follow geometry instead of texture noise.

Proportions are measured from the sheet at 0.0092 units per pixel with the
floor at sheet row 764 (about 6.33 units including the crest). The pipeline's
rig convention puts Left at -X while facing -Y, so this model is the mirror of
the sheet; frozen_knight_compare.py mirrors the review strips for comparison.

Blender 5.2 background:  blender --background --python build_frozen_knight.py
QUICK=1 skips the cavity pass and renders the comparison at low samples.
Then: rig_export.py -- frozen-knight ; polish_rig.py -- frozen-knight ;
verify_exports.py -- frozen-knight ; python frozen_knight_compare.py
"""
import sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
import bmesh

QUICK=os.environ.get('QUICK')=='1'
out=reset('frozen-knight')
REF=ROOT.parents[1]/'art-references'/'frozen-knight-redesign'
rng=random.Random(1001)

# Albedo eyedropped from the sheet (sRGB), lifted from the lit sample values.
COL={'steel':(134,142,160),'snow':(226,232,242),'navy':(40,43,60),'tunic':(50,57,80),'leather':(68,46,34),
     'silver':(168,174,188),'glove':(31,31,35),'sole':(84,90,106),'blade':(124,136,156),'frost':(210,228,246),
     'grip':(90,60,42),'ice':(150,206,242),'dark':(12,13,20),'eye':(150,222,255)}
# (noise variation, noise scale, edge-wear lift)
STYLE={'steel':(.08,2.6,.22),'snow':(.04,3,0),'navy':(.07,3,.12),'tunic':(.07,3,.1),'leather':(.08,4,.16),
       'silver':(.05,3,.2),'glove':(.06,3,.28),'sole':(.07,3,.16),'blade':(.06,4,.2),'frost':(.05,5,0),
       'grip':(.08,6,.12),'ice':(.08,3,0),'dark':(0,1,0),'eye':(0,1,0)}
def srgb(c):return tuple(((v/255+.055)/1.055)**2.4 for v in c)
MATS={}
def paint(key):
    """Low-noise painted colour, darkened by the baked per-vertex Cavity
    attribute and lifted on convex edges by the per-vertex Wear attribute."""
    if key is None:return None
    if key in MATS:return MATS[key]
    var,sc,wear=STYLE[key]
    m=mat('Knight '+key,srgb(COL[key]),var,sc,.82)
    n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');ramp=next(x for x in n if x.type=='VALTORGB')
    cav=n.new('ShaderNodeAttribute');cav.attribute_name='Cavity';cav.attribute_type='GEOMETRY'
    cr=n.new('ShaderNodeMapRange');cr.inputs['To Min'].default_value=.58;cr.inputs['To Max'].default_value=1
    mul=n.new('ShaderNodeVectorMath');mul.operation='MULTIPLY'
    l.new(cav.outputs['Fac'],cr.inputs['Value']);l.new(ramp.outputs[0],mul.inputs[0]);l.new(cr.outputs['Result'],mul.inputs[1]);last=mul
    if wear:
        wa=n.new('ShaderNodeAttribute');wa.attribute_name='Wear';wa.attribute_type='GEOMETRY'
        wr=n.new('ShaderNodeMapRange');wr.inputs['To Min'].default_value=1;wr.inputs['To Max'].default_value=1+wear
        m2=n.new('ShaderNodeVectorMath');m2.operation='MULTIPLY'
        l.new(wa.outputs['Fac'],wr.inputs['Value']);l.new(mul.outputs[0],m2.inputs[0]);l.new(wr.outputs['Result'],m2.inputs[1]);last=m2
    l.new(last.outputs[0],p.inputs['Base Color'])
    if key=='eye':
        p.inputs['Emission Color'].default_value=(*srgb(COL[key]),1);p.inputs['Emission Strength'].default_value=4.0
    MATS[key]=m;return m
for k in COL:paint(k)

# ---------------------------------------------------------------- helpers
def active(o):
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
def applied(o):
    active(o);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);return o
def flat(o):
    for p in o.data.polygons:p.use_smooth=False
def bev(o,width,segs=1):
    active(o);mod=o.modifiers.new('Chamfer','BEVEL');mod.width=width;mod.segments=segs;mod.limit_method='ANGLE';mod.angle_limit=math.radians(25)
    bpy.ops.object.modifier_apply(modifier=mod.name);return o
def fuse_to(objects,name,key,voxel,triangles,smooth=1,factor=.45,symmetric=False):
    # Symmetric decimation folds triangles on the mirror plane (black slivers
    # in renders); every call here leaves it off.
    o=join(objects,name);o.data.remesh_voxel_size=voxel;active(o);bpy.ops.object.voxel_remesh()
    if smooth:
        mod=o.modifiers.new('Voxel step blend','SMOOTH');mod.factor=factor;mod.iterations=smooth;bpy.ops.object.modifier_apply(modifier=mod.name)
    o.data.calc_loop_triangles();count=len(o.data.loop_triangles)
    if count>triangles:
        mod=o.modifiers.new('Faceted topology','DECIMATE');mod.ratio=triangles/count
        if symmetric:mod.use_symmetry=True;mod.symmetry_axis='X'
        bpy.ops.object.modifier_apply(modifier=mod.name)
    finish(o,name,paint(key));flat(o);return o
def copy_of(objects,name):
    copies=[]
    for o in objects:
        c=o.copy();c.data=o.data.copy();bpy.context.collection.objects.link(c);copies.append(c)
    return join(copies,name)
def bvh_of(o):return BVHTree.FromObject(o,bpy.context.evaluated_depsgraph_get())
def set_materials(o,keys):
    o.data.materials.clear()
    for k in keys:o.data.materials.append(paint(k))
    return {k:i for i,k in enumerate(keys)}
def sources(groups):
    """Copies of each colour group's source volumes, taken before fusing."""
    return {k:copy_of(v,'SRC_'+k) for k,v in groups.items()}
def paint_nearest(o,src):
    """Per face, the colour of the nearest source volume."""
    keys=list(src);slot=set_materials(o,keys);trees={k:bvh_of(s) for k,s in src.items()}
    for p in o.data.polygons:
        c=p.center;d={k:t.find_nearest(c)[3] for k,t in trees.items()};p.material_index=slot[min(d,key=d.get)]
    for s in src.values():bpy.data.objects.remove(s,do_unlink=True)
    return o
def frame(O,X,Y,Z):
    X,Y,Z,O=Vector(X),Vector(Y),Vector(Z),Vector(O)
    return Matrix(((X.x,Y.x,Z.x,O.x),(X.y,Y.y,Z.y,O.y),(X.z,Y.z,Z.z,O.z),(0,0,0,1)))
def xf(o,M):
    for v in o.data.vertices:v.co=M@v.co
    o.data.update();return o
def axes_up(up,lateral=(1,0,0)):
    """Right-handed frame whose local Z is `up`, X lateral, Y = Z x X (back)."""
    Z=Vector(up).normalized();X=Vector(lateral);X=(X-Z*X.dot(Z)).normalized();return X,Z.cross(X),Z
class Builder:
    """Accumulates many small closed solids into one mesh object."""
    def __init__(self):self.v=[];self.f=[]
    def add(self,verts,faces):
        k=len(self.v);self.v+=[tuple(p) for p in verts];self.f+=[tuple(i+k for i in face) for face in faces]
    def make(self,name,key):return mesh(name,self.v,self.f,paint(key))
BOXF=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
def box(name,center,size,key,X=(1,0,0),Y=(0,1,0),Z=(0,0,1),bevel=.03,segs=2):
    O=Vector(center);X,Y,Z=Vector(X),Vector(Y),Vector(Z);vs=[]
    for sx in(-1,1):
        for sy in(-1,1):
            for sz in(-1,1):vs.append(O+X*sx*size[0]/2+Y*sy*size[1]/2+Z*sz*size[2]/2)
    o=mesh(name,vs,BOXF,paint(key))
    return bev(o,bevel,segs) if bevel else o
def octo(hw,front,back,cf,cb=None,cx=0,cy=0):
    """Chamfered rectangle in plan; front is -Y."""
    cb=cf if cb is None else cb
    return [(cx-hw+cf,cy-front),(cx+hw-cf,cy-front),(cx+hw,cy-front+cf),(cx+hw,cy+back-cb),(cx+hw-cb,cy+back),(cx-hw+cb,cy+back),(cx-hw,cy+back-cb),(cx-hw,cy-front+cf)]
def prism(name,rings,key,bevel=0,segs=1):
    """Closed loft through equal-count rings: [(z,[(x,y)..])..] or [[xyz..]..]."""
    if isinstance(rings[0],tuple):pts=[[Vector((x,y,z)) for x,y in ring] for z,ring in rings]
    else:pts=[[Vector(p) for p in ring] for ring in rings]
    n=len(pts[0]);m=len(pts);verts=[p for ring in pts for p in ring]
    faces=[tuple(range(n-1,-1,-1))]+[(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(m-1) for k in range(n)]+[tuple(range((m-1)*n,m*n))]
    o=mesh(name,verts,faces,paint(key))
    return bev(o,bevel,segs) if bevel else o
def loft(name,levels,key,side=1,exponent=.85,shape=None,n=40):
    """Rings of (z, cx, cy, half-width, front depth, back depth); -Y is forward."""
    rings=[]
    for j in range(len(levels)-1):
        p0=levels[max(0,j-1)];p1=levels[j];p2=levels[j+1];p3=levels[min(len(levels)-1,j+2)]
        for k in range(3):
            t=k/3;rings.append([.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t) for a,b,c,d in zip(p0,p1,p2,p3)])
    rings.append(levels[-1]);verts=[]
    for z,cx,cy,rx,front,back in rings:
        for k in range(n):
            a=k*math.tau/n;co=math.cos(a);si=math.sin(a)
            x=side*(cx+rx*math.copysign(abs(co)**exponent,co));y=cy+(back if si>=0 else front)*math.copysign(abs(si)**exponent,si)
            if shape:x,y=shape(x,y,z,co,si)
            verts.append((x,y,z))
    faces=[tuple(range(n-1,-1,-1))]+[(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(len(rings)-1) for k in range(n)]+[tuple(range((len(rings)-1)*n,len(rings)*n))]
    return mesh(name,verts,faces,paint(key))
def band(name,z0,z1,rx,front,back,thick,key,cy=.04,n=48):
    verts=[]
    for z,grow in [(z0,0),(z1,0),(z1,thick),(z0,thick)]:
        for k in range(n):
            a=k*math.tau/n;co=math.cos(a);si=math.sin(a)
            verts.append(((rx+grow)*math.copysign(abs(co)**.8,co),cy+((back if si>=0 else front)+grow)*math.copysign(abs(si)**.8,si),z))
    faces=[(r*n+k,r*n+(k+1)%n,((r+1)%4)*n+(k+1)%n,((r+1)%4)*n+k) for r in range(4) for k in range(n)]
    return mesh(name,verts,faces,paint(key))
def ball(name,c,r,key,seg=14,rings=9):
    rr=r if isinstance(r,(tuple,list)) else (r,r,r)
    return applied(ell(name,c,rr,paint(key),seg,rings))
def lerp(a,b,t):return Vector(a).lerp(Vector(b),t)
def blanket(name,targets,center,rx,ry,thick,wave=.09,seed=0,nr=5,na=28,sink=.07):
    """Snow cap: a closed slab draped from above onto `targets`, wavy outer edge."""
    probe=copy_of(targets,'PROBE');tree=bvh_of(probe);bpy.data.objects.remove(probe,do_unlink=True)
    r=random.Random(seed);ph=[r.uniform(0,6.3) for _ in range(3)];cx,cy=center
    def hz(x,y,fallback):
        loc,nor,i,d=tree.ray_cast(Vector((x,y,20)),Vector((0,0,-1)),40)
        return loc.z if loc is not None else fallback
    z0=hz(cx,cy,0);top=[Vector((cx,cy,z0+thick))];bot=[Vector((cx,cy,z0-sink))];prev=[z0]*na
    for i in range(1,nr+1):
        t=i/nr;ring=[]
        for k in range(na):
            a=k*math.tau/na;e=1+wave*(.55*math.sin(3*a+ph[0])+.30*math.sin(7*a+ph[1])+.15*math.sin(11*a+ph[2]))
            x=cx+rx*t*e*math.cos(a);y=cy+ry*t*e*math.sin(a);z=hz(x,y,prev[k]-.06);prev[k]=z
            top.append(Vector((x,y,z+thick*(1-.35*t**3))));bot.append(Vector((x,y,z-sink)))
    verts=top+bot;B=len(top);faces=[]
    def T(i,k):return 0 if i==0 else 1+(i-1)*na+k%na
    for k in range(na):faces.append((T(0,0),T(1,k),T(1,k+1)));faces.append((B+T(0,0),B+T(1,k+1),B+T(1,k)))
    for i in range(1,nr):
        for k in range(na):faces.append((T(i,k),T(i+1,k),T(i+1,k+1),T(i,k+1)));faces.append((B+T(i,k),B+T(i,k+1),B+T(i+1,k+1),B+T(i+1,k)))
    for k in range(na):faces.append((T(nr,k),B+T(nr,k),B+T(nr,k+1),T(nr,k+1)))
    return mesh(name,verts,faces,paint('snow'))
def crystals(name,base,specs):
    """Clustered hexagonal ice crystals rooted below `base`."""
    b=Builder()
    for off,d,L,rad in specs:
        d=Vector(d).normalized();t=d.orthogonal().normalized();s=d.cross(t);c=Vector(base)+Vector(off)
        rings=[(c-d*.09,rad*.9),(c+d*L*.70,rad)];verts=[]
        for p,rr in rings:
            for k in range(6):a=k*math.tau/6+.3;verts.append(p+(t*math.cos(a)+s*math.sin(a))*rr)
        verts.append(c+d*L)
        faces=[tuple(range(5,-1,-1))]+[(k,(k+1)%6,6+(k+1)%6,6+k) for k in range(6)]+[(6+k,6+(k+1)%6,12) for k in range(6)]
        b.add(verts,faces)
    o=b.make(name,'ice');flat(o);return o
def mirrored(o,name,bone):
    c=o.copy();c.data=o.data.copy();bpy.context.collection.objects.link(c);c.name=name
    for v in c.data.vertices:v.co.x=-v.co.x
    bm=bmesh.new();bm.from_mesh(c.data);bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.to_mesh(c.data);bm.free();c.data.update()
    return rigid(c,bone)
def finals_add(o,bone,both=True,left_name=None):
    rigid(o,'Right'+bone if both else bone);flat(o);FINALS.append(o)
    if both:FINALS.append(mirrored(o,left_name or o.name.replace('Right','Left'),'Left'+bone))
    return o
FINALS=[]

# ---------------------------------------------------------------- skeleton anchors (Right side, +X)
S=Vector((1.10,.08,4.40));E=Vector((1.38,.06,3.42));WR=Vector((1.54,.10,2.64))
HP=Vector((.50,.06,2.45));KN=Vector((.62,-.02,1.45));AN=Vector((.70,.14,.56));TOE=Vector((.74,-.82,.14))
FORE=(WR-E).normalized()

# ---------------------------------------------------------------- head: bucket helm
up=prism('Helm upper',[(5.27,octo(.60,.64,.62,.17,.13,0,-.08)),(5.96,octo(.58,.60,.60,.17,.13,0,-.06)),(6.10,octo(.45,.46,.50,.13,.11,0,-.04))],'steel',.03,2)
fg=prism('Faceguard',[(4.84,octo(.60,.66,.58,.18,.14,0,-.08)),(4.92,octo(.645,.73,.66,.19,.15,0,-.08)),(5.29,octo(.645,.75,.66,.19,.15,0,-.08)),(5.36,octo(.61,.69,.60,.18,.14,0,-.08))],'steel',.025,2)
poly=[(-.80,5.42),(-.80,6.05),(-.72,6.18),(.22,6.34),(.44,6.25),(.50,6.06),(.30,5.97),(-.58,5.97),(-.62,5.42)]
crest=prism('Crest fin',[[(-.10,y,z) for y,z in poly],[(.10,y,z) for y,z in poly]],'steel',.025,1)
hsnow=blanket('Helm snow',[up],(0,-.05),.54,.57,.045,seed=3)
# Visor slit and breathing slots are carved into the clean prisms before the
# voxel fuse (booleans on the decimated mesh are unreliable on its mirror
# seam); recess faces take the dark colour from the nearest cutter.
cutters=[box('Visor cut',(0,-.80,5.31),(1.0,.36,.17),None,bevel=0)]+[box('Breath slot',(x,-.83,5.03),(.085,.36,.22),None,bevel=0) for x in (-.30,0,.30)]
src=sources({'steel':[up,fg,crest],'snow':[hsnow],'dark':cutters})
def carve(o,cutter):
    active(o);mod=o.modifiers.new('Carve','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
for c in cutters:
    for o in (up,fg):carve(o,c)
    bpy.data.objects.remove(c,do_unlink=True)
helm=paint_nearest(fuse_to([up,fg,crest,hsnow],'Frost helm','steel',.018 if QUICK else .014,2600,1,.4),src)
eyes=[ball('Visor eye',(s*.21,-.665,5.31),(.085,.04,.058),'eye',12,8) for s in (-1,1)]
for o in [helm]+eyes:rigid(o,'Head');flat(o);FINALS.append(o)

# ---------------------------------------------------------------- chest: undersuit, cuirass, emblem
suit=loft('Torso suit',[(3.05,0,.03,.60,.50,.50),(3.40,0,.03,.64,.54,.52),(3.90,0,.03,.72,.60,.56),(4.30,0,.03,.74,.60,.56),
                        (4.55,0,.03,.56,.46,.46),(4.66,0,.03,.34,.34,.34),(4.98,0,0,.31,.32,.31),(5.10,0,0,.18,.18,.18)],'navy',exponent=.9,n=32)
torso=fuse_to([suit]+[ball('Shoulder mass',(s*.92,.06,4.30),(.34,.38,.34),'navy') for s in (-1,1)],'Torso undersuit','navy',.03,700,2,.5)
def plate(hw,front,back,cf,cb,crease,cy=.03):
    o=octo(hw,front,back,cf,cb,0,cy);return [o[0],(0,cy-front-crease)]+o[1:]
cu=prism('Cuirass',[(3.34,plate(.66,.60,.58,.22,.20,.02)),(3.52,plate(.78,.72,.64,.26,.22,.04)),(3.85,plate(.85,.78,.67,.28,.24,.06)),
                    (4.20,plate(.86,.79,.68,.28,.24,.06)),(4.46,plate(.80,.73,.66,.26,.22,.05)),(4.62,plate(.62,.60,.57,.20,.18,.03)),
                    (4.73,plate(.42,.46,.46,.14,.14,.0))],'steel',.03,1)
for v in cu.data.vertices:
    w=max(0,min(1,(.2-v.co.y)/.5));floor=3.34+w*.32*min(1,abs(v.co.x)/.75)
    if v.co.z<floor:v.co.z=floor
cu.data.update();tree=bvh_of(cu)
def front_y(z,x=0):
    loc,_,_,_=tree.ray_cast(Vector((x,-5,z)),Vector((0,1,0)),10);return loc.y
kite=[Vector((0,front_y(4.62)+.03,4.62)),Vector((-.20,front_y(4.32,-.20)+.03,4.32)),Vector((.20,front_y(4.32,.20)+.03,4.32)),Vector((0,front_y(3.46)+.03,3.46)),
      Vector((0,front_y(4.44)-.13,4.44)),Vector((0,front_y(3.90)-.11,3.90))]
emblem=mesh('Emblem ridge',kite,[(0,2,4),(0,4,1),(1,4,5),(4,2,5),(1,5,3),(5,2,3),(0,1,3),(0,3,2)],paint('steel'))
cuirass=fuse_to([cu,emblem],'Cuirass','steel',.022 if QUICK else .018,2400,1,.4)
for o in [torso,cuirass]:rigid(o,'Chest');FINALS.append(o)

# ---------------------------------------------------------------- pelvis: hips, belt, buckle, tunic
hips=loft('Hip suit',[(2.28,0,.04,.62,.50,.56),(2.55,0,.04,.82,.58,.64),(2.90,0,.04,.80,.58,.62),(3.20,0,.04,.70,.55,.55),(3.45,0,.04,.62,.50,.50)],'navy',exponent=.85,n=32)
hips=fuse_to([hips]+[ball('Hip ball',(s*.50,.06,2.45),(.38,.40,.38),'navy') for s in (-1,1)],'Hip undersuit','navy',.03,520,2,.5)
belt=band('Belt',2.97,3.25,.74,.60,.60,.09,'leather')
bz=3.11;by=-.71
buckle=fuse_to([box('Buckle bar',(0,by,bz+.15),(.42,.06,.08),'silver',bevel=.012),box('Buckle bar',(0,by,bz-.15),(.42,.06,.08),'silver',bevel=.012),
                box('Buckle bar',(-.17,by,bz),(.08,.06,.38),'silver',bevel=.012),box('Buckle bar',(.17,by,bz),(.08,.06,.38),'silver',bevel=.012),
                box('Buckle prong',(-.05,by-.01,bz),(.18,.04,.035),'silver',bevel=.008)],'Belt buckle','silver',.008,260,1,.3)
tunic=[prism('Tunic flap',[(2.02,octo(.21,.63,-.53,.02,.02)),(2.98,octo(.17,.62,-.54,.02,.02))],'tunic',.015,1),
       prism('Tunic flap back',[(2.10,octo(.21,-.64,.75,.02,.02)),(2.98,octo(.17,-.62,.73,.02,.02))],'tunic',.015,1)]
for o in [hips,join([belt,buckle]+tunic,'Belt and tunic')]:rigid(o,'Pelvis');flat(o);FINALS.append(o)

# ---------------------------------------------------------------- arms (built on the Right, mirrored)
arm=fuse_to([tube('Upper arm suit',[S+Vector((-.04,0,.06)),lerp(S,E,.35),lerp(S,E,.7),E],[.30,.31,.29,.27],paint('navy'),12),
             ball('Shoulder ball',S,(.33,.34,.33),'navy'),ball('Elbow ball',E,.27,'navy')],'Right upper arm suit','navy',.025,320,2,.5)
finals_add(arm,'UpperArm')
def lame(z0,z1,cx,rx,ry):
    return loft('Pauldron lame',[(z0,cx,.06,rx-.035,ry-.035,ry-.035),(z0+.035,cx,.06,rx,ry,ry),(z1-.025,cx,.06,rx,ry,ry),(z1,cx,.06,rx-.04,ry-.04,ry-.04)],'steel',exponent=.75,n=32)
dome=loft('Pauldron dome',[(4.36,1.22,.06,.52,.62,.62),(4.62,1.21,.06,.50,.60,.60),(4.80,1.18,.06,.40,.50,.50),(4.91,1.15,.06,.22,.30,.30)],'steel',exponent=.75,n=32)
lames=[lame(4.20,4.40,1.25,.50,.66),lame(4.02,4.22,1.29,.44,.60),lame(3.86,4.04,1.31,.38,.54)]
psnow=blanket('Pauldron snow',[dome],(1.17,.05),.44,.52,.055,seed=7)
src=sources({'steel':[dome]+lames,'snow':[psnow]})
pauldron=paint_nearest(fuse_to([dome]+lames+[psnow],'Right pauldron','steel',.019 if QUICK else .016,1300),src)
pauldron=join([pauldron,ball('Pauldron rivet',(1.12,-.605,4.30),.042,'silver',8,6)],'Right pauldron')
finals_add(pauldron,'UpperArm')
fore=fuse_to([tube('Forearm suit',[E,lerp(E,WR,.5),WR+FORE*.02],[.25,.24,.22],paint('navy'),12),ball('Elbow ball',E,.27,'navy')],'Right forearm suit','navy',.025,260,2,.5)
finals_add(fore,'Forearm')
Xl,Yl,Zl=axes_up(-FORE);FM=frame(WR,Xl,Yl,Zl)
def oct_ring(z,hw,cf):return (z,octo(hw,hw,hw,cf))
vam=xf(prism('Vambrace',[oct_ring(0,.36,.12),oct_ring(.05,.40,.13),oct_ring(.15,.38,.13),oct_ring(.60,.34,.11),oct_ring(.70,.30,.10)],'steel',.02,1),FM)
nc=(Xl*.8+Yl*.6).normalized();a2=nc.cross(Zl).normalized();cc=FM@Vector((.30,.12,.80))
couter=applied(ell('Couter',(0,0,0),(1,1,1),paint('steel'),12,8))
for v in couter.data.vertices:v.co=cc+a2*v.co.x*.21+Zl*v.co.z*.25+nc*v.co.y*.075
boss=mesh('Couter boss',[cc+nc*.05+(a2*math.cos(a)+Zl*math.sin(a))*.09 for a in [k*math.tau/6 for k in range(6)]]+[cc+nc*.15],
          [tuple(range(5,-1,-1))]+[(k,(k+1)%6,6) for k in range(6)],paint('steel'))
vambrace=fuse_to([vam,couter,boss],'Right vambrace','steel',.017 if QUICK else .014,700)
straps=[xf(prism('Vambrace strap',[oct_ring(z0,hw,.13),oct_ring(z0+.09,hw,.13)],'leather',.012,1),FM) for z0,hw in [(.22,.405),(.46,.385)]]
rivets=[ball('Strap rivet',FM@Vector((hw+.02,-.10,z)),.036,'silver',8,6) for z,hw in [(.265,.405),(.505,.385)]]
vambrace=join([vambrace]+straps+rivets,'Right vambrace')
finals_add(vambrace,'Forearm')

# ---------------------------------------------------------------- fists and sword
def fist(name,wrist,F,K0,theta,r,l0):
    """Gloved fist around a handle tunnel. The back of the hand faces U, the
    knuckle line runs along K (pinky -> index), the hand's long axis is F (in
    line with the forearm). The tunnel axis A sits `theta` degrees from F, so
    the index curls lower than the little finger (the diagonal grip). Each
    finger curls in its own plane around the tunnel; the thumb wraps over the
    top and rests on the index and middle fingers."""
    F=Vector(F).normalized();K=(Vector(K0)-F*Vector(K0).dot(F)).normalized();U=K.cross(F).normalized()
    th=math.radians(theta);A=(F*math.cos(th)+K*math.sin(th)).normalized();W=Vector(wrist);cot=math.cos(th)/math.sin(th)
    def at(u,l,k):return W+U*u+F*l+K*k
    fr=.072;R=r+fr+.012;Rl=r/math.sin(th)+fr+.012;parts=[]
    parts.append(box(name+' wrist',at(.03,-.07,0),(.36,.30,.42),'glove',U,F,K,.07,2))
    parts.append(box(name+' back',at(R+.02,l0*.33,0),(.15,l0*.80,.50),'glove',U,F,K,.06,2))
    lc_index=l0+.195*cot
    for j in range(4):
        k=(j-1.5)*.13;lc=l0+k*cot;s=.93 if j==0 else 1
        pts=[at(R+.03,lc-Rl*1.15,k*.95),at(R,lc+Rl*.35,k),at(R*.25,lc+Rl,k),at(-R*.75,lc+Rl*.82,k),at(-R,lc+Rl*.05,k),at(-R*.62,lc-Rl*.72,k),at(-R*.02,lc-Rl*.96,k)]
        parts.append(tube(name+' finger',pts,[fr*s,fr*s,fr*s,fr*s,fr*s,fr*s*.95,fr*s*.86],paint('glove'),10))
        parts.append(ball(name+' knuckle',at(R+.01,lc+Rl*.30,k),.084*s,'glove',10,7))
    parts.append(ball(name+' thenar',at(R-.06,lc_index-.24,.19),(.12,.12,.12),'glove',12,8))
    parts.append(tube(name+' thumb',[at(R-.02,lc_index-.32,.23),at(.03,lc_index-Rl-.08,.25),at(-R-.03,lc_index-.12,.20),at(-R-.07,lc_index+.02,.11)],
                      [.088,.082,.076,.066],paint('glove'),10))
    return parts,W+F*l0,A,U,K
fist_parts,GRIP,BLADE,FU,FK=fist('Right fist',WR,FORE,(-.45,-1,0),58,.088,.34)
rfist=fuse_to(fist_parts,'Right gloved fist','glove',.013 if QUICK else .011,1050,1,.4)
rigid(rfist,'RightHand');flat(rfist);FINALS.append(rfist)
lparts,LGRIP,_,_,_=fist('Left fist',WR,FORE,(-.15,-1,0),78,.05,.31)
lfist=fuse_to(lparts,'Left gloved fist','glove',.013 if QUICK else .011,950,1,.4)
FINALS.append(mirrored(lfist,'Left gloved fist','LeftHand'));bpy.data.objects.remove(lfist,do_unlink=True)

# Broadsword: handle through the fist tunnel; the edges lie in the blade/forearm
# plane (hammer grip), so the flat faces the back of the hand and a horizontal
# sweep leads with the edge.
A=BLADE;WD=(FORE-A*FORE.dot(A)).normalized();NF=A.cross(WD).normalized()
def blade_mesh():
    st=[.50,.78,1.06,1.34,1.62,1.88,2.10];hw=[.228,.224,.219,.213,.206,.197,.186];tt=[.050,.048,.046,.044,.042,.040,.038]
    stations=list(zip(st,hw,tt))+[(2.30,.11,.026)];verts=[];mats=[]
    for s,h,t in stations:
        c=GRIP+A*s;b1=.065+.025*rng.uniform(-1,1);b2=.065+.025*rng.uniform(-1,1);te=.013
        for w,n in [(h,0),(h-b1,te),(0,t),(-h+b2,te),(-h,0),(-h+b2,-te),(0,-t),(h-b1,-te)]:verts.append(c+WD*w+NF*n)
    verts.append(GRIP+A*2.45);tip=len(verts)-1;faces=[tuple(range(7,-1,-1))];m=len(stations)
    FROST={0,3,4,7}
    for j in range(m-1):
        for k in range(8):faces.append((j*8+k,j*8+(k+1)%8,(j+1)*8+(k+1)%8,(j+1)*8+k));mats.append(1 if k in FROST else 0)
    for k in range(8):faces.append(((m-1)*8+k,(m-1)*8+(k+1)%8,tip));mats.append(1)
    o=mesh('Blade',verts,faces,None);slot=set_materials(o,['blade','frost'])
    for p,mi in zip(o.data.polygons,[0]+mats):p.material_index=mi
    return o
guard=box('Crossguard',GRIP+A*.46,(.80,.10,.15),'steel',WD,A,NF,.03,1)
for v in guard.data.vertices:
    d=(v.co-(GRIP+A*.46)).dot(WD)
    if abs(d)>.3:v.co+=NF*(v.co-(GRIP+A*.46)).dot(NF)*.35+A*(v.co-(GRIP+A*.46)).dot(A)*.3
handle=tube('Grip wrap',[GRIP+A*(-.42+.084*i) for i in range(11)],[.086 if i%2 else .095 for i in range(11)],paint('grip'),8)
pommel=ball('Pommel',GRIP-A*.50,(.12,.12,.12),'steel',10,6)
for v in pommel.data.vertices:v.co-=A*(v.co-(GRIP-A*.50)).dot(A)*.18
sword=join([blade_mesh(),guard,handle,pommel],'Frost broadsword');rigid(sword,'RightHand');flat(sword);FINALS.append(sword)

# ---------------------------------------------------------------- legs (built on the Right, mirrored)
thigh=fuse_to([tube('Thigh suit',[HP+Vector((0,0,.12)),lerp(HP,KN,.35),lerp(HP,KN,.7),KN],[.37,.37,.34,.31],paint('navy'),12),
               ball('Hip ball',HP,(.38,.40,.38),'navy'),ball('Knee ball',KN,.31,'navy')],'Right thigh suit','navy',.025,360,2,.5)
finals_add(thigh,'Thigh')
def panel(a0,a1,c=(.40,.04),top=(2.95,.55,.70),bottom=(2.06,.62,.77),thick=.07,cols=5,chamfer=7):
    """Curved hanging tasset plate on an ellipse around the hip; chamfered bottom corners."""
    vs=[];cx,cy=c
    for z,rx,ry,inset in [(top[0],top[1],top[2],0),(bottom[0]+.10,bottom[1]-.01,bottom[2]-.01,0),(bottom[0],bottom[1],bottom[2],chamfer)]:
        for layer in (0,1):
            for i in range(cols):
                a=math.radians(a0+inset+(a1-a0-2*inset)*i/(cols-1));g=1-layer*thick/max(rx,ry)
                vs.append((cx+rx*g*math.cos(a),cy+ry*g*math.sin(a),z))
    n=cols;faces=[]
    def V(row,layer,i):return (row*2+layer)*n+i
    for row in range(2):
        for i in range(n-1):
            faces.append((V(row,0,i),V(row,0,i+1),V(row+1,0,i+1),V(row+1,0,i)));faces.append((V(row,1,i),V(row+1,1,i),V(row+1,1,i+1),V(row,1,i+1)))
        faces.append((V(row,0,0),V(row+1,0,0),V(row+1,1,0),V(row,1,0)));faces.append((V(row,0,n-1),V(row,1,n-1),V(row+1,1,n-1),V(row+1,0,n-1)))
    for i in range(n-1):
        faces.append((V(0,0,i),V(0,1,i),V(0,1,i+1),V(0,0,i+1)));faces.append((V(2,0,i),V(2,0,i+1),V(2,1,i+1),V(2,1,i)))
    return bev(mesh('Tasset plate',vs,faces,paint('steel')),.018,1)
tasset=fuse_to([panel(-113,-49),panel(-40,38),panel(48,112)],'Right tassets','steel',.017 if QUICK else .014,480)
finals_add(tasset,'Thigh')
kc=Vector((.64,-.38,1.45));kn=Vector((.18,-1,.06)).normalized();kx,ky,kz=axes_up(kn,(1,0,0))
KM=frame(kc,kx,ky,kz)
disk=xf(prism('Knee cop',[(-.06,octo(.36,.36,.36,.21)),(-.02,octo(.41,.41,.41,.24)),(.04,octo(.40,.40,.40,.235)),(.075,octo(.31,.31,.31,.18))],'steel',.015,1),KM)
kboss=mesh('Knee boss',[KM@Vector((math.cos(a)*.26,math.sin(a)*.26,.06)) for a in [k*math.tau/8+.39 for k in range(8)]]+[KM@Vector((0,0,.20))],
           [tuple(range(7,-1,-1))]+[(k,(k+1)%8,8) for k in range(8)],paint('steel'))
wing=box('Knee wing',(.97,-.22,1.42),(.08,.30,.38),'steel',bevel=.02,segs=1)
kneecop=fuse_to([disk,kboss,wing],'Right knee cop','steel',.016 if QUICK else .013,340)
finals_add(kneecop,'Thigh')
shin=fuse_to([tube('Shin suit',[KN,lerp(KN,AN,.5),AN+Vector((0,0,-.04))],[.30,.29,.27],paint('navy'),12),ball('Knee ball',KN,.31,'navy')],'Right shin suit','navy',.025,260,2,.5)
finals_add(shin,'Shin')
sx,sy,sz=axes_up(KN-AN);SM=frame(AN,sx,sy,sz)
gr=xf(prism('Greave',[(.16,[(-.20,-.30),(.20,-.30),(.30,-.20),(.30,-.08),(-.30,-.08),(-.30,-.20)]),(.20,[(-.22,-.36),(.22,-.36),(.33,-.22),(.33,-.08),(-.33,-.08),(-.33,-.22)]),
                               (.50,[(-.21,-.35),(.21,-.35),(.31,-.21),(.31,-.08),(-.31,-.08),(-.31,-.21)]),(.56,[(-.17,-.30),(.17,-.30),(.27,-.18),(.27,-.08),(-.27,-.08),(-.27,-.18)])],'steel',.02,1),SM)
greave=fuse_to([gr],'Right greave','steel',.017 if QUICK else .014,420)
gstrap=xf(prism('Greave strap',[(.24,octo(.33,.385,.32,.12,.10)),(.34,octo(.33,.385,.32,.12,.10))],'leather',.012,1),SM)
gb=SM@Vector((.17,-.40,.29))
gbuckle=fuse_to([box('Greave buckle',gb+sy*.0+sz*.05,(.17,.04,.04),'silver',sx,sy,sz,.01,1),box('Greave buckle',gb-sz*.05,(.17,.04,.04),'silver',sx,sy,sz,.01,1),
                 box('Greave buckle',gb+sx*.065,(.04,.04,.14),'silver',sx,sy,sz,.01,1),box('Greave buckle',gb-sx*.065,(.04,.04,.14),'silver',sx,sy,sz,.01,1)],'Greave buckle','silver',.007,160)
greave=join([greave,gstrap,gbuckle],'Right greave')
finals_add(greave,'Shin')
sole=box('Sabaton sole',(.76,-.14,.085),(1.04,1.68,.17),'sole',bevel=.045,segs=2)
upper=prism('Sabaton upper',[(.15,octo(.46,.80,.76,.24,.14,.76,-.14)),(.40,octo(.44,.74,.72,.22,.13,.76,-.14)),(.50,octo(.36,.58,.64,.18,.12,.76,-.12))],'steel',.03,1)
cuff=prism('Sabaton cuff',[(.38,octo(.40,.42,.40,.13,.13,.72,.14)),(.72,octo(.38,.40,.38,.12,.12,.72,.14)),(.76,octo(.34,.36,.34,.11,.11,.72,.14))],'steel',.02,1)
toe=prism('Toe cap',[(.38,octo(.40,.30,.30,.14,.04,.76,-.62)),(.51,octo(.36,.27,.28,.12,.04,.76,-.62))],'steel',.02,1)
tsnow=blanket('Toe snow',[toe],(.76,-.64),.36,.25,.04,seed=11)
src=sources({'sole':[sole],'steel':[upper,cuff,toe],'snow':[tsnow]})
sabaton=paint_nearest(fuse_to([sole,upper,cuff,toe,tsnow],'Right sabaton','steel',.019 if QUICK else .016,950),src)
sabaton=join([sabaton,box('Boot strap',(1.215,.20,.29),(.035,.13,.26),'leather',bevel=.01,segs=1),ball('Boot rivet',(1.24,.20,.33),.036,'silver',8,6)],'Right sabaton')
finals_add(sabaton,'Foot')

# ---------------------------------------------------------------- ice crystals (sheet: Right pauldron, outer Left boot)
pc=crystals('Pauldron crystals',(1.15,.02,4.84),[((0,0,0),(.25,-.10,1),.50,.075),((-.12,-.10,0),(-.35,-.25,1),.32,.06),((.14,.05,-.03),(.65,.10,1),.30,.055),
                                                 ((.0,.14,-.02),(.10,.50,1),.24,.05),((.10,-.14,-.02),(.30,-.55,1),.22,.045)])
rigid(pc,'RightUpperArm');FINALS.append(pc)
bc=crystals('Boot crystals',(-1.12,.24,.56),[((0,0,0),(-.35,.20,1),.50,.065),((-.03,-.12,-.04),(-.70,-.05,1),.36,.055),((.02,.13,-.03),(-.20,.50,1),.30,.05)])
rigid(bc,'LeftFoot');FINALS.append(bc)

# ---------------------------------------------------------------- cavity, wear, anatomy
def cavity(objects,rays=40,reach=.28):
    bm=bmesh.new()
    for o in objects:bm.from_mesh(o.data)
    tree=BVHTree.FromBMesh(bm);bm.free();g=math.pi*(3-math.sqrt(5));dirs=[]
    for i in range(rays):
        z=1-(i+.5)/rays;r=math.sqrt(1-z*z);dirs.append(Vector((r*math.cos(g*i),r*math.sin(g*i),math.sqrt(z))))
    for o in objects:
        me=o.data;vals=[]
        for v in me.vertices:
            n=v.normal.normalized();t=n.orthogonal().normalized();b=n.cross(t);origin=v.co+n*.01;occ=0
            for d in dirs:
                loc,_,_,dist=tree.ray_cast(origin,t*d.x+b*d.y+n*d.z,reach)
                if loc is not None:occ+=1-dist/reach*.5
            vals.append(max(0,1-occ/rays*1.25))
        attr=me.attributes.get('Cavity') or me.attributes.new('Cavity','FLOAT','POINT');attr.data.foreach_set('value',vals)
def wear(o):
    """Convex-edge highlight: how far each vertex stands out of its neighbours."""
    bm=bmesh.new();bm.from_mesh(o.data);bm.verts.ensure_lookup_table();bm.normal_update();vals=[]
    for v in bm.verts:
        nb=[e.other_vert(v).co for e in v.link_edges]
        if not nb:vals.append(0);continue
        mean=sum(nb,Vector())/len(nb);el=sum((p-v.co).length for p in nb)/len(nb)
        vals.append(max(0,min(1,((v.co-mean).dot(v.normal)/max(el,1e-5)-.06)*2.4)))
    bm.free();attr=o.data.attributes.get('Wear') or o.data.attributes.new('Wear','FLOAT','POINT');attr.data.foreach_set('value',vals)
def clean(o):
    """Drop zero-volume pillows (a face and its reversed twin) that decimation
    can leave; rig_export's weld would otherwise leave them open."""
    bm=bmesh.new();bm.from_mesh(o.data);seen={};dup=[]
    for f in bm.faces:
        k=tuple(sorted(v.index for v in f.verts))
        if k in seen:dup+=[f,seen[k]]
        else:seen[k]=f
    if dup:
        bmesh.ops.delete(bm,geom=list(set(dup)),context='FACES')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(o.data);bm.free();o.data.update()
    if dup:print('CLEANED',o.name,len(set(dup)),flush=True)
for o in FINALS:clean(o);flat(o);wear(o)
if QUICK:
    for o in FINALS:
        a=o.data.attributes.new('Cavity','FLOAT','POINT');a.data.foreach_set('value',[1]*len(o.data.vertices))
else:cavity(FINALS)
HAND_TAIL=WR+FORE*.5;FOOT=TOE
spec={'Pelvis':[[0,.05,2.48],[0,.05,3.30],None],'Chest':[[0,.05,3.30],[0,.02,4.78],'Pelvis'],'Head':[[0,.02,4.78],[0,-.06,6.10],'Chest']}
for side,s in [('Left',-1),('Right',1)]:
    m=lambda v:[round(s*v[0],4),round(v[1],4),round(v[2],4)]
    spec.update({side+'UpperArm':[m(S),m(E),'Chest'],side+'Forearm':[m(E),m(WR),side+'UpperArm'],side+'Hand':[m(WR),m(HAND_TAIL),side+'Forearm'],
                 side+'Thigh':[m(HP),m(KN),'Pelvis'],side+'Shin':[m(KN),m(AN),side+'Thigh'],side+'Foot':[m(AN),m(FOOT),side+'Shin']})
# Sword measurements from the built geometry (Blender world rest pose).
sv=[sword.matrix_world@v.co for v in sword.data.vertices];tip=max(sv,key=lambda p:(p-GRIP).dot(A))
bl=[p for p in sv if (p-GRIP).dot(A)>.6]
import numpy as np
P=np.array([list(p) for p in bl]);c0=P.mean(0);_,_,vt=np.linalg.svd(P-c0);ax=Vector(vt[0].tolist());ax=ax if ax.dot(A)>0 else -ax
X=np.array([list((Vector(p)-Vector(c0.tolist()))-ax*(Vector(p)-Vector(c0.tolist())).dot(ax)) for p in bl]);_,_,vt2=np.linalg.svd(X)
width=Vector(vt2[0].tolist());width=width if width.dot(WD)>0 else -width
bdir=(tip-GRIP).normalized()
measure={'gripCentre':[round(x,4) for x in GRIP],'tip':[round(x,4) for x in tip],'bladeDirection':[round(x,4) for x in bdir],'edgeAxis':[round(x,4) for x in width],
         'bladeForearmDegrees':round(math.degrees(bdir.angle(FORE)),2),'gripToTip':round((tip-GRIP).length,4),'wristToTip':round((tip-WR).length,4),
         'wristToTipAlongBlade':round((tip-WR).dot(bdir),4),'flatNormal':[round(x,4) for x in bdir.cross(width).normalized()],'backOfHand':[round(x,4) for x in FU]}
print('SWORD_MEASURE',json.dumps(measure),flush=True)
(out/'anatomy.json').write_text(json.dumps({'body':'fully rigid hard-surface armour; voxel-fused pieces, navy undersuit volumes overlapping every joint',
    'reference':'../../../art-references/frozen-knight-redesign/frozen-knight-turnaround-v1.png','status':'shape review before rigging',
    'scale':'0.0092 units per sheet pixel, floor at sheet row 764','handedness':'pipeline convention: Left at -X facing -Y (mirror of the sheet)',
    'sword':measure,'bones':spec},indent=2))
tris={o.name:(o.data.calc_loop_triangles(),len(o.data.loop_triangles))[1] for o in FINALS}
print('TRIANGLES',sum(tris.values()),json.dumps(tris),flush=True)
zs=[(o.matrix_world@v.co).z for o in FINALS for v in o.data.vertices];print('HEIGHT',round(min(zs),3),round(max(zs),3),flush=True)

# ---------------------------------------------------------------- review stage
# Comparison frames match the sheet (0.0092 units per pixel, floor at row 764).
# Lights and side/three-quarter cameras are the mirror of the sheet's so that
# the horizontally flipped strips (frozen_knight_compare.py) read like the sheet.
scene=bpy.context.scene;stage=bpy.data.collections.new('REVIEW_ONLY');scene.collection.children.link(stage)
def staged(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    stage.objects.link(o);return o
scene.world=bpy.data.worlds.new('Studio grey');scene.world.use_nodes=True
bg=scene.world.node_tree.nodes['Background'];bg.inputs[0].default_value=(*srgb((152,148,147)),1);bg.inputs[1].default_value=.30
scene.render.engine='CYCLES';scene.cycles.samples=12 if QUICK else 28;scene.cycles.use_denoising=True
scene.view_settings.view_transform='Standard';scene.render.image_settings.file_format='PNG'
center=Vector((0,0,3.1));lights=[]
for pos,power,size in [((4.5,-7,8.5),1080,7),((-7,-3,3.5),170,6),((-2,8,7),400,5)]:
    bpy.ops.object.light_add(type='AREA',location=pos);L=staged(bpy.context.object);L.data.energy=power;L.data.size=size;lights.append((L,Vector(pos)))
def aim(o,target):o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=staged(bpy.context.object);scene.camera=cam
def view(angle,distance=14,z=2.949):
    R=Matrix.Rotation(math.radians(angle),3,'Z')
    for L,p in lights:L.location=R@p;aim(L,center)
    cam.location=R@Vector((0,-distance,z));cam.rotation_euler=(R@Vector((0,1,0))).to_track_quat('-Z','Y').to_euler()
def closeup(label,target,direction,distance,lens=85,res=900):
    cam.data.type='PERSP';cam.data.lens=lens;scene.render.resolution_x=res;scene.render.resolution_y=res
    cam.location=Vector(target)+Vector(direction).normalized()*distance;aim(cam,target)
    scene.render.filepath=str(out/'review'/f'{label}.png');bpy.ops.render.render(write_still=True)
def compare():
    """Sheet-matched view strips; frozen_knight_compare.py flips them beside the reference."""
    review=out/'review';review.mkdir(exist_ok=True)
    scene.render.film_transparent=True;cam.data.type='ORTHO';cam.data.ortho_scale=887*.0092
    scene.render.resolution_x=560;scene.render.resolution_y=887;scene.render.resolution_percentage=100
    for angle,label in [(0,'Front'),(-90,'Side'),(180,'Back'),(-25,'ThreeQuarter')]:
        view(angle);scene.render.filepath=str(review/f'{label}.png');bpy.ops.render.render(write_still=True)
    scene.render.film_transparent=False
    view(30)
    closeup('HelmDetail',(0,-.15,5.55),(.45,-1,.18),5.2)
    closeup('GripOuter',GRIP+A*.15,(.78,-.50,-.22),3.0)
    keep={'Right gloved fist','Frost broadsword','Right vambrace','Right forearm suit'}
    for o in FINALS:o.hide_render=o.name not in keep
    closeup('GripInner',GRIP+A*.15,(-.85,-.40,-.30),3.0)
    for o in FINALS:o.hide_render=False
compare()
# Leave the hero three-quarter camera (sword side) for rig_export/animate_mobs renders.
cam.data.type='ORTHO';cam.data.ortho_scale=8.5;view(30,14,3.05);scene.render.resolution_x=900;scene.render.resolution_y=900
bpy.ops.mesh.primitive_plane_add(size=60,location=(0,0,-.005));floor=staged(bpy.context.object);floor.data.materials.append(mat('Stage floor',srgb((150,147,146)),0))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Sculpt.blend'))
print('BUILD_COMPLETE',flush=True)
