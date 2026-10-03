# Task: make 50–65 mobs run smoothly (server first, then phones)

You're working on a Roblox wave-survival roguelite, "Wavebreaker: Survive the Horde".
Repo: `C:\Users\Jeremiah\Documents\ChatGPT\Roblox`. The game code is under `roguelite-planning/studio-prototype/`.
Studio place: "roguelite" (placeId 107877054949326), shared with the user, a friend in Team Create and other agent sessions.

## The problem

Each wave spawns 8 + 3 per wave mobs (`ShopService.waveEnemyCount`): wave 15 = 50, wave 20 = 65 plus the boss. Endless goes up to 100, plus lava-slime splits. Parties are 1–4 players. **Nobody has measured the server cost at these counts.** The user doesn't want lag or FPS drops at peak waves.

How mobs work today:
- Every mob is a full R15 Humanoid owned by the server, cloned from `ServerStorage.RogueliteNPCs`.
- Each mob has its **own** `RunService.Heartbeat` connection in `RogueliteZombieChase.server.luau`. The chase logic is throttled to every 0.1 s; an attack in progress updates every frame.
- Every 0.1 s each mob does a line-of-sight raycast. Pathfinding goes through a shared budget of 10 computes per second.

## Already fixed today — don't redo

From the launch audit, `roguelite-planning/plans/2026-10-02-launch-audit.md`:
- P1–P4: bullets, batched hits, aim replication, targeting scans
- P7: enemy shots are drawn on clients
- P8: idle enemy work runs behind the 0.1 s tick
- P11, P12, P13
- F1: client animation by distance and on-screen
- F2: damage numbers capped
- F4

Read their "Done" notes so you don't undo them.

## Still open — your job

Line numbers come from the audit and may have shifted.

| Item | What | Where |
|---|---|---|
| **P5** | 65–100 full Humanoids simulated on the server, most state types still on | `RogueliteZombieChase.server.luau`, spawn ~350–405, tick ~433–564 |
| **P6** | Melee hit checks run ~120×/s; each returns every part of every enemy touched | `combat/RogueliteCombat.server.luau` ~359–389 |
| **P9** | Each enemy's tick repeats shared work: marker lookup, nearest player, the neighbour sort | `RogueliteZombieChase.server.luau` ~416–486, `combat/EnemySpatialGrid.luau` ~59 |
| **P10** | Contact damage loops over every enemy for every player at 10 Hz | `combat/CharacterService.luau` Heartbeat ~286–325 |
| Optional | Phone pass, only if time allows: F3 (Deck of Cards), F5 (raycast filters), F6 (effect limits) | see the audit |

## How to work

1. **Measure a baseline.**
2. **Fix the cheapest items first**, one item per commit.
3. **Re-measure** with the same setup.
4. **Report** the before and after numbers.

### Measuring

- **Ask the user before you start Play.** Play loads them into the game, so treat it as using their PC. Call `get_studio_state` first, because other sessions share this Studio.
- Setup:
  - Play solo and start a Pine Valley run. Get to wave 8 or later so tanks are in the mix.
  - Then use the admin panel's **Keep N alive** at 65 with a mixed roster (regular, baby, tank, spitter). This sets `TestZombieCountOverride`; see `combat/AdminService.server.luau` ~49–62, max 100.
  - Repeat at 50 and 100.
- Record for about 60 s while the player kites the crowd:
  - server: `Stats.HeartbeatTimeMs`, `Stats.PhysicsStepTimeMs`, `Stats.DataSendKbps`, `Stats.PhysicsSendKbps`, `Stats.InstanceCount`
  - time spent in the enemy scripts themselves (os.clock sums around the per-enemy update, or `debug.profilebegin`/`profileend` read in the MicroProfiler)
  - client FPS: average and worst 1%
- Never use `screen_capture` with a position: it leaves Studio's edit camera stuck. In Play, read attributes and `Stats` rather than requiring game modules from `execute_luau`.
- For Edit-mode checks, use `tools/FreshRequire.luau` served by `tools/dev_server.py`. The plugin VM caches `require`, so Studio modules come back stale. Pick a port that `netstat -ano` shows is free.
- A solo Studio run puts the server and the client on one PC, so the numbers are rough. Network cost with 4 real players needs real clients. Say so in the report and never claim it passed.

**Targets** (if the baseline says otherwise, adjust them and explain why):
- 65 mobs + 1 player: the server holds a steady 60 Hz.
- The enemy scripts (chase, attacks and contact) average about 2–3 ms per server frame or less.
- No frame goes over 16.7 ms during normal fighting.
- The server sends about 50 KB/s or less per player.

### Fix ideas, cheapest first

