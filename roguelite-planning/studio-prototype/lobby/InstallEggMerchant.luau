--!nonstrict
-- Edit-mode installer for the egg merchant on the quest-board island (Island_South_4), after ONE
-- Studio 3D Import of blender-egg-merchant-kit/exports/fbx/egg-merchant-studio.fbx (defaults).
-- Run with the repo's roguelite-planning folder served on localhost:
--   local HS = game:GetService("HttpService")
--   loadstring(HS:GetAsync("http://127.0.0.1:<port>/studio-prototype/lobby/InstallEggMerchant.luau"))()(
--     "http://127.0.0.1:<port>/", {eggTexture = "rbxassetid://…", merchantTexture = "rbxassetid://…", icon = "rbxassetid://…"})
--
-- Builds Workspace.RogueliteLobby.EggMerchant (ModelStreamingMode Persistent, like the chest island):
--   Egg       pedestal + nest + the pre-broken egg (EggStage). Kind: base | shell | shard | crack | inner;
--             shards carry Outward, cracks Stage. Model attributes: Hinge, EggBase, EggCentre.
--   Merchant  rigid parts posed by EggMerchant; each non-root part has Joint, JointParent, JointPivot.
--   Collision invisible boxes so players bump into the pedestal and the merchant.
-- and Workspace.RogueliteLobby.Stations.Eggs (StationId "Eggs", Icon): StationApproach draws the
-- walk-up ring in front of the merchant from its invisible `Interaction` part.
-- The practice dummy that stood there (Scenery.Practice_Dummy_86) moves to
-- ServerStorage.EggMerchantBackup, so putting it back is a drag. Re-running repairs in place.
-- Textured parts use MeshPart.TextureID (one uploaded atlas per group; a multi-model FBX import
-- gives every mesh the same texture, and SurfaceAppearance can render blank in Play).
-- opts.test: accept plain Parts as stand-ins for the meshes and leave the practice dummy alone
-- (an Edit-mode check of the fitting, assembly and placement before the real import).
-- opts.egg / opts.merchant: the two install-data tables, to run without the HTTP server.
return function(base, opts)
	base = base or "http://127.0.0.1:8857/"
	opts = opts or {}
	local HS = game:GetService("HttpService")
	local SS = game:GetService("ServerStorage")
	local lobby = workspace:WaitForChild("RogueliteLobby")
	local report = {}
	local function json(path)
		return HS:JSONDecode(HS:GetAsync(base .. "blender-egg-merchant-kit/" .. path, true))
	end
	local function v3(t)
		return Vector3.new(t[1], t[2], t[3])
	end
	local EGG = opts.egg or json("studio-install-data-egg.json")
	local MER = opts.merchant or json("studio-install-data-merchant.json")
	local partClass = opts.test and "BasePart" or "MeshPart"

	-- Where things stand (world): the dummy's spot, facing the path (+Z).
	local EGG_XZ = Vector2.new(-1401.94, 155.0)
	local MERCHANT_XZ = Vector2.new(-1393.6, 156.6)
	local MERCHANT_LOOK = Vector3.new(-0.34, 0, 0.94).Unit -- toward the path, turned a little toward the egg

	-- Every imported or already-installed part, by name.
	local root = lobby:FindFirstChild("EggMerchant")
	local found = {}
	local function want(name)
		return EGG.parts[name] ~= nil or MER.parts[name] ~= nil
	end
	for _, d in workspace:GetDescendants() do
		if d:IsA(partClass) and want(d.Name) then
			-- Prefer a fresh import over the installed copy when both exist.
			if not found[d.Name] or (root and found[d.Name]:IsDescendantOf(root)) then
				found[d.Name] = d
			end
		end
	end

	local TURNS = {}
	for _, rx in { 0, 90, 180, 270 } do
		for _, ry in { 0, 90, 180, 270 } do
			for _, rz in { 0, 90, 270 } do
				table.insert(TURNS, CFrame.Angles(math.rad(rx), math.rad(ry), math.rad(rz)))
			end
		end
	end
	-- Scale fix and the 90-degree turn that best maps the part layout (the importer may scale by
	-- 100 and lay the file on its back). Returns the group's authored pivot in the import's space.
	local function fit(data, baseName)
		local b = found[baseName]
		assert(b, baseName .. " not imported")
		local wantSize = v3(data.parts[baseName].size)
		local factor = math.max(b.Size.X, b.Size.Y, b.Size.Z) / math.max(wantSize.X, wantSize.Y, wantSize.Z)
		local R, best = CFrame.identity, math.huge
		for _, turn in TURNS do
			local err = 0
			for name, info in data.parts do
				local p = found[name]
				if p then
					local o = (v3(info.centre) - v3(data.parts[baseName].centre)) * factor
					err += ((p.Position - b.Position) - turn:VectorToWorldSpace(o)).Magnitude
				end
			end
			if err < best - 1e-3 then
				R, best = turn, err
			end
		end
		local origin = b.Position - R:VectorToWorldSpace(v3(data.parts[baseName].centre) * factor)
		return CFrame.new(origin) * R, factor, best
	end
	local function ground(xz, ignore)
		local params = RaycastParams.new()
		params.FilterType = Enum.RaycastFilterType.Exclude
		params.FilterDescendantsInstances = ignore
		local hit = workspace:Raycast(Vector3.new(xz.X, 160, xz.Y), Vector3.new(0, -80, 0), params)
		return hit and hit.Position.Y or 120
	end
	local function dress(p, textured, texture)
		local sa = p:FindFirstChildOfClass("SurfaceAppearance")
		if sa then
			if textured and not texture then
				texture = sa.ColorMap
			end
			sa:Destroy()
		end
		p.Anchored = true
		p.CanTouch = false
		p.Locked = true
		if textured then
			if p:IsA("MeshPart") then
				p.TextureID = texture or p.TextureID
			end
			p.Material = Enum.Material.SmoothPlastic
			p.Color = Color3.new(1, 1, 1)
			p.CastShadow = true
		else
			if p:IsA("MeshPart") then
				p.TextureID = ""
			end
			p.Material = Enum.Material.Neon
			p.CastShadow = false
		end
	end
	local function assemble(name, data, baseName, parts, scaleFrom)
		local pivot, factor, err = fit(data, baseName)
		local m = Instance.new("Model")
		m.Name = name
		for _, p in parts do
			p.Parent = m
		end
		m.PrimaryPart = found[baseName]
		found[baseName].PivotOffset = found[baseName].CFrame:ToObjectSpace(pivot)
		if math.abs(factor - 1) > 0.01 then
			m:ScaleTo(1 / factor)
		end
		local rx, ry, rz = (pivot - pivot.Position):ToEulerAnglesXYZ()
		table.insert(report, string.format("%s: %d parts, scale fix %.3f, turn (%d,%d,%d), fit error %.3f", name, #parts, factor, math.deg(rx), math.deg(ry), math.deg(rz), err))
		return m
	end

	-- Egg ---------------------------------------------------------------------------------------
	local eggParts = {}
	for name, info in EGG.parts do
		local p = found[name]
		if not p then
			table.insert(report, "missing egg part " .. name)
			continue
		end
		local kind = name:find("^Pedestal_") and "base"
			or name == "Egg_Bottom" and "shell"
			or name:find("^Egg_Top_") and "shard"
			or name:find("^Egg_Crack_") and "crack"
			or name:find("Inner") and "inner"
			or "base"
		dress(p, kind == "base" or kind == "shell" or kind == "shard", opts.eggTexture)
		p:SetAttribute("Kind", kind)
		p.CanCollide = false
		p.CanQuery = kind == "base"
		if kind == "crack" then
			p:SetAttribute("Stage", tonumber(name:match("(%d+)$")) or 1)
			p.Transparency = 1
		elseif kind == "inner" then
			p.Transparency = 1
		end
		local s = EGG.shards and EGG.shards[name]
		if s then
			p:SetAttribute("Outward", v3(s.outward))
		end
		table.insert(eggParts, p)
	end
	-- Shard order is the name order (Egg_Top_1..N) so flights alternate spin directions.
	table.sort(eggParts, function(a, b)
		return a.Name < b.Name
	end)

	-- Merchant ------------------------------------------------------------------------------------
	local merParts = {}
	for name in MER.parts do
		local p = found[name]
		if not p then
			table.insert(report, "missing merchant part " .. name)
			continue
		end
		dress(p, true, opts.merchantTexture)
		p.CanCollide = false
		p.CanQuery = false
		p:SetAttribute("Joint", nil)
		p:SetAttribute("JointParent", nil)
		p:SetAttribute("JointPivot", nil)
		table.insert(merParts, p)
	end
	for jname, j in MER.joints do
		local p = found[j.child]
		if p then
			p:SetAttribute("Joint", jname)
			p:SetAttribute("JointParent", j.parent)
			p:SetAttribute("JointPivot", v3(j.pivot))
		end
	end

	-- Replace the old install (its parts were picked up above and are reused).
	local backup = SS:FindFirstChild("EggMerchantBackup") or Instance.new("Folder")
	backup.Name = "EggMerchantBackup"
	backup.Parent = SS
	if root then
		for _, p in eggParts do
			p.Parent = nil
		end
		for _, p in merParts do
			p.Parent = nil
		end
		root:Destroy()
	end
	local eggModel = assemble("Egg", EGG, "Pedestal_Base", eggParts)
	local merModel = assemble("Merchant", MER, "Merchant_Hips", merParts)
	local e = EGG.egg
	local c = v3(e.centre)
	eggModel:SetAttribute("Hinge", CFrame.new(0, e.break_height, 0))
	eggModel:SetAttribute("EggCentre", c)
	eggModel:SetAttribute("EggBase", Vector3.new(c.X, c.Y - e.height / 2, c.Z))
	eggModel:SetAttribute("SourceFbx", "roguelite-planning/blender-egg-merchant-kit/exports/fbx/egg-merchant-studio.fbx")
	merModel:SetAttribute("SourceFbx", "roguelite-planning/blender-egg-merchant-kit/exports/fbx/egg-merchant-studio.fbx")

	-- The practice dummy that stood here goes to the backup folder.
	local dummy = lobby:FindFirstChild("Scenery") and lobby.Scenery:FindFirstChild("Practice_Dummy_86")
	if dummy and not opts.test and (Vector2.new(dummy.Position.X, dummy.Position.Z) - EGG_XZ).Magnitude < 3 then
		dummy.Parent = backup
		table.insert(report, "moved Practice_Dummy_86 to ServerStorage.EggMerchantBackup")
	end

	root = Instance.new("Model")
	root.Name = "EggMerchant"
	root.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
	local ignore = { root, eggModel, merModel, backup }
	if dummy then
		table.insert(ignore, dummy) -- test mode leaves it standing on the egg's spot
	end
	local eggY = ground(EGG_XZ, ignore)
	local merY = ground(MERCHANT_XZ, ignore)
	local eggPos = Vector3.new(EGG_XZ.X, eggY, EGG_XZ.Y)
	local merPos = Vector3.new(MERCHANT_XZ.X, merY, MERCHANT_XZ.Y)
	eggModel:PivotTo(CFrame.lookAt(eggPos, eggPos + Vector3.zAxis))
	merModel:PivotTo(CFrame.lookAt(merPos, merPos + MERCHANT_LOOK))
	eggModel.Parent = root
	merModel.Parent = root
	-- Collision: a box around the pedestal and egg, one around the merchant and his basket.
	local function box(name, cf, size)
		local b = Instance.new("Part")
		b.Name = name
		b.Anchored = true
		b.CanCollide = true
		b.CanQuery = false
		b.CanTouch = false
		b.Transparency = 1
		b.CastShadow = false
		b.Size = size
		b.CFrame = cf
		b.Parent = root
		return b
	end
	local _, eggSize = eggModel:GetBoundingBox()
	box("EggCollision", eggModel:GetPivot() * CFrame.new(0, eggSize.Y / 2, 0), Vector3.new(eggSize.X * 0.8, eggSize.Y, eggSize.Z * 0.8))
	box("MerchantCollision", merModel:GetPivot() * CFrame.new(0, 3.2, 0.35), Vector3.new(3, 6.4, 3))
	root.Parent = lobby

	-- The walk-up stand: a tall invisible Interaction part in front of the merchant, so the ring sits
	-- 3.4 studs in front of him and the EGGS label floats over his basket.
	local stations = lobby:WaitForChild("Stations")
	local old = stations:FindFirstChild("Eggs")
	if old then
		old:Destroy()
	end
	local stand = Instance.new("Model")
	stand.Name = "Eggs"
	stand:SetAttribute("StationId", "Eggs")
	if opts.icon then
		stand:SetAttribute("Icon", opts.icon)
	end
	local inter = Instance.new("Part")
	inter.Name = "Interaction"
	inter.Anchored = true
	inter.CanCollide = false
	inter.CanQuery = false
	inter.CanTouch = false
	inter.Transparency = 1
	inter.CastShadow = false
	inter.Size = Vector3.new(1, 15, 1)
	local front = merPos + MERCHANT_LOOK * 1.2
	inter.CFrame = CFrame.lookAt(front, front + MERCHANT_LOOK)
	inter.Parent = stand
	stand.PrimaryPart = inter
	stand.Parent = stations

	table.insert(report, string.format("egg at %.1f,%.1f,%.1f; merchant at %.1f,%.1f,%.1f", eggPos.X, eggPos.Y, eggPos.Z, merPos.X, merPos.Y, merPos.Z))
	-- Remove the emptied import shell (the importer names its root after the file).
	for _, ch in workspace:GetChildren() do
		if string.find(string.lower(ch.Name), "egg%-merchant") and not ch:FindFirstChildWhichIsA("BasePart", true) then
			ch:Destroy()
		end
	end
	return table.concat(report, "\n")
end
