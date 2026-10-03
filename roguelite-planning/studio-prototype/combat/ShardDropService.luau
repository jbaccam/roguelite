-- Server owns one lightweight marker per death and credits only after magnetic arrival.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local E=require(combat.EconomyConfig)
local Motion=require(combat.ShardMotion)
local D={drops={}}
local characters,isCombat,award
local folder=Instance.new('Folder');folder.Name='RogueliteShardDrops';folder.Parent=workspace
local function living(p)
 local c=p and p.Character;local h=c and c:FindFirstChildOfClass('Humanoid');local r=c and c:FindFirstChild('HumanoidRootPart')
 return h and h.Health>0 and r
end
function D.configure(c,phase,credit) characters=c;isCombat=phase;award=credit end
-- Lookup only: drops are bucketed by their fixed origin on a CELL-stud X/Z grid, so the pickup pass
-- and the Golden Retriever look at drops near a player instead of every drop. Nothing here merges,
-- caps or deletes uncollected drops; each keeps its value and identity (ShardTests).
-- A drop put straight into D.drops (tests) has no cell and is always checked, as before.
local CELL=16
local buckets,serial={},0
local function cellKey(x,z) return x*65536+z end
local function cells(position,range)
 return math.floor((position.X-range)/CELL),math.floor((position.X+range)/CELL),math.floor((position.Z-range)/CELL),math.floor((position.Z+range)/CELL)
end
local function index(d)
 serial+=1;d.serial=serial
 d.cell=cellKey(math.floor(d.origin.X/CELL),math.floor(d.origin.Z/CELL))
 local b=buckets[d.cell];if not b then b={};buckets[d.cell]=b end
 b[d]=true
end
local function unindex(d)
 local b=d.cell and buckets[d.cell]
 if b then b[d]=nil;if next(b)==nil then buckets[d.cell]=nil end end
end
local function remove(i) local d=table.remove(D.drops,i);if d then unindex(d);d.model:Destroy() end end
-- One reused line-of-sight filter per player, rebuilt when their body or the enemy folder changes.
local sight={}
local function visible(p,from,to)
 local mobs=workspace:FindFirstChild('RogueliteEnemies')
 local c=sight[p]
 if not c or c.character~=p.Character or c.mobs~=mobs then
  local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude
  local exclude={p.Character,folder}
  if mobs then table.insert(exclude,mobs) end
  params.FilterDescendantsInstances=exclude
  c={character=p.Character,mobs=mobs,params=params};sight[p]=c
 end
 return not workspace:Raycast(from,to-from,c.params)
end
function D.collect(p,d)
 if not isCombat or not isCombat() or not d or d.collected or d.target or not d.model.Parent then return false end
 local now=workspace:GetServerTimeNow()
 if now-d.born<Motion.REST_SECONDS then return false end
 local r=living(p);local s=characters.states[p]
 if not r or not s or (d.owner and d.owner~=p) then return false end
 local radius=math.clamp(s.stats.PickupRadius or 0,0,100)
 if (r.Position-d.origin).Magnitude>radius or not visible(p,d.origin,r.Position) then return false end
 return D.start(p,d,now)
end
-- The Golden Retriever pet (PetService): the same ownership, phase and rest rules as collect, but
-- no pickup radius or line of sight (the pet brings it). PetService picks crystals within its range.
function D.fetch(p,d)
 if not isCombat or not isCombat() or not d or d.collected or d.target or not d.model.Parent then return false end
 local now=workspace:GetServerTimeNow()
 if now-d.born<Motion.REST_SECONDS then return false end
 local r=living(p);local s=characters and characters.states[p]
 if not r or not s or (d.owner and d.owner~=p) then return false end
 d.fetched=true
 return D.start(p,d,now)
end
function D.start(p,d,now)
 d.target=p;d.started=now
 d.startPosition=Motion.idle(d.origin,d.born,now)
 d.model:SetAttribute('MagnetOrigin',d.startPosition)
 d.model:SetAttribute('MagnetStart',now)
 d.model:SetAttribute('MagnetUserId',p.UserId)
 return true
end
local function cancel(d)
 d.target=nil;d.started=nil;d.position=d.origin;d.fetched=nil
 d.model:SetAttribute('MagnetUserId',nil);d.model:SetAttribute('MagnetStart',nil)
end
-- Idle drops within pickup radius of a living player in the run: the only idle drops D.collect
-- can accept this step. Distances are exact; the buckets only skip the far ones.
local function nearPlayers()
 local near={}
 for _,p in Players:GetPlayers() do
  local r=living(p);local s=characters.states[p]
  if r and s then
   local at=r.Position;local radius=math.clamp(s.stats.PickupRadius or 0,0,100)
   local x0,x1,z0,z1=cells(at,radius)
   for x=x0,x1 do for z=z0,z1 do
    local b=buckets[cellKey(x,z)]
    if b then for d in b do if not near[d] and (at-d.origin).Magnitude<=radius then near[d]=true end end end
   end end
  end
 end
 return near
