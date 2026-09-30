-- The Pharaoh's effects (plan F Task 12). Client-only; nothing here changes hits.
-- CursedBolts: a cyan-gold CurseOrb charges in the crook with orbiting glyphs, inward sparkles, a
-- light ramp and flaring eyes; a gold muzzle flash; then cyan cores in gold halos trailing glyphs,
-- bursting into sand where they stop.
-- TombEruption: gold dust spirals up the raised staff; rotating hieroglyph circles open under each
-- target; the staff strike sends a gold ring; at impact + eruptDelay an obelisk bursts up through
-- every circle on a sand geyser, holds, then sinks back.
local Players=game:GetService('Players')
local C=require(script.Parent:WaitForChild('Common'))
local K=C.K
local ns=C.ns
local up=Vector3.yAxis
local GOLD,BRIGHT,CYAN,SAND,WHITE=Color3.fromRGB(255,206,96),Color3.fromRGB(255,244,196),Color3.fromRGB(110,236,255),Color3.fromRGB(232,206,152),Color3.new(1,1,1)
local OBELISKS={'Obelisk_A','Obelisk_B','Obelisk_C'}
local BURIED={Obelisk_A=.073,Obelisk_B=.072,Obelisk_C=.074} -- share of height authored below ground (kit manifest)
local RUBBLE={'SandstoneRubble_A','SandstoneRubble_B'}
local STONE={SAND,Enum.Material.Sandstone}
local SPHERE,SURFACE=Enum.ParticleEmitterShape.Sphere,Enum.ParticleEmitterShapeStyle.Surface
local P={}

local function dust(pos,count)
 C.emit(pos,up,'DustPuff',{emit=count,Speed={9,14},SpreadAngle=88,Drag=4,Lifetime={.8,1.1},Size=ns({0,1.4},{1,3.4}),Color=SAND,Transparency=ns({0,.25},{.6,.4},{1,1}),LightInfluence=.8,Rotation={0,360},RotSpeed={-40,40}})
end
local function groundUnder(pos,ctx)
 local skip={C.folder(),ctx.npc};for _,pl in Players:GetPlayers() do if pl.Character then table.insert(skip,pl.Character) end end
 return K.groundBelow(pos,skip,ctx.groundY)
end

-- CursedBolts -----------------------------------------------------------------------------
local function charge(ctx)
 local at,def=ctx.attack,ctx.def;local o=ctx.points(def.point,C.age(ctx));if not C.near(o) then return end
 local _=C.cue('pharaoh_charge',o,.75) or C.cue('pharaoh_windup',o,.75)
 local core,g=C.sprite(o,'CurseOrb',.2,WHITE,0)
 core=core or C.part('Host',Vector3.one*.1,CFrame.new(o),K.White,1)
 local light=Instance.new('PointLight');light.Color=CYAN;light.Range=0;light.Brightness=0;light.Shadows=false;light.Parent=core
 -- Glyphs locked to a spinning sphere orbit the crook; cyan sparkles converge into it.
 local spin=C.part('Host',Vector3.one*4.5,CFrame.new(o),K.White,1)
 C.fx(spin,'Hieroglyphs',{Rate=25,LockedToPart=true,Shape=SPHERE,ShapeStyle=SURFACE,Speed={.2,.5},Lifetime={.6,.9},Size=ns({0,0},{.25,.75},{1,0}),Color=GOLD,Transparency=ns({0,.05},{1,.5}),LightEmission=.7,Rotation={-20,20},RotSpeed={-60,60}})
 C.fx(spin,'SnowSparkle',{Rate=26,Shape=SPHERE,ShapeStyle=SURFACE,ShapeInOut=Enum.ParticleEmitterShapeInOut.Inward,Speed={3,4.5},Lifetime={.4,.55},Size=ns({0,.5},{1,0}),Color=CYAN,LightEmission=1})
 local eyes=C.glow(ctx.npc,'EyeGlow');local begin=at.chargeStart or at.warnStart
 C.follow(ctx,at.impact,function(age)
  local p=ctx.points(def.point,age);core.CFrame=CFrame.new(p);spin.CFrame=CFrame.new(p)*CFrame.Angles(.35,age*5,0)
  local e=1-(1-math.clamp((age-begin)/.6,0,1))^2 -- the orb grows over 0.6 s from chargeStart
  if g then local s=.5+2.9*e+math.sin(age*32)*.14*e;g.Size=UDim2.fromScale(s,s) end
  light.Range=4+10*e;light.Brightness=.3+2.4*e;C.setGlow(eyes,Color3.fromRGB(225,255,255),e)
 end,function() C.setGlow(eyes,nil,0);core:Destroy();C.retire({spin},.9) end)
