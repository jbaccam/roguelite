"""Additional modular terrain assets, preserving the approved v2 kit."""
import bpy, math, json, shutil, hashlib, random
from pathlib import Path
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
ROOT=Path(__file__).resolve().parent
for d in ('textures','previews','exports/glb','exports/fbx'): (ROOT/d).mkdir(parents=True,exist_ok=True)
V2=ROOT.parent/'blender-cliff-pillars-v2'
# Reuse the exact approved source material setup without running the v2 model generator.
source=(V2/'generate_pillars.py').read_text()
setup=source[source.index('SOURCES='):source.index('def outline')]
exec(setup)

def dense(poly,spacing=2):
    out=[]
    for i,a in enumerate(poly):
        b=poly[(i+1)%len(poly)];n=max(1,round(math.dist(a,b)/spacing))
        out.extend([(a[0]+(b[0]-a[0])*j/n,a[1]+(b[1]-a[1])*j/n) for j in range(n)])
    return out

def box(w,d,curve=0):
    pts=[]
    # CCW perimeter; negative Y is the intended arena-facing side.
    c=min(1.1,d*.15)
    for x,y in [(-w/2+c,-d/2),(w/2-c,-d/2),(w/2,-d/2+c),(w/2,d/2-c),(w/2-c,d/2),(-w/2+c,d/2),(-w/2,d/2-c),(-w/2,-d/2+c)]:pts.append((x,y))
    return [(x,y+curve*(1-(x/(w/2))**2)) for x,y in dense(pts)]

def prism(name,poly,h,grass=True,seed=0,taper=.95,overhang=.035,heightfn=None):
    poly=[(x+.10*math.sin(y*.6+seed),y+.12*math.sin(x*.5+seed)) for x,y in poly]
    n=len(poly);verts=[];faces=[];uvs=[];roles=[];rockuvs=[];blends=[]
    heightfn=heightfn or (lambda x,y:h)
    rim=min(1.65,h*.27) if grass else 0
    levels=max(3,math.ceil(h/2.6));fractions=[i/levels for i in range(levels+1)]
    rings=[(t,False) for t in fractions]+([(0.48,True),(.92,True),(1,True)] if grass else [])
    def topz(x,y):return heightfn(x,y)+.10*math.sin(x*.45+seed)*math.cos(y*.6)
    for k,(t,isrim) in enumerate(rings):
        for i,(x,y) in enumerate(poly):
            hh=topz(x,y);z=(hh-rim)*t if not isrim else hh-rim+rim*t
            s=taper+(1-taper)*t+.012*math.sin(t*math.pi) if not isrim else 1+overhang*math.sin(t*math.pi*.75)
            if k==0:z=0
            verts.append((x*s+.07*math.sin(z*.3+seed),y*s,z))
    arc=[0]
    for i in range(n):arc.append(arc[-1]+math.dist(poly[i],poly[(i+1)%n]))
    def add(ids,role,tex,rock=None,blend=None):
        faces.append(ids);roles.append(role);uvs.append(tex);rockuvs.append(rock or tex);blends.append(blend or [0]*len(ids))
    for k in range(len(rings)-1):
        rimface=grass and k>=levels
        for i in range(n):
            j=(i+1)%n;ids=(k*n+i,k*n+j,(k+1)*n+j,(k+1)*n+i);tex=[];rock=[];weights=[]
            for q,u in zip(ids,[arc[i]/10.5,arc[i+1]/10.5,arc[i+1]/10.5,arc[i]/10.5]):
                ii=q%n;hh=topz(*poly[ii]);z=verts[q][2];base=hh-rim
                rv=(z-base)/10.5+.38;rock.append((u,rv))
                if rimface:
                    f=max(0,min(1,(z-base)/rim));tex.append((u,.38+.60*f));w=max(0,min(1,f/.55));weights.append(w*w*(3-2*w))
                else:tex.append((u,rv));weights.append(0)
            add(ids,2 if rimface else 0,tex,rock,weights)
    outer=(len(rings)-1)*n
    # Tessellate the concave footprints correctly; subdivide each top triangle for small surface variation.
    boundary=[Vector(verts[outer+i]) for i in range(n)]
    for tri in tessellate_polygon([boundary]):
        ids=[outer+(v if isinstance(v,int) else min(range(n),key=lambda i:(boundary[i]-v).length_squared)) for v in tri]
        center=sum((Vector(verts[q]) for q in ids),Vector())/3;center.z+=.035*math.sin(center.x*.4+seed)
        ci=len(verts);verts.append(tuple(center))
        for a,b in zip(ids,ids[1:]+ids[:1]):
            f=(a,b,ci);add(f,1 if grass else 0,[(verts[q][0]/(9 if grass else 10.5),verts[q][1]/(9 if grass else 10.5)) for q in f])
    for tri in tessellate_polygon([[Vector(verts[i]) for i in range(n)]]):
        ids=tuple(reversed([v if isinstance(v,int) else min(range(n),key=lambda i:(Vector(verts[i])-v).length_squared) for v in tri]));add(ids,0,[(verts[q][0]/10.5,verts[q][1]/10.5) for q in ids])
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    for m in materials:mesh.materials.append(m)
    uv=mesh.uv_layers.new(name='UVMap');ru=mesh.uv_layers.new(name='RockUV');bu=mesh.uv_layers.new(name='BlendUV')
    for p,role,coords,rcoords,weights in zip(mesh.polygons,roles,uvs,rockuvs,blends):
        p.material_index=role;p.use_smooth=True
        for li,co,rc,w in zip(p.loop_indices,coords,rcoords,weights):uv.data[li].uv=co;ru.data[li].uv=rc;bu.data[li].uv=(w,0)
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);return obj

