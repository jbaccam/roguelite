-- Server-owned enemy movement and test-wave lifecycle. Katana damage is in RogueliteCombat.
local Players = game:GetService("Players")
local ServerStorage = game:GetService("ServerStorage")
local PathfindingService = game:GetService("PathfindingService")
local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
local PhysicsService = game:GetService("PhysicsService")
local combat = game:GetService('ReplicatedStorage'):WaitForChild('RogueliteCombat')
local Role = require(game:GetService('ServerScriptService'):WaitForChild('ServerRole'))
-- Lobby servers run no waves; their maps are parked (ServerRole).
if Role.get() == 'Lobby' then return end
local Death = require(combat:WaitForChild('ZombieDeath'))
local Types = require(combat:WaitForChild('ZombieTypes'))
local EnemyCatalog = require(combat:WaitForChild('EnemyCatalog'))
local RunSetupRules = require(game:GetService('ReplicatedStorage'):WaitForChild('RunSetupRules'))
local EnemyAttacks = require(script.Parent:WaitForChild('EnemyAttacks'))
local Attacks = require(script.Parent:WaitForChild('ZombieAttacks'))
-- The admin panel's Hammer boss spawns (AdminSpawn below). This script and BossService are unsandboxed.
local Bosses = require(script.Parent:WaitForChild('BossService'))
local BossMotion = require(combat:WaitForChild('BossMotion'))
-- Hammer plus the MapBossDefs ids; MapBossService is required on first use (it needs the generated timing).
local BossIds = require(combat:WaitForChild('AdminConfig')).BossIds
local waveGeneration = 0
-- Admin Pause (ShopService.adminPause): no new spawns until Resume. Looked up lazily, because
-- ShopService creates RogueliteRunState.
local function adminPaused()
    local run = game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteRunState')
    -- Plan L: a paused run (RunPaused) spawns nothing either.
    return (run ~= nil and run:GetAttribute('AdminPaused') == true) or combat:GetAttribute('RunPaused') == true
end

combat:SetAttribute('ZombieCount',combat:GetAttribute('ZombieCount') or 5)
local function spawnCount() return math.clamp(combat:GetAttribute('ZombieCount') or 5,0,100) end
local COLLISION_GROUP = "RogueliteZombies"
if not PhysicsService:IsCollisionGroupRegistered(COLLISION_GROUP) then
    PhysicsService:RegisterCollisionGroup(COLLISION_GROUP)
end
PhysicsService:CollisionGroupSetCollidable(COLLISION_GROUP, COLLISION_GROUP, false)

local TweenService = game:GetService("TweenService")
local templates = ServerStorage:WaitForChild("RogueliteNPCs")
local template = templates:WaitForChild("Zombie_NPC")
local folder = Instance.new("Folder")
folder.Name = "RogueliteEnemies"
folder.Parent = workspace

local SpatialGrid = require(script.Parent:WaitForChild("EnemySpatialGrid"))
local neighborGrid = SpatialGrid.new(folder, 4.5)
-- Registered before enemy callbacks: one lazy snapshot per Heartbeat, never across frames.
RunService.Heartbeat:Connect(function() neighborGrid:invalidate() end)
folder.ChildAdded:Connect(function() neighborGrid:invalidate() end)
folder.ChildRemoved:Connect(function() neighborGrid:invalidate() end)

-- Pathfinding budget: ComputeAsync is the costliest call here and every blocked zombie asked once
-- a second, so the server shares PATH_RATE computes per second (bursts up to PATH_BURST), oldest
-- request first. A zombie waiting its turn keeps its last path, or holds as it did mid-compute.
-- Each zombie has at most one request queued; one no longer wanted (zombie gone, or back in
-- sight) is dropped without spending the budget.
local PATH_RATE, PATH_BURST = 10, 10
local pathQueue, pathHead, pathTail, pathTokens = {}, 1, 0, PATH_BURST
local function queuePath(job)
    pathTail += 1
    pathQueue[pathTail] = job
