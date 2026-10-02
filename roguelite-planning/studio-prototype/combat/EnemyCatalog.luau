-- Shared regular-enemy configuration. Only the server applies these values.
-- Native Pine Valley balance is authoritative ZombieTypes tuning. All other
-- numbers are provisional playtest baselines, not approved final balance.
local Types = require(script.Parent.ZombieTypes)
local MotionTuning = require(script.Parent.EnemyMotionTuning)
-- Wave-ready chase speeds against the 24 studs/s player base. Most melee close
-- at 65-75% of player speed, fast skirmishers near 85-90%, heavies and ranged
-- (which stop at range) near 50-58%. Kiting still works; standing still does not.
local ProvisionalSpeeds = {
	skeleton = 17,
	["ice-elf"] = 14,
	["bow-skeleton"] = 14,
	["ash-shaman"] = 13,
	["fire-goblin"] = 18,
	werewolf = 21,
	["obsidian-ogre"] = 12,
	["frozen-knight"] = 12,
	mummy = 13,
	["spitter-zombie"] = 13,
	crab = 16,
	["hermit-crab"] = 12,
	["rock-throwing-crab"] = 13,
	scorpion = 15,
	["ember-spider"] = 20,
	["frost-ghost"] = 16,
	["lava-slime"] = 13,
	snake = 15,
}
local C =
	{ List = {}, ById = {}, ByLegacy = { Regular = "regular-zombie", Baby = "baby-zombie", Mutant = "tank-zombie" } }
local function add(id, name, map, behavior, health, speed, damage, options)
	local d = {
		id = id,
		name = name,
		map = map,
		behavior = behavior,
		health = health,
		healthPerWave = 2,
		speed = speed,
		damage = damage,
		damagePerWave = 0.6,
		radius = 1.6,
		height = 6,
		stopRange = 3.2,
		attackRange = 4.6,
		attackImpact = 0.35,
		attackRecovery = 0.85,
		attackCooldown = 1.2,
		strideLength = 6,
		cadence = 0.8,
		balanceStatus = "Provisional playtest baseline",
		template = name:gsub("[^%w]", "") .. "_NPC",
		maxHeight = 4.5,
	}
	for k, v in options or {} do
		d[k] = v
	end
	C.ById[id] = d
	table.insert(C.List, d)
