-- QuestService checks (plans/2026-10-01-H-store-and-quests.md, plans/2026-10-02-K-quests-power-ui.md):
-- the config's shape, the daily roll of 4, progress, claims, the streak (growing, breaking, the
-- 30-day wrap), 10-level roads, old-save conversion, Achiever, the plan K stats, unlocks, the
-- view, and plan M's weekly quests, wins and feats (plans/2026-10-02-M-feats-weekly-roads.md).
-- Run in Studio Edit on fresh copies (plans/2026-10-02-K-build-steps.md "Running Luau checks"):
-- `QuestTests(QuestService, QuestConfig)` returns the number of checks.
return function(S, C)
	S.use(C)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local uid = 4242
	local function profile()
		return { bestWaves = {}, mapWins = {} }
	end
	-- Finish every quest of `day` (and claim nothing).
	local function finishDay(d, day)
		local st = S.state(d, day, uid)
		for _, id in st.list do
			local q = C.DailyById[id]
			S.event(d, day, uid, q.stat, q.target)
		end
		return st
	end

	-- Config: 16 dailies, 19 roads x 10 levels that grow, plan H targets kept, art for every stat.
	check(#C.Daily == 16 and C.DailyCount == 4 and C.DailyPlay == 3, "16 daily quests, 4 a day, 3 of them run quests")
	local statSet = {}
	for _, s in C.Stats do
		statSet[s] = true
	end
	local ids = {}
	for _, q in C.Daily do
		check(not ids[q.id], "Daily ids are unique: " .. q.id)
		ids[q.id] = true
		check(statSet[q.stat] == true, "Daily quest counts a saved stat: " .. q.id)
		check(C.Icons[q.stat] ~= nil, "Daily quest has art: " .. q.id)
		check(q.target > 0 and q.emeralds > 0 and q.weight > 0, "Daily numbers are positive: " .. q.id)
	end
	check(#C.Roads == 19 and C.Levels == 10 and #C.TierNames == 10, "19 roads, 10 levels")
	check(#C.TierRewards == 10 and #C.TierColors == 10, "A reward and a colour per level")
	for _, r in C.Roads do
		check(#r.targets == 10, r.id .. " has 10 levels")
		for k = 2, 10 do
			check(r.targets[k] > r.targets[k - 1], r.id .. " gets harder every level")
		end
		check(statSet[r.stat] == true or r.stat == "bestStreak" or r.stat == "achievements", r.id .. " counts a known stat")
		check(C.Icons[r.stat] ~= nil, r.id .. " has art")
	end
	for id, old in C.LegacyRoadTargets do
		for _, target in old do
			check(table.find(C.RoadById[id].targets, target) ~= nil, id .. " keeps old target " .. target)
		end
	end
	check(
		C.RoadById.Achiever.targets[10] == (#C.Roads - 1) * C.Levels + #C.Unlocks + #C.Feats,
		"Achiever's last level is everything else"
	)
	check(C.short(250000) == "250K" and C.short(1e9) == "1B" and C.short(999) == "999" and C.short(12345) == "12.3K", "Short numbers")
	check(C.duration(30) == "30 minutes" and C.duration(60) == "1 hour" and C.duration(600) == "10 hours", "Durations")
	check(C.clock(434) == "7:14" and C.amount(C.RoadById.Playtime, 600) == "10 hours", "Clock and road amounts")
	check(C.progressText(C.RoadById.HeavyHitter, 125000, 250000) == "125K / 250K", "Short progress text")

	-- Daily roll: four different quests, the first three run quests, the same all day, varied.
	local seen = {}
	for day = 20000, 20060 do
		local list = C.rollDaily(day, uid)
		check(#list == 4, "Four quests a day")
		local got = {}
		for i, id in list do
			check(C.DailyById[id] ~= nil, "Rolled a real quest")
			check(not got[id], "No repeats in a day")
			got[id] = true
			if i <= 3 then
				check(C.DailyById[id].play == true, "The first three are run quests")
			end
		end
		check(table.concat(C.rollDaily(day, uid), ",") == table.concat(list, ","), "Same roll all day")
		seen[table.concat(list, ",")] = true
	end
	local sets = 0
	for _ in seen do
		sets += 1
	end
	check(sets >= 20, "Rolls vary between days (" .. sets .. " sets)")
	local lobby = 0
	for day = 21000, 21400 do
		if not C.DailyById[C.rollDaily(day, uid)[4]].play then
			lobby += 1
		end
	end
	check(lobby > 0, "Lobby quests come up in the fourth slot")

	-- Progress: capped at the target for the quest, uncapped for the lifetime stat.
	local d, day = profile(), 20100
	local st = S.state(d, day, uid)
	local first = C.DailyById[st.list[1]]
	check(S.claimQuest(d, day, uid, 1) == false, "Unfinished quest can't be claimed")
	S.event(d, day, uid, first.stat, first.target * 3)
	check(st.progress[first.id] == first.target, "Quest progress stops at the target")
	check(st.stats[first.stat] == first.target * 3, "Lifetime stat keeps counting")
	local ok, _, grant = S.claimQuest(d, day, uid, 1)
	check(ok and grant.emeralds == first.emeralds, "Claim pays the quest's emeralds")
	check(S.claimQuest(d, day, uid, 1) == false, "A quest pays once")
	check(st.stats.quests == 1, "Claims count toward Questor")
	check(S.claimQuest(d, day, uid, 9) == false and S.claimQuest(d, day, uid, "1") == false, "Bad index refused")
	check(S.event(d, day, uid, "bogus", 5) == false and S.event(d, day, uid, "kills", -5) == false, "Bad events ignored")

	-- New day: today's progress resets, lifetime stats stay.
	local kills = st.stats.kills
	st = S.state(d, day + 1, uid)
	check(next(st.progress) == nil and next(st.claimed) == nil and st.day == day + 1, "Progress resets at the new day")
	check(st.stats.kills == kills, "Lifetime stats survive the new day")

	-- Streak: a day counts when all 4 are done; a missed day breaks it.
	d = profile()
	st = S.state(d, 30000, uid)
	for i = 1, 3 do
		local q = C.DailyById[st.list[i]]
		S.event(d, 30000, uid, q.stat, q.target)
	end
	check(st.streak.count == 0, "Three of four don't count the day")
	finishDay(d, 30000)
	check(st.streak.count == 1 and table.find(st.streak.pending, 1), "Day 1 reward waits")
	finishDay(d, 30001)
	finishDay(d, 30002)
	check(S.streak(st, 30002) == 3 and table.find(st.streak.pending, 3), "Three days in a row, day 3 reward waits")
	finishDay(d, 30002)
	check(st.streak.count == 3, "Finishing again the same day doesn't count twice")
	check(S.streak(st, 30003) == 3, "Not broken until a whole day is missed")
	check(S.streak(st, 30004) == 0, "Broken after a missed day")
	finishDay(d, 30004)
	check(st.streak.count == 1 and st.streak.best == 3, "Starts again at 1; best stays 3")
	local ones = 0
	for _, m in st.streak.pending do
		if m == 1 then
			ones += 1
		end
	end
	check(ones == 2, "Unclaimed rewards wait through a break")
	check(S.claimStreak(d, 30004, uid, 1) == true and S.claimStreak(d, 30004, uid, 7) == false, "Claim only what's waiting")
	check(#st.streak.pending == 2, "A claim takes one reward off")

	-- 30-day wrap: day 31 lands on spot 1 again.
	d = profile()
	for i = 0, 30 do
		finishDay(d, 40000 + i)
	end
	st = d.quests
	check(st.streak.count == 31 and S.position(31) == 1, "Day 31 is spot 1 of the track")
	check(table.find(st.streak.pending, 30) and #st.streak.pending == #C.Streak + 1, "Every reward once, plus day 1 again")

	-- Roads: ten levels, claimed one at a time.
	d = profile()
	S.event(d, 1, uid, "kills", 600)
	ok, _, grant = S.claimRoad(d, 1, uid, "Slayer")
	check(ok and grant.emeralds == C.TierRewards[1].emeralds and next(grant.chests) == nil, "Slayer level 1 (100) pays emeralds only")
	ok, _, grant = S.claimRoad(d, 1, uid, "Slayer")
	check(ok and grant.emeralds == C.TierRewards[2].emeralds and grant.chests.Silver == 1, "Slayer level 2 (500) pays a Silver Chest")
	check(S.claimRoad(d, 1, uid, "Slayer") == false, "Level 3 needs 2,500")
	check(S.claimRoad(d, 1, uid, "Nope") == false, "Unknown road refused")
	d.quests.streak.best = 7
	local n = 0
	while S.claimRoad(d, 1, uid, "Dedicated") do
		n += 1
	end
	check(n == 4, "Best streak 7 clears four Dedicated levels (2, 3, 5, 7)")
	S.event(d, 1, uid, "minutes", 18000)
	n = 0
	while S.claimRoad(d, 1, uid, "Playtime") do
		n += 1
	end
	local _, msg = S.claimRoad(d, 1, uid, "Playtime")
	check(n == 10 and msg == "All tiers done", "Playtime stops at Legend")

	-- Achiever: levels claimed on other roads plus unlocks claimed, never its own.
	check(S.stat(d.quests, "achievements") == 16, "Achiever counts 2 + 4 + 10 levels")
	ok = S.claimRoad(d, 1, uid, "Achiever")
	check(ok and d.quests.roads.Achiever == 1, "Achiever level 1 at 3 levels")
	check(S.stat(d.quests, "achievements") == 16, "Achiever's own levels don't count toward it")
	d.bestWaves.PineValley = 10
	S.claimUnlock(d, 1, uid, "WaveRider", function()
		return false
	end)
	check(S.stat(d.quests, "achievements") == 17, "Unlocks count toward Achiever")

	-- Old saves: plan H tiers become the level with the same target, once.
	for id, old in C.LegacyRoadTargets do
		for tier = 1, #old do
			local dd = profile()
			dd.quests = { roads = { [id] = tier } }
			local s2 = S.state(dd, 1, uid)
			check(C.RoadById[id].targets[s2.roads[id]] == old[tier], id .. " old tier " .. tier .. " keeps its target")
			check(s2.roadsVersion == C.RoadsVersion, "Converted saves are marked")
		end
	end
	d = profile()
	d.quests = { roads = { Slayer = 3 } }
	S.state(d, 1, uid)
	check(d.quests.roads.Slayer == 4, "Slayer old tier 3 (10,000) is level 4")
	S.state(d, 2, uid)
	check(d.quests.roads.Slayer == 4, "Conversion runs once")
	S.event(d, 2, uid, "kills", 25000)
	ok, _, grant = S.claimRoad(d, 2, uid, "Slayer")
	check(ok and d.quests.roads.Slayer == 5 and grant.emeralds == C.TierRewards[5].emeralds, "Next claim is level 5 (25,000)")
	d = profile()
	S.state(d, 1, uid)
	check(d.quests.roadsVersion == C.RoadsVersion and next(d.quests.roads) == nil, "New profiles start converted")

	-- Plan K stats count like the rest.
	d = profile()
	for _, stat in { "deepRuns", "minutes", "levels", "shards", "meleeKills", "rangedKills", "buys", "damage", "eggs" } do
		check(S.event(d, 1, uid, stat, 3) and d.quests.stats[stat] == 3, "Counts " .. stat)
	end

	-- Unlocks.
	d = profile()
	check(S.claimUnlock(d, 1, uid, "WaveRider") == false, "Wave Rider needs wave 10")
	d.bestWaves["PineValley/Hard"] = 12
	local okU, msgU, g = S.claimUnlock(d, 1, uid, "WaveRider", function()
		return false
	end)
	check(okU and g.class == "Chef", "Hard Pine Valley wave 12 unlocks Chef (was Thrower): " .. tostring(msgU))
	check(C.UnlockById.WaveRider.desc == "Reach wave 10 on Pine Valley", "Chef's unlock is Thrower's old quest")
	for _, u in C.Unlocks do
		check(u.reward.class ~= "Thrower", "No unlock gives the old Thrower class: " .. u.id)
	end
	check(S.claimUnlock(d, 1, uid, "WaveRider") == false, "Unlock pays once")
	d.bestWaves.BeachCove = 30
	okU, _, g = S.claimUnlock(d, 1, uid, "EndlessLegend")
	check(okU and g.armorSet == "Samurai", "Wave 30 anywhere gives the Samurai set")
	d.mapWins.PineValley = true
	okU, _, g = S.claimUnlock(d, 1, uid, "ValleyVictor", function()
		return true
	end)
	check(okU and g.emeralds == C.ClassRefund and g.class == nil, "Owned class pays emeralds instead")
	check(S.claimUnlock(d, 1, uid, "FrostBreaker") == false, "Frost Breaker needs a Frozen Pass win")
	d.mapWins["FrozenPass/Hard"] = true
	okU, _, g = S.claimUnlock(d, 1, uid, "FrostBreaker")
	check(okU and g.weapon == "Mjolnir", "Frozen Pass win gives Mjolnir")

	-- Runs count once per stint.
	d = profile()
	S.runStarted(d, 1, uid, "run1/1")
	S.runStarted(d, 1, uid, "run1/1")
	S.runStarted(d, 1, uid, "run1/2")
	check(d.quests.stats.runs == 2, "One run per stint")

	-- The view is plain JSON, carries the derived stats, and the badge counts what can be claimed.
	d = profile()
	finishDay(d, 50000)
	S.event(d, 50000, uid, "kills", 600)
	local view = S.view(d, 50000, uid, 3600)
	local json = game:GetService("HttpService"):JSONEncode(view)
	check(type(json) == "string" and #view.daily == 4 and view.streak.count == 1, "View encodes")
	check(view.stats.achievements == 0 and view.stats.bestStreak == 1, "View has the derived stats")
	-- 4 quests + the day-1 streak reward + Slayer's next level (+ any road the quests cleared).
	check(S.claimable(d, 50000, uid) >= 6, "Badge counts every waiting reward")

	-- Plan M config: level 1 pays 50, 12 feats with rewards and art, weekly quests count saved stats.
	check(C.TierRewards[1].emeralds == 50, "Level 1 pays 50")
	check(#C.Feats == 12, "12 feats")
	for _, f in C.Feats do
		check(C.FeatRewards[f.stars] ~= nil and C.Icons[f.icon] ~= nil and C.FeatById[f.id] == f, "Feat has a reward and art: " .. f.id)
	end
	for id, q in C.WeeklyById do
		check(statSet[q.stat] == true and C.Icons[q.stat] ~= nil and q.target > 0 and q.emeralds > 0, "Weekly quest counts a saved stat: " .. id)
	end
	-- Weeks run Monday to Sunday: UTC day 4 (1970-01-05) was a Monday.
	check(C.week(4) == C.week(10) and C.week(3) ~= C.week(4) and C.week(11) ~= C.week(10), "Weeks start on Monday")
	check(C.weekResetIn(4, 100) == 6 * 86400 + 100 and C.weekResetIn(10, 100) == 100, "Week reset countdown")

	-- Weekly roll: 2 normal + 1 hard, the hard one only from what the player can do.
	local nightmareSeen, lockedSeen = false, false
	for week = 3000, 3200 do
		local list = C.rollWeekly(week, uid, { Hard = false, Nightmare = false })
		local a, b, c = C.WeeklyById[list[1]], C.WeeklyById[list[2]], C.WeeklyById[list[3]]
		check(#list == 3 and not a.hard and not b.hard and c.hard, "2 normal + 1 hard")
		check(list[1] ~= list[2], "No repeats in a week")
		check(c.needs == nil, "A new player never rolls a locked hard quest")
		check(table.concat(C.rollWeekly(week, uid, {}), ",") == table.concat(list, ","), "Same roll all week")
		local full = C.rollWeekly(week, uid, { Hard = true, Nightmare = true })
		nightmareSeen = nightmareSeen or full[3] == "NightmareWin"
		lockedSeen = lockedSeen or C.WeeklyById[full[3]].needs ~= nil
	end
	check(nightmareSeen and lockedSeen, "Unlocked players can roll Hard and Nightmare quests")
	check(not S.canPlay(profile()).Hard, "No wins: no Hard quests")
	local monday = 20003 -- (20003 + 3) % 7 == 0
	d = profile()
	st = S.state(d, monday, uid)
	local week1 = table.concat(st.weekList, ",")
	check(#st.weekList == 3 and st.week == C.week(monday), "Three weekly quests")
	d.mapWins.PineValley = true
	d.mapWins["PineValley/Hard"] = true
	check(S.canPlay(d).Hard and S.canPlay(d).Nightmare, "A Hard win opens Nightmare quests")
	st = S.state(d, monday + 3, uid)
	check(table.concat(st.weekList, ",") == week1, "Unlocking Hard midweek keeps the week's list")
	check(S.claimWeekly(d, monday + 3, uid, 1) == false, "Unfinished weekly can't be claimed")
	local w1 = C.WeeklyById[st.weekList[1]]
	S.event(d, monday + 3, uid, w1.stat, w1.target * 2)
	check(st.weekProgress[w1.id] == w1.target, "Weekly progress stops at the target")
	ok, _, grant = S.claimWeekly(d, monday + 3, uid, 1)
	check(ok and grant.emeralds == 300 and next(grant.chests) == nil, "A weekly pays 300")
	check(S.claimWeekly(d, monday + 3, uid, 1) == false, "A weekly pays once")
	check(st.stats.weeklies == 1, "Claims count toward Weekly Warrior")
	local w3 = C.WeeklyById[st.weekList[3]]
	S.event(d, monday + 4, uid, w3.stat, w3.target)
	ok, _, grant = S.claimWeekly(d, monday + 4, uid, 3)
	check(ok and grant.emeralds == 600 and grant.chests.Gold == 1, "The hard weekly pays 600 + a Gold Chest")
	check(S.claimWeekly(d, monday + 4, uid, 4) == false and S.claimWeekly(d, monday + 4, uid, "1") == false, "Bad weekly index refused")
	st = S.state(d, monday + 7, uid)
	check(st.week == C.week(monday + 7) and next(st.weekProgress) == nil and next(st.weekClaimed) == nil, "New week, fresh progress")
	check(st.stats.weeklies == 2, "Weekly Warrior keeps counting")
	-- A claimed daily quest feeds "Finish 12 Daily Quests".
	local dw
	for w = 3000, 3600 do
		local l = C.rollWeekly(w, uid, S.canPlay(profile()))
		if l[1] == "Dailies" or l[2] == "Dailies" then
			dw = w
			break
		end
	end
	check(dw ~= nil, "Some week rolls Finish 12 Daily Quests")
	d = profile()
	local dday = dw * 7 - 3 -- that week's Monday
	st = S.state(d, dday, uid)
	local q1 = C.DailyById[st.list[1]]
	S.event(d, dday, uid, q1.stat, q1.target)
	S.claimQuest(d, dday, uid, 1)
	check(st.weekProgress.Dailies == 1, "A claimed daily counts toward the weekly")

	-- Wins (QuestService.win) and feats.
	d = profile()
	check(S.claimFeat(d, 1, uid, "LoneWolf") == false, "Lone Wolf needs a solo win")
	check(S.claimFeat(d, 1, uid, "Nope") == false and S.claimFeat(d, 1, uid, 5) == false, "Unknown feat refused")
	check(S.win(d, 1, uid, "bad") == false, "Bad win refused")
	S.win(d, 1, uid, { diff = "Normal", solo = true, flawless = false, class = "Brawler" })
	ok, _, grant = S.claimFeat(d, 1, uid, "LoneWolf")
	check(ok and grant.emeralds == 300 and grant.chests.Silver == 1, "Lone Wolf pays one star")
	check(S.claimFeat(d, 1, uid, "LoneWolf") == false, "A feat pays once")
	check(S.claimFeat(d, 1, uid, "LoneLegend") == false, "A Normal solo win isn't Lone Legend")
	check(S.claimFeat(d, 1, uid, "Untouchable") == false, "Going down blocks Untouchable")
	check(d.quests.stats.hardWins == 0 and d.quests.stats.flawlessWins == 0, "A Normal win with a death counts neither")
	S.win(d, 1, uid, { diff = "Nightmare", solo = true, flawless = true, class = "Gunner" })
	check(S.claimFeat(d, 1, uid, "LoneLegend") == true, "A Nightmare solo win counts for Hard")
	ok, _, grant = S.claimFeat(d, 1, uid, "FlawlessNightmare")
	check(ok and grant.emeralds == 1500 and grant.chests.Magical == 1, "Flawless Nightmare pays three stars")
	ok, _, grant = S.claimFeat(d, 1, uid, "Untouchable")
	check(ok and grant.emeralds == 750 and grant.chests.Gold == 1, "Untouchable pays two stars")
	local ws = d.quests.stats
	check(ws.hardWins == 1 and ws.nightmareWins == 1 and ws.flawlessWins == 1, "A Nightmare no-down win counts all three")
	check(S.claimFeat(d, 1, uid, "JackOfAllTrades") == false, "Two classes aren't three")
	S.win(d, 1, uid, { diff = "Normal", class = "Brawler" })
	check(S.claimFeat(d, 1, uid, "JackOfAllTrades") == false, "The same class twice counts once")
	S.win(d, 1, uid, { diff = "Normal", class = "Mage" })
	check(S.claimFeat(d, 1, uid, "JackOfAllTrades") == true, "Three classes")
	check(S.claimFeat(d, 1, uid, "MasterOfAll") == false, "Three classes aren't six")
	-- Feats from saved map records count right away; solo and no-down don't.
	d = profile()
	d.mapWins["PineValley/Nightmare"] = true
	check(S.claimFeat(d, 1, uid, "StepItUp") and S.claimFeat(d, 1, uid, "NightmareWalker"), "A saved Nightmare win counts for Hard too")
	check(S.claimFeat(d, 1, uid, "LoneWolf") == false and S.claimFeat(d, 1, uid, "Untouchable") == false, "Saved wins aren't solo or no-down")
	d.mapWins["VolcanicCrater/Hard"] = true
	check(S.claimFeat(d, 1, uid, "DragonSlayer") == false, "A Hard Volcanic Crater win isn't Dragon Slayer")
	d.mapWins["VolcanicCrater/Nightmare"] = true
	check(S.claimFeat(d, 1, uid, "DragonSlayer") == true, "Dragon Slayer")
	d.bestWaves.BeachCove = 45
	d.bestWaves["FrozenPass/Hard"] = 40
	d.bestWaves["FrozenPass/Nightmare"] = 28
	check(S.claimFeat(d, 1, uid, "DeepDiver") and not S.claimFeat(d, 1, uid, "Abyss"), "Wave 45 is Deep Diver, not Abyss")
	check(S.claimFeat(d, 1, uid, "NightShift") == false, "Hard waves don't count for Night Shift")
	d.bestWaves["FrozenPass/Nightmare"] = 31
	check(S.claimFeat(d, 1, uid, "NightShift") == true, "Night Shift")
	check(S.stat(d.quests, "achievements") == 5, "Feats count toward Achiever")
	view = S.view(d, 1, uid, 3600)
	check(#view.weekly == 3 and view.feats.DragonSlayer.claimed and view.feats.Abyss.have == 45, "View has weekly quests and feats")
	check(view.weekResetIn == C.weekResetIn(1, 3600), "View has the week's reset time")
	local before = S.claimable(d, 1, uid)
	d.bestWaves.BeachCove = 50
	check(S.claimable(d, 1, uid) == before + 1, "Badge counts a ready feat")

	-- CLAIM ALL (2026-10-03): every ready reward of one tab in one request, each checked again.
	d = profile()
	local aday = 40000
	st = S.state(d, aday, uid)
	check(S.claimAll(d, aday, uid, "Daily") == false, "Claim all with nothing ready pays nothing")
	check(S.claimAll(d, aday, uid, "Bogus") == false, "Claim all needs a real tab")
	for i = 1, 2 do
		local q = C.DailyById[st.list[i]]
		S.event(d, aday, uid, q.stat, q.target)
	end
	-- What the single claims would pay now (two quests sharing a stat may finish a third).
	local function ready()
		local n, want = 0, 0
		for _, id in st.list do
			local q = C.DailyById[id]
			if not st.claimed[id] and (st.progress[id] or 0) >= q.target then
				n += 1
				want += q.emeralds
			end
		end
		for _, m in st.streak.pending do
			n += 1
			want += C.StreakByDay[m].emeralds or 0
		end
		return n, want
	end
	local n, want = ready()
	local okAll, msg, grants, total = S.claimAll(d, aday, uid, "Daily")
	check(okAll and total.count == n and #grants == n and total.emeralds == want and n >= 2, "Claim all pays every finished daily")
	check(string.find(msg, "Claimed " .. n .. " rewards", 1, true) == 1, "Claim all says how many: " .. tostring(msg))
	for _, id in st.list do
		local q = C.DailyById[id]
		check((st.claimed[id] == true) == ((st.progress[id] or 0) >= q.target), "Only finished dailies are claimed")
	end
	check(S.claimAll(d, aday, uid, "Daily") == false or #st.streak.pending == 0, "A claimed daily isn't paid twice")
	finishDay(d, aday)
	n, want = ready()
	okAll, _, _, total = S.claimAll(d, aday, uid, "Daily")
	check(okAll and total.count == n and total.emeralds == want, "Claim all takes the rest and the streak reward")
	check(#st.streak.pending == 0 and st.stats.quests == 4, "Every daily claimed once, streak reward taken")
	-- Achievements: feats and unlocks, then every ready road level; Achiever counts the others.
	d = profile()
	S.event(d, 1, uid, "kills", 2500) -- Slayer levels 1-3
	d.bestWaves.PineValley = 10 -- Wave Rider: the Chef class (was Thrower, 2026-10-09)
	d.mapWins.FrozenPass = true -- Frost Breaker: Mjolnir, skipped while it can't be paid
	local noClass = function()
		return false
	end
	local okA, _, gA, tA = S.claimAll(d, 1, uid, "Achievements", noClass, function(u)
		return u.reward.weapon == nil
	end)
	st = d.quests
	check(okA and st.roads.Slayer == 3 and st.roads.Achiever == 1, "Claim all takes every ready road level, Achiever too")
	check(st.unlocks.WaveRider == true and not st.unlocks.FrostBreaker, "Claim all skips an unlock that can't be paid")
	check(tA.count == 5 and tA.emeralds == 250 and tA.chests.Silver == 2, "Claim all adds the rewards up (3 + 1 levels, 1 unlock)")
	local class
	for _, g in gA do
		class = class or g.class
	end
	check(class == "Chef", "An unlocked class comes with the grants")
	check(S.claimAll(d, 1, uid, "Achievements", noClass, function(u)
		return u.reward.weapon == nil
	end) == false, "Nothing ready is left")
	okA, _, gA = S.claimAll(d, 1, uid, "Achievements", noClass)
	check(okA and #gA == 1 and gA[1].weapon == "Mjolnir" and st.unlocks.FrostBreaker, "The weapon unlock pays once it can")
	-- Weekly.
	d = profile()
	st = S.state(d, monday, uid)
	for i = 1, 2 do
		local q = C.WeeklyById[st.weekList[i]]
		S.event(d, monday, uid, q.stat, q.target)
	end
	n, want = 0, 0
	for _, id in st.weekList do
		local q = C.WeeklyById[id]
		if (st.weekProgress[id] or 0) >= q.target then
			n += 1
			want += q.emeralds
		end
	end
	okAll, _, _, total = S.claimAll(d, monday, uid, "Weekly")
	check(okAll and total.count == n and total.emeralds == want and st.stats.weeklies == n, "Claim all pays finished weeklies")
	return checks
end
