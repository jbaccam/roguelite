--!nonstrict
-- Mob movement probe (launch audit P5: the Humanoid setup changed, so measure before and after).
-- NOT read-only: during an approved Play session it admin-spawns one regular zombie, one tank and
-- one werewolf next to the first player, turns Admin Freeze on (so their AI stays out of the way,
-- the wave's enemies stand still too), drives each one with Humanoid:Move on the server and
-- measures, from server velocities sampled every frame:
--   accel   seconds from standing to 90% of WalkSpeed
--   reverse seconds from full speed one way to 90% of WalkSpeed the other way (turning included)
--   stop    seconds from full speed, after Move(0) + MoveTo(own position) like the chase's stop,
--           to under 10% of WalkSpeed, and how far it slid
-- then removes its three enemies and puts Admin Freeze back as it was. Paste the whole file as the
-- code of one execute_luau call in the Server datamodel during a run's combat phase (a wave is on;
-- Keep N alive off is best). Takes about 6 s. Run it once on the old code (before the push) and
-- once after; the numbers should match within a frame (0.017 s).
-- Reference (2026-10-01, EnemyTemplateTests): a scale-1 werewolf reversed in 0.08 s and stopped in
-- 0.05 s; at scale 0.01 it reached 10 of 16 studs/s after 1.2 s, never reversed and slid 0.9 s.
local IDS = { "regular-zombie", "tank-zombie", "werewolf" }
local RUN = 1.2 -- seconds per leg

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local combat = game:GetService("ReplicatedStorage"):WaitForChild("RogueliteCombat")
local spawner = game:GetService("ServerStorage"):FindFirstChild("AdminSpawn")
assert(RunService:IsServer() and RunService:IsRunning(), "run this in the Server datamodel during Play")
assert(spawner, "no AdminSpawn: this server runs no waves")
assert(combat:GetAttribute("ZombiesEnabled") == true, "start a wave first (enemies are off)")
local player = Players:GetPlayers()[1]
local anchor = player and player.Character and player.Character:FindFirstChild("HumanoidRootPart")
assert(anchor, "no player body to spawn next to")
local folder = workspace:WaitForChild("RogueliteEnemies")

local wasFrozen = combat:GetAttribute("AdminFreeze") == true
spawner:Invoke("Freeze", true)
local before = {}
for _, npc in folder:GetChildren() do
	before[npc] = true
end
for _, id in IDS do
	spawner:Invoke("Spawn", id, 1, anchor.Position)
end
local probes = {}
for _, npc in folder:GetChildren() do
	if not before[npc] and npc:GetAttribute("AdminSpawn") then
		probes[npc:GetAttribute("EnemyId")] = npc
	end
end
task.wait(0.6) -- land, and let the first frozen step pass

local function flat(v)
	return Vector3.new(v.X, 0, v.Z)
end
-- The direction with the most open floor (8 headings, 34 studs, at hip height and at the feet).
local function openDirection(root, avoid)
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { folder, avoid }
	local best, bestRoom = Vector3.xAxis, -1
	for i = 0, 7 do
		local direction = CFrame.Angles(0, i * math.pi / 4, 0):VectorToWorldSpace(Vector3.zAxis)
		local room = 34
		for _, height in { 0, -1.5 } do
			local hit = workspace:Raycast(root.Position + Vector3.yAxis * height, direction * 34, params)
			if hit then room = math.min(room, (hit.Position - root.Position).Magnitude) end
		end
		if room > bestRoom then best, bestRoom = direction, room end
	end
	return best, bestRoom
end
local function measure(id, npc)
	local h, root = npc:FindFirstChildOfClass("Humanoid"), npc:FindFirstChild("HumanoidRootPart")
	if not h or not root then return { id = id, error = "no humanoid/root" } end
	local speed = h.WalkSpeed
	local direction, room = openDirection(root, player.Character)
	local result = { id = id, walkSpeed = speed, mass = root.AssemblyMass, scale = npc:GetScale(), room = room }
	local disabled = {}
	for _, state in { "Swimming", "Seated", "FallingDown", "Ragdoll", "GettingUp", "PlatformStanding", "Flying", "StrafingNoPhysics", "Climbing" } do
		if not h:GetStateEnabled(Enum.HumanoidStateType[state]) then table.insert(disabled, state) end
	end
	result.statesOff = table.concat(disabled, ",")
	result.canTouchParts = 0
	for _, p in npc:GetDescendants() do
		if p:IsA("BasePart") and p.CanTouch then result.canTouchParts += 1 end
	end
	-- One leg: drive, sample every server frame until `reached` or RUN seconds.
	local function leg(drive, reached)
		drive()
		local start = os.clock()
		local at, peak = nil, 0
		while os.clock() - start < RUN do
			RunService.Heartbeat:Wait()
			local v = flat(root.AssemblyLinearVelocity)
			peak = math.max(peak, v.Magnitude)
			if not at and reached(v) then at = os.clock() - start end
		end
		return at, peak
	end
	local accel, peak = leg(function() h:Move(direction) end, function(v) return v:Dot(direction) >= 0.9 * speed end)
	local reverse = leg(function() h:Move(-direction) end, function(v) return v:Dot(-direction) >= 0.9 * speed end)
	local from = root.Position
	local stopAt = leg(function() h:Move(Vector3.zero); h:MoveTo(root.Position) end, function(v) return v.Magnitude < 0.1 * speed end)
	result.accel, result.peakSpeed, result.reverse, result.stop = accel, peak, reverse, stopAt
	result.slide = flat(root.Position - from).Magnitude
	return result
end

local results, pending = {}, 0
for _, id in IDS do
	local npc = probes[id]
	if npc then
		pending += 1
		task.spawn(function()
			local ok, r = pcall(measure, id, npc)
			results[id] = ok and r or { id = id, error = tostring(r) }
			pending -= 1
		end)
	else
		results[id] = { id = id, error = "did not spawn (no open floor 20-40 studs from the player?)" }
	end
end
local waited = os.clock()
while pending > 0 and os.clock() - waited < 10 do
	task.wait(0.1)
end
for _, npc in probes do
	npc:Destroy()
end
spawner:Invoke("Freeze", wasFrozen)

local function fmt(v)
	return v and string.format("%.3f", v) or "never"
end
local lines = { "id                 speed  mass  scale  accel90  reverse90  stop10  slide  peak  room  statesOff / CanTouch parts" }
for _, id in IDS do
	local r = results[id]
	if r.error then
		table.insert(lines, id .. ": " .. r.error)
	else
		table.insert(lines, string.format("%-18s %5.1f %5.1f %5.2f  %7s  %9s  %6s  %5.2f %5.1f %5.1f  %s / %d", id, r.walkSpeed, r.mass, r.scale, fmt(r.accel), fmt(r.reverse), fmt(r.stop), r.slide, r.peakSpeed, r.room, r.statesOff, r.canTouchParts))
	end
end
return table.concat(lines, "\n")
