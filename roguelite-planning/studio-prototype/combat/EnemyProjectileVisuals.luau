-- Repository-built visuals for spell projectiles that have no imported mesh.
-- The same model is the client-drawn flying shot (EnemyVisuals) and the
-- cosmetic held copy, so what a caster holds is exactly what it throws. Visual
-- only: every part is anchored and non-colliding/non-queryable/non-touching.
local V = {}
-- Shots with neither an imported template nor a built spell: a plain ball (or wedge) in this colour.
local colors = {
	Spit = Color3.fromRGB(148, 200, 76),
	Rock = Color3.fromRGB(135, 116, 93),
	Arrow = Color3.fromRGB(224, 198, 138),
	Icicle = Color3.fromRGB(159, 241, 255),
	Fireball = Color3.fromRGB(255, 126, 59),
}

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

-- A flying shot as EnemyAttacks used to build it on the server: the imported template when there
-- is one (Arrow, Rock), else a built spell (Fireball, Icicle), else a plain ball (Spit).
function V.shot(kind, templates)
	local template = templates and templates:FindFirstChild(kind)
	local shot = template and template:Clone() or V.build(kind) or Instance.new(kind == "Icicle" and "WedgePart" or "Part")
	if not template and not V.has(kind) then
		if shot:IsA("Part") then
			shot.Shape = Enum.PartType.Ball
		end
		shot.Size = kind == "Icicle" and Vector3.new(0.35, 0.35, 1.5) or Vector3.one * (kind == "Arrow" and 0.42 or 0.8)
		shot.Material = kind == "Rock" and Enum.Material.Slate or Enum.Material.Neon
		shot.Color = colors[kind] or Color3.new(1, 1, 1)
	end
	local function configure(p)
		if p:IsA("BasePart") then
			p.Anchored = true
			p.CanCollide = false
			p.CanTouch = false
			p.CanQuery = false
			p.CastShadow = false
		end
	end
	configure(shot)
	for _, p in shot:GetDescendants() do
		configure(p)
	end
	shot.Name = "Enemy" .. kind
	return shot
end

-- Seconds a shot has flown at server time `now`: since `started`, frozen at `held` while the run
-- is paused (plan L). Example: an arrow launched at t=10 and drawn at t=10.5 has flown 0.5 s (17.5
-- studs at 35/s); paused at t=10.5 and drawn at t=12, it still has. On Resume the client moves
-- `started` later by the frozen time, so at t=13 it has flown 1 s, as on the server.
function V.flown(started, now, held)
	return math.max(0, (held and math.min(held, now) or now) - started)
end

-- Where it is then, facing along its flight.
function V.shotFrame(origin, velocity, flown)
	local at = origin + velocity * flown
	return CFrame.lookAt(at, at + velocity)
end

-- 2026-10-10, user: "its too hard to see the little rocks or arrows and the lines would help
-- players avoid them and actually see them". While a shooter draws, EnemyVisuals shows a red line
-- along the exact path the server locked (EnemyAttacks "Aim"), faded out by release; in flight each
-- shot gets a short red-orange trail behind it and is drawn a little bigger. Flat Beams/Trails, no
-- effect meshes.
V.AIM_COLOR = Color3.fromRGB(255, 60, 50)
V.TRAIL_COLOR = Color3.fromRGB(255, 96, 50)
V.AIM_CAP = 20 -- lines drawn at once, nearest first
V.FADE = 0.3 -- the line fades out over the draw's last 0.3 s (at most half the draw), gone at release
-- Bigger in flight so they read from the high camera; held copies keep their size.
V.FLIGHT_SCALE = { Arrow = 1.35, Rock = 1.3, Spit = 1.15, Icicle = 1.15, Fireball = 1.1 }

-- The aim line's look at server time `now`: a telegraph, not a guide. It shows the locked path,
-- brightening, then fades out to nothing at release; the shot flies that path with no line ahead
-- of it. (2026-10-10 testers: the line kept drawn in flight made shots "too easy to avoid... show
-- the path... have it fade away, and then have the item actually go on that path".) Width grows
-- 0.3 -> 0.5 over the draw (the "a little too hard to see" fix). Example: a 0.55 s draw fades over
-- its last 0.275 s: 0 s in: 0.6 opaque, 0.3 wide; 0.275 s in: 0.95; 0.4 s in: ~0.52; 0.55 s in: 0.
function V.aimLook(startedAt, releaseAt, now)
	local span = math.max(releaseAt - startedAt, 1e-3)
	local p = math.clamp((now - startedAt) / span, 0, 1)
	local width = 0.3 + 0.2 * p
	local fade = math.min(V.FADE, span * 0.5)
	local left = releaseAt - now
	if left <= 0 then
		return 0, width
	elseif left < fade then
		return 0.95 * left / fade, width
	end
	return 0.6 + 0.35 * math.clamp((now - startedAt) / (span - fade), 0, 1), width
end

-- Where along the drawn line (0-1) the aimed point sits: solid up to it, fading past it to where
-- the shot runs out or hits a wall. Example: aimed 20 studs out on a 71-stud path: 0.28.
function V.aimFade(aimDistance, length)
	return math.clamp((aimDistance or length) / math.max(length, 1e-3), 0.02, 0.98)
end

-- Up to `cap` keys of `items` ({[key] = {origin = Vector3}}), nearest to `from` first.
function V.nearest(items, from, cap)
	local list = {}
	for key, item in items do
		table.insert(list, { key = key, d = (item.origin - from).Magnitude })
	end
	table.sort(list, function(a, b)
		return a.d < b.d
	end)
	local keep = {}
	for i = 1, math.min(cap, #list) do
		keep[list[i].key] = true
	end
	return keep
end

-- A flying shot made readable: scaled up a little and given a short tapering trail. Call once it
-- is parented and pivoted to its first frame, so the trail doesn't streak in from the template's
-- spot. The trail's two points sit across the flight (frame's up axis), FaceCamera keeps it flat.
function V.readable(shot, kind, frame)
	local scale = V.FLIGHT_SCALE[kind] or 1.15
	if shot:IsA("Model") then
		shot:ScaleTo(shot:GetScale() * scale)
	elseif shot:IsA("BasePart") then
		shot.Size *= scale
	end
	shot:PivotTo(frame)
	local base = shot:IsA("BasePart") and shot or shot.PrimaryPart or shot:FindFirstChildWhichIsA("BasePart", true)
	if not base then
		return
	end
	local a0, a1 = Instance.new("Attachment"), Instance.new("Attachment")
	a0.Name, a1.Name = "TrailTop", "TrailBottom"
	a0.Parent, a1.Parent = base, base
	a0.WorldPosition = frame * Vector3.new(0, 0.2, 0)
	a1.WorldPosition = frame * Vector3.new(0, -0.2, 0)
	local trail = Instance.new("Trail")
	trail.Attachment0, trail.Attachment1 = a0, a1
	trail.Color = ColorSequence.new(V.TRAIL_COLOR)
	trail.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.15), NumberSequenceKeypoint.new(1, 1) })
	trail.WidthScale = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(1, 0.2) })
	trail.Lifetime = 0.3
	trail.MinLength = 0.05
	trail.FaceCamera = true
	trail.LightEmission = 1
	trail.LightInfluence = 0
	trail.Parent = base
end

return V
