import bpy,bmesh,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
report={}
for kind in ['blend','fbx','glb']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path=str(OUT/('Evergreen_Master.'+kind))
    if kind=='blend': bpy.ops.wm.open_mainfile(filepath=path)
    elif kind=='fbx': bpy.ops.import_scene.fbx(filepath=path)
    else: bpy.ops.import_scene.gltf(filepath=path)
    objs=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('Evergreen_Master')]
    assert len(objs)==1,(kind,len(objs))
    o=objs[0]; m=o.data; m.calc_loop_triangles()
    bm=bmesh.new(); bm.from_mesh(m); bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
    boundary=sum(e.is_boundary for e in bm.edges); nonmanifold=sum(not e.is_manifold for e in bm.edges)
    assert boundary==0 and nonmanifold==0,(kind,boundary,nonmanifold)
    assert len(m.materials)==1 and len(m.uv_layers)==1
    assert all(0<=c<=1 for v in m.uv_layers.active.data for c in v.uv)
    assert all(t.area>1e-10 for t in m.loop_triangles)
    coords=[o.matrix_world@v.co for v in m.vertices]
    report[kind]={'mesh_objects':1,'vertices_in_file':len(m.vertices),'triangles':len(m.loop_triangles),'materials':len(m.materials),'UV_layers':len(m.uv_layers),'boundary_edges_after_weld':boundary,'nonmanifold_edges_after_weld':nonmanifold,'minimum_z':min(p.z for p in coords),'maximum_z':max(p.z for p in coords),'origin_world':list(o.matrix_world.translation),'texture_nodes':sum(n.type=='TEX_IMAGE' and n.image is not None for n in m.materials[0].node_tree.nodes)}
    bm.free()
(OUT/'verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
