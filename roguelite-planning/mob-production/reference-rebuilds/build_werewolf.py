"""Werewolf reference rebuild (2026-10-01).

Source: ../../art-references/werewolf-redesign/werewolf-turnaround-v1.png and
werewolf-details-and-pose-v1.png (user-supplied). Faceted low-poly: one fused
fur skin (body, mane and every fur shard voxel-merged, then decimated), a
rigid head, fused hands/paws/tail and torn shorts. Colours are assigned per
face from the nearest source piece, so colour edges follow the tuft outlines.

Blender 5.2 background:  blender --background --python build_werewolf.py
QUICK=1 skips the cavity pass and renders the comparison at low samples.
Then: rig_export.py -- werewolf ; polish_rig.py -- werewolf ; verify_exports.py -- werewolf
"""
import sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
import bmesh

QUICK=os.environ.get('QUICK')=='1'
out=reset('werewolf')
REF=ROOT.parents[1]/'art-references'/'werewolf-redesign'
rng=random.Random(1031)

# Albedo eyedropped from the sheet (sRGB), lifted from the lit sample values.
COL={'fur':(128,127,143),'mane':(70,68,77),'bib':(180,176,182),'muzzle':(224,218,212),'inner':(178,174,184),
     'brow':(58,56,63),'claw':(44,43,49),'nose':(36,35,39),'eye':(244,160,30),'pupil':(16,12,10),
     'fang':(236,228,206),'mouth':(96,34,40),'shorts':(122,93,68),'belt':(88,66,49),'buckle':(64,49,38)}
def srgb(c):return tuple(((v/255+.055)/1.055)**2.4 for v in c)
MATS={}
def paint(key,variation=.07,scale=3.2):
    """Low-noise painted colour, darkened by the baked per-vertex Cavity attribute."""
    if key in MATS:return MATS[key]
    m=mat('Werewolf '+key,srgb(COL[key]),variation,scale,.82)
    n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');ramp=next(x for x in n if x.type=='VALTORGB')
    attr=n.new('ShaderNodeAttribute');attr.attribute_name='Cavity';attr.attribute_type='GEOMETRY'
    rangeN=n.new('ShaderNodeMapRange');rangeN.inputs['To Min'].default_value=.72;rangeN.inputs['To Max'].default_value=1
    mul=n.new('ShaderNodeVectorMath');mul.operation='MULTIPLY'
    l.new(attr.outputs['Fac'],rangeN.inputs['Value']);l.new(ramp.outputs[0],mul.inputs[0]);l.new(rangeN.outputs['Result'],mul.inputs[1])
    l.new(mul.outputs[0],p.inputs['Base Color'])
    MATS[key]=m;return m
for k in COL:paint(k)

def applied(o):
    active(o);bpy.ops.object.transform_apply(location=True,rotation=True,scale=True);return o
def flat(o):
    for p in o.data.polygons:p.use_smooth=False
def active(o):
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
def clean(o):
    """Collapse decimation fins. Where a thin shard tip pinched flat, decimation
    leaves two back-to-back faces on the same vertices. Blender's glTF exporter
    runs mesh.validate() on the source mesh, deletes those duplicates and opens
    pinholes in Model.blend. Merging each fin into one point keeps the tip closed."""
    bm=bmesh.new();bm.from_mesh(o.data)
    for _ in range(8):
        bm.verts.index_update();seen={};fins=[]
        for f in bm.faces:
            k=tuple(sorted(v.index for v in f.verts))
            if k in seen:fins.append(list(f.verts))
            else:seen[k]=f
        if not fins:break
        for vs in fins:
            vs=[v for v in vs if v.is_valid]
            if len(vs)>1:bmesh.ops.pointmerge(bm,verts=vs,merge_co=sum((v.co for v in vs),Vector())/len(vs))
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7)
    for _ in range(6):
        # Any remaining pinch (an edge on 1 or 3+ faces) collapses to a point.
        bad=[e for e in bm.edges if not e.is_manifold]
        if not bad:break
        for e in bad:
            if e.is_valid:bmesh.ops.pointmerge(bm,verts=list(e.verts),merge_co=(e.verts[0].co+e.verts[1].co)/2)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7)
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bm.to_mesh(o.data);bm.free();o.data.validate();flat(o);return o
def manifold_report(objects):
    bad={}
    for o in objects:
        bm=bmesh.new();bm.from_mesh(o.data);n=sum(not e.is_manifold for e in bm.edges);bm.free()
        before=len(o.data.polygons);o.data.validate();after=len(o.data.polygons)
        if n or before!=after:bad[o.name]=(n,before-after)
    return bad
def fuse_to(objects,name,key,voxel,triangles,smooth=2,factor=.5,symmetric=False):
    o=join(objects,name);o.data.remesh_voxel_size=voxel;active(o);bpy.ops.object.voxel_remesh()
    if smooth:
        mod=o.modifiers.new('Voxel step blend','SMOOTH');mod.factor=factor;mod.iterations=smooth;bpy.ops.object.modifier_apply(modifier=mod.name)
    o.data.calc_loop_triangles();count=len(o.data.loop_triangles)
    if count>triangles:
        mod=o.modifiers.new('Faceted topology','DECIMATE');mod.ratio=triangles/count
        if symmetric:mod.use_symmetry=True;mod.symmetry_axis='X'
        bpy.ops.object.modifier_apply(modifier=mod.name)
    finish(o,name,paint(key));clean(o);return o
def copy_of(objects,name):
    copies=[]
    for o in objects:
        c=o.copy();c.data=o.data.copy();bpy.context.collection.objects.link(c);copies.append(c)
    return join(copies,name)
def bvh_of(o):return BVHTree.FromObject(o,bpy.context.evaluated_depsgraph_get())

