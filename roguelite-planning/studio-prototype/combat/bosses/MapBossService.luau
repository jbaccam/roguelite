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
local Rules=require(game.ReplicatedStorage:WaitForChild('RunSetupRules'))
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
-- def.height (the Hammer's Slam: 6) raises the circle's band top, so a plain jump doesn't clear it.
function X.circle(def,at,f) return {kind='circle',center=X.onGround(f,X.point(f,at,def.point,at.impact)),radius=def.radius,height=def.height} end
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
-- The lane's direction; the root then faces along it. def.facing='forward' (the Hammer's charge)
-- runs straight at the target, body and all; otherwise the crab's side-on lane through the target.
function X.laneDir(def,pos,goal,look)
 if def.facing=='forward' then local d=flat(goal-pos);return d.Magnitude>.1 and d.Unit or flat(look).Unit end
 return X.lane(X.laneFacing(pos,goal,look),goal)
end
-- Mid-rush the crab's body is turned 90 degrees (RushStart): its claws face the left of the
-- lane (+Y x dir). def.offset shifts the hit band that way, so it runs from shell to claw tips.
-- A forward runner is centred on his path.
function X.laneSide(dir,def) return def.facing=='forward' and Vector3.zero or Vector3.yAxis:Cross(dir)*(def.offset or 0) end
-- Warning rectangle over the body's swept capsule (half a width past each end).
function X.laneShape(f,dir,length,width,side) return {kind='line',origin=X.onGround(f,f.cf.Position)-dir*width/2+(side or Vector3.zero),direction=dir,length=length+width,width=width} end
-- The rushing body's hit between two distances travelled along the lane.
function X.rushBody(def,cf,dir,groundY,from,to)
 local base=Vector3.new(cf.X,groundY,cf.Z)+X.laneSide(dir,def)
 return {kind='capsule',a=base+dir*from,b=base+dir*to,radius=def.width/2}
end
function X.cone(def,at,f,t) return {kind='cone',origin=X.onGround(f,X.point(f,at,def.point,t)),direction=X.flatDir(f,X.localDir(at,def.point,t)),halfAngle=def.halfAngle,length=def.length} end
-- A sweep hits from the moment its swing starts, not from its impact mark: the dragon's tail
-- crosses behind him about 0.2 s before impact, so a player at his rear was never hit. The swing
-- starts where the wind-up stops: walking back from impact while the tip keeps slowing down.
-- A combo's later phase (hitAfter, X.phaseWindows) never starts before the phase before it ends.
local hitFroms=setmetatable({},{__mode='k'})
function X.hitFrom(def,at)
 if def.shape~='sweep' then return at.impact end
 if hitFroms[at] then return hitFroms[at] end
 local list=at.samples and at.samples[def.point];local from=at.impact
 if list and #list>2 then
  local function speed(i) local a,b=list[i-1],list[i];return Vector3.new(b[2]-a[2],b[3]-a[3],b[4]-a[4]).Magnitude/math.max(b[1]-a[1],1e-6) end
  local i=#list;local floor=math.max(at.warnStart,at.hitAfter or at.warnStart)
  while i>2 and list[i][1]>at.impact do i-=1 end
  while i>2 and list[i-1][1]>=floor and speed(i-1)<=speed(i) do i-=1 end
  from=math.min(at.impact,math.max(list[i-1][1],at.hitAfter or -math.huge))
 end
 hitFroms[at]=from;return from
end
-- The whole tail hits: from its root at the hindquarters (baseRadius behind the boss's centre,
-- toward the tail) through def.mid to def.point. Mid-tail to tip alone missed anyone standing
-- under the thick base at his rear.
function X.sweep(def,at,f,t)
 local center=X.onGround(f,f.cf.Position)
 local mid,tip=X.onGround(f,X.point(f,at,def.mid,t)),X.onGround(f,X.point(f,at,def.point,t))
 local back=flat(mid-center);local baseRadius=def.baseRadius or def.radius
 local base=back.Magnitude>baseRadius and center+back.Unit*baseRadius or center
 return {kind='chain',a=base,points={base,mid,tip},radii={baseRadius,def.radius}}