end
function D.step(now)
 local near=isCombat and isCombat() and nearPlayers() or nil
 for i=#D.drops,1,-1 do
  local d=D.drops[i]
  if not d.model.Parent then remove(i)
  elseif isCombat and isCombat() then
   if d.target then
    local r=living(d.target)
    -- A fetched crystal (Golden Retriever) skips the line-of-sight check on its way in.
    -- A boss crystal (forced) flies to its player from anywhere, walls or not.
    if not r or not characters.states[d.target] or (not d.forced and ((r.Position-d.origin).Magnitude>100 or (not d.fetched and not visible(d.target,d.position,r.Position)))) then cancel(d)
    else
     d.position=Motion.pull(d.startPosition,r.Position,now-d.started)
     if now-d.started>=Motion.PULL_SECONDS then
      d.collected=true
      if award(d.target,d.value,true) then remove(i) else d.collected=false;cancel(d) end
     end
    end
   elseif near and d.cell and not near[d] then continue -- out of every pickup radius
   elseif d.owner then D.collect(d.owner,d)
   else for _,p in Players:GetPlayers() do if D.collect(p,d) then break end end end
  end
 end
end
-- A defeated wave boss showers crystals over a wide disc, and they fly to the run's players (D.spawn).
D.BOSS_DROPS=50;D.BOSS_DROP_VALUE=4
-- The shower bursts out of the boss (user, 2026-10-03: "the crystals don't pop out of the boss very
-- satisfyingly"): crystal n leaves his body BOSS_BURST_STAGGER*n seconds in and arcs to its spot
-- (ShardMotion.burst, drawn by ShardVisuals from BurstFrom / BurstDelay), all landed by about
-- 1.2 s. They start flying to their players BOSS_FLY_DELAY after the shower, one every
-- BOSS_FLY_STAGGER seconds: a pile, a beat, then a stream.
D.BOSS_BURST_STAGGER=.012
D.BOSS_FLY_DELAY=1.4;D.BOSS_FLY_STAGGER=.02
-- A kill's crystal value; nil = EconomyConfig.KILL_SHARDS. Nothing sets it now (the tutorial used
-- 5 until 2026-10-03; crystals are worth 1 everywhere).
D.killValue=nil
local function dropAt(at,owner,value,bonus)
 local model=Instance.new('Model');model.Name='CrystalShard'
 local root=Instance.new('Part');root.Name='ShardMarker';root.Size=Vector3.one*.1;root.Transparency=1
 root.Anchored=true;root.CanCollide=false;root.CanTouch=false;root.CanQuery=false;root.CastShadow=false
 root.CFrame=CFrame.new(at);root.Parent=model;model.PrimaryPart=root
 local born=workspace:GetServerTimeNow()
 model:SetAttribute('DesignerBonus',bonus)
 model:SetAttribute('Origin',at);model:SetAttribute('BornAt',born)
 model:SetAttribute('OwnerUserId',owner and owner.UserId or 0);model:SetAttribute('ShardValue',value);model.Parent=folder
 local d={model=model,position=at,origin=at,born=born,owner=owner,value=value,collected=false}
 table.insert(D.drops,d);index(d);return d
end
-- The nearest drop p may take within range of position (the Golden Retriever), ties to the older
-- drop, like a scan of D.drops in order.
function D.nearest(p,position,range)
 local best,bestDistance
 local function consider(d)
  if not d.collected and not d.target and d.model.Parent and (d.owner==nil or d.owner==p) then
   local distance=(d.origin-position).Magnitude
   if distance<=range and (not best or distance<bestDistance or distance==bestDistance and d.serial<best.serial) then best,bestDistance=d,distance end
  end
 end
 local x0,x1,z0,z1=cells(position,range)
 for x=x0,x1 do for z=z0,z1 do
  local b=buckets[cellKey(x,z)]
  if b then for d in b do consider(d) end end
 end end
 return best
