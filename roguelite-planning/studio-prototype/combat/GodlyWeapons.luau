-- Godly weapon specials (plans/2026-10-01-G-godly-weapons.md), server-owned:
--   36 Reaper's Scythe: 1 in 3 kills raise a crimson wraith that hunts and claws for 6 s
--   37 Poseidon's Trident: a throw lands with a tidal wave ring that pushes enemies out
--   38 Storm Bow: the arrow splits into storm arrows that rain on different enemies
--   39 Shadow Daggers: the pair zips through a chain of enemies
--   40 Vampire Blade: hits heal, kills send a healing wisp (shares the life-steal cap)
--   41 Ray Gun: a kill disintegrates the enemy in a burst that hits the ones nearby
-- Numbers live in WeaponCatalog.Godly. Every special is capped, and nothing it does can start
-- another special: wraith claws, wave hits, bursts and wisps are secondary hits, and kills by
-- secondary hits never raise wraiths, burst or send wisps. Clients draw from GodlyFX.
-- ModuleScript in ServerScriptService, Sandboxed (it is required by the sandboxed combat script).
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local Players=game:GetService('Players')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local Enemies=require(combat:WaitForChild('EnemyCatalog'))
local Batch=require(combat:WaitForChild('ShotBatch'))
local G={}
G.MaxWraiths=24 -- per server, whatever the owners' caps
G.MaxScheduled=512

