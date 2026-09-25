--!strict
-- Build the Beach Cove kit directly in Studio, with no 3D Importer step.
--
-- Roblox can construct a MeshPart from geometry supplied in Luau:
--   AssetService:CreateEditableMesh()  -> add vertices / uvs / triangles
--   AssetService:CreateMeshPartAsync(Content.fromObject(em)) -> a real MeshPart
-- so the geometry never has to be uploaded as an asset at all.
--
-- Geometry comes from a local HTTP server started beside this repo:
--   python -m http.server 8787 --bind 127.0.0.1   (run in the kit folder)
-- Requires HttpService.HttpEnabled = true.
--
-- Pass 1 builds the 25 meshes into ServerStorage.BeachCoveKit.
-- Pass 2 places them per arena-layout.json into Workspace.BeachCoveArena.

local AssetService = game:GetService("AssetService")
local HttpService = game:GetService("HttpService")
local ServerStorage = game:GetService("ServerStorage")

local BASE = "http://127.0.0.1:8787"
local log = {}
local function note(fmt, ...)
	table.insert(log, string.format(fmt, ...))
end

local function getJson(path: string)
	local raw = HttpService:GetAsync(BASE .. path)
	return HttpService:JSONDecode(raw)
end

-- Filled in from the upload_image step; name -> "rbxassetid://...".
local TEXTURES: { [string]: string } = TEXTURE_MAP_PLACEHOLDER

