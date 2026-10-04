-- Pets on the server (RARITY_GODLY_ARMOR.md step 6): the follower folders clients draw from, and
-- every pet ability. Numbers live in PetConfig. Studio: SSS.PetService, a SANDBOXED Script
-- (Capabilities copied from SSS.RogueliteCombat), so it may require the sandboxed combat modules.
--
-- Server authority:
--   - The equipped pet and its tier come only from ProfilePet / ProfilePets (ProfileService).
--   - Abilities run only in the Combat phase, only for players in the run (ShopService.states) with a
--     living, not-downed character, and only while combat.ZombiesEnabled is on.
--   - Never targets practice dummies (ZombieDeath.isPractice, LobbyDummy, PracticeTarget).
--   - Cooldowns are kept here. A use that finds no target retries soon without spending it.
-- Stat bonuses (Bee, Monkey, Lucky Cat, Cheetah Cub, Baby Dragon) are applied by CharacterService.
--
-- workspace.RoguelitePets holds one Folder per player with an equipped pet (named by UserId,
-- attributes PetId, Tier, OwnerUserId); PetVisuals draws a follower for each, in every phase.
-- RS.RogueliteCombat.PetFX fires (ownerUserId, kind, data) to clients near the owner for the visuals.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Tags = game:GetService("CollectionService")
local RS = game:GetService("ReplicatedStorage")
local SSS = game:GetService("ServerScriptService")
local combat = RS:WaitForChild("RogueliteCombat")
local Pets = require(combat:WaitForChild("PetConfig"))
local Stats = require(combat:WaitForChild("CharacterStats"))
local Death = require(combat:WaitForChild("ZombieDeath"))
local Characters = require(SSS:WaitForChild("CharacterService"))
local Effects = require(SSS:WaitForChild("CombatEffectsService"))
local Shards = require(SSS:WaitForChild("ShardDropService"))
local Shop = require(SSS:WaitForChild("ShopService"))
local Batch = require(combat:WaitForChild("ShotBatch"))

local fx = combat:FindFirstChild("PetFX")
if not fx then
	fx = Instance.new("RemoteEvent")
	fx.Name = "PetFX"
	fx.Sandboxed = true
	fx.Capabilities = SecurityCapabilities.new(Enum.SecurityCapability.Basic, Enum.SecurityCapability.RemoteEvent)
	fx.Parent = combat
end
assert(fx:IsA("RemoteEvent"), "RogueliteCombat.PetFX must be a RemoteEvent")

local folder = workspace:FindFirstChild("RoguelitePets")
if not folder then
	folder = Instance.new("Folder")
	folder.Name = "RoguelitePets"
	folder.Parent = workspace
end

local state = {} -- player -> {id, tier, nextAt, burstReady, burstToken}
-- To players near the pet's owner, and the owner (ShotBatch.fire): lobby players don't get arena pets.
local function send(player, kind, data)
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	Batch.fire(fx, root and root.Position, player, player.UserId, kind, data)
end

-- The follower folder ---------------------------------------------------------------------------
local function publish(player)
	local id, tier = Pets.equipped(player:GetAttribute("ProfilePet"), player:GetAttribute("ProfilePets"))
	local f = folder:FindFirstChild(tostring(player.UserId))
	local s = state[player]
	if not id then
		if f then
			f:Destroy()
		end
		if s and s.id == "CheetahCub" then
			Characters.setPetTemp(player, nil)
		end
		state[player] = nil
		return
	end
	if not f then
		f = Instance.new("Folder")
		f.Name = tostring(player.UserId)
		f:SetAttribute("OwnerUserId", player.UserId)
		f.Parent = folder
	end
	f:SetAttribute("PetId", id)
	f:SetAttribute("Tier", tier)
	if not s or s.id ~= id then
		if s and s.id == "CheetahCub" then
			Characters.setPetTemp(player, nil)
		end
		-- A pet equipped mid-wave waits 2 s before its first use.
		state[player] = { id = id, tier = tier, nextAt = os.clock() + 2, burstReady = 0, burstToken = 0 }
	else
		s.tier = tier
	end
