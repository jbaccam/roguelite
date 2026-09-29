-- Server only: encounter lifecycle, committed poses and substepped hammer damage.
local Players=game:GetService('Players')
local Run=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Motion=require(combat:WaitForChild('BossMotion'))
local Characters=require(script.Parent.CharacterService)
local Death=require(combat.ZombieDeath)
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed; this module is unsandboxed
local B={states={}}
-- Wave chase speed: well under the 24 studs/s player base, fast enough to close gaps.
local CHASE_SPEED=15
local lastPracticeRequest=-math.huge
function B.practice(player,action)
 -- Developers only (the admin panel), in Studio and on live servers; CharacterService checks too.
 if not Admin.isAdmin(player) or (action~='SpawnBoss' and action~='RemoveBoss') then return false end
 local ch=player.Character;local h=ch and ch:FindFirstChildOfClass('Humanoid');local root=ch and ch:FindFirstChild('HumanoidRootPart')
 local folder=workspace:FindFirstChild('RogueliteEnemies')
 if not Characters.states[player] or not h or h.Health<=0 or not root or not folder or os.clock()-lastPracticeRequest<.5 then return false end
 local phase=game.ReplicatedStorage:FindFirstChild('RogueliteRunState')
 if phase and not table.find({'Shop','Combat','Practice'},phase:GetAttribute('Phase')) then return false end
 lastPracticeRequest=os.clock()
 if action=='RemoveBoss' then
  for _,npc in folder:GetChildren() do if npc:GetAttribute('IsHammerBoss') and npc:GetAttribute('BossPractice') then npc:Destroy() end end
  combat:SetAttribute('PracticeBossStatus','Practice boss removed');return true
 end
 for _,npc in folder:GetChildren() do
  if npc:GetAttribute('IsHammerBoss') then combat:SetAttribute('PracticeBossStatus','A boss is already present');return false end
 end
 local exclude={folder,ch,workspace:FindFirstChild('ZombieVariantPreviews')}
 for _,p in Players:GetPlayers() do if p.Character then table.insert(exclude,p.Character) end end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=exclude
 local look=Vector3.new(root.CFrame.LookVector.X,0,root.CFrame.LookVector.Z)
 if look.Magnitude<.1 then look=Vector3.new(0,0,-1) else look=look.Unit end
 local cf
 for _,angle in {0,45,-45,90,-90,180} do
  local direction=CFrame.Angles(0,math.rad(angle),0):VectorToWorldSpace(look)
  local at=root.Position+direction*20
  local floor=workspace:Raycast(at+Vector3.yAxis*16,-Vector3.yAxis*48,params)
  if floor and floor.Normal.Y>.8 and not workspace:Raycast(root.Position,direction*20,params) then
   local pos=floor.Position+Vector3.yAxis*(Motion.RootHeight+.1)
   local overlap=OverlapParams.new();overlap.FilterType=Enum.RaycastFilterType.Exclude;overlap.FilterDescendantsInstances=exclude;overlap.RespectCanCollide=true
   if #workspace:GetPartBoundsInBox(CFrame.new(pos+Vector3.yAxis*1.8),Vector3.new(10,11,7)*Motion.Scale,overlap)==0 then
    cf=CFrame.lookAt(pos,Vector3.new(root.Position.X,pos.Y,root.Position.Z));break
   end
  end
 end
 if not cf then combat:SetAttribute('PracticeBossStatus','Move to open ground to spawn the boss');return false end
 -- Enabling first lets the normal population reset finish before adding the boss.
 combat:SetAttribute('ZombiesEnabled',true)
 local npc=B.spawn(cf,true)
 if not npc then combat:SetAttribute('PracticeBossStatus','Boss template unavailable');return false end
 combat:SetAttribute('PracticeBossStatus','Practice boss active · no rewards')
 npc.Destroying:Connect(function() combat:SetAttribute('PracticeBossStatus','Practice boss gone · spawn another') end)
 return true
