-- Authored Blender local bone deltas, converted once by the exporter to Roblox.
-- Supports duplicated Bone hierarchies and rigid articulated Motor6D imports.
local M = {}
local cache = {}
local loading, failed = {}, {}
local REQUIRED = { "Idle", "Move", "Attack" }
local function compileClip(data, clip)
	local frames = {}
	for i, frame in clip.frames do
		local poses = {}
		for bone, values in frame.transforms do
			assert(#values == 12, "Expected local CFrame with 12 components")
			for _, v in values do
				assert(type(v) == "number" and v == v and math.abs(v) < 1e6, "Invalid transform")
			end
			poses[bone] = CFrame.new(table.unpack(values))
		end
		frames[i] = { time = frame.time or (i - 1) / (clip.fps or data.fps or 24), poses = poses }
	end
	assert(#frames >= 2 and clip.duration > 0, "Empty enemy clip")
	return { frames = frames, duration = clip.duration, loop = clip.loop == true }
end
-- `eager` lists the clips to build now (nil: all of them); any other clip builds on its first
-- lookup. A clip table listed under two names (map bosses alias Walk as Move) builds once.
function M.compile(data, eager)
	assert(type(data) == "table" and data.bones and data.clips, "Invalid enemy animation payload")
	local raw, built = data.clips, {}
	local function build(clip)
		local compiled = built[clip]
		if not compiled then
			compiled = compileClip(data, clip)
			built[clip] = compiled
		end
		return compiled
	end
	local clips = setmetatable({}, {
		__index = function(t, name)
			local clip = raw[name]
			if clip == nil then
				return nil
			end
			local compiled = build(clip)
			rawset(t, name, compiled)
			return compiled
		end,
	})
	local result = { clips = clips, bones = data.bones, motion = data.motion or {}, projectile = data.projectile }
	for name, clip in raw do
		if not eager or table.find(eager, name) then
			rawset(clips, name, build(clip))
		end
	end
	for _, name in REQUIRED do
		assert(raw[name], "Required enemy clip " .. name)
	end
	return result
end
local function source(id)
	local folder = script.Parent:FindFirstChild("EnemyAnimations")
	return folder and folder:FindFirstChild(id)
end
-- Ordinary enemies only ever sample Idle, Move and Attack; Hit/Death build if someone asks.
function M.load(id)
	if cache[id] then
		return cache[id]
	end
	local module = source(id)
	if not module then
		return nil
	end
	local compiled = M.compile(require(module), REQUIRED)
	cache[id] = compiled
	return compiled
end
-- One warm() step on a later frame, under a MicroProfiler label (a throwing step closes it).
local function step(label, f, ...)
	task.wait()
	debug.profilebegin(label)
	local ok, result = pcall(f, ...)
	debug.profileend()
	if not ok then
		error(result, 0)
	end
	return result
end
-- load() spread over frames for the client, starting next frame: each clip module decodes on
-- its own frame, then one clip compiles per frame. Yields; call it from a thread. Same data as
-- load() once built.
function M.warm(id)
	while loading[id] do
		task.wait()
	end
	if cache[id] or failed[id] then
		return cache[id]
	end
	local module = source(id)
	if not module then
		return nil
	end
	loading[id] = true
	local ok, result = pcall(function()
		-- init requires these modules itself; requiring them first, leaves before the clips that
		-- join them (reverse descendant order), only moves each decode to its own frame.
		local modules = module:GetDescendants()
		for i = #modules, 1, -1 do
			if modules[i]:IsA("ModuleScript") then
				step("EnemyMotion:Decode", require, modules[i])
			end
		end
		local compiled = step("EnemyMotion:Decode", function()
			return M.compile(require(module), {})
		end)
		for _, name in REQUIRED do
			step("EnemyMotion:Compile", function()
				return compiled.clips[name]
			end)
		end
		return compiled
	end)
	loading[id] = nil
	if not ok then
		failed[id] = true
		warn("EnemyMotion: " .. tostring(id) .. " clips failed: " .. tostring(result))
		return nil
	end
	cache[id] = cache[id] or result
	return cache[id]
end
-- Non-blocking: the data if built, else starts warm() and returns nil, true while it builds.
function M.loadAsync(id)
	if cache[id] then
		return cache[id]
	end
	if failed[id] or not source(id) then
		return nil, false
	end
	if not loading[id] then
		task.spawn(M.warm, id)
	end
	return nil, true
end
-- sample/blend/scalePose write into `out` when given (cleared first, so its contents equal a
-- fresh result): per-enemy buffers instead of new tables every frame. `out` must not be an input.
function M.sample(data, name, time, out)
	local clip = data.clips[name]
	local poses = out or {}
	table.clear(poses)
	if not clip then
		return poses
	end
	time = clip.loop and time % clip.duration or math.clamp(time, 0, clip.duration)
	local frames = clip.frames
	local lo, hi = 1, #frames
	while lo < hi do
		local mid = math.ceil((lo + hi) / 2)
		if frames[mid].time <= time then
			lo = mid
		else
			hi = mid - 1
		end
	end
	local a, b = frames[lo], frames[math.min(lo + 1, #frames)]
	local alpha = b.time > a.time and math.clamp((time - a.time) / (b.time - a.time), 0, 1) or 0
	for name, pose in a.poses do
		poses[name] = pose:Lerp(b.poses[name] or pose, alpha)
	end
	return poses
end
function M.blend(a, b, alpha, out)
	local result = out or {}
	table.clear(result)
	for name, pose in b do
		result[name] = (a[name] or pose):Lerp(pose, alpha)
	end
	return result
end
function M.scalePose(poses, ratio, out)
	if math.abs(ratio - 1) < 1e-6 then
		return poses
	end
	local result = out or {}
	table.clear(result)
	for name, pose in poses do
		result[name] = CFrame.new(pose.Position * ratio) * pose.Rotation
	end
	return result
end
function M.bind(npc)
	local joints = {}
	for _, v in npc:GetDescendants() do
		if v:IsA("Bone") or v:IsA("Motor6D") then
			local name = v:GetAttribute("EnemyBone") or v.Name:gsub("Motor6D$", "")
			joints[name] = joints[name] or {}
			table.insert(joints[name], v)
		end
	end
	return joints
end
local NONE = table.freeze({})
function M.apply(joints, poses)
	for name, pose in poses do
		for _, joint in joints[name] or NONE do
			if joint.Parent then
				joint.Transform = pose
			end
		end
	end
end
-- boneWorld's rig lookups per model, rebuilt only after a descendant is added or removed (or a
-- cached joint lost its parent): casters and archers ask for a bone every frame.
local rigs = setmetatable({}, { __mode = "k" })
local function rigOf(npc)
	local rig = rigs[npc]
	if not rig then
		rig = { dirty = true }
		rigs[npc] = rig
		local function changed()
			rig.dirty = true
		end
		npc.DescendantAdded:Connect(changed)
		npc.DescendantRemoving:Connect(changed)
	end
	if rig.dirty then
		rig.dirty = false
		rig.targets, rig.byPart, rig.byName, rig.alias = {}, {}, {}, {}
		for _, v in npc:GetDescendants() do
			if v:IsA("Motor6D") and v.Part0 and v.Part1 then
				local alias = v:GetAttribute("EnemyBone") or v.Name:gsub("Motor6D$", "")
				rig.byPart[v.Part1] = v
				rig.byName[alias] = v
				rig.alias[v] = alias
			end
		end
	end
	return rig
end
local function world(rig, npc, node, poses)
	if node:IsA("Bone") then
		return world(rig, npc, node.Parent, poses) * node.CFrame * (poses[node.Name] or CFrame.identity)
	end
	if node:IsA("BasePart") then
		local motor = rig.byPart[node]
		if motor then
			local pose = poses[rig.alias[motor]] or CFrame.identity
			return world(rig, npc, motor.Part0, poses) * motor.C0 * pose * motor.C1:Inverse()
		end
		return node.CFrame
	end
	return npc:GetPivot()
end
-- Forward kinematics for server projectile origins; never reads a client pose.
function M.boneWorld(npc, name, poses)
	local rig = rigOf(npc)
	local target = rig.targets[name]
	if target == nil then
		target = npc:FindFirstChild(name, true) or false
		rig.targets[name] = target
	end
	local motor = not (target and target:IsA("Bone")) and rig.byName[name]
	if (target and not target.Parent) or (motor and not motor.Parent) then
		-- Removed since the last rebuild (removal signals are deferred): rescan now.
		rig.dirty = true
		return M.boneWorld(npc, name, poses)
	end
	if target and target:IsA("Bone") then
		return world(rig, npc, target, poses)
	end
	if motor then
		return world(rig, npc, motor.Part1, poses) * motor.C1
	end
	return nil
end
function M.arrowPose(npc, data, poses)
	local p = data.projectile
	if not p then
		return nil
	end
	local hand = M.boneWorld(npc, "LeftHand", poses)
	local draw = M.boneWorld(npc, "BowDraw", poses)
	if not hand or not draw then
		return nil
	end
	local upper = hand * Vector3.new(table.unpack(p.upperStringInHand))
	local ratio = npc:GetScale() / (npc:GetAttribute("EnemyBaselineModelScale") or 1)
	upper = hand * (Vector3.new(table.unpack(p.upperStringInHand)) * ratio)
	local rest = hand * (Vector3.new(table.unpack(p.arrowRestInHand)) * ratio)
	local nock = draw.Position:Lerp(upper, p.nockFraction or 0.22)
	return nock, (rest - nock).Unit
end
function M.projectileOrigin(npc, data, poses)
	local p = data.projectile
	if not p then
		return nil
	end
	if p.heldBone and p.centerInBone then
		local joint = M.boneWorld(npc, p.heldBone, poses)
		local ratio = npc:GetScale() / (npc:GetAttribute("EnemyBaselineModelScale") or 1)
		return joint and joint * (Vector3.new(table.unpack(p.centerInBone)) * ratio) or nil
	end
	if p.upperStringInHand and p.arrowRestInHand then
		return M.arrowPose(npc, data, poses)
	end
	return nil
end
return M
