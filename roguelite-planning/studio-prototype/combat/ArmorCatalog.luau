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
	-- chests: only these chest kinds drop the set (Phoenix: the Robux Legendary Chest only).
	{ id = "Phoenix", name = "Phoenix", rarity = "Godly", model = "Phoenix", helmet = "full", chests = { "Legendary" } },
}

-- Generated 1024px item icons, 2026-10-01. Shared by armory, chest reveals, and store.
A.Icons = {
	["Iron.Helmet"] = "rbxassetid://129145366804816",
	["Iron.Chest"] = "rbxassetid://87779254850761",
	["Iron.Legs"] = "rbxassetid://92415099543295",
	["Iron.Boots"] = "rbxassetid://136478333897120",
	["Ninja.Helmet"] = "rbxassetid://122802619485422",
	["Ninja.Chest"] = "rbxassetid://78801616313923",
	["Ninja.Legs"] = "rbxassetid://94605542017106",
	["Ninja.Boots"] = "rbxassetid://122686411592392",
	["Viking.Helmet"] = "rbxassetid://103535004889613",
	["Viking.Chest"] = "rbxassetid://94896508153973",
	["Viking.Legs"] = "rbxassetid://126170661340997",
	["Viking.Boots"] = "rbxassetid://107105181804474",
	["Samurai.Helmet"] = "rbxassetid://106887858145836",
	["Samurai.Chest"] = "rbxassetid://73415381523062",
	["Samurai.Legs"] = "rbxassetid://78615423814209",
	["Samurai.Boots"] = "rbxassetid://82101371139011",
	["Spartan.Helmet"] = "rbxassetid://87897893879420",
	["Spartan.Chest"] = "rbxassetid://73918482671172",
	["Spartan.Legs"] = "rbxassetid://99913277149982",
	["Spartan.Boots"] = "rbxassetid://139187705472346",
	["Phoenix.Helmet"] = "rbxassetid://95410937063230",
	["Phoenix.Chest"] = "rbxassetid://93182390331732",
	["Phoenix.Legs"] = "rbxassetid://123491029382483",
	["Phoenix.Boots"] = "rbxassetid://90694826818994",
	["DragonScale.Helmet"] = "rbxassetid://117294820929917",
	["DragonScale.Chest"] = "rbxassetid://119736620076191",
	["DragonScale.Legs"] = "rbxassetid://122778396125798",
	["DragonScale.Boots"] = "rbxassetid://72705697021106",
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
