-- Pure checks for EnemySpatialGrid (launch audit P9): on made-up crowds, separation must match the
-- old version (copied below: neighbours sorted back into folder order, or the whole folder for a
-- dense pile) to float precision, measuring the same neighbours. Studio Edit, no Play: load
-- EnemySpatialGrid's source with loadstring and pass the module in. Nothing in the place is used.
-- Returns {passed, checks, crowds, queries, worstDifference, oldMs, newMs}.
return function(Grid)
	local checks = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local rng = Random.new(29)
	local RADIUS = 4.5

	-- The old separation over the same entries (EnemySpatialGrid before P9).
	local function old(cellsOf, entries, folder, npc, position)
		local x, z = math.floor(position.X / RADIUS), math.floor(position.Z / RADIUS)
		local nearby = {}
		for dx = -1, 1 do
			local column = cellsOf[x + dx]
			if column then
				for dz = -1, 1 do
					for _, entry in column[z + dz] or {} do
						if entry.npc ~= npc and entry.npc.Parent == folder then
							table.insert(nearby, entry)
						end
					end
				end
			end
		end
		if #nearby > #entries / 2 then
			nearby = entries
		else
			table.sort(nearby, function(a, b) return a.order < b.order end)
		end
		local separation, measured = Vector3.zero, 0
		for _, entry in nearby do
			if entry.npc == npc or entry.npc.Parent ~= folder then continue end
			local delta = position - entry.position
			delta = Vector3.new(delta.X, 0, delta.Z)
			local spacing = delta.Magnitude
			if spacing > 0.01 and spacing < RADIUS then
				separation += delta.Unit * (1 - spacing / RADIUS)
				measured += 1
			end
		end
		return separation, measured
	end

	-- Stub enemies: what Grid reads is folder:GetChildren(), npc:FindFirstChild, root:IsA,
	-- root.Position and npc.Parent.
	local function crowd(count, spread, center)
		local folder = {}
		local children = {}
		function folder.GetChildren() return table.clone(children) end
		for i = 1, count do
			local root = { Position = center + Vector3.new(rng:NextNumber(-spread, spread), rng:NextNumber(-1, 1), rng:NextNumber(-spread, spread)) }
			function root.IsA(_, class) return class == "BasePart" end
			local npc = { Parent = folder, Name = "Zombie_" .. i }
			function npc.FindFirstChild(_, name) return name == "HumanoidRootPart" and root or nil end
			npc.root = root
			children[i] = npc
		end
		-- Two enemies on the same spot (spacing under .01 is skipped) and one with no root.
		if count >= 3 then
			children[2].root.Position = children[1].root.Position
			local rootless = { Parent = folder }
			function rootless.FindFirstChild() return nil end
			table.insert(children, rootless)
		end
		return folder, children
	end
	local function oldIndex(children)
		local cellsOf, entries = {}, {}
		for order, npc in children do
			local root = npc:FindFirstChild("HumanoidRootPart")
			if root then
				local p = root.Position
				local x, z = math.floor(p.X / RADIUS), math.floor(p.Z / RADIUS)
				cellsOf[x] = cellsOf[x] or {}
				cellsOf[x][z] = cellsOf[x][z] or {}
				local entry = { npc = npc, position = p, order = order }
				table.insert(cellsOf[x][z], entry)
				table.insert(entries, entry)
			end
		end
		return cellsOf, entries
	end

	local crowds, queries, worst = 0, 0, 0
	local oldTime, newTime = 0, 0
	for _, shape in { { 5, 30 }, { 20, 12 }, { 65, 40 }, { 65, 6 }, { 100, 60 }, { 100, 3 }, { 2, 1 } } do
		for _ = 1, 12 do
			local count, spread = shape[1], shape[2]
			local folder, children = crowd(count, spread, Vector3.new(rng:NextNumber(-300, 300), 0, rng:NextNumber(-300, 300)))
			local grid = Grid.new(folder, RADIUS)
			local cellsOf, entries = oldIndex(children)
			-- An enemy that died after the frame's rebuild drops out of both (Parent nil).
			grid:rebuild()
			if count > 4 then children[4].Parent = nil end
			crowds += 1
			for _, npc in children do
				local root = npc:FindFirstChild("HumanoidRootPart")
				if not root then continue end
				for _, position in { root.Position, root.Position + Vector3.new(rng:NextNumber(-3, 3), 0, rng:NextNumber(-3, 3)) } do
					queries += 1
					local t0 = os.clock()
					local a, measured = old(cellsOf, entries, folder, npc, position)
					local t1 = os.clock()
					local b = grid:separation(npc, position)
					local t2 = os.clock()
					oldTime += t1 - t0
					newTime += t2 - t1
					local difference = (a - b).Magnitude
					worst = math.max(worst, difference)
					check(difference < 1e-4, "separation differs by " .. difference .. " in a crowd of " .. count)
					check(b.Y == 0, "separation stays flat")
					-- The same neighbours push: count the new version's contributors the same way.
					local contributors = 0
					for _, other in children do
						local r = other:FindFirstChild("HumanoidRootPart")
						if other ~= npc and r and other.Parent == folder then
							local d = Vector3.new(position.X - r.Position.X, 0, position.Z - r.Position.Z).Magnitude
							if d > 0.01 and d < RADIUS then contributors += 1 end
						end
					end
					check(contributors == measured, "same neighbours push (" .. contributors .. " vs " .. measured .. ")")
				end
			end
			-- An enemy not in the folder (a boss measured from outside) still gets pushed.
			local outsider = { Parent = nil }
			local position = children[1]:FindFirstChild("HumanoidRootPart").Position + Vector3.new(1, 0, 1)
			check((old(cellsOf, entries, folder, outsider, position) - grid:separation(outsider, position)).Magnitude < 1e-4, "outsider separation")
			-- invalidate drops the cells; the next call rebuilds from the folder.
			grid:invalidate()
			check(grid.cells == nil, "invalidate clears the grid")
			grid:separation(children[1], children[1].root.Position)
			check(grid.cells ~= nil, "rebuilt on demand")
		end
	end
	return { passed = true, checks = checks, crowds = crowds, queries = queries, worstDifference = worst, oldMs = oldTime * 1000, newMs = newTime * 1000 }
end
