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

	-- Section 1: the chest table (2026-10-03: a few items per chest, each one a roll)
	local want = {
		Wooden = { price = "daily", items = 1, pity = false,
			odds = { Common = 0.78, Rare = 0.2, Epic = 0.018, Legendary = 0.002 },
			stack = { Common = 3, Rare = 1, Epic = 1, Legendary = 1 } },
		Silver = { price = 160, items = 1, pity = true,
			odds = { Common = 0.6, Rare = 0.35, Epic = 0.04, Legendary = 0.0095, Godly = 0.0005 },
			stack = { Common = 4, Rare = 2, Epic = 1, Legendary = 1, Godly = 1 } },
		Gold = { price = 300, items = 1.5, pity = true,
			odds = { Common = 0.45, Rare = 0.42, Epic = 0.11, Legendary = 0.019, Godly = 0.001 },
			stack = { Common = 6, Rare = 3, Epic = 1, Legendary = 1, Godly = 1 } },
		Magical = { price = 700, items = 2, pity = true,
			odds = { Common = 0.2, Rare = 0.4, Epic = 0.35, Legendary = 0.047, Godly = 0.003 },
			stack = { Common = 8, Rare = 4, Epic = 2, Legendary = 1, Godly = 1 } },
	}
	for kind, w in want do
		local d = Chests.ById[kind]
		local same = (w.price == "daily" and d.daily == true and d.emeralds == nil or d.emeralds == w.price)
			and d.items == w.items
			and d.pity == w.pity
		local sum = 0
		for r, q in w.odds do
			same = same and d.odds[r] == q
			sum += q
		end
		for r in d.odds do
			same = same and w.odds[r] ~= nil
		end
		for r, n in w.stack do
			same = same and d.stack[r] == n
		end
		check(same, kind .. " matches the section 1 table")
		check(math.abs(sum - 1) < 1e-9, kind .. " odds add up to 1")
	end
	local L = Chests.ById.Legendary
	check(
		L.emeralds == nil
			and L.pity
			and table.concat(L.fixed, ",") == "Common,Rare,Epic,Legendary"
			and L.bonusGodly == 0.02
			and L.stack.Common == 12
			and L.stack.Rare == 5
			and L.stack.Epic == 2
			and L.stack.Legendary == 1,
		"Legendary Chest: x12 common, x5 rare, x2 epic, x1 Legendary, 2% Godly"
	)
	check(Chests.LegendaryPity == 50 and Chests.GodlyPity == 150, "Pity is 50 Legendary / 150 Godly")
	-- Items per chest (user, 2026-10-03: a Silver Chest is 1-2 items at most). Godly is off here.
	for kind, text in { Wooden = "1 item", Silver = "1 item", Gold = "1–2 items", Magical = "2 items", Legendary = "4 items" } do
		check(Chests.itemsText(kind) == text, kind .. " holds " .. text .. ", says " .. Chests.itemsText(kind))
	end

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
	local summaries = { -- Godly off: Silver's, Gold's and Magical's Godly share goes to Common
		Wooden = "Common=78%  ·  ×3 Rare=20% Epic=1.8% Legendary=0.2%",
		Silver = "Common=60%  ·  ×4 Rare=35%  ·  ×2 Epic=4% Legendary=0.95%",
		Gold = "Common=57%  ·  ×6 Rare=54%  ·  ×3 Epic=16% Legendary=2.8%",
		Magical = "Common=36%  ·  ×8 Rare=64%  ·  ×4 Epic=58%  ·  ×2 Legendary=9.2%",
		Legendary = "Common=×12 Rare=×5 Epic=×2 Legendary=×1",
	}
	for kind, text in summaries do
		check(rows(kind) == text, kind .. " summary: " .. rows(kind))
	end

	-- Every chest: an item count in its range, all different items, each with its rarity's stack
	local function counted(kind, n)
		local d = Chests.ById[kind]
		local lo, hi = Chests.itemRange(kind)
		for _ = 1, n do
			local rolls = Chests.roll(kind, rng)
			assert(#rolls >= lo and #rolls <= hi, kind .. " rolled " .. #rolls .. " items")
			local want, copies = {}, 0
			for _, r in rolls do
				want[r] = (want[r] or 0) + 1
				copies += d.stack[r]
				if not Chests.godlyEnabled() then
					assert(r ~= "Godly", kind .. " rolled a Godly while Godly is off")
				end
			end
			local got, items, total = {}, 0, 0
			for id, c in Chests.fill(kind, rolls, rng) do
				local r = Chests.RarityOf[id]
				assert(c == d.stack[r], kind .. " gave " .. c .. " copies of a " .. r)
				got[r] = (got[r] or 0) + 1
				items += 1
				total += c
			end
			assert(items == #rolls and total == copies, kind .. " gave " .. items .. " items for " .. #rolls .. " rolls")
			for r, k in want do
				assert(got[r] == k, kind .. " " .. r .. " items " .. tostring(got[r]) .. " of " .. k)
			end
		end
		checks += 1
	end
	for _, kind in Chests.Order do
		counted(kind, 5000)
	end

	-- odds() matches a simulation (4.5 standard deviations per item)
	local function compare(kind, n)
		local seen, sim = {}, Random.new(7)
		for _ = 1, n do
			for id in Chests.fill(kind, Chests.roll(kind, sim), sim) do
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
			if Chests.chance(kind, r) > 0 then
				pooled += #Chests.poolFor(kind, r)
			end
		end
		check(listed == pooled, kind .. " odds list every item it can hold once")
		for id in seen do
			assert(Chests.chance(kind, Chests.RarityOf[id]) > 0, kind .. " dropped " .. id .. " it can't hold")
		end
	end
	for _, kind in Chests.Order do
		compare(kind, rolls)
	end

	-- Legendary pity
	local function has(list, r)
		return table.find(list, r) ~= nil
	end
	local pity = { Legendary = Chests.LegendaryPity - 1, Godly = 0 }
	check(has(Chests.open("Silver", rng, pity), "Legendary") and pity.Legendary == 0, "The 50th pity chest has a Legendary and resets the counter")
	pity = { Legendary = 10, Godly = 0 }
	Chests.open("Wooden", rng, pity)
	check(pity.Legendary == 10 and pity.Godly == 0, "Wooden chests don't count toward pity")
	pity = { Legendary = 0, Godly = 0 }
	local gap, worst = 0, 0
	for _ = 1, 20000 do
		gap += 1
		if has(Chests.open("Silver", rng, pity), "Legendary") then
			worst = math.max(worst, gap)
			gap = 0
		end
	end
	check(worst == Chests.LegendaryPity, "Over 20,000 Silver chests the longest Legendary wait is exactly 50, got " .. worst)
	-- Godly off: never rolls, never counts
	pity = { Legendary = 0, Godly = Chests.GodlyPity - 1 }
	check(not has(Chests.open("Gold", rng, pity), "Godly") and pity.Godly == Chests.GodlyPity - 1, "No Godly and no Godly pity while Godly is off")

	-- Godly on (temporary pool on this copy only)
	Chests.Pool.Godly = { "G1", "G2", "G3" }
	for _, id in Chests.Pool.Godly do
		Chests.RarityOf[id] = "Godly"
	end
	check(Chests.godlyEnabled(), "A Godly pool turns Godly on")
	check(
		rows("Gold") == "Common=57%  ·  ×6 Rare=54%  ·  ×3 Epic=16% Legendary=2.8% Godly=0.15%",
		"Gold summary with Godly: " .. rows("Gold")
	)
	check(not rows("Wooden"):find("Godly"), "Wooden never shows Godly")
	check(Chests.itemsText("Legendary") == "4–5 items", "the Legendary Chest's Godly is a fifth item")
	pity = { Legendary = 0, Godly = Chests.GodlyPity - 1 }
	check(has(Chests.open("Gold", rng, pity), "Godly") and pity.Godly == 0, "The 150th pity chest has a Godly and resets the counter")
	pity = { Legendary = 0, Godly = 5 }
	Chests.open("Wooden", rng, pity)
	check(pity.Godly == 5, "Wooden chests don't count toward Godly pity")
	pity = { Legendary = 0, Godly = 0 }
	gap, worst = 0, 0
	for _ = 1, 6000 do
		gap += 1
		if has(Chests.open("Silver", rng, pity), "Godly") then
			worst = math.max(worst, gap)
			gap = 0
		end
	end
	check(worst == Chests.GodlyPity, "Over 6,000 Silver chests the longest Godly wait is exactly 150, got " .. worst)
	-- Both due on a one-item chest: the Godly now, the Legendary on the next chest.
	pity = { Legendary = Chests.LegendaryPity - 1, Godly = Chests.GodlyPity - 1 }
	local first = Chests.open("Silver", rng, pity)
	check(has(first, "Godly") and not has(first, "Legendary") and pity.Legendary == Chests.LegendaryPity, "a one-item chest owing both gives the Godly first")
	check(has(Chests.open("Silver", rng, pity), "Legendary") and pity.Legendary == 0, "and the Legendary comes in the next chest")
	for _, kind in Chests.Order do
		counted(kind, 2000)
	end
	compare("Gold", rolls)
	compare("Legendary", rolls)
	Chests.Pool.Godly = godlyPool
	for _, id in { "G1", "G2", "G3" } do
		Chests.RarityOf[id] = nil
	end
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
	check(Chests.ById.Legendary.legendary == 1 and Chests.ById.Silver.legendary < 1, "the chest screen reads a guaranteed Legendary as 1")
	local prng, seen = Random.new(7), {}
	for _ = 1, 3000 do
		for id in Chests.fill("Magical", Chests.open("Magical", prng, { Legendary = 0, Godly = Chests.GodlyPity - 1 }), prng) do
			seen[id] = true
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