end
local function boltImpact(ctx)
 local at,def=ctx.attack,ctx.def;local o=ctx.points(def.point,at.impact);if not C.near(o) then return end
 C.cue('pharaoh_bolt',o,.8)
 C.star(o,GOLD,6.5,.2);K.pop(C.folder(),o,CYAN,1,5,.3,.35);C.light(o,CYAN,18,3,.3)
 C.emit(o,up,'Hieroglyphs',{emit=10,Speed={6,10},SpreadAngle=180,Drag=4,Lifetime={.5,.8},Size=ns({0,.9},{1,0}),Color=GOLD,LightEmission=.7,RotSpeed={-90,90}})
end
-- A bolt: neon cyan core in a pulsing gold halo under the CurseOrb sprite. Its trail, glyph wake and
-- light ride a tail host that lingers so they fade out rather than vanish.
function P.projectile(ctx,i)
 local k=(ctx.def.radius or 1.2)/1.2 -- sized for the authored 1.2-stud bolt
 local core=K.ball(C.folder(),'BossVfxBolt',1*k,CYAN,0,Enum.Material.Neon)
 local rim=K.ball(core,'BossVfxBoltRim',1.7*k,GOLD,.6,Enum.Material.Neon) -- a child, so it goes with the core
 local _,_,img=C.sprite(core,'CurseOrb',3.2*k,WHITE,0)
 local tail=C.tail(core,(ctx.def.life or 2.2)+2,.9)
 K.trail(tail,1.1,.35,CYAN,GOLD,.15)
 C.fx(tail,'Hieroglyphs',{Rate=18,Speed={.3,.8},SpreadAngle=180,Lifetime=.8,Size=ns({0,.75},{1,0}),Color=GOLD,Acceleration=Vector3.new(0,3,0),Drag=1,LightEmission=.6,RotSpeed={-45,45}})
 local light=Instance.new('PointLight');light.Color=CYAN;light.Range=10;light.Brightness=1.8;light.Shadows=false;light.Parent=tail
 local t=math.random()+i
 return core,function(dt)
  t+=dt;rim.CFrame=core.CFrame;rim.Size=Vector3.one*1.7*k*(1+math.sin(t*22)*.08)
  if img then img.Rotation=(t*240)%360 end
 end,function(pos)
  if not C.near(pos) then return end
  K.pop(C.folder(),pos,CYAN,1,4.5,.28,.3);C.star(pos,CYAN,4.5,.16)
  C.emit(pos,up,'Hieroglyphs',{emit=5,Speed={4,7},SpreadAngle=180,Drag=4,Lifetime={.5,.7},Size=ns({0,.8},{1,0}),Color=GOLD,LightEmission=.7})
  local gy=groundUnder(pos,ctx)
  if gy and pos.Y-gy<6 then
   C.emit(Vector3.new(pos.X,gy+.3,pos.Z),up,'SandBurst',{emit=16,Speed={6,12},SpreadAngle=40,Lifetime={.55,.8},Size=ns({0,1.2},{1,3}),Color=SAND,Transparency=ns({0,0},{.7,.2},{1,1}),Acceleration=Vector3.new(0,-30,0),Rotation={-20,20},LightInfluence=.8})
  end
  local now=os.clock();if now-(ctx.boltPop or 0)>.12 then ctx.boltPop=now;C.cue('sand_burst',pos,.3,1.3) end
 end
end