end
-- Warning arc over the tail's active path, from the boss's centre out past the tip (the whole
-- tail hits, X.sweep). Yaw is unwrapped sample to sample, then centred, so a sweep across the
-- boss's back never wraps into the front. Hits are also held inside this arc (the hit loop).
function X.sweepArc(def,at,f)
 local pivot=X.onGround(f,f.cf.Position);local first,last,angle,lo,hi,near,far,nearTip
 local from=X.hitFrom(def,at)
 local steps=math.max(1,math.ceil((at.activeEnd-from)*60))
 for i=0,steps do
  local t=from+(at.activeEnd-from)*i/steps
  local tip=flat(X.point(f,at,def.point,t)-pivot);local mid=flat(X.point(f,at,def.mid,t)-pivot)
  if not first then first=tip.Magnitude>.05 and tip.Unit or flat(f.cf.LookVector).Unit;angle=Shapes.yaw(first,tip);lo,hi,near,far,nearTip=angle,angle,math.huge,0,math.huge
  else angle+=Shapes.yaw(last,tip);lo,hi=math.min(lo,angle),math.max(hi,angle) end
  last=tip;near=math.min(near,mid.Magnitude,tip.Magnitude);far=math.max(far,mid.Magnitude,tip.Magnitude);nearTip=math.min(nearTip,tip.Magnitude)
 end
 -- Past each end, the tip's own thickness where it sits closest to the boss (the widest angle).
 local pad=math.asin(math.min(1,def.radius/math.max(nearTip,def.radius,1)));local half=(hi-lo)/2+pad
 local inner=def.baseRadius and 0 or math.max(0,near-def.radius)
 -- A sweep reaching all the way round (the Hammer's Spin) warns a full ring, not an arc that runs
 -- past its own start. It hits the same either way: every yaw is inside.
 if half>=math.pi then return {kind='arc',pivot=pivot,forward=first,from=-math.pi,to=math.pi,inner=inner,outer=far+def.radius} end
 return {kind='arc',pivot=pivot,forward=CFrame.Angles(0,(lo+hi)/2,0):VectorToWorldSpace(first),from=-half,to=half,inner=inner,outer=far+def.radius}
end
-- Evenly spread projectile yaws (0 = world -Z) across +-spread/2 about a flat direction.
function X.yaws(def,dir)
 local base=Shapes.yaw(Vector3.new(0,0,-1),dir);local list={}
 for i=1,def.count do list[i]=base+(def.count>1 and def.spread*((i-1)/(def.count-1)-.5) or 0) end
 return list
end
-- A volley's MapBossAttackData: released from def.point at impact and fanned about the aim from
-- there to `goal`, or about the point's own direction when mouthAimed (the crab's bubbles).
function X.volley(def,at,f,goal,mouthAimed,rage)
 local origin=X.point(f,at,def.point,at.impact);local aim=flat(goal-origin)
 local dir=mouthAimed and X.flatDir(f,X.localDir(at,def.point,at.impact)) or (aim.Magnitude>.1 and aim.Unit or flat(f.cf.LookVector).Unit)
 -- Enraged: rage.extra more shots, the fan widened to keep the same gap between them.
 local count=def.count+(rage and rage.extra or 0);local fan={count=count,spread=def.count>1 and def.spread*(count-1)/(def.count-1) or def.spread}
 return {origin={origin.X,origin.Y,origin.Z},yaws=X.yaws(fan,dir),height=f.groundY+math.clamp(origin.Y-f.groundY,1.5,3.5),speed=def.speed,life=def.life,radius=def.radius}
end
-- The attack def with a part's fields on top: one combo phase (def.phases[i]) or a lane's finish.
function X.merged(def,part) local m=table.clone(def);m.phases=nil;m.finish=nil;for k,v in part do m[k]=v end;return m end
-- A combo (def.phases, the Hammer's SwingSpin and SpinSlam) is one clip with several hits. Each
-- phase's window is the clip's timing with that phase's own times (at.phases, in order, scaled by
-- MapBossDefs). hitAfter: a later swing never starts hitting before the one before it ends.
local phaseWindows=setmetatable({},{__mode='k'})
function X.phaseWindows(def,at)
 if not def.phases or not at or not at.phases or #at.phases<#def.phases then return nil end
 if phaseWindows[at] then return phaseWindows[at] end
 local list={}
 for i=1,#def.phases do
  local w=table.clone(at);w.phases=nil;for k,v in at.phases[i] do w[k]=v end
  w.hitAfter=list[i-1] and list[i-1].activeEnd;list[i]=w
 end
 phaseWindows[at]=list;return list
end
-- A combo's hit units: per phase its def, window and hit memory, so a player is hit at most once
-- per phase (and can be hit again by the next one).
function X.phases(def,at)
 local windows=X.phaseWindows(def,at);if not windows then return nil end
 local list={}
 for i,w in windows do list[i]={def=X.merged(def,def.phases[i]),at=w,hits={},ticks={},fired=false} end
 return list
end
-- The warning shape of a circle, sweep, breath or wave hit: what a phase publishes at commit (sweeps
-- also hold their hits inside it).
function X.shapeOf(def,at,f)
 if def.shape=='circle' then return X.circle(def,at,f)
 elseif def.shape=='sweep' then return X.sweepArc(def,at,f)
 elseif def.shape=='breath' then return X.cone(def,at,f,at.impact)
 elseif def.shape=='wave' then return X.wave(def,at,f) end
 return nil
