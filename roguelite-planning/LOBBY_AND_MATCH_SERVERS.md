# Lobby and Match Servers (MVP)

Status: design approved by the user on 2026-09-28. Plan A done (see the second status line); next are plans B and C.
Plan A (server roles and map folders) is implemented and verified in Studio Play on 2026-09-28. Plans B (run lifecycle) and C (teleports, save lock) are next.

## In one paragraph

Players join a **lobby server**. A party steps onto a pad and presses START. The lobby
reserves a private **match server**, saves everyone, and teleports the whole pad there.
The match server loads only the chosen map (Pine Valley or Beach Cove). Players who die
spectate the survivors and respawn when the wave ends, unless they buy a revive. The run ends
on a win at wave 20, when everyone is down, or when a player leaves. Rewards are saved, and a
results screen sends everyone back to a lobby server. Only the party is ever in a match
server, so the Tab player list shows just them.

## Decisions (user, 2026-09-28)

| Question | Decision |
|---|---|
| One Studio file or two places | **One file, two server types.** Reserved servers become match servers. |
| Beach Cove ending (no King Crab yet) | **Clear wave 20, no boss.** Pine Valley keeps the Hammer boss at wave 20. |
| Dying | **Spectate survivors** (‹ › to switch), **respawn at the end of the wave**. |
| Paid revives | **Unlimited per run; the price doubles**: 65, 130, 260, 520, 1040 R$, then stays at 1040. |
| Leaving | **Leave Run** between waves (and on the death screen) keeps rewards and returns to the lobby. |
| Endless / Play Again | Not in this version. Endless will get the same Cash Out → lobby later. |

## 1. Server roles

A new server-only module, `ServerRole` (in **ServerScriptService**), decides the role once, at server start:

- **Match** when this is a reserved server: `game.PrivateServerId ~= ""` and `game.PrivateServerOwnerId == 0`.
- **Lobby** in every other live server, including player-bought VIP servers.
- **Studio**: Workspace attribute `StudioServerRole`:
  - `Combined` is the default and keeps today's one-server setup: lobby and arenas together, and START walks you over.
  - `Lobby` and `Match` force one role. A forced Match reads Workspace attributes `StudioMatchMap` (default `PineValley`) and `StudioMatchDifficulty` (default `Normal`).

The role is published as the ReplicatedStorage attribute `ServerRole`. Client scripts read that attribute; they never require the module, because a client that required it would run the parking code.

