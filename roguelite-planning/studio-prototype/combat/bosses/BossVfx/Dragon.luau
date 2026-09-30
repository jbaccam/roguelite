-- The Inferno Dragon's effects (plan F Task 14). Client-only; nothing here changes hits.
-- Sizes follow the scaled boss: ctx.scale is its size multiple and def.radius / def.length are the
-- server's final hit sizes, so what burns is what hurts.
-- FireBreath: the throat glows and embers are sucked into the jaws on the inhale; a mouth blast,
--   then a layered flame jet follows the sampled (and tracking) breath direction down onto the
--   ground. The ground along the whole cone catches, licks up flame and leaves scorch marks.
-- TailWhip: dust as he coils; an ember ribbon on the spade, a dust wall kicked where it skims the
--   ground, a burning crescent and a white wind slash revealed along the swept arc.
-- FrontStomp: a wing-gust of dust and heating cracks under the landing; then a flash, two
--   shockwaves, a dust wall, lava cracks that glow and cool, fire jets out of the cracks, molten
--   rocks and a smoke ring.
-- Aftershock (FrontStomp's follow-up): a magma geyser out of each circle.
local C=require(script.Parent:WaitForChild('Common'))
local K=C.K
local ns,cs=C.ns,C.cs
local up=Vector3.yAxis
local HOT,EMBER,FLAME,DEEP=Color3.fromRGB(255,226,140),Color3.fromRGB(255,138,52),Color3.fromRGB(255,150,50),Color3.fromRGB(200,48,26)
local WHITE_HOT=Color3.fromRGB(255,250,214)
local COOL,SMOKE,ASH=Color3.fromRGB(110,28,16),Color3.fromRGB(74,66,62),Color3.fromRGB(196,176,156)
local ROCKS={'MoltenRock_A','MoltenRock_B','MoltenRock_C'}
local OBSIDIAN={Color3.fromRGB(52,46,48),Enum.Material.Basalt}
local SPHERE,SURFACE,INWARD=Enum.ParticleEmitterShape.Sphere,Enum.ParticleEmitterShapeStyle.Surface,Enum.ParticleEmitterShapeInOut.Inward
local D={}

local function dust(pos,count,look,speed,size)
 size=size or 3.5
 C.emit(pos,look or up,'DustPuff',{emit=count,Speed=speed or {4,8},SpreadAngle=50,Drag=3,Lifetime={.6,.9},Size=ns({0,size*.45},{1,size}),Color=ASH,Transparency=ns({0,.3},{.6,.45},{1,1}),LightInfluence=.8,Rotation={0,360},RotSpeed={-40,40}})
end
local function embers(pos,count,speed,spread,size)
 C.emit(pos,up,'Ember',{emit=count,Speed=speed,SpreadAngle=spread or 55,Lifetime={.7,1.3},Size=ns({0,size or .55},{1,0}),Color={HOT,EMBER},Acceleration=Vector3.new(0,-22,0),Drag=.8,LightEmission=1})
end
-- A short burst of flame straight up out of the ground: the fire jets and geysers.
local function jet(pos,height,width)
 C.emit(pos,up,'Flame',{emit=math.ceil(height*.9),Speed={height*1.3,height*1.9},SpreadAngle=9,Lifetime={.35,.55},Size=ns({0,width*.6},{.4,width},{1,width*.4}),Color=cs({0,WHITE_HOT},{.25,HOT},{.6,FLAME},{1,DEEP}),Transparency=ns({0,.2},{.15,0},{.8,.2},{1,1}),Drag=1.5,LightEmission=.85,Rotation={-25,25},RotSpeed={-50,50}})
end

-- FireBreath ------------------------------------------------------------------------------
local function inhale(ctx)
 local at,def=ctx.attack,ctx.def;local m=ctx.points(def.point,C.age(ctx));if not C.near(m) then return end
 local s=ctx.scale
 local _=C.cue('dragon_inhale',m,.8) or C.cue('dragon_windup',m,.7)
 -- Embers and a little smoke spawn on a sphere round the jaws and stream inward.
 local host=C.part('Host',Vector3.one*12*s,CFrame.new(m),K.White,1)
 C.fx(host,'Ember',{Rate=70,Shape=SPHERE,ShapeStyle=SURFACE,ShapeInOut=INWARD,Speed={12*s,16*s},Lifetime={.38,.46},Size=ns({0,.3*s},{.6,.6*s},{1,.1}),Color={HOT,EMBER},Transparency=ns({0,1},{.2,0},{1,.2}),LightEmission=1})
 C.fx(host,'SmokePuff',{Rate=10,Shape=SPHERE,ShapeStyle=SURFACE,ShapeInOut=INWARD,Speed={11*s,13*s},Lifetime={.42,.5},Size=ns({0,2*s},{1,.5}),Color=Color3.fromRGB(120,100,90),Transparency=ns({0,1},{.3,.6},{1,1}),LightInfluence=.7})
 local light=Instance.new('PointLight');light.Color=EMBER;light.Range=0;light.Brightness=0;light.Shadows=false;light.Parent=host
 C.follow(ctx,at.impact,function(age)
  host.CFrame=CFrame.new(ctx.points(def.point,age))
  local k=math.clamp((age-at.warnStart)/math.max(.1,at.impact-at.warnStart),0,1);light.Range=(4+10*k)*s;light.Brightness=.4+2.6*k*k
 end,function() C.retire({host},.6) end)
end
-- The LavaGlow sections ramp hot on the inhale, flicker through the breath and cool afterwards.
local function throat(ctx)
 if ctx.dragonThroat then return end;ctx.dragonThroat=true
 local at=ctx.attack;local glow=C.glow(ctx.npc,'LavaGlow');if #glow==0 then return end
 C.follow(ctx,at.activeEnd+.4,function(age)
  local k=age<at.impact and math.clamp((age-at.warnStart)/math.max(.1,at.impact-at.warnStart),0,1)^1.5
   or age<at.activeEnd and .85+.15*math.sin(age*37) or 1-(age-at.activeEnd)/.4
  C.setGlow(glow,HOT,k)
 end,function() C.setGlow(glow,nil,0) end)
end
-- The flame jet. The damage cone is flat on the ground from the mouth's ground point along the
-- sampled direction; the jet aims from the mouth to 85% of that length on the ground, and three
-- ground hosts along the centreline set the whole cone alight, so the fire covers what it hurts.
local function breath(ctx)
 if ctx.dragonBreath then return end;ctx.dragonBreath=true
 local at,def=ctx.attack,ctx.def;local len=def.length or 20;local s=ctx.scale;local half=def.halfAngle or math.rad(22)
 local m=ctx.points(def.point,math.max(C.age(ctx),at.impact));if not C.near(m,len) then return end
 local mouth=C.part('Host',Vector3.one*.6*s,CFrame.new(m),K.White,1)
 local mid=C.part('Host',Vector3.one*.1,CFrame.new(m),K.White,1)
 C.fx(mouth,'Flame',{Rate=130,Speed={32,42},SpreadAngle=math.deg(half)*.8,Lifetime={.6,.75},Size=ns({0,2.4*s},{.45,6*s},{1,8.5*s}),Color=cs({0,HOT},{.3,FLAME},{1,DEEP}),Transparency=ns({0,.35},{.12,0},{.75,.15},{1,1}),Drag=.4,Acceleration=Vector3.new(0,5,0),LightEmission=.75,Rotation={-30,30},RotSpeed={-40,40},ZOffset=.5})
 C.fx(mouth,'Flame',{Rate=80,Speed={38,44},SpreadAngle=7,Lifetime={.32,.45},Size=ns({0,1.2*s},{1,4.2*s}),Color={WHITE_HOT,Color3.fromRGB(255,204,96)},Transparency=ns({0,.2},{.7,.3},{1,1}),LightEmission=1,Rotation={-20,20},ZOffset=1}) -- hot inner core
 C.fx(mouth,'Ember',{Rate=60,Speed={24,40},SpreadAngle=math.deg(half),Lifetime={.7,1.1},Size=ns({0,.5*s},{1,0}),Color={HOT,EMBER},Drag=.8,Acceleration=Vector3.new(0,8,0),LightEmission=1})
 C.fx(mouth,'SmokePuff',{Rate=14,Speed={14,20},SpreadAngle=math.deg(half),Lifetime={1,1.4},Size=ns({0,2*s},{1,7*s}),Color={SMOKE,Color3.fromRGB(40,36,34)},Transparency=ns({0,1},{.3,.45},{1,1}),Acceleration=Vector3.new(0,6,0),LightInfluence=.6,Rotation={0,360},RotSpeed={-30,30}})
 -- The ground on fire: hosts at 35%, 62% and 88% of the cone, each as wide as the cone there.
 local ground={}
 for i,f in {.35,.62,.88} do
  local w=2*len*f*math.tan(half)
  local h=C.part('Host',Vector3.new(w,.2,len*.26),CFrame.new(m),K.White,1)
  ground[i]={host=h,f=f,
   flame=C.fx(h,'Flame',{Rate=18+i*8,EmissionDirection=Enum.NormalId.Top,Speed={3,7},SpreadAngle=20,Lifetime={.4,.6},Size=ns({0,1.6*s},{.4,3.8*s},{1,2.4*s}),Color=cs({0,HOT},{.4,FLAME},{1,DEEP}),Transparency=ns({0,.3},{.2,0},{1,1}),LightEmission=.8,Rotation={-15,15}}),
   smoke=i==3 and C.fx(h,'SmokePuff',{Rate=16,EmissionDirection=Enum.NormalId.Top,Speed={4,8},SpreadAngle=25,Lifetime={1,1.4},Size=ns({0,3*s},{1,8*s}),Color={SMOKE,Color3.fromRGB(40,36,34)},Transparency=ns({0,.6},{.2,.35},{1,1}),Acceleration=Vector3.new(0,3,0),LightInfluence=.6,Rotation={0,360},RotSpeed={-30,30}}) or nil}
 end
 local light=Instance.new('PointLight');light.Color=FLAME;light.Range=len*1.1;light.Brightness=3.2;light.Shadows=false;light.Parent=mid
 local snd,sh=C.cue('fire_breath',m,.85,1,true)
 -- The blast out of the jaws.
 K.pop(C.folder(),m,FLAME,1.5*s,7*s,.25,.35);C.star(m,HOT,7*s,.18);C.light(m,HOT,24*s,3.5,.3);C.shake(m,.55,.35)
 local nextMark,hosts=at.impact+.1,{mouth,mid}
 for _,g in ground do table.insert(hosts,g.host) end
 C.follow(ctx,at.activeEnd,function(age)
  local p=ctx.points(def.point,age);local d=C.flat(ctx.dirAt(def.point,age));if d.Magnitude<.05 then d=C.flat(ctx.cf.LookVector) end;d=d.Unit
  local base=C.ground(ctx,p);local farPt=base+d*len*.85
  mouth.CFrame=C.aim(p,farPt+up*1.2-p);mid.CFrame=CFrame.new((p+farPt)/2+up*1.5);light.Brightness=2.8+math.random()*.8
  for _,g in ground do local c=base+d*len*g.f+up*.2;g.host.CFrame=CFrame.lookAt(c,c+d) end
  if sh then sh.CFrame=CFrame.new(p) end
  if age>=nextMark then -- scorch marks every 0.2 s along the burning cone, fading over 4 s
   nextMark+=.2;local side=d:Cross(up);local f=.3+math.random()*.65
   C.stain(base+d*len*f+side*(math.random()-.5)*len*f*math.tan(half)*1.6+up*.03,'ScorchMark',(5+math.random()*3)*s,Color3.new(1,1,1),.2,1.4,2.4,.08)
  end
 end,function() C.retire(hosts,1.5);C.stopSound(snd,sh,.25) end)
end

-- TailWhip --------------------------------------------------------------------------------
local function coil(ctx)
 local g=C.ground(ctx,ctx.cf.Position);if not C.near(g) then return end
 local s=ctx.scale
 C.cue('dragon_windup',g,.8)
 for _,x in {-3,3} do local p=ctx.ground*Vector3.new(x*s,0,3.5*s);dust(Vector3.new(p.X,ctx.groundY+.4,p.Z),6,up,{4,8},4*s) end -- under the hind feet
end
-- The spade's ember ribbon: a Trail between the outer half of the TailMid->SpadeTip span, on from
-- just before impact to the end of the sweep, then frozen so it fades where it finished. Where the
-- spade skims the ground it throws up a wall of dust along its path.
local function tail(ctx)
 if ctx.dragonTail then return end;ctx.dragonTail=true
 local at,def=ctx.attack,ctx.def;local s=ctx.scale;local age0=C.age(ctx);local tip0=ctx.points(def.point,age0);if not C.near(tip0) then return end
 local a=C.part('Host',Vector3.one*.1,CFrame.new(ctx.points(def.mid,age0)),K.White,1)
 local b=C.part('Host',Vector3.one*.4,CFrame.new(tip0),K.White,1)
 local a0=Instance.new('Attachment');a0.Parent=a;local a1=Instance.new('Attachment');a1.Parent=b
 local tr=Instance.new('Trail');tr.Name='BossVfxTrail';tr.Attachment0=a0;tr.Attachment1=a1;tr.Lifetime=.3;tr.MinLength=.05;tr.FaceCamera=false;tr.LightEmission=.8;tr.LightInfluence=.2
 tr.Color=cs({0,WHITE_HOT},{.3,EMBER},{1,Color3.fromRGB(150,40,20)});tr.Transparency=ns({0,.1},{.5,.5},{1,1});tr.WidthScale=ns({0,1},{1,.35});tr.Enabled=false;tr.Parent=a
 local sparks=C.fx(b,'Ember',{Rate=0,Enabled=true,Speed={5,11},SpreadAngle=180,Lifetime={.4,.7},Size=ns({0,.55*s},{1,0}),Color={HOT,EMBER},Drag=1.2,Acceleration=Vector3.new(0,6,0),LightEmission=1})
 local nextDust,lastTip=0,tip0
 C.follow(ctx,at.activeEnd+.3,function(age)
  if age>at.activeEnd+.04 then if sparks then sparks.Rate=0 end;return end
  local on=age>=at.impact-.06
  local mid,tip=ctx.points(def.mid,age),ctx.points(def.point,age);local along=tip-mid;local ext=along.Magnitude>.1 and along.Unit or Vector3.zero
  a.CFrame=CFrame.new(mid:Lerp(tip,.35));b.CFrame=CFrame.new(tip+ext*1.2*s);tr.Enabled=on;if sparks then sparks.Rate=on and 90 or 0 end
  if on and age>=nextDust and tip.Y-ctx.groundY<4.5*s then
   nextDust=age+.035;local v=C.flat(tip-lastTip);local look=(v.Magnitude>.01 and v.Unit or Vector3.zero)+up*.7
   dust(Vector3.new(tip.X,ctx.groundY+.4,tip.Z),3,look,{7,12},5*s)
   C.emit(Vector3.new(tip.X,ctx.groundY+.3,tip.Z),look,'Ember',{emit=4,Speed={8,14},SpreadAngle=30,Lifetime={.4,.7},Size=ns({0,.45*s},{1,0}),Color={HOT,EMBER},Acceleration=Vector3.new(0,-20,0),LightEmission=1})
  end
  lastTip=tip
 end,function() C.retire({a,b},.5) end)
end
-- The crescents: a burning ring and a thinner white wind slash just outside it, revealed over the
-- server's sweep arc in the direction the tail travels, then widening and fading.
local function whip(ctx)
 local at,def=ctx.attack,ctx.def;local tip=ctx.points(def.point,at.impact)
 C.shake(tip,.9,.35);if not C.near(tip) then return end
 C.cue('tail_whoosh',tip,.9);C.star(tip,HOT,5*ctx.scale,.16)
 local s=C.shape(ctx);if not s or s.kind~='arc' then return end
 local base=Vector3.new(s.pivot.X,ctx.groundY+.12,s.pivot.Z);local frame=CFrame.lookAt(base,base+s.forward)
 local from,to=s.from,s.to
 if C.Shapes.yaw(s.forward,tip-s.pivot)>C.Shapes.yaw(s.forward,ctx.points(def.point,at.activeEnd)-s.pivot) then from,to=to,from end
 local outer,sweep=s.outer-1,math.max(.1,at.activeEnd-at.impact)
 K.ring(C.folder(),frame,{segments=40,from=from,to=to,radius0=outer,radius1=outer+2,width=math.clamp((outer-s.inner)*.5,3,9),reveal=sweep,duration=sweep+.45,hold=.06,color=EMBER,rim=HOT,bodyAlpha=.55})
 K.ring(C.folder(),frame+up*.6,{segments=40,from=from,to=to,radius0=outer+1.5,radius1=outer+5,width=1.4,reveal=sweep,duration=sweep+.35,hold=.04,color=Color3.new(1,1,1),bodyAlpha=.35})
end

-- FrontStomp ------------------------------------------------------------------------------
local function rear(ctx)
 local at,def=ctx.attack,ctx.def;local s=ctx.scale;local g=C.ground(ctx,ctx.cf.Position);if not C.near(g) then return end
 C.cue('dragon_windup',g,.9);C.cue('wing_flap',g,.6)
 local c=C.ground(ctx,ctx.points(def.point,at.impact));local r=def.radius or 10
 C.at(ctx,math.min(at.impact*.3,.25),function() -- the wing flap pushes a ring of dust outward
  C.dustRing(g,6*s,10,ASH,{16,22},4*s)
 end)
 C.at(ctx,at.impact*.55,function() -- the ground heats under the landing: faint cracks and rising embers
  local p,set=C.plate(c+up*.04,'LavaCracks',r*1.5,COOL,nil,1.2)
  if p then K.animate(at.impact*.45+.05,function(t) set(1-.45*t,COOL:Lerp(EMBER,t)) end,function() p:Destroy() end,'bossPlate',64) end
  local h=C.part('Host',Vector3.new(r*1.3,.2,r*1.3),CFrame.new(c+up*.2),K.White,1)
  C.fx(h,'Ember',{emit=22,EmissionDirection=Enum.NormalId.Top,Speed={3,7},SpreadAngle=15,Lifetime={.5,.8},Size=ns({0,.45*s},{1,0}),Color={HOT,EMBER},LightEmission=1})
  C.retire({h},1)
 end)
end
local function stomp(ctx)
 local at,def=ctx.attack,ctx.def;local s=ctx.scale;local r=def.radius or 10;local g=C.ground(ctx,ctx.points(def.point,at.impact))
 C.shake(g,1.8,.65);if not C.near(g,r) then return end
 C.cue('ground_quake',g,1);C.cue('lava_hiss',g,.6)
 C.star(g+up*3,WHITE_HOT,r*1.4,.26);C.light(g+up*4,FLAME,r*3.5,4.5,.7)
 K.pop(C.folder(),g+up*1.5,HOT,r*.4,r*1.6,.28,.45)
 C.ring(g+up*.07,'ShockwaveRing',2,r*2.1,.32,Color3.fromRGB(255,214,150),0,true) -- the snap, out to the hit edge
 C.ring(g+up*.1,'ShockwaveRing',r,r*3.4,.8,Color3.fromRGB(255,140,60),.35,true) -- a slower rolling second wave
 C.dustRing(g,r*.9,16,ASH,{18,26},5*s)
 -- A foot flash under each front foot.
 for _,name in {'LeftFrontImpact','RightFrontImpact'} do local f=C.ground(ctx,ctx.points(name,at.impact));C.star(f+up*1.2,HOT,4*s,.16);dust(f+up*.4,5,up,{8,14},4*s) end
 -- Lava cracks: snap open, glow orange-yellow, cool to dark red over ~2 s, fade out by 3 s.
 local p,set=C.plate(g+up*.04,'LavaCracks',r*2.2,HOT,nil,2.4)
 if p then
  K.animate(3,function(t,age)
   local col=age<.25 and HOT or HOT:Lerp(COOL,K.smooth((age-.25)/1.9))
   local a=age<.08 and 1-age/.08 or t<.6 and 0 or K.smooth((t-.6)/.4)
   set(a,col,r*2.2*(age<.12 and .82+.18*age/.12 or 1),nil,2.4-1.6*K.smooth(age/2.2))
  end,function() p:Destroy() end,'bossPlate',64)
 end
 -- Fire jets burst out of the cracks, staggered round the ring.
 local seed=math.random()*6.28
 for i=1,6 do
  local a=seed+i/6*math.pi*2;local q=g+Vector3.new(math.cos(a),0,math.sin(a))*r*(.45+.25*(i%2))
  task.delay(.04*i,function() if C.near(q) then jet(q+up*.3,9*s,3*s) end end)
 end
 C.chunks(g+up*1.5,ctx.groundY,ROCKS,{count=10,speed={9,15},up={26,36},scale={1.6*s,2.2*s},life=1.6,trail={HOT,DEEP,.6*s},fallback=OBSIDIAN})
 embers(g+up*.5,80,{16,34},60,.6*s)
 C.emit(g+up*.6,up,'SmokePuff',{emit=14,Speed={14,20},SpreadAngle=85,Drag=3.5,Lifetime={1.1,1.6},Size=ns({0,3*s},{1,7*s}),Color={SMOKE,Color3.fromRGB(46,40,38)},Transparency=ns({0,.3},{.5,.45},{1,1}),LightInfluence=.6,Rotation={0,360},RotSpeed={-30,30}})
end

-- Aftershock: magma geysers -----------------------------------------------------------------
function D.aftershock(m)
 local s,r=m.scale or 1,m.radius or 6
 for i,p in m.points do
  if C.near(p,r) then
   local plate,set=C.plate(p+up*.05,'LavaCracks',r*2.1,HOT,nil,2.2)
   if plate then K.animate(1.6,function(t) set(K.smooth((t-.35)/.65),HOT:Lerp(COOL,t)) end,function() plate:Destroy() end,'bossPlate',64) end
   jet(p+up*.3,16*s,r*.9);jet(p+up*.3,10*s,r*.5)
   C.ring(p+up*.08,'ShockwaveRing',1,r*2.3,.3,Color3.fromRGB(255,180,110),0,true)
   C.star(p+up*2.5,WHITE_HOT,r*1.5,.2);C.light(p+up*4,FLAME,r*4,3.5,.5)
   C.chunks(p+up*1.2,p.Y,ROCKS,{count=4,speed={5,9},up={24,34},scale={1.2*s,1.7*s},life=1.4,trail={HOT,DEEP,.5*s},fallback=OBSIDIAN})
   embers(p+up*.5,30,{14,28},30,.5*s)
   C.emit(p+up*2,up,'SmokePuff',{emit=5,Speed={8,12},SpreadAngle=30,Drag=2,Lifetime={1,1.4},Size=ns({0,2.5*s},{1,6*s}),Color={SMOKE,Color3.fromRGB(46,40,38)},Transparency=ns({0,.35},{.5,.5},{1,1}),LightInfluence=.6,Rotation={0,360}})
   if i<=2 then C.cue('lava_hiss',p,.55,1.1);C.cue('ground_quake',p,.4,1.3) end
   C.shake(p,.8,.3)
  end
 end
end

function D.windup(ctx)
 local k=ctx.kind
 if k=='FireBreath' then inhale(ctx);throat(ctx) elseif k=='TailWhip' then coil(ctx);tail(ctx) elseif k=='FrontStomp' then rear(ctx) end
end
function D.impact(ctx)
 local k=ctx.kind
 if k=='FireBreath' then throat(ctx);breath(ctx) elseif k=='TailWhip' then tail(ctx);whip(ctx) elseif k=='FrontStomp' then stomp(ctx) end
end
-- The breath and the tail run on their own controllers; active only starts them if impact was missed.
function D.active(ctx,age)
 if ctx.kind=='FireBreath' then breath(ctx) elseif ctx.kind=='TailWhip' then tail(ctx) end
end
return D
