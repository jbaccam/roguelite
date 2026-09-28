# Plan A: Server Roles and Maps

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One Studio place boots as a Lobby, Match or Combined server. It keeps only the areas that role needs, and the active map (Pine Valley or Beach Cove) drives the player spawn, enemy spawn area, enemy roster and boss.

**Architecture:**
- A new sandboxed server module `ServerRole` decides the role once at boot:
  - Reserved server → Match.
  - Other live server → Lobby.
  - Studio → Workspace attribute `StudioServerRole`, default Combined.
- It parks unused areas in `ServerStorage.InactiveAreas`, and it makes the combat attribute `RunMap` the single source of truth for the active map.
- A new shared data module `MapConfig` lists each map's Workspace folders, roster and boss.
- Existing scripts stop using fixed `workspace.X` paths and ask `ServerRole` instead.

**Tech stack:** Roblox Luau, Roblox Studio via the Studio MCP (`execute_luau`, `start_stop_play`, `get_console_output`), a local Python HTTP server for syncing repo files into Studio.

**Spec:** `roguelite-planning/LOBBY_AND_MATCH_SERVERS.md` §1, §3 and §9. Plans B (run lifecycle) and C (cross-server teleports and the session lock) follow this one and are written after it lands.

---

## Conventions (read before any task)

**Paths.** Repo paths are relative to `C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/`. Studio paths are DataModel paths.

| Repo file | Studio instance |
|---|---|
| `studio-prototype/combat/MapConfig.luau` | `ReplicatedStorage.RogueliteCombat.MapConfig` (ModuleScript, **Sandboxed**, Capabilities copied from `CharacterStats`) |
| `studio-prototype/combat/MapConfigTests.luau` | `ServerStorage.RogueliteTests.MapConfigTests` (ModuleScript) |
| `studio-prototype/lobby/ServerRole.luau` | `ServerScriptService.ServerRole` (ModuleScript, **Sandboxed**, Capabilities copied from `ShopService`) |
| `studio-prototype/lobby/ServerRoleBoot.server.luau` | `ServerScriptService.ServerRoleBoot` (Script) |
| `studio-prototype/lobby/ServerRoleTests.luau` | `ServerStorage.RogueliteTests.ServerRoleTests` (ModuleScript) |
| `studio-prototype/lobby/GroupMapAreas.luau` | not installed; run once in Edit |
| `studio-prototype/RogueliteZombieChase.server.luau` | `ServerScriptService.RogueliteZombieChase` |
| `hammer-boss/BossEncounter.server.luau` | `ServerScriptService.BossEncounter` |
| `studio-prototype/combat/RogueliteCombat.server.luau` | `ServerScriptService.RogueliteCombat` |
| `studio-prototype/lobby/RogueliteLobbyPreview.server.luau` | `ServerScriptService.RogueliteLobbyPreview` |
| `studio-prototype/lobby/RogueliteLobbyPreview.client.luau` | `StarterPlayer.StarterPlayerScripts.RogueliteLobbyPreview` |
| `studio-prototype/ui/RogueliteLobbyHUD.client.luau` | `StarterPlayer.StarterPlayerScripts.RogueliteLobbyHUD` |
| `studio-prototype/lobby/RogueliteLobbyPortalEnergy.client.luau` (new export) | `StarterPlayer.StarterPlayerScripts.RogueliteLobbyPortalEnergy` |
| `studio-prototype/ApplyPropCollision.luau` | not installed; an Edit tool |

**Sandboxing** (it has broken this place twice). A sandboxed script can only require sandboxed modules.
- `RogueliteCombat` (server) and `ShopService` are sandboxed, so `ServerRole` and `MapConfig` must be too: set `Sandboxed = true` and copy `Capabilities` from a sibling.
- Unsandboxed scripts (`RogueliteZombieChase`, `BossEncounter`, `RogueliteLobbyPreview`) may require sandboxed modules.
- **Never** require `RunSetupRules` or any other unsandboxed module from a sandboxed script.

**Shared Studio.** The user runs several Claude sessions against this one Studio.
- Before every `start_stop_play`, call `list_sessions` and `get_studio_state`.
- If Studio is already in Play and you didn't start it, don't touch Play. Wait, or ask the user.
- Never use a positioned `screen_capture`.
- Always stop Play when a check is finished.

**Local file server.** Start it once, in the background, before Task 1:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning"
```

**Studio helper.** Paste this block at the top of every Edit-mode `execute_luau` call that syncs or tests:

```lua
local RS,SSS,SS=game:GetService('ReplicatedStorage'),game:GetService('ServerScriptService'),game:GetService('ServerStorage')
local Http=game:GetService('HttpService')
local function pull(path)
 local was=Http.HttpEnabled;Http.HttpEnabled=true
 local ok,src=pcall(function() return Http:GetAsync('http://127.0.0.1:8765/'..path,true) end)
 Http.HttpEnabled=was
 assert(ok,'pull '..path..': '..tostring(src))
 return (src:gsub('\r\n','\n'))
end
local function norm(s) return ((s:gsub('\r\n','\n')):gsub('%s+$','')) end
-- true when Studio and the repo file hold the same code
local function same(inst,path) return norm(inst.Source)==norm(pull(path)) end
-- Overwrite an existing script with the repo file.
local function sync(inst,path) inst.Source=pull(path);return inst end
-- Create (if missing) and fill a script; capsFrom makes it sandboxed with that sibling's Capabilities.
local function create(className,name,parent,path,capsFrom)
 local s=parent:FindFirstChild(name)
 if not s then
  s=Instance.new(className);s.Name=name
  if capsFrom then s.Sandboxed=true;s.Capabilities=capsFrom.Capabilities end
  s.Parent=parent
 end
 s.Source=pull(path);return s
end
-- Require a fresh copy (Studio caches module results in Edit).
local function fresh(m) local c=m:Clone();c.Parent=m.Parent;local ok,r=pcall(require,c);c:Destroy();assert(ok,r);return r end
local function testsFolder() local f=SS:FindFirstChild('RogueliteTests') or Instance.new('Folder');f.Name='RogueliteTests';f.Parent=SS;return f end
```

**Editing an existing script.** Before you edit its repo file, run `return same(<instance>,'<repo path>')` in Edit.
- **Expected: `true`.** If it returns `false`, Studio or the repo holds someone else's unsynced edits. Stop and tell the user; don't overwrite either side.
- After editing the repo file, run `sync(<instance>,'<repo path>')`.

**Commits.** Commit only files this task changed, on `main`. Other sessions share this working folder, so never switch branches. End every message with:

```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

If Task 0 recorded "no baseline", skip every commit step and list the changed files in the final report instead.

---

### Task 0: Pre-flight

**Files:** none.

- [ ] **Step 1: Baseline decision.** Several files this plan edits, including the whole `studio-prototype/lobby/` folder, `ui/RogueliteLobbyHUD.client.luau` and `ApplyPropCollision.luau`, have never been committed, and others carry other sessions' uncommitted work. Ask the user one question:

  > "Before I start, can I make one baseline commit of all current roguelite work, so each task after it commits only its own changes?"

  - **If yes:** run the command below.
  - **If no:** record "no baseline" and skip every commit step in this plan.

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning && git commit -q -m "$(printf 'Baseline roguelite work before server roles\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')" && git log --oneline -1
```

- [ ] **Step 2: Start the local file server** (the command in Conventions) in the background. Check it with:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/LOBBY_AND_MATCH_SERVERS.md
```

  Expected: `200`.

