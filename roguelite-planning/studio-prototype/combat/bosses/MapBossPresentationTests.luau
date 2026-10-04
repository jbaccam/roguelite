-- MapBossPresentationTests: the client's pure helpers (Hammer Brute rebuild R4, 2026-10-03). Run in
-- Edit through tools/RepoRequire.luau only: R.run('MapBossPresentationTests'). MapBossPresentation
-- is a LocalScript, which a plain require can't load; RepoRequire runs its repo text, and that
-- returns its helpers (P) before anything client-side starts. Nothing is written to Studio.
-- The Hammer timings are hand-made (as in MapBossServiceTests); the four older bosses use their real
-- defs and timing, to show their paths are the old ones.
local Http=game:GetService('HttpService')
local P=require({Name='MapBossPresentation'})
local X=require({Name='MapBossService'})._shapes
local S=require({Name='MapBossShapes'})
local Defs=require({Name='MapBossDefs'})
local r={};local function add(ok,m) table.insert(r,(ok and 'PASS ' or 'FAIL ')..m) end
-- Protected: a missing helper reads as one FAIL line instead of stopping the run.
local function check(m,f) local ok,v=pcall(f);add(ok and v==true,m..(ok and '' or ' (error: '..tostring(v)..')')) end
local function near(a,b,eps) return type(a)=='number' and type(b)=='number' and math.abs(a-b)<(eps or 1e-9) end
local function with(t,extra) local c=table.clone(t);for k,v in extra do c[k]=v end;return c end

-- 1. The four bosses take the old paths.
local OLD={'KingCrab','Pharaoh','FrostCyclops','Dragon'}
check('four bosses: every attack window equals the server\'s (X.window, the crab rush at 30 studs too); none is a combo, charge or pseudo attack',function()
 for _,id in OLD do
  local def,T=Defs.get(id),Defs.timing(id)
  for _,a in def.attacks do
   if a.clips then
    for _,len in {0,30} do
     local L=len>0 and len or nil;local c,s=P.window(a,T,L),X.window(a,T,L)
     for _,k in {'warnStart','impact','activeEnd','recoveryEnd','duration'} do if not near(c[k],s[k]) then return false end end
    end
   elseif P.window(a,T)~=X.window(a,T) then return false end
   if P.isCharge(a) or P.phases(a,{phases={{impact=1}}},T)~=nil then return false end
  end
  for _,kind in {'Roar','IntroLand','Slam','ClawCrush'} do if P.pseudo(def,kind)~=nil then return false end end
 end
 return true
end)
check('four bosses: every warning outline is Shapes.outline as before (the Dragon TailWhip arc is no full ring)',function()
 local tw=Defs.get('Dragon').attacks.TailWhip;local DT=Defs.timing('Dragon')
 local df=X.frame(CFrame.lookAt(Vector3.new(0,DT.rootHeight,0),Vector3.new(0,DT.rootHeight,-1)),DT,0)
 local arc=X.sweepArc(tw,X.window(tw,DT),df)
 local list={arc,{kind='circle',center=Vector3.new(1,0,2),radius=9},{kind='line',origin=Vector3.zero,direction=Vector3.new(0,0,-1),length=40,width=7},
  {kind='cone',origin=Vector3.zero,direction=Vector3.new(1,0,0),halfAngle=math.rad(24),length=30}}
 for _,sh in list do
  local loops,o=P.edgeLoops(sh,48),S.outline(sh,48)
  if #loops~=1 or #loops[1]~=#o then return false end
  for i,p in o do if (loops[1][i]-p).Magnitude>1e-9 then return false end end
 end
 return not P.fullRing(arc)
end)
check('fade: a layer is exactly as painted at alpha nil or 1 (the old paint path), 35% opacity at .35',function()
 for _,t in {.78,.68,.42,.3,.2,1,0} do if P.fade(t,nil)~=t or P.fade(t,1)~=t then return false end end
 return near(P.fade(.78,.35),1-.22*.35) and near(P.fade(1,.35),1)
end)

