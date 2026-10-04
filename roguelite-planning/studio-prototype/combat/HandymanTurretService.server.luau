-- Handyman turret, server (HANDYMAN_TURRET.md, 2026-10-03). Studio: SSS.HandymanTurretService, a
-- SANDBOXED Script (Capabilities copied from SSS.RogueliteCombat), like PetService. Numbers and
-- rules: RogueliteCombat.HandymanTurret.
--
-- Server authority: who has a turret, where it stands, what it shoots and when are decided here.
-- Its tier is the run's (ShopService state turretTier, bought with the shop's UpgradeTurret).
-- Clients only ask to BUILD (RunAction 'BuildTurret'; RogueliteMeta ignores the action) and draw:
--   workspace.RogueliteTurrets holds one Folder per turret, named by UserId, with OwnerUserId, Tier,
--   Position (the ground point under it), Yaw (its facing), BuiltAt and ReadyAt (server time: last
--   built, BUILD works again), Aim (where its head points; nil when idle) and Admin (a panel turret).
--   HandymanTurret.client draws them. No server parts, so nothing blocks enemies or players, and
--   nothing here writes a CFrame.
-- Life: built next to a Handyman when a wave (or the sandbox) starts and they have none, moved by
-- BUILD, gone when they leave the run (lobby, results, disconnect), the run resets, or they end up
-- 500+ studs away (another arena: the next wave builds one again). It holds fire between waves,
-- while the run is paused, through a boss entrance, while its owner is down or their weapons are off.
-- Health (2026-10-04, user: "lets let mobs destroy it"): each turret has its own hp (Health and
-- MaxHealth on its Folder; HandymanTurret.maxHealth from the wave, its tier and the owner's gear
-- power) and a target table in HandymanTurret.posts. A wave mob whose nearest target it is
-- (RogueliteZombieChase -> HandymanTurret.nearer) walks to it and attacks it; the hit lands on the
-- table's `taken` (EnemyAttacks, ZombieAttacks), which this script takes off every frame with the
-- owner's armour. At 0 it breaks (Broken = server time): no shots, no longer a target, BUILD again
-- after HandymanTurret.rebuildAt (5 s or its own cooldown, the sooner) puts a fresh one at you, and
-- the next wave rebuilds it at you. BUILD on a standing one moves it with its damage; every wave
-- starts it at full health, like players (ShopService refillHealth). No regeneration in a wave.
-- Shots: a 10 Hz target pick through TargetGrid (nearest enemy in range with a clear line from the
-- head), nails are StatProjectiles (their own instance; projectile keys from 2^30 so clients never
-- mix them with weapon bullets) with id 'Turret'. Hits go through CombatEffectsService as the
-- owner's: crits, statuses, kill credit and crystals, contribution, run analytics and the
-- utilityKills quest (RogueliteMeta).
-- Off until RogueliteCombat.HandymanTurrets holds T1-T4 (InstallHandymanTurret): one warning, no
-- turrets, no BUILD, no shop upgrade.
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
  warn('HandymanTurretService: RogueliteCombat.HandymanTurrets (T1-T4) is missing, so Handyman turrets stay off until InstallHandymanTurret runs (HANDYMAN_TURRET.md)')
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
  -- For mobs (2026-10-04): its half-width from the Base part's footprint (T1 2.05 wide -> 1.03,
  -- so its target pad is 0.28) and its middle, a little over half the head height, for their aim.
  local base=m:FindFirstChild('Base')
  if base and base:IsA('BasePart') then
   -- World X and Z extents of the part, whichever way the import turned it.
   local c,s=base.CFrame,base.Size
   local x=math.abs(c.RightVector.X)*s.X+math.abs(c.UpVector.X)*s.Y+math.abs(c.LookVector.X)*s.Z
   local z=math.abs(c.RightVector.Z)*s.X+math.abs(c.UpVector.Z)*s.Y+math.abs(c.LookVector.Z)*s.Z
   g.radius=math.clamp(math.max(x,z)/2,.8,2)
  end
  g.middle=math.clamp(g.head.Y*.55,.8,2.2)
 end
 g.radius=g.radius or 1;g.middle=g.middle or 1.2
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
-- player -> {folder, tier, position, yaw, facing, head (world), readyAt, nextShot, shots, aimSent,
-- aimAt, seenTarget, runId, admin, hp, maxHp, hpWave, broken, brokeWave, post}. Health and the
-- break live on the turret, not the player (several turrets per player later stay possible).
local turrets={}
local adminGiven={} -- player -> runId: an ADMIN panel turret, kept whatever the class this run
local suppressed={} -- player -> 'runId:wave': ADMIN Clear, no wave-start build until then or BUILD
local lastRequest={}
local holder
local function folder()
 if holder and holder.Parent==workspace then return holder end
 holder=workspace:FindFirstChild('RogueliteTurrets')
 if not holder then holder=Instance.new('Folder');holder.Name='RogueliteTurrets';holder.Parent=workspace end
 return holder