end
Characters.onPracticeBoss=B.practice
local function exclusions(npc)
 local list={npc,workspace:FindFirstChild('RogueliteEnemies'),workspace:FindFirstChild('HammerBossReview')}
 for _,p in Players:GetPlayers() do if p.Character then table.insert(list,p.Character) end end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=list;return params
end
function B.start(npc,kind,target)
 local s=B.states[npc];local a=Motion.Attacks[kind];local h=npc:FindFirstChildOfClass('Humanoid');local root=npc.PrimaryPart
 if not s or not a or s.attack or h.Health<=0 or not target or not target.Parent then return false end
 local delta=target.Position-root.Position;local flat=Vector3.new(delta.X,0,delta.Z)
 if flat.Magnitude>Motion.reach(kind)+3 or math.abs(delta.Y)>7 then return false end
 if workspace:Raycast(root.Position,target.Position-root.Position,exclusions(npc)) then return false end
 if flat.Magnitude>.1 then root.CFrame=CFrame.lookAt(root.Position,root.Position+flat) end
 if kind=='Slam' then
  local localHit=Motion.head(CFrame.identity,'Slam',a.active).Position
  root.CFrame*=CFrame.Angles(0,math.atan2(localHit.X,-localHit.Z),0)
 end
 local ground=workspace:Raycast(root.Position+Vector3.yAxis*8,-Vector3.yAxis*30,exclusions(npc))
 if not ground then return false end
 local now=workspace:GetServerTimeNow()
 s.attack={kind=kind,start=now,cf=root.CFrame,hits={},sampled=0};s.next=now+a.cooldown
 npc:SetAttribute('BossAttack',kind);npc:SetAttribute('BossStart',now);npc:SetAttribute('BossFrame',root.CFrame);npc:SetAttribute('BossGroundY',ground.Position.Y)
 npc:SetAttribute('BossSerial',(npc:GetAttribute('BossSerial') or 0)+1);npc:SetAttribute('Attacking',true)
 h:Move(Vector3.zero);h:MoveTo(root.Position);h.AutoRotate=false;root.Anchored=true
 return true
end
function B.spawn(cf,practice)
 assert(typeof(cf)=='CFrame','Server spawn requires CFrame')
 -- practice: an admin-panel boss (BossPractice: no loot). Callers check the developer first.
 local template=game.ServerStorage.RogueliteNPCs:FindFirstChild('HammerBoss_NPC');if not template then return nil end
 local folder=workspace:FindFirstChild('RogueliteEnemies');if not folder then return nil end
 local npc=template:Clone();npc.Name='HammerBoss';Motion.prepare(npc);npc:PivotTo(cf);npc:SetAttribute('BossPractice',practice==true)
 local root=npc.PrimaryPart;local h=npc.Humanoid;h.WalkSpeed=CHASE_SPEED
 npc:SetAttribute('IsBoss',true);npc:SetAttribute('IsHammerBoss',true);npc:SetAttribute('ZombieType','HammerBoss')
 npc:SetAttribute('ContactDamage',0);npc:SetAttribute('ContactRange',0);npc:SetAttribute('BaseMoveSpeed',h.WalkSpeed)
 for name in Motion.Data.parts do
  local part=npc:FindFirstChild(name)
  if part then part:SetAttribute('BossRest',root.CFrame:ToObjectSpace(part.CFrame)) end
 end
 for _,p in npc:GetDescendants() do if p:IsA('BasePart') then p.Anchored=false end end
 npc.Parent=folder;root:SetNetworkOwner(nil);h.AutoRotate=true
 local s={next=workspace:GetServerTimeNow()+2,index=0,lastHealth=h.Health};B.states[npc]=s
 h.HealthChanged:Connect(function(health)
  if health<s.lastHealth and health>0 and not s.attack then npc:SetAttribute('BossHitStart',workspace:GetServerTimeNow()) end;s.lastHealth=health
 end)
 h.Died:Connect(function() Death.finish(npc) end)
 Tags:AddTag(npc,'RogueliteZombie');Tags:AddTag(npc,'HammerBoss')
 return npc