def boulder(name,w,d,h,seed):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1);obj=bpy.context.object;obj.name=name
    for v in obj.data.vertices:
        x,y,z=v.co;factor=1+.10*math.sin(x*8+y*5+seed)+.05*math.cos(z*8+seed)
        v.co=(math.copysign(abs(x)**.8,x)*w*.5*factor+.12*w*z,math.copysign(abs(y)**.85,y)*d*.5*factor,max(0,(z+1)*h*.5*factor))
    minz=min(v.co.z for v in obj.data.vertices)
    for v in obj.data.vertices:v.co.z-=minz
    obj.data.materials.append(materials[0]);obj.data.update();uv=obj.data.uv_layers.new(name='UVMap')
    obj.data.uv_layers.new(name='RockUV');obj.data.uv_layers.new(name='BlendUV')
    for p in obj.data.polygons:
        p.use_smooth=True;normal=p.normal;axis=max(range(3),key=lambda i:abs(normal[i]))
        for li in p.loop_indices:
            co=obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv.data[li].uv=((co.y if axis==0 else co.x)/10.5,(co.y if axis==2 else co.z)/10.5)
    return obj

def combine(name,parts):
    bpy.ops.object.select_all(action='DESELECT')
    for obj,loc in parts:obj.location=loc;obj.select_set(True)
    bpy.context.view_layer.objects.active=parts[0][0];bpy.ops.object.join();obj=bpy.context.object;obj.name=name
    bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.ops.object.transform_apply(location=False,rotation=True,scale=True);return obj

