import bpy,bmesh,math,json,random,shutil,sys
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parents[2]
INVENTORY=json.loads((ROOT/'inventory.json').read_text())
random.seed(843)
bpy.context.preferences.filepaths.save_version=0
COL={'wood':(.29,.19,.125),'woodlight':(.38,.25,.17),'gold':(.64,.45,.20),'goldlight':(.82,.64,.33),'stone':(.24,.235,.26),'stoneedge':(.36,.34,.35),'dark':(.07,.065,.075),'steel':(.53,.52,.57),'silver':(.72,.70,.73),'leather':(.20,.115,.078),'blue':(.05,.24,.87),'cyan':(.08,.68,.96),'purple':(.44,.13,.8),'green':(.33,.41,.20),'skin':(.49,.53,.34),'eye':(.48,.98,.10),'navy':(.12,.14,.24)}
def reset():
 global asset,stage,scene
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.outliner.orphans_purge(do_recursive=True)
 scene=bpy.context.scene
 asset=bpy.data.collections.new('ASSET | export geometry');scene.collection.children.link(asset)
 stage=bpy.data.collections.new('REVIEW | not exported');scene.collection.children.link(stage)
def move(o,c):
 for col in list(o.users_collection):col.objects.unlink(o)
 c.objects.link(o)
def mesh(name,v,f,color):
 me=bpy.data.meshes.new(name);me.from_pydata(v,[],f);me.update()
 o=bpy.data.objects.new(name,me);asset.objects.link(o)
 o['color']=COL.get(color,color) if isinstance(color,str) else color
 bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free();return o
def color_obj(o,name,color):
 o.name=name;move(o,asset);o['color']=COL.get(color,color) if isinstance(color,str) else color;return o
def bevel(o,w):
 if w:
  bpy.context.view_layer.objects.active=o;m=o.modifiers.new('Broad crafted bevel','BEVEL');m.width=w;m.segments=1;bpy.ops.object.modifier_apply(modifier=m.name)
 return o
def box(name,loc,dim,color,w=.04):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.dimensions=dim;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 return bevel(color_obj(o,name,color),w)
def prism(name,profile,depth,color,w=0,y=0):
 n=len(profile);v=[(x,y-depth/2,z) for x,z in profile]+[(x,y+depth/2,z) for x,z in profile]
 return bevel(mesh(name,v,[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],color),w)
def lathe(name,rings,color,n=12,xy=(0,0)):
 v=[(xy[0]+r*math.cos(2*math.pi*i/n),xy[1]+r*math.sin(2*math.pi*i/n),z) for z,r in rings for i in range(n)]
 f=[tuple(range(n-1,-1,-1)),tuple(range((len(rings)-1)*n,len(rings)*n))]
 f += [(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for j in range(len(rings)-1) for i in range(n)]
 return mesh(name,v,f,color)
def tube(name,pts,radii,color,n=7):
 pts=list(map(Vector,pts));radii=[radii]*len(pts) if isinstance(radii,(float,int)) else radii
 v=[]
 for i,p in enumerate(pts):
  t=(pts[min(i+1,len(pts)-1)]-pts[max(i-1,0)]).normalized();a=t.cross(Vector((0,1,0))).normalized()
  if a.length<.01:a=t.cross(Vector((1,0,0))).normalized()
  b=t.cross(a).normalized()
  for k in range(n):v.append(p+radii[i]*(a*math.cos(k*2*math.pi/n)+b*math.sin(k*2*math.pi/n)))
 f=[tuple(range(n-1,-1,-1)),tuple(range((len(pts)-1)*n,len(pts)*n))]
 f += [(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i) for j in range(len(pts)-1) for i in range(n)]
 return mesh(name,v,f,color)
def ico(name,loc,scale,color,sub=2):
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub,radius=1,location=loc);o=bpy.context.object;o.scale=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);return color_obj(o,name,color)
def gem(name,center,rx,rz,color,depth=.15):
 x,y,z=center;v=[(x-rx,y,z),(x,y,z+rz),(x+rx,y,z),(x,y,z-rz),(x,y-depth,z),(x,y+.06,z)]
 return mesh(name,v,[(i,(i+1)%4,4) for i in range(4)]+[((i+1)%4,i,5) for i in range(4)],color)
def plate_gem(name,x,z,size,color='blue',y=-.24):
 prism(name+' gold bezel',[(x-size,z),(x,z+size),(x+size,z),(x,z-size)],.14,'goldlight',.025,y)
 sign=1 if y<0 else -1
 gem(name,(x,y-sign*.105,z),size*.67,size*.67,color,size*.30*sign)
