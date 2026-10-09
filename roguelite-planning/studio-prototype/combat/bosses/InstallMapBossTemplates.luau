-- Edit-time assembly of the map-boss templates (plan F Task 4). Paste into execute_luau
-- (Edit) after MapBossTiming and MapBossDefs are synced. The raw imports in
-- ServerStorage.MapBossRawImports are never edited; each is named by its MapBossDefs id (the
-- SOURCE FBX imported, then renamed: Hammer, KingCrab, ...). An older <Id>_NPC is moved to
-- ServerStorage.BeforeMapBoss_<yyyymmdd_hhmmss> (one folder per run) before its replacement is parented.
-- ONLY (a global set before this code, e.g. ONLY={'Hammer'}) installs just those ids and fails on
-- a missing raw import or timing. Without it every Defs.Order id is installed, and one without a
-- raw import or timing yet is reported SKIPPED and left alone.
-- The Hammer (R9, 2026-10-04) has no raw import: Hammer_NPC is a copy of the original 16-part Motor6D
-- template RogueliteNPCs.HammerBoss_NPC (COPY), which stays for the legacy runtime. Its meshes,
-- textures and SurfaceAppearances are kept as they are (they render in game today); the old
-- runtime's attributes go, the map-boss ones come, and two Neon eye plates are welded to the head.
-- Until MapBossTiming has 'hammer-brute' it is SKIPPED (ONLY={'Hammer'} fails), so the gate
-- (MapBossDefs.ready) stays closed.
assert(not game:GetService("RunService"):IsRunning(), "Run the installer in Edit mode")
local storage = game:GetService("ServerStorage")
local combat = game.ReplicatedStorage.RogueliteCombat
local raw = storage:FindFirstChild("MapBossRawImports")
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
	-- The original model (R9): HammerBoss_NPC's meshes; his clips come from hammer-boss-moves.
	Hammer = "hammer-boss/finished/HammerBoss.blend",
	KingCrab = "king-crab-boss/exports/game/KingCrab_Studio.fbx",
	FrostCyclops = "frost-cyclops-boss/exports/game/FrostCyclops_Studio.fbx",
	Pharaoh = "pharaoh-boss/exports/game/Pharaoh_Studio.fbx",
	Dragon = "dragon-boss/exports/game/Dragon_Studio.fbx",
	-- Round 10 leaders (MapBossDefs.Leaders): installed only by name (ONLY={'DJCrab'} ...), never by
	-- a plain run, which walks Defs.Order.
	DJCrab = "dj-crab-boss/exports/game/DJCrab_Studio.fbx",
	TombWarden = "tomb-warden-boss/exports/game/TombWarden_Studio.fbx",
	BloodAlpha = "alpha-werewolf-boss/exports/game/AlphaWolf_Studio.fbx",
}
-- One new backup folder per run, named by the date and time (and _2, _3... after another run in the
-- same second), so a second run on one day never puts a second <Id>_NPC beside the first.
local backup
local function backupFolder()
	if not backup then
		local base = "BeforeMapBoss_" .. os.date("%Y%m%d_%H%M%S")
		local name, n = base, 1
		while storage:FindFirstChild(name) do
			n += 1
			name = base .. "_" .. n
		end
		backup = Instance.new("Folder")
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
-- Studio caps every mesh at 2048 units per axis (20.48 studs at the 100x import) and silently
-- shrinks an import that exceeds it while leaving the skeleton full size. The Studio FBX files
-- keep every section under that cap (the Dragon's big sections are split into pieces), so a
-- section over 20.48 studs here means a bad import: fail rather than install a torn model.
local function assertUnderMeshCap(npc, id)
	for _, p in npc:GetDescendants() do
		if p:IsA("MeshPart") then
			local s = p.Size
			assert(math.max(s.X, s.Y, s.Z) <= 20.48, id .. ": " .. p.Name .. " exceeds the 2048-unit mesh cap; re-export it split")
		end
	end
end
-- Ids installed as a copy of an existing Motor6D template instead of from a raw import (R9).
local COPY = { Hammer = "HammerBoss_NPC" }
-- The old runtime's attributes (BossService.spawn, BossMotion.prepare, effects), on any instance.
local LEGACY_ATTRIBUTES = { "IsHammerBoss", "BossRest", "BossVisualScale", "BossVfxBaseColor" }
-- The Hammer's eye plates over his painted eyes, Head-local at template scale 1. Measured on
-- hammer-boss/finished/HammerBoss.blend (the white faces of the Head texture): both eyes 0.47 either
-- side of the Head's centre and 0.41 above it, their front 1.01 ahead of it; each plate sits just in
-- front, a little inside the white. His right eye is round (a disc), his left narrowed (a slit).
-- Named *_EyeGlow, so BossVfx/Hammer (Common.glow) tints them red on enrage.
local EYES = {
	{ offset = Vector3.new(0.47, 0.409, -1.034), size = Vector3.new(0.03, 0.26, 0.26), shape = Enum.PartType.Cylinder, turn = CFrame.Angles(0, math.pi / 2, 0) },
	{ offset = Vector3.new(-0.47, 0.409, -1.034), size = Vector3.new(0.26, 0.1, 0.03), shape = Enum.PartType.Block, turn = CFrame.identity },
}
local function eyePlates(npc, def)
	local head = assert(npc:FindFirstChild("Head"), "Missing Head")
	local scale = npc:GetScale()
	for _, e in EYES do
		local plate = Instance.new("Part")
		plate.Name = "HammerBrute_EyeGlow"
		plate.Shape = e.shape
		plate.Size = e.size * scale
		plate.CFrame = head.CFrame * CFrame.new(e.offset * scale) * e.turn
		plate.Material = Enum.Material.Neon
		plate.Color = def.glowColor or Color3.new(1, 1, 1)
		plate.Anchored = false
		plate.CanCollide = false
		plate.CanTouch = false
		plate.CanQuery = false
		plate.CastShadow = false
		plate.Massless = true
		local weld = Instance.new("Weld")
		weld.Name = "EyeGlowWeld"
		weld.Part0 = head
		weld.Part1 = plate
		weld.C0 = head.CFrame:ToObjectSpace(plate.CFrame)
		weld.Parent = plate
		plate.Parent = npc
	end
	return #EYES
end
-- COPY: the template as it is (meshes, textures, SurfaceAppearances, Motor6Ds and Humanoid), without
-- the old runtime's attributes, plus the eye plates. Returns the model, its root, its Humanoid and
-- the report's text.
local function copied(id, def)
	local source = assert(folder:FindFirstChild(COPY[id]), "Missing RogueliteNPCs." .. COPY[id])
	local npc = source:Clone()
	npc.Name = id .. "_NPC"
	for _, inst in { npc, table.unpack(npc:GetDescendants()) } do
		for _, key in LEGACY_ATTRIBUTES do
			if inst:GetAttribute(key) ~= nil then
				inst:SetAttribute(key, nil)
			end
		end
	end
	local root = assert(npc.PrimaryPart or npc:FindFirstChild("HumanoidRootPart"), "Missing HumanoidRootPart in " .. COPY[id])
	local humanoid = assert(npc:FindFirstChildOfClass("Humanoid"), "Missing Humanoid in " .. COPY[id])
	assertUnderMeshCap(npc, id)
	local motors, sections = 0, 0
	for _, v in npc:GetDescendants() do
		if v:IsA("Motor6D") then
			motors += 1
		elseif v:IsA("MeshPart") then
			sections += 1
			local surface = v:FindFirstChildOfClass("SurfaceAppearance")
			assert(v.TextureID:match("^rbxassetid://") or (surface and surface.ColorMap ~= ""), "Untextured section " .. v.Name)
		end
	end
	local eyes = eyePlates(npc, def)
	if not humanoid:FindFirstChildOfClass("Animator") then
		Instance.new("Animator").Parent = humanoid
	end
	npc.PrimaryPart = root
	return npc, root, humanoid, string.format("copy of %s motors=%d sections=%d eyes=%d", COPY[id], motors, sections, eyes)
end
-- A raw import as a template (the other four). Returns the model, its new root and Humanoid, the
-- report's text and the ground height.
local function imported(id, def, T)
	assert(raw, "Import the boss FBX files first")
	local source = assert(raw:FindFirstChild(id), "Missing raw import " .. id)
	-- A fresh Model at scale 1, not the raw import's clone (ScaleTo 0.01): a Humanoid scales its
	-- walking force by its model's scale, so at 0.01 the boss slid as if on ice (EnemyTemplateTests).
	local npc = Instance.new("Model")
	for _, child in source:Clone():GetChildren() do
		child.Parent = npc
	end
	for key, value in source:GetAttributes() do
		if not key:match("^RBX") then
			npc:SetAttribute(key, value)
		end
	end
	npc.Name = id .. "_NPC"
	for _, v in npc:GetChildren() do
		if v:IsA("AnimationController") then
			v:Destroy()
		end
	end
	local rig = assert(npc:FindFirstChild("RootPart"), "Missing importer RootPart in " .. id)
	assertUnderMeshCap(npc, id)
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
				-- Glow sections may be split into pieces (Dragon_LavaGlow_Front / _Rear).
				-- (Round 10: the DJ Crab's LEDs and button are one DJCrab_Glow section.)
				if part.Name:match("_EyeGlow$") or part.Name:match("_EyeGlow_") or part.Name:match("_LavaGlow$") or part.Name:match("_LavaGlow_") or part.Name:match("_Glow$") then
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
	humanoid.Parent = npc
	Instance.new("Animator").Parent = humanoid
	npc.PrimaryPart = root
	local bones = 0
	for _, v in npc:GetDescendants() do
		if v:IsA("Bone") then
			bones += 1
		end
	end
	return npc, root, humanoid, string.format("bones=%d sections=%d", bones, sections), centre.Y - T.rootHeight
end
local report = {}
local only = ONLY
for _, id in only or Defs.Order do
	-- The template is built at authored size; MapBossService applies def.scale at spawn.
	local def, T = Defs.get(id), Defs.rawTiming(id)
	local available = if COPY[id] then folder:FindFirstChild(COPY[id]) else raw and raw:FindFirstChild(id)
	if not only and not (def and T and available) then
		table.insert(report, "SKIPPED " .. id .. ": " .. (not def and "no def" or not T and "no MapBossTiming entry" or COPY[id] and "no " .. COPY[id] or "no raw import"))
		continue
	end
	assert(def and T, "Missing defs or timing for " .. id)
	local npc, root, humanoid, extra, ground
	if COPY[id] then
		npc, root, humanoid, extra = copied(id, def)
		-- The timing's root height must be this template's (HumanoidRootPart centre above the soles):
		-- MapBossService sets HipHeight from it.
		ground = root.Position.Y - T.rootHeight
		assert(math.abs(lowestY(npc) - ground) < 0.05, string.format("%s: MapBossTiming rootHeight %.3f is not the template's %.3f", id, T.rootHeight, root.Position.Y - lowestY(npc)))
	else
		npc, root, humanoid, extra, ground = imported(id, def, T)
	end
	local groundOffset = T.groundOffset or 0
	humanoid.AutomaticScalingEnabled = false
	humanoid.RequiresNeck = false
	humanoid.BreakJointsOnDeath = false
	humanoid.HipHeight = math.max(0, T.rootHeight - root.Size.Y * 0.5)
	humanoid.MaxHealth = def.health
	humanoid.Health = def.health
	humanoid.WalkSpeed = def.chaseSpeed
	humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
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
	table.insert(
		report,
		string.format(
			"INSTALLED %s %s hrpHeight=%.3f hipHeight=%.3f lowestMeshAboveGround=%.3f",
			id,
			extra,
			root.Size.Y,
			humanoid.HipHeight,
			lowestY(npc) - ground
		)
	)
end
-- VFX mesh templates: children of the BossVfxAssets ids module (plan F Task 10 fills its Source).
local kit = raw and raw:FindFirstChild("VfxKit")
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
