-- Armory 3D stage: the timber armory hall (blender-armory-backdrop) behind the Armory screen.
-- Client-only. The hall is cloned from ReplicatedStorage.ArmoryBackdrop (installed by
-- blender-armory-backdrop/studio-install-armory.luau) into the camera, far from the lobby, next to
-- the map-select islands. The local player's avatar is copied onto the round dais, with their
-- starting weapon floating at their shoulder like in a run. The hall's racks, pegs, shelf, barrel
-- and anvil hold the game's real weapon models (WeaponTemplates, see DISPLAY). The upgrade view
-- swaps the avatar for the chosen weapon, spinning above the dais. Hide() gives the player their
-- camera back.
local RS = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Lighting = game:GetService("Lighting")
local PromptService = game:GetService("ProximityPromptService")
local S = {}

-- The hall's pivot is the dais top centre (the avatar's feet); its open front faces -Z, towards
-- the lobby sun. The camera stands on -Z looking +Z.
local ORIGIN = Vector3.new(1600, 420, -14000)
-- Camera presets, measured from the dais top centre (same as build_armory.py CAMERAS, Studio axes).
S.Views = {
	hero = { eye = Vector3.new(0, 3.3, -20.5), look = Vector3.new(0, 2.75, 0), fov = 30 },
	upgrade = { eye = Vector3.new(0, 3.9, -8.2), look = Vector3.new(0, 3.55, 0), fov = 30 },
}
-- Slow camera drift so the hall reads as a place, not a picture.
-- The lobby's bright, saturated grade blows out the pale stone dais up close; dim the scene a
-- little while the Armory is open (restored on Hide).
local EXPOSURE_DROP = 0.3
local DAIS_FILL = 0.35 -- installer default 0.8
local SWAY, SWAY_PERIOD = math.rad(1.6), 16
local BLEND = 0.55
local SHOWCASE_SIZE = 3.6 -- longest side of the showcased weapon, studs
local SHOWCASE_HEIGHT = 3.7 -- above the dais top
local SPIN = math.rad(38) -- degrees per second
local FLOAT_OFFSET = Vector3.new(-2.3, 3.6, 0.2) -- starting weapon beside the avatar (screen right)

-- Real weapon models on the hall's holders, from blender-armory-backdrop/build_armory.py DISPLAY
-- (armory-report.json weapon_slots_studio), relative to the dais top centre. `dir` is where the
-- model's long axis points (its tip for melee weapons, normalized to +Y), `len` its longest side
-- in studs. The flat side faces the camera unless `face` says otherwise; `up` keeps the model's
-- +Y upright for weapons whose long axis is X or Z (launcher, boomerang, box).
S.Display = {
	{ id = "03", at = Vector3.new(0, 5.9, 6.95), dir = Vector3.new(0.669, 0.743, 0), len = 7.4 },
	{ id = "06", at = Vector3.new(0, 5.9, 6.85), dir = Vector3.new(-0.669, 0.743, 0), len = 7 },
	{ id = "32", at = Vector3.new(7.5, 2.078, 6.47), dir = Vector3.new(0, 0.99, 0.139), len = 4.6 },
	{ id = "30", at = Vector3.new(8.7, 2.276, 6.498), dir = Vector3.new(0, 0.99, 0.139), len = 5 },
	{ id = "26", at = Vector3.new(9.85, 1.88, 6.442), dir = Vector3.new(0, 0.99, 0.139), len = 4.2 },
	{ id = "11", at = Vector3.new(-8.1, 6.5, 6.75), dir = Vector3.new(-1, 0, 0), len = 4, up = Vector3.new(0, 1, 0) },
	{ id = "01", at = Vector3.new(-10.9, 5.6, 7), dir = Vector3.new(0, -1, 0), len = 3.6 },
	{ id = "12", at = Vector3.new(-8.1, 3.55, 7.1), dir = Vector3.new(-1, 0, 0), len = 2.8, up = Vector3.new(0, 1, 0) },
	{ id = "35", at = Vector3.new(-10, 3.27, 6.9), dir = Vector3.new(0, 1, 0), len = 1.5 },
	{ id = "33", at = Vector3.new(-12, 3.27, 6.8), dir = Vector3.new(-1, 0, 0), len = 1.6, up = Vector3.new(0, 1, 0) },
	{ id = "06", at = Vector3.new(-11.65, 1, 3.25), dir = Vector3.new(-0.12, -0.99, -0.06), len = 3.8 },
	{ id = "03", at = Vector3.new(-12.2, 0.9, 3.05), dir = Vector3.new(0.1, -0.99, 0.1), len = 4.6 },
	{
		id = "31",
		at = Vector3.new(12.2, 2.03, 3),
		dir = Vector3.new(-0.94, 0, 0.342),
		len = 3,
		face = Vector3.new(0, 1, 0),
	},
}

