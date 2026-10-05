local Tags=game:GetService('CollectionService')
local RunService=game:GetService('RunService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Stats=require(combat.CharacterStats)
local Characters=require(script.Parent.CharacterService)
local Death=require(combat.ZombieDeath)
-- Hits and chain/armor shots go to players near them plus the attacker (ShotBatch), not the lobby.
local Batch=require(combat.ShotBatch)
local STUDIO=RunService:IsStudio()
-- A frame's non-lethal hits go out together over HitFX, unreliable (ShotBatch.hitWriter says
-- why), flushed at the start of the next frame with the chain bolts queued before them. A kill
-- goes at once on the reliable Hit remote, after the hits still queued: it must reach clients
-- before the enemy's removal does (the Ray Gun dissolves the body it gets).
-- Made here when the place lacks it. If even that fails, hits go one by one on Hit as before.
local hitFX=combat:FindFirstChild('HitFX')
if not hitFX then
 local ok,made=pcall(function()
  local r=Instance.new('UnreliableRemoteEvent');r.Name='HitFX';r.Sandboxed=true
  r.Capabilities=SecurityCapabilities.new(Enum.SecurityCapability.Basic,Enum.SecurityCapability.RemoteEvent);r.Parent=combat
  return r
 end)
 if ok then hitFX=made else warn('HitFX could not be made; hits go one by one:',made) end
end
local hits=hitFX and Batch.hitWriter(hitFX) or {flush=function() end,push=function(_,owner,position,actual,npc,lethal,secondary,dot,id)
 Batch.fire(combat.Hit,position,owner,position+Vector3.yAxis*2,actual,npc,position,lethal,secondary,id,owner.UserId,dot)
end}
local bolts=Batch.writer(combat:WaitForChild('Shot'))
local function flush() bolts:flush();hits:flush() end
RunService.PreSimulation:Connect(flush)
local E={statuses={}}
local weaponTotals={};local telemetryElapsed=0
-- Aggregate rapid fire/card hits in server memory; replicate at most four times a second.
-- ShopService flushes before snapshots and inventory mutations so sale/combine never loses a hit.
function E.flushWeaponStats()
 for slot,total in weaponTotals do
  if slot.Parent and slot:GetAttribute('CopyId')==total.copyId and slot:GetAttribute('WeaponId')==total.id then
   slot:SetAttribute('RunDamage',(slot:GetAttribute('RunDamage') or 0)+total.damage)
   if total.kills>0 then slot:SetAttribute('RunKills',(slot:GetAttribute('RunKills') or 0)+total.kills) end
  end
 end
 table.clear(weaponTotals)
