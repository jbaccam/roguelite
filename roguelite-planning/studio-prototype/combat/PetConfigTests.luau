-- PetConfig checks (RARITY_GODLY_ARMOR.md step 6): all 12 pets present with a rarity and strong
-- suit, tier numbers never get worse, stat ids are real CharacterStats ids with legal values,
-- effect lines are non-empty, damage grows with the wave and tier, and the profile strings parse.
-- Pure; run in Studio Edit on fresh copies: require(PetConfigTests)(PetConfig, CharacterStats).
return function(P, S)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end

	local ids = {
		"GoldenRetriever",
		"Bunny",
		"Frog",
		"Penguin",
		"Fox",
		"Bee",
		"Turtle",
		"Monkey",
		"LuckyCat",
		"Owl",
		"CheetahCub",
		"BabyDragon",
	}
	check(#P.List == 12 and #P.Order == 12, "12 pets, found " .. #P.List)
	local rank = { Common = 1, Rare = 2, Epic = 3, Legendary = 4 }
	for _, id in ids do
		local d = P.ById[id]
		check(d ~= nil, id .. " is in PetConfig")
		check(rank[d.rarity] ~= nil, id .. " has a pet rarity")
		check(
			type(d.name) == "string" and #d.name > 0 and type(d.suit) == "string" and #d.suit > 0,
			id .. " has a name and suit"
		)
		check(table.find(P.StudioGrant, id) ~= nil, id .. " is in the Studio grant")
	end
	check(#P.StudioGrant == 12, "the Studio grant is every pet")

	-- Tiers: every per-tier list has 4 numbers and never gets worse. Shorter cooldowns are better.
	local lowerIsBetter = { every = true }
	for _, d in P.List do
		for field, v in d do
			if type(v) == "table" and field ~= "stats" then
				check(#v == 4, d.id .. "." .. field .. " has 4 tiers")
				for t = 2, 4 do
					if lowerIsBetter[field] then
						check(v[t] <= v[t - 1], d.id .. "." .. field .. " tier " .. t .. " is not slower")
					else
						check(v[t] >= v[t - 1], d.id .. "." .. field .. " tier " .. t .. " is not weaker")
					end
				end
			end
		end
		for stat, values in d.stats or {} do
			check(S.ById[stat] ~= nil, d.id .. " stat " .. stat .. " is a CharacterStats id")
			check(#values == 4, d.id .. " " .. stat .. " has 4 tiers")
			for t = 1, 4 do
				local sd = S.ById[stat]
				check(
					values[t] > 0 and values[t] <= sd.max - sd.min,
					d.id .. " " .. stat .. " tier " .. t .. " is in range"
				)
				if t > 1 then
					check(values[t] >= values[t - 1], d.id .. " " .. stat .. " never drops")
				end
			end
			local got = P.stats(d.id, 3)
			check(got[stat] == values[3], d.id .. " stats() returns the tier III value")
		end
		for t = 1, 4 do
			local text = P.effectText(d.id, t)
			check(type(text) == "string" and #text > 10, d.id .. " has an effect line at tier " .. t)
			check(not text:find("nil"), d.id .. " effect line has no missing numbers")
		end
		if d.base then
			check(P.damage(d.id, 1, 5) > P.damage(d.id, 1, 1), d.id .. " damage grows with the wave")
			check(P.damage(d.id, 4, 1) > P.damage(d.id, 1, 1), d.id .. " damage grows with the tier")
		end
	end
	check(P.TierMult[1] == 1 and P.TierMult[4] == 1.5, "tier multipliers 1 .. 1.5")
	check(
		math.abs(P.damage("Fox", 1, 1) - 10) < 1e-6 and math.abs(P.damage("Fox", 1, 3) - 15) < 1e-6,
		"Fox: 10 + 2.5 per wave"
	)
	check(math.abs(P.damage("Penguin", 1, 2) - 5) < 1e-6, "Penguin: 3 + wave")
	check(math.abs(P.damage("BabyDragon", 2, 1) - 5 * 1.15) < 1e-6, "Baby Dragon: (4 + wave) x 1.15 at Tier II")
	check(next(P.stats("Fox", 1)) == nil and next(P.stats("Nope", 1)) == nil, "no stats for Fox or an unknown pet")

	-- Profile strings
	local parsed = P.parse("Bunny:2:3,Fox:1:0,Nope:1:1,Owl:9:0")
	check(parsed.Bunny.tier == 2 and parsed.Bunny.have == 3, "parse Bunny:2:3")
	check(parsed.Nope == nil, "unknown pets are dropped")
	check(parsed.Owl.tier == 4, "tiers clamp to IV")
	local id, tier = P.equipped("Fox", "Bunny:2:3,Fox:3:0")
	check(id == "Fox" and tier == 3, "equipped Fox at Tier III")
	check(P.equipped("Monkey", "Bunny:2:3") == nil, "an unowned equipped pet is ignored")
	check(P.equipped("", "Bunny:2:3") == nil, "no pet equipped")
	return { passed = checks }
end
