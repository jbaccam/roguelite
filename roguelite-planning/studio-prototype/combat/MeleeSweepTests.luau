-- Pure checks for TargetGrid.open and TargetGrid.sweep (launch audit P6): on made-up crowds, a melee
-- tick that judges each enemy once and stops when nobody else can be hit must hit exactly the
-- enemies, in the same order, that the old loop hit (it judged every returned part of every
-- enemy until one hit). Crowds include bosses (always open), dead and already-hit enemies, parts
-- with no enemy, walls, and a first hit that kills others mid-tick (the Wrecking Ball's shockwave).
-- Studio Edit, no Play: load TargetGrid's source with loadstring and pass it in.
-- Returns {passed, checks, ticks, hits, oldJudged, newJudged, oldQueries, newQueries}.
return function(G)
	local checks = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local rng = Random.new(53)
	local totals = { hits = 0, oldJudged = 0, newJudged = 0, oldQueries = 0, newQueries = 0, ticks = 0 }
	for _ = 1, 3000 do
		-- A crowd around the swing's origin.
		local origin = Vector3.new(rng:NextNumber(-50, 50), 0, rng:NextNumber(-50, 50))
		local range = rng:NextNumber(3, 9)
		local count = rng:NextInteger(0, 30)
		local enemies, list, parts = {}, {}, {}
		for i = 1, count do
			local e = {
				npc = { id = i },
				position = origin + Vector3.new(rng:NextNumber(-14, 14), rng:NextNumber(-1, 1), rng:NextNumber(-14, 14)),
				boss = rng:NextNumber() < 0.05,
			}
			e.alive = rng:NextNumber() < 0.95
			e.clear = rng:NextNumber() < 0.85
			-- A boss is measured to its nearest side: sometimes in reach though its root isn't.
			e.bossReach = e.boss and rng:NextNumber() < 0.6
			enemies[i] = e
			if e.alive then table.insert(list, e) end -- the snapshot holds the living
			for _ = 1, rng:NextInteger(3, 16) do table.insert(parts, { owner = e.npc }) end
		end
		for _ = 1, rng:NextInteger(0, 4) do table.insert(parts, { owner = nil }) end -- scenery-ish parts
		local byNpc = {}
		for _, e in enemies do byNpc[e.npc] = e end
		local alreadyHit = {}
		for _, e in enemies do if rng:NextNumber() < 0.15 then alreadyHit[e.npc] = true end end
		-- Each box returns a fixed random handful of parts (the same for old and new).
		local steps = rng:NextInteger(1, 8)
		local boxesPerSample = rng:NextInteger(1, 3)
		local returned = {}
		for i = 0, steps do
			returned[i] = {}
			for b = 1, boxesPerSample do
				local got = {}
				if #parts > 0 then
					for _ = 1, rng:NextInteger(0, math.min(40, #parts)) do table.insert(got, parts[rng:NextInteger(1, #parts)]) end
				end
				returned[i][b] = got
			end
		end
		local shockwave = rng:NextNumber() < 0.3 and {} or nil
		if shockwave then for _, e in enemies do if rng:NextNumber() < 0.3 then shockwave[e.npc] = true end end end

		-- One run of the tick: `newWay` picks the old per-part loop or open+sweep.
		local function run(newWay)
			local hit = table.clone(alreadyHit)
			local dead = {}
			local order, judged, queries = {}, 0, 0
			-- Both loops look at slot.hit first; the rest is the costly part (tag, attributes, reach, a raycast).
			local function canHit(npc)
				if hit[npc] then return false end
				judged += 1
				local e = byNpc[npc]
				if not e.alive or dead[npc] then return false end
				local inReach = if e.boss then e.bossReach else (e.position - origin).Magnitude <= range
				return inReach and e.clear
			end
			local function strike(npc)
				local first = next(hit) == nil
				hit[npc] = true
				table.insert(order, npc.id)
				if first and shockwave then for victim in shockwave do if victim ~= npc then dead[victim] = true end end end
			end
			if newWay then
				local open, remaining = G.open({ list = list }, origin, range, hit)
				local _, q = G.sweep(steps, function(i) return returned[i] end, function(box)
					return box
				end, function(part) return part.owner end, function(npc)
					if canHit(npc) then strike(npc) end
				end, open, remaining)
				queries = q
			else
				for i = 0, steps do
					for _, box in returned[i] do
						queries += 1
						for _, part in box do
							local npc = part.owner
							if npc and not hit[npc] and canHit(npc) then strike(npc) end
						end
					end
				end
			end
			return order, judged, queries
		end
		local oldOrder, oldJudged, oldQueries = run(false)
		local newOrder, newJudged, newQueries = run(true)
		check(#oldOrder == #newOrder, "same number of hits (" .. #oldOrder .. " vs " .. #newOrder .. ")")
		for i, id in oldOrder do check(newOrder[i] == id, "same hit " .. i) end
		check(newJudged <= oldJudged, "never judges more than the old loop")
		check(newQueries <= oldQueries, "never queries more than the old loop")
		-- Every enemy the old loop hit was open: the early stop can't skip a hit.
		local open = G.open({ list = list }, origin, range, alreadyHit)
		for _, id in oldOrder do check(open[enemies[id].npc], "a hit enemy was open") end
		totals.ticks += 1
		totals.hits += #oldOrder
		totals.oldJudged += oldJudged
		totals.newJudged += newJudged
		totals.oldQueries += oldQueries
		totals.newQueries += newQueries
	end
	-- open: bosses always, others by root distance, never the already hit.
	local a = { npc = {}, position = Vector3.new(3, 0, 0) }
	local b = { npc = {}, position = Vector3.new(30, 0, 0), boss = true }
	local c = { npc = {}, position = Vector3.new(30, 0, 0) }
	local d = { npc = {}, position = Vector3.new(1, 0, 0) }
	local open, n = G.open({ list = { a, b, c, d } }, Vector3.zero, 4, { [d.npc] = true })
	check(n == 2 and open[a.npc] and open[b.npc] and not open[c.npc] and not open[d.npc], "open set")
	-- Nobody open: no sample is taken. open nil: every sample is taken.
	local samples = G.sweep(5, function() error("sampled with nobody open") end, nil, nil, nil, {}, 0)
	check(samples == 0, "no samples when nobody can be hit")
	samples = G.sweep(5, function() return {} end, nil, nil, nil, nil, nil)
	check(samples == 6, "all samples without an open set")
	totals.passed = true
	totals.checks = checks
	return totals
end
