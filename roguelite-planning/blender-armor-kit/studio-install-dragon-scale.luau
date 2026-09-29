-- Installs the Dragon Scale armor after Studio's 3D Importer and stores it as
-- ReplicatedStorage.ArmorSets.DragonScale, the template ArmorService and the Armory clone.
-- Run in Edit after Import 3D of exports/fbx/dragon-scale.fbx (lands as workspace['dragon-scale']).
--
-- The importer may rescale and turn the scene, so nothing is assumed about its axes:
--  - Size: the helmet's longest side is compared with its authored size, and the model is scaled back.
--  - Turn: the character-space centre of every mesh is known (the normalized R15 rest pose, measured
--    from CreateHumanoidModelFromDescription, plus each mesh's authored offset from
--    studio-install-data-dragon-scale.json). The turn R that maps character space onto the import
--    is solved from the feet and the helmet, then checked against all 26 meshes.
-- Each mesh gets:
--  - Mount: a CFrame from its body part to the mesh, used as the Weld C0.
--  - Rest: its CFrame in HumanoidRootPart space, used for the Armory's 3D views.
--  - Piece, BodyPart: which piece and which R15 part it belongs to.
-- Textured meshes use TextureID (SurfaceAppearance renders blank in Play here); glow meshes are Neon.
-- Refuses to overwrite an installed set.
local RS = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")

local GLOW = Color3.fromRGB(255, 132, 30)
-- Texture ids: the five 1024 atlases uploaded 2026-09-29 (textures/dragon-scale-*.png).
local PARTS = {
	DragonScale_Helmet_Head = { piece = "Helmet", body = "Head", glow = false, offset = Vector3.new(-0.0, 0.3505, -0.1299), size = Vector3.new(2.0934, 1.9391, 2.1801), texture = "rbxassetid://84842539507005" },
	DragonScale_Chest_UpperTorso = { piece = "Chest", body = "UpperTorso", glow = false, offset = Vector3.new(-0.0, 0.2879, 0.1062), size = Vector3.new(1.98, 2.1819, 1.8457), texture = "rbxassetid://135900482412527" },
	DragonScale_Chest_LowerTorso = { piece = "Chest", body = "LowerTorso", glow = false, offset = Vector3.new(-0.0, -0.173, -0.0444), size = Vector3.new(1.988, 0.847, 1.6151), texture = "rbxassetid://135900482412527" },
	DragonScale_Chest_LeftUpperArm = { piece = "Chest", body = "LeftUpperArm", glow = false, offset = Vector3.new(-0.2098, 0.4457, -0.0293), size = Vector3.new(1.4437, 2.1145, 2.1), texture = "rbxassetid://115141085987683" },
	DragonScale_Chest_RightUpperArm = { piece = "Chest", body = "RightUpperArm", glow = false, offset = Vector3.new(0.2098, 0.4515, -0.0293), size = Vector3.new(1.4437, 2.103, 2.1), texture = "rbxassetid://115141085987683" },
	DragonScale_Chest_LeftLowerArm = { piece = "Chest", body = "LeftLowerArm", glow = false, offset = Vector3.new(-0.1169, -0.12, 0.1053), size = Vector3.new(1.2599, 1.24, 1.6455), texture = "rbxassetid://115141085987683" },
	DragonScale_Chest_RightLowerArm = { piece = "Chest", body = "RightLowerArm", glow = false, offset = Vector3.new(0.12, -0.12, 0.1025), size = Vector3.new(1.2661, 1.24, 1.651), texture = "rbxassetid://115141085987683" },
	DragonScale_Legs_LeftUpperLeg = { piece = "Legs", body = "LeftUpperLeg", glow = false, offset = Vector3.new(-0.0763, 0.0, -0.0386), size = Vector3.new(1.1286, 1.2, 1.2572), texture = "rbxassetid://130164121208142" },
	DragonScale_Legs_RightUpperLeg = { piece = "Legs", body = "RightUpperLeg", glow = false, offset = Vector3.new(0.0825, 0.0, -0.0449), size = Vector3.new(1.141, 1.2, 1.2698), texture = "rbxassetid://130164121208142" },
	DragonScale_Legs_LeftLowerLeg = { piece = "Legs", body = "LeftLowerLeg", glow = false, offset = Vector3.new(-0.1057, 0.1989, -0.194), size = Vector3.new(1.1875, 1.1037, 1.568), texture = "rbxassetid://130164121208142" },
	DragonScale_Legs_RightLowerLeg = { piece = "Legs", body = "RightLowerLeg", glow = false, offset = Vector3.new(0.1057, 0.1988, -0.194), size = Vector3.new(1.1875, 1.1035, 1.568), texture = "rbxassetid://130164121208142" },
	DragonScale_Boots_LeftLowerLeg = { piece = "Boots", body = "LeftLowerLeg", glow = false, offset = Vector3.new(-0.1316, -0.3427, 0.0), size = Vector3.new(1.2333, 0.4201, 1.4862), texture = "rbxassetid://111073067516615" },
	DragonScale_Boots_RightLowerLeg = { piece = "Boots", body = "RightLowerLeg", glow = false, offset = Vector3.new(0.1316, -0.3422, 0.0), size = Vector3.new(1.2333, 0.421, 1.4721), texture = "rbxassetid://111073067516615" },
	DragonScale_Boots_LeftFoot = { piece = "Boots", body = "LeftFoot", glow = false, offset = Vector3.new(-0.1163, 0.1026, -0.025), size = Vector3.new(1.1966, 0.5092, 1.646), texture = "rbxassetid://111073067516615" },
	DragonScale_Boots_RightFoot = { piece = "Boots", body = "RightFoot", glow = false, offset = Vector3.new(0.1137, 0.108, -0.025), size = Vector3.new(1.1913, 0.52, 1.646), texture = "rbxassetid://111073067516615" },
	DragonScale_Helmet_Head_Glow = { piece = "Helmet", body = "Head", glow = true, offset = Vector3.new(-0.0, 0.0457, -0.9622), size = Vector3.new(0.8204, 0.5857, 0.5448), texture = "" },
	DragonScale_Chest_UpperTorso_Glow = { piece = "Chest", body = "UpperTorso", glow = true, offset = Vector3.new(-0.0, 0.023, -0.7698), size = Vector3.new(0.19, 0.8539, 0.0864), texture = "" },
	DragonScale_Chest_LowerTorso_Glow = { piece = "Chest", body = "LowerTorso", glow = true, offset = Vector3.new(-0.0, 0.026, -0.6655), size = Vector3.new(0.3282, 0.2348, 0.0559), texture = "" },
	DragonScale_Chest_LeftUpperArm_Glow = { piece = "Chest", body = "LeftUpperArm", glow = true, offset = Vector3.new(-0.3742, 0.4952, -0.8695), size = Vector3.new(0.5911, 0.4555, 0.4525), texture = "" },
	DragonScale_Chest_RightUpperArm_Glow = { piece = "Chest", body = "RightUpperArm", glow = true, offset = Vector3.new(0.3742, 0.4952, -0.8695), size = Vector3.new(0.5911, 0.4555, 0.4525), texture = "" },
	DragonScale_Chest_LeftLowerArm_Glow = { piece = "Chest", body = "LeftLowerArm", glow = true, offset = Vector3.new(-0.6447, -0.1003, -0.0002), size = Vector3.new(0.0601, 0.4809, 0.0219), texture = "" },
	DragonScale_Chest_RightLowerArm_Glow = { piece = "Chest", body = "RightLowerArm", glow = true, offset = Vector3.new(0.6447, -0.1003, -0.0002), size = Vector3.new(0.0601, 0.4809, 0.0219), texture = "" },
	DragonScale_Legs_LeftUpperLeg_Glow = { piece = "Legs", body = "LeftUpperLeg", glow = true, offset = Vector3.new(-0.1941, 0.0015, -0.2903), size = Vector3.new(0.8532, 0.6076, 0.6879), texture = "" },
	DragonScale_Legs_RightUpperLeg_Glow = { piece = "Legs", body = "RightUpperLeg", glow = true, offset = Vector3.new(0.1941, 0.0015, -0.2903), size = Vector3.new(0.8532, 0.6076, 0.6879), texture = "" },
	DragonScale_Legs_LeftLowerLeg_Glow = { piece = "Legs", body = "LeftLowerLeg", glow = true, offset = Vector3.new(-0.5935, -0.0092, 0.0121), size = Vector3.new(0.015, 0.5038, 0.0918), texture = "" },
	DragonScale_Legs_RightLowerLeg_Glow = { piece = "Legs", body = "RightLowerLeg", glow = true, offset = Vector3.new(0.5935, -0.0092, 0.0121), size = Vector3.new(0.015, 0.5038, 0.0918), texture = "" },
}

