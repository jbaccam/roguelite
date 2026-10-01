-- Server only: encounter lifecycle, committed poses and substepped hammer damage.
local Players=game:GetService('Players')
local Run=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Motion=require(combat:WaitForChild('BossMotion'))
local Characters=require(script.Parent.CharacterService)
local Death=require(combat.ZombieDeath)
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed; this module is unsandboxed
local Rules=require(game.ReplicatedStorage:WaitForChild('RunSetupRules'))
local B={states={}}
-- Shared with MapBossService (find-or-create); MapBossPresentation throws the player on the client.
local knock=combat:FindFirstChild('MapBossKnockdown') or Instance.new('RemoteEvent')
knock.Name='MapBossKnockdown';knock.Parent=combat
-- Wave chase speed: under the 24 studs/s player base but closing; the charge catches kiters.
local CHASE_SPEED=18
-- Normal, one player; RunSetupRules.bossScale adds difficulty and player count.
local HEALTH=24000
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
 local wasEnabled=combat:GetAttribute('ZombiesEnabled')
 combat:SetAttribute('ZombiesEnabled',true)
 local npc=B.spawn(cf,true)
 if not npc then
  -- Put zombies back as they were: on with no boss and no test-run mark would be a stray wave.
  combat:SetAttribute('ZombiesEnabled',wasEnabled)
  combat:SetAttribute('PracticeBossStatus','Boss template unavailable');return false
 end
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
-- force: no range or sight checks (the slam that ends a charge); it faces the target if one is
-- given, else straight ahead.
function B.start(npc,kind,target,force)
 local s=B.states[npc];local a=Motion.Attacks[kind];local h=npc:FindFirstChildOfClass('Humanoid');local root=npc.PrimaryPart
 if not s or not a or s.attack or h.Health<=0 then return false end
 if not force and (not target or not target.Parent) then return false end
 local delta=target and target.Parent and target.Position-root.Position or root.CFrame.LookVector;local flat=Vector3.new(delta.X,0,delta.Z)
 if not force then
  if flat.Magnitude>Motion.reach(kind)+3 or math.abs(delta.Y)>7 then return false end
  if workspace:Raycast(root.Position,target.Position-root.Position,exclusions(npc)) then return false end
 end
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
-- Charge (Motion.Charge): a player kiting beyond minRange is run down in a straight line, fixed at
-- wind-up, that ends where his front meets them (stepCharge) or short of a wall, then the boss slams.
function B.charge(npc,s,target,now)
 local C=Motion.Charge;local h=npc.Humanoid;local root=npc.PrimaryPart
 local delta=target.Position-root.Position;local flat=Vector3.new(delta.X,0,delta.Z)
 if flat.Magnitude<C.minRange or flat.Magnitude>C.maxRange or math.abs(delta.Y)>10 then return false end
 local params=exclusions(npc)
 if workspace:Raycast(root.Position,delta,params) then return false end
 local dir=flat.Unit;local limit=C.maxLength
 local wall=workspace:Raycast(root.Position,dir*limit,params);if wall then limit=wall.Distance-3 end
 local length=math.min(limit,flat.Magnitude-C.contact)
 if length<8 then return false end
 local ground=workspace:Raycast(root.Position+Vector3.yAxis*8,-Vector3.yAxis*30,params);if not ground then return false end
 local cf=CFrame.lookAt(root.Position,root.Position+dir);root.CFrame=cf
 local run=Motion.duration('ChargeStart')
 s.attack={kind='Charge',start=now,cf=cf,dir=dir,length=length,limit=limit,target=target,run=run,finish=run+length/C.speed+C.brake,travelled=0,hits={}}
 s.nextCharge=now+C.cooldown
 npc:SetAttribute('BossAttack','Charge');npc:SetAttribute('BossStart',now);npc:SetAttribute('BossFrame',cf);npc:SetAttribute('BossGroundY',ground.Position.Y)
 npc:SetAttribute('BossChargeLength',length);npc:SetAttribute('BossChargeSpeed',C.speed)
 npc:SetAttribute('BossSerial',(npc:GetAttribute('BossSerial') or 0)+1);npc:SetAttribute('Attacking',true)
 h:Move(Vector3.zero);h:MoveTo(root.Position);h.AutoRotate=false;root.Anchored=true
 return true