end
RunService.Heartbeat:Connect(function(dt)
    pathTokens = math.min(PATH_BURST, pathTokens + dt * PATH_RATE)
    while pathHead <= pathTail do
        local job = pathQueue[pathHead]
        if job.wanted() then
            if pathTokens < 1 then break end
            pathTokens -= 1
            task.spawn(job.run)
        end
        pathQueue[pathHead] = nil
        pathHead += 1
    end
    if pathHead > pathTail then pathHead, pathTail = 1, 0 end
end)

-- The active map's marker, looked up on each use: Studio's combined mode can switch maps between runs.
local function marker()
    return Role.marker() or error('No RogueliteZombieSpawn in the active map ' .. tostring(Role.activeMap()))
end
local spawnZombie

-- Spawn director: Brotato-style telegraphed groups spread around the players.
-- A red X marks each incoming enemy for TELEGRAPH_TIME; a player standing on a
-- group's marks pushes that group to a nearby open spot instead of cancelling it.
-- The marker's SpawnAreaCenter/SpawnAreaRadius bound the walkable arena floor.
local TELEGRAPH_TIME = 1
local GROUP_STAGGER = 0.2
local GROUP_RADIUS = 3.5
local GROUP_SPACING = 10
local MIN_PLAYER_DISTANCE = 22
local SPAWN_BAND = {28, 70}
local STAND_RADIUS = 5
local RELOCATE_BAND = {14, 30}
local RESPAWN_DELAY = 2
local MIN_MASS = 4 -- enemy bodies below this get a denser root (see spawnZombie)
local WARNING_COLOR = Color3.fromRGB(214, 58, 52)
local warnings = Instance.new("Folder")
warnings.Name = "RogueliteSpawnWarnings"
warnings.Parent = workspace
local queued, queuedSet, flushScheduled = {}, {}, false

local function arena()
    local m = marker()
    local center = m:GetAttribute('SpawnAreaCenter')
    if typeof(center) ~= 'Vector3' then center = m.Position end
    return center, m:GetAttribute('SpawnAreaRadius') or 60
end
local function livingRoots()
    local roots = {}
    for _, player in Players:GetPlayers() do
        local character = player.Character
        local root = character and character:FindFirstChild("HumanoidRootPart")
        local humanoid = character and character:FindFirstChildOfClass("Humanoid")
        if root and humanoid and humanoid.Health > 0 then table.insert(roots, root) end
    end
    return roots
end
local function flatDistance(a, b) return Vector2.new(a.X - b.X, a.Z - b.Z).Magnitude end
local function clearOfPlayers(point, minimum, roots)
    for _, root in roots do
        if flatDistance(point, root.Position) < minimum then return false end
    end
    return true
end
-- Rock/tree climb blockers have CanQuery off, so test their footprints directly. Their parts are
-- listed once per map and kept until the folder's contents or the active map (RunMap) change.
local blockerCache = {}
local function forgetBlockers() blockerCache.parts = nil end
combat:GetAttributeChangedSignal('RunMap'):Connect(forgetBlockers)
local function blockerParts()
    local blockers = Role.find(marker():GetAttribute('SpawnBlockerFolder') or 'MapOneNoClimb')
    if blockers ~= blockerCache.folder then
        for _, link in blockerCache.links or {} do link:Disconnect() end
        blockerCache.folder, blockerCache.parts, blockerCache.links = blockers, nil, nil
        if blockers then
            blockerCache.links = {blockers.DescendantAdded:Connect(forgetBlockers), blockers.DescendantRemoving:Connect(forgetBlockers)}
        end
    end
    if blockers and not blockerCache.parts then
        local parts = {}
        for _, part in blockers:GetDescendants() do
            if part:IsA("BasePart") then table.insert(parts, part) end
        end
        blockerCache.parts = parts
    end
    return blockerCache.parts
end
local function insideBlocker(point, parts)
    for _, part in parts or {} do
        local localPoint = part.CFrame:PointToObjectSpace(point)
        if math.abs(localPoint.X) < part.Size.X / 2 + 1.5 and math.abs(localPoint.Z) < part.Size.Z / 2 + 1.5 then return true end
    end
    return false
