-- Server-owned modeled throws, return flights, cone damage and bounded zones.
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local RS=game:GetService('ReplicatedStorage')
local Motion=require(RS.RogueliteCombat.SpecialMotion)
local WeaponMotion=require(RS.RogueliteCombat.WeaponMotion)
local Stats=require(RS.RogueliteCombat.CharacterStats)
local Targets=require(RS.RogueliteCombat.ProjectileTarget)
local Ground=require(RS.RogueliteCombat.GroundContact)
local S={}
function S.new(combat,damage,rayParams)
 local Area=require(script.Parent.UtilityWeapons) -- also the spray / stream Area Size rule (2026-10-09)
 local utility=Area.new(combat,damage,rayParams)
 local chickens=require(script.Parent.EggChickens).new(combat,damage,rayParams)
 local event=combat:WaitForChild('SpecialFX');local flights={};local zones={};local serial=0
 local ground=Ground.new()
 local duckBursts={}
 local ballRadius=Ground.ballGeometry(combat.WeaponTemplates:FindFirstChild('22'))
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
  return d.owner.Character==d.character and h and h.Health>0 and not combat:GetAttribute('RunPaused') and not d.owner:GetAttribute('RunDown') and state and state:GetAttribute('WeaponEnabled') and slot and slot:GetAttribute('WeaponId')==d.id and (not d.copyId or slot:GetAttribute('CopyId')==d.copyId) and (combat:GetAttribute('ZombiesEnabled') or d.practiceTarget)
 end
 local function allowed(npc,d)
  return not d.practiceTarget or npc:GetAttribute('PracticeTarget')==true
 end
 local function duckPulse(r)
  local d=r.d
  local root=d.character:FindFirstChild('HumanoidRootPart')
  local state=combat.PlayerStates:FindFirstChild(tostring(d.owner.UserId))
  if not root then return end
  local origin=WeaponMotion.combatOrigin(root.CFrame,state and state:GetAttribute('RingRadius') or WeaponMotion.BaseRadius,d.slotIndex,d.id,d.kind)
  -- r.spread: the Area Size scale, so the flames fan as wide as the cone hits (2026-10-09).
  event:FireAllClients('Spray',nextId(),origin,r.direction,r.length,d.owner.UserId,d.slotIndex,r.timing.emission,r.spread)
  local wall=rayParams(d.character,true)
  for _,npc in Tags:GetTagged('RogueliteZombie') do
   local h=npc:FindFirstChildOfClass('Humanoid');local target=npc:FindFirstChild('HumanoidRootPart')
   if h and h.Health>0 and target and allowed(npc,d) then
    local delta=target.Position-origin
    if delta.Magnitude<=r.length and delta.Magnitude>.01 and delta.Unit:Dot(r.direction)>r.coneDot and not workspace:Raycast(origin,delta,wall) then
     damage(npc,d.damage*r.timing.damageScale,d)
    end
   end
  end
 end
 local function zone(d,position,kind)
  local own={};local total=0
  for key,z in zones do total+=1;if z.d.owner==d.owner and z.d.id==d.id then table.insert(own,key) end end
  table.sort(own)
  -- Fire 4 / Poison 3 per player and weapon id (SpecialMotion.Fire.cap); the oldest goes first.
  local tuning=kind=='Fire' and Motion.Fire or Motion.Poison
  while #own>=tuning.cap do local key=table.remove(own,1);zones[key]=nil;event:FireAllClients('ZoneEnd',key) end
  if total>=64 then return end
  local ground=workspace:Raycast(position+Vector3.yAxis*3,-Vector3.yAxis*30,rayParams(d.character,true))
  if ground then position=ground.Position+Vector3.yAxis*(kind=='Fire' and .15 or 2) end
  -- Fire starts big and burns down (SpecialMotion.zoneRadius); poison stays one size.
  local r0,r1=Motion.zoneRadii(kind,Stats.mult(d.stats.AreaSize))
  local duration=math.clamp(tuning.duration*Stats.mult(d.stats.Duration),2,12)
  local hold=Motion.zoneHold(kind,duration)
  local now=workspace:GetServerTimeNow()
  local key=nextId();zones[key]={d=d,position=position,radius=r0,r0=r0,r1=r1,hold=hold,born=now,duration=duration,ends=now+duration,nextTick=0,ticks=0,kind=kind,tuning=tuning}
  -- r0 stays the 4th value, so older listeners (the Armory showcase) still get the start size.
  event:FireAllClients('Zone',key,kind,position,r0,duration,r1,now,hold)
 end
 local function endFlight(r)
  if r.ended then return end
  r.ended=true
  flights[r.key]=nil;event:FireAllClients('End',r.key)
 end
 local function segment(r,finish,returning)
  r.origin=r.position;r.finish=finish;r.started=workspace:GetServerTimeNow();r.t=0;r.returning=returning
  r.height=r.d.id=='31' and 0 or returning and 1 or math.min(Motion.profiles[r.d.id].height,(finish-r.origin).Magnitude*.2)
  r.duration=Motion.duration(r.origin,finish,r.d.projectileSpeed*(returning and 1.35 or 1))
  event:FireAllClients('Segment',r.key,r.origin,finish,r.started,r.duration,r.height,returning)
 end
 local function returnOrEnd(r)
  if r.ended then return end
  if Motion.profiles[r.d.id].returns and not r.returning then
   local root=r.d.character:FindFirstChild('HumanoidRootPart')
   if root then
    local state=combat.PlayerStates:FindFirstChild(tostring(r.d.owner.UserId))
    segment(r,WeaponMotion.origin(root.CFrame,state and state:GetAttribute('RingRadius') or WeaponMotion.BaseRadius,r.d.slotIndex),true);return
   end
  end
  endFlight(r)
  -- Complete the flight before invoking optional landing behavior. If an asset or capability
  -- fails while hatching, that finished egg must not retry the same hatch every Heartbeat.
  chickens:landed(r.d,r.position)
 end
 local function impact(r,result)
  local d=r.d;local profile=Motion.profiles[d.id]
  local npc=result and result.Instance:FindFirstAncestorOfClass('Model')
  if npc and Tags:HasTag(npc,'RogueliteZombie') and allowed(npc,d) and not r.hit[npc] then
   r.hit[npc]=true
   if d.id~='22' or (r.contacts or 0)<24 then damage(npc,d.damage*r.factor,d) end
   -- A bowling ball stays on its lane after contact. Keep a bounded damage budget, but never
   -- destroy the rolling visual merely because its original pierce charges ran out.
   if d.id=='22' then r.contacts=(r.contacts or 0)+1;r.factor=math.max(.2,r.factor*.7);return end
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
  for key,r in duckBursts do
   if not valid(r.d) or now>=r.ends then duckBursts[key]=nil
   elseif r.pulses<r.timing.pulses and now>=r.nextPulse then
    -- No catch-up packet storm after a stall; retain a visible pulse spacing.
    duckPulse(r);r.pulses+=1;r.nextPulse=now+r.timing.spacing
   end
  end
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
    if r.d.id=='22' then
     local floorCenter=ground:center(pos,r.radius,r.position.Y-r.radius-Ground.Clearance)
     if not floorCenter then landed(r,r.position);endFlight(r);break end
     pos=floorCenter
    end
    local delta=pos-r.position
    local hit
    if not r.returning and delta.Magnitude>.001 then
     hit=workspace:Spherecast(r.position,r.radius,delta,Targets.sweepParams(r,rayParams(r.d.character,false)))
    end
    -- Spherecast.Position is the contact surface, not the sphere centre. Snapping a rolling ball
    -- onto an enemy's ankle used to drop its next sweep into the floor and make it pop.
    r.position=r.d.id=='22' and pos or hit and hit.Position or pos;r.t=t;r.remaining-=delta.Magnitude
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
    z.nextTick=now+z.tuning.tick
    -- The radius right now: a fire burns down from r0 to r1 (SpecialMotion.zoneRadius).
    z.radius=Motion.zoneRadius(z.r0,z.r1,now-z.born,z.duration,z.hold)
    -- The first tick is the ignition (Fire: 100% across the full start radius) and shows as a hit.
    local ignition=z.ticks==0;z.ticks+=1
    local factor=ignition and z.tuning.ignite or z.tuning.factor
    local wall=rayParams(z.d.character,true)
    for _,npc in Tags:GetTagged('RogueliteZombie') do
     local root=npc:FindFirstChild('HumanoidRootPart');local h=npc:FindFirstChildOfClass('Humanoid')
     if h and h.Health>0 and root and allowed(npc,z.d) and (root.Position-z.position).Magnitude<=z.radius and not workspace:Raycast(z.position+Vector3.yAxis*.3,root.Position-z.position-Vector3.yAxis*.3,wall) then
      -- Secondary ticks cannot proc crit, chains, knockback or status stacks. A damage-over-time
      -- tick (last true): clients show its number without a splat or flash.
      -- Element (2026-10-10 hit colours): a fire zone's ignition splash and ticks are 'Burn', a
      -- poison cloud's 'Poison', so they show only that colour (no cream number or white streaks).
      damage(npc,z.d.damage*factor,z.d,true,not (ignition and z.kind=='Fire'),nil,z.kind=='Fire' and 'Burn' or 'Poison')
     end
    end
   end
  end
 end)
 local self={hooks=hooks}
 function self:handles(id) return Motion.profiles[id]~=nil or id=='17' or id=='28' or id=='29' end
 function self:busy(player,index)
  local r=duckBursts[tostring(player.UserId)..':'..index]
  if r and valid(r.d) and workspace:GetServerTimeNow()<r.ends then return true end
  for _,r in flights do if r.d.owner==player and r.d.slotIndex==index and Motion.profiles[r.d.id].returns then return true end end
  return false
 end
 function self:launch(d,origin,aim)
  if not valid(d) then return end
  if d.id=='28' or d.id=='29' then utility:launch(d,origin,aim);return end
  if d.id=='17' then
   local key=tostring(d.owner.UserId)..':'..d.slotIndex
   local previous=duckBursts[key]
   local now=workspace:GetServerTimeNow()
   if previous and valid(previous.d) and now<previous.ends then return end
   local timing=Motion.duckTiming(d.cooldown)
   local r={d=d,direction=(aim-origin).Magnitude>.01 and (aim-origin).Unit or -Vector3.zAxis,
    length=math.min(d.range,14*Stats.mult(d.stats.AttackRange)),timing=timing,
    ends=now+timing.cycle,pulses=1,nextPulse=now+timing.spacing,
    -- Area Size widens the cone (UtilityWeapons.duckConeDot): +50% Area -> 49.3 deg instead of 32.9.
    coneDot=Area.duckConeDot(d.stats.AreaSize),spread=Area.areaScale(d.stats.AreaSize)}
   -- Direction is committed for this burst; new targets are acquired on the next burst.
   duckBursts[key]=r;duckPulse(r)
   return
  end
  local profile=Motion.profiles[d.id];if not profile then return end
  local existing=0;for _ in flights do existing+=1 end
  local count=math.min(5,1+Stats.shotStat(d,'ProjectileCount')) -- CharacterStats.usesStat (2026-10-03)
  if profile.returns then count=1 end
  if existing+count>128 then return end
  local state=combat.PlayerStates:FindFirstChild(tostring(d.owner.UserId));local slot=state and state:FindFirstChild('Slot'..d.slotIndex)
  local reserve=profile.reserve and ((slot and slot:GetAttribute('ThrowIndex') or 0)%3+1) or 1
  if slot then slot:SetAttribute('ThrowIndex',reserve) end
  for i=1,count do
   local def=table.clone(d);local target=aim;local from=origin
   local delay=(i-1)*.06
   -- Predict once, then commit. This flight does not keep a live target reference: ordinary
   -- pins, eggs, molotovs and kunai never steer after release. Only a contact bounce or the
   -- authored return phase creates a new segment.
   if d.arcTarget then target=Targets.predict(d.arcTarget,origin,function(distance) return Motion.duration(Vector3.zero,Vector3.xAxis*distance,d.projectileSpeed) end,delay,d.range,rayParams,d.character,d.id=='14') end
   if i>1 then target+=Vector3.new((i%2==0 and 1 or -1)*i*.65,0,0) end
   -- A rolling ball continues through the first target down the entire lane.
   local radius=math.clamp(d.id=='22' and .8 or d.id=='08' and .45 or d.id=='23' and math.max(.55,d.projectileRadius) or d.projectileRadius,.12,1.2)
   if d.id=='22' then
    radius=ballRadius*math.clamp(d.projectileRadius/.12,1,2.5)
    from=ground:center(origin,radius)
    if not from then continue end
    local lane=Vector3.new(target.X-origin.X,0,target.Z-origin.Z)
    if lane.Magnitude<.01 then continue end
    target=from+lane.Unit*d.range
   end
   local key=nextId();local height=math.min(profile.height,(target-origin).Magnitude*.2)
   local r={key=key,d=def,origin=from,finish=target,position=from,launchOrigin=from,started=workspace:GetServerTimeNow()+delay,height=height,duration=Motion.duration(from,target,d.projectileSpeed),t=0,hit={},factor=1,bounces=math.min(4,d.nativeBounce+Stats.shotStat(d,'Bounce')),pierces=math.min(4,d.nativePierce+Stats.shotStat(d,'Pierce')),remaining=d.range*1.8,expires=workspace:GetServerTimeNow()+8,radius=radius}
   flights[key]=r
   event:FireAllClients('Launch',key,d.id,d.owner.UserId,d.slotIndex,reserve,from,target,r.started,r.duration,height,d.id=='22' and radius or nil)
  end
 end
 return self
end
return S