class Builder:
    """Accumulates many small closed solids into one mesh object."""
    def __init__(self):self.v=[];self.f=[]
    def add(self,verts,faces):
        k=len(self.v);self.v+=[tuple(p) for p in verts];self.f+=[tuple(i+k for i in face) for face in faces]
    def make(self,name,key):return mesh(name,self.v,self.f,paint(key))

def shard(b,root,normal,flow,L,W,T,lift=.32,bend=.26,sink=.07):
    """One soft fur clump: a thick rounded teardrop lying along the surface,
    rooted below it, tapering to a rounded tip that curls slightly away.
    (Thin diamond shards read as blades/scales and were rejected 2026-10-01.)"""
    T=max(T*1.9,.42*W);lift*=.6;bend*=.7
    n=Vector(normal).normalized();d=Vector(flow);d=d-n*d.dot(n)
    if d.length<1e-4:d=Vector((0,0,-1))-n*(-n.z)
    d.normalize();s=n.cross(d).normalized();base=Vector(root)-n*sink
    verts=[];faces=[];rings=[];m=6
    for t,wf,tf in [(0,.72,.75),(.24,1,1),(.52,.88,.86),(.76,.56,.56),(.92,.24,.26)]:
        c=base+d*(L*t)+n*(L*(lift*t+bend*t*t)+sink*min(1,t*3.2))
        tang=(d+n*(lift+2*bend*t)).normalized();up=tang.cross(s).normalized();i=len(verts)
        for k in range(m):
            a=k*math.tau/m;co=math.cos(a);si=math.sin(a)
            verts.append(c+s*co*W*.5*wf+up*si*T*tf*(.55 if si>0 else .3))
        rings.append(i)
    verts.append(base+d*L+n*(L*(lift+bend)+sink));tip=len(verts)-1
    for a,c in zip(rings,rings[1:]):
        for k in range(m):faces.append((a+k,a+(k+1)%m,c+(k+1)%m,c+k))
    last=rings[-1]
    for k in range(m):faces.append((last+k,last+(k+1)%m,tip))
    faces.append(tuple(rings[0]+k for k in range(m-1,-1,-1)))
    b.add(verts,faces)

def loft(name,levels,key,side=1,exponent=.85,shape=None,n=48):
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

def loft_y(name,levels,key,exponent=.72,n=32):
    """Snout/jaw sections along -Y: (y, cz, half-width, top height, bottom height)."""
    verts=[]
    for y,cz,hw,top,bottom in levels:
        for k in range(n):
            a=k*math.tau/n;co=math.cos(a);si=math.sin(a)
            verts.append((hw*math.copysign(abs(co)**exponent,co),y,cz+(top if si>=0 else bottom)*math.copysign(abs(si)**exponent,si)))
    m=len(levels);faces=[tuple(range(n))]+[(j*n+(k+1)%n,j*n+k,(j+1)*n+k,(j+1)*n+(k+1)%n) for j in range(m-1) for k in range(n)]+[tuple(range(m*n-1,(m-1)*n-1,-1))]
    return mesh(name,verts,faces,paint(key))

def bar(name,a,b,height,depth,key,forward=Vector((0,-1,0)),bevel=.025):
    a=Vector(a);b=Vector(b);ax=(b-a).normalized();fw=(forward-ax*forward.dot(ax)).normalized();up=ax.cross(fw).normalized()
    if up.z<0:up=-up
    vs=[];f=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
    for p in (a,b):
        for su in (-1,1):
            for sf in (-1,1):vs.append(p+up*su*height/2+fw*sf*depth/2)
    o=mesh(name,[vs[0],vs[1],vs[2],vs[3],vs[4],vs[5],vs[6],vs[7]],f,paint(key))
    if bevel:
        active(o);mod=o.modifiers.new('Chamfer','BEVEL');mod.width=bevel;mod.segments=1;bpy.ops.object.modifier_apply(modifier=mod.name)
    return o

def orient(o,center,forward,scale_xyz):
    """Place a unit sphere-built object: local -Y to `forward`, local Z up-ish."""
    f=Vector(forward).normalized();up=Vector((0,0,1));x=(-f).cross(up).normalized();z=x.cross(-f).normalized()
    R=Matrix((x,-f,z)).transposed()
    for v in o.data.vertices:
        p=Vector((v.co.x*scale_xyz[0],v.co.y*scale_xyz[1],v.co.z*scale_xyz[2]));v.co=Vector(center)+R@p
    return o

def cut_tag(o,cutter,key):
    """Boolean difference whose new faces carry `key`'s material."""
    cutter.data.materials.clear();cutter.data.materials.append(paint(key))
    active(o);mod=o.modifiers.new('Carve','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter;mod.material_mode='TRANSFER'
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True);clean(o)

def set_materials(o,keys):
    o.data.materials.clear()
    for k in keys:o.data.materials.append(paint(k))
    return {k:i for i,k in enumerate(keys)}

# ---------------------------------------------------------------- body skin
def torso_shape(x,y,z,co,si):
    ax=abs(x);front=max(0,-si)**3;rear=max(0,si)**3
    pec=.17*math.exp(-((ax-.55)/.42)**2-((z-4.55)/.33)**2)
    abdomen=sum(.035*math.exp(-((ax-.17)/.13)**2-((z-zz)/.11)**2) for zz in (3.62,3.86,4.08))
    y-=front*(pec+abdomen+.03*math.exp(-(x/.35)**2-((z-3.78)/.25)**2))
    y+=rear*(.15*math.exp(-((ax-.95)/.36)**2-((z-4.45)/.45)**2)+.11*math.exp(-((ax-.55)/.36)**2-((z-5.12)/.22)**2))
    y-=rear*.05*math.exp(-(x/.13)**2)
    return x,y
