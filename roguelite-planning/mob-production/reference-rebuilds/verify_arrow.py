import bpy,bmesh,json,hashlib
from pathlib import Path
out=Path(__file__).resolve().parent/'bow-skeleton'
expected=json.loads((out/'ArrowProjectile.json').read_text())
report={'passed':False,'imports':{},'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [out/'ArrowProjectile.blend',out/'ArrowProjectile.fbx',out/'ArrowProjectile.glb',out/'ArrowBaseColor.png']}}
for extension in ['fbx','glb']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if extension=='fbx':bpy.ops.import_scene.fbx(filepath=str(out/'ArrowProjectile.fbx'))
    else:bpy.ops.import_scene.gltf(filepath=str(out/'ArrowProjectile.glb'))
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(meshes)==1
    o=meshes[0];o.data.calc_loop_triangles();assert len(o.data.loop_triangles)==expected['triangles'];assert o.data.uv_layers
    bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
    assert all(e.is_manifold for e in bm.edges);bm.free()
    assert any(tuple(i.size)==(512,512) for i in bpy.data.images)
    report['imports'][extension]={'triangles':len(o.data.loop_triangles),'textureLoaded':True,'closedGeometry':True}
report['passed']=True;(out/'ArrowChecks.json').write_text(json.dumps(report,indent=2));print('ARROW_VERIFIED',report['passed'])
