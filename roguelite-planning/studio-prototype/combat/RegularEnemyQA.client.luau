-- Execute only in the real Studio client while RegularEnemyQA is running.
local Run = game:GetService("RunService")
assert(Run:IsStudio(), "QA is Studio-only")
local stage = workspace:WaitForChild("RegularEnemyQA", 15)
assert(stage, "Start server harness first")
local output = Instance.new("StringValue")
output.Name = "ClientResults"
output.Parent = stage
local records = {}
local previous = {}
local elapsed = 0
local connection
connection = Run.RenderStepped:Connect(function(dt)
	if not stage.Parent then
		connection:Disconnect()
		return
	end
	elapsed += dt
	if elapsed < 0.05 then
		return
	end
	elapsed = 0
	for _, npc in stage:GetChildren() do
		if npc:IsA("Model") and npc:GetAttribute("RegularEnemyQA") then
			local id = npc:GetAttribute("EnemyId")
			local r = records[id]
				or { id = id, states = {}, maxPoseChange = 0, movePoseChanges = 0, groundedSamples = 0, maxMeasuredSpeed = 0 }
			records[id] = r
			local mode = npc:GetAttribute("ClientMotionState")
			if mode then
				r.states[mode] = true
			end
			local speed = npc:GetAttribute("ClientMeasuredSpeed") or 0
			r.maxMeasuredSpeed = math.max(r.maxMeasuredSpeed, speed)
			local h = npc:FindFirstChildOfClass("Humanoid")
			if h and h.FloorMaterial ~= Enum.Material.Air then
				r.groundedSamples += 1
			end
			local poses = {}
			for _, joint in npc:GetDescendants() do
				if joint:IsA("Bone") or joint:IsA("Motor6D") then
					local pose = joint.Transform
					poses[joint] = pose
					local prior = previous[npc] and previous[npc][joint]
					if prior then
						local delta = (pose.Position - prior.Position).Magnitude
							+ (pose.LookVector - prior.LookVector).Magnitude
							+ (pose.UpVector - prior.UpVector).Magnitude
						r.maxPoseChange = math.max(r.maxPoseChange, delta)
						if mode == "Move" and delta > 0.0005 then
							r.movePoseChanges += 1
						end
					end
				end
			end
			previous[npc] = poses
			if stage:GetAttribute("Phase") == "IdleAfterMove" and mode == "Idle" then
				r.stoppedToIdle = true
			end
			if r.states.Attack and mode ~= "Attack" then
				r.recoveredFromAttack = true
			end
		end
	end
	if stage:GetAttribute("Phase") == "Complete" then
		output.Value = game:GetService("HttpService"):JSONEncode(records)
		connection:Disconnect()
	end
end)
return "Client motion evidence collection started"