end
-- One hit unit's circle, wave, breath or sweep hits between clip times t0 and age: the attack itself
-- (P = A), a combo phase, or a lane's finish. strike(e,from,source) lands one hit (the server's line
-- of sight and damage) and says whether it counted. True when a circle fired (its follow-up is due).
function X.stepHits(P,f,age,t0,people,strike)
 local def,at=P.def,P.at
 if def.shape=='circle' and age>=at.impact and not P.fired then
  P.fired=true;local c=X.circle(def,at,f)
  for _,e in people do if Shapes.contains(c,e.at) and strike(e,c.center+Vector3.yAxis*2,c.center) then P.hits[e.player]=true end end
  return true
 elseif def.shape=='wave' and age>=at.impact then
  for _,e in people do
   for _,line in P.lines or {P.line} do
    if not P.hits[e.player] and X.waveHit(def,at,line,e.at,t0,age) and strike(e,line.origin+Vector3.yAxis*2,line.origin) then P.hits[e.player]=true end
   end
  end
 elseif (def.shape=='breath' or def.shape=='sweep') and age>=X.hitFrom(def,at) then
  -- Bound catch-up to this unit's active window, never a stale whole turn. A sweep starts with
  -- its swing (X.hitFrom), and hits only inside its warning arc.
  local breath=def.shape=='breath';local begin,finish=math.max(t0,X.hitFrom(def,at)),math.min(age,at.activeEnd)
  local origin=f.cf.Position
  local function test(time)
   local shape=breath and X.cone(def,at,f,time) or X.sweep(def,at,f,time)
   for _,e in people do
    local p=e.player;local ready
    if breath then ready=not P.ticks[p] or time-P.ticks[p]>=def.tick-1e-6 else ready=not P.hits[p] and (not P.arc or Shapes.contains(P.arc,e.at)) end
    if ready and Shapes.contains(shape,e.at) and strike(e,origin,origin) then P.ticks[p]=time;P.hits[p]=true end
   end
  end
  -- A whipping tail tip covers ~4.6 studs per 1/60 s; at 1/120 its 4-stud hit leaves no gaps.
  if begin<=finish then for time=begin,finish,breath and 1/30 or 1/120 do test(time) end;test(finish) end
 end
 return false
end
-- The forward charge keeps running while its target stays in the lane (def.contact, ported from
-- BossService.stepCharge): it ends with his root `contact` studs short of them (the body hit is
-- width/2 > contact, so it lands), wherever they now are along the lane. Backing away down the lane
-- doesn't outrun him; stepping out of it (or 7 studs up or down) dodges: the length stays
-- `previous`. Capped by def.length and the wall, and never below the distance already travelled.
function X.contactLength(def,cf,dir,targetPos,wallLength,previous,travelled)
 local d=flat(targetPos-cf.Position);local along=d:Dot(dir);local side=(d-dir*along).Magnitude
 if side>def.width/2 or math.abs(targetPos.Y-cf.Y)>7 then return previous end
 local cap=math.min(def.length,wallLength or def.length)
 return math.max(travelled or 0,math.min(cap,along-math.sqrt(math.max(0,def.contact^2-side^2))))
end
-- A lane's finish (def.finish, the ChargeSlam): the end clip's own timing, measured from where the
-- run ends (cf moved `length` along dir) on the floor at groundY. Its clip starts at the lane
-- window's activeEnd (X.laneTiming). Returns that timing and the frame; nil without timing.
function X.finishFrame(def,T,cf,dir,length,groundY)
 local at=T.attacks and def.clips and T.attacks[def.clips[3]];if not at then return nil end
 return at,X.frame(cf+dir*length,T,groundY)
end
-- The Hammer-style charge (a forward lane or a contact run): it follows the floor, its length can
-- change, and clients get it as BossChargeLength.
function X.isCharge(def) return def.shape=='lane' and (def.facing=='forward' or def.contact~=nil) end
-- A lane's window, duration and data for its current length: the warning, and the finish slam where
-- the run ends (on the end floor, A.endGround, once he has stopped). The contact run re-times it on
-- every change, so the server's hits stay exact.
function X.laneTiming(T,A)
 local def=A.def
 A.at=X.window(def,T,A.length);A.duration=X.duration(def,A.at)
 A.data.length=A.length;A.data.shape=Shapes.encode(X.laneShape(A.frame,A.dir,A.length,def.width,X.laneSide(A.dir,def)))
 local F=A.finish
 if F then
  F.at,F.frame=X.finishFrame(def,T,A.cf,A.dir,A.length,A.endGround or A.ground);F.start=A.at.activeEnd
  if F.at then
   A.duration=math.max(A.duration,F.start+F.at.impact+.05)
   A.data.finish={shape=Shapes.encode(X.circle(F.def,F.at,F.frame)),impact=F.start+F.at.impact}
  end
 end
end
-- def.lockout: an attack's own minimum gap between its starts (the charge: 5 s), on top of cooldowns.
function X.lockedOut(s,kind,now)
 local a=s.def.attacks[kind];local last=s.lastStart and s.lastStart[kind]
 return a.lockout~=nil and last~=nil and now-last<a.lockout
end
-- The order walk, from the attack after the last one: the first in range, not locked out, that
-- try(kind) starts (in sight; MapBossService.start). Returns its index.
function X.walk(s,order,reach,now,try)
 for i=1,#order do
  local index=(s.index+i-1)%#order+1;local kind=order[index];local range=s.def.attacks[kind].range
  if reach>=range[1] and reach<=range[2] and not X.lockedOut(s,kind,now) and try(kind) then return index end
 end
 return nil
