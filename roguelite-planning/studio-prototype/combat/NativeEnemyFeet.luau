-- Two-link IK on the preferred native R15 rigs. A stance foot moves backward
-- exactly one stud per stud of root travel, then lifts through a recovery arc.
local F = {}
local TAU = 2 * math.pi
local function rotationBetween(a, b)
	a = a.Unit
	b = b.Unit
	local dot = math.clamp(a:Dot(b), -1, 1)
	local axis = a:Cross(b)
	if axis.Magnitude < 1e-6 then
		return dot > 0 and CFrame.identity or CFrame.Angles(math.pi, 0, 0)
	end
	return CFrame.fromAxisAngle(axis.Unit, math.acos(dot))
end
function F.bind(npc, kind)
	local root = npc:FindFirstChild("HumanoidRootPart")
	local h = npc:FindFirstChildOfClass("Humanoid")
	local rootMotor = npc:FindFirstChild("Root", true)
	if not root or not h or not rootMotor or not rootMotor:IsA("Motor6D") then
		return nil
	end
	local state = {
		root = root,
		humanoid = h,
		rootMotor = rootMotor,
		legs = {},
		stance = kind == "Baby" and 0.22 or kind == "Mutant" and 0.52 or 0.32,
	}
	local verticalRatio = kind == "Mutant" and 0.8 or 0.86
	local lengthTotal = 0
	local offsetTotal = 0
	for _, side in { "Left", "Right" } do
		local hip = npc:FindFirstChild(side .. "Hip", true)
		local knee = npc:FindFirstChild(side .. "Knee", true)
		local ankle = npc:FindFirstChild(side .. "Ankle", true)
		if not hip or not knee or not ankle then
			return nil
		end
		local u = hip.C1:Inverse() * knee.C0
		local v = knee.C1:Inverse() * ankle.C0
		local l1, l2 = u.Position.Magnitude, v.Position.Magnitude
		local length = l1 + l2
		local hipRest = rootMotor.C0 * rootMotor.C1:Inverse() * hip.C0
		local footRest = hipRest * hip.C1:Inverse() * knee.C0 * knee.C1:Inverse() * ankle.C0 * ankle.C1:Inverse()
		local foot = ankle.Part1
		local height = h.HipHeight + root.Size.Y * 0.5 + hipRest.Y - foot.Size.Y * 0.5 - ankle.C1.Y
		local reach = length * math.sqrt(0.96 ^ 2 - verticalRatio ^ 2)
		state.legs[side] = {
			hip = hip,
			knee = knee,
			ankle = ankle,
			u = u.Position,
			v = v.Position,
			l1 = l1,
			l2 = l2,
			foot = foot,
			rest = footRest,
			reach = reach,
			length = length,
		}
		lengthTotal += reach * 2 / state.stance
		offsetTotal += length * verticalRatio - height
	end
	state.strideLength = lengthTotal * 0.5
	state.bodyOffset = offsetTotal * 0.5
	return state
end
function F.footPath(u, stance, reach, length)
	if u < stance then
		return reach * (1 - 2 * u / stance), 0, true
	end
	local t = (u - stance) / (1 - stance)
	-- Short toe-off/landing arcs match the planted backward derivative. The
	-- middle swing has zero endpoint velocity; lift has zero ground velocity.
	local edge = 0.06
	local tangent = -2 * reach * (1 - stance) / stance
	local forward
	if t < edge then
		forward = -reach + tangent * (t - t * t / (2 * edge))
	elseif t > 1 - edge then
		local remaining = 1 - t
		forward = reach - tangent * (remaining - remaining * remaining / (2 * edge))
	else
		local alpha = (t - edge) / (1 - 2 * edge)
		local smooth = alpha * alpha * (3 - 2 * alpha)
		local start = -reach + tangent * edge * 0.5
		forward = start * (1 - 2 * smooth)
	end
	return forward, math.sin(t * math.pi) ^ 2 * length * 0.22, false
