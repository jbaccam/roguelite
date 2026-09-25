-- Authored Blender local bone deltas, converted once by the exporter to Roblox.
-- Supports duplicated Bone hierarchies and rigid articulated Motor6D imports.
local M = {}
local cache = {}
function M.compile(data)
	assert(type(data) == "table" and data.bones and data.clips, "Invalid enemy animation payload")
	local result = { clips = {}, bones = data.bones, motion = data.motion or {}, projectile = data.projectile }
	for name, clip in data.clips do
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
		result.clips[name] = { frames = frames, duration = clip.duration, loop = clip.loop == true }
	end
	for _, name in { "Idle", "Move", "Attack" } do
		assert(result.clips[name], "Required enemy clip " .. name)
	end
	return result
end
function M.load(id)
	if cache[id] then
		return cache[id]
	end
	local folder = script.Parent:FindFirstChild("EnemyAnimations")
	local source = folder and folder:FindFirstChild(id)
	if not source then
		return nil
	end
	local compiled = M.compile(require(source))
	cache[id] = compiled
	return compiled
end
function M.sample(data, name, time)
	local clip = data.clips[name]
	if not clip then
		return {}
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
	local poses = {}
	for name, pose in a.poses do
		poses[name] = pose:Lerp(b.poses[name] or pose, alpha)
	end
	return poses
end
function M.blend(a, b, alpha)
	local result = {}
	for name, pose in b do
		result[name] = (a[name] or pose):Lerp(pose, alpha)
	end
	return result
end
function M.scalePose(poses, ratio)
	if math.abs(ratio - 1) < 1e-6 then
		return poses
	end
	local result = {}
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
function M.apply(joints, poses)
	for name, pose in poses do
		for _, joint in joints[name] or {} do
			if joint.Parent then
				joint.Transform = pose
			end
		end
	end
end
-- Forward kinematics for server projectile origins; never reads a client pose.
function M.boneWorld(npc, name, poses)
	local target = npc:FindFirstChild(name, true)
	local byPart, byName = {}, {}
	for _, v in npc:GetDescendants() do
		if v:IsA("Motor6D") and v.Part0 and v.Part1 then
			local alias = v:GetAttribute("EnemyBone") or v.Name:gsub("Motor6D$", "")
			byPart[v.Part1] = v
			byName[alias] = v
		end
	end
	local function world(node)
		if node:IsA("Bone") then
			return world(node.Parent) * node.CFrame * (poses[node.Name] or CFrame.identity)
		end
		if node:IsA("BasePart") then
			local motor = byPart[node]
			if motor then
				local alias = motor:GetAttribute("EnemyBone") or motor.Name:gsub("Motor6D$", "")
				return world(motor.Part0) * motor.C0 * (poses[alias] or CFrame.identity) * motor.C1:Inverse()
			end
			return node.CFrame
		end
		return npc:GetPivot()
	end
	if target and target:IsA("Bone") then
		return world(target)
	end
	local motor = byName[name]
	if motor then
		return world(motor.Part1) * motor.C1
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
