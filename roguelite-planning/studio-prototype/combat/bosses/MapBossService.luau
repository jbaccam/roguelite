-- Server only: the four map bosses (plan F), driven by MapBossDefs and the generated
-- MapBossTiming. Mirrors the Hammer BossService: server-owned attacks, the root pinned during an
-- attack, and hit tests substepped inside each attack's active window. Every hit shape comes
-- from MapBossShapes, the same tables the client draws as ground warnings.
local Players=game:GetService('Players')
local Run=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local Http=game:GetService('HttpService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Shapes=require(combat:WaitForChild('MapBossShapes'))
local flat=Shapes.flat
local M={states={}}

-- Pure shape builders (M._shapes). Attack timing `at` is a MapBossTiming attack entry; points
-- are ground-frame studs (plan F Coordinates). Shapes lie on the attack's ground height.
local X={}
M._shapes=X
local function v3(t) return Vector3.new(t[1],t[2],t[3]) end
function X.frame(cf,T,groundY) local g=cf*CFrame.new(0,-T.rootHeight,0);return {cf=cf,ground=g,groundY=groundY or g.Y} end
-- A named point at clip time t: its sampled track, else the authored impact point.
function X.localPoint(at,name,t)
 local p=Shapes.sample(at.samples and at.samples[name],t);if p then return p end
 local fixed=at.points and at.points[name];return fixed and v3(fixed.rootAtImpactStudio) or Vector3.zero
end
function X.localDir(at,name,t)
 return Shapes.sample(at.dirs and at.dirs[name],t) or (at.directionAtImpactStudio and v3(at.directionAtImpactStudio)) or nil
end
function X.point(f,at,name,t) return f.ground*X.localPoint(at,name,t) end
function X.onGround(f,p) return Vector3.new(p.X,f.groundY,p.Z) end
-- Ground-frame direction -> flat world unit vector; the boss's facing when missing or vertical.
function X.flatDir(f,d)
 local look=flat(f.cf.LookVector).Unit;if not d then return look end
 d=flat(f.ground:VectorToWorldSpace(d));return d.Magnitude>.05 and d.Unit or look
end
function X.window(def,T,length)
 if def.clips then -- the crab's rush: RushStart, travel at `speed`, RushEnd (clips played at def.rate)
  local c=T.clips or {};local rate=def.rate or 1;local rs,re=c[def.clips[1]],c[def.clips[3]];if not rs or not re then return nil end
  rs,re=rs/rate,re/rate;local move=(length or def.length)/def.speed
  return {warnStart=0,impact=rs,activeEnd=rs+move,recoveryEnd=rs+move+re,duration=rs+move+re}
 end
 return T.attacks and T.attacks[def.clip]
end
-- When the boss may act again: recovery, stretched to cover delayed hits (wave travel, eruptions).
function X.duration(def,at)
 local d=at.recoveryEnd or at.duration
 if def.shape=='wave' then d=math.max(d,at.impact+def.length/def.travel+.05)
 elseif def.shape=='targets' then d=math.max(d,at.impact+def.eruptDelay+.05) end
 return d
end
function X.circle(def,at,f) return {kind='circle',center=X.onGround(f,X.point(f,at,def.point,at.impact)),radius=def.radius} end
function X.wave(def,at,f,yaw)
 local d=at.directionAtImpactStudio and v3(at.directionAtImpactStudio);local dir=X.flatDir(f,d)
 if yaw and yaw~=0 then dir=CFrame.Angles(0,yaw,0):VectorToWorldSpace(dir) end
 return {kind='line',origin=X.onGround(f,X.point(f,at,def.point,at.impact)),direction=dir,length=def.length,width=def.width}
end
-- Turns cf's facing toward goal by at most maxTurn radians about +Y (the breath's tracking).
function X.turnToward(cf,goal,maxTurn)
 local d=flat(goal-cf.Position);if d.Magnitude<.1 then return cf end
 local a=math.clamp(Shapes.yaw(cf.LookVector,d),-maxTurn,maxTurn)
 return CFrame.new(cf.Position)*CFrame.Angles(0,a,0)*cf.Rotation
