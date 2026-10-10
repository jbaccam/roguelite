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
--   follow circles + extra, breath turn rate x track, a wave (the Stomp, a Hammer slam's rubble
--   wave) splits into `fan` (degrees), and `order` (optional) replaces the attack order. roar: a clip
--   played once on enraging (no hit).
-- Hammer Brute runtime (MapBossService, 2026-10-03):
--   phases: a combo clip's hits in order, each the attack def with the phase's fields on top, timed
--     by the clip's MapBossTiming phases. height: a circle's band top (default MapBossShapes 5.5).
--   lanes: facing='forward' runs straight at the target; contact keeps running until the root is
--     `contact` studs from a target still in the lane; finish is a circle hit at the end clip's
--     impact, or a list of hits timed by the end clip's phases in order (the Hammer: {circle, wave}).
--     lockout: seconds between one attack's starts, on top of cooldowns.
--   wave as a phase or a finish part (2026-10-09): facing='forward' sends it along the frame's facing
--     (aimed) instead of the clip's authored direction; it starts at def.point at impact.
--   intro {drop,fall,after,clip} and introName: a wave boss's sky-drop entrance. tutorial
--     {order,enrage,follow}: the TutorialBossHealth boss's attack order, and false turns enrage or
--     follow-ups off.
--   aim {rate,lock} (boss or attack): a circle, sweep, wave or combo turns its frame toward its target
--     at up to `rate` rad/s, holding still from `lock` s before each hit. home (a forward lane): the
--     run's heading turns toward the target at up to `home` rad/s (2026-10-04).
-- D.ready(id) (server): true only when this place can run the boss on this runtime (def, timing,
--   client clips, template, MapBossService and MapBossShapes all present). D.legacy(id): true for the
--   'Hammer' until then, and every 'Hammer' spawn (BossEncounter, RogueliteZombieChase) asks it and
--   spawns the old BossService Hammer instead (rebuild R6, 2026-10-03).
-- The server never waits for MapBossTiming (its ReplicatedStorage is complete at load): a place
-- without it has no timings, so nothing is ready and wave 20 still gets the old Hammer. A client
-- waits up to 60 s for it to replicate. Either way, one that turns up later is still picked up: every
-- D.timing / D.rawTiming looks for it again until it is here (timings()).
local Run=game:GetService('RunService')
local timingModule=script.Parent:FindFirstChild('MapBossTiming') or (not Run:IsServer() and script.Parent:WaitForChild('MapBossTiming',60)) or nil
if not timingModule then warn('MapBossDefs: no MapBossTiming here yet, so no map boss is ready') end
local Timing=timingModule and require(timingModule) or nil
local function timings()
 if not Timing then local m=script.Parent:FindFirstChild('MapBossTiming');if m then Timing=require(m) end end
 return Timing or {}
