-- Studio-only isolated integration harness. Explicitly require/start during Play.
-- Never inserted as an auto-running production script; cleanup restores state.
local Run = game:GetService("RunService")
local Players = game:GetService("Players")
local Tags = game:GetService("CollectionService")
local combat = game.ReplicatedStorage.RogueliteCombat
local Catalog = require(combat.EnemyCatalog)
local Attacks = require(game.ServerScriptService.EnemyAttacks)
local Slam = require(game.ServerScriptService.ZombieAttacks)
local Q = {}
-- Hits, last impact and attack serial per enemy: server tables now (EnemyAttacks.tally,
-- ZombieAttacks.tally), no longer attributes.
local function tally(npc)
	return Attacks.tally[npc] or Slam.tally[npc] or { hits = 0, serial = 0 }
end
function Q.inspect(id, mode)
	local s = assert(Q.state, "Start QA first")
	local phase = s.stage:GetAttribute("Phase")
	assert(phase == "Complete" or phase:sub(1, 6) == "Visual", "Preserve the telemetry run before visual repeats")
	local npc = assert(s.npcs[id], "Unknown regular enemy")
	assert(mode == "Idle" or mode == "Move" or mode == "Attack", "Expected Idle, Move or Attack")
	if s.active then
		local deadline = os.clock() + 3
		repeat
			task.wait(0.03)
		until not s.active:GetAttribute("Attacking") or os.clock() > deadline
	end
	s.active = nil
	s.repeatingAttack = false
	s.inspectMove = nil
	for _, n in s.npcs do
		n.Humanoid:Move(Vector3.zero)
		n.Humanoid:MoveTo(n.HumanoidRootPart.Position)
	end
	local d = Catalog.fromModel(npc)
	local root = npc.HumanoidRootPart
	if mode == "Move" then
		s.inspectMove = { npc = npc, center = root.Position, direction = 1 }
		npc.Humanoid:MoveTo(root.Position - Vector3.zAxis * 10)
	elseif mode == "Attack" then
		local player = Players:GetPlayers()[1]
		player.Character:PivotTo(CFrame.new(root.Position.X, 2.1, root.Position.Z - d.attackRange * 0.65))
		s.active = npc
		s.repeatingAttack = true
	end
	s.stage:SetAttribute("Phase", "Visual" .. mode)
	s.stage:SetAttribute("ActiveEnemy", id)
	return { id = id, mode = mode, path = npc:GetFullName() }
end
function Q.cleanup()
	if not Q.state then
		return
	end
	local s = Q.state
	Q.state = nil
	if s.control then
		s.control:Destroy()
	end
	if s.connection then
		s.connection:Disconnect()
	end
	for _, npc in s.npcs do
		Tags:RemoveTag(npc, "RogueliteZombie")
	end
	s.stage:Destroy()
	for p, old in s.players do
		if p.Character and p.Character:FindFirstChild("HumanoidRootPart") then
			local root = p.Character.HumanoidRootPart
			root.Anchored = old.anchored
			p.Character:PivotTo(old.pivot)
			local h = p.Character:FindFirstChildOfClass("Humanoid")
			h.MaxHealth = old.maxHealth
			h.Health = math.min(old.health, h.MaxHealth)
		end
		if old.weaponFolder.Parent then
			old.weaponFolder:SetAttribute("WeaponEnabled", old.weaponEnabled)
		end
	end
	combat:SetAttribute("ZombiesEnabled", false)
	combat:SetAttribute("EnemyRoster", s.old.roster)
	combat:SetAttribute("ZombieCount", s.old.count)
	combat:SetAttribute("ZombiesEnabled", s.old.enabled)
