-- Puts each player's worn armor on their character. The profile's `wearing` table arrives as the
-- server-set ProfileWearing attribute ('Chest:DragonScale,Helmet:DragonScale'); every spawn and
-- every change re-dresses the character. Each piece is one MeshPart per R15 part, cloned from
-- ReplicatedStorage.ArmorSets.<model> and welded to its body part at the part's `Mount` attribute
-- (the CFrame from body part to mesh, set by the kit's Studio installer). A worn helmet hides
-- what its set's `helmet` mode says (ArmorCatalog): hood = hats and hair, full = those and the
-- face. Phoenix's flames and lights ride along as Attachments inside its meshes.
-- Cosmetic only. Unsandboxed (reads the unsandboxed ArmorCatalog).
local Players = game:GetService("Players")
local RS = game:GetService("ReplicatedStorage")
local Catalog = require(RS:WaitForChild("RogueliteCombat"):WaitForChild("ArmorCatalog"))

local HIDE = { [Enum.AccessoryType.Hat] = true, [Enum.AccessoryType.Hair] = true }

local function worn(player)
	local out = {}
	for slot, setId in string.gmatch(player:GetAttribute("ProfileWearing") or "", "([^,:]+):([^,:]+)") do
		if Catalog.isSlot(slot) and Catalog.ById[setId] then
			out[slot] = setId
		end
	end
	return out
end

-- What a helmet covers: {object, hide?} for hat/hair accessory handles and the face decal.
local function covered(character, mode)
	local out = {}
	for _, d in character:GetChildren() do
		if d:IsA("Accessory") and HIDE[d.AccessoryType] then
			local h = d:FindFirstChild("Handle")
			if h then
				table.insert(out, { h, mode == "hood" or mode == "full" })
			end
		end
	end
	local head = character:FindFirstChild("Head")
	local face = head and head:FindFirstChild("face")
	if face and face:IsA("Decal") then
		table.insert(out, { face, mode == "full" })
	end
	return out
end

-- mode: the worn helmet's ArmorCatalog `helmet` ('open' | 'hood' | 'full'), or nil for none.
local function setHidden(character, mode)
	for _, pair in covered(character, mode) do
		local x, hidden = pair[1], pair[2]
		local base = x:GetAttribute("ArmorBaseTransparency")
		if hidden then
			if base == nil then
				x:SetAttribute("ArmorBaseTransparency", x.Transparency)
			end
			x.Transparency = 1
		elseif base ~= nil then
			x.Transparency = base
			x:SetAttribute("ArmorBaseTransparency", nil)
		end
	end
end

local function dress(player, character)
	if player.Character ~= character or not character:FindFirstChildOfClass("Humanoid") then
		return
	end
	local old = character:FindFirstChild("Armor")
	if old then
		old:Destroy()
	end
	local sets = RS:FindFirstChild("ArmorSets")
	local w = worn(player)
	local folder = Instance.new("Folder")
	folder.Name = "Armor"
	for slot, setId in w do
		local template = sets and sets:FindFirstChild(Catalog.ById[setId].model)
		if not template then
			warn("ArmorService: ReplicatedStorage.ArmorSets." .. Catalog.ById[setId].model .. " is not installed")
			continue
		end
		for _, src in template:GetChildren() do
			if src:IsA("BasePart") and src:GetAttribute("Piece") == slot then
				local body = character:FindFirstChild(src:GetAttribute("BodyPart") or "")
				if body and body:IsA("BasePart") then
					local mount = src:GetAttribute("Mount") or CFrame.new()
					local p = src:Clone()
					p.Anchored = false
					p.CanCollide = false
					p.CanTouch = false
					p.CanQuery = false
					p.Massless = true
					p.CFrame = body.CFrame * mount
					local weld = Instance.new("Weld")
					weld.Part0, weld.Part1, weld.C0 = body, p, mount
					weld.Parent = p
					p.Parent = folder
				end
			end
		end
	end
	folder.Parent = character
	setHidden(character, w.Helmet and Catalog.ById[w.Helmet].helmet or nil)
	-- The Armory copies the character once this matches ProfileWearing.
	character:SetAttribute("ArmorWorn", player:GetAttribute("ProfileWearing") or "")
end

local function added(player)
	player.CharacterAdded:Connect(function(character)
		-- AvatarNormalizer replaces characters it did not make; dress only the normalized one.
		local t0 = os.clock()
		while character.Parent and not character:GetAttribute("NormalizedAvatar") and os.clock() - t0 < 10 do
			task.wait(0.1)
		end
		dress(player, character)
		-- Accessories can finish loading after the dress: keep them under the helmet.
		character.ChildAdded:Connect(function(c)
			local helmet = worn(player).Helmet
			if c:IsA("Accessory") and helmet then
				task.defer(setHidden, character, Catalog.ById[helmet].helmet)
			end
		end)
	end)
	player:GetAttributeChangedSignal("ProfileWearing"):Connect(function()
		if player.Character then
			dress(player, player.Character)
		end
	end)
	if player.Character then
		task.spawn(dress, player, player.Character)
	end
end

Players.PlayerAdded:Connect(added)
for _, p in Players:GetPlayers() do
	task.spawn(added, p)
end