end
local D={}
-- The installer's order (InstallMapBossTemplates). The Hammer is Pine Valley's, the first map.
D.Order={'Hammer','KingCrab','Pharaoh','FrostCyclops','Dragon'}
D.ENRAGE_AT=.5
D.FIRST_ATTACK=1.2 -- seconds after spawn before the first attack
-- Pine Valley's wave-20 boss (and the tutorial's, at TutorialBossHealth), on this runtime
-- (plans/2026-10-03-hammer-brute-rebuild-design.md section 4). He chases at 24 (26 enraged), matching the
-- player's 24 base before enrage. Charge starts at 22 studs, so the order walk picks it only when nobody is in melee
-- reach, and never within 5 s of the last one (lockout). The eyes glow white (glowColor, the
-- installer's Neon HammerBrute_EyeGlow plates) until the enrage turns them red (BossVfx/Hammer).
-- He keeps the original 16-part Motor6D model (R9, 2026-10-04): Hammer_NPC is a copy of HammerBoss_NPC,
-- authored at 1.0. The clips are Motor6D.Transforms (partposes_to_motor6d.py).
-- Bigger and further-reaching (user, 2026-10-09: "his movements felt very tight, and not large enough
-- for a boss fight, the range was short and he didn't apply enough pressure ... since he has no ranged
-- attacks"):
--   scale 1.5 (was 1.15): 11.92 studs authored, 17.9 in game, like the other map bosses. The hammer's
--     own path grows with him; the melee ranges grow with it (Swing 16 -> 21, the spins 14 -> 18).
--   Rubble waves replace the CRACKS follow-ups: every slam (the Slam, SpinSlam's slam, the Charge's
--     finish) sends a wave of dirt and rock from the HammerFace impact along his aimed facing, 85 long,
--     9 wide, its front at 55 studs/s (WAVE). Enraged it fans into 3 (-25, 0, +25 deg) like the
--     cyclops's Stomp. It is the slam clip's own phase, timed like the circle (Slam [circle, wave],
--     SpinSlam [rev1, rev2, circle, wave]; the Charge's finish {circle, wave} by the Slam's phases).
--   The Slam's circle is 12 and it slams from up to 45 studs, so the wave reaches a kiting player.
--   Sweeps radius 4.5 / baseRadius 6. The Spin hits twice, 16 a revolution (SwingSpin 20/16/16,
--     SpinSlam 16/16/26 and the wave's 22).
-- Chaining and tracking (user, 2026-10-04: "chaining attacks and better player tracking is all i
-- need"): the clips are Slam, Swing, Spin (two revolutions: two sweep phases), SwingSpin (a swing and
-- two spins), SpinSlam (two spins and a slam) and the Charge, which ends in the regular Slam. The intro
-- lands on the Slam clip; no roar, so the enrage shows on BossEnraged like the other bosses.
--   aim: every hit's frame turns toward its target at up to 150 deg/s until 0.3 s before that hit
--     (MapBossService X.aimOpen; a combo re-aims in each phase's wind-up).
--   home (the Charge): the run's heading turns toward the target at up to 40 deg/s.
local function sweep(damage) return {shape='sweep',damage=damage,point='HammerFace',mid='HammerGrip',radius=4.5,baseRadius=6} end
local SLAM={shape='circle',damage=26,point='HammerFace',radius=12,height=6,knockdown=.6}
-- No knockdown (false, so the Charge's .6 doesn't carry into its finish wave); a well-timed jump clears
-- it (the default 5.5 band, as the Stomp).
local WAVE={shape='wave',damage=22,point='HammerFace',facing='forward',length=85,width=9,travel=55,knockdown=false}
D.Hammer={anim='hammer-brute',name='Hammer Brute',introName='HAMMER BRUTE',health=18000,scale=1.5,chaseSpeed=24,glowColor=Color3.fromRGB(255,255,255),
 intro={drop=1.2,fall=.65,after=3.6,clip='Slam'},roar=nil,aim={rate=math.rad(150),lock=.3},
 enrage={cooldown=.6,chase=2,fan={-25,0,25},order={'SwingSpin','SpinSlam','Slam','SwingSpin','Charge','SpinSlam','Spin'}},
 tutorial={order={'Slam','Swing','Charge','Slam','Spin'},enrage=false,follow=false},
 attacks={
  Slam={clip='Slam',range={0,45},cooldown=.8,phases={SLAM,WAVE}},
  Swing={clip='Swing',range={0,21},cooldown=.8,damage=20,shape='sweep',point='HammerFace',mid='HammerGrip',radius=4.5,baseRadius=6},
  Spin={clip='Spin',range={0,18},cooldown=1,phases={sweep(16),sweep(16)}},
  SwingSpin={clip='SwingSpin',range={0,18},cooldown=1,phases={sweep(20),sweep(16),sweep(16)}},
  SpinSlam={clip='SpinSlam',range={0,18},cooldown=1.1,phases={sweep(16),sweep(16),SLAM,WAVE}},
  Charge={clips={'ChargeStart','ChargeRun','Slam'},facing='forward',home=math.rad(40),range={22,110},lockout=5,cooldown=1,damage=24,
   shape='lane',length=75,width=9,speed=32,contact=4,knockdown=.6,finish={SLAM,WAVE}},
 },order={'Slam','Swing','Charge','Spin','SwingSpin','Slam','SpinSlam'}}
-- Clip blends carry the hammer with both fists (MapBossPresentation P.toolBlend, 2026-10-09).
D.Hammer.toolBlend={tool='Hammer',hands={'RightHand','LeftHand'}}
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
 ['hammer-brute']={'Slam','Swing','Spin','SwingSpin','SpinSlam','ChargeStart','ChargeRun'}}
-- Unique entrances (round 10 spec: every boss gets its own intro; Hammer Brute keeps his sky drop).
-- style names the entrance BossIntro.client films; lead is the seconds from spawn to the key moment
-- (BossIntroLand), when the intro clip's impact lands; after is the hold that follows (camera orbit,
-- name card, then back to the player). The boss can't be hurt and stands still until BossIntroUntil;
-- its health bar slides in after it (RogueliteHUD).
D.KingCrab.intro={style='surface',clip='ClawCrush',lead=2.2,after=2.6}    -- claws break the sand first, then the slam
D.Pharaoh.intro={style='sandrise',clip='TombEruption',lead=2.5,after=2.4} -- a sand spiral; he rises and drives his staff down
D.FrostCyclops.intro={style='footsteps',clip='GroundSlam',lead=2.4,after=2.4} -- three thuds, the club, then the ground strike
D.Dragon.intro={style='descent',clip='FrontStomp',lead=2.7,after=2.6}     -- his shadow crosses the arena, he glides down and lands
-- Round 10 leaders (Round10Defs, Round10Service): mini-bosses on this runtime, spawned only by their
-- event, never by BossEncounter's wave 20, Endless or the admin boss list (AdminConfig.BossIds).
-- intro style 'event': the event's own cinematic films them (no sky-drop camera); the event times
-- their intro clip (opts.eventIntro). 'signal' attacks hit nothing themselves: MapBossService calls
-- the event's hook at their impact (the DJ's Beat Command sends rushers; the alpha's howl buffs).
-- 'ring': an expanding ring with gaps (MapBossShapes.ringHit). Numbers are starting values.
D.Leaders={'DJCrab','TombWarden','BloodAlpha'}
D.DJCrab={anim='dj-crab',name='DJ Crab',leader=true,health=7000,scale=1,chaseSpeed=14,glowColor=Color3.fromRGB(70,230,215),stop=12,
 intro={style='event',clip='Intro',lead=2.0,after=2.8},
 enrage={cooldown=.7,chase=2,extra=1},
 attacks={
  BeatCommand={clip='BeatCommand',range={0,70},cooldown=1.1,damage=0,shape='signal',lockout=7},
  -- Rock bombardment: landing circles under players, rocks arrive eruptDelay later (BossVfx DJCrab).
  Bombard={clip='Bombard',range={6,70},cooldown=1.3,damage=16,shape='targets',radius=5,maxTargets=4,lead=.2,eruptDelay=1.15,extra=1},
  -- Double claw bass slam: the ring runs out from between the claws; three gaps are the way through.
  ClawSlam={clip='ClawSlam',range={0,24},cooldown=1.9,damage=22,shape='ring',point='SlamCenter',inner=3,outer=32,travel=22,width=3,height=4,gaps=3,gapWidth=math.rad(17),knockdown=.5},
 },order={'BeatCommand','ClawSlam','Bombard','BeatCommand','Bombard','ClawSlam'}}
D.TombWarden={anim='tomb-warden',name='Tomb Warden',leader=true,health=6000,scale=1,chaseSpeed=17,glowColor=Color3.fromRGB(255,176,64),
 intro={style='event',clip='Emerge',lead=3.7,after=1.3},
 roar='Roar',enrage={cooldown=.7,chase=3,follow=1},
 attacks={
  FistSlam={clip='FistSlam',range={0,15},cooldown=1.2,damage=26,shape='circle',point='SlamCenter',radius=9,knockdown=.6,
   follow={radius=5,delay=.9,maxTargets=3,range=40,damage=16}},
  FistHook={clip='FistHook',range={0,10},cooldown=.9,damage=20,shape='sweep',point='HookFist',mid='HookMid',radius=2.6,baseRadius=3},
 },order={'FistHook','FistSlam','FistHook','FistHook','FistSlam'}}
D.BloodAlpha={anim='alpha-werewolf',name='Blood Moon Alpha',leader=true,health=6500,scale=1,chaseSpeed=21,glowColor=Color3.fromRGB(255,170,60),stop=5,
 intro={style='event',clip='Howl',lead=2.0,after=2.4},
 enrage={cooldown=.65,chase=3},
 attacks={
  Howl={clip='Howl',range={0,90},cooldown=1,damage=0,shape='signal',lockout=12},
  -- A warned, direction-locked charge (the Hammer's lane: forward, a little homing, ends at contact)
  -- into a claw rake; the miss leaves a punish window (cooldown).
  Charge={clips={'ChargeStart','ChargeRun','ClawRake'},facing='forward',home=math.rad(25),range={14,70},lockout=6,cooldown=1.4,damage=22,
   shape='lane',length=56,width=6,speed=38,contact=3.5,knockdown=.5,finish={shape='circle',point='RightClaw',radius=6.5,damage=18}},
  ClawRake={clip='ClawRake',range={0,8},cooldown=.8,damage=18,shape='circle',point='RightClaw',radius=6.5},
 },order={'Howl','Charge','ClawRake','ClawRake','Charge','ClawRake'}}
D.ATTACK_CLIPS['dj-crab']={'BeatCommand','ClawSlam','Bombard','Intro'}
D.ATTACK_CLIPS['tomb-warden']={'FistSlam','FistHook','Emerge','Roar'}
D.ATTACK_CLIPS['alpha-werewolf']={'Howl','ChargeStart','ChargeRun','ClawRake'}
function D.get(id) return D[id] and type(D[id])=='table' and D[id].anim and D[id] or nil end
function D.isLeader(id) local d=D.get(id);return d~=nil and d.leader==true end
function D.isBoss(id) return D.get(id)~=nil end
-- The generated timing as authored (the template installer builds the unscaled template from it).
function D.rawTiming(id) local d=D.get(id);return d and timings()[d.anim] end

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
 local raw=timings()[def.anim];if not raw then return nil end
 local s=def.scale or 1
 local T=table.clone(raw);T.scale=s;T.attacks={}
 for _,k in LENGTHS do if raw[k] then T[k]=raw[k]*s end end
 for name,at in raw.attacks or {} do T.attacks[name]=D.scaleAttack(at,s,rateOf(def,name)) end
 cache[id]=T
 return T
end
-- Whether one piece of a map boss is in this place: ('timing', id) its generated timing (a malformed
-- one counts as missing), ('clips', anim) RogueliteCombat.BossAnimations[anim], ('template', name)
-- ServerStorage.RogueliteNPCs[name], ('server', name) a ServerScriptService module, ('shared', name)
-- a RogueliteCombat module. Tests pass their own `has` to D.ready and D.legacy instead.
local function present(kind,name)
 if kind=='timing' then local ok,T=pcall(D.timing,name);return ok and T~=nil end
 local parent
 if kind=='clips' then parent=script.Parent:FindFirstChild('BossAnimations')
 elseif kind=='template' then parent=game:GetService('ServerStorage'):FindFirstChild('RogueliteNPCs')
 elseif kind=='server' then parent=game:GetService('ServerScriptService')
 elseif kind=='shared' then parent=script.Parent end
 return parent~=nil and parent:FindFirstChild(name)~=nil
end
-- Server (and Edit): true when this place can run `id` on this runtime: its def, its generated timing,
-- its clip modules (which clients play), its template (RogueliteNPCs.<id>_NPC), and MapBossService and
-- MapBossShapes to run it. Never throws. Clients can't see ServerStorage, so it is false there.
-- Example: today D.Hammer is here but MapBossTiming has no 'hammer-brute', so ready('Hammer') is false.
function D.ready(id,has)
 has=has or present;local def=D.get(id)
 return def~=nil and has('timing',id) and has('clips',def.anim) and has('template',id..'_NPC') and has('server','MapBossService') and has('shared','MapBossShapes')
end
-- The one gate for the bosses with an older runtime: true while 'Hammer' must still spawn the old
-- BossService Hammer, i.e. until every piece of the rebuilt Hammer Brute is here (D.ready). Never for
-- any other id. BossEncounter and RogueliteZombieChase both ask this.
function D.legacy(id,has) return id=='Hammer' and not D.ready(id,has) end
return D