-- TombEruption ----------------------------------------------------------------------------
local function spiral(ctx)
 local at=ctx.attack;local s=ctx.points('StaffImpact',C.age(ctx));if not C.near(s) then return end
 C.cue('pharaoh_windup',s,.75)
 -- Gold dust rises from the staff foot on a spinning host with locked particles: a spiral.
 local host=C.part('Host',Vector3.new(2.4,.2,2.4),CFrame.new(s),K.White,1)
 C.fx(host,'SnowSparkle',{Rate=40,LockedToPart=true,EmissionDirection=Enum.NormalId.Top,Speed={6,9},SpreadAngle=6,Lifetime={.7,.9},Size=ns({0,0},{.2,.5},{1,0}),Color=GOLD,LightEmission=.9,Rotation={0,360}})
 C.fx(host,'Hieroglyphs',{Rate=6,LockedToPart=true,EmissionDirection=Enum.NormalId.Top,Speed={4,6},SpreadAngle=6,Lifetime={.8,1},Size=ns({0,0},{.2,.6},{1,0}),Color=GOLD,LightEmission=.7})
 C.follow(ctx,at.impact,function(age) host.CFrame=CFrame.new(ctx.points('StaffImpact',age))*CFrame.Angles(0,age*7,0) end,function() C.retire({host},1) end)
end
local function staffImpact(ctx)
 local at=ctx.attack;local g=C.ground(ctx,ctx.points('StaffImpact',at.impact))
 C.shake(g,.45,.3);if not C.near(g) then return end
 C.cue('stone_rumble',g,.85)
 local s=ctx.scale
 C.ring(g+up*.06,'ShockwaveRing',1,9*s,.4,GOLD,0,true);C.ring(g+up*.09,'HieroglyphCircle',2,7*s,.6,GOLD,.2,1.6);C.star(g+up*1.2,BRIGHT,6*s,.18);dust(g+up*.3,10)
