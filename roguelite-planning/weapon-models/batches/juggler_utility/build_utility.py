import bpy,bmesh,math,json,random,shutil,sys
from mathutils import Vector, Matrix
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
INV=json.loads((ROOT/'inventory.json').read_text())
TAU=math.tau
def lin(v):return ((v+.055)/1.055)**2.4 if v>.04045 else v/12.92
def mat(name,rgb,facets=True,wood=False):
 m=bpy.data.materials.new(name);m.use_nodes=True;b=m.node_tree.nodes.get('Principled BSDF');base=tuple(lin(v) for v in rgb);m.diffuse_color=(*base,1);b.inputs['Base Color'].default_value=(*base,1);b.inputs['Roughness'].default_value=.78
 if facets:
  n=m.node_tree.nodes;l=m.node_tree.links;t=n.new('ShaderNodeTexCoord');v=n.new('ShaderNodeTexVoronoi');v.inputs['Scale'].default_value=5
  if wood:
   s=n.new('ShaderNodeVectorMath');s.operation='MULTIPLY';s.inputs[1].default_value=(2.5,2.5,.34);l.new(t.outputs['Object'],s.inputs[0]);l.new(s.outputs[0],v.inputs['Vector'])
  else:l.new(t.outputs['Object'],v.inputs['Vector'])
  bw=n.new('ShaderNodeRGBToBW');l.new(v.outputs['Color'],bw.inputs[0]);r=n.new('ShaderNodeValToRGB');r.color_ramp.elements[0].position=.12;r.color_ramp.elements[0].color=(*(x*.90 for x in base),1);r.color_ramp.elements[1].position=.9;r.color_ramp.elements[1].color=(*(x*1.07 for x in base),1);l.new(bw.outputs[0],r.inputs[0]);l.new(r.outputs[0],b.inputs['Base Color'])
 return m
def move(o,c):
 for col in list(o.users_collection):col.objects.unlink(o)
 c.objects.link(o)
def finish(o,m,bev=0):
 move(o,asset);o.data.materials.append(m)
 if bev:
  mod=o.modifiers.new('Broad single facet bevel','BEVEL');mod.width=bev;mod.segments=1;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)
 return o
def mesh(name,v,f,m,bev=0):
 me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update();o=bpy.data.objects.new(name,me);asset.objects.link(o);bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free();return finish(o,m,bev)
def box(name,loc,dim,m,bev=.025):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return finish(o,m,bev)
def prism(name,p,th,m,bev=.02,y=0):
 n=len(p);return mesh(name,[(x,y+d,z) for d in [-th/2,th/2] for x,z in p],[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],m,bev)
def lathe(name,levels,m,n=12,center=(0,0,0)):
 v=[(center[0]+r*math.cos(TAU*i/n),center[1]+r*math.sin(TAU*i/n),center[2]+z) for z,r in levels for i in range(n)];f=[tuple(range(n-1,-1,-1)),tuple(range((len(levels)-1)*n,len(levels)*n))]
 for j in range(len(levels)-1):
  for i in range(n):f.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
 return mesh(name,v,f,m)
def cylinder(name,a,b,r,m,n=10):
 a=Vector(a);b=Vector(b);o=lathe(name,[(0,r),((b-a).length,r)],m,n);o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();o.location=a;return o
def ring(name,outer,inner,th,m,bev=.015):
 n=len(outer);v=[(x,y,z) for y in [-th/2,th/2] for p in [outer,inner] for x,z in p];f=[]
 for i in range(n):
  j=(i+1)%n;f.extend([(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),(i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)])
 return mesh(name,v,f,m,bev)
def oval(w,h):return [(-w*.30,-h/2),(w*.30,-h/2),(w/2,-h*.30),(w/2,h*.30),(w*.30,h/2),(-w*.30,h/2),(-w/2,h*.30),(-w/2,-h*.30)]
def link(name,loc,ang,twist=0,w=.32,h=.52):
 o=ring(name,oval(w,h),oval(w-.145,h-.145),.12,steel,.016);o.rotation_euler=(Matrix.Rotation(ang,4,'Y')@Matrix.Rotation(twist,4,'Z')).to_euler();o.location=loc;return o
def transform(objects,angle,translation=(0,0,0)):
 bpy.context.view_layer.update()
 M=Matrix.Translation(Vector(translation))@Matrix.Rotation(angle,4,'Y')
 for o in objects:o.matrix_world=M@o.matrix_world
