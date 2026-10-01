-- Armor sets: four pieces each (helmet, chest, legs, boots), worn over the normalized R15 body
-- (AvatarNormalizer). Every piece is its own chest item with its set's rarity (ChestConfig pools).
-- Set bonuses and tier scaling (RARITY_GODLY_ARMOR.md step 5) live in CharacterStats.ArmorSets and
-- CharacterStats.armorBonus, because sandboxed CharacterService can't require this module. Meshes live in ReplicatedStorage.ArmorSets.<model>, one MeshPart per R15 part (plus
-- extras like Phoenix's wings), installed by blender-armor-kit/studio-install-armor.luau.
-- Unsandboxed (ProfileService, ArmorService and ArmoryUI read it).
local A = {}

A.Slots = { "Helmet", "Chest", "Legs", "Boots" }

-- helmet: what a worn helmet hides. open = nothing (face and hair show), hood = hats and hair,
-- full = hats, hair and the face.
A.Sets = {
	{ id = "Iron", name = "Iron", rarity = "Common", model = "Iron", helmet = "open" },
	{ id = "Ninja", name = "Ninja", rarity = "Rare", model = "Ninja", helmet = "hood" },
	{ id = "Viking", name = "Viking", rarity = "Rare", model = "Viking", helmet = "open" },
	{ id = "Samurai", name = "Samurai", rarity = "Epic", model = "Samurai", helmet = "full" },
	{ id = "Spartan", name = "Spartan", rarity = "Epic", model = "Spartan", helmet = "full" },
	{ id = "DragonScale", name = "Dragon Scale", rarity = "Legendary", model = "DragonScale", helmet = "full" },
	{ id = "Phoenix", name = "Phoenix", rarity = "Godly", model = "Phoenix", helmet = "full" },
}

-- Piece icons for chest reveals and odds ('Iron.Helmet' -> image), rendered from each kit's
-- .blend by blender-armor-kit/render_icons.py and uploaded.
A.Icons = {
	["DragonScale.Boots"] = "rbxassetid://122619097931139",
	["DragonScale.Chest"] = "rbxassetid://99087648687237",
	["DragonScale.Helmet"] = "rbxassetid://107313624596017",
	["DragonScale.Legs"] = "rbxassetid://99675553277531",
	["Iron.Boots"] = "rbxassetid://85626163763678",
	["Iron.Chest"] = "rbxassetid://125004347306285",
	["Iron.Helmet"] = "rbxassetid://108620771694726",
	["Iron.Legs"] = "rbxassetid://106319354254330",
	["Ninja.Boots"] = "rbxassetid://84851293687606",
	["Ninja.Chest"] = "rbxassetid://84533859284815",
	["Ninja.Helmet"] = "rbxassetid://123952778159697",
	["Ninja.Legs"] = "rbxassetid://97067760550019",
	["Phoenix.Boots"] = "rbxassetid://119867479721375",
	["Phoenix.Chest"] = "rbxassetid://99037831238990",
	["Phoenix.Helmet"] = "rbxassetid://83919301031061",
	["Phoenix.Legs"] = "rbxassetid://136423621963228",
	["Samurai.Boots"] = "rbxassetid://110749138580619",
	["Samurai.Chest"] = "rbxassetid://76632440125129",
	["Samurai.Helmet"] = "rbxassetid://93114126403391",
	["Samurai.Legs"] = "rbxassetid://128518737623168",
	["Spartan.Boots"] = "rbxassetid://131876371544570",
	["Spartan.Chest"] = "rbxassetid://109195399406235",
	["Spartan.Helmet"] = "rbxassetid://92189851172805",
	["Spartan.Legs"] = "rbxassetid://81528249409821",
	["Viking.Boots"] = "rbxassetid://135434557996276",
	["Viking.Chest"] = "rbxassetid://76607499373698",
	["Viking.Helmet"] = "rbxassetid://135240295104077",
	["Viking.Legs"] = "rbxassetid://89528919327823",
}

A.ById = {}
for _, s in A.Sets do
	A.ById[s.id] = s
end

-- Studio test profiles own these sets (in-memory profiles only, never saved).
A.StudioGrant = { "DragonScale" }

-- 'DragonScale.Helmet'
function A.pieceName(pieceId)
	local setId, slot = A.split(pieceId)
	local set = setId and A.ById[setId]
	return set and (set.name .. " " .. slot) or pieceId
end

function A.pieceId(setId, slot)
	return setId .. "." .. slot
end

function A.split(pieceId)
	return string.match(pieceId or "", "^(%w+)%.(%w+)$")
end

function A.isSlot(slot)
	return table.find(A.Slots, slot) ~= nil
end

function A.valid(pieceId)
	local setId, slot = A.split(pieceId)
	return setId ~= nil and A.ById[setId] ~= nil and A.isSlot(slot)
end

return A
