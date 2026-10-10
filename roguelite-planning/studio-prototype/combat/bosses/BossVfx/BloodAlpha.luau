-- The Blood Moon Alpha's effects (round 10, Frozen Pass BLOOD MOON HUNT). Client-only; nothing here
-- changes hits. The howl's ground ring and the empowered wolves are Round10World's (Round10FX 'Howl').
-- Howl: breath fogs out of the mouth as it rears; at the peak red rings roll off the mouth on a
--   beat through the hold, and snow shakes off the mane.
-- Charge: snow kicked back as it coils; while it runs, snow spray at every footfall behind the
--   replicated body; a skid where it stops, then the claw rake.
-- ClawRake (alone or the charge's finish): red-and-ivory claw crescents through the front at claw
--   height and a snow burst on the ground.
-- Intro (the rim howl, BossIntroLand): the howl rings, a red flash and snow off the rim.
local C=require(script.Parent:WaitForChild('Common'))
local K=C.K
local ns=C.ns
local up=Vector3.yAxis
local RED,DEEP,IVORY,SNOW,BREATH=Color3.fromRGB(255,74,64),Color3.fromRGB(170,24,30),Color3.fromRGB(255,240,222),Color3.fromRGB(236,244,255),Color3.fromRGB(230,236,246)
local A={}

local function snow(pos,look,count,speed,spread,size)
 C.emit(pos,look,'SnowSparkle',{emit=math.ceil(count/2),Speed=speed,SpreadAngle=spread,Lifetime={.5,.8},Size=ns({0,.35},{1,0}),Color=SNOW,Acceleration=Vector3.new(0,-30,0),Drag=1,LightEmission=.4})
 C.emit(pos,look,'DustPuff',{emit=count,Speed=speed,SpreadAngle=spread,Drag=3,Lifetime={.6,.9},Size=ns({0,(size or 2)*.5},{1,size or 2}),Color=SNOW,Transparency=ns({0,.2},{.6,.4},{1,1}),LightInfluence=.9,Rotation={0,360},RotSpeed={-40,40}})
end
local function ringPulse(pos,color,size,seconds)
 local host,g,img=C.sprite(pos,'ShockwaveRing',1,color,0);if not host then return end
 K.animate(seconds or .45,function(t) local s=1+size*(1-(1-t)^3);g.Size=UDim2.fromScale(s,s);img.ImageTransparency=K.smooth((t-.15)/.85) end,function() host:Destroy() end,'bossStar',24)
end
local function howlCue(pos,volume) return C.cue('wolf_howl',pos,volume) or C.cue('zombie_roar',pos,volume,1.3) end

-- Howl -----------------------------------------------------------------------------------------
local function breath(ctx)
 if ctx.alphaBreath then return end;ctx.alphaBreath=true
 local at=ctx.attack;local m=ctx.points('Mouth',C.age(ctx));if not C.near(m) then return end
 local host=C.part('Host',Vector3.one*.6,C.aim(m,ctx.dirAt('Mouth',C.age(ctx))),K.White,1)
 C.fx(host,'FrostMist',{Rate=8,Speed={2,4},SpreadAngle=20,Lifetime={.7,1},Size=ns({0,.6},{1,2.4}),Color=BREATH,Transparency=ns({0,.45},{.5,.6},{1,1}),Drag=1.5,LightInfluence=.8,Rotation={0,360},RotSpeed={-30,30}})
 C.follow(ctx,at.activeEnd or at.impact+.8,function(age) local p=ctx.points('Mouth',age);host.CFrame=C.aim(p,ctx.dirAt('Mouth',age)) end,function() C.retire({host},1) end)
end
local function howlPeak(ctx)
 if ctx.alphaHowl then return end;ctx.alphaHowl=true
 local at=ctx.attack;local m=ctx.points('Mouth',at.impact);if not C.near(m,30) then return end
 howlCue(m,.95);C.light(m,RED,30,3,.9);C.star(m,IVORY,6,.2)
 local root=ctx.npc.PrimaryPart;if root then snow(root.Position+up*2,up,10,{6,10},70,2.5) end
 -- A ring off the mouth every 0.22 s from the peak to the end of the hold.
 local nextPulse,last=at.impact,(at.activeEnd or at.impact+.8)
 C.follow(ctx,last,function(age)
  if age>=nextPulse then
   nextPulse+=.22;local p=ctx.points('Mouth',age)
   ringPulse(p,(math.floor((age-at.impact)/.22)%2==0) and RED or IVORY,10,.5)
  end
 end)
 local g=C.ground(ctx,ctx.cf.Position);C.shake(g,.8,.5);C.dustRing(g,3,10,SNOW,{12,18},3)
end

-- ClawRake -------------------------------------------------------------------------------------
-- Two crossing claw crescents at claw height through the front, then snow thrown where they end.
local function rake(ctx,claw)
 local root=ctx.npc.PrimaryPart;if not root or not C.near(claw) then return end
 local frame=CFrame.new(Vector3.new(root.Position.X,claw.Y,root.Position.Z))*root.CFrame.Rotation
 local reach=math.max(3,C.flat(claw-root.Position).Magnitude)
 for i,tilt in {-.32,.32} do
  local f=frame*CFrame.new(0,i*.4-.2,0)*CFrame.Angles(0,0,tilt)
  K.ring(C.folder(),f,{segments=12,from=-.9,to=.9,radius0=reach-1.5,radius1=reach+1,width=.9,reveal=.08,duration=.32,color=i==1 and RED or DEEP,rim=IVORY,bodyAlpha=.25})
 end
 C.cue('hammer_whoosh',claw,.6,1.35);C.star(claw,IVORY,4.5,.15)
 local g=Vector3.new(claw.X,ctx.groundY,claw.Z);snow(g+up*.3,root.CFrame.LookVector+up*.5,10,{10,16},45,2.5)
end
local function rakeAt(ctx,when)
 if ctx.alphaRake then return end;ctx.alphaRake=true
 C.at(ctx,when,function() rake(ctx,ctx.points('RightClaw',when)) end)
end

-- Charge ---------------------------------------------------------------------------------------
local function coil(ctx)
 local g=C.ground(ctx,ctx.cf.Position);if not C.near(g) then return end
 local dir=ctx.charge and ctx.charge.dir or C.flat(ctx.cf.LookVector)
 C.cue('hammer_whoosh',g,.4,1.2)
 snow(g-dir*1.5+up*.3,-dir+up*.5,8,{6,11},35,2.5)
end
local function skid(ctx,pos,dir)
 C.shake(pos,.5,.22);if not C.near(pos) then return end
 C.cue('sand_burst',pos,.45,1.2)
 snow(pos+dir*1.5+up*.4,dir+up*.7,18,{12,18},35,3)
end
local function run(ctx)
 if ctx.alphaRun or not ctx.charge then return end;ctx.alphaRun=true
 local ch,def=ctx.charge,ctx.def;local s=ctx.scale or 1
 local stride=ctx.timing.chargeStrideLength or 16;local half=math.max(1,stride/2)
 local root0=ctx.npc.PrimaryPart;local last=root0 and root0.Position;local covered=0
 local nextStep,side,stopped=half*.5,1,false
 local maxAge=ctx.attack.impact+(def.length or 56)/(def.speed or 38)+2
 C.follow(ctx,maxAge,function(age)
  local root=ctx.npc.PrimaryPart;if not root then return true end
  local step=last and C.flat(root.Position-last).Magnitude or 0;last=root.Position
  if step<20 then covered+=step end
  local dir=ch.heading or ch.dir;local pos=Vector3.new(root.Position.X,root.Position.Y-ctx.timing.rootHeight,root.Position.Z)
  if not stopped then
   while covered>=nextStep do
    local f=pos+dir:Cross(up)*side*1.1*s
    if C.near(f) then snow(f+up*.3,-dir+up*.6,4,{6,10},30,2.2) end
    C.shake(f,.2,.1);side=-side;nextStep+=half
   end
   if ch.stopAge and age>=ch.stopAge then stopped=true;skid(ctx,pos,dir) end
  else
   -- The finish rake where the run ended, at its impact (known once the server's stop arrives).
   local f,at=C.finish(ctx)
   if f and at and age>=at then ctx.alphaRake=true;rake(ctx,Vector3.new(f.center.X,ctx.groundY+3.2*s,f.center.Z));return true end
   if not at and age>ch.stopAge+2 then return true end
  end
 end)
end

function A.windup(ctx)
 local k=ctx.kind
 if k=='Howl' then breath(ctx) elseif ctx.charge then coil(ctx) end
end
function A.impact(ctx)
 local k=ctx.kind
 if k=='Howl' then breath(ctx);howlPeak(ctx)
 elseif ctx.charge then run(ctx)
 elseif k=='ClawRake' then rakeAt(ctx,ctx.attack.impact) end
end
-- The run's impact is the launch (end of ChargeStart); active keeps it alive if the impact was missed.
function A.active(ctx,age) if ctx.charge then run(ctx) end end

-- Intro: the rim howl.
function A.intro(m)
 local root=m.npc.PrimaryPart;if not root then return end
 local head=root.Position+up*(((m.timing and m.timing.height) or 9.1)-((m.timing and m.timing.rootHeight) or 4))*.85
 C.shake(root.Position,1,.6);if not C.near(root.Position,60) then return end
 howlCue(head,1);C.light(head,RED,50,3.5,1.2)
 for i=0,4 do task.delay(i*.22,function() ringPulse(head,i%2==0 and RED or IVORY,16,.6) end) end
 local g=m.ground or Vector3.new(root.Position.X,C.feet(m.npc) or root.Position.Y,root.Position.Z)
 C.dustRing(g,3,12,SNOW,{14,20},3);snow(root.Position+up*2,up,14,{6,12},80,3)
end
return A