def cut(o,c):
 bpy.context.view_layer.objects.active=o;mod=o.modifiers.new('Actual through opening','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=c;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(c,do_unlink=True)
def hole(o,x,z,r,n=8):
 c=cylinder('hole cutter',(x,-2,z),(x,2,z),r,dark,n);cut(o,c)
def strap(name,z,r,width=.16,turns=1,phase=0):
 # A closed broad helical leather ribbon, with real thickness and faceted turns.
 N=round(turns*12);v=[]
 for side in [0,.018]:
  for i in range(N+1):
   a=phase+TAU*turns*i/N;zz=z+width*turns*i/N
   v += [((r+side)*math.cos(a),(r+side)*math.sin(a),zz+dz) for dz in [-width*.43,width*.43]]
 f=[];k=2*(N+1)
 for i in range(N):
  a=2*i;b=a+2;f.extend([(a,b,b+1,a+1),(k+a+1,k+b+1,k+b,k+a),(a,k+a,k+b,b),(a+1,b+1,k+b+1,k+a+1)])
 f += [(0,1,k+1,k),(2*N,k+2*N,k+2*N+1,2*N+1)];return mesh(name,v,f,leather)

def ico(name,loc,scale,m,sub=2):
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub,radius=1,location=loc);o=bpy.context.object;o.name=name;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return finish(o,m)
def uvball(name,loc,scale,m,n=12,rings=8):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=n,ring_count=rings,radius=1,location=loc);o=bpy.context.object;o.name=name;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return finish(o,m)
def tube(name,points,r,m,n=8):
 v=[]
 for i,p in enumerate(points):
  t=(Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)])).normalized();a=t.cross(Vector((0,1,0)))
  if a.length<.01:a=t.cross(Vector((0,0,1)))
  a.normalize();b=t.cross(a)
  v.extend([Vector(p)+r*(a*math.cos(TAU*j/n)+b*math.sin(TAU*j/n)) for j in range(n)])
 f=[tuple(range(n-1,-1,-1)),tuple(range((len(points)-1)*n,len(points)*n))]+[(k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j) for k in range(len(points)-1) for j in range(n)]
 return mesh(name,v,f,m)
def xlathe(name,levels,m,n=12,z=0,y=0):
 o=lathe(name,levels,m,n);o.rotation_euler.y=math.pi/2;o.location=(0,y,z);return o
def pins():
 levels=[(0,.27),(.12,.37),(.65,.59),(1.18,.61),(1.68,.49),(2.16,.27),(2.36,.235),(2.57,.24),(2.80,.29),(3.16,.40),(3.44,.36),(3.62,.20)]
 for i,(x,y,ang,s) in enumerate([(0,0,0,1)]):
  o=lathe('Pin '+str(i+1)+' | continuous faceted body and twin red bands',[(z,r*1.18 if z<1.7 else r) for z,r in levels],white,10);o.data.materials.append(red)
  for p in o.data.polygons:
   if p.index>=2 and (p.index-2)//10 in [5,7]:p.material_index=1
  o.scale=(s,s,s);o.rotation_euler.y=ang;o.location=(x,y,.04)
 return (3,-12,5.6),(0,0,1.80),4.4

def ball():
 o=uvball('Faceted midnight bowling ball',(0,0,1.2),(1.2,1.2,1.2),navy,16,10)
 for i,(x,z,r) in enumerate([(-.29,1.87,.19),(.30,1.87,.19),(.04,1.29,.215)]):
  c=cylinder('Finger socket cutter',(x,-1.7,z),(x,-.52,z),r,dark,10);cut(o,c)
 # Dark material within the carved real blind sockets.
 o.data.materials.append(dark)
 for p in o.data.polygons:
  if p.center.y<-.50 and abs(p.normal.y)<.45 and any(abs(p.center.x-x)<r+.02 and abs(p.center.z-z)<r+.02 for x,z,r in [(-.29,1.87,.19),(.30,1.87,.19),(.04,1.29,.215)]):p.material_index=1
 bpy.context.view_layer.objects.active=o;mod=o.modifiers.new('Finger hole mouth bevels','BEVEL');mod.width=.035;mod.segments=1;mod.limit_method='ANGLE';mod.angle_limit=.60;bpy.ops.object.modifier_apply(modifier=mod.name)
 return (2,-10,4.6),(0,0,1.2),3.3

