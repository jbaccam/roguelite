# Plan D: Admin Panel

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One developer-only **ADMIN** panel (P, or an ADMIN button in the arena and lobby HUDs) with Travel, Mobs, Waves and Player tabs. It works in Studio and in the published game for listed UserIds only, the server checks every request, and any run where it was used pays no rewards. It replaces the Studio-only STATS panel, GEAR inventory and Z/K/X test panel for developers. A play-test that never touches it behaves exactly as before.

**Architecture:**
- `AdminConfig` (new, sandboxed, `ReplicatedStorage.RogueliteCombat`): developer UserIds, `isAdmin`, the test-run guard (`isTestRun`, `markTestRun`) and one argument rule per admin action (`check`).
- `AdminService` (new unsandboxed Script): owns the `AdminAction` RemoteFunction. It checks the developer, a rate limit and the arguments, then routes to:
  - `ShopService`: sandbox, waves and grants.
  - `ServerRole`: travel.
  - `ServerStorage.AdminSpawn`: a BindableFunction in `RogueliteZombieChase` for extra enemies, Clear and Freeze.
- Existing remotes stay: `EditPractice` (class, stats, heal, emeralds) and `EquipWeapon` (give weapon). Their `IsStudio()` gates become developer checks.
- God mode is one check in `CharacterService.contact`, which every player-damage path already calls.
- `ShopService.resetRun` clears the test-run flag and all admin state, so a new run is clean.
- Client: `AdminPanelUI` (window + tabs, embedding `CharacterStatsUI` and `WeaponInventoryUI`) and `AdminPanel.client` (button + P). `RogueliteUI` loses STATS and GEAR in the same task.

**Tech stack:** Roblox Luau; Roblox Studio via the Studio MCP (`execute_luau`, `start_stop_play`, `get_console_output`, plain `screen_capture`); a local Python HTTP server for syncing repo files into Studio; stylua for parse checks; Rojo project JSON for packaging.

**Spec:** `roguelite-planning/ADMIN_PANEL.md` (approved 2026-09-28). Builds on plan A (`ServerRole`, `MapConfig`, map folders). Plan B (run-end rewards) must check `AdminConfig.isTestRun()` too. Plan C (teleports) will enable Travel on published servers.

---

## Conventions (read before any task)

**Paths.** Repo paths are relative to `C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/`. Studio paths are DataModel paths. `SSS` = ServerScriptService, `RS` = ReplicatedStorage, `SPS` = StarterPlayer.StarterPlayerScripts.

| Repo file | Studio instance |
|---|---|
| `studio-prototype/combat/AdminConfig.luau` (new) | `RS.RogueliteCombat.AdminConfig` (ModuleScript, **Sandboxed**, Capabilities copied from `CharacterStats`) |
| `studio-prototype/combat/AdminConfigTests.luau` (new) | `ServerStorage.RogueliteTests.AdminConfigTests` (ModuleScript) |
| `studio-prototype/combat/AdminService.server.luau` (new) | `SSS.AdminService` (Script, **unsandboxed**) |
| `studio-prototype/ui/AdminPanelUI.luau` (new) | `RS.AdminPanelUI` (ModuleScript, **unsandboxed**) |
| `studio-prototype/ui/AdminPanel.client.luau` (new) | `SPS.AdminPanel` (LocalScript, **unsandboxed**) |
| `studio-prototype/combat/CharacterService.luau` | `SSS.CharacterService` |
| `studio-prototype/combat/ShopService.luau` | `SSS.ShopService` |
| `studio-prototype/combat/RogueliteCombat.server.luau` | `SSS.RogueliteCombat` |
| `studio-prototype/combat/RogueliteCombat.client.luau` | `SPS.RogueliteCombat` |
| `studio-prototype/RogueliteZombieChase.server.luau` | `SSS.RogueliteZombieChase` |
| `hammer-boss/BossService.luau` | `SSS.BossService` |
| `studio-prototype/combat/ProfileService.luau` | `SSS.ProfileService` |
| `studio-prototype/combat/LeaderboardService.server.luau` | `SSS.LeaderboardService` |
| `studio-prototype/combat/RogueliteMeta.server.luau` | `SSS.RogueliteMeta` |
| `studio-prototype/ui/RogueliteUI.luau` | `RS.RogueliteUI` |
| `studio-prototype/ui/RogueliteHUD.client.luau` | `SPS.RogueliteHUD` |
| `studio-prototype/ui/CharacterStatsUI.luau` | `RS.CharacterStatsUI` |
| `studio-prototype/ui/WeaponInventoryUI.luau` | `RS.WeaponInventoryUI` |
| `studio-prototype/ui/LobbyUI.luau` | `RS.LobbyUI` |
| `studio-prototype/lobby/RogueliteLobbyPreview.client.luau` | `SPS.RogueliteLobbyPreview` |
| `studio-prototype/combat/default.project.json` | Rojo project (no Studio instance) |

**Sandboxing** (it has broken this place twice). A sandboxed script can only require sandboxed modules. An unsandboxed script can require both kinds.
- **Sandboxed:** RogueliteCombat (server and client), CharacterService, ShopService, CombatEffectsService, ShardDropService, HeartDropService, CharacterStats, EnemyCatalog, WeaponCatalog, MapConfig, ServerRole, and the data modules ShopService loads (ShopCatalog, EconomyConfig, RunXP). Task 0 confirms these.
- **Unsandboxed:** RogueliteZombieChase, BossEncounter, BossService, RogueliteLobbyPreview, RogueliteMeta, ProfileService, AvatarNormalizer, EnemyAttacks, RunSetupRules, ChestConfig, and the lobby/HUD UI modules in ReplicatedStorage.
- A new module that sandboxed code requires is created with `create(..., capsFrom)`, which sets `Sandboxed=true` and copies Capabilities. Other new scripts are created without `capsFrom` and stay unsandboxed.
- Rojo project entries do not carry `Sandboxed`. Studio is the source of truth for that property.

Every new `require` in this plan, and why it is allowed:

| Requirer (kind) | Requires (kind) | Why it's allowed |
|---|---|---|
| AdminConfig (S) | EnemyCatalog, ShopCatalog, MapConfig, EconomyConfig, RunXP (all S) | Sandboxed → sandboxed. Task 0 Step 5 checks all five. |
| CharacterService, RogueliteCombat server + client (S) | AdminConfig (S) | Sandboxed → sandboxed. |
| ShopService (S) | MapConfig (S) | Sandboxed → sandboxed. |
| ProfileService, RogueliteMeta, BossService, RogueliteLobbyPreview.client, CharacterStatsUI (U) | AdminConfig (S) | Unsandboxed may require sandboxed. |
| LeaderboardService (either) | AdminConfig (S) | A sandboxed module is fine either way. |
| RogueliteZombieChase (U) | BossService (U), BossMotion | Unsandboxed may require both. ZombieChase already requires the unsandboxed RunSetupRules, so it can't be sandboxed. |
| AdminService (U, new) | AdminConfig, MapConfig, ServerRole, ShopService (S) | Unsandboxed may require sandboxed. |
| AdminPanelUI, AdminPanel.client (U, new) | UITheme, CharacterStatsUI, WeaponInventoryUI, RunSetupRules (U), AdminConfig, MapConfig, EnemyCatalog, ShopCatalog (S) | Unsandboxed may require both kinds. |

**Never** add a require of an unsandboxed module (RunSetupRules, BossService, ProfileService, UI modules) to a sandboxed script.

**Load order** (it deadlocked the server once): modules that ShopService or CharacterService require must not `WaitForChild('RogueliteRunState')` at load, because ShopService creates that folder. `AdminConfig` looks the folder up lazily inside functions. The spawner's resume hook waits for it inside `task.spawn`.

**Shared Studio.** The user runs several Claude sessions against one Studio and uses the PC at the same time.
- Every Studio MCP call needs `studio_id`. Get it from `list_roblox_studios` (the roguelite place, 107877054949326).
- Before every `start_stop_play`, call `list_sessions` and `get_studio_state`. If Studio is already in Play and you didn't start it, don't touch Play: wait, or ask the user.
- Never use a positioned `screen_capture`. Only use plain captures with no camera arguments.
- Don't type into Studio with keyboard tools. Checks open the panel through its Studio test hook instead.
- Always stop Play when a check is finished.

**Local file server.** Start it once, in the background, in Task 0:

```bash
python -m http.server 8765 --bind 127.0.0.1 --directory "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning"
```

**Studio helper (Edit).** Paste this block at the top of every Edit-mode `execute_luau` call that syncs or tests:

```lua
local RS,SSS,SS=game:GetService('ReplicatedStorage'),game:GetService('ServerScriptService'),game:GetService('ServerStorage')
local SPS=game:GetService('StarterPlayer').StarterPlayerScripts
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

**Play checks.** Every check prints `PASS …` / `FAIL …` lines. **Expected: every line `PASS`.** A `FAIL` stops the task: use superpowers:systematic-debugging, fix the repo file, re-sync and re-run that step.
- **Client** checks run with `datamodel_type: Client`. They use remotes, replicated attributes and PlayerGui only.
- **Server** checks that only read or write attributes, workspace and `ServerStorage.AdminSpawn` run with `datamodel_type: Server`.
- **Server checks that need a service's internals** (ShopService, CharacterService, ProfileService) go through `serverCheck` below. **Never `require` a stateful service straight from `execute_luau`.** That code runs in its own Luau VM, so the require boots a *second* copy of the module, with its own Heartbeat and remote connections. `ServerRole` even guards against this ("a command-bar require").

Paste this at the top of those Server calls:

```lua
-- Runs body as a temporary Script in the running server, so it shares the game's module copies.
-- body uses add(ok, message). Returns the PASS/FAIL lines.
local function serverCheck(body)
 local s=Instance.new('Script');s.Name='PlanDCheck'
 s.Source="local r={};local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end\nlocal ran,err=pcall(function()\n"..body.."\nend)\nif not ran then add(false,'error: '..tostring(err)) end\nscript:SetAttribute('Result',table.concat(r,'\\n'))"
 s.Parent=game:GetService('ServerScriptService')
 local t0=os.clock();while s:GetAttribute('Result')==nil and os.clock()-t0<45 do task.wait(.25) end
 local out=s:GetAttribute('Result') or 'TIMEOUT: read get_console_output for PlanDCheck'
 s:Destroy();return out
end
```

If the first `serverCheck` returns `TIMEOUT` and the console shows nothing from `PlanDCheck`, this Studio isn't running scripts created during Play. Use this fallback instead:
1. Stop Play.
2. In Edit, create `SSS.PlanDCheck` (a Script with `Disabled=true`) whose Source is the same wrapper.
3. Start Play. From the Server datamodel, set `Disabled=false` and read its `Result` attribute.
4. Stop Play and delete the Script in Edit.

After every Play check, run `get_console_output`. It must show:
- no new errors;
- no line containing `capability`, `Sandboxed` or `cannot require`;
- no `Infinite yield` naming `RogueliteRunState`, `AdminConfig`, `AdminAction` or `AdminSpawn`.

Then stop Play.

**Editing an existing script.** Before you edit its repo file, run `return same(<instance>,'<repo path>')` in Edit.
- **Expected: `true`.** If it returns `false`, Studio or the repo holds someone else's unsynced edits. Stop and tell the user; don't overwrite either side.
- Make the edits as exact `Replace … with …` blocks. Every "Replace" text is quoted from the file as it is **after the previous tasks of this plan**.
- After editing, parse-check, then run `sync(<instance>,'<repo path>')`.

**Parse check** (stylua runs from the repo, where rokit finds it):

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && for f in <files>; do ~/.rokit/bin/stylua --check "$f" 2>&1 | grep -i "error parsing" && echo "PARSE ERROR $f" || echo "ok $f"; done
```

**Commits.** Commit only the files the task changed, on `main`. Other sessions share this working folder, so never switch branches and never `git add -A`. End every message with:

```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

**Keeping normal play unchanged.** Each change below is inert unless the panel is used. Task 8 Step 8 proves it with a full normal run.

| Change | Why normal play doesn't see it |
|---|---|
| `CharacterService.contact` returns 0 for `AdminGod` | Only AdminService sets `AdminGod`, and `resetRun` clears it. |
| `EditPractice` and `EquipWeapon` need a developer, not Studio | Their only UI (STATS and GEAR) moves into the ADMIN panel in the same plan. Non-developer Studio testers lose STATS/GEAR, and the spec intends that. **Between Tasks 3 and 7** a non-developer Studio account still *sees* the old STATS/GEAR panels, but the server ignores them. The developer's own Studio session keeps working throughout. |
| `ShopService.resetRun` clears admin state and restores the map roster | In normal play those values are already unset, and the roster already equals the map's, so no attribute changes and no signal fires. |
| `beginWave` split into `startWave` | Same statements, same order. |
| Spawner: `AdminPaused` gate, `AdminSpawn` extras kept by `resetWave`, `AdminFreeze` skip | None of these attributes is ever set without the panel. `S.pause` (the solo-death pause) is untouched, and the spawner ignores it as before. |
| Boss: `AdminFreeze`, practice gate | `BossEncounter` still calls `B.spawn(cf,false)`, and Freeze is never set. |
| HUD: Practice display, TEST RUN tag | The Practice display only shows when `Phase=='Practice'`, which only the panel sets. The tag only shows when `AdminTestRun` is set. |
| RogueliteUI: STATS/GEAR gone, and a Practice phase closes menus | STATS/GEAR were Studio-only test tools. Practice never happens without the panel. |
| ProfileService, LeaderboardService, RogueliteMeta death info | Guarded by `AdminTestRun`, which is never set without the panel. ShopService clears it at boot. |
| COMBAT TEST panel (Z/K/X) and LOBBY/ARENA switch hidden | Hidden for developers only. Other Studio testers keep both. |

---

### Task 0: Pre-flight

**Files:** none.

- [ ] **Step 1: Check that no other session has uncommitted work in the files this plan edits.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && git status --short -- studio-prototype/combat/CharacterService.luau studio-prototype/combat/ShopService.luau studio-prototype/combat/RogueliteCombat.server.luau studio-prototype/combat/RogueliteCombat.client.luau studio-prototype/RogueliteZombieChase.server.luau hammer-boss/BossService.luau studio-prototype/combat/ProfileService.luau studio-prototype/combat/LeaderboardService.server.luau studio-prototype/combat/RogueliteMeta.server.luau studio-prototype/ui/RogueliteUI.luau studio-prototype/ui/RogueliteHUD.client.luau studio-prototype/ui/CharacterStatsUI.luau studio-prototype/ui/WeaponInventoryUI.luau studio-prototype/ui/LobbyUI.luau studio-prototype/lobby/RogueliteLobbyPreview.client.luau studio-prototype/combat/default.project.json ADMIN_PANEL.md; echo "status done"
```

  Expected: only `status done`. If any file is listed, stop and ask the user whose change it is.
  - When this plan was written (2026-09-28), another session had uncommitted edits in `studio-prototype/combat/RogueliteCombat.client.luau`. That session must commit first; Task 7 Step 7a edits this file.

