-- The weapon preview uses the player's real avatar, the lobby's reviewed practice-dummy mesh,
-- and a local clone of the actual ChestIsland with its chest/reward stations removed.
-- No substitute figures/scenery, gameplay tags, remotes, scripts, combat services or physics.
local Players = game:GetService("Players")
local Tags = game:GetService("CollectionService")
local Scene = {}
Scene.__index = Scene
Scene.MaxDummies = 7
Scene.Lane = { minX = -18, maxX = 18, minZ = -28, maxZ = 28 }
local ROTATION = CFrame.Angles(0, math.pi / 2, 0)
local BODY_FEET = { LeftFoot = true, RightFoot = true, ["Left Leg"] = true, ["Right Leg"] = true }

local function finite(n)
	return type(n) == "number" and n == n and math.abs(n) < math.huge
end

-- Returns exact real sources, including the runtime dummy wrapper's mesh. A missing streamed
-- asset is a clean error for the UI to retry; no generic fallback is manufactured.
function Scene.sources(lobby, player)
	lobby = lobby or workspace:FindFirstChild("RogueliteLobby")
	player = player or Players.LocalPlayer
	local island = lobby and lobby:FindFirstChild("ChestIsland")
	local ground = island and island:FindFirstChild("Ground")
	local top = ground and ground:FindFirstChild("Island_South_4_Top")
	local cliff = ground and ground:FindFirstChild("Island_South_4_Cliff")
	local scenery = lobby and lobby:FindFirstChild("Scenery")
	if not island or not island:IsA("Model") or not top or not top:IsA("MeshPart") or not cliff then
		return nil, "The lobby chest island is still loading. Reopen the weapon preview in a moment."
	end
	local dummy
	if scenery then
		for _, name in { "Practice_Dummy_85", "Practice_Dummy_84" } do
			local source = scenery:FindFirstChild(name)
			if source and source:IsA("BasePart") and source:GetAttribute("Asset") == "Practice_Dummy" then
				dummy = source
				break
			elseif source then
				for _, child in source:GetDescendants() do
					if child:IsA("BasePart") and child:GetAttribute("Asset") == "Practice_Dummy" then
						dummy = child
						break
					end
				end
				if dummy then
					break
				end
			end
		end
		if not dummy then
			for _, child in scenery:GetDescendants() do
				if child:IsA("BasePart") and child:GetAttribute("Asset") == "Practice_Dummy" then
					dummy = child
					break
				end
			end
		end
	end
	if not dummy then
		return nil, "The real lobby practice dummy is still loading. Reopen the weapon preview in a moment."
	end
	local avatar = player and player.Character
	local root = avatar and avatar:FindFirstChild("HumanoidRootPart")
	if not root or not root:IsA("BasePart") or not avatar:FindFirstChildOfClass("Humanoid") then
		return nil, "Your avatar is still loading. Reopen the weapon preview once your character appears."
	end
	return { island = island, top = top, dummy = dummy, avatar = avatar }
end

local function clone(source)
	local was = source.Archivable
	source.Archivable = true
	local ok, copy = pcall(function()
		return source:Clone()
	end)
	source.Archivable = was
	assert(ok and copy, "Could not copy " .. source:GetFullName())
	return copy
end

local function interaction(instance)
	return instance:IsA("LuaSourceContainer")
		or instance:IsA("RemoteEvent")
		or instance:IsA("RemoteFunction")
		or instance:IsA("UnreliableRemoteEvent")
		or instance:IsA("BindableEvent")
		or instance:IsA("BindableFunction")
		or instance:IsA("ProximityPrompt")
		or instance:IsA("ClickDetector")
		or instance:IsA("TouchTransmitter")
		or instance:IsA("Tool")
		or instance:IsA("ForceField")
		or instance:IsA("Sound")
		or instance:IsA("BillboardGui")
		or instance:IsA("SurfaceGui")
		or instance:IsA("ScreenGui")
		or instance:IsA("Constraint")
		or instance:IsA("WeldConstraint")
		or instance:IsA("BodyMover")
