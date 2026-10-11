-- Turrets, server (HANDYMAN_TURRET.md). Studio: SSS.HandymanTurretService, a SANDBOXED Script
-- (Capabilities copied from SSS.RogueliteCombat), like PetService. Rules and numbers:
-- RogueliteCombat.HandymanTurret.
--
-- Turret items (2026-10-04, Brotato's structures): every turret item a run member owns (their
-- ShopService items: Nail Turret, Twin Nailer, Quad Nailer, Gatling Rig) is one turret, at most 10
-- each and 30 on the server, shared out fairly (HandymanTurret.share). At each wave start (and when
-- the sandbox starts) they are placed for the player on a ring around them, facing where they face
-- (HandymanTurret.ring / spot); the ground and sight rays run only then. Turrets added mid-wave
-- (admin Give, Scrap Magnet's temporary ones) go to free spots on the ring around the player then.
-- Temporary ones go when the wave ends. Follow (2026-10-10): mid-wave, a turret whose owner is
-- past its range packs up (PackAt, no fire, PACK_TIME) and rises again (BuiltAt, no fire,
-- BUILD_TIME) at a free spot ahead of him, 2 of a player's moving at once, 1.5 s apart
-- (HandymanTurret.leftBehind / followRing); between waves nothing moves. Turrets can't be destroyed and
-- block nothing (user, 2026-10-04: "let's not let mobs destroy the turrets"): mobs ignore them.
-- Server authority: who has turrets, where they stand, what they shoot and when are decided here.
-- Clients send nothing for turrets (BUILD and its RunAction 'BuildTurret' are gone; nothing listens
-- for it, so an old client's request is ignored) and draw:
--   workspace.RogueliteTurrets holds one Folder per turret, named UserId_n, with OwnerUserId, Index
--   (n: 1-10 from items, 11 up for Scrap Magnet's), Tier, Position (the ground point under it), Yaw
--   (its facing), BuiltAt (server time it was placed), Temp (Scrap Magnet's), Aim (where its head
--   points; nil when idle) and PackAt (server time it started packing up to follow; nil once it
--   stands again). HandymanTurret.client draws them. No server parts, no CFrame writes.
-- Life: gone when the owner leaves the run (lobby, results, disconnect) or the run resets. If the
-- owner ends up 500+ studs away (another arena) they are placed around them again. They hold fire
-- between waves, while the run is paused, through a boss entrance, while their owner is down and
-- while their owner's weapons are off.
-- Shots: a 10 Hz target pick through one TargetGrid snapshot per tick (the nearest enemy in range
-- with a clear line from the head), picked again only when a nail is due or every 0.3 s for the
-- head's aim. Nails are StatProjectiles (their own instance; projectile keys from 2^30 so clients
-- never mix them with weapon bullets) with id 'Turret' and slotIndex 100 + Index, so clients know
-- which turret fired. Hits go through CombatEffectsService as the owner's, by Brotato's structure
-- rule (HandymanTurret.weapon): kill credit and crystals, contribution, run analytics and the
-- utilityKills quest (RogueliteMeta).
-- Off until RogueliteCombat.HandymanTurrets holds T1-T4 (InstallHandymanTurret): one warning, no
-- turrets (the items still sell and wait in the inventory).
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local RS=game:GetService('ReplicatedStorage')
local SSS=game:GetService('ServerScriptService')
local combat=RS:WaitForChild('RogueliteCombat')
local H=require(combat:WaitForChild('HandymanTurret'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local Death=require(combat:WaitForChild('ZombieDeath'))
local Targets=require(combat:WaitForChild('ProjectileTarget'))
local Characters=require(SSS:WaitForChild('CharacterService'))
local Effects=require(SSS:WaitForChild('CombatEffectsService'))
local Shop=require(SSS:WaitForChild('ShopService'))
local Grid=require(SSS:WaitForChild('TargetGrid'))
local Role=require(SSS:WaitForChild('ServerRole'))
local rng=Random.new()

local warned=false
local function ready()
 local folder=H.templates(combat)
 if not folder and not warned then
  warned=true
  warn('HandymanTurretService: RogueliteCombat.HandymanTurrets (T1-T4) is missing, so turrets stay off until InstallHandymanTurret runs (HANDYMAN_TURRET.md)')
 end
 return folder~=nil
end

-- Ray filters: every body, the weapon showcases and the map's spawn marker (as RogueliteCombat's),
-- plus the enemies for line-of-sight checks. Rebuilt at most every 0.5 s (enemies every 0.1 s when
-- they changed), not per projectile step.
local SHOWCASES={'RogueliteWeaponShowcase','RogueliteWeaponShowcase_PlaySize'}
local enemyVersion=0
Tags:GetInstanceAddedSignal('RogueliteZombie'):Connect(function() enemyVersion+=1 end)
Tags:GetInstanceRemovedSignal('RogueliteZombie'):Connect(function() enemyVersion+=1 end)
local worldParams,worldAt,enemyParams,enemyAt,enemySeen=nil,-math.huge,nil,-math.huge,-1
local function rayParams(_,ignoreEnemies)
 local now=os.clock()
 if not worldParams or now-worldAt>.5 then
  local list={}
  for _,p in Players:GetPlayers() do if p.Character then table.insert(list,p.Character) end end
  for _,name in SHOWCASES do local f=workspace:FindFirstChild(name);if f then table.insert(list,f) end end
  local marker=Role.marker();if marker then table.insert(list,marker) end
  local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances=list
  worldParams,worldAt,enemyParams=p,now,nil
 end
 if not ignoreEnemies then return worldParams end
 if not enemyParams or (enemySeen~=enemyVersion and now-enemyAt>.1) then
  local list=worldParams.FilterDescendantsInstances
  for _,npc in Tags:GetTagged('RogueliteZombie') do table.insert(list,npc) end
  local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances=list
  enemyParams,enemyAt,enemySeen=p,now,enemyVersion
 end
 return enemyParams
end

-- Nails: the normal swept projectiles and damage path, under id 'Turret'.
local nails=require(SSS:WaitForChild('StatProjectiles')).new(combat,function(npc,amount,d) return Effects.hit(npc,amount,d) end,rayParams,2^30)

-- Where a turret's head and muzzles are, from its tier's template: the head pivot in the model's
-- space, and each Barrel attachment Muzzle1..n from the head pivot (the head at rest faces -Z).
local geometryCache={}
local function geometry(tier)
 local folder=H.templates(combat);local m=folder and folder:FindFirstChild('T'..tier)
 local cached=geometryCache[tier]
 if cached and cached.model==m then return cached end
 local g={model=m,head=Vector3.new(0,2.2,0),muzzles={Vector3.new(0,.2,-1.2)}}
 if m then
  local pivot=m:GetPivot();local head,barrel=m:FindFirstChild('Head'),m:FindFirstChild('Barrel')
  local headPivot=head:GetPivot()
  g.head=pivot:PointToObjectSpace(headPivot.Position)
  local list={}
  -- Tier IV's six barrels spin, so it fires from their centre (Barrel MuzzleCentre, in its frame).
  local centre=barrel:GetAttribute('MuzzleCentre')
  if m:GetAttribute('Spin')==true and typeof(centre)=='Vector3' then
   list[1]=headPivot:PointToObjectSpace(barrel:GetPivot():PointToWorldSpace(centre))
  else
   for i=1,12 do
    local a=barrel:FindFirstChild('Muzzle'..i)
    if not (a and a:IsA('Attachment')) then break end
    table.insert(list,headPivot:PointToObjectSpace(a.WorldPosition))
   end
  end
  if #list>0 then g.muzzles=list end
 end
 geometryCache[tier]=g
 return g
end

-- Enemies -----------------------------------------------------------------------------------
local function shelled(npc) return npc:GetAttribute('IsMapBoss')==true or npc:GetAttribute('IsHammerBoss')==true end
-- A boss is measured to its nearest body box (it is far wider than its root), as weapons do.
local function reachPoint(e,from)
 if not e.boss then return e.position end
 local best,bestDistance=e.position,(e.position-from).Magnitude
 for _,p in e.npc:GetChildren() do
  -- Not the Hammer's hammer nor the hands holding it (e.hammer: the old Hammer or the map-boss one,
  -- R9, the same template): RogueliteCombat.server reachPoint.
  if p:IsA('MeshPart') and not (e.hammer and (p.Name=='Hammer' or p.Name=='LeftHand' or p.Name=='RightHand')) then
   local l=p.CFrame:PointToObjectSpace(from);local h=p.Size*.5
   local q=p.CFrame:PointToWorldSpace(Vector3.new(math.clamp(l.X,-h.X,h.X),math.clamp(l.Y,-h.Y,h.Y),math.clamp(l.Z,-h.Z,h.Z)))
   local distance=(q-from).Magnitude
   if distance<bestDistance then best,bestDistance=q,distance end
  end
 end
 return best
end
-- One snapshot per tick for every turret (TargetGrid), only when a turret is shooting.
local function snapshot()
 local list={}
 for _,npc in Tags:GetTagged('RogueliteZombie') do
  local hum=npc:FindFirstChildOfClass('Humanoid');local root=npc:FindFirstChild('HumanoidRootPart')
  if hum and root and hum.Health>0 and npc:IsDescendantOf(workspace) then
   table.insert(list,{npc=npc,hum=hum,root=root,position=root.Position,boss=shelled(npc),hammer=npc:GetAttribute('IsHammerBoss')==true or npc:GetAttribute('MapBossId')=='Hammer',dummy=npc:GetAttribute('LobbyDummy'),practice=Death.isPractice(npc)})
  end
 end
 return Grid.new(list)
end
local function fresh(e) return e.hum.Health>0 and e.npc.Parent~=nil and e.root.Parent~=nil end

-- Turrets --------------------------------------------------------------------------------------
-- player -> list of turrets {folder, index, tier, temp, position, yaw, facing, head, nextShot,
-- pickedAt, shots, aimSent, aimAt, seenTarget, packAt, readyAt, movedAt, range}.
local turrets={}
local motion={} -- player -> {at, clock, velocity}: their flat run, for follow spots
local placedAt={} -- player -> the wave key their turrets were last placed for
local suppressed={} -- player -> wave key: ADMIN Clear, nothing comes back until the next wave
local scrap={} -- player -> {key, crystals, built}: Scrap Magnet's count this wave
local defs={} -- player -> {stats, character, [tier] = definition}
local holder
local function folder()
 if holder and holder.Parent==workspace then return holder end
 holder=workspace:FindFirstChild('RogueliteTurrets')
 if not holder then holder=Instance.new('Folder');holder.Name='RogueliteTurrets';holder.Parent=workspace end
 return holder
end
-- The run, wave and phase a placement belongs to: a new wave (or the sandbox turning into waves)
-- places everything again.
local function waveKey() return Shop.runId..':'..Shop.wave..':'..Shop.phase end
local function total() local n=0;for _,list in turrets do n+=#list end;return n end
local function remove(list,i) local t=table.remove(list,i);if t then t.folder:Destroy() end end
local function despawn(p)
 local list=turrets[p];if not list then return end
 turrets[p]=nil
 for _,t in list do t.folder:Destroy() end
end
local function bodyOf(p)
 local c=p.Character;local h=c and c:FindFirstChildOfClass('Humanoid');local r=c and c:FindFirstChild('HumanoidRootPart')
 if h and r and h.Health>0 then return c,r,h end
end
-- Keeps turrets: in the run and out of the lobby, any class (items, not the class, give turrets).
local function keeps(p)
 return Shop.states[p]~=nil and Characters.states[p]~=nil and Shop.members[p]~=nil and p:GetAttribute('LobbyPreviewActive')~=true
end
local function lookOf(root)
 local look=Vector3.new(root.CFrame.LookVector.X,0,root.CFrame.LookVector.Z)
 return look.Magnitude>.01 and look.Unit or Vector3.new(0,0,-1)
end
-- The floor under the player: 2 = the normalized R15 HipHeight, plus half the root (this sandboxed
-- script may not read a player's HipHeight: no AvatarAppearance capability).
local function footOf(root) return root.Position-Vector3.yAxis*(2+root.Size.Y*.5) end
-- HandymanTurret.spot's probe: the ground under a ring spot, or nil. Solid, fairly flat floor
-- within 4 studs of the player's feet (no cliff tops, canopies or pits), inside the arena circle
-- (the spawn marker's SpawnAreaCenter / SpawnAreaRadius, as the spawner uses), with a clear line
-- from the player (no turret behind a wall or the arena's invisible boundary). Two rays a try.
local function prober(root)
 local params=rayParams(nil,true)
 local m=Role.marker()
 local center=m and m:GetAttribute('SpawnAreaCenter');if m and typeof(center)~='Vector3' then center=m.Position end
 local radius=m and (m:GetAttribute('SpawnAreaRadius') or 60)
 local anchor=H.anchor(footOf(root),center,radius)
 local floorY=center and center.Y or anchor.Y
 local from=Vector3.new(anchor.X,floorY+4,anchor.Z)
 return function(point)
  if center and Vector2.new(point.X-center.X,point.Z-center.Z).Magnitude>math.max(0,radius-8) then return nil end
  local at=Vector3.new(point.X,from.Y,point.Z)
  if (at-from).Magnitude>.05 and workspace:Raycast(from,at-from,params) then return nil end
  local hit=workspace:Raycast(at+Vector3.yAxis*24,-Vector3.yAxis*64,params)
  if not hit or hit.Normal.Y<.7 or math.abs(hit.Position.Y-floorY)>8 then return nil end
  return hit.Position
 end,anchor
end
local function newTurret(p,index,temp)
 local f=Instance.new('Folder');f.Name=p.UserId..'_'..index;f:SetAttribute('OwnerUserId',p.UserId);f:SetAttribute('Index',index)
 return {folder=f,index=index,temp=temp or nil,shots=0,nextShot=0}
end
-- Turret t stands at `position` facing `look` as `tier`; clients pop it in at BuiltAt (set last).
local function stand(t,position,look,tier)
 t.tier=tier;t.position=position;t.yaw=H.yaw(look);t.facing=look;t.runId=Shop.runId
 t.head=CFrame.new(position)*CFrame.Angles(0,t.yaw,0)*geometry(tier).head
 t.nextShot=os.clock()+.35 -- the build pop, then it opens fire
 t.aimSent=nil;t.seenTarget=nil;t.pickedAt=nil
 t.packAt=nil;t.readyAt=nil;t.movedAt=os.clock() -- every placement starts the follow cooldown
 local f=t.folder
 f:SetAttribute('Tier',tier);f:SetAttribute('Position',position);f:SetAttribute('Yaw',t.yaw)
 f:SetAttribute('Temp',t.temp);f:SetAttribute('Aim',nil);f:SetAttribute('PackAt',nil)
 f:SetAttribute('BuiltAt',workspace:GetServerTimeNow())
 if not f.Parent then f.Parent=folder() end -- parented last, so clients get it whole
end
-- Wave start: every turret the player's items give (best first), up to `allowed` (their share of
-- the server's 30), on a fresh ring around them. Last wave's temporary ones go; Folders are kept by
-- Index, so a client only re-poses and re-tiers them.
local function place(p,allowed)
 local s=Shop.states[p];local cs=Characters.states[p];local _,root=bodyOf(p)
 local tiers=H.tiers(s and s.items)
 while #tiers>allowed do table.remove(tiers) end
 local list=turrets[p] or {};turrets[p]=list
 local byIndex={}
 for _,t in list do if t.temp or t.index>#tiers or not root then t.folder:Destroy() else byIndex[t.index]=t end end
 table.clear(list)
 if not root or #tiers==0 then return end
 local look=lookOf(root);local probe,foot=prober(root)
 local spots=H.ring(#tiers,H.band(cs and cs.class),rng,H.angle(look))
 for i,tier in tiers do
  local at=H.spot(foot,spots[i].angle,spots[i].radius,probe)
  if at then
   local t=byIndex[i] or newTurret(p,i,false);table.insert(list,t);stand(t,at,look,tier)
  elseif byIndex[i] then byIndex[i].folder:Destroy() end
 end
end
-- Free ground spots for n turrets on a ring around where the player is now, at least SPACING from
-- the turrets standing; with no free spot left they take the ring's spots anyway (a second pass).
-- Returns the points and the facing. A follow move (mover: the turret moving, heading/speed: his
-- run) uses HandymanTurret.followRing around HandymanTurret.followCenter, so it lands ahead of him,
-- and ignores its own old spot and turrets packing up. One move: usually 1 spot, 3 points, 2 rays.
local function free(p,root,n,mover,heading,speed)
 local list=turrets[p] or {}
 local cs=Characters.states[p]
 local look=heading or lookOf(root);local probe,foot=prober(root)
 local band=H.band(cs and cs.class)
 local spots,centre
 if mover then spots=H.followRing(#list,band,rng,H.angle(look));centre=H.followCenter(foot,look,speed)
 else spots=H.ring(#list+n,band,rng,H.angle(look));centre=foot end
 local taken={};for _,t in list do if t~=mover and not t.packAt then table.insert(taken,t.position) end end
 local points,pass={},1
 while #points<n and pass<=2 do
  for _,spot in spots do
   if #points>=n then break end
   local at=H.spot(centre,spot.angle,spot.radius,probe)
   if not at then continue end
   local clear=pass==2
   if not clear then clear=true;for _,q in taken do if Vector2.new(at.X-q.X,at.Z-q.Z).Magnitude<H.SPACING then clear=false;break end end end
   if clear then table.insert(points,at);table.insert(taken,at) end
  end
  pass+=1
 end
 return points,look
end
-- Mid-wave additions (admin Give, Scrap Magnet): new turrets of these tiers at free spots.
local function add(p,root,tiers,temp)
 local list=turrets[p] or {};turrets[p]=list
 local points,look=free(p,root,#tiers)
 local index=temp and H.MAX_OWNED or 0
 for _,t in list do if (t.temp==true)==(temp==true) then index=math.max(index,t.index) end end
 for k,at in points do
  index+=1;local t=newTurret(p,index,temp);table.insert(list,t)
  stand(t,at,look,tiers[k])
 end
 return #points
end
-- Follow: start packing (no fire, the head idles; clients fold it into the ground).
local function pack(t,clock)
 t.packAt=clock;t.readyAt=nil;t.nextShot=math.max(t.nextShot,clock)
 t.aimSent=nil;t.folder:SetAttribute('Aim',nil)
 t.folder:SetAttribute('PackAt',workspace:GetServerTimeNow())
end
-- Follow: stand again at a free spot ahead of the player (root nil, or no ground found: where it
-- was), same Folder and Index, then BUILD_TIME before it fires.
local function rebuild(p,root,t,clock)
 t.packAt=nil
 local at,look=nil,t.facing
 if root then
  local m=motion[p];local v=m and m.velocity or Vector3.zero
  local heading=v.Magnitude>3 and v.Unit or lookOf(root)
  local points;points,look=free(p,root,1,t,heading,v.Magnitude)
  at=points[1]
 end
 stand(t,at or t.position,look or t.facing,t.tier)
 t.nextShot=clock+H.BUILD_TIME;t.readyAt=clock+H.BUILD_TIME;t.movedAt=clock
end
-- Mid-wave item changes (ADMIN Give or Clear): turrets for new items now, extra ones gone. Nothing
-- while the server is at its 30. Cheap when nothing changed (the usual case).
local function sync(p,root)
 local s=Shop.states[p];local list=turrets[p] or {}
 local want=H.tiers(s.items)
 local have={};for _,t in list do if not t.temp then table.insert(have,t) end end
 if #have==#want then return end
 if #have>#want then
  for i=#list,1,-1 do if not list[i].temp and list[i].index>#want then remove(list,i) end end
  return
 end
 local count={};for _,t in have do count[t.tier]=(count[t.tier] or 0)+1 end
 local missing={};for _,tier in want do if (count[tier] or 0)>0 then count[tier]-=1 else table.insert(missing,tier) end end
 local room=H.MAX_SERVER-total()
 while #missing>room do table.remove(missing) end
 if #missing>0 then add(p,root,missing,false) end
end
-- Scrap Magnet (HandymanTurret.scrapBuilds): ShopService's onShards listener only records the
-- crystals (it runs in the shop's thread); the build happens here.
Shop.onShards=function(p,collected,crystals)
 local key=waveKey();local c=scrap[p]
 if not c or c.key~=key then c={key=key,crystals=0,built=0};scrap[p]=c end
 c.crystals+=tonumber(crystals) or tonumber(collected) or 0 -- an older ShopService sends no crystals
end
local function magnet(p,root)
 local s=Shop.states[p];local copies=H.count(s.items,H.SCRAP_MAGNET)
 local c=scrap[p]
 if copies<=0 or not c or c.key~=waveKey() or Shop.phase~='Combat' then return end
 local n=math.min(H.scrapBuilds(c.crystals,copies,c.built),H.MAX_SERVER-total())
 if n<=0 then return end
 local tiers={};for i=1,n do tiers[i]=1 end
 c.built+=add(p,root,tiers,true)
end

-- Aim replicates for the head's turn only: written when it moves 1.5+ studs (at most 5 times a
-- second) or drifts .25+ studs for .5 s, cleared after AIM_IDLE without a target. Each nail's own
-- Shot row turns the head exactly when it fires.
local function aimAt(t,aim,now)
 local sent=t.aimSent
 if aim==nil then if sent~=nil then t.aimSent=nil;t.folder:SetAttribute('Aim',nil) end;return end
 local moved=sent and (aim-sent).Magnitude or math.huge;local age=now-(t.aimAt or -1e6)
 if sent==nil or moved>1.5 and age>=.2 or moved>.25 and age>=.5 then t.aimSent=aim;t.aimAt=now;t.folder:SetAttribute('Aim',aim) end
end
-- The owner's turret definition per tier (HandymanTurret.weapon: Brotato's rule), rebuilt when
-- their stats table or body changes (CharacterService replaces the stats table on every change).
local function definition(p,tier,cs,character)
 local c=defs[p]
 if not c or c.stats~=cs.stats or c.character~=character then c={stats=cs.stats,character=character};defs[p]=c end
 local d=c[tier]
 if not d then d=H.weapon(tier,cs.stats);d.owner=p;d.character=character;c[tier]=d end
 return d
end
-- One nail (plus any Extra projectiles, 5 degrees apart like the guns) from the next muzzle at e.
local function fire(t,d,e,point,character)
 local interval,damage,burst=H.cadence(d)
 local g=geometry(t.tier)
 local flat=Vector3.new(point.X-t.head.X,0,point.Z-t.head.Z)
 local look=flat.Magnitude>.05 and flat.Unit or t.facing
 local headCF=CFrame.lookAt(t.head,t.head+look)
 t.shots+=1
 local muzzle=headCF:PointToWorldSpace(g.muzzles[(t.shots-1)%#g.muzzles+1])
 if workspace:Raycast(t.head,muzzle-t.head,rayParams(nil,false)) then muzzle=t.head end -- a muzzle poking into a wall fires from the head
 local shot=table.clone(d);shot.damage=damage;shot.arcTarget=e.root;shot.practiceTarget=e.practice
 shot.slotIndex=100+t.index -- which turret fired (HandymanTurret.client); never a weapon slot
 local aim=e.boss and point or Targets.predict(e.root,muzzle,function(distance) return distance/shot.projectileSpeed end,0,shot.range,rayParams,character)
 local direction=aim-muzzle
 if direction.Magnitude<.05 then direction=look end
 direction=direction.Unit
 local jitter=burst>1 and math.rad(rng:NextNumber(-H.GATLING_SPREAD,H.GATLING_SPREAD)) or 0
 -- Extra projectiles through the shared rule (CharacterStats.usesStat): the turret is a bullet
 -- weapon like the Nail Gun, so Two Straws adds a nail, and Pierce/Bounce apply (StatProjectiles).
 local count=1+Stats.shotStat(shot,'ProjectileCount')
 for i=1,count do
  local angle=math.rad((i-(count+1)/2)*5)+jitter
  nails:launch(shot,muzzle,muzzle+CFrame.Angles(0,angle,0):VectorToWorldSpace(direction)*shot.range)
 end
 return interval
end
-- Follow, once a tick in a wave (not paused): track his flat run, stand finished packs, and pack
-- the ones left behind past their range (HandymanTurret.leftBehind: 2 moving at once, 1.5 s apart).
local function follow(p,root,list,cs,character,clock)
 local m=motion[p];local at=root.Position
 if m and clock-m.clock<.5 and clock>m.clock then
  local v=Vector3.new(at.X-m.at.X,0,at.Z-m.at.Z)/(clock-m.clock)
  m.velocity=m.velocity:Lerp(v,.5);m.at=at;m.clock=clock
 else motion[p]={at=at,clock=clock,velocity=Vector3.zero} end
 for _,t in list do if t.packAt and clock-t.packAt>=H.PACK_TIME then rebuild(p,root,t,clock) end end
 for _,t in list do t.range=definition(p,t.tier,cs,character).range end
 for _,t in H.leftBehind(list,at,clock) do pack(t,clock) end
end

-- The 10 Hz loop -------------------------------------------------------------------------------
local TICK=.1
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<TICK then return end;elapsed=0
 if not ready() then for p in turrets do despawn(p) end;return end
 local clock=os.clock();local now=workspace:GetServerTimeNow()
 local paused=combat:GetAttribute('RunPaused')==true
 local phase=Shop.phase
 local wave=phase=='Combat' or phase=='Practice'
 local fighting=wave and combat:GetAttribute('ZombiesEnabled')==true and not paused
  and (combat:GetAttribute('CinematicUntil') or 0)<=now -- a boss entrance (BossService.INTRO)
 local zombies=combat:GetAttribute('ZombiesEnabled')==true
 local key=waveKey()
 -- Gone with the run: out of it, in the lobby, or a new run (Shop.runId).
 for p,list in turrets do if not keeps(p) or (list[1] and list[1].runId~=Shop.runId) then despawn(p) end end
 -- Wave start: every due player's turrets are placed in the same tick, so the server's 30 is shared
 -- fairly between them (HandymanTurret.share); someone arriving later gets what is left.
 if wave and not paused then
  local due,others={},0
  for p in Shop.states do
   if keeps(p) and placedAt[p]~=key and bodyOf(p) then table.insert(due,p) elseif turrets[p] then others+=#turrets[p] end
  end
  if #due>0 then
   local wants={};for i,p in due do wants[i]=#H.tiers(Shop.states[p].items) end
   local shares=H.share(wants,H.MAX_SERVER-others)
   for i,p in due do placedAt[p]=key;place(p,shares[i]) end
  end
 end
 local snap,wall
 local can=function(e) if e.dummy then return false end;return zombies or e.practice end
 for p in Shop.states do
  if not keeps(p) then continue end
  local cs=Characters.states[p];local character,root=bodyOf(p)
  local list=turrets[p]
  -- Another arena (500+ studs from their turrets): placed around them again below.
  if list and root and list[1] and (root.Position-list[1].position).Magnitude>500 then despawn(p);list=nil end
  if not wave then
   -- Between waves: Scrap Magnet's turrets go, the rest hold fire (the head idles; a pause keeps it).
   -- Nothing follows; one caught packing as the wave ended stands up near him (or where it was).
   if list then
    for i=#list,1,-1 do if list[i].temp then remove(list,i) end end
    for _,t in list do if t.packAt then rebuild(p,root,t,clock) end end
    for _,t in list do t.nextShot=math.max(t.nextShot,clock);if not paused and clock-(t.seenTarget or -1e6)>H.AIM_IDLE then aimAt(t,nil,clock) end end
   end
   continue
  end
  if root and not paused and placedAt[p]==key and suppressed[p]~=key then sync(p,root);magnet(p,root) end
  list=turrets[p];if not list or #list==0 then continue end
  if root and not paused and placedAt[p]==key and H.follows(cs and cs.class) then follow(p,root,list,cs,character,clock) end
  local enabled=cs.folder and cs.folder:GetAttribute('WeaponEnabled')~=false
  local active=fighting and character~=nil and enabled and p:GetAttribute('RunDown')==nil and not Characters.frozen(p)
  for _,t in list do
   if t.packAt then t.nextShot=math.max(t.nextShot,clock);continue end -- folding up to follow: no fire
   if not active then
    t.nextShot=math.max(t.nextShot,clock) -- no banked shots after a hold
    if not paused and clock-(t.seenTarget or -1e6)>H.AIM_IDLE then aimAt(t,nil,clock) end
    continue
   end
   -- A target pick when a nail is due this tick, else every 0.3 s for the head's aim.
   local due=clock>=t.nextShot-TICK
   if not due and clock-(t.pickedAt or -1e6)<.3 then continue end
   t.pickedAt=clock
   local d=definition(p,t.tier,cs,character)
   snap=snap or snapshot();wall=wall or rayParams(nil,true)
   local e,point=Grid.nearest(snap,t.head,d.range,can,function(e) return reachPoint(e,t.head) end,function(at,e) return fresh(e) and workspace:Raycast(t.head,at-t.head,wall)==nil end)
   if not e then
    t.nextShot=math.max(t.nextShot,clock)
    if clock-(t.seenTarget or -1e6)>H.AIM_IDLE then aimAt(t,nil,clock) end
    continue
   end
   t.seenTarget=clock
   aimAt(t,point,clock)
   -- Shots due by now, on the turret's own clock (two at most per tick), so its average rate is
   -- exact at 10 Hz: Tier IV's 0.187 s nails come one or two a tick.
   local fired=0
   while clock>=t.nextShot and fired<2 and fresh(e) do
    t.nextShot+=fire(t,d,e,point,character);fired+=1
   end
   if clock-t.nextShot>.5 then t.nextShot=clock end
  end
 end
end)

-- ADMIN panel (AdminService action Turret, ADMIN_PANEL.md). AdminService already checked the
-- developer and the arguments, and marked the run a test run.
--   Give n: one more Nail Turret / Twin Nailer / Quad Nailer / Gatling Rig item (n = 1-4) in your
--     run inventory (ShopService.adminItem, so the 10 limit holds); in a wave it stands at once.
--   Clear: your turret items go, and every standing turret now; other players' come back at the
--     next wave.
Shop.turretAdmin=function(p,mode,n)
 if mode=='Clear' then
  local s=Shop.states[p]
  if s then
   for i=#s.items,1,-1 do if H.ItemTier[s.items[i].id] then table.remove(s.items,i) end end
   s.revision+=1;Shop.publish(p,'Turrets cleared')
  end
  local key=waveKey()
  for q in turrets do despawn(q) end
  for q in Shop.states do suppressed[q]=key end
  return true,'Turrets cleared'
 elseif mode=='Give' then
  local it=H.Items[n];if not it then return false,'Unknown turret' end
  if not Shop.states[p] or not Shop.members[p] then return false,'Join the arena first' end
  local ok,message=Shop.adminItem(p,it.id)
  if ok then suppressed[p]=nil end
  if ok and not ready() then message=message..' (turret models are not installed: InstallHandymanTurret)' end
  return ok,message
 end
 return false,'Unknown turret action'
end

Players.PlayerRemoving:Connect(function(p)
 despawn(p);placedAt[p]=nil;suppressed[p]=nil;scrap[p]=nil;defs[p]=nil;motion[p]=nil
end)