end
function Q.start()
	assert(Run:IsStudio(), "QA is Studio-only")
	assert(not Q.state, "QA already running")
	local player = assert(Players:GetPlayers()[1], "One real Studio client is required")
	assert(
		require(game.ServerScriptService.CharacterService).states[player],
		"Start QA from a real server Script, not the Studio tool require cache"
	)
	assert(player.Character and player.Character:FindFirstChild("HumanoidRootPart"), "Wait for character")
	local s = {
		old = {
			enabled = combat:GetAttribute("ZombiesEnabled"),
			count = combat:GetAttribute("ZombieCount"),
			roster = combat:GetAttribute("EnemyRoster"),
		},
		npcs = {},
		players = {},
		records = {},
	}
	Q.state = s
	local control = Instance.new("BindableFunction")
	control.Name = "RegularEnemyQAControl"
	control.Parent = game.ServerStorage
	s.control = control
	control.OnInvoke = function(action, id, mode)
		if action == "inspect" then
			return Q.inspect(id, mode)
		elseif action == "cleanup" then
			return Q.cleanup()
		elseif action == "status" then
			return s.stage:GetAttribute("Phase")
		end
		error("Unknown QA command")
	end
	combat:SetAttribute("ZombiesEnabled", false)
	combat:SetAttribute("ZombieCount", 0)
	combat:SetAttribute("EnemyRoster", nil)
	local stage = Instance.new("Folder")
	stage.Name = "RegularEnemyQA"
	stage:SetAttribute("Phase", "Settling")
	stage.Parent = workspace
	s.stage = stage
	local floor = Instance.new("Part")
	floor.Name = "TestFloor"
	floor.Anchored = true
	floor.Size = Vector3.new(240, 2, 240)
	floor.Position = Vector3.new(2000, -2, 0)
	floor.Color = Color3.fromRGB(71, 83, 91)
	floor.Material = Enum.Material.Slate
	floor.Parent = stage
	for _, p in Players:GetPlayers() do
		local char = p.Character
		local root = char and char:FindFirstChild("HumanoidRootPart")
		local h = char and char:FindFirstChildOfClass("Humanoid")
		local f = combat.PlayerStates:FindFirstChild(tostring(p.UserId))
		if root and h and f then
			s.players[p] = {
				pivot = char:GetPivot(),
				anchored = root.Anchored,
				maxHealth = h.MaxHealth,
				health = h.Health,
				weaponFolder = f,
				weaponEnabled = f:GetAttribute("WeaponEnabled"),
			}
			f:SetAttribute("WeaponEnabled", false)
			h.MaxHealth = 10000
			h.Health = 10000
			root.Anchored = true
			char:PivotTo(CFrame.new(2000, 3, 95))
		end
	end
	for i, d in Catalog.List do
		local template = assert(game.ServerStorage.RogueliteNPCs:FindFirstChild(d.template), "Missing " .. d.id)
		local npc = template:Clone()
		npc.Name = d.id
		npc:SetAttribute("EnemyId", d.id)
		npc:SetAttribute("ZombieType", d.legacy or d.id)
		npc:SetAttribute("RegularEnemyQA", true)
		npc:SetAttribute("ContactDamage", 0)
		npc:SetAttribute("AttackDamage", d.damage)
		npc:SetAttribute("SlamDamage", d.damage)
		npc:SetAttribute("SpawnIndex", i)
		npc:SetAttribute("Chasing", false)
		local root = npc.HumanoidRootPart
		local h = npc:FindFirstChildOfClass("Humanoid")
		h.MaxHealth = d.health
		h.Health = d.health
		h.WalkSpeed = d.speed
		h.BreakJointsOnDeath = false
		local position = Vector3.new(
			2000 + ((i - 1) % 7 - 3) * 28,
			h.HipHeight + root.Size.Y * 0.5 - 1 + 0.05,
			math.floor((i - 1) / 7) * 32 - 32
		)
		npc.Parent = stage
		npc:PivotTo(CFrame.new(position))
		for _, part in npc:GetDescendants() do
			if part:IsA("BasePart") then
				part.Anchored = false
				part.CollisionGroup = "RogueliteZombies"
			end
		end
		root:SetNetworkOwner(nil)
		Tags:AddTag(npc, "RogueliteZombie")
		s.npcs[d.id] = npc
		s.records[d.id] = {
			id = d.id,
			health = h.MaxHealth,
			speed = h.WalkSpeed,
			travel = 0,
			groundedSamples = 0,
			moveSamples = 0,
			impacts = 0,
		}
	end
	combat:SetAttribute("ZombiesEnabled", true)
	local previous = {}
	s.connection = Run.Heartbeat:Connect(function(dt)
		if s.inspectMove then
			local move = s.inspectMove
			local root = move.npc.HumanoidRootPart
			local target = move.center - Vector3.zAxis * (move.direction * 10)
			if
				(Vector3.new(root.Position.X, 0, root.Position.Z) - Vector3.new(target.X, 0, target.Z)).Magnitude < 1
			then
				move.direction *= -1
				target = move.center - Vector3.zAxis * (move.direction * 10)
			end
			move.npc.Humanoid:MoveTo(target)
		end
		for id, npc in s.npcs do
			if npc.Parent then
				local root = npc.HumanoidRootPart
				local h = npc.Humanoid
				local record = s.records[id]
				if previous[id] and stage:GetAttribute("Phase") == "Moving" then
					record.travel += Vector2.new(root.Position.X - previous[id].X, root.Position.Z - previous[id].Z).Magnitude
					record.moveSamples += 1
				end
				previous[id] = root.Position
				if h.FloorMaterial ~= Enum.Material.Air then
					record.groundedSamples += 1
				end
				local impact = tally(npc).lastImpact
				if impact and impact ~= record.lastImpact then
					record.lastImpact = impact
					record.impacts += 1
				end
			end
		end
		if s.active and s.active.Parent then
			local npc = s.active
			local d = Catalog.fromModel(npc)
			local start = npc:GetAttribute(d.legacy == "Mutant" and "SlamStart" or "EnemyAttackStart")
			if s.repeatingAttack or not start or npc:GetAttribute("Attacking") then
				if d.legacy == "Mutant" then
					Slam.update(npc, player.Character.HumanoidRootPart)
				else
					Attacks.update(npc, player.Character.HumanoidRootPart, dt)
				end
			end
		end
	end)
	task.spawn(function()
		task.wait(1.5)
		if Q.state ~= s then
			return
		end
		stage:SetAttribute("Phase", "Moving")
		for _, npc in s.npcs do
			npc:SetAttribute("Chasing", true)
			npc.Humanoid:MoveTo(npc.HumanoidRootPart.Position - Vector3.zAxis * 20)
		end
		task.wait(4)
		if Q.state ~= s then
			return
		end
		stage:SetAttribute("Phase", "IdleAfterMove")
		for _, npc in s.npcs do
			npc:SetAttribute("Chasing", false)
			npc.Humanoid:Move(Vector3.zero)
			npc.Humanoid:MoveTo(npc.HumanoidRootPart.Position)
		end
		task.wait(1.5)
		for _, d in Catalog.List do
			if Q.state ~= s then
				return
			end
			local npc = s.npcs[d.id]
			local root = npc.HumanoidRootPart
			local ph = player.Character.Humanoid
			local distance = d.attackRange * 0.65
			player.Character:PivotTo(CFrame.new(root.Position.X, 2.1, root.Position.Z - distance))
			s.active = npc
			stage:SetAttribute("ActiveEnemy", d.id)
			stage:SetAttribute("Phase", "Attacking")
			local beforeHealth = ph.Health
			local deadline = os.clock() + 3
			repeat
				task.wait(0.03)
			until tally(npc).serial > 0 or os.clock() > deadline
			local record = s.records[d.id]
			record.attackStarted = tally(npc).serial > 0
			task.wait(d.attackRecovery + (d.projectile and distance / d.projectileSpeed or 0) + 0.2)
			s.active = nil
			record.attackRecovered = npc:GetAttribute("Attacking") == false
			record.playerDamage = beforeHealth - ph.Health
			record.hits = tally(npc).hits
			npc.Humanoid:Move(Vector3.zero)
			npc.Humanoid:MoveTo(root.Position)
			stage:SetAttribute("Phase", "IdleAfterAttack")
			task.wait(0.15)
		end
		stage:SetAttribute("Phase", "Complete")
		stage:SetAttribute("ActiveEnemy", nil)
		local output = Instance.new("StringValue")
		output.Name = "ServerResults"
		output.Value = game:GetService("HttpService"):JSONEncode(s.records)
		output.Parent = stage
	end)
	return { types = #Catalog.List, stage = stage:GetFullName() }
end
return Q