def blocks():
 for i,(loc,angle) in enumerate([((0,0,.61),0)]):
  before=set(asset.objects);o=box('Block '+str(i+1)+' | chamfered concrete shell',(0,0,0),(2.30,1.14,1.20),concrete,.12)
  for x in [-.56,.56]:
   c=box('True rectangular through cavity',(x,0,0),(.76,2,.76),dark,.06);cut(o,c)
  if i==2:o.rotation_euler.y=math.pi/2+angle
  o.location=loc
 return (5,-10,5.1),(0,0,.61),3.2

def ducks():
 for i,(pos,angle,s) in enumerate([((0,0,0),-.16,1)]):
  before=set(asset.objects)
  ico('Duck '+str(i+1)+' plump body',(0,0,.73),(.87,.92,.69),yellow)
  ico('Duck rounded head',(0,-.38,1.62),(.68,.63,.70),yellow)
  for side in [-1,1]:
   o=ico('Raised sculpted wing',(side*.70,.03,.75),(.24,.53,.37),yellow);o.rotation_euler.x=-.25
   eye=uvball('Gloss black oval eye',(side*.31,-.919,1.74),(.135,.068,.185),dark,10,6);eye.rotation_euler.z=side*.25
   box('White eye glint',(side*.31-.022,-.980,1.80),(.043,.009,.050),white,.002)
  # Open wedge bill: thick upper/lower mandibles and deep mouth cavity.
  prism('Broad upper orange duck bill',[(-.39,1.40),(-.34,1.52),(0,1.62),(.34,1.52),(.39,1.40),(0,1.38)],.43,orange,.018,y=-1.04)
  prism('Lower orange bill rim',[(-.32,1.39),(-.29,1.14),(0,1.10),(.29,1.14),(.32,1.39),(.24,1.22),(0,1.18),(-.24,1.22)],.30,orange,.015,y=-1.00)
  prism('Deep dark mouth interior',[(-.28,1.38),(-.23,1.26),(0,1.22),(.23,1.26),(.28,1.38)],.045,mouth,0,y=-1.10)
  ico('Upturned pointed tail',(0,.78,.93),(.36,.45,.36),yellow,1)
  bpy.context.view_layer.update();M=Matrix.Translation(Vector(pos))@Matrix.Rotation(angle,4,'Z')@Matrix.Diagonal((s,s,s,1))
  for o in set(asset.objects)-before:o.matrix_world=M@o.matrix_world
 return (3,-10,5),(0,0,1.17),3.0

def gloves():
 for i,side in enumerate([-1,1]):
  before=set(asset.objects)
  # Broad flattened fist, tucked lower palm, curled inward thumb.
  ico('Glove '+str(i+1)+' broad faceted knuckles',(0,0,1.60),(.75,.55,.88),red)
  ico('Glove lower palm',(0,.02,.96),(.54,.45,.58),red,2)
  thumb=ico('Curled inner thumb',(side*-.53,-.06,1.35),(.31,.40,.53),red);thumb.rotation_euler.y=side*.29
  lathe('Dark cuff with rolled edges',[(.02,.39),(.10,.48),(.58,.48),(.67,.41)],dark,10)
  box('Ivory wrist closure patch',(0,-.447,.35),(.62,.09,.37),ivory,.055)
  prism('Red diagonal wrist badge',[(-.20,.21),(.18,.24),(.09,.46),(-.21,.46)],.012,red,.007,y=-.500)
  box('Side ivory strap',(side*-.444,-.03,.35),(.08,.31,.37),ivory,.025)
  transform(set(asset.objects)-before,side*.19,(side*.91,0,.08))
  for o in set(asset.objects)-before:o['component']='LeftGlove' if side<0 else 'RightGlove'
 return (2,-12,5),(0,0,1.49),4.25