- [ ] **Step 3: Confirm Studio is in Edit** (`get_studio_state` → `Current Studio Mode: Edit`) and no other session is in Play (`list_sessions`).

---

### Task 1: MapConfig (map data)

**Files:**
- Create: `studio-prototype/combat/MapConfigTests.luau`
- Create: `studio-prototype/combat/MapConfig.luau`

- [ ] **Step 1: Write the failing test.** Create `studio-prototype/combat/MapConfigTests.luau`:

```lua
-- MapConfig data checks. Run in Studio Edit (plan A, Task 1).
return function(Maps, EnemyCatalog, Rules)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	check(Maps.valid(Maps.Default), "Default map must exist")
	check(not Maps.valid("Nope") and not Maps.valid(nil) and not Maps.valid(5), "Unknown ids are invalid")
	check(Maps.get("Nope") == nil, "get() returns nil for unknown ids")
	local seenFolders = {}
	for _, name in Maps.LobbyFolders do
		seenFolders[name] = "lobby"
	end
	for id, map in Maps.Maps do
		local index = Rules.MapIndex[id]
		check(index ~= nil, id .. " must be a RunSetupRules map")
		check(#map.folders > 0, id .. " needs at least one folder")
		for _, name in map.folders do
			check(type(name) == "string" and seenFolders[name] == nil, id .. " folder " .. tostring(name) .. " is shared")
			seenFolders[name] = id
		end
		check(map.boss == nil or map.boss == "Hammer", id .. " boss must be Hammer or nil")
		if map.roster ~= nil then
			local count = 0
			for enemyId in map.roster:gmatch("[^,%s]+") do
				local enemy = EnemyCatalog.ById[enemyId]
				check(enemy ~= nil, id .. " roster has unknown enemy " .. enemyId)
				check(enemy.map == Rules.Maps[index].name, enemyId .. " belongs to " .. tostring(enemy.map))
				count += 1
			end
			check(count > 0, id .. " roster must not be empty")
		end
	end
	check(Maps.Maps.PineValley.boss == "Hammer" and Maps.Maps.PineValley.roster == nil, "Pine Valley keeps its zombies and Hammer boss")
	check(Maps.Maps.BeachCove.boss == nil, "Beach Cove is won by clearing wave 20")
	return { passed = checks }
end
```

- [ ] **Step 2: Install the test and run it; it should fail.** In Edit (helper block first):

```lua
create('ModuleScript','MapConfigTests',testsFolder(),'studio-prototype/combat/MapConfigTests.luau')
return fresh(SS.RogueliteTests.MapConfigTests)(fresh(RS.RogueliteCombat.MapConfig),require(RS.RogueliteCombat.EnemyCatalog),require(RS.RunSetupRules))
```

  Expected: an error containing `MapConfig is not a valid member`.

- [ ] **Step 3: Write MapConfig.** Create `studio-prototype/combat/MapConfig.luau`:

```lua
-- Per-map match data for the server roles, the wave spawner and the boss trigger.
-- Keys are RunSetupRules.Maps ids (LOBBY_AND_MATCH_SERVERS.md §1, §3).
-- folders: the Workspace folders that make up the map; ServerRole.find searches them in order.
-- roster: EnemyCatalog ids cycled by spawn slot; repeating an id weights it. nil keeps Pine
-- Valley's wave-based zombie mix. boss: 'Hammer' spawns the Hammer boss at wave 20; nil means
-- the map is won by clearing wave 20.
local M={Default='PineValley',LobbyFolders={'RogueliteLobby'}}
M.Maps={
 PineValley={folders={'PineValleyArena'},boss='Hammer'},
 -- blender-beach-cove-kit rebuilds BeachCoveArena by deleting it, so the markers and the
 -- hand-placed props live beside it in BeachCoveExtras.
 BeachCove={folders={'BeachCoveArena','BeachCoveExtras'},roster='crab,snake,crab,hermit-crab,crab,rock-throwing-crab'},
}
function M.valid(id) return type(id)=='string' and M.Maps[id]~=nil end
function M.get(id) return M.valid(id) and M.Maps[id] or nil end
return M
```

- [ ] **Step 4: Install it (sandboxed) and run the test; it should pass.** In Edit:

```lua
create('ModuleScript','MapConfig',RS.RogueliteCombat,'studio-prototype/combat/MapConfig.luau',RS.RogueliteCombat.CharacterStats)
local r=fresh(SS.RogueliteTests.MapConfigTests)(fresh(RS.RogueliteCombat.MapConfig),require(RS.RogueliteCombat.EnemyCatalog),require(RS.RunSetupRules))
return 'passed '..r.passed..' sandboxed='..tostring(RS.RogueliteCombat.MapConfig.Sandboxed)
```

  Expected: `passed 27 sandboxed=true`. That count is:
  - 3 general checks.
  - Pine Valley: 4 (it's a RunSetupRules map, has folders, 1 folder name, boss).
  - Beach Cove: 18 (map, has folders, 2 folder names, boss, 6 roster entries × 2, roster not empty).
  - 2 final checks.

  If the number differs, re-count against the test before changing anything.

- [ ] **Step 5: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/combat/MapConfig.luau roguelite-planning/studio-prototype/combat/MapConfigTests.luau && git commit -q -m "$(printf 'Add MapConfig: per-map folders, roster and boss\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 2: ServerRole (role detection, parking, active map)

**Files:**
- Create: `studio-prototype/lobby/ServerRoleTests.luau`
- Create: `studio-prototype/lobby/ServerRole.luau`
- Create: `studio-prototype/lobby/ServerRoleBoot.server.luau`

- [ ] **Step 1: Write the failing test.** Create `studio-prototype/lobby/ServerRoleTests.luau`:

```lua
-- ServerRole.detect checks. Run in Studio Edit (plan A, Task 2); Edit mode has no boot side effects.
return function(Role)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	check(Role.detect(true, nil, "", 0) == "Combined", "Studio defaults to Combined")
	check(Role.detect(true, "Lobby", "", 0) == "Lobby", "Studio can force Lobby")
	check(Role.detect(true, "Match", "", 0) == "Match", "Studio can force Match")
	check(Role.detect(true, "Arena", "", 0) == "Combined", "Unknown Studio roles fall back to Combined")
	check(Role.detect(true, "Lobby", "abc", 0) == "Lobby", "Studio ignores server ids")
	check(Role.detect(false, "Match", "", 0) == "Lobby", "Live public servers are lobbies whatever the Studio attribute says")
	check(Role.detect(false, nil, "abc-123", 0) == "Match", "Reserved servers are matches")
	check(Role.detect(false, nil, "abc-123", 99) == "Lobby", "Player-bought VIP servers are lobbies")
	return { passed = checks }
end
```

- [ ] **Step 2: Install the test and run it; it should fail.** In Edit:

```lua
create('ModuleScript','ServerRoleTests',testsFolder(),'studio-prototype/lobby/ServerRoleTests.luau')
return fresh(SS.RogueliteTests.ServerRoleTests)(fresh(SSS.ServerRole))
```

  Expected: an error containing `ServerRole is not a valid member`.

- [ ] **Step 3: Write ServerRole.** Create `studio-prototype/lobby/ServerRole.luau`:

```lua
-- Which kind of server this is and which map it plays (LOBBY_AND_MATCH_SERVERS.md §1).
-- Match: a reserved server (TeleportService:ReserveServer). Lobby: every other live server,
-- including player-bought VIP servers. Studio: Workspace.StudioServerRole picks 'Lobby' or
-- 'Match'; anything else is 'Combined' (lobby and maps in one server, the old preview).
-- Areas a role doesn't use wait in ServerStorage.InactiveAreas, so clients never stream them.
-- The active map is the combat attribute RunMap. Only its PlayerSpawn is enabled, because Roblox
-- spawns players at a random enabled SpawnLocation.
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local ServerStorage=game:GetService('ServerStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Maps=require(combat:WaitForChild('MapConfig'))
local R={}

function R.detect(isStudio,studioRole,privateServerId,privateServerOwnerId)
 if isStudio then return (studioRole=='Lobby' or studioRole=='Match') and studioRole or 'Combined' end
 return (privateServerId~='' and privateServerOwnerId==0) and 'Match' or 'Lobby'
end
local role=R.detect(RunService:IsStudio(),workspace:GetAttribute('StudioServerRole'),game.PrivateServerId,game.PrivateServerOwnerId)
function R.get() return role end
function R.activeMap() local id=combat:GetAttribute('RunMap');return Maps.valid(id) and id or nil end
-- A direct child of the active map's folders: markers, PlayerSpawn, blockers, boundary.
function R.find(name)
 local map=Maps.get(R.activeMap());if not map or type(name)~='string' then return nil end
 for _,folderName in map.folders do
  local folder=workspace:FindFirstChild(folderName);local child=folder and folder:FindFirstChild(name)
  if child then return child end
 end
 return nil
end
function R.marker() return R.find('RogueliteZombieSpawn') end
function R.playerSpawn() return R.find('PlayerSpawn') end

-- Edit mode (tests, command bar): detection only, no side effects.
if not RunService:IsRunning() then return R end

local parked=ServerStorage:FindFirstChild('InactiveAreas') or Instance.new('Folder')
parked.Name='InactiveAreas';parked.Parent=ServerStorage
local function place(name,active)
 local area=workspace:FindFirstChild(name) or parked:FindFirstChild(name)
 if area then area.Parent=active and workspace or parked end
end
local function applyMap()
 local id=R.activeMap();if role=='Lobby' or not id then return end
 for mapId,map in Maps.Maps do
  for _,name in map.folders do
   if role=='Match' then place(name,mapId==id) end
   local area=workspace:FindFirstChild(name) or parked:FindFirstChild(name)
   local spawn=area and area:FindFirstChild('PlayerSpawn')
   if spawn and spawn:IsA('SpawnLocation') then spawn.Enabled=mapId==id end
  end
 end
 combat:SetAttribute('EnemyRoster',Maps.get(id).roster)
end
-- Switch the active map: once per match server, and on each START in Combined Studio.
function R.setMap(id)
 if not Maps.valid(id) then return false end
 if combat:GetAttribute('RunMap')==id then applyMap() else combat:SetAttribute('RunMap',id) end
 return true
end

RS:SetAttribute('ServerRole',role)
if role=='Lobby' then
 for _,map in Maps.Maps do for _,name in map.folders do place(name,false) end end
elseif role=='Match' then
 for _,name in Maps.LobbyFolders do place(name,false) end
 for _,map in Maps.Maps do for _,name in map.folders do place(name,false) end end
end
combat:GetAttributeChangedSignal('RunMap'):Connect(applyMap)
if role=='Combined' then
 R.setMap(R.activeMap() or Maps.Default)
elseif role=='Match' and RunService:IsStudio() then
 -- Studio stand-in for the match entry that live match servers read (plan C).
 local studioMap=workspace:GetAttribute('StudioMatchMap')
 combat:SetAttribute('RunDifficulty',workspace:GetAttribute('StudioMatchDifficulty') or 'Normal')
 R.setMap(Maps.valid(studioMap) and studioMap or Maps.Default)
end
return R
```

- [ ] **Step 4: Write the boot script.** Create `studio-prototype/lobby/ServerRoleBoot.server.luau`:

```lua
-- Picks this server's role and parks unused areas as soon as the server starts (ServerRole).
require(script.Parent:WaitForChild('ServerRole'))
```

- [ ] **Step 5: Install both and run the test; it should pass.** In Edit:

```lua
create('ModuleScript','ServerRole',SSS,'studio-prototype/lobby/ServerRole.luau',SSS.ShopService)
create('Script','ServerRoleBoot',SSS,'studio-prototype/lobby/ServerRoleBoot.server.luau')
local r=fresh(SS.RogueliteTests.ServerRoleTests)(fresh(SSS.ServerRole))
return 'passed '..r.passed..' sandboxed='..tostring(SSS.ServerRole.Sandboxed)..' areasUntouched='..tostring(workspace:FindFirstChild('RogueliteLobby')~=nil and SS:FindFirstChild('InactiveAreas')==nil)
```

  Expected: `passed 8 sandboxed=true areasUntouched=true`. Requiring it in Edit must not park anything.

- [ ] **Step 6: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/lobby/ServerRole.luau roguelite-planning/studio-prototype/lobby/ServerRoleBoot.server.luau roguelite-planning/studio-prototype/lobby/ServerRoleTests.luau && git commit -q -m "$(printf 'Add ServerRole: lobby/match/combined detection and area parking\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

> Don't Play-test yet. The Workspace folders `ServerRole` looks for are created in Task 3. Until then Combined mode behaves as before, because `setMap` finds no folders and changes nothing.

---

### Task 3: Group the map areas (one-time Edit migration)

**Files:**
- Create: `studio-prototype/lobby/GroupMapAreas.luau`

This moves Workspace content into folders. **Positions never change.** Every move is logged so `UNDO=true` reverses it.

- [ ] **Step 1: Write the migration.** Create `studio-prototype/lobby/GroupMapAreas.luau`:

```lua
-- One-time Edit migration (LOBBY_AND_MATCH_SERVERS.md §9). Gathers Pine Valley's loose Workspace
-- parts into Workspace.PineValleyArena and Beach Cove's hand-placed props into
-- Workspace.BeachCoveExtras.Props, then gives each map a PlayerSpawn and a RogueliteZombieSpawn.
-- Positions never change. Every move and every new instance is recorded in
-- ServerStorage.MapGrouping_20260928; set UNDO=true and run again to reverse it. Running it
-- twice is safe: it only picks up what is still loose.
local UNDO=false
local PINE_CENTER=Vector3.new(56,5,450) -- Pine Valley's zombie spawn marker
local PINE_RADIUS=250
local BEACH_CENTER=Vector3.new(700,0,300) -- BeachCoveArena.SandFloor
local BEACH_RADIUS=190
local KEEP={Baseplate=true,RogueliteLobby=true,BeachCoveArena=true,BeachCoveExtras=true,PineValleyArena=true}
local SS=game:GetService('ServerStorage')
local log=SS:FindFirstChild('MapGrouping_20260928') or Instance.new('Folder')
log.Name='MapGrouping_20260928';log.Parent=SS
local function record(kind,inst) local v=Instance.new('ObjectValue');v.Name=kind;v.Value=inst;v.Parent=log end

if UNDO then
 local restored,removed=0,0
 for _,v in log:GetChildren() do if v.Name=='moved' and v.Value then v.Value.Parent=workspace;restored+=1 end end
 for _,v in log:GetChildren() do if v.Name=='created' and v.Value then v.Value:Destroy();removed+=1 end end
 for _,inst in workspace:GetChildren() do
  local original=inst:GetAttribute('OriginalName')
  if original then inst.Name=original;inst:SetAttribute('OriginalName',nil) end
  if inst:GetAttribute('AddedSpawnBoundaryModel') then inst:SetAttribute('SpawnBoundaryModel',nil);inst:SetAttribute('AddedSpawnBoundaryModel',nil) end
 end
 log:Destroy()
 return ('Undone: %d moved back, %d created removed'):format(restored,removed)
end

local function flat(p) return Vector3.new(p.X,0,p.Z) end
local function where(inst)
 if inst:IsA('BasePart') then return inst.Position end
 if inst:IsA('Model') then return inst:GetPivot().Position end
 local sum,n=Vector3.zero,0
 for _,d in inst:GetDescendants() do if d:IsA('BasePart') then sum+=d.Position;n+=1 end end
 return n>0 and sum/n or nil
end
local function folder(parent,name)
 local f=parent:FindFirstChild(name)
 if not f then f=Instance.new('Folder');f.Name=name;f.Parent=parent;record('created',f) end
 return f
end
local function move(inst,into) record('moved',inst);inst.Parent=into end

local pine=folder(workspace,'PineValleyArena')
local extras=folder(workspace,'BeachCoveExtras')
local props=folder(extras,'Props')
local movedPine,movedBeach=0,0
for _,c in workspace:GetChildren() do
 if KEEP[c.Name] or c:IsA('Terrain') or c:IsA('Camera') or game:GetService('Players'):GetPlayerFromCharacter(c) then continue end
 local p=where(c);if not p then continue end
 if (p-PINE_CENTER).Magnitude<PINE_RADIUS then move(c,pine);movedPine+=1
 elseif (c:IsA('BasePart') or c:IsA('Model')) and (flat(p)-flat(BEACH_CENTER)).Magnitude<BEACH_RADIUS then move(c,props);movedBeach+=1 end
end

-- Pine Valley: its SpawnLocation becomes PlayerSpawn; its marker names its boundary explicitly.
local pineSpawn=pine:FindFirstChild('SpawnLocation')
if pineSpawn then pineSpawn:SetAttribute('OriginalName',pineSpawn.Name);pineSpawn.Name='PlayerSpawn' end
pineSpawn=pine:FindFirstChild('PlayerSpawn')
local pineMarker=pine:FindFirstChild('RogueliteZombieSpawn')
if pineMarker and pineMarker:GetAttribute('SpawnBoundaryModel')==nil then
 pineMarker:SetAttribute('SpawnBoundaryModel','MapOneBoundary');pineMarker:SetAttribute('AddedSpawnBoundaryModel',true)
end

-- Beach Cove: markers beside the rebuilt arena (MapConfig note).
local arena=workspace.BeachCoveArena
local sand=arena.SandFloor
local floorTop=sand.Position.Y+sand.Size.X/2 -- a cylinder lying on its side (ApplyPropCollision)
local center=Vector3.new(sand.Position.X,floorTop,sand.Position.Z)
local ring=0
for _,w in arena.BoundaryWall:GetDescendants() do
 if w:IsA('BasePart') and w.Name:match('^Wall') then ring=math.max(ring,(flat(w.Position)-flat(center)).Magnitude) end
end
local function clearSpot()
 local params=OverlapParams.new();params.FilterType=Enum.RaycastFilterType.Exclude
 params.FilterDescendantsInstances={sand,arena.BoundaryWall,workspace.Baseplate}
 for radius=0,60,6 do
  for step=0,(radius==0 and 0 or 11) do
   local a=step*math.pi/6
   local p=center+Vector3.new(math.cos(a)*radius,0,math.sin(a)*radius)
   if #workspace:GetPartBoundsInBox(CFrame.new(p+Vector3.new(0,4,0)),Vector3.new(12,7,12),params)==0 then return p end
  end
 end
 return center
end
if not extras:FindFirstChild('PlayerSpawn') then
 local s=Instance.new('SpawnLocation');s.Name='PlayerSpawn'
 s.Anchored=true;s.Size=Vector3.new(12,1,12);s.Transparency=1;s.CanCollide=false;s.CanQuery=false
 s.Enabled=false -- ServerRole enables the active map's spawn
 s.Duration=pineSpawn and pineSpawn.Duration or 10
 s.Position=clearSpot()+Vector3.new(0,.5,0)
 for _,d in s:GetChildren() do d:Destroy() end
 s.Parent=extras;record('created',s)
end
if not extras:FindFirstChild('RogueliteZombieSpawn') then
 local m=Instance.new('Part');m.Name='RogueliteZombieSpawn'
 m.Anchored=true;m.Size=Vector3.new(1,1,1);m.Transparency=1;m.CanCollide=false;m.CanTouch=false
 m.Position=center+Vector3.new(0,.5,0)
 m:SetAttribute('SpawnAreaCenter',center);m:SetAttribute('SpawnAreaRadius',math.floor(ring-11))
 m:SetAttribute('SpawnBlockerFolder','NoClimb');m:SetAttribute('SpawnBoundaryModel','BoundaryWall')
 m.Parent=extras;record('created',m)
end
return ('Pine Valley: %d moved. Beach Cove: %d props moved, wall ring %.1f, spawn radius %d, PlayerSpawn at %s'):format(
 movedPine,movedBeach,ring,extras.RogueliteZombieSpawn:GetAttribute('SpawnAreaRadius'),tostring(extras.PlayerSpawn.Position))
```

- [ ] **Step 2: Snapshot the current layout** so the result can be compared. In Edit:

```lua
local n=0;for _,c in workspace:GetChildren() do n+=1 end
return 'workspace children before: '..n
```

  Record the number, about 250.

- [ ] **Step 3: Run the migration** in Edit, loading it through the helper (loadstring works in Edit):

```lua
return loadstring(pull('studio-prototype/lobby/GroupMapAreas.luau'))()
```

  Expected, from the 2026-09-28 survey: `Pine Valley: ~190 moved. Beach Cove: ~40 props moved, wall ring 106.0, spawn radius 95, PlayerSpawn at <x≈700, y≈1.5, z≈300 ± 60>`.

- [ ] **Step 4: Verify nothing map-related is still loose.** In Edit:

```lua
local loose={}
for _,c in workspace:GetChildren() do
 local p=(c:IsA('BasePart') and c.Position) or (c:IsA('Model') and c:GetPivot().Position)
 if p and ((p-Vector3.new(56,5,450)).Magnitude<250 or (Vector3.new(p.X,0,p.Z)-Vector3.new(700,0,300)).Magnitude<190) and c.Name~='Baseplate' then table.insert(loose,c.Name) end
end
local pine,extras=workspace.PineValleyArena,workspace.BeachCoveExtras
return ('loose=%d pineChildren=%d pineSpawn=%s pineMarker=%s beachProps=%d beachSpawnEnabled=%s beachMarkerRadius=%s'):format(
 #loose,#pine:GetChildren(),tostring(pine:FindFirstChild('PlayerSpawn')~=nil),tostring(pine:FindFirstChild('RogueliteZombieSpawn')~=nil),
 #extras.Props:GetChildren(),tostring(extras.PlayerSpawn.Enabled),tostring(extras.RogueliteZombieSpawn:GetAttribute('SpawnAreaRadius')))
```

  Expected: `loose=0 pineChildren=<≈190> pineSpawn=true pineMarker=true beachProps=<≈40> beachSpawnEnabled=false beachMarkerRadius=95`.

- [ ] **Step 5: Look at it.** Take a plain `screen_capture` with **no camera position**. The maps must look exactly as before. Nothing moved; only the Explorer tree changed.

- [ ] **Step 6: Commit** the migration script. The Studio change lives in the place file.

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/lobby/GroupMapAreas.luau && git commit -q -m "$(printf 'Group Pine Valley and Beach Cove into map folders with spawn markers\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 4: Wave spawner and boss follow the active map

**Files:**
- Modify: `studio-prototype/RogueliteZombieChase.server.luau` (lines 8, 32, 55-57, 78, 90, 94, 258, 261, 271, 355)
- Modify: `hammer-boss/BossEncounter.server.luau` (lines 1-2, 5, 12)

- [ ] **Step 1: Check that Studio matches the repo** for both scripts. In Edit:

```lua
return tostring(same(SSS.RogueliteZombieChase,'studio-prototype/RogueliteZombieChase.server.luau'))..' '..tostring(same(SSS.BossEncounter,'hammer-boss/BossEncounter.server.luau'))
```

  Expected: `true true`. If either is `false`, stop and tell the user.

- [ ] **Step 2: Edit `RogueliteZombieChase.server.luau`.** Make these exact replacements.

  a) Replace:
```lua
local combat = game:GetService('ReplicatedStorage'):WaitForChild('RogueliteCombat')
```
  with:
```lua
local combat = game:GetService('ReplicatedStorage'):WaitForChild('RogueliteCombat')
local Role = require(game:GetService('ServerScriptService'):WaitForChild('ServerRole'))
-- Lobby servers run no waves; their maps are parked (ServerRole).
if Role.get() == 'Lobby' then return end
```

  b) Replace:
```lua
local marker = workspace:WaitForChild("RogueliteZombieSpawn")
```
  with:
```lua
-- The active map's marker, looked up on each use: Studio's combined mode can switch maps between runs.
local function marker()
    return Role.marker() or error('No RogueliteZombieSpawn in the active map ' .. tostring(Role.activeMap()))
end
```

  c) Replace:
```lua
    local center = marker:GetAttribute('SpawnAreaCenter')
    if typeof(center) ~= 'Vector3' then center = marker.Position end
    return center, marker:GetAttribute('SpawnAreaRadius') or 60
```
  with:
```lua
    local m = marker()
    local center = m:GetAttribute('SpawnAreaCenter')
    if typeof(center) ~= 'Vector3' then center = m.Position end
    return center, m:GetAttribute('SpawnAreaRadius') or 60
```

  d) Replace:
```lua
    local blockers = workspace:FindFirstChild(marker:GetAttribute('SpawnBlockerFolder') or 'MapOneNoClimb')
```
  with:
```lua
    local blockers = Role.find(marker():GetAttribute('SpawnBlockerFolder') or 'MapOneNoClimb')
```

  e) Replace:
```lua
    local exclude = {folder, warnings, marker, workspace:FindFirstChild("Zombie_R15_ProvidedTextures_Studio")}
```
  with:
```lua
    local exclude = {folder, warnings, marker(), workspace:FindFirstChild("Zombie_R15_ProvidedTextures_Studio")}
```

  f) Replace:
```lua
    table.insert(rayExclude, workspace:FindFirstChild(marker:GetAttribute('SpawnBoundaryModel') or 'MapOneBoundary'))
```
  with:
```lua
    table.insert(rayExclude, Role.find(marker():GetAttribute('SpawnBoundaryModel') or 'MapOneBoundary'))
```

  g) Replace:
```lua
local position = spawnPosition or marker.Position + Vector3.new(math.cos(angle) * 10, 0, math.sin(angle) * 10)
```
  with:
```lua
local position = spawnPosition or marker().Position + Vector3.new(math.cos(angle) * 10, 0, math.sin(angle) * 10)
```

  h) Replace:
```lua
groundParams.FilterDescendantsInstances = {folder, marker, workspace:FindFirstChild("Zombie_R15_ProvidedTextures_Studio")}
```
  with:
```lua
groundParams.FilterDescendantsInstances = {folder, marker(), workspace:FindFirstChild("Zombie_R15_ProvidedTextures_Studio")}
```

  i) Replace:
```lua
    npc:PivotTo(CFrame.new(position) * marker.CFrame.Rotation)
```
  with:
```lua
    npc:PivotTo(CFrame.new(position) * marker().CFrame.Rotation)
```

  j) Replace:
```lua
    params.FilterDescendantsInstances = {folder, target.Parent, marker}
```
  with:
```lua
    params.FilterDescendantsInstances = {folder, target.Parent, marker()}
```

  Then confirm no bare `marker` use is left:

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/studio-prototype" && grep -n -E "marker[^(]|marker$" RogueliteZombieChase.server.luau | grep -v -E "^\S+:\s*--|local function marker\(\)|marker's"
```

  Expected: no output.

- [ ] **Step 3: Edit `hammer-boss/BossEncounter.server.luau`.**

  a) Replace:
```lua
local RS=game:GetService('ReplicatedStorage')
local B=require(script.Parent:WaitForChild('BossService'))
```
  with:
```lua
local RS=game:GetService('ReplicatedStorage')
local Role=require(script.Parent:WaitForChild('ServerRole'))
-- Lobby servers run no waves (ServerRole).
if Role.get()=='Lobby' then return end
local B=require(script.Parent:WaitForChild('BossService'))
```

  b) Replace:
```lua
local Motion=require(combat:WaitForChild('BossMotion'))
```
  with:
```lua
local Motion=require(combat:WaitForChild('BossMotion'))
local Maps=require(combat:WaitForChild('MapConfig'))
```

  c) Replace:
```lua
 local marker=workspace:FindFirstChild('RogueliteZombieSpawn');if not marker then return end
```
  with:
```lua
 -- Only maps with the Hammer boss spawn it (MapConfig); Beach Cove is won by clearing wave 20.
 local map=Maps.get(Role.activeMap());if not map or map.boss~='Hammer' then return end
 local marker=Role.marker();if not marker then return end
```

- [ ] **Step 4: Parse-check both files** (stylua runs from the repo, where rokit finds it):

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && for f in studio-prototype/RogueliteZombieChase.server.luau hammer-boss/BossEncounter.server.luau; do ~/.rokit/bin/stylua --check "$f" 2>&1 | grep -i "error parsing" && echo "PARSE ERROR $f" || echo "ok $f"; done
```

  Expected: `ok` for both.

- [ ] **Step 5: Sync both to Studio.** In Edit:

```lua
sync(SSS.RogueliteZombieChase,'studio-prototype/RogueliteZombieChase.server.luau')
sync(SSS.BossEncounter,'hammer-boss/BossEncounter.server.luau')
return 'synced'
```

- [ ] **Step 6: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/RogueliteZombieChase.server.luau roguelite-planning/hammer-boss/BossEncounter.server.luau && git commit -q -m "$(printf 'Spawn enemies and the boss from the active map\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 5: Combat ray filter and the lobby server respect the role

**Files:**
- Modify: `studio-prototype/combat/RogueliteCombat.server.luau` (the `Shop` require line; `rayParams`)
- Modify: `studio-prototype/lobby/RogueliteLobbyPreview.server.luau` (lines 11-12, 20-21, `areaSpawn`, `travelRemote`, the START branch, `attach`)

- [ ] **Step 1: Check that Studio matches the repo.** In Edit:

```lua
return tostring(same(SSS.RogueliteCombat,'studio-prototype/combat/RogueliteCombat.server.luau'))..' '..tostring(same(SSS.RogueliteLobbyPreview,'studio-prototype/lobby/RogueliteLobbyPreview.server.luau'))
```

  Expected: `true true`.

- [ ] **Step 2: Edit `RogueliteCombat.server.luau`.**

  a) Replace:
```lua
local Shop=require(script.Parent:WaitForChild('ShopService'))
```
  with:
```lua
local Shop=require(script.Parent:WaitForChild('ShopService'))
local Role=require(script.Parent:WaitForChild('ServerRole'))
```

  b) Replace:
```lua
 for _,name in {'RogueliteWeaponShowcase','RogueliteWeaponShowcase_PlaySize','RogueliteZombieSpawn'} do
  local f=workspace:FindFirstChild(name);if f then table.insert(filter,f) end
 end
```
  with:
```lua
 for _,name in {'RogueliteWeaponShowcase','RogueliteWeaponShowcase_PlaySize'} do
  local f=workspace:FindFirstChild(name);if f then table.insert(filter,f) end
 end
 local marker=Role.marker();if marker then table.insert(filter,marker) end
```

- [ ] **Step 3: Edit `RogueliteLobbyPreview.server.luau`.**

  a) Replace:
```lua
local RS=game:GetService('ReplicatedStorage')
local root=workspace:WaitForChild('RogueliteLobby')
```
  with:
```lua
local RS=game:GetService('ReplicatedStorage')
-- Match servers have no lobby: ServerRole parks it.
local Role=require(SSS:WaitForChild('ServerRole'))
if Role.get()=='Match' then return end
local root=workspace:WaitForChild('RogueliteLobby')
```

  b) Replace:
```lua
local lobbySpawn=root:WaitForChild('LobbySpawn');lobbySpawn.Enabled=false -- placed by script, never picked by Roblox
local arenaSpawn=workspace:WaitForChild('SpawnLocation')
```
  with:
```lua
-- Lobby servers spawn players here; the combined Studio preview places them by script instead.
local lobbySpawn=root:WaitForChild('LobbySpawn');lobbySpawn.Enabled=Role.get()=='Lobby'
```

  c) Replace:
```lua
 local base=area=='Lobby' and lobbySpawn.Position or arenaSpawn.Position
```
  with:
```lua
 local base=area=='Lobby' and lobbySpawn.Position or Role.playerSpawn().Position
```

  d) Replace:
```lua
travelRemote.OnServerEvent:Connect(function(player,area)
 if area~='Lobby' and area~='Arena' then return end
```
  with:
```lua
travelRemote.OnServerEvent:Connect(function(player,area)
 if Role.get()~='Combined' or (area~='Lobby' and area~='Arena') then return end
```

  e) Replace:
```lua
 if action=='Start' or action=='Play' then
  local mapOk,mapWhy=Rules.validMap(player,a,e);if not mapOk then return reply(false,mapWhy) end
```
  with:
```lua
 if action=='Start' or action=='Play' then
  -- Lobby servers send parties to match servers (plan C); Studio can't teleport.
  if Role.get()=='Lobby' then return reply(false,'Runs start in the published game. Use the combined Studio mode to play here') end
  local mapOk,mapWhy=Rules.validMap(player,a,e);if not mapOk then return reply(false,mapWhy) end
```

  f) Replace:
```lua
 player:SetAttribute('StudioArea',root:GetAttribute('StudioStartArea')=='Lobby' and 'Lobby' or 'Arena')
```
  with:
```lua
 player:SetAttribute('StudioArea',(Role.get()=='Lobby' or root:GetAttribute('StudioStartArea')=='Lobby') and 'Lobby' or 'Arena')
```

  Confirm `arenaSpawn` is gone:

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/studio-prototype" && grep -c "arenaSpawn" lobby/RogueliteLobbyPreview.server.luau
```

  Expected: `0`.

- [ ] **Step 4: Parse-check.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && for f in studio-prototype/combat/RogueliteCombat.server.luau studio-prototype/lobby/RogueliteLobbyPreview.server.luau; do ~/.rokit/bin/stylua --check "$f" 2>&1 | grep -i "error parsing" && echo "PARSE ERROR $f" || echo "ok $f"; done
```

  Expected: `ok` for both.

- [ ] **Step 5: Sync both to Studio.** In Edit:

```lua
sync(SSS.RogueliteCombat,'studio-prototype/combat/RogueliteCombat.server.luau')
sync(SSS.RogueliteLobbyPreview,'studio-prototype/lobby/RogueliteLobbyPreview.server.luau')
return 'synced'
```

- [ ] **Step 6: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/combat/RogueliteCombat.server.luau roguelite-planning/studio-prototype/lobby/RogueliteLobbyPreview.server.luau && git commit -q -m "$(printf 'Lobby server and combat rays follow the server role and active map\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 6: Lobby client scripts stay out of match servers

**Files:**
- Modify: `studio-prototype/ui/RogueliteLobbyHUD.client.luau` (after line 5)
- Modify: `studio-prototype/lobby/RogueliteLobbyPreview.client.luau` (before the travel switch)
- Create: `studio-prototype/lobby/RogueliteLobbyPortalEnergy.client.luau`, exported from Studio and then guarded

- [ ] **Step 1: Check that Studio matches the repo** for the two scripts the repo already has. In Edit:

```lua
local sps=game.StarterPlayer.StarterPlayerScripts
return tostring(same(sps.RogueliteLobbyHUD,'studio-prototype/ui/RogueliteLobbyHUD.client.luau'))..' '..tostring(same(sps.RogueliteLobbyPreview,'studio-prototype/lobby/RogueliteLobbyPreview.client.luau'))
```

  Expected: `true true`.

- [ ] **Step 2: Export the portal script into the repo.** In Edit:

```lua
return game.StarterPlayer.StarterPlayerScripts.RogueliteLobbyPortalEnergy.Source
```

  Write the returned text, unchanged, to `studio-prototype/lobby/RogueliteLobbyPortalEnergy.client.luau`. It is 48 lines and starts with `-- Animates the lobby portals' energy`.

- [ ] **Step 3: Guard `RogueliteLobbyHUD.client.luau`.** Replace:
```lua
local player=Players.LocalPlayer
```
  with:
```lua
local player=Players.LocalPlayer
-- Match servers have no lobby (ServerRole sets this attribute before players join).
local role=ReplicatedStorage:GetAttribute('ServerRole')
while role==nil do ReplicatedStorage:GetAttributeChangedSignal('ServerRole'):Wait();role=ReplicatedStorage:GetAttribute('ServerRole') end
if role=='Match' then return end
```

- [ ] **Step 4: Limit the travel switch to Combined** in `RogueliteLobbyPreview.client.luau`. Replace:
```lua
local travel=workspace:WaitForChild('RogueliteLobby'):WaitForChild('StudioTravel')
```
  with:
```lua
-- The switch only exists where the lobby and the maps share one server (ServerRole).
local RS=game:GetService('ReplicatedStorage')
local role=RS:GetAttribute('ServerRole')
while role==nil do RS:GetAttributeChangedSignal('ServerRole'):Wait();role=RS:GetAttribute('ServerRole') end
if role~='Combined' then return end
local travel=workspace:WaitForChild('RogueliteLobby'):WaitForChild('StudioTravel')
```

- [ ] **Step 5: Guard the portal script.** In `RogueliteLobbyPortalEnergy.client.luau`, replace:
```lua
local RunService = game:GetService('RunService')
local root = workspace:WaitForChild('RogueliteLobby')
```
  with:
```lua
local RunService = game:GetService('RunService')
-- Match servers have no lobby (ServerRole).
local RS = game:GetService('ReplicatedStorage')
local role = RS:GetAttribute('ServerRole')
while role == nil do RS:GetAttributeChangedSignal('ServerRole'):Wait(); role = RS:GetAttribute('ServerRole') end
if role == 'Match' then return end
local root = workspace:WaitForChild('RogueliteLobby')
```