end
RunService.Heartbeat:Connect(function(dt)
 telemetryElapsed+=dt
 if telemetryElapsed>=.25 then telemetryElapsed=0;E.flushWeaponStats() end
end)
-- When each enemy was last knocked back (os.clock()), kept on the server: as an attribute it
-- replicated on every shove. Weapons and pets (PetService) share it: one shove per 0.12 s.
E.knockedAt=setmetatable({},{__mode='k'})
-- E.onHit(npc,d,actual,secondary) and E.onKill(npc,d,position,secondary): set by GodlyWeapons (the
-- Vampire Blade's healing, the Scythe's wraiths, the Ray Gun's burst). Never on practice targets.
-- Damage listeners: E.listenDamage(fn) adds fn(owner,sourceId,actual,secondary,lethal) for every real
-- (non-practice) hit, status tick, chain and blast. sourceId is the weapon id, or e.g. 'Armor'.
-- Several can listen (RunAnalytics' damage by weapon, the Deal Damage quest). They run inside
-- this sandboxed module's thread, so they should only add up numbers.
local damageListeners={}
function E.listenDamage(fn) if type(fn)=='function' then table.insert(damageListeners,fn) end end
local function alive(npc)
 local h=npc and npc:FindFirstChildOfClass('Humanoid');local r=npc and npc:FindFirstChild('HumanoidRootPart')
 if npc and npc:IsDescendantOf(workspace) and h and r and h.Health>0 then return h,r end
end
local function valid(d)
 local h=d.owner and d.owner.Character and d.owner.Character:FindFirstChildOfClass('Humanoid')
 return h and h.Health>0 and d.owner.Character==d.character
end
local function near(position,range,skip,character)
 local list={}
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude
 params.FilterDescendantsInstances={workspace:FindFirstChild('RogueliteEnemies'),character}
 for _,npc in Tags:GetTagged('RogueliteZombie') do
  local h,r=alive(npc)
  if h and not skip[npc] and (r.Position-position).Magnitude<=range and not workspace:Raycast(position,r.Position-position,params) then table.insert(list,npc) end
 end
 table.sort(list,function(a,b) return (a.HumanoidRootPart.Position-position).Magnitude<(b.HumanoidRootPart.Position-position).Magnitude end)
 return list
end
local function status(npc,d,name,duration,amount,spread)
 local h,r=alive(npc);if not h then return end
 local entries=E.statuses[npc];if not entries then entries={};E.statuses[npc]=entries end
 local key=tostring(d.owner.UserId)..name;local old=entries[key]
 entries[key]={name=name,d=d,ends=os.clock()+duration,nextTick=old and old.nextTick or os.clock()+1,amount=amount,stacks=name=='Poison' and math.min(d.stats.PoisonStacks,(old and old.stacks or 0)+1) or 1,spread=spread}
 -- Only CharacterStatsTests reads these; no client does, so live servers don't replicate them.
 if STUDIO then npc:SetAttribute(name..'Until',workspace:GetServerTimeNow()+duration) end
end
-- dot: a burn/poison tick or a zone tick (SpecialWeapons). Clients show its number but not a
-- splat or flash. It changes nothing else here.
-- stream (2026-10-03): a Vacuum / Power Washer stream tick (UtilityWeapons), as its share of one
-- attack: a .12 s tick of a .32 s cooldown is .375. The tick is the weapon's own hit (user: their
-- cards say "Any weapon"), so it crits and rolls burn, poison, slow and lightning, each at share x
-- its chance, so a stream procs as often a second as a weapon attacking at its cooldown. Example:
-- Ice Cube 15% -> 5.6% a tick. Clients still draw it as a light tick (secondary on the wire), and it
-- never knocks back (the Vacuum pulls). What it sets off (chains, burn ticks) stays secondary.
function E.hit(npc,amount,d,secondary,dot,stream)
 local own=not secondary or type(stream)=='number' -- the weapon's own hit: crits and procs
 local share=type(stream)=='number' and math.clamp(stream,0,1) or 1
 local h,r=alive(npc);if not h or not d or not valid(d) then return 0 end
 if not Tags:HasTag(npc,'RogueliteZombie') then return 0 end
 -- A wave boss can't be hurt during its super-jump entrance (BossService BossIntroUntil).
 if (npc:GetAttribute('BossIntroUntil') or 0)>workspace:GetServerTimeNow() then return 0 end
 -- Tag before damage: the Died handler can run immediately on a lethal shot.
 if d.id=='10' and not secondary and amount>0 and not npc:GetAttribute('LobbyDummy') and not npc:GetAttribute('DesignerShirt') then npc:SetAttribute('DesignerShirt',true) end
 local s=d.stats;local position=r.Position
 if own then
  -- Ninja 4-piece: after a dodge (CharacterService.contact) the next direct hit always crits. Not a
  -- turret's nail (d.structure, HandymanTurret 2026-10-04: turrets never crit), so it keeps it.
  local owner=Characters.states[d.owner];local sure=owner and owner.dodgeCrit and not d.structure
  if sure then owner.dodgeCrit=nil end
  if sure or math.random()<s.CritChance/100 then amount*=s.CritDamage/100 end
 end
 -- Gear power (CharacterStats.powerDamage): every hit, status tick, pet and armor blast passes here.
 amount*=Stats.powerDamage(s.GearPower)
 if npc:GetAttribute('IsElite') or npc:GetAttribute('IsBoss') then amount*=Stats.mult(s.BossDamage) end
 -- Owl pet mark (PetService): +bonus% on every hit from the owner while the mark lasts.
 local mark=npc:GetAttribute('PetMark_'..d.owner.UserId)
 if type(mark)=='number' and (npc:GetAttribute('PetMarkUntil_'..d.owner.UserId) or 0)>workspace:GetServerTimeNow() then amount*=1+mark/100 end
 if Death.isPractice(npc) then
  local actual=math.min(h.Health,math.max(0,amount))
  if actual<=0 then return 0 end
  h.Health=h.Health-actual>1 and h.Health-actual or h.MaxHealth
  -- QA counters (ArcAttackTests): Studio only, they replicated on every practice hit.
  if STUDIO then
   npc:SetAttribute('PracticeHits',(npc:GetAttribute('PracticeHits') or 0)+1)
   npc:SetAttribute('PracticeDamage',(npc:GetAttribute('PracticeDamage') or 0)+actual)
   npc:SetAttribute('LastWeaponId',d.id)
  end
  hits:push(d.owner,position,actual,npc,false,secondary==true,dot==true,d.id)
  return actual -- no death, rewards, lifesteal farming or damage to the tester
 end
 -- Kill credit, read when the enemy dies (quests count Utility kills; leaderboard, shard and
 -- heart owners). Written before the damage, as before, but only when it changes: one player's
 -- minigun no longer rewrites both on every bullet. The value at any moment is the same.
 if npc:GetAttribute('LastDamageUserId')~=d.owner.UserId then npc:SetAttribute('LastDamageUserId',d.owner.UserId) end
 if npc:GetAttribute('LastWeaponId')~=d.id then npc:SetAttribute('LastWeaponId',d.id) end
 local before=h.Health;h:TakeDamage(math.max(0,amount));local actual=before-math.max(0,h.Health)
 if actual<=0 then return 0 end
 -- Run-only, server-authoritative per-copy counters. A delayed status cannot credit an unrelated
 -- weapon now occupying this slot. ShopService carries counters with copies when combining.
 local ownerState=Characters.states[d.owner]
 local slot=ownerState and ownerState.folder and type(d.slotIndex)=='number' and d.slotIndex<=6 and ownerState.folder:FindFirstChild('Slot'..d.slotIndex)
 if slot and slot:GetAttribute('WeaponId')==d.id and slot:GetAttribute('CopyId')==d.copyId then
  local total=weaponTotals[slot]
  if not total or total.copyId~=d.copyId then total={copyId=d.copyId,id=d.id,damage=0,kills=0};weaponTotals[slot]=total end
  total.damage+=actual;if h.Health<=0 then total.kills+=1 end
 end
 for _,fn in damageListeners do local ok,err=pcall(fn,d.owner,d.id,actual,secondary==true,h.Health<=0);if not ok then warn('listenDamage failed:',err) end end
 if not d.structure then Characters.leech(d.owner,actual) end -- turrets don't life-steal (HandymanTurret)
 if E.onHit then local ok,err=pcall(E.onHit,npc,d,actual,secondary==true);if not ok then warn('onHit failed:',err) end end
 if STUDIO then combat:SetAttribute('ConfirmedHits',(combat:GetAttribute('ConfirmedHits') or 0)+1) end
 -- A lethal hit is represented by the death burst, not a second hit burst.
 -- The weapon id lets clients add that weapon's impact sound (RogueliteSounds). A kill also
 -- carries its owner and dot flag (HitFX packs those).
 if h.Health<=0 then
  flush()
  Batch.fire(combat.Hit,position,d.owner,position+Vector3.new(0,2,0),actual,npc,position,true,secondary==true,d.id,d.owner.UserId,dot==true)
 else hits:push(d.owner,position,actual,npc,false,secondary==true,dot==true,d.id) end
 if h.Health<=0 then
  local entries=E.statuses[npc]
  if entries then
   for _,effect in entries do if effect.name=='Burn' and effect.spread and effect.ends>os.clock() then
    for i,target in near(position,8*Stats.mult(effect.d.stats.AreaSize),{[npc]=true},effect.d.character) do
     if i>effect.d.stats.BurnSpread then break end
     status(target,effect.d,'Burn',3*Stats.mult(effect.d.stats.Duration),effect.amount,false)
    end
   end end
  end
  E.statuses[npc]=nil
  if E.onKill then local ok,err=pcall(E.onKill,npc,d,position,secondary==true);if not ok then warn('onKill failed:',err) end end
  Death.finish(npc);return actual
 end
 if not own then return actual end
 local knockback=math.min(40,s.Knockback+(d.nativeKnockback or 0))
 if knockback>0 and not secondary and os.clock()-(E.knockedAt[npc] or -1e6)>.12 then
  local pr=d.character:FindFirstChild('HumanoidRootPart');local delta=pr and Vector3.new(position.X-pr.Position.X,0,position.Z-pr.Position.Z)
  if delta and delta.Magnitude>.01 then r:ApplyImpulse(delta.Unit*knockback*r.AssemblyMass*(npc:GetAttribute('IsBoss') and .25 or 1));E.knockedAt[npc]=os.clock() end
 end
 local elemental=Stats.mult(s.Damage)*Stats.mult(s.ElementalDamage)
 if math.random()<share*math.max(s.BurnChance,d.burn or 0)/100 then status(npc,d,'Burn',3*Stats.mult(s.Duration),6*elemental*Stats.mult(s.BurnDamage),true) end
 if math.random()<share*math.max(s.PoisonChance,d.poison or 0)/100 then status(npc,d,'Poison',4*Stats.mult(s.Duration),3*elemental*Stats.mult(s.PoisonDamage),false) end
 -- A weapon's native slow (WeaponCatalog.SlowById, Medusa 35% for 2 s) or the player's stats, whichever is bigger.
 if math.random()<share*math.max(s.SlowChance,d.slow or 0)/100 then status(npc,d,'Slow',math.max(s.SlowDuration,d.slowFor or 0)*Stats.mult(s.Duration),math.min(70,math.max(s.SlowStrength,d.slowStrength or 0)),false) end
 local state=Characters.states[d.owner]
 if state then
  -- A stream tick counts as its share of a hit: with ChainEvery 5, about every 13 ticks at .375.
  local before=state.hits;state.hits+=share
  local sourceCount=math.max(s.ChainCount,d.lightning and 1 or 0)
  local count=math.min(6,sourceCount+s.ChainBonus)
  if sourceCount>0 and math.floor(state.hits/s.ChainEvery)>math.floor(before/s.ChainEvery) then
   for i,target in near(position,12*Stats.mult(s.AreaSize),{[npc]=true},d.character) do
    if i>count then break end
    bolts:push(d.owner,position,target.HumanoidRootPart.Position,'Lightning',d.id)
    E.hit(target,d.damage*.4*Stats.mult(s.ChainDamage),d,true)
   end
  end
 end
 return actual
end
-- Armor perks hit through the same path as weapons, with a weapon-like source whose id is 'Armor'
-- (no weapon sound or style on clients). It is only valid while the wearer's body is alive.
local function armorSource(player)
 local state=Characters.states[player];local character=player and player.Character
 if not state or not state.stats or not character then return end
 local d={id='Armor',owner=player,character=character,stats=state.stats,damage=0}
 if valid(d) then return d end
end
-- Dragon Scale 4-piece fire thorns (CharacterService.contact rolls the chance): the zombie that
-- hit the wearer gets a normal burn, 6/s for 3 s scaled by the wearer's burn stats like a weapon burn.
Characters.onThorns=function(player,npc)
 local d=armorSource(player);if not d or not alive(npc) or not Tags:HasTag(npc,'RogueliteZombie') then return end
 local s=d.stats
 status(npc,d,'Burn',3*Stats.mult(s.Duration),6*Stats.mult(s.Damage)*Stats.mult(s.ElementalDamage)*Stats.mult(s.BurnDamage),true)
end
-- Phoenix 4-piece rise (RogueliteMeta): `damage` to every living zombie within `radius` of
-- `position`, with the Blast burst on clients. Returns how many zombies were hit.
function E.armorBlast(player,position,radius,damage)
 local d=armorSource(player);if not d then return 0 end
 Batch.fire(combat.Shot,position,player,position+Vector3.yAxis*.5,position,'Blast','Armor',.07,radius)
 local count=0
 for _,npc in Tags:GetTagged('RogueliteZombie') do
  local h,r=alive(npc)
  if h and not npc:GetAttribute('LobbyDummy') and (r.Position-position).Magnitude<=radius then E.hit(npc,damage,d,true);count+=1 end
 end
 return count
end
-- Pets (PetService) apply burn, poison and slow through the same status table as weapons.
E.status=status
local elapsed=0
local pausedAt -- plan L: os.clock() when the run paused
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.1 then return end;elapsed=0
 local now=os.clock()
 -- Pause (plan L): statuses wait out a paused run, then their end and tick times move later by it.
 if combat:GetAttribute('RunPaused')==true then pausedAt=pausedAt or now;return end
 if pausedAt then
  local by=now-pausedAt;pausedAt=nil
  local serverBy=by
  for npc,entries in E.statuses do
   for _,e in entries do e.ends+=by;e.nextTick+=by end
   for _,name in {'Burn','Poison','Slow'} do local u=npc:GetAttribute(name..'Until');if u then npc:SetAttribute(name..'Until',u+serverBy) end end
  end
 end
 for npc,entries in E.statuses do
  local h=alive(npc)
  if not h then E.statuses[npc]=nil;continue end
  local slow=0
  for key,e in entries do
   if now>=e.ends or not valid(e.d) then entries[key]=nil
   elseif e.name=='Slow' then slow=math.max(slow,e.amount)
   elseif now>=e.nextTick then e.nextTick=now+1;E.hit(npc,e.amount*e.stacks,e.d,true,true) end
  end
  if h.Parent and h.Health>0 then
   slow*=npc:GetAttribute('IsBoss') and .5 or 1
   if npc:GetAttribute('StatusSlowStrength')~=slow then npc:SetAttribute('StatusSlowStrength',slow) end
   local vacuumSlow=(npc:GetAttribute('VacuumSlowUntil') or 0)>workspace:GetServerTimeNow() and 35 or 0
   h.WalkSpeed=(npc:GetAttribute('BaseMoveSpeed') or 12)*(1-math.max(slow,vacuumSlow)/100)
  end
  if next(entries)==nil then E.statuses[npc]=nil end
 end
end)
return E
