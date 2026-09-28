-- Normalizes the five mini islands after Studio's 3D Importer and stores them as
-- ReplicatedStorage.MapSelectIslands.<MapId> for the run-setup backdrop (MapSelectBackdrop).
-- Run in Edit after File > Import 3D of exports/fbx/*-mini-island.fbx at default settings.
-- Bounds come from studio-island-bounds.json (main island mesh, glTF axes, top at y=0). The FBX
-- importer turns the islands 180 degrees about Y relative to glTF, so x and z flip here (verified
-- 2026-09-27 from the Pine Valley log offsets); the Blender front camera ends up on -Z.
-- Refuses to overwrite an island that is already installed.
local RS = game:GetService("ReplicatedStorage")
local BOUNDS = {
	PineValley = { file = "pinevalley-mini-island", mesh = "PineValley_Island", center = Vector3.new(0.0413, -12.7246, -0.3092), sizeX = 62.022 },
	BeachCove = { file = "beachcove-mini-island", mesh = "BeachCove_Island", center = Vector3.new(0.656, -11.009, 0.0983), sizeX = 62.0999 },
	DesertBasin = { file = "desert-mini-island", mesh = "Desert_Island", center = Vector3.new(0.6071, -10.0746, 0.0479), sizeX = 62.0201 },
	FrozenPass = { file = "frozen-mini-island", mesh = "FrozenPass_Island", center = Vector3.new(0.6101, -10.7058, 0.218), sizeX = 62.0181 },
	VolcanicCrater = { file = "volcanic-mini-island", mesh = "Volcanic_Island", center = Vector3.new(0.6071, -6.1048, 0.0479), sizeX = 62.0201 },
}
local LAVA = Color3.fromRGB(255, 118, 36)

local folder = RS:FindFirstChild("MapSelectIslands") or Instance.new("Folder")
folder.Name = "MapSelectIslands"
folder.Parent = RS
local report = {}
for mapId, b in BOUNDS do
	if folder:FindFirstChild(mapId) then
		table.insert(report, mapId .. ": already installed")
		continue
	end
	local model = workspace:FindFirstChild(b.file)
	local island = model and model:FindFirstChild(b.mesh, true)
	if not island then
		table.insert(report, mapId .. ": import not found (" .. b.file .. ")")
		continue
	end
	-- Importer unit handling varies (1x or 100x); restore the authored size in studs.
	local factor = island.Size.X / b.sizeX
	if math.abs(factor - 1) > 0.01 then
		model:ScaleTo(model:GetScale() / factor)
	end
	local c = Vector3.new(-b.center.X, b.center.Y, -b.center.Z)
	local origin = island.Position - island.CFrame:VectorToWorldSpace(c)
	model.WorldPivot = CFrame.new(origin) * (island.CFrame - island.Position)
	local parts = 0
	for _, p in model:GetDescendants() do
		if p:IsA("BasePart") then
			parts += 1
			p.Anchored = true
			p.CanCollide = false
			p.CanQuery = false
			p.CanTouch = false
			p.Locked = true
			if string.find(p.Name, "_Lava") then
				-- The importer puts this emissive mesh on a SurfaceAppearance; Neon glows from Color.
				local sa = p:FindFirstChildOfClass("SurfaceAppearance")
				if sa then
					p.TextureID = sa.ColorMap
					sa:Destroy()
				end
				p.Material = Enum.Material.Neon
				p.Color = LAVA
				p.CastShadow = false
			end
		end
	end
	model.Name = mapId
	model:SetAttribute("SourceFbx", "roguelite-planning/blender-map-mini-islands/exports/fbx/" .. b.file .. ".fbx")
	model:PivotTo(CFrame.new(0, 0, 0))
	model.Parent = folder
	table.insert(report, string.format("%s: %d parts, scale fix %.3f", mapId, parts, factor))
end
return table.concat(report, "\n")
