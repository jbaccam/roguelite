-- The exported poses drive rendering AND authoritative weapon collision.
local SCALE=1.15
local function copy(value)
 if type(value)~='table' then return value end
 local result={};for k,v in value do result[k]=copy(v) end;return result
end
-- Scale a private copy so geometry, joint pivots, poses and collision agree.
local D=copy(require(script.Parent.BossData))
local function scale3(values) for i=1,3 do values[i]*=SCALE end end
D.rootHeight*=SCALE;D.walkSpeed*=SCALE;if D.chargeSpeed then D.chargeSpeed*=SCALE end
scale3(D.hammerHeadRest);scale3(D.hammerHeadSize)
for _,joint in D.joints do scale3(joint.head) end
for _,part in D.parts do scale3(part.center);scale3(part.size) end
for _,clip in D.clips do for _,frame in clip.frames do for _,pose in frame do scale3(pose) end end end
local M={Scale=SCALE,Data=D,RootHeight=D.rootHeight,HeadSize=Vector3.new(table.unpack(D.hammerHeadSize))}
local headRest=CFrame.new(table.unpack(D.hammerHeadRest))
local arms={}
-- Must match ELBOW_MIN/ELBOW_MAX in wrist_motion.py, which authored the clips.
-- If they disagree the runtime re-solves each arm into a pose the animation
-- never contained.
local minFlex,maxFlex=math.rad(12),math.rad(130)
local function hingeFrame(direction,normal)
 local y=direction.Unit;local z=normal.Unit
 return CFrame.fromMatrix(Vector3.zero,y:Cross(z).Unit,y,z)
end
for _,side in {'Right','Left'} do
 local function joint(name) return Vector3.new(table.unpack(D.joints[side..name].head))-Vector3.yAxis*D.rootHeight end
 local a,b,w=joint('UpperArm'),joint('LowerArm'),joint('Hand')
 local u,v=b-a,w-b;local axis=u:Cross(v).Unit
 arms[side]={a=a,b=b,w=w,l1=u.Magnitude,l2=v.Magnitude,axis=axis,restFlex=math.acos(math.clamp(u.Unit:Dot(v.Unit),-1,1)),frame=hingeFrame(u,axis),pole=Vector3.new(side=='Right' and 2.2 or -2.2,-3.5,.35)}
end
-- Enforce the same one-way hinge after interpolation and transition blending.
-- Keeping endpoints near each other alone does not prevent a backwards elbow.
function M.constrainArms(poses)
 local chest=poses.UpperTorso
 for side,a in arms do
  local hand=poses[side..'Hand'];local shoulder=chest*a.a;local wrist=hand*a.w
  local v=wrist-shoulder;local u=v.Magnitude>1e-6 and v.Unit or chest:VectorToWorldSpace(-Vector3.yAxis)
  local low=math.sqrt(a.l1*a.l1+a.l2*a.l2+2*a.l1*a.l2*math.cos(maxFlex))
  local high=math.sqrt(a.l1*a.l1+a.l2*a.l2+2*a.l1*a.l2*math.cos(minFlex))
  local distance=math.clamp(v.Magnitude,low,high)
  local corrected=shoulder+u*distance
  poses[side..'Hand']=hand+(corrected-wrist);wrist=corrected
  local along=(a.l1*a.l1-a.l2*a.l2+distance*distance)/(2*distance)
  local pole=chest:VectorToWorldSpace(a.pole);pole-=u*pole:Dot(u)
  if pole.Magnitude<1e-5 then pole=chest:VectorToWorldSpace(Vector3.xAxis);pole-=u*pole:Dot(u) end
  local requested=poses[side..'LowerArm']*a.b-shoulder;requested-=u*requested:Dot(u)
  local swivel=math.atan2(u:Dot(pole:Cross(requested)),pole:Dot(requested))
  swivel=math.clamp(swivel,-math.rad(75),math.rad(75))
  local bend=CFrame.fromAxisAngle(u,swivel):VectorToWorldSpace(pole.Unit)
  local elbow=shoulder+u*along+bend*math.sqrt(math.max(0,a.l1*a.l1-along*along))
  local upper,lower=elbow-shoulder,wrist-elbow
  local axis=upper:Cross(lower).Unit
  local rotation=hingeFrame(upper,axis)*a.frame:Inverse()
  local flex=math.acos(math.clamp(upper.Unit:Dot(lower.Unit),-1,1))
  poses[side..'UpperArm']=CFrame.new(shoulder)*rotation*CFrame.new(-a.a)
  poses[side..'LowerArm']=CFrame.new(elbow)*rotation*CFrame.fromAxisAngle(a.axis,flex-a.restFlex)*CFrame.new(-a.b)
 end
 return poses