TORSO=[(2.56,0,.04,.86,.56,.60),(2.70,0,.05,.96,.60,.68),(3.05,0,.04,.90,.62,.66),(3.40,0,.02,.84,.66,.66),
       (3.80,0,0,.92,.74,.66),(4.20,0,-.03,1.10,.80,.72),(4.60,0,-.05,1.26,.82,.80),(4.95,0,-.06,1.30,.74,.86),
       (5.20,0,-.10,1.06,.60,.82),(5.45,0,-.18,.66,.48,.62),(5.70,0,-.28,.42,.38,.42)]
# Limb sections are slimmer than the sheet outline: the fur coat adds the rest.
ARM=[(2.60,1.88,-.08,.31,.31,.31),(2.82,1.86,-.07,.35,.36,.35),(3.10,1.80,-.04,.45,.47,.44),(3.45,1.72,0,.47,.49,.48),
     (3.78,1.62,.03,.39,.42,.44),(4.10,1.55,0,.39,.48,.44),(4.45,1.48,-.02,.44,.53,.48),(4.80,1.42,-.03,.49,.54,.53),
     (5.05,1.32,-.04,.50,.52,.54),(5.22,1.12,-.05,.38,.40,.46)]
LEG=[(.50,.86,.15,.28,.28,.28),(.74,.85,.12,.31,.30,.32),(1.02,.84,.06,.35,.34,.43),(1.32,.82,-.02,.40,.40,.49),
     (1.62,.78,-.06,.39,.44,.44),(1.95,.70,-.02,.34,.40,.43),(2.30,.64,.02,.40,.46,.50),(2.65,.58,.04,.44,.50,.54),(3.00,.50,.04,.44,.50,.54)]
def axis_at(levels,z):
    for a,b in zip(levels,levels[1:]):
        if a[0]<=z<=b[0]:
            t=(z-a[0])/(b[0]-a[0]);return a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t
    e=levels[0] if z<levels[0][0] else levels[-1];return e[1],e[2]
base=[loft('Torso',TORSO,'fur',shape=torso_shape,n=56)]
for s in [-1,1]:
    base.append(loft('Arm',ARM,'fur',side=s));base.append(loft('Leg',LEG,'fur',side=s))
mane_base=[ell('Mane mass',(0,-.12,5.62),(.78,.62,.72),paint('mane'),32,20),ell('Back mane hump',(0,.36,4.95),(1.04,.55,.78),paint('mane'),32,20)]
probe=copy_of(base+mane_base,'PROBE');bv=bvh_of(probe)
def hit(origin,direction):
    loc,nor,i,d=bv.ray_cast(Vector(origin),Vector(direction).normalized(),30)
    return (loc,nor) if loc is not None else (None,None)

fur=Builder();mane=Builder();bib=Builder()
def pair(fn):
    """Generate one random variation and apply it on both sides (mirror-exact)."""
    r={'l':rng.uniform(-1,1),'w':rng.uniform(-1,1),'t':rng.uniform(-1,1)}
    for s in [-1,1]:fn(s,r)
def placed(b,origin,direction,flow,L,W,T,lift=.2,bend=.16,need=None):
    p,nrm=hit(origin,direction)
    if p is None or (need and not need(p)):return
    shard(b,p,nrm,flow,L,W,T,lift,bend)
def coat(levels,zs,count,L,W,T,lift=.10,bend=.13,spread=.12,skip=None):
    """Sparse rings of big, flat-lying fur clumps on a limb, jittered so no rows read."""
    for j,z0 in enumerate(zs):
        for k in range(count):
            a=(k+.5*(j%2))*math.tau/count+rng.uniform(-.28,.28);z=z0+rng.uniform(-.07,.07);cx,cy=axis_at(levels,z)
            if skip and skip(z,a):continue
            r=rng.uniform(-1,1)
            for s in [-1,1]:
                rad=Vector((s*math.cos(a),math.sin(a),0));c=Vector((s*cx,cy,z));p,nrm=hit(c+rad*.9,-rad)
                if p is None or nrm.dot(rad)<.2 or (p.xy-c.xy).length>.7:continue
                shard(fur,p,nrm,Vector((0,0,-1))+rad*spread,L*(1+.18*r),W*(1+.14*r),T,lift,bend,.05)

# Back mane: inverted shield of overlapping dark shards from the crown to mid-back.
for j,(z,hw) in enumerate([(6.18,.50),(5.97,.72),(5.75,.92),(5.52,1.08),(5.30,1.18),(5.08,1.22),(4.86,1.10),(4.64,.93),(4.42,.74),(4.20,.52),(3.98,.30)]):
    step=.30;offset=0 if j%2 else step/2
    for x in [x for x in [offset+k*step for k in range(8)] if x<=hw+.01]:
        L=.52+.10*min(1,(z-4)/1.6);r=rng.uniform(-1,1)
        for s in ([1] if x<.01 else [-1,1]):
            placed(mane,(s*x,5,z),(0,-1,0),(s*x*.25,.38,-1),L*(1+.08*r),.40,.14,.24,.20)
# Face ruff: big dark shards flaring out and back from behind the ears to the shoulders.
for z in [6.22,6.02,5.82,5.62,5.42,5.22]:
    for y in [-.62,-.40,-.16,.10]:
        big=1.12 if 5.5<z<6.1 else .9
        pair(lambda s,r,z=z,y=y,big=big:placed(mane,(s*5,y,z),(-s,0,0),(s*.78,.32,-.48),(.62+.05*r['l'])*big,.46,.16,.20,.16,need=lambda p:abs(p.x)<1.1))
# Dark collar wrapping the top corners of the bib and the throat.
for z in [5.18,4.98]:
    for x in [.62,.86,1.08]:
        pair(lambda s,r,z=z,x=x:placed(mane,(s*x,-4,z),(0,1,0),(s*.35,-.3,-1),.50,.44,.14,.16,.14,need=lambda p:p.z>4.8))
