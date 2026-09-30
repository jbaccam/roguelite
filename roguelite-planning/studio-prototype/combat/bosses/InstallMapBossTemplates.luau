-- Edit-time assembly of the four map-boss templates (plan F Task 4). Paste into execute_luau
-- (Edit) after MapBossTiming and MapBossDefs are synced. The raw imports in
-- ServerStorage.MapBossRawImports are never edited. An older <Id>_NPC is moved to
-- ServerStorage.BeforeMapBoss_<yyyymmdd> before its replacement is parented.
assert(not game:GetService("RunService"):IsRunning(), "Run the installer in Edit mode")
local storage = game:GetService("ServerStorage")
local combat = game.ReplicatedStorage.RogueliteCombat
local raw = assert(storage:FindFirstChild("MapBossRawImports"), "Import the boss FBX files first")
local folder = assert(storage:FindFirstChild("RogueliteNPCs"), "Missing RogueliteNPCs")
-- Studio caches module results in Edit: require a fresh copy.
local function fresh(m)
	local c = m:Clone()
	c.Parent = m.Parent
	local ok, r = pcall(require, c)
	c:Destroy()
	assert(ok, r)
	return r
end
local Defs = fresh(assert(combat:FindFirstChild("MapBossDefs"), "Sync MapBossDefs and MapBossTiming first"))
local SOURCE = {
	KingCrab = "king-crab-boss/exports/game/KingCrab_Studio.fbx",
	FrostCyclops = "frost-cyclops-boss/exports/game/FrostCyclops_Studio.fbx",
	Pharaoh = "pharaoh-boss/exports/game/Pharaoh_Studio.fbx",
	Dragon = "dragon-boss/exports/game/Dragon_Studio.fbx",
}
local backup
local function backupFolder()
	if not backup then
		local name = "BeforeMapBoss_" .. os.date("%Y%m%d")
		backup = storage:FindFirstChild(name) or Instance.new("Folder")
		backup.Name = name
		backup.Parent = storage
	end
	return backup
end
-- Imported SurfaceAppearances render blank in Play when their images came through the MCP
-- uploader; MeshPart.TextureID is safe. Move any ColorMap into TextureID and drop the surface.
local function flattenSurface(p)
	for _, sa in p:GetChildren() do
		if sa:IsA("SurfaceAppearance") then
			if p.TextureID == "" and sa.ColorMap ~= "" then
				p.TextureID = sa.ColorMap
			end
			sa:Destroy()
		end
	end
end
local function lowestY(model)
	local low = math.huge
	for _, p in model:GetDescendants() do
		if p:IsA("MeshPart") then
			local cf, s = p.CFrame, p.Size * 0.5
			for _, x in { -1, 1 } do
				for _, y in { -1, 1 } do
					for _, z in { -1, 1 } do
						low = math.min(low, (cf * Vector3.new(x * s.X, y * s.Y, z * s.Z)).Y)
					end
				end
			end
		end
	end
	return low
end
-- Studio caps every mesh at 2048 units per axis. The dragon's Obsidian section is 30.05 studs long,
-- 3004.59 units at the 100x import, so the importer shrank all seven dragon sections by
-- 2048 / 3004.59 about the first section's centre (Dragon_Belly) but left the skeleton at full
-- size. Every bone then turned its section about the wrong pivot, which opened gaps at the neck,
-- horns, spikes, claws and wings. Sizes and centres are restored about the same anchor, in the
-- importer RootPart's space; the skeleton is already right. Measured against Dragon.glb (the
-- restore factor is 1.467085 on every axis of every section).
local IMPORT_RESTORE = { Dragon = { factor = 3004.590 / 2048, anchor = "Dragon_Belly" } }
local function restoreImportShrink(npc, id, rig)
	local fix = IMPORT_RESTORE[id]
	if not fix or npc:GetAttribute("ImportShrinkRestored") then
		return 0
	end
	local anchor = assert(npc:FindFirstChild(fix.anchor, true), "Missing " .. fix.anchor)
	local centre = rig.CFrame:PointToObjectSpace(anchor.Position)
	local n = 0
	for _, p in npc:GetDescendants() do
		if p:IsA("MeshPart") then
			local rel = rig.CFrame:ToObjectSpace(p.CFrame)
			p.Size *= fix.factor
			p.CFrame = rig.CFrame * (CFrame.new(centre + (rel.Position - centre) * fix.factor) * rel.Rotation)
			n += 1
		end
	end
	npc:SetAttribute("ImportShrinkRestored", fix.factor)
	return n