end
-- Follow-up circle spots: one under each target, plus `extra` more 7-11 studs round each (seeded).
function X.followSpots(targets,extra,cap,rng)
 local list={}
 for _,p in targets do if #list<cap then table.insert(list,p) end end
 for _,p in targets do
  for _=1,extra do
   if #list>=cap then break end
   local a=rng:NextNumber()*math.pi*2;table.insert(list,p+Vector3.new(math.cos(a),0,math.sin(a))*rng:NextNumber(7,11))
  end
 end
 return list
end
-- The wave front reaches along-distance d at impact + d/travel; true when that time is in (t0, t1].
function X.waveHit(def,at,line,pos,t0,t1)
 if not Shapes.contains(line,pos) then return false end
 local t=at.impact+flat(pos-line.origin):Dot(line.direction)/def.travel;return t>t0 and t<=t1
end
-- Side-on facing, with the target on its +X or -X (whichever is the smaller turn); X.lane of
-- that facing is then the lane through the target.
function X.laneFacing(pos,target,look)
 local d=flat(target-pos);if d.Magnitude<.1 then return CFrame.lookAt(pos,pos+flat(look)) end
 local side=Vector3.yAxis:Cross(d.Unit);if side:Dot(look)<0 then side=-side end
 return CFrame.lookAt(pos,pos+side)
end
function X.lane(cf,target) local r=flat(cf.RightVector).Unit;return flat(target-cf.Position):Dot(r)>=0 and r or -r end
-- Warning rectangle over the body's swept capsule (half a width past each end).
function X.laneShape(f,dir,length,width) return {kind='line',origin=X.onGround(f,f.cf.Position)-dir*width/2,direction=dir,length=length+width,width=width} end
function X.cone(def,at,f,t) return {kind='cone',origin=X.onGround(f,X.point(f,at,def.point,t)),direction=X.flatDir(f,X.localDir(at,def.point,t)),halfAngle=def.halfAngle,length=def.length} end
function X.sweep(def,at,f,t) return {kind='capsule',a=X.onGround(f,X.point(f,at,def.mid,t)),b=X.onGround(f,X.point(f,at,def.point,t)),radius=def.radius} end
-- Warning arc over the tail's active path. Yaw is unwrapped sample to sample, then centred, so a
-- sweep across the boss's back never wraps into the front.
function X.sweepArc(def,at,f)
 local pivot=X.onGround(f,f.cf.Position);local first,last,angle,lo,hi,near,far
 local steps=math.max(1,math.ceil((at.activeEnd-at.impact)*60))
 for i=0,steps do
  local t=at.impact+(at.activeEnd-at.impact)*i/steps
  local tip=flat(X.point(f,at,def.point,t)-pivot);local mid=flat(X.point(f,at,def.mid,t)-pivot)
  if not first then first=tip.Magnitude>.05 and tip.Unit or flat(f.cf.LookVector).Unit;angle=Shapes.yaw(first,tip);lo,hi,near,far=angle,angle,math.huge,0
  else angle+=Shapes.yaw(last,tip);lo,hi=math.min(lo,angle),math.max(hi,angle) end
  last=tip;near=math.min(near,mid.Magnitude,tip.Magnitude);far=math.max(far,mid.Magnitude,tip.Magnitude)
 end
 local pad=def.radius/math.max(far,1);local half=(hi-lo)/2+pad
 return {kind='arc',pivot=pivot,forward=CFrame.Angles(0,(lo+hi)/2,0):VectorToWorldSpace(first),from=-half,to=half,inner=math.max(0,near-def.radius),outer=far+def.radius}
end
-- Evenly spread projectile yaws (0 = world -Z) across +-spread/2 about a flat direction.
function X.yaws(def,dir)
 local base=Shapes.yaw(Vector3.new(0,0,-1),dir);local list={}
 for i=1,def.count do list[i]=base+(def.count>1 and def.spread*((i-1)/(def.count-1)-.5) or 0) end
 return list
end

