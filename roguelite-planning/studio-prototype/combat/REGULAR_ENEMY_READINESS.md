# Regular enemy runtime setup

2026-09-25. Scope is the 21 regular entries in `MAP_MOB_ROSTER.md`; bosses are excluded. The three preferred native zombie meshes and rigs are preserved. Their template Humanoid defaults now match the authoritative wave-one tuning rather than the stale 100/24/240 template values.

The existing Pine Valley wave selection still uses Regular/Baby/Tank. The other eighteen templates are available for explicit server-selected rosters; this setup does not add them to the existing waves. `EnemyRoster` is an optional server-owned comma-separated list of catalog IDs. No new client remote can select targets, claim hits, spawn enemies, or change tuning.

Studio-only testing: the character panel's Zombies section has a typed count box (0–100) and a mob picker. Picking mobs sends the Studio-gated `EditPractice` `Roster` action; the server accepts only known catalog IDs, removes duplicates, and writes `EnemyRoster`, which cycles by spawn slot and ignores the wave-8 tank gate. **Use wave mix** clears it. Without a roster, tanks spawn only from wave 8 in slots 5, 13, 21, … (every eighth slot).

## Tuning

The native values retain existing balance. All other HP, damage and movement values are explicitly marked **provisional QA baselines**, not approved final balance.

| Enemy | Base HP | Speed (studs/s) | Behavior |
|---|---:|---:|---|
| Regular Zombie | 3 | 16 | Melee |
| Baby Zombie | 1 | 20 | Melee |
| Tank Zombie | 20 | 12.5 | Existing warned slam |
| Spitter Zombie | 5 | 13 | Ranged spit |
| Crab | 4 | 16 | Melee |
| Snake | 3 | 15 | Warned fast lunge |
| Hermit Crab | 12 | 12 | Heavy melee |
| Rock-Throwing Crab | 6 | 13 | Ranged rock |
| Skeleton | 4 | 17 | Melee |
| Bow Skeleton | 4 | 14 | Ranged arrow |
| Mummy | 10 | 13 | Heavy melee |
| Scorpion | 6 | 15 | Warned straight lunge |
| Frost Ghost | 5 | 16 | Floating melee |
| Werewolf | 8 | 21 | Fast melee |
| Frozen Knight | 14 | 12 | Heavy melee |
| Ice Elf | 5 | 14 | Ranged icicle |
| Fire Goblin | 4 | 18 | Melee |
| Ember Spider | 2 | 20 | Fast melee |
| Lava Slime | 6 | 13 | Splits once into two smaller children |
| Obsidian Ogre | 20 | 12 | Heavy melee |
| Ash Shaman | 6 | 13 | Ranged fireball |

Native health grows by 2/1/11 per wave for Regular/Baby/Tank. Tank first appears at wave 8 with 97 HP. Native Regular/Baby damage remains `1 + .6*(wave-1)` with the existing shared .8-second damage gate; Tank slam remains `2 + .85*(wave-1)`. Attack animation now anticipates the Regular/Baby melee impact. `EnemyCatalog.luau` and `ZombieTypes.luau` are authoritative.

### Wave-ready speeds (2026-09-28)

Playtest feedback: every mob was far too slow against the 24 studs/s player base, so ranged builds never took damage. All speeds were raised (table above; the hammer boss went from 4.5 to 15). Rough tiers against the player: fast skirmishers (Werewolf, Ember Spider, Baby) ~85%, standard melee 65–75%, heavies and ranged ~50–58% (ranged stop at range anyway). Kiting still works; standing still does not.

Imported mobs have short authored strides, so their Move clips now cap at 4 loops/s on the client and feet glide slightly above that; the hammer boss gait caps at 1.8× its authored rate. Native zombies keep planted-foot stepping. A proper fix for the glide is re-authored run clips with longer strides.