end

-- Scrub while detached, before tags or scripts can enter the scene's DataModel ancestry.
-- Shirt/Pants/BodyColors/CharacterMesh, Accessories, wrap layers, face decals and surface textures
-- are deliberately preserved. Only the avatar keeps its inert Humanoid for clothing rendering.
function Scene.scrub(model, avatar)
	local list = { model }
	for _, child in model:GetDescendants() do
		table.insert(list, child)
	end
	for _, child in list do
		if child ~= model and not child:IsDescendantOf(model) then
			continue
		end
		for _, tag in Tags:GetTags(child) do
			Tags:RemoveTag(child, tag)
		end
		for name in child:GetAttributes() do
			-- Roblox inserts protected appearance metadata (e.g. RBXRefinementScale). It is
			-- necessary for the imported avatar and is not gameplay state we may remove.
			if not name:match("^RBX") then
				pcall(function()
					child:SetAttribute(name, nil)
				end)
			end
		end
		local externalJoint = child:IsA("JointInstance")
			and (
				not child.Part0
				or not child.Part1
				or not child.Part0:IsDescendantOf(model)
				or not child.Part1:IsDescendantOf(model)
			)
		if
			interaction(child)
			or externalJoint
			or (not avatar and (child:IsA("Humanoid") or child:IsA("Animator") or child:IsA("AnimationController")))
		then
			child:Destroy()
		elseif
			child:IsA("Model")
			and child ~= model
			and (child.Name:match("^Weapon_") or child.Name:match("^Reserve%d"))
		then
			child:Destroy()
		elseif child:IsA("BasePart") then
			child.Anchored = true
			child.CanCollide = false
			child.CanQuery = false
			child.CanTouch = false
			child.AssemblyLinearVelocity = Vector3.zero
			child.AssemblyAngularVelocity = Vector3.zero
			child.LocalTransparencyModifier = 0
			child.CastShadow = true
		elseif child:IsA("ParticleEmitter") or child:IsA("Beam") or child:IsA("Trail") then
			child.Enabled = false
		elseif child:IsA("Humanoid") then
			child.EvaluateStateMachine = false
			child.AutoRotate = false
			child.BreakJointsOnDeath = false
			child.RequiresNeck = false
			-- UI modules use the same avatar-display capabilities as ArmoryStage. No avatar height or
			-- scale property is needed for grounding; it comes from the actual cloned feet below.
			child.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
			child.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
		end
	end
end

local function lowerY(part)
	local cf, size = part.CFrame, part.Size * 0.5
	return cf.Y
		- math.abs(cf.RightVector.Y) * size.X
		- math.abs(cf.UpVector.Y) * size.Y
		- math.abs(cf.LookVector.Y) * size.Z
end

-- Reset copied movement transforms into the avatar's own neutral rig pose. Traversing the actual
-- joints also preserves accessory weld offsets. Every part remains anchored and nonphysical.
local function neutralRig(model, root)
	local edges = {}
	for _, child in model:GetDescendants() do
		if
			(child:IsA("JointInstance") or child:IsA("WeldConstraint"))
			and child.Part0
			and child.Part1
			and child.Part0:IsDescendantOf(model)
			and child.Part1:IsDescendantOf(model)
		then
			if child:IsA("Motor6D") then
				child.Transform = CFrame.identity
			end
			local relative = child:IsA("JointInstance") and child.C0 * child.C1:Inverse()
				or child.Part0.CFrame:ToObjectSpace(child.Part1.CFrame)
			table.insert(edges, { a = child.Part0, b = child.Part1, cf = relative })
		end
	end
	local known = { [root] = true }
	for _ = 1, #edges + 1 do
		local changed = false
		for _, edge in edges do
			if known[edge.a] and not known[edge.b] then
				edge.b.CFrame = edge.a.CFrame * edge.cf
				known[edge.b] = true
				changed = true
			elseif known[edge.b] and not known[edge.a] then
				edge.a.CFrame = edge.b.CFrame * edge.cf:Inverse()
				known[edge.a] = true
				changed = true
			end
		end
		if not changed then
			break
		end
	end
