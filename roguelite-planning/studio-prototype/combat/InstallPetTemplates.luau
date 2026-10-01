--!nonstrict
-- Edit-mode installer: turns the 12 raw 3D-Importer pet models into ReplicatedStorage.PetModels.<Id>.
-- Run from the command bar / execute_luau while `python -m http.server 8765 --bind 127.0.0.1 --directory roguelite-planning` runs:
--   local HS = game:GetService("HttpService")
--   loadstring(HS:GetAsync("http://127.0.0.1:8765/studio-prototype/combat/InstallPetTemplates.luau"))()()
--
-- Raw imports are found by kit name (e.g. Workspace."golden-retriever") or in ServerStorage.PetRawImports, where
-- they are moved after install so a re-run works. The importer brings FBX in at 100x (centimetres) and may turn it;
-- this script scales each model to PetRigs size, checks the part layout against PetRigs (fitErr = summed centre
-- error, studs), then places the root at its PetRigs centre so the model pivot is the ground point under the pet (y = 0,
-- facing -Z). Parts keep the importer's TextureID (one atlas per pet); `_Glow` parts become Neon in their PetRigs colour.

return function(base)
	base = base or "http://127.0.0.1:8765/"
	local HS = game:GetService("HttpService")
	local RS = game:GetService("ReplicatedStorage")
	local SS = game:GetService("ServerStorage")
	local rigs = loadstring(HS:GetAsync(base .. "studio-prototype/combat/PetRigs.luau"))()

	local folder = RS:FindFirstChild("PetModels") or Instance.new("Folder")
	folder.Name, folder.Parent = "PetModels", RS
	local raw = SS:FindFirstChild("PetRawImports") or Instance.new("Folder")
	raw.Name, raw.Parent = "PetRawImports", SS

	local function v(t)
		return Vector3.new(t[1], t[2], t[3])
	end

	local report = {}
	for id, rig in rigs do
		local src = workspace:FindFirstChild(rig.kit) or raw:FindFirstChild(rig.kit)
		if not src then
			report[id] = "raw import missing: " .. rig.kit
			continue
		end
		if src.Parent == workspace then
			src.Parent = raw
		end
		local old = folder:FindFirstChild(id)
		if old then
			old:Destroy()
		end
		local m = src:Clone()
		local parts = {}
		for _, d in m:GetDescendants() do
			if d:IsA("BasePart") then
				parts[d.Name] = d
			end
		end
		local root = parts[rig.root]
		if not root then
			m:Destroy()
			report[id] = "root part missing: " .. rig.root
			continue
		end
		-- Scale by the overall bounding box against PetRigs' at-rest size (largest axis, turn-independent).
		local _, box = m:GetBoundingBox()
		local want = v(rig.size)
		local k = math.max(want.X, want.Y, want.Z) / math.max(box.X, box.Y, box.Z)
		m:ScaleTo(m:GetScale() * k)

		-- The importer keeps the FBX's -Z forward / Y up, so the raw model is already upright (all parts at
		-- rotation 0). A turn search is ambiguous on near-symmetric pets, so only verify identity fits.
		local rc = root.Position
		local best, bestErr = CFrame.identity, 0
		for name, p in parts do
			local info = rig.parts[name]
			if info then
				bestErr += ((p.Position - rc) - (v(info.center) - v(rig.parts[rig.root].center))).Magnitude
			end
		end
		-- Apply: rotate every part about the root centre, then move the root centre to its PetRigs centre.
		local target = v(rig.parts[rig.root].center)
		for _, p in parts do
			local rel = p.CFrame - rc
			p.CFrame = CFrame.new(target) * best * rel
		end
		local worst = 0
		local missing = {}
		for name, info in rig.parts do
			local p = parts[name]
			if not p then
				table.insert(missing, name)
				continue
			end
			worst = math.max(worst, (p.Position - v(info.center)).Magnitude)
			p.Anchored, p.CanCollide, p.CanTouch, p.CanQuery, p.Massless = true, false, false, false, true
			p.CastShadow = not info.glow
			if info.glow then
				p.Material = Enum.Material.Neon
				p.TextureID = ""
				local c = info.neon or { 255, 170, 60 }
				p.Color = Color3.fromRGB(c[1], c[2], c[3])
			end
			p:SetAttribute("PetPart", true)
		end
		m.Name = id
		-- With a PrimaryPart the model pivot is root.CFrame * root.PivotOffset; the importer leaves its own
		-- (-90 X) offset there, so reset it to the ground point under the pet.
		m.PrimaryPart = root
		root.PivotOffset = root.CFrame:Inverse()
		m:SetAttribute("PetId", id)
		m:SetAttribute("Hover", rig.hover or 0)
		m.Parent = folder
		report[id] = string.format(
			"ok scale=%.4f fitErr=%.3f worstPart=%.3f studs%s",
			k,
			bestErr,
			worst,
			#missing > 0 and (" MISSING " .. table.concat(missing, ",")) or ""
		)
	end
	return report
end
