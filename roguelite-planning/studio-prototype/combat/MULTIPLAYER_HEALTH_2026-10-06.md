# Multiplayer health policy — October 6, 2026

Each additional participant can bring six more weapons. Regular enemies retain their exact solo HP, damage and speed: the coordinated spawn policy supplies N times the authored arrivals for N active players, and boss-add capacity grows to 20N (20/40/60/80). Applying N times HP to those N times arrivals would create N-squared total health and erase the early fodder one-shot pacing. Spawn controls and their live tests are owned by the separate timeline/cap integration.

Bosses are one shared target, so `RunSetupRules.bossScale` now uses **1/2/3/4 times solo HP** for 1–4 encounter participants. Previously it used 1/2.35/3.7/5.05. Against equal per-player DPS, ideal boss kill time now matches solo. There is no multiplayer damage or speed increase. Map gear power, Normal/Hard/Nightmare, and Endless continue to apply exactly once as before.

| Players | Weapons at six slots each | Previous boss HP factor | New factor | Normal Pine Hammer HP |
|---|---:|---:|---:|---:|
| 1 | 6 | 1.00 | 1 | 10,800 |
| 2 | 12 | 2.35 | 2 | 21,600 |
| 3 | 18 | 3.70 | 3 | 32,400 |
| 4 | 24 | 5.05 | 4 | 43,200 |

The solo column is unchanged. All five maps and all three difficulties share this rule; no weapon inventory, rarity, stat roll, or current build is inspected. `partySize` floors and clamps the server count to 1–4, with safe missing/NaN inputs.

## Encounter participation and caps

Both legacy and rebuilt boss spawners snapshot `RunMember` players at encounter creation, including temporarily downed run members. Lobby spectators are excluded. HP does not change during the fight as somebody dies, revives or leaves. Regular arrivals use living/up players, so they adjust to the active team. This distinction preserves the existing stable boss encounter health instead of encouraging deaths to reduce boss HP. Tutorial fixed boss health remains fixed. Endless bosses first spawn through these same boss services, then apply their existing Endless factor without another player multiplier.

The 100-enemy global safety cap remains. Four-player arrivals may saturate it, particularly if the squad stops killing. Exact equal intensity cannot be guaranteed at that cap or against unequal build strength; that is an explicit performance constraint, not a claim of measured four-client parity.

## Economy audit — unchanged

Ordinary shards are owned by `LastDamageUserId`; more total arrivals provide more total drops, but rewards can concentrate on the player landing final hits. Bosses still produce a fixed 50 crystals split evenly among living run members, so each player receives a smaller boss-crystal share in a larger squad. That is existing behavior and was not silently retuned. Emerald milestone/win formulas are per-player and do not divide by party size. No persistent reward, DataStore, or shop changes were made by this policy.

## Verification

Local actual-source Luau runner passed **4,261 EnemyScalingTests + 942 NormalBalanceTests + 265 GearPowerTests = 5,468 assertions**. Added checks cover all five maps, three difficulties and four party sizes: linear boss HP, unchanged ideal per-player health budget, unchanged incoming damage, and malformed/out-of-range counts. Runtime and tests compile. No Studio sync or Play test was performed by this agent for this pass; parent integration records actual multiplayer checks separately.

Changed implementation: `lobby/RunSetupRules.luau`. Changed tests: `combat/GearPowerTests.luau`. Ordinary enemy catalogs were not edited for party size.

## Teammate revives: easier and safer (2026-10-10)

Play-test: "Make reviving easier, it's hella hard. It takes too long and it's too easy to die when you're doing it. Especially against ranged mobs you just get volleyed with projectiles." Code: `TeammateRevive.luau` (rules), `RogueliteMeta.server.luau` (wiring), `CharacterService.contact` (damage), `EnemyAttacks.luau` (shots), `TeammateReviveVisuals.client.luau` (ring, bubble).

