local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local Motion=require(combat:WaitForChild('WeaponMotion'))
local templates=combat:WaitForChild('WeaponTemplates')
local Chains=require(combat:WaitForChild('ChainWeaponMotion'))
local chainRigs={}
for _,id in {'02','04','25'} do chainRigs[id]=Chains.bind(templates:WaitForChild(id),id) end
local Death=require(combat:WaitForChild('ZombieDeath'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local Targets=require(combat:WaitForChild('ProjectileTarget'))
local Characters=require(script.Parent:WaitForChild('CharacterService'))
local Effects=require(script.Parent:WaitForChild('CombatEffectsService'))
local states={}
local Shop=require(script.Parent:WaitForChild('ShopService'))
local Role=require(script.Parent:WaitForChild('ServerRole'))
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed, like this script
local Wire=require(combat:WaitForChild('ShotBatch')) -- packs each attack into one attribute
-- Slot 1 holds the loadout starter the lobby validated (RunWeapon); Brawler's signature until one is picked.
-- Each class build opens with its signature weapon. RunSetupRules isn't sandboxed, so this script can't require it.
local function starter(player)
 local id=player:GetAttribute('RunWeapon')
 return type(id)=='string' and Catalog.ById[id] and templates:FindFirstChild(id) and id or Stats.Classes.Brawler.build[1]
end
-- What clients draw a weapon from (P3). Each attack is one packed 'Attack' attribute (Wire.packAttack;
-- it was 12 attributes), cleared on reset. AimPosition only turns an idle gun toward its target, so
-- it no longer follows the target at 30 Hz: it is written when the aim moves 1.5+ studs (at most 10
-- times a second), drifts .25+ studs for .3 s, appears or clears, and when the weapon fires; melee
-- slots don't need it. Clients glide between writes. Example: 4 players with 3 guns and 3 swords
-- each, all tracking walking enemies: ~720 writes a second before, ~120 now.
local function aimAt(slot,aim,now,firing)
 local sent=slot.aimSent
 if aim==nil then
  if sent~=nil then slot.aimSent=nil;slot.folder:SetAttribute('AimPosition',nil) end
  return
 end
 local moved=sent and (aim-sent).Magnitude or math.huge;local age=now-(slot.aimAt or -1e6)
 if sent==nil or moved>1.5 and age>=.1 or moved>.25 and age>=.3 or firing and moved>.05 then
  slot.aimSent=aim;slot.aimAt=now;slot.folder:SetAttribute('AimPosition',aim)
 end
end
local function reset(slot,now)
 slot.start=-1e6;slot.ready=now;slot.previous=0;slot.hit={};slot.definition=nil
 slot.lastTarget=nil;slot.aimNpc=nil;slot.nextSearch=nil
 slot.folder:SetAttribute('Attack',nil);slot.aimSent=nil;slot.folder:SetAttribute('AimPosition',nil)
end
local function add(player)
 local f=Instance.new('Folder');f.Name=tostring(player.UserId)
 f:SetAttribute('WeaponEnabled',true);f:SetAttribute('RingRadius',Motion.BaseRadius)
 -- Lobby practice dummies are attacked until the player switches it off (T / ATTACKS).
 f:SetAttribute('LobbyAttacks',true)
 local s={folder=f,slots={},lastOption=-1e6,lastEquip=-1e6,lastLobbyAttacks=-1e6};states[player]=s
 for i=1,Catalog.Slots do
  local child=Instance.new('Folder');child.Name='Slot'..i
  child:SetAttribute('WeaponId',i==1 and starter(player) or '');child:SetAttribute('Index',i);child.Parent=f
  local slot={folder=child,random=Random.new()};s.slots[i]=slot;reset(slot,0)
 end
 f:SetAttribute('EquippedCount',1);f.Parent=combat.PlayerStates
 Characters.attach(player,f)
 Shop.attach(player)
 -- The lobby server sets these only after validating a pick (class unlocked, weapon owned).
 player:GetAttributeChangedSignal('RunClass'):Connect(function() Characters.setClass(player,player:GetAttribute('RunClass')) end)
 player:GetAttributeChangedSignal('RunWeapon'):Connect(function() Shop.setStarter(player,starter(player)) end)
 for _,slot in s.slots do slot.folder:GetAttributeChangedSignal('WeaponId'):Connect(function() reset(slot,workspace:GetServerTimeNow()+.25) end) end
end
Players.PlayerAdded:Connect(add)
for _,p in Players:GetPlayers() do add(p) end
Players.PlayerRemoving:Connect(function(p) local s=states[p];if s then s.folder:Destroy();states[p]=nil end end)
-- Give weapon (ADMIN panel Player tab): developers only, checked by UserId. tier 1-4 (default 1).
combat.EquipWeapon.OnServerEvent:Connect(function(player,index,id,tier)
 local s=states[player]
 if tier==nil then tier=1 end
 if not Admin.isAdmin(player) or not s or not Catalog.validate(index,id) then return end
 if type(tier)~='number' or tier%1~=0 or tier<1 or tier>4 then return end
 local hum=player.Character and player.Character:FindFirstChildOfClass('Humanoid')
 if not hum or hum.Health<=0 then return end
 if id~='' and not templates:FindFirstChild(id) then return end
 if os.clock()-s.lastEquip<.12 then return end;s.lastEquip=os.clock()
 local slot=s.slots[index]
 if slot.folder:GetAttribute('WeaponId')==id and (slot.folder:GetAttribute('Tier') or 1)==tier then return end
 -- Creative copies are free, and never inherit the replaced copy's paid refund.
 slot.folder:SetAttribute('CopyId',game:GetService('HttpService'):GenerateGUID(false))
 slot.folder:SetAttribute('BasePrice',0);slot.folder:SetAttribute('FinalPurchasePrice',0);slot.folder:SetAttribute('PurchasePrice',0)
 slot.folder:SetAttribute('Tier',tier);slot.folder:SetAttribute('WavePurchased',0)
 slot.folder:SetAttribute('WeaponId',id);reset(slot,workspace:GetServerTimeNow()+.25)
 local count=0;for _,v in s.slots do if v.folder:GetAttribute('WeaponId')~='' then count+=1 end end
 s.folder:SetAttribute('EquippedCount',count)
 local shopState=Shop.states[player];if shopState then shopState.ready=false;shopState.revision+=1;Shop.publish(player) end
 Admin.markTestRun()
end)
combat.SetTestOption.OnServerEvent:Connect(function(player,key,value)
 local s=states[player]
 if not RunService:IsStudio() or not s or type(value)~='boolean' or (key~='Zombies' and key~='Katana' and key~='Weapons' and key~='StopWave') then return end
 if os.clock()-s.lastOption<.15 then return end;s.lastOption=os.clock()
 -- Test controls work in Shop/Combat, including after the tester dies.
 if key=='StopWave' then if value then Shop.stopWave() end;return end
 if key=='Zombies' then combat:SetAttribute('ZombiesEnabled',value)
 else s.folder:SetAttribute('WeaponEnabled',value);for _,slot in s.slots do reset(slot,workspace:GetServerTimeNow()+.25) end end
end)
-- Any player may switch their own lobby-dummy attacks. Booleans only, rate limited.
-- It only gates LobbyDummy targets, so arena fights are never affected.
combat.SetLobbyAttacks.OnServerEvent:Connect(function(player,value)
 local s=states[player]
 if not s or type(value)~='boolean' then return end
 if os.clock()-s.lastLobbyAttacks<.25 then return end;s.lastLobbyAttacks=os.clock()
 s.folder:SetAttribute('LobbyAttacks',value)
end)
-- Lobby dummies follow the player's switch; everything else needs a live wave or
-- is a Studio practice target.
local function targetable(npc,s)
 if npc:GetAttribute('LobbyDummy') then return Death.isPractice(npc) and s.folder:GetAttribute('LobbyAttacks')~=false end
 return combat:GetAttribute('ZombiesEnabled') or Death.isPractice(npc)
end
local function alive(npc)
 if not npc:IsDescendantOf(workspace) then return end
 local hum=npc:FindFirstChildOfClass('Humanoid');local root=npc:FindFirstChild('HumanoidRootPart')
 if hum and root and hum.Health>0 then return hum,root end
end
-- Raycast filters are cached and shared: building one (and copying every enemy into it) per call
-- ran per projectile per frame and inside enemy loops. The returned params are read-only; a caller
-- that excludes more copies them (ProjectileTarget.sweepParams, SpecialWeapons' egg chickens).
local SHOWCASES={'RogueliteWeaponShowcase','RogueliteWeaponShowcase_PlaySize'}
local frame,checkedFrame=0,-1
RunService.PreSimulation:Connect(function() frame+=1 end)
local enemyVersion=0
Tags:GetInstanceAddedSignal('RogueliteZombie'):Connect(function() enemyVersion+=1 end)
Tags:GetInstanceRemovedSignal('RogueliteZombie'):Connect(function() enemyVersion+=1 end)
local baseFilter,filters={},{}
-- Characters, showcases and the map marker are compared once a frame; any change drops the cache.
local function refreshBase()
 if checkedFrame==frame then return end;checkedFrame=frame
 local list={}
 for _,p in Players:GetPlayers() do if p.Character then list[#list+1]=p.Character end end
 for _,name in SHOWCASES do local f=workspace:FindFirstChild(name);if f then list[#list+1]=f end end
 local marker=Role.marker();if marker then list[#list+1]=marker end
 local same=#list==#baseFilter
 if same then for i,v in list do if baseFilter[i]~=v then same=false;break end end end
 if not same then baseFilter=list;filters={} end
end
local function rayParams(character,ignoreEnemies)
 refreshBase()
 local entry=filters[character or false];if not entry then entry={};filters[character or false]=entry end
 local slot=ignoreEnemies and 2 or 1
 local p=entry[slot]
 -- A new object on every rebuild, so copies made from the old one can tell it changed.
 if not p or (ignoreEnemies and entry.enemies~=enemyVersion) then
  local filter={character};table.move(baseFilter,1,#baseFilter,#filter+1,filter)
  if ignoreEnemies then for _,npc in Tags:GetTagged('RogueliteZombie') do filter[#filter+1]=npc end;entry.enemies=enemyVersion end
  p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances=filter;entry[slot]=p
 end
 return p
end
local function clear(origin,finish,p) return workspace:Raycast(origin,finish-origin,p)==nil end
-- Where reach is measured to. A boss is far wider than its root box (the dragon's side is ~9
-- studs from its centre, the Hammer Brute's chest and arms 3-5), so it is measured to the nearest
-- point of any body section's box: a pan touching its flank is in range. The Hammer Brute's hammer
-- and the hands holding it are not his body, or reaching the hammer would hit him. Every other
-- enemy is measured to its root, as before.
local HELD={Hammer=true,LeftHand=true,RightHand=true}
local function shelled(npc) return npc:GetAttribute('IsMapBoss')==true or npc:GetAttribute('IsHammerBoss')==true end
-- A boss's body sections in child order, kept until a child is added or removed (or it is
-- destroyed): walking every child per slot per tick and per melee hit was the cost.
local sections={}
local function bodySections(npc,root)
 local c=sections[npc]
 if c and c.root==root then return c.list end
 if c then for _,link in c.links do link:Disconnect() end end
 local list={}
 for _,p in npc:GetChildren() do if p:IsA('MeshPart') or p==root then list[#list+1]=p end end
 c={root=root,list=list,links={}};sections[npc]=c
 local function drop() if sections[npc]==c then sections[npc]=nil end;for _,link in c.links do link:Disconnect() end end
 c.links={npc.ChildAdded:Connect(drop),npc.ChildRemoved:Connect(drop),npc.Destroying:Connect(drop)}
 return list
end
local function reachPoint(npc,root,from)
 if not shelled(npc) then return root.Position end
 local hammer=npc:GetAttribute('IsHammerBoss')==true
 local best,bestDistance=root.Position,(root.Position-from).Magnitude
 for _,p in bodySections(npc,root) do
  -- Parent check: the removal signal is deferred, so a section can leave before the cache drops.
  if p.Parent==npc and not (hammer and HELD[p.Name]) then
   local l=p.CFrame:PointToObjectSpace(from);local h=p.Size*.5
   local q=p.CFrame:PointToWorldSpace(Vector3.new(math.clamp(l.X,-h.X,h.X),math.clamp(l.Y,-h.Y,h.Y),math.clamp(l.Z,-h.Z,h.Z)))
   local distance=(q-from).Magnitude
   if distance<bestDistance then best,bestDistance=q,distance end
  end
 end
 -- Standing inside a section's box: a point just short of the player, so it still counts as a target.
 if bestDistance<.05 then return from+(root.Position-from).Unit*.05 end
 return best
end
-- dot: a zone tick (SpecialWeapons); clients skip its splat and flash (CombatEffectsService).
local function damage(npc,amount,d,secondary,dot) return Effects.hit(npc,amount,d,secondary,dot) end
local rockets=require(combat:WaitForChild('RocketProjectile')).new(combat,damage,rayParams)
local projectiles=require(script.Parent:WaitForChild('StatProjectiles')).new(combat,damage,rayParams)
local arcs=require(script.Parent:WaitForChild('ArcProjectiles')).new(combat,damage,rayParams)
local specials=require(script.Parent:WaitForChild('SpecialWeapons')).new(combat,damage,rayParams)
-- Godly specials (plans/2026-10-01-G): wraiths, tidal wave, storm arrows, dagger chain, healing, bursts.
local godly=require(script.Parent:WaitForChild('GodlyWeapons')).new(damage,function(player,npc)
 local s=states[player];return s~=nil and targetable(npc,s)
end)
specials.hooks.landed=function(d,position,struck) godly:landed(d,position,struck) end
-- Legendary Tier IV moves (WeaponCatalog.Legendary): slashes, the rocket split, the Royal Flush,
-- STRIKE!, the shockwave and Mjolnir's lightning. A do-nothing stand-in if the module is missing.
local legendary=(function()
 local m=script.Parent:FindFirstChild('LegendaryMoves')
 local ok,api=pcall(function() return require(m).new(damage,function(player,npc) local s=states[player];return s~=nil and targetable(npc,s) end,rayParams) end)
 if m and ok then return api end
 if m then warn('LegendaryMoves failed to start:',api) end
 return {swing=function() end,contact=function() end,shoot=function() return false end,impact=function() end}
end)()
specials.hooks.impact=function(d,position,hit) legendary:impact(d,position,hit) end
local function shoot(d,origin,aim,character)
 if godly:handles(d.id) then godly:launch(d,origin,aim,d.arcTarget);return end
 if legendary:shoot(d,origin,aim,character) then return end -- the rocket split or the Royal Flush
 if specials:handles(d.id) then specials:launch(d,origin,aim);return end
 d.muzzleShotId=workspace:GetServerTimeNow() -- One visual flash per trigger, not per pellet.
 if d.id=='18' or d.id=='33' then arcs:launch(d,origin,aim);return end
 local count=(d.projectileCount or (d.kind=='Spread' and 5 or 1))+d.stats.ProjectileCount
 if d.arcTarget then aim=Targets.predict(d.arcTarget,origin,function(distance) return distance/d.projectileSpeed end,0,d.range,rayParams,character) end
 local direction=(aim-origin).Unit
 d.muzzleDirection=direction -- All spread pellets leave the same barrel mouth.
 d.rocketTargetDistance=(aim-origin).Magnitude
 for i=1,count do
  local angle=(i-(count+1)/2)*5
  local target=origin+CFrame.Angles(0,math.rad(angle),0):VectorToWorldSpace(direction)*d.range
  if d.id=='11' then rockets:launch(character,d,origin,target)
  else projectiles:launch(d,origin,target) end
 end
end
-- A slot's definition is rebuilt only when its weapon, tier, stats table, class or body changes
-- (CharacterService replaces the stats table on every change). Never changed in place: an attack
-- works on a clone, which its swing and projectiles keep.
local function definition(slot,base,cs,player,character,index)
 local tier=slot.folder:GetAttribute('Tier');local c=slot.cached
 if not c or c.base~=base or c.tier~=tier or c.stats~=cs.stats or c.class~=cs.class or c.character~=character then
  local d=Stats.weapon(base,cs.stats,cs.class,tier);d.stats=cs.stats;d.owner=player;d.character=character;d.slotIndex=index
  c={base=base,tier=tier,stats=cs.stats,class=cs.class,character=character,d=d};slot.cached=c
 end
 return c.d
end
-- Targeting (P4, TargetGrid): one snapshot of the living enemies per tick, shared by every player
-- and slot, picked from nearest first with the first clear line winning. Enemies killed earlier in
-- the tick fail `fresh`, as the old per-player rebuild dropped them.
local Grid=require(script.Parent:WaitForChild('TargetGrid'))
local function snapshot(enemies)
 local list,byNpc={},{}
 for _,npc in enemies do
  local hum,root=alive(npc)
  if hum then
   local e={npc=npc,hum=hum,root=root,position=root.Position,boss=shelled(npc),dummy=npc:GetAttribute('LobbyDummy'),practice=Death.isPractice(npc)}
   table.insert(list,e);byNpc[npc]=e
  end
 end
 local snap=Grid.new(list);snap.byNpc=byNpc
 return snap
end
local function fresh(e) return e.hum.Health>0 and e.npc.Parent~=nil and e.root.Parent~=nil end
-- Where an enemy is measured to from `origin`: a boss's nearest side, anyone else's root.
local function measured(e,origin) return e.boss and reachPoint(e.npc,e.root,origin) or e.position end
-- The nearest enemy `can` accepts in range with a clear line from origin, and its point.
local function nearest(snap,origin,range,can,wallParams)
 return Grid.nearest(snap,origin,range,can,function(e) return measured(e,origin) end,function(point,e) return fresh(e) and clear(origin,point,wallParams) end)
end
-- A cooling weapon keeps last tick's target while it is still alive, allowed and in range.
local function kept(slot,snap,origin,range,can)
 local e=slot.aimNpc and snap.byNpc[slot.aimNpc]
 if not e or not can(e) or not fresh(e) then return end
 local point=measured(e,origin)
 local distance=(point-origin).Magnitude
 if distance<range and distance>.01 then return e,point end
end
-- WeaponMotion.chooseStyle reads the crowd size for only some weapons. Asking it for no crowd and a
-- huge one tells whether the count can change this stroke; when it can't, the crowd's raycasts are
-- skipped (the Boxing Gloves still look for a second enemy to punch).
local function crowdMatters(id,serial,distance,range) return Motion.chooseStyle(id,0,serial,distance,range)~=Motion.chooseStyle(id,math.huge,serial,distance,range) end
-- LastContact only drives the Frying Pan's wobble (RogueliteCombat.client).
local function contact(slot,id,now) if id=='16' then slot.folder:SetAttribute('LastContact',now) end end
-- One reused melee overlap query; its enemy list is reassigned only when the tagged set differs.
local overlap=OverlapParams.new();overlap.FilterType=Enum.RaycastFilterType.Include
local overlapList={}
local function meleeOverlap(enemies)
 if overlapList~=enemies then
  local same=#enemies==#overlapList
  if same then for i,v in enemies do if overlapList[i]~=v then same=false;break end end end
  if not same then overlap.FilterDescendantsInstances=enemies end
  overlapList=enemies
 end
 return overlap
end
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<1/30 then return end;elapsed=0
 local now=workspace:GetServerTimeNow();local enemies=Tags:GetTagged('RogueliteZombie')
 local snap -- built on the first player who needs it
 for player,s in states do
  local character=player.Character;local root=character and character:FindFirstChild('HumanoidRootPart');local hum=character and character:FindFirstChildOfClass('Humanoid')
  if character~=s.character then s.character=character;for _,slot in s.slots do reset(slot,now+.25) end end
  if not root or not hum or hum.Health<=0 then continue end
  -- Animated limbs and mesh length must never expand/contract the slots.
  -- Small visual intersections are intentional; combat still uses server poses.
  local equippedCount=0
  for _,slot in s.slots do if Catalog.ById[slot.folder:GetAttribute('WeaponId')] then equippedCount+=1 end end
  local radius=Motion.radius(root.Size,equippedCount)
  if math.abs((s.folder:GetAttribute('RingRadius') or 0)-radius)>.04 then s.folder:SetAttribute('RingRadius',radius) end
  radius=s.folder:GetAttribute('RingRadius')
  local wallParams=rayParams(character,true)
  -- The tick's one snapshot (built for the first player who targets) serves every slot and the
  -- attack that fires (nothing can revive an enemy mid-tick). `living` is its list, nil when this
  -- player isn't targeting.
  local living,can
  if equippedCount>0 and Characters.states[player] and s.folder:GetAttribute('WeaponEnabled') then
   snap=snap or snapshot(enemies);living=snap.list
   -- targetable(npc,s) on the snapshot's flags.
   local zombies,lobby=combat:GetAttribute('ZombiesEnabled'),s.folder:GetAttribute('LobbyAttacks')~=false
   can=function(e) if e.dummy then return e.practice and lobby end;return zombies or e.practice end
  end
  local prepared={};local targetCount=0
  for index,slot in s.slots do
   local id=slot.folder:GetAttribute('WeaponId');local base=Catalog.ById[id];if not base then continue end
   local cs=Characters.states[player];if not cs then continue end
   local d=definition(slot,base,cs,player,character,index)
   local origin=Motion.combatOrigin(root.CFrame,radius,index,id,d.kind)
   local searchRange=d.targetRange or d.range
   if d.kind=='Melee' and Motion.DownwardWeapons[id] then
    searchRange=math.max(searchRange,Motion.attackReach(id,'Downward',d.range))
   end
   local found,point
   if living then
    -- Cooling down (it can't attack this tick): keep the target, searching again at 10 Hz.
    if now<slot.ready and now<(slot.nextSearch or 0) then found,point=kept(slot,snap,origin,searchRange,can) end
    if not found then found,point=nearest(snap,origin,searchRange,can,wallParams);slot.nextSearch=now+.1 end
   end
   slot.aimNpc=found and found.npc
   if found then targetCount+=1 end
   table.insert(prepared,{index=index,slot=slot,id=id,definition=d,origin=origin,found=found,target=found and found.root,point=point})
  end
  for _,entry in prepared do
   local index,slot,id=entry.index,entry.slot,entry.id
   local d,origin,target=entry.definition,entry.origin,entry.target
   -- An earlier slot's attack may have killed it.
   if target and not fresh(entry.found) then target=nil end
   if target then
    -- Each weapon owns its clock. Independent opening offsets can overlap;
    -- they have no rank, reserved turn, or dependency on another weapon firing.
    if not slot.lastTarget or now-slot.lastTarget>.3 then
     local phaseStart=slot.start<0 and math.max(now,slot.ready) or now
     local opening=targetCount>1 and slot.random:NextNumber(0,d.cooldown*.8) or 0
     slot.ready=math.max(slot.ready,phaseStart+opening)
    end
    slot.lastTarget=now
   end
   local _,_,duration=Motion.attackTiming(id,d.kind,slot.style)
   -- Clients pose a melee weapon from its attack alone, so only the others are aimed between attacks
   -- (the last attack's kind is what clients draw: a thrown hammer aims).
   if target then if (slot.definition or d).kind~='Melee' then aimAt(slot,target.Position,now) end
   elseif (now-slot.start)*d.motionRate>duration then aimAt(slot,nil,now) end
   if not s.folder:GetAttribute('WeaponEnabled') then continue end
   if target and now>=slot.ready and not specials:busy(player,index) then
    -- Small symmetric variation changes the relative timing every cycle while
    -- keeping the nominal average cadence. Never interrupt this weapon's cut.
    d=table.clone(d) -- this attack's own copy; the slot's cached definition stays unchanged
    local interval=d.cooldown*(equippedCount>1 and slot.random:NextNumber(.9,1.1) or 1)
    slot.serial=(slot.serial or 0)+1
    -- Distances use the reach point (a boss's nearest side); a map boss's swing still faces the root.
    local reach=entry.point or target.Position
    local targetOffset=reach-origin
    local flat=Vector3.new(targetOffset.X,0,targetOffset.Z).Magnitude
    -- The crowd in reach (living enemies with a clear line, in tag order) sets some strokes, and
    -- the Boxing Gloves' second punch goes to the last of them within 8 studs of the target.
    local nearby,second=0,nil
    if id=='19' or crowdMatters(id,slot.serial,flat,d.range) then
     local crowd=Grid.around(snap,origin,d.range)
     if crowd~=living then table.sort(crowd,Grid.byOrder) end
     for _,e in crowd do local h,r=alive(e.npc);if h and (r.Position-origin).Magnitude<=d.range and clear(origin,r.Position,wallParams) then nearby+=1;if r~=target and (r.Position-target.Position).Magnitude<8 then second=r end end end
    end
    slot.style=Motion.chooseStyle(id,nearby,slot.serial,flat,d.range)
    slot.side=Motion.chooseSide(slot.serial)
    d.range=Motion.attackReach(id,slot.style,d.range)
    -- Resolve the hammer's melee/throw choice after selecting its stroke:
    -- overheads can advance farther, while other cuts retain normal reach.
    if (id=='31' or d.throwable) and (reach-origin).Magnitude>d.range then
     d.kind='Ranged';d.damage=d.damage/Stats.mult(d.stats.MeleeDamage)*Stats.mult(d.stats.RangedDamage)
     d.range=d.targetRange
    end
    -- A melee swing at the Hammer Brute lands on his shell (that point), not inside him at his root;
    -- standing inside a body section, it still swings at his root.
    local aim=d.kind=='Melee' and target.Parent:GetAttribute('IsHammerBoss') and (reach-origin).Magnitude>.1 and reach or target.Position
    _,_,duration=Motion.attackTiming(id,d.kind,slot.style)
    interval=math.max(interval,duration/d.motionRate)
    slot.hand=slot.serial%2==1 and -1 or 1;slot.secondAim=second and second.Position or nil
    slot.attackRoot=Motion.attackRoot(root.CFrame,aim)
    slot.attackOrigin=Motion.combatOrigin(slot.attackRoot,radius,index,id,d.kind)
    slot.start=now;slot.ready=now+interval;slot.previous=0;slot.hit={};slot.aim=aim;slot.definition=d
    local delta=Vector3.new(aim.X-origin.X,0,aim.Z-origin.Z)
    slot.direction=delta.Magnitude>.01 and delta.Unit or Motion.frame(root.CFrame).LookVector
    -- One attribute for the whole attack (it was 12, plus an unread ReachScale), and the gun on target as it fires.
    slot.folder:SetAttribute('Attack',Wire.packAttack({start=now,rate=d.motionRate,kind=d.kind,style=slot.style,side=slot.side,hand=slot.hand,range=d.range,root=slot.attackRoot,aim=slot.aim,direction=slot.direction,second=slot.secondAim}))
    if d.kind~='Melee' then aimAt(slot,target.Position,now,true) end
    d.practiceTarget=Death.isPractice(target.Parent)
    d.arcTarget=target
    if d.kind=='Melee' then legendary:swing(d,slot.attackOrigin or origin,target,slot.direction) end
    if d.kind~='Melee' then shoot(d,origin,target.Position,character)
    elseif d.scripted then godly:attack(d,origin,target) end -- the daggers' chain is the hit
   end
   d=slot.definition or d
   local age=(now-slot.start)*d.motionRate
   local activeFrom,activeTo=Motion.attackTiming(id,d.kind,slot.style)
   if d.kind=='Melee' and not d.scripted and slot.previous<=activeTo and age>=activeFrom and slot.style=='Reap' then
    -- The Reap's blade turns a full circle: hit each enemy in reach as its heading passes it.
    local from=slot.previous<activeFrom and -1 or Motion.reapFraction(slot.previous)
    local to=Motion.reapFraction(math.min(age,activeTo))
    local attackOrigin=slot.attackOrigin or origin
    for _,e in living or {} do
     local npc=e.npc
     if not slot.hit[npc] and Tags:HasTag(npc,'RogueliteZombie') and (not npc:GetAttribute('LobbyDummy') or targetable(npc,s)) then
      local health,npcRoot=alive(npc)
      if health then
       local point=reachPoint(npc,npcRoot,attackOrigin);local offset=point-attackOrigin
       local fraction=Motion.reapFractionOf(slot.direction,offset,slot.side)
       if fraction>from and fraction<=to and offset.Magnitude<=d.range and clear(attackOrigin,point,wallParams) then
        slot.hit[npc]=true;damage(npc,d.damage,d);contact(slot,id,now)
       end
      end
     end
    end
   elseif d.kind=='Melee' and not d.scripted and slot.previous<=activeTo and age>=activeFrom then
    local first,last=math.max(slot.previous,activeFrom),math.min(age,activeTo)
    if first<=last then
     local template=templates[id];local size=template:GetAttribute('BoundsSize');local center=template:GetAttribute('BoundsCenter')
     local overlap=meleeOverlap(enemies)
     local steps=math.max(1,math.ceil((last-first)*120))
     for i=0,steps do
      local sampleAge=first+(last-first)*i/steps
      local pose=Motion.pose(slot.attackRoot or root.CFrame,radius,index,slot.aim,slot.start,slot.start+sampleAge,d.kind,id,slot.direction,d.range,size,center,slot.style,slot.side)
      if chainRigs[id] then pose=Chains.pose(chainRigs[id],slot.attackRoot or root.CFrame,slot.direction,slot.aim,sampleAge,d.range,slot.style,slot.side) end
      -- Skinned meshes keep a static engine bounding box. Query the measured
      -- rigid handle and payload at their animated bone poses instead.
      local boxes=chainRigs[id] and Chains.hitBoxes(chainRigs[id],pose,sampleAge) or {{cf=pose*CFrame.new(center),size=size}}
      if id=='19' then
       boxes={}
       for _,part in template:GetDescendants() do if part:IsA('BasePart') then
        local side=template:GetPivot():ToObjectSpace(part.CFrame).X<0 and -1 or 1
        if side==slot.hand or slot.secondAim then
         local aim=side==slot.hand and slot.aim or slot.secondAim
         table.insert(boxes,{cf=Motion.glovePose(slot.attackRoot,aim,sampleAge,side,d.range),size=part.Size})
        end
       end end
      end
      for _,box in boxes do
       for _,part in workspace:GetPartBoundsInBox(box.cf,box.size+Vector3.one*.4,overlap) do
       local npc=part:FindFirstAncestorOfClass('Model')
       if npc and not slot.hit[npc] and Tags:HasTag(npc,'RogueliteZombie') and (not npc:GetAttribute('LobbyDummy') or targetable(npc,s)) then
        local health,npcRoot=alive(npc)
        local attackOrigin=slot.attackOrigin or origin
        local point=health and reachPoint(npc,npcRoot,attackOrigin)
        if health and (point-attackOrigin).Magnitude<=d.range and clear(attackOrigin,point,wallParams) then
         local first=next(slot.hit)==nil -- the swing's first contact (the Wrecking Ball's shockwave)
         slot.hit[npc]=true;damage(npc,d.damage,d);contact(slot,id,now)
         if first then legendary:contact(d,npc,point) end
        end
       end
       end
      end
     end
    end
   end
   slot.previous=age
  end
 end
end)
