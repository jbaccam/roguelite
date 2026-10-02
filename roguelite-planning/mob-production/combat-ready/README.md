# Regular enemy animation delivery

This is the animation-only delivery for the 18 custom regular enemies. The three
preferred native Pine Valley templates remain in Studio and use their existing
meshes with the revised native motion controller. Bosses are excluded.

The latest nine `reference-rebuilds/` models are used for Ash Shaman, Bow Skeleton,
Fire Goblin, Lava Slime, Obsidian Ogre, Rock-Throwing Crab, Skeleton, Snake and
Spitter Zombie. The other nine use their latest `revisions/` models. This pass
does not rebuild sculpture, alter UVs, change weights, or replace approved hand
and wrist fixes. Each `AnimationChecks.json` records matching before/after
geometry-and-weight fingerprints.

Open [the interactive animation review](review.html) through the existing local
server: <http://127.0.0.1:8814/combat-ready/review.html>. It displays actual GLB
meshes, offers all five clips, playback speed, camera orbit and a frame scrubber.
All model, render and metadata URLs include their SHA-256 content hash. Run
`refresh_review_assets.py` after any export to keep those URLs current.
`StanceSheet.jpg`, `WalkSheet.jpg`, `AnticipationSheet.jpg` and `ImpactSheet.jpg`
show Blender renders of all 18 models.

## Motion

- Humanoids use lowered hips, bent knees, fixed ankle targets, restrained torso
  lean, relaxed elbows, hip/chest counter-rotation and opposing arm/leg travel.
- Movement uses a planted phase at constant backward foot velocity and a smooth
  lifted return. `motion.strideLength` lets the runtime advance phase from actual
  horizontal travel, keeping feet synchronized with movement.
- Heavy profiles have 1.25-second cycles and restrained lifts. Small quick
  profiles have 0.67-second cycles. Standard profiles use 0.875 seconds.
- Arthropods use alternating planted groups and two-segment leg solves. Snakes
  use traveling spinal motion; the ghost floats; the slime uses weighted crown
  compression without unsupported bone scaling.
- Attacks include anticipation, impact/release and recovery. Their authored
  impact timing is metadata; damage and projectile timing remain server-owned.
- Bow Skeleton retains the reviewed straight drawing wrist and hand/string
  contact. The projectile metadata gives exact imported-hand-local arrow rest
  and upper-string points. The arrow is a separate asset, with its origin at the
  nock and its tip 1.9 authoring units along forward.
- Bow Skeleton shoots square to its target (2026-10-01). The authored shot left
  53° to its right, so the game had to turn the whole skeleton 53° away from
  the player. `square_bow_skeleton.py` turns the chest through the shot and the
  skull back again in `StudioAnimationData.json`, then sets
  `attackFacingYaw` to 0. Hips, legs and skull now face the target and the
  arrow leaves straight ahead. Re-run it after any re-export of the Attack
  clip; it applies only once. Then run
  `studio-prototype/combat/build_enemy_animation_modules.py`.
- Ranged origin metadata follows the held rock, the Ice Elf's throwing fist, the
  fireball above the Shaman's open casting palm, or Spitter's mouth through the
  actual imported joints.

## Character-specific attacks (2026-09-27)

The shared placeholder swing (every armed humanoid raised one arm and chopped
straight down) is replaced. `attack_design.py` solves two-bone arm IK to keyed
wrist targets in the chest frame; `attack_keys.py` holds each humanoid's
choreography and `creature_attacks.py` the creatures'. Per frame the solver
searches the elbow direction and forearm pronation for the most natural arm:
a comfortable wrist for the held weapon's grip, little upper-arm roll on the
continuous skinned meshes, the authored elbow hint, frame-to-frame continuity
and, for swords, the sharpened edge (not the flat) facing the swing's travel.

| Enemy | Attack |
|---|---|
| Skeleton | Forward diagonal chop: sword cocked behind the shoulder, over the top and down at the target, off foot steps in. At impact the flat faces the target at most 0.20 (edge at least 0.74) |
| Frozen Knight | Heavy horizontal sweep, edge leading: sword hauled back past the hip, cut flat across the front with the whole torso, follow-through wrapping past the far hip (2026-10-01 rebuild) |
| Fire Goblin | Reverse-grip ice-pick stab: fist raised overhead, blade down, driven down and forward with a hop |
| Mummy | Wide hook: elbow up at shoulder height, fist round at head height |
| Obsidian Ogre | Straight cross from a jaw-level chamber, hip and shoulder through, lead hand back to guard |
| Werewolf | Pouncing double claw rake from high and wide, both claws raking on past the hips (2026-10-01 rebuild) |
| Ice Elf | Overhand icicle throw, sighting along the off hand |
| Ash Shaman | Staff planted; open palm gathers the fireball at the hip and thrusts it at chest height |
| Spitter Zombie | Rear back gulping, lurch forward with the face level to spit |
| Scorpion | Tail coils high, then the stinger drives forward over the head (planar constant-curvature tail solve) |
| Crab / Hermit Crab | Raised gaping pincer jab-and-snap / both claws spread wide then scissor shut |
| Ember Spider | Rears onto its back legs with front legs lifted, drops forward biting |
| Frost Ghost | Left-right mitten one-two with a forward surge |

