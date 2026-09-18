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
def pan():
 n=16;levels=[(1.18,.0),(1.29,.06),(1.43,.42),(1.41,.47),(1.33,.46),(1.21,.16),(1.13,.12)]
 v=[(r*math.cos(TAU*i/n),r*math.sin(TAU*i/n),z) for r,z in levels for i in range(n)];f=[tuple(range(n-1,-1,-1))]
 for j in range(len(levels)-1):
  for i in range(n):f.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
 f.append(tuple(range((len(levels)-1)*n,len(levels)*n)));mesh('Cast iron pan with sloped interior and thick rim',v,f,iron)
 neck=box('Flattened iron handle tang',(1.62,0,.40),(.58,.30,.19),steel,.04)
 grip=prism('Tapered wooden handle',[(1.94,.34),(3.29,.23),(3.50,.33),(3.56,.55),(3.42,.71),(2.1,.60)],.45,wood,.055)
 # Handle profile faces upward; Y thickness becomes Z and Z becomes Y.
 for vert in grip.data.vertices:vert.co=(vert.co.x,vert.co.z-.47,vert.co.y+.47)
 cutter=cylinder('hanging hole cutter',(3.28,0,-1),(3.28,0,2),.115,dark,8);cut(grip,cutter)
 collar=box('Iron octagonal ferrule',(2.0,0,.47),(.21,.52,.31),steel,.065)
 for x,y,l in [(-.6,-.1,.4),(.25,.3,.26),(.5,-.6,.18)]:
  o=box('Subtle cooking surface scratch',(x,y,.1206),(l,.007,.001),scratch,0);o.rotation_euler.z=.45
 for o in list(asset.objects):
  if any(s in o.name for s in ['handle','ferrule']):
   for vert in o.data.vertices:
    co=o.matrix_world@vert.co;co.x=1.4+(co.x-1.4)*.80;vert.co=o.matrix_world.inverted()@co
 return (-3.5,-5,6),(.68,0,.22),4.7
def nunchucks():
 for j,ang in enumerate([.22,-.22]):
  before=set(asset.objects)
  lathe('Wood baton '+str(j),[(0,.17),(.055,.24),(.16,.26),(2.10,.25),(2.20,.21)],wood,12)
  for z in [.38,.69]:lathe('Dark grip metal band',[(z,.26),(z+.025,.275),(z+.18,.275),(z+.205,.26)],iron,12)
  cap=lathe('Beveled slotted chain ferrule',[(2.12,.265),(2.17,.29),(2.52,.29),(2.58,.25)],steel,12)
  for k in range(8):
   a=TAU*k/8;o=box('Ferrule channel cutter',(.277*math.sin(a),-.277*math.cos(a),2.35),(.055,.06,.22),dark,.009);o.rotation_euler.z=a;bpy.context.view_layer.update();cut(cap,o)
  link('Terminal chain eye',(0,0,2.64),0,math.pi/2,w=.26,h=.33)
  transform(set(asset.objects)-before,ang,(-.97 if j==0 else .97,0,.02))
 # Chain arches above the two terminal eyes.
 for i,(x,z,ang) in enumerate([(-.40,2.88,.50),(-.21,3.06,.84),(0,3.13,1.56),(.23,3.05,-.84),(.41,2.87,-.50)]):link('Interlocked chain link '+str(i),(x,0,z),ang,math.pi/2 if i%2 else 0,w=.28,h=.43)
 return (3,-11,5),(0,0,1.63),4.05
def blade(name,sections,m):
 # Each cross section has narrow bright cutting bevels and a broad darker facet.
 v=[]
 for x,z,w in sections:v.extend([(x-w/2,0,z),(x-w*.30,-.055,z),(x+w*.37,-.055,z),(x+w/2,0,z),(x+w*.37,.055,z),(x-w*.30,.055,z)])
 n=6;f=[tuple(range(n-1,-1,-1)),tuple(range((len(sections)-1)*n,len(sections)*n))]
 for j in range(len(sections)-1):
  for i in range(n):f.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
 o=mesh(name,v,f,m);o.data.materials.append(edge)
 for p in o.data.polygons:
  if p.index>=2 and (p.index-2)%6 in [0,2,3,5]:p.material_index=1
 return o
