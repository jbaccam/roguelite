# Baby and mutant zombies

## Current delivery state — September 22, 2026

The corrected baby and rounded full-shirt mutant meshes are uploaded and installed in roguelite, place 107877054949326. `ServerStorage.RogueliteNPCs` contains `BabyZombie_NPC` and `MutantZombie_NPC`, each with 15 MeshParts, 15 Motor6Ds, Humanoid and Animator. Raw imports are preserved in `ServerStorage.ZombieRawImports`; non-colliding static review copies are in `Workspace.ZombieVariantPreviews`. Uploaded mesh/texture IDs and assembled sizes/CFrames are recorded in `../../baby-mutant-zombies/StudioAssetManifest.json`.

The user explicitly approved limited Studio import-dialog UI control with “ye” after being asked. Both FBXs were imported through that dialog; assembly and testing used the Studio connector. The prior programmatic upload attempt was unavailable and produced no mesh assets.

The single-client Play smoke test confirmed live baby/mutant spawns, correct MaxHealth and WalkSpeed, client joint motion, mutant hunched waist, and at least two mutant slam starts. Weapon damage reduced the mutant from 240 to 30 HP and it subsequently disappeared. Exact slam damage, dodge/wall/death cancellation cases, respawn, and multiple clients remain unverified. Console output showed Roblox CorePackages social/chat errors and an existing CardPresentation missing-showcase-child wait; no zombie error was observed. The test wave was Play-only and Studio was returned to Edit mode.

## Baby sliding and the spawn-pad step — September 28, 2026

- Babies slid like they were on ice. Cause: the whole template weighs 0.33 (only its small root part has mass; every limb is `Massless`), and the Humanoid can't steer a body that light. It accelerated at about 25 studs/s² (the regular zombie manages ~700), averaged 12 studs/s against its 20 WalkSpeed, and moved about 38° off the way it faced. Test weights of 1/2/4/8: from 2 up it runs like the regular zombie. `RogueliteZombieChase` now raises any enemy under 4 mass to 4 at spawn by making its root denser. Knockback impulses already scale by `AssemblyMass`. Most custom mobs weigh 1.3–2.2, and lava slime split children about 0.3, so they get the same floor.
- Babies also stood still at the edge of the 1-stud `PlayerSpawn` pad. Their hips are 0.84 studs up, and with a clear line of sight the chase never gets a path jump waypoint. A chasing walker (not Heavy) now hops when 0.3 s covers under 15% of its walk. That only counts when it is over 1 stud outside its stop range, steering at the target, and not attacking or frozen.
- Verified in single-client Play with weapons off. Open ground, player circling: babies averaged 19.1 studs/s, an 11° facing error and 3.7% sideways frames (regular zombies: 10°, 4%), and never hopped. Six babies against a player on the pad: one hop each at the edge, all six on the pad, no other hops in 20 s. Console clean. Multiple clients untested.

## Starting balance

| Type | HP | Speed | Damage | Behavior |
| --- | ---: | ---: | ---: | --- |
| Regular | 40 | 12 | 10 contact | Existing chaser |
| Baby | 24 | 16 | 6 contact | Faster cadence and small bob, closer stopping distance |
| Mutant | 240 | 9.5 | 26 slam | Permanently hunched idle/walk; no additional contact hit |

Damage values precede character armor, dodge and first-hit blocking. The regular/baby contact cooldown remains the existing player-wide 0.8 seconds. Initial five-slot composition is regular, baby, regular, regular, mutant; the pattern repeats with one mutant per eight slots and two babies per eight. These are provisional tuning values requiring the actual Play check, not a demonstrated balanced encounter.

The mutant raises its arms for 0.32 seconds, lands at 0.46 seconds, recovers by 1.0 second, and can start another slam after 2.15 seconds. Its orange ground warning becomes an impact flash. Target direction and circle are committed at attack start. The server validates current life, wave toggle, range, vertical separation, walls, and one impact per attack. Death/removal cancels damage. Player damage uses the existing authoritative `CharacterService.contact` path and red damage popup. There is no new client-to-server attack remote.