end
-- The attack order: the tutorial boss's (def.tutorial.order), else the enraged one when the def has
-- it (def.enrage.order), else def.order.
function X.orderFor(s)
 local def=s.def
 if s.tutorial and def.tutorial and def.tutorial.order then return def.tutorial.order end
 return s.enraged and def.enrage and def.enrage.order or def.order
end
-- The tutorial boss (TutorialBossHealth) teaches the moves, it doesn't punish: def.tutorial.enrage
-- and .follow set to false turn those off. True when `key` stays on for this boss.
function X.allows(s,key) return not (s.tutorial and s.def.tutorial and s.def.tutorial[key]==false) end
-- The enrage roar (def.roar): once, after enraging, and only between attacks: one under way
-- finishes first.
function X.roarDue(s) return s.enraged==true and not s.roared and not s.attack and s.def.roar~=nil end

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
-- root aims attacks; at (CharacterService.seen: where their screen has them) is what hits test.
local function living()
 local list={}
 for _,p in Players:GetPlayers() do
  local ch=p.Character;local pr=ch and ch:FindFirstChild('HumanoidRootPart');local ph=ch and ch:FindFirstChildOfClass('Humanoid')
  if pr and ph and ph.Health>0 and Characters.states[p] then table.insert(list,{player=p,root=pr,at=Characters.seen(p,pr)}) end
 end
 return list
end
-- One hit: line of sight from `from`, then CharacterService applies armor, dodge and blocks.
local function hit(npc,def,e,from,params,source)
 if workspace:Raycast(from,e.root.Position-from,params) then return false end
 local actual=Characters.contact(e.player,def.damage*(npc:GetAttribute('BossDamageScale') or 1))
 if Run:IsStudio() then npc:SetAttribute('BossHits',(npc:GetAttribute('BossHits') or 0)+1);npc:SetAttribute('LastBossDamage',actual) end -- QA only (hammer-boss/test_heavy_studio): live servers don't replicate them (audit P12)
 if def.knockdown and actual>0 then knock:FireClient(e.player,source,def.knockdown) end
 return true
