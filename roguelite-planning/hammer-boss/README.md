# Hammer boss — reference rebuild

The current deliverable is **`finished/HammerBoss.blend`**. Earlier files in this folder and `reference-rebuild/` are authoring drafts, not the installed boss.

The rebuilt model is 11.92 studs tall, with a 9.05-stud handle. Carry grips are 5.33 studs apart; attack grips slide to 6.55 and 8.05 along the shaft, 1.50 studs apart near its end. It has a projecting belly, torn cream shirt, suspenders, charcoal trousers, rounded hips and seat, closed grips, and a beveled iron hammer. Enlarged traps/back blend into the unchanged shoulders. Green skin retains the Tank family palette; the boss now has its own modeled scarred brow, narrowed eye, and broken-tooth snarl. It is a reconstructed 3D interpretation of the supplied single view; hidden surfaces are authored rather than recovered from that image.

## Extended attack paths — September 24, 2026

Rebuilt the attacks around near-straight reach rather than pulling the grip inward to satisfy the wrist solver. Both arms reach 97.3–97.6% of their available length during active strikes, with a small positive elbow bend. The slam raises both wrists above 13.1 studs (the model is 11.92 studs tall), carries the hammer behind the head, and follows through with the hands held forward. Swing/spin torso rotation follows the weapon, with the intended striking face leading. The horizontal head-height constraint now continues smoothly through recovery instead of switching off at the end of the damage window.

Idle and every attack share the same solved carry pose. Attack endpoints match it within 0.000002 in exported pose components; spin foot/head rotations also return cleanly through the full revolution. The elbow hinge uses 12–130 degrees and remains enforced after frame and clip blending. The authoring optimizer can adjust the weapon pitch while keeping both hands on the shaft. The model's mesh proportions were not lengthened. A whole-clip elbow planner limits changes in shoulder swivel while preserving the authored hand and hammer paths; the final maximum authored changes are 9 degrees for slam, 15 for swing, and 16 for spin. Runtime interpolation now follows the held handle point relative to the torso and interpolates the hands relative to the weapon, preventing independent world-space interpolation from cutting inward across the swing arc.

Final checks passed: every authored attack frame retained hand contact and joint closure, maximum wrist bend stayed below 35 degrees, and the shaft stayed outside the torso core throughout windup/strike/recovery. Arm centerlines are required to remain outside the torso core; the former padded shell was removed because the user explicitly allows slight muscle overlap. These sampled core tests are not an exhaustive mesh-intersection proof. Runtime checking covered 2,307 poses/transitions, and 87 actual client poses matched within 0.00392 studs and approximately 0.07 degrees. The initial 0.00001 basis-vector diagnostic was tighter than the observed Motor6D precision; the rendering regression uses 0.01 studs and a 0.002 basis-vector difference (approximately 0.12 degrees). Single-client Play verified one active hit per attack, zero early hits, the slam inside/outside boundary, and 18.02 studs traveled in four seconds. Both Rojo packages built. The final full sequences are in `finished/ElbowMotionReview.mp4` at half speed. Multi-client/published behavior was not retested.

Installed in the authorized Studio place. Previous motion is preserved in `ServerStorage.BeforeHammerBossExtendedReach`. The reports below are historical.

## Elbow hinge correction — September 23, 2026

The previous wrist-fitting solver allowed elbow branch flips and independently rotated the upper and lower arm sections. The replacement gives both sections the same hinge axis, keeps signed elbow flexion between 8 and 130 degrees, and limits shoulder swivel to 75 degrees either way. Bone lengths remain fixed. The same constraint runs after frame interpolation and after client transition blending, so interpolated poses cannot bypass the limits. Death releases the hammer grip as the body falls.

All seven clips were rebuilt and installed in the authorized Studio place. Horizontal attacks now keep the hammer head at player height through their damage windows. The 7-stud slam radius, faster spin, heavy gait, and paired handle grips are retained. The prior installed motion is backed up in `ServerStorage.BeforeHammerBossElbowHinge`.