groups={'Grassy_Walls':[],'Exposed_Rock':[],'Scatter_and_Fillers':[],'Special_Modules':[]};notes={}
def register(group,name,obj,note):groups[group].append(obj);notes[name]=note;return obj
def wall(name,poly,h,group='Grassy_Walls',grass=True,note='',**kw):return register(group,name,prism(name,poly,h,grass,seed=len(notes)+1,**kw),note)
wall('Long_Grass_Wall',box(26,7),10,note='Straight front; overlap ends 1–2 units.')
wall('Concave_Grass_Wall',box(24,7,3.4),10,note='Arena-facing negative-Y side curves inward.')
wall('Convex_Grass_Wall',box(24,7,-3.4),10,note='Arena-facing negative-Y side bulges outward.')
corner=dense([(-11,-4),(4,-4),(5,11),(-2,12),(-3,3),(-11,3)])
wall('Inward_Grass_Corner',corner,10,note='Organic L corner; rotate to fit perimeter.')
wall('Outward_Grass_Corner',[(-x,y) for x,y in reversed(corner)],11,note='Mirrored outward corner with asymmetric arms.')
wall('Sloped_Height_Wall',box(24,8),12,heightfn=lambda x,y:8.5+x/24*7,note='Smooth top grade from 5 to 12; preserve scale when connecting.')
register('Grassy_Walls','Stepped_Height_Wall',combine('Stepped_Height_Wall',[(prism('StepLow',box(12,8),6,True,12),(-6,0,0)),(prism('StepHigh',box(12,8),11,True,13),(5,0,0))]),'Two levels with one-unit overlap; step is not a walking ramp.')
wall('Broad_Grass_Platform',dense([(-13,-8),(10,-8),(14,-3),(12,8),(-8,9),(-14,3)]),5.8,note='Broad irregular platform for several props.')
wall('Moderate_Overhang_Wall',box(22,8),10,overhang=.07,taper=.92,note='Grass lip expands moderately, around 0.6 unit per side.')
for name,poly in [('Exposed_Long_Wall',box(26,7)),('Exposed_Concave_Wall',box(24,7,3.4)),('Exposed_Convex_Wall',box(24,7,-3.4)),('Exposed_Organic_Corner',corner)]:wall(name,poly,12,'Exposed_Rock',False,'Exposed rock only; no grass cap.')
wall('Vertical_Buttress',dense([(-4,-5),(3,-5),(5,-1),(3,4),(-3,4),(-5,0)]),19,'Exposed_Rock',False,'Narrow wall support for breaking long wall repetition.',taper=.87,heightfn=lambda x,y:18+.7*math.sin(x*.6))
wall('Eroded_Notch_Wall',dense([(-13,-4),(-5,-4),(-3,0),(2,1),(5,-4),(13,-4),(13,4),(-13,4)]),11,'Exposed_Rock',False,'Broad wall with broken inward notch.',heightfn=lambda x,y:11-3*math.exp(-x*x/13))
wall('Low_Base_Filler',dense([(-12,-4),(-5,-5),(6,-4),(12,-2),(11,3),(-10,3)]),3,'Scatter_and_Fillers',False,'Low broad exposed rock to conceal seams and wall bases.',heightfn=lambda x,y:2.8+.5*math.sin(x*.4))
for name,w,d,h,seed in [('Small_Boulder',3.5,2.8,2.3,1),('Medium_Boulder',6,4.4,3.9,2),('Large_Boulder',9,6.8,5.8,3),('Standing_Rock',4.5,3.8,8.5,4)]:register('Scatter_and_Fillers',name,boulder(name,w,d,h,seed),'Standalone exposed rock; base at Z=0.')
register('Scatter_and_Fillers','Four_Rock_Cluster',combine('Four_Rock_Cluster',[(boulder('ClusterA',5,4,4,8),(-2,0,0)),(boulder('ClusterB',4,3,2.8,9),(2,1,0)),(boulder('ClusterC',3,2.5,2,10),(1,-2,0)),(boulder('ClusterD',2.8,2,1.7,11),(-3,-2,0))]),'Four joined disconnected rock shells for quick dressing.')
register('Scatter_and_Fillers','Broken_Rubble',combine('Broken_Rubble',[(boulder('Debris'+str(i),2.5+(i%2),1.8,1.2+.3*(i%3),20+i),((i-3)*1.7,math.sin(i*2)*1.4,0)) for i in range(7)]),'Seven broken stones in one mesh; for cliff/ground junctions.')
register('Special_Modules','Shelf_Wall',combine('Shelf_Wall',[(prism('ShelfHigh',box(22,6),13,True,30),(0,2,0)),(prism('ShelfLow',box(13,8),6,True,31),(1,-3,0))]),'Integrated 13×8 lower grassy shelf; overlap into taller wall.')
register('Special_Modules','Tree_Shelf_Wall',combine('Tree_Shelf_Wall',[(prism('TreeWall',box(17,6),11,True,32),(0,2,0)),(prism('TreeShelf',box(8,8),6.5,True,33),(3,-3,0))]),'Lower 8×8 grassy shelf suitable for a pine tree prop.')
register('Special_Modules','Path_Cut_Through',combine('Path_Cut_Through',[(prism('PathLeft',box(9,10),10,True,35),(-8,0,0)),(prism('PathRight',box(9,10),7,True,36),(8,0,0))]),'Open central passage, approximately 6.5 units clear; add your own dirt path.')
wall('Distant_Mountain_Backdrop',dense([(-23,-7),(-11,-9),(4,-7),(24,-6),(22,9),(6,11),(-20,9)],3),33,'Special_Modules',False,'Distant exposed mountain wall; same nominal source texture scale.',taper=.88,heightfn=lambda x,y:27+5*math.sin(x*.14)+3*math.cos(x*.29))

