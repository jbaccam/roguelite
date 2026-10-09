-- Client: map-boss animation, ground warnings and effects (plan F). Follows the Hammer
-- BossPresentation: sampled Bone.Transform clips with priority Death > attack > Hit > Walk/Idle,
-- and warnings drawn from the server's MapBossAttackData through MapBossShapes, the same shapes
-- the server hit-tests. Effects come from BossVfx/<BossId>. Visual only.
-- Hammer Brute runtime (MapBossService R1-R3, client R4, 2026-10-03). Each path below only runs
-- when the server sends its data, so the four older bosses take exactly the old code:
--   combos (def.phases, data.phases): every phase's warning from the commit, each filled on its own
--     timing; a later phase starts faint (P.phaseAlpha). VFX read ctx.phases / C.phaseShape.
--   the forward charge (P.isCharge): re-timed from BossChargeLength (else data.length); the lane
--     reshaped in place and the finish circle (data.finish) moved down it as the run grows. It runs
--     until the server's stop (data.stoppedAt, P.chargeStop), then ChargeSlam from that stop.
--   pseudo attacks (P.pseudo): the intro clip (def.intro.clip, timed to BossIntroLand; before
--     BossIntroUntil even when it is also an attack's clip) and the enrage roar (def.roar): the clip
--     only, no warning or attack hooks.
--   aim (data.yaw, MapBossService def.aim): the frame turns toward the target until each hit's lock;
--     the warning turns in place with BossFrame (turnWarning) and C.shape / C.phaseShape turn with it.
--   homing (def.home): the lane runs from the body on along BossChargeHead (P.homeRun).
--   the intro hook fires at BossIntroLand; with a roar, the enrage hook fires as the roar starts.
--   new hook `followup` when follow-up circles appear (their eruption is still `aftershock`), and
--     `roar` as each roar starts (its peak; a roar a pause cancelled is played again with it).
-- Rubble waves (2026-10-09): a wave phase (the Hammer's Slam and SpinSlam) and a charge's finish wave
--   (data.finish.parts) warn their lines (one, or the enraged fan) like the Stomp. VFX contract:
--     ctx.phases[i].lines  a wave phase's lines as published (decoded; C.phaseShape(ctx,i) is the middle one,
--                          turned to the current frame)
--     ctx.waves()          every wave of this attack now: {key, def (length, width, travel, damage),
--                          impact (attack clock; a finish's nil until the stop is known), lines (turned
--                          to the boss's current frame / moved with the run), finish (true for the charge's)}
--     hook wave(ctx,unit)  once per wave as its front leaves the impact point (unit as in ctx.waves()):
--                          the front reaches `d` studs down each line at unit.impact + d / unit.def.travel.
local Tags=game:GetService('CollectionService')
local Run=game:GetService('RunService')
local Players=game:GetService('Players')
local Http=game:GetService('HttpService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Shapes=require(combat:WaitForChild('MapBossShapes'))

-- Pure helpers (P): timing and warning geometry. MapBossPresentationTests runs them in Edit through
-- tools/RepoRequire, which runs this file's repo text: it returns P before anything client-side.
local P={}
-- The server's windows (MapBossShapes.window): the rush is RushStart, travel at speed, then RushEnd.
-- The timing from MapBossDefs.timing is already scaled and rate-adjusted (real seconds, final studs).
-- A pseudo attack (P.pseudo) is its clip's timing, or just its length from T.clips.
function P.window(a,T,length)
 if a.pseudo then
  local at=T.attacks and T.attacks[a.clip];if at then return at end
  local d=T.clips and T.clips[a.clip];return d and {warnStart=0,impact=0,activeEnd=0,recoveryEnd=d,duration=d} or nil
 end
 return Shapes.window(a,T,length)
end
-- BossAttack names a clip that is no attack: the def's intro clip (MapBossService spawn) or its
-- enrage roar (startRoar). Played like an attack at rate 1; nil for anything else. The intro's clip
-- can also be an attack's (the Hammer lands on his Slam): during the intro (inIntro: BossStart before
-- BossIntroUntil) it is the intro, otherwise the attack.
function P.pseudo(def,kind,inIntro)
 local attack=def.attacks and def.attacks[kind]
 if def.intro and kind==def.intro.clip and (inIntro or not attack) then return {clip=kind,rate=1,pseudo='intro'} end
 if def.roar and kind==def.roar and not attack then return {clip=kind,rate=1,pseudo='roar'} end
 return nil
end
-- A homing run (def.home, MapBossService X.homeStep) as the client knows it: the body goes straight
-- on from the last heading the server sent (BossChargeHead, a ground CFrame facing it, and
-- BossChargeHeadAt, the distance run there; before any, the commit: start, dir0, 0). Returns the body
-- `travelled` along the path, the heading, and the run's end `length` along.
function P.homeRun(start,dir0,head,headAt,length,travelled)
 local from,dir,at0=start,dir0,0
 if typeof(head)=='CFrame' and type(headAt)=='number' then
  local d=Shapes.flat(head.LookVector);if d.Magnitude>1e-3 then from,dir,at0=Vector3.new(head.X,start.Y,head.Z),d.Unit,headAt end
 end
 return from+dir*math.max(0,travelled-at0),dir,from+dir*math.max(0,length-at0)
end
-- Shared with MapBossService (MapBossShapes): the attack def with a phase's (or a finish's) fields on
-- top; whether it is the Hammer-style charge, whose length changes as he runs; and a lane's times for
-- a length (its window, duration and finish times), which the charge is re-timed with.
P.merged,P.isCharge,P.laneTimes=Shapes.merged,Shapes.isCharge,Shapes.laneTimes
-- Where the charge's run ends on the attack clock, and whether that is a guess. The server's stop
-- ends it: the data's stoppedAt (MapBossService X.stopCharge), as `confirmed`. The predicted end
-- (the window's activeEnd from BossChargeLength) runs late, since that length arrives after a latency
-- and in 0.5-stud steps, so with no stop CHARGE_HOLD s past it (a long stall, or a server without
-- stoppedAt) the run ends now, a guess: ChargeSlam from its first frame, its impact still ahead.
-- `latched`/`guessed`: the end already in use. A confirmed stop replaces a later end, and re-anchors a
-- guess while the slam's impact (slamAt after it) is still ahead; it is already past when it arrives,
-- so min(confirmed, age) keeps ChargeSlam. Nothing ever goes back to ChargeRun. nil: still running.
P.CHARGE_HOLD=.75
function P.chargeStop(latched,guessed,predicted,confirmed,age,slamAt)
 if confirmed and (not latched or confirmed<=latched) then return confirmed,false end
 if confirmed and guessed and age<latched+(slamAt or 0) then return math.min(confirmed,age),false end
 if latched then return latched,guessed end
 if age>=predicted+P.CHARGE_HOLD then return age,true end
 return nil,false
end
-- The charge's clip at `age`: 1 ChargeStart, 2 ChargeRun, 3 ChargeSlam (then also its clip time,
-- from the run's end at the attack's rate).
function P.chargePhase(impact,stop,age,rate)
 if age<impact then return 1 end
 if not stop or age<stop then return 2 end
 return 3,(age-stop)*(rate or 1)
end
-- A wave's lines from its data (lines: a list of encoded lines, the enraged fan), decoded; nil without.
function P.lines(d)
 if type(d)~='table' or type(d.lines)~='table' then return nil end
 local list={};for _,l in d.lines do if type(l)=='table' then local s=Shapes.decode(l);if s.kind=='line' then table.insert(list,s) end end end
 return #list>0 and list or nil