- **P9:**
  - Cache `Role.marker()` per map and invalidate it when `RunMap` changes.
  - Collect the living player roots once per tick for all enemies, not once per enemy.
  - Drop the neighbour sort in `EnemySpatialGrid`.
- **P10:** use the spatial grid, or a cached enemy list with squared distances, instead of looping over every enemy for every player.
- **P6:**
  - Take one hit part per enemy per query (dedupe by model).
  - Cache the Boxing Gloves' parts instead of calling `GetDescendants` each sample.
  - Cap sampling at 30–60 Hz.
- **P5:**
  - Disable the Humanoid states mobs never use: Swimming, Seated, FallingDown, Ragdoll, GettingUp, PlatformStanding, Flying, StrafingNoPhysics. Climbing is already off.
  - **Keep** Running, Jumping, Freefall and Landed: mobs hop when stuck and follow path jump waypoints. Heavy mobs don't jump.
  - Replace the per-enemy Heartbeat connections with **one scheduler** that steps enemies round-robin, staggered across frames.
    - Mobs far from every player (say beyond 90 studs) think every 0.25–0.5 s instead of every 0.1 s.
    - Attacks in progress keep their exact per-frame timing.
  - Skip `MoveTo` when the goal hasn't moved meaningfully since the last call.
  - Enemy limbs: turn `CanTouch` off where nothing uses `.Touched`. Turn `CanQuery` off only on parts no hit test needs; melee and bullet queries need some, so check first.
- **Only if still over budget after all of that:** write a proposal for the record-based design in `roguelite-planning/ENEMY_SIMULATION_ARCHITECTURE.md`: the server keeps lightweight enemy records and clients draw the models. The user approved that direction on 2026-09-17, but it's a big rewrite, so get their okay before starting it.

## Don't break how mobs feel (hard rules)

Mob movement took several rounds of fixes. Every change must keep:
- **Model scale 1** on every Humanoid NPC. A Humanoid's walk force scales with `Model:GetScale()`; mobs at 0.01 slid around as if on ice skates.
- The `MIN_MASS = 4` root density boost for light mobs (babies, slime splits).
- Turning through AlignOrientation or the Humanoid. Never CFrame-turn a walking NPC; that stops it.
- These exactly as they are now:
  - speeds, acceleration, stop and reverse times
  - attack wind-ups and damage
  - hop-when-stuck and pathfinding around rocks
  - spawn telegraphs
  - Pause and Freeze (`RunPaused`, `AdminFreeze`) and admin spawns
- If you touch the Humanoid setup, measure acceleration, reverse time and stop time on the server before and after for one regular zombie, the tank and one imported mob (werewolf).

These existing checks must still pass (all in `combat/`, run in Edit through the FreshRequire harness): EnemyTests, EnemyShotTests, EnemyTemplateTests, MotionTests, CombatWireTests, ZombieTests, WeaponBalanceTests, GearPowerTests.

## Studio and git rules

- **The repo is the source of truth.** Change the repo first and run the checks. Then ask the user "push it to Studio?" before writing any script into Studio. Each change needs its own okay.
- **Studio can drift from the repo.** Other sessions and a non-Claude agent edit Studio directly.
  - Before editing a script, compare its Studio `Source` with the repo.
  - Push with the guarded all-or-nothing sync: `tools/launch_sync.py` builds the manifest and `tools/LaunchSync.luau` writes it. A script is written only if Studio still holds exactly the guard source.
  - Never overwrite Studio-only edits; merge them into the repo.
- **New ModuleScripts:**
  - Set `Sandboxed = true` and copy `Capabilities` from a neighbour, or their requires fail.
  - Don't create a module before the things it `WaitForChild`s exist in the place.
  - Modules that ShopService requires must not `WaitForChild('RogueliteRunState')` at load; that deadlocks the server.
- **Never leave Studio broken between steps.** The user play-tests constantly. Land each change together with everything that depends on it.
- **The user judges feel.** You measure. When done, hand over with a short "what to try" list.
- **Git:**
  - Small commits straight to `main`.
  - Only your own files: `git commit -m "..." -- <paths>`, never `git add -A`. Other sessions share this working folder and its git index.
  - Push with `git push origin main`. There is also a `copy-the-scene` remote for a different game; never push there.

## Deliverable

- The fixes, in small commits.
- In the launch audit: mark P5, P6, P9 and P10 done, each with before/after numbers.
- A table with rows for 50, 65 and 100 mobs, and these columns: server heartbeat ms, enemy-script ms, physics ms, data send KB/s, client FPS (average / 1% low).
- What still needs testing with real multiple clients.
- Plain, short writing: numbers, not adjectives.
