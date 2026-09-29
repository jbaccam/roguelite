# Server roles and map folders (plan A) — validation, September 28, 2026

## Delivered

- `ServerRole` picks Lobby, Match or Combined and publishes it as the `ReplicatedStorage.ServerRole` attribute. Areas a role doesn't use wait in `ServerStorage.InactiveAreas`, so clients never stream them.
- Pine Valley lives in `Workspace.PineValleyArena`. Beach Cove is `BeachCoveArena` plus `BeachCoveExtras` (PlayerSpawn, RogueliteZombieSpawn, hand-placed props). Only the active map's PlayerSpawn is enabled.
- `RunMap` switches the active map, its spawn and its enemy roster. Combat rays and the lobby server follow the role and the active map, and the lobby client scripts stay out of match servers.
- Match servers start the `AssetPreloader` from the arena HUD; every other role starts it from the lobby HUD.
- Design: `../../LOBBY_AND_MATCH_SERVERS.md`. Plan: `../../plans/2026-09-28-A-server-roles-and-maps.md`.

## Evidence

Studio Play in the connected roguelite place, one local player, 2026-09-28. Each run was checked with server and client scripts, then Play was stopped. Only the Studio attributes listed under Reproducing changed between runs.

- **Combined:** role Combined; all four areas in Workspace; `RunMap` defaults to PineValley; only the Pine spawn is enabled. Setting `RunMap` to BeachCove enables the Beach spawn and applies the Beach roster. 4 Beach enemies spawned, all Beach Cove types and all inside the ring. Setting it back to PineValley restores Pine. A client Play request for DesertBasin returned `false Coming soon`. The preloader loaded 137 images.
- **Lobby:** role Lobby; the lobby is in Workspace; the three map folders are parked; LobbySpawn is enabled; the player is in the lobby; there is no `RogueliteEnemies` folder. Client: `lobbyHUD=true`, `travelSwitch=false`. A Play request was refused with "Runs start in the published game. Use the combined Studio mode to play here".
- **Match, Beach Cove:** role Match; the lobby and Pine Valley are parked, and only those two; the Beach folders are in Workspace; `RunMap` is BeachCove, Normal; the Beach spawn is enabled and the player spawned on the beach. No Hammer boss appears. Client: `lobbyHUD=false`, `travelSwitch=false`. Preload count 137. No infinite yield on `RogueliteLobby`.
- **Match, Pine Valley:** the lobby and the Beach folders are parked; Pine Valley is active; the player spawned at the Pine spawn; the Hammer boss spawns.
- **Katana regression check:** in Combined, `slot1=01` (Frying Pan), so the earlier fix survived.
- **Beach roster follow-up:** snakes and lava slimes spawn, fight and respawn after their 10 clip modules were installed. Before that, the snake Idle clip wait blocked its animation.
- **Studio console:** no errors, and no lines mentioning capability, Sandboxed or a missing marker. The expected `ServerRoleBoot` warning appears in forced Lobby and Match.
- The Rojo combat project (`../combat/default.project.json`) builds.

## Not tested

- Live lobby-to-match teleports. Plan C ships them, and `LIVE_ROLES` stays `false` until then.
- Multiple real clients. Every run above had one local player.
- Published DataStores, session locks and saves.
- The published game with `LIVE_ROLES=false`. Live servers are meant to stay Combined; that path only ran in Studio.
- Reserved-server detection (`PrivateServerId` and `PrivateServerOwnerId`). `ServerRoleTests.luau` covers the decision function only.
- The final-cleanup change that gates the arena HUD's preloader on `ServerRole == Match`. It was synced to Studio and compared with the file, but Play was not re-run afterwards.

## Reproducing in Studio

Set these Workspace attributes in Edit before pressing Play. Studio defaults to Combined when `StudioServerRole` is unset.

| Attribute | Value | Effect |
|---|---|---|
| `StudioServerRole` | unset | Combined: lobby and all maps in one server, `RunMap` defaults to PineValley |
| `StudioServerRole` | `Lobby` | Lobby only; the map folders are parked; runs are refused |
| `StudioServerRole` | `Match` | Match only; the lobby and unused maps are parked |
| `StudioMatchMap` | `PineValley` (default) or `BeachCove` | Map a forced Match plays |
| `StudioMatchDifficulty` | `Normal` (default) | Difficulty a forced Match plays |

Clear them afterwards so the place returns to the normal combined preview:

```lua
for _,a in {'StudioServerRole','StudioMatchMap','StudioMatchDifficulty'} do workspace:SetAttribute(a,nil) end
```

The check scripts are in Task 8 ("Verify every role in Play") of `../../plans/2026-09-28-A-server-roles-and-maps.md`. A forced Lobby or Match logs one expected `ServerRoleBoot` warning at start. Look at the console for errors and for any line mentioning `capability` or `Sandboxed`.