end
function F.apply(state, poses, phase, stride, attacking)
	if not state then
		return poses
	end
	-- Slam roots keep their small authored vertical impulse on top of the stance.
	poses.Root = CFrame.new(0, state.bodyOffset, 0) * (poses.Root or CFrame.identity)
	local root = state.root
	local lower = root.CFrame * state.rootMotor.C0 * poses.Root * state.rootMotor.C1:Inverse()
	local ground = root.Position.Y - state.humanoid.HipHeight - root.Size.Y * 0.5
	for side, leg in state.legs do
		local u = (phase / TAU + 0.75 + (side == "Right" and 0.5 or 0)) % 1
		local forward, lift = F.footPath(u, state.stance, leg.reach, leg.length)
		forward *= stride
		lift *= stride
		if attacking then
			forward = 0
			lift = 0
		end
		local horizontal = root.CFrame * Vector3.new(leg.rest.X, 0, leg.rest.Z - forward)
		local footTarget = CFrame.new(horizontal.X, ground + leg.foot.Size.Y * 0.5 + lift, horizontal.Z)
			* root.CFrame.Rotation
		local hipWorld = lower * leg.hip.C0
		local target = footTarget * leg.ankle.C1
		local delta = hipWorld:PointToObjectSpace(target.Position)
		local distance = math.clamp(delta.Magnitude, math.abs(leg.l1 - leg.l2) + 1e-4, leg.l1 + leg.l2 - 1e-4)
		local direction = delta.Magnitude > 1e-5 and delta.Unit or -Vector3.yAxis
		local pole = hipWorld:VectorToObjectSpace(root.CFrame.LookVector)
		pole -= direction * pole:Dot(direction)
		if pole.Magnitude < 1e-5 then
			pole = Vector3.zAxis
		end
		local along = (leg.l1 ^ 2 - leg.l2 ^ 2 + distance ^ 2) / (2 * distance)
		local bend = math.sqrt(math.max(0, leg.l1 ^ 2 - along ^ 2))
		local kneeVector = direction * along + pole.Unit * bend
		local hipRotation = rotationBetween(leg.u, kneeVector)
		local upper = hipWorld * hipRotation * leg.hip.C1:Inverse()
		local kneeWorld = upper * leg.knee.C0
		local actualTarget = hipWorld * (direction * distance)
		local kneeRotation = rotationBetween(leg.v, kneeWorld:VectorToObjectSpace(actualTarget - kneeWorld.Position))
		local lowerLeg = kneeWorld * kneeRotation * leg.knee.C1:Inverse()
		poses[side .. "Hip"] = hipRotation
		poses[side .. "Knee"] = kneeRotation
		poses[side .. "Ankle"] = (lowerLeg * leg.ankle.C0):ToObjectSpace(footTarget * leg.ankle.C1).Rotation
	end
	return poses
end

-- Imported bipeds (Bone or Motor6D rigs) run on the same planted feet. Their authored Move clips
-- are slow walks: a skeleton's foot sweeps 1.9 studs with 0.3 studs of lift, so at 17 studs/s the
-- clip looped 5.5 times a second and the body glided over tiny shuffling steps. Here the legs
-- (Thigh/Shin/Foot bones or UpperLeg/LowerLeg/Foot motors) follow footPath at a running stance,
-- and the clip keeps the upper body, timed so its arm swing matches the feet.
local CHAINS = { { "Thigh", "Shin", "Foot" }, { "UpperLeg", "LowerLeg", "Foot" } }
local partWorld
-- The frame a joint's pose applies in: a Bone's parent times its rest CFrame, a motor's Part0
-- times C0. Rest values come from the rig, never from last frame's Transform.
local function pivot(rig, joint, poses)
	if joint:IsA("Bone") then
		return partWorld(rig, joint.Parent, poses) * joint.CFrame
	end
	return partWorld(rig, joint.Part0, poses) * joint.C0
end
function partWorld(rig, node, poses)
	if node:IsA("Bone") then
		return pivot(rig, node, poses) * (poses[node.Name] or CFrame.identity)
	end
	local motor = rig.byPart[node]
	if motor then
		return pivot(rig, motor, poses) * (poses[rig.alias[motor]] or CFrame.identity) * motor.C1:Inverse()
	end
	return node.CFrame
