--!nonstrict
-- All-or-nothing Studio sync of whole scripts (launch work, 2026-10-02). Like SyncPlan, but each
-- entry names its class (ModuleScript, Script or LocalScript) and its guard is the exact Source
-- Studio had when the manifest was built (a file the dev server serves), so a script that matched
-- "a commit plus another plan's hunks" can be guarded too. tools/launch_sync.py builds the manifest
-- from a Studio dump. With tools/dev_server.py running, call from execute_luau:
--   local HS=game:GetService('HttpService');local base='http://127.0.0.1:8934/'
--   return loadstring(HS:GetAsync(base..'studio-prototype/tools/LaunchSync.luau?t='..os.clock(),true))()(base,'studio-prototype/tools/_launchsync/manifest.json',true)
-- Manifest: {rev, scripts={{studio, repo, class, guard (served path, or nil for a new script),
-- sandboxLike (dot path, new scripts)}}, remotes={{parent, name, class, sandboxLike}}}.
-- A script is written only if Studio's Source still equals its guard (or is already the new
-- source); a new one only if nothing has that name yet. Every new source must compile first.
-- dryRun reports without writing.
return function(base, manifestPath, dryRun)
	local HS = game:GetService("HttpService")
	local History = game:GetService("ChangeHistoryService")
	local function get(path)
		return (HS:GetAsync(base .. path .. "?t=" .. os.clock(), true):gsub("\r\n", "\n"))
	end
	local function resolve(path)
		local parts = string.split(path, ".")
		local ok, inst = pcall(function()
			return game:GetService(parts[1])
		end)
		inst = ok and inst or nil
		for i = 2, #parts do
			inst = inst and inst:FindFirstChild(parts[i])
		end
		return inst
	end
	local function split(path)
		local parts = string.split(path, ".")
		local name = table.remove(parts)
		return table.concat(parts, "."), name
	end
	local manifest = HS:JSONDecode(get(manifestPath))
	local plan, report = {}, {}
	for _, e in manifest.scripts do
		local parentPath, name = split(e.studio)
		local parent = resolve(parentPath)
		if not parent then
			return "ABORT: " .. parentPath .. " not found"
		end
		local source = get("git/" .. manifest.rev .. "/studio-prototype/" .. e.repo)
		local fn, err = loadstring(source, "=" .. e.repo)
		if not fn then
			return "ABORT: " .. e.repo .. " does not compile: " .. tostring(err)
		end
		local inst = parent:FindFirstChild(name)
		if inst and not inst:IsA(e.class) then
			return "ABORT: " .. e.studio .. " is a " .. inst.ClassName .. ", expected " .. e.class
		end
		local state
		if inst then
			local now = inst.Source:gsub("\r\n", "\n")
			if now == source then
				state = "unchanged"
			elseif e.guard and now == get(e.guard) then
				state = "update"
			else
				return "ABORT: Studio's " .. e.studio .. " changed since the manifest was built (edited in Studio?); merge it by hand"
			end
		else
			if e.guard then
				return "ABORT: " .. e.studio .. " is missing but the manifest expected it"
			end
			state = "create"
		end
		table.insert(plan, { e = e, parent = parent, name = name, inst = inst, source = source, state = state })
	end
	for _, r in manifest.remotes or {} do
		if not resolve(r.parent) then
			return "ABORT: " .. r.parent .. " not found (remote " .. r.name .. ")"
		end
	end
	if dryRun then
		for _, p in plan do
			table.insert(report, p.e.studio .. ": " .. p.state)
		end
		for _, r in manifest.remotes or {} do
			table.insert(report, r.parent .. "." .. r.name .. ": " .. (resolve(r.parent):FindFirstChild(r.name) and "exists" or "would create " .. r.class))
		end
		return "DRY RUN (" .. manifest.rev .. ")\n" .. table.concat(report, "\n")
	end

	History:SetWaypoint("Before launch sync " .. manifest.rev)
	local function copyCaps(inst, likePath)
		local like = likePath and resolve(likePath)
		if like then
			pcall(function()
				inst.Sandboxed = like.Sandboxed
			end)
			pcall(function()
				inst.Capabilities = like.Capabilities
			end)
		end
	end
	for _, r in manifest.remotes or {} do
		local parent = resolve(r.parent)
		if not parent:FindFirstChild(r.name) then
			local ev = Instance.new(r.class)
			ev.Name = r.name
			copyCaps(ev, r.sandboxLike)
			ev.Parent = parent
			table.insert(report, r.parent .. "." .. r.name .. ": created")
		end
	end
	for _, p in plan do
		if p.state == "create" then
			local inst = Instance.new(p.e.class)
			inst.Name = p.name
			copyCaps(inst, p.e.sandboxLike)
			inst.Source = p.source
			inst.Parent = p.parent
		elseif p.state == "update" then
			p.inst.Source = p.source
		end
		table.insert(report, p.e.studio .. ": " .. p.state)
	end
	History:SetWaypoint("After launch sync " .. manifest.rev)
	return table.concat(report, "\n")
end
