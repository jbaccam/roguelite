-- Cosmetic held ammo only. The server's shot flight (EnemyAttacks) exclusively owns collision/damage.
local combat = script.Parent
local Motion = require(combat.EnemyMotion)
local Visuals = require(combat.EnemyProjectileVisuals)
local H = {}
-- Casters hold the spell they throw: the Shaman keeps a small ember in his
-- open palm that swells into the full fireball through the wind-up; the Ice
-- Elf conjures its icicle in the throwing fist. Both vanish at release, when
-- the flying shot (EnemyVisuals, built from the same visuals) takes over.
local SPELLS = { ["ash-shaman"] = { kind = "Fireball", idle = 0.45 }, ["ice-elf"] = { kind = "Icicle", idle = 0 } }
local states = setmetatable({}, { __mode = "k" })
local function removeArrow(s)
	if s.arrow then
		s.arrow:Destroy()
		s.arrow = nil
	end
end
local function removeSpell(s)
	if s.spell then
		s.spell:Destroy()
		s.spell = nil
	end
end
function H.remove(npc)
	local s = states[npc]
	if not s then
		return
	end
	removeArrow(s)
	removeSpell(s)
	for part, transparency in s.held do
		if part.Parent then
			part.LocalTransparencyModifier = transparency
		end
	end
	states[npc] = nil
end
local function updateSpell(npc, config, data, poses, age)
	local spell = SPELLS[config.id]
	local s = states[npc]
	if not s then
		s = { held = {} }
		states[npc] = s
	end
	local attacking = age and age >= 0 and age <= config.attackRecovery
	local grow = spell.idle
	if attacking then
		-- Swells over the wind-up, gone from release until recovery ends.
		grow = age < config.attackImpact and spell.idle + (1 - spell.idle) * math.clamp(age / (config.attackImpact * 0.85), 0, 1)
			or 0
	end
	local origin = grow > 0.01 and Motion.projectileOrigin(npc, data, poses)
	if not origin then
		removeSpell(s)
		return
	end
	if not s.spell then
		s.spell = Visuals.build(spell.kind)
		s.spell.Name = "Held" .. spell.kind
		s.spellScale = 1
		s.spell.Parent = workspace
	end
	local ratio = npc:GetScale() / (npc:GetAttribute("EnemyBaselineModelScale") or 1)
	local scale = math.max(0.05, grow * ratio)
	if math.abs(scale - s.spellScale) > 1e-3 then
		s.spell:ScaleTo(scale)
		s.spellScale = scale
	end
	local root = npc:FindFirstChild("HumanoidRootPart")
	local facing = root and root.CFrame.LookVector or Vector3.zAxis
	s.spell:PivotTo(CFrame.lookAt(origin, origin + facing))
end
function H.update(npc, config, data, poses, age, authoredTime)
	if SPELLS[config.id] then
		return updateSpell(npc, config, data, poses, age)
	end
	if config.id ~= "bow-skeleton" and config.id ~= "rock-throwing-crab" then
		return
	end
	local s = states[npc]
	if not s then
		s = { held = {} }
		states[npc] = s
		for _, part in npc:GetDescendants() do
			local name = part.Name:lower()
			if part:IsA("BasePart") and name:find("held") and name:find("rock") then
				s.held[part] = part.LocalTransparencyModifier
			end
		end
	end
	local attacking = age and age >= 0 and age <= config.attackRecovery
	if config.id == "rock-throwing-crab" then
		for part, transparency in s.held do
			if part.Parent then
				part.LocalTransparencyModifier = attacking and age >= config.attackImpact and 1 or transparency
			end
		end
		return
	end
	local p = data.projectile
	local show = p and attacking and age < config.attackImpact and authoredTime >= (p.showStart or 0.25)
	if not show then
		removeArrow(s)
		return
	end
	if not s.arrow then
		local folder = combat:FindFirstChild("EnemyProjectileTemplates")
		local template = folder and folder:FindFirstChild("Arrow")
		if not template then
			return
		end
		local arrow = template:Clone()
		arrow.Name = "HeldEnemyArrow"
		for _, part in arrow:GetDescendants() do
			if part:IsA("BasePart") then
				part.Anchored = true
				part.CanCollide = false
				part.CanTouch = false
				part.CanQuery = false
			end
		end
		if arrow:IsA("BasePart") then
			arrow.Anchored = true
			arrow.CanCollide = false
			arrow.CanTouch = false
			arrow.CanQuery = false
		end
		arrow.Parent = workspace
		s.arrow = arrow
	end
	local origin, direction = Motion.arrowPose(npc, data, poses)
	if origin then
		s.arrow:PivotTo(CFrame.lookAt(origin, origin + direction))
	end
end
return H
