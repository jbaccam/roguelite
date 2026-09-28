-- Builds Workspace.RogueliteLobby.ChestIsland: a floating island east of the lobby's east island
-- (next to the Rewards station) holding the five chests on stepped stone pedestals in an arc that
-- faces the lobby. Built only from the lobby's own reviewed meshes (island top/cliff, portal pad,
-- boulders, trees, lanterns, plants) plus ReplicatedStorage.ChestModels (installed by
-- blender-chest-kit/studio-install-chests.luau). Re-running replaces the island.
-- Chests: ChestIsland.Chests.<Tier> (models), pedestals: ChestIsland.Pedestals.<Tier>.
-- Everything is anchored and non-colliding (it is a display players look at, not walk on).
local RS = game:GetService("ReplicatedStorage")
local lobby = workspace:WaitForChild("RogueliteLobby")
local S = lobby.Scenery

local CENTER = Vector3.new(-1182, 130, 84) -- island top centre
local FACING = Vector3.new(-1, 0, 0) -- towards the lobby (west)
local ARC_RADIUS, ARC_BACK = 36, 26 -- arc centre sits ARC_BACK studs behind the island centre
local ORDER = { "Wooden", "Silver", "Gold", "Magical", "Legendary" } -- left to right seen from the lobby
local ANGLES = { -48, -24, 0, 24, 48 }
local RISE = { 1.8, 2.4, 3, 3.6, 4.4 } -- pedestal top height above the island top

local old = lobby:FindFirstChild("ChestIsland")
if old then
	old:Destroy()
end
local island = Instance.new("Model")
island.Name = "ChestIsland"
local function folder(name)
	local f = Instance.new("Folder")
	f.Name = name
	f.Parent = island
	return f
end
local ground, peds, chests, dressing = folder("Ground"), folder("Pedestals"), folder("Chests"), folder("Dressing")

local function prep(p)
	for _, d in (p:IsA("BasePart") and { p } or {}) do
		d.Anchored = true
		d.CanCollide = false
		d.CanTouch = false
		d.CanQuery = false
		d.Locked = true
	end
	return p
end
local function clone(name, parent)
	local src = S:FindFirstChild(name)
	assert(src, "missing lobby mesh " .. name)
	local c = src:Clone()
	for _, d in c:GetDescendants() do
		if d:IsA("BasePart") then
			prep(d)
		end
	end
	prep(c)
	c.Parent = parent
	return c
end

-- Island: the South island's top and cliff, turned so its long side runs north-south.
local srcTop, srcCliff = S.Island_South_4_Top, S.Island_South_4_Cliff
local turn = CFrame.Angles(0, math.rad(90), 0)
local topCf = CFrame.new(CENTER) * turn * (srcTop.CFrame - srcTop.Position)
local top = clone("Island_South_4_Top", ground)
top.CFrame = topCf
local cliff = clone("Island_South_4_Cliff", ground)
cliff.CFrame = CFrame.new(CENTER) * turn * srcTop.CFrame:ToObjectSpace(srcCliff.CFrame)
local groundY = CENTER.Y + top.Size.Y / 2

