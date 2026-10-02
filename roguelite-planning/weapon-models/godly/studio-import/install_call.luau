local install = (function()
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
			part.PivotOffset = CFrame.identity -- the importer's is turned and 100x
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

end)()
return install({["import"]="Godly_Weapons",["replace"]=true,["weapons"]={{["id"]="36",["name"]="Reaper's Scythe",["folder"]="reapers-scythe",["scale"]=1.15,["aim"]="blade",["texture"]="rbxassetid://81028499820107",["textured"]="ReapersScythe",["parts"]={["ReapersScythe"]={["kind"]="textured",["center"]={0.9565,2.5911,0.048},["size"]={3.7841,4.9168,0.9157}},["ReapersScythe_Glow"]={["kind"]="glow",["center"]={0.9422,2.2247,0.1251},["size"]={3.749,4.4495,0.7378},["color"]={255,22,52}},["ReapersScythe_GlowCore"]={["kind"]="glow",["center"]={0.9419,3.1772,-0.0596},["size"]={3.7481,2.2584,0.3906},["color"]={255,150,128}}},["points"]={["Grip"]={["part"]="ReapersScythe",["at"]={-0.0,1.8769,0.0}},["FloatPivot"]={["part"]="ReapersScythe",["at"]={-0.0,2.5247,0.0}}}},{["id"]="37",["name"]="Poseidon's Trident",["folder"]="poseidons-trident",["scale"]=1.0,["aim"]="blade",["texture"]="rbxassetid://99157776260222",["textured"]="PoseidonsTrident",["parts"]={["PoseidonsTrident"]={["kind"]="textured",["center"]={-0.0,3.1545,-0.0087},["size"]={2.3274,6.3091,1.253}},["PoseidonsTrident_Glow"]={["kind"]="glow",["center"]={-0.0,3.459,-0.0145},["size"]={2.4606,5.882,0.637},["color"]={0,132,172}},["PoseidonsTrident_GlowCore"]={["kind"]="glow",["center"]={-0.0,3.7152,-0.0156},["size"]={0.587,0.6319,0.6027},["color"]={176,255,240}}},["points"]={["Grip"]={["part"]="PoseidonsTrident",["at"]={-0.0,2.3884,0.0}},["ThrowPivot"]={["part"]="PoseidonsTrident",["at"]={-0.0,3.1096,0.0}},["Tip"]={["part"]="PoseidonsTrident",["at"]={-0.0,6.3095,0.0}},["Pearl"]={["part"]="PoseidonsTrident",["at"]={-0.0,3.8965,0.0}}}},{["id"]="38",["name"]="Storm Bow",["folder"]="storm-bow",["scale"]=1.05,["aim"]="forward",["texture"]="rbxassetid://102197317454414",["textured"]="StormBow",["parts"]={["StormBow"]={["kind"]="textured",["center"]={0.0989,2.5,0.0},["size"]={1.7132,5.0,0.5948}},["StormBow_Glow"]={["kind"]="glow",["center"]={-0.058,2.5,0.0},["size"]={1.5399,4.827,0.4812},["color"]={18,108,255}},["StormBow_GlowCore"]={["kind"]="glow",["center"]={-0.059,2.5,0.0},["size"]={1.4039,4.8458,0.5002},["color"]={214,240,255}}},["points"]={["Grip"]={["part"]="StormBow",["at"]={-0.0203,2.5,0.0}},["FloatPivot"]={["part"]="StormBow",["at"]={-0.0203,2.5,0.0}},["ArrowRest"]={["part"]="StormBow",["at"]={-0.0135,2.7842,-0.203}},["Nock"]={["part"]="StormBow",["at"]={-0.7133,2.7842,0.0}}}},{["id"]="39",["name"]="Shadow Daggers",["folder"]="shadow-daggers",["scale"]=0.9,["aim"]="blade",["texture"]="rbxassetid://135902138077868",["textured"]="ShadowDaggers_L",["parts"]={["ShadowDaggers_L"]={["kind"]="textured",["center"]={-0.9139,2.3232,0.0},["size"]={1.2657,4.2673,0.344}},["ShadowDaggers_L_Glow"]={["kind"]="glow",["center"]={-1.0864,2.2683,0.0},["size"]={1.0293,4.5367,0.316},["color"]={255,14,30}},["ShadowDaggers_L_GlowCore"]={["kind"]="glow",["center"]={-1.0863,2.898,0.0},["size"]={1.053,3.3099,0.328},["color"]={255,64,48}},["ShadowDaggers_R"]={["kind"]="textured",["center"]={0.953,2.1859,0.0},["size"]={1.344,3.9928,0.344}},["ShadowDaggers_R_Glow"]={["kind"]="glow",["center"]={1.1484,2.1235,0.0},["size"]={1.0869,4.247,0.316},["color"]={255,14,30}},["ShadowDaggers_R_GlowCore"]={["kind"]="glow",["center"]={1.15,2.7517,0.0},["size"]={1.1135,3.0174,0.328},["color"]={255,64,48}}},["points"]={["GripL"]={["part"]="ShadowDaggers_L",["at"]={-0.9,0.81,0.0}},["GripR"]={["part"]="ShadowDaggers_R",["at"]={0.9,0.81,0.0}}}},{["id"]="40",["name"]="Vampire Blade",["folder"]="vampire-blade",["scale"]=1.15,["aim"]="blade",["texture"]="rbxassetid://76161511888035",["textured"]="VampireBlade",["parts"]={["VampireBlade"]={["kind"]="textured",["center"]={-0.0,2.6531,-0.1121},["size"]={2.68,4.8095,0.7717}},["VampireBlade_Glow"]={["kind"]="glow",["center"]={-0.0,2.53,-0.052},["size"]={2.2024,5.06,0.732},["color"]={255,6,36}},["VampireBlade_GlowCore"]={["kind"]="glow",["center"]={-0.0,3.2192,-0.051},["size"]={0.28,2.8416,0.754},["color"]={255,72,48}}},["points"]={["Grip"]={["part"]="VampireBlade",["at"]={-0.0,1.09,0.0}},["FloatPivot"]={["part"]="VampireBlade",["at"]={-0.0,2.53,0.0}}}},{["id"]="41",["name"]="Ray Gun",["folder"]="ray-gun",["scale"]=0.9,["aim"]="forward",["texture"]="rbxassetid://107056169613395",["textured"]="RayGun",["parts"]={["RayGun"]={["kind"]="textured",["center"]={-0.081,0.9454,0.0},["size"]={3.3271,1.8908,0.5774}},["RayGun_Glow"]={["kind"]="glow",["center"]={0.0453,1.2121,0.0},["size"]={2.7369,0.4904,0.522},["color"]={16,255,40}},["RayGun_GlowCore"]={["kind"]="glow",["center"]={0.6292,1.1775,0.0832},["size"]={2.0867,0.4262,0.2864},["color"]={140,255,110}}},["points"]={["Grip"]={["part"]="RayGun",["at"]={-0.9435,0.4598,0.0}},["Muzzle"]={["part"]="RayGun",["at"]={1.6725,1.1775,0.0}}}}}})
