-- Pets (RARITY_GODLY_ARMOR.md section 11, build step 6): the 12 pets, their tier numbers and the
-- player-facing effect lines. Pure data and helpers, shared by the server (PetService,
-- CharacterService, ProfileService, ChestConfig) and the client (ArmoryUI, PetVisuals).
-- Studio: RS.RogueliteCombat.PetConfig, a SANDBOXED ModuleScript (Capabilities copied from
-- CharacterStats), because the sandboxed CharacterService and PetService require it. Never wait
-- on RogueliteRunState here.
--
-- Rarity only means rarer and flashier, never stronger: every pet's Tier I is tuned to about the
-- same power budget, with a different strong suit. Every number is in PETS below; tier values are
-- {I, II, III, IV}. Damage numbers grow with the wave: base at wave 1, +perWave each wave after,
-- times TierMult. Copies upgrade a pet like a weapon (ChestConfig.UpgradeByRarity by rarity).
local P = { List = {}, ById = {}, Order = {} }

-- Uploaded item art; literal data keeps this module safe for sandboxed consumers.
P.Icons = {
	["Bunny"] = "rbxassetid://126035665768012",
	["GoldenRetriever"] = "rbxassetid://139974074985172",
	["Frog"] = "rbxassetid://72068688209203",
	["Penguin"] = "rbxassetid://134561532767972",
	["Fox"] = "rbxassetid://104736061635962",
	["Bee"] = "rbxassetid://135259222397245",
	["Turtle"] = "rbxthumb://type=Asset&id=88750159550350&w=420&h=420",
	["Monkey"] = "rbxassetid://114598472980257",
	["LuckyCat"] = "rbxassetid://86306160093146",
	["Owl"] = "rbxassetid://93634935695834",
	["CheetahCub"] = "rbxassetid://91328976444641",
	["BabyDragon"] = "rbxassetid://105864059105336",
}

P.Tiers = 4
P.TierMult = { 1, 1.15, 1.3, 1.5 } -- damage multiplier per tier
P.Rarities = { "Common", "Rare", "Epic", "Legendary" }

-- THE TUNING TABLE. Fields:
--   every     seconds between uses (number, or per tier)
--   range     studs from the owner to look for a target
--   stats     flat CharacterStats bonuses per tier: {StatId={I,II,III,IV}}
--   base/perWave  damage at wave 1 and added per wave after (times TierMult)
--   plus per-pet extras (heal, radius, slow, bonus, ...), commented inline.
local PETS = {
	{
		id = "GoldenRetriever", name = "Golden Retriever", rarity = "Common", suit = "Loot",
		description = "Runs out and fetches crystals for you.",
		every = { 3, 2.6, 2.2, 1.8 }, range = 45,
	},
	{
		id = "Bunny", name = "Bunny", rarity = "Common", suit = "Team healing",
		description = "Drops carrots that heal you or a hurt teammate.",
		every = 10, range = 40, heal = { 12, 14, 16, 18 }, -- HP, before the target's Recovery
	},
	{
		id = "Frog", name = "Frog", rarity = "Common", suit = "Space",
		description = "Hops into crowds and slams them away.",
		every = 6, range = 20, radius = { 8, 9, 10, 11 }, knockback = 35, -- studs/s, bosses x0.25
		base = 6, perWave = 1.5,
	},
	{
		id = "Penguin", name = "Penguin", rarity = "Common", suit = "Slow",
		description = "Belly-slides through enemies and slows them.",
		every = 7, range = 20, slide = 16, width = 3, slow = { 30, 34, 38, 42 }, slowFor = 2.5,
		base = 4, perWave = 1, -- = 3 + wave
	},
	{
		id = "Fox", name = "Fox", rarity = "Rare", suit = "Damage",
		description = "Pounces on nearby enemies.",
		every = 3, range = 22, base = 10, perWave = 2.5, -- also times your Damage stat
	},
	{
		id = "Bee", name = "Bee", rarity = "Rare", suit = "Poison",
		description = "Stings enemies and poisons them.",
		every = 4, range = 18, stats = { PoisonChance = { 8, 10, 12, 15 } },
	},
	{
		id = "Turtle", name = "Turtle", rarity = "Rare", suit = "Team defense",
		description = "Gives a shell shield that blocks one hit.",
		every = { 15, 13.5, 12, 10.5 }, range = 40, shieldFor = 15,
	},
	{
		id = "Monkey", name = "Monkey", rarity = "Rare", suit = "Attack speed",
		description = "Makes you attack faster.",
		stats = { AttackSpeed = { 6, 7, 8, 10 } },
	},
	{
		id = "LuckyCat", name = "Lucky Cat", rarity = "Epic", suit = "Luck",
		description = "Brings luck: the run shop rolls better tiers more often.",
		stats = { Luck = { 8, 10, 12, 15 } },
	},
	{
		id = "Owl", name = "Owl", rarity = "Epic", suit = "Bosses",
		description = "Marks the toughest enemy nearby so your hits do more.",
		every = 4, range = 50, markFor = 5, bonus = { 20, 23, 26, 30 }, -- % more damage from you
	},
	{
		id = "CheetahCub", name = "Cheetah Cub", rarity = "Epic", suit = "Speed",
		description = "Makes you faster, with a speed burst after you get hit.",
		stats = { MoveSpeed = { 1.5, 2, 2.5, 3 } },
		burst = 6, burstFor = 2, burstCooldown = 6, -- +MoveSpeed for burstFor s after damage
	},
	{
		id = "BabyDragon", name = "Baby Dragon", rarity = "Legendary", suit = "Fire",
		description = "Breathes small fire blasts that burn groups.",
		every = 5, range = 14, cone = 8, coneAngle = 25, -- studs long, degrees half-angle
		base = 5, perWave = 1, -- = 4 + wave
		stats = { BurnChance = { 5, 6, 7, 8 } },
	},
}

