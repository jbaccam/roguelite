import bpy,json
from pathlib import Path
root=Path(__file__).resolve().parents[2]
for slug in ['02-nunchucks','04-kusarigama']:
 bpy.ops.wm.open_mainfile(filepath=str(root/'assets'/slug/'Model.blend'))
 o=next(o for o in bpy.context.scene.objects if o.type=='MESH' and o.vertex_groups)
 for g in o.vertex_groups:
  vs=[o.matrix_world@v.co for v in o.data.vertices if any(a.group==g.index and a.weight>.9 for a in v.groups)]
  if vs:print('PART',slug,g.name,len(vs),tuple(round(sum(v[i] for v in vs)/len(vs),3) for i in range(3)),flush=True)