- [ ] **Step 2: Start the local file server** (the command in Conventions) in the background. Check it:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/ADMIN_PANEL.md
```

  Expected: `200`.

- [ ] **Step 3: Confirm Studio is idle.** Call `list_roblox_studios` and keep the roguelite place's `studio_id`. Then `get_studio_state` must show `Current Studio Mode: Edit`, and `list_sessions` must show no other session in Play.

- [ ] **Step 4: Confirm the Studio account and the in-memory profiles.** In Edit:

```lua
local ok,id=pcall(function() return game:GetService('StudioService'):GetUserId() end)
local run=game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteRunState')
return 'user='..tostring(ok and id)..' studioDataStores='..tostring(workspace:GetAttribute('EnableStudioDataStores'))..' savedRunState='..tostring(run~=nil)..' savedTestRun='..tostring(run and run:GetAttribute('AdminTestRun'))
```

  Expected: `user=341854066 studioDataStores=nil …`.
  - Any other user id means the panel would never show in this Studio. Stop and ask the user.
  - `studioDataStores=true` means Studio would save real profiles. Stop and ask the user.
  - Record `savedRunState`. Task 2 clears a stale `AdminTestRun` at boot either way.

- [ ] **Step 5: Confirm sandboxing.** In Edit (helper block first):

```lua
local c=RS.RogueliteCombat
local mustBeSandboxed={c.CharacterStats,c.EnemyCatalog,c.ShopCatalog,c.MapConfig,c.EconomyConfig,c.RunXP,c.WeaponCatalog,SSS.CharacterService,SSS.ShopService,SSS.ServerRole,SSS.RogueliteCombat,SPS.RogueliteCombat}
local mustBeOpen={SSS.RogueliteZombieChase,SSS.BossService,SSS.ProfileService,SSS.RogueliteMeta,RS.RunSetupRules}
local bad={}
for _,s in mustBeSandboxed do if not s.Sandboxed then table.insert(bad,s:GetFullName()..' is not sandboxed') end end
for _,s in mustBeOpen do if s.Sandboxed then table.insert(bad,s:GetFullName()..' is sandboxed') end end
return #bad==0 and 'sandboxing as expected' or table.concat(bad,'\n')
```

  Expected: `sandboxing as expected`. Otherwise stop: the require table in Conventions is wrong for this place, and the user must decide before any require is added.

- [ ] **Step 6: Confirm Studio matches the repo** for every script this plan edits. In Edit:

```lua
local list={
 {SSS.CharacterService,'studio-prototype/combat/CharacterService.luau'},
 {SSS.ShopService,'studio-prototype/combat/ShopService.luau'},
 {SSS.RogueliteCombat,'studio-prototype/combat/RogueliteCombat.server.luau'},
 {SPS.RogueliteCombat,'studio-prototype/combat/RogueliteCombat.client.luau'},
 {SSS.RogueliteZombieChase,'studio-prototype/RogueliteZombieChase.server.luau'},
 {SSS.BossService,'hammer-boss/BossService.luau'},
 {SSS.ProfileService,'studio-prototype/combat/ProfileService.luau'},
 {SSS.LeaderboardService,'studio-prototype/combat/LeaderboardService.server.luau'},
 {SSS.RogueliteMeta,'studio-prototype/combat/RogueliteMeta.server.luau'},
 {RS.RogueliteUI,'studio-prototype/ui/RogueliteUI.luau'},
 {SPS.RogueliteHUD,'studio-prototype/ui/RogueliteHUD.client.luau'},
 {RS.CharacterStatsUI,'studio-prototype/ui/CharacterStatsUI.luau'},
 {RS.WeaponInventoryUI,'studio-prototype/ui/WeaponInventoryUI.luau'},
 {RS.LobbyUI,'studio-prototype/ui/LobbyUI.luau'},
 {SPS.RogueliteLobbyPreview,'studio-prototype/lobby/RogueliteLobbyPreview.client.luau'},
}
local out={}
for _,e in list do if not same(e[1],e[2]) then table.insert(out,'DIFFERENT '..e[2]) end end
return #out==0 and 'all 15 match' or table.concat(out,'\n')
```

  Expected: `all 15 match`. If any differ, stop and tell the user which. Each task re-checks its own files before editing, because other sessions keep working.

---

### Task 1: AdminConfig (who is a developer, test runs, request rules)

**Files:**
- Create: `studio-prototype/combat/AdminConfigTests.luau`
- Create: `studio-prototype/combat/AdminConfig.luau`
- Modify: `studio-prototype/combat/default.project.json`

- [ ] **Step 1: Write the failing test.** Create `studio-prototype/combat/AdminConfigTests.luau`:

```lua
-- AdminConfig checks: who is a developer, the test-run guard and every request rule.
-- Run in Studio Edit (plan D, Task 1).
return function(Admin, Enemies, Items)
	local checks = 0
	local function check(condition, message)
		assert(condition, message)
		checks += 1
	end
	local function show(call)
		return tostring(call[1]) .. " " .. tostring(call[2]) .. " " .. tostring(call[3])
	end
	-- Who is a developer: a real Player whose UserId is listed.
	check(Admin.isAdminId(341854066), "EggaRowls is a developer")
	check(not Admin.isAdminId(1) and not Admin.isAdminId(-1) and not Admin.isAdminId(0), "Other ids are not developers")
	check(not Admin.isAdminId("341854066") and not Admin.isAdminId(nil), "Ids must be numbers")
	check(
		not Admin.isAdmin(nil) and not Admin.isAdmin({ UserId = 341854066 }) and not Admin.isAdmin(workspace),
		"Only real Player instances pass"
	)
	-- The test-run guard reads RogueliteRunState.AdminTestRun.
	local run = Instance.new("Folder")
	check(not Admin.isTestRun(run), "A fresh run is not a test run")
	run:SetAttribute("AdminTestRun", true)
	check(Admin.isTestRun(run), "The flag marks a test run")
	run:SetAttribute("AdminTestRun", false)
	check(not Admin.isTestRun(run), "Only true counts")
	run:Destroy()
	check(#Admin.Actions == 15, "15 admin actions, found " .. #Admin.Actions)
	local anEnemy = Enemies.List[1].id
	local anItem
	for _, entry in Items.List do
		if entry.kind ~= "Weapon" then
			anItem = entry.id
			break
		end
	end
	local valid = {
		{ "Travel", "Lobby" },
		{ "Travel", "PineValley" },
		{ "Travel", "BeachCove" },
		{ "Spawn", anEnemy, 5 },
		{ "Spawn", "Hammer", 1 },
		{ "Spawn", anEnemy, 50 },
		{ "KeepAlive", 10, "" },
		{ "KeepAlive", 0, "" },
		{ "KeepAlive", 100, "crab,snake" },
		{ "ClearMobs" },
		{ "Freeze", true },
		{ "Freeze", false },
		{ "Sandbox" },
		{ "Waves" },
		{ "EndWave" },
		{ "Pause", true },
		{ "JumpWave", 1 },
		{ "JumpWave", 20 },
		{ "God", true },
		{ "Weapons", false },
		{ "GiveItem", anItem },
		{ "Shards", "Add", 100 },
		{ "Shards", "Add", -100 },
		{ "Shards", "Set", 0 },
		{ "Level", "Add", 1 },
		{ "Level", "Set", 10 },
	}
	for _, call in valid do
		check(Admin.check(call[1], call[2], call[3]), "should pass: " .. show(call))
	end
	local invalid = {
		{ nil },
		{ 5 },
		{ "Explode" },
		{ "Travel", "DesertBasin" },
		{ "Travel" },
		{ "Travel", { "Lobby" } },
		{ "Spawn", "dragon", 5 },
		{ "Spawn", anEnemy, 0 },
		{ "Spawn", anEnemy, 51 },
		{ "Spawn", anEnemy, 2.5 },
		{ "Spawn", anEnemy, 0 / 0 },
		{ "KeepAlive", 101, "" },
		{ "KeepAlive", -1, "" },
		{ "KeepAlive", 5, "crab,dragon" },
		{ "KeepAlive", 5 },
		{ "KeepAlive", 5, string.rep("crab,", 130) },
		{ "ClearMobs", true },
		{ "Freeze", "yes" },
		{ "Freeze" },
		{ "Sandbox", 1 },
		{ "JumpWave", 0 },
		{ "JumpWave", 21 },
		{ "JumpWave", math.huge },
		{ "Pause", 1 },
		{ "God", 1 },
		{ "GiveItem", "weapon_01_1" },
		{ "GiveItem", "nope" },
		{ "Shards", "Add", 1e7 },
		{ "Shards", "Set", -1 },
		{ "Shards", "Give", 5 },
		{ "Shards", "Set", 1.5 },
		{ "Level", "Add", 0 },
		{ "Level", "Set", 0 },
		{ "Level", "Set", 1001 },
		{ "Level", "Add", "1" },
	}
	for _, call in invalid do
		check(not Admin.check(call[1], call[2], call[3]), "should fail: " .. show(call))
	end
	return { passed = checks }
end
```

- [ ] **Step 2: Install the test and run it; it should fail.** In Edit (helper block first):

```lua
create('ModuleScript','AdminConfigTests',testsFolder(),'studio-prototype/combat/AdminConfigTests.luau')
return fresh(SS.RogueliteTests.AdminConfigTests)(fresh(RS.RogueliteCombat.AdminConfig),require(RS.RogueliteCombat.EnemyCatalog),require(RS.RogueliteCombat.ShopCatalog))
```

  Expected: an error containing `AdminConfig is not a valid member`.

- [ ] **Step 3: Write AdminConfig.** Create `studio-prototype/combat/AdminConfig.luau`:

```lua
-- Developer accounts and request rules for the ADMIN panel (ADMIN_PANEL.md).
-- Shared: clients only use isAdmin to show or hide the ADMIN button. The server checks isAdmin
-- and check() on every admin request. By UserId, never by name, because names can change.
-- Sandboxed (Capabilities copied from CharacterStats): CharacterService, ShopService and the
-- RogueliteCombat scripts require it, so everything it requires must be sandboxed too.
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local combat=RS:WaitForChild('RogueliteCombat')
local Enemies=require(combat:WaitForChild('EnemyCatalog'))
local Items=require(combat:WaitForChild('ShopCatalog'))
local Maps=require(combat:WaitForChild('MapConfig'))
local E=require(combat:WaitForChild('EconomyConfig'))
local XP=require(combat:WaitForChild('RunXP'))
local A={UserIds={341854066},BossId='Hammer'} -- 341854066: EggaRowls
local admins={};for _,id in A.UserIds do admins[id]=true end
function A.isAdminId(id) return type(id)=='number' and admins[id]==true end
function A.isAdmin(player) return typeof(player)=='Instance' and player:IsA('Player') and A.isAdminId(player.UserId) end

-- Test runs: the first admin action of a run sets RogueliteRunState.AdminTestRun, and
-- ShopService.resetRun clears it. While it is set, reward code grants nothing. The folder is
-- looked up lazily: ShopService creates it after requiring this module.
function A.isTestRun(runState)
 runState=runState or RS:FindFirstChild('RogueliteRunState')
 return typeof(runState)=='Instance' and runState:GetAttribute('AdminTestRun')==true
end
function A.markTestRun()
 local run=RunService:IsServer() and RS:FindFirstChild('RogueliteRunState')
 if run then run:SetAttribute('AdminTestRun',true) end
end

-- Argument rules for every AdminAction request. Nothing a client sends is trusted.
local function int(v,lo,hi) return type(v)=='number' and v==v and v%1==0 and v>=lo and v<=hi end
local function flag(a,b) return type(a)=='boolean' and b==nil end
local function none(a,b) return a==nil and b==nil end
-- Comma list of EnemyCatalog ids; '' means the map's own mix.
local function enemyList(v)
 if type(v)~='string' or #v>600 then return false end
 for id in v:gmatch('[^,%s]+') do if not Enemies.ById[id] then return false end end
 return true
end
local rules={
 Travel=function(a,b) return b==nil and (a=='Lobby' or Maps.valid(a)) end,
 Spawn=function(a,b) return (a==A.BossId or (type(a)=='string' and Enemies.ById[a]~=nil)) and int(b,1,50) end,
 KeepAlive=function(a,b) return int(a,0,100) and enemyList(b) end,
 ClearMobs=none,Freeze=flag,
 Sandbox=none,Waves=none,EndWave=none,Pause=flag,
 JumpWave=function(a,b) return int(a,1,20) and b==nil end,
 God=flag,Weapons=flag,
 GiveItem=function(a,b) local e=type(a)=='string' and Items.ById[a];return e and e.kind~='Weapon' and b==nil end,
 Shards=function(a,b) return (a=='Add' and int(b,-E.MAX_SHARDS,E.MAX_SHARDS)) or (a=='Set' and int(b,0,E.MAX_SHARDS)) end,
 Level=function(a,b) return (a=='Add' and int(b,1,100)) or (a=='Set' and int(b,1,XP.MAX_LEVEL)) end,
}
A.Actions={};for name in rules do table.insert(A.Actions,name) end;table.sort(A.Actions)
-- true only for a known action with valid arguments.
function A.check(action,a,b)
 local rule=type(action)=='string' and rules[action] or nil
 return rule~=nil and rule(a,b)==true
end
return A
```

- [ ] **Step 4: Install it (sandboxed) and run the test; it should pass.** In Edit:

```lua
create('ModuleScript','AdminConfig',RS.RogueliteCombat,'studio-prototype/combat/AdminConfig.luau',RS.RogueliteCombat.CharacterStats)
local r=fresh(SS.RogueliteTests.AdminConfigTests)(fresh(RS.RogueliteCombat.AdminConfig),require(RS.RogueliteCombat.EnemyCatalog),require(RS.RogueliteCombat.ShopCatalog))
return 'passed '..r.passed..' sandboxed='..tostring(RS.RogueliteCombat.AdminConfig.Sandboxed)
```

  Expected: `passed 69 sandboxed=true`. That count is:
  - 4 who-is-a-developer checks;
  - 3 test-run checks;
  - 1 action count;
  - 26 valid calls;
  - 35 invalid calls.

  If the number differs, re-count against the test before changing anything.

- [ ] **Step 5: Add it to the Rojo project.** In `studio-prototype/combat/default.project.json`, replace:

```json
        "MapConfig": {
          "$path": "MapConfig.luau"
        },
```

  with:

```json
        "MapConfig": {
          "$path": "MapConfig.luau"
        },
        "AdminConfig": {
          "$path": "AdminConfig.luau"
        },
```

  Check the JSON and parse the Luau:

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && python -c "import json;json.load(open('studio-prototype/combat/default.project.json'))" && echo "json ok" && for f in studio-prototype/combat/AdminConfig.luau studio-prototype/combat/AdminConfigTests.luau; do ~/.rokit/bin/stylua --check "$f" 2>&1 | grep -i "error parsing" && echo "PARSE ERROR $f" || echo "ok $f"; done
```

  Expected: `json ok`, then `ok` twice.

- [ ] **Step 6: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/combat/AdminConfig.luau roguelite-planning/studio-prototype/combat/AdminConfigTests.luau roguelite-planning/studio-prototype/combat/default.project.json && git commit -q -m "$(printf 'Add AdminConfig: developer ids, test-run guard and admin request rules\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 2: Test runs pay nothing, and the HUD says so

Nothing sets `AdminTestRun` yet, so after this task normal play is unchanged. The checks set the flag by hand.

**Files:**
- Modify: `studio-prototype/combat/ProfileService.luau` (requires; `recordRun`)
- Modify: `studio-prototype/combat/LeaderboardService.server.luau` (requires; `credit`; best wave)
- Modify: `studio-prototype/combat/RogueliteMeta.server.luau` (requires; death info)
- Modify: `studio-prototype/combat/ShopService.luau` (boot; `resetRun`)
- Modify: `studio-prototype/ui/RogueliteUI.luau` (TEST RUN tag; `SetTestRun`; Practice closes menus)
- Modify: `studio-prototype/ui/RogueliteHUD.client.luau` (Practice timer; TEST RUN)

- [ ] **Step 1: Check that Studio matches the repo.** In Edit:

```lua
local out={}
for _,e in {{SSS.ProfileService,'studio-prototype/combat/ProfileService.luau'},{SSS.LeaderboardService,'studio-prototype/combat/LeaderboardService.server.luau'},{SSS.RogueliteMeta,'studio-prototype/combat/RogueliteMeta.server.luau'},{SSS.ShopService,'studio-prototype/combat/ShopService.luau'},{RS.RogueliteUI,'studio-prototype/ui/RogueliteUI.luau'},{SPS.RogueliteHUD,'studio-prototype/ui/RogueliteHUD.client.luau'}} do table.insert(out,tostring(same(e[1],e[2]))) end
return table.concat(out,' ')
```

  Expected: `true true true true true true`.

- [ ] **Step 2: ProfileService: `recordRun` grants nothing in a test run.** In `studio-prototype/combat/ProfileService.luau`:

  a) Replace:
```lua
local Skills=require(combat:WaitForChild('SkillTreeConfig'))
```
  with:
```lua
local Skills=require(combat:WaitForChild('SkillTreeConfig'))
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed; this module is unsandboxed
```

  b) Replace:
```lua
-- Run result: emeralds for the waves passed, best wave per map.
function P.recordRun(player,map,wavesPassed,emeralds)
 local d=P.profiles[player];if not d then return end
```
  with:
```lua
-- Run result: emeralds for the waves passed, best wave per map.
-- A test run (the admin panel was used) grants nothing: no emeralds, wins or best waves.
function P.recordRun(player,map,wavesPassed,emeralds)
 local d=P.profiles[player];if not d or Admin.isTestRun() then return end
```

- [ ] **Step 3: LeaderboardService: no kills or best waves from a test run.** In `studio-prototype/combat/LeaderboardService.server.luau`:

  a) Replace:
```lua
local runState=RS:WaitForChild('RogueliteRunState')
```
  with:
```lua
local runState=RS:WaitForChild('RogueliteRunState')
-- Test runs (the admin panel was used) record no kills or best waves. Time played still counts:
-- it measures time on the server, not a run result.
local Admin=require(combat:WaitForChild('AdminConfig'))
```

  b) Replace:
```lua
 if Shop.phase~='Combat' or npc:GetAttribute('PracticeTarget') or npc:GetAttribute('KillCredited') then return end
```
  with:
```lua
 if Shop.phase~='Combat' or Admin.isTestRun(runState) or npc:GetAttribute('PracticeTarget') or npc:GetAttribute('KillCredited') then return end
```

  c) Replace:
```lua
   if wave>d.bestWave and inRun(p) then d.bestWave=wave end
```
  with:
```lua
   if wave>d.bestWave and inRun(p) and not Admin.isTestRun(runState) then d.bestWave=wave end
```

- [ ] **Step 4: RogueliteMeta: the death screen shows 0 emeralds in a test run.** In `studio-prototype/combat/RogueliteMeta.server.luau`:

  a) Replace:
```lua
local Characters=require(SSS:WaitForChild('CharacterService'))
```
  with:
```lua
local Characters=require(SSS:WaitForChild('CharacterService'))
local Admin=require(combat:WaitForChild('AdminConfig'))
```

  b) Replace:
```lua
 p:SetAttribute('DeathInfo',Http:JSONEncode({wave=Shop.wave,level=s.level,emeralds=emeraldsFor(Shop.wave),map='Pine Valley',
```
  with:
```lua
 -- A test run (the admin panel was used) pays nothing, so the death screen shows 0 emeralds.
 p:SetAttribute('DeathInfo',Http:JSONEncode({wave=Shop.wave,level=s.level,emeralds=Admin.isTestRun() and 0 or emeraldsFor(Shop.wave),map='Pine Valley',
```

- [ ] **Step 5: ShopService: a server boot and a new run are never test runs.** In `studio-prototype/combat/ShopService.luau`:

  a) Replace:
```lua
run.Name='RogueliteRunState';run.Parent=RS
run:SetAttribute('Phase','Shop');run:SetAttribute('Wave',1)
```
  with:
```lua
run.Name='RogueliteRunState';run.Parent=RS
run:SetAttribute('Phase','Shop');run:SetAttribute('Wave',1);run:SetAttribute('AdminTestRun',nil)
```

  b) Replace:
```lua
 run:SetAttribute('Phase','Shop');run:SetAttribute('Wave',1);run:SetAttribute('WaveEndsAt',nil);run:SetAttribute('Paused',nil)
 combat:SetAttribute('ZombiesEnabled',false);Shards.clear(false)
```
  with:
```lua
 run:SetAttribute('Phase','Shop');run:SetAttribute('Wave',1);run:SetAttribute('WaveEndsAt',nil);run:SetAttribute('Paused',nil)
 -- A new run starts clean: not a test run (ADMIN_PANEL.md).
 run:SetAttribute('AdminTestRun',nil)
 combat:SetAttribute('ZombiesEnabled',false);Shards.clear(false)
```

- [ ] **Step 6: RogueliteUI: TEST RUN tag, and Practice closes menus.** In `studio-prototype/ui/RogueliteUI.luau`:

  a) Replace:
```lua
 local phaseText=label(phase,"Label","PRACTICE",8,2,123,26,17)
```
  with:
```lua
 local phaseText=label(phase,"Label","PRACTICE",8,2,123,26,17)
 -- TEST RUN tag under the phase pill: the admin panel was used, so this run pays no rewards.
 local testTag=panel(timer,"TestRun",57,86,111,26,"inset");testTag.Visible=false
 label(testTag,"Label","TEST RUN",0,0,111,26,15,C.gold)
```

  b) Replace:
```lua
  phaseText.Text=wave and ("WAVE "..tostring(wave)) or string.upper(phaseName or "PRACTICE")
 end
```
  with:
```lua
  phaseText.Text=wave and ("WAVE "..tostring(wave)) or string.upper(phaseName or "PRACTICE")
 end
 function controller:SetTestRun(on)
  testTag.Visible=on==true;gui:SetAttribute("TestRunShown",on==true)
 end
```

  c) Replace:
```lua
   if data.phase=='Shop' then controller:ShowPreview('Shop') elseif data.phase=='Combat' then close() end
```
  with:
```lua
   -- Sandbox (phase Practice) has no shop: close any open menu, as a wave start does.
   if data.phase=='Shop' then controller:ShowPreview('Shop') elseif data.phase=='Combat' or data.phase=='Practice' then close() end
```

- [ ] **Step 7: RogueliteHUD: the Sandbox timer and the TEST RUN tag.** In `studio-prototype/ui/RogueliteHUD.client.luau`, replace:

```lua
 view:SetTimer(remaining,validWave and math.floor(wave) or nil,phase,bossLabel)
```

  with:

```lua
 -- Sandbox (phase Practice, from the admin panel): no countdown and no wave number.
 local practice=state~=nil and state:GetAttribute("Phase")=="Practice"
 view:SetTimer(not practice and remaining or nil,not practice and validWave and math.floor(wave) or nil,phase,practice and "SANDBOX" or bossLabel)
 -- A run where the admin panel was used pays no rewards (ADMIN_PANEL.md).
 view:SetTestRun(state~=nil and state:GetAttribute("AdminTestRun")==true)
```

- [ ] **Step 8: Parse-check and sync.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && for f in studio-prototype/combat/ProfileService.luau studio-prototype/combat/LeaderboardService.server.luau studio-prototype/combat/RogueliteMeta.server.luau studio-prototype/combat/ShopService.luau studio-prototype/ui/RogueliteUI.luau studio-prototype/ui/RogueliteHUD.client.luau; do ~/.rokit/bin/stylua --check "$f" 2>&1 | grep -i "error parsing" && echo "PARSE ERROR $f" || echo "ok $f"; done
```

  Expected: `ok` six times. Then in Edit:

```lua
sync(SSS.ProfileService,'studio-prototype/combat/ProfileService.luau')
sync(SSS.LeaderboardService,'studio-prototype/combat/LeaderboardService.server.luau')
sync(SSS.RogueliteMeta,'studio-prototype/combat/RogueliteMeta.server.luau')
sync(SSS.ShopService,'studio-prototype/combat/ShopService.luau')
sync(RS.RogueliteUI,'studio-prototype/ui/RogueliteUI.luau')
sync(SPS.RogueliteHUD,'studio-prototype/ui/RogueliteHUD.client.luau')
return 'synced'
```

- [ ] **Step 9: Play check.** Follow the shared-Studio rules and start Play.

  a) **Server** (direct; attributes only): set the flag and a fake Practice phase.
```lua
local run=game.ReplicatedStorage:WaitForChild('RogueliteRunState')
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait();local _=p.Character or p.CharacterAdded:Wait()
task.wait(2)
local fresh=run:GetAttribute('AdminTestRun')==nil
run:SetAttribute('AdminTestRun',true);run:SetAttribute('Phase','Practice')
return 'freshRunNotTest='..tostring(fresh)
```
  Expected: `freshRunNotTest=true`.

  b) **Client:**
```lua
local hud=game.Players.LocalPlayer.PlayerGui:WaitForChild('RogueliteHUD');task.wait(.5)
local timer=hud.SafeArea.HUD.Timer
return 'tag='..tostring(timer.TestRun.Visible)..' time='..timer.Time.Text..' phase='..timer.Phase.Label.Text
```
  Expected: `tag=true time=SANDBOX phase=PRACTICE`.

  c) **Server** (`serverCheck`; restores Phase, then the reward guard):
```lua
return serverCheck([==[
local RS=game.ReplicatedStorage;local run=RS.RogueliteRunState
local Profiles=require(game.ServerScriptService.ProfileService);local Shop=require(game.ServerScriptService.ShopService)
run:SetAttribute('Phase',Shop.phase)
local p=game.Players:GetPlayers()[1]
local t0=os.clock();while not Profiles.get(p) and os.clock()-t0<10 do task.wait(.1) end
local d=Profiles.get(p);local gems=d.emeralds;local key='PlanDCheck'
add(run:GetAttribute('AdminTestRun')==true,'the flag is set for this check')
Profiles.recordRun(p,key,25,500)
add(d.emeralds==gems and d.bestWaves[key]==nil and d.mapWins[key]==nil,'test run: recordRun grants no emeralds, best wave or win')
Shop.resetRun()
add(run:GetAttribute('AdminTestRun')==nil,'resetRun clears the flag')
Profiles.recordRun(p,key,3,7)
add(d.emeralds>gems and d.bestWaves[key]==3,'a real run still pays ('..(d.emeralds-gems)..' emeralds)')
d.emeralds=gems;d.bestWaves[key]=nil;Profiles.publish(p)
]==])
```
  Expected: four `PASS` lines.

  d) **Client:**
```lua
task.wait(.5)
local timer=game.Players.LocalPlayer.PlayerGui.RogueliteHUD.SafeArea.HUD.Timer
return 'tag='..tostring(timer.TestRun.Visible)..' time='..timer.Time.Text
```
  Expected: `tag=false time=--:--` (Shop phase, no countdown).

  Run `get_console_output` (Conventions), then stop Play.

- [ ] **Step 10: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/combat/ProfileService.luau roguelite-planning/studio-prototype/combat/LeaderboardService.server.luau roguelite-planning/studio-prototype/combat/RogueliteMeta.server.luau roguelite-planning/studio-prototype/combat/ShopService.luau roguelite-planning/studio-prototype/ui/RogueliteUI.luau roguelite-planning/studio-prototype/ui/RogueliteHUD.client.luau && git commit -q -m "$(printf 'Test runs pay no emeralds, wins, best waves or leaderboard entries\n\nThe HUD shows a TEST RUN tag and a Sandbox timer.\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 3: Developer checks on the existing tools, god mode, clean new runs

**Files:**
- Modify: `studio-prototype/combat/CharacterService.luau` (require; `setClass` → `clearAdmin`; `contact`; `request` gate and test-run mark)
- Modify: `studio-prototype/combat/ShopService.luau` (`resetRun` clears admin edits)
- Modify: `studio-prototype/combat/RogueliteCombat.server.luau` (require; `EquipWeapon`)
- Modify: `hammer-boss/BossService.luau` (require; `practice` gate; `spawn` assertion)
- Modify: `studio-prototype/combat/RogueliteMeta.server.luau` (`onPracticeEmeralds`)

- [ ] **Step 1: Check that Studio matches the repo.** In Edit:

```lua
local out={}
for _,e in {{SSS.CharacterService,'studio-prototype/combat/CharacterService.luau'},{SSS.ShopService,'studio-prototype/combat/ShopService.luau'},{SSS.RogueliteCombat,'studio-prototype/combat/RogueliteCombat.server.luau'},{SSS.BossService,'hammer-boss/BossService.luau'},{SSS.RogueliteMeta,'studio-prototype/combat/RogueliteMeta.server.luau'}} do table.insert(out,tostring(same(e[1],e[2]))) end
return table.concat(out,' ')
```

  Expected: `true true true true true`.

- [ ] **Step 2: Audit every player-damage path.** God mode is one check in `CharacterService.contact`, so every way a player loses health must go through `contact`. The repo audit (2026-09-28) found these callers:
  - `CharacterService` Heartbeat contact loop (`ContactDamage`);
  - `CharacterService.request('Damage')` (test damage);
  - `EnemyAttacks.damage` (regular melee, lunges and projectiles);
  - `ZombieAttacks` (the tank's slam);
  - `BossService` hammer `damage`.

  The only other `TakeDamage` is `CombatEffectsService.hit`, which hurts enemies. Nothing creates `Explosion` instances. Confirm there's nothing extra in Studio. In Edit:

```lua
local hits={}
for _,service in {workspace,game.ReplicatedStorage,game.ReplicatedFirst,game.ServerScriptService,game.ServerStorage,game.StarterPlayer,game.StarterGui,game.Lighting} do
 for _,s in service:GetDescendants() do
  if s:IsA('LuaSourceContainer') then
   local ok,src=pcall(function() return s.Source end)
   if ok and (src:find('TakeDamage',1,true) or src:find('BreakJoints()',1,true) or src:find("new('Explosion'",1,true) or src:find('new("Explosion"',1,true) or src:find('%.Health%s*=%s*0%f[^%d%.]')) then table.insert(hits,s:GetFullName()) end
  end
 end
