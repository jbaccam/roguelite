-- Edit-mode sync for plan I (run end, Gear Power, analytics), safe against Studio-only edits.
-- Run only after the user says to push it to Studio. Serve two folders first (pick free ports):
--   cur:  the files as committed by plan I   (git archive / git show <commit>:<path>)
--   base: the same files one commit earlier   (what Studio is expected to hold)
-- e.g. python -m http.server 8812 --bind 127.0.0.1 --directory <cur dir>
--      python -m http.server 8813 --bind 127.0.0.1 --directory <base dir>
-- Both dirs mirror `studio-prototype/` (combat/..., lobby/..., ui/...). Then paste this into
-- execute_luau (Edit).
-- All or nothing: a script is planned for writing only when every line Studio has beyond `base`
-- also exists in `cur` (writing loses nothing). If any script would lose a Studio-only edit, or is
-- missing or ambiguous, nothing is written and the report says why. New modules are created
-- with the sandbox setting their requirers need.
assert(not game:GetService("RunService"):IsRunning(), "Run the sync in Edit mode")
local DRY = true -- set false to write
local CUR, BASE = "http://127.0.0.1:8812/", "http://127.0.0.1:8813/"
local Http = game:GetService("HttpService")
local SSS, RS, SS = game:GetService("ServerScriptService"), game:GetService("ReplicatedStorage"), game:GetService("ServerStorage")
-- Order: modules before the scripts that require them.
local FILES = {
	{ "combat/CharacterStats.luau", "CharacterStats" },
	{ "lobby/RunSetupRules.luau", "RunSetupRules" },
	{ "combat/CharacterService.luau", "CharacterService" },
	{ "combat/CombatEffectsService.luau", "CombatEffectsService" },
	{ "combat/ShopService.luau", "ShopService" },
	{ "combat/ProfileService.luau", "ProfileService" },
	{ "combat/RunAnalytics.luau", "RunAnalytics", new = { parent = SSS, sandboxed = false } },
	{ "combat/RogueliteMeta.server.luau", "RogueliteMeta" },
	{ "ui/RunResultsUI.luau", "RunResultsUI", new = { parent = RS, sandboxed = false } },
	{ "ui/DeathScreenUI.luau", "DeathScreenUI" },
	{ "ui/ShopUI.luau", "ShopUI" },
	{ "ui/RogueliteUI.luau", "RogueliteUI" },
	{ "ui/RunSetupUI.luau", "RunSetupUI" },
	{ "ui/ArmoryUI.luau", "ArmoryUI" },
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
local function find(name)
	local hits = {}
	for _, d in game:GetDescendants() do
		if d:IsA("LuaSourceContainer") and d.Name == name and not d:IsDescendantOf(SS) then
			table.insert(hits, d)
		end
	end
	return hits
end
local plan, report, blocked = {}, {}, false
for _, f in FILES do
	local path, name = f[1], f[2]
	local cur, base = get(CUR .. path), get(BASE .. path)
	local hits = find(name)
	if not cur then
		blocked = true
		table.insert(report, "NO CURRENT FILE " .. path)
	elseif #hits == 0 and f.new then
		table.insert(plan, { create = f.new, name = name, src = cur })
		table.insert(report, "create " .. f.new.parent:GetFullName() .. "." .. name)
	elseif #hits ~= 1 then
		blocked = true
		table.insert(report, "FOUND " .. #hits .. " scripts named " .. name)
	elseif norm(hits[1].Source) == norm(cur) then
		table.insert(report, "same " .. hits[1]:GetFullName())
	else
		local studioOnly = {}
		local b, c = lines(base or ""), lines(cur)
		for l, n in lines(hits[1].Source) do
			if n > (b[l] or 0) and not c[l] then
				table.insert(studioOnly, l:sub(1, 100))
			end
		end
		if not base or #studioOnly > 0 then
			blocked = true
			table.insert(report, "STUDIO-ONLY EDITS in " .. hits[1]:GetFullName() .. ":\n   " .. table.concat(studioOnly, "\n   "))
		else
			table.insert(plan, { script = hits[1], src = cur })
			table.insert(report, "write " .. hits[1]:GetFullName())
		end
	end
end
if blocked then
	return "NOTHING WRITTEN\n" .. table.concat(report, "\n")
end
if DRY then
	return "DRY RUN\n" .. table.concat(report, "\n")
end
for _, p in plan do
	if p.create then
		local m = Instance.new("ModuleScript")
		m.Name = p.name
		m.Source = unix(p.src)
		m.Sandboxed = p.create.sandboxed
		m.Parent = p.create.parent
	else
		p.script.Source = unix(p.src)
	end
end
return "WROTE\n" .. table.concat(report, "\n")