Validation: every authored frame passed signed hinge, joint closure, grip and wrist checks; 2,307 runtime samples including locomotion transitions passed. The final live client matched 87 applied poses within 0.0032 studs. Single-client server tests confirmed one hit per attack, zero early hits, a slam hit at 6.5 studs and miss at 7.5, and 18.09 studs of walking in four seconds. Both Rojo packages built. Full attack sequences were rendered for geometry review in `finished/ElbowMotionReview.mp4` at half speed. Published/multiplayer testing remains unverified. An unrelated CardShowcase missing-child warning was observed during an earlier test.

The reports below describe previous revisions unless explicitly labeled as the elbow correction.

## Deliverables

The latest traps/arms revision raises and widens the trapezius and upper back into the unchanged shoulder caps. Biceps, triceps, and forearms have fuller shaped profiles with narrower elbow/wrist transitions. The shirt and suspenders are fitted by ray-casting onto the enlarged body surface rather than using an approximate torso outline. Prior grip geometry and hand orientation are retained.

- `finished/HammerBoss.blend`: editable meshes, 17-bone rig, packed textures, seven actions, review stage and camera.
- `finished/HammerBoss_Import.fbx`: textured static sections for Roblox import.
- `finished/Idle.fbx`, `Walk.fbx`, `Slam.fbx`, `Swing.fbx`, `Spin.fbx`, `Hit.fbx`, `Death.fbx`: rig and baked 30 FPS animation exports.
- `finished/textures/`: individual 1024 × 1024 maps for all 16 sections, including the new modeled face. The old `HammerBoss_Color.png` is superseded.
- `finished/HammerBoss_NPC.rbxmx`: installed Roblox template, including uploaded mesh and texture references, Humanoid and Motor6Ds.
- `finished/BossDataMain.luau` and `finished/clips/`: matching motion samples used by both client presentation and server collision. Clips are split to respect Studio's per-script source limit.
- `finished/studio-asset-manifest.json`: complete template properties and attributes, including uploaded asset IDs.
- `finished/LeftGrip_Front.png`, `LeftGrip_Under.png`, `LeftGrip_Contact.png`: close-up geometry/contact reviews; `HammerBoss_Back.png` shows the continuous back and fuller trousers.

## Studio integration

Installed in the authorized **roguelite place 107877054949326**. The template lives in `ServerStorage.RogueliteNPCs.HammerBoss_NPC`; the visible comparison is `Workspace.ZombieVariantPreviews.HammerBoss_Preview`, beside the Tank. Unrelated NPC templates and previews are retained. Modified pre-boss scripts are backed up under `ServerStorage.BeforeHammerBoss_20260923`; the prior boss model and motion modules are retained under `ServerStorage.BeforeHammerBossSkinGrip_20260923`.

The version immediately before this continuity revision is retained under `ServerStorage.BeforeHammerBossContinuity_20260923`. All 16 mesh sections use `SurfaceAppearance` color maps and Precise render fidelity. SurfaceAppearance avoids the dark atlas seams observed when the same textures were rendered through Humanoid/TextureID compositing. The saved template and installer both preserve this fix.

The encounter uses wave 20 by default; `ReplicatedStorage.RogueliteCombat.HammerBossWave` can override it. Wave completion waits while the boss is alive. Changing the normal enemy count preserves the boss. Stopping a wave removes it. Boss movement and hit decisions run on the server; clients display the matching poses, warning shapes and impact effects.

Each hand stays closed around the shaft while sliding into the paired attack grip. Arm extension follows fixed bone lengths and a one-way elbow hinge; the weapon path yields to anatomical reach limits. The hammer's local Z striking end leads horizontal/spinning travel. A slam commits its direction before anticipation. Swing and spin collision sample the actual oriented head at 120 Hz during their active windows; each player can be hit once per attack. Warning shapes do not themselves deal damage.

Walk is a 1.6-second asymmetrical gait authored at 4.5 studs/second, with a lower dragging left step, longer right support, weight sway and 0.558 studs of authored hip bob. Client phase follows horizontal distance traveled. Planted feet move backward relative to the root at the matching speed, reducing sliding. The weapon lifts enough to clear the ground during the body drop.