end

local function watch(player)
	player:GetAttributeChangedSignal("ProfilePet"):Connect(function()
		publish(player)
	end)
	player:GetAttributeChangedSignal("ProfilePets"):Connect(function()
		publish(player)
	end)
	publish(player)
end
Players.PlayerAdded:Connect(watch)
for _, p in Players:GetPlayers() do
	task.spawn(watch, p)
end
Players.PlayerRemoving:Connect(function(p)
	state[p] = nil
	local f = folder:FindFirstChild(tostring(p.UserId))
	if f then
		f:Destroy()
	end
end)

-- Run, player and enemy checks ------------------------------------------------------------------
local function run()
	return RS:FindFirstChild("RogueliteRunState")
end
local function wave()
	local r = run()
	return math.max(1, (r and r:GetAttribute("Wave")) or 1)
end
local function rootOf(player)
	local c = player.Character
	local h = c and c:FindFirstChildOfClass("Humanoid")
	local r = c and c:FindFirstChild("HumanoidRootPart")
	if h and r and h.Health > 0 then
		return r, h
	end
end
-- In the run: a ShopService player, alive, not downed, not in the lobby preview.
local function inRun(player)
	return Shop.states[player] ~= nil
		and Characters.states[player] ~= nil
		and player:GetAttribute("LobbyPreviewActive") ~= true
		and player:GetAttribute("RunDown") == nil
		and rootOf(player) ~= nil
