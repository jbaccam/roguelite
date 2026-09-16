"""Re-import every export and verify geometry, UVs, texture nodes and source hashes."""
import bpy,json,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sources={'rock':'ChatGPT Image Sep 16, 2026, 11_42_57 AM (1).png','grass':'ChatGPT Image Sep 16, 2026, 11_42_57 AM (2).png','transition':'ChatGPT Image Sep 16, 2026, 11_42_58 AM (3).png'}
report={'texture_sha256':{},'exports':[]}
for role,name in sources.items():
    original=hashlib.sha256((Path('C:/Users/Jeremiah/Downloads')/name).read_bytes()).hexdigest();copied=hashlib.sha256((ROOT/'textures'/f'{role}.png').read_bytes()).hexdigest()
    assert original==copied
    report['texture_sha256'][role]={'original':original,'copy':copied,'identical':True}
expected=json.loads((ROOT/'polygon-report.json').read_text())['modules']
counts={v['file_stem']:v['triangles'] for v in expected.values()}
for suffix in ('glb','fbx'):
    for path in sorted((ROOT/'exports'/suffix).glob('*.'+suffix)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if suffix=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
        else:bpy.ops.import_scene.fbx(filepath=str(path))
        objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];assert len(objs)==1
        entry={'file':str(path.relative_to(ROOT)),'mesh_objects':len(objs),'parts':[]};total=0
        for obj in objs:
            mesh=obj.data;mesh.calc_loop_triangles();total+=len(mesh.loop_triangles)
            assert len(mesh.uv_layers)>0 and len(mesh.materials)==1
            coords=[tuple(uv.uv) for uv in mesh.uv_layers.active.data];assert all(math.isfinite(v) for co in coords for v in co)
            assert len(set(coords))>5
            assert all(-.0001<=v<=1.0001 for co in coords for v in co)
            mat=mesh.materials[0];textures=[node for node in mat.node_tree.nodes if node.type=='TEX_IMAGE' and node.image]
            assert textures and all(node.image.size[0]>0 for node in textures)
            assert all(tuple(node.image.size)==(2048,2048) for node in textures)
            bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');assert bs.inputs['Metallic'].default_value==0
            assert bs.inputs['Base Color'].is_linked
            entry['parts'].append({'name':obj.name,'triangles':len(mesh.loop_triangles),'uv_loops':len(coords),'material':mat.name,'images':[n.image.name for n in textures],'base_color_image_link':True})
        assert total==counts[path.stem],(path,total,counts[path.stem])
        entry['total_triangles']=total;entry['passed']=True;report['exports'].append(entry)
report['all_passed']=True
(ROOT/'validation-report.json').write_text(json.dumps(report,indent=2))
print('VALIDATION_PASSED',len(report['exports']),flush=True)
