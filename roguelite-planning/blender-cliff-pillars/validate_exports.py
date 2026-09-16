"""Re-import each generated FBX and GLB in Blender to verify geometry exists."""
import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
report={'blender_version':bpy.app.version_string,'files':{},'passed':True}
for ext in ('fbx','glb'):
    paths=sorted((ROOT/'exports'/ext).glob('*.'+ext))
    if len(paths)!=6:report['passed']=False
    for path in paths:
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        if ext=='fbx':bpy.ops.import_scene.fbx(filepath=str(path))
        else:bpy.ops.import_scene.gltf(filepath=str(path))
        objs=[o for o in bpy.context.scene.objects if o.type=='MESH']
        triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in objs)
        result={'mesh_objects':len(objs),'triangles':triangles,'bytes':path.stat().st_size,'ok':len(objs)==2 and triangles>0}
        report['files'][str(path.relative_to(ROOT))]=result
        report['passed']=report['passed'] and result['ok']
(ROOT/'validation-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
if not report['passed']:raise SystemExit(1)
