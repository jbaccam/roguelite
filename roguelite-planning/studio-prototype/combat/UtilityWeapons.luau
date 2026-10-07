-- Server-owned persistent cones/streams; no client supplied damage or targets.
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local Motion=require(game.ReplicatedStorage.RogueliteCombat.WeaponMotion)
local U=require(game.ReplicatedStorage.RogueliteCombat.UtilityMotion)
local Batch=require(game.ReplicatedStorage.RogueliteCombat.ShotBatch)
local W={}
function W.new(combat,damage,rayParams)
 local streams={};local budget=0
 local function valid(d)
  local state=combat.PlayerStates:FindFirstChild(tostring(d.owner.UserId))
  local slot=state and state:FindFirstChild('Slot'..d.slotIndex)
  local h=d.character and d.character:FindFirstChildOfClass('Humanoid')
  return d.owner.Character==d.character and h and h.Health>0 and not combat:GetAttribute('RunPaused') and not d.owner:GetAttribute('RunDown') and state and state:GetAttribute('WeaponEnabled') and slot and slot:GetAttribute('WeaponId')==d.id and (combat:GetAttribute('ZombiesEnabled') or d.practiceTarget),state
 end
 RunService.Heartbeat:Connect(function(dt)
  budget+=dt;if budget<.05 then return end;local step=math.min(budget,.1);budget=0
  local now=workspace:GetServerTimeNow()
  for key,r in streams do
   local d=r.d;local ok,state=valid(d);local pr=d.character:FindFirstChild('HumanoidRootPart')
   if not ok or not pr or now>r.ends then streams[key]=nil;combat.SpecialFX:FireAllClients('StreamEnd',key);continue end
   local target=d.arcTarget
   local aim=target and target.Parent and target.Position or r.aim
   local slotOrigin=Motion.origin(pr.CFrame,state:GetAttribute('RingRadius') or Motion.BaseRadius,d.slotIndex)
   local delta=d.id=='28' and Vector3.new(aim.X-slotOrigin.X,0,aim.Z-slotOrigin.Z) or aim-slotOrigin
   local direction=delta.Magnitude>.01 and delta.Unit or Motion.frame(pr.CFrame).LookVector
   local origin=slotOrigin+direction*1.1
   local wallParams=rayParams(d.character,true) -- one filter for this stream's walls and every enemy below
   local nearWall=workspace:Raycast(slotOrigin,origin-slotOrigin,wallParams)
   if nearWall then origin=slotOrigin end
   local length=d.range
   local wall=workspace:Raycast(origin,direction*length,wallParams)
   if wall then length=math.max(.1,(wall.Position-origin).Magnitude) end
   local vacuum=d.id=='28';local width=vacuum and length*.48 or .6
   local pressure=vacuum and 1 or U.washPressure(now-r.started)
   if now>=r.nextVisual then
    r.nextVisual=now+.1
    -- Nearby players and the owner only (10 Hz); StreamEnd still goes to everyone.
    Batch.fire(combat.SpecialFX,origin,d.owner,'Stream',key,d.id,d.owner.UserId,d.slotIndex,origin,origin+direction*length,width,now+.3,U.SafeDistance,r.started)
   end
   local tickDamage=now>=r.nextDamage
   if tickDamage then r.nextDamage=now+.12 end
   for _,npc in Tags:GetTagged('RogueliteZombie') do
    local root=npc:FindFirstChild('HumanoidRootPart');local h=npc:FindFirstChildOfClass('Humanoid')
    if not root or not h or h.Health<=0 or (d.practiceTarget and not npc:GetAttribute('PracticeTarget')) then continue end
    if not U.inCone(origin,direction,root.Position,length,width,vacuum and 4 or 2) then continue end
    if workspace:Raycast(origin,root.Position-origin,wallParams) then continue end
    -- A tick is .12 s of the weapon's damage per second, and its own hit: it crits and procs items
    -- at that share of an attack (CombatEffectsService.hit's stream, 2026-10-03).
    if tickDamage and pressure>0 then local share=.12/d.cooldown*(vacuum and 1 or pressure*U.WashDamageScale);damage(npc,d.damage*share,d,true,nil,math.min(1,share)) end
    if not vacuum or h.Health<=0 or not root.Parent then continue end
    -- Shared per enemy: overlapping vacuums cannot refresh a hold forever.
    local hold=npc:GetAttribute('VacuumHoldUntil') or 0
    local immune=npc:GetAttribute('VacuumImmuneUntil') or 0
    if hold>0 and now>=hold then
     npc:SetAttribute('VacuumHoldUntil',0);npc:SetAttribute('VacuumHolder',nil);npc:SetAttribute('VacuumImmuneUntil',math.max(immune,hold+U.EscapeDuration));hold=0;immune=npc:GetAttribute('VacuumImmuneUntil')
    end
    local safe=math.max(U.SafeDistance,(npc:GetAttribute('ContactRange') or 4.5)+2)
    local distance=(Vector3.new(root.Position.X,0,root.Position.Z)-Vector3.new(pr.Position.X,0,pr.Position.Z)).Magnitude
    if now<immune or distance<=safe or npc:GetAttribute('IsBoss') then continue end
    if hold==0 then hold=now+U.HoldDuration;npc:SetAttribute('VacuumHoldUntil',hold);npc:SetAttribute('VacuumHolder',key) end
    -- Several vacuums can damage a mob, but one owns this bounded pull. Different players used
    -- to overwrite its velocity toward opposite points every tick, causing jitter and launches.
    if npc:GetAttribute('VacuumHolder')~=key then continue end
    npc:SetAttribute('VacuumSlowUntil',math.min(hold,now+.15))
    if not root.Anchored then
     local desired=U.pull(root.Position,pr.Position,direction,safe)
     local current=root.AssemblyLinearVelocity
     local flat=Vector3.new(current.X,0,current.Z):Lerp(desired,1-math.exp(-18*step))
     local inward=Vector3.new(root.Position.X-pr.Position.X,0,root.Position.Z-pr.Position.Z).Unit
     local minInward=-math.max(0,distance-safe)/step
     if flat:Dot(inward)<minInward then flat+=inward*(minInward-flat:Dot(inward)) end
     root.AssemblyLinearVelocity=Vector3.new(flat.X,current.Y,flat.Z)
    end
   end
  end
 end)
 local self={}
 function self:launch(d,origin,aim)
  local key='Utility_'..d.owner.UserId..'_'..d.slotIndex
  local now=workspace:GetServerTimeNow();local r=streams[key]
  if not r then
   local count=0;for _ in streams do count+=1 end;if count>=96 then return end
   r={nextDamage=now,nextVisual=now,started=now};streams[key]=r
  end
  r.d=d;r.aim=aim;r.ends=now+math.min(1.5,d.cooldown+.12)
 end
 return self
end
return W
