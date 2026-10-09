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
  id='PopGoesTheZombie',title='POP GOES THE ZOMBIE',objective='SURVIVE',kind='survive',duration=60,intro=4.2,
  arming='ABOUT TO BURST',
  needs={templates={'BloaterZombie_NPC'}},
  -- Waves of the map's zombies plus Bloaters, from the arena edge (EventSpawn telegraphs each).
  -- interval: seconds between pulses, early -> late (the last 15 s push harder).
  spawn={interval={3.0,2.2},perPlayer=6,base=4,cap={34,14},fodder={'regular-zombie','regular-zombie','baby-zombie','regular-zombie','tank-zombie'},
   exploder='bloater',exploderEvery=2,exploderPerPlayer=1,exploderCap={3,2},firstExploder=1.2},
 },
 BeachCove={
  id='CrabRave',title='CRAB RAVE',objective='DEFEAT THE DJ CRAB',kind='leader',leader='DJCrab',intro=4.8,music='CrabRave',
  needs={leader='DJCrab'},
  spawn={interval={4.2,3.4},perPlayer=3,base=3,cap={20,10},fodder={'crab','crab','hermit-crab','rock-throwing-crab','crab'}},
  -- Beat Command: up to count + perPlayer x players crab adds rush along warned lanes.
  rush={count=3,perPlayer=2,warn=.9,speed=40,length=34,width=4.5,damage=14,range=55},
 },
 DesertBasin={
  id='TombOpens',title='THE TOMB OPENS',objective='DESTROY THE TOMBS AND DEFEAT THE WARDEN',kind='tombs',leader='TombWarden',intro=5.0,
  needs={leader='TombWarden',props={'Sarcophagus'}},
  tombs={count=3,health=1500,radius=27,letters={'A','B','C'},pulse={6.5,5.0},stagger=2.2,perPulse=1,perPlayer=1,telegraph=1.1,
   fodder={'skeleton','mummy','skeleton','bow-skeleton'},cap={24,10}},
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
  -- Fixed vents in groups that take turns: warn (orange), erupt (damage ticks), cool.
  vents={count=6,radius={20,30},groups=3,warn=1.5,erupt=2.0,gap=2.3,blast=9,tick=.5,
   playerDamage=12,enemyShare=.35,cues={'CHARGING','ERUPTING','COOLING'}},
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
-- MM:SS for a countdown (the HUD timer reads WaveEndsAt the same way).
function D.clock(seconds) local s=math.max(0,math.ceil(seconds or 0));return string.format('%02d:%02d',s//60,s%60) end
return D
