-- Pet egg checks (EggConfig + ProfileService.buyEgg/openEgg). Pure apart from a stand-in player.
-- Run in Studio Edit on fresh copies (no Play session needed):
--   require(EggTests)(EggConfig, PetConfig, ProfileService)
-- ProfileService is driven with a Folder standing in for the player (it only needs attributes and
-- a profile table), so buying, hatching and every rejection run against the real server code.
return function(E, P, Profiles)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end

	-- Odds: every rarity sums to 100, every pet appears once, the Baby Dragon gets all of Legendary.
	local total, seen = 0, {}
	for _, r in E.Rarities do
		total += E.Odds[r]
		check(#E.ByRarity[r] > 0, r .. " has pets")
	end
	check(total == 100, "rarity odds sum to 100, got " .. total)
	local sum = 0
	for _, o in E.odds() do
		check(not seen[o.id], o.id .. " listed once")
		seen[o.id] = true
		check(P.ById[o.id] and P.ById[o.id].rarity == o.rarity, o.id .. " has its PetConfig rarity")
		sum += o.chance
	end
	for _, id in P.Order do
		check(seen[id], id .. " can hatch")
	end
	check(math.abs(sum - 100) < 1e-6, "pet chances sum to 100, got " .. sum)
	local dragon
	for _, o in E.odds() do
		if o.id == "BabyDragon" then
			dragon = o.chance
		end
	end
	check(dragon == 5, "Baby Dragon is 5%")

	-- Rolls follow the odds (200k rolls; each rarity within 0.5 points).
	local rng, got = Random.new(7), {}
	local N = 200000
	for _ = 1, N do
		local id, rarity = E.roll(rng)
		check(P.ById[id] and P.ById[id].rarity == rarity, "roll gives a pet of its rarity")
		got[rarity] = (got[rarity] or 0) + 1
	end
	for _, r in E.Rarities do
		local pct = (got[r] or 0) / N * 100
		check(math.abs(pct - E.Odds[r]) < 0.5, string.format("%s rolled %.2f%%, odds %d%%", r, pct, E.Odds[r]))
	end

	-- Amounts.
	for _, n in { 1, 3, 10 } do
		check(E.validAmount(n), n .. " is a valid amount")
	end
	for _, n in { 0, 2, 100, -1, 1.5, "3", nil, math.huge } do
		check(not E.validAmount(n), tostring(n) .. " is rejected")
	end
	check(E.price(3) == 750 and E.price(10) == 2500, "price is 250 each")

	-- Server: buy and hatch with a stand-in player.
	if Profiles then
		local fake = Instance.new("Folder")
		local d = { emeralds = 1000, bought = 0, pets = {}, weapons = {}, armor = {}, eggs = 0 }
		Profiles.profiles[fake] = d
		local publish = Profiles.publish
		Profiles.publish = function(p) -- the real publish reads the whole profile; record eggs only
			p:SetAttribute("ProfileEggs", Profiles.profiles[p].eggs or 0)
		end
		local ok, msg = Profiles.buyEgg(fake, 2, false)
		check(not ok and msg == "Invalid amount", "buy ×2 rejected: " .. tostring(msg))
		ok = Profiles.buyEgg(fake, "1", false)
		check(not ok, "buy with a string amount rejected")
		ok, msg = Profiles.buyEgg(fake, 10, false)
		check(not ok and msg:find("more emeralds"), "buy ×10 with 1000 emeralds rejected: " .. tostring(msg))
		check(d.emeralds == 1000 and d.eggs == 0, "a rejected buy spends nothing")
		ok = Profiles.buyEgg(fake, 3, false)
		check(ok and d.emeralds == 250 and d.eggs == 3, "buy ×3 costs 750 and adds 3 eggs")
		check(fake:GetAttribute("ProfileEggs") == 3, "ProfileEggs published")
		-- Restricted regions: only earned emeralds may buy random items.
		d.bought = 200
		ok, msg = Profiles.buyEgg(fake, 1, true)
		check(not ok and msg:find("region"), "restricted buy with Robux emeralds rejected: " .. tostring(msg))
		d.bought = 0
		ok, msg = Profiles.openEgg(fake, 2)
		check(not ok and msg == "Invalid amount", "hatch ×2 rejected")
		local results
		ok, msg, results = Profiles.openEgg(fake, 10)
		check(ok and d.eggs == 0, "hatch ×10 hatches the 3 owned: " .. tostring(msg))
		local pets = 0
		for i, r in results do
			pets += r.count
			check(P.ById[r.id] and r.rarity == P.ById[r.id].rarity, "result is a pet with its rarity")
			if i > 1 then
				local rank = { Common = 1, Rare = 2, Epic = 3, Legendary = 4 }
				check(rank[results[i - 1].rarity] >= rank[r.rarity], "results rarest first")
			end
		end
		check(pets == 3, "3 eggs give 3 pets, got " .. pets)
		local owned = 0
		for _, rec in d.pets do
			owned += 1 + rec.have
		end
		check(owned == 3, "the profile holds the 3 copies")
		ok, msg = Profiles.openEgg(fake, 1)
		check(not ok and msg:find("No "), "hatch with no eggs rejected")
		Profiles.publish = publish
		Profiles.profiles[fake] = nil
		fake:Destroy()
	end
	return checks
end
