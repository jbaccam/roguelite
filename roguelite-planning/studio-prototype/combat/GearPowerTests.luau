-- Gear power and map scaling checks (GEAR_POWER.md). Run in Studio Edit on fresh copies:
--   fresh(GearPowerTests)(fresh(CharacterStats), fresh(RunSetupRules), require(MapBossDefs))
-- MapBossDefs is optional (nil skips the boss-health check).
-- The invariant: a player whose gear power matches a map's recommended power deals x damage and
-- has y health, and that map's enemies have x health and deal y damage, so the fight is the same
-- as a power 1 player's in Pine Valley. Returns the number of checks passed.
return function(Stats, Rules, BossDefs)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local function near(a, b, message)
		check(math.abs(a - b) < 1e-6, message .. " (" .. tostring(a) .. " vs " .. tostring(b) .. ")")
	end
	-- Profile strings, as ProfileService publishes them.
	local function get(attrs)
		return function(name)
			return attrs[name]
		end
	end

	-- Power from gear: starter tier, owned worn pieces, the pet.
	check(Stats.gearPower(get({}), "01") == 1, "No profile: a Tier I starter is power 1")
	check(Stats.gearPower(get({ ProfileWeapons = "01:1:0" }), "01") == 1, "Fresh account: power 1")
	check(Stats.gearPower(get({ ProfileWeapons = "01:2:0,00:1:0" }), "01") == 2, "Tier II starter: power 2")
	check(Stats.gearPower(get({ ProfileWeapons = "01:2:0" }), "30") == 1, "An unowned starter counts as Tier I")
	local armor = "Iron.Helmet:1:0,Iron.Chest:1:0,Iron.Legs:2:0,Iron.Boots:1:0"
	local wearing = "Helmet:Iron,Chest:Iron,Legs:Iron,Boots:Iron"
	check(Stats.gearPower(get({ ProfileWeapons = "01:2:0", ProfileArmor = armor, ProfileWearing = wearing }), "01") == 7,
		"Tier II starter + Iron pieces I, I, II, I = 7")
	check(Stats.gearPower(get({ ProfileWeapons = "01:1:0", ProfileArmor = "Iron.Helmet:3:0", ProfileWearing = wearing }), "01") == 4,
		"Only owned worn pieces count")
	check(Stats.gearPower(get({ ProfileWeapons = "01:1:0", ProfilePet = "Fox", ProfilePets = "Fox:3:0" }), "01") == 4,
		"A Tier III pet adds 3")
	check(Stats.gearPower(get({ ProfileWeapons = "01:1:0", ProfilePet = "", ProfilePets = "Fox:3:0" }), "01") == 1,
		"An owned pet that isn't equipped adds nothing")

	-- The curve: +12% damage and +6% health a point above 1; never below x1.
	near(Stats.powerDamage(1), 1, "Power 1 damage")
	near(Stats.powerHealth(1), 1, "Power 1 health")
	near(Stats.powerDamage(6), 1.6, "Power 6 damage")
	near(Stats.powerHealth(6), 1.3, "Power 6 health")
	near(Stats.powerDamage(0), 1, "Power 0 (no profile) never weakens")
	near(Stats.powerDamage(nil), 1, "Missing power never weakens")
	check(Stats.ById.GearPower ~= nil, "GearPower is a listed stat")

	-- Maps: recommended power climbs; enemies match the curve at it; each Normal stays under the
	-- previous map's Hard; the run's first value (extra waves) is 0.
	local hard = Rules.difficulty("Hard")
	local normal = Rules.difficulty("Normal")
	local previous
	for i, m in Rules.Maps do
		check(type(m.power) == "number", m.id .. " has a recommended power")
		local waves, hp, damage = Rules.enemyScale(m.id, "Normal")
		check(waves == 0, m.id .. " has no head start")
		near(hp, Stats.powerDamage(m.power) * normal.hp, m.id .. " enemy health = damage at its power")
		near(damage, Stats.powerHealth(m.power) * normal.damage, m.id .. " enemy damage = health at its power")
		-- Same fight at the recommended power: enemy health / player damage, enemy damage / player health.
		near(hp / Stats.powerDamage(m.power), normal.hp, m.id .. " time to kill matches Pine Valley")
		near(damage / Stats.powerHealth(m.power), normal.damage, m.id .. " hits to die match Pine Valley")
		local _, hpHard, damageHard = Rules.enemyScale(m.id, "Hard")
		near(hpHard, hp * hard.hp / normal.hp, m.id .. " Hard multiplies health")
		near(damageHard, damage * hard.damage / normal.damage, m.id .. " Hard multiplies damage")
		if previous then
			check(m.power > previous.power, m.id .. " recommends more power than " .. previous.id)
			local _, prevHard = Rules.enemyScale(previous.id, "Hard")
			check(hp < prevHard, m.id .. " Normal stays under " .. previous.id .. " Hard")
		end
		-- Bosses: solo Normal health = the Hammer's 18,000 x Normal HP x the map's damage curve.
		local hpScale, damageScale = Rules.bossScale("Normal", 1, m.id)
		near(damageScale, Stats.powerHealth(m.power) * normal.damage, m.id .. " boss damage follows the curve")
		local bossId = ({ BeachCove = "KingCrab", DesertBasin = "Pharaoh", FrozenPass = "FrostCyclops", VolcanicCrater = "Dragon" })[m.id]
		local authored = bossId and BossDefs and BossDefs[bossId] and BossDefs[bossId].health or (i == 1 and 18000 or nil)
		if authored then
			near(authored * hpScale, 18000 * Stats.powerDamage(m.power) * normal.hp, m.id .. " boss health = Hammer x the curve")
		end
		local hp2 = Rules.bossScale("Normal", 2, m.id)
		near(hp2, hpScale * (1 + Rules.BossPlayerHp), m.id .. " a second player adds BossPlayerHp")
		for _, difficulty in Rules.Difficulties do
			local soloHp, soloDamage = Rules.bossScale(difficulty.id, 1, m.id)
			for players = 1, 4 do
				local partyHp, partyDamage = Rules.bossScale(difficulty.id, players, m.id)
				near(partyHp, soloHp * players, m.id .. " linear HP for six weapons per additional player")
				near(partyHp / players, soloHp, m.id .. " ideal aggregate DPS preserves boss kill time")
				near(partyDamage, soloDamage, m.id .. " multiplayer never increases damage per hit")
			end
		end
		previous = m
	end
	for _, case in {{0,1},{-9,1},{2.9,2},{8,4},{math.huge,4},{-math.huge,1},{0/0,1},{'3',3},{'bad',1}} do
		check(Rules.partySize(case[1]) == case[2], "bounded server party count")
	end
	check(Rules.partySize(nil) == 1, "missing party count preserves solo")
	check(Rules.BossPlayerHp == 1, "one full six-slot build per additional participant")
	return checks
end
