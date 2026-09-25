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
return F
