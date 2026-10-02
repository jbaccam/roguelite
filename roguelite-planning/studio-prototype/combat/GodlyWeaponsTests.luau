-- Godly weapon checks (plans/2026-10-01-G). Edit mode, no Play: pass fresh requires of
-- GodlyWeapons, WeaponCatalog, CharacterStats, ChestConfig, ShopCatalog and WeaponMotion.
return function(G, Weapons, Stats, Chests, Shop, Motion)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local ids = { "36", "37", "38", "39", "40", "41" }
	local neutral = Stats.resolve("Brawler", 0, {
		Damage = 0, MeleeDamage = 0, RangedDamage = 0, ElementalDamage = 0, UtilityPower = 0,
		ExplosionDamage = 0, AttackSpeed = 0, CooldownReduction = 0,
	})
	-- Catalog: six classless Godlies with specials; ~24 single-target DPS at Tier I (power 160).
	-- A lone enemy takes 2 storm arrows / both daggers.
	local lone = { ["38"] = 2, ["39"] = 2 }
	for _, id in ids do
		local w = Weapons.ById[id]
		check(w and w.godly and w.home == "Godly" and Weapons.isGodly(id), id .. " is a Godly")
		check(w.special == Weapons.Godly[id], id .. " carries its special")
		local d = Stats.weapon(w, neutral, "Brawler", 1)
		local dps = d.damage * (lone[id] or 1) / d.cooldown
		check(dps >= 22 and dps <= 26, string.format("%s Tier I single-target DPS %.1f", id, dps))
		check(Chests.RarityOf[id] == "Godly", id .. " is Godly in the chests")
		check(Shop.ById["weapon_" .. id .. "_1"] == nil, id .. " is never sold in the run shop")
	end
	check(Weapons.ById["31"].cooldown == 2, "Mjolnir attacks every 2.0 s")
	check(#Chests.WeaponPool.Godly == 0, "daily deals never offer a Godly")
	check(Chests.godlyEnabled("Silver") and Chests.godlyEnabled("Legendary"), "Godly weapons drop from chests")

	-- Tier values.
	check(G.tierValue({ 4, 4, 4, 6 }, 4) == 6 and G.tierValue({ 4, 4, 4, 6 }, 9) == 6 and G.tierValue(3, 2) == 3, "tier values")

	-- Storm Bow: distinct targets; a lone enemy takes at most loneMax.
	local a, b, c = {}, {}, {}
	local t = G.arrowTargets(a, { b, a, c }, 5, 2)
	check(#t == 3 and t[1] == a and t[2] == b and t[3] == c, "arrows: each enemy once, main first")
	t = G.arrowTargets(a, {}, 5, 2)
	check(#t == 2 and t[1] == a and t[2] == a, "arrows: a lone enemy takes 2")
	local many = {}
	for i = 1, 9 do
		many[i] = {}
	end
	check(#G.arrowTargets(a, many, 7, 2) == 7, "arrows: capped at the volley size")

	-- Shadow Daggers: nearest hop, hop limit, lone hits.
	local pos = { [a] = Vector3.new(0, 0, 0), [b] = Vector3.new(5, 0, 0), [c] = Vector3.new(30, 0, 0) }
	local d1 = {}
	pos[d1] = Vector3.new(9, 0, 0)
	local path = G.chain(a, { c, d1, b }, 5, 12, 2, function(n)
		return pos[n]
	end)
	check(#path == 3 and path[2] == b and path[3] == d1, "chain: nearest hops within 12 studs, c is too far")
	path = G.chain(a, {}, 5, 12, 2, function(n)
		return pos[n]
	end)
	check(#path == 2 and path[2] == a, "chain: a lone enemy takes both blades")

	-- Wraith cap: oldest go first.
	local list = { { key = 1, born = 5 }, { key = 2, born = 1 }, { key = 3, born = 3 }, { key = 4, born = 4 } }
	local out = G.overCap(list, 4)
	check(#out == 1 and out[1] == 2, "wraiths: at the cap the oldest fades")
	check(#G.overCap({ { key = 1, born = 1 } }, 4) == 0, "wraiths: under the cap nothing fades")

	-- Tidal wave: reaches the rim at waveTime.
	check(G.waveDelay(0, 10, 0.5) == 0 and math.abs(G.waveDelay(10, 10, 0.5) - 0.5) < 1e-6 and G.waveDelay(20, 10, 0.5) == 0.5, "wave timing")

	-- Reap: the turn passes each heading in order, and the server's fraction matches the pose.
	check(Motion.reapFraction(0) == 0 and Motion.reapFraction(1) == 1, "reap runs 0..1 over the hit window")
	local forward = Vector3.new(0, 0, -1)
	check(math.abs(Motion.reapFractionOf(forward, forward, 1) - 0.5) < 1e-6, "reap: the cut direction is half way")
	for _, side in { 1, -1 } do
		for _, deg in { -150, -60, 0, 45, 170 } do
			local heading = CFrame.lookAt(Vector3.zero, forward) * CFrame.Angles(0, math.rad(deg * side), 0)
			local f = Motion.reapFractionOf(forward, heading.LookVector, side)
			check(math.abs(f - (deg + 180) / 360) < 1e-4, string.format("reap fraction matches the pose (%d, side %d)", deg, side))
		end
	end
	check(Motion.chooseStyle("36", 1, 1, 3, 10) == "Reap" and Motion.chooseStyle("39", 3, 2, 3, 10) == "Chain", "Godly styles")
	check(Motion.chooseStyle("37", 1, 1, 3, 9) == "Thrust" and Motion.chooseStyle("37", 3, 1, 3, 9) == "Horizontal", "Trident stabs one, sweeps many")
	return checks
end
