from pathlib import Path
src=(Path(__file__).parent/'base.py').read_text()
src=src[:src.index("if __name__=='__main__':")]
src=src.replace("scene.cursor.location=pivots[item['index']]", "scene.cursor.location={12:(.1,0,.7),13:(0,0,1.9),14:(-.2,0,1.5),15:(0,0,1),16:(.1,.1,.45),18:(0,.2,1.2)}[item['index']]")
src=src.replace("bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all", "[o.data.uv_layers.remove(uv) for uv in list(o.data.uv_layers)];bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all")
src=src.replace("bpy.ops.export_scene.fbx(filepath", "mod=o.modifiers.new('Portable triangles','TRIANGULATE');bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=mod.name)\n bpy.ops.export_scene.fbx(filepath")
src=src.replace("scene.view_settings.view_transform='AgX'", "scene.view_settings.view_transform='Standard';scene.view_settings.exposure=-.55")
src=src.replace("../../batches/melee_tools/build_melee.py", "../../batches/throwables/build_throwables.py")
src=src.replace("o['pivot']='Handhold center'", "o['pivot']='Assembly center or central grip; components preserved as vertex groups'")
src=src.replace("stage=bpy.data.collections.new", "[bpy.data.objects.remove(ob,do_unlink=True) for ob in list(bpy.data.objects) if ob.type=='EMPTY'];stage=bpy.data.collections.new")
src=src.replace("Chain pose is static; links remain identifiable by vertex groups.", "Posed sets are static; individual pieces remain identifiable by vertex groups. Back decoration mirrors the visible side where appropriate. Molotov glass and flames are opaque stylized geometry for portable rendering; no alpha or emission is required.")
exec(compile(src,str(Path(__file__).parent/'base.py'),'exec'))

def palette():
 global cream,brown,orange,red,gold,black,green,amber,fire,yellow
 cream=mat('Cream',(.91,.78,.57));brown=mat('End grain brown',(.48,.235,.12));orange=mat('Honey orange timber',(.69,.37,.15),True,True)
 red=mat('Scarlet',(.65,.12,.105));gold=mat('Gold',(.85,.61,.25));black=mat('Ink black',(.14,.13,.17));green=mat('Olive bottle',(.29,.36,.18));amber=mat('Amber liquid',(.57,.245,.035));fire=mat('Orange flame', (1,.40,.02),False);yellow=mat('Yellow flame',(1,.83,.14),False)

def boomerang():
 palette()
 # Bent solid aerofoil: continuous rounded elbow, broad faceted cross sections.
 path=[(-1.63,3.19,.19),(-1.6,3.08,.28),(-1.51,2.76,.32),(-1.30,2.34,.34),(-1.06,1.88,.35),(-.81,1.42,.35),(-.55,1.02,.37),(-.24,.76,.39),(.12,.70,.39),(.53,.82,.37),(1.02,1.02,.34),(1.48,1.24,.32),(1.89,1.44,.27),(2.11,1.58,.23),(2.17,1.65,.16)]
 v=[];n=8
 for i,(x,z,w) in enumerate(path):
  a=Vector(path[max(0,i-1)][:2]);b=Vector(path[min(len(path)-1,i+1)][:2]);d=(b-a).normalized();normal=Vector((-d.y,d.x))
  for j in range(n):
   t=math.tau*j/n;v.append((x+normal.x*w*math.cos(t),.13*math.sin(t),z+normal.y*w*math.cos(t)))
 f=[tuple(range(n-1,-1,-1)),tuple(range((len(path)-1)*n,len(path)*n))]
 for i in range(len(path)-1):
  for j in range(n):f.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
 o=mesh('Solid curved wooden boomerang',v,f,orange);o.data.materials.append(brown)
 for p in o.data.polygons:
  if p.index<2 or (p.index-2)//8 in [0,1,2,11,12,13]:p.material_index=1
 # Paint bands conform to cross sections, wrapping around the entire arm.
 for idx in [2,3,11,12]:
  x,z,w=path[idx];a=Vector(path[idx-1][:2]);b=Vector(path[idx+1][:2]);d=(b-a).normalized();normal=Vector((-d.y,d.x));vv=[]
  for s in [-.055,.055]:
   for j in range(8):
    t=math.tau*j/8;vv.append((x+d.x*s+normal.x*(w+.003)*math.cos(t),.134*math.sin(t),z+d.y*s+normal.y*(w+.003)*math.cos(t)))
  # hollow closed band, thickness avoids open surfaces
  inner=[(x+(x0-x)*.994,y*.96,z+(z0-z)*.994) for x0,y,z0 in vv];vv+=inner;ff=[]
  for j in range(8):
   k=(j+1)%8;ff.extend([(j,k,k+8,j+8),(j+16,j+24,k+24,k+16),(j,j+16,k+16,k),(j+8,k+8,k+24,j+24)])
  mesh('Cream wraparound decorative band',vv,ff,cream)
 for side in [-1,1]:
  for idx,direction in [(2,-1),(11,1)]:
   a=Vector(path[idx][:2]);b=Vector(path[idx+1][:2]);d=(b-a).normalized();normal=Vector((-d.y,d.x));c=(a+b)/2;w=(path[idx][2]+path[idx+1][2])/2
   for offset in [-.18,0,.18]:
    coords=[]
    for u,q in [(offset-.067,-.075),(offset+.067,-.075),(offset,.105)]:
     pos=c+normal*u+d*q*direction;yy=side*(.13-.05385*abs(u)/w+.019);coords.append((pos.x,yy,pos.y))
    coords += [(x,y-side*.003,z) for x,y,z in coords]
    mesh('Flush cream triangular painted motif',coords,[(0,1,2),(3,5,4),(0,3,4,1),(1,4,5,2),(2,5,3,0)],cream)
 return (0,-9,5),(.2,0,1.84),4.5