end
-- An obelisk rising out of the sand at full size: up in 0.18 s overshooting 10%, settle, hold
-- 0.9 s, sink in 0.4 s. Its authored buried foot keeps the base hidden in the floor.
local function obelisk(p,k)
 local name=OBELISKS[math.random(#OBELISKS)];local o=C.mesh(name,CFrame.new(p),(.9+math.random()*.2)*(k or 1))
 if not o then o=C.part('Obelisk',Vector3.new(2.2,6,2.2),CFrame.new(p),SAND,0);o.Material=Enum.Material.Sandstone end
 local size,below=o.Size,BURIED[name] or .07
 local frame=CFrame.new(p)*CFrame.Angles(0,math.random()*6.28,0)*CFrame.Angles(math.rad(math.random(-6,6)),0,math.rad(math.random(-6,6)))
 local function rise(r) o.CFrame=frame*CFrame.new(0,size.Y*(.5-below)-(1-r)*size.Y,0) end
 rise(0)
 K.animate(1.5,function(_,age)
  rise(age<.18 and 1.1*(1-(1-age/.18)^3) or age<.3 and 1.1-.1*K.smooth((age-.18)/.12) or age<1.08 and 1 or 1-K.smooth((age-1.08)/.4))
 end,function() o:Destroy() end,'bossObelisk',16)
end
-- k: the circle's radius over the authored 4.5 (the kit's obelisks and bursts were sized for it).
local function eruptAt(p,i,k)
 if not C.near(p) then return end
 obelisk(p,k)
 C.ring(p+up*.1,'ShockwaveRing',2,9*k,.5,BRIGHT,.3,true)
 C.emit(p+up*.3,up,'SandBurst',{emit=40,Speed={30,45},SpreadAngle=12,Lifetime={.9,1.2},Size=ns({0,2.2},{.5,4},{1,5.5}),Color=SAND,Transparency=ns({0,0},{.7,.2},{1,1}),Acceleration=Vector3.new(0,-55,0),Drag=.6,Rotation={-15,15},RotSpeed={-40,40},LightInfluence=.8})
 C.emit(p+up*5.5,up,'SandBurst',{emit=1,Speed=0,Lifetime=.9,Size=ns({0,10},{1,12}),Color=SAND,Transparency=ns({0,0},{.8,.1},{1,1}),LightInfluence=.8}) -- the bottom-anchored geyser plume
 dust(p+up*.4,10)
 C.chunks(p+up*1.5,p.Y,RUBBLE,{count=5,speed={8,14},up={16,24},scale={.7,1.05},life=1.4,fallback=STONE})
 C.ring(p+up*.08,'ShockwaveRing',1,10,.3,GOLD,.1,true);C.star(p+up*3,BRIGHT,8,.2);C.light(p+up*3,Color3.fromRGB(255,210,130),16,2.4,.35)
 C.cue('sand_burst',p,i<=2 and .8 or .4);C.shake(p,.6,.3)
end
-- One controller per attack: circles open as soon as the server's target snapshot replicates
-- (MapBossAttackData.points), turn at 20°/s, pulse in the last 0.3 s, then flash away as the
-- obelisks erupt. If the boss dies first the circles fade and nothing erupts, like the server.
local function tomb(ctx)
 if ctx.tomb then return end;ctx.tomb=true
 local at,def=ctx.attack,ctx.def;local erupt=at.impact+(def.eruptDelay or .9);local size=(def.radius or 4.5)*2
 local circles,built,fired,deadAt={},false,false,nil
 local function build(points)
  for _,v in points do
   local p=Vector3.new(v[1],v[2],v[3])
   if C.near(p) then
    local plate,set=C.plate(p+up*.14,'HieroglyphCircle',size*.7,GOLD,0,1.8)
    local host=C.part('Host',Vector3.new(size*.8,.2,size*.8),CFrame.new(p+up*.3),K.White,1)
    local glyphs={Rate=7,EmissionDirection=Enum.NormalId.Top,Speed={1.5,3},SpreadAngle=10,Lifetime={1,1.4},Size=ns({0,0},{.2,.9},{1,0}),Color=GOLD,Transparency=ns({0,.1},{1,.5}),LightEmission=.7,RotSpeed={-30,30}}
    C.fx(host,'Hieroglyphs',glyphs)
    local rumble=C.fx(host,'DustPuff',{Rate=0,Enabled=true,EmissionDirection=Enum.NormalId.Top,Speed={2,5},SpreadAngle=30,Lifetime={.5,.7},Size=ns({0,1},{1,2.2}),Color=SAND,Transparency=ns({0,.35},{1,1}),LightInfluence=.8,Rotation={0,360}})
    table.insert(circles,{p=p,plate=plate,set=set,host=host,rumble=rumble,born=C.age(ctx),rot=math.random(0,359)})
   end
  end
 end
 K.animate(math.max(.5,erupt-C.age(ctx))+1,function()
  local age=C.age(ctx)
  if not deadAt and not fired and not C.live(ctx) then deadAt=age end
  if not built and not deadAt and type(ctx.data.points)=='table' then built=true;build(ctx.data.points) end
  if not fired and not deadAt and age>=erupt then fired=true;for i,c in circles do eruptAt(c.p,i,(def.radius or 4.5)/4.5) end end
  local ending=(fired and age-erupt) or (deadAt and age-deadAt) or nil;local left=erupt-age
  for _,c in circles do
   if c.set then
    local life=age-c.born;local s=size*(.7+.3*(1-(1-math.min(1,life/.3))^3));local a=1-.95*math.min(1,life/.25);local col,bright=GOLD,1.8
    if left<.3 and not ending then local w=.5+.5*math.sin(age*42);s*=1+.05*w;col=GOLD:Lerp(BRIGHT,w);bright=1.8+1.2*w end -- the edge pulses
    if ending then a=math.max(a,math.min(1,ending/.3));col=BRIGHT;bright=2.6 end -- flash, then gone
    c.set(a,col,s,c.rot+life*20,bright)
   end
   if c.rumble then c.rumble.Rate=(left<.3 and not ending) and 30 or 0 end
  end
  if ending and ending>.35 then return true end
 end,function()
  for _,c in circles do if c.plate then c.plate:Destroy() end;C.retire({c.host},1.2) end
 end,'bossWave',8)
end

function P.windup(ctx)
 if ctx.kind=='CursedBolts' then charge(ctx) elseif ctx.kind=='TombEruption' then spiral(ctx);tomb(ctx) end
end
function P.impact(ctx)
 if ctx.kind=='CursedBolts' then boltImpact(ctx) elseif ctx.kind=='TombEruption' then staffImpact(ctx);tomb(ctx) end
end
-- Bolts fly on the presentation's projectile path; the eruption runs on the tomb controller.
function P.active(ctx,age) end
return P