-- Edit-mode test requires stop here: the services and the Heartbeat load on a running server only.
if not (Run:IsServer() and Run:IsRunning()) then return M end
local Defs=require(combat:WaitForChild('MapBossDefs'))
local Characters=require(script.Parent.CharacterService)
local Death=require(combat.ZombieDeath)
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed; this module is unsandboxed
local knock=combat:FindFirstChild('MapBossKnockdown') or Instance.new('RemoteEvent')
knock.Name='MapBossKnockdown';knock.Parent=combat
local MOUTH_AIMED={BubbleBarrage=true} -- fanned about the mouth's own direction, not the target
local function exclusions(npc)
 local list={npc}
 for _,name in {'RogueliteEnemies','MapBossPreview','HammerBossReview'} do local f=workspace:FindFirstChild(name);if f then table.insert(list,f) end end
 for _,p in Players:GetPlayers() do if p.Character then table.insert(list,p.Character) end end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=list;return params
end
local function living()
 local list={}
 for _,p in Players:GetPlayers() do
  local ch=p.Character;local pr=ch and ch:FindFirstChild('HumanoidRootPart');local ph=ch and ch:FindFirstChildOfClass('Humanoid')
  if pr and ph and ph.Health>0 and Characters.states[p] then table.insert(list,{player=p,root=pr}) end
 end
 return list
end
-- One hit: line of sight from `from`, then CharacterService applies armor, dodge and blocks.
local function hit(npc,def,e,from,params,source)
 if workspace:Raycast(from,e.root.Position-from,params) then return false end
 local actual=Characters.contact(e.player,def.damage)
 npc:SetAttribute('BossHits',(npc:GetAttribute('BossHits') or 0)+1);npc:SetAttribute('LastBossDamage',actual)
 if def.knockdown and actual>0 then knock:FireClient(e.player,source,def.knockdown) end
 return true