for i, d in PETS do
	d.order = i
	P.ById[d.id] = d
	table.insert(P.List, d)
	table.insert(P.Order, d.id)
end
-- Studio test profiles (in memory, never saved) own every pet at Tier I.
P.StudioGrant = table.clone(P.Order)

function P.valid(id)
	return type(id) == "string" and P.ById[id] ~= nil
end
local function clampTier(tier)
	return math.clamp(math.floor(tonumber(tier) or 1), 1, P.Tiers)
end
P.clampTier = clampTier
-- A field's value at a tier: numbers are the same at every tier, tables are {I,II,III,IV}.
function P.value(v, tier)
	if type(v) == "table" then
		return v[clampTier(tier)]
	end
	return v
end
function P.get(id, field, tier)
	local d = P.ById[id]
	return d and P.value(d[field], tier)
end
-- Flat CharacterStats bonuses for a pet at a tier ({} for an unknown pet or one with none).
function P.stats(id, tier)
	local d = P.ById[id]
	local out = {}
	if d and d.stats then
		for stat, values in d.stats do
			out[stat] = P.value(values, tier)
		end
	end
	return out
end
-- Damage at a wave and tier: (base + perWave*(wave-1)) * TierMult.
function P.damage(id, tier, wave)
	local d = P.ById[id]
	if not d or not d.base then
		return 0
	end
	return (d.base + (d.perWave or 0) * math.max(0, (wave or 1) - 1)) * P.TierMult[clampTier(tier)]
end

-- Profile strings (ProfileService): ProfilePets 'Bunny:2:3,Fox:1:0' (id:tier:copies) and
-- ProfilePet (the equipped id, or '').
function P.parse(text)
	local out = {}
	for id, tier, have in string.gmatch(text or "", "([^,:]+):(%d+):(%d+)") do
		if P.ById[id] then
			out[id] = { id = id, tier = clampTier(tier), have = tonumber(have) }
		end
	end
	return out
end
function P.tierOf(text, id)
	local rec = P.parse(text)[id]
	return rec and rec.tier
end
-- The equipped pet and its tier from the two attributes, or nil when none (or not owned).
function P.equipped(petText, petsText)
	if not P.valid(petText) then
		return nil
	end
	local tier = P.tierOf(petsText, petText)
	if not tier then
		return nil
	end
	return petText, tier
end

-- 1.5 -> '1.5', 12 -> '12', 11.5 -> '11.5', 2.875 -> '2.9'.
local function num(x)
	local s = string.format("%.1f", x)
	return (s:gsub("%.0$", ""))
end
P.num = num
-- One short line for the Armory, with the real numbers at that tier.
function P.effectText(id, tier)
	local d = P.ById[id]
	if not d then
		return ""
	end
	tier = clampTier(tier)
	local v = function(field)
		return P.value(d[field], tier)
	end
	local dmg = function()
		return num(P.damage(id, tier, 1)) .. " damage (+" .. num(d.perWave * P.TierMult[tier]) .. " per wave)"
	end
	if id == "GoldenRetriever" then
		return "Every " .. num(v("every")) .. " s, fetches a crystal up to " .. d.range .. " studs away."
	elseif id == "Bunny" then
		return "Every " .. num(v("every")) .. " s, drops a carrot that heals the most hurt player nearby for "
			.. num(v("heal")) .. " HP."
	elseif id == "Frog" then
		return "Every " .. num(v("every")) .. " s, slams a crowd: " .. dmg() .. " and knockback in a "
			.. num(v("radius")) .. "-stud circle."
	elseif id == "Penguin" then
		return "Every " .. num(v("every")) .. " s, slides through enemies: " .. dmg() .. " and "
			.. num(v("slow")) .. "% slow for " .. num(d.slowFor) .. " s."
	elseif id == "Fox" then
		return "Every " .. num(v("every")) .. " s, pounces on an enemy: " .. dmg() .. ", boosted by your Damage."
	elseif id == "Bee" then
		return "+" .. num(P.stats(id, tier).PoisonChance) .. "% poison chance. Every " .. num(v("every"))
			.. " s, stings an enemy with poison."
	elseif id == "Turtle" then
		return "Every " .. num(v("every")) .. " s, gives the most hurt player nearby a shell that blocks one hit."
	elseif id == "Monkey" then
		return "+" .. num(P.stats(id, tier).AttackSpeed) .. "% attack speed."
	elseif id == "LuckyCat" then
		return "+" .. num(P.stats(id, tier).Luck) .. " luck: the run shop rolls better tiers more often."
	elseif id == "Owl" then
		return "Every " .. num(v("every")) .. " s, marks the toughest enemy nearby: your hits on it do +"
			.. num(v("bonus")) .. "%."
	elseif id == "CheetahCub" then
		return "+" .. num(P.stats(id, tier).MoveSpeed) .. " move speed. After you get hit: +" .. num(d.burst)
			.. " speed for " .. num(d.burstFor) .. " s."
	elseif id == "BabyDragon" then
		return "+" .. num(P.stats(id, tier).BurnChance) .. "% burn chance. Every " .. num(v("every"))
			.. " s, breathes fire that burns enemies in front: " .. dmg() .. "."
	end
	return d.description
end

return P