**Areas.** Each area is one Workspace folder:
- `RogueliteLobby`
- `PineValleyArena` (new: the loose Pine Valley parts are gathered into it once, see §9)
- `BeachCoveArena`
- `BeachCoveExtras` (Beach Cove's PlayerSpawn, RogueliteZombieSpawn and hand-placed props; its kit rebuilds `BeachCoveArena` by deleting it)

At start, the role parents the areas it doesn't use into `ServerStorage.InactiveAreas`, so clients never download them:
- Lobby: keeps only the lobby.
- Match: keeps only its map.
- Combined: keeps everything.

**What runs where:**

| System | Lobby | Match | Combined (Studio) |
|---|---|---|---|
| Queue pads, run setup, chests, armory, store, skills | yes | no | yes |
| Weapon ring beside the player (RogueliteCombat) | yes | yes | yes |
| Attackable practice dummies + ATTACKS switch | yes | no (lobby only) | yes |
| Waves, enemies, boss, shop, level-ups, death screen | no | yes | yes |
| Profile loading and saving, Robux receipts | yes | yes | yes |
| Studio travel switch | no | no | yes |

### Lobby practice dummies (2026-09-28)

User request: make the lobby dummies attackable, with a clear way to turn attacks off so a ranged weapon doesn't fire nonstop.

- `lobby/LobbyPracticeDummies.server.luau` (ServerScriptService) wraps each `Asset=Practice_Dummy` mesh (3, one per side island) at runtime. Each gets a Model with an invisible HumanoidRootPart and a Humanoid, the `PracticeTarget` and `LobbyDummy` attributes, and the `RogueliteZombie` and `LobbyPracticeDummy` tags. Edit-mode geometry is unchanged, and the mesh keeps its collision (`MobCollision` skips dummies).
- `ZombieDeath.isPractice` extends the old Studio-only practice path to lobby dummies in any server: hits show numbers, but there is no death, kill credit, drops, lifesteal, statuses or rewards.
- `PlayerStates.<id>.LobbyAttacks` (server-owned, default ON) gates only LobbyDummy targets. `SetLobbyAttacks` accepts booleans only, one every 0.25 s. Arena targeting ignores it.
- The player-facing controls in `LobbyUI` are:
  - an ATTACKS ON/OFF button under SETTINGS (lime when on, charcoal when off, with a T or Y key tag);
  - T on keyboard, Y on gamepad;
  - a Dummy attacks row in Settings;
  - a toast on each change;
  - a PRACTICE DUMMY sign over each dummy that says what's happening and how to switch it, with wording for keyboard, gamepad or touch.
  - The signs follow the dummy's root as it streams in and out (StreamingEnabled).
- The setting lasts for the session, like the other settings.
- Verified in single-client Studio Play:
  - Attacks ON: a tier-1 Frying Pan at 4.5 studs landed 4 hits in 4 s. A tier-1 Glock at 20 studs (about the Rewards station's distance) fired 5 shots and landed 5 hits.
  - Attacks OFF, via the real T key and the Settings row: 0 shots and 0 hits. The button, the sign text and the toast all updated.
  - With dummy attacks OFF, arena zombies still took hits.
  - After 58 hits the dummy was alive, with no kill credit, shard, heart or death pop. Emeralds stayed at 0.
  - The console was clean.
- Not tested:
  - Multiple real clients (what other players see and their independent switches).
  - The live lobby role (`LIVE_ROLES=false`; the lobby HUD is still Studio-preview gated).
  - Mobile touch layout.

## 2. The trip: lobby → match

1. The host presses START on a pad, or PLAY claims a free pad (existing rules, still up to 4 players, Open or Solo).
2. The lobby server re-checks every member: map and difficulty unlocked (`RunSetupRules.validMap`), and class and weapon owned (`validLoadout`).
3. `TeleportService:ReserveServer(game.PlaceId)` returns an access code and a private server ID.
4. The lobby writes the match entry to a MemoryStore hash map, key = private server ID, expiry 1 hour. The entry is `{map, difficulty, members = {[userId] = {class, weapon}}}`. It is stored server-side and never passes through a client, so it can't be faked.
5. Each member's profile is **saved and released** (§6).
6. `TeleportService:TeleportAsync(game.PlaceId, members, options)`, with `options.ReservedServerAccessCode` set.
7. **If the teleport fails** (`TeleportInitFailed` or an error):
   - The lobby retries once.
   - Then it tells the players "Couldn't start the run, try again", frees the pad, and takes their profiles back.

**Arriving in the match:**
- The match server reads its entry using `game.PrivateServerId`.
- It kicks back to the lobby any player who isn't a listed member. This can't normally happen.
- After loading each member's profile, it re-checks the loadout against *that player's own save*. If the check fails, the player gets their class signature weapon.
- It waits for all listed members, up to 30 s, before wave 1 starts. Runs open on wave 1; the first shop comes after it (user direction, 2026-09-28). A member who arrives after wave 1 has begun waits like a downed player and spawns at the next wave end.
- If a player disconnects mid-run and rejoins the game, they land in a lobby server. There's no rejoining a match.
- **Plan C requirements** (from the plan A review):
  - `AvatarNormalizer` spawns players on join. A match server must hold that spawn until `ServerRole.setMap(entry.map)` has returned; `setMap` applies the map before it returns.
  - If `setMap` returns false (a missing or bad match entry), send the players back to a lobby.
  - Flip `ServerRole`'s `LIVE_ROLES` to true in the same change that ships the teleports.

## 3. In the match: map, enemies, starting weapon

- **Each map folder holds its own markers:**
  - `PlayerSpawn`, a SpawnLocation.
  - `RogueliteZombieSpawn`, which carries the existing `SpawnAreaCenter`/`SpawnAreaRadius` attributes and points at that map's no-climb folder and boundary.
  - Beach Cove gets new markers, placed inside its `BoundaryWall` and away from the `NoClimb` zones.
- **The active map** is the combat attribute `RunMap`:
  - The wave spawner (`RogueliteZombieChase`), boss, respawns and results all read it.
  - It replaces the fixed `workspace.RogueliteZombieSpawn` and the hard-coded `MAP='PineValley'` in `RogueliteMeta` (a current bug: Beach Cove runs pay out as Pine Valley).
- **Enemy roster** = the `EnemyCatalog` entries whose map matches `RunMap`:
  - Pine Valley: Zombie, Baby Zombie, Mutant Zombie.
  - Beach Cove: Crab, Snake, Hermit Crab, Rock-Throwing Crab (their NPC models are already in `ServerStorage.RogueliteNPCs`).
  - The Studio enemy picker still overrides it in Studio.
- **Boss:** only Pine Valley spawns the Hammer boss at wave 20. Beach Cove has no boss.
- **Starting weapon:** the member's validated class and weapon become `RunClass`/`RunWeapon`, and the ring shows that weapon from the moment they spawn. `ShopService.setStarter` also swaps live slots in a match until wave 1 begins, not only in the lobby.

## 4. Dying, spectating, respawning, revives

- **On death during a wave:**
  - The player stays down (existing `HoldRespawn`/`RunDown`).
  - The camera follows a living teammate. **‹ ›** (the arrows on screen, Q/E, or LB/RB) switches between them, with their name shown.
  - The death screen shows the next revive price, "You respawn when the wave ends", and **Leave Run**.
- **When the wave ends** (shop phase):
  - Every downed player respawns at the map's `PlayerSpawn` with full health.
  - Weapons, items, shards and level are kept; `resetPlayer` is not called.
- **Everyone down:**
  - The wave pauses (existing `Shop.pause`).
  - A 10-second countdown shows "Revive or the run ends".
  - A revive in that window resumes the run. Otherwise the run ends as a **Defeat**.
  - Solo players reach this state as soon as they die.
- **Paid revive (unlimited):**
  - The nth revive this run uses product `Revive1`…`Revive5` (65 / 130 / 260 / 520 / 1040 R$). From the 5th on it stays `Revive5`.
  - Existing behavior stays: revive where you fell at 50% health, 3 s shield, nearby enemies pushed back.
  - A revive bought after it can't be used is still refunded as 50 emeralds.
  - The count resets each run.
  - `ReviveLimitPerRun` is removed. Product IDs of 0 stay "not for sale" in live servers; Studio simulates the grant.

## 5. Ending a run

| Outcome | When | Emeralds (existing `RunSetupRules` formulas) |
|---|---|---|
| **Victory** | Wave 20 finishes (on Pine Valley it can't finish while the Hammer boss lives) | `winEmeralds`, plus `firstWinEmeralds` on the first win for that map + difficulty; the win is recorded |
| **Defeat** | Everyone is down and the 10 s countdown runs out | `runEmeralds(wave reached)` |
| **Left** | Leave Run, or disconnecting mid-run | `runEmeralds(wave reached)` for that player only; the rest play on |

Examples on Normal:
- Pine Valley Victory: 80, plus 100 on the first win.
- Beach Cove Victory: 160, plus 200 on the first win.
- A Defeat on wave 12 in Pine Valley: 40.

VIP bonus applies as it does today.

- **Rewards are granted once per player per run.** Each run gets a run ID, and the profile ignores a second grant with the same ID.
- **Results screen** (new, `RunResultsUI`), fed by a `RunResult` attribute on the player:
  - Shows VICTORY or DEFEAT, map and difficulty, waves reached, emeralds earned, and FIRST WIN or NEW BEST tags.
  - **Back to Lobby** button, or automatic after 20 s.
- **Returning:**
  1. The match server saves and releases each profile.
  2. It teleports players to a public lobby server with `TeleportAsync(game.PlaceId, players)`. A group teleported together lands in the same lobby server.
  3. In Combined Studio mode, Back to Lobby uses the existing in-place move.
- **Leave Run** is offered in the between-wave shop and on the death screen. Leaving mid-wave while alive isn't offered; closing the game counts as Left.

## 6. Saving between servers (session lock)

`ProfileService` gains a lock inside the saved record: `lock = {job = game.JobId, at = os.time()}`.

- **Load:**
  - If another server's lock is present, retry every 3 s for up to 15 s.
  - After that, take over, assuming that server crashed.
  - While waiting, the player sees "Loading your save…". Robux receipts return `NotProcessedYet` until the profile is loaded, and Roblox retries them later.
- **Every save** is an `UpdateAsync` that **cancels** if the stored lock belongs to a different server. A server that has lost the lock never writes its out-of-date copy; it stops saving that player.
- **Release:** the save before a teleport and the save on leaving clear the lock.
- **Studio** keeps in-memory profiles unless `EnableStudioDataStores=true` (unchanged). The lock logic is tested against a fake store.

## 7. Studio behavior and testing

**In Studio (verified with evidence before claiming):**
- Role selection for Combined, Lobby and Match. Areas are parked correctly, and each role runs only its systems.
- A forced Match loads Pine Valley and Beach Cove, with the right markers, roster and boss / no boss.
- Win, defeat, Leave Run, rewards granted once, the results screen and the auto return.
- Spectating (‹ › switching), respawn at wave end with the build kept, the 10 s everyone-down countdown.
- Revive price steps (simulated grants).
- Session lock against a fake store: the wait, the takeover after 15 s, a lost lock never writing, and receipts deferred until loaded.
- The katana fix: the ring shows the loadout starter in the lobby and in a match.

**Published game only (the user runs this checklist; not claimed until done):**
1. Join and land in a lobby server. Tab shows only lobby players.
2. Two accounts on one pad press START. Both land in the same match server, and Tab shows only those two.
3. A third account starts from another pad and lands in a different match server.
4. Die: spectate, switch with ‹ ›, respawn at wave end.
5. Revive prompts show 65, then 130 (needs real product IDs).
6. Leave Run returns you to the lobby, and the emerald count went up by the shown amount.
7. Win a Normal run (the Pine Valley boss, or Beach Cove wave 20), return, and the win shows as unlocked (Hard opens).
8. Leave the game mid-run, rejoin: you're in the lobby with emeralds for the waves reached.

## 8. Rule and doc updates

- `AGENTS.md`: the "explicitly approved limited death-screen revive" becomes the approved death-screen revive with unlimited uses and a doubling price, capped at 1040 R$ per revive.
- `MONETIZATION_AND_REWARDS.md`: update the revive section, the product list and the "not allowed" line about unlimited or repeated revive chains.
- `MonetizationConfig.luau`: the `Revive1`…`Revive5` products; remove `ReviveLimitPerRun`.
- `PROGRESSION_AND_SESSION_FLOW.md`: note that Keep Going / Endless and Play Again are deferred, and Leave Run is added.
- `studio-prototype/combat/LOADOUT.md`: the starter is the loadout weapon, not the katana.

## 9. What changes where

| Piece | Change |
|---|---|
| `ServerRole` (new, ServerScriptService; server only, clients read the `ReplicatedStorage.ServerRole` attribute) | Role detection, area parking, the `ServerRole` attribute |
| `MatchService` (new, ServerScriptService) | Reserve, write the match entry, save, teleport, retry/fail (lobby); read the entry, check members, wait for the party, return teleport (match) |
| `RogueliteLobbyPreview.server` | Runs live in the Lobby role (drop the Studio-only exit); `launch()` teleports via MatchService when not Combined; the travel remote stays Studio-only |
| `RogueliteLobbyPreview.client` | Plan C: drop its Studio-only exit for the half that hides the run HUD, level-up and damage overlays in the lobby (live lobbies need it); keep the travel switch Combined-only |
| `ProfileService` | Session lock, save-and-release, run-ID-deduped `recordRun` with win and first-win emeralds |
| `RogueliteMeta.server` | Map from `RunMap`; spectate/respawn-at-wave-end; 10 s everyone-down countdown; unlimited doubling revives; Leave Run; run end → results |
| `ShopService` | Win at the end of wave 20; respawn downed players at the shop phase; `setStarter` applies in a match until wave 1; Leave Run action |
| `RogueliteZombieChase.server`, `BossEncounter.server` | The active map's markers and roster; Hammer boss only on Pine Valley |
| `DeathScreenUI` | Spectate camera and ‹ › switching, next revive price, Leave Run, the countdown |
| `RunResultsUI` (new) | The results screen and Back to Lobby |
| `ShopUI` | Leave Run button |
| Workspace (done 2026-09-28, `lobby/GroupMapAreas.luau`) | Pine Valley lives in `Workspace.PineValleyArena`. Beach Cove is `BeachCoveArena` (rebuilt by its kit) plus `BeachCoveExtras` (PlayerSpawn, RogueliteZombieSpawn, hand-placed `Props`). **New map props go inside their map folder**; anything left loose in Workspace shows up on every server. Only the active map's `PlayerSpawn` is enabled (ServerRole). Studio: `Workspace.StudioServerRole` = `Lobby` / `Match` (with `StudioMatchMap`, `StudioMatchDifficulty`), unset = Combined. |

## Out of scope for this version

- Endless / Keep Going, Play Again with the same party, rejoining a match after disconnecting.
- The King Crab boss, the tutorial / first-join flow, cross-server party invites or friends-follow into matches.
- Monetization IDs themselves: the user creates the 5 revive products in the Creator Dashboard.

## Early plan B pieces (2026-09-29)

- `RogueliteMeta` reads the map from `RunMap` (the hard-coded `MAP='PineValley'` bug is fixed; Beach Cove runs now record and pay as Beach Cove).
- Best wave saves as each wave clears (`ShopService.onWaveCleared` → `ProfileService.recordProgress`), not only on Give Up. Clearing wave 20 records the win and pays the first-win bonus once. Wave emeralds still pay on Give Up until plan B's Leave Run / results screen.
- Every wave starts at full health (`ShopService.refillHealth`, also run when a wave ends).
- Still not built: plans B (Leave Run, victory/defeat results, spectate) and C (lobby → match teleports, session lock). Until C ships, Studio and live servers stay Combined, so lobby and arenas share one server.

## Plan C built (2026-10-01, from the code audit)

User decision 2026-10-01: the beta uses match servers. `ServerRole.LIVE_ROLES=true`.

- **Session lock:** `combat/ProfileLock.luau` (§6). 15 fake-store checks pass in `ProfileLockTests`. `ProfileService.handOff` / `reclaim` release the save before a teleport and take it back if the teleport fails.
- **Trips:** `lobby/MatchService.luau` (§2). Lobby pads reserve a server, write the MemoryStore entry `RogueliteMatchV1[PrivateServerId]`, hand off every save, and teleport the party (all or nobody). The match reads the entry, `setMap`s, admits only listed members (others go back to a lobby), re-checks each loadout against that player's save, and starts wave 1 when everyone is in, or 30 s after the first arrival. `AvatarNormalizer` holds spawns until the map is set.
- **Leaving:** in a match, the death screen's Give Up is Leave Run: rewards settle and the player returns to a public lobby. Closing the game also keeps rewards, because run emeralds pay as each wave clears (`ProfileService.settleRun`, once per stint).
- **Run end:** past wave 20 the run continues (Endless, per `PROGRESSION_AND_SESSION_FLOW.md`). The win and the wave-20 emeralds are saved at the wave-20 clear.
- **Not built yet (at the time):** the results screen, a between-waves Leave Run button, spectating, the 10 s everyone-down countdown and doubling revives. All but the doubling revives were built on 2026-10-02 (below).
- **Untested:** none of the teleport path runs in Studio. The published checklist in §7 must pass before beta players are invited.

## Plan B built (2026-10-02, synced to Studio the same day)

User direction 2026-10-01: Endless works like Brotato's (the same wave → shop loop keeps going past wave 20, enemies keep scaling), and players can **extract** (Leave Run) whenever they want instead of having to die.

- **Results screen** (`ui/RunResultsUI.luau`, fed by the `RunResult` attribute from `RogueliteMeta.setResult`): VICTORY! / DEFEAT / EXTRACTED, map and difficulty (and ENDLESS), emeralds the run paid, FIRST WIN +n, NEW BEST, waves cleared, level, best wave, and the weapons and items the run ended with. BACK TO LOBBY, or automatic after 20 s.
  - **Victory** = the run reached wave 20, whether the player then left or fell in Endless. Clearing wave 20 no longer ends anything: the shop shows "Endless (Wave 21)" in gold and the status line says "VICTORY! Keep going in Endless, or LEAVE RUN to take your rewards".
  - **Defeat** = everyone down and the last stand ran out, or the last one down left.
  - **Left (EXTRACTED)** = Leave Run before wave 20 while others play on, or between waves.
- **Leave Run** in the between-wave shop (above GO; tap twice, the second tap shows "LEAVE? KEEP n EMERALDS") and on the death screen (replaces GIVE UP; RunAction `LeaveRun`, the old `GiveUp` still works). Not offered mid-wave while alive. A player who leaves between waves has their body removed (so nothing in the arena can reach it) until they return.
- **Spectating:** a downed player with teammates still standing watches one of them (‹ ›, Q/E, LB/RB) and sees REVIVE and LEAVE RUN. **Downed players respawn at the map's spawn with full health when the wave ends**, keeping their build.
- **Last stand:** when everyone in the run is down (solo players on death), the wave stays paused and the death screen shows "REVIVE OR THE RUN ENDS · 10". An open Revive purchase prompt holds the clock (at least 5 s left once it closes). Then the run ends as a Defeat for everyone in it.
- **Return:** a match server teleports the returning group to a public lobby (`MatchService.toLobby`); the Combined Studio role walks them into the lobby; a Studio forced-Match, or a teleport that fails, puts them back in the arena.
- **Starter tiers:** the loadout starter enters the run at its owned tier (a Tier II Frying Pan starts at Tier II). See GEAR_POWER.md for the matching map scaling.
- **Analytics:** see PLAYTEST_ANALYTICS.md.
- **Still not built:** Play Again with the same party; rejoining a match after disconnecting. (Doubling revives: built, below.)
- **Not tested yet:** everything above needs a Studio Play pass (single player: die solo, revive, let the clock run out, leave between waves, win wave 20 and keep going), and the multi-player parts (spectating, wave-end respawn, last stand with two players, group return) need two real clients or the published game.

## Doubling revives built (2026-10-02, plan J items 6 and 11)

- **Revives:** no limit per run. The nth revive buys product `Revive<n>` from `MonetizationConfig` (65 / 130 / 260 / 520 / 1040 R$; from the 5th on, `Revive5`). The count resets when the player's run ends and when a new run starts at wave 1. `ReviveLimitPerRun` is gone.
  - The client sends `PurchaseRequest('Revive')`; `RogueliteMeta` turns that into this player's next step, so a client can't ask for a cheaper product. Receipts for any step grant the same revive (or 50 emeralds when it can't be used any more).
  - `DeathInfo` carries `revive` (which revive this is), `revivePrice` and `nextRevivePrice`. The death screen's button shows "REVIVE · R$ 130" and the note says "Back with 50% health · next one R$ 260".
  - An open prompt for any step holds the last stand's clock. Analytics `RevivePrompt` and `Revived` carry the revive number.
  - Product IDs are 0 until the user creates the five products in the Creator Dashboard; Studio simulates the grant, live servers say "Not on sale yet".
- **Last-stand clock on the splash:** "REVIVE OR THE RUN ENDS · n" now shows under YOU DIED from the first frame (it pops on each new second), and the summary title takes over when the splash fades. So the 10 s stays (user: fine if the countdown is visible the whole time).
- **Not tested yet:** Studio Play (solo: die, revive at 65, die again and see 130, let the clock run out). Real prompts need the five product IDs and the published game.
