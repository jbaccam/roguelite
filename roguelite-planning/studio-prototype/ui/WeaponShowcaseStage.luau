-- Automated, cosmetic-only weapon theatre. Local avatar/lobby assets; no gameplay or rewards.
-- Motion and special-event renderers are the production ones; dummy reactions are local theatre.
local RS = game:GetService("ReplicatedStorage")
local C = RS:WaitForChild("RogueliteCombat")
local Catalog = require(C:WaitForChild("WeaponCatalog"))
local Stats = require(C:WaitForChild("CharacterStats"))
local Motion = require(C:WaitForChild("WeaponMotion"))
local Chains = require(C:WaitForChild("ChainWeaponMotion"))
local Cards = require(C:WaitForChild("CardPresentation"))
local Swing = require(C:WaitForChild("SwingVisuals"))
local Legendary = require(C:WaitForChild("LegendaryVisuals"))
local Godly = require(C:WaitForChild("GodlyVisuals"))
local Special = require(C:WaitForChild("SpecialMotion"))
local Utility = require(C:WaitForChild("UtilityMotion"))
local Ground = require(C:WaitForChild("GroundContact"))
local Thrown = require(C:WaitForChild("ThrownVisuals"))
local Arc = require(C:WaitForChild("ArcMotion"))
local Pandora = require(C:WaitForChild("PandoraVisuals"))
local Styles = require(C:WaitForChild("ProjectileStyleVisuals")).Styles
local Roll = require(C:WaitForChild("RolledShirtVisual"))
local K = require(C:WaitForChild("VfxKit"))
local Data = require(RS:WaitForChild("WeaponShowcaseCatalog"))
local Scene = require(RS:WaitForChild("WeaponShowcaseScene"))
local SpecialVisuals = require(C:WaitForChild("SpecialWeaponVisuals"))
local Muzzle = require(C:WaitForChild("MuzzleFlashVisuals"))
local Chicken = require(C:WaitForChild("ChickenTemplate"))
local Rockets = require(C:WaitForChild("RocketVisuals"))
local RocketExplosion = require(C:WaitForChild("RocketExplosionVisuals"))
local RayImpact = require(C:WaitForChild("RayImpact"))
local Content = game:GetService("ContentProvider")
local warmed = false
local muzzleTakeSerial = 0
local Recipes = Data.build(Catalog)
local Stage = {}
Stage.__index = Stage
local ORIGIN = Vector3.new(2600, 420, -16000)
local OWNER = -420042 -- synthetic visual owner; never a player
local GREEN = Color3.fromRGB(145, 239, 20)
local WOOD = Color3.fromRGB(153, 112, 64)
local neutral = {}
for _, s in Stats.List do
	neutral[s.id] = s.base
end

local function part(parent, name, size, at, color, shape)
	local p = K.part(parent, name, size, color, 0, Enum.Material.SmoothPlastic, shape)
	p.CFrame = typeof(at) == "CFrame" and at or CFrame.new(at)
	p.CastShadow = true
	return p
end
local function scrub(model)
	for _, x in model:GetDescendants() do
		if x:IsA("BasePart") then
			x.Anchored = true
			x.CanCollide = false
			x.CanQuery = false
			x.CanTouch = false
			x.LocalTransparencyModifier = 0
		elseif
			x:IsA("LuaSourceContainer")
			or x:IsA("Humanoid")
			or x:IsA("ProximityPrompt")
			or x:IsA("ClickDetector")
		then
			x:Destroy()
		end
	end
end
local function disk(parent, name, pos, radius, height, color)
	return part(
		parent,
		name,
		Vector3.new(height, radius * 2, radius * 2),
		CFrame.new(pos) * CFrame.Angles(0, 0, math.pi / 2),
		color,
		Enum.PartType.Cylinder
	)
end
function Stage.new(player)
	local self = setmetatable(
		{ clock = 0, events = {}, movers = {}, dummies = {}, autoplay = true, serial = 0, hits = 0, closed = false },
		Stage
	)
	self.folder = Instance.new("Folder")
	self.folder.Name = "WeaponShowcaseLocal"
	self.folder.Parent = workspace
	local ok, result, reason = pcall(Scene.new, self.folder, ORIGIN, player or game.Players.LocalPlayer)
	if not ok or not result then
		self.folder:Destroy()
		error(reason or result or "Lobby preview assets unavailable")
	end
	self.scene = result
	self.dummies = result.dummies
	self.presenter = result.presenter
	self.root = result.presenter.root
	self.backdrop = result.backdrop
	return self
end
function Stage:setViewportRect(rect)
	if not rect then
		return
	end
	local previous = self.viewportRect
	if
		not previous
		or previous.left ~= rect.left
		or previous.right ~= rect.right
		or previous.top ~= rect.top
		or previous.bottom ~= rect.bottom
		or previous.fullWidth ~= rect.fullWidth
		or previous.fullHeight ~= rect.fullHeight
	then
		self.viewportRect = rect
		self.cameraCache = nil
	end
end
function Stage:camera()
	local viewport = workspace.CurrentCamera and workspace.CurrentCamera.ViewportSize or Vector2.new(1440, 900)
	local rect = self.viewportRect or { left = 0.055, right = 0.945, top = 0.14, bottom = 0.76 }
	if rect.fullWidth and rect.fullHeight then
		viewport = Vector2.new(rect.fullWidth, rect.fullHeight)
	end
	if self.cameraCache and self.cameraCache.viewport == viewport then
		return self.cameraCache.cf, 48
	end
	-- A lower three-quarter view shows the avatar, silhouettes and island backdrop together.
	local eye = Vector3.new(30, 18, 35).Unit
	local rotation = CFrame.lookAt(Vector3.zero, -eye)
	local points = {}
	local function bounds(model, margin)
		local cf, size = model:GetBoundingBox()
		local half = size * 0.5 + Vector3.one * (margin or 0.5)
		for _, x in { -1, 1 } do
			for _, y in { -1, 1 } do
				for _, z in { -1, 1 } do
					table.insert(points, cf:PointToWorldSpace(half * Vector3.new(x, y, z)))
				end
			end
		end
	end
	bounds(self.presenter.model, 0.65)
	if self.visual then
		bounds(self.visual.model, 1)
	end
	if self.weapon and self.weapon.kind == "Melee" then
		local reach = self.weapon.range * 1.05
		for _, x in { -1, 1 } do
			for _, z in { -1, 1 } do
				table.insert(points, self.root.Position + Vector3.new(x * reach, 1, z * reach))
			end
		end
	end
	for i, d in self.dummies do
		if i <= (self.targetCount or 3) then
			bounds(d.model, 0.5)
		end
	end
	if self.id == "38" then
		table.insert(points, ORIGIN + Vector3.new(0, 17, -4))
	end
	if self.id == "22" then
		table.insert(points, ORIGIN + Vector3.new(6, 3, -27))
	end
	if self.variant and self.variant.mode == "legendary" then
		table.insert(points, ORIGIN + Vector3.new(0, 7, -21))
	end
	local lo, hi = Vector3.one * math.huge, -Vector3.one * math.huge
	for _, p in points do
		local v = rotation:VectorToObjectSpace(p - ORIGIN)
		lo = lo:Min(v)
		hi = hi:Max(v)
	end
	local focus = ORIGIN + rotation:VectorToWorldSpace((lo + hi) / 2)
	local tan = math.tan(math.rad(24))
	local aspect = viewport.X / viewport.Y
	local cx = (rect.left + rect.right) / 2
	local cy = (rect.top + rect.bottom) / 2
	local distance = math.max(
		22,
		(hi.Y - lo.Y) / (2 * tan * (rect.bottom - rect.top)),
		(hi.X - lo.X) / (2 * tan * aspect * (rect.right - rect.left))
	)
	local cf
	for _ = 1, 12 do
		cf = CFrame.lookAt(focus + eye * distance, focus)
			* CFrame.new(-(cx - 0.5) * 2 * distance * tan * aspect, (cy - 0.5) * 2 * distance * tan, 0)
		local fits = true
		for _, p in points do
			local v = cf:PointToObjectSpace(p)
			local z = -v.Z
			local x = 0.5 + v.X / (2 * z * tan * aspect)
			local y = 0.5 - v.Y / (2 * z * tan)
			if z <= 0 or x < rect.left or x > rect.right or y < rect.top or y > rect.bottom then
				fits = false
				break
			end
		end
		if fits then
			break
		end
		distance *= 1.08
	end
	self.cameraCache = { cf = cf, viewport = viewport }
	return cf, 48
