import bpy, json, math, bmesh
from pathlib import Path
from mathutils import Vector

root=Path(__file__).resolve().parent
out={}
for ext in ['glb','fbx']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path=root/('Glock_Reference_Test.'+ext)
    if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
    else:bpy.ops.import_scene.fbx(filepath=str(path))
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    assert len(objects)==1,(ext,'Unexpected object count')
    o=objects[0]
    coords=[o.matrix_world@v.co for v in o.data.vertices]
    dims=[max(v[i] for v in coords)-min(v[i] for v in coords) for i in range(3)]
    assert all(math.isfinite(v) for co in coords for v in co)
    assert len(o.data.uv_layers)==1
    assert len(o.data.materials)==1
    images=[n.image for m in o.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    assert images and all(im.size[0]==1024 and im.size[1]==1024 for im in images)
    # glTF legitimately splits vertices at UV/normal seams. Weld for topology audit only.
    bm=bmesh.new();bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.000001)
    nonmanifold=sum(not e.is_manifold for e in bm.edges)
    bm.free()
    out[ext]={'mesh_objects':len(objects),'triangles':sum(len(p.vertices)-2 for p in o.data.polygons),'materials':len(o.data.materials),'uv_layers':len(o.data.uv_layers),'base_color_image_loaded':True,'bounds':dims,'nonmanifold_edges_after_seam_weld':nonmanifold}
    assert nonmanifold==0,(ext,nonmanifold)
(root/'export_validation.json').write_text(json.dumps(out,indent=2))
print('EXPORT_REIMPORT_VALIDATION_PASSED',json.dumps(out))