def helix(name,z0,z1,radius,turns,color,width=.075):
 v=[];steps=int(turns*16)
 for i in range(steps+1):
  t=i/steps;a=t*turns*2*math.pi;z=z0+t*(z1-z0)
  for r,dz in [(radius,-width),(radius+.025,-width),(radius+.025,width),(radius,width)]:v.append((r*math.cos(a),r*math.sin(a),z+dz))
 f=[(3,2,1,0),tuple(range(steps*4,steps*4+4))]
 for j in range(steps):
  for k in range(4):f.append((j*4+k,j*4+(k+1)%4,(j+1)*4+(k+1)%4,(j+1)*4+k))
 return mesh(name,v,f,color)
def hammer():
 box('Heavy octagonal hammer head',(0,0,3.75),(2.85,.96,1.60),'stone',.20)
 for x in [-1.18,1.18]:
  box('Wide forged end band',(x,0,3.75),(.48,1.04,1.68),'stoneedge',.14)
  for sy in [-1,1]:
   box('Recessed rune panel',(x,sy*.528,3.76),(.31,.025,1.22),'dark',.015)
   for dx in [-.185,.185]:box('Raised rune frame',(x+dx,sy*.56,3.76),(.035,.035,1.34),'steel',.01)
   for z in [3.10,4.42]:box('Frame end',(x,sy*.56,z),(.40,.035,.04),'steel',.008)
   pts=[(x-.04,sy*.563,4.35),(x+.10,sy*.563,4.23),(x+.04,sy*.563,4.05),(x-.10,sy*.563,3.90),(x-.06,sy*.563,3.77),(x+.11,sy*.563,3.58),(x+.05,sy*.563,3.43),(x-.10,sy*.563,3.25),(x+.03,sy*.563,3.15)]
   tube('Interlaced angular rune',pts,.033,'steel',4)
   for z in [4.15,3.78,3.4]:tube('Rune knot',[(x-.10,sy*.563,z),(x,sy*.563,z+.13),(x+.10,sy*.563,z),(x,sy*.563,z-.13),(x-.10,sy*.563,z)],.026,'stoneedge',4)
 box('Head to haft socket',(0,0,2.85),(.81,.71,.29),'stoneedge',.07)
 box('Lower socket',(0,0,2.60),(.56,.57,.29),'stone',.06)
 lathe('Dark shaft',[(.73,.225),(2.52,.225)],'dark',10)
 helix('Broad spiral leather wrapping',.78,2.5,.234,4.0,'leather',.135)
 lathe('Faceted pommel',[(.45,.25),(.54,.37),(.83,.37),(.95,.28)],'stoneedge',8)
 tube('Leather wrist loop',[(0,-.27,.68),(.10,-.43,.39),(.18,-.52,.08),(.10,-.51,-.10),(-.16,-.43,-.21),(-.39,-.35,-.13),(-.46,-.30,.10),(-.36,-.28,.35),(0,-.27,.68)],.075,'leather',5)
 return -17,(5,-13,7)
def staff():
 tube('Crooked carved wooden shaft',[(0,0,.25),(.04,0,.65),(-.03,0,1.35),(.02,.02,2.25),(-.12,0,3.05),(-.28,0,3.42),(-.13,0,3.75),(-.25,0,4.10)], [.145,.12,.12,.136,.153,.178,.153,.17],'wood',8)
 lathe('Gold bottom ferrule',[(0,.145),(.09,.213),(.38,.179),(.47,.17)],'gold',8)
 lathe('Ferrule rim',[(.41,.196),(.49,.196),(.54,.153)],'goldlight',8)
 lathe('Central grip band',[(2.09,.20),(2.13,.23),(2.34,.23),(2.4,.19)],'gold',8)
 # Collar and inset blue stone; branches rise from the collar around the crystal.
 box('Crown gold socket',(-.22,0,3.96),(.58,.54,.51),'gold',.065)
 plate_gem('Socket sapphire',-.22,3.98,.22,'cyan',-.33)
 tube('Left fork', [(-.23,0,3.95),(-.68,0,4.15),(-.91,0,4.54),(-.94,0,4.88)], [.21,.16,.105,.025],'wood',7)
 tube('Right fork',[(-.19,.11,3.99),(.07,.09,4.29),(.12,.06,4.81),(.05,.04,5.22),(-.13,.02,5.45)],[.19,.16,.12,.09,.018],'woodlight',7)
 tube('Front claw',[(-.20,-.13,3.97),(-.43,-.31,4.35),(-.65,-.29,4.62)],[.17,.13,.02],'wood',6)
 # Asymmetric six-sided crystal with broad triangular facets and a sharply tapered crown.
 v=[(-.35,0,4.15),(-.70,-.19,4.62),(-.66,.18,4.63),(-.18,-.30,4.63),(-.12,.19,4.66),(-.61,-.17,5.16),(-.55,.15,5.17),(-.23,-.14,5.16),(-.17,.15,5.14),(-.51,0,5.62)]
 f=[(0,1,3),(0,3,4),(0,4,2),(0,2,1),(1,5,3),(3,5,7),(3,7,4),(4,7,8),(4,8,2),(2,8,6),(2,6,1),(1,6,5),(5,9,7),(7,9,8),(8,9,6),(6,9,5)]
 v=[(x,y,z+(.38 if z>5.5 else .10 if z>5.0 else 0)) for x,y,z in v]
 mesh('Large cyan crown crystal',v,f,'cyan')
 return -39,(2,-15,7)
