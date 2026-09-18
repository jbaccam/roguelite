import bpy, math, json
from pathlib import Path
from mathutils import Vector, Matrix
OUT=Path(__file__).parent
SRC=OUT.parents[2]/'weapon-models/studio-import/Weapon_Showcase.blend'
bpy.ops.wm.open_mainfile(filepath=str(SRC))
o=bpy.data.objects['W03_Katana']
pts=[o.matrix_world@v.co for v in o.data.vertices]
vs=[Vector((-p.x,p.z,p.y)) for p in pts]
lo=Vector([min(p[i] for p in vs)for i in range(3)]);hi=Vector([max(p[i] for p in vs)for i in range(3)])
g=json.loads((OUT.parent/'katana-geometry.json').read_text())
rot=Matrix.Rotation(.97,3,'Z');grip=Vector(g['grip'])
vs=[rot@((p-(lo+hi)/2)*g['meshScale'])-grip for p in vs]
# Same 180-degree facing correction as the combat template. Blender uses Z up.
for v,p in zip(o.data.vertices,vs):v.co=(-p.x,p.z,p.y)
o.matrix_world=Matrix.Identity(4);o.name='Katana_User_Scale'
for ob in list(bpy.data.objects):
 if ob!=o:bpy.data.objects.remove(ob,do_unlink=True)
for im in bpy.data.images:
 if im.source=='FILE':
  try:im.pack()
  except:pass
def mat(name,color,metal=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1);p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=.65
 return m
body=mat('Avatar | slate',(0.24,.38,.50));skin=mat('Avatar | warm neutral',(.72,.66,.55));target=mat('Rear zombie | moss',(.29,.44,.20));floor=mat('Floor',(.11,.14,.18));mark=mat('Clearance guide',(.18,.28,.34));white=mat('Labels',(.8,.87,.91))
def cube(name,loc,scale,material,bevel=.06):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);q=bpy.context.object;q.name=name;q.dimensions=scale;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);q.data.materials.append(material)
 if bevel:mod=q.modifiers.new('Soft corners','BEVEL');mod.width=bevel;mod.segments=1;q.modifiers.new('Normals','WEIGHTED_NORMAL')
 return q
def proxy(prefix,x,y,material):
 cube(prefix+' torso',(x,y,3.1),(2,1,2),material)
 cube(prefix+' head',(x,y,4.6),(1.15,1.05,1),skin if prefix=='Avatar' else material)
 for side in [-1,1]:
  cube(prefix+' leg',(x+side*.52,y,1.1),(.85,.9,2),material)
  cube(prefix+' arm',(x+side*1.38,y,3.05),(.6,.75,1.85),material)
 # Face points toward -Y; establishes which side is behind.
 for xx in [-.24,.24]:cube(prefix+' eye',(x+xx,y-.534,4.7),(.13,.025,.14),floor,.01)
proxy('Avatar',0,0,body);proxy('Rear target',0,5,target);proxy('Front target',0,-5,target)
cube('Floor',(0,1,-.12),(23,23,.2),floor)
def text(label,loc,size=.42):
 bpy.ops.object.text_add(location=loc);q=bpy.context.object;q.data.body=label;q.data.size=size;q.data.align_x='CENTER';q.data.extrude=.001;q.data.materials.append(white)
 return q
text('FRONT',(0,-3.6,.012),.4);text('REAR TARGET',(0,6.3,.012),.4)
text('FIXED RIGHT SLOT',(4,-2,.012),.32)
bpy.ops.mesh.primitive_torus_add(major_radius=1.8,minor_radius=.025,major_segments=64,minor_segments=6,location=(0,0,.02));bpy.context.object.name='Avatar clearance footprint';bpy.context.object.data.materials.append(mark)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=8
scene.cycles.use_denoising=True
scene.render.resolution_x=800;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.fps=30;scene.frame_start=1;scene.frame_end=135
scene.world=bpy.data.worlds.new('Preview World');scene.world.color=(.25,.25,.25)
def area(name,loc,power,size):
 bpy.ops.object.light_add(type='AREA',location=loc);q=bpy.context.object;q.name=name;q.data.energy=power;q.data.shape='DISK';q.data.size=size;q.rotation_euler=(Vector((0,2,2))-q.location).to_track_quat('-Z','Y').to_euler()
