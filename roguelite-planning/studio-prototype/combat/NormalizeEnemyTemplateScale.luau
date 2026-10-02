-- Edit-time fix (2026-10-01) for templates assembled before the installers built them at scale 1.
-- Each Humanoid template in ServerStorage.RogueliteNPCs that isn't at model scale 1 moves into a
-- fresh Model, keeping its parts, joints, attributes, tags and pivot; part sizes don't change
-- (EnemyTemplateTests explains why the scale matters). EnemyBaselineModelScale is divided by the
-- old scale, so clients still play the clips at their authored size. The old models are kept in
-- ServerStorage.BeforeTemplateScale_<yyyymmdd>. Templates already at scale 1 are left alone.
assert(not game:GetService("RunService"):IsRunning(), "Run in Edit mode")
local Tags = game:GetService("CollectionService")
local storage = game:GetService("ServerStorage")
local folder = storage.RogueliteNPCs
local backup
local report = {}
for _, old in folder:GetChildren() do
	if old:IsA("Model") and old:FindFirstChildOfClass("Humanoid") and math.abs(old:GetScale() - 1) > 1e-6 then
		if not backup then
			local name = "BeforeTemplateScale_" .. os.date("%Y%m%d")
			backup = storage:FindFirstChild(name) or Instance.new("Folder")
			backup.Name = name
			backup.Parent = storage
		end
		old:Clone().Parent = backup
		local scale = old:GetScale()
		local npc = Instance.new("Model")
		npc.Name = old.Name
		for key, value in old:GetAttributes() do
			if not key:match("^RBX") then
				npc:SetAttribute(key, value)
			end
		end
		npc:SetAttribute("EnemyBaselineModelScale", (old:GetAttribute("EnemyBaselineModelScale") or 1) / scale)
		for _, tag in Tags:GetTags(old) do
			Tags:AddTag(npc, tag)
		end
		local primary, pivot = old.PrimaryPart, old:GetPivot()
		for _, child in old:GetChildren() do
			child.Parent = npc
		end
		npc.WorldPivot = pivot
		npc.PrimaryPart = primary
		npc.ModelStreamingMode = old.ModelStreamingMode
		old:Destroy()
		npc.Parent = folder
		table.insert(report, string.format("%s %.3g -> %.3g", npc.Name, scale, npc:GetScale()))
	end
end
return #report .. " templates moved to scale 1\n" .. table.concat(report, "\n")
