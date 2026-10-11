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
-- Latest feedback: modestly faster walking chase; ordinary zombies are slower separately.
local CHASE_SPEED=24
-- Normal, one player; RunSetupRules.bossScale adds difficulty and player count.
local HEALTH=18000 -- 24000 until 2026-10-01: a balanced wave-20 build took 60-115 s; now ~45-90 s
-- Seconds between hit flinches (BossPresentation plays one only while he stands).
local FLINCH_GAP=2
-- Super-jump entrance (2026-10-03): a wave boss (not an admin/practice one) drops in from the
-- sky and lands hammer-first. drop: seconds of rumble and growing shadow before he falls; fall:
-- the fall; after: the landing and the camera orbit (BossIntro.client). Until BossIntroUntil he
-- can't be hurt (CombatEffectsService) and stands still, and CinematicUntil holds the players
-- (CharacterService.frozen) and the enemies (RogueliteZombieChase).
B.INTRO={drop=1.2,fall=.65,after=3.6}
local lastPracticeRequest=-math.huge
-- The map-boss Hammer (R9, 2026-10-04): MapBossService, once this place can run him there
-- (MapBossDefs.ready('Hammer'): his def, timing, clips, Hammer_NPC and the runtime); nil until then,
-- or if those modules fail to load, and the old Hammer spawns as before. Required on first use, never
-- at load, so this module never waits on the map-boss modules.
local function mapHammer()
 local defs=combat:FindFirstChild('MapBossDefs');local service=game:GetService('ServerScriptService'):FindFirstChild('MapBossService')
 if not defs or not service then return nil end
 local ok,result=pcall(function() local D=require(defs);return D.ready and D.ready('Hammer') and require(service) or nil end)
 if not ok then warn('BossService: map-boss Hammer unavailable: '..tostring(result)) end
 return ok and result or nil
end
-- The admin panel's Spawn boss / Remove boss (CharacterService.onPracticeBoss).
function B.practice(player,action)
 -- Developers only (the admin panel), in Studio and on live servers; CharacterService checks too.
 if not Admin.isAdmin(player) or (action~='SpawnBoss' and action~='RemoveBoss') then return false end
 -- The map-boss Hammer when he is ready: MapBossService.practice makes the same checks and spawns him
 -- 20 studs ahead, no rewards. Remove boss below takes either Hammer. If his spawn throws, no
 -- half-built one is left (nor zombies switched on by it), the status says why, and the old Hammer
 -- spawns below instead.
 local map=action=='SpawnBoss' and mapHammer();local failed
 if map then
  local wasEnabled=combat:GetAttribute('ZombiesEnabled')
  local ok,result=pcall(map.practice,player,'Hammer')
  if ok then return result end
  failed=tostring(result);warn('BossService: map-boss Hammer practice spawn failed, the old Hammer instead: '..failed)
  local enemies=workspace:FindFirstChild('RogueliteEnemies')
  for _,npc in enemies and enemies:GetChildren() or {} do if npc:GetAttribute('MapBossId')=='Hammer' and npc:GetAttribute('BossPractice') then npc:Destroy() end end
  combat:SetAttribute('ZombiesEnabled',wasEnabled)
  combat:SetAttribute('PracticeBossStatus','Map-boss Hammer failed: '..failed)
 end
 local ch=player.Character;local h=ch and ch:FindFirstChildOfClass('Humanoid');local root=ch and ch:FindFirstChild('HumanoidRootPart')
 local folder=workspace:FindFirstChild('RogueliteEnemies')
 if not Characters.states[player] or not h or h.Health<=0 or not root or not folder or os.clock()-lastPracticeRequest<.5 then return false end
 local phase=game.ReplicatedStorage:FindFirstChild('RogueliteRunState')
 if phase and not table.find({'Shop','Combat','Practice'},phase:GetAttribute('Phase')) then return false end
 lastPracticeRequest=os.clock()
 if action=='RemoveBoss' then
  -- A practice Hammer, old or map-boss (MapBossId 'Hammer').
  for _,npc in folder:GetChildren() do if (npc:GetAttribute('IsHammerBoss') or npc:GetAttribute('MapBossId')=='Hammer') and npc:GetAttribute('BossPractice') then npc:Destroy() end end
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
 combat:SetAttribute('PracticeBossStatus',failed and 'Old Hammer instead (map-boss Hammer failed: '..failed..')' or 'Practice boss active · no rewards')
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
 npc:SetAttribute('BossChargeWarningLength',limit) -- warn every point this run can reach before wind-up ends
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
   local at=pr and Characters.seen(p,pr) -- where their screen has them (CharacterService.seen)
   if pr and ph and ph.Health>0 and Characters.states[p] and not A.hits[p] and math.abs(at.Y-to.Y)<=7 then
    local q=Vector2.new(at.X,at.Z);local t=math.clamp((q-a2):Dot(ab)/math.max(ab:Dot(ab),1e-6),0,1)
    if (q-(a2+ab*t)).Magnitude<=C.halfWidth then
     A.hits[p]=true
     local actual=Characters.contact(p,C.damage*(npc:GetAttribute('BossDamageScale') or 1))
     if Run:IsStudio() then npc:SetAttribute('BossHits',(npc:GetAttribute('BossHits') or 0)+1);npc:SetAttribute('LastBossDamage',actual) end -- QA only (hammer-boss/test_heavy_studio): live servers don't replicate them (audit P12)
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
  -- A missed run already paid its warning and brake. Slamming empty ground forced another
  -- 1.67 seconds of standing still and let a fleeing player erase the entire gap closure.
  if not target or not B.start(npc,'Slam',target,true) then
   root.Anchored=false;npc.Humanoid.AutoRotate=true;npc:SetAttribute('BossStart',nil)
  end
 end
