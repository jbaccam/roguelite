"""Refresh packed/exported material and actual mesh review renders after atlas revision."""
import bpy,sys,shutil,json
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parent
for mob in sys.argv[sys.argv.index('--')+1:]:
    out=root/mob
    bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'))
    scene=bpy.context.scene
    scene.render.resolution_x=800;scene.render.resolution_y=800;scene.cycles.samples=12
    rig=bpy.data.objects['Rig'];meshes=[o for o in scene.objects if o.type=='MESH' and o.parent==rig]
    if mob in ['crab','hermit-crab','rock-throwing-crab','scorpion','snake'] and not rig.get('cream_tile_corrected'):
        geometry=json.loads((out/'Geometry.json').read_text())
        for o in meshes:
            for uv in o.data.uv_layers.active.data:
                u,v=uv.uv
                if .5<u<.75 and .25<v<.5:uv.uv=(u+.25,v+.50)
            o.data.calc_loop_triangles();uv=o.data.uv_layers.active
            geometry[o.name]['triangleUVs']=[[list(uv.data[l].uv) for l in t.loops] for t in o.data.loop_triangles]
        (out/'Geometry.json').write_text(json.dumps(geometry,separators=(',',':')))
        rig['cream_tile_corrected']=True
    shutil.copyfile(root/'Materials.png',out/'BaseColor.png')
    atlas=bpy.data.images.load(str(out/'BaseColor.png'),check_existing=False);atlas.pack()
    for o in meshes:
        for m in o.data.materials:
            for n in m.node_tree.nodes:
                if n.type=='TEX_IMAGE':n.image=atlas
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
    for o in meshes:o.select_set(True)
    bpy.context.view_layer.objects.active=rig
    actions={n:bpy.data.actions[n] for n in ['Idle','Move','Attack','Hit','Death']}
    fbxargs=dict(use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
    rig.animation_data.action=None
    for b in rig.pose.bones:b.location=(0,0,0);b.rotation_euler=(0,0,0);b.scale=(1,1,1)
    bpy.ops.export_scene.fbx(filepath=str(out/'Model.fbx'),bake_anim=False,**fbxargs)
    for clip,action in actions.items():
        rig.animation_data.action=action;scene.frame_start=1;scene.frame_end=int(action.frame_range[1])
        bpy.ops.export_scene.fbx(filepath=str(out/(clip+'.fbx')),bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0,**fbxargs)
    rig.animation_data.action=actions['Idle'];scene.frame_end=31;scene.frame_set(1)
    bpy.ops.export_scene.gltf(filepath=str(out/'Model.glb'),export_format='GLB',use_selection=True,export_animations=True,export_skins=True,export_animation_mode='ACTIONS')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Model.blend'))
    scene.render.filepath=str(out/'Preview.png');bpy.ops.render.render(write_still=True)
    coords=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    lo=Vector(tuple(min(v[i] for v in coords) for i in range(3)));hi=Vector(tuple(max(v[i] for v in coords) for i in range(3)));center=(lo+hi)/2;size=max(hi-lo)
    cam=scene.camera;original=cam.location.copy();cam.location=center+Vector((-1.3,1.8,.65))*size;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(out/'Back.png');bpy.ops.render.render(write_still=True)
    cam.location=original;cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.resolution_x=640;scene.render.resolution_y=640;scene.cycles.samples=12
    rig.animation_data.action=actions['Attack']
    for frame,name in [(11,'Windup'),(16,'Impact')]:
        scene.frame_set(frame);scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
    print('REFRESHED',mob,flush=True)
