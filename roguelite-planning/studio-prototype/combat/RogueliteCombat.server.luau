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
-- Slot 1 holds the loadout starter the lobby validated (RunWeapon); Brawler's signature until one is picked.
-- Each class build opens with its signature weapon. RunSetupRules isn't sandboxed, so this script can't require it.
local function starter(player)
 local id=player:GetAttribute('RunWeapon')
 return type(id)=='string' and Catalog.ById[id] and templates:FindFirstChild(id) and id or Stats.Classes.Brawler.build[1]
end
local function reset(slot,now)
 slot.start=-1e6;slot.ready=now;slot.previous=0;slot.hit={};slot.definition=nil
 slot.lastTarget=nil
 slot.folder:SetAttribute('StartTime',slot.start);slot.folder:SetAttribute('AimPosition',nil)
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
local function rayParams(character,ignoreEnemies)
 local filter={character}
 for _,p in Players:GetPlayers() do if p.Character then table.insert(filter,p.Character) end end
 for _,name in {'RogueliteWeaponShowcase','RogueliteWeaponShowcase_PlaySize'} do
  local f=workspace:FindFirstChild(name);if f then table.insert(filter,f) end
 end
 local marker=Role.marker();if marker then table.insert(filter,marker) end
 if ignoreEnemies then for _,npc in Tags:GetTagged('RogueliteZombie') do table.insert(filter,npc) end end
 local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances=filter;return p
