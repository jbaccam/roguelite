-- Run-setup backdrop: the chosen map's mini island, blurred behind the map and class screens.
-- Client-only. Islands are cloned from ReplicatedStorage.MapSelectIslands (installed by
-- blender-map-mini-islands/studio-install-islands.luau) into the camera, side by side far from
-- the lobby, and seen from the approved Blender hero camera. The camera slides between them when
-- the map changes. A locked map's island becomes a near-black silhouette (a solid-fill
-- Highlight) against its hazy sky. Hide() gives the player their camera back.
local RS = game:GetService("ReplicatedStorage")
local Lighting = game:GetService("Lighting")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Players = game:GetService("Players")
local B = {}

local ORIGIN = Vector3.new(0, 420, -14000) -- far from the lobby and arena, low enough for the same sky haze
-- Studs between islands. The camera faces +Z, so screen-right is world -X: later maps sit
-- further along -X and > slides the view left to right.
local STEP = Vector3.new(-280, 0, 0)
-- Blender Cam_Hero (0,-118,34). The FBX importer turns the islands 180 degrees about Y, so the
-- front of each island faces -Z in Studio.
local HERO = Vector3.new(0, 34, -118)
local LOOK = Vector3.new(0, -7, 0)
local FOV = 32 -- Blender's 35 mm lens on a 36 mm sensor, vertical at 16:9
local SWAY, SWAY_PERIOD = math.rad(4), 14 -- slow drift so the world reads as alive
local SLIDE = 0.45
local BLUR = 12
-- Per-map colour grade, matching each island's preview sky.
local TINT = {
	PineValley = Color3.fromRGB(255, 255, 255),
	BeachCove = Color3.fromRGB(246, 252, 255),
	DesertBasin = Color3.fromRGB(255, 243, 224),
	FrozenPass = Color3.fromRGB(232, 242, 255),
	VolcanicCrater = Color3.fromRGB(255, 226, 212),
}
local SILHOUETTE = Color3.fromRGB(12, 14, 20)

local order = {} -- map ids in ladder order, set on first Show
local shadows = {} -- ladder index -> that island's silhouette Highlight
local stage, blur, grade, conn
local saved -- camera state before the backdrop took over
local shownMaps, shownLocked -- what Show was last given, to rebuild a lost stage
local slot, fromSlot, toSlot, slideStart = 1, 1, 1, 0

local function source()
	return RS:FindFirstChild("MapSelectIslands")
end

local function build(maps)
	local islands = source()
	if not islands then
		return false
	end
	if stage then
		return true
	end
	stage = Instance.new("Folder")
	stage.Name = "MapSelectBackdrop"
	for i, m in maps do
		order[i] = m.id
		local template = islands:FindFirstChild(m.id)
		if template then
			local island = template:Clone()
			island:PivotTo(CFrame.new(ORIGIN + STEP * (i - 1)))
			island.Parent = stage
			-- Flat fill over every part; the blur softens it into a silhouette. Transparent
			-- until the map is shown locked.
			local shadow = Instance.new("Highlight")
			shadow.Name = "LockedSilhouette"
			shadow.FillColor = SILHOUETTE
			shadow.FillTransparency = 1
			shadow.OutlineTransparency = 1
			shadow.DepthMode = Enum.HighlightDepthMode.Occluded
			shadow.Enabled = false -- only while the screen is open (Show/Hide)
			shadow.Adornee = island
			shadow.Parent = island
			shadows[i] = shadow
		end
	end
	return true
end

local keepStage

-- Clones the islands ahead of time (AssetPreloader) and parks them in the camera for good, so
-- the renderer keeps their meshes and textures. Parenting them on Show made parts of an island
-- appear a beat late. They sit 14000 studs from the lobby and arena, far outside either view.
function B.Prepare(maps)
	shownMaps = shownMaps or maps
	if not build(maps) then
		return false
	end
	keepStage(workspace.CurrentCamera)
	return true
end

-- One camera shot per island, for AssetPreloader's warm-up behind the loading screen.
function B.WarmViews()
	local out = {}
	for i in order do
		local center = ORIGIN + STEP * (i - 1)
		table.insert(out, { cframe = CFrame.lookAt(center + HERO, center + LOOK), fov = FOV })
	end
	return out
end

local function ease(t)
	return 1 - (1 - t) ^ 3
end