def katana():
 # Build upright, then rake to match the reference's upper-left tip / lower-right grip.
 lathe('Black wrapped katana handle',[(0,.145),(1.16,.145)],leather,8)
 for z in [.08,1.08]:lathe('Black end collar',[(z,.16),(z+.09,.16)],leather,8)
 strap('Continuous diagonal black grip binding',.12,.151,.155,6.1)
 for i in range(5):
  z=.25+i*.17
  for side in [-1,1]:
   prism('Ivory diamond exposed between bindings',[(-.070,z),(0,z-.075),(.070,z),(0,z+.075)],.009,ivory,.003,y=side*.177)
 lathe('Octagonal pommel',[(0,.15),(.04,.19),(.15,.19),(.18,.16)],steel,8)
 lathe('Wide octagonal tsuba',[(1.18,.27),(1.22,.31),(1.31,.31),(1.34,.27)],iron,8)
 box('Brass habaki blade collar',(0,0,1.43),(.29,.19,.24),brass,.025)
 blade('Curved single edged katana blade',[(0,1.52,.26),(.02,1.95,.26),(.08,2.4,.26),(.17,2.85,.25),(.29,3.30,.24),(.46,3.72,.22),(.65,4.08,.20),(.81,4.35,.015)],silver)
 transform(list(asset.objects),-.97,(1.40,0,.20));return (1.4,-10,3.7),(-.10,0,1.68),4.9
def kusarigama():
 before=set(asset.objects)
 lathe('Wood sickle shaft',[(0,.14),(.05,.18),(2.10,.18),(2.16,.14)],wood,10)
 lathe('Sickle lower socket ferrule',[(0,.19),(.04,.23),(.22,.23),(.25,.19)],steel,8)
 box('Square blade mounting socket',(0,0,2.22),(.42,.43,.45),steel,.04)
 for z in [.75,1.01,1.27]:
  n=12;v=[(r*math.cos(TAU*i/n),r*math.sin(TAU*i/n),z+dz+.07*math.cos(TAU*i/n)) for r,dz in [(.181,-.085),(.205,-.085),(.205,.085),(.181,.085)] for i in range(n)];f=[]
  for j in range(4):
   for i in range(n):f.append((j*n+i,j*n+(i+1)%n,((j+1)%4)*n+(i+1)%n,((j+1)%4)*n+i))
  mesh('Closed angled black hand wrap',v,f,leather)
 # Sweep blade across negative X with widening arc and bright edge bands.
 secs=[(0,2.22,.38),(-.34,2.33,.40),(-.68,2.33,.42),(-1.02,2.23,.40),(-1.32,2.08,.34),(-1.58,1.87,.23),(-1.77,1.62,.005)]
 # Custom strips with vertical width and varying y thickness.
 v=[]
 for x,z,w in secs:v.extend([(x,0,z-w/2),(x,-.07,z-w*.27),(x,-.07,z+w*.28),(x,0,z+w/2),(x,.07,z+w*.28),(x,.07,z-w*.27)])
 f=[tuple(range(5,-1,-1)),tuple(range((len(secs)-1)*6,len(secs)*6))]
 for j in range(len(secs)-1):
  for k in range(6):f.append((j*6+k,j*6+(k+1)%6,(j+1)*6+(k+1)%6,(j+1)*6+k))
 o=mesh('Curved sickle blade with cutting bevel',v,f,steel);o.data.materials.append(edge)
 for p in o.data.polygons:
  if p.index>=2 and (p.index-2)%6 in [0,2,3,5]:p.material_index=1
 cylinder('Large octagonal blade rivet',(0,-.26,2.20),(0,-.30,2.20),.075,steel,8)
 transform(set(asset.objects)-before,.27,(-.50,0,1.05))
 path=[(-.51,1.01),(-.42,.75),(-.22,.52),(.07,.38),(.38,.34),(.67,.41),(.92,.62),(1.10,.88),(1.33,1.13),(1.58,1.25),(1.80,1.08)]
 for i,(x,z) in enumerate(path):
  a=Vector(path[max(0,i-1)]);b=Vector(path[min(len(path)-1,i+1)]);d=b-a;ang=math.atan2(d.x,d.y)
  link('Sickle interlocked chain '+str(i),(x,0,z),ang,math.pi/2 if i%2 else 0,w=.26,h=.40)
 cylinder('Weight attachment collar',(1.85,0,.94),(1.99,0,.78),.19,steel,8)
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1);temp=bpy.context.object
 points=[p.center.normalized()*.45 for p in temp.data.polygons];faces=[]
 for vert in temp.data.vertices:
  normal=vert.co.normalized();u=normal.cross(Vector((0,0,1)))
  if u.length<.01:u=normal.cross(Vector((1,0,0)))
  u.normalize();v=normal.cross(u);ids=[p.index for p in temp.data.polygons if vert.index in p.vertices];ids.sort(key=lambda i:math.atan2(points[i].dot(v),points[i].dot(u)));faces.append(tuple(ids))
 bpy.data.objects.remove(temp,do_unlink=True);mesh('Beveled twelve-facet iron chain weight',[p+Vector((2.13,0,.49)) for p in points],faces,iron,.025)
 return (2,-11,4.6),(.35,0,1.85),4.8
