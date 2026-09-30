"""Charge review: ChargeStart -> 3 ChargeRun loops -> runtime 0.12 s blend into
Slam, sampled at 60 Hz with the same runtime code the validator checks
(charge_runtime.py). Side view (from the hammer side) and 3/4 front view.
Ground stripes scroll back at chargeSpeed while the root would be moving, so a
planted foot should stay locked to a stripe. Writes
finished/attack-videos/Charge_Review.mp4 (normal speed, then half speed) and
finished/attack-videos/Charge_Strip.png. Nothing is saved to the .blend."""
import bpy,math,json,os,subprocess,shutil
from pathlib import Path
from mathutils import Matrix,Vector
HERE=Path(__file__).resolve().parent;OUT=HERE/'finished';VID=OUT/'attack-videos'
FRAMES=Path(os.environ.get('CHARGE_FRAMES',str(HERE/'charge-review-frames')))
bpy.ops.wm.open_mainfile(filepath=str(OUT/'HammerBoss.blend'))
d=json.loads((OUT/'BossData.json').read_text())
exec(compile((HERE/'charge_runtime.py').read_text(),str(HERE/'charge_runtime.py'),'exec'))
scene=bpy.context.scene;rig=bpy.data.objects['HammerBoss_Rig'];SPEED=d['chargeSpeed']
rig.animation_data_clear()
joints=[b.name for b in rig.data.bones if b.name!='HumanoidRootPart']
def apply(P):
 D={n:delta(m) for n,m in P.items()}
 for name in joints:
  pb=rig.pose.bones[name];pb.rotation_mode='QUATERNION';pb.matrix=D[name]@rig.data.bones[name].matrix_local;bpy.context.view_layer.update()

# ---- sequence (60 Hz)
seq=[]
for k in range(0,36):seq.append(('ChargeStart  frame %.1f'%(k/2),rsample('ChargeStart',k/60),0.0))
for k in range(0,96):
 t=k/60;seq.append(('ChargeRun  loop %d  frame %.1f'%(k//32+1,(k%32)/2),rsample('ChargeRun',t,True),SPEED*t))
A=rsample('ChargeRun',1.6,True);travel=SPEED*1.6
for k in range(0,101):
 t=k/60;w=min(1,t/.12);P=constrain(rblend(A,rsample('Slam',t),w))
 seq.append(('Slam  frame %.1f%s'%(t*30,'  (runtime blend %.0f%%)'%(w*100) if w<1 else ''),P,travel))

# ---- stage: ground stripes that scroll with root travel
mat_dark=bpy.data.materials.new('ReviewStripe');mat_dark.diffuse_color=(.12,.13,.16,1)
holder=bpy.data.objects.new('ReviewStripes',None);scene.collection.objects.link(holder)
bpy.ops.mesh.primitive_cube_add(size=1)
proto=bpy.context.object;proto.scale=(16,.12,.01);proto.data.materials.append(mat_dark)
stripes=[proto]
for i in range(1,26):
 c=proto.copy();scene.collection.objects.link(c);stripes.append(c)
for i,o in enumerate(stripes):o.parent=holder;o.location=(0,-26+i*2,.006)
SP=2.0
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.color_type='TEXTURE'
scene.display.shading.light='STUDIO';scene.display.shading.show_shadows=True
scene.render.resolution_x=720;scene.render.resolution_y=600;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.use_stamp=True
for attr in dir(scene.render):
 if attr.startswith('use_stamp_') and attr not in ('use_stamp_note',) and isinstance(getattr(scene.render,attr),bool):
  try:setattr(scene.render,attr,False)
  except Exception:pass
scene.render.use_stamp_note=True;scene.render.stamp_font_size=18
cams={}
for name,loc,target,scale in (('side',(-30,-1.0,5.2),(0,-1.0,5.2),17.0),('front34',(-19,-24,11),(-.8,-1.2,4.8),17.5)):
 cd=bpy.data.cameras.new('Review_'+name);cd.type='ORTHO';cd.ortho_scale=scale
 co=bpy.data.objects.new('Review_'+name,cd);scene.collection.objects.link(co)
 co.location=loc;co.rotation_euler=(Vector(target)-co.location).to_track_quat('-Z','Y').to_euler();cams[name]=co
if FRAMES.exists():shutil.rmtree(FRAMES)
FRAMES.mkdir(parents=True)
for i,(label,P,travel) in enumerate(seq):
 apply(P);holder.location.y=travel%SP
 for view,co in cams.items():
  scene.camera=co;scene.render.stamp_note_text=label+('   | side' if view=='side' else '   | 3/4 front')
  scene.render.filepath=str(FRAMES/('%s_%04d.png'%(view,i)));bpy.ops.render.render(write_still=True)
# ---- frame strip: 8 side-view poses at authored frames
strip=[('ChargeStart',0),('ChargeStart',4),('ChargeStart',9),('ChargeStart',13),('ChargeRun',0),('ChargeRun',4),('ChargeRun',8),('ChargeRun',12)]
scene.render.resolution_x=330;scene.render.resolution_y=380;scene.render.stamp_font_size=12;scene.camera=cams['side']
for j,(clip,f) in enumerate(strip):
 apply(FR[clip][f]);holder.location.y=0
 scene.render.stamp_note_text='%s f%d'%(clip,f);scene.render.filepath=str(FRAMES/('strip_%d.png'%j));bpy.ops.render.render(write_still=True)
ff=shutil.which('ffmpeg') or 'ffmpeg'
VID.mkdir(exist_ok=True)
cmd=[ff,'-y','-framerate','60','-i',str(FRAMES/'side_%04d.png'),'-framerate','60','-i',str(FRAMES/'front34_%04d.png'),
 '-filter_complex','[0:v][1:v]hstack=inputs=2,split=2[a][b];[b]setpts=2*PTS[bs];[a][bs]concat=n=2:v=1:a=0,format=yuv420p[v]',
 '-map','[v]','-r','60','-c:v','libx264','-crf','20','-preset','medium',str(VID/'Charge_Review.mp4')]
print('FFMPEG',subprocess.run(cmd,capture_output=True,text=True).returncode)
cmd=[ff,'-y','-i',str(FRAMES/'strip_%d.png'),'-vf','tile=8x1',str(VID/'Charge_Strip.png')]
print('FFMPEG_STRIP',subprocess.run(cmd,capture_output=True,text=True).returncode)
print('REVIEW_SAMPLES',len(seq))