local stage, avatar, avatarRoot, idleTrack, floater, showcase, conn
local saved
local view, fromView, blendStart = "hero", "hero", 0
local yaw = 0 -- avatar turntable (drag to spin)
local spinStart = os.clock()

local function source()
	return RS:FindFirstChild("ArmoryBackdrop")
end

local function stageCFrame()
	return CFrame.new(ORIGIN)
end

local function scrub(model)
	for _, d in model:GetDescendants() do
		if d:IsA("Script") or d:IsA("LocalScript") or d:IsA("Tool") or d:IsA("ForceField") then
			d:Destroy()
		elseif d:IsA("BasePart") then
			d.CanCollide = false
			d.CanQuery = false
			d.CanTouch = false
			d.Anchored = false
			d.CastShadow = true
		end
	end
end

-- A copy of the player's current look, standing on the dais facing the camera.
local function buildAvatar()
	if avatar then
		avatar:Destroy()
		avatar = nil
	end
	local character = Players.LocalPlayer.Character
	if not character or not character:FindFirstChildOfClass("Humanoid") then
		return
	end
	local was = character.Archivable
	character.Archivable = true
	local ok, copy = pcall(function()
		return character:Clone()
	end)
	character.Archivable = was
	if not ok or not copy then
		return
	end
	scrub(copy)
	-- Floating combat weapons are the run's; the stage places its own.
	for _, d in copy:GetChildren() do
		if d:IsA("Model") and d:GetAttribute("WeaponId") then
			d:Destroy()
		end
	end
	local humanoid = copy:FindFirstChildOfClass("Humanoid")
	local root = copy:FindFirstChild("HumanoidRootPart")
	if not humanoid or not root then
		copy:Destroy()
		return
	end
	humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	humanoid.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
	humanoid.BreakJointsOnDeath = false
	humanoid.RequiresNeck = false
	root.Anchored = true
	copy.Name = "ArmoryAvatar"
	copy.Parent = stage
	avatar, avatarRoot = copy, root
	-- Stand on the dais: root height = hip height + half the root part.
	local lift = humanoid.HipHeight + root.Size.Y / 2
	if humanoid.RigType == Enum.HumanoidRigType.R6 then
		lift = 3
	end
	avatar:SetAttribute("Lift", lift)
	local animator = humanoid:FindFirstChildOfClass("Animator") or Instance.new("Animator", humanoid)
	local animate = character:FindFirstChild("Animate")
	local idle = animate and animate:FindFirstChild("idle") and animate.idle:FindFirstChildOfClass("Animation")
	local anim = Instance.new("Animation")
	anim.AnimationId = idle and idle.AnimationId or "rbxassetid://507766666"
	local tOk, track = pcall(function()
		return animator:LoadAnimation(anim)
	end)
	if tOk and track then
		track.Looped = true
		track:Play(0)
		idleTrack = track
	end
end

local function template(weaponId)
	local combat = RS:FindFirstChild("RogueliteCombat")
	local templates = combat and combat:FindFirstChild("WeaponTemplates")
	return templates and weaponId and templates:FindFirstChild(weaponId)
end

-- Clone a weapon template as an anchored, scaled display model centred on its bounding box.
local function display(weaponId, size)
	local t = template(weaponId)
	if not t then
		return nil
	end
	local m = t:Clone()
	for _, d in m:GetDescendants() do
		if d:IsA("Script") or d:IsA("LocalScript") then
			d:Destroy()
		elseif d:IsA("BasePart") then
			d.Anchored = true
			d.CanCollide = false
			d.CanQuery = false
			d.CanTouch = false
		elseif d:IsA("ParticleEmitter") or d:IsA("Trail") or d:IsA("Beam") then
			d.Enabled = false
		end
	end
	if not m:IsA("Model") then
		local wrap = Instance.new("Model")
		m.Parent = wrap
		m = wrap
	end
	-- BoundsSize/BoundsCenter are the tight bounds in the pivot frame (tip on +Y for normalized
	-- weapons). GetBoundingBox is inflated for meshes authored on a diagonal.
	local extents = t:GetAttribute("BoundsSize")
	local centre = t:GetAttribute("BoundsCenter") or Vector3.zero
	local pivot = m:GetPivot()
	if typeof(extents) ~= "Vector3" then
		local box
		box, extents = m:GetBoundingBox()
		centre = pivot:PointToObjectSpace(box.Position)
	end
	m.WorldPivot = pivot * CFrame.new(centre)
	local longest = math.max(extents.X, extents.Y, extents.Z)
	if longest > 0 then
		m:ScaleTo(m:GetScale() * size / longest)
	end
	m:SetAttribute("DisplayExtents", extents)
	m.Name = "Display_" .. weaponId
	return m