end
-- A combo's phases from MapBossAttackData.phases (the server's times and shapes), falling back to
-- the clip's own phase timing: {index, def (merged), warnStart, impact, activeEnd, shape (decoded),
-- lines (a wave phase's, decoded)}. nil unless the def has phases and every phase has an impact (then
-- the old single-shape path).
function P.phases(a,data,T)
 if type(a.phases)~='table' or type(data.phases)~='table' then return nil end
 local at=T.attacks and T.attacks[a.clip];local list={}
 for i,part in a.phases do
  local d=type(data.phases[i])=='table' and data.phases[i] or {};local w=at and at.phases and at.phases[i] or {}
  local impact=d.impact or w.impact;if type(impact)~='number' then return nil end
  list[i]={index=i,def=P.merged(a,part),warnStart=d.warnStart or w.warnStart or 0,impact=impact,activeEnd=d.activeEnd or w.activeEnd or impact,
   shape=type(d.shape)=='table' and Shapes.decode(d.shape) or nil,lines=P.lines(d)}
 end
 return list
end
-- A charge's finish waves from data.finish.parts (MapBossService X.laneTiming): {index, def (merged),
-- after (seconds from the run's end to its hit), lines (decoded, where the server put them for the
-- published length)}, for each part with lines; nil without any.
function P.finishWaves(a,data)
 local f=type(data.finish)=='table' and data.finish;local parts=f and type(f.parts)=='table' and f.parts
 if not parts or type(a.finish)~='table' or a.finish[1]==nil then return nil end
 local list={}
 for i,d in parts do
  local lines=P.lines(d)
  if lines and type(d.after)=='number' and type(a.finish[i])=='table' then table.insert(list,{index=i,def=P.merged(a,a.finish[i]),after=d.after,lines=lines}) end
 end
 return #list>0 and list or nil
end
-- A shape carried from one ground frame to another (a homing run's finish follows where the run now
-- ends): its points and directions, frame-relative, placed in `to`.
function P.carried(shape,from,to)
 local s=table.clone(shape)
 for _,k in {'center','origin'} do if typeof(shape[k])=='Vector3' then s[k]=to:PointToWorldSpace(from:PointToObjectSpace(shape[k])) end end
 if typeof(shape.direction)=='Vector3' then s.direction=to:VectorToWorldSpace(from:VectorToObjectSpace(shape.direction)) end
 return s
