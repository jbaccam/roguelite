import bpy, json, struct, gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'supplied-textures'/'studio-native'
OUT.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'supplied-textures'/'Zombie_Blender_Provided_Textures.blend'))
data=json.loads((ROOT/'stock_r15.json').read_text())
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.samples=1
scene.render.bake.margin=12
scene.render.bake.use_clear=True
for p in data['parts']:
    name=p['name']
    if name in ('Head','HumanoidRootPart'):continue
    o=bpy.data.objects[name]
    raw=(ROOT/'stock_meshes'/(name+'.mesh')).read_bytes()
    if raw[:2]==b'\x1f\x8b':raw=gzip.decompress(raw)
    end=raw.index(b'\n')+1
    hs,vs,fs,nv,nf=struct.unpack_from('<HBBII',raw,end)
    stock=[struct.unpack_from('<ff',raw,end+hs+i*vs+24) for i in range(nv)]
    original=o.data.uv_layers.active
    original.name='ProvidedImageProjection'
    uv=o.data.uv_layers.new(name='RobloxStockUV')
    for loop in o.data.loops:
        u,v=stock[loop.vertex_index]
        uv.data[loop.index].uv=(u,1-v)
    o.data.uv_layers.active=uv
    mat=o.data.materials[0].copy();o.data.materials[0]=mat
    nt=mat.node_tree
    source=next(n for n in nt.nodes if n.type=='TEX_IMAGE')
    mapping=nt.nodes.new('ShaderNodeUVMap');mapping.uv_map=original.name
    nt.links.new(mapping.outputs['UV'],source.inputs['Vector'])
    emission=nt.nodes.new('ShaderNodeEmission')
    nt.links.new(source.outputs['Color'],emission.inputs['Color'])
    nt.links.new(emission.outputs[0],nt.nodes.get('Material Output').inputs['Surface'])
    target=bpy.data.images.new(name+'_StockUV',1024,1024,alpha=False)
    target.colorspace_settings.name='sRGB'
    node=nt.nodes.new('ShaderNodeTexImage');node.image=target
    for n in nt.nodes:n.select=False
    node.select=True;nt.nodes.active=node
    bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
    bpy.ops.object.bake(type='EMIT')
    target.filepath_raw=str(OUT/(name+'.png'));target.file_format='PNG';target.save()
    print('BAKED',name,flush=True)
print('STOCK_UV_ALIGNMENT_BAKE_COMPLETE',flush=True)