end

-- Rotation that points a display model's long axis along `slot.dir` (see S.Display).
local AXES = { X = Vector3.xAxis, Y = Vector3.yAxis, Z = Vector3.zAxis }
local function slotRotation(extents, slot)
	local dir = slot.dir.Unit
	local sizes = { X = extents.X, Y = extents.Y, Z = extents.Z }
	local long = "Y"
	for axis, v in sizes do
		if v > sizes[long] + 1e-3 then
			long = axis
		end
	end
	local world = {}
	-- Long axis: +Y tips and +X, but -Z (LookVector) for guns built along Z.
	world[long] = long == "Z" and -dir or dir
	local second, secondDir
	if long == "Y" then
		-- The thinner of X/Z is the flat side; it faces the camera (-Z) unless told otherwise.
		second = sizes.X <= sizes.Z and "X" or "Z"
		secondDir = slot.face or Vector3.new(0, 0, -1)
	else
		second = "Y"
		secondDir = slot.up or Vector3.yAxis
	end
	secondDir = (secondDir - dir * secondDir:Dot(dir)).Unit
	-- The flat side's +axis faces the camera: some blades are one-sided planes facing +Z.
	world[second] = secondDir
	-- Right-handed completion of the third axis.
	if not world.X then
		world.X = world.Y:Cross(world.Z)
	elseif not world.Y then
		world.Y = world.Z:Cross(world.X)
	else
		world.Z = world.X:Cross(world.Y)
	end
	return CFrame.fromMatrix(Vector3.zero, world.X, world.Y, world.Z)
end
S.SlotRotation = slotRotation -- exposed for layout tests

-- Hang the real weapon models on the hall's holders.
local function dress(hall)
	local folder = Instance.new("Folder")
	folder.Name = "DisplayWeapons"
	folder.Parent = hall
	for i, slot in S.Display do
		local m = display(slot.id, slot.len)
		if m then
			m.Name = string.format("Display%02d_%s", i, slot.id)
			m:PivotTo(stageCFrame() * CFrame.new(slot.at) * slotRotation(m:GetAttribute("DisplayExtents"), slot))
			m.Parent = folder
		end
	end
end

local function glowPart(parent, color)
	local p = Instance.new("Part")
	p.Name = "ShowcaseGlow"
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Transparency = 1
	p.Size = Vector3.new(0.2, 0.2, 0.2)
	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = 12
	light.Brightness = 1.6
	light.Parent = p
	local sparks = Instance.new("ParticleEmitter")
	sparks.Name = "Motes"
	sparks.Texture = "rbxasset://textures/particles/sparkles_main.dds"
	sparks.Color = ColorSequence.new(color)
	sparks.LightEmission = 0.8
	sparks.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.25), NumberSequenceKeypoint.new(1, 0) })
	sparks.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(1, 1) })
	sparks.Lifetime = NumberRange.new(1.2, 2)
	sparks.Rate = 10
	sparks.Speed = NumberRange.new(0.6, 1.4)
	sparks.SpreadAngle = Vector2.new(180, 180)
	sparks.Parent = p
	p.Parent = parent
	return p, light, sparks
end

local function ease(t)
	return 1 - (1 - t) ^ 3
end

local function camCFrame(name)
	local v = S.Views[name]
	local base = stageCFrame()
	return base:PointToWorldSpace(v.eye), base:PointToWorldSpace(v.look), v.fov
end

