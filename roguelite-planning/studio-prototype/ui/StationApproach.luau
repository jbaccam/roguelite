-- Walk-up stands in the lobby: no E prompts. Each stand gets a glowing lime ring on the ground in
-- front of its counter and a floating icon + name above it so it is easy to find from across the
-- island. Stepping onto the ring opens the stand's window with a short camera push and fade;
-- the ring re-arms once the player steps off it, so closing the window while standing there sticks.
-- Client-only presentation; windows still go through LobbyUI's open() and the server checks.
local Players = game:GetService("Players")
local RS = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local T = require(RS:WaitForChild("UITheme"))
local A = {}

-- What each stand opens and how it is labelled (StationId -> route, icon, label).
A.Stands = {
	Workshop = { route = "Armory", icon = "armory", label = "ARMORY" },
	Collection = { route = "Loadout", icon = "loadout", label = "LOADOUT" },
	Rewards = { route = "Chests", icon = "chest", label = "CHESTS" },
	Store = { route = "Store", icon = "store", label = "STORE" },
	Quests = { route = "Quests", icon = "quests", label = "QUESTS" },
	Eggs = { route = "Eggs", label = "EGGS" }, -- icon: the stand's Icon attribute (the egg merchant)
}
local RING_RADIUS = 3.6 -- studs, drawn ring
local ENTER = 4.2 -- open when the player's feet are this close to the ring centre
local LEAVE = 7.5 -- re-arm after walking this far away
local AHEAD = 2.2 -- ring centre past the counter's front edge
local DASHES = 20
local LIME = Color3.fromRGB(145, 239, 20)

local function part(props)
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	for k, v in props do
		p[k] = v
	end
	return p
end

