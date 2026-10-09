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
-- Round 10 event moves (Round10Service): npc -> fn(kind, attack, now), called once at each attack's
-- impact (the DJ Crab's Beat Command, the Blood Moon Alpha's howl). Weak: a removed boss drops out.
M.hooks=setmetatable({},{__mode='k'})

-- Pure shape builders (M._shapes). Attack timing `at` is a MapBossTiming attack entry; points
-- are ground-frame studs (plan F Coordinates). Shapes lie on the attack's ground height.
local X={}
M._shapes=X
local NONE=table.freeze({}) -- an empty list to loop over without making one each Heartbeat
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
-- An attack's window; a lane's is RushStart, travel at `speed`, RushEnd (MapBossShapes.window, the
-- client's too).
X.window=Shapes.window
-- When the boss may act again: recovery, stretched to cover delayed hits (wave travel, eruptions).
function X.duration(def,at)
 local d=at.recoveryEnd or at.duration
 if def.shape=='wave' then d=math.max(d,at.impact+def.length/def.travel+.05)
 elseif def.shape=='targets' then d=math.max(d,at.impact+def.eruptDelay+.05) end
 if def.shape=='ring' then d=math.max(d,at.impact+(def.outer-def.inner)/def.travel+.05) end -- round 10: until the front is out
 return d
end
-- def.height (the Hammer's Slam: 6) raises the circle's band top, so a plain jump doesn't clear it.
function X.circle(def,at,f) return {kind='circle',center=X.onGround(f,X.point(f,at,def.point,at.impact)),radius=def.radius,height=def.height} end
-- A wave line from def.point at impact: along the clip's authored direction (the Stomp), or with
-- def.facing='forward' (the Hammer's rubble wave, 2026-10-09) along the frame's own facing, which aim
-- turns (and a charge's finish frame faces down the run). yaw turns it (an enraged fan).
function X.wave(def,at,f,yaw)
 local d=def.facing~='forward' and at.directionAtImpactStudio and v3(at.directionAtImpactStudio) or nil;local dir=X.flatDir(f,d)
 if yaw and yaw~=0 then dir=CFrame.Angles(0,yaw,0):VectorToWorldSpace(dir) end
 return {kind='line',origin=X.onGround(f,X.point(f,at,def.point,at.impact)),direction=dir,length=def.length,width=def.width}
end
-- The yaw that turns cf's facing toward goal, at most maxTurn radians either way (0 when goal is on
-- top of it).
function X.turnAngle(cf,goal,maxTurn)
 local d=flat(goal-cf.Position);if d.Magnitude<.1 then return 0 end
 return math.clamp(Shapes.yaw(cf.LookVector,d),-maxTurn,maxTurn)
end
-- Turns cf's facing toward goal by at most maxTurn radians about +Y (the breath's tracking, aim).
function X.turnToward(cf,goal,maxTurn)
 local d=flat(goal-cf.Position);if d.Magnitude<.1 then return cf end
 return CFrame.new(cf.Position)*CFrame.Angles(0,X.turnAngle(cf,goal,maxTurn),0)*cf.Rotation
end
-- Aim (def.aim={rate,lock}, the Hammer; the boss def's, or an attack's own): the attack frame keeps
-- turning toward its target until aim.lock s before the hit coming next, then holds, so its warning
-- stops moving before the hit. A combo re-aims in each phase's wind-up: from the phase before it's
-- activeEnd to this phase's impact - lock. True when clip time `age` is inside one of those windows.
function X.aimOpen(A,age,lock)
 local list=A.phases or {A}
 for i,P in list do
  local from=i>1 and list[i-1].at.activeEnd or 0
  if age>=from and age<P.at.impact-lock then return true end
 end
 return false
end
-- One aim step: A.cf turns toward goal at up to aim.rate over dt (yaw only, about the root), while
-- the window is open. True when it turned.
function X.aimStep(A,age,dt,goal,aim)
 if not goal or dt<=0 or not X.aimOpen(A,age,aim.lock) then return false end
 local a=X.turnAngle(A.cf,goal,aim.rate*dt);if math.abs(a)<1e-7 then return false end
 A.cf=CFrame.new(A.cf.Position)*CFrame.Angles(0,a,0)*A.cf.Rotation;return true
end
-- Republishing a turned frame (BossFrame) or heading (BossChargeHead): only once it has turned more
-- than SEND_TURN (1 degree) from the one sent, and exactly when the aim locks (the frame the hit
-- uses). A few updates a second, not one a frame.
X.SEND_TURN=math.rad(1)
function X.frameDue(sentYaw,yaw,locked)
 local d=math.abs(Shapes.wrap(yaw-sentYaw));return d>X.SEND_TURN or (locked and d>1e-6)
end
function X.headDue(sent,dir) return math.abs(Shapes.yaw(sent,dir))>X.SEND_TURN end
-- Charge homing (def.home rad/s, the Hammer's run): the heading turns toward goal by at most maxTurn.
function X.homeDir(dir,pos,goal,maxTurn)
 local d=flat(goal-pos);if d.Magnitude<.1 then return dir end
 return CFrame.Angles(0,math.clamp(Shapes.yaw(dir,d),-maxTurn,maxTurn),0):VectorToWorldSpace(dir)
end
-- One homing step: the heading turns toward goal (nil: it holds) at up to def.home over dt, then the
-- body moves on to `travel` (the run's distance so far) along it. Returns the step's two ends: the
-- body hit's segment of the real path.
function X.homeStep(A,def,goal,dt,travel)
 if goal then A.dir=X.homeDir(A.dir,A.pos,goal,def.home*math.max(0,dt)) end
 local a=A.pos;A.pos=a+A.dir*math.max(0,travel-A.travelled);A.travelled=math.max(A.travelled,travel)
 return a,A.pos
end
-- The body's hit on a homing run: one step's segment of the path, on the floor.
function X.pathBody(def,a,b,groundY) return {kind='capsule',a=Vector3.new(a.X,groundY,a.Z),b=Vector3.new(b.X,groundY,b.Z),radius=def.width/2} end
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
-- The front crossing a moving player (def.facing='forward', the Hammer's rubble; the Stomp keeps
-- X.waveHit): the front is (t - impact) x travel down the line. A player ahead of it at t0 (along
-- `prev`, their last sample; nil: where they are now) and level with or behind it at t1 was crossed
-- in between, so walking or dashing toward the boss can't slip through the gap between two 60 Hz
-- samples (X.waveHit tests only where they are now: about 1 crossing in 3 got through). They must be
-- inside the line's width and height band now, and the crossing on the line (0..length). For a still
-- player it is exactly X.waveHit. Returns the hit and their along-distance now (the next prev).
function X.waveCross(def,at,line,pos,prev,t0,t1)
 local d=flat(pos-line.origin);local along=d:Dot(line.direction)
 local f0,f1=(t0-at.impact)*def.travel,(t1-at.impact)*def.travel
 local r0,r1=(prev or along)-f0,along-f1
 if r0<=0 or r1>0 or f1<0 then return false,along end
 local x=f0+(f1-f0)*r0/(r0-r1)
 if x<-1e-6 or x>line.length+1e-6 or (d-line.direction*along).Magnitude>line.width/2 then return false,along end
 local y=pos.Y-line.origin.Y
 return y>=-Shapes.HEIGHT_BELOW and y<=(line.height or Shapes.HEIGHT_ABOVE),along
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
X.merged=Shapes.merged
-- A combo (def.phases, the Hammer's SwingSpin and SpinSlam) is one clip with several hits. Each
-- phase's window is the clip's timing with that phase's own times (at.phases, in order, scaled by
-- MapBossDefs). hitAfter: a later swing never starts hitting before the one before it ends.
-- A def phase past the clip's timed phases (MapBossShapes.partWindow) borrows the last timed phase's
-- window, or the clip's own times when it has none (2026-10-09: the rubble wave is timed like the slam
-- circle, so a clip baked without the wave phase still slams instead of the attack being dropped);
-- `borrowed` marks it. Cached per timing and phase count.
local phaseWindows=setmetatable({},{__mode='k'})
function X.phaseWindows(def,at)
 if not def.phases or not at then return nil end
 local byCount=phaseWindows[at];local n=#def.phases
 if byCount and byCount[n] then return byCount[n] end
 local list={}
 for i=1,n do
  local w=table.clone(Shapes.partWindow(at,i));w.borrowed=not (at.phases and at.phases[i]) or nil
  w.hitAfter=list[i-1] and list[i-1].activeEnd;list[i]=w
 end
 byCount=byCount or {};byCount[n]=list;phaseWindows[at]=byCount
 return list
end
-- A combo's hit units: per phase its def, window and hit memory, so a player is hit at most once
-- per phase (and can be hit again by the next one). A borrowed window of the same shape as the phase
-- before it (a second sweep on one timed swing) shares that phase's hit memory, so the one swing
-- never hits a player twice.
function X.phases(def,at)
 local windows=X.phaseWindows(def,at);if not windows then return nil end
 local list={}
 for i,w in windows do
  local P={def=X.merged(def,def.phases[i]),at=w,hits={},ticks={},fired=false};local prev=list[i-1]
  if w.borrowed and prev and prev.def.shape==P.def.shape then P.hits,P.ticks=prev.hits,prev.ticks end
  list[i]=P
 end
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
-- One hit unit's held shapes in frame f (a combo phase or a lane's finish part): a sweep's arc
-- (P.arc), a wave's lines (P.lines: one, or enraged one per `fan` degree, as the Stomp; P.line the
-- middle one). Returns its warning shape: the shape, or a wave's middle line.
function X.place(P,f,fan)
 local def,at=P.def,P.at
 if def.shape=='wave' then
  P.lines={};for _,deg in fan or {0} do table.insert(P.lines,X.wave(def,at,f,math.rad(deg))) end
  P.line=P.lines[math.ceil(#P.lines/2)];return P.line
 end
 local shape=X.shapeOf(def,at,f);if def.shape=='sweep' then P.arc=shape end
 return shape
end
-- What clients get for one hit unit (MapBossAttackData phases[i], finish.parts[i]): its warning shape
-- and a wave's lines (encoded); the caller adds its times.
function X.unitData(P,shape)
 local d={shape=shape and Shapes.encode(shape)}
 if P.lines then d.lines={};for i,l in P.lines do d.lines[i]=Shapes.encode(l) end end
 return d
end
-- After an aim turn: the shapes an attack holds, rebuilt from its new frame (a sweep's arc, a wave's
-- lines, each combo phase's arc or lines). A wave keeps the fan it committed with (A.fan, M.start): an
-- enrage mid-attack never adds lines the clients weren't warned about. Circles are built from the
-- frame when they hit anyway, so nothing is built for them here.
function X.reshape(A,f)
 local def,at=A.def,A.at
 if A.phases then
  for _,P in A.phases do if P.def.shape=='sweep' or P.def.shape=='wave' then X.place(P,f,A.fan) end end
 elseif def.shape=='sweep' then A.arc=X.sweepArc(def,at,f)
 elseif def.shape=='wave' then
  A.lines={};for _,deg in A.fan or {0} do table.insert(A.lines,X.wave(def,at,f,math.rad(deg))) end;A.line=A.lines[math.ceil(#A.lines/2)]
 end
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
 elseif def.shape=='wave' and age>=at.impact and def.facing=='forward' then
  -- The Hammer's rubble: the front crossing each player between samples (X.waveCross), per line,
  -- from their along-distance last step (P.prev[line index][player]).
  local prev=P.prev;if not prev then prev={};P.prev=prev end
  for _,e in people do
   for li,line in P.lines do
    local seen=prev[li];if not seen then seen={};prev[li]=seen end
    local crossed,along=X.waveCross(def,at,line,e.at,seen[e.player],t0,age);seen[e.player]=along
    if crossed and not P.hits[e.player] and strike(e,line.origin+Vector3.yAxis*2,line.origin) then P.hits[e.player]=true end
   end
  end
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
-- A lane's finish (def.finish: one circle, or the Hammer's list {slam circle, rubble wave}): the end
-- clip's own timing, measured from where the run ends (cf moved `length` along dir) on the floor at
-- groundY. Its clip starts at the lane window's activeEnd (X.laneTiming); part i is timed by the clip's
-- phase i (MapBossShapes.partWindow). Returns the clip's timing and the frame; nil without timing.
function X.finishFrame(def,T,cf,dir,length,groundY)
 local at=T.attacks and def.clips and T.attacks[def.clips[3]];if not at then return nil end
 return at,X.frame(cf+dir*length,T,groundY)
end
-- The Hammer-style charge (a forward lane or a contact run): it follows the floor, its length can
-- change, and clients get it as BossChargeLength (MapBossShapes.isCharge).
X.isCharge=Shapes.isCharge
-- A lane's window, duration and data for its current length: the warning, and the finish slam where
-- the run ends (on the end floor, A.endGround, once he has stopped). The contact run re-times it on
-- every change, so the server's hits stay exact. The times are MapBossShapes.laneTimes, which the
-- client re-times its charge with. A homing run (A.pos, def.home): the lane and the finish go on
-- from where the body is now, along its heading.
function X.laneTiming(T,A)
 local def=A.def;local t=Shapes.laneTimes(def,T,A.length)
 A.at,A.duration=t.at,t.duration
 local cf,f,rest=A.cf,A.frame,A.length
 if A.pos then cf=CFrame.lookAt(A.pos,A.pos+A.dir);f=X.frame(cf,T,A.ground);rest=A.length-A.travelled end
 A.data.length=A.length;A.data.shape=Shapes.encode(X.laneShape(f,A.dir,rest,def.width,X.laneSide(A.dir,def)))
 -- The finish hits: A.finishes (X.finishUnits), or an older caller's single A.finish.
 local list=A.finishes or (A.finish and {A.finish})
 if not list then return end
 local fa,frame=X.finishFrame(def,T,cf,A.dir,rest,A.endGround or A.ground)
 for i,F in list do F.at,F.frame,F.start=fa and Shapes.partWindow(fa,i),frame,A.at.activeEnd end
 local F=list[1]
 if F.at then
  -- data.finish.shape/impact: the first part (the slam circle) as before. A list's parts
  -- (X.publishParts) are only rebuilt when the data goes out: at the commit and the stop.
  local parts=A.data.finish and A.data.finish.parts;local shape=X.shapeOf(F.def,F.at,F.frame)
  A.data.finish={shape=shape and Shapes.encode(shape),impact=t.finishImpact,parts=parts}
 end
end
-- A lane's finish hit units (M.start): one per part (MapBossShapes.finishParts), each with its own hit
-- memory; A.finish the first, A.finishes all of them, A.listed when def.finish is a list. A wave part
-- is `detached`: its front runs on its own clock (X.stepWave), not the attack's.
function X.finishUnits(A)
 local def=A.def;local units={}
 for i,part in Shapes.finishParts(def) do local U={def=X.merged(def,part),hits={},ticks={},fired=false};U.detached=U.def.shape=='wave' or nil;units[i]=U end
 A.finish,A.finishes,A.listed=units[1],units,def.finish[1]~=nil
 return units
end
-- A finish list's parts for clients (data.finish.parts), built only when the data goes out (M.start and
-- X.stopCharge): each part's shape, a wave's lines (A.fan, where the run ends: also the lines its hits
-- use, final at the stop), `after` (seconds from the run's end to its hit) and impact (attack clock).
function X.publishParts(A)
 if not (A.listed and A.data.finish) then return end
 local parts={}
 for i,P in A.finishes do
  if P.at then
   local shape=P.def.shape=='wave' and X.place(P,P.frame,A.fan) or X.shapeOf(P.def,P.at,P.frame)
   local d=X.unitData(P,shape);d.after=P.at.impact;d.impact=P.start+P.at.impact;parts[i]=d
  end
 end
 A.data.finish.parts=parts
end
-- A charge that has stopped: the finish slam lands on the floor where he ended (A.endGround), and the
-- data says when the run ended on the server clock (stoppedAt = start + the final window's activeEnd,
-- which is also the finish's clock). Clients start ChargeSlam from it, not from their own prediction,
-- which runs on a BossChargeLength that arrives late and in 0.5-stud steps.
function X.stopCharge(T,A) A.endGround=A.floorY;X.laneTiming(T,A);X.publishParts(A);A.data.stoppedAt=A.start+A.at.activeEnd end
-- A combo at commit (M.start): its hit units placed in frame f (a wave with the commit's fan, A.fan),
-- their warnings (data.phases; data.shape the first, for older readers), and the attack's duration:
-- its recovery, stretched for a phase that hits later (X.duration), but never for a wave phase, whose
-- front runs on its own clock after he is released (X.stepWave). The cyclops's Stomp (no phases)
-- keeps its own stretch. Returns the units.
function X.commitPhases(A,f)
 A.phases=X.phases(A.def,A.at);A.data.phases={}
 for i,P in A.phases do
  local shape=X.place(P,f,A.fan)
  if P.def.shape=='wave' then P.detached=true else A.duration=math.max(A.duration,X.duration(P.def,P.at)) end
  local d=X.unitData(P,shape);d.warnStart,d.impact,d.activeEnd=P.at.warnStart,P.at.impact,P.at.activeEnd
  A.data.phases[i]=d
 end
 A.data.shape=A.data.phases[1].shape
 return A.phases
end
-- One detached wave (s.waves: a wave phase or finish part, handed over at the commit): its hits on its
-- own clock, the attack's start (W.start) plus a finish's run end (P.start), whether the attack is
-- still under way or not. True once its front is past the far end. M.step drops every wave on the
-- boss's death, a pause or the zombies switched off; a new attack never ends one.
function X.stepWave(W,now,people,strike)
 local P=W.P;local age=now-W.start-(P.start or 0)
 if not P.at then return now-W.start>30 end
 local t0=W.t0 or age;W.t0=age
 X.stepHits(P,nil,age,t0,people,strike)
 return age>=Shapes.hitEnd(P.def,P.at)+.05
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
-- Round 10 ring (def.shape 'ring', MapBossShapes.ringHit): from def.point on the ground at impact, with
-- def.gaps openings def.gapWidth radians wide (each side) at evenly spaced yaws turned by `spin`
-- (random per slam, so the way through moves). Pure.
function X.ring(def,at,f,spin)
 local gaps={}
 for i=1,def.gaps or 0 do gaps[i]=Shapes.wrap((spin or 0)+(i-1)*2*math.pi/def.gaps) end
 return {center=X.onGround(f,X.point(f,at,def.point,at.impact)),inner=def.inner,outer=def.outer,travel=def.travel,width=def.width,height=def.height,gaps=gaps,gap=def.gapWidth or math.rad(14)}
end
-- One ring step: players the front crossed between clip times t0 and age, once each.
function X.stepRing(A,age,t0,people,strike)
 local ring,impact=A.ring,A.at.impact;if not ring or age<impact then return end
 for _,e in people do
  if not A.hits[e.player] and Shapes.ringHit(ring,e.at,t0-impact,age-impact) and strike(e,ring.center+Vector3.yAxis*2) then A.hits[e.player]=true end
 end
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
 local rage=s.enraged and s.def.enrage or {}
 -- The wave fan this attack commits with (enraged: rage.fan): its aim turns (X.reshape) keep it, so an
 -- enrage mid-attack never adds lines the clients weren't warned about.
 A.fan=rage.fan
 if def.shape=='lane' then
  -- Clamped short of a wall at body height; the body travels at `speed` after RushStart.
  -- def.contact: the run ends with his root `contact` studs short of the target, and follows them
  -- down the lane (stepAttack, X.contactLength). def.finish: the closing slam, its own hit memory,
  -- so a player hit by the run can be hit by the slam too.
  A.dir=laneDir;local wall=workspace:Raycast(cf.Position,A.dir*def.length,params)
  A.limit=wall and math.max(0,wall.Distance-math.min(8,s.T.footprintRadius or 4)/2-1) or def.length;A.travelled=0
  A.length=def.contact and X.contactLength(def,cf,A.dir,Vector3.new(goal.X,cf.Y,goal.Z),A.limit,A.limit,0) or A.limit
  A.target=def.contact and target or nil
  -- A finish (the Hammer's slam circle and rubble wave): one hit unit per part, each timed by the end
  -- clip's phase (X.laneTiming, X.finishUnits).
  if def.finish then X.finishUnits(A) end
  -- def.home (the Hammer): a homing run. The body and its heading live in A.pos / A.dir (stepAttack).
  if def.home and def.facing=='forward' then A.pos,A.sentDir,A.homeTarget=cf.Position,A.dir,target end
  A.data={dir={A.dir.X,A.dir.Z}};X.laneTiming(s.T,A);X.publishParts(A)
 else A.at=X.window(def,s.T);A.duration=X.duration(def,A.at) end
 local at=A.at
 if def.phases then
  -- Every phase's warning goes out at commit (data.phases; the client fills a later one in as its
  -- hit nears). A wave phase (the Hammer's rubble) also sends its lines (A.fan, like the Stomp) and
  -- runs on its own clock (X.commitPhases, s.waves), so he is released at the clip's recovery.
  X.commitPhases(A,f)
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
 if def.shape=='ring' then A.ring=X.ring(def,at,f,math.random()*2*math.pi);A.data.ring=Shapes.encodeRing(A.ring) end -- round 10
 A.data.rate=def.rate or 1
 -- def.aim (the boss def's, or the attack's own): the frame turns toward the target until each hit's
 -- lock (stepAttack). data.yaw is the frame's heading the shapes were built in: clients turn them by
 -- the BossFrame they get.
 local aim=(def.phases or def.shape=='circle' or def.shape=='sweep' or def.shape=='wave') and (def.aim or s.def.aim) or nil
 if aim then A.aim,A.aimTarget,A.sentYaw=aim,target,Shapes.yawOf(cf);A.data.yaw=A.sentYaw end
 s.attack=A;s.lastStart[kind]=now -- def.lockout (X.lockedOut)
 -- Detached waves (a wave phase, a finish wave) go on their own clock now: stepWaves runs them every
 -- Heartbeat, through and after this attack.
 for _,list in {A.phases or NONE,A.finishes or NONE} do for _,P in list do if P.detached then table.insert(s.waves,{P=P,start=now}) end end end
 npc:SetAttribute('BossAttack',kind);npc:SetAttribute('BossStart',now);npc:SetAttribute('BossFrame',cf);npc:SetAttribute('BossGroundY',f.groundY);npc:SetAttribute('BossDuration',A.duration)
 -- A charge's length (X.isCharge) changes as he runs. Client contract: re-time the end clip from
 -- BossChargeLength, falling back to data.length. It is set before BossSerial, so no client reads
 -- the last charge's value; stepAttack sends it on 0.5-stud changes, and exactly when he stops.
 if X.isCharge(def) then A.sentLength=A.length;npc:SetAttribute('BossChargeLength',A.length) end
 -- A homing run's heading (stepAttack): none until it turns, never the last charge's.
 if A.pos then npc:SetAttribute('BossChargeHead',nil);npc:SetAttribute('BossChargeHeadAt',nil) end
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
 local s={id=id,def=def,T=T,next=workspace:GetServerTimeNow()+Defs.FIRST_ATTACK,index=0,lastHealth=h.Health,stop=def.stop or math.min(8*scale,T.footprintRadius or 4)+3,follows={},waves={},followSerial=0,
  lastStart={},tutorial=tutorial or nil};M.states[npc]=s
 if intro then
  -- The entrance (BossService's, from def.intro): rumble and a growing shadow for `drop`, the fall,
  -- then the landing and camera orbit (BossIntro.client) for `after`. The intro clip is timed so
  -- its impact meets the ground at BossIntroLand; it deals no damage (no s.attack). Until
  -- BossIntroUntil he can't be hurt (CombatEffectsService) and stands anchored, and CinematicUntil
  -- holds the players (CharacterService.frozen) and the enemies (RogueliteZombieChase).
  -- Round 10 / unique intros: intro.lead (seconds to the key moment) for styles other than the sky
  -- drop, and opts.eventIntro {land, done} when a round 10 event times the leader inside its own
  -- cinematic. BossIntroStyle tells BossIntro.client which entrance to film (nil: the sky drop).
  local now=workspace:GetServerTimeNow()
  local land=opts.eventIntro and opts.eventIntro.land or now+(intro.lead or (intro.drop or 0)+(intro.fall or 0))
  local done=opts.eventIntro and opts.eventIntro.done or land+intro.after
  npc:SetAttribute('BossIntroStyle',intro.style)
  local clip=T.attacks and T.attacks[intro.clip]
  npc:SetAttribute('BossIntroStart',now);npc:SetAttribute('BossIntroLand',land);npc:SetAttribute('BossIntroUntil',done)
  if def.introName then npc:SetAttribute('BossIntroName',def.introName) end
  npc:SetAttribute('BossAttack',intro.clip);npc:SetAttribute('BossStart',land-(clip and Shapes.impactOf(clip) or 0));npc:SetAttribute('BossFrame',root.CFrame)
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
-- One hit unit's hits this step (X.stepHits): the attack itself, a combo phase or a finish part. A
-- circle that fired brings its follow-up (none in the tutorial).
local function stepUnit(npc,s,A,P,f,age,t0,now,root,params,people)
 if X.stepHits(P,f,age,t0,people,function(e,from,source) return hit(npc,P.def,e,from,params,source) end) and P.def.follow and X.allows(s,'follow') then
  queueFollow(npc,s,A,P,now,root,params,people)
 end
end
-- Detached waves (X.stepWave): every Heartbeat, during an attack or not, until each front is out.
local function stepWaves(npc,s,now,params,people)
 for i=#s.waves,1,-1 do
  local W=s.waves[i]
  if X.stepWave(W,now,people,function(e,from,source) return hit(npc,W.P.def,e,from,params,source) end) then table.remove(s.waves,i) end
 end
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
  local length
  if A.pos then
   -- Homing: measured along the current heading from where the body is now, and capped by the wall
   -- ahead of it on that heading (the run so far counts toward def.length).
   local wall=workspace:Raycast(A.pos,A.dir*math.max(.1,def.length-A.travelled),params)
   local cap=wall and math.max(0,wall.Distance-math.min(8,s.T.footprintRadius or 4)/2-1) or def.length-A.travelled
   length=A.travelled+math.min(cap,X.contactLength(def,CFrame.new(A.pos),A.dir,A.target.Position,cap,A.length-A.travelled,0))
  else length=X.contactLength(def,A.cf,A.dir,A.target.Position,A.limit,A.length,A.travelled) end
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
 local aim=A.aim
 if aim then
  -- Aim (X.aimStep): the frame, the body and every shape it holds turn toward the target until the
  -- next hit's lock. Clients get BossFrame once it has turned 1 degree, and exactly at the lock.
  local target=A.aimTarget and A.aimTarget.Parent and A.aimTarget or nil
  if not target then local best=math.huge;for _,e in people do local d=(e.root.Position-A.cf.Position).Magnitude;if d<best then target,best=e.root,d end end end
  if X.aimStep(A,age,age-t0,target and target.Position,aim) then A.frame=X.frame(A.cf,s.T,A.ground);f=A.frame;X.reshape(A,f) end
  local yaw=Shapes.yawOf(A.cf)
  if X.frameDue(A.sentYaw,yaw,not X.aimOpen(A,age,aim.lock)) then A.sentYaw=yaw;npc:SetAttribute('BossFrame',A.cf) end
 end
 if def.shape=='lane' and A.pos then
  -- Homing (def.home): the heading turns toward the target as he runs and the body follows it; the
  -- body hit sweeps each step's segment of the real path. Clients get the heading as BossChargeHead
  -- (on the ground where the body was, facing it) and BossChargeHeadAt (the distance run there) once
  -- it has turned 1 degree.
  local travel=math.clamp((age-at.impact)*def.speed,0,A.length)
  if travel>A.travelled then
   local goal=A.homeTarget and A.homeTarget.Parent and A.homeTarget.Position or nil
   local a,b=X.homeStep(A,def,goal,age-t0,travel)
   local floor=workspace:Raycast(b+Vector3.yAxis*6,-Vector3.yAxis*(s.T.rootHeight+14),params)
   if floor then A.floorY=floor.Position.Y end
   local body=X.pathBody(def,a,b,A.floorY or f.groundY)
   for _,e in people do
    if not A.hits[e.player] and Shapes.contains(body,e.at) and hit(npc,def,e,b,params,body.b) then A.hits[e.player]=true end
   end
   if X.headDue(A.sentDir,A.dir) then
    A.sentDir=A.dir;local g=Vector3.new(A.pos.X,A.ground,A.pos.Z)
    npc:SetAttribute('BossChargeHeadAt',A.travelled);npc:SetAttribute('BossChargeHead',CFrame.lookAt(g,g+A.dir))
   end
  end
  root.CFrame=CFrame.lookAt(A.pos,A.pos+A.dir).Rotation+Vector3.new(A.pos.X,A.floorY and A.floorY+s.T.rootHeight or A.cf.Y,A.pos.Z)
  if travel>=A.length and not A.stopped then
   A.stopped=true;X.stopCharge(s.T,A)
   A.sentLength=A.length;npc:SetAttribute('BossChargeLength',A.length);publish(npc,A);npc:SetAttribute('BossDuration',A.duration)
  end
 elseif def.shape=='lane' then
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
    -- Stopped (X.stopCharge): late readers get the exact final length, warning, finish, duration
    -- and stoppedAt: the run's one data republish.
    X.stopCharge(s.T,A)
    A.sentLength=A.length;npc:SetAttribute('BossChargeLength',A.length);publish(npc,A);npc:SetAttribute('BossDuration',A.duration)
   end
  end
 else root.CFrame=A.cf end
 -- Circle, wave, breath and sweep hits (X.stepHits): the attack itself, or each combo phase with
 -- its own hit memory. A circle that fired brings its follow-up (none in the tutorial).
 -- A detached wave phase runs in stepWaves instead.
 if A.phases then
  for _,P in A.phases do if not P.detached then stepUnit(npc,s,A,P,f,age,t0,now,root,params,people) end end
 else stepUnit(npc,s,A,A,f,age,t0,now,root,params,people) end
 -- A lane's finish slam, on the end clip's clock (it starts where the run ends, F.start). Each part has
 -- its own hit memory; a finish wave runs in stepWaves.
 for _,F in A.finishes or NONE do
  if F.at and not F.detached then stepUnit(npc,s,A,F,F.frame,age-F.start,t0-F.start,now,root,params,people) end
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
 if def.shape=='ring' then X.stepRing(A,age,t0,people,function(e,from) return hit(npc,def,e,from,params,from) end) end -- round 10
 local impact=at.impact or A.phases and A.phases[1].at.impact
 if impact and age>=impact and not A.impacted then A.impacted=true;npc:SetAttribute('BossImpactStart',now);local hook=M.hooks[npc];if hook then task.spawn(hook,A.kind,A,now) end end
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
 if not h or not root or h.Health<=0 then s.attack=nil;s.shots=nil;table.clear(s.follows);table.clear(s.waves);return end
 -- The sky-drop entrance (def.intro, M.spawn): stand still until it's over, then fight.
 if s.intro then
  if now<s.intro then h:Move(Vector3.zero);return end
  s.intro=nil;npc:SetAttribute('BossStart',nil);release(npc,h,root)
 end
 if combat:GetAttribute('ZombiesEnabled')~=true then
  s.attack=nil;s.shots=nil;table.clear(s.follows);table.clear(s.waves);npc:SetAttribute('BossStart',nil);release(npc,h,root);h:Move(Vector3.zero);return
 end
 -- Pause (plan L): a paused run cancels the attack under way, its shots and follow-ups, and
 -- holds still. Attacks start fresh (with their wind-up) once the run unfreezes.
 if combat:GetAttribute('RunPaused')==true then
  if s.attack then s.attack=nil;npc:SetAttribute('BossStart',nil);release(npc,h,root) end
  s.shots=nil;table.clear(s.follows);table.clear(s.waves);h:Move(Vector3.zero);h:MoveTo(root.Position);return
 end
 checkEnrage(npc,s,h)
 local params,people=exclusions(npc),living()
 stepShots(npc,s,now,params,people)
 stepFollows(npc,s,now,params,people)
 stepWaves(npc,s,now,params,people)
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
