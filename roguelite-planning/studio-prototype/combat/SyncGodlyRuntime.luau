-- Edit-mode sync of the Godly weapons change (plans/2026-10-01-G) from this repo into Studio,
-- all or nothing, safe against Studio-only edits. Serve two folders first:
--   python -m http.server 8771 --bind 127.0.0.1 --directory roguelite-planning   (current files)
--   python -m http.server 8793 --bind 127.0.0.1 --directory <dir with the HEAD copies>
-- The HEAD dir holds `git show HEAD:roguelite-planning/studio-prototype/<path>` saved as <path>.
-- A script is written only when every line Studio has beyond the last commit also exists in the
-- repo file (writing loses nothing). If any script fails that check, or its name is ambiguous,
-- NOTHING is written and the report says why. DRY = true only reports.
-- New instances: SSS.GodlyWeapons and RS.RogueliteCombat.GodlyVisuals (ModuleScripts) and
-- RS.RogueliteCombat.GodlyFX (RemoteEvent), Sandboxed with their neighbours' Capabilities.
assert(not game:GetService("RunService"):IsRunning(), "Run the sync in Edit mode")
local DRY = ...
if DRY == nil then
	DRY = true
end
local Http = game:GetService("HttpService")
local RS, SSS = game:GetService("ReplicatedStorage"), game:GetService("ServerScriptService")
local combat = RS:WaitForChild("RogueliteCombat")
-- {repo path under studio-prototype, Studio name, class}
local FILES = {
	{ "combat/WeaponCatalog.luau", "WeaponCatalog", "ModuleScript" },
	{ "combat/ChestConfig.luau", "ChestConfig", "ModuleScript" },
	{ "combat/ShopCatalog.luau", "ShopCatalog", "ModuleScript" },
	{ "combat/CharacterService.luau", "CharacterService", "ModuleScript" },
	{ "combat/CombatEffectsService.luau", "CombatEffectsService", "ModuleScript" },
	{ "combat/RogueliteCombat.server.luau", "RogueliteCombat", "Script" },
	{ "combat/RogueliteCombat.client.luau", "RogueliteCombat", "LocalScript" },
	{ "combat/WeaponMotion.luau", "WeaponMotion", "ModuleScript" },
	{ "combat/SpecialWeapons.luau", "SpecialWeapons", "ModuleScript" },
	{ "combat/SpecialMotion.luau", "SpecialMotion", "ModuleScript" },
	{ "combat/ThrownVisuals.luau", "ThrownVisuals", "ModuleScript" },
	-- RunSetupRules is patched by hand (PATCHES below): Studio held an older map table on 2026-10-01
	-- that another session had not pushed yet, so only the Godly lines go in.
	{ "ui/RunSetupUI.luau", "RunSetupUI", "ModuleScript" },
	{ "ui/ArmoryUI.luau", "ArmoryUI", "ModuleScript" },
	{ "ui/ChestScreenUI.luau", "ChestScreenUI", "ModuleScript" },
	{ "ui/WeaponInventoryUI.luau", "WeaponInventoryUI", "ModuleScript" },
	{ "audio/RogueliteSounds.client.luau", "RogueliteSounds", "LocalScript" },
}
-- New modules: repo path, parent, name, sibling whose Capabilities it copies.
local NEW = {
	{ "combat/GodlyWeapons.luau", SSS, "GodlyWeapons", SSS:FindFirstChild("SpecialWeapons") },
	{ "combat/GodlyVisuals.luau", combat, "GodlyVisuals", combat:FindFirstChild("SwingVisuals") },
}
-- Surgical edits for scripts whose Studio copy must keep its own other lines: each `from` must
-- appear exactly once in Studio (or `to` already present).
local HOME = "function R.homeWeapons(class) local out={};for _,w in Weapons.List do if w.home==class then table.insert(out,w) end end;return out end\n"
local OWNED = "-- Godlies this profile owns (any class can start with one); unowned Godlies are never listed.\nfunction R.ownedGodlies(weapons) local out={};for _,w in Weapons.List do if w.godly and weapons[w.id] then table.insert(out,w) end end;return out end\n"
local LOADOUT = " if not w or w.home~=class or not p.weapons[weapon] then return false,'Weapon not owned' end"
local GODLY_LOADOUT = " -- An owned Godly starts a run with any class (it is the run's one Godly: the shop never sells one).\n if not w or (w.home~=class and not w.godly) or not p.weapons[weapon] then return false,'Weapon not owned' end"
local PATCHES = {
	{ "RunSetupRules", "ModuleScript", { { HOME, HOME .. OWNED }, { LOADOUT, GODLY_LOADOUT } } },
}
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
local function find(name, class)
	local hits = {}
	for _, d in game:GetDescendants() do
		if d.ClassName == class and d.Name == name and not d:IsDescendantOf(game.ServerStorage) then
			table.insert(hits, d)
		end
	end
	return hits
