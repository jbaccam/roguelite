-- Read-only data checks; optional client stage smoke explicitly owns/destroys its local theatre.
-- Root Studio runner loads this test source; it need not be shipped in the production overlay.
local Tests = {}
function Tests.run(Catalog, Data)
	local n = 0
	local function check(ok, reason)
		assert(ok, reason)
		n += 1
	end
	local recipes = Data.build(Catalog)
	check(#recipes.List == 42, "Exactly 42 reviewed weapons")
	local modes = {
		melee = true,
		bullet = true,
		poison = true,
		shirt = true,
		rocket = true,
		throw = true,
		fire = true,
		cards = true,
		yo = true,
		ball = true,
		vacuum = true,
		water = true,
		pandora = true,
		lightning = true,
		rain = true,
		chain = true,
		ray = true,
		legendary = true,
		hatch = true,
		wraith = true,
		wisp = true,
		burst = true,
	}
	for _, w in Catalog.List do
		local e = recipes.ById[w.id]
		check(e and e.id == w.id, "Every catalog ID has a recipe")
		check(e.name == w.name and modes[e.mode], "Real name and supported mode " .. w.id)
		for tier = 1, 4 do
			local variants = Data.variants(e, tier)
			check(#variants > 0 and variants[1].key == "Base", "Base is available at every tier " .. w.id)
			local seen = {}
			for _, v in variants do
				check(
					not seen[v.key] and modes[v.mode] and type(v.condition) == "string" and #v.condition > 0,
					"Unique supported described variant " .. w.id .. "/" .. v.key
				)
				seen[v.key] = true
				check(not v.minTier or tier >= v.minTier, "No Tier IV move at a lower tier")
			end
			local legendary = Catalog.Legendary[w.id]
			if legendary then
				check((seen[legendary.move] == true) == (tier == 4), "Legendary tier gate " .. w.id)
			end
			check(Data.variant(e, "invalid", tier).key == "Base", "Invalid variant falls back safely")
		end
	end
	for _, pair in
		{
			{ "15", "Hatch" },
			{ "31", "Throw" },
			{ "36", "Wraith" },
			{ "36", "BigWraith" },
			{ "37", "Throw" },
			{
				"40",
				"Wisp",
			},
			{
				"41",
				"Burst",
			},
		}
	do
		check(Data.variant(recipes.ById[pair[1]], pair[2], 1).key == pair[2], "Special trigger covered " .. pair[1])
	end
	return { passed = n, weapons = #recipes.List }
end
function Tests.stage(Stage, Catalog, Data, first, last)
	assert(game:GetService("RunService"):IsClient(), "Stage smoke is client-only")
	local recipes = Data.build(Catalog)
	local stage = Stage.new()
	stage.autoplay = false
	local camera = workspace.CurrentCamera
	local oldType, oldFrame, oldFov = camera.CameraType, camera.CFrame, camera.FieldOfView
	local frame, fov = stage:camera()
	camera.CameraType = Enum.CameraType.Scriptable
	camera.CFrame = frame
	camera.FieldOfView = fov
	local checked = 0
	local errors = {}
	local maximum = 0
	for i = first or 1, last or #Catalog.List do
		local w = Catalog.List[i]
		for _, tier in { 1, 4 } do
			for _, v in Data.variants(recipes.ById[w.id], tier) do
				local ok, err = pcall(function()
					stage:select(w.id, tier, v.key)
					local started = os.clock()
					repeat
						task.wait()
					until stage.assetsReady or os.clock() - started > 5
					assert(stage.assetsReady, "Preview assets released for playback")
					assert(stage.visual and stage.visual.model.Parent, "Actual template cloned")
					local view, lens = stage:camera()
					camera.CFrame = view
					camera.FieldOfView = lens
					local size = camera.ViewportSize
					local rect = stage.viewportRect or { left = 0.055, right = 0.945, top = 0.14, bottom = 0.76 }
					for _, point in
						{ stage.root.Position, stage.visual.model:GetPivot().Position, stage.dummies[stage.primaryIndex].root.Position }
					do
						local screen, visible = camera:WorldToViewportPoint(point)
						assert(
							visible
								and screen.X / size.X > rect.left
								and screen.X / size.X < rect.right
								and screen.Y / size.Y > rect.top
								and screen.Y / size.Y < rect.bottom,
							"Avatar, weapon and targets inside visible stage"
						)
					end
					assert(stage.presenter.model.Name == "PlayerAvatar", "Real avatar scene")
					if w.id == "00" or w.id == "07" or w.id == "24" or w.id == "30" then
						assert(stage.targetCount == 1 and #stage.visualTargets == 1, "Aimed gun has exactly one target")
						assert(stage.dummies[1].visible and stage.aim == stage.dummies[1].root.Position, "Lone target is actually aimed at")
					end
					for index, d in stage.dummies do
						assert(d.target:IsA("MeshPart"), "Reviewed lobby dummy mesh")
						if index <= stage.targetCount then
							assert(
								(Vector3.new(d.root.Position.X, 0, d.root.Position.Z) - Vector3.new(
									stage.root.Position.X,
									0,
									stage.root.Position.Z
								)).Magnitude > 5,
								"Clear avatar-to-target spacing"
							)
						end
					end
					for _ = 1, 115 do
						stage:step(0.1)
						maximum = math.max(maximum, #stage.movers)
					end
					assert(#stage.movers <= 40, "Bounded mover budget")
					for _, x in stage.folder:GetDescendants() do
						assert(
							not x:IsA("LuaSourceContainer")
								and not x:IsA("RemoteEvent")
								and (
									not x:IsA("Humanoid")
									or x:IsDescendantOf(stage.presenter.model) and not x.EvaluateStateMachine
								),
							"Presentation-only instances"
						)
						if x:IsA("BasePart") then
							assert(x.Anchored and not x.CanCollide and not x.CanTouch, "Local cosmetic geometry")
						end
					end
				end)
				checked += 1
				if not ok then
					table.insert(errors, w.id .. " T" .. tier .. " " .. v.key .. ": " .. tostring(err))
				end
				task.wait() -- let cancelled production VFX jobs retire before the next take
			end
		end
	end
	stage:destroy()
	stage:destroy()
	stage:step(0.1)
	assert(
		stage.folder.Parent == nil and #stage.events == 0 and #stage.movers == 0,
		"Close is idempotent; no owned scene/jobs remain"
	)
	camera.CameraType = oldType
	camera.CFrame = oldFrame
	camera.FieldOfView = oldFov
	return { checked = checked, errors = errors, maxMovers = maximum, cleaned = true }
end
-- Actual Stage scheduler + renderers, with a deterministic simulation clock. This checks
-- cadence/ownership/bounds; use LiveEffectsTests for real-time particle appearance.
function Tests.cadence(Stage)
	assert(game:GetService("RunService"):IsClient(), "Cadence regression is client-only")
	local Catalog = require(game.ReplicatedStorage.RogueliteCombat.WeaponCatalog)
	local Motion = require(game.ReplicatedStorage.RogueliteCombat.WeaponMotion)
	local Stats = require(game.ReplicatedStorage.RogueliteCombat.CharacterStats)
	local baseline = {}
	for _, stat in Stats.List do
		baseline[stat.id] = stat.base
	end
	local stage = Stage.new()
	local results, n = {}, 0
	local function check(ok, why)
		assert(ok, why)
		n += 1
	end
	local ok, err = xpcall(function()
		for _, id in { "28", "29" } do
			for tier = 1, 4 do
				local weapon = Stats.weapon(Catalog.ById[id], baseline, "", tier)
				local _, _, duration = Motion.attackTiming(id, weapon.kind)
				local interval = math.max(weapon.cooldown, duration / weapon.motionRate)
				check(
					math.min(1.5, weapon.cooldown + 0.12) > interval + 0.02,
					"Channel covers attack and animation cadence at every tier: " .. id .. "/" .. tier
				)
			end
		end
		for _, case in
			{
				{ "30", 1, "Base", 9 },
				{ "07", 4, "Base", 5 },
				{ "19", 4, "Base", 5 },
				{ "12", 4, "Base", 12 },
				{ "18", 4, "Flush", 12 },
				{ "11", 4, "Split", 15 },
				{ "28", 4, "Base", 7 },
				{ "29", 4, "Base", 5 },
				{ "17", 4, "Base", 5 },
				{ "14", 4, "Base", 16 },
				{ "08", 4, "Base", 14 },
				{ "15", 4, "Hatch", 18 },
				{ "36", 4, "Wraith", 16 },
				{ "41", 4, "Burst", 9 },
			}
		do
			stage.autoplay = true
			stage:select(case[1], case[2], case[3])
			local started = os.clock()
			repeat
				task.wait()
			until stage.assetsReady or os.clock() - started > 5
			check(stage.assetsReady, "Assets ready " .. case[1])
			local take, model, muzzle = stage.take, stage.visual.model, stage.muzzle
			local times, previous, gapMax = {}, 0, 0
			local funnel, resets = nil, 0
			local lastOpacity = 0
			for frame = 1, math.ceil(case[4] / 0.02) do
				stage:step(0.02)
				if stage.serial ~= previous then
					check(stage.serial == previous + 1, "One attack per trigger, no catch-up burst")
					if #times > 0 then
						local gap = stage.clock - times[#times]
						local _, _, motion = Motion.attackTiming(stage.id, stage.attackKind, stage.style)
						local expected = math.max(stage.weapon.cooldown, motion / stage.weapon.motionRate)
						check(gap >= expected - 0.0001, "Never faster than production cadence " .. case[1])
						if case[1] ~= "12" then
							check(gap <= expected + 0.0201, "No arbitrary silence between attacks " .. case[1])
						end
						gapMax = math.max(gapMax, gap)
					end
					table.insert(times, stage.clock)
					previous = stage.serial
				end
				check(
					stage.take == take and stage.visual.model == model and stage.muzzle == muzzle and stage.assetsReady,
					"Loop keeps take, assets and render adapters mounted"
				)
				check(
					#stage.movers <= 40 and #stage.zoneKeys <= 3 and stage.chickenCount <= 3,
					"Persistent playback remains bounded"
				)
				if case[1] == "36" then
					check(#stage.wraithKeys <= Catalog.Godly["36"].ghostCap[case[2]], "Live wraith cap")
				end
				if stage.variant.mode == "legendary" then
					local every = Catalog.Legendary[stage.id].every or 1
					check(
						stage.slot:GetAttribute("LegendaryCharge") == stage.serial % every,
						"Special fires exactly on catalog prerequisite count"
					)
				end
				if case[1] == "28" and stage.serial > 0 then
					check(stage.streamMode == "vacuum", "Vacuum channel has no forced two-second break")
					local current = stage.fx:FindFirstChild("VacuumFunnel")
					if current then
						funnel = funnel or current
						check(current == funnel, "One pooled vacuum persists across resets")
					end
					local opacity = stage.dummies[2].target.LocalTransparencyModifier
					if opacity < lastOpacity and lastOpacity > 0.8 then
						resets += 1
					end
					lastOpacity = opacity
				end
				if frame % 60 == 0 then
					task.wait()
				end
			end
			check(#times >= 3, "Multiple live-speed attacks observed " .. case[1])
			if case[1] == "28" then
				check(funnel ~= nil and resets >= 2, "Vacuum replenishes dummies while suction continues")
			end
			local beforeStop = stage.serial
			stage.autoplay = false
			local allowance = stage.demoRemaining
			for _ = 1, 700 do
				stage:step(0.02)
			end
			check(
				stage.serial == beforeStop + allowance and stage.demoRemaining == 0,
				"Loop OFF finishes one demonstration and stops"
			)
			check(stage.streamMode == nil and not stage.returning, "Loop OFF releases channels and returning throws")
			local stopped = stage.serial
			for _ = 1, 100 do
				stage:step(0.02)
			end
			check(stage.serial == stopped, "No hidden repeat after stopping")
			stage.autoplay = true
			stage:step(0.02)
			check(stage.serial == stopped + 1 and stage.take == take, "Loop ON resumes one attack without rebuilding")
			table.insert(results, { id = case[1], variant = case[3], attacks = #times, maxGap = gapMax })
		end
		-- Starting with Loop OFF still shows a full charged special once, then stops.
		stage.autoplay = false
		stage:select("18", 4, "Flush")
		local started = os.clock()
		repeat
			task.wait()
		until stage.assetsReady or os.clock() - started > 5
		for _ = 1, 650 do
			stage:step(0.02)
		end
		check(
			stage.serial == Catalog.Legendary["18"].every and stage.completedDemos == 1,
			"One-shot special includes real-speed prerequisites"
		)
	end, debug.traceback)
	stage:destroy()
	assert(ok, err)
	return { passed = n, cases = results, cleaned = true }
end
return Tests
