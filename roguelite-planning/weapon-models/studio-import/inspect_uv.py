import bpy,collections
from pathlib import Path
p=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(p/'Weapon_Showcase.blend'))
for name in ['W20_Cinder_Blocks','W22_Bowling_Ball']:
 o=bpy.data.objects[name];uv=o.data.uv_layers.active
 print(name,collections.Counter((round(sum(uv.data[i].uv.x for i in f.loop_indices)/len(f.loop_indices),2),round(sum(uv.data[i].uv.y for i in f.loop_indices)/len(f.loop_indices),2)) for f in o.data.polygons))
 print('normals',o.data.has_custom_normals)
