-- Server-owned regular enemy attacks. No client-supplied hit/target claims.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local combat = game.ReplicatedStorage:WaitForChild("RogueliteCombat")
local Catalog = require(combat:WaitForChild("EnemyCatalog"))
local Motion = require(combat:WaitForChild("EnemyMotion"))
local Characters = require(script.Parent:WaitForChild("CharacterService"))
local A = {}
local states = setmetatable({}, { __mode = "k" })
local projectiles = {}
A.shots = projectiles -- shots in flight, read by EnemyShotTests
-- Shots are drawn on the clients (EnemyVisuals); the server keeps only the flight and hit test
-- below. Each shot sends a Launch (and an End if it stops early), instead of a replicated part
-- moved every frame: an arrow's 2 s flight was ~120 CFrame updates to every client, now 1-2 events.
-- ("Launch", id, kind, origin, velocity, started, lifetime), ("End", id), and while the run is
-- paused ("Hold", at) / ("Resume", frozenSeconds).
local shotEvent = combat:FindFirstChild("EnemyShot") or Instance.new("RemoteEvent")
shotEvent.Name = "EnemyShot"
shotEvent.Parent = combat
local shotSerial = 0
-- Hits, impacts and attack serials per enemy, for Studio QA (RegularEnemyQA). A server table, not
-- attributes: those replicated to every client on every hit and no client read them.
A.tally = setmetatable({}, { __mode = "k" })
local function tally(npc)
	local t = A.tally[npc]
	if not t then
		t = { hits = 0, serial = 0 }
		A.tally[npc] = t
	end
	return t
end
local function params(npc)
	local excluded = { npc }
	local enemies = workspace:FindFirstChild("RogueliteEnemies")
	if enemies then
		table.insert(excluded, enemies)
	end
	for _, p in Players:GetPlayers() do
		if p.Character then
			table.insert(excluded, p.Character)
		end
	end
	local p = RaycastParams.new()
	p.FilterType = Enum.RaycastFilterType.Exclude
	p.FilterDescendantsInstances = excluded
	return p
end
local function alive(npc)
	local h = npc:FindFirstChildOfClass("Humanoid")
	local root = npc:FindFirstChild("HumanoidRootPart")
	return npc:IsDescendantOf(workspace)
		and not npc:GetAttribute("PracticeTarget")
		and h
		and h.Health > 0
		and root
		and combat:GetAttribute("ZombiesEnabled") == true,
		h,
		root
end
local function validPlayer(player)
	local char = player.Character
	local root = char and char:FindFirstChild("HumanoidRootPart")
	local h = char and char:FindFirstChildOfClass("Humanoid")
	return Characters.states[player] and root and h and h.Health > 0, root
