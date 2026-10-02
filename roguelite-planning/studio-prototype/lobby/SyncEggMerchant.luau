--!nonstrict
-- Edit-mode sync for the egg merchant's scripts. Run with the repo's roguelite-planning folder served
-- on localhost (python -m http.server <port> --bind 127.0.0.1):
--   local HS = game:GetService("HttpService")
--   loadstring(HS:GetAsync("http://127.0.0.1:<port>/studio-prototype/lobby/SyncEggMerchant.luau"))()("http://127.0.0.1:<port>/")
--
-- 1. Creates or updates the egg merchant's own modules. They are UNSANDBOXED, like ChestConfig,
--    ChestStage and ChestScreenUI, because only unsandboxed scripts require them (ProfileService,
--    RogueliteMeta, LobbyUI) and they play sounds through the unsandboxed ChestFX.
-- 2. Adds the hunks in lobby/egg-merchant-hunks.json to the shared scripts, next to their anchor
--    lines, and changes nothing else in them: Studio and the repo both carry other sessions' edits
--    to ProfileService, RogueliteMeta and LobbyUI, so those files are never pushed whole.
-- All or nothing: every source compiles and every anchor is found once before anything is written.
-- Returns a report string. Pass dryRun=true to check without writing.
return function(base, dryRun)
	base = base or "http://127.0.0.1:8857/"
	local HS = game:GetService("HttpService")
	local RS = game:GetService("ReplicatedStorage")
	local History = game:GetService("ChangeHistoryService")
	local report = {}
	local function get(path)
		return (HS:GetAsync(base .. "studio-prototype/" .. path .. "?t=" .. os.clock(), true):gsub("\r\n", "\n"))
	end
	local function compiles(name, src)
		local fn, err = loadstring(src, "=" .. name)
		return fn ~= nil, err
	end

	local MODULES = {
		{ path = "combat/EggConfig.luau", parent = RS:WaitForChild("RogueliteCombat"), name = "EggConfig" },
		{ path = "ui/EggMerchant.luau", parent = RS, name = "EggMerchant" },
		{ path = "ui/EggStage.luau", parent = RS, name = "EggStage" },
		{ path = "ui/EggScreenUI.luau", parent = RS, name = "EggScreenUI" },
	}
	for _, m in MODULES do
		m.source = get(m.path)
		local ok, err = compiles(m.name, m.source)
		if not ok then
			return "ABORT: " .. m.path .. " does not compile: " .. tostring(err)
		end
	end

	-- Hunks, grouped per Studio script.
	local hunks = HS:JSONDecode(get("lobby/egg-merchant-hunks.json"))
	local targets, order = {}, {}
	local function resolve(path)
		local parts = string.split(path, ".")
		local inst = game:GetService(parts[1])
		for i = 2, #parts do
			inst = inst and inst:FindFirstChild(parts[i])
		end
		return inst
	end
	for _, h in hunks do
		if not h.studio then
			continue -- repo-only (the Rojo project file)
		end
		local t = targets[h.studio]
		if not t then
			local inst = resolve(h.studio)
			if not inst then
				return "ABORT: " .. h.studio .. " not found"
			end
			t = { inst = inst, source = inst.Source:gsub("\r\n", "\n"), added = 0, present = 0 }
			targets[h.studio] = t
			table.insert(order, h.studio)
		end
		if string.find(t.source, h.text, 1, true) then
			t.present += 1
		else
			local lines = string.split(t.source, "\n")
			local at, hits = nil, 0
			for i, l in lines do
				if l == h.anchor then
					at = i
					hits += 1
				end
			end
			if hits ~= 1 then
				return "ABORT: anchor found " .. hits .. " times in " .. h.studio .. ": " .. h.anchor
			end
			local ins = string.split(h.text, "\n")
			local pos = h.where == "after" and at + 1 or at
			for k, l in ins do
				table.insert(lines, pos + k - 1, l)
			end
			t.source = table.concat(lines, "\n")
			t.added += 1
		end
	end
	for _, path in order do
		local t = targets[path]
		local ok, err = compiles(path, t.source)
		if not ok then
			return "ABORT: patched " .. path .. " does not compile: " .. tostring(err)
		end
	end
	if dryRun then
		for _, path in order do
			table.insert(report, path .. ": " .. targets[path].added .. " to add, " .. targets[path].present .. " present")
		end
		return "DRY RUN\n" .. table.concat(report, "\n")
	end

	-- Write: modules first (LobbyUI's hunk requires EggScreenUI), then the hunks.
	History:SetWaypoint("Before egg merchant sync")
	for _, m in MODULES do
		local inst = m.parent:FindFirstChild(m.name)
		local created = false
		if not inst then
			inst = Instance.new("ModuleScript")
			inst.Name = m.name
			created = true
		end
		pcall(function()
			inst.Sandboxed = false
		end)
		if inst.Source:gsub("\r\n", "\n") ~= m.source then
			inst.Source = m.source
			table.insert(report, m.name .. (created and ": created" or ": updated"))
		else
			table.insert(report, m.name .. ": unchanged")
		end
		inst.Parent = m.parent
	end
	for _, path in order do
		local t = targets[path]
		if t.added > 0 then
			t.inst.Source = t.source
		end
		table.insert(report, path .. ": " .. t.added .. " hunks added, " .. t.present .. " already there")
	end
	History:SetWaypoint("Egg merchant sync")
	return table.concat(report, "\n")
end