end
local function despawn(p)
 local t=turrets[p];if not t then return end
 turrets[p]=nil
 -- No longer a mob target: out of the list, and a mob still holding its table sees it gone.
 local i=table.find(H.posts,t.post);if i then table.remove(H.posts,i) end
 t.post.hp=0;t.post.taken=0;t.post.Parent=nil
 if t.folder then t.folder:Destroy() end
end
-- The run, wave and phase its health belongs to: a new wave (or the sandbox turning into waves)
-- refills it, and rebuilds a broken one.
local function waveKey() return Shop.runId..':'..Shop.wave..':'..Shop.phase end
local function powerOf(p) local cs=Characters.states[p];return cs and cs.stats and cs.stats.GearPower or 1 end
-- Health on the turret and its target table, and Health/MaxHealth on its Folder for the bar
-- (to 0.1, so even a small hit flashes it).
local function setHealth(t,hp,maxHp)
 t.hp,t.maxHp=hp,maxHp;t.post.hp=t.broken and 0 or hp
 local f=t.folder
 f:SetAttribute('MaxHealth',maxHp)
 local shown=math.ceil(hp*10)/10;if f:GetAttribute('Health')~=shown then f:SetAttribute('Health',shown) end
end
local function fullHealth(p,t)
 local maxHp=H.maxHealth(t.tier,Shop.wave,powerOf(p))
 t.hpWave=waveKey();setHealth(t,maxHp,maxHp)
end
-- A new tier mid-life (the shop between waves, or ADMIN Tier): that tier's max, its damage kept.
-- Example, wave 5: Tier I at 70 / 120 -> Tier II at 130 / 180.
local function retier(p,t)
 local maxHp=H.maxHealth(t.tier,Shop.wave,powerOf(p))
 setHealth(t,t.broken and 0 or math.max(1,maxHp-(t.maxHp-t.hp)),maxHp)
end
-- 0 HP: it stops, is no target, and BUILD works again at H.rebuildAt (the button shows BROKEN and
-- the seconds). Clients hide it with a flat burst and a crunch (Broken = server time).
local function breakTurret(p,t)
 local now=workspace:GetServerTimeNow()
 t.broken=now;t.brokeWave=waveKey();t.post.taken=0
 setHealth(t,0,t.maxHp)
 t.readyAt=H.rebuildAt(now,t.readyAt);t.aimSent=nil;t.seenTarget=nil
 local f=t.folder
 f:SetAttribute('ReadyAt',t.readyAt);f:SetAttribute('Aim',nil);f:SetAttribute('Broken',now)
end
-- Mobs' hits queued on its target table come off here, through the owner's armour. Nothing lands
-- between waves or while the run is held, as for players (CharacterService.contact).
local function takeHits(p,t,held)
 local post=t.post;local amount=post.taken;post.taken=0
 if t.broken or held or amount<=0 then return end
 local cs=Characters.states[p]
 local left,broke=H.takeHit(t.hp,amount,cs and cs.stats)
 setHealth(t,left,t.maxHp)
 if broke then breakTurret(p,t) end
