-- Asset loading, so windows, scroll lists and the run-setup backdrop never pop in.
-- Started once from the lobby HUD entry script, and from the arena HUD on match servers (which
-- never run the lobby HUD); never blocks either HUD. The loading screen stays up until this is
-- ready (PlayerGui attribute AssetWarmReady), capped, so the first menu a player opens is whole.
--   1. Every UI image named in the shared UI/catalog modules is requested and then kept
--      resident by a tiny, nearly transparent label. Destroying preload labels lets the engine
--      drop the texture again, which is what made icons appear late while scrolling.
--   2. The map-select islands and the Armory hall are cloned, parked in the camera for good, and
--      (while the loading screen still covers everything) each is looked at once, so the
--      renderer has their meshes and textures before PLAY or ARMORY is pressed.
--   3. Weapon, pet and armor models are fetched last (Armory showcase, pet and weapon previews).
local RS = game:GetService("ReplicatedStorage")
local ReplicatedFirst = game:GetService("ReplicatedFirst")
local ContentProvider = game:GetService("ContentProvider")
local RunService = game:GetService("RunService")
local P = {}

-- Modules whose exported tables name UI images, most visible first (lobby frame, then icons).
-- A path starting with "@ReplicatedFirst" looks there instead of ReplicatedStorage.
local SOURCES = {
	{ "UITheme" },
	{ "RogueliteUI" },
	{ "WeaponInventoryUI" },
	{ "RogueliteCombat", "ArmorCatalog" },
	{ "RogueliteCombat", "PetConfig" },
	{ "StoreFX" },
	{ "ChestFX" },
	{ "RogueliteCombat", "ShopCatalog" },
	{ "RogueliteCombat", "LevelUpCatalog" },
	{ "RogueliteCombat", "ChestConfig" },
	{ "RogueliteCombat", "EggConfig" },
	{ "RogueliteCombat", "MonetizationConfig" },
	{ "RogueliteCombat", "SkillTreeConfig" },
	{ "RogueliteCombat", "QuestConfig" },
	{ "StatPlates" },
	{ "ItemCardUI" },
	{ "@ReplicatedFirst", "LoadingScreenUI" }, -- trip art, shown the moment a teleport starts
}

-- Match servers do not display these lobby-only screens. Keep combat/shop and
-- monetization images (revive/reroll UI) in both roles.
local LOBBY_ONLY = {
	StoreFX = true,
	ChestFX = true,
	ChestConfig = true,
	EggConfig = true,
	SkillTreeConfig = true,
	QuestConfig = true,
}

-- Model folders whose meshes and textures are fetched after the images, per role.
local MODELS = {
	{ path = { "RogueliteCombat", "WeaponTemplates" } },
	{ path = { "PetModels" } },
	{ path = { "ArmorSets" }, lobbyOnly = true },
}

local WARM_HOLD = 0.15 -- seconds the camera rests on each warm-up shot
local CHARACTER_WAIT = 20

local started = false

local function find(path)
	local node = RS
	for i, name in path do
		if i == 1 and name == "@ReplicatedFirst" then
			node = ReplicatedFirst
		else
			node = node and node:FindFirstChild(name)
		end
	end
	return node
end