end
function Stage:later(delay, fn)
	table.insert(self.events, { at = self.clock + delay, fn = fn })
end
function Stage:move(duration, update, finish)
	if #self.movers >= 40 then
		return false
	end
	table.insert(
		self.movers,
		{ born = self.clock, duration = math.max(0.02, duration), update = update, finish = finish }
	)
	return true
end
function Stage:impact(index, color, text)
	local d = self.dummies[index]
	if not d or index > (self.targetCount or 7) then
		return
	end
	d.hit = self.clock
	d.color = color or GREEN
	self.hits += 1
	K.pop(self.fx, d.root.Position, color or GREEN, 0.12, 0.8, 0.13, 0.55)
	if text then
		local a = K.part(self.fx, "Feedback", Vector3.one * 0.05, color or GREEN, 1)
		a.Position = d.root.Position + Vector3.yAxis * 2
		local gui = Instance.new("BillboardGui")
		gui.Size = UDim2.fromOffset(120, 32)
		gui.AlwaysOnTop = true
		gui.Parent = a
		local l = Instance.new("TextLabel")
		l.Size = UDim2.fromScale(1, 1)
		l.BackgroundTransparency = 1
		l.Font = Enum.Font.FredokaOne
		l.TextSize = 21
		l.Text = text
		l.TextColor3 = color or GREEN
		l.TextStrokeTransparency = 0.1
		l.Parent = gui
		self:move(0.65, function(t)
			a.Position = d.root.Position + Vector3.yAxis * (2 + t)
			l.TextTransparency = t
		end, function()
			a:Destroy()
		end)
	end
end
function Stage:clearTake()
	if self.rockets then
		self.rockets.destroy()
		self.rockets = nil
	end
	if self.specialFX then
		self.specialFX.destroy()
		self.specialFX = nil
	end
	if self.legend then
		self.legend.destroy()
		self.legend = nil
	end
	if self.godly then
		self.godly.destroy()
		self.godly = nil
	end
	if self.vacuum then
		self.vacuum:destroy()
		self.vacuum = nil
	end
	table.clear(self.events)
	table.clear(self.movers)
	if self.take then
		self.take:Destroy()
		self.take = nil
	end
	self.visual = nil
	self.muzzle = nil
	self.pulling = false
	self.streamMode = nil
	self.streamUntil = nil
	self.returning = false
	self.zoneKeys = {}
	self.wraithKeys = {}
	self.chickenCount = 0
