-- Hammer Brute effects (rebuild R5, 2026-10-03). Client-only; nothing here changes hits. Flat
-- stylized effects only: Neon segments, painted kit textures tinted here, 4x4 flipbooks and ground
-- decals; no shaded effect meshes (no flung chunks either).
-- Slams (the Slam, a combo's circle phase, the charge's finish): dust gathers on the raised head and
--   a whoosh on the downswing; then a white snap ring out to the hit edge, a slower dust ring, an
--   impact star, dust and dirt thrown up, EarthCracks for ~2.5 s, and a shake that fades with distance.
-- Sweeps (Swing, Spin, a combo's sweep phases): a Neon crescent laid along the sampled HammerFace
--   track while it moves fast (a white rim on the outside, red once enraged), dust where it skims.
-- Charge: dust as he loads, a rumble and dust at every footfall while he runs, a skid streak and
--   dirt thrown forward where he stops, then the finish slam where the circle has moved to.
-- Follow-up cracks (followup / aftershock): each circle opens a crack decal that grows until it
--   erupts in a dirt burst.
-- Enrage (fired as the roar starts): the eyes ignite red and stay; at the roar's peak a red roar
--   ring, steam puffs and a shake; steam keeps rising off his head for the rest of the fight.
-- Intro (fired at the landing): a landing ring, dust wall, cracks and shake (BossIntro.client has
--   the boom, its own shockwave and the camera).
-- Shapes and times come from the server's data (ctx.phases, C.phaseShape, C.shape, C.finish), so
-- what the effects mark is what hurts. Sounds: the game's small kit, pitch-shifted (BossVfxAssets).
local C=require(script.Parent:WaitForChild('Common'))
local K=C.K
local ns=C.ns
local up=Vector3.yAxis
local POINT='HammerFace'
local DUST,DIRT,CRACK=Color3.fromRGB(214,196,160),Color3.fromRGB(128,96,64),Color3.fromRGB(92,70,52)
local PALE,WHITE,WARM=Color3.fromRGB(255,246,226),Color3.new(1,1,1),Color3.fromRGB(255,214,160)
local RED,STEAM=Color3.fromRGB(255,52,40),Color3.fromRGB(232,232,226)
local SWEEP_SPEED=16 -- studs/s: the head moving at least this fast lays crescent (the wind-up holds don't)
local H={}

local function dust(pos,look,count,speed,size,spread)
 C.emit(pos,look or up,'DustPuff',{emit=count,Speed=speed or {6,10},SpreadAngle=spread or 60,Drag=3,Lifetime={.6,1},Size=ns({0,size*.45},{1,size}),Color=DUST,Transparency=ns({0,.25},{.6,.45},{1,1}),LightInfluence=.8,Rotation={0,360},RotSpeed={-40,40}})
end
local function dirt(pos,look,count,speed,spread,size)
 C.emit(pos,look or up,'SandSpray',{emit=count,Speed=speed,SpreadAngle=spread or 45,Lifetime={.45,.7},Size=ns({0,(size or 1.2)},{1,(size or 1.2)*2.3}),Color=DIRT,Transparency=ns({0,0},{.7,.2},{1,1}),Acceleration=Vector3.new(0,-50,0),Drag=.8,Rotation={-40,40},LightInfluence=.8})
end
-- The EarthCracks decal (skipped until the texture is uploaded: C.texture is nil).
local function cracks(pos,size,seconds)
 local id=C.texture('EarthCracks');if not id or not C.near(pos,size) then return end
 C.decal(pos,id,size,CRACK,.05,seconds-.8,.75,math.random(0,359))
end
local function groundAt(ctx,p) return Vector3.new(p.X,ctx.groundY,p.Z) end

-- Slams -----------------------------------------------------------------------------------
-- Dust trickling off the raised head, a glint at the top, and the whoosh on the downswing.
local function slamWindup(ctx,impact)
 local age0=C.age(ctx);if age0>=impact-.05 then return end
 local head=ctx.points(POINT,age0)
 if C.near(head) then
  local host=C.part('Host',Vector3.one*1.6,CFrame.new(head),K.White,1)
  C.fx(host,'DustPuff',{Rate=12,Speed={.5,2},SpreadAngle=50,EmissionDirection=Enum.NormalId.Bottom,Lifetime={.5,.8},Size=ns({0,.6},{1,1.6}),Color=DUST,Transparency=ns({0,.35},{.6,.55},{1,1}),Acceleration=Vector3.new(0,-14,0),Drag=1.5,LightInfluence=.8,Rotation={0,360},RotSpeed={-60,60}})
  local glint=false
  C.follow(ctx,impact,function(age)
   local p=ctx.points(POINT,age);host.CFrame=CFrame.new(p)
   if not glint and age>=impact-.3 then glint=true;C.star(p+up,PALE,4*(ctx.scale or 1),.16) end
  end,function() C.retire({host},.8) end)
 end
 C.at(ctx,math.max(age0,impact-.22),function() C.cue('hammer_whoosh',ctx.points(POINT,C.age(ctx)),.7,.62) end)
end
local function slam(ctx,g,r,big)
 local s=ctx.scale or 1
 C.shake(g,big and 1.9 or 1.6,.55);if not C.near(g,r) then return end
 C.cue('hammer_boom',g,.9,.72);C.cue('hammer_thud',g,.55,.62)
 C.star(g+up*2.5,PALE,r*1.3,.22);C.light(g+up*3,WARM,r*2.6,2.8,.4)
 C.ring(g+up*.06,'ShockwaveRing',2,r*2.2,.3,PALE,0,true) -- the snap, out to the hit edge
 C.ring(g+up*.09,'ShockwaveRing',r*.8,r*3.4,.8,DUST,.35,true) -- a slower rolling dust wave
 cracks(g+up*.035,r*2.1,2.5)
 C.dustRing(g,r*.85,14,DUST,{18,26},4.5*s)
 dust(g+up*.5,up,16,{10,16},r*.7,80)
 dirt(g+up*.3,up,28,{14,24},55,1.3*s)
end
-- Where a circle lands: the server's shape, else the sampled head on the ground.
local function slamAt(ctx,u,big)
 local c=u.shape and u.shape.kind=='circle' and u.shape.center or groundAt(ctx,ctx.points(u.point or POINT,u.impact))
 slam(ctx,c,(u.shape and u.shape.radius) or u.radius or 9.5,big)
end

-- Sweeps ----------------------------------------------------------------------------------
-- One crescent piece from a to b: a flat Neon band (width across the swing) with a thin rim on the
-- side away from the boss; it thins and fades in 0.3 s, so the newest piece is the widest.
local function piece(a,b,center,s,rim)
 local len=(b-a).Magnitude;local mid=(a+b)/2;local out=C.flat(mid-center);out=out.Magnitude>.1 and out.Unit or Vector3.zero
 local w=2.4*s
 local body=C.part('Crescent',Vector3.new(w,.1,len+.2),CFrame.lookAt(mid,b),PALE,.25);body.Material=Enum.Material.Neon
 local edge=C.part('CrescentRim',Vector3.new(.35*s,.12,len+.2),CFrame.lookAt(mid+out*w*.5,b+out*w*.5),rim,.05);edge.Material=Enum.Material.Neon
 K.animate(.3,function(t)
  local k=K.smooth(t);body.Size=Vector3.new(w*(1-.7*t),.1,len+.2);body.Transparency=.25+.75*k;edge.Transparency=.05+.95*k
 end,function() body:Destroy();edge:Destroy() end,'bossSweep',220)
end
local function crescent(ctx,from,to,key)
 ctx.hammerSweeps=ctx.hammerSweeps or {};if ctx.hammerSweeps[key] then return end;ctx.hammerSweeps[key]=true
 local s=ctx.scale or 1;local center=groundAt(ctx,ctx.cf.Position);local rim=ctx.enraged and RED or WHITE
 if not C.near(center,30) then return end
 local last,lastAge,whooshed,nextDust
 C.follow(ctx,to+.02,function(age)
  if age<from then return end
  local p=ctx.points(POINT,age)
  if not last then last,lastAge=p,age;return end
  local step=p-last;local dt=age-lastAge
  if dt<=1e-4 or step.Magnitude<.3 then return end
  if step.Magnitude/dt>=SWEEP_SPEED then
   if not whooshed then whooshed=true;C.cue('hammer_whoosh',p,.8,.72) end
   piece(last,p,center,s,rim)
   if p.Y-ctx.groundY<3.5*s and age>=(nextDust or 0) then
    nextDust=age+.05;local v=C.flat(step);dust(groundAt(ctx,p)+up*.4,(v.Magnitude>.01 and v.Unit or Vector3.zero)+up*.6,2,{7,12},3.5*s,30)
   end
  end
  last,lastAge=p,age
 end)
end

-- The attack's hits: each combo phase (ctx.phases), else the attack itself. A sweep's crescent runs
-- from where the hit before it ended (its wind-up is too slow to draw).
local function units(ctx)
 local list={}
 if ctx.phases then
  local prev=0
  for i,ph in ctx.phases do
   table.insert(list,{key=i,kind=ph.def.shape,from=prev,impact=ph.impact,to=ph.activeEnd,shape=ph.shape or C.phaseShape(ctx,i),radius=ph.def.radius,point=ph.def.point})
   prev=ph.activeEnd
  end
 else
  local at=ctx.attack
  list[1]={key=1,kind=ctx.def.shape,from=at.warnStart or 0,impact=at.impact,to=at.activeEnd,shape=C.shape(ctx),radius=ctx.def.radius,point=ctx.def.point}
 end
 return list
end
local function plan(ctx)
 if ctx.hammerPlanned then return end;ctx.hammerPlanned=true
 for _,u in units(ctx) do
  -- A combo's slam winds up once the hit before it is over (u.from).
  if u.kind=='circle' then C.at(ctx,u.from,function() slamWindup(ctx,u.impact) end);C.at(ctx,u.impact,function() slamAt(ctx,u,false) end)
  elseif u.kind=='sweep' then crescent(ctx,u.from,u.to,u.key) end
 end
end

-- Charge ----------------------------------------------------------------------------------
local function chargeWindup(ctx)
 local g=groundAt(ctx,ctx.cf.Position);if not C.near(g) then return end
 local s=ctx.scale or 1;local dir=ctx.charge.dir
 C.cue('zombie_roar',g,.55,.8)
 dust(g-dir*2*s+up*.4,-dir+up*.4,8,{6,10},4*s,50) -- the back foot digs in
 dirt(g-dir*2.5*s+up*.3,-dir+up*.7,10,{8,12},30,1.1*s)
end
-- A skid streak: two dragged-heel marks behind where he stopped, and dirt thrown forward.
local function skid(ctx,pos,dir)
 local s=ctx.scale or 1;local side=dir:Cross(up)
 C.shake(pos,.6,.25);if not C.near(pos) then return end
 C.cue('sand_burst',pos,.55,.9);C.cue('hammer_thud',pos,.4,.5)
 for _,x in {-1.6*s,1.6*s} do
  local c=pos-dir*3.5*s+side*x+up*.03;local p,set=C.plate(c,'ScorchMark',4*s,DIRT,0,false)
  if p then
   p.Size=Vector3.new(2.6*s,.05,7*s);p.CFrame=CFrame.lookAt(p.Position,p.Position+dir)
   K.animate(2.4,function(t,age) set(age<.08 and 1-.6*age/.08 or .4+.6*K.smooth((t-.45)/.55)) end,function() p:Destroy() end,'bossPlate',64)
  end
 end
 dirt(pos+dir*2*s+up*.4,dir+up*.8,26,{14,22},35,1.3*s)
 dust(pos+dir*1.5*s+up*.4,dir+up*.3,10,{9,14},4.5*s,70)
end
-- From the launch to the finish slam, on the server's clock and the run's current length (the
-- presentation re-times ctx.attack and ctx.charge from BossChargeLength as he runs).
local function charge(ctx)
 if ctx.hammerCharge or not ctx.charge then return end;ctx.hammerCharge=true
 local ch,def=ctx.charge,ctx.def;local s=ctx.scale or 1;local dir=ch.dir
 local start=groundAt(ctx,ctx.cf.Position)
 local stride=ctx.timing.chargeStrideLength or def.speed*.53;local half=math.max(1,stride/2)
 local travel0=math.clamp((C.age(ctx)-ctx.attack.impact)*def.speed,0,ch.length)
 local nextStep,side,stopped,slammed=math.max(half*.5,travel0),1,false,false
 local snd,sh=C.cue('stone_rumble',start,.45,1.15,true)
 local slamFinish=(ctx.timing.clips and ctx.timing.clips[def.clips[3]] or 1.5)/(def.rate or 1)
 local maxAge=ctx.attack.impact+(def.length or 75)/def.speed+slamFinish+.5
 C.follow(ctx,maxAge,function(age)
  local at=ctx.attack;local travel=math.clamp((age-at.impact)*def.speed,0,ch.length)
  local root=ctx.npc.PrimaryPart;local floorY=root and root.Position.Y-ctx.timing.rootHeight or ctx.groundY
  local pos=Vector3.new(start.X,floorY,start.Z)+dir*travel
  if sh then sh.CFrame=CFrame.new(pos+up*2) end
  if not stopped then
   -- A footfall every half stride, alternating feet: dust kicked back and a small thump.
   while travel>=nextStep do
    local f=Vector3.new(start.X,floorY,start.Z)+dir*nextStep+dir:Cross(up)*side*1.6*s
    if C.near(f) then dust(f+up*.3,-dir+up*.6,3,{5,9},3.5*s,40) end
    C.shake(f,.3,.12);C.cue('hammer_thud',f,.3,.55);side=-side;nextStep+=half
   end
   if age>=at.activeEnd then stopped=true;C.stopSound(snd,sh,.15);skid(ctx,pos,dir) end
  end
  if stopped and not ch.finishImpact then return true end
  if ch.finishImpact and not slammed and age>=ch.finishImpact-.22 and not ctx.hammerWhoosh then ctx.hammerWhoosh=true;C.cue('hammer_whoosh',pos,.7,.62) end
  if ch.finishImpact and not slammed and age>=ch.finishImpact then
   slammed=true;local f=ch.finish;if f then slam(ctx,f.center,f.radius,true) end;return true
  end
 end,function() C.stopSound(snd,sh,.15) end)
end

-- Hooks -------------------------------------------------------------------------------------
function H.windup(ctx) if ctx.charge then chargeWindup(ctx) else plan(ctx) end end
-- The charge's impact is the launch (end of ChargeStart); a missed windup still plans the rest.
function H.impact(ctx) if ctx.charge then charge(ctx) else plan(ctx) end end
function H.active(ctx,age) if ctx.charge then charge(ctx) end end

-- Follow-up cracks: a crack decal opens on each circle and grows until it erupts (aftershock).
function H.followup(m)
 local r=m.radius or 5.5;local life=math.max(.1,m.at-workspace:GetServerTimeNow())
 for _,p in m.points do
  if C.near(p,r) then
   local plate,set=C.plate(p+up*.04,'EarthCracks',r*.7,CRACK,nil,false)
   if plate then
    K.animate(life+1.4,function(_,age)
     local k=math.min(1,age/life)
     set(age<life and .55-.45*k or .1+.9*K.smooth((age-life-.6)/.8),nil,r*(.7+1.5*(1-(1-k)^2)))
    end,function() plate:Destroy() end,'bossPlate',64)
   end
   -- Grit trickles up out of the opening crack.
   local h=C.host(p+up*.3,life+.6,up)
   C.fx(h,'DustPuff',{Rate=6,Speed={1,3},SpreadAngle=60,Lifetime={.5,.8},Size=ns({0,.6},{1,1.8}),Color=DUST,Transparency=ns({0,.4},{.6,.6},{1,1}),LightInfluence=.8,Rotation={0,360}})
   task.delay(life,function() C.retire({h},.8) end)
  end
 end
end
-- The eruption: a dirt burst out of each crack.
function H.aftershock(m)
 local s,r=m.scale or 1,m.radius or 5.5
 for i,p in m.points do
  if C.near(p,r) then
   C.emit(p+up*.4,up,'SandBurst',{emit=3,Speed={0,1},Lifetime={.5,.65},Size=ns({0,r*.9},{1,r*1.5}),Color=DIRT,Transparency=ns({0,0},{.8,.2},{1,1}),LightInfluence=.8})
   dirt(p+up*.3,up,22,{16,26},30,1.2*s);dust(p+up*.4,up,8,{12,18},r*.8,70)
   C.ring(p+up*.07,'ShockwaveRing',1,r*2.3,.32,PALE,0,true);C.star(p+up*2,PALE,r*1.3,.18)
   if i<=2 then C.cue('sand_burst',p,.6,.95);C.cue('hammer_thud',p,.4,.7) end
   C.shake(p,.6,.25)
  end
 end
end

-- Enrage --------------------------------------------------------------------------------------
-- His head, near enough for effects: the root plus most of his height (the glow mesh is skinned,
-- so its part doesn't move with the head).
local function headOffset(m) local T=m.timing or {};return ((T.height or 13.7)-(T.rootHeight or 4))*.88 end
function H.enrage(m)
 local npc=m.npc;local root=npc.PrimaryPart;if not root then return end
 local r=6*(m.scale or 1)
 -- The eyes ignite and stay red.
 local glow=C.glow(npc,'EyeGlow')
 if #glow>0 then K.animate(.3,function(t) C.setGlow(glow,RED,t) end,function() C.setGlow(glow,RED,1) end,'bossGlow',8) end
 -- Steam keeps rising off his head for the rest of the fight (on the root, so it follows him).
 local at=Instance.new('Attachment');at.Name='BossVfxSteam';at.Position=Vector3.new(0,headOffset(m),0);at.Parent=root
 C.fx(at,'SmokePuff',{Rate=1.2,EmissionDirection=Enum.NormalId.Top,Speed={2,4},SpreadAngle=25,Lifetime={1,1.4},Size=ns({0,.8},{1,2.6}),Color=STEAM,Transparency=ns({0,.5},{.4,.6},{1,1}),Acceleration=Vector3.new(0,3,0),LightInfluence=.6,Rotation={0,360},RotSpeed={-30,30}})
 -- The roar: its peak (the clip's impact when it has one, else 0.3 s in), or right now.
 local function roar()
  local p=root.Position;local head=p+up*headOffset(m);local y=C.feet(npc);local g=Vector3.new(p.X,y or p.Y-((m.timing and m.timing.rootHeight) or 4),p.Z)
  C.shake(p,1.5,.7);if not C.near(p,40) then return end
  C.cue('zombie_roar',head,.95,.55);C.cue('ground_quake',g,.55,.9)
  C.ring(g+up*.08,'ShockwaveRing',r,r*7,.8,RED,0,true);C.ring(g+up*.11,'ShockwaveRing',r*.5,r*4.5,.55,WHITE,.2,true)
  C.star(head,RED,r*2,.26);C.light(head,RED,40,3.5,.8)
  C.emit(head,up,'SmokePuff',{emit=12,Speed={6,11},SpreadAngle=70,Drag=2.5,Lifetime={.9,1.3},Size=ns({0,1.5},{1,4.5}),Color=STEAM,Transparency=ns({0,.25},{.5,.45},{1,1}),Acceleration=Vector3.new(0,4,0),LightInfluence=.6,Rotation={0,360},RotSpeed={-40,40}})
  for _,x in {-1,1} do -- off both shoulders
   local sp=p+up*headOffset(m)*.8+root.CFrame.RightVector*x*3*(m.scale or 1)
   C.emit(sp,(up+root.CFrame.RightVector*x*.6).Unit,'SmokePuff',{emit=5,Speed={5,9},SpreadAngle=30,Drag=2.5,Lifetime={.8,1.2},Size=ns({0,1.2},{1,3.5}),Color=STEAM,Transparency=ns({0,.3},{.5,.5},{1,1}),LightInfluence=.6,Rotation={0,360}})
  end
  C.dustRing(g,r,14,DUST,{16,24},4*(m.scale or 1))
 end
 local ctx=m.roar
 if ctx then local peak=ctx.attack and ctx.attack.impact or 0;C.at(ctx,peak>0 and peak or .3,roar) else roar() end
end

-- Intro: the landing ---------------------------------------------------------------------------
function H.intro(m)
 local root=m.npc.PrimaryPart;local g=m.ground
 if not g then if not root then return end;local y=C.feet(m.npc);g=Vector3.new(root.Position.X,y or root.Position.Y,root.Position.Z) end
 local s=m.scale or 1;local r=8*s
 C.shake(g,1.8,.7);if not C.near(g,40) then return end
 C.ring(g+up*.06,'ShockwaveRing',r*.5,r*5,.6,PALE,0,true);C.ring(g+up*.09,'ShockwaveRing',r*.3,r*3.2,.9,DUST,.25,true)
 C.star(g+up*3,PALE,r*1.6,.24)
 cracks(g+up*.035,r*2.6,3.2)
 C.dustRing(g,r*.8,16,DUST,{20,28},r*.55)
 dust(g+up*.5,up,18,{10,18},r*.9,80)
 dirt(g+up*.3,up,30,{16,26},55,1.4*s)
end
return H
