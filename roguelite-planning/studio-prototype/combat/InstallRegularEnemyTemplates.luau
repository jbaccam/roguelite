-- Edit-time assembly of native UI imports; run after retargeted clips are installed.
-- The accepted raw model is never edited. Native rig geometry and every boss are preserved.
-- Optional: set `local ONLY={werewolf=true}` above this text to rebuild just those templates.
local ONLY = ONLY
local storage = game:GetService("ServerStorage")
local raw = assert(storage:FindFirstChild("RegularEnemyRawImports"), "Import accepted FBX meshes first")
local folder = assert(storage:FindFirstChild("RogueliteNPCs"), "Missing existing NPC folder")
local combat = game.ReplicatedStorage.RogueliteCombat
-- Studio caches require results after Source edits; use a fresh dependency set.
local freshCatalog = Instance.new("Folder")
freshCatalog.Name = "RegularEnemyCatalogValidation"
freshCatalog.Parent = storage
for _, name in { "EnemyCatalog", "EnemyMotionTuning", "ZombieTypes" } do
	combat[name]:Clone().Parent = freshCatalog
end
local catalog = require(freshCatalog.EnemyCatalog)
freshCatalog:Destroy()
local animationFolder = assert(combat:FindFirstChild("EnemyAnimations"), "Install retargeted animation modules first")
local receipts = {}
for _, config in catalog.List do
	if ONLY and not ONLY[config.id] then
		continue
	end
	if config.legacy then
		local native = assert(folder:FindFirstChild(config.template), "Missing preferred native rig")
		local h = assert(native:FindFirstChildOfClass("Humanoid"), "Missing native humanoid")
		h.MaxHealth = config.health
		h.Health = config.health
		h.WalkSpeed = config.speed
		native:SetAttribute("EnemyId", config.id)
		native:SetAttribute("ZombieType", config.legacy)
		native:SetAttribute("BaseMoveSpeed", config.speed)
		native:SetAttribute("BaseMaxHealth", config.health)
		native:SetAttribute("HealthPerWave", config.healthPerWave)
		native:SetAttribute("StatDefaultWave", 1)
		native:SetAttribute("EnemyBalanceStatus", config.balanceStatus)
		native:SetAttribute("ContactDamage", 0)
		native:SetAttribute("AttackDamage", config.damage)
		native:SetAttribute("ContactRange", config.attackRange)
		table.insert(receipts, {
			id = config.id,
			template = native.Name,
			health = h.MaxHealth,
			speed = h.WalkSpeed,
			nativeRigPreserved = true,
		})
		continue
	end
	local source = raw:FindFirstChild(config.id)
	local animation = animationFolder:FindFirstChild(config.id)
	if not source or not animation then
		continue
	end
	local fresh = animation:Clone()
	fresh.Parent = animationFolder
	local data = require(fresh)
	fresh:Destroy()
	assert(
		data.coordinateSpace == "Actual Roblox FBX import bone-local Transform; derived from receipt"
			or data.coordinateSpace == "Actual Roblox FBX import joint-local Transform; derived from receipt",
		"Unverified import axes: " .. config.id
	)
	local existing = folder:FindFirstChild(config.template)
	if existing and not existing:GetAttribute("RegularEnemyAssemblerOwned") then
		error("Refusing to replace an unowned template: " .. config.template)
	end
	-- Built in a fresh Model at scale 1, not in the clone itself: the raw import is ScaleTo(0.01),
	-- and a Humanoid scales its walking force by its model's scale, so at 0.01 the mob barely
	-- accelerated and slid as if on ice (EnemyTemplateTests). Part sizes don't change.
	local npc = Instance.new("Model")
	for _, child in source:Clone():GetChildren() do
		child.Parent = npc
	end
	npc.WorldPivot = source:GetPivot() -- the root below is placed and faced by it
	for key, value in source:GetAttributes() do
		if not key:match("^RBX") then
			npc:SetAttribute(key, value)
		end
	end
	npc.Name = config.template
	local bounds, size = npc:GetBoundingBox()
	local baseY = bounds.Position.Y - size.Y * 0.5
	local centerY = baseY + math.max(0.9, size.Y * 0.45)
	local root = Instance.new("Part")
	root.Name = "HumanoidRootPart"
	root.Transparency = 1
	root.Size = Vector3.new(
		math.clamp(size.X * 0.42, 1, 4),
		math.clamp(size.Y * 0.3, 0.65, 2),
		math.clamp(size.Z * 0.65, 0.8, 3)
	)
	root.CFrame = CFrame.new(npc:GetPivot().Position.X, centerY, npc:GetPivot().Position.Z) * npc:GetPivot().Rotation
	root.RootPriority = 127
	root.CanCollide = true
	root.CanTouch = false
	root.CanQuery = true
	root.Parent = npc
	local attached = {}
	for _, joint in npc:GetDescendants() do
		if joint:IsA("Motor6D") and joint.Part0 and joint.Part1 then
			attached[joint.Part1] = true
		end
	end
	for _, part in npc:GetDescendants() do
		if part:IsA("BasePart") and part ~= root then
			part.Anchored = false
			part.CanCollide = false
			part.CanTouch = false
			part.CanQuery = true
			part.Massless = true
			if not attached[part] then
				local weld = Instance.new("WeldConstraint")
				weld.Name = "EnemyRootWeld"
				weld.Part0 = root
				weld.Part1 = part
				weld.Parent = root
			end
		end
	end
	for _, v in npc:GetChildren() do
		if v:IsA("AnimationController") then
			v:Destroy()
		end
	end
	local humanoid = Instance.new("Humanoid")
	humanoid.Name = "Humanoid"
	humanoid.RigType = Enum.HumanoidRigType.R15
	humanoid.RequiresNeck = false
	humanoid.BreakJointsOnDeath = false
	humanoid.HipHeight = math.max(0.05, centerY - baseY - root.Size.Y * 0.5)
	humanoid.MaxHealth = config.health
	humanoid.Health = config.health
	humanoid.WalkSpeed = config.speed
	humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	humanoid.Parent = npc
	local animator = Instance.new("Animator")
	animator.Parent = humanoid
	npc.PrimaryPart = root
	npc:SetAttribute("EnemyId", config.id)
	npc:SetAttribute("ZombieType", config.id)
	npc:SetAttribute("RegularEnemyAssemblerOwned", true)
	npc:SetAttribute("EnemyMotionVersion", 1)
	-- Clients scale the clips by GetScale() / this: the clips were measured at the raw import's scale.
	npc:SetAttribute("EnemyBaselineModelScale", (data.baselineModelScale or source:GetScale()) / source:GetScale())
	npc:SetAttribute("EnemyImportReceiptHash", data.importReceiptHash)
	npc:SetAttribute("SourceAsset", assert(data.sourceImportAsset, "Missing mesh import provenance"))
	npc:SetAttribute("AnimationSourceAsset", data.sourceAnimationAsset)
	npc:SetAttribute("EnemyBalanceStatus", config.balanceStatus)
	npc:SetAttribute("BaseMoveSpeed", humanoid.WalkSpeed)
	npc:SetAttribute("BaseMaxHealth", config.health)
	npc:SetAttribute("HealthPerWave", config.healthPerWave)
	npc:SetAttribute("StatDefaultWave", 1)
	npc:SetAttribute("ContactDamage", 0)
	npc:SetAttribute("AttackDamage", config.damage)
	npc:SetAttribute("ContactRange", config.attackRange)
	npc:SetAttribute("RebuildRevision", nil) -- raw-import bookkeeping from AdoptRegularEnemyImport
	root.Anchored = false
	if existing then
		existing:Destroy()
	end
	npc.Parent = folder
	local bones = 0
	for _, v in npc:GetDescendants() do
		if v:IsA("Bone") then
			bones += 1
		end
	end
	table.insert(
		receipts,
		{ id = config.id, template = npc.Name, bones = bones, scale = npc:GetScale(), hipHeight = humanoid.HipHeight }
	)
