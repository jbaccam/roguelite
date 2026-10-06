"""Run the actual spawn director in a deterministic mocked Luau task scheduler.
Usage: python SpawnDirectorTests.py /path/to/luau.exe
The movement/Roblox geometry engine is not exercised by this test.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

PRELUDE = r'''
local now, events, starts, arrivals = 0, {}, {}, {}
local waveGeneration = 1
local queued, queuedSet, pendingGroups, recentCenters = {}, {}, {}, {}
local directorRunning = false
local respawnReadyAt = {}
local bossActive = false
local timed = false
local plannedIds = {}
local timelineOrders,timelineDispatchAt,groupStarts={},0,{}
local function timelineMode() return timed end
local function makeArrivalRoom() return true end
local function bossPressure() return bossActive end
local Population = {BossPressure={groupInterval=.65}}
local queueSpawn
local GROUP_STAGGER, GROUP_SIZE, SWARM_MIN, SWARM_GATHER = .22, {2,4}, 3, .35
local MIN_PLAYER_DISTANCE, STAND_RADIUS, TELEGRAPH_TIME = 22, 5, 1
local SPAWN_BAND = {28,52}
local os = {clock=function() return now end}
local tutorial, enabled, paused, failPoint, blocked = false, true, false, false, false
local roots = {{Position=0}}
local function playersUp() return #roots end
local combat = {GetAttribute=function(_, name)
 if name == 'ZombiesEnabled' then return enabled end
 if name == 'TutorialRun' or name == 'WaveNoRespawn' then return tutorial end
end}
local folder = {FindFirstChild=function() return nil end}
local countLimit = 100
local function spawnCount() return countLimit end
local function adminPaused() return paused end
local function spawnHeld() return paused end
local function flatDistance() return blocked and 0 or 10 end
local function livingRoots() return roots end
local function releaseQueued(members, generation)
 for _, i in members do if queuedSet[i] == generation then queuedSet[i] = nil end end
end
local function pickSpawnPoint(avoid, anchor, band, minimum, direction)
 table.insert(starts, {time=now, origin=direction and direction.origin or anchor, angle=direction and direction.angle})
 return not failPoint and {time=now} or nil
end
local function memberSpots(point, n) return table.create(n, point) end
local function makeWarning(point) return {Destroy=function() end} end
local function clearOfPlayers() return not blocked end
local function spawnZombie(i, _, point)
 assert(point, 'unmarked nil spawn')
 assert(now-point.time >= 1-1e-8, 'spawn without full warning')
 table.insert(arrivals, {time=now, index=i})
end
local function schedule(co, at, args) table.insert(events, {co=co,at=at,args=args}) end
local function resume(co, args)
 local ok, delay = coroutine.resume(co, table.unpack(args or {}))
 assert(ok, delay)
 if coroutine.status(co) ~= 'dead' then schedule(co, now+delay, {}) end
end
local task = {}
function task.spawn(fn, ...) resume(coroutine.create(fn), {...}) end
function task.wait(delay) delay=delay or 1/60;coroutine.yield(delay);return delay end
function task.delay(delay, fn, ...) schedule(coroutine.create(fn),now+delay,{...}) end
local function advance(untilTime)
 local steps=0
 while true do
  table.sort(events,function(a,b) return a.at<b.at end)
  local e=events[1]
  if not e or e.at>untilTime then break end
  table.remove(events,1);now=math.max(now,e.at);resume(e.co,e.args)
  steps+=1;assert(steps<10000,'scheduler livelock')
 end
 now=untilTime
end
'''
CHECKS = r'''

math.randomseed(54)
for i=1,20 do queueSpawn(i) end
advance(.3)
for i=21,40 do queueSpawn(i) end
advance(.5)
roots[1].Position=100
advance(1.5)
assert(#starts>=6,'arrival stream missing')
for i=2,#starts do
 assert(starts[i].time-starts[i-1].time>=.22-1e-8,'flushes bypass global stagger')
 if starts[i].time>.5 then assert(starts[i].origin==100,'stale player spawn anchor') end
 local delta=(starts[i].angle-starts[i-1].angle)%(math.pi*2)
 assert(delta>2.3 and delta<2.5,'groups did not rotate sectors')
end
-- Simulated server hitch: only one pending group begins immediately, subsequent starts wait.
local oldStarts=#starts
now=3
advance(3)
assert(#starts<=oldStarts+1,'hitch dumped scheduled groups together')
advance(8)
assert(#arrivals==40,'lost or duplicated spawn slots')
local seen={}
for _,a in arrivals do assert(not seen[a.index],'duplicate slot');seen[a.index]=true end
-- Reset while a warning is live: no old-generation arrivals.
for i=41,50 do queueSpawn(i) end
advance(8.2)
waveGeneration+=1;queued={};queuedSet={};pendingGroups={};recentCenters={}
local before=#arrivals
advance(10)
assert(#arrivals==before,'old generation spawned after reset')
-- Missing ground never falls back to an unmarked arena-center spawn; it retries.
failPoint=true
queueSpawn(60)
advance(12)
assert(#arrivals==before,'failed ground produced a spawn')
failPoint=false
advance(15)
assert(#arrivals==before+1,'failed ground slot did not recover')
-- Entering a warning requires a new full warning, not an instant relocation.
blocked=true
queueSpawn(61)
advance(17)
assert(#arrivals==before+1,'spawn appeared on a blocked warning')
blocked=false
advance(20)
assert(#arrivals==before+2,'blocked group did not recover')
-- A fixed-count tutorial has no periodic missing-slot repair. Pause through several retries
-- after its warning begins, then resume: the exact requested slot must still arrive once.
tutorial=true
queueSpawn(62)
advance(20.4)
paused=true
advance(23)
assert(#arrivals==before+2,'tutorial spawned during pause')
paused=false
advance(26)
assert(#arrivals==before+3 and arrivals[#arrivals].index==62,'paused tutorial group stranded')
tutorial=false
local bossStart, bossArrivals=#starts,#arrivals
for i=1,30 do queueSpawn(i) end
bossActive=true;countLimit=20
advance(40)
assert(#arrivals-bossArrivals==20,'boss onset did not discard excess pending slots')
for i=bossStart+2,#starts do assert(starts[i].time-starts[i-1].time>=.65-1e-8,'boss arrivals too fast') end
bossActive=false;countLimit=100
respawnReadyAt[70]=42
queueSpawn(70,true)
advance(41.9)
assert(not queuedSet[70],'periodic repair bypassed respawn delay')
advance(42);queueSpawn(70,true);advance(45)
assert(arrivals[#arrivals].index==70,'respawn failed after cooldown')
-- Exercise the actual timed scattered branch too: distinct marks, one-second warning,
-- relocation and pause must still obey the same lifecycle (not just the pure clock tests).
timed=true;waveGeneration+=1;queued={};queuedSet={};pendingGroups={};recentCenters={}
local timedBefore=#arrivals
for i=71,79 do plannedIds[i]='test-enemy';queueSpawn(i) end
advance(49)
assert(#arrivals==timedBefore+9,'timed scattered arrivals lost slots')
blocked=true;queueSpawn(80);advance(51)
assert(#arrivals==timedBefore+9,'timed unsafe mark spawned')
blocked=false;advance(54)
assert(#arrivals==timedBefore+10,'timed relocation did not restart full warning')
-- Actual group drain at every party size: compact groups retain their warning time while
-- their starts speed up linearly, and EVERY individual mark cycles the party's roots.
for _,bossMode in {false,true} do for players=1,4 do
 waveGeneration+=1;events={};queued={};queuedSet={};pendingGroups={};recentCenters={};directorRunning=false
 starts={};arrivals={};groupStarts={};roots={};swarmPlayer=0;bossActive=bossMode;countLimit=100
 for p=1,players do roots[p]={Position=p*100} end
 for i=1,20*players do queueSpawn(i) end
 local began=now;advance(now+12)
 assert(#arrivals==20*players,'multiplayer drain stranded authored arrivals '..players)
 for i=2,#groupStarts do
  local expected=(bossMode and .65 or .22)/players
  assert(groupStarts[i].time-groupStarts[i-1].time>=expected-1e-8,'party bypassed compact-group stagger')
  assert(groupStarts[i].time-groupStarts[i-1].time<=expected+1e-8,'party still bottlenecked by solo group cadence')
 end
 for _,group in groupStarts do assert(group.count<=4,'multiplayer grew compact group size') end
 for i,mark in starts do assert(mark.origin==((i-1)%players+1)*100,'individual mark did not round-robin living members') end
end end
-- The actual reservation-dispatch block also speeds up; three slots per dispatch remains fixed.
for players=1,4 do
 events={};queued={};queuedSet={};pendingGroups={};directorRunning=false;plannedIds={}
 timelineOrders=table.create(80,'enemy');timelineDispatchAt=0
 local began=now
 for tick=0,players-1 do now=math.max(now,timelineDispatchAt)+1e-6;dispatch(players) end
 local reserved=0;for _ in queuedSet do reserved+=1 end
 assert(reserved==3*players,'actual reservation throughput not linear '..players..' got '..reserved)
 local before=reserved;dispatch(players)
 reserved=0;for _ in queuedSet do reserved+=1 end
 assert(reserved==before,'same-time dispatch produced a catch-up burst')
end
print('PASS: cross-flush cadence, moving anchors, sector rotation, hitch pacing, slot deduplication, generation reset, safe-ground retry, full-warning relocation, paused tutorial recovery, boss cadence/cap, respawn cooldown; actual 1-4-player normal/boss group cadence, every-mark root rotation, linear reservation dispatch without burst catchup')
'''

source = (Path(__file__).resolve().parent.parent / "RogueliteZombieChase.server.luau").read_text()
director = source[source.index("local function retryGroup("):source.index("-- Endless: the map")]
director=director.replace('local function telegraphGroup(members, generation, tutorial)\n','local function telegraphGroup(members, generation, tutorial)\n    table.insert(groupStarts,{time=now,count=#members})\n')
dispatch=source[source.index('    if spawnHeld() or activePlayers==0'):source.index('-- Endless bosses (2026-10-03')]
dispatch=dispatch.rsplit('end)',1)[0]
with tempfile.TemporaryDirectory(prefix="roguelite-spawn-tests-") as directory:
    harness = Path(directory) / "SpawnDirectorTests.luau"
    timeline=(Path(__file__).resolve().parent / 'WaveTimeline.luau').read_text()
    harness.write_text('local Timeline=(function()\n'+timeline+'\nend)()\n'+PRELUDE + director+'\nlocal function dispatch(activePlayers)\n'+dispatch+'\nend\n'+ CHECKS)
    subprocess.run([sys.argv[1], str(harness)], check=True)