for z in [5.12,5.32]:
    for x in [0,.25,.50]:
        for s in ([1] if x<.01 else [-1,1]):
            placed(mane,(s*x,-4,z),(0,1,0),(s*x*.4,-.25,-1),.46,.42,.13,.18,.14)
for y in [-.22,.06,.34]:
    for x in [0,.24]:
        for s in ([1] if x<.01 else [-1,1]):
            placed(mane,(s*x,y,9),(0,0,-1),(s*x*.5,1,-.2),.50,.40,.14,.36,.15)
# Chest bib: broad pale clumps lying flat in a V, rows overlapping downward.
for j,z in enumerate([5.00,4.74,4.48,4.22,3.96,3.72]):
    hw=1.0*(z-3.45)/1.55;step=.34;offset=0 if j%2==0 or hw<.2 else step/2
    for x in [x for x in [offset+k*step for k in range(5)] if x<=hw+.02]:
        for s in ([1] if x<.01 else [-1,1]):
            placed(bib,(s*x,-4,z),(0,1,0),(s*x*.15,-.2,-1),.60-.04*(5.0-z),.54,.10,.08,.10)
# Grey coat on the limbs, then longer silhouette tufts at deltoid, elbow, forearm, cuffs and calves.
# Limbs stay smooth muscle; soft tufts only where the sheet breaks the silhouette.
for z in [4.30,4.04]:
    for y in [.05,.32]:
        pair(lambda s,r,z=z,y=y:placed(fur,(s*5,y,z),(-s,0,0),(s*.4,.3,-1),.40,.42,.13,.16,.14))
for z in [1.74,1.56]:
    for o in [-.15,.15]:
        pair(lambda s,r,z=z,o=o:placed(fur,(s*(.78+o),-4,z),(0,1,0),(s*.2,-.18,-1),.38,.40,.12,.14,.12))
for z in [1.30,1.04]:
    pair(lambda s,r,z=z:placed(fur,(s*5,.15,z),(-s,0,0),(s*.45,.2,-1),.40,.40,.12,.16,.14))
for z in [5.10,4.85]:
    for y in [-.25,.05,.32]:
        pair(lambda s,r,z=z,y=y:placed(fur,(s*5,y,z),(-s,0,0),(s*.6,.05*y,-1),.42+.04*r['l'],.42,.14,.20,.16))
for y in [-.20,.20]:
    pair(lambda s,r,y=y:placed(fur,(s*1.42,y,9),(0,0,-1),(s*.6,y*.3,-1),.38,.40,.13,.12,.12))
for z in [3.86,3.66]:
    for o in [-.15,.15]:
        pair(lambda s,r,z=z,o=o:placed(fur,(s*(1.64+o),5,z),(0,-1,0),(s*.35,.7,-.75),.48,.46,.14,.22,.18))
for z in [3.42,3.12]:
    for y in [-.20,.15]:
        pair(lambda s,r,z=z,y=y:placed(fur,(s*5,y,z),(-s,0,0),(s*.5,.12,-1),.52+.04*r['l'],.48,.14,.20,.16))
def cuff(axis,z,count,L,W):
    for k in range(count):
        a=(k+.5)*math.tau/count
        for s in [-1,1]:
            c=Vector((s*axis[0],axis[1],z));r=Vector((s*math.cos(a),math.sin(a),0))
            placed(fur,c+r*.85,-r,Vector((0,0,-1))+r*.35,L,W,.12,.18,.14)
cuff((1.88,-.08),2.72,8,.34,.32)
cuff((.86,.14),.64,8,.34,.32)
for z in [1.28,1.02]:
    for o in [-.14,.14]:
        pair(lambda s,r,z=z,o=o:placed(fur,(s*(.82+o),4,z),(0,-1,0),(s*.15,.45,-1),.40,.36,.12,.20,.16))
for z in [3.74,3.52]:
    for x in [.22,.55]:
        pair(lambda s,r,x=x,z=z:placed(fur,(s*x,4,z),(0,-1,0),(s*.3,.4,-1),.32,.34,.11,.14,.12))

tufts={'fur':fur.make('Grey shards','fur'),'mane':mane.make('Mane shards','mane'),'bib':bib.make('Bib shards','bib')}
groups={'furbase':copy_of(base,'SRC_furbase'),'furtuft':copy_of([tufts['fur']],'SRC_furtuft'),
        'mane':copy_of(mane_base+[tufts['mane']],'SRC_mane'),'bib':copy_of([tufts['bib']],'SRC_bib')}
skin=fuse_to(base+mane_base+list(tufts.values()),'Werewolf fur skin','fur',.026 if QUICK else .022,13500,4,.55)
slot=set_materials(skin,['fur','mane','bib']);trees={k:bvh_of(o) for k,o in groups.items()}
def mane_zone(c,n):
    ax=abs(c.x)
    if c.z>5.28 and ax<1.05:return True
    if n.y>.05 and c.y>-.1 and 3.85<c.z:return ax<1.25*min(1,(c.z-3.85)/1.2)
    return False
def bib_zone(c,n):return n.y<-.15 and c.y<0 and 3.45<c.z<5.1 and abs(c.x)<1.0*(c.z-3.45)/1.55
for p in skin.data.polygons:
    c=p.center;d={k:t.find_nearest(c)[3] for k,t in trees.items()};k=min(d,key=d.get)
    if k=='furbase':k='mane' if mane_zone(c,p.normal) else 'bib' if bib_zone(c,p.normal) else 'fur'
    elif k=='furtuft':k='fur'
    p.material_index=slot[k]
# ManeMask lets polish_rig keep the face ruff on Chest/Head instead of the arms.
mask=[0.0]*len(skin.data.vertices)
for p in skin.data.polygons:
    if p.material_index==slot['mane']:
        for i in p.vertices:mask[i]=1.0