end
table.sort(hits);return #hits..'\n'..table.concat(hits,'\n')
```

  Expected: `ServerScriptService.CharacterService`, `ServerScriptService.CombatEffectsService`, and only test or QA modules (`…Tests`, `…QA`, `ServerStorage.RogueliteTests.*`), which build throwaway fixtures. For any other script, read it:
  - If it can hurt a player, route it through `CharacterService.contact` or check `player:GetAttribute('AdminGod')`, and add that edit to this task.
  - List every extra hit in the task report.

- [ ] **Step 3: CharacterService.** In `studio-prototype/combat/CharacterService.luau`:

  a) Replace:
```lua
local Skills=require(combat:WaitForChild('SkillTreeConfig'))
```
  with:
```lua
local Skills=require(combat:WaitForChild('SkillTreeConfig'))
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed, like this module
```

  b) Replace:
```lua
function Service.setClass(player,class)
 local s=Service.states[player]
 if not s or type(class)~='string' or not Stats.Classes[class] or s.class==class then return end
 s.class=class;Service.refresh(player)
end
```
  with:
```lua
function Service.setClass(player,class)
 local s=Service.states[player]
 if not s or type(class)~='string' or not Stats.Classes[class] or s.class==class then return end
 s.class=class;Service.refresh(player)
end
-- A new run starts clean (ShopService.resetRun): admin stat edits, class picks and god mode
-- never carry into a run that pays rewards. Normal play has nothing to clear. The caller refreshes.
function Service.clearAdmin(player)
 local s=Service.states[player];if not s then return end
 s.overrides={}
 local picked=player:GetAttribute('RunClass');if Stats.Classes[picked] then s.class=picked end
 player:SetAttribute('AdminGod',nil)
end
```

  c) Replace:
```lua
 if not s or not h or h.Health<=0 or player.Character:FindFirstChildOfClass('ForceField') then return 0 end
```
  with:
```lua
 -- Admin god mode (AdminGod, set only by AdminService): no damage from any source. Every player
 -- damage path (contact, enemy melee and projectiles, zombie slams, the boss) comes through here.
 if not s or not h or h.Health<=0 or player.Character:FindFirstChildOfClass('ForceField') or player:GetAttribute('AdminGod')==true then return 0 end
```

  d) Replace:
```lua
 -- Studio stat/health/population controls remain usable during combat.
 if not RunService:IsStudio() or not s or not h or h.Health<=0 then return false end
```
  with:
```lua
 -- Developer controls (the ADMIN panel's Player tab), usable during combat. Checked by UserId on
 -- every request (AdminConfig), in Studio and on live servers; everyone else gets nothing.
 if not Admin.isAdmin(player) or not s or not h or h.Health<=0 then return false end
```

  e) Replace:
```lua
 s.lastRequest=os.clock();s.folder:SetAttribute('PracticeRevision',(s.folder:GetAttribute('PracticeRevision') or 0)+1)
 return true
end
```
  with:
```lua
 s.lastRequest=os.clock();s.folder:SetAttribute('PracticeRevision',(s.folder:GetAttribute('PracticeRevision') or 0)+1)
 Admin.markTestRun()
 return true
end
```

- [ ] **Step 4: ShopService: a new run clears admin edits.** In `studio-prototype/combat/ShopService.luau`, replace:

```lua
 for p in S.states do S.resetPlayer(p) end
```

  with:

```lua
 for p in S.states do Characters.clearAdmin(p);S.resetPlayer(p) end
```

  `S.resetPlayer` → `S.bonuses` → `Characters.refresh` applies the cleared stats.

- [ ] **Step 5: RogueliteCombat.server: Give weapon for developers, with a tier.** In `studio-prototype/combat/RogueliteCombat.server.luau`:

  a) Replace:
```lua
local Role=require(script.Parent:WaitForChild('ServerRole'))
```
  with:
```lua
local Role=require(script.Parent:WaitForChild('ServerRole'))
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed, like this script
```

  b) Replace:
```lua
combat.EquipWeapon.OnServerEvent:Connect(function(player,index,id)
 local s=states[player]
 if not RunService:IsStudio() or not s or not Catalog.validate(index,id) then return end
 local hum=player.Character and player.Character:FindFirstChildOfClass('Humanoid')
 if not hum or hum.Health<=0 then return end
 if id~='' and not templates:FindFirstChild(id) then return end
 if os.clock()-s.lastEquip<.12 then return end;s.lastEquip=os.clock()
 local slot=s.slots[index]
 if slot.folder:GetAttribute('WeaponId')==id then return end
 -- Creative copies are free, and never inherit the replaced copy's paid refund.
 slot.folder:SetAttribute('CopyId',game:GetService('HttpService'):GenerateGUID(false))
 slot.folder:SetAttribute('BasePrice',0);slot.folder:SetAttribute('FinalPurchasePrice',0);slot.folder:SetAttribute('PurchasePrice',0)
 slot.folder:SetAttribute('Tier',1);slot.folder:SetAttribute('WavePurchased',0)
 slot.folder:SetAttribute('WeaponId',id);reset(slot,workspace:GetServerTimeNow()+.25)
 local count=0;for _,v in s.slots do if v.folder:GetAttribute('WeaponId')~='' then count+=1 end end
 s.folder:SetAttribute('EquippedCount',count)
 local shopState=Shop.states[player];if shopState then shopState.ready=false;shopState.revision+=1;Shop.publish(player) end
end)
```
  with:
```lua
-- Give weapon (ADMIN panel Player tab): developers only, checked by UserId. tier 1-4 (default 1).
combat.EquipWeapon.OnServerEvent:Connect(function(player,index,id,tier)
 local s=states[player]
 if tier==nil then tier=1 end
 if not Admin.isAdmin(player) or not s or not Catalog.validate(index,id) then return end
 if type(tier)~='number' or tier%1~=0 or tier<1 or tier>4 then return end
 local hum=player.Character and player.Character:FindFirstChildOfClass('Humanoid')
 if not hum or hum.Health<=0 then return end
 if id~='' and not templates:FindFirstChild(id) then return end
 if os.clock()-s.lastEquip<.12 then return end;s.lastEquip=os.clock()
 local slot=s.slots[index]
 if slot.folder:GetAttribute('WeaponId')==id and (slot.folder:GetAttribute('Tier') or 1)==tier then return end
 -- Creative copies are free, and never inherit the replaced copy's paid refund.
 slot.folder:SetAttribute('CopyId',game:GetService('HttpService'):GenerateGUID(false))
 slot.folder:SetAttribute('BasePrice',0);slot.folder:SetAttribute('FinalPurchasePrice',0);slot.folder:SetAttribute('PurchasePrice',0)
 slot.folder:SetAttribute('Tier',tier);slot.folder:SetAttribute('WavePurchased',0)
 slot.folder:SetAttribute('WeaponId',id);reset(slot,workspace:GetServerTimeNow()+.25)
 local count=0;for _,v in s.slots do if v.folder:GetAttribute('WeaponId')~='' then count+=1 end end
 s.folder:SetAttribute('EquippedCount',count)
 local shopState=Shop.states[player];if shopState then shopState.ready=false;shopState.revision+=1;Shop.publish(player) end
 Admin.markTestRun()
end)
```

- [ ] **Step 6: BossService: developers, not Studio, spawn practice bosses.** In `hammer-boss/BossService.luau`:

  a) Replace:
```lua
local Death=require(combat.ZombieDeath)
local B={states={}}
```
  with:
```lua
local Death=require(combat.ZombieDeath)
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed; this module is unsandboxed
local B={states={}}
```

  b) Replace:
```lua
 if not Run:IsStudio() or (action~='SpawnBoss' and action~='RemoveBoss') then return false end
```
  with:
```lua
 -- Developers only (the admin panel), in Studio and on live servers; CharacterService checks too.
 if not Admin.isAdmin(player) or (action~='SpawnBoss' and action~='RemoveBoss') then return false end
```

  c) Replace:
```lua
 assert(not practice or Run:IsStudio(),'Practice is Studio only')
```
  with:
```lua
 -- practice: an admin-panel boss (BossPractice: no loot). Callers check the developer first.
```

- [ ] **Step 7: RogueliteMeta: developer emeralds work on live servers.** In `studio-prototype/combat/RogueliteMeta.server.luau`, replace:

```lua
-- Stats admin panel (Studio only): add or set emeralds. CharacterService validates the numbers;
-- grants count as earned, and Robux emeralds are clamped so they never exceed the balance.
Characters.onPracticeEmeralds=function(p,mode,amount)
 local d=studio and Profiles.get(p);if not d then return false end
```

  with:

```lua
-- Admin panel emeralds (developers only): add or set. CharacterService checks the developer and
-- the numbers. In Studio the profile is in memory; on a live server this is a real, saved change
-- to the developer's own account. Grants count as earned; Robux emeralds are clamped to the balance.
Characters.onPracticeEmeralds=function(p,mode,amount)
 local d=Admin.isAdmin(p) and Profiles.get(p);if not d then return false end
```

- [ ] **Step 8: Parse-check and sync.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && for f in studio-prototype/combat/CharacterService.luau studio-prototype/combat/ShopService.luau studio-prototype/combat/RogueliteCombat.server.luau hammer-boss/BossService.luau studio-prototype/combat/RogueliteMeta.server.luau; do ~/.rokit/bin/stylua --check "$f" 2>&1 | grep -i "error parsing" && echo "PARSE ERROR $f" || echo "ok $f"; done
```

  Expected: `ok` five times. Then in Edit:

```lua
sync(SSS.CharacterService,'studio-prototype/combat/CharacterService.luau')
sync(SSS.ShopService,'studio-prototype/combat/ShopService.luau')
sync(SSS.RogueliteCombat,'studio-prototype/combat/RogueliteCombat.server.luau')
sync(SSS.BossService,'hammer-boss/BossService.luau')
sync(SSS.RogueliteMeta,'studio-prototype/combat/RogueliteMeta.server.luau')
return 'synced'
```

- [ ] **Step 9: Play check.** Start Play (shared-Studio rules).

  a) **Server** (`serverCheck`):
```lua
return serverCheck([==[
local RS=game.ReplicatedStorage;local run=RS.RogueliteRunState
local Characters=require(game.ServerScriptService.CharacterService);local Shop=require(game.ServerScriptService.ShopService)
local Admin=require(RS.RogueliteCombat.AdminConfig)
local p=game.Players:GetPlayers()[1];local char=p.Character or p.CharacterAdded:Wait();local h=char:WaitForChild('Humanoid')
local s=Characters.states[p];local t0=os.clock();while not s and os.clock()-t0<10 do task.wait(.1);s=Characters.states[p] end
add(Admin.isAdmin(p),'the Studio player is a developer ('..p.UserId..')')
for _,f in char:GetChildren() do if f:IsA('ForceField') then f:Destroy() end end
s.blocks=0;h.Health=h.MaxHealth;local before=h.Health
p:SetAttribute('AdminGod',true)
add(Characters.contact(p,20,1)==0 and h.Health==before,'god mode: contact deals 0')
p:SetAttribute('AdminGod',nil)
local dealt=Characters.contact(p,20,1)
add(dealt>0 and h.Health<before,'without god mode, contact still hurts ('..dealt..')')
h.Health=h.MaxHealth;run:SetAttribute('AdminTestRun',nil);s.lastRequest=-1e6
add(Characters.request(p,'Stat','Damage',50)==true and s.overrides.Damage==50,'developer stat edit accepted')
add(run:GetAttribute('AdminTestRun')==true,'the edit marks a test run')
p:SetAttribute('AdminGod',true)
Shop.resetRun()
add(next(s.overrides)==nil and p:GetAttribute('AdminGod')==nil and run:GetAttribute('AdminTestRun')==nil,'resetRun clears stat edits, god mode and the flag')
]==])
```
  Expected: six `PASS` lines.

  b) **Client** (Give weapon with a tier):
```lua
local combat=game.ReplicatedStorage.RogueliteCombat;local lp=game.Players.LocalPlayer
local own=combat.PlayerStates:WaitForChild(tostring(lp.UserId))
local free;for i=1,6 do if own['Slot'..i]:GetAttribute('WeaponId')=='' then free=i;break end end
combat.EquipWeapon:FireServer(free,'01',4);task.wait(.5)
local got=own['Slot'..free]:GetAttribute('WeaponId')..' tier '..tostring(own['Slot'..free]:GetAttribute('Tier'))
combat.EquipWeapon:FireServer(free,'01',9);task.wait(.3)
local bad=tostring(own['Slot'..free]:GetAttribute('Tier'))
combat.EquipWeapon:FireServer(free,'');task.wait(.3)
return 'slot'..free..'='..got..' afterBadTier='..bad..' cleared='..tostring(own['Slot'..free]:GetAttribute('WeaponId')=='')
```
  Expected: `slot<n>=01 tier 4 afterBadTier=4 cleared=true`.

  Run `get_console_output`, then stop Play.

- [ ] **Step 10: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/combat/CharacterService.luau roguelite-planning/studio-prototype/combat/ShopService.luau roguelite-planning/studio-prototype/combat/RogueliteCombat.server.luau roguelite-planning/hammer-boss/BossService.luau roguelite-planning/studio-prototype/combat/RogueliteMeta.server.luau && git commit -q -m "$(printf 'Developer checks replace Studio gates; add god mode and clean new runs\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 4: Spawner: extra enemies, Clear, Freeze, and a pausable population

**Files:**
- Modify: `studio-prototype/RogueliteZombieChase.server.luau` (requires; `adminPaused`; `queueSpawn`; `telegraphGroup`; `spawnZombie`; the per-NPC Heartbeat; `resetWave`; `AdminSpawn` and the resume hook at the end)
- Modify: `hammer-boss/BossService.luau` (`B.step` Freeze)

- [ ] **Step 1: Check that Studio matches the repo.** In Edit:

```lua
return tostring(same(SSS.RogueliteZombieChase,'studio-prototype/RogueliteZombieChase.server.luau'))..' '..tostring(same(SSS.BossService,'hammer-boss/BossService.luau'))
```

  Expected: `true true`.

- [ ] **Step 2: Edit `RogueliteZombieChase.server.luau`.** This file indents with 4 spaces, and `spawnZombie`'s body starts at column 0. Keep both.

  a) Replace:
```lua
local Attacks = require(script.Parent:WaitForChild('ZombieAttacks'))
local waveGeneration = 0
```
  with:
```lua
local Attacks = require(script.Parent:WaitForChild('ZombieAttacks'))
-- The admin panel's Hammer boss spawns (AdminSpawn below). This script and BossService are unsandboxed.
local Bosses = require(script.Parent:WaitForChild('BossService'))
local BossMotion = require(combat:WaitForChild('BossMotion'))
local waveGeneration = 0
-- Admin Pause (ShopService.adminPause): no new spawns until Resume. Looked up lazily, because
-- ShopService creates RogueliteRunState.
local function adminPaused()
    local run = game:GetService('ReplicatedStorage'):FindFirstChild('RogueliteRunState')
    return run ~= nil and run:GetAttribute('AdminPaused') == true
end
```

  b) Replace:
```lua
    if generation ~= waveGeneration or combat:GetAttribute('ZombiesEnabled') ~= true then return end
```
  with:
```lua
    if generation ~= waveGeneration or combat:GetAttribute('ZombiesEnabled') ~= true or adminPaused() then return end
```

  c) Replace:
```lua
local function queueSpawn(index)
    if queuedSet[index] or folder:FindFirstChild(string.format('Zombie_%02d', index)) then return end
```
  with:
```lua
local function queueSpawn(index)
    if adminPaused() or queuedSet[index] or folder:FindFirstChild(string.format('Zombie_%02d', index)) then return end
```

  d) Replace:
```lua
spawnZombie = function(index,overrideId,spawnPosition,splitChild)
if combat:GetAttribute('ZombiesEnabled') ~= true or index>spawnCount() then return end
local instanceName=string.format('Zombie_%02d',index)..(splitChild and '_Split'..splitChild or '')
```
  with:
```lua
-- admin: an extra enemy from the admin panel (AdminSpawn): named Admin_nn, outside the wave's
-- slots, never respawned. index is then its serial number.
spawnZombie = function(index,overrideId,spawnPosition,splitChild,admin)
if combat:GetAttribute('ZombiesEnabled') ~= true or (not admin and index>spawnCount()) then return end
local instanceName=string.format(admin and 'Admin_%02d' or 'Zombie_%02d',index)..(splitChild and '_Split'..splitChild or '')
```

  e) Replace:
```lua
npc:SetAttribute('SplitChild',splitChild~=nil)
```
  with:
```lua
npc:SetAttribute('SplitChild',splitChild~=nil)
if admin then npc:SetAttribute('AdminSpawn',true) end
```

  f) Replace:
```lua
        for child=1,config.splitCount do spawnZombie(index,id,position+Vector3.new(child==1 and -1.5 or 1.5,0,0),child) end
```
  with:
```lua
        for child=1,config.splitCount do spawnZombie(index,id,position+Vector3.new(child==1 and -1.5 or 1.5,0,0),child,admin) end
```

  g) Replace:
```lua
    if splitChild or not npc:GetAttribute('DeathPopped') then return end
```
  with:
```lua
    if splitChild or admin or not npc:GetAttribute('DeathPopped') then return end
```

  h) Replace:
```lua
local connection
connection = RunService.Heartbeat:Connect(function(dt)
    if not npc.Parent or humanoid.Health <= 0 then
        generation += 1
        npc:SetAttribute("Chasing", false)
        connection:Disconnect()
        return
    end
```
  with:
```lua
local frozen = false
local connection
connection = RunService.Heartbeat:Connect(function(dt)
    if not npc.Parent or humanoid.Health <= 0 then
        generation += 1
        npc:SetAttribute("Chasing", false)
        connection:Disconnect()
        return
    end
    -- Admin Freeze: no moving and no new attacks; animations, hits and damage still work.
    if combat:GetAttribute('AdminFreeze') == true then
        if not frozen then
            frozen = true
            npc:SetAttribute("Chasing", false)
            humanoid:Move(Vector3.zero)
            humanoid:MoveTo(root.Position)
        end
        return
    end
    frozen = false
```

  i) Replace:
```lua
    for _,npc in folder:GetChildren() do
        if not npc:GetAttribute('IsHammerBoss') or not combat:GetAttribute('ZombiesEnabled') then npc:Destroy() end
    end
```
  with:
```lua
    for _,npc in folder:GetChildren() do
        -- Bosses and admin-panel extras outlive a population change; everything goes when enemies turn off.
        local keep = npc:GetAttribute('IsHammerBoss') or npc:GetAttribute('AdminSpawn')
        if not keep or not combat:GetAttribute('ZombiesEnabled') then npc:Destroy() end
    end
```

  j) Replace:
```lua
combat:GetAttributeChangedSignal('EnemyRoster'):Connect(resetWave)
resetWave()
```
  with:
```lua
combat:GetAttributeChangedSignal('EnemyRoster'):Connect(resetWave)
resetWave()

-- Admin panel spawner (ADMIN_PANEL.md). Only AdminService calls it, after checking the developer.
-- ('Spawn', id, count, position): extra enemies (or 'Hammer' bosses) on open floor 20-40 studs
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
    for _ = 1, math.clamp(math.floor(count), 0, 50) do
        local point = pickSpawnPoint({}, position, {20, 40}, 20)
        if point then
            if id == 'Hammer' then
                local at = point + Vector3.yAxis * (BossMotion.RootHeight + 0.1)
                local boss = Bosses.spawn(CFrame.lookAt(at, Vector3.new(position.X, at.Y, position.Z)), true)
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
    run:GetAttributeChangedSignal('AdminPaused'):Connect(function()
        if adminPaused() or combat:GetAttribute('ZombiesEnabled') ~= true or not Role.marker() then return end
        for index = 1, spawnCount() do queueSpawn(index) end
    end)
end)
```

  Confirm the new call sites line up:

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/studio-prototype" && grep -c "adminPaused()" RogueliteZombieChase.server.luau && grep -c "AdminSpawn" RogueliteZombieChase.server.luau
```

  Expected: `4`, then `7`.
  - `adminPaused()` appears 4 times: its definition, the telegraph check, `queueSpawn` and the resume hook.
  - `AdminSpawn` appears on 7 lines: two comments, the tag, the `resetWave` keep, the bindable lookup, its name and the boss tag.

- [ ] **Step 3: BossService: Freeze holds the boss.** In `hammer-boss/BossService.luau`, replace:

```lua
 if npc:GetAttribute('BossManual') and Run:IsStudio() then h:Move(Vector3.zero);return end
```

  with:

```lua
 if npc:GetAttribute('BossManual') and Run:IsStudio() then h:Move(Vector3.zero);return end
 -- Admin Freeze: no moving and no new attacks; an attack already under way finishes above.
 if combat:GetAttribute('AdminFreeze')==true then h:Move(Vector3.zero);h:MoveTo(root.Position);return end
```

- [ ] **Step 4: Parse-check and sync.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && for f in studio-prototype/RogueliteZombieChase.server.luau hammer-boss/BossService.luau; do ~/.rokit/bin/stylua --check "$f" 2>&1 | grep -i "error parsing" && echo "PARSE ERROR $f" || echo "ok $f"; done
```

  Expected: `ok` twice. Then in Edit:

```lua
sync(SSS.RogueliteZombieChase,'studio-prototype/RogueliteZombieChase.server.luau')
sync(SSS.BossService,'hammer-boss/BossService.luau')
return 'synced'
```

- [ ] **Step 5: Play check.** Start Play. Run this in **Server** (direct: it uses the bindable and attributes only):

```lua
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat;local run=RS.RogueliteRunState
local r={};local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local spawner=game.ServerStorage:WaitForChild('AdminSpawn',5)
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
local char=p.Character or p.CharacterAdded:Wait();local root=char:WaitForChild('HumanoidRootPart')
local enemies=workspace.RogueliteEnemies;local originalCount=combat:GetAttribute('ZombieCount')
local function flat(a,b) return Vector3.new(a.X-b.X,0,a.Z-b.Z).Magnitude end
add(spawner~=nil and spawner:IsA('BindableFunction'),'ServerStorage.AdminSpawn exists')
p:SetAttribute('AdminGod',true);combat.PlayerStates[tostring(p.UserId)]:SetAttribute('WeaponEnabled',false)
combat:SetAttribute('RunMap','PineValley');task.wait(.3)
char:PivotTo(CFrame.new(workspace.PineValleyArena.PlayerSpawn.Position+Vector3.new(0,4,0)));task.wait(.5)
combat:SetAttribute('ZombieCount',0);combat:SetAttribute('ZombiesEnabled',true);task.wait(1)
add(#enemies:GetChildren()==0,'ZombieCount 0: no wave enemies')
local made=spawner:Invoke('Spawn','regular-zombie',5,root.Position)
add(spawner:Invoke('Spawn','Hammer',1,root.Position)==1,'Spawn the Hammer boss')
spawner:Invoke('Freeze',true)
local named,near,boss=0,0,nil
for _,npc in enemies:GetChildren() do
 if npc:GetAttribute('IsHammerBoss') then boss=npc
 elseif npc.Name:match('^Admin_%d+$') and npc:GetAttribute('AdminSpawn') then named+=1
  local d=flat(npc:GetPivot().Position,root.Position);if d>=19.5 and d<=40.5 then near+=1 end
 end
end
add(made==5 and named==5,'Spawn 5: five Admin_nn extras ('..made..' made, '..named..' named)')
add(near==5,'all five 20-40 studs away ('..near..')')
add(boss~=nil and boss:GetAttribute('AdminSpawn')==true and boss:GetAttribute('BossPractice')==true,'the boss is an admin extra with no loot')
task.wait(.5)
local before={};for _,npc in enemies:GetChildren() do before[npc]=npc:GetPivot().Position end
task.wait(2)
local moved=0;for npc,pos in before do if npc.Parent and (npc:GetPivot().Position-pos).Magnitude>1.5 then moved+=1 end end
add(combat:GetAttribute('AdminFreeze')==true and moved==0,'Freeze: nothing moves ('..moved..' moved)')
spawner:Invoke('Freeze',false);task.wait(1.5)
moved=0;for npc,pos in before do if npc.Parent and (npc:GetPivot().Position-pos).Magnitude>1.5 then moved+=1 end end
add(combat:GetAttribute('AdminFreeze')==nil and moved>0,'Unfreeze: they chase again ('..moved..' moved)')
combat:SetAttribute('ZombieCount',3);task.wait(2.5)
local wave,extra=0,0;for _,npc in enemies:GetChildren() do if npc.Name:match('^Zombie_%d+$') then wave+=1 elseif npc:GetAttribute('AdminSpawn') then extra+=1 end end
add(wave==3 and extra==6,'a population change keeps the extras ('..wave..' wave, '..extra..' extras)')
for _,npc in enemies:GetChildren() do if npc:GetAttribute('AdminSpawn') then npc:FindFirstChildOfClass('Humanoid').Health=0 end end
task.wait(3.5)
extra=0;wave=0;for _,npc in enemies:GetChildren() do if npc:GetAttribute('AdminSpawn') then extra+=1 elseif npc.Name:match('^Zombie_%d+$') then wave+=1 end end
add(extra==0 and wave==3,'killed extras never respawn; the wave slots stay ('..extra..' extras)')
run:SetAttribute('AdminPaused',true)
local victim=enemies:FindFirstChild('Zombie_01');if victim then victim:FindFirstChildOfClass('Humanoid').Health=0 end
task.wait(3.5)
add(victim~=nil and enemies:FindFirstChild('Zombie_01')==nil,'AdminPaused: a killed wave enemy stays gone')
run:SetAttribute('AdminPaused',nil);task.wait(2.5)
add(enemies:FindFirstChild('Zombie_01')~=nil,'resume refills the empty slot')
spawner:Invoke('Spawn','regular-zombie',2,root.Position);spawner:Invoke('Clear');task.wait(.5)
add(#enemies:GetChildren()==0,'Clear removes every enemy')
combat:SetAttribute('ZombiesEnabled',false);combat:SetAttribute('ZombieCount',originalCount)
p:SetAttribute('AdminGod',nil);combat.PlayerStates[tostring(p.UserId)]:SetAttribute('WeaponEnabled',true)
return table.concat(r,'\n')
```

  Expected: every line `PASS`. `Clear` also resets the spawn queues, so the 3 wave slots don't come back until the population changes again, and they don't. Run `get_console_output`, then stop Play.

- [ ] **Step 6: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/RogueliteZombieChase.server.luau roguelite-planning/hammer-boss/BossService.luau && git commit -q -m "$(printf 'Spawner: admin extras, Clear, Freeze and a pausable population\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 5: Run modes and grants in ShopService

**Files:**
- Modify: `studio-prototype/combat/ShopService.luau` (require MapConfig; `startWave`/`waveEnemyCount`; admin modes and grants before `S.request`; `resetRun`)

- [ ] **Step 1: Check that Studio matches the repo.** In Edit: `return same(SSS.ShopService,'studio-prototype/combat/ShopService.luau')`. Expected: `true`.

- [ ] **Step 2: Edit `ShopService.luau`.**

  a) Replace:
```lua
local StatSchema=require(combat.CharacterStats)
```
  with:
```lua
local StatSchema=require(combat.CharacterStats)
local Maps=require(combat.MapConfig) -- sandboxed, like this module
```

  b) Replace:
```lua
local function beginWave()
 if S.phase~='Shop' then return end
 local count=0
 for p,s in S.states do if living(p) then count+=1;if not s.ready or s.pendingLevels>0 then return end end end
 if count==0 then return end
 S.phase='Combat';run:SetAttribute('Phase','Combat');run:SetAttribute('WaveEndsAt',workspace:GetServerTimeNow()+E.WAVE_SECONDS)
 combat:SetAttribute('ZombieCount',combat:GetAttribute('TestZombieCountOverride') or math.min(100,5+(S.wave-1)*2));combat:SetAttribute('ZombiesEnabled',true)
 for p in S.states do local cs=Characters.states[p];cs.blocks=1;cs.folder:SetAttribute('BlocksRemaining',cs.stats.FirstHitBlock);S.publish(p,'Wave started') end
end
```
  with:
```lua
-- The wave's normal enemy count (Keep N alive overrides it through TestZombieCountOverride).
function S.waveEnemyCount() return math.min(100,5+(S.wave-1)*2) end
local function startWave()
 S.phase='Combat';run:SetAttribute('Phase','Combat');run:SetAttribute('WaveEndsAt',workspace:GetServerTimeNow()+E.WAVE_SECONDS)
 combat:SetAttribute('ZombieCount',combat:GetAttribute('TestZombieCountOverride') or S.waveEnemyCount());combat:SetAttribute('ZombiesEnabled',true)
 for p in S.states do local cs=Characters.states[p];cs.blocks=1;cs.folder:SetAttribute('BlocksRemaining',cs.stats.FirstHitBlock);S.publish(p,'Wave started') end
end
local function beginWave()
 if S.phase~='Shop' then return end
 local count=0
 for p,s in S.states do if living(p) then count+=1;if not s.ready or s.pendingLevels>0 then return end end end
 if count==0 then return end
 startWave()
end
```

  c) Replace:
```lua
function S.request(p,action,revision,arg,extra)
```
  with:
```lua
-- Admin panel run modes (ADMIN_PANEL.md "Waves"). AdminService checks the developer first.
-- Enemies turn off for one frame so the spawner and BossEncounter see the old wave end
-- (signals are deferred in this place).
local function endEnemies()
 combat:SetAttribute('ZombiesEnabled',false);Shards.clear(false)
 S.paused=nil;run:SetAttribute('Paused',nil);run:SetAttribute('AdminPaused',nil);run:SetAttribute('WaveEndsAt',nil)
 for _,s in S.states do s.ready=false;s.revision+=1 end
 task.wait()
end
-- Sandbox: phase Practice at wave 1, no clock and no shop. Enemies stay on (weapons need them),
-- but only Keep N alive (TestZombieCountOverride) and Mobs spawns fill the arena.
function S.setPractice()
 endEnemies()
 S.phase='Practice';S.wave=1;run:SetAttribute('Phase','Practice');run:SetAttribute('Wave',1)
 combat:SetAttribute('ZombieCount',combat:GetAttribute('TestZombieCountOverride') or 0);combat:SetAttribute('ZombiesEnabled',true)
 for p in S.states do S.publish(p,'Sandbox · no waves') end
 return true
end
-- Waves from the sandbox: the normal wave-1 shop, then the normal beginWave/finishWave loop.
-- The build stays: it's the same test run.
function S.setWaves()
 if S.phase~='Practice' then return false end
 endEnemies()
 S.phase='Shop';S.wave=1;run:SetAttribute('Phase','Shop');run:SetAttribute('Wave',1)
 for p in S.states do S.prepareUpgrades(p);S.publish(p,'Waves · press Start when ready') end
 return true
end
-- Start wave n (1-20) now from any phase, skipping the shop's ready check.
function S.jumpToWave(n)
 if type(n)~='number' or n~=n or n%1~=0 or n<1 or n>20 then return false end
 endEnemies()
 S.wave=n;run:SetAttribute('Wave',n)
 startWave();return true
end
-- End this wave as if the timer ran out (wave reward, next shop). A boss can't hold it open.
function S.endWave()
 if S.phase~='Combat' then return false end
 S.paused=nil;run:SetAttribute('Paused',nil);run:SetAttribute('AdminPaused',nil)
 return S.finishWave()
end
-- Pause/Resume: the wave clock (pause/resume above) and, through AdminPaused, the spawner.
-- S.pause alone (a solo death) keeps spawning as before.
function S.adminPause(on)
 if on then
  if S.phase~='Combat' or S.paused then return false end
  S.pause();run:SetAttribute('AdminPaused',true)
 else
  if not run:GetAttribute('AdminPaused') then return false end
  run:SetAttribute('AdminPaused',nil);S.resume()
 end
 return true
end
-- Admin grants (Player tab). AdminConfig.check already validated mode and number.
function S.adminShards(p,mode,value)
 local s=S.states[p];if not s then return false,'No run state' end
 local total=mode=='Set' and value or s.shards+value
 if not E.integer(total,0,E.MAX_SHARDS) then return false,'Shards must be between 0 and '..E.MAX_SHARDS end
 s.shards=total;s.revision+=1;S.publish(p,'Shards: '..total)
 return true,'Shards: '..total
end
-- New levels arrive as earned level-ups (chosen in the shop); lowering the level drops unspent ones.
function S.adminLevel(p,mode,value)
 local s=S.states[p];if not s then return false,'No run state' end
 local level=math.clamp(mode=='Set' and value or s.level+value,1,XP.MAX_LEVEL)
 s.pendingLevels=math.max(0,s.pendingLevels+level-s.level);s.level=level;s.xp=0
 s.upgradeOffers={};s.revision+=1;S.prepareUpgrades(p);S.publish(p,'Level '..level)
 return true,'Level '..level
end
function S.adminItem(p,id)
 local s=S.states[p];local entry=Catalog.ById[id]
 if not s or not entry or entry.kind=='Weapon' then return false,'Unknown item' end
 local existing;for _,it in s.items do if it.id==id then existing=it end end
 if existing and existing.count>=entry.cap then return false,'Item copy limit reached' end
 if not existing and #s.items>=E.ITEM_CAPACITY then return false,'Item inventory full' end
 if existing then existing.count+=1 else table.insert(s.items,{id=id,count=1}) end
 s.revision+=1;S.bonuses(p);S.publish(p,entry.name..' added')
 return true,entry.name..' added'
end
function S.request(p,action,revision,arg,extra)
```

  d) Replace (the Task 2 text in `resetRun`):
```lua
 -- A new run starts clean: not a test run (ADMIN_PANEL.md).
 run:SetAttribute('AdminTestRun',nil)
```
  with:
```lua
 -- A new run starts clean: not a test run, no admin pause, freeze or Keep N alive, and the map's
 -- own enemy mix (ADMIN_PANEL.md). Normal play already has these, so nothing fires.
 run:SetAttribute('AdminTestRun',nil);run:SetAttribute('AdminPaused',nil)
 local map=Maps.get(combat:GetAttribute('RunMap'))
 combat:SetAttribute('AdminFreeze',nil);combat:SetAttribute('TestZombieCountOverride',nil);combat:SetAttribute('EnemyRoster',map and map.roster)
```