end
function Stage:select(id, tier, key)
	assert(not self.closed, "Showcase stage closed")
	assert(Catalog.ById[id], "Unknown weapon")
	self:clearTake()
	self.cameraCache = nil
	self.id = id
	self.tier = math.clamp(math.floor(tier or 1), 1, 4)
	self.entry = Recipes.ById[id]
	self.variant = Data.variant(self.entry, key, self.tier)
	self.weapon = Stats.weapon(Catalog.ById[id], neutral, "", self.tier)
	self.hits = 0
	self.serial = 0
	self.completedDemos = 0
	self.demoRemaining = self.variant.mode == "legendary" and (Catalog.Legendary[id].every or 1) or 1
	self.nextAttackAt = self.clock + 0.12
	self.nextStreamVisual = 0
	self.nextStreamHit = 0
	self.pullEpoch = self.clock
	self.legendaryCharge = 0
	self.zoneSerial = 0
	self.wraithSerial = 0
	self.cycleStarted = self.clock
	self.take = Instance.new("Folder")
	self.take.Name = "Take_" .. id
	self.take.Parent = self.folder
	self.fx = Instance.new("Folder")
	self.fx.Name = "Effects"
	self.fx.Parent = self.take
	local template = C.WeaponTemplates:FindFirstChild(id)
	assert(template, "Weapon model " .. id .. " is unavailable")
	local model = template:Clone()
	scrub(model)
	model.Name = "PreviewWeapon_" .. id
	model.Parent = self.take
	local v = { id = id, model = model, parts = {}, chain = Chains.bind(model, id), cards = Cards.bind(model, id) }
	self.visual = v
	self.template = template
	if id == "19" then
		v.gloves = {}
		for _, p in model:GetDescendants() do
			if p:IsA("BasePart") then
				local cf = model:GetPivot():ToObjectSpace(p.CFrame)
				table.insert(v.gloves, { part = p, localCF = cf, side = cf.X < 0 and -1 or 1 })
			end
		end
	end
	if id == "15" or id == "23" then
		v.reserves = {}
		for i = 2, 3 do
			local copy = template:Clone()
			scrub(copy)
			copy.Name = "Reserve" .. i
			copy.Parent = model
			v.reserves[i] = copy
		end
	end
	for _, p in model:GetDescendants() do
		if p:IsA("BasePart") then
			table.insert(v.parts, p)
		end
	end
	if id == "33" then
		v.lid = model:FindFirstChild("W33_Lid_Hinge", true)
		v.pandora = Pandora.idle(model)
	end
	-- Pizza Cutter wheel (2026-10-09), the same roll as RogueliteCombat.client: it spins about its own local Z.
	local wheel = id == "42" and model:FindFirstChild("Wheel", true)
	if wheel then
		local rest = model:GetPivot():ToObjectSpace(wheel.CFrame)
		local axle = rest:VectorToWorldSpace(Vector3.zAxis)
		local out = (Vector3.yAxis - axle * axle.Y).Unit
		local r = wheel:GetAttribute("WheelRadius") or math.max(wheel.Size.X, wheel.Size.Y) / 2
		v.wheel = { part = wheel, rest = rest, tip = rest.Position + out * r, tangent = out:Cross(axle), out = out, r = r, speed = 0, angle = 0 }
	end
	local function lookup(owner, slot)
		if owner == OWNER and slot == 1 then
			return self.visual
		end
	end
	self.swing = Swing.mount(self.fx)
	local targets = {}
	self.visualTargets = targets
	self.legend = Legendary.mount(C, self.fx, lookup, { preview = true, ownerRoot = self.root, targets = targets })
	self.specialFX = SpecialVisuals.mount(C, self.fx, lookup, { preview = true })
	if id == "11" then
		RocketExplosion.warm()
		self.rockets = Rockets.mount(C, self.fx, { preview = true, ground = self.scene.ground })
	end
	muzzleTakeSerial += 1
	self.muzzle = Muzzle.mount(self.take, { renderKey = "WeaponShowcaseMuzzle" .. muzzleTakeSerial })
	self.godly = Godly.mount(C, self.fx, lookup, { preview = true, ownerRoot = self.root })
	local slot = Instance.new("Folder")
	slot.Name = "VisualTier"
	slot:SetAttribute("Tier", self.tier)
	slot:SetAttribute("LegendaryCharge", 0)
	slot.Parent = self.take
	self.slot = slot
	self.swing.attach(v, id, template)
	self.legend.attach(v, id, template, slot)
	self.godly.attach(v, id, template)
	self.assetsReady = false
	local take = self.take
	task.spawn(function()
		local assets = { model }
		if not warmed then
			for _, id in Legendary.Textures do
				table.insert(assets, id)
			end
			for _, id in Godly.Textures or {} do
				table.insert(assets, id)
			end
			table.insert(assets, "rbxassetid://131707953627421")
		end
		pcall(function()
			Content:PreloadAsync(assets)
		end)
		warmed = true
		if not self.closed and self.take == take then
			self.assetsReady = true
		end
	end)
	task.delay(4, function()
		if not self.closed and self.take == take then
			self.assetsReady = true
		end
	end)
	self.attackStart = -1e6
	self.attackKind = self.weapon.kind
	self.style = nil
	self.flyingUntil = -1e6
	local melee = self.variant.mode == "melee"
		or self.variant.mode == "wraith"
		or self.variant.mode == "wisp"
		or (self.variant.mode == "legendary" and self.weapon.kind == "Melee" and id ~= "31")
	Scene.place(self.presenter, 0, 12, -Vector3.zAxis)
	local vacuum = self.variant.mode == "vacuum"
	local area = self.variant.mode == "legendary"
		or self.variant.mode == "rain"
		or self.variant.mode == "burst"
		or self.variant.mode == "wraith"
	self.targetCount = id == "22" and 5
		or self.variant.mode == "chain" and math.min(7, Catalog.Godly["39"].chain[self.tier])
		or self.variant.mode == "lightning" and 4
		or area and 5
		or 3
	if id == "12" then
		self.targetCount = math.min(7, 1 + self.weapon.nativeBounce)
	end
	-- A lone target makes aimed guns legible; area/chain weapons retain the groups they need.
	if id == "00" or id == "07" or id == "24" or id == "30" then
		self.targetCount = 1
	end
	self.primaryIndex = self.targetCount == 1 and 1 or 2
	local distance = melee and math.clamp(self.weapon.range * 0.8, 6, 11)
		or vacuum and self.weapon.range * 0.64
		or self.variant.mode == "fire" and 10
		or 18
	for i, d in self.dummies do
		local x, z
		if self.targetCount == 1 then
			x, z = 0, 12 - distance
		elseif id == "22" then
			x = 6
			z = 12 - 7 - i * 4.7
		elseif melee then
			local angle = ({ -0.82, 0, 0.82, -0.5, 0.5, -0.9, 0.9 })[i]
			x = math.sin(angle) * distance
			z = 12 - math.cos(angle) * distance
			if i > 3 then
				z -= 7
			end
		elseif vacuum then
			x = 6 + ((i - 1) % 3 - 1) * 4.8
			z = 12 - distance - math.floor((i - 1) / 3) * 6
		else
			x = ((i - 1) % 3 - 1) * 5.5
			z = 12 - distance - math.floor((i - 1) / 3) * 6
		end
		Scene.place(d, x, z, Vector3.zAxis)
		d.visible = i <= self.targetCount
		if d.visible then
			table.insert(targets, d.model)
		end
		for _, p in d.model:GetDescendants() do
			if p:IsA("BasePart") then
				p.LocalTransparencyModifier = d.visible and 0 or 1
			end
		end
		d.hit = -100
	end
	self.aim = self.dummies[self.primaryIndex].root.Position
	self.direction = (self.aim - self.root.Position).Unit
	self:pose(0)
	self.duration = self:cadence()
	self.nextCycle = self.nextAttackAt
	return self.variant