def yoyo():
 # Disk axis is Y, front face carries raised chamfered star and silver rim.
 for side in [-1,1]:
  o=lathe('Red yo-yo half',[(0,.93),(.09,1.03),(.36,1.03),(.48,.91)],red,14);o.rotation_euler.x=-side*math.pi/2;o.location=(-.55,side*.12,1.10)
  outer=[(math.sin(TAU*j/14)*.88-.55,math.cos(TAU*j/14)*.88+1.1) for j in range(14)];inner=[(math.sin(TAU*j/14)*.72-.55,math.cos(TAU*j/14)*.72+1.1) for j in range(14)]
  o=ring('Silver face ring',outer,inner,.06,silver,.018);o.location.y=side*.61
  pts=[(-.55+math.sin(TAU*j/10)*(.62 if j%2==0 else .29),1.1+math.cos(TAU*j/10)*(.62 if j%2==0 else .29)) for j in range(10)]
  v=[(x,side*.647,z) for x,z in pts]+[(-.55,side*.76,1.1)];f=[tuple(range(9,-1,-1))]+[(j,(j+1)%10,10) for j in range(10)];mesh('Raised five point gold star',v,f,gold)
 cylinder('Ivory wound string spool',(-.55,-.13,1.1),(-.55,.13,1.1),.63,ivory,14)
 pts=[(-.25,0,1.38),(-.02,-.04,1.01),(.32,-.10,.66),(.76,-.15,.42),(1.26,-.12,.33),(1.72,-.13,.20),(1.89,-.41,.14),(1.73,-.70,.14)]
 smooth=[]
 for j in range(len(pts)-1):
  a,b,c,d=[Vector(pts[max(0,min(len(pts)-1,k))]) for k in [j-1,j,j+1,j+2]]
  for k in range(5):
   t=k/5;smooth.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
 smooth.append(Vector(pts[-1]))
 for strand in [0,1]:
  pp=[v+Vector((0,.025*math.sin(j*.80+strand*math.pi),.025*math.cos(j*.80+strand*math.pi))) for j,v in enumerate(smooth)];tube('Twisted ivory cord strand '+str(strand),pp,.034,ivory,6)
 o=ring('Gold finger loop',oval(.63,.74),oval(.43,.53),.105,gold,.023);o.rotation_euler.x=math.pi/2;o.location=(1.43,-.96,.15)
 box('Red cord end clamp',(1.70,-.68,.15),(.24,.22,.20),red,.03)
 return (4,-9,5),(.30,-.15,1),4.25

def wrecking():
 o=uvball('Large faceted iron wrecking ball',(-.96,0,.93),(.90,.90,.93),steel,12,8)
 for m in [steel_light,steel_dark]:o.data.materials.append(m)
 rng=random.Random(25)
 for p in o.data.polygons:p.material_index=rng.choices([0,1,2],[.55,.25,.20])[0]
 lathe('Ball top chain socket',[(1.74,.29),(1.82,.33),(1.98,.33)],steel,10,(-.96,0,0))
 pts=[(-.86,2.02),(-.65,2.30),(-.42,2.58),(-.17,2.83),(.10,3.08),(.40,3.16),(.66,3.04)]
 for i,(x,z) in enumerate(pts):
  a=Vector(pts[max(0,i-1)]);b=Vector(pts[min(len(pts)-1,i+1)]);d=b-a;link('Heavy interlocked chain '+str(i),(x,0,z),math.atan2(d.x,d.y),math.pi/2 if i%2 else 0,w=.39,h=.59)
 before=set(asset.objects)
 lathe('Brown wrapped wooden grip',[(0,.22),(.08,.26),(1.61,.26),(1.71,.23)],wood,10)
 for z in [0,1.63]:lathe('Heavy steel grip cap',[(z,.28),(z+.06,.34),(z+.27,.34),(z+.32,.28)],steel,10)
 # actual broad helical leather wrap
 for j in range(5):
  pts2=[(.268*math.cos(TAU*k/12),.268*math.sin(TAU*k/12),.28+j*.25+k*.25/12) for k in range(13)];tube('Raised diagonal leather seam',pts2,.016,leather,5)
 transform(set(asset.objects)-before,-.38,(1.39,0,1.15))
 return (2,-10,5),(.1,0,1.8),4.6

