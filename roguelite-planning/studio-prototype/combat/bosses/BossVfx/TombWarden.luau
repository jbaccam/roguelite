-- The Tomb Warden's effects (round 10, Desert Basin THE TOMB OPENS). Client-only; nothing here
-- changes hits.
-- FistSlam: sand pours off the raised stone fists and gold dust gathers; the slam lands in a gold and
--   sand shockwave with sandstone rubble. Its follow-up circles open as cracked sand with a gold glyph
--   ring and erupt in sand geysers (followup / aftershock).
-- FistHook: grit kicks off the planted foot; the hook leaves a sand crescent through the front.
-- Roar (enrage): gold dust rings and a sandstorm puff off the shoulders; the eyes burn hotter.
-- Intro (Emerge, at BossIntroLand): he steps out of the coffin: a dust wall, rubble and a rumble.
local C=require(script.Parent:WaitForChild('Common'))
local K=C.K
local ns=C.ns
local up=Vector3.yAxis
local GOLD,BRIGHT,SAND,DUST=Color3.fromRGB(255,190,84),Color3.fromRGB(255,240,200),Color3.fromRGB(226,196,140),Color3.fromRGB(214,190,150)
local CRACK=Color3.fromRGB(122,92,60)
local RUBBLE={'SandstoneRubble_A','SandstoneRubble_B'}
local STONE={SAND,Enum.Material.Sandstone}
local W={}

local function dust(pos,look,count,speed,size)
 C.emit(pos,look,'DustPuff',{emit=count,Speed=speed,SpreadAngle=80,Drag=3.5,Lifetime={.8,1.2},Size=ns({0,size*.5},{1,size}),Color=DUST,Transparency=ns({0,.25},{.6,.42},{1,1}),LightInfluence=.8,Rotation={0,360},RotSpeed={-40,40}})
end
local function burst(pos,count,speed,spread,size)
 C.emit(pos,up,'SandBurst',{emit=count,Speed=speed,SpreadAngle=spread,Lifetime={.6,.9},Size=ns({0,size},{1,size*2.4}),Color=SAND,Transparency=ns({0,0},{.7,.2},{1,1}),Acceleration=Vector3.new(0,-50,0),Rotation={-20,20},LightInfluence=.8})
end
local function headOf(npc,T)
 local root=npc.PrimaryPart;if not root then return nil end
 return root.Position+up*(((T and T.height) or 8.6)-((T and T.rootHeight) or 3.5))*.85
end

-- FistSlam -------------------------------------------------------------------------------------
local function slamWindup(ctx)
 if ctx.wardenRaise then return end;ctx.wardenRaise=true
 local at=ctx.attack;local p=ctx.points('SlamCenter',C.age(ctx));if not C.near(p) then return end
 C.cue('stone_rumble',p,.6,.9)
 local host=C.part('Host',Vector3.new(2.4,.4,2.4),C.aim(p,-up),K.White,1)
 C.fx(host,'SandSpray',{Rate=22,Speed={1,3},SpreadAngle=25,Lifetime={.5,.75},Size=ns({0,.9},{1,1.9}),Color=SAND,Transparency=ns({0,.15},{.7,.35},{1,1}),Acceleration=Vector3.new(0,-28,0),Rotation={0,360},RotSpeed={-90,90},LightInfluence=.8})
 C.fx(host,'SnowSparkle',{Rate=18,Speed={.5,1.5},SpreadAngle=180,Lifetime={.4,.6},Size=ns({0,.5},{1,0}),Color=GOLD,LightEmission=.9})
 local glint=false
 C.follow(ctx,at.impact,function(age)
  local q=ctx.points('SlamCenter',age);host.CFrame=C.aim(q,-up)
  if not glint and age>=at.impact-.3 then glint=true;C.star(q+up,BRIGHT,5,.18) end
 end,function() C.retire({host},.8) end)
