# Plan I: run end, Gear Power and play-test analytics (record)

**Asked 2026-10-01** (user): implement the results screen, Leave Run between waves (extract any time, Endless included), spectating after death and the 10 s everyone-down countdown; carry Armory upgrades into runs; make gear levels scale to the maps; track gameplay for play-tests and make sure the stats that unlock content are saved.

**Built 2026-10-02 and synced to Studio the same day** (user: "yes push it all in"). The guarded sync wrote 12 scripts and created RunAnalytics and RunResultsUI as one undo step. Afterwards all 14 matched the repo, kept their sandbox settings and compiled, and GearPowerTests passed 78 checks on the Studio scripts. Not play-tested yet.

## What changed

| Area | Files |
|---|---|
| Gear Power (GEAR_POWER.md) | `combat/CharacterStats.luau`, `combat/CharacterService.luau`, `combat/CombatEffectsService.luau`, `lobby/RunSetupRules.luau`, `ui/RunSetupUI.luau`, `ui/ArmoryUI.luau`, tests `combat/GearPowerTests.luau` |
| Starter keeps its owned tier | `combat/ShopService.luau` |
| Run end (LOBBY_AND_MATCH_SERVERS.md "Plan B built") | `combat/RogueliteMeta.server.luau`, `combat/ProfileService.luau`, `ui/RunResultsUI.luau` (new), `ui/DeathScreenUI.luau`, `ui/ShopUI.luau`, `ui/RogueliteUI.luau`, `combat/default.project.json` |
| Analytics (PLAYTEST_ANALYTICS.md) | `combat/RunAnalytics.luau` (new), hooks in `RogueliteMeta`, `ProfileService` (`markRunStart/End`), `CharacterService` (attacker on `onDamaged`) |

## Verification so far

- StyLua parse check: every changed file parses.
- `GearPowerTests`: **PASS, 78 checks** (Edit-mode harness on unparented copies of the repo code, Studio's real `MapBossDefs`). Boss health at Normal solo: Hammer 18,000, King Crab 26,640, Pharaoh 35,280, Frost Cyclops 43,920, Dragon 52,560.
- Independent code review of the diff (subagent).
- **Not run yet:** any Studio Play test. No claim that the flows below work until they are played.

## Studio sync (after the user says "push it to Studio")

Guarded like `ui/SyncUIRuntime.luau`: a Studio script is written only when every line Studio has beyond the last commit is also in the repo file. Two files are shared with the quests session's uncommitted work (`ProfileService`, `RogueliteMeta`): push the committed versions (HEAD), which hold only this plan's changes.

| Repo file | Studio | Sandboxed |
|---|---|---|
| combat/CharacterStats.luau | ReplicatedStorage.RogueliteCombat.CharacterStats | yes |
| combat/CharacterService.luau | ServerScriptService.CharacterService | yes |
| combat/CombatEffectsService.luau | ServerScriptService.CombatEffectsService | yes |
| combat/ShopService.luau | ServerScriptService.ShopService | yes |
| combat/ProfileService.luau | ServerScriptService.ProfileService | no |
| combat/RogueliteMeta.server.luau | ServerScriptService.RogueliteMeta | no |
| combat/RunAnalytics.luau (new) | ServerScriptService.RunAnalytics | no |
| lobby/RunSetupRules.luau | ReplicatedStorage.RunSetupRules | no |
| ui/RunResultsUI.luau (new) | ReplicatedStorage.RunResultsUI | no |
| ui/DeathScreenUI.luau, RogueliteUI.luau, RunSetupUI.luau, ArmoryUI.luau | ReplicatedStorage.* | no |
| ui/ShopUI.luau | ReplicatedStorage.ShopUI | yes |

Order: RunAnalytics before RogueliteMeta (it requires it); RunResultsUI before RogueliteUI; CharacterStats before CharacterService, RunSetupRules and the UI.

`SyncRunEndRuntime.luau` does this. Serve `cur` = the files at the latest commit that has plan I (3cb6462 or later) and `base` = f71e614 (before plan I). Checked 2026-10-02: Studio holds none of plan I yet, but it does hold the egg merchant's lines (cce0dcc, synced by that session), which are in `cur`, so the guard passes.

Code review (subagent, 2026-10-02) found four real issues, fixed in 3cb6462: the wave clock stayed paused after a last stand ended without a revive; a respawn finishing after the player had left gave them a live body behind the results; a failed save handoff stranded a player on results; an open revive prompt could hold the last stand forever.

## Play-test checklist (the user runs it)

Single player, Studio Combined:
1. Armory: upgrade a starter to Tier II. The POWER plate goes up by 1. Launch a run: slot 1 shows the Tier II badge.
2. Map select: "Your power n · recommended m" under the difficulty buttons.
3. Die in a wave: YOU DIED, then the summary with "REVIVE OR THE RUN ENDS · 10" counting down. Let it run out: the results screen says DEFEAT with the waves cleared and emeralds. After 20 s (or BACK TO LOBBY) you're in the lobby.
4. Die again and press REVIVE (Studio simulates it): you're back with half health, the countdown is gone.
5. Clear a wave, then in the shop press LEAVE RUN twice: EXTRACTED results, then the lobby.
6. Admin Jump to wave 20, beat it: the shop title turns gold "Endless (Wave 21)"; keep going, then LEAVE RUN: VICTORY with ENDLESS (and TEST RUN · NO REWARDS, since the admin panel was used).
7. Stats tab: Gear power shows your power.

Two clients (Studio Test → 2 players, or the published game):
8. One dies mid-wave: SPECTATING the other, ‹ › / Q E switch, then respawn at the map spawn when the wave ends with the same weapons.
9. Both die: the last stand on both screens; nobody revives: both get DEFEAT and return together.
10. One leaves between waves: the other keeps playing; GO works for them alone.

Published only: AnalyticsService events appear in the Creator Dashboard after ~a day (PLAYTEST_ANALYTICS.md).