end
local function clear(origin,finish,p) return workspace:Raycast(origin,finish-origin,p)==nil end
-- Where reach is measured to. A map boss is far wider than its root box (the dragon's side is
-- ~9 studs from its centre), so it is measured to the nearest point of any body section's box:
-- a pan touching its flank is in range. Every other enemy is measured to its root, as before.
local function reachPoint(npc,root,from)
 if not npc:GetAttribute('IsMapBoss') then return root.Position end
 local best,bestDistance=root.Position,(root.Position-from).Magnitude
 for _,p in npc:GetChildren() do
  if p:IsA('MeshPart') or p==root then
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
local function damage(npc,amount,d,secondary) return Effects.hit(npc,amount,d,secondary) end
local rockets=require(combat:WaitForChild('RocketProjectile')).new(combat,damage,rayParams)
local projectiles=require(script.Parent:WaitForChild('StatProjectiles')).new(combat,damage,rayParams)
local arcs=require(script.Parent:WaitForChild('ArcProjectiles')).new(combat,damage,rayParams)
local specials=require(script.Parent:WaitForChild('SpecialWeapons')).new(combat,damage,rayParams)
local function shoot(d,origin,aim,character)
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
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<1/30 then return end;elapsed=0
 local now=workspace:GetServerTimeNow();local enemies=Tags:GetTagged('RogueliteZombie')
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
  -- Reuse eligibility only within this player's non-yielding preparation pass.
  -- Rebuild for the next player: earlier attacks may have killed an enemy.
  local targetParts,targetPositions,targetBosses
  if equippedCount>1 and Characters.states[player] and s.folder:GetAttribute('WeaponEnabled') then
   targetParts,targetPositions,targetBosses={},{},{}
   for _,npc in enemies do local health,part=alive(npc)
    if health and targetable(npc,s) then
     targetParts[#targetParts+1]=part;targetPositions[#targetPositions+1]=part.Position
     targetBosses[#targetBosses+1]=npc:GetAttribute('IsMapBoss')==true
    end
   end
  end
  local prepared={};local targetCount=0
  for index,slot in s.slots do
   local id=slot.folder:GetAttribute('WeaponId');local base=Catalog.ById[id];if not base then continue end
   local cs=Characters.states[player];if not cs then continue end
   local d=Stats.weapon(base,cs.stats,cs.class,slot.folder:GetAttribute('Tier'));d.stats=cs.stats;d.owner=player;d.character=character;d.slotIndex=index
   local origin=Motion.combatOrigin(root.CFrame,radius,index,id,d.kind)
   local searchRange=d.targetRange or d.range
   if d.kind=='Melee' and Motion.DownwardWeapons[id] then
    searchRange=math.max(searchRange,Motion.attackReach(id,'Downward',d.range))
   end
   local target,best,point=nil,searchRange,nil
   if targetParts then
    for i,part in targetParts do local position=targetBosses[i] and reachPoint(part.Parent,part,origin) or targetPositions[i];local distance=(position-origin).Magnitude
     if distance<best and distance>.01 and clear(origin,position,wallParams) then target=part;best=distance;point=position end
    end
   elseif s.folder:GetAttribute('WeaponEnabled') then
    for _,npc in enemies do local health,part=alive(npc)
     if health and targetable(npc,s) then local position=reachPoint(npc,part,origin);local distance=(position-origin).Magnitude
      if distance<best and distance>.01 and clear(origin,position,wallParams) then target=part;best=distance;point=position end
     end
    end
   end
   if target then targetCount+=1 end
   table.insert(prepared,{index=index,slot=slot,id=id,definition=d,origin=origin,target=target,point=point})
  end
  for _,entry in prepared do
   local index,slot,id=entry.index,entry.slot,entry.id
   local d,origin,target=entry.definition,entry.origin,entry.target
   if target and (not target.Parent or not alive(target.Parent)) then target=nil end
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
   if target then slot.folder:SetAttribute('AimPosition',target.Position) elseif (now-slot.start)*d.motionRate>duration then slot.folder:SetAttribute('AimPosition',nil) end
   if not s.folder:GetAttribute('WeaponEnabled') then continue end
   if target and now>=slot.ready and not specials:busy(player,index) then
    -- Small symmetric variation changes the relative timing every cycle while
    -- keeping the nominal average cadence. Never interrupt this weapon's cut.
    local interval=d.cooldown*(equippedCount>1 and slot.random:NextNumber(.9,1.1) or 1)
    slot.serial=(slot.serial or 0)+1
    local nearby,second=0,nil
    for _,npc in enemies do local h,r=alive(npc);if h and (r.Position-origin).Magnitude<=d.range and clear(origin,r.Position,wallParams) then nearby+=1;if r~=target and (r.Position-target.Position).Magnitude<8 then second=r end end end
    -- Distances use the reach point (a map boss's nearest side); the swing still faces the root.
    local reach=entry.point or target.Position
    local targetOffset=reach-origin
    slot.style=Motion.chooseStyle(id,nearby,slot.serial,Vector3.new(targetOffset.X,0,targetOffset.Z).Magnitude,d.range)
    slot.side=Motion.chooseSide(slot.serial)
    d.range=Motion.attackReach(id,slot.style,d.range)
    -- Resolve the hammer's melee/throw choice after selecting its stroke:
    -- overheads can advance farther, while other cuts retain normal reach.
    if id=='31' and (reach-origin).Magnitude>d.range then
     d.kind='Ranged';d.damage=d.damage/Stats.mult(d.stats.MeleeDamage)*Stats.mult(d.stats.RangedDamage)
     d.range=d.targetRange
    end
    _,_,duration=Motion.attackTiming(id,d.kind,slot.style)
    interval=math.max(interval,duration/d.motionRate)
    slot.folder:SetAttribute('AttackSide',slot.side)
    slot.hand=slot.serial%2==1 and -1 or 1;slot.secondAim=second and second.Position or nil
    slot.attackRoot=Motion.attackRoot(root.CFrame,target.Position)
    slot.attackOrigin=Motion.combatOrigin(slot.attackRoot,radius,index,id,d.kind)
    slot.folder:SetAttribute('AttackRoot',slot.attackRoot);slot.folder:SetAttribute('AttackStyle',slot.style)
    slot.folder:SetAttribute('AttackKind',d.kind);slot.folder:SetAttribute('AttackHand',slot.hand);slot.folder:SetAttribute('SecondAim',slot.secondAim)
    slot.start=now;slot.ready=now+interval;slot.previous=0;slot.hit={};slot.aim=target.Position;slot.definition=d
    local delta=Vector3.new(target.Position.X-origin.X,0,target.Position.Z-origin.Z)
    slot.direction=delta.Magnitude>.01 and delta.Unit or Motion.frame(root.CFrame).LookVector
    slot.folder:SetAttribute('MotionRate',d.motionRate);slot.folder:SetAttribute('ReachScale',Stats.mult(d.stats.AttackRange))
    slot.folder:SetAttribute('SwingRange',d.range)
    slot.folder:SetAttribute('AttackAim',slot.aim);slot.folder:SetAttribute('AttackDirection',slot.direction);slot.folder:SetAttribute('StartTime',now)
    d.practiceTarget=Death.isPractice(target.Parent)
    d.arcTarget=target
    if d.kind~='Melee' then shoot(d,origin,target.Position,character) end
   end
   d=slot.definition or d
   local age=(now-slot.start)*d.motionRate
   local activeFrom,activeTo=Motion.attackTiming(id,d.kind,slot.style)
   if d.kind=='Melee' and slot.previous<=activeTo and age>=activeFrom then
    local first,last=math.max(slot.previous,activeFrom),math.min(age,activeTo)
    if first<=last then
     local template=templates[id];local size=template:GetAttribute('BoundsSize');local center=template:GetAttribute('BoundsCenter')
     local overlap=OverlapParams.new();overlap.FilterType=Enum.RaycastFilterType.Include;overlap.FilterDescendantsInstances=enemies
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
        if health and (point-attackOrigin).Magnitude<=d.range and clear(attackOrigin,point,wallParams) then slot.hit[npc]=true;damage(npc,d.damage,d);slot.folder:SetAttribute('LastContact',now) end
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