-- Ground height under a point (the lobby's walkable surfaces), falling back to `y`.
local function ground(at, ignore)
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = ignore
	local hit = workspace:Raycast(at + Vector3.new(0, 6, 0), Vector3.new(0, -20, 0), params)
	return hit and hit.Position.Y or at.Y - 3.5
end

-- Ring of dashes + soft glow disc + floating label for one stand. Returns its state.
local function dress(stand, info, folder)
	local inter = stand:FindFirstChild("Interaction", true)
	if not inter or not inter:IsA("BasePart") then
		return nil
	end
	local front = inter.CFrame.LookVector
	front = Vector3.new(front.X, 0, front.Z)
	front = front.Magnitude > 0.1 and front.Unit or Vector3.zAxis
	local centre = inter.Position + front * AHEAD
	local character = Players.LocalPlayer.Character
	local y = ground(centre, { folder, stand, character })
	centre = Vector3.new(centre.X, y + 0.06, centre.Z)

	local model = Instance.new("Model")
	model.Name = "Approach_" .. stand.Name
	local base = CFrame.new(centre)
	-- Soft lime glow on the ground (the store's radial glow texture).
	local disc = part({
		Name = "Glow",
		Size = Vector3.new(RING_RADIUS * 2.6, 0.05, RING_RADIUS * 2.6),
		Transparency = 1,
		CFrame = base,
	})
	local decal = Instance.new("Decal")
	decal.Face = Enum.NormalId.Top
	decal.Texture = "rbxassetid://101092695897243"
	decal.Color3 = LIME
	decal.Transparency = 0.45
	decal.Parent = disc
	disc.Parent = model
	-- Dashed Neon ring that slowly turns.
	local ring = Instance.new("Model")
	ring.Name = "Ring"
	for k = 1, DASHES do
		local a = 2 * math.pi * k / DASHES
		local len = 2 * math.pi * RING_RADIUS / DASHES * 0.55
		part({
			Name = "Dash",
			Material = Enum.Material.Neon,
			Color = LIME,
			Transparency = 0.15,
			Size = Vector3.new(len, 0.08, 0.28),
			CFrame = base * CFrame.Angles(0, -a, 0) * CFrame.new(0, 0, -RING_RADIUS),
			Parent = ring,
		})
	end
	ring.WorldPivot = base
	ring.Parent = model

	-- Floating icon + name above the stand, world-sized so it reads from across the island.
	local top = stand:GetPivot().Position.Y
	for _, d in stand:GetDescendants() do
		if d:IsA("BasePart") then
			top = math.max(top, d.Position.Y + d.Size.Y / 2)
		end
	end
	local anchor = part({ Name = "LabelAnchor", Size = Vector3.new(0.2, 0.2, 0.2), Transparency = 1 })
	anchor.CFrame = CFrame.new(Vector3.new(inter.Position.X, top + 3, inter.Position.Z) - front * 1.5)
	anchor.Parent = model
	local board = Instance.new("BillboardGui")
	board.Name = "StandLabel"
	board.Size = UDim2.fromScale(7, 3.6)
	board.LightInfluence = 0
	board.MaxDistance = 220
	board.ResetOnSpawn = false
	board.Adornee = anchor
	board.Parent = anchor
	local holder = T.frame(board, "Holder", 0, 0, 0, 0)
	holder.Size = UDim2.fromScale(1, 1)
	local icon = Instance.new("ImageLabel")
	icon.Name = "Icon"
	icon.BackgroundTransparency = 1
	icon.Image = T.Asset[info.icon] or ""
	if icon.Image == "" then
		icon.Image = stand:GetAttribute("Icon") or ""
	end
	icon.ScaleType = Enum.ScaleType.Fit
	icon.AnchorPoint = Vector2.new(0.5, 0)
	icon.Position = UDim2.fromScale(0.5, 0)
	icon.Size = UDim2.fromScale(0.62, 0.62)
	icon.Parent = holder
	local name = Instance.new("TextLabel")
	name.Name = "Name"
	name.BackgroundTransparency = 1
	name.Text = info.label
	name.Font = T.Font
	name.TextScaled = true
	name.TextColor3 = T.Color.white
	name.TextStrokeTransparency = 0.1
	name.AnchorPoint = Vector2.new(0.5, 1)
	name.Position = UDim2.fromScale(0.5, 1)
	name.Size = UDim2.fromScale(1, 0.36)
	name.Parent = holder
	model.Parent = folder
	return {
		stand = stand,
		info = info,
		centre = centre,
		ring = ring,
		decal = decal,
		anchor = anchor,
		base = base,
		armed = true,
		bobAt = anchor.CFrame,
	}
end

-- Quick "step in" transition: short camera push and a dip to dark while the window opens.
local fade
local function transition(openFn)
	if not fade then
		local gui = Instance.new("ScreenGui")
		gui.Name = "StationTransition"
		gui.IgnoreGuiInset = true
		gui.DisplayOrder = 90
		gui.ResetOnSpawn = false
		fade = Instance.new("Frame")
		fade.BorderSizePixel = 0
		fade.BackgroundColor3 = T.Color.shade
		fade.BackgroundTransparency = 1
		fade.Size = UDim2.fromScale(1, 1)
		fade.Parent = gui
		gui.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")
	end
	local quick = TweenInfo.new(0.14, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
	TweenService:Create(fade, quick, { BackgroundTransparency = 0.45 }):Play()
	-- FOV punch on the regular camera: always 70 -> 62 -> 70 (T.CAMERA_FOV), never from the FOV it
	-- finds. Starting from the current FOV ratcheted 70 -> 62 -> 54 when a chest, egg or Armory stage
	-- saved it mid-punch (2026-10-03). A stage taking the camera cancels the punch, and the punch back
	-- is skipped while one holds it.
	T.cameraFov(T.CAMERA_FOV - 8, quick)
	task.delay(0.12, function()
		local ok, err = pcall(openFn)
		if not ok then
			warn("StationApproach: open failed:", err)
		end
		local out = TweenInfo.new(0.28, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
		TweenService:Create(fade, out, { BackgroundTransparency = 1 }):Play()
		T.cameraFov(T.CAMERA_FOV, out)
	end)
end

-- opts: open(route) opens a lobby window; busy() is true while a window, run setup or queue is up.
function A.start(root, opts)
	local player = Players.LocalPlayer
	local stations = root:WaitForChild("Stations")
	local folder = Instance.new("Folder")
	folder.Name = "StationApproach"
	folder.Parent = workspace.CurrentCamera
	local stands = {}

	-- No E prompts on stands: walking up is the only way in (the HUD buttons still work).
	local function mute(d)
		if d:IsA("ProximityPrompt") and d.Name == "OpenStation" then
			d.Enabled = false
		end
	end
	for _, d in stations:GetDescendants() do
		mute(d)
	end
	stations.DescendantAdded:Connect(mute)

	local function build()
		-- Keep each stand's armed state so a rebuild never re-opens the stand you stand on.
		local wasArmed = {}
		for _, s in stands do
			wasArmed[s.stand] = s.armed
		end
		folder:ClearAllChildren()
		table.clear(stands)
		for _, stand in stations:GetChildren() do
			local info = A.Stands[stand:GetAttribute("StationId") or stand.Name]
			local s = info and dress(stand, info, folder)
			if s then
				if wasArmed[stand] ~= nil then
					s.armed = wasArmed[stand]
				end
				table.insert(stands, s)
			end
		end
	end
	build()
	-- The place streams: stands far from the player (e.g. while in the arena) have no parts yet.
	-- Rebuild shortly after any stand part streams in or out.
	local pending = false
	local function later(d)
		if pending or not d:IsA("BasePart") then
			return
		end
		pending = true
		task.delay(0.5, function()
			pending = false
			build()
		end)
	end
	stations.DescendantAdded:Connect(later)
	stations.DescendantRemoving:Connect(later)

	local last = 0
	RunService.RenderStepped:Connect(function()
		local now = os.clock()
		local hrp = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
		local hum = player.Character and player.Character:FindFirstChildOfClass("Humanoid")
		local busy = opts.busy()
		folder.Parent = opts.visible() and workspace.CurrentCamera or nil
		for _, s in stands do
			-- Idle motion: the ring turns, the label bobs.
			s.ring:PivotTo(s.base * CFrame.Angles(0, now * 0.6, 0))
			s.anchor.CFrame = s.bobAt + Vector3.new(0, math.sin(now * 2 + s.centre.X) * 0.25, 0)
			if not hrp or not hum then
				continue
			end
			local feet = hrp.Position - Vector3.new(0, hum.HipHeight + hrp.Size.Y / 2, 0)
			local flat = Vector3.new(feet.X - s.centre.X, 0, feet.Z - s.centre.Z).Magnitude
			local near = flat <= ENTER and math.abs(feet.Y - s.centre.Y) < 6
			s.decal.Transparency = near and 0.15 or 0.45
			if flat > LEAVE then
				s.armed = true
			elseif near and s.armed and not busy and now - last > 0.6 then
				s.armed = false
				last = now
				transition(function()
					opts.open(s.info.route)
				end)
			end
		end
	end)
	return { Rebuild = build }
end

return A