Skeleton, Knight and Goblin carry their weapon arm ready while idling and
walking instead of swinging it loose. Bow Skeleton, Rock-Throwing Crab, Snake
and Lava Slime keep their reviewed attacks.

`animate_mobs.py -- <id> --preview <dir> [clip] [frames]` renders fixed-camera
Workbench strips (side/front/three-quarter/top) without saving or exporting.
`animate_mobs.py -- <id> --debug 0 <script.py>` executes a probe inside the
posed rig (used for the blade-presentation check).

**Blade orientation.** Both swords were modelled with the flat facing forward.
`../edge_forward_blades.py` turned the blade, guard, grip and pommel islands 90°
about the blade axis so the edges run along the knuckle line; fists, UVs,
weights and the rig are untouched. Previous sources are in each source's
`history/before-edge-forward/`. Revised FBXs are staged as
`../studio-import/sources/*-edge-forward.fbx`.

**Grip fixes (2026-09-27, second pass).** The Knight's sword originally ran
diagonally across the fist, perpendicular to the curled fingers, so it never
looked held and swept through the forearm. `../reseat_knight_sword.py` moves the
sword so the handle runs through the finger tunnel, the guard sits past the
thumb and the edges run along the forearm (the hammer-grip punching line). The
Skeleton's crossguard was trimmed to 60% length (`../shorten_skeleton_guard.py`)
so its rear quillon clears the forearm. Its follow-through now stays in the
cutting line and eases into an 80-degree ready carry instead of rolling the arm
inward and dropping the point. The solver checks the weapon against the actual
evaluated forearm mesh during wind-up and recovery. Per-frame triangle overlap
tests find zero sword-body intersections for both mobs in Idle, Move and Attack.

**Ice Elf.** Redesigned after the supplied Solo Leveling ice-elf reference in
`../revisions/ice-elf/build_ice_elf.py`: spiked swept-back mane, heavy V brows,
narrow pupil-less glowing eyes, indigo cheek markings, a wide fanged grin and
long swept ears. Its own atlas (`make_evil_atlas.py` -> `EvilAtlas.png`) repaints
two tiles the elf never used and cools the skin; the shared atlas is unchanged.
The old hidden forearm icicle is removed. Previous build: `history/before-evil/`.

**Held spells.** `EnemyProjectileVisuals.luau` builds the fireball and icicle in
code. The server flies them; `EnemyHeldProjectiles` shows the same model in the
caster's hand (Shaman: palm ember that swells through the wind-up; Elf:
conjured in the throwing fist), hidden at release.

## Files and import axes

`Model.blend` is the editable posed rig; `Model.fbx` is the rest mesh and rig;
`Model.glb` carries five clips; `animations/` contains armature-only FBX clips.
Textures are copied from the accepted source without rebaking. `Geometry.json`
retains portable source mesh data. `AnimationData.json` is the source animation
sample format and is **not** the payload installed into Studio.

Native FBX import produces different bone-local axes and initially expands the
model 100 times. The import receipts under `../studio-import/` record the actual
bones after normalization to authoring scale. `retarget_studio.py` reconstructs
each global deformation, converts coordinates using the observed mapping
`(-BlenderX, BlenderZ, BlenderY)`, then derives local transforms against the
actual imported rest hierarchy. Its output, `StudioAnimationData.json`, is the
runtime payload. This avoids guessing the FBX bone orientation.

Rigid source models can import as Motor6D chains. For these, the receipt includes
Part0/Part1 rest frames and C0/C1 offsets. Retargeting derives the motor joint
frames and verifies the actual native equation `Part0 * C0 * Transform * C1^-1`
against the desired mesh deformation. The zero-influence Root Bone stays
identity; source root motion is included once in the top-level motors.

The normalized model reports `GetScale() = 0.01`; that value is the baseline,
not an additional visual or stride scale. Runtime scaling uses the ratio of the
current model scale to `EnemyBaselineModelScale`.

## Verification

- All 18 models: unchanged geometry/weights, exact idle/movement loop closure,
  and independent fresh imports of rest FBX, animated GLB and all 90 individual
  animation FBXs passed. Reports include file hashes.
- All humanoids: actual world-space opposite-leg/arm covariance passed; planted
  ankle errors are below 0.002 authoring units.
