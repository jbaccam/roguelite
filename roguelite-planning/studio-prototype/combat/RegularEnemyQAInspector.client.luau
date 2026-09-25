-- Optional Studio-only visual QA camera. Never mapped into the production project.
local Run = game:GetService("RunService")
assert(Run:IsStudio(), "QA inspector is Studio-only")
local stage = workspace:WaitForChild("RegularEnemyQA", 30)
assert(stage, "Start the isolated QA stage first")
local camera = workspace.CurrentCamera
local old = { type = camera.CameraType, subject = camera.CameraSubject, frame = camera.CFrame }
local key = "RegularEnemyQAInspector"
local function cleanup()
	Run:UnbindFromRenderStep(key)
	camera.CameraType = old.type
	camera.CameraSubject = old.subject
	camera.CFrame = old.frame
end
stage.AncestryChanged:Connect(function()
	if not stage.Parent then
		cleanup()
	end
end)
Run:BindToRenderStep(key, Enum.RenderPriority.Camera.Value + 100, function()
	local id = stage:GetAttribute("ActiveEnemy")
	local npc = id and stage:FindFirstChild(id)
	local root = npc and npc:FindFirstChild("HumanoidRootPart")
	if not root then
		return
	end
	local offset = stage:GetAttribute("CameraOffset") or Vector3.new(11, 4, 10)
	local focus = root.Position + Vector3.new(0, stage:GetAttribute("CameraFocusHeight") or 0.5, 0)
	camera.CameraType = Enum.CameraType.Scriptable
	camera.CFrame = CFrame.lookAt(focus + offset, focus)
end)