end
local function slamImpact(ctx)
 local at,def=ctx.attack,ctx.def;local g=C.ground(ctx,ctx.points('SlamCenter',at.impact));local r,s=def.radius or 9,ctx.scale
 C.shake(g,1.3,.5);if not C.near(g,r) then return end
 C.cue('stone_rumble',g,.9,.8);C.cue('sand_burst',g,.7,.9)
 C.star(g+up*2.5,BRIGHT,r*1.2,.22);C.light(g+up*3,GOLD,r*3,2.6,.35)
 C.ring(g+up*.06,'ShockwaveRing',1,r*2.1,.4,GOLD,0,true);C.ring(g+up*.09,'HieroglyphCircle',2,r*1.4,.6,GOLD,.2,1.6)
 C.ring(g+up*.11,'ShockwaveRing',r*.8,r*2.8,.7,SAND,.4,true)
 burst(g+up*.3,40,{18,30},40,1.6*s);dust(g+up*.4,up,12,{10,15},4.5*s);C.dustRing(g,r*.8,14,DUST,{16,22},3.5*s)
 C.chunks(g+up*1.5,ctx.groundY,RUBBLE,{count=6,speed={9,15},up={14,22},scale={.7,1.1},life=1.4,fallback=STONE})
 local p,set=C.plate(g+up*.04,'EarthCracks',r*1.4,CRACK,nil,false)
 if p then K.animate(2.2,function(t,age) set(age<.08 and 1-.6*age/.08 or .4+.6*K.smooth((t-.4)/.6)) end,function() p:Destroy() end,'bossPlate',64) end
end

-- FistHook -------------------------------------------------------------------------------------
local function hookWindup(ctx)
 local g=C.ground(ctx,ctx.cf.Position);if not C.near(g) then return end
 C.cue('hammer_whoosh',g,.45,.8)
 dust(g-ctx.cf.LookVector*1.5+up*.3,-ctx.cf.LookVector+up*.4,5,{5,9},3)
end
-- The hook's path: a crescent of sand through the front at fist height, revealed along the swing.
local function hookImpact(ctx)
 local at=ctx.attack;local fist=ctx.points('HookFist',at.impact);if not C.near(fist) then return end
 local root=ctx.cf;local reach=C.flat(fist-root.Position).Magnitude
 local frame=CFrame.new(Vector3.new(root.X,fist.Y,root.Z))*root.Rotation
 K.ring(C.folder(),frame,{segments=14,from=-1.1,to=1.1,radius0=math.max(2,reach-1),radius1=reach+1.5,width=1.6,reveal=.1,duration=.42,color=SAND,rim=BRIGHT,bodyAlpha=.35})
 C.cue('hammer_thud',fist,.45,.8);C.star(fist,BRIGHT,4,.15)
 C.emit(fist,ctx.dirAt('HookFist',at.impact),'SandSpray',{emit=16,Speed={10,16},SpreadAngle=35,Lifetime={.4,.6},Size=ns({0,1},{1,2.2}),Color=SAND,Transparency=ns({0,0},{.7,.25},{1,1}),Acceleration=Vector3.new(0,-40,0),Drag=.8,Rotation={-40,40},LightInfluence=.8})
end

function W.windup(ctx)
 if ctx.kind=='FistSlam' then slamWindup(ctx) elseif ctx.kind=='FistHook' then hookWindup(ctx) end
end
function W.impact(ctx)
 if ctx.kind=='FistSlam' then slamImpact(ctx) elseif ctx.kind=='FistHook' then hookImpact(ctx) end
end
function W.active(ctx,age) end

-- Follow-up circles: cracked sand with a slow gold glyph ring until they erupt.
function W.followup(m)
 local r=m.radius or 5;local life=math.max(.1,m.at-workspace:GetServerTimeNow())
 for _,p in m.points do
  if C.near(p,r) then
   local plate,set=C.plate(p+up*.04,'EarthCracks',r*.7,CRACK,nil,false)
   if plate then
    K.animate(life+1.4,function(_,age)
     local k=math.min(1,age/life)
     set(age<life and .55-.45*k or .1+.9*K.smooth((age-life-.6)/.8),nil,r*(.7+1.4*(1-(1-k)^2)))
    end,function() plate:Destroy() end,'bossPlate',64)
   end
   C.stain(p+up*.06,'HieroglyphCircle',r*1.6,GOLD,.15,life,.3,.35,.6,1.4)
   local h=C.host(p+up*.3,life+1.4,up)
   C.fx(h,'DustPuff',{Rate=6,Speed={1,3},SpreadAngle=60,Lifetime={.5,.8},Size=ns({0,.6},{1,1.8}),Color=DUST,Transparency=ns({0,.4},{.6,.6},{1,1}),LightInfluence=.8,Rotation={0,360}})
   task.delay(life,function() C.retire({h},.8) end)
  end
 end
