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
local waveGeneration = 0

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
-- Rock/tree climb blockers have CanQuery off, so test their footprints directly.
local function insideBlocker(point)
    local blockers = Role.find(marker():GetAttribute('SpawnBlockerFolder') or 'MapOneNoClimb')
    if not blockers then return false end
    for _, part in blockers:GetDescendants() do
        if part:IsA("BasePart") then
            local localPoint = part.CFrame:PointToObjectSpace(point)
            if math.abs(localPoint.X) < part.Size.X / 2 + 1.5 and math.abs(localPoint.Z) < part.Size.Z / 2 + 1.5 then return true end
        end
    end
    return false
end
local function groundAt(point)
    local center = arena()
    local exclude = {folder, warnings, marker(), workspace:FindFirstChild("Zombie_R15_ProvidedTextures_Studio")}
    for _, root in livingRoots() do table.insert(exclude, root.Parent) end
    -- The arena's invisible walls and lid sit above the floor; the ground ray ignores them.
    local rayExclude = table.clone(exclude)
    table.insert(rayExclude, Role.find(marker():GetAttribute('SpawnBoundaryModel') or 'MapOneBoundary'))
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = rayExclude
    local hit = workspace:Raycast(Vector3.new(point.X, center.Y + 200, point.Z), Vector3.new(0, -260, 0), params)
    -- Floor level only: never on cliffs, terraces, canopies or boulder tops.
    if not hit or hit.Normal.Y < 0.75 or math.abs(hit.Position.Y - center.Y) > 5 or insideBlocker(hit.Position) then return nil end
    local overlap = OverlapParams.new()
    overlap.FilterType = Enum.RaycastFilterType.Exclude
    overlap.FilterDescendantsInstances = exclude
    overlap.RespectCanCollide = true
    if #workspace:GetPartBoundsInBox(CFrame.new(hit.Position + Vector3.new(0, 3.5, 0)), Vector3.new(3, 5, 3), overlap) > 0 then return nil end
    return hit.Position
end
-- Prefer a ring around a random living player so pressure comes from every side.
local function pickSpawnPoint(avoid, anchor, band, minimum)
    local center, radius = arena()
    local roots = livingRoots()
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
        local ground = spaced and groundAt(candidate)
        if ground then return ground end
    end
    return nil