def kunais():
 global steel,silver,iron
 palette()
 steel=mat('Blue charcoal kunai steel',(.28,.29,.34));silver=mat('Pale gray blade bevel',(.49,.50,.55));iron=mat('Charcoal grip steel',(.20,.21,.25))
 for k,(a,x,z) in enumerate([(0,0,0)]):
  before=set(asset.objects)
  outline=[(0,0),(-.42,1.53),(0,1.91),(.42,1.53)];v=[(x,0,z) for x,z in outline]
  v += [(x*.94,y,1.10+(z-1.10)*.975) for y in [-.025,.025] for x,z in outline];v += [(0,-.16,1.70),(0,.16,1.70)];f=[]
  for j in range(4):
   q=(j+1)%4;f.extend([(j,q,4+q,4+j),(j,8+j,8+q,q),(4+j,4+q,12),(8+q,8+j,13)])
  o=mesh('Kunai %d diamond blade'%k,v,f,steel);o.data.materials.append(silver)
  for p in o.data.polygons:
   if p.index%4 in [0,1]:p.material_index=1
  lathe('Blade collar',[(1.9,.21),(2.02,.21),(2.05,.17)],iron,8)
  lathe('Dark grip core',[(2.02,.14),(2.72,.14)],iron,8)
  old=globals()['leather'];globals()['leather']=cream;strap('Broad diagonal ivory grip wrapping',2.05,.145,.17,3.6);globals()['leather']=old
  lathe('Upper grip wrap',[(2.63,.155),(2.73,.155)],cream,8)
  outer=[(.34*math.cos(math.tau*j/8+math.pi/8),3.04+.34*math.sin(math.tau*j/8+math.pi/8)) for j in range(8)];inner=[(.205*math.cos(math.tau*j/8+math.pi/8),3.04+.205*math.sin(math.tau*j/8+math.pi/8)) for j in range(8)]
  ring('Open octagonal pommel ring',outer,inner,.16,steel,.025)
  transform(set(asset.objects)-before,a,(x,0,z))
 return (1.0,-11,3.8),(0,0,1.69),3.85

