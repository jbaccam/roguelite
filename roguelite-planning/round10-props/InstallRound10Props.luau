-- Edit-time installer for the round 10 props (Desert Basin tombs, Volcanic Crater vents and debris).
-- Run through execute_luau in Edit with tools/dev_server.py on 127.0.0.1:8934 (it serves the manifests):
--   loadstring(game.HttpService:GetAsync('http://127.0.0.1:8934/round10-props/InstallRound10Props.luau'))()()
-- It finds the 3D Importer's models for Sarcophagus.fbx, SarcophagusBroken.fbx, VolcanicVent.fbx and
-- VolcanicDebris.fbx anywhere in Workspace by their mesh names, and builds:
--   ServerStorage.Round10Props.Sarcophagus        body (solid) + lid; pivot (PrimaryPart 'Pivot') at the
--     cavity floor centre on the ground, its LookVector out of the open face. The lid carries
--     'Hinge' (pivot space: the bottom front edge it falls forward about), Round10Service.buildTomb.
--   ServerStorage.Round10Props.SarcophagusBroken  the four chunks where they sat in the intact coffin,
--     same pivot convention (Round10Service drops it on a destroyed tomb's frame).
--   ServerStorage.Round10Props.VolcanicVent       Vent_Rock + Vent_Glow (Neon), pivot at the opening's
--     ground centre.
--   ReplicatedStorage.RogueliteCombat.Round10Assets.VolcanicDebris  five fragments (client debris).
-- Axes: the props were authored Blender +Z up, open face -Y; the importer's rotation is solved from the
-- coffin (the lid sits in front of the body) and reused for every kit, so one convention holds. A
-- Blender body-space point (x, y, z) is pivot-space (-x, z, y) (front -Y -> -Z, up +Z -> +Y).
-- SurfaceAppearance colour maps move to TextureID (MCP-era SurfaceAppearances render blank in Play).
-- The raw imports are left in Workspace for the user to delete; older templates are moved aside.
return function(server)
	assert(game.PlaceId == 107877054949326, "Installer is scoped to the roguelite place")
	assert(not game:GetService("RunService"):IsRunning(), "Install in Edit mode")
	local HS = game:GetService("HttpService")
	local base = (server or "http://127.0.0.1:8934/") .. "round10-props/exports/"
	local manifest = HS:JSONDecode(HS:GetAsync(base .. "props-manifest.json?t=" .. os.clock(), true))
	local offsets = HS:JSONDecode(HS:GetAsync(base .. "SarcophagusBroken-offsets.json?t=" .. os.clock(), true))
	local assets = manifest.assets
	local function v3(t) return Vector3.new(t[1], t[2], t[3]) end
	local function pivotSpace(b) return Vector3.new(-b.X, b.Z, b.Y) end -- Blender body space -> pivot space
	-- A fresh import in Workspace wins. The vent and debris (stored = true) may instead come from an
	-- earlier import kept in ServerStorage.Round10RawImports, so a coffin-only re-import still rebuilds
	-- every template; the coffin family always needs a fresh import.
	local function findMesh(name, stored)
		for _, d in workspace:GetDescendants() do
			if d:IsA("MeshPart") and d.Name == name and not d:FindFirstAncestor("Round10Event") then return d end
		end
		local raw = stored and game.ServerStorage:FindFirstChild("Round10RawImports")
		if raw then
			for _, d in raw:GetDescendants() do
				if d:IsA("MeshPart") and d.Name == name then return d end
			end
		end
	end
	local function flatten(p)
		for _, c in p:GetChildren() do
			if c:IsA("SurfaceAppearance") then
				if p.TextureID == "" and c.ColorMap ~= "" then p.TextureID = c.ColorMap end
				c:Destroy()
			end
		end
		p.Anchored = true; p.CanTouch = false; p.CastShadow = true
	end
	-- One mesh's authored info: Blender local bounds centre (relative to its origin) and size.
	local function info(file, mesh)
		local m = assert(assets[file] and assets[file].meshes[mesh], "manifest has no " .. file .. "/" .. mesh)
		local lo, hi = v3(m.boundsMinBlender), v3(m.boundsMaxBlender)
		return m, (lo + hi) / 2, hi - lo
	end
	local body = assert(findMesh("Sarcophagus_Body"), "Import Sarcophagus.fbx first")
	local lid = assert(findMesh("Sarcophagus_Lid"), "Sarcophagus_Lid missing")
	local bodyInfo, bodyLocalCenter, bodySize = info("Sarcophagus.fbx", "Sarcophagus_Body")
	-- Scale: the imported body's tallest side against its authored height.
	local s = bodySize.Z / math.max(body.Size.X, body.Size.Y, body.Size.Z)
	assert(s > 0.005 and s < 200, "bad import scale " .. s)
	-- Front (the open face) is where the lid sits; up is world +Y (checked against the body's shape).
	local F = Vector3.new(lid.Position.X - body.Position.X, 0, lid.Position.Z - body.Position.Z)
	assert(F.Magnitude > 0.1, "Cannot tell the coffin's front: lid on top of body")
	F = F.Unit
	local pivotRot = CFrame.lookAt(Vector3.zero, F)
	-- Each imported part's rotation relative to the pivot (the importer's, the same for every kit).
	local partRot = pivotRot:Inverse() * body.CFrame.Rotation
	-- Body origin (cavity floor centre, ground): its bounds centre minus the authored offset.
	local bodyCenter = body.Position
	-- (Import units: the authored offset divided by s.)
	local origin = bodyCenter - pivotRot:VectorToWorldSpace(pivotSpace(bodyLocalCenter + v3(bodyInfo.originBlender)) / s)
	local function template(name, parentFolder)
		local old = parentFolder:FindFirstChild(name)
		if old then
			local history = game.ServerStorage:FindFirstChild("Round10PropsHistory") or Instance.new("Folder")
			history.Name = "Round10PropsHistory"; history.Parent = game.ServerStorage
			old.Name = name .. "_before_" .. os.date("%Y%m%d_%H%M%S"); old.Parent = history
		end
		local m = Instance.new("Model"); m.Name = name
		local pivot = Instance.new("Part"); pivot.Name = "Pivot"; pivot.Size = Vector3.one * 0.2; pivot.Transparency = 1
		pivot.Anchored = true; pivot.CanCollide = false; pivot.CanQuery = false; pivot.CanTouch = false; pivot.CFrame = CFrame.new()
		pivot.Parent = m; m.PrimaryPart = pivot
		return m
	end
	-- Place `src` (an imported MeshPart) into model `m` at pivot-space position `at` (studs).
	local function put(m, src, at, name)
		local p = src:Clone(); flatten(p)
		p.Name = name or src.Name; p.Size = src.Size * s
		p.CFrame = CFrame.new(at) * partRot
		p.Parent = m
		return p
	end
	local store = game.ServerStorage:FindFirstChild("Round10Props") or Instance.new("Folder")
	store.Name = "Round10Props"; store.Parent = game.ServerStorage
	local report = {}
	-- Coffin: body + lid, both from their imported centres relative to the body origin.
	do
		local m = template("Sarcophagus", store)
		-- Imported positions relative to the origin, rotated into pivot space and scaled to studs.
		local function at(p) return pivotRot:Inverse():VectorToWorldSpace(p.Position - origin) * s end
		local b = put(m, body, at(body)); b.CanCollide = true; b.CanQuery = true
		local l = put(m, lid, at(lid)); l.CanCollide = false; l.CanQuery = true
		-- The hinge: the lid's bottom front edge, on the ground, |hinge y| in front of the origin.
		local hinge = assets["Sarcophagus.fbx"].lid and assets["Sarcophagus.fbx"].lid.hingeLineBodySpaceBlender or { 0, -3.47, 0 }
		l:SetAttribute("Hinge", CFrame.new(pivotSpace(v3(hinge)))) -- authored studs
		m:SetAttribute("SourceAsset", "round10-props/exports/Sarcophagus.fbx")
		m.Parent = store
		table.insert(report, ("Sarcophagus: scale %.4f, body %s, lid at %s"):format(s, tostring(b.Size), tostring(l.CFrame.Position)))
	end
	-- Broken kit: each chunk's bounds centre in body space (origin offset + local bounds centre).
	do
		local m = template("SarcophagusBroken", store)
		local n = 0
		for name, o in offsets.chunks do
			local src = findMesh(name)
			if src then
				local _, localCenter = info("SarcophagusBroken.fbx", name)
				local at = pivotSpace(v3(o.offsetBodySpaceBlender) + localCenter) -- authored studs
				local p = put(m, src, at); p.CanCollide = false; p.CanQuery = false
				n += 1
			end
		end
		assert(n == 4, "Expected 4 broken chunks, found " .. n .. " (import SarcophagusBroken.fbx)")
		m.Parent = store
		table.insert(report, "SarcophagusBroken: 4 chunks")
	end
	-- Vent: rock and glow about the opening's ground centre.
	do
		local rock, glow = findMesh("Vent_Rock", true), findMesh("Vent_Glow", true)
		assert(rock and glow, "Import VolcanicVent.fbx (Vent_Rock, Vent_Glow)")
		local m = template("VolcanicVent", store)
		for _, pair in { { rock, "Vent_Rock" }, { glow, "Vent_Glow" } } do
			local mi, localCenter = info("VolcanicVent.fbx", pair[2])
			local at = pivotSpace(localCenter + v3(mi.originBlender or { 0, 0, 0 })) -- authored studs
			local p = put(m, pair[1], at); p.CanCollide = false; p.CanQuery = false
			if pair[2] == "Vent_Glow" then p.Material = Enum.Material.Neon; p.Color = Color3.fromRGB(255, 120, 40) end
		end
		m.Parent = store
		table.insert(report, "VolcanicVent")
	end
	-- Debris: the five fragments, for the client's eruption debris.
	do
		local combat = game.ReplicatedStorage.RogueliteCombat
		local folder = combat:FindFirstChild("Round10Assets") or Instance.new("Folder")
		folder.Name = "Round10Assets"; folder.Parent = combat
		local m = folder:FindFirstChild("VolcanicDebris"); if m then m:Destroy() end
		m = Instance.new("Model"); m.Name = "VolcanicDebris"
		local n = 0
		for i = 1, 5 do
			local src = findMesh("Debris_" .. i, true)
			if src then
				local p = src:Clone(); flatten(p); p.Size = src.Size * s; p.CFrame = CFrame.new(i * 0.6, 0, 0) * partRot
				p.CanCollide = false; p.CanQuery = false; p.CastShadow = false; p.Parent = m; n += 1
			end
		end
		m.Parent = folder
		table.insert(report, "VolcanicDebris: " .. n .. " fragments")
	end
	return table.concat(report, "\n")
end