area('Key',(3,-6,13),1800,9);area('Fill',(-6,4,8),1300,8)
bpy.ops.object.camera_add(location=(15,-18,25));cam=bpy.context.object;cam.rotation_euler=(Vector((1,0,2))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=19;scene.camera=cam
def smooth(t):t=max(0,min(1,t));return t*t*(3-2*t)
def pose(t,side=1):
 # .09 outward windup, .11 horizontal slash, .16 raised recovery.
 tilt=0;angle=0;x=3.25;y=0
 if 0<=t<.09:
  u=smooth(t/.09);tilt=math.pi/2*u;angle=math.radians(40);x+=.85*u;y=1.1*u
 elif .09<=t<.20:
  u=smooth((t-.09)/.11);tilt=math.pi/2;angle=math.radians(40+115*u);x=4.1;y=1.1
 elif .20<=t<.36:
  u=smooth((t-.20)/.10);retract=smooth((t-.30)/.06);tilt=math.pi/2*(1-u);angle=math.radians(155);x=4.1-.85*retract;y=1.1*(1-retract)
 angle*=side;y*=side
 direction=Vector((math.cos(angle),math.sin(angle),0));blade=direction*math.sin(tilt)+Vector((0,0,1))*math.cos(tilt)
 across=Vector((-direction.y,direction.x,0));depth=blade.cross(across)
 m=Matrix((across,depth,blade)).transposed().to_4x4();m.translation=Vector((x,y,3.15));return m
minimum=999
for i in range(1001):
 m=pose(i/1000*.36)
 for v in o.data.vertices:
  p=m@v.co
  if 1<p.z<5.5:minimum=min(minimum,math.hypot(p.x,p.y))
for frame in range(1,136):
 sec=(frame-1)/30
 # Mirrored front cut, rear cut, then slow rear replay.
 age=sec-.35 if sec<1.1 else sec-1.35 if sec<2.1 else (sec-2.35)*.25
 side=-1 if sec<1.1 else 1
 o.matrix_world=pose(age,side);o.keyframe_insert(data_path='location',frame=frame);o.rotation_mode='QUATERNION';o.rotation_quaternion=o.matrix_world.to_quaternion();o.keyframe_insert(data_path='rotation_quaternion',frame=frame)
for f,label in [(1,'FRONT - NORMAL SPEED'),(34,'REAR - NORMAL SPEED'),(64,'REAR - 25 percent speed replay')]:scene.timeline_markers.new(label,frame=f)
scene.view_settings.view_transform='AgX'
scene.frame_set(30)
for screen in bpy.data.screens:
 for ar in screen.areas:
  if ar.type=='VIEW_3D':ar.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Katana_Outward_Slash.blend'))
(OUT/'validation.json').write_text(json.dumps({'mesh_vertices':len(o.data.vertices),'measured_mesh_scale':g['meshScale'],'minimum_vertex_radius_near_avatar':minimum,'avatar_footprint_radius':1.8,'windup_seconds':.09,'slash_seconds':.11,'recovery_seconds':.16,'horizontal_arc_degrees':115,'note':'Independent Blender motion concept, not an exported Roblox animation.'},indent=2))
scene.render.image_settings.file_format='PNG'
for f in [1,16,46,50]:
 scene.frame_set(f);scene.render.filepath=str(OUT/f'check_{f:03}.png');bpy.ops.render.render(write_still=True)
scene.render.resolution_percentage=75;scene.cycles.samples=2
scene.render.filepath=str(OUT/'frames/frame_');bpy.ops.render.render(animation=True)
