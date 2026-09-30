-- Giant King Crab effects (plan F Task 11). Client-only; nothing here changes hits.
-- ClawCrush: sand trickles off the raised claw; the palm lands in a coral shockwave, a crown splash,
-- sand spray and flung shell chips. SidewaysRush: dust as it braces, sand kicked from both leg
-- groups while it scuttles, a furrow along the lane and a skid burst at the stop.
-- BubbleBarrage: mouth foam that pumps with the clip; wobbling bubbles that pop into splashes.
local C=require(script.Parent:WaitForChild('Common'))
local K=C.K
local ns=C.ns
local up=Vector3.yAxis
local CORAL,SAND,WATER,FOAM,WHITE=Color3.fromRGB(255,128,98),Color3.fromRGB(228,202,152),Color3.fromRGB(186,236,255),Color3.fromRGB(236,250,255),Color3.new(1,1,1)
local FURROW=Color3.fromRGB(128,98,66) -- ScorchMark tinted to damp dug sand
local CHIPS={'ShellChip_A','ShellChip_B','ShellChip_C'}
local SHELL={CORAL,Enum.Material.SmoothPlastic}
local Crab={}

local function sandSpray(pos,look,count,speed,spread)
 C.emit(pos,look,'SandSpray',{emit=count,Speed=speed,SpreadAngle=spread,Lifetime={.45,.7},Size=ns({0,1.2},{1,2.8}),Color=SAND,Transparency=ns({0,0},{.7,.2},{1,1}),Acceleration=Vector3.new(0,-45,0),Drag=.8,Rotation={-40,40},LightInfluence=.8})
end
local function dust(pos,look,count,speed,size)
 C.emit(pos,look,'DustPuff',{emit=count,Speed=speed,SpreadAngle=85,Drag=4,Lifetime={.7,1},Size=ns({0,size*.5},{1,size}),Color=SAND,Transparency=ns({0,.25},{.6,.4},{1,1}),LightInfluence=.8,Rotation={0,360},RotSpeed={-40,40}})
end
local function splash(pos,look,count,speed,spread,size)
 C.emit(pos,look,'WaterSplash',{emit=count,Speed=speed,SpreadAngle=spread,Lifetime={.35,.55},Size=ns({0,size*.5},{1,size}),Color=WATER,Transparency=ns({0,0},{.7,.25},{1,1}),Acceleration=Vector3.new(0,-40,0),Rotation={-30,30},LightEmission=.2,LightInfluence=.6})
end

-- ClawCrush -------------------------------------------------------------------------------
local function crushWindup(ctx)
 local at,def=ctx.attack,ctx.def;local claw=ctx.points(def.point,C.age(ctx));if not C.near(claw) then return end
 C.cue('crab_windup',claw,.75)
 local host=C.part('Host',Vector3.new(2.5,.5,2.5),C.aim(claw,-up),K.White,1)
 C.fx(host,'SandSpray',{Rate=20,Speed={1,3},SpreadAngle=25,Lifetime={.5,.7},Size=ns({0,.9},{1,1.8}),Color=SAND,Transparency=ns({0,.15},{.7,.35},{1,1}),Acceleration=Vector3.new(0,-26,0),Rotation={0,360},RotSpeed={-90,90},LightInfluence=.8})
 local glint=false
 C.follow(ctx,at.impact,function(age)
  local p=ctx.points(def.point,age);host.CFrame=C.aim(p,-up)
  if not glint and age>=at.impact-.3 then glint=true;C.star(p+up*1.5,Color3.fromRGB(255,236,222),5,.18) end -- the claw flashes at the top
 end,function() C.retire({host},.8) end)
end
local function crushImpact(ctx)
 local at,def=ctx.attack,ctx.def;local g=C.ground(ctx,ctx.points(def.point,at.impact))
 C.shake(g,.8,.35);if not C.near(g) then return end
 C.cue('crab_slam',g,.9)
 C.star(g+up*2.2,Color3.fromRGB(255,226,206),9,.2);C.light(g+up*3,Color3.fromRGB(255,214,190),18,2.2,.3)
 C.ring(g+up*.06,'ShockwaveRing',1,14,.45,CORAL,0,true);C.ring(g+up*.08,'ShockwaveRing',1,8,.22,Color3.fromRGB(255,244,236),.1,true)
 C.emit(g+up*.3,up,'WaterSplash',{emit=22,Speed={18,28},SpreadAngle=35,Lifetime={.55,.75},Size=ns({0,1.4},{1,2.8}),Color=WATER,Transparency=ns({0,0},{.75,.2},{1,1}),Acceleration=Vector3.new(0,-70,0),Drag=.6,Rotation={-25,25},LightEmission=.25,LightInfluence=.6})
 -- Two crown splashes standing on the sand (the sheet is bottom-anchored, so centre them half up).
 C.emit(g+up*4,up,'WaterSplash',{emit=2,Speed=0,Lifetime={.55,.65},Size=ns({0,7},{1,9}),Color=WATER,Transparency=ns({0,0},{.8,.1},{1,1}),LightEmission=.2,LightInfluence=.6})
 sandSpray(g+up*.3,up,30,{12,20},65);dust(g+up*.4,up,8,{10,14},4)
 C.chunks(g+up*1.5,ctx.groundY,CHIPS,{count=3,speed={10,16},up={14,22},scale={2.4,3.2},life=1.4,fallback=SHELL})
