local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Debris = game:GetService("Debris")
local V = {}
local Motion = require(script.Parent.RocketMotion)
function V.mount(combat, visuals, options)
	options = options or {}
	local closed = false
	local template = combat:WaitForChild("RocketTemplate")
	local Explosion = require(combat:WaitForChild("RocketExplosionVisuals"))
	local explode = Explosion.mount(visuals, options)
	-- Build the 3D explosion once any player holds a Rocket Launcher (WeaponCatalog id '11', the
	-- only weapon RogueliteCombat launches as a rocket), well before its first impact.
	if not options.preview then
		local states = combat:WaitForChild("PlayerStates")
		local function watch(slot)
			if slot:GetAttribute("WeaponId") == nil then
				return
			end
			local function check()
				if slot:GetAttribute("WeaponId") == "11" then
					Explosion.warm()
				end
			end
			slot:GetAttributeChangedSignal("WeaponId"):Connect(check)
			check()
		end
		states.DescendantAdded:Connect(watch)
		for _, slot in states:GetDescendants() do
			watch(slot)
		end
	end
	local active = {}
	local smokeFolder = Instance.new("Folder")
	smokeFolder.Name = "RPGCloudTrail"
	smokeFolder.Parent = visuals
	local puffs = {}
	local spacing, lifetime, maxPuffs = 0.75, 1.15, 144
	local rocketLength = template:GetAttribute("Length")
	-- Different silhouettes: tall billow, wide bank, diagonal plume, rounded
	-- cluster, trailing beads, and a small split cloud. Each smoothly contracts.
	local shapes = {
		{ { 0, 0.3, 0, 1.15 }, { -0.48, -0.12, 0, 0.82 }, { 0.46, -0.08, 0.08, 0.9 }, { 0.1, 0.78, 0.02, 0.72 } },
		{ { -0.55, 0, 0, 0.95 }, { 0, 0.22, 0.06, 1.1 }, { 0.58, -0.06, 0, 0.85 }, { 0.98, -0.2, 0.05, 0.38 } },
		{ { -0.48, -0.3, 0, 0.7 }, { -0.1, 0.04, 0.1, 1.05 }, { 0.32, 0.48, 0, 0.98 }, { 0.67, 0.7, 0.02, 0.48 } },
		{ { 0, 0.2, 0, 1.2 }, { -0.5, -0.18, 0.08, 0.75 }, { 0.45, -0.12, 0, 0.82 } },
		{ { -0.28, 0.18, 0, 1.1 }, { 0.28, -0.1, 0.08, 0.85 }, { 0.82, -0.2, 0, 0.48 }, { 1.15, -0.26, 0.02, 0.26 } },
		{ { -0.28, 0.08, 0, 0.95 }, { 0.35, 0.24, 0.08, 0.85 }, { 0.7, -0.14, 0, 0.55 } },
	}
	local function emitCloud(position, born, seed)
		local camera = workspace.CurrentCamera
		if not options.preview and camera and (camera.CFrame.Position - position).Magnitude > 150 then
			return
		end
		if #puffs >= maxPuffs then
			local oldest = table.remove(puffs, 1)
			oldest.model:Destroy()
		end
		local model = Instance.new("Model")
		model.Name = "SmokeCloud"
		model:SetAttribute("BornAt", born)
		model.Parent = smokeFolder
		local width = 0.83 + (seed % 3) * 0.025
		local variant = seed % #shapes + 1
		model:SetAttribute("Variant", variant)
		local puff = { model = model, born = born, position = position, parts = {}, width = width }
		for i, lobe in shapes[variant] do
			local part = Instance.new("Part")
			part.Name = "CloudLobe"
			part.Shape = Enum.PartType.Ball
			part.Anchored = true
			part.CanCollide = false
			part.CanTouch = false
			part.CanQuery = false
			part.CastShadow = false
			part.Material = Enum.Material.SmoothPlastic
			part.Color = i == 2 and Color3.fromRGB(250, 251, 255) or Color3.fromRGB(213, 219, 230)
			local mirrored = seed % 2 == 0 and 1 or -1
			local offset = Vector3.new(lobe[1] * mirrored, lobe[2], lobe[3])
			local size = Vector3.new(1, 0.92, 0.88) * width * lobe[4]
			part.Size = size
			part.Position = position + offset * width
			part.Parent = model
			table.insert(puff.parts, { part = part, offset = offset, size = size })
		end
		table.insert(puffs, puff)
	end
	local function remove(id)
		local r = active[id]
		if r then
			r.model:Destroy()
			active[id] = nil
		end
	end
	local function handle(action, id, position, velocity, started, range, projectileScale, targetDistance)
		if closed then
			return
		end
		if action == "Redirect" then
			local r = active[id]
			if not r then
				return
			end
			r.origin = position
			r.velocity = velocity
			r.started = started
			r.range = range
			r.targetDistance = targetDistance or range
			r.nextSmoke = r.length
		elseif action == "Launch" then
			Explosion.warm()
			local model = template:Clone()
			model.Name = "FlyingRPG_" .. id
			model:ScaleTo(template:GetScale() * (projectileScale or 1))
			model.Parent = visuals
			local speed = velocity.Magnitude
			local age = math.max(0, workspace:GetServerTimeNow() - started)
			local r = {
				model = model,
				origin = position,
				velocity = velocity,
				started = started,
				range = range,
				targetDistance = targetDistance or range,
				length = rocketLength * (projectileScale or 1),
				-- The launch origin is the muzzle and position tracks the rocket tip.
				-- Do not emit until its exhaust/tail has cleared that opening.
				nextSmoke = rocketLength * (projectileScale or 1)
					+ math.max(0, math.floor((math.max(0, age - lifetime) * speed - rocketLength) / spacing)) * spacing,
			}
			active[id] = r
			model:PivotTo(CFrame.lookAt(position, position + velocity) * CFrame.new(0, 0, r.length / 2))
		else
			remove(id)
			if action == "Impact" then
				explode(position, velocity) -- impact packet: position, damage radius
			end
		end
	end
	local function step()
		if closed then
			return
		end
		local now = workspace:GetServerTimeNow()
		for id, r in active do
			local age = math.max(0, now - r.started)
			local distance = age * r.velocity.Magnitude
			if distance > r.range + 10 then
				remove(id)
			else
				local traveled = math.min(distance, r.range)
				local tip = Motion.position(r.origin, r.velocity.Unit, traveled, r.targetDistance, id)
				local heading = Motion.direction(r.origin, r.velocity.Unit, traveled, r.targetDistance, id)
				r.model:PivotTo(CFrame.lookAt(tip, tip + heading) * CFrame.new(0, 0, r.length / 2))
				-- Sample the traveled path, not the current frame position. Low frame rates
				-- still leave a continuous trail with correctly staggered particle ages.
				r.nextSmoke = math.max(
					r.nextSmoke,
					r.length
						+ math.max(0, math.floor((traveled - r.velocity.Magnitude * lifetime - r.length) / spacing))
							* spacing
				)
				local samples = 0
				while r.nextSmoke <= traveled and samples < 40 do
					local sampleTip = Motion.position(r.origin, r.velocity.Unit, r.nextSmoke, r.targetDistance, id)
					local sampleDirection =
						Motion.direction(r.origin, r.velocity.Unit, r.nextSmoke, r.targetDistance, id)
					local tail = sampleTip - sampleDirection * r.length
					emitCloud(
						tail,
						r.started + r.nextSmoke / r.velocity.Magnitude,
						math.floor(r.nextSmoke / spacing) + id
					)
					r.nextSmoke += spacing
					samples += 1
				end
			end
		end
		-- Clouds stay in world space when the rocket moves or is destroyed. Older
		-- clouds contract into smaller, simpler puffs and fade before newer ones.
		for i = #puffs, 1, -1 do
			local puff = puffs[i]
			local age = math.max(0, now - puff.born)
			if age >= lifetime then
				puff.model:Destroy()
				table.remove(puffs, i)
			else
				local t = age / lifetime
				local smooth = t * t * (3 - 2 * t)
				local growth = 1.12 - 0.94 * smooth
				local compact = 1 - 0.4 * smooth
				local fade = math.clamp((t - 0.08) / 0.92, 0, 1)
				local position = puff.position + Vector3.yAxis * (t * 0.45)
				for _, lobe in puff.parts do
					lobe.part.Size = lobe.size * growth
					lobe.part.Position = position + lobe.offset * puff.width * growth * compact
					lobe.part.Transparency = 0.06 + 0.94 * fade
				end
			end
		end
	end
	if options.preview then
		return {
			handle = handle,
			step = step,
			destroy = function()
				if closed then
					return
				end
				closed = true
				for id in active do
					remove(id)
				end
				for _, puff in puffs do
					puff.model:Destroy()
				end
				table.clear(puffs)
				smokeFolder:Destroy()
			end,
		}
	end
	combat:WaitForChild("RocketFX").OnClientEvent:Connect(handle)
	RunService.RenderStepped:Connect(step)
end
return V
