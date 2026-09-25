import bpy,bmesh
from pathlib import Path
p=Path(__file__).resolve().parent/'spitter-zombie'/'Model.blend';bpy.ops.wm.open_mainfile(filepath=str(p))
o=bpy.data.objects['Tattered shirt fitted to belly'];bm=bmesh.new();bm.from_mesh(o.data)
for e in bm.edges:
    if not e.is_manifold:print('BAD_EDGE',len(e.link_faces),[list(v.co) for v in e.verts],[(f.index,f.calc_area()) for f in e.link_faces])
bmesh.ops.dissolve_degenerate(bm,dist=.00005,edges=list(bm.edges))
print('AFTER_DISSOLVE',sum(not e.is_manifold for e in bm.edges))
bm.free()