end
function D.spawn(npc,position)
 if npc:GetAttribute('PracticeTarget') then return end
 if not isCombat or not isCombat() or not Tags:HasTag(npc,'RogueliteZombie') or npc:GetAttribute('ShardDropped') then return end
 local h=npc:FindFirstChildOfClass('Humanoid');if not h or h.Health>0 then return end
 npc:SetAttribute('ShardDropped',true)
 local id=npc:GetAttribute('LastDamageUserId');local owner=type(id)=='number' and Players:GetPlayerByUserId(id) or nil
 local exclude={folder,npc}
 local mobs=workspace:FindFirstChild('RogueliteEnemies');if mobs then table.insert(exclude,mobs) end
 for _,p in Players:GetPlayers() do if p.Character then table.insert(exclude,p.Character) end end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=exclude
 if npc:GetAttribute('IsHammerBoss') or npc:GetAttribute('IsMapBoss') then
  -- The run's living players share them out evenly (EconomyConfig.shareIndex: 50 across 3 players
  -- is 17 / 17 / 16). Each crystal bursts out to its spot, then flies to its player on its own,
  -- no walking over needed (2026-10-03). With nobody alive in the run they stay public, as before.
  local takers={}
  for _,p in Players:GetPlayers() do if p:GetAttribute('RunMember') and living(p) and characters and characters.states[p] then table.insert(takers,p) end end
  table.sort(takers,function(a,b) return a.UserId<b.UserId end)
  local now=workspace:GetServerTimeNow()
  local first
  for n=1,D.BOSS_DROPS do
   -- Golden-angle spiral: evenly filled disc, 3 to 14 studs from the body.
   local angle=n*2.39996;local radius=3+math.sqrt(n/D.BOSS_DROPS)*11
   local spot=position+Vector3.new(math.cos(angle)*radius,0,math.sin(angle)*radius)
   local ground=workspace:Raycast(spot+Vector3.new(0,6,0),Vector3.new(0,-100,0),params)
   local owner=#takers>0 and takers[E.shareIndex(n,#takers)] or nil
   local d=dropAt(ground and ground.Position+Vector3.new(0,1.15,0) or spot,owner,D.BOSS_DROP_VALUE,0)
   d.model:SetAttribute('BurstFrom',position+Vector3.new(0,3,0));d.model:SetAttribute('BurstDelay',n*D.BOSS_BURST_STAGGER)
   if owner then d.forced=true;D.start(owner,d,now+D.BOSS_FLY_DELAY+n*D.BOSS_FLY_STAGGER) end
   first=first or d
  end
  return first
 end
 local ground=workspace:Raycast(position+Vector3.new(0,2,0),Vector3.new(0,-100,0),params)
 local at=ground and ground.Position+Vector3.new(0,1.15,0) or position
 local base=D.killValue or E.KILL_SHARDS
 local value=base+(npc:GetAttribute('DesignerShirt')==true and E.DESIGNER_BONUS_SHARDS or 0)
 return dropAt(at,owner,value,value-base)
end
-- Wave end (ShopService.finishWave, while still in Combat): every crystal left on the ground or
-- still flying is credited now as a normal pickup (shards and XP) to its owner, else the nearest
-- living run member, and drawn flying to them: the model stays for the pull, then goes. One with
-- nobody to take it stays for D.clear(true) to bag, as before (2026-10-03).
function D.sweep()
 local now=workspace:GetServerTimeNow()
 for i=#D.drops,1,-1 do
  local d=D.drops[i]
  if d.collected or not d.model.Parent then continue end
  local p=d.target or d.owner
  if not (p and living(p) and characters.states[p]) then
   p=nil;local nearest=math.huge
   for _,q in Players:GetPlayers() do
    local root=living(q)
    if root and characters.states[q] and q:GetAttribute('RunMember') then
     local distance=(root.Position-d.origin).Magnitude
     if distance<nearest then nearest=distance;p=q end
    end
   end
  end
  if p and award(p,d.value,true) then
   d.collected=true
   -- A boss crystal still waiting its turn keeps it, so its burst and the stream play out (the
   -- boss's death usually ends the wave at once); anything else flies now.
   local flyAt=now
   if d.target==p and d.started and d.started>now then flyAt=d.started
   elseif d.target~=p or (d.started or now)>now then
    d.model:SetAttribute('MagnetOrigin',Motion.idle(d.origin,d.born,now));d.model:SetAttribute('MagnetStart',now);d.model:SetAttribute('MagnetUserId',p.UserId)
   end
   table.remove(D.drops,i);unindex(d)
   local model=d.model
   task.delay(flyAt-now+Motion.PULL_SECONDS+.1,function() model:Destroy() end)
  end
 end
end
function D.clear(bank)
 for i=#D.drops,1,-1 do
  local d=D.drops[i]
  if bank and not d.collected then
   local owner=d.owner
   if not owner then
    local nearest=math.huge
    for _,p in Players:GetPlayers() do local root=living(p)
     if root and characters.states[p] then local distance=(root.Position-d.origin).Magnitude;if distance<nearest then nearest=distance;owner=p end end
    end
   end
   if owner then d.collected=true;award(owner,d.value,false) end
  end
  remove(i)
 end
end
Players.PlayerRemoving:Connect(function(p)
 sight[p]=nil
 for i=#D.drops,1,-1 do if D.drops[i].owner==p then remove(i) elseif D.drops[i].target==p then cancel(D.drops[i]) end end
end)
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<1/30 then return end;elapsed=0;D.step(workspace:GetServerTimeNow())
end)
return D
