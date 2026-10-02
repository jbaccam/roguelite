-- Per-boss gameplay numbers for the map-boss runtime (plan F). Clip timings and sampled
-- points come from the generated MapBossTiming; this file owns size, health, speed, damage,
-- ranges, cooldowns, playback rate and attack order. Every value is a starting point for play-testing.
--
-- scale: the boss is spawned at this multiple of its authored size. D.timing(id) returns the
--   generated timing already scaled (root height, footprint, stride, sampled points), so the server
--   hit tests, the client warnings and the effects all read the scaled boss. Distances written
--   below (radius, length, range...) are final studs for the scaled boss.
-- health: Normal, one player. MapBossService multiplies it by the run difficulty and the player
--   count (RunSetupRules.bossScale), and boss damage by the difficulty's damage.
-- stop: optional chase hold-off (flat studs, centre to player); default min(8 x scale, footprint) + 3.
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
D.KingCrab={anim='king-crab',name='Giant King Crab',health=21000,scale=1.4,chaseSpeed=22,glowColor=nil,deathSeconds=nil,
 enrage={cooldown=.6,chase=3,extra=4,follow=2},
 attacks={
  ClawCrush={clip='ClawCrush',rate=1.3,range={0,20},cooldown=1,damage=28,shape='circle',point='ClawImpact',radius=9,
   follow={radius=5.5,delay=.8,maxTargets=4,range=48,damage=18}},
  SidewaysRush={clips={'RushStart','RushLoop','RushEnd'},rate=1.25,range={8,70},cooldown=1.4,damage=24,shape='lane',length=70,width=12,speed=42},
  BubbleBarrage={clip='BubbleBarrage',rate=1.2,range={10,72},cooldown=1.1,damage=10,shape='projectiles',point='BubbleOrigin',count=13,spread=math.rad(52),speed=30,radius=2,life=2.6,perPlayer=2},
 },order={'ClawCrush','BubbleBarrage','SidewaysRush','ClawCrush','SidewaysRush','BubbleBarrage'}}
-- The Pharaoh's staff crook releases the bolts ~10 studs ahead and 14 up, so they pass over anyone
-- within ~13 studs (MapBossServiceTests 4). He holds off at 20 (stop), bolts start at 15, and a
-- player who closes in gets the tombs instead. The bolts fly 48 x 2.5 = 120 studs.
D.Pharaoh={anim='pharaoh',name='The Pharaoh',health=24000,scale=1.4,chaseSpeed=20,glowColor=Color3.fromRGB(120,235,255),stop=20,
 enrage={cooldown=.6,chase=3,extra=2,follow=2},
 attacks={
  CursedBolts={clip='CursedBolts',rate=1.25,range={15,100},cooldown=.9,damage=22,shape='projectiles',point='BoltOrigin',count=5,spread=math.rad(34),speed=48,radius=1.6,life=2.5,perPlayer=1},
  TombEruption={clip='TombEruption',rate=1.2,range={0,100},cooldown=1.4,damage=30,shape='targets',radius=5.5,maxTargets=5,lead=.25,eruptDelay=.7,extra=1},
 },order={'CursedBolts','TombEruption','CursedBolts','CursedBolts','TombEruption'}}
-- The cyclops holds off at 18 studs (stop) and uses Stomp's wave from range. Ground Slam's club
-- lands ~11.6 studs ahead, so radius 15 reaches ~27 studs; rate 1 keeps its warning at
-- radius/22 + .25 s (0.93 s of the 0.96 s wind-up).
D.FrostCyclops={anim='frost-cyclops',name='Frost Cyclops',health=27000,scale=1.4,chaseSpeed=21,glowColor=nil,stop=18,
 enrage={cooldown=.6,chase=3,follow=2,fan={-28,0,28}},
 attacks={
  GroundSlam={clip='GroundSlam',rate=1,range={0,22},cooldown=1,damage=32,shape='circle',point='ClubImpact',radius=15,knockdown=.7,
   follow={radius=6,delay=.85,maxTargets=4,range=48,damage=22}},
  Stomp={clip='Stomp',rate=1.3,range={10,75},cooldown=1.3,damage=30,shape='wave',point='StompImpact',length=78,width=7,travel=80},
 },order={'GroundSlam','Stomp','GroundSlam','Stomp','Stomp'}}
D.Dragon={anim='dragon',name='Inferno Dragon',health=31500,scale=1.25,chaseSpeed=22,glowColor=Color3.fromRGB(255,150,40),
 enrage={cooldown=.6,chase=3,follow=2,track=1.6},
 attacks={
  FireBreath={clip='FireBreath',rate=1.2,range={4,32},cooldown=1.3,damage=12,shape='breath',point='FireOrigin',halfAngle=math.rad(24),length=30,tick=.35,track=math.rad(70)},
  -- Fireball: the long-range answer to kiting, spat on the FireBreath clip (rate must match it).
  Fireball={clip='FireBreath',rate=1.2,range={24,80},cooldown=1.4,damage=20,shape='projectiles',point='FireOrigin',count=3,spread=math.rad(16),speed=45,radius=2,life=2,perPlayer=1},
  -- The whole tail hits once its swing starts: baseRadius around the hindquarters to TailMid,
  -- radius from there to the spade (user, 2026-10-01: standing under his rear never got hit).
  TailWhip={clip='TailWhip',rate=1.25,range={0,26},cooldown=1,damage=34,shape='sweep',point='SpadeTip',mid='TailMid',radius=4,baseRadius=5.5},
  FrontStomp={clip='FrontStomp',rate=1.2,range={0,16},cooldown=1.1,damage=38,shape='circle',point='StompCenter',radius=12,knockdown=.8,
   follow={radius=6.5,delay=.85,maxTargets=4,range=56,damage=26}},
 },order={'FireBreath','Fireball','FrontStomp','TailWhip','Fireball','FireBreath','TailWhip','FrontStomp'}}
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
