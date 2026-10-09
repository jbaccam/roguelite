-- Edit-time installer for the round 10 Bloater (Pine Valley, POP GOES THE ZOMBIE). Run through
-- execute_luau in Edit, with tools/dev_server.py on 127.0.0.1:8934 (it serves bloater-import-data.json):
--   loadstring(game.HttpService:GetAsync('http://127.0.0.1:8934/bloater-zombie/InstallBloater.luau'))()(source)
-- source: the Model Studio's 3D Importer made from BloaterZombie_Import.fbx (15 unskinned R15
-- sections + EyeGlow). Same construction as baby-mutant-zombies/InstallZombieVariants: the importer's
-- uniform scale and axis rotation are solved from the section centres, every section is placed at
-- its authored centre, and the 15 Motor6Ds come from the authored joints. Plus: EyeGlow welded to the
-- Head (Neon), SurfaceAppearance colour maps moved to TextureID (MCP-era SurfaceAppearances render
-- blank in Play), the template built at model scale 1 (a Humanoid's walk force scales with it), and
-- the round 10 attributes (Exploder). The raw import is kept; an older template is moved aside.
return function(source, server)
	assert(game.PlaceId == 107877054949326, "Installer is scoped to the roguelite place")
	assert(not game:GetService("RunService"):IsRunning(), "Install in Edit mode")
	local HS = game:GetService("HttpService")
	local data = HS:JSONDecode(HS:GetAsync((server or "http://127.0.0.1:8934/") .. "bloater-zombie/bloater-import-data.json?t=" .. os.clock(), true)).Bloater
	local Types = require(game.ReplicatedStorage.RogueliteCombat.ZombieTypes)
	local config = Types.Bloater
	assert(config, "Sync ZombieTypes (T.Bloater) first")
	local function vec(a) return Vector3.new(a[1], a[2], a[3]) end
	local function motorName(name)
		if name == "LowerTorso" then return "Root" elseif name == "UpperTorso" then return "Waist" elseif name == "Head" then return "Neck" end
		for _, pair in { { "UpperArm", "Shoulder" }, { "LowerArm", "Elbow" }, { "Hand", "Wrist" }, { "UpperLeg", "Hip" }, { "LowerLeg", "Knee" }, { "Foot", "Ankle" } } do
			if name:sub(-#pair[1]) == pair[1] then return name:sub(1, #name - #pair[1]) .. pair[2] end
		end
	end
	local found, extras, count = {}, {}, 0
	for _, obj in source:GetDescendants() do
		if obj:IsA("MeshPart") then
			if data.parts[obj.Name] then
				assert(not found[obj.Name], "Duplicate imported section " .. obj.Name)
				found[obj.Name] = obj
				count += 1
			elseif data.extras and data.extras[obj.Name] then
				extras[obj.Name] = obj
			end
		end
	end
	assert(count == 15, "Expected 15 named sections, found " .. count)
	-- The importer's uniform scale and axis rotation, from all section centres.
	local meanA, meanB = Vector3.zero, Vector3.zero
	for name, obj in found do meanA += obj.Position; meanB += vec(data.parts[name].center) end
	meanA /= 15; meanB /= 15
	local aa, bb = 0, 0
	for name, obj in found do aa += (obj.Position - meanA).Magnitude ^ 2; bb += (vec(data.parts[name].center) - meanB).Magnitude ^ 2 end
	local scale = math.sqrt(bb / aa)
	local directions = { Vector3.xAxis, -Vector3.xAxis, Vector3.yAxis, -Vector3.yAxis, Vector3.zAxis, -Vector3.zAxis }
	local best, cost = nil, math.huge
	for _, right in directions do
		for _, up in directions do
			if math.abs(right:Dot(up)) < 0.01 then
				local rot = CFrame.fromMatrix(Vector3.zero, right, up, right:Cross(up))
				local e = 0
				for name, obj in found do e += ((rot:VectorToWorldSpace(obj.Position - meanA) * scale) - (vec(data.parts[name].center) - meanB)).Magnitude ^ 2 end
				if e < cost then best, cost = rot, e end
			end
		end
	end
	assert(math.sqrt(cost / 15) < 0.15, "Imported layout does not match the authored geometry (" .. math.sqrt(cost / 15) .. ")")
	local templates = assert(game.ServerStorage:FindFirstChild("RogueliteNPCs"), "Missing RogueliteNPCs")
	local old = templates:FindFirstChild(config.template)
	if old then
		local history = game.ServerStorage:FindFirstChild("RogueliteNPCsHistory") or Instance.new("Folder")
		history.Name = "RogueliteNPCsHistory"; history.Parent = game.ServerStorage
		old.Name = config.template .. "_before_" .. os.date("%Y%m%d_%H%M%S"); old.Parent = history
	end
	local function flatten(p)
		for _, sa in p:GetChildren() do
			if sa:IsA("SurfaceAppearance") then
				if p.TextureID == "" and sa.ColorMap ~= "" then p.TextureID = sa.ColorMap end
				sa:Destroy()
			elseif not sa:IsA("SpecialMesh") then sa:Destroy() end
		end
	end
	local npc = Instance.new("Model"); npc.Name = config.template
	local parts = {}
	local function place(name, obj, center)
		local p = obj:Clone(); flatten(p)
		p.Size = obj.Size * scale; p.CFrame = CFrame.new(center) * (best * obj.CFrame.Rotation)
		p.Color = Color3.new(1, 1, 1); p.Anchored = false; p.CanCollide = false; p.CanTouch = false; p.CanQuery = true; p.Massless = true
		p.Name = name; p.Parent = npc
		return p
	end
	for name, obj in found do parts[name] = place(name, obj, vec(data.parts[name].center)) end
	local root = Instance.new("Part"); root.Name = "HumanoidRootPart"; root.Transparency = 1
	root.Size = Vector3.new(2.4, 2, 1.6)
	root.CFrame = CFrame.new(0, data.rootHeight, 0); root.CanCollide = true; root.CanQuery = false; root.CanTouch = false
	root.Anchored = true; root.Parent = npc; parts.HumanoidRootPart = root; npc.PrimaryPart = root
	for name, j in data.joints do
		local a, b = parts[j.parent], parts[name]
		local frame = CFrame.new(vec(j.head))
		local m = Instance.new("Motor6D"); m.Name = motorName(name); m.Part0 = a; m.Part1 = b
		m.C0 = a.CFrame:ToObjectSpace(frame); m.C1 = b.CFrame:ToObjectSpace(frame); m.Parent = a
	end
	-- The glowing eyes: Neon, welded to the Head (they scale with it in the swell, Round10World).
	for name, obj in extras do
		local e = data.extras[name]
		local p = place(name, obj, vec(e.center))
		p.Material = Enum.Material.Neon; p.TextureID = ""; p.Color = Color3.fromRGB(255, 226, 92)
		local host = parts[e.weldTo or "Head"]
		local w = Instance.new("WeldConstraint"); w.Part0 = host; w.Part1 = p; w.Parent = p
	end
	local h = Instance.new("Humanoid"); h.RigType = Enum.HumanoidRigType.R15; h.AutomaticScalingEnabled = false
	h.HipHeight = data.rootHeight - root.Size.Y / 2; h.BreakJointsOnDeath = false; h.RequiresNeck = true
	h.MaxHealth = config.health; h.Health = config.health; h.WalkSpeed = config.speed; h.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	h.Parent = npc; Instance.new("Animator", h)
	for key, value in { ZombieType = "Bloater", EnemyId = "bloater", Exploder = true, BaseMoveSpeed = config.speed, ContactDamage = 0, ContactRange = config.contactRange,
		SourceAsset = "bloater-zombie/BloaterZombie_Import.fbx" } do npc:SetAttribute(key, value) end
	npc.Parent = templates
	assert(math.abs(npc:GetScale() - 1) < 1e-6, "Template must sit at model scale 1")
	return { name = npc.Name, parts = count, extras = #(function() local t = {}; for k in extras do table.insert(t, k) end; return t end)(), scale = scale, alignmentError = math.sqrt(cost / 15), height = data.height }
end
