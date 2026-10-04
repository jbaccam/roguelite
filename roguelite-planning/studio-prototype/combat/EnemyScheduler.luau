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
-- reserved (2026-10-03): cap slots something else takes, an Endless boss's bossSlots (below):
-- 4 players at wave 25 keep 90 enemies while it is up, 100 again once it falls.
S.SWARM = 1.2
S.PLAYER_SCALE = { 1, 1.6, 2.1, 2.5 }
S.MAX_POPULATION = 100
function S.playerScale(players)
	local n = math.max(1, math.floor(tonumber(players) or 1))
	return S.PLAYER_SCALE[math.min(n, #S.PLAYER_SCALE)]
end
function S.population(base, players, reserved)
	base = math.max(0, tonumber(base) or 0)
	local cap = S.MAX_POPULATION - math.max(0, tonumber(reserved) or 0)
	return math.max(0, math.min(cap, math.floor(base * S.SWARM * S.playerScale(players) + 0.5)))
end

-- Endless (2026-10-03, user: "start spawning bosses randomly in endless mode", "make sure the rounds
-- get harder in endless mode"). The 100 cap means count alone can't carry it (solo reaches 100 at
-- wave 26), so mobs get stronger: n = waves past FROM (RunSetupRules.WinWave), on top of each type's
-- own wave growth (EnemyCatalog.scaled). Waves 1-20 and the tutorial have n = 0: every multiplier 1.
--   health  x(1 + health)^n, compounding so each wave is ~15% tougher: 25 x1.76, 30 x3.11, 40 x9.65
--   damage  x(1 + damage x n), linear so hits grow slower than health: 25 x1.3, 30 x1.6, 40 x2.2
--   speed   +speed x n up to speedCap (+10% from wave 30), never past maxSpeed: a zombie 16 -> 17.6,
--           a werewolf stays 21, under every class's 22-24 base, so kiting still works
--   tough   this share of wave slots bring the map's toughest type (toughest): 25 10%, 30 20%, 35+ 30%
--   bosses  each wave a bossChance (35%) of a random boss, never the wave after a boss wave (wave 20's
--           counts), always after bossDrought (3) waves without one: one every 2-4 waves, ~3 on
--           average. It lands bossDelay s into the wave. Health: the map's own wave-20 boss
--           x(1 + bossHealth x n), so wave 30 is x2.5; damage x(1 + bossDamage x n). While it is up
--           it takes bossSlots of the 100 cap (a boss costs far more than one mob).
-- Example, a solo Pine Valley zombie (HP / damage a hit): wave 20 41 / 33.5, 25 90 / 53,
-- 30 190 / 78, 40 782 / 140. Its Hammer boss: 18,000 HP at 20, 31,500 at 25, 45,000 at 30.
S.Endless = {
	FROM = 20,
	health = 0.12,
	damage = 0.06,
	speed = 0.01,
	speedCap = 0.10,
	maxSpeed = 21,
	tough = 0.02,
	toughCap = 0.30,
	bossChance = 0.35,
	bossDrought = 3,
	bossRecent = 2, -- a pick avoids the last two bosses (wave 20's included) when another exists
	bossDelay = 5,
	bossHealth = 0.15,
	bossDamage = 0.04,
	bossSlots = 10,
}
-- The multipliers for `wave` (all 1 / 0 up to FROM).
function S.endless(wave)
	local E = S.Endless
	local w = tonumber(wave) or 0
	local n = if w == w then math.max(0, math.floor(w) - E.FROM) else 0
	return {
		waves = n,
		health = (1 + E.health) ^ n,
		damage = 1 + E.damage * n,
		speed = math.min(E.speedCap, E.speed * n),
		tough = math.min(E.toughCap, E.tough * n),
		bossHealth = 1 + E.bossHealth * n,
		bossDamage = 1 + E.bossDamage * n,
	}
end
function S.endlessSpeed(speed, scale)
	if speed >= S.Endless.maxSpeed then
		return speed
	end
	return math.min(speed * (1 + scale.speed), S.Endless.maxSpeed)
end
-- Whether wave slot `index` brings the toughest type: index x the golden ratio, wrapped to 0-1,
-- under share. Picks spread evenly (share 0.2: 20 of slots 1-100), and a slot picked at 10% stays
-- picked at 20%, so each wave adds tough slots without reshuffling the rest.
function S.toughSlot(index, share)
	return share > 0 and (index * 0.6180339887) % 1 < share
end
-- The roster's toughest type: a Heavy (tank zombie, hermit crab, mummy, frozen knight, ogre) when it
-- has one, else the most wave-20 health. byId: EnemyCatalog.ById.
function S.toughest(ids, byId)
	local best, bestHeavy, bestHealth = nil, false, -math.huge
	for _, id in ids do
		local d = byId[id]
		if d then
			local heavy = d.behavior == "Heavy"
			local health = (d.health or 0) + (d.healthPerWave or 0) * 19
			if (heavy and not bestHeavy) or (heavy == bestHeavy and health > bestHealth) then
				best, bestHeavy, bestHealth = id, heavy, health
			end
		end
	end
	return best
end
-- A run's Endless boss history: the last boss wave (wave 20's map boss to begin with) and the last
-- bossRecent bosses, newest last.
function S.endlessState(mapBoss)
	return { last = S.Endless.FROM, recent = if mapBoss then { mapBoss } else {} }
end
-- Does `wave` bring a boss? rng (a per-run Random) is drawn only when the rules leave it open.
function S.endlessBossDue(state, wave, rng)
	local E = S.Endless
	if wave <= E.FROM then
		return false
	end
	local since = wave - state.last
	if since <= 1 then
		return false -- never two boss waves in a row
	elseif since > E.bossDrought then
		return true -- the last bossDrought waves had none
	end
	return rng:NextNumber() < E.bossChance
end
-- One of `available` (boss ids whose templates are in the place), not in `recent` when it can.
function S.endlessBossPick(available, recent, rng)
	if #available == 0 then
		return nil
	end
	local fresh = {}
	for _, id in available do
		if not table.find(recent, id) then
			table.insert(fresh, id)
		end
	end
	local pool = if #fresh > 0 then fresh else available
	return pool[rng:NextInteger(1, #pool)]
end
function S.endlessBossRecord(state, wave, id)
	state.last = wave
	table.insert(state.recent, id)
	while #state.recent > S.Endless.bossRecent do
		table.remove(state.recent, 1)
	end
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