end
-- Attacks don't root an enemy: it keeps walking (the chase loop steers) and keeps turning toward
-- its target at this rate, so a swing lands where the enemy is at impact instead of where the
-- player was when it started.
local TURN_RATE = math.rad(540)
-- Melee forgiveness (user, 2026-09-30: dodging by changing direction was too easy). A swing starts
-- TRIGGER_BONUS studs before attackRange, then hits anyone within its reach + REACH_BONUS whose
-- direction is within ~95 degrees of the facing (ARC_DOT), checked every frame for HIT_WINDOW
-- seconds from impact instead of one frame. Example, a normal zombie (4.6 reach, 0.35 s impact):
-- it swings at 5 studs and connects out to its reach, 4.6 studs centre to centre: about 2 studs
-- between the bodies, an arm. A player who backs off as it swings sees it whiff.
-- (2026-10-01: the user kept a longer reach, +1.5 at 6.1 studs, over the arm's-length +0.5. On
-- 2026-10-03 it was "a little too much range" at +0.9, then still "hitting me when im not even
-- really in their physical range": no bonus now.)
local TRIGGER_BONUS = 0.4
local REACH_BONUS = 0
local LUNGE_REACH_BONUS = 0.2
local ARC_DOT = -0.1
local HIT_WINDOW = 0.15
-- Ranged enemies stop to shoot (MAP_MOB_ROSTER: "stops, aims, and fires"), from the draw until
-- this long after release; walking on through the shot slid them across the ground.
local RANGED_PLANT_AFTER = 0.2
-- A lunge ends this far past where the player stood at the strike, or where it connects, instead
-- of flying its full length straight through them (a snake's dash is 11 studs).
local LUNGE_FOLLOW = 1.5
-- Shots lead the target: aimed where a player running straight will be when the shot arrives,
-- at most this many seconds ahead (an arrow flies about 2 s). Changing direction still dodges.
local MAX_LEAD = 2.5
local function turnToward(from, to, maxAngle)
	local angle = math.acos(math.clamp(from:Dot(to), -1, 1))
	if angle <= maxAngle then
		return to
	end
	return CFrame.Angles(0, from:Cross(to).Y >= 0 and maxAngle or -maxAngle, 0):VectorToWorldSpace(from)
end
-- The body turns through an AlignOrientation, never CFrame writes: re-aiming a walking Humanoid's
-- root by CFrame every frame stops its walk dead (measured 16 -> 0 studs/s), while the constraint
-- turns it and it keeps walking (16.3 studs/s).
-- It is written only once the aim has turned more than ~2 degrees since the last write: each write
-- replicates, and a target straight ahead needn't send 60 a second. Hits use s.direction itself.
local FACE_DOT = math.cos(math.rad(2))
function A.faceDue(faced, direction)
	return not faced or faced:Dot(direction) < FACE_DOT
end
local function face(root, s)
	if not A.faceDue(s.faced, s.direction) then
		return
	end
	s.faced = s.direction
	local align = root:FindFirstChild("AttackFacing")
	if not align then
		local attachment = Instance.new("Attachment")
		attachment.Name = "AttackFacingAttachment"
		attachment.Parent = root
		align = Instance.new("AlignOrientation")
		align.Name = "AttackFacing"
		align.Mode = Enum.OrientationAlignmentMode.OneAttachment
		align.Attachment0 = attachment
		align.MaxTorque = math.huge
		align.Responsiveness = 60
		align.Parent = root
	end
	align.CFrame = CFrame.lookAt(Vector3.zero, s.direction)
	align.Enabled = true
end
-- Attack over: the Humanoid steers its own facing again.
local function release(npc, h)
	local root = npc:FindFirstChild("HumanoidRootPart")
	local align = root and root:FindFirstChild("AttackFacing")
	if align then
		align.Enabled = false
	end
	if h then
		h.AutoRotate = true
	end
end
local function track(root, target, s, dt)
	if target and target.Parent then
		local delta = target.Position - root.Position
		local flat = Vector3.new(delta.X, 0, delta.Z)
		if flat.Magnitude > 0.05 then
			s.direction = turnToward(s.direction, flat.Unit, TURN_RATE * math.min(dt or 1 / 60, 0.1))
		end
	end
	face(root, s)
end
function A.segmentDistance(a, b, p)
	local delta = b - a
	local t = delta:Dot(delta) > 1e-8 and math.clamp((p - a):Dot(delta) / delta:Dot(delta), 0, 1) or 0
	return (p - (a + delta * t)).Magnitude, t
end
-- Where a shot fired from `from` at `speed` meets a target at `position` moving at `velocity`
-- (flat): the earliest t with |position + velocity*t - from| = speed*t. Example: a player 20
-- studs away running sideways at 24 studs/s, an arrow at 35: it meets them 0.79 s later, 19
-- studs to the side. No meeting within MAX_LEAD (outrunning the shot): aim at them as they are.
function A.intercept(from, position, velocity, speed)
	local v = Vector3.new(velocity.X, 0, velocity.Z)
	local d = position - from
	local a, b, c = v:Dot(v) - speed * speed, 2 * d:Dot(v), d:Dot(d)
	local t
	if math.abs(a) < 1e-6 then
		t = b < 0 and -c / b or nil
	else
		local disc = b * b - 4 * a * c
		if disc >= 0 then
			local root = math.sqrt(disc)
			local t1, t2 = (-b - root) / (2 * a), (-b + root) / (2 * a)
			t = math.min(t1 > 0 and t1 or math.huge, t2 > 0 and t2 or math.huge)
		end
	end
	if not t or t > MAX_LEAD then
		return position
	end
	return position + v * t
end
local function damage(npc, player, amount)
	local config = Catalog.fromModel(npc)
	if config and config.legacy then
		-- Preserve the original native-zombie shared contact grace period.
		local state = Characters.states[player]
		local now = os.clock()
		if not state or now - state.lastContact < 0.8 then
			return
		end
		state.lastContact = now
	end
	local actual = Characters.contact(player, amount, nil, npc)
	local t = tally(npc)
	t.hits += 1
	t.lastDamage = actual
end
local function melee(npc, root, config, s)
	for _, player in Players:GetPlayers() do
		local ok, pr = validPlayer(player)
		if ok and not s.hitPlayers[player] then
			local delta = pr.Position - root.Position
			local flat = Vector3.new(delta.X, 0, delta.Z)
			if
				math.abs(delta.Y) <= config.maxHeight
				and flat.Magnitude
					<= (config.hitRange or config.attackRange)
						+ (config.behavior == "Lunge" and LUNGE_REACH_BONUS or REACH_BONUS)
				and (flat.Magnitude < 0.1 or flat.Unit:Dot(s.direction) > ARC_DOT)
				and not workspace:Raycast(root.Position, delta, s.params)
			then
				s.hitPlayers[player] = true
				damage(npc, player, npc:GetAttribute("AttackDamage") or config.damage)
			end
		end
	end
end
local function projectile(npc, root, config, s, target)
	local start = root.Position + Vector3.yAxis * 0.6 + s.direction * (config.radius + 0.4)
	if config.projectile then
		local data = Motion.load(config.id)
		if data and data.projectile then
			local origin = Motion.projectileOrigin(npc, data, Motion.sample(data, "Attack", data.motion.attackImpact))
			if origin then
				start = origin
			end
		end
	end
	if workspace:Raycast(root.Position, start - root.Position, s.params) then
		return
	end
	-- Released at where the target will be (A.intercept); the shot still travels, so it can be dodged.
	if target and target.Parent then
		s.aim = A.intercept(start, target.Position, target.AssemblyLinearVelocity, config.projectileSpeed)
	end
	local direction = s.aim - start
	if direction.Magnitude < 0.01 then
		return
	end
	shotSerial += 1
	local lifetime = config.attackRange / config.projectileSpeed + 1
	table.insert(projectiles, {
		id = shotSerial,
		kind = config.projectile,
		source = npc,
		origin = start,
		position = start,
		velocity = direction.Unit * config.projectileSpeed,
		lifetime = lifetime,
		remaining = lifetime,
		flown = 0,
		damage = npc:GetAttribute("AttackDamage") or config.damage,
		params = s.params,
	})
end
-- Server time the shots in flight last moved at, while a paused run holds them (plan L).
local heldAt = nil
local HEIGHTS = { -1.3, 0, 1.3 }
RunService.Heartbeat:Connect(function(dt)
	if #projectiles == 0 and not heldAt then
		return
	end
	local now = workspace:GetServerTimeNow()
	-- Plan L: shots in flight hang while the run is paused, then carry on (lifetime counts frames).
	-- Clients hold theirs at the frame these last moved and, on Resume, start them later by the
	-- frozen time. Example: frozen from t=20 to t=35, a shot launched at t=19.5 counts from t=34.5.
	if combat:GetAttribute("RunPaused") == true then
		if not heldAt and #projectiles > 0 then
			heldAt = now - dt
			shotEvent:FireAllClients("Hold", heldAt)
		end
		return
	end
	if heldAt then
		shotEvent:FireAllClients("Resume", now - dt - heldAt)
		heldAt = nil
	end
	local enabled = combat:GetAttribute("ZombiesEnabled") == true
	for i = #projectiles, 1, -1 do
		local p = projectiles[i]
		p.remaining -= dt
		local stop = p.remaining <= 0 or not enabled
		if not stop then
			local finish = p.position + p.velocity * dt
			local wall = workspace:Raycast(p.position, finish - p.position, p.params)
			local wallT = wall and (wall.Position - p.position).Magnitude / (finish - p.position).Magnitude or math.huge
			local closest, closestT = nil, wallT
			for _, player in Players:GetPlayers() do
				local ok, pr = validPlayer(player)
				if ok then
					for _, height in HEIGHTS do
						local distance, t = A.segmentDistance(p.position, finish, pr.Position + Vector3.yAxis * height)
						if distance <= 1.15 and t < closestT then
							closest = player
							closestT = t
						end
					end
				end
			end
			if closest then
				damage(p.source, closest, p.damage)
				stop = true
			elseif wall then
				stop = true
			else
				p.position = finish
				p.flown += dt
				-- Sent after its first step, timed so that origin + velocity * (now - started) is
				-- where it is now. A shot stopped on its first step isn't sent (it showed a frame at most).
				if not p.sent then
					p.sent = true
					shotEvent:FireAllClients("Launch", p.id, p.kind, p.origin, p.velocity, now - p.flown, p.lifetime)
				end
			end
		end
		if stop then
			-- A shot that runs out of time ends on the clients by itself.
			if p.sent and p.remaining > 0 then
				shotEvent:FireAllClients("End", p.id)
			end
			table.remove(projectiles, i)
		end
	end
end)
function A.update(npc, target, dt)
	local config = Catalog.fromModel(npc)
	if not config or config.legacy == "Mutant" or npc:GetAttribute("IsBoss") then
		return false
	end
	local ok, h, root = alive(npc)
	local s = states[npc]
	if not ok then
		states[npc] = nil
		return false
	end
	if not s then
		s = { nextAttack = 0 }
		states[npc] = s
	end
	local now = workspace:GetServerTimeNow()
	if s.start then
		local age = now - s.start
		h.AutoRotate = false
		local lunging = config.behavior == "Lunge"
			and age >= config.attackImpact
			and age <= config.attackImpact + config.lungeDuration
		local planted = config.behavior == "Ranged" and age < config.attackImpact + RANGED_PLANT_AFTER
		if lunging or planted then
			-- The dash owns movement, in the direction it had at the strike; a shooter stands still.
			h:Move(Vector3.zero)
			h:MoveTo(root.Position)
		end
		if lunging then
			root.AssemblyLinearVelocity = Vector3.new(0, root.AssemblyLinearVelocity.Y, 0)
		end
		if not lunging then
			track(root, target, s, dt)
		end
		if lunging and not s.lungeLimit then
			local full = config.lungeSpeed * config.lungeDuration
			local ahead = target
					and target.Parent
					and Vector3.new(target.Position.X - root.Position.X, 0, target.Position.Z - root.Position.Z):Dot(
						s.direction
					)
				or full
			s.lungeLimit, s.dashed = math.clamp(ahead + LUNGE_FOLLOW, 0, full), 0
		end
		if age >= config.attackImpact and not s.hit then
			s.hit = true
			if config.behavior == "Ranged" then
				projectile(npc, root, config, s, target)
			elseif config.behavior ~= "Lunge" then
				melee(npc, root, config, s)
			end
			tally(npc).lastImpact = now
		elseif
			s.hit
			and config.behavior ~= "Ranged"
			and config.behavior ~= "Lunge"
			and age <= config.attackImpact + HIT_WINDOW
		then
			melee(npc, root, config, s) -- still swinging through: catch a player who steps into it
		end
		if lunging then
			-- Stops once it connects or reaches the end of its run.
			if s.dashed < s.lungeLimit and not next(s.hitPlayers) then
				local step = math.min(config.lungeSpeed * math.min(dt or 1 / 60, 0.05), s.lungeLimit - s.dashed)
				local move = s.direction * step
				local wall = workspace:Raycast(root.Position, move + s.direction * config.radius, s.params)
				if not wall then
					root.CFrame += move
					s.dashed += step
				end
			end
			melee(npc, root, config, s)
		end
		if age >= config.attackRecovery then
			s.start = nil
			release(npc, h)
			npc:SetAttribute("Attacking", false)
			return false
		end
		-- true while a lunge dash moves the body or a shooter stands; otherwise the chase steers.
		return lunging or planted
	end
	if now < s.nextAttack or not target or not target.Parent then
		return false
	end
	local player = Players:GetPlayerFromCharacter(target.Parent)
	local valid = player and validPlayer(player)
	if not valid then
		return false
	end
	local delta = target.Position - root.Position
	local flat = Vector3.new(delta.X, 0, delta.Z)
	local trigger = config.attackRange
		+ ((config.behavior == "Ranged" or config.behavior == "Lunge") and 0 or TRIGGER_BONUS)
	if flat.Magnitude > trigger or math.abs(delta.Y) > config.maxHeight or flat.Magnitude < 0.01 then
		return false
	end
	s.params = params(npc)
	if workspace:Raycast(root.Position, delta, s.params) then
		return false
	end
	s.direction = flat.Unit
	s.aim = target.Position
	s.start = now
	s.hit = false
	s.hitPlayers = {}
	s.nextAttack = now + config.attackCooldown
	s.lungeLimit = nil
	s.faced = nil -- release() let the Humanoid turn it, so the first facing always writes
	-- Square to the target: the bow skeleton's shot now leaves straight ahead (its chest turns
	-- in the clip), so nobody faces off to one side any more.
	h.AutoRotate = false
	face(root, s)
	-- The client poses the swing from EnemyAttackStart; the serial is for QA only (A.tally).
	npc:SetAttribute("EnemyAttackStart", now)
	tally(npc).serial += 1
	npc:SetAttribute("Attacking", true)
	-- Melee swings on the move and the chase keeps steering it; a shooter plants (see above).
	if config.behavior == "Ranged" then
		h:Move(Vector3.zero)
		h:MoveTo(root.Position)
		return true
	end
	return false
end
-- An attack in progress, wind-up to recovery. The chase loop updates those every frame, so their
-- timing is exact, and looks for a new attack only on its 0.1 s tick.
function A.busy(npc)
	local s = states[npc]
	return s ~= nil and s.start ~= nil
end
-- Drop an attack in progress without its hit (admin Freeze), so it can't land the moment the
-- enemy updates again. The cooldown stays; the next attack starts a fresh wind-up.
function A.cancel(npc)
	local s = states[npc]
	if not s or not s.start then
		return
	end
	s.start = nil
	release(npc, npc:FindFirstChildOfClass("Humanoid"))
	npc:SetAttribute("Attacking", false)
	npc:SetAttribute("EnemyAttackStart", nil) -- the client stops the swing pose too
end
return A
