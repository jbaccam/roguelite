"""Rigid chest rig, no keyframes. Run in Blender --background --threads 4."""
import bpy,bmesh,json,math,sys,struct,subprocess,shutil
from pathlib import Path
from mathutils import Vector,Matrix
HERE=Path(__file__).resolve().parent
OUT=HERE.parents[1]/'assets'/'33-pandoras-box'
HINGE=Vector((0,1.105,1.90))
bpy.context.preferences.filepaths.save_version=0

def geometry(objs):
 result={'mesh_count':len(objs),'vertices':0,'triangles':0,'loose_vertices':0,'zero_area_faces':0,'non_manifold_edges':0}
 for o in objs:
  bm=bmesh.new();bm.from_mesh(o.data)
  result['vertices']+=len(bm.verts);result['triangles']+=sum(len(f.verts)-2 for f in bm.faces)
  result['loose_vertices']+=sum(not v.link_faces for v in bm.verts);result['zero_area_faces']+=sum(f.calc_area()<1e-10 for f in bm.faces);result['non_manifold_edges']+=sum(not e.is_manifold for e in bm.edges);bm.free()
 return result
def evaluated(o):
 dg=bpy.context.evaluated_depsgraph_get();ev=o.evaluated_get(dg);return [ev.matrix_world@v.co for v in ev.data.vertices]
def weight_bone(o):
 names=set()
 for v in o.data.vertices:
  groups=[g for g in v.groups if g.weight>1e-7]
  assert len(groups)==1 and abs(groups[0].weight-1)<1e-6,(o.name,'not rigid weighted')
  names.add(o.vertex_groups[groups[0].group].name)
 assert len(names)==1,(o.name,names)
 return names.pop()
def pose_check(arm,meshes,angles=(30,60,90)):
 pb=arm.pose.bones['Lid_Hinge'];pb.matrix_basis=Matrix.Identity(4);bpy.context.view_layer.update()
 rest={o.name:evaluated(o) for o in meshes};bone_groups={o.name:weight_bone(o) for o in meshes}
 anchor=arm.matrix_world@pb.bone.head_local;axis=Vector((1,0,0))
 report=[]
 for deg in angles:
  delta=Matrix.Translation(anchor)@Matrix.Rotation(math.radians(-deg),4,axis)@Matrix.Translation(-anchor)
  pb.matrix=arm.matrix_world.inverted()@delta@arm.matrix_world@pb.bone.matrix_local;bpy.context.view_layer.update()
  fixed=rigid=motion=0
  for o in meshes:
   now=evaluated(o);before=rest[o.name]
   if bone_groups[o.name]=='Root':fixed=max(fixed,max((a-b).length for a,b in zip(now,before)))
   else:
    rigid=max(rigid,max((a-delta@b).length for a,b in zip(now,before)));motion=max(motion,max((a-b).length for a,b in zip(now,before)))
  assert fixed<2e-5 and rigid<2e-5 and motion>.20,(fixed,rigid,motion)
  report.append({'angle_degrees':deg,'body_max_displacement':fixed,'lid_max_rigid_transform_error':rigid,'lid_max_displacement':motion})
 pb.matrix_basis=Matrix.Identity(4);bpy.context.view_layer.update()
 return {'bone_hierarchy':{b.name:b.parent.name if b.parent else None for b in arm.data.bones},'hinge_world_anchor':list(anchor),'hinge_world_axis':[1,0,0],'rigid_weights':True,'body_meshes':sum(x=='Root' for x in bone_groups.values()),'lid_meshes':sum(x=='Lid_Hinge' for x in bone_groups.values()),'pose_samples':report,'actions':len(bpy.data.actions),'rest_pose_restored':True}

