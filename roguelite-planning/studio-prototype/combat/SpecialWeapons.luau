-- Server-owned modeled throws, return flights, cone damage and bounded zones.
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local RS=game:GetService('ReplicatedStorage')
local Motion=require(RS.RogueliteCombat.SpecialMotion)
local WeaponMotion=require(RS.RogueliteCombat.WeaponMotion)
local Stats=require(RS.RogueliteCombat.CharacterStats)
local Targets=require(RS.RogueliteCombat.ProjectileTarget)
local S={}
function S.new(combat,damage,rayParams)
 local utility=require(script.Parent.UtilityWeapons).new(combat,damage,rayParams)
 -- rayParams hands out shared, read-only params; EggChickens adds its folder to the filter, so it
 -- gets a private copy (hatching is rare).
 local function ownParams(character,ignoreEnemies)
  local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude
  p.FilterDescendantsInstances=rayParams(character,ignoreEnemies).FilterDescendantsInstances;return p
 end
 local chickens=require(script.Parent.EggChickens).new(combat,damage,ownParams)
 local event=combat:WaitForChild('SpecialFX');local flights={};local zones={};local serial=0
 -- hooks.landed(d,position,struck): a 'wave' throw (the Trident) landed; set by GodlyWeapons.
 -- hooks.impact(d,position,hit): any throw stopped, once (where it hit, or where it came down),
 -- with the enemies it hit; set by LegendaryMoves (Mjolnir's lightning, the bowling STRIKE).
 local hooks={}
 local function landed(r,position)
  if hooks.impact and not r.impacted then
   r.impacted=true
   local ok,err=pcall(hooks.impact,r.d,position,r.hit);if not ok then warn('impact hook failed:',err) end
  end
  if r.landed or not Motion.profiles[r.d.id].wave then return end
  r.landed=true
  if hooks.landed then local ok,err=pcall(hooks.landed,r.d,position,r.hit);if not ok then warn('landed hook failed:',err) end end
 end
 local function nextId() serial+=1;return serial end
 local function valid(d)
  local h=d.character and d.character:FindFirstChildOfClass('Humanoid')
  local state=combat.PlayerStates:FindFirstChild(tostring(d.owner.UserId))
  local slot=state and state:FindFirstChild('Slot'..d.slotIndex)
  return d.owner.Character==d.character and h and h.Health>0 and state and state:GetAttribute('WeaponEnabled') and slot and slot:GetAttribute('WeaponId')==d.id and (combat:GetAttribute('ZombiesEnabled') or d.practiceTarget)
 end
 local function allowed(npc,d)
  return not d.practiceTarget or npc:GetAttribute('PracticeTarget')==true
 end
 local function zone(d,position,kind)
  local own={};local total=0
  for key,z in zones do total+=1;if z.d.owner==d.owner and z.d.id==d.id then table.insert(own,key) end end
  table.sort(own)
  if #own>=3 then local key=own[1];zones[key]=nil;event:FireAllClients('ZoneEnd',key) end
  if total>=64 then return end
  local ground=workspace:Raycast(position+Vector3.yAxis*3,-Vector3.yAxis*30,rayParams(d.character,true))
  if ground then position=ground.Position+Vector3.yAxis*(kind=='Fire' and .15 or 2) end
  local radius=math.clamp((kind=='Fire' and 4.5 or 5.5)*Stats.mult(d.stats.AreaSize),2,12)
  local duration=math.clamp((kind=='Fire' and 4 or 5)*Stats.mult(d.stats.Duration),2,12)
  local key=nextId();zones[key]={d=d,position=position,radius=radius,ends=workspace:GetServerTimeNow()+duration,nextTick=0,kind=kind}
  event:FireAllClients('Zone',key,kind,position,radius,duration)
 end
 local function endFlight(r)
  flights[r.key]=nil;event:FireAllClients('End',r.key)
 end
 local function segment(r,finish,returning)
  r.origin=r.position;r.finish=finish;r.started=workspace:GetServerTimeNow();r.t=0;r.returning=returning
  r.height=r.d.id=='31' and 0 or returning and 1 or math.min(Motion.profiles[r.d.id].height,(finish-r.origin).Magnitude*.2)
  r.duration=Motion.duration(r.origin,finish,r.d.projectileSpeed*(returning and 1.35 or 1))
  event:FireAllClients('Segment',r.key,r.origin,finish,r.started,r.duration,r.height,returning)
 end
 local function returnOrEnd(r)
  if Motion.profiles[r.d.id].returns and not r.returning then
   local root=r.d.character:FindFirstChild('HumanoidRootPart')
   if root then
    local state=combat.PlayerStates:FindFirstChild(tostring(r.d.owner.UserId))
    segment(r,WeaponMotion.origin(root.CFrame,state and state:GetAttribute('RingRadius') or WeaponMotion.BaseRadius,r.d.slotIndex),true);return
   end
  end
  chickens:landed(r.d,r.position) -- a landing egg may hatch a chicken
  endFlight(r)
 end
 local function impact(r,result)
  local d=r.d;local profile=Motion.profiles[d.id]
  local npc=result and result.Instance:FindFirstAncestorOfClass('Model')
  if npc and Tags:HasTag(npc,'RogueliteZombie') and allowed(npc,d) and not r.hit[npc] then
   r.hit[npc]=true;damage(npc,d.damage*r.factor,d)
   if d.id=='22' and r.pierces>0 then r.pierces-=1;r.factor*=.7;return end
   if not profile.zone and r.bounces>0 then
    local target=Targets.replacement(r.position,d,r.hit,r.remaining,r.launchOrigin,rayParams)
    if target then
     r.bounces-=1;r.factor*=.65
     local point=Targets.predict(target,r.position,function(distance) return Motion.duration(Vector3.zero,Vector3.xAxis*distance,d.projectileSpeed) end,0,r.remaining,rayParams,d.character)
     segment(r,point,false);return
    end
   end
   if not profile.zone and r.pierces>0 then r.pierces-=1;r.factor*=.7;return end
  end
  if profile.zone then zone(d,result and result.Position or r.position,profile.zone) end
  landed(r,result and result.Position or r.position)
  returnOrEnd(r)
 end
 RunService.Heartbeat:Connect(function()
  local now=workspace:GetServerTimeNow()
  for _,r in flights do
   if not valid(r.d) or now>r.expires then endFlight(r);continue end
   if now<r.started then continue end
   if r.returning then
    local root=r.d.character:FindFirstChild('HumanoidRootPart')
    if not root then endFlight(r);continue end
    local state=combat.PlayerStates:FindFirstChild(tostring(r.d.owner.UserId))
    r.finish=WeaponMotion.origin(root.CFrame,state and state:GetAttribute('RingRadius') or WeaponMotion.BaseRadius,r.d.slotIndex)
   end
   local untilT=math.clamp((now-r.started)/r.duration,0,1)
   local oldStart=r.started
   while flights[r.key] and r.t<untilT do
    local t=math.min(untilT,r.t+.02)
    local pos=Motion.position(r.origin,r.finish,t,r.height)
    local delta=pos-r.position
    local hit
    if not r.returning and delta.Magnitude>.001 then
     hit=workspace:Spherecast(r.position,r.radius,delta,Targets.sweepParams(r,rayParams(r.d.character,false)))
    end
    r.position=hit and hit.Position or pos;r.t=t;r.remaining-=delta.Magnitude
    if hit then impact(r,hit);if r.started~=oldStart then break end end
    if not r.returning and r.remaining<=0 then returnOrEnd(r);break end
   end
   if flights[r.key] and r.started==oldStart and r.t>=1 then
    if not r.returning and Motion.profiles[r.d.id].zone then zone(r.d,r.position,Motion.profiles[r.d.id].zone) end
    if not r.returning then landed(r,r.position) end
    returnOrEnd(r)
   end
  end
  for key,z in zones do
   if now>=z.ends or not valid(z.d) then zones[key]=nil;event:FireAllClients('ZoneEnd',key)
   elseif now>=z.nextTick then
    z.nextTick=now+.4
    local wall=rayParams(z.d.character,true)
    for _,npc in Tags:GetTagged('RogueliteZombie') do
     local root=npc:FindFirstChild('HumanoidRootPart');local h=npc:FindFirstChildOfClass('Humanoid')
     if h and h.Health>0 and root and allowed(npc,z.d) and (root.Position-z.position).Magnitude<=z.radius and not workspace:Raycast(z.position+Vector3.yAxis*.3,root.Position-z.position-Vector3.yAxis*.3,wall) then
      -- Secondary ticks cannot proc crit, chains, knockback or status stacks.
      damage(npc,z.d.damage*.4,z.d,true)
     end
    end
   end
  end
 end)
 local self={hooks=hooks}
 function self:handles(id) return Motion.profiles[id]~=nil or id=='17' or id=='28' or id=='29' end
 function self:busy(player,index)
  for _,r in flights do if r.d.owner==player and r.d.slotIndex==index and Motion.profiles[r.d.id].returns then return true end end
  return false
 end
 function self:launch(d,origin,aim)
  if not valid(d) then return end
  if d.id=='28' or d.id=='29' then utility:launch(d,origin,aim);return end
  if d.id=='17' then
   local direction=(aim-origin).Magnitude>.01 and (aim-origin).Unit or -Vector3.zAxis
   local length=math.min(d.range,14*Stats.mult(d.stats.AttackRange))
   event:FireAllClients('Spray',nextId(),origin,direction,length,d.owner.UserId,d.slotIndex)
   local wall=rayParams(d.character,true)
   for _,npc in Tags:GetTagged('RogueliteZombie') do
    local h=npc:FindFirstChildOfClass('Humanoid');local root=npc:FindFirstChild('HumanoidRootPart')
    if h and h.Health>0 and root and allowed(npc,d) then
     local delta=root.Position-origin
     if delta.Magnitude<=length and delta.Magnitude>.01 and delta.Unit:Dot(direction)>.84 and not workspace:Raycast(origin,delta,wall) then damage(npc,d.damage,d) end
    end
   end
   return
  end
  local profile=Motion.profiles[d.id];if not profile then return end
  local existing=0;for _ in flights do existing+=1 end
  local count=math.min(5,1+d.stats.ProjectileCount)
  if profile.returns then count=1 end
  if existing+count>128 then return end
  local state=combat.PlayerStates:FindFirstChild(tostring(d.owner.UserId));local slot=state and state:FindFirstChild('Slot'..d.slotIndex)
  local reserve=profile.reserve and ((slot and slot:GetAttribute('ThrowIndex') or 0)%3+1) or 1
  if slot then slot:SetAttribute('ThrowIndex',reserve) end
  for i=1,count do
   local def=table.clone(d);local target=aim
   local delay=(i-1)*.06
   if d.arcTarget then target=Targets.predict(d.arcTarget,origin,function(distance) return Motion.duration(Vector3.zero,Vector3.xAxis*distance,d.projectileSpeed) end,delay,d.range,rayParams,d.character,d.id=='14') end
   if i>1 then target+=Vector3.new((i%2==0 and 1 or -1)*i*.65,0,0) end
   -- A rolling ball continues through the first target down the entire lane.
   if d.id=='22' and (target-origin).Magnitude>.01 then target=origin+(target-origin).Unit*d.range end
   local key=nextId();local height=math.min(profile.height,(target-origin).Magnitude*.2)
   local r={key=key,d=def,origin=origin,finish=target,position=origin,launchOrigin=origin,started=workspace:GetServerTimeNow()+delay,height=height,duration=Motion.duration(origin,target,d.projectileSpeed),t=0,hit={},factor=1,bounces=math.min(4,d.nativeBounce+d.stats.Bounce),pierces=math.min(4,d.nativePierce+d.stats.Pierce),remaining=d.range*1.8,expires=workspace:GetServerTimeNow()+8,radius=math.clamp(d.id=='22' and .65 or d.id=='08' and .45 or d.projectileRadius,.12,1.2)}
   flights[key]=r
   event:FireAllClients('Launch',key,d.id,d.owner.UserId,d.slotIndex,reserve,origin,target,r.started,r.duration,height)
  end
 end
 return self
end
return S
