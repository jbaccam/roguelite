-- Edit-mode sync of the map-boss runtime from this repo into Studio. Serve roguelite-planning/ with
--   python -m http.server 8765 --bind 127.0.0.1 --directory roguelite-planning
-- then paste this file into execute_luau (Edit). Only scripts whose code differs are written.
-- New modules are created unsandboxed, like the rest of the map-boss chain (see the
-- roguelite-new-modules note: MapBossPresentation, MapBossService and BossVfx are all unsandboxed).
-- It also restores the dragon template's import shrink (see InstallMapBossTemplates) if the
-- template in ServerStorage predates that fix.
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
for _, name in { "Common", "Dragon", "FrostCyclops", "KingCrab", "Pharaoh" } do
	put(vfx, "ModuleScript", name, BASE .. "BossVfx/" .. name .. ".luau")
end
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

-- Dragon template: restore the importer's 2048-unit mesh shrink about Dragon_Belly.
local FACTOR = 3004.590 / 2048
local dragon = SS.RogueliteNPCs:FindFirstChild("Dragon_NPC")
if dragon and not dragon:GetAttribute("ImportShrinkRestored") then
	local rig = assert(dragon:FindFirstChild("RootPart"), "Dragon_NPC has no importer RootPart")
	local anchor = assert(dragon:FindFirstChild("Dragon_Belly", true), "Dragon_NPC has no Dragon_Belly")
	local centre = rig.CFrame:PointToObjectSpace(anchor.Position)
	-- Welds off while the sections move, so no section drags the assembly; re-enabling rebuilds
	-- each weld's offset from the new placement.
	local welds = {}
	for _, w in dragon:GetDescendants() do
		if w:IsA("WeldConstraint") and w.Enabled and ((w.Part0 and w.Part0:IsA("MeshPart")) or (w.Part1 and w.Part1:IsA("MeshPart"))) then
			w.Enabled = false
			table.insert(welds, w)
		end
	end
	local rigBefore = rig.CFrame
	local n = 0
	for _, p in dragon:GetDescendants() do
		if p:IsA("MeshPart") then
			local rel = rig.CFrame:ToObjectSpace(p.CFrame)
			p.Size *= FACTOR
			p.CFrame = rig.CFrame * (CFrame.new(centre + (rel.Position - centre) * FACTOR) * rel.Rotation)
			n += 1
		end
	end
	for _, w in welds do
		w.Enabled = true
	end
	assert(rig.CFrame == rigBefore, "the importer RootPart moved")
	dragon:SetAttribute("ImportShrinkRestored", FACTOR)
	table.insert(report, string.format("DRAGON restored %d sections x%.6f, %d welds rebuilt", n, FACTOR, #welds))
end
table.insert(report, "scripts written: " .. written)
return table.concat(report, "\n")