if '--audit' in sys.argv:
 ext=sys.argv[sys.argv.index('--audit')+1]
 bpy.ops.wm.read_factory_settings(use_empty=True)
 if ext=='glb':bpy.ops.import_scene.gltf(filepath=str(OUT/'Model.glb'))
 else:bpy.ops.import_scene.fbx(filepath=str(OUT/'Model.fbx'))
 arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
 shapes={pb.custom_shape for pb in arm.pose.bones if pb.custom_shape}
 meshes=[o for o in bpy.data.objects if o.type=='MESH' and o not in shapes]
 assert all(any(m.type=='ARMATURE' and m.object==arm for m in o.modifiers) for o in meshes)
 report=pose_check(arm,meshes);report.update(geometry(meshes));report['excluded_actual_bone_custom_shapes']=[o.name for o in shapes];report['scene_cameras_lights']=sum(o.type in {'CAMERA','LIGHT'} for o in bpy.data.objects)
 report['images']=[{'name':im.name,'loaded':im.has_data,'size':list(im.size)} for im in bpy.data.images if im.type=='IMAGE']
 for im in bpy.data.images:
  if im.type=='IMAGE':float(im.pixels[0])
 report['images']=[{'name':im.name,'loaded':im.has_data,'size':list(im.size)} for im in bpy.data.images if im.type=='IMAGE']
 welded_nonmanifold=0
 for o in meshes:
  bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6);welded_nonmanifold+=sum(not e.is_manifold for e in bm.edges);bm.free()
 report['non_manifold_edges_after_welding_uv_normal_seams']=welded_nonmanifold
 report['topology_note']='GLB can split vertices at UV and flat-normal seams; coincident seam vertices are welded only in a temporary audit mesh.'
 assert report['actions']==0 and report['scene_cameras_lights']==0
 (OUT/('rig_reimport_'+ext+'.json')).write_text(json.dumps(report,indent=2));print('AUDIT COMPLETE',ext,report);sys.exit()

source=HERE/'Pandora_Static_Source.blend'
if not source.exists():
 subprocess.run([bpy.app.binary_path,'--background','--threads','4','--python',str(HERE/'build_magic.py'),'--','33'],check=True)
 shutil.copyfile(OUT/'Model.blend',source)
bpy.ops.wm.open_mainfile(filepath=str(source))
asset=max((c for c in bpy.data.collections if c.name.startswith('ASSET')),key=lambda c:sum(o.type=='MESH' for o in c.objects))
stage=next(c for c in bpy.data.collections if c.name.startswith('REVIEW'))
scene=bpy.context.scene
original=list(asset.objects)
def move(o):
 for c in list(o.users_collection):c.objects.unlink(o)
 asset.objects.link(o)
def material(name,color):
 im=bpy.data.images.new(name+' texture',width=8,height=8,alpha=False);im.pixels[:]=list(color+(1,))*64;im.filepath_raw=str(OUT/'InteriorBaseColor.png');im.file_format='PNG';im.save();im.pack()
 m=bpy.data.materials.new(name);m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.8
 tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=im;m.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color']);return m
inside=material('Finished dark stone interior',(.19,.185,.21))
outer=bpy.data.objects['Stone coffer body'].data.materials[0]
def uv_flat(o,coord=(.5,.5)):
 for layer in list(o.data.uv_layers):o.data.uv_layers.remove(layer)
 uv=o.data.uv_layers.new(name='AtlasUV');uv.active_render=True
 for p in o.data.polygons:
  for i,li in enumerate(p.loop_indices):uv.data[li].uv=(coord[0]+(.0002 if i%2 else -.0002),coord[1]+(.0002 if i%3 else -.0002))
def add_box(name,loc,dims,mat,bevel=.02,uvcoord=(.5,.5)):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dims;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);move(o);o.data.materials.append(mat)
 if bevel:
  mod=o.modifiers.new('Finished edge bevel','BEVEL');mod.width=bevel;mod.segments=1;bpy.ops.object.modifier_apply(modifier=mod.name)
 uv_flat(o,uvcoord);return o

# Cut through all three original solid caps so the cavity remains genuinely open.
for name in ['Stone coffer body','Dark slightly open lid seam','Purple magic within seam']:
 o=bpy.data.objects[name];o.data.materials.append(inside)
 bpy.ops.mesh.primitive_cube_add(size=1,location=(0,0,1.88));cutter=bpy.context.object;cutter.name='TEMP cavity cutter';cutter.dimensions=(2.23,1.54,3.0);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 cutter.data.materials.append(outer);cutter.data.materials.append(inside)
 for p in cutter.data.polygons:p.material_index=1
 bpy.context.view_layer.objects.active=o
 mod=o.modifiers.new('Real open chest cavity','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter;bpy.ops.object.modifier_apply(modifier=mod.name)
 bpy.data.objects.remove(cutter,do_unlink=True)
 for p in o.data.polygons:
  if p.material_index==1:
   for li in p.loop_indices:o.data.uv_layers.active.data[li].uv=(.5,.5)

# Add a shallow inset on the actual lid underside; it fits entirely inside the cavity rim.
add_box('Lid underside inset stone panel',(0,0,1.833),(2.10,1.40,.042),inside,.018)
gold_uv=tuple(bpy.data.objects['Heavy central clasp'].data.uv_layers.active.data[0].uv)
for x in [-1.005,1.005]:add_box('Lid underside gold edge',(x,0,1.807),(.035,1.33,.016),outer,.005,gold_uv)
for y in [-.645,.645]:add_box('Lid underside gold edge',(0,y,1.807),(2.04,.035,.016),outer,.005,gold_uv)
for x in [-.76,.76]:
 add_box('Rear fixed hinge leaf',(x,1.015,1.72),(.31,.10,.33),outer,.012,gold_uv)
 bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=.10,depth=.34,location=(x,HINGE.y,HINGE.z),rotation=(0,math.pi/2,0))
 barrel=bpy.context.object;barrel.name='Rear hinge barrel';move(barrel);barrel.data.materials.append(outer);uv_flat(barrel,gold_uv)
 add_box('Lid hinge leaf',(x,1.092,2.04),(.26,.10,.30),outer,.012,gold_uv)