Spawning is now Brotato-style (see `RogueliteZombieChase.server.luau`): enemies arrive in groups of 2–4 at points 28–70 studs from a random living player (never within 22), each marked by a pulsing red X for 1 s. If a player stands within 5 studs of a group's marks when they resolve, that group spawns at a nearby open spot instead (14–30 studs away) — it is never cancelled. Points are floor-level only (never cliffs, terraces, boulder tops or the NoClimb rock/tree footprints) and inside the `SpawnAreaCenter`/`SpawnAreaRadius` attributes on `Workspace.RogueliteZombieSpawn` (83, 2, 476 / 118 on Map One). Replacements queue 2 s after a death, then telegraph.

## Animation and attacks

`RogueliteZombieAnimation.client.luau` presents Idle/Move/Attack from server timestamps. The preferred native rigs use relaxed shoulders, forward torso lean, bent knees and opposing limbs. `NativeEnemyFeet.luau` solves their actual Motor6D leg chains; planted travel is tied to measured root displacement, with a lifted swing and matching endpoint velocities.

The eighteen imported models use retargeted `StudioAnimationData.json`, generated against their actual native FBX Bone or Motor6D rest frames. These are local CFrame clips, not invented published animation IDs. `EnemyMotion` supports the imported joint aliases and duplicated bone hierarchies. Walking clips advance by actual distance and measured stride. Ghost, slime and snake use speed-normalized time for their floating/sliding body motion. Transitions blend briefly; established gaits are not continuously damped. Import normalization is tracked by `EnemyBaselineModelScale`; child slime translations and stride scale with the model.

`EnemyAttacks` owns melee, visible projectiles and locked-direction lunges on the server. Damage checks current life/phase, range, elevation and wall occlusion; projectiles use swept travel against players and world geometry. Native Tank retains `ZombieAttacks`. Arrow, rock, icicle, fireball and spit release from sampled hand/claw/casting/mouth anchors. The bow's aim offset comes from its actual arrow release direction. The cosmetic nocked arrow hides at release; HeldRock hides until recovery. Children of Lava Slime carry `SplitChild` and cannot split again.

## Source and packaging

- `InstallRegularEnemyTemplates.luau` clones reviewed imports into `ServerStorage.RogueliteNPCs`; raw imports remain untouched. Native template changes are limited to intended tuning/metadata.
- `build_enemy_animation_modules.py` accepts only Studio-retargeted payloads. It splits large clips to respect Studio's 200,000-character Source limit.
- `EnemyAnimations/` contains the packaged local clips. The generated modules retain original mesh import provenance separately from animation authoring provenance.
- Native model bundles must preserve geometry, skins, Motor6Ds, SurfaceAppearances and uploaded asset references. They are exported directly from Studio; receipts are not substitutes for those model files.
- `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx` verifies the combat package. The root `CopyTheScene` build is separate.

Do not blanket-sync the place or replace unrelated Studio content. The reusable QA scripts are intentionally excluded from the production Rojo tree. Studio practice continues to use the existing nonpersistent path.

## Verification

Fresh dependency-isolated Edit checks passed **252,989 assertions**, covering all 21 catalog entries, 54 required imported Idle/Move/Attack clips, 1,134 sampled poses, exact template HP/speed defaults, and complete bindings to real imported joints. Native foot tests passed **663 samples/checks** using independent forward kinematics through the actual C0/Transform/C1 chains: maximum stance drift <0.0000081 studs, ground error <0.0000069, sole penetration <0.0000023. Opposite foot/hand covariance was positive for all three rigs; same-side covariance was negative.

These numeric checks do not replace actual Play inspection. `RegularEnemyQA.luau` creates an isolated Studio-only stage, captures physical travel/grounding, stops the models, exercises every server attack, and records recovery. `RegularEnemyQA.client.luau` observes real client poses and state transitions. After telemetry, `Q.inspect(id, 'Idle'|'Move'|'Attack')` permits repeatable visual inspection without overwriting the first results. `Q.cleanup()` restores player state and prior combat attributes; stopping Play also discards the stage.

Actual Play evidence and final native bundle paths will be recorded after that run. Multiple real clients, high latency, mobile performance and published DataStores remain untested.