-- 2. The Hammer, hand-made timing (MapBossServiceTests 5): HammerFace circles him 8 studs out.
local function th(t)
 if t<.4 then return -math.pi/2-.3*t/.4 elseif t<.45 then return -math.pi/2-.3
 elseif t<.66 then return -math.pi/2-.3+(math.pi+.3)*((t-.45)/.21)^2 elseif t<.72 then return math.pi/2 end
 return math.pi/2+(2*math.pi+.5)*math.min(1,(t-.72)/.53)^2
end
local function circling(radius) local list={};for k=0,96 do local t=k/60;local d=CFrame.Angles(0,th(t),0):VectorToWorldSpace(Vector3.new(0,0,-radius));list[k+1]={t,d.X,3,d.Z} end;return list end
local HT={rootHeight=4,clips={ChargeStart=.5,ChargeRun=.53,ChargeSlam=1.2,Roar=1.2,IntroLand=3},attacks={
 SwingSpin={duration=1.6,warnStart=0,impact=.5,activeEnd=1.25,recoveryEnd=1.6,phases={{warnStart=0,impact=.5,activeEnd=.7},{warnStart=0,impact=.8,activeEnd=1.25}},
  samples={HammerFace=circling(8),HammerGrip=circling(4)}},
 ChargeSlam={duration=1.2,warnStart=0,impact=.4,activeEnd=.45,recoveryEnd=1.2,samples={HammerFace={{0,0,6,-3},{.4,0,0,-5},{1.2,0,0,-5}}}},
 IntroLand={duration=3,warnStart=0,impact=.65,activeEnd=.65,recoveryEnd=3},
}}
local hammerSweep={shape='sweep',point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4}
local swingSpin={clip='SwingSpin',range={0,14},cooldown=1,phases={with(hammerSweep,{damage=20}),with(hammerSweep,{damage=22})}}
local charge={clips={'ChargeStart','ChargeRun','ChargeSlam'},facing='forward',range={22,70},lockout=5,cooldown=1,damage=24,shape='lane',length=75,width=9,speed=32,contact=4,
 finish={shape='circle',damage=26,point='HammerFace',radius=9.5,height=6,knockdown=.6}}
local crab={clips={'RushStart','RushLoop','RushEnd'},shape='lane',length=38,width=9,speed=30}
local hf=X.frame(CFrame.lookAt(Vector3.new(0,4,0),Vector3.new(0,4,-1)),HT,0)
local laneCf,laneDir=CFrame.lookAt(Vector3.new(0,4,0),Vector3.new(0,4,-1)),Vector3.new(0,0,-1)
-- A charge as MapBossService M.start builds it, for X.laneTiming.
local function chargeAttack(length)
 return {def=charge,cf=laneCf,frame=X.frame(laneCf,HT,0),ground=0,dir=laneDir,length=length,data={},finish={def=X.merged(charge,charge.finish),hits={},ticks={},fired=false}}
end
-- What the client receives: the server's data through JSON.
local function wire(t) return Http:JSONDecode(Http:JSONEncode(t)) end

