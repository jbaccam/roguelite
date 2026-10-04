-- Daily quests, the streak and achievements on a saved profile table (QuestConfig,
-- plans/2026-10-01-H-store-and-quests.md; 4 a day and 10-level roads: plans/2026-10-02-K-quests-power-ui.md;
-- weekly quests and feats: plans/2026-10-02-M-feats-weekly-roads.md).
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

-- Map record keys are 'PineValley' (Normal) or 'PineValley/Hard': the key's difficulty rank.
local function keyRank(key)
 local diff=string.match(key,'/(.+)$')
 return diff and S.config().DiffRank[diff] or 1
end
-- What the weekly roll may hand out (plan M): Hard needs a win anywhere, Nightmare a Hard win.
function S.canPlay(d)
 local top=0
 for key,won in d.mapWins or {} do if won then top=math.max(top,keyRank(key)) end end
 return {Hard=top>=1,Nightmare=top>=2}
end

-- d.quests, created or filled in on first use and rolled over when the day or week changes.
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
 -- Plan M: the hardest difficulty won solo / without going down, classes that won, feats claimed.
 st.wonWith=type(st.wonWith)=='table' and st.wonWith or {}
 st.classWins=type(st.classWins)=='table' and st.classWins or {}
 st.feats=type(st.feats)=='table' and st.feats or {}
 if st.day~=day or type(st.list)~='table' then
  st.day=day;st.list=C.rollDaily(day,userId);st.progress={};st.claimed={};st.allDone=false
 end
 -- The week's list is saved when it rolls, so unlocking Hard midweek never changes it.
 local week=C.week(day)
 if st.week~=week or type(st.weekList)~='table' then
  st.week=week;st.weekList=C.rollWeekly(week,userId,S.canPlay(d));st.weekProgress={};st.weekClaimed={}
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

-- n more of a lifetime stat, and for today's and this week's quests that count it (capped at
-- their targets).
local function track(st,stat,n)
 local C=S.config()
 st.stats[stat]+=n
 for _,id in st.list do
  local q=C.DailyById[id]
  if q and q.stat==stat then st.progress[id]=math.min(q.target,(st.progress[id] or 0)+n) end
 end
 for _,id in st.weekList do
  local q=C.WeeklyById[id]
  if q and q.stat==stat then st.weekProgress[id]=math.min(q.target,(st.weekProgress[id] or 0)+n) end
 end
end
-- Adds n to a lifetime stat and to the quests that count it. Returns true when anything changed.
function S.event(d,day,userId,stat,n)
 n=math.floor(tonumber(n) or 0)
 if n<=0 or type(stat)~='string' then return false end
 local st=S.state(d,day,userId)
 if st.stats[stat]==nil then return false end
 track(st,stat,n)
 countDay(st,day)
 return true
end
-- A map win (plan M), from the server's run state: diff (difficulty id), solo (the only member at
-- every wave clear from wave 1), flawless (no death from wave 1), class (the class it was won with).
function S.win(d,day,userId,info)
 if type(info)~='table' then return false end
 local C=S.config();local st=S.state(d,day,userId)
 local rank=C.DiffRank[info.diff] or 1
 if rank>=2 then track(st,'hardWins',1) end
 if rank>=3 then track(st,'nightmareWins',1) end
 if info.flawless==true then track(st,'flawlessWins',1);st.wonWith.flawless=math.max(st.wonWith.flawless or 0,rank) end
 if info.solo==true then st.wonWith.solo=math.max(st.wonWith.solo or 0,rank) end
 if type(info.class)=='string' and #info.class<=24 then st.classWins[info.class]=true end
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
-- claimed on every other road plus unlocks and feats claimed.
function S.stat(st,stat)
 if stat=='bestStreak' then return st.streak.best end
 if stat=='achievements' then
  local n=0
  for id,level in st.roads do if id~='Achiever' and type(level)=='number' then n+=level end end
  for _,claimed in st.unlocks do if claimed==true then n+=1 end end
  for _,claimed in st.feats do if claimed==true then n+=1 end end
  return n
 end
 return st.stats[stat] or 0
