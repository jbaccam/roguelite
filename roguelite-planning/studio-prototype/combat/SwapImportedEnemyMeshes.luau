-- Studio edit-time tool (not mapped into the production tree). After a revised
-- enemy FBX is brought in with Studio's 3D Importer, this moves the revised
-- meshes onto the existing raw import and its assembled template, keeping
-- every Humanoid, root, joint, tag and attribute those already have.
--
--   require(this).run(workspace["skeleton-edge-forward"], "skeleton", {"RightHand_Geometry"})
--
-- `parts` lists the MeshParts whose geometry changed; every MeshPart also takes
-- the new TextureID (the Ice Elf's atlas changed). The fresh import is
-- normalised exactly like the originals (ScaleTo 0.01) and checked against
-- the old rig through an unchanged reference part before anything is edited.
-- Returns receipt patches for the changed parts and motors.
local S = {}
local function cf(c)
	return { c:GetComponents() }
end
local function motorFor(model, part)
	for _, d in model:GetDescendants() do
		if d:IsA("Motor6D") and d.Part1 == part then
			return d
		end
	end
end
function S.run(fresh, id, parts, reference)
	local storage = game.ServerStorage
	local raw = assert(storage.RegularEnemyRawImports:FindFirstChild(id), "Missing raw import " .. id)
	local catalog = require(game.ReplicatedStorage.RogueliteCombat.EnemyCatalog)
	local config = assert(catalog.get(id))
	local template = assert(storage.RogueliteNPCs:FindFirstChild(config.template), "Missing template")
	if math.abs(fresh:GetScale() - raw:GetScale()) > 1e-6 then
		fresh:ScaleTo(raw:GetScale())
	end
	local function find(model, name)
		for _, d in model:GetDescendants() do
			if d:IsA("BasePart") and d.Name == name then
				return d
			end
		end
	end
	local refFresh, refRaw = assert(find(fresh, reference)), assert(find(raw, reference))
	assert((refFresh.Size - refRaw.Size).Magnitude < 1e-3, "Reference part differs; not the same rig")
	local report = { id = id, parts = {}, motors = {}, textures = 0 }
	for _, target in { raw, template } do
		local refTarget = assert(find(target, reference))
		for _, name in parts do
			local new, old = assert(find(fresh, name), "Fresh import lacks " .. name), assert(find(target, name))
			old:ApplyMesh(new)
			old.Size = new.Size
			local placed = refTarget.CFrame * refFresh.CFrame:ToObjectSpace(new.CFrame)
			local m0, m1 = motorFor(fresh, new), motorFor(target, old)
			if m0 and m1 then
				m1.C0, m1.C1 = m0.C0, m0.C1
			end
			old.CFrame = placed
			if target == raw then
				table.insert(report.parts, { name = name, cframe = cf(old.CFrame), size = { old.Size.X, old.Size.Y, old.Size.Z }, meshId = old.MeshId })
				if m1 then
					table.insert(report.motors, { name = m1.Name, c0 = cf(m1.C0), c1 = cf(m1.C1) })
				end
			end
		end
		for _, new in fresh:GetDescendants() do
			if new:IsA("MeshPart") and new.TextureID ~= "" then
				local old = find(target, new.Name)
				if old and old:IsA("MeshPart") and old.TextureID ~= new.TextureID then
					old.TextureID = new.TextureID
					report.textures += 1
				end
			end
		end
	end
	return report
end
return S
