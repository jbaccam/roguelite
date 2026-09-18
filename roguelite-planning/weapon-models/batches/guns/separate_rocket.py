"""Empty launcher plus independently exportable stylized rocket. No animation."""
import bpy,bmesh,sys,json,math,importlib.util
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('guns',HERE/'build_guns.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
ENTRY=next(e for e in g.INVENTORY if e['index']==11)
OUT=Path(ENTRY['output']);ROCKET=OUT/'components'/'Rocket'
BUILD_BOUNDS={}
def capture(key):
    v=[o.matrix_world@v.co for o in g.asset.objects for v in o.data.vertices]
    BUILD_BOUNDS[key]={'min':[min(p[i] for p in v) for i in range(3)],'max':[max(p[i] for p in v) for i in range(3)]}
def empty_launcher():
    g.rocket()
    for name in ['Olive rocket nose','Yellow nose band','Red conical tip','Long olive tube','Front polygon flared collar']:
        bpy.data.objects.remove(g.asset.objects[name],do_unlink=True)
    for ob in list(g.asset.objects):
        if ob.name.startswith('Charcoal tube clamp'):bpy.data.objects.remove(ob,do_unlink=True)
    for x in [-2.09,-1.18,.34]:
        g.lathe('Hollow charcoal tube clamp',[(x-.11,.54),(x-.085,.59),(x+.09,.59),(x+.115,.54),(x+.115,.515),(x-.11,.515),(x-.11,.54)],g.CHAR,10,z=2.10,caps=False)
    # Deep blind visual bore: a true annulus at the opening with an actual inner wall.
    tube=g.lathe('Hollow olive launcher tube',[(-2.55,.45),(-2.40,.53),(.55,.53),(.73,.60),(1.72,.60),(1.72,.50),(-.90,.43)],g.OLIVE,10,z=2.10)
    tube.data.materials.append(g.DARK)
    for p in tube.data.polygons:
        if 50<=p.index<60 or p.index==61:p.material_index=1
    # Closing the cross section, instead of cap disks, keeps the front ring genuinely open.
    rim=g.lathe('Open polygon flared muzzle rim',[(1.42,.61),(1.58,.81),(1.89,.87),(2.04,.79),(2.04,.67),(1.84,.58),(1.42,.52),(1.42,.61)],g.CHAR,10,z=2.10,caps=False)
    rim.data.materials.append(g.DARK)
    for p in rim.data.polygons:
        if 40<=p.index<60:p.material_index=1
    capture('launcher')
def full_rocket():
    g.lathe('Complete olive rocket exterior',[(-.80,.19),(-.72,.27),(-.55,.29),(1.43,.29),(1.64,.43),(1.91,.47),(2.42,.29)],g.OLIVE,10,z=2.10)
    g.lathe('Yellow reference warhead band',[(1.86,.477),(1.91,.482),(1.99,.454)],g.YELLOW,10,z=2.10)
    g.lathe('Red reference conical nose',[(2.38,.30),(2.69,.065),(2.72,.025)],g.RED,10,z=2.10)
    g.lathe('Olive rear collar',[(-.76,.25),(-.67,.305),(-.53,.305),(-.49,.29)],g.OLIVE,10,z=2.10)
    # Four plain stylized tail vanes; hidden rear is inferred, no engine or mechanisms.
    for i in range(4):
        vane=g.prism('Tail vane %d'%(i+1),[(-.68,2.10+.26),(-.57,2.10+.40),(-.18,2.10+.40),(.19,2.10+.285)],.055,g.OLIVE,.008)
        a=i*math.pi/2
        for v in vane.data.vertices:
            y,z=v.co.y,v.co.z-2.10;v.co.y=y*math.cos(a)-z*math.sin(a);v.co.z=2.10+y*math.sin(a)+z*math.cos(a)
    capture('rocket')

def audit_current(ob):
    bm=bmesh.new();bm.from_mesh(ob.data)
    r={'vertices':len(ob.data.vertices),'triangles':len(ob.data.polygons),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'loose_vertices':sum(not v.link_edges for v in bm.verts),'zero_area_faces':sum(f.calc_area()<1e-10 for f in bm.faces),'dimensions':list(ob.dimensions)};bm.free();return r

def repivot_and_audit(folder,key,anchor_original):
    bpy.ops.wm.open_mainfile(filepath=str(folder/'Model.blend'))
    scene=bpy.context.scene;col=next(c for c in bpy.data.collections if c.name.endswith('| EXPORT') and c.objects)
    ob=next(o for o in col.objects if o.type=='MESH')
    original_z_shift=-BUILD_BOUNDS[key]['min'][2]
    anchor_world=Vector(anchor_original)+Vector((0,0,original_z_shift))
    # Place the origin on the common longitudinal axis, at the warhead's rear shoulder.
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    scene.cursor.location=anchor_world;bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    ob['ComponentRole']='Empty launcher' if key=='launcher' else 'Separate complete rocket'
    ob['ForwardAxis']='+X';ob['Animation']='None; separate static prop ready for later scripting'
    ob['InsertionAnchorOriginal']=[1.64,0,2.10]
    for c in list(bpy.data.collections):
        if not c.all_objects:bpy.data.collections.remove(c)
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'Model.blend'))
    # Component files use centered local geometry AND a zero root transform.
    # Main launcher retains its approved world presentation, with its origin on that same socket.
    transform_before=list(ob.location)
    if key=='rocket':ob.location=(0,0,0)
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    bpy.ops.export_scene.fbx(filepath=str(folder/'Model.fbx'),use_selection=True,object_types={'MESH'},bake_anim=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(folder/'Model.glb'),use_selection=True,export_format='GLB',export_animations=False)
    stats=json.loads((folder/'validation.json').read_text());stats['geometry']=audit_current(ob)
    stats['pivot']={'type':'Warhead rear shoulder / insertion socket on centerline','local_forward':'+X','blend_world_location':transform_before,'export_root_translation':[0,0,0] if key=='rocket' else transform_before}
    stats['separate_component']=key=='rocket';stats['contains_rocket']=key=='rocket'
    if key=='launcher':
        local_origin=ob.matrix_world.inverted()@Vector((2.20,0,2.10+original_z_shift))
        hit,loc,normal,face=ob.ray_cast(local_origin,Vector((-1,0,0)))
        hitworld=ob.matrix_world@loc
        stats['empty_bore_ray_check']={'hit':hit,'ray_from_original':[2.20,0,2.10],'first_axial_surface_original_x':hitworld.x,'expected_backstop_x':-.90,'open_depth_from_muzzle':2.04-hitworld.x,'pass':hit and abs(hitworld.x+.90)<.001}
    for ext in ['glb','fbx']:
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(folder/'Model.glb'))
        else:bpy.ops.import_scene.fbx(filepath=str(folder/'Model.fbx'))
        objs=list(bpy.context.scene.objects);meshes=[o for o in objs if o.type=='MESH'];tris=0;deg=0;images=[]
        for o in meshes:
            o.data.calc_loop_triangles();tris+=len(o.data.loop_triangles)
            for t in o.data.loop_triangles:
                a,b,c=[o.data.vertices[i].co for i in t.vertices];deg+=int((b-a).cross(c-a).length<2e-10)
            for mat in o.data.materials:
                images.extend(n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
        for im in images:
            if len(im.pixels):_pixel=im.pixels[0]
        stats[ext+'_reimport']={'mesh_objects':len(meshes),'nonmesh_objects':len(objs)-len(meshes),'triangles':tris,'matches_source':tris==stats['triangles'],'zero_area_triangles':deg,'UV':all(bool(o.data.uv_layers) for o in meshes),'texture_images':len(images),'textures_loaded':all(im.has_data for im in images),'passed':len(meshes)==1 and len(objs)==1 and tris==stats['triangles'] and deg==0 and bool(images) and all(im.has_data for im in images)}
    (folder/'validation.json').write_text(json.dumps(stats,indent=2))
    for backup in folder.glob('*.blend1'):backup.unlink()
    return stats

g.BUILDERS[11]=empty_launcher;g.deliver(ENTRY)
component=dict(ENTRY,name='Rocket',output=str(ROCKET));g.BUILDERS[11]=full_rocket;g.deliver(component)
launcher=repivot_and_audit(OUT,'launcher',(1.64,0,2.10))
rocket=repivot_and_audit(ROCKET,'rocket',(1.64,0,2.10))
rig={'status':'Static separated assets; no animations','launcher':'Model.blend / Model.fbx / Model.glb','rocket_files':'components/Rocket/Model.blend / Model.fbx / Model.glb','launcher_contains_rocket':False,'independent_exports':True,'launcher_bore':{'axis':'+X','nominal_inner_radius_at_tube_front':.50,'inner_radius_at_backstop':.43,'muzzle_rim_x_original':2.04,'backstop_x_original':-.90,'clear_centerline_depth':2.94},'rocket':{'forward_axis':'+X','tip_x_local':1.08,'rear_x_local':-2.44,'maximum_radius':.482,'tail_fin_radius_max':.401,'full_length':3.52,'pivot':'Warhead rear shoulder, on centerline'},'alignment':{'coordinate_system':'Blender right-handed Z-up, +X forward; units match primary model','launcher_socket_world':launcher['pivot']['blend_world_location'],'rocket_export_root':[0,0,0],'rocket_loaded_matrix_relative_to_launcher_object':'Identity: same rotation, position and scale as the launcher mesh object because both origins share the insertion shoulder.','rocket_blend_to_loaded_world_translation':[launcher['pivot']['blend_world_location'][i]-rocket['pivot']['blend_world_location'][i] for i in range(3)],'fbx_axes':{'forward':'-Z','up':'Y'},'glb_conversion':'Blender exporter converts Z-up to glTF Y-up for both assets consistently.'},'checks':{'empty_bore_ray_pass':launcher['empty_bore_ray_check']['pass'],'launcher_round_trips':all(launcher[x+'_reimport']['passed'] for x in ['fbx','glb']),'rocket_round_trips':all(rocket[x+'_reimport']['passed'] for x in ['fbx','glb']),'launcher_triangles':launcher['triangles'],'rocket_triangles':rocket['triangles']},'limitations':['Hidden rocket rear is an inferred stylized cylinder with four low-profile tail fins.','No functional internal mechanism or engine details.','No animation, attachments in Studio, or gameplay scripts added.']}
(OUT/'rig_validation.json').write_text(json.dumps(rig,indent=2))
(ROCKET/'rig_validation.json').write_text(json.dumps(rig,indent=2))
(OUT/'README.md').write_text('# Empty Rocket Launcher\n\nThe primary Model.blend/FBX/GLB contain the launcher only. Its front is a genuine open annular rim with a modeled inner wall and a dark closed backstop 2.94 units behind the muzzle. Preview and Alternate show the empty launcher.\n\nThe separate full rocket is in components/Rocket. Both mesh origins share the warhead rear shoulder / insertion socket, +X forward in Blender. Set rocket exported root transform to the launcher mesh transform to reproduce the loaded alignment. Full coordinate details and actual bore ray/standalone export checks are in rig_validation.json and validation.json.\n\nRebuild using batches/guns/separate_rocket.py with Blender --background --threads 4. Single packed base-color atlas per asset. No animation or Studio integration was added.\n')
(ROCKET/'README.md').write_text('# Separate Rocket\n\nIndependent complete stylized low-poly rocket. The olive forward body, yellow band, and red conical tip match the visible reference. The hidden rear is inferred as a plain olive cylinder with four shallow tail vanes; it has no functional internals.\n\nThe pivot is the rear shoulder of the visible forward body, on the +X longitudinal axis. Standalone exports have zero root translation. Position/rotate/scale the exported rocket to match the launcher mesh object for loaded alignment. Blender review staging is separate and excluded from exports. See rig_validation.json for measurements and coordinate conversion; validation.json contains fresh standalone GLB/FBX checks. No animation or Studio integration.\n')
print('SEPARATION_COMPLETE',json.dumps(rig),flush=True)

