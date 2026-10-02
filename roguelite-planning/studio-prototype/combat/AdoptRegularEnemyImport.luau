-- Studio edit-time tool (not mapped into the production tree). After Studio's
-- 3D Importer brings in a rebuilt enemy FBX (workspace["<id>-rebuild"]), this
-- normalises it exactly like the original raw imports (ScaleTo 0.01, RootPart
-- at the origin), keeps the previous raw import under
-- ServerStorage.RegularEnemyRawImportsHistory, files the new one as
-- ServerStorage.RegularEnemyRawImports.<id>, and returns the regular-mob
-- receipt JSON (bones, meshes, parts, motors) that retarget_studio.py reads.
-- Set ID (and optionally REVISION) above this text when pasting into execute_luau.
local ID = assert(ID, "Set ID, e.g. local ID='werewolf'")
local REVISION = REVISION or ""
local Http = game:GetService("HttpService")
local storage = game:GetService("ServerStorage")
local rawFolder = assert(storage:FindFirstChild("RegularEnemyRawImports"), "Missing RegularEnemyRawImports")
local fresh = workspace:FindFirstChild(ID .. "-rebuild")
local existing = rawFolder:FindFirstChild(ID)
if not fresh then
	-- Re-running after adoption only re-dumps the receipt.
	assert(existing and existing:GetAttribute("RebuildRevision") == REVISION, "Import " .. ID .. "-rebuild.fbx first")
	fresh = existing
else
	if math.abs(fresh:GetScale() - 0.01) > 1e-6 then
		fresh:ScaleTo(0.01)
	end
	local root = assert(fresh:FindFirstChild("RootPart"), "Import has no RootPart")
	fresh:PivotTo(root.CFrame:Inverse() * fresh:GetPivot())
	if existing then
		local history = storage:FindFirstChild("RegularEnemyRawImportsHistory") or Instance.new("Folder")
		history.Name = "RegularEnemyRawImportsHistory"
		history.Parent = storage
		local previous = history:FindFirstChild(ID .. "-before-rebuild")
		if previous then
			previous:Destroy()
		end
		existing.Name = ID .. "-before-rebuild"
		existing.Parent = history
	end
	fresh.Name = ID
	fresh:SetAttribute("EnemyId", ID)
	fresh:SetAttribute("SourceImportScale", 0.01)
	fresh:SetAttribute("SourceForward", "Blender -Y -> Roblox -Z")
	fresh:SetAttribute("RebuildRevision", REVISION)
	for _, d in fresh:GetDescendants() do
		if d:IsA("BasePart") then
			d.Anchored = true
		end
	end
	fresh.Parent = rawFolder
end
local function cf(c)
	local t = { c:GetComponents() }
	for i, v in t do
		t[i] = math.round(v * 1e7) / 1e7
	end
	return t
end
local root = fresh:FindFirstChild("RootPart") or fresh.PrimaryPart
local bones, meshes, parts, motors = {}, {}, {}, {}
for _, d in fresh:GetDescendants() do
	if d:IsA("Bone") then
		table.insert(bones, { name = d.Name, parent = d.Parent:IsA("Bone") and d.Parent.Name or "RootPart", cframe = cf(d.CFrame) })
	elseif d:IsA("BasePart") then
		table.insert(parts, { name = d.Name, cframe = cf(d.CFrame), size = { d.Size.X, d.Size.Y, d.Size.Z } })
		if d:IsA("MeshPart") then
			local sa = d:FindFirstChildOfClass("SurfaceAppearance")
			table.insert(meshes, {
				name = d.Name,
				meshId = d.MeshId,
				textureId = d.TextureID,
				colorMap = sa and sa.ColorMap or "",
				cframe = cf(root.CFrame:ToObjectSpace(d.CFrame)),
				size = { d.Size.X, d.Size.Y, d.Size.Z },
			})
		end
	elseif d:IsA("Motor6D") and d.Part0 and d.Part1 then
		table.insert(motors, {
			name = d.Name,
			parent = d.Parent.Name,
			part0 = d.Part0.Name,
			part1 = d.Part1.Name,
			c0 = cf(d.C0),
			c1 = cf(d.C1),
			transform = cf(d.Transform),
		})
	end
end
return Http:JSONEncode({
	id = ID,
	revision = REVISION,
	scale = fresh:GetScale(),
	pivot = cf(fresh:GetPivot()),
	rootPartCFrame = cf(root.CFrame),
	bones = bones,
	meshes = meshes,
	parts = parts,
	motors = motors,
})