# Temporary image blend and color bake match the approved v2 method.
blend=source[source.index('nodes=materials[2]'):source.index('scene=bpy.context.scene;scene.render.engine=\'CYCLES\'')]
exec(blend)
objects=[o for vals in groups.values() for o in vals]
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=1
for obj in objects:
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    atlasuv=obj.data.uv_layers.new(name='AtlasUV');obj.data.uv_layers.active=atlasuv;atlasuv.active_render=True
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.018);bpy.ops.object.mode_set(mode='OBJECT')
    size=4096 if obj.name=='Distant_Mountain_Backdrop' else 2048
    atlas=bpy.data.images.new(obj.name+'_Color',width=size,height=size,alpha=False);atlas.filepath_raw=str(ROOT/'textures'/(obj.name.lower()+'-atlas.png'));atlas.file_format='PNG'
    for mat in obj.data.materials:
        node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=atlas;mat.node_tree.nodes.active=node
    bpy.ops.object.bake(type='DIFFUSE',pass_filter={'COLOR'},margin=16,use_clear=True);atlas.save()
    m=bpy.data.materials.new(obj.name+'_Atlas');m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.85;bs.inputs['Metallic'].default_value=0;bs.inputs['Specular IOR Level'].default_value=.12
    tx=m.node_tree.nodes.new('ShaderNodeTexImage');tx.image=atlas;m.node_tree.links.new(tx.outputs['Color'],bs.inputs['Base Color'])
    obj.data.materials.clear();obj.data.materials.append(m)
    for p in obj.data.polygons:p.material_index=0
    for layer in list(obj.data.uv_layers):
        if layer.name!='AtlasUV':obj.data.uv_layers.remove(layer)
    print('ATLAS_READY',obj.name,flush=True)

scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=2000;scene.render.resolution_y=1400;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
scene.world=bpy.data.worlds.new('PreviewWorld') if not scene.world else scene.world;scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.55,.65,.8,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65;scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
bpy.ops.mesh.primitive_plane_add(size=600,location=(0,0,-.06));ground=bpy.context.object;ground.name='Preview_Ground';mat=bpy.data.materials.new('PreviewGround');mat.use_nodes=True;mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.075,.105,.13,1);mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=1;ground.data.materials.append(mat)
bpy.ops.object.light_add(type='SUN');bpy.context.object.data.energy=1.5;bpy.context.object.rotation_euler=(.35,-.4,-.4);bpy.context.object.data.angle=.3
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam
labels=[]
labelmat=bpy.data.materials.new('PreviewLabel');labelmat.use_nodes=True;labelmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.8,.9,1,1)
def label(text,loc):
    bpy.ops.object.text_add(location=loc,rotation=(0,0,0));o=bpy.context.object;o.name='Label_'+text;o.data.body=text.replace('_',' ');o.data.align_x='CENTER';o.data.size=1.15;o.data.materials.append(labelmat);labels.append(o)
def render(name,target,scale):
    cam.location=Vector(target)+Vector((12,-68,75));cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;scene.render.filepath=str(ROOT/'previews'/name);bpy.ops.render.render(write_still=True)
for group,objs in groups.items():
    for o in objects:o.hide_render=o not in objs
    for o in labels:o.hide_render=True
    for i,o in enumerate(objs):
        o.location=((i%3-1)*36,(i//3)*32,0);label(o.name,(o.location.x,o.location.y-10,.03))
    target=(0,(math.ceil(len(objs)/3)-1)*16,5)
    render(group.lower()+'.png',target,130 if group!='Special_Modules' else 140)
    print('PREVIEW_READY',group,flush=True)
for o in labels:o.hide_render=True
for o in objects:o.hide_render=True
report={'blender_version':bpy.app.version_string,'modules':{}}
for group,objs in groups.items():
    for i,obj in enumerate(objs):
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj;obj.location=(0,0,0);obj.hide_render=False
        stem=obj.name.lower().replace('_','-');obj.data.calc_loop_triangles()
        obj.data.name=obj.name
        bpy.ops.export_scene.gltf(filepath=str(ROOT/'exports/glb'/f'{stem}.glb'),export_format='GLB',use_selection=True,export_apply=True)
        bpy.ops.export_scene.fbx(filepath=str(ROOT/'exports/fbx'/f'{stem}.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True,add_leaf_bones=False)
        report['modules'][obj.name]={'file_stem':stem,'group':group,'triangles':len(obj.data.loop_triangles),'vertices':len(obj.data.vertices),'materials':1,'atlas_size':4096 if obj.name=='Distant_Mountain_Backdrop' else 2048,'dimensions':list(obj.dimensions),'usage':notes[obj.name]}
        obj.hide_render=True
(ROOT/'polygon-report.json').write_text(json.dumps(report,indent=2))
for gi,(group,objs) in enumerate(groups.items()):
    for i,o in enumerate(objs):o.location=((i%3-1)*36,(i//3)*26+gi*100,0);o.hide_render=False
for lab in labels:
    target=bpy.data.objects.get(lab.name.removeprefix('Label_'))
    if target:lab.location=target.location+Vector((0,-10,.03));lab.hide_render=False
for im in bpy.data.images:
    if im.source=='FILE':im.pack()
cam.location=(70,-130,140);cam.rotation_euler=(Vector((0,120,8))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=330
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'modular-cliff-expansion.blend'))
print('EXPANSION_READY',len(objects),ROOT,flush=True)