- [ ] **Step 3: Parse-check and sync.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && ~/.rokit/bin/stylua --check studio-prototype/combat/ShopService.luau 2>&1 | grep -i "error parsing" && echo PARSE ERROR || echo ok
```

  Expected: `ok`. Then in Edit: `sync(SSS.ShopService,'studio-prototype/combat/ShopService.luau');return 'synced'`.

- [ ] **Step 4: Play check.** Start Play.

  a) **Server** (direct): put the tester on Pine Valley, invulnerable, weapons off.
```lua
local combat=game.ReplicatedStorage.RogueliteCombat
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait();local char=p.Character or p.CharacterAdded:Wait()
combat:SetAttribute('RunMap','PineValley');task.wait(.3)
char:PivotTo(CFrame.new(workspace.PineValleyArena.PlayerSpawn.Position+Vector3.new(0,4,0)))
p:SetAttribute('StudioArea','Arena');p:SetAttribute('AdminGod',true);combat.PlayerStates[tostring(p.UserId)]:SetAttribute('WeaponEnabled',false)
return 'ready'
```

  b) **Server** (`serverCheck`): Sandbox.
```lua
return serverCheck([==[
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat;local run=RS.RogueliteRunState
local Shop=require(game.ServerScriptService.ShopService)
add(Shop.setPractice(),'setPractice returns true');task.wait(1)
add(Shop.phase=='Practice' and run:GetAttribute('Phase')=='Practice' and run:GetAttribute('Wave')==1,'phase Practice at wave 1')
add(run:GetAttribute('WaveEndsAt')==nil and combat:GetAttribute('ZombiesEnabled')==true and combat:GetAttribute('ZombieCount')==0,'no clock; enemies on with an empty population')
add(#workspace.RogueliteEnemies:GetChildren()==0,'no wave enemies in Sandbox')
]==])
```
  Expected: four `PASS` lines.

  c) **Client:** the HUD in Sandbox, and the shop refuses to start a wave.
```lua
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat;local run=RS.RogueliteRunState;local Http=game:GetService('HttpService')
local lp=game.Players.LocalPlayer;local own=combat.PlayerStates:WaitForChild(tostring(lp.UserId))
local hud=lp.PlayerGui:WaitForChild('RogueliteHUD');task.wait(.5)
local timer=hud.SafeArea.HUD.Timer
local snap=Http:JSONDecode(own:GetAttribute('ShopSnapshot'))
combat.ShopAction:FireServer('Start',snap.revision);task.wait(1.5)
return 'time='..timer.Time.Text..' phase='..timer.Phase.Label.Text..' menus='..tostring(hud.SafeArea.Menus.Visible)..' runPhase='..tostring(run:GetAttribute('Phase'))
```
  Expected: `time=SANDBOX phase=PRACTICE menus=false runPhase=Practice`.

  d) **Server** (`serverCheck`): waves, jump, pause, end, grants and the new-run cleanup.
```lua
return serverCheck([==[
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat;local run=RS.RogueliteRunState
local Shop=require(game.ServerScriptService.ShopService);local Characters=require(game.ServerScriptService.CharacterService)
local p=game.Players:GetPlayers()[1];local enemies=workspace.RogueliteEnemies
add(Shop.phase=='Practice','still in Sandbox: no wave started on its own')
add(Shop.setWaves() and Shop.phase=='Shop' and run:GetAttribute('Phase')=='Shop' and run:GetAttribute('Wave')==1,'Waves: the wave-1 shop')
add(not Shop.setWaves(),'Waves again: refused, already running')
add(not Shop.jumpToWave(21) and not Shop.jumpToWave(0),'Jump refuses waves outside 1-20')
add(Shop.jumpToWave(18) and Shop.phase=='Combat' and run:GetAttribute('Wave')==18 and (run:GetAttribute('WaveEndsAt') or 0)>workspace:GetServerTimeNow(),'Jump to wave 18 starts it now')
task.wait(3)
local n=0;for _,npc in enemies:GetChildren() do if npc:GetAttribute('SpawnWave')==18 then n+=1 end end
add(n>0,'wave-18 enemies spawn ('..n..')')
add(Shop.adminPause(true) and run:GetAttribute('WaveEndsAt')==nil and run:GetAttribute('Paused')==true and run:GetAttribute('AdminPaused')==true,'Pause stops the clock')
local victim;for _,npc in enemies:GetChildren() do if npc.Name:match('^Zombie_%d+$') then victim=npc;break end end
local vname=victim and victim.Name;if victim then victim:FindFirstChildOfClass('Humanoid').Health=0 end
task.wait(3.5)
add(vname~=nil and enemies:FindFirstChild(vname)==nil,'paused: a killed enemy stays gone')
add(Shop.adminPause(false) and (run:GetAttribute('WaveEndsAt') or 0)>workspace:GetServerTimeNow() and run:GetAttribute('AdminPaused')==nil,'Resume restarts the clock')
task.wait(2.5)
add(vname~=nil and enemies:FindFirstChild(vname)~=nil,'Resume refills the wave')
add(Shop.endWave() and Shop.phase=='Shop' and run:GetAttribute('Wave')==19,'End this wave: shop, wave 19')
add(not Shop.endWave(),'End this wave with no wave running: refused')
local s=Shop.states[p];local cs=Characters.states[p]
add(Shop.adminShards(p,'Set',500) and s.shards==500,'shards set 500')
add(Shop.adminShards(p,'Add',100) and s.shards==600,'shards +100')
add(not Shop.adminShards(p,'Add',-1000) and s.shards==600,'shards never go below 0')
local level,pending=s.level,s.pendingLevels
add(Shop.adminLevel(p,'Add',1) and s.level==level+1 and s.pendingLevels==pending+1,'level +1 is an earned level-up')
add(Shop.adminLevel(p,'Set',1) and s.level==1 and s.pendingLevels==0,'level set 1 drops unspent level-ups')
local damage=cs.stats.Damage
add(Shop.adminItem(p,'protein') and cs.stats.Damage>damage,'give item: Protein Shake adds damage')
add(not Shop.adminItem(p,'weapon_01_1'),'weapons are not items')
combat:SetAttribute('AdminFreeze',true);combat:SetAttribute('TestZombieCountOverride',7);combat:SetAttribute('EnemyRoster','crab');run:SetAttribute('AdminPaused',true)
Shop.resetRun();task.wait(.3)
add(combat:GetAttribute('AdminFreeze')==nil and combat:GetAttribute('TestZombieCountOverride')==nil and run:GetAttribute('AdminPaused')==nil and combat:GetAttribute('EnemyRoster')==nil,'resetRun clears Freeze, Pause and Keep N alive and restores the Pine Valley mix')
add(Shop.phase=='Shop' and run:GetAttribute('Wave')==1,'back to the normal wave-1 shop')
]==])
```
  Expected: every line `PASS`. If `wave-18 enemies spawn` fails, check that the player is still on Pine Valley before debugging the spawner. Run `get_console_output`, then stop Play.

- [ ] **Step 5: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/combat/ShopService.luau && git commit -q -m "$(printf 'ShopService: Sandbox, Waves, jump, end and pause a wave, and admin grants\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 6: AdminService (the server end of the panel)

**Files:**
- Create: `studio-prototype/combat/AdminService.server.luau`
- Modify: `studio-prototype/combat/default.project.json`

- [ ] **Step 1: Write AdminService.** Create `studio-prototype/combat/AdminService.server.luau`:

```lua
-- ADMIN panel server (ADMIN_PANEL.md). Owns the RemoteFunction RogueliteCombat.AdminAction.
-- Each request: developer check by UserId (AdminConfig; everyone else gets no reply), a rate
-- limit, then AdminConfig.check on every argument. The owning service does the work, and a
-- successful action marks the run as a test run (no rewards).
-- Unsandboxed Script: it uses sandboxed modules (AdminConfig, MapConfig, ServerRole, ShopService)
-- and the spawner's ServerStorage.AdminSpawn bindable (RogueliteZombieChase, unsandboxed).
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local RS=game:GetService('ReplicatedStorage')
local SS=game:GetService('ServerStorage')
local SSS=game:GetService('ServerScriptService')
local combat=RS:WaitForChild('RogueliteCombat')
local Admin=require(combat:WaitForChild('AdminConfig'))
local Maps=require(combat:WaitForChild('MapConfig'))
local Role=require(SSS:WaitForChild('ServerRole'))
local Shop=require(SSS:WaitForChild('ShopService'))
local remote=combat:FindFirstChild('AdminAction') or Instance.new('RemoteFunction')
remote.Name='AdminAction';remote.Parent=combat
local NO_ARENA='No arena on this server'

local function alive(p)
 local char=p.Character;local h=char and char:FindFirstChildOfClass('Humanoid');local root=char and char:FindFirstChild('HumanoidRootPart')
 if h and root and h.Health>0 then return char,root end
end
-- The spawner exists wherever enemies can: not on lobby servers (RogueliteZombieChase).
local function spawner() return SS:FindFirstChild('AdminSpawn') end
local function arenaHasOthers(p)
 for _,q in Players:GetPlayers() do if q~=p and q:GetAttribute('StudioArea')=='Arena' and alive(q) then return true end end
 return false
end
-- Keep N alive (the old Z-mode plus mob picker): n enemies of the picked EnemyCatalog ids
-- ('' = the map's own mix), respawning as they die. 0 turns it off and brings back the map's
-- mix and the phase's normal count.
local function keepAlive(n,ids)
 local map=Maps.get(Role.activeMap())
 if n==0 then
  combat:SetAttribute('TestZombieCountOverride',nil);combat:SetAttribute('EnemyRoster',map and map.roster)
  combat:SetAttribute('ZombieCount',Shop.phase=='Combat' and Shop.waveEnemyCount() or 0)
  return true,'Keep alive off'
 end
 local list={};for id in ids:gmatch('[^,%s]+') do table.insert(list,id) end
 combat:SetAttribute('TestZombieCountOverride',n);combat:SetAttribute('EnemyRoster',#list>0 and table.concat(list,',') or (map and map.roster))
 combat:SetAttribute('ZombieCount',n)
 return true,'Keeping '..n..' alive'
end

local actions={}
-- Travel: instant in Studio's combined server. Published servers need plan C's teleports.
function actions.Travel(p,where)
 if not (RunService:IsStudio() and Role.get()=='Combined') then return false,'Needs lobby/match teleports (plan C)' end
 local char=alive(p);if not char then return false,'Respawn first' end
 if where=='Lobby' then
  local lobby=workspace:FindFirstChild('RogueliteLobby');local spawn=lobby and lobby:FindFirstChild('LobbySpawn')
  if not spawn then return false,'No lobby on this server' end
  p:SetAttribute('StudioArea','Lobby');char:PivotTo(CFrame.new(spawn.Position+Vector3.new(0,4,0)))
  -- Like the old LOBBY switch: nothing keeps running in an empty arena. A sandbox ends with a new run.
  if not arenaHasOthers(p) then if Shop.phase=='Practice' then Shop.resetRun() else Shop.stopWave() end end
  return true,'Lobby'
 end
 if not Role.setMap(where) then return false,'That map is not available here' end
 local spawn=Role.playerSpawn();if not spawn then return false,'No PlayerSpawn on '..where end
 p:SetAttribute('StudioArea','Arena');char:PivotTo(CFrame.new(spawn.Position+Vector3.new(0,4,0)))
 Shop.setPractice()
 return true,'Sandbox on '..where
end
-- Mobs.
function actions.Spawn(p,id,count)
 local sp=spawner();if not sp then return false,NO_ARENA end
 if combat:GetAttribute('ZombiesEnabled')~=true then return false,'Enemies spawn in Sandbox or during a wave' end
 local _,root=alive(p);if not root then return false,'Respawn first' end
 local made=sp:Invoke('Spawn',id,count,root.Position)
 if made==0 then return false,'No open floor 20-40 studs from you (or no model for that enemy)' end
 return true,'Spawned '..made
end
function actions.KeepAlive(p,n,ids) if not spawner() then return false,NO_ARENA end;return keepAlive(n,ids) end
-- Clear all: every enemy goes now. During a wave, turning Keep N alive off brings the wave's
-- normal count back.
function actions.ClearMobs(p)
 local sp=spawner();if not sp then return false,NO_ARENA end
 sp:Invoke('Clear');keepAlive(0,'')
 return true,'Cleared'
end
function actions.Freeze(p,on)
 local sp=spawner();if not sp then return false,NO_ARENA end
 sp:Invoke('Freeze',on);return true,on and 'Enemies frozen' or 'Enemies unfrozen'
end
-- Waves.
function actions.Sandbox(p) if not spawner() then return false,NO_ARENA end;Shop.setPractice();return true,'Sandbox · no waves' end
function actions.Waves(p)
 if not spawner() then return false,NO_ARENA end
 if not Shop.setWaves() then return false,'Waves are already running' end
 return true,'Waves from wave 1'
end
function actions.JumpWave(p,n) if not spawner() then return false,NO_ARENA end;Shop.jumpToWave(n);return true,'Wave '..n end
function actions.EndWave(p) if not Shop.endWave() then return false,'No wave running' end;return true,'Wave ended' end
function actions.Pause(p,on)
 if not Shop.adminPause(on) then return false,on and 'No wave running' or 'Not paused' end
 return true,on and 'Paused' or 'Resumed'
end
-- Player.
function actions.God(p,on) p:SetAttribute('AdminGod',on or nil);return true,on and 'God mode on' or 'God mode off' end
-- Weapons on/off: the old K test key.
function actions.Weapons(p,on)
 local states=combat:FindFirstChild('PlayerStates');local state=states and states:FindFirstChild(tostring(p.UserId))
 if not state then return false,'No weapon state yet' end
 state:SetAttribute('WeaponEnabled',on);return true,on and 'Weapons on' or 'Weapons off'
end
function actions.GiveItem(p,id) return Shop.adminItem(p,id) end
function actions.Shards(p,mode,n) return Shop.adminShards(p,mode,n) end
function actions.Level(p,mode,n) return Shop.adminLevel(p,mode,n) end
for _,name in Admin.Actions do assert(actions[name],'AdminService has no handler for '..name) end

local last={}
remote.OnServerInvoke=function(p,action,a,b)
 if not Admin.isAdmin(p) then return nil end -- non-developers get no reply
 if os.clock()-(last[p] or -math.huge)<.15 then return {ok=false,message='Slow down'} end
 last[p]=os.clock()
 if not Admin.check(action,a,b) then return {ok=false,message='Invalid request'} end
 local ran,ok,message=pcall(actions[action],p,a,b)
 if not ran then warn('AdminService:',action,ok);return {ok=false,message='Server error'} end
 if ok then Admin.markTestRun() end
 return {ok=ok==true,message=message or ''}
end
Players.PlayerRemoving:Connect(function(p) last[p]=nil end)
```

- [ ] **Step 2: Add it to the Rojo project.** In `studio-prototype/combat/default.project.json`, replace:

```json
      "ServerRoleBoot": {
        "$path": "../lobby/ServerRoleBoot.server.luau"
      }
```

  with:

```json
      "ServerRoleBoot": {
        "$path": "../lobby/ServerRoleBoot.server.luau"
      },
      "AdminService": {
        "$path": "AdminService.server.luau"
      }
```

- [ ] **Step 3: Check and install (unsandboxed).**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && python -c "import json;json.load(open('studio-prototype/combat/default.project.json'))" && echo "json ok" && ~/.rokit/bin/stylua --check studio-prototype/combat/AdminService.server.luau 2>&1 | grep -i "error parsing" && echo PARSE ERROR || echo ok
```

  Expected: `json ok`, `ok`. Then in Edit:

```lua
local s=create('Script','AdminService',SSS,'studio-prototype/combat/AdminService.server.luau')
return 'sandboxed='..tostring(s.Sandboxed)
```

  Expected: `sandboxed=false`.

- [ ] **Step 4: Play check through the real remote.** Start Play.

  a) **Client**: travel and mobs.
```lua
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat;local run=RS.RogueliteRunState
local remote=combat:WaitForChild('AdminAction',10);local lp=game.Players.LocalPlayer
local own=combat.PlayerStates:WaitForChild(tostring(lp.UserId))
local r={};local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local function call(...) task.wait(.2);local ok,res=pcall(remote.InvokeServer,remote,...);if ok and type(res)=='table' then return res end;return {ok=false,message='no reply: '..tostring(res)} end
local function count(match) local n=0;for _,npc in workspace.RogueliteEnemies:GetChildren() do if match(npc) then n+=1 end end;return n end
add(remote~=nil and remote:IsA('RemoteFunction'),'AdminAction exists')
add(run:GetAttribute('AdminTestRun')==nil,'a fresh Play is not a test run')
local res=call('Explode');add(res.ok==false and res.message=='Invalid request','unknown action refused')
add(run:GetAttribute('AdminTestRun')==nil,'a refused request marks nothing')
res=call('JumpWave',99);add(res.ok==false,'wave 99 refused')
res=call('God',true);add(res.ok and lp:GetAttribute('AdminGod')==true,'God mode on')
add(run:GetAttribute('AdminTestRun')==true,'the first admin action marks a test run')
res=call('Weapons',false);add(res.ok and own:GetAttribute('WeaponEnabled')==false,'Weapons off')
res=call('Travel','BeachCove');task.wait(1)
local pos=lp.Character:GetPivot().Position
add(res.ok and combat:GetAttribute('RunMap')=='BeachCove' and run:GetAttribute('Phase')=='Practice','Travel Beach Cove: Sandbox there')
add((Vector3.new(pos.X,0,pos.Z)-Vector3.new(700,0,300)).Magnitude<110 and lp:GetAttribute('StudioArea')=='Arena','standing on Beach Cove')
res=call('Spawn','crab',5);task.wait(.3)
add(res.ok and count(function(n) return n.Name:match('^Admin_') and n:GetAttribute('EnemyId')=='crab' end)==5,'Spawn 5 crabs: '..res.message)
res=call('KeepAlive',3,'snake');task.wait(2.5)
add(res.ok and count(function(n) return n.Name:match('^Zombie_%d+$') and n:GetAttribute('EnemyId')=='snake' end)==3,'Keep 3 snakes alive')
add(count(function(n) return n.Name:match('^Admin_') end)==5,'the crabs stay')
res=call('Freeze',true);add(res.ok and combat:GetAttribute('AdminFreeze')==true,'Freeze on')
res=call('Freeze',false);add(res.ok and combat:GetAttribute('AdminFreeze')==nil,'Freeze off')
res=call('ClearMobs');task.wait(1)
add(res.ok and #workspace.RogueliteEnemies:GetChildren()==0 and combat:GetAttribute('TestZombieCountOverride')==nil,'Clear all removes everything and stops Keep N alive')
return table.concat(r,'\n')
```

  b) **Client**: waves and player (same session).
```lua
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat;local run=RS.RogueliteRunState
local remote=combat.AdminAction;local lp=game.Players.LocalPlayer;local own=combat.PlayerStates[tostring(lp.UserId)]
local r={};local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local function call(...) task.wait(.2);local ok,res=pcall(remote.InvokeServer,remote,...);if ok and type(res)=='table' then return res end;return {ok=false,message='no reply: '..tostring(res)} end
local res=call('Waves');add(res.ok and run:GetAttribute('Phase')=='Shop' and run:GetAttribute('Wave')==1,'Waves: wave-1 shop')
res=call('JumpWave',5);add(res.ok and run:GetAttribute('Phase')=='Combat' and run:GetAttribute('Wave')==5,'Jump to wave 5')
res=call('Pause',true);add(res.ok and run:GetAttribute('Paused')==true and run:GetAttribute('WaveEndsAt')==nil,'Pause')
res=call('Pause',false);add(res.ok and run:GetAttribute('Paused')==nil and run:GetAttribute('WaveEndsAt')~=nil,'Resume')
res=call('EndWave');add(res.ok and run:GetAttribute('Phase')=='Shop' and run:GetAttribute('Wave')==6,'End this wave')
res=call('Shards','Set',777);task.wait(.3);add(res.ok and own:GetAttribute('Shards')==777,'Shards set 777')
res=call('Shards','Add',100);task.wait(.3);add(res.ok and own:GetAttribute('Shards')==877,'Shards +100')
local level=own:GetAttribute('RunLevel');res=call('Level','Add',1);task.wait(.3);add(res.ok and own:GetAttribute('RunLevel')==level+1,'Level +1')
res=call('Level','Set',1);task.wait(.3);add(res.ok and own:GetAttribute('RunLevel')==1,'Level set 1')
res=call('GiveItem','protein');add(res.ok,'Give item: '..res.message)
res=call('Weapons',true);add(res.ok and own:GetAttribute('WeaponEnabled')==true,'Weapons back on')
res=call('Travel','PineValley');task.wait(.5);add(res.ok and combat:GetAttribute('RunMap')=='PineValley' and run:GetAttribute('Phase')=='Practice','Travel Pine Valley')
res=call('Travel','Lobby');task.wait(1);add(res.ok and lp:GetAttribute('StudioArea')=='Lobby' and run:GetAttribute('Phase')=='Shop','Travel Lobby: the empty sandbox ends')
res=call('God',false);add(res.ok and lp:GetAttribute('AdminGod')==nil,'God mode off')
return table.concat(r,'\n')
```

  Expected: every line `PASS` in both. Run `get_console_output`, then stop Play.

- [ ] **Step 5: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/combat/AdminService.server.luau roguelite-planning/studio-prototype/combat/default.project.json && git commit -q -m "$(printf 'Add AdminService: checked AdminAction requests for travel, mobs, waves and player\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 7: The panel, and the old test tools go (one swap)

This task adds the ADMIN panel and removes the tools it replaces **together**, so developers never lose a tool between tasks.

**Files:**
- Create: `studio-prototype/ui/AdminPanelUI.luau`
- Create: `studio-prototype/ui/AdminPanel.client.luau`
- Modify: `studio-prototype/ui/CharacterStatsUI.luau` (require; `render` option; developer gate; emerald comment)
- Modify: `studio-prototype/ui/WeaponInventoryUI.luau` (tier and next free slot)
- Modify: `studio-prototype/ui/RogueliteUI.luau` (remove STATS/GEAR launchers, tabs, views and I/P keys)
- Modify: `studio-prototype/ui/RogueliteHUD.client.luau` (`UI.mount` call)
- Modify: `studio-prototype/ui/LobbyUI.luau` (the ADMIN spot)
- Modify: `studio-prototype/combat/RogueliteCombat.client.luau` (COMBAT TEST hidden for developers)
- Modify: `studio-prototype/lobby/RogueliteLobbyPreview.client.luau` (travel switch hidden for developers)
- Modify: `studio-prototype/combat/default.project.json`

- [ ] **Step 1: Check that Studio matches the repo.** In Edit:

```lua
local out={}
for _,e in {{RS.CharacterStatsUI,'studio-prototype/ui/CharacterStatsUI.luau'},{RS.WeaponInventoryUI,'studio-prototype/ui/WeaponInventoryUI.luau'},{RS.RogueliteUI,'studio-prototype/ui/RogueliteUI.luau'},{SPS.RogueliteHUD,'studio-prototype/ui/RogueliteHUD.client.luau'},{RS.LobbyUI,'studio-prototype/ui/LobbyUI.luau'},{SPS.RogueliteCombat,'studio-prototype/combat/RogueliteCombat.client.luau'},{SPS.RogueliteLobbyPreview,'studio-prototype/lobby/RogueliteLobbyPreview.client.luau'}} do table.insert(out,tostring(same(e[1],e[2]))) end
return table.concat(out,' ')
```

  Expected: seven `true`.

- [ ] **Step 2: CharacterStatsUI: the Player tab reuses it without its mob controls.** In `studio-prototype/ui/CharacterStatsUI.luau`:

  a) Replace:
```lua
local EnemyCatalog=require(combat:WaitForChild('EnemyCatalog'))
```
  with:
```lua
local EnemyCatalog=require(combat:WaitForChild('EnemyCatalog'))
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed; UI modules are unsandboxed
```

  b) Replace:
```lua
 function self:render(content,width)
```
  with:
```lua
 -- opts.skipMobs (the ADMIN panel's Player tab): leave out the population controls, which live
 -- in the panel's Mobs tab.
 function self:render(content,width,opts)
```

  c) Replace:
```lua
  local mobCols=usable<600 and 3 or 6;local mobRows=math.ceil(#EnemyCatalog.List/mobCols)
```
  with:
```lua
  -- Without the population panel, the controls below move up into its 250 px slot (238 + gap).
  if opts and opts.skipMobs then extra-=250 else
  local mobCols=usable<600 and 3 or 6;local mobRows=math.ceil(#EnemyCatalog.List/mobCols)
```

  d) Replace:
```lua
  extra+=zextra
```
  with:
```lua
  extra+=zextra
  end
```

  e) Replace:
```lua
  -- Emeralds (saved currency): quick grants plus an exact value. Studio only, never saved.
```
  with:
```lua
  -- Emeralds (saved currency): quick grants plus an exact value. In memory in Studio; a real,
  -- saved change to the developer's own account on a live server.
```

  f) Replace:
```lua
  if not game:GetService('RunService'):IsStudio() then
```
  with:
```lua
  if not Admin.isAdmin(player) then
```

- [ ] **Step 3: WeaponInventoryUI: any tier, into the next free slot.** In `studio-prototype/ui/WeaponInventoryUI.luau`:

  a) Replace:
```lua
-- UI sends only slot + catalogue ID. The server owns the equipped state.
```
  with:
```lua
-- UI sends only slot, catalogue ID and tier. The server owns the equipped state.
```

  b) Replace:
```lua
 local self={selected=1,filter='',state=state}
 local function updated() refresh() end
```
  with:
```lua
 -- Give weapon (ADMIN panel): the selected slot starts at, and moves on to, the next free slot.
 local function nextFree() for i=1,6 do if state['Slot'..i]:GetAttribute('WeaponId')=='' then return i end end end
 local self={selected=nextFree() or 1,filter='',state=state,tier=1}
 local function updated()
  if state['Slot'..self.selected]:GetAttribute('WeaponId')~='' then self.selected=nextFree() or self.selected end
  refresh()
 end
```

  c) Replace:
```lua
  label(content,'Instructions','Choose a slot, then equip any weapon. Duplicates allowed.',x,top+38,area,42,16)
```
  with:
```lua
  label(content,'Instructions','Choose a slot and a tier, then equip any weapon. Duplicates allowed.',x,top+38,area-236,42,16)
  for tier=1,4 do
   local b=button(content,'Tier'..tier,T.Roman[tier],x+area-232+(tier-1)*58,top+42,52,34,function() self.tier=tier;refresh() end,tier~=self.tier)
   b.Caption.TextSize=16
  end
```

  d) Replace:
```lua
   button(card,'Equip','Equip → '..self.selected,10,188,cardW-20,34,function() combat.EquipWeapon:FireServer(self.selected,d.id) end,true).Caption.TextSize=17
```
  with:
```lua
   button(card,'Equip','Equip '..T.Roman[self.tier]..' → '..self.selected,10,188,cardW-20,34,function() combat.EquipWeapon:FireServer(self.selected,d.id,self.tier) end,true).Caption.TextSize=17
```

- [ ] **Step 4: RogueliteUI: STATS and GEAR leave the arena HUD.** In `studio-prototype/ui/RogueliteUI.luau`:

  a) Replace:
```lua
function UI.mount(playerGui, studioPreview)
```
  with:
```lua
function UI.mount(playerGui)
```

  b) Replace:
```lua
 -- Full-screen menus (shop, inventory, stats, upgrades).
```
  with:
```lua
 -- Full-screen menus (shop, upgrades).
```

  c) Replace:
```lua
 local shopView
 local creativeInventory
 local levelUpView
```
  with:
```lua
 local shopView
 local levelUpView
```

  d) Replace:
```lua
 local inventoryTab=button(footer,"InventoryTab","Inventory",0,8,140,48,function() controller:ShowPreview("Inventory") end,true)
 local statsTab=button(footer,'StatsTab','Stats',0,8,100,48,function() controller:ShowPreview('Stats') end,true)
 local closeButton=button(footer,"Close","Back to game",280,8,210,48,close,true)
 closeButton.Modal=true -- Only while its menu is visible; releases first-person cursor.
 local tabModes={Shop=shopTab,Upgrades=upgradesTab,Inventory=inventoryTab,Stats=statsTab}
 local helpers={panel=panel,label=label,button=button,icon=icon}
 local statsView=require(RS:WaitForChild('CharacterStatsUI')).new(player,helpers)
 local shopModule=require(RS:WaitForChild('ShopUI'))
 shopView=shopModule.new(player,helpers,function() if render and (controller.Mode=='Shop' or controller.Mode=='Inventory') then render() elseif controller.Mode=='Stats' then local data=shopView:snapshot();if data then status.Text=data.message end end end)
 creativeInventory=require(RS:WaitForChild('WeaponInventoryUI')).new(player,helpers,function() if render and controller.Mode=='Inventory' then task.defer(render) end end)
 function controller:SetStats() end -- Stats render from live server attributes inside the Stats view.
 -- Right edge: menu launchers. Inventory and Stats are Studio test tools.
```
  with:
```lua
 local closeButton=button(footer,"Close","Back to game",280,8,210,48,close,true)
 closeButton.Modal=true -- Only while its menu is visible; releases first-person cursor.
 local tabModes={Shop=shopTab,Upgrades=upgradesTab}
 local helpers={panel=panel,label=label,button=button,icon=icon}
 local shopModule=require(RS:WaitForChild('ShopUI'))
 shopView=shopModule.new(player,helpers,function() if render and controller.Mode=='Shop' then render() end end)
 function controller:SetStats() end -- RogueliteHUD still calls this; stat edits live in the ADMIN panel.
 -- Right edge: menu launchers. The ADMIN button (developers only) is AdminPanel.client's, at
 -- LayoutOrder 5 after SETTINGS; the old GEAR and STATS test tools moved into that panel.
```

  e) Replace:
```lua
 launcher('OpenShop','store','SHOP',1,function() controller:ShowPreview('Shop') end)
 if studioPreview then
  launcher('InventoryButton','loadout','GEAR',2,function() controller:ShowPreview('Inventory') end)
  launcher('StatsButton','profile','STATS',3,function() controller:ShowPreview('Stats') end)
 end
```
  with:
```lua
 launcher('OpenShop','store','SHOP',1,function() controller:ShowPreview('Shop') end)
```

  f) Replace:
```lua
  if input.KeyCode==Enum.KeyCode.B then controller:ShowPreview('Shop')
  elseif studioPreview and input.KeyCode==Enum.KeyCode.I then if controller.Mode=='Inventory' then close() else controller:ShowPreview('Inventory') end
  elseif studioPreview and input.KeyCode==Enum.KeyCode.P then if controller.Mode=='Stats' then close() else controller:ShowPreview('Stats') end end
```
  with:
```lua
  if input.KeyCode==Enum.KeyCode.B then controller:ShowPreview('Shop') end
```

  g) Replace:
```lua
  if controller.Mode=='Inventory' then
   local height=creativeInventory:render(content,width)
   if width>=850 then content.EquippedWeapons.Position=UDim2.fromOffset(content.EquippedWeapons.Position.X.Offset,scroller.CanvasPosition.Y) end
   content.Size=UDim2.fromOffset(width,height);scroller.CanvasSize=UDim2.fromOffset(0,height)
   title.Text='CREATIVE INVENTORY';note.Text='Studio test tool  ·  Choose a slot  ·  Equip any weapon for free  ·  Duplicates allowed'
   return
  end
  if isShop then
```
  with:
```lua
  if isShop then
```

  h) Replace:
```lua
  if controller.Mode=='Stats' then
   local offset=shopView:debug(content,width)
   local inner=frame(content,'StatEditor',0,offset,width,1)
   local height=statsView:render(inner,width)+offset;inner.Size=UDim2.fromOffset(width,height-offset);content.Size=UDim2.fromOffset(width,height);scroller.CanvasSize=UDim2.fromOffset(0,height);return
  end
  local pendingCount=(shopView:snapshot() or {}).pendingLevels or 0
```
  with:
```lua
  local pendingCount=(shopView:snapshot() or {}).pendingLevels or 0
```

  i) Replace:
```lua
  controller.Mode=mode;title.Text=mode=='Stats' and 'CHARACTER STATS' or mode=='Inventory' and 'WEAPON INVENTORY' or (mode=='Shop' and 'SHOP' or 'LEVEL UP!')
  note.Text=mode=='Stats' and 'STUDIO PRACTICE  ·  Server-applied edits  ·  No saved rewards' or mode=='Inventory' and 'Owned weapons and items' or mode=='Shop' and '' or 'Upgrade offers appear here between waves'
```
  with:
```lua
  controller.Mode=mode;title.Text=mode=='Shop' and 'SHOP' or 'LEVEL UP!'
  note.Text=mode=='Shop' and '' or 'Upgrade offers appear here between waves'
```

  j) Delete this block (it only served the GEAR view):
```lua
 scroller:GetPropertyChangedSignal('CanvasPosition'):Connect(function()
  local slots=content:FindFirstChild('EquippedWeapons')
  if controller.Mode=='Inventory' and slots and scroller.AbsoluteSize.X-10>=850 then slots.Position=UDim2.fromOffset(slots.Position.X.Offset,scroller.CanvasPosition.Y) end
 end)
```

  k) Replace:
```lua
  local bw=(footerWidth-32)/5
  for i,b in {shopTab,upgradesTab,inventoryTab,statsTab,closeButton} do
```
  with:
```lua
  local bw=(footerWidth-16)/3
  for i,b in {shopTab,upgradesTab,closeButton} do
```

  Confirm nothing still refers to the removed pieces:

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning/studio-prototype" && grep -n -E "studioPreview|creativeInventory|statsView|inventoryTab|statsTab|'Inventory'|'Stats'" ui/RogueliteUI.luau
```

  Expected: no output.

  The Studio-only debug shards path (`ShopService.request('Shards')`, `ShopUI:debug`) stays. `ShopTests` and `RunXPTests` use it. Only its Stats-view UI is gone.

- [ ] **Step 5: RogueliteHUD: the new mount call.** In `studio-prototype/ui/RogueliteHUD.client.luau`, replace:

```lua
local view=UI.mount(playerGui,RunService:IsStudio())
```

  with:

```lua
local view=UI.mount(playerGui)
```

- [ ] **Step 6: LobbyUI: mark the ADMIN spot.** In `studio-prototype/ui/LobbyUI.luau`, replace:

```lua
 local settings=T.iconButton(right,'Settings','settings','SETTINGS',64,function() open('Settings') end);settings.LayoutOrder=4
```

  with:

```lua
 local settings=T.iconButton(right,'Settings','settings','SETTINGS',64,function() open('Settings') end);settings.LayoutOrder=4
 -- LayoutOrder 5 is the developers' ADMIN button, added by AdminPanel.client (ADMIN_PANEL.md).
