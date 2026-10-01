-- Edit-mode sync of the roguelite UI scripts from this repo into Studio, safe against Studio-only
-- edits. Serve two folders first:
--   python -m http.server 8765 --bind 127.0.0.1 --directory roguelite-planning   (current files)
--   python -m http.server 8791 --bind 127.0.0.1 --directory <dir with the HEAD copies>
-- The HEAD dir holds `git show HEAD:roguelite-planning/studio-prototype/ui/<File>` saved as
-- ui/<File>. Then paste this file into execute_luau (Edit).
-- Each script is found by name (outside ServerStorage backups). It is written only when every line
-- Studio has beyond the last commit also exists in the repo file, i.e. writing loses nothing. If
-- Studio holds lines the repo lacks (someone edited Studio directly), it is skipped and those lines
-- are listed: port them into the repo first, then sync again. Set DRY = true to only report.
assert(not game:GetService("RunService"):IsRunning(), "Run the sync in Edit mode")
local DRY = false
local Http = game:GetService("HttpService")
local FILES = {
	"UITheme.luau",
	"UILayoutAudit.luau",
	"ArmoryUI.luau",
	"ArmoryStage.luau",
	"LobbyUI.luau",
	"ChestScreenUI.luau",
	"ChestStage.luau",
	"ChestFX.luau",
	"SkillTreeUI.luau",
	"RunSetupUI.luau",
	"MapSelectBackdrop.luau",
	"RogueliteUI.luau",
	"ShopUI.luau",
	"LevelUpUI.luau",
	"DeathScreenUI.luau",
	"RogueliteHUD.client.luau",
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
-- Trimmed non-empty lines with how often each appears.
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
		if d:IsA("LuaSourceContainer") and d.Name == name and not d:IsDescendantOf(game.ServerStorage) then
			table.insert(hits, d)
		end
	end
	return hits
end
local report = {}
for _, file in FILES do
	local name = file:gsub("%.client%.luau$", ""):gsub("%.server%.luau$", ""):gsub("%.luau$", "")
	local cur = get("http://127.0.0.1:8765/studio-prototype/ui/" .. file)
	local head = get("http://127.0.0.1:8791/ui/" .. file)
	local hits = find(name)
	if not cur then
		table.insert(report, "NO REPO FILE " .. file)
	elseif #hits ~= 1 then
		table.insert(report, "FOUND " .. #hits .. " scripts named " .. name .. " - skipped")
	else
		local s = hits[1]
		local studioOnly = {}
		if head then
			local h, c = lines(head), lines(cur)
			for l, n in lines(s.Source) do
				if n > (h[l] or 0) and not c[l] then
					table.insert(studioOnly, l:sub(1, 100))
				end
			end
		end
		if norm(s.Source) == norm(cur) then
			table.insert(report, "same " .. s:GetFullName())
		elseif not head then
			table.insert(report, "NO HEAD COPY for " .. file .. " - skipped")
		elseif #studioOnly > 0 then
			table.insert(report, "STUDIO-ONLY EDITS in " .. s:GetFullName() .. " - skipped:\n   " .. table.concat(studioOnly, "\n   "))
		elseif DRY then
			table.insert(report, "would write " .. s:GetFullName())
		else
			s.Source = unix(cur)
			table.insert(report, "WROTE " .. s:GetFullName())
		end
	end
end
return table.concat(report, "\n")
