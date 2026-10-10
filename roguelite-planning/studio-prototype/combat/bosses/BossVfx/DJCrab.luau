-- The DJ Crab's effects (round 10, Beach Cove CRAB RAVE). Client-only; nothing here changes hits.
-- BeatCommand: teal sparkles trail the conducting claw; at the snap a beat ring pops round it and a
--   teal pulse rolls off the speakers (the rush lanes themselves are Round10World's).
-- ClawSlam: sand trickles off the raised claws; the double slam lands in a coral-and-white burst, then
--   the bass ring (MapBossShapes ring data) rolls out as flat Neon segments with a sand wall kicked up
--   along its front, the gaps left dark so the way through reads.
-- Bombard: the speakers boom on the second pump; a rock whistles down onto every warned circle,
--   landing at impact + eruptDelay with a sand burst, chips and a thump.
-- Intro: at the claw snap (BossIntroLand) the speakers drop the beat: a teal and coral double ring,
--   confetti sparkles off the speakers, sand thrown round and a shake.
local Players=game:GetService('Players')
local C=require(script.Parent:WaitForChild('Common'))
local K=C.K
local ns=C.ns
local Shapes=C.Shapes
local up=Vector3.yAxis
local TEAL,CORAL,IVORY,SAND=Color3.fromRGB(70,230,215),Color3.fromRGB(255,112,86),Color3.fromRGB(255,244,222),Color3.fromRGB(228,202,152)
local ROCKS={'SandstoneRubble_A','SandstoneRubble_B'}
local STONE={Color3.fromRGB(150,128,104),Enum.Material.Slate}
local SHELL={CORAL,Enum.Material.SmoothPlastic}
local D={}

local function sandSpray(pos,look,count,speed,spread,size)
 C.emit(pos,look,'SandSpray',{emit=count,Speed=speed,SpreadAngle=spread,Lifetime={.45,.7},Size=ns({0,(size or 1)*1.1},{1,(size or 1)*2.6}),Color=SAND,Transparency=ns({0,0},{.7,.2},{1,1}),Acceleration=Vector3.new(0,-45,0),Drag=.8,Rotation={-40,40},LightInfluence=.8})
end
local function dust(pos,count,size)
 C.emit(pos,up,'DustPuff',{emit=count,Speed={9,14},SpreadAngle=85,Drag=4,Lifetime={.7,1},Size=ns({0,size*.5},{1,size}),Color=SAND,Transparency=ns({0,.25},{.6,.4},{1,1}),LightInfluence=.8,Rotation={0,360},RotSpeed={-40,40}})
end
local function confetti(pos,count,speed)
 for i,col in {TEAL,CORAL,IVORY} do
  C.emit(pos,up,'SnowSparkle',{emit=math.ceil(count/3),Speed=speed,SpreadAngle=55,Lifetime={.8,1.2},Size=ns({0,.55},{.7,.4},{1,0}),Color=col,Acceleration=Vector3.new(0,-22,0),Drag=1.2,LightEmission=.8,Rotation={0,360},RotSpeed={-120,120}})
 end
end
-- A camera-facing ring snapping open round a point (the beat pulse).
local function pulse(pos,color,size,seconds)
 local host,g,img=C.sprite(pos,'ShockwaveRing',1,color,0);if not host then return end
 K.animate(seconds or .35,function(t) local s=1+size*(1-(1-t)^3);g.Size=UDim2.fromScale(s,s);img.ImageTransparency=K.smooth((t-.2)/.8) end,function() host:Destroy() end,'bossStar',24)
end
local function groundUnder(pos,ctx)
 local skip={C.folder(),ctx.npc};for _,pl in Players:GetPlayers() do if pl.Character then table.insert(skip,pl.Character) end end
 return K.groundBelow(pos,skip,ctx.groundY)
end

-- BeatCommand ----------------------------------------------------------------------------------
local function conduct(ctx)
 if ctx.djConduct then return end;ctx.djConduct=true
 local at=ctx.attack;local p0=ctx.points('CommandClaw',C.age(ctx));if not C.near(p0) then return end
 C.cue('crab_windup',p0,.6,1.2)
 local host=C.part('Host',Vector3.one*.6,CFrame.new(p0),K.White,1)
 C.fx(host,'SnowSparkle',{Rate=34,Speed={.5,1.5},SpreadAngle=180,Lifetime={.35,.5},Size=ns({0,.45},{1,0}),Color=TEAL,LightEmission=1,Rotation={0,360}})
 C.follow(ctx,at.impact,function(age) host.CFrame=CFrame.new(ctx.points('CommandClaw',age)) end,function() C.retire({host},.6) end)
end
local function snap(ctx)
 local at=ctx.attack;local p=ctx.points('CommandClaw',at.impact);if not C.near(p) then return end
 C.cue('crab_slam',p,.45,1.6)
 C.star(p,IVORY,5,.16);pulse(p,TEAL,9,.32);C.light(p,TEAL,18,2.5,.3)
 local s=ctx.points('SpeakerTop',at.impact);pulse(s,TEAL,14,.45);pulse(s,CORAL,9,.38)
end

-- ClawSlam -------------------------------------------------------------------------------------
local function slamWindup(ctx)
 if ctx.djRaise then return end;ctx.djRaise=true
 local at=ctx.attack;local hosts={}
 for i,name in {'LeftClaw','RightClaw'} do
  local p=ctx.points(name,C.age(ctx))
  if C.near(p) then
   local h=C.part('Host',Vector3.new(2,.4,2),C.aim(p,-up),K.White,1)
   C.fx(h,'SandSpray',{Rate=14,Speed={1,3},SpreadAngle=25,Lifetime={.5,.7},Size=ns({0,.8},{1,1.6}),Color=SAND,Transparency=ns({0,.15},{.7,.35},{1,1}),Acceleration=Vector3.new(0,-26,0),Rotation={0,360},LightInfluence=.8})
   hosts[i]={host=h,name=name}
  end
 end
 if not next(hosts) then return end
 C.cue('crab_windup',ctx.points('SlamCenter',C.age(ctx)),.8,.9)
 local glint=false
 C.follow(ctx,at.impact,function(age)
  for _,h in hosts do h.host.CFrame=C.aim(ctx.points(h.name,age),-up) end
  if not glint and age>=at.impact-.28 then glint=true;for _,h in hosts do C.star(ctx.points(h.name,age)+up,IVORY,4,.16) end end
 end,function() local list={};for _,h in hosts do table.insert(list,h.host) end;C.retire(list,.8) end)
end
-- The bass ring: one Neon segment per 7.5° on the front, hidden in the gaps, plus a sand wall
-- thrown up along the front. Runs from impact until the front reaches the outer radius.
local function bassRing(ctx)
 if ctx.djRing then return end;ctx.djRing=true
 local at=ctx.attack;local ring=Shapes.decodeRing(ctx.data and ctx.data.ring);if not ring then return end
 local c=ring.center;if not C.near(c,ring.outer) then return end
 local n=48;local segs={};local width=ring.width or 3
 for i=1,n do
  local a=(i-.5)/n*math.pi*2;local dir=Vector3.new(math.sin(a),0,-math.cos(a))
  if not Shapes.inGap(ring,c+dir*10) then
   local body=C.part('BassRing',Vector3.new(.1,.08,.1),CFrame.new(c),TEAL,1);body.Material=Enum.Material.Neon
   local rim=C.part('BassRim',Vector3.new(.1,.1,.1),CFrame.new(c),IVORY,1);rim.Material=Enum.Material.Neon
   table.insert(segs,{body=body,rim=rim,dir=dir})
  end
 end
 local stop=Shapes.ringEnd(ring);local nextKick=0
 local snd,sh=C.cue('crab_scuttle',c,.5,.8,true)
 K.animate(stop+.6,function()
  local age=C.age(ctx);local t=age-at.impact
  if t<0 then return end
  local r=Shapes.ringRadius(ring,math.min(t,stop));local fade=K.smooth((t-stop+.3)/.5)
  local chord=2*r*math.sin(math.pi/n)*1.06
  for _,s in segs do
   local mid=c+s.dir*(r-width*.25)+up*.06
   s.body.Size=Vector3.new(chord,.08,width*.5);s.body.CFrame=CFrame.lookAt(mid,mid+s.dir);s.body.Transparency=.35+.65*fade
   local edge=c+s.dir*(r+.05)+up*.08
   s.rim.Size=Vector3.new(chord,.1,.35);s.rim.CFrame=CFrame.lookAt(edge,edge+s.dir);s.rim.Transparency=.1+.9*fade
  end
  if sh then sh.CFrame=CFrame.new(c+up*2) end
  -- The sand wall: a few bursts along the front every 0.08 s while it travels.
  if t<stop and age>=nextKick then
   nextKick=age+.08
   for _=1,3 do
    local s=segs[math.random(#segs)];if s then sandSpray(c+s.dir*r+up*.3,s.dir*.35+up,4,{8,14},18,.9) end
   end
  end
  if t>stop+.5 then return true end
 end,function() for _,s in segs do s.body:Destroy();s.rim:Destroy() end;C.stopSound(snd,sh,.2) end,'bossWave',8)
end
local function slamImpact(ctx)
 local at=ctx.attack;local g=C.ground(ctx,ctx.points('SlamCenter',at.impact));local s=ctx.scale
 C.shake(g,1.1,.45);if not C.near(g,10) then return end
 C.cue('crab_slam',g,.9,.85)
 C.star(g+up*2,IVORY,9*s,.2);C.light(g+up*3,TEAL,26,3,.35);K.pop(C.folder(),g+up,CORAL,2,8*s,.25,.5)
 C.ring(g+up*.07,'ShockwaveRing',1,12*s,.35,IVORY,0,true);C.ring(g+up*.09,'ShockwaveRing',2,9*s,.3,TEAL,.1,true)
 sandSpray(g+up*.3,up,36,{12,22},60,1.2*s);dust(g+up*.4,10,4*s);C.dustRing(g,3.5*s,10,SAND,{14,20},3*s)
 C.chunks(g+up*1.2,ctx.groundY,{'ShellChip_A','ShellChip_B','ShellChip_C'},{count=3,speed={8,13},up={12,18},scale={1.6*s,2.2*s},life=1.2,fallback=SHELL})
 bassRing(ctx)
end

-- Bombard --------------------------------------------------------------------------------------
-- A rock: falls from 34 studs up and a little toward the boss along a short arc, spinning, its
-- shadow plate darkening under it; lands at `land` (server time) on the circle centre.
local function rock(ctx,p,land,i)
 local from=ctx.cf.Position;local back=C.flat(from-p);back=back.Magnitude>1 and back.Unit or Vector3.zAxis
 local start=p+back*10+up*34;local fall=.7
 -- k5: the circle against its old 5 studs (2026-10-10: radius 7.5), so the rock and its burst fill it.
 local r=(ctx.def.radius or 5);local k5=r/5
 local m=C.mesh(ROCKS[(i-1)%#ROCKS+1],CFrame.new(start),2*k5)
 if not m then m=C.part('Rock',Vector3.new(2.4,2,2.2)*k5,CFrame.new(start),STONE[1],0);m.Material=STONE[2] end
 K.trail(m,1.1,.25,IVORY,SAND,.35)
 local shadow,set=C.plate(p+up*.05,'ScorchMark',r*.9,Color3.fromRGB(40,34,30),0,false)
 local spin=CFrame.Angles(math.random()*6,math.random()*6,math.random()*6);local axis=Vector3.new(math.random()-.5,math.random()-.5,math.random()-.5).Unit
 local landed=false
 K.animate(land-workspace:GetServerTimeNow()+.6,function()
  local now=workspace:GetServerTimeNow();local k=1-(land-now)/fall
  if shadow then set(1-.6*math.clamp((k+.3)/1.3,0,1),nil,r*(.5+.4*math.clamp(k,0,1))) end
  if k<0 then m.Transparency=1;return end
  m.Transparency=0
  if k>=1 then
   if not landed then
    landed=true;m:Destroy();if shadow then shadow:Destroy();shadow=nil end
    if C.near(p,r) then
     C.cue('crab_slam',p,i<=2 and .7 or .35,1.1);C.shake(p,.6,.25)
     C.star(p+up*1.5,IVORY,r*1.2,.18);C.ring(p+up*.07,'ShockwaveRing',1,r*2.2,.32,SAND,0,true)
     C.emit(p+up*.3,up,'SandBurst',{emit=24,Speed={16*k5,26*k5},SpreadAngle=30,Lifetime={.6,.9},Size=ns({0,1.4*k5},{1,3.2*k5}),Color=SAND,Transparency=ns({0,0},{.7,.2},{1,1}),Acceleration=Vector3.new(0,-50,0),Rotation={-20,20},LightInfluence=.8})
     dust(p+up*.4,8,3.5*k5);C.dustRing(p,r*.8,10,SAND,{14,20},2.5*k5)
     C.chunks(p+up*1,p.Y,ROCKS,{count=4,speed={8,14},up={10,16},scale={.6*k5,.9*k5},life=1.2,fallback=STONE})
    end
   end
   return true
  end
  local e=k*k -- accelerating fall
  local pos=start:Lerp(p+up*1.2,e)+up*math.sin(k*math.pi)*4
  m.CFrame=CFrame.new(pos)*spin*CFrame.fromAxisAngle(axis,k*9)
 end,function() if m.Parent then m:Destroy() end;if shadow then shadow:Destroy() end end,'bossObelisk',16)
end
local function bombard(ctx)
 if ctx.djBombard then return end;ctx.djBombard=true
 local at,def=ctx.attack,ctx.def;local s=ctx.points('SpeakerTop',at.impact)
 if C.near(s) then
  C.cue('crab_slam',s,.6,.7);pulse(s,TEAL,16,.45);pulse(s,CORAL,10,.4);C.light(s,TEAL,24,2.6,.35)
  confetti(s,18,{10,16})
 end
 local land=ctx.start+at.impact+(def.eruptDelay or 1.15)
 -- The circles' points replicate with the attack data; wait for them briefly if they lag.
 K.animate(1.2,function()
  local pts=ctx.data and ctx.data.points
  if type(pts)=='table' and #pts>0 then
   if C.live(ctx) then for i,v in pts do rock(ctx,Vector3.new(v[1],groundUnder(Vector3.new(v[1],v[2]+4,v[3]),ctx) or v[2],v[3]),land,i) end end
   return true
  end
 end,nil,'bossAt',16)
end
local function pump(ctx)
 if ctx.djPump then return end;ctx.djPump=true
 local at=ctx.attack;local first=(at.pumps and at.pumps[1]) or .25
 C.at(ctx,first,function() local s=ctx.points('SpeakerTop',first);if C.near(s) then pulse(s,TEAL,9,.3);C.cue('crab_windup',s,.5,1.3) end end)
end

function D.windup(ctx)
 local k=ctx.kind
 if k=='BeatCommand' then conduct(ctx) elseif k=='ClawSlam' then slamWindup(ctx) elseif k=='Bombard' then pump(ctx) end
end
function D.impact(ctx)
 local k=ctx.kind
 if k=='BeatCommand' then snap(ctx) elseif k=='ClawSlam' then slamImpact(ctx) elseif k=='Bombard' then bombard(ctx) end
end
function D.active(ctx,age) end
-- The beat drops: the intro clip's claw snap.
function D.intro(m)
 local root=m.npc.PrimaryPart;if not root then return end
 local g=m.ground or Vector3.new(root.Position.X,C.feet(m.npc) or root.Position.Y,root.Position.Z);local s=m.scale or 1
 C.shake(g,1.2,.5);if not C.near(g,40) then return end
 C.cue('crab_slam',g,.85,.8)
 C.ring(g+up*.06,'ShockwaveRing',2,34*s,.6,TEAL,0,true);C.ring(g+up*.09,'ShockwaveRing',1,22*s,.5,CORAL,.15,true)
 C.light(g+up*4,TEAL,40,3,.7);C.star(g+up*4*s,IVORY,12*s,.22)
 confetti(root.Position+up*3*s,36,{14,22})
 C.dustRing(g,5*s,14,SAND,{16,24},3.5*s);sandSpray(g+up*.3,up,30,{12,20},70,1.2)
end
return D
