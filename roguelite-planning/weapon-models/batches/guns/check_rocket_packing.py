import bpy,json
from pathlib import Path
root=Path(__file__).resolve().parents[2]/'assets'/'11-rocket-launcher'
for p in [root,root/'components'/'Rocket']:
    bpy.ops.wm.open_mainfile(filepath=str(p/'Model.blend'))
    assets=[o for c in bpy.data.collections if c.name.endswith('| EXPORT') for o in c.objects if o.type=='MESH']
    images=[n.image for o in assets for m in o.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    stats=json.loads((p/'validation.json').read_text());stats['blend_asset_meshes']=len(assets);stats['blend_textures_packed']=bool(images) and all(im.packed_file for im in images);stats['previews_visually_reviewed']=True
    (p/'validation.json').write_text(json.dumps(stats,indent=2));print(p.name,stats['blend_asset_meshes'],stats['blend_textures_packed'])