end
-- From a joint's posed frame to its child joint's pivot; nil if the two aren't directly linked.
local function link(joint, child)
	if joint:IsA("Bone") then
		return child.Parent == joint and child.CFrame or nil
	end
	return child:IsA("Motor6D") and child.Part0 == joint.Part1 and joint.C1:Inverse() * child.C0 or nil
end
-- joints: EnemyMotion.bind(npc). sample(t): the Move clip's poses at t, as the client displays
-- them. stance: the planted share of each stride (0.32 like the zombies; heavies plod at 0.45).
function F.bindImported(npc, joints, sample, duration, stance)
	local root = npc:FindFirstChild("HumanoidRootPart")
	local h = npc:FindFirstChildOfClass("Humanoid")
	if not root or not h then
		return nil
	end
	local rig = { byPart = {}, alias = {} }
	for _, v in npc:GetDescendants() do
		if v:IsA("Motor6D") and v.Part0 and v.Part1 then
			rig.byPart[v.Part1] = v
			rig.alias[v] = v:GetAttribute("EnemyBone") or v.Name:gsub("Motor6D$", "")
		end
	end
	local function find(name)
		local list = joints[name]
		return list and list[1]
	end
	local chain
	for _, names in CHAINS do
		if find("Left" .. names[1]) and find("Right" .. names[1]) then
			chain = names
			break
		end
	end
	if not chain then
		return nil
	end
	local state = { root = root, humanoid = h, rig = rig, legs = {}, stance = stance }
	local frame = root.CFrame
	local floor = -(h.HipHeight + root.Size.Y * 0.5)
	local rest = {}
	for _, side in { "Left", "Right" } do
		local hip, knee, ankle = find(side .. chain[1]), find(side .. chain[2]), find(side .. chain[3])
		local upper, lower = hip and knee and link(hip, knee), knee and ankle and link(knee, ankle)
		if not upper or not lower then
			return nil
		end
		local ankleRest = frame:ToObjectSpace(pivot(rig, ankle, rest))
		state.legs[side] = {
			hip = hip,
			names = { side .. chain[1], side .. chain[2], side .. chain[3] },
			upper = upper,
			lower = lower,
			u = upper.Position,
			v = lower.Position,
			l1 = upper.Position.Magnitude,
			l2 = lower.Position.Magnitude,
			length = upper.Position.Magnitude + lower.Position.Magnitude,
			rest = ankleRest.Position,
			footRotation = ankleRest.Rotation,
			height = ankleRest.Y - floor,
		}
	end
	-- Over one Move loop: the hips' average height, which way the knees bend, and when the left
	-- foot reaches furthest forward (its plant, which footPath puts at phase 0.25).
	local SAMPLES = 16
	local hipHeight, kneeForward, plantZ = 0, 0, math.huge
	state.plantTime = 0
	for i = 0, SAMPLES - 1 do
		local t = duration * i / SAMPLES
		local poses = sample(t)
		for side, leg in state.legs do
			local hipAt = frame:PointToObjectSpace(pivot(rig, leg.hip, poses).Position)
			local kneeFrame = pivot(rig, leg.hip, poses) * (poses[leg.names[1]] or CFrame.identity) * leg.upper
			local kneeAt = frame:PointToObjectSpace(kneeFrame.Position)
			local ankleAt = frame:PointToObjectSpace((kneeFrame * (poses[leg.names[2]] or CFrame.identity) * leg.lower).Position)
			local line = ankleAt - hipAt
			local along = line.Magnitude > 1e-4 and math.clamp((kneeAt - hipAt):Dot(line) / line:Dot(line), 0, 1) or 0
			kneeForward -= (kneeAt - (hipAt + line * along)).Z
			hipHeight += (hipAt.Y - floor - leg.height) / (SAMPLES * 2)
			if side == "Left" and ankleAt.Z < plantZ then
				plantZ = ankleAt.Z
				state.plantTime = t
			end
		end
	end
	-- Lower the body when straight legs would leave no reach (the zombies do the same), then
	-- size the stride from the reach: stance 0.32 and 0.85 reach make a 5.3-stud stride.
	local length = (state.legs.Left.length + state.legs.Right.length) * 0.5
	state.drop = math.max(0, hipHeight - length * 0.88)
	local reach = length * math.sqrt(math.max(0, 0.96 ^ 2 - ((hipHeight - state.drop) / length) ^ 2))
	reach = math.clamp(reach, length * 0.2, length * 0.45)
	local hip = state.legs.Left.hip
	local body = hip:IsA("Bone") and hip.Parent or rig.byPart[hip.Part0]
	if state.drop > 0 and body and (body:IsA("Bone") or body:IsA("Motor6D")) then
		state.body, state.bodyName = body, body:IsA("Bone") and body.Name or rig.alias[body]
	else
		state.drop = 0
	end
	for _, leg in state.legs do
		leg.reach = reach
		leg.pole = kneeForward >= 0 and 1 or -1
	end
	state.strideLength = reach * 2 / stance
	return state
