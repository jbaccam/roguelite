"""Revision of the existing rounded family: lighter stone, grown rims, eroded terraces."""
import bpy,math,json,sys,shutil,hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
for d in ('textures','previews','exports/glb','exports/fbx'):(ROOT/d).mkdir(parents=True,exist_ok=True)
OLD=ROOT.parent/'blender-rounded-stackable-kit'
previous=(OLD/'generate_stackable.py').read_text()
definitions=previous[previous.index('V2='):previous.index("preview='--preview'")]
definitions=definitions.replace("setup=source[source.index('SOURCES='):source.index('specs=')]", "setup=source[source.index('SOURCES='):source.index('specs=')]\nsetup=setup.replace('ChatGPT Image Sep 16, 2026, 11_42_57 AM (1).png','02862eb3-b09f-4d03-8bc3-ad7b57fd49a7.png').replace('rim=min(1.65,h*.27)','rim=min(3.5,h*.45)').replace('rim*.55','rim*.35')")
definitions=definitions.replace('C:/Users/Jeremiah/AppData/Local/Temp/codex-clipboard-1228ecae-c585-4927-89e1-31d682f938e9.png','C:/Users/Jeremiah/Downloads/62c4effc-a3a8-48f1-a138-776cdb1d9a8e.png')
exec(definitions)
old_chunk=chunk
def chunk(name,w,d,h,seed,taper=.93):
    obj=old_chunk(name,w,d,h,seed,taper);rim=min(3.5,h*.45)
    for v in obj.data.vertices:
        x,y,z=v.co;a=math.atan2(y/(d*.5),x/(w*.5));rad=math.hypot(x/(w*.5),y/(d*.5))
        if z>=h-rim-.2 and z<h:
            # Irregular lower vegetation boundary, with longer local droops.
            factor=1+.19*math.sin(3*a+seed)+.12*math.cos(7*a+seed)
            v.co.z=h-(h-z)*factor
        if rad>.88 and z<h*.1:
            s=.985+.015*min(1,z/(h*.1));v.co.x*=s;v.co.y*=s
    # Keep upright side stone coordinates and give the expanded rim a lower blend weight.
    for p in obj.data.polygons:
        if p.material_index==2:
            for li in p.loop_indices:
                uv=obj.data.uv_layers['UVMap'].data[li].uv
                f=(uv.y-.38)/.60;obj.data.uv_layers['BlendUV'].data[li].uv.x=min(1,max(0,f/.35))
    obj.data.update()
    bpy.context.view_layer.objects.active=obj
    bevel=obj.modifiers.new('Small_worn_edge_chamfer','BEVEL');bevel.width=.10;bevel.segments=1;bevel.limit_method='ANGLE';bevel.angle_limit=.60
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    return obj