local sets = RS:FindFirstChild("ArmorSets")
if sets and sets:FindFirstChild("DragonScale") then
	return "DragonScale already installed; delete ReplicatedStorage.ArmorSets.DragonScale first to reinstall"
end
local model = workspace:FindFirstChild("dragon-scale")
if not model then
	return "import not found: expected workspace['dragon-scale'] from Import 3D of exports/fbx/dragon-scale.fbx"
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
local helm = mesh.DragonScale_Helmet_Head
local want = PARTS.DragonScale_Helmet_Head.size
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

-- Character-space centre of each mesh, and the turn from character space onto the import.
local function centre(name)
	local info = PARTS[name]
	return (rest[info.body] * CFrame.new(info.offset)).Position
end
local function frame(a, b)
	local x = a.Unit
	local y = (b - x * x:Dot(b)).Unit
	return CFrame.fromMatrix(Vector3.zero, x, y, x:Cross(y))
end
local cl, cr, ch = centre("DragonScale_Boots_LeftFoot"), centre("DragonScale_Boots_RightFoot"), centre("DragonScale_Helmet_Head")
local wl, wr, wh =
	mesh.DragonScale_Boots_LeftFoot.Position, mesh.DragonScale_Boots_RightFoot.Position, helm.Position
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
out.Name = "DragonScale"
local turn = R:Inverse()
for name, info in PARTS do
	local p = mesh[name]
	local mount = CFrame.new(info.offset) * (turn * p.CFrame.Rotation)
	for _, c in p:GetChildren() do
		if c:IsA("SurfaceAppearance") then
			c:Destroy()
		end
	end
	if info.glow then
		p.Material = Enum.Material.Neon
		p.Color = GLOW
		p.TextureID = ""
		p.CastShadow = false
	else
		p.Material = Enum.Material.SmoothPlastic
		p.Color = Color3.new(1, 1, 1)
		p.TextureID = info.texture
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
	p:SetAttribute("BodyPart", info.body)
	p:SetAttribute("Mount", mount)
	p:SetAttribute("Rest", rest[info.body] * mount)
	p.Name = name
	-- Stored standing upright (feet at y = -500), out of sight.
	p.CFrame = CFrame.new(0, -500 + 3, 0) * rest[info.body] * mount
	p.Parent = out
end
out.Parent = sets
model:Destroy()
return string.format("installed %d meshes; import scale factor %.3f; fit error %.4f studs", #out:GetChildren(), factor, worst)