-- Pure helpers (GodlyWeaponsTests) -----------------------------------------------------------
function G.tierValue(value,tier)
 if type(value)~='table' then return value end
 return value[math.clamp(math.floor(tier or 1),1,#value)]
end
-- Storm Bow targets: the main target first, then others (nearest first) up to n, each enemy at
-- most once; a lone enemy takes up to loneMax arrows instead.
function G.arrowTargets(main,others,n,loneMax)
 local out={main}
 for _,npc in others do
  if #out>=n then break end
  if npc~=main and not table.find(out,npc) then out[#out+1]=npc end
 end
 if #out==1 then for i=2,math.min(n,loneMax) do out[i]=main end end
 return out
end
-- Shadow Daggers chain: from the first target, hop to the nearest unvisited enemy within hop
-- studs of the last one, up to count enemies. positionOf(npc) -> Vector3 or nil (gone).
-- A lone enemy takes loneHits hits (both blades).
function G.chain(first,candidates,count,hop,loneHits,positionOf)
 local path={first};local used={[first]=true}
 while #path<count do
  local last=positionOf(path[#path]);if not last then break end
  local best,bestDistance=nil,hop
  for _,npc in candidates do
   local p=not used[npc] and positionOf(npc)
   if p then local distance=(p-last).Magnitude;if distance<=bestDistance then best,bestDistance=npc,distance end end
  end
  if not best then break end
  used[best]=true;path[#path+1]=best
 end
 if #path==1 then for i=2,loneHits do path[i]=first end end
 return path
end
-- Scythe wraith cap: the keys to fade so a new wraith fits (oldest first). list = {key,born}.
function G.overCap(list,cap)
 table.sort(list,function(a,b) return a.born<b.born end)
 local out={}
 for i=1,#list-cap+1 do out[#out+1]=list[i].key end
 return out
end
-- Tidal wave: when the ring reaches an enemy distance studs from the centre.
function G.waveDelay(distance,radius,duration) return math.clamp(distance/math.max(radius,.01),0,1)*duration end
-- Heavy mobs, elites and bosses raise the big wraith.
function G.isBig(npc)
 if npc:GetAttribute('IsBoss') or npc:GetAttribute('IsElite') or npc:GetAttribute('IsMapBoss') then return true end
 if npc:GetAttribute('ZombieType')=='Mutant' then return true end
 local enemy=Enemies.ById and Enemies.ById[npc:GetAttribute('EnemyId')]
 return enemy~=nil and enemy.behavior=='Heavy'
end

function G.new(damage,canTarget)
 local fx=combat:WaitForChild('GodlyFX')
 local Characters=require(script.Parent:WaitForChild('CharacterService'))
 local Effects=require(script.Parent:WaitForChild('CombatEffectsService'))
 local wraiths={};local wraithCount=0;local serial=0;local scheduled={}
 local function nextKey() serial+=1;return serial end
 local function alive(npc)
  local h=npc and npc.Parent and npc:FindFirstChildOfClass('Humanoid');local r=npc and npc:FindFirstChild('HumanoidRootPart')
  if h and r and h.Health>0 and npc:IsDescendantOf(workspace) and Tags:HasTag(npc,'RogueliteZombie') then return h,r end
 end
 local function ownerAlive(d)
  local h=d.character and d.character:FindFirstChildOfClass('Humanoid')
  return d.owner and d.owner.Parent==Players and d.owner.Character==d.character and h and h.Health>0
 end
 -- Living enemies this owner may hit within range of position, nearest first.
 local function around(d,position,range,skip)
  local out={}
  for _,npc in Tags:GetTagged('RogueliteZombie') do
   local h,r=alive(npc)
   if h and not (skip and skip[npc]) and (not d.practiceTarget or npc:GetAttribute('PracticeTarget')==true) and canTarget(d.owner,npc) then
    local distance=(r.Position-position).Magnitude
    if distance<=range then out[#out+1]={npc=npc,distance=distance} end
   end
  end
  table.sort(out,function(a,b) return a.distance<b.distance end)
  local list={};for i,e in out do list[i]=e.npc end
  return list
 end
 local function later(at,fn)
  if #scheduled>=G.MaxScheduled then return end
  scheduled[#scheduled+1]={at=at,fn=fn}
 end
 local function send(position,owner,...) Batch.fire(fx,position,owner,...) end
 local function special(d) return Catalog.Godly[d.id] end
 local function area(d) return Stats.mult(d.stats.AreaSize) end

 -- 36: wraiths -------------------------------------------------------------------------------
 local function fade(key)
  if not wraiths[key] then return end
  wraiths[key]=nil;wraithCount-=1
  send(nil,nil,'Fade',key)
 end
 local function raise(d,position,big)
  local spec=special(d)
  local own={}
  for key,w in wraiths do if w.d.owner==d.owner then own[#own+1]={key=key,born=w.born} end end
  local cap=G.tierValue(spec.ghostCap,d.tier)
  for _,key in G.overCap(own,cap) do fade(key) end
  if wraithCount>=G.MaxWraiths then return end
  local key=nextKey();local now=workspace:GetServerTimeNow()
  wraiths[key]={key=key,d=d,position=position+Vector3.yAxis*1.5,born=now,ends=now+spec.ghostLife,big=big,
   nextClaw=now+.45,nextSearch=now,spec=spec}
  wraithCount+=1
  send(position,d.owner,'Rise',key,d.owner.UserId,position,big,spec.ghostLife)
 end

 -- 37: tidal wave ----------------------------------------------------------------------------
 local api={}
 function api:landed(d,position,struck)
  local spec=special(d);if not spec or not spec.waveRadius or not ownerAlive(d) then return end
  local radius=math.clamp(G.tierValue(spec.waveRadius,d.tier)*area(d),4,24)
  local now=workspace:GetServerTimeNow()
  send(position,d.owner,'Wave',d.owner.UserId,position,radius,spec.waveTime)
  for _,npc in around(d,position,radius,struck) do
   local _,r=alive(npc)
   later(now+G.waveDelay((r.Position-position).Magnitude,radius,spec.waveTime),function()
    local h,root=alive(npc);if not h or not ownerAlive(d) then return end
    damage(npc,d.damage*spec.waveFactor,d,true)
    local _,after=alive(npc)
    if after then
     local away=Vector3.new(root.Position.X-position.X,0,root.Position.Z-position.Z)
     away=away.Magnitude>.05 and away.Unit or Vector3.xAxis
     local scale=npc:GetAttribute('IsBoss') and .2 or 1
     after:ApplyImpulse((away*spec.wavePush+Vector3.yAxis*spec.wavePush*.25)*after.AssemblyMass*scale)
    end
   end)
  end
 end

 -- 38: storm arrows --------------------------------------------------------------------------
 function api:handles(id) return id=='38' end
 function api:launch(d,origin,aim,target)
  local spec=special(d);if not spec or not ownerAlive(d) then return end
  local main=target and target.Parent;if not main or not alive(main) then return end
  local _,mainRoot=alive(main)
  local n=G.tierValue(spec.arrows,d.tier)+math.clamp(Stats.shotStat(d,'ProjectileCount'),0,2) -- CharacterStats.usesStat
  local list=G.arrowTargets(main,around(d,mainRoot.Position,spec.spread*area(d),{[main]=true}),n,spec.loneMax)
  local now=workspace:GetServerTimeNow()
  -- The arrow climbs to a split point above the group, then the storm arrows strike down.
  local split=mainRoot.Position+Vector3.yAxis*9
  local rise=math.clamp((split-origin).Magnitude/d.projectileSpeed,.12,.7)
  local roots={}
  for i,npc in list do
   local _,r=alive(npc);roots[i]=r and r.Position or mainRoot.Position
   local at=now+rise+.16+(i-1)*.035
   later(at,function() if alive(npc) and ownerAlive(d) then damage(npc,d.damage,d) end end)
  end
  send(origin,d.owner,'Rain',d.owner.UserId,d.slotIndex,origin,split,roots,list,now,rise)
 end

 -- 39: dagger chain --------------------------------------------------------------------------
 function api:attack(d,origin,target)
  local spec=special(d);if not spec or not ownerAlive(d) then return end
  local first=target and target.Parent;if not first or not alive(first) then return end
  local _,firstRoot=alive(first)
  local candidates=around(d,firstRoot.Position,spec.hop*area(d)*(G.tierValue(spec.chain,d.tier)),{[first]=true})
  local path=G.chain(first,candidates,G.tierValue(spec.chain,d.tier),spec.hop*area(d),spec.loneHits,function(npc)
   local _,r=alive(npc);return r and r.Position
  end)
  local now=workspace:GetServerTimeNow();local step=.09
  local points={}
  for i,npc in path do
   local _,r=alive(npc);points[i]=r and r.Position or firstRoot.Position
   later(now+.08+(i-1)*step,function() if alive(npc) and ownerAlive(d) then damage(npc,d.damage,d) end end)
  end
  send(origin,d.owner,'Chain',d.owner.UserId,d.slotIndex,origin,points,path,now,step)
 end

 -- Hit and kill hooks (CombatEffectsService) ------------------------------------------------
 Effects.onHit=function(npc,d,actual,secondary)
  if secondary or d.id~='40' then return end
  local spec=special(d)
  Characters.leechFlat(d.owner,actual*G.tierValue(spec.leech,d.tier),G.tierValue(spec.capBonus,d.tier))
 end
 Effects.onKill=function(npc,d,position,secondary)
  if secondary or not d or not Catalog.Godly[d.id] or not ownerAlive(d) then return end
  local spec=special(d)
  if d.id=='36' then
   if math.random()<spec.ghostChance then raise(d,position,G.isBig(npc)) end
  elseif d.id=='40' then
   -- The wisp flies to the wielder; it heals when it arrives.
   send(position,d.owner,'Wisp',d.owner.UserId,position)
   later(workspace:GetServerTimeNow()+.5,function()
    if ownerAlive(d) then Characters.leechFlat(d.owner,spec.wispHeal,G.tierValue(spec.capBonus,d.tier)) end
   end)
  elseif d.id=='41' then
   local radius=math.clamp(G.tierValue(spec.burstRadius,d.tier)*area(d),2,16)
   send(position,d.owner,'Burst',d.owner.UserId,position,radius)
   for _,other in around(d,position,radius,{[npc]=true}) do damage(other,d.damage*G.tierValue(spec.burstFactor,d.tier),d,true) end
  end
 end

 -- Simulation: wraiths at 30 Hz, scheduled hits every frame -------------------------------------
 local elapsed=0
 RunService.Heartbeat:Connect(function(dt)
  local now=workspace:GetServerTimeNow()
  if #scheduled>0 then
   local due={}
   for i=#scheduled,1,-1 do if scheduled[i].at<=now then due[#due+1]=scheduled[i].fn;table.remove(scheduled,i) end end
   for i=#due,1,-1 do local ok,err=pcall(due[i]);if not ok then warn('GodlyWeapons scheduled hit failed:',err) end end
  end
  elapsed+=dt;if elapsed<1/30 then return end
  local step=elapsed;elapsed=0
  for key,w in wraiths do
   if now>=w.ends or not ownerAlive(w.d) then fade(key);continue end
   local spec=w.spec
   local h,root=alive(w.target)
   if (not h or (root.Position-w.position).Magnitude>spec.ghostSight) and now>=w.nextSearch then
    w.nextSearch=now+.25
    local found=around(w.d,w.position,spec.ghostSight)[1]
    if found~=w.target then w.target=found;if found then send(w.position,w.d.owner,'Chase',key,found) end end
    h,root=alive(w.target)
   end
   if h then
    local goal=root.Position+Vector3.yAxis*1.2
    local delta=goal-w.position;local distance=delta.Magnitude
    local reach=spec.ghostReach*(w.big and 1.4 or 1)
    if distance>reach*.7 then w.position+=delta.Unit*math.min(distance-reach*.7,spec.ghostSpeed*step) end
    if distance<=reach+1 and now>=w.nextClaw then
     w.nextClaw=now+spec.ghostClawEvery
     send(w.position,w.d.owner,'Claw',key,w.target)
     damage(w.target,w.d.damage*spec.ghostClaw*(w.big and spec.bigClaw or 1),w.d,true)
    end
   end
  end
 end)
 return api
end
return G
