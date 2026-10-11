-- VfxKit.animate lifetime guarantees (2026-10-10, wave-50 "frozen swing effects" report).
-- newKit() returns a fresh VfxKit plus a fake clock/RenderStepped (run_vfxkit_tests.py).
-- Every effect must be cleaned up exactly once, however its callbacks nest or fail.
return function(newKit)
	local checks = 0
	local function check(ok, message)
		checks += 1
		assert(ok, message)
	end
	local function tracker()
		local calls = {}
		return calls, function(name)
			return function()
				calls[name] = (calls[name] or 0) + 1
			end
		end
	end
	local function run(env, seconds)
		for _ = 1, math.ceil(seconds / 0.05) do
			env.frame(0.05)
		end
	end

	-- 1. A finishing update spawns a child whose budget evicts an OLDER effect (lower index).
	-- The old loop then removed the wrong index: the effect after it was dropped uncleaned.
	do
		local K, env = newKit()
		local calls, done = tracker()
		K.animate(5, function() end, done("old"), "child", 1)
		K.animate(0.1, function(t)
			if t >= 1 then
				K.animate(0.1, function() end, done("child"), "child", 1)
			end
		end, done("parent"), "parent", 8)
		K.animate(0.4, function() end, done("victim"), "swing", 8)
		run(env, 1)
		for _, name in { "old", "parent", "child", "victim" } do
			check(calls[name] == 1, ("%s cleaned %s times, expected once"):format(name, tostring(calls[name])))
		end
		check(not env.connected(), "Scheduler stops once every effect is gone")
	end

	-- 2. A finishing update evicts ITSELF (same category, it is the oldest).
	do
		local K, env = newKit()
		local calls, done = tracker()
		K.animate(0.1, function(t)
			if t >= 1 then
				K.animate(0.1, function() end, done("child"), "same", 1)
			end
		end, done("parent"), "same", 1)
		K.animate(0.4, function() end, done("victim"), "swing", 8)
		run(env, 1)
		for _, name in { "parent", "child", "victim" } do
			check(calls[name] == 1, ("self-evict: %s cleaned %s times"):format(name, tostring(calls[name])))
		end
	end

	-- 3. An evicted effect's cleanup throws: the new effect must still be registered and cleaned.
	do
		local K, env = newKit()
		local calls, done = tracker()
		K.animate(5, function() end, function()
			error("boom")
		end, "bad", 1)
		K.animate(0.2, function() end, done("new"), "bad", 1)
		run(env, 1)
		check(calls.new == 1, "Effect added after a failing eviction is still cleaned")
		check(#env.warnings == 1, "A failing cleanup warns once")
	end

	-- 4. An update that throws retires its effect and still runs the cleanup.
	do
		local K, env = newKit()
		local calls, done = tracker()
		K.animate(5, function()
			error("bad update")
		end, done("thrower"), "x", 4)
		env.frame(0.05)
		check(calls.thrower == 1, "Throwing update still cleans up")
	end

	-- 5. Bad or huge durations are capped by MaxLifetime.
	do
		local K, env = newKit()
		local calls, done = tracker()
		K.animate(nil, function() end, done("nil"))
		K.animate(0 / 0, function() end, done("nan"))
		K.animate(1e9, function() end, done("huge"))
		K.animate(math.huge, function() end, done("inf"))
		run(env, K.MaxLifetime + 1)
		for _, name in { "nil", "nan", "huge", "inf" } do
			check(calls[name] == 1, name .. " duration is retired by MaxLifetime")
		end
	end

	-- 6. Cleanups that spawn follow-ups (rain splits, wisp landings) and many nested spawns keep
	-- the category budgets exact afterwards.
	do
		local K, env = newKit()
		local calls, done = tracker()
		local spawned = 0
		for i = 1, 30 do
			K.animate(0.05 + (i % 5) * 0.05, function(t)
				if t >= 1 or math.random() < 0.3 then
					spawned += 1
					K.animate(0.1, function() end, done("spawn" .. spawned), "spawn", 3)
				end
			end, function()
				done("parent" .. i)()
				K.animate(0.1, function() end, done("follow" .. i), "follow", 2)
			end, "parent", 6)
		end
		run(env, 2)
		for name, count in calls do
			check(count == 1, ("%s cleaned %d times"):format(name, count))
		end
		check(not env.connected(), "Nested spawns all retire")
		local fresh, f = tracker()
		for i = 1, 3 do
			K.animate(1, function() end, f("z" .. i), "z", 3)
		end
		check(next(fresh) == nil, "Budget counts stayed exact: three fit in a budget of three")
		K.animate(1, function() end, f("z4"), "z", 3)
		check(fresh.z1 == 1 and fresh.z2 == nil, "The fourth evicts only the oldest")
		run(env, 2)
	end

	-- 7. The cleanup order modules follow (2026-10-10, check_vfx_cleanup_order.py): own parts are
	-- destroyed first, then follow-ups start. A follow-up that throws after starting another effect
	-- leaves nothing behind: the parts are gone, the started follow-up still retires once, and the
	-- scheduler keeps running later effects.
	do
		local K, env = newKit()
		local calls, done = tracker()
		local parts = { alive = 3 }
		K.animate(0.1, function() end, function()
			parts.alive = 0 -- own parts first
			K.animate(0.1, function() end, done("landing"), "landing", 4)
			error("follow-up failed")
		end, "slash", 4)
		K.animate(0.5, function() end, done("later"), "swing", 8)
		run(env, 1)
		check(parts.alive == 0, "Own parts are destroyed even though the follow-up threw")
		check(calls.landing == 1, "The follow-up started before the throw still retires once")
		check(calls.later == 1, "Later effects still retire")
		check(#env.warnings == 1 and not env.connected(), "One warning, and the scheduler stops when idle")
	end
	return { checks = checks }
end
