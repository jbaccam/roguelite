-- Body-contact checks for CharacterService (launch audit P10), runnable in Edit with no instances:
-- the real CharacterService source runs against stub players, enemies and a fake clock, next to
-- the old contact loop (copied below), and both must hurt the same player with the same enemy for
-- the same damage on every tick. Crowds move, die, lose their root, change attributes mid-run
-- (the cached record must follow) and some lines of sight are blocked.
-- Usage (execute_luau, Edit, dev server running): tests(<CharacterService source text>).
-- Returns {passed, checks, ticks, contacts, oldReads, newReads}. The pre-P10 source (git 2ad238a)
-- passes too, with newReads equal to oldReads, so the copy below is the old loop.
-- 2026-10-02: 699 checks, 97 contacts in 600 ticks (4 players, 70 enemies); 5,588 reads, was 432,953.
return function(source)
	local checks = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local rng = Random.new(41)
	local now = 0
	local reads = 0 -- Instance-style calls made by the loop under test
	local function signal()
		local s = { fns = {} }
		function s.Connect(_, fn)
			table.insert(s.fns, fn)
			return { Disconnect = function() end }
		end
		function s.fire(...)
			for _, fn in s.fns do
				fn(...)
			end
		end
		return s
	end

	-- The world.
	local enemies, tagged = {}, {}
	local blocked = {} -- [npc][player] = true: a wall between them
	local combatAttributes = { ZombiesEnabled = true }
	local function newEnemy(i)
		local npc = { Name = "Zombie_" .. i, attributes = {}, signals = {} }
		-- Standing still: CharacterService.seenEnemy (where a player saw it) is then where it is.
		local root = { Parent = npc, Position = Vector3.new(rng:NextNumber(-12, 12), rng:NextNumber(-1, 1), rng:NextNumber(-12, 12)), AssemblyLinearVelocity = Vector3.zero }
		local hum = { Health = 10, Parent = npc }
		npc.root, npc.hum = root, hum
		function npc.FindFirstChild(_, name)
			reads += 1
			return name == "HumanoidRootPart" and npc.root.Parent == npc and npc.root or nil
		end
		function npc.FindFirstChildOfClass(_, class)
			reads += 1
			return class == "Humanoid" and hum or nil
		end
		function npc.GetAttribute(_, name)
			reads += 1
			return npc.attributes[name]
		end
		function npc.GetAttributeChangedSignal(_, name)
			npc.signals[name] = npc.signals[name] or signal()
			return npc.signals[name]
		end
		function npc.set(name, value)
			npc.attributes[name] = value
			if npc.signals[name] then npc.signals[name].fire() end
		end
		-- Mostly wave mobs (bump), some old proximity mobs, a practice dummy, a boss.
		local kind = rng:NextInteger(1, 10)
		if kind <= 6 then
			npc.attributes = { ContactDamage = 0, ContactRange = 4.6, BumpDamage = rng:NextInteger(1, 4), BumpRange = rng:NextNumber(1.5, 3.5) }
		elseif kind <= 8 then
			npc.attributes = { ContactDamage = rng:NextInteger(1, 10), ContactRange = rng:NextNumber(2, 5) }
		elseif kind == 9 then
			npc.attributes = { PracticeTarget = true }
		else
			npc.attributes = { ContactDamage = 0, ContactRange = 0 } -- a boss: no bump numbers
		end
		return npc
	end
	for i = 1, 70 do
		enemies[i] = newEnemy(i)
		tagged[i] = enemies[i]
	end
	local players = {}
	for i = 1, 4 do
		local root = { Position = Vector3.new(rng:NextNumber(-6, 6), 0, rng:NextNumber(-6, 6)), CFrame = CFrame.identity }
		local h = { Health = 100, MaxHealth = 100, GetState = function() return Enum.HumanoidStateType.Running end }
		local character = {}
		-- A paused run holds players in place (CharacterService's shop hold).
		function character.PivotTo(_, cf)
			root.Position = cf.Position
		end
		function character.FindFirstChildOfClass(_, class)
			return class == "Humanoid" and h or nil
		end
		function character.FindFirstChild(_, name)
			return name == "HumanoidRootPart" and root or nil
		end
		players[i] = { UserId = i, Character = character, root = root, h = h, GetAttribute = function() return nil end }
	end

	-- Stub services for loading CharacterService.
	local heartbeat
	local enemyFolder = { Name = "RogueliteEnemies" }
	local remoteStub = { Name = "", OnServerEvent = signal(), IsA = function(_, c) return c == "RemoteEvent" end }
	local viewStub = { Name = "PlayerView", OnServerEvent = signal() } -- the clients' position reports
	local combat = {
		WaitForChild = function(_, name) return { Name = name } end,
		FindFirstChild = function(_, name) return name == "PlayerView" and viewStub or remoteStub end,
		GetAttribute = function(_, name) return combatAttributes[name] end,
		GetAttributeChangedSignal = function() return signal() end,
	}
	local Stats = { Movement = { Gravity = 196.2, JumpHeight = 7, AirSpeedMultiplier = 1 }, mult = function() return 1 end }
	local game = {}
	local services = {
		Players = { GetPlayers = function() return players end, PlayerRemoving = signal() },
		RunService = { Heartbeat = { Connect = function(_, fn) heartbeat = fn end } },
		CollectionService = { GetTagged = function() reads += 1 return table.clone(tagged) end },
	}
	function game.GetService(_, name) return services[name] end
	game.ReplicatedStorage = {
		WaitForChild = function() return combat end,
		FindFirstChild = function() return nil end, -- no RogueliteRunState: not in the shop
	}
	local workspace = {
		GetServerTimeNow = function() return now end, -- CharacterService.frozen (boss entrances) and .seen
		FindFirstChild = function(_, name) return name == "RogueliteEnemies" and enemyFolder or nil end,
		Raycast = function(_, origin, direction, params)
			local npc, character = params.FilterDescendantsInstances[1], params.FilterDescendantsInstances[2]
			for i, p in players do
				if p.Character == character and blocked[npc] and blocked[npc][i] then return { Position = origin + direction * 0.5 } end
			end
			return nil
		end,
	}
	local fn = assert(loadstring(source, "=CharacterService"))
	setfenv(fn, setmetatable({
		game = game,
		workspace = workspace,
		require = function(module) return module.Name == "CharacterStats" and Stats or {} end,
		RaycastParams = { new = function() return {} end },
		os = { clock = function() return now end },
	}, { __index = getfenv(0) }))
	local Service = fn()
	check(type(heartbeat) == "function", "the contact loop is a Heartbeat")
	local contacts = {}
	Service.contact = function(player, amount, _, npc)
		table.insert(contacts, { player = player, amount = amount, npc = npc })
		return amount
	end
	local oldTimers = {}
	for _, p in players do
		Service.states[p] = { lastBump = 0, lastContact = 0, stats = { Regeneration = 0, Recovery = 0, MoveSpeed = 16 } }
		oldTimers[p] = { lastBump = 0, lastContact = 0 }
	end

	-- The contact loop before P10, over the same world.
	local oldReads = 0
	local function attribute(npc, name)
		oldReads += 1
		return npc.attributes[name]
	end
	-- Each player's position as the last tick ended: bumps test the path from there (2026-10-03).
	local pathEnd = {}
	local function nearest(a, b, p)
		local ab = Vector3.new(b.X - a.X, 0, b.Z - a.Z)
		local len = ab:Dot(ab)
		if len < 1e-6 then return b end
		return a + (b - a) * math.clamp(Vector3.new(p.X - a.X, 0, p.Z - a.Z):Dot(ab) / len, 0, 1)
	end
	local function old()
		local out = {}
		if not combatAttributes.ZombiesEnabled or combatAttributes.RunPaused == true then return out end
		for player in Service.states do
			local s, root = oldTimers[player], player.root
			local from = pathEnd[player]
			if not from or (root.Position - from).Magnitude > 10 then from = root.Position end
			oldReads += 1 -- GetTagged
			for _, npc in tagged do
				oldReads += 2
				local nr = npc.root and npc.root.Parent == npc and npc.root or nil
				local nh = npc.hum
				local contactDamage = attribute(npc, "ContactDamage") or 10
				local contactRange = attribute(npc, "ContactRange") or 4.5
				local bump = contactDamage <= 0
				if bump then
					contactDamage = attribute(npc, "BumpDamage") or 0
					contactRange = attribute(npc, "BumpRange") or 0
				end
				local ready = if bump then now - s.lastBump >= 0.6 else now - s.lastContact >= 0.8
				local delta = nr and nearest(from, root.Position, nr.Position) - nr.Position
				if ready and contactDamage > 0 and not attribute(npc, "PracticeTarget") and nr and nh and nh.Health > 0 and math.abs(delta.Y) < 4.5 and Vector2.new(delta.X, delta.Z).Magnitude < contactRange then
					local index = table.find(players, player)
					if not (blocked[npc] and blocked[npc][index]) then
						if bump then s.lastBump = now else s.lastContact = now end
						table.insert(out, { player = player, amount = contactDamage, npc = npc })
						break
					end
				end
			end
		end
		return out
	end

	local ticks, total = 0, 0
	local serial = #enemies
	for tick = 1, 600 do
		-- The world changes between ticks: walking, a death, a respawn, a lost root, a wall, a
		-- changed attribute, and now and then waves off or a paused run.
		for _, npc in tagged do
			npc.root.Position += Vector3.new(rng:NextNumber(-1.5, 1.5), 0, rng:NextNumber(-1.5, 1.5))
		end
		for _, p in players do
			p.root.Position += Vector3.new(rng:NextNumber(-1, 1), 0, rng:NextNumber(-1, 1))
		end
		local roll = rng:NextInteger(1, 12)
		local victim = tagged[rng:NextInteger(1, #tagged)]
		if roll == 1 then
			victim.hum.Health = 0
		elseif roll == 2 then
			table.remove(tagged, table.find(tagged, victim))
			serial += 1
			table.insert(tagged, newEnemy(serial))
		elseif roll == 3 then
			victim.root.Parent = nil
		elseif roll == 4 then
			blocked[victim] = { [rng:NextInteger(1, 4)] = true }
		elseif roll == 5 then
			victim.set("BumpRange", rng:NextNumber(1, 6))
		elseif roll == 6 then
			victim.set("ContactDamage", rng:NextInteger(0, 3))
		elseif roll == 7 then
			victim.set("PracticeTarget", not victim.attributes.PracticeTarget or nil)
		elseif roll == 8 then
			combatAttributes.RunPaused = rng:NextNumber() < 0.5 or nil
		elseif roll == 9 then
			combatAttributes.ZombiesEnabled = rng:NextNumber() < 0.8
		end
		now += 0.1
		local expected = old()
		table.clear(contacts)
		heartbeat(0.1)
		for _, p in players do
			pathEnd[p] = p.root.Position
		end
		ticks += 1
		check(#contacts == #expected, "tick " .. tick .. ": " .. #contacts .. " contacts, expected " .. #expected)
		for i, c in expected do
			local got = contacts[i]
			check(got.player == c.player and got.npc == c.npc and got.amount == c.amount, "tick " .. tick .. ": same contact " .. i)
		end
		total += #expected
	end
	check(total > 50, "the crowd made real contacts (" .. total .. ")")

	-- Hits judged from the player's screen (2026-10-03): their own report while fresh and near
	-- their body here, and an enemy moved back along its velocity by the view delay.
	local p1 = players[1]
	local here = p1.root.Position
	viewStub.OnServerEvent.fire(p1, here + Vector3.new(3, 0, 0))
	check(Service.seen(p1, p1.root) == here + Vector3.new(3, 0, 0), "a fresh report near the body is where they are")
	now += 0.5
	check(Service.seen(p1, p1.root) == here, "a report 0.5 s old is dropped for the body here")
	viewStub.OnServerEvent.fire(p1, here + Vector3.new(40, 0, 0))
	check(Service.seen(p1, p1.root) == here, "a report 40 studs from the body is ignored")
	viewStub.OnServerEvent.fire(p1, "nowhere")
	check(Service.seen(p1, p1.root) == here, "a report that isn't a position changes nothing")
	local walker = { Position = Vector3.new(10, 0, 0), AssemblyLinearVelocity = Vector3.new(12, 3, 0) }
	local seen = Service.seenEnemy(p1, walker)
	check(math.abs(seen.X - (10 - 12 * 0.2)) < 1e-6 and seen.Y == 0, "a zombie walking at 12 studs/s shows 2.4 studs behind (no ping here)")
	-- A sprint (2.4 studs a check) straight through a zombie at 0.3 studs off its middle: both
	-- checks are 1.2 studs away, past a 1.4 bump only along the path between them.
	local through = Service.nearestOnPath(Vector3.new(0, 0, -1.2), Vector3.new(0, 0, 1.2), Vector3.new(0.3, 0, 0))
	check(through.Magnitude < 1e-6, "running through a zombie between two checks passes its middle")
	check(Service.nearestOnPath(Vector3.new(1, 0, 1), Vector3.new(1, 0, 1), Vector3.zero) == Vector3.new(1, 0, 1), "standing still is the one point")
	return { passed = true, checks = checks, ticks = ticks, contacts = total, oldReads = oldReads, newReads = reads }
end
