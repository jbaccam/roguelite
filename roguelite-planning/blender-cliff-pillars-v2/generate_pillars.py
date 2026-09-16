"""Astra cliff revision: run with Blender --background --python this_file.py."""
import bpy, math, json, shutil
from pathlib import Path
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
for d in ('textures','previews','exports/glb','exports/fbx'): (ROOT/d).mkdir(parents=True,exist_ok=True)
SOURCES={'rock':'ChatGPT Image Sep 16, 2026, 11_42_57 AM (1).png','grass':'ChatGPT Image Sep 16, 2026, 11_42_57 AM (2).png','transition':'ChatGPT Image Sep 16, 2026, 11_42_58 AM (3).png'}
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
materials=[]
for role,filename in SOURCES.items():
    dest=ROOT/'textures'/f'{role}.png'; shutil.copy2(Path('C:/Users/Jeremiah/Downloads')/filename,dest)
    m=bpy.data.materials.new('Cliff_'+role); m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Roughness'].default_value=.85;bs.inputs['Metallic'].default_value=0;bs.inputs['Specular IOR Level'].default_value=.12
    tx=m.node_tree.nodes.new('ShaderNodeTexImage');tx.image=bpy.data.images.load(str(dest));tx.extension='REPEAT';tx.interpolation='Linear'
    uvnode=m.node_tree.nodes.new('ShaderNodeUVMap');uvnode.uv_map='UVMap';m.node_tree.links.new(uvnode.outputs['UV'],tx.inputs['Vector'])
    m.node_tree.links.new(tx.outputs['Color'],bs.inputs['Base Color']); materials.append(m)

def outline(w,d,power,n,seed,unique=False):
    pts=[]
    for i in range(n):
        a=i*math.tau/n
        # Superellipse yields broad box faces with rounded, clipped corners.
        x=math.copysign(abs(math.cos(a))**(2/power),math.cos(a))*w/2
        y=math.copysign(abs(math.sin(a))**(2/power),math.sin(a))*d/2
        wobble=1+.025*math.sin(3*a+seed)+.016*math.sin(7*a+.7*seed)
        if unique: x+=.8*math.sin(2*a)+.65*math.cos(a)*math.sin(a); y*=1+.14*math.cos(a)
        pts.append((x*wobble,y*wobble))
    return pts