def sword():
 # Double-edged broad blade: sculpted diamond section with raised central ridge.
 rings=[(1.82,.23),(2.05,.40),(2.25,.40),(2.40,.30),(4.72,.30),(5.25,.25)]
 v=[]
 for z,w in rings:v.extend([(-w,0,z),(-w*.60,-.10,z),(0,-.145,z),(w*.60,-.10,z),(w,0,z),(w*.60,.10,z),(0,.145,z),(-w*.60,.10,z)])
 f=[tuple(range(7,-1,-1))]
 for j in range(len(rings)-1):
  for i in range(8):f.append((j*8+i,j*8+(i+1)%8,(j+1)*8+(i+1)%8,(j+1)*8+i))
 v.append((0,0,5.95));f += [((len(rings)-1)*8+i,(len(rings)-1)*8+(i+1)%8,len(v)-1) for i in range(8)]
 mesh('Broad diamond-section steel blade',v,f,'silver')
 for y in [-.149,.149]:prism('Dark recessed fuller',[(-.055,2.40),(.055,2.40),(.065,4.72),(0,4.9),(-.065,4.72)],.008,(.32,.32,.40),0,y)
 prism('Swept golden crossguard',[(-1.05,1.97),(-.95,2.20),(-.75,2.10),(-.30,1.96),(0,1.93),(.30,1.96),(.75,2.10),(.95,2.20),(1.05,1.97),(.81,1.85),(.25,1.72),(-.25,1.72),(-.81,1.85)],.29,'gold',.055)
 for y in [-.20,.20]:
  plate_gem('Royal centre sapphire',0,1.86,.31,'blue',y)
  for x in [-.94,.94]:plate_gem('Guard tip sapphire',x,2.04,.17,'blue',y)
 lathe('Grip core',[(.34,.17),(1.69,.17)],'stone',8)
 helix('Indigo crossed leather wrap',.38,1.67,.18,5.5,'navy',.09)
 lathe('Grip end collar',[(.26,.21),(.38,.21),(.42,.17)],'gold',8)
 lathe('Hexagonal pommel',[(0,.19),(.09,.31),(.31,.29),(.37,.20)],'gold',6)
 plate_gem('Pommel sapphire',0,.17,.19,'blue',-.26)
 return -48,(1.5,-16,6)
def pandora():
 box('Stone coffer body',(0,0,.89),(2.65,1.96,1.70),'stone',.14)
 box('Bottom bevel plinth',(0,0,.19),(2.77,2.07,.30),'stoneedge',.08)
 for x in [-1.24,1.24]:
  for y in [-.90,.90]:
   box('Corner gilded upright',(x,y,.88),(.19,.20,1.60),'gold',.035)
   box('Octagonal corner foot',(x*1.015,y*1.015,.20),(.40,.41,.40),'gold',.075)
 for y in [-1.005,1.005]:
  box('Horizontal lower trim',(0,y,.20),(2.45,.10,.15),'gold',.03)
  box('Horizontal upper trim',(0,y,1.63),(2.54,.12,.16),'gold',.03)
  for sign in [-1,1]:
   pts=[(sign*.04,y*1.01,.27),(sign*1.05,y*1.01,.27),(sign*1.15,y*1.01,.57),(sign*.97,y*1.01,1.14),(sign*.72,y*1.01,1.33),(sign*.46,y*1.01,1.06),(sign*.69,y*1.01,.85),(sign*.83,y*1.01,1.02)]
   tube('Raised angular spiral scrollwork',pts,.072,'goldlight',4)
 for x in [-1.34,1.34]:
  for z in [.24,1.63]:box('Side horizontal border',(x,0,z),(.10,1.82,.14),'gold',.025)
  pts=[(x,-.72,.29),(x,.65,.29),(x,.74,.72),(x,.37,1.18),(x,-.12,.87),(x,.16,.58),(x,.31,.79)]
  tube('Side spiral relief',pts,.075,'gold',4)
 box('Dark slightly open lid seam',(0,0,1.82),(2.53,1.85,.18),'dark',.03)
 box('Purple magic within seam',(0,0,1.825),(2.59,1.90,.065),'purple',.02)
 box('Heavy chamfered stone lid',(0,0,2.08),(2.87,2.15,.45),'stone',.16)
 box('Raised inset lid panel',(0,0,2.34),(2.20,1.62,.17),'stoneedge',.09)
 for x in [-1.25,1.25]:
  for y in [-.90,.90]:
   s=1 if x>0 else -1
   pts=[(x+.06*s,y*1.18,1.98),(x+.15*s,y*1.18,2.14),(x+.12*s,y*1.18,2.48),(x-.15*s,y*1.18,2.48),(x-.15*s,y*1.18,2.25),(x-.01*s,y*1.18,2.25),(x-.01*s,y*1.18,2.37)]
   tube('Lid hooked corner binding',pts,.082,'goldlight',4)
 box('Top gem gold setting',(0,0,2.46),(.75,.66,.13),'gold',.06)
 # Pyramid jewel faces on top.
 mesh('Lid amethyst pyramid',[(-.31,-.26,2.53),(.31,-.26,2.53),(.31,.26,2.53),(-.31,.26,2.53),(0,0,2.77)],[(0,1,4),(1,2,4),(2,3,4),(3,0,4),(3,2,1,0)],'purple')
 prism('Heavy central clasp',[(-.28,2.03),(.28,2.03),(.36,1.91),(.28,1.23),(0,1.02),(-.28,1.23),(-.36,1.91)],.20,'gold',.055,-1.105)
 gem('Clasp amethyst',(0,-1.245,1.56),.115,.27,'purple',.065)
 return 0,(-6,-11,7)