end
M.Attacks={
 Slam={anticipation=5/30,active=23/30,finish=24/30,duration=50/30,cooldown=2.65,damage=24,radius=9.5},
 Swing={anticipation=6/30,active=19/30,finish=25/30,duration=54/30,cooldown=2.95,damage=18},
 Spin={anticipation=6/36,active=21/36,finish=37/36,duration=66/36,cooldown=4.15,damage=22},
}
local clips={}
for name,clip in D.clips do
 local frames={}
 for i,frame in clip.frames do local poses={};for part,values in frame do poses[part]=CFrame.new(table.unpack(values)) end;frames[i]=poses end
 clips[name]={frames=frames,duration=clip.lastFrame/clip.fps,last=clip.lastFrame,fps=clip.fps}
end
function M.duration(name) return clips[name].duration end
-- Charge (2026-09-30): runs down a player who kites from range. ChargeStart plays in place, then
-- the server drives the body in a straight line at `speed` while ChargeRun loops (its cadence from
-- ground covered: D.chargeSpeed studs per clip second). He then brakes for `brake` seconds by
-- playing ChargeStart backwards (run pose -> carry pose, every frame validated) and slams. A direct
-- ChargeRun->Slam blend flips the elbows (forward in the carry, back in the run) and snaps.
-- Anyone the body passes within `halfWidth` takes `damage` and is knocked down.
M.Charge={minRange=24,maxRange=70,speed=30,maxLength=55,stopShort=6,halfWidth=4.5,damage=24,knockdown=.6,cooldown=6,brake=.3}
M.hasCharge=clips.ChargeStart~=nil and clips.ChargeRun~=nil
function M.chargeRunTime(travelled) return travelled/(D.chargeSpeed or M.Charge.speed) end
-- Interpolate the held end of the tool, then the hands in tool space.
-- Independently interpolating world-space hand matrices cuts across the
-- swing arc and pulls the cuffs inward between otherwise extended frames.
local gripPivot=headRest*CFrame.new(-7.3*SCALE,0,0)
function M.blend(a,b,alpha)
 local result={}
 for name,cf in a do result[name]=cf:Lerp(b[name],alpha) end
 local heldA=a.UpperTorso:ToObjectSpace(a.Hammer*gripPivot)
 local heldB=b.UpperTorso:ToObjectSpace(b.Hammer*gripPivot)
 result.Hammer=result.UpperTorso*heldA:Lerp(heldB,alpha)*gripPivot:Inverse()
 for _,name in {'RightHand','LeftHand'} do
  result[name]=result.Hammer*a.Hammer:ToObjectSpace(a[name]):Lerp(b.Hammer:ToObjectSpace(b[name]),alpha)
 end
 return result
