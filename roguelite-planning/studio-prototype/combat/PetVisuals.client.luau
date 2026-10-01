-- Pet followers and pet VFX, client only (RARITY_GODLY_ARMOR.md step 6). Studio:
-- StarterPlayer.StarterPlayerScripts.PetVisuals, a LocalScript (unsandboxed).
--
-- For every Folder in workspace.RoguelitePets (PetService: attributes PetId, Tier, OwnerUserId) it
-- clones ReplicatedStorage.PetModels[PetId] into a local Model and drives its anchored parts by
-- CFrame every frame (no physics, no Motor6D): each part's world CFrame comes from its rest offset,
-- its parent chain and the per-joint rotation about the pivot from PetRigs (RS.RogueliteCombat).
-- The pet follows its owner (about 4 studs behind, 2.5 to the side) on a spring, faces where it
-- travels, sits on the ground (+hover for flyers) and teleports when more than 60 studs behind.
-- It blends the idle and move clips by its real speed and plays its action clip, with a short
-- dash, on each PetFX event. Effects are built from code, capped, and cleaned up with Debris.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local RS = game:GetService("ReplicatedStorage")
local Debris = game:GetService("Debris")
local TweenService = game:GetService("TweenService")
local combat = RS:WaitForChild("RogueliteCombat")
local Pets = require(combat:WaitForChild("PetConfig"))

local TELEPORT = 60
local BEHIND, SIDE = 4, 2.5
local MAX_EFFECTS = 40 -- transient effect parts/emitters alive at once
local DRAW_RANGE = 250 -- pets farther than this from the camera keep following but skip posing
local AMBER = Color3.fromRGB(255, 178, 74)
local TEX = {
	sparkle = "rbxasset://textures/particles/sparkles_main.dds",
	fire = "rbxasset://textures/particles/fire_main.dds",
	smoke = "rbxasset://textures/particles/smoke_main.dds",
}

local holder = Instance.new("Folder")
holder.Name = "RoguelitePetsLocal"
holder.Parent = workspace

-- PetRigs is required lazily: it may arrive after this script starts.
local Rigs
local function rigs()
	if Rigs == nil then
		local m = combat:FindFirstChild("PetRigs")
		if m then
			local ok, r = pcall(require, m)
			Rigs = ok and r or false
			if not ok then
				warn("PetVisuals: PetRigs failed to load", r)
			end
		end
	end
	return Rigs or nil
end

-- Small helpers ---------------------------------------------------------------------------------
local function v3(t, default)
	if typeof(t) == "Vector3" then
		return t
	end
	if type(t) == "table" then
		return Vector3.new(t[1] or t.x or t.X or 0, t[2] or t.y or t.Y or 0, t[3] or t.z or t.Z or 0)
	end
	return default or Vector3.zero
end
local function rgb(t, default)
	if typeof(t) == "Color3" then
		return t
	end
	if type(t) == "table" and type(t[1]) == "number" then
		return Color3.fromRGB(t[1], t[2], t[3])
	end
	return default
end
local function smooth(x)
	x = math.clamp(x, 0, 1)
	return x * x * (3 - 2 * x)
end
local function flat(v)
	return Vector3.new(v.X, 0, v.Z)
end
local active = 0
-- Reserve room for a transient effect that lives `life` seconds; false when the cap is reached.
local function budget(life)
	if active >= MAX_EFFECTS then
		return false
	end
	active += 1
	task.delay(life, function()
		active -= 1
	end)
	return true
end
local function part(props)
	local p = Instance.new("Part")
	p.Anchored, p.CanCollide, p.CanQuery, p.CanTouch, p.CastShadow = true, false, false, false, false
	p.TopSurface, p.BottomSurface = Enum.SurfaceType.Smooth, Enum.SurfaceType.Smooth
	for k, v in props do
		p[k] = v
	end
	return p
end
local function temp(inst, life)
	inst.Parent = inst.Parent or holder
	Debris:AddItem(inst, life)
	return inst
end
local function tween(inst, time, goal, style)
	local t =
		TweenService:Create(inst, TweenInfo.new(time, style or Enum.EasingStyle.Quad, Enum.EasingDirection.Out), goal)
	t:Play()
	return t