def crystal():
 lathe('Broad carved octagonal base',[(0,.98),(.08,1.08),(.34,1.00),(.44,.88),(.51,.85)],'stone',12)
 lathe('Gold equatorial plinth band',[(.43,.87),(.47,.94),(.58,.94),(.63,.85)],'gold',12)
 lathe('Stone orb cradle',[(.59,.84),(.72,.88),(.85,.77),(.91,.62)],'stone',12)
 for a in [-math.pi/4,-3*math.pi/4,math.pi/4,3*math.pi/4]:
  x,y=.78*math.cos(a),.78*math.sin(a)
  o=box('Raised retaining claw',(x,y,1.03),(.23,.27,.67),'gold',.05);o.rotation_euler=(-.4*math.sin(a),.4*math.cos(a),a)
  o=box('Claw dark inner bevel',(x*.94,y*.94,1.09),(.20,.18,.65),'stone',.035);o.rotation_euler=(-.4*math.sin(a),.4*math.cos(a),a)
 plate_gem('Cradle front crystal',0,.54,.30,'cyan',-.915)
 orb=ico('Arcane swirling interior',(0,0,1.78),(.97,.97,.97),'blue',3);orb['orb']=True
 shell=ico('Faceted translucent crystal shell',(0,0,1.78),(1.04,1.04,1.04),(.46,.65,1.0),3);shell['glass']=True
 # Conformal spiral streaks and angular star inclusions are real surface geometry.
 for arm in [0,math.pi]:
  pts=[]
  for i in range(35):
   t=i/34;r=.06+.72*t;a=arm+t*5.0;x=r*math.cos(a);z=1.78+r*math.sin(a);y=-math.sqrt(max(.01,.97**2-r*r))-.006;pts.append((x,y,z))
  tube('Arcane swirling inlay',pts,[.010+.013*i/34 for i in range(35)],'cyan' if arm==0 else (.60,.42,.96),5)
 for x,z,s in [(-.57,2.15,.05),(.47,1.34,.06),(-.48,1.45,.05),(.64,2.0,.03)]:
  r2=x*x+(z-1.78)**2;y=-math.sqrt(.97**2-r2)-.012;gem('Suspended starlight',(x,y,z),s,s*1.3,(.60,.90,1),.015)
 return 0,(1.8,-14,5.5)
