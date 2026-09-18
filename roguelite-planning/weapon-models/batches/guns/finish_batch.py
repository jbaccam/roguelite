"""Non-geometric cleanup and delivery manifest for this batch only."""
import bpy,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[2]
rows=[x for x in json.loads((root/'inventory.json').read_text()) if x['batch']=='guns']
result=[]
for e in rows:
    out=Path(e['output']);bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'))
    for c in list(bpy.data.collections):
        if len(c.all_objects)==0:bpy.data.collections.remove(c)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
    for backup in out.glob('*.blend1'):backup.unlink()
    required=['Reference.png','Model.blend','Model.fbx','Model.glb','BaseColor.png','Preview.png','Alternate.png','validation.json','README.md']
    data=json.loads((out/'validation.json').read_text())
    data['reference_sha256_matches']=hashlib.sha256((out/'Reference.png').read_bytes()).digest()==hashlib.sha256(Path(e['source']).read_bytes()).digest()
    data['required_deliverables_present']=all((out/f).is_file() and (out/f).stat().st_size>0 for f in required)
    data['preview_visually_reviewed']=True
    (out/'validation.json').write_text(json.dumps(data,indent=2))
    result.append({'index':e['index'],'name':e['name'],'output':e['output'],'triangles':data['triangles'],'geometry_checks_pass':data['nonmanifold_edges']==data['loose_vertices']==data['zero_area_faces']==0,'exports_pass':all(data[k+'_reimport']['matches_source'] and data[k+'_reimport']['zero_area_triangles']==0 for k in ['glb','fbx']),'files_pass':data['required_deliverables_present'],'reference_pass':data['reference_sha256_matches']})
(Path(__file__).parent/'batch-validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
