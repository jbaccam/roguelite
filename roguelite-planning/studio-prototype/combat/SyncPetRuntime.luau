-- Edit-mode sync of the pet gameplay (RARITY_GODLY_ARMOR.md step 6) from this repo into Studio.
-- Serve roguelite-planning/ first:
--   python -m http.server 8765 --bind 127.0.0.1 --directory roguelite-planning
-- Optional, for the safety check on shared files (same idea as ui/SyncUIRuntime): serve a folder
-- holding the HEAD copies, `git show HEAD:roguelite-planning/<path>` saved at the same <path>:
--   python -m http.server 8791 --bind 127.0.0.1 --directory <dir with the HEAD copies>
-- Then paste this file into execute_luau (Edit).
--
-- New scripts are created with the right sandboxing (plan D "capsFrom"):
--   RS.RogueliteCombat.PetConfig   ModuleScript, SANDBOXED, Capabilities from CharacterStats
--   RS.RogueliteCombat.PetRigs     ModuleScript, SANDBOXED, Capabilities from CharacterStats
--   RS.RogueliteCombat.PetFX       RemoteEvent, SANDBOXED, Basic + RemoteEvent
--   SSS.PetService                 Script, SANDBOXED, Capabilities from SSS.RogueliteCombat
--   SPS.PetVisuals                 LocalScript, unsandboxed
--   ServerStorage.RogueliteTests.PetConfigTests  ModuleScript (run below on fresh copies)
-- Shared files that other sessions also edit are pushed whole from the repo and listed in a
-- WARNING block so the operator can diff them. With the HEAD server up, a shared file whose Studio
-- copy holds lines that neither HEAD nor the repo has (a Studio-only edit) is SKIPPED and those
-- lines are printed; port them into the repo first, or set FORCE_SHARED = true.
-- DRY = true only reports.
assert(not game:GetService("RunService"):IsRunning(), "Run the sync in Edit mode")
local DRY = false
local FORCE_SHARED = false
local Http = game:GetService("HttpService")
local RS, SSS, SS = game.ReplicatedStorage, game.ServerScriptService, game.ServerStorage
local RC = RS.RogueliteCombat
local SPS = game.StarterPlayer.StarterPlayerScripts
local BASE = "studio-prototype/"

local function get(url)
	local was = Http.HttpEnabled
	Http.HttpEnabled = true
	local ok, src = pcall(function()
		return Http:GetAsync(url, true)
	end)
	Http.HttpEnabled = was
	return ok and src or nil
end
local function unix(s)
	return (s:gsub("\r\n", "\n"))
end
local function norm(s)
	return (unix(s):gsub("%s+$", ""))
end
local function pull(path)
	local src = get("http://127.0.0.1:8765/" .. path)
	assert(src, "pull " .. path .. " failed: is the 8765 server running?")
	return unix(src)
end
local function lines(s)
	local t = {}
	for l in (unix(s) .. "\n"):gmatch("(.-)\n") do
		local k = l:gsub("^%s+", ""):gsub("%s+$", "")
		if k ~= "" then
			t[k] = (t[k] or 0) + 1
		end
	end
	return t
end

local report, warnings = {}, {}
local function note(s)
	table.insert(report, s)
end