def medusa():
 lathe('Leather weapon grip',[(.27,.19),(1.16,.19)],'dark',9);helix('Diagonal grip binding',.29,1.14,.197,4.5,'leather',.058)
 lathe('Gold grip end',[(0,.20),(.12,.30),(.28,.29),(.38,.23)],'gold',7);plate_gem('Pommel emerald',0,.17,.16,'eye',-.26)
 lathe('Grip lower ring',[(.30,.25),(.38,.25),(.42,.2)],'goldlight',10)
 lathe('Neck gold collar',[(1.08,.28),(1.17,.36),(1.45,.36),(1.54,.28)],'gold',8)
 for z in [1.15,1.45]:lathe('Neck collar rim',[(z,.39),(z+.075,.39)],'goldlight',8)
 plate_gem('Collar emerald',0,1.32,.24,'eye',-.38)
 # Custom face planes, broad temples, projecting cheekbones, tapered jaw and chin.
 # Each ring has front-facing vertices at angles 210..330; face looks along -Y.
 rings=[(1.46,.17,.19),(1.65,.32,.29),(1.84,.49,.37),(2.15,.61,.43),(2.44,.65,.45),(2.72,.62,.43),(2.96,.51,.35),(3.09,.28,.23)]
 v=[];n=12
 for z,rx,ry in rings:
  for i in range(n):
   a=2*math.pi*i/n;v.append((rx*math.cos(a),ry*math.sin(a),z))
 f=[tuple(range(n-1,-1,-1)),tuple(range((len(rings)-1)*n,len(rings)*n))]
 for j in range(len(rings)-1):
  for i in range(n):
   a=j*n+i;b=j*n+(i+1)%n;c=(j+1)*n+(i+1)%n;d=(j+1)*n+i
   f.extend([(a,b,c),(a,c,d)])
 mesh('Sculpted stone face',v,f,'skin')
 ico('Rear cranium',(0,.14,2.55),(.60,.48,.61),'skin',2)
 # Almond eye sockets and luminous inset eyes, with heavy angular brows.
 for s in [-1,1]:
  x=s*.29
  prism('Recessed almond eye socket',[(x-.22,2.43),(x-.13,2.57),(x+.10,2.58),(x+.22,2.48),(x+.10,2.36),(x-.10,2.35)],.075,'green',.012,-.417)
  prism('Emerald almond eye',[(x-.16,2.46),(x-.08,2.53),(x+.075,2.53),(x+.15,2.47),(x+.065,2.42),(x-.08,2.42)],.03,'eye',.009,-.469)
  brow=[(s*.08,-.48,2.61),(s*.24,-.49,2.70),(s*.43,-.40,2.68),(s*.55,-.31,2.60)]
  tube('Stern sculpted brow ridge',brow,[.068,.09,.074,.04],'green',5)
  ico('Angular cheek plane',(s*.40,-.36,2.20),(.22,.14,.24),'skin',1)
  ico('Ear',(s*.62,.0,2.31),(.12,.13,.23),'skin',1)
 mesh('Sculpted nose bridge',[(-.09,-.43,2.63),(.09,-.43,2.63),(-.115,-.51,2.20),(.115,-.51,2.20),(0,-.67,2.23),(0,-.53,2.60),(-.13,-.42,2.16),(.13,-.42,2.16)],[(0,1,5),(0,5,4,2),(5,1,3,4),(2,4,3,7,6),(0,2,6),(1,7,3),(0,6,7,1)],'skin')
 for s in [-1,1]:ico('Nostril inset',(s*.092,-.523,2.185),(.047,.026,.024),'dark',1)
 prism('Defined upper lip',[(-.23,1.975),(-.12,2.06),(0,2.035),(.10,2.06),(.23,1.975),(.10,1.993),(0,1.99),(-.10,1.993)],.055,'green',0,-.38)
 prism('Mouth crease',[(-.22,1.967),(0,1.997),(.21,1.967),(0,1.956)],.018,'dark',0,-.417)
 prism('Lower lip plane',[(-.17,1.949),(0,1.968),(.17,1.949),(.09,1.90),(-.09,1.90)],.055,'skin',0,-.392)
 # Seven thick, individually routed serpent locks plus five open-mouthed heads.
 locks=[([(-.43,.13,2.09),(-.69,.02,2.15),(-.81,-.02,2.63),(-.65,0,3.07),(-.32,.04,3.29),(.08,.06,3.22)],[.17,.20,.20,.19,.17,.14]),
 ([(.40,.12,2.03),(.64,.08,2.43),(.79,.06,2.99),(.61,.03,3.35),(.22,0,3.47),(-.20,.02,3.36)],[.17,.19,.20,.19,.18,.13]),
 ([(-.28,.31,2.11),(-.52,.38,2.68),(-.51,.30,3.22),(-.92,.15,3.32),(-1.12,.02,3.63),(-1.04,-.05,3.94),(-.79,-.08,4.11)],[.18,.24,.22,.18,.17,.15,.13]),
 ([(.18,.40,2.45),(.36,.33,3.04),(.27,.26,3.54),(.53,.15,3.85),(.85,.02,3.78),(1.05,-.04,3.57)],[.20,.23,.21,.17,.14,.12]),
 ([(-.39,.17,2.85),(-.92,.08,2.98),(-1.12,-.02,3.28),(-1.40,-.10,3.28)],[.19,.18,.16,.12]),
 ([(-.52,.18,2.10),(-.95,.04,2.38),(-1.22,-.02,2.23),(-1.24,-.11,1.93),(-1.05,-.18,1.79)],[.18,.18,.16,.14,.11]),
 ([(.46,.17,2.77),(.71,.04,2.45),(.91,-.01,2.24),(1.15,-.04,2.31),(1.23,-.09,2.66),(1.44,-.14,2.80)],[.21,.21,.18,.16,.14,.11])]
 for i,(pts,rs) in enumerate(locks):
  smooth=[];rads=[];vv=list(map(Vector,pts))
  for j in range(len(vv)-1):
   p0=vv[max(0,j-1)];p1=vv[j];p2=vv[j+1];p3=vv[min(len(vv)-1,j+2)]
   for t in [0,.5]:
    smooth.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t));rads.append(rs[j]*(1-t)+rs[j+1]*t)
  smooth.append(vv[-1]);rads.append(rs[-1]);tube('Serpent lock %02d'%i,smooth,rads,(.27,.33,.18),7)
 def snakehead(name,p,flip):
  x,y,z=p
  # Closed wedge upper skull, separate open lower jaw with real dark mouth space.
  prof=[(x-.19,z+.11),(x+.04,z+.16),(x+.26,z+.03),(x+.26,z-.05),(x+.03,z-.08),(x-.17,z-.04)]
  if flip:prof=[(2*x-a,b) for a,b in prof]
  prism(name+' angular skull',prof,.25,'green',.025,y)
  d=-1 if flip else 1
  prism(name+' open jaw',[(x-.10*d,z-.07),(x+.10*d,z-.36),(x+.24*d,z-.32),(x+.23*d,z-.38),(x+.07*d,z-.41),(x-.15*d,z-.11)],.20,'green',.01,y)
  prism(name+' dark recessed mouth',[(x-.13*d,z-.08),(x+.23*d,z-.065),(x+.22*d,z-.33),(x+.07*d,z-.365)],.035,(.075,.10,.04),0,y+.08)
  for sy in [-1,1]:
   gem(name+' glowing eye',(x+.04*d,y+sy*.128,z+.035),.043,.055,'eye',.008)
  for off in [.13,.22]:
   tube(name+' pointed fang',[(x+off*d,y-.075,z-.035),(x+(off-.015)*d,y-.075,z-.16)],[.022,.001],(.66,.70,.42),5)
  tube(name+' lower fang',[(x+.17*d,y-.075,z-.355),(x+.165*d,y-.075,z-.25)],[.021,.001],(.66,.70,.42),5)
 for i in range(2,7):snakehead('Snake %02d'%i,locks[i][0][-1],i in [4,5])
 return -13,(1.3,-15,6.0)

