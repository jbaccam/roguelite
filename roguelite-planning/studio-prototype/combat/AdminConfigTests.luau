-- AdminConfig checks: who is a developer, the test-run guard and every request rule.
-- Run in Studio Edit (plan D, Task 1). The markTestRun checks briefly add a temporary
-- ReplicatedStorage.RogueliteRunState (and set aside a real one) and restore Studio afterwards;
-- the "run not marked" warning in the output is expected.
return function(Admin, Enemies, Items)
	local RS = game:GetService("ReplicatedStorage")
	local MAX_SHARDS = require(RS.RogueliteCombat.EconomyConfig).MAX_SHARDS
	local MAX_LEVEL = require(RS.RogueliteCombat.RunXP).MAX_LEVEL
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
	check(table.isfrozen(Admin.UserIds), "The developer list is frozen")
	check(not pcall(table.insert, Admin.UserIds, 1), "Nothing can add a developer at runtime")
	-- The test-run guard reads RogueliteRunState.AdminTestRun.
	local run = Instance.new("Folder")
	check(not Admin.isTestRun(run), "A fresh run is not a test run")
	run:SetAttribute("AdminTestRun", true)
	check(Admin.isTestRun(run), "The flag marks a test run")
	run:SetAttribute("AdminTestRun", false)
	check(not Admin.isTestRun(run), "Only true counts")
	run:Destroy()
	-- markTestRun and isTestRun() with no argument use ReplicatedStorage.RogueliteRunState.
	-- Set any real folder aside first, and put everything back before asserting.
	local real = RS:FindFirstChild("RogueliteRunState")
	if real then
		real.Parent = nil
	end
	local noFolderIsTest = Admin.isTestRun()
	local noFolderMark = Admin.markTestRun()
	local madeFolder = RS:FindFirstChild("RogueliteRunState") ~= nil
	local temp = Instance.new("Folder")
	temp.Name = "RogueliteRunState"
	temp.Parent = RS
	local firstMark = Admin.markTestRun()
	local secondMark = Admin.markTestRun()
	local flagValue = temp:GetAttribute("AdminTestRun")
	local folderIsTest = Admin.isTestRun()
	temp:Destroy()
	if real then
		real.Parent = RS
	end
	check(noFolderIsTest == false, "isTestRun() is false when there is no run folder")
	check(noFolderMark == false, "markTestRun returns false when the run folder is missing")
	check(not madeFolder, "markTestRun does not create the run folder")
	check(firstMark == true, "markTestRun returns true when it sets the flag")
	check(secondMark == true, "markTestRun returns true when the flag was already set")
	check(flagValue == true, "markTestRun sets AdminTestRun")
	check(folderIsTest == true, "isTestRun() sees the flag on the run folder")
	-- Every action name, in sorted order.
	-- 2026-10-03: the tutorial and turret actions were missing here (15 listed, 19 real); EndlessBoss makes 20.
	local expectedActions = {
		"ClearMobs",
		"EndWave",
		"EndlessBoss",
		"Freeze",
		"GiveItem",
		"God",
		"JumpWave",
		"KeepAlive",
		"Level",
		"Pause",
		"Sandbox",
		"Shards",
		"Spawn",
		"Travel",
		"Turret",
		"TutorialEnd",
		"TutorialLobby",
		"TutorialStart",
		"Waves",
		"Weapons",
	}
	check(#Admin.Actions == 20, "20 admin actions, found " .. #Admin.Actions)
	check(
		table.concat(Admin.Actions, ",") == table.concat(expectedActions, ","),
		"action names: " .. table.concat(Admin.Actions, ",")
	)
	local anEnemy = Enemies.List[1].id
	local boss = Admin.BossId
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
		{ "Spawn", boss, 5 },
		{ "KeepAlive", 10, "" },
		{ "KeepAlive", 0, "" },
		{ "KeepAlive", 100, "crab,snake" },
		{ "ClearMobs" },
		{ "Freeze", true },
		{ "Freeze", false },
		{ "Sandbox" },
		{ "Waves" },
		{ "EndWave" },
		{ "EndlessBoss" },
		{ "Pause", true },
		{ "JumpWave", 1 },
		{ "JumpWave", 20 },
		{ "God", true },
		{ "Weapons", false },
		{ "GiveItem", anItem },
		{ "Shards", "Add", 100 },
		{ "Shards", "Add", -100 },
		{ "Shards", "Add", MAX_SHARDS },
		{ "Shards", "Add", -MAX_SHARDS },
		{ "Shards", "Set", 0 },
		{ "Shards", "Set", MAX_SHARDS },
		{ "Level", "Add", 1 },
		{ "Level", "Add", 100 },
		{ "Level", "Set", 10 },
		{ "Level", "Set", MAX_LEVEL },
		-- Turrets (turret items, 2026-10-04): Give 1-4 or Clear.
		{ "Turret", "Give", 1 },
		{ "Turret", "Give", 4 },
		{ "Turret", "Clear" },
	}
	for _, call in valid do
		check(Admin.check(call[1], call[2], call[3]), "should pass: " .. show(call))
	end
	local invalid = {
		-- Action names
		{ nil },
		{ 5 },
		{ {} },
		{ workspace },
		{ true },
		{ "Explode" },
		{ "travel", "Lobby" },
		-- Travel
		{ "Travel", "DesertBasin" },
		{ "Travel" },
		{ "Travel", { "Lobby" } },
		{ "Travel", "Lobby", 1 },
		-- Spawn
		{ "Spawn", "dragon", 5 },
		{ "Spawn", workspace, 5 },
		{ "Spawn", anEnemy, 0 },
		{ "Spawn", anEnemy, 51 },
		{ "Spawn", anEnemy, 2.5 },
		{ "Spawn", anEnemy, 0 / 0 },
		{ "Spawn", anEnemy, "5" },
		{ "Spawn", anEnemy, Vector3.zero },
		{ "Spawn", boss, 6 },
		{ "Spawn", boss, 0 },
		-- KeepAlive
		{ "KeepAlive", 101, "" },
		{ "KeepAlive", -1, "" },
		{ "KeepAlive", 0 / 0, "" },
		{ "KeepAlive", 5, "crab,dragon" },
		{ "KeepAlive", 5 },
		{ "KeepAlive", 5, {} },
		{ "KeepAlive", 5, string.rep("crab,", 130) },
		-- Actions that take no argument, or one flag
		{ "ClearMobs", true },
		{ "ClearMobs", nil, 1 },
		{ "Freeze", "yes" },
		{ "Freeze" },
		{ "Sandbox", 1 },
		{ "Waves", 1 },
		{ "EndWave", true },
		{ "EndlessBoss", "Dragon" },
		{ "EndlessBoss", nil, 1 },
		{ "Pause", 1 },
		{ "God", 1 },
		{ "God", true, 1 },
		{ "Weapons", "on" },
		-- JumpWave
		{ "JumpWave", 0 },
		{ "JumpWave", 21 },
		{ "JumpWave", 1.5 },
		{ "JumpWave", math.huge },
		{ "JumpWave", -math.huge },
		-- GiveItem
		{ "GiveItem", "weapon_01_1" },
		{ "GiveItem", "nope" },
		{ "GiveItem", {} },
		{ "GiveItem", anItem, 1 },
		-- Shards
		{ "Shards", "Add", 1e7 },
		{ "Shards", "Add", MAX_SHARDS + 1 },
		{ "Shards", "Add", -MAX_SHARDS - 1 },
		{ "Shards", "Add", -math.huge },
		{ "Shards", "Set", -1 },
		{ "Shards", "Set", MAX_SHARDS + 1 },
		{ "Shards", "Set", 1e300 },
		{ "Shards", "Set", 0 / 0 },
		{ "Shards", "Set", 1.5 },
		{ "Shards", "Give", 5 },
		{ "Shards", {}, 5 },
		-- Level
		{ "Level", "Add", 0 },
		{ "Level", "Add", 101 },
		{ "Level", "Add", "1" },
		{ "Level", "Set", 0 },
		{ "Level", "Set", MAX_LEVEL + 1 },
		{ "Level", "Set", 0 / 0 },
		-- Turrets: the old Give-without-tier, Tier and Break are gone.
		{ "Turret", "Give" },
		{ "Turret", "Give", 0 },
		{ "Turret", "Give", 5 },
		{ "Turret", "Give", 1.5 },
		{ "Turret", "Give", "1" },
		{ "Turret", "Tier", 2 },
		{ "Turret", "Break" },
		{ "Turret", "Clear", 1 },
	}
	for _, call in invalid do
		check(not Admin.check(call[1], call[2], call[3]), "should fail: " .. show(call))
	end
	return { passed = checks }
end