-- Every rbxassetid string reachable from the modules' exported tables, in source order.
function P.collect(role)
	role = role or RS:GetAttribute("ServerRole")
	local seen, list = {}, {}
	local function walk(t, depth, visited)
		if depth > 4 or visited[t] then
			return
		end
		visited[t] = true
		for _, v in t do
			if type(v) == "string" and (string.find(v, "^rbxassetid://%d+$") or string.find(v, "^rbxthumb://")) then
				if not seen[v] then
					seen[v] = true
					table.insert(list, v)
				end
			elseif type(v) == "table" then
				walk(v, depth + 1, visited)
			end
		end
	end
	for _, path in SOURCES do
		if role == "Match" and LOBBY_ONLY[path[#path]] then
			continue
		end
		local node = find(path)
		if node and node:IsA("ModuleScript") then
			local ok, t = pcall(require, node)
			if ok and type(t) == "table" then
				walk(t, 0, {})
			end
		end
	end
	return list
end

local function warmImages(player, gui)
	local ids = P.collect()
	local T = require(RS:WaitForChild("UITheme"))
	table.insert(ids, 1, T.headshotId(player.UserId)) -- profile chip, Profile and Party windows
	local cache = Instance.new("ScreenGui")
	cache.Name = "AssetWarmCache"
	cache.ResetOnSpawn = false
	cache.IgnoreGuiInset = true
	cache.DisplayOrder = -100
	local labels = {}
	for _, id in ids do
		local l = Instance.new("ImageLabel")
		l.BackgroundTransparency = 1
		l.BorderSizePixel = 0
		l.Size = UDim2.fromOffset(1, 1)
		l.Image = id
		l.ImageTransparency = 0.995 -- still drawn (so it stays resident) but invisible
		l.Interactable = false
		l.Parent = cache
		table.insert(labels, l)
	end
	cache.Parent = gui
	gui:SetAttribute("AssetWarmTotal", #labels)
	local done = 0
	pcall(ContentProvider.PreloadAsync, ContentProvider, labels, function()
		done += 1
		gui:SetAttribute("AssetWarmLoaded", done)
	end)
	cache:SetAttribute("Images", #ids)
end

-- Fetch the islands and the hall, clone them into the camera, and return their warm-up shots.
local function prepareStages()
	local views = {}
	local islands = RS:WaitForChild("MapSelectIslands", 15)
	if islands then
		pcall(ContentProvider.PreloadAsync, ContentProvider, { islands })
		local Rules = require(RS:WaitForChild("RunSetupRules"))
		local Backdrop = require(RS:WaitForChild("MapSelectBackdrop"))
		if Backdrop.Prepare(Rules.Maps) then
			for _, v in Backdrop.WarmViews() do
				table.insert(views, v)
			end
		end
	end
	local hall = RS:WaitForChild("ArmoryBackdrop", 15)
	if hall then
		pcall(ContentProvider.PreloadAsync, ContentProvider, { hall })
		local Armory = require(RS:WaitForChild("ArmoryStage"))
		if Armory.Prepare() then
			for _, v in Armory.WarmViews() do
				table.insert(views, v)
			end
		end
	end
	return views
end

-- Look at each stage once while the loading screen hides the camera. Skipped once the loading
-- screen is gone: the stages are still parked, they just render for the first time on open.
local function lookAtStages(player, gui, views)
	local function covered()
		return gui:GetAttribute("LoadingScreenUp") == true
	end
	local deadline = os.clock() + CHARACTER_WAIT
	while covered() and os.clock() < deadline do
		local c = player.Character
		if c and c:FindFirstChild("HumanoidRootPart") then
			break
		end
		task.wait(0.1)
	end
	if #views == 0 or not covered() then
		return
	end
	local camera = workspace.CurrentCamera
	local T = require(RS:WaitForChild("UITheme"))
	T.cameraTake("Preload")
	camera.CameraType = Enum.CameraType.Scriptable
	pcall(function() -- the camera is always handed back below
		for _, v in views do
			if not covered() then
				break
			end
			camera.FieldOfView = v.fov
			camera.CFrame = v.cframe
			local t = os.clock()
			repeat
				RunService.RenderStepped:Wait()
			until os.clock() - t >= WARM_HOLD
		end
	end)
	-- The regular camera (Custom, your Humanoid, FOV 70), not the type and FOV found before the
	-- warm-up (2026-10-03: every stage hands back the same constant).
	T.cameraRelease("Preload")
end

local function warmModels(role)
	local list = {}
	for _, m in MODELS do
		if role == "Match" and m.lobbyOnly then
			continue
		end
		local folder = find(m.path)
		if folder then
			table.insert(list, folder)
		end
	end
	if #list > 0 then
		pcall(ContentProvider.PreloadAsync, ContentProvider, list)
	end
end

function P.start(player)
	if started then
		return
	end
	started = true
	local gui = player:WaitForChild("PlayerGui")
	local role = RS:GetAttribute("ServerRole")
	local pending = 1
	local function finished()
		pending -= 1
		if pending == 0 then
			gui:SetAttribute("AssetWarmReady", true)
			task.spawn(warmModels, role)
		end
	end
	task.spawn(function()
		pcall(warmImages, player, gui)
		finished()
	end)
	-- The map-select islands and the Armory hall only exist behind lobby screens.
	if role ~= "Match" then
		pending += 1
		task.spawn(function()
			local ok, views = pcall(prepareStages)
			if ok then
				pcall(lookAtStages, player, gui, views)
			end
			finished()
		end)
	end
end

return P