end
function Stage:pose(dt)
	local v = self.visual
	if not v then
		return
	end
	local d = self.weapon
	local id = self.id
	local age = (self.clock - self.attackStart) * (self.rate or d.motionRate)
	local kind = self.attackKind or d.kind
	local style = self.style
	local side = Motion.chooseSide(self.serial)
	local _, activeEnd, duration = Motion.attackTiming(id, kind, style)
	local radius = Motion.BaseRadius
	local idle = Motion.pose(self.root.CFrame, radius, 1, nil, 0, 1e6, kind, id)
	local pose = idle
	local active = age >= 0 and age < duration
	if kind == "Melee" then
		if v.gloves then
			idle *= CFrame.Angles(-math.pi / 2, 0, 0)
			pose = idle
		end
		if active then
			if not v.attackReturn or v.attackReturn.start ~= self.attackStart then
				v.attackReturn = { start = self.attackStart, entry = v.lastPose or idle, gloves = {} }
			end
			local cut
			if v.chain then
				cut = Chains.pose(
					v.chain,
					self.root.CFrame,
					self.direction,
					self.aim,
					math.min(age, activeEnd),
					d.range,
					style,
					side,
					true
				)
			else
				cut = Motion.pose(
					self.root.CFrame,
					radius,
					1,
					self.aim,
					self.attackStart,
					self.attackStart + math.min(age, activeEnd),
					kind,
					id,
					self.direction,
					d.range,
					self.template:GetAttribute("BoundsSize"),
					self.template:GetAttribute("BoundsCenter"),
					style,
					side,
					true
				)
			end
			pose = age <= activeEnd and cut
				or (
					v.chain and Chains.swingReturn(v.chain, cut, idle, age, v.attackReturn)
					or Motion.swingReturn(cut, idle, age, v.attackReturn, id, style)
				)
			if age < Motion.SwingHitStart then
				pose = v.attackReturn.entry:Lerp(pose, Motion.entryAlpha(age))
			end
		else
			v.attackReturn = nil
		end
	else
		pose = Motion.pose(self.root.CFrame, radius, 1, self.aim, self.attackStart, self.attackStart + age, kind, id)
	end
	if v.gloves then
		pose = idle
	end
	v.lastPose = pose
	v.model:PivotTo(pose)
	if v.gloves then
		for _, g in v.gloves do
			local rest = pose * g.localCF
			g.part.CFrame = rest
			if active and (g.side == side or self.tier >= 3) then
				local target = g.side == side and self.aim or self.dummies[3].root.Position
				local cut = Motion.glovePose(self.root.CFrame, target, math.min(age, activeEnd), g.side, d.range)
				g.part.CFrame = cut:Lerp(rest, Motion.swingRecovery(age))
			end
		end
	end
	if v.reserves then
		for i, copy in v.reserves do
			copy:PivotTo(pose * CFrame.new((i == 2 and -1 or 1) * 1.5, 0.35, 0.25))
		end
	end
	Chains.apply(v.chain, age)
	Cards.step(v.cards, self.clock)
	if v.lid then
		v.lid.Transform = CFrame.Angles(0, -math.pi / 2 * Arc.lid(self.clock - self.attackStart), 0)
	end
	if v.wheel then
		-- Spin = (rim speed + half the push along the blade) / radius, capped at 30 rad/s. The cut grabs the wheel;
		-- afterwards it is a free wheel that coasts down with a 0.6 s time constant (see RogueliteCombat.client).
		local s = v.wheel
		local tip = pose:PointToWorldSpace(s.tip)
		if dt > 0 and s.last then
			local step = tip - s.last
			local cut = age >= 0 and age <= activeEnd
			local drive = step.Magnitude < 12
					and math.clamp(
						(step:Dot(pose:VectorToWorldSpace(s.tangent)) + 0.5 * step:Dot(pose:VectorToWorldSpace(s.out)))
							/ (dt * s.r)
							* (cut and 1 or 0.15),
						-30,
						30
					)
				or 0
			local grab = (math.abs(drive) > math.abs(s.speed) and (cut or drive * s.speed >= 0)) and 18 or 1 / 0.6
			s.speed += (drive - s.speed) * (1 - math.exp(-grab * dt))
			s.angle = (s.angle + s.speed * dt) % (2 * math.pi)
		end
		s.last = tip
		s.part.CFrame = pose * s.rest * CFrame.Angles(0, 0, s.angle)
	end
	if v.pandora then
		Pandora.stepIdle(v.pandora, pose, true, Arc.lid(self.clock - self.attackStart))
	end
	local frame = {
		visible = true,
		active = active,
		age = age,
		start = self.attackStart,
		kind = kind,
		style = style,
		side = side,
		attackRoot = self.root.CFrame,
		rate = self.rate or d.motionRate,
		direction = self.direction,
		range = d.range,
		hand = side,
		secondAim = self.dummies[3].root.Position,
	}
	self.swing.step(v, pose, frame)
	self.legend.step(v, pose, frame)
	self.godly.step(v, pose, frame)
	self.godly.stepEffects(dt)
	if self.specialFX then
		self.specialFX.step(dt)
	end
	if self.rockets then
		self.rockets.step(dt)
	end
	for _, p in v.parts do
		local reserve = p:FindFirstAncestor("Reserve2") or p:FindFirstAncestor("Reserve3")
		local hidden = (self.clock < self.flyingUntil and not reserve) or (v.hide and (v.hide[p] or 0) > 0)
		p.LocalTransparencyModifier = hidden and 1 or 0
	end
	if v.cards then
		for _, entry in v.cards.cards do
			local flying = self.clock < (entry.flyingUntil or 0)
			for _, part in entry.model:GetDescendants() do
				if part:IsA("BasePart") then
					part.LocalTransparencyModifier = flying and 1 or 0
				elseif part:IsA("SurfaceGui") then
					part.Enabled = not flying
				end
			end
		end
	end
end
function Stage:beginAttack(kind, style)
	self.serial += 1
	self.attackStart = self.clock
	self.attackKind = kind or self.weapon.kind
	self.style = style
		or Motion.chooseStyle(self.id, 3, self.serial, (self.aim - self.root.Position).Magnitude, self.weapon.range)
	self.rate = self.weapon.motionRate
	self:pose(0)
end
function Stage:melee(style)
	self:beginAttack("Melee", style)
	self:later(0.24 / self.rate, function()
		for i = 1, (self.style == "Thrust" and 2 or 5) do
			self:impact(i, self.id == "27" and Color3.fromRGB(97, 171, 244) or nil, self.id == "27" and "SLOWED" or nil)
		end
		if self.id == "27" then
			local at = self.dummies[2].root.Position
			K.ring(self.fx, CFrame.new(at - Vector3.yAxis * 2.5), {
				segments = 16,
				radius0 = 1,
				radius1 = 3,
				width = 0.5,
				color = Color3.fromRGB(92, 158, 226),
				duration = 0.6,
			})
		end
	end)
end
function Stage:origin()
	local p = self.visual.model:GetPivot()
	local offset = Motion.MuzzleOffsets[self.id]
	local style = Styles[self.id]
	return style and style.muzzle and style.muzzle(self.visual) or offset and p:PointToWorldSpace(offset) or p.Position