end

-- SidewaysRush ----------------------------------------------------------------------------
local function rushWindup(ctx)
 local g=C.ground(ctx,ctx.cf.Position);if not C.near(g) then return end
 C.cue('crab_windup',g,.6,1.15)
 for i=1,6 do local a=i/6*math.pi*2;local out=Vector3.new(math.cos(a),0,math.sin(a));dust(g+out*5+up*.4,out+up*.5,3,{4,7},3.5) end
end
-- From launch to the skid: follows the replicated body, kicks sand behind both leg groups while
-- it moves, lays the furrow and plays the scuttle loop. The lane comes from MapBossAttackData.
local function rush(ctx)
 if ctx.crabRush then return end;ctx.crabRush=true
 local at,def,data=ctx.attack,ctx.def,ctx.data
 local dir=data.dir and Vector3.new(data.dir[1],0,data.dir[2]) or C.flat(ctx.cf.LookVector);if dir.Magnitude<.05 then dir=C.flat(ctx.cf.LookVector) end;dir=dir.Unit
 local length=data.length or def.length;local start=C.ground(ctx,ctx.cf.Position)
 if not C.near(start+dir*length/2,length/2) then return end
 sandSpray(start-dir*4+up*.4,-dir+up*.7,20,{12,18},30);dust(start-dir*3+up*.4,-dir+up*.3,6,{8,12},4);C.shake(start,.35,.2) -- launch kick
 local back=-dir+up*.9;local feet={}
 for i,off in {4.5,-4.5} do
  local h=C.part('Host',Vector3.new(3,.3,1.5),C.aim(start+dir*off+up*.3,back),K.White,1)
  feet[i]={host=h,off=off,
   spray=C.fx(h,'SandSpray',{Rate=0,Enabled=true,Speed={9,15},SpreadAngle=30,Lifetime={.45,.65},Size=ns({0,1.1},{1,2.6}),Color=SAND,Transparency=ns({0,0},{.7,.25},{1,1}),Acceleration=Vector3.new(0,-40,0),Drag=.8,Rotation={-40,40},LightInfluence=.8}),
   dust=C.fx(h,'DustPuff',{Rate=0,Enabled=true,Speed={2,4},SpreadAngle=60,Lifetime={.6,.9},Size=ns({0,1.5},{1,3.2}),Color=SAND,Transparency=ns({0,.4},{1,1}),Drag=2,LightInfluence=.8,Rotation={0,360}})}
 end
 local s,sh=C.cue('crab_scuttle',start,.7,1.1,true)
 local furrow,laid,last={},0,start
 C.follow(ctx,at.activeEnd,function(age)
  local root=ctx.npc.PrimaryPart;local pos=root and C.ground(ctx,root.Position) or start+dir*math.clamp((age-at.impact)*def.speed,0,length)
  local moving=(pos-last).Magnitude>.02;last=pos
  for _,f in feet do
   f.host.CFrame=C.aim(pos+dir*f.off+up*.3,back)
   if f.spray then f.spray.Rate=moving and 60 or 0 end;if f.dust then f.dust.Rate=moving and 12 or 0 end
  end
  if sh then sh.CFrame=CFrame.new(pos+up*2) end
  -- A furrow plate every 2.6 studs, laid just behind the body.
  local along=(pos-start):Dot(dir)
  while laid+2.6<=along-1 do
   laid+=2.6;local p,set=C.plate(start+dir*laid+up*.03,'ScorchMark',6.5,FURROW,nil,false)
   if p then set(.45);table.insert(furrow,{p=p,set=set}) end
  end
 end,function(stopped)
  local root=ctx.npc.PrimaryPart;local pos=root and root.Parent and C.ground(ctx,root.Position) or last
  local hosts={};for i,f in feet do hosts[i]=f.host end;C.retire(hosts,.9);C.stopSound(s,sh,.15)
  if not stopped then
   -- The skid: sand thrown forward as the legs dig in.
   sandSpray(pos+dir*4+up*.4,dir+up*.8,30,{14,22},35);dust(pos+dir*3+up*.4,dir+up*.3,10,{9,14},4.5)
   C.chunks(pos+dir*3+up*1,ctx.groundY,CHIPS,{count=2,speed={8,12},up={10,14},scale={2,2.6},life=1.1,dir=dir,fallback=SHELL})
   C.shake(pos,.5,.25);C.cue('crab_slam',pos,.45,1.25)
  end
  -- The furrow fades over 1.5 s once the rush is over.
  if #furrow>0 then K.animate(1.5,function(t) for _,f in furrow do f.set(.45+.55*K.smooth(t)) end end,function() for _,f in furrow do f.p:Destroy() end end,'bossPlate',64) end
 end)
