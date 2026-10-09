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
-- ZombieCount is the wave's base size (ShopService.waveEnemyCount); the wave keeps
-- EnemyScheduler.population of it filled: twice the previous requested occupancy (2026-10-05),
-- and more for each player up. Up = a run member alive and not downed, so a teammate leaving lowers
-- it (slots past the new count stop refilling) and a revive or rejoin raises it (watched below).
-- The tutorial and the admin panel's Keep N alive keep their exact count.
local Population = require(script.Parent:WaitForChild("EnemyScheduler"))
local Timeline = require(script.Parent:WaitForChild('WaveTimeline'))
local timelineState, timelineOrders, plannedIds = nil, {}, {}
local timelineDispatchAt = 0
local function timelineMode()
    local run=combat.Parent:FindFirstChild('RogueliteRunState')
    return run and run:GetAttribute('Phase')=='Combat' and combat:GetAttribute('TutorialRun')~=true
        and combat:GetAttribute('WaveNoRespawn')~=true and combat:GetAttribute('TestZombieCountOverride')==nil
        and combat:GetAttribute('EventSpawnHold')~=true
end
local function spawnHeld()
    return adminPaused() or combat:GetAttribute('AdminFreeze')==true
        or (combat:GetAttribute('CinematicUntil') or 0)>workspace:GetServerTimeNow()
end
-- Endless retains its encounter handle; all live bosses now apply the smaller BossPressure cap.
local endlessBoss = nil
local liveBosses = {}
local function bossPressure()
    -- A round 10 event (EventSpawnHold, Round10Service) budgets its own arrivals and leader.
    if combat:GetAttribute('EventSpawnHold') == true then return false end
    if combat:GetAttribute('TutorialRun') == true or combat:GetAttribute('WaveNoRespawn') == true or combat:GetAttribute('TestZombieCountOverride') ~= nil then return false end
    for boss in liveBosses do
        local h = boss.Parent and boss:FindFirstChildOfClass('Humanoid')
        if h and h.Health > 0 and not boss:GetAttribute('DeathPopped') then return true end
    end
    return false
end
local function playersUp()
    local n = 0
    for _, player in Players:GetPlayers() do
        local character=player.Character
        local humanoid=character and character:FindFirstChildOfClass('Humanoid')
        local root=character and character:FindFirstChild('HumanoidRootPart')
        if Timeline.participating(player:GetAttribute('RunMember'),player:GetAttribute('RunDown'),player:GetAttribute('RunReturning'),humanoid and humanoid.Health,root~=nil,false) then n+=1 end
    end
    return n
end
local function spawnCount()
    local base = math.clamp(combat:GetAttribute('ZombieCount') or 5,0,100)
    if combat:GetAttribute('TutorialRun') == true or combat:GetAttribute('WaveNoRespawn') == true or combat:GetAttribute('TestZombieCountOverride') ~= nil then return base end
    if bossPressure() then return Population.bossPopulation(base, playersUp()) end
    if timelineMode() then return Timeline.MaxAlive end
    return Population.population(base, playersUp(), endlessBoss and endlessBoss.Parent and Population.Endless.bossSlots or 0)
end
local COLLISION_GROUP = "RogueliteZombies"
if not PhysicsService:IsCollisionGroupRegistered(COLLISION_GROUP) then
    PhysicsService:RegisterCollisionGroup(COLLISION_GROUP)
end
PhysicsService:CollisionGroupSetCollidable(COLLISION_GROUP, COLLISION_GROUP, false)

local templates = ServerStorage:WaitForChild("RogueliteNPCs")
local template = templates:WaitForChild("Zombie_NPC")
local folder = Instance.new("Folder")
folder.Name = "RogueliteEnemies"
folder.Parent = workspace

