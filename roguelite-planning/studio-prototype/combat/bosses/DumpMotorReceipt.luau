-- Edit-mode only, read-only: the receipt of a Motor6D boss template for partposes_to_motor6d.py (R9,
-- 2026-10-04: the old Hammer, ServerStorage.RogueliteNPCs.HammerBoss_NPC). Writes nothing to Studio;
-- the JSON goes to the dev server (tools/dev_server.py, %TEMP%/roguelite-gui-dumps/<name>.json):
--   NAME='HammerBoss_NPC'; DUMP='hammer-old-receipt'   then paste this file into execute_luau (Edit)
-- Every CFrame is relative to the HumanoidRootPart, as {x,y,z,R00..R22} rounded to 1e-7. bindName is
-- what EnemyMotion.bind calls the joint: its EnemyBone attribute, else its name minus "Motor6D".
assert(not game:GetService("RunService"):IsRunning(), "Dump in Edit mode")
local HS = game:GetService("HttpService")
local Tags = game:GetService("CollectionService")
local NAME, DUMP = NAME or "HammerBoss_NPC", DUMP or "hammer-old-receipt"
local npc = assert(game.ServerStorage.RogueliteNPCs:FindFirstChild(NAME), "missing RogueliteNPCs." .. NAME)
local root = assert(npc:FindFirstChild("HumanoidRootPart"), "missing HumanoidRootPart")
local function r(v)
	return math.round(v * 1e7) / 1e7
end
local function cf(c)
	local t = { c:GetComponents() }
	for i, v in t do
		t[i] = r(v)
	end
	return t
end
local function v3(v)
	return { r(v.X), r(v.Y), r(v.Z) }
end
local function value(v)
	local t = typeof(v)
	if t == "CFrame" then
		return cf(v)
	elseif t == "Vector3" then
		return v3(v)
	elseif t == "Color3" then
		return { r(v.R), r(v.G), r(v.B) }
	elseif t == "number" or t == "string" or t == "boolean" then
		return v
	end
	return tostring(v)
end
local function attributes(inst)
	local out = {}
	for k, v in inst:GetAttributes() do
		out[k] = { t = typeof(v), v = value(v) }
	end
	return out
end
local function read(inst, prop)
	local ok, v = pcall(function()
		return inst[prop]
	end)
	return ok and value(v) or nil
end
local parts, motors, other = {}, {}, {}
local low = math.huge
for _, d in npc:GetDescendants() do
	if d:IsA("BasePart") then
		local surface = d:FindFirstChildOfClass("SurfaceAppearance")
		local p = {
			name = d.Name,
			class = d.ClassName,
			parent = d.Parent == npc and "" or d.Parent.Name,
			size = v3(d.Size),
			cframe = cf(root.CFrame:ToObjectSpace(d.CFrame)),
			material = d.Material.Name,
			color = value(d.Color),
			transparency = d.Transparency,
			anchored = d.Anchored,
			canCollide = d.CanCollide,
			canQuery = d.CanQuery,
			canTouch = d.CanTouch,
			massless = d.Massless,
			castShadow = d.CastShadow,
			attributes = attributes(d),
		}
		if d:IsA("MeshPart") then
			p.meshId, p.textureId, p.meshSize = d.MeshId, d.TextureID, v3(d.MeshSize)
			p.renderFidelity = d.RenderFidelity.Name
			for _, corner in { -1, 1 } do
				for _, y in { -1, 1 } do
					for _, z in { -1, 1 } do
						low = math.min(low, (d.CFrame * (d.Size * 0.5 * Vector3.new(corner, y, z))).Y)
					end
				end
			end
		end
		if surface then
			p.surfaceAppearance = {
				colorMap = read(surface, "ColorMap"),
				normalMap = read(surface, "NormalMap"),
				metalnessMap = read(surface, "MetalnessMap"),
				roughnessMap = read(surface, "RoughnessMap"),
				alphaMode = read(surface, "AlphaMode"),
				color = read(surface, "Color"),
			}
		end
		table.insert(parts, p)
	elseif d:IsA("Motor6D") then
		table.insert(motors, {
			name = d.Name,
			bindName = d:GetAttribute("EnemyBone") or (d.Name:gsub("Motor6D$", "")),
			parent = d.Parent.Name,
			part0 = d.Part0 and d.Part0.Name,
			part1 = d.Part1 and d.Part1.Name,
			c0 = cf(d.C0),
			c1 = cf(d.C1),
			transform = cf(d.Transform),
			enabled = d.Enabled,
			attributes = attributes(d),
		})
	else
		table.insert(other, { class = d.ClassName, name = d.Name, parent = d.Parent.Name, attributes = attributes(d) })
	end
end
table.sort(parts, function(a, b)
	return a.name < b.name
end)
table.sort(motors, function(a, b)
	return a.name < b.name
end)
local h = npc:FindFirstChildOfClass("Humanoid")
local receipt = {
	id = NAME,
	dumpedAt = os.date("!%Y-%m-%dT%H:%M:%SZ"),
	scale = npc:GetScale(),
	pivot = cf(npc:GetPivot()),
	rootCFrame = cf(root.CFrame),
	primaryPart = npc.PrimaryPart and npc.PrimaryPart.Name,
	attributes = attributes(npc),
	tags = Tags:GetTags(npc),
	rootAboveSoles = r(root.Position.Y - low),
	humanoid = h and {
		hipHeight = h.HipHeight,
		rigType = h.RigType.Name,
		maxHealth = h.MaxHealth,
		health = h.Health,
		walkSpeed = h.WalkSpeed,
		automaticScalingEnabled = h.AutomaticScalingEnabled,
		requiresNeck = h.RequiresNeck,
		breakJointsOnDeath = h.BreakJointsOnDeath,
		displayDistanceType = h.DisplayDistanceType.Name,
		animator = h:FindFirstChildOfClass("Animator") ~= nil,
	} or nil,
	parts = parts,
	motors = motors,
	other = other,
}
local json = HS:JSONEncode(receipt)
HS:PostAsync("http://127.0.0.1:8934/dump/" .. DUMP, json)
return string.format("%s: %d parts, %d motors, %d other, scale %s, %d chars posted to /dump/%s", NAME, #parts, #motors, #other, tostring(receipt.scale), #json, DUMP)
