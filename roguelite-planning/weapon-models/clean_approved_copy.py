"""Remove invisible collapsed bevel faces in the delivery copy; original stays untouched."""
import bpy,bmesh,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'assets'/'00-glock-approved'
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Model.blend'))
o=bpy.data.objects['Glock_Reference_Test']
bm=bmesh.new();bm.from_mesh(o.data)
before={'vertices':len(bm.verts),'faces':len(bm.faces),'zero_area_faces':sum(f.calc_area()<1e-10 for f in bm.faces)}
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-6)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
after={'vertices':len(bm.verts),'faces':len(bm.faces),'zero_area_faces':sum(f.calc_area()<1e-10 for f in bm.faces),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges)}
assert after['zero_area_faces']==0,after
assert after['nonmanifold_edges']==0,after
bm.to_mesh(o.data);bm.free();o.data.update()
for image in bpy.data.images:
    if image.name.startswith('Glock_BaseColor'):
        image.filepath=str(ROOT/'BaseColor.png');image.pack()
bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
bpy.ops.export_scene.fbx(filepath=str(ROOT/'Model.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
bpy.ops.export_scene.gltf(filepath=str(ROOT/'Model.glb'),use_selection=True,export_format='GLB',export_animations=False)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Model.blend'))
path=ROOT/'validation.json';stats=json.loads(path.read_text());stats.update(after)
stats['triangles']=sum(len(p.vertices)-2 for p in o.data.polygons)
stats['cleanup']='Delivery copy only: welded coincident vertices and dissolved invisible zero-area bevel faces; original approved file untouched.'
stats['before_cleanup']=before
path.write_text(json.dumps(stats,indent=2))
print('CLEANED_APPROVED_DELIVERY_COPY',json.dumps(stats))