-- New scripts ------------------------------------------------------------------------------------
-- Create (if missing) and fill a script. capsFrom: Sandboxed = true with that instance's Capabilities.
local function create(className, name, parent, path, capsFrom)
	local src = pull(path)
	local s = parent:FindFirstChild(name)
	if s and not s:IsA(className) then
		note("WARNING " .. s:GetFullName() .. " is a " .. s.ClassName .. ", expected " .. className .. " - skipped")
		return s
	end
	if not s then
		if DRY then
			note("would create " .. parent:GetFullName() .. "." .. name .. (capsFrom and " (sandboxed)" or ""))
			return nil
		end
		s = Instance.new(className)
		s.Name = name
		if capsFrom then
			s.Sandboxed = true
			s.Capabilities = capsFrom.Capabilities
		end
		s.Source = src
		s.Parent = parent
		note("CREATED " .. s:GetFullName() .. (capsFrom and " (Sandboxed, caps from " .. capsFrom.Name .. ")" or ""))
		return s
	end
	if capsFrom and not s.Sandboxed then
		if DRY then
			note("would sandbox " .. s:GetFullName())
		else
			s.Sandboxed = true
			s.Capabilities = capsFrom.Capabilities
			note("SANDBOXED " .. s:GetFullName() .. " (caps from " .. capsFrom.Name .. ")")
		end
	end
	if norm(s.Source) == norm(src) then
		note("same " .. s:GetFullName())
	elseif DRY then
		note("would write " .. s:GetFullName())
	else
		s.Source = src
		note("WROTE " .. s:GetFullName() .. " (" .. #src .. " chars)")
	end
	return s
end

local moduleCaps = RC:WaitForChild("CharacterStats")
assert(moduleCaps.Sandboxed, "CharacterStats should be sandboxed (plan D conventions)")
local scriptCaps = SSS:FindFirstChild("RogueliteCombat")
if not (scriptCaps and scriptCaps:IsA("Script") and scriptCaps.Sandboxed) then
	scriptCaps = nil
	for _, c in SSS:GetChildren() do
		if c:IsA("Script") and c.Sandboxed then
			scriptCaps = c
			break
		end
	end
end
assert(scriptCaps, "no sandboxed Script in ServerScriptService to copy Capabilities from")

create("ModuleScript", "PetConfig", RC, BASE .. "combat/PetConfig.luau", moduleCaps)
if get("http://127.0.0.1:8765/" .. BASE .. "combat/PetRigs.luau") then
	create("ModuleScript", "PetRigs", RC, BASE .. "combat/PetRigs.luau", moduleCaps)
else
	note("WARNING no repo PetRigs.luau yet: pets will follow but not animate")
end
local fx = RC:FindFirstChild("PetFX")
if not fx then
	if DRY then
		note("would create RemoteEvent RogueliteCombat.PetFX (sandboxed)")
	else
		fx = Instance.new("RemoteEvent")
		fx.Name = "PetFX"
		fx.Sandboxed = true
		fx.Capabilities =
			SecurityCapabilities.new(Enum.SecurityCapability.Basic, Enum.SecurityCapability.RemoteEvent)
		fx.Parent = RC
		note("CREATED " .. fx:GetFullName() .. " (Sandboxed, Basic + RemoteEvent)")
	end
elseif not fx.Sandboxed then
	note("WARNING " .. fx:GetFullName() .. " exists but is not Sandboxed")
end
create("Script", "PetService", SSS, BASE .. "combat/PetService.server.luau", scriptCaps)
create("LocalScript", "PetVisuals", SPS, BASE .. "combat/PetVisuals.client.luau", nil)
local tests = SS:FindFirstChild("RogueliteTests")
if not tests and not DRY then
	tests = Instance.new("Folder")
	tests.Name = "RogueliteTests"
	tests.Parent = SS
end
if tests then
	create("ModuleScript", "PetConfigTests", tests, BASE .. "combat/PetConfigTests.luau", nil)
end

-- Shared files (other sessions edit these too) ---------------------------------------------------
local SHARED = {
	{ "ChestConfig", "combat/ChestConfig.luau" },
	{ "ProfileService", "combat/ProfileService.luau" },
	{ "CharacterService", "combat/CharacterService.luau" },
	{ "CombatEffectsService", "combat/CombatEffectsService.luau" },
	{ "ShardDropService", "combat/ShardDropService.luau" },
	{ "RogueliteMeta", "combat/RogueliteMeta.server.luau" },
	{ "ArmoryUI", "ui/ArmoryUI.luau" },
	{ "LobbyUI", "ui/LobbyUI.luau" },
}
local function find(name)
	local hits = {}
	for _, d in game:GetDescendants() do
		if d:IsA("LuaSourceContainer") and d.Name == name and not d:IsDescendantOf(SS) then
			table.insert(hits, d)
		end
	end
	return hits
end
for _, item in SHARED do
	local name, path = item[1], BASE .. item[2]
	local cur = pull(path)
	local head = get("http://127.0.0.1:8791/" .. path)
	local hits = find(name)
	if #hits ~= 1 then
		table.insert(warnings, "FOUND " .. #hits .. " scripts named " .. name .. " - skipped")
		continue
	end
	local s = hits[1]
	if norm(s.Source) == norm(cur) then
		note("same " .. s:GetFullName())
		continue
	end
	local studioOnly = {}
	if head then
		local h, c = lines(head), lines(cur)
		for l, n in lines(s.Source) do
			if n > (h[l] or 0) and not c[l] then
				table.insert(studioOnly, l:sub(1, 100))
			end
		end
	end
	if #studioOnly > 0 and not FORCE_SHARED then
		table.insert(
			warnings,
			"STUDIO-ONLY EDITS in " .. s:GetFullName() .. " - skipped:\n   " .. table.concat(studioOnly, "\n   ")
		)
	elseif DRY then
		table.insert(warnings, "would push " .. s:GetFullName() .. " (shared: diff it first)")
	else
		s.Source = cur
		table.insert(
			warnings,
			"PUSHED shared " .. s:GetFullName() .. (head and " (checked against HEAD)" or " (NO HEAD CHECK: diff it)")
		)
	end
end

-- Checks -----------------------------------------------------------------------------------------
local function fresh(m)
	local c = m:Clone()
	c.Parent = m.Parent
	local ok, r = pcall(require, c)
	c:Destroy()
	assert(ok, r)
	return r
end
if not DRY and tests and tests:FindFirstChild("PetConfigTests") and RC:FindFirstChild("PetConfig") then
	local ok, result = pcall(function()
		return fresh(tests.PetConfigTests)(fresh(RC.PetConfig), fresh(RC.CharacterStats))
	end)
	note(ok and ("PetConfigTests PASS " .. result.passed .. " checks") or ("PetConfigTests FAIL " .. tostring(result)))
end
local models = RS:FindFirstChild("PetModels")
local have, missing = 0, {}
for _, id in { "GoldenRetriever", "Bunny", "Frog", "Penguin", "Fox", "Bee", "Turtle", "Monkey", "LuckyCat", "Owl", "CheetahCub", "BabyDragon" } do
	if models and models:FindFirstChild(id) then
		have += 1
	else
		table.insert(missing, id)
	end
end
note("PetModels installed: " .. have .. "/12" .. (#missing > 0 and (" (missing " .. table.concat(missing, ", ") .. ")") or ""))

if #warnings > 0 then
	note("\nWARNING shared files (other sessions edit these; diff before trusting Studio):")
	for _, w in warnings do
		note(" - " .. w)
	end
end
return table.concat(report, "\n")
