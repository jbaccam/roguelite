-- Pure motion checks. Run with a freshly loaded WeaponMotion, including in Edit.
return function(M)
 local checks=0
 local function check(ok,message) checks+=1;assert(ok,message) end
 local function render(state,root,dt,slot,aim,attacking)
  M.stepFloat(state,root,Vector3.zero,dt)
  local pose=M.pose(root,2.6,slot,aim,-100,0,'Melee')
  return M.floatPose(pose,root,state,slot,attacking or false,2.6,aim~=nil)
 end
 check(M.radius(Vector3.new(2,2,1))==6.2,'Standard avatar spacing') -- 4.2 before the wider ring (2026-10-03)
 -- Wider ring: slot order kept (angles rise 1 -> 6), 4-5 weapons at least 70 degrees apart, and
 -- with 4 equipped on a standard avatar neighbours sit 8+ studs apart (4.9 before).
 for slot=2,6 do check(M.SlotLayout[slot].angle>M.SlotLayout[slot-1].angle,'slot order '..slot) end
 for slot=2,5 do check(M.SlotLayout[slot].angle-M.SlotLayout[slot-1].angle>=70,'spread '..slot) end
 local r4=M.radius(Vector3.new(2,2,1),4)
 check(math.abs(r4-7.28)<1e-6 and (M.origin(CFrame.identity,r4,2)-M.origin(CFrame.identity,r4,1)).Magnitude>8,'4-weapon spacing')
 local samples={}
 for _,fps in {20,30,60,144} do
  local state=M.newFloat()
  render(state,CFrame.identity,0,1)
  for frame=1,fps do
   render(state,CFrame.new(frame/fps*8,0,0),1/fps,1)
  end
  samples[fps]=state.slots[1].position
 end
 for _,fps in {20,30,60} do
  check((samples[fps]-samples[144]).Magnitude<.002,'Follow changes with FPS '..fps)
 end
 local peak=0
 for _,fps in {20,30,60,144} do
  local state=M.newFloat()
  render(state,CFrame.identity,0,1)
  local below,above=false,false
  for frame=1,fps*3 do
   local t=frame/fps
   local y=t<.6 and math.max(0,35*t-58.333333*t*t) or 0
   local root=CFrame.new(0,y,0)
   local pose=render(state,root,1/fps,1)
   local offset=state.slots[1].position-M.origin(root,2.6,1)
   below=below or (y>0 and offset.Y<-.2)
   above=above or (t>.3 and offset.Y>.2)
   peak=math.max(peak,math.abs(offset.Y))
   check(pose.Position.Magnitude<100 and offset.Magnitude<=3.501,'Unbounded jump spring')
  end
  check(below and above,'Jump must lag and catch up '..fps)
  check((state.slots[1].position-M.origin(CFrame.identity,2.6,1)).Magnitude<.001,'Landing must settle')
 end
 -- Independent followers can move inward during reversals, then settle back
 -- to their individual rest slots. There is no rigid ring constraint.
 local state=M.newFloat()
 render(state,CFrame.identity,0,1)
 local turned=CFrame.Angles(0,math.pi,0)
 local first=render(state,turned,1/60,1)
 check((state.slots[1].position-Vector3.new(2.6,.25,0)).Magnitude<.2,'Turn snapped position')
 check(first.LookVector:Dot(CFrame.identity.LookVector)>.5,'Turn snapped facing')
 local minRadius=100
 for _=1,90 do
  render(state,turned,1/60,1)
  local p=state.slots[1].position
  minRadius=math.min(minRadius,Vector3.new(p.X,0,p.Z).Magnitude)
 end
 check(minRadius<2.5,'Reversal remained locked to the circular frame')
 check(state.slots[1].rotation.LookVector:Dot(turned.LookVector)>.999,'Facing did not settle')
 for slot=1,6 do
  for yaw=-180,180,45 do
   local root=CFrame.Angles(0,math.rad(yaw),0)
   local fresh=M.newFloat()
   local aim=Vector3.new(12,3,-8)
   local pose=render(fresh,root,1/60,slot,aim,true)
   local expected=M.pose(root,2.6,slot,aim,-100,0,'Melee')
   check(pose.LookVector:Dot(expected.LookVector)>.99999,'Explicit attack aim changed')
  end
 end
 render(state,CFrame.new(1000,0,0),1/60,1)
 check((state.slots[1].position-M.origin(CFrame.new(1000,0,0),2.6,1)).Magnitude<.001,'Teleport trails')
 render(state,CFrame.new(1002,0,0),.5,1)
 check((state.slots[1].position-M.origin(CFrame.new(1002,0,0),2.6,1)).Magnitude<.001,'Suspended frame trails')
 return {checks=checks,peakJumpLag=peak,minimumTurnRadius=minRadius,frameRates={20,30,60,144}}
end
