-- Forward-kinematic checks of the imported-biped run (NativeEnemyFeet.bindImported) on the real
-- templates, like NativeEnemyFeetTests does for the zombies: a stance foot stays put while the
-- body travels a stride, it sits at its rest height above the floor, the knees bend the way the
-- authored walk bends them, and the clip's hands swing against the feet.
-- templates: ServerStorage.RogueliteNPCs. Works on unparented clones; changes nothing.
return function(templates, Feet, Motion, Catalog)
	local TAU = 2 * math.pi
	local I = CFrame.identity
	local output, checks = {}, 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	for _, d in Catalog.List do
		local template = not d.legacy and templates:FindFirstChild(d.template)
		local data = template and Motion.load(d.id)
		if not data then
			continue
		end
		local npc = template:Clone()
		local joints = Motion.bind(npc)
		local duration = data.clips.Move.duration
		local stance = d.runStance or (d.behavior == "Heavy" and 0.45 or 0.32)
		local state = Feet.bindImported(npc, joints, function(t)
			return Motion.sample(data, "Move", t)
		end, duration, stance)
		if not state then
			output[d.id] = "no biped legs (clip gait)"
			npc:Destroy()
			continue
		end
		-- Independent FK: a Bone's posed frame, a motor-driven part's CFrame, else the part.
		local byPart, alias = {}, {}
		for _, v in npc:GetDescendants() do
			if v:IsA("Motor6D") and v.Part0 and v.Part1 then
				byPart[v.Part1] = v
				alias[v] = v:GetAttribute("EnemyBone") or v.Name:gsub("Motor6D$", "")
			end
		end
		local function world(node, poses)
			if node:IsA("Bone") then
				return world(node.Parent, poses) * node.CFrame * (poses[node.Name] or I)
			end
			local m = byPart[node]
			if m then
				return world(m.Part0, poses) * m.C0 * (poses[alias[m]] or I) * m.C1:Inverse()
			end
			return node.CFrame
		end
		local function jointAt(name, poses)
			local j = joints[name][1]
			return (j:IsA("Bone") and world(j.Parent, poses) * j.CFrame or world(j.Part0, poses) * j.C0).Position
		end
		local root = npc.HumanoidRootPart
		local look = root.CFrame.LookVector
		local base = npc:GetPivot()
		local h = npc:FindFirstChildOfClass("Humanoid")
		local function frame(phase, distance)
			npc:PivotTo(base + look * distance)
			local clock = (state.plantTime + (phase / TAU - 0.25) * duration) % duration
			return Feet.applyImported(state, Motion.sample(data, "Move", clock), phase, 1)
		end
		local left = state.legs.Left
		local first, slip, ground = nil, 0, 0
		for i = 0, 100 do
			local u = state.stance * i / 101
			local poses = frame((u - 0.75) * TAU, u * state.strideLength)
			local ankle = jointAt(left.names[3], poses)
			first = first or ankle
			slip = math.max(slip, Vector2.new(ankle.X - first.X, ankle.Z - first.Z).Magnitude)
			local floor = root.Position.Y - h.HipHeight - root.Size.Y * 0.5
			ground = math.max(ground, math.abs(ankle.Y - floor - left.height))
			for _, pose in poses do
				for _, v in { pose:GetComponents() } do
					check(v == v and math.abs(v) < 1e4, "Finite IK pose: " .. d.id)
				end
			end
		end
		check(slip < 1e-3, ("Planted foot slides %.4f studs: %s"):format(slip, d.id))
		check(ground < 1e-3, ("Planted foot off the floor %.4f studs: %s"):format(ground, d.id))
		-- A full loop in place: knee side, foot/hand opposition and swing-foot lift.
		local rows, knee, lift = {}, 0, 0
		for i = 0, 59 do
			local phase = i / 60 * TAU
			local poses = frame(phase, 0)
			local inRoot = function(p)
				return root.CFrame:PointToObjectSpace(p)
			end
			local hip, kneeAt, ankle =
				inRoot(jointAt(left.names[1], poses)), inRoot(jointAt(left.names[2], poses)), inRoot(jointAt(left.names[3], poses))
			local line = ankle - hip
			knee -= (kneeAt - (hip + line * math.clamp((kneeAt - hip):Dot(line) / line:Dot(line), 0, 1))).Z
			lift = math.max(lift, ankle.Y - (-(h.HipHeight + root.Size.Y * 0.5)) - left.height)
			local row = { lf = -ankle.Z }
			for _, side in { "Left", "Right" } do
				local hand = joints[side .. "Hand"] and inRoot(jointAt(side .. "Hand", poses))
				row[side] = hand and -hand.Z or 0
			end
			table.insert(rows, row)
		end
		check(knee * left.pole > 0, "Knees bend against the authored walk: " .. d.id)
		check(lift > left.length * 0.15, "Swing foot barely lifts: " .. d.id)
		local function covariance(a, b)
			local ma, mb = 0, 0
			for _, row in rows do
				ma += row[a] / #rows
				mb += row[b] / #rows
			end
			local value = 0
			for _, row in rows do
				value += (row[a] - ma) * (row[b] - mb) / #rows
			end
			return value
		end
		output[d.id] = {
			strideLength = math.floor(state.strideLength * 100 + 0.5) / 100,
			reach = math.floor(left.reach * 100 + 0.5) / 100,
			legLength = math.floor(left.length * 100 + 0.5) / 100,
			drop = math.floor(state.drop * 100 + 0.5) / 100,
			loopsPerSecond = math.floor(d.speed / state.strideLength * 100 + 0.5) / 100,
			kneePole = left.pole,
			maxStanceSlip = slip,
			maxGroundError = ground,
			swingLift = math.floor(lift * 100 + 0.5) / 100,
			-- Positive: the right hand swings forward with the left foot (natural); negative: same side.
			oppositeHand = covariance("lf", "Right"),
			sameHand = covariance("lf", "Left"),
		}
		npc:Destroy()
	end
	return { checks = checks, rigs = output }
end
