-- Round 10 events (ROUND_10_MASTER_SPEC.md): one map-specific halfway event per map, replacing the
-- old wave-10 midboss. Shared by the server director (Round10Service) and the client presentation
-- (Round10Events.client): titles, objectives, timings and starting tuning. Every number here is a
-- starting value for play-testing, not approved tuning.
--
-- kind: 'survive' (clear after `duration` seconds of active combat), 'leader' (clear when the
--   leader, a MapBossDefs id run by MapBossService, dies) or 'tombs' (all coffins destroyed AND the
--   leader dead). intro: seconds of cinematic (CinematicUntil holds players, enemies and spawning).
-- needs: what this place must have for the event to run (Round10Service.ready); a missing piece
--   keeps the old wave-10 midboss, so a part-synced place never gets a broken wave.
--   templates: ServerStorage.RogueliteNPCs children; leader: MapBossDefs.ready(id); props:
--   ServerStorage.Round10Props children.
local D={}
D.WAVE=10
-- Seconds between the clear and the shop opening: the EVENT CLEARED banner and crystal pickup.
D.CLEAR_HOLD=3
-- Completion shower: crystals the clear pays when no leader drop did (the old midboss's drop,
-- MapBossService/ShardDropService IsMapBoss), so every map's wave 10 pays alike.
D.CLEAR_SHARDS=60

