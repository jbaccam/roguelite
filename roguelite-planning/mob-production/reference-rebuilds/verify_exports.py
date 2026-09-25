"""Reopen exchange files in clean Blender scenes; never treat this as art approval."""
import bpy,sys,json,struct,math,traceback,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ids=sys.argv[sys.argv.index('--')+1:]
for mob in ids:
    out=ROOT/mob;report={'id':mob,'checks':{},'errors':[],'sha256':{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [out/'Model.blend',out/'Model.fbx',out/'Model.glb',out/'BaseColor.png',*sorted((out/'animations').glob('*.fbx'))]}}
    expected=json.loads((out/'Rig.json').read_text());bone_names=set(expected['bones'])|{'Root'}
    if (out/'Normal.png').exists():report['sha256']['Normal.png']=hashlib.sha256((out/'Normal.png').read_bytes()).hexdigest()
    try:
        blob=(out/'Model.glb').read_bytes();magic,version,length=struct.unpack_from('<III',blob);assert magic==0x46546c67 and version==2 and length==len(blob)
        chunklen,kind=struct.unpack_from('<II',blob,12);doc=json.loads(blob[20:20+chunklen])
        assert len(doc.get('skins',[]))>0 and len(doc.get('images',[]))>0
        if mob=='obsidian-ogre':assert any('normalTexture' in m for m in doc.get('materials',[])),'Missing exported stone normal texture'
        if mob=='bow-skeleton':assert 'HeldArrow' not in bone_names,'Held arrow was not removed'
        animations={a['name'] for a in doc.get('animations',[])};assert animations==set(expected['actions']),animations
        for mesh in doc['meshes']:
            for p in mesh['primitives']:assert {'POSITION','NORMAL','TEXCOORD_0','JOINTS_0','WEIGHTS_0'}<=p['attributes'].keys()
        report['checks']['glbStructure']={'animations':sorted(animations),'meshes':len(doc['meshes']),'embeddedImages':len(doc['images'])}
        for extension in ['fbx','glb']:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            if extension=='fbx':bpy.ops.import_scene.fbx(filepath=str(out/'Model.fbx'))
            else:bpy.ops.import_scene.gltf(filepath=str(out/'Model.glb'))
            rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE'];assert len(rigs)==1
            rig=rigs[0];actual={b.name for b in rig.data.bones};assert actual==bone_names,(extension,actual^bone_names)
            widgets={p.custom_shape for p in rig.pose.bones if p.custom_shape}
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o not in widgets];assert meshes
            assert all(any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers) for o in meshes)
            assert all(o.data.uv_layers for o in meshes)
            assert any(im.size[0]==2048 and im.size[1]==2048 for im in bpy.data.images)
            triangles=0;max_influences=0;unweighted=0;bad_sum=0
            for o in meshes:
                o.data.calc_loop_triangles();triangles+=len(o.data.loop_triangles)
                for v in o.data.vertices:
                    ww=[g.weight for g in v.groups if g.weight>1e-5];max_influences=max(max_influences,len(ww));unweighted+=not ww;bad_sum+=abs(sum(ww)-1)>1e-4
            assert triangles==expected['totals']['triangles'],(extension,triangles,expected['totals'])
            assert max_influences<=4 and not unweighted and not bad_sum
            report['checks'][extension+'Import']={'triangles':triangles,'bones':len(actual),'meshes':len(meshes),'maxInfluences':max_influences,'weightsNormalized':True,'textureLoaded':True}
        motions={}
        for name in expected['actions']:
            bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.fbx(filepath=str(out/'animations'/f'{name}.fbx'))
            rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');assert rig.animation_data and rig.animation_data.action
            action=rig.animation_data.action;start,end=action.frame_range;assert end>start
            bpy.context.scene.frame_set(round(start));a={p.name:p.matrix.copy() for p in rig.pose.bones}
            bpy.context.scene.frame_set(round(start+(end-start)*.35));delta=max(max(abs(p.matrix[i][j]-a[p.name][i][j]) for i in range(4) for j in range(4)) for p in rig.pose.bones)
            assert delta>1e-5,(name,'no bone movement')
            motions[name]={'frames':[float(start),float(end)],'sampledMatrixDelta':delta}
        report['checks']['fbxAnimationImports']=motions
        assert not expected['failures'],expected['failures']
        report['passed']=True
    except Exception as e:
        report['passed']=False;report['errors'].append(str(e));report['traceback']=traceback.format_exc()
    (out/'ExchangeChecks.json').write_text(json.dumps(report,indent=2));print('VERIFIED',mob,report['passed'],report['errors'],flush=True)
