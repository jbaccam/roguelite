-- Daily quests, the daily streak and achievements (plans/2026-10-01-H-store-and-quests.md).
-- Shared data: QuestService (server) checks progress and grants, the lobby UI draws from it.
-- Rewards: emeralds (counted as earned), chests by ChestConfig id, a class, a weapon by
-- WeaponCatalog name, or a full armor set by ArmorCatalog id.
local Q={}

-- Existing art only (ui/assets/upgrades and ui/assets/hud).
Q.Icons={
 waves='rbxassetid://80556274645944', -- Armor (shield)
 kills='rbxassetid://105663077535579', -- Damage (fist)
 runs='rbxassetid://119231770241307', -- play portal
 bosses='rbxassetid://113971691535704', -- teeth
 chests='rbxassetid://128369126123154', -- chest
 earn='rbxassetid://107205947937384', -- emerald
 upgrades='rbxassetid://128990045041232', -- anvil
 wins='rbxassetid://129045264697854', -- target
 streak='rbxassetid://104925573900277', -- flame (Elemental Damage)
 quests='rbxassetid://85014504299735', -- scroll
 utilityKills='rbxassetid://133538769433103', -- gear (Utility Power)
 speed='rbxassetid://117216104224040', -- wings (Move Speed)
 frost='rbxassetid://104227388119878', -- frost streaks (Attack Speed)
 heart='rbxassetid://87748663271804', -- Max HP
}

-- Daily pool. Every day rolls two `play` quests and one more from what's left, by weight.
-- color: the card's header band.
Q.Daily={
 {id='Waves',stat='waves',target=10,emeralds=60,title='Survive 10 Waves',play=true,weight=3,color=Color3.fromRGB(64,150,240)},
 {id='Kills',stat='kills',target=300,emeralds=60,title='Defeat 300 Enemies',play=true,weight=3,color=Color3.fromRGB(232,74,64)},
 {id='Runs',stat='runs',target=3,emeralds=50,title='Play 3 Runs',play=true,weight=3,color=Color3.fromRGB(156,96,236)},
 {id='Earn',stat='earn',target=150,emeralds=50,title='Earn 150 Emeralds',play=true,weight=2,color=Color3.fromRGB(40,180,96)},
 {id='Boss',stat='bosses',target=1,emeralds=80,chests={Silver=1},title='Defeat a Map Boss',play=true,weight=1,color=Color3.fromRGB(236,140,36)},
 {id='Chests',stat='chests',target=3,emeralds=40,title='Open 3 Chests',weight=2,color=Color3.fromRGB(214,164,40)},
 {id='Upgrade',stat='upgrades',target=1,emeralds=40,title='Upgrade Any Item',weight=2,color=Color3.fromRGB(110,128,140)},
}
Q.DailyById={};for _,q in Q.Daily do Q.DailyById[q.id]=q end
Q.DailyCount=3

-- The day's quests for one player: the same three all day (seeded by day and user id).
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
 pick(function(q) return q.play end);pick(function(q) return q.play end)
 pick(function() return true end)
 return out
end

-- Streak: a day counts when all three daily quests are finished. Missing a day starts again at
-- 0. Each reward waits for CLAIM even if the streak breaks later. After day 30 the track repeats.
Q.StreakCycle=30
Q.Streak={
 {day=1,emeralds=50},{day=3,chests={Silver=1}},{day=7,chests={Gold=1}},{day=10,emeralds=250},
 {day=15,chests={Gold=2}},{day=20,chests={Magical=1}},{day=30,chests={Legendary=1}},
}
Q.StreakByDay={};for _,s in Q.Streak do Q.StreakByDay[s.day]=s end

-- Trophy roads: lifetime stats with five tiers each.
Q.TierNames={'Beginner','Intermediate','Advanced','Expert','Master'}
Q.TierRewards={
 {emeralds=50,chests={Silver=1}},{emeralds=120,chests={Silver=1}},{emeralds=250,chests={Gold=1}},
 {emeralds=500,chests={Magical=1}},{emeralds=1000,chests={Legendary=1}},
}
Q.Roads={
 {id='Survivor',name='Survivor',stat='waves',goal='Survive %s waves',targets={25,100,300,1000,3000}},
 {id='Slayer',name='Slayer',stat='kills',goal='Defeat %s enemies',targets={500,2500,10000,50000,200000}},
 {id='BossHunter',name='Boss Hunter',stat='bosses',goal='Defeat %s map bosses',targets={1,5,15,50,150}},
 {id='Champion',name='Champion',stat='wins',goal='Win %s maps',targets={1,3,10,25,60}},
 {id='Collector',name='Collector',stat='chests',goal='Open %s chests',targets={5,25,100,300,1000}},
 {id='Dedicated',name='Dedicated',stat='bestStreak',goal='Reach a %s-day streak',targets={3,7,14,30,60}},
 {id='Upgrader',name='Upgrader',stat='upgrades',goal='Upgrade items %s times',targets={1,5,20,50,120}},
 {id='Questor',name='Questor',stat='quests',goal='Finish %s daily quests',targets={5,20,60,150,365}},
}
Q.RoadById={};for _,r in Q.Roads do Q.RoadById[r.id]=r end

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

-- Lifetime stats the server counts (QuestService.event).
Q.Stats={'waves','kills','runs','bosses','earn','chests','upgrades','wins','quests','utilityKills'}

-- 1234567 -> '1,234,567'
function Q.comma(n)
 local s=tostring(math.floor(n or 0));local out=s:reverse():gsub('(%d%d%d)','%1,'):reverse()
 return (out:gsub('^,',''))
end
return Q
