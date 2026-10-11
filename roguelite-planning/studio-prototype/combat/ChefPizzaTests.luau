-- ChefPizza rule checks: chance gating with a seeded generator, Chef class only, Chef weapons only,
-- 1 s spacing, the cap of 4 with the oldest removed, lifetime and blink timing, heal = 10% x
-- Recovery, the server pickup check (distance, gone, expired, dead) and Full Belly stacks (cap 5,
-- 10 s refreshed by each slice, all lost together, stat terms). Pure: plain tables and
-- numbers. Run `python roguelite-planning/studio-prototype/combat/run_chef_pizza_tests.py
-- build/luau-validation/luau.exe`, or in Studio Edit: `ChefPizzaTests(ChefPizza, CharacterStats,
-- WeaponCatalog)`. Returns the number of checks. Stats is optional; given, Recovery uses its mult
-- (CharacterService.heal). Weapons is optional; given, every catalog weapon is checked by class tag.
return function(P,Stats,Weapons)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local function near(a, b) return math.abs(a - b) < 1e-9 end

	-- A seeded generator with Random's NextNumber (Park-Miller, exact in doubles), so the CLI (no
	-- Random) and Studio agree.
	local function seeded(seed)
		local state = seed
		return {
			calls = 0,
			NextNumber = function(self)
				self.calls += 1
				state = state * 16807 % 2147483647
				return (state - 1) / 2147483646
			end,
		}
	end
	-- A generator that always returns v, to put a roll exactly at the edge.
	local function fixed(v)
		return { calls = 0, NextNumber = function(self) self.calls += 1; return v end }
	end

	local pan = { id = "01", class = "Chef" }
	local glock = { id = "00", class = "Gunner" }
	local function kill(o)
		o.class = o.class or "Chef"
		o.weapon = o.weapon == nil and pan or o.weapon
		o.weaponId = o.weaponId or (type(o.weapon) == "table" and o.weapon.id) or nil
		o.now = o.now or 100
		return P.decide(o)
	end

	-- Constants match the design.
	check(P.CHANCE == .15 and P.SPACING == 1 and P.MAX_PER_CHEF == 4, "Chance, spacing or cap differs from the design")
	check(P.LIFETIME == 12 and P.BLINK == 3 and P.HEAL_FRACTION == .1, "Lifetime, blink or heal differs from the design")

	-- Chance gating: about 15% over many eligible kills with a seeded generator, and the same seed
	-- gives the same drops.
	local function rate(seed, n)
		local rng, hits = seeded(seed), 0
		for _ = 1, n do if kill({ rng = rng }) then hits += 1 end end
		return hits / n, rng.calls
	end
	local r1, calls = rate(42, 20000)
	check(calls == 20000, "Every eligible kill should spend exactly one roll")
	check(r1 > .14 and r1 < .16, ("Drop rate %.4f is not about 15%%"):format(r1))
	check(rate(42, 500) == rate(42, 500), "The same seed should give the same drops")
	check(kill({ rng = fixed(.1499) }) == true, "A roll just under 15% should drop")
	local ok, why = kill({ rng = fixed(.15) })
	check(ok == false and why == "chance", "A roll of exactly 15% should not drop")
	check(kill({ rng = fixed(.5), chance = 1 }) == true, "TestPizzaChance 1 should always drop")
	check(kill({ rng = fixed(0), chance = 0 }) == false, "TestPizzaChance 0 should never drop")

	-- Chef class only, and a wrong class spends no roll.
	for _, class in { "Brawler", "Gunner", "Thrower", "Juggler", "Handyman", "Mage" } do
		local rng = fixed(0)
		ok, why = kill({ class = class, rng = rng })
		check(ok == false and why == "class" and rng.calls == 0, class .. " kills should never drop pizza")
	end
	local nobody = fixed(0)
	ok, why = P.decide({ class = nil, weapon = pan, weaponId = "01", now = 1, rng = nobody })
	check(ok == false and why == "class" and nobody.calls == 0, "A kill with no class should never drop pizza")

	-- Chef weapons only, by class tag (d.class, or d.home for a bare table), never by id.
	check(P.isChefWeapon(pan, "01"), "Frying Pan with class Chef is a Chef weapon")
	check(not P.isChefWeapon(glock, "00"), "Glock is not a Chef weapon")
	check(not P.isChefWeapon({ class = "Brawler" }, "01"), "The class tag decides, not the id")
	check(P.isChefWeapon({ class = "Chef" }, "99"), "Any weapon tagged Chef counts, whatever its id")
	check(P.isChefWeapon({ home = "Chef" }, "05") and not P.isChefWeapon({ home = "Thrower" }, "05"), "A bare {home=} table counts its home")
	check(P.WEAPON_IDS == nil, "No hard-coded Chef weapon id list")
	check(not P.isChefWeapon({ class = "Chef", godly = true }, "36"), "Godlies are never Chef weapons")
	check(not P.isChefWeapon(nil, "01"), "A kill with no catalog weapon is not a Chef weapon")
	check(not P.isChefWeapon(nil, "Turret") and not P.isChefWeapon(nil, "Bloater"), "Turret and Bloater credit are not Chef weapons")

	-- Every Chef weapon in the real catalog (2026-10-10: a class ability, not the Pizza Cutter's).
	-- A Chef's kill with each one drops at the same 15%; a non-Chef holding it gets nothing (like
	-- specialty); a Chef's kill with any other weapon (other classes, Godlies) gets nothing.
	if Weapons then
		local chefIds, rolls = {}, {}
		for _, w in Weapons.List do
			local tagged = Weapons.inClass(w, "Chef")
			check(P.isChefWeapon(w, w.id) == tagged, "Chef weapon follows the class tag: " .. w.name)
			if tagged then
				table.insert(chefIds, w.id)
				check(kill({ weapon = w, rng = fixed(.1499) }) == true, "A Chef's " .. w.name .. " kill drops under 15%")
				ok, why = kill({ weapon = w, rng = fixed(.15) })
				check(ok == false and why == "chance", w.name .. " has no higher rate than 15%")
				local seededRate = 0
				local g = seeded(7)
				for _ = 1, 5000 do if kill({ weapon = w, rng = g }) then seededRate += 1 end end
				table.insert(rolls, seededRate)
				for _, class in { "Brawler", "Gunner", "Juggler", "Handyman", "Mage" } do
					local r = fixed(0)
					ok, why = kill({ class = class, weapon = w, rng = r })
					check(ok == false and why == "class" and r.calls == 0, class .. " holding " .. w.name .. " drops nothing")
				end
			else
				local r = fixed(0)
				ok, why = kill({ weapon = w, rng = r })
				check(ok == false and why == "weapon" and r.calls == 0, "A Chef's " .. w.name .. " kill drops nothing")
			end
		end
		table.sort(chefIds)
		check(table.concat(chefIds, ",") == "01,05,14,15,16,42", "Chef weapons: Pan, Spatula, Molotov, Egg, Steak, Pizza Cutter; got " .. table.concat(chefIds, ","))
		for i = 2, #rolls do check(rolls[i] == rolls[1], "Every Chef weapon drops at the same rate (same seed, same drops)") end
	end
	local rng = fixed(0)
	ok, why = kill({ weapon = glock, rng = rng })
	check(ok == false and why == "weapon" and rng.calls == 0, "A Chef's Glock kill should never drop pizza")
	ok, why = kill({ weapon = false, weaponId = "Turret", rng = fixed(0) })
	check(ok == false and why == "weapon", "A Chef's turret kill should never drop pizza")

	-- Spacing: at least 1 s between one Chef's drops; a spaced-out kill spends no roll.
	rng = fixed(0)
	ok, why = kill({ now = 100.9, lastDrop = 100, rng = rng })
	check(ok == false and why == "spacing" and rng.calls == 0, "A drop 0.9 s after the last should be blocked")
	ok, why = kill({ now = 100.99, lastDrop = 100, rng = fixed(0) })
	check(ok == false and why == "spacing", "A drop 0.99 s after the last should be blocked")
	check(kill({ now = 101, lastDrop = 100, rng = fixed(0) }) == true, "A drop 1 s after the last should be allowed")
	check(kill({ now = 100, lastDrop = nil, rng = fixed(0) }) == true, "A Chef's first drop has no spacing")
	-- A burst of guaranteed rolls 0.1 s apart for 6 s drops on 0, 1, 2 ... 6: never closer.
	local last, drops = nil, {}
	for i = 0, 60 do
		local now = i / 10
		if kill({ now = now, lastDrop = last, rng = fixed(0) }) then last = now; table.insert(drops, now) end
	end
	check(#drops == 7, ("Expected 7 drops in 6 s of instant kills, got %d"):format(#drops))
	for i = 2, #drops do check(drops[i] - drops[i - 1] >= P.SPACING - 1e-9, "Drops closer than 1 s") end

	-- Cap 4 per Chef: a 5th removes his oldest, never a slice already flying to someone.
	local function slices(...)
		local list = {}
		for _, born in { ... } do table.insert(list, { born = born }) end
		return list
	end
	check(#P.evictions(slices(1, 2, 3)) == 0, "Three on the ground: the 4th needs no removal")
	local s = slices(3, 1, 4, 2)
	local out = P.evictions(s)
	check(#out == 1 and out[1].born == 1, "A 5th slice should remove the oldest (born 1)")
	s[2].taken = true -- the oldest is flying to a player
	out = P.evictions(s)
	check(#out == 1 and out[1].born == 2, "A slice already flying is never removed; the next oldest goes")
	out = P.evictions(slices(5, 1, 4, 2, 3)) -- over the cap somehow: back down to 3 + the new one
	check(#out == 2 and out[1].born == 1 and out[2].born == 2, "Over the cap should remove the two oldest")
	local all = slices(1, 2, 3, 4)
	for _, x in all do x.taken = true end
	check(#P.evictions(all) == 0, "Nothing to remove when every slice is flying")
	check(#P.evictions({}) == 0, "No slices, nothing to remove")
	-- Simulate a Chef dropping 7 slices: he never has more than 4 and keeps the newest 4.
	local ground = {}
	for born = 1, 7 do
		for _, x in P.evictions(ground) do table.remove(ground, table.find(ground, x)) end
		table.insert(ground, { born = born })
		check(#ground <= P.MAX_PER_CHEF, "A Chef had more than 4 slices down")
	end
	table.sort(ground, function(a, b) return a.born < b.born end)
	check(ground[1].born == 4 and ground[4].born == 7, "The newest 4 slices should remain")

	-- Lifetime and blink: lasts 12 s, solid until the last 3 s, then blinks (faster in the last 1.2),
	-- and never blinks while flying to a player.
	local born = 50
	local expires = P.expiresAt(born)
	check(expires == 62, "A slice born at 50 should expire at 62")
	for t = born, expires - P.BLINK - .01, .01 do
		check(not P.hidden(t, expires, false), ("Hidden at %.2f, before the last 3 s"):format(t))
	end
	local hiddenSlow, shownSlow, hiddenFast, shownFast = 0, 0, 0, 0
	for t = expires - P.BLINK + .001, expires - .001, .01 do
		local h = P.hidden(t, expires, false)
		check(not P.hidden(t, expires, true), "A slice flying to a player should never blink")
		if expires - t < 1.2 then
			if h then hiddenFast += 1 else shownFast += 1 end
		elseif h then hiddenSlow += 1 else shownSlow += 1 end
	end
	check(hiddenSlow > 0 and shownSlow > 0, "The last 3 s should blink")
	check(hiddenFast > 0 and shownFast > 0, "The last 1.2 s should blink")
	-- Faster in the last 1.2 s: more on/off switches per second.
	local function switches(a, b)
		local n, prev = 0, nil
		for t = a, b, .005 do
			local h = P.hidden(t, expires, false)
			if prev ~= nil and h ~= prev then n += 1 end
			prev = h
		end
		return n / (b - a)
	end
	check(switches(expires - 1.15, expires - .05) > switches(expires - 2.95, expires - 1.25) * 1.5, "Blinking should speed up in the last 1.2 s")

	-- Heal: 10% of the picker's max HP, times Recovery, through CharacterService.heal's formula.
	local mult = Stats and Stats.mult or function(v) return math.max(.05, 1 + v / 100) end
	local function heal(hp, maxHp, recovery)
		return math.min(maxHp, hp + math.max(0, P.healBase(maxHp)) * mult(recovery))
	end
	check(near(P.healBase(100), 10) and near(P.healBase(150), 15), "Base heal should be 10% of max HP")
	check(P.healBase(0) == 0 and P.healBase(-5) == 0 and P.healBase(nil) == 0, "Bad max HP should heal nothing")
	check(near(heal(50, 100, 0), 60), "Recovery 0: 100 max HP heals 10")
	check(near(heal(50, 150, 25), 50 + 18.75), "Chef's +25% Recovery: 150 max HP heals 18.75")
	check(near(heal(50, 100, 100), 70), "Recovery +100%: 100 max HP heals 20")
	check(near(heal(50, 100, -50), 55), "Recovery -50%: 100 max HP heals 5")
	check(heal(95, 100, 100) == 100, "Healing stops at max HP")
	check(heal(100, 100, 0) == 100, "A full-health player stays at max (the slice is still used up)")

	-- Server pickup check.
	local function pick(o)
		local base = { exists = true, taken = false, born = 10, now = 12, rest = .3, alive = true, distance = 3, radius = 4 }
		for k, v in o do base[k] = v end
		return P.canCollect(base)
	end
	check(pick({}) == true, "A living player 3 studs away inside 4 should pick it up")
	check(pick({ distance = 4 }) == true, "Exactly at the radius counts")
	ok, why = pick({ distance = 4.01 })
	check(ok == false and why == "far", "Just outside the radius should be refused")
	ok, why = pick({ distance = 0 / 0 })
	check(ok == false and why == "far", "A NaN distance should be refused")
	ok, why = pick({ distance = math.huge })
	check(ok == false and why == "far", "No body (infinite distance) should be refused")
	ok, why = pick({ exists = false })
	check(ok == false and why == "gone", "A removed slice can't be picked up")
	ok, why = pick({ taken = true })
	check(ok == false and why == "taken", "A slice flying to someone else can't be taken twice")
	ok, why = pick({ now = 10.1 })
	check(ok == false and why == "resting", "A slice can't be grabbed in its first 0.3 s")
	check(pick({ now = 10.3 }) == true, "After 0.3 s it can be grabbed")
	ok, why = pick({ now = 22 })
	check(ok == false and why == "expired", "At 12 s the slice is gone")
	check(pick({ now = 21.99 }) == true, "Just before 12 s it can still be picked up")
	ok, why = pick({ now = 30 })
	check(ok == false and why == "expired", "Long after expiry nothing is picked up")
	ok, why = pick({ alive = false })
	check(ok == false and why == "dead", "A dead or downed player can't pick it up")

	-- Pose: bobs within BOB of its spot and turns steadily.
	for t = 0, 12, .05 do
		local bob = P.pose(3.3, 3.3 + t)
		check(math.abs(bob) <= P.BOB + 1e-9, "Bob left its range")
	end
	local _, a0 = P.pose(5, 6)
	local _, a1 = P.pose(5, 7)
	check(near(a1 - a0, P.SPIN_SPEED), "Spin should turn SPIN_SPEED radians a second")

	-- Full Belly: one stack per slice eaten, up to 5; every pickup restarts the 10 s timer for all
	-- stacks; when it runs out they all go at once.
	check(P.BUFF_STACKS == 5 and P.BUFF_SECONDS == 10, "Full Belly cap or duration differs from the design")
	check(P.BUFF_PER_STACK.Damage == 4 and P.BUFF_PER_STACK.AttackSpeed == 4 and P.BUFF_SPEED_PER_STACK == 3, "Full Belly per-stack numbers differ from the design")
	local stacks, untilTime = P.stacksAfterPickup(100, nil, nil)
	check(stacks == 1 and untilTime == 110, "The first slice gives 1 stack until 10 s later")
	check(P.buffStacks(105, stacks, untilTime) == 1 and P.buffStacks(109.99, stacks, untilTime) == 1, "The stack lasts 10 s")
	check(P.buffStacks(110, stacks, untilTime) == 0 and P.buffStacks(200, stacks, untilTime) == 0, "At 10 s the stack is gone")
	-- Stacking and the cap: slices every 2 s climb 1, 2, 3, 4, 5, then stay at 5.
	stacks, untilTime = nil, nil
	for i = 1, 8 do
		stacks, untilTime = P.stacksAfterPickup(100 + 2 * i, stacks, untilTime)
		check(stacks == math.min(i, 5), ("Slice %d should leave %d stacks, got %d"):format(i, math.min(i, 5), stacks))
		check(untilTime == 110 + 2 * i, "Every slice restarts the timer")
	end
	check(P.buffStacks(125.9, stacks, untilTime) == 5, "All 5 stacks live until 10 s after the last slice")
	check(P.buffStacks(126, stacks, untilTime) == 0, "All 5 stacks go together when the timer runs out")
	-- Refresh keeps every stack: 3 stacks with 1 s left, another slice -> 4 stacks, a full 10 s.
	stacks, untilTime = P.stacksAfterPickup(49, 3, 50)
	check(stacks == 4 and untilTime == 59, "A slice before expiry adds a stack and refreshes all of them")
	-- After expiry the count starts again at 1, never at the old count + 1.
	stacks, untilTime = P.stacksAfterPickup(50, 3, 50)
	check(stacks == 1 and untilTime == 60, "A slice after expiry starts again at 1 stack")
	stacks = P.stacksAfterPickup(51, 5, 60)
	check(stacks == 5, "The cap holds at 5")
	check(P.buffStacks(1, 99, 2) == 5 and P.buffStacks(1, -3, 2) == 0 and P.buffStacks(1, 2.7, 2) == 2, "Live stacks stay whole and within 0-5")
	check(P.buffStacks(1, "3", 2) == 0 and P.buffStacks(nil, 3, 2) == 0 and P.buffStacks(0 / 0, 3, 2) == 0, "Bad input means no stacks")
	-- Time left for the HUD bar.
	local left, share = P.buffLeft(104, 110)
	check(near(left, 6) and near(share, .6), "6 s of 10 left is a 60% bar")
	left, share = P.buffLeft(111, 110)
	check(left == 0 and share == 0, "An expired buff has an empty bar")
	left, share = P.buffLeft(90, 110)
	check(left == 10 and share == 1, "The bar never shows more than 10 s")
	check(select(1, P.buffLeft(nil, 110)) == 0, "No time, no bar")
	-- Stat terms: points on Damage and Attack speed, a percent of Movement speed.
	check(P.buffBonus(0) == nil and P.buffBonus(nil) == nil and P.buffBonus(-1) == nil, "No stacks, no bonus")
	local flat, percent = P.buffBonus(3)
	check(flat.Damage == 12 and flat.AttackSpeed == 12 and percent.MoveSpeed == 9, "3 stacks: +12% damage, +12% attack speed, +9% speed")
	flat, percent = P.buffBonus(9)
	check(flat.Damage == 20 and flat.AttackSpeed == 20 and percent.MoveSpeed == 15, "The bonus never passes 5 stacks")
	check(P.buffText() == "+4% damage and attack speed, +3% speed per stack (up to 5, 10 s)", "Ability text: " .. P.buffText())
	-- Through the real stat resolver (CharacterService.refresh adds flat and percent the same way).
	if Stats and Stats.resolve and Stats.Classes and Stats.Classes.Chef then
		flat, percent = P.buffBonus(5)
		local plain = Stats.resolve("Chef", nil, {}, {}, {})
		local fed = Stats.resolve("Chef", nil, {}, flat, percent)
		check(near(fed.Damage - plain.Damage, 20) and near(fed.AttackSpeed - plain.AttackSpeed, 20), "5 stacks: +20 Damage and +20 Attack speed on a Chef")
		check(near(fed.MoveSpeed, plain.MoveSpeed * 1.15), ("5 stacks: speed x1.15 (%.2f -> %.2f)"):format(plain.MoveSpeed, fed.MoveSpeed))
		check(fed.MaxHP == plain.MaxHP and fed.Recovery == plain.Recovery, "Full Belly touches nothing else")
		if Stats.mult then
			-- Example: a weapon's damage x1.2 and its attacks 1.2x as fast at 5 stacks (about +44% DPS).
			check(near(Stats.mult(fed.Damage) / Stats.mult(plain.Damage), 1.2), "5 stacks: x1.2 damage on a Chef")
		end
	end

	return checks
end
