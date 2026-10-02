-- Installs the six Godly weapons as ReplicatedStorage.RogueliteCombat.WeaponTemplates.36-41 after
-- ONE Studio Import 3D of studio-import/Godly_Weapons.fbx (combine_godly_weapons.py builds it).
-- Ids follow MonetizationConfig.GodlyWeapons: 36 Reaper's Scythe, 37 Poseidon's Trident,
-- 38 Storm Bow, 39 Shadow Daggers, 40 Vampire Blade, 41 Ray Gun.
--
-- Run in Edit: (this chunk)(cfg). make_install_call.py writes the cfg from each weapon's
-- studio-install-data.json and studio-asset-ids.json:
--   cfg.import  = 'Godly_Weapons'  the Workspace model the importer made. If it's gone, the raw copy
--                 kept in ServerStorage.GodlyWeaponImport by an earlier install is used instead.
--   cfg.weapons = { {id, name, folder, scale, aim, texture, textured, parts, points}, ... }
--       scale    play size = authored size x scale
--       aim      'blade' keeps the authored frame (tip +Y, blade in the XY plane, like Excalibur);
--                'forward' turns +X (barrel / arrow) to combat-forward -Z, like the gun templates
--       parts    {[meshName] = {kind = 'textured'|'glow', center = {x,y,z}, size = {x,y,z}, color = {r,g,b}}}
--       points   {[attachmentName] = {part = meshName, at = {x,y,z}}}, authored Studio-frame points
--   cfg.replace = true to replace installed templates 36-41
--
-- Nothing reads ids 36-41 until WeaponCatalog lists them, so installing changes no gameplay.
-- The importer may rescale (it brought Dragon Scale in at 100x) and may turn the whole scene, so
-- nothing is assumed: each weapon's import scale comes from its textured mesh, and every part's
-- offset from that mesh is checked against the authored data before anything is replaced.
return function(cfg)
	assert(not game:GetService("RunService"):IsRunning(), "Stop Play before installing")
	local combat = game.ReplicatedStorage:WaitForChild("RogueliteCombat")
	local templates = combat:WaitForChild("WeaponTemplates")
	local imported = workspace:FindFirstChild(cfg.import)
	local source = imported or game.ServerStorage:FindFirstChild("GodlyWeaponImport")
	assert(source, "Import Godly_Weapons.fbx first (File > Import 3D)")

	local function v3(t)
		return Vector3.new(t[1], t[2], t[3])
	end
	local AIM = { blade = CFrame.identity, forward = CFrame.Angles(0, math.pi / 2, 0) }
	local report = {}
	local built = {}

	for _, w in cfg.weapons do
		assert(cfg.replace or not templates:FindFirstChild(w.id), w.id .. " is installed; pass replace=true")
		local aim = assert(AIM[w.aim], w.id .. ": unknown aim " .. tostring(w.aim))
		local meshes = {}
		for name in w.parts do
			local mesh = source:FindFirstChild(name, true)
			assert(mesh and mesh:IsA("MeshPart"), w.id .. ": missing imported mesh " .. name)
			meshes[name] = mesh
		end

		-- Import scale and frame, from the textured mesh.
		local base = meshes[w.textured]
		local baseData = w.parts[w.textured]
		local sigma = base.Size.Magnitude / v3(baseData.size).Magnitude
		local sizeError = (base.Size / sigma - v3(baseData.size)).Magnitude
		assert(sizeError < 0.05, string.format("%s: textured mesh proportions off by %.3f (turned?)", w.id, sizeError))
		for name, mesh in meshes do
			local data = w.parts[name]
			local rel = base.CFrame:ToObjectSpace(mesh.CFrame)
			local offset = rel.Position / sigma
			local expected = v3(data.center) - v3(baseData.center)
			assert(
				(offset - expected).Magnitude < 0.05,
				string.format("%s: %s sits %.3f studs off its authored spot", w.id, name, (offset - expected).Magnitude)
			)
			assert((mesh.Size / sigma - v3(data.size)).Magnitude < 0.05, w.id .. ": " .. name .. " size mismatch")
		end

		local model = Instance.new("Model")
		model.Name = w.id
		local placed = {}
		for name, mesh in meshes do
			local data = w.parts[name]
			local part = mesh:Clone()
			part:ClearAllChildren()
			part.Name = name
			part.Size = v3(data.size) * w.scale
			-- Authored frame: centre from the install data, turn as imported relative to the textured mesh.
			local turn = base.CFrame:ToObjectSpace(mesh.CFrame).Rotation
			part.CFrame = aim * CFrame.new(v3(data.center) * w.scale) * turn
			part.Anchored, part.CanCollide, part.CanTouch, part.CanQuery = true, false, false, false
			part.Massless = true
			part.RenderFidelity = Enum.RenderFidelity.Automatic
			if data.kind == "textured" then
				part.Material = Enum.Material.Plastic
				part.Color = Color3.new(1, 1, 1)
				part.TextureID = w.texture
			else
				part.Material = Enum.Material.Neon
				part.Color = Color3.fromRGB(data.color[1], data.color[2], data.color[3])
				part.TextureID = ""
				part.CastShadow = false
			end
			part.Parent = model
			placed[name] = part
		end

		-- Centre the bounds on the origin, like every other template. A new Model takes its pivot
		-- rotation from its first part, so reset it first or turned weapons measure in the wrong axes.
		model.WorldPivot = CFrame.identity
		local box, size = model:GetBoundingBox()
		local shift = CFrame.new(-box.Position)
		for _, part in placed do
			part.CFrame = shift * part.CFrame
		end
		for pointName, point in w.points do
			local part = assert(placed[point.part], w.id .. ": point " .. pointName .. " on missing part")
			local world = shift * aim * (v3(point.at) * w.scale)
			local attachment = Instance.new("Attachment")
			attachment.Name = pointName
			attachment.Position = part.CFrame:PointToObjectSpace(world)
			attachment.Parent = part
		end
		model.WorldPivot = CFrame.identity
		model:SetAttribute("WeaponIndex", tonumber(w.id))
		model:SetAttribute("DisplayName", w.name)
		model:SetAttribute("Rarity", "Godly")
		model:SetAttribute("GodlyPlayScale", w.scale)
		model:SetAttribute("RelativeWeaponScale", 1 / 3)
		model:SetAttribute("BoundsCenter", Vector3.zero)
		model:SetAttribute("BoundsSize", size)
		model:SetAttribute("SourceDisplay", "weapon-models/godly/" .. w.folder .. " via Godly_Weapons.fbx")
		model:SetAttribute("GodlyTemplateVersion", 1)
		table.insert(built, model)
		table.insert(
			report,
			string.format(
				"%s %s: %d parts, bounds %.2f x %.2f x %.2f, import scale %.3f",
				w.id,
				w.name,
				#model:GetChildren(),
				size.X,
				size.Y,
				size.Z,
				sigma
			)
		)
	end

	-- Everything validated: swap the templates in together.
	for _, model in built do
		local old = templates:FindFirstChild(model.Name)
		if old then
			old:Destroy()
		end
		model.Parent = templates
	end
	-- Keep the raw import (server-only) so a re-install never needs another GUI import.
	if imported then
		local old = game.ServerStorage:FindFirstChild("GodlyWeaponImport")
		if old then
			old:Destroy()
		end
		imported.Name = "GodlyWeaponImport"
		imported.Parent = game.ServerStorage
	end
	return table.concat(report, "\n")
end