check('charge: re-timed at 20, 36.5 and 75 studs, the window, duration and finish times match the server (X.window, X.laneTiming)',function()
 for _,len in {20,36.5,75} do
  local A=chargeAttack(len);X.laneTiming(HT,A);local t=P.chargeTiming(charge,HT,len)
  if not (near(t.at.impact,A.at.impact) and near(t.at.activeEnd,A.at.activeEnd) and near(t.duration,A.duration) and near(t.finishStart,A.finish.start) and near(t.finishImpact,A.data.finish.impact)) then return false end
 end
 local short,long=P.chargeTiming(charge,HT,20),P.chargeTiming(charge,HT,36)
 return P.isCharge(charge) and P.isCharge({shape='lane',contact=4}) and not P.isCharge(crab) and near(long.finishImpact-short.finishImpact,16/32)
end)
check('charge: without a finish, the duration is the lane window\'s (the crab rush: no finish times)',function()
 local plain=with(charge,{finish=false});local t=P.chargeTiming(plain,HT,30)
 return t.finishImpact==nil and near(t.duration,X.window(plain,HT,30).duration) and P.chargeTiming(crab,{clips={RushStart=.8,RushLoop=.5,RushEnd=.6}},30).finishImpact==nil
end)
-- The run's end. A target backs down the lane at 12 studs/s: the contact length is 20 + 12 t, so the
-- server (32 studs/s after the 0.5 s ChargeStart) stops at t = 1.8 with 41.6 studs. The client sees
-- BossChargeLength 100 ms late in 0.5-stud steps, and the stop data (stoppedAt) 100 ms after the stop.
check('charge stop: ChargeRun holds past the late prediction until stoppedAt arrives, then ChargeSlam from now - stoppedAt; it never goes back to the run',function()
 local start,imp,lat,dt,rate=1000,.5,.1,1/60,1.25
 local stopT=36/20;local stoppedAt=start+stopT;local final=20+12*stopT
 local stop,last,oldEnd,first,slamAt,back=nil,0,nil,nil,nil,false
 for k=0,180 do
  local age=k*dt;local seen=age-lat
  local length=seen>=stopT and final or 20+math.floor(math.max(0,12*seen)/.5)*.5
  local predicted=imp+length/32
  if not oldEnd and age>=imp and age>=predicted then oldEnd=age end -- the old client's switch
  stop=P.chargeStop(stop,predicted,seen>=stopT and stoppedAt-start or nil,age)
  local phase,slam=P.chargePhase(imp,stop,age,rate)
  if phase<last then back=true end;last=phase
  if phase==3 and not first then first,slamAt=age,slam end
 end
 return oldEnd~=nil and oldEnd<stopT and not back and first~=nil and first>=stopT+lat-1e-9 and first<stopT+lat+dt+1e-9
  and near(slamAt,(start+first-stoppedAt)*rate) and near(stop,stopT)
end)
check('charge stop: with no stop data, the prediction counts only 0.75 s after it passes; a late longer length then never reopens the run',function()
 local stop,last,back,latchedAt=nil,0,false,nil
 for k=0,240 do
  local age=k/60;local predicted=.5+(age<2.3 and 30 or 40)/32 -- 1.4375, then a late 1.75
  stop=P.chargeStop(stop,predicted,nil,age)
  local phase=P.chargePhase(.5,stop,age)
  if phase<last then back=true end;last=phase
  if stop and not latchedAt then latchedAt=age end
 end
 return not back and last==3 and near(stop,.5+30/32) and latchedAt>=.5+30/32+P.CHARGE_HOLD-1e-9 and latchedAt<.5+30/32+P.CHARGE_HOLD+1/60
end)
check('charge stop: a latched end only moves earlier (a later stop is ignored, an earlier one taken); still running inside the hold',function()
 return P.chargeStop(1.4,1.2,1.6,2)==1.4 and P.chargeStop(1.4,1.2,1.3,2)==1.3 and P.chargeStop(nil,1.2,nil,1.5)==nil and P.chargeStop(nil,1.2,nil,1.95)==1.2
  and P.chargeStop(nil,1.2,1.7,1.5)==1.7 and P.chargePhase(.5,1.7,1.5)==2 and P.chargePhase(.5,nil,9)==2 and P.chargePhase(.5,nil,.2)==1
end)
check('charge: the lane and finish published at 30 studs, redrawn for 40, equal what the server publishes at 40',function()
 local A=chargeAttack(30);X.laneTiming(HT,A);local d30=wire(A.data)
 A.length=40;X.laneTiming(HT,A);local d40=wire(A.data)
 local lane30,lane40,fin30,fin40=S.decode(d30.shape),S.decode(d40.shape),S.decode(d30.finish.shape),S.decode(d40.finish.shape)
 local l,f=P.laneAt(lane30,d30.length,40),P.moved(fin30,laneDir,40-d30.length)
 return near(l.length,lane40.length,1e-6) and (l.origin-lane40.origin).Magnitude<1e-6 and (l.direction-lane40.direction).Magnitude<1e-6 and l.width==lane40.width
  and (f.center-fin40.center).Magnitude<1e-6 and f.radius==fin40.radius and near(lane30.length,30+9,1e-6) and (fin30.center-S.decode(d30.finish.shape).center).Magnitude<1e-9
end)
check('phases: from MapBossAttackData.phases: merged defs, the server\'s times and decoded shapes (the Spin a full ring); the clip window filled from them',function()
 local units=X.phases(swingSpin,HT.attacks.SwingSpin);local data={phases={}}
 for i,U in units do data.phases[i]={shape=S.encode(X.shapeOf(U.def,U.at,hf)),warnStart=U.at.warnStart,impact=U.at.impact,activeEnd=U.at.activeEnd} end
 local list=P.phases(swingSpin,wire(data),HT)
 local filled=P.comboWindow({duration=1.6,recoveryEnd=1.6},list)
 return #list==2 and list[1].def.damage==20 and list[2].def.damage==22 and list[2].def.phases==nil and list[2].def.clip=='SwingSpin' and swingSpin.phases~=nil
  and list[1].impact==.5 and list[1].activeEnd==.7 and list[2].impact==.8 and list[2].activeEnd==1.25 and list[2].warnStart==0
  and list[1].shape.kind=='arc' and not P.fullRing(list[1].shape) and P.fullRing(list[2].shape)
  and filled.impact==.5 and filled.activeEnd==1.25 and filled.warnStart==0 and P.comboWindow(HT.attacks.SwingSpin,list)==HT.attacks.SwingSpin
end)
check('phases: no data.phases (or a phase with no impact anywhere) falls back to the single-shape path',function()
 return P.phases(swingSpin,{},HT)==nil and P.phases(swingSpin,{phases={{impact=.5}}},{attacks={}})==nil and P.phases({clip='Slam',shape='circle'},{phases={{impact=1}}},HT)==nil
  and #P.phases(swingSpin,{phases={}},HT)==2 -- the clip's own phase timing
end)
check('phase alpha: the first phase full; a later one 35% at its warnStart, full by impact - 0.35 s, rising in between',function()
 local mid=P.phaseAlpha(true,.2,0,.8)
 return P.phaseAlpha(false,0,0,.8)==1 and near(P.phaseAlpha(true,0,0,.8),.35) and near(P.phaseAlpha(true,.45,0,.8),1) and mid>.35 and mid<1
  and P.phaseAlpha(true,.8,0,.8)==1 and P.phaseAlpha(true,.3,0,.3)>.35
end)
check('full ring: its edges are whole circles round the pivot (outer, and inner when cut), with no seam; Shapes.outline alone seams to the pivot',function()
 local units=X.phases(swingSpin,HT.attacks.SwingSpin);local ring=X.shapeOf(units[2].def,units[2].at,hf)
 local function on(pts,radius) for _,p in pts do if math.abs(S.flat(p-ring.pivot).Magnitude-radius)>1e-6 then return false end end;return #pts>=32 end
 local seam=false;for _,p in S.outline(ring,48) do if S.flat(p-ring.pivot).Magnitude<1e-6 then seam=true end end
 local loops=P.edgeLoops(ring,48);local cut=with(ring,{inner=3});local two=P.edgeLoops(cut,48)
 return P.fullRing(ring) and seam and #loops==1 and on(loops[1],ring.outer) and #two==2 and on(two[1],ring.outer) and on(two[2],3)
end)
check('pseudo: the intro clip and the roar play as attacks (their timing, else the clip length); no other kind, and no boss without them',function()
 local def={intro={drop=1.2,fall=.65,after=3.6,clip='IntroLand'},roar='Roar',attacks={}}
 local intro,roar=P.pseudo(def,'IntroLand'),P.pseudo(def,'Roar');local rw=P.window(roar,HT)
 return intro.pseudo=='intro' and roar.pseudo=='roar' and intro.rate==1 and P.window(intro,HT)==HT.attacks.IntroLand and rw.duration==1.2 and rw.warnStart==0
  and P.pseudo(def,'Slam')==nil and P.pseudo({attacks={}},'Roar')==nil and P.window({clip='Nope',pseudo='roar'},HT)==nil
end)
check('merged: the phase on top, phases and finish dropped, the def itself untouched',function()
 local m=P.merged(charge,charge.finish)
 return m.shape=='circle' and m.damage==26 and m.radius==9.5 and m.finish==nil and m.clips==charge.clips and charge.shape=='lane' and charge.finish~=nil
end)

local passed=0;for _,line in r do if line:sub(1,4)=='PASS' then passed+=1 end end
table.insert(r,('%d PASS, %d FAIL'):format(passed,#r-passed))
return table.concat(r,'\n')
