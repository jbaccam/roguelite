-- Normalizes the armory hall after Studio's 3D Importer and stores it as
-- ReplicatedStorage.ArmoryBackdrop for the Armory screen (ui/ArmoryStage.luau).
-- Run in Edit after File > Import 3D of exports/fbx/armory-backdrop.fbx at default settings.
-- Bounds come from bounds.py (Blender bounding boxes in Studio axes after the importer's 180-degree
-- turn about Y, the same as the map-select islands). The pivot ends up on the dais top centre
-- (the avatar's feet) with the open front facing -Z. Refuses to overwrite an installed hall.
local RS = game:GetService("ReplicatedStorage")
local BOUNDS = {
	Armory_GlowLime = { center = Vector3.new(0, -0.219, 0), sizeX = 5.5517 },
	Armory_Room = { center = Vector3.new(0, 3.7149, 14.5124), sizeX = 80.0 },
}
local GLOW = {
	Armory_GlowLime = Color3.fromRGB(145, 239, 20),
	Armory_GlowWarm = Color3.fromRGB(255, 216, 140),
}

if RS:FindFirstChild("ArmoryBackdrop") then
	return "ArmoryBackdrop already installed; delete it first to reinstall"
end
local model = workspace:FindFirstChild("armory-backdrop")
local anchor = model and model:FindFirstChild("Armory_GlowLime", true)
local room = model and model:FindFirstChild("Armory_Room", true)
if not anchor or not room then
	return "import not found: expected workspace['armory-backdrop'] with Armory_GlowLime and Armory_Room"
end

-- Importer unit handling varies (1x or 100x); restore the authored size in studs.
local factor = room.Size.X / BOUNDS.Armory_Room.sizeX
if math.abs(factor - 1) > 0.01 then
	model:ScaleTo(model:GetScale() / factor)
end
local c = BOUNDS.Armory_GlowLime.center
local origin = anchor.Position - anchor.CFrame:VectorToWorldSpace(c)
model.WorldPivot = CFrame.new(origin) * (anchor.CFrame - anchor.Position)

local report = {}
for _, p in model:GetDescendants() do
	if p:IsA("BasePart") then
		p.Anchored = true
		p.CanCollide = false
		p.CanQuery = false
		p.CanTouch = false
		p.Locked = true
		local glow = GLOW[p.Name]
		if glow then
			-- Lantern glass reads as lit warm glass; Neon blew out under the lobby bloom. Its
			-- PointLights carry the glow.
			p.Material = p.Name == "Armory_GlowWarm" and Enum.Material.SmoothPlastic or Enum.Material.Neon
			p.Color = glow
			p.CastShadow = false
			if p:IsA("MeshPart") then
				p.TextureID = ""
			end
		end
		-- SurfaceAppearance from the importer renders blank in Play; keep the atlas on TextureID.
		local sa = p:FindFirstChildOfClass("SurfaceAppearance")
		if sa and p:IsA("MeshPart") then
			if not glow and sa.ColorMap ~= "" then
				p.TextureID = sa.ColorMap
			end
			sa:Destroy()
		end
		if p.Name == "Armory_Trees" then
			p.CastShadow = false
		end
		table.insert(report, p.Name .. " " .. tostring(p.Size))
	end
end

-- Warm lantern light, and a soft fill on the dais so any avatar reads against the hall.
local pivot = model:GetPivot()
local function light(name, offset, color, range, brightness, shadows)
	local p = Instance.new("Part")
	p.Name = name
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Transparency = 1
	p.Size = Vector3.new(0.2, 0.2, 0.2)
	p.CFrame = pivot * CFrame.new(offset)
	local l = Instance.new("PointLight")
	l.Color = color
	l.Range = range
	l.Brightness = brightness
	l.Shadows = shadows == true
	l.Parent = p
	p.Parent = model
end
-- Lanterns hang at Blender (+-3.9, 5.1, 6.5) -> Studio (-+3.9, 6.5, 5.1).
light("LanternLightL", Vector3.new(3.9, 6.5, 5.1), Color3.fromRGB(255, 199, 120), 14, 1.4)
light("LanternLightR", Vector3.new(-3.9, 6.5, 5.1), Color3.fromRGB(255, 199, 120), 14, 1.4)
light("DaisFill", Vector3.new(0, 4.5, -5), Color3.fromRGB(255, 244, 228), 16, 0.8)
light("DaisGlow", Vector3.new(0, 0.6, 0), Color3.fromRGB(145, 239, 20), 7, 0.6)

model.Name = "ArmoryBackdrop"
model:PivotTo(CFrame.new())
model.Parent = RS
return "installed ArmoryBackdrop ("
	.. #report
	.. " parts, scale fix "
	.. string.format("%.3f", factor)
	.. ")\n"
	.. table.concat(report, "\n")
