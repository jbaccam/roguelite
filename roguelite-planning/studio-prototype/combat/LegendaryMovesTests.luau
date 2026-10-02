-- Legendary move checks (plan J item 8, rarity step 3). Edit mode, no Play: pass fresh requires of
-- LegendaryMoves (the server module; only its pure helpers are used) and WeaponCatalog.
return function(L, Catalog)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local function near(a, b, message) check(math.abs(a - b) < 1e-6, message .. ": " .. tostring(a) .. " vs " .. tostring(b)) end

	-- Which attack is the move: every 3rd swing is swings 3, 6, 9.
	for count = 1, 9 do check(L.due(count, 3) == (count % 3 == 0), "every 3rd " .. count) end
	for count = 1, 4 do check(L.due(count, 1), "every attack " .. count) end
	check(not L.due(4, 5) and L.due(5, 5) and L.due(10, 5), "every 5th throw")

	-- Movers: flat distance to the swept stretch.
	local d, t = L.segmentDistance(Vector3.new(5, 3, 2), Vector3.zero, Vector3.new(10, 0, 0))
	near(d, 2, "distance ignores height")
	near(t, 0.5, "halfway along")
	d = L.segmentDistance(Vector3.new(-3, 0, 4), Vector3.zero, Vector3.new(10, 0, 0))
	near(d, 5, "behind the start measures to the start")

	-- The Royal Flush fans five cards evenly, the middle one straight at the target.
	local forward = Vector3.new(0, 0, -1)
	local cards = L.fan(forward, 5, 26)
	check(#cards == 5, "five cards")
	near(cards[3]:Dot(forward), 1, "middle card goes straight")
	near(math.deg(math.acos(math.clamp(cards[1]:Dot(forward), -1, 1))), 13, "outer card 13 degrees off")
	near(cards[1]:Dot(forward), cards[5]:Dot(forward), "fan is symmetric")
	for i, c in cards do near(c.Magnitude, 1, "card direction " .. i .. " is a unit vector") near(c.Y, 0, "cards fly flat") end
	check(#L.fan(forward, 1, 26) == 1 and L.fan(forward, 1, 26)[1]:Dot(forward) > 0.999, "a single card goes straight")

	-- Mini rockets: the target first, then others once each; few enemies means the target takes the rest.
	local a, b, c = {}, {}, {}
	local list = L.splitTargets(a, { b, a, c, b }, 3)
	check(list[1] == a and list[2] == b and list[3] == c, "target, then the nearest others")
	list = L.splitTargets(a, {}, 3)
	check(#list == 3 and list[2] == a and list[3] == a, "a lone target takes all three")
	list = L.splitTargets(a, { b }, 3)
	check(list[1] == a and list[2] == b and list[3] == a, "two enemies share three minis")

	-- Blast falloff and the ring's arrival time.
	near(L.falloff(0, 5), 1, "full damage at the centre")
	near(L.falloff(5, 5), 0.35, "35% at the edge")
	near(L.falloff(9, 5), 0.35, "never below the edge value")
	near(L.ringDelay(0, 10, 0.4), 0, "the ring starts at once")
	near(L.ringDelay(5, 10, 0.4), 0.2, "halfway out at half time")
	near(L.ringDelay(30, 10, 0.4), 0.4, "past the edge is the end")

	-- Catalog: exactly the seven Legendaries have a move, live only at Tier IV.
	local legendaryIds = {}
	for _, w in Catalog.List do
		if w.rarity == "Legendary" then legendaryIds[w.id] = true end
	end
	local count = 0
	for id, spec in Catalog.Legendary do
		count += 1
		check(legendaryIds[id], id .. " is a Legendary weapon")
		check(type(spec.factor) == "number" and spec.factor > 0 and spec.factor <= 1.5, id .. " move hit is bounded")
		for tier = 1, 3 do check(Catalog.legendaryMove(id, tier) == nil, id .. " has no move at Tier " .. tier) end
		check(Catalog.legendaryMove(id, 4) == spec, id .. " move at Tier IV")
	end
	for id in legendaryIds do check(Catalog.Legendary[id] ~= nil, id .. " Legendary has a move") end
	check(count == 7, "seven moves")
	check(Catalog.legendaryMove("01", 4) == nil, "a Common weapon has none")
	-- The user's counts (plan J).
	check(Catalog.Legendary["03"].move == "Slash" and Catalog.Legendary["03"].every == 3, "Katana every 3rd swing")
	check(Catalog.Legendary["11"].move == "Split" and Catalog.Legendary["11"].every == 4 and Catalog.Legendary["11"].minis == 3, "Rocket every 4th, into 3")
	check(Catalog.Legendary["18"].move == "Flush" and Catalog.Legendary["18"].every == 5 and Catalog.Legendary["18"].cards == 5, "Cards every 5th, five cards")
	check(Catalog.Legendary["22"].move == "Strike" and Catalog.Legendary["22"].hits == 5, "STRIKE at 5+ enemies")
	check(Catalog.Legendary["25"].move == "Shock", "Wrecking Ball shockwave")
	check(Catalog.Legendary["32"].move == "Beam" and Catalog.Legendary["32"].every == 1, "Excalibur every swing")
	check(Catalog.Legendary["31"].move == "Thunder" and Catalog.Legendary["31"].every == 4, "Mjolnir every 4th throw")
	return checks
end
