"""Verify the delivered roster against its source images and independent export audit."""
from pathlib import Path
import hashlib, json
from PIL import Image

ROOT=Path(__file__).resolve().parent
items=[json.loads((ROOT/'approved-glock.json').read_text())]+json.loads((ROOT/'inventory.json').read_text())
inventory=items[1:]
audit=json.loads((ROOT/'export_audit.json').read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
issues=[]
for key in ('index','source','output'):
    values=[i[key] for i in inventory]
    if len(values)!=len(set(values)):issues.append('Duplicate inventory '+key)
source_folder=Path(inventory[0]['source']).parent
actual={str(p.resolve()).lower() for p in source_folder.glob('*.png')}
assigned={str(Path(i['source']).resolve()).lower() for i in inventory}
if actual!=assigned:issues.append({'source_coverage_difference':sorted(actual^assigned)})
models={}
rows=[]
for item in items:
    folder=Path(item['output']);errors=[]
    for name in ['Model.blend','Model.fbx','Model.glb','Preview.png','Alternate.png','Reference.png','validation.json','README.md']:
        if not (folder/name).exists():errors.append('Missing '+name)
    for name in ['Preview.png','Alternate.png','Reference.png']:
        if (folder/name).exists():
            try:
                with Image.open(folder/name) as im:im.verify()
            except Exception as exc:errors.append(name+' invalid image: '+str(exc))
    if (folder/'Reference.png').exists() and Path(item['source']).exists():
        if digest(folder/'Reference.png')!=digest(item['source']):errors.append('Reference changed')
    if (folder/'Model.glb').exists():
        model_hash=digest(folder/'Model.glb')
        if model_hash in models:errors.append('Duplicate GLB content: '+models[model_hash])
        models[model_hash]=item['name']
    inspected=audit.get(str(item['index']),{})
    blend=inspected.get('blend',{})
    if not blend.get('opened'):errors.append('Blender file not independently opened')
    if blend.get('unpacked_images') or blend.get('unloaded_images'):errors.append('Blender texture not packed/loaded')
    exports=inspected.get('formats',{})
    for ext in ['fbx','glb']:
        result=exports.get(ext,{})
        if not result or 'error' in result:errors.append(ext+' reimport missing/failed');continue
        if result['meshes']<1 or result['triangles']<1:errors.append(ext+' empty geometry')
        if not result['finite_coordinates']:errors.append(ext+' nonfinite geometry')
        if result['zero_area_faces']:errors.append(ext+' degenerate geometry')
        if not result['has_uvs'] or not result['image_count'] or result['unloaded_images']:errors.append(ext+' incomplete UV/texture data')
        if result['unwanted_cameras_or_lights']:errors.append(ext+' exported staging')
    if len(exports)==2 and all('triangles' in r for r in exports.values()):
        if exports['fbx']['triangles']!=exports['glb']['triangles']:errors.append('Export triangle counts differ')
    components=item.get('components',[])
    if item.get('representation')=='single_reusable':
        for ext,result in exports.items():
            if result.get('meshes')!=1:errors.append(ext+' reusable single is not one mesh')
    if components:
        if blend.get('parented_meshes'):errors.append('Review component meshes are parented')
        for ext,result in exports.items():
            if item.get('component_mode')!='additional' and result.get('meshes')!=len(components):errors.append(ext+' review components not separate meshes')
        for component in components:
            component_folder=folder/'components'/component
            for filename in ['Model.blend','Model.fbx','Model.glb']:
                if not (component_folder/filename).exists():errors.append(component+' missing '+filename)
            component_audit=audit.get(str(item['index'])+':'+component,{})
            component_blend=component_audit.get('blend',{})
            if not component_blend.get('opened') or component_blend.get('mesh_count_including_stage')!=1 or component_blend.get('parented_meshes') or component_blend.get('unpacked_images') or component_blend.get('unloaded_images'):errors.append(component+' Blender component is not independent and self-contained')
            for ext in ['glb','fbx']:
                result=component_audit.get('formats',{}).get(ext,{})
                if result.get('meshes')!=1 or result.get('zero_area_faces') or not result.get('finite_coordinates') or not result.get('image_count') or result.get('unloaded_images') or not result.get('has_uvs') or result.get('unwanted_cameras_or_lights'):errors.append(component+' '+ext+' audit failed')
    if item.get('rigged'):
        rig_report=json.loads((ROOT/'rig_audit.json').read_text()) if (ROOT/'rig_audit.json').exists() else {}
        for ext in ['blend','fbx','glb']:
            if not rig_report.get(str(item['index']),{}).get(ext,{}).get('passed'):errors.append(ext+' independent rig audit missing/failed')
    rows.append({'index':item['index'],'name':item['name'],'batch':item['batch'],'passed':not errors,'issues':errors})
report={'expected_items':len(items),'reusable_model_count':len(items)+sum(len(i.get('components',[])) if i.get('component_mode')=='additional' else max(0,len(i.get('components',[]))-1) for i in items),'source_images':len(actual),'passed_items':sum(r['passed'] for r in rows),'inventory_issues':issues,'items':rows,'studio_import_tested':False}
(ROOT/'delivery_verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
if issues or any(not r['passed'] for r in rows):raise SystemExit(1)