def build(name,w,d,h,power,n,seed,taper,curve,offset,unique=False):
    pts=outline(w,d,power,n,seed,unique); verts=[]; faces=[]; uvfaces=[]; roles=[]
    rim=min(1.65,h*.27); rocktop=h-rim
    # Modest horizontal subdivisions define bends without large triangular rock patches.
    levels=max(3,round(rocktop/2.5)); rings=[]
    for k in range(levels+1):
        t=k/levels; rings.append((rocktop*t,taper+(1-taper)*t+.022*math.sin(t*math.pi),0))
    rings.extend([(h-rim*.52,1.022,1),(h-.13,1.035,1),(h,1.012,1)])
    for z,s,role in rings:
        t=z/h; dx=curve*math.sin(t*math.pi*.85); dy=curve*.22*math.sin(t*math.pi*1.3)
        for i,(x,y) in enumerate(pts):
            a=i*math.tau/n; dz=(.095*math.sin(3*a+seed)+.055*math.cos(5*a))*(t**2)
            verts.append((x*s+dx,y*s+dy,z+dz))
    arcs=[0]
    for i in range(n):arcs.append(arcs[-1]+math.dist(pts[i],pts[(i+1)%n]))
    density=10.5
    def face(ids,uv,role):faces.append(ids);uvfaces.append(uv);roles.append(role)
    for k in range(len(rings)-1):
        isrim=k>=levels
        for i in range(n):
            j=(i+1)%n; ids=(k*n+i,k*n+j,(k+1)*n+j,(k+1)*n+i)
            if isrim:
                # Full grass/rock transition remains upright. Its dense top foliage is in upper V.
                v0=.38+(rings[k][0]-rocktop)/rim*.60;v1=.38+(rings[k+1][0]-rocktop)/rim*.60
                u0=arcs[i]/density;u1=arcs[i+1]/density
                role=2
            else:
                v0=(rings[k][0]-rocktop)/density+.38;v1=(rings[k+1][0]-rocktop)/density+.38;u0=arcs[i]/density;u1=arcs[i+1]/density;role=0
            face(ids,[(u0,v0),(u1,v0),(u1,v1),(u0,v1)],role)
    # Two internal rings create a clean, slightly rolling grass surface.
    outer=(len(rings)-1)*n
    for fraction in (.65,.30):
        start=len(verts)
        for i,(x,y) in enumerate(pts):
            xx=x*fraction+curve*math.sin(math.pi*.85); yy=y*fraction+curve*.22*math.sin(math.pi*1.3)
            zz=h+.14*(1-fraction)+.085*math.sin(xx*.45+seed)*math.cos(yy*.55)
            verts.append((xx,yy,zz))
        for i in range(n):
            j=(i+1)%n;ids=(outer+i,outer+j,start+j,start+i);face(ids,[(verts[q][0]/9,verts[q][1]/9) for q in ids],1)
        outer=start
    center=len(verts);verts.append((curve*math.sin(math.pi*.85),curve*.22*math.sin(math.pi*1.3),h+.17))
    for i in range(n):
        ids=(outer+i,outer+(i+1)%n,center);face(ids,[(verts[q][0]/9,verts[q][1]/9) for q in ids],1)
    face(tuple(reversed(range(n))),[(verts[q][0]/density,verts[q][1]/density) for q in reversed(range(n))],0)
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    for m in materials:mesh.materials.append(m)
    uv=mesh.uv_layers.new(name='UVMap')
    rockuv=mesh.uv_layers.new(name='RockUV');blenduv=mesh.uv_layers.new(name='BlendUV')
    for p,coords,role in zip(mesh.polygons,uvfaces,roles):
        p.material_index=role;p.use_smooth=True
        for li,co in zip(p.loop_indices,coords):uv.data[li].uv=co
        for li in p.loop_indices:
            vi=mesh.loops[li].vertex_index;z=verts[vi][2]
            if role==2:
                rockuv.data[li].uv=(uv.data[li].uv.x,(z-rocktop)/density+.38)
                weight=max(0,min(1,(z-rocktop)/(rim*.55)));weight=weight*weight*(3-2*weight)
                blenduv.data[li].uv=(weight,0)
    # Preserve the underside and grass edge break while smoothing small silhouette segments.
    for edge in mesh.edges:
        a,b=edge.vertices
        if (a//n==b//n and a//n in (0,levels,len(rings)-1)):edge.use_edge_sharp=True
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.location=offset
    obj['texture_roles']='rock: cliff sides; grass: top; transition: upper beveled rim'
    obj['base_width_ratio']=taper;obj['display_offset']=list(offset)
    return obj

specs=[('Short_Blocky',10,8,5.5,4.7,32,1,.94,.15,(-24,0,0),False),('Medium_Subtle_Taper',9,8.2,10,3.4,32,2,.84,.35,(-11,0,0),False),('Tall_Curved',8.5,7.4,17,4,36,3,.94,.9,(1,1,0),False),('Wide_Platform',18,11,4.4,4.2,40,4,.94,.18,(18,-1,0),False),('Shoulder_Cliff',13,8.5,11.5,2.8,36,5,.89,.55,(0,17,0),True)]
objects=[build(*s) for s in specs]
# Blend only the lower part of the supplied transition sheet into the supplied rock.
# Bake this temporary image-only composition, leaving one ordinary texture per game mesh.
nodes=materials[2].node_tree.nodes;links=materials[2].node_tree.links
bs=nodes.get('Principled BSDF');transition_tx=next(n for n in nodes if n.type=='TEX_IMAGE')
rock_tx=nodes.new('ShaderNodeTexImage');rock_tx.image=materials[0].node_tree.nodes.get('Image Texture').image
rock_uv=nodes.new('ShaderNodeUVMap');rock_uv.uv_map='RockUV';links.new(rock_uv.outputs['UV'],rock_tx.inputs['Vector'])
factor_uv=nodes.new('ShaderNodeUVMap');factor_uv.uv_map='BlendUV';sep=nodes.new('ShaderNodeSeparateXYZ');links.new(factor_uv.outputs['UV'],sep.inputs[0])
mix=nodes.new('ShaderNodeMixRGB');links.new(sep.outputs['X'],mix.inputs[0]);links.new(rock_tx.outputs['Color'],mix.inputs[1]);links.new(transition_tx.outputs['Color'],mix.inputs[2]);links.new(mix.outputs[0],bs.inputs['Base Color'])
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=1;scene.render.bake.use_pass_direct=False;scene.render.bake.use_pass_indirect=False
for obj in objects:
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    atlasuv=obj.data.uv_layers.new(name='AtlasUV');obj.data.uv_layers.active=atlasuv;atlasuv.active_render=True
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.025);bpy.ops.object.mode_set(mode='OBJECT')
    atlas=bpy.data.images.new(obj.name+'_Color',width=2048,height=2048,alpha=False);atlas.filepath_raw=str(ROOT/'textures'/(obj.name.lower()+'-atlas.png'));atlas.file_format='PNG'
    for m in materials:
        node=m.node_tree.nodes.new('ShaderNodeTexImage');node.image=atlas;m.node_tree.nodes.active=node
    bpy.ops.object.bake(type='DIFFUSE',pass_filter={'COLOR'},margin=16,use_clear=True);atlas.save()
    m=bpy.data.materials.new(obj.name+'_Atlas');m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.85;bs.inputs['Metallic'].default_value=0;bs.inputs['Specular IOR Level'].default_value=.12
    tx=m.node_tree.nodes.new('ShaderNodeTexImage');tx.image=atlas;uvnode=m.node_tree.nodes.new('ShaderNodeUVMap');uvnode.uv_map='AtlasUV';m.node_tree.links.new(uvnode.outputs['UV'],tx.inputs['Vector']);m.node_tree.links.new(tx.outputs['Color'],bs.inputs['Base Color'])
    obj.data.materials.clear();obj.data.materials.append(m)
    for p in obj.data.polygons:p.material_index=0
    # Export only baked UVs; source generator retains the construction mappings.
    for layer in list(obj.data.uv_layers):
        if layer.name!='AtlasUV':obj.data.uv_layers.remove(layer)
    print('ATLAS_READY',obj.name,flush=True)
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=1800;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.55,.65,.8,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65
scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.06));ground=bpy.context.object;ground.name='Preview_Ground'
stage=bpy.data.materials.new('Preview_Stage');stage.use_nodes=True;stage.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.075,.105,.13,1);stage.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=1;ground.data.materials.append(stage)
bpy.ops.object.light_add(type='SUN',location=(0,-20,40));bpy.context.object.data.energy=1.5;bpy.context.object.rotation_euler=(.35,-.4,-.4);bpy.context.object.data.angle=.3
bpy.ops.object.light_add(type='AREA',location=(-10,-20,30));bpy.context.object.data.energy=1600;bpy.context.object.data.size=25
bpy.ops.object.camera_add(location=(36,-65,43));cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam
def render(path,location,target,scale):
    cam.location=location;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
    scene.render.filepath=str(ROOT/'previews'/path);bpy.ops.render.render(write_still=True)
