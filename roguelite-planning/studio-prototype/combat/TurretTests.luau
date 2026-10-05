-- Turret checks (HANDYMAN_TURRET.md; turret items 2026-10-04). Pure: no Instances, no Play. Studio
-- Edit (command bar), with the place's modules or fresh copies loaded from source:
--   local RS, SSS = game.ReplicatedStorage, game.ServerScriptService
--   local C = RS.RogueliteCombat
--   print(require(<this module>)(require(C.HandymanTurret), require(SSS.TargetGrid),
--     require(C.WeaponCatalog), require(C.CharacterStats), require(C.EconomyConfig), require(C.ShopCatalog)))
-- Covers the four turret items' numbers and Utility Power scaling, the balance target against
-- WeaponCatalog (each tier 40-50% of an average class ranged weapon of the same tier, range no
-- longer than theirs), Brotato's structure rule (Damage, Attack speed, Crit, Life steal ignored;
-- Pierce, extra nails and procs kept), the ring placement maths (bands, 5-stud spacing, the
-- fallback), the 10 / 30 caps, Scrap Magnet counting, the Handyman as Engineer (x1.25 Utility
-- Power gains, x0.5 Damage gains, 20% off structure items, the 4-8 ring, shop weighting), the shop
-- entries (ShopCatalog, optional) and targeting through TargetGrid. Returns the number of checks.
return function(H, G, Weapons, Stats, E, Catalog)
	local checks = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local function near(a, b, eps)
		return math.abs(a - b) <= (eps or 1e-6)
	end
	local neutral = {}
	for _, d in Stats.List do
		neutral[d.id] = d.base
	end
	local function with(over)
		local s = table.clone(neutral)
		for k, v in over do
			s[k] = v
		end
		return s
	end

	-- The four items: one per model, prices in the tier bands (EconomyConfig.price inflates them).
	local items = {
		{ "turret_nail", "Nail Turret", 1, 24 },
		{ "turret_twin", "Twin Nailer", 2, 46 },
		{ "turret_quad", "Quad Nailer", 3, 85 },
		{ "turret_gatling", "Gatling Rig", 4, 150 },
	}
	check(#H.Items == 4, "Four turret items")
	for i, row in items do
		local it = H.Items[i]
		check(it.id == row[1] and it.name == row[2] and it.tier == row[3] and it.price == row[4], "Item " .. row[1])
		check(H.ItemTier[row[1]] == row[3], "ItemTier " .. row[1])
		local band = E.TIER_PRICE_BANDS[row[3]]
		check(row[4] >= band[1] and row[4] <= band[2], "Price " .. row[4] .. " in its tier band")
	end
	check(E.price(24, 5, 1) == 41, "A Nail Turret costs 41 at wave 5")

	-- Tier numbers before Utility Power: x1.4 damage and the weapons' cooldown steps.
	local damage, cooldown, pierce, burst = { 4, 6, 8, 11 }, { 0.8, 0.72, 0.64, 0.56 }, { 0, 1, 1, 2 }, { 1, 1, 1, 3 }
	local dps = { 5.0, 8.33, 12.5, 19.64 }
	for t = 1, 4 do
		local d = H.weapon(t, neutral)
		check(d.tier == t and d.id == H.Id and d.structure == true, "Tier " .. t .. " definition")
		check(near(d.damage, damage[t]), "Tier " .. t .. " damage " .. d.damage)
		check(damage[t] == math.floor(H.DAMAGE * Weapons.TierGrowth ^ (t - 1) + 0.5), "Tier " .. t .. " damage follows TierGrowth")
		check(near(d.cooldown, cooldown[t]), "Tier " .. t .. " cooldown " .. d.cooldown)
		check(near(d.cooldown, H.COOLDOWN * Weapons.TierCooldown[t]), "Tier " .. t .. " cooldown follows TierCooldown")
		check(near(d.range, 25) and near(d.projectileSpeed, H.SPEED), "Tier " .. t .. " range 25 and speed")
		check(d.nativePierce == pierce[t], "Tier " .. t .. " pierce " .. d.nativePierce)
		check(d.burst == burst[t] and d.projectileCount == 1, "Tier " .. t .. " nails per cycle")
		check(near(H.baseDps(t), dps[t], 0.01), "Tier " .. t .. " DPS " .. H.baseDps(t))
		local interval, nail, n = H.cadence(d)
		check(n == burst[t] and near(interval * n, d.cooldown) and near(nail * n, d.damage), "Tier " .. t .. " cadence keeps DPS")
		check(H.weapon(t, nil).stats == nil and near(H.weapon(t, nil).damage, damage[t]), "Tier " .. t .. " base numbers without stats")
	end
	check(near(select(2, H.cadence(H.weapon(4, neutral))), 11 / 3), "Gatling: 3 nails of 3.67")

	-- Balance against the class ranged weapons (WeaponCatalog, not Godly), single target, one copy.
	local rangeSum, count, nailGun = 0, 0, nil
	for t = 1, 4 do
		local sum, n = 0, 0
		for _, base in Weapons.List do
			if not base.godly and base.kind ~= "Melee" then
				local d = Stats.weapon(base, neutral, nil, t)
				sum += d.damage * (base.kind == "Spread" and d.projectileCount or 1) / d.cooldown
				n += 1
				if t == 1 then
					rangeSum += base.range
					count += 1
					if base.id == "24" then
						nailGun = base
					end
				end
			end
		end
		local ratio = H.baseDps(t) / (sum / n)
		check(ratio >= 0.4 and ratio <= 0.5, string.format("Tier %d turret is %.1f%% of an average ranged weapon", t, ratio * 100))
	end
	check(count >= 20, "Ranged weapons counted: " .. count)
	check(H.RANGE <= rangeSum / count, string.format("Range %d is within the ranged average %.1f", H.RANGE, rangeSum / count))
	check(nailGun ~= nil and H.RANGE <= nailGun.range, "Range is within the Nail Gun's")

	-- Utility Power scales damage: +30% -> a Nail Turret's nail is 5.2.
	check(near(H.weapon(1, with({ UtilityPower = 30 })).damage, 5.2), "+30% Utility Power: 5.2 per nail")
	check(near(H.weapon(2, with({ UtilityPower = 50 })).damage, 9), "+50% Utility Power: Twin 9 per nail")

	-- Brotato's structure rule: these change nothing.
	local loaded = with({
		Damage = 50,
		RangedDamage = 40,
		MeleeDamage = 30,
		AttackSpeed = 60,
		CooldownReduction = 30,
		CritChance = 100,
		LifeSteal = 10,
		Knockback = 20,
		AttackRange = 50,
		ProjectileSpeed = 80,
		ProjectileSize = 50,
	})
	for t = 1, 4 do
		local a, b = H.weapon(t, neutral), H.weapon(t, loaded)
		check(near(a.damage, b.damage) and near(a.cooldown, b.cooldown) and near(a.range, b.range) and near(a.projectileSpeed, b.projectileSpeed) and near(a.projectileRadius, b.projectileRadius), "Tier " .. t .. ": Damage, Ranged, Attack speed, CDR, Range ignored")
	end
	local ds = H.weapon(1, loaded).stats
	check(ds.CritChance == 0 and ds.LifeSteal == 0 and ds.Damage == 0 and ds.RangedDamage == 0 and ds.Knockback == 0 and ds.AttackSpeed == 0, "No crit, life steal, damage, knockback in its hit stats")
	check(loaded.CritChance == 100 and loaded.Damage == 50, "The owner's own stats are untouched")
	-- And these still count: extra nails, Pierce, Bounce, burn, slow, poison, lightning, boss damage.
	local kept = with({ ProjectileCount = 1, Pierce = 2, Bounce = 1, BurnChance = 15, SlowChance = 15, PoisonChance = 15, ChainCount = 1, BossDamage = 20, GearPower = 3, UtilityPower = 20 })
	local d = H.weapon(1, kept) -- (the service adds owner and character; shotStat needs only stats)
	check(Stats.shotStat(d, "ProjectileCount") == 1 and Stats.shotStat(d, "Pierce") == 2 and Stats.shotStat(d, "Bounce") == 1, "Two Straws, Pierce and Bounce apply")
	check(d.stats.BurnChance == 15 and d.stats.SlowChance == 15 and d.stats.PoisonChance == 15 and d.stats.ChainCount == 1, "Status procs apply")
	check(d.stats.BossDamage == 20 and d.stats.GearPower == 3, "Boss damage and gear power apply")
	check(Stats.usesStat(H.Base, "ProjectileCount") and Stats.usesStat(H.Base, "Pierce") and Stats.usesStat(H.Base, "Bounce"), "A bullet weapon for the shot stats")
	check(d.classFit == nil and d.classFitPercent == nil, "No class-fit bonus")

	-- Ring placement: n spots, all 5+ studs apart, the first ring inside the band.
	check(near(H.fitRadius(10), 5 / (2 * math.sin(math.pi * 0.9 / 10)), 1e-9) and near(H.fitRadius(10), 8.96, 0.01), "10 fit a 8.96-stud ring")
	check(H.capacity(8) == 8 and H.capacity(14) >= 10, "8 fit at 8 studs, 10+ at 14")
	local function points(spots)
		local out = {}
		for i, spot in spots do
			out[i] = H.offset(spot)
		end
		return out
	end
	for _, band in { H.RING, H.Engineer.ring } do
		for n = 1, H.MAX_OWNED do
			for seed = 1, 12 do
				local spots = H.ring(n, band, Random.new(seed), seed)
				check(#spots == n, string.format("%d spots on %d-%d", n, band[1], band[2]))
				check(H.spaced(points(spots), H.SPACING), string.format("%d spots 5+ apart on %d-%d (seed %d)", n, band[1], band[2], seed))
				local first = spots[1].radius
				check(first >= band[1] - 1e-9 and first <= band[2] + 1e-9, string.format("First ring %.2f inside %d-%d", first, band[1], band[2]))
				for _, spot in spots do
					-- Vector3 is 32-bit in Roblox: a 10-stud offset carries ~1e-6 error.
					check(near((H.offset(spot)).Magnitude, spot.radius, 1e-4), "Offset length is its radius")
				end
			end
			check(H.spaced(points(H.ring(n, band, nil, 0)), H.SPACING), "Exact ring spaced too")
		end
	end
	local handy10 = H.ring(10, H.Engineer.ring, nil, 0)
	local inner, outer = 0, 0
	for _, spot in handy10 do
		if near(spot.radius, 8) then
			inner += 1
		elseif near(spot.radius, 13) then
			outer += 1
		end
	end
	check(inner == 8 and outer == 2, "A Handyman's 10: 8 at 8 studs, 2 at 13")
	check(near(H.ring(1, H.Engineer.ring, nil, 0)[1].radius, 4) and near(H.ring(1, H.RING, nil, 0)[1].radius, 8), "One turret: at the band's inside edge")
	check(near(H.ring(1, H.RING, nil, 1.2)[1].angle, 1.2), "The first spot is at the start angle (the player's facing)")
	check(near(H.angle(Vector3.new(0, 0, -1)), -math.pi / 2) and (H.offset({ angle = H.angle(Vector3.new(0, 0, -1)), radius = 1 }) - Vector3.new(0, 0, -1)).Magnitude < 1e-6, "Facing -Z puts the first spot in front")
	check(#H.ring(0, H.RING, nil, 0) == 0, "No turrets, no spots")
	check(not H.spaced({ Vector3.zero, Vector3.new(4.9, 0, 0) }, 5) and H.spaced({ Vector3.zero, Vector3.new(0, 9, 5) }, 5), "Spacing is measured on the ground")

	-- Fallback: the ring spot, else half as far, else the player's spot, else the given centre.
	local center = Vector3.new(10, 2, 10)
	local function probeWithin(limit)
		return function(point)
			local flat = Vector2.new(point.X - center.X, point.Z - center.Z).Magnitude
			if flat <= limit + 1e-6 then
				return Vector3.new(point.X, 0, point.Z)
			end
			return nil
		end
	end
	local at, r = H.spot(center, 0, 12, probeWithin(100))
	check(r == 12 and (at - Vector3.new(22, 0, 10)).Magnitude < 1e-6, "Ground at the ring spot")
	at, r = H.spot(center, 0, 12, probeWithin(7))
	check(r == 6 and (at - Vector3.new(16, 0, 10)).Magnitude < 1e-6, "Over a cliff at 12: half as far, 6")
	at, r = H.spot(center, 0, 12, probeWithin(1))
	check(r == 0 and (at - Vector3.new(10, 0, 10)).Magnitude < 1e-6, "Nowhere out there: the player's spot")
	at, r = H.spot(center, 0, 12, function()
		return nil
	end)
 check(r == 0 and at == nil, "No ground found: defer placement instead of creating an airborne turret")
 local safe=H.anchor(Vector3.new(100,30,100),Vector3.new(0,2,0),100)
 check(safe.Y==2 and Vector2.new(safe.X,safe.Z).Magnitude<=74.0001,"Jumping at a corner uses the ground-level interior")

	-- Caps: 10 per player, 30 on the server shared fairly.
	check(H.MAX_OWNED == 10 and H.MAX_SERVER == 30, "10 / 30")
	local inventory = { { id = "turret_nail", count = 7 }, { id = "toolbelt", count = 2 }, { id = "turret_gatling", count = 5 } }
	check(H.owned(inventory) == 12 and H.count(inventory, "toolbelt") == 2 and H.count(inventory, "nope") == 0, "Counts turret items only")
	local tiers = H.tiers(inventory)
	check(#tiers == 10 and tiers[1] == 4 and tiers[5] == 4 and tiers[6] == 1 and tiers[10] == 1, "At most 10 turrets, best first")
	check(#H.tiers({}) == 0 and #H.tiers(nil) == 0, "No items, no turrets")
	local turretEntry, plain = { turret = 1, structure = true }, { structure = true }
	check(H.offerable(turretEntry, 9) and not H.offerable(turretEntry, 10), "Turret items stop at 10 owned")
	check(H.offerable(plain, 10) and H.offerable({}, 10), "Other items aren't capped by it")
	local function same(a, b)
		if #a ~= #b then
			return false
		end
		for i in a do
			if a[i] ~= b[i] then
				return false
			end
		end
		return true
	end
	check(same(H.share({ 10, 10, 10, 10 }, 30), { 8, 8, 7, 7 }), "Four with 10 each: 8, 8, 7, 7")
	check(same(H.share({ 3, 10 }, 30), { 3, 10 }), "Room for everyone: all")
	check(same(H.share({ 2, 10, 10 }, 12), { 2, 5, 5 }), "A small want leaves more for the rest")
	check(same(H.share({ 10, 10 }, 0), { 0, 0 }) and same(H.share({ 5 }, -3), { 0 }), "Nothing left: none")

	-- Scrap Magnet: every 40 crystals a temporary Nail Turret, 3 a wave per copy.
	check(H.scrapBuilds(39, 1, 0) == 0 and H.scrapBuilds(40, 1, 0) == 1, "40 crystals build one")
	check(H.scrapBuilds(130, 2, 1) == 2, "2 copies, 130 crystals, 1 built: 2 more")
	check(H.scrapBuilds(400, 1, 0) == 3 and H.scrapBuilds(400, 1, 3) == 0 and H.scrapBuilds(400, 2, 3) == 3, "3 a wave per copy")
	check(H.scrapBuilds(100, 0, 0) == 0 and H.scrapBuilds(nil, 1, nil) == 0, "No magnet, nothing")

	-- The Handyman as Engineer: Utility Power gains x1.25, Damage gains x0.5, no +5% Damage buff.
	check(Stats.Classes.Handyman.buffs.Damage == nil and Stats.Classes.Handyman.buffs.UtilityPower == 15, "+15 Utility Power, no Damage buff")
	check(near(Stats.resolve("Handyman", 0).UtilityPower, 15) and near(Stats.resolve("Handyman", 0).Damage, 0), "His base: 15 Utility Power, 0 Damage")
	check(near(Stats.resolve("Handyman", 0, nil, { UtilityPower = 12 }).UtilityPower, 30), "A +12 card gives him +15")
	check(near(Stats.resolve("Handyman", 0, nil, { Damage = 10 }).Damage, 5), "+10% Damage gives him +5%")
	check(near(Stats.resolve("Handyman", 0, nil, { Damage = -3 }).Damage, -3), "A loss isn't halved")
	check(near(Stats.resolve("Handyman", 4).UtilityPower, 15 + 25), "Four home weapons: +20 counts +25")
	check(near(Stats.resolve("Handyman", 2).CooldownReduction, 10), "Other set bonuses unchanged")
	check(near(Stats.resolve("Gunner", 0, nil, { Damage = 10, UtilityPower = 12 }).Damage, 10) and near(Stats.resolve("Gunner", 0, nil, { UtilityPower = 12 }).UtilityPower, 12), "Other classes unchanged")
	check(string.find(Stats.Classes.Handyman.description, "Engineer", 1, true) ~= nil, "Engineer description")
	-- His turret rules: the 4-8 ring, 20% off structure items, a free Nail Turret.
	check(H.band("Handyman") == H.Engineer.ring and H.band("Gunner") == H.RING and H.RING[1] == 8 and H.RING[2] == 14, "Rings: Handyman 4-8, others 8-14")
	check(H.Engineer.ring[1] == 4 and H.Engineer.ring[2] == 8 and H.Engineer.free == "turret_nail", "Engineer rules")
	check(H.startsWithTurret("Handyman") and not H.startsWithTurret("Gunner"), "Only the Handyman starts with one")
	check(near(H.priceFactor("Handyman", plain), 0.8) and H.priceFactor("Gunner", plain) == 1 and H.priceFactor("Handyman", {}) == 1, "20% off structure items, for him only")
	check(E.price(24, 5, H.priceFactor("Handyman", plain)) == 32, "His wave-5 Nail Turret: 32, not 41")
	-- Shop weighting: a Handyman, or a carried Handyman weapon, favours structure items.
	check(H.favoured("Handyman", {}) and H.favoured("Gunner", { "00", "24" }) and not H.favoured("Gunner", { "00" }), "Who is favoured")
	local pool = { { id = "a" }, { id = "b", structure = true }, { id = "c" } }
	check(#H.weightPool(pool, true, 0.1, 0) == 1 and H.weightPool(pool, true, 0.1, 0)[1].id == "b", "A favoured roll under 15%: structure items only")
	check(H.weightPool(pool, true, 0.2, 0) == pool and #H.weightPool(pool, true, 0.2, 0.15) == 1, "15% plus the early-wave bonus")
	check(H.weightPool(pool, false, 0, 0.15) == pool and H.weightPool({ { id = "a" } }, true, 0, 0)[1].id == "a", "Not favoured, or none in the pool: unchanged")

	-- Worked example (design section 8): turret DPS sums.
	local function sum(list, up)
		local total = 0
		for _, t in list do
			local w = H.weapon(t, with({ UtilityPower = up }))
			total += w.damage / w.cooldown
		end
		return total
	end
	check(near(sum({ 1 }, Stats.resolve("Handyman", 0).UtilityPower), 5.75, 0.01), "Wave 1 Handyman: 5.75")
	check(near(sum({ 1, 1, 1 }, 30), 19.5, 0.01), "Wave 5: 19.5")
	check(near(sum({ 1, 1, 1, 1, 2 }, 45), 41.1, 0.1), "Wave 10: about 41")
	check(near(sum({ 1, 1, 1, 1, 1, 1, 2, 2, 3 }, 70), 100.6, 0.1), "Wave 15: about 100")
	check(near(sum({ 1, 1 }, 0), 10, 0.01), "A Gunner's 2 Nail Turrets: 10")

	-- Card text says exactly what it does.
	check(string.find(H.describe(1), "4 damage every 0.8 s within 25 studs.", 1, true) ~= nil, "Nail card: " .. H.describe(1))
	check(string.find(H.describe(2), "6 damage every 0.72 s within 25 studs, through 1 enemy.", 1, true) ~= nil, "Twin card: " .. H.describe(2))
	check(string.find(H.describe(4), "3 nails of 3.7 damage every 0.56 s within 25 studs, through 2 enemies.", 1, true) ~= nil, "Gatling card: " .. H.describe(4))

	-- The shop entries (ShopCatalog), when given.
	if Catalog then
		for i, row in items do
			local entry = Catalog.ById[row[1]]
			check(entry ~= nil and entry.kind == "Turret" and entry.turret == row[3] and entry.tier == row[3], "Catalog " .. row[1])
			check(entry.basePrice == row[4] and entry.cap == H.MAX_OWNED and entry.structure == true and entry.icon == H.Icons[i], "Catalog " .. row[1] .. " price, cap and icon")
			check(next(entry.modifiers) == nil and table.find(entry.tags, "Structure") ~= nil, "Catalog " .. row[1] .. " is no stat item")
			check(Catalog.weaponStats(entry) == nil, "Works for every build")
		end
		local magnet, belt = Catalog.ById[H.SCRAP_MAGNET], Catalog.ById[H.TOOLBELT]
		check(magnet and magnet.tier == 2 and magnet.basePrice == 40 and magnet.structure and next(magnet.modifiers) == nil, "Scrap Magnet: tier 2, 40")
		check(belt and belt.tier == 1 and belt.basePrice == 18 and belt.structure and belt.modifiers.UtilityPower == 6, "Toolbelt: tier 1, 18, +6 Utility Power")
		check(Catalog.ById.spare_parts == nil and Catalog.ById.duct_tape == nil, "No Spare Parts or Duct Tape (turrets can't break)")
	end

	-- Targeting through TargetGrid: the nearest allowed enemy with a clear line within its range.
	local origin = Vector3.new(0, 2, 0)
	local function pick(list, range, blocked)
		local grid = G.new(list)
		local e = G.nearest(grid, origin, range, function(e)
			return not e.dummy
		end, function(e)
			return e.position
		end, function(_, e)
			return not (blocked and blocked[e.id])
		end)
		return e and e.id
	end
	local function enemyAt(distance, id, extra)
		local e = { position = origin + Vector3.new(distance, 0, 0), boss = false, id = id }
		for k, v in extra or {} do
			e[k] = v
		end
		return e
	end
	local range = H.weapon(1, neutral).range
	check(pick({ enemyAt(range - 0.1, "in") }, range) == "in", "Just inside range")
	check(pick({ enemyAt(range + 0.1, "out") }, range) == nil, "Just outside range")
	check(pick({ enemyAt(20, "far"), enemyAt(8, "close"), enemyAt(range + 5, "out") }, range) == "close", "Nearest first")
	check(pick({ enemyAt(8, "close"), enemyAt(20, "far") }, range, { close = true }) == "far", "A blocked line is skipped")
	check(pick({ enemyAt(5, "dummy", { dummy = true }), enemyAt(12, "zombie") }, range) == "zombie", "Lobby dummies are never targets")
	check(pick({ enemyAt(27, "x") }, H.weapon(1, loaded).range) == nil, "Attack range doesn't stretch it")

	-- Facing.
	check(near(H.yaw(Vector3.new(0, 0, -1)), 0), "-Z is yaw 0")
	for _, dir in { Vector3.new(1, 0, 0), Vector3.new(-0.6, 0, 0.8), Vector3.new(0, 0, 1) } do
		check((CFrame.Angles(0, H.yaw(dir), 0).LookVector - dir.Unit).Magnitude < 1e-6, "Yaw faces its direction")
	end
	-- The destructible layer (9f6e956) and BUILD are gone.
	check(H.posts == nil and H.maxHealth == nil and H.canBuild == nil and H.canUpgrade == nil and H.Keys == nil, "No health, targets, BUILD or upgrades")
	return checks
end