def roller():
 before=set(asset.objects)
 lathe('Faceted red ergonomic roller grip',[(0,.21),(.10,.28),(.24,.25),(1.05,.24),(1.18,.18)],red,8)
 for z in [.0,1.10]:lathe('Charcoal grip end collar',[(z,.27),(z+.08,.30),(z+.21,.30),(z+.26,.24)],steel,8)
 transform(set(asset.objects)-before,-.18,(.70,0,.04))
 tube('Bent one piece metal roller arm',[(.47,0,1.30),(.39,0,1.68),(1.65,0,1.96),(1.65,0,2.61),(1.27,0,2.67)],.085,silver,6)
 xlathe('Ivory roller core',[(-1.24,.39),(-1.18,.46),(1.24,.46),(1.30,.38)],white,12,z=2.67)
 xlathe('Dark axle end',[(-1.38,.15),(-1.24,.15)],steel,10,z=2.67)
 # Yellow closed shell over upper roller, with varying downward edge and real drips.
 xs=[-1.18,-.97,-.79,-.73,-.72,-.69,-.63,-.59,-.58,-.51,-.30,-.13,-.08,-.07,-.04,.02,.06,.075,.12,.30,.43,.46,.49,.55,.60,.63,.65,.74,.91,.96,.97,1.0,1.06,1.10,1.12,1.21]
 ends=[-.15,-.18,-.20,-.29,-.43,-.49,-.50,-.46,-.32,-.20,-.21,-.29,-.43,-.60,-.68,-.70,-.66,-.58,-.37,-.21,-.24,-.34,-.43,-.46,-.44,-.40,-.29,-.20,-.26,-.37,-.48,-.54,-.55,-.51,-.40,-.23]
 v=[];N=9
 for shell in [0,1]:
  for x,end in zip(xs,ends):
   for j in range(N):
    a=-math.pi*.12+(math.pi*1.22)*j/(N-1);r=.476+shell*.06+.007*math.sin(x*19+j*7);zz=2.67+r*math.sin(a)
    if j in [0,N-1]:zz=2.67+end
    v.append((x,-r*math.cos(a),zz))
 K=len(xs)*N;f=[]
 for s in [0,1]:
  for i in range(len(xs)-1):
   for j in range(N-1):a=s*K+i*N+j;f.append((a,a+1,a+N+1,a+N))
 for i in range(len(xs)-1):
  for j in [0,N-1]:a=i*N+j;b=(i+1)*N+j;f.append((a,b,b+K,a+K))
 for i in [0,len(xs)-1]:
  for j in range(N-1):a=i*N+j;f.append((a,a+K,a+K+1,a+1))
 mesh('Thick yellow paint coat with hanging contour',v,f,yellow)
 for x,z in [(-.67,2.20),(.00,2.05),(1.08,2.18)]:ico('Rounded end of hanging yellow paint drip',(x,-.46,z),(.079,.09,.13),yellow,1)
 ico('Detached falling yellow paint drop',(-.68,-.1,1.99),(.075,.08,.13),yellow,1)
 return (-4,-10,5.2),(.05,0,1.61),4.1

def vacuum():
 # Body extends along X. Front is negative X, near-side dust chamber at negative Y.
 xlathe('Front red suction housing',[(.05,.53),(.18,.65),(.38,.65),(.48,.51)],red,10,z=.87)
 xlathe('Dark central motor backbone',[(.39,.43),(1.37,.43)],steel,10,z=.87)
 body=xlathe('Rear red motor housing',[(1.27,.51),(1.36,.65),(1.55,.65),(1.72,.51)],red,10,z=.87)
 xlathe('Front dark suction collar',[(-.48,.29),(-.38,.35),(.17,.35)],steel,10,z=.89)
 xlathe('Flared hose throat',[(-.96,.39),(-.51,.24)],steel,8,z=.89)
 # Rectangular octagonal mouth flares from a deep narrow throat. Closed thick shell.
 outline=[(-.61,-.72),(.61,-.72),(.78,-.55),(.78,.55),(.61,.72),(-.61,.72),(-.78,.55),(-.78,-.55)]
 v=[]
 for x,sy,sz in [(-2.12,1.18,1.18),(-1.96,1.18,1.18),(-.90,.28,.28),(-1.02,.20,.20),(-2.14,1.0,1.0)]:
  v.extend([(x,y*sy,.89+z*sz) for y,z in outline])
 f=[]
 for k in range(5):
  for j in range(8):f.append((k*8+j,k*8+(j+1)%8,((k+1)%5)*8+(j+1)%8,((k+1)%5)*8+j))
 o=mesh('Deep open flared octagonal vacuum funnel',v,f,steel);o.data.materials.append(dark)
 for p in o.data.polygons:
  if 16<=p.index<32:p.material_index=1
 # Deep throat ends at a dark recess, rather than a flat opening billboard.
 xlathe('Recessed nozzle throat',[(-.95,.15),(-.72,.15)],dark,8,z=.89)
 for x in [.27,1.17]:xlathe('Dust chamber dark retaining collar',[(x,.51),(x+.13,.55),(x+.22,.49)],steel,10,z=.77,y=-.48)
 xlathe('Faceted pale blue dust cup',[(.44,.48),(.51,.51),(1.15,.51),(1.23,.46)],blue,12,z=.77,y=-.48)
 box('Dust cup latch',(.82,-.47,1.32),(.50,.24,.13),steel,.035)
 box('Dust cup lower internal block',(.98,-.992,.66),(.25,.035,.29),navy,.025)
 outer=[(.13,1.36),(.28,2.01),(.47,2.20),(1.24,2.20),(1.44,2.00),(1.57,1.39)]
 inner=[(.40,1.43),(.52,1.88),(.61,1.95),(1.13,1.95),(1.21,1.88),(1.30,1.43)]
 ring('Open top carry handle',outer,inner,.27,steel,.045)
 box('Red top power button',(.54,0,2.20),(.27,.25,.06),red,.018)
 box('Red finger trigger',(.49,0,1.84),(.10,.18,.22),red,.015)
 for i in range(3):
  cutter=box('Actual motor vent cutter',(1.49,-.55,.96+i*.13),(.23,.45,.065),dark,.01);cut(body,cutter)
 for y in [-.58,.58]:
  cylinder('Charcoal rear wheel',(1.47,y,.51),(1.47,y+(-.17 if y<0 else .17),.51),.34,steel,12)
  cylinder('Red wheel hub',(1.47,y+(-.18 if y<0 else .18),.51),(1.47,y+(-.195 if y<0 else .195),.51),.19,red,12)
 return (-4.8,-8,3.9),(-.25,0,1.15),4.6