skin.data.attributes.new('ManeMask','FLOAT','POINT').data.foreach_set('value',mask)
for o in groups.values():bpy.data.objects.remove(o,do_unlink=True)
bpy.data.objects.remove(probe,do_unlink=True)
skin['smooth_skin']=True
print('SKIN',len(skin.data.polygons),flush=True)

# ---------------------------------------------------------------- head
# Angular planes: chamfered cranium block, brow shelf, tapered box snout.
cran=applied(ell('Cranium',(0,-.52,6.0),(.55,.50,.43),paint('fur'),14,9))
for v in cran.data.vertices:
    if v.co.y<-.86:v.co.y=-.86+(v.co.y+.86)*.45
    if v.co.z>6.28:v.co.z=6.28+(v.co.z-6.28)*.55
hp=[cran,ell('Brow ridge',(0,-.86,5.94),(.42,.13,.09),paint('fur'),14,8)]
hp.append(loft_y('Snout',[(-.84,5.57,.37,.27,.30),(-1.16,5.53,.32,.22,.25),(-1.46,5.52,.26,.18,.20),(-1.68,5.54,.19,.13,.14)],'fur',.6,16))
hp.append(loft_y('Lower jaw',[(-.76,5.29,.34,.11,.14),(-1.10,5.26,.29,.10,.13),(-1.40,5.26,.20,.08,.10)],'fur',.6,16))
for s in [-1,1]:
    hp.append(ell('Jowl',(s*.19,-1.32,5.38),(.17,.30,.11),paint('fur'),16,10))
    hp.append(ell('Cheek',(s*.38,-.80,5.62),(.24,.28,.26),paint('fur'),16,10))
    # Triangular ear: flat front face, ridged back, one sharp tip, tilted outward.
    B=Vector((s*.38,-.48,6.16));T=Vector((s*.63,-.54,7.0));ac=Vector((1,0,.22*s)).normalized()*s
    def ring(c,sc):return [c+ac*(-.25*sc)+Vector((0,-.12*sc,0)),c+ac*(.25*sc)+Vector((0,-.12*sc,0)),c+Vector((0,.17*sc,0))]
    verts=ring(B,1)+ring(B.lerp(T,.45),.66)+[T]
    faces=[(2,1,0),(0,1,4,3),(1,2,5,4),(2,0,3,5),(3,4,6),(4,5,6),(5,3,6)]
    hp.append(mesh('Ear',verts,faces,paint('fur')))
cheek=Builder()
for s in [-1,1]:
    for root,flow,L in [((.52,-.76,5.58),(.85,.35,-.35),.42),((.50,-.68,5.40),(.7,.35,-.7),.40),((.54,-.62,5.76),(.8,.4,0),.36),((.44,-.86,5.30),(.5,.2,-.9),.34)]:
        shard(cheek,Vector((s*root[0],root[1],root[2])),Vector((s,-.3,0)),Vector((s*flow[0],flow[1],flow[2])),L,.32,.13,.15,.12)
    for root in [(.18,-.80,6.30),(.34,-.60,6.32)]:
        shard(cheek,Vector((s*root[0],root[1],root[2])),Vector((0,-.3,1)),Vector((s*.12,1,.12)),.34,.30,.11,.25,.12)
shard(cheek,Vector((0,-.62,6.38)),Vector((0,-.2,1)),Vector((0,1,.1)),.36,.32,.12,.25,.12)
hp.append(cheek.make('Cheek shards','fur'))
muzzle_src=copy_of([o for o in hp if o.name.split('.')[0] in ('Snout','Lower jaw','Jowl','Cheek')],'SRC_muzzle')
fur_src=copy_of([o for o in hp if o.name.split('.')[0] not in ('Snout','Lower jaw','Jowl','Cheek')],'SRC_headfur')
head=fuse_to(hp,'Werewolf head','fur',.016 if QUICK else .013,2000,2,.45)
slot=set_materials(head,['fur','muzzle','inner']);mt=bvh_of(muzzle_src);ft=bvh_of(fur_src)
def muzzle_line(y):
    pts=[(-1.90,5.50),(-1.45,5.52),(-1.15,5.60),(-.96,5.66),(-.82,5.50),(-.66,5.26)]
    for (y0,z0),(y1,z1) in zip(pts,pts[1:]):
        if y0<=y<=y1:return z0+(z1-z0)*(y-y0)/(y1-y0)
    return 5.0
def inner_ear(c,n):
    """Front-facing ear faces inside an inset triangle, leaving a grey rim."""
    if n.y>-.45 or c.z<6.28:return False
    s=1 if c.x>0 else -1;a=Vector((s*.14,6.11));b=Vector((s*.62,6.21));t=Vector((s*.63,7.0));q=Vector((c.x,c.z));cen=(a+b+t)/3
    a,b,t=[cen+(v-cen)*.72 for v in (a,b,t)]
    def side(p1,p2):return (p2.x-p1.x)*(q.y-p1.y)-(p2.y-p1.y)*(q.x-p1.x)
    d1,d2,d3=side(a,b),side(b,t),side(t,a);return not((d1<0 or d2<0 or d3<0) and (d1>0 or d2>0 or d3>0))
for p in head.data.polygons:
    c=p.center
    if inner_ear(c,p.normal):p.material_index=slot['inner'];continue
    near_muzzle=mt.find_nearest(c)[3]<ft.find_nearest(c)[3]
    p.material_index=slot['muzzle'] if near_muzzle and c.y<-.66 and c.z<muzzle_line(c.y) else slot['fur']