end
-- A combo clip's own window may lack impact or activeEnd (MapBossService reads phase 1's impact):
-- fill them from the phases, so the attack hooks run from the first hit to the last.
function P.comboWindow(at,list)
 if at.impact and at.activeEnd and at.warnStart then return at end
 local w=table.clone(at);w.warnStart=w.warnStart or 0;w.impact=w.impact or list[1].impact;w.activeEnd=w.activeEnd or list[#list].activeEnd
 return w
end
-- A later combo phase (or the charge's finish) starts at 35% alpha and fills to full by its
-- impact - 0.35 s, so the hit that comes first reads first. The first phase is always full.
function P.phaseAlpha(later,age,warnStart,impact)
 if not later then return 1 end
 return .35+.65*math.clamp((age-warnStart)/math.max(.05,impact-.35-warnStart),0,1)
end
-- A layer's transparency at alpha (1 = as painted; nil or 1 leaves it exactly as it was).
function P.fade(t,alpha) if not alpha or alpha>=1 then return t end;return 1-(1-t)*alpha end
-- A sweep reaching all the way round (MapBossService X.sweepArc: from=-pi, to=pi).
function P.fullRing(shape) return shape.kind=='arc' and shape.to-shape.from>=2*math.pi-1e-3 end
-- Closed outlines for the warning edge. A full ring is its outer circle (and inner, if any) with no
-- seam back to the pivot: Shapes.outline closes an arc radially. Anything else: Shapes.outline.
function P.edgeLoops(shape,n)
 if not P.fullRing(shape) then return {Shapes.outline(shape,n)} end
 local loops={Shapes.outline({kind='circle',center=shape.pivot,radius=shape.outer},n)}
 if (shape.inner or 0)>.05 then table.insert(loops,Shapes.outline({kind='circle',center=shape.pivot,radius=shape.inner},n)) end
 return loops
end
-- The charge lane (a line published for baseLength) at its current length: same start and width.
function P.laneAt(base,baseLength,length) local s=table.clone(base);s.length=base.length+(length-baseLength);return s end
-- A shape moved `by` studs along dir (the finish circle, and a finish wave's lines, follow the end of
-- the run).
function P.moved(shape,dir,by)
 local s=table.clone(shape)
 if shape.center then s.center=shape.center+dir*by end;if shape.origin then s.origin=shape.origin+dir*by end
 return s
end
if not Run:IsRunning() then return P end -- Edit (the tests): helpers only

local EnemyMotion=require(combat:WaitForChild('EnemyMotion'))
local Defs=require(combat:WaitForChild('MapBossDefs'))
local Maps=require(combat:WaitForChild('MapConfig'))
local animations=combat:WaitForChild('BossAnimations')
local vfxFolder=combat:WaitForChild('BossVfx')
local Common=require(vfxFolder:WaitForChild('Common'))
local player=Players.LocalPlayer
local MAX_GAIT_RATE=2.6 -- Walk clip seconds per real second (chase speeds outrun the authored walk)
local FILL,EDGE=.78,.2
local TINT={KingCrab=Color3.fromRGB(255,120,90),Pharaoh=Color3.fromRGB(255,200,80),FrostCyclops=Color3.fromRGB(140,220,255),Dragon=Color3.fromRGB(255,110,40)}
TINT.DJCrab,TINT.TombWarden,TINT.BloodAlpha=Color3.fromRGB(255,96,140),Color3.fromRGB(255,170,70),Color3.fromRGB(255,70,70) -- round 10 leaders
local tracked,compiled,modules={},{},{}
local function decode(raw) local ok,t=pcall(Http.JSONDecode,Http,raw or '');return ok and type(t)=='table' and t or {} end
local function clipDuration(motion,name) local c=motion.clips[name];return c and c.duration or 1 end
-- EnemyMotion.compile asserts Idle, Move and Attack: alias Walk -> Move and the first attack -> Attack.
-- compile builds a clip listed under two names once and shares the result.
local function aliased(anim,source)
 local raw=require(source);local data=table.clone(raw);data.clips=table.clone(raw.clips)
 data.clips.Move=data.clips.Move or data.clips.Walk;data.clips.Attack=data.clips.Attack or data.clips[Defs.ATTACK_CLIPS[anim][1]]
 return data
end
local function load(anim)
 if compiled[anim]~=nil then return compiled[anim] or nil end
 local source=animations:FindFirstChild(anim);if not source then return nil end
 local ok,result=pcall(function() return EnemyMotion.compile(aliased(anim,source)) end)
 if not ok then warn('MapBossPresentation: '..anim..' animations failed: '..tostring(result)) end
 compiled[anim]=ok and result or false;return compiled[anim] or nil
end
local function vfxFor(id)
 if modules[id]==nil then
  local m=vfxFolder:FindFirstChild(id);local ok,r=true,Common
  if m then ok,r=pcall(require,m) end
  if not ok then warn('MapBossPresentation: BossVfx.'..id..' failed: '..tostring(r)) end
  modules[id]=ok and r or Common
 end
 return modules[id]
end
-- MicroProfiler labels (DEVICE_PROFILING.md): a throwing body still closes its label.
local function profiled(label,f,...)
 debug.profilebegin(label)
 local r=table.pack(pcall(f,...))
 debug.profileend()
 if not r[1] then error(r[2],0) end
 return table.unpack(r,2,r.n)
end
local vfxLabels=setmetatable({},{__index=function(t,name) local label='Boss:Vfx:'..name;t[name]=label;return label end})
-- Effects never break the boss: every hook runs protected.
local function call(state,name,...)
 local f=state.vfx[name] or Common[name];if not f then return end
 debug.profilebegin(vfxLabels[name])
 local r=table.pack(pcall(f,...))
 debug.profileend()
 if not r[1] then warn('BossVfx.'..state.id..'.'..name..': '..tostring(r[2]));return end
 return table.unpack(r,2,r.n)
end
local window=P.window
-- The forward charge's current run (P.isCharge), every frame. BossChargeLength (else data.length)
-- re-times the predicted window and moves the lane and the finish circle; the server sends it on
-- 0.5-stud changes and at the stop, when it also republishes the data with stoppedAt. The run ends
-- at P.chargeStop (the server's stop; a guess at now only after a long stall), so:
--   ch.stopAge   the run's end on the attack clock; nil while he is still running (ChargeRun plays on)
--   ch.guessed   stopAge is that guess (a confirmed stop may still re-anchor it)
--   ch.runEnd    the lane warning's end: stopAge, else at least just ahead of now (held while running)
--   ch.finishShow  the finish circle's impact for its warning (runEnd + the slam clip's impact)
--   ch.finishImpact  the finish slam's impact, once the stop is known (nil before)
--   ch.duration  the attacking window: the stop (or the hold past the prediction) plus the slam clip
--                (and a finish wave's travel)
--   ch.waves     a finish list's waves (P.finishWaves): {index, def, after, lines}, the lines where the run
--                now ends; each hits at stopAge + after
-- A homing run (ch.home, def.home): the lane goes from the body on along the heading the server sent
-- (P.homeRun), and the finish circle and waves sit where that ends, turned with it (ch.heading, ch.endPos).
local function chargeStep(npc,ctx,age)
 local ch=ctx.charge;local length=npc:GetAttribute('BossChargeLength')
 if type(length)~='number' then length=ctx.data.length or ctx.def.length end
 if length~=ch.length or ctx.raw~=ch.raw then
  ch.length,ch.raw=length,ctx.raw
  local t=P.laneTimes(ctx.def,ctx.timing,length);ctx.attack=t.at
  ch.predicted,ch.tail,ch.slamAt=t.at.activeEnd,t.duration-t.at.activeEnd,t.finishImpact and t.finishImpact-t.finishStart
  local d=ctx.data;local published=d.length or length
  -- This attack's stop only: stoppedAt from an earlier charge is before this one started.
  ch.confirmed=type(d.stoppedAt)=='number' and d.stoppedAt>=ctx.start-1e-3 and d.stoppedAt-ctx.start or nil
  local lane=type(d.shape)=='table' and Shapes.decode(d.shape);ch.lane=lane and lane.kind=='line' and P.laneAt(lane,published,length) or nil
  local f=type(d.finish)=='table' and type(d.finish.shape)=='table' and Shapes.decode(d.finish.shape)
  ch.finish=f and f.kind=='circle' and ch.slamAt and P.moved(f,ch.dir,length-published) or nil
  -- Homing: the finish's place relative to the end of the straight run it was published for.
  if ch.home and ch.finish and not ch.confirmed and not ch.finishLocal then
   local e=ch.start+ch.dir*published;ch.finishLocal=CFrame.lookAt(e,e+ch.dir):PointToObjectSpace(f.center)
  end
  -- Finish waves (the Hammer's rubble, data.finish.parts): their lines move down the lane with the run's
  -- end like the circle (wv.base and wv.from: as published, for a homing run to carry them).
  ch.waves=ch.finish and P.finishWaves(ctx.def,d) or nil
  local e=ch.start+ch.dir*published
  for _,wv in ch.waves or {} do
   wv.base,wv.from=wv.lines,CFrame.lookAt(e,e+ch.dir)
   local moved={};for j,l in wv.lines do moved[j]=P.moved(l,ch.dir,length-published) end;wv.lines=moved
  end
 end
 if ch.home then
  local travelled=math.clamp(((age or 0)-ctx.attack.impact)*ctx.def.speed,0,length)
  local body,dir,finish=P.homeRun(ch.start,ch.dir,npc:GetAttribute('BossChargeHead'),npc:GetAttribute('BossChargeHeadAt'),length,travelled)
  local w=ctx.def.width;ch.heading,ch.endPos=dir,finish
  ch.lane={kind='line',origin=body-dir*w/2,direction=dir,length=Shapes.flat(finish-body).Magnitude+w,width=w}
  if ch.finish and ch.finishLocal and not ch.confirmed then
   ch.finish=table.clone(ch.finish);ch.finish.center=CFrame.lookAt(finish,finish+dir):PointToWorldSpace(ch.finishLocal)
  end
  -- The finish waves go on from where the run now ends, along its heading (until the stop's data).
  if ch.waves and not ch.confirmed then
   local to=CFrame.lookAt(finish,finish+dir)
   for _,wv in ch.waves do local list={};for j,l in wv.base do list[j]=P.carried(l,wv.from,to) end;wv.lines=list end
  end
 end
 -- The end only moves on this attack's own clock (age nil: no BossStart, or another attack's).
 if age then ch.stopAge,ch.guessed=P.chargeStop(ch.stopAge,ch.guessed,ch.predicted,ch.confirmed,age,ch.slamAt) end
 ch.runEnd=ch.stopAge or math.max(ch.predicted,(age or -math.huge)+.05)
 ch.finishShow=ch.slamAt and ch.runEnd+ch.slamAt or nil
 ch.finishImpact=ch.stopAge and ch.slamAt and ch.stopAge+ch.slamAt or nil
 ch.duration=(ch.stopAge or ch.predicted+P.CHARGE_HOLD)+ch.tail
end
local function context(npc,state,kind,a,start,serial)
 local cf=npc:GetAttribute('BossFrame');if typeof(cf)~='CFrame' then return nil end
 local T=state.T;local raw=npc:GetAttribute('MapBossAttackData');local data=decode(raw)
 local ctx={npc=npc,id=state.id,kind=kind,def=a,serial=serial,start=start,cf=cf,groundY=npc:GetAttribute('BossGroundY') or cf.Y-T.rootHeight,
  timing=T,tint=state.tint,raw=raw,data=data,ground=cf*CFrame.new(0,-T.rootHeight,0),scale=T.scale or 1,enraged=npc:GetAttribute('BossEnraged')~=nil}
 local at=window(a,T,data.length);if not at then return nil end
 ctx.attack=at
 if a.pseudo then ctx.pseudo=a.pseudo
 elseif a.phases then
  ctx.phases=P.phases(a,data,T);if ctx.phases then ctx.attack=P.comboWindow(at,ctx.phases) end
  for _,ph in ctx.phases or {} do if ph.lines then ctx.phaseWaves=true end end
 elseif P.isCharge(a) then
  local d=type(data.dir)=='table' and Vector3.new(data.dir[1],0,data.dir[2]) or Shapes.flat(cf.LookVector)
  ctx.charge={dir=d.Magnitude>1e-3 and d.Unit or Vector3.new(0,0,-1),home=a.home~=nil and a.facing=='forward',start=Vector3.new(cf.X,ctx.groundY,cf.Z)}
  chargeStep(npc,ctx)
 end
 -- ctx.attack, not a local copy: the charge re-times it.
 function ctx.points(name,t)
  local at=ctx.attack;local p=Shapes.sample(at.samples and at.samples[name],t)
  if not p then local fixed=at.points and at.points[name];p=fixed and Vector3.new(table.unpack(fixed.rootAtImpactStudio)) or Vector3.zero end
  return ctx.ground*p
 end
 function ctx.dirAt(name,t)
  local at=ctx.attack;local d=Shapes.sample(at.dirs and at.dirs[name],t) or (at.directionAtImpactStudio and Vector3.new(table.unpack(at.directionAtImpactStudio)))
  return d and d.Magnitude>1e-3 and ctx.ground:VectorToWorldSpace(d).Unit or ctx.cf.LookVector
 end
 -- Every wave of this attack as it stands now (the VFX contract in the header): a wave phase's lines
 -- turned to the frame the boss has now (aim, as C.phaseShape), or a charge's finish waves where the run
 -- ends. A new list each call.
 function ctx.waves()
  local list={}
  if ctx.phases then
   local y=ctx.data.yaw;local turn=type(y)=='number' and Shapes.wrap(Shapes.yawOf(ctx.cf)-y) or 0
   for i,ph in ctx.phases do
    if ph.lines then
     local lines={};for j,l in ph.lines do lines[j]=math.abs(turn)>1e-6 and Shapes.rotated(l,ctx.cf.Position,turn) or l end
     table.insert(list,{key=i,def=ph.def,impact=ph.impact,lines=lines,finish=false})
    end
   end
  elseif ctx.charge and ctx.charge.waves then
   local ch=ctx.charge
   for _,wv in ch.waves do table.insert(list,{key='finish'..wv.index,def=wv.def,impact=ch.stopAge and ch.stopAge+wv.after or nil,lines=wv.lines,finish=true}) end
  end
  return list
 end
 return ctx
end
-- Clip time for an attack at `age` real seconds: the clip plays at the attack's rate.
local function attackClip(ctx,age,motion)
 local a,at=ctx.def,ctx.attack;local rate=a.rate or 1
 if a.shape~='lane' then return a.clip,age*rate end
 -- The Hammer's charge: ChargeRun until the server's stop (chargeStep), one chargeStrideLength of
 -- ground per cycle (without it, the clip at its authored speed); then ChargeSlam from that stop.
 if ctx.charge then
  local phase,slam=P.chargePhase(at.impact,ctx.charge.stopAge,age,rate)
  if phase==1 then return a.clips[1],age*rate elseif phase==3 then return a.clips[3],slam end
  local run=clipDuration(motion,a.clips[2])
  return a.clips[2],(age-at.impact)*a.speed/(ctx.timing.chargeStrideLength or a.speed*run)*run
 end
 if age<at.impact then return a.clips[1],age*rate end
 if age<at.activeEnd then
  -- Loop phase follows the ground covered: one rushStrideLength per RushLoop cycle.
  local travelled=(age-at.impact)*a.speed
  return a.clips[2],travelled/(ctx.timing.rushStrideLength or 2.2)*clipDuration(motion,a.clips[2])
 end
 return a.clips[3],(age-at.activeEnd)*rate
end

-- Ground warnings, three layers per shape: a faint zone fill, a bright edge, and a hotter inner
-- fill that grows out to the edge exactly at impact (circles and cones from their centre, lines
-- from their origin), so the timing reads at a glance. The edge flickers in the last 0.3 s.
local GROW_FILL,EDGE_WIDTH=.42,.24
-- Released warning parts wait unparented for the next cast instead of being rebuilt: a
-- FireBreath warning is ~115 parts. slab resets every property a warning changes.
local pool,POOL_MAX={},256
local function slab(w,name,size,cf,tint,transparency,list)
 local p=table.remove(pool)
 if not p then p=Instance.new('Part');p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false;p.Material=Enum.Material.Neon end
 p.Name=name;p.Shape=Enum.PartType.Block;p.Size=size;p.CFrame=cf
 p.Color=tint;p.Transparency=transparency;p.Parent=w.folder
 table.insert(w.parts,p)
 if list then table.insert(list,p) end
 return p
end
local function release(w)
 for _,p in w.parts do
  -- Only parts still in the folder: one destroyed elsewhere can't be parented again.
  if p.Parent==w.folder and #pool<POOL_MAX then p.Parent=nil;table.insert(pool,p) else p:Destroy() end
 end
 table.clear(w.parts);w.folder:Destroy()
end
-- Fill geometry for one shape into `list`; `grow` also records how each part scales.
local function fillShape(w,shape,y,tint,transparency,list,grow)
 local function flat(v) return Vector3.new(v.X,y,v.Z) end
 -- A full ring with nothing cut from its middle (the Hammer's Spin) fills as one disc.
 if P.fullRing(shape) and (shape.inner or 0)<=.05 then shape={kind='circle',center=shape.pivot,radius=shape.outer} end
 if shape.kind=='circle' then
  local c=flat(shape.center);local p=slab(w,'WarningFill',Vector3.new(.045,shape.radius*2,shape.radius*2),CFrame.new(c)*CFrame.Angles(0,0,math.pi/2),tint,transparency,list);p.Shape=Enum.PartType.Cylinder
  if grow then table.insert(grow,{part=p,mode='disc',cf=p.CFrame,size=p.Size}) end
 elseif shape.kind=='line' then
  local o=flat(shape.origin);local mid=o+shape.direction*shape.length/2
  local p=slab(w,'WarningFill',Vector3.new(shape.width,.045,shape.length),CFrame.lookAt(mid,mid+shape.direction),tint,transparency,list)
  if grow then table.insert(grow,{part=p,mode='along',origin=o,dir=shape.direction,size=p.Size}) end
 elseif shape.kind=='cone' or shape.kind=='arc' then
  -- Polar ribbon: angular sectors split into radial bands, each strip as wide as its outer edge.
  local pivot=flat(shape.origin or shape.pivot);local forward=shape.direction or shape.forward
  local from,to=shape.from or -shape.halfAngle,shape.to or shape.halfAngle;local inner,outer=shape.inner or 0,shape.outer or shape.length
  local n=math.max(4,math.ceil((to-from)/math.rad(6)));local bands=math.clamp(math.ceil((outer-inner)/7),1,4);local step=(to-from)/n
  for i=0,n-1 do
   local d=CFrame.Angles(0,from+step*(i+.5),0):VectorToWorldSpace(forward)
   for b=0,bands-1 do
    local r0,r1=inner+(outer-inner)*b/bands,inner+(outer-inner)*(b+1)/bands;local p=pivot+d*(r0+r1)/2
    local part=slab(w,'WarningFill',Vector3.new(math.max(.05,r1*math.abs(step)*1.02),.045,r1-r0),CFrame.lookAt(p,p+d),tint,transparency,list)
    if grow then table.insert(grow,{part=part,mode='radial',pivot=pivot,cf=part.CFrame,size=part.Size}) end
   end
  end
 end
end
-- One edge segment from a to b (flat points at the warning height).
local function edgeFrame(a,b)
 local m=(a+b)/2+Vector3.yAxis*.03;return Vector3.new(EDGE_WIDTH,.06,(b-a).Magnitude+.1),CFrame.lookAt(m,b+Vector3.yAxis*.03)
end
local function edgeShape(w,shape,y,tint)
 local function flat(v) return Vector3.new(v.X,y,v.Z) end
 for _,pts in P.edgeLoops(shape,48) do
  for i=1,#pts do
   local a,b=flat(pts[i]),flat(pts[i%#pts+1])
   if (b-a).Magnitude>.01 then local size,cf=edgeFrame(a,b);slab(w,'WarningEdge',size,cf,tint,EDGE,w.edges) end
  end
 end
end
local function drawShape(w,shape,y,tint,noGrow)
 fillShape(w,shape,y,tint,FILL,w.fills)
 if not noGrow then fillShape(w,shape,y+.02,tint,1,w.growParts,w.grow) end
 edgeShape(w,shape,y,tint)
end
local function newWarning(serial,raw)
 local w={folder=Instance.new('Folder'),parts={},fills={},edges={},grow={},growParts={},raw=raw,serial=serial};w.folder.Name='BossWarning';w.folder.Parent=workspace
 return w
end
-- One hit's layers inside a warning (a combo phase, the charge lane or its finish): its own fills,
-- edges and grow layer and paint state, in the warning's folder and part list, so release(w)
-- returns them all.
local function subWarning(w) return {folder=w.folder,parts=w.parts,fills={},edges={},grow={},growParts={}} end
local function buildWarning(ctx)
 local w=newWarning(ctx.serial,ctx.raw)
 local tint=ctx.tint or Color3.fromRGB(224,45,49);local d=ctx.data
 if ctx.def.shape=='targets' then
  for _,p in d.points or {} do drawShape(w,{kind='circle',center=Vector3.new(p[1],p[2],p[3]),radius=ctx.def.radius},p[2]+.07,tint) end
 elseif ctx.def.shape=='projectiles' then
  -- One narrow lane per shot along its level flight, no grow layer: where the volley will go.
  if d.origin and d.yaws then
   local o=Vector3.new(d.origin[1],ctx.groundY,d.origin[3]);local len=math.min((d.speed or 20)*(d.life or 2),38);local width=(d.radius or 1)*2
   for _,yaw in d.yaws do fillShape(w,{kind='line',origin=o,direction=CFrame.Angles(0,yaw,0).LookVector,length=len,width=width},ctx.groundY+.07,tint,.8,w.fills) end
  end
 elseif ctx.def.shape=='ring' then
  -- Round 10 ring (MapBossShapes.ringArcs): the solid stretches only; the gaps stay clear (the way through).
  local ring=Shapes.decodeRing(d.ring)
  if ring then for _,arc in Shapes.ringArcs(ring) do drawShape(w,arc,ring.center.Y+.07,tint) end end
 elseif d.lines then
  for _,line in d.lines do drawShape(w,Shapes.decode(line),ctx.groundY+.07,tint) end
 elseif d.shape then drawShape(w,Shapes.decode(d.shape),ctx.groundY+.07,tint) end
 return w
end
-- k: 0 when the warning appears, 1 at impact. left: seconds to impact. alpha (optional, a later
-- combo phase): every layer at that share of its opacity (P.fade).
-- Each layer is only rewritten when its value moved (the edge holds still until the flicker).
local function paintWarning(w,k,left,now,alpha)
 debug.profilebegin('Boss:PaintWarning')
 k=math.clamp(k,0,1)
 local e=1-(1-k)^1.6 -- fast start, easing into the edge
 if e~=w.e then
  w.e=e
  for _,g in w.grow do
   local p=g.part
   if g.mode=='disc' then p.Size=Vector3.new(g.size.X,g.size.Y*e,g.size.Z*e)
   elseif g.mode=='along' then local len=g.size.Z*e;local mid=g.origin+g.dir*len/2+Vector3.yAxis*.02;p.Size=Vector3.new(g.size.X,g.size.Y,math.max(.05,len));p.CFrame=CFrame.lookAt(mid,mid+g.dir)
   else p.Size=Vector3.new(g.size.X*e,g.size.Y,g.size.Z*e);p.CFrame=CFrame.new(g.pivot+(g.cf.Position-g.pivot)*e)*g.cf.Rotation end
  end
 end
 local grow=P.fade(e<.02 and 1 or GROW_FILL-.12*k,alpha)
 if grow~=w.growT then w.growT=grow;for _,g in w.grow do g.part.Transparency=grow end end
 local flicker=left<.3 and (.5+.5*math.sin(now*48)) or 0
 local fill,edge=P.fade(FILL-.1*k,alpha),P.fade(EDGE*(1-flicker),alpha)
 if fill~=w.fillT then w.fillT=fill;for _,p in w.fills do p.Transparency=fill end end
 if edge~=w.edgeT then w.edgeT=edge;for _,p in w.edges do p.Transparency=edge end end
 debug.profileend()
end
-- Hide one hit's layers once it has landed; painting again (a charge that ran on) shows them.
local function hideWarning(s)
 if s.hidden then return end
 s.hidden=true;s.e,s.growT,s.fillT,s.edgeT=nil,nil,nil,nil
 for _,list in {s.fills,s.edges,s.growParts} do for _,p in list do p.Transparency=1 end end
end
-- One hit's layers, filling from warnStart to impact (alpha: P.phaseAlpha), held full to holdTo
-- (the charge lane, through the run; default impact), then hidden.
local function paintHit(s,age,warnStart,impact,now,alpha,holdTo)
 local stop=holdTo or impact
 if age>=stop then hideWarning(s);return end
 s.hidden=false
 paintWarning(s,(age-warnStart)/math.max(.05,impact-warnStart),(age<impact and impact or stop)-age,now,alpha)
end
-- Combos and the forward charge: one sub-warning per hit, all drawn at the commit.
local function plannedWarning(ctx)
 local w=newWarning(ctx.serial,ctx.raw);local tint=ctx.tint or Color3.fromRGB(224,45,49);local y=ctx.groundY+.07;w.subs={}
 if ctx.phases then
  -- A wave phase warns every line it sends (one, or the enraged fan), as the Stomp does.
  for i,ph in ctx.phases do
   local s=subWarning(w)
   if ph.lines then for _,l in ph.lines do drawShape(s,l,y,tint) end elseif ph.shape then drawShape(s,ph.shape,y,tint) end
   w.subs[i]=s
  end
 else
  local ch=ctx.charge
  if ch.lane then w.lane=subWarning(w);w.lane.length=ch.lane.length;drawShape(w.lane,ch.lane,y,tint) end
  -- The finish slam's circle, on the floor where the server measured it; it moves with the run.
  if ch.finish then w.finish=subWarning(w);w.finish.center=ch.finish.center;drawShape(w.finish,ch.finish,ch.finish.center.Y+.07,tint) end
  -- A finish wave: one layer per line, so each is placed again (placeLane) as the run's end moves.
  if ch.waves then
   w.waves={}
   for i,wv in ch.waves do
    for j,l in wv.lines do local s=subWarning(w);s.wave,s.line,s.placed=i,j,l;drawShape(s,l,l.origin.Y+.07,tint);table.insert(w.waves,s) end
   end
  end
 end
 return w
end
-- The lane at its new length (and, homing, its new start and heading), in place: the fill, the grow
-- layer's extent and the four edges.
local function placeLane(s,shape,y)
 local o=Vector3.new(shape.origin.X,y,shape.origin.Z);local dir=shape.direction;local mid=o+dir*shape.length/2
 local f=s.fills[1];if f then f.Size=Vector3.new(shape.width,.045,shape.length);f.CFrame=CFrame.lookAt(mid,mid+dir) end
 local g=s.grow[1];if g then g.origin=Vector3.new(o.X,y+.02,o.Z);g.dir=dir;g.size=Vector3.new(shape.width,.045,shape.length);s.e=nil end
 local pts=Shapes.outline(shape)
 if #s.edges==#pts then
  for i,p in s.edges do
   local a,b=pts[i],pts[i%#pts+1];p.Size,p.CFrame=edgeFrame(Vector3.new(a.X,y,a.Z),Vector3.new(b.X,y,b.Z))
  end
 end
 s.length=shape.length
end
-- An aimed attack's warning turned in place by `angle` about the vertical axis through pivot (the
-- boss's frame turned: BossFrame against data.yaw), its grow layers' geometry too, so each fill keeps
-- growing where it now lies. Never rebuilt.
local function turnWarning(w,pivot,angle)
 local p=Vector3.new(pivot.X,0,pivot.Z);local r=CFrame.new(p)*CFrame.Angles(0,angle,0)*CFrame.new(-p)
 for _,part in w.parts do if part.Parent==w.folder then part.CFrame=r*part.CFrame end end
 local function regrow(s)
  for _,g in s.grow do
   if g.cf then g.cf=r*g.cf end;if g.pivot then g.pivot=r*g.pivot end;if g.origin then g.origin=r*g.origin end;if g.dir then g.dir=r:VectorToWorldSpace(g.dir) end
  end
  s.e=nil
 end
 regrow(w);for _,s in w.subs or {} do regrow(s) end;if w.lane then regrow(w.lane) end;if w.finish then regrow(w.finish) end
 for _,s in w.waves or {} do regrow(s) end
end
-- Every part of a sub-warning moved by `by` (the finish circle down the lane).
local function moveWarning(s,by)
 for _,list in {s.fills,s.edges,s.growParts} do for _,p in list do p.CFrame+=by end end
 for _,g in s.grow do if g.cf then g.cf+=by end;if g.origin then g.origin+=by end;if g.pivot then g.pivot+=by end end
end
-- Combos: each phase fills on its own timing and hides at its impact. The charge: the lane fills to
-- the launch and stays up for the run, reshaped as it grows; the finish circle fills as a later hit.
-- Released after the last hit, or when the attack stops.
local function stepPlanned(state,ctx,age,now,live)
 local at=ctx.attack;local last
 if ctx.phases then last=0;for _,ph in ctx.phases do last=math.max(last,ph.impact) end
 else
  last=math.max(ctx.charge.runEnd,ctx.charge.finishShow or 0)
  for _,wv in ctx.charge.waves or {} do last=math.max(last,ctx.charge.runEnd+wv.after) end
 end
 local w=state.warning
 if not live or age<at.warnStart or age>=last then if w then release(w);state.warning=nil end;return end
 if not w or w.serial~=ctx.serial or not w.subs then if w then release(w) end;w=profiled('Boss:BuildWarning',plannedWarning,ctx);state.warning=w end
 if ctx.phases then
  for i,s in w.subs do
   local ph=ctx.phases[i];paintHit(s,age,ph.warnStart,ph.impact,now,P.phaseAlpha(i>1,age,ph.warnStart,ph.impact))
  end
  return
 end
 -- The lane holds until the server's stop (ch.runEnd), and the finish circle until its slam: both
 -- only ever end once, so neither hides and comes back.
 local ch=ctx.charge
 if w.lane then
  if ch.lane and (ch.home or math.abs(ch.lane.length-w.lane.length)>1e-3) then placeLane(w.lane,ch.lane,ctx.groundY+.07) end
  paintHit(w.lane,age,at.warnStart,at.impact,now,nil,ch.runEnd)
 end
 if w.finish and ch.finish and ch.finishShow then
  local by=ch.finish.center-w.finish.center
  if by.Magnitude>1e-3 then moveWarning(w.finish,by);w.finish.center=ch.finish.center end
  paintHit(w.finish,age,at.warnStart,ch.finishShow,now,P.phaseAlpha(true,age,at.warnStart,ch.finishShow))
 end
 -- Finish waves: each line follows the run's end, and fills as a later hit until its own impact.
 for _,s in w.waves or {} do
  local wv=ch.waves and ch.waves[s.wave];local line=wv and wv.lines[s.line]
  if line then
   if (line.origin-s.placed.origin).Magnitude>1e-3 or (line.direction-s.placed.direction).Magnitude>1e-4 then placeLane(s,line,line.origin.Y+.07);s.placed=line end
   local show=ch.runEnd+wv.after
   paintHit(s,age,at.warnStart,show,now,P.phaseAlpha(true,age,at.warnStart,show))
  else hideWarning(s) end
 end
end

-- Projectiles: the server's shots replayed from origin, yaws, speed and life (MapBossShapes.shot),
-- stopping where MapBossShotEnds says the server stopped them. Only a volley's own ends count
-- (Shapes.shotEnds): the last volley's list can still be here when this one launches.
local function launch(state,ctx)
 local d=ctx.data;if not d.yaws or not d.origin then return end
 local B={ctx=ctx,born=ctx.start+ctx.attack.impact,origin=Vector3.new(d.origin[1],d.origin[2],d.origin[3]),list={}}
 for i,yaw in d.yaws do local part,update,finish=call(state,'projectile',ctx,i);table.insert(B.list,{i=i,yaw=yaw,part=part,update=update,finish=finish}) end
 state.shots=state.shots or {};table.insert(state.shots,B)
end
local function stepShots(npc,state,now,dt)
 if not state.shots then return end
 local raw=npc:GetAttribute('MapBossShotEnds');if raw~=state.endsRaw then state.endsRaw=raw;state.ends=decode(raw) end
 for bi=#state.shots,1,-1 do
  local B=state.shots[bi];local d=B.ctx.data;local ends=Shapes.shotEnds(state.ends,B.ctx.serial);local alive=false
  for _,s in B.list do
   if s.done then continue end
   local stop=math.min(B.born+d.life,ends and ends[tostring(s.i)] or math.huge)
   local pos,dir=Shapes.shot(B.origin,s.yaw,d.speed,d.height,math.max(0,math.min(now,stop)-B.born))
   if s.part then s.part.CFrame=CFrame.lookAt(pos,pos+dir) end
   if s.update then pcall(s.update,dt) end
   if now>=stop then
    s.done=true;if s.finish then pcall(s.finish,pos) end;if s.part then s.part:Destroy() end
   else alive=true end
  end
  if not alive then table.remove(state.shots,bi) end
 end
end
local function clear(state)
 if state.warning then release(state.warning);state.warning=nil end
 if state.follow then release(state.follow.w) end;state.follow=nil
 for _,B in state.shots or {} do for _,s in B.list do if s.part then s.part:Destroy() end end end;state.shots=nil
 for _,c in state.connections or {} do c:Disconnect() end;state.connections=nil
end

-- Follow-up circles (MapBossService queueFollow): a warning from when the server publishes them to
-- their eruption time, then the boss module's aftershock hook. Only the latest set is shown.
local function stepFollow(npc,state,now,death)
 local raw=npc:GetAttribute('MapBossFollow')
 if raw and raw~=state.followRaw then
  state.followRaw=raw;local d=decode(raw)
  if state.follow then release(state.follow.w);state.follow=nil end
  if type(d.points)=='table' and #d.points>0 and type(d.at)=='number' and d.at>now then
   local F={kind=d.kind,at=d.at,born=now,radius=d.radius or 5,points={},w=newWarning(d.serial,raw)}
   for i,p in d.points do F.points[i]=Vector3.new(p[1],p[2],p[3]) end
   profiled('Boss:BuildWarning',function()
    for _,p in F.points do drawShape(F.w,{kind='circle',center=p,radius=F.radius},p.Y+.07,state.tint or Color3.fromRGB(224,45,49)) end
   end)
   state.follow=F
   -- The boss module's followup hook (optional; the Hammer's cracks open here and grow until they erupt).
   call(state,'followup',{npc=npc,id=state.id,kind=F.kind,points=F.points,radius=F.radius,at=F.at,born=now,tint=state.tint,scale=state.T.scale or 1})
  end
 end
 local F=state.follow;if not F then return end
 if death then release(F.w);state.follow=nil;return end
 if now>=F.at then
  release(F.w);state.follow=nil
  call(state,'aftershock',{npc=npc,id=state.id,kind=F.kind,points=F.points,radius=F.radius,tint=state.tint,scale=state.T.scale or 1})
  return
 end
 paintWarning(F.w,(now-F.born)/math.max(.05,F.at-F.born),F.at-now,now)
end
-- Once per boss: the spawn intro (only if it spawned in the last 3 s) and the enrage burst.
-- A sky-drop boss (BossIntroLand) gets its intro on the landing instead, within 3 s of it.
-- A boss with a roar (def.roar and its clip) enrages as the roar starts: BossEnraged can come
-- mid-attack, and the roar waits for that attack (and through a pause, Admin Freeze or BossManual).
-- A client that missed the roar (it joined late) enrages at the next real attack after BossEnraged,
-- never while the run is paused. Every roar the server starts also gets the `roar` hook (its peak):
-- one a pause cancelled is played again from the start, so its peak comes again with it.
local function roars(state) local r=state.def.roar;return r~=nil and state.T.clips~=nil and state.T.clips[r]~=nil end
local function stepMoments(npc,state,now,death)
 if death then return end
 if not state.introDone then
  local land=npc:GetAttribute('BossIntroLand')
  if type(land)=='number' then
   if now>=land then
    state.introDone=true
    local cf=npc:GetAttribute('BossFrame');local ground=typeof(cf)=='CFrame' and Vector3.new(cf.X,npc:GetAttribute('BossGroundY') or cf.Y-state.T.rootHeight,cf.Z) or nil
    if now-land<3 then call(state,'intro',{npc=npc,id=state.id,tint=state.tint,scale=state.T.scale or 1,land=land,ground=ground,timing=state.T}) end
   end
  else
   state.introDone=true;local born=npc:GetAttribute('BossSpawnedAt')
   if type(born)=='number' and now-born<3 then call(state,'intro',{npc=npc,id=state.id,tint=state.tint,scale=state.T.scale or 1}) end
  end
 end
 local enraged=npc:GetAttribute('BossEnraged')
 if not roars(state) then
  if not state.enraged and enraged then state.enraged=true;call(state,'enrage',{npc=npc,id=state.id,tint=state.tint,scale=state.T.scale or 1,timing=state.T}) end
  return
 end
 if not enraged then return end
 local ctx=state.ctx;local current=ctx and ctx.serial==npc:GetAttribute('BossSerial')
 local roaring=current and ctx.kind==state.def.roar
 if not state.enraged then
  local after=current and not ctx.pseudo and type(enraged)=='number' and ctx.start>enraged and combat:GetAttribute('RunPaused')~=true
  if roaring or after then
   state.enraged=true;call(state,'enrage',{npc=npc,id=state.id,tint=state.tint,scale=state.T.scale or 1,roar=roaring and ctx or nil,roars=true,timing=state.T})
  end
 end
 if roaring and state.roarSerial~=ctx.serial then state.roarSerial=ctx.serial;call(state,'roar',ctx) end
end

local function track(npc)
 if tracked[npc] then return end
 local state={phase=0};tracked[npc]=state
 task.spawn(function()
  local id=npc:GetAttribute('MapBossId');local def=id and Defs.get(id);local T=id and Defs.timing(id)
  if not def or not T then return end
  -- The animation modules are large; wait for them to replicate.
  local motion;for _=1,40 do motion=load(def.anim);if motion or compiled[def.anim]==false or tracked[npc]~=state then break end;task.wait(.5) end
  if not motion or tracked[npc]~=state then return end
  state.id,state.def,state.T,state.tint,state.vfx,state.joints=id,def,T,TINT[id],vfxFor(id),EnemyMotion.bind(npc)
  -- Rebind after the rig changes (a streamed-out boss comes back with new Bone/Motor6D
  -- instances), as RogueliteZombieAnimation does; clear() disconnects these.
  local function changed(v)
   if v:IsA('Bone') or v:IsA('Motor6D') or v:IsA('BasePart') or v:IsA('Humanoid') then state.bindingsDirty=true end
  end
  if tracked[npc]~=state then return end -- dropped while the effects module loaded
  state.connections={npc.DescendantAdded:Connect(changed),npc.DescendantRemoving:Connect(changed)}
  state.motion=motion
 end)
end
Tags:GetInstanceAddedSignal('MapBoss'):Connect(track)
for _,npc in Tags:GetTagged('MapBoss') do track(npc) end

-- Ahead of the fight: from two waves before BossEncounter spawns the run map's boss (wave
-- HammerBossWave, default 20) its clips decode and compile one module or clip per frame, instead
-- of all in the spawn frame (King Crab ~120 ms on desktop). Same data as load(); a boss that
-- arrives first (or an admin spawn) still loads synchronously in track, and this stops.
local warming={}
local function warm(anim)
 if warming[anim] or compiled[anim]~=nil then return end
 local source=animations:FindFirstChild(anim);if not source then return end
 warming[anim]=true
 task.spawn(function()
  -- A failure here is reported once, by the synchronous load() at spawn.
  pcall(function()
   local list=source:GetDescendants()
   for i=#list,1,-1 do -- leaves before the clips that join them; require caches each for load()
    if compiled[anim]~=nil then return end
    if list[i]:IsA('ModuleScript') then task.wait();profiled('Boss:Warm',require,list[i]) end
   end
   task.wait();if compiled[anim]~=nil then return end
   local data=profiled('Boss:Warm',aliased,anim,source)
   local motion=EnemyMotion.compile(data,{})
   for name in data.clips do
    task.wait();if compiled[anim]~=nil then return end
    profiled('Boss:Warm',function() return motion.clips[name] end)
   end
   if compiled[anim]==nil then compiled[anim]=motion end
  end)
 end)
end
task.spawn(function()
 -- ShopService creates the run state on match servers only; lobby clients just wait here.
 local run=game.ReplicatedStorage:WaitForChild('RogueliteRunState',math.huge)
 local function check()
  local map=Maps.get(combat:GetAttribute('RunMap'));local def=map and map.boss and Defs.get(map.boss)
  local wave=run:GetAttribute('Wave')
  if def and type(wave)=='number' and wave>=(combat:GetAttribute('HammerBossWave') or 20)-2 then warm(def.anim) end
 end
 run:GetAttributeChangedSignal('Wave'):Connect(check)
 combat:GetAttributeChangedSignal('RunMap'):Connect(check)
 check()
 -- Endless mode (RogueliteZombieChase) books a random boss in the shop before its wave
 -- (EndlessBossId) and spawns it 5 s in: warm that one too. An id without a map-boss def is
 -- skipped, and warm() stops at a def whose clips aren't installed (the Hammer Brute until his
 -- BossAnimations are: the old BossService Hammer spawns meanwhile, MapBossDefs.ready).
 local function endless()
  local id=run:GetAttribute('EndlessBossId');local def=type(id)=='string' and Defs.get(id)
  if def then warm(def.anim) end
 end
 run:GetAttributeChangedSignal('EndlessBossId'):Connect(endless)
 endless()
end)

-- The `wave` hook: once per wave (ctx.waves()) as its front leaves the impact point, and only while it
-- is still travelling (a client that arrives later skips it). Nothing is built until one is due.
local function stepWaves(state,ctx,age)
 local fired=ctx.waveFired or {};local due=false
 if ctx.phases then
  if not ctx.phaseWaves then return end
  for _,ph in ctx.phases do if ph.lines and age>=ph.impact and not fired[ph.index] then due=true end end
 else
  local ch=ctx.charge;if not (ch and ch.waves and ch.stopAge) then return end
  for _,wv in ch.waves do if age>=ch.stopAge+wv.after and not fired['finish'..wv.index] then due=true end end
 end
 if not due then return end
 ctx.waveFired=fired
 for _,u in ctx.waves() do
  if u.impact and age>=u.impact and not fired[u.key] then
   fired[u.key]=true
   if age<u.impact+u.def.length/math.max(u.def.travel or 1,1e-3) then call(state,'wave',ctx,u) end
  end
 end
end
-- BossAttack's def: an attack, else the intro clip or the roar (P.pseudo, cached per boss).
-- During the intro (inIntro) its clip is the intro even when it is also an attack's.
local function attackDef(state,kind,inIntro)
 if inIntro and state.def.intro and kind==state.def.intro.clip then
  state.introDef=state.introDef or P.pseudo(state.def,kind,true);return state.introDef
 end
 local a=state.def.attacks[kind];if a then return a end
 state.pseudo=state.pseudo or {};local p=state.pseudo[kind]
 if p==nil then p=P.pseudo(state.def,kind) or false;state.pseudo[kind]=p end
 return p or nil
end
local function frame(npc,state,now,dt)
 local h=npc:FindFirstChildOfClass('Humanoid');local root=npc.PrimaryPart;if not h or not root then return end
 if state.bindingsDirty or not next(state.joints) then state.bindingsDirty=false;state.joints=EnemyMotion.bind(npc) end
 local motion,T=state.motion,state.T
 local displacement=state.previousPosition and root.Position-state.previousPosition or Vector3.zero
 state.previousPosition=root.Position
 local distance=Vector2.new(displacement.X,displacement.Z).Magnitude
 local start=npc:GetAttribute('BossStart');local kind=npc:GetAttribute('BossAttack');local age=start and now-start
 -- The sky-drop intro (MapBossService spawn) plays before BossIntroUntil; every attack starts after it.
 local introUntil=npc:GetAttribute('BossIntroUntil');local a=kind and attackDef(state,kind,start~=nil and type(introUntil)=='number' and start<introUntil)
 local serial=npc:GetAttribute('BossSerial') or 0
 if a and start and serial~=(state.ctx and state.ctx.serial) then state.ctx=context(npc,state,kind,a,start,serial) end
 local ctx=state.ctx
 if ctx then
  local raw=npc:GetAttribute('MapBossAttackData');if raw~=ctx.raw then ctx.raw=raw;ctx.data=decode(raw) end
  -- The breath turns during its active window (MapBossService tracking); follow the new frame.
  local cf=npc:GetAttribute('BossFrame');if typeof(cf)=='CFrame' and cf~=ctx.cf then ctx.cf=cf;ctx.ground=cf*CFrame.new(0,-T.rootHeight,0) end
  -- The charge's run, latched end and duration on this frame's clock (age; nil without BossStart).
  if ctx.charge then chargeStep(npc,ctx,ctx.serial==serial and age or nil) end
 end
 local death=npc:GetAttribute('BossDeathStart');local hit=npc:GetAttribute('BossHitStart')
 -- A charge's own re-timed duration: BossDuration comes again only once he has stopped.
 local attacking=ctx and ctx.serial==serial and npc:GetAttribute('Attacking') and age and age>=0 and age<=(ctx.charge and ctx.charge.duration or npc:GetAttribute('BossDuration') or ctx.attack.duration)
 local clip,time
 local v=root.AssemblyLinearVelocity;local moving=Vector2.new(v.X,v.Z).Magnitude>.4
 if death then clip,time='Death',now-death
 elseif attacking then clip,time=attackClip(ctx,age,motion)
 -- A flinch never replaces the walk: on the move it would slide the boss along in one pose.
 elseif hit and now-hit<clipDuration(motion,'Hit') and not moving then clip,time='Hit',now-hit
 else
  clip=moving and 'Walk' or 'Idle'
  -- Ground distance, not elapsed time, advances the planted-foot gait; cadence capped.
  state.phase+=moving and math.min(distance/(T.strideLength or 4)*clipDuration(motion,'Walk'),dt*MAX_GAIT_RATE) or dt
  time=state.phase%clipDuration(motion,clip)
 end
 local poses=EnemyMotion.sample(motion,clip,time)
 if state.lastClip~=clip and state.lastPose and clip~='Death' then state.blendFrom=state.lastPose;state.blendStart=now end
 if state.blendFrom then
  local weight=math.clamp((now-state.blendStart)/((clip=='Walk' or clip=='Idle') and .16 or .12),0,1)
  poses=EnemyMotion.blend(state.blendFrom,poses,weight)
  if weight==1 then state.blendFrom=nil end
 end
 state.lastPose=poses;state.lastClip=clip
 local baseline=npc:GetAttribute('EnemyBaselineModelScale')
 EnemyMotion.apply(state.joints,baseline and EnemyMotion.scalePose(poses,npc:GetScale()/baseline) or poses)
 -- Warnings: from the moment the boss commits to impact (tombs: to their eruption); the grow
 -- layer reaches the edge at impact. Combos and the charge: stepPlanned. The intro and the roar
 -- warn nothing.
 local at=ctx and ctx.attack
 if ctx and (ctx.phases or ctx.charge) then stepPlanned(state,ctx,age or -1,now,not death and attacking)
 elseif ctx and ctx.pseudo then if state.warning then release(state.warning);state.warning=nil end
 else
  local warnEnd=at and (ctx.def.shape=='targets' and at.impact+ctx.def.eruptDelay or at.impact)
  -- A ring stays up while its front runs out (it fills by the impact, then holds).
  local ring=at and ctx.def.shape=='ring' and type(ctx.data.ring)=='table' and ctx.data.ring
  if ring then warnEnd=at.impact+Shapes.ringEnd(ring) end
  if not death and attacking and age>=at.warnStart and age<warnEnd then
   local w=state.warning
   if not w or w.serial~=ctx.serial or w.raw~=ctx.raw then if w then release(w) end;w=profiled('Boss:BuildWarning',buildWarning,ctx);state.warning=w end
   paintWarning(w,(age-at.warnStart)/math.max(.05,(ring and at.impact or warnEnd)-at.warnStart),warnEnd-age,now)
  elseif state.warning then release(state.warning);state.warning=nil end
 end
 -- An aimed attack (data.yaw, MapBossService def.aim): its shapes were published in the frame it
 -- committed in; the warning turns in place with every BossFrame the server sends after.
 local w=state.warning
 if w and ctx and w.serial==ctx.serial and type(ctx.data.yaw)=='number' then
  w.yaw=w.yaw or ctx.data.yaw
  local turn=Shapes.wrap(Shapes.yawOf(ctx.cf)-w.yaw)
  if math.abs(turn)>1e-4 then turnWarning(w,ctx.cf.Position,turn);w.yaw=Shapes.yawOf(ctx.cf) end
 end
 stepFollow(npc,state,now,death)
 stepMoments(npc,state,now,death)
 -- Effects: windup once at warnStart, impact once at impact, active every frame in the active window.
 -- The intro and the roar play their clip only (their effects: the intro and enrage hooks).
 if attacking and not death and not ctx.pseudo then
  if not ctx.woundUp and age>=at.warnStart then ctx.woundUp=true;if age<at.impact then call(state,'windup',ctx) end end
  if not ctx.impacted and age>=at.impact then
   ctx.impacted=true;if age<math.max(at.activeEnd,at.impact+.5) then call(state,'impact',ctx) end
   if ctx.def.shape=='projectiles' then launch(state,ctx) end
  end
  if age>=at.impact and age<at.activeEnd then call(state,'active',ctx,age) end
  if ctx.phases or ctx.charge then stepWaves(state,ctx,age) end
 end
 stepShots(npc,state,now,dt)
end
Run.PreSimulation:Connect(function(dt)
 local now=workspace:GetServerTimeNow()
 for npc,state in tracked do
  if not npc.Parent or not Tags:HasTag(npc,'MapBoss') then clear(state);tracked[npc]=nil;continue end
  if not state.motion then continue end
  debug.profilebegin('Boss:Frame')
  local ok,err=pcall(frame,npc,state,now,dt)
  debug.profileend()
  if not ok and not state.warned then state.warned=true;warn('MapBossPresentation: '..tostring(err)) end
 end
end)

-- Knockdown (GroundSlam, FrontStomp): a short fall, thrown away from the impact.
task.spawn(function()
 -- MapBossService creates it on the server when it first loads (the first map boss), so this can
 -- wait the whole session; the explicit timeout keeps the infinite-yield warning out of Output.
 local knock=combat:WaitForChild('MapBossKnockdown',math.huge)
 local token
 knock.OnClientEvent:Connect(function(source,seconds)
  if typeof(source)~='Vector3' or type(seconds)~='number' or seconds~=seconds then return end
  local ch=player.Character;local h=ch and ch:FindFirstChildOfClass('Humanoid');local root=ch and ch:FindFirstChild('HumanoidRootPart')
  if not h or not root or h.Health<=0 then return end
  local away=Shapes.flat(root.Position-source);if away.Magnitude<.1 then away=Shapes.flat(-root.CFrame.LookVector) end
  local mine={};token=mine
  h.PlatformStand=true;root.AssemblyLinearVelocity=away.Unit*28+Vector3.yAxis*22
  task.delay(math.clamp(seconds,0,2),function() if token==mine and h.Parent then h.PlatformStand=false end end)
 end)
end)
