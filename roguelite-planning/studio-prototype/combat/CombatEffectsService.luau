local Tags=game:GetService('CollectionService')
local RunService=game:GetService('RunService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Stats=require(combat.CharacterStats)
local Characters=require(script.Parent.CharacterService)
local Death=require(combat.ZombieDeath)
local E={statuses={}}
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
 npc:SetAttribute(name..'Until',workspace:GetServerTimeNow()+duration)
end
function E.hit(npc,amount,d,secondary)
 local h,r=alive(npc);if not h or not d or not valid(d) then return 0 end
 if not Tags:HasTag(npc,'RogueliteZombie') then return 0 end
 -- Tag before damage: the Died handler can run immediately on a lethal shot.
 if d.id=='10' and not secondary and amount>0 then npc:SetAttribute('DesignerShirt',true) end
 local s=d.stats;local position=r.Position
 if not secondary then
  -- Ninja 4-piece: after a dodge (CharacterService.contact) the next direct hit always crits.
  local owner=Characters.states[d.owner];local sure=owner and owner.dodgeCrit
  if sure then owner.dodgeCrit=nil end
  if sure or math.random()<s.CritChance/100 then amount*=s.CritDamage/100 end
 end
 if npc:GetAttribute('IsElite') or npc:GetAttribute('IsBoss') then amount*=Stats.mult(s.BossDamage) end
 -- Owl pet mark (PetService): +bonus% on every hit from the owner while the mark lasts.
 local mark=npc:GetAttribute('PetMark_'..d.owner.UserId)
 if type(mark)=='number' and (npc:GetAttribute('PetMarkUntil_'..d.owner.UserId) or 0)>workspace:GetServerTimeNow() then amount*=1+mark/100 end
 if RunService:IsStudio() and npc:GetAttribute('PracticeTarget') then
  local actual=math.min(h.Health,math.max(0,amount))
  if actual<=0 then return 0 end
  h.Health=h.Health-actual>1 and h.Health-actual or h.MaxHealth
  npc:SetAttribute('PracticeHits',(npc:GetAttribute('PracticeHits') or 0)+1)
  npc:SetAttribute('PracticeDamage',(npc:GetAttribute('PracticeDamage') or 0)+actual)
  npc:SetAttribute('LastWeaponId',d.id)
  combat.Hit:FireAllClients(position+Vector3.yAxis*2,actual,npc,position,false,secondary==true)
  return actual -- no death, rewards, lifesteal farming or damage to the tester
 end
 npc:SetAttribute('LastDamageUserId',d.owner.UserId)
 local before=h.Health;h:TakeDamage(math.max(0,amount));local actual=before-math.max(0,h.Health)
 if actual<=0 then return 0 end
 Characters.leech(d.owner,actual)
 combat:SetAttribute('ConfirmedHits',(combat:GetAttribute('ConfirmedHits') or 0)+1)
 -- A lethal hit is represented by the death burst, not a second hit burst.
 combat.Hit:FireAllClients(position+Vector3.new(0,2,0),actual,npc,position,h.Health<=0,secondary==true)
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
  E.statuses[npc]=nil;Death.finish(npc);return actual
 end
 if secondary then return actual end
 local knockback=math.min(40,s.Knockback+(d.nativeKnockback or 0))
 if knockback>0 and os.clock()-(npc:GetAttribute('LastKnockback') or -1e6)>.12 then
  local pr=d.character:FindFirstChild('HumanoidRootPart');local delta=pr and Vector3.new(position.X-pr.Position.X,0,position.Z-pr.Position.Z)
  if delta and delta.Magnitude>.01 then r:ApplyImpulse(delta.Unit*knockback*r.AssemblyMass*(npc:GetAttribute('IsBoss') and .25 or 1));npc:SetAttribute('LastKnockback',os.clock()) end
 end
 local elemental=Stats.mult(s.Damage)*Stats.mult(s.ElementalDamage)
 if math.random()<math.max(s.BurnChance,d.burn or 0)/100 then status(npc,d,'Burn',3*Stats.mult(s.Duration),6*elemental*Stats.mult(s.BurnDamage),true) end
 if math.random()<math.max(s.PoisonChance,d.poison or 0)/100 then status(npc,d,'Poison',4*Stats.mult(s.Duration),3*elemental*Stats.mult(s.PoisonDamage),false) end
 if math.random()<math.max(s.SlowChance,d.slow or 0)/100 then status(npc,d,'Slow',s.SlowDuration*Stats.mult(s.Duration),s.SlowStrength,false) end
 local state=Characters.states[d.owner]
 if state then
  state.hits+=1
  local sourceCount=math.max(s.ChainCount,d.lightning and 1 or 0)
  local count=math.min(6,sourceCount+s.ChainBonus)
  if sourceCount>0 and state.hits%s.ChainEvery==0 then
   for i,target in near(position,12*Stats.mult(s.AreaSize),{[npc]=true},d.character) do
    if i>count then break end
    combat.Shot:FireAllClients(position,target.HumanoidRootPart.Position,'Lightning',d.id)
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
 combat.Shot:FireAllClients(position+Vector3.yAxis*.5,position,'Blast','Armor',.07,radius)
 local count=0
 for _,npc in Tags:GetTagged('RogueliteZombie') do
  local h,r=alive(npc)
  if h and not npc:GetAttribute('LobbyDummy') and (r.Position-position).Magnitude<=radius then E.hit(npc,damage,d,true);count+=1 end
 end
 return count
end
local elapsed=0
-- Pets (PetService) apply burn, poison and slow through the same status table as weapons.
E.status=status
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.1 then return end;elapsed=0
 local now=os.clock()
 for npc,entries in E.statuses do
  local h=alive(npc)
  if not h then E.statuses[npc]=nil;continue end
  local slow=0
  for key,e in entries do
   if now>=e.ends or not valid(e.d) then entries[key]=nil
   elseif e.name=='Slow' then slow=math.max(slow,e.amount)
   elseif now>=e.nextTick then e.nextTick=now+1;E.hit(npc,e.amount*e.stacks,e.d,true) end
  end
  if h.Parent and h.Health>0 then
   slow*=npc:GetAttribute('IsBoss') and .5 or 1
   npc:SetAttribute('StatusSlowStrength',slow)
   local vacuumSlow=(npc:GetAttribute('VacuumSlowUntil') or 0)>workspace:GetServerTimeNow() and 35 or 0
   h.WalkSpeed=(npc:GetAttribute('BaseMoveSpeed') or 12)*(1-math.max(slow,vacuumSlow)/100)
  end
  if next(entries)==nil then E.statuses[npc]=nil end
 end
end)
return E
