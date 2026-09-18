-- Server-only authoritative character builds, practice controls and health economy.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Stats=require(combat:WaitForChild('CharacterStats'))
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local Service={states={}}
local drops={}
local function humanoid(player) return player.Character and player.Character:FindFirstChildOfClass('Humanoid') end
function Service.refresh(player)
 local s=Service.states[player];if not s then return end
 local count=0
 for _,slot in s.folder:GetChildren() do local d=Catalog.ById[slot:GetAttribute('WeaponId')];if d and d.home==s.class then count+=1 end end
 s.stats=Stats.resolve(s.class,count,s.overrides,s.itemBonuses,s.itemPercent)
 s.folder:SetAttribute('Class',s.class);s.folder:SetAttribute('AffinityCount',count)
 for _,d in Stats.List do
  local value=s.stats[d.id];s.folder:SetAttribute('Stat_'..d.id,value)
  s.folder:SetAttribute('Override_'..d.id,s.overrides[d.id]~=nil)
  if player.Character then player.Character:SetAttribute('Stat_'..d.id,value) end
 end
 local h=humanoid(player)
 if h then
  local missing=h.MaxHealth-h.Health;local alive=h.Health>0
  h.MaxHealth=s.stats.MaxHP;if alive then h.Health=math.clamp(h.MaxHealth-missing,1,h.MaxHealth) end
  h.WalkSpeed=s.stats.MoveSpeed
  player.Character:SetAttribute('CombatClass',s.class)
 end
 if Service.onStatsChanged then Service.onStatsChanged(player) end
end
function Service.attach(player,folder)
 local s={folder=folder,class='Brawler',overrides={},lastRequest=-1e6,lastContact=0,blocks=1,leech=0,hits=0}
 Service.states[player]=s
 local function spawned(character)
  local h=character:WaitForChild('Humanoid',10);if not h or player.Character~=character then return end
  s.leech=0;s.blocks=1;s.hits=0;s.lastContact=os.clock()
  Service.refresh(player);h.Health=h.MaxHealth
  -- Disable Roblox's implicit regeneration: this game's Recovery/Regeneration own healing.
  local health=character:FindFirstChild('Health');if health and health:IsA('Script') then health.Disabled=true end
 end
 player.CharacterAdded:Connect(spawned)
 if player.Character then task.spawn(spawned,player.Character) end
 for _,slot in folder:GetChildren() do slot:GetAttributeChangedSignal('WeaponId'):Connect(function() Service.refresh(player) end) end
 Service.refresh(player)
end
function Service.heal(player,amount)
 local s=Service.states[player];local h=humanoid(player)
 if s and h and h.Health>0 then h.Health=math.min(h.MaxHealth,h.Health+math.max(0,amount)*Stats.mult(s.stats.Recovery)) end
end
function Service.leech(player,damage)
 local s=Service.states[player];if not s then return end
 local h=humanoid(player);if not h or h.Health<=0 then return end
 local heal=math.min(damage*s.stats.LifeSteal/100*Stats.mult(s.stats.Recovery),math.max(0,s.stats.LifeStealCap-s.leech))
 s.leech+=heal;h.Health=math.min(h.MaxHealth,h.Health+heal)
end
function Service.contact(player,amount,roll)
 local s=Service.states[player];local h=humanoid(player)
 if not s or not h or h.Health<=0 or player.Character:FindFirstChildOfClass('ForceField') then return 0 end
 if s.stats.FirstHitBlock>0 and s.blocks>0 then s.blocks-=1;s.folder:SetAttribute('BlocksRemaining',s.blocks);return 0 end
 if (roll or math.random())<s.stats.Dodge/100 then return 0 end
 local before=h.Health;h:TakeDamage(Stats.incoming(amount,s.stats));return before-h.Health
end
function Service.drop(player,position)
 if Service.onKill then Service.onKill(player) end
 local s=Service.states[player];if not s or #drops>=60 or math.random()>.15+s.stats.Luck/500 then return end
 local p=Instance.new('Part');p.Name='PracticeHealthDrop';p.Shape=Enum.PartType.Ball;p.Size=Vector3.one*.7
 p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false;p.Material=Enum.Material.Neon;p.Color=Color3.fromRGB(146,200,113);p.Position=position;p.Parent=workspace
 p:SetAttribute('OwnerUserId',player.UserId)
 table.insert(drops,{part=p,owner=player,expires=os.clock()+20})
