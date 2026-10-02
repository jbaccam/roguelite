-- Launch-audit P7/P8/P12 checks for enemy attacks, runnable in Edit with no instances: the real
-- EnemyAttacks and ZombieAttacks sources run against stub enemies, a stub player and a fake clock.
-- - Shots: the client's flight math (EnemyProjectileVisuals) puts each shot exactly where the
--   server has it, every frame, through a pause, a wall stop and a time-out.
-- - Facing: the AttackFacing write is skipped until the aim turns more than ~2 degrees, while the
--   hit still lands at the same moment.
-- - QA tallies (hits, impacts, serials) replace the per-hit attributes.
-- Usage (execute_luau, Edit, dev server running): load this file, EnemyProjectileVisuals,
-- EnemyCatalog and ZombieTypes from the repo with loadstring, then
--   tests({ EnemyAttacks = <source text>, ZombieAttacks = <source text> }, Visuals, Catalog, Types)
-- It loadstrings the two attack modules itself with stubbed game/workspace/require/Instance, so
-- nothing in the place is created, changed or required. 2026-10-02: 5,907 checks pass.
return function(sources, Visuals, Catalog, Types)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local function near(a, b, eps)
		return (a - b).Magnitude <= (eps or 1e-6)
	end

	-- Pure flight math (the examples in EnemyProjectileVisuals).
	check(Visuals.flown(10, 10.5) == 0.5, "Flown since launch")
	check(Visuals.flown(10, 9.9) == 0, "Never before its launch")
	check(Visuals.flown(10, 12, 10.5) == 0.5, "Held while the run is paused")
	check(Visuals.flown(19.5 + 15, 35.5) == 1, "Frozen 15 s: counts on from where it hung")
	local f = Visuals.shotFrame(Vector3.zero, Vector3.new(0, 0, -35), 0.5)
	check(near(f.Position, Vector3.new(0, 0, -17.5)) and near(f.LookVector, Vector3.new(0, 0, -1)), "Shot frame")

	-- World stubs shared by both modules.
	local world = { clock = 100, attrs = { ZombiesEnabled = true }, events = {}, wallZ = nil }
	local remote = {
		FireAllClients = function(_, ...)
			table.insert(world.events, table.pack(...))
		end,
	}
	local combat = {
		WaitForChild = function(_, name)
			return name
		end,
		FindFirstChild = function(_, name)
			return name == "EnemyShot" and remote or nil
		end,
		GetAttribute = function(_, name)
			return world.attrs[name]
		end,
	}
	local heartbeats = {}
	local RunService = {
		Heartbeat = {
			Connect = function(_, fn)
				table.insert(heartbeats, fn)
			end,
		},
	}
	local targetHumanoid = { Health = 100 }
	local targetRoot = { Position = Vector3.new(0, 3, -20), AssemblyLinearVelocity = Vector3.zero }
	local character = {
		FindFirstChild = function(_, name)
			return name == "HumanoidRootPart" and targetRoot or nil
		end,
		FindFirstChildOfClass = function(_, class)
			return class == "Humanoid" and targetHumanoid or nil
		end,
	}
	targetRoot.Parent = character
	local player = { Character = character, UserId = 1 }
	local Players = {
		GetPlayers = function()
			return { player }
		end,
		GetPlayerFromCharacter = function(_, c)
			return c == character and player or nil
		end,
	}
	local contacts = {}
	local Characters = {
		states = { [player] = { lastContact = -math.huge } },
		contact = function(p, amount, _, npc)
			table.insert(contacts, { player = p, amount = amount, npc = npc, at = world.clock })
			return amount
		end,
	}
	local workspaceStub = {
		GetServerTimeNow = function()
			return world.clock
		end,
		FindFirstChild = function()
			return nil
		end,
		-- Straight-down rays find the floor at y=0; a wall at z=wallZ blocks rays that cross it.
		Raycast = function(_, origin, direction)
			if direction.X == 0 and direction.Z == 0 and direction.Y < 0 then
				return { Position = Vector3.new(origin.X, 0, origin.Z), Normal = Vector3.yAxis }
			end
			local z = world.wallZ
			if z and direction.Z ~= 0 then
				local t = (z - origin.Z) / direction.Z
				if t >= 0 and t <= 1 then
					return { Position = origin + direction * t, Normal = Vector3.zAxis }
				end
			end
			return nil
		end,
	}
	-- Attachments and AlignOrientations as plain tables that count CFrame writes.
	local function fakeInstance(class)
		local store = { ClassName = class }
		return setmetatable({}, {
			__index = store,
			__newindex = function(_, k, v)
				if k == "CFrame" then
					store.writes = (store.writes or 0) + 1
				end
				if k == "Parent" and v then
					v.children[store.Name] = store.self
				end
				store[k] = v
			end,
		}),
			store
	end
	local Instance = {
		new = function(class)
			assert(class == "Attachment" or class == "AlignOrientation", "Unexpected Instance.new " .. tostring(class))
			local proxy, store = fakeInstance(class)
			store.self = proxy
			return proxy
		end,
	}
	local game = {
		GetService = function(_, name)
			return name == "Players" and Players or name == "RunService" and RunService or error("No stub for " .. name)
		end,
		ReplicatedStorage = {
			WaitForChild = function()
				return combat
			end,
		},
	}
	local stubs = {
		EnemyCatalog = {
			fromModel = function(npc)
				return npc.config
			end,
		},
		EnemyMotion = {
			load = function()
				return nil
			end,
		},
		CharacterService = Characters,
		ZombieTypes = Types,
	}
	local function load(name)
		local fn = assert(loadstring(sources[name], "=" .. name))
		setfenv(
			fn,
			setmetatable({
				game = game,
				workspace = workspaceStub,
				script = {
					Parent = {
						WaitForChild = function(_, n)
							return n
						end,
					},
				},
				require = function(n)
					return assert(stubs[n], "No stub for " .. tostring(n))
				end,
				Instance = Instance,
				RaycastParams = {
					new = function()
						return {}
					end,
				},
			}, { __index = getfenv(0) })
		)
		return fn()
	end
	local A = load("EnemyAttacks")
	local Z = load("ZombieAttacks")
	check(#heartbeats == 1, "EnemyAttacks steps its shots on one Heartbeat")
	local stepShots = heartbeats[1]
	local function makeNpc(config, position, attrs)
		local root = { Position = position, AssemblyLinearVelocity = Vector3.zero, children = {} }
		root.CFrame = CFrame.lookAt(position, position + Vector3.new(0, 0, -1))
		function root:FindFirstChild(n)
			return self.children[n]
		end
		local h = {
			Health = 100,
			AutoRotate = true,
			Move = function() end,
			MoveTo = function() end,
		}
		local npc = { config = config, attrs = attrs or {}, attributeWrites = 0 }
		function npc:FindFirstChildOfClass(c)
			return c == "Humanoid" and h or nil
		end
		function npc:FindFirstChild(n)
			return n == "HumanoidRootPart" and root or nil
		end
		function npc:IsDescendantOf()
			return true
		end
		function npc:GetAttribute(n)
			return self.attrs[n]
		end
		function npc:SetAttribute(n, v)
			self.attrs[n] = v
			self.attributeWrites += 1
		end
		return npc, root
	end
	local function facingWrites(root)
		local align = root.children.AttackFacing
		return align and align.writes or 0
	end

	-- The client's view of the shots, built only from the events, the way EnemyVisuals does it.
	local client = { shots = {}, held = nil, read = 0 }
	local function eventsSince(first, name)
		local found = {}
		for i = first, #world.events do
			if world.events[i][1] == name then
				table.insert(found, world.events[i])
			end
		end
		return found
	end
	local function readEvents()
		for i = client.read + 1, #world.events do
			local e = world.events[i]
			if e[1] == "Launch" then
				client.shots[e[2]] = { kind = e[3], origin = e[4], velocity = e[5], started = e[6], lifetime = e[7] }
			elseif e[1] == "End" then
				client.shots[e[2]] = nil
			elseif e[1] == "Hold" then
				client.held = e[2]
			elseif e[1] == "Resume" then
				for _, s in client.shots do
					s.started += e[2]
				end
				client.held = nil
			end
		end
		client.read = #world.events
	end
	-- Every frame: each server shot that was sent is drawn exactly where the server has it, and a
	-- client shot past its lifetime is exactly one the server has dropped.
	local compared, worst = 0, 0
	local function compare()
		readEvents()
		for _, p in A.shots do
			if p.sent then
				local s = client.shots[p.id]
				check(s ~= nil, "Client knows every sent shot")
				local flown = Visuals.flown(s.started, world.clock, client.held)
				check(flown < s.lifetime + 1e-9, "Client shot still alive while the server's is")
				-- Vector3 is 32-bit: a thousandth of a stud is rounding, not drift.
				local drawn = Visuals.shotFrame(s.origin, s.velocity, flown).Position
				check(near(drawn, p.position, 1e-3), "Client shot on the server's position")
				worst = math.max(worst, (drawn - p.position).Magnitude)
				compared += 1
			end
		end
		for id, s in client.shots do
			local live = false
			for _, p in A.shots do
				live = live or p.id == id
			end
			if not live then
				check(Visuals.flown(s.started, world.clock, client.held) >= s.lifetime - 1e-9, "Only a timed-out shot outlives the server's")
				client.shots[id] = nil
			end
		end
	end
	-- One frame in the chase loop's order, or the other way round (Heartbeat order isn't fixed).
	-- idle: the enemy isn't updated (frozen by a pause, or done for the scenario).
	local frameDts = { 1 / 60, 1 / 48, 1 / 60, 1 / 72, 1 / 30 }
	local frame = 0
	local function step(npc, shotsFirst, idle)
		frame += 1
		local dt = frameDts[frame % #frameDts + 1]
		world.clock += dt
		if shotsFirst then
			stepShots(dt)
		end
		if not idle then
			A.update(npc, targetRoot, dt)
		end
		if not shotsFirst then
			stepShots(dt)
		end
		compare()
		return dt
	end

	-- 1. A bow skeleton shoots a standing player 20 studs away, paused mid-flight for 15 s.
	for _, shotsFirst in { false, true } do
		table.clear(contacts)
		targetRoot.Position = Vector3.new(0, 3, -20)
		local bow = Catalog.get("bow-skeleton")
		local npc = makeNpc(bow, Vector3.new(0, 3, 0), { AttackDamage = bow.damage })
		local first = #world.events + 1
		local released, launched = nil, nil
		for _ = 1, 400 do
			step(npc, shotsFirst)
			released = released or (#A.shots > 0 and world.clock)
			launched = launched or eventsSince(first, "Launch")[1]
			if launched and #contacts == 0 and world.clock - launched[6] > 0.2 then
				break
			end
		end
		check(launched and launched[3] == "Arrow", "Arrow launched")
		check(math.abs(launched[5].Magnitude - 35) < 1e-3 and launched[5].Unit.Z < -0.99, "Arrow flies at its speed toward the player")
		local start = npc.attrs.EnemyAttackStart
		check(released - start >= bow.attackImpact and released - start < bow.attackImpact + 1 / 29, "Released at impact time")
		-- Pause: no frame moves the shot, the client holds it, then both carry on.
		world.attrs.RunPaused = true
		local before = A.shots[1].position
		for _ = 1, 15 * 60 do
			step(npc, shotsFirst, true)
		end
		check(A.shots[1].position == before, "Server shot hangs while paused")
		check(#eventsSince(first, "Hold") == 1, "One Hold for the whole pause")
		world.attrs.RunPaused = nil
		local hitAt
		for _ = 1, 200 do
			step(npc, shotsFirst)
			if #contacts > 0 then
				hitAt = world.clock
				break
			end
		end
		check(#eventsSince(first, "Resume") == 1, "One Resume after it")
		check(hitAt ~= nil and #contacts == 1 and contacts[1].amount == bow.damage, "The arrow hits once after the pause")
		check(#eventsSince(first, "End") == 1 and next(client.shots) == nil, "The hit's End removes the client's shot")
		local t = A.tally[npc]
		-- Its cooldown ran out during the 15 s pause, so a second draw starts as it resumes.
		check(t and t.hits == 1 and t.serial == 2 and t.lastDamage == bow.damage and t.lastImpact, "QA tally: one hit, two attacks")
		check(npc.attrs.EnemyHits == nil and npc.attrs.LastEnemyImpact == nil and npc.attrs.EnemyAttackSerial == nil, "No per-hit attributes")
		for _ = 1, 120 do
			step(npc, shotsFirst, true)
		end
	end

	-- 2. A wall stops a shot early: the End reaches the client before its lifetime.
	do
		local bow = Catalog.get("bow-skeleton")
		local npc = makeNpc(bow, Vector3.new(40, 3, 0), { AttackDamage = bow.damage })
		targetRoot.Position = Vector3.new(40, 3, -20)
		table.clear(contacts)
		local first = #world.events + 1
		for _ = 1, 200 do
			step(npc, false, world.wallZ ~= nil)
			if #A.shots > 0 and A.shots[1].sent then
				world.wallZ = -8
			end
			if world.wallZ and #A.shots == 0 then
				break
			end
		end
		world.wallZ = nil
		local ends = eventsSince(first, "End")
		check(#ends == 1 and #contacts == 0 and next(client.shots) == nil, "A wall stop sends an End and nobody is hit")
		for _ = 1, 160 do
			step(npc, false, true)
		end
	end

	-- 3. The player steps out of the path: the shot times out on both sides, with no End sent.
	do
		local bow = Catalog.get("bow-skeleton")
		local npc = makeNpc(bow, Vector3.new(80, 3, 0), { AttackDamage = bow.damage })
		targetRoot.Position = Vector3.new(80, 3, -20)
		local before = #world.events
		local sent = false
		for _ = 1, 400 do
			step(npc, false, sent)
			if #A.shots > 0 and A.shots[1].sent then
				sent = true
				targetRoot.Position = Vector3.new(200, 3, -20)
			end
			if sent and #A.shots == 0 then
				break
			end
		end
		local ended = false
		for i = before + 1, #world.events do
			ended = ended or world.events[i][1] == "End"
		end
		check(sent and #A.shots == 0 and not ended, "A timed-out shot ends on the clients by itself")
		readEvents()
		compare()
		check(next(client.shots) == nil, "And the client has dropped it at the same moment")
	end
	check(compared > 1000, "Compared client and server shots on many frames")

	-- 4. Facing: a skeleton swings at a still player, then at one strafing past at 8 studs/s.
	local facing = {}
	for _, strafe in { 0, 8 } do
		local skeleton = Catalog.get("skeleton")
		local npc, root = makeNpc(skeleton, Vector3.new(0, 3, 300), { AttackDamage = skeleton.damage })
		targetRoot.Position = Vector3.new(0, 3, 296)
		table.clear(contacts)
		local start, frames, impact = nil, 0, nil
		for _ = 1, 200 do
			local dt = step(npc, false)
			targetRoot.Position += Vector3.new(strafe * dt, 0, 0)
			start = start or npc.attrs.EnemyAttackStart
			if start and A.busy(npc) then
				frames += 1
			end
			impact = impact or (A.tally[npc] and A.tally[npc].lastImpact)
			if start and not A.busy(npc) then
				break
			end
		end
		check(start and impact - start >= skeleton.attackImpact and impact - start < skeleton.attackImpact + 1 / 29, "Swing lands at its impact time")
		check(#contacts == 1, "The swing hits once")
		facing[strafe] = { writes = facingWrites(root), frames = frames }
		check(facingWrites(root) <= frames, "Never more writes than frames")
		for _ = 1, 90 do
			step(npc, false, true)
		end
	end
	check(facing[0].writes == 1, "A still target: one facing write per swing")
	check(A.faceDue(nil, Vector3.zAxis) and not A.faceDue(Vector3.zAxis, Vector3.zAxis), "First write always; same aim never")
	local turned = function(deg)
		return CFrame.Angles(0, math.rad(deg), 0):VectorToWorldSpace(Vector3.zAxis)
	end
	check(not A.faceDue(Vector3.zAxis, turned(1.9)) and A.faceDue(Vector3.zAxis, turned(2.1)), "Written past 2 degrees")

	-- 5. The Mutant's slam: lands at its impact time, hits once, tallied, few facing writes.
	do
		local mutant = Catalog.get("Mutant") or { legacy = "Mutant" }
		local npc, root = makeNpc(mutant, Vector3.new(0, 3, 500), { ZombieType = "Mutant", SlamDamage = 5 })
		targetRoot.Position = Vector3.new(0, 3, 495)
		table.clear(contacts)
		local start, impact, frames = nil, nil, 0
		for _ = 1, 200 do
			world.clock += 1 / 60
			Z.update(npc, targetRoot)
			start = start or npc.attrs.SlamStart
			if Z.busy(npc) then
				frames += 1
			end
			impact = impact or (Z.tally[npc] and Z.tally[npc].lastImpact)
			if start and not Z.busy(npc) then
				break
			end
		end
		check(start and impact - start >= Types.Slam.impact and impact - start < Types.Slam.impact + 1 / 59, "Slam lands at its impact time")
		check(#contacts == 1 and contacts[1].amount == 5, "The slam hits once")
		local t = Z.tally[npc]
		check(t.hits == 1 and t.serial == 1 and t.lastDamage == 5, "Slam QA tally")
		check(npc.attrs.SlamHits == nil and npc.attrs.SlamSerial == nil and npc.attrs.LastSlamImpact == nil, "No per-hit slam attributes")
		check(facingWrites(root) == 1 and frames > 30, "A still target: one facing write per slam")
		facing.slam = { writes = facingWrites(root), frames = frames }
	end
	return {
		checks = checks,
		comparedFrames = compared,
		worstStuds = worst,
		stillSwing = facing[0],
		strafeSwing = facing[8],
		slam = facing.slam,
	}
end
