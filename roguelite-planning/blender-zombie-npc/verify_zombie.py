import bpy, json, bmesh
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).resolve().parent
manifest=json.loads((OUT/'rig_manifest.json').read_text()); names=set(manifest['sections'])
results={}
def check(tag):
    obs=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name in names]
    assert len(obs)==15,(tag,len(obs))
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']; assert len(rigs)==1
    rig=rigs[0]; assert all(n in rig.data.bones for n in names)
    assert 'HumanoidRootPart' in rig.data.bones
    assert rig.location.length<.001,(tag,rig.location[:])
    for o in obs:
        assert o.data.uv_layers and len(o.data.materials)==1
        assert all(-.001<=v<=1.001 for uv in o.data.uv_layers.active.data for v in uv.uv)
        assert all(abs(sum(g.weight for g in v.groups)-1)<.001 for v in o.data.vertices)
        bm=bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001)
        assert all(e.is_manifold for e in bm.edges),(tag,o.name,'open edges')
        assert all(f.calc_area()>1e-9 for f in bm.faces),(tag,o.name,'zero area')
        bm.free()
    images=[n.image for o in obs for m in o.data.materials for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    assert images
    for i in set(images):
        _=i.pixels[0]
        assert i.has_data
    bpy.context.scene.frame_set(1); bpy.context.view_layer.update()
    def sample(o):
        ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get()); return [ev.matrix_world@v.co for v in ev.data.vertices]
    before={o.name:sample(o) for o in obs}
    b=rig.pose.bones['LeftLowerArm']; b.rotation_mode='XYZ'; b.rotation_euler.x=.65; bpy.context.view_layer.update()
    movement=max((a-z).length for a,z in zip(before['LeftLowerArm'],sample(next(o for o in obs if o.name=='LeftLowerArm'))))
    stable=max((a-z).length for a,z in zip(before['RightFoot'],sample(next(o for o in obs if o.name=='RightFoot'))))
    assert movement>.05 and stable<.001,(tag,movement,stable)
    b.rotation_euler.x=0; bpy.context.view_layer.update()
    allv=[p for o in obs for p in before[o.name]]
    bounds=[min(p.z for p in allv),max(p.z for p in allv)]
    assert abs(bounds[0])<.002,(tag,bounds)
    results[tag]={'parts':len(obs),'bones':len(rig.data.bones),'uv_and_weights':'pass','closed_shells':'pass','elbow_motion':movement,'unrelated_foot_motion':stable,'vertical_bounds':bounds,'textures_loaded':True}
bpy.ops.wm.open_mainfile(filepath=str(OUT/'Zombie_R15.blend')); check('blend')
for fmt in ['fbx','glb']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if fmt=='fbx':bpy.ops.import_scene.fbx(filepath=str(OUT/'Zombie_R15.fbx'))
    else:bpy.ops.import_scene.gltf(filepath=str(OUT/'Zombie_R15.glb'))
    check(fmt)
(OUT/'verification.json').write_text(json.dumps(results,indent=2)); print(json.dumps(results))