lid_prefixes=('Heavy chamfered stone lid','Raised inset lid panel','Lid hooked corner binding','Top gem gold setting','Lid amethyst pyramid','Heavy central clasp','Clasp amethyst','Lid underside','Lid hinge')
meshes=[o for o in asset.objects if o.type=='MESH'];lid=[o for o in meshes if o.name.startswith(lid_prefixes)];body=[o for o in meshes if o not in lid]
assert len(body)>10 and len(lid)>10,(len(body),len(lid))
for o in meshes:
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.dissolve_degenerate(bm,dist=1e-7,edges=list(bm.edges));bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free()

bpy.ops.object.armature_add(location=(0,0,0));arm=bpy.context.object;arm.name='Pandora_Chest_Rig';move(arm);arm.show_in_front=True
bpy.ops.object.mode_set(mode='EDIT');root=arm.data.edit_bones[0];root.name='Root';root.head=(0,0,0);root.tail=(0,0,.6)
bone=arm.data.edit_bones.new('Lid_Hinge');bone.head=HINGE;bone.tail=HINGE+Vector((.8,0,0));bone.parent=root;bone.use_connect=False
bpy.ops.object.mode_set(mode='OBJECT')
arm['Rig instructions']='Pose Mode: Lid_Hinge local Y rotation, 0 closed, -90 degrees open. No animation actions.'
for o in meshes:
 group=o.vertex_groups.new(name='Lid_Hinge' if o in lid else 'Root');group.add(list(range(len(o.data.vertices))),1,'REPLACE')
 mod=o.modifiers.new('Rigid chest skeleton','ARMATURE');mod.object=arm
 world=o.matrix_world.copy();o.parent=arm;o.matrix_world=world
for o in bpy.data.objects:o.animation_data_clear()
for action in list(bpy.data.actions):bpy.data.actions.remove(action)
report=pose_check(arm,meshes)
report['cavity']={'inner_x_width':2.23,'inner_y_depth':1.54,'floor_z':.38,'rim_top_z':1.91,'lid_underside_finished':True,'solid_caps_removed':['Stone coffer body','Dark slightly open lid seam','Purple magic within seam']}
# Ray proof: with the lid open, a vertical ray at cavity center reaches the interior floor, not a cap.
arm.pose.bones['Lid_Hinge'].rotation_mode='XYZ';arm.pose.bones['Lid_Hinge'].rotation_euler=(0,-math.pi/2,0);bpy.context.view_layer.update()
arm.update_tag();bpy.context.view_layer.update()
deps=bpy.context.evaluated_depsgraph_get();hit,loc,normal,face,obj,matrix=scene.ray_cast(deps,Vector((0,0,1.93)),Vector((0,0,-1)))
assert hit and abs(loc.z-.38)<1e-4,(hit,list(loc),obj.name if obj else None)
report['open_cavity_center_ray_hit']={'object':obj.name,'z':loc.z,'expected_floor_z':.38}

# Save a temporary 90-degree posed still with all moving geometry visible; no keyframe is created.
cam=scene.camera;orig_cam=cam.matrix_world.copy();orig_scale=cam.data.ortho_scale
def frame_pose(offset):
 coords=[v for o in meshes for v in evaluated(o)];mn=Vector([min(v[j] for v in coords) for j in range(3)]);mx=Vector([max(v[j] for v in coords) for j in range(3)]);center=(mn+mx)/2
 cam.location=center+Vector(offset);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();inv=cam.rotation_euler.to_matrix().transposed();pc=[inv@(v-center) for v in coords];cam.data.ortho_scale=max(max(v[j] for v in pc)-min(v[j] for v in pc) for j in [0,1])*1.18
