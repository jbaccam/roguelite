-- MapBossServiceTests: pure shape-builder checks (plan F Task 7). Run in Edit through
-- tools/RepoRequire.luau (R.run('MapBossServiceTests')): fresh repo copies, nothing written to Studio.
-- The timing tables below are hand-made, so these run before the generated MapBossTiming exists;
-- an Edit-mode require of MapBossService loads only its pure builders (M._shapes).
local service=script.Parent:FindFirstChild('MapBossService') or game:GetService('ServerScriptService'):FindFirstChild('MapBossService')
assert(service,'MapBossService is not installed')
local X=require(service)._shapes
local S=require(game.ReplicatedStorage.RogueliteCombat.MapBossShapes)
local defsModule=game.ReplicatedStorage.RogueliteCombat:FindFirstChild('MapBossDefs')
local Defs;if defsModule then local ok,v=pcall(require,defsModule);assert(ok,v);Defs=v end
local r={};local function add(ok,m) table.insert(r,(ok and 'PASS ' or 'FAIL ')..m) end
-- Protected: a missing builder reads as one FAIL line instead of stopping the run.
local function check(m,f) local ok,v=pcall(f);add(ok and v==true,m..(ok and '' or ' (error: '..tostring(v)..')')) end
local T={rootHeight=4,clips={RushStart=.8,RushLoop=.5,RushEnd=.6},attacks={
 Stomp={duration=2,warnStart=.3,impact=1,activeEnd=1,recoveryEnd=1.8,directionAtImpactStudio={0,0,-1},samples={StompImpact={{.3,1,2,-3},{1,1,0,-4},{1.8,1,0,-4}}}},
 TailWhip={duration=2,warnStart=.2,impact=.9,activeEnd=1.3,recoveryEnd=1.9,samples={
  SpadeTip={{.9,6,1.2,8},{1.1,0,1.2,11},{1.3,-6,1.2,8}},TailMid={{.9,2,2,4},{1.1,0,2,5},{1.3,-2,2,4}}}},
}}
local stomp={clip='Stomp',shape='wave',point='StompImpact',length=26,width=5,travel=40}
local whip={clip='TailWhip',shape='sweep',point='SpadeTip',mid='TailMid',radius=3}
local rush={clips={'RushStart','RushLoop','RushEnd'},shape='lane',length=38,width=9,speed=30}
local cf=CFrame.lookAt(Vector3.new(10,4,20),Vector3.new(10,4,0)) -- root 4 up, facing -Z; ground y=0
local f=X.frame(cf,T,0)
-- 1. Stomp wave: a player 12 studs ahead is hit at impact + 12/40, not before.
local at=X.window(stomp,T);local line=X.wave(stomp,at,f);local due=at.impact+12/40
local player=line.origin+line.direction*12+Vector3.yAxis*3
add((line.origin-Vector3.new(11,0,16)).Magnitude<1e-4 and line.direction:Dot(Vector3.new(0,0,-1))>.999,'wave starts at the sampled StompImpact, heading -Z')
add(not X.waveHit(stomp,at,line,player,at.impact-.1,due-.02),'wave: no hit before impact + 12/40')
add(X.waveHit(stomp,at,line,player,due-.02,due+.02),'wave: hit at impact + 12/40')
add(not X.waveHit(stomp,at,line,player+Vector3.new(4,0,0),due-.02,due+.02),'wave: misses 4 studs to the side')
add(math.abs(X.duration(stomp,at)-1.8)<1e-6,'wave: duration is recovery (the front ends first)')
-- 2. Lane: toward the target's side.
add(X.lane(cf,cf*Vector3.new(10,0,-3)):Dot(cf.RightVector)>.99,'lane: toward a target on the right')
add(X.lane(cf,cf*Vector3.new(-10,0,-3)):Dot(cf.RightVector)<-.99,'lane: toward a target on the left')
local goal=Vector3.new(10,4,0);local faced=X.laneFacing(cf.Position,goal,cf.LookVector);local toGoal=(goal-cf.Position).Unit
add(math.abs(faced.LookVector:Dot(toGoal))<1e-6 and X.lane(faced,goal):Dot(toGoal)>.99,'lane: turns side-on so the lane runs through the target')
-- The crab rushes side-on, claws to the left of the lane: the hit and its warning run from the
-- shell (7 studs right of the path) to the claw tips (14 left), not just 6 either side.
local crabRush={shape='lane',width=21,offset=3.5};local rd=Vector3.new(0,0,-1);local left=Vector3.yAxis:Cross(rd)
local rcf=CFrame.lookAt(Vector3.new(0,4,0),Vector3.new(0,4,-1));local body=X.rushBody(crabRush,rcf,rd,0,0,10)
local warnLane=X.laneShape(X.frame(rcf,T,0),rd,30,21,X.laneSide(rd,crabRush))
local function both(p) return S.contains(body,p) and S.contains(warnLane,p) end
add(both(Vector3.new(0,3,-5)+left*13.5) and both(Vector3.new(0,3,-5)-left*6.5) and not S.contains(body,Vector3.new(0,3,-5)-left*8) and not S.contains(warnLane,Vector3.new(0,3,-5)-left*8),
 'lane: the crab rush hits claw tips 13.5 left and shell 6.5 right, not 8 right; the warning matches')
