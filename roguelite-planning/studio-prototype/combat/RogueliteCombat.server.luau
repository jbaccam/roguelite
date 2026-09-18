local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local Motion=require(combat:WaitForChild('WeaponMotion'))
local templates=combat:WaitForChild('WeaponTemplates')
local Death=require(combat:WaitForChild('ZombieDeath'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local Characters=require(script.Parent:WaitForChild('CharacterService'))
local Effects=require(script.Parent:WaitForChild('CombatEffectsService'))
local states={}
local Shop=require(script.Parent:WaitForChild('ShopService'))
local function reset(slot,now)
 slot.start=-1e6;slot.ready=now;slot.previous=0;slot.hit={};slot.definition=nil
 slot.folder:SetAttribute('StartTime',slot.start);slot.folder:SetAttribute('AimPosition',nil)
end
local function add(player)
 local f=Instance.new('Folder');f.Name=tostring(player.UserId)
 f:SetAttribute('WeaponEnabled',true);f:SetAttribute('RingRadius',6)
 local s={folder=f,slots={},lastOption=-1e6,lastEquip=-1e6};states[player]=s
 for i=1,Catalog.Slots do
  local child=Instance.new('Folder');child.Name='Slot'..i
  child:SetAttribute('WeaponId',i==1 and '03' or '');child:SetAttribute('Index',i);child.Parent=f
  local slot={folder=child};s.slots[i]=slot;reset(slot,0)
 end
 f:SetAttribute('EquippedCount',1);f.Parent=combat.PlayerStates
 Characters.attach(player,f)
 Shop.attach(player)
 for _,slot in s.slots do slot.folder:GetAttributeChangedSignal('WeaponId'):Connect(function() reset(slot,workspace:GetServerTimeNow()+.25) end) end
end
Players.PlayerAdded:Connect(add)
for _,p in Players:GetPlayers() do add(p) end
Players.PlayerRemoving:Connect(function(p) local s=states[p];if s then s.folder:Destroy();states[p]=nil end end)
combat.EquipWeapon.OnServerEvent:Connect(function(player,index,id)
 local s=states[player]
 if not RunService:IsStudio() or not s or not Catalog.validate(index,id) then return end
 local hum=player.Character and player.Character:FindFirstChildOfClass('Humanoid')
 if not hum or hum.Health<=0 then return end
 if id~='' and not templates:FindFirstChild(id) then return end
 if os.clock()-s.lastEquip<.12 then return end;s.lastEquip=os.clock()
 local slot=s.slots[index]
 if slot.folder:GetAttribute('WeaponId')==id then return end
 -- Creative copies are free, and never inherit the replaced copy's paid refund.
 slot.folder:SetAttribute('CopyId',game:GetService('HttpService'):GenerateGUID(false))
 slot.folder:SetAttribute('BasePrice',0);slot.folder:SetAttribute('FinalPurchasePrice',0);slot.folder:SetAttribute('PurchasePrice',0)
 slot.folder:SetAttribute('Tier',1);slot.folder:SetAttribute('WavePurchased',0)
 slot.folder:SetAttribute('WeaponId',id);reset(slot,workspace:GetServerTimeNow()+.25)
 local count=0;for _,v in s.slots do if v.folder:GetAttribute('WeaponId')~='' then count+=1 end end
 s.folder:SetAttribute('EquippedCount',count)
 local shopState=Shop.states[player];if shopState then shopState.ready=false;shopState.revision+=1;Shop.publish(player) end
end)
combat.SetTestOption.OnServerEvent:Connect(function(player,key,value)
 local s=states[player]
 if not RunService:IsStudio() or not s or type(value)~='boolean' or (key~='Zombies' and key~='Katana' and key~='Weapons') then return end
 local hum=player.Character and player.Character:FindFirstChildOfClass('Humanoid')
 local run=game.ReplicatedStorage:FindFirstChild('RogueliteRunState')
 if not hum or hum.Health<=0 or (run and run:GetAttribute('Phase')~='Practice') then return end
 if os.clock()-s.lastOption<.15 then return end;s.lastOption=os.clock()
 if key=='Zombies' then combat:SetAttribute('ZombiesEnabled',value)
 else s.folder:SetAttribute('WeaponEnabled',value);for _,slot in s.slots do reset(slot,workspace:GetServerTimeNow()+.25) end end
end)
local function alive(npc)
 if not npc:IsDescendantOf(workspace) then return end
 local hum=npc:FindFirstChildOfClass('Humanoid');local root=npc:FindFirstChild('HumanoidRootPart')
 if hum and root and hum.Health>0 then return hum,root end
end
local function rayParams(character,ignoreEnemies)
 local filter={character}
 for _,p in Players:GetPlayers() do if p.Character then table.insert(filter,p.Character) end end
 for _,name in {'RogueliteWeaponShowcase','RogueliteWeaponShowcase_PlaySize','RogueliteZombieSpawn'} do
  local f=workspace:FindFirstChild(name);if f then table.insert(filter,f) end
 end
 if ignoreEnemies then local f=workspace:FindFirstChild('RogueliteEnemies');if f then table.insert(filter,f) end end
 local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances=filter;return p
end
local function clear(origin,finish,p) return workspace:Raycast(origin,finish-origin,p)==nil end
local function damage(npc,amount,d) return Effects.hit(npc,amount,d) end
local rockets=require(combat:WaitForChild('RocketProjectile')).new(combat,damage,rayParams)
local projectiles=require(script.Parent:WaitForChild('StatProjectiles')).new(combat,damage,rayParams)
local function shoot(d,origin,aim,p,wallParams,enemies,character)
 local count=(d.kind=='Spread' and 5 or 1)+d.stats.ProjectileCount
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
  -- Common radius, fixed anchors every 60 degrees. Bound each complete mesh outside the body.
  local half=1.5
  for _,slot in s.slots do local t=templates:FindFirstChild(slot.folder:GetAttribute('WeaponId'));if t then half=math.max(half,t:GetAttribute('BoundsSize').Magnitude/2) end end
  local body=1.6
  for _,part in character:GetChildren() do if part:IsA('BasePart') and part~=root then
   local offset=part.Position-root.Position;body=math.max(body,Vector3.new(offset.X,0,offset.Z).Magnitude+math.max(part.Size.X,part.Size.Z)/2)
  end end
  local radius=body+half+1
  if math.abs((s.folder:GetAttribute('RingRadius') or 0)-radius)>.04 then s.folder:SetAttribute('RingRadius',radius) end
  radius=s.folder:GetAttribute('RingRadius')
  local wallParams=rayParams(character,true);local params=rayParams(character,false)
  for index,slot in s.slots do
   local id=slot.folder:GetAttribute('WeaponId');local base=Catalog.ById[id];if not base then continue end
   local cs=Characters.states[player];if not cs then continue end
   local d=Stats.weapon(base,cs.stats,cs.class,slot.folder:GetAttribute('Tier'));d.stats=cs.stats;d.owner=player;d.character=character;d.slotIndex=index
   local origin=Motion.origin(root.CFrame,radius,index)
   local target,best=nil,d.range
   if s.folder:GetAttribute('WeaponEnabled') and combat:GetAttribute('ZombiesEnabled') then
    for _,npc in enemies do local health,part=alive(npc)
     if health then local distance=(part.Position-origin).Magnitude
      if distance<best and distance>.01 and clear(origin,part.Position,wallParams) then target=part;best=distance end
     end
    end
   end
   if target then slot.folder:SetAttribute('AimPosition',target.Position) elseif (now-slot.start)*d.motionRate>.34 then slot.folder:SetAttribute('AimPosition',nil) end
   if not s.folder:GetAttribute('WeaponEnabled') or not combat:GetAttribute('ZombiesEnabled') then continue end
   if target and now>=slot.ready then
    slot.start=now;slot.ready=now+d.cooldown;slot.previous=0;slot.hit={};slot.aim=target.Position;slot.definition=d
    slot.folder:SetAttribute('MotionRate',d.motionRate);slot.folder:SetAttribute('ReachScale',Stats.mult(d.stats.AttackRange))
    slot.folder:SetAttribute('AttackAim',slot.aim);slot.folder:SetAttribute('StartTime',now)
    if d.kind~='Melee' then shoot(d,origin,target.Position,params,wallParams,enemies,character) end
   end
   d=slot.definition or d
   local age=(now-slot.start)*d.motionRate
   if d.kind=='Melee' and slot.previous<=.22 and age>=.08 then
    local first,last=math.max(slot.previous,.08),math.min(age,.22)
    if first<=last then
     local template=templates[id];local size=template:GetAttribute('BoundsSize');local center=template:GetAttribute('BoundsCenter')
     local overlap=OverlapParams.new();overlap.FilterType=Enum.RaycastFilterType.Include;overlap.FilterDescendantsInstances=enemies
     local steps=math.max(1,math.ceil((last-first)*120))
     for i=0,steps do
      local pose=Motion.pose(root.CFrame,radius,index,slot.aim,slot.start,slot.start+first+(last-first)*i/steps,d.kind)
      local reach=Stats.mult(d.stats.AttackRange)
      pose=CFrame.new(origin+(pose.Position-origin)*reach)*pose.Rotation
      for _,part in workspace:GetPartBoundsInBox(pose*CFrame.new(center),size+Vector3.one*.4,overlap) do
       local npc=part:FindFirstAncestorOfClass('Model')
       if npc and not slot.hit[npc] and Tags:HasTag(npc,'RogueliteZombie') then
        local health,npcRoot=alive(npc)
        if health and (npcRoot.Position-origin).Magnitude<=d.range and clear(origin,npcRoot.Position,wallParams) then slot.hit[npc]=true;damage(npc,d.damage,d) end
       end
      end
     end
    end
   end
   slot.previous=age
  end
 end
end)
