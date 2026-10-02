-- Daily quests, the streak and achievements on a saved profile table (QuestConfig,
-- plans/2026-10-01-H-store-and-quests.md; 4 a day and 10-level roads: plans/2026-10-02-K-quests-power-ui.md).
-- Pure logic: no Instances or attributes, so QuestTests runs it on plain tables. ProfileService
-- owns the profile: it calls these, grants what a claim returns and publishes the view. `day` is
-- MonetizationConfig.day() (UTC days).
local S={}
-- QuestConfig, loaded on first use. Tests run fresh copies side by side: S.use(config) sets it.
function S.config()
 if not S.Config then
  -- Never waits: on a server everything in ReplicatedStorage is there from the start.
  local folder=game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteCombat')
  local module=folder and folder:FindFirstChild('QuestConfig')
  assert(module,'QuestConfig is not installed')
  S.Config=require(module)
 end
 return S.Config
end
function S.use(config) S.Config=config end

-- Plan H saves count up to five tiers per road. Each old tier becomes the level with the same
-- target (Slayer tier 3 = 10,000 kills = level 4). Levels skipped in between aren't paid: the old
-- tiers paid more. Runs once per profile (roadsVersion).
local function convertRoads(st)
 local C=S.config()
 for id,tier in st.roads do
  local old=C.LegacyRoadTargets[id];local road=C.RoadById[id]
  if old and road and type(tier)=='number' and tier>0 then
   st.roads[id]=table.find(road.targets,old[math.min(tier,#old)]) or tier
  end
 end
end

-- d.quests, created or filled in on first use and rolled over when the day changes.
function S.state(d,day,userId)
 local C=S.config()
 local st=type(d.quests)=='table' and d.quests or {}
 d.quests=st
 st.stats=type(st.stats)=='table' and st.stats or {}
 for _,k in C.Stats do if type(st.stats[k])~='number' then st.stats[k]=0 end end
 st.streak=type(st.streak)=='table' and st.streak or {}
 local sk=st.streak
 sk.count=sk.count or 0;sk.last=sk.last or 0;sk.best=sk.best or 0
 sk.pending=type(sk.pending)=='table' and sk.pending or {}
 st.roads=type(st.roads)=='table' and st.roads or {}
 if st.roadsVersion~=C.RoadsVersion then convertRoads(st);st.roadsVersion=C.RoadsVersion end
 st.unlocks=type(st.unlocks)=='table' and st.unlocks or {}
 if st.day~=day or type(st.list)~='table' then
  st.day=day;st.list=C.rollDaily(day,userId);st.progress={};st.claimed={};st.allDone=false
 end
 return st
end

-- The streak as of `day`: it is broken (0) once a whole day passed without finishing them all.
function S.streak(st,day) local sk=st.streak;return sk.last>=day-1 and sk.count or 0 end
-- Its spot on the 30-day track: 1..30, 0 with no streak.
function S.position(count) return count>0 and (count-1)%S.config().StreakCycle+1 or 0 end

local function finishedAll(st)
 for _,id in st.list do
  local q=S.config().DailyById[id]
  if not q or (st.progress[id] or 0)<q.target then return false end
 end
 return #st.list>0
end
-- Every daily quest done today for the first time: the streak grows (or starts again at 1).
local function countDay(st,day)
 if st.allDone or not finishedAll(st) then return end
 st.allDone=true
 local sk=st.streak
 if sk.last==day then return end
 sk.count=sk.last==day-1 and sk.count+1 or 1;sk.last=day
 sk.best=math.max(sk.best,sk.count)
 local pos=S.position(sk.count)
 if S.config().StreakByDay[pos] then table.insert(sk.pending,pos) end
end

-- Adds n to a lifetime stat and to today's quests that count it. Returns true when anything changed.
function S.event(d,day,userId,stat,n)
 n=math.floor(tonumber(n) or 0)
 if n<=0 or type(stat)~='string' then return false end
 local st=S.state(d,day,userId)
 if st.stats[stat]==nil then return false end
 st.stats[stat]+=n
 for _,id in st.list do
  local q=S.config().DailyById[id]
  if q and q.stat==stat then st.progress[id]=math.min(q.target,(st.progress[id] or 0)+n) end
 end
 countDay(st,day)
 return true
end
-- A run counts the first time its stint clears a wave.
function S.runStarted(d,day,userId,stint)
 local st=S.state(d,day,userId)
 if type(stint)~='string' or st.runStint==stint then return false end
 st.runStint=stint
 return S.event(d,day,userId,'runs',1)
end

-- Lifetime stat value, including the derived ones: the best streak, and Achiever's count of levels
-- claimed on every other road plus unlocks claimed.
function S.stat(st,stat)
 if stat=='bestStreak' then return st.streak.best end
 if stat=='achievements' then
  local n=0
  for id,level in st.roads do if id~='Achiever' and type(level)=='number' then n+=level end end
  for _,claimed in st.unlocks do if claimed==true then n+=1 end end
  return n
 end
 return st.stats[stat] or 0
end

-- Progress toward an unlock: have, need. Map records come from the profile (bestWaves keys are
-- 'PineValley' or 'PineValley/Hard'; mapWins the same).
local function onMap(key,map) return map=='*' or key==map or string.sub(key,1,#map+1)==map..'/' end
function S.unlockProgress(d,st,u)
 local g=u.goal
 if g.stat then return math.min(S.stat(st,g.stat),g.target),g.target end
 if g.win then
  for key in d.mapWins or {} do if onMap(key,g.win) then return 1,1 end end
  return 0,1
 end
 local best=0
 for key,w in d.bestWaves or {} do if onMap(key,g.best) and w>best then best=w end end
 return math.min(best,g.wave),g.wave
end

-- What the client draws (JSON on the ProfileQuests attribute).
function S.view(d,day,userId,resetIn)
 local C=S.config();local st=S.state(d,day,userId)
 local daily={}
 for i,id in st.list do daily[i]={id=id,progress=st.progress[id] or 0,claimed=st.claimed[id]==true} end
 local unlocks={}
 for _,u in C.Unlocks do local have,need=S.unlockProgress(d,st,u);unlocks[u.id]={have=have,need=need,claimed=st.unlocks[u.id]==true} end
 local stats={};for k,v in st.stats do stats[k]=v end
 stats.bestStreak=st.streak.best;stats.achievements=S.stat(st,'achievements')
 local count=S.streak(st,day)
 return {day=day,resetIn=resetIn,daily=daily,allDone=st.allDone==true,
  streak={count=count,position=S.position(count),best=st.streak.best,today=st.streak.last==day,pending=table.clone(st.streak.pending)},
  stats=stats,roads=table.clone(st.roads),unlocks=unlocks}
end
-- How many rewards are waiting for CLAIM (the badge on the Quests buttons).
function S.claimable(d,day,userId)
 local C=S.config();local st=S.state(d,day,userId);local n=#st.streak.pending
 for _,id in st.list do local q=C.DailyById[id];if q and not st.claimed[id] and (st.progress[id] or 0)>=q.target then n+=1 end end
 for _,r in C.Roads do local t=(st.roads[r.id] or 0)+1;if r.targets[t] and S.stat(st,r.stat)>=r.targets[t] then n+=1 end end
 for _,u in C.Unlocks do if not st.unlocks[u.id] then local have,need=S.unlockProgress(d,st,u);if have>=need then n+=1 end end end
 return n
end

-- Claims. Each returns ok, message and the grant ({emeralds, chests, class, weapon (name),
-- armorSet}) for ProfileService to hand out. Nothing is marked claimed unless ok.
local function merge(a,b)
 local g={emeralds=(a.emeralds or 0)+(b and b.emeralds or 0),chests={}}
 for k,n in a.chests or {} do g.chests[k]=(g.chests[k] or 0)+n end
 for k,n in b and b.chests or {} do g.chests[k]=(g.chests[k] or 0)+n end
 return g
end
function S.claimQuest(d,day,userId,index)
 local st=S.state(d,day,userId)
 local id=type(index)=='number' and st.list[index];local q=id and S.config().DailyById[id]
 if not q then return false,'Unknown quest' end
 if st.claimed[id] then return false,'Already claimed' end
 if (st.progress[id] or 0)<q.target then return false,'Not finished yet' end
 st.claimed[id]=true;st.stats.quests+=1
 return true,q.title..' complete!',merge(q)
end
function S.claimStreak(d,day,userId,milestone)
 local st=S.state(d,day,userId);local pending=st.streak.pending
 local at=table.find(pending,milestone)
 local s=at and S.config().StreakByDay[milestone]
 if not s then return false,'Nothing to claim there' end
 table.remove(pending,at)
 return true,'Day '..milestone..' streak reward!',merge(s)
end
function S.claimRoad(d,day,userId,roadId)
 local st=S.state(d,day,userId);local r=type(roadId)=='string' and S.config().RoadById[roadId]
 if not r then return false,'Unknown achievement' end
 local tier=(st.roads[r.id] or 0)+1;local target=r.targets[tier]
 if not target then return false,'All tiers done' end
 if S.stat(st,r.stat)<target then return false,'Not finished yet' end
 st.roads[r.id]=tier
 return true,r.name..' · '..S.config().TierNames[tier]..' complete!',merge(S.config().TierRewards[tier])
end
-- ownsClass(name) -> bool: an unlock for a class already owned pays emeralds instead.
function S.claimUnlock(d,day,userId,id,ownsClass)
 local st=S.state(d,day,userId);local u=type(id)=='string' and S.config().UnlockById[id]
 if not u then return false,'Unknown achievement' end
 if st.unlocks[u.id] then return false,'Already claimed' end
 local have,need=S.unlockProgress(d,st,u)
 if have<need then return false,'Not finished yet' end
 st.unlocks[u.id]=true
 local r=u.reward
 if r.class then
  if ownsClass and ownsClass(r.class) then return true,r.class..' already unlocked: +'..S.config().ClassRefund..' emeralds',{emeralds=S.config().ClassRefund} end
  return true,r.class..' class unlocked!',{class=r.class}
 end
 if r.weapon then return true,r.weapon..' unlocked!',{weapon=r.weapon} end
 return true,r.armorSet..' armor set unlocked!',{armorSet=r.armorSet}
end
return S
