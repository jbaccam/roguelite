--!nonstrict
-- Read-only repo loader for Studio Edit checks (Hammer Brute rebuild, Track RUN). Studio's copies of
-- the map-boss modules can be older than the repo, and the plugin VM caches require() across
-- execute_luau calls, so names in PATHS load from the repo text through tools/dev_server.py instead.
-- Nothing is written to Studio: no instances, no Source, no attributes, no HttpEnabled.
-- A repo module's requires of other PATHS modules (by instance or by name) resolve to the same fresh
-- copies; anything else is Studio's require. Each chunk sees `script` as its Studio instance when
-- there is one, else a stand-in {Name, Parent} under the folder it would sync to.
-- rev (optional): load the files as committed at that git revision (dev_server /git/<rev>/), e.g.
-- 'HEAD' to compare old and new builders side by side.
-- Usage (execute_luau, Edit, with the dev server on 127.0.0.1:8934):
--   local HS=game:GetService('HttpService')
--   local base='http://127.0.0.1:8934/'
--   local R=loadstring(HS:GetAsync(base..'studio-prototype/tools/RepoRequire.luau?t='..os.clock(),true))()(base)
--   print(R.run('MapBossServiceTests'))                -- a test module's PASS/FAIL lines
--   print(R.run('MapBossPresentationTests'))           -- the client's pure helpers (R4)
--   print(R.run('BossVfxHammerTests'))                 -- the Hammer's rubble wave helpers
--   print(R.compiles('combat/bosses/MapBossService.luau')) -- true, or false and the error
--   local X=R.require('MapBossService')._shapes          -- Edit: the pure builders only
return function(base, rev)
	local HS = game:GetService("HttpService")
	local ROOT = "studio-prototype/"
	local PATHS = {
		MapBossShapes = "combat/bosses/MapBossShapes.luau",
		MapBossDefs = "combat/bosses/MapBossDefs.luau",
		MapBossTiming = "combat/bosses/MapBossTiming.luau",
		MapBossService = "combat/bosses/MapBossService.luau",
		MapBossServiceTests = "combat/bosses/MapBossServiceTests.luau",
		MapBossShapesTests = "combat/bosses/MapBossShapesTests.luau",
		-- The LocalScript's repo text returns its pure helpers in Edit (it stops before anything
		-- client-side); a plain require can't load a LocalScript, so only this loader runs it.
		MapBossPresentation = "combat/bosses/MapBossPresentation.client.luau",
		MapBossPresentationTests = "combat/bosses/MapBossPresentationTests.luau",
		-- BossVfx/Hammer returns only its rubble-wave helpers in Edit (it stops before Common).
		BossVfxHammer = "combat/bosses/BossVfx/Hammer.luau",
		BossVfxHammerTests = "combat/bosses/BossVfxHammerTests.luau",
	}
	-- Where each module lives in Studio (SyncMapBossRuntime): its `script`, or the stand-in's Parent.
	local STUDIO = {
		MapBossShapes = { "ReplicatedStorage", "RogueliteCombat" },
		MapBossDefs = { "ReplicatedStorage", "RogueliteCombat" },
		MapBossTiming = { "ReplicatedStorage", "RogueliteCombat" },
		MapBossService = { "ServerScriptService" },
		MapBossServiceTests = { "ServerScriptService" },
		MapBossShapesTests = { "ServerScriptService" },
		MapBossPresentation = { "StarterPlayer", "StarterPlayerScripts" },
		MapBossPresentationTests = { "ServerScriptService" },
		BossVfxHammer = { "ReplicatedStorage", "RogueliteCombat", "BossVfx" },
		BossVfxHammerTests = { "ServerScriptService" },
	}
	local function folder(name)
		local parts = STUDIO[name]
		local ok, inst = pcall(game.GetService, game, parts[1])
		inst = ok and inst or nil
		for i = 2, #parts do
			inst = inst and inst:FindFirstChild(parts[i])
		end
		return inst
	end
	local R = { cache = {} }
	function R.source(path)
		local url = base .. (rev and ("git/" .. rev .. "/") or "") .. ROOT .. path .. "?t=" .. os.clock()
		return (HS:GetAsync(url, true):gsub("\r\n", "\n"))
	end
	function R.compiles(path)
		local fn, err = loadstring(R.source(path), "=" .. path)
		return fn ~= nil, err
	end
	-- A fresh chunk for `name`, with the require shim and its `script`.
	local function chunk(name)
		local path = assert(PATHS[name], "RepoRequire: no repo path for " .. tostring(name))
		local fn, err = loadstring(R.source(path), "=" .. path)
		assert(fn, tostring(err))
		local parent = folder(name)
		local here = parent and parent:FindFirstChild(name)
		if not (here and here:IsA("ModuleScript")) then
			here = { Name = name, Parent = parent }
		end
		setfenv(fn, setmetatable({ require = R.require, script = here }, { __index = getfenv(0) }))
		return fn
	end
	function R.require(target)
		local name = (typeof(target) == "Instance" or type(target) == "table") and target.Name or target
		if not PATHS[name] then
			return require(target)
		end
		if R.cache[name] == nil then
			R.cache[name] = chunk(name)()
		end
		return R.cache[name]
	end
	-- A test module run fresh every time (not cached): its return value.
	function R.run(name)
		return chunk(name)()
	end
	return R
end
