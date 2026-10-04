-- Edit-mode sync of the map-boss runtime from this repo into Studio. Serve roguelite-planning/ with
--   python -m http.server 8765 --bind 127.0.0.1 --directory roguelite-planning
-- then paste this file into execute_luau (Edit). Only scripts whose code differs are written.
-- New modules are created unsandboxed, like the rest of the map-boss chain (see the
-- roguelite-new-modules note: MapBossPresentation, MapBossService and BossVfx are all unsandboxed).
-- It warns if the dragon template is still the old shrunk import (see InstallMapBossTemplates).
-- MapBossServiceTests, MapBossShapesTests and MapBossPresentationTests run from the repo through
-- tools/RepoRequire.luau and are not synced.
assert(not game:GetService("RunService"):IsRunning(), "Run the sync in Edit mode")
local Http = game:GetService("HttpService")
local RS, SSS, SS = game.ReplicatedStorage, game.ServerScriptService, game.ServerStorage
local RC = RS.RogueliteCombat
local BASE = "studio-prototype/combat/bosses/"
local function pull(path)
	local was = Http.HttpEnabled
	Http.HttpEnabled = true
	local ok, src = pcall(function()
		return Http:GetAsync("http://127.0.0.1:8765/" .. path, true)
	end)
	Http.HttpEnabled = was
	assert(ok, "pull " .. path .. ": " .. tostring(src))
	return (src:gsub("\r\n", "\n"))
end
local function norm(s)
	return ((s:gsub("\r\n", "\n")):gsub("%s+$", ""))
end
local report, written = {}, 0
local function put(parent, className, name, path)
	local s = parent:FindFirstChild(name)
	local src = pull(path)
	if not s then
		s = Instance.new(className)
		s.Name = name
		s.Parent = parent
		table.insert(report, "CREATED " .. s:GetFullName())
	end
	if norm(s.Source) ~= norm(src) then
		s.Source = src
		written += 1
		table.insert(report, "WROTE " .. s:GetFullName() .. " (" .. #src .. ")")
	end
	return s
end

-- Runtime scripts.
put(RC, "ModuleScript", "MapBossTiming", BASE .. "MapBossTiming.luau")
put(RC, "ModuleScript", "MapBossDefs", BASE .. "MapBossDefs.luau")
put(RC, "ModuleScript", "MapBossShapes", BASE .. "MapBossShapes.luau")
put(RC, "ModuleScript", "BossVfxAssets", BASE .. "BossVfxAssets.luau")
put(SSS, "ModuleScript", "MapBossService", BASE .. "MapBossService.luau")
put(game.StarterPlayer.StarterPlayerScripts, "LocalScript", "MapBossPresentation", BASE .. "MapBossPresentation.client.luau")
local vfx = RC:FindFirstChild("BossVfx")
if not vfx then
	vfx = Instance.new("Folder")
	vfx.Name = "BossVfx"
	vfx.Parent = RC
end
for _, name in { "Common", "Dragon", "FrostCyclops", "Hammer", "KingCrab", "Pharaoh" } do
	put(vfx, "ModuleScript", name, BASE .. "BossVfx/" .. name .. ".luau")
end
-- Wave bosses: BossEncounter routes 'Hammer' to this runtime once MapBossDefs.ready('Hammer') (the
-- Hammer Brute rebuild); until then it spawns the old BossService Hammer. Its other routing
-- (RogueliteZombieChase admin and Endless spawns, BossIntro, the shell and tutorial readers) is in
-- plan_hammer_brute_hunks.py, synced with tools/SyncPlan.
put(SSS, "Script", "BossEncounter", BASE .. "BossEncounter.server.luau")
-- Animation modules: ANIMATIONS lists repo files under BossAnimations/ ('king-crab/ClawCrush/Frames01');
-- a trailing 'init' is the folder's own module.
for _, rel in ANIMATIONS or {} do
	local parts = string.split(rel, "/")
	local node = RC.BossAnimations
	for i, p in parts do
		if not (i == #parts and p == "init") then
			node = assert(node:FindFirstChild(p), "missing BossAnimations node " .. rel)
		end
	end
	if norm(node.Source) ~= norm(pull(BASE .. "BossAnimations/" .. rel .. ".luau")) then
		node.Source = pull(BASE .. "BossAnimations/" .. rel .. ".luau")
		written += 1
		table.insert(report, "WROTE " .. node:GetFullName())
	end
end

-- Dragon template: the Studio FBX is split under the 2048-unit mesh cap, so there is no import
-- shrink to restore any more (the old x1.467 restore here would stretch a correct template).
-- A template still carrying a capped section is the old shrunk import: rerun InstallMapBossTemplates.
local dragon = SS.RogueliteNPCs:FindFirstChild("Dragon_NPC")
if dragon then
	for _, p in dragon:GetDescendants() do
		if p:IsA("MeshPart") and math.max(p.Size.X, p.Size.Y, p.Size.Z) >= 20.47 then
			table.insert(report, "WARNING Dragon_NPC has a capped section (" .. p.Name .. "): rerun InstallMapBossTemplates")
			break
		end
	end
end
table.insert(report, "scripts written: " .. written)
return table.concat(report, "\n")
