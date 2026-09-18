"""Independent parent audit. Reads assets; never modifies their blend/export files."""
import bpy, json, math, sys, struct
from pathlib import Path

ROOT=Path(__file__).resolve().parent
inventory=[json.loads((ROOT/'approved-glock.json').read_text())]+json.loads((ROOT/'inventory.json').read_text())
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
if args:inventory=[i for i in inventory if str(i['index']) in args]
expanded=[]
for item in inventory:
    expanded.append(item)
    for component in item.get('components',[]):
        expanded.append({'index':str(item['index'])+':'+component,'name':item['name']+' / '+component,'output':str(Path(item['output'])/'components'/component),'is_component':True})
inventory=expanded
report={}
for item in inventory:
    folder=Path(item['output']);result={'name':item['name'],'formats':{}}
    try:
        bpy.ops.wm.open_mainfile(filepath=str(folder/'Model.blend'))
        referenced={n.image for o in bpy.context.scene.objects if o.type=='MESH' for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image}
        meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
        result['blend']={'opened':True,'mesh_count_including_stage':len(meshes),'parented_meshes':[o.name for o in meshes if o.parent],'referenced_images':len(referenced),'unpacked_images':[im.name for im in referenced if not im.packed_file],'unloaded_images':[im.name for im in referenced if not all(im.size)]}
    except Exception as exc:result['blend']={'opened':False,'error':str(exc)}
    for ext in ['glb','fbx']:
        path=folder/('Model.'+ext)
        if not path.exists():result['formats'][ext]={'error':'missing'};continue
        try:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(path))
            else:bpy.ops.import_scene.fbx(filepath=str(path))
            custom_shapes={pb.custom_shape for o in bpy.context.scene.objects if o.type=='ARMATURE' for pb in o.pose.bones if pb.custom_shape}
            meshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o not in custom_shapes]
            unwanted=[o.name for o in bpy.context.scene.objects if o.type in {'CAMERA','LIGHT'}]
            triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
            points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
            finite=all(math.isfinite(c) for p in points for c in p)
            dimensions=[max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)] if points else []
            images=[n.image for o in meshes for m in o.data.materials if m and m.use_nodes for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
            bad_images=[im.name for im in images if not all(im.size)]
            result['formats'][ext]={'meshes':len(meshes),'triangles':triangles,'finite_coordinates':finite,'bounds':dimensions,'unwanted_cameras_or_lights':unwanted,'image_count':len(images),'unloaded_images':bad_images,'has_uvs':all(len(o.data.uv_layers)>0 for o in meshes),'uv_layer_counts':sorted(set(len(o.data.uv_layers) for o in meshes)),'zero_area_faces':sum(p.area<1e-10 for o in meshes for p in o.data.polygons)}
            result['formats'][ext]['importer_bone_display_helpers']=[o.name for o in custom_shapes]
            if ext=='glb':
                data=path.read_bytes();size,kind=struct.unpack_from('<II',data,12);payload=json.loads(data[20:20+size])
                result['formats'][ext]['file_mesh_instances']=sum('mesh' in node for node in payload.get('nodes',[]))
                assert result['formats'][ext]['file_mesh_instances']==len(meshes),'Imported mesh count differs from actual GLB payload'
        except Exception as exc:result['formats'][ext]={'error':str(exc)}
    report[str(item['index'])]=result
    print('AUDITED',item['index'],item['name'],flush=True)
path=ROOT/'export_audit.json'
existing=json.loads(path.read_text()) if path.exists() else {}
existing.update(report);path.write_text(json.dumps(existing,indent=2))
print('AUDIT_DONE',len(report),flush=True)
