-- Daily quests, the daily streak and achievements (plans/2026-10-01-H-store-and-quests.md; 4 a day
-- from 16, and 10-level roads: plans/2026-10-02-K-quests-power-ui.md; weekly quests, feats and 19
-- roads: plans/2026-10-02-M-feats-weekly-roads.md). Shared data: QuestService (server) checks
-- progress and grants, the lobby UI draws from it. Rewards: emeralds (counted as earned), chests by
-- ChestConfig id, a class, a weapon by WeaponCatalog name, or a full armor set by ArmorCatalog id.
local Q={}
local function rgb(r,g,b) return Color3.fromRGB(r,g,b) end

-- Art: ui/assets/upgrades, ui/assets/hud (the user's plan K icons: hud/asset-ids.json) and the
-- egg merchant's egg. Keyed by stat, so a quest or road finds its icon by what it counts.
Q.Icons={
 waves='rbxassetid://80556274645944', -- Armor (shield)
 kills='rbxassetid://105663077535579', -- Damage (fist)
 runs='rbxassetid://119231770241307', -- play portal
 bosses='rbxassetid://140040643870888', -- boss teeth (hud/boss-teeth.png, 2026-10-02)
 chests='rbxassetid://128369126123154', -- chest
 earn='rbxassetid://107205947937384', -- emerald
 upgrades='rbxassetid://128990045041232', -- anvil
 wins='rbxassetid://129045264697854', -- target
 deepRuns='rbxassetid://129045264697854', -- target
 streak='rbxassetid://113526779615647', -- streak flame
 bestStreak='rbxassetid://133092049631498', -- calendar
 quests='rbxassetid://85014504299735', -- scroll
 achievements='rbxassetid://79366861483753', -- achievements
 utilityKills='rbxassetid://133538769433103', -- gear (Utility Power)
 meleeKills='rbxassetid://95614914114816', -- Melee Damage
 rangedKills='rbxassetid://79016661829505', -- Ranged Damage
 minutes='rbxassetid://79916703515403', -- clock
 damage='rbxassetid://108283829124468', -- sword burst
 levels='rbxassetid://101475186887359', -- XP
 shards='rbxassetid://129322350142524', -- shard bag
 buys='rbxassetid://113789432822588', -- store bag
 eggs='rbxassetid://115158817562855', -- pet egg (hud/pet-egg.png)
 title='rbxassetid://87815515863495', -- ribbon (titles, plan K part 4)
 speed='rbxassetid://117216104224040', -- wings (Move Speed)
 frost='rbxassetid://104227388119878', -- frost streaks (Attack Speed)
 heart='rbxassetid://87748663271804', -- Max HP
 -- Plan M. The user makes the solo / no-down / Nightmare / classes art; until then each borrows one.
 solo='rbxassetid://138623258102251', -- profile (hud/profile.png) until the lone wolf arrives
 flawless='rbxassetid://87748663271804', -- Max HP heart until the shield arrives
 nightmare='rbxassetid://140040643870888', -- boss teeth until the skull arrives
 classes='rbxassetid://79366861483753', -- achievements until the masks arrive
 weekly='rbxassetid://133092049631498', -- calendar
}
-- Stats that share another stat's art.
for stat,art in {hardWins='wins',nightmareWins='nightmare',flawlessWins='flawless',wave25Runs='waves',weeklies='weekly'} do Q.Icons[stat]=Q.Icons[art] end

-- Daily pool. Every day rolls DailyPlay run quests (`play`: they need a run), then the rest from
-- everything left, by weight. color: the card's header band. short: the tracker's name.
Q.Daily={
 {id='Waves',stat='waves',target=10,emeralds=60,title='Survive 10 Waves',play=true,weight=3,color=rgb(64,150,240)},
 {id='Kills',stat='kills',target=300,emeralds=60,title='Defeat 300 Enemies',play=true,weight=3,color=rgb(232,74,64)},
 {id='Runs',stat='runs',target=3,emeralds=50,title='Play 3 Runs',play=true,weight=3,color=rgb(156,96,236)},
 {id='Earn',stat='earn',target=150,emeralds=50,title='Earn 150 Emeralds',play=true,weight=2,color=rgb(40,180,96)},
 {id='Boss',stat='bosses',target=1,emeralds=80,chests={Silver=1},title='Defeat a Map Boss',play=true,weight=1,color=rgb(236,140,36)},
 {id='DeepRun',stat='deepRuns',target=1,emeralds=60,title='Reach Wave 10 in One Run',short='Reach Wave 10',play=true,weight=2,color=rgb(30,150,170)},
 {id='Minutes',stat='minutes',target=20,emeralds=50,title='Play 20 Minutes',play=true,weight=2,color=rgb(214,150,40)},
 {id='Levels',stat='levels',target=15,emeralds=50,title='Level Up 15 Times',play=true,weight=2,color=rgb(110,90,230)},
 {id='Shards',stat='shards',target=300,emeralds=50,title='Collect 300 Shards',play=true,weight=2,color=rgb(70,170,230)},
 {id='Melee',stat='meleeKills',target=150,emeralds=60,title='Defeat 150 Enemies with Melee',short='150 Melee Kills',play=true,weight=2,color=rgb(200,70,50)},
 {id='Ranged',stat='rangedKills',target=150,emeralds=60,title='Defeat 150 Enemies with Ranged',short='150 Ranged Kills',play=true,weight=2,color=rgb(60,120,210)},
 {id='Buys',stat='buys',target=5,emeralds=50,title='Buy 5 Shop Items',play=true,weight=2,color=rgb(190,110,40)},
 {id='Damage',stat='damage',target=50000,emeralds=60,title='Deal 50,000 Damage',short='Deal 50K Damage',play=true,weight=2,color=rgb(220,60,90)},
 {id='Chests',stat='chests',target=3,emeralds=40,title='Open 3 Chests',weight=2,color=rgb(214,164,40)},
 {id='Upgrade',stat='upgrades',target=1,emeralds=40,title='Upgrade Any Item',weight=2,color=rgb(110,128,140)},
 {id='Hatch',stat='eggs',target=1,emeralds=40,title='Hatch an Egg',weight=1,color=rgb(150,200,60)},
}
Q.DailyById={};for _,q in Q.Daily do Q.DailyById[q.id]=q end
Q.DailyCount=4
Q.DailyPlay=3

-- The day's quests for one player: the same four all day (seeded by day and user id).
function Q.rollDaily(day,userId)
 local r=Random.new(day*7919+(userId or 0)%104729)
 local picked,out={},{}
 local function pick(filter)
  local total=0
  for _,q in Q.Daily do if not picked[q.id] and filter(q) then total+=q.weight end end
  if total<=0 then return end
  local x=r:NextNumber()*total
  for _,q in Q.Daily do
   if not picked[q.id] and filter(q) then
    x-=q.weight
    if x<=0 then picked[q.id]=true;table.insert(out,q.id);return end
   end
  end
 end
 for _=1,Q.DailyPlay do pick(function(q) return q.play end) end
 for _=Q.DailyPlay+1,Q.DailyCount do pick(function() return true end) end
 return out
end

-- Streak: a day counts when every daily quest is finished. Missing a day starts again at 0. Each
-- reward waits for CLAIM even if the streak breaks later. After day 30 the track repeats.
Q.StreakCycle=30
Q.Streak={
 {day=1,emeralds=50},{day=3,chests={Silver=1}},{day=7,chests={Gold=1}},{day=10,emeralds=250},
 {day=15,chests={Gold=2}},{day=20,chests={Magical=1}},{day=30,chests={Legendary=1}},
}
Q.StreakByDay={};for _,s in Q.Streak do Q.StreakByDay[s.day]=s end

-- Weekly quests (plan M): 3 a week, new every Monday 00:00 UTC. Two from Weekly (each about 5-8
-- runs), then one from WeeklyHard that the player can do when the week rolls (needs: 'Hard' = a win
-- on Normal anywhere, 'Nightmare' = a win on Hard anywhere). The list is saved when it rolls.
Q.Weekly={
 {id='Wins',stat='wins',target=3,emeralds=300,title='Win 3 Maps',color=rgb(64,150,240)},
 {id='Bosses',stat='bosses',target=5,emeralds=300,title='Defeat 5 Map Bosses',color=rgb(236,140,36)},
 {id='Waves',stat='waves',target=100,emeralds=300,title='Survive 100 Waves',color=rgb(30,150,170)},
 {id='Runs',stat='runs',target=10,emeralds=300,title='Play 10 Runs',color=rgb(156,96,236)},
 {id='Hours',stat='minutes',target=120,emeralds=300,title='Play 2 Hours',color=rgb(214,150,40)},
 {id='DeepRuns',stat='deepRuns',target=5,emeralds=300,title='Reach Wave 10 in 5 Runs',color=rgb(40,180,96)},
 {id='Dailies',stat='quests',target=12,emeralds=300,title='Finish 12 Daily Quests',color=rgb(110,90,230)},
 {id='Levels',stat='levels',target=100,emeralds=300,title='Level Up 100 Times',color=rgb(70,170,230)},
 {id='Chests',stat='chests',target=10,emeralds=300,title='Open 10 Chests',color=rgb(214,164,40)},
}
Q.WeeklyHard={
 {id='HardWins',stat='hardWins',target=3,title='Win 3 Maps on Hard',needs='Hard'},
 {id='NightmareWin',stat='nightmareWins',target=1,title='Win a Map on Nightmare',needs='Nightmare'},
 {id='Flawless',stat='flawlessWins',target=1,title='Win Without Going Down'},
 {id='BossHunt',stat='bosses',target=12,title='Defeat 12 Map Bosses'},
 {id='WinMany',stat='wins',target=8,title='Win 8 Maps'},
 {id='Endless',stat='wave25Runs',target=1,title='Reach Wave 25 in One Run'},
}
for _,q in Q.WeeklyHard do q.hard=true;q.emeralds=600;q.chests={Gold=1};q.color=rgb(200,64,28) end
Q.WeeklyById={}
for _,list in {Q.Weekly,Q.WeeklyHard} do for _,q in list do Q.WeeklyById[q.id]=q end end
Q.WeeklyCount=3
-- Week number: UTC day 0 (1970-01-01) was a Thursday, so +3 starts every week on a Monday.
function Q.week(day) return (day+3)//7 end
-- Seconds until next Monday 00:00 UTC, given the seconds left today.
function Q.weekResetIn(day,todayLeft) return (6-(day+3)%7)*86400+todayLeft end
-- The week's quests for one player: 2 normal, then 1 hard they can do. can = {Hard=bool, Nightmare=bool}.
function Q.rollWeekly(week,userId,can)
 local r=Random.new(week*104723+(userId or 0)%99991)
 local out={}
 local function pick(list,ok)
  local pool={}
  for _,q in list do if ok(q) and not table.find(out,q.id) then table.insert(pool,q) end end
  if #pool>0 then table.insert(out,pool[r:NextInteger(1,#pool)].id) end
 end
 for _=1,Q.WeeklyCount-1 do pick(Q.Weekly,function() return true end) end
 pick(Q.WeeklyHard,function(q) return q.needs==nil or (can and can[q.needs])==true end)
 return out
end

-- Roads: lifetime stats with ten levels each. Each level is also a future title ("Slayer Skilled").
Q.TierNames={'Rookie','Beginner','Intermediate','Skilled','Advanced','Expert','Elite','Master','Grandmaster','Legend'}
Q.Levels=#Q.TierNames
Q.TierRewards={
 {emeralds=50}, -- 25 until plan M
 {emeralds=50,chests={Silver=1}},
 {emeralds=100,chests={Silver=1}},
 {emeralds=200,chests={Gold=1}},
 {emeralds=300,chests={Gold=1}},
 {emeralds=500,chests={Magical=1}},
 {emeralds=700,chests={Magical=1}},
 {emeralds=1000,chests={Legendary=1}},
 {emeralds=1500,chests={Legendary=1}},
 {emeralds=2500,chests={Legendary=2}},
}
-- Rank colours by level (QuestsUI): grey, bronze, silver, gold, emerald, blue, purple, red, then
-- Grandmaster dark with a gold rim and Legend dark red with a pulsing red rim.
Q.TierColors={rgb(150,160,166),rgb(214,132,58),rgb(200,210,218),rgb(255,200,60),rgb(70,226,120),
 rgb(60,150,255),rgb(176,100,255),rgb(255,64,96),rgb(60,46,72),rgb(120,14,36)}
-- format: how the goal number reads ('hours' for minutes, 'short' for big numbers like 250K).
Q.Roads={
 {id='Survivor',name='Survivor',stat='waves',goal='Survive %s waves',targets={10,25,100,300,600,1000,2000,3000,5000,10000}},
 {id='Slayer',name='Slayer',stat='kills',goal='Defeat %s enemies',targets={100,500,2500,10000,25000,50000,100000,200000,500000,1000000}},
 {id='BossHunter',name='Boss Hunter',stat='bosses',goal='Defeat %s map bosses',targets={1,3,5,15,30,50,100,150,300,500}},
 {id='Champion',name='Champion',stat='wins',goal='Win %s maps',targets={1,2,3,5,10,25,40,60,100,200}},
 {id='Collector',name='Collector',stat='chests',goal='Open %s chests',targets={3,5,25,50,100,300,500,1000,2000,5000}},
 {id='Dedicated',name='Dedicated',stat='bestStreak',goal='Reach a %s-day streak',targets={2,3,5,7,14,21,30,45,60,100}},
 {id='Upgrader',name='Upgrader',stat='upgrades',goal='Upgrade items %s times',targets={1,3,5,10,20,35,50,80,120,200}},
 {id='Questor',name='Questor',stat='quests',goal='Finish %s daily quests',targets={3,5,20,40,60,100,150,250,365,600}},
 {id='Playtime',name='Playtime',stat='minutes',goal='Play %s in runs',format='hours',targets={30,60,180,360,600,1200,2400,4500,9000,18000}},
 {id='Hatcher',name='Hatcher',stat='eggs',goal='Hatch %s eggs',targets={1,3,5,10,25,50,100,200,350,500}},
 {id='Rich',name='Rich',stat='earn',goal='Earn %s emeralds in runs',targets={500,1500,5000,10000,25000,50000,100000,200000,400000,1000000}},
 {id='Runner',name='Runner',stat='runs',goal='Play %s runs',targets={3,10,25,50,100,200,350,500,750,1000}},
 {id='HeavyHitter',name='Heavy Hitter',stat='damage',goal='Deal %s damage',format='short',targets={5e4,2.5e5,1e6,3e6,1e7,3e7,1e8,3e8,1e9,3e9}},
 {id='Leveler',name='Leveler',stat='levels',goal='Level up %s times',targets={10,50,150,400,1000,2000,4000,7500,12000,20000}},
 -- Plan M. Shard Hoarder's targets are first guesses, like the Shards daily.
 {id='Bruiser',name='Bruiser',stat='meleeKills',goal='Defeat %s enemies with melee',targets={50,250,1000,5000,12500,25000,50000,100000,250000,500000}},
 {id='Sharpshooter',name='Sharpshooter',stat='rangedKills',goal='Defeat %s enemies with ranged',targets={50,250,1000,5000,12500,25000,50000,100000,250000,500000}},
 {id='ShardHoarder',name='Shard Hoarder',stat='shards',goal='Collect %s shards',format='short',targets={300,1500,5000,15000,40000,100000,200000,400000,750000,1500000}},
 {id='WeeklyWarrior',name='Weekly Warrior',stat='weeklies',goal='Finish %s weekly quests',targets={1,3,6,10,20,35,52,80,120,156}},
 -- Last level = everything else: 18 roads x 10 + 5 unlocks + 12 feats.
 {id='Achiever',name='Achiever',stat='achievements',goal='Reach %s achievement levels',targets={3,10,25,40,60,85,110,140,170,197}},
}
Q.RoadById={};for _,r in Q.Roads do Q.RoadById[r.id]=r end
-- Plan H's five tiers per road. QuestService converts saves that still count those (roadsVersion).
Q.LegacyRoadTargets={
 Survivor={25,100,300,1000,3000},Slayer={500,2500,10000,50000,200000},BossHunter={1,5,15,50,150},
 Champion={1,3,10,25,60},Collector={5,25,100,300,1000},Dedicated={3,7,14,30,60},
 Upgrader={1,5,20,50,120},Questor={5,20,60,150,365},
}
Q.RoadsVersion=2

-- One-time unlocks. goal: best = reach `wave` on that map (any difficulty, '*' = any map),
-- win = win that map (any difficulty), stat = a lifetime stat reaching `target`.
Q.Unlocks={
 {id='WaveRider',name='Wave Rider',desc='Reach wave 10 on Pine Valley',icon='speed',goal={best='PineValley',wave=10},reward={class='Thrower'}},
 {id='ValleyVictor',name='Valley Victor',desc='Win Pine Valley',icon='wins',goal={win='PineValley'},reward={class='Juggler'}},
 {id='HandyWork',name='Handy Work',desc='Defeat 1,000 enemies with Utility weapons',icon='utilityKills',goal={stat='utilityKills',target=1000},reward={class='Handyman'}},
 {id='FrostBreaker',name='Frost Breaker',desc='Win Frozen Pass',icon='frost',goal={win='FrozenPass'},reward={weapon='Mjolnir'}},
 {id='EndlessLegend',name='Endless Legend',desc='Reach wave 30 on any map',icon='heart',goal={best='*',wave=30},reward={armorSet='Samurai'}},
}
Q.UnlockById={};for _,u in Q.Unlocks do Q.UnlockById[u.id]=u end
-- An unlock achievement for a class you already own pays its emerald price instead.
Q.ClassRefund=400

-- Difficulty ranks for goals: `diff` means that difficulty or harder.
Q.DiffRank={Normal=1,Hard=2,Nightmare=3}
-- Feats (plan M): one-time challenges, paid by stars. Goals as for unlocks, plus `diff`, and
-- solo / flawless (read from the wins QuestService.win recorded; a goal uses one of them, never
-- both) and classes = how many classes have won a map.
Q.FeatRewards={{emeralds=300,chests={Silver=1}},{emeralds=750,chests={Gold=1}},{emeralds=1500,chests={Magical=1}}}
Q.Feats={
 {id='LoneWolf',name='Lone Wolf',desc='Win a map solo',stars=1,icon='solo',goal={win='*',solo=true}},
 {id='StepItUp',name='Step It Up',desc='Win any map on Hard',stars=1,icon='wins',goal={win='*',diff='Hard'}},
 {id='JackOfAllTrades',name='Jack of All Trades',desc='Win with 3 different classes',stars=1,icon='classes',goal={classes=3}},
 {id='Untouchable',name='Untouchable',desc='Win a map without going down',stars=2,icon='flawless',goal={win='*',flawless=true}},
 {id='LoneLegend',name='Lone Legend',desc='Win solo on Hard',stars=2,icon='solo',goal={win='*',diff='Hard',solo=true}},
 {id='NightmareWalker',name='Nightmare Walker',desc='Win any map on Nightmare',stars=2,icon='nightmare',goal={win='*',diff='Nightmare'}},
 {id='DeepDiver',name='Deep Diver',desc='Reach wave 40 on any map',stars=2,icon='waves',goal={best='*',wave=40}},
 {id='Abyss',name='Abyss',desc='Reach wave 50 on any map',stars=3,icon='waves',goal={best='*',wave=50}},
 {id='NightShift',name='Night Shift',desc='Reach wave 30 on Nightmare',stars=3,icon='nightmare',goal={best='*',diff='Nightmare',wave=30}},
 {id='MasterOfAll',name='Master of All',desc='Win with all 6 classes',stars=3,icon='classes',goal={classes=6}},
 {id='FlawlessNightmare',name='Flawless Nightmare',desc='Win on Nightmare without going down',stars=3,icon='flawless',goal={win='*',diff='Nightmare',flawless=true}},
 {id='DragonSlayer',name='Dragon Slayer',desc='Win Volcanic Crater on Nightmare',stars=3,icon='bosses',goal={win='VolcanicCrater',diff='Nightmare'}},
}
Q.FeatById={};for _,f in Q.Feats do Q.FeatById[f.id]=f end
-- Diamond colours by stars: bronze, silver, gold.
Q.StarColors={rgb(214,132,58),rgb(200,210,218),rgb(255,200,60)}

-- Lifetime stats the server counts (QuestService.event). bestStreak and achievements are derived.
Q.Stats={'waves','kills','runs','bosses','earn','chests','upgrades','wins','quests','utilityKills',
 'deepRuns','minutes','levels','shards','meleeKills','rangedKills','buys','damage','eggs',
 'hardWins','nightmareWins','flawlessWins','wave25Runs','weeklies'}

-- 1234567 -> '1,234,567'
function Q.comma(n)
 local s=tostring(math.floor(n or 0));local out=s:reverse():gsub('(%d%d%d)','%1,'):reverse()
 return (out:gsub('^,',''))
end
-- 250000 -> '250K', 12345 -> '12.3K', 3e9 -> '3B'
function Q.short(n)
 n=math.floor(n or 0)
 for _,u in {{1e9,'B'},{1e6,'M'},{1e3,'K'}} do
  if n>=u[1] then
   local v=n/u[1]
   local s=v>=100 and tostring(math.floor(v)) or string.format('%.1f',math.floor(v*10)/10)
   return (s:gsub('%.0$',''))..u[2]
  end
 end
 return tostring(n)
end
-- Minutes as a goal: '30 minutes', '1 hour', '10 hours'.
function Q.duration(min)
 min=math.floor(min or 0)
 if min<60 then return min..(min==1 and ' minute' or ' minutes') end
 local h=min/60
 local s=h==math.floor(h) and tostring(math.floor(h)) or string.format('%.1f',h)
 return s..(h==1 and ' hour' or ' hours')
end
-- Minutes as progress: 434 -> '7:14' (hours:minutes).
function Q.clock(min) min=math.floor(min or 0);return string.format('%d:%02d',min//60,min%60) end
-- A road's goal number in words for its format.
function Q.amount(road,n)
 if road.format=='hours' then return Q.duration(n) elseif road.format=='short' then return Q.short(n) end
 return Q.comma(n)
end
-- 'have / need' on a road's progress bar.
function Q.progressText(road,have,need)
 if road.format=='hours' then return Q.clock(have)..' / '..Q.clock(need) end
 if road.format=='short' then return Q.short(have)..' / '..Q.short(need) end
 return Q.comma(have)..' / '..Q.comma(need)
end
return Q