BUILD={17:ducks,19:gloves,20:blocks,21:yoyo,22:ball,23:pins,25:wrecking,27:roller,28:vacuum}
def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
def stats(obs,weld=False):
 d={'mesh_objects':len(obs),'vertices':0,'triangles':0,'loose_vertices':0,'nonmanifold_edges':0,'zero_area_faces':0,'zero_area_triangles':0,'uv_layers':True,'loaded_textures':True}
 d['materials']=len({m.name for o in obs for m in o.data.materials if m})
 for o in obs:
  bm=bmesh.new();bm.from_mesh(o.data)
  if weld:bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
  d['vertices']+=len(o.data.vertices);o.data.calc_loop_triangles();d['triangles']+=len(o.data.loop_triangles)
  d['loose_vertices']+=sum(not v.link_edges for v in bm.verts);d['nonmanifold_edges']+=sum(not e.is_manifold for e in bm.edges);d['zero_area_faces']+=sum(f.calc_area()<1e-10 for f in bm.faces)
  d['zero_area_triangles']+=sum((o.data.vertices[t.vertices[1]].co-o.data.vertices[t.vertices[0]].co).cross(o.data.vertices[t.vertices[2]].co-o.data.vertices[t.vertices[0]].co).length<1e-10 for t in o.data.loop_triangles)
  d['uv_layers'] &= bool(o.data.uv_layers);d['loaded_textures'] &= any(n.type=='TEX_IMAGE' and n.image and len(n.image.pixels)>0 for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes);bm.free()
 return d
