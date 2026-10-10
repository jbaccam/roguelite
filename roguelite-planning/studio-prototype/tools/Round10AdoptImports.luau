-- Edit-time: adopt the round 10 imports in one call (2026-10-10). After the six FBX in
-- build/round10-import-2026-10-10 are imported with Studio's 3D Importer (skinned, Keep Zero
-- Influence Bones, "insert using scene position" off), run in execute_luau (Edit) with a dev server
-- that serves roguelite-planning/ (tools/dev_server.py):
--   local base='http://127.0.0.1:8950/'
--   return loadstring(game.HttpService:GetAsync(base..'studio-prototype/tools/Round10AdoptImports.luau'))()(base)
-- Steps, each only when its import is in Workspace:
--   Bloater  -> bloater-zombie/InstallBloater (RogueliteNPCs.BloaterZombie_NPC).
--   Coffins  -> round10-props/InstallRound10Props (Round10Props.*; the vent and debris come from the
--               stored imports when not re-imported).
--   The raw Bloater and prop imports are then filed in ServerStorage.Round10RawImports (one they
--   replace goes to Round10RawImportsHistory).
--   Leaders  -> ServerStorage.MapBossRawImports.<Id> at ScaleTo(0.01) with ImportBaselineScale (an
--               older one to MapBossRawImportsHistory). Their height is checked against BossGameData
--               (5%), and each receipt (DumpBossReceipt) is POSTed to <base>dump/<anim>-receipt
--               for retarget_boss.py. The templates come later: retarget_boss.py, build_boss_modules.py,
--               a MapBossTiming/BossAnimations sync, then InstallMapBossTemplates with ONLY.
-- Returns a report. dry=true only reports which imports it found (and where), changing nothing.
return function(base, dry)
	assert(game.PlaceId == 107877054949326, "Scoped to the roguelite place")
	assert(not game:GetService("RunService"):IsRunning(), "Run in Edit mode")
	assert(type(base) == "string" and base:sub(-1) == "/", "Pass the dev server root, ending in /")
	local HS = game:GetService("HttpService")
	local storage = game:GetService("ServerStorage")
	local report = {}
	local function say(line) table.insert(report, line) end
	local function get(path) return HS:GetAsync(base .. path .. "?t=" .. os.clock(), true) end
	local function run(path) return assert(loadstring(get(path), path))() end
	local function folder(parent, name)
		local f = parent:FindFirstChild(name) or Instance.new("Folder")
		f.Name = name; f.Parent = parent
		return f
	end
	local function topModel(d)
		local m = d
		while m.Parent and m.Parent ~= workspace do m = m.Parent end
		return m.Parent == workspace and m:IsA("Model") and m or nil
	end
	-- An import by its model name, else the top-level Model holding a mesh named `mesh` (or with that prefix).
	local function findImport(name, mesh, prefix)
		local m = workspace:FindFirstChild(name)
		if m and m:IsA("Model") then return m end
		for _, d in workspace:GetDescendants() do
			if d:IsA("MeshPart") and (d.Name == mesh or (prefix and d.Name:sub(1, #mesh) == mesh)) then
				local t = topModel(d)
				if t and not t:FindFirstChildOfClass("Humanoid") and not t:FindFirstAncestor("Round10Event") then return t end
			end
		end
	end
	-- File a raw import, moving an older one of the same name to the history folder.
	local function file(model, into, history, name)
		local old = into:FindFirstChild(name)
		if old and old ~= model then
			old.Name = name .. "_before_" .. os.date("%Y%m%d_%H%M%S"); old.Parent = folder(storage, history)
		end
		model.Name = name; model.Parent = into
	end

	if dry then
		local found = {
			Bloater = findImport("BloaterZombie_Import", "EyeGlow"), Sarcophagus = findImport("Sarcophagus", "Sarcophagus_Body"),
			SarcophagusBroken = findImport("SarcophagusBroken", "SarcophagusBroken_", true),
			DJCrab = findImport("DJCrab_Studio", "DJCrab_", true), TombWarden = findImport("TombWarden_Studio", "TombWarden_", true),
			BloodAlpha = findImport("AlphaWolf_Studio", "AlphaWolf_", true),
		}
		for _, k in { "Bloater", "Sarcophagus", "SarcophagusBroken", "DJCrab", "TombWarden", "BloodAlpha" } do
			say(k .. ": " .. (found[k] and found[k]:GetFullName() or "not found"))
		end
		return table.concat(report, "\n")
	end

	-- Bloater.
	local bloater = findImport("BloaterZombie_Import", "EyeGlow")
	if bloater then
		local r = run("bloater-zombie/InstallBloater.luau")(bloater, base)
		say(("Bloater: %s, %d sections, alignment %.6f, height %.2f"):format(r.name, r.parts, r.alignmentError, r.height or 0))
		file(bloater, folder(storage, "Round10RawImports"), "Round10RawImportsHistory", "BloaterZombie_Import")
	else
		say("Bloater: not imported (skipped)")
	end

	-- Coffins (and the vent and debris, re-imported or stored).
	local coffin = findImport("Sarcophagus", "Sarcophagus_Body")
	if coffin then
		say(run("round10-props/InstallRound10Props.luau")(base))
		local raw = folder(storage, "Round10RawImports")
		local broken = findImport("SarcophagusBroken", "SarcophagusBroken_", true)
		file(coffin, raw, "Round10RawImportsHistory", "Sarcophagus")
		if broken then file(broken, raw, "Round10RawImportsHistory", "SarcophagusBroken") end
		for _, n in { "VolcanicVent", "VolcanicDebris" } do
			local m = findImport(n, n == "VolcanicVent" and "Vent_Rock" or "Debris_1")
			if m then file(m, raw, "Round10RawImportsHistory", n) end
		end
	else
		say("Coffins: not imported (skipped)")
	end

	-- Leaders: raw imports, scale, height check, receipts.
	local LEADERS = {
		{ id = "DJCrab", fbx = "DJCrab_Studio", prefix = "DJCrab_", anim = "dj-crab", dir = "dj-crab-boss" },
		{ id = "TombWarden", fbx = "TombWarden_Studio", prefix = "TombWarden_", anim = "tomb-warden", dir = "tomb-warden-boss" },
		{ id = "BloodAlpha", fbx = "AlphaWolf_Studio", prefix = "AlphaWolf_", anim = "alpha-werewolf", dir = "alpha-werewolf-boss" },
	}
	local dumper = get("studio-prototype/combat/bosses/DumpBossReceipt.luau")
	for _, L in LEADERS do
		local m = findImport(L.fbx, L.prefix, true)
		if not m then
			say(L.id .. ": not imported (skipped)")
		else
			local raw = folder(storage, "MapBossRawImports")
			file(m, raw, "MapBossRawImportsHistory", L.id)
			if not m:GetAttribute("ImportBaselineScale") then m:ScaleTo(0.01); m:SetAttribute("ImportBaselineScale", 0.01) end
			local want = HS:JSONDecode(get(L.dir .. "/exports/game/BossGameData.json")).height
			local got = m:GetExtentsSize().Y
			local bones = 0
			for _, d in m:GetDescendants() do if d:IsA("Bone") then bones += 1 end end
			local ok = want and math.abs(got - want) / want <= 0.05
			local src = dumper:gsub("local ID=ID or 'KingCrab'", "local ID='" .. L.id .. "'", 1)
			local receipt = assert(loadstring(src, "DumpBossReceipt"))()
			HS:PostAsync(base .. "dump/" .. L.anim .. "-receipt", receipt, Enum.HttpContentType.ApplicationJson)
			say(("%s: filed, height %.2f vs %.2f (%s), %d bones, receipt -> dump/%s-receipt.json"):format(
				L.id, got, want or -1, ok and "ok" or "CHECK", bones, L.anim))
		end
	end
	return table.concat(report, "\n")
end
