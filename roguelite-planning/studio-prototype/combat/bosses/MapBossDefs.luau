-- Per-boss gameplay numbers for the map-boss runtime (plan F). Clip timings and sampled
-- points come from the generated MapBossTiming; this file owns size, health, speed, damage,
-- ranges, cooldowns, playback rate and attack order. Every value is a starting point for play-testing.
--
-- scale: the boss is spawned at this multiple of its authored size. D.timing(id) returns the
--   generated timing already scaled (root height, footprint, stride, sampled points), so the server
--   hit tests, the client warnings and the effects all read the scaled boss. Distances written
--   below (radius, length, range...) are final studs for the scaled boss.
-- rate: attack clip playback speed. D.timing(id) divides that attack's times by it, and the client
--   plays the clip at age * rate. Every warning starts the moment the boss commits (warnStart 0).
-- follow: a second hazard after impact. Circles open under up to maxTargets players within range
--   that the main hit missed, and erupt `delay` seconds later.
-- enrage (below ENRAGE_AT health): cooldowns x cooldown, chaseSpeed + chase, projectiles + extra,
--   follow circles + extra, breath turn rate x track, and the Stomp wave splits into `fan`.
local Timing=require(script.Parent:WaitForChild('MapBossTiming'))
local D={}
D.Order={'KingCrab','Pharaoh','FrostCyclops','Dragon'}
D.ENRAGE_AT=.5
D.FIRST_ATTACK=1.2 -- seconds after spawn before the first attack
D.KingCrab={anim='king-crab',name='Giant King Crab',health=2400,scale=1.4,chaseSpeed=17,glowColor=nil,deathSeconds=nil,
 enrage={cooldown=.6,chase=3,extra=4,follow=2},
 attacks={
  ClawCrush={clip='ClawCrush',rate=1.3,range={0,20},cooldown=1,damage=28,shape='circle',point='ClawImpact',radius=9,
   follow={radius=5.5,delay=.8,maxTargets=4,range=48,damage=18}},
  SidewaysRush={clips={'RushStart','RushLoop','RushEnd'},rate=1.25,range={8,52},cooldown=1.4,damage=24,shape='lane',length=50,width=12,speed=42},
  BubbleBarrage={clip='BubbleBarrage',rate=1.2,range={10,46},cooldown=1.1,damage=10,shape='projectiles',point='BubbleOrigin',count=13,spread=math.rad(52),speed=26,radius=2,life=2.6,perPlayer=2},
 },order={'ClawCrush','BubbleBarrage','SidewaysRush','ClawCrush','SidewaysRush','BubbleBarrage'}}
D.Pharaoh={anim='pharaoh',name='The Pharaoh',health=3000,scale=1.4,chaseSpeed=15,glowColor=Color3.fromRGB(120,235,255),
 enrage={cooldown=.6,chase=3,extra=2,follow=2},
 attacks={
  CursedBolts={clip='CursedBolts',rate=1.25,range={8,56},cooldown=.9,damage=22,shape='projectiles',point='BoltOrigin',count=5,spread=math.rad(34),speed=40,radius=1.6,life=2.2,perPlayer=1},
  TombEruption={clip='TombEruption',rate=1.2,range={0,70},cooldown=1.4,damage=30,shape='targets',radius=5.5,maxTargets=5,lead=.25,eruptDelay=.7,extra=1},
 },order={'CursedBolts','TombEruption','CursedBolts','CursedBolts','TombEruption'}}
D.FrostCyclops={anim='frost-cyclops',name='Frost Cyclops',health=3600,scale=1.4,chaseSpeed=16,glowColor=nil,
 enrage={cooldown=.6,chase=3,follow=2,fan={-28,0,28}},
 attacks={
  GroundSlam={clip='GroundSlam',rate=1.15,range={0,18},cooldown=1,damage=32,shape='circle',point='ClubImpact',radius=12,knockdown=.7,
   follow={radius=6,delay=.85,maxTargets=4,range=48,damage=22}},
  Stomp={clip='Stomp',rate=1.3,range={8,42},cooldown=1.3,damage=30,shape='wave',point='StompImpact',length=44,width=7,travel=60},
 },order={'GroundSlam','Stomp','GroundSlam','Stomp','Stomp'}}