end
local function stepCharge(npc,s,now,root)
 local A,C=s.attack,Motion.Charge;local age=now-A.start
 -- Until he stops, the run ends where his front meets the target, wherever they now are along the
 -- lane: backing away down it doesn't outrun him, stepping out of it dodges (he never turns).
 local pr=A.target
 if not A.stopped and pr.Parent then
  local d=pr.Position-A.cf.Position;local along=d:Dot(A.dir);local side=(Vector3.new(d.X,0,d.Z)-A.dir*along).Magnitude
  if side<=C.halfWidth and math.abs(pr.Position.Y-root.Position.Y)<=7 then
   -- Stop with them inside the body hit, so contact always lands.
   local length=math.clamp(along-math.sqrt(math.max(0,C.contact^2-side^2)),A.travelled,A.limit)
   if math.abs(length-A.length)>.05 then A.length=length;A.finish=A.run+length/C.speed+C.brake;npc:SetAttribute('BossChargeLength',length) end
  end
 end
 local travelled=math.clamp((age-A.run)*C.speed,0,A.length)
 if travelled>=A.length then A.stopped=true end
 if travelled>A.travelled then
  local from=A.cf.Position+A.dir*A.travelled;local to=A.cf.Position+A.dir*travelled
  local params=exclusions(npc)
  -- Follow the floor so a slope doesn't leave him floating or buried.
  local floor=workspace:Raycast(to+Vector3.yAxis*6,-Vector3.yAxis*(Motion.RootHeight+14),params)
  if floor then to=Vector3.new(to.X,floor.Position.Y+Motion.RootHeight+.1,to.Z) end
  root.CFrame=CFrame.lookAt(to,to+A.dir)
  local a2,b2=Vector2.new(from.X,from.Z),Vector2.new(to.X,to.Z);local ab=b2-a2
  for _,p in Players:GetPlayers() do
   local char=p.Character;local pr=char and char:FindFirstChild('HumanoidRootPart');local ph=char and char:FindFirstChildOfClass('Humanoid')
   if pr and ph and ph.Health>0 and Characters.states[p] and not A.hits[p] and math.abs(pr.Position.Y-to.Y)<=7 then
    local q=Vector2.new(pr.Position.X,pr.Position.Z);local t=math.clamp((q-a2):Dot(ab)/math.max(ab:Dot(ab),1e-6),0,1)
    if (q-(a2+ab*t)).Magnitude<=C.halfWidth then
     A.hits[p]=true
     local actual=Characters.contact(p,C.damage*(npc:GetAttribute('BossDamageScale') or 1))
     npc:SetAttribute('BossHits',(npc:GetAttribute('BossHits') or 0)+1);npc:SetAttribute('LastBossDamage',actual)
     if actual>0 then knock:FireClient(p,to-A.dir*2,C.knockdown) end
    end
   end
  end
  A.travelled=travelled
 end
 if age>=A.finish then
  -- After the brake, a slam at the stopping point, facing whoever is nearest if in reach.
  s.attack=nil;npc:SetAttribute('Attacking',false)
  local target,dist=nil,Motion.reach('Slam')+3
  for _,p in Players:GetPlayers() do
   local pr=p.Character and p.Character:FindFirstChild('HumanoidRootPart')
   if pr then local d=(pr.Position-root.Position).Magnitude;if d<dist then target,dist=pr,d end end
  end
  if not B.start(npc,'Slam',target,true) then root.Anchored=false;npc.Humanoid.AutoRotate=true end
 end
end
function B.spawn(cf,practice)
 assert(typeof(cf)=='CFrame','Server spawn requires CFrame')
 -- practice: an admin-panel boss (BossPractice: no loot). Callers check the developer first.
 local template=game.ServerStorage.RogueliteNPCs:FindFirstChild('HammerBoss_NPC');if not template then return nil end
 local folder=workspace:FindFirstChild('RogueliteEnemies');if not folder then return nil end
 local npc=template:Clone();npc.Name='HammerBoss';Motion.prepare(npc);npc:PivotTo(cf);npc:SetAttribute('BossPractice',practice==true)
 local root=npc.PrimaryPart;local h=npc.Humanoid;h.WalkSpeed=CHASE_SPEED
 local hpScale,damageScale=Rules.bossScale(combat:GetAttribute('RunDifficulty'),#Players:GetPlayers())
 h.MaxHealth=math.ceil(HEALTH*hpScale);h.Health=h.MaxHealth;npc:SetAttribute('BossDamageScale',damageScale)
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
   local hit=Motion.touches(head,pr.Position) or Motion.sweeps(attack.cf.Position,head.Position,pr.Position)
   -- Slam: a ground shock disc; a normal jump (about 5 studs up) doesn't clear it.
   if kind=='Slam' then local delta=pr.Position-center;hit=Vector2.new(delta.X,delta.Z).Magnitude<=a.radius and math.abs(delta.Y)<=6 end
   if hit and not workspace:Raycast(attack.cf.Position,pr.Position-attack.cf.Position,exclusions(npc)) then
    attack.hits[p]=true -- consume even when armor/dodge/first-hit block prevents damage
    local actual=Characters.contact(p,a.damage*(npc:GetAttribute('BossDamageScale') or 1))
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
 if s.attack and s.attack.kind=='Charge' then stepCharge(npc,s,now,root);return end
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
  -- Out of reach and kiting: run them down (Motion.Charge), on its own cooldown.
  if Motion.hasCharge and now>=s.next and now>=(s.nextCharge or 0) and B.charge(npc,s,target,now) then return end
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