The warning is a 5.2-stud radius circle centered 3.5 studs ahead. Characters above 4.5 studs relative to the impact ground are excluded. The published/mobile dodge window has not been playtested. The prototype still uses the existing server-owned Humanoid enemy implementation; this update does not claim to complete the separately planned record-based horde migration or prove large-population performance.

## Sources

- `ZombieTypes.luau`: stats, spawn composition and slam dimensions/timing.
- `ZombieMotion.luau`: 15-joint bobbing, hunched locomotion, raise/slam/recovery poses.
- `ZombieAttacks.luau`: server attack lifecycle and impact validation.
- `ZombieSlamVisuals.luau`: local non-colliding warning/impact disc.
- `../RogueliteZombieChase.server.luau`: selects templates, applies stats and runs attacks.
- `../RogueliteZombieAnimation.client.luau`: applies locally evaluated poses using server timestamps.
- `CharacterService.luau`: per-mob contact damage/range, while retaining existing defenses.
- `../../baby-mutant-zombies/`: models, textures, FBX exports, Blender slam preview and importer.

## Checks performed

- 65,718 assertions over 363 sampled poses plus tuning/range checks passed in the actual Studio Luau environment using `ZombieTests.luau`.
- Combat and root Rojo packaging succeeded.
- Both final meshes passed Blender/FBX/GLB reimport checks for 15 sections, 16 bones, UV bounds, normalized weights, loaded textures, closed geometry and elbow movement with stable unrelated foot.
- Both mesh-only import FBXs independently reopened with 15 mesh objects and no armature.
- Actual runtime CFrames were transferred to the mutant Blender rig for the slam review. At impact, both fist bottoms are within 0.071 authoring units of ground, about 3.45 units forward. The raised fists exceed the head height; the rest torso remains hunched.
- Corrected shirt yoke uses the torso's top surface itself, avoiding an additional floating shoulder plate. Full sleeves retain fabric under both upper arms.

## Required follow-up after mesh import

1. Assemble both uploaded models using `ServerStorage.ZombieVariantImportTools.InstallZombieVariants`; preserve the raw imports and record asset IDs.
2. Verify faces, axes, dimensions, texture permission, root collision, feet, and all 15 Motor6Ds in Studio.
3. In actual Play, verify the baby speed/bob and mutant hunched walk/raise/slam. Check stationary in-circle damage, leaving the circle, jumping, a wall, death during windup, stopping the wave, cooldown, one-hit-per-slam, normal weapon kills, and respawning the correct type.
4. Confirm no errors and restore Edit mode/test state. Multiple real clients, device profiling, published asset access and DataStores remain untested. This feature adds no DataStore/persistent reward code.

## Body bumps (2026-09-29)

Wave mobs still set `ContactDamage` 0 (their timed swings own damage), but running into one now hurts too. Each spawn sets `BumpDamage` = half its hit (rounded, at least 1) and `BumpRange` = min(stopRange, radius + 1.5) − 0.3 (2.8 studs for a normal zombie). `CharacterService` deals it when a player's body overlaps a mob with clear line of sight, at most once per 0.6 s per player across all mobs (its own timer, separate from the old 0.8 s contact timer). The range sits inside the mob's stop distance, so fighting at normal reach never bumps. Example: a wave-10 zombie that hits for 12 bumps for 6; dashing through a pack for 1.5 s costs about 2–3 bumps.

## Harder to dodge, no gliding (2026-09-30)

User playtest: changing direction dodged almost every swing, and many mobs slid.
- **Swings** (`EnemyAttacks`): a melee swing starts 1 stud before `attackRange`, reaches `attackRange` (or `hitRange`) + 1.5 studs (+0.6 for Lunge dashes), hits within ~95 degrees of the facing (was ~81), and checks every frame for 0.15 s from impact (was one frame). Ranged shots are unchanged. Example: a normal zombie swings at 5.6 studs and connects out to 6.1.
- **Gait** (`RogueliteZombieAnimation`): the Move loop may run as fast as each mob's own stride needs at full speed, 4–12 loops/s (was a flat 4), so feet keep up with the body. Before: crab and snake legs covered ~40% of the ground, spider 52%, goblin 67%, skeleton 73%. Frost ghost, lava slime and snake keep their time-based motion.
- **Mutant zombie slam** radius 6.5 (was 5.2); its warning disc reads the same value.
