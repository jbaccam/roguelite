-- One Heartbeat for every wave enemy (launch audit P5), used by RogueliteZombieChase. Pure: no
-- Instances, so EnemySchedulerTests runs it on stub enemies. Unsandboxed, like EnemySpatialGrid.
--
-- Each enemy used to have its own Heartbeat connection: 100 enemies were 6,000 callbacks a second.
-- Now one connection steps them all in order, every frame, so an attack in progress keeps its exact
-- per-frame timing. Each enemy still thinks (chases, looks for a new attack) on its own clock every
-- THINK seconds. Three changes:
-- - The clock keeps its phase: it subtracts the interval instead of restarting from 0 after each
--   think. Restarting threw away the part of a frame past 0.1 s, so thinks came every 6-7 frames
--   (0.10-0.12 s), enemies drifted, and two that ever thought on the same frame stayed together
--   for good: crowds slowly bunched onto a few frames. Now it is 0.1 s on average, 6 frames at 60 Hz.
-- - Spread: a new enemy's first think comes up to 5 frames late, on the least busy of the 6 frames.
--   Example: 60 enemies in 15 groups of 4, 0.2 s apart: 12 thought on the busiest frame before,
--   10 a frame now (EnemySchedulerTests).
-- - Far: an enemy whose target is more than FAR studs away, with a clear line to it, thinks every
--   FAR_THINK seconds. It walks straight at its target either way (its walk point is 8 studs ahead,
--   and even the werewolf covers 6.3 studs in 0.3 s), and the stuck-hop check already waits 0.3 s.
--   Blocked enemies (following a path) and everyone nearer keep THINK.
local S = {
	THINK = 0.1,
	FAR_THINK = 0.3,
	FAR = 90,
	PHASES = 6,
	FRAME = 1 / 60,
}

-- The think interval after a think that saw its target `distance` studs away with a clear line.
function S.interval(distance)
	return if distance > S.FAR then S.FAR_THINK else S.THINK
end

-- Counts the clock and says whether the enemy thinks this frame: once `elapsed` reaches the
-- interval, keeping what is past it (at most one think a frame, even after a long hitch).
function S.due(record, dt)
	record.elapsed += dt
	if record.elapsed < record.interval then
		return false
	end
	record.elapsed %= record.interval
	return true
end

-- Which of the PHASES frames in a THINK a clock thinks on. Every clock adds the same frame times,
-- so the gaps between clocks never change: a clock's phase is its `elapsed` modulo the interval.
-- Bins are centred on whole frames, so clocks a whole number of frames apart never straddle an edge.
function S.phase(elapsed)
	return math.floor((elapsed % S.THINK) / S.FRAME + 0.5) % S.PHASES
end

-- The starting clock for a new enemy: 0 to PHASES - 1 frames behind, on the phase the fewest
-- current (THINK) enemies use; ties to the earliest. Its first think is 0.1 s to 5 frames later.
function S.startElapsed(records)
	local counts = {}
	for p = 0, S.PHASES - 1 do
		counts[p] = 0
	end
	for _, record in records do
		if not record.done and record.interval == S.THINK then
			local p = S.phase(record.elapsed)
			counts[p] += 1
		end
	end
	local best, bestCount = 0, math.huge
	for k = 0, S.PHASES - 1 do
		local count = counts[S.phase(-k * S.FRAME)]
		if count < bestCount then
			best, bestCount = k, count
		end
	end
	return -best * S.FRAME
end

-- Steps records[1..n] in order with step(record, a, b). A step that errors is reported through
-- onError(record, message) and the rest still run. A step that yields (a WaitForChild somewhere)
-- finishes on its own later, and the rest of the frame carries on without waiting for it; it
-- never steps anyone else. Records added during the run (past n) wait for the next frame, as a
-- new Heartbeat connection did. Returns how many steps ran to the end this frame.
function S.run(records, n, step, onError, a, b)
	local cursor, finished, current = 1, 0, nil
	local function batch(self, from)
		for i = from, n do
			cursor = i
			step(records[i], a, b)
			if current ~= self then
				return -- this batch yielded in step i; the frame went on without it
			end
			finished += 1
		end
		cursor = n + 1
	end
	while cursor <= n do
		local co = coroutine.create(batch)
		current = co
		local ok, message = coroutine.resume(co, co, cursor)
		if not ok then
			onError(records[cursor], debug.traceback(co, tostring(message)))
			cursor += 1
		elseif coroutine.status(co) ~= "dead" then
			cursor += 1 -- yielded: skip past the waiting enemy
		end
	end
	current = nil
	return finished
end

-- Wave population: how many enemy slots a wave keeps filled, from its base size (ZombieCount,
-- ShopService.waveEnemyCount) and the players up in the run (2026-10-03, user: "scale spawn rate for
-- multiplayer depending on how many people", then "up the mob count a little bit, there should be
-- larger swarms"). SWARM makes every wave 20% bigger; PLAYER_SCALE adds less for each extra player,
-- because a team also kills faster: 1 x1.0, 2 x1.6, 3 x2.1, 4 x2.5 (more than 4 only in Studio).
-- Never above MAX_POPULATION, the cap the waves always had (unmeasured past it, launch audit P5).
-- Example: wave 10's base is 35 -> 42 solo, 67 for 2 players, 88 for 3, 100 (105 capped) for 4.
S.SWARM = 1.2
S.PLAYER_SCALE = { 1, 1.6, 2.1, 2.5 }
S.MAX_POPULATION = 100
function S.playerScale(players)
	local n = math.max(1, math.floor(tonumber(players) or 1))
	return S.PLAYER_SCALE[math.min(n, #S.PLAYER_SCALE)]
end
function S.population(base, players)
	base = math.max(0, tonumber(base) or 0)
	return math.min(S.MAX_POPULATION, math.floor(base * S.SWARM * S.playerScale(players) + 0.5))
end

-- Drops finished records (record.done), keeping the order of the rest.
function S.compact(records)
	local j = 0
	for i = 1, #records do
		local record = records[i]
		records[i] = nil
		if not record.done then
			j += 1
			records[j] = record
		end
	end
end

return S