def spatula():
 grip=prism('Wooden hanging grip',[(-.23,.08),(-.29,.19),(-.26,1.49),(-.19,1.59),(.19,1.59),(.26,1.49),(.29,.19),(.23,.08)],.22,wood,.045);hole(grip,0,.32,.105)
 cylinder('Handle rivet',(0,-.13,1.38),(0,-.16,1.38),.075,steel,8)
 box('Handle steel collar',(0,0,1.61),(.49,.29,.09),steel,.018)
 prism('Bent steel neck',[(-.13,1.63),(-.13,2.18),(-.24,2.32),(.24,2.32),(.13,2.18),(.13,1.63)],.12,silver,.02)
 head=prism('Three slot spatula head',[(-.46,2.23),(-.58,2.40),(-.62,3.67),(-.55,3.78),(.55,3.78),(.62,3.67),(.58,2.40),(.46,2.23)],.13,silver,.045)
 for x in [-.30,0,.30]:
  cutter=prism('Slot cutter',[(x-.065,2.58),(x-.065,3.49),(x-.038,3.54),(x+.038,3.54),(x+.065,3.49),(x+.065,2.58),(x+.038,2.54),(x-.038,2.54)],1,dark,0);cut(head,cutter)
 bpy.context.view_layer.objects.active=head;mod=head.modifiers.new('Slot opening chamfers','BEVEL');mod.width=.014;mod.segments=1;bpy.ops.object.modifier_apply(modifier=mod.name)
 transform(list(asset.objects),-.29,(.65,0,0));return (2,-12,5),(.1,0,1.90),4.5
def bat():
 o=lathe('Tapered faceted ash baseball bat',[(0,.17),(.055,.22),(.14,.22),(.19,.15),(.35,.12),(1.04,.13),(1.30,.16),(1.65,.22),(2.05,.28),(2.55,.34),(3.15,.38),(3.40,.38),(3.49,.34),(3.53,.25)],batwood,12)
 strap('Spiral black leather grip',.24,.14,.13,6.3)
 # Narrow angular wood scars carried as shallow colored inset shapes.
 for x,z,h in [(-.12,1.65,.23),(.10,2.4,.31),(-.10,2.93,.22)]:
  radius=.22+(z-1.65)*.10;prism('Long angular wood scar',[(x,z),(x+.034,z+h*.6),(x+.015,z+h),(x-.016,z+h*.35)],.006,wooddark,0,y=-radius)
 transform(list(asset.objects),.66,(-1.0,0,.11));return (2,-11,4.5),(.15,0,1.54),4.35
def shovel():
 # Blade's closed shell is explicitly cupped, with a central folded reinforcing ridge.
 outline=[(-.55,1.40),(-.59,.68),(-.44,.31),(0,.03),(.44,.31),(.59,.68),(.55,1.40)]
 v=[(x,.015,z) for x,z in outline]+[(x,-.045,z) for x,z in outline]+[(x*.84,-.13,.72+(z-.72)*.84) for x,z in outline]+[(0,-.22,.61)];n=7;f=[]
 # Broad explicit perimeter chamfer frames the cupped face and its central crease.
 for i in range(n):
  j=(i+1)%n;f.extend([(7+i,7+j,14+j,14+i),(14+i,14+j,21)])
 f += [tuple(range(n-1,-1,-1))]+[(i,(i+1)%n,7+(i+1)%n,7+i) for i in range(n)]
 mesh('Cupped pointed steel shovel blade',v,f,silver,.008)
 prism('Central blade reinforcing ridge',[(-.13,1.40),(0,.55),(.13,1.40)],.19,steel,.008,y=-.13)
 lathe('Wood octagonal shovel shaft',[(1.43,.135),(3.26,.135)],batwood,8)
 lathe('Steel shaft socket',[(1.33,.15),(1.38,.18),(1.67,.18),(1.71,.14)],steel,8)
 cylinder('Socket rivet',(0,-.175,1.53),(0,-.22,1.53),.054,edge,8)
 outer=[(-.13,3.11),(-.39,3.32),(-.43,3.83),(.43,3.83),(.39,3.32),(.13,3.11)]
 inner=[(-.08,3.32),(-.26,3.43),(-.28,3.68),(.28,3.68),(.26,3.43),(.08,3.32)]
 ring('Open wooden D handle',outer,inner,.19,batwood,.024)
 box('Dark grip across shovel handle',(0,0,3.76),(.59,.24,.21),iron,.025)
 transform(list(asset.objects),.24,(-.43,0,.04));return (2,-12,5),(.0,0,1.92),4.45
