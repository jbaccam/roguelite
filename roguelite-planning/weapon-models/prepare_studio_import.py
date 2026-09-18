"""Prepare reviewed models for one native Studio import; originals stay unchanged."""
import bpy,json,re
from pathlib import Path
from mathutils import Vector,Matrix
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'studio-import';OUT.mkdir(exist_ok=True)
(OUT/'textures').mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
items=[json.loads((ROOT/'approved-glock.json').read_text())]+json.loads((ROOT/'inventory.json').read_text())
manifest=[]
for item in items:
    idx=item['index'];prefix=f'W{idx:02d}_'+re.sub('[^A-Za-z0-9]+','_',item['name']).strip('_')
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(Path(item['output'])/'Model.glb'))
    obs=set(bpy.data.objects)-before
    helpers={p.custom_shape for o in obs if o.type=='ARMATURE' for p in o.pose.bones if p.custom_shape}
    for o in list(obs):
        if o in helpers or o.type not in {'MESH','ARMATURE'}:
            for child in list(o.children):
                world=child.matrix_world.copy();child.parent=None;child.matrix_world=world
            obs.discard(o);bpy.data.objects.remove(o,do_unlink=True)
    meshes=[o for o in obs if o.type=='MESH']
    arms=[o for o in obs if o.type=='ARMATURE']
    if not item.get('components') or item.get('component_mode')=='additional':
        bpy.ops.object.select_all(action='DESELECT')
        for o in meshes:o.select_set(True)
        bpy.context.view_layer.objects.active=meshes[0]
        bpy.ops.object.join();meshes=[bpy.context.object]
    for n,o in enumerate(meshes):o.name=prefix+(f'__{n+1:02d}' if len(meshes)>1 else '')
    for o in arms:
        o.name=prefix+'__Rig'
        for bone in list(o.data.bones):
            old=bone.name;new=f'W{idx:02d}_{old}'
            for mesh in meshes:
                group=mesh.vertex_groups.get(old)
                if group:group.name=new
            bone.name=new
    images=set()
    for o in meshes:
        for m in o.data.materials:
            if not m:continue
            m.name=prefix+'_'+m.name
            if m.use_nodes:
                images.update(n.image for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
    for n,im in enumerate(images):
        im.name=f'{prefix}_Texture{n}'
        im.filepath_raw=str(OUT/'textures'/(im.name+'.png'));im.file_format='PNG';im.save()
    # Keep models spaced apart for import preview. Studio normalizes each item later.
    bbox=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
    lo=Vector(tuple(min(v[k] for v in bbox) for k in range(3)))
    hi=Vector(tuple(max(v[k] for v in bbox) for k in range(3)))
    center=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
    offset=Vector(((idx%6)*10,(idx//6)*10,0))-center
    for o in meshes+arms:
        if o.parent not in meshes+arms:o.matrix_world=Matrix.Translation(offset)@o.matrix_world
    manifest.append({'index':idx,'name':item['name'],'prefix':prefix,'meshes':[o.name for o in meshes],'bones':sum(len(o.data.bones)for o in arms)})
    if idx==11:
        before=set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(Path(item['output'])/'components/Rocket/Model.glb'))
        rocket=[o for o in set(bpy.data.objects)-before if o.type=='MESH'][0];rocket.name='W11_Rocket_Component'
        rocket.location+=Vector((54,0,3))
        for m in rocket.data.materials:
            m.name='Rocket_'+m.name
            for n in m.node_tree.nodes:
                if n.type=='TEX_IMAGE' and n.image:
                    im=n.image;im.name='Rocket_BaseColor';im.filepath_raw=str(OUT/'textures/Rocket_BaseColor.png');im.file_format='PNG';im.save()
        manifest[-1]['rocket']=rocket.name
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.context.scene.objects:
    if o.type in {'MESH','ARMATURE'}:o.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Weapon_Showcase.blend'))
bpy.ops.export_scene.fbx(filepath=str(OUT/'Weapon_Showcase.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y')
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('READY',len(manifest),'weapon families',sum(o.type=='MESH' for o in bpy.context.scene.objects),'meshes')
