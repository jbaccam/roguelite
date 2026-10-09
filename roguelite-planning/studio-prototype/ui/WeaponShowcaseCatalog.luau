-- Explicit presentation recipes. This catalog never grants/equips a weapon or fires a remote.
local C = { ById = {}, List = {} }
local recipes = {
	["00"] = { "bullet", "Single aimed shot" },
	["01"] = { "melee", "Heavy pan swing", { "Horizontal", "Diagonal", "Downward" } },
	["02"] = { "melee", "Linked nunchuck swings", { "FigureEight", "Spin" } },
	["03"] = { "melee", "Katana cuts", { "Diagonal", "Horizontal", "Thrust" } },
	["04"] = { "melee", "Chain-and-sickle sweep", { "Horizontal", "Diagonal" } },
	["05"] = { "melee", "Spatula swing", { "Horizontal", "Downward" } },
	["06"] = { "melee", "Heavy bat swing", { "Horizontal", "Diagonal", "Downward" } },
	["07"] = { "bullet", "Rapid gunfire" },
	["08"] = { "poison", "Poison cloud" },
	["09"] = { "bullet", "Pellet spread" },
	["10"] = { "shirt", "Rolled shirt shot" },
	["11"] = { "rocket", "Rocket and explosion" },
	["12"] = { "throw", "Bouncing boomerang return" },
	["13"] = { "throw", "Straight kunai throw" },
	["14"] = { "throw", "Molotov and burning ground" },
	["15"] = { "throw", "Egg toss with occasional chicken hatches" },
	["16"] = { "melee", "Steak slap", { "Slap", "Diagonal" } },
	["17"] = { "fire", "Flamethrower duck" },
	["18"] = { "cards", "Curved card volley" },
	["19"] = { "melee", "Alternating boxing jabs", { "Thrust" } },
	["20"] = { "melee", "Cinder block impact", { "Diagonal", "Horizontal", "Downward" } },
	["21"] = { "yo", "Yo-yo out and back" },
	["22"] = { "ball", "Ground roll through a line" },
	["23"] = { "throw", "Bowling pin toss" },
	["24"] = { "bullet", "Nail shot" },
	["25"] = { "melee", "Wrecking-ball chain sweep", { "Horizontal", "Downward" } },
	["26"] = { "melee", "Shovel slam", { "Downward", "Diagonal" } },
	["27"] = { "melee", "Paint roller and slow", { "Horizontal", "Downward" } },
	["28"] = { "vacuum", "Inward vacuum funnel" },
	["29"] = { "water", "Continuous water jet" },
	["30"] = { "bullet", "Arcane energy orb" },
	["31"] = { "melee", "Mjolnir swing", { "Horizontal", "Downward" } },
	["32"] = { "melee", "Excalibur sword swing", { "Horizontal" } },
	["33"] = { "pandora", "Cursed skull from the open box" },
	["34"] = { "bullet", "Medusa gaze and slow" },
	["35"] = { "lightning", "Chaining crystal lightning" },
	["36"] = { "melee", "Full reaping sweep", { "Reap" } },
	["37"] = { "melee", "Trident thrust and sweep", { "Thrust", "Horizontal" } },
	["38"] = { "rain", "Storm arrow split and rain" },
	["39"] = { "chain", "Twin-dagger chain" },
	["40"] = { "melee", "Vampire blade cuts", { "Diagonal", "Horizontal" } },
	["41"] = { "ray", "Ray bolt with impact splash" },
	["42"] = { "melee", "Pizza cutter slices", { "Diagonal", "Thrust" } },
}
local extras = {
	["15"] = {
		{
			key = "Hatch",
			label = "CHICKEN HATCH",
			mode = "hatch",
			condition = "A landing egg has a 1 in 8 hatch chance. Chickens chase and peck for 8 seconds.",
		},
	},
	["31"] = {
		{
			key = "Throw",
			label = "HAMMER THROW",
			mode = "throw",
			condition = "Outside melee reach, Mjolnir flies out and returns.",
		},
	},
	["37"] = {
		{
			key = "Throw",
			label = "TIDAL THROW",
			mode = "throw",
			condition = "Outside melee reach, the thrown trident returns and raises a tidal wave.",
		},
	},
	["36"] = {
		{
			key = "Wraith",
			label = "SOUL WRAITH",
			mode = "wraith",
			condition = "On a kill: a 1 in 3 chance to summon a clawing wraith.",
		},
		{
			key = "BigWraith",
			label = "ELITE WRAITH",
			mode = "wraith",
			big = true,
			condition = "An elite soul creates the larger, stronger wraith.",
		},
	},
	["40"] = {
		{
			key = "Wisp",
			label = "LIFE WISP",
			mode = "wisp",
			condition = "A killing hit sends a healing wisp back to the wielder.",
		},
	},
	["41"] = {
		{
			key = "Burst",
			label = "DISINTEGRATION",
			mode = "burst",
			condition = "Every impact splashes nearby enemies. A killing hit also disintegrates its target.",
		},
	},
}
function C.build(catalog)
	local result = { ById = {}, List = {} }
	for _, w in catalog.List do
		local r = assert(recipes[w.id], "Missing showcase recipe: " .. w.id)
		local e = { id = w.id, name = w.name, mode = r[1], styles = r[3], variants = {} }
		table.insert(e.variants, {
			key = "Base",
			label = "BASE ATTACK",
			mode = r[1],
			condition = r[2] .. ". Tier changes use the live weapon stats.",
		})
		if r[3] then
			for _, style in r[3] do
				table.insert(e.variants, {
					key = style,
					label = string.upper(style),
					mode = "melee",
					style = style,
					condition = "An authored "
						.. string.lower(style)
						.. " swing, using the same animation and ribbons as a run.",
				})
			end
		end
		for _, v in extras[w.id] or {} do
			table.insert(e.variants, table.clone(v))
		end
		local legendary = catalog.Legendary[w.id]
		if legendary then
			table.insert(e.variants, {
				key = legendary.move,
				label = string.upper(catalog.LegendaryNames[legendary.move] or legendary.move),
				mode = "legendary",
				minTier = 4,
				condition = catalog.legendaryText(w.id),
			})
		end
		result.ById[w.id] = e
		table.insert(result.List, e)
	end
	return result
end
function C.variants(entry, tier)
	local list = {}
	for _, v in entry.variants do
		if not v.minTier or tier >= v.minTier then
			table.insert(list, v)
		end
	end
	return list
end
function C.variant(entry, key, tier)
	for _, v in C.variants(entry, tier) do
		if v.key == key then
			return v
		end
	end
	return entry.variants[1]
end
return C
