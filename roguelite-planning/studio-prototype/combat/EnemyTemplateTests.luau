-- Edit-time checks on the assembled enemy templates (ServerStorage.RogueliteNPCs). Changes nothing.
-- A Humanoid scales its walking force by its model's GetScale(). The imported mobs and map bosses
-- were built from raw imports at ScaleTo(0.01), so they pushed with 1/100th of the force: on a
-- flat floor (2026-10-01) a werewolf at scale 0.01 reached 10 of 16 studs/s after 1.2 s, could
-- not reverse within 1.2 s and took 0.9 s to stop; the same geometry in a scale-1 model reversed
-- in 0.08 s and stopped in 0.05 s, like the zombies.
return function(templates)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	for _, npc in templates:GetChildren() do
		if npc:IsA("Model") and npc:FindFirstChildOfClass("Humanoid") then
			check(math.abs(npc:GetScale() - 1) < 1e-6, npc.Name .. " must be at model scale 1, not " .. npc:GetScale())
			-- Clients scale the clips by GetScale() / EnemyBaselineModelScale; a template is at 1.
			local baseline = npc:GetAttribute("EnemyBaselineModelScale") or 1
			check(math.abs(npc:GetScale() / baseline - 1) < 1e-4, npc.Name .. " clips must play at their authored size")
		end
	end
	check(checks >= 2 * 26, "Expected all 26 enemy templates")
	return checks
end