def finish(entry,angle,camera):
 out=Path(entry['output']);out.mkdir(parents=True,exist_ok=True);shutil.copyfile(entry['source'],out/'Reference.png')
 objs=list(asset.objects);rot=Matrix.Rotation(math.radians(angle),4,'Y')
 for o in objs:o.matrix_world=rot@o.matrix_world
 minz=min((o.matrix_world@v.co).z for o in objs for v in o.data.vertices)
 for o in objs:o.location.z-=minz
 # Triangulate visible planes and use a portable face-color atlas. Color variation follows mesh facets.
 colors=[];polycols=[]
 for o in objs:
  bm=bmesh.new();bm.from_mesh(o.data)
  if not o.get('orb') and any(s in o.name.lower() for s in ['shaft','head','body','lid','base','face','cranium','cheek','blade','skull','serpent']):
   edges=[e for e in bm.edges if e.calc_length()>.37]
   if edges:bmesh.ops.subdivide_edges(bm,edges=edges,cuts=1,use_grid_fill=True)
  bmesh.ops.triangulate(bm,faces=list(bm.faces))
  bmesh.ops.dissolve_degenerate(bm,dist=1e-6,edges=list(bm.edges))
  bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(o.data);bm.free()
  base=tuple(o['color']);these=[]
  for p in o.data.polygons:
   fac=random.uniform(.90,1.075)
   if o.get('orb'):
    c=p.center;dx=c.x;dz=c.z;rr=math.sqrt(dx*dx+dz*dz)/1.04;theta=math.atan2(dz,dx)
    swirl=(.5+.5*math.cos(theta-rr*7.4))**5
    front=max(0,-c.y/1.04);core=math.exp(-rr*rr*15)
    base=(.25+.25*swirl+.25*core,.32+.37*swirl+.46*core,.80+.17*swirl)
    fac=random.uniform(.92,1.07)
   col=tuple(min(1,max(0,x*fac)) for x in base);these.append(len(colors));colors.append(col)
  polycols.append(these)
 tile=4;grid=math.ceil(math.sqrt(len(colors)));size=grid*tile
 img=bpy.data.images.new('Portable base-color atlas',width=size,height=size,alpha=False)
 pixels=[0.0]*(size*size*4)
 for i,col in enumerate(colors):
  tx=(i%grid)*tile;ty=(i//grid)*tile
  for yy in range(ty,ty+tile):
   for xx in range(tx,tx+tile):
    k=(yy*size+xx)*4;pixels[k:k+4]=[*col,1]
 img.pixels.foreach_set(pixels);img.filepath_raw=str(out/'BaseColor.png');img.file_format='PNG';img.save();img.pack()
 mat=bpy.data.materials.new(entry['name']+' | atlas');mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.72
 tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=img;tex.interpolation='Closest';mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
 glass=None;arcane=None
 if any(o.get('glass') for o in objs):
  glass=mat.copy();glass.name='Crystal shell | portable alpha';gs=glass.node_tree.nodes.get('Principled BSDF');gs.inputs['Alpha'].default_value=.22;gs.inputs['Roughness'].default_value=.14;gs.inputs['Coat Weight'].default_value=.6
  arcane=mat.copy();arcane.name='Arcane interior | subtle emission';es=arcane.node_tree.nodes.get('Principled BSDF');et=next(n for n in arcane.node_tree.nodes if n.type=='TEX_IMAGE');arcane.node_tree.links.new(et.outputs['Color'],es.inputs['Emission Color']);es.inputs['Emission Strength'].default_value=.35
 for o,indices in zip(objs,polycols):
  o.data.materials.clear();o.data.materials.append(glass if o.get('glass') else arcane if o.get('orb') and arcane else mat)
  for layer in list(o.data.uv_layers):o.data.uv_layers.remove(layer)
  uv=o.data.uv_layers.new(name='AtlasUV');uv.active_render=True
  for p,idx in zip(o.data.polygons,indices):
   x=((idx%grid)+.5)/grid;y=((idx//grid)+.5)/grid
   for k,li in enumerate(p.loop_indices):
    dx,dy=[(-.18,-.18),(.18,-.18),(0,.18)][k%3];uv.data[li].uv=(x+dx/grid,y+dy/grid)
  o.select_set(True)
 # Useful assembly origin: bottom center; geometry remains separately named and editable.
 bpy.context.scene.cursor.location=(0,0,0)
 bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.select_set(True)
 bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
 bpy.ops.export_scene.fbx(filepath=str(out/'Model.fbx'),use_selection=True,object_types={'MESH'},add_leaf_bones=False,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y')
 bpy.ops.export_scene.gltf(filepath=str(out/'Model.glb'),export_format='GLB',use_selection=True,export_materials='EXPORT')
 verts=sum(len(o.data.vertices) for o in objs);tris=sum(len(o.data.polygons) for o in objs);loose=zero=nonman=0
 for o in objs:
  bm=bmesh.new();bm.from_mesh(o.data);loose+=sum(not v.link_faces for v in bm.verts);zero+=sum(f.calc_area()<1e-10 for f in bm.faces);nonman+=sum(not e.is_manifold for e in bm.edges);bm.free()
 coords=[o.matrix_world@v.co for o in objs for v in o.data.vertices];mn=[min(v[i] for v in coords) for i in range(3)];mx=[max(v[i] for v in coords) for i in range(3)]
 report={'name':entry['name'],'vertices':verts,'triangles':tris,'mesh_count':len(objs),'material_count':len(set(m.name for o in objs for m in o.data.materials)),'uv':'per-face atlas coordinates','packed_texture':True,'loose_vertices':loose,'zero_area_faces':zero,'non_manifold_edges':nonman,'bounds_min':mn,'bounds_max':mx,'intentional_intersections':'Separate closed decorative components intersect support surfaces; no runtime rig or collision setup.','limitations':['Unseen rear surfaces inferred symmetrically.','Roblox Studio import not tested.']}
 # Verify both delivery formats can be read back, without contaminating the editable source scene.
 originals=set(bpy.data.objects)
 bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
 imported=[o for o in bpy.data.objects if o not in originals];report['glb_reimport_meshes']=sum(o.type=='MESH' for o in imported);report['glb_reimport_triangles']=sum(len(o.data.polygons) for o in imported if o.type=='MESH')
 for o in imported:bpy.data.objects.remove(o,do_unlink=True)
 originals=set(bpy.data.objects);bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
 imported=[o for o in bpy.data.objects if o not in originals];report['fbx_reimport_meshes']=sum(o.type=='MESH' for o in imported);report['fbx_reimport_triangles']=sum(len(o.data.polygons) for o in imported if o.type=='MESH')
 for o in imported:bpy.data.objects.remove(o,do_unlink=True)
 (out/'validation.json').write_text(json.dumps(report,indent=2))
 # Importers may reuse basename-matched image datablocks. Restore authoritative atlas after roundtrip audit.
 img.filepath_raw=str(out/'BaseColor.png');img.reload();img.pack();tex.image=img
 desc={30:'Crooked wooden staff, three crown tines, cyan faceted crystal, inset socket gem and gold ferrules.',31:'Broad beveled hammer head, inset angular knotwork, thin leather wrapping and wrist loop.',32:'Diamond-section steel blade, dark fuller, golden swept guard, sapphire settings and indigo leather grip.',33:'Stone coffer with raised angular scroll relief, corner bindings, central clasp, amethyst lid jewel and purple lid seam.',34:'Sculpted olive stone face, green almond eyes, five open serpent mouths with upper/lower fangs, seven curved serpent locks and jeweled handle.',35:'Faceted alpha shell surrounding an opaque colored swirl interior, modeled spiral inlays and star inclusions, stone/gold cradle and front gem.'}[entry['index']]
 extra=' Crystal shell alpha and subtle interior emission use portable materials; appearance may need transparency/lighting tuning in Roblox. The stylized interior is modeled and surface-colored rather than volumetric.' if entry['index']==35 else ''
 (out/'README.md').write_text('# '+entry['name']+'\n\n'+desc+'\n\nReference: `'+Path(entry['source']).name+'` (user-provided generated art; copied without edits as Reference.png). Rebuild with `batches/magic/build_magic.py -- '+str(entry['index'])+'` in Blender background mode.\n\nSeparate named mesh components; one portable face-color texture atlas, packed in the Blender file and embedded in exports. Rear details inferred from the visible design. Decorative components intentionally intersect. Static components can be merged on import if desired.'+extra+'\n\nActual geometry and reimport checks are in validation.json. Roblox Studio import, scale tuning, attachment points and collision configuration are not tested.\n')
 # Review stage, matched neutral lighting, no stage geometry is exported.
 def aim(o,point):o.rotation_euler=(Vector(point)-o.location).to_track_quat('-Z','Y').to_euler()
 center=Vector([(mn[i]+mx[i])*.5 for i in range(3)]);height=mx[2]-mn[2];width=mx[0]-mn[0];extent=max(height,width)
 bpy.ops.object.camera_add(location=center+Vector(camera)*extent/5);cam=bpy.context.object;move(cam,stage);cam.name='Review camera';aim(cam,center);cam.data.type='ORTHO';scene.camera=cam
 def frame():
  inv=cam.rotation_euler.to_matrix().transposed();pc=[inv@(v-center) for v in coords]
  cam.data.ortho_scale=max(max(v[j] for v in pc)-min(v[j] for v in pc) for j in [0,1])*1.18
 frame()
 for name,offset,power,sz in [('Key',(-4,-6,9),1000,5),('Fill',(5,-3,6),700,4),('Rim',(2,5,8),1100,4)]:
  bpy.ops.object.light_add(type='AREA',location=center+Vector(offset)*extent/5);o=bpy.context.object;move(o,stage);o.name=name;o.data.energy=power*(extent/5)**2;o.data.shape='DISK';o.data.size=sz*extent/5;aim(o,center)
 bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.04));floor=bpy.context.object;move(floor,stage);floor.name='Review floor (not exported)'
 fm=bpy.data.materials.new('Neutral floor');fm.diffuse_color=(.115,.12,.135,1);floor.data.materials.append(fm)
 scene.world.color=(.22,.22,.22);scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
 scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG';scene.render.filepath=str(out/'Preview.png')
 # Saved viewport opens on the asset in material mode.
 bpy.ops.object.select_all(action='DESELECT')
 for o in objs:o.select_set(True)
 bpy.context.view_layer.objects.active=objs[0]
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':area.spaces.active.region_3d.view_distance=extent*1.6;area.spaces.active.region_3d.view_location=center;area.spaces.active.shading.type='MATERIAL'
 bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
 bpy.ops.render.render(write_still=True)
 cam.location=center+Vector((-camera[0]-3,abs(camera[1]),camera[2]))*extent/5;aim(cam,center);frame();scene.render.filepath=str(out/'Alternate.png');bpy.ops.render.render(write_still=True)
 print('COMPLETE',entry['index'],entry['name'],tris,flush=True)

FUN={30:staff,31:hammer,32:sword,33:pandora,34:medusa,35:crystal}
ids=[int(x) for x in sys.argv[sys.argv.index('--')+1:]] if '--' in sys.argv else list(FUN)
for idx in ids:
 reset();angle,cam=FUN[idx]();finish(next(e for e in INVENTORY if e['index']==idx),angle,cam)