end
function M.sample(name,time,looped)
 local clip=assert(clips[name],'Unknown boss clip')
 if looped then time=time%clip.duration end
 local f=math.clamp(time*clip.fps,0,clip.last);local i=math.floor(f)+1;local j=math.min(i+1,#clip.frames);local alpha=f%1
 local result=M.blend(clip.frames[i],clip.frames[j],alpha)
 if name=='Death' then
  for part,cf in clip.frames[i] do result[part]=cf:Lerp(clip.frames[j][part],alpha) end
 end
 local attack=M.Attacks[name]
 if (name=='Swing' or name=='Spin') and time>=attack.active and time<=attack.finish then
  local shift=Vector3.yAxis*(4.6*SCALE-D.rootHeight-(result.Hammer*headRest).Y)
  for _,part in {'Hammer','RightHand','LeftHand'} do result[part]+=shift end
 end
 return M.constrainArms(result)
end
function M.head(root,clip,time)
 return root*M.sample(clip,time).Hammer*headRest
end
function M.reach(clip)
 local a=M.Attacks[clip];local p=M.head(CFrame.identity,clip,a.active).Position
 return Vector2.new(p.X,p.Z).Magnitude
end
function M.active(clip,time)
 local a=M.Attacks[clip];return a~=nil and time>=a.active and time<=a.finish
end
function M.prepare(npc)
 if npc:GetAttribute('BossVisualScale')==SCALE then return end
 local previous=npc:GetScale();local ratio=SCALE/previous
 npc:ScaleTo(SCALE)
 for name in D.parts do
  local part=npc:FindFirstChild(name);local rest=part and part:GetAttribute('BossRest')
  if rest then part:SetAttribute('BossRest',CFrame.new(rest.Position*ratio)*rest.Rotation) end
 end
 npc:SetAttribute('BossVisualScale',SCALE)
end
function M.apply(npc,poses)
 M.prepare(npc)
 M.constrainArms(poses)
 local rest={HumanoidRootPart=CFrame.identity}
 for name in D.parts do
  local part=npc:FindFirstChild(name)
  if part then rest[name]=part:GetAttribute('BossRest') end
 end
 for name,joint in D.joints do
  local m=npc:FindFirstChild('Boss_'..name,true)
  if m and rest[name] then
   local parentPose=joint.parent=='HumanoidRootPart' and CFrame.identity or poses[joint.parent]
   local parentRest=rest[joint.parent]
   if parentPose and parentRest then
    m.Transform=m.C0:Inverse()*(parentPose*parentRest):Inverse()*(poses[name]*rest[name])*m.C1
   end
  end
 end
end
-- Capsule sample points around a normal avatar's root, tested against the actual
-- oriented head. The small radius is player body width, not bonus weapon reach.
function M.touches(head,playerRoot)
 local half=M.HeadSize*.5
 for _,height in {-1.5,-.5,.5,1.5} do
  local p=head:PointToObjectSpace(playerRoot+Vector3.yAxis*height)
  local closest=Vector3.new(math.clamp(p.X,-half.X,half.X),math.clamp(p.Y,-half.Y,half.Y),math.clamp(p.Z,-half.Z,half.Z))
  if (p-closest).Magnitude<=.85 then return true end
 end
 return false
end
-- Swing/Spin hit band (user, 2026-09-30: sweeps felt like they missed). A player is hit when
-- within SweepRadius of the line from the boss to the hammer head as it sweeps, so standing
-- inside the swing (between boss and hammer) counts too. The warning draws this same area.
M.SweepRadius=2.8*SCALE
function M.sweeps(root,head,playerRoot)
 if math.abs(playerRoot.Y-root.Y)>6 then return false end
 local a=Vector2.new(root.X,root.Z);local b=Vector2.new(head.X,head.Z);local p=Vector2.new(playerRoot.X,playerRoot.Z)
 local ab=b-a;local t=ab:Dot(ab)>1e-6 and math.clamp((p-a):Dot(ab)/ab:Dot(ab),0,1) or 0
 return (p-(a+ab*t)).Magnitude<=M.SweepRadius
end
-- The warning follows the actual projected sweep.
function M.warning(root,clip)
 local a=M.Attacks[clip];local points={}
 if clip=='Slam' then return {M.head(root,clip,a.active).Position},a.radius end
 for i=0,math.ceil((a.finish-a.active)*120) do
  local head=M.head(root,clip,math.min(a.finish,a.active+i/120))
  table.insert(points,head.Position)
 end
 return points,M.SweepRadius
end
return M