local function render()
	local camera = workspace.CurrentCamera
	local now = os.clock()
	local t = ease(math.clamp((now - blendStart) / BLEND, 0, 1))
	local e0, l0, f0 = camCFrame(fromView)
	local e1, l1, f1 = camCFrame(view)
	local eye, look = e0:Lerp(e1, t), l0:Lerp(l1, t)
	-- Slow drift so the hall reads as a place, not a picture.
	local sway = math.sin(now * 2 * math.pi / SWAY_PERIOD) * SWAY
	local centre = stageCFrame().Position
	eye = centre + CFrame.Angles(0, sway, 0):VectorToWorldSpace(eye - centre)
	camera.CameraType = Enum.CameraType.Scriptable
	camera.FieldOfView = f0 + (f1 - f0) * t
	camera.CFrame = CFrame.lookAt(eye, look)

	local base = stageCFrame()
	if avatarRoot and avatar and avatar.Parent then
		local lift = avatar:GetAttribute("Lift") or 3
		-- An unrotated root looks down -Z, i.e. at the camera.
		avatarRoot.CFrame = base * CFrame.new(0, lift, 0) * CFrame.Angles(0, yaw, 0)
	end
	if floater and floater.Parent then
		local bob = math.sin(now * 2.2) * 0.18
		local side = base * CFrame.Angles(0, yaw, 0) * CFrame.new(FLOAT_OFFSET + Vector3.new(0, bob, 0))
		floater:PivotTo(side * CFrame.Angles(0, math.pi * 0.5 + math.sin(now * 0.9) * 0.3, math.rad(-20)))
	end
	if showcase and showcase.Parent then
		local bob = math.sin(now * 1.8) * 0.15
		local ang = (now - spinStart) * SPIN
		showcase:PivotTo(
			base * CFrame.new(0, SHOWCASE_HEIGHT + bob, 0) * CFrame.Angles(math.rad(-8), ang, math.rad(12))
		)
		local glow = stage:FindFirstChild("ShowcaseGlow")
		if glow then
			glow.CFrame = base * CFrame.new(0, SHOWCASE_HEIGHT, -1.2)
		end
	end
end

-- Clones the hall ahead of time (AssetPreloader) so the first Show has nothing to build.
function S.Prepare()
	if stage then
		return true
	end
	local hall = source()
	if not hall then
		return false
	end
	stage = Instance.new("Folder")
	stage.Name = "ArmoryStage"
	local copy = hall:Clone()
	copy:PivotTo(stageCFrame())
	copy.Parent = stage
	for _, name in { "DaisFill", "DaisGlow" } do
		local holder = copy:FindFirstChild(name)
		local light = holder and holder:FindFirstChildOfClass("PointLight")
		if light then
			light.Brightness = name == "DaisFill" and DAIS_FILL or 0.35
		end
	end
	dress(copy)
	return true
end

function S.Available()
	return source() ~= nil
end

-- weaponId: the starting weapon floating beside the avatar (optional).
function S.Show(weaponId)
	if not S.Prepare() then
		return false
	end
	local camera = workspace.CurrentCamera
	if not conn then
		saved = {
			type = camera.CameraType,
			subject = camera.CameraSubject,
			fov = camera.FieldOfView,
			exposure = Lighting.ExposureCompensation,
			prompts = PromptService.Enabled,
		}
		-- World prompts (lobby stands) must not draw over the Armory.
		PromptService.Enabled = false
		TweenService:Create(Lighting, TweenInfo.new(0.3), { ExposureCompensation = saved.exposure - EXPOSURE_DROP })
			:Play()
		stage.Parent = camera
		view, fromView, blendStart, yaw = "hero", "hero", 0, 0
		buildAvatar()
		conn = RunService.RenderStepped:Connect(render)
	end
	S.SetStarter(weaponId)
	render()
	return true
end

function S.SetStarter(weaponId)
	if floater and floater:GetAttribute("WeaponId") == weaponId then
		return
	end
	if floater then
		floater:Destroy()
		floater = nil
	end
	if not stage or not weaponId then
		return
	end
	floater = display(weaponId, 2.4)
	if floater then
		floater:SetAttribute("WeaponId", weaponId)
		floater.Parent = stage
	end
end

local function setAvatarVisible(on)
	if not avatar then
		return
	end
	for _, d in avatar:GetDescendants() do
		if d:IsA("BasePart") or d:IsA("Decal") then
			local base = d:GetAttribute("ArmoryBase")
			if base == nil then
				base = d.Transparency
				d:SetAttribute("ArmoryBase", base)
			end
			if d.Name ~= "HumanoidRootPart" then
				d.Transparency = on and base or 1
			end
		end
	end
end

