-- Armor sets: four pieces each (helmet, chest, legs, boots), worn over the normalized R15 body
-- (AvatarNormalizer). Cosmetic for now: set stats, armor chests and tiers come with the armor
-- spec (RARITY_GODLY_ARMOR.md step 5). Meshes live in ReplicatedStorage.ArmorSets.<model>, one
-- MeshPart per R15 part, installed by blender-armor-kit/studio-install-dragon-scale.luau.
-- Unsandboxed (ProfileService, ArmorService and ArmoryUI read it).
local A = {}

A.Slots = { "Helmet", "Chest", "Legs", "Boots" }

A.Sets = {
	{ id = "DragonScale", name = "Dragon Scale", rarity = "Legendary", model = "DragonScale" },
}

A.ById = {}
for _, s in A.Sets do
	A.ById[s.id] = s
end

-- Studio test profiles own these sets (in-memory profiles only, never saved).
A.StudioGrant = { "DragonScale" }

-- 'DragonScale.Helmet'
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