In Studio, open **Stats / Test [P] → Zombies → Spawn boss / Remove boss**. These server-validated controls allow one practice boss, reject extra arguments and rapid requests, and grant no boss rewards. Set normal zombies to zero for an isolated fight. The HUD shows **HAMMER BRUTE** with the nearest living boss's HP; it hides after death/removal and resets for a new boss.

| Move | Warning begins | Active damage | Return to idle |
| --- | --- | --- | --- |
| Slam | frame 5 | frames 23–24 | frame 50 |
| Swing | frame 6 | frames 19–25 | frame 54 |
| Spin | frame 6 | frames 21–37 | frame 66 |

Frames use 30 FPS and start at zero in the design data; Blender's timeline starts at frame 1. Idle, walk, hit and death last 96, 48, 18 and 84 frames respectively.

`BossService.spawn(cframe, true)` creates a Studio-only practice boss. Practice death gives no shard drop. Death cancels attacks immediately, preserves the visible death pose for 2.9 seconds, then removes the model. No DataStore access is introduced.

## Elbow, wrist and weapon-distance fix — September 23, 2026

Attacks showed popping elbows, twisted wrists and the hammer pinned against the
body. Measured cause, not guessed:

| | before | after |
| --- | --- | --- |
| Max arm extension, Slam/Swing/Spin | 99.8 / 99.7 / 99.4 % | 93.7 / 93.7 / 93.6 % |
| Min elbow offset from the shoulder-wrist line | 0.18 / 0.22 / 0.32 studs | 0.94 / 0.90 / 0.92 studs |
| Idle (unchanged control) | 89.8 %, 1.22 studs | 89.8 %, 1.22 studs |

`ELBOW_MIN` in `wrist_motion.py` was 8 degrees. That is the minimum elbow *flex*,
so it set the reach sphere at 99.8% of (upper arm + forearm), and the grip
optimiser in `solve_grips` always pushed to that limit because its
belly-clearance penalty drives the weapon outward until the projection stops it.
At that extension the elbow sits on the shoulder-to-wrist line with almost no
perpendicular offset, so its bend direction is unconstrained and flips between
frames — the popping elbow. The locked forearm then forces the hand joint to
absorb every orientation change, which is the twisted wrist. `lever_motion.py`
also carried a 1.6-stud inward pull whose own comment says it existed to buy back
elbow flex; that is what held the hammer against the belly.

Fix: `ELBOW_MIN` 8 → 42 degrees, the paired-grip reach target expressed as a
fraction of arm length (`ARM_TARGET` / `ARM_CEILING`) instead of a 0.025-stud
margin, and the inward pull reduced from 1.6 to 0.30 studs. `minFlex` in
`BossMotion.luau` was raised to match — the runtime re-solves both arms every
frame, so if the two constants disagree the runtime produces a pose the clips
never contained. With them matched, the runtime reproduces the baked clips to
within 8e-6 studs of elbow displacement and 0.0002 degrees of forearm twist
across all seven clips.

Only `Slam`, `Swing` and `Spin` changed; `Idle`, `Walk`, `Hit` and `Death` are
byte-identical. Attack reach is effectively unchanged (Slam 9.14 → 9.31, Swing
9.04 → 9.12, Spin 9.59 → 9.56), so hit windows and warning shapes were not
rebalanced. `test_elbow_runtime.luau` now asserts a 41.9-degree floor instead of
7.9 so a revert of either constant fails the regression; it passes over 2307
samples with zero hinge-axis mismatch and a 1e-6 maximum joint gap.

The pre-fix sources and clips are kept in `before-arm-flex/`, and the pre-fix
Studio modules in `ServerStorage.BeforeHammerBossArmFlex_20260923`.

Verified: the numbers above, measured both offline against the clip files and
in Studio against the live modules; a posed before/after comparison and a
five-frame swing-arc strip inspected in the Studio viewport. Not verified: a
Play-mode run of the encounter, and multi-client behaviour.

## Validation

