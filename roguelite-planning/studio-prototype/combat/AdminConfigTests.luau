-- AdminConfig checks: who is a developer, the test-run guard and every request rule.
-- Run in Studio Edit (plan D, Task 1).
return function(Admin, Enemies, Items)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local function show(call)
		return tostring(call[1]) .. " " .. tostring(call[2]) .. " " .. tostring(call[3])
	end
	-- Who is a developer: a real Player whose UserId is listed.
	check(Admin.isAdminId(341854066), "EggaRowls is a developer")
	check(not Admin.isAdminId(1) and not Admin.isAdminId(-1) and not Admin.isAdminId(0), "Other ids are not developers")
	check(not Admin.isAdminId("341854066") and not Admin.isAdminId(nil), "Ids must be numbers")
	check(
		not Admin.isAdmin(nil) and not Admin.isAdmin({ UserId = 341854066 }) and not Admin.isAdmin(workspace),
		"Only real Player instances pass"
	)
	-- The test-run guard reads RogueliteRunState.AdminTestRun.
	local run = Instance.new("Folder")
	check(not Admin.isTestRun(run), "A fresh run is not a test run")
	run:SetAttribute("AdminTestRun", true)
	check(Admin.isTestRun(run), "The flag marks a test run")
	run:SetAttribute("AdminTestRun", false)
	check(not Admin.isTestRun(run), "Only true counts")
	run:Destroy()
	check(#Admin.Actions == 15, "15 admin actions, found " .. #Admin.Actions)
	local anEnemy = Enemies.List[1].id
	local anItem
	for _, entry in Items.List do
		if entry.kind ~= "Weapon" then
			anItem = entry.id
			break
		end
	end
	local valid = {
		{ "Travel", "Lobby" },
		{ "Travel", "PineValley" },
		{ "Travel", "BeachCove" },
		{ "Spawn", anEnemy, 5 },
		{ "Spawn", "Hammer", 1 },
		{ "Spawn", anEnemy, 50 },
		{ "KeepAlive", 10, "" },
		{ "KeepAlive", 0, "" },
		{ "KeepAlive", 100, "crab,snake" },
		{ "ClearMobs" },
		{ "Freeze", true },
		{ "Freeze", false },
		{ "Sandbox" },
		{ "Waves" },
		{ "EndWave" },
		{ "Pause", true },
		{ "JumpWave", 1 },
		{ "JumpWave", 20 },
		{ "God", true },
		{ "Weapons", false },
		{ "GiveItem", anItem },
		{ "Shards", "Add", 100 },
		{ "Shards", "Add", -100 },
		{ "Shards", "Set", 0 },
		{ "Level", "Add", 1 },
		{ "Level", "Set", 10 },
	}
	for _, call in valid do
		check(Admin.check(call[1], call[2], call[3]), "should pass: " .. show(call))
	end
	local invalid = {
		{ nil },
		{ 5 },
		{ "Explode" },
		{ "Travel", "DesertBasin" },
		{ "Travel" },
		{ "Travel", { "Lobby" } },
		{ "Spawn", "dragon", 5 },
		{ "Spawn", anEnemy, 0 },
		{ "Spawn", anEnemy, 51 },
		{ "Spawn", anEnemy, 2.5 },
		{ "Spawn", anEnemy, 0 / 0 },
		{ "KeepAlive", 101, "" },
		{ "KeepAlive", -1, "" },
		{ "KeepAlive", 5, "crab,dragon" },
		{ "KeepAlive", 5 },
		{ "KeepAlive", 5, string.rep("crab,", 130) },
		{ "ClearMobs", true },
		{ "Freeze", "yes" },
		{ "Freeze" },
		{ "Sandbox", 1 },
		{ "JumpWave", 0 },
		{ "JumpWave", 21 },
		{ "JumpWave", math.huge },
		{ "Pause", 1 },
		{ "God", 1 },
		{ "GiveItem", "weapon_01_1" },
		{ "GiveItem", "nope" },
		{ "Shards", "Add", 1e7 },
		{ "Shards", "Set", -1 },
		{ "Shards", "Give", 5 },
		{ "Shards", "Set", 1.5 },
		{ "Level", "Add", 0 },
		{ "Level", "Set", 0 },
		{ "Level", "Set", 1001 },
		{ "Level", "Add", "1" },
	}
	for _, call in invalid do
		check(not Admin.check(call[1], call[2], call[3]), "should fail: " .. show(call))
	end
	return { passed = checks }
end