for o in (muzzle_src,fur_src):bpy.data.objects.remove(o,do_unlink=True)
mouth=[(-.38,-.96,5.29),(-.34,-1.14,5.30),(-.28,-1.36,5.315),(-.15,-1.52,5.32),(0,-1.57,5.32)]
cut_tag(head,tube('Mouth line',mouth+[(-x,y,z) for x,y,z in reversed(mouth[:-1])],(.042,.03),None,6),'mouth')
hb=bvh_of(head)
def head_hit(x,z):
    loc,nor,i,d=hb.ray_cast(Vector((x,-5,z)),Vector((0,1,0)),10);return loc,nor
def almond(name,center,forward,w,h,depth,roll,key,dome=.5):
    """Pointed-corner eye lens in the face plane, rolled so the inner corner dips."""
    f=Vector(forward).normalized();X=(-f).cross(Vector((0,0,1))).normalized();Z=X.cross(-f).normalized()
    ring=[];n=14;cr=math.cos(roll);sr=math.sin(roll)
    for k in range(n):
        a=k*math.tau/n;u=w*math.copysign(abs(math.cos(a))**1.5,math.cos(a));v=h*math.sin(a)
        ring.append((u*cr-v*sr,u*sr+v*cr))
    verts=[Vector(center)+X*u+Z*v+f*depth*.5 for u,v in ring]+[Vector(center)+X*u+Z*v-f*depth*.5 for u,v in ring]+[Vector(center)+f*depth*(.5+dome)]
    faces=[(k,(k+1)%n,n+(k+1)%n,n+k) for k in range(n)]+[(k,2*n,(k+1)%n) for k in range(n)]+[tuple(range(2*n-1,n-1,-1))]
    return mesh(name,verts,faces,paint(key))
feature=[]
for s in [-1,1]:
    p,nrm=head_hit(s*.30,5.78);f=(nrm.normalized()+Vector((s*.3,-1,0)).normalized()).normalized();roll=s*math.radians(15)
    feature.append(almond('Eye rim',p+f*.002,f,.150,.088,.03,roll,'brow',.2))
    feature.append(almond('Amber eye',p+f*.016,f,.122,.068,.026,roll,'eye',.4))
    feature.append(almond('Pupil',p+f*.032+Vector((-s*.012,0,-.004)),f,.036,.058,.014,0,'pupil',.3))
    a,_=head_hit(s*.09,5.86);b,_=head_hit(s*.47,6.03)
    feature.append(bar('Heavy brow',a+Vector((0,-.05,.01)),b+Vector((s*.04,-.045,.01)),.17,.23,'brow',bevel=.04))
    fang=[(s*.27,-1.46,5.40),(s*.285,-1.53,5.27),(s*.27,-1.52,5.12)]
    feature.append(tube('Upper fang',fang,[(.085,.07),(.06,.05),(.008,.008)],paint('fang'),6))
p,nrm=head_hit(0,5.62)
c=p+Vector((0,-.02,.03));nose=applied(ell('Nose',c,(.20,.14,.115),paint('nose'),12,8))
for v in nose.data.vertices:
    if v.co.z>c.z:v.co.z=c.z+(v.co.z-c.z)*.7
    else:v.co.x=c.x+(v.co.x-c.x)*(1-.35*(c.z-v.co.z)/.115)
feature.append(nose)
for o in [head]+feature:rigid(o,'Head');flat(o)

# ---------------------------------------------------------------- hands, paws, tail
def hand(s,side):
    parts=[applied(cube('Palm',(s*1.89,-.10,2.34),(.42,.70,.58),paint('fur'),.10))]
    for v in parts[0].data.vertices:
        t=(2.63-v.co.z)/.58;v.co.y=-.10+(v.co.y+.10)*(.86+.24*t)
    claws=[]
    def claw(tip,d):
        inw=Vector((-s,0,0));base=tip-d*.04
        claws.append(rigid(tube('Hand claw',[base,base+d*.14+inw*.02,base+d*.29+inw*.10],[(.08,.066),(.055,.046),(.006,.006)],paint('claw'),6),side+'Hand'))
    for y,L in [(-.24,.36),(-.08,.40),(.08,.38),(.23,.32)]:
        k=Vector((s*1.91,y-.10,2.12));q=L/.38
        pts=[k+Vector((0,0,.06)),k+Vector((-s*.02,0,-.15*q)),k+Vector((-s*.07,0,-.28*q)),k+Vector((-s*.13,0,-.37*q))]
        parts.append(tube('Finger',pts,[.14,.13,.115,.095],paint('fur'),10));claw(pts[-1],(pts[-1]-pts[-2]).normalized())
    th=[Vector((s*1.80,-.37,2.42)),Vector((s*1.74,-.46,2.28)),Vector((s*1.70,-.50,2.13))]
    parts.append(tube('Thumb',th,[.145,.13,.11],paint('fur'),10));claw(th[-1],(th[-1]-th[-2]).normalized())
    o=fuse_to(parts,side+' clawed hand','fur',.016 if QUICK else .012,1300,2,.45,False)
    return [rigid(o,side+'Hand')]+claws
def paw(s,side):
    A=Vector((s*.87,.14,.50));parts=[ell('Ankle',A+Vector((0,-.02,-.06)),(.30,.30,.27),paint('fur'))]
    parts+=[cube('Paw',(s*.90,-.24,.25),(.94,.88,.50),paint('fur'),.15),ell('Heel',(s*.88,.22,.22),(.30,.28,.22),paint('fur'))];claws=[]
    for o in [-.31,-.105,.105,.31]:
        c=Vector((s*.90+o,-.72+.06*abs(o)/.31,.19));parts.append(ell('Toe',c,(.165,.22,.19),paint('fur')))
        b=c+Vector((0,-.17,.06));claws.append(tube('Toe claw',[b,b+Vector((0,-.14,-.02)),b+Vector((0,-.25,-.15))],[(.072,.06),(.05,.044),(.006,.006)],paint('claw'),6))
    R=Matrix.Translation(A)@Matrix.Rotation(math.radians(s*8),4,'Z')@Matrix.Translation(-A)
    for o in parts+claws:
        o.matrix_world=R@o.matrix_world;applied(o)
    foot=fuse_to(parts,side+' paw','fur',.018 if QUICK else .014,950,2,.45,False)
    return [rigid(foot,side+'Foot')]+[rigid(c,side+'Foot') for c in claws]
