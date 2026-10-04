# Admin Panel (developer tools)

Status: design approved by the user on 2026-09-28 ("go ahead"). Builds on plan A (server roles and maps).

## In one paragraph

One **ADMIN** panel for the developer (the user's account, EggaRowls) gives quick access to every test tool, in the lobby and every arena. It can:
- travel to any map;
- spawn any enemy or boss;
- switch between a **sandbox with no waves** and normal waves (jump to a wave, end or pause it);
- change the character (class, stats, god mode, weapons, items, shards, level, emeralds).

It works in Studio and in the published game, but only for listed developer accounts, and the server checks the account on every action. It replaces today's scattered Studio-only tools (STATS panel, GEAR inventory, the Z/K test keys) and never changes normal gameplay: a play-test that doesn't touch the panel behaves exactly as before.

## Decisions (user, 2026-09-28)

| Question | Decision |
|---|---|
| Where it works | Studio **and** the published game, only for developer accounts. |
| Rewards | A run where the panel was used is a **test run**: no emeralds or wins for the whole run, and no leaderboard kills or best waves from the first admin action on, for anyone in that run. |
| Default when entering an arena from the panel | **Sandbox (no waves).** |

## Who is a developer

`AdminConfig` (a shared, sandboxed module in `ReplicatedStorage.RogueliteCombat`) holds `UserIds = {341854066}` (EggaRowls) and `isAdmin(player)`.
- The **client** only uses it to show or hide the ADMIN button.
- The **server** checks it on every admin request. Nothing the client sends is trusted, and non-developers get no reply.
- The check is by UserId, never by name, because names can change.

## Opening it

- **Where the button goes:** a small **ADMIN** icon button. It sits at the bottom of the arena HUD's right-edge launcher column and beside the lobby HUD's right-side buttons (STORE / SKILLS / REWARDS / SETTINGS; since 2026-10-03 STORE / SKILLS / EGGS / SETTINGS / ATTACKS).
- **Hotkey:** **P** (today's STATS key) toggles it in both areas.
- **Who sees it:** developers only. Everyone else sees nothing new.
- **What it replaces:** the old **STATS** and **GEAR** launchers and footer tabs in the arena HUD, and their I/P keys, are removed. Their contents move into the panel.
- **Style:** the panel uses the existing green nine-slice UI theme (`UITheme`): one window, four tabs, and a close button.

## The four tabs

### Travel
- **Buttons:** **Lobby** and one per playable map (`MapConfig.Maps`: Pine Valley, Beach Cove, and future maps automatically).
- **Studio (Combined server):** travel is instant.
  - A map button sets the active map (`ServerRole.setMap`), switches the run to **Sandbox**, and moves the developer to that map's `PlayerSpawn`.
  - **Lobby** moves them to the lobby, like today's LOBBY/ARENA switch.
- **Published game:** the lobby and maps are separate servers. Travel uses plan C's teleports, starting a solo test match or returning to a lobby. Until plan C ships, the buttons that need a teleport are shown disabled with the tooltip "Needs lobby/match teleports (plan C)".
- **The old travel switch:** the Studio LOBBY/ARENA switch stays for non-developer Studio testers. For developers it's hidden, because Travel replaces it.

### Mobs
- **Spawn:** pick any regular enemy or boss (`EnemyCatalog` plus the Hammer boss), a count (1–50; bosses 1–5, so a mistyped number can't stall the server) and **Spawn**. They appear on the walkable floor of the current map around the developer, at 20–40 studs, and fight normally. These are **extra** enemies: they don't take wave slots and don't respawn.
- **Keep N alive:** pick enemy types and a number; the spawner keeps that many alive, respawning as they die. This is today's Z-mode plus mob picker.
- **Clear all:** removes every enemy, including bosses, and turns off Keep N alive.
- **Freeze:** enemies stop moving and attacking, while animations and damage still work, so you can inspect models and hitboxes. Press it again to unfreeze.

### Waves
- **Sandbox (no waves):**
  - No wave timer, no shop between waves, and the wave counter hidden.
  - The run's phase is `Practice`.
  - Enemies come only from Mobs.
- **Waves:** a normal run from wave 1 (the same code path as a real run), with:
  - **Jump to wave N** (1–20): starts wave N now.
  - **End this wave:** goes to the shop phase as if the timer ran out.
  - **Pause / Resume:** freezes the wave timer and enemy spawning.

### Player
- **Class** and **stat edits:** today's STATS panel content, unchanged.
- **Heal**, and **God mode**: takes no damage from any source.
- **Give weapon:** any weapon and tier into the next free slot (today's GEAR inventory), plus **Give item**: any shop item.
- **Shards:** +100 / +1000 / set. **Level:** +1 / set.
- **Emeralds:** +100 / +1000 / set, to the saved profile. That's in-memory in Studio, and on a live server it's a real change to the developer's own account.

## Test runs (no rewards)

- **What gets marked:** the first admin action of a run, outside Studio, sets `RogueliteRunState.AdminTestRun = true`. In Studio, profiles are in-memory anyway, but the flag is set there too, so the code path gets tested.
- **What a test run does:** rewards are blocked for the whole run: no emeralds, wins or first-win, including for a player who was already down when the flag was set (their record keeps its own test status, so a give-up after a reset still pays nothing). Leaderboard kills and best waves are blocked "from the first admin action on", because stats earned earlier in that run are already recorded live. The flag is cleared when a new run starts (`Shop.resetRun`), including when the last player leaves the server.
- **Where it's enforced:** today's reward entry point is `ProfileService.recordRun` (called from `RogueliteMeta`), plus `LeaderboardService`'s run submissions. Plan B's run-end rewards must check the same flag.
- **What players see:** the HUD shows a small "TEST RUN" tag while the flag is set, so nobody confuses it with a real run.

## Server design

| Piece | Change |
|---|---|
| `AdminConfig` (new, `ReplicatedStorage.RogueliteCombat`, sandboxed) | Developer UserIds, `isAdmin(player)`. |
| `AdminService` (new unsandboxed Script, `ServerScriptService`) | Owns the `AdminAction` RemoteFunction. It checks the admin, the rate limit and every argument, then routes to the services below and sets `AdminTestRun`. It's unsandboxed because it calls both sandboxed modules (CharacterService, ShopService, ServerRole) and unsandboxed ones (BossService). |
| `CharacterService` | Admin checks replace the `IsStudio()`-only gate on its existing actions (class, stats, heal, emeralds, boss). Adds god mode: `Service.contact` returns 0 for a player with `AdminGod`. Every other damage path must also go through `contact` or check `AdminGod`, and the plan lists and covers each one. |
| `ShopService` | Adds `setPractice()` (sandbox), `jumpToWave(n)`, `endWave()` and admin grants for shards, level and items. It reuses the existing `pause`/`resume`/`stopWave`/`resetRun`/`beginWave`/`finishWave`. |
| `RogueliteZombieChase` | Exposes a server-side BindableFunction, `ServerStorage.AdminSpawn`, with `('Spawn', id, count, position)`, `('Clear')` and `('Freeze', on)`. Extra enemies are named `Admin_nn` and never respawn. Freeze makes the movement and attack loop skip while `combat.AdminFreeze` is set. |
| `RogueliteCombat.server` | `EquipWeapon` (give weapon) accepts admins, not only Studio. |
| `ServerRole` | Unchanged. Travel uses `setMap` and `playerSpawn`. |
| `ProfileService` / `LeaderboardService` | Skip grants while `AdminTestRun` is set. |

## Client design

| Piece | Change |
|---|---|
| `AdminPanelUI` (new module, `ReplicatedStorage`) | The window and four tabs. The Player tab embeds the existing `CharacterStatsUI` and `WeaponInventoryUI` views. |
| `AdminPanel.client` (new LocalScript, `StarterPlayerScripts`) | For developers only: mounts the ADMIN button in whichever HUD is showing and binds P. |
| `RogueliteUI` | Removes the STATS and GEAR launchers, tabs and keys (they move into the panel). Adds a spot for the ADMIN launcher, filled only for developers. |
| `LobbyUI` | Adds a spot for the ADMIN button next to SETTINGS, filled only for developers. |
| `RogueliteHUD` | Shows a "TEST RUN" tag while `AdminTestRun` is set, and handles the `Practice` phase: no wave countdown. |

## Testing

**In Studio, with evidence:**
- A non-developer test account (a Studio local server with 2 players) sees no ADMIN button, and its admin requests are refused on the server.
- The developer can travel Lobby → Pine Valley → Beach Cove → Lobby.
- Spawn 5 of each enemy and the boss on both maps: the right types appear, inside the map, and they don't respawn.
- Keep N alive, Clear all and Freeze all work.
- Sandbox has no timer and no shop. Waves can jump to wave 18, end the wave, and pause and resume.
- Class, stats, heal and god mode work (no damage from contact, projectiles or the boss). Give weapon, item, shards, level and emeralds all work.
- `AdminTestRun` is set by the first admin action and cleared by a new run, and the test-run guard blocks a `recordRun` grant.
- A normal play-test without the panel behaves exactly as before: waves, shop, death screen, rewards path.

**Published game only** (the user runs this; not claimed until done): the ADMIN button shows for EggaRowls and not for a second account. Emerald grants save, and runs where the panel was used pay nothing.

## Out of scope

- Admin tools for other players: kicking, spectating others, server-wide announcements.
- A live server list, or joining a specific match.
- Editing maps from the panel.