D.Dragon={anim='dragon',name='Inferno Dragon',health=4500,scale=1.25,chaseSpeed=18,glowColor=Color3.fromRGB(255,150,40),
 enrage={cooldown=.6,chase=3,follow=2,track=1.6},
 attacks={
  FireBreath={clip='FireBreath',rate=1.2,range={4,32},cooldown=1.3,damage=12,shape='breath',point='FireOrigin',halfAngle=math.rad(24),length=30,tick=.35,track=math.rad(70)},
  TailWhip={clip='TailWhip',rate=1.25,range={0,26},cooldown=1,damage=34,shape='sweep',point='SpadeTip',mid='TailMid',radius=4},
  FrontStomp={clip='FrontStomp',rate=1.2,range={0,16},cooldown=1.1,damage=38,shape='circle',point='StompCenter',radius=12,knockdown=.8,
   follow={radius=6.5,delay=.85,maxTargets=4,range=56,damage=26}},
 },order={'FireBreath','FrontStomp','TailWhip','FireBreath','TailWhip','FrontStomp'}}
D.ATTACK_CLIPS={['king-crab']={'ClawCrush','RushStart','RushLoop','RushEnd','BubbleBarrage'},['frost-cyclops']={'GroundSlam','Stomp'},['pharaoh']={'CursedBolts','TombEruption'},['dragon']={'FireBreath','TailWhip','FrontStomp'}}
function D.get(id) return D[id] and type(D[id])=='table' and D[id].anim and D[id] or nil end
function D.isBoss(id) return D.get(id)~=nil end
-- The generated timing as authored (the template installer builds the unscaled template from it).
function D.rawTiming(id) local d=D.get(id);return d and Timing[d.anim] end

-- Scaled, rate-adjusted timing (see the header). Built once per boss.
local TIMES={'duration','warnStart','impact','activeEnd','recoveryEnd','chargeStart','channelStart','channelEnd'}
local LENGTHS={'rootHeight','height','footprintRadius','groundOffset','strideLength','rushStrideLength'}
local cache={}
local function rateOf(def,clip)
 for _,a in def.attacks do if a.clip==clip or (a.clips and table.find(a.clips,clip)) then return a.rate or 1 end end
 return 1
end
local function track(list,s,rate)
 if not list then return nil end
 local out={};for i,p in list do out[i]={p[1]/rate,p[2]*s,p[3]*s,p[4]*s} end;return out
end
function D.timing(id)
 local def=D.get(id);if not def then return nil end
 if cache[id] then return cache[id] end
 local raw=Timing[def.anim];if not raw then return nil end
 local s=def.scale or 1
 local T=table.clone(raw);T.scale=s;T.attacks={}
 for _,k in LENGTHS do if raw[k] then T[k]=raw[k]*s end end
 for name,at in raw.attacks or {} do
  local rate=rateOf(def,name);local n=table.clone(at);n.rate=rate
  for _,k in TIMES do if at[k] then n[k]=at[k]/rate end end
  n.warnStart=0
  if at.pumps then n.pumps={};for i,t in at.pumps do n.pumps[i]=t/rate end end
  if at.samples then n.samples={};for p,list in at.samples do n.samples[p]=track(list,s,rate) end end
  if at.dirs then n.dirs={};for p,list in at.dirs do n.dirs[p]=track(list,1,rate) end end
  if at.points then
   n.points={}
   for p,pt in at.points do
    local c=table.clone(pt)
    for _,k in {'rootAtImpactStudio','groundPointAtImpactStudio'} do local v=pt[k];if type(v)=='table' then c[k]={v[1]*s,v[2]*s,v[3]*s} end end
    n.points[p]=c
   end
  end
  T.attacks[name]=n
 end
 cache[id]=T
 return T
end
return D