end
add(
	"regular-zombie",
	"Regular Zombie",
	"Pine Valley",
	"Melee",
	3,
	12,
	1,
	{ legacy = "Regular", template = "Zombie_NPC", attackImpact = 0.24, attackRecovery = 0.58, attackCooldown = 0.8 }
)
add(
	"baby-zombie",
	"Baby Zombie",
	"Pine Valley",
	"Melee",
	1,
	16,
	1,
	{ legacy = "Baby", template = "BabyZombie_NPC", attackImpact = 0.18, attackRecovery = 0.45, attackCooldown = 0.8 }
)
add("tank-zombie", "Tank Zombie", "Pine Valley", "Heavy", 20, 9.5, 2, {
	legacy = "Mutant",
	template = "MutantZombie_NPC",
	attackImpact = Types.Slam.impact,
	attackRecovery = Types.Slam.recovery,
	attackCooldown = Types.Slam.cooldown,
})
add("spitter-zombie", "Spitter Zombie", "Pine Valley", "Ranged", 5, 10, 1.5, {
	projectile = "Spit",
	projectileSpeed = 27,
	stopRange = 18,
	attackRange = 32,
	attackImpact = 0.52,
	attackRecovery = 1.15,
	attackCooldown = 2.5,
})
-- maxMoveCycles: short-legged scuttlers need more Move loops per second than the default 4,
-- or their feet glide (crab: 1.7-stud stride at 16 studs/s wants ~9). Crabs chase the player
-- straight: aiming ahead of a juking player made them veer off sideways (2026-10-01).
add(
	"crab",
	"Crab",
	"Beach Cove",
	"Melee",
	4,
	11,
	1,
	{ height = 3, radius = 1.8, strideLength = 3.5, maxMoveCycles = 10 }
)
-- gaitStride: ground covered per Move loop when the authored clip's own stride is far too short
-- to read at wave speed. The snake's slither (1.6 studs) and the slime's hop (1.2) looped about
-- once a second while the body slid 13-15 studs; at 5.5 studs they loop ~2.5 times a second.
add("snake", "Snake", "Beach Cove", "Lunge", 3, 12, 1.5, {
	gaitStride = 5.5,
	height = 3,
	radius = 1.2,
	attackRange = 15,
	hitRange = 3.4,
	stopRange = 9,
	lungeSpeed = 52,
	lungeDuration = 0.22,
	attackImpact = 0.38,
	attackRecovery = 1.15,
	attackCooldown = 2,
	strideLength = 5,
})
add("hermit-crab", "Hermit Crab", "Beach Cove", "Heavy", 12, 7, 2, {
	height = 4,
	radius = 2,
	healthPerWave = 5,
	attackImpact = 0.55,
	attackRecovery = 1.25,
	attackCooldown = 1.8,
	strideLength = 3.2,
	maxMoveCycles = 10,
})
add("rock-throwing-crab", "Rock-Throwing Crab", "Beach Cove", "Ranged", 6, 8, 2, {
	height = 3,
	projectile = "Rock",
	projectileSpeed = 26,
	stopRange = 18,
	attackRange = 32,
	attackImpact = 0.6,
	attackRecovery = 1.25,
	attackCooldown = 2.5,
	strideLength = 3.5,
	maxMoveCycles = 10,
})
add("skeleton", "Skeleton", "Desert Badlands", "Melee", 4, 12, 1.2)
add("bow-skeleton", "Bow Skeleton", "Desert Badlands", "Ranged", 4, 10, 1.5, {
	projectile = "Arrow",
	projectileSpeed = 35,
	stopRange = 20,
	attackRange = 36,
	attackImpact = 0.55,
	attackRecovery = 1.1,
	attackCooldown = 2.3,
})
add(
	"mummy",
	"Mummy",
	"Desert Badlands",
	"Heavy",
	10,
	8,
	2,
	{ healthPerWave = 4, attackImpact = 0.48, attackRecovery = 1.15, attackCooldown = 1.6 }
)
add("scorpion", "Scorpion", "Desert Badlands", "Lunge", 6, 10, 1.8, {
	height = 4,
	attackRange = 12,
	hitRange = 3.8,
	stopRange = 7,
	lungeSpeed = 36,
	lungeDuration = 0.24,
	attackImpact = 0.48,
	attackRecovery = 1.25,
	attackCooldown = 2.2,
	strideLength = 3.8,
})
add("frost-ghost", "Frost Ghost", "Frozen Pass", "Melee", 5, 11, 1.3, { height = 4, strideLength = 5 })
add(
	"werewolf",
	"Werewolf",
	"Frozen Pass",
	"Melee",
	8,
	16,
	1.8,
	{ healthPerWave = 3, attackImpact = 0.24, attackRecovery = 0.65, attackCooldown = 1, strideLength = 7 }
)
add(
	"frozen-knight",
	"Frozen Knight",
	"Frozen Pass",
	"Heavy",
	14,
	7.5,
	2.2,
	{ healthPerWave = 5, attackImpact = 0.58, attackRecovery = 1.3, attackCooldown = 1.9 }
)
add("ice-elf", "Ice Elf", "Frozen Pass", "Ranged", 5, 11, 1.8, {
	projectile = "Icicle",
	projectileSpeed = 32,
	stopRange = 20,
	attackRange = 36,
	attackImpact = 0.55,
	attackRecovery = 1.15,
	attackCooldown = 2.3,
})
add("fire-goblin", "Fire Goblin", "Volcanic Crater", "Melee", 4, 12, 1.3, { height = 5, strideLength = 5 })
add(
	"ember-spider",
	"Ember Spider",
	"Volcanic Crater",
	"Melee",
	2,
	17,
	1,
	{ height = 3, radius = 1.3, attackImpact = 0.2, attackRecovery = 0.52, attackCooldown = 0.9, strideLength = 3.8 }
)
add(
	"lava-slime",
	"Lava Slime",
	"Volcanic Crater",
	"Splitter",
	6,
	8,
	1.4,
	{
		height = 3,
		splitCount = 2,
		childScale = 0.6,
		attackImpact = 0.4,
		attackRecovery = 0.9,
		strideLength = 3,
		gaitStride = 5.5,
	}
)
add("obsidian-ogre", "Obsidian Ogre", "Volcanic Crater", "Heavy", 20, 7, 3, {
	healthPerWave = 7,
	height = 8,
	radius = 2.4,
	attackRange = 6,
	stopRange = 4.4,
	attackImpact = 0.65,
	attackRecovery = 1.5,
	attackCooldown = 2.2,
	strideLength = 6,
})
add("ash-shaman", "Ash Shaman", "Volcanic Crater", "Ranged", 6, 9, 2, {
	projectile = "Fireball",
	projectileSpeed = 25,
	stopRange = 20,
	attackRange = 36,
	attackImpact = 0.6,
	attackRecovery = 1.3,
	attackCooldown = 2.6,
})
for _, d in C.List do
	if not d.legacy and MotionTuning[d.id] then
		d.strideLength = MotionTuning[d.id].strideLength
	end
	if not d.legacy then
		d.speed = assert(ProvisionalSpeeds[d.id])
		d.speedStatus = "Provisional QA gameplay speed; not approved final balance"
	end
	-- Only the floating ghost animates by time; everything that touches the ground paces by it.
	d.timeBasedMovement = d.id == "frost-ghost"
	if d.legacy then
		local native = Types.get(d.legacy)
		for _, key in
			{ "health", "healthPerWave", "damagePerWave", "speed", "radius", "height", "stopRange", "cadence" }
		do
			d[key] = native[key]
		end
		d.damage = d.legacy == "Mutant" and Types.Slam.damage or native.damage
		d.attackRange = d.legacy == "Mutant" and Types.Slam.trigger or native.contactRange
		d.balanceStatus = "Existing authoritative Pine Valley tuning"
	end
end
function C.get(id)
	return C.ById[id] or C.ById[C.ByLegacy[id]]
end
function C.fromModel(npc)
	return C.get(npc:GetAttribute("EnemyId") or npc:GetAttribute("ZombieType") or "Regular")
end
function C.scaled(id, wave)
	local d = assert(C.get(id), "Unknown regular enemy: " .. tostring(id))
	local result = table.clone(d)
	local numeric = tonumber(wave) or 1
	if numeric ~= numeric then
		numeric = 1
	end
	local growth = math.clamp(math.floor(numeric) - 1, 0, 999)
	if d.legacy then
		local native = Types.scaled(d.legacy, growth + 1)
		result.health = native.health
		result.damage = d.legacy == "Mutant" and native.slamDamage or native.damage
	else
		result.health = d.health + d.healthPerWave * growth
		result.damage = d.damage + d.damagePerWave * growth
	end
	return result
end
-- Only an explicit server-owned attribute changes the established Pine Valley roster.
function C.forSlot(index, wave, roster)
	if type(roster) == "string" then
		local ids = {}
		for id in roster:gmatch("[^,%s]+") do
			if C.ById[id] then
				table.insert(ids, id)
			end
		end
		if #ids > 0 then
			return ids[(index - 1) % #ids + 1]
		end
	end
	return C.ByLegacy[Types.forSlot(index, wave)]
end
return C
