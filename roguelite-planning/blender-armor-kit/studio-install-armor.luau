-- Installs one armor set after Studio's 3D Importer as ReplicatedStorage.ArmorSets.<Set>: the
-- template ArmorService clones onto characters and the Armory shows. Works for every set kit
-- (<set>/studio-install-data.json); replaces the Dragon Scale-only installer's approach.
--
-- Run in Edit: loadstring(installer)()(cfg) with
--   cfg.set      = 'Iron'           ArmorCatalog set id (also the template name)
--   cfg.import   = 'iron'           workspace name the importer gave the model
--   cfg.prefix   = 'Iron'           mesh name prefix
--   cfg.data     = decoded studio-install-data.json
--   cfg.textures = {['textures/iron-body.png'] = 'rbxassetid://…', …}   uploaded atlases
--   cfg.vfxTextures = {['textures/vfx/flame.png'] = 'rbxassetid://…', …} (sets with vfx)
--   cfg.replace  = true to replace an installed set
--   cfg.skipVfx  = true to install meshes only; cfg.vfxOnly = true adds the VFX to an installed
--                  set (two smaller steps: Studio dropped out twice doing Phoenix in one go)
--   cfg.vfxFrom / cfg.vfxTo = only these vfx entries (1-based), to add them in batches
--
-- The importer may rescale and turn the scene, so nothing is assumed about its axes:
--  - Size: the helmet's longest side is compared with its authored size, and the model is scaled back.
--  - Turn: every mesh's character-space centre is known (the normalized R15 rest pose from
--    CreateHumanoidModelFromDescription, plus its authored offset). The turn is solved from the
--    feet and the helmet, then checked against every mesh.
-- Each mesh gets:
--  - Mount: a CFrame from its body part, used as the Weld C0;
--  - Rest: a CFrame in HumanoidRootPart space, for the Armory's 3D views;
--  - Piece, BodyPart.
-- Textured meshes use TextureID (SurfaceAppearance renders blank in Play); glow meshes are Neon.
-- VFX entries (Phoenix) become Attachments with ParticleEmitters/PointLights inside the meshes, so
-- they ride along when ArmorService clones the pieces.
-- VFX: ParticleEmitters and PointLights from the install data, inside the template's meshes.
local function addVfx(cfg, out, mounts)
	local data, prefix = cfg.data, cfg.prefix
	local function v3(t)
		return Vector3.new(t[1], t[2], t[3])
	end
	local function rgb(t)
		return Color3.fromRGB(t[1], t[2], t[3])
	end
	local vfxCount = 0
	local ENUMS = {
		EmissionDirection = Enum.NormalId,
		Orientation = Enum.ParticleOrientation,
		Shape = Enum.ParticleEmitterShape,
		ShapeInOut = Enum.ParticleEmitterShapeInOut,
		ShapeStyle = Enum.ParticleEmitterShapeStyle,
	}
	local RANGES = { Lifetime = true, Speed = true, Rotation = true, RotSpeed = true }
	local SEQUENCES = { Size = true, Transparency = true, Squash = true }
	local function value(key, x)
		if ENUMS[key] then
			return ENUMS[key][x]
		elseif key == "Texture" then
			return assert(cfg.vfxTextures[x], "no uploaded particle texture for " .. x)
		elseif RANGES[key] then
			return NumberRange.new(x[1], x[2])
		elseif key == "SpreadAngle" then
			return Vector2.new(x[1], x[2])
		elseif key == "Acceleration" then
			return v3(x)
		elseif SEQUENCES[key] then
			local kps = {}
			for _, k in x do
				table.insert(kps, NumberSequenceKeypoint.new(k[1], k[2], k[3] or 0))
			end
			return NumberSequence.new(kps)
		elseif key == "Color" then
			if type(x[1]) == "table" then
				local kps = {}
				for _, k in x do
					table.insert(kps, ColorSequenceKeypoint.new(k[1], rgb(k[2])))
				end
				return ColorSequence.new(kps)
			end
			return rgb(x)
		end
		return x
	end
	-- The carrier for an entry: the named part, else the piece's main textured mesh on that body part.
	local function carrier(e)
		local name = e.parent_part or (prefix .. "_" .. e.piece .. "_" .. e.body_part)
		return out:FindFirstChild(name), name
	end
	for i, e in data.vfx do
		if i < (cfg.vfxFrom or 1) or i > (cfg.vfxTo or math.huge) then
			continue
		end
		local part, name = carrier(e)
		assert(part, "no mesh " .. name .. " for vfx " .. tostring(e.name))
		local parent = part
		if e.parent == "attachment" then
			local a = e.attachment
			local cf = CFrame.fromMatrix(v3(a.position), v3(a.axis), v3(a.secondary_axis))
			local att = Instance.new("Attachment")
			att.Name = e.name
			att.CFrame = mounts[name]:Inverse() * cf
			att.Parent = part
			parent = att
		end
		local fx = Instance.new(e.class)
		fx.Name = e.name
		for key, x in e.properties or {} do
			local ok, err = pcall(function()
				fx[key] = value(key, x)
			end)
			if not ok then
				warn("armor vfx " .. e.name .. "." .. key .. ": " .. tostring(err))
			end
		end
		fx.Parent = parent
		vfxCount += 1
	end
	return vfxCount
end