**September 23 wrist alignment revision:** Slam radius is 7 studs, double the previous radius and four times its area. Both the warning disc and impact debris use that radius. `wrist_motion.py` solves the paired grip, wrist roll around the shaft, elbow placement, and forearm twist together. The wrist cuff now follows the forearm instead of inheriting the hammer head's roll unchanged. The solver allows elbow flexion rather than forcing 99% extension, which was incompatible with the existing grip geometry; active hammer reach remains above 9 studs. This replaces the prior locked-elbow constraint.

`validate_wrists.py` checks every authored attack frame for wrist bend below 35 degrees, wrist joint closure below 0.001 studs, radial grip drift below 0.001 studs, and clearance from a conservative torso core. Maximum measured bends are 19.13 degrees for Slam, 31.83 for Swing, and 20.80 for Spin; joint gaps and radial grip drift are below 0.000007 studs. `validate_lever.py` still verifies contact at the handle end, the correct striking face, and exact slam ground contact. The walk's planted-foot and bob checks still pass. Native Blender side views are saved as `WristReview_*.png`. These are sampled geometric checks, not exhaustive mesh collision proof. Historical reports below refer to their stated revisions.

The wrist revision was installed into the open roguelite place and tested with one Studio client. Slam hit at 6.5 studs and missed at 7.5; all three attacks had zero early hits and exactly one active hit. Eighty-seven client pose samples, including both hands and forearms, matched the authored orientations (reported angular error zero) and positions within 0.003202 studs. A stationary swing pose was also inspected in Studio. The only captured output afterward was the connector restoring the temporary review camera. Both packages built. Native place save, exhaustive motion review, multi-client latency and published asset access are unverified. Backups are under `ServerStorage.BeforeHammerBossWrist_20260923`.

**September 23 motion polish:** Slam radius is now 3.5 studs (previously 2.35), with matching warning/impact spread. Spin uses 36 fps instead of 30 and continuous angular travel through its active revolution. Windup rotates around the held end; outward elbow poles and a paired-grip torso-clearance projection replace the unstable windup/recovery paths. Attack entry blends for 0.12 seconds, before damage can begin. `inspect_arm_motion.py` checks all exported idle/walk/attack frames against a conservative torso core and caps torso-relative elbow steps at 0.85 studs/frame; these are sampled checks, not exhaustive mesh collision proof. Active arm extension remains above 99.3% and both grips remain attached.

The installed revision passed all three single-client server attack tests with zero early hits and exactly one active hit. The slam test placed the player 3.2 studs from impact, outside the old radius. Walk travel was 18.024 studs in four seconds. All 87 actual client pose samples passed (maximum hand/hammer position error 0.003202 studs); Studio's output log was empty. Both Rojo builds passed. Blender windup and swing renders were inspected; exhaustive visual review of every angle and multi-client latency remain unverified. See `finished/polish-studio-test-results.json`. Previous Studio modules are retained in `ServerStorage.BeforeHammerBossPolish_20260923`.

**Current September 23 lever/heavy-walk revision:** `heavy-motion-checks.json` measures minimum active arm extension of 99.3%, zero leg overreach, planted-foot drift below 0.000001 studs/frame, and 0.558 studs of authored bob. `lever-motion-checks.json` measures grip drift below 0.000004 studs, correct leading striking faces, and slam ground contact within 0.000003 studs of the intended clearance. Finger tube frames were repaired to prevent collapsed circular holes.

`heavy-studio-test-results.json` records 87 actual client pose samples (maximum hand error 0.003016 studs, hammer error 0.000977), all three attacks with zero early hits and exactly one active hit, and 18.006 studs of travel in four seconds. A further 176 moving client samples showed 0.843 studs of rendered hip height variation including the locomotion transition. The HUD showed full/half health, hid on removal/death, and reset to full after respawn. New face and both shoulder textures were visually checked in Play and Edit. Several failed import maps were replaced by direct image uploads; raw-ID preload callbacks still reported failure despite visible rendering, so published asset access remains unverified. A temporary texture diagnostic caused a Plugin-capability error and was removed; no gameplay errors were observed. Both Rojo packages built successfully. Studio save was requested after returning to Edit.

The prior installed model/modules/scripts are preserved in `ServerStorage.BeforeHammerBossLever_20260923`. Reports below describe earlier revisions and are historical, not reruns of the latest implementation.