end
-- Everything a spawn check needs that can't change while one pick runs (it never yields):
-- gathered once per pick instead of once per attempt.
local function spawnContext()
    local m = marker()
    local center, radius = arena()
    local roots = livingRoots()
    local exclude = {folder, warnings, m, workspace:FindFirstChild("Zombie_R15_ProvidedTextures_Studio")}
    for _, root in roots do table.insert(exclude, root.Parent) end
    -- The arena's invisible walls and lid sit above the floor; the ground ray ignores them.
    local rayExclude = table.clone(exclude)
    table.insert(rayExclude, Role.find(m:GetAttribute('SpawnBoundaryModel') or 'MapOneBoundary'))
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = rayExclude
    local overlap = OverlapParams.new()
    overlap.FilterType = Enum.RaycastFilterType.Exclude
    overlap.FilterDescendantsInstances = exclude
    overlap.RespectCanCollide = true
    return {center = center, radius = radius, roots = roots, params = params, overlap = overlap, blockers = blockerParts()}
end
local function groundAt(point, context)
    local center = context.center
    local hit = workspace:Raycast(Vector3.new(point.X, center.Y + 200, point.Z), Vector3.new(0, -260, 0), context.params)
    -- Floor level only: never on cliffs, terraces, canopies or boulder tops.
    if not hit or hit.Normal.Y < 0.75 or math.abs(hit.Position.Y - center.Y) > 5 or insideBlocker(hit.Position, context.blockers) then return nil end
    if #workspace:GetPartBoundsInBox(CFrame.new(hit.Position + Vector3.new(0, 3.5, 0)), Vector3.new(3, 5, 3), context.overlap) > 0 then return nil end
    return hit.Position