end
-- "0.25 -> 0.85 (t 0.4) -> 1.3", "NumberSequence 0:0.10, 0.4:0.14, 1:0", a number or {a, b}.
local function numberSeq(v, default)
	if type(v) == "number" then
		return NumberSequence.new(v)
	end
	if type(v) == "table" and type(v[1]) == "number" then
		return NumberSequence.new(v[1], v[2] or v[1])
	end
	if type(v) == "string" then
		local ok, seq = pcall(function()
			local keys = {}
			if v:find(":") then
				for t, x in v:gmatch("([%d%.]+)%s*:%s*([%-%d%.]+)") do
					table.insert(keys, NumberSequenceKeypoint.new(tonumber(t), tonumber(x)))
				end
			else
				local parts = string.split(v, "->")
				for i, s in parts do
					local x = tonumber(s:match("[%-%d%.]+"))
					local t = tonumber(s:match("%(t%s*([%d%.]+)%)")) or (i - 1) / math.max(1, #parts - 1)
					table.insert(keys, NumberSequenceKeypoint.new(t, x))
				end
			end
			keys[1] = NumberSequenceKeypoint.new(0, keys[1].Value)
			keys[#keys] = NumberSequenceKeypoint.new(1, keys[#keys].Value)
			return NumberSequence.new(keys)
		end)
		if ok then
			return seq
		end
	end
	return default
end
local function colorSeq(entry, default)
	if type(entry.colour_sequence) == "table" then
		local ok, seq = pcall(function()
			local keys = {}
			for _, k in entry.colour_sequence do
				table.insert(keys, ColorSequenceKeypoint.new(k[1], rgb(k[2])))
			end
			return ColorSequence.new(keys)
		end)
		if ok then
			return seq
		end
	end
	local c = rgb(entry.color or entry.colour_rgb or entry.colour)
	return c and ColorSequence.new(c) or default
end
-- A ParticleEmitter from a PetRigs vfx entry's `suggested` values, with safe defaults.
local function emitter(parent, entry, defaults)
	local s = type(entry.suggested) == "table" and entry.suggested or {}
	local e = Instance.new("ParticleEmitter")
	e.Texture = defaults.texture or TEX.sparkle
	e.Rate = type(s.Rate) == "number" and s.Rate or defaults.rate or 4
	local life = type(s.Lifetime) == "table" and s.Lifetime or defaults.life or { 0.5, 0.9 }
	e.Lifetime = NumberRange.new(life[1], life[2] or life[1])
	local speed = type(s.Speed) == "table" and s.Speed or defaults.speed or { 0.2, 0.5 }
	e.Speed = NumberRange.new(speed[1], speed[2] or speed[1])
	local spread = type(s.SpreadAngle) == "table" and s.SpreadAngle or defaults.spread or { 180, 180 }
	e.SpreadAngle = Vector2.new(spread[1], spread[2] or spread[1])
	e.Acceleration = v3(s.Acceleration, defaults.accel or Vector3.zero)
	e.Drag = type(s.Drag) == "number" and s.Drag or 0
	e.LightEmission = type(s.LightEmission) == "number" and s.LightEmission or 0.8
	e.LightInfluence = type(s.LightInfluence) == "number" and s.LightInfluence or 0
	e.Size = numberSeq(s.Size, defaults.size or NumberSequence.new(0.12, 0))
	e.Transparency = numberSeq(s.Transparency, NumberSequence.new(0.1, 1))
	e.Color = colorSeq(entry, defaults.color or ColorSequence.new(Color3.new(1, 1, 1)))
	e.Rotation = NumberRange.new(0, 360)
	e.RotSpeed = NumberRange.new(-90, 90)
	e.LockedToPart = false
	e.Parent = parent
	return e
end

-- Rig math ---------------------------------------------------------------------------------------
-- Interpolated pose of one clip at u (0-1 along it) into acc with weight w.
local function addClip(acc, clip, u, w)
	if not clip or w <= 0.001 then
		return
	end
	local frames = clip.frames
	local n = frames and #frames or 0
	if n == 0 then
		return
	end
	local a, b, alpha = frames[1], frames[1], 0
	if n > 1 then
		local loop = clip.loop ~= false
		local function t(i)
			return frames[i].t or (i - 1) / (loop and n or (n - 1))
		end
		if u >= t(n) then
			if loop then
				a, b = frames[n], frames[1]
				alpha = (u - t(n)) / math.max(1e-3, 1 - t(n))
			else
				a, b = frames[n], frames[n]
			end
		elseif u <= t(1) then
			a, b = frames[1], frames[1]
		else
			for i = 1, n - 1 do
				if u >= t(i) and u < t(i + 1) then
					a, b = frames[i], frames[i + 1]
					alpha = (u - t(i)) / math.max(1e-3, t(i + 1) - t(i))
					break
				end
			end
		end
	end
	alpha = (1 - math.cos(math.clamp(alpha, 0, 1) * math.pi)) / 2 -- sine ease
	local function mix(field)
		return ((a[field] or 0) * (1 - alpha) + (b[field] or 0) * alpha) * w
	end
	acc.lift += mix("lift")
	acc.pitch += mix("pitch")
	acc.roll += mix("roll")
	acc.yaw += mix("yaw")
	if clip.grounded then
		acc.grounded += w -- lift is from the ground here, not from the hover height
	end
	local function add(f, k)
		if k <= 0 then
			return
		end
		for name, j in f.joints or {} do
			acc.joints[name] = (acc.joints[name] or Vector3.zero) + v3(j) * k
		end
		for name, o in f.offsets or {} do
			acc.offsets[name] = (acc.offsets[name] or Vector3.zero) + v3(o) * k
		end
	end
	add(a, (1 - alpha) * w)
	add(b, alpha * w)
end

-- Pets -------------------------------------------------------------------------------------------
local entries = {} -- folder -> entry
local byOwner = {} -- userId -> entry
local shields = {} -- userId -> {part, ends}
local exclude, excludeAt = {}, 0
local rayParams = RaycastParams.new()
rayParams.FilterType = Enum.RaycastFilterType.Exclude
rayParams.RespectCanCollide = true
local function refreshExclude(now)
	if now - excludeAt < 1 then
		return
	end
	excludeAt = now
	exclude = { holder }
	for _, name in { "RogueliteEnemies", "RoguelitePets", "RogueliteShardDrops" } do
		local f = workspace:FindFirstChild(name)
		if f then
			table.insert(exclude, f)
		end
	end
	for _, p in Players:GetPlayers() do
		if p.Character then
			table.insert(exclude, p.Character)
		end
	end
	rayParams.FilterDescendantsInstances = exclude
end
local function groundY(position, fallback)
	local hit = workspace:Raycast(position + Vector3.new(0, 4, 0), Vector3.new(0, -40, 0), rayParams)
	return hit and hit.Position.Y or fallback
end

local function clearEntry(entry)
	if entry.model then
		entry.model:Destroy()
	end
	for _, inst in entry.extras do
		if typeof(inst) == "Instance" then
			inst:Destroy()
		end
	end
	if entry.reticle then
		entry.reticle.gui:Destroy()
	end
	if byOwner[entry.ownerId] == entry then
		byOwner[entry.ownerId] = nil
	end
end

-- Attachment on a pet part at a model-space (rest) position.
local function attachAt(entry, partName, modelPos)
	local rec = entry.parts[partName] or entry.parts[entry.rootName]
	if not rec then
		return
	end
	local a = Instance.new("Attachment")
	a.Position = rec.rest:PointToObjectSpace(modelPos or rec.rest.Position)
	a.Parent = rec.part
	return a
end
local function pivotOf(entry, partName)
	local data = entry.rig and entry.rig.parts and entry.rig.parts[partName]
	return data and v3(data.pivot) or (entry.parts[partName] and entry.parts[partName].rest.Position) or Vector3.zero
end
local function vfxFind(entry, ...)
	local list = entry.rig and entry.rig.vfx
	if type(list) ~= "table" then
		return nil
	end
	for key, e in list do
		if type(e) == "table" then
			local tag = string.lower(tostring(key) .. " " .. tostring(e.kind or "") .. " " .. tostring(e.name or ""))
			for _, word in { ... } do
				if tag:find(word, 1, true) then
					return e
				end
			end
		end
	end
end
-- Always-on Epic / Legendary ambience from PetRigs.vfx.
local function ambience(entry)
	local id = entry.id
	if id == "LuckyCat" then
		local e = vfxFind(entry, "coinsparkle", "coin") or {}
		local partName = e.part or "LuckyCat_Coin"
		local a = attachAt(entry, partName, pivotOf(entry, partName) + v3(e.offset))
		if a then
			emitter(a, e, { rate = 3, color = ColorSequence.new(Color3.fromRGB(255, 214, 120)) })
		end
	elseif id == "Owl" then
		local e = vfxFind(entry, "neon_pulse", "reticle") or {}
		local rec = entry.parts[e.part or "Owl_Reticle_Glow"]
		entry.pulse = rec and rec.part
	elseif id == "CheetahCub" then
		local e = vfxFind(entry, "speedtrail", "trail") or {}
		local partName = e.part or "CheetahCub_Scarf"
		local pv = pivotOf(entry, partName)
		local a0 = attachAt(entry, partName, pv + v3(e.offset0, Vector3.new(0, 0.35, 1.25)))
		local a1 = attachAt(entry, partName, pv + v3(e.offset1, Vector3.new(0.12, 0.25, 1.28)))
		if a0 and a1 then
			local tr = Instance.new("Trail")
			tr.Attachment0, tr.Attachment1 = a0, a1
			tr.Lifetime, tr.MinLength, tr.FaceCamera = 0.22, 0.05, true
			tr.LightEmission, tr.LightInfluence = 0.7, 0
			tr.Transparency = NumberSequence.new(0.55, 1)
			tr.WidthScale = NumberSequence.new(1, 0.2)
			tr.Color = ColorSequence.new(Color3.fromRGB(150, 230, 255), Color3.fromRGB(70, 170, 240))
			tr.Enabled = false
			tr.Parent = a0.Parent
			entry.runTrail = tr
		end
	elseif id == "BabyDragon" then
		local embers = vfxFind(entry, "ambient_embers", "ember") or {}
		local fireColor = ColorSequence.new({
			ColorSequenceKeypoint.new(0, Color3.fromRGB(255, 222, 130)),
			ColorSequenceKeypoint.new(0.5, Color3.fromRGB(255, 146, 50)),
			ColorSequenceKeypoint.new(1, Color3.fromRGB(220, 70, 40)),
		})
		for _, partName in embers.parts or { entry.rootName } do
			local at = embers.attachments and embers.attachments[partName]
			local a = attachAt(entry, partName, at and v3(at.position) or nil)
			if a then
				emitter(a, embers, { rate = 2.5, life = { 1.2, 1.8 }, accel = Vector3.new(0, 1, 0), color = fireColor })
			end
		end
		local trail = vfxFind(entry, "flight_trail") or {}
		entry.glide = {}
		for partName, list in trail.attachment_positions or {} do
			for _, pos in list do
				local a = attachAt(entry, partName, v3(pos))
				if a then
					local em = emitter(a, trail, { rate = 10, life = { 0.3, 0.45 }, color = fireColor })
					em.Enabled = false
					table.insert(entry.glide, em)
				end
			end
		end
	end
end

local function build(entry)
	local models = RS:FindFirstChild("PetModels")
	local template = models and models:FindFirstChild(entry.id)
	if not template then
		return false
	end
	local all = rigs()
	entry.rig = all and all[entry.id] or nil
	local rig = entry.rig or {}
	local model = Instance.new("Model")
	model.Name = "Pet_" .. entry.ownerId .. "_" .. entry.id
	local pivot = template:GetPivot()
	entry.parts, entry.order = {}, {}
	for _, src in template:GetDescendants() do
		if src:IsA("BasePart") then
			local p = src:Clone()
			for _, c in p:GetChildren() do
				if c:IsA("JointInstance") or c:IsA("Constraint") or c:IsA("LuaSourceContainer") then
					c:Destroy()
				end
			end
			p.Anchored, p.CanCollide, p.CanQuery, p.CanTouch, p.Massless = true, false, false, false, true
			p.Parent = model
			entry.parts[p.Name] = { part = p, rest = pivot:ToObjectSpace(src.CFrame) }
		end
	end
	entry.rootName = rig.root
	if not entry.parts[entry.rootName or ""] then
		entry.rootName = next(entry.parts)
	end
	-- Parents before children, so each joint can build on its parent's transform.
	local function depth(name)
		local d, cur = 0, name
		while rig.parts and rig.parts[cur] and rig.parts[cur].parent and d < 20 do
			cur = rig.parts[cur].parent
			d += 1
		end
		return d
	end
	for name, rec in entry.parts do
		local data = rig.parts and rig.parts[name]
		rec.pivot = data and v3(data.pivot) or rec.rest.Position
		rec.parentName = data and data.parent
		rec.depth = depth(name)
		table.insert(entry.order, name)
	end
	table.sort(entry.order, function(a, b)
		return entry.parts[a].depth < entry.parts[b].depth
	end)
	entry.list = {}
	for i, name in entry.order do
		entry.list[i] = entry.parts[name].part
	end
	entry.hover = rig.hover or 0
	entry.flyer = entry.hover > 0 or rig.locomotion == "fly" or rig.locomotion == "hover"
	entry.model = model
	ambience(entry)
	model.Parent = holder
	return true
end

local function newEntry(folder)
	local id = folder:GetAttribute("PetId")
	local ownerId = folder:GetAttribute("OwnerUserId") or tonumber(folder.Name)
	if not Pets.valid(id) or type(ownerId) ~= "number" then
		return nil
	end
	local entry = {
		folder = folder,
		id = id,
		tier = folder:GetAttribute("Tier") or 1,
		ownerId = ownerId,
		extras = {},
		retryAt = 0,
		pos = nil,
		vel = Vector3.zero,
		dir = Vector3.new(0, 0, -1),
		speed = 0,
		movePhase = 0,
		idlePhase = math.random(),
		actionWeight = 0,
		idleTime = 0,
		nextBeckon = os.clock() + math.random(6, 12),
		groundAt = 0,
		gy = nil,
	}
	byOwner[ownerId] = entry
	return entry
end

local function track(folder)
	if not folder:IsA("Folder") then
		return
	end
	local function refresh()
		local old = entries[folder]
		local id = folder:GetAttribute("PetId")
		if old and old.id == id then
			old.tier = folder:GetAttribute("Tier") or old.tier
			return
		end
		if old then
			clearEntry(old)
			entries[folder] = nil
		end
		entries[folder] = newEntry(folder)
	end
	folder:GetAttributeChangedSignal("PetId"):Connect(refresh)
	folder:GetAttributeChangedSignal("Tier"):Connect(refresh)
	refresh()
end
local function untrack(folder)
	local entry = entries[folder]
	if entry then
		clearEntry(entry)
		entries[folder] = nil
	end
end
local function watchFolder(f)
	if f.Name ~= "RoguelitePets" or not f:IsA("Folder") then
		return
	end
	f.ChildAdded:Connect(track)
	f.ChildRemoved:Connect(untrack)
	for _, c in f:GetChildren() do
		track(c)
	end
end
workspace.ChildAdded:Connect(watchFolder)
if workspace:FindFirstChild("RoguelitePets") then
	watchFolder(workspace.RoguelitePets)
end

-- Actions and VFX --------------------------------------------------------------------------------
-- Play the pet's action (or a named) clip, with an optional dash to `to` and back.
local function play(entry, clipName, dash)
	local clips = entry.rig and entry.rig.clips or {}
	local clip = clips[clipName or "action"] or clips.action
	local now = os.clock()
	entry.action = clip
			and {
				clip = clip,
				start = now,
				duration = clip.duration or 0.8,
				ends = now + (clip.duration or 0.8) + (clip.hold and 0.5 or 0),
			}
		or nil
	if dash and entry.pos then
		local to = dash.to
		to = Vector3.new(to.X, groundY(to, entry.pos.Y), to.Z)
		entry.dash = {
			from = entry.pos,
			to = to,
			start = now,
			out = dash.out or 0.3,
			hold = dash.hold or 0.15,
			back = dash.back or 0.35,
			arc = dash.arc or 0,
		}
	end
end

local function ring(position, radius, color)
	if not budget(0.5) then
		return
	end
	local p = temp(
		part({
			Shape = Enum.PartType.Cylinder,
			Size = Vector3.new(0.3, 1, 1),
			CFrame = CFrame.new(position) * CFrame.Angles(0, 0, math.rad(90)),
			Material = Enum.Material.Neon,
			Color = color,
			Transparency = 0.25,
		}),
		0.5
	)
	tween(p, 0.35, { Size = Vector3.new(0.3, radius * 2, radius * 2), Transparency = 1 })
end
local function burst(position, color, count, texture, speed, life)
	if not budget(life + 0.3) then
		return
	end
	local p = temp(part({ Size = Vector3.one * 0.2, Transparency = 1, CFrame = CFrame.new(position) }), life + 0.3)
	local e = emitter(p, {}, {
		texture = texture,
		rate = 0,
		life = { life * 0.6, life },
		speed = speed or { 3, 6 },
		color = ColorSequence.new(color),
		size = NumberSequence.new(0.35, 0),
	})
	e.Enabled = false
	e:Emit(count)
end
local function rootOf(userId)
	local p = Players:GetPlayerByUserId(userId)
	local c = p and p.Character
	return c and c:FindFirstChild("HumanoidRootPart")
end

local function popShield(userId, position)
	local s = shields[userId]
	shields[userId] = nil
	if s and s.part.Parent then
		tween(s.part, 0.2, { Size = s.part.Size * 1.4, Transparency = 1 })
		Debris:AddItem(s.part, 0.25)
	end
	local r = rootOf(userId)
	local at = r and r.Position or position
	if at then
		burst(at, Color3.fromRGB(150, 230, 210), 14, TEX.sparkle, { 6, 10 }, 0.5)
	end
end

local function speedTrail(r, duration)
	local a0 = Instance.new("Attachment")
	a0.Position = Vector3.new(0, 0.9, 0)
	local a1 = Instance.new("Attachment")
	a1.Position = Vector3.new(0, -0.9, 0)
	a0.Parent, a1.Parent = r, r
	local tr = Instance.new("Trail")
	tr.Attachment0, tr.Attachment1 = a0, a1
	tr.Lifetime, tr.LightEmission, tr.LightInfluence = 0.25, 0.6, 0
	tr.Transparency = NumberSequence.new(0.5, 1)
	tr.Color = ColorSequence.new(Color3.fromRGB(190, 240, 255))
	tr.Parent = r
	for _, inst in { a0, a1, tr } do
		Debris:AddItem(inst, duration + 0.3)
	end
end

local function reticle(entry, npc, untilTime)
	if entry.reticle then
		entry.reticle.gui:Destroy()
		entry.reticle = nil
	end
	local r = typeof(npc) == "Instance" and npc:FindFirstChild("HumanoidRootPart")
	if not r then
		return
	end
	local size = math.clamp(npc:GetExtentsSize().Magnitude * 0.45, 4, 14)
	local gui = Instance.new("BillboardGui")
	gui.Name = "OwlMark"
	gui.Adornee = r
	gui.AlwaysOnTop = true
	gui.LightInfluence = 0
	gui.Size = UDim2.new(size, 0, size, 0)
	local spin = Instance.new("Frame")
	spin.Name = "Spin"
	spin.AnchorPoint = Vector2.new(0.5, 0.5)
	spin.Position = UDim2.fromScale(0.5, 0.5)
	spin.Size = UDim2.fromScale(1, 1)
	spin.BackgroundTransparency = 1
	spin.Parent = gui
	local circle = Instance.new("Frame")
	circle.AnchorPoint = Vector2.new(0.5, 0.5)
	circle.Position = UDim2.fromScale(0.5, 0.5)
	circle.Size = UDim2.fromScale(0.72, 0.72)
	circle.BackgroundTransparency = 1
	circle.Parent = spin
	Instance.new("UICorner", circle).CornerRadius = UDim.new(1, 0)
	local stroke = Instance.new("UIStroke", circle)
	stroke.Color, stroke.Thickness, stroke.Transparency = AMBER, 3, 0.1
	for i = 0, 3 do
		local tickMark = Instance.new("Frame")
		tickMark.AnchorPoint = Vector2.new(0.5, 0.5)
		local horizontal = i % 2 == 1
		local sign = i < 2 and -1 or 1
		tickMark.Position = horizontal and UDim2.fromScale(0.5 + sign * 0.42, 0.5)
			or UDim2.fromScale(0.5, 0.5 + sign * 0.42)
		tickMark.Size = horizontal and UDim2.fromScale(0.18, 0.05) or UDim2.fromScale(0.05, 0.18)
		tickMark.BackgroundColor3 = AMBER
		tickMark.BorderSizePixel = 0
		tickMark.Parent = spin
	end
	gui.Parent = holder
	entry.reticle = { gui = gui, spin = spin, npc = npc, untilTime = untilTime }
end

local KIND_CLIP = {
	Fetch = "action",
	Carrot = "action",
	Slam = "action",
	Slide = "action",
	Pounce = "action",
	Sting = "action",
	Shield = "action",
	Mark = "action",
	Breath = "action",
}

local function onFx(ownerId, kind, data)
	data = type(data) == "table" and data or {}
	if kind == "ShieldPop" then
		popShield(data.target, data.position)
		return
	end
	local entry = byOwner[ownerId]
	local pos = entry and entry.pos
	if kind == "Fetch" and data.position then
		if entry then
			play(entry, KIND_CLIP.Fetch, { to = data.position, out = 0.35, hold = 0.2, back = 0.45, arc = 0.4 })
		end
		burst(data.position, Color3.fromRGB(150, 220, 255), 8, TEX.sparkle, { 2, 4 }, 0.5)
	elseif kind == "Carrot" then
		local r = rootOf(data.target)
		local at = r and r.Position or data.position
		if entry then
			local near = at and pos and (at - pos).Magnitude < 14
			play(entry, KIND_CLIP.Carrot, near and { to = at, out = 0.25, hold = 0.1, back = 0.3, arc = 1 } or nil)
		end
		if at and budget(0.9) then
			local carrot = temp(
				part({
					Size = Vector3.new(0.35, 1, 0.35),
					Color = Color3.fromRGB(240, 132, 40),
					Material = Enum.Material.SmoothPlastic,
					CFrame = CFrame.new(at + Vector3.new(0, 2.5, 0)) * CFrame.Angles(0, 0, math.rad(20)),
				}),
				0.9
			)
			local top = part({
				Size = Vector3.new(0.3, 0.35, 0.3),
				Color = Color3.fromRGB(96, 170, 70),
				CFrame = carrot.CFrame * CFrame.new(0, 0.65, 0),
			})
			top.Parent = carrot
			local weld = Instance.new("WeldConstraint")
			weld.Part0, weld.Part1 = carrot, top
			weld.Parent = carrot
			top.Anchored = false
			tween(carrot, 0.8, { CFrame = carrot.CFrame + Vector3.new(0, 1.5, 0), Transparency = 1 })
			tween(top, 0.8, { Transparency = 1 })
			burst(at + Vector3.new(0, 1, 0), Color3.fromRGB(140, 235, 140), 14, TEX.sparkle, { 2, 5 }, 0.7)
		end
	elseif kind == "Slam" and data.position then
		local radius = data.radius or 8
		if entry then
			play(entry, KIND_CLIP.Slam, { to = data.position, out = 0.38, hold = 0.2, back = 0.4, arc = 4 })
		end
		task.delay(0.38, function()
			local y = groundY(data.position, data.position.Y - 2)
			ring(Vector3.new(data.position.X, y + 0.2, data.position.Z), radius, Color3.fromRGB(150, 210, 140))
			burst(
				Vector3.new(data.position.X, y + 0.5, data.position.Z),
				Color3.fromRGB(200, 190, 170),
				12,
				TEX.smoke,
				{ 4, 8 },
				0.6
			)
		end)
	elseif kind == "Slide" and data.from and data.to then
		if entry then
			play(entry, KIND_CLIP.Slide, { to = data.to, out = 0.45, hold = 0.1, back = 0.5 })
		end
		local length = (data.to - data.from).Magnitude
		if length > 0.5 and budget(0.7) then
			local y = groundY(data.from, data.from.Y - 2) + 0.15
			local a = Vector3.new(data.from.X, y, data.from.Z)
			local b = Vector3.new(data.to.X, y, data.to.Z)
			local streak = temp(
				part({
					Size = Vector3.new(1.2, 0.1, length),
					CFrame = CFrame.lookAt((a + b) / 2, b),
					Material = Enum.Material.Neon,
					Color = Color3.fromRGB(200, 236, 255),
					Transparency = 0.35,
				}),
				0.7
			)
			tween(streak, 0.6, { Transparency = 1, Size = Vector3.new(0.2, 0.1, length) })
			for i = 0, 3 do
				task.delay(i * 0.1, function()
					burst(
						a:Lerp(b, i / 3) + Vector3.new(0, 0.4, 0),
						Color3.fromRGB(225, 245, 255),
						5,
						TEX.smoke,
						{ 1, 3 },
						0.6
					)
				end)
			end
		end
	elseif kind == "Pounce" and data.position then
		if entry then
			play(entry, KIND_CLIP.Pounce, { to = data.position, out = 0.22, hold = 0.12, back = 0.35, arc = 1.6 })
		end
		task.delay(0.22, function()
			if not budget(0.4) then
				return
			end
			local face = workspace.CurrentCamera and workspace.CurrentCamera.CFrame.Rotation or CFrame.new()
			for i = -1, 1 do
				local claw = temp(
					part({
						Size = Vector3.new(0.12, 2.4, 0.12),
						CFrame = CFrame.new(data.position + Vector3.new(0, 0.5, 0))
							* face
							* CFrame.new(i * 0.45, 0, -1)
							* CFrame.Angles(0, 0, math.rad(25)),
						Material = Enum.Material.Neon,
						Color = Color3.fromRGB(255, 236, 214),
						Transparency = 0.1,
					}),
					0.35
				)
				tween(claw, 0.3, { Transparency = 1, Size = Vector3.new(0.05, 3, 0.05) })
			end
		end)
	elseif kind == "Sting" and data.position then
		if entry then
			play(entry, KIND_CLIP.Sting, { to = data.position, out = 0.25, hold = 0.1, back = 0.3, arc = 1.2 })
		end
		task.delay(0.25, function()
			burst(
				data.position + Vector3.new(0, 0.5, 0),
				Color3.fromRGB(120, 220, 80),
				12,
				TEX.smoke,
				{ 1.5, 3.5 },
				0.8
			)
		end)
	elseif kind == "Shield" and data.target then
		if entry then
			play(entry, KIND_CLIP.Shield)
		end
		local old = shields[data.target]
		if old then
			old.part:Destroy()
		end
		local bubble = part({
			Shape = Enum.PartType.Ball,
			Size = Vector3.one * 7,
			Material = Enum.Material.ForceField,
			Color = Color3.fromRGB(120, 220, 200),
			Transparency = 0,
		})
		bubble.Parent = holder
		shields[data.target] = { part = bubble, ends = os.clock() + (data.duration or 15) }
	elseif kind == "Mark" then
		if entry then
			play(entry, KIND_CLIP.Mark)
			reticle(entry, data.target, data.untilTime or (workspace:GetServerTimeNow() + 5))
		end
	elseif kind == "Burst" then
		local r = rootOf(ownerId)
		if r then
			speedTrail(r, data.duration or 2)
			burst(r.Position, Color3.fromRGB(170, 235, 255), 18, TEX.sparkle, { 6, 10 }, 0.4)
		end
		if entry then
			entry.burstUntil = os.clock() + (data.duration or 2)
		end
	elseif kind == "Breath" and data.from and data.to then
		if entry then
			play(entry, KIND_CLIP.Breath, { to = data.from, out = 0.3, hold = 0.7, back = 0.4 })
		end
		task.delay(0.3, function()
			if not budget(1.6) then
				return
			end
			local head = entry and entry.parts and entry.parts.BabyDragon_Head
			local from = head and head.part.Position or (data.from + Vector3.new(0, 2, 0))
			local to = Vector3.new(data.to.X, from.Y - 0.5, data.to.Z)
			local p = temp(part({ Size = Vector3.one * 0.2, Transparency = 1, CFrame = CFrame.lookAt(from, to) }), 1.6)
			local cone = entry and vfxFind(entry, "fire_breath") or {}
			local length = (to - from).Magnitude
			local e = emitter(p, cone, {
				texture = TEX.fire,
				rate = 90,
				life = { 0.45, 0.55 },
				spread = { 25, 25 },
				size = NumberSequence.new({
					NumberSequenceKeypoint.new(0, 0.3),
					NumberSequenceKeypoint.new(0.4, 0.9),
					NumberSequenceKeypoint.new(1, 1.4),
				}),
				color = ColorSequence.new({
					ColorSequenceKeypoint.new(0, Color3.fromRGB(255, 240, 150)),
					ColorSequenceKeypoint.new(0.5, Color3.fromRGB(240, 84, 36)),
					ColorSequenceKeypoint.new(1, Color3.fromRGB(72, 60, 60)),
				}),
			})
			-- Speed x lifetime = the cone length; it spreads 25 degrees like the server's cone.
			e.Speed = NumberRange.new(length / 0.55, length / 0.45)
			e.SpreadAngle = Vector2.new(25, 25)
			e.EmissionDirection = Enum.NormalId.Front
			local light = Instance.new("PointLight")
			light.Color, light.Brightness, light.Range, light.Shadows = Color3.fromRGB(255, 150, 60), 2, 8, false
			light.Parent = p
			task.delay(0.6, function()
				e.Enabled = false
				light.Enabled = false
			end)
		end)
	end
end
combat:WaitForChild("PetFX").OnClientEvent:Connect(onFx)

-- The frame loop ---------------------------------------------------------------------------------
local function update(entry, dt, now, camPos)
	if not entry.model then
		if now >= entry.retryAt then
			entry.retryAt = now + 1
			build(entry)
		end
		if not entry.model then
			return
		end
	end
	local owner = Players:GetPlayerByUserId(entry.ownerId)
	local character = owner and owner.Character
	local hrp = character and character:FindFirstChild("HumanoidRootPart")
	if not hrp then
		return
	end
	-- Follow: a spring toward a spot behind and beside the owner, on the ground.
	local spot = (hrp.CFrame * CFrame.new(SIDE, 0, BEHIND)).Position
	if now >= entry.groundAt or not entry.gy then
		entry.groundAt = now + 0.1
		entry.gy = groundY(spot, hrp.Position.Y - 3)
	end
	local goal = Vector3.new(spot.X, entry.gy, spot.Z)
	if not entry.pos or (goal - entry.pos).Magnitude > TELEPORT then
		entry.pos, entry.vel, entry.dash = goal, Vector3.zero, nil
	end
	local k = 50 -- stiffness: about 6 studs of lag behind a running owner
	entry.vel += ((goal - entry.pos) * k - entry.vel * 2 * math.sqrt(k)) * dt
	if entry.vel.Magnitude > 60 then
		entry.vel = entry.vel.Unit * 60
	end
	entry.pos += entry.vel * dt
	-- A dash (action) overrides the follow position: out to the target, hold, back to the follow spot.
	local shown, faceTo = entry.pos, nil
	local d = entry.dash
	if d then
		local t = now - d.start
		if t < d.out then
			local u = smooth(t / d.out)
			shown = d.from:Lerp(d.to, u) + Vector3.new(0, d.arc * 4 * u * (1 - u), 0)
			faceTo = d.to
		elseif t < d.out + d.hold then
			shown = d.to
			faceTo = d.to + (d.to - d.from)
		elseif t < d.out + d.hold + d.back then
			local u = smooth((t - d.out - d.hold) / d.back)
			shown = d.to:Lerp(entry.pos, u) + Vector3.new(0, d.arc * 0.5 * 4 * u * (1 - u), 0)
			faceTo = entry.pos
		else
			entry.dash = nil
		end
	end
	local last = entry.shown or shown
	local speed = flat(shown - last).Magnitude / math.max(dt, 1e-3)
	entry.speed += (speed - entry.speed) * math.min(1, dt * 10)
	entry.shown = shown
	-- Facing: where it travels, else where its owner looks.
	local want = faceTo and flat(faceTo - shown)
		or (entry.speed > 1 and flat(shown - last))
		or flat(hrp.CFrame.LookVector)
	if want.Magnitude > 1e-3 then
		entry.dir = entry.dir:Lerp(want.Unit, math.min(1, dt * (faceTo and 14 or 8)))
		if entry.dir.Magnitude < 1e-3 then
			entry.dir = want.Unit
		end
		entry.dir = entry.dir.Unit
	end
	-- Ambience switches.
	local running = entry.speed > 12 or (entry.burstUntil or 0) > now
	if entry.runTrail then
		entry.runTrail.Enabled = running
	end
	if entry.glide then
		for _, em in entry.glide do
			em.Enabled = entry.speed > 4
		end
	end
	if entry.pulse then
		local marking = entry.reticle ~= nil
		local period = marking and 0.45 or 1.4
		local lo, hi = marking and 0.05 or 0.35, marking and 0.35 or 0.55
		entry.pulse.Transparency = lo + (hi - lo) * (0.5 + 0.5 * math.sin(now * 2 * math.pi / period))
	end
	if entry.reticle then
		local r = entry.reticle
		local h = typeof(r.npc) == "Instance" and r.npc:FindFirstChildOfClass("Humanoid")
		if
			workspace:GetServerTimeNow() > r.untilTime
			or not h
			or h.Health <= 0
			or not r.npc:IsDescendantOf(workspace)
		then
			r.gui:Destroy()
			entry.reticle = nil
		else
			r.spin.Rotation = (now * 60) % 360
		end
	end
	-- LuckyCat beckons now and then while standing still.
	if entry.speed < 0.5 and not entry.action and not entry.dash then
		entry.idleTime += dt
		if entry.id == "LuckyCat" and entry.idleTime > 3 and now >= entry.nextBeckon then
			entry.nextBeckon = now + math.random(8, 14)
			play(entry, "action")
		end
	else
		entry.idleTime = 0
	end
	if camPos and (shown - camPos).Magnitude > DRAW_RANGE then
		return
	end
	-- Pose: idle and move blended by speed; the action clip over both while it plays.
	local rig = entry.rig or {}
	local clips = rig.clips or {}
	local cycle = rig.cycle or (clips.move and clips.move.duration) or 0.6
	local stride = rig.stride or 3
	local rate
	if entry.flyer then
		rate = (1 / cycle) * math.clamp(0.8 + entry.speed / math.max(0.1, stride / cycle) * 0.4, 0.8, 1.6)
	else
		rate = math.clamp(entry.speed / stride, 0.5 / cycle, 2.2 / cycle)
	end
	entry.movePhase = (entry.movePhase + dt * rate) % 1
	entry.idlePhase = (entry.idlePhase + dt / ((clips.idle and clips.idle.duration) or 2)) % 1
	local acc = { joints = {}, offsets = {}, lift = 0, pitch = 0, roll = 0, yaw = 0, grounded = 0 }
	local a = entry.action
	local target = 0
	if a then
		if now >= a.ends then
			-- Keep the finished clip's last pose while its weight fades out.
			entry.fading, entry.action, a = a, nil, nil
		else
			target = 1
		end
	end
	entry.actionWeight += (target - entry.actionWeight) * math.min(1, dt * (target > 0 and 14 or 8))
	local aw = entry.actionWeight
	-- A flyer whose idle is additive (a bob on top of the wingbeat) always plays its move clip.
	local additiveIdle = clips.idle and clips.idle.additive
	local m = (entry.flyer and additiveIdle) and 1 or math.clamp((entry.speed - 0.5) / 3, 0, 1)
	addClip(acc, clips.move, entry.movePhase, (1 - aw) * m)
	if additiveIdle then
		addClip(acc, clips.idle, entry.idlePhase, (1 - aw) * (1 - 0.5 * math.clamp(entry.speed / 6, 0, 1)))
	else
		addClip(acc, clips.idle, entry.idlePhase, (1 - aw) * (1 - m))
	end
	local shownAction = a or entry.fading
	if shownAction and aw > 0.001 then
		addClip(acc, shownAction.clip, math.clamp((now - shownAction.start) / shownAction.duration, 0, 1), aw)
	end
	local bob = entry.flyer and math.sin(now * 2 * math.pi / 1.6) * 0.15 or 0
	local root = entry.parts[entry.rootName]
	local rp = root and root.pivot or Vector3.zero
	local base = CFrame.lookAt(shown, shown + entry.dir)
		* CFrame.new(0, entry.hover * (1 - math.clamp(acc.grounded, 0, 1)) + acc.lift + bob, 0)
		* CFrame.new(rp)
		* CFrame.Angles(math.rad(acc.pitch), math.rad(acc.yaw), math.rad(acc.roll))
		* CFrame.new(-rp)
	local transforms, cframes = {}, table.create(#entry.order)
	for i, name in entry.order do
		local rec = entry.parts[name]
		local parentT = rec.parentName and transforms[rec.parentName] or CFrame.identity
		local j = acc.joints[name]
		local o = acc.offsets[name]
		local t = parentT
		if j or o then
			t = parentT
				* CFrame.new(rec.pivot + (o or Vector3.zero))
				* CFrame.Angles(math.rad(j and j.X or 0), math.rad(j and j.Y or 0), math.rad(j and j.Z or 0))
				* CFrame.new(-rec.pivot)
		end
		transforms[name] = t
		cframes[i] = base * t * rec.rest
	end
	workspace:BulkMoveTo(entry.list, cframes, Enum.BulkMoveMode.FireCFrameChanged)
end

RunService.RenderStepped:Connect(function(dt)
	dt = math.min(dt, 1 / 20)
	local now = os.clock()
	refreshExclude(now)
	local cam = workspace.CurrentCamera
	local camPos = cam and cam.CFrame.Position
	for _, entry in entries do
		local ok, err = pcall(update, entry, dt, now, camPos)
		if not ok and not entry.warned then
			entry.warned = true
			warn("PetVisuals", entry.id, err)
		end
	end
	-- Shell shields follow their player and fade out when they expire.
	for userId, s in shields do
		local r = rootOf(userId)
		if not r or now > s.ends then
			shields[userId] = nil
			tween(s.part, 0.3, { Transparency = 1 })
			Debris:AddItem(s.part, 0.35)
		else
			s.part.CFrame = r.CFrame
		end
	end
end)

Players.PlayerRemoving:Connect(function(p)
	local s = shields[p.UserId]
	if s then
		s.part:Destroy()
		shields[p.UserId] = nil
	end
end)
