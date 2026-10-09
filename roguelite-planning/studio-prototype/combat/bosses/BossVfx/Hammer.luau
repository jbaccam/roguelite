-- Hammer Brute effects (rebuild R5, 2026-10-03). Client-only; nothing here changes hits. Flat
-- stylized effects: Neon segments, painted kit textures tinted here, 4x4 flipbooks and ground
-- decals; no shaded effect meshes. The only meshes are the rubble wave's rocks, real props: the
-- kit's rock meshes with their texture cleared, recoloured flat dirt-brown and rock-grey.
-- Rubble wave (2026-10-09; the `wave` hook, MapBossPresentation 3c28997, for the Slam's and SpinSlam's
--   wave phases and the charge's finish wave): a line of rubble bursts races out from the slam along
--   each of the unit's lines (one, or the enraged fan of 3). Each burst heaves up out of the ground at
--   unit.impact + d/travel (the instant the server hit-tests that distance), knee-high by the hammer
--   (~1.9 studs) up to tall rocky heaps at the far end (~7.7 studs at 83), pops with an overshoot,
--   holds, cracks and sinks back with a dust puff. Each wave keeps its own server clock (unit.startTime,
--   else the attack's start + unit.impact), so it runs on after his attack ends, as the server's front
--   does; only his death or removal, a pause or a reset (RW.stops) end it early. RW below holds the pure
--   helpers (BossVfxHammerTests); H.rubbleWave(ctx, lines, travel, startAge, key) is the same by hand.
-- Slams (the Slam, a combo's circle phase, the charge's finish): dust gathers on the raised head and
--   a whoosh on the downswing; then a white snap ring out to the hit edge, a slower dust ring, an
--   impact star, dust and dirt thrown up, EarthCracks for ~2.5 s, and a shake that fades with distance.
-- Sweeps (Swing, Spin, a combo's sweep phases): a Neon crescent laid along the sampled HammerFace
--   track while it moves fast (a white rim on the outside, red once enraged), dust where it skims.
-- Charge: dust as he loads, a rumble and dust at every footfall while he runs, a skid streak and
--   dirt thrown forward where he stops, then the finish slam where the circle has moved to.
-- Follow-up cracks (followup / aftershock): each circle opens a crack decal that grows until it
--   erupts in a dirt burst.
-- Enrage (fired once, as the first roar starts): the eyes ignite red and stay, and steam keeps
--   rising off his head for the rest of the fight. Roar (each roar, a replayed one too): at its peak
--   a red roar ring, steam puffs and a shake.
-- Intro (fired at the landing): a landing ring, dust wall, cracks and shake (BossIntro.client has
--   the boom, its own shockwave and the camera).
-- Shapes and times come from the server's data (ctx.phases, C.phaseShape, C.shape, C.finish, the wave
-- unit), so what the effects mark is what hurts. Sounds: the game's small kit, pitch-shifted (BossVfxAssets).

-- Rubble wave: pure helpers (RW) -----------------------------------------------------------------
-- No instances, no clocks: the schedule along a line, each burst's pose over time and its heap of
-- chunks. In Edit this module returns only {rubble=RW} (tools/RepoRequire, BossVfxHammerTests and the
-- preview); RW.chunk/RW.place are the one builder the game and the preview share.
local RW={}
RW.TRAVEL,RW.LENGTH,RW.WIDTH=55,85,9 -- the slam wave phase (MapBossDefs) when the data has none
RW.NEAR,RW.FAR,RW.CURVE=1.7,8.1,1.15 -- peak height by the hammer and at the far end, and how it builds
RW.FIRST,RW.LAST=3,2 -- the first burst 3 studs out, the last 2 short of the end
RW.SPACING,RW.FAN_SPACING=5,5.6 -- studs between bursts: one line 17 bursts at 85, a fan line 15
RW.RISE,RW.SETTLE,RW.CRACK=.13,.24,.07 -- pop (to a 10% overshoot), settle, crack jolt (seconds)
RW.YAW=8 -- degrees a heap turns off its line at most
-- Workspace containers the ground ray never lands on (a heap must not sit on a zombie, pet or drop).
RW.EXCLUDE={'RogueliteEnemies','RoguelitePets','RogueliteTurrets','RogueliteChickens','RogueliteHeartDrops','RogueliteShardDrops'}
RW.DIRT={Color3.fromRGB(124,92,60),Color3.fromRGB(104,76,52),Color3.fromRGB(146,110,74)}
RW.ROCK={Color3.fromRGB(128,126,120),Color3.fromRGB(104,103,100),Color3.fromRGB(152,148,140)}
RW.DARK=Color3.fromRGB(86,62,42)
-- Kit rock meshes by role: chipped blocks for the upheaved slabs, hull rocks for the dirt.
RW.MESHES={slab={'SandstoneRubble_B','SandstoneRubble_A','MoltenRock_C'},lump={'MoltenRock_C','MoltenRock_B'},
 side={'SandstoneRubble_A','MoltenRock_B','SandstoneRubble_B'},clod={'MoltenRock_B','MoltenRock_A'},bit={'ShellChip_C','MoltenRock_A','ShellChip_B'}}
local function smooth(t) t=math.clamp(t,0,1);return t*t*(3-2*t) end
-- Peak height at d studs along a line `length` long: 1.7 by the hammer, building to 8.1 at the end.
function RW.height(d,length) local f=math.clamp(d/math.max(length,1),0,1);return RW.NEAR+(RW.FAR-RW.NEAR)*f^RW.CURVE end
-- A heap's footprint half-width: wider as it grows, never past 90% of the lane's half-width.
function RW.radius(h,halfW) return math.min(halfW*.9,.9+.45*h) end
-- The bursts along one line: {index, d, at, h, f, seed, sign, yaw, slack}, in order. `at` is
-- startAge + d/travel, when the server's front (MapBossService X.waveHit) reaches d. A little
-- unevenness in spacing and height (seeded), never out of order.
function RW.schedule(length,travel,startAge,fan,seed)
 local rng=Random.new(seed or 1);local list={}
 local span=length-RW.FIRST-RW.LAST
 local n=span>0 and math.max(2,math.floor(span/(fan and RW.FAN_SPACING or RW.SPACING)+.5)+1) or 1
 local step=n>1 and span/(n-1) or 0;local jitter=math.clamp((6-step)/2,0,.3) -- gaps stay within 4-6 studs
 for i=1,n do
  local d=n>1 and RW.FIRST+step*(i-1) or length*.5
  if i>1 and i<n then d+=(rng:NextNumber()*2-1)*jitter end
  list[i]={index=i,d=d,at=startAge+d/travel,h=RW.height(d,length)*(.95+.1*rng:NextNumber()),f=math.clamp(d/length,0,1),
   seed=rng:NextInteger(1,2^30),sign=i%2==0 and 1 or -1,yaw=math.rad(rng:NextNumber(-RW.YAW,RW.YAW)),slack=rng:NextNumber()}
 end
 return list
end
-- A burst's sideways offset from the line (a slight zig-zag), keeping its heap inside the lane.
function RW.offset(b,halfW) return b.sign*b.slack*math.min(.6,math.max(0,halfW*.95-RW.radius(b.h,halfW))) end
-- When a burst (f: its share of the line) starts cracking, and when it is gone under the ground.
function RW.times(f) local hold=.58+.12*f;return hold,hold+RW.CRACK+.38+.14*f end
-- A burst `since` seconds after it rises: lift (0 buried, 1 at rest, 1.1 the overshoot), scale, crack
-- (how far its chunks have tipped: 0 to 1 in the crack, on to 1.8 as it sinks) and the phase name.
function RW.pose(since,f)
 local hold,gone=RW.times(f)
 if since<0 then return 0,.7,0,'wait' end
 if since<RW.RISE then local k=since/RW.RISE;return 1.1*(1-(1-k)^3),.7+.3*k,0,'rise' end
 if since<RW.SETTLE then return 1.1-.1*smooth((since-RW.RISE)/(RW.SETTLE-RW.RISE)),1,0,'settle' end
 if since<hold then return 1,1,0,'hold' end
 if since<hold+RW.CRACK then local k=(since-hold)/RW.CRACK;return 1-.04*k,1,k,'crack' end
 if since<gone then local k=(since-hold-RW.CRACK)/(gone-hold-RW.CRACK);return .96*(1-k*k),1,1+.8*k,'sink' end
 return 0,1,1.8,'gone'
end
-- Most chunks per heap: one line 6 (Low 5); each line of the fan 4 (Low 3). quality: ClientQuality's
-- effects share (Low .35, Balanced .65, Full 1).
function RW.chunkCap(fan,quality)
 if not fan then return quality<.5 and 5 or 6 end
 return quality<.5 and 3 or 4
end
-- Debris bits tumbling off a heap: at its peak (heaps from 4 studs) and as it cracks (from 6). A fan's
-- side lines only shed at the crack; Low only the 6-stud heaps, once.
function RW.bits(h,fan,main,quality)
 local peak,crack=h>=4 and 1 or 0,h>=6 and 1 or 0
 if quality<.5 then peak,crack=h>=6 and 1 or 0,0 end
 if fan and not main then peak=0 end
 return peak,crack
end
-- Most debris bits in the air at once for a wave (Low 10, else 24).
function RW.maxBits(quality) return quality<.5 and 10 or 24 end
-- Whether a wave stops early: its boss gone (removed, dying, at 0 health) or the run paused or reset
-- (ZombiesEnabled off). s: {parented, dying, health (nil without a Humanoid), paused, zombies}. The
-- attack ending is not a reason: the server's front runs on to the end of its line.
function RW.stops(s)
 return not s.parented or s.dying==true or (type(s.health)=='number' and s.health<=0) or s.paused==true or s.zombies~=true
end
-- One heap at peak height h, in the burst's frame (ground point, Y up, -Z the way the wave travels):
-- a list of {name, color, size, rot, pos, crack, top, bottom, hx, hz (half-extents across, along)}. A
-- rock slab leaning forward makes the peak, on a wide dirt mound; side slabs lean out, and bigger heaps
-- add a dirt lip in front and a clod behind. Each chunk reaches its `top` and is sunk past its foot, so
-- none floats; none leaves halfW (RW.heap also fits the heap's turn off its line).
function RW.layout(h,halfW,cap,rng)
 local r=RW.radius(h,halfW);local list={}
 local function roll(a,b) return a+(b-a)*rng:NextNumber() end
 local function pick(t) return t[rng:NextInteger(1,#t)] end
 local function add(name,color,sx,sz,rot,x,z,top)
  -- Grow the height until the box reaches below the ground by `bury` (deep enough that the pop's
  -- overshoot never lifts a foot out), then stand it on its top. A chunk turned wider than the lane
  -- is narrowed; one off to the side is moved in.
  local R,U,L=rot.RightVector,rot.UpVector,rot.LookVector
  local bury=.2+.2*top+.1*h;local sy,v,hx,hz
  local function measure()
   sy=math.max(.3,(top+bury-math.abs(R.Y)*sx-math.abs(L.Y)*sz)/math.max(.25,math.abs(U.Y)))
   v=math.abs(R.Y)*sx+math.abs(U.Y)*sy+math.abs(L.Y)*sz
   hx=(math.abs(R.X)*sx+math.abs(U.X)*sy+math.abs(L.X)*sz)/2
   hz=(math.abs(R.Z)*sx+math.abs(U.Z)*sy+math.abs(L.Z)*sz)/2
  end
  measure()
  for _=1,4 do
   if hx<=halfW then break end
   local k=math.max(.4,(halfW-math.abs(U.X)*sy/2)/math.max(1e-3,(math.abs(R.X)*sx+math.abs(L.X)*sz)/2))*.98;sx,sz=sx*k,sz*k;measure()
  end
  if math.abs(x)+hx>halfW then x=math.sign(x)*math.max(0,halfW-hx) end
  table.insert(list,{name=name,color=color,size=Vector3.new(sx,sy,sz),rot=rot,pos=Vector3.new(x,top-v/2,z),
   crack=Vector2.new(math.rad(roll(-7,7)),math.rad(roll(-7,7))),top=top,bottom=top-v,hx=hx,hz=hz})
 end
 local lean=math.rad(roll(10,20))
 -- The peak: a rock slab leaning forward, set a little back so its top is over the middle.
 add(pick(RW.MESHES.slab),pick(RW.ROCK),r*roll(1.1,1.35),r*roll(.75,.95),
  CFrame.Angles(0,math.rad(roll(-20,20)),0)*CFrame.Angles(-lean,0,math.rad(roll(-10,10))),r*roll(-.15,.15),r*.12,h*1.04)
 -- The heaved dirt underneath.
 add(pick(RW.MESHES.lump),pick(RW.DIRT),r*roll(1.7,1.95),r*roll(1.3,1.6),
  CFrame.Angles(0,math.rad(roll(0,360)),0)*CFrame.Angles(math.rad(roll(-6,6)),0,math.rad(roll(-6,6))),r*roll(-.1,.1),r*roll(-.15,.1),h*roll(.36,.46))
 -- Side slabs leaning outward (one on small heaps), rock or dirt.
 local sides=(cap>=4 and h>=2.6) and 2 or 1;local first=rng:NextNumber()<.5 and -1 or 1
 for i=1,math.min(sides,cap-2) do
  local s=i==1 and first or -first
  add(pick(RW.MESHES.side),rng:NextNumber()<.55 and pick(RW.ROCK) or pick(RW.DIRT),r*roll(.65,.85),r*roll(.5,.7),
   CFrame.Angles(0,math.rad(roll(-25,25)),0)*CFrame.Angles(-lean*.5,0,-s*math.rad(roll(15,30))),s*r*roll(.5,.65),r*roll(-.25,.3),h*roll(.5,.72))
 end
 -- A dirt lip thrown forward in front of the bigger heaps, and a clod behind the biggest.
 if cap>=5 and h>=4.5 then
  add(pick(RW.MESHES.lump),pick(RW.DIRT),r*roll(1.1,1.4),r*roll(.5,.65),
   CFrame.Angles(0,math.rad(roll(-20,20)),0)*CFrame.Angles(-math.rad(roll(25,35)),0,0),r*roll(-.2,.2),-r*roll(.65,.8),h*roll(.3,.4))
 end
 if cap>=6 and h>=6 then
  add(pick(RW.MESHES.clod),RW.DARK,r*roll(.75,.9),r*roll(.6,.75),
   CFrame.Angles(math.rad(roll(-15,15)),math.rad(roll(0,360)),math.rad(roll(-15,15))),r*roll(-.3,.3),r*roll(.6,.75),h*roll(.25,.33))
 end
 return list
end
-- How far a heap reaches across its line: its chunks turned `yaw` off the line and set `side` across
-- it (an upper bound from each chunk's half-extents).
function RW.reach(specs,yaw,side)
 local c,s=math.abs(math.cos(yaw)),math.abs(math.sin(yaw));local m=0
 for _,sp in specs do m=math.max(m,math.abs(side)+(math.abs(sp.pos.X)+sp.hx)*c+(math.abs(sp.pos.Z)+sp.hz)*s) end
 return m
end
-- A burst's heap (b from RW.schedule, b.side its offset): RW.layout narrowed until, turned b.yaw and
-- set b.side across, no chunk reaches past halfW from the line, so it stays inside the warned lane.
function RW.heap(b,halfW,cap)
 local hw=halfW-math.abs(b.side);local specs
 for _=1,5 do
  specs=RW.layout(b.h,hw,cap,Random.new(b.seed))
  local over=RW.reach(specs,b.yaw,b.side)-halfW
  if over<=0 then break end
  hw=math.max(.5,hw-over-.02)
 end
 return specs
end
-- A chunk's frame: `base` is the burst frame (moved down while it is buried), scale its pop, k its crack.
function RW.frameOf(spec,base,scale,k)
 k=k or 0;return base*CFrame.new(spec.pos*(scale or 1))*CFrame.Angles(spec.crack.X*k,0,spec.crack.Y*k)*spec.rot
end
-- A new chunk (unparented): the kit rock `name` from templates (BossVfxAssets) with its texture and
-- children cleared, matte; a plain block when the template is missing.
function RW.chunk(templates,name)
 local t=templates and templates:FindFirstChild(name);local p=t and t:IsA('MeshPart') and t:Clone() or nil -- nil: not Archivable
 if p then p:ClearAllChildren();p.TextureID=''
 else p=Instance.new('Part');p.TopSurface=Enum.SurfaceType.Smooth;p.BottomSurface=Enum.SurfaceType.Smooth end
 p.Name='BossVfxRubble';p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false
 p.Material=Enum.Material.Plastic;p.Reflectance=0;p.Transparency=0
 return p
end
-- A chunk dressed and placed at a pose.
function RW.place(p,spec,base,scale,k) p.Color=spec.color;p.Size=spec.size*(scale or 1);p.CFrame=RW.frameOf(spec,base,scale,k);return p end
if not game:GetService('RunService'):IsRunning() then return {rubble=RW} end -- Edit: the helpers only

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
-- Where a circle lands: the server's shape, read as it lands (an aimed attack has turned since it was
-- published; C.shape and C.phaseShape turn it to the frame now), else the sampled head on the ground.
local function slamAt(ctx,u,big)
 local shape=ctx.phases and C.phaseShape(ctx,u.key) or not ctx.phases and C.shape(ctx) or nil
 local c=shape and shape.kind=='circle' and shape.center or groundAt(ctx,ctx.points(u.point or POINT,u.impact))
 slam(ctx,c,(shape and shape.radius) or u.radius or 9.5,big)
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
  -- A piece per 1.2 studs of head travel, not per frame: the same crescent at 60 and 240 fps.
  if dt<=1e-4 or step.Magnitude<1.2*s then return end
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
-- from where the hit before it ended (its wind-up is too slow to draw). A wave phase rides the slam it
-- comes with, so it doesn't move that `from` on.
local function units(ctx)
 local list={}
 if ctx.phases then
  local prev=0
  for i,ph in ctx.phases do
   table.insert(list,{key=i,kind=ph.def.shape,from=prev,impact=ph.impact,to=ph.activeEnd,radius=ph.def.radius,point=ph.def.point,def=ph.def})
   if ph.def.shape~='wave' then prev=ph.activeEnd end
  end
 else
  local at=ctx.attack
  list[1]={key=1,kind=ctx.def.shape,from=at.warnStart or 0,impact=at.impact,to=at.activeEnd,radius=ctx.def.radius,point=ctx.def.point,def=ctx.def}
 end
 return list
end
local function plan(ctx)
 if ctx.hammerPlanned then return end;ctx.hammerPlanned=true
 for _,u in units(ctx) do
  -- A combo's slam winds up once the hit before it is over (u.from).
  if u.kind=='circle' then C.at(ctx,u.from,function() slamWindup(ctx,u.impact) end);C.at(ctx,u.impact,function() slamAt(ctx,u,false) end)
  elseif u.kind=='sweep' then crescent(ctx,u.from,u.to,u.key) end -- a wave phase: the wave hook (H.wave)
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
-- From the launch to the finish slam. The run ends only at the server's stop (the presentation's
-- ctx.charge.stopAge, from data.stoppedAt; nil while he runs), so footfalls carry on until then and
-- the skid lands where the run ends (a homing run's ctx.charge.endPos, else the final length down the
-- lane). Footfalls follow the replicated body, which is where the player sees him: the ground it has
-- covered (a homing run curves), on his current heading.
local function charge(ctx)
 if ctx.hammerCharge or not ctx.charge then return end;ctx.hammerCharge=true
 local ch,def=ctx.charge,ctx.def;local s=ctx.scale or 1
 local start=groundAt(ctx,ctx.cf.Position)
 local stride=ctx.timing.chargeStrideLength or def.speed*.53;local half=math.max(1,stride/2)
 local root0=ctx.npc.PrimaryPart;local last=root0 and root0.Position;local covered=0
 local function travelled(age)
  local root=ctx.npc.PrimaryPart
  if root then
   local step=last and C.flat(root.Position-last).Magnitude or 0;last=root.Position
   if step<20 then covered+=step end -- a streamed-in jump is not ground covered
   return covered
  end
  return math.clamp((age-ctx.attack.impact)*def.speed,0,ch.stopAge and ch.length or def.length or 75)
 end
 local nextStep,side,stopped,slammed=half*.5,1,false,false
 local snd,sh=C.cue('stone_rumble',start,.45,1.15,true)
 local slamFinish=(ctx.timing.clips and ctx.timing.clips[def.clips[3]] or 1.5)/(def.rate or 1)
 local maxAge=ctx.attack.impact+(def.length or 75)/def.speed+.75+slamFinish+.5 -- .75: the client's hold for the stop
 C.follow(ctx,maxAge,function(age)
  local travel=travelled(age);local dir=ch.heading or ch.dir
  local root=ctx.npc.PrimaryPart;local floorY=root and root.Position.Y-ctx.timing.rootHeight or ctx.groundY
  local pos=root and Vector3.new(root.Position.X,floorY,root.Position.Z) or Vector3.new(start.X,floorY,start.Z)+ch.dir*travel
  if sh then sh.CFrame=CFrame.new(pos+up*2) end
  if not stopped then
   -- A footfall every half stride, alternating feet: dust kicked back and a small thump.
   while travel>=nextStep do
    local f=pos+dir:Cross(up)*side*1.6*s
    if C.near(f) then dust(f+up*.3,-dir+up*.6,3,{5,9},3.5*s,40) end
    C.shake(f,.3,.12);C.cue('hammer_thud',f,.3,.55);side=-side;nextStep+=half
   end
   if ch.stopAge and age>=ch.stopAge then
    stopped=true;C.stopSound(snd,sh,.15)
    local e=ch.endPos or start+ch.dir*ch.length;skid(ctx,Vector3.new(e.X,floorY,e.Z),dir)
   end
  end
  if stopped and not ch.finishImpact then return true end
  if ch.finishImpact and not slammed and age>=ch.finishImpact-.22 and not ctx.hammerWhoosh then ctx.hammerWhoosh=true;C.cue('hammer_whoosh',pos,.7,.62) end
  if ch.finishImpact and not slammed and age>=ch.finishImpact then
   slammed=true;local f=ch.finish;if f then slam(ctx,f.center,f.radius,true) end;return true
  end
 end,function() C.stopSound(snd,sh,.15) end)
end

-- Rubble wave -----------------------------------------------------------------------------------
-- One controller per wave (all of its fan lines) on the attack clock. Each burst rises at its `at`,
-- so a late start catches up to the right pose and a burst already past its life never appears.
-- Chunks come from a pool of kit rocks; one K.animate owns every chunk, ground plate, dust host and
-- debris bit, and its cleanup returns them all, however it ends (done, evicted by its budget, or the
-- boss gone). It stops early, nothing new rising and whatever stands sinking in 0.3 s, when the boss
-- dies or is removed, the run pauses, or (while the front still travels) the attack is cancelled or
-- reset (C.live). Once the front has reached the end the server's hits are done, so his next attack
-- doesn't cut the last heaps short.
local combat=script.Parent.Parent
local Q=require(combat:WaitForChild('ClientQuality'))
local Players=game:GetService('Players')
local pool,pooled,POOL_MAX={},0,240
local function take(name)
 local list=pool[name];local p=list and table.remove(list)
 if p then pooled-=1;return p end
 return RW.chunk(combat:FindFirstChild('BossVfxAssets'),name)
end
local function give(p,name)
 if p.Parent==C.folder() and pooled<POOL_MAX then p.Parent=nil;pool[name]=pool[name] or {};table.insert(pool[name],p);pooled+=1
 else p:Destroy() end
end
-- Dust and thrown dirt for 4 heap sizes on each line: one host per size and line (at most 12), moved
-- to each burst before it emits (particles stay where they were born), not a host per burst. Per line,
-- so the fan's three same-frame bursts don't all emit from the last one's spot.
local function dustHost(W,b)
 local band=math.clamp(math.floor(b.f*4)+1,1,4);local key=(b.line-1)*4+band
 local e=W.hosts[key];if e then return e end
 local r=RW.radius(RW.height((band-.5)/4*W.length,W.length),W.halfW);local s=.7+.15*band
 local host=C.part('Host',Vector3.new(r*1.5,.2,r*1.5),CFrame.new(W.mid),K.White,1)
 e={host=host,
  dust=C.fx(host,'DustPuff',{Rate=0,Shape=Enum.ParticleEmitterShape.Box,EmissionDirection=Enum.NormalId.Top,Speed={3,7},SpreadAngle=75,Lifetime={.6,.95},Drag=2.5,Size=ns({0,r*.5},{1,r*1.15}),Color=DUST,Transparency=ns({0,.25},{.6,.5},{1,1}),Acceleration=Vector3.new(0,1.5,0),LightInfluence=.8,Rotation={0,360},RotSpeed={-40,40}}),
  dirt=C.fx(host,'SandSpray',{Rate=0,Shape=Enum.ParticleEmitterShape.Box,EmissionDirection=Enum.NormalId.Top,Speed={8+band*2,14+band*3},SpreadAngle=35,Lifetime={.4,.65},Size=ns({0,s},{1,s*2.2}),Color=DIRT,Transparency=ns({0,0},{.7,.2},{1,1}),Acceleration=Vector3.new(0,-50,0),Drag=.8,Rotation={-40,40},LightInfluence=.8})}
 W.hosts[key]=e;return e
end
local function puff(W,b,dust,dirt)
 local e=dustHost(W,b)
 e.host.CFrame=CFrame.new(b.ground+up*.3)*CFrame.Angles(0,b.yaw,0)
 if e.dust and dust>0 then e.dust:Emit(dust) end;if e.dirt and dirt>0 then e.dirt:Emit(dirt) end
end
-- Small bits knocked off the top of a heap: they arc out sideways and ahead, bounce once and shrink.
-- t: the wave's clock.
local function shed(W,b,n,t)
 for _=1,n do
  if #W.bits>=W.maxBits then return end
  local name=RW.MESHES.bit[math.random(#RW.MESHES.bit)];local tpl=C.template(name)
  local base=tpl and tpl.Size or Vector3.new(1,.8,.6);local a=.55+.55*math.random()+.4*b.f
  local size=base/math.max(base.X,base.Y,base.Z)*a
  local s=math.random()<.5 and -1 or 1;local cf=b.frame
  local out=cf.RightVector*s*(.6+.6*math.random())+cf.LookVector*(.3+.5*math.random())
  local pos=cf*Vector3.new(s*b.r*.3,b.h*(.65+.2*math.random()),0)
  local rot=CFrame.Angles(math.random()*6.28,math.random()*6.28,math.random()*6.28)
  local p=take(name);p.Color=math.random()<.5 and RW.ROCK[math.random(#RW.ROCK)] or RW.DIRT[math.random(#RW.DIRT)];p.Size=size;p.CFrame=CFrame.new(pos)*rot;p.Parent=C.folder()
  table.insert(W.bits,{part=p,name=name,pos=pos,v=out.Unit*(5+4*math.random())+up*(7+5*math.random()),rot=rot,size=size,half=a*.3,g=b.ground.Y,born=t,
   spin=Vector3.new(math.random()-.5,math.random()-.5,math.random()-.5)*14})
 end
end
-- A burst heaves up: its ground (a short ray from 4 above the line's ground to 6 below, past enemies,
-- pets, drops and players), its heap from the pool at the pose for `since`, a torn-earth plate, and
-- when fresh its dust, dirt, shake and crunch. Where the ground drops away more than 6 studs it is
-- skipped rather than left floating (a miss before any burst found ground means the floor can't be
-- hit at all: then the line's own height).
local function spawn(W,b,since)
 local p=b.origin+b.dir*b.d+b.dir:Cross(up)*b.side
 if not C.near(p,b.h+6) then b.done=true;return end
 local hit=workspace:Raycast(Vector3.new(p.X,b.origin.Y+4,p.Z),Vector3.new(0,-10,0),W.params)
 if not hit and W.groundSeen then b.done=true;return end
 W.groundSeen=W.groundSeen or hit~=nil
 local g=Vector3.new(p.X,hit and hit.Position.Y or b.origin.Y,p.Z)
 b.ground=g;b.frame=CFrame.lookAt(g,g+b.dir)*CFrame.Angles(0,b.yaw,0)
 b.specs=RW.heap(b,b.halfW,W.cap);b.r=RW.radius(b.h,b.halfW-math.abs(b.side))
 local top=0;for _,s in b.specs do top=math.max(top,s.top) end;b.depth=top*1.12+.3
 local lift,scale,crack=RW.pose(since,b.f);local base=b.frame*CFrame.new(0,-(1-lift)*b.depth,0)
 b.parts,b.scale={},scale
 for i,s in b.specs do local part=RW.place(take(s.name),s,base,scale,crack);part.Parent=C.folder();b.parts[i]=part end
 if not W.low or (b.index%2==1 and (b.main or not W.fan)) then
  local plate,set=C.plate(g+up*.03,'ScorchMark',b.r*2.5,RW.DARK,nil,false);if plate then b.plate,b.setPlate,b.plateA=plate,set,1;set(1) end
 end
 if since<.15 then
  puff(W,b,2+math.floor(b.f*2.5+.5),3+math.floor(b.f*4));C.shake(g,.16+.45*b.f,.15)
  -- A crunch every other burst of the middle line (higher and lighter by the hammer), a thump under the big ones.
  if b.main and (b.index%2==1 or b.f>.7) then C.cue('sand_burst',g,.22+.3*b.f,1.35-.5*b.f) end
  if b.main and b.f>=.8 then C.cue('hammer_thud',g,.4,.6) end
 end
end
local function release(b)
 if not b.parts then return end
 for i,s in b.specs do if b.parts[i] then give(b.parts[i],s.name) end end
 b.parts=nil
end
-- One frame of a standing burst: its pose (or, stopped, a 0.3 s sink), moved in one BulkMoveTo; the
-- debris, crack and sink puff as it passes them. A holding heap isn't touched. t: the wave's clock.
local function stepBurst(W,b,t,since,parts,cfs)
 local lift,scale,crack,phase
 if W.stopAt then
  b.stopLift=b.stopLift or b.lift or 0
  local k=math.clamp((t-W.stopAt)/.3,0,1);lift,scale,crack,phase=b.stopLift*(1-k*k),b.scale,b.crack or 0,k>=1 and 'gone' or 'stop'
 else lift,scale,crack,phase=RW.pose(since,b.f) end
 if phase=='gone' then release(b);b.released=true;return end
 b.lift,b.crack=lift,crack
 if phase=='hold' and b.still then return end
 b.still=phase=='hold'
 if scale~=b.scale then b.scale=scale;for i,s in b.specs do b.parts[i].Size=s.size*scale end end
 local base=b.frame*CFrame.new(0,-(1-lift)*b.depth,0)
 for i,s in b.specs do table.insert(parts,b.parts[i]);table.insert(cfs,RW.frameOf(s,base,scale,crack)) end
 if W.stopAt then return end
 -- Each moment once, and only near when it happens (a late catch-up skips what it missed).
 local hold=RW.times(b.f)
 if not b.peaked and since>=RW.RISE then b.peaked=true;if since<RW.RISE+.2 then shed(W,b,b.peakBits,t) end end
 if not b.cracked and (phase=='crack' or phase=='sink') then
  b.cracked=true
  if since<hold+.2 then
   shed(W,b,b.crackBits,t)
   if b.main and b.last then C.cue('ice_wave',b.ground,.45,1.1) end -- the far heaps come down
  end
 end
 if not b.sinking and phase=='sink' then b.sinking=true;if since<hold+RW.CRACK+.25 then puff(W,b,2+math.floor(b.f*2+.5),0) end end
end
-- RW.stops for this boss now: only his own state and the run's pause or reset, never the attack
-- window (a wave runs on after his attack ends, as the server's front does).
local function ended(ctx)
 local npc=ctx.npc;local h=npc:FindFirstChildOfClass('Humanoid')
 return RW.stops({parented=npc.Parent~=nil,dying=npc:GetAttribute('BossDeathStart')~=nil,health=h and h.Health or nil,
  paused=combat:GetAttribute('RunPaused')==true,zombies=combat:GetAttribute('ZombiesEnabled')==true})
end
-- The controller. lines: the wave's line shapes ({kind='line', origin (on the ground), direction, length,
-- width}, decoded or as MapBossAttackData encodes them), in the frame the boss has now; one, or the
-- enraged fan (the middle one carries the sounds). travel: studs/s (nil: 55). startAge: the attack-clock
-- time the front leaves each origin (the wave's impact). key: once per attack and key. t0 (optional):
-- that moment as a server time (workspace:GetServerTimeNow()); without it, ctx.start + startAge. The
-- wave keeps its own clock from there, so it outlives the attack.
local function rubbleWave(ctx,lines,travel,startAge,key,t0)
 key=key or 'wave';ctx.hammerRubble=ctx.hammerRubble or {}
 if type(t0)~='number' then t0=type(startAge)=='number' and type(ctx.start)=='number' and ctx.start+startAge or nil end
 if ctx.hammerRubble[key] or type(lines)~='table' or #lines==0 or not t0 then return end
 ctx.hammerRubble[key]=true
 travel=type(travel)=='number' and travel>0 and travel or RW.TRAVEL
 local q=Q.get().effects;local fan=#lines>1;local main=math.ceil(#lines/2)
 local W={bursts={},bits={},hosts={},travel=travel,t0=t0,fan=fan,low=q<.5,cap=RW.chunkCap(fan,q),maxBits=RW.maxBits(q),length=0,halfW=RW.WIDTH/2,frontEnd=0}
 -- The ground ray's exclusions, once per wave.
 local exclude={C.folder(),ctx.npc}
 for _,name in RW.EXCLUDE do local f=workspace:FindFirstChild(name);if f then table.insert(exclude,f) end end
 for _,pl in Players:GetPlayers() do if pl.Character then table.insert(exclude,pl.Character) end end
 W.params=RaycastParams.new();W.params.FilterType=Enum.RaycastFilterType.Exclude;W.params.IgnoreWater=true;W.params.FilterDescendantsInstances=exclude
 local seed=math.random(1,2^24);local lastGone=0
 for li,line in lines do
  if typeof(line.origin)~='Vector3' then line=C.Shapes.decode(line) end
  local dir=typeof(line.direction)=='Vector3' and C.flat(line.direction) or Vector3.zero;local length=line.length or RW.LENGTH
  if typeof(line.origin)~='Vector3' or dir.Magnitude<1e-3 or length<=0 then continue end
  dir=dir.Unit
  -- On the ground the server measured it from (a charge's finish can be off his start's height).
  local origin=line.origin;local halfW=(line.width or RW.WIDTH)/2
  if li==main or W.length==0 then W.length,W.halfW,W.mid,W.mainOrigin,W.mainDir=length,halfW,origin+dir*length/2,origin,dir end
  W.frontEnd=math.max(W.frontEnd,length/travel)
  if C.near(origin+dir*length/2,length/2+10) then
   local list=RW.schedule(length,travel,0,fan,seed+li*7919)
   for _,b in list do
    b.line,b.origin,b.dir,b.halfW,b.main,b.last=li,origin,dir,halfW,li==main,b.index==#list
    b.side=RW.offset(b,halfW);local _,gone=RW.times(b.f);b.gone=gone
    b.peakBits,b.crackBits=RW.bits(b.h,fan,b.main,q)
    lastGone=math.max(lastGone,b.at+gone)
    table.insert(W.bursts,b)
   end
  end
 end
 if #W.bursts==0 then return end
 W.lingerUntil=lastGone+1.1 -- the last sink puff's dust
 local t1=workspace:GetServerTimeNow()-W.t0
 -- A rumble that rides the middle line's front until it reaches the end.
 if t1<W.frontEnd-.2 then W.rumble,W.rumbleHost=C.cue('stone_rumble',W.mainOrigin+up*2,.5,1.2,true) end
 K.animate(math.max(.5,W.lingerUntil-t1)+1,function()
  local t=workspace:GetServerTimeNow()-W.t0;local dt=math.clamp(t-(W.lastT or t),0,.05);W.lastT=t
  if not W.stopAt and ended(ctx) then W.stopAt=t end
  local parts,cfs,busy={},{},false
  for _,b in W.bursts do
   if b.done then continue end
   local since=t-b.at
   if b.parts==nil and not b.released then
    if W.stopAt or since>=b.gone then b.done=true;continue end
    if since<0 then busy=true;continue end
    spawn(W,b,since);if b.done then continue end
   end
   if b.parts then stepBurst(W,b,t,since,parts,cfs) end
   if b.plate then
    local a=since<.12 and 1-.6*math.max(0,since)/.12 or since<b.gone-.15 and .4 or .4+.6*smooth((since-b.gone+.15)/.75)
    if W.stopAt then a=math.max(a,smooth((t-W.stopAt)/.4)) end
    if a>=.999 and since>.12 then b.plate:Destroy();b.plate=nil
    elseif a~=b.plateA then b.plateA=a;b.setPlate(a) end
   end
   if b.released and not b.plate then b.done=true else busy=true end
  end
  for i=#W.bits,1,-1 do
   local c=W.bits[i];local age=t-c.born
   if age>=1.1 then give(c.part,c.name);table.remove(W.bits,i)
   else
    if not c.rest then
     c.v-=up*70*dt;c.pos+=c.v*dt;c.rot*=CFrame.Angles(c.spin.X*dt,c.spin.Y*dt,c.spin.Z*dt)
     if c.pos.Y<c.g+c.half and c.v.Y<0 then
      if c.v.Y<-6 and not c.bounced then c.bounced=true;c.v=Vector3.new(c.v.X*.45,-c.v.Y*.3,c.v.Z*.45);c.spin*=.5 else c.rest=true end
      c.pos=Vector3.new(c.pos.X,c.g+c.half,c.pos.Z)
     end
    end
    if age>.8 then c.part.Size=c.size*math.max(.05,1-smooth((age-.8)/.3)) end
    table.insert(parts,c.part);table.insert(cfs,CFrame.new(c.pos)*c.rot)
   end
  end
  if #parts>0 then workspace:BulkMoveTo(parts,cfs,Enum.BulkMoveMode.FireCFrameChanged) end
  if W.rumble then
   if W.stopAt or t>=W.frontEnd+.15 then C.stopSound(W.rumble,W.rumbleHost,.35);W.rumble=nil
   elseif W.rumbleHost.Parent then W.rumbleHost.CFrame=CFrame.new(W.mainOrigin+W.mainDir*math.clamp(t*W.travel,0,W.length)+up*2) end
  end
  return not busy and #W.bits==0 and t>=(W.stopAt and math.min(W.lingerUntil,W.stopAt+1) or W.lingerUntil)
 end,function()
  for _,b in W.bursts do
   release(b)
   if b.plate then b.plate:Destroy();b.plate=nil end
  end
  for _,c in W.bits do if c.part then give(c.part,c.name) end end;table.clear(W.bits)
  for _,e in W.hosts do e.host:Destroy() end
  if W.rumble then C.stopSound(W.rumble,W.rumbleHost,.2);W.rumble=nil end
 end,'bossRubble',6) -- 6: Low quality (x.35) still keeps 2 waves at once
end
-- The wave hook (MapBossPresentation stepWaves): once per wave as its front leaves the impact point.
-- unit = {key, def (length, width, travel), impact (attack clock), lines (decoded, turned to his frame
-- now / moved to where the charge ends), finish, startTime (optional: the server time the front left)}:
-- the Slam's and SpinSlam's wave phases and the charge's finish waves alike.
function H.wave(ctx,unit)
 if type(unit)~='table' then return end
 rubbleWave(ctx,unit.lines,unit.def and unit.def.travel,unit.impact,unit.key,unit.startTime)
end
H.rubble=RW
H.rubbleWave=rubbleWave

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
   local h=C.host(p+up*.3,life+1.4,up) -- outlives the 0.8 s retire below
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
local function headOffset(T) T=T or {};return ((T.height or 13.7)-(T.rootHeight or 4))*.88 end
-- The roar's peak: a red roar ring, a star, steam off his head and shoulders, the roar and a shake.
local function roarPeak(npc,scale,T)
 local root=npc.PrimaryPart;if not root then return end
 local r=6*(scale or 1);local p=root.Position;local head=p+up*headOffset(T);local y=C.feet(npc);local g=Vector3.new(p.X,y or p.Y-((T and T.rootHeight) or 4),p.Z)
 C.shake(p,1.5,.7);if not C.near(p,40) then return end
 C.cue('zombie_roar',head,.95,.55);C.cue('ground_quake',g,.55,.9)
 C.ring(g+up*.08,'ShockwaveRing',r,r*7,.8,RED,0,true);C.ring(g+up*.11,'ShockwaveRing',r*.5,r*4.5,.55,WHITE,.2,true)
 C.star(head,RED,r*2,.26);C.light(head,RED,40,3.5,.8)
 C.emit(head,up,'SmokePuff',{emit=12,Speed={6,11},SpreadAngle=70,Drag=2.5,Lifetime={.9,1.3},Size=ns({0,1.5},{1,4.5}),Color=STEAM,Transparency=ns({0,.25},{.5,.45},{1,1}),Acceleration=Vector3.new(0,4,0),LightInfluence=.6,Rotation={0,360},RotSpeed={-40,40}})
 for _,x in {-1,1} do -- off both shoulders
  local sp=p+up*headOffset(T)*.8+root.CFrame.RightVector*x*3*(scale or 1)
  C.emit(sp,(up+root.CFrame.RightVector*x*.6).Unit,'SmokePuff',{emit=5,Speed={5,9},SpreadAngle=30,Drag=2.5,Lifetime={.8,1.2},Size=ns({0,1.2},{1,3.5}),Color=STEAM,Transparency=ns({0,.3},{.5,.5},{1,1}),LightInfluence=.6,Rotation={0,360}})
 end
 C.dustRing(g,r,14,DUST,{16,24},4*(scale or 1))
end
-- Once: the eyes ignite and stay red, and steam keeps rising off his head for the rest of the fight
-- (on the root, so it follows him). The roar's peak comes with each roar (H.roar); a boss without a
-- roar clip (m.roars unset) gets it now.
function H.enrage(m)
 local npc=m.npc;local root=npc.PrimaryPart;if not root then return end
 local glow=C.glow(npc,'EyeGlow')
 if #glow>0 then K.animate(.3,function(t) C.setGlow(glow,RED,t) end,function() C.setGlow(glow,RED,1) end,'bossGlow',8) end
 local at=Instance.new('Attachment');at.Name='BossVfxSteam';at.Position=Vector3.new(0,headOffset(m.timing),0);at.Parent=root
 C.fx(at,'SmokePuff',{Rate=1.2,EmissionDirection=Enum.NormalId.Top,Speed={2,4},SpreadAngle=25,Lifetime={1,1.4},Size=ns({0,.8},{1,2.6}),Color=STEAM,Transparency=ns({0,.5},{.4,.6},{1,1}),Acceleration=Vector3.new(0,3,0),LightInfluence=.6,Rotation={0,360},RotSpeed={-30,30}})
 if not m.roars then roarPeak(npc,m.scale,m.timing) end
end
-- Each roar the server starts (a replay after a pause cancelled one too): the peak at the clip's
-- impact when it has one, else 0.3 s in, while that roar is still live.
function H.roar(ctx)
 local peak=ctx.attack and ctx.attack.impact or 0
 C.at(ctx,peak>0 and peak or .3,function() roarPeak(ctx.npc,ctx.scale,ctx.timing) end)
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
