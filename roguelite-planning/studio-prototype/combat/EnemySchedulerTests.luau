-- Pure checks for EnemyScheduler (launch audit P5), runnable in Edit with no instances: load its
-- source with loadstring and pass the module in. Covers
-- - the think clock: the same rule as the old per-enemy loop, so every enemy still thinks every
--   0.1 s (0.3 s only when far with a clear line);
-- - the spread: a wave's groups (4 enemies every 0.2 s) no longer think all on one frame;
-- - the runner: everyone is stepped once per frame in order, an error or a yield in one enemy's
--   step never stops or repeats the others, and enemies added mid-frame wait a frame;
-- - compact: finished enemies drop out, the order of the rest is kept.
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

	result.passed = true
	result.checks = checks
	return result
end