D.Events={
 PineValley={
  -- intro 5.4 (2026-10-10, was 4.2): a harmless intro Bloater waddles in, arms and pops on camera
  -- (Round10Intro, Round10Service introBloater) before the title card.
  id='PopGoesTheZombie',title='POP GOES THE ZOMBIE',objective='SURVIVE',kind='survive',duration=60,intro=5.4,
  arming='ABOUT TO BURST',
  -- The intro Bloater (2026-10-10): starts walkFrom studs behind Focus, waddles onto it by armAt (s
  -- into the intro), arms with the real warning and pops at burstAt (armAt + Blast.fuse 1.5).
  introPop={walkFrom=9,armAt=1.7,burstAt=3.2},
  needs={templates={'BloaterZombie_NPC'}},
  -- Waves of the map's zombies plus Bloaters, from the arena edge (EventSpawn telegraphs each).
  -- interval: seconds between pulses, early -> late (the last 15 s push harder).
  spawn={interval={3.0,2.2},perPlayer=6,base=4,cap={34,14},fodder={'regular-zombie','regular-zombie','baby-zombie','regular-zombie','regular-zombie','baby-zombie','regular-zombie','tank-zombie'}, -- 1 tank in 8 (was 1 in 5, 2026-10-10)
   exploder='bloater',exploderEvery=2,exploderPerPlayer=1,exploderCap={3,2},firstExploder=1.2},
 },
 BeachCove={
  id='CrabRave',title='CRAB RAVE',objective='DEFEAT THE DJ CRAB',kind='leader',leader='DJCrab',intro=4.8,music='CrabRave',
  needs={leader='DJCrab'},
  spawn={interval={4.2,3.4},perPlayer=3,base=3,cap={20,10},fodder={'crab','crab','hermit-crab','rock-throwing-crab','crab'}},
  -- Beat Command: up to count + perPlayer x players crab adds rush along warned lanes.
  -- 2026-10-10 user: "larger attacks": length 34 -> 50, width 4.5 -> 6.4 (the lane drawn is the lane tested).
  rush={count=3,perPlayer=2,warn=.9,speed=40,length=50,width=6.4,damage=14,range=55},
 },
 DesertBasin={
  id='TombOpens',title='THE TOMB OPENS',objective='DESTROY THE TOMBS AND DEFEAT THE WARDEN',kind='tombs',leader='TombWarden',intro=5.0,
  needs={leader='TombWarden',props={'Sarcophagus'}},
  -- 2026-10-10 user: "they need to be spread apart", "multiple wardens come out" in multiplayer, and the
  -- tombs' spawning "feels like just another normal round". ring: the tombs' ring as a share of the
  -- arena radius, clamped to ringClamp studs; minGap: studs between any two tombs (was 16 on a 27 ring).
  -- wardens: Tomb Wardens by party size 1-4 (A from tomb A's cavity, the rest burst out in front of
  -- B / C when the fight starts); the party's boss health is split between them (Defs.wardenHealth).
  -- burst: each standing tomb glows and shakes for `warn` s, then pours size skeletons out of its
  -- mouth `pour` s apart; bursts come faster and bigger the longer the tomb stands (Defs.burstSize,
  -- Defs.burstInterval). Destroying a tomb stops its stream and cancels its pour mid-way.
  tombs={count=3,health=1500,ring=.62,ringClamp={30,42},minGap=34,letters={'A','B','C'},wardens={1,2,2,3},
   burst={warn=.9,interval={4.2,2.6},step=.3,base=2,perPlayer=1,grow=3,growEvery=3,pour=.14,stagger=1.4},
   fodder={'skeleton','mummy','skeleton','bow-skeleton'},cap={30,10}},
 },
 FrozenPass={
  id='BloodMoonHunt',title='BLOOD MOON HUNT',objective='DEFEAT THE ALPHA',kind='leader',leader='BloodAlpha',intro=4.4,
  needs={leader='BloodAlpha'},
  -- Packs from alternating approaches; the alpha's Howl empowers wolves near it.
  spawn={interval={7.5,6.0},perPlayer=2,base=2,cap={14,6},fodder={'werewolf'},pack=true},
  howl={radius=42,seconds=6,speed=1.25,damage=1.25,cue='PACK EMPOWERED'},
 },
 VolcanicCrater={
  id='Eruption',title='ERUPTION',objective='SURVIVE',kind='survive',duration=60,intro=4.0,
  needs={props={'VolcanicVent'}},
  spawn={interval={3.2,2.4},perPlayer=4,base=3,cap={30,12},fodder={'lava-slime','lava-slime','fire-goblin','lava-slime','ember-spider'}},
  -- Vents in groups that take turns: charge (warn s), erupt (damage ticks), cool. 2026-10-10 user:
  -- remove the big CHARGING / ERUPTING / COOLING tags (the vent's glow, light and ground ring say it
  -- now), "spread out more and larger aoe", and "they should change locations ... or just have more".
  -- rings: vents alternate between two rings (shares of the arena radius, clamped to radius studs).
  -- blast: the vent's own disc; splash: lava splashes thrown out each eruption (count discs of
  -- radius at distance studs from the vent, picked when it starts charging and drawn while it
  -- charges). relocate: every `every` eruptions a vent moves (the new spot is marked for warn s);
  -- minGap from other vents, clear from players.
  vents={count=8,rings={.3,.62},radius={18,44},groups=4,warn=1.5,erupt=1.8,cool=.9,gap=1.9,blast=12,tick=.5,
   splash={count=3,radius=6,distance={13,19}},relocate={every=2,warn=1.6,minGap=22,clear=8},
   playerDamage=12,enemyShare=.35},
 },
}
-- Event music (Round10Events.client), played through the RogueliteMusic group (the Settings music
-- slider) while the event's playlist is ducked. soundId nil: the normal boss playlist plays instead.
-- CrabRave: the user's pick, Syn Cole - Feel Good (NCS). audio/music/round10/feelgood_segment.ogg is
-- the source from 40.87 s to 77.60 s (bar 21 to bar 40 at 124.15 BPM, measured from the supplied MP3):
-- the build-up, then the 16-bar drop that loops. accent: the drop's first beat in that file, which
-- lands on the DJ's claw snap 2.0 s into the intro (accentAtIntro). Never a gameplay dependency: a
-- missing, muted or late track changes no timing.
D.Music={
 CrabRave={soundId=nil,accent=5.80,accentAtIntro=2.0,loopStart=5.80,loopEnd=36.73,volume=.5,
  credit='Syn Cole - Feel Good [NCS Release]'},
}
-- The event for a map id, or nil.
function D.forMap(map) return type(map)=='string' and D.Events[map] or nil end
function D.byId(id) for map,e in D.Events do if e.id==id then return e,map end end;return nil end
-- Spawn pacing at progress k (0 at the start of the active phase, 1 at its end; leader and tomb
-- events use their elapsed time over 60 s, held at 1): the interval eases from early to late.
function D.interval(spawn,k) k=math.clamp(k or 0,0,1);return spawn.interval[1]+(spawn.interval[2]-spawn.interval[1])*k end
-- Living event adds the director keeps at most, for `players` up (1-4): cap[1] solo plus cap[2] a
-- player. Example, Pine Valley with 3 players: 34 + 2 x 14 = 62 (under WaveTimeline.MaxAlive 100).
function D.cap(spawn,players) return math.min(90,spawn.cap[1]+spawn.cap[2]*math.max(0,(players or 1)-1)) end
-- How many arrive in one pulse: base + perPlayer x players.
function D.pulseSize(spawn,players) return spawn.base+spawn.perPlayer*math.max(1,players or 1) end
-- Tomb event (2026-10-10). Wardens for `players` up: 1 solo, 2 for 2-3, 3 for 4.
function D.wardens(tombs,players) local w=tombs.wardens or {1};return w[math.clamp(math.floor(players or 1),1,#w)] end
-- Each Warden's share of the party-scaled boss health (MapBossService already multiplies by the party):
-- the pool is split evenly, so the total stays what one Warden had. Example, 4 players: one Warden
-- would have 4 x solo; three Wardens get 4/3 x solo each. 3 players: two at 1.5 x solo.
function D.wardenHealth(partyHealth,count) return math.ceil(partyHealth/math.max(1,count or 1)) end
-- Skeletons in a tomb's burst after `bursts` earlier ones: base + perPlayer x players, +1 every
-- growEvery bursts up to +grow. Example, solo: 3, 3, 3, 4, 4, 4, 5 ... 6; 4 players: 6 ... 9.
function D.burstSize(burst,players,bursts)
 return burst.base+burst.perPlayer*math.max(1,players or 1)+math.min(burst.grow,(bursts or 0)//burst.growEvery)
end
-- Seconds to a tomb's next burst after `bursts` bursts: interval[1] less `step` each, down to interval[2].
-- Example: 4.2, 3.9, 3.6 ... 2.6 (from the 6th burst on).
function D.burstInterval(burst,bursts) return math.max(burst.interval[2],burst.interval[1]-burst.step*(bursts or 0)) end
-- Vent cycle state at `c` seconds into its period: 'Charging', 'Erupting', 'Cooling', 'Moving' (only on
-- a relocating cycle) or 'Idle', and the seconds that state has left.
function D.ventState(vents,c,relocating)
 local w,e,o=vents.warn,vents.warn+vents.erupt,vents.warn+vents.erupt+vents.cool
 if c<w then return 'Charging',w-c elseif c<e then return 'Erupting',e-c elseif c<o then return 'Cooling',o-c end
 local m=o+(vents.relocate and vents.relocate.warn or 0)
 if relocating and c<m then return 'Moving',m-c end
 return 'Idle',nil
end
-- MM:SS for a countdown (the HUD timer reads WaveEndsAt the same way).
function D.clock(seconds) local s=math.max(0,math.ceil(seconds or 0));return string.format('%02d:%02d',s//60,s%60) end
return D
