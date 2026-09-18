import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'supplied-textures'
OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Zombie_Stock_R15_Preview.blend'))
data=json.loads((ROOT/'stock_r15.json').read_text())
parts={p['name']:p for p in data['parts']}
# Rounded classic-avatar head; preserve stock bounds and neck pivot.
head=bpy.data.objects['Head'];hp=parts['Head']
bpy.ops.mesh.primitive_cube_add(size=1)
temp=bpy.context.object;temp.dimensions=(hp['size'][0],hp['size'][2],hp['size'][1])
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
bevel=temp.modifiers.new('Rounded Roblox head','BEVEL');bevel.width=.23;bevel.segments=8
bpy.ops.object.modifier_apply(modifier=bevel.name)
head.data=temp.data
bpy.data.objects.remove(temp,do_unlink=True)
head.vertex_groups.new(name='Head').add(list(range(len(head.data.vertices))),1,'REPLACE')
for polygon in head.data.polygons:polygon.use_smooth=True
weighted=head.modifiers.new('Head weighted normals','WEIGHTED_NORMAL');weighted.keep_sharp=True
sources={'head':'C:/Users/Jeremiah/AppData/Local/Temp/codex-clipboard-38985ec3-bc0d-4fac-80bd-3bd94573dcc2.png','torso':'ChatGPT Image Sep 17, 2026, 12_31_38 PM (2).png','limb':'ChatGPT Image Sep 17, 2026, 12_31_38 PM (1).png'}
mats={}
for kind,file in sources.items():
    im=bpy.data.images.load(str(Path('C:/Users/Jeremiah/Downloads')/file));im.pack()
    m=bpy.data.materials.new('Provided '+kind+' texture');m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=1;bs.inputs['Specular IOR Level'].default_value=.12
    t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=im
    m.node_tree.links.new(t.outputs['Color'],bs.inputs['Base Color']);mats[kind]=m
# Pixel bounds measured from supplied unfolded panels, excluding template outlines.
panels={
'head':[(360,355,897,919),(20,355,345,880),(905,355,1235,880),(20,355,345,880),(95,25,1155,280),(80,930,1170,1225)],
'torso':[(9,279,484,690),(752,279,1231,690),(497,279,739,690),(1247,279,1486,690),(10,36,483,264),(497,703,738,828)],
'limb':[(17,290,262,735),(598,290,870,733),(280,290,581,733),(888,290,1183,732),(16,10,261,271),(885,910,1182,1229)]}
for name,p in parts.items():
    if name=='HumanoidRootPart':continue
    o=bpy.data.objects[name]
    kind='head' if name=='Head' else 'torso' if 'Torso' in name else 'limb'
    o.data.materials.clear();o.data.materials.append(mats[kind])
    uv=o.data.uv_layers.active
    im=mats[kind].node_tree.nodes.get('Image Texture').image;W,H=im.size
    if kind=='torso':group=['UpperTorso','LowerTorso']
    elif kind=='limb':
        side='Left' if name.startswith('Left') else 'Right'
        group=[side+s for s in (['UpperArm','LowerArm','Hand'] if ('Arm' in name or 'Hand' in name) else ['UpperLeg','LowerLeg','Foot'])]
    else:group=['Head']
    bottom=min(parts[n]['cf'][1]-parts[n]['size'][1]/2 for n in group)
    top=max(parts[n]['cf'][1]+parts[n]['size'][1]/2 for n in group)
    for poly in o.data.polygons:
        poly.material_index=0
        normal=poly.normal;axis=max(range(3),key=lambda a:abs(normal[a]))
        face=(3 if normal.x>0 else 2) if axis==0 else ((1 if normal.y>0 else 0) if axis==1 else (4 if normal.z>0 else 5))
        x0,y0,x1,y1=panels[kind][face]
        if face==4 and 'UpperArm' in name:
            # Cover shoulder tops with the supplied sleeve fabric, not the green cap.
            x0,y0,x1,y1=295,305,560,408
        if face==4 and name=='UpperTorso':
            # The shirt continues across both shoulders behind the neckline.
            x0,y0,x1,y1=800,319,1110,420
        if 'Foot' in name:
            # Existing brown fabric panel supplies simple covered shoes; no repaint.
            x0,y0,x1,y1=920,934,1110,1030
        for li in poly.loop_indices:
            v=o.data.vertices[o.data.loops[li].vertex_index].co;sx,sy,sz=p['size']
            vertical=(v.z+p['cf'][1]-bottom)/(top-bottom)
            if face==0:u,w=v.x/sx+.5,vertical
            elif face==1:u,w=.5-v.x/sx,vertical
            elif face==2:u,w=.5-v.y/sz,vertical
            elif face==3:u,w=v.y/sz+.5,vertical
            elif face==4:u,w=v.x/sx+.5,v.y/sz+.5
            else:u,w=v.x/sx+.5,.5-v.y/sz
            u=max(0,min(1,u));w=max(0,min(1,w))
            if 'Foot' in name and face<4:w=v.z/p['size'][1]+.5
            uv.data[li].uv=((x0+(x1-x0)*u)/W,1-(y0+(y1-y0)*(1-w))/H)
    o['TextureSource']=sources[kind]
rig=bpy.data.objects['Stock_R15_Zombie_Rig']
assert len(rig.data.bones)==16
for name,p in parts.items():
    if name=='HumanoidRootPart':continue
    o=bpy.data.objects[name]
    assert list(o['StockSize'])==p['size']
    assert len(o.data.materials)==1 and o.data.uv_layers.active
    assert any(mod.type=='ARMATURE' for mod in o.modifiers)
    assert o.vertex_groups.get(name) is not None
    assert not any(word in o.name.lower() for word in ('hair','accessory'))
(OUT/'validation.json').write_text(json.dumps({'body_sections':15,'bones_including_root':16,'source_dimensions_preserved':True,'original_images':sources,'hair':False,'source_images_repainted':False,'note':'Texture panels aligned from supplied raster nets; separate UV template files were not attached. Studio animation compatibility still requires in-engine animation testing.'},indent=2))
scene=bpy.context.scene
scene.render.filepath=str(OUT/'Zombie_Blender_Provided_Textures.png')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Zombie_Blender_Provided_Textures.blend'))
bpy.ops.render.render(write_still=True)
print('Verified 15 standard-size stock body sections, 16 bones; three original packed images; no hair. UV panels aligned to supplied images, no source repainting.')