end
function W.aftershock(m)
 local s,r=m.scale or 1,m.radius or 5
 for i,p in m.points do
  if C.near(p,r) then
   burst(p+up*.3,30,{26,40},14,1.8*s)
   C.emit(p+up*r,up,'SandBurst',{emit=1,Speed=0,Lifetime=.8,Size=ns({0,r*1.8},{1,r*2.3}),Color=SAND,Transparency=ns({0,0},{.8,.1},{1,1}),LightInfluence=.8}) -- the bottom-anchored geyser
   dust(p+up*.4,up,8,{12,18},r*.7)
   C.ring(p+up*.07,'ShockwaveRing',1,r*2.3,.32,GOLD,0,true);C.star(p+up*2,BRIGHT,r*1.3,.18)
   C.chunks(p+up*1.2,p.Y,RUBBLE,{count=3,speed={7,12},up={12,18},scale={.6,.9},life=1.2,fallback=STONE})
   if i<=2 then C.cue('sand_burst',p,.6,1) end;C.shake(p,.6,.25)
  end
 end
end

-- Enrage roar ----------------------------------------------------------------------------------
local function roarPeak(npc,scale,T)
 local root=npc.PrimaryPart;if not root then return end
 local s=scale or 1;local head=headOf(npc,T) or root.Position;local y=C.feet(npc);local g=Vector3.new(root.Position.X,y or root.Position.Y-3,root.Position.Z)
 C.shake(root.Position,1.4,.6);if not C.near(root.Position,40) then return end
 C.cue('zombie_roar',head,.9,.6);C.cue('stone_rumble',g,.6,.8)
 C.ring(g+up*.08,'ShockwaveRing',6*s,40*s,.8,GOLD,0,true);C.ring(g+up*.11,'HieroglyphCircle',4*s,22*s,.9,GOLD,.25,1.6)
 C.star(head,BRIGHT,10*s,.24);C.light(head,GOLD,40,3.5,.8)
 for _,x in {-1,1} do
  local sp=head-up*1.5+root.CFrame.RightVector*x*2.6*s
  dust(sp,(up+root.CFrame.RightVector*x*.6).Unit,6,{6,10},4*s)
 end
 C.dustRing(g,5*s,16,DUST,{18,26},4*s)
end
function W.enrage(m)
 local npc=m.npc;local root=npc.PrimaryPart;if not root then return end
 local glow=C.glow(npc,'EyeGlow');local hot=Color3.fromRGB(255,120,40)
 if #glow>0 then K.animate(.3,function(t) C.setGlow(glow,hot,t) end,function() C.setGlow(glow,hot,1) end,'bossGlow',8) end
 C.fx(root,'Hieroglyphs',{Rate=5,EmissionDirection=Enum.NormalId.Top,Speed={2,4},SpreadAngle=40,Lifetime={1,1.4},Size=ns({0,0},{.2,.9},{1,0}),Color=GOLD,Transparency=ns({0,.15},{1,.6}),LightEmission=.7,Acceleration=Vector3.new(0,3,0),RotSpeed={-40,40}})
 if not m.roars then roarPeak(npc,m.scale,m.timing) end
end
function W.roar(ctx)
 local peak=ctx.attack and ctx.attack.impact or 0
 C.at(ctx,peak>0 and peak or .3,function() roarPeak(ctx.npc,ctx.scale,ctx.timing) end)
end

-- Intro: out of the coffin ---------------------------------------------------------------------
function W.intro(m)
 local root=m.npc.PrimaryPart;local g=m.ground
 if not g then if not root then return end;local y=C.feet(m.npc);g=Vector3.new(root.Position.X,y or root.Position.Y,root.Position.Z) end
 local s=m.scale or 1;local r=6*s
 C.shake(g,1.4,.6);if not C.near(g,40) then return end
 C.cue('stone_rumble',g,.85,.75);C.cue('sand_burst',g,.6,.85)
 C.ring(g+up*.06,'ShockwaveRing',r*.5,r*5,.6,BRIGHT,0,true);C.ring(g+up*.09,'HieroglyphCircle',r*.4,r*3,.9,GOLD,.25,1.6)
 C.light(g+up*4,GOLD,36,2.8,.7)
 C.dustRing(g,r*.8,16,DUST,{18,26},r*.55);dust(g+up*.5,up,16,{9,16},r*.8)
 C.chunks(g+up*2,g.Y,RUBBLE,{count=5,speed={8,14},up={12,20},scale={.6,1},life=1.4,fallback=STONE})
end
return W