end
local report = {}
for _, id in Defs.Order do
	-- The template is built at authored size; MapBossService applies def.scale at spawn.
	local def, T = Defs.get(id), Defs.rawTiming(id)
	assert(def and T, "Missing defs or timing for " .. id)
	local source = assert(raw:FindFirstChild(id), "Missing raw import " .. id)
	local npc = source:Clone()
	npc.Name = id .. "_NPC"
	for _, v in npc:GetChildren() do
		if v:IsA("AnimationController") then
			v:Destroy()
		end
	end
	local rig = assert(npc:FindFirstChild("RootPart"), "Missing importer RootPart in " .. id)
	local restored = restoreImportShrink(npc, id, rig)
	if restored > 0 then
		table.insert(report, string.format("RESTORED %s %d sections x%.6f", id, restored, IMPORT_RESTORE[id].factor))
	end
	-- The ground frame is root.CFrame * CFrame.new(0, -rootHeight, 0) and sampled points sit
	-- groundOffset above the armature's z = 0, so the armature origin (the importer RootPart)
	-- rests groundOffset above the ground: HRP centre = RootPart + rootHeight - groundOffset.
	-- For the Frost Cyclops that is exactly rootHeight above its soles (the lowest mesh point).
	local groundOffset = T.groundOffset or 0
	local centre = rig.Position + Vector3.yAxis * (T.rootHeight - groundOffset)
	local footprint = math.min(8, T.footprintRadius or 4)
	local root = Instance.new("Part")
	root.Name = "HumanoidRootPart"
	root.Transparency = 1
	-- Half the root height tall, so the Humanoid keeps a real HipHeight (rootHeight / 2) instead
	-- of dragging a floor-touching box; HipHeight + Size.Y / 2 is still rootHeight.
	root.Size = Vector3.new(footprint, T.rootHeight, footprint)
	root.CFrame = CFrame.new(centre) * rig.CFrame.Rotation
	root.RootPriority = 127
	root.CanCollide = true
	root.CanTouch = false
	root.CanQuery = true
	root.Massless = false
	root.Anchored = false
	root.Parent = npc
	local attached = {}
	for _, joint in npc:GetDescendants() do
		if joint:IsA("Motor6D") and joint.Part0 and joint.Part1 then
			attached[joint.Part1] = true
		end
	end
	local sections = 0
	for _, part in npc:GetDescendants() do
		if part:IsA("BasePart") and part ~= root then
			part.Anchored = false
			part.CanCollide = false
			part.CanTouch = false
			part.CanQuery = part:IsA("MeshPart")
			part.Massless = true
			if not attached[part] then
				local weld = Instance.new("WeldConstraint")
				weld.Name = "EnemyRootWeld"
				weld.Part0 = root
				weld.Part1 = part
				weld.Parent = root
			end
			if part:IsA("MeshPart") then
				sections += 1
				flattenSurface(part)
				part.RenderFidelity = Enum.RenderFidelity.Precise
				if part.Name:match("EyeGlow$") or part.Name:match("LavaGlow$") then
					part.Material = Enum.Material.Neon
					part.TextureID = ""
					part.Color = def.glowColor or Color3.fromRGB(255, 200, 120)
				end
				assert(part.Material == Enum.Material.Neon or part.TextureID:match("^rbxassetid://"), "Untextured section " .. part.Name)
			end
		end
	end
	local humanoid = Instance.new("Humanoid")
	humanoid.Name = "Humanoid"
	humanoid.RigType = Enum.HumanoidRigType.R15
	humanoid.AutomaticScalingEnabled = false
	humanoid.RequiresNeck = false
	humanoid.BreakJointsOnDeath = false
	humanoid.HipHeight = math.max(0, T.rootHeight - root.Size.Y * 0.5)
	humanoid.MaxHealth = def.health
	humanoid.Health = def.health
	humanoid.WalkSpeed = def.chaseSpeed
	humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	humanoid.Parent = npc
	Instance.new("Animator").Parent = humanoid
	npc.PrimaryPart = root
	npc:SetAttribute("IsBoss", true)
	npc:SetAttribute("IsMapBoss", true)
	npc:SetAttribute("MapBossId", id)
	npc:SetAttribute("BossName", def.name)
	npc:SetAttribute("ZombieType", id)
	npc:SetAttribute("EnemyBaselineModelScale", npc:GetScale())
	npc:SetAttribute("MapBossRootHeight", T.rootHeight)
	npc:SetAttribute("MapBossGroundOffset", groundOffset)
	npc:SetAttribute("BossDeathSeconds", (T.clips.Death or 2.3) + 0.6)
	npc:SetAttribute("ContactDamage", 0)
	npc:SetAttribute("ContactRange", 0)
	npc:SetAttribute("BaseMoveSpeed", def.chaseSpeed)
	npc:SetAttribute("SourceAsset", SOURCE[id])
	npc:SetAttribute("MapBossAssemblerOwned", true)
	local existing = folder:FindFirstChild(npc.Name)
	if existing then
		existing.Parent = backupFolder()
	end
	npc.Parent = folder
	local bones = 0
	for _, v in npc:GetDescendants() do
		if v:IsA("Bone") then
			bones += 1
		end
	end
	table.insert(
		report,
		string.format(
			"INSTALLED %s bones=%d sections=%d hrpHeight=%.3f hipHeight=%.3f lowestMeshAboveGround=%.3f",
			id,
			bones,
			sections,
			root.Size.Y,
			humanoid.HipHeight,
			lowestY(npc) - (centre.Y - T.rootHeight)
		)
	)
end
-- VFX mesh templates: children of the BossVfxAssets ids module (plan F Task 10 fills its Source).
local kit = raw:FindFirstChild("VfxKit")
if kit then
	local assets = combat:FindFirstChild("BossVfxAssets")
	if not assets then
		assets = Instance.new("ModuleScript")
		assets.Name = "BossVfxAssets"
		assets.Source = "return {Textures={},Flipbook={},Sounds={}}\n"
		assets.Parent = combat
	end
	local n = 0
	for _, source in kit:GetDescendants() do
		if source:IsA("MeshPart") then
			local copy = source:Clone()
			for _, child in copy:GetChildren() do
				if not child:IsA("SurfaceAppearance") then
					child:Destroy()
				end
			end
			flattenSurface(copy)
			copy.Anchored = true
			copy.CanCollide = false
			copy.CanQuery = false
			copy.CanTouch = false
			copy.CastShadow = false
			copy:SetAttribute("SourceAsset", "boss-vfx-kit/exports/fbx/AllMeshes.fbx")
			local old = assets:FindFirstChild(copy.Name)
			if old then
				old:Destroy()
			end
			copy.Parent = assets
			n += 1
		end
	end
	table.insert(report, "VFX_MESHES " .. n)
end
return table.concat(report, "\n")
