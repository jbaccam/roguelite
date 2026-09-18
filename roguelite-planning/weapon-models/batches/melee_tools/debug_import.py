import bpy
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'assets/02-nunchucks/Model.glb'
for o in list(bpy.data.objects):bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(p))
for o in bpy.data.objects:print('OBJ',o.name,o.type,o.users_collection,flush=True)
print('SCENE',[o.name for o in bpy.context.scene.objects],flush=True)