def run(item):
 global asset,steel,dark,wood,leather,white,red,yellow,orange,mouth,ivory,gold,silver,navy,concrete,blue,steel_light,steel_dark
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 for m in list(bpy.data.materials):bpy.data.materials.remove(m)
 for im in list(bpy.data.images):
  if im.name not in ['Render Result','Viewer Node']:bpy.data.images.remove(im)
 scene=bpy.context.scene;asset=bpy.data.collections.new(item['name']+' | export geometry');scene.collection.children.link(asset)
 palette={'steel':(.28,.29,.33),'dark':(.085,.085,.09),'wood':(.44,.27,.15),'leather':(.33,.19,.10),'white':(.92,.91,.89),'red':(.85,.105,.10),'yellow':(1,.77,.015),'orange':(1,.34,.015),'mouth':(.37,.065,.006),'ivory':(.85,.78,.68),'gold':(.98,.70,.12),'silver':(.60,.63,.70),'navy':(.19,.22,.31),'concrete':(.50,.50,.50),'blue':(.48,.57,.77),'steel_light':(.31,.32,.36),'steel_dark':(.25,.26,.30)}
 materials=[]
 for name,color in palette.items():globals()[name]=mat(name,color,False);materials.append(globals()[name])
 loc,target,scale=BUILD[item['index']]();bpy.context.view_layer.update()
 out=Path(item['output']);out.mkdir(parents=True,exist_ok=True);shutil.copyfile(item['source'],out/'Reference.png')
 obs=list(asset.objects)
 # One atlas containing padded color tiles. Face islands have positive UV area.
 size=320;atlas=bpy.data.images.new(item['slug']+'_BaseColor',width=size,height=size,alpha=False);pixels=[];cols=list(palette.values())+[(.5,.5,.5)]*8
 for yy in range(size):
  for xx in range(size):pixels.extend((*cols[(yy//64)*5+xx//64],1))
 atlas.pixels.foreach_set(pixels);atlas.filepath_raw=str(out/'BaseColor.png');atlas.file_format='PNG';atlas.save();atlas.pack()
 final=mat('Portable color atlas',(.5,.5,.5),False);tex=final.node_tree.nodes.new('ShaderNodeTexImage');tex.image=atlas;tex.interpolation='Closest';final.node_tree.links.new(tex.outputs['Color'],final.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
 for o in obs:
  bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
  bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(o.data);bm.free()
  while o.data.uv_layers:o.data.uv_layers.remove(o.data.uv_layers[0])
  uv=o.data.uv_layers.new(name='BaseColorUV')
  for p in o.data.polygons:
   idx=materials.index(o.data.materials[p.material_index]);cx=(idx%5+.5)/5;cy=(idx//5+.5)/5
   for j,li in enumerate(p.loop_indices):uv.data[li].uv=(cx+.065*math.cos(TAU*j/len(p.loop_indices)),cy+.065*math.sin(TAU*j/len(p.loop_indices)))
   p.material_index=0;p.use_smooth=False
  o.data.materials.clear();o.data.materials.append(final)
  # Retain separate identifiable components, all with a common assembly pivot.
  scene.cursor.location={21:(-.55,0,1.1),22:(0,0,1.2),25:(1.07,0,2),27:(.60,0,.60),28:(.86,0,2.07)}.get(item['index'],(0,0,0));bpy.ops.object.origin_set(type='ORIGIN_CURSOR');o.select_set(False)
 if item['index']==17:
  bpy.ops.object.select_all(action='DESELECT')
  for o in obs:
   vg=o.vertex_groups.new(name=o.name);vg.add(list(range(len(o.data.vertices))),1,'REPLACE');o.select_set(True)
  bpy.context.view_layer.objects.active=obs[0];bpy.ops.object.join();o=bpy.context.object;o.name='RubberDuck';obs=[o]
 if item['index']==19:
  joined=[];part_sets={label:[o for o in obs if o.get('component')==label] for label in ['LeftGlove','RightGlove']}
  for side,label in [(-1,'LeftGlove'),(1,'RightGlove')]:
   bpy.ops.object.select_all(action='DESELECT');parts=part_sets[label]
   for o in parts:
    vg=o.vertex_groups.new(name=o.name);vg.add(list(range(len(o.data.vertices))),1,'REPLACE');o.select_set(True)
   bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();o=bpy.context.object;o.name=label;o['component']=label;o.parent=None
   scene.cursor.location=(side*.91+math.sin(side*.19)*.35,0,.08+math.cos(side*.19)*.35);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');joined.append(o)
  obs=joined
 bpy.ops.object.select_all(action='DESELECT')
 for o in obs:o.select_set(True)
 bpy.context.view_layer.objects.active=obs[0]
 bpy.ops.export_scene.fbx(filepath=str(out/'Model.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
 bpy.ops.export_scene.gltf(filepath=str(out/'Model.glb'),use_selection=True,export_format='GLB',export_animations=False)
 st=stats(obs);st.update(index=item['index'],name=item['name'],bounds_min=[min((o.matrix_world@v.co)[j] for o in obs for v in o.data.vertices) for j in range(3)],bounds_max=[max((o.matrix_world@v.co)[j] for o in obs for v in o.data.vertices) for j in range(3)],notes='Single reusable item; gloves are independent left/right components. Closed assembled components with intentional overlapping joints. Back surfaces inferred. Palette UV islands intentionally overlap by material. Static prop; no rig. No Studio validation.')
 st['multiplicity']='Independent left and right gloves, plus review assembly' if item['index']==19 else 'One reusable item'
 if item['index']==19:
  st['components']={}
  for side,label in [(-1,'LeftGlove'),(1,'RightGlove')]:
   cs=bpy.data.scenes.new(label);bpy.context.window.scene=cs;copies=[]
   pivot=Vector((side*.91+math.sin(side*.19)*.35,0,.08+math.cos(side*.19)*.35))
   for original in obs:
    if original.get('component')!=label:continue
    c=original.copy();c.data=original.data.copy();cs.collection.objects.link(c);c.location-=pivot;copies.append(c)
   bpy.ops.object.select_all(action='SELECT');bpy.context.view_layer.objects.active=copies[0];cs.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
   dest=out/'components'/label;dest.mkdir(parents=True,exist_ok=True);shutil.copyfile(out/'BaseColor.png',dest/'BaseColor.png')
   bpy.ops.export_scene.fbx(filepath=str(dest/'Model.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
   bpy.ops.export_scene.gltf(filepath=str(dest/'Model.glb'),use_selection=True,use_active_scene=True,export_format='GLB',export_animations=False)
   bpy.data.libraries.write(str(dest/'Model.blend'),{cs},fake_user=True)
   cs_stats=stats(copies);cs_stats['pivot']='Wrist center at origin';st['components'][label]=cs_stats;(dest/'validation.json').write_text(json.dumps(cs_stats,indent=2));(dest/'README.md').write_text(label+' independent reusable glove. All mesh origins at the wrist center. No rig or shared object dependency. Packed color atlas. Rebuilt by parent build_utility.py index 19.\n')
   bpy.context.window.scene=scene
   for c in copies:bpy.data.objects.remove(c,do_unlink=True)
   bpy.data.scenes.remove(cs)
 stage=bpy.data.collections.new('REVIEW | not exported');scene.collection.children.link(stage)
 floor=mat('Review gray',(.48,.48,.48),False);bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,st['bounds_min'][2]-.035));g=bpy.context.object;g.data.materials.append(floor);move(g,stage)
 for pos,power,sz in [((-4,-6,8),700,5),((5,-3,6),500,5),((1,5,7),850,4)]:
  bpy.ops.object.light_add(type='AREA',location=pos);o=bpy.context.object;o.data.energy=power;o.data.shape='DISK';o.data.size=sz;aim(o,target);move(o,stage)
 scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.4,.4,.4,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.55
 bpy.ops.object.camera_add(location=loc);cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=scale;aim(cam,target);move(cam,stage);scene.camera=cam
 scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=950;scene.render.resolution_y=950;scene.render.resolution_percentage=100;scene.view_settings.view_transform='Standard';scene.view_settings.exposure=-.45;scene.render.image_settings.file_format='PNG'
 bpy.ops.object.select_all(action='DESELECT')
 for o in obs:o.select_set(True)
 bpy.context.view_layer.objects.active=obs[0]
 scene.render.filepath=str(out/'Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'));bpy.ops.render.render(write_still=True)
 cam.location=(-loc[0],-loc[1],loc[2]);aim(cam,target);scene.render.filepath=str(out/'Alternate.png');bpy.ops.render.render(write_still=True);cam.location=loc;aim(cam,target);scene.render.filepath=str(out/'Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
 for ext in ['glb','fbx']:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
  else:bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
  imported=[o for o in scene.objects if o.type=='MESH'];st[ext+'_reimport']=stats(imported,True);st[ext+'_reimport']['unexpected_nonmesh_objects']=sum(o.type!='MESH' for o in scene.objects);st[ext+'_reimport']['topology_note']='Welded coordinate duplicates for topology analysis because exporters split UV/normal seams.'
 (out/'validation.json').write_text(json.dumps(st,indent=2));(out/'README.md').write_text('# '+item['name']+'\n\nEditable reference reconstruction with separately named closed mesh components. Preview and Alternate are actual Blender Cycles renders. Geometry-only FBX/GLB include a packed portable color atlas; palette UV islands intentionally overlap by color. Unseen surfaces inferred from the single source. Component intersections at assembly joints are intentional. Static pose, no rig, no Studio test.\n\nRebuild: Blender 5.2 --background --threads 4 --python ../../batches/juggler_utility/build_utility.py -- '+str(item['index'])+'\n\nMeasured mesh and export checks: validation.json.\n');print('ASSET_COMPLETE',item['index'],json.dumps(st),flush=True)
if __name__=='__main__':
 ids=[int(x) for x in sys.argv[sys.argv.index('--')+1:]] if '--' in sys.argv else list(BUILD)
 for i in ids:run(next(x for x in INV if x['index']==i))















