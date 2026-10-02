-- ChestConfig checks (RARITY_GODLY_ARMOR.md step 1): chest table, item counts, odds against a
-- simulation, both pity counters, upgrade and spare-copy tables, deal prices and rarity pools.
-- Run in Studio Edit on a fresh copy of ChestConfig. The Phoenix armor fills the Godly pool; most
-- checks run with that pool set aside (Godly off), the Godly checks put it back.
-- `rolls` = simulated chests per chest kind.
return function(Chests, rolls)
	rolls = rolls or 100000
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local rng = Random.new(20260928)

	-- Armor pieces share the pools (2026-09-30): Iron Common, Ninja+Viking Rare, Samurai+Spartan
	-- Epic, Dragon Scale Legendary, Phoenix Godly; 4 pieces each.
	local godlyPool = Chests.Pool.Godly
	check(#godlyPool == 10 and Chests.godlyEnabled(), "The 6 Godly weapons and 4 Phoenix pieces fill the Godly pool")
	Chests.Pool.Godly = {}

	-- Pools, rarities, colours
	local sizes = { Common = 16, Rare = 20, Epic = 13, Legendary = 11, Godly = 0 }
	local weapons = { Common = 12, Rare = 12, Epic = 5, Legendary = 7, Godly = 0 }
	for r, n in sizes do
		check(#Chests.Pool[r] == n, r .. " pool has " .. n .. " items, found " .. #Chests.Pool[r])
		check(#Chests.WeaponPool[r] == weapons[r], r .. " has " .. weapons[r] .. " weapons")
		check(typeof(Chests.RarityColor[r]) == "Color3", r .. " has a colour")
	end
	for id, r in { ["Iron.Helmet"] = "Common", ["Ninja.Boots"] = "Rare", ["Samurai.Chest"] = "Epic",
		["DragonScale.Legs"] = "Legendary", ["Phoenix.Helmet"] = "Godly" } do
		check(Chests.RarityOf[id] == r and Chests.isArmor(id), id .. " is a " .. r .. " armor piece")
	end
	check(not Chests.isArmor("31"), "Mjolnir is not armor")
	check(#Chests.Rarities == 5 and Chests.Rarities[5] == "Godly", "Godly is the fifth rarity")
	check(Chests.RarityOf["31"] == "Legendary", "Mjolnir is Legendary")
	check(not Chests.godlyEnabled(), "Godly is off while its pool is empty")

	-- Section 1: the chest table {emeralds, items, rare, epic, legendary, godly, pity}
	local want = {
		Wooden = { "daily", 3, 0.25, 0.02, 0.002, 0, false }, -- free once a day
		Silver = { 160, 6, 1, 0.08, 0.008, 0.0005, true },
		Gold = { 300, 10, 2, 0.25, 0.03, 0.002, true },
		Magical = { 700, 18, 4, 1, 0.1, 0.006, true },
		Legendary = { nil, 8, 3, 1, 1, 0.02, true },
	}
	for kind, w in want do
		local d = Chests.ById[kind]
		check(
			(w[1] == "daily" and d.daily == true and d.emeralds == nil or d.emeralds == w[1])
				and d.copies == w[2]
				and d.rare == w[3]
				and d.epic == w[4]
				and d.legendary == w[5]
				and d.godly == w[6]
				and d.pity == w[7],
			kind .. " matches the section 1 table"
		)
	end
	check(Chests.LegendaryPity == 50 and Chests.GodlyPity == 150, "Pity is 50 Legendary / 150 Godly")

	-- Section 2: upgrade costs (copies + emeralds tripling each tier) and spare-copy emeralds
	for r, e in { Common = 60, Rare = 120, Epic = 250, Legendary = 500, Godly = 1000 } do
		local t = Chests.UpgradeEmeralds[r]
		check(t[1] == e and t[2] == e * 3 and t[3] == e * 9, r .. " upgrades cost " .. e .. "/" .. e * 3 .. "/" .. e * 9 .. " emeralds")
	end
	check(Chests.upgradeEmeralds("31", 1) == 500 and Chests.upgradeEmeralds("Iron.Chest", 3) == 540, "upgradeEmeralds reads the item's rarity")
	local upgrades = {
		Common = { 2, 6, 15 },
		Rare = { 2, 4, 8 },
		Epic = { 1, 2, 4 },
		Legendary = { 1, 2, 3 },
		Godly = { 1, 1, 2 },
	}
	local spare = { Common = 2, Rare = 5, Epic = 20, Legendary = 60, Godly = 200 }
	for r, costs in upgrades do
		for t = 1, 3 do
			check(Chests.UpgradeByRarity[r][t] == costs[t], r .. " tier " .. t .. " costs " .. costs[t])
		end
		check(Chests.OverflowByRarity[r] == spare[r], r .. " spare copy is " .. spare[r] .. " emeralds")
	end
	check(
		Chests.upgradeCost("31", 2) == 2 and Chests.overflow("31") == 60,
		"Mjolnir upgrades and cashes in as a Legendary"
	)
	check(Chests.upgradeCost("00", 3) == 15, "Glock III -> IV costs 15")

	-- The UI's text
	for x, text in { [0.25] = "25%", [0.02] = "2%", [0.002] = "0.2%", [0.0005] = "0.05%", [0.006] = "0.6%", [0.1] = "10%" } do
		check(Chests.percent(x) == text, "percent(" .. x .. ") = " .. text .. ", got " .. Chests.percent(x))
	end
	local function rows(kind)
		local out = {}
		for _, row in Chests.summary(kind) do
			table.insert(out, row.rarity .. "=" .. row.text)
		end
		return table.concat(out, " ")
	end
	local summaries = {
		Wooden = "Common=×0–3 Rare=25% Epic=2% Legendary=0.2%",
		Silver = "Common=×3–5 Rare=×1 Epic=8% Legendary=0.8%",
		Gold = "Common=×6–8 Rare=×2 Epic=25% Legendary=3%",
		Magical = "Common=×12–13 Rare=×4 Epic=×1 Legendary=10%",
		Legendary = "Common=×3 Rare=×3 Epic=×1 Legendary=×1",
	}
	for kind, text in summaries do
		check(rows(kind) == text, kind .. " summary: " .. rows(kind))
	end

	-- Item counts are conserved by rollCounts and group
	local function conserved(kind, n)
		local d = Chests.ById[kind]
		for _ = 1, n do
			local counts = Chests.rollCounts(kind, rng)
			local total = 0
			for _, r in Chests.Rarities do
				total += counts[r]
				assert(counts[r] >= 0, kind .. " negative " .. r)
			end
			assert(total == d.copies, kind .. " rolled " .. total .. " items, not " .. d.copies)
			local tally, grouped = {}, 0
			for _, r in Chests.Rarities do
				Chests.group(r, counts[r], rng, tally)
			end
			for _, c in tally do
				grouped += c
			end
			assert(grouped == total, kind .. " grouped " .. grouped .. " of " .. total .. " items")
			if not Chests.godlyEnabled() then
				assert(counts.Godly == 0, kind .. " rolled a Godly while Godly is off")
			end
		end
		checks += 1
	end
	for _, kind in Chests.Order do
		conserved(kind, 5000)
	end

	-- odds() matches a simulation (4.5 standard deviations per weapon)
	local function compare(kind, n)
		local seen, sim = {}, Random.new(7)
		for _ = 1, n do
			local counts = Chests.rollCounts(kind, sim)
			local tally = {}
			for _, r in Chests.Rarities do
				Chests.group(r, counts[r], sim, tally)
			end
			for id in tally do
				seen[id] = (seen[id] or 0) + 1
			end
		end
		local listed = 0
		for _, o in Chests.odds(kind) do
			listed += 1
			local p, got = o.chance / 100, (seen[o.id] or 0) / n
			local sigma = math.sqrt(p * (1 - p) / n)
			assert(
				math.abs(got - p) <= 4.5 * sigma + 1e-9,
				string.format("%s %s: odds say %.4f%%, simulation %.4f%%", kind, o.id, p * 100, got * 100)
			)
		end
		local pooled = 0
		for _, r in Chests.Rarities do
			pooled += #Chests.Pool[r]
		end
		check(listed == pooled, kind .. " odds list every pooled weapon once")
	end
	for _, kind in Chests.Order do
		compare(kind, rolls)
	end

	-- Legendary pity
	local pity = { Legendary = Chests.LegendaryPity - 1, Godly = 0 }
	local counts = Chests.open("Silver", rng, pity)
	check(counts.Legendary == 1 and pity.Legendary == 0, "The 50th pity chest has a Legendary and resets the counter")
	pity = { Legendary = 10, Godly = 0 }
	Chests.open("Wooden", rng, pity)
	check(pity.Legendary == 10 and pity.Godly == 0, "Wooden chests don't count toward pity")
	pity = { Legendary = 0, Godly = 0 }
	local gap, worst = 0, 0
	for _ = 1, 20000 do
		local c = Chests.open("Silver", rng, pity)
		gap += 1
		if c.Legendary > 0 then
			worst = math.max(worst, gap)
			gap = 0
		end
	end
	check(
		worst == Chests.LegendaryPity,
		"Over 20,000 Silver chests the longest Legendary wait is exactly 50, got " .. worst
	)
	-- Godly off: never rolls, never counts
	pity = { Legendary = 0, Godly = Chests.GodlyPity - 1 }
	counts = Chests.open("Gold", rng, pity)
	check(
		counts.Godly == 0 and pity.Godly == Chests.GodlyPity - 1,
		"No Godly and no Godly pity while Godly is off"
	)

	-- Godly on (temporary pool on this copy only)
	Chests.Pool.Godly = { "G1", "G2", "G3" }
	check(Chests.godlyEnabled(), "A Godly pool turns Godly on")
	check(
		rows("Gold") == "Common=×5–8 Rare=×2 Epic=25% Legendary=3% Godly=0.2%",
		"Gold summary with Godly: " .. rows("Gold")
	)
	check(not rows("Wooden"):find("Godly"), "Wooden never shows Godly")
	pity = { Legendary = 0, Godly = Chests.GodlyPity - 1 }
	counts = Chests.open("Gold", rng, pity)
	check(counts.Godly == 1 and pity.Godly == 0, "The 150th pity chest has a Godly and resets the counter")
	pity = { Legendary = 0, Godly = 5 }
	Chests.open("Wooden", rng, pity)
	check(pity.Godly == 5, "Wooden chests don't count toward Godly pity")
	pity = { Legendary = 0, Godly = 0 }
	gap, worst = 0, 0
	for _ = 1, 6000 do
		local c = Chests.open("Silver", rng, pity)
		gap += 1
		if c.Godly > 0 then
			worst = math.max(worst, gap)
			gap = 0
		end
	end
	check(worst == Chests.GodlyPity, "Over 6,000 Silver chests the longest Godly wait is exactly 150, got " .. worst)
	for _, kind in Chests.Order do
		conserved(kind, 2000)
	end
	compare("Gold", rolls)
	compare("Legendary", rolls)
	Chests.Pool.Godly = godlyPool
	check(Chests.godlyEnabled(), "Godly is on again with the Godly weapons and Phoenix")
	-- Godly weapons drop from every chest with a Godly chance; Phoenix only from the Legendary Chest.
	for _, kind in Chests.Order do
		local legendary = kind == "Legendary"
		local chance = Chests.ById[kind].godly > 0
		check(Chests.godlyEnabled(kind), kind .. " has the Godly weapons in its pool")
		check((rows(kind):find("Godly") ~= nil) == chance, kind .. " summary shows Godly only with a Godly chance")
		local weapons = 0
		for _, o in Chests.odds(kind) do
			if o.rarity == "Godly" and not o.id:find("^Phoenix%.") then
				weapons += 1
			end
		end
		check(weapons == (chance and 6 or 0), kind .. " odds list " .. weapons .. " Godly weapons")
		local phoenix = 0
		for _, o in Chests.odds(kind) do
			if o.id:find("^Phoenix%.") then
				phoenix += 1
			end
		end
		check(phoenix == (legendary and 4 or 0), kind .. " odds list " .. phoenix .. " Phoenix pieces")
	end
	local prng, seen = Random.new(7), {}
	for _ = 1, 3000 do
		local counts = Chests.open("Magical", prng, { Legendary = 0, Godly = Chests.GodlyPity - 1 })
		for r, n in counts do
			for id in Chests.group(r, n, prng, nil, "Magical") do
				seen[id] = true
			end
		end
	end
	for id in seen do
		assert(not id:find("^Phoenix%."), "a Magical Chest dropped " .. id)
	end
	checks += 1

	-- Section 3: daily deals
	for _, o in Chests.DealOdds do
		check(o[1] ~= "Godly", "Deals never offer Godly")
		check(
			Chests.DealPrice[o[1]] > Chests.OverflowByRarity[o[1]],
			o[1] .. " deal price per copy is above its spare-copy value"
		)
	end
	local mix, drng, n = {}, Random.new(99), 20000
	for _ = 1, n do
		local deal = Chests.rollDeal(drng)
		local a = Chests.DealAmount[deal.rarity]
		assert(Chests.RarityOf[deal.id] == deal.rarity, "deal weapon " .. deal.id .. " is " .. deal.rarity)
		assert(not Chests.isArmor(deal.id), "deals are weapons only")
		assert(deal.amount >= a[1] and deal.amount <= a[2], "deal amount in range")
		assert(deal.each == Chests.DealPrice[deal.rarity] and deal.price == deal.amount * deal.each, "deal price")
		assert(deal.each > Chests.overflow(deal.id), "deal price per copy beats cashing in")
		mix[deal.rarity] = (mix[deal.rarity] or 0) + 1
	end
	checks += 1
	for _, o in Chests.DealOdds do
		local got = (mix[o[1]] or 0) / n * 100
		check(math.abs(got - o[2]) < 1.5, string.format("%s deals %.1f%% (want %d%%)", o[1], got, o[2]))
	end
	return { passed = checks }
end
