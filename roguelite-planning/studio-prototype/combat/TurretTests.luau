-- Handyman turret checks (HANDYMAN_TURRET.md, 2026-10-03). Pure: no Instances, no Play. Studio Edit
-- (command bar), with the place's modules or fresh copies loaded from source:
--   local RS, SSS = game.ReplicatedStorage, game.ServerScriptService
--   local C = RS.RogueliteCombat
--   print(require(<this module>)(require(C.HandymanTurret), require(SSS.TargetGrid),
--     require(C.WeaponCatalog), require(C.CharacterStats), require(C.EconomyConfig)))
-- Covers tier stats, the balance target against WeaponCatalog (Tier I-IV at 40-50% of an average
-- class ranged weapon of the same tier, range no longer than theirs), Handyman scaling, upgrade
-- pricing and validation, who may BUILD, and targeting range through TargetGrid. Since 2026-10-04
-- also its health table, damage after armour, breaking, rebuild timing and mob target choice.
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

	-- Health (2026-10-04): 60 + 15 a wave, x1.5 a tier, x the owner's gear power health share.
	local healthTable = {
		[1] = { 60, 120, 195, 345 },
		[2] = { 90, 180, 293, 518 },
		[3] = { 135, 270, 439, 776 },
		[4] = { 203, 405, 658, 1164 },
	}
	for tier, row in healthTable do
		for i, wave in { 1, 5, 10, 20 } do
			local hp = H.maxHealth(tier, wave, 1)
			check(hp == row[i], string.format("Tier %d wave %d health %d (want %d)", tier, wave, hp, row[i]))
		end
	end
	check(H.maxHealth(1, 0, nil) == 60 and H.maxHealth(1, nil, nil) == 60, "Wave 0 or missing counts as wave 1")
	check(H.maxHealth(9, 1, 1) == 203, "Tier past IV is IV")
	check(H.maxHealth(1, 1, 9) == math.floor(60 * Stats.powerHealth(9) + 0.5), "Gear power 9 adds its health share")
	check(H.maxHealth(1, 1, 9) > 60, "Higher gear power, tougher turret")
	-- About 11 regular-zombie hits of the same wave (5 + 1.5 a wave), every wave.
	for _, wave in { 1, 5, 10, 20 } do
		local hits = math.ceil(H.maxHealth(1, wave, 1) / (5 + 1.5 * (wave - 1)))
		check(hits >= 10 and hits <= 12, string.format("Wave %d: %d zombie hits to break", wave, hits))
	end

	-- Damage after the owner's armour and contact resistance (CharacterStats.incoming), no dodge.
	check(near(H.damageTaken(11, handy), Stats.incoming(11, handy)), "Same as the player takes")
	local armoured = table.clone(neutral)
	armoured.Armor = 15
	check(near(H.damageTaken(10, armoured), 5), "15 armour halves it")
	armoured.Armor = 5
	check(near(H.damageTaken(11, armoured), 8.25), "Worked example: 11 with 5 armour is 8.25")
	local dodgy = table.clone(neutral)
	dodgy.Dodge = 60
	check(near(H.damageTaken(11, dodgy), 11), "Dodge doesn't protect it")
	check(near(H.damageTaken(11, nil), 11) and near(H.damageTaken(-3, neutral), 0), "No stats: raw; never negative")

	-- Breaking.
	local hp, broke = H.takeHit(10, 4, neutral)
	check(near(hp, 6) and not broke, "A hit it survives")
	hp, broke = H.takeHit(6, 6, neutral)
	check(hp == 0 and broke, "The hit that breaks it")
	hp, broke = H.takeHit(0, 50, neutral)
	check(hp == 0 and not broke, "A broken one takes nothing and doesn't break twice")
	hp, broke = H.takeHit(3, 50, neutral)
	check(hp == 0 and broke, "Overkill stops at 0")

	-- Rebuild timing: REBUILD_DELAY after the break, or its own cooldown if that ends sooner.
	check(H.REBUILD_DELAY == 5, "5 s to rebuild")
	check(H.rebuildAt(100, 107) == 105, "Moved 1 s before: 5 s, not 7")
	check(H.rebuildAt(100, 104) == 104, "Its own cooldown ends sooner")
	check(H.rebuildAt(100, 95) == 95, "Cooldown already over: right away")
	check(H.canBuild(ctx({ now = 100, readyAt = H.rebuildAt(100, 108) })) == false, "Broken: not yet")
	check(H.canBuild(ctx({ now = 105, readyAt = H.rebuildAt(100, 108) })), "Broken: BUILD at 105")

	-- Mob targets: a standing turret nearer (to its edge) than every living player.
	local from = Vector3.new(0, 3, 0)
	local function post(x, z, hpLeft, pad)
		local p = H.newPost(nil)
		p.Position, p.hp, p.pad = Vector3.new(x, 1.2, z), hpLeft or 100, pad or 0.25
		return p
	end
	local you = { root = "you" }
	local near6, far12 = post(6, 0), post(0, 12)
	local best, distance = H.nearer({ near6 }, from, you, 10)
	check(best == near6 and best.root == near6 and near(distance, 5.75), "Turret at 6 beats you at 10")
	best = H.nearer({ near6 }, from, you, 5)
	check(best == you, "You at 5 beat the turret at 6")
	best = H.nearer({ far12 }, from, you, 10)
	check(best == you, "A farther turret is ignored")
	best = H.nearer({ post(6, 0, 0) }, from, you, 10)
	check(best == you, "A broken turret is no target")
	best = H.nearer({ far12, near6 }, from, you, 20)
	check(best == near6, "Nearest of several turrets")
	best = H.nearer({ near6 }, from, nil, math.huge)
	check(best == near6, "No living player: the turret")
	best, distance = H.nearer({ post(7, 0, 100, 1) }, from, you, 6.5)
	check(best ~= you and near(distance, 6), "Measured to its edge: centre 7, pad 1")
	best, distance = H.nearer({}, from, you, 10)
	check(best == you and distance == 10, "No turrets: unchanged")
	check(near6.turret == true and near6.userId == 0 and near6.taken == 0, "Target table shape")
	check(H.posts ~= nil and H.BODY == 0.75, "Shared list and body width")
	return checks
end