end
function B.spawn(cf,practice)
 assert(typeof(cf)=='CFrame','Server spawn requires CFrame')
 -- practice: an admin-panel boss (BossPractice: no loot). Callers check the developer first.
 local template=game.ServerStorage.RogueliteNPCs:FindFirstChild('HammerBoss_NPC');if not template then return nil end
 local folder=workspace:FindFirstChild('RogueliteEnemies');if not folder then return nil end
 if not practice then
  -- A wave boss lands facing the nearest run member: BossEncounter's spot has no facing, so he
  -- fell facing world -Z, away from the map's spawn (user, 2026-10-03).
  local near,best=nil,math.huge
  for _,p in Players:GetPlayers() do
   local r=p:GetAttribute('RunMember') and p.Character and p.Character:FindFirstChild('HumanoidRootPart')
   if r then local d=(r.Position-cf.Position).Magnitude;if d<best then near,best=r,d end end
  end
  local to=near and Vector3.new(near.Position.X,cf.Position.Y,near.Position.Z)
  if to and (to-cf.Position).Magnitude>.5 then cf=CFrame.lookAt(cf.Position,to) end
 end
 local npc=template:Clone();npc.Name='HammerBoss';Motion.prepare(npc);npc:PivotTo(cf);npc:SetAttribute('BossPractice',practice==true)
 local root=npc.PrimaryPart;local h=npc.Humanoid;h.WalkSpeed=CHASE_SPEED
 -- Only run members count (ShopService RunMember): players in the lobby don't toughen the boss.
 local members=0;for _,p in Players:GetPlayers() do if p:GetAttribute('RunMember') then members+=1 end end
 local hpScale,damageScale=Rules.bossScale(combat:GetAttribute('RunDifficulty'),math.max(1,members))
 -- The tutorial's boss (TutorialDirector sets TutorialBossHealth) has a fixed, small health.
 local fixed=not practice and combat:GetAttribute('TutorialBossHealth')
 h.MaxHealth=type(fixed)=='number' and fixed or math.ceil(HEALTH*hpScale);h.Health=h.MaxHealth;npc:SetAttribute('BossDamageScale',damageScale)
 npc:SetAttribute('IsBoss',true);npc:SetAttribute('IsHammerBoss',true);npc:SetAttribute('ZombieType','HammerBoss')
 -- The player-facing name (intro card, boss bar): Hammer Brute everywhere (user, 2026-10-05).
 npc:SetAttribute('BossName','Hammer Brute')
 npc:SetAttribute('ContactDamage',0);npc:SetAttribute('ContactRange',0);npc:SetAttribute('BaseMoveSpeed',h.WalkSpeed)
 for name in Motion.Data.parts do
  local part=npc:FindFirstChild(name)
  if part then part:SetAttribute('BossRest',root.CFrame:ToObjectSpace(part.CFrame)) end
 end
 for _,p in npc:GetDescendants() do if p:IsA('BasePart') then p.Anchored=false end end
 npc.Parent=folder;root:SetNetworkOwner(nil);h.AutoRotate=true
 local s={next=workspace:GetServerTimeNow()+2,index=0,lastHealth=h.Health};B.states[npc]=s
 if not practice then
  -- The entrance (B.INTRO): his Slam clip is timed so the hammer hits the ground as he lands;
  -- it deals no damage (no s.attack). He stays anchored where he lands until it's over.
  local now=workspace:GetServerTimeNow();local I=B.INTRO
  local land=now+I.drop+I.fall;local done=land+I.after
  npc:SetAttribute('BossIntroStart',now);npc:SetAttribute('BossIntroLand',land);npc:SetAttribute('BossIntroUntil',done)
  npc:SetAttribute('BossAttack','Slam');npc:SetAttribute('BossStart',land-Motion.Attacks.Slam.active);npc:SetAttribute('BossFrame',root.CFrame)
  npc:SetAttribute('BossGroundY',root.Position.Y-Motion.RootHeight-.1)
  npc:SetAttribute('BossSerial',(npc:GetAttribute('BossSerial') or 0)+1);npc:SetAttribute('Attacking',true)
  root.Anchored=true;h.AutoRotate=false
  s.intro=done;s.next=done+.6
  combat:SetAttribute('CinematicUntil',done)
 end
 -- One flinch per FLINCH_GAP: six weapons hitting every few frames restarted it on its first frame,
 -- so he froze in that pose while he kept walking (slid) into his next attack.
 h.HealthChanged:Connect(function(health)
  local now=workspace:GetServerTimeNow()
  if health<s.lastHealth and health>0 and not s.attack and now-(npc:GetAttribute('BossHitStart') or -math.huge)>=FLINCH_GAP then npc:SetAttribute('BossHitStart',now) end;s.lastHealth=health
 end)
 h.Died:Connect(function() Death.finish(npc) end)
 Tags:AddTag(npc,'RogueliteZombie');Tags:AddTag(npc,'HammerBoss')
 -- Boss arrival i-frames for the whole run (CharacterStats.BossArrival), after the entrance above.
 if Characters.bossArrived then pcall(Characters.bossArrived) end
 return npc