return function(cfg)
	local RS = game:GetService("ReplicatedStorage")
	local Players = game:GetService("Players")
	local data, prefix = cfg.data, cfg.prefix
	local PARTS = data.parts
	local function v3(t)
		return Vector3.new(t[1], t[2], t[3])
	end
	local function rgb(t)
		return Color3.fromRGB(t[1], t[2], t[3])
	end

	local sets = RS:FindFirstChild("ArmorSets")
	local old = sets and sets:FindFirstChild(cfg.set)
	if cfg.vfxOnly then
		assert(old, cfg.set .. " is not installed yet")
		local mounts = {}
		for _, p in old:GetChildren() do
			mounts[p.Name] = p:GetAttribute("Mount")
		end
		return cfg.set .. ": added " .. addVfx(cfg, old, mounts) .. " vfx"
	end
	if old and not cfg.replace then
		return cfg.set .. " already installed; pass replace=true to reinstall"
	end
	local model = workspace:FindFirstChild(cfg.import)
	if not model then
		return "import not found: expected workspace['" .. cfg.import .. "']"
	end
	local mesh = {}
	for name in PARTS do
		local p = model:FindFirstChild(name, true)
		if not (p and p:IsA("MeshPart")) then
			return "missing MeshPart " .. name .. " in the import"
		end
		mesh[name] = p
	end

	-- Importer unit handling varies: restore the authored size in studs.
	local helmName = prefix .. "_Helmet_Head"
	local helm = mesh[helmName]
	local want = v3(PARTS[helmName].size)
	local factor = math.max(helm.Size.X, helm.Size.Y, helm.Size.Z) / math.max(want.X, want.Y, want.Z)
	if math.abs(factor - 1) > 0.01 then
		model:ScaleTo(model:GetScale() / factor)
	end

	-- Rest pose of the normalized body (AvatarNormalizer's scales), relative to HumanoidRootPart.
	local desc = Instance.new("HumanoidDescription")
	for k, v in { HeightScale = 1, WidthScale = 1, DepthScale = 1, HeadScale = 1, BodyTypeScale = 0, ProportionScale = 0 } do
		desc[k] = v
	end
	local dummy = Players:CreateHumanoidModelFromDescription(desc, Enum.HumanoidRigType.R15)
	local hrp = dummy:FindFirstChild("HumanoidRootPart")
	local rest = {}
	for _, bp in dummy:GetChildren() do
		if bp:IsA("BasePart") then
			rest[bp.Name] = hrp.CFrame:ToObjectSpace(bp.CFrame)
		end
	end
	dummy:Destroy()
	desc:Destroy()

	local function centre(name)
		local info = PARTS[name]
		return (rest[info.body_part] * CFrame.new(v3(info.offset))).Position
	end
	local function frame(a, b)
		local x = a.Unit
		local y = (b - x * x:Dot(b)).Unit
		return CFrame.fromMatrix(Vector3.zero, x, y, x:Cross(y))
	end
	local lf, rf = prefix .. "_Boots_LeftFoot", prefix .. "_Boots_RightFoot"
	local cl, cr, ch = centre(lf), centre(rf), centre(helmName)
	local wl, wr, wh = mesh[lf].Position, mesh[rf].Position, helm.Position
	local R = frame(wr - wl, wh - (wl + wr) / 2) * frame(cr - cl, ch - (cl + cr) / 2):Inverse()
	local t = wh - R * ch
	local worst = 0
	for name in PARTS do
		worst = math.max(worst, (R * centre(name) + t - mesh[name].Position).Magnitude)
	end
	if worst > 0.02 then
		return string.format("fit check failed: a mesh sits %.3f studs from where the install data puts it", worst)
	end

	sets = sets or Instance.new("Folder")
	sets.Name = "ArmorSets"
	sets.Parent = RS
	local out = Instance.new("Model")
	out.Name = cfg.set
	local turn = R:Inverse()
	local glow = data.glow_color_srgb and rgb(data.glow_color_srgb) or Color3.fromRGB(255, 132, 30)
	local mounts = {}
	for name, info in PARTS do
		local p = mesh[name]
		local mount = CFrame.new(v3(info.offset)) * (turn * p.CFrame.Rotation)
		mounts[name] = mount
		for _, c in p:GetChildren() do
			if c:IsA("SurfaceAppearance") then
				c:Destroy()
			end
		end
		if info.kind == "glow" then
			p.Material = Enum.Material.Neon
			p.Color = info.color_srgb and rgb(info.color_srgb) or glow
			p.TextureID = ""
			p.CastShadow = false
		else
			local tex = cfg.textures[info.atlas]
			assert(tex, "no uploaded texture for " .. tostring(info.atlas))
			p.Material = Enum.Material.SmoothPlastic
			p.Color = Color3.new(1, 1, 1)
			p.TextureID = tex
			p.CastShadow = true
		end
		p.Anchored = true
		p.CanCollide = false
		p.CanTouch = false
		p.CanQuery = false
		p.Massless = true
		pcall(function()
			p.CollisionFidelity = Enum.CollisionFidelity.Box
		end)
		p:SetAttribute("Piece", info.piece)
		p:SetAttribute("BodyPart", info.body_part)
		p:SetAttribute("Mount", mount)
		p:SetAttribute("Rest", rest[info.body_part] * mount)
		p.Name = name
		-- Stored standing upright (feet at y = -500), out of sight.
		p.CFrame = CFrame.new(0, -500 + 3, 0) * rest[info.body_part] * mount
		p.Parent = out
	end

	local vfxCount = (data.vfx and not cfg.skipVfx) and addVfx(cfg, out, mounts) or 0

	if old then
		old:Destroy()
	end
	out.Parent = sets
	model:Destroy()
	return string.format(
		"%s: installed %d meshes and %d vfx; import scale factor %.3f; fit error %.4f studs",
		cfg.set,
		#out:GetChildren(),
		vfxCount,
		factor,
		worst
	)
end