scene.cycles.samples=24;frame_pose((-6,-10,8));scene.render.filepath=str(OUT/'Rig_Pose_Check.png');bpy.ops.render.render(write_still=True)
arm.pose.bones['Lid_Hinge'].matrix_basis=Matrix.Identity(4);bpy.context.view_layer.update();cam.matrix_world=orig_cam;cam.data.ortho_scale=orig_scale
stats=geometry(meshes);assert stats['zero_area_faces']==0 and stats['loose_vertices']==0 and stats['non_manifold_edges']==0,stats
stats.update({'name':'Pandoras Box','material_count':len(set(m.name for o in meshes for m in o.data.materials)),'packed_texture':True,'uv':'Original exterior atlas preserved; separate packed stone interior atlas','armature_count':1,'animation_count':0,'limitations':['Unseen hollow interior and lid underside inferred.','Roblox Studio import and runtime hinge control not tested.'],'intentional_intersections':'Closed ornamental components overlap their support meshes; all lid ornaments rigidly follow the lid.'})
(OUT/'validation.json').write_text(json.dumps(stats,indent=2));(OUT/'rig_validation.json').write_text(json.dumps(report,indent=2))
bpy.ops.object.select_all(action='DESELECT')
for o in meshes+[arm]:o.select_set(True)
bpy.context.view_layer.objects.active=arm
bpy.ops.export_scene.fbx(filepath=str(OUT/'Model.fbx'),use_selection=True,object_types={'MESH','ARMATURE'},add_leaf_bones=False,bake_anim=False,use_armature_deform_only=True,path_mode='COPY',embed_textures=True,axis_forward='-Z',axis_up='Y')
bpy.ops.export_scene.gltf(filepath=str(OUT/'Model.glb'),export_format='GLB',use_selection=True,export_animations=False,export_materials='EXPORT')
raw=(OUT/'Model.glb').read_bytes();length,typ=struct.unpack_from('<II',raw,12);doc=json.loads(raw[20:20+length]);assert not doc.get('animations') and len(doc.get('skins',[]))==1
report['raw_glb']={'skins':len(doc['skins']),'animations':len(doc.get('animations',[])),'mesh_payloads':len(doc.get('meshes',[])),'cameras':len(doc.get('cameras',[])),'joint_names':[doc['nodes'][j]['name'] for j in doc['skins'][0]['joints']]}
(OUT/'rig_validation.json').write_text(json.dumps(report,indent=2))
scene.render.filepath=str(OUT/'Preview.png');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Model.blend'));bpy.ops.render.render(write_still=True)
frame_pose((3,11,7));scene.render.filepath=str(OUT/'Alternate.png');bpy.ops.render.render(write_still=True)
for o in list(bpy.data.objects):
 if o not in meshes+[arm]:bpy.data.objects.remove(o,do_unlink=True)
scene.camera=None;bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Model.blend'))
(OUT/'README.md').write_text('''# Pandora's Box — rigid opening rig

The approved exterior is preserved. The stone coffer and both seam caps now have a real hollow cavity, with a finished dark-stone floor/walls and inset lid underside. Hidden surfaces are inferred from the reference.

## Control
Select **Pandora_Chest_Rig**, enter Pose Mode, select **Lid_Hinge**, and rotate its **local Y axis from 0 degrees (closed) to -90 degrees (open)**. This is a rear-edge hinge parallel to model X at `(0, 1.105, 1.90)` in Blender coordinates. Root moves the entire chest. Lid, clasp, amethyst, top panel and all lid ornaments have full rigid weights to Lid_Hinge; body and rim geometry have full weights to Root. There are no constraints, actions, clips, keyframes or leaf bones.

Model.blend, Model.fbx and Model.glb are saved/exported in the closed rest pose. Rig_Pose_Check.png is a temporary 90-degree posed render, not an animation. Preview.png and Alternate.png show the closed rest model. Export payload contains only meshes and the two-bone armature. Textures are packed and embedded.

Rebuild with Blender background mode and `batches/magic/rig_pandora.py`; it uses the preserved approved static source when available. If that local backup is absent, the script automatically runs `build_magic.py -- 33` to regenerate only the static Pandora source first (the inventory reference image must be accessible). Fresh import tests use `--audit glb` and `--audit fbx`. Numerical motion/cavity checks are in rig_validation.json and rig_reimport_*.json. Blender's GLB importer may create a bone-display custom-shape Icosphere in glTF_not_exported; only the actual bone custom-shape helper is excluded from payload geometry checks.

Decorative components intentionally overlap supports. Closed components remain manifold. Keep the two skinning groups if combining meshes. Roblox Studio import, runtime controls and collision configuration have not been tested.
''')
print('RIG COMPLETE',stats,flush=True)