BUILD={1:pan,2:nunchucks,3:katana,4:kusarigama,5:spatula,6:bat,26:shovel}
def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
def run(item):
 global asset,iron,steel,dark,wood,batwood,wooddark,leather,silver,edge,brass,ivory,scratch
 random.seed(item['index']);bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 scene=bpy.context.scene;asset=bpy.data.collections.new(item['name']+' | Export geometry');scene.collection.children.link(asset)
 iron=mat('Charcoal cast iron',(.185,.175,.166));steel=mat('Dark gray steel',(.26,.25,.24));dark=mat('Recessed dark steel',(.10,.095,.09),False);wood=mat('Warm walnut wood',(.40,.245,.135),True,True);batwood=mat('Honey ash wood',(.57,.375,.185),True,True);wooddark=mat('Dark grain scar',(.29,.20,.12),False);leather=mat('Charcoal leather',(.16,.15,.14));silver=mat('Faceted warm gray blade',(.44,.43,.42));edge=mat('Pale blade bevel',(.62,.61,.58));brass=mat('Warm brass collar',(.58,.45,.23));ivory=mat('Warm ivory ray skin',(.57,.51,.41));scratch=mat('Subtle worn iron',(.25,.23,.20),False)
 loc,target,scale=BUILD[item['index']]();out=Path(item['output']);out.mkdir(parents=True,exist_ok=True);shutil.copyfile(item['source'],out/'Reference.png')
 # Merge geometry into one portable asset mesh, preserving named parts as vertex groups.
 obs=list(asset.objects);bpy.ops.object.select_all(action='DESELECT')
 for o in obs:
  group=o.vertex_groups.new(name=o.name);group.add(list(range(len(o.data.vertices))),1,'REPLACE');o.select_set(True)
 bpy.context.view_layer.objects.active=obs[0];bpy.ops.object.join();o=bpy.context.object;o.name=item['name'].replace(' ','_');bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
 bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.remove_doubles(threshold=.00001);bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.uv.smart_project(angle_limit=math.radians(60),island_margin=.012);bpy.ops.object.mode_set(mode='OBJECT')
 atlas=bpy.data.images.new(item['slug']+'_BaseColor',width=1024,height=1024,alpha=False);atlas.colorspace_settings.name='sRGB';scene.render.engine='CYCLES';scene.cycles.samples=1;scene.render.bake.margin=6
 for m in o.data.materials:
  nt=m.node_tree;bs=nt.nodes.get('Principled BSDF');em=nt.nodes.new('ShaderNodeEmission');inp=bs.inputs['Base Color']
  if inp.is_linked:nt.links.new(inp.links[0].from_socket,em.inputs['Color'])
  else:em.inputs['Color'].default_value=inp.default_value
  nt.links.new(em.outputs[0],nt.nodes.get('Material Output').inputs['Surface']);tex=nt.nodes.new('ShaderNodeTexImage');tex.image=atlas;nt.nodes.active=tex
 bpy.ops.object.bake(type='EMIT');atlas.filepath_raw=str(out/'BaseColor.png');atlas.file_format='PNG';atlas.save();atlas.pack()
 final=mat(item['name']+' | portable baked base color',(.5,.5,.5),False);tex=final.node_tree.nodes.new('ShaderNodeTexImage');tex.image=atlas;final.node_tree.links.new(tex.outputs['Color'],final.node_tree.nodes.get('Principled BSDF').inputs['Base Color']);o.data.materials.clear();o.data.materials.append(final)
 for p in o.data.polygons:p.material_index=0;p.use_smooth=False
 pivots={1:(2.30,0,.47),2:(.708,0,1.19),3:(.864,0,.567),4:(-.193,0,2.159),5:(.393,0,.863),6:(-.601,0,.623),26:(.164,0,2.468)}
 scene.cursor.location=pivots[item['index']];bpy.ops.object.origin_set(type='ORIGIN_CURSOR');o['source_reference']=str(out/'Reference.png');o['geometry_notes']='Closed low-poly components; intentional overlapping assemblies. No rig. Not Studio-tested.';o['pivot']='Handhold center'
 bpy.ops.export_scene.fbx(filepath=str(out/'Model.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
 bpy.ops.export_scene.gltf(filepath=str(out/'Model.glb'),use_selection=True,export_format='GLB',export_animations=False)
 stage=bpy.data.collections.new('REVIEW | not exported');scene.collection.children.link(stage)
 floor=mat('Neutral review floor',(.48,.48,.48),False);bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.04));ground=bpy.context.object;ground.name='Review floor';ground.data.materials.append(floor);move(ground,stage)
 for pos,power,size in [((-4,-6,8),950,6),((5,-4,6),700,5),((1,5,8),1200,5)]:
  bpy.ops.object.light_add(type='AREA',location=pos);a=bpy.context.object;a.data.energy=power;a.data.shape='DISK';a.data.size=size;aim(a,target);move(a,stage)
 scene.world.use_nodes=True;scene.world.node_tree.nodes.get('Background').inputs[0].default_value=(.4,.4,.4,1);scene.world.node_tree.nodes.get('Background').inputs[1].default_value=.6
 bpy.ops.object.camera_add(location=loc);cam=bpy.context.object;cam.name='Reference comparison camera';cam.data.type='ORTHO';cam.data.ortho_scale=scale;aim(cam,target);move(cam,stage);scene.camera=cam
 scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.shading.type='MATERIAL'
 scene.render.filepath=str(out/'Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'));bpy.ops.render.render(write_still=True)
 cam.location=(-loc[0],-loc[1],loc[2]);aim(cam,target);scene.render.filepath=str(out/'Alternate.png');bpy.ops.render.render(write_still=True);cam.location=loc;aim(cam,target);scene.render.filepath=str(out/'Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
 bm=bmesh.new();bm.from_mesh(o.data);stats={'index':item['index'],'name':item['name'],'vertices':len(o.data.vertices),'triangles':sum(len(p.vertices)-2 for p in o.data.polygons),'mesh_objects':1,'materials':1,'uv_layers':len(o.data.uv_layers),'texture':'1024x1024 packed base color','nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'loose_vertices':sum(not v.link_edges for v in bm.verts),'zero_area_faces':sum(f.calc_area()<1e-10 for f in bm.faces),'bounds':list(o.dimensions),'notes':'Intentional component intersections; mirrored/extrapolated unseen surfaces. Static prop; no rig or gameplay. Roblox import not tested.'};bm.free()
 # Reimport each export into a fresh scene to verify mesh counts, triangles and textures.
 for ext in ['glb','fbx']:
  bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
  if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
  else:bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
  imported=[x for x in bpy.context.scene.objects if x.type=='MESH'];stats[ext+'_reimport']={'mesh_objects':len(imported),'triangles':sum(len(p.vertices)-2 for x in imported for p in x.data.polygons),'has_uv':all(len(x.data.uv_layers)>0 for x in imported),'has_image_texture':all(any(n.type=='TEX_IMAGE' and n.image for m in x.data.materials if m and m.use_nodes for n in m.node_tree.nodes) for x in imported),'unexpected_stage_objects':sum(x.type!='MESH' for x in bpy.context.scene.objects)}
 (out/'validation.json').write_text(json.dumps(stats,indent=2));(out/'README.md').write_text('# '+item['name']+'\n\nReference-matched stylized static weapon prop. Generated by `../../batches/melee_tools/build_melee.py` (index '+str(item['index'])+'). The original source is copied as Reference.png. Model.blend is editable; named vertex groups identify assembled pieces. Model.fbx and Model.glb export only the asset, with one packed 1024px base-color atlas. Preview.png and Alternate.png are actual Blender renders.\n\nUnseen backs and thickness are conservatively inferred from the single reference. Components intentionally intersect where assembled. Chain pose is static; links remain identifiable by vertex groups. No rigging, Roblox import, or gameplay testing has been performed. See validation.json for measured topology and export reimport results.\n')
 print('ASSET_COMPLETE',json.dumps(stats),flush=True)
if __name__=='__main__':
 ids=[int(x) for x in sys.argv[sys.argv.index('--')+1:]] if '--' in sys.argv else list(BUILD)
 for i in ids:run(next(x for x in INV if x['index']==i))
