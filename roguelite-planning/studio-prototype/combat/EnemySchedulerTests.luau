-- Pure checks for EnemyScheduler (launch audit P5), runnable in Edit with no instances: load its
-- source with loadstring and pass the module in. Covers
-- - the think clock: the same rule as the old per-enemy loop, so every enemy still thinks every
--   0.1 s (0.3 s only when far with a clear line);
-- - the spread: a wave's groups (4 enemies every 0.2 s) no longer think all on one frame;
-- - the runner: everyone is stepped once per frame in order, an error or a yield in one enemy's
--   step never stops or repeats the others, and enemies added mid-frame wait a frame;
-- - compact: finished enemies drop out, the order of the rest is kept;
-- - wave population (2026-10-03): 20% bigger swarms, each extra player adds less, the 100 cap holds.
-- - Endless (2026-10-03): waves 1-20 untouched, every later wave harder, capped speed, tough slots,
--   and the seeded boss schedule (never back to back, at most 3 waves without, no repeat picks).
-- Returns {passed, checks, oldPeak, newPeak, ...}.
return function(S)
	local checks = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local result = {}

	-- Interval: far only past S.FAR.
	check(S.interval(0) == S.THINK and S.interval(S.FAR) == S.THINK, "near enemies think every 0.1 s")
	check(S.interval(S.FAR + 0.01) == S.FAR_THINK, "far enemies think every 0.3 s")
	check(S.THINK == 0.1 and S.FAR_THINK == 0.3 and S.FAR == 90, "documented numbers")
	-- The fastest enemy (werewolf, 21 studs/s) must not reach its 8-stud walk point between far thinks.
	check(21 * S.FAR_THINK < 8, "a far think never lets an enemy reach its walk point")

	-- due(): at most one think a frame, never two within one interval, and on average exactly
	-- one per interval at any frame rate (the old restart-from-0 rule averaged 0.10-0.12 s).
	local rng = Random.new(61)
	for _, interval in { S.THINK, S.FAR_THINK } do
		for _ = 1, 100 do
			local record = { elapsed = rng:NextNumber(-5 * S.FRAME, 0), interval = interval }
			local time, thinks, last = 0, 0, nil
			local low, high = rng:NextNumber(1 / 240, 1 / 60), rng:NextNumber(1 / 60, 1 / 15)
			for _ = 1, 400 do
				local dt = rng:NextNumber(low, high)
				time += dt
				if S.due(record, dt) then
					thinks += 1
					if last then check(time - last > interval - high - 1e-9, "never two thinks within an interval") end
					last = time
				end
				check(record.elapsed >= -5 * S.FRAME - 1e-9 and record.elapsed < interval, "clock stays in range")
			end
			check(math.abs(thinks - time / interval) <= 2 + time / interval * 0.02 or high > interval, "one think per interval on average")
		end
	end
	-- A long hitch thinks once and keeps the phase: 0.07 + 0.25 s -> one think, 0.02 left.
	local hitch = { elapsed = 0.07, interval = S.THINK }
	check(S.due(hitch, 0.25) and math.abs(hitch.elapsed - 0.02) < 1e-9, "a hitch is one think")
	check(not S.due(hitch, S.FRAME), "and not another the next frame")

	-- The spread. A wave: 15 groups of 4, 0.2 s apart (12 frames at 60 Hz), then `seconds` of play.
	-- Returns the most thinks on one frame after the wave is in, the same over the last 2 s, and
	-- the average a frame. `spread` false is the old per-enemy loop (restart from 0, no spread).
	local function simulate(spread, jitter, seconds)
		local records, peak, latePeak, total, frames = {}, 0, 0, 0, 0
		local last = 15 * 12 + math.floor(seconds * 60)
		for f = 1, last do
			local dt = S.FRAME * (1 + (jitter and rng:NextNumber(-jitter, jitter) or 0))
			if f % 12 == 1 and f <= 15 * 12 then
				for _ = 1, 4 do
					table.insert(records, { elapsed = spread and S.startElapsed(records) or 0, interval = S.THINK, time = 0 })
				end
			end
			local count = 0
			for _, record in records do
				record.time += dt
				local due
				if spread then
					due = S.due(record, dt)
				else
					record.elapsed += dt
					due = record.elapsed >= record.interval
					if due then record.elapsed = 0 end
				end
				if due then
					count += 1
					local slack = S.FRAME * (1 + (jitter or 0)) + 1e-9
					if record.last then
						local gap = record.time - record.last
						if spread then
							check(math.abs(gap - 0.1) <= slack, "think every 0.1 s, was " .. gap)
						else
							check(gap >= 0.1 - 1e-9 and gap <= 0.1 + slack, "old clock: 0.1 s plus up to a frame, was " .. gap)
						end
					elseif spread then
						-- First think: 0.1 s after spawn as before, at most 5 frames (and a frame time) later.
						check(record.time >= 0.1 - 1e-9 and record.time <= 0.1 + 5 * S.FRAME + slack, "first think " .. record.time)
					end
					record.last = record.time
				end
			end
			if f > 15 * 12 then
				peak = math.max(peak, count)
				total += count
				frames += 1
				if f > last - 120 then latePeak = math.max(latePeak, count) end
			end
		end
		return peak, latePeak, total / frames
	end
	local oldPeak, _, oldAverage = simulate(false, nil, 10)
	local newPeak, _, newAverage = simulate(true, nil, 10)
	check(newPeak <= 11 and newPeak < oldPeak, "60 enemies at 60 Hz: busiest frame " .. oldPeak .. " before, " .. newPeak .. " now")
	check(math.abs(newAverage - 10) < 0.2, "every enemy thinks every 0.1 s (6 frames): " .. newAverage .. " a frame")
	check(oldAverage < newAverage, "the old clock thought less often (every 6-7 frames): " .. oldAverage)
	-- Frame times +-15% for 60 s: the old clocks drift together; the new ones keep their spread.
	local _, oldLate = simulate(false, 0.15, 60)
	local jitterPeak, newLate = simulate(true, 0.15, 60)
	check(newLate <= 16 and newLate < oldLate, "after 60 s of uneven frames: busiest frame " .. oldLate .. " before, " .. newLate .. " now")
	result.oldPeak, result.newPeak, result.oldAverage, result.newAverage = oldPeak, newPeak, oldAverage, newAverage
	result.oldPeakAfter60sJitter, result.newPeakAfter60sJitter, result.newPeakJitter = oldLate, newLate, jitterPeak

	-- The runner.
	local order, errors = {}, {}
	local yielded
	local records = {}
	for i = 1, 8 do
		records[i] = { id = i }
	end
	local function step(record, a, b)
		check(a == "dt" and b == "frame", "step gets the frame's arguments")
		table.insert(order, record.id)
		if record.id == 3 then
			error("boom")
		elseif record.id == 5 then
			yielded = coroutine.running()
			coroutine.yield()
			table.insert(order, "5 resumed")
		elseif record.id == 6 then
			table.insert(records, { id = 9 }) -- spawned mid-frame
		end
	end
	local finished = S.run(records, 8, step, function(record, message)
		table.insert(errors, { record.id, message })
	end, "dt", "frame")
	check(table.concat(order, ",") == "1,2,3,4,5,6,7,8", "each stepped once, in order: " .. table.concat(order, ","))
	check(finished == 6, "6 steps ran to the end (not 3's error or 5's yield): " .. finished)
	check(#errors == 1 and errors[1][1] == 3 and string.find(errors[1][2], "boom"), "the error is reported with its enemy")
	-- The yielded step finishes later and steps no one else.
	check(yielded ~= nil and coroutine.status(yielded) == "suspended", "5 waits")
	coroutine.resume(yielded)
	check(table.concat(order, ",") == "1,2,3,4,5,6,7,8,5 resumed", "5 finished alone: " .. table.concat(order, ","))
	check(#records == 9 and records[9].id == 9, "the enemy spawned mid-frame waits for the next frame")
	-- Nothing to run.
	check(S.run({}, 0, step, error) == 0, "empty frame")

	-- compact.
	local list = { { id = 1 }, { id = 2, done = true }, { id = 3 }, { id = 4, done = true }, { id = 5, done = true }, { id = 6 } }
	S.compact(list)
	check(#list == 3 and list[1].id == 1 and list[2].id == 3 and list[3].id == 6, "compact keeps the order of the living")
	S.compact(list)
	check(#list == 3, "compact twice changes nothing")

	-- Wave population: base x1.2, then x1.6 / 2.1 / 2.5 for 2 / 3 / 4 players up, at most 100.
	check(S.playerScale(1) == 1 and S.playerScale(2) == 1.6 and S.playerScale(3) == 2.1 and S.playerScale(4) == 2.5, "player scale 1 / 1.6 / 2.1 / 2.5")
	check(S.playerScale(0) == 1 and S.playerScale(nil) == 1 and S.playerScale(6) == 2.5, "nobody up counts as one; past 4 stays x2.5")
	check(S.population(8, 1) == 10 and S.population(20, 1) == 24 and S.population(35, 1) == 42 and S.population(65, 1) == 78, "solo waves 1 / 5 / 10 / 20: 10, 24, 42, 78")
	check(S.population(8, 4) == 24 and S.population(20, 4) == 60 and S.population(35, 4) == 100 and S.population(65, 4) == 100, "4 players: 24, 60, 100, 100 (capped)")
	check(S.population(35, 2) == 67 and S.population(35, 3) == 88, "wave 10 with 2 and 3 players: 67, 88")
	check(S.population(0, 4) == 0, "an empty wave stays empty (practice, QA)")
	check(S.MAX_POPULATION == 100, "the cap is unchanged")
	local last = 0
	for n = 1, 4 do
		local p = S.population(30, n)
		check(p > last, "more players, more enemies: " .. p)
		last = p
	end
	for n = 2, 4 do
		check(S.playerScale(n) - S.playerScale(n - 1) < S.playerScale(n - 1) - (n > 2 and S.playerScale(n - 2) or 0), "each extra player adds less")
	end
	-- Reserved cap slots (an Endless boss): 4 players keep 90 while it is up; a smaller wave is untouched.
	check(S.population(80, 4, 10) == 90 and S.population(80, 4) == 100 and S.population(68, 1, 10) == 82, "a boss's 10 slots: 90 for 4 players, solo wave 21's 82 untouched")

	-- Endless (2026-10-03): waves 1-20 unchanged, then every wave harder than the last.
	local E = S.Endless
	local function near(a, b) return math.abs(a - b) < 1e-3 end
	for _, w in { 1, 10, 20, 0 / 0, "x", false } do
		local e = S.endless(w or nil)
		check(e.waves == 0 and e.health == 1 and e.damage == 1 and e.speed == 0 and e.tough == 0 and e.bossHealth == 1 and e.bossDamage == 1, "no Endless scaling at wave " .. tostring(w))
	end
	local e25, e30, e40 = S.endless(25), S.endless(30), S.endless(40)
	check(near(e25.health, 1.7623) and near(e30.health, 3.1058) and near(e40.health, 9.6463), "health x1.76 / x3.11 / x9.65 at 25 / 30 / 40")
	check(near(e25.damage, 1.3) and near(e30.damage, 1.6) and near(e40.damage, 2.2), "damage x1.3 / x1.6 / x2.2")
	check(near(e25.speed, 0.05) and near(e30.speed, 0.1) and near(e40.speed, 0.1), "speed +5% / +10% / +10% (capped)")
	check(near(e25.tough, 0.1) and near(e30.tough, 0.2) and near(e40.tough, 0.3) and near(S.endless(60).tough, 0.3), "tough share 10% / 20% / 30% (capped)")
	check(near(e30.bossHealth, 2.5) and near(e30.bossDamage, 1.4), "wave 30's boss: x2.5 health, x1.4 damage")
	for w = 21, 60 do
		local a, b = S.endless(w - 1), S.endless(w)
		check(b.health > a.health and b.damage > a.damage and b.bossHealth > a.bossHealth, "wave " .. w .. " is harder than " .. (w - 1))
		-- A zombie (3 + 2 a wave): at least 9% tougher than the wave before, all the way.
		check((3 + 2 * (w - 1)) * b.health >= (3 + 2 * (w - 2)) * a.health * 1.09, "zombie health climbs at wave " .. w)
	end
	check(near(S.endlessSpeed(16, e30), 17.6) and S.endlessSpeed(21, e40) == 21 and S.endlessSpeed(20, e40) == 21 and S.endlessSpeed(16, S.endless(20)) == 16, "speed: 16 -> 17.6, never past 21, unchanged up to 20")
	for _, speed in { 9.5, 12, 16, 17, 20, 21 } do
		check(S.endlessSpeed(speed, S.endless(80)) <= math.max(speed, E.maxSpeed) and E.maxSpeed < 22, "kiting stays possible at " .. speed)
	end
	-- Tough slots: evenly spread, and a slot picked at a lower share stays picked.
	for _, share in { 0.02, 0.1, 0.2, 0.3 } do
		local count = 0
		for i = 1, 100 do
			if S.toughSlot(i, share) then
				count += 1
				check(S.toughSlot(i, math.min(1, share + 0.1)), "slot " .. i .. " stays tough as the share grows")
			end
		end
		check(math.abs(count - share * 100) <= 2, "share " .. share .. " picks " .. count .. " of 100 slots")
	end
	check(not S.toughSlot(5, 0), "share 0 picks nothing")
	local byId = {
		crab = { behavior = "Melee", health = 4, healthPerWave = 2 },
		hermit = { behavior = "Heavy", health = 12, healthPerWave = 5 },
		ogre = { behavior = "Heavy", health = 20, healthPerWave = 7 },
		archer = { behavior = "Ranged", health = 6, healthPerWave = 2 },
	}
	check(S.toughest({ "crab", "hermit", "crab", "archer" }, byId) == "hermit", "a roster's Heavy is its toughest")
	check(S.toughest({ "hermit", "ogre" }, byId) == "ogre", "two Heavies: the one with more wave-20 health")
	check(S.toughest({ "crab", "archer", "nope" }, byId) == "archer", "no Heavy: the most health; unknown ids skipped")
	check(S.toughest({}, byId) == nil, "an empty roster has none")

	-- Endless bosses: never right after a boss wave (wave 20's counts), always after 3 without.
	local noDraw = { NextNumber = function() error("drew when the rules decide") end }
	local state = S.endlessState("KingCrab")
	check(state.last == 20 and #state.recent == 1 and state.recent[1] == "KingCrab", "history starts at wave 20's map boss")
	check(not S.endlessBossDue(state, 20, noDraw) and not S.endlessBossDue(state, 21, noDraw), "no Endless boss at 20 or 21 (20 was a boss wave)")
	check(S.endlessBossDue(state, 24, noDraw), "guaranteed at 24: 21-23 had none")
	local low, high = { NextNumber = function() return 0.34 end }, { NextNumber = function() return 0.35 end }
	check(S.endlessBossDue(state, 22, low) and not S.endlessBossDue(state, 22, high) and S.endlessBossDue(state, 23, low), "waves 22-23: a 35% roll")
	-- Over many seeded runs: a boss every 2, 3 or 4 waves (35% / 23% / 42%), about 3.07 on average.
	local rng2 = Random.new(7)
	local gaps, total, bosses = { 0, 0, 0, 0, 0 }, 0, 0
	local sim = S.endlessState(nil)
	for w = 21, 30020 do
		if S.endlessBossDue(sim, w, rng2) then
			local gap = w - sim.last
			check(gap >= 2 and gap <= 4, "boss gap " .. gap)
			gaps[gap] += 1
			total += gap
			bosses += 1
			S.endlessBossRecord(sim, w, "X")
		end
	end
	check(math.abs(total / bosses - 3.07) < 0.05 and math.abs(gaps[2] / bosses - 0.35) < 0.02, "mean gap " .. total / bosses)
	result.endlessMeanGap = total / bosses
	-- Picks: never the last two bosses while another exists; any when all are recent; nil with none.
	local rng3 = Random.new(11)
	local all = { "Hammer", "KingCrab", "Pharaoh", "FrostCyclops", "Dragon" }
	local hist = S.endlessState("Hammer")
	for w = 1, 200 do
		local id = S.endlessBossPick(all, hist.recent, rng3)
		check(id ~= nil and not table.find(hist.recent, id), "pick " .. w .. " avoids the last two")
		S.endlessBossRecord(hist, 20 + w * 3, id)
		check(#hist.recent <= E.bossRecent and hist.recent[#hist.recent] == id, "history keeps the last two, newest last")
	end
	check(S.endlessBossPick({ "Hammer" }, { "Hammer" }, rng3) == "Hammer", "the only boss in the place repeats")
	check(S.endlessBossPick({}, {}, rng3) == nil, "no boss templates: no pick (Endless goes on without)")
	local a1, a2 = Random.new(5), Random.new(5)
	for _ = 1, 20 do
		check(S.endlessBossPick(all, {}, a1) == S.endlessBossPick(all, {}, a2), "the same seed picks the same bosses")
	end

	result.passed = true
	result.checks = checks
	return result
end