end
function Stage:projectile(target, index, override)
	local id = override or self.id
	local style = Styles[id]
	local origin = self:origin()
	local speed = self.weapon.projectileSpeed
	if id == "11" and self.rockets then
		local key = self.serial * 16 + (index or self.primaryIndex)
		local delta = target - origin
		local distance = delta.Magnitude
		local duration = distance / speed
		self.rockets.handle(
			"Launch",
			key,
			origin,
			delta.Unit * speed,
			workspace:GetServerTimeNow(),
			distance,
			1,
			distance
		)
		self:later(duration, function()
			self.rockets.handle("Impact", key, target, self.weapon.blastRadius)
			for i = 1, self.targetCount do
				if (self.dummies[i].root.Position - target).Magnitude <= self.weapon.blastRadius then
					self:impact(i, K.Amber)
				end
			end
		end)
		return
	end
	local model, parts
	if style then
		model, parts = style.build(self.fx, self.visual)
	elseif id == "10" then
		model = Roll.create(self.fx)
	elseif id == "11" and C:FindFirstChild("RocketTemplate") then
		model = C.RocketTemplate:Clone()
		scrub(model)
		model.Parent = self.fx
	else
		model = Instance.new("Model")
		model.Name = id == "11" and "Rocket" or "Bullet"
		model.Parent = self.fx
		local p = part(
			model,
			"Projectile",
			Vector3.new(id == "11" and 0.32 or 0.09, id == "11" and 0.32 or 0.09, id == "11" and 1.6 or 0.7),
			origin,
			id == "11" and K.Amber or Color3.fromRGB(255, 231, 179)
		)
		p.Material = Enum.Material.Neon
		model.PrimaryPart = p
		K.trail(p, id == "11" and 0.25 or 0.08, 0.12, p.Color, p.Color, 0.2)
	end
	local state = { model = model, parts = parts or {}, visual = self.visual, home = origin, segmentStart = origin }
	local direction = (target - origin).Unit
	if style and style.launch then
		style.launch(self.fx, origin)
	elseif not Motion.MuzzleOffsets[id] then
		K.pop(self.fx, origin, K.Amber, 0.2, 1.1, 0.12, 0.3)
	end
	local travel = math.clamp((target - origin).Magnitude / speed, 0.08, 1.5)
	if id == "21" and state.parts.disc then
		self.visual.hide = self.visual.hide or {}
		self.visual.hide[state.parts.disc] = 1
	end
	self:move(travel, function(t)
		local point = origin:Lerp(target, t)
		local cf = CFrame.lookAt(point, point + direction)
		if style then
			style.update(state, cf, t * travel, self.fx)
		else
			model:PivotTo(cf)
		end
	end, function()
		self:impact(index or 2, id == "34" and Color3.fromRGB(153, 226, 150) or nil, id == "34" and "SLOWED" or nil)
		if style and style.impact then
			style.impact(self.fx, target, state)
		end
		if id == "11" then
			K.pop(self.fx, target, K.Amber, 1, self.weapon.blastRadius * 2, 0.3, 0.45)
			K.shards(self.fx, target, K.Amber, 10, 17, 0.45, 0.25)
		end
		if id == "21" then
			self:move(0.22, function(t)
				local p = target:Lerp(state.home, t * t)
				style.update(state, CFrame.lookAt(p, p + direction), travel + t * 0.22, self.fx)
			end, function()
				model:Destroy()
				self.visual.hide[state.parts.disc] = 0
			end)
		else
			model:Destroy()
			if state.bolt then
				state.bolt:destroy()
			end
		end
	end)
end
function Stage:shoot()
	self:beginAttack("Ranged")
	local offset = Motion.MuzzleOffsets[self.id]
	if offset then
		self.muzzle(self.visual.model, self.id, offset, self.serial)
	end
	if self.id == "41" then
		local origin = self:origin()
		local target = self.dummies[2].root.Position
		self.godly.shot(
			origin,
			target,
			"Ranged",
			"41",
			0.12,
			0,
			true,
			Vector3.yAxis,
			OWNER,
			1,
			true,
			true,
			self.serial,
			self.serial,
			self.weapon.projectileSpeed,
			true
		)
		self:later((target - origin).Magnitude / self.weapon.projectileSpeed, function()
			self:impact(2, Color3.fromRGB(146, 255, 80))
			local radius = RayImpact.radius(self.weapon)
			self.godly.handle("RayImpact", OWNER, target, radius)
			for i = 1, self.targetCount do
				if i ~= 2 and (self.dummies[i].root.Position - target).Magnitude <= radius then
					self:impact(i, Color3.fromRGB(146, 255, 80))
				end
			end
		end)
	else
		for i = 1, self.weapon.projectileCount do
			self:projectile(self.dummies[(i - 1) % self.targetCount + 1].root.Position, (i - 1) % self.targetCount + 1)
		end
	end
end
function Stage:throw(mode, onLand)
	self:beginAttack("Ranged")
	local id = self.id
	local profile = Special.profiles[id]
	local origin = self:origin()
	local target = self.dummies[2].root.Position
	local ballCenter = Vector3.zero
	local rollRadius = 1
	if id == "22" then
		rollRadius, ballCenter = Ground.ballGeometry(self.template)
		origin = assert(self.scene:groundAt(6, 9)) + Vector3.yAxis * (rollRadius + Ground.Clearance)
		target = origin - Vector3.zAxis * self.weapon.range
	elseif id == "14" or id == "15" or id == "23" then
		target -= Vector3.yAxis * 1.5
	end
	local clone = self.template:Clone()
	scrub(clone)
	clone.Name = "Flying_" .. id
	clone.Parent = self.fx
	Thrown.decorate(clone, id)
	if id == "12" then
		local points = {}
		for i = 1, math.min(1 + self.weapon.nativeBounce, 7) do
			table.insert(points, self.dummies[i].root.Position)
		end
		table.insert(points, origin)
		local total = 0
		local from = origin
		for _, at in points do
			total += Special.duration(from, at, self.weapon.projectileSpeed)
			from = at
		end
		self.flyingUntil = self.clock + total
		self.returning = true
		local age = 0
		local function leg(index, start)
			local finish = points[index]
			local time = Special.duration(start, finish, self.weapon.projectileSpeed)
			local direction = (finish - start).Unit
			self:move(time, function(t)
				local p = Special.position(start, finish, t, 0.7)
				clone:PivotTo(CFrame.new(p) * Special.rotation(id, age + t * time, direction))
			end, function()
				age += time
				if index < #points then
					self:impact(index)
					leg(index + 1, finish)
				else
					clone:Destroy()
					self.returning = false
				end
			end)
		end
		leg(1, origin)
		return
	end
	local duration = Special.duration(origin, target, self.weapon.projectileSpeed)
	local direction = (target - origin).Unit
	self.flyingUntil = self.clock + duration * (profile.returns and 2 or 1)
	if profile.returns then
		self.returning = true
	end
	local row = { id = id }
	local hit = {}
	local radius = rollRadius
	self:move(duration, function(t)
		local p = Special.position(origin, target, t, profile.height)
		local rotation
		if id == "22" then
			local floor = self.scene:groundAt(p.X - ORIGIN.X, p.Z - ORIGIN.Z)
			if floor then
				p = Vector3.new(p.X, floor.Y + radius + Ground.Clearance, p.Z)
			end
			rotation = CFrame.lookAt(Vector3.zero, direction)
				* CFrame.Angles(-(target - origin).Magnitude * t / math.max(0.3, radius), 0, 0)
		else
			rotation = Special.rotation(id, t * duration, direction)
		end
		clone:PivotTo(CFrame.new(p) * rotation * CFrame.new(-ballCenter))
		Thrown.step(self.fx, row, p)
		if id == "22" then
			for i, d in self.dummies do
				if i <= self.weapon.nativePierce + 1 and not hit[i] and math.abs(p.Z - d.root.Position.Z) < 2 then
					hit[i] = true
					self:impact(i)
					if onLand then
						onLand(p, i)
					end
				end
			end
		end
	end, function()
		if id ~= "22" then
			self:impact(2)
			Thrown.impact(self.fx, id, target)
			if onLand then
				onLand(target, 2)
			end
		end
		if id == "14" then
			self:zone(target, "Fire")
		end
		if id == "37" then
			self.godly.handle("Wave", OWNER, target, Catalog.Godly["37"].waveRadius[self.tier], 0.5)
			for i = 1, self.targetCount do
				self:impact(i, Color3.fromRGB(87, 217, 242))
			end
		end
		if profile.returns then
			self:move(duration, function(t)
				local p = Special.position(target, origin, t, profile.height)
				clone:PivotTo(CFrame.new(p) * Special.rotation(id, duration + t * duration, direction))
			end, function()
				clone:Destroy()
				self.returning = false
			end)
		else
			clone:Destroy()
		end
	end)
