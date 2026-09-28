-- Background asset loading for the lobby, so windows, scroll lists and the run-setup backdrop
-- never pop in. Started once from the lobby HUD entry script; never blocks the HUD.
--   1. Every UI image named in the shared UI/catalog modules is requested and then kept
--      resident by a tiny, nearly transparent label. Destroying preload labels lets the engine
--      drop the texture again, which is what made icons appear late while scrolling.
--   2. The map-select islands' meshes and textures are fetched and the backdrop scene is
--      cloned ahead of time, so PLAY shows the finished island on its first frame.
local RS = game:GetService("ReplicatedStorage")
local ContentProvider = game:GetService("ContentProvider")
local P = {}

-- Modules whose exported tables name UI images, most visible first (lobby frame, then icons).
local SOURCES = {
	{ "UITheme" },
	{ "RogueliteUI" },
	{ "WeaponInventoryUI" },
	{ "StoreFX" },
	{ "RogueliteCombat", "ShopCatalog" },
	{ "RogueliteCombat", "LevelUpCatalog" },
	{ "RogueliteCombat", "ChestConfig" },
	{ "RogueliteCombat", "MonetizationConfig" },
	{ "RogueliteCombat", "SkillTreeConfig" },
}

local started = false

-- Every rbxassetid string reachable from the modules' exported tables, in source order.
function P.collect()
	local seen, list = {}, {}
	local function walk(t, depth, visited)
		if depth > 4 or visited[t] then
			return
		end
		visited[t] = true
		for _, v in t do
			if type(v) == "string" and string.find(v, "^rbxassetid://%d+$") then
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
		local node = RS
		for _, name in path do
			node = node and node:FindFirstChild(name)
		end
		if node and node:IsA("ModuleScript") then
			local ok, t = pcall(require, node)
			if ok and type(t) == "table" then
				walk(t, 0, {})
			end
		end
	end
	return list
end

local function warmImages(player)
	local ids = P.collect()
	local T = require(RS:WaitForChild("UITheme"))
	table.insert(ids, 1, T.headshotId(player.UserId)) -- profile chip, Profile and Party windows
	local gui = Instance.new("ScreenGui")
	gui.Name = "AssetWarmCache"
	gui.ResetOnSpawn = false
	gui.IgnoreGuiInset = true
	gui.DisplayOrder = -100
	local labels = {}
	for _, id in ids do
		local l = Instance.new("ImageLabel")
		l.BackgroundTransparency = 1
		l.BorderSizePixel = 0
		l.Size = UDim2.fromOffset(1, 1)
		l.Image = id
		l.ImageTransparency = 0.995 -- still drawn (so it stays resident) but invisible
		l.Interactable = false
		l.Parent = gui
		table.insert(labels, l)
	end
	gui.Parent = player:WaitForChild("PlayerGui")
	pcall(ContentProvider.PreloadAsync, ContentProvider, labels)
	gui:SetAttribute("Images", #ids)
end

local function warmIslands()
	local islands = RS:WaitForChild("MapSelectIslands", 15)
	if not islands then
		return
	end
	pcall(ContentProvider.PreloadAsync, ContentProvider, { islands })
	local Rules = require(RS:WaitForChild("RunSetupRules"))
	require(RS:WaitForChild("MapSelectBackdrop")).Prepare(Rules.Maps)
end

-- The Armory hall (ArmoryStage) behind the Armory screen.
local function warmArmory()
	local hall = RS:WaitForChild("ArmoryBackdrop", 15)
	if not hall then
		return
	end
	pcall(ContentProvider.PreloadAsync, ContentProvider, { hall })
	require(RS:WaitForChild("ArmoryStage")).Prepare()
end

function P.start(player)
	if started then
		return
	end
	started = true
	task.spawn(warmImages, player)
	task.spawn(warmIslands)
	task.spawn(warmArmory)
end

return P