end
local function tierOf(p) local s=Shop.states[p];return H.tier(s and s.turretTier or 1) end
local function bodyOf(p)
 local c=p.Character;local h=c and c:FindFirstChildOfClass('Humanoid');local r=c and c:FindFirstChild('HumanoidRootPart')
 if h and r and h.Health>0 then return c,r,h end
end
local function isAdmin(p) return adminGiven[p]~=nil and adminGiven[p]==Shop.runId end
-- Keeps a turret: in the run, out of the lobby, a Handyman (or an ADMIN turret), this run.
local function keeps(p,t)
 local cs=Characters.states[p]
 if not Shop.states[p] or not cs or not Shop.members[p] or p:GetAttribute('LobbyPreviewActive')==true then return false end
 if t and t.runId~=Shop.runId then return false end
 return cs.class==H.Class or isAdmin(p)
end
local function context(p)
 local cs=Characters.states[p];local t=turrets[p]
 return {ready=ready(),class=cs and cs.class,admin=isAdmin(p),member=Shop.members[p]~=nil,lobby=p:GetAttribute('LobbyPreviewActive')==true,
  alive=bodyOf(p)~=nil,down=p:GetAttribute('RunDown')~=nil,phase=Shop.phase,paused=combat:GetAttribute('RunPaused')==true,
  frozen=Characters.frozen(p),now=workspace:GetServerTimeNow(),readyAt=t and t.readyAt or 0}
