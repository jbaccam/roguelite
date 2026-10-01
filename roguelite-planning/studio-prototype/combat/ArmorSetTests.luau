-- Armor set bonus checks (RARITY_GODLY_ARMOR.md step 5, approved 2026-09-30): CharacterStats.armorBonus
-- counting, mixed sets, the 4-piece perks, tier scaling from the lowest counted piece, rounding and
-- the ProfileWearing/ProfileArmor strings. Pure; run in Studio Edit on a fresh copy of CharacterStats.
return function(S)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local function eq(got, want, message)
		check(got == want, string.format("%s: got %s, want %s", message, tostring(got), tostring(want)))
	end
	local function count(t)
		local n = 0
		for _ in t do
			n += 1
		end
		return n
	end
	-- All four slots of one set at one tier, as tables.
	local function full(setId, tier)
		local wearing, tiers = {}, {}
		for _, slot in S.ArmorSlots do
			wearing[slot] = setId
			tiers[setId .. "." .. slot] = tier
		end
		return wearing, tiers
	end

	-- The approved table at tier I.
	local want = {
		Iron = { two = { Armor = 2 }, four = { ContactReduction = 10 } },
		Ninja = { two = { Dodge = 8 }, four = { DodgeCrit = true } },
		Viking = { two = { MeleeDamage = 12 }, four = { RageAttackSpeed = 25 } },
		Samurai = { two = { CritChance = 8 }, four = { CritDamage = 40 } },
		Spartan = { two = { Armor = 3 }, four = { FirstHitBlock = 1 } },
		DragonScale = { two = { MaxHP = 25 }, four = { BurnChance = 20, FireThorns = 25 } },
		Phoenix = { two = { Regeneration = 2 }, four = { PhoenixBlast = 100 } },
	}
	eq(count(S.ArmorSets), 7, "seven sets")
	for setId, w in want do
		local set = S.ArmorSets[setId]
		check(set ~= nil, setId .. " exists")
		check(
			type(set.text) == "table" and type(set.text.two) == "string" and type(set.text.four) == "string",
			setId .. " has text.two/.four"
		)
		for part, bonus in w do
			eq(count(set[part]), count(bonus), setId .. " " .. part .. " size")
			for id, v in bonus do
				eq(set[part][id], v, setId .. " " .. part .. " " .. id)
			end
		end
		-- Tier I, all four pieces: stats and perks are the table's values.
		local stats, perks, sets = S.armorBonus(full(setId, 1))
		eq(sets[setId].count, 4, setId .. " counted 4")
		for _, part in { "two", "four" } do
			for id, v in w[part] do
				if S.ById[id] then
					eq(stats[id], v, setId .. " tier I stat " .. id)
				else
					eq(perks[id], v, setId .. " tier I perk " .. id)
				end
			end
		end
	end

	-- Counting: nothing worn, one piece, two, three (still only `two`), four.
	local stats, perks = S.armorBonus({}, nil)
	check(next(stats) == nil and next(perks) == nil, "nothing worn gives nothing")
	stats, perks = S.armorBonus({ Helmet = "Iron" }, nil)
	check(next(stats) == nil and next(perks) == nil, "one piece gives nothing")
	stats = S.armorBonus({ Helmet = "Iron", Boots = "Iron" }, nil)
	eq(stats.Armor, 2, "2 Iron: Armor")
	eq(stats.ContactReduction, nil, "2 Iron: no 4-piece")
	stats = S.armorBonus({ Helmet = "Iron", Chest = "Iron", Legs = "Iron" }, nil)
	eq(stats.Armor, 2, "3 Iron: Armor")
	eq(stats.ContactReduction, nil, "3 Iron: no 4-piece")
	stats, perks = S.armorBonus({ Helmet = "Ninja", Chest = "Ninja", Legs = "Ninja" }, nil)
	eq(stats.Dodge, 8, "3 Ninja: Dodge")
	eq(perks.DodgeCrit, nil, "3 Ninja: no dodge crit")

	-- Mixing sets: pieces of different sets never count together; two pairs give both 2-piece bonuses.
	stats, perks = S.armorBonus({ Helmet = "Iron", Chest = "Spartan", Legs = "Viking", Boots = "Ninja" }, nil)
	check(next(stats) == nil and next(perks) == nil, "four different sets give nothing")
	stats, perks = S.armorBonus({ Helmet = "Iron", Chest = "Iron", Legs = "Spartan", Boots = "Spartan" }, nil)
	eq(stats.Armor, 5, "2 Iron + 2 Spartan: Armor 2 + 3")
	check(stats.ContactReduction == nil and stats.FirstHitBlock == nil, "2 + 2: no 4-piece bonus")
	stats, perks = S.armorBonus({ Helmet = "Ninja", Chest = "Ninja", Legs = "Ninja", Boots = "Viking" }, nil)
	eq(stats.Dodge, 8, "3 Ninja + 1 Viking: Dodge")
	check(stats.MeleeDamage == nil and perks.DodgeCrit == nil, "3 + 1: no Viking bonus, no Ninja 4-piece")
	stats = S.armorBonus({ Helmet = "Nope", Chest = "Nope", Hat = "Iron", Shoes = "Iron" }, nil)
	check(next(stats) == nil, "unknown sets and slots are ignored")

	-- Tier scaling: x(1 + 0.1 x (tier - 1)), whole numbers, half rounds up.
	stats = S.armorBonus(full("Iron", 4))
	eq(stats.Armor, 3, "Iron IV: Armor 2 x 1.3 = 2.6 -> 3")
	eq(stats.ContactReduction, 13, "Iron IV: ContactReduction 13")
	stats = S.armorBonus(full("Spartan", 4))
	eq(stats.Armor, 4, "Spartan IV: Armor 3 x 1.3 = 3.9 -> 4")
	eq(stats.FirstHitBlock, 1, "Spartan IV: FirstHitBlock stays 1")
	stats = S.armorBonus(full("Spartan", 2))
	eq(stats.Armor, 3, "Spartan II: Armor 3.3 -> 3")
	stats, perks = S.armorBonus(full("DragonScale", 2))
	eq(stats.MaxHP, 28, "Dragon II: MaxHP 27.5 -> 28")
	eq(stats.BurnChance, 22, "Dragon II: BurnChance 22")
	eq(perks.FireThorns, 28, "Dragon II: thorns 27.5 -> 28")
	stats, perks = S.armorBonus(full("DragonScale", 4))
	eq(stats.MaxHP, 33, "Dragon IV: MaxHP 32.5 -> 33")
	eq(stats.BurnChance, 26, "Dragon IV: BurnChance 26")
	eq(perks.FireThorns, 33, "Dragon IV: thorns 32.5 -> 33")
	stats, perks = S.armorBonus(full("Phoenix", 3))
	eq(stats.Regeneration, 2, "Phoenix III: Regeneration 2.4 -> 2")
	eq(perks.PhoenixBlast, 120, "Phoenix III: blast 120")
	stats, perks = S.armorBonus(full("Phoenix", 4))
	eq(stats.Regeneration, 3, "Phoenix IV: Regeneration 2.6 -> 3")
	eq(perks.PhoenixBlast, 130, "Phoenix IV: blast 130")
	stats, perks = S.armorBonus(full("Viking", 4))
	eq(stats.MeleeDamage, 16, "Viking IV: MeleeDamage 15.6 -> 16")
	eq(perks.RageAttackSpeed, 33, "Viking IV: rage 32.5 -> 33")
	stats, perks = S.armorBonus(full("Ninja", 4))
	eq(stats.Dodge, 10, "Ninja IV: Dodge 10.4 -> 10")
	eq(perks.DodgeCrit, true, "Ninja IV: dodge crit stays a flag")
	stats = S.armorBonus(full("Samurai", 2))
	eq(stats.CritChance, 9, "Samurai II: CritChance 8.8 -> 9")
	eq(stats.CritDamage, 44, "Samurai II: CritDamage 44")

	-- Lowest counted piece: `two` uses the best two pieces, `four` all four.
	local _, sets
	stats, _, sets = S.armorBonus(
		{ Helmet = "Iron", Chest = "Iron", Legs = "Iron", Boots = "Iron" },
		{ ["Iron.Helmet"] = 4, ["Iron.Chest"] = 4, ["Iron.Legs"] = 1, ["Iron.Boots"] = 2 }
	)
	eq(sets.Iron.tierTwo, 4, "two scales from the second-best piece")
	eq(sets.Iron.tierFour, 1, "four scales from the lowest piece")
	eq(stats.Armor, 3, "mixed tiers: 2-piece at IV")
	eq(stats.ContactReduction, 10, "mixed tiers: 4-piece at I")
	stats = S.armorBonus(
		{ Helmet = "Iron", Chest = "Iron", Legs = "Iron" },
		{ ["Iron.Helmet"] = 1, ["Iron.Chest"] = 4, ["Iron.Legs"] = 4 }
	)
	eq(stats.Armor, 3, "3 pieces: a low third piece does not lower the 2-piece")
	stats = S.armorBonus(full("Iron", 9))
	eq(stats.Armor, 3, "tiers above IV clamp to IV")

	-- Ownership: with a tier list, a worn piece that isn't owned doesn't count.
	stats = S.armorBonus({ Helmet = "Iron", Chest = "Iron" }, { ["Iron.Helmet"] = 1 })
	check(next(stats) == nil, "an unowned worn piece doesn't count")

	-- The server's attribute strings.
	local wearing = S.parseWearing("Chest:DragonScale,Helmet:DragonScale")
	eq(wearing.Chest, "DragonScale", "parseWearing chest")
	eq(wearing.Helmet, "DragonScale", "parseWearing helmet")
	local tiers = S.parseArmorTiers("DragonScale.Helmet:2:0,DragonScale.Chest:3:1,Iron.Boots:1:4")
	eq(tiers["DragonScale.Helmet"], 2, "parseArmorTiers helmet")
	eq(tiers["DragonScale.Chest"], 3, "parseArmorTiers chest")
	stats = S.armorBonus("Chest:DragonScale,Helmet:DragonScale", "DragonScale.Helmet:2:0,DragonScale.Chest:3:1")
	eq(stats.MaxHP, 28, "strings: 2 Dragon Scale at II and III scale from II")
	stats = S.armorBonus("Chest:DragonScale,Helmet:DragonScale", "")
	check(next(stats) == nil, "strings: nothing owned counts nothing")
	stats = S.armorBonus(nil, nil)
	check(next(stats) == nil, "nil wearing gives nothing")

	-- The deltas feed resolve as flat bonuses and stay inside the stat limits.
	stats = S.armorBonus(full("Spartan", 1))
	local resolved = S.resolve("Gunner", 0, nil, stats)
	eq(resolved.Armor, 3, "resolve: Gunner + Spartan armor")
	eq(resolved.FirstHitBlock, 1, "resolve: Spartan block")
	for setId in S.ArmorSets do
		local s4 = S.armorBonus(full(setId, 4))
		for id, v in s4 do
			check(S.ById[id] ~= nil and v <= S.ById[id].max, setId .. " IV " .. id .. " within limits")
		end
	end

	return { passed = checks }
end
