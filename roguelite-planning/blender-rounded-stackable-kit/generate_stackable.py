"""Rounded stackable cliff kit. --preview makes only three style prototypes."""
import bpy,math,json,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
for d in ('textures','previews','exports/glb','exports/fbx'):(ROOT/d).mkdir(parents=True,exist_ok=True)
V2=ROOT.parent/'blender-cliff-pillars-v2';source=(V2/'generate_pillars.py').read_text()
setup=source[source.index('SOURCES='):source.index('specs=')]
setup=setup.replace("'ChatGPT Image Sep 16, 2026, 11_42_58 AM (3).png'","'C:/Users/Jeremiah/AppData/Local/Temp/codex-clipboard-1228ecae-c585-4927-89e1-31d682f938e9.png'")
import shutil
exec(setup)
# Rounded, subtly scalloped footprints. All pieces avoid the wall/corner grammar.
def outline(w,d,power,n,seed,unique=False):
    pts=[]
    for i in range(n):
        a=math.tau*i/n;r=1+.045*math.sin(3*a+seed)+.028*math.cos(5*a+seed*.6)+.013*math.sin(13*a+seed)
        pts.append((w*.5*math.cos(a)*r+.025*w*math.sin(2*a+seed),d*.5*math.sin(a)*r))
    return pts

def chunk(name,w,d,h,seed,taper=.93):
    obj=build(name,w,d,h,2,40 if w>12 else 32,seed,taper,.15,(0,0,0))
    # Small scallops at the grass lip and shallow side bends preserve a natural silhouette.
    for vertex in obj.data.vertices:
        x,y,z=vertex.co;angle=math.atan2(y/(d*.5),x/(w*.5));radius=math.hypot(x/(w*.5),y/(d*.5))
        if z>h-.5 and radius>.85:
            delta=.016*math.sin(15*angle+seed)+.008*math.cos(21*angle+seed)
            vertex.co.x*=1+delta;vertex.co.y*=1+delta;vertex.co.z+=.07*math.sin(15*angle+seed)
        elif .2<z<h-1.65:
            delta=.018*math.sin(5*angle+z*.55+seed)*math.sin(math.pi*z/h)
            vertex.co.x*=1+delta;vertex.co.y*=1+delta
    obj.data.update();return obj

# Bake-only source texture composition; final assets use one image per material.
exec(source[source.index('nodes=materials[2]'):source.index("scene=bpy.context.scene;scene.render.engine='CYCLES'")])
expansion=(ROOT.parent/'blender-cliff-expansion/generate_expansion.py').read_text()
exec(expansion[expansion.index('def boulder'):expansion.index("groups={'Grassy_Walls'")])
preview='--preview' in sys.argv
objects=[]
specs=[('01_Short_Squat_Grass',7.5,7,4.6,1,.94),('02_Medium_Grass',8,7.3,8.6,2,.95),('03_Tall_Narrow_Grass',7.3,6.5,14.2,3,.92),('04_Wide_Low_Plateau',17,13,3.8,4,.96),('05_Broad_Medium_Plateau',15,12.5,7.5,5,.93),('06_Tall_Wide_Mass',15,12.5,13.2,6,.92),('07_Slightly_Tapered_Grass',9.6,8.7,9,7,.86)]
for spec in specs:
    if not preview or spec[0].startswith(('01','03','04')):objects.append(chunk(*spec))
if not preview:
    objects.append(combine('08_Double_Stack',[(chunk('DoubleLower',17,13,5.5,8), (0,0,0)),(chunk('DoubleUpper',10,9,5.3,9),(-1.5,1,5.3))]))
    objects.append(combine('09_Triple_Stack',[(chunk('TripleLower',19,14,4.7,10),(0,0,0)),(chunk('TripleMid',13.5,10,4.8,11),(1.5,1,4.5)),(chunk('TripleUpper',8,7,4.8,12),(-1,1.8,9.1))]))
    objects.append(boulder('10_Bare_Low_Filler',11,8,2.8,20))
    objects.append(boulder('11_Medium_Boulder',6.2,5.5,4.5,21))
    objects.append(boulder('12_Large_Boulder',10,8.5,6.6,22))
    objects.append(combine('13_Rock_Cluster',[(boulder('ClusterMain',6,5,5,24),(0,1,0)),(boulder('ClusterLeft',3.8,3.5,3,25),(-3,-1,0)),(boulder('ClusterRight',4,3,3.7,26),(3,-.5,0)),(boulder('ClusterFront',2.7,2.5,2,27),(0,-2.7,0))]))
    objects.append(boulder('14_Standing_Narrow_Rock',5,4.2,10.5,28))

scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=1
for obj in objects:
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    atlasuv=obj.data.uv_layers.new(name='AtlasUV');obj.data.uv_layers.active=atlasuv;atlasuv.active_render=True
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.022);bpy.ops.object.mode_set(mode='OBJECT')
    atlas=bpy.data.images.new(obj.name+'_Color',width=2048,height=2048,alpha=False);atlas.filepath_raw=str(ROOT/'textures'/(obj.name.lower()+'-atlas.png'));atlas.file_format='PNG'
    for mat in obj.data.materials:
        node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=atlas;mat.node_tree.nodes.active=node
    bpy.ops.object.bake(type='DIFFUSE',pass_filter={'COLOR'},margin=16,use_clear=True);atlas.save()
    m=bpy.data.materials.new(obj.name+'_Atlas');m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.85;bs.inputs['Metallic'].default_value=0;bs.inputs['Specular IOR Level'].default_value=.12
    tx=m.node_tree.nodes.new('ShaderNodeTexImage');tx.image=atlas;m.node_tree.links.new(tx.outputs['Color'],bs.inputs['Base Color']);obj.data.materials.clear();obj.data.materials.append(m)
    for p in obj.data.polygons:p.material_index=0
    for uv in list(obj.data.uv_layers):
        if uv.name!='AtlasUV':obj.data.uv_layers.remove(uv)
    print('ATLAS_READY',obj.name,flush=True)

scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=2100;scene.render.resolution_y=1400;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.55,.65,.8,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65;scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
bpy.ops.mesh.primitive_plane_add(size=400,location=(0,0,-.04));ground=bpy.context.object;ground.name='Preview_Ground';m=bpy.data.materials.new('PreviewGround');m.use_nodes=True;m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.075,.105,.13,1);m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=1;ground.data.materials.append(m)
bpy.ops.object.light_add(type='SUN');bpy.context.object.data.energy=1.5;bpy.context.object.rotation_euler=(.35,-.4,-.4);bpy.context.object.data.angle=.3
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam
labels=[];lm=bpy.data.materials.new('PreviewLabel');lm.use_nodes=True;lm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.8,.9,1,1)
def label(name,loc):
    bpy.ops.object.text_add(location=loc);o=bpy.context.object;o.name='Label_'+name;o.data.body=name.replace('_',' ');o.data.align_x='CENTER';o.data.size=.85;o.data.materials.append(lm);labels.append(o)
if preview:
    for i,obj in enumerate(objects):obj.location=((i-1)*19,0,0);label(obj.name,obj.location+Vector((0,-8,.02)))
    target=Vector((0,0,6));scale=64
else:
    positions=[(-50,65),(-30,65),(-10,65),(12,65),(34,65),(56,65),(-40,32),(-8,32),(30,32),(-48,0),(-24,0),(0,0),(25,0),(49,0)]
    for obj,(x,y) in zip(objects,positions):obj.location=(x,y,0);label(obj.name,obj.location+Vector((0,-9,.02)))
    target=Vector((3,30,5));scale=143
cam.location=target+Vector((0,-70,66));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
scene.render.filepath=str(ROOT/'previews'/('style-preview.png' if preview else 'rounded-stackable-lineup.png'));bpy.ops.render.render(write_still=True)
print('PREVIEW_READY',scene.render.filepath,flush=True)
report={'blender_version':bpy.app.version_string,'modules':{}}
if not preview:
    for obj in objects:
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj;old=obj.location.copy();obj.location=(0,0,0);obj.data.name=obj.name;stem=obj.name.lower().replace('_','-')
        bpy.ops.export_scene.gltf(filepath=str(ROOT/'exports/glb'/f'{stem}.glb'),export_format='GLB',use_selection=True,export_apply=True)
        bpy.ops.export_scene.fbx(filepath=str(ROOT/'exports/fbx'/f'{stem}.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True,add_leaf_bones=False)
        obj.data.calc_loop_triangles();report['modules'][obj.name]={'file_stem':stem,'vertices':len(obj.data.vertices),'triangles':len(obj.data.loop_triangles),'materials':1,'dimensions':list(obj.dimensions),'pivot':'ground-level local origin','atlas_size':2048};obj.location=old
    (ROOT/'polygon-report.json').write_text(json.dumps(report,indent=2))
for im in bpy.data.images:
    if im.source=='FILE':im.pack()
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/('style-preview.blend' if preview else 'rounded-stackable-cliff-kit.blend')))
