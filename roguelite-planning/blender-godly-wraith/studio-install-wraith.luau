-- Installs the crimson wraith (the Reaper's Scythe's helper, plans/2026-10-01-G) as
-- ReplicatedStorage.RogueliteCombat.GodlyAssets.Wraith after one Import (Ctrl+M) of
-- exports/fbx/Wraith.fbx. GodlyVisuals clones it for every wraith and animates it.
-- Run in Edit: (this chunk)(cfg); make_install_call.py writes the cfg from studio-install-data.json.
--   cfg.import  = 'Wraith' (the Workspace model the importer made; if it's gone, the raw copy kept
--                 in ServerStorage.GodlyWraithImport by an earlier install is used)
--   cfg.texture = uploaded BaseColor (MeshPart.TextureID; SurfaceAppearance renders blank in Play)
--   cfg.parts   = {[mesh] = {kind, center, size, color, shoulder}}, authored Studio frame
--   cfg.points  = {[attachment] = {part = mesh, at = {x,y,z}}}
-- The model's pivot is the authored origin (body axis at chest height) and it faces -Z. Each arm
-- gets a `Shoulder` attachment at its pivot so the claws swing around the shoulder; the body gets
-- `Tail` (smoke), `Eyes` and `Core`. The importer's scale and turn are measured, never assumed.
return function(cfg)
	assert(not game:GetService("RunService"):IsRunning(), "Stop Play before installing")
	local combat = game.ReplicatedStorage:WaitForChild("RogueliteCombat")
	local imported = workspace:FindFirstChild(cfg.import)
	local source = imported or game.ServerStorage:FindFirstChild("GodlyWraithImport")
	assert(source, "Import exports/fbx/Wraith.fbx first (File > Import, Ctrl+M)")
	local function v3(t)
		return Vector3.new(t[1], t[2], t[3])
	end
	local meshes = {}
	for name in cfg.parts do
		local mesh = source:FindFirstChild(name, true)
		assert(mesh and mesh:IsA("MeshPart"), "missing imported mesh " .. name)
		meshes[name] = mesh
	end
	local base, baseData = meshes.Wraith_Body, cfg.parts.Wraith_Body
	local sigma = base.Size.Magnitude / v3(baseData.size).Magnitude
	assert((base.Size / sigma - v3(baseData.size)).Magnitude < 0.05, "body proportions differ (turned on import?)")
	for name, mesh in meshes do
		local data = cfg.parts[name]
		local offset = base.CFrame:ToObjectSpace(mesh.CFrame).Position / sigma
		assert((offset - (v3(data.center) - v3(baseData.center))).Magnitude < 0.05, name .. " is off its authored spot")
	end
	local model = Instance.new("Model")
	model.Name = "Wraith"
	local placed = {}
	for name, mesh in meshes do
		local data = cfg.parts[name]
		local part = mesh:Clone()
		part:ClearAllChildren()
		part.Size = v3(data.size)
		part.CFrame = CFrame.new(v3(data.center)) * base.CFrame:ToObjectSpace(mesh.CFrame).Rotation
		part.Anchored, part.CanCollide, part.CanTouch, part.CanQuery, part.Massless = true, false, false, false, true
		part.CastShadow = data.kind == "textured"
		if data.kind == "textured" then
			part.Material = Enum.Material.Plastic
			part.Color = Color3.new(1, 1, 1)
			part.TextureID = cfg.texture
		else
			part.Material = Enum.Material.Neon
			part.Color = Color3.fromRGB(data.color[1], data.color[2], data.color[3])
			part.TextureID = ""
		end
		part.Parent = model
		placed[name] = part
		if data.shoulder then
			local a = Instance.new("Attachment")
			a.Name = "Shoulder"
			a.Position = part.CFrame:PointToObjectSpace(v3(data.shoulder))
			a.Parent = part
		end
	end
	for name, point in cfg.points do
		local part = assert(placed[point.part], "point " .. name .. " on a missing part")
		local a = Instance.new("Attachment")
		a.Name = name
		a.Position = part.CFrame:PointToObjectSpace(v3(point.at))
		a.Parent = part
	end
	model.PrimaryPart = placed.Wraith_Body
	model.WorldPivot = CFrame.identity
	model:SetAttribute("SourceDisplay", "blender-godly-wraith via exports/fbx/Wraith.fbx")
	model:SetAttribute("ImportScale", sigma)
	local assets = combat:FindFirstChild("GodlyAssets")
	if not assets then
		assets = Instance.new("Folder")
		assets.Name = "GodlyAssets"
		assets.Parent = combat
	end
	local old = assets:FindFirstChild("Wraith")
	if old then
		old:Destroy()
	end
	model.Parent = assets
	if imported then
		local keep = game.ServerStorage:FindFirstChild("GodlyWraithImport")
		if keep then
			keep:Destroy()
		end
		imported.Name = "GodlyWraithImport"
		imported.Parent = game.ServerStorage
	end
	local _, size = model:GetBoundingBox()
	return string.format("Wraith installed: %d parts, %.2f x %.2f x %.2f studs, import scale %.3f", #model:GetChildren(), size.X, size.Y, size.Z, sigma)
end