```

- [ ] **Step 7: Hide the replaced Studio tools for developers only.**

  a) In `studio-prototype/combat/RogueliteCombat.client.luau`, replace:
```lua
if RunService:IsStudio()then
```
  with:
```lua
-- Developers use the ADMIN panel instead (Keep N alive, Weapons, End this wave); other Studio
-- testers keep this panel and its Z/K/X keys (ADMIN_PANEL.md).
if RunService:IsStudio() and not require(combat:WaitForChild('AdminConfig')).isAdmin(player) then
```

  b) In `studio-prototype/lobby/RogueliteLobbyPreview.client.luau`, replace:
```lua
if role~='Combined' then return end
local travel=workspace:WaitForChild('RogueliteLobby'):WaitForChild('StudioTravel')
```
  with:
```lua
if role~='Combined' then return end
-- Developers travel from the ADMIN panel's Travel tab instead (ADMIN_PANEL.md).
if require(RS:WaitForChild('RogueliteCombat'):WaitForChild('AdminConfig')).isAdmin(player) then return end
local travel=workspace:WaitForChild('RogueliteLobby'):WaitForChild('StudioTravel')
```

- [ ] **Step 8: Write the panel module.** Create `studio-prototype/ui/AdminPanelUI.luau`:

```lua
-- ADMIN panel window (ADMIN_PANEL.md): one green-theme window with Travel, Mobs, Waves and Player
-- tabs. Presentation and requests only: AdminService checks the developer and every argument.
-- The Player tab reuses the old STATS (CharacterStatsUI) and GEAR (WeaponInventoryUI) views.
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local T=require(RS:WaitForChild('UITheme'))
local combat=RS:WaitForChild('RogueliteCombat')
local Admin=require(combat:WaitForChild('AdminConfig'))
local Maps=require(combat:WaitForChild('MapConfig'))
local Enemies=require(combat:WaitForChild('EnemyCatalog'))
local Items=require(combat:WaitForChild('ShopCatalog'))
local Rules=require(RS:WaitForChild('RunSetupRules')) -- map display names
local C=T.Color
local M={}
local W,H=900,600 -- window content size; the Body inside is (W-36) x (H-58)
local CW=W-60 -- canvas width inside the scroll frame
local TABS={'Travel','Mobs','Waves','Player'}
local function left(l) l.TextXAlignment=Enum.TextXAlignment.Left;return l end
function M.new(player)
 local remote=combat:WaitForChild('AdminAction')
 local run=RS:WaitForChild('RogueliteRunState')
 local own=combat:WaitForChild('PlayerStates'):WaitForChild(tostring(player.UserId))
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='AdminPanel',ResetOnSpawn=false,DisplayOrder=60,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets})
 local helpers={panel=T.panel,label=T.label,button=T.button,icon=T.icon}
 local self={Screen=screen,tab='Travel',mobs={},spawnCount=5,keepCount=10,jump=1}
 local win,list,draw
 local statsView=require(RS:WaitForChild('CharacterStatsUI')).new(player,helpers)
 local inventory=require(RS:WaitForChild('WeaponInventoryUI')).new(player,helpers,function() if win and self.tab=='Player' then task.defer(draw) end end)
 -- One request: the server's reply shows as a toast, then the tab redraws with the new state.
 local function send(action,a,b)
  local ok,res=pcall(remote.InvokeServer,remote,action,a,b)
  local good=ok and type(res)=='table' and res.ok==true
  local message=ok and type(res)=='table' and res.message or 'No reply from the server'
  if message~='' then T.toast(screen,message,good and C.lime or C.negative) end
  if win then task.defer(draw) end
  return good
 end
 local function button(parent,name,text,x,y,w,callback,primary)
  local b=T.button(parent,name,text,x,y,w,40,callback,not primary);b.Caption.TextSize=17;return b
 end
 local function heading(parent,name,text,y) return left(T.label(parent,name,text,0,y,CW,30,22)) end
 local function note(parent,name,text,y,color) return T.text(parent,name,text,0,y,CW,22,15,color or C.muted) end
 -- Number field: Enter or clicking away calls onSet(number); anything else puts the value back.
 local function numberBox(parent,name,value,x,y,w,onSet)
  local box=T.make('TextBox',parent,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,40),BackgroundColor3=C.well,BorderSizePixel=0,TextColor3=C.white,Font=T.Font,TextSize=18,Text=tostring(value),ClearTextOnFocus=false})
  box.FocusLost:Connect(function() local v=tonumber(box.Text);if v and v==v then onSet(v) else box.Text=tostring(value) end end)
  return box
 end
 -- A label that follows one attribute while it is on screen.
 local function live(l,inst,attr,format)
  local function set() l.Text=format(inst:GetAttribute(attr)) end
  set();local conn=inst:GetAttributeChangedSignal(attr):Connect(set)
  l.Destroying:Connect(function() conn:Disconnect() end)
 end
 local tabs={}
 -- Travel: instant only where the lobby and the maps share one Studio server. Published servers
 -- need plan C's teleports, so the buttons stay disabled with the reason underneath.
 function tabs.Travel(c)
  local instant=RunService:IsStudio() and RS:GetAttribute('ServerRole')=='Combined'
  heading(c,'TravelTitle','Travel',0)
  note(c,'TravelNote',instant and 'Maps open in Sandbox (no waves). Lobby takes you back to the portals.' or 'Needs lobby/match teleports (plan C)',32,instant and C.muted or C.gold)
  local places={{id='Lobby',name='Lobby',order=0}}
  for id in Maps.Maps do local i=Rules.MapIndex[id];table.insert(places,{id=id,name=i and Rules.Maps[i].name or id,order=i or 99}) end
  table.sort(places,function(a,b) return a.order<b.order end)
  local here=player:GetAttribute('StudioArea')=='Lobby' and 'Lobby' or combat:GetAttribute('RunMap')
  local bw=math.min(260,(CW-8*(#places-1))/#places)
  for i,place in places do
   local b=button(c,'Go_'..place.id,place.name,(i-1)*(bw+8),64,bw,function() send('Travel',place.id) end,place.id==here)
   b.Interactable=instant
  end
  return 120
 end
 -- Mobs: pick types (any EnemyCatalog enemy or the Hammer boss). Spawn adds that many of each
 -- picked type; Keep N alive uses the picked regular types.
 local options={}
 for _,d in Enemies.List do table.insert(options,{id=d.id,name=d.name}) end
 table.insert(options,{id=Admin.BossId,name='Hammer boss'})
 local function picked(regularOnly)
  local out={}
  for _,o in options do if self.mobs[o.id] and not (regularOnly and o.id==Admin.BossId) then table.insert(out,o.id) end end
  return out
 end
 function tabs.Mobs(c)
  heading(c,'MobsTitle','Enemies',0)
  note(c,'MobsNote','Pick types. Spawn puts extras 20-40 studs around you: they fight normally and never respawn.',32)
  local cols=4;local cw=(CW-(cols-1)*8)/cols
  for i,o in options do
   local on=self.mobs[o.id]==true
   local b=button(c,'Mob_'..o.id,(on and '✓ ' or '')..o.name,((i-1)%cols)*(cw+8),64+math.floor((i-1)/cols)*48,cw,function() self.mobs[o.id]=not on or nil;draw() end,on)
   b.Caption.TextSize=15
  end
  local y=64+math.ceil(#options/cols)*48+8
  left(T.label(c,'CountLabel','Count',0,y,80,40,20))
  numberBox(c,'SpawnCount',self.spawnCount,90,y,90,function(v) self.spawnCount=math.clamp(math.floor(v),1,50);draw() end)
  button(c,'Spawn','Spawn',190,y,200,function()
   local ids=picked(false)
   if #ids==0 then T.toast(screen,'Pick an enemy first',C.negative);return end
   for i,id in ids do if i>1 then task.wait(.2) end;send('Spawn',id,self.spawnCount) end
  end,true)
  y+=60
  heading(c,'KeepTitle','Keep N alive',y);y+=32
  note(c,'KeepNote','Keeps this many of the picked types alive, respawning as they die. Nothing picked: the map mix.',y);y+=30
  numberBox(c,'KeepCount',self.keepCount,0,y,90,function(v) self.keepCount=math.clamp(math.floor(v),1,100);draw() end)
  button(c,'KeepOn','Keep alive',100,y,200,function() send('KeepAlive',self.keepCount,table.concat(picked(true),',')) end,true)
  button(c,'KeepOff','Stop',310,y,120,function() send('KeepAlive',0,'') end)
  local keeping=combat:GetAttribute('TestZombieCountOverride')
  T.text(c,'KeepStatus',keeping and ('Keeping '..keeping..' alive') or 'Off',444,y+9,CW-444,22,16,keeping and C.lime or C.muted)
  y+=60
  local frozen=combat:GetAttribute('AdminFreeze')==true
  button(c,'ClearAll','Clear all',0,y,200,function() send('ClearMobs') end)
  button(c,'Freeze',frozen and 'Unfreeze' or 'Freeze',210,y,200,function() send('Freeze',not frozen) end,frozen)
  note(c,'FreezeNote','Frozen enemies stop moving and attacking; you can still hit them.',y+48)
  return y+80
 end
 function tabs.Waves(c)
  local phase=run:GetAttribute('Phase');local sandbox=phase=='Practice';local fighting=phase=='Combat'
  heading(c,'ModeTitle','Mode',0)
  button(c,'Sandbox','Sandbox (no waves)',0,36,280,function() send('Sandbox') end,sandbox)
  button(c,'Waves','Waves',290,36,200,function() send('Waves') end,not sandbox)
  note(c,'ModeNote',sandbox and 'Sandbox: no wave timer and no shop. Enemies only come from Mobs.' or ('Wave '..tostring(run:GetAttribute('Wave'))..' · '..(fighting and 'fighting' or 'shop')),84)
  heading(c,'JumpTitle','Jump to wave (1-20)',120)
  numberBox(c,'JumpWave',self.jump,0,156,90,function(v) self.jump=math.clamp(math.floor(v),1,20) end)
  button(c,'Jump','Start this wave now',100,156,260,function() send('JumpWave',self.jump) end,true)
  local paused=run:GetAttribute('AdminPaused')==true
  local e=button(c,'EndWave','End this wave',0,216,220,function() send('EndWave') end);e.Interactable=fighting
  local p=button(c,'Pause',paused and 'Resume' or 'Pause',230,216,160,function() send('Pause',not paused) end,paused);p.Interactable=fighting
  return 272
 end
 function tabs.Player(c)
  local god=player:GetAttribute('AdminGod')==true
  local armed=own:GetAttribute('WeaponEnabled')~=false
  heading(c,'PlayerTitle','Player',0)
  button(c,'God',god and 'God mode: ON' or 'God mode: OFF',0,36,260,function() send('God',not god) end,god)
  button(c,'WeaponsToggle',armed and 'Weapons: ON' or 'Weapons: OFF',270,36,260,function() send('Weapons',not armed) end,armed)
  local shards=left(T.label(c,'ShardsLabel','',0,90,220,40,20))
  live(shards,own,'Shards',function(v) return 'Shards · '..tostring(v or 0) end)
  button(c,'Shards100','+100',230,90,110,function() send('Shards','Add',100) end)
  button(c,'Shards1000','+1000',350,90,120,function() send('Shards','Add',1000) end)
  numberBox(c,'ShardsSet',own:GetAttribute('Shards') or 0,480,90,140,function(v) send('Shards','Set',math.floor(v)) end)
  local level=left(T.label(c,'LevelLabel','',0,140,220,40,20))
  live(level,own,'RunLevel',function(v) return 'Level · '..tostring(v or 1) end)
  button(c,'LevelUp','+1',230,140,110,function() send('Level','Add',1) end)
  numberBox(c,'LevelSet',own:GetAttribute('RunLevel') or 1,350,140,120,function(v) send('Level','Set',math.floor(v)) end)
  note(c,'SetHint','Type a number and press Enter to set it.',188)
  heading(c,'ItemsTitle','Give item',220)
  local items={};for _,e in Items.List do if e.kind~='Weapon' then table.insert(items,e) end end
  local cols=4;local cw=(CW-(cols-1)*8)/cols
  for i,e in items do
   button(c,'Item_'..e.id,e.name,((i-1)%cols)*(cw+8),256+math.floor((i-1)/cols)*48,cw,function() send('GiveItem',e.id) end).Caption.TextSize=15
  end
  local y=256+math.ceil(#items/cols)*48+16
  -- Class, stat edits, heal and emeralds: the old STATS panel, without its mob controls (Mobs tab).
  local stats=T.frame(c,'StatsView',0,y,CW,1)
  local h=statsView:render(stats,CW,{skipMobs=true});stats.Size=UDim2.fromOffset(CW,h);y+=h+16
  -- Give weapon: the old GEAR inventory, any weapon and tier into the next free slot.
  heading(c,'GearTitle','Give weapon',y);y+=36
  local gear=T.frame(c,'Inventory',0,y,CW,1)
  h=inventory:render(gear,CW);gear.Size=UDim2.fromOffset(CW,h)
  return y+h+16
 end
 draw=function()
  if not win then return end
  local keep=list and list.Parent and list.CanvasPosition
  for _,child in win.Body:GetChildren() do child:Destroy() end
  T.tabs(win.Body,0,0,W-36,46,TABS,self.tab,function(id) self.tab=id;list=nil;draw() end)
  list=T.scroll(win.Body,'Content',0,56,W-36,H-58-56)
  local canvas=T.frame(list,'Canvas',0,0,CW,0)
  local height=tabs[self.tab](canvas)
  canvas.Size=UDim2.fromOffset(CW,height);list.CanvasSize=UDim2.fromOffset(0,height)
  if keep then list.CanvasPosition=keep end
  screen:SetAttribute('Tab',self.tab)
 end
 function self.Open()
  if win then return end
  win=T.window(screen,'AdminWindow','Admin',W,H,function() win=nil;list=nil;screen:SetAttribute('Open',false) end)
  screen:SetAttribute('Open',true);draw()
 end
 function self.Close() if win then win.Close() end end
 function self.Toggle() if win then self.Close() else self.Open() end end
 function self.Show(tab) if tab and tabs[tab] then self.tab=tab end;if win then list=nil;draw() else self.Open() end end
 -- Redraw live state (phase, wave, pause, freeze, map, area) while open. The Player tab redraws
 -- only after its own requests: rebuilding the stat editor on every shard pickup would fight typing.
 local function changed() if win and self.tab~='Player' then draw() end end
 for _,a in {'Phase','Wave','AdminPaused'} do run:GetAttributeChangedSignal(a):Connect(changed) end
 for _,a in {'AdminFreeze','TestZombieCountOverride','RunMap'} do combat:GetAttributeChangedSignal(a):Connect(changed) end
 player:GetAttributeChangedSignal('StudioArea'):Connect(changed)
 return self
end
return M
```

- [ ] **Step 9: Write the launcher.** Create `studio-prototype/ui/AdminPanel.client.luau`:

```lua
-- ADMIN panel launcher (ADMIN_PANEL.md). Developers only: adds the ADMIN button to the arena HUD's
-- launcher column and the lobby HUD's right-side buttons, and binds P. Showing it is cosmetic:
-- AdminService checks the developer on every request.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local Input=game:GetService('UserInputService')
local player=Players.LocalPlayer
local Admin=require(RS:WaitForChild('RogueliteCombat'):WaitForChild('AdminConfig'))
if not Admin.isAdmin(player) then return end
local T=require(RS:WaitForChild('UITheme'))
local panel=require(RS:WaitForChild('AdminPanelUI')).new(player)
local gui=player:WaitForChild('PlayerGui')
-- The spot in each HUD: LayoutOrder 5, right after SETTINGS (RogueliteUI 'Menu', LobbyUI 'Right').
local SPOTS={RogueliteHUD={path={'SafeArea','HUD','Menu'},size=58},RogueliteLobbyHUD={path={'HUD','Right'},size=64}}
local function mount(screen)
 local spot=SPOTS[screen.Name];if not spot then return end
 local parent=screen
 for _,name in spot.path do parent=parent:WaitForChild(name,10);if not parent then return end end
 if parent:FindFirstChild('AdminButton') then return end
 local b=T.iconButton(parent,'AdminButton','profile','ADMIN',spot.size,panel.Toggle);b.LayoutOrder=5
end
for _,screen in gui:GetChildren() do task.spawn(mount,screen) end
gui.ChildAdded:Connect(mount)
Input.InputBegan:Connect(function(input,processed)
 if processed or Input:GetFocusedTextBox() or input.KeyCode~=Enum.KeyCode.P then return end
 panel.Toggle()
end)
-- Studio-only hook so checks can open a tab without keyboard input (like LobbyUI's TestOpenWindow).
if RunService:IsStudio() then
 local hook=Instance.new('BindableEvent');hook.Name='TestShow';hook.Parent=panel.Screen
 hook.Event:Connect(function(tab) if tab then panel.Show(tab) else panel.Close() end end)
end
```

- [ ] **Step 10: Add both to the Rojo project.** In `studio-prototype/combat/default.project.json`:

  a) Replace:
```json
      "ChestScreenUI": {
        "$path": "../ui/ChestScreenUI.luau"
      }
```
  with:
```json
      "ChestScreenUI": {
        "$path": "../ui/ChestScreenUI.luau"
      },
      "AdminPanelUI": {
        "$path": "../ui/AdminPanelUI.luau"
      }
```

  b) Replace:
```json
        "RogueliteLobbyHUD": {
          "$path": "../ui/RogueliteLobbyHUD.client.luau"
        }
```
  with:
```json
        "RogueliteLobbyHUD": {
          "$path": "../ui/RogueliteLobbyHUD.client.luau"
        },
        "AdminPanel": {
          "$path": "../ui/AdminPanel.client.luau"
        }
```

- [ ] **Step 11: Parse-check, then sync everything in one Edit call** (so Play never sees half the swap).

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && python -c "import json;json.load(open('studio-prototype/combat/default.project.json'))" && echo "json ok" && for f in studio-prototype/ui/AdminPanelUI.luau studio-prototype/ui/AdminPanel.client.luau studio-prototype/ui/CharacterStatsUI.luau studio-prototype/ui/WeaponInventoryUI.luau studio-prototype/ui/RogueliteUI.luau studio-prototype/ui/RogueliteHUD.client.luau studio-prototype/ui/LobbyUI.luau studio-prototype/combat/RogueliteCombat.client.luau studio-prototype/lobby/RogueliteLobbyPreview.client.luau; do ~/.rokit/bin/stylua --check "$f" 2>&1 | grep -i "error parsing" && echo "PARSE ERROR $f" || echo "ok $f"; done
```

  Expected: `json ok` and nine `ok`. Then in Edit:

```lua
sync(RS.CharacterStatsUI,'studio-prototype/ui/CharacterStatsUI.luau')
sync(RS.WeaponInventoryUI,'studio-prototype/ui/WeaponInventoryUI.luau')
sync(RS.LobbyUI,'studio-prototype/ui/LobbyUI.luau')
sync(RS.RogueliteUI,'studio-prototype/ui/RogueliteUI.luau')
sync(SPS.RogueliteHUD,'studio-prototype/ui/RogueliteHUD.client.luau')
sync(SPS.RogueliteCombat,'studio-prototype/combat/RogueliteCombat.client.luau')
sync(SPS.RogueliteLobbyPreview,'studio-prototype/lobby/RogueliteLobbyPreview.client.luau')
local ui=create('ModuleScript','AdminPanelUI',RS,'studio-prototype/ui/AdminPanelUI.luau')
local ls=create('LocalScript','AdminPanel',SPS,'studio-prototype/ui/AdminPanel.client.luau')
return 'synced; AdminPanelUI sandboxed='..tostring(ui.Sandboxed)..' AdminPanel sandboxed='..tostring(ls.Sandboxed)
```

  Expected: `synced; AdminPanelUI sandboxed=false AdminPanel sandboxed=false`.

- [ ] **Step 12: Play check (developer UI).** Start Play. Run in **Client**:

```lua
local gui=game.Players.LocalPlayer.PlayerGui
local r={};local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local menu=gui:WaitForChild('RogueliteHUD'):WaitForChild('SafeArea'):WaitForChild('HUD'):WaitForChild('Menu');task.wait(2)
add(menu:FindFirstChild('AdminButton')~=nil and menu.AdminButton.LayoutOrder==5,'ADMIN button in the arena HUD, after SETTINGS')
add(menu:FindFirstChild('InventoryButton')==nil and menu:FindFirstChild('StatsButton')==nil,'GEAR and STATS launchers are gone')
local footer=gui.RogueliteHUD.SafeArea.Menus.Footer
add(footer:FindFirstChild('InventoryTab')==nil and footer:FindFirstChild('StatsTab')==nil and footer:FindFirstChild('ShopTab')~=nil,'footer keeps Shop, Upgrades and Back')
local lobby=gui:FindFirstChild('RogueliteLobbyHUD')
add(lobby~=nil and lobby.HUD.Right:FindFirstChild('AdminButton')~=nil,'ADMIN button in the lobby HUD')
add(gui:FindFirstChild('RogueliteCombatTestControls')==nil,'COMBAT TEST panel hidden for developers')
add(gui:FindFirstChild('StudioTravel')==nil,'LOBBY/ARENA switch hidden for developers')
local panel=gui:WaitForChild('AdminPanel',10)
local expect={
 Travel={'Go_Lobby','Go_PineValley','Go_BeachCove','TravelNote'},
 Mobs={'Mob_regular-zombie','Mob_crab','Mob_Hammer','SpawnCount','Spawn','KeepCount','KeepOn','KeepOff','ClearAll','Freeze'},
 Waves={'Sandbox','Waves','JumpWave','Jump','EndWave','Pause'},
 Player={'God','WeaponsToggle','Shards100','Shards1000','ShardsSet','LevelUp','LevelSet','Item_protein','StatsView','Inventory'},
}
for _,tab in {'Travel','Mobs','Waves','Player'} do
 panel.TestShow:Fire(tab);task.wait(.5)
 local window=panel:FindFirstChild('AdminWindow');local canvas=window and window.Window.Body.Content.Canvas
 local missing={}
 for _,name in expect[tab] do if not (canvas and canvas:FindFirstChild(name)) then table.insert(missing,name) end end
 add(#missing==0 and panel:GetAttribute('Tab')==tab,tab..' tab: '..(#missing==0 and 'all controls' or 'missing '..table.concat(missing,', ')))
 if tab=='Travel' and canvas then add(canvas.Go_PineValley.Interactable,'Travel is instant in combined Studio') end
 if tab=='Player' and canvas then
  add(canvas.StatsView:FindFirstChild('ClassPanel') and canvas.StatsView:FindFirstChild('Heal') and canvas.StatsView:FindFirstChild('Emeralds') and not canvas.StatsView:FindFirstChild('ZombieControls'),'Player: class, stats, heal and emeralds, without mob controls')
  add(canvas.Inventory:FindFirstChild('Tier4')~=nil and canvas.Inventory:FindFirstChild('WeaponCard_01')~=nil,'Player: give weapon with tiers')
 end
end
panel.TestShow:Fire(nil);task.wait(.3)
add(panel:FindFirstChild('AdminWindow')==nil,'the panel closes')
return table.concat(r,'\n')
```

  Expected: every line `PASS`.

- [ ] **Step 13: Look at it.** Run in **Client**: `game.Players.LocalPlayer.PlayerGui.AdminPanel.TestShow:Fire('Mobs')`. Take a plain `screen_capture` with **no camera arguments**. Repeat with `'Player'`, scrolled to the top.
  - Check: one green nine-slice window titled Admin, four tabs, a red X, nothing overlapping or cut off.
  - Close it with `TestShow:Fire(nil)`.
  - Run `get_console_output`, then stop Play.

- [ ] **Step 14: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/studio-prototype/ui/AdminPanelUI.luau roguelite-planning/studio-prototype/ui/AdminPanel.client.luau roguelite-planning/studio-prototype/ui/CharacterStatsUI.luau roguelite-planning/studio-prototype/ui/WeaponInventoryUI.luau roguelite-planning/studio-prototype/ui/RogueliteUI.luau roguelite-planning/studio-prototype/ui/RogueliteHUD.client.luau roguelite-planning/studio-prototype/ui/LobbyUI.luau roguelite-planning/studio-prototype/combat/RogueliteCombat.client.luau roguelite-planning/studio-prototype/lobby/RogueliteLobbyPreview.client.luau roguelite-planning/studio-prototype/combat/default.project.json && git commit -q -m "$(printf 'Add the ADMIN panel; move STATS, GEAR and the test keys into it\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

---

### Task 8: Verify the spec's test list

**Files:** none (verification). Run each step in its own fresh Play session unless it says otherwise. Before each Play, follow the shared-Studio rules. After each step, run `get_console_output` and stop Play.

- [ ] **Step 1: A non-developer sees nothing and is refused (2 players).** The MCP can't start a Studio local server, so **the user runs this checklist**. First call `list_roblox_studios` while the local server is up. If it lists the Server and Player windows, run the same code through them with `execute_luau` and record the output. Otherwise, give the user this list and record the step as "user-run, pending" until they report back. **Don't claim it passed without their answer.**
  1. In Studio: **Test** tab → **Clients and Servers** → **2 Players** → **Start**. Both test players (Player1, Player2) have non-developer UserIds.
  2. In each player window, check:
     - the arena HUD's right column shows only **SHOP** and **SETTINGS**, with no ADMIN button (also in the lobby);
     - pressing **P** does nothing;
     - the **COMBAT TEST** panel and the **LOBBY/ARENA** switch are still there (non-developer Studio testers keep them).
  3. In Player1's window, **View → Command Bar**:
     ```lua
     local c=game.ReplicatedStorage.RogueliteCombat;print(c.AdminAction:InvokeServer('God',true));c.EquipWeapon:FireServer(2,'01',4);c.EditPractice:FireServer('Emeralds','Add',100)
     ```
     Expected print: `nil`.
  4. In the Server window's command bar:
     ```lua
     local p=game.Players.Player1;local c=game.ReplicatedStorage.RogueliteCombat;print(p:GetAttribute('AdminGod'),game.ReplicatedStorage.RogueliteRunState:GetAttribute('AdminTestRun'),c.PlayerStates[tostring(p.UserId)].Slot2:GetAttribute('WeaponId'),p:GetAttribute('ProfileGems'))
     ```
     Expected: `nil nil  0` (the weapon id is empty and the emeralds are unchanged at 0).
  5. Stop the local server.

- [ ] **Step 2: Travel Lobby → Pine Valley → Beach Cove → Lobby.** Start Play. In **Client**:

```lua
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat;local run=RS.RogueliteRunState;local remote=combat:WaitForChild('AdminAction',10);local lp=game.Players.LocalPlayer
local r={};local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local function call(...) task.wait(.2);local ok,res=pcall(remote.InvokeServer,remote,...);return ok and type(res)=='table' and res or {ok=false,message=tostring(res)} end
local function at(center,radius) local p=lp.Character:GetPivot().Position;return (Vector3.new(p.X,0,p.Z)-Vector3.new(center.X,0,center.Z)).Magnitude<radius end
local res=call('Travel','Lobby');task.wait(1);add(res.ok and lp:GetAttribute('StudioArea')=='Lobby' and at(workspace.RogueliteLobby.LobbySpawn.Position,40),'Lobby')
res=call('Travel','PineValley');task.wait(1);add(res.ok and combat:GetAttribute('RunMap')=='PineValley' and run:GetAttribute('Phase')=='Practice' and at(workspace.PineValleyArena.PlayerSpawn.Position,40),'Pine Valley, in Sandbox')
res=call('Travel','BeachCove');task.wait(1);add(res.ok and combat:GetAttribute('RunMap')=='BeachCove' and run:GetAttribute('Phase')=='Practice' and at(workspace.BeachCoveExtras.PlayerSpawn.Position,40),'Beach Cove, in Sandbox')
res=call('Travel','Lobby');task.wait(1);add(res.ok and lp:GetAttribute('StudioArea')=='Lobby' and run:GetAttribute('Phase')=='Shop','back to the Lobby; the sandbox ended')
task.wait(.5);add(lp.PlayerGui.RogueliteLobbyHUD.Enabled,'the lobby HUD shows')
return table.concat(r,'\n')
```

  Expected: five `PASS`.

- [ ] **Step 3: 5 of each enemy and the boss on both maps; they don't respawn.** Same Play session. Do the following once for each map.
  1. **Client:** `game.ReplicatedStorage.RogueliteCombat.AdminAction:InvokeServer('Travel','PineValley')` (second pass: `'BeachCove'`).
  2. **Server** (direct), with `MAP` set to `'PineValleyArena'` (second pass: `'BeachCoveExtras'`):

```lua
local MAP='PineValleyArena'
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat;local Catalog=require(combat.EnemyCatalog) -- pure data: a copy is harmless
local spawner=game.ServerStorage.AdminSpawn;local templates=game.ServerStorage.RogueliteNPCs;local enemies=workspace.RogueliteEnemies
local r={};local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local p=game.Players:GetPlayers()[1];local root=p.Character.HumanoidRootPart
p:SetAttribute('AdminGod',true);combat.PlayerStates[tostring(p.UserId)]:SetAttribute('WeaponEnabled',false)
local marker=workspace[MAP].RogueliteZombieSpawn
local center=marker:GetAttribute('SpawnAreaCenter') or marker.Position;local radius=marker:GetAttribute('SpawnAreaRadius') or 60
local ids,skipped={}, {}
for _,d in Catalog.List do if templates:FindFirstChild(d.template) then table.insert(ids,d.id) else table.insert(skipped,d.id) end end
table.insert(ids,'Hammer')
local made={};for _,id in ids do made[id]=spawner:Invoke('Spawn',id,id=='Hammer' and 1 or 5,root.Position) end
local counts,outside={},0
for _,npc in enemies:GetChildren() do
 local key=npc:GetAttribute('IsHammerBoss') and 'Hammer' or npc:GetAttribute('EnemyId');counts[key]=(counts[key] or 0)+1
 local pos=npc:GetPivot().Position;if (Vector3.new(pos.X,0,pos.Z)-Vector3.new(center.X,0,center.Z)).Magnitude>radius+2 then outside+=1 end
end
for _,id in ids do local want=id=='Hammer' and 1 or 5;add(made[id]==want and counts[id]==want,MAP..' '..id..': made '..tostring(made[id])..', present '..tostring(counts[id])) end
add(outside==0,MAP..': every enemy inside the arena ring ('..outside..' outside)')
for _,npc in enemies:GetChildren() do local h=npc:FindFirstChildOfClass('Humanoid');if h then h.Health=0 end end
task.wait(3.5)
add(#enemies:GetChildren()==0,MAP..': none respawn after dying')
return table.concat(r,'\n')..'\nno model (not spawned): '..table.concat(skipped,', ')
```

  Expected: every line `PASS` on both maps. Record the "no model" list in the report: those enemies have no template yet, so the panel answers "no model for that enemy".

- [ ] **Step 4: Keep N alive, Clear all and Freeze.** In a fresh Play, re-run **Task 6 Step 4a** (Client). Expected: every line `PASS`.

- [ ] **Step 5: Sandbox and Waves.** In a fresh Play, re-run **Task 5 Step 4** a–d. Expected: every line `PASS`. Together they show:
  - Sandbox has no timer and no shop;
  - Waves jumps to 18;
  - End this wave works;
  - Pause and Resume work.

- [ ] **Step 6: Player tools and god mode against every damage path.** Start Play.

  a) **Server** (direct): lower health so Heal has something to do.
```lua
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait();local h=(p.Character or p.CharacterAdded:Wait()):WaitForChild('Humanoid')
task.wait(2);h.Health=math.floor(h.MaxHealth/2);return 'health '..h.Health
```

  b) **Client:** class, stats, heal, emeralds and give weapon through their real remotes.
```lua
local combat=game.ReplicatedStorage.RogueliteCombat;local lp=game.Players.LocalPlayer
local own=combat.PlayerStates:WaitForChild(tostring(lp.UserId));local edit=combat.EditPractice;local h=lp.Character.Humanoid
local r={};local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
edit:FireServer('Heal');task.wait(.4);add(h.Health==h.MaxHealth,'Heal to full')
edit:FireServer('Class','Gunner');task.wait(.4);add(own:GetAttribute('Class')=='Gunner','class Gunner')
edit:FireServer('Stat','MaxHP',250);task.wait(.4);add(own:GetAttribute('Stat_MaxHP')==250 and h.MaxHealth==250,'stat edit: max HP 250')
local gems=lp:GetAttribute('ProfileGems') or 0
edit:FireServer('Emeralds','Add',100);task.wait(.4);add(lp:GetAttribute('ProfileGems')==gems+100,'emeralds +100')
edit:FireServer('Emeralds','Set',gems);task.wait(.4);add(lp:GetAttribute('ProfileGems')==gems,'emeralds set back')
local free;for i=1,6 do if own['Slot'..i]:GetAttribute('WeaponId')=='' then free=i;break end end
combat.EquipWeapon:FireServer(free,'01',3);task.wait(.4);add(own['Slot'..free]:GetAttribute('WeaponId')=='01' and own['Slot'..free]:GetAttribute('Tier')==3,'give weapon: tier III into slot '..free)
combat.EquipWeapon:FireServer(free,'');edit:FireServer('Reset');task.wait(.2);edit:FireServer('Class','Brawler');task.wait(.4)
local remote=combat.AdminAction
local res=remote:InvokeServer('GiveItem','protein');add(res and res.ok,'give item')
task.wait(.2);res=remote:InvokeServer('Shards','Set',300);task.wait(.3);add(res and res.ok and own:GetAttribute('Shards')==300,'shards set')
task.wait(.2);res=remote:InvokeServer('Level','Add',1);add(res and res.ok,'level +1')
return table.concat(r,'\n')
```

  c) **Client:** go to Pine Valley in Sandbox, weapons off: `local a=game.ReplicatedStorage.RogueliteCombat.AdminAction;a:InvokeServer('Travel','PineValley');task.wait(.3);a:InvokeServer('Weapons',false);return 'ok'`.

  d) **Server** (direct): god mode against melee, projectiles, slams and the boss.
```lua
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat;local spawner=game.ServerStorage.AdminSpawn
local r={};local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
local p=game.Players:GetPlayers()[1];local char=p.Character;local h=char.Humanoid;local root=char.HumanoidRootPart
for _,f in char:GetChildren() do if f:IsA('ForceField') then f:Destroy() end end
p:SetAttribute('AdminGod',true);h.Health=h.MaxHealth
local lost,last=0,h.Health
local conn=h.HealthChanged:Connect(function(v) if v<last then lost+=last-v end;last=v end)
-- Rock-throwing crabs for projectiles: their template is known to exist (plan A spawned Beach Cove's roster).
for _,spec in {{'regular-zombie',3},{'rock-throwing-crab',3},{'tank-zombie',2},{'Hammer',1}} do spawner:Invoke('Spawn',spec[1],spec[2],root.Position) end
task.wait(14)
local melee,shots,slams,boss=0,0,0,0
for _,npc in workspace.RogueliteEnemies:GetChildren() do
 local id=npc:GetAttribute('EnemyId')
 if npc:GetAttribute('IsHammerBoss') then boss+=npc:GetAttribute('BossHits') or 0
 elseif id=='rock-throwing-crab' then shots+=npc:GetAttribute('EnemyHits') or 0
 elseif id=='tank-zombie' then slams+=npc:GetAttribute('SlamHits') or 0
 else melee+=npc:GetAttribute('EnemyHits') or 0 end
end
add(melee>0 and shots>0 and slams>0 and boss>0,('attacks landed: melee %d, projectiles %d, slams %d, boss %d'):format(melee,shots,slams,boss))
add(lost==0 and h.Health==h.MaxHealth,'god mode: no health lost ('..lost..')')
p:SetAttribute('AdminGod',nil);task.wait(3)
add(lost>0,'without god mode the same enemies hurt ('..math.floor(lost)..')')
p:SetAttribute('AdminGod',true);conn:Disconnect();spawner:Invoke('Clear');h.Health=h.MaxHealth
return table.concat(r,'\n')
```
  Expected: every line `PASS`. If one attack count is 0 only because that enemy never reached you, re-run with a longer wait before calling it a failure. Check that enemy's distance from you first.

- [ ] **Step 7: The test-run flag.** In a fresh Play:
  1. Re-run **Task 2 Step 9 c** (Server). Before it, set the flag with **Task 2 Step 9 a**. Expected: every line `PASS`.
  2. Run **Task 6 Step 4a** again. Its first seven result lines, through "the first admin action marks a test run", must be `PASS`.

  Together they show:
  - the first admin action sets the flag;
  - a new run clears it;
  - the guard blocks a `recordRun` grant.

- [ ] **Step 8: A normal play-test without the panel behaves as before.** Fresh Play. **Don't touch the panel.** The harness only speeds up waves, using the same functions the timer and the Start button use.

  a) **Server** (direct): stand in the Pine Valley arena, weapons off so no level-ups block Start.
```lua
local combat=game.ReplicatedStorage.RogueliteCombat
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait();local char=p.Character or p.CharacterAdded:Wait();task.wait(2)
char:PivotTo(CFrame.new(workspace.PineValleyArena.PlayerSpawn.Position+Vector3.new(0,4,0)));p:SetAttribute('StudioArea','Arena')
combat.PlayerStates[tostring(p.UserId)]:SetAttribute('WeaponEnabled',false);task.wait(.5);return 'ready'
```

  b) **Client:** a normal start.