end
-- Puts the turret BUILD_AHEAD studs in front of the player (short of a wall), on the ground under
-- that spot, facing where they face. manual: BUILD (starts the cooldown); else the wave-start build.
local function build(p,manual)
 local character,root,hum=bodyOf(p)
 if not character then return false,'Respawn first' end
 local look=Vector3.new(root.CFrame.LookVector.X,0,root.CFrame.LookVector.Z)
 look=look.Magnitude>.01 and look.Unit or Vector3.new(0,0,-1)
 local params=rayParams(nil,true)
 local from=root.Position
 local spot=from+look*H.BUILD_AHEAD
 local wall=workspace:Raycast(from,spot-from,params)
 if wall then spot=from+look*math.max(0,(wall.Position-from).Magnitude-1.5) end
 local ground=workspace:Raycast(spot+Vector3.yAxis*3,-Vector3.yAxis*40,params)
 -- 2 = the normalized R15 HipHeight; this sandboxed script may not read a player's (AvatarAppearance).
 local position=ground and ground.Position or spot-Vector3.yAxis*(2+root.Size.Y*.5)
 local tier=tierOf(p)
 local t=turrets[p];local new=t==nil
 if new then
  local f=Instance.new('Folder');f.Name=tostring(p.UserId);f:SetAttribute('OwnerUserId',p.UserId)
  t={folder=f,shots=0,nextShot=0,readyAt=0,hp=0,maxHp=0,post=H.newPost(f)};turrets[p]=t
  table.insert(H.posts,t.post)
 end
 local now=workspace:GetServerTimeNow()
 -- A new, broken or ADMIN-given turret is fresh at full health; BUILD moving a standing one keeps
 -- its damage (moving isn't a repair).
 local fresh=new or t.broken~=nil or not manual
 local oldTier=t.tier
 t.tier=tier;t.position=position;t.yaw=H.yaw(look);t.facing=look;t.runId=Shop.runId;t.admin=isAdmin(p)
 local g=geometry(tier)
 t.head=CFrame.new(position)*CFrame.Angles(0,t.yaw,0)*g.head
 t.post.Position=position+Vector3.yAxis*g.middle;t.post.pad=g.radius-H.BODY;t.post.taken=0
 t.readyAt=manual and now+H.BUILD_COOLDOWN or now
 t.nextShot=os.clock()+.35 -- the build pop, then it opens fire
 t.aimSent=nil;t.seenTarget=nil
 local f=t.folder
 -- Broken goes before BuiltAt, so a client never pops in a turret it still thinks is broken.
 t.broken=nil;f:SetAttribute('Broken',nil)
 if fresh then fullHealth(p,t) elseif oldTier~=tier then retier(p,t) end
 f:SetAttribute('Tier',tier);f:SetAttribute('Position',position);f:SetAttribute('Yaw',t.yaw)
 f:SetAttribute('ReadyAt',t.readyAt);f:SetAttribute('Admin',t.admin or nil);f:SetAttribute('Aim',nil)
 f:SetAttribute('BuiltAt',now)
 if new then f.Parent=folder() end -- parented last, so clients get it whole
 return true
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
-- The owner's turret definition, rebuilt when its tier, stats table, class or body changes
-- (CharacterService replaces the stats table on every change).
local function definition(p,t,cs,character)
 local c=t.cached
 if not c or c.tier~=t.tier or c.stats~=cs.stats or c.class~=cs.class or c.character~=character then
  local d=H.weapon(t.tier,cs.stats,cs.class);d.stats=cs.stats;d.owner=p;d.character=character
  c={tier=t.tier,stats=cs.stats,class=cs.class,character=character,d=d};t.cached=c
 end
 return c.d
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

-- The 10 Hz loop -------------------------------------------------------------------------------
local TICK=.1
local elapsed=0
local pausedAt -- os.clock() when the run froze (RunPaused): BUILD's cooldown waits it out
RunService.Heartbeat:Connect(function(dt)
 -- Mobs' hits come off every frame, not at 10 Hz, so a break shows the moment it happens.
 local held
 for p,t in turrets do
  if t.post.taken>0 then
   if held==nil then
    held=(Shop.phase~='Combat' and Shop.phase~='Practice') or combat:GetAttribute('RunPaused')==true
     or (combat:GetAttribute('CinematicUntil') or 0)>workspace:GetServerTimeNow()
   end
   takeHits(p,t,held)
  end
 end
 elapsed+=dt;if elapsed<TICK then return end;elapsed=0
 if not ready() then for p in turrets do despawn(p) end;return end
 local clock=os.clock();local now=workspace:GetServerTimeNow()
 local paused=combat:GetAttribute('RunPaused')==true
 if paused then pausedAt=pausedAt or clock
 elseif pausedAt then
  local by=clock-pausedAt;pausedAt=nil
  for _,t in turrets do t.readyAt+=by;t.folder:SetAttribute('ReadyAt',t.readyAt) end
 end
 local phase=Shop.phase
 local wave=phase=='Combat' or phase=='Practice'
 local fighting=wave and combat:GetAttribute('ZombiesEnabled')==true and not paused
  and (combat:GetAttribute('CinematicUntil') or 0)<=now -- a boss entrance (BossService.INTRO)
 local zombies=combat:GetAttribute('ZombiesEnabled')==true
 local snap
 for p in turrets do if not Shop.states[p] then despawn(p) end end
 for p in Shop.states do
  local t=turrets[p]
  if not keeps(p,t) then despawn(p);continue end
  local character,root=bodyOf(p)
  if t and root and (root.Position-t.position).Magnitude>500 then despawn(p);t=nil end -- another arena
  if not t then
   -- The wave-start build: a Handyman in a wave (or the sandbox) without one gets it next to them.
   if wave and character and p:GetAttribute('RunDown')==nil and not Characters.frozen(p) and suppressed[p]~=Shop.runId..':'..Shop.wave then build(p,false) end
   continue
  end
  local tier=tierOf(p)
  if t.tier~=tier then
   local g=geometry(tier)
   t.tier=tier;t.head=CFrame.new(t.position)*CFrame.Angles(0,t.yaw,0)*g.head
   t.post.Position=t.position+Vector3.yAxis*g.middle;t.post.pad=g.radius-H.BODY
   t.folder:SetAttribute('Tier',tier);retier(p,t)
  end
  if t.broken then
   -- Broken: no shots and no target. The next wave rebuilds it at its owner, as the wave-start
   -- build does; before that, BUILD can (H.rebuildAt).
   if wave and t.brokeWave~=waveKey() and character and p:GetAttribute('RunDown')==nil and not Characters.frozen(p) then build(p,false) end
   continue
  end
  -- Every wave starts it at full health for that wave, like players.
  if wave and t.hpWave~=waveKey() then fullHealth(p,t) end
  local cs=Characters.states[p]
  local enabled=cs and cs.folder and cs.folder:GetAttribute('WeaponEnabled')~=false
  if not (fighting and character and cs and enabled and p:GetAttribute('RunDown')==nil and not Characters.frozen(p)) then
   t.nextShot=math.max(t.nextShot,clock) -- no banked shots after a hold
   -- Between waves the head goes back to idling; a pause keeps it exactly where it was.
   if not paused and clock-(t.seenTarget or -1e6)>H.AIM_IDLE then aimAt(t,nil,clock) end
   continue
  end
  local d=definition(p,t,cs,character)
  snap=snap or snapshot()
  local can=function(e) if e.dummy then return false end;return zombies or e.practice end
  local wall=rayParams(nil,true)
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
   local interval=fire(t,d,e,point,character)
   t.nextShot+=interval;fired+=1
  end
  if clock-t.nextShot>.5 then t.nextShot=clock end
 end
end)

-- BUILD: the player's own request, checked here. A refused one does nothing (the button shows the
-- cooldown from ReadyAt). RogueliteMeta's handler on the same remote ignores this action.
task.spawn(function()
 local remote=combat:WaitForChild('RunAction')
 remote.OnServerEvent:Connect(function(p,action)
  if action~='BuildTurret' then return end
  if os.clock()-(lastRequest[p] or -1e6)<.25 then return end;lastRequest[p]=os.clock()
  if not H.canBuild(context(p)) then return end
  suppressed[p]=nil
  build(p,true)
 end)
end)