overlay_files=['ChatGPT Image Sep 16, 2026, 04_33_16 PM (1).png','ChatGPT Image Sep 16, 2026, 04_33_16 PM (2).png','ChatGPT Image Sep 16, 2026, 04_33_16 PM (3).png','ChatGPT Image Sep 16, 2026, 04_33_17 PM (4).png']
overlays=[];alpha_report={}
import numpy as np
for i,f in enumerate(overlay_files):
    path=Path('C:/Users/Jeremiah/Downloads')/f;dest=ROOT/'textures'/f'moss-overlay-{i+1}.png';shutil.copy2(path,dest)
    im=bpy.data.images.load(str(dest));pixels=np.array(im.pixels[:],dtype=np.float32).reshape(-1,4);a=pixels[:,3]
    alpha_report[f]={'channels':im.channels,'alpha_min':float(a.min()),'alpha_max':float(a.max()),'transparent_fraction':float((a<.01).mean()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()};overlays.append(im)

def mossify(obj,w,d,h,index):
    # Reuse current rounded mesh, keeping exposed image-textured stone on its top and rim.
    for p in obj.data.polygons:
        old=p.material_index;p.material_index=0
        for li in p.loop_indices:
            co=obj.data.vertices[obj.data.loops[li].vertex_index].co
            if old==1:obj.data.uv_layers['UVMap'].data[li].uv=(co.x/10.5,co.y/10.5)
            elif old==2:obj.data.uv_layers['UVMap'].data[li].uv=obj.data.uv_layers['RockUV'].data[li].uv
    mat=materials[0].copy();mat.name=obj.name+'_SparseMoss_Source';obj.data.materials.clear();obj.data.materials.append(mat)
    nodes=mat.node_tree.nodes;links=mat.node_tree.links;bs=nodes.get('Principled BSDF');color=next(n.outputs['Color'] for n in nodes if n.type=='TEX_IMAGE')
    for kind,overlay in [('MossTop',overlays[index%4]),('MossSide',overlays[(index+2)%4])]:
        layer=obj.data.uv_layers.new(name=kind)
        for p in obj.data.polygons:
            for li in p.loop_indices:
                co=obj.data.vertices[obj.data.loops[li].vertex_index].co
                if kind=='MossTop' and p.normal.z>.45:
                    layer.data[li].uv=((co.x+w*.21)/(w*.40)+.5,(co.y+d*.15)/(d*.40)+.5)
                elif kind=='MossSide' and p.normal.y<-.25:
                    layer.data[li].uv=((co.x-w*.14)/(w*.38)+.5,(co.z-(h-1.1))/min(3.6,h*.65)+.7)
                else:layer.data[li].uv=(4,4)
        uvn=nodes.new('ShaderNodeUVMap');uvn.uv_map=kind;tx=nodes.new('ShaderNodeTexImage');tx.image=overlay;tx.extension='CLIP';links.new(uvn.outputs['UV'],tx.inputs['Vector'])
        # Clip faint contaminated alpha fringes before compositing into an opaque atlas.
        clean=nodes.new('ShaderNodeMath');clean.operation='SUBTRACT';clean.inputs[1].default_value=.18;clean.use_clamp=True;links.new(tx.outputs['Alpha'],clean.inputs[0])
        strength=nodes.new('ShaderNodeMath');strength.operation='MULTIPLY';strength.inputs[1].default_value=.90;links.new(clean.outputs[0],strength.inputs[0])
        mixn=nodes.new('ShaderNodeMixRGB');links.new(strength.outputs[0],mixn.inputs[0]);links.new(color,mixn.inputs[1]);links.new(tx.outputs['Color'],mixn.inputs[2]);color=mixn.outputs[0]
    links.new(color,bs.inputs['Base Color']);return obj

def terrace(name,parts):
    # Unequal, offset masses reach down through lower terraces, hiding rear 'cake' seams.
    obj=combine(name,parts)
    bpy.context.view_layer.objects.active=obj
    # Keep controllable low-poly shells; top exposure naturally disappears inside upper footprints.
    return obj

preview='--preview' in sys.argv
objects=[]
specs=[('01_Short_Squat_Grass',7.5,7,4.6,1,.94),('02_Medium_Grass',8,7.3,8.6,2,.95),('03_Tall_Narrow_Grass',7.3,6.5,14.2,3,.92),('04_Wide_Low_Plateau',17,13,3.8,4,.96),('05_Broad_Medium_Plateau',15,12.5,7.5,5,.93),('06_Tall_Wide_Mass',15,12.5,13.2,6,.92),('07_Slightly_Tapered_Grass',9.6,8.7,9,7,.86)]
for spec in specs:
    if not preview or spec[0].startswith('02'):objects.append(chunk(*spec))
double=terrace('08_Double_Eroded_Terrace',[(chunk('DoubleLower',18,13,4.6,8),(0,0,0)),(chunk('DoubleUpper',11.7,10.5,11.4,9),(-4.4,2.5,0))])
if preview:
    objects.append(double)
else:
    objects.append(double)
    objects.append(terrace('09_Triple_Eroded_Terrace',[(chunk('TripleLow',20,14,3.7,10),(0,0,0)),(chunk('TripleMiddle',12.5,11,7.7,11),(5,1.3,0)),(chunk('TripleHigh',10.6,9.5,14.1,12),(-3.8,3,0))]))
    objects.extend([boulder('10_Bare_Low_Filler',11,8,2.8,20),boulder('11_Medium_Boulder',6.2,5.5,4.5,21),boulder('12_Large_Boulder',10,8.5,6.6,22),combine('13_Rock_Cluster',[(boulder('ClusterMain',6,5,5,24),(0,1,0)),(boulder('ClusterLeft',3.8,3.5,3,25),(-3,-1,0)),(boulder('ClusterRight',4,3,3.7,26),(3,-.5,0)),(boulder('ClusterFront',2.7,2.5,2,27),(0,-2.7,0))]),boulder('14_Standing_Narrow_Rock',5,4.2,10.5,28)])
for idx,(name,w,d,h,seed) in enumerate([('15_Short_Moss_Only',7.5,7,4.6,1),('16_Medium_Moss_Only',8,7.3,8.6,2),('17_Tall_Moss_Only',7.3,6.5,14.2,3),('18_Wide_Low_Moss_Only',17,13,3.8,4)]):
    if not preview or idx==1:objects.append(mossify(chunk(name,w,d,h,seed),w,d,h,idx))
if not preview:objects.append(mossify(boulder('19_Mossy_Boulder_Filler',10,8.5,5.5,31),10,8.5,5.5,3))

# Bake the approved image-only composition into simple opaque game materials.
old=previous[previous.rindex("scene=bpy.context.scene;scene.render.engine='CYCLES'"):previous.index("scene.render.engine='BLENDER_EEVEE'")]
exec(old)
scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=2200;scene.render.resolution_y=1450;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.55,.65,.8,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65;scene.view_settings.view_transform='Standard';scene.view_settings.look='None'
bpy.ops.mesh.primitive_plane_add(size=500,location=(0,0,-.04));ground=bpy.context.object;ground.name='Preview_Ground';m=bpy.data.materials.new('PreviewGround');m.use_nodes=True;m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.075,.105,.13,1);m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=1;ground.data.materials.append(m)
bpy.ops.object.light_add(type='SUN');bpy.context.object.data.energy=1.5;bpy.context.object.rotation_euler=(.35,-.4,-.4);bpy.context.object.data.angle=.3
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';scene.camera=cam
labels=[];lm=bpy.data.materials.new('PreviewLabel');lm.use_nodes=True;lm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.8,.9,1,1)
def label(obj):
    bpy.ops.object.text_add(location=obj.location+Vector((0,-10,.02)));lab=bpy.context.object;lab.name='Label_'+obj.name;lab.data.body=obj.name.replace('_',' ');lab.data.align_x='CENTER';lab.data.size=1.;lab.data.materials.append(lm);labels.append(lab)