```lua
local RS=game.ReplicatedStorage;local combat=RS.RogueliteCombat;local run=RS.RogueliteRunState;local Http=game:GetService('HttpService')
local lp=game.Players.LocalPlayer;local own=combat.PlayerStates:WaitForChild(tostring(lp.UserId));local gui=lp.PlayerGui
local r={};local function add(ok,msg) table.insert(r,(ok and 'PASS ' or 'FAIL ')..msg) end
add(run:GetAttribute('Phase')=='Shop' and run:GetAttribute('Wave')==1,'Play starts in the wave-1 shop')
add(run:GetAttribute('AdminTestRun')==nil and gui.RogueliteHUD:GetAttribute('TestRunShown')~=true,'not a test run; no TEST RUN tag')
combat.ShopAction:FireServer('Start',Http:JSONDecode(own:GetAttribute('ShopSnapshot')).revision)
local t0=os.clock();while run:GetAttribute('Phase')~='Combat' and os.clock()-t0<5 do task.wait(.1) end
add(run:GetAttribute('Phase')=='Combat' and (run:GetAttribute('WaveEndsAt') or 0)>workspace:GetServerTimeNow(),'Start begins wave 1 with a clock')
task.wait(.6);add(gui.RogueliteHUD.SafeArea.HUD.Timer.Time.Text:match('^%d%d:%d%d$')~=nil,'the HUD counts down')
task.wait(2);add(#workspace.RogueliteEnemies:GetChildren()>0,'wave enemies spawn')
return table.concat(r,'\n')
```

  c) **Server** (`serverCheck`): the timer's own `finishWave`, and the Start button's `request('Start')`, up to wave 6.
```lua
return serverCheck([==[
local Shop=require(game.ServerScriptService.ShopService);local Profiles=require(game.ServerScriptService.ProfileService)
local run=game.ReplicatedStorage.RogueliteRunState;local p=game.Players:GetPlayers()[1]
for _=1,5 do
 Shop.finishWave()
 local s=Shop.states[p];s.lastRequest=-1e6;Shop.request(p,'Start',s.revision)
 local t0=os.clock();while Shop.phase~='Combat' and os.clock()-t0<3 do task.wait(.1) end
end
add(Shop.phase=='Combat' and run:GetAttribute('Wave')==6,'normal waves reach wave 6')
add(run:GetAttribute('AdminTestRun')==nil,'still not a test run')
game.ServerStorage:SetAttribute('PlanDGems',Profiles.get(p).emeralds)
]==])
```

  d) **Server** (direct): die, and check the death screen's emeralds.
```lua
local Http=game:GetService('HttpService');local p=game.Players:GetPlayers()[1]
p.Character.Humanoid.Health=0;task.wait(1.5)
local info=p:GetAttribute('DeathInfo');local d=info and Http:JSONDecode(info)
return 'down='..tostring(p:GetAttribute('RunDown'))..' deathEmeralds='..tostring(d and d.emeralds)
```
  Expected: `down=true deathEmeralds=20` (Pine Valley Normal pays 20 per 5 waves: `RunSetupRules.runEmeralds`).

  e) **Client:** the death screen shows; give up.
```lua
local lp=game.Players.LocalPlayer;local shown=lp.PlayerGui:WaitForChild('DeathScreen').Enabled
game.ReplicatedStorage.RogueliteCombat.RunAction:FireServer('GiveUp');task.wait(1)
return 'deathScreen='..tostring(shown)
```
  Expected: `deathScreen=true`.

  f) **Server** (`serverCheck`): the reward path paid.
```lua
return serverCheck([==[
local Profiles=require(game.ServerScriptService.ProfileService);local Shop=require(game.ServerScriptService.ShopService)
local p=game.Players:GetPlayers()[1];local before=game.ServerStorage:GetAttribute('PlanDGems')
add(Profiles.get(p).emeralds==before+20,'give up pays the run: +'..tostring(Profiles.get(p).emeralds-before))
add(Profiles.get(p).bestWaves.PineValley==5,'best wave recorded: 5 waves passed')
add(Shop.phase=='Shop' and game.ReplicatedStorage.RogueliteRunState:GetAttribute('Wave')==1,'a new run starts at the wave-1 shop')
game.ServerStorage:SetAttribute('PlanDGems',nil)
]==])
```
  Expected: every line `PASS`. If `best wave recorded` fails because the Studio profile already had a higher Pine Valley best, record the old value. It's only a failure if `recordRun` wasn't called at all.

- [ ] **Step 9: Travel is disabled outside the combined Studio server.**
  1. In Edit: `workspace:SetAttribute('StudioServerRole','Match');workspace:SetAttribute('StudioMatchMap','PineValley')`.
  2. Start Play. In **Client**:

```lua
local gui=game.Players.LocalPlayer.PlayerGui;local panel=gui:WaitForChild('AdminPanel',15)
panel.TestShow:Fire('Travel');task.wait(.5)
local c=panel.AdminWindow.Window.Body.Content.Canvas
local res=game.ReplicatedStorage.RogueliteCombat.AdminAction:InvokeServer('Travel','BeachCove')
panel.TestShow:Fire(nil)
return 'buttons='..tostring(c.Go_Lobby.Interactable)..','..tostring(c.Go_BeachCove.Interactable)..' note='..c.TravelNote.Text..' server='..tostring(res and res.message)
```

  Expected: `buttons=false,false note=Needs lobby/match teleports (plan C) server=Needs lobby/match teleports (plan C)`.

  3. Stop Play. Clear the Studio test attributes (plan A Task 8 Step 5):

```lua
for _,a in {'StudioServerRole','StudioMatchMap','StudioMatchDifficulty'} do workspace:SetAttribute(a,nil) end
return tostring(workspace:GetAttribute('StudioServerRole'))
```

  Expected: `nil`.

- [ ] **Step 10: A short hands-on pass by the user.** Ask the user to start Play once and try the panel by hand: press **P**, click each tab, and click the ADMIN button in the arena and in the lobby. They should also check that typing in a number box doesn't trigger P. Record what they report.

- [ ] **Step 11: If any check failed:** use superpowers:systematic-debugging. Fix it in the repo, re-sync, re-run **that** step, and commit the fix with its own message. Don't mark the task done with a `FAIL` line.

---

### Task 9: Document it and report

**Files:**
- Modify: `ADMIN_PANEL.md` (status line; a new section at the end)

- [ ] **Step 1: Update the spec.** In `ADMIN_PANEL.md`, replace:

```markdown
Status: design approved by the user on 2026-09-28 ("go ahead"). Builds on plan A (server roles and maps).
```

  with:

```markdown
Status: design approved by the user on 2026-09-28 ("go ahead"). Built by plan D (`plans/2026-09-28-D-admin-panel.md`) on plan A (server roles and maps).
```

  Then add this section at the end of the file:

```markdown
## Implementation notes (plan D)

- **Weapons on/off** sits in the Player tab. It replaces the old K key, so developers don't lose it.
- **The COMBAT TEST panel (Z/K/X)** is hidden for developers, like the LOBBY/ARENA switch. Other Studio testers keep both.
- **Travel on published servers:** the "tooltip" is a line under the disabled buttons ("Needs lobby/match teleports (plan C)"). Roblox has no hover tooltip on disabled buttons.
- **Test runs** record no kills or best waves on the leaderboards. **Time played still counts**, because it measures time on the server, not a run result.
- **A new run (`Shop.resetRun`) starts clean.** It clears the flag, god mode, stat edits, the admin class pick, Freeze, Pause and Keep N alive, and brings back the map's enemy mix. Admin changes can never boost a later run that pays.
- **Waves from Sandbox** keeps your build, because it's the same test run. **Sandbox** runs at wave-1 enemy strength.
- **Clear all during a wave:** turning Keep N alive off brings back the wave's normal count, so the spawner refills the wave after the clear.
- **A Hammer boss from Mobs** drops no loot (`BossPractice`).
- **Old debug path:** the Studio-only debug shards path (`ShopService.request('Shards')`) stays for ShopTests and RunXPTests. Its old Stats-view UI is gone.
- **Plan B:** its run-end rewards must check `AdminConfig.isTestRun()`.
```

- [ ] **Step 2: Packaging check.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox/roguelite-planning" && ~/.rokit/bin/rojo build studio-prototype/combat/default.project.json -o "$TEMP/plan-d-check.rbxlx" && echo "rojo ok"
```

  Expected: `rojo ok`. If it fails on an entry this plan didn't add, record the error in the report and continue. If it fails on `AdminConfig`, `AdminService`, `AdminPanelUI` or `AdminPanel`, fix that path.

- [ ] **Step 3: Commit.**

```bash
cd "C:/Users/Jeremiah/Documents/ChatGPT/Roblox" && git add roguelite-planning/ADMIN_PANEL.md && git commit -q -m "$(printf 'Document how the admin panel was built\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')"
```

- [ ] **Step 4: Stop the local file server** started in Task 0.

- [ ] **Step 5: Report to the user.** Keep it short and plain:
  - The panel works in Studio: P or the ADMIN button, four tabs. Quote the Task 8 PASS lines as evidence, and list any "no model" enemies.
  - A run where the panel was used pays nothing. A normal run still pays: Task 8 Step 8 got +20 emeralds at wave 6.
  - Still to do by the user:
    - the 2-player non-developer check (Task 8 Step 1), if it's still pending;
    - the **published-game** checks: the ADMIN button shows for EggaRowls and not for a second account; emerald grants save; a run where the panel was used pays nothing;
    - travel between servers, which waits for plan C.

---

## Self-review against the spec

| Spec item | Where |
|---|---|
| One ADMIN panel for listed developers (EggaRowls, 341854066), Studio and published | Task 1 (`AdminConfig.UserIds`, `isAdmin`), Task 7 (`AdminPanel.client` developer gate) |
| Server checks the account on every action; non-developers get no reply; by UserId, not name | Task 1 (`isAdminId`), Task 3 (`EditPractice`, `EquipWeapon`, boss practice), Task 6 (`AdminAction` returns `nil`), Task 8 Step 1 |
| Replaces STATS, GEAR and the Z/K keys; never changes normal gameplay | Task 7 Steps 4 and 7; Conventions table; Task 8 Step 8 |
| Button at the bottom of the arena launcher column and beside the lobby's right-side buttons; P toggles; developers only | Task 7 Steps 4, 6 and 9; Task 7 Step 12 |
| Green nine-slice theme, one window, four tabs, a close button | Task 7 Step 8 (`T.window`, `T.tabs`); Step 13 capture |
| Travel: Lobby + one button per `MapConfig.Maps`; Studio instant via `setMap` + Sandbox + `PlayerSpawn`; Lobby like the old switch | Task 6 `actions.Travel`, Task 7 `tabs.Travel`, Task 8 Step 2 |
| Published travel disabled with "Needs lobby/match teleports (plan C)" | Task 6 (server message), Task 7 (disabled buttons + note), Task 8 Step 9 |
| Old LOBBY/ARENA switch hidden for developers, kept for others | Task 7 Step 7b, Task 7 Step 12, Task 8 Step 1 |
| Mobs: any enemy or boss, count 1–50, 20–40 studs on walkable floor, extra, no wave slots, no respawn | Task 1 rule, Task 4 (`AdminSpawn`, `Admin_nn`, `resetWave` keep, no-respawn guard), Task 8 Step 3 |
| Keep N alive (old Z-mode + mob picker) | Task 6 `keepAlive`, Task 7 Mobs tab, Task 6 Step 4a |
| Clear all removes every enemy incl. bosses and turns off Keep N alive | Task 4 `Clear`, Task 6 `ClearMobs` |
| Freeze stops moving and attacking; animations and damage still work; toggles | Task 4 (NPC loop + boss step), Task 4 Step 5 |
| Sandbox: no timer, no shop, wave counter hidden, phase `Practice`, enemies only from Mobs | Task 5 `setPractice`, Task 2 HUD (`SANDBOX`/`PRACTICE`, menus close), Task 5 Step 4c |
| Waves: normal run from wave 1; jump to 1–20; end this wave; pause/resume clock and spawning | Task 5 (`setWaves`, `jumpToWave`, `endWave`, `adminPause`), Task 4 spawn gate, Task 5 Step 4d |
| Player: class and stat edits (old STATS content) | Task 7 Step 2 (`skipMobs`) + Player tab; Task 8 Step 6b |
| Heal; god mode with no damage from any source | `CharacterStatsUI` Heal; Task 3 contact check + damage-path audit; Task 8 Step 6d |
| Give weapon (any weapon and tier, next free slot) and give item (any shop item) | Task 3 `EquipWeapon` tier, Task 7 Step 3, Task 5 `adminItem` |
| Shards +100/+1000/set; Level +1/set | Task 5 `adminShards`/`adminLevel`; Player tab |
| Emeralds +100/+1000/set to the saved profile (in memory in Studio, real on live) | Existing `CharacterStatsUI` panel (+100/+1K/+10K/set, unchanged per "today's STATS content"); Task 3 `onPracticeEmeralds` |
| Test run: first admin action sets `AdminTestRun` (Studio too); cleared by `resetRun` | Task 1 `markTestRun`; called by Task 3 (EditPractice, EquipWeapon) and Task 6 (AdminAction); Task 2/5 `resetRun` |
| Test run grants nothing: emeralds, wins, first win, best waves, leaderboard | Task 2 (`recordRun`, `LeaderboardService` kills/best wave, death screen shows 0). First-win bonuses don't exist yet (plan B). |
| HUD "TEST RUN" tag | Task 2 Steps 6–7 |
| `AdminConfig` shared + sandboxed; `AdminService` unsandboxed Script owning `AdminAction` | Tasks 1 and 6; Conventions sandbox table |
| `CharacterService` admin gates + god mode; `ShopService` modes and grants; spawner bindable; `EquipWeapon` for admins; `ServerRole` unchanged | Tasks 3, 4, 5, 6 (`ServerRole` is only called) |
| `AdminPanelUI`, `AdminPanel.client`, `RogueliteUI`, `LobbyUI`, `RogueliteHUD` client changes | Tasks 2 and 7 |
| Testing list | Task 8 Steps 1–8 (Step 1 is user-run if the MCP can't reach local-server windows) |
| Published-only checks: user runs, not claimed | Task 9 Step 5 |
| Out of scope (other players, server list, map editing) | Not built |

**Placeholders:** none. Every edit is an exact Replace against the file as it stands after the previous tasks, or a complete new file.

**Names used consistently:**
- Attributes: `AdminTestRun`, `AdminPaused` (on `RogueliteRunState`); `AdminFreeze`, `TestZombieCountOverride`, `EnemyRoster` (on `RogueliteCombat`); `AdminGod`, `StudioArea` (on the Player); `AdminSpawn` (on NPCs).
- Instances: `ServerStorage.AdminSpawn`, `RogueliteCombat.AdminAction`, `PlayerGui.AdminPanel`, and its `TestShow` hook.
- Action names: the 15 in `AdminConfig.Actions`, asserted by `AdminService` at load.

**Risks in the existing code that this plan works around:**
- **`execute_luau` runs in its own Luau VM,** so requiring a stateful service there boots a second copy. Service-internal checks run as a temporary Script (`serverCheck`).
- **`BossService.spawn` asserted Studio for practice bosses,** `RogueliteMeta.onPracticeEmeralds` checked `studio`, and `CharacterStatsUI` disabled every control outside Studio. Admin boss spawns, emerald grants and the stat editor would have silently failed on live servers.
- **`resetWave` destroys every non-boss enemy on any population change,** so admin extras get the same "kept while enemies are on" treatment as bosses.
- **`S.pause` is shared with the solo-death pause,** so the spawner freeze uses its own `AdminPaused` flag and normal death pauses behave as before.
- **Signals are deferred in this place,** so mode switches turn enemies off for one frame before turning them back on. The spawner and `BossEncounter` then see the old wave end.
- **`ServerRole.LIVE_ROLES=false` makes published servers Combined,** so "instant travel" also requires `RunService:IsStudio()`.
- **Admin state (stat edits, class, god mode, freeze, Keep N alive, roster) used to outlive the run.** `resetRun` now clears it, so a later paying run is never boosted.
- **Not fixed here (out of scope):** `RogueliteMeta` still hard-codes `MAP='PineValley'` for rewards and the death screen, so Beach Cove runs are paid and recorded as Pine Valley. That's plan B.
