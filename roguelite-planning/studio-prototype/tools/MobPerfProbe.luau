--!nonstrict
-- Mob performance probe (launch audit P5, P6, P9, P10). Read-only: it only watches. Paste this
-- whole file as the code of an execute_luau call during Play, with SECONDS and LABEL set below.
--
-- In the Server datamodel it samples, once a frame for SECONDS:
--   Stats.HeartbeatTimeMs, PhysicsStepTimeMs, DataSendKbps, PhysicsSendKbps, InstanceCount
--   (plus primitives, moving primitives and contacts), the server frame time (Heartbeat dt: worst
--   frame and how many went over 16.7 ms and 33.3 ms), the enemy count, and the enemy scripts'
--   own time where the code publishes it: RogueliteZombieChase's EnemyMs / EnemyPeakMs (new code,
--   the scheduler: chase and enemy attacks). The old code publishes nothing; take its number from
--   the Script Profiler (HOW-TO, step 3), which works on any code.
-- In the Client datamodel it samples RenderStepped for SECONDS: average FPS and the 1% low (the
-- FPS of the slowest 1% of frames).
--
-- The first call starts the sampler and returns at once; call again after SECONDS to get the
-- report (the state lives in _G.MobPerfProbe). If the second call says "started" again, the
-- plugin VM didn't keep _G: set BLOCK = true and SECONDS = 25, and the call waits and reports.
--
-- HOW-TO (one measurement session; the user starts Play, Claude only reads):
--  1. Studio: Play (solo). Start a Pine Valley run and play to wave 8 or later (tanks appear).
--  2. Admin panel (F2) > Keep N alive: N = 65, ids "regular-zombie,baby-zombie,tank-zombie,
--     spitter-zombie". Wait until the count holds, then kite the crowd in circles for the whole
--     sample (keep fighting: the swing, contact and attack code must run).
--  3. Enemy-script time on the old code: Developer Console (F9) > Script Profiler, Server,
--     1000 Hz, Start; stop after 60 s. Note the total ms of RogueliteZombieChase (+ EnemyAttacks,
--     ZombieAttacks, which it calls), CharacterService and RogueliteCombat; ms per frame = total
--     ms / (60 s x 60 frames). (Studio's own View > Script Profiler, set to Server, works too.)
--  4. At the same time Claude starts this probe on the Server and on the Client (LABEL "65 mobs"),
--     and reads both after 60 s. If the wave ends during a sample (the shop opens and the enemies
--     go), that sample doesn't count: redo it in the next wave.
--  5. Repeat 2-4 with N = 50 and N = 100.
--  6. After the push: the same steps on the new code. EnemyMs then also comes from this probe.
-- Client FPS by hand instead: Shift+F5 shows FPS; the MicroProfiler (Ctrl+F6) shows frame times.
-- Studio solo puts the server and the client on one PC: treat the numbers as rough, and network
-- numbers (DataSendKbps) as one player's. Four real players need a live test.
local SECONDS = 60
local LABEL = "65 mobs"
local BLOCK = false

local RunService = game:GetService("RunService")
local Stats = game:GetService("Stats")

local function summary(list)
	local n = #list
	if n == 0 then
		return "n/a"
	end
	local sorted = table.clone(list)
	table.sort(sorted)
	local sum = 0
	for _, v in sorted do
		sum += v
	end
	local function at(q)
		return sorted[math.clamp(math.ceil(q * n), 1, n)]
	end
	return string.format("avg %.2f  p50 %.2f  p95 %.2f  max %.2f", sum / n, at(0.5), at(0.95), sorted[n])
end

local function serverProbe()
	local s = { started = os.clock(), dts = {}, samples = {}, enemies = {} }
	local names = { "HeartbeatTimeMs", "PhysicsStepTimeMs", "DataSendKbps", "PhysicsSendKbps", "InstanceCount", "PrimitivesCount", "MovingPrimitivesCount", "ContactsCount" }
	for _, name in names do
		s.samples[name] = {}
	end
	s.enemyMs, s.enemyPeakMs = {}, {}
	local chase = game:GetService("ServerScriptService"):FindFirstChild("RogueliteZombieChase")
	local lastRead = os.clock()
	s.connection = RunService.Heartbeat:Connect(function(dt)
		table.insert(s.dts, dt * 1000)
		for _, name in names do
			local ok, value = pcall(function()
				return Stats[name]
			end)
			if ok and type(value) == "number" then
				table.insert(s.samples[name], value)
			end
		end
		local folder = workspace:FindFirstChild("RogueliteEnemies")
		table.insert(s.enemies, folder and #folder:GetChildren() or 0)
		-- The new code's meter is a one-second mean, rewritten once a second: read it once a second.
		if chase and os.clock() - lastRead >= 1 then
			lastRead = os.clock()
			local ms = chase:GetAttribute("EnemyMs")
			if ms ~= nil then
				table.insert(s.enemyMs, ms)
				table.insert(s.enemyPeakMs, chase:GetAttribute("EnemyPeakMs") or 0)
			end
		end
		if os.clock() - s.started >= SECONDS then
			s.connection:Disconnect()
			s.done = true
		end
	end)
	function s.report()
		local over16, over33 = 0, 0
		for _, ms in s.dts do
			if ms > 1000 / 60 + 1 then over16 += 1 end
			if ms > 1000 / 30 + 1 then over33 += 1 end
		end
		local lines = {
			string.format("SERVER %s, %.0f s, %d frames (%.1f a second)", LABEL, os.clock() - s.started, #s.dts, #s.dts / math.max(0.001, os.clock() - s.started)),
			"enemies:               " .. summary(s.enemies),
			"frame ms (dt):         " .. summary(s.dts) .. string.format("  over 16.7 ms: %d, over 33.3 ms: %d", over16, over33),
		}
		for _, name in names do
			table.insert(lines, string.format("%-22s %s", name .. ":", summary(s.samples[name])))
		end
		if #s.enemyMs > 0 then
			table.insert(lines, "EnemyMs (scheduler, per frame, 1 s means): " .. summary(s.enemyMs))
			table.insert(lines, "EnemyPeakMs (worst frame in each second):  " .. summary(s.enemyPeakMs))
		else
			table.insert(lines, "EnemyMs: none published (old code): use the Script Profiler (HOW-TO step 3)")
		end
		return table.concat(lines, "\n")
	end
	return s
end

local function clientProbe()
	local s = { started = os.clock(), dts = {} }
	s.connection = RunService.RenderStepped:Connect(function(dt)
		table.insert(s.dts, dt)
		if os.clock() - s.started >= SECONDS then
			s.connection:Disconnect()
			s.done = true
		end
	end)
	function s.report()
		local n = #s.dts
		if n == 0 then
			return "CLIENT: no frames"
		end
		local total = 0
		for _, dt in s.dts do
			total += dt
		end
		local sorted = table.clone(s.dts)
		table.sort(sorted, function(a, b)
			return a > b
		end)
		-- 1% low: the average FPS over the slowest 1% of frames.
		local slow, count = 0, math.max(1, math.floor(n / 100))
		for i = 1, count do
			slow += sorted[i]
		end
		return string.format("CLIENT %s, %.0f s: average %.1f FPS, 1%% low %.1f FPS, worst frame %.1f ms", LABEL, total, n / total, count / slow, sorted[1] * 1000)
	end
	return s
end

local key = RunService:IsClient() and "client" or "server"
_G.MobPerfProbe = _G.MobPerfProbe or {}
local running = _G.MobPerfProbe[key]
if running then
	if not running.done then
		return string.format("%s probe still sampling: %.0f of %d s", key, os.clock() - running.started, SECONDS)
	end
	_G.MobPerfProbe[key] = nil
	return running.report()
end
local probe = key == "client" and clientProbe() or serverProbe()
if BLOCK then
	while not probe.done do
		task.wait(0.5)
	end
	return probe.report()
end
_G.MobPerfProbe[key] = probe
return string.format("%s probe started (%s, %d s); call again after it finishes", key, LABEL, SECONDS)
