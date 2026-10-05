-- Temporary client fixture: runs actual frame-driven production renderers in the viewer.
-- Source only; never included in Rojo. No input simulation, remotes, rewards or persistence.
local Tests = {}
local cases = {
	{ "11", 1, "Base", { "RPGCloudTrail", "SmokeCloud", "CloudLobe" } },
	{ "08", 1, "Base", { "FlyingPoison", "PoisonPuff", "PoisonZone", "SoftPoison" } },
	{ "15", 1, "Base", { "PreviewChicken" } },
	{ "28", 4, "Base", { "VacuumFunnel", "CurvedWind", "InwardMote" } },
	{ "29", 4, "Base", { "WaterStream", "WaterJet", "SplashDroplet" } },
	{ "17", 4, "Base", { "ContinuousFlame" } },
	{ "18", 4, "Flush", { "RoyalCard", "LegendaryHeadline" } },
	{ "22", 4, "Strike", { "23", "LegendaryHeadline" } },
	{ "15", 4, "Hatch", { "PreviewChicken" } },
	{ "38", 4, "Base", { "StormArrow" } },
	{ "39", 4, "Base", { "FlyingDaggerL", "FlyingDaggerR" } },
	{ "36", 4, "Wraith", { "WraithSmoke", "WraithEmbers" } },
	{ "37", 4, "Throw", { "WaveColumn", "WaveCrest" } },
	{ "41", 4, "Burst", { "RayBolt", "GodlyBurst" } },
}
function Tests.run(first, last)
	assert(game:GetService("RunService"):IsClient(), "Client only")
	local UI = require(game.ReplicatedStorage.WeaponShowcaseUI)
	local results = {}
	for index = first or 1, last or #cases do
		local case = cases[index]
		local names, active = {}, {}
		UI.open(game.Players.LocalPlayer, case[1], case[2], { variant = case[3] })
		local folder = assert(workspace:FindFirstChild("WeaponShowcaseLocal"))
		local function added(x)
			names[x.Name] = true
		end
		for _, x in folder:GetDescendants() do
			added(x)
		end
		local connection = folder.DescendantAdded:Connect(added)
		local started = os.clock()
		local complete = false
		repeat
			task.wait(0.05)
			assert(UI.isOpen(), "Viewer unexpectedly closed")
			for _, x in folder:GetDescendants() do
				if x:IsA("ParticleEmitter") and x.Enabled and x.Rate > 0 then
					active[x.Name] = true
				end
				if x:IsA("Beam") and x.Enabled and x.Transparency.Keypoints[1].Value < 1 then
					active[x.Name] = true
				end
				if x:IsA("BillboardGui") and x.Name == "AttackHeadline" and x.Enabled then
					local limit = x:FindFirstChildWhichIsA("UITextSizeConstraint", true)
					local viewport = workspace.CurrentCamera.ViewportSize
					local cap = 48 * math.clamp(math.min(viewport.X, viewport.Y) / 900, 0.25, 1.35)
					assert(
						x.Size.Y.Scale == 0 and limit and limit.MaxTextSize <= cap,
						"Special headline text stays capped"
					)
					active[x.Name] = true
				end
			end
			complete = true
			for _, name in case[4] do
				if not names[name] then
					complete = false
				end
			end
			if case[1] == "28" then
				complete = complete and active.CurvedWind == true
			end
			if case[1] == "17" then
				complete = complete and active.ContinuousFlame == true
			end
			if case[1] == "18" then
				complete = complete and active.LegendaryHaze == true and active.AttackHeadline == true
			end
			if case[1] == "22" then
				complete = complete and active.AttackHeadline == true
			end
		until complete or os.clock() - started > 11
		connection:Disconnect()
		local missing = {}
		for _, name in case[4] do
			if not names[name] then
				table.insert(missing, name)
			end
		end
		table.insert(
			results,
			{ id = case[1], variant = case[3], passed = complete, missing = missing, active = active, seconds = os.clock()
				- started }
		)
		UI.close(true)
		task.wait()
		assert(not workspace:FindFirstChild("WeaponShowcaseLocal"), "Viewer geometry cleaned")
	end
	return results
end
return Tests
