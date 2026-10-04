-- RunPause checks (plans/2026-10-02-L-pause.md). Run in Studio Edit on a fresh copy:
-- `RunPauseTests(RunPause)` returns the number of checks. Players are plain tables here.
return function(R)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local a, b, c = { name = "a" }, { name = "b" }, { name = "c" }

	-- Solo: pausing freezes, resuming unfreezes, and the frozen time is reported.
	local st = R.new()
	check(R.evaluate(st, { a }) == false, "Nobody paused: not frozen")
	check(R.set(st, a, true) == true and R.set(st, a, true) == false, "Pausing twice changes nothing")
	local frozen, count, n = R.evaluate(st, { a })
	check(frozen and count == 1 and n == 1, "Solo pause freezes")
	check(R.step(st, true, 100) == "freeze" and R.step(st, true, 101) == nil, "Freeze happens once")
	R.set(st, a, false)
	check(R.evaluate(st, { a }) == false, "Solo resume unfreezes")
	local change, by = R.step(st, false, 112.5)
	check(change == "unfreeze" and by == 12.5, "Unfreeze reports the frozen time")
	check(R.step(st, false, 113) == nil, "Unfreeze happens once")

	-- Party: frozen only when every living member has paused.
	st = R.new()
	R.set(st, a, true)
	frozen, count, n = R.evaluate(st, { a, b, c })
	check(not frozen and count == 1 and n == 3, "1 of 3 paused: keeps going")
	R.set(st, b, true)
	check(R.evaluate(st, { a, b, c }) == false, "2 of 3 paused: keeps going")
	R.set(st, c, true)
	check(R.evaluate(st, { a, b, c }) == true, "3 of 3 paused: frozen")
	R.set(st, b, false)
	frozen, count = R.evaluate(st, { a, b, c })
	check(not frozen and count == 2, "One resume unfreezes for everyone; the others stay paused")

	-- Downed players don't count; a member leaving re-checks.
	st = R.new()
	R.set(st, a, true)
	check(R.evaluate(st, { a }) == true, "b downed (not living): a alone pausing freezes")
	R.set(st, b, true)
	R.forget(st, b)
	check(R.isPaused(st, b) == false, "Leaving forgets the pause")
	check(R.isPaused(st, a) == true, "Forgetting b keeps a paused")
	check(R.evaluate(st, { a, c }) == false, "c still playing: not frozen")
	check(R.evaluate(st, {}) == false, "Nobody alive: never frozen (the last stand holds the run)")

	-- Clear: a new run starts unpaused.
	R.step(st, true, 5)
	R.clear(st)
	check(not st.frozen and next(st.paused) == nil, "Clear resets everything")
	check(R.set(st, a, "yes") == false and R.isPaused(st, a) == false, "Only true pauses")

	-- Requests (2026-10-03): a resume is never dropped, so P tapped twice can't leave the run frozen.
	st = R.new()
	check(R.allow(st, a, true, 10) == true, "First pause goes through")
	check(R.allow(st, a, false, 10.05) == true, "A resume right after it still goes through")
	check(R.allow(st, a, true, 10.1) == false, "A second pause within RATE is dropped")
	check(R.allow(st, a, true, 10 + R.RATE) == true, "A pause after RATE goes through")
	check(R.allow(st, b, true, 10.1) == true, "The limit is per player")
	R.forget(st, a)
	check(R.allow(st, a, true, 10.3) == true, "Leaving forgets the limit too")

	-- Leaving while paused: a solo run unfreezes at once, a party's stays as it was.
	st = R.new()
	R.set(st, a, true)
	R.step(st, R.evaluate(st, { a }), 50)
	R.forget(st, a)
	check(R.evaluate(st, {}) == false and R.step(st, false, 53) == "unfreeze", "Solo leave while frozen unfreezes the run")
	st = R.new()
	R.set(st, a, true)
	R.set(st, b, true)
	R.step(st, R.evaluate(st, { a, b }), 50)
	R.forget(st, a)
	check(R.evaluate(st, { b }) == true and R.step(st, true, 51) == nil, "b still in the menu: stays frozen after a leaves")

	-- Leave Run rules: any time while standing or down (mid-wave too); with the party, leader only.
	check(R.canLeave({ member = true, alive = true }) == true, "Alive member may leave (shop or mid-wave)")
	check(R.canLeave({ member = true, down = true }) == true, "Downed member may leave")
	local ok, why = R.canLeave({ member = false, alive = true })
	check(ok == false and type(why) == "string", "Not in a run: refused with a reason")
	ok, why = R.canLeave({ member = true, alive = false })
	check(ok == false and type(why) == "string", "Respawning: refused with a reason")
	ok = R.canLeave({ member = true, alive = true, withParty = true, leader = false })
	check(ok == false, "Leave with party: not the leader is refused")
	check(R.canLeave({ member = true, alive = true, withParty = true, leader = true }) == true, "Leave with party: the leader may")
	return checks
end
