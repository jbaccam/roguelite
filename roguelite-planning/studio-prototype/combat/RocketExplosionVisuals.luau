-- True 3D meshes and animation authored in Cartoon_Rocket_3D.blend.
-- Visual-only. mount(folder) returns the existing rocket Impact callback contract.
local Run = game:GetService("RunService")
local Assets = game:GetService("AssetService")
local Http = game:GetService("HttpService")
local M = {}
local data, records, templates = nil, {}, {}
local keepAlive = {}
local status -- nil until warm(), then 'building', 'ready' or 'failed'
local function rgb(v)
	local function s(x)
		return x <= 0.0031308 and x * 12.92 or 1.055 * x ^ (1 / 2.4) - 0.055
	end
	return Color3.new(s(v[1]), s(v[2]), s(v[3]))
end
local function build()
	if data then
		return
	end
	local chunks = script:WaitForChild("Data"):GetChildren()
	table.sort(chunks, function(a, b)
		return a.Name < b.Name
	end)
	local strings = {}
	-- One chunk per frame: the build started on a launch or an equip, not a loading screen.
	for _, chunk in chunks do
		task.wait()
		table.insert(strings, require(chunk))
	end
	local decoded = Http:JSONDecode(table.concat(strings))
	local ringOverride = script:FindFirstChild("RingOverride")
	if ringOverride then
		decoded.templates.Ring = require(ringOverride)
	end
	for name, r in decoded.templates do
		local mesh = assert(Assets:CreateEditableMesh(), "Could not allocate cartoon mesh")
		local ids = {}
		for i, v in r.v do
			ids[i] = mesh:AddVertex(Vector3.new(table.unpack(v)))
		end
		for i, f in r.f do
			local face = mesh:AddTriangle(ids[f[1]], ids[f[2]], ids[f[3]])
			-- Colors are immutable after construction; equal corner alphas can share an ID.
			local color = rgb(r.c[i])
			local a1, a2, a3 = r.a and r.a[f[1]] or 1, r.a and r.a[f[2]] or 1, r.a and r.a[f[3]] or 1
			local c1 = mesh:AddColor(color, a1)
			local c2 = a2 == a1 and c1 or mesh:AddColor(color, a2)
			local c3 = a3 == a1 and c1 or a3 == a2 and c2 or mesh:AddColor(color, a3)
			mesh:SetFaceColors(face, { c1, c2, c3 })
			if r.n then
				local normals = {}
				for _, n in r.n[i] do
					table.insert(normals, mesh:AddNormal(Vector3.new(table.unpack(n))))
				end
				mesh:SetFaceNormals(face, normals)
			end
		end
		local fixed = assert(
			Assets:CreateEditableMeshAsync(Content.fromObject(mesh), { FixedSize = true }),
			"Fixed mesh allocation failed"
		)
		mesh:Destroy()
		table.insert(keepAlive, fixed)
		local part = Assets:CreateMeshPartAsync(Content.fromObject(fixed))
		part.Name = name
		part.Anchored = true
		part.CanCollide = false
		part.CanTouch = false
		part.CanQuery = false
		part.CastShadow = false
		if name == "Ring" then
			part.DoubleSided = true
		end
		part.Material = r.glow and Enum.Material.Neon or Enum.Material.SmoothPlastic
		part.Color = Color3.new(1, 1, 1)
		templates[name] = { part = part, size = Vector3.new(table.unpack(r.size)) }
		task.wait()
	end
	for _, r in decoded.objects do
		local keys = {}
		for _, k in r.keys do
			keys[k[1]] =
				{ pose = CFrame.new(k[2], k[3], k[4], k[6], k[7], k[8], k[5]), scale = Vector3.new(k[9], k[10], k[11]) }
		end
		r.keys = keys
		r.color = rgb(r.color)
		table.insert(records, r)
	end
	data = decoded
end
-- Builds the meshes on first need (RocketVisuals: a rocket launcher equipped, or a rocket
-- launched) instead of at client start: 19 data chunks and EditableMeshes most sessions never
-- use. Impacts before it is ready play PreviousExplosion, as during the old start-up build.
function M.warm()
	if status then
		return
	end
	status = "building"
	task.spawn(function()
		local ok, err = pcall(build)
		status = ok and "ready" or "failed"
		if not ok then
			warn("Cartoon rocket build failed: " .. tostring(err))
		end
	end)
