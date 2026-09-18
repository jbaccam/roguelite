local package=game.ReplicatedStorage.RogueliteCombat
local M=require(package.KatanaMotion)
local t=package.KatanaTemplate
local center,size=t:GetAttribute('BoundsCenter'),t:GetAttribute('BoundsSize')
local checked,minClearance=0,math.huge
for _,radius in {1.6,2.5,3.8}do
 for degrees=-180,180,10 do
  for step=0,84 do
   local cf=M.pose(CFrame.identity,radius,center,size,0,math.rad(degrees),step/120)
   local closest,width=M.clearance(cf,center,size)
   local clearance=closest.Magnitude-width-radius
   minClearance=math.min(minClearance,clearance)
   assert(clearance>=M.Margin-.001,'Avatar intersection at '..degrees..' / '..step)
   checked+=1
  end
 end
end
local a=M.pose(CFrame.identity,2.5,center,size,-100,0,1)
local b=M.pose(CFrame.identity,2.5,center,size,-100,0,50)
assert(math.abs(a.X-b.X)<.001 and math.abs(a.Z-b.Z)<.001,'Idle slot orbits')
for step=0,84 do
 local cf=M.pose(CFrame.identity,2.5,center,size,0,-math.pi/2,step/120,4.5)
 assert(cf.X>0,'Rear attack moved to the left side')
 assert(cf.Z>=-.001,'Rear attack routed in front of the avatar')
end
for _,yaw in {math.pi/2,-math.pi/2,math.pi}do
 for step=1,19 do
  local cf=M.pose(CFrame.identity,2.5,center,size,0,yaw,M.Windup*step/20,4.5)
  assert(cf.UpVector.X>=-.001,'Windup tips blade inward')
 end
 for step=1,19 do
  local cf,active=M.pose(CFrame.identity,2.5,center,size,0,yaw,M.Windup+M.Strike*step/20,4.5)
  assert(active and math.abs(cf.UpVector.Y)<.001,'Strike is not horizontal')
 end
end
return {poses=checked,minimumClearance=minClearance,idleSlotFixed=true,rearAttackStaysOnRight=true,rearAttackNeverRoutesInFront=true,outwardWindup=true,horizontalStrike=true}
