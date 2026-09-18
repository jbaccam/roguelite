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
 local s=d.stats;local position=r.Position
 if not secondary and math.random()<s.CritChance/100 then amount*=s.CritDamage/100 end
 if npc:GetAttribute('IsElite') or npc:GetAttribute('IsBoss') then amount*=Stats.mult(s.BossDamage) end
 local before=h.Health;h:TakeDamage(math.max(0,amount));local actual=before-h.Health
 if actual<=0 then return 0 end
 Characters.leech(d.owner,actual)
 combat:SetAttribute('ConfirmedHits',(combat:GetAttribute('ConfirmedHits') or 0)+1)
 combat.Hit:FireAllClients(position+Vector3.new(0,2,0),actual,npc)
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
  E.statuses[npc]=nil;Characters.drop(d.owner,position);Death.finish(npc);return actual
 end
 if secondary then return actual end
 if s.Knockback>0 and os.clock()-(npc:GetAttribute('LastKnockback') or -1e6)>.12 then
  local pr=d.character:FindFirstChild('HumanoidRootPart');local delta=pr and Vector3.new(position.X-pr.Position.X,0,position.Z-pr.Position.Z)
  if delta and delta.Magnitude>.01 then r:ApplyImpulse(delta.Unit*s.Knockback*r.AssemblyMass*(npc:GetAttribute('IsBoss') and .25 or 1));npc:SetAttribute('LastKnockback',os.clock()) end
 end
 local elemental=Stats.mult(s.Damage)*Stats.mult(s.ElementalDamage)
 if math.random()<math.max(s.BurnChance,d.burn or 0)/100 then status(npc,d,'Burn',3*Stats.mult(s.Duration),6*elemental*Stats.mult(s.BurnDamage),true) end
 if math.random()<math.max(s.PoisonChance,d.poison or 0)/100 then status(npc,d,'Poison',4*Stats.mult(s.Duration),3*elemental*Stats.mult(s.PoisonDamage),false) end
 if math.random()<math.max(s.SlowChance,d.slow or 0)/100 then status(npc,d,'Slow',s.SlowDuration*Stats.mult(s.Duration),s.SlowStrength,false) end
 local state=Characters.states[d.owner]
 if state then
  state.hits+=1
  local count=math.max(s.ChainCount,d.lightning and 1 or 0)
  if count>0 and state.hits%s.ChainEvery==0 then
   for i,target in near(position,12*Stats.mult(s.AreaSize),{[npc]=true},d.character) do
    if i>count then break end
    combat.Shot:FireAllClients(position,target.HumanoidRootPart.Position,'Lightning',d.id)
    E.hit(target,d.damage*.4*Stats.mult(s.ChainDamage),d,true)
   end
  end
 end
 return actual
end
local elapsed=0
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
  if h.Parent and h.Health>0 then h.WalkSpeed=(npc:GetAttribute('BaseMoveSpeed') or 13.5)*(1-slow/100*(npc:GetAttribute('IsBoss') and .5 or 1)) end
  if next(entries)==nil then E.statuses[npc]=nil end
 end
end)
return E