- [ ] **Step 6: Parse-check.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && for f in studio-prototype/ui/RogueliteLobbyHUD.client.luau studio-prototype/lobby/RogueliteLobbyPreview.client.luau studio-prototype/lobby/RogueliteLobbyPortalEnergy.client.luau; do ~/.rokit/bin/stylua --check "$f" 2>&1 | grep -i "error parsing" && echo "PARSE ERROR $f" || echo "ok $f"; done
```

  Expected: `ok` three times.

- [ ] **Step 7: Sync all three.** In Edit:

```lua
local sps=game.StarterPlayer.StarterPlayerScripts
sync(sps.RogueliteLobbyHUD,'studio-prototype/ui/RogueliteLobbyHUD.client.luau')
sync(sps.RogueliteLobbyPreview,'studio-prototype/lobby/RogueliteLobbyPreview.client.luau')
sync(sps.RogueliteLobbyPortalEnergy,'studio-prototype/lobby/RogueliteLobbyPortalEnergy.client.luau')
return 'synced'
```

- [ ] **Step 8: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/ui/RogueliteLobbyHUD.client.luau roguelite-planning/studio-prototype/lobby/RogueliteLobbyPreview.client.luau roguelite-planning/studio-prototype/lobby/RogueliteLobbyPortalEnergy.client.luau && git commit -q -m "$(printf 'Keep lobby client scripts out of match servers\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 7: ApplyPropCollision finds props in the new folders

**Files:**
- Modify: `studio-prototype/ApplyPropCollision.luau` (lines 107-108, 115, 146)

This is an Edit tool that nothing installs. **Don't run it**; only fix its lookups.

- [ ] **Step 1: Edit.**

  a) Replace:
```lua
-- First arena (Pine Valley): loose top-level props on the grass, x < 400, above y = -60.
local mapOne=workspace:FindFirstChild('MapOneNoClimb')
```
  with:
```lua
-- First arena (Pine Valley): props in Workspace.PineValleyArena on the grass, x < 400, above y = -60.
local pineArea=workspace:FindFirstChild('PineValleyArena') or workspace
local mapOne=pineArea:FindFirstChild('MapOneNoClimb')
```

  b) Replace:
```lua
 for _,c in workspace:GetChildren() do
  if (c:IsA('Model') or c:IsA('MeshPart')) and matches(c.Name,ARENA_BOXED) then
```
  with:
```lua
 for _,c in pineArea:GetChildren() do
  if (c:IsA('Model') or c:IsA('MeshPart')) and matches(c.Name,ARENA_BOXED) then
```

  c) Replace:
```lua
 for _,c in workspace:GetChildren() do if c:IsA('MeshPart') then table.insert(candidates,c) end end
```
  with:
```lua
 -- Hand-placed props sit in BeachCoveExtras.Props (GroupMapAreas), outside the rebuilt arena folder.
 local extras=workspace:FindFirstChild('BeachCoveExtras');local looseProps=extras and extras:FindFirstChild('Props')
 for _,c in (looseProps or workspace):GetChildren() do if c:IsA('MeshPart') then table.insert(candidates,c) end end
```

- [ ] **Step 2: Parse-check.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && ~/.rokit/bin/stylua --check studio-prototype/ApplyPropCollision.luau 2>&1 | grep -i "error parsing" && echo PARSE ERROR || echo ok
```

  Expected: `ok`.

- [ ] **Step 3: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/ApplyPropCollision.luau && git commit -q -m "$(printf 'Point ApplyPropCollision at the grouped map folders\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 8: Verify every role in Play

**Files:** none (verification). Before **each** Play: `list_sessions` + `get_studio_state`, as in Conventions. After each check: `get_console_output` must show no new errors, and **stop Play**.

- [ ] **Step 1: Combined (default).** In Edit, confirm `workspace:GetAttribute('StudioServerRole')==nil`. Start Play, wait for the player, then run in **Server**:

```lua
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat
local Catalog=require(combat.EnemyCatalog)
local r={}
local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
local char=p.Character or p.CharacterAdded:Wait()
add(RS:GetAttribute('ServerRole')=='Combined','role Combined')
for _,n in {'RogueliteLobby','PineValleyArena','BeachCoveArena','BeachCoveExtras'} do add(workspace:FindFirstChild(n)~=nil,n..' in Workspace') end
add(combat:GetAttribute('RunMap')=='PineValley','RunMap defaults to PineValley')
add(workspace.PineValleyArena.PlayerSpawn.Enabled and not workspace.BeachCoveExtras.PlayerSpawn.Enabled,'only the Pine spawn is enabled')
add(combat:GetAttribute('EnemyRoster')==nil,'Pine Valley keeps the default roster')
combat:SetAttribute('RunMap','BeachCove');task.wait(.3)
add(workspace.BeachCoveExtras.PlayerSpawn.Enabled and not workspace.PineValleyArena.PlayerSpawn.Enabled,'RunMap swaps the enabled spawn')
add(combat:GetAttribute('EnemyRoster')=='crab,snake,crab,hermit-crab,crab,rock-throwing-crab','Beach roster applied')
char:PivotTo(CFrame.new(workspace.BeachCoveExtras.PlayerSpawn.Position+Vector3.new(0,4,0)));task.wait(.5)
combat:SetAttribute('ZombiesEnabled',true);task.wait(5)
local roster={crab=true,snake=true,['hermit-crab']=true,['rock-throwing-crab']=true}
local n,bad,far=0,0,0
for _,npc in workspace.RogueliteEnemies:GetChildren() do
 if npc:IsA('Model') then n+=1
  local d=Catalog.fromModel(npc);if not d or not roster[d.id] then bad+=1 end
  local pos=npc:GetPivot().Position;if (Vector3.new(pos.X,0,pos.Z)-Vector3.new(700,0,300)).Magnitude>100 then far+=1 end
 end
end
add(n>0,'Beach enemies spawned ('..n..')');add(bad==0,'all enemies are Beach Cove types ('..bad..' wrong)');add(far==0,'all enemies inside the Beach ring ('..far..' outside)')
combat:SetAttribute('ZombiesEnabled',false);combat:SetAttribute('RunMap','PineValley');task.wait(.3)
add(workspace.PineValleyArena.PlayerSpawn.Enabled and combat:GetAttribute('EnemyRoster')==nil,'back to Pine Valley')
return table.concat(r,'\n')
```

  Expected: every line `PASS`. Stop Play.

- [ ] **Step 2: Lobby.** In Edit: `workspace:SetAttribute('StudioServerRole','Lobby')`. Start Play, then run in **Server**:

```lua
local RS,SS=game.ReplicatedStorage,game.ServerStorage
local r={}
local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
local t0=os.clock();while not p:GetAttribute('LobbyPreviewActive') and os.clock()-t0<8 do task.wait(.2) end
add(RS:GetAttribute('ServerRole')=='Lobby','role Lobby')
add(workspace:FindFirstChild('RogueliteLobby')~=nil,'lobby in Workspace')
for _,n in {'PineValleyArena','BeachCoveArena','BeachCoveExtras'} do add(SS.InactiveAreas:FindFirstChild(n)~=nil,n..' parked') end
add(workspace.RogueliteLobby.LobbySpawn.Enabled,'LobbySpawn enabled')
add(p:GetAttribute('StudioArea')=='Lobby' and p:GetAttribute('LobbyPreviewActive')==true,'player is in the lobby')
add(workspace:FindFirstChild('RogueliteEnemies')==nil,'no wave spawner in the lobby')
return table.concat(r,'\n')
```

  Then run in **Client**:

```lua
local gui=game.Players.LocalPlayer.PlayerGui
local remote=workspace.RogueliteLobby:WaitForChild('RunSetup')
local got;local c=remote.OnClientEvent:Connect(function(k,ok,m) if k=='Result' then got={ok,m} end end)
task.wait(.4);remote:FireServer('Play','PineValley','Brawler','01',true,'Normal')
local t0=os.clock();while not got and os.clock()-t0<3 do task.wait(.05) end;c:Disconnect()
return 'lobbyHUD='..tostring(gui:FindFirstChild('RogueliteLobbyHUD')~=nil)..' travelSwitch='..tostring(gui:FindFirstChild('StudioTravel')~=nil)..' play='..(got and (tostring(got[1])..' '..got[2]) or 'no reply')
```

  Expected: every server line `PASS`. Client: `lobbyHUD=true travelSwitch=false play=false Runs start in the published game. Use the combined Studio mode to play here`. Stop Play.

- [ ] **Step 3: Match on Beach Cove.** In Edit: `workspace:SetAttribute('StudioServerRole','Match');workspace:SetAttribute('StudioMatchMap','BeachCove')`. Start Play, then run in **Server**:

```lua
local RS,SS=game.ReplicatedStorage,game.ServerStorage;local combat=RS.RogueliteCombat;local run=RS.RogueliteRunState
local r={}
local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
local char=p.Character or p.CharacterAdded:Wait();task.wait(1)
add(RS:GetAttribute('ServerRole')=='Match','role Match')
for _,n in {'RogueliteLobby','PineValleyArena'} do add(SS.InactiveAreas:FindFirstChild(n)~=nil,n..' parked') end
for _,n in {'BeachCoveArena','BeachCoveExtras'} do add(workspace:FindFirstChild(n)~=nil,n..' in Workspace') end
add(combat:GetAttribute('RunMap')=='BeachCove' and combat:GetAttribute('RunDifficulty')=='Normal','RunMap BeachCove, Normal')
add(workspace.BeachCoveExtras.PlayerSpawn.Enabled,'Beach spawn enabled')
local pos=char:GetPivot().Position
add((Vector3.new(pos.X,0,pos.Z)-Vector3.new(700,0,300)).Magnitude<110,'player spawned on the beach')
combat:SetAttribute('ZombiesEnabled',true);task.wait(3)
combat:SetAttribute('HammerBossWave',run:GetAttribute('Wave'));combat:SetAttribute('ZombiesEnabled',false);task.wait(.2);combat:SetAttribute('ZombiesEnabled',true);task.wait(2)
local boss=false;for _,npc in workspace.RogueliteEnemies:GetChildren() do if npc:GetAttribute('IsHammerBoss') then boss=true end end
add(not boss and run:GetAttribute('BossAlive')~=true,'no Hammer boss on Beach Cove')
combat:SetAttribute('ZombiesEnabled',false);combat:SetAttribute('HammerBossWave',nil)
return table.concat(r,'\n')
```

  Then run in **Client**:

```lua
local gui=game.Players.LocalPlayer.PlayerGui
return 'lobbyHUD='..tostring(gui:FindFirstChild('RogueliteLobbyHUD')~=nil)..' travelSwitch='..tostring(gui:FindFirstChild('StudioTravel')~=nil)
```

  Expected: every server line `PASS`. Client: `lobbyHUD=false travelSwitch=false`. `get_console_output` must show no `Infinite yield` on `RogueliteLobby`. Stop Play.

- [ ] **Step 4: Match on Pine Valley (boss check).** In Edit: `workspace:SetAttribute('StudioMatchMap','PineValley')`. Start Play, then run in **Server**:

```lua
local RS,SS=game.ReplicatedStorage,game.ServerStorage;local combat=RS.RogueliteCombat;local run=RS.RogueliteRunState
local r={}
local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
local char=p.Character or p.CharacterAdded:Wait();task.wait(1)
for _,n in {'RogueliteLobby','BeachCoveArena','BeachCoveExtras'} do add(SS.InactiveAreas:FindFirstChild(n)~=nil,n..' parked') end
add(workspace:FindFirstChild('PineValleyArena')~=nil and combat:GetAttribute('RunMap')=='PineValley','Pine Valley active')
local pos=char:GetPivot().Position
add((pos-workspace.PineValleyArena.PlayerSpawn.Position).Magnitude<40,'player spawned at the Pine Valley spawn')
combat:SetAttribute('HammerBossWave',run:GetAttribute('Wave'));combat:SetAttribute('ZombiesEnabled',true);task.wait(3)
local boss=false;for _,npc in workspace.RogueliteEnemies:GetChildren() do if npc:GetAttribute('IsHammerBoss') then boss=true end end
add(boss and run:GetAttribute('BossAlive')==true,'Hammer boss spawns on Pine Valley')
combat:SetAttribute('ZombiesEnabled',false);combat:SetAttribute('HammerBossWave',nil)
return table.concat(r,'\n')
```

  Expected: every line `PASS`. Stop Play.

- [ ] **Step 5: Reset the Studio test attributes** (they persist in the place file). In Edit:

```lua
for _,a in {'StudioServerRole','StudioMatchMap','StudioMatchDifficulty'} do workspace:SetAttribute(a,nil) end
return tostring(workspace:GetAttribute('StudioServerRole'))
```

  Expected: `nil`.

- [ ] **Step 6: Re-run the katana check in Combined** (the earlier fix must survive). Start Play and run in **Server**:

```lua
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
local f=game.ReplicatedStorage.RogueliteCombat.PlayerStates:WaitForChild(tostring(p.UserId),10)
return 'slot1='..tostring(f and f.Slot1:GetAttribute('WeaponId'))
```

  Expected: `slot1=01`. Stop Play.

- [ ] **Step 7: If any check failed:** use superpowers:systematic-debugging. Fix it in the repo, re-sync, and re-run **that** step. Don't mark the task done with a `FAIL` line.

---

### Task 9: Document where things live

**Files:**
- Modify: `LOBBY_AND_MATCH_SERVERS.md` (§9 table, last row)

- [ ] **Step 1: Update the spec's Workspace row.** Replace the last row of the §9 table, the one starting `| Workspace (Edit, one time) |`, with:

```markdown
| Workspace (done 2026-09-28, `lobby/GroupMapAreas.luau`) | Pine Valley lives in `Workspace.PineValleyArena`. Beach Cove is `BeachCoveArena` (rebuilt by its kit) plus `BeachCoveExtras` (PlayerSpawn, RogueliteZombieSpawn, hand-placed `Props`). **New map props go inside their map folder**; anything left loose in Workspace shows up on every server. Only the active map's `PlayerSpawn` is enabled (ServerRole). Studio: `Workspace.StudioServerRole` = `Lobby` / `Match` (with `StudioMatchMap`, `StudioMatchDifficulty`), unset = Combined. |
```

- [ ] **Step 2: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/LOBBY_AND_MATCH_SERVERS.md && git commit -q -m "$(printf 'Document map folders and Studio role attributes\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

- [ ] **Step 3: Stop the local file server** started in Task 0.

- [ ] **Step 4: Report to the user.** Keep it short and plain:
  - The roles work in Studio, with the Task 8 PASS lines as evidence.
  - Beach Cove now spawns its own enemies inside its ring, with no boss.
  - Players spawn on the chosen map.
  - Not yet possible: real teleports between servers (plan C) and the win, spectate and revive flow (plan B).