limbs=[]
for s,side in [(-1,'Left'),(1,'Right')]:limbs+=hand(s,side)+paw(s,side)
P=[Vector(p) for p in [(0,.60,2.88),(0,.88,2.66),(0,1.10,2.36),(0,1.24,2.04),(0,1.29,1.72)]];TR=[.18,.30,.34,.28,.12]
tail_parts=[tube('Tail core',P,TR,paint('fur'),12)];tb=Builder()
for i in range(1,len(P)):
    t=.5;c=P[i-1].lerp(P[i],t);tan=(P[i]-P[i-1]).normalized();u=Vector((1,0,0));w=tan.cross(u);rad=TR[i-1]*(1-t)+TR[i]*t
    for a in ([90,162,234,306,18] if i%2 else [54,126,198,270,342]):
        r=u*math.cos(math.radians(a))+w*math.sin(math.radians(a))
        shard(tb,c+r*rad*.8,r,tan,.58,.52,.13,.14,.10)
for a in [0,120,240]:
    r=Vector((math.cos(math.radians(a)),0,math.sin(math.radians(a))));shard(tb,P[-1]+Vector((0,-.02,.06))+r*.05,r+Vector((0,.2,-1)),Vector((0,.2,-1)),.36,.32,.12,.12,.08)
tail_parts.append(tb.make('Tail shards','fur'))
tail=rigid(fuse_to(tail_parts,'Bushy tail','fur',.016 if QUICK else .013,1300,4,.55),'Tail')