local function trimBossPopulation()
    if not bossPressure() then return end
    local count = spawnCount()
    local regular={}
    for _,npc in folder:GetChildren() do
        local h=npc:FindFirstChildOfClass('Humanoid')
        if h and h.Health>0 and not npc:GetAttribute('IsBoss') and not npc:GetAttribute('IsElite') and not npc:GetAttribute('AdminSpawn') and not npc:GetAttribute('DeathPopped') then table.insert(regular,npc) end
    end
    table.sort(regular,function(a,b) return (a:GetAttribute('SpawnBorn') or 0)<(b:GetAttribute('SpawnBorn') or 0) end)
    for i=1,math.max(0,#regular-count) do regular[i]:Destroy() end -- removal, never a kill/reward
end
folder.ChildAdded:Connect(function(npc)
    if npc:GetAttribute('IsBoss') or npc:GetAttribute('IsHammerBoss') or npc:GetAttribute('IsMapBoss') then
        liveBosses[npc] = true
        task.defer(trimBossPopulation)
    end
end)
folder.ChildRemoved:Connect(function(npc) liveBosses[npc] = nil end)

local SpatialGrid = require(script.Parent:WaitForChild("EnemySpatialGrid"))
local neighborGrid = SpatialGrid.new(folder, 4.5)
-- One lazy snapshot per frame (the scheduler below invalidates it before stepping anyone).
folder.ChildAdded:Connect(function() neighborGrid:invalidate() end)
folder.ChildRemoved:Connect(function() neighborGrid:invalidate() end)
local Scheduler = require(script.Parent:WaitForChild("EnemyScheduler"))
-- States wave enemies never use (launch audit P5). Each enabled state is one more transition the
-- Humanoid checks every physics step, for every enemy (Swimming looks for water under each one).
-- Running, Jumping, Freefall and Landed stay on: enemies hop when stuck and take path jump points.
local UNUSED_STATES = {
    Enum.HumanoidStateType.Climbing, Enum.HumanoidStateType.Swimming, Enum.HumanoidStateType.Seated,
    Enum.HumanoidStateType.FallingDown, Enum.HumanoidStateType.Ragdoll, Enum.HumanoidStateType.GettingUp,
    Enum.HumanoidStateType.PlatformStanding, Enum.HumanoidStateType.Flying, Enum.HumanoidStateType.StrafingNoPhysics,
}

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

-- Work every enemy's tick used to repeat (launch audit P9), done once per frame instead: the
-- players' bodies, the map marker and the Freeze/Pause flags. At 100 enemies that was ~1,000
-- player scans and marker lookups a second, plus 12,000 attribute reads for the two flags.
-- Health and positions are still read live, so a player who dies mid-frame is dropped at once.
-- The frame number comes from PreSimulation, which runs before any Heartbeat callback.
local frameNumber, frameShared = 0, nil
RunService.PreSimulation:Connect(function() frameNumber += 1 end)
local function shared()
    if frameShared and frameShared.frame == frameNumber then return frameShared end
    local targets = {}
    for _, player in Players:GetPlayers() do
        local character = player.Character
        local targetRoot = character and character:FindFirstChild("HumanoidRootPart")
        local targetHumanoid = character and character:FindFirstChildOfClass("Humanoid")
        if targetRoot and targetHumanoid then
            table.insert(targets, {root = targetRoot, humanoid = targetHumanoid, userId = player.UserId})
        end
    end
    frameShared = {
        frame = frameNumber,
        targets = targets,
        marker = Role.marker(),
        -- Admin Freeze, or plan L's paused run.
        -- A boss entrance (CinematicUntil) holds them too while the camera is on the boss.
        frozen = combat:GetAttribute('AdminFreeze') == true or combat:GetAttribute('RunPaused') == true
            or (combat:GetAttribute('CinematicUntil') or 0) > workspace:GetServerTimeNow(),
    }
    return frameShared
end

-- Every wave enemy, stepped by one Heartbeat in spawn order (EnemyScheduler, launch audit P5):
-- each record is {step, elapsed, interval}, added by spawnZombie and dropped once done.
local mobs = {}
-- Server time spent stepping them (chase and attacks), for tools/MobPerfProbe.luau: EnemyMs is
-- the average per server frame over the last second, EnemyPeakMs the worst frame in it,
-- EnemyCount the enemies stepped. Attributes on this script: server-only, nothing replicates.
local meter = {time = 0, peak = 0, frames = 0, since = os.clock()}
local function measure(spent, count)
    meter.time += spent
    meter.frames += 1
    if spent > meter.peak then meter.peak = spent end
    local now = os.clock()
    if now - meter.since >= 1 then
        script:SetAttribute('EnemyMs', math.floor(meter.time * 1e6 / meter.frames + 0.5) / 1000)
        script:SetAttribute('EnemyPeakMs', math.floor(meter.peak * 1e6 + 0.5) / 1000)
        script:SetAttribute('EnemyCount', count)
        meter.time, meter.peak, meter.frames, meter.since = 0, 0, 0, now
    end
end
local function stepMob(record, dt, frame) record.step(dt, frame) end
local function stepFailed(record, message)
    -- Reported once per enemy; the others keep going and it is still stepped every frame.
    if record.warned then return end
    record.warned = true
    warn('Enemy step failed: ' .. tostring(message))
end
RunService.Heartbeat:Connect(function(dt)
    local n = #mobs
    if n == 0 then measure(0, 0) return end
    local started = os.clock()
    neighborGrid:invalidate()
    Scheduler.run(mobs, n, stepMob, stepFailed, dt, shared())
    Scheduler.compact(mobs)
    measure(os.clock() - started, n)
end)
local spawnZombie
-- One synchronous death listener survives immediate corpse removal. Weak keys and clearing
-- before dispatch prevent lifetime listener growth and duplicate split children.
local splitterDeaths=setmetatable({},{__mode='k'})
Death.onDeath=function(npc,position)
    local split=splitterDeaths[npc]
    if split then splitterDeaths[npc]=nil;split(position) end
end

-- Spawn director: Brotato-style telegraphed groups spread around the players.
-- A red X marks each incoming enemy for TELEGRAPH_TIME; a player standing on a
-- group's marks pushes that group to a nearby open spot instead of cancelling it.
-- The marker's SpawnAreaCenter/SpawnAreaRadius bound the walkable arena floor.
local TELEGRAPH_TIME = 1
local GROUP_STAGGER = 0.22
local GROUP_RADIUS = 3.5
local GROUP_SPACING = 10
local MIN_PLAYER_DISTANCE = 22
local SPAWN_BAND = {28, 52} -- keep new swarms close enough to join the fight promptly
local STAND_RADIUS = 5
local RESPAWN_DELAY = .15
-- Small packets arrive continuously from different sectors. One shared director serializes
-- starts across all refill batches, so simultaneous kills cannot restart a burst at time zero.
local GROUP_SIZE = {2, 4}
local SWARM_ARC = math.rad(15)
local SWARM_GATHER, SWARM_MIN = .35, 3
local pendingGroups, recentCenters = {}, {}
local directorRunning = false
local queueSpawn
local MIN_MASS = 4 -- enemy bodies below this get a denser root (see spawnZombie)
local WARNING_COLOR = Color3.fromRGB(214, 58, 52)
local warnings = Instance.new("Folder")
warnings.Name = "RogueliteSpawnWarnings"
warnings.Parent = workspace
local queued, queuedSet = {}, {}
local respawnReadyAt = {}
local function populationSnapshot()
    local total,regular,entries=0,0,{}
    for _,npc in folder:GetChildren() do
        local h=npc:FindFirstChildOfClass('Humanoid')
        if h and h.Health>0 and not npc:GetAttribute('DeathPopped') then
            total+=1
            local protected=npc:GetAttribute('IsBoss') or npc:GetAttribute('IsElite') or npc:GetAttribute('AdminSpawn')
            if not protected then regular+=1 end
            table.insert(entries,{npc=npc,protected=protected,born=npc:GetAttribute('SpawnBorn') or 0,index=npc:GetAttribute('SpawnIndex') or 0})
        end
    end
    return total,regular,entries
end
local function makeArrivalRoom(pending)
    if pending>=math.min(Timeline.MaxAlive,spawnCount()) then return false end
    local total,regular,entries=populationSnapshot()
    while not Timeline.capacity(total,regular,pending,spawnCount()) do
        local retire=Timeline.retireCandidate(entries)
        if not retire then return false end -- protected boss/elite/admin rigs are never removed
        retire.npc:Destroy();retire.protected=true;total-=1;regular-=1
    end
    return true
end

local function arena()
    local m = marker()
    local center = m:GetAttribute('SpawnAreaCenter')
    if typeof(center) ~= 'Vector3' then center = m.Position end
    return center, m:GetAttribute('SpawnAreaRadius') or 60
end
local function livingRoots()
    local roots = {}
    local run = combat.Parent:FindFirstChild('RogueliteRunState')
    local practice = not run or run:GetAttribute('Phase')=='Practice'
    for _, player in Players:GetPlayers() do
        local character = player.Character
        local root = character and character:FindFirstChild("HumanoidRootPart")
        local humanoid = character and character:FindFirstChildOfClass("Humanoid")
        if Timeline.participating(player:GetAttribute('RunMember'),player:GetAttribute('RunDown'),player:GetAttribute('RunReturning'),humanoid and humanoid.Health,root~=nil,practice) then table.insert(roots,root) end
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
    if flatDistance(point, center) > context.radius then return nil end
    local hit = workspace:Raycast(Vector3.new(point.X, center.Y + 200, point.Z), Vector3.new(0, -260, 0), context.params)
    -- Floor level only: never on cliffs, terraces, canopies or boulder tops.
    if not hit or hit.Normal.Y < 0.75 or math.abs(hit.Position.Y - center.Y) > 5 or insideBlocker(hit.Position, context.blockers) then return nil end
    if #workspace:GetPartBoundsInBox(CFrame.new(hit.Position + Vector3.new(0, 3.5, 0)), Vector3.new(3, 5, 3), context.overlap) > 0 then return nil end
    return hit.Position
end
-- Prefer a ring around a random living player so pressure comes from every side. heading (a swarm,
-- optional): {origin, angle} tries that player's side first (within SWARM_ARC), then anywhere.
local function pickSpawnPoint(avoid, anchor, band, minimum, heading)
    local context = spawnContext()
    local center, radius, roots = context.center, context.radius, context.roots
    for attempt = 1, 32 do
        local swarm = heading and attempt <= 16
        local origin = swarm and heading.origin or anchor or (#roots > 0 and attempt <= 24 and roots[math.random(#roots)].Position)
        local candidate
        if origin then
            local angle = swarm and heading.angle + (math.random() * 2 - 1) * SWARM_ARC or math.random() * math.pi * 2
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
        -- Groups over 4 get a wider ring (6 -> x1.22), so their bodies don't spawn inside each other.
        local offset = count > 1 and GROUP_RADIUS * math.max(1, math.sqrt(count / 4)) * (0.55 + math.random() * 0.45) or 0
        local candidate = point + Vector3.new(math.cos(angle) * offset, 0, math.sin(angle) * offset)
        spots[n] = clearOfPlayers(candidate, MIN_PLAYER_DISTANCE, context.roots) and groundAt(candidate, context) or point
    end
    return spots
end
-- Static here: each client pulses the bars (EnemyVisuals), 0.1 to 0.55 transparency and back every
-- 0.25 s. Server tweens replicated Transparency every frame, ~20 bars at each wave start.
local function makeWarning(position)
    local mark = Instance.new("Model")
    mark.Name = "SpawnWarning"
    for _, yaw in {45, -45} do
        local bar = Instance.new("Part")
        bar.Name = "WarningBar"
        bar.Anchored, bar.CanCollide, bar.CanQuery, bar.CanTouch, bar.CastShadow = true, false, false, false, false
        bar.Material = Enum.Material.Neon
        bar.Color = WARNING_COLOR
        bar.Transparency = 0.1
        bar.Size = Vector3.new(0.7, 0.12, 4.2)
        bar.CFrame = CFrame.new(position + Vector3.new(0, 0.08, 0)) * CFrame.Angles(0, math.rad(yaw), 0)
        bar.Parent = mark
    end
    mark.Parent = warnings
    return mark
end
local function releaseQueued(members, generation)
    for _, index in members do
        if queuedSet[index] == generation then queuedSet[index] = nil end
    end
end
local function retryGroup(members, generation)
    releaseQueued(members, generation)
    task.delay(.35, function()
        if generation ~= waveGeneration or combat:GetAttribute('ZombiesEnabled') ~= true then return end
        -- Fixed-count tutorial waves have no periodic missing-slot repair. Preserve their
        -- interrupted warning across a long pause instead of dropping it in queueSpawn.
        if adminPaused() then retryGroup(members, generation) return end
        for _, index in members do queueSpawn(index, true) end
    end)
end
local heading = math.random() * math.pi * 2
local swarmPlayer = 0
local function telegraphBody(members, generation, tutorial)
    if generation ~= waveGeneration then return end
    if spawnHeld() or combat:GetAttribute('ZombiesEnabled') ~= true then retryGroup(members, generation) return end
    -- Resolve the current player location here, never while waiting in the arrival queue.
    local roots = livingRoots()
    if #roots == 0 then retryGroup(members, generation) return end
    swarmPlayer = Timeline.nextRoot(swarmPlayer,#roots)
    heading = (heading + math.pi * (3 - math.sqrt(5))) % (math.pi * 2)
    local direction = not tutorial and {origin = roots[swarmPlayer].Position, angle = heading} or nil
    local avoid, now = {}, os.clock()
    for i = #recentCenters, 1, -1 do
        local entry = recentCenters[i]
        if entry.generation ~= generation or now - entry.time > 1.5 then
            table.remove(recentCenters, i)
        else
            table.insert(avoid, entry.point)
        end
    end
    local point = pickSpawnPoint(avoid, timelineMode() and roots[swarmPlayer].Position or nil, tutorial and {28, 70} or SPAWN_BAND, MIN_PLAYER_DISTANCE, direction)
    if not point then retryGroup(members, generation) return end
    table.insert(recentCenters, {point = point, time = now, generation = generation})
    local spots
    if timelineMode() then
        -- Each arrival has its own spaced location around the players, not a shared tight blob.
        spots={point};table.insert(avoid,point)
        for n=2,#members do
            swarmPlayer=Timeline.nextRoot(swarmPlayer,#roots)
            -- Every individual mark takes a turn around a living run member, including the
            -- second/third/fourth member of a compact warning group.
            local spot=pickSpawnPoint(avoid,roots[swarmPlayer].Position,SPAWN_BAND,MIN_PLAYER_DISTANCE,nil)
            if not spot then retryGroup(members,generation) return end
            spots[n]=spot;table.insert(avoid,spot)
            table.insert(recentCenters,{point=spot,time=now,generation=generation})
        end
    else spots=memberSpots(point,#members) end
    local marks = {}
    for n in members do marks[n] = makeWarning(spots[n]) end
    local warned=0
    while warned<TELEGRAPH_TIME and generation==waveGeneration do
        local dt=task.wait(.05)
        warned=Timeline.advanceWarning(warned,dt,spawnHeld())
    end
    for _, mark in marks do mark:Destroy() end
    if generation ~= waveGeneration then return end
    if combat:GetAttribute('ZombiesEnabled') ~= true or spawnHeld() then retryGroup(members, generation) return end
    roots = livingRoots()
    -- A player entering any mark restarts this group's full warning at fresh safe locations.
    if not Timeline.safeSpots(spots,roots,STAND_RADIUS,function(spot,root) return flatDistance(spot,root.Position) end) then retryGroup(members,generation) return end
    releaseQueued(members, generation)
    for n,index in members do
        if timelineMode() and not makeArrivalRoom(0) then retryGroup({index},generation)
        else spawnZombie(index,plannedIds[index],spots[n]);plannedIds[index]=nil end
    end
end
local function telegraphGroup(members, generation, tutorial)
    local ok, err = pcall(telegraphBody, members, generation, tutorial)
    if not ok then
        warn('Spawn telegraph failed: ' .. tostring(err))
        retryGroup(members, generation)
    end
end
local function drainGroups()
    if directorRunning then return end
    directorRunning = true
    task.spawn(function()
        while #pendingGroups > 0 do
            local group = table.remove(pendingGroups, 1)
            if group.generation == waveGeneration then
                local count, eligible = spawnCount(), {}
                for _, index in group.members do
                    if timelineMode() or index <= count then table.insert(eligible, index) else releaseQueued({index}, group.generation) end
                end
                group.members = eligible
                if #eligible == 0 then continue end
                task.spawn(telegraphGroup, group.members, group.generation, group.tutorial)
                -- Relative wait (not overdue task.delay reservations): a frame hitch never dumps
                -- every overdue group at once. Concurrent flushes append to this same stream.
                local spacing=group.tutorial and .2 or bossPressure() and Population.BossPressure.groupInterval or GROUP_STAGGER
                task.wait(timelineMode() and Timeline.groupInterval(spacing,playersUp()) or spacing)
            end
        end
        directorRunning = false
    end)
end
local function flushQueue()
    local generation, batch = waveGeneration, queued
    queued = {}
    local tutorial = combat:GetAttribute('TutorialRun') == true or combat:GetAttribute('WaveNoRespawn') == true
    local i = 1
    while i <= #batch do
        local size = math.min(#batch - i + 1, math.random(GROUP_SIZE[1], GROUP_SIZE[2]))
        local members = table.move(batch, i, i + size - 1, 1, {})
        i += size
        table.insert(pendingGroups, {members = members, generation = generation, tutorial = tutorial})
    end
    drainGroups()
end
-- One flush timer at a time; a sooner flush replaces a later one (a swarm that filled up early goes now).
local flushAt, flushToken = nil, 0
local function scheduleFlush(delay)
    local at = os.clock() + delay
    if flushAt and flushAt <= at then return end
    flushAt, flushToken = at, flushToken + 1
    local token = flushToken
    task.delay(delay, function()
        if token ~= flushToken then return end
        flushAt = nil
        flushQueue()
    end)
end
-- respawn: a killed enemy's slot, which waits for company (SWARM_GATHER, SWARM_MIN); a wave's first
-- fill and refills go at once. Slots past the wave's count (fewer players up) stay empty.
queueSpawn = function(index, respawn)
    if combat:GetAttribute('EventSpawnHold') == true then return end -- the event director spawns (Round10Spawn)
    if adminPaused() or queuedSet[index] or (not timelineMode() and index > spawnCount()) or folder:FindFirstChild(string.format('Zombie_%02d', index)) then return end
    if (respawnReadyAt[index] or 0) > os.clock() then return end
    queuedSet[index] = waveGeneration
    table.insert(queued, index)
    local tutorial = combat:GetAttribute('TutorialRun') == true or combat:GetAttribute('WaveNoRespawn') == true
    scheduleFlush(tutorial and 0.3 or respawn and #queued < SWARM_MIN and SWARM_GATHER or 0.12)
end

-- Endless: the map's toughest type (Population.toughest), for a growing share of wave slots.
-- Pine Valley has no roster (its zombie mix): its tank zombie.
local function toughestId()
    local ids, roster = {}, combat:GetAttribute('EnemyRoster')
    if type(roster) == 'string' then
        for id in roster:gmatch('[^,%s]+') do if EnemyCatalog.ById[id] then table.insert(ids, id) end end
    end
    return Population.toughest(ids, EnemyCatalog.ById) or EnemyCatalog.ByLegacy.Mutant
end
-- admin: an extra enemy from the admin panel (AdminSpawn): named Admin_nn, outside the wave's
-- slots, never respawned. index is then its serial number.
spawnZombie = function(index,overrideId,spawnPosition,splitChild,admin)
if combat:GetAttribute('ZombiesEnabled') ~= true or (not admin and not timelineMode() and index>spawnCount()) then return end
-- Bosses/admin rigs also occupy the global ceiling; split children may not bypass it.
local totalAlive=populationSnapshot()
if totalAlive>=Timeline.MaxAlive then return end
-- admin: true (an admin-panel extra) or a table (a round 10 event arrival, Round10Spawn): Event_nnn.
local event=type(admin)=='table' and admin or nil
local instanceName=string.format(event and 'Event_%03d' or admin and 'Admin_%02d' or 'Zombie_%02d',index)..(splitChild and '_Split'..splitChild or '')
if folder:FindFirstChild(instanceName) then return end
local thisWave = waveGeneration
local run=game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteRunState')
local wave=run and run:GetAttribute('Wave') or 1
local id=overrideId or EnemyCatalog.forSlot(index,wave,combat:GetAttribute('EnemyRoster'))
-- Endless (waves past 20, never the tutorial): stronger, a little faster, more of the toughest type.
-- All 1 (no change) up to wave 20. Example, wave 30: x3.11 health, x1.6 damage, +10% speed, 20% tough.
local hard=Population.endless(combat:GetAttribute('TutorialRun')~=true and wave or 0)
if not overrideId and Population.toughSlot(index,hard.tough) then id=toughestId() end
local config=EnemyCatalog.scaled(id,wave)
-- The map's place on the ladder and the run difficulty (both set at launch) scale health and
-- damage on top of wave growth (RunSetupRules.enemyScale): later maps' health starts some waves ahead.
local extraWaves,hpScale,damageScale=RunSetupRules.enemyScale(combat:GetAttribute('RunMap'),combat:GetAttribute('RunDifficulty'))
if extraWaves>0 then config.health=EnemyCatalog.scaled(id,wave+extraWaves).health end
config.health=math.max(1,math.ceil(config.health*hpScale*hard.health));config.damage*=damageScale*hard.damage
config.speed*=RunSetupRules.enemyMoveScale(combat:GetAttribute('RunDifficulty'))
config.speed=Population.endlessSpeed(config.speed,hard)
local kind=config.legacy or id
local selected=templates:FindFirstChild(config.template)
if not selected then warn('Missing regular enemy template: '..config.template);return end
-- No marker in the active map: build nothing (resetWave warns once).
local m = Role.marker(); if not m then return end
local npc = selected:Clone()
npc.Name = instanceName
if splitChild then npc:ScaleTo(npc:GetScale()*config.childScale);config.health=math.max(1,math.ceil(config.health*.45));config.damage*=.6 end
npc:SetAttribute("SpawnIndex", index)
npc:SetAttribute('SpawnBorn',workspace:GetServerTimeNow())
npc:SetAttribute('SpawnTimeline',timelineMode()==true and not admin)
npc:SetAttribute('ZombieType',kind)
npc:SetAttribute('EnemyId',id)
npc:SetAttribute('EnemyBalanceStatus',config.balanceStatus)
npc:SetAttribute('CrowdRadius',math.clamp(config.radius or 1.5,1.2,3.5)*(splitChild and config.childScale or 1))
npc:SetAttribute('SplitChild',splitChild~=nil)
if event then
    npc:SetAttribute('EventSpawn',true);npc:SetAttribute('EventGen',event.gen)
    for key,value in event.attrs or {} do npc:SetAttribute(key,value) end
elseif admin then npc:SetAttribute('AdminSpawn',true) end
-- Bloaters (behavior Exploder) arm and burst through ExploderService.
if config.behavior=='Exploder' then npc:SetAttribute('Exploder',true) end
npc:SetAttribute('ContactDamage',0) -- Timestamped attacks own damage; never double-hit through proximity.
npc:SetAttribute('AttackDamage',config.damage)
npc:SetAttribute('SlamDamage',config.damage)
npc:SetAttribute('SpawnWave',wave)
npc:SetAttribute('ContactRange',config.attackRange)
-- Body bump (CharacterService): pushing into a mob's body costs half its hit, so a swarm
-- can't be run through for free between swings. The range sits inside the mob's stop
-- distance, so standing and fighting at normal reach never triggers it. It's the body as it
-- is (2026-10-03): its narrower ground side (a humanoid's depth) halved, plus 0.8 for the
-- player's half-body and a touch. The old radius + 1.5 bumped from 1.5 studs in front of a
-- skeleton and 3.6 off an ogre ("hit in stupid angles or ranges").
npc:SetAttribute('BumpDamage',math.max(1,math.floor(config.damage*.5+.5)))
local body=npc:GetExtentsSize()
npc:SetAttribute('BumpRange',math.min(config.stopRange-.3,math.min(body.X,body.Z)/2+.8))
npc.Parent = folder
local root = npc:WaitForChild("HumanoidRootPart")
local humanoid = npc:WaitForChild("Humanoid")
humanoid.MaxHealth = config.health
humanoid.Health = humanoid.MaxHealth
humanoid.BreakJointsOnDeath = false
if config.behavior=='Splitter' and not splitChild then splitterDeaths[npc]=function(position)
    local currentRun=combat.Parent:FindFirstChild('RogueliteRunState')
    local sameWave=npc:GetAttribute('SpawnTimeline') and currentRun and currentRun:GetAttribute('Wave')==wave or thisWave==waveGeneration
    if (admin or sameWave) and combat:GetAttribute('ZombiesEnabled') then
        for child=1,config.splitCount do spawnZombie(index,id,position+Vector3.new(child==1 and -1.5 or 1.5,0,0),child,admin) end
    end
end end
humanoid.Died:Connect(function() Death.finish(npc) end)
-- Schedule replacements in this script's lifecycle, independently of the damage caller.
npc.Destroying:Connect(function()
    splitterDeaths[npc]=nil
    -- WaveNoRespawn (the tutorial): a wave is a fixed number of enemies that ends when they're dead.
    if splitChild or admin or npc:GetAttribute('SpawnTimeline') or not npc:GetAttribute('DeathPopped') or combat:GetAttribute('WaveNoRespawn') == true then return end
    local delay = bossPressure() and Population.BossPressure.respawnDelay or RESPAWN_DELAY
    respawnReadyAt[index] = os.clock() + delay
    task.delay(delay, function()
        if thisWave == waveGeneration and combat:GetAttribute('ZombiesEnabled') then queueSpawn(index, true) end
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
        -- No script listens for an enemy's touches (melee and shots use spatial queries, which
        -- CanQuery keeps working). Every template but the regular zombie already had this off.
        part.CanTouch = false
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
for _, state in UNUSED_STATES do humanoid:SetStateEnabled(state, false) end
CollectionService:AddTag(npc, "RogueliteZombie")

local waypoints, waypointIndex = nil, 1
local computing, lastPath, generation = false, -math.huge, 0
local path, blockedAt = nil, -math.huge -- one reused Path; when sight was last blocked
-- Line-of-sight filter, reused: rebuilt only when the target body or the map marker changes.
local sight, sightTarget, sightMarker = RaycastParams.new(), nil, nil
sight.FilterType = Enum.RaycastFilterType.Exclude
local previousTarget = nil
local stall = nil
local attacks = kind == 'Mutant' and Attacks or EnemyAttacks -- the Mutant slams (ZombieAttacks)
-- The nearest living player from this frame's list (ties to the earlier player, as before).
local function nearestTarget(targets)
    local best, distance = nil, math.huge
    for _, t in targets do
        if t.humanoid.Health > 0 then
            local offset=t.root.Position-root.Position
            local d = Vector2.new(offset.X,offset.Z).Magnitude
            if d < distance then best, distance = t, d end
        end
    end
    return best, distance
end

local frozen = false
-- Stepped every frame by the scheduler (was this enemy's own Heartbeat connection). Its first
-- think comes 0.1 s after spawn, up to 5 frames later to spread the crowd (EnemyScheduler).
local record = {elapsed = Scheduler.startElapsed(mobs), interval = Scheduler.THINK}
record.step = function(dt, frame)
    if record.done then return end
    if not npc.Parent or humanoid.Health <= 0 then
        generation += 1
        npc:SetAttribute("Chasing", false)
        record.done = true
        return
    end
    -- Admin Freeze: no moving and no attacks; players' hits and damage still work. The first
    -- frozen frame cancels an attack in progress, so its hit can't land the moment Freeze ends.
    if frame.frozen then -- plan L: a paused run freezes them too
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
    -- Round 10: an event move (Round10Service: the DJ crab's rushers) drives this body itself.
    if npc:GetAttribute('EventControlled') then stall = nil return end
    -- Standing still to attack isn't a stall (see the hop below). An attack in progress updates
    -- every frame, so its wind-up, hit and recovery keep their exact timing; the check for a new
    -- one waits for the 0.1 s think (100 enemies: 1,000 checks a second instead of 6,000).
    if attacks.busy(npc) and attacks.update(npc,previousTarget,dt) then stall = nil return end
    if not Scheduler.due(record, dt) then return end
    -- Every 0.1 s, unless this think finds the target far off with a clear line (below).
    record.interval = Scheduler.THINK
    if not attacks.busy(npc) and attacks.update(npc,previousTarget,dt) then stall = nil return end
    local statusSlow=npc:GetAttribute('StatusSlowStrength') or 0
    local vacuumSlow=(npc:GetAttribute('VacuumSlowUntil') or 0)>workspace:GetServerTimeNow() and 35 or 0
    -- SpeedBuff: a round 10 pack buff (the Blood Moon Alpha's howl), set and cleared by Round10Service.
    humanoid.WalkSpeed=config.speed*(1-math.max(statusSlow,vacuumSlow)/100)*(npc:GetAttribute('SpeedBuff') or 1)
    local nearest, distance = nearestTarget(frame.targets)
    local target = nearest and nearest.root
    if target ~= previousTarget then
        previousTarget = target
        generation += 1
        waypoints = nil
    end
    npc:SetAttribute("Chasing", target ~= nil)
    npc:SetAttribute("TargetUserId", nearest and nearest.userId or 0)
    if not target then
        humanoid:Move(Vector3.zero)
        humanoid:MoveTo(root.Position)
        return
    end
    -- Markers are CanQuery=false now; the marker entry (last, so nil is safe) is only for older places.
    local m = frame.marker
    if target.Parent ~= sightTarget or m ~= sightMarker then
        sightTarget, sightMarker = target.Parent, m
        sight.FilterDescendantsInstances = {folder, sightTarget, m}
    end
    local obstruction = workspace:Raycast(root.Position, target.Position - root.Position, sight)
    if not obstruction then
        waypoints = nil
        -- More than 90 studs from every player with a clear line: think every 0.3 s.
        record.interval = Scheduler.interval(distance)
        local delta = target.Position - root.Position
        local flat = Vector3.new(delta.X, 0, delta.Z)
        local direction = neighborGrid:steer(npc, root.Position, target.Position, config.stopRange)
        humanoid:Move(direction)
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
            humanoid:Move(neighborGrid:steer(npc, root.Position, point.Position, .5))
        end
    else
        humanoid:Move(Vector3.zero) -- Do not keep pushing through an unreachable obstacle.
    end
end
table.insert(mobs, record)
end

local function resetWave()
    waveGeneration += 1
    queued, queuedSet = {}, {}
    respawnReadyAt = {}
    pendingGroups, recentCenters = {}, {}
    timelineState,timelineOrders,plannedIds=nil,{},{}
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
        if not timelineMode() then for index = 1, spawnCount() do queueSpawn(index) end end
    end
end
combat:GetAttributeChangedSignal('ZombiesEnabled'):Connect(resetWave)
combat:GetAttributeChangedSignal('ZombieCount'):Connect(resetWave)
combat:GetAttributeChangedSignal('EnemyRoster'):Connect(resetWave)
resetWave()

-- Round 10 events (Round10Service, ROUND_10_MASTER_SPEC.md). While EventSpawnHold is on the event
-- director owns the wave: ordinary arrivals stop (timelineMode, queueSpawn, bossPressure above) and
-- whatever the wave had queued or had just landed goes (removal, never a kill or reward).
combat:GetAttributeChangedSignal('EventSpawnHold'):Connect(function()
    if combat:GetAttribute('EventSpawnHold') ~= true then return end
    waveGeneration += 1
    queued, queuedSet = {}, {}
    pendingGroups, recentCenters = {}, {}
    timelineState, timelineOrders, plannedIds = nil, {}, {}
    warnings:ClearAllChildren()
    for _, npc in folder:GetChildren() do
        if not npc:GetAttribute('IsBoss') and not npc:GetAttribute('AdminSpawn') and not npc:GetAttribute('EventSpawn') and not npc:GetAttribute('EventObjective') then npc:Destroy() end
    end
end)
-- The director's spawner (unsandboxed callers only):
--   ('Arena')                 -> the arena centre and radius
--   ('Point', {anchor, band, minimum, avoid}) -> an open floor point (pickSpawnPoint), or nil
--   ('Ground', position)      -> that spot's open floor point, or nil
--   ('Spawn', {id, position, gen, telegraph, source, attrs}) -> the enemy, or nil. With telegraph
--     (seconds) it marks the spot with the usual red X first and yields; it is cancelled when the
--     event (RogueliteRunState EventGen ~= gen) or the wave changes, or `source` (a coffin) is gone.
local eventSpawn = ServerStorage:FindFirstChild('Round10Spawn') or Instance.new('BindableFunction')
eventSpawn.Name = 'Round10Spawn'
local eventSerial = 0
local function eventCurrent(request, generation)
    local run = combat.Parent:FindFirstChild('RogueliteRunState')
    if generation ~= waveGeneration or combat:GetAttribute('ZombiesEnabled') ~= true then return false end
    if not run or run:GetAttribute('EventGen') ~= request.gen then return false end
    local source = request.source
    if typeof(source) == 'Instance' then
        local h = source:FindFirstChildOfClass('Humanoid')
        if not source.Parent or (h and h.Health <= 0) or source:GetAttribute('DeathPopped') then return false end
    end
    return true
end
eventSpawn.OnInvoke = function(action, request)
    if action == 'Arena' then
        local ok, center, radius = pcall(arena)
        if ok then return center, radius end
        return nil
    elseif action == 'Point' then
        request = type(request) == 'table' and request or {}
        local ok, point = pcall(pickSpawnPoint, request.avoid or {}, request.anchor, request.band or SPAWN_BAND, request.minimum or MIN_PLAYER_DISTANCE, nil)
        return ok and point or nil
    elseif action == 'Ground' then
        if typeof(request) ~= 'Vector3' then return nil end
        local ok, point = pcall(function() return groundAt(request, spawnContext()) end)
        return ok and point or nil
    end
    if action ~= 'Spawn' or type(request) ~= 'table' or not EnemyCatalog.get(request.id) or typeof(request.position) ~= 'Vector3' then return nil end
    local generation = waveGeneration
    if not eventCurrent(request, generation) then return nil end
    local telegraph = tonumber(request.telegraph) or 0
    if telegraph > 0 then
        local mark = makeWarning(request.position)
        local warned = 0
        while warned < telegraph and eventCurrent(request, generation) do
            local dt = task.wait(.05)
            warned = Timeline.advanceWarning(warned, dt, spawnHeld())
        end
        mark:Destroy()
        if not eventCurrent(request, generation) then return nil end
    end
    eventSerial += 1
    local serial = eventSerial
    spawnZombie(serial, EnemyCatalog.get(request.id).id, request.position, nil, {gen = request.gen, attrs = type(request.attrs) == 'table' and request.attrs or nil})
    return folder:FindFirstChild(string.format('Event_%03d', serial))
end
eventSpawn.Parent = ServerStorage
-- Bloater fuses and bursts (ExploderService). Optional: a place without it still runs every wave.
do
    local module = script.Parent:FindFirstChild('ExploderService')
    if module then
        local ok, err = pcall(require, module)
        if not ok then warn('ExploderService failed to load: ' .. tostring(err)) end
    end
end
-- More players up mid-wave (a revive, a rejoin, a late arrival) fill the new slots at once; fewer
-- need nothing here (queueSpawn leaves slots past the count empty). Checked once a second.
-- Also repair empty slots after an interrupted/failed spawn, so a wave cannot permanently thin out.
-- Fixed-count tutorial waves deliberately never refill defeated slots.
task.spawn(function()
    local population = 0
    while true do
        task.wait(1)
        if timelineMode() then population=0;continue end
        local count = combat:GetAttribute('ZombiesEnabled') == true and Role.marker() and not adminPaused() and spawnCount() or 0
        if count > 0 then trimBossPopulation() end
        if count > population then
            for index = population + 1, count do queueSpawn(index) end
        end
        if combat:GetAttribute('WaveNoRespawn') ~= true and combat:GetAttribute('TutorialRun') ~= true then
            for index = 1, count do queueSpawn(index, true) end
        end
        population = count
    end
end)

-- Ordinary combat waves consume authored timed arrivals. Deaths, revives and Resume do not
-- refill vacancies. A small dispatcher reserves only the next three warnings, never a mass batch.
RunService.Heartbeat:Connect(function(dt)
    if not timelineMode() or combat:GetAttribute('ZombiesEnabled')~=true or not Role.marker() then return end
    local run=combat.Parent:FindFirstChild('RogueliteRunState')
    local wave=run:GetAttribute('Wave') or 1
    if not timelineState or timelineState.wave~=wave then timelineState=Timeline.new(wave);timelineOrders={} end
    local boss=bossPressure()
    if timelineState.boss~=nil and timelineState.boss~=boss then
        -- A boss arriving mid-wave cancels ordinary queued arrivals before switching to small adds.
        timelineOrders={};queued,queuedSet={},{};pendingGroups={};plannedIds={}
        waveGeneration+=1;warnings:ClearAllChildren();trimBossPopulation()
    end
    local activePlayers=playersUp()
    if timelineState.players~=activePlayers then timelineState.players=activePlayers;trimBossPopulation() end
    local reserved=0;for _ in queuedSet do reserved+=1 end
    Timeline.enqueue(timelineOrders,{},reserved,Timeline.queueLimit(activePlayers,boss))
    local event=Timeline.step(timelineState,dt,spawnHeld(),boss,activePlayers)
    if event then
        local incoming={}
        for n,role in event.roles do
            local id=Timeline.pickId(role,event.serial*100+n,combat:GetAttribute('EnemyRoster'),EnemyCatalog.ById,EnemyCatalog.ByLegacy,wave)
            if wave>20 and Population.toughSlot(event.serial*100+n,Population.endless(wave).tough) then id=toughestId() end
            if id then table.insert(incoming,id) end
        end
        Timeline.enqueue(timelineOrders,incoming,reserved,Timeline.queueLimit(activePlayers,boss))
        script:SetAttribute('TimelinePulse',event.serial)
        script:SetAttribute('TimelineElapsed',event.at)
    end
    if spawnHeld() or activePlayers==0 or os.clock()<timelineDispatchAt then return end
    timelineDispatchAt=os.clock()+Timeline.dispatchInterval(activePlayers)
    for _=1,3 do
        if #timelineOrders==0 then break end
        local pending=0;for _ in queuedSet do pending+=1 end
        if not makeArrivalRoom(pending) then break end
        local free
        for index=1,Timeline.MaxAlive do
            if not queuedSet[index] and not folder:FindFirstChild(string.format('Zombie_%02d',index)) then free=index;break end
        end
        if not free then break end
        plannedIds[free]=table.remove(timelineOrders,1);queueSpawn(free)
    end
end)

-- Endless bosses (2026-10-03, user: "start spawning bosses randomly in endless mode"). Past wave 20
-- the shop before each wave decides if that wave brings a boss (Population.endlessBossDue: 35%,
-- never right after a boss wave, always after 3 without) and which (endlessBossPick: one whose
-- template is in this place, not one of the last two). RogueliteRunState EndlessBossWave / Id / Name
-- tell the HUD, which says so at the top of the screen and loads the boss's animations meanwhile.
-- Population.Endless.bossDelay (5 s) into that wave it lands 28-42 studs from a run member through
-- wave 20's spawns (BossService / MapBossService: entrance, boss bar, crystal shower), with the
-- map's own wave-20 boss health x the Endless scale. ShopService holds the wave open while it lives.
-- Example: Pine Valley Normal solo, wave 26's shop -> "A BOSS approaches next wave: Inferno Dragon";
-- it lands with the Hammer's 18,000 x 1.9 = 34,200 HP, not the Dragon's own number.
local Maps = require(combat:WaitForChild('MapConfig'))
local HAMMER_HEALTH = 18000 -- BossService HEALTH: RunSetupRules bossBase is relative to it
local endless = {state = nil, rng = nil, decided = nil, pending = nil}
local function runState() return game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteRunState') end
local function bossDefs()
    local module = combat:FindFirstChild('MapBossDefs')
    local ok, defs = pcall(function() return module and require(module) end)
    return ok and defs or nil
end
-- MapBossService, or nil when this place lacks it or it fails to load. It never waits, so the old
-- Hammer and the regular enemies never depend on the map-boss modules.
local function mapBossService()
    local module = script.Parent:FindFirstChild('MapBossService')
    local ok, service = pcall(function() return module and require(module) end)
    return ok and service or nil
end
-- A map boss this place can run: MapBossDefs.ready (its def, timing, client clips, template and
-- runtime). A MapBossDefs from before ready() (Studio behind the repo) is read the old way.
local function mapReady(id, defs)
    if not defs then return false end
    if defs.ready then return defs.ready(id) end
    local def, anims = defs.get(id), combat:FindFirstChild('BossAnimations')
    return id ~= 'Hammer' and def ~= nil and templates:FindFirstChild(id .. '_NPC') ~= nil and anims ~= nil and anims:FindFirstChild(def.anim) ~= nil and defs.timing(id) ~= nil
end
-- The Hammer stays on BossService until the rebuilt Hammer Brute is ready here: MapBossDefs.legacy,
-- the gate BossEncounter asks too. A MapBossDefs without legacy() (older, or none) keeps the old one.
local function oldHammer(id, defs)
    if id ~= 'Hammer' then return false end
    if defs and defs.legacy then local ok, old = pcall(defs.legacy, id); return not ok or old ~= false end
    return true
end
-- The bosses this place can spawn: a template in RogueliteNPCs, and a def, timing and client
-- animations for the map bosses. A missing one is never picked.
local function endlessBosses()
    local defs, list = bossDefs(), {}
    for _, id in BossIds do
        local ok
        if oldHammer(id, defs) then ok = templates:FindFirstChild('HammerBoss_NPC') ~= nil
        else
            ok = mapReady(id, defs)
        end
        if ok then table.insert(list, id) end
    end
    return list
end
local function endlessClear(run)
    endless.pending = nil
    run:SetAttribute('EndlessBossWave', nil); run:SetAttribute('EndlessBossId', nil); run:SetAttribute('EndlessBossName', nil)
end
-- Book `id` for `wave` (the HUD shows it from now); it lands `delay` s into that wave.
local function endlessQueue(run, wave, id, delay)
    local defs = bossDefs()
    local def = not oldHammer(id, defs) and defs and defs.get(id)
    endless.pending = {wave = wave, id = id, delay = delay, prev = endless.state and endless.state.last}
    if endless.state then Population.endlessBossRecord(endless.state, wave, id) end
    run:SetAttribute('EndlessBossId', id)
    run:SetAttribute('EndlessBossName', def and def.name or 'Hammer Brute') -- the boss bar's name for the old Hammer
    run:SetAttribute('EndlessBossWave', wave)
    return endless.pending
end
local function endlessSpawn(p)
    local defs = bossDefs()
    local old = oldHammer(p.id, defs)
    local T = not old and defs and defs.timing(p.id)
    if not old and not T then return nil end
    -- A run member's side of the arena, 28-42 studs off on open floor (as admin spawns pick);
    -- else wave 20's spot by the map's marker (BossEncounter).
    local roots = {}
    for _, player in Players:GetPlayers() do
        local character = player:GetAttribute('RunMember') == true and not player:GetAttribute('RunDown') and player.Character
        local root = character and character:FindFirstChild('HumanoidRootPart')
        if root then table.insert(roots, root) end
    end
    local near = roots[math.random(math.max(1, #roots))]
    local picked, point = pcall(pickSpawnPoint, {}, near and near.Position, {28, 42}, 26)
    if not picked then point = nil end
    local m = Role.marker()
    if not point and m then
        local params = RaycastParams.new()
        params.FilterType = Enum.RaycastFilterType.Exclude
        params.FilterDescendantsInstances = {folder, m}
        local ground = workspace:Raycast(m.Position + Vector3.new(0, 35, -15), Vector3.new(0, -100, 0), params)
        point = ground and ground.Position
    end
    if not point then return nil end
    local at = point + Vector3.yAxis * ((old and BossMotion.RootHeight or T.rootHeight) + 0.1)
    local face = near and Vector3.new(near.Position.X, at.Y, near.Position.Z)
    local cf = face and (face - at).Magnitude > 0.5 and CFrame.lookAt(at, face) or CFrame.new(at)
    local boss
    if old then boss = Bosses.spawn(cf, false)
    else
        local service = mapBossService()
        local ok, made = pcall(function() return service and service.spawn(p.id, cf, false, {intro = true}) end)
        if not ok then warn('Endless boss ' .. p.id .. ' failed to spawn: ' .. tostring(made)) end
        boss = ok and made or nil
        -- The rebuilt Hammer failing to spawn brings the old one instead (as BossEncounter does). A
        -- half-built one (the spawn failed after he was parented) goes first, so there are never two.
        if not boss and p.id == 'Hammer' then
            for _, npc in folder:GetChildren() do if npc:GetAttribute('MapBossId') == 'Hammer' then npc:Destroy() end end
            boss = Bosses.spawn(cf + Vector3.yAxis * (BossMotion.RootHeight - T.rootHeight), false); old = boss ~= nil
        end
    end
    if not boss then return nil end
    -- Spawn already scaled it by difficulty, players and map power. Every Endless boss then gets the
    -- map's own boss health (18,000 x RunSetupRules bossBase) x(1 + 0.15 an Endless wave), whoever it
    -- is: wave 30 in Pine Valley is 45,000 solo, 78,750 for two players.
    local scale = Population.endless(math.max(p.wave, Population.Endless.FROM + 1))
    local index = RunSetupRules.MapIndex[combat:GetAttribute('RunMap')] or 1
    local own = HAMMER_HEALTH * (RunSetupRules.Maps[index].bossBase or 1)
    local authored = old and HAMMER_HEALTH or defs.get(p.id).health
    local h = boss:FindFirstChildOfClass('Humanoid')
    if h then h.MaxHealth = math.ceil(h.MaxHealth * own / authored * scale.bossHealth); h.Health = h.MaxHealth end
    boss:SetAttribute('BossDamageScale', (boss:GetAttribute('BossDamageScale') or 1) * scale.bossDamage)
    boss:SetAttribute('EndlessBoss', p.wave)
    return boss
end
local function bossUp()
    for _, npc in folder:GetChildren() do
        local h = npc:GetAttribute('IsBoss') and npc:FindFirstChildOfClass('Humanoid')
        if h and h.Health > 0 then return true end
    end
    return false
end
-- Waits out pauses and entrances; gives up if the wave moved on or another boss is up.
local function endlessArrive(p)
    local run = runState()
    while true do
        if endless.pending ~= p or not run or run:GetAttribute('Wave') ~= p.wave or run:GetAttribute('Phase') ~= 'Combat' or combat:GetAttribute('ZombiesEnabled') ~= true then return end
        if not adminPaused() and run:GetAttribute('Paused') ~= true and (combat:GetAttribute('CinematicUntil') or 0) <= workspace:GetServerTimeNow() then break end
        task.wait(0.5)
    end
    if bossUp() then return end -- one boss at a time: one already up (an admin's) is this wave's
    p.landed = true
    local ok, boss = pcall(endlessSpawn, p)
    if not ok then warn('Endless boss failed: ' .. tostring(boss)) end
    if ok and boss then p.boss = boss; endlessBoss = boss; return end
    -- Never break a run: no boss this wave after all, so it doesn't count as a boss wave.
    if endless.state and endless.state.last == p.wave and p.prev then endless.state.last = p.prev end
end
local function endlessCheck()
    local run = runState(); if not run then return end
    local wave, phase = run:GetAttribute('Wave'), run:GetAttribute('Phase')
    if type(wave) ~= 'number' then return end
    if endless.pending and endless.pending.wave ~= wave then endlessClear(run) end
    if wave <= Population.Endless.FROM or combat:GetAttribute('TutorialRun') == true then
        endless.state, endless.decided = nil, nil -- the history starts over at wave 21
    elseif phase == 'Shop' and (endless.decided or 0) < wave then
        endless.decided = wave
        if not endless.state then
            local map = Maps.get(combat:GetAttribute('RunMap'))
            endless.state, endless.rng = Population.endlessState(map and map.boss), Random.new()
        end
        if not endless.pending and Population.endlessBossDue(endless.state, wave, endless.rng) then
            local ok, list = pcall(endlessBosses)
            local id = ok and Population.endlessBossPick(list, endless.state.recent, endless.rng)
            if id then endlessQueue(run, wave, id, Population.Endless.bossDelay) end -- none in the place: no boss
        end
    end
    local p = endless.pending
    if p and p.wave == wave then
        if phase == 'Combat' and not p.armed then p.armed = true; task.delay(p.delay, endlessArrive, p)
        elseif phase ~= 'Combat' and not p.landed then p.armed = false end
    end
end
local function endlessCheckSafe()
    local ok, err = pcall(endlessCheck)
    if not ok then warn('Endless boss check failed: ' .. tostring(err)) end
end
task.spawn(function()
    local run = game:GetService('ReplicatedStorage'):WaitForChild('RogueliteRunState')
    for _, name in {'Wave', 'Phase'} do run:GetAttributeChangedSignal(name):Connect(function() task.defer(endlessCheckSafe) end) end
    endlessCheckSafe()
end)
-- The admin panel's Spawn Endless boss (AdminService): a random boss with the Endless pick and
-- scale, landing now in a wave, or 5 s into the next wave from the shop. Up to wave 20 it is
-- scaled as wave 21. Returns ok, message.
local function endlessAdmin()
    local run = runState()
    local wave, phase = run and run:GetAttribute('Wave'), run and run:GetAttribute('Phase')
    if type(wave) ~= 'number' or (phase ~= 'Combat' and phase ~= 'Shop') then return false, 'Start Waves first (the sandbox has no waves)' end
    if combat:GetAttribute('TutorialRun') == true then return false, 'Not in the tutorial' end
    if phase == 'Combat' and bossUp() then return false, 'A boss is already up' end
    local ok, list = pcall(endlessBosses)
    local id = ok and Population.endlessBossPick(list, endless.state and endless.state.recent or {}, endless.rng or Random.new())
    if not id then return false, 'No boss templates in this place' end
    local p = endlessQueue(run, wave, id, phase == 'Combat' and 0 or Population.Endless.bossDelay)
    local name = run:GetAttribute('EndlessBossName')
    if phase ~= 'Combat' then return true, name .. ' comes ' .. Population.Endless.bossDelay .. ' s into the next wave' end
    p.armed = true
    task.spawn(endlessArrive, p)
    if p.landed and not p.boss then return false, 'No open floor for ' .. name end
    return true, 'Endless boss: ' .. name
end

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
    elseif action == 'EndlessBoss' then
        return endlessAdmin()
    elseif action ~= 'Spawn' or typeof(position) ~= 'Vector3' or type(count) ~= 'number' then
        return 0
    end
    if combat:GetAttribute('ZombiesEnabled') ~= true or not Role.marker() then return 0 end
    local made = 0
    -- AdminConfig caps bosses at 5; checked here again.
    for _ = 1, math.clamp(math.floor(count), 0, table.find(BossIds, id) and 5 or 50) do
        local point = pickSpawnPoint({}, position, {20, 40}, 20)
        if point then
            -- The old BossService Hammer until the rebuilt one is ready (oldHammer); then the map-boss path below.
            if id == 'Hammer' and oldHammer(id, bossDefs()) then
                local at = point + Vector3.yAxis * (BossMotion.RootHeight + 0.1)
                local boss = Bosses.spawn(CFrame.lookAt(at, Vector3.new(position.X, at.Y, position.Z)), true)
                if boss then boss:SetAttribute('AdminSpawn', true); made += 1 end
            elseif table.find(BossIds, id) then
                local defs, service = bossDefs(), mapBossService()
                local timing = defs and service and defs.timing(id)
                local at = timing and point + Vector3.yAxis * (timing.rootHeight + 0.1)
                local boss = at and service.spawn(id, CFrame.lookAt(at, Vector3.new(position.X, at.Y, position.Z)), true)
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
        if timelineMode() then return end
        if adminPaused() or combat:GetAttribute('ZombiesEnabled') ~= true or not Role.marker() then return end
        for index = 1, spawnCount() do queueSpawn(index) end
    end)
    run:GetAttributeChangedSignal('AdminPaused'):Connect(function()
        if timelineMode() then return end
        if adminPaused() or combat:GetAttribute('ZombiesEnabled') ~= true or not Role.marker() then return end
        for index = 1, spawnCount() do queueSpawn(index) end
    end)
end)