| | Before | Now |
|---|---|---|
| Time, one reviver | 5 s | 2.5 s |
| More revivers | not faster (longest single hold) | +50% speed each: 2 → 1.67 s, 3 → 1.25 s |
| Reach | 10-stud prompt, 14 on the server | 16-stud prompt, 20 on the server, measured where the reviver's own screen has them (`CharacterService.seen`) |
| Let go / step out | back to 0 (except the last 0.5 s) | the ring drains 20% a second (full to empty in 5 s) |
| Damage to the reviver | full | 40% (60% less) from every source |
| Regular enemies' shots | full | stopped at the reviver's bubble, no damage |
| Getting hit | didn't interrupt | still doesn't |
| Pause (plan L) | reset every hold | drops the holds, keeps the ring's fill |

What the revived player gets is unchanged: 50% health, a 3 s shield and the revive shove.

**Not abusable:** the guard (`ReviveGuard`, a server-set player attribute) is on only while the server counts that player's hold: pressing, alive, in the run, in reach, a teammate down, run not paused. Walking near a body does nothing. It drops on the next 0.1 s check after any of those fails, and ends with the revive. A full ring takes 2.5 s of holding, so one down gives at most about 2.5 s of protection. Holding, letting go and holding again doesn't help: the ring drains half as fast as one reviver fills it, so a second of draining costs half a second more of holding.

**Example.** Two players on Desert Badlands, wave 10. Ana is down, Ben revives her while three Bow Skeletons shoot at him. Each arrow is 15.6 damage before difficulty, map and armor scaling (7.5 + 0.9 a wave). Each skeleton fires every 2.65 s (2.3 s × 1.15 for a two-player Normal run).
- Before: Ben stood still for 5 s, about 5.7 arrows, about 88 damage. If he dodged out of the prompt, the ring went back to 0.
- Now: 2.5 s, about 2.8 arrows, and all of them stop at his bubble: 0 arrow damage. A zombie swing that would do 10 does 4. If he has to step away for 1 s at 60%, he comes back to 40% and needs 1.5 s more.

**Ring on screen:** the spot publishes `Progress`, `ProgressAt` and `ProgressRate` (and `Revivers`) only when the speed changes, so every screen draws the same ring smoothly. The prompt's own `HoldDuration` is 60 s, so no client ends a hold early; the server finishes the revive. Each guarded reviver shows a lime ForceField bubble (client-only, cannot be hit or raycast).

**Verification:** `python run_survival_tests.py <luau.exe>` ran BossArrivalTests (12) and TeammateReviveTests (79, rewritten for the ring: speeds, helpers, drain, reach, guard on and off, pause, the revive shove). `run_enemy_shot_tests.py` still passes (6,351). Boss shots (MapBossService) and hazards aren't stopped by the bubble; they get the 40% damage. No Studio sync or Play test was run for this change.

### Second pass (2026-10-10, "a lil too op")

After a play-test the first pass was toned down. The table above shows the first pass; these are the live numbers now:

| | Before | First pass | Now |
|---|---|---|---|
| Time, one reviver | 5 s | 2.5 s | 3.5 s |
| More revivers | not faster | +50% each | +25% each: 2 → 2.8 s, 3 → 2.33 s |
| Reach (prompt / server) | 10 / 14 | 16 / 20 | 12 / 16 |
| Ring drain when nobody holds | instant reset | full to empty in 5 s | full to empty in 3 s |
| Reviver damage | 100% | 40% | 60% (40% less), shots included |
| Regular enemies' shots | hit | stopped at the bubble | hit, at 60% (`TeammateRevive.BLOCK_SHOTS` / `EnemyAttacks` `BLOCK_REVIVE_SHOTS` = false) |

The guard rules are the same: on only while the server counts the hold. The bubble still shows, and now means 40% less damage.

**Example, same fight** (3 Bow Skeletons, one reviver, 15.6 per arrow before scaling, one arrow per skeleton every 2.65 s):
- Originally: 5 s, about 5.7 arrows, about 88 damage.
- First pass: 2.5 s, 0 damage (every arrow stopped).
- Now: 3.5 s, about 4 arrows × 15.6 × 0.6, about 37 damage.

Verification: `python run_survival_tests.py <luau.exe>`: BossArrivalTests 12 and TeammateReviveTests 81 checks passed, with every scenario retimed to these numbers. No Studio sync or Play test by this agent.