-- Pedestals and chests along the arc.
local arcCentre = CENTER - FACING * ARC_BACK
local templates = RS:FindFirstChild("ChestModels")
local report = {}
for i, tier in ORDER do
	local a = math.rad(ANGLES[i])
	-- Rotate FACING about Y by the arc angle (positive = to the right seen from the lobby, +Z).
	local dir = (CFrame.Angles(0, a, 0):VectorToWorldSpace(FACING)).Unit
	local spot = arcCentre + dir * ARC_RADIUS
	local base = Vector3.new(spot.X, groundY, spot.Z)
	local face = CFrame.lookAt(base, base + dir)
	local ped = Instance.new("Model")
	ped.Name = tier
	ped.Parent = peds
	local template = templates and templates:FindFirstChild(tier)
	local width = 8
	if template then
		local _, size = template:GetBoundingBox()
		width = math.max(size.X, size.Z)
	end
	local h = RISE[i]
	-- Rock mound (a flattened lobby boulder) with two round flagstone steps on top.
	local mound = clone("Boulder_2_594", ped)
	-- Rock base: its rounded top ends just under the lower slab, the rest is buried.
	mound.Size = Vector3.new(width * 1.65, 2 * (h - 0.2), width * 1.55)
	mound.CFrame = face * CFrame.new(0, 0, 0.4) * CFrame.Angles(0, math.rad(20 * i), 0)
	local lower = clone("Portal1_Pad_6", ped)
	lower.Size = Vector3.new(width * 1.45, 0.9, width * 1.45 * lower.Size.Z / lower.Size.X)
	lower.CFrame = face * CFrame.new(0, h - 0.55, 0.3) * CFrame.Angles(0, math.rad(37 * i), 0)
	local upper = clone("Portal2_Pad_8", ped)
	upper.Size = Vector3.new(width * 1.12, 0.9, width * 1.12 * upper.Size.Z / upper.Size.X)
	upper.CFrame = face * CFrame.new(0, h - 0.05, 0.3) * CFrame.Angles(0, math.rad(-23 * i), 0)
	local topY = h + 0.4
	if template then
		local chest = template:Clone()
		chest:PivotTo(face * CFrame.new(0, topY, 0.3))
		chest.Parent = chests
		table.insert(report, tier .. " placed")
	else
		table.insert(report, tier .. ": no template (run studio-install-chests.luau first)")
	end
	ped:SetAttribute("Top", face * CFrame.new(0, topY, 0.3))
end

-- Dressing: trees behind the arc, lanterns between pedestals, plants around the mounds.
local function place(name, pos, yaw, scale)
	local c = clone(name, dressing)
	if scale and scale ~= 1 then
		c.Size *= scale
	end
	c.CFrame = CFrame.new(pos + Vector3.new(0, c.Size.Y / 2, 0)) * CFrame.Angles(0, math.rad(yaw or 0), 0)
	return c
end
local back = -FACING
local side = Vector3.new(0, 1, 0):Cross(FACING).Unit -- to the right seen from the lobby
local g = Vector3.new(CENTER.X, groundY, CENTER.Z)
place("Broadleaf_Tree_2_68", g + back * 22 + side * 16, 30, 1)
place("Broadleaf_Tree_3_69", g + back * 20 - side * 20, 110, 1)
place("Broadleaf_Tree_70", g + back * 25 + side * 1, 200, 1.1)
place("Broadleaf_Tree_70", g + back * 16 + side * 33, 65, 0.9)
place("Broadleaf_Tree_3_69", g + back * 15 - side * 34, 250, 0.85)
for i, s in { -1, 1 } do
	place("Lantern_Post_34", g + back * 6 + side * s * 38, 90 * i)
	place("Lantern_Post_34", g + back * 10 + side * s * 12, 90 * i)
end
local plants = { "Shrub_99", "Shrub_2_584", "Shrub_3_480", "Fern_418", "Flowers_2_181", "Flowers_3_394", "Grass_Tuft_548", "Flowers_1_228" }
local rng = Random.new(28)
for n = 1, 46 do
	local a = rng:NextNumber(0, math.pi * 2)
	local r = rng:NextNumber(8, 31)
	local p = g + Vector3.new(math.cos(a) * r, 0, math.sin(a) * r * 1.2)
	-- Keep the lobby-facing front of each pedestal clear.
	local clear = true
	for _, ped in peds:GetChildren() do
		local top_ = ped:GetAttribute("Top")
		if top_ then
			local d = (p - top_.Position) * Vector3.new(1, 0, 1)
			-- Also keep the chest screen's camera line clear (about 20 studs out in front).
			if d.Magnitude < 7 or (d:Dot(top_.LookVector) > 0 and d.Magnitude < 24) then
				clear = false
			end
		end
	end
	if clear and (p - g):Dot(FACING) < 18 then
		place(plants[rng:NextInteger(1, #plants)], p, rng:NextNumber(0, 360), rng:NextNumber(0.8, 1.2))
	end
end

island.WorldPivot = CFrame.new(CENTER)
-- A showpiece seen from the whole lobby and flown to by the chest screen: always streamed in.
island.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
island:SetAttribute("Facing", FACING)
island.Parent = lobby
return table.concat(report, "\n")