end
function M.mount(visuals, options)
	options = options or {}
	assert(Run:IsClient(), "Cartoon rocket visuals must run on the client")
	local active = {}
	local fallback
	local previous = script:FindFirstChild("PreviousExplosion")
	local function play(position, radius)
		if not visuals.Parent then
			return
		end
		if status ~= "ready" then
			M.warm()
			if previous then
				if not fallback then
					fallback = require(previous).mount(visuals)
				end
				fallback(position, radius)
			end
			return
		end
		local camera = workspace.CurrentCamera
		if not options.preview and camera and (camera.CFrame.Position - position).Magnitude > 180 then
			return
		end
		for i = #active, 1, -1 do
			if not active[i].folder.Parent then
				table.remove(active, i)
			end
		end
		if #active >= 3 then
			table.remove(active, 1).folder:Destroy()
		end
		local scale = math.clamp((radius or 9) / 9, 0.3, 2)
		local params = RaycastParams.new()
		params.FilterType = Enum.RaycastFilterType.Exclude
		params.RespectCanCollide = true
		local exclude = { visuals }
		local enemies = workspace:FindFirstChild("RogueliteEnemies")
		if enemies then
			table.insert(exclude, enemies)
		end
		for _, p in game.Players:GetPlayers() do
			if p.Character then
				table.insert(exclude, p.Character)
			end
		end
		params.FilterDescendantsInstances = exclude
		if options.ground then
			params.FilterType = Enum.RaycastFilterType.Include
			params.FilterDescendantsInstances = { options.ground }
			params.RespectCanCollide = false
		end
		local hit = workspace:Raycast(position + Vector3.yAxis * 2, -Vector3.yAxis * 12, params)
		local origin = hit and Vector3.new(position.X, hit.Position.Y + 0.06, position.Z) or position
		local folder = Instance.new("Folder")
		folder.Name = "CartoonRocket3D_Burst"
		folder.Parent = visuals
		local entry = { folder = folder, began = os.clock(), origin = CFrame.new(origin), scale = scale, objects = {} }
		for _, r in records do
			local t = templates[r.template]
			local part = t.part:Clone()
			part.Name = r.name
			part.Color = r.color
			part.Transparency = 1
			part.Parent = folder
			table.insert(entry.objects, { record = r, part = part, size = t.size })
		end
		table.insert(active, entry)
	end
	local connection
	connection = Run.RenderStepped:Connect(function()
		if not visuals.Parent then
			connection:Disconnect()
			for _, a in active do
				a.folder:Destroy()
			end
			return
		end
		for i = #active, 1, -1 do
			local e = active[i]
			local frame = (os.clock() - e.began) * 65 + 1
			if frame > 75 or not e.folder.Parent then
				e.folder:Destroy()
				table.remove(active, i)
			else
				local lo = math.floor(frame)
				local hi = math.min(lo + 1, 75)
				local blend = frame - lo
				for _, o in e.objects do
					local a = o.record.keys[lo]
					local b = o.record.keys[hi]
					local size = a.scale:Lerp(b.scale, blend) * o.size * e.scale
					if math.max(size.X, size.Y, size.Z) < 0.012 then
						o.part.Transparency = 1
					else
						local pose = a.pose:Lerp(b.pose, blend)
						-- Keep the blast low; retain the pressure ring's ground alignment.
						local offset = pose.Position * e.scale
						if o.record.template ~= "Ring" then
							offset = Vector3.new(offset.X, offset.Y * 0.55, offset.Z)
							size = Vector3.new(size.X, size.Y * 0.75, size.Z)
						end
						o.part.Size =
							Vector3.new(math.max(size.X, 0.001), math.max(size.Y, 0.001), math.max(size.Z, 0.001))
						o.part.CFrame = e.origin * CFrame.new(offset) * pose.Rotation
						o.part.Transparency = o.record.template == "Ring" and math.clamp((frame - 3) / 11, 0, 1) or 0
					end
				end
			end
		end
	end)
	return play
end
return M
