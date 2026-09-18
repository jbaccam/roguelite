import bpy,bmesh,json,math
from pathlib import Path
OUT=Path(__file__).resolve().parent
report={}
for kind in ['blend','fbx','glb']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path=str(OUT/('Log_Master.'+kind))
    if kind=='blend': bpy.ops.wm.open_mainfile(filepath=path)
    elif kind=='fbx': bpy.ops.import_scene.fbx(filepath=path)
    else: bpy.ops.import_scene.gltf(filepath=path)
    objs=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('Log_Master')]
    assert len(objs)==1,(kind,len(objs))
    if kind!='blend': assert len([o for o in bpy.context.scene.objects if o.type=='MESH'])==1
    o=objs[0]; m=o.data; m.calc_loop_triangles()
    bm=bmesh.new(); bm.from_mesh(m); bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
    boundary=sum(e.is_boundary for e in bm.edges); nonmanifold=sum(not e.is_manifold for e in bm.edges)
    assert boundary==0 and nonmanifold==0,(kind,boundary,nonmanifold)
    assert len(m.materials)==1 and len(m.uv_layers)==1
    assert all(math.isfinite(c) and 0<=c<=1 for v in m.uv_layers.active.data for c in v.uv)
    assert all(t.area>1e-10 for t in m.loop_triangles)
    coords=[o.matrix_world@v.co for v in m.vertices]
    bounds=[[min(p[i] for p in coords),max(p[i] for p in coords)] for i in range(3)]
    assert abs(bounds[2][0])<.0001
    assert abs(sum(bounds[0]))<.0001 and abs(sum(bounds[1]))<.0001
    assert abs((bounds[0][1]-bounds[0][0])-12.016321)<.001
    texnodes=[n for n in m.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and n.image is not None]
    assert len(texnodes)>=1 and all(tuple(n.image.size)==(2048,2048) for n in texnodes),(kind,[(n.name,list(n.image.size),n.image.filepath) for n in texnodes])
    seen=set(); components=0
    for v in bm.verts:
        if v in seen: continue
        components+=1; todo=[v]; seen.add(v)
        while todo:
            for e in todo.pop().link_edges:
                for other in e.verts:
                    if other not in seen: seen.add(other); todo.append(other)
    assert components==5
    report[kind]={'mesh_objects':1,'vertices_in_file':len(m.vertices),'triangles':len(m.loop_triangles),'materials':len(m.materials),'UV_layers':len(m.uv_layers),'boundary_edges_after_weld':boundary,'nonmanifold_edges_after_weld':nonmanifold,'closed_shells':components,'bounds_world':bounds,'origin_world':list(o.matrix_world.translation),'loaded_texture_dimensions':list(texnodes[0].image.size),'zero_area_triangles':0}
    bm.free()
(OUT/'verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
