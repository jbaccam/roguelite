-- Fresh-source Edit regression and optional real-physics Server Play fixture.
-- Neither uses CombatEffectsService, reduces health, or grants persistent rewards.
local Tests = {}

function Tests.run(read)
	local checks = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local function setup()
		local c = { models = {}, damage = {}, events = {}, blocked = {}, queue = {}, clock = 0 }
		local beat = { callbacks = {} }
		function beat:Connect(fn)
			table.insert(self.callbacks, fn)
			return { Disconnect = function() end }
		end
		local tags = {}
		function tags:GetTagged()
			return c.models
		end
		function tags:HasTag(npc)
			return npc.tagged
		end
		local world = {}
		function world:Raycast(origin, delta)
			for _, point in c.blocked do
				if (origin + delta - point).Magnitude < 0.001 then
					return {}
				end
			end
			return nil
		end
		function world:Spherecast(_, _, _, params)
			while #c.queue > 0 do
				local hit = table.remove(c.queue, 1)
				if not params.seen[hit.Instance.npc] then
					return hit
				end
			end
			return nil
		end
		local modules = {}
		local refs = setmetatable({}, {
			__index = function(t, k)
				local value = { Name = k }
				rawset(t, k, value)
				return value
			end,
		})
		local services = {
			RunService = { Heartbeat = beat },
			CollectionService = tags,
			ReplicatedStorage = { RogueliteCombat = refs },
		}
		local fakeGame = { ReplicatedStorage = services.ReplicatedStorage }
		function fakeGame:GetService(name)
			return assert(services[name], name)
		end
		local env = setmetatable({
			game = fakeGame,
			workspace = world,
			script = { Parent = refs },
			os = {
				clock = function()
					return c.clock
				end,
			},
			require = function(ref)
				return assert(modules[ref.Name], ref.Name)
			end,
		}, { __index = getfenv() })
		local function load(name)
			local fn = assert(loadstring(read(name), name))
			setfenv(fn, env)
			local value = fn()
			modules[name] = value
			return value
		end
		load("WeaponMotion")
		load("SpecialMotion")
		load("CharacterStats")
		load("WeaponCatalog")
		modules.ProjectileTarget = {
			sweepParams = function(r)
				return { seen = r.hit }
			end,
			predict = function(root)
				return root.Position
			end,
		}
		modules.ShotBatch = {
			fire = function(_, _, _, ...)
				table.insert(c.events, table.pack(...))
			end,
			writer = function()
				return { push = function() end, flush = function() end }
			end,
		}
		local character = {}
		function character:FindFirstChildOfClass()
			return { Health = 100 }
		end
		local owner = { UserId = 123, Character = character }
		local combat = { Shot = {} }
		function combat:GetAttribute()
			return true
		end
		function combat:WaitForChild()
			return {}
		end
		c.ray = load("RayImpact")
		c.projectiles = load("StatProjectiles").new(combat, function(npc, amount, definition, secondary)
			table.insert(c.damage, { npc = npc, amount = amount, definition = definition, secondary = secondary })
			if c.lethal == npc then
				npc.health = 0
			end
		end, function()
			return {}
		end)
		c.definition = {
			id = "41",
			tier = 1,
			kind = "Ranged",
			owner = owner,
			character = character,
			stats = {},
			damage = 100,
			range = 40,
			projectileRadius = 0.12,
			projectileSpeed = 150,
			slotIndex = 1,
			practiceTarget = true,
		}
		function c:npc(name, position, options)
			options = options or {}
			local npc = {
				Name = name,
				tagged = options.tagged ~= false,
				health = options.health or 100,
				present = options.present ~= false,
				practice = options.practice ~= false,
			}
			local root = { Position = position, npc = npc }
			function root:FindFirstAncestorOfClass()
				return npc
			end
			function npc:FindFirstChild()
				return root
			end
			function npc:FindFirstChildOfClass()
				return { Health = self.health }
			end
			function npc:IsDescendantOf()
				return self.present
			end
			function npc:GetAttribute(name)
				return name == "PracticeTarget" and self.practice
			end
			npc.root = root
			table.insert(self.models, npc)
			return npc
		end
		function c:contact(npc, point)
			local part = npc and npc.root or {
				FindFirstAncestorOfClass = function()
					return nil
				end,
			}
			table.insert(self.queue, { Instance = part, Position = point, Normal = Vector3.zAxis })
		end
		function c:step(count)
			for _ = 1, count or 1 do
				self.clock += 1 / 60
				for _, fn in beat.callbacks do
					fn(1 / 60)
				end
			end
		end
		function c:count(npc)
			local count, first = 0, nil
			for _, row in self.damage do
				if row.npc == npc then
					count += 1
					first = first or row
				end
			end
			return count, first
		end
		return c
	end
	-- Exact contact path: both lethal and nonlethal direct hits splash once, and only valid
	-- neighbors receive bounded secondary damage. A lethal direct hit does not add another blast.
	for _, lethal in { false, true } do
		local c = setup()
		local point = Vector3.new(0, 5, -10)
		local direct = c:npc("Direct", point)
		local close = c:npc("Near", point + Vector3.xAxis * 2)
		local edge = c:npc("Edge", point + Vector3.xAxis * 6)
		local excluded = {
			c:npc("Outside", point + Vector3.xAxis * 6.1),
			c:npc("Dead", point + Vector3.xAxis, { health = 0 }),
			c:npc("Untagged", point + Vector3.xAxis, { tagged = false }),
			c:npc("NonPractice", point + Vector3.xAxis, { practice = false }),
			c:npc("Removed", point + Vector3.xAxis, { present = false }),
			c:npc("BehindWall", point - Vector3.xAxis * 2),
		}
		table.insert(c.blocked, excluded[#excluded].root.Position)
		c.lethal = lethal and direct or nil
		c.projectiles:launch(c.definition, Vector3.new(0, 5, 0), point)
		c:contact(direct, point)
		c:step(90)
		local count, hit = c:count(direct)
		check(count == 1 and hit.amount == 100 and not hit.secondary, "Direct hit exactly once, full damage")
		local nearCount, nearHit = c:count(close)
		local edgeCount, edgeHit = c:count(edge)
		check(
			nearCount == 1 and edgeCount == 1 and nearHit.secondary and edgeHit.secondary,
			"Contact hits nearby enemies once as secondary damage"
		)
		check(
			math.abs(nearHit.amount - 45) < 0.001 and math.abs(edgeHit.amount - 15) < 0.001,
			"Real contact applies distance falloff"
		)
		for _, npc in excluded do
			check(c:count(npc) == 0, "Excluded " .. npc.Name)
		end
		check(
			#c.events == 1 and c.events[1][1] == "RayImpact" and c.events[1][4] == 6,
			"One confirmed impact visual with the gameplay radius"
		)
	end
	do
		local c = setup()
		local point = Vector3.new(0, 5, -10)
		local near = c:npc("WallNeighbor", point + Vector3.xAxis * 2)
		c.projectiles:launch(c.definition, Vector3.new(0, 5, 0), point)
		c:contact(nil, point)
		c:step(90)
		check(c:count(near) == 1 and #c.events == 1, "World wall contact also splashes once")
		local miss = setup()
		miss:npc("MissNeighbor", Vector3.new(2, 5, -40))
		miss.projectiles:launch(miss.definition, Vector3.new(0, 5, 0), Vector3.new(0, 5, -40))
		miss:step(90)
		check(#miss.events == 0 and #miss.damage == 0, "A range-end miss has no phantom blast")
	end
	do
		local c = setup()
		c.definition.stats.Pierce = 1
		local first = c:npc("First", Vector3.new(0, 5, -10))
		local splashed = c:npc("SplashedInFlight", Vector3.new(0, 5, -13))
		local last = c:npc("SecondDirect", Vector3.new(0, 5, -23))
		c.projectiles:launch(c.definition, Vector3.new(0, 5, 0), Vector3.new(0, 5, -40))
		c:contact(first, first.root.Position)
		c:step()
		c:contact(splashed, splashed.root.Position)
		c:contact(last, last.root.Position)
		c:step(90)
		check(
			c:count(first) == 1 and c:count(splashed) == 1 and c:count(last) == 1,
			"Piercing cannot directly hit its earlier splash victim"
		)
		check(
			select(2, c:count(last)).amount == 70 and #c.events == 2,
			"Pierced contact preserves the existing 70% damage decay"
		)
	end
	do
		local c = setup()
		for tier = 1, 4 do
			c.definition.tier = tier
			local radius = c.ray.radius(c.definition)
			local previous = math.huge
			for i = 0, 100 do
				local factor = c.ray.factor(c.definition, radius * i / 100)
				check(factor > 0 and factor <= previous, "Each tier has positive, decreasing splash")
				previous = factor
			end
			check(c.ray.factor(c.definition, radius + 0.01) == 0, "No damage beyond radius")
		end
		c.definition.stats.AreaSize = 10000
		check(c.ray.radius(c.definition) == 12, "AreaSize cannot grow splash beyond twelve studs")
		c.definition.stats.AreaSize = 0
		c.definition.tier = 1
		-- Deliberately reverse candidate order: the cap must choose the nearest enemies.
		for i = 16, 1, -1 do
			c:npc(tostring(i), Vector3.xAxis * (i / 4))
		end
		local damage, seen = {}, {}
		local callback
		callback = function(npc, amount)
			check(seen[npc] == true, "Victim is recorded before callback")
			damage[npc.Name] = amount
		end
		local count = c.ray.apply(c.definition, Vector3.zero, nil, seen, c.models, function()
			return true
		end, callback)
		check(
			count == 12 and damage["1"] and damage["12"] and not damage["13"],
			"Splash cap selects the twelve nearest victims"
		)
		local same = c.ray.apply(c.definition, Vector3.zero, nil, seen, c.models, function()
			return true
		end, callback)
		check(same == 4, "Later contacts only consider still-unhit victims")
		check(c.ray.apply(c.definition, Vector3.zero, nil, seen, c.models, function()
			return true
		end, callback) == 0, "No victim repeats across the flight")
	end
	return { checks = checks }
end

-- Server Play only. Uses the installed StatProjectiles and actual Spherecast/raycast filters.
-- All targets are anchored practice models, far from play; recording callback never damages them.
-- One empty Heartbeat connection remains until Stop Play, as with the production test harnesses.
function Tests.live()
	assert(game:GetService("RunService"):IsServer(), "Run on the Play server")
	local player = assert(game:GetService("Players"):GetPlayers()[1], "A live player is required")
	local character = assert(player.Character, "Player character required")
	local hum = assert(character:FindFirstChildOfClass("Humanoid"), "Living character required")
	assert(hum.Health > 0, "Living character required")
	local tags = game:GetService("CollectionService")
	local folder = Instance.new("Folder")
	folder.Name = "RayImpactQA"
	folder.Parent = workspace
	local actors = Instance.new("Folder")
	actors.Name = "Targets"
	actors.Parent = folder
	local checks, hits, events = 0, {}, {}
	local origin = Vector3.new(7200, 1200, 7200)
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local function remote(record)
		return {
			FireAllClients = function(_, ...)
				if record then
					table.insert(events, table.pack(...))
				end
			end,
			FireClient = function(_, _, ...)
				if record then
					table.insert(events, table.pack(...))
				end
			end,
		}
	end
	local combat = { Shot = remote(false), GodlyFX = remote(true) }
	function combat:GetAttribute()
		return true
	end
	function combat:WaitForChild(name)
		return self[name]
	end
	local projectile = require(game:GetService("ServerScriptService"):WaitForChild("StatProjectiles")).new(
		combat,
		function(npc, amount, _, secondary)
			table.insert(hits, { npc = npc, amount = amount, secondary = secondary })
		end,
		function(_, wallOnly)
			local p = RaycastParams.new()
			p.FilterType = Enum.RaycastFilterType.Exclude
			p.FilterDescendantsInstances = wallOnly and { character, actors } or { character }
			return p
		end,
		2 ^ 29
	)
	local function part(parent, name, point, size)
		local p = Instance.new("Part")
		p.Name = name
		p.Size = size
		p.Anchored = true
		p.CanCollide = false
		p.CanTouch = false
		p.CanQuery = true
		p.Position = origin + point
		p.Parent = parent
		return p
	end
	local function npc(name, point, options)
		options = options or {}
		local model = Instance.new("Model")
		model.Name = name
		model:SetAttribute("PracticeTarget", options.practice ~= false)
		model:SetAttribute("LobbyDummy", true)
		part(model, "HumanoidRootPart", point, Vector3.new(1, 2, 1))
		local h = Instance.new("Humanoid")
		h.BreakJointsOnDeath = false
		h.RequiresNeck = false
		h.EvaluateStateMachine = false
		h.MaxHealth = 1000
		h.Health = options.dead and 0 or 1000
		h.Parent = model
		model.Parent = actors
		if options.tagged ~= false then
			tags:AddTag(model, "RogueliteZombie")
		end
		return model
	end
	local function count(model)
		local n, row = 0, nil
		for _, hit in hits do
			if hit.npc == model then
				n += 1
				row = hit
			end
		end
		return n, row
	end
	local definition = {
		id = "41",
		tier = 1,
		kind = "Ranged",
		owner = player,
		character = character,
		stats = {},
		damage = 100,
		range = 40,
		projectileRadius = 0.12,
		projectileSpeed = 150,
		slotIndex = 1,
		practiceTarget = true,
	}
	local ok, result = pcall(function()
		local direct = npc("Direct", Vector3.new(0, 0, -12))
		local close = npc("Near", Vector3.new(2, 0, -11.5))
		local far = npc("Far", Vector3.new(5, 0, -11.5))
		local blocked = npc("Blocked", Vector3.new(-4, 0, -11.5))
		local outside = npc("Outside", Vector3.new(7, 0, -11.5))
		local dead = npc("Dead", Vector3.new(3, 0, -13), { dead = true })
		local ordinary = npc("NotPractice", Vector3.new(3, 0, -14), { practice = false })
		local friendly = npc("Untagged", Vector3.new(3, 0, -9), { tagged = false })
		part(folder, "SplashWall", Vector3.new(-2, 0, -11.5), Vector3.new(0.3, 8, 6))
		projectile:launch(definition, origin, origin - Vector3.zAxis * 40)
		task.wait(0.7)
		local directCount, directHit = count(direct)
		check(
			directCount == 1 and directHit.amount == 100 and not directHit.secondary,
			"Real swept direct contact damages once"
		)
		local nearCount, nearHit = count(close)
		local farCount, farHit = count(far)
		check(
			nearCount == 1
				and farCount == 1
				and nearHit.secondary
				and farHit.secondary
				and nearHit.amount > farHit.amount,
			"Actual neighboring models receive falling secondary damage"
		)
		for _, model in { blocked, outside, dead, ordinary, friendly } do
			check(count(model) == 0, "Real physics excludes " .. model.Name)
		end
		check(
			#events == 1 and events[1][1] == "RayImpact" and events[1][4] == 6,
			"One actual-contact visual, matching six-stud radius"
		)
		check(hum.Health > 0 and direct.Humanoid.Health == 1000, "Recording-only fixture never applies gameplay damage")
		-- A separate miss runs its full range without any burst or nearby damage.
		local beforeHits, beforeEvents = #hits, #events
		projectile:launch(definition, origin + Vector3.xAxis * 40, origin + Vector3.xAxis * 40 - Vector3.zAxis * 40)
		task.wait(0.7)
		check(#hits == beforeHits and #events == beforeEvents, "Actual range-end miss does not explode")
		return {
			checks = checks,
			direct = directHit.amount,
			near = nearHit.amount,
			far = farHit.amount,
			effects = #events,
		}
	end)
	for _, model in actors:GetChildren() do
		tags:RemoveTag(model, "RogueliteZombie")
	end
	folder:Destroy()
	assert(ok, result)
	return result
end

return Tests
