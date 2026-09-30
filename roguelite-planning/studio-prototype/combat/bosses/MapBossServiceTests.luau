-- MapBossServiceTests: pure shape-builder checks (plan F Task 7). Run with fresh(require) in Edit.
-- The timing table below is hand-made, so these run before the generated MapBossTiming exists;
-- an Edit-mode require of MapBossService loads only its pure builders (M._shapes).
local service=script.Parent:FindFirstChild('MapBossService') or game:GetService('ServerScriptService'):FindFirstChild('MapBossService')
assert(service,'MapBossService is not installed')
local X=require(service)._shapes
local S=require(game.ReplicatedStorage.RogueliteCombat.MapBossShapes)
local r={};local function add(ok,m) table.insert(r,(ok and 'PASS ' or 'FAIL ')..m) end
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
local lw=X.window(rush,T,30)
add(math.abs(lw.impact-.8)<1e-6 and math.abs(lw.duration-(.8+1+.6))<1e-6,'lane: duration = RushStart + length/speed + RushEnd')
-- 3. Sweep: the TailWhip capsule at impact contains the sampled SpadeTip.
local wat=X.window(whip,T);local tip=f.ground*S.sample(wat.samples.SpadeTip,wat.impact)
add(S.contains(X.sweep(whip,wat,f,wat.impact),tip),'sweep: capsule at impact contains the sampled SpadeTip')
add(not S.contains(X.sweep(whip,wat,f,wat.activeEnd),tip),'sweep: the capsule has moved on by activeEnd')
local arc=X.sweepArc(whip,wat,f)
add(S.contains(arc,tip) and S.contains(arc,f.ground*S.sample(wat.samples.SpadeTip,wat.activeEnd)) and not S.contains(arc,f.ground*Vector3.new(0,1,-10)),'sweep: warning arc covers the tip path, not the front')
-- Projectile fan and a missing sample track.
local ys=X.yaws({count=3,spread=math.rad(18)},Vector3.new(-1,0,0))
add(#ys==3 and math.abs(ys[2]-math.pi/2)<1e-6 and math.abs(ys[3]-ys[1]-math.rad(18))<1e-6,'projectiles: yaws spread evenly about the aim')
add(X.localPoint({points={P={rootAtImpactStudio={1,2,3}}}},'P',0)==Vector3.new(1,2,3),'point falls back to rootAtImpactStudio')
return table.concat(r,'\n')