-- The hero framing is for 16:9. On narrower screens (16:10, 4:3 tablets) keep the same horizontal
-- view so the island's sides aren't cropped: 32 degrees vertical at 4:3 becomes about 42.
-- Same formula as ArmoryStage.FieldOfView.
local function fieldOfView(fov, viewport)
	local aspect = viewport.Y > 0 and viewport.X / viewport.Y or 16 / 9
	if aspect >= 16 / 9 then
		return fov
	end
	return 2 * math.deg(math.atan(math.tan(math.rad(fov / 2)) * (16 / 9) / aspect))
end

-- The islands live in the current camera. When the camera is replaced they move to the new one;
-- if they were destroyed with the old camera they are cloned again.
function keepStage(camera)
	if stage and stage.Parent == camera then
		return
	end
	if stage and pcall(function()
		stage.Parent = camera
	end) then
		return
	end
	stage = nil
	table.clear(shadows)
	if build(shownMaps) then
		stage.Parent = camera
		for _, shadow in shadows do
			shadow.Enabled = conn ~= nil
		end
		if shadows[toSlot] then
			shadows[toSlot].FillTransparency = shownLocked and 0 or 1
		end
	end
end

local function render()
	local camera = workspace.CurrentCamera
	keepStage(camera)
	local t = math.clamp((os.clock() - slideStart) / SLIDE, 0, 1)
	slot = fromSlot + (toSlot - fromSlot) * ease(t)
	local center = ORIGIN + STEP * (slot - 1)
	local yaw = math.sin(os.clock() * 2 * math.pi / SWAY_PERIOD) * SWAY
	local eye = center + CFrame.Angles(0, yaw, 0):VectorToWorldSpace(HERO)
	camera.CameraType = Enum.CameraType.Scriptable
	camera.FieldOfView = fieldOfView(FOV, camera.ViewportSize)
	camera.CFrame = CFrame.lookAt(eye, center + LOOK)
end

-- Shows `maps[index]` (RunSetupRules.Maps order). Returns false when the islands are not
-- installed; the caller then keeps a plain blur.
function B.Show(maps, index, locked)
	if not build(maps) then
		return false
	end
	local camera = workspace.CurrentCamera
	shownMaps, shownLocked = maps, locked
	if not conn then
		saved = { type = camera.CameraType, subject = camera.CameraSubject, fov = camera.FieldOfView }
		keepStage(camera)
		for _, shadow in shadows do
			shadow.Enabled = true
		end
		blur = Instance.new("BlurEffect")
		blur.Name = "MapSelectBlur"
		blur.Size = BLUR
		blur.Parent = Lighting
		grade = Instance.new("ColorCorrectionEffect")
		grade.Name = "MapSelectGrade"
		grade.Parent = Lighting
		fromSlot, toSlot, slideStart = index, index, 0
		conn = RunService.RenderStepped:Connect(render)
	elseif index ~= toSlot then
		fromSlot, toSlot, slideStart = slot, index, os.clock()
	end
	local goal = locked
			and { Saturation = -0.75, Brightness = -0.1, Contrast = 0, TintColor = Color3.fromRGB(196, 206, 224) }
		or { Saturation = 0.05, Brightness = 0, Contrast = 0.04, TintColor = TINT[maps[index].id] or Color3.new(1, 1, 1) }
	TweenService:Create(grade, TweenInfo.new(0.25), goal):Play()
	if shadows[index] then
		TweenService:Create(shadows[index], TweenInfo.new(0.25), { FillTransparency = locked and 0 or 1 }):Play()
	end
	render()
	return true
end

function B.Hide()
	if not conn then
		return
	end
	conn:Disconnect()
	conn = nil
	blur:Destroy()
	grade:Destroy()
	blur, grade = nil, nil
	-- The islands stay parked in the camera (see Prepare); a stage destroyed with its camera is
	-- rebuilt on the next Show. Highlights cost a pass every frame, so they go off.
	for _, shadow in shadows do
		shadow.Enabled = false
	end
	local camera = workspace.CurrentCamera
	local humanoid = Players.LocalPlayer.Character and Players.LocalPlayer.Character:FindFirstChildOfClass("Humanoid")
	camera.CameraSubject = humanoid or saved.subject
	camera.CameraType = saved.type == Enum.CameraType.Scriptable and Enum.CameraType.Custom or saved.type
	camera.FieldOfView = saved.fov
end

function B.IsShown()
	return conn ~= nil
end

return B