-- ---------------------------------------------------------------------------
-- pass 1: geometry
-- ---------------------------------------------------------------------------
local function buildAsset(stem: string, info: any): MeshPart?
	local data = getJson("/studio-mesh-json/" .. info.json)

	local em = AssetService:CreateEditableMesh()

	local vids = table.create(#data.vertices)
	for i, v in ipairs(data.vertices) do
		vids[i] = em:AddVertex(Vector3.new(v[1], v[2], v[3]))
	end

	local uvids = table.create(#data.uvs)
	for i, uv in ipairs(data.uvs) do
		uvids[i] = em:AddUV(Vector2.new(uv[1], uv[2]))
	end

	local made = 0
	for _, t in ipairs(data.triangles) do
		-- t = {v0, v1, v2, uv0, uv1, uv2}, all 1-based from the exporter
		local fid = em:AddTriangle(vids[t[1] + 1], vids[t[2] + 1], vids[t[3] + 1])
		if fid then
			made += 1
			pcall(function()
				em:SetFaceUVs(fid, { uvids[t[4] + 1], uvids[t[5] + 1], uvids[t[6] + 1] })
			end)
		end
	end

	local ok, mp = pcall(function()
		return AssetService:CreateMeshPartAsync(Content.fromObject(em))
	end)
	if not ok then
		note("FAIL %-24s %s", stem, tostring(mp):sub(1, 110))
		return nil
	end

	mp.Name = data.name
	mp.Anchored = true
	mp.CanCollide = false
	mp.CanTouch = false
	mp.Color = Color3.new(1, 1, 1)
	local tex = TEXTURES[data.name]
	if tex then
		pcall(function()
			mp.TextureID = tex
		end)
	end
	note("ok   %-24s %d tris  size %s", stem, made, tostring(mp.Size))
	return mp
end

local manifest = getJson("/studio-mesh-json/manifest.json")

local kit = ServerStorage:FindFirstChild("BeachCoveKit")
if not kit then
	kit = Instance.new("Folder")
	kit.Name = "BeachCoveKit"
	kit.Parent = ServerStorage
end
for _, c in ipairs(kit:GetChildren()) do
	c:Destroy()
end

local built = 0
for stem, info in pairs(manifest.assets) do
	local mp = buildAsset(stem, info)
	if mp then
		mp.Parent = kit
		built += 1
	end
end
note("built %d/%d meshes", built, 25)

-- ---------------------------------------------------------------------------
-- pass 2: place the arena
-- ---------------------------------------------------------------------------
local layout = getJson("/arena-layout.json")

local existing = workspace:FindFirstChild("BeachCoveArena")
if existing then
	existing:Destroy()
end

local arena = Instance.new("Folder")
arena.Name = "BeachCoveArena"
local scenery = Instance.new("Folder")
scenery.Name = "Scenery"
scenery.Parent = arena

-- Sit the arena clear of map one rather than on top of it.
local ORIGIN = Vector3.new(ARENA_ORIGIN_X, ARENA_ORIGIN_Y, ARENA_ORIGIN_Z)

local NON_COLLIDING = {
	["16_Palm_Tall"] = true, ["17_Palm_Leaning"] = true, ["18_Palm_Short"] = true,
	["19_Driftwood_Log"] = true, ["20_Driftwood_Planks"] = true,
	["22_Tide_Pool_Small"] = true, ["23_Tide_Pool_Large"] = true,
	["24_Grass_Patch_Small"] = true, ["25_Grass_Patch_Large"] = true,
}

local function luaName(stem: string): string
	local parts = {}
	for piece in string.gmatch(stem, "[^-]+") do
		if tonumber(piece) then
			table.insert(parts, piece)
		else
			table.insert(parts, piece:sub(1, 1):upper() .. piece:sub(2))
		end
	end
	return table.concat(parts, "_")
end

local pivots: { [string]: Vector3 } = {}
for stem, info in pairs(layout.assets) do
	local p = info.pivot_offset
	pivots[luaName(stem)] = Vector3.new(p[1], p[2], p[3])
end

local placed, missing = 0, {}
for _, inst in ipairs(layout.instances) do
	local name = luaName(inst.asset)
	local template = kit:FindFirstChild(name)
	if not template then
		missing[name] = true
		continue
	end
	local p = inst.position
	local part = template:Clone()
	part.Anchored = true
	part.CanCollide = not NON_COLLIDING[name]
	part.CanQuery = part.CanCollide
	part.CanTouch = false
	local base = CFrame.new(ORIGIN + Vector3.new(p[1], p[2], p[3]))
		* CFrame.Angles(0, math.rad(inst.yaw_deg), 0)
	part.CFrame = base * CFrame.new(pivots[name] or Vector3.zero)
	part.Parent = scenery
	placed += 1
end

-- Invisible boundary on the clear-floor circle; the cliff meshes are scenery.
local boundary = Instance.new("Folder")
boundary.Name = "BoundaryWall"
boundary.Parent = arena

local R = layout.arena_clear_diameter_studs / 2
local SEGMENTS = 32
local segWidth = 2 * math.pi * R / SEGMENTS * 1.08
for i = 1, SEGMENTS do
	local theta = (i - 1) / SEGMENTS * 2 * math.pi
	local wall = Instance.new("Part")
	wall.Name = string.format("Wall%02d", i)
	wall.Size = Vector3.new(segWidth, 60, 2)
	wall.Anchored = true
	wall.CanCollide = true
	wall.Transparency = 1
	wall.CastShadow = false
	wall.CFrame = CFrame.new(ORIGIN + Vector3.new(math.cos(theta) * R, 30, math.sin(theta) * R))
		* CFrame.Angles(0, -theta, 0)
	wall.Parent = boundary
end

-- Sand floor, so the cove reads as a beach rather than floating cliffs.
local floor = Instance.new("Part")
floor.Name = "SandFloor"
floor.Shape = Enum.PartType.Cylinder
floor.Size = Vector3.new(2, layout.sand_floor_radius_studs * 2, layout.sand_floor_radius_studs * 2)
floor.CFrame = CFrame.new(ORIGIN + Vector3.new(0, -1, 0)) * CFrame.Angles(0, 0, math.rad(90))
floor.Anchored = true
floor.Color = Color3.fromRGB(223, 200, 150)
floor.Material = Enum.Material.Sand
floor.TopSurface = Enum.SurfaceType.Smooth
floor.Parent = arena

arena.Parent = workspace

local miss = {}
for n in pairs(missing) do
	table.insert(miss, n)
end
if #miss > 0 then
	table.sort(miss)
	note("MISSING: %s", table.concat(miss, ", "))
end
note("placed %d/%d instances at origin %s", placed, #layout.instances, tostring(ORIGIN))
return table.concat(log, "\n")