end
-- Prefer a ring around a random living player so pressure comes from every side.
local function pickSpawnPoint(avoid, anchor, band, minimum)
    local context = spawnContext()
    local center, radius, roots = context.center, context.radius, context.roots
    for attempt = 1, 32 do
        local origin = anchor or (#roots > 0 and attempt <= 24 and roots[math.random(#roots)].Position)
        local candidate
        if origin then
            local angle = math.random() * math.pi * 2
            local distance = band[1] + math.random() * (band[2] - band[1])
            candidate = Vector3.new(origin.X + math.cos(angle) * distance, center.Y, origin.Z + math.sin(angle) * distance)
        else
            local angle = math.random() * math.pi * 2
            local distance = math.sqrt(math.random()) * radius
            candidate = center + Vector3.new(math.cos(angle) * distance, 0, math.sin(angle) * distance)
        end
        local spaced = flatDistance(candidate, center) <= radius and clearOfPlayers(candidate, minimum, roots)
        for _, other in avoid do
            if spaced and flatDistance(candidate, other) < GROUP_SPACING then spaced = false end
        end
        local ground = spaced and groundAt(candidate, context)
        if ground then return ground end
    end
    return nil
end
local function memberSpots(point, count)
    local spots = {}
    local context = spawnContext()
    for n = 1, count do
        local angle = (n / count + math.random() * 0.15) * math.pi * 2
        local offset = count > 1 and GROUP_RADIUS * (0.55 + math.random() * 0.45) or 0
        spots[n] = groundAt(point + Vector3.new(math.cos(angle) * offset, 0, math.sin(angle) * offset), context) or point
    end
    return spots
end
local function makeWarning(position)
    local mark = Instance.new("Model")
    mark.Name = "SpawnWarning"
    for _, yaw in {45, -45} do
        local bar = Instance.new("Part")
        bar.Anchored, bar.CanCollide, bar.CanQuery, bar.CanTouch, bar.CastShadow = true, false, false, false, false
        bar.Material = Enum.Material.Neon
        bar.Color = WARNING_COLOR
        bar.Transparency = 0.1
        bar.Size = Vector3.new(0.7, 0.12, 4.2)
        bar.CFrame = CFrame.new(position + Vector3.new(0, 0.08, 0)) * CFrame.Angles(0, math.rad(yaw), 0)
        bar.Parent = mark
        TweenService:Create(bar, TweenInfo.new(0.25, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true), {Transparency = 0.55}):Play()
    end
    mark.Parent = warnings
    return mark
end
local function releaseQueued(members, generation)
    for _, index in members do
        if queuedSet[index] == generation then queuedSet[index] = nil end
    end
end
local function telegraphBody(members, point, generation)
    if generation ~= waveGeneration then releaseQueued(members, generation) return end
    local spots = point and memberSpots(point, #members) or {}
    local marks = {}
    for n in members do if spots[n] then marks[n] = makeWarning(spots[n]) end end
    task.wait(TELEGRAPH_TIME)
    for _, mark in marks do mark:Destroy() end
    releaseQueued(members, generation)
    if generation ~= waveGeneration or combat:GetAttribute('ZombiesEnabled') ~= true or adminPaused() then return end
    local roots = livingRoots()
    local blocked = false
    for _, spot in spots do
        if not clearOfPlayers(spot, STAND_RADIUS, roots) then blocked = true end
    end
    if blocked then
        local moved = pickSpawnPoint({}, point, RELOCATE_BAND, RELOCATE_BAND[1]) or pickSpawnPoint({}, nil, SPAWN_BAND, MIN_PLAYER_DISTANCE)
        spots = moved and memberSpots(moved, #members) or {}
    end
    for n, index in members do spawnZombie(index, nil, spots[n]) end
end
-- The group's queue slots are always released, even if the body errors part-way (a missing
-- marker, say); otherwise those slots never refill until the next resetWave. After a normal
-- run the body has already released them and this release does nothing.
local function telegraphGroup(members, point, generation)
    local ok, err = pcall(telegraphBody, members, point, generation)
    releaseQueued(members, generation)
    if not ok then warn('Spawn telegraph failed: ' .. tostring(err)) end
end
-- A big refill picks PICKS_PER_FRAME groups a frame instead of all at once; each group's
-- telegraph still starts GROUP_STAGGER after the previous one, timed from the flush.
local PICKS_PER_FRAME = 4
local function flushQueue()
    flushScheduled = false
    local generation, batch, chosen, delay = waveGeneration, queued, {}, 0
    queued = {}
    local started, picks = os.clock(), 0
    local i = 1
    while i <= #batch do
        local size = math.min(#batch - i + 1, math.random(2, 4))
        local members = table.move(batch, i, i + size - 1, 1, {})
        i += size
        if picks >= PICKS_PER_FRAME then picks = 0; task.wait() end
        -- An error here would strand the rest of the batch in queuedSet; with no point the group
        -- still goes to telegraphGroup, which releases it (and so does a wave reset mid-flush).
        local point
        if generation == waveGeneration then
            picks += 1
            local picked
            picked, point = pcall(pickSpawnPoint, chosen, nil, SPAWN_BAND, MIN_PLAYER_DISTANCE)
            if not picked then warn('Spawn point failed: ' .. tostring(point)); point = nil end
            if point then table.insert(chosen, point) end
        end
        task.delay(math.max(0, started + delay - os.clock()), telegraphGroup, members, point, generation)
        delay += GROUP_STAGGER
    end
end
local function queueSpawn(index)
    if adminPaused() or queuedSet[index] or folder:FindFirstChild(string.format('Zombie_%02d', index)) then return end
    queuedSet[index] = waveGeneration
    table.insert(queued, index)
    if not flushScheduled then
        flushScheduled = true
        task.delay(0.3, flushQueue)
    end
end

-- admin: an extra enemy from the admin panel (AdminSpawn): named Admin_nn, outside the wave's
-- slots, never respawned. index is then its serial number.
spawnZombie = function(index,overrideId,spawnPosition,splitChild,admin)
if combat:GetAttribute('ZombiesEnabled') ~= true or (not admin and index>spawnCount()) then return end
local instanceName=string.format(admin and 'Admin_%02d' or 'Zombie_%02d',index)..(splitChild and '_Split'..splitChild or '')
if folder:FindFirstChild(instanceName) then return end
local thisWave = waveGeneration
local run=game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteRunState')
local wave=run and run:GetAttribute('Wave') or 1
local id=overrideId or EnemyCatalog.forSlot(index,wave,combat:GetAttribute('EnemyRoster'))
local config=EnemyCatalog.scaled(id,wave)
-- The map's place on the ladder and the run difficulty (both set at launch) scale health and
-- damage on top of wave growth (RunSetupRules.enemyScale): later maps' health starts some waves ahead.
local extraWaves,hpScale,damageScale=RunSetupRules.enemyScale(combat:GetAttribute('RunMap'),combat:GetAttribute('RunDifficulty'))
if extraWaves>0 then config.health=EnemyCatalog.scaled(id,wave+extraWaves).health end
config.health=math.max(1,math.ceil(config.health*hpScale));config.damage*=damageScale
local kind=config.legacy or id
local selected=templates:FindFirstChild(config.template)
if not selected then warn('Missing regular enemy template: '..config.template);return end
-- No marker in the active map: build nothing (resetWave warns once).
local m = Role.marker(); if not m then return end
local npc = selected:Clone()
npc.Name = instanceName
if splitChild then npc:ScaleTo(npc:GetScale()*config.childScale);config.health=math.max(1,math.ceil(config.health*.45));config.damage*=.6 end
npc:SetAttribute("SpawnIndex", index)
npc:SetAttribute('ZombieType',kind)
npc:SetAttribute('EnemyId',id)
npc:SetAttribute('EnemyBalanceStatus',config.balanceStatus)
npc:SetAttribute('SplitChild',splitChild~=nil)
if admin then npc:SetAttribute('AdminSpawn',true) end
npc:SetAttribute('ContactDamage',0) -- Timestamped attacks own damage; never double-hit through proximity.
npc:SetAttribute('AttackDamage',config.damage)
npc:SetAttribute('SlamDamage',config.damage)
npc:SetAttribute('SpawnWave',wave)
npc:SetAttribute('ContactRange',config.attackRange)
-- Body bump (CharacterService): pushing into a mob's body costs half its hit, so a swarm
-- can't be run through for free between swings. The range sits inside the mob's stop
-- distance, so standing and fighting at normal reach never triggers it.
npc:SetAttribute('BumpDamage',math.max(1,math.floor(config.damage*.5+.5)))
npc:SetAttribute('BumpRange',math.min(config.stopRange,config.radius+1.5)-.3)
npc.Parent = folder
local root = npc:WaitForChild("HumanoidRootPart")
local humanoid = npc:WaitForChild("Humanoid")
humanoid.MaxHealth = config.health
humanoid.Health = humanoid.MaxHealth
humanoid.BreakJointsOnDeath = false
humanoid.Died:Connect(function()
    -- Admin extras outlive a population change (resetWave keeps them), so they split in any wave.
    if config.behavior=='Splitter' and not splitChild and (admin or thisWave==waveGeneration) and combat:GetAttribute('ZombiesEnabled') then
        local position=root.Position
        for child=1,config.splitCount do spawnZombie(index,id,position+Vector3.new(child==1 and -1.5 or 1.5,0,0),child,admin) end
    end
    Death.finish(npc)
end)
-- Schedule replacements in this script's lifecycle, independently of the damage caller.
npc.Destroying:Connect(function()
    if splitChild or admin or not npc:GetAttribute('DeathPopped') then return end
    task.delay(RESPAWN_DELAY, function()
        if thisWave == waveGeneration and combat:GetAttribute('ZombiesEnabled') then queueSpawn(index) end
    end)
end)
local angle = (index - 1) * math.pi * 2 / math.max(1,spawnCount())
local position = spawnPosition or m.Position + Vector3.new(math.cos(angle) * 10, 0, math.sin(angle) * 10)
local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Exclude
groundParams.FilterDescendantsInstances = {folder, m, workspace:FindFirstChild("Zombie_R15_ProvidedTextures_Studio")}
local ground = workspace:Raycast(position + Vector3.new(0, 30, 0), Vector3.new(0, -100, 0), groundParams)
if ground then position = Vector3.new(position.X, ground.Position.Y + humanoid.HipHeight + root.Size.Y / 2 + 0.1, position.Z) end
local facing = nil
for _, root in livingRoots() do
    if not facing or flatDistance(position, root.Position) < flatDistance(position, facing) then facing = root.Position end
end
if facing and flatDistance(position, facing) > 0.1 then
    npc:PivotTo(CFrame.lookAt(position, Vector3.new(facing.X, position.Y, facing.Z)))
else
    npc:PivotTo(CFrame.new(position) * m.CFrame.Rotation)
end
for _, part in npc:GetDescendants() do
    if part:IsA("BasePart") then
        part.Anchored = false
        part.CollisionGroup = COLLISION_GROUP
    end
end
-- The Humanoid can't steer a very light body. The baby zombie (0.33 mass, every limb Massless)
-- slid ~38 degrees off its facing on average at ~60% of its WalkSpeed; from 2 mass up it runs
-- like the regular zombie. Lava slime split children are lighter still.
if root.AssemblyMass < MIN_MASS then
    local physical = root.CurrentPhysicalProperties
    local density = (root:GetMass() + MIN_MASS - root.AssemblyMass) / (root.Size.X * root.Size.Y * root.Size.Z)
    root.CustomPhysicalProperties = PhysicalProperties.new(math.min(density, 100), physical.Friction, physical.Elasticity, physical.FrictionWeight, physical.ElasticityWeight)
end
root:SetNetworkOwner(nil)
humanoid.WalkSpeed = config.speed
npc:SetAttribute('BaseMoveSpeed',config.speed)
humanoid.AutoRotate = true
humanoid:SetStateEnabled(Enum.HumanoidStateType.Climbing, false)
CollectionService:AddTag(npc, "RogueliteZombie")

local waypoints, waypointIndex = nil, 1
local computing, lastPath, generation = false, -math.huge, 0
local path, blockedAt = nil, -math.huge -- one reused Path; when sight was last blocked
-- Line-of-sight filter, reused: rebuilt only when the target body or the map marker changes.
local sight, sightTarget, sightMarker = RaycastParams.new(), nil, nil
sight.FilterType = Enum.RaycastFilterType.Exclude
local previousTarget = nil
local elapsed = 0
local stall = nil
local function nearestTarget()
    local best, distance = nil, math.huge
    for _, player in Players:GetPlayers() do
        local character = player.Character
        local targetRoot = character and character:FindFirstChild("HumanoidRootPart")
        local targetHumanoid = character and character:FindFirstChildOfClass("Humanoid")
        if targetRoot and targetHumanoid and targetHumanoid.Health > 0 then
            local offset=targetRoot.Position-root.Position
            local d = Vector2.new(offset.X,offset.Z).Magnitude
            if d < distance then best, distance = targetRoot, d end
        end
    end
    return best, distance
end

local frozen = false
local connection
connection = RunService.Heartbeat:Connect(function(dt)
    if not npc.Parent or humanoid.Health <= 0 then
        generation += 1
        npc:SetAttribute("Chasing", false)
        connection:Disconnect()
        return
    end
    -- Admin Freeze: no moving and no attacks; players' hits and damage still work. The first
    -- frozen frame cancels an attack in progress, so its hit can't land the moment Freeze ends.
    if combat:GetAttribute('AdminFreeze') == true or combat:GetAttribute('RunPaused') == true then -- plan L: a paused run freezes them too
        if not frozen then
            frozen = true
            EnemyAttacks.cancel(npc)
            Attacks.cancel(npc)
            npc:SetAttribute("Chasing", false)
            humanoid:Move(Vector3.zero)
            humanoid:MoveTo(root.Position)
        end
        stall = nil
        return
    end
    frozen = false
    -- Standing still to attack isn't a stall (see the hop below).
    if kind=='Mutant' then
        if Attacks.update(npc,previousTarget) then stall = nil return end
    elseif EnemyAttacks.update(npc,previousTarget,dt) then stall = nil return end
    elapsed += dt
    if elapsed < 0.1 then return end
    elapsed = 0
    local statusSlow=npc:GetAttribute('StatusSlowStrength') or 0
    local vacuumSlow=(npc:GetAttribute('VacuumSlowUntil') or 0)>workspace:GetServerTimeNow() and 35 or 0
    humanoid.WalkSpeed=config.speed*(1-math.max(statusSlow,vacuumSlow)/100)
    local target, distance = nearestTarget()
    if target ~= previousTarget then
        previousTarget = target
        generation += 1
        waypoints = nil
    end
    npc:SetAttribute("Chasing", target ~= nil)
    npc:SetAttribute("TargetUserId", target and Players:GetPlayerFromCharacter(target.Parent).UserId or 0)
    if not target then
        humanoid:Move(Vector3.zero)
        humanoid:MoveTo(root.Position)
        return
    end
    -- Gentle separation keeps the five bodies readable without pushing physics piles.
    local separation = neighborGrid:separation(npc, root.Position)
    if distance < config.stopRange and separation.Magnitude < 0.15 then
        humanoid:Move(Vector3.zero)
        humanoid:MoveTo(root.Position)
        return
    end
    -- Markers are CanQuery=false now; the marker entry (last, so nil is safe) is only for older places.
    local m = Role.marker()
    if target.Parent ~= sightTarget or m ~= sightMarker then
        sightTarget, sightMarker = target.Parent, m
        sight.FilterDescendantsInstances = {folder, sightTarget, m}
    end
    local obstruction = workspace:Raycast(root.Position, target.Position - root.Position, sight)
    if not obstruction then
        waypoints = nil
        local delta = target.Position - root.Position
        local flat = Vector3.new(delta.X, 0, delta.Z)
        local direction = (distance >= config.stopRange and flat.Magnitude > 0.01) and flat.Unit or Vector3.zero
        direction += separation * 1.8
        if direction.Magnitude > 0.05 then
            humanoid:MoveTo(root.Position + direction.Unit * math.min(8, math.max(distance - config.stopRange + 1, 1)))
        else
            humanoid:MoveTo(root.Position)
        end
        -- A step taller than the hips stops a walker dead (babies at the 1-stud spawn pad).
        -- The line of sight is clear, so no path gives a jump waypoint: hop when 0.3 s of
        -- chasing covered under 15% of the walk. Close in, arriving at the MoveTo point isn't a stall,
        -- and neither is being held back by the crowd's separation push.
        local chasing = direction.Magnitude > 0.05 and flat.Magnitude > 0.01 and direction.Unit:Dot(flat.Unit) > 0.8
        if chasing and distance >= config.stopRange + 1 and humanoid.WalkSpeed > 4 and config.behavior ~= 'Heavy' then
            if not stall then
                stall = {at = root.Position, since = os.clock()}
            elseif os.clock() - stall.since >= 0.3 then
                if flatDistance(root.Position, stall.at) < humanoid.WalkSpeed * 0.3 * 0.15 then humanoid.Jump = true end
                stall = nil
            end
        else
            stall = nil
        end
        return
    end
    stall = nil
    blockedAt = os.clock()
    if not computing and os.clock() - lastPath > 1 then
        computing = true
        local job = {}
        -- Checked when its turn comes: still alive and still out of sight (checked every 0.1 s).
        job.wanted = function()
            if npc.Parent and humanoid.Health > 0 and os.clock() - blockedAt <= 0.3 then return true end
            computing = false
            return false
        end
        -- From where the zombie and its current target are now, not where they were when it asked.
        job.run = function()
            local goal = previousTarget
            if not goal or not goal.Parent then computing = false return end
            lastPath = os.clock()
            local requestGeneration = generation
            local start, finish = root.Position, goal.Position
            path = path or PathfindingService:CreatePath({AgentRadius = config.radius, AgentHeight = config.height, AgentCanJump = config.behavior~='Heavy', WaypointSpacing = 4})
            local ok = pcall(function() path:ComputeAsync(start, finish) end)
            if requestGeneration == generation and npc.Parent and humanoid.Health > 0 then
                if ok and path.Status == Enum.PathStatus.Success then
                    waypoints, waypointIndex = path:GetWaypoints(), 2
                else
                    waypoints = nil
                end
            end
            computing = false
        end
        queuePath(job)
    end
    local point = waypoints and waypoints[waypointIndex]
    if point then
        if (Vector3.new(point.Position.X, root.Position.Y, point.Position.Z) - root.Position).Magnitude < 2 then
            waypointIndex += 1
            point = waypoints[waypointIndex]
        end
        if point then
            if point.Action == Enum.PathWaypointAction.Jump then humanoid.Jump = true end
            humanoid:MoveTo(point.Position)
        end
    else
        humanoid:Move(Vector3.zero) -- Do not keep pushing through an unreachable obstacle.
    end
end)
end

local function resetWave()
    waveGeneration += 1
    queued, queuedSet = {}, {}
    warnings:ClearAllChildren()
    for _,npc in folder:GetChildren() do
        -- Bosses and admin-panel extras outlive a population change; everything goes when enemies turn off.
        local keep = npc:GetAttribute('IsBoss') or npc:GetAttribute('AdminSpawn')
        if not keep or not combat:GetAttribute('ZombiesEnabled') then npc:Destroy() end
    end
    if combat:GetAttribute('ZombiesEnabled') then
        if not Role.marker() then
            warn('No RogueliteZombieSpawn in the active map ' .. tostring(Role.activeMap()) .. '; no enemies this wave')
            return
        end
        for index = 1, spawnCount() do queueSpawn(index) end
    end
end
combat:GetAttributeChangedSignal('ZombiesEnabled'):Connect(resetWave)
combat:GetAttributeChangedSignal('ZombieCount'):Connect(resetWave)
combat:GetAttributeChangedSignal('EnemyRoster'):Connect(resetWave)
resetWave()

-- Admin panel spawner (ADMIN_PANEL.md). Only AdminService calls it, after checking the developer.
-- ('Spawn', id, count, position): extra enemies (or bosses: AdminConfig.BossIds) on open floor 20-40 studs
-- around position. They fight normally, take no wave slot and never respawn. Returns how many
-- appeared. ('Clear'): removes every enemy, bosses included. ('Freeze', on): sets AdminFreeze.
local adminSerial = 0
local adminSpawn = ServerStorage:FindFirstChild('AdminSpawn') or Instance.new('BindableFunction')
adminSpawn.Name = 'AdminSpawn'
adminSpawn.OnInvoke = function(action, id, count, position)
    if action == 'Clear' then
        waveGeneration += 1
        queued, queuedSet = {}, {}
        warnings:ClearAllChildren()
        folder:ClearAllChildren()
        return true
    elseif action == 'Freeze' then
        combat:SetAttribute('AdminFreeze', id == true or nil)
        return true
    elseif action ~= 'Spawn' or typeof(position) ~= 'Vector3' or type(count) ~= 'number' then
        return 0
    end
    if combat:GetAttribute('ZombiesEnabled') ~= true or not Role.marker() then return 0 end
    local made = 0
    -- AdminConfig caps bosses at 5; checked here again.
    for _ = 1, math.clamp(math.floor(count), 0, table.find(BossIds, id) and 5 or 50) do
        local point = pickSpawnPoint({}, position, {20, 40}, 20)
        if point then
            if id == 'Hammer' then
                local at = point + Vector3.yAxis * (BossMotion.RootHeight + 0.1)
                local boss = Bosses.spawn(CFrame.lookAt(at, Vector3.new(position.X, at.Y, position.Z)), true)
                if boss then boss:SetAttribute('AdminSpawn', true); made += 1 end
            elseif table.find(BossIds, id) then
                local timing = require(combat:WaitForChild('MapBossDefs')).timing(id)
                local at = timing and point + Vector3.yAxis * (timing.rootHeight + 0.1)
                local boss = at and require(script.Parent:WaitForChild('MapBossService')).spawn(id, CFrame.lookAt(at, Vector3.new(position.X, at.Y, position.Z)), true)
                if boss then boss:SetAttribute('AdminSpawn', true); made += 1 end
            else
                adminSerial += 1
                spawnZombie(adminSerial, id, point, nil, true)
                if folder:FindFirstChild(string.format('Admin_%02d', adminSerial)) then made += 1 end
            end
        end
    end
    return made
end
adminSpawn.Parent = ServerStorage

-- Resume after an admin Pause: refill the wave's empty slots.
task.spawn(function()
    local run = game:GetService('ReplicatedStorage'):WaitForChild('RogueliteRunState')
    -- Plan L: unpausing the run refills the wave's empty slots the same way.
    combat:GetAttributeChangedSignal('RunPaused'):Connect(function()
        if adminPaused() or combat:GetAttribute('ZombiesEnabled') ~= true or not Role.marker() then return end
        for index = 1, spawnCount() do queueSpawn(index) end
    end)
    run:GetAttributeChangedSignal('AdminPaused'):Connect(function()
        if adminPaused() or combat:GetAttribute('ZombiesEnabled') ~= true or not Role.marker() then return end
        for index = 1, spawnCount() do queueSpawn(index) end
    end)
end)
