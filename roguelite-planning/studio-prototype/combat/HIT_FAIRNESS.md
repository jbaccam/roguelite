# Enemy hits judged from the player's screen — October 3, 2026

**The complaint (user, Studio play-test):** zombies, and then every mob, hit "when im not even really in their physical range". In the user's words: "if i triggered their hit animation, they are going to hit me regardless if i move away from it."

## What was measured

Measured in Studio Play, read-only. The server and the client each recorded positions with `workspace:GetServerTimeNow()` for 8 s, and the two recordings were lined up against each other:

- **The server sees the player's body 220 ms late.** In one ~11-stud move at about 20 studs/s, the client was at z 35.7 while the server still had z 40.6.
- **The client sees the enemies 190–205 ms late** (two zombies).

Hits were all judged on the server, between its late copy of the player and the enemy where it really is. Take a player kiting at 22 studs/s from a zombie chasing at 12:

- the server's distance was about 22 × 0.22 + 12 × 0.2 ≈ 7 studs shorter than the one on screen;
- a regular zombie connecting at 4.6 studs on the server looked about 12 studs away to the player.

Swings, enemy shots, tank slams, body bumps and both kinds of boss all had this problem.

## The fix

- **Each client reports where its body is** 30 times a second while in a run. This goes over `RogueliteCombat.PlayerView`, an UnreliableRemoteEvent made in Studio with HitFX's sandbox settings. The sender is at the end of `RogueliteCombat.client`.
  - The first version (8674bd9) had `CharacterService` create the remote itself. A sandboxed module can't set `Sandboxed` (that needs CapabilityControl), so CharacterService failed to load, along with every server script that requires it, and the UI never came up. The hotfix (ae6513d) only looks the remote up, and waits for it if it isn't there yet.
- **`CharacterService.seen(player, root)`** is the player's position as their own screen shows it. It uses the latest report while that report is under 0.3 s old and within 3 + speed × 0.35 studs of the body on the server (about 11 studs at 24 studs/s). Otherwise it uses the body on the server, so a report can't carry anyone far from where physics has them.
- **`CharacterService.seenEnemy(player, root)`** is an enemy as that player saw it: moved back along its ground velocity by 0.2 s plus half the player's ping (at most 0.15 s of ping). Example: a zombie walking at 12 studs/s shows 2.4 studs behind.
- **Used by:**
  - `EnemyAttacks`: melee swings use seen against seenEnemy; shots use seen.
  - `ZombieAttacks`: the tank's slam uses seen.
  - `CharacterService`: the body bump uses seen against seenEnemy.
  - `BossService`: the charge, hammer and slam use seen.
  - `MapBossService`: every hit test uses `e.at` = seen.

  Shots and boss attacks are drawn on the server clock, so only the player's side needed fixing there. Line-of-sight raycasts and aiming still use the bodies on the server.

## Checked

`ContactTests` passes 704 checks:
- the 699 that compare the contact loop with the old one;
- 5 new ones: a fresh report near the body is used, an old one or one 40 studs off isn't, a non-position report changes nothing, and a zombie at 12 studs/s shows 2.4 studs behind.

All the changed scripts compile.

**Also changed the same day (618c18e):** the zombie swing arc went from about 95 to about 75 degrees each side of the facing, and its hit window from 0.15 to 0.08 s. Circling past a zombie's side counted as a hit before (user: "especially when i circle them").

**Studio:**
- The 8674bd9 sync broke Studio as described above.
- The user then reopened Studio, and the 7 scripts came back at their earlier versions.
- Synced again at 618c18e with `tools/LaunchSync.luau` (`hit-fairness-sync-map.json`, plus the PlayerView remote): 7 scripts, each guarded on its pre-fix version. Afterwards all 7 matched, Sandboxed was unchanged, and the remote matched HitFX's capabilities.

Not yet play-tested.

## Every mob's reach, measured (2026-10-03, round 2)

User: "make sure i can train all the other mobs too without getting hit in stupid angles or ranges".

Every melee mob hit out to the same 4.6 studs centre to centre (the native zombie 4.5), whatever its size. Their body bumps used a rough radius + 1.5.

**How it was measured.** In Studio Edit, each mob's template was posed at its attack's strike frame with fresh copies of EnemyMotion, or ZombieMotion for the native zombies. `EnemyMotion.boneWorld` gave how far forward of the root the striking limb gets:
- jointed parts: their outer box edges;
- skinned meshes: the hand bone, plus the blade's forward share for the sword and dagger users (blade lengths from `mob-production/combat-ready/attack_keys.py`).

The client already lines each clip's strike frame up with the server's impact time (RogueliteZombieAnimation), so timing was right; only range was off.

**Reach** = limb + 0.75 (the player's half-body). **Stop** (where the chase stops) = 0.6 inside the reach, so a mob still connects on a player standing still. Lunges keep their dash trigger and take reach as `hitRange`. All of these live in `EnemyCatalog.Reach`.

| Mob | Limb at strike | Reach (was) | Stop (was) |
|---|---|---|---|
| Regular zombie | 2.63 (arm swipe) | 3.4 (4.5) | 2.8 (3.5) |
| Baby zombie | 1.36 | 2.1 (3.1) | 1.5 (2.1) |
| Skeleton | 2.03 + sword | 3.7 (4.6) | 3.1 (3.2) |
| Frozen Knight | 2.28 + 2.6 sword across a sweep | 4.7 (4.6) | 4.1 (3.2) |
| Fire Goblin | 2.23 + dagger | 3.6 (4.6) | 3.0 (3.2) |
| Mummy | 2.79 | 3.5 (4.6) | 2.9 (3.2) |
| Werewolf | 3.4 + claws | 4.6 (4.6) | 4.0 (3.2) |
| Obsidian Ogre | 3.65 + fist | 5.0 (6.0) | 4.4 (4.4) |
| Crab | 2.87 | 3.6 (4.6) | 3.0 (3.2) |
| Hermit Crab | 3.14 | 3.9 (4.6) | 3.3 (3.2) |
| Frost Ghost | 1.52 | 2.3 (4.6) | 1.7 (3.2) |
| Ember Spider | 1.80 | 2.6 (4.6) | 2.0 (3.2) |
| Lava Slime | 1.24 | 2.0 (4.6) | 1.8 (3.2) |
| Scorpion (lunge) | 2.93 | 3.7 (3.8 + 0.6) | 7 |
| Snake (lunge) | 2.28 | 3.0 (3.4 + 0.6) | 9 |

- **Split Lava Slime children** scale the limb part of the reach by their size (`EnemyAttacks`).
- **Body bump** (`RogueliteZombieChase`) is now the body's narrower ground side halved, plus 0.8, capped 0.3 inside the stop distance. Examples: zombie 1.4 (was 2.5), skeleton 1.6 (2.8), ogre 2.2 (3.6), tank 2.1 (4.2).
- **The tank zombie's slam** draws its full 6.5-stud disc during the windup (ZombieSlamVisuals), so it stays as it was.
- **Arcs:** every swing is ~75 degrees each side of the facing (round 1).

**Checked:** `EnemyTests` pass 253,034 checks (54 clips); the changed scripts compile. Not yet play-tested.
