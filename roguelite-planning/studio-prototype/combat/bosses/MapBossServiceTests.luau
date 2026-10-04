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
  local def=Defs.get(id);if def.tutorial or def.intro or def.roar or (def.enrage and def.enrage.order) then plain=false end
  for _,a in def.attacks do if a.phases or a.finish or a.contact or a.lockout or a.facing or a.height then plain=false end end
 end
 add(plain,'the four bosses use none of the Hammer fields (phases, finish, contact, lockout, facing, height, intro, roar, tutorial, enrage.order)')
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