end

-- BubbleBarrage ---------------------------------------------------------------------------
-- Mouth foam from windup to the end of the volley, with an extra gush on each authored pump.
local function foam(ctx)
 if ctx.crabFoam then return end;ctx.crabFoam=true
 local at,def=ctx.attack,ctx.def;local age0=C.age(ctx);local m=ctx.points(def.point,age0);if not C.near(m) then return end
 C.cue('crab_windup',m,.55,1.1);C.cue('bubbles',m,.35)
 local host=C.part('Host',Vector3.one*1.2,C.aim(m,ctx.dirAt(def.point,age0)),K.White,1)
 local e=C.fx(host,'Bubble',{Rate=30,Speed={2,4},SpreadAngle=40,Lifetime={.5,.8},Size=ns({0,.25},{.5,.55},{1,.4}),Color=FOAM,Transparency=ns({0,.1},{.8,.25},{1,1}),Acceleration=Vector3.new(0,3,0),Drag=1.5,Rotation={0,360},LightEmission=.2,LightInfluence=.6})
 local pumped={}
 C.follow(ctx,at.activeEnd+.05,function(age)
  local p,d=ctx.points(def.point,age),ctx.dirAt(def.point,age);host.CFrame=C.aim(p,d)
  for i,t in at.pumps or {} do
   if not pumped[i] and age>=t then
    pumped[i]=true;if e then e:Emit(14) end
    splash(p,d+up*.3,4,{6,10},30,2);C.cue('bubbles',p,.4,1+i*.08)
   end
  end
 end,function() C.retire({host},.9) end)
end
local function launch(ctx)
 local at,def=ctx.attack,ctx.def;local m=ctx.points(def.point,at.impact);if not C.near(m) then return end
 local d=ctx.dirAt(def.point,at.impact)
 C.cue('bubbles',m,.6);K.pop(C.folder(),m,FOAM,1,4,.22,.55)
 splash(m,d,8,{8,14},30,2.4)
 C.emit(m,d,'Bubble',{emit=20,Speed={6,12},SpreadAngle=45,Lifetime={.5,.8},Size=ns({0,.3},{1,.6}),Color=FOAM,Drag=2,Acceleration=Vector3.new(0,4,0),LightInfluence=.6})
end
-- A bubble: a glassy ball under the kit's Bubble sprite (rim, shine and highlight), wobbling ±8% at
-- 6 Hz, trailing mini bubbles; it pops into a splash where the server stopped it.
function Crab.projectile(ctx,i)
 local d=(ctx.def.radius or 1.5)*2
 local ball=K.ball(C.folder(),'BossVfxBubble',d,Color3.fromRGB(190,236,255),.62,Enum.Material.Glass)
 local _,g=C.sprite(ball,'Bubble',d*1.08,WHITE,.05)
 local tail=C.tail(ball,(ctx.def.life or 2.6)+2,.9)
 C.fx(tail,'Bubble',{Rate=14,Speed={.5,1.5},SpreadAngle=180,Lifetime={.6,.9},Size=ns({0,.45},{1,.15}),Color=FOAM,Transparency=ns({0,.1},{1,.8}),Acceleration=Vector3.new(0,2.5,0),Drag=1.5,LightInfluence=.6})
 local t,phase=0,i*.7
 return ball,function(dt)
  t+=dt;local w=math.sin(t*math.pi*12+phase)*.08
  ball.Size=Vector3.new(d*(1+w),d*(1-w),d*(1+w))
  if g then g.Size=UDim2.fromScale(d*1.08*(1+w),d*1.08*(1-w)) end
 end,function(pos)
  if not C.near(pos) then return end
  K.pop(C.folder(),pos,FOAM,d*.7,d*1.7,.2,.5)
  splash(pos,up,10,{6,12},180,1.6)
  C.emit(pos,up,'Bubble',{emit=6,Speed={3,6},SpreadAngle=180,Lifetime={.3,.5},Size=ns({0,.35},{1,.1}),Color=FOAM,Drag=2,LightInfluence=.6})
  local now=os.clock();if now-(ctx.crabPop or 0)>.09 then ctx.crabPop=now;C.cue('bubbles',pos,.45,1.2+math.random()*.3) end -- a volley popping at once gets one pop per 0.09 s
 end
end

function Crab.windup(ctx)
 local k=ctx.kind
 if k=='ClawCrush' then crushWindup(ctx) elseif k=='SidewaysRush' then rushWindup(ctx) elseif k=='BubbleBarrage' then foam(ctx) end
end
function Crab.impact(ctx)
 local k=ctx.kind
 if k=='ClawCrush' then crushImpact(ctx) elseif k=='SidewaysRush' then rush(ctx) elseif k=='BubbleBarrage' then foam(ctx);launch(ctx) end
end
-- The rush's impact is the launch (end of RushStart); active keeps its controller alive if the impact was missed.
function Crab.active(ctx,age) if ctx.kind=='SidewaysRush' then rush(ctx) end end
return Crab
