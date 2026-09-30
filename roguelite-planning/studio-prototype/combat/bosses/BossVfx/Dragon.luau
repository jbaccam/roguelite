-- The Inferno Dragon's effects (plan F Task 14). Client-only; nothing here changes hits.
-- FireBreath: the throat glows and embers are sucked into the jaws on the inhale; then a layered
-- flame cone follows the sampled breath direction down onto the ground, lighting it, licking up at
-- the far end and leaving scorch marks.
-- TailWhip: dust as he coils, an ember ribbon on the spade, dust kicked where it skims the ground,
-- and a crescent shockwave revealed along the swept arc.
-- FrontStomp: a wing-gust of dust and a pre-glow under the landing; then lava cracks that glow and
-- cool, molten rocks thrown up in a ring, embers and a low smoke ring.
local C=require(script.Parent:WaitForChild('Common'))
local K=C.K
local ns,cs=C.ns,C.cs
local up=Vector3.yAxis
local HOT,EMBER,FLAME,DEEP=Color3.fromRGB(255,226,140),Color3.fromRGB(255,138,52),Color3.fromRGB(255,150,50),Color3.fromRGB(200,48,26)
local COOL,SMOKE,ASH=Color3.fromRGB(110,28,16),Color3.fromRGB(74,66,62),Color3.fromRGB(196,176,156)
local ROCKS={'MoltenRock_A','MoltenRock_B','MoltenRock_C'}
local OBSIDIAN={Color3.fromRGB(52,46,48),Enum.Material.Basalt}
local SPHERE,SURFACE,INWARD=Enum.ParticleEmitterShape.Sphere,Enum.ParticleEmitterShapeStyle.Surface,Enum.ParticleEmitterShapeInOut.Inward
local D={}

local function dust(pos,count,look,speed)
 C.emit(pos,look or up,'DustPuff',{emit=count,Speed=speed or {4,8},SpreadAngle=50,Drag=3,Lifetime={.6,.9},Size=ns({0,1.5},{1,3.5}),Color=ASH,Transparency=ns({0,.3},{.6,.45},{1,1}),LightInfluence=.8,Rotation={0,360},RotSpeed={-40,40}})
end

