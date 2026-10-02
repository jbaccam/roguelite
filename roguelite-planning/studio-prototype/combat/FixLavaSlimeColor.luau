-- Edit-time fix (2026-10-01): every mesh of the assembled lava slime template takes the authored
-- atlas, as InstallRegularEnemyTemplates now does (its ATLAS_OVERRIDES note explains the yellow
-- import). Safe to re-run.
assert(not game:GetService("RunService"):IsRunning(), "Run in Edit mode")
local ATLAS = "rbxassetid://100144175087527"
local npc = game.ServerStorage.RogueliteNPCs.LavaSlime_NPC
local changed = 0
for _, part in npc:GetDescendants() do
	local surface = part:IsA("MeshPart") and part:FindFirstChildOfClass("SurfaceAppearance")
	if part:IsA("MeshPart") and (surface or part.TextureID ~= ATLAS) then
		if surface then
			surface:Destroy()
		end
		part.TextureID = ATLAS
		changed += 1
	end
end
return changed .. " lava slime meshes moved to the authored atlas"