end
local function publish(npc,A) npc:SetAttribute('MapBossAttackData',Http:JSONEncode(A.data)) end
local function segmentDistance(a,b,p) local ab=b-a;local t=math.clamp((p-a):Dot(ab)/math.max(ab:Dot(ab),1e-6),0,1);return (a+ab*t-p).Magnitude end
function M.start(npc,kind,target,force)
 local s=M.states[npc];local def=s and s.def.attacks[kind];local h=npc:FindFirstChildOfClass('Humanoid');local root=npc.PrimaryPart
 if not def or s.attack or not h or h.Health<=0 or not root or not X.window(def,s.T) then return false end
 local goal=target and target.Parent and target.Position or root.Position+root.CFrame.LookVector*12
 local delta=goal-root.Position;local params=exclusions(npc)
 if not force and (not target or math.abs(delta.Y)>10 or workspace:Raycast(root.Position,delta,params)) then return false end
 local laneDir
 if def.shape=='lane' then
  -- The lane is the side the target is on once the crab stands side-on to it, so it runs through
  -- the target. The root then faces along the lane: RushStart turns the body so its right side
  -- leads, and RushLoop travels along the model's forward.
  laneDir=X.lane(X.laneFacing(root.Position,goal,root.CFrame.LookVector),goal);root.CFrame=CFrame.lookAt(root.Position,root.Position+laneDir)
 elseif flat(delta).Magnitude>.1 then root.CFrame=CFrame.lookAt(root.Position,root.Position+flat(delta)) end
 local ground=workspace:Raycast(root.Position+Vector3.yAxis*8,-Vector3.yAxis*(s.T.rootHeight+30),params)
 if not ground then return false end
 local now=workspace:GetServerTimeNow();local cf=root.CFrame;local f=X.frame(cf,s.T,ground.Position.Y)
 local A={kind=kind,def=def,start=now,cf=cf,ground=f.groundY,frame=f,hits={},ticks={},sampled=0,data={}}
 if def.shape=='lane' then
  -- Clamped short of a wall at body height; the body travels at `speed` after RushStart.
  A.dir=laneDir;local wall=workspace:Raycast(cf.Position,A.dir*def.length,params)
  A.length=wall and math.max(0,wall.Distance-math.min(8,s.T.footprintRadius or 4)/2-1) or def.length;A.travelled=0
  A.data={dir={A.dir.X,A.dir.Z},length=A.length,shape=Shapes.encode(X.laneShape(f,A.dir,A.length,def.width))}
 end
 A.at=X.window(def,s.T,A.length);local at=A.at;A.duration=X.duration(def,at)
 local rage=s.enraged and s.def.enrage or {}
 if def.shape=='circle' then A.data.shape=Shapes.encode(X.circle(def,at,f))
 elseif def.shape=='wave' then
  -- Enraged, the wave splits into a fan (rage.fan, degrees). Hits test every line; data.shape
  -- (the middle line) is kept for older readers, and the client warns and draws data.lines.
  A.lines={};A.data.lines={}
  for _,deg in rage.fan or {0} do local line=X.wave(def,at,f,math.rad(deg));table.insert(A.lines,line);table.insert(A.data.lines,Shapes.encode(line)) end
  A.line=A.lines[math.ceil(#A.lines/2)];A.data.shape=Shapes.encode(A.line)
 elseif def.shape=='breath' then A.data.shape=Shapes.encode(X.cone(def,at,f,at.impact))
 elseif def.shape=='sweep' then A.data.shape=Shapes.encode(X.sweepArc(def,at,f))
 elseif def.shape=='projectiles' then
  local origin=X.point(f,at,def.point,at.impact);local aim=flat(goal-origin)
  local dir=MOUTH_AIMED[kind] and X.flatDir(f,X.localDir(at,def.point,at.impact)) or (aim.Magnitude>.1 and aim.Unit or flat(cf.LookVector).Unit)
  -- Enraged: rage.extra more shots, the fan widened to keep the same gap between them.
  local count=def.count+(rage.extra or 0);local fan={count=count,spread=def.count>1 and def.spread*(count-1)/(def.count-1) or def.spread}
  A.data={origin={origin.X,origin.Y,origin.Z},yaws=X.yaws(fan,dir),height=f.groundY+math.clamp(origin.Y-f.groundY,1.5,3.5),speed=def.speed,life=def.life,radius=def.radius}
 end
 A.data.rate=def.rate or 1
 s.attack=A
 npc:SetAttribute('BossAttack',kind);npc:SetAttribute('BossStart',now);npc:SetAttribute('BossFrame',cf);npc:SetAttribute('BossGroundY',f.groundY);npc:SetAttribute('BossDuration',A.duration)
 publish(npc,A);npc:SetAttribute('BossSerial',(npc:GetAttribute('BossSerial') or 0)+1);npc:SetAttribute('Attacking',true)
 h:Move(Vector3.zero);h:MoveTo(root.Position);h.AutoRotate=false;root.Anchored=true
 return true
end
function M.spawn(id,cf,practice)
 assert(typeof(cf)=='CFrame','Server spawn requires CFrame')
 -- practice: an admin-panel boss (BossPractice: no loot). Callers check the developer first.
 local def,T=Defs.get(id),Defs.timing(id);if not def or not T then return nil end
 local template=game.ServerStorage.RogueliteNPCs:FindFirstChild(id..'_NPC');if not template then return nil end
 local folder=workspace:FindFirstChild('RogueliteEnemies');if not folder then return nil end
 local npc=template:Clone();npc.Name=id
 -- The template is at authored size; def.scale grows it about its pivot (the HumanoidRootPart),
 -- which is then placed at cf. EnemyBaselineModelScale stays the template's, so the client scales
 -- the clips' translations by the same factor.
 local scale=def.scale or 1
 if scale~=1 then npc:ScaleTo(npc:GetScale()*scale) end
 npc:PivotTo(cf);npc:SetAttribute('BossPractice',practice==true)
 local root=npc.PrimaryPart;local h=npc:FindFirstChildOfClass('Humanoid')
 if not root or not h then npc:Destroy();return nil end
 h.HipHeight=math.max(0,T.rootHeight-root.Size.Y*.5)
 h.MaxHealth=def.health;h.Health=def.health;h.WalkSpeed=def.chaseSpeed
 npc:SetAttribute('BossSpawnedAt',workspace:GetServerTimeNow())
 npc:SetAttribute('IsBoss',true);npc:SetAttribute('IsMapBoss',true);npc:SetAttribute('MapBossId',id);npc:SetAttribute('BossName',def.name);npc:SetAttribute('ZombieType',id)
 npc:SetAttribute('ContactDamage',0);npc:SetAttribute('ContactRange',0);npc:SetAttribute('BaseMoveSpeed',h.WalkSpeed)
 if not npc:GetAttribute('BossDeathSeconds') and T.clips and T.clips.Death then npc:SetAttribute('BossDeathSeconds',T.clips.Death+.6) end
 for _,p in npc:GetDescendants() do if p:IsA('BasePart') then p.Anchored=false end end
 npc.Parent=folder;root:SetNetworkOwner(nil);h.AutoRotate=true
 local s={id=id,def=def,T=T,next=workspace:GetServerTimeNow()+Defs.FIRST_ATTACK,index=0,lastHealth=h.Health,stop=math.min(8*scale,T.footprintRadius or 4)+3,follows={},followSerial=0};M.states[npc]=s
 h.HealthChanged:Connect(function(health)
  if health<s.lastHealth and health>0 and not s.attack then npc:SetAttribute('BossHitStart',workspace:GetServerTimeNow()) end;s.lastHealth=health
 end)
 h.Died:Connect(function() Death.finish(npc) end)
 Tags:AddTag(npc,'RogueliteZombie');Tags:AddTag(npc,'MapBoss')
 return npc
end
local lastPracticeRequest=-math.huge
-- Admin-panel practice boss, the same rules as BossService.practice: 20 studs ahead on open ground.
function M.practice(player,id)
 local def,T=Defs.get(id),Defs.timing(id)
 if not Admin.isAdmin(player) or not def or not T then return false end
 local ch=player.Character;local h=ch and ch:FindFirstChildOfClass('Humanoid');local root=ch and ch:FindFirstChild('HumanoidRootPart')
 local folder=workspace:FindFirstChild('RogueliteEnemies')
 if not Characters.states[player] or not h or h.Health<=0 or not root or not folder or os.clock()-lastPracticeRequest<.5 then return false end
 local phase=game.ReplicatedStorage:FindFirstChild('RogueliteRunState')
 if phase and not table.find({'Shop','Combat','Practice'},phase:GetAttribute('Phase')) then return false end
 lastPracticeRequest=os.clock()
 for _,npc in folder:GetChildren() do
  if npc:GetAttribute('IsBoss') then combat:SetAttribute('PracticeBossStatus','A boss is already present');return false end
 end
 local exclude={folder,ch}
 for _,p in Players:GetPlayers() do if p.Character then table.insert(exclude,p.Character) end end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=exclude
 local look=Vector3.new(root.CFrame.LookVector.X,0,root.CFrame.LookVector.Z)
 if look.Magnitude<.1 then look=Vector3.new(0,0,-1) else look=look.Unit end
 local size,height=math.min(16,(T.footprintRadius or 4)*2),T.height or 10
 local cf
 for _,angle in {0,45,-45,90,-90,180} do
  local direction=CFrame.Angles(0,math.rad(angle),0):VectorToWorldSpace(look)
  local at=root.Position+direction*20
  local floor=workspace:Raycast(at+Vector3.yAxis*16,-Vector3.yAxis*48,params)
  if floor and floor.Normal.Y>.8 and not workspace:Raycast(root.Position,direction*20,params) then
   local pos=floor.Position+Vector3.yAxis*(T.rootHeight+.1)
   local overlap=OverlapParams.new();overlap.FilterType=Enum.RaycastFilterType.Exclude;overlap.FilterDescendantsInstances=exclude;overlap.RespectCanCollide=true
   if #workspace:GetPartBoundsInBox(CFrame.new(floor.Position+Vector3.yAxis*(height/2+.3)),Vector3.new(size,height,size),overlap)==0 then
    cf=CFrame.lookAt(pos,Vector3.new(root.Position.X,pos.Y,root.Position.Z));break
   end
  end
 end
 if not cf then combat:SetAttribute('PracticeBossStatus','Move to open ground to spawn the boss');return false end
 -- Enabling first lets the normal population reset finish before adding the boss.
 local wasEnabled=combat:GetAttribute('ZombiesEnabled')
 combat:SetAttribute('ZombiesEnabled',true)
 local npc=M.spawn(id,cf,true)
 if not npc then
  combat:SetAttribute('ZombiesEnabled',wasEnabled)
  combat:SetAttribute('PracticeBossStatus','Boss template unavailable');return false
 end
 combat:SetAttribute('PracticeBossStatus','Practice boss active · no rewards')
 npc.Destroying:Connect(function() combat:SetAttribute('PracticeBossStatus','Practice boss gone · spawn another') end)
 return true
end
-- Server projectiles: level flight (MapBossShapes.shot), stopped by world geometry or a hit.
local function stepShots(npc,s,now,params,people)
 local B=s.shots;if not B then return end
 local def=B.def;local t=math.min(now-B.born,def.life);local changed,alive=false,false
 for i,shot in B.list do
  if shot.done then continue end
  local p=Shapes.shot(B.origin,shot.yaw,def.speed,B.height,math.max(t,0));local seg=p-shot.pos
  local wall=seg.Magnitude>1e-3 and workspace:Raycast(shot.pos,seg,params)
  if wall then p=wall.Position end
  for _,e in people do
   local n=B.hits[e.player] or 0
   if n<def.perPlayer and segmentDistance(shot.pos,p,e.root.Position)<=def.radius+1.2 and hit(npc,def,e,shot.pos,params,p) then B.hits[e.player]=n+1;shot.done=true;break end
  end
  shot.pos=p
  if wall or t>=def.life then shot.done=true end
  if shot.done then B.ends[tostring(i)]=now;changed=true else alive=true end
 end
 if changed then npc:SetAttribute('MapBossShotEnds',Http:JSONEncode(B.ends)) end
 if not alive then s.shots=nil end
end
local rng=Random.new()
local function groundAt(pos,params,fallbackY)
 local g=workspace:Raycast(Vector3.new(pos.X,pos.Y+6,pos.Z),-Vector3.yAxis*30,params)
 return g and g.Position or Vector3.new(pos.X,fallbackY,pos.Z)
end
-- Ground spots under up to maxTargets living players within range of the boss, nearest first,
-- skipping anyone in `skip`, plus `extra` spots round each (X.followSpots), capped at 10.
local function spotsNear(root,people,maxTargets,range,extra,skip,params,groundY)
 table.sort(people,function(a,b) return (a.root.Position-root.Position).Magnitude<(b.root.Position-root.Position).Magnitude end)
 local targets={}
 for _,e in people do
  if #targets>=maxTargets then break end
  if not (skip and skip[e.player]) and flat(e.root.Position-root.Position).Magnitude<=range then table.insert(targets,groundAt(e.root.Position,params,groundY)) end
 end
 local list=X.followSpots(targets,extra,10,rng)
 for i,p in list do list[i]=groundAt(p,params,p.Y) end
 return list
end
local function encodePoints(points) local list={};for i,v in points do list[i]={v.X,v.Y,v.Z} end;return list end
-- A circle attack's follow-up (def.follow): circles open under the players the main hit missed and
-- erupt def.follow.delay later. It runs on its own clock, so the boss is free to move meanwhile.
local function queueFollow(npc,s,A,now,root,params,people)
 local F=A.def.follow;local rage=s.enraged and s.def.enrage or {}
 local points=spotsNear(root,people,F.maxTargets,F.range,rage.follow or 0,A.hits,params,A.ground)
 if #points==0 then return end
 s.followSerial+=1
 table.insert(s.follows,{def=F,points=points,at=now+F.delay,hits={}})
 npc:SetAttribute('MapBossFollow',Http:JSONEncode({serial=s.followSerial,kind=A.kind,at=now+F.delay,radius=F.radius,points=encodePoints(points)}))
end
local function stepFollows(npc,s,now,params,people)
 for i=#s.follows,1,-1 do
  local Q=s.follows[i]
  if now>=Q.at then
   for _,e in people do for _,c in Q.points do
    if not Q.hits[e.player] and Shapes.contains({kind='circle',center=c,radius=Q.def.radius},e.root.Position) and hit(npc,Q.def,e,c+Vector3.yAxis*2,params,c) then Q.hits[e.player]=true end
   end end
   table.remove(s.follows,i)
  end
 end
end
local function stepAttack(npc,s,now,h,root,params,people)
 local A=s.attack;local def,at,f=A.def,A.at,A.frame;local age=now-A.start;local t0=A.sampled
 local rage=s.enraged and s.def.enrage or {}
 if def.track and age>=at.impact-.1 and age<at.activeEnd then
  -- The breath turns toward the nearest player at up to def.track rad/s (x rage.track): side-steps
  -- still escape it, standing still does not. The client follows the replicated BossFrame.
  local target,dist=nil,math.huge
  for _,e in people do local d=(e.root.Position-A.cf.Position).Magnitude;if d<dist then target,dist=e.root,d end end
  if target then
   A.cf=X.turnToward(A.cf,target.Position,def.track*(rage.track or 1)*math.max(0,age-t0))
   A.frame=X.frame(A.cf,s.T,A.ground);f=A.frame;npc:SetAttribute('BossFrame',A.cf)
  end
 end
 if def.shape=='lane' then
  local travel=math.clamp((age-at.impact)*def.speed,0,A.length);local base=Vector3.new(A.cf.X,f.groundY,A.cf.Z)
  root.CFrame=A.cf+A.dir*travel
  if travel>A.travelled then
   local body={kind='capsule',a=base+A.dir*A.travelled,b=base+A.dir*travel,radius=def.width/2}
   for _,e in people do
    if not A.hits[e.player] and Shapes.contains(body,e.root.Position) and hit(npc,def,e,root.Position,params,body.b) then A.hits[e.player]=true end
   end
   A.travelled=travel
  end
 else root.CFrame=A.cf end
 if def.shape=='circle' and age>=at.impact and not A.fired then
  A.fired=true;local c=X.circle(def,at,f)
  for _,e in people do if Shapes.contains(c,e.root.Position) and hit(npc,def,e,c.center+Vector3.yAxis*2,params,c.center) then A.hits[e.player]=true end end
  if def.follow then queueFollow(npc,s,A,now,root,params,people) end
 elseif def.shape=='wave' and age>=at.impact then
  for _,e in people do
   for _,line in A.lines or {A.line} do
    if not A.hits[e.player] and X.waveHit(def,at,line,e.root.Position,t0,age) and hit(npc,def,e,line.origin+Vector3.yAxis*2,params,line.origin) then A.hits[e.player]=true end
   end
  end
 elseif (def.shape=='breath' or def.shape=='sweep') and age>=at.impact then
  -- Bound catch-up to this attack's active window, never a stale whole turn.
  local breath=def.shape=='breath';local begin,finish=math.max(t0,at.impact),math.min(age,at.activeEnd)
  local function test(time)
   local shape=breath and X.cone(def,at,f,time) or X.sweep(def,at,f,time)
   for _,e in people do
    local p=e.player;local ready
    if breath then ready=not A.ticks[p] or time-A.ticks[p]>=def.tick-1e-6 else ready=not A.hits[p] end
    if ready and Shapes.contains(shape,e.root.Position) and hit(npc,def,e,A.cf.Position,params,A.cf.Position) then A.ticks[p]=time;A.hits[p]=true end
   end
  end
  if begin<=finish then for time=begin,finish,breath and 1/30 or 1/60 do test(time) end;test(finish) end
 elseif def.shape=='targets' then
  if age>=math.max(at.warnStart,at.impact-(def.lead or 0)) and not A.points then
   -- Snapshot the nearest players in range as ground spots (plus def.extra round each, more when
   -- enraged); they erupt after eruptDelay.
   A.points=spotsNear(root,people,def.maxTargets,def.range[2],(def.extra or 0)+(rage.follow or 0),nil,params,f.groundY)
   A.data.points=encodePoints(A.points);publish(npc,A)
  end
  if A.points and age>=at.impact+def.eruptDelay and not A.fired then
   A.fired=true
   for _,e in people do for _,c in A.points do
    if not A.hits[e.player] and Shapes.contains({kind='circle',center=c,radius=def.radius},e.root.Position) and hit(npc,def,e,c+Vector3.yAxis*2,params,c) then A.hits[e.player]=true end
   end end
  end
 elseif def.shape=='projectiles' and age>=at.impact and not A.fired then
  A.fired=true;local d=A.data;local origin=v3(d.origin)
  s.shots={def=def,born=A.start+at.impact,origin=origin,height=d.height,list={},hits={},ends={}}
  for i,yaw in d.yaws do s.shots.list[i]={yaw=yaw,pos=origin} end
  npc:SetAttribute('MapBossShotEnds','{}')
 end
 if age>=at.impact and not A.impacted then A.impacted=true;npc:SetAttribute('BossImpactStart',now) end
 A.sampled=age
 if age>=A.duration then
  s.attack=nil;s.next=now+def.cooldown*(rage.cooldown or 1);npc:SetAttribute('Attacking',false);root.Anchored=false;root:SetNetworkOwner(nil);h.AutoRotate=true
 end
end
-- Below ENRAGE_AT health: faster chase, shorter cooldowns and the def.enrage extras (see MapBossDefs).
local function checkEnrage(npc,s,h)
 if s.enraged or h.Health>h.MaxHealth*Defs.ENRAGE_AT then return end
 s.enraged=true;local speed=s.def.chaseSpeed+(s.def.enrage and s.def.enrage.chase or 0)
 h.WalkSpeed=speed;npc:SetAttribute('BaseMoveSpeed',speed);npc:SetAttribute('BossEnraged',workspace:GetServerTimeNow())
end
function M.step(npc,s,now)
 if not npc.Parent then M.states[npc]=nil;return end
 local h=npc:FindFirstChildOfClass('Humanoid');local root=npc.PrimaryPart
 if not h or not root or h.Health<=0 then s.attack=nil;s.shots=nil;table.clear(s.follows);return end
 if combat:GetAttribute('ZombiesEnabled')~=true then
  s.attack=nil;s.shots=nil;table.clear(s.follows);npc:SetAttribute('Attacking',false);npc:SetAttribute('BossStart',nil);root.Anchored=false;h.AutoRotate=true;h:Move(Vector3.zero);return
 end
 checkEnrage(npc,s,h)
 local params,people=exclusions(npc),living()
 stepShots(npc,s,now,params,people)
 stepFollows(npc,s,now,params,people)
 if s.attack then stepAttack(npc,s,now,h,root,params,people);return end
 if npc:GetAttribute('BossManual') and Run:IsStudio() then h:Move(Vector3.zero);return end
 -- Admin Freeze: no moving and no new attacks; an attack already under way finishes above.
 if combat:GetAttribute('AdminFreeze')==true then h:Move(Vector3.zero);h:MoveTo(root.Position);return end
 local target,dist=nil,math.huge
 for _,e in people do local d=(e.root.Position-root.Position).Magnitude;if d<dist then target,dist=e.root,d end end
 if not target then h:Move(Vector3.zero);return end
 local reach=flat(target.Position-root.Position).Magnitude;local order=s.def.order
 if now>=s.next then
  -- Walk the order from the last attack: the first one in range (and in sight) starts.
  for i=1,#order do
   local index=(s.index+i-1)%#order+1;local range=s.def.attacks[order[index]].range
   if reach>=range[1] and reach<=range[2] and M.start(npc,order[index],target) then s.index=index;return end
  end
 end
 if reach>s.stop then h:MoveTo(target.Position) else h:Move(Vector3.zero);h:MoveTo(root.Position) end
end
-- Tests only: start `kind` now at the nearest player (or straight ahead), ignoring range and cooldown.
function M._force(npc,kind)
 local s=M.states[npc];local root=npc.PrimaryPart;if not s or s.attack or not root then return false end
 local target,dist=nil,math.huge
 for _,e in living() do local d=(e.root.Position-root.Position).Magnitude;if d<dist then target,dist=e.root,d end end
 return M.start(npc,kind,target,true)
end
Run.Heartbeat:Connect(function() local now=workspace:GetServerTimeNow();for npc,s in M.states do M.step(npc,s,now) end end)
return M