end
function Stage:arcs()
	self:beginAttack("Ranged")
	local id = self.id
	local origin = self:origin()
	if id == "33" then
		Pandora.open(self.fx, self.visual.model:GetPivot(), self.template:GetAttribute("BoundsSize"))
	end
	for i = 1, (id == "18" and self.weapon.projectileCount or 1) do
		self:later((id == "33" and Arc.BOX_OPEN or (i - 1) * Arc.CARD_STAGGER), function()
			local target = self.dummies[(i - 1) % self.targetCount + 1].root.Position
			local model, skull, cardEntry
			if id == "33" then
				model, skull = Pandora.skull(self.fx)
			else
				cardEntry = self.visual.cards.cards[(i - 1) % #self.visual.cards.cards + 1]
				model = cardEntry.model:Clone()
				scrub(model)
				for _, face in model:GetDescendants() do
					if face:IsA("SurfaceGui") then
						face.Enabled = true
					end
				end
				model.Parent = self.fx
				local p = model.PrimaryPart
				if p then
					K.trail(p, 0.4, 0.2, K.White, Color3.fromRGB(247, 93, 114), 0.4)
				end
			end
			local distance = (target - origin).Magnitude
			local side, height, bend = Arc.shape(id, distance, i)
			local duration = Arc.duration(id, distance, self.weapon.projectileSpeed)
			if cardEntry then
				cardEntry.flyingUntil = self.clock + duration + 0.12
			end
			self:move(duration, function(t)
				local p = Arc.position(origin, target, t, side, height, bend)
				local nextP = Arc.position(origin, target, math.min(1, t + 0.01), side, height, bend)
				local look = (nextP - p).Magnitude > 0.001 and (nextP - p).Unit or (target - origin).Unit
				local cf = CFrame.lookAt(p, p + look)
				if skull then
					Pandora.stepSkull(skull, cf, t * duration)
				else
					model:PivotTo(cf * CFrame.Angles(math.pi / 2 + 0.2, 0, t * duration * math.pi * 10 + i))
				end
			end, function()
				model:Destroy()
				self:impact((i - 1) % self.targetCount + 1)
				if id == "33" then
					Pandora.impact(self.fx, target, self.weapon.blastRadius)
				end
			end)
		end)
	end
end
function Stage:zone(at, kind)
	-- Match the server's three-zone per-copy cap; looping no longer destroys the whole take.
	self.zoneSerial += 1
	local key = "preview-zone-" .. self.zoneSerial
	while #self.zoneKeys >= 3 do
		self.specialFX.handle("ZoneEnd", table.remove(self.zoneKeys, 1))
	end
	table.insert(self.zoneKeys, key)
	local life = kind == "Fire" and 4 or 5
	local base = Vector3.new(at.X, ORIGIN.Y + (kind == "Fire" and 0.15 or 2), at.Z)
	-- Same sizes as the server (SpecialMotion.zoneRadii): the Molotov fire starts at 7.2 and burns down to 3.6.
	local r0, r1 = Special.zoneRadii(kind, 1)
	self.specialFX.handle("Zone", key, kind, base, r0, life, r1, nil, Special.zoneHold(kind, life))
	for j = 1, math.floor(life / 0.4) do
		self:later(j * 0.4, function()
			if table.find(self.zoneKeys, key) then
				self:impact(2, kind == "Fire" and K.Amber or GREEN)
			end
		end)
	end
	self:later(life, function()
		local index = table.find(self.zoneKeys, key)
		if index then
			table.remove(self.zoneKeys, index)
			self.specialFX.handle("ZoneEnd", key)
		end
	end)
end
function Stage:stream(mode)
 self:beginAttack("Ranged")
 if mode == "fire" then
  local timing=Special.duckTiming(self.weapon.cooldown)
  local direction=(self.aim-self:origin()).Unit
  for pulse=1,timing.pulses do
   self:later((pulse-1)*timing.spacing,function()
    self.specialFX.handle("Spray","preview",self:origin(),direction,math.min(self.weapon.range,14),OWNER,1,timing.emission)
    self:impact(2,K.Amber)
   end)
  end
  return
 end
 if not self.streamMode then
  self.pullEpoch=self.clock
  self.nextStreamVisual=self.clock
  self.nextStreamHit=self.clock
 end
 self.streamMode=mode
 self.streamUntil=self.clock+math.min(1.5,self.weapon.cooldown+.12)
end
function Stage:stepStream()
	local mode = self.streamMode
	if not mode then
		return
	end
	if self.clock > self.streamUntil then
		self.specialFX.handle("StreamEnd", "preview")
		self.streamMode = nil
		self.pulling = false
		for _, d in self.dummies do
			Scene.setVisible(d, d.visible)
		end
		return
	end
	if mode == "fire" then
		return
	end
	local origin = self:origin()
	local direction = self.aim - origin
	if mode == "vacuum" then
		direction = Vector3.new(direction.X, 0, direction.Z)
	end
	direction = direction.Unit
	if self.clock >= self.nextStreamVisual then
		self.nextStreamVisual = self.clock + 0.1
		local finish = mode == "vacuum" and origin + direction * self.weapon.range or self.aim
		self.specialFX.handle(
			"Stream",
			"preview",
			self.id,
			OWNER,
			1,
			origin,
			finish,
			mode == "vacuum" and self.weapon.range * 0.48 or 0.6,
			workspace:GetServerTimeNow() + 0.3,
			Utility.SafeDistance,
			workspace:GetServerTimeNow() - (self.clock - self.pullEpoch)
		)
	end
	if self.clock >= self.nextStreamHit and (mode ~= "water" or Utility.washPressure(self.clock - self.pullEpoch) > 0) then
		self.nextStreamHit = self.clock + 0.12
		self:impact(2, mode == "water" and Color3.fromRGB(119, 219, 249) or GREEN)
	end
	if mode == "vacuum" then
		self.pulling = true
		-- Replenish cosmetic targets during a short fade; the nozzle keeps running throughout.
		-- This is a demonstration reset, not an invented weapon recharge or damage pause.
		local hold, fade = Utility.HoldDuration, 0.12
		local age = (self.clock - self.pullEpoch) % (hold + fade * 2)
		local amount = age < hold + fade and math.min(1, age / hold) or 0
		local alpha = age < hold and 0 or age < hold + fade and (age - hold) / fade or 1 - (age - hold - fade) / fade
		for i = 1, self.targetCount do
			local d = self.dummies[i]
			d.model:PivotTo(d.rest - direction * (amount * 1.5))
			for _, p in d.model:GetDescendants() do
				if p:IsA("BasePart") then
					p.LocalTransparencyModifier = alpha
				end
			end
		end
	end
end
function Stage:lightning()
	self:beginAttack("Ranged")
	local style = Styles["35"]
	local start = self:origin()
	style.launch(self.fx, start)
	for i = 1, 4 do
		local from = i == 1 and start or self.dummies[i - 1].root.Position
		local target = self.dummies[i].root.Position
		self:later((i - 1) * 0.14, function()
			local model, parts = style.build(self.fx, self.visual)
			local s = { model = model, parts = parts, segmentStart = from }
			self:move(0.12, function(t)
				local p = from:Lerp(target, t)
				style.update(s, CFrame.new(p), t * 0.12, self.fx)
			end, function()
				style.impact(self.fx, target, s)
				self:impact(i, Color3.fromRGB(187, 162, 255))
				model:Destroy()
				if s.bolt then
					s.bolt:destroy()
				end
			end)
		end)
	end
end
function Stage:godlyMove(mode, big)
	local now = workspace:GetServerTimeNow()
	local targets, npcs = {}, {}
	for i, d in self.dummies do
		if i > self.targetCount then
			continue
		end
		table.insert(targets, d.root.Position)
		table.insert(npcs, d.model)
	end
	if mode == "rain" or mode == "chain" then
		self:beginAttack("Ranged")
		local count = (mode == "rain" and Catalog.Godly["38"].arrows or Catalog.Godly["39"].chain)[self.tier]
		while #targets > count do
			table.remove(targets)
			table.remove(npcs)
		end
		if mode == "rain" then
			self.godly.handle(
				"Rain",
				OWNER,
				1,
				self:origin(),
				ORIGIN + Vector3.new(0, 15, -4),
				targets,
				npcs,
				now,
				0.35
			)
		else
			self.godly.handle("Chain", OWNER, 1, self:origin(), targets, npcs, now, 0.09)
		end
		for i = 1, count do
			self:later(mode == "rain" and (0.55 + i * 0.035) or i * 0.09, function()
				self:impact(i, mode == "rain" and Color3.fromRGB(148, 215, 255) or Color3.fromRGB(224, 83, 180))
			end)
		end
	elseif mode == "wraith" then
		local summon = self.serial % math.max(1, math.round(1 / Catalog.Godly["36"].ghostChance)) == 0
		self:melee("Reap")
		if not summon then
			return
		end
		self:later(0.3, function()
			local spec = Catalog.Godly["36"]
			while #self.wraithKeys >= spec.ghostCap[self.tier] do
				self.godly.handle("Fade", table.remove(self.wraithKeys, 1))
			end
			self.wraithSerial += 1
			local key = self.wraithSerial
			table.insert(self.wraithKeys, key)
			self.godly.handle("Rise", key, OWNER, targets[2], big == true, spec.ghostLife)
			self.godly.handle("Chase", key, npcs[4])
			for i = 1, math.floor((spec.ghostLife - 0.5) / spec.ghostClawEvery) do
				self:later(i * spec.ghostClawEvery, function()
					if not table.find(self.wraithKeys, key) then
						return
					end
					self.godly.handle("Claw", key, npcs[4])
					self:impact(4, Color3.fromRGB(224, 80, 104), "CLAW")
				end)
			end
			self:later(spec.ghostLife, function()
				local index = table.find(self.wraithKeys, key)
				if index then
					table.remove(self.wraithKeys, index)
					self.godly.handle("Fade", key)
				end
			end)
		end)
	elseif mode == "wisp" then
		self:melee("Diagonal")
		self:later(0.32, function()
			self.godly.handle("Wisp", OWNER, targets[2])
			self:impact(2, Color3.fromRGB(255, 102, 102), "LIFE WISP")
		end)
	elseif mode == "burst" then
		self:shoot()
		local token = self.serial
		local arrival = (targets[2] - self:origin()).Magnitude / self.weapon.projectileSpeed
		self:later(arrival, function()
			self.godly.hit(npcs[2], true, false, "41", targets[2])
			self.dummies[2].resetToken = token
			for _, part in npcs[2]:GetDescendants() do
				if part:IsA("BasePart") then
					part.LocalTransparencyModifier = 1
				end
			end
			self:later(math.min(0.35, self.weapon.cooldown * 0.5), function()
				if npcs[2].Parent and self.dummies[2].resetToken == token then
					Scene.setVisible(self.dummies[2], true)
				end
			end)
		end)
	end
end
function Stage:hatch(at)
	if self.chickenCount >= 3 then
		return
	end
	self.chickenCount += 1
	local m = Chicken.build()
	scrub(m)
	m.Name = "PreviewChicken"
	m.Parent = self.fx
	-- Same cream articulated fallback used by live EggChickens, not a second hand-made model.
	K.shards(self.fx, at, Color3.fromRGB(250, 244, 230), 9, 7, 0.5, 0.18, Enum.Material.SmoothPlastic, 0.9)
	local start = Vector3.new(at.X, ORIGIN.Y + 0.85, at.Z)
	local destination = self.dummies[3].root.Position
	local finish = Vector3.new(destination.X, ORIGIN.Y + 0.85, destination.Z + 2)
	self:move(8, function(t)
		local age = t * 8
		local p = start:Lerp(finish, math.min(1, age))
		local peck = age > 1 and math.max(0, math.sin(age * math.pi * 2 / 0.7)) or 0
		m:PivotTo(
			CFrame.lookAt(p, p - Vector3.zAxis)
				* CFrame.Angles(peck * 0.22, 0, age < 1 and math.sin(age * 20) * 0.08 or 0)
		)
	end, function()
		m:Destroy()
		self.chickenCount -= 1
	end)
	for i = 1, 7 do
		self:later(1 + i * 0.7, function()
			self:impact(3, K.Amber, "PECK")
		end)
	end
end
function Stage:legendaryMove()
	local spec = Catalog.Legendary[self.id]
	local move = spec.move
	local w = self.weapon
	-- Every prerequisite is a normal attack at the live cadence; the special replaces/adds
	-- to exactly the catalog's nth attack, without a separate fast demo or a quiet cooldown.
	self.legendaryCharge += 1
	if self.legendaryCharge < (spec.every or 1) then
		if self.id == "31" then
			self:throw("throw")
		elseif w.kind == "Melee" then
			self:melee()
		elseif self.id == "18" then
			self:arcs()
		else
			self:shoot()
		end
		self.slot:SetAttribute("LegendaryCharge", self.legendaryCharge)
		return
	end
	self.legendaryCharge = 0
	local now = workspace:GetServerTimeNow()
	local origin = self.root.Position
	local target = self.dummies[2].root.Position
	local dir = (target - origin).Unit
	self.slot:SetAttribute("LegendaryCharge", 0)
	if move == "Slash" or move == "Beam" or move == "Roll" then -- Roll: the Pizza Cutter's ghost wheel (2026-10-09)
		self:melee()
		self.legend.handle(move, self.serial, OWNER, 1, origin, dir, spec.range, spec.speed, spec.width, now)
	elseif move == "Flush" then
		self:beginAttack("Ranged")
		local list = {}
		for i = 1, spec.cards do
			local angle = math.rad((i - 3) * spec.fan / 4)
			table.insert(
				list,
				{ i, CFrame.fromAxisAngle(Vector3.yAxis, angle):VectorToWorldSpace(dir), w.range * spec.rangeScale }
			)
		end
		self.legend.handle("Flush", OWNER, 1, self:origin(), list, w.projectileSpeed, now)
	elseif move == "Split" then
		self:beginAttack("Ranged")
		local start = self:origin()
		local splitAt = start:Lerp(target, 0.45)
		local minis = {}
		for i = 1, 3 do
			table.insert(minis, { now + spec.splitAfter + 0.4, self.dummies[i].root.Position, self.dummies[i].model })
		end
		self.legend.handle(
			"Split",
			OWNER,
			1,
			start,
			splitAt,
			now,
			now + spec.splitAfter,
			minis,
			spec.radius,
			spec.spread
		)
	elseif move == "Strike" then
		local count = 0
		local fired = false
		self:throw("ball", function(at)
			count += 1
			if count >= spec.hits and not fired then
				fired = true
				self.legend.handle("Strike", OWNER, Vector3.new(at.X, ORIGIN.Y + 0.1, at.Z), spec.radius, count, now)
				self:impact(5, K.Amber, "STRIKE!")
			end
		end)
	elseif move == "Shock" then
		self:melee()
		self:later(0.18, function()
			self.legend.handle(
				"Shock",
				OWNER,
				Vector3.new(self.dummies[2].root.Position.X, ORIGIN.Y + 0.1, self.dummies[2].root.Position.Z),
				spec.radius,
				spec.time,
				now
			)
		end)
	elseif move == "Thunder" then
		self:throw("throw", function(at)
			self.legend.handle(
				"Thunder",
				OWNER,
				Vector3.new(at.X, ORIGIN.Y + 0.1, at.Z),
				spec.radius,
				workspace:GetServerTimeNow() + spec.delay
			)
		end)
	end
	if move ~= "Strike" then
		for i = 1, 5 do
			self:later(0.45 + i * 0.035, function()
				self:impact(i, K.Amber)
			end)
		end
	end
end
function Stage:cadence()
 if self.id == "17" then return Special.duckTiming(self.weapon.cooldown).cycle end
	local _, _, duration = Motion.attackTiming(self.id, self.attackKind or self.weapon.kind, self.style)
	return math.max(self.weapon.cooldown, duration / self.weapon.motionRate)
end
function Stage:sequence()
	local mode = self.variant.mode
	if mode == "legendary" then
		self:legendaryMove()
	elseif mode == "melee" then
		self:melee(self.variant.style or self.entry.styles and self.entry.styles[self.serial % #self.entry.styles + 1])
	elseif self.id == "15" and (mode == "throw" or mode == "hatch") then
		-- One illustrative hatch per eight eggs in both modes. The dedicated hatch view
		-- starts with its trigger; normal playback shows it early enough to discover.
		local hatch = self.serial % 8 == (mode == "hatch" and 0 or 2)
		self:throw("throw", function(at)
			if hatch then
				self:hatch(at)
			end
		end)
	elseif mode == "throw" or mode == "ball" then
		self:throw(mode)
	elseif mode == "cards" or mode == "pandora" then
		self:arcs()
	elseif mode == "fire" or mode == "water" or mode == "vacuum" then
		self:stream(mode)
	elseif mode == "poison" then
		self:beginAttack("Ranged")
		local start = self:origin()
		local target = self.dummies[2].root.Position
		local duration = Special.duration(start, target, self.weapon.projectileSpeed)
		local key = "ShowcasePoison_" .. self.serial
		self.specialFX.handle(
			"Launch",
			key,
			"08",
			OWNER,
			1,
			1,
			start,
			target,
			workspace:GetServerTimeNow(),
			duration,
			Special.profiles["08"].height
		)
		self:later(duration, function()
			self.specialFX.handle("End", key)
			self:zone(target, "Poison")
		end)
	elseif mode == "lightning" then
		self:lightning()
	elseif mode == "rain" or mode == "chain" or mode == "wraith" or mode == "wisp" or mode == "burst" then
		self:godlyMove(mode, self.variant.big)
	else
		self:shoot()
	end
end
function Stage:step(dt)
	if self.closed then
		return
	end
	if self.assetsReady == false then
		return
	end
	self.clock += math.min(dt, 0.1)
	if
		self.visual
		and not self.returning
		and self.clock >= self.nextAttackAt
		and (self.demoRemaining > 0 or self.autoplay)
	then
		if self.demoRemaining <= 0 then
			self.demoRemaining = self.variant.mode == "legendary" and (Catalog.Legendary[self.id].every or 1) or 1
		end
		self:sequence()
		self.demoRemaining -= 1
		if self.demoRemaining == 0 then
			self.completedDemos += 1
		end
		self.duration = self:cadence()
		self.cycleStarted = self.clock
		self.nextAttackAt = self.clock + self.duration
		self.nextCycle = self.nextAttackAt
	end
	for i = #self.events, 1, -1 do
		if self.events[i].at <= self.clock then
			local e = table.remove(self.events, i)
			e.fn()
		end
	end
	for i = #self.movers, 1, -1 do
		local m = self.movers[i]
		local t = math.clamp((self.clock - m.born) / m.duration, 0, 1)
		m.update(t)
		if t >= 1 then
			table.remove(self.movers, i)
			if m.finish then
				m.finish()
			end
		end
	end
	if self.visual then
		self:pose(dt)
		self:stepStream()
	end
	for _, d in self.dummies do
		local age = self.clock - d.hit
		local hit = math.clamp(1 - age / 0.28, 0, 1)
		if d.highlight then
			d.highlight.FillTransparency = 1 - hit * 0.55
			d.highlight.FillColor = d.color or GREEN
		end
		if not self.pulling then
			d.model:PivotTo(
				CFrame.new(d.ground)
					* CFrame.Angles(math.sin(age * 25) * hit * 0.045, 0, 0)
					* CFrame.new(0, d.footOffset + 0.015, 0)
					* d.rest.Rotation
			)
		end
	end
end
function Stage:status()
	return {
		loading = self.assetsReady == false,
		id = self.id,
		tier = self.tier,
		variant = self.variant and self.variant.key,
		hits = self.hits,
		attacks = self.serial,
		interval = self.visual and self:cadence() or 0,
		completedDemos = self.completedDemos,
		streamActive = self.streamMode ~= nil,
		movers = #self.movers,
		pending = #self.events,
		progress = self.nextCycle
				and math.clamp(1 - (self.nextCycle - self.clock) / math.max(0.001, self.duration), 0, 1)
			or 0,
		closed = self.closed,
	}
end
function Stage:destroy()
	if self.closed then
		return
	end
	self.closed = true
	self:clearTake()
	self.folder:Destroy()
	table.clear(self.dummies)
end
return Stage