def molotov():
 palette()
 o=lathe('Green faceted bottle',[(0,.45),(.1,.53),(.25,.54),(1.36,.54),(1.65,.54),(1.92,.50),(2.17,.25),(2.68,.22),(2.73,.27),(2.89,.27),(2.94,.22)],green,10)
 o.data.materials.append(amber)
 for p in o.data.polygons:
  if p.index>=2 and (p.index-2)//10==2 and (p.index-2)%10 in [5,6,7,8]:p.material_index=1
 lathe('Bunched cloth in bottle mouth',[(2.90,.19),(3.0,.17),(3.12,.11)],cream,7)
 # Thick folded fabric silhouette, narrowing and turning down beside the mouth.
 p=[(-.12,2.88),(.02,3.16),(.29,3.26),(.60,3.10),(.73,2.74),(.83,2.33),(1.05,2.13),(1.24,2.30),(1.28,2.63),(1.13,2.52),(1.0,2.72),(.94,3.19),(.65,3.52),(.27,3.54),(.04,3.39)]
 rag=prism('Folded linen rag',p,.28,cream,.05)
 prism('Dark folded rag crease',[(.15,3.2),(.39,3.38),(.69,3.2),(.76,2.78),(.93,2.44),(.78,2.52),(.57,3.10),(.37,3.22)],.012,brown,0,y=-.17)
 prism('Charred rag tip',[(.80,2.55),(.82,2.25),(1.05,2.11),(1.25,2.25),(1.30,2.54),(1.13,2.46),(1.03,2.59)],.31,brown,.03)
 for name,p,m,y in [('Outer sculpted flame',[(.99,2.48),(.94,2.8),(1.07,3.10),(1.04,3.49),(1.35,3.21),(1.31,2.98),(1.48,3.11),(1.39,2.69),(1.24,2.47)],fire,0),('Golden flame core',[(1.07,2.49),(1.06,2.78),(1.20,3.10),(1.20,3.29),(1.31,3.06),(1.24,2.84),(1.33,2.92),(1.29,2.63)],yellow,-.17)]:prism(name,p,.15,m,.005,y=y)
 for x,z in [(.95,3.74),(1.14,4.0)]:prism('Floating stylized ember',[(x,z),(x-.06,z+.1),(x-.08,z+.3),(x+.05,z+.19)],.09,fire,0)
 transform(list(asset.objects),.25,(-.6,0,.15));return (2,-10,4.5),(.3,0,2.03),4.75

def eggs():
 palette()
 for k,(x,y,z) in enumerate([(0,0,.08)]):
  bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1);o=bpy.context.object;o.name='Egg %d cream faceted shell'%(k+1)
  for v in o.data.vertices:
   q=v.co.copy();v.co=(q.x*.68*(1-.19*q.z),q.y*.62*(1-.19*q.z),q.z*.97+1)
  bm=bmesh.new();bm.from_mesh(o.data)
  for height,upper in [(1.90,True),(.09,False)]:
   cut=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.000001,plane_co=(0,0,height),plane_no=(0,0,1),clear_outer=upper,clear_inner=not upper)
   bmesh.ops.holes_fill(bm,edges=[e for e in bm.edges if e.is_boundary],sides=0)
  bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()
  shell=mat('Egg %d cream with broad ochre patches'%k,(.94,.85,.70),False);finish(o,shell);o.location=(x,y,z)
  anchor=bpy.data.objects.new('Temporary egg paint coordinates',None);bpy.context.scene.collection.objects.link(anchor);anchor.location=(x,y,z)
  nt=shell.node_tree;tex=nt.nodes.new('ShaderNodeTexCoord');tex.object=anchor;mask=None
  centers=[Vector((-.33,-.52,1.43)),Vector((.36,-.47,.74)),Vector((-.43,-.4,.32)),Vector((.42,.32,1.45)),Vector((-.44,.29,.81))]
  centers[0].x+=.055*k;centers[1].z+=.12*k
  for t,r in zip(centers,[.24,.31,.29,.27,.31]):
   dist=nt.nodes.new('ShaderNodeVectorMath');dist.operation='DISTANCE';dist.inputs[1].default_value=t;nt.links.new(tex.outputs['Object'],dist.inputs[0]);less=nt.nodes.new('ShaderNodeMath');less.operation='LESS_THAN';less.inputs[1].default_value=r;nt.links.new(dist.outputs['Value'],less.inputs[0])
   noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=3;noise.inputs['Detail'].default_value=0;nt.links.new(tex.outputs['Object'],noise.inputs['Vector']);mul=nt.nodes.new('ShaderNodeMath');mul.operation='MULTIPLY_ADD';mul.inputs[1].default_value=.15;mul.inputs[2].default_value=r-.075;nt.links.new(noise.outputs['Fac'],mul.inputs[0]);nt.links.new(mul.outputs[0],less.inputs[1])
   if mask is None:mask=less.outputs[0]
   else:
    mx=nt.nodes.new('ShaderNodeMath');mx.operation='MAXIMUM';nt.links.new(mask,mx.inputs[0]);nt.links.new(less.outputs[0],mx.inputs[1]);mask=mx.outputs[0]
  mix=nt.nodes.new('ShaderNodeMixRGB');mix.inputs[1].default_value=(*(lin(c) for c in (.94,.85,.70)),1);mix.inputs[2].default_value=(*(lin(c) for c in (.72,.47,.29)),1);nt.links.new(mask,mix.inputs[0]);nt.links.new(mix.outputs[0],nt.nodes.get('Principled BSDF').inputs['Base Color'])
 return (1,-10,3.4),(0,0,1.05),2.4