render('cliff-lineup.png',(36,-65,43),(0,5,7),68)
for o in objects:o.hide_render=o!=objects[1]
render('medium-closeup.png',(3,-23,17),(-11,0,5.2),24)
for o in objects:o.hide_render=o!=objects[4]
render('shoulder-closeup.png',(20,-10,23),(0,17,5.8),30)
for o in objects:o.hide_render=False
print('PREVIEW_READY',ROOT/'previews/cliff-lineup.png',flush=True)
report={'blender_version':bpy.app.version_string,'modules':{}}
for obj in objects:
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    old=obj.location.copy();obj.location=(0,0,0);stem=obj.name.lower().replace('_','-')
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'exports/glb'/f'{stem}.glb'),export_format='GLB',use_selection=True,export_apply=True)
    bpy.ops.export_scene.fbx(filepath=str(ROOT/'exports/fbx'/f'{stem}.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True,add_leaf_bones=False)
    obj.data.calc_loop_triangles();report['modules'][obj.name]={'vertices':len(obj.data.vertices),'triangles':len(obj.data.loop_triangles),'materials':1,'texture':'2048px baked color atlas from three supplied sheets','base_width_ratio':obj['base_width_ratio'],'dimensions':list(obj.dimensions),'pivot':'bottom center','file_stem':stem}
    obj.location=old
(ROOT/'polygon-report.json').write_text(json.dumps(report,indent=2))
for im in bpy.data.images:
    if im.source=='FILE':im.pack()
cam.location=(36,-65,43);cam.rotation_euler=(Vector((0,5,7))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=68
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'textured-cliff-variations.blend'))
print('KIT_READY',ROOT,flush=True)
