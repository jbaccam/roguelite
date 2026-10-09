-- Installs the Pizza Cutter (id 42, Chef's Legendary melee) as ReplicatedStorage.RogueliteCombat.WeaponTemplates['42']
-- after ONE Studio Import (File > Import, Ctrl+M) of this folder's Model.fbx, staged as build/chef-import/PizzaCutter.fbx.
-- 2026-10-09.
--
-- Run in Edit: (this chunk)(cfg). Every cfg field is optional:
--   cfg.import   the Workspace model the importer made. Studio names it after the file: 'PizzaCutter' (the default).
--                If several Workspace children share the name, the one holding MeshParts 'Handle' and 'Wheel' is
--                used (two such is an error). If none is left, the raw copy an earlier install kept in
--                ServerStorage.PizzaCutterImport is used, so a re-install never needs another GUI import.
--   cfg.texture  'rbxassetid://<id>' of BaseColor.png. Default: TEXTURE, the authored atlas uploaded 2026-10-09 (not
--                the importer's copy, which can drift in colour). Set on both meshes as MeshPart.TextureID, never a
--                SurfaceAppearance (script-made SurfaceAppearances render white in Play).
--   cfg.length   held length in studs. Default 3.5: the Frying Pan template's 0.832 studs per Blender unit x 4.21
--                (Pan 3.78 long, Spatula 2.65).
--   cfg.replace  true rebuilds an installed '42'. Without it an installed '42' is left alone, so a rerun is a no-op.
--   cfg.dryRun   true checks everything and reports what it would do, and changes nothing in the place.
--   cfg.source   tests only: an Instance holding Handle and Wheel to read instead of the import.
--
-- Touches only WeaponTemplates['42'], ServerStorage.PizzaCutterImport and, if the play-size showcase folder still
-- exists (CleanupPlace removed it; the Armory and journal clone the template), its '42_Pizza_Cutter'. It never runs
-- InstallLoadout (that rebuilds every template and asserts exactly 36), so no other weapon is touched.
--
-- Template convention, as 01 Frying Pan and 05 Spatula: Model '42', identity WorldPivot, bounds centred on the origin
-- (BoundsCenter 0, BoundsSize = the box), striking end (the wheel) on +Y, thin axis Z. MeshParts 'Handle' and 'Wheel'
-- are anchored, CanCollide/CanTouch/CanQuery off, Plastic, white, TextureID, RenderFidelity Automatic.
-- Wheel spin convention (read by RogueliteCombat.client and WeaponShowcaseStage): the Wheel's CFrame centre is the
-- axle and it spins about its OWN local Z (attribute WheelAxis='Z'); WheelRadius is the rim radius in studs. The
-- Handle never moves relative to the model.
--
-- Authored geometry (validation.json), in Roblox axes and Blender units. The FBX maps Blender (x, y, z) to Roblox
-- (x, z, -y), and Roblox centres each MeshPart on its own bounding box.
local LENGTH = 4.21
local HANDLE = { center = Vector3.new(0, 0.715, -0.0495), size = Vector3.new(0.8, 3.35, 0.679) }
local WHEEL = { center = Vector3.new(0, 2.21, -0.132), size = Vector3.new(2.08, 2.08, 0.23), radius = 1.04 }
local GRIP = Vector3.zero -- the Handle object's origin: the wood grip's midpoint
local VERSION = 1
local TEXTURE = "rbxassetid://92867308963249" -- BaseColor.png, uploaded by hand 2026-10-09

return function(cfg)
	cfg = cfg or {}
	assert(not game:GetService("RunService"):IsRunning(), "Stop Play before installing")
	local combat = game.ReplicatedStorage:WaitForChild("RogueliteCombat")
	local templates = combat:WaitForChild("WeaponTemplates")
	local existing = templates:FindFirstChild("42")
	if existing and not cfg.replace then
		return "WeaponTemplates.42 is already installed (version "
			.. tostring(existing:GetAttribute("PizzaCutterTemplateVersion"))
			.. "); nothing changed. Pass replace=true to rebuild it."
	end

	-- The import: Handle and Wheel MeshParts somewhere inside it.
	local function meshes(m)
		local h, w = m:FindFirstChild("Handle", true), m:FindFirstChild("Wheel", true)
		if h and h:IsA("MeshPart") and w and w:IsA("MeshPart") then
			return h, w
		end
	end
	local importName = cfg.import or "PizzaCutter"
	local found = {}
	for _, child in workspace:GetChildren() do
		if child.Name == importName and meshes(child) then
			table.insert(found, child)
		end
	end
	assert(#found <= 1, "Two Workspace models named '" .. importName .. "' hold Handle and Wheel; delete one or pass cfg.import")
	local imported = found[1]
	local kept = game.ServerStorage:FindFirstChild("PizzaCutterImport")
	local source = imported or (kept and meshes(kept) and kept)
	if cfg.source then -- tests: read this instance instead (with dryRun, nothing in the place is read or moved)
		source, imported = cfg.source, nil
	end
	assert(source, "Import build/chef-import/PizzaCutter.fbx first (File > Import); expected Workspace." .. importName)
	local handle, wheel = meshes(source)

	-- Import scale and frame, from the Handle (the importer brings meshes in at about 100x and may turn the scene).
	local sigma = handle.Size.Magnitude / HANDLE.size.Magnitude
	local function near(a, b, what)
		local off = (a - b).Magnitude
		assert(off < 0.03, string.format("%s is off by %.3f Blender units (turned or a different export?)", what, off))
	end
	near(handle.Size / sigma, HANDLE.size, "Handle proportions")
	near(wheel.Size / sigma, WHEEL.size, "Wheel size (its thin axis must be local Z)")
	local rel = handle.CFrame:ToObjectSpace(wheel.CFrame)
	-- The importer may turn the scene 180 degrees about Y (seen 2026-10-09: the wheel came in on +Z, not -Z),
	-- which only moves which face the arm is on; compare the Z offset by size, not sign.
	local expected = WHEEL.center - HANDLE.center
	local got = rel.Position / sigma
	near(Vector3.new(got.X, got.Y, math.abs(got.Z)), Vector3.new(expected.X, expected.Y, math.abs(expected.Z)), "Wheel axle offset from the Handle")
	-- The axle must run along the model's Z, so the rim sweeps edge first through the swing plane (local XY).
	local axle = rel:VectorToWorldSpace(Vector3.zAxis)
	assert(math.abs(axle.Z) > 0.999, "Wheel axle is turned off the model Z axis: " .. tostring(axle))

	-- Texture: one shared atlas for both meshes.
	local texture, textureFrom = cfg.texture or TEXTURE, cfg.texture and "cfg.texture" or "the uploaded BaseColor.png"
	if texture == "" then
		texture, textureFrom = handle.TextureID, "the importer's Handle.TextureID (check its pixels against BaseColor.png)"
	end
	if texture == "" then
		local appearance = handle:FindFirstChildOfClass("SurfaceAppearance")
		local ok, map = pcall(function()
			return appearance and appearance.ColorMap
		end)
		texture, textureFrom = ok and map or "", "the importer's colour map (check its pixels against BaseColor.png)"
	end
	assert(texture and texture ~= "", "No texture found: upload BaseColor.png and pass cfg.texture='rbxassetid://<id>'")

	-- Build the template off the DataModel.
	local scale = (cfg.length or 3.5) / LENGTH
	local model = Instance.new("Model")
	model.Name = "42"
	local function place(mesh, name, data, turn)
		local part = mesh:Clone()
		part:ClearAllChildren() -- importer extras, including any SurfaceAppearance
		part.Name = name
		part.Size = data.size * scale
		part.CFrame = CFrame.new(data.center * scale) * turn
		part.Anchored, part.CanCollide, part.CanTouch, part.CanQuery = true, false, false, false
		part.Massless = false
		part.CastShadow = true
		part.PivotOffset = CFrame.identity -- the importer's is 100x
		part.RenderFidelity = Enum.RenderFidelity.Automatic
		part.Material = Enum.Material.Plastic
		part.Color = Color3.new(1, 1, 1)
		part.TextureID = texture
		part.Parent = model
		return part
	end
	local handlePart = place(handle, "Handle", HANDLE, CFrame.identity)
	-- The imported turn is kept only about the axle (the wheel is round), so the texture lands as authored.
	local wheelPart = place(wheel, "Wheel", WHEEL, rel.Rotation)
	-- Centre the bounds on the origin, like every other template. A new Model takes its pivot rotation from its
	-- first part, so reset it before measuring.
	model.WorldPivot = CFrame.identity
	local box, size = model:GetBoundingBox()
	local shift = CFrame.new(-box.Position)
	handlePart.CFrame = shift * handlePart.CFrame
	wheelPart.CFrame = shift * wheelPart.CFrame
	local grip = Instance.new("Attachment")
	grip.Name = "Grip"
	grip.Position = handlePart.CFrame:PointToObjectSpace(shift * (GRIP * scale))
	grip.Parent = handlePart
	wheelPart:SetAttribute("WheelAxis", "Z")
	wheelPart:SetAttribute("WheelRadius", WHEEL.radius * scale)
	model.WorldPivot = CFrame.identity
	model:SetAttribute("WeaponIndex", 42)
	model:SetAttribute("DisplayName", "Pizza Cutter")
	model:SetAttribute("ShowcaseOnly", true)
	model:SetAttribute("RelativeWeaponScale", 1 / 3)
	model:SetAttribute("BoundsCenter", Vector3.zero)
	model:SetAttribute("BoundsSize", size)
	model:SetAttribute("WheelAxis", "Z")
	model:SetAttribute("SourceDisplay", "weapon-models/assets/42-pizza-cutter/Model.fbx")
	model:SetAttribute("PizzaCutterTemplateVersion", VERSION)

	local showcase = workspace:FindFirstChild("RogueliteWeaponShowcase_PlaySize")
	local report = {
		string.format("%s WeaponTemplates.42 Pizza Cutter: Handle + Wheel, bounds %.2f x %.2f x %.2f studs (length %.2f)",
			existing and "Replace" or "Create", size.X, size.Y, size.Z, size.Y),
		string.format("  import %s (scale %.2f), texture %s from %s", source:GetFullName(), sigma, texture, textureFrom),
		string.format("  wheel axle at %s, radius %.3f studs, spins about its local Z", tostring(wheelPart.Position), WHEEL.radius * scale),
		imported and "  keep the raw import as ServerStorage.PizzaCutterImport" or "  raw import already kept in ServerStorage",
		showcase and "  add RogueliteWeaponShowcase_PlaySize.42_Pizza_Cutter" or "  no play-size showcase folder (removed); nothing to add there",
	}
	if cfg.dryRun then
		model:Destroy()
		table.insert(report, 1, "DRY RUN, nothing changed. Would:")
		return table.concat(report, "\n")
	end

	-- Everything validated: swap it in.
	if existing then
		existing:Destroy()
	end
	model.Parent = templates
	if showcase then
		local old = showcase:FindFirstChild("42_Pizza_Cutter")
		if old then
			old:Destroy()
		end
		local right = -math.huge
		for _, m in showcase:GetChildren() do
			if m:IsA("Model") then
				right = math.max(right, m:GetPivot().X)
			end
		end
		local display = model:Clone()
		display.Name = "42_Pizza_Cutter"
		display:PivotTo(CFrame.new((right > -math.huge and right or 0) + 6, 4, 0))
		display.Parent = showcase
	end
	if imported then
		if kept then
			kept:Destroy()
		end
		imported.Name = "PizzaCutterImport"
		imported.Parent = game.ServerStorage
	end
	return table.concat(report, "\n")
end
