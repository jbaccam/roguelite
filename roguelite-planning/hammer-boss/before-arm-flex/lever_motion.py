"""Sliding two-hand sledgehammer poses, in Blender's Z-up authoring space."""
def ease(a,b,f):
 t=max(0,min(1,(f-a)/(b-a)));return t*t*(3-2*t)

def keyed(keys,f):
 for (a,v),(b,w) in zip(keys,keys[1:]):
  if a<=f<=b:
   t=ease(a,b,f);return [x+(y-x)*t for x,y in zip(v,w)]
 return keys[-1][1]

def blend_frame(a,b,t):
 return T(a.translation.lerp(b.translation,t))@a.to_quaternion().slerp(b.to_quaternion(),t).to_matrix().to_4x4()

def attack_pose(clip,f,chest):
 last={'Slam':50,'Swing':54,'Spin':66}[clip]
 weight=ease(0,16,f)*(1-ease(last-18,last,f))
 gripWeight=ease(5,18,f)*(1-ease(last-10,last,f))
 grip={'Right':2.72+(6.55-2.72)*gripWeight,'Left':8.05+(8.05-8.05)*gripWeight}
 center=7.30
 if clip=='Slam':
  # Pitch lifts the head over the shoulder, then drives its lower end into ground.
  pitch,hy,hz=keyed([(0,[35,-2.8,8.4]),(12,[78,-2.2,9.6]),(18,[102,-1.8,9.7]),(20,[64,-2.8,8.8]),(23,[-18,-3.5,4.84]),(29,[-18,-3.5,4.84]),(39,[10,-3.3,6.4]),(50,[35,-2.8,8.4])],f)
  rotation=R(z=90,y=pitch)
  centerWorld=Vector((-.15,hy,hz))
 else:
  if clip=='Swing':
   yaw=keyed([(0,[-65]),(13,[-72]),(18,[-72]),(21,[-28]),(23,[32]),(25,[88]),(31,[108]),(43,[45]),(54,[0])],f)[0]
  else:
   # A continuous revolution, without stopping at every quarter turn.
   yaw=(-60+(f-21)*22.5) if 21<=f<=37 else keyed([(0,[-50]),(14,[-60]),(21,[-60]),(37,[300]),(43,[334]),(55,[360]),(66,[360])],f)[0]
  # Roll a quarter turn around the shaft: the long head's striking end leads
  # tangential travel, rather than sweeping with the broad side of the block.
  rotation=R(z=90+yaw,x=90)
  centerWorld=R(z=yaw)@Vector((0,-3.45,6.75))
 target=T(centerWorld)@rotation@T((-center,0,0))
 H=blend_frame(HT,target,weight)
 # Interpolate authored angles, not the shortest quaternion arc. Crossing
 # 180 degrees during a partial windup otherwise changes arcs in one frame.
 if clip=='Slam':orientation=R(z=90*weight,y=-13+(pitch+13)*weight)
 else:
  unwind=yaw-360 if clip=='Spin' and f>=43 else yaw
  orientation=R(z=(90+unwind)*weight,x=90*weight,y=-13*(1-weight))
 # Rotate about the held end, rather than interpolating the distant head
 # position and sweeping the wrists through a large unintended arc.
 H=T((HT@Vector((center,0,0))).lerp(centerWorld,weight))@orientation@T((-center,0,0))
 weapon=H@HT.inverted()
 handOffsets={side:HT@T((g-({'Right':2.72,'Left':8.05}[side]),0,0))@HT.inverted() for side,g in grip.items()}
 # The two wrist targets lie on the intersection of the arms' reach spheres.
 # This extends BOTH elbows while preserving the paired grip and bone lengths.
 extension=ease(15,19,f)*(1-ease(last-16,last-7,f))
 spheres=[]
 for side in ('Right','Left'):
  a=joints[side+'UpperArm']['head'];b=joints[side+'LowerArm']['head'];w=joints[side+'Hand']['head']
  offset=weapon.to_3x3()@(handOffsets[side]@w)
  spheres.append((chest@a-offset,(b-a).length+(w-b).length-.025))
 c1,r1=spheres[0];c2,r2=spheres[1];axis=c2-c1;dist=axis.length;axis.normalize()
 along=(r1*r1-r2*r2+dist*dist)/(2*dist);centerReach=c1+axis*along
 radius=math.sqrt(max(0,r1*r1-along*along))
 direction=weapon.translation-centerReach;direction-=axis*direction.dot(axis)
 full=centerReach+direction.normalized()*radius
 if clip=='Slam' and 23<=f<=29:
  # Select the point on that reach circle that also puts the striking face
  # on the ground; choose the forward of the two possible solutions.
  bottom=min((weapon.to_3x3()@(HT@Vector((x,y,z)))).z for x in [-1.55,1.55] for y in [-1.155,1.155] for z in [-2.21,2.21])
  up=Vector((0,0,1));u=up-axis*axis.z;ul=u.length;u.normalize();v=axis.cross(u)
  height=(.005-bottom-centerReach.z)/max(ul,.0001)
  if abs(height)<=radius:
   spread=math.sqrt(radius*radius-height*height)
   full=min([centerReach+u*height+v*spread,centerReach+u*height-v*spread],key=lambda p:p.y)
 weapon.translation=weapon.translation.lerp(full,extension)
 # Move the paired grip as a unit to the arms' feasible reach, preserving all
 # finger/shaft contact while each hand independently slides along the wood.
 for iteration in range(60):
  for side in ('Right','Left'):
   a=joints[side+'UpperArm']['head'];b=joints[side+'LowerArm']['head'];w=joints[side+'Hand']['head']
   delta=weapon@handOffsets[side]@w-chest@a;limit=(b-a).length+(w-b).length-.035
   if delta.length>limit:weapon.translation-=delta.normalized()*(delta.length-limit)
 if not (clip=='Slam' and 23<=f<=29):
  # Project the paired grip out of the belly during windup/recovery. Moving
  # the weapon and both hands together retains real contact with the shaft.
  inv=chest.inverted();forward=chest.to_3x3()@Vector((0,-1,0))
  for iteration in range(80):
   push=0
   for side,s in [('Right',-1),('Left',1)]:
    a=joints[side+'UpperArm']['head'];b=joints[side+'LowerArm']['head'];w=joints[side+'Hand']['head']
    shoulder=chest@a;wrist=weapon@handOffsets[side]@w
    elbow,_=ik(shoulder,wrist,(b-a).length,(w-b).length,chest@(a+Vector((s*3.5,-2.5,-.7))))
    for k in range(9):
     p=inv@elbow.lerp(wrist,k/8)
     section=1.3-(p.x/2.25)**2-((p.z-6.5)/2.15)**2
     if section>0:
      front=-.15-1.7*math.sqrt(section)
      if p.y>front:push=max(push,p.y-front)
   if push<.0001:break
   weapon.translation+=forward*min(push,.15)
   for side in ('Right','Left'):
    a=joints[side+'UpperArm']['head'];b=joints[side+'LowerArm']['head'];w=joints[side+'Hand']['head']
    delta=weapon@handOffsets[side]@w-chest@a;limit=(b-a).length+(w-b).length-.035
    if delta.length>limit:weapon.translation-=delta.normalized()*(delta.length-limit)
 if clip=='Slam' and 23<=f<=29:
  bottom=min((weapon@HT@Vector((x,y,z))).z for x in [-1.55,1.55] for y in [-1.155,1.155] for z in [-2.21,2.21])
  weapon.translation.z+=.005-bottom
 # A little elbow flexion is required to stack the wrist behind a real
 # two-handed grip. Near-locked elbows forced the former 90-degree fold.
 wrists=sum((weapon@handOffsets[side]@joints[side+'Hand']['head'] for side in ('Right','Left')),Vector())/2
 inward=chest@Vector((0,0,7))-wrists;inward.z=0
 if inward.length>.001:weapon.translation+=inward.normalized()*1.6*ease(12,19,f)*(1-ease(last-18,last,f))
 return weapon,handOffsets
