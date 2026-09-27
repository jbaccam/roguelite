-- Repository-built visuals for spell projectiles that have no imported mesh.
-- The same model is the server's flying projectile and the client's cosmetic
-- held copy, so what a caster holds is exactly what it throws. Visual only:
-- every part is anchored and non-colliding/non-queryable/non-touching.
local V = {}

local function part(model, name, shape, size, color, material, transparency)
	local p = Instance.new("Part")
	p.Name = name
	p.Shape = shape
	p.Size = size
	p.Color = color
	p.Material = material
	p.Transparency = transparency or 0
	p.Anchored = true
	p.CanCollide = false
	p.CanTouch = false
	p.CanQuery = false
	p.CastShadow = false
	p.Parent = model
	return p
end

-- Fireball: bright core inside a translucent flame shell, licking flames and
-- warm light. Colours sit in the volcanic map's ember-orange range.
local function fireball()
	local m = Instance.new("Model")
	m.Name = "Fireball"
	local core = part(m, "Core", Enum.PartType.Ball, Vector3.one * 0.55, Color3.fromRGB(255, 206, 120), Enum.Material.Neon)
	local shell =
		part(m, "Shell", Enum.PartType.Ball, Vector3.one * 0.9, Color3.fromRGB(255, 112, 38), Enum.Material.Neon, 0.35)
	shell.CFrame = core.CFrame
	m.PrimaryPart = core
	local flames = Instance.new("ParticleEmitter")
	flames.Name = "Flames"
	flames.Texture = "rbxasset://textures/particles/fire_main.dds"
	flames.Color = ColorSequence.new({
		ColorSequenceKeypoint.new(0, Color3.fromRGB(255, 214, 130)),
		ColorSequenceKeypoint.new(0.5, Color3.fromRGB(255, 118, 40)),
		ColorSequenceKeypoint.new(1, Color3.fromRGB(120, 36, 18)),
	})
	flames.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.55), NumberSequenceKeypoint.new(1, 0) })
	flames.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.1), NumberSequenceKeypoint.new(1, 1) })
	flames.Lifetime = NumberRange.new(0.18, 0.32)
	flames.Rate = 45
	flames.Speed = NumberRange.new(0.6, 1.4)
	flames.SpreadAngle = Vector2.new(180, 180)
	flames.LightEmission = 1
	flames.Acceleration = Vector3.new(0, 3, 0)
	flames.Parent = core
	local light = Instance.new("PointLight")
	light.Color = Color3.fromRGB(255, 140, 60)
	light.Range = 7
	light.Brightness = 1.6
	light.Parent = core
	return m
end

-- Icicle: a long frosted crystal spike with a pale glowing core. Points along
-- the model's look vector, which is the flight direction.
local function icicle()
	local m = Instance.new("Model")
	m.Name = "Icicle"
	local root = part(m, "Root", Enum.PartType.Block, Vector3.new(0.1, 0.1, 0.1), Color3.new(1, 1, 1), Enum.Material.Glass, 1)
	local shard = part(m, "Shard", Enum.PartType.Block, Vector3.new(1, 1, 1), Color3.fromRGB(186, 232, 250), Enum.Material.Glass, 0.15)
	local mesh = Instance.new("SpecialMesh")
	mesh.MeshType = Enum.MeshType.Sphere
	mesh.Scale = Vector3.new(0.34, 0.34, 1.7)
	mesh.Parent = shard
	local glow = part(m, "Glow", Enum.PartType.Block, Vector3.new(1, 1, 1), Color3.fromRGB(205, 246, 255), Enum.Material.Neon, 0.25)
	local glowMesh = mesh:Clone()
	glowMesh.Scale = Vector3.new(0.16, 0.16, 1.2)
	glowMesh.Parent = glow
	-- Offset so the tip leads: the shard's widest point sits behind the root.
	shard.CFrame = root.CFrame * CFrame.new(0, 0, 0.15)
	glow.CFrame = shard.CFrame
	m.PrimaryPart = root
	local light = Instance.new("PointLight")
	light.Color = Color3.fromRGB(170, 230, 255)
	light.Range = 5
	light.Brightness = 0.8
	light.Parent = root
	return m
end

local builders = { Fireball = fireball, Icicle = icicle }

function V.build(kind)
	local f = builders[kind]
	return f and f() or nil
end

function V.has(kind)
	return builders[kind] ~= nil
end

return V
