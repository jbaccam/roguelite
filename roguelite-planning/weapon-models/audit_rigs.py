"""Independent skeletal delivery checks; temporary poses only, never saves assets."""
import bpy, json, math, sys
from pathlib import Path
from mathutils import Matrix
ROOT=Path(__file__).resolve().parent
items=json.loads((ROOT/'inventory.json').read_text())
ids=[int(v) for v in sys.argv[sys.argv.index('--')+1:]] if '--' in sys.argv else [2,4,25,33]
report={}
def inspect():
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    assert len(rigs)==1, f'Expected one armature, got {len(rigs)}'
    rig=rigs[0]
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
    assert meshes,'No skinned meshes'
    assert not bpy.data.actions,'Unexpected animation Actions'
    assignments={};bad=[]
    for o in meshes:
        names={g.index:g.name for g in o.vertex_groups if g.name in rig.data.bones}
        for v in o.data.vertices:
            influences=[(names[g.group],g.weight) for g in v.groups if g.group in names and g.weight>1e-6]
            if len(influences)!=1 or abs(sum(w for n,w in influences)-1)>1e-5:bad.append((o.name,v.index,influences))
            elif influences:assignments.setdefault(influences[0][0],[]).append((o.name,v.index))
    assert not bad,f'{len(bad)} vertices without exactly one rigid bone weight'
    for pb in rig.pose.bones:
        assert max(abs(pb.matrix_basis[i][j]-(1 if i==j else 0)) for i in range(4) for j in range(4))<1e-4, f'Non-rest saved pose: {pb.name}'
    def positions():
        bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();result={}
        for o in meshes:
            ev=o.evaluated_get(dg);me=ev.to_mesh()
            for v in me.vertices:result[(o.name,v.index)]=ev.matrix_world@v.co
            ev.to_mesh_clear()
        return result
    baseline=positions();tests=[]
    for bone in rig.data.bones:
        if bone.parent is None or bone.name not in assignments:continue
        pb=rig.pose.bones[bone.name];old=pb.matrix_basis.copy();pb.matrix_basis=Matrix.Rotation(.22,4,'Z')
        posed=positions();desc={bone.name}|{b.name for b in bone.children_recursive}
        affected=[key for name,keys in assignments.items() if name in desc for key in keys]
        stationary=[key for name,keys in assignments.items() if name not in desc for key in keys]
        moved=max((posed[k]-baseline[k]).length for k in affected)
        fixed_error=max([(posed[k]-baseline[k]).length for k in stationary] or [0])
        rigid_error=0
        for name,keys in assignments.items():
            origin=keys[0]
            rigid_error=max(rigid_error,max(abs((posed[k]-posed[origin]).length-(baseline[k]-baseline[origin]).length) for k in keys))
        tests.append({'bone':bone.name,'max_motion':moved,'stationary_error':fixed_error,'rigid_distance_error':rigid_error})
        assert moved>1e-5,f'Bone does not move assigned geometry: {bone.name}'
        assert fixed_error<1e-4,f'Unexpected movement outside descendants: {bone.name}'
        assert rigid_error<1e-4,f'Rigid part deformed: {bone.name}'
        pb.matrix_basis=old
    assert tests,'No movable weighted child bones tested'
    return {'passed':True,'armature':rig.name,'bone_count':len(rig.data.bones),'mesh_count':len(meshes),'skinned_vertices':sum(len(o.data.vertices) for o in meshes),'hierarchy':{b.name:b.parent.name if b.parent else None for b in rig.data.bones},'pose_tests':tests,'action_count':len(bpy.data.actions)}
for item in items:
    if item['index'] not in ids:continue
    result={}
    for ext in ['blend','fbx','glb']:
        try:
            path=Path(item['output'])/('Model.'+ext)
            bpy.ops.wm.read_factory_settings(use_empty=True)
            if ext=='blend':bpy.ops.wm.open_mainfile(filepath=str(path))
            elif ext=='fbx':bpy.ops.import_scene.fbx(filepath=str(path))
            else:bpy.ops.import_scene.gltf(filepath=str(path))
            result[ext]=inspect()
        except Exception as exc:result[ext]={'passed':False,'error':str(exc)}
        print('RIG_AUDIT',item['index'],ext,result[ext].get('passed'),result[ext].get('error',''),flush=True)
    report[str(item['index'])]=result
target=ROOT/'rig_audit.json';previous=json.loads(target.read_text()) if target.exists() else {};previous.update(report);target.write_text(json.dumps(previous,indent=2))
if any(not f.get('passed') for r in report.values() for f in r.values()):raise SystemExit(1)