end
local function memberSpots(point, count)
    local spots = {}
    for n = 1, count do
        local angle = (n / count + math.random() * 0.15) * math.pi * 2
        local offset = count > 1 and GROUP_RADIUS * (0.55 + math.random() * 0.45) or 0
        spots[n] = groundAt(point + Vector3.new(math.cos(angle) * offset, 0, math.sin(angle) * offset)) or point
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
local function telegraphGroup(members, point, generation)
    if generation ~= waveGeneration then releaseQueued(members, generation) return end
    local spots = point and memberSpots(point, #members) or {}
    local marks = {}
    for n in members do if spots[n] then marks[n] = makeWarning(spots[n]) end end
    task.wait(TELEGRAPH_TIME)
    for _, mark in marks do mark:Destroy() end
    releaseQueued(members, generation)
    if generation ~= waveGeneration or combat:GetAttribute('ZombiesEnabled') ~= true then return end
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
local function flushQueue()
    flushScheduled = false
    local generation, batch, chosen, delay = waveGeneration, queued, {}, 0
    queued = {}
    local i = 1
    while i <= #batch do
        local size = math.min(#batch - i + 1, math.random(2, 4))
        local members = table.move(batch, i, i + size - 1, 1, {})
        i += size
        local point = pickSpawnPoint(chosen, nil, SPAWN_BAND, MIN_PLAYER_DISTANCE)
        if point then table.insert(chosen, point) end
        task.delay(delay, telegraphGroup, members, point, generation)
        delay += GROUP_STAGGER
    end
end
local function queueSpawn(index)
    if queuedSet[index] or folder:FindFirstChild(string.format('Zombie_%02d', index)) then return end
    queuedSet[index] = waveGeneration
    table.insert(queued, index)
    if not flushScheduled then
        flushScheduled = true
        task.delay(0.3, flushQueue)
    end
end

spawnZombie = function(index,overrideId,spawnPosition,splitChild)
if combat:GetAttribute('ZombiesEnabled') ~= true or index>spawnCount() then return end
local instanceName=string.format('Zombie_%02d',index)..(splitChild and '_Split'..splitChild or '')
if folder:FindFirstChild(instanceName) then return end
local thisWave = waveGeneration
local run=game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteRunState')
local wave=run and run:GetAttribute('Wave') or 1
local id=overrideId or EnemyCatalog.forSlot(index,wave,combat:GetAttribute('EnemyRoster'))
local config=EnemyCatalog.scaled(id,wave)
-- Run difficulty (set by the lobby at launch) scales health and damage on top of wave growth.
local difficulty=RunSetupRules.difficulty(combat:GetAttribute('RunDifficulty'))
config.health=math.max(1,math.ceil(config.health*difficulty.hp));config.damage*=difficulty.damage
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
npc:SetAttribute('ContactDamage',0) -- Timestamped attacks own damage; never double-hit through proximity.
npc:SetAttribute('AttackDamage',config.damage)
npc:SetAttribute('SlamDamage',config.damage)
npc:SetAttribute('SpawnWave',wave)
npc:SetAttribute('ContactRange',config.attackRange)
npc.Parent = folder
local root = npc:WaitForChild("HumanoidRootPart")
local humanoid = npc:WaitForChild("Humanoid")
humanoid.MaxHealth = config.health
humanoid.Health = humanoid.MaxHealth
humanoid.BreakJointsOnDeath = false
humanoid.Died:Connect(function()
    if config.behavior=='Splitter' and not splitChild and thisWave==waveGeneration and combat:GetAttribute('ZombiesEnabled') then
        local position=root.Position
        for child=1,config.splitCount do spawnZombie(index,id,position+Vector3.new(child==1 and -1.5 or 1.5,0,0),child) end
    end
    Death.finish(npc)
end)
-- Schedule replacements in this script's lifecycle, independently of the damage caller.
npc.Destroying:Connect(function()
    if splitChild or not npc:GetAttribute('DeathPopped') then return end
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
root:SetNetworkOwner(nil)
humanoid.WalkSpeed = config.speed
npc:SetAttribute('BaseMoveSpeed',config.speed)
humanoid.AutoRotate = true
humanoid:SetStateEnabled(Enum.HumanoidStateType.Climbing, false)
CollectionService:AddTag(npc, "RogueliteZombie")

local waypoints, waypointIndex = nil, 1
local computing, lastPath, generation = false, -math.huge, 0
local previousTarget = nil
local elapsed = 0
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

local connection
connection = RunService.Heartbeat:Connect(function(dt)
    if not npc.Parent or humanoid.Health <= 0 then
        generation += 1
        npc:SetAttribute("Chasing", false)
        connection:Disconnect()
        return
    end
    if kind=='Mutant' then
        if Attacks.update(npc,previousTarget) then return end
    elseif EnemyAttacks.update(npc,previousTarget,dt) then return end
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
    local separation = Vector3.zero
    for _, other in folder:GetChildren() do
        local otherRoot = other ~= npc and other:FindFirstChild("HumanoidRootPart")
        if otherRoot then
            local delta = root.Position - otherRoot.Position
            delta = Vector3.new(delta.X, 0, delta.Z)
            local spacing = delta.Magnitude
            if spacing > 0.01 and spacing < 4.5 then
                separation += delta.Unit * (1 - spacing / 4.5)
            end
        end
    end
    if distance < config.stopRange and separation.Magnitude < 0.15 then
        humanoid:Move(Vector3.zero)
        humanoid:MoveTo(root.Position)
        return
    end
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    -- Markers are CanQuery=false now; the marker entry (last, so nil is safe) is only for older places.
    params.FilterDescendantsInstances = {folder, target.Parent, Role.marker()}
    local obstruction = workspace:Raycast(root.Position, target.Position - root.Position, params)
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
        return
    end
    if not computing and os.clock() - lastPath > 1 then
        computing = true
        lastPath = os.clock()
        local requestGeneration = generation
        local start, finish = root.Position, target.Position
        task.spawn(function()
            local path = PathfindingService:CreatePath({AgentRadius = config.radius, AgentHeight = config.height, AgentCanJump = config.behavior~='Heavy', WaypointSpacing = 4})
            local ok = pcall(function() path:ComputeAsync(start, finish) end)
            if requestGeneration == generation and npc.Parent and humanoid.Health > 0 then
                if ok and path.Status == Enum.PathStatus.Success then
                    waypoints, waypointIndex = path:GetWaypoints(), 2
                else
                    waypoints = nil
                end
            end
            computing = false
        end)
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
        if not npc:GetAttribute('IsHammerBoss') or not combat:GetAttribute('ZombiesEnabled') then npc:Destroy() end
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
