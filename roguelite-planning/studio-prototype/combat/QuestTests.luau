-- QuestService checks (plans/2026-10-01-H-store-and-quests.md): the daily roll, progress, claims,
-- the streak (growing, breaking, the 30-day wrap), trophy roads and unlocks. Run in Studio Edit on
-- fresh copies: `require(QuestTests)(require(serviceCopy), require(configCopy))`.
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

	-- Daily roll: three different quests, at least two `play`, the same all day, varied over days.
	local seen = {}
	for day = 20000, 20060 do
		local list = C.rollDaily(day, uid)
		check(#list == 3, "Three quests a day")
		local plays, ids = 0, {}
		for _, id in list do
			check(C.DailyById[id] ~= nil, "Rolled a real quest")
			check(not ids[id], "No repeats in a day")
			ids[id] = true
			if C.DailyById[id].play then
				plays += 1
			end
		end
		check(plays >= 2, "At least two play quests")
		check(table.concat(C.rollDaily(day, uid), ",") == table.concat(list, ","), "Same roll all day")
		seen[table.concat(list, ",")] = true
	end
	local sets = 0
	for _ in seen do
		sets += 1
	end
	check(sets >= 8, "Rolls vary between days (" .. sets .. " sets)")

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

	-- Streak: days 1-3 in a row, a missed day breaks it, the next finished day starts at 1.
	d = profile()
	finishDay(d, 30000)
	st = d.quests
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

	-- Trophy roads.
	d = profile()
	S.event(d, 1, uid, "kills", 600)
	ok, _, grant = S.claimRoad(d, 1, uid, "Slayer")
	check(ok and grant.emeralds == C.TierRewards[1].emeralds and grant.chests.Silver == 1, "Slayer tier 1 pays")
	check(S.claimRoad(d, 1, uid, "Slayer") == false, "Tier 2 needs 2,500")
	check(S.claimRoad(d, 1, uid, "Nope") == false, "Unknown road refused")
	d.quests.streak.best = 7
	check(S.claimRoad(d, 1, uid, "Dedicated") == true and S.claimRoad(d, 1, uid, "Dedicated") == true, "Best streak 7 clears two Dedicated tiers")

	-- Unlocks.
	d = profile()
	check(S.claimUnlock(d, 1, uid, "WaveRider") == false, "Wave Rider needs wave 10")
	d.bestWaves["PineValley/Hard"] = 12
	local okU, msg, g = S.claimUnlock(d, 1, uid, "WaveRider", function()
		return false
	end)
	check(okU and g.class == "Thrower", "Hard Pine Valley wave 12 unlocks Thrower: " .. tostring(msg))
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

	-- The view is plain JSON and the badge count matches what can be claimed.
	d = profile()
	finishDay(d, 50000)
	S.event(d, 50000, uid, "kills", 500)
	local view = S.view(d, 50000, uid, 3600)
	local json = game:GetService("HttpService"):JSONEncode(view)
	check(type(json) == "string" and #view.daily == 3 and view.streak.count == 1, "View encodes")
	-- 3 quests + day-1 streak reward + Slayer tier 1 (+ any road the finished quests cleared).
	check(S.claimable(d, 50000, uid) >= 5, "Badge counts every waiting reward")
	return checks
end
