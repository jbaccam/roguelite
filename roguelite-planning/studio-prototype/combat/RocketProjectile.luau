-- Server-owned travel, swept collision, and one bounded blast per rocket.
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local Motion=require(script.Parent.RocketMotion)
local Targets=require(script.Parent.ProjectileTarget)
local Rocket={}
function Rocket.new(combat,damage,rayParams)
 local active={};local nextId=0
 local event=combat:WaitForChild('RocketFX')
 local function finish(id,r,result)
  active[id]=nil
  if not result then event:FireAllClients('Remove',id);return end
  local position=result.Position
  event:FireAllClients('Impact',id,position,r.definition.blastRadius)
  local wallParams=rayParams(r.character,true)
  local origin=position+result.Normal*.12
  for _,npc in Tags:GetTagged('RogueliteZombie') do
   local hum=npc:FindFirstChildOfClass('Humanoid');local root=npc:FindFirstChild('HumanoidRootPart')
   if npc:IsDescendantOf(workspace) and hum and root and hum.Health>0 then
    local distance=(root.Position-position).Magnitude
    if distance<=r.definition.blastRadius and not workspace:Raycast(origin,root.Position-origin,wallParams) then
     local amount=math.round(r.definition.damage*(1-.65*math.clamp(distance/r.definition.blastRadius,0,1)))
     damage(npc,amount,r.definition)
    end
   end
  end
 end
 RunService.Heartbeat:Connect(function(dt)
  for id,r in active do
   if (not combat:GetAttribute('ZombiesEnabled') and not r.definition.practiceTarget) or not r.character.Parent or r.definition.owner.Character~=r.character or not r.character:FindFirstChildOfClass('Humanoid') or r.character:FindFirstChildOfClass('Humanoid').Health<=0 then finish(id,r,nil);continue end
   if workspace:GetServerTimeNow()>r.expires then finish(id,r,nil);continue end
   if r.target and not Targets.alive(r.target) then
    local remaining=r.range-r.traveled
    local replacement=Targets.replacement(r.position,r.definition,nil,remaining,r.launchOrigin,rayParams)
    if not replacement or r.redirects>=8 then finish(id,r,nil);continue end
    r.target=replacement;r.redirects+=1;r.range=remaining;r.traveled=0;r.origin=r.position
    local predicted=Targets.predict(replacement,r.position,function(distance) return distance/r.definition.projectileSpeed end,0,remaining,rayParams,r.character)
    local delta=predicted-r.position;r.direction=delta.Magnitude>.01 and delta.Unit or r.direction;r.targetDistance=delta.Magnitude;r.started=workspace:GetServerTimeNow()
    event:FireAllClients('Redirect',id,r.origin,r.direction*r.definition.projectileSpeed,r.started,r.range,r.definition.projectileRadius/.12,r.targetDistance)
   end
   local distance=math.min(math.max(0,workspace:GetServerTimeNow()-r.started)*r.definition.projectileSpeed,r.range)
   local params=rayParams(r.character,false)
   -- Sweep short chords along the curve, including on delayed frames.
   while active[id] and r.traveled<distance do
    local nextDistance=math.min(distance,r.traveled+.65)
    local position=Motion.position(r.origin,r.direction,nextDistance,r.targetDistance,id)
    local delta=position-r.position
    local result=delta.Magnitude>.0001 and workspace:Spherecast(r.position,r.definition.projectileRadius,delta,params)
    if result then finish(id,r,result)
    else r.position=position;r.traveled=nextDistance end
   end
   if active[id] and r.traveled>=r.range then finish(id,r,nil) end
  end
 end)
 local self={}
 function self:launch(character,definition,slotOrigin,aim)
  if nextId>0 then local count=0;for _ in active do count+=1 end;if count>=128 then return end end
  if (aim-slotOrigin).Magnitude<.01 then return end
  local direction=(aim-slotOrigin).Unit
  -- Start at the barrel mouth. Check the short path to the muzzle too, so a
  -- nearby wall cannot be skipped when the launcher is pressed against it.
  local origin=slotOrigin+direction*1.8+Vector3.yAxis*.25
  local muzzleAim=aim-origin
  if muzzleAim.Magnitude>.01 then direction=muzzleAim.Unit end
  nextId+=1
  local targetDistance=math.clamp((definition.rocketTargetDistance or (aim-slotOrigin).Magnitude)-1.8,0,definition.range)
  local r={character=character,definition=definition,position=origin,origin=origin,direction=direction,traveled=0,targetDistance=targetDistance,started=workspace:GetServerTimeNow()}
  active[nextId]=r
  r.target=definition.arcTarget;r.launchOrigin=origin;r.range=definition.range;r.expires=workspace:GetServerTimeNow()+10;r.redirects=0
  event:FireAllClients('Launch',nextId,origin,direction*definition.projectileSpeed,r.started,definition.range,definition.projectileRadius/.12,targetDistance)
  local obstruction=workspace:Raycast(slotOrigin,origin-slotOrigin,rayParams(character,false))
  if obstruction then finish(nextId,r,obstruction) end
 end
 return self
end
return Rocket