end

local function record(model, root, target, avatar)
	root.PivotOffset = CFrame.identity
	model.PrimaryPart = root
	local foot = math.huge
	if avatar then
		for _, child in model:GetChildren() do
			if child:IsA("BasePart") and BODY_FEET[child.Name] then
				foot = math.min(foot, lowerY(child))
			end
		end
	end
	if foot == math.huge then
		for _, child in model:GetDescendants() do
			if child:IsA("BasePart") and child ~= root and not child:FindFirstAncestorOfClass("Accessory") then
				foot = math.min(foot, lowerY(child))
			end
		end
	end
	assert(foot < math.huge, "Preview model has no visible foot geometry")
	local cf, bounds = model:GetBoundingBox()
	return {
		model = model,
		root = root,
		target = target,
		baseColor = target and target.Color,
		footOffset = root.Position.Y - foot,
		bounds = bounds,
		boundsCenter = root.CFrame:PointToObjectSpace(cf.Position),
		rest = root.CFrame,
		hit = -100,
		visible = true,
		avatar = avatar == true,
	}
end

function Scene.repositionRoot(item, cf)
	assert(typeof(cf) == "CFrame", "Preview root pose must be a CFrame")
	-- PrimaryPart's pivot was normalized on the clone, so PivotTo moves all anchored limbs/meshes.
	item.model:PivotTo(cf)
end

function Scene.setVisible(item, visible)
	item.visible = visible == true
	for _, child in item.model:GetDescendants() do
		if child:IsA("BasePart") then
			child.LocalTransparencyModifier = item.visible and 0 or 1
		end
	end
end

function Scene:groundAt(x, z)
	local start = self.origin + Vector3.new(x, 24, z)
	local hit = workspace:Raycast(start, Vector3.new(0, -64, 0), self.groundParams)
	if hit and hit.Normal.Y > 0.55 then
		return hit.Position
	end
	return nil
end

function Scene.place(item, x, z, facing)
	assert(finite(x) and finite(z), "Preview lane coordinates must be finite")
	local scene = assert(item.scene, "Preview actor is not attached to a scene")
	local ground = scene:groundAt(x, z)
	if not ground then
		return false, "The requested preview position is outside the island's grass surface."
	end
	local rotation = CFrame.identity
	if typeof(facing) == "Vector3" then
		local flat = Vector3.new(facing.X, 0, facing.Z)
		if flat.Magnitude > 0.001 then
			rotation = CFrame.lookAt(Vector3.zero, flat.Unit)
		end
	elseif typeof(facing) == "CFrame" then
		rotation = facing.Rotation
	elseif finite(facing) then
		rotation = CFrame.Angles(0, facing, 0)
	end
	local cf = CFrame.new(ground + Vector3.yAxis * (item.footOffset + 0.015)) * rotation
	Scene.repositionRoot(item, cf)
	item.rest = cf
	item.ground = ground
	return true
end

