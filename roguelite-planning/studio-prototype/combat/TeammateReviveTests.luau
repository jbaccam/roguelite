-- TeammateRevive checks (the ring's speed and drain, validation, the reviver guard, one revive per
-- down). `TeammateReviveTests(TeammateRevive)` returns the number of checks; run_survival_tests.py runs
-- it in the Luau CLI, or run it in Studio Edit on a fresh copy. Players are plain tables, the clock is
-- a number the test moves, and the view only records what it would have drawn, so no instance is made.
return function(R)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local function near(a, b, tolerance)
		return math.abs(a - b) <= (tolerance or 1e-6)
	end
	local H, REACH = R.HOLD_SECONDS, R.RANGE + R.SLACK

	-- The 2026-10-10 numbers (play-test: "it takes too long and it's too easy to die when you're doing it").
	check(H == 2.5 and R.RANGE == 16 and REACH == 20, "2.5 s alone (was 5), 16-stud prompt (was 10), 20 studs on the server")
	check(near(R.rate(1), 0.4) and near(1 / R.rate(2), 5 / 3) and near(1 / R.rate(3), 1.25), "1 reviver 2.5 s, 2 revivers 1.67 s, 3 revivers 1.25 s")
	check(near(R.rate(0), -0.2), "Nobody holding: drains 20% a second (full to empty in 5 s)")
	check(R.GUARD == 0.4, "A reviver takes 40% damage (60% less)")
	check(R.PROMPT_HOLD > 2 * H, "The prompt's own hold never ends before the server's revive")

	-- A fresh world: ana, ben, cal and dan in the run, all alive at the origin, nobody down.
	local function world()
		local w = {
			now = 0,
			frozen = false,
			revived = {},
			alive = {},
			member = {},
			down = {},
			pos = {},
			made = {},
			destroyed = 0,
			guards = {},
			guardWrites = 0,
		}
		w.ana, w.ben, w.cal, w.dan = { name = "ana" }, { name = "ben" }, { name = "cal" }, { name = "dan" }
		for _, p in { w.ana, w.ben, w.cal, w.dan } do
			w.alive[p], w.member[p], w.pos[p] = true, true, Vector3.zero
		end
		local view = {}
		function view.create(s, began, ended, at)
			table.insert(w.made, { s = s, began = began, ended = ended })
			return at
		end
		function view.publish(s, reviver, progress, rate, at, count)
			s.shownReviver, s.shownProgress, s.shownRate, s.shownAt, s.shownCount = reviver, progress, rate, at, count
		end
		function view.destroy(s)
			s.gone = true
			w.destroyed += 1
		end
		w.svc = R.new({
			manual = true,
			view = view,
			clock = function()
				return w.now
			end,
			spawn = function(f, ...)
				f(...)
			end,
			guard = function(q, on)
				w.guards[q] = on or nil
				w.guardWrites += 1
			end,
			positionOf = function(q)
				return w.alive[q] and w.pos[q] or nil
			end,
			canHelp = function(q)
				return w.alive[q] == true and w.member[q] == true and not w.down[q]
			end,
			isDown = function(p)
				return w.down[p] ~= nil
			end,
			frozen = function()
				return w.frozen
			end,
			onRevive = function(p, q)
				table.insert(w.revived, { p = p, q = q, at = w.now })
				w.down[p] = nil -- RogueliteMeta's rise clears the down
			end,
		})
		-- p falls at `at` (default the origin), like onDied.
		function w.fall(p, at)
			w.down[p] = true
			w.alive[p] = false
			w.svc.spot(p, at or Vector3.zero)
		end
		-- Step the service every 0.1 s (its real STEP) up to t.
		function w.at(t)
			while w.now + 0.1 < t - 1e-9 do
				w.now += 0.1
				w.svc.step(w.now)
			end
			w.now = t
			w.svc.step(t)
		end
		return w
	end
	local function ring(w, p, t)
		return (w.svc.progress(p, t))
	end

	-- One reviver: 2.5 s, once; the spot goes first.
	local w = world()
	w.fall(w.ana)
	check(w.svc.holdBegan(w.ana, w.ben) == true, "A living teammate in reach can start a hold")
	w.at(2.4)
	check(#w.revived == 0 and near(ring(w, w.ana), 0.96), "2.4 s: 96%, not yet")
	local s = w.svc.spots[w.ana]
	check(s.shownReviver == w.ben and near(s.shownRate, 0.4) and s.shownCount == 1, "The spot shows who holds and how fast it fills")
	check(w.guards[w.ben] == true, "Ben's hold counts: he is guarded")
	w.at(2.5)
	check(#w.revived == 1 and w.revived[1].p == w.ana and w.revived[1].q == w.ben, "2.5 s revives Ana, credited to Ben (was 5 s)")
	check(w.svc.spots[w.ana] == nil and s.gone, "The revived player's spot goes")
	check(w.guards[w.ben] == nil, "The guard ends with the revive")
	w.at(4)
	check(#w.revived == 1, "Never twice for one down")
	check(w.svc.holdBegan(w.ana, w.ben) == false, "No spot left to hold")

	-- Unlimited and free: the same player can go down and be revived again, by anyone.
	w.fall(w.ana)
	w.now = 10
	w.svc.holdBegan(w.ana, w.cal)
	w.at(12.5)
	check(#w.revived == 2 and w.revived[2].q == w.cal, "A second down is revived again, by Cal this time")

	-- More revivers are faster: two x1.5, three x2.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.svc.holdBegan(w.ana, w.cal)
	w.at(1.6)
	check(#w.revived == 0, "Two holding: not done at 1.6 s")
	w.at(1.7)
	check(#w.revived == 1 and (w.revived[1].q == w.ben or w.revived[1].q == w.cal), "Two holding: up by 1.7 s (1.67 s), one revive")
	w = world()
	w.fall(w.ana)
	for _, q in { w.ben, w.cal, w.dan } do
		w.svc.holdBegan(w.ana, q)
	end
	check(w.svc.spots[w.ana].shownCount == 3 and near(w.svc.spots[w.ana].shownRate, 0.8), "Three holding: x2")
	w.at(1.2)
	check(#w.revived == 0, "Three holding: not at 1.2 s")
	w.at(1.3)
	check(#w.revived == 1, "Three holding: up by 1.3 s (1.25 s), one revive")
	-- A helper joining part way: each stretch fills at its own speed.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.at(1) -- 40%
	w.svc.holdBegan(w.ana, w.cal)
	w.at(2)
	check(#w.revived == 1 and near(w.revived[1].at, 2), "Ben 1 s alone (40%) + 1 s with Cal (60%): up at 2 s")

	-- Letting go drains slowly instead of resetting.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.at(1.5) -- 60%
	w.svc.holdEnded(w.ana, w.ben)
	check(w.guards[w.ben] == nil, "Let go: the guard is off at once")
	check(near(w.svc.spots[w.ana].shownRate, -0.2), "The ring shows it draining")
	w.at(2.5)
	check(near(ring(w, w.ana), 0.4) and #w.revived == 0, "1 s later: 40%, not 0")
	w.svc.holdBegan(w.ana, w.ben)
	w.at(3.9)
	check(#w.revived == 0, "The rest takes 1.5 s (60% at 0.4 a second)")
	w.at(4)
	check(#w.revived == 1 and near(w.revived[1].at, 4), "Up at 4.0 s (the old rule: 2.5 s after the new press)")
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.at(1)
	w.svc.holdEnded(w.ana, w.ben)
	w.at(10)
	check(ring(w, w.ana) == 0 and w.svc.spots[w.ana].shownRate == 0, "Left alone it drains to empty and stops there")
	check(#w.revived == 0, "and nobody is revived")
	-- Pressing again while holding changes nothing.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.at(1)
	check(w.svc.holdBegan(w.ana, w.ben) == true and near(ring(w, w.ana, 1), 0.4), "A second press neither restarts nor speeds the ring")
	local _, _, holders = w.svc.progress(w.ana, 1)
	check(holders == 1, "One reviver pressing twice is still one reviver")

	-- Reach (where their screen has them): 20 studs keeps a hold; walking out stops it.
	w = world()
	w.fall(w.ana)
	w.pos[w.ben] = Vector3.new(REACH + 1, 0, 0)
	check(w.svc.holdBegan(w.ana, w.ben) == false, "Out of reach can't start a hold (an instant exploit press)")
	check(w.guards[w.ben] == nil, "and isn't guarded: standing near a body protects nobody")
	w.pos[w.ben] = Vector3.new(REACH - 0.5, 0, 0)
	check(w.svc.holdBegan(w.ana, w.ben) == true, "19.5 studs away can (was 14)")
	w.at(1)
	w.pos[w.ben] = Vector3.new(REACH + 0.5, 0, 0)
	w.at(1.1)
	check(w.guards[w.ben] == nil and w.svc.spots[w.ana].holds[w.ben] == nil, "Walking out of reach drops the hold and the guard")
	check(near(ring(w, w.ana, 1.1), 0.44), "The ring keeps what it had (the last 0.1 s counted)")
	w.pos[w.ben] = Vector3.zero
	w.at(3)
	check(#w.revived == 0, "Coming back without pressing again doesn't resume")

	-- The reviver dying or going down stops their part; taking damage doesn't.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.at(1) -- Ben is hit here: alive, still holding
	w.at(2)
	check(near(ring(w, w.ana), 0.8) and w.guards[w.ben] == true, "Damage alone keeps the hold")
	w.alive[w.ben] = false
	w.at(2.1)
	check(w.svc.spots[w.ana].holds[w.ben] == nil and w.guards[w.ben] == nil, "The reviver dying drops the hold")
	w.at(6)
	check(#w.revived == 0, "and nobody is revived")
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.at(1)
	w.fall(w.ben)
	w.at(1.1)
	check(w.svc.spots[w.ana].holds[w.ben] == nil and w.svc.spots[w.ben] ~= nil, "A reviver who goes down loses the hold and gets a spot")

	-- Who can't revive: the downed player themselves, non-members, other downed players.
	w = world()
	w.fall(w.ana)
	w.fall(w.cal)
	w.member[w.dan] = false
	check(w.svc.holdBegan(w.ana, w.ana) == false, "Not yourself")
	check(w.svc.holdBegan(w.ana, w.cal) == false, "Not another downed player")
	check(w.svc.holdBegan(w.ana, w.dan) == false, "Not someone outside the run")
	check(w.svc.holdBegan(w.ben, w.cal) == false, "No spot for someone who isn't down")
	check(next(w.guards) == nil, "Nobody is guarded without a counted hold")

	-- One reviver holding two rings (they overlap): guarded once, off only when both stop.
	w = world()
	w.fall(w.ana)
	w.fall(w.cal, Vector3.new(6, 0, 0))
	w.svc.holdBegan(w.ana, w.ben)
	w.svc.holdBegan(w.cal, w.ben)
	local writes = w.guardWrites
	w.svc.holdEnded(w.ana, w.ben)
	check(w.guards[w.ben] == true and w.guardWrites == writes, "Still holding Cal's ring: still guarded, no extra write")
	w.svc.holdEnded(w.cal, w.ben)
	check(w.guards[w.ben] == nil, "Both let go: unguarded")

	-- The pause freeze: no presses while frozen; a freeze drops holds but keeps the ring.
	w = world()
	w.fall(w.ana)
	w.frozen = true
	check(w.svc.holdBegan(w.ana, w.ben) == false, "No hold while frozen")
	w.frozen = false
	w.svc.holdBegan(w.ana, w.ben)
	w.at(1)
	w.frozen = true
	w.at(1.1)
	check(w.svc.spots[w.ana].holds[w.ben] == nil and w.guards[w.ben] == nil, "A freeze drops the hold and the guard")
	local frozenAt = ring(w, w.ana, 1.1)
	w.at(20)
	check(near(ring(w, w.ana, 20), frozenAt) and w.svc.spots[w.ana].shownRate == 0, "Frozen, the ring neither fills nor drains")
	w.frozen = false
	w.at(21)
	check(#w.revived == 0 and near(ring(w, w.ana), frozenAt - 0.2), "After it, it drains until someone presses again")

	-- The spot goes whenever the player stops being down some other way.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.at(1)
	w.down[w.ana] = nil -- a paid revive, the wave's end, Leave Run or the last stand ending
	w.at(1.1)
	check(w.svc.spots[w.ana] == nil and w.destroyed == 1, "Not down any more: the spot goes on the next step")
	check(w.guards[w.ben] == nil, "and its reviver's guard with it")
	w.at(4)
	check(#w.revived == 0, "and no teammate revive follows")
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.svc.clear(w.ana)
	check(w.svc.spots[w.ana] == nil and w.guards[w.ben] == nil, "clear removes the spot and its guards at once (clearDown, PlayerRemoving)")
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.now = 0.5
	w.svc.holdBegan(w.ana, w.cal)
	w.now = 1
	w.svc.clear(w.ben) -- Ben disconnects
	local held, who = w.svc.progress(w.ana, 1)
	check(who == w.cal and near(held, 0.2 + 0.3) and w.guards[w.ben] == nil, "A reviver leaving drops only their hold, at once")

	-- A new down replaces the old spot, and the old prompt's events no longer count.
	w = world()
	w.fall(w.ana)
	local old = w.made[1]
	w.fall(w.ana, Vector3.new(50, 0, 0))
	check(w.destroyed == 1 and #w.made == 2, "The old spot is destroyed")
	w.pos[w.ben] = Vector3.new(50, 0, 0)
	old.began(w.ben)
	check(w.svc.spots[w.ana].holds[w.ben] == nil, "A late event from the old prompt is ignored")
	w.made[2].began(w.ben)
	check(ring(w, w.ana, 0) == 0 and w.svc.spots[w.ana].holds[w.ben] ~= nil, "The new prompt counts")
	w.pos[w.ben] = Vector3.zero
	w.at(1)
	check(w.svc.spots[w.ana].holds[w.ben] == nil, "Reach is measured from the new spot")

	-- Last stand: everyone down, nobody can help.
	w = world()
	for _, p in { w.ana, w.ben, w.cal, w.dan } do
		w.fall(p)
	end
	local any = false
	for _, p in { w.ana, w.ben, w.cal, w.dan } do
		for _, q in { w.ana, w.ben, w.cal, w.dan } do
			any = any or w.svc.holdBegan(p, q)
		end
	end
	check(not any, "Everyone down: no hold is possible (the last stand and paid revive are unchanged)")

	-- The revive shove (shovePlan / shoveEase), with MonetizationConfig's 14 / 13 / 4.
	if R.shovePlan then
		local function near(a, b)
			return math.abs(a - b) < 1e-6
		end
		local spot = Vector3.new(100, 3, -40)
		local mobs = {
			{ name = "close", position = spot + Vector3.new(2, 0, 0) },
			{ name = "mid", position = spot + Vector3.new(0, -2, 10) }, -- lower ground: flat distance counts
			{ name = "edge", position = spot + Vector3.new(-13.5, 0, 0) },
			{ name = "far", position = spot + Vector3.new(15, 0, 0) },
			{ name = "onTop1", position = spot },
			{ name = "onTop2", position = spot + Vector3.new(0, 1, 0) },
		}
		local plans = R.shovePlan(spot, mobs, 14, 13, 4)
		local by = {}
		for _, plan in plans do
			by[plan.mob.name] = plan
		end
		check(#plans == 5 and by.far == nil, "Only enemies within 14 studs (flat) are shoved")
		check(near(by.close.distance, 11) and near(by.close.direction.X, 1), "2 studs off: shoved 11 straight out, to 13")
		check(near(by.mid.distance, 4) and near(by.mid.direction.Z, 1) and near(by.mid.direction.Y, 0), "10 off: the 4-stud minimum, flat, to 14")
		check(near(by.edge.distance, 4) and near(by.edge.direction.X, -1), "13.5 off: still the minimum, away from the spot")
		for _, plan in plans do
			local d = plan.direction
			local landed = Vector3.new(plan.mob.position.X - spot.X, 0, plan.mob.position.Z - spot.Z) + d * plan.distance
			check(near(d.Magnitude, 1) and d.Y == 0, plan.mob.name .. ": a flat unit direction")
			check(landed.Magnitude >= 13 - 1e-6 and landed.Magnitude <= 18, plan.mob.name .. ": lands 13-18 studs from the spot")
		end
		check(near(by.onTop1.distance, 13) and by.onTop1.direction:Dot(by.onTop2.direction) < 0.99, "A pile on the spot fans out, not all one way")
		check(#R.shovePlan(spot, {}, 14, 13, 4) == 0, "Nobody near: no shove")
		check(R.shoveEase(0) == 0 and R.shoveEase(1) == 1 and R.shoveEase(2) == 1 and R.shoveEase(-1) == 0, "The shove starts at 0 and ends at its full distance")
		check(R.shoveEase(1 / 3) > 0.7 and R.shoveEase(0.5) > R.shoveEase(1 / 3), "Most of the shove lands at once (an ease-out), and it only moves outward")
	end
	return checks
end