- All five crawlers: planted tip errors are below 0.000001 authoring units;
  swing tips stay above their contact plane. See `verify_crawler_contacts.py`.
- Fire Goblin: 375 grip-contact vertices remain attached through every frame of
  all five actions, maximum deviation below 0.000001. See `GripMotionChecks.json`.
- Bow Skeleton: string contact, return to brace and 53 quarter-frame straight
  wrist checks passed again on the new attack. See `ShootingChecks.json`.
- Native Studio import and retarget checks are recorded separately per enemy.
  The runtime integration's test report records actual client play tests;
  Blender and exchange checks alone do not establish game-loop verification.
- `DeliveryChecks.json` reconciles all 18 export and retarget receipts with
  current file hashes; run `verify_delivery.py` after final exports.
- 2026-09-27 attack pass: all 15 re-animated enemies passed geometry/loop/gait
  checks, fresh FBX/GLB re-imports and Studio retargeting (<6e-7 error). In
  single-client Studio Play sessions every changed enemy entered its attack
  state on the client (the slow crab/hermit crab/mummy after a longer sample),
  the held icicle and fireball were observed (fireball swelling 0.45 -> 1.0
  across the wind-up) and arrow, rock, icicle, fireball and spit projectiles flew.
- The edge-forward Skeleton/Knight FBXs and the redesigned Ice Elf were imported
  with Studio's 3D Importer and moved onto the existing raw imports and templates
  by `../../studio-prototype/combat/SwapImportedEnemyMeshes.luau` (swapped parts
  snapped exactly to their joints). Receipts under `../studio-import/` were
  regenerated from Studio (previous copies in `history/before-2026-09-27/`);
  retargets pass and `verify_delivery.py` passes for all 18.
- Bow Skeleton and Rock-Throwing Crab now use their 2026-09-25 longer-stride
  walks (strides 2.26 -> 3.11 and 1.17 -> 1.38; planted feet exact, crawler
  contacts pass), matching every other enemy.
- In-engine Play captures (client animation script paused, pose frozen on a clip
  frame) confirmed the Ice Elf's new head and atlas, the Skeleton's wind-up and
  chop, and the Knight's flat sweep. Seen from the target, the Skeleton's blade
  shows edge-on. The place was saved with File > Save to Roblox (not published).
- Multiple real clients, high latency and mobile performance remain untested.

## Reproduction

Run Blender in a separate background process; never replace the user's open
Blender document:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --threads 4 --python roguelite-planning/mob-production/combat-ready/animate_mobs.py -- skeleton
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --threads 4 --python roguelite-planning/mob-production/combat-ready/verify_exports.py -- skeleton
python roguelite-planning/mob-production/combat-ready/retarget_studio.py skeleton
```

`verify_preserved_contacts.py` accepts `fire-goblin` or `bow-skeleton` after `--`.
`verify_crawler_contacts.py` checks all five arthropods.

## Werewolf and Frozen Knight rebuilds in Studio (2026-10-01)

Both mobs were rebuilt from new reference sheets (`../reference-rebuilds/`, "Werewolf reference rebuild" and "Frozen Knight reference rebuild" in that README). Their attacks gained a longer follow-through: the knight's cut wraps past the far hip, and the werewolf's claws rake on past the hips.

- **Import.** The user imported `../studio-import/sources/{werewolf,frozen-knight}-rebuild.fbx` with Studio's 3D Importer, using Keep Zero Influence Bones. Both came in as Bone rigs, with every MeshPart on a Motor6D to RootPart. That includes the fully rigid knight, which previously imported as a Motor6D chain.
- **Adoption.** `../../studio-prototype/combat/AdoptRegularEnemyImport.luau` ran ScaleTo 0.01 and put the RootPart at the origin. It filed each import as `ServerStorage.RegularEnemyRawImports.<id>` and moved the old raws to `RegularEnemyRawImportsHistory.<id>-before-rebuild`. It also dumped the receipts. The old receipts are in `../studio-import/history/before-2026-10-01-rebuild/`. A sum over every bone, part and motor number matched the Studio data exactly.
- **Retarget.** `retarget_studio.py` passes for both, with a world reconstruction error under 3e-7. `build_enemy_animation_modules.py` changed only these two mobs and their `EnemyMotionTuning` entries.
- **Studio write.** The 13 modules were written to Studio after checking that Studio's Source equalled HEAD. `InstallRegularEnemyTemplates.luau` now takes an optional `ONLY` set and rebuilt just `Werewolf_NPC` (17 bones, HipHeight 2.15) and `FrozenKnight_NPC` (16 bones, HipHeight 1.91).
- **Check.** Edit-mode copies at rest and posed on the attack impact frame were textured, attached and correctly posed in a plain viewport capture.
- **Not tested.** No Play test was run. Gameplay, hit timing, multiple clients and the Frozen Pass lighting are untested.
