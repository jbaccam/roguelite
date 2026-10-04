--!nonstrict
-- Edit-mode installer (HANDYMAN_TURRET.md, 2026-10-03): builds
-- ReplicatedStorage.RogueliteCombat.HandymanTurrets.T1-T4 from the turret art
-- (roguelite-planning/blender-handyman-turret, README "Model contract"). The turret feature stays
-- off until all four are there (HandymanTurret.templates). Run only with the user's okay.
--
-- 1. File > Import 3D, default settings, scale 1:1, each exports/fbx/HandymanTurret_T<n>.fbx.
--    Upload textures/HandymanTurret_T<n>.png too if the importer didn't bring the colour map in.
-- 2. In the command bar / execute_luau, with the dev server serving roguelite-planning
--    (python -m http.server 8765 --bind 127.0.0.1 --directory roguelite-planning):
--      local HS = game:GetService("HttpService")
--      print(loadstring(HS:GetAsync("http://127.0.0.1:8765/studio-prototype/combat/InstallHandymanTurret.luau"))()({}))
--    opts: textures = {[n] = "rbxassetid://..."} (the uploaded colour maps; otherwise the importer's
--    SurfaceAppearance colour map is moved to TextureID), icons = {[n] = "rbxassetid://..."} (the
--    uploaded previews/icon_T<n>.png; better: paste them into HandymanTurret.Icons), only = n (one
--    tier). Returns a report, one line per tier.
--
-- The importer can't be trusted to keep the file's orientation (it turned the chest, armory and
-- island kits 180 degrees about Y, the raw FBX nodes carry a -90 degree X turn, and it once laid a
-- file on its back). So, like blender-chest-kit/studio-install-chests.luau, every imported MeshPart
-- HandymanTurret_T<n>_<Part> is matched against the spec's part centres and sizes: the 90-degree turn
-- that best maps the parts' layout wins, and the model is placed from it. Never rescaled more than
-- 15% (the baked atlas can't re-tile): a bigger mismatch is reported and the tier skipped.
--
-- Each template: Model "T<n>" (PrimaryPart Base) with Base, Head, Barrel (and T4's Glow), anchored,
-- no collision, touch or query. Pivots, identity rotation, Roblox axes, barrels at rest to -Z:
--   Base   (0,0,0), the ground point under it        Head   the yaw axis (spec Head.pivot)
--   Barrel the trunnion: recoil along +Z, T4 spins about its Z (spec Barrel.pivot)
--   Glow   T4 only: Neon (248,88,99), pivot = Head's, attribute Follows = 'Head'
-- Barrel attachments Muzzle1..n at muzzlesFromBarrelPivot; Barrel attribute MuzzleCentre (in the
-- Barrel's frame) for T4, which aims from its centre. Model attributes Tier, Height, Radius, Spin,
-- Icon (if given), SourceFbx. A part's SurfaceAppearance colour map moves to TextureID
-- (SurfaceAppearance images showed white in Play here).

-- turret-spec.json (blender-handyman-turret/exports), Roblox axes and studs from the Base pivot.
-- muzzles = muzzlesFromBarrelPivot. Regenerate this table if the art changes.
local DATA = {
	[1] = {
		height = 3.409, radius = 1.784, spin = false,
		muzzles = { Vector3.new(0, 0, -1.1) }, muzzleCentre = Vector3.new(0, 2.78, -1.72),
		parts = {
			Base = { center = Vector3.new(0, 1.025, 0.365), size = Vector3.new(3.1329, 2.05, 2.8372), pivot = Vector3.new(0, 0, 0) },
			Head = { center = Vector3.new(-0.0031, 2.7293, 0.2246), size = Vector3.new(1.5538, 1.3586, 2.0107), pivot = Vector3.new(0, 2.05, 0) },
			Barrel = { center = Vector3.new(0, 2.78, -1.11), size = Vector3.new(0.5543, 0.5543, 1.22), pivot = Vector3.new(0, 2.78, -0.62) },
		},
	},
	[2] = {
		height = 3.925, radius = 2.148, spin = false,
		muzzles = { Vector3.new(0.21, 0, -1.4), Vector3.new(-0.21, 0, -1.4) }, muzzleCentre = Vector3.new(0, 2.98, -2.12),
		parts = {
			Base = { center = Vector3.new(0, 1.1, 0.41), size = Vector3.new(3.5119, 2.2, 3.1848), pivot = Vector3.new(0, 0, 0) },
			Head = { center = Vector3.new(0, 3.0623, 0.0284), size = Vector3.new(2.4757, 1.7246, 2.6631), pivot = Vector3.new(0, 2.2, 0) },
			Barrel = { center = Vector3.new(0, 2.98, -1.385), size = Vector3.new(0.86, 0.5, 1.47), pivot = Vector3.new(0, 2.98, -0.72) },
		},
	},
	[3] = {
		height = 4.391, radius = 2.241, spin = false,
		muzzles = { Vector3.new(0.19, -0.18, -1.4), Vector3.new(0.19, 0.18, -1.4), Vector3.new(-0.19, -0.18, -1.4), Vector3.new(-0.19, 0.18, -1.4) },
		muzzleCentre = Vector3.new(0, 3.2, -2.22),
		parts = {
			Base = { center = Vector3.new(0, 1.2, 0), size = Vector3.new(3.1849, 2.4, 3.1849), pivot = Vector3.new(0, 0, 0) },
			Head = { center = Vector3.new(0, 3.3956, 0.1521), size = Vector3.new(2.8238, 1.9913, 3.1707), pivot = Vector3.new(0, 2.4, 0) },
			Barrel = { center = Vector3.new(0, 3.2, -1.46), size = Vector3.new(0.94, 0.82, 1.52), pivot = Vector3.new(0, 3.2, -0.82) },
		},
	},
	[4] = {
		height = 5.105, radius = 2.421, spin = true,
		muzzles = {
			Vector3.new(0, 0.27, -1.48), Vector3.new(0.2338, 0.135, -1.48), Vector3.new(0.2338, -0.135, -1.48),
			Vector3.new(0, -0.27, -1.48), Vector3.new(-0.2338, -0.135, -1.48), Vector3.new(-0.2338, 0.135, -1.48),
		},
		muzzleCentre = Vector3.new(0, 3.38, -2.4),
		parts = {
			Base = { center = Vector3.new(0, 1.3, 0), size = Vector3.new(3.3743, 2.6, 3.3743), pivot = Vector3.new(0, 0, 0) },
			Head = { center = Vector3.new(0, 3.8525, 0.1506), size = Vector3.new(4.4713, 2.5049, 3.3737), pivot = Vector3.new(0, 2.6, 0) },
			Barrel = { center = Vector3.new(0, 3.38, -1.59), size = Vector3.new(0.85, 0.85, 1.62), pivot = Vector3.new(0, 3.38, -0.92) },
			Glow = { center = Vector3.new(0, 3.9749, -0.18), size = Vector3.new(3.8472, 1.1498, 1.96), pivot = Vector3.new(0, 2.6, 0) },
		},
	},
}
local GLOW = Color3.fromRGB(248, 88, 99) -- glow_srgb, the Tier IV colour
local MAX_SCALE_FIX = 0.15

return function(opts)
	opts = opts or {}
	local RS = game:GetService("ReplicatedStorage")
	local combat = RS:WaitForChild("RogueliteCombat")
	local folder = combat:FindFirstChild("HandymanTurrets") or Instance.new("Folder")
	folder.Name = "HandymanTurrets"
	local report = {}

	-- Imported parts by tier, wherever the importer put them; installed templates too, so a re-run repairs them.
	local found = {}
	for _, d in workspace:GetDescendants() do
		if d:IsA("MeshPart") then
			local n, part = string.match(d.Name, "^HandymanTurret_T(%d)_(%a+)$")
			n = tonumber(n)
			if n and DATA[n] and DATA[n].parts[part] then
				found[n] = found[n] or {}
				found[n][part] = d
			end
		end
	end
	for _, m in folder:GetChildren() do
		local n = tonumber(string.match(m.Name, "^T(%d)$"))
		if n and DATA[n] and not found[n] then
			found[n] = {}
			for _, d in m:GetChildren() do
				if d:IsA("MeshPart") and DATA[n].parts[d.Name] then
					found[n][d.Name] = d
				end
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
	local function largest(v)
		return math.max(v.X, v.Y, v.Z)
	end

	for n, t in DATA do
		if opts.only and opts.only ~= n then
			continue
		end
		local parts = found[n]
		local missing = {}
		for name in t.parts do
			if not (parts and parts[name]) then
				table.insert(missing, name)
			end
		end
		if #missing > 0 then
			table.insert(report, string.format("T%d: not imported (missing %s)", n, table.concat(missing, ", ")))
			continue
		end
		local base = parts.Base
		-- Size check: the importer should keep the authored studs.
		local factor = largest(base.Size) / largest(t.parts.Base.size)
		if math.abs(factor - 1) > MAX_SCALE_FIX then
			table.insert(report, string.format("T%d: imported at %.3fx the authored size; re-import at 1:1 (not installed)", n, factor))
			continue
		end
		-- Orientation: the 90-degree turn that best maps every part's offset from the base.
		local R, best = CFrame.identity, math.huge
		for _, turn in TURNS do
			local err = 0
			for name, p in parts do
				local o = (t.parts[name].center - t.parts.Base.center) * factor
				err += ((p.Position - base.Position) - turn:VectorToWorldSpace(o)).Magnitude
			end
			if err < best - 1e-3 then
				R, best = turn, err
			end
		end
		local origin = base.Position - R:VectorToWorldSpace(t.parts.Base.center * factor)
		local pivot = CFrame.new(origin) * R
		local old = folder:FindFirstChild("T" .. n)
		if old then
			for _, p in parts do
				p.Parent = nil -- keep the parts when repairing an installed template
			end
			old:Destroy()
		end
		local model = Instance.new("Model")
		model.Name = "T" .. n
		for name, p in parts do
			p.Name = name
			p.Anchored, p.CanCollide, p.CanTouch, p.CanQuery, p.Massless = true, false, false, false, true
			p.Locked = true
			for _, child in p:GetChildren() do
				if child:IsA("Attachment") or child:IsA("JointInstance") or child:IsA("WeldConstraint") then
					child:Destroy()
				end
			end
			local sa = p:FindFirstChildOfClass("SurfaceAppearance")
			if name == "Glow" then
				if sa then
					sa:Destroy()
				end
				p.TextureID = ""
				p.Material = Enum.Material.Neon
				p.Color = GLOW
				p.CastShadow = false
				p:SetAttribute("Follows", "Head")
			else
				if sa then
					if sa.ColorMap ~= "" then
						p.TextureID = sa.ColorMap
					end
					sa:Destroy()
				end
				local texture = opts.textures and opts.textures[n]
				if texture then
					p.TextureID = type(texture) == "number" and ("rbxassetid://" .. texture) or texture
				end
				p.Material = Enum.Material.SmoothPlastic
				p.Color = Color3.new(1, 1, 1)
				p.CastShadow = true
			end
			p.Parent = model
		end
		-- With a PrimaryPart the pivot is PrimaryPart.CFrame * PivotOffset.
		model.PrimaryPart = base
		base.PivotOffset = base.CFrame:ToObjectSpace(pivot)
		if math.abs(factor - 1) > 0.005 then
			model:ScaleTo(1 / factor)
		end
		model:PivotTo(CFrame.new())
		-- Now in spec space: check every centre, then the moving parts' pivots (identity rotation).
		local worst = 0
		for name, p in parts do
			worst = math.max(worst, (p.Position - t.parts[name].center).Magnitude)
		end
		for _, name in { "Head", "Barrel", "Glow" } do
			local p = parts[name]
			if p then
				p.PivotOffset = p.CFrame:ToObjectSpace(CFrame.new(t.parts[name].pivot))
			end
		end
		local barrel = parts.Barrel
		local barrelPivot = CFrame.new(t.parts.Barrel.pivot)
		for i, offset in t.muzzles do
			local a = Instance.new("Attachment")
			a.Name = "Muzzle" .. i
			a.CFrame = barrel.CFrame:ToObjectSpace(barrelPivot * CFrame.new(offset))
			a.Parent = barrel
		end
		-- T4's six barrels spin: it aims and flashes from their centre (in the Barrel's frame).
		barrel:SetAttribute("MuzzleCentre", t.muzzleCentre - t.parts.Barrel.pivot)
		model:SetAttribute("Tier", n)
		model:SetAttribute("Height", t.height)
		model:SetAttribute("Radius", t.radius)
		model:SetAttribute("Spin", t.spin)
		local icon = opts.icons and opts.icons[n]
		if icon then
			model:SetAttribute("Icon", type(icon) == "number" and ("rbxassetid://" .. icon) or icon)
		end
		model:SetAttribute("SourceFbx", "roguelite-planning/blender-handyman-turret/exports/fbx/HandymanTurret_T" .. n .. ".fbx")
		model.Parent = folder
		local rx, ry, rz = R:ToEulerAnglesXYZ()
		table.insert(report, string.format("T%d: %s, scale fix %.3f, turn (%d,%d,%d), fit error %.3f, worst centre %.3f studs, %d muzzles%s",
			n, worst < 0.05 and "ok" or "CHECK", factor, math.deg(rx), math.deg(ry), math.deg(rz), best, worst, #t.muzzles,
			barrel.TextureID == "" and " · NO TEXTURE (pass opts.textures)" or ""))
	end
	folder.Parent = combat
	-- Remove the emptied import shells (the importer names its root after the file).
	for _, c in workspace:GetChildren() do
		if string.find(c.Name, "^HandymanTurret_T%d") and not c:FindFirstChildWhichIsA("BasePart", true) then
			c:Destroy()
		end
	end
	local have = {}
	for n = 1, 4 do
		if folder:FindFirstChild("T" .. n) then
			table.insert(have, "T" .. n)
		end
	end
	table.sort(report)
	table.insert(report, #have == 4 and "HandymanTurrets complete: turrets turn on at the next server start" or ("HandymanTurrets has " .. (#have > 0 and table.concat(have, ", ") or "nothing") .. ": turrets stay off until all four are installed"))
	return table.concat(report, "\n")
end
