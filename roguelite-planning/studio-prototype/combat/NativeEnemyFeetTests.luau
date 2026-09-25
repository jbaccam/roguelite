-- Independent forward-kinematic checks against the real preserved Motor6Ds.
return function(templates, Feet, Motion)
	local output = {}
	local checks = 0
	for kind, name in { Regular = "Zombie_NPC", Baby = "BabyZombie_NPC", Mutant = "MutantZombie_NPC" } do
		local npc = templates[name]:Clone()
		npc.Parent = templates.Parent
		local state = assert(Feet.bind(npc, kind))
		local root = state.root
		local function sample(phase, distance)
			root.CFrame = CFrame.new(0, state.humanoid.HipHeight + root.Size.Y * 0.5, -distance)
			local pose = Feet.apply(state, Motion.pose(kind, phase, 1, 1, 0), phase, 1, false)
			local solved = { [root] = root.CFrame }
			local joints = {}
			for _, j in npc:GetDescendants() do
				if j:IsA("Motor6D") then
					joints[j.Part1] = j
				end
			end
			local function world(part)
				if solved[part] then
					return solved[part]
				end
				local j = assert(joints[part])
				solved[part] = world(j.Part0) * j.C0 * (pose[j.Name] or CFrame.identity) * j.C1:Inverse()
				return solved[part]
			end
			return world(npc.LeftFoot), world(npc.RightFoot), world(npc.LeftHand), world(npc.RightHand)
		end
		local first
		local slip, ground = 0, 0
		for i = 0, 100 do
			local u = state.stance * i / 101
			local foot = sample((u - 0.75) * 2 * math.pi, u * state.strideLength)
			first = first or foot.Position
			slip = math.max(slip, Vector2.new(foot.X - first.X, foot.Z - first.Z).Magnitude)
			ground = math.max(ground, math.abs(foot.Y - npc.LeftFoot.Size.Y * 0.5))
			checks += 1
		end
		assert(slip < 0.0001 and ground < 0.0001, "Planted foot drift or ground gap: " .. kind)
		local rows = {}
		local penetration = 0
		for i = 0, 119 do
			local lf, rf, lh, rh = sample(i / 120 * 2 * math.pi, 0)
			table.insert(rows, { lf = -lf.Z, rf = -rf.Z, lh = -lh.Z, rh = -rh.Z })
			penetration =
				math.max(penetration, -(lf.Y - npc.LeftFoot.Size.Y * 0.5), -(rf.Y - npc.RightFoot.Size.Y * 0.5))
			checks += 1
		end
		local function covariance(a, b)
			local ma, mb = 0, 0
			for _, row in rows do
				ma += row[a]
				mb += row[b]
			end
			ma /= #rows
			mb /= #rows
			local value = 0
			for _, row in rows do
				value += (row[a] - ma) * (row[b] - mb)
			end
			return value / #rows
		end
		local lr, rl, same = covariance("lf", "rh"), covariance("rf", "lh"), covariance("lf", "lh")
		assert(lr > 0 and rl > 0 and same < 0, "Foot/hand opposition lost after IK: " .. kind)
		assert(penetration < 0.0001, "Foot penetrates floor: " .. kind)
		local eps = 1e-5
		local edge = state.stance
		local reach = state.legs.Left.reach
		local length = state.legs.Left.length
		local before = (
			Feet.footPath(edge - eps, edge, reach, length) - Feet.footPath(edge - eps * 2, edge, reach, length)
		) / eps
		local after = (
			Feet.footPath(edge + eps * 2, edge, reach, length) - Feet.footPath(edge + eps, edge, reach, length)
		) / eps
		assert(math.abs(before - after) < 0.05, "Toe-off horizontal velocity jumps: " .. kind)
		output[kind] = {
			strideLength = state.strideLength,
			bodyOffset = state.bodyOffset,
			maxStanceSlip = slip,
			maxGroundError = ground,
			maxPenetration = penetration,
			opposingCovariance = { lr, rl },
			sameSideCovariance = same,
		}
		npc:Destroy()
	end
	return { checks = checks, rigs = output }
end