end
local projectileSources = storage:FindFirstChild("RegularEnemyProjectiles")
if projectileSources and not ONLY then
	local destination = combat:FindFirstChild("EnemyProjectileTemplates") or Instance.new("Folder")
	destination.Name = "EnemyProjectileTemplates"
	destination.Parent = combat
	for name, sourcePath in
		{
			Arrow = "mob-production/reference-rebuilds/bow-skeleton/ArrowProjectile.fbx",
			Rock = "mob-production/reference-rebuilds/rock-throwing-crab/RockProjectile.fbx",
		}
	do
		local source = projectileSources:FindFirstChild(name)
		if source then
			local existing = destination:FindFirstChild(name)
			assert(
				not existing or existing:GetAttribute("RegularEnemyAssemblerOwned"),
				"Unowned projectile template: " .. name
			)
			local copy = source:Clone()
			copy.Name = name
			copy:SetAttribute("RegularEnemyAssemblerOwned", true)
			copy:SetAttribute("SourceAsset", sourcePath)
			for _, v in copy:GetDescendants() do
				assert(not v:IsA("LuaSourceContainer"), "Projectile imports must contain reviewed geometry only")
				if v:IsA("BasePart") then
					v.Anchored = true
					v.CanCollide = false
					v.CanTouch = false
					v.CanQuery = false
				end
			end
			if existing then
				existing:Destroy()
			end
			copy.Parent = destination
		end
	end
end
return receipts