-- ADMIN panel (AdminService action Turret, ADMIN_PANEL.md). AdminService already checked the
-- developer and the arguments, and marked the run a test run.
--   Give: build one at you now, whatever your class (kept for this run).
--   Tier n: your turret's tier for this run (1-4).
--   Break: your turret drops to 0 HP now, as if mobs broke it (2026-10-04, to test break/rebuild).
--   Clear: every turret goes; none is rebuilt until the next wave or that player's BUILD.
Shop.turretAdmin=function(p,mode,tier)
 if not ready() then return false,'Turret models are not installed (InstallHandymanTurret)' end
 local s=Shop.states[p]
 if mode=='Clear' then
  for q in turrets do despawn(q) end
  for q in Shop.states do suppressed[q]=Shop.runId..':'..Shop.wave end
  table.clear(adminGiven)
  return true,'Turrets cleared'
 end
 if not s or not Shop.members[p] then return false,'Join the arena first' end
 if mode=='Tier' then
  s.turretTier=H.tier(tier);Shop.publish(p)
  return true,'Turret Tier '..({'I','II','III','IV'})[s.turretTier]
 elseif mode=='Give' then
  adminGiven[p]=Shop.runId;suppressed[p]=nil
  local ok,why=build(p,false)
  return ok,ok and 'Turret built' or why
 elseif mode=='Break' then
  local t=turrets[p]
  if not t or t.broken then return false,'You have no standing turret' end
  breakTurret(p,t)
  return true,'Turret broken: BUILD in '..math.ceil(math.max(0,t.readyAt-workspace:GetServerTimeNow()))..' s'
 end
 return false,'Unknown turret action'
end

Players.PlayerRemoving:Connect(function(p)
 despawn(p);adminGiven[p]=nil;suppressed[p]=nil;lastRequest[p]=nil
end)