def render(filename,target,scale,vector=(0,-70,66)):
    target=Vector(target);cam.location=target+Vector(vector);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;scene.render.filepath=str(ROOT/'previews'/filename);bpy.ops.render.render(write_still=True)
if preview:
    for obj,x in zip(objects,[-20,0,22]):obj.location=(x,0,0);label(obj)
    render('lightstone-rim-style-preview.png',(0,0,6),68,vector=(4,-70,46))
    print('PREVIEW_READY',scene.render.filepath,flush=True)
else:
    pos=[(-50,65),(-30,65),(-10,65),(12,65),(34,65),(56,65),(-40,32),(-8,32),(30,32),(-48,0),(-24,0),(0,0),(25,0),(49,0)]
    for obj,(x,y) in zip(objects[:14],pos):obj.location=(x,y,0);label(obj)
    for obj in objects[14:]:obj.hide_render=True
    render('revised-rounded-lineup.png',(3,30,5),143)
    for obj in objects[:14]:obj.hide_render=True
    for lab in labels:lab.hide_render=True
    for i,obj in enumerate(objects[14:]):obj.location=((i-2)*23,0,0);obj.hide_render=False;label(obj)
    render('moss-only-lineup.png',(0,0,5),122,vector=(0,-70,46))
    for lab in labels:lab.hide_render=True
    for obj in objects:obj.hide_render=True
    for name,file in [('02_Medium_Grass','grass-rim-closeup.png'),('09_Triple_Eroded_Terrace','asymmetric-stack-closeup.png')]:
        obj=next(o for o in objects if o.name==name);obj.hide_render=False;render(file,obj.location+Vector((0,0,7 if name.startswith('09') else 5)),37 if name.startswith('09') else 21,vector=(15,-36,19));obj.hide_render=True
    report={'blender_version':bpy.app.version_string,'modules':{}}
    for obj in objects:
        bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj;oldloc=obj.location.copy();obj.location=(0,0,0);obj.data.name=obj.name;stem=obj.name.lower().replace('_','-')
        bpy.ops.export_scene.gltf(filepath=str(ROOT/'exports/glb'/f'{stem}.glb'),export_format='GLB',use_selection=True,export_apply=True)
        bpy.ops.export_scene.fbx(filepath=str(ROOT/'exports/fbx'/f'{stem}.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True,add_leaf_bones=False)
        obj.data.calc_loop_triangles();report['modules'][obj.name]={'file_stem':stem,'triangles':len(obj.data.loop_triangles),'vertices':len(obj.data.vertices),'materials':1,'dimensions':list(obj.dimensions),'atlas_size':2048};obj.location=oldloc;obj.hide_render=False
    (ROOT/'polygon-report.json').write_text(json.dumps(report,indent=2))
    for i,obj in enumerate(objects[14:]):obj.location=((i-2)*23,-34,0)
    for lab in labels:
        obj=bpy.data.objects.get(lab.name.removeprefix('Label_'))
        if obj:lab.location=obj.location+Vector((0,-10,.02));lab.hide_render=False
    render('complete-19-piece-lineup.png',(3,15,5),167)
(ROOT/'overlay-alpha-report.json').write_text(json.dumps(alpha_report,indent=2))
for im in bpy.data.images:
    if im.source=='FILE':im.pack()
bpy.context.preferences.filepaths.save_version=0;bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/('style-preview.blend' if preview else 'rounded-lightstone-revision.blend')))