# ---------------------------------------------------------------- torn shorts and belt
seat=loft('Shorts seat',[(2.54,0,.04,.92,.60,.66),(2.72,0,.05,1.06,.66,.76),(3.02,0,.04,1.00,.68,.76),(3.40,0,.02,.91,.72,.72)],'shorts',exponent=.8)
cloth=[seat];left=[]
for s in [-1,1]:
    n=28;verts=[];rings=[(2.70,.58,.04,.46,.52),(2.45,.66,.03,.45,.53),(2.20,.71,.01,.44,.51),(2.02,.74,0,.44,.50),None]
    if s<0:
        for k in range(n):
            down=(k%2==0);mag=rng.uniform(.10,.20) if down else rng.uniform(0,.05)
            if down and rng.random()<.18:mag+=.12
            left.append(mag if down else -mag)
        teeth=left
    else:teeth=[left[(n//2-k)%n] for k in range(n)]
    for ring in rings:
        for k in range(n):
            a=k*math.tau/n;co=math.cos(a);si=math.sin(a)
            if ring is None:z,cx,cy,rx,ry=1.90-teeth[k]+.03*math.sin(a*3),.75,0,.45,.51
            else:z,cx,cy,rx,ry=ring
            verts.append((s*cx+rx*co,cy+ry*si,z))
    faces=[(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(len(rings)-1) for k in range(n)]
    leg=mesh('Shorts leg',verts,faces,paint('shorts'));active(leg)
    mod=leg.modifiers.new('Cloth thickness','SOLIDIFY');mod.thickness=.06;mod.offset=1;bpy.ops.object.modifier_apply(modifier=mod.name)
    # Rips are cut through the simple shell before the voxel merge (robust boolean).
    c,size,through=(((-.56,-.55,2.16),(.17,.6,.12),'y') if s<0 else ((1.10,-.10,2.10),(.6,.15,.11),'x'))
    k=applied(cube('Tear',c,size,None,0))
    for v in k.data.vertices:
        if v.co.z>c[2]:
            if through=='y':v.co.x=c[0]+(v.co.x-c[0])*.15
            else:v.co.y=c[1]+(v.co.y-c[1])*.15
    cut(leg,k);cloth.append(leg)
shorts=fuse_to(cloth,'Torn shorts','shorts',.014 if QUICK else .011,2200,1,.4)
def band(name,z0,z1,rx,front,back,thick,key,n=56):
    verts=[]
    for z,grow in [(z0,0),(z1,0),(z1,thick),(z0,thick)]:
        for k in range(n):
            a=k*math.tau/n;co=math.cos(a);si=math.sin(a)
            verts.append(((rx+grow)*math.copysign(abs(co)**.82,co),.02+((back if si>=0 else front)+grow)*math.copysign(abs(si)**.82,si),z))
    faces=[(r*n+k,r*n+(k+1)%n,((r+1)%4)*n+(k+1)%n,((r+1)%4)*n+k) for r in range(4) for k in range(n)]
    return mesh(name,verts,faces,paint(key))
belt=band('Belt',3.29,3.47,.93,.77,.76,.065,'belt');buckle=cube('Belt loop',(0,-.835,3.38),(.30,.07,.25),paint('buckle'),.02)
shorts=join([shorts,belt,buckle],'Torn shorts');flat(shorts)
print('SHORTS',len(shorts.data.polygons),flush=True)

# ---------------------------------------------------------------- cavity, anatomy, review
finals=[skin,head,shorts,tail]+feature+limbs
bad=manifold_report(finals)
if bad and not QUICK:raise RuntimeError('Non-manifold or degenerate meshes: '+json.dumps(bad))
if bad:print('WARNING non-manifold',json.dumps(bad),flush=True)
def cavity(objects,rays=40,reach=.36):
    bm=bmesh.new()
    for o in objects:bm.from_mesh(o.data)
    tree=BVHTree.FromBMesh(bm);bm.free();g=math.pi*(3-math.sqrt(5));dirs=[]
    for i in range(rays):
        z=1-(i+.5)/rays;r=math.sqrt(1-z*z);dirs.append(Vector((r*math.cos(g*i),r*math.sin(g*i),math.sqrt(z))))
    for o in objects:
        me=o.data;vals=[]
        for v in me.vertices:
            n=v.normal.normalized();t=n.orthogonal().normalized();b=n.cross(t);origin=v.co+n*.012;occ=0
            for d in dirs:
                loc,_,_,dist=tree.ray_cast(origin,t*d.x+b*d.y+n*d.z,reach)
                if loc is not None:occ+=1-dist/reach*.5
            vals.append(max(0,1-occ/rays*1.25))
        attr=me.attributes.get('Cavity') or me.attributes.new('Cavity','FLOAT','POINT');attr.data.foreach_set('value',vals)
if QUICK:
    for o in finals:
        a=o.data.attributes.new('Cavity','FLOAT','POINT');a.data.foreach_set('value',[1]*len(o.data.vertices))
else:cavity(finals)
spec={'Pelvis':[[0,.04,2.62],[0,.02,3.42],None],'Chest':[[0,.02,3.42],[0,-.22,5.28],'Pelvis'],'Head':[[0,-.22,5.28],[0,-.55,6.45],'Chest'],
      'Tail':[[0,.70,2.80],[0,1.25,1.85],'Pelvis']}
for side,s in [('Left',-1),('Right',1)]:
    spec.update({side+'UpperArm':[[s*1.42,-.03,4.88],[s*1.62,.03,3.74],'Chest'],side+'Forearm':[[s*1.62,.03,3.74],[s*1.88,-.08,2.62],side+'UpperArm'],
                 side+'Hand':[[s*1.88,-.08,2.62],[s*1.90,-.13,1.82],side+'Forearm'],side+'Thigh':[[s*.56,.04,2.65],[s*.78,-.06,1.60],'Pelvis'],
                 side+'Shin':[[s*.78,-.06,1.60],[s*.86,.14,.52],side+'Thigh'],side+'Foot':[[s*.86,.14,.52],[s*.92,-.75,.18],side+'Shin']})
(out/'anatomy.json').write_text(json.dumps({'body':'fused faceted fur skin with voxel-merged mane, bib and fur shards','reference':'../../../art-references/werewolf-redesign/werewolf-turnaround-v1.png','status':'shape review before rigging','bones':spec},indent=2))
tris={o.name:(o.data.calc_loop_triangles(),len(o.data.loop_triangles))[1] for o in finals}
print('TRIANGLES',sum(tris.values()),json.dumps(tris),flush=True)

# Review stage: the comparison frames match the sheet (0.01 units per pixel, ground at y=770).
scene=bpy.context.scene;stage=bpy.data.collections.new('REVIEW_ONLY');scene.collection.children.link(stage)
def staged(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    stage.objects.link(o);return o
scene.world=bpy.data.worlds.new('Studio grey');scene.world.use_nodes=True
bg=scene.world.node_tree.nodes['Background'];bg.inputs[0].default_value=(*srgb((160,157,156)),1);bg.inputs[1].default_value=.55
scene.render.engine='CYCLES';scene.cycles.samples=12 if QUICK else 28;scene.cycles.use_denoising=True
scene.view_settings.view_transform='Standard';scene.render.image_settings.file_format='PNG'
center=Vector((0,0,3.3));lights=[]
for pos,power,size in [((-4.5,-7,8.5),1100,7),((7,-3,3.5),320,6),((2,8,7),520,5)]:
    bpy.ops.object.light_add(type='AREA',location=pos);L=staged(bpy.context.object);L.data.energy=power;L.data.size=size;lights.append((L,Vector(pos)))
def aim(o,target):o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add();cam=staged(bpy.context.object);scene.camera=cam
def view(angle,distance=14):
    R=Matrix.Rotation(math.radians(angle),3,'Z')
    for L,p in lights:L.location=R@p;aim(L,center)
    cam.location=R@Vector((0,-distance,3.265));cam.rotation_euler=(R@Vector((0,1,0))).to_track_quat('-Z','Y').to_euler()
def compare():
    """Sheet-matched view strips; werewolf_compare.py composes them beside the reference."""
    review=out/'review';review.mkdir(exist_ok=True)
    scene.render.film_transparent=True;cam.data.type='ORTHO';cam.data.ortho_scale=8.87
    scene.render.resolution_x=560;scene.render.resolution_y=887;scene.render.resolution_percentage=100
    for angle,label in [(0,'Front'),(90,'Side'),(180,'Back'),(25,'ThreeQuarter')]:
        view(angle);scene.render.filepath=str(review/f'{label}.png');bpy.ops.render.render(write_still=True)
    scene.render.film_transparent=False
    cam.data.type='PERSP';cam.data.lens=85;scene.render.resolution_x=900;scene.render.resolution_y=900
    R=Matrix.Rotation(math.radians(28),3,'Z');head_c=Vector((0,-.9,5.9))
    for L,p in lights:L.location=R@p;aim(L,center)
    cam.location=head_c+R@Vector((0,-6.2,.4));aim(cam,head_c);scene.render.filepath=str(review/'HeadDetail.png');bpy.ops.render.render(write_still=True)
compare()
# Leave the hero 3/4 camera and lights for rig_export/animate_mobs renders.
cam.data.type='ORTHO';cam.data.ortho_scale=8.6;view(25);scene.render.resolution_x=900;scene.render.resolution_y=900
bpy.ops.mesh.primitive_plane_add(size=60,location=(0,0,-.005));floor=staged(bpy.context.object);floor.data.materials.append(mat('Stage floor',srgb((150,147,146)),0))
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Sculpt.blend'))
print('BUILD_COMPLETE',flush=True)