def steak():
 palette();fat=mat('Warm ivory fat',(.91,.78,.63));flesh=mat('Red meat facets',(.70,.16,.12));side=mat('Steak side',(.62,.40,.30))
 outline=[(-.9,1.25),(-.59,1.55),(-.12,1.60),(.25,1.39),(.36,.99),(.7,.68),(1.13,.53),(1.43,.22),(1.52,-.27),(1.35,-.68),(.92,-.95),(.37,-1.03),(-.1,-.85),(-.43,-.54),(-.74,-.31),(-1.00,.13),(-1.10,.66)]
 # Topology closed solid with broad cream edge, red central inset, thick side wall.
 n=len(outline);v=[(x,y,z) for z,s in [(0,.91),(.12,1),(.40,1),(.47,.90)] for x,y in [(a*s,b*s) for a,b in outline]];f=[tuple(range(n-1,-1,-1)),tuple(range(3*n,4*n))]
 for j in range(3):
  for i in range(n):f.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
 o=mesh('Thick steak with perimeter fat',v,f,fat);o.data.materials.append(side)
 for p in o.data.polygons:
  if p.index>=2 and (p.index-2)//n<2:p.material_index=1
 # Faceted marbled red meat inset follows the same asymmetric bean outline.
 from mathutils.geometry import delaunay_2d_cdt
 boundary=[Vector((x*.84,y*.84)) for x,y in outline];points=list(boundary)
 def inside(x,y):
  odd=False
  for i in range(n):
   a=boundary[i];b=boundary[(i+1)%n]
   if (a.y>y)!=(b.y>y) and x<(b.x-a.x)*(y-a.y)/(b.y-a.y)+a.x:odd=not odd
  return odd
 while len(points)<n+34:
  x=random.uniform(-.87,1.2);y=random.uniform(-.84,1.3)
  if inside(x,y):points.append(Vector((x,y)))
 verts,edges,faces,*_=delaunay_2d_cdt(points,[(i,(i+1)%n) for i in range(n)],[list(range(n))],1,.00001)
 vv=[(p.x,p.y,.475+random.random()*.005) for p in verts];ff=list(faces)
 # Create the matching underside and close the perimeter using the original boundary.
 boundaryids=[min(range(len(verts)),key=lambda j:(verts[j]-p).length) for p in boundary];bottom=len(vv);vv.extend((p.x,p.y,.470) for p in boundary);ff.append(tuple(range(bottom+n-1,bottom-1,-1)))
 for i in range(n):j=(i+1)%n;ff.append((boundaryids[i],boundaryids[j],bottom+j,bottom+i))
 meat=mesh('Irregular triangulated red meat face',vv,ff,flesh)
 # Give actual 3D face triangulation a restrained ruby color breakup.
 for j in range(4):meat.data.materials.append(mat('Ruby meat tone '+str(j),(.60+j*.025,.10+j*.018,.08+j*.012),False))
 for p in meat.data.polygons:p.material_index=1+p.index%4
 # Bone is a T branching into an open rounded eye, above the meat face.
 outer=[(.29,.1),(.41,.3),(.70,.33),(.91,.19),(1.0,-.04),(.86,-.24),(.57,-.28),(.35,-.11)];inner=[(.43,.08),(.5,.18),(.68,.20),(.80,.12),(.85,-.02),(.77,-.12),(.6,-.14),(.47,-.06)]
 o=ring('Cream bone ring',outer,inner,.026,fat,.007)
 for q in o.data.vertices:q.co=(q.co.x,q.co.z,q.co.y+.487)
 p=[(.44,.01),(.27,.17),(.02,.23),(-.42,.47),(-.1,.20),(.18,.05),(.48,-.14)]
 o=prism('Branching bone and fat seam',p,.02,fat,0)
 for q in o.data.vertices:q.co=(q.co.x,q.co.z,q.co.y+.487)
 o=prism('Bone branch joining perimeter fat',[(.42,-.05),(.23,.21),(.10,.38),(.16,.71),(.30,.87),(.34,.98),(.43,.75),(.31,.55),(.29,.34),(.57,.15)],.018,fat,0)
 for q in o.data.vertices:q.co=(q.co.x,q.co.z,q.co.y+.487)
 bones=[ob for ob in asset.objects if 'bone' in ob.name.lower()];main=bones[0]
 for other in bones[1:]:
  bpy.context.view_layer.objects.active=main;mod=main.modifiers.new('Unified bone face','BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=other;bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(other,do_unlink=True)
 for o in list(asset.objects):o.location.z=.23
 return (3,-5,7),(.12,.1,.50),3.65

def suit(name,x,z,size,m,y=-.2,kind='spade'):
 if kind=='diamond':p=[(0,1),(.62,0),(0,-1),(-.62,0)]
 else:
  p=[(0,1),(-.7,.36),(-.76,.04),(-.57,-.25),(-.29,-.28),(-.09,-.11),(-.11,-.45),(-.39,-.68),(.39,-.68),(.11,-.45),(.09,-.11),(.29,-.28),(.57,-.25),(.76,.04),(.7,.36)]
  if kind=='heart':p=[(0,-.8),(-.78,.02),(-.75,.44),(-.49,.67),(-.18,.67),(0,.43),(.18,.67),(.49,.67),(.75,.44),(.78,.02)]
 return prism(name,[(x+a*size,z+b*size) for a,b in p],.014,m,.002,y=y)

def cards():
 palette();paper=mat('Warm card stock',(.91,.89,.85),False);shadowpaper=mat('Shadowed card layers',(.57,.55,.55),False);maroon=mat('Deep red sleeve',(.40,.07,.09));ink=black
 def cardbody(name,y,z,w,h,m):
  p=[(-w/2+.065,z-h/2),(w/2-.065,z-h/2),(w/2,z-h/2+.065),(w/2,z+h/2-.065),(w/2-.065,z+h/2),(-w/2+.065,z+h/2),(-w/2,z+h/2-.065),(-w/2,z-h/2+.065)];return prism(name,p,.053,m,.004,y=y)
 for i in range(8):cardbody('Layered deck card %02d'%i,i*.067,1.24,1.55,2.28,shadowpaper if i in [3,6] else paper)
 box('Crimson decorative card back',(0,-.038,1.24),(1.34,.018,2.05),maroon,.06)
 for x in [-.57,.57]:box('Gold long border',(x,-.053,1.24),(.033,.014,1.81),gold,.002)
 for z in [.34,2.14]:box('Gold short border',(0,-.053,z),(1.17,.014,.033),gold,.002)
 suit('Crimson central diamond',0,1.24,.78,red,-.065,'diamond')
 for x in [-.56,.56]:
  for z in [.36,2.12]:
   o=ring('Golden corner diamond',[(x,z+.13),(x+.1,z),(x,z-.13),(x-.1,z)],[(x,z+.06),(x+.047,z),(x,z-.06),(x-.047,z)],.015,gold,0);o.location.y=-.07
 box('Thick red deck sleeve',(0,.205,1.20),(1.69,.65,.56),red,.035)
 for z in [.91,1.49]:box('Gold sleeve rim',(0,.205,z),(1.72,.68,.065),gold,.013)
 suit('Gold spade clasp',0,1.21,.49,gold,-.167)
 suit('Inset dark spade silhouette',0,1.21,.415,maroon,-.182)
 clasp=suit('Faceted gold central spade',0,1.21,.345,gold,-.200)
 for q in clasp.data.vertices:q.co.y=-.20+(q.co.y+.20)*6
 for ob in list(asset.objects):
  group=ob.vertex_groups.new(name='COMPONENT_Deck');group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
 for j,(x,z,a,kind) in enumerate([(-1.23,3.23,-.26,'heart'),(.35,3.42,.18,'spade'),(1.80,2.26,.32,'diamond')]):
  before=set(asset.objects);cardbody('Floating '+kind+' card',0,0,.83,1.32,paper);suit('Large '+kind+' suit',0,0,.24,red if kind!='spade' else ink,-.039,kind)
  for xx,zz in [(-.29,.49),(.29,-.49)]:suit('Small corner suit',xx,zz,.066,red if kind!='spade' else ink,-.04,'diamond')
  transform(set(asset.objects)-before,a,(x,.22,z))
  for ob in set(asset.objects)-before:
   group=ob.vertex_groups.new(name='COMPONENT_'+kind.title()+'Card');group.add(list(range(len(ob.data.vertices))),1,'REPLACE')
 return (3,-10,4.8),(.25,0,2.03),4.85

BUILD={12:boomerang,13:kunais,14:molotov,15:eggs,16:steak,18:cards}
if __name__=='__main__':
 ids=[int(x) for x in sys.argv[sys.argv.index('--')+1:]] if '--' in sys.argv else list(BUILD)
 for i in ids:run(next(x for x in INV if x['index']==i))



