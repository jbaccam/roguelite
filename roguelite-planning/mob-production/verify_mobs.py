"""Independent Blender source/interchange validation. No Studio claims."""
import bpy,bmesh,json,math,sys,hashlib
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parent
ids=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [p.name for p in root.iterdir() if (p/'Model.blend').exists()]
reports={}
for mob in ids:
    out=root/mob;expected=json.loads((out/'Rig.json').read_text())['bones'];report={}
    for fmt in ['blend','fbx','glb']:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        path=str(out/('Model.'+fmt))
        if fmt=='blend':bpy.ops.wm.open_mainfile(filepath=path)
        elif fmt=='fbx':bpy.ops.import_scene.fbx(filepath=path)
        else:bpy.ops.import_scene.gltf(filepath=path)
        rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];assert len(rigs)==1,(mob,fmt,'rig count')
        rig=rigs[0];assert set(rig.data.bones.keys())==set(expected),(mob,fmt,'bones')
        rig.animation_data_clear()
        for b in rig.pose.bones:b.rotation_mode='XYZ';b.rotation_euler=(0,0,0);b.location=(0,0,0);b.scale=(1,1,1)
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)]
        assert len(meshes)>0
        tri=0;open_edges=0
        for o in meshes:
            me=o.data;me.calc_loop_triangles();tri+=len(me.loop_triangles)
            assert all(math.isfinite(c) for v in me.vertices for c in v.co)
            assert me.uv_layers,(mob,fmt,o.name,'missing UVs')
            assert all(-.001<=c<=1.001 for uv in me.uv_layers.active.data for c in uv.uv)
            for v in me.vertices:
                weights=[g.weight for g in v.groups if g.weight>0]
                assert weights and abs(sum(weights)-1)<1e-4,(mob,fmt,o.name,'weights')
                assert len(weights)<=4
            bm=bmesh.new();bm.from_mesh(me)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
            assert all(f.calc_area()>1e-10 for f in bm.faces),(mob,fmt,o.name,'zero area')
            open_edges+=sum(not e.is_manifold for e in bm.edges);bm.free()
            tex=[n.image for m in me.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
            for image in tex:
                _=image.pixels[0]
            assert tex and all(i.has_data for i in tex),(mob,fmt,o.name,'missing texture')
        assert open_edges==0,(mob,fmt,'nonmanifold',open_edges)
        # Rig must actually deform geometry, not merely coexist with it.
        def snapshot():
            bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
            return {o.name:[o.matrix_world@v.co for v in o.evaluated_get(dg).data.vertices] for o in meshes}
        before=snapshot();target='RightLowerArm' if 'RightLowerArm' in expected else 'Head' if 'Head' in expected else 'LeftLeg0Lower' if 'LeftLeg0Lower' in expected else 'Crown'
        rig.pose.bones[target].rotation_euler.x=.35
        after=snapshot();moved=max((a-b).length for name in before for a,b in zip(before[name],after[name]))
        assert moved>.01,(mob,fmt,'rig does not move geometry')
        report[fmt]={'triangles':tri,'bones':len(expected),'meshes':len(meshes),'normalizedWeights':True,'textureLoaded':True,'closedComponents':True,'rigPoseDisplacement':moved,'actions':list(bpy.data.actions.keys())}
        if fmt=='glb':
            assert len(bpy.data.actions)>=5,(mob,'GLB missing clips',list(bpy.data.actions.keys()))
    # Separately reimport each FBX action and inspect nonconstant evaluated transforms.
    report['clips']={}
    for clip in ['Idle','Move','Attack','Hit','Death']:
        bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(out/(clip+'.fbx')))
        rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
        assert rig.animation_data and rig.animation_data.action,(mob,clip,'missing action')
        action=rig.animation_data.action;start,end=action.frame_range
        assert end>start,(mob,clip,'empty action')
        observed=[]
        for f in [start,start+(end-start)*.25,start+(end-start)*.5,start+(end-start)*.75,end]:
            bpy.context.scene.frame_set(round(f));bpy.context.view_layer.update()
            observed.append([x for b in rig.pose.bones for row in b.matrix for x in row])
        motion=max(abs(a-b) for frame in observed[1:] for a,b in zip(observed[0],frame))
        assert motion>.001,(mob,clip,'static clip')
        report['clips'][clip]={'frames':[float(start),float(end)],'evaluatedMotion':motion}
    report['fileHashes']={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['Model.blend','Model.fbx','Model.glb','BaseColor.png','Idle.fbx','Move.fbx','Attack.fbx','Hit.fbx','Death.fbx']}
    (out/'validation.json').write_text(json.dumps(report,indent=2));reports[mob]=report
    print('VERIFIED',mob,flush=True)
(root/'verification.json').write_text(json.dumps(reports,indent=2))