-- FireBreath ------------------------------------------------------------------------------
local function inhale(ctx)
 local at,def=ctx.attack,ctx.def;local m=ctx.points(def.point,C.age(ctx));if not C.near(m) then return end
 local _=C.cue('dragon_inhale',m,.8) or C.cue('dragon_windup',m,.7)
 -- Embers and a little smoke spawn on a 6-stud sphere round the jaws and stream inward.
 local host=C.part('Host',Vector3.one*12,CFrame.new(m),K.White,1)
 C.fx(host,'Ember',{Rate=40,Shape=SPHERE,ShapeStyle=SURFACE,ShapeInOut=INWARD,Speed={10,13},Lifetime={.42,.5},Size=ns({0,.25},{.6,.5},{1,.1}),Color={HOT,EMBER},Transparency=ns({0,1},{.2,0},{1,.2}),LightEmission=1})
 C.fx(host,'SmokePuff',{Rate=6,Shape=SPHERE,ShapeStyle=SURFACE,ShapeInOut=INWARD,Speed={9,11},Lifetime={.45,.55},Size=ns({0,1.6},{1,.4}),Color=Color3.fromRGB(120,100,90),Transparency=ns({0,1},{.3,.6},{1,1}),LightInfluence=.7})
 local light=Instance.new('PointLight');light.Color=EMBER;light.Range=0;light.Brightness=0;light.Shadows=false;light.Parent=host
 C.follow(ctx,at.impact,function(age)
  host.CFrame=CFrame.new(ctx.points(def.point,age))
  local k=math.clamp((age-at.warnStart)/math.max(.1,at.impact-at.warnStart),0,1);light.Range=3+7*k;light.Brightness=.4+2*k*k
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
-- The flame cone. The damage cone is flat on the ground from the mouth's ground point along the
-- sampled direction; the flames are aimed from the mouth to 85% of that length on the ground so
-- the fire visibly covers the area it hurts.
local function breath(ctx)
 if ctx.dragonBreath then return end;ctx.dragonBreath=true
 local at,def=ctx.attack,ctx.def;local len=def.length or 20
 local m=ctx.points(def.point,math.max(C.age(ctx),at.impact));if not C.near(m,len) then return end
 local mouth=C.part('Host',Vector3.one*.6,CFrame.new(m),K.White,1)
 local far=C.part('Host',Vector3.new(9,.2,5),CFrame.new(m),K.White,1)
 local mid=C.part('Host',Vector3.one*.1,CFrame.new(m),K.White,1)
 C.fx(mouth,'Flame',{Rate=90,Speed={26,34},SpreadAngle=18,Lifetime={.55,.7},Size=ns({0,2},{.45,5},{1,7}),Color=cs({0,HOT},{.3,FLAME},{1,DEEP}),Transparency=ns({0,.35},{.12,0},{.75,.15},{1,1}),Drag=.4,Acceleration=Vector3.new(0,5,0),LightEmission=.75,Rotation={-30,30},RotSpeed={-40,40},ZOffset=.5})
 C.fx(mouth,'Flame',{Rate=60,Speed={30,36},SpreadAngle=7,Lifetime={.3,.42},Size=ns({0,1},{1,3.5}),Color={Color3.fromRGB(255,250,214),Color3.fromRGB(255,204,96)},Transparency=ns({0,.2},{.7,.3},{1,1}),LightEmission=1,Rotation={-20,20},ZOffset=1}) -- hot inner core
 C.fx(mouth,'Ember',{Rate=40,Speed={20,34},SpreadAngle=24,Lifetime={.7,1.1},Size=ns({0,.45},{1,0}),Color={HOT,EMBER},Drag=.8,Acceleration=Vector3.new(0,8,0),LightEmission=1})
 C.fx(far,'SmokePuff',{Rate=15,EmissionDirection=Enum.NormalId.Top,Speed={3,6},SpreadAngle=25,Lifetime={1,1.4},Size=ns({0,2.5},{1,6.5}),Color={SMOKE,Color3.fromRGB(40,36,34)},Transparency=ns({0,.6},{.2,.35},{1,1}),Acceleration=Vector3.new(0,2,0),LightInfluence=.6,Rotation={0,360},RotSpeed={-30,30}})
 C.fx(far,'Flame',{Rate=22,EmissionDirection=Enum.NormalId.Top,Speed={2,5},SpreadAngle=30,Lifetime={.4,.55},Size=ns({0,1.5},{.4,3.5},{1,2.5}),Color=cs({0,HOT},{.4,FLAME},{1,DEEP}),Transparency=ns({0,.3},{.2,0},{1,1}),LightEmission=.8,Rotation={-15,15}}) -- fire licking up where it lands
 local light=Instance.new('PointLight');light.Color=FLAME;light.Range=24;light.Brightness=3;light.Shadows=false;light.Parent=mid
 local s,sh=C.cue('fire_breath',m,.85,1,true)
 C.light(m,HOT,20,3,.25);C.shake(m,.35,.25)
 local nextMark=at.impact+.1
 C.follow(ctx,at.activeEnd,function(age)
  local p=ctx.points(def.point,age);local d=C.flat(ctx.dirAt(def.point,age));if d.Magnitude<.05 then d=C.flat(ctx.cf.LookVector) end;d=d.Unit
  local farPt=C.ground(ctx,p)+d*len*.85
  mouth.CFrame=C.aim(p,farPt+up*1.2-p);far.CFrame=CFrame.lookAt(farPt+up*.3,farPt+up*.3+d)
  mid.CFrame=CFrame.new((p+farPt)/2+up*1.5);light.Brightness=2.6+math.random()*.8
  if sh then sh.CFrame=CFrame.new(p) end
  if age>=nextMark then -- a scorch mark every 0.25 s where the flames land, fading over 4 s
   nextMark+=.25;local side=d:Cross(up)
   C.stain(farPt+side*(math.random()-.5)*6+d*(math.random()-.5)*3+up*.03,'ScorchMark',6+math.random()*2,Color3.new(1,1,1),.2,1.4,2.4,.08)
  end
 end,function() C.retire({mouth,far,mid},1.5);C.stopSound(s,sh,.25) end)
end

-- TailWhip --------------------------------------------------------------------------------
local function coil(ctx)
 local g=C.ground(ctx,ctx.cf.Position);if not C.near(g) then return end
 C.cue('dragon_windup',g,.8)
 for _,x in {-3,3} do local p=ctx.ground*Vector3.new(x,0,3.5);dust(Vector3.new(p.X,ctx.groundY+.4,p.Z),5) end -- under the hind feet
end
-- The spade's ember ribbon: a Trail between the outer half of the TailMid->SpadeTip span, on from
-- just before impact to the end of the sweep, then frozen so it fades where it finished.
local function tail(ctx)
 if ctx.dragonTail then return end;ctx.dragonTail=true
 local at,def=ctx.attack,ctx.def;local age0=C.age(ctx);local tip0=ctx.points(def.point,age0);if not C.near(tip0) then return end
 local a=C.part('Host',Vector3.one*.1,CFrame.new(ctx.points(def.mid,age0)),K.White,1)
 local b=C.part('Host',Vector3.one*.4,CFrame.new(tip0),K.White,1)
 local a0=Instance.new('Attachment');a0.Parent=a;local a1=Instance.new('Attachment');a1.Parent=b
 local tr=Instance.new('Trail');tr.Name='BossVfxTrail';tr.Attachment0=a0;tr.Attachment1=a1;tr.Lifetime=.25;tr.MinLength=.05;tr.FaceCamera=false;tr.LightEmission=.7;tr.LightInfluence=.2
 tr.Color=cs({0,HOT},{.4,EMBER},{1,Color3.fromRGB(150,40,20)});tr.Transparency=ns({0,.2},{.5,.55},{1,1});tr.WidthScale=ns({0,1},{1,.35});tr.Enabled=false;tr.Parent=a
 local sparks=C.fx(b,'Ember',{Rate=0,Enabled=true,Speed={4,9},SpreadAngle=180,Lifetime={.4,.7},Size=ns({0,.45},{1,0}),Color={HOT,EMBER},Drag=1.2,Acceleration=Vector3.new(0,6,0),LightEmission=1})
 local nextDust,lastTip=0,tip0
 C.follow(ctx,at.activeEnd+.3,function(age)
  if age>at.activeEnd+.04 then if sparks then sparks.Rate=0 end;return end
  local on=age>=at.impact-.06
  local mid,tip=ctx.points(def.mid,age),ctx.points(def.point,age);local along=tip-mid;local ext=along.Magnitude>.1 and along.Unit or Vector3.zero
  a.CFrame=CFrame.new(mid:Lerp(tip,.45));b.CFrame=CFrame.new(tip+ext*1.2);tr.Enabled=on;if sparks then sparks.Rate=on and 70 or 0 end
  if on and age>=nextDust and tip.Y-ctx.groundY<3.8 then -- the spade skims the ground: kick dust along its path
   nextDust=age+.045;local v=C.flat(tip-lastTip);dust(Vector3.new(tip.X,ctx.groundY+.4,tip.Z),2,(v.Magnitude>.01 and v.Unit or Vector3.zero)+up*.6,{5,9})
  end
  lastTip=tip
 end,function() C.retire({a,b},.5) end)
end
-- The crescent: a VfxKit ring over the server's sweep arc, revealed in the direction the tail
-- travels across the active window, then widening and fading.
local function whip(ctx)
 local at,def=ctx.attack,ctx.def;local tip=ctx.points(def.point,at.impact)
 C.shake(tip,.7,.3);if not C.near(tip) then return end
 C.cue('tail_whoosh',tip,.9)
 local s=C.shape(ctx);if not s or s.kind~='arc' then return end
 local base=Vector3.new(s.pivot.X,ctx.groundY+.12,s.pivot.Z);local frame=CFrame.lookAt(base,base+s.forward)
 local from,to=s.from,s.to
 if C.Shapes.yaw(s.forward,tip-s.pivot)>C.Shapes.yaw(s.forward,ctx.points(def.point,at.activeEnd)-s.pivot) then from,to=to,from end
 local outer,sweep=s.outer-1,math.max(.1,at.activeEnd-at.impact)
 K.ring(C.folder(),frame,{segments=36,from=from,to=to,radius0=outer,radius1=outer+1.5,width=math.clamp((outer-s.inner)*.5,3,7),reveal=sweep,duration=sweep+.4,hold=.06,color=EMBER,rim=HOT,bodyAlpha=.62})
end

-- FrontStomp ------------------------------------------------------------------------------
local function rear(ctx)
 local at,def=ctx.attack,ctx.def;local g=C.ground(ctx,ctx.cf.Position);if not C.near(g) then return end
 C.cue('dragon_windup',g,.9)
 local c=C.ground(ctx,ctx.points(def.point,at.impact))
 C.at(ctx,at.warnStart+.25,function() -- the wing flap pushes a ring of dust outward
  for i=1,8 do local a=i/8*math.pi*2;local out=Vector3.new(math.cos(a),0,math.sin(a));dust(g+out*6+up*.4,2,out+up*.25,{14,20}) end
 end)
 C.at(ctx,at.impact-.45,function() -- the ground heats under the landing: faint cracks and rising embers
  local p,set=C.plate(c+up*.04,'LavaCracks',14,COOL,nil,1.2)
  if p then K.animate(.5,function(t) set(1-.4*t,COOL:Lerp(EMBER,t)) end,function() p:Destroy() end,'bossPlate',64) end
  local h=C.part('Host',Vector3.new(12,.2,12),CFrame.new(c+up*.2),K.White,1)
  C.fx(h,'Ember',{emit=14,EmissionDirection=Enum.NormalId.Top,Speed={3,6},SpreadAngle=15,Lifetime={.5,.8},Size=ns({0,.4},{1,0}),Color={HOT,EMBER},LightEmission=1})
  C.retire({h},1)
 end)
end
local function stomp(ctx)
 local at,def=ctx.attack,ctx.def;local g=C.ground(ctx,ctx.points(def.point,at.impact))
 C.shake(g,1.4,.55);if not C.near(g) then return end
 C.cue('ground_quake',g,1);C.cue('lava_hiss',g,.6)
 C.star(g+up*2.5,HOT,13,.24);C.light(g+up*3,FLAME,30,4,.6)
 C.ring(g+up*.07,'ShockwaveRing',2,20,.35,Color3.fromRGB(255,176,96),0,true)
 -- Lava cracks: snap open, glow orange-yellow, cool to dark red over ~2 s, fade out by 3 s.
 local p,set=C.plate(g+up*.04,'LavaCracks',20,HOT,nil,2.2)
 if p then
  K.animate(3,function(t,age)
   local col=age<.25 and HOT or HOT:Lerp(COOL,K.smooth((age-.25)/1.9))
   local a=age<.08 and 1-age/.08 or t<.6 and 0 or K.smooth((t-.6)/.4)
   set(a,col,20*(age<.12 and .82+.18*age/.12 or 1),nil,2.2-1.4*K.smooth(age/2.2))
  end,function() p:Destroy() end,'bossPlate',64)
 end
 C.chunks(g+up*1.5,ctx.groundY,ROCKS,{count=6,speed={7,11},up={24,32},scale={1.4,1.9},life=1.5,trail={HOT,DEEP,.5},fallback=OBSIDIAN})
 C.emit(g+up*.5,up,'Ember',{emit=60,Speed={14,30},SpreadAngle=55,Lifetime={.7,1.3},Size=ns({0,.55},{1,0}),Color={HOT,EMBER},Acceleration=Vector3.new(0,-22,0),Drag=.8,LightEmission=1})
 C.emit(g+up*.6,up,'SmokePuff',{emit=10,Speed={12,16},SpreadAngle=85,Drag=3.5,Lifetime={1,1.4},Size=ns({0,2.5},{1,5.5}),Color={SMOKE,Color3.fromRGB(46,40,38)},Transparency=ns({0,.3},{.5,.45},{1,1}),LightInfluence=.6,Rotation={0,360},RotSpeed={-30,30}})
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
