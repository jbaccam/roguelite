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
--   follow circles + extra, breath turn rate x track, the Stomp wave splits into `fan`, and
--   `order` (optional) replaces the attack order. roar: a clip played once on enraging (no hit).
-- Hammer Brute runtime (MapBossService, 2026-10-03):
--   phases: a combo clip's hits in order, each the attack def with the phase's fields on top, timed
--     by the clip's MapBossTiming phases. height: a circle's band top (default MapBossShapes 5.5).
--   lanes: facing='forward' runs straight at the target; contact keeps running until the root is
--     `contact` studs from a target still in the lane; finish is a circle hit at the end clip's
--     impact. lockout: seconds between one attack's starts, on top of cooldowns.
--   intro {drop,fall,after,clip} and introName: a wave boss's sky-drop entrance. tutorial
--     {order,enrage,follow}: the TutorialBossHealth boss's attack order, and false turns enrage or
--     follow-ups off.
-- D.ready(id) (server): true only when this place can run the boss on this runtime, def, timing,
--   client clips and template all present. Every spawn of 'Hammer' checks it, and falls back to the
--   old BossService Hammer until his template and animations are installed (rebuild R6, 2026-10-03).
local Timing=require(script.Parent:WaitForChild('MapBossTiming'))
local D={}
-- The installer's order (InstallMapBossTemplates). The Hammer is Pine Valley's, the first map.
D.Order={'Hammer','KingCrab','Pharaoh','FrostCyclops','Dragon'}
D.ENRAGE_AT=.5
D.FIRST_ATTACK=1.2 -- seconds after spawn before the first attack
-- Pine Valley's wave-20 boss (and the tutorial's, at TutorialBossHealth), rebuilt on this runtime
-- (plans/2026-10-03-hammer-brute-rebuild-design.md section 4). He chases at 20 (23 enraged), under the
-- players' 24. Charge starts at 22 studs, so the order walk picks it only when nobody is in melee
-- reach, and never within 5 s of the last one (lockout). Every slam (Slam, SpinSlam's second hit, the
-- ChargeSlam) opens CRACKS under up to 3 players it missed, 0.85 s later. The eyes glow white
-- (glowColor, the installer's Neon EyeGlow) until the enrage turns them red (BossVfx/Hammer).
local CRACKS={radius=5.5,delay=.85,maxTargets=3,range=40,damage=16}
D.Hammer={anim='hammer-brute',name='Hammer Brute',introName='HAMMER ZOMBIE BOSS',health=18000,scale=1,chaseSpeed=20,glowColor=Color3.fromRGB(255,255,255),
 intro={drop=1.2,fall=.65,after=3.6,clip='IntroLand'},roar='Roar',
 enrage={cooldown=.6,chase=3,follow=2,order={'SwingSpin','Slam','Charge','SpinSlam','Swing','SpinSlam','Spin'}},
 tutorial={order={'Slam','Swing','Charge','Slam','Spin'},enrage=false,follow=false},
 attacks={
  Slam={clip='Slam',range={0,16},cooldown=.8,damage=26,shape='circle',point='HammerFace',radius=9.5,height=6,knockdown=.6,follow=CRACKS},
  Swing={clip='Swing',range={0,14},cooldown=.8,damage=20,shape='sweep',point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4},
  Spin={clip='Spin',range={0,14},cooldown=1,damage=22,shape='sweep',point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4},
  SwingSpin={clip='SwingSpin',range={0,14},cooldown=1,phases={
   {shape='sweep',damage=20,point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4},
   {shape='sweep',damage=22,point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4}}},
  SpinSlam={clip='SpinSlam',range={0,14},cooldown=1.1,phases={
   {shape='sweep',damage=22,point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4},
   {shape='circle',damage=26,point='HammerFace',radius=9.5,height=6,knockdown=.6,follow=CRACKS}}},
  Charge={clips={'ChargeStart','ChargeRun','ChargeSlam'},facing='forward',range={22,70},lockout=5,cooldown=1,damage=24,
   shape='lane',length=75,width=9,speed=32,contact=4,knockdown=.6,
   finish={shape='circle',damage=26,point='HammerFace',radius=9.5,height=6,knockdown=.6,follow=CRACKS}},
 },order={'Slam','Swing','Charge','Slam','Spin','SwingSpin'}}
D.KingCrab={anim='king-crab',name='Giant King Crab',health=21000,scale=1.4,chaseSpeed=22,glowColor=nil,deathSeconds=nil,
 enrage={cooldown=.6,chase=3,extra=4,follow=2},
 attacks={
  ClawCrush={clip='ClawCrush',rate=1.3,range={0,20},cooldown=1,damage=28,shape='circle',point='ClawImpact',radius=9,
   follow={radius=5.5,delay=.8,maxTargets=4,range=48,damage=18}},
  -- Hits the whole side-on body: at scale 1.4 the claws reach 14 studs from his centre and the
  -- shell 7 the other way, so a 21-wide band shifted 3.5 toward the claws (X.laneSide). It was
  -- 12 wide on his centre line, and the claws never hit (2026-10-02).
  SidewaysRush={clips={'RushStart','RushLoop','RushEnd'},rate=1.25,range={8,70},cooldown=1.4,damage=24,shape='lane',length=70,width=21,offset=3.5,speed=42},
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
D.ATTACK_CLIPS={['king-crab']={'ClawCrush','RushStart','RushLoop','RushEnd','BubbleBarrage'},['frost-cyclops']={'GroundSlam','Stomp'},['pharaoh']={'CursedBolts','TombEruption'},['dragon']={'FireBreath','TailWhip','FrontStomp'},
 ['hammer-brute']={'Slam','Swing','Spin','SwingSpin','SpinSlam','ChargeStart','ChargeRun','ChargeSlam','IntroLand','Roar'}}
function D.get(id) return D[id] and type(D[id])=='table' and D[id].anim and D[id] or nil end
function D.isBoss(id) return D.get(id)~=nil end
-- The generated timing as authored (the template installer builds the unscaled template from it).
function D.rawTiming(id) local d=D.get(id);return d and Timing[d.anim] end

-- Scaled, rate-adjusted timing (see the header). Built once per boss.
local TIMES={'duration','warnStart','impact','activeEnd','recoveryEnd','chargeStart','channelStart','channelEnd'}
local LENGTHS={'rootHeight','height','footprintRadius','groundOffset','strideLength','rushStrideLength','chargeStrideLength'}
local cache={}
local function rateOf(def,clip)
 for _,a in def.attacks do if a.clip==clip or (a.clips and table.find(a.clips,clip)) then return a.rate or 1 end end
 return 1
end
local function track(list,s,rate)
 if not list then return nil end
 local out={};for i,p in list do out[i]={p[1]/rate,p[2]*s,p[3]*s,p[4]*s} end;return out
end
-- One attack's timing at scale s and playback rate: times / rate, warned from the commit
-- (warnStart 0), sampled and authored points x s. A combo's phases get the same.
function D.scaleAttack(at,s,rate)
 local n=table.clone(at);n.rate=rate
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
 if at.phases then n.phases={};for i,ph in at.phases do n.phases[i]=D.scaleAttack(ph,s,rate) end end
 return n
end
function D.timing(id)
 local def=D.get(id);if not def then return nil end
 if cache[id] then return cache[id] end
 local raw=Timing[def.anim];if not raw then return nil end
 local s=def.scale or 1
 local T=table.clone(raw);T.scale=s;T.attacks={}
 for _,k in LENGTHS do if raw[k] then T[k]=raw[k]*s end end
 for name,at in raw.attacks or {} do T.attacks[name]=D.scaleAttack(at,s,rateOf(def,name)) end
 cache[id]=T
 return T
end
-- Server (and Edit): true when this place can run `id` on this runtime: its def, its generated timing,
-- its clip modules (RogueliteCombat.BossAnimations[anim], which clients play) and its template
-- (ServerStorage.RogueliteNPCs.<id>_NPC). With any one missing, callers keep the old path: 'Hammer'
-- spawns the BossService Hammer, so a def synced ahead of his template never breaks wave 20.
-- Example: today D.Hammer is here but MapBossTiming has no 'hammer-brute', so ready('Hammer') is false.
-- Clients can't see ServerStorage, so it is false there.
function D.ready(id)
 local def=D.get(id);if not def or not D.timing(id) then return false end
 local anims=script.Parent:FindFirstChild('BossAnimations');local npcs=game:GetService('ServerStorage'):FindFirstChild('RogueliteNPCs')
 return anims~=nil and anims:FindFirstChild(def.anim)~=nil and npcs~=nil and npcs:FindFirstChild(id..'_NPC')~=nil
end
return D
