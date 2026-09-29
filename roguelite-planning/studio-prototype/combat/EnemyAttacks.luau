-- Server-owned regular enemy attacks. No client-supplied hit/target claims.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local combat = game.ReplicatedStorage:WaitForChild("RogueliteCombat")
local Catalog = require(combat:WaitForChild("EnemyCatalog"))
local Motion = require(combat:WaitForChild("EnemyMotion"))
local Visuals = require(combat:WaitForChild("EnemyProjectileVisuals"))
local Characters = require(script.Parent:WaitForChild("CharacterService"))
local A = {}
local states = setmetatable({}, { __mode = "k" })
local projectiles = {}
local colors = {
	Spit = Color3.fromRGB(148, 200, 76),
	Rock = Color3.fromRGB(135, 116, 93),
	Arrow = Color3.fromRGB(224, 198, 138),
	Icicle = Color3.fromRGB(159, 241, 255),
	Fireball = Color3.fromRGB(255, 126, 59),
}
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
local function face(root, s)
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
	align.CFrame = CFrame.lookAt(Vector3.zero, s.direction) * CFrame.Angles(0, s.yaw or 0, 0)
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
	local actual = Characters.contact(player, amount)
	npc:SetAttribute("EnemyHits", (npc:GetAttribute("EnemyHits") or 0) + 1)
	npc:SetAttribute("LastEnemyDamage", actual)
end
local function melee(npc, root, config, s)
	for _, player in Players:GetPlayers() do
		local ok, pr = validPlayer(player)
		if ok and not s.hitPlayers[player] then
			local delta = pr.Position - root.Position
			local flat = Vector3.new(delta.X, 0, delta.Z)
			if
				math.abs(delta.Y) <= config.maxHeight
				and flat.Magnitude <= (config.hitRange or config.attackRange)
				and (flat.Magnitude < 0.1 or flat.Unit:Dot(s.direction) > 0.15)
				and not workspace:Raycast(root.Position, delta, s.params)
			then
				s.hitPlayers[player] = true
				damage(npc, player, npc:GetAttribute("AttackDamage") or config.damage)
			end
		end
	end
end
local function projectile(npc, root, config, s)
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
	local direction = s.aim - start
	if direction.Magnitude < 0.01 then
		return
	end
	local templates = combat:FindFirstChild("EnemyProjectileTemplates")
	local template = templates and templates:FindFirstChild(config.projectile)
	local part = template and template:Clone() or Visuals.build(config.projectile)
		or Instance.new(config.projectile == "Icicle" and "WedgePart" or "Part")
	if not template and not Visuals.has(config.projectile) then
		if part:IsA("Part") then
			part.Shape = Enum.PartType.Ball
		end
		part.Size = config.projectile == "Icicle" and Vector3.new(0.35, 0.35, 1.5)
			or Vector3.one * (config.projectile == "Arrow" and 0.42 or 0.8)
		part.Material = config.projectile == "Rock" and Enum.Material.Slate or Enum.Material.Neon
		part.Color = colors[config.projectile]
	end
	local function configure(p)
		if p:IsA("BasePart") then
			p.Anchored = true
			p.CanCollide = false
			p.CanTouch = false
			p.CanQuery = false
			p.CastShadow = false
		end
	end
	configure(part)
	for _, p in part:GetDescendants() do
		configure(p)
	end
	part.Name = "Enemy" .. config.projectile
	part:PivotTo(CFrame.lookAt(start, start + direction))
	part:SetAttribute("ServerEnemyProjectile", true)
	part.Parent = workspace
	table.insert(projectiles, {
		part = part,
		source = npc,
		position = start,
		velocity = direction.Unit * config.projectileSpeed,
		remaining = config.attackRange / config.projectileSpeed + 1,
		damage = npc:GetAttribute("AttackDamage") or config.damage,
		params = s.params,
	})
end
RunService.Heartbeat:Connect(function(dt)
	for i = #projectiles, 1, -1 do
		local p = projectiles[i]
		p.remaining -= dt
		local stop = not p.part.Parent or p.remaining <= 0 or combat:GetAttribute("ZombiesEnabled") ~= true
		if not stop then
			local finish = p.position + p.velocity * dt
			local wall = workspace:Raycast(p.position, finish - p.position, p.params)
			local wallT = wall and (wall.Position - p.position).Magnitude / (finish - p.position).Magnitude or math.huge
			local closest, closestT = nil, wallT
			for _, player in Players:GetPlayers() do
				local ok, pr = validPlayer(player)
				if ok then
					for _, height in { -1.3, 0, 1.3 } do
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
				p.part:PivotTo(CFrame.lookAt(finish, finish + p.velocity))
			end
		end
		if stop then
			p.part:Destroy()
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
		if lunging then
			-- The dash owns movement, in the direction it had at the strike.
			h:Move(Vector3.zero)
			h:MoveTo(root.Position)
			root.AssemblyLinearVelocity = Vector3.new(0, root.AssemblyLinearVelocity.Y, 0)
		else
			track(root, target, s, dt)
		end
		if age >= config.attackImpact and not s.hit then
			s.hit = true
			if config.behavior == "Ranged" then
				-- Released at where the target is now; the shot still travels, so it can be dodged.
				if target and target.Parent then
					s.aim = target.Position
				end
				projectile(npc, root, config, s)
			elseif config.behavior ~= "Lunge" then
				melee(npc, root, config, s)
			end
			npc:SetAttribute("LastEnemyImpact", now)
		end
		if lunging then
			local move = s.direction * config.lungeSpeed * math.min(dt or 1 / 60, 0.05)
			local wall = workspace:Raycast(root.Position, move + s.direction * config.radius, s.params)
			if not wall then
				root.CFrame += move
			end
			melee(npc, root, config, s)
		end
		if age >= config.attackRecovery then
			s.start = nil
			release(npc, h)
			npc:SetAttribute("Attacking", false)
			return false
		end
		-- true only while a lunge dash moves the body; otherwise the chase keeps steering.
		return lunging
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
	if flat.Magnitude > config.attackRange or math.abs(delta.Y) > config.maxHeight or flat.Magnitude < 0.01 then
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
	s.yaw = config.attackFacingYaw or 0
	if config.projectile == "Arrow" then
		local data = Motion.load(config.id)
		if data and data.projectile then
			s.yaw = data.projectile.attackFacingYaw or s.yaw
		end
	end
	h.AutoRotate = false
	face(root, s)
	npc:SetAttribute("EnemyAttackStart", now)
	npc:SetAttribute("EnemyAttackSerial", (npc:GetAttribute("EnemyAttackSerial") or 0) + 1)
	npc:SetAttribute("EnemyAttackDirection", s.direction)
	npc:SetAttribute("Attacking", true)
	-- No stop: the enemy swings on the move and the chase keeps steering it.
	return false
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