The current traps/arms revision passed 87 actual client pose samples across seven clips (maximum hand error 0.003015 studs, hammer error 0.000977 studs). All authored frames passed reach and grip checks. At rest, 7,680 shirt vertex/face-center samples had no body penetration, with minimum signed clearance 0.0966 studs; this sampling is not an exhaustive intersection proof. Front and rear views were inspected in Studio. Both Rojo packages rebuilt successfully. See `finished/traps-muscles-test-results.json` and `finished/garment-fit-checks.json`. The immediately preceding model and modules are retained in `ServerStorage.BeforeHammerBossTraps_20260923`.

The current continuity revision passed 87 actual client pose samples across all seven clips, with maximum hand error 0.002903 studs and weapon error 0.000977 studs. Authoring checks also passed every frame. Sixteen contact probes per hand measured maximum positive shaft clearance below 0.019 studs; slight negative clearances indicate contact/intersection. These probes are not an exhaustive collision proof. Final wrist and rear views were inspected in Studio after the surface rendering fix. See `continuity-test-results.json`, `grip-contact-checks.json`, and `fbx-roundtrip-checks.json` in `finished/`.

After the skin/grip revision, 87 actual client pose samples across all seven clips kept both hands and the hammer within 0.005 studs of their expected positions (largest hand error 0.002844 studs at the preview's world offset). All authored frames also passed the regenerated arm-reach checks. See `finished/skin-grip-test-results.json` and `finished/authoring-checks.json`. The gameplay checks below were performed before this visual revision; combat logic was unchanged. Revised template installation alignment error was 0.00000125 studs, and both Rojo packages built again successfully.

The rebuilt proportions, grip, front/three-quarter views, overhead windup, slam contact, swing, spin and collapsed death poses were inspected in Blender renders. Every authored frame passed arm-reach checks, and both grips use the same weapon transform throughout. These checks do not prove a perfect match to the reference or exhaustive absence of mesh intersections.

Single-client Studio Play testing verified all three attacks cause no damage before the active window, exactly one hit per attack, and no extra damage during recovery. Client warnings appeared as circle, arc and circle, and the client applied poses across 490 observed simulation frames. Actual post-defense damage in this test was 20.4, 15.3 and 18.7. Killing during anticipation cancelled damage, retained the death animation briefly, removed the boss afterward and generated zero practice drops. Results are saved in `finished/studio-test-results.json`.

The wave-20 regression verified automatic spawn, preservation across population changes, blocking timed wave completion while alive, and transition to the wave-21 shop after death. A separate movement check recorded 14.11 studs of travel in two seconds with an unanchored living boss. These final runs produced no runtime errors; their reports are saved beside the attack test results.

The last pose regression repeated slam and spin after the ground-contact adjustment and measured a 360-degree active spin sweep. Both retained their no-early-damage and no-repeat-damage guarantees, with no runtime errors.

Both the root CopyTheScene package and the roguelite combat package build successfully. Multi-client latency, published asset access, long-run balance, and exhaustive full-speed/half-speed review from every angle remain unverified.

## Rebuild and provenance

Run `reference_rebuild.py`, then `finish_reference.py` with Blender 5.2. `revise_motion.py` rebuilds motion and previews from the finished baked model without rebaking textures. The combat Rojo project includes the boss template and scripts.

The supplied image is preserved unchanged as `source/boss-reference.png`, SHA256 `B401488FE31019B7D2179CBCF652D17082BA92E1B5ED7AD2BF2D5A64736CA6F6`. Body, clothing, hands, facial features and hammer are authored Blender geometry. Clothing and weapon materials are procedural and baked. Skin uses the established local `baby-mutant-zombies/source-art/MutantTexture.png`; the face uses newly modeled features baked into its own map, rather than the Tank face tile. No Creator Store character or external character model was used. The impact uses Roblox's bundled `impact_explosion_03.mp3` and smoke particle texture.

## Flat-face slam follow-through and level swing (September 24)

The slam keeps its approved overhead and middle weapon path through frame 20, then continues the rotation into a horizontal shaft and flat lower striking-face contact. The torso follows the hands down. The horizontal swing eases from its carry windup into a level shaft for the entire active window; recovery releases extension progressively to avoid forcing the wrists as the grip returns. Spin is unchanged.

Updated separate review videos are in `finished/attack-videos/`: Slam.mp4, Swing.mp4 and Spin.mp4. Each shows normal speed followed by half speed. These are Blender renders of the exported animation data, not gameplay recordings.

All authored wrist, hinge, grip, reach, ground-contact and walking checks passed. Studio checked 2,307 interpolated poses/transitions with signed elbow flexion 12–101.574 degrees and maximum joint gap 0.00000267 studs. All 87 actual client pose samples passed (maximum position error 0.003913 studs; basis-vector error 0.001184). Both Rojo packages built. Combat damage logic is unchanged; the earlier damage-window tests were not rerun for this animation-only revision. The full multiplayer loop was not tested.

## Shoulder-loaded swing and spin (September 24)

Swing and Spin now lift the original separated carry grip toward the right shoulder before sliding either hand. Both elbows bend about 74–77 degrees at the loaded pose. The grip then slides toward the handle end while the arms extend into a level horizontal strike. Swing covers 180 degrees during its active window; Spin continues through 360 degrees. The approved slam is unchanged. Updated normal/half-speed previews are in `finished/attack-videos/`.

`validate_shoulder_sweeps.py` checks the unchanged grip through the shoulder lift, bent elbows, raised hammer, level active shaft, and sweep angles. These and all wrist, hinge, reach, grip, ground-contact and walking checks passed. The Studio pose regression passed 2,307 samples/transitions with a maximum joint gap of 0.00000267 studs. Both Rojo packages built. Damage timing and gameplay code are unchanged; multiplayer behavior was not tested in this revision.

Client playback also passed all 87 pose samples (maximum position error 0.003913 studs, basis-vector error 0.001184). The initial Studio Play startup stalled; activating Studio and starting playback completed the test. Idle, Walk, Slam, Hit and Death clip data were compared with the preceding commit and are unchanged.

## Direct carry recovery and larger runtime boss (September 24)

Swing and Spin now recover directly in torso space around the held end of the hammer. The right hand slides from its attack grip back up the shaft; the left hand remains attached and takes the shortest roll back to its resting orientation. The old second pitch-down/handle-to-face motion is removed. Reach projection moves both hands with the weapon, and the final pose exactly matches carry. Wrist roll values are normalized before carry blending to prevent accidental full rotations.

Runtime size is 1.15 times the authored size. BossMotion scales a private pose-data copy, and BossService scales each spawned model exactly once. Rest transforms, joint pivots, hammer collision, warning sweep width and ground offset use the same scale. Authored stride distance scales with the body while movement speed remains 4.5 studs/second; health, damage and the slam radius are unchanged.

All authored checks passed. Recovery wrist height stays below 5.97 authored studs, and maximum left-grip rotation per frame is 12.68 degrees. Studio passed 2,307 interpolated joint samples (maximum gap 0.00000377 studs), plus 87 actual client poses (maximum position error 0.005043 studs). Both packages built. Updated normal/half-speed videos show the authored motion; the 15% enlargement is applied in-game. Multi-client behavior was not tested.

Final single-client gameplay checks passed: one hit per attack, zero early hits, a miss at 7.5 studs outside the slam radius, and 18.015 studs of walking over four seconds at the unchanged speed of 4.5. Reapplying model preparation did not change its size. See `finished/recovery-scale-studio-checks.json`.

## Hit areas (2026-09-30)

User playtest: hits that looked certain missed. Before, Swing/Spin only hit within 0.85 studs of the hammer head, while the red warning showed a wider band (Spin: a full disc).
- **Swing/Spin** now hit anyone within `BossMotion.SweepRadius` (2.8 × scale = 3.2 studs) of the line from the boss to the hammer head as it sweeps, including between the boss and the hammer. The Swing warning ribbon is filled in to the boss to match; Spin's disc already was.
- **Slam** radius 9.5 (was 7); it also hits players up to 6 studs above the impact (was 4), so a plain jump no longer clears it. The warning disc and impact chips read the same radius.
