import bpy, math, json, sys
from pathlib import Path
from mathutils import Vector, Quaternion

OUT = Path(__file__).parent
bpy.ops.wm.open_mainfile(filepath=str(OUT.parent / 'blender-slash-preview/Katana_Outward_Slash.blend'))
scene=bpy.context.scene
sword=bpy.data.objects['Katana_User_Scale']
sword.animation_data_clear()
sword.rotation_mode='QUATERNION'
for ob in list(bpy.data.objects):
    if ob.name.startswith(('Front target','Rear target')) or ob.type=='FONT':
        bpy.data.objects.remove(ob,do_unlink=True)

# All rotations use ONE fixed axis. No changing basis, local blade roll, or
# Euler wrap. The cutting edge and curvature return to their original facing.
# time, grip x, grip y (negative is forward), grip z, rotation around Y
KEYS=[
    (0.00, 3.25, 0.00, 3.15,   0),
    (0.16, 3.25, 0.00, 3.15,   0),
    (0.27, 3.48,-0.85, 3.82,  10),
    (0.32, 3.22,-1.82, 4.12, -30),
    (0.38, 2.39,-3.15, 4.45, -91),
    (0.44, 1.62,-3.70, 4.48,-130),
    (0.53, 0.92,-3.75, 4.30,-137),
    (0.66,-0.55,-3.25, 4.72,-115),
    (0.84, 0.55,-2.75, 5.15, -58),
    (1.00, 3.10,-1.40, 3.50,  -8),
    (1.08, 3.25, 0.00, 3.15,   0),
    (1.35, 3.25, 0.00, 3.15,   0),
]

def slopes(vals):
    d=[(vals[i+1]-vals[i])/(KEYS[i+1][0]-KEYS[i][0]) for i in range(len(KEYS)-1)]
    m=[0.0]*len(KEYS)
    for i in range(1,len(KEYS)-1):
        if d[i-1]*d[i]>0:
            a=KEYS[i][0]-KEYS[i-1][0]; b=KEYS[i+1][0]-KEYS[i][0]
            w1=2*b+a; w2=b+2*a
            m[i]=(w1+w2)/(w1/d[i-1]+w2/d[i])
    return m

TANGENTS=[slopes([k[j] for k in KEYS]) for j in range(1,5)]
def pose(t):
    t=max(KEYS[0][0],min(KEYS[-1][0],t))
    i=next((i for i in range(len(KEYS)-1) if t<=KEYS[i+1][0]),len(KEYS)-2)
    a,b=KEYS[i],KEYS[i+1]; dt=b[0]-a[0]; u=(t-a[0])/dt
    vals=[]
    for j in range(1,5):
        ma=TANGENTS[j-1][i]; mb=TANGENTS[j-1][i+1]
        vals.append((2*u**3-3*u*u+1)*a[j]+(u**3-2*u*u+u)*dt*ma+(-2*u**3+3*u*u)*b[j]+(u**3-u*u)*dt*mb)
    return Vector(vals[:3]),Quaternion((0,1,0),math.radians(vals[3]))

scene.frame_start=1; scene.frame_end=82; scene.render.fps=60
for f in range(1,83):
    sword.location,sword.rotation_quaternion=pose((f-1)/60)
    sword.keyframe_insert(data_path='location',frame=f)
    sword.keyframe_insert(data_path='rotation_quaternion',frame=f)
if sword.animation_data:
    sword.animation_data.action.name='Katana | diagonal descending cut and outside recovery'
    # Dense samples with linear interpolation retain the continuous quaternion
    # hemisphere; no automatic Bezier overshoot between samples.
    for layer in sword.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for k in fc.keyframe_points:k.interpolation='LINEAR'

scene.timeline_markers.clear()
for sec,name in [(0,'READY'),(.16,'OUTWARD ANTICIPATION'),(.27,'DIAGONAL CUT'),(.44,'FOLLOW THROUGH'),(.53,'OUTSIDE RECOVERY'),(1.08,'SAME READY POSE')]:
    scene.timeline_markers.new(name,frame=round(sec*60)+1)

cam=scene.camera
cam.location=(0,-26,9)
cam.rotation_euler=(Vector((-.2,-1.4,4.7))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.type='ORTHO';cam.data.ortho_scale=13.0;cam.name='Camera | front diagonal review'
side=cam.copy();side.data=cam.data.copy();scene.collection.objects.link(side)
side.name='Camera | three quarter depth review';side.location=(14,-23,15)
side.rotation_euler=(Vector((0,-1.3,4.5))-side.location).to_track_quat('-Z','Y').to_euler()
side.data.ortho_scale=14.5

scene.render.engine='CYCLES';scene.cycles.samples=4;scene.cycles.use_denoising=True
scene.render.resolution_x=960;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'

# Conservative all-geometry clearance: avatar AABB expanded beyond body, arms,
# head, and feet. Every sword vertex has clearance from this enclosure at
# every sampled pose, and mesh extrema provide a separating axis throughout.
boxlo=Vector((-1.73,-.57,0));boxhi=Vector((1.73,.57,5.15))
min_gap=1e9;floor_gap=1e9;fail=[]
for n in range(1351):
    t=n/1000; p,q=pose(t)
    verts=[p+q@v.co for v in sword.data.vertices]
    low=Vector([min(v[j] for v in verts) for j in range(3)])
    high=Vector([max(v[j] for v in verts) for j in range(3)])
    gaps=[max(boxlo[j]-high[j],low[j]-boxhi[j]) for j in range(3)]
    gap=max(gaps); min_gap=min(min_gap,gap);floor_gap=min(floor_gap,low.z)
    if gap<=0:fail.append(round(t,3))
p0,q0=pose(0);p1,q1=pose(1.35)
validation={'sampled_poses':1351,'mesh_vertices':len(sword.data.vertices),'avatar_conservative_aabb':[list(boxlo),list(boxhi)],'minimum_separating_axis_clearance_studs':min_gap,'minimum_floor_clearance_studs':floor_gap,'possible_avatar_intersection_times':fail,'start_end_position_error':(p1-p0).length,'start_end_quaternion_angle_error_degrees':math.degrees(q0.rotation_difference(q1).angle),'cut_seconds':.17,'cycle_seconds':1.35,'rotation_axis':'world Y only; no axial roll','forward_grip_reach_studs':3.75,'preview_only':'Blender animation; no Studio or gameplay changes.'}
(OUT/'validation.json').write_text(json.dumps(validation,indent=2))
assert not fail, validation
assert floor_gap>0,validation
scene.frame_set(1)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Katana_Diagonal_Slash.blend'))
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
if 'checks' in args:
    for f in [1,17,20,23,27,33,42,54,66]:
        scene.frame_set(f);scene.render.filepath=str(OUT/f'check_{f:03}.png');bpy.ops.render.render(write_still=True)
elif 'render' in args:
    scene.frame_start=11;scene.frame_end=65
    scene.render.filepath=str(OUT/'frames/frame_');bpy.ops.render.render(animation=True)
elif 'side' in args:
    scene.camera=side
    for f in [1,17,23,27,42,66]:
        scene.frame_set(f);scene.render.filepath=str(OUT/f'side_{f:03}.png');bpy.ops.render.render(write_still=True)
print('VALIDATION',json.dumps(validation))