end

-- Progress toward an unlock's or a feat's goal: have, need. Map records come from the profile
-- (bestWaves keys are 'PineValley' or 'PineValley/Hard'; mapWins the same). diff = that
-- difficulty or harder; solo / flawless read the wins QuestService.win recorded (any map).
local function onMap(key,map) return map=='*' or key==map or string.sub(key,1,#map+1)==map..'/' end
function S.goalProgress(d,st,g)
 if g.stat then return math.min(S.stat(st,g.stat),g.target),g.target end
 if g.classes then
  local n=0;for _,won in st.classWins do if won==true then n+=1 end end
  return math.min(n,g.classes),g.classes
 end
 local need=S.config().DiffRank[g.diff] or 1
 if g.win then
  if g.solo then return (st.wonWith.solo or 0)>=need and 1 or 0,1 end
  if g.flawless then return (st.wonWith.flawless or 0)>=need and 1 or 0,1 end
  for key,won in d.mapWins or {} do if won and onMap(key,g.win) and keyRank(key)>=need then return 1,1 end end
  return 0,1
 end
 local best=0
 for key,w in d.bestWaves or {} do if onMap(key,g.best) and keyRank(key)>=need and w>best then best=w end end
 return math.min(best,g.wave),g.wave
end
function S.unlockProgress(d,st,u) return S.goalProgress(d,st,u.goal) end

-- What the client draws (JSON on the ProfileQuests attribute).
function S.view(d,day,userId,resetIn)
 local C=S.config();local st=S.state(d,day,userId)
 local daily={}
 for i,id in st.list do daily[i]={id=id,progress=st.progress[id] or 0,claimed=st.claimed[id]==true} end
 local unlocks={}
 for _,u in C.Unlocks do local have,need=S.unlockProgress(d,st,u);unlocks[u.id]={have=have,need=need,claimed=st.unlocks[u.id]==true} end
 local feats={}
 for _,f in C.Feats do local have,need=S.goalProgress(d,st,f.goal);feats[f.id]={have=have,need=need,claimed=st.feats[f.id]==true} end
 local weekly={}
 for i,id in st.weekList do weekly[i]={id=id,progress=st.weekProgress[id] or 0,claimed=st.weekClaimed[id]==true} end
 local stats={};for k,v in st.stats do stats[k]=v end
 stats.bestStreak=st.streak.best;stats.achievements=S.stat(st,'achievements')
 local count=S.streak(st,day)
 return {day=day,resetIn=resetIn,daily=daily,allDone=st.allDone==true,
  streak={count=count,position=S.position(count),best=st.streak.best,today=st.streak.last==day,pending=table.clone(st.streak.pending)},
  stats=stats,roads=table.clone(st.roads),unlocks=unlocks,
  weekly=weekly,weekResetIn=resetIn and C.weekResetIn(day,resetIn),feats=feats}
end
-- How many rewards are waiting for CLAIM (the badge on the Quests buttons).
function S.claimable(d,day,userId)
 local C=S.config();local st=S.state(d,day,userId);local n=#st.streak.pending
 for _,id in st.list do local q=C.DailyById[id];if q and not st.claimed[id] and (st.progress[id] or 0)>=q.target then n+=1 end end
 for _,id in st.weekList do local q=C.WeeklyById[id];if q and not st.weekClaimed[id] and (st.weekProgress[id] or 0)>=q.target then n+=1 end end
 for _,r in C.Roads do local t=(st.roads[r.id] or 0)+1;if r.targets[t] and S.stat(st,r.stat)>=r.targets[t] then n+=1 end end
 for _,u in C.Unlocks do if not st.unlocks[u.id] then local have,need=S.unlockProgress(d,st,u);if have>=need then n+=1 end end end
 for _,f in C.Feats do if not st.feats[f.id] then local have,need=S.goalProgress(d,st,f.goal);if have>=need then n+=1 end end end
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
 st.claimed[id]=true;track(st,'quests',1) -- Questor, and the weekly "Finish 12 Daily Quests"
 return true,q.title..' complete!',merge(q)
end
-- Weekly quest `index` (1-3) of this week (plan M).
function S.claimWeekly(d,day,userId,index)
 local st=S.state(d,day,userId)
 local id=type(index)=='number' and st.weekList[index];local q=id and S.config().WeeklyById[id]
 if not q then return false,'Unknown quest' end
 if st.weekClaimed[id] then return false,'Already claimed' end
 if (st.weekProgress[id] or 0)<q.target then return false,'Not finished yet' end
 st.weekClaimed[id]=true;track(st,'weeklies',1) -- Weekly Warrior
 return true,q.title..' complete!',merge(q)
end
-- A feat, once (plan M): pays its stars' reward.
function S.claimFeat(d,day,userId,id)
 local C=S.config();local st=S.state(d,day,userId)
 local f=type(id)=='string' and C.FeatById[id]
 if not f then return false,'Unknown feat' end
 if st.feats[f.id] then return false,'Already claimed' end
 local have,need=S.goalProgress(d,st,f.goal)
 if have<need then return false,'Not finished yet' end
 st.feats[f.id]=true
 return true,f.name..' complete!',merge(C.FeatRewards[f.stars])
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

-- CLAIM ALL (user, 2026-10-03): every ready reward of one Quests tab in one request. Each goes
-- through its own claim above, so each is checked again and nothing unready is paid. group: 'Daily'
-- (quests + streak milestones), 'Weekly' or 'Achievements' (feats, unlocks, then every ready road
-- level; Achiever counts the others' claims, so roads repeat until nothing more is ready).
-- canUnlock(u) -> false skips an unlock that can't be paid yet (a weapon not in the game).
-- Returns ok, message, grants (one per claim, as the single claims return them) and the total
-- ({emeralds, chests, count}). Example: 3 daily quests of 40 + 60 + 100 -> count 3, emeralds 200.
function S.claimAll(d,day,userId,group,ownsClass,canUnlock)
 local C=S.config();local st=S.state(d,day,userId)
 local grants={}
 local function take(ok,_,g) if ok then table.insert(grants,g) end;return ok end
 if group=='Daily' then
  for i in st.list do take(S.claimQuest(d,day,userId,i)) end
  for _,m in table.clone(st.streak.pending) do take(S.claimStreak(d,day,userId,m)) end
 elseif group=='Weekly' then
  for i in st.weekList do take(S.claimWeekly(d,day,userId,i)) end
 elseif group=='Achievements' then
  for _,f in C.Feats do take(S.claimFeat(d,day,userId,f.id)) end
  for _,u in C.Unlocks do if not canUnlock or canUnlock(u) then take(S.claimUnlock(d,day,userId,u.id,ownsClass)) end end
  for _=1,50 do
   local more=false
   for _,r in C.Roads do if take(S.claimRoad(d,day,userId,r.id)) then more=true end end
   if not more then break end
  end
 else return false,'Unknown tab' end
 if #grants==0 then return false,'Nothing to claim' end
 local total=merge({});total.count=#grants
 for _,g in grants do
  total.emeralds+=g.emeralds or 0
  for k,n in g.chests or {} do total.chests[k]=(total.chests[k] or 0)+n end
 end
 -- 'Claimed 3 rewards · +200 emeralds · 1 Gold Chest'
 local parts={'Claimed '..#grants..(#grants==1 and ' reward' or ' rewards')}
 if total.emeralds>0 then table.insert(parts,'+'..C.comma(total.emeralds)..' emeralds') end
 for _,kind in {'Wooden','Silver','Gold','Magical','Legendary'} do
  local n=total.chests[kind];if n and n>0 then table.insert(parts,n..' '..kind..(n==1 and ' Chest' or ' Chests')) end
 end
 for _,g in grants do
  if g.class then table.insert(parts,g.class..' class') elseif g.weapon then table.insert(parts,g.weapon)
  elseif g.armorSet then table.insert(parts,g.armorSet..' armor') end
 end
 return true,table.concat(parts,' · '),grants,total
end
return S