function Scene:createDummy(name, x, z, facing)
	if #self.dummies >= Scene.MaxDummies then
		return nil, "Preview dummy limit reached"
	end
	local mesh = clone(self.dummySource)
	Scene.scrub(mesh, false)
	mesh.Name = "LobbyPracticeDummyMesh"
	mesh.CFrame = CFrame.identity
	local model = Instance.new("Model")
	model.Name = name or "LobbyPracticeDummy"
	mesh.Parent = model
	local root = Instance.new("Part")
	root.Name = "HumanoidRootPart"
	root.Size = Vector3.one
	-- The reviewed dummy's painted front is local +Z. Normalize the cosmetic root so its
	-- LookVector is the face direction, just like the real player avatar's root.
	root.CFrame = CFrame.Angles(0, math.pi, 0)
	root.Transparency = 1
	root.Anchored = true
	root.CanCollide = false
	root.CanTouch = false
	root.CanQuery = false
	root.CastShadow = false
	root.Parent = model
	local item = record(model, root, mesh, false)
	item.scene = self
	local highlight = Instance.new("Highlight")
	highlight.Name = "PreviewHit"
	highlight.Adornee = model
	highlight.FillTransparency = 1
	highlight.OutlineTransparency = 1
	highlight.DepthMode = Enum.HighlightDepthMode.Occluded
	highlight.Parent = model
	item.highlight = highlight
	model.Parent = self.actors
	local ok, reason = Scene.place(item, x or 0, z or -10, facing or Vector3.zAxis)
	if not ok then
		model:Destroy()
		return nil, reason
	end
	table.insert(self.dummies, item)
	return item
end