end
local remote=combat:FindFirstChild('EditPractice') or Instance.new('RemoteEvent')
remote.Name='EditPractice';remote.Parent=combat
function Service.request(player,action,key,value)
 local s=Service.states[player];local h=humanoid(player);local run=game.ReplicatedStorage:FindFirstChild('RogueliteRunState')
 if not RunService:IsStudio() or not s or not h or h.Health<=0 or (run and run:GetAttribute('Phase')~='Practice' and run:GetAttribute('Phase')~='Shop' and action~='Zombies') then return false end
 if type(action)~='string' or type(key)=='table' or os.clock()-s.lastRequest<.08 then return false end
 if action=='Stat' then
  if type(key)~='string' or not Stats.valid(key,value) then return false end
  s.overrides[key]=value;Service.refresh(player)
 elseif action=='Class' then
  if type(key)~='string' or not Stats.Classes[key] then return false end
  s.class=key;s.overrides={};Service.refresh(player)
 elseif action=='Build' then
  if run and run:GetAttribute('Phase')~='Practice' then return false end
  local preset=Stats.Classes[s.class].build
  for index,id in preset do if not combat.WeaponTemplates:FindFirstChild(id) then return false end end
  for i=1,6 do
   local slot=s.folder:FindFirstChild('Slot'..i);slot:SetAttribute('WeaponId',preset[i] or '');slot:SetAttribute('StartTime',-1e6)
  end
  s.folder:SetAttribute('EquippedCount',#preset);Service.refresh(player)
 elseif action=='Reset' then s.overrides={};Service.refresh(player)
 elseif action=='Heal' then h.Health=h.MaxHealth
 elseif action=='Damage' then Service.contact(player,20)
 elseif action=='Zombies' then
  if type(value)~='number' or value~=value or value%1~=0 or value<0 or value>100 then return false end
  combat:SetAttribute('ZombieCount',value)
  combat:SetAttribute('TestZombieCountOverride',value)
 elseif action=='AutoZombies' then combat:SetAttribute('TestZombieCountOverride',nil)
 else return false end
 s.lastRequest=os.clock();s.folder:SetAttribute('PracticeRevision',(s.folder:GetAttribute('PracticeRevision') or 0)+1)
 return true
end
remote.OnServerEvent:Connect(function(...) Service.request(...) end)
Players.PlayerRemoving:Connect(function(p) Service.states[p]=nil end)
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.1 then return end;local step=elapsed;elapsed=0
 local now=os.clock()
 for player,s in Service.states do
  local h=humanoid(player);local root=player.Character and player.Character:FindFirstChild('HumanoidRootPart')
  if h and root and h.Health>0 then
   Service.heal(player,s.stats.Regeneration*step)
   local second=math.floor(now);if s.leechSecond~=second then s.leechSecond=second;s.leech=0 end
   if now-s.lastContact>=.8 and combat:GetAttribute('ZombiesEnabled') then
    for _,npc in Tags:GetTagged('RogueliteZombie') do
     local nr=npc:FindFirstChild('HumanoidRootPart');local nh=npc:FindFirstChildOfClass('Humanoid')
     if nr and nh and nh.Health>0 and (nr.Position-root.Position).Magnitude<4.5 then
      local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances={npc,player.Character,workspace:FindFirstChild('RogueliteEnemies')}
      if not workspace:Raycast(nr.Position,root.Position-nr.Position,params) then s.lastContact=now;Service.contact(player,10);break end
     end
    end
   end
  end
 end
 for i=#drops,1,-1 do
  local d=drops[i];if not d.part.Parent then table.remove(drops,i);continue end;local s=Service.states[d.owner];local h=humanoid(d.owner);local r=d.owner.Character and d.owner.Character:FindFirstChild('HumanoidRootPart')
  local collect=s and h and h.Health>0 and h.Health<h.MaxHealth and r and (r.Position-d.part.Position).Magnitude<=s.stats.PickupRadius
  if collect then Service.heal(d.owner,8) end
  if collect or not s or now>d.expires or not d.part.Parent then d.part:Destroy();table.remove(drops,i) end
 end
end)
local function resetBlocks() for _,s in Service.states do s.blocks=1;s.folder:SetAttribute('BlocksRemaining',1) end end
combat:GetAttributeChangedSignal('ZombieCount'):Connect(resetBlocks)
combat:GetAttributeChangedSignal('ZombiesEnabled'):Connect(resetBlocks)
return Service