-- "hero" (avatar on the dais) or "upgrade" (weaponId spinning above the dais).
function S.SetView(name, weaponId, tierColor)
	if not conn then
		return
	end
	local keep = name == "upgrade" and showcase and showcase:GetAttribute("WeaponId") == weaponId
	if showcase and not keep then
		showcase:Destroy()
		showcase = nil
	end
	local glow = stage:FindFirstChild("ShowcaseGlow")
	if glow then
		glow:Destroy()
	end
	if name == "upgrade" and weaponId then
		if not keep then
			showcase = display(weaponId, SHOWCASE_SIZE)
			if showcase then
				showcase:SetAttribute("WeaponId", weaponId)
				showcase.Parent = stage
				spinStart = os.clock()
			end
		end
		glowPart(stage, tierColor or Color3.fromRGB(145, 239, 20))
	end
	setAvatarVisible(name ~= "upgrade")
	if floater then
		for _, d in floater:GetDescendants() do
			if d:IsA("BasePart") then
				d.LocalTransparencyModifier = name == "upgrade" and 1 or 0
			end
		end
	end
	if name ~= view then
		fromView, view, blendStart = view, name, os.clock()
	end
end

-- Upgrade celebration: a ring of light and a burst of motes in the new tier's colour.
function S.Burst(color)
	if not stage or not conn then
		return
	end
	local at = stageCFrame() * CFrame.new(0, view == "upgrade" and SHOWCASE_HEIGHT or 3, 0)
	local p = Instance.new("Part")
	p.Name = "UpgradeBurst"
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Transparency = 1
	p.Size = Vector3.new(0.2, 0.2, 0.2)
	p.CFrame = at
	p.Parent = stage
	local e = Instance.new("ParticleEmitter")
	e.Texture = "rbxasset://textures/particles/sparkles_main.dds"
	e.Color = ColorSequence.new(color)
	e.LightEmission = 1
	e.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.6), NumberSequenceKeypoint.new(1, 0) })
	e.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(1, 1) })
	e.Lifetime = NumberRange.new(0.6, 1.1)
	e.Speed = NumberRange.new(8, 14)
	e.Drag = 4
	e.SpreadAngle = Vector2.new(180, 180)
	e.Rate = 0
	e.Parent = p
	e:Emit(70)
	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = 18
	light.Brightness = 6
	light.Parent = p
	TweenService:Create(light, TweenInfo.new(0.9, Enum.EasingStyle.Quad), { Brightness = 0 }):Play()
	-- Expanding flat ring over the dais.
	local ring = Instance.new("Part")
	ring.Name = "BurstRing"
	ring.Shape = Enum.PartType.Cylinder
	ring.Material = Enum.Material.Neon
	ring.Color = color
	ring.Anchored = true
	ring.CanCollide = false
	ring.CanQuery = false
	ring.CanTouch = false
	ring.Size = Vector3.new(0.08, 2, 2)
	ring.CFrame = stageCFrame() * CFrame.new(0, 0.1, 0) * CFrame.Angles(0, 0, math.pi / 2)
	ring.Transparency = 0.1
	ring.Parent = stage
	TweenService
		:Create(ring, TweenInfo.new(0.7, Enum.EasingStyle.Quad), { Size = Vector3.new(0.08, 11, 11), Transparency = 1 })
		:Play()
	task.delay(1.5, function()
		p:Destroy()
		ring:Destroy()
	end)
	if showcase then
		spinStart -= 0.8 -- a quick extra spin
	end
end

-- Turntable: drag horizontally on empty screen space to turn the avatar.
function S.Turn(deltaRadians)
	yaw = (yaw + deltaRadians) % (2 * math.pi)
end

function S.Hide()
	if not conn then
		return
	end
	conn:Disconnect()
	conn = nil
	if idleTrack then
		idleTrack:Stop(0)
		idleTrack = nil
	end
	for _, v in { avatar, floater, showcase } do
		if v then
			v:Destroy()
		end
	end
	avatar, avatarRoot, floater, showcase = nil, nil, nil, nil
	local glow = stage:FindFirstChild("ShowcaseGlow")
	if glow then
		glow:Destroy()
	end
	stage.Parent = nil
	local camera = workspace.CurrentCamera
	local humanoid = Players.LocalPlayer.Character and Players.LocalPlayer.Character:FindFirstChildOfClass("Humanoid")
	camera.CameraSubject = humanoid or saved.subject
	camera.CameraType = saved.type == Enum.CameraType.Scriptable and Enum.CameraType.Custom or saved.type
	camera.FieldOfView = saved.fov
	Lighting.ExposureCompensation = saved.exposure
	PromptService.Enabled = saved.prompts
end

function S.IsShown()
	return conn ~= nil
end

return S
