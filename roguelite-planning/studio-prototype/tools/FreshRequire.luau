--!nonstrict
-- Fresh copies of repo modules in Studio Edit, for checks and UI previews without Play (plan K).
-- The plugin VM caches require() across execute_luau calls, so Studio's ModuleScripts can come back
-- stale. Names in PATHS load from the repo through tools/dev_server.py instead, and their requires
-- of each other (by instance name) resolve to the same fresh copies; everything else is required
-- from Studio as usual. Usage (execute_luau):
--   local HS=game:GetService('HttpService')
--   local base='http://127.0.0.1:8934/studio-prototype/'
--   local Fresh=loadstring(HS:GetAsync(base..'tools/FreshRequire.luau?t='..os.clock(),true))()(base)
--   local QuestsUI=Fresh.require('QuestsUI')
return function(base)
	local HS = game:GetService("HttpService")
	local PATHS = {
		QuestConfig = "combat/QuestConfig.luau",
		QuestService = "combat/QuestService.luau",
		QuestTests = "combat/QuestTests.luau",
		CharacterStats = "combat/CharacterStats.luau",
		QuestsUI = "ui/QuestsUI.luau",
		StatPlates = "ui/StatPlates.luau",
		PauseUI = "ui/PauseUI.luau",
		UITheme = "ui/UITheme.luau",
		StoreFX = "ui/StoreFX.luau",
		UILayoutAudit = "ui/UILayoutAudit.luau",
		RunSetupRules = "lobby/RunSetupRules.luau",
	}
	-- Where each module lives in Studio: its fresh copy sees that instance as `script`, so
	-- `script.Parent.X` requires still find their (Studio) siblings.
	local STUDIO = {
		QuestConfig = "ReplicatedStorage.RogueliteCombat.QuestConfig",
		QuestService = "ServerScriptService.QuestService",
		CharacterStats = "ReplicatedStorage.RogueliteCombat.CharacterStats",
		QuestsUI = "ReplicatedStorage.QuestsUI",
		StatPlates = "ReplicatedStorage.StatPlates",
		PauseUI = "ReplicatedStorage.PauseUI",
		UITheme = "ReplicatedStorage.UITheme",
		StoreFX = "ReplicatedStorage.StoreFX",
		UILayoutAudit = "ReplicatedStorage.UILayoutAudit",
		RunSetupRules = "ReplicatedStorage.RunSetupRules",
	}
	local function resolve(path)
		local parts = string.split(path or "", ".")
		local ok, inst = pcall(game.GetService, game, parts[1])
		inst = ok and inst or nil
		for i = 2, #parts do
			inst = inst and inst:FindFirstChild(parts[i])
		end
		return inst
	end
	local F = { cache = {} }
	function F.source(path)
		return (HS:GetAsync(base .. path .. "?t=" .. os.clock(), true):gsub("\r\n", "\n"))
	end
	function F.compiles(path)
		local fn, err = loadstring(F.source(path), "=" .. path)
		return fn ~= nil, err
	end
	function F.require(target)
		local name = typeof(target) == "Instance" and target.Name or target
		local path = PATHS[name]
		if not path then
			return require(target)
		end
		if F.cache[name] == nil then
			local fn, err = loadstring(F.source(path), "=" .. path)
			assert(fn, tostring(err))
			local here = typeof(target) == "Instance" and target or resolve(STUDIO[name])
			setfenv(fn, setmetatable({ require = F.require, script = here }, { __index = getfenv(0) }))
			F.cache[name] = fn()
		end
		return F.cache[name]
	end
	return F
end