end
local function publish(npc,A) npc:SetAttribute('MapBossAttackData',Http:JSONEncode(A.data)) end
local function segmentDistance(a,b,p) local ab=b-a;local t=math.clamp((p-a):Dot(ab)/math.max(ab:Dot(ab),1e-6),0,1);return (a+ab*t-p).Magnitude end
-- Holding still for an attack, the intro or the roar (commit), and back to the chase (release).
-- The server keeps network ownership of the boss either way: a released root left to the nearest
-- client would let it push him around.
local function commit(npc,h,root) npc:SetAttribute('Attacking',true);h:Move(Vector3.zero);h:MoveTo(root.Position);h.AutoRotate=false;root.Anchored=true end
local function release(npc,h,root) npc:SetAttribute('Attacking',false);root.Anchored=false;root:SetNetworkOwner(nil);h.AutoRotate=true end
function M.start(npc,kind,target,force)
 local s=M.states[npc];local def=s and s.def.attacks[kind];local h=npc:FindFirstChildOfClass('Humanoid');local root=npc.PrimaryPart
 if not def or s.attack or not h or h.Health<=0 or not root or not X.window(def,s.T) then return false end
 -- A combo needs its clip's phase timings (MapBossTiming phases), and a finish its end clip's.
 if def.phases and not X.phaseWindows(def,X.window(def,s.T)) then return false end
 if def.finish and not (def.clips and s.T.attacks and s.T.attacks[def.clips[3]]) then return false end
 local goal=target and target.Parent and target.Position or root.Position+root.CFrame.LookVector*12
 local delta=goal-root.Position;local params=exclusions(npc)
 if not force and (not target or math.abs(delta.Y)>10 or workspace:Raycast(root.Position,delta,params)) then return false end
 local laneDir
 if def.shape=='lane' then
  -- The crab's lane is the side the target is on once it stands side-on to it, so it runs through
  -- the target: RushStart turns the body so its right side leads, and RushLoop travels along the
  -- model's forward. A forward runner (the Hammer) runs straight at them. Either way the root
  -- faces along the lane (X.laneDir).
  laneDir=X.laneDir(def,root.Position,goal,root.CFrame.LookVector);root.CFrame=CFrame.lookAt(root.Position,root.Position+laneDir)
 elseif flat(delta).Magnitude>.1 then root.CFrame=CFrame.lookAt(root.Position,root.Position+flat(delta)) end
 local ground=workspace:Raycast(root.Position+Vector3.yAxis*8,-Vector3.yAxis*(s.T.rootHeight+30),params)
 if not ground then return false end
 local now=workspace:GetServerTimeNow();local cf=root.CFrame;local f=X.frame(cf,s.T,ground.Position.Y)
 local A={kind=kind,def=def,start=now,cf=cf,ground=f.groundY,frame=f,hits={},ticks={},sampled=0,data={}}
 if def.shape=='lane' then
  -- Clamped short of a wall at body height; the body travels at `speed` after RushStart.
  -- def.contact: the run ends with his root `contact` studs short of the target, and follows them
  -- down the lane (stepAttack, X.contactLength). def.finish: the closing slam, its own hit memory,
  -- so a player hit by the run can be hit by the slam too.
  A.dir=laneDir;local wall=workspace:Raycast(cf.Position,A.dir*def.length,params)
  A.limit=wall and math.max(0,wall.Distance-math.min(8,s.T.footprintRadius or 4)/2-1) or def.length;A.travelled=0
  A.length=def.contact and X.contactLength(def,cf,A.dir,Vector3.new(goal.X,cf.Y,goal.Z),A.limit,A.limit,0) or A.limit
  A.target=def.contact and target or nil
  if def.finish then A.finish={def=X.merged(def,def.finish),hits={},ticks={},fired=false} end
  A.data={dir={A.dir.X,A.dir.Z}};X.laneTiming(s.T,A)
 else A.at=X.window(def,s.T);A.duration=X.duration(def,A.at) end
 local at=A.at
 local rage=s.enraged and s.def.enrage or {}
 if def.phases then
  -- Every phase's warning goes out at commit (data.phases; the client fills a later one in as its
  -- hit nears). data.shape (the first phase) is kept for older readers.
  A.phases=X.phases(def,at);A.data.phases={}
  for i,P in A.phases do
   local shape=X.shapeOf(P.def,P.at,f)
   if P.def.shape=='sweep' then P.arc=shape elseif P.def.shape=='wave' then P.line=shape end
   A.duration=math.max(A.duration,X.duration(P.def,P.at))
   A.data.phases[i]={shape=shape and Shapes.encode(shape),warnStart=P.at.warnStart,impact=P.at.impact,activeEnd=P.at.activeEnd}
  end
  A.data.shape=A.data.phases[1].shape
 elseif def.shape=='circle' then A.data.shape=Shapes.encode(X.circle(def,at,f))
 elseif def.shape=='wave' then
  -- Enraged, the wave splits into a fan (rage.fan, degrees). Hits test every line; data.shape
  -- (the middle line) is kept for older readers, and the client warns and draws data.lines.
  A.lines={};A.data.lines={}
  for _,deg in rage.fan or {0} do local line=X.wave(def,at,f,math.rad(deg));table.insert(A.lines,line);table.insert(A.data.lines,Shapes.encode(line)) end
  A.line=A.lines[math.ceil(#A.lines/2)];A.data.shape=Shapes.encode(A.line)
 elseif def.shape=='breath' then A.data.shape=Shapes.encode(X.cone(def,at,f,at.impact))
 elseif def.shape=='sweep' then A.arc=X.sweepArc(def,at,f);A.data.shape=Shapes.encode(A.arc)
 elseif def.shape=='projectiles' then A.data=X.volley(def,at,f,goal,MOUTH_AIMED[kind],rage) end
 A.data.rate=def.rate or 1
 s.attack=A;s.lastStart[kind]=now -- def.lockout (X.lockedOut)
 npc:SetAttribute('BossAttack',kind);npc:SetAttribute('BossStart',now);npc:SetAttribute('BossFrame',cf);npc:SetAttribute('BossGroundY',f.groundY);npc:SetAttribute('BossDuration',A.duration)
 -- A charge's length (X.isCharge) changes as he runs. Client contract: re-time the end clip from
 -- BossChargeLength, falling back to data.length. It is set before BossSerial, so no client reads
 -- the last charge's value; stepAttack sends it on 0.5-stud changes, and exactly when he stops.
 if X.isCharge(def) then A.sentLength=A.length;npc:SetAttribute('BossChargeLength',A.length) end
 A.serial=(npc:GetAttribute('BossSerial') or 0)+1
 publish(npc,A);npc:SetAttribute('BossSerial',A.serial);commit(npc,h,root)
 return true
end
function M.spawn(id,cf,practice,opts)
 assert(typeof(cf)=='CFrame','Server spawn requires CFrame')
 -- practice: an admin-panel boss (BossPractice: no loot). Callers check the developer first.
 -- opts.intro (BossEncounter's wave bosses): the def.intro sky-drop entrance, when the def has one.
 local def,T=Defs.get(id),Defs.timing(id);if not def or not T then return nil end
 local template=game.ServerStorage.RogueliteNPCs:FindFirstChild(id..'_NPC');if not template then return nil end
 local folder=workspace:FindFirstChild('RogueliteEnemies');if not folder then return nil end
 local intro=not practice and opts and opts.intro and def.intro or nil
 if intro then
  -- He lands facing the nearest run member: BossEncounter's spot has no facing, so he fell facing
  -- world -Z, away from the map's spawn (BossService, user 2026-10-03).
  local near,best=nil,math.huge
  for _,p in Players:GetPlayers() do
   local r=p:GetAttribute('RunMember') and p.Character and p.Character:FindFirstChild('HumanoidRootPart')
   if r then local d=(r.Position-cf.Position).Magnitude;if d<best then near,best=r,d end end
  end
  local to=near and Vector3.new(near.Position.X,cf.Position.Y,near.Position.Z)
  if to and (to-cf.Position).Magnitude>.5 then cf=CFrame.lookAt(cf.Position,to) end
 end
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
 -- Difficulty and the run's player count scale health; difficulty scales every hit (see hit).
 -- Only run members count (ShopService RunMember): players in the lobby don't toughen the boss.
 local members=0;for _,p in Players:GetPlayers() do if p:GetAttribute('RunMember') then members+=1 end end
 local hpScale,damageScale=Rules.bossScale(combat:GetAttribute('RunDifficulty'),math.max(1,members))
 -- The tutorial's boss (TutorialDirector sets TutorialBossHealth): that fixed health, no scaling,
 -- and the def.tutorial variant (s.tutorial: its order, no enrage or follow-ups).
 local fixed=not practice and combat:GetAttribute('TutorialBossHealth');local tutorial=type(fixed)=='number'
 h.MaxHealth=tutorial and fixed or math.ceil(def.health*hpScale);h.Health=h.MaxHealth;h.WalkSpeed=def.chaseSpeed
 npc:SetAttribute('BossDamageScale',damageScale)
 npc:SetAttribute('BossSpawnedAt',workspace:GetServerTimeNow())
 npc:SetAttribute('IsBoss',true);npc:SetAttribute('IsMapBoss',true);npc:SetAttribute('MapBossId',id);npc:SetAttribute('BossName',def.name);npc:SetAttribute('ZombieType',id)
 npc:SetAttribute('ContactDamage',0);npc:SetAttribute('ContactRange',0);npc:SetAttribute('BaseMoveSpeed',h.WalkSpeed)
 if not npc:GetAttribute('BossDeathSeconds') and T.clips and T.clips.Death then npc:SetAttribute('BossDeathSeconds',T.clips.Death+.6) end
 for _,p in npc:GetDescendants() do if p:IsA('BasePart') then p.Anchored=false end end
 npc.Parent=folder;root:SetNetworkOwner(nil);h.AutoRotate=true
 local s={id=id,def=def,T=T,next=workspace:GetServerTimeNow()+Defs.FIRST_ATTACK,index=0,lastHealth=h.Health,stop=def.stop or math.min(8*scale,T.footprintRadius or 4)+3,follows={},followSerial=0,
  lastStart={},tutorial=tutorial or nil};M.states[npc]=s
 if intro then
  -- The entrance (BossService's, from def.intro): rumble and a growing shadow for `drop`, the fall,
  -- then the landing and camera orbit (BossIntro.client) for `after`. The intro clip is timed so
  -- its impact meets the ground at BossIntroLand; it deals no damage (no s.attack). Until
  -- BossIntroUntil he can't be hurt (CombatEffectsService) and stands anchored, and CinematicUntil
  -- holds the players (CharacterService.frozen) and the enemies (RogueliteZombieChase).
  local now=workspace:GetServerTimeNow();local land=now+intro.drop+intro.fall;local done=land+intro.after
  local clip=T.attacks and T.attacks[intro.clip]
  npc:SetAttribute('BossIntroStart',now);npc:SetAttribute('BossIntroLand',land);npc:SetAttribute('BossIntroUntil',done)
  if def.introName then npc:SetAttribute('BossIntroName',def.introName) end
  npc:SetAttribute('BossAttack',intro.clip);npc:SetAttribute('BossStart',land-(clip and clip.impact or 0));npc:SetAttribute('BossFrame',root.CFrame)
  npc:SetAttribute('BossGroundY',root.Position.Y-T.rootHeight-.1)
  npc:SetAttribute('BossSerial',(npc:GetAttribute('BossSerial') or 0)+1);commit(npc,h,root)
  s.intro=done;s.next=done+.6
  combat:SetAttribute('CinematicUntil',done)
 end
 -- One flinch per 2 s, as the Hammer boss (BossService): restarting it on every hit froze the
 -- boss in its first frame while it kept walking.
 h.HealthChanged:Connect(function(health)
  local now=workspace:GetServerTimeNow()
  if health<s.lastHealth and health>0 and not s.attack and now-(npc:GetAttribute('BossHitStart') or -math.huge)>=2 then npc:SetAttribute('BossHitStart',now) end;s.lastHealth=health
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
   if n<def.perPlayer and segmentDistance(shot.pos,p,e.at)<=def.radius+1.2 and hit(npc,def,e,shot.pos,params,p) then B.hits[e.player]=n+1;shot.done=true;break end
  end
  shot.pos=p
  if wall or t>=def.life then shot.done=true end
  if shot.done then B.ends[tostring(i)]=now;changed=true else alive=true end
 end
 if changed then npc:SetAttribute('MapBossShotEnds',Http:JSONEncode({serial=B.serial,ends=B.ends})) end
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
-- A circle hit's follow-up (def.follow): circles open under the players that hit missed and erupt
-- def.follow.delay later. It runs on its own clock, so the boss is free to move meanwhile. P is the
-- hit unit that fired: the attack itself, a combo phase or a lane's finish.
local function queueFollow(npc,s,A,P,now,root,params,people)
 local F=P.def.follow;local rage=s.enraged and s.def.enrage or {}
 local points=spotsNear(root,people,F.maxTargets,F.range,rage.follow or 0,P.hits,params,A.ground)
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
    if not Q.hits[e.player] and Shapes.contains({kind='circle',center=c,radius=Q.def.radius,height=Q.def.height},e.at) and hit(npc,Q.def,e,c+Vector3.yAxis*2,params,c) then Q.hits[e.player]=true end
   end end
   table.remove(s.follows,i)
  end
 end
end
-- The enrage roar (def.roar): an attack with no hit, anchored for the clip's length and published
-- like one (BossAttack = the clip), so the client plays it. Cooldowns run on meanwhile.
local function startRoar(npc,s,now,h,root,params)
 local duration=s.T.clips and s.T.clips[s.def.roar];if not duration then return false end
 local ground=workspace:Raycast(root.Position+Vector3.yAxis*8,-Vector3.yAxis*(s.T.rootHeight+30),params)
 local cf=root.CFrame;local A={kind=s.def.roar,roar=true,start=now,cf=cf,duration=duration,sampled=0,data={rate=1}}
 s.attack=A
 npc:SetAttribute('BossAttack',A.kind);npc:SetAttribute('BossStart',now);npc:SetAttribute('BossFrame',cf);npc:SetAttribute('BossGroundY',ground and ground.Position.Y or cf.Y-s.T.rootHeight);npc:SetAttribute('BossDuration',duration)
 A.serial=(npc:GetAttribute('BossSerial') or 0)+1
 publish(npc,A);npc:SetAttribute('BossSerial',A.serial);commit(npc,h,root)
 return true
end
local function stepAttack(npc,s,now,h,root,params,people)
 local A=s.attack;local age=now-A.start;local t0=A.sampled
 if A.roar then
  -- Only a finished roar counts: one cancelled by a pause plays again afterwards (X.roarDue).
  root.CFrame=A.cf;A.sampled=age
  if age>=A.duration then s.attack=nil;s.roared=true;release(npc,h,root) end
  return
 end
 local def=A.def;local rage=s.enraged and s.def.enrage or {}
 if A.target and not A.stopped and A.target.Parent then
  -- The forward charge (def.contact) runs on while its target stays in the lane; once he has
  -- stopped, the run is fixed. The server re-times on every change, so its hits stay exact;
  -- clients get BossChargeLength on 0.5-stud changes (M.start), the rest when he stops.
  local length=X.contactLength(def,A.cf,A.dir,A.target.Position,A.limit,A.length,A.travelled)
  if math.abs(length-A.length)>.05 then A.length=length;X.laneTiming(s.T,A) end
  if math.abs(A.length-(A.sentLength or -1))>=.5 then A.sentLength=A.length;npc:SetAttribute('BossChargeLength',A.length) end
 end
 local at,f=A.at,A.frame
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
  local travel=math.clamp((age-at.impact)*def.speed,0,A.length)
  if def.facing=='forward' then
   -- A forward runner follows the floor (BossService.stepCharge), so a slope doesn't leave him
   -- floating or buried; until he moves he stays where he committed. The crab's rush is level.
   local to=A.cf.Position+A.dir*travel
   if travel>A.travelled then
    local floor=workspace:Raycast(to+Vector3.yAxis*6,-Vector3.yAxis*(s.T.rootHeight+14),params)
    if floor then A.floorY=floor.Position.Y end
   end
   root.CFrame=A.cf.Rotation+Vector3.new(to.X,A.floorY and A.floorY+s.T.rootHeight or A.cf.Y,to.Z)
  else root.CFrame=A.cf+A.dir*travel end
  if travel>A.travelled then
   local body=X.rushBody(def,A.cf,A.dir,A.floorY or f.groundY,A.travelled,travel)
   for _,e in people do
    if not A.hits[e.player] and Shapes.contains(body,e.at) and hit(npc,def,e,root.Position,params,body.b) then A.hits[e.player]=true end
   end
   A.travelled=travel
  end
  if travel>=A.length and not A.stopped then
   A.stopped=true
   if X.isCharge(def) then
    -- Stopped: the finish slam lands on the floor where he ended (A.endGround), and late readers
    -- get the exact final length, warning, finish and duration: the run's one data republish.
    A.endGround=A.floorY;X.laneTiming(s.T,A)
    A.sentLength=A.length;npc:SetAttribute('BossChargeLength',A.length);publish(npc,A);npc:SetAttribute('BossDuration',A.duration)
   end
  end
 else root.CFrame=A.cf end
 -- Circle, wave, breath and sweep hits (X.stepHits): the attack itself, or each combo phase with
 -- its own hit memory. A circle that fired brings its follow-up (none in the tutorial).
 for _,P in A.phases or {A} do
  if X.stepHits(P,f,age,t0,people,function(e,from,source) return hit(npc,P.def,e,from,params,source) end) and P.def.follow and X.allows(s,'follow') then queueFollow(npc,s,A,P,now,root,params,people) end
 end
 -- A lane's finish slam, on the end clip's clock (it starts where the run ends, F.start).
 local F=A.finish
 if F and F.at and X.stepHits(F,F.frame,age-F.start,t0-F.start,people,function(e,from,source) return hit(npc,F.def,e,from,params,source) end) and F.def.follow and X.allows(s,'follow') then
  queueFollow(npc,s,A,F,now,root,params,people)
 end
 if def.shape=='targets' then
  if age>=math.max(at.warnStart,at.impact-(def.lead or 0)) and not A.points then
   -- Snapshot the nearest players in range as ground spots (plus def.extra round each, more when
   -- enraged); they erupt after eruptDelay.
   A.points=spotsNear(root,people,def.maxTargets,def.range[2],(def.extra or 0)+(rage.follow or 0),nil,params,f.groundY)
   A.data.points=encodePoints(A.points);publish(npc,A)
  end
  if A.points and age>=at.impact+def.eruptDelay and not A.fired then
   A.fired=true
   for _,e in people do for _,c in A.points do
    if not A.hits[e.player] and Shapes.contains({kind='circle',center=c,radius=def.radius},e.at) and hit(npc,def,e,c+Vector3.yAxis*2,params,c) then A.hits[e.player]=true end
   end end
  end
 elseif def.shape=='projectiles' and age>=at.impact and not A.fired then
  A.fired=true;local d=A.data;local origin=v3(d.origin)
  s.shots={def=def,serial=A.serial,born=A.start+at.impact,origin=origin,height=d.height,list={},hits={},ends={}}
  for i,yaw in d.yaws do s.shots.list[i]={yaw=yaw,pos=origin} end
  npc:SetAttribute('MapBossShotEnds',Http:JSONEncode({serial=A.serial,ends={}}))
 end
 local impact=at.impact or A.phases and A.phases[1].at.impact
 if impact and age>=impact and not A.impacted then A.impacted=true;npc:SetAttribute('BossImpactStart',now) end
 A.sampled=age
 if age>=A.duration then s.attack=nil;s.next=now+def.cooldown*(rage.cooldown or 1);release(npc,h,root) end
end
-- Below ENRAGE_AT health: faster chase, shorter cooldowns and the def.enrage extras (see MapBossDefs).
-- Never for the tutorial boss whose def says so (X.allows).
local function checkEnrage(npc,s,h)
 if s.enraged or not X.allows(s,'enrage') or h.Health>h.MaxHealth*Defs.ENRAGE_AT then return end
 s.enraged=true;local speed=s.def.chaseSpeed+(s.def.enrage and s.def.enrage.chase or 0)
 h.WalkSpeed=speed;npc:SetAttribute('BaseMoveSpeed',speed);npc:SetAttribute('BossEnraged',workspace:GetServerTimeNow())
end
function M.step(npc,s,now)
 if not npc.Parent then M.states[npc]=nil;return end
 local h=npc:FindFirstChildOfClass('Humanoid');local root=npc.PrimaryPart
 if not h or not root or h.Health<=0 then s.attack=nil;s.shots=nil;table.clear(s.follows);return end
 -- The sky-drop entrance (def.intro, M.spawn): stand still until it's over, then fight.
 if s.intro then
  if now<s.intro then h:Move(Vector3.zero);return end
  s.intro=nil;npc:SetAttribute('BossStart',nil);release(npc,h,root)
 end
 if combat:GetAttribute('ZombiesEnabled')~=true then
  s.attack=nil;s.shots=nil;table.clear(s.follows);npc:SetAttribute('BossStart',nil);release(npc,h,root);h:Move(Vector3.zero);return
 end
 -- Pause (plan L): a paused run cancels the attack under way, its shots and follow-ups, and
 -- holds still. Attacks start fresh (with their wind-up) once the run unfreezes.
 if combat:GetAttribute('RunPaused')==true then
  if s.attack then s.attack=nil;npc:SetAttribute('BossStart',nil);release(npc,h,root) end
  s.shots=nil;table.clear(s.follows);h:Move(Vector3.zero);h:MoveTo(root.Position);return
 end
 checkEnrage(npc,s,h)
 local params,people=exclusions(npc),living()
 stepShots(npc,s,now,params,people)
 stepFollows(npc,s,now,params,people)
 if s.attack then stepAttack(npc,s,now,h,root,params,people);return end
 if npc:GetAttribute('BossManual') and Run:IsStudio() then h:Move(Vector3.zero);return end
 -- Admin Freeze: no moving and no new attacks; an attack already under way finishes above.
 if combat:GetAttribute('AdminFreeze')==true then h:Move(Vector3.zero);h:MoveTo(root.Position);return end
 -- Enraged: the roar first, once (an attack under way finished above); without its clip, never.
 if X.roarDue(s) then if startRoar(npc,s,now,h,root,params) then return end;s.roared=true end
 local target,dist=nil,math.huge
 for _,e in people do local d=(e.root.Position-root.Position).Magnitude;if d<dist then target,dist=e.root,d end end
 if not target then h:Move(Vector3.zero);return end
 local reach=flat(target.Position-root.Position).Magnitude
 if now>=s.next then
  -- Walk the order (the tutorial's or enraged one, X.orderFor) from the last attack: the first one
  -- in range, not locked out and in sight starts.
  local index=X.walk(s,X.orderFor(s),reach,now,function(kind) return M.start(npc,kind,target) end)
  if index then s.index=index;return end
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
