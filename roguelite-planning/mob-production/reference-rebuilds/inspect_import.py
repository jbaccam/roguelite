import bpy,json
from pathlib import Path
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(Path(__file__).resolve().parent/'snake'/'Model.glb'))
for o in bpy.context.scene.objects:
    if o.type=='MESH':print('IMPORTED',o.name,[(m.type,m.object.name if m.type=='ARMATURE' else '') for m in o.modifiers],o.parent.name if o.parent else None,o.parent_type,o.parent_bone,len(o.vertex_groups))
