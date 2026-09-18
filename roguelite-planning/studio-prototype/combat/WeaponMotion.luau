local M={}
-- Draco barrel mouth in the normalized play-size model, above its magazine-centered pivot.
M.DracoMuzzle=Vector3.new(0,.585,-1.385)
M.MuzzleOffsets={
 ['00']=Vector3.new(0,.56,-1.195),
 ['07']=M.DracoMuzzle,
 ['09']=Vector3.new(0,.315,-1.67),
}
function M.frame(cf)
 local forward=Vector3.new(cf.LookVector.X,0,cf.LookVector.Z)
 return CFrame.lookAt(cf.Position,cf.Position+(forward.Magnitude>.001 and forward.Unit or -Vector3.zAxis))
end
function M.origin(root,radius,slot)
 local angle=(slot-1)*math.pi/3
 return M.frame(root):PointToWorldSpace(Vector3.new(math.cos(angle)*radius,.25,-math.sin(angle)*radius))
end
function M.pose(root,radius,slot,aim,start,now,kind)
 local origin=M.origin(root,radius,slot)
 -- Every idle weapon faces the character's twelve o'clock, regardless of slot.
 local forward=M.frame(root).LookVector
 local delta=aim and aim-origin or forward
 delta=Vector3.new(delta.X,0,delta.Z)
 if delta.Magnitude<.01 then delta=forward end
 local direction=delta.Unit
 local age=now-start
 local cf=CFrame.lookAt(origin,origin+direction)
 local active=false
 if kind=='Melee' then
  if age>=0 and age<.34 then
   local t=math.clamp((age-.08)/.14,0,1)
   active=age>=.08 and age<=.22
   local recovery=age>.22 and 1-(age-.22)/.12 or 1
   cf*=CFrame.new(0,0,-math.sin(t*math.pi)*.65)*CFrame.Angles(0,math.rad(65-130*t)*recovery,math.rad(-65)*math.sin(t*math.pi)*recovery)
  end
 elseif age>=0 and age<.16 then
  cf*=CFrame.new(0,0,.23*(1-age/.16))
 end
 return cf,active
end
-- Cosmetic spring state belongs to a rendered character, never the server hit pose.
function M.newFloat()
 return {offset=Vector3.zero,velocity=Vector3.zero,moving=0,phase=0}
end
function M.stepFloat(state,velocity,dt)
 dt=math.clamp(dt,0,.1)
 local speed=Vector3.new(velocity.X,0,velocity.Z).Magnitude
 state.moving+=(math.clamp(speed/16,0,1)-state.moving)*(1-math.exp(-8*dt))
 state.phase+=dt*(2.1+state.moving*6)
 local horizontal=Vector3.new(velocity.X,0,velocity.Z)*-.026
 if horizontal.Magnitude>.44 then horizontal=horizontal.Unit*.44 end
 local target=horizontal+Vector3.yAxis*math.clamp(-velocity.Y*.024,-.72,.72)
 -- Substeps keep the lightly damped landing rebound stable at low frame rates.
 local count=math.max(1,math.ceil(dt*120));local h=dt/count
 for _=1,count do
  state.velocity+=((target-state.offset)*110-state.velocity*8)*h
  state.offset+=state.velocity*h
 end
end
function M.floatPose(pose,root,state,slot,attacking)
 local phase=state.phase+(slot-1)*.55
 local bob=math.sin(phase)*(.12+.22*state.moving)
 local sway=math.sin(phase*.5)*.16*state.moving
 local offset=state.offset+Vector3.yAxis*bob+M.frame(root).RightVector*sway
 if offset.Magnitude>1.2 then offset=offset.Unit*1.2 end
 local strength=attacking and .45 or 1
 -- Roll around the aim axis; never yaw the muzzle away from its target.
 local roll=math.sin(phase+.4)*math.rad(1.5+3.5*state.moving)*strength
 return CFrame.new(pose.Position+offset*strength)*pose.Rotation*CFrame.Angles(0,0,roll)
end
return M