end
local function damage(npc,s,time)
 local attack=s.attack;local kind=attack.kind;local a=Motion.Attacks[kind]
 if not Motion.active(kind,time) then return end
 local head=Motion.head(attack.cf,kind,time);local center=Motion.head(attack.cf,'Slam',Motion.Attacks.Slam.active).Position
 for _,p in Players:GetPlayers() do
  local char=p.Character;local pr=char and char:FindFirstChild('HumanoidRootPart');local ph=char and char:FindFirstChildOfClass('Humanoid')
  if pr and ph and ph.Health>0 and Characters.states[p] and not attack.hits[p] then
   local at=Characters.seen(p,pr) -- where their screen has them (CharacterService.seen)
   local hit=Motion.touches(head,at) or Motion.sweeps(attack.cf.Position,head.Position,at)
   -- Slam: a ground shock disc; a normal jump (about 5 studs up) doesn't clear it.
   if kind=='Slam' then local delta=at-center;hit=Vector2.new(delta.X,delta.Z).Magnitude<=a.radius and math.abs(delta.Y)<=6 end
   if hit and not workspace:Raycast(attack.cf.Position,pr.Position-attack.cf.Position,exclusions(npc)) then
    attack.hits[p]=true -- consume even when armor/dodge/first-hit block prevents damage
    local actual=Characters.contact(p,a.damage*(npc:GetAttribute('BossDamageScale') or 1))
    if Run:IsStudio() then npc:SetAttribute('BossHits',(npc:GetAttribute('BossHits') or 0)+1);npc:SetAttribute('LastBossDamage',actual) end -- QA only (hammer-boss/test_heavy_studio): live servers don't replicate them (audit P12)
   end
  end
 end
end
function B.step(npc,s,now)
 if not npc.Parent then B.states[npc]=nil;return end
 local h=npc.Humanoid;local root=npc.PrimaryPart
 if h.Health<=0 then s.attack=nil;return end
 -- The super-jump entrance (B.INTRO): stand still until it's over, then fight.
 if s.intro then
  if now<s.intro then h:Move(Vector3.zero);return end
  s.intro=nil;npc:SetAttribute('Attacking',false);npc:SetAttribute('BossStart',nil)
  root.Anchored=false;root:SetNetworkOwner(nil);h.AutoRotate=true
 end
 if combat:GetAttribute('ZombiesEnabled')~=true then
  s.attack=nil;npc:SetAttribute('Attacking',false);npc:SetAttribute('BossStart',nil);root.Anchored=false;h.AutoRotate=true;h:Move(Vector3.zero);return
 end
 -- Pause (plan L): a paused run cancels the swing or charge under way and holds still.
 if combat:GetAttribute('RunPaused')==true then
  if s.attack then s.attack=nil;npc:SetAttribute('Attacking',false);npc:SetAttribute('BossStart',nil);root.Anchored=false;root:SetNetworkOwner(nil);h.AutoRotate=true end
  h:Move(Vector3.zero);h:MoveTo(root.Position);return
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
  if dist<=preferred+1.2 then
   -- A melee player who closes has earned a damage window. Hold ground instead
   -- of backing away faster than their walk; attacks keep their normal wind-up,
   -- cooldown, wall/height validation and authored damage volumes.
   h:Move(Vector3.zero);h:MoveTo(root.Position)
   if now>=s.next and B.start(npc,order[nextIndex],target) then s.index=nextIndex end
  else h:MoveTo(target.Position) end
 else h:Move(Vector3.zero) end
end
Run.Heartbeat:Connect(function() local now=workspace:GetServerTimeNow();for npc,s in B.states do B.step(npc,s,now) end end)
return B
