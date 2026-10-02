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
-- 4. Real defs: every projectile attack reaches a still player straight ahead (root 3 up) anywhere
-- in its range and at the boss's hold-off distance, replaying the server's shot test.
local defsModule=game.ReplicatedStorage.RogueliteCombat:FindFirstChild('MapBossDefs')
if defsModule then
 local c=defsModule:Clone();c.Parent=defsModule.Parent;local ok,Defs=pcall(require,c);c:Destroy();assert(ok,Defs)
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
return table.concat(r,'\n')