end
-- A weapon-like damage source for the pet (like CombatEffectsService's armorSource): hits count as
-- the owner's (kill credit, crystals), with the owner's current stats. id 'Pet' has no weapon sound.
local function source(player)
	local s = Characters.states[player]
	local character = player.Character
	if not s or not s.stats or not character then
		return
	end
	return { id = "Pet", owner = player, character = character, stats = s.stats, damage = 0 }
end

-- Where reach is measured to (RogueliteCombat.server reachPoint): a map boss to the nearest point
-- of its body boxes, every other enemy to its root.
local function reachPoint(npc, root, from)
	if not npc:GetAttribute("IsMapBoss") then
		return root.Position
	end
	local best, bestDistance = root.Position, (root.Position - from).Magnitude
	-- The Hammer's hammer and the hands holding it aren't his body (the map-boss Hammer keeps the old
	-- 16-part template, R9; RogueliteCombat.server reachPoint).
	local hammer = npc:GetAttribute("MapBossId") == "Hammer"
	for _, p in npc:GetChildren() do
		if (p:IsA("MeshPart") or p == root) and not (hammer and (p.Name == "Hammer" or p.Name == "LeftHand" or p.Name == "RightHand")) then
			local l = p.CFrame:PointToObjectSpace(from)
			local h = p.Size * 0.5
			local q = p.CFrame:PointToWorldSpace(
				Vector3.new(math.clamp(l.X, -h.X, h.X), math.clamp(l.Y, -h.Y, h.Y), math.clamp(l.Z, -h.Z, h.Z))
			)
			local distance = (q - from).Magnitude
			if distance < bestDistance then
				best, bestDistance = q, distance
			end
		end
	end
	return best
end
-- Living, real enemies within `range` of `from`: {npc, h, r, at (reach point), distance}, nearest first.
local function enemies(from, range)
	local list = {}
	for _, npc in Tags:GetTagged("RogueliteZombie") do
		local h = npc:FindFirstChildOfClass("Humanoid")
		local r = npc:FindFirstChild("HumanoidRootPart")
		if
			h
			and r
			and h.Health > 0
			and npc:IsDescendantOf(workspace)
			and not Death.isPractice(npc)
			and not npc:GetAttribute("LobbyDummy")
			and not npc:GetAttribute("PracticeTarget")
		then
			local at = reachPoint(npc, r, from)
			local distance = (at - from).Magnitude
			if distance <= range then
				table.insert(list, { npc = npc, h = h, r = r, at = at, distance = distance })
			end
		end
	end
	table.sort(list, function(a, b)
		return a.distance < b.distance
	end)
	return list
end
-- Run players near `from` (the owner included): {player, root, h, distance}.
local function teammates(from, range)
	local list = {}
	for p in Shop.states do
		if inRun(p) then
			local r, h = rootOf(p)
			local distance = (r.Position - from).Magnitude
			if distance <= range then
				table.insert(list, { player = p, root = r, h = h, distance = distance })
			end
		end
	end
	return list
end
local function flat(v)
	return Vector3.new(v.X, 0, v.Z)
end
local function knock(e, from, speed)
	local delta = flat(e.r.Position - from)
	-- One shove per 0.12 s, shared with weapon knockback through CombatEffectsService's server table
	-- (an attribute here replicated to every client on each shove; launch audit P12).
	if delta.Magnitude < 0.01 or os.clock() - (Effects.knockedAt and Effects.knockedAt[e.npc] or -1e6) <= 0.12 then
		return
	end
	e.r:ApplyImpulse(delta.Unit * speed * e.r.AssemblyMass * (e.npc:GetAttribute("IsBoss") and 0.25 or 1))
	if Effects.knockedAt then
		Effects.knockedAt[e.npc] = os.clock()
	end
end
local function alive(e)
	return e.h.Health > 0 and e.npc.Parent ~= nil
end

-- Abilities -------------------------------------------------------------------------------------
-- Each returns true when it did something (the cooldown starts), false to retry soon.
local ABILITY = {}

ABILITY.GoldenRetriever = function(p, root, tier)
	-- The nearest crystal it may take (ShardDropService buckets, ties to the older one).
	-- D.fetch re-checks phase, rest time and ownership.
	local best = Shards.nearest(p, root.Position, Pets.get("GoldenRetriever", "range", tier))
	if best and Shards.fetch(p, best) then
		send(p, "Fetch", { position = best.origin })
		return true
	end
	return false
end

ABILITY.Bunny = function(p, root, tier)
	local best, worst
	for _, t in teammates(root.Position, Pets.get("Bunny", "range", tier)) do
		local fraction = t.h.Health / math.max(1, t.h.MaxHealth)
		if t.h.Health < t.h.MaxHealth and (not best or fraction < worst) then
			best, worst = t, fraction
		end
	end
	if not best then
		return false -- nobody is hurt
	end
	Characters.heal(best.player, Pets.get("Bunny", "heal", tier))
	send(p, "Carrot", { target = best.player.UserId, position = best.root.Position })
	return true
end

ABILITY.Frog = function(p, root, tier)
	local radius = Pets.get("Frog", "radius", tier)
	local list = enemies(root.Position, Pets.get("Frog", "range", tier))
	if #list == 0 then
		return false
	end
	-- The densest group: the enemy with the most others within the slam radius.
	local center, most = list[1].at, -1
	for _, e in list do
		local n = 0
		for _, o in list do
			if (o.at - e.at).Magnitude <= radius then
				n += 1
			end
		end
		if n > most then
			center, most = e.at, n
		end
	end
	local src = source(p)
	if not src then
		return false
	end
	local damage = Pets.damage("Frog", tier, wave())
	local knockback = Pets.get("Frog", "knockback", tier)
	for _, e in enemies(center, radius) do
		Effects.hit(e.npc, damage, src, true)
		if alive(e) then
			knock(e, center, knockback)
		end
	end
	send(p, "Slam", { position = center, radius = radius })
	return true
end

ABILITY.Penguin = function(p, root, tier)
	local list = enemies(root.Position, Pets.get("Penguin", "range", tier))
	if #list == 0 then
		return false
	end
	local dir = flat(list[1].at - root.Position)
	dir = dir.Magnitude > 0.1 and dir.Unit or flat(root.CFrame.LookVector).Unit
	local from = root.Position
	local to = from + dir * Pets.get("Penguin", "slide", tier)
	local width = Pets.get("Penguin", "width", tier)
	local src = source(p)
	if not src then
		return false
	end
	local damage = Pets.damage("Penguin", tier, wave())
	local slow = Pets.get("Penguin", "slow", tier)
	local slowFor = Pets.get("Penguin", "slowFor", tier)
	local length = (to - from).Magnitude
	for _, e in enemies(from + dir * length / 2, length / 2 + width + 2) do
		-- Distance from the slide line (flat).
		local rel = flat(e.at - from)
		local along = math.clamp(rel:Dot(dir), 0, length)
		if (rel - dir * along).Magnitude <= width then
			Effects.hit(e.npc, damage, src, true)
			if alive(e) then
				Effects.status(e.npc, src, "Slow", slowFor, slow, false)
			end
		end
	end
	send(p, "Slide", { from = from, to = to })
	return true
end

ABILITY.Fox = function(p, root, tier)
	local e = enemies(root.Position, Pets.get("Fox", "range", tier))[1]
	local src = e and source(p)
	if not src then
		return false
	end
	Effects.hit(e.npc, Pets.damage("Fox", tier, wave()) * Stats.mult(src.stats.Damage), src, true)
	send(p, "Pounce", { position = e.at, target = e.npc })
	return true
end

ABILITY.Bee = function(p, root, tier)
	local e = enemies(root.Position, Pets.get("Bee", "range", tier))[1]
	local src = e and source(p)
	if not src then
		return false
	end
	-- One poison stack, the same strength as a weapon poison from this player.
	local s = src.stats
	local amount = 3 * Stats.mult(s.Damage) * Stats.mult(s.ElementalDamage) * Stats.mult(s.PoisonDamage)
	Effects.status(e.npc, src, "Poison", 4 * Stats.mult(s.Duration), amount, false)
	send(p, "Sting", { position = e.at, target = e.npc })
	return true
end

ABILITY.Turtle = function(p, root, tier)
	-- Prefer players without a shield, then the most hurt (lowest health fraction).
	local best, bestKey
	for _, t in teammates(root.Position, Pets.get("Turtle", "range", tier)) do
		local key = (Characters.hasPetShield(t.player) and 10 or 0) + t.h.Health / math.max(1, t.h.MaxHealth)
		if not best or key < bestKey then
			best, bestKey = t, key
		end
	end
	if not best then
		return false
	end
	local duration = Pets.get("Turtle", "shieldFor", tier)
	if not Characters.givePetShield(best.player, duration) then
		return false
	end
	send(p, "Shield", { target = best.player.UserId, duration = duration })
	return true
end

ABILITY.Owl = function(p, root, tier)
	local best, bestKey
	for _, e in enemies(root.Position, Pets.get("Owl", "range", tier)) do
		local boss = (e.npc:GetAttribute("IsBoss") or e.npc:GetAttribute("IsMapBoss")) and 1 or 0
		local key = boss * 1e9 + e.h.MaxHealth
		if not best or key > bestKey then
			best, bestKey = e, key
		end
	end
	if not best then
		return false
	end
	local duration = Pets.get("Owl", "markFor", tier)
	local untilTime = workspace:GetServerTimeNow() + duration
	best.npc:SetAttribute("PetMark_" .. p.UserId, Pets.get("Owl", "bonus", tier))
	best.npc:SetAttribute("PetMarkUntil_" .. p.UserId, untilTime)
	send(p, "Mark", { target = best.npc, position = best.at, untilTime = untilTime })
	return true
end

ABILITY.BabyDragon = function(p, root, tier)
	local e = enemies(root.Position, Pets.get("BabyDragon", "range", tier))[1]
	local src = e and source(p)
	if not src then
		return false
	end
	local length = Pets.get("BabyDragon", "cone", tier)
	local cosHalf = math.cos(math.rad(Pets.get("BabyDragon", "coneAngle", tier)))
	-- The dragon flies toward the target first: the breath starts up to 5 studs short of it.
	local toTarget = flat(e.at - root.Position)
	local dir = toTarget.Magnitude > 0.1 and toTarget.Unit or flat(root.CFrame.LookVector).Unit
	local origin = root.Position + dir * math.max(0, toTarget.Magnitude - 5)
	local damage = Pets.damage("BabyDragon", tier, wave())
	local s = src.stats
	local burn = 6 * Stats.mult(s.Damage) * Stats.mult(s.ElementalDamage) * Stats.mult(s.BurnDamage)
	for _, o in enemies(origin, length) do
		local rel = flat(o.at - origin)
		if rel.Magnitude < 0.5 or rel.Unit:Dot(dir) >= cosHalf then
			Effects.hit(o.npc, damage, src, true)
			if alive(o) then
				Effects.status(o.npc, src, "Burn", 3 * Stats.mult(s.Duration), burn, false)
			end
		end
	end
	send(p, "Breath", { from = origin, to = origin + dir * length, target = e.npc })
	return true
end

-- Cheetah Cub: a short speed burst after real damage (CharacterService.contact), with a cooldown.
-- CharacterService hooks add listeners, so nothing else is chained here.
Characters.onDamaged = function(player, actual)
	local s = state[player]
	local r = run()
	if not s or s.id ~= "CheetahCub" or not r or r:GetAttribute("Phase") ~= "Combat" or not inRun(player) then
		return
	end
	local now = os.clock()
	if now < s.burstReady then
		return
	end
	local d = Pets.ById.CheetahCub
	s.burstReady = now + d.burstCooldown
	s.burstToken += 1
	local token = s.burstToken
	Characters.setPetTemp(player, { MoveSpeed = d.burst })
	send(player, "Burst", { duration = d.burstFor })
	task.delay(d.burstFor, function()
		local now2 = state[player]
		if now2 == s and s.burstToken == token then
			Characters.setPetTemp(player, nil)
		end
	end)
end
-- Turtle shell popped by a hit.
Characters.onPetShieldPop = function(player)
	local r = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
	Batch.fire(fx, r and r.Position, player, 0, "ShieldPop", { target = player.UserId, position = r and r.Position })
end

-- The loop ---------------------------------------------------------------------------------------
local wasCombat = false
local elapsed = 0
RunService.Heartbeat:Connect(function(dt)
	elapsed += dt
	if elapsed < 0.1 then
		return
	end
	elapsed = 0
	local r = run()
	local isCombat = r ~= nil and r:GetAttribute("Phase") == "Combat" and combat:GetAttribute("ZombiesEnabled") == true
		and combat:GetAttribute("RunPaused") ~= true -- plan L: pets rest while the run is paused
		-- and through a boss entrance (BossService.INTRO): nobody attacks during its cutscene.
		and (combat:GetAttribute("CinematicUntil") or 0) <= workspace:GetServerTimeNow()
	local now = os.clock()
	if isCombat and not wasCombat then
		-- A new wave: every pet waits half its cooldown before its first use.
		for _, s in state do
			s.nextAt = now + (Pets.get(s.id, "every", s.tier) or 0) * 0.5
		end
	end
	wasCombat = isCombat
	if not isCombat then
		return
	end
	for player, s in state do
		local ability = ABILITY[s.id]
		if ability and now >= s.nextAt and player.Parent and inRun(player) then
			local root = rootOf(player)
			local ok, did = pcall(ability, player, root, s.tier)
			if not ok then
				warn("PetService", s.id, did)
			end
			s.nextAt = now + ((ok and did) and Pets.get(s.id, "every", s.tier) or 0.5)
		end
	end
end)