local lw=X.window(rush,T,30)
add(math.abs(lw.impact-.8)<1e-6 and math.abs(lw.duration-(.8+1+.6))<1e-6,'lane: duration = RushStart + length/speed + RushEnd')
-- 3. Sweep: the TailWhip capsule at impact contains the sampled SpadeTip.
local wat=X.window(whip,T);local tip=f.ground*S.sample(wat.samples.SpadeTip,wat.impact)
add(S.contains(X.sweep(whip,wat,f,wat.impact),tip),'sweep: capsule at impact contains the sampled SpadeTip')
add(not S.contains(X.sweep(whip,wat,f,wat.activeEnd),tip),'sweep: the capsule has moved on by activeEnd')
local arc=X.sweepArc(whip,wat,f)
add(S.contains(arc,tip) and S.contains(arc,f.ground*S.sample(wat.samples.SpadeTip,wat.activeEnd)) and not S.contains(arc,f.ground*Vector3.new(0,1,-10)),'sweep: warning arc covers the tip path, not the front')
-- The whole tail hits: under the base (1.1 studs from the centre) is 3.4 from TailMid, which
-- mid-to-tip alone (radius 3) missed.
local under=f.ground*Vector3.new(.5,1,1)
add(S.contains(X.sweep(whip,wat,f,wat.impact),under),'sweep: the tail base, under his rear, hits')
-- Hits start where the wind-up stops (the tip's slowest moment before impact), not at impact.
local wind={duration=2,warnStart=.2,impact=.9,activeEnd=1.3,samples={SpadeTip={{.2,0,1,8},{.3,3,1,7},{.4,5,1,5},{.5,5.2,1,4.8},{.6,4,1,6},{.9,-6,1,8}}}}
add(math.abs(X.hitFrom(whip,wind)-.4)<1e-6 and math.abs(X.hitFrom(whip,wat)-wat.impact)<1e-6,'sweep: hits from the end of the wind-up (0.4), not impact (0.9); no wind-up samples: impact')
-- Projectile fan and a missing sample track.
local ys=X.yaws({count=3,spread=math.rad(18)},Vector3.new(-1,0,0))
add(#ys==3 and math.abs(ys[2]-math.pi/2)<1e-6 and math.abs(ys[3]-ys[1]-math.rad(18))<1e-6,'projectiles: yaws spread evenly about the aim')
add(X.localPoint({points={P={rootAtImpactStudio={1,2,3}}}},'P',0)==Vector3.new(1,2,3),'point falls back to rootAtImpactStudio')
-- 5. Hammer Brute runtime (rebuild R1-R3, 2026-10-03), hand-made timings again. HammerFace circles
-- the boss 8 studs out and HammerGrip 4, 3 up, at yaw th(t) (0 = ahead, +pi/2 = his left): wound
-- back, held 0.4-0.45, the Swing easing in to +90 degrees at 0.66, held 0.66-0.72 (the Spin's
-- wind-up, inside the Swing's window, which ends at 0.7), then the Spin easing in, 2pi + 0.5 by 1.25.
-- Swings ease in from a held pose as authored clips do, so X.hitFrom's walk back is exact.
local function th(t)
 if t<.4 then return -math.pi/2-.3*t/.4 elseif t<.45 then return -math.pi/2-.3
 elseif t<.66 then return -math.pi/2-.3+(math.pi+.3)*((t-.45)/.21)^2 elseif t<.72 then return math.pi/2 end
 return math.pi/2+(2*math.pi+.5)*math.min(1,(t-.72)/.53)^2
end
local function circling(radius) local list={};for k=0,96 do local t=k/60;local d=CFrame.Angles(0,th(t),0):VectorToWorldSpace(Vector3.new(0,0,-radius));list[k+1]={t,d.X,3,d.Z} end;return list end
local HT={rootHeight=4,clips={ChargeStart=.5,ChargeRun=.53,ChargeSlam=1.2,Roar=1.2},attacks={
 SwingSpin={duration=1.6,warnStart=0,impact=.5,activeEnd=1.25,recoveryEnd=1.6,phases={{warnStart=0,impact=.5,activeEnd=.7},{warnStart=0,impact=.8,activeEnd=1.25}},
  samples={HammerFace=circling(8),HammerGrip=circling(4)}},
 ChargeSlam={duration=1.2,warnStart=0,impact=.4,activeEnd=.45,recoveryEnd=1.2,samples={HammerFace={{0,0,6,-3},{.4,0,0,-5},{1.2,0,0,-5}}}},
}}
local function with(t,extra) local c=table.clone(t);for k,v in extra do c[k]=v end;return c end
local hammerSweep={shape='sweep',point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4}
local swingSpin={clip='SwingSpin',range={0,14},cooldown=1,phases={with(hammerSweep,{damage=20}),with(hammerSweep,{damage=22})}}
local hf=X.frame(CFrame.lookAt(Vector3.new(0,4,0),Vector3.new(0,4,-1)),HT,0) -- root 4 up at the origin, facing -Z; ground y=0
-- R1. Combos: one clip, a window, def and hit memory per phase.
check('phases: two windows with the phase times, all warned from the commit',function()
 local w=X.phaseWindows(swingSpin,HT.attacks.SwingSpin)
 return #w==2 and w[1].impact==.5 and w[1].activeEnd==.7 and w[2].impact==.8 and w[2].activeEnd==1.25 and w[1].warnStart==0 and w[2].warnStart==0
end)
check('phases: each phase def is the attack def with the phase on top (damage 20, then 22)',function()
 local units=X.phases(swingSpin,HT.attacks.SwingSpin)
 return #units==2 and units[1].def.damage==20 and units[2].def.damage==22 and units[2].def.clip=='SwingSpin'
end)
check('phases: the Swing phase warns an arc over its path (ahead, both sides), not behind him',function()
 local units=X.phases(swingSpin,HT.attacks.SwingSpin);local arc=X.shapeOf(units[1].def,units[1].at,hf)
 return arc.kind=='arc' and arc.to-arc.from<2*math.pi-.1 and S.contains(arc,Vector3.new(0,3,-7)) and S.contains(arc,Vector3.new(7,3,0)) and S.contains(arc,Vector3.new(-7,3,0)) and not S.contains(arc,Vector3.new(0,3,7))
end)
check('phases: the Spin phase warns a full ring (-pi to pi), behind him too',function()
 local units=X.phases(swingSpin,HT.attacks.SwingSpin);local ring=X.shapeOf(units[2].def,units[2].at,hf)
 return ring.kind=='arc' and ring.from==-math.pi and ring.to==math.pi and ring.inner==0 and S.contains(ring,Vector3.new(0,3,7))
end)
-- Three still players 7 studs out: ahead, behind, and on his left just past where the Swing ends
-- (the Spin passes that one twice). Stepped at 60 Hz like the server's Heartbeat. The clip's own
-- times: the Swing's wind-up ends at 0.4, and the Spin may not hit before the Swing ends at 0.7.
check('phases: hit once per phase (the Spin passes "left" twice); the Swing misses behind him; no Swing hit before 0.4, no Spin hit before 0.7',function()
 local left=CFrame.Angles(0,math.pi/2+.3,0):VectorToWorldSpace(Vector3.new(0,0,-7))+Vector3.yAxis*3
 local people={{player='ahead',at=Vector3.new(0,3,-7)},{player='behind',at=Vector3.new(0,3,7)},{player='left',at=left}}
 local units=X.phases(swingSpin,HT.attacks.SwingSpin);local count,early,t0={},{},0
 for _,P in units do P.arc=X.shapeOf(P.def,P.at,hf) end
 for k=1,100 do
  local age=k/60
  for i,P in units do
   X.stepHits(P,hf,age,t0,people,function(e)
    local key=e.player..i;count[key]=(count[key] or 0)+1
    if age<({.4,.7})[i]-1e-9 then table.insert(early,key) end
    return true
   end)
  end
  t0=age
 end
 local function n(key) return count[key] or 0 end
 return n('ahead1')==1 and n('ahead2')==1 and n('behind1')==0 and n('behind2')==1 and n('left1')==1 and n('left2')==1 and #early==0
end)
check('phases: a missing phase timing refuses the combo (no windows)',function()
 return X.phaseWindows(swingSpin,{duration=1,impact=.5,activeEnd=.7,phases={{impact=.5,activeEnd=.7}}})==nil and X.phaseWindows({clip='Slam'},HT.attacks.SwingSpin)==nil
end)
-- R2. The Hammer's charge: a forward lane that keeps running to its target, then slams.
local charge={clips={'ChargeStart','ChargeRun','ChargeSlam'},facing='forward',range={22,70},lockout=5,cooldown=1,damage=24,shape='lane',length=75,width=9,speed=32,contact=4,offset=3.5,
 finish={shape='circle',damage=26,point='HammerFace',radius=9.5,height=6,knockdown=.6}}
check('charge: a forward lane runs straight at the target and he faces along it; no side-on offset',function()
 local pos,goal=Vector3.new(0,4,0),Vector3.new(30,9,-40);local dir=X.laneDir(charge,pos,goal,Vector3.new(0,0,-1))
 local want=Vector3.new(30,0,-40).Unit;local faced=CFrame.lookAt(pos,pos+dir)
 return (dir-want).Magnitude<1e-6 and faced.LookVector:Dot(want)>.9999 and X.laneSide(dir,charge)==Vector3.zero and X.laneSide(dir,{offset=3.5}).Magnitude>3.49
end)
check('charge: the crab lane is unchanged (through the target, side-on offset kept)',function()
 local pos,goal=Vector3.new(0,4,0),Vector3.new(30,9,-40);local look=Vector3.new(0,0,-1)
 local crab={shape='lane',width=21,offset=3.5};local dir=X.laneDir(crab,pos,goal,look)
 return (dir-X.lane(X.laneFacing(pos,goal,look),goal)).Magnitude<1e-9 and X.laneSide(dir,crab)==Vector3.yAxis:Cross(dir)*3.5
end)
local laneCf,laneDir=CFrame.lookAt(Vector3.new(0,4,0),Vector3.new(0,4,-1)),Vector3.new(0,0,-1)
check('charge: contact run ends 4 short of a target 40 down the lane (36); 2 off-centre it still tracks; stepped out it keeps its length and the run misses them',function()
 local centred=X.contactLength(charge,laneCf,laneDir,Vector3.new(0,4,-40),75,50,0)
 local off=X.contactLength(charge,laneCf,laneDir,Vector3.new(2,4,-40),75,50,0)
 local out=X.contactLength(charge,laneCf,laneDir,Vector3.new(5,4,-40),75,50,0)
 return math.abs(centred-36)<1e-9 and math.abs(off-(40-math.sqrt(12)))<1e-9 and out==50 and not S.contains(X.rushBody(charge,laneCf,laneDir,0,0,50),Vector3.new(5,3,-40))
end)
check('charge: contact length capped by def.length and the wall, never below the distance travelled',function()
 return X.contactLength(charge,laneCf,laneDir,Vector3.new(0,4,-120),75,50,0)==75 and X.contactLength(charge,laneCf,laneDir,Vector3.new(0,4,-120),60,50,0)==60
  and X.contactLength(charge,laneCf,laneDir,Vector3.new(0,4,-30),75,50,30)==30
end)
check('charge: the body hit at the contact stop reaches a target 2 off-centre (contact < width/2)',function()
 local goal=Vector3.new(2,3,-40);local length=X.contactLength(charge,laneCf,laneDir,goal,75,50,0)
 return S.contains(X.rushBody(charge,laneCf,laneDir,0,length-1,length),goal)
end)
-- A charge as M.start builds it, for X.laneTiming.
local function chargeAttack(cf,dir,length)
 return {def=charge,cf=cf,frame=X.frame(cf,HT,0),ground=0,dir=dir,length=length,data={},finish={def=X.merged(charge,charge.finish),hits={},ticks={},fired=false}}
end
check('charge: the finish slam lands at HammerFace at the ChargeSlam impact, from where the run ends',function()
 local A=chargeAttack(CFrame.lookAt(Vector3.new(0,4,0),Vector3.new(1,4,0)),Vector3.new(1,0,0),36);X.laneTiming(HT,A)
 local F=A.finish;local c=X.circle(F.def,F.at,F.frame)
 return F.def.damage==26 and c.kind=='circle' and (c.center-Vector3.new(41,0,0)).Magnitude<1e-6 and c.radius==9.5 and c.height==6
  and math.abs(F.start+F.at.impact-(.5+36/32+.4))<1e-9 and math.abs(A.data.finish.impact-(.5+36/32+.4))<1e-9
end)
check('charge: lane timing for a run grown 30 -> 40 moves the finish 10 studs down the lane, lasts past its impact, and lands on the end floor',function()
 local A=chargeAttack(laneCf,laneDir,30);X.laneTiming(HT,A);local c30,i30=S.decode(A.data.finish.shape).center,A.data.finish.impact;local covers30=A.duration>=i30
 A.length=40;X.laneTiming(HT,A);local c40=S.decode(A.data.finish.shape).center
 local grown=(c40-c30-laneDir*10).Magnitude<1e-6 and A.data.length==40 and math.abs(A.data.finish.impact-i30-10/32)<1e-9 and A.duration>=A.data.finish.impact and covers30
 A.endGround=2;X.laneTiming(HT,A)
 return grown and math.abs(S.decode(A.data.finish.shape).center.Y-2)<1e-9 and A.finish.frame.groundY==2
end)
check('charge stop: the data says when the run ended (stoppedAt = start + ChargeStart + length/speed, the finish clock) and its final length; none before the stop',function()
 local A=chargeAttack(laneCf,laneDir,30);A.start=100;X.laneTiming(HT,A);local before=A.data.stoppedAt
 A.length=36;A.floorY=2;X.stopCharge(HT,A)
 local wire=game:GetService('HttpService'):JSONDecode(game:GetService('HttpService'):JSONEncode(A.data))
 return before==nil and math.abs(A.data.stoppedAt-(100+.5+36/32))<1e-9 and math.abs(A.data.stoppedAt-(A.start+A.finish.start))<1e-9 and A.data.length==36
  and A.finish.frame.groundY==2 and math.abs(wire.stoppedAt-A.data.stoppedAt)<1e-3 and wire.length==36
end)
check('lockout: the order walk skips the charge within 5 s of its last start',function()
 local s={def={attacks={Slam={range={0,16}},Charge=charge},order={'Slam','Charge','Slam'}},index=1,lastStart={Charge=10}}
 local any=function() return true end
 return X.walk(s,s.def.order,30,13,any)==nil and X.walk(s,s.def.order,30,15.01,any)==2 and X.walk(s,s.def.order,10,13,any)==3 and X.walk({def=s.def,index=1},s.def.order,30,13,any)==2
end)
-- R3. Full-ring sweeps, circle height, the tutorial variant, the enrage order and the roar.
check('sweep: a whole Spin (2pi + 0.5) warns a full ring from his centre (baseRadius) out past the tip',function()
 local a=X.sweepArc(with(hammerSweep,{clip='Spin'}),{duration=1.6,warnStart=.7,impact=.8,activeEnd=1.25,samples=HT.attacks.SwingSpin.samples},hf)
 return a.from==-math.pi and a.to==math.pi and a.inner==0 and math.abs(a.outer-11.2)<1e-6
end)
check('circle: def.height goes on the shape (6 reaches 5.8 above, not 7)',function()
 local c=X.circle({point='HammerFace',radius=9.5,height=6},HT.attacks.ChargeSlam,hf)
 return c.height==6 and S.contains(c,c.center+Vector3.yAxis*5.8) and not S.contains(c,c.center+Vector3.yAxis*7) and X.circle({point='HammerFace',radius=9.5},HT.attacks.ChargeSlam,hf).height==nil
end)
check('order: tutorial order when s.tutorial, enraged order when enraged and present, else def.order',function()
 local def={order={'Slam'},enrage={order={'SwingSpin'}},tutorial={order={'Swing'},enrage=false,follow=false}}
 return X.orderFor({def=def,tutorial=true,enraged=true})==def.tutorial.order and X.orderFor({def=def,enraged=true})==def.enrage.order and X.orderFor({def=def})==def.order
  and X.orderFor({def={order=def.order,enrage={cooldown=.6}},enraged=true})==def.order
end)
check('tutorial: no enrage and no follow-ups; outside the tutorial both stay on',function()
 local def={tutorial={enrage=false,follow=false}}
 return not X.allows({def=def,tutorial=true},'enrage') and not X.allows({def=def,tutorial=true},'follow') and X.allows({def=def},'enrage') and X.allows({def=def},'follow') and X.allows({def={},tutorial=true},'follow')
end)
check('roar: due once after enrage, never mid-attack, only with def.roar',function()
 local s={def={roar='Roar'}};local before=X.roarDue(s)
 s.enraged=true;s.attack={};local mid=X.roarDue(s);s.attack=nil;local due=X.roarDue(s);s.roared=true
 return before==false and mid==false and due==true and X.roarDue(s)==false and X.roarDue({def={},enraged=true})==false
end)
-- R10. Tracking (user, 2026-10-04: "chaining attacks and better player tracking is all i need").
local AIM={rate=math.rad(150),lock=.3}
local function facing() return CFrame.lookAt(Vector3.new(0,4,0),Vector3.new(0,4,-1)) end
check('aim: turns at most rate x dt toward the target (150 deg/s over 0.1 s: 15 deg), yaw only about the root',function()
 local A={cf=facing(),at={impact=.7}}
 local turned=X.aimStep(A,.2,.1,Vector3.new(10,3,0),AIM)
 local yaw=S.yawOf(A.cf)
 return turned and math.abs(math.abs(yaw)-math.rad(15))<1e-6 and yaw<0 and A.cf.Position==Vector3.new(0,4,0) and math.abs(A.cf.LookVector.Y)<1e-9
  and not X.aimStep(A,.2,.1,Vector3.new(0,4,0),AIM) -- a target on top of him turns nothing
end)
-- A target circling him at 6 rad/s, 12 studs out, stepped at 60 Hz: when does the frame turn?
local function circle(A,stop)
 local turns={}
 for k=1,math.floor(stop*60) do
  local age=k/60;local a=age*6
  if X.aimStep(A,age,1/60,Vector3.new(math.sin(a)*12,3,-math.cos(a)*12),AIM) then table.insert(turns,age) end
 end
 return turns
end
check('aim: one hit turns until impact - lock (0.7 - 0.3) and then holds',function()
 local A={cf=facing(),at={impact=.7}};local turns=circle(A,1.2)
 return #turns>0 and turns[#turns]<.4 and turns[#turns]>.38 and X.aimOpen(A,.39,AIM.lock) and not X.aimOpen(A,.4,AIM.lock) and not X.aimOpen(A,.9,AIM.lock)
end)
check('aim: a combo re-aims in each phase\'s wind-up (after the phase before ends, until its impact - lock), never mid-hit',function()
 local A={cf=facing(),phases={{at={impact=.5,activeEnd=.7}},{at={impact=1.3,activeEnd=1.5}},{at={impact=2,activeEnd=2.2}}}}
 local turns=circle(A,2.5);local inside={[1]=false,[2]=false,[3]=false};local outside=false
 for _,t in turns do
  if t<.2 then inside[1]=true elseif t>=.7 and t<1 then inside[2]=true elseif t>=1.5 and t<1.7 then inside[3]=true else outside=true end
 end
 return inside[1] and inside[2] and inside[3] and not outside and not X.aimOpen(A,.6,AIM.lock) and X.aimOpen(A,.75,AIM.lock) and not X.aimOpen(A,1.2,AIM.lock)
end)
check('aim: the turned frame turns every shape it holds (the sweep arc and the circle) about the root, and nothing else',function()
 local units=X.phases(swingSpin,HT.attacks.SwingSpin);local A={def=swingSpin,at=HT.attacks.SwingSpin,phases=units}
 local f0=X.frame(facing(),HT,0);X.reshape(A,f0);local arc0=units[1].arc
 local cf=CFrame.new(0,4,0)*CFrame.Angles(0,.6,0)*facing().Rotation;local f1=X.frame(cf,HT,0);X.reshape(A,f1)
 local want=S.rotated(arc0,Vector3.new(0,0,0),.6);local arc=units[1].arc
 local slam={point='HammerFace',radius=9.5};local c0,c1=X.circle(slam,HT.attacks.ChargeSlam,f0),X.circle(slam,HT.attacks.ChargeSlam,f1)
 return (arc.pivot-want.pivot).Magnitude<1e-6 and (arc.forward-want.forward).Magnitude<1e-6 and math.abs(arc.from-want.from)<1e-6 and math.abs(arc.to-want.to)<1e-6 and math.abs(arc.outer-want.outer)<1e-6
  and (c1.center-S.rotated(c0,Vector3.zero,.6).center).Magnitude<1e-6
end)
check('frame republish: only past 1 degree from the one sent (across +-180 too), and exactly once the aim locks',function()
 local due=X.frameDue
 local ok=not due(0,math.rad(.9),false) and due(0,math.rad(1.1),false) and due(0,math.rad(.5),true) and not due(0,0,true)
  and not due(math.rad(179.6),math.rad(-179.6),false) and due(math.rad(179),math.rad(-179),false)
 -- A target drifting round slowly (0.45 deg a frame): a send every third frame, not every frame.
 local sent,count=0,0
 for k=1,60 do local yaw=math.rad(.45)*k;if due(sent,yaw,false) then sent=yaw;count+=1 end end
 return ok and count==20 and X.headDue(Vector3.new(0,0,-1),CFrame.Angles(0,math.rad(1.2),0).LookVector) and not X.headDue(Vector3.new(0,0,-1),CFrame.Angles(0,math.rad(.8),0).LookVector)
end)
local homing=with(charge,{home=math.rad(40)})
check('homing: the heading turns at most home x dt toward the target (40 deg/s over 0.1 s: 4 deg); the body moves on along the new heading',function()
 local A={pos=Vector3.new(0,4,0),dir=Vector3.new(0,0,-1),travelled=0}
 local a,b=X.homeStep(A,homing,Vector3.new(30,3,-1),.1,3.2)
 local turned=math.abs(S.yaw(Vector3.new(0,0,-1),A.dir))
 return math.abs(turned-math.rad(4))<1e-6 and a==Vector3.new(0,4,0) and (b-(a+A.dir*3.2)).Magnitude<1e-9 and A.travelled==3.2 and math.abs(A.dir.Magnitude-1)<1e-9 and A.dir.Y==0
  and X.homeDir(Vector3.new(0,0,-1),Vector3.zero,Vector3.new(0,0,-9),1)==Vector3.new(0,0,-1)
end)
-- A target 8 studs right of his line, 30 ahead, standing still: the straight charge (width 9) misses
-- them; the homing run curves after them and one of its per-step body segments reaches them.
check('homing: a run curves after a target off the straight lane and its per-step body hit reaches them; the straight lane misses them',function()
 local goal=Vector3.new(8,3,-30);local A={pos=Vector3.new(0,4,0),dir=Vector3.new(0,0,-1),travelled=0};local struck=false
 for k=1,80 do
  local a,b=X.homeStep(A,homing,goal,1/60,math.min(36,k/60*32))
  if S.contains(X.pathBody(homing,a,b,0),Vector3.new(goal.X,3,goal.Z)) then struck=true end
 end
 local straight=X.rushBody(homing,facing(),Vector3.new(0,0,-1),0,0,36)
 return struck and not S.contains(straight,Vector3.new(goal.X,3,goal.Z)) and A.travelled==36
end)
check('homing: lane timing runs the lane and the finish on from the body along its heading; at the commit it is the straight one',function()
 local function attack(len) return {def=homing,cf=laneCf,frame=X.frame(laneCf,HT,0),ground=0,dir=laneDir,length=len,data={},finish={def=X.merged(homing,homing.finish),hits={},ticks={},fired=false}} end
 local plain=attack(40);X.laneTiming(HT,plain)
 local commit=attack(40);commit.pos,commit.travelled=laneCf.Position,0;X.laneTiming(HT,commit)
 local Http=game:GetService('HttpService');local same=Http:JSONEncode(plain.data)==Http:JSONEncode(commit.data)
 local A=attack(40);A.pos,A.travelled=Vector3.new(6,4,-14),15;A.dir=CFrame.Angles(0,-.4,0):VectorToWorldSpace(laneDir);X.laneTiming(HT,A)
 local lane=S.decode(A.data.shape);local fin=S.decode(A.data.finish.shape)
 local endCf=CFrame.lookAt(A.pos,A.pos+A.dir)+A.dir*25;local want=X.circle(A.finish.def,HT.attacks.ChargeSlam,X.frame(endCf,HT,0))
 return same and (lane.origin-(Vector3.new(6,0,-14)-A.dir*homing.width/2)).Magnitude<1e-6 and (lane.direction-A.dir).Magnitude<1e-6 and math.abs(lane.length-(25+homing.width))<1e-6
  and (fin.center-want.center).Magnitude<1e-6 and A.data.length==40
end)
check('homing: only a forward lane with def.home homes (the crab rush and a plain charge keep straight lanes)',function()
 return Defs==nil or (Defs.get('KingCrab').attacks.SidewaysRush.home==nil and Defs.get('KingCrab').attacks.SidewaysRush.facing==nil)
end)
-- R11. Rubble waves (user, 2026-10-09: "his strike down on the ground should apply ... waves that
-- progressively get higher of dirt and rock"). Every slam sends a wave as its own phase, timed like the
-- slam circle (the baker writes Slam [circle, wave], SpinSlam [rev1, rev2, circle, wave]). Hand-made
-- Slam: HammerFace lands 10 studs ahead at 0.7; its authored direction is +X (the side), so a wave that
-- follows his facing (-Z) is told apart from one that follows the clip (the Stomp).
local WT={rootHeight=4,clips={ChargeStart=.5,ChargeRun=.53,Slam=1.45},attacks={
 Slam={duration=1.45,warnStart=0,impact=.7,activeEnd=.7,recoveryEnd=1.3,directionAtImpactStudio={1,0,0},
  phases={{warnStart=0,impact=.7,activeEnd=.7},{warnStart=0,impact=.7,activeEnd=.7}},
  samples={HammerFace={{0,0,9,-4},{.7,0,0,-10},{1.45,0,0,-10}}}},
}}
local WAVE={shape='wave',damage=22,point='HammerFace',facing='forward',length=85,width=9,travel=55,knockdown=false}
local SLAM12={shape='circle',damage=26,point='HammerFace',radius=12,height=6,knockdown=.6}
local slamDef={clip='Slam',range={0,45},cooldown=.8,phases={SLAM12,WAVE}}
local FAN={-25,0,25}
-- Every unit stepped at 60 Hz from 0 to `stop` (clock offset `from`, a finish's F.start): the first time
-- (on the unit's clock, age - from) each person was struck by each unit, and how often.
local function struckBy(units,f,people,stop,from)
 local first,count,t0={},{},0;from=from or 0
 for k=1,math.floor(stop*60) do
  local age=k/60
  for i,U in units do
   X.stepHits(U,U.frame or f,age-from,t0-from,people,function(e) local key=e.player..'@'..i;count[key]=(count[key] or 0)+1;first[key]=first[key] or age-from;return true end)
  end
  t0=age
 end
 return first,count
end
check('rubble wave: a phase whose line starts at the HammerFace impact and runs 85 along his facing, not the clip\'s +X; the Stomp (no facing) still follows its clip',function()
 local units=X.phases(slamDef,WT.attacks.Slam);local shape=X.place(units[2],hf)
 local line=units[2].line;local stomp=X.wave({point='HammerFace',length=26,width=5},WT.attacks.Slam,hf)
 return shape==line and #units[2].lines==1 and line.kind=='line' and (line.origin-Vector3.new(0,0,-10)).Magnitude<1e-6 and (line.direction-Vector3.new(0,0,-1)).Magnitude<1e-6
  and line.length==85 and line.width==9 and units[2].def.damage==22 and units[1].def.radius==12 and (stomp.direction-Vector3.new(1,0,0)).Magnitude<1e-6
end)
check('rubble wave: players 5, 30 and 80 down the line are hit at impact + d/55 (within one 60 Hz step), once; 4.6 off the side or 90 out never; the circle only within 12, at impact',function()
 local units=X.phases(slamDef,WT.attacks.Slam);for _,U in units do X.place(U,hf) end
 local function on(d,side) return Vector3.new(side or 0,3,-10-d) end
 local people={{player='d5',at=on(5)},{player='d30',at=on(30)},{player='d80',at=on(80)},{player='side',at=on(30,4.6)},{player='far',at=on(90)}}
 local first,count=struckBy(units,hf,people,3)
 local function at(d,key) local t=first[key];local due=.7+d/55;return t~=nil and t>=due-1e-9 and t<due+1/60+1e-9 and count[key]==1 end
 return at(5,'d5@2') and at(30,'d30@2') and at(80,'d80@2') and first['side@2']==nil and first['far@2']==nil
  and count['d5@1']==1 and math.abs(first['d5@1']-.7)<1/60+1e-9 and first['d30@1']==nil and first['side@1']==nil
end)
check('rubble wave: the attack lasts until the front reaches the far end (impact + 85/55 + 0.05), past the recovery',function()
 local units=X.phases(slamDef,WT.attacks.Slam)
 return math.abs(X.duration(units[2].def,units[2].at)-(.7+85/55+.05))<1e-9 and X.duration(units[1].def,units[1].at)==1.3
end)
check('rubble wave enraged: a fan of 3 lines (-25, 0, +25 deg) from one origin, the middle one P.line; a player on the +25 line is hit once (not per line), one between the lines 60 out never',function()
 local units=X.phases(slamDef,WT.attacks.Slam);local P=units[2];X.place(P,hf,FAN)
 local o=Vector3.new(0,0,-10);local function along(deg,d) return o+CFrame.Angles(0,math.rad(deg),0):VectorToWorldSpace(Vector3.new(0,0,-d))+Vector3.yAxis*3 end
 local angles=true
 for i,deg in FAN do if math.abs(S.yaw(Vector3.new(0,0,-1),P.lines[i].direction)-math.rad(deg))>1e-6 or (P.lines[i].origin-o).Magnitude>1e-6 then angles=false end end
 local first,count=struckBy({P},hf,{{player='plus',at=along(25,40)},{player='between',at=along(12.5,60)}},3)
 local due=.7+40/55
 return #P.lines==3 and P.line==P.lines[2] and angles and count['plus@1']==1 and first['plus@1']>=due-1e-9 and first['plus@1']<due+1/60+1e-9 and first['between@1']==nil
end)
check('rubble wave aim: a 0.6 rad turn rebuilds the phase\'s lines (the enraged fan kept) turned about the root, as the client turns the published ones; it sends its lines',function()
 local units=X.phases(slamDef,WT.attacks.Slam);local A={def=slamDef,at=WT.attacks.Slam,phases=units}
 X.reshape(A,X.frame(facing(),WT,0),{fan=FAN});local before={};for i,l in units[2].lines do before[i]=l end
 local data=X.unitData(units[2],units[2].line)
 local cf=CFrame.new(0,4,0)*CFrame.Angles(0,.6,0)*facing().Rotation;X.reshape(A,X.frame(cf,WT,0),{fan=FAN})
 for i,l in units[2].lines do
  local want=S.rotated(before[i],Vector3.zero,.6)
  if (l.origin-want.origin).Magnitude>1e-6 or (l.direction-want.direction).Magnitude>1e-6 then return false end
 end
 return #units[2].lines==3 and #data.lines==3 and data.shape.kind=='line' and units[1].arc==nil
end)
check('rubble wave aim: the wave phase (same impact as the circle) never re-aims after the slam: the frame holds from impact - lock through the travel',function()
 local A={cf=facing(),phases={{at={impact=.7,activeEnd=.7}},{at={impact=.7,activeEnd=.7}}}}
 return X.aimOpen(A,.39,AIM.lock) and not X.aimOpen(A,.4,AIM.lock) and not X.aimOpen(A,.7,AIM.lock) and not X.aimOpen(A,1.5,AIM.lock)
end)
-- The Charge ends in the Slam: its finish is the list {circle, wave}, timed by the Slam clip's phases.
local chargeW={clips={'ChargeStart','ChargeRun','Slam'},facing='forward',range={22,110},lockout=5,cooldown=1,damage=24,shape='lane',length=75,width=9,speed=32,contact=4,knockdown=.6,finish={SLAM12,WAVE}}
local function finishAttack(length,fan)
 local units={};for i,part in S.finishParts(chargeW) do units[i]={def=X.merged(chargeW,part),hits={},ticks={},fired=false} end
 return {def=chargeW,cf=laneCf,frame=X.frame(laneCf,WT,0),ground=0,dir=laneDir,length=length,data={},finish=units[1],finishes=units,fan=fan}
end
check('finish list: parts in order (a single finish is a list of one); the wave part is the wave, not the run (damage 22, no knockdown)',function()
 local single={finish=SLAM12};local list=S.finishParts(chargeW);local A=finishAttack(36)
 return #S.finishParts(single)==1 and S.finishParts(single)[1]==SLAM12 and S.finishParts({})==nil and list==chargeW.finish
  and A.finishes[2].def.shape=='wave' and A.finishes[2].def.damage==22 and A.finishes[2].def.knockdown==false and A.finishes[1].def.knockdown==.6 and A.finishes[2].def.facing=='forward'
end)
check('finish list: from where a 36-stud run ends, the circle (r 12) and the wave start at the HammerFace impact 10 on; the wave heads on down the run; both at the Slam\'s phase impact',function()
 local A=finishAttack(36);X.laneTiming(WT,A);local C,W=A.finishes[1],A.finishes[2];local start=.5+36/32
 local c=X.circle(C.def,C.at,C.frame)
 return A.finish==C and (c.center-Vector3.new(0,0,-46)).Magnitude<1e-6 and c.radius==12 and #W.lines==1 and (W.line.origin-Vector3.new(0,0,-46)).Magnitude<1e-6
  and (W.line.direction-laneDir).Magnitude<1e-6 and math.abs(C.start-start)<1e-9 and math.abs(W.start-start)<1e-9 and C.at.impact==.7 and W.at.impact==.7 and C.at.phases==nil
end)
check('finish list: the attack lasts past the wave\'s far end (run end + 0.7 + 85/55 + 0.05); the client\'s laneTimes agree; the old single circle only past its impact',function()
 local A=finishAttack(36);X.laneTiming(WT,A);local start=.5+36/32
 local single=X.merged(chargeW,{});single.finish=SLAM12;local t1=S.laneTimes(single,WT,36)
 return math.abs(A.duration-(start+.7+85/55+.05))<1e-9 and math.abs(S.laneTimes(chargeW,WT,36).duration-A.duration)<1e-9
  and math.abs(t1.duration-math.max(start+1.45,start+.7+.05))<1e-9 and math.abs(t1.finishImpact-(start+.7))<1e-9
end)
check('finish list data: finish.shape/impact stay the circle (older readers); finish.parts has both in order, the wave\'s lines and after = 0.7; enraged (A.fan) the wave sends 3 lines',function()
 local A=finishAttack(36);X.laneTiming(WT,A);local wire=game:GetService('HttpService'):JSONDecode(game:GetService('HttpService'):JSONEncode(A.data));local p=wire.finish.parts
 local c=S.decode(wire.finish.shape);local start=.5+36/32
 local R=finishAttack(36,FAN);X.laneTiming(WT,R)
 return c.kind=='circle' and c.radius==12 and math.abs(wire.finish.impact-(start+.7))<1e-6 and #p==2 and p[1].shape.kind=='circle' and p[1].lines==nil and #p[2].lines==1
  and p[2].shape.kind=='line' and math.abs(p[2].after-.7)<1e-9 and math.abs(p[2].impact-(start+.7))<1e-6 and #R.finishes[2].lines==3 and #R.data.finish.parts[2].lines==3
end)
check('finish list hits from the end of the run: the circle within 12 at the slam; the wave a player 40 past the run\'s end at end + 0.7 + 30/55, once; nobody before the run ends',function()
 local A=finishAttack(36);X.laneTiming(WT,A);local start=A.finishes[1].start
 local people={{player='near',at=Vector3.new(3,3,-44)},{player='down',at=Vector3.new(0,3,-76)},{player='aside',at=Vector3.new(14,3,-76)}}
 local first,count=struckBy(A.finishes,nil,people,start+3,start)
 local due=.7+30/55
 return count['near@1']==1 and math.abs(first['near@1']-.7)<1/60+1e-9 and first['down@1']==nil and count['down@2']==1 and first['down@2']>=due-1e-9 and first['down@2']<due+1/60+1e-9
  and first['aside@2']==nil and first['aside@1']==nil
end)
check('finish list homing: the parts run on from the body along its heading (the wave down the new heading)',function()
 local A=finishAttack(40);A.pos,A.travelled=Vector3.new(6,4,-14),15;A.dir=CFrame.Angles(0,-.4,0):VectorToWorldSpace(laneDir);X.laneTiming(WT,A)
 local endCf=CFrame.lookAt(A.pos,A.pos+A.dir)+A.dir*25;local want=X.wave(A.finishes[2].def,A.finishes[2].at,X.frame(endCf,WT,0))
 return (A.finishes[2].line.origin-want.origin).Magnitude<1e-6 and (A.finishes[2].line.direction-A.dir).Magnitude<1e-6
end)
check('intro: a clip with only phase times still lands on its first impact (MapBossShapes.impactOf)',function()
 return S.impactOf({impact=.7})==.7 and S.impactOf({phases={{impact=.6},{impact=.6}}})==.6 and S.impactOf({})==nil
  and S.hitEnd(WAVE,{impact=.7})==.7+85/55 and S.hitEnd(SLAM12,{impact=.7})==.7
end)
-- 4. Real defs: every projectile attack reaches a still player straight ahead (root 3 up) anywhere
-- in its range and at the boss's hold-off distance, replaying the server's shot test.
if Defs then
 check('phases: MapBossDefs divides phase times by rate (warned from the commit) and scales their points',function()
  local n=Defs.scaleAttack({duration=2,impact=1,phases={{warnStart=.3,impact=.5,activeEnd=.75,samples={P={{.5,1,2,3}}}},{impact=1,activeEnd=1.5}}},2,1.25);local p=n.phases
  return #p==2 and p[1].warnStart==0 and p[2].warnStart==0 and math.abs(p[1].impact-.4)<1e-9 and math.abs(p[1].activeEnd-.6)<1e-9 and math.abs(p[2].impact-.8)<1e-9
   and math.abs(p[2].activeEnd-1.2)<1e-9 and math.abs(p[1].samples.P[1][1]-.4)<1e-9 and p[1].samples.P[1][4]==6 and math.abs(n.impact-.8)<1e-9
 end)
 -- The four bosses keep their numbers: no combos, charges or tutorial variants, and only the
 -- Hammer (once it has a def) rewires anything here.
 local plain=true
 for _,id in {'KingCrab','Pharaoh','FrostCyclops','Dragon'} do
  local def=Defs.get(id);if def.tutorial or def.intro or def.roar or def.aim or (def.enrage and def.enrage.order) then plain=false end
  for _,a in def.attacks do if a.phases or a.finish or a.contact or a.lockout or a.facing or a.height or a.aim or a.home then plain=false end end
 end
 add(plain,'the four bosses use none of the Hammer fields (phases, finish, contact, lockout, facing, height, aim, home, intro, roar, tutorial, enrage.order)')
 -- The Hammer's chained moves (2026-10-04): Spin two sweeps, SwingSpin a swing and two spins, SpinSlam two
 -- spins and a slam; the Charge homes and ends in the Slam's clip and circle; every hit aims; no roar.
 local H=Defs.get('Hammer');local a=H and H.attacks
 add(H and H.chaseSpeed==24 and H.chaseSpeed+H.enrage.chase==26 and a.Charge.range[2]==110 and a.Charge.length==75 and a.Charge.speed==32,
  'Hammer closes distant kites while keeping capped, warned charge travel and bounded walking speed')
 local function kinds(x) local list={};for i,p in x.phases or x.finish or {} do list[i]=p.shape end;return table.concat(list,',') end
 add(H~=nil and kinds(a.Spin)=='sweep,sweep' and kinds(a.SwingSpin)=='sweep,sweep,sweep' and kinds(a.SpinSlam)=='sweep,sweep,circle,wave' and kinds(a.Slam)=='circle,wave'
  and a.Charge.clips[3]=='Slam' and a.Charge.home and kinds(a.Charge)=='circle,wave' and H.roar==nil and H.intro.clip=='Slam'
  and H.aim and H.aim.lock==.3 and math.abs(H.aim.rate-math.rad(150))<1e-9 and table.concat(Defs.ATTACK_CLIPS['hammer-brute'],',')=='Slam,Swing,Spin,SwingSpin,SpinSlam,ChargeStart,ChargeRun',
  'Hammer: Slam a circle and a wave, Spin, SwingSpin and SpinSlam chain 2-4 phases, the Charge homes into the Slam\'s circle and wave, every hit aims, no roar; ATTACK_CLIPS matches')
 -- The 2026-10-09 feedback ("not large enough for a boss fight, the range was short ... no ranged attacks").
 check('Hammer 2026-10-09: scale 1.5; every slam sends the rubble wave (85 x 9 at 55 studs/s, 22, along his facing, no knockdown), enraged a fan of 3; no follow-ups left',function()
  local W=a.Slam.phases[2];local same=a.SpinSlam.phases[4]==W and a.Charge.finish[2]==W and a.SpinSlam.phases[3]==a.Slam.phases[1] and a.Charge.finish[1]==a.Slam.phases[1]
  local follows=false
  for _,x in a do if x.follow then follows=true end;for _,p in x.phases or {} do if p.follow then follows=true end end;for _,p in type(x.finish)=='table' and x.finish or {} do if type(p)=='table' and p.follow then follows=true end end end
  return H.scale==1.5 and same and W.shape=='wave' and W.length==85 and W.width==9 and W.travel==55 and W.damage==22 and W.facing=='forward' and W.point=='HammerFace' and W.knockdown==false
   and table.concat(H.enrage.fan,',')=='-25,0,25' and H.enrage.follow==nil and not follows and H.introName=='HAMMER BRUTE'
 end)
 check('Hammer 2026-10-09: Slam circle 12 from up to 45 studs; sweeps 4.5 / 6; Spin 16 a revolution, SwingSpin 20/16/16, SpinSlam 16/16/26 + 22; aim, homing and pursuit kept',function()
  local function damages(x) local list={};for i,p in x.phases do list[i]=p.damage end;return table.concat(list,'/') end
  local C=a.Slam.phases[1];local sweeps=true
  for _,x in {a.Swing,a.Spin.phases[1],a.SwingSpin.phases[3],a.SpinSlam.phases[2]} do if x.radius~=4.5 or x.baseRadius~=6 then sweeps=false end end
  return C.shape=='circle' and C.radius==12 and C.height==6 and C.damage==26 and a.Slam.range[1]==0 and a.Slam.range[2]==45 and sweeps
   and damages(a.Spin)=='16/16' and damages(a.SwingSpin)=='20/16/16' and damages(a.SpinSlam)=='16/16/26/22' and a.Swing.damage==20
   and a.Charge.home==math.rad(40) and H.aim.lock==.3 and H.chaseSpeed==24 and H.enrage.chase==2 and a.Charge.range[2]==110 and H.enrage.cooldown==.6
 end)
 check('scale 1.5 timing: MapBossDefs.scaleAttack keeps a phased Slam\'s times (rate 1) and moves its HammerFace 1.5x out (10 -> 15 ahead), the circle\'s far edge 27',function()
  local n=Defs.scaleAttack(WT.attacks.Slam,1.5,1);local f15=X.frame(facing(),{rootHeight=4*1.5},0)
  local units=X.phases(a.Slam,n);local c=X.circle(units[1].def,units[1].at,f15);X.place(units[2],f15)
  return #n.phases==2 and n.phases[1].impact==.7 and n.phases[2].impact==.7 and n.impact==.7 and n.recoveryEnd==1.3 and n.samples.HammerFace[2][4]==-15
   and (c.center-Vector3.new(0,0,-15)).Magnitude<1e-6 and c.radius==12 and (units[2].line.origin-c.center).Magnitude<1e-6 and units[2].line.length==85
   and math.abs(X.duration(units[2].def,units[2].at)-(.7+85/55+.05))<1e-9
 end)
 -- Every attack an order names exists: X.walk would throw on every Heartbeat otherwise.
 local missing,defs={},0
 for id in Defs do
  local def=Defs.get(id)
  if def then
   defs+=1
   for _,list in {def.order,def.enrage and def.enrage.order,def.tutorial and def.tutorial.order} do
    for _,kind in list do if not def.attacks[kind] then table.insert(missing,id..'.'..tostring(kind)) end end
   end
  end
 end
 add(#missing==0 and defs>=4,('every order, enrage.order and tutorial.order names a real attack (%d defs; missing: %s)'):format(defs,#missing>0 and table.concat(missing,', ') or 'none'))
 -- Every clip an attack, intro or roar plays is one the build generates (ATTACK_CLIPS, which
 -- build_boss_modules.py ATTACKS mirrors, and the client's aliased() reads).
 local unlisted={}
 for id in Defs do
  local def=Defs.get(id)
  if def then
   local listed,used=Defs.ATTACK_CLIPS[def.anim] or {},{}
   for _,a in def.attacks do for _,c in a.clips or {a.clip} do table.insert(used,c) end end
   if def.intro then table.insert(used,def.intro.clip) end;if def.roar then table.insert(used,def.roar) end
   for _,c in used do if not table.find(listed,c) then table.insert(unlisted,id..'.'..tostring(c)) end end
  end
 end
 add(#unlisted==0,('every attack, intro and roar clip is in ATTACK_CLIPS (missing: %s)'):format(#unlisted>0 and table.concat(unlisted,', ') or 'none'))
 -- MapBossDefs.legacy / ready (rebuild R6): the one gate every 'Hammer' spawn asks. A stubbed
 -- has(kind,name) stands in for the place, so each missing piece is tried on its own.
 check('legacy: the Hammer is the old one unless def, timing, clips, template, MapBossService and MapBossShapes are all here; never another boss',function()
  local asked={};local function all(kind,name) asked[kind..':'..name]=true;return true end
  if Defs.legacy('Hammer',all)~=false or Defs.ready('Hammer',all)~=true then return false end
  for _,key in {'timing:Hammer','clips:hammer-brute','template:Hammer_NPC','server:MapBossService','shared:MapBossShapes'} do if not asked[key] then return false end end
  for _,missing in {'timing','clips','template','server','shared'} do
   local function has(kind) return kind~=missing end
   if Defs.legacy('Hammer',has)~=true or Defs.ready('Hammer',has) then return false end
  end
  local function none() return false end
  return Defs.legacy('KingCrab',none)==false and Defs.legacy('KingCrab',all)==false and not Defs.ready('KingCrab',none)
   and Defs.legacy('Nope',all)==false and Defs.ready('Nope',all)==false
 end)
 -- In this place: the Hammer stays the old one while MapBossTiming has no 'hammer-brute'.
 local okNow,readyNow=pcall(function()
  local list={};for _,id in Defs.Order do if Defs.ready(id) then table.insert(list,id) end end
  assert(Defs.timing('Hammer')~=nil or Defs.legacy('Hammer')==true,'the Hammer is not legacy without his timing')
  return #list>0 and table.concat(list,', ') or 'none'
 end)
 add(okNow,('legacy here: Hammer=%s (ready now: %s)'):format(tostring(okNow and Defs.legacy('Hammer')),tostring(readyNow)))
 local function segd(a,b,p) local ab=b-a;local t=math.clamp((p-a):Dot(ab)/math.max(ab:Dot(ab),1e-6),0,1);return (a+ab*t-p).Magnitude end
 -- The Dragon's tail whip hits a player standing 8 studs behind him (under his rear), as the
 -- server's hit loop tests it (tail chain inside the warning arc), and never one 8 studs in front.
 local tw=Defs.get('Dragon').attacks.TailWhip;local DT=Defs.timing('Dragon');local twat=X.window(tw,DT)
 local df=X.frame(CFrame.lookAt(Vector3.new(0,DT.rootHeight,0),Vector3.new(0,DT.rootHeight,-1)),DT,0)
 local twArc=X.sweepArc(tw,twat,df)
 local function struck(p)
  for t=X.hitFrom(tw,twat),twat.activeEnd,1/60 do if S.contains(X.sweep(tw,twat,df,t),p) and S.contains(twArc,p) then return t end end
  return nil
 end
 local behind=struck(Vector3.new(0,3,8))
 add(behind~=nil and X.hitFrom(tw,twat)<twat.impact and struck(Vector3.new(0,3,-8))==nil,
  ('Dragon TailWhip hits a player 8 studs behind him (at %s s; swing from %.2f s, impact %.2f s) and not 8 in front'):format(tostring(behind and math.floor(behind*100+.5)/100),X.hitFrom(tw,twat),twat.impact))
 for _,id in Defs.Order do
  -- The Hammer Brute's def comes before his generated timing (rebuild R6): an id without one is skipped.
  if not Defs.timing(id) then continue end
  local def,RT=Defs.get(id),Defs.timing(id);local rf=X.frame(CFrame.lookAt(Vector3.new(0,RT.rootHeight,0),Vector3.new(0,RT.rootHeight,-1)),RT,0)
  local stop=def.stop or math.min(8*def.scale,RT.footprintRadius or 4)+3
  for kind,a in def.attacks do
   if a.shape=='projectiles' then
    local list={a.range[1],a.range[2]};for d=a.range[1],a.range[2],5 do table.insert(list,d) end
    if stop>=a.range[1] and stop<=a.range[2] then table.insert(list,stop) end
    local miss={}
    for _,d in list do
     local goal=Vector3.new(0,3,-d);local v=X.volley(a,X.window(a,RT),rf,goal,kind=='BubbleBarrage');local o=Vector3.new(table.unpack(v.origin));local any=false
     for _,yaw in v.yaws do
      local pos=o
      for i=1,math.ceil(v.life*60) do local p=S.shot(o,yaw,v.speed,v.height,i/60);if segd(pos,p,goal)<=v.radius+1.2 then any=true;break end;pos=p end
      if any then break end
     end
     if not any then table.insert(miss,math.floor(d*10+.5)/10) end
    end
    add(#miss==0,('%s %s reaches a still player across its range (misses at %s)'):format(id,kind,#miss>0 and table.concat(miss,', ') or 'none'))
   end
  end
 end
end
local passed=0;for _,line in r do if line:sub(1,4)=='PASS' then passed+=1 end end
table.insert(r,('%d PASS, %d FAIL'):format(passed,#r-passed))
return table.concat(r,'\n')