end
local report, writes, blocked = {}, {}, false
for _, f in FILES do
	local path, name, class = f[1], f[2], f[3]
	local cur = get("http://127.0.0.1:8771/studio-prototype/" .. path)
	local head = get("http://127.0.0.1:8793/" .. path)
	local hits = find(name, class)
	if not cur or not head then
		blocked = true
		table.insert(report, "NO " .. (cur and "HEAD" or "REPO") .. " COPY " .. path)
	elseif #hits ~= 1 then
		blocked = true
		table.insert(report, "FOUND " .. #hits .. " " .. class .. " named " .. name)
	else
		local s = hits[1]
		local studioOnly = {}
		local h, c = lines(head), lines(cur)
		for l, n in lines(s.Source) do
			if n > (h[l] or 0) and not c[l] then
				table.insert(studioOnly, l:sub(1, 100))
			end
		end
		if norm(s.Source) == norm(cur) then
			table.insert(report, "same " .. s:GetFullName())
		elseif #studioOnly > 0 then
			blocked = true
			table.insert(report, "STUDIO-ONLY EDITS in " .. s:GetFullName() .. ":\n   " .. table.concat(studioOnly, "\n   "))
		else
			table.insert(writes, { script = s, source = unix(cur) })
			table.insert(report, "write " .. s:GetFullName() .. (norm(s.Source) == norm(head) and "" or " (Studio lagged HEAD)"))
		end
	end
end
local patched = {}
for _, p in PATCHES do
	local hits = find(p[1], p[2])
	if #hits ~= 1 then
		blocked = true
		table.insert(report, "PATCH: found " .. #hits .. " " .. p[2] .. " named " .. p[1])
	else
		local src = unix(hits[1].Source)
		for _, r in p[3] do
			local from, to = r[1], r[2]
			if src:find(to, 1, true) then
				continue
			end
			local first = src:find(from, 1, true)
			if not first or src:find(from, first + 1, true) then
				blocked = true
				table.insert(report, "PATCH " .. p[1] .. ": anchor not found once: " .. from:sub(1, 80))
			else
				src = src:sub(1, first - 1) .. to .. src:sub(first + #from)
			end
		end
		table.insert(patched, { script = hits[1], source = src })
		table.insert(report, "patch " .. hits[1]:GetFullName())
	end
end
local newSources = {}
for _, n in NEW do
	local src = get("http://127.0.0.1:8771/studio-prototype/" .. n[1])
	if not src or not n[4] then
		blocked = true
		table.insert(report, "NEW " .. n[3] .. ": " .. (src and "no sibling to copy Capabilities from" or "no repo copy"))
	else
		newSources[n[3]] = unix(src)
		table.insert(report, (n[2]:FindFirstChild(n[3]) and "update " or "create ") .. n[2]:GetFullName() .. "." .. n[3])
	end
end
table.insert(report, (combat:FindFirstChild("GodlyFX") and "keep " or "create ") .. "RemoteEvent GodlyFX")
if blocked then
	table.insert(report, "BLOCKED: nothing written")
	return table.concat(report, "\n")
end
if DRY then
	table.insert(report, "DRY RUN: nothing written")
	return table.concat(report, "\n")
end
-- Everything checked: create the new pieces first, then write the scripts.
if not combat:FindFirstChild("GodlyFX") then
	local special = combat:FindFirstChild("SpecialFX")
	local fx = Instance.new("RemoteEvent")
	fx.Name = "GodlyFX"
	fx.Sandboxed = true
	fx.Capabilities = special and special.Capabilities
		or SecurityCapabilities.new(Enum.SecurityCapability.Basic, Enum.SecurityCapability.RemoteEvent)
	fx.Parent = combat
end
for _, n in NEW do
	local m = n[2]:FindFirstChild(n[3])
	if not m then
		m = Instance.new("ModuleScript")
		m.Name = n[3]
		m.Sandboxed = true
		m.Capabilities = n[4].Capabilities
		m.Parent = n[2]
	end
	m.Source = newSources[n[3]]
end
for _, w in writes do
	w.script.Source = w.source
end
for _, p in patched do
	p.script.Source = p.source
end
table.insert(report, "WROTE " .. #writes .. " scripts and " .. #NEW .. " new modules")
return table.concat(report, "\n")