end
local function damage(npc,s,time)
 local attack=s.attack;local kind=attack.kind;local a=Motion.Attacks[kind]
 if not Motion.active(kind,time) then return end
 local head=Motion.head(attack.cf,kind,time);local center=Motion.head(attack.cf,'Slam',Motion.Attacks.Slam.active).Position
 for _,p in Players:GetPlayers() do
  local char=p.Character;local pr=char and char:FindFirstChild('HumanoidRootPart');local ph=char and char:FindFirstChildOfClass('Humanoid')
  if pr and ph and ph.Health>0 and Characters.states[p] and not attack.hits[p] then
   local hit=Motion.touches(head,pr.Position)
   if kind=='Slam' then local delta=pr.Position-center;hit=Vector2.new(delta.X,delta.Z).Magnitude<=a.radius and math.abs(delta.Y)<=4 end
   if hit and not workspace:Raycast(attack.cf.Position,pr.Position-attack.cf.Position,exclusions(npc)) then
    attack.hits[p]=true -- consume even when armor/dodge/first-hit block prevents damage
    local actual=Characters.contact(p,a.damage)
    npc:SetAttribute('BossHits',(npc:GetAttribute('BossHits') or 0)+1);npc:SetAttribute('LastBossDamage',actual)
   end
  end
 end
end
function B.step(npc,s,now)
 if not npc.Parent then B.states[npc]=nil;return end
 local h=npc.Humanoid;local root=npc.PrimaryPart
 if h.Health<=0 then s.attack=nil;return end
 if combat:GetAttribute('ZombiesEnabled')~=true then
  s.attack=nil;npc:SetAttribute('Attacking',false);npc:SetAttribute('BossStart',nil);root.Anchored=false;h.AutoRotate=true;h:Move(Vector3.zero);return
 end
 if s.attack then
  local attack=s.attack;local age=now-attack.start;local a=Motion.Attacks[attack.kind]
  root.CFrame=attack.cf
  -- Bound catch-up to this attack's short active window, never a stale whole turn.
  local begin=math.max(attack.sampled,a.active);local finish=math.min(age,a.finish)
  if age>=a.active and begin<=finish then
   for time=begin,finish,1/120 do damage(npc,s,time) end
   damage(npc,s,finish)
   if not attack.impact then attack.impact=true;npc:SetAttribute('BossImpactStart',now) end
  end
  attack.sampled=age
  if age>=a.duration then
   s.attack=nil;npc:SetAttribute('Attacking',false);root.Anchored=false;root:SetNetworkOwner(nil);h.AutoRotate=true
  end
  return
 end
 if npc:GetAttribute('BossManual') and Run:IsStudio() then h:Move(Vector3.zero);return end
 -- Admin Freeze: no moving and no new attacks; an attack already under way finishes above.
 if combat:GetAttribute('AdminFreeze')==true then h:Move(Vector3.zero);h:MoveTo(root.Position);return end
 local target,dist=nil,math.huge
 for _,p in Players:GetPlayers() do
  local ch=p.Character;local ph=ch and ch:FindFirstChildOfClass('Humanoid');local pr=ch and ch:FindFirstChild('HumanoidRootPart')
  if ph and ph.Health>0 and pr then local d=(pr.Position-root.Position).Magnitude;if d<dist then target,dist=pr,d end end
 end
 if target then
  local order={'Slam','Swing','Slam','Spin'};local nextIndex=s.index%#order+1
  local preferred=Motion.reach(order[nextIndex])
  if dist<preferred-1.8 then
   local away=Vector3.new(root.Position.X-target.Position.X,0,root.Position.Z-target.Position.Z)
   if away.Magnitude>.1 then h:MoveTo(root.Position+away.Unit*4) end
  elseif dist<=preferred+1.2 and now>=s.next then
   if B.start(npc,order[nextIndex],target) then s.index=nextIndex end
  elseif dist>preferred+1.2 then h:MoveTo(target.Position) else h:Move(Vector3.zero);h:MoveTo(root.Position) end
 else h:Move(Vector3.zero) end
end
Run.Heartbeat:Connect(function() local now=workspace:GetServerTimeNow();for npc,s in B.states do B.step(npc,s,now) end end)
return B
