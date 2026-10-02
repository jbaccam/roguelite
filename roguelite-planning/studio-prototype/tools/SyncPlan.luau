--!nonstrict
-- Edit-mode Studio sync for a plan's changes (plan K; generalizes lobby/SyncEggMerchant.luau). With
-- tools/dev_server.py running, call from execute_luau:
--   local HS=game:GetService('HttpService')
--   local base='http://127.0.0.1:8934/'
--   return loadstring(HS:GetAsync(base..'studio-prototype/tools/SyncPlan.luau?t='..os.clock(),true))()(base,'studio-prototype/combat/plan-k-sync.json',true)
-- The manifest (a plan's *_hunks.py --json) has:
--   modules: {path, parent (dot path), name, base (git rev), sandboxLike (dot path, optional)}:
--     whole modules the plan owns. One is written only if Studio's Source is still what `base`
--     committed (or already the new source), so an edit made in Studio since is never overwritten.
--     A new module copies Sandboxed and Capabilities from sandboxLike.
--   hunks: {repo, studio, anchor, where, text}: anchored edits to shared scripts ('after', 'before',
--     'replace', or 'block' with anchor {first, last}).
-- All or nothing: every module and patched script compiles, every anchor matches once and every
-- guard passes before anything is written. dryRun reports without writing. Returns a report.
return function(base, manifestPath, dryRun)
	local HS = game:GetService("HttpService")
	local History = game:GetService("ChangeHistoryService")
	local function get(path)
		return (HS:GetAsync(base .. path .. "?t=" .. os.clock(), true):gsub("\r\n", "\n"))
	end
	local function compiles(name, src)
		local fn, err = loadstring(src, "=" .. name)
		return fn ~= nil, err
	end
	local function resolve(path)
		local parts = string.split(path, ".")
		local inst = game:GetService(parts[1])
		for i = 2, #parts do
			inst = inst and inst:FindFirstChild(parts[i])
		end
		return inst
	end
	local manifest = HS:JSONDecode(get(manifestPath))
	local report = {}

	local modules = {}
	for _, m in manifest.modules or {} do
		local parent = resolve(m.parent)
		if not parent then
			return "ABORT: " .. m.parent .. " not found"
		end
		local source = get("studio-prototype/" .. m.path)
		local ok, err = compiles(m.name, source)
		if not ok then
			return "ABORT: " .. m.path .. " does not compile: " .. tostring(err)
		end
		local inst = parent:FindFirstChild(m.name)
		if inst then
			local now = inst.Source:gsub("\r\n", "\n")
			if now ~= source then
				local okBase, was = pcall(get, "git/" .. m.base .. "/studio-prototype/" .. m.path)
				if not okBase or now ~= was then
					return "ABORT: Studio's " .. m.parent .. "." .. m.name .. " is not the " .. m.base .. " version (edited in Studio, or Studio lags); merge it by hand"
				end
			end
		end
		table.insert(modules, { m = m, parent = parent, inst = inst, source = source })
	end

	local targets, order = {}, {}
	for _, h in manifest.hunks or {} do
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
			local function find(a)
				local at, hits = nil, 0
				for i, l in lines do
					if l == a then
						at, hits = i, hits + 1
					end
				end
				return at, hits
			end
			local ins = string.split(h.text, "\n")
			if h.where == "block" then
				local a, na = find(h.anchor[1])
				local z, nz = find(h.anchor[2])
				if na ~= 1 or nz ~= 1 or z < a then
					return "ABORT: block anchors in " .. h.studio .. " found " .. na .. "/" .. nz .. " times: " .. h.anchor[1]
				end
				for _ = a, z do
					table.remove(lines, a)
				end
				for k, l in ins do
					table.insert(lines, a + k - 1, l)
				end
			else
				local at, hits = find(h.anchor)
				if hits ~= 1 then
					return "ABORT: anchor found " .. hits .. " times in " .. h.studio .. ": " .. h.anchor
				end
				if h.where == "replace" then
					table.remove(lines, at)
				end
				local pos = h.where == "after" and at + 1 or at
				for k, l in ins do
					table.insert(lines, pos + k - 1, l)
				end
			end
			t.source = table.concat(lines, "\n")
			t.added += 1
		end
	end
	for _, path in order do
		local ok, err = compiles(path, targets[path].source)
		if not ok then
			return "ABORT: patched " .. path .. " does not compile: " .. tostring(err)
		end
	end

	if dryRun then
		for _, e in modules do
			table.insert(report, e.m.name .. ": " .. (not e.inst and "would create" or e.inst.Source:gsub("\r\n", "\n") == e.source and "unchanged" or "would update"))
		end
		for _, path in order do
			table.insert(report, path .. ": " .. targets[path].added .. " to add, " .. targets[path].present .. " present")
		end
		return "DRY RUN\n" .. table.concat(report, "\n")
	end

	History:SetWaypoint("Before " .. manifestPath)
	for _, e in modules do
		local inst, created = e.inst, false
		if not inst then
			inst = Instance.new("ModuleScript")
			inst.Name = e.m.name
			created = true
			local like = e.m.sandboxLike and resolve(e.m.sandboxLike)
			if like then
				pcall(function()
					inst.Sandboxed = like.Sandboxed
				end)
				pcall(function()
					inst.Capabilities = like.Capabilities
				end)
			end
		end
		if inst.Source:gsub("\r\n", "\n") ~= e.source then
			inst.Source = e.source
			table.insert(report, e.m.name .. (created and ": created" or ": updated"))
		else
			table.insert(report, e.m.name .. ": unchanged")
		end
		inst.Parent = e.parent
	end
	for _, path in order do
		local t = targets[path]
		if t.added > 0 then
			t.inst.Source = t.source
		end
		table.insert(report, path .. ": " .. t.added .. " hunks added, " .. t.present .. " already there")
	end
	History:SetWaypoint("After " .. manifestPath)
	return table.concat(report, "\n")
end
