-- Shared deterministic poses: server hit volumes and client visuals use the same path.
local M = {}
M.Damage = 25
M.Cooldown = .58
M.Windup = .10
M.Strike = .10
M.Recovery = .18
M.Range = 10
M.Margin = .30

local function smooth(t)
 t=math.clamp(t,0,1);return t*t*(3-2*t)
end
function M.flatFrame(root)
 local f=Vector3.new(root.LookVector.X,0,root.LookVector.Z)
 if f.Magnitude<.001 then f=Vector3.new(0,0,-1)end
 return CFrame.lookAt(root.Position,root.Position+f.Unit)
end
function M.closestOnSegment(a,b,p)
 local d=b-a;local t=d:Dot(d)>1e-8 and math.clamp((p-a):Dot(d)/d:Dot(d),0,1)or 0
 return a+d*t
end
-- Enclose the full mesh in a capsule, including its curved blade and hilt.
function M.clearance(pose,center,size)
 local a=pose:PointToWorldSpace(center-Vector3.yAxis*size.Y/2)
 local b=pose:PointToWorldSpace(center+Vector3.yAxis*size.Y/2)
 a=Vector3.new(a.X,0,a.Z);b=Vector3.new(b.X,0,b.Z)
 local closest=M.closestOnSegment(a,b,Vector3.zero)
 return closest, math.sqrt(size.X^2+size.Z^2)/2
end
function M.pose(root,radius,center,size,startTime,yaw,now,targetDistance)
 local age=now-startTime
 local active=false
 local tilt,azimuth,extension,roll=0,0,0,0
 local width=math.sqrt(size.X^2+size.Z^2)/2
 local slotRadius=radius+width+M.Margin+.12
 -- Open the blade outward first, then cut horizontally through the target.
 -- Rear targets mirror the front stroke: no inward-facing rear windup.
 local distance=math.max(targetDistance or 4,1)
 local sweepSign=math.sin(yaw)<-.001 and -1 or 1
 local reach=Vector3.new(.55,0,-math.sin(yaw)*1.15)
 local bladeAim=math.atan2(math.sin(yaw)*distance+reach.Z,math.cos(yaw)*distance-slotRadius-reach.X)
 local startAngle=bladeAim-sweepSign*math.rad(75)
 local endAngle=bladeAim+sweepSign*math.rad(75)
 if sweepSign<0 then
  startAngle=math.clamp(startAngle,-math.rad(80),math.rad(80))
  endAngle=math.max(endAngle,-math.rad(178))
 else
  startAngle=math.clamp(startAngle,-math.rad(80),math.rad(80))
  endAngle=math.min(endAngle,math.rad(178))
 end
 local bob=math.sin(now*2.5)*.075
 if age>=0 and age<M.Windup+M.Strike+M.Recovery then
  if age<M.Windup then
   local t=smooth(age/M.Windup);tilt=math.pi/2*t;azimuth=startAngle*t;extension=t;roll=t;bob*=1-t
  elseif age<M.Windup+M.Strike then
   local t=(age-M.Windup)/M.Strike;tilt=math.pi/2;azimuth=startAngle+(endAngle-startAngle)*smooth(t);extension=1;roll=1;active=true;bob=0
  else
   local t=(age-M.Windup-M.Strike)/M.Recovery
   -- Lift clear before retracting the extended grip; never drag the blade inward to recover.
   local lift=smooth(t/.65);local retract=smooth((t-.65)/.35)
   tilt=math.pi/2*(1-lift);azimuth=endAngle;extension=1-retract;roll=1-lift;bob*=retract
  end
 end
 local grip=Vector3.new(slotRadius,.05+bob,0)+reach*extension
 local outward=Vector3.new(math.cos(azimuth),0,-math.sin(azimuth))
 local blade=outward*math.sin(tilt)+Vector3.yAxis*math.cos(tilt)
 local across=Vector3.new(-outward.Z,0,outward.X)
 local pose=CFrame.fromMatrix(grip,across,blade,across:Cross(blade))
 -- Orient the cutting edge into the sweep; mirror the roll for front versus rear cuts.
 if sweepSign>0 then pose*=CFrame.Angles(0,math.pi*roll,0)end
 local closest,capsuleRadius=M.clearance(pose,center,size)
 local required=radius+capsuleRadius+M.Margin
 if closest.Magnitude<required then
  local direction=closest.Magnitude>.001 and closest.Unit or Vector3.xAxis
  if direction.Z*math.sin(yaw)>.001 then
   -- A rear attack may only clear outward/right, never detour in front (and vice versa).
   local a=pose:PointToWorldSpace(center-Vector3.yAxis*size.Y/2)
   local b=pose:PointToWorldSpace(center+Vector3.yAxis*size.Y/2)
   pose=CFrame.new(math.max(0,required-math.min(a.X,b.X)),0,0)*pose
  else
   pose=CFrame.new(direction*(required-closest.Magnitude))*pose
  end
 end
 return M.flatFrame(root)*pose,active
end
function M.bladeBox(pose,center,size)
 -- Exclude the grip/lower 28%; narrow hit thickness stays tied to the visible asset.
 local low=center.Y-size.Y/2+size.Y*.28
 local high=center.Y+size.Y/2
 return pose*CFrame.new(center.X,(low+high)/2,center.Z),Vector3.new(size.X+.18,high-low,size.Z+.18)
end
return M
