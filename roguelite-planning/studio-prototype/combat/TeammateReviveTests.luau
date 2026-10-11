-- TeammateRevive checks (hold timing, validation, one revive per down). Run in Studio Edit on a fresh
-- copy: `TeammateReviveTests(TeammateRevive)` returns the number of checks. Players are plain tables,
-- the clock is a number the test moves, and the view only records what it would have drawn, so no
-- instance is made.
return function(R)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local H, GRACE, REACH = R.HOLD_SECONDS, R.RELEASE_GRACE, R.RANGE + R.SLACK

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
		function view.publish(s, reviver, began)
			s.shownReviver, s.shownBegan = reviver, began
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
		function w.at(t)
			w.now = t
			w.svc.step(t)
		end
		return w
	end

	-- A full 5 s hold revives once, at 5.0 and not before; the spot goes first.
	local w = world()
	w.fall(w.ana)
	check(w.svc.holdBegan(w.ana, w.ben) == true, "A living teammate in reach can start a hold")
	w.at(4.9)
	check(#w.revived == 0, "4.9 s is not enough")
	local s = w.svc.spots[w.ana]
	check(s.shownReviver == w.ben and s.shownBegan == 0, "The spot shows who holds and since when (server time)")
	w.at(5)
	check(#w.revived == 1 and w.revived[1].p == w.ana and w.revived[1].q == w.ben, "5.0 s revives Ana, credited to Ben")
	check(w.svc.spots[w.ana] == nil and s.gone, "The revived player's spot goes")
	w.at(6)
	check(#w.revived == 1, "Never twice for one down")
	check(w.svc.holdBegan(w.ana, w.ben) == false, "No spot left to hold")

	-- Unlimited and free: the same player can go down and be revived again, by anyone.
	w.fall(w.ana)
	w.now = 10
	w.svc.holdBegan(w.ana, w.cal)
	w.at(15)
	check(#w.revived == 2 and w.revived[2].q == w.cal, "A second down is revived again, by Cal this time")

	-- Letting go resets; the progress starts over on the next press.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.now = 3
	w.svc.holdEnded(w.ana, w.ben)
	check(w.svc.progress(w.ana, 3) == 0 and w.svc.spots[w.ana].shownBegan == nil, "Letting go at 3 s resets the ring")
	w.at(5)
	check(#w.revived == 0, "No revive after a let-go")
	w.now = 6
	w.svc.holdBegan(w.ana, w.ben)
	w.at(10.9)
	check(#w.revived == 0, "A new press starts from zero (4.9 s)")
	w.at(11)
	check(#w.revived == 1, "and revives after its own 5 s")

	-- The release grace: let go in the last half second still counts; earlier does not.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.now = H - GRACE + 0.2
	w.svc.holdEnded(w.ana, w.ben)
	check(w.svc.spots[w.ana].holds[w.ben].released == true, "A release at 4.7 s is kept (the client's 5 s ended first)")
	w.at(H - 0.01)
	check(#w.revived == 0, "Still not before 5.0 s on the server")
	w.at(H)
	check(#w.revived == 1, "Revived at 5.0 s")
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.now = H - GRACE - 0.1
	w.svc.holdEnded(w.ana, w.ben)
	w.at(H)
	check(#w.revived == 0, "A release at 4.4 s resets")
	-- A kept release still needs the reviver alive and in reach until 5.0 s.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.now = 4.8
	w.svc.holdEnded(w.ana, w.ben)
	w.alive[w.ben] = false
	w.at(H)
	check(#w.revived == 0, "A kept release whose reviver died before 5.0 s doesn't revive")

	-- Reach: within the prompt plus slack keeps the hold; walking out resets it.
	w = world()
	w.fall(w.ana)
	w.pos[w.ben] = Vector3.new(REACH + 1, 0, 0)
	check(w.svc.holdBegan(w.ana, w.ben) == false, "Out of reach can't start a hold (an instant exploit press)")
	w.pos[w.ben] = Vector3.new(REACH - 0.5, 0, 0)
	check(w.svc.holdBegan(w.ana, w.ben) == true, "Just inside the reach (prompt + slack) can")
	w.at(2)
	w.pos[w.ben] = Vector3.new(REACH + 0.5, 0, 0)
	w.at(2.1)
	check(w.svc.progress(w.ana) == 0, "Walking out of reach resets")
	w.pos[w.ben] = Vector3.zero
	w.at(5)
	check(#w.revived == 0, "Coming back without pressing again doesn't resume")

	-- The reviver dying cancels; taking damage (still alive) doesn't.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.at(2) -- Ben is hit here: alive, still holding
	w.at(4)
	check(w.svc.progress(w.ana, 4) == 4, "Damage alone keeps the hold")
	w.alive[w.ben] = false
	w.at(4.5)
	check(w.svc.progress(w.ana) == 0, "The reviver dying resets")
	w.at(6)
	check(#w.revived == 0, "and nobody is revived")
	-- The reviver going down mid-hold (their own spot appears) cancels too.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.now = 3
	w.fall(w.ben)
	w.at(3.1)
	check(w.svc.progress(w.ana) == 0 and w.svc.spots[w.ben] ~= nil, "A reviver who goes down loses the hold and gets a spot")

	-- Who can't revive: the downed player themselves, non-members, other downed players.
	w = world()
	w.fall(w.ana)
	w.fall(w.cal)
	w.member[w.dan] = false
	check(w.svc.holdBegan(w.ana, w.ana) == false, "Not yourself")
	check(w.svc.holdBegan(w.ana, w.cal) == false, "Not another downed player")
	check(w.svc.holdBegan(w.ana, w.dan) == false, "Not someone outside the run")
	check(w.svc.holdBegan(w.ben, w.cal) == false, "No spot for someone who isn't down")

	-- Several holders: never faster, never summed, one revive.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.now = 2
	w.svc.holdBegan(w.ana, w.cal)
	w.now = 3
	w.svc.holdEnded(w.ana, w.ben)
	local held, who = w.svc.progress(w.ana, 3)
	check(held == 1 and who == w.cal, "Ben lets go at 3 s: the ring drops to Cal's 1 s")
	w.at(6.9)
	check(#w.revived == 0, "Two holders aren't faster than one")
	w.at(7)
	check(#w.revived == 1 and w.revived[1].q == w.cal, "Cal's own 5 s revives")
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.svc.holdBegan(w.ana, w.cal)
	w.svc.holdBegan(w.ana, w.dan)
	w.at(2.5)
	w.at(4.9)
	check(#w.revived == 0 and w.svc.progress(w.ana, 4.9) == 4.9, "Three holds from 0 s: 4.9 s of progress, not 14.7")
	w.at(5)
	check(#w.revived == 1, "Three full holds at once: one revive")
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.now = 4
	check(w.svc.holdBegan(w.ana, w.ben) == true and w.svc.progress(w.ana, 4) == 4, "Pressing again doesn't restart the hold")
	w.svc.holdEnded(w.ana, w.ben)
	w.svc.holdBegan(w.ana, w.ben)
	check(w.svc.progress(w.ana, 4) == 0, "Let go and press again: from zero")

	-- The pause freeze: no presses while frozen, and a freeze resets holds.
	w = world()
	w.fall(w.ana)
	w.frozen = true
	check(w.svc.holdBegan(w.ana, w.ben) == false, "No hold while frozen")
	w.frozen = false
	w.svc.holdBegan(w.ana, w.ben)
	w.at(3)
	w.frozen = true
	w.at(3.1)
	check(w.svc.progress(w.ana) == 0 and w.svc.spots[w.ana].shownBegan == nil, "A freeze resets the hold")
	w.frozen = false
	w.at(20)
	check(#w.revived == 0, "and it doesn't resume on its own")

	-- The spot goes whenever the player stops being down some other way.
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.at(4)
	w.down[w.ana] = nil -- a paid revive, the wave's end, Leave Run or the last stand ending
	w.at(4.1)
	check(w.svc.spots[w.ana] == nil and w.destroyed == 1, "Not down any more: the spot goes on the next step")
	w.at(6)
	check(#w.revived == 0, "and no teammate revive follows")
	w = world()
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.svc.clear(w.ana)
	check(w.svc.spots[w.ana] == nil, "clear removes the spot at once (clearDown, PlayerRemoving)")
	w.fall(w.ana)
	w.svc.holdBegan(w.ana, w.ben)
	w.now = 0.5
	w.svc.holdBegan(w.ana, w.cal)
	w.now = 1
	w.svc.clear(w.ben) -- Ben disconnects
	held, who = w.svc.progress(w.ana, 1)
	check(who == w.cal and held == 0.5, "A reviver leaving drops only their hold, at once")

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
	check(w.svc.progress(w.ana, 0) == 0 and w.svc.spots[w.ana].holds[w.ben] ~= nil, "The new prompt counts")
	w.pos[w.ben] = Vector3.zero
	w.at(1)
	check(w.svc.progress(w.ana) == 0, "Reach is measured from the new spot")

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
