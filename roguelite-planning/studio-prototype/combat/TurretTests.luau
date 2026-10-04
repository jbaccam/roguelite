-- Handyman turret checks (HANDYMAN_TURRET.md, 2026-10-03). Pure: no Instances, no Play. Studio Edit
-- (command bar), with the place's modules or fresh copies loaded from source:
--   local RS, SSS = game.ReplicatedStorage, game.ServerScriptService
--   local C = RS.RogueliteCombat
--   print(require(<this module>)(require(C.HandymanTurret), require(SSS.TargetGrid),
--     require(C.WeaponCatalog), require(C.CharacterStats), require(C.EconomyConfig)))
-- Covers tier stats, the balance target against WeaponCatalog (Tier I-IV at 40-50% of an average
-- class ranged weapon of the same tier, range no longer than theirs), Handyman scaling, upgrade
-- pricing and validation, who may BUILD, and targeting range through TargetGrid.
-- Returns the number of checks.
return function(H, G, Weapons, Stats, E)
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

	-- Tier stats before character bonuses: x1.4 damage and the weapons' cooldown steps.
	local damage, cooldown, pierce, burst = { 4, 6, 8, 11 }, { 0.8, 0.72, 0.64, 0.56 }, { 0, 1, 1, 2 }, { 1, 1, 1, 3 }
	for t = 1, 4 do
		local d = H.weapon(t, neutral, nil)
		check(d.tier == t and d.id == H.Id, "Tier " .. t .. " definition")
		check(near(d.damage, damage[t]), "Tier " .. t .. " damage " .. d.damage)
		check(damage[t] == math.floor(H.DAMAGE * Weapons.TierGrowth ^ (t - 1) + 0.5), "Tier " .. t .. " damage follows TierGrowth")
		check(near(d.cooldown, cooldown[t]), "Tier " .. t .. " cooldown " .. d.cooldown)
		check(near(d.cooldown, H.COOLDOWN * Weapons.TierCooldown[t]), "Tier " .. t .. " cooldown follows TierCooldown")
		check(near(d.range, H.RANGE) and near(d.projectileSpeed, H.SPEED), "Tier " .. t .. " range and speed")
		check(d.nativePierce == pierce[t], "Tier " .. t .. " pierce " .. d.nativePierce)
		check(d.burst == burst[t] and d.projectileCount == 1, "Tier " .. t .. " nails per cycle")
		check(near(H.baseDps(t), damage[t] / cooldown[t]), "Tier " .. t .. " base DPS")
		if t > 1 then
			check(H.baseDps(t) > H.baseDps(t - 1), "DPS grows each tier")
		end
		local interval, nail, n = H.cadence(d)
		check(n == burst[t] and near(interval * n, d.cooldown) and near(nail * n, d.damage), "Tier " .. t .. " cadence keeps DPS")
	end
	check(near(H.baseDps(1), 5), "Tier I is 5 DPS")
	check(near(H.baseDps(4) / H.baseDps(1), (11 / 4) / 0.7), "Tier IV / I is the rounded x1.4^3 / 0.7")

	-- Balance against the class ranged weapons (WeaponCatalog, not Godly), single target, one copy:
	-- each Tier's turret is 40-50% of their average at that tier. Shotgun counts its pellets; the
	-- Deck of Cards' damage is already its volley.
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

	-- Handyman scaling: Damage, Ranged damage, Utility power and the own-class +15% (CharacterStats.weapon).
	local handy = Stats.resolve("Handyman", 0)
	local d = H.weapon(1, handy, "Handyman")
	local expected = 4 * Stats.mult(handy.Damage) * Stats.mult(handy.RangedDamage) * Stats.mult(handy.UtilityPower) * Stats.mult(15)
	check(near(d.damage, expected) and d.classFitPercent == 15, string.format("Handyman Tier I nail %.3f", d.damage))
	check(near(d.damage, 4 * 1.05 * 1.15 * 1.15, 1e-6), "Worked example: 5.55 per nail")
	local more = table.clone(handy)
	more.UtilityPower += 20
	check(near(H.weapon(1, more, "Handyman").damage / d.damage, Stats.mult(more.UtilityPower) / Stats.mult(handy.UtilityPower)), "Utility power scales it")
	local twoHome = Stats.resolve("Handyman", 2)
	check(near(H.weapon(1, twoHome, "Handyman").cooldown, 0.8 * 0.9), "Two home weapons: 10% cooldown reduction")
	more = table.clone(neutral)
	more.AttackRange = 20
	check(near(H.weapon(1, more, nil).range, 30), "Attack range scales its reach")
	check(Stats.usesStat(H.Base, "ProjectileCount") and Stats.usesStat(H.Base, "Pierce") and Stats.usesStat(H.Base, "Bounce"), "Bullet weapon: Two Straws, pierce and bounce items apply")

	-- Upgrade prices: a weapon tier step (the middle of the tier's price band), inflated like offers.
	check(H.UPGRADE_BASE[1] == 18 and H.UPGRADE_BASE[2] == 42 and H.UPGRADE_BASE[3] == 77, "Upgrade bases 18 / 42 / 77")
	check(H.upgradePrice(1, 5, 1) == 32, "Tier II on wave 5 costs 32")
	check(H.upgradePrice(1, 5, 1) == E.price(18, 5, 1) and H.upgradePrice(2, 10, 1) == E.price(42, 10, 1), "Same formula as shop offers")
	check(H.upgradePrice(1, 5, 0.8) == 25, "A 20% discount applies")
	check(H.upgradePrice(4, 5, 1) == nil, "No price past Tier IV")
	for tier = 1, 2 do
		local a, b = H.upgradePrice(tier, 8, 1), H.upgradePrice(tier + 1, 8, 1)
		check(b > a, "Each step costs more")
	end

	-- Upgrade validation (ShopService runs this after its own phase/revision/rate checks).
	local ok, why, price = H.canUpgrade("Handyman", 1, 1, 32, 5, 1, true)
	check(ok and why == nil and price == 32, "Handyman with 32 shards buys Tier II")
	check(not H.canUpgrade("Handyman", 1, 1, 31, 5, 1, true), "One shard short")
	check(not H.canUpgrade("Gunner", 1, 1, 999, 5, 1, true), "Non-Handyman can't upgrade")
	check(not H.canUpgrade("Handyman", 4, 4, 999, 5, 1, true), "Tier IV is the top")
	check(not H.canUpgrade("Handyman", 2, 1, 999, 5, 1, true), "Stale click (showed Tier I, has II)")
	check(not H.canUpgrade("Handyman", 1, nil, 999, 5, 1, true), "Missing tier argument")
	check(not H.canUpgrade("Handyman", 1, "1", 999, 5, 1, true), "Tier argument must be a number")
	check(not H.canUpgrade("Handyman", 1, 1, "999", 5, 1, true), "Shards must be a number")
	check(not H.canUpgrade("Handyman", 1, 1, 999, 5, 1, false), "Not installed: no upgrade")
	local offer = H.offer("Handyman", 1, 5, 1, true)
	check(offer and offer.tier == 1 and offer.next == 2 and offer.price == 32, "Shop row for a Tier I turret")
	offer = H.offer("Handyman", 4, 5, 1, true)
	check(offer and offer.next == nil and offer.price == nil, "Shop row at Tier IV")
	check(H.offer("Mage", 1, 5, 1, true) == nil and H.offer("Handyman", 1, 5, 1, false) == nil, "No row for others or before install")

	-- Who may BUILD.
	local function ctx(over)
		local c = { ready = true, class = "Handyman", member = true, lobby = false, alive = true, down = false, phase = "Combat", paused = false, frozen = false, now = 100, readyAt = 0 }
		for k, v in over or {} do
			c[k] = v
		end
		return c
	end
	check(H.canBuild(ctx()), "A Handyman in a wave builds")
	check(H.canBuild(ctx({ phase = "Practice" })), "And in the sandbox")
	for _, name in { "Brawler", "Gunner", "Thrower", "Juggler", "Mage" } do
		check(not H.canBuild(ctx({ class = name })), name .. " can't build")
	end
	check(H.canBuild(ctx({ class = "Gunner", admin = true })), "An ADMIN turret works for any class")
	check(not H.canBuild(ctx({ ready = false })), "Not installed")
	check(not H.canBuild(ctx({ member = false })), "Not in the run")
	check(not H.canBuild(ctx({ lobby = true })), "In the lobby")
	check(not H.canBuild(ctx({ alive = false })), "Dead")
	check(not H.canBuild(ctx({ down = true })), "Downed")
	check(not H.canBuild(ctx({ phase = "Shop" })), "Between waves")
	check(not H.canBuild(ctx({ paused = true })), "Paused")
	check(not H.canBuild(ctx({ frozen = true })), "Boss entrance")
	check(not H.canBuild(ctx({ now = 100, readyAt = 100.5 })), "Cooling down")
	check(H.canBuild(ctx({ now = 100.5, readyAt = 100.5 })), "Ready again at ReadyAt")

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
	local function at(distance, id, extra)
		local e = { position = origin + Vector3.new(distance, 0, 0), boss = false, id = id }
		for k, v in extra or {} do
			e[k] = v
		end
		return e
	end
	local range = H.weapon(1, neutral, nil).range
	check(pick({ at(range - 0.1, "in") }, range) == "in", "Just inside range")
	check(pick({ at(range + 0.1, "out") }, range) == nil, "Just outside range")
	check(pick({ at(20, "far"), at(8, "close"), at(range + 5, "out") }, range) == "close", "Nearest first")
	check(pick({ at(8, "close"), at(20, "far") }, range, { close = true }) == "far", "A blocked line is skipped")
	check(pick({ at(5, "dummy", { dummy = true }), at(12, "zombie") }, range) == "zombie", "Lobby dummies are never targets")
	local reach = H.weapon(1, more, nil).range -- +20% Attack range
	check(pick({ at(27, "x") }, range) == nil and pick({ at(27, "x") }, reach) == "x", "Attack range reaches 27 studs")

	-- Facing and keys.
	check(near(H.yaw(Vector3.new(0, 0, -1)), 0), "-Z is yaw 0")
	for _, dir in { Vector3.new(1, 0, 0), Vector3.new(-0.6, 0, 0.8), Vector3.new(0, 0, 1) } do
		check((CFrame.Angles(0, H.yaw(dir), 0).LookVector - dir.Unit).Magnitude < 1e-6, "Yaw faces its direction")
	end
	for _, taken in { Enum.KeyCode.Q, Enum.KeyCode.E, Enum.KeyCode.P, Enum.KeyCode.LeftShift } do
		check(H.Keys.Keyboard ~= taken, "BUILD key doesn't clash with " .. taken.Name)
	end
	for _, taken in { Enum.KeyCode.ButtonA, Enum.KeyCode.ButtonB, Enum.KeyCode.ButtonX, Enum.KeyCode.ButtonY } do
		check(H.Keys.Gamepad ~= taken, "BUILD pad button doesn't clash with " .. taken.Name)
	end
	check(H.BUILD_COOLDOWN == 8, "8 s BUILD cooldown")
	return checks
end
