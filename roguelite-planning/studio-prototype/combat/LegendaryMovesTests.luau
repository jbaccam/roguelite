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

	-- Swing movers (2026-10-09). The Rolling Slice keeps the card's 20 studs; slashes grow with Attack Range.
	local wheel, katana = Catalog.Legendary["42"], Catalog.Legendary["03"]
	near(L.moverRange(wheel, 1), 20, "wheel rolls 20 studs")
	near(L.moverRange(wheel, 1.5), 20, "Attack Range never changes the wheel's distance")
	near(L.moverRange(katana, 1.5), katana.range * 1.5, "Attack Range grows the Katana slash")
	-- The lane grows with Area Size, between 2 and 9 studs.
	near(L.laneWidth(wheel, 1), 3, "3-stud wheel lane")
	near(L.laneWidth(wheel, 2), 6, "Area Size x2 doubles the lane")
	near(L.laneWidth(wheel, 5), 9, "lane capped at 9")
	near(L.laneWidth(wheel, 0.5), 2, "lane never below 2")
	-- Only melee weapons' moves leave from the swing; the wheel starts at the feet, the slash at the cut.
	for id, spec in Catalog.Legendary do
		if L.MoverLead[spec.move] then check(Catalog.ById[id].kind == "Melee", id .. " " .. spec.move .. " comes from a melee swing") end
	end
	check(L.MoverLead.Roll and L.MoverLead.Slash and L.MoverLead.Beam, "slash, beam and wheel are swing movers")
	check(L.MoverLead.Roll < L.MoverLead.Slash, "the wheel starts closer than the slash")
	-- The lane check the mover uses: cut inside half the lane plus 1 stud of slack, missed beyond, measured flat.
	local a0, b0 = Vector3.zero, Vector3.new(0, 0, -20)
	check(L.segmentDistance(Vector3.new(2.4, 3, -10), a0, b0) <= L.laneWidth(wheel, 1) * 0.5 + 1, "enemy 2.4 studs off the lane is cut")
	check(L.segmentDistance(Vector3.new(2.6, 3, -10), a0, b0) > L.laneWidth(wheel, 1) * 0.5 + 1, "enemy 2.6 studs off the lane is missed")
	check(L.due(4, wheel.every) and not L.due(3, wheel.every) and L.due(8, wheel.every), "every 4th swing rolls")

	-- Catalog: exactly the eight Legendaries have a move, live only at Tier IV (Pizza Cutter 2026-10-09).
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
	check(count == 8, "eight moves")
	check(Catalog.legendaryMove("01", 4) == nil, "a Common weapon has none")
	-- The user's counts (plan J).
	check(Catalog.Legendary["03"].move == "Slash" and Catalog.Legendary["03"].every == 3, "Katana every 3rd swing")
	check(Catalog.Legendary["11"].move == "Split" and Catalog.Legendary["11"].every == 4 and Catalog.Legendary["11"].minis == 3, "Rocket every 4th, into 3")
	check(Catalog.Legendary["18"].move == "Flush" and Catalog.Legendary["18"].every == 5 and Catalog.Legendary["18"].cards == 5, "Cards every 5th, five cards")
	check(Catalog.Legendary["22"].move == "Strike" and Catalog.Legendary["22"].hits == 5, "STRIKE at 5+ enemies")
	check(Catalog.Legendary["25"].move == "Shock", "Wrecking Ball shockwave")
	check(Catalog.Legendary["32"].move == "Beam" and Catalog.Legendary["32"].every == 1, "Excalibur every swing")
	check(Catalog.Legendary["31"].move == "Thunder" and Catalog.Legendary["31"].every == 4, "Mjolnir every 4th throw")
	-- Rolling Slice (2026-10-09 design): every 4th swing, 60%, a 20-stud lane; it has its card line.
	local roll = Catalog.Legendary["42"]
	check(roll.move == "Roll" and roll.every == 4 and roll.factor == 0.6 and roll.range == 20, "Pizza Cutter every 4th swing, 60%, 20 studs")
	check(Catalog.LegendaryNames.Roll == "Rolling Slice" and type(Catalog.legendaryText("42")) == "string", "Rolling Slice name and text")
	return checks
end
