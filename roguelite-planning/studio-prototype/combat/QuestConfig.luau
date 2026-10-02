-- Daily quests, the daily streak and achievements (plans/2026-10-01-H-store-and-quests.md; 4 a day
-- from 16, and 10-level roads: plans/2026-10-02-K-quests-power-ui.md). Shared data: QuestService
-- (server) checks progress and grants, the lobby UI draws from it. Rewards: emeralds (counted as
-- earned), chests by ChestConfig id, a class, a weapon by WeaponCatalog name, or a full armor set
-- by ArmorCatalog id.
local Q={}
local function rgb(r,g,b) return Color3.fromRGB(r,g,b) end

-- Art: ui/assets/upgrades, ui/assets/hud (the user's plan K icons: hud/asset-ids.json) and the
-- egg merchant's egg. Keyed by stat, so a quest or road finds its icon by what it counts.
Q.Icons={
 waves='rbxassetid://80556274645944', -- Armor (shield)
 kills='rbxassetid://105663077535579', -- Damage (fist)
 runs='rbxassetid://119231770241307', -- play portal
 bosses='rbxassetid://113971691535704', -- teeth
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
 eggs='rbxassetid://117887028525234', -- pet egg
 title='rbxassetid://87815515863495', -- ribbon (titles, plan K part 4)
 speed='rbxassetid://117216104224040', -- wings (Move Speed)
 frost='rbxassetid://104227388119878', -- frost streaks (Attack Speed)
 heart='rbxassetid://87748663271804', -- Max HP
}

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

-- Roads: lifetime stats with ten levels each. Each level is also a future title ("Slayer Skilled").
Q.TierNames={'Rookie','Beginner','Intermediate','Skilled','Advanced','Expert','Elite','Master','Grandmaster','Legend'}
Q.Levels=#Q.TierNames
Q.TierRewards={
 {emeralds=25},
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
 {id='Achiever',name='Achiever',stat='achievements',goal='Reach %s achievement levels',targets={3,10,20,30,45,60,80,100,120,145}},
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

-- Lifetime stats the server counts (QuestService.event). bestStreak and achievements are derived.
Q.Stats={'waves','kills','runs','bosses','earn','chests','upgrades','wins','quests','utilityKills',
 'deepRuns','minutes','levels','shards','meleeKills','rangedKills','buys','damage','eggs'}

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
