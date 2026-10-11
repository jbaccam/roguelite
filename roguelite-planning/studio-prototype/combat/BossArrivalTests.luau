-- Boss arrival i-frames (CharacterStats.BossArrival / bossGraceUntil; CharacterService.bossArrived
-- stores the result in RogueliteCombat.BossGraceUntil and contact blocks every hit before it).
-- `BossArrivalTests(CharacterStats)` returns the number of checks; run_survival_tests.py runs it
-- in the Luau CLI on the real CharacterStats.
return function(Stats)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local function near(a, b)
		return math.abs(a - b) < 1e-6
	end
	local I = Stats.BossArrival.IFrames
	check(I >= 1 and I <= 2, "A second or two of i-frames (friends' ask)")
	check(I > Stats.Dash.IFrames, "Longer than a dash's i-frames")
	local grace = Stats.bossGraceUntil
	-- An admin boss with no entrance at 100 s: hits are blocked until 101.5 s.
	check(near(grace(100, nil, nil), 100 + I), "No entrance: the window starts at the spawn")
	check(near(grace(100, 50, nil), 100 + I), "An old, finished cinematic doesn't move it")
	-- The Hammer Brute's sky drop (BossService.INTRO 1.2 + 0.65 + 3.6 = 5.45 s) from 100 s.
	check(near(grace(100, 105.45, nil), 105.45 + I), "An entrance: the window starts when the hold lets go")
	-- A round 10 leader inside an event intro that ends at 112 s.
	check(near(grace(103, 112, nil), 112 + I), "A round 10 leader: after the event's cinematic")
	-- A second boss (an extra Warden) never shortens the first one's window, only extends it.
	check(near(grace(100.5, nil, 101.5), 100.5 + I), "A second boss in the window extends it")
	check(near(grace(100, nil, 120), 120), "A later window already set is kept")
	check(near(grace(100, "x", "y"), 100 + I), "Bad stored values fall back to the spawn time")
	-- What contact does with the stored time (CharacterService.contact): blocked strictly before it.
	local function blocked(now, untilTime)
		return type(untilTime) == "number" and now < untilTime
	end
	local stored = grace(100, 105.45, nil)
	check(blocked(105.0, stored) and blocked(106.9, stored), "Hits during the entrance and 1.45 s after it miss")
	check(not blocked(stored, stored) and not blocked(107.5, stored), "Hits land again once the window ends")
	check(not blocked(0, nil), "No boss yet: nothing is blocked")
	return checks
end