function Scene.new(parent, origin, player)
	assert(parent and typeof(origin) == "Vector3", "Preview scene requires a local parent and world origin")
	local sources, reason = Scene.sources(nil, player)
	if not sources then
		return nil, reason
	end
	local self = setmetatable({
		origin = origin,
		groundY = origin.Y,
		dummies = {},
		dummySource = sources.dummy,
		backdrop = "LobbyChestIsland",
		lane = table.clone(Scene.Lane),
		islandScale = 1,
	}, Scene)
	local folder = Instance.new("Folder")
	folder.Name = "WeaponShowcaseScene"
	self.folder = folder
	local ok, err = xpcall(function()
		local island = clone(sources.island)
		for _, child in island:GetChildren() do
			if child.Name ~= "Ground" and child.Name ~= "Dressing" then
				child:Destroy()
			end
		end
		Scene.scrub(island, false)
		island.Name = "LobbyChestIslandBackdrop"
		self.island = island
		island.Parent = folder
		local top = assert(island.Ground:FindFirstChild("Island_South_4_Top"), "Chest island grass is missing")
		local originalPivot = island:GetPivot()
		local topOffset = top.Position.Y + top.Size.Y * 0.5 - originalPivot.Y
		island:PivotTo(CFrame.new(origin - Vector3.yAxis * topOffset) * ROTATION)
		-- Retain the real grass mesh as a query-only cosmetic surface; nothing can collide with it.
		top.CanQuery = true
		self.ground = top
		local params = RaycastParams.new()
		params.FilterType = Enum.RaycastFilterType.Include
		params.FilterDescendantsInstances = { top }
		params.RespectCanCollide = false
		self.groundParams = params
		folder.Parent = parent
		local actual = assert(self:groundAt(0, 0), "The real chest-island grass surface is not ready")
		island:PivotTo(island:GetPivot() + Vector3.yAxis * (origin.Y - actual.Y))
		-- Compose the existing island's foliage around the lane, not across it. The open
		-- middle remains readable while trees, flowers and the authored rocks frame the view.
		local dressing = island:FindFirstChild("Dressing")
		if dressing then
			local treeSpots = { { -23, -18 }, { -25, 4 }, { -15, -32 }, { 15, -33 }, { 26, -19 }, { -20, 23 } }
			local edgeSpots =
				{ { -20, -7 }, { -19, 9 }, { -17, 20 }, { 23, -8 }, { 24, -24 }, { -8, -33 }, { 9, -32 }, { 19, 24 } }
			local treeIndex, edgeIndex = 0, 0
			local function groundProp(prop, x, z, yaw)
				local floor = self:groundAt(x, z)
				if not floor then
					prop:Destroy()
					return
				end
				prop.CFrame = CFrame.new(floor + Vector3.yAxis * (prop.Position.Y - lowerY(prop)))
					* CFrame.Angles(0, yaw or 0, 0)
			end
			for _, prop in dressing:GetChildren() do
				if prop:IsA("BasePart") then
					if prop.Name:find("Tree") then
						treeIndex += 1
						local spot = treeSpots[treeIndex]
						if spot then
							groundProp(prop, spot[1], spot[2], treeIndex * 1.7)
						else
							prop:Destroy()
						end
					elseif prop.Name:find("Lantern") then
						prop:Destroy()
					else
						edgeIndex += 1
						local spot = edgeSpots[(edgeIndex - 1) % #edgeSpots + 1]
						local offset = math.floor((edgeIndex - 1) / #edgeSpots) * 1.8
						groundProp(prop, spot[1] + offset, spot[2] + offset, edgeIndex * 2.4)
					end
				end
			end
			local pedestal = sources.island:FindFirstChild("Pedestals")
			local stone = pedestal and pedestal:FindFirstChild("Boulder_2_594", true)
			if stone and stone:IsA("BasePart") then
				for i, spot in { { -22, -25 }, { 23, -27 }, { -24, 16 } } do
					local rock = clone(stone)
					Scene.scrub(rock, false)
					rock.Name = "LobbyBoulder" .. i
					rock.Size *= i == 3 and 0.48 or 0.65
					rock.Parent = dressing
					groundProp(rock, spot[1], spot[2], i * 1.3)
				end
			end
			-- Far-edge decoration never alters the queryable grass or the gameplay island.
			for _, prop in dressing:GetChildren() do
				if prop:IsA("BasePart") then
					local p = prop.Position - origin
					if math.abs(p.X) < 13 and p.Z > -28 and p.Z < 22 then
						prop:Destroy()
					end
				end
			end
		end
		local actors = Instance.new("Folder")
		actors.Name = "Actors"
		actors.Parent = folder
		self.actors = actors
		local avatar = clone(sources.avatar)
		-- Remove source combat attachments before their identifying attributes are scrubbed.
		for _, child in avatar:GetChildren() do
			if child:IsA("Model") and child:GetAttribute("WeaponId") then
				child:Destroy()
			end
		end
		local root = assert(avatar:FindFirstChild("HumanoidRootPart"), "The cloned avatar has no root")
		-- Capture internal accessory constraint offsets while detached, then strip the constraints.
		-- Never traverse joints referring outside the clone (e.g. a live equipped-tool weld).
		neutralRig(avatar, root)
		Scene.scrub(avatar, true)
		avatar.Name = "PlayerAvatar"
		avatar.Parent = actors
		-- Roblox's avatar joint upgrade may synchronously regenerate AnimationConstraint,
		-- BallSocketConstraint and accessory rigid joints on Workspace parenting, and initialize
		-- torso collision, even when EvaluateStateMachine is false. Normalize the complete
		-- cosmetic physical state after insertion; clothing and the copied pose stay intact.
		for _, child in avatar:GetDescendants() do
			if child:IsA("Constraint") or child:IsA("WeldConstraint") then
				child:Destroy()
			elseif child:IsA("BasePart") then
				child.Anchored = true
				child.CanCollide = false
				child.CanQuery = false
				child.CanTouch = false
			end
		end
		self.presenter = record(avatar, root, nil, true)
		self.presenter.scene = self
		self.root = root
		assert(Scene.place(self.presenter, 0, 12, -Vector3.zAxis))
		local spots = { { -6, -8 }, { 0, -10 }, { 6, -8 }, { -7, -17 }, { 0, -20 }, { 7, -17 }, { 0, -27 } }
		for i, p in spots do
			local item, why = self:createDummy("LobbyPracticeDummy" .. i, p[1], p[2], Vector3.zAxis)
			assert(item, why)
			Scene.setVisible(item, i <= 3)
		end
		self.sourceIsland = sources.island:GetFullName()
		self.sourceDummy = sources.dummy:GetFullName()
	end, debug.traceback)
	if not ok then
		folder:Destroy()
		return nil, "The real lobby preview could not be prepared: " .. tostring(err)
	end
	return self
end

function Scene:destroy()
	if self.folder then
		self.folder:Destroy()
	end
	self.dummies = {}
	self.presenter = nil
	self.root = nil
end

return Scene