end
-- weight: how much of a walk this frame is (0 standing, 1 running); the clip keeps the rest.
function F.applyImported(state, poses, phase, weight)
	if not state or weight <= 1e-3 then
		return poses
	end
	local rig, root = state.rig, state.root
	if state.body then
		local frame = pivot(rig, state.body, poses)
		local name = state.bodyName
		poses[name] = CFrame.new(frame:VectorToObjectSpace(Vector3.new(0, -state.drop * weight, 0)))
			* (poses[name] or CFrame.identity)
	end
	local floor = root.Position.Y - state.humanoid.HipHeight - root.Size.Y * 0.5
	for side, leg in state.legs do
		local u = (phase / TAU + 0.75 + (side == "Right" and 0.5 or 0)) % 1
		local forward, lift = F.footPath(u, state.stance, leg.reach, leg.length)
		local flat = root.CFrame * Vector3.new(leg.rest.X, 0, leg.rest.Z - forward)
		local target = Vector3.new(flat.X, floor + leg.height + lift, flat.Z)
		local hipFrame = pivot(rig, leg.hip, poses)
		local delta = hipFrame:PointToObjectSpace(target)
		local distance = math.clamp(delta.Magnitude, math.abs(leg.l1 - leg.l2) + 1e-4, leg.l1 + leg.l2 - 1e-4)
		local direction = delta.Magnitude > 1e-5 and delta.Unit or hipFrame:VectorToObjectSpace(-Vector3.yAxis)
		local pole = hipFrame:VectorToObjectSpace(root.CFrame.LookVector * leg.pole)
		pole -= direction * pole:Dot(direction)
		if pole.Magnitude < 1e-5 then
			pole = direction:Cross(hipFrame:VectorToObjectSpace(root.CFrame.RightVector))
		end
		local along = (leg.l1 ^ 2 - leg.l2 ^ 2 + distance ^ 2) / (2 * distance)
		local bend = math.sqrt(math.max(0, leg.l1 ^ 2 - along ^ 2))
		local hipRotation = rotationBetween(leg.u, direction * along + pole.Unit * bend)
		local kneeFrame = hipFrame * hipRotation * leg.upper
		local kneeRotation =
			rotationBetween(leg.v, kneeFrame:VectorToObjectSpace(hipFrame * (direction * distance) - kneeFrame.Position))
		local ankleFrame = kneeFrame * kneeRotation * leg.lower
		local ankleRotation = ankleFrame.Rotation:Inverse() * root.CFrame.Rotation * leg.footRotation
		local hipName, kneeName, ankleName = leg.names[1], leg.names[2], leg.names[3]
		poses[hipName] = (poses[hipName] or CFrame.identity):Lerp(hipRotation, weight)
		poses[kneeName] = (poses[kneeName] or CFrame.identity):Lerp(kneeRotation, weight)
		poses[ankleName] = (poses[ankleName] or CFrame.identity):Lerp(ankleRotation, weight)
	end
	return poses
end
return F
