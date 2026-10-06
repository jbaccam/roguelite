# Blender to Studio event implementation plan

## Outcome and scope

Deliver five distinct round 10 encounters, polished models and animation, unique intros for those encounters and all five map bosses, and consistent Hammer Brute naming. Use the existing game style and source-owned combat overlay. Finish one complete asset-to-game slice before expanding the batch. Quality is established by renders, deformation checks, fresh imports and actual gameplay footage, not by promising perfect first-pass generation.

This is an implementation plan, not a claim that work or tests below have run. Encounter direction is in [Round 10 events and boss intros](2026-10-05-wave-10-events-and-boss-intros.md). Numeric art and gameplay targets below are initial project targets, subject to measured import behavior and playtesting.

## Phase 0 Baseline and integration inventory

1. Record Git branch, commit and dirty files. Preserve concurrent work; do not reset or overwrite it. The October 5 checkout has active combat, scaling, rewards and presentation changes. Reconcile those before changing the same modules.
2. Read CURRENT_GAME_STRUCTURE, the combat README, ENEMY_SIMULATION_ARCHITECTURE, BOSS_GAME_PACKAGE_SPEC, mob-production/combat-ready/README, and the latest per-asset import receipts.
3. The new SWARM_PRESSURE_2026-10-05 note describes doubled occupancy and faster refill, capped at 100 regular slots. Four-player targets reach the cap early. Measure this version before adding another multiplier. Its note does not establish completed multiplayer or mobile testing. The combat README currently links a missing aggregate COMBAT_FEEDBACK_2026-10-05 file; use the existing individual reports until that link is resolved.
4. Discover Blender MCP and Studio MCP capabilities for the session. In Blender, inspect active file, objects and missing external files before editing; save a separate working copy. In Studio, list connected instances and identify place 107877054949326; confirm the selected instance as required by the connector before mutations. Read-only planning does not require modifying either app.
5. Capture existing normal zombie, crab, mummy, werewolf, slime and boss bounds, root/ground offsets, material setup, animation identifiers and rig type. Take a baseline gameplay-camera screenshot beside a normal avatar.
6. Inventory existing boss intros and clips. Preserve already-good models/animations; add missing unique introductions rather than rebuilding approved bosses unnecessarily.

Exit: baseline manifest, target place, exact source/template mappings and a documented file scope for the first slice.

## Phase 1 Lock model construction and size

Use these latest reference sheets under art-references/round-10-events-2026-10-05:

| Asset | Sheet | Required identity and construction |
| --- | --- | --- |
| Exploding zombie | 01-exploding-zombie-v3.png | Yellow, near-spherical inflated belly, puffed cheeks, complete arms and hands, short legs; belly can animate without swallowing hands or garment scraps. |
| DJ crab | 02-dj-crab-v1.png | Coral shell, eight walking legs plus two pincers, headphones and rear-facing twin speakers; accessories separate from leg joints. |
| Sarcophagus | 03-sarcophagus-v1.png | Hollow body with solid rear, removable lid that actually fits; separate lid, body and break pieces. |
| Tomb Warden | 04-mummy-brute-v2.png | Wrapped body, broken stone mask, large stone fists, teal sash; readable without size being its only difference. |
| Alpha werewolf | 05-alpha-werewolf-v2.png | Russet body, dark mane, pale chest/tail tip, notched ear; clear difference from gray regular wolf. |
| Vent | 06-volcanic-vent-v1.png | Low basalt ring, recessed opening, separate lava/glow section; fixed terrain-relative pivot. |
| Debris | 07-volcanic-debris-v3.png | Five small separate fragments, no matchstick, no collision; reuse for short cosmetic bursts. |

Create a single canonical front/side/back blockout. Generated sheets can disagree: reconcile one actual 3D structure rather than reproduce incompatible silhouettes. Validate the crab's hidden legs, mask break side, wolf tail attachment and coffin wall thickness explicitly.

Proposed starting scale relative to measured existing templates: bloater about normal zombie height but 1.6-1.9 times torso width; DJ about 1.4-1.6 times regular crab width; Warden 1.4-1.6 times regular mummy height; alpha 1.25-1.4 times regular wolf height. These are comparison targets, not values to stack on existing scale multipliers. Choose final studs from the avatar lineup. Coffin cavity must clear the Warden's actual emergence pose; a side-on pose may fit better than an unnaturally wide coffin. Keep vent height low enough that it does not become a wall. Start debris around 0.15-0.5 studs and judge it in motion.

Store height, width, depth, foot contact plane, root height, logical collision radius, visual bounds and accessory bounds separately. Oversized visual mane or belly does not silently enlarge an attack's hitbox. Use the same ground-origin convention throughout the asset package.

Exit: gray blockouts pass close-up and actual gameplay-distance silhouette review alongside regular mobs. No textures or detailed animation until proportions work.

## Phase 2 Mesh construction and edge quality

1. Build intentional low-poly forms; AI-to-3D output is only a starting mesh. Remove duplicate/internal faces, floating scraps and unusable topology. Rebuild hands, joints and accessory connections where necessary.
2. Use real narrow bevel geometry where the silhouette needs softened edges. Start with one or two segments, adjusting to object scale. Do not apply a global subdivision modifier that erases the faceted style.
3. Use selective smooth shading and sharp-edge/angle controls. Inspect normals under a moving neutral light. Smooth shading alone cannot round a box silhouette; weighted/custom normals must survive export to count as part of the result.
4. Keep deformation loops around shoulders, elbows, wrists, hips and knees. Concentrate extra geometry on hands, face silhouette and belly deformation, not invisible undersides.
5. Preserve broad fur clumps and chunky bandage wraps. Avoid loose micro-strips and hundreds of individual hair pieces. Bind rigid stone fists/mask and crab speakers rigidly rather than letting them melt with skin weights.
6. Apply/normalize authoring transforms before rig binding using the tested pipeline; do not apply transforms blindly to an already-bound approved rig. Keep a non-destructive source and an explicit export copy. Lock export triangulation so normals and skin deformation are reproducible.
7. Initial total triangle targets: bloater 3-6k; DJ 5-8k; Warden 5-8k; alpha 6-10k; coffin body plus lid 1-3k; vent 0.5-1.5k; each debris fragment 30-150. These are project performance budgets, not Roblox platform limits. Existing boss spec also asks each imported section to stay below its 20k-triangle validation threshold. Check current platform specifications at implementation time.

Exit: no accidental holes, inverted normals, paper-thin fingers or intersecting accessories; flat clay renders and wireframes approved in front, side, back and gameplay view. Record total triangles, mesh sections and material count.

## Phase 3 UVs and textures

1. UV unwrap after shapes stabilize. Place seams away from faces and highly visible belly areas; checker-test stretching at joints and curved surfaces. Give mirrored regions overlap only when intentional; preserve unique mask damage and asymmetric markings.
2. Use the project's broad painterly 2-4 value palette, matte appearance and low texture noise. Keep high-frequency dirt and baked dramatic shadows out of the maps.
3. Start with one 1024-square base-color atlas per character and one prop atlas where practical. Do not give every small section a separate 1024 image. Choose lower resolutions for debris and increase only where actual gameplay view justifies it.
4. Add sufficient island padding for mipmaps; inspect the texture downsampled and from a distant camera for seams/bleeding. Match texel density across the body and accessories.
5. Keep emission masks/glow sections separate from normal surface color. Bloater yellow must remain recognizable when no effect is active. Teal cloth and russet fur must still contrast in desert/snow lighting.
6. Bake any Blender-only procedural appearance into delivery textures. Check base-color color space and data-map settings. Package real image files and confirm there are no missing links.
7. Inspect Studio lighting early: Blender material success is not proof of Studio material success. Check that white hit flashes restore the correct material/texture state afterward.

Exit: textured turnaround, gameplay-scale comparison, seam review and fresh-file texture-load check pass. Keep reference-style matte surfaces rather than shiny plastic.

## Phase 4 Rig and deformation

Use a control rig for authoring and export only the necessary deform rig. Reuse the existing project's compatible rest-pose and naming conventions where appropriate; reuse does not mean stretching a normal enemy rig onto a different body without correction.

| Asset | Rig needs |
| --- | --- |
| Bloater | Root, hips/spine, head, two complete arm/hand chains and leg/foot chains; limited belly control bones for translation-based swelling/jiggle. |
| DJ | Root/carapace, eight articulated leg chains, two articulated pincer arms and jaws; speaker/headphone attachment controls; optional small eyestalk motion. |
| Warden | Root/hips/spine/head, arms and legs; fists rigid to hands, mask rigid to head, few optional sash controls. |
| Alpha | Root/hips/spine/chest/head/jaw, arms/hands and legs/feet, small tail chain; mane mostly follows neck/chest with restrained secondary motion. |
| Coffin | Separate body/lid transforms; scripted prop animation is sufficient unless a bone rig demonstrably simplifies delivery. |
| Vent/debris | No character skeleton; separate rock/glow sections and effect attachments. |

Normalize weights; remove unweighted vertices and accidental remote influences. Roblox's current mesh specification permits at most four bone influences per vertex. Rigid pieces should use one. Auto-weighting is an initial pass, not the finished skin.

Run a deformation pose suite before authoring clips: shoulders reaching forward/high/outward, elbow deep flexion, wrists through needed rotation, crouch, high step, torso twist, head turn, full pincer opening and leg extension. Check collapsed armpits, pinched knees, floating mask, fist/wrist gaps, inverted elbows and belly-hand penetration. Anatomically extreme poses are tests, not required attack poses.

The current runtime samples rigid transforms. Do not rely on Blender-only shape keys, constraints or animated bone scale for inflation. Bake supported deform-bone motion and prove it through the export/import round trip. If a different deformation mechanism is needed, validate that mechanism as a separate technical spike first.

Exit: documented deformation poses pass; constraints are baked; deform hierarchy is stable; no negative scales, NaNs or unweighted vertices. Any rig change invalidates old retarget receipts and affected animation exports.

## Phase 5 Animation production

Author against the established 24 fps game package convention; runtime interpolation remains smooth. Retain the expected per-pipeline clip names (regular mobs use Move; boss package uses Walk) or explicitly map them. Do not silently rename existing clip keys.

Each action has anticipation, readable acceleration, decisive contact/release, follow-through and recovery. Use hips, chest and footwork together rather than waving a forearm. Favor clean large poses that remain readable at gameplay distance. Review at real time, quarter speed and frame-by-frame.

| Asset | Required animation set |
| --- | --- |
| Bloater | Idle, waddling Move, Hit, stop/brace, Inflate/Arm, Detonate transition, ordinary Death, event intro performance. Decide and document whether lethal damage also detonates; prevent double detonation. |
| DJ | Idle groove, scuttle Move, Hit, beat-command, double-claw slam, recovery, Death, intro power-up/performance. Supporting mobs need compatible rush/bombardment cues. |
| Warden | Idle, heavy Move, Hit, coffin emergence, stone-fist attack with windup/impact/recovery, Death. Match coffin dimensions and lid trajectory. |
| Alpha | Idle, Move, howl, charge-start/charge-loop/charge-end, claw follow-through, Hit, Death, intro entrance. |
| Coffin | Rise, lid-rattle, open, spawn pulse, damage response, break/disable; safe debris paths. |
| Vent | Warning charge, eruption, active hold, cooldown through effect timing; no pointless skeletal animation. |

Keep existing full bosses' attack identities: Cyclops ground slam and stomp; Dragon breath, broad tail whip and front stomp; King Crab claw/rush/bubbles; Pharaoh bolts/tomb eruption; Hammer Brute's established kit. Add or refine their unique intro clips only as needed.

Movement: plant feet with IK in Blender, bake deform bones, record stride length and drive runtime cycle from actual travel. Avoid sliding during planted phases or jogging while stationary. Initial review threshold: planted-foot drift below 0.05 studs at final scale, excluding intentional skids. Scale stride once, not twice. Server owns actual chase/charge displacement; animation supplies cosmetic local motion.

Attacks: record warnStart, directionLock, impact/release, activeEnd and recoveryEnd in seconds. Define actual hand/claw/mouth/ground-contact attachment points. Damage timing comes from the server using the same metadata; client animation markers are not authority. Sample fast sweeps sufficiently to avoid missing targets between frames.

Loops: first/last pose and velocity should join without a pop. Hit reactions must blend without corrupting attack state. Death ends stable above terrain, clears gameplay state once and never resumes movement. Secondary tail, cloth and belly motion should follow the main action without clipping or becoming visual noise.

Exit: one contact sheet per asset showing key poses, short actual-mesh videos for every clip, transition tests and timing metadata. Review both frontal and side motion; a flattering single angle is insufficient.

## Phase 6 One asset round trip before batch export

Start with the yellow bloater. Prove its model, hands, belly deformation, normals, textures and one movement/arming clip through Studio before exporting all other assets.

Package per asset: editable Model.blend, delivery rest FBX, review GLB where supported by the existing review pipeline, textures, AnimationData.json, attack/timing metadata, geometry/rig manifest, previews and validation report with hashes. Static props need only relevant files.

Use the existing rest-FBX settings as a starting contract: forward -Z, up Y, deform bones only, no leaf bones, no animation baked into the rest import, copied/embedded texture files. Bake constraints into sampled animation data separately. Reimport exports into a fresh Blender file and verify geometry, materials, rest bones, bounds and clip data against the source.

Do not assume the historical 100x import expansion applies forever. Measure a calibration object and actual imported bounds; normalize once. Record baseline scale so runtime resizing and stride conversion use a ratio, not a repeated 0.01 multiplier.

Exit: actual Studio-imported bloater matches source at rest and in motion. Only then batch the remaining assets.

## Phase 7 Studio import and MCP integration

Available Studio MCP tools include listing instances, inspecting instances/tree, executing Luau, reading/editing scripts, capturing the screen, reading output and starting/stopping Play. Blender MCP exposes scene inspection, Python execution and renders. Availability does not prove an app is connected.

No arbitrary local rigged-FBX upload tool was identified in this session's exposed Studio MCP inventory. Use Studio's native 3D Importer for that boundary, with supported UI automation or a clearly identified user import step if necessary. Do not claim insert_asset or generate_mesh imports an existing local FBX: asset insertion needs an existing asset ID, and generation is not a faithful Blender import. Use MCP for inspection, adoption, receipts, source integration and validation around that boundary.

1. Import into a staging area, never directly over the working template. Retain zero-influence bones if the project's root hierarchy depends on them. Check texture visibility and asset permissions under the actual owning account/group.
2. Inspect imported MeshParts, Bones, root, Motor6Ds, material/texture IDs and bounds via MCP. A rigid model may import differently from a skinned model; inspect instead of assuming.
3. Save an import receipt containing source hashes, normalized scale, imported rest transforms, mesh transforms, Bone names and Motor6D Part0/Part1/C0/C1 where applicable.
4. Adapt the existing adoption/retarget pipeline. For regular enemies, consult AdoptRegularEnemyImport.luau, InstallRegularEnemyTemplates.luau, combat-ready/retarget_studio.py and build_enemy_animation_modules.py. Register new IDs and source directories explicitly; do not assume the existing scripts accept arbitrary new mobs without extension.
5. Reconstruct world-space deformation against imported rest frames. Install StudioAnimationData-derived runtime modules, not raw AnimationData.json. Verify both Bone and Motor6D paths and that root motion is applied exactly once.
6. Install versioned templates with correct root, pivots, baseline scale, logical collision data and attachments. Cosmetic meshes should not add physical crowd obstacles. Coffin objectives use explicit target metadata rather than accidental decorative hitboxes.
7. Run a Studio edit-time clip viewer: idle, movement, attack, hit, death, introduction. Capture normal camera and close-up views; compare imported contact points with authored ones.
8. Change canonical repo files first and build the combat overlay: `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx`.
9. Synchronize only mapped combat scripts/modules/templates, preserving the existing map and unrelated instances. Never sync the root Copy The Scene project. Check existing source for concurrent edits before overwriting. Apply required Sandboxed/Capabilities properties following the combat README.
10. Compare installed source and manifest hashes, save an installation receipt and retain rollback copies. Runtime installation success is separate from publishing the place.

Exit: correct place, valid import/retarget receipts, matching source and Studio versions, clean clip playback and no relevant console errors.

## Phase 8 Encounter director and authoritative gameplay

Implement a shared server encounter lifecycle: Prepare -> Intro -> Active -> Complete/Failed -> Cleanup -> Shop. Each run/wave has a generation ID so delayed spawns, chain reactions, sounds and intro callbacks cannot leak into later waves.

Define per-event configuration for map/wave eligibility, normal-spawn suppression, spawn sources, population reservation, objective entities, timers, intro, music and completion conditions. Integrate with the existing wave/shop flow rather than run an independent timer that races it. Remove the old round-10 weak boss only for encounters that successfully activate; choose an explicit safe fallback if event assets are missing.

Implement the five rules in the encounter note. Specifically, tombs replace edge spawning; all three must be destroyed and the Warden killed. Tombs spawn ordinary mobs, not recurring Wardens. Ensure automatic weapons can deliberately target objectives without globally changing all target priorities.

Exploders need one authoritative detonation, a visible radius/countdown, bounded chain-reaction work and per-target hit deduplication. DJ coordinated attacks need warnings and traversable gaps. Alpha buffs have bounded duration/range and restore correctly on death. Vent damage must match the warned circle, not debris trajectories; stage active zones so escape paths remain. Slime children count toward the population budget before creation.

Server validates phase, membership, health, distance, attack timing and reward eligibility. Reserve capacity for objectives/elites/children and repair failed spawn slots without duplicating entities. Cancel all hazards on death/reset/abort. Suppress practice/admin persistent rewards and production DataStores. Specify no-reward removal versus normal kills so event cleanup cannot farm XP/shards.

The required long-term architecture is server enemy records with pooled client visuals. The present replicated Humanoid cap is not a measured capacity guarantee. Avoid multiplying beyond it. If current architecture cannot deliver the target pressure, create a separately validated migration to that record-based architecture, then profile progressively; do not silently mix two authorities or launch an unbounded rewrite inside an asset task.

Exit: each event starts once, has one clear objective, finishes once, cleans up and transitions to shop correctly in isolated fixtures.

## Phase 9 Unique intros and presentation

Use a common intro controller for synchronized timing, camera ownership and cleanup; provide unique camera paths, performances, sound and effect cues per event/boss. Reference the encounter note for all ten proposed sequences. Existing map-boss intro data supports sky drops; extend that format for other sequences instead of forcing every boss into the Hammer entrance.

Start around 3-5 seconds. Frame actors relative to their real size and terrain; avoid walls, cliff interiors and other players' accessories blocking the shot. Show event/boss name and objective, then return to the player's previous camera/control state.

Hammer Brute must be the shared display name everywhere, including MapBossDefs introName and BossIntro's legacy table. Preserve stable internal IDs. Audit tutorial, full boss, Endless, health bars and Journal displays.

All participants use server timestamps. No damage, combat clock loss, attack precharging or free boss damage during a forced intro. Preview eruptions/slams are cosmetic. Handle death, reset, disconnect, late join, missing asset, skipped/cancelled intro and consecutive camera requests. Every exit restores camera, input and lighting/audio state. Define repeat/Endless shortening and skip policy without allowing a single player to bypass the encounter's server phase.

Add event music loops and short stings, attack warnings and impact sounds. Keep warnings audible over up to 24 weapons; bound simultaneous voices. Pool debris/particles/lights; retain hazard cues on reduced effects settings. Do not use a famous track by default when an original event loop is needed.

Exit: all five event intros and five boss intros have unique footage; no unsafe camera takeover or stuck controls; no Hammer Zombie display text remains in active paths.

## Phase 10 Multiplayer pressure and performance

Test one, two, three and four actual clients with weak, typical and strong six-slot builds. One client plus fake server players does not verify replication, framing or crowd feel for four clients.

Measure active population over time, spawn-to-contact time, kills/second, refill latency, time spent at cap, per-player pressure and damage, server frame time, client frame time, bandwidth, memory, mesh/bone/effect counts and temporary economy income. Test grouped and scattered players; spawns should not feed only the nearest teammate.

Separate density, arrival cadence, composition, HP and damage adjustments. More enemies should not create invisible contact damage or spawn directly on players. Initial tuning goal is sustained visible pressure with an escape route and useful crowd-clearing moments, not maximum occupancy every frame. Excess shards and XP need full-run economy checks.

Set acceptance budgets before testing on named devices: proposed 60 fps desktop target and at least stable 30 fps on the selected lower-end mobile device, with frame-time percentiles reported. These are goals, not achieved benchmarks. Include full event duration and repeated events to reveal pool/memory leaks. Preserve warnings before decorative effects when reducing cost.

Exit: a recorded squad playthrough and device performance report establish playable pressure; unsupported configurations remain explicitly unverified.

## Phase 11 Regression and release gates

- Asset checks: counts, weights, transforms, normals, UVs/textures, clip closure and fresh import receipts.
- Visual checks: actual imported model under every relevant map's lighting, silhouettes beside ordinary enemies, hands/feet/attachments, complete attack range and contact frames.
- Encounter tests: all five maps; each completion condition; objective destroyed during queued spawn; simultaneous Warden/coffin deaths; last player death; abort/leave; reconnect where supported; stale callbacks; missing assets; no duplicate rewards.
- Intro tests: all five events and bosses, tutorial and Endless routes, multiplayer synchronization, camera interruption and restore.
- Combat regression: waves 9->10->11 and 19->20->Endless; shop/level-up flow; shards, rewards, targeting, existing regular animations, terrain, turrets and weapon hit feedback.
- Abuse tests: forged objective damage, duplicate requests, invalid numbers, stale IDs and client deletion of cosmetic entities. Server outcomes remain unchanged by cosmetic tampering.
- Practice remains nonpersistent. Published asset loading/ownership and real network behavior require their own tests; Studio success alone is not publication verification.
- Record date, Git revision, place ID, test mode, actual client count/device, steps, result, screenshot/video/log evidence and exclusions. Never report edit-time assertions as play tests.

Release only with source/Studio parity, clean relevant output, documented rollback and an explicit list of any remaining unverified release conditions. Commit only task-owned files; preserve concurrent work. Publishing is a separate deployment step.

## Recommended delivery order

1. Baseline and naming audit; model scale lineup; build one shared encounter/intro scaffold.
2. Bloater model, skin, animations, native import/retarget and Pine Valley event end to end.
3. Verify existing swarm changes with actual multiplayer; establish limits before increasing load further.
4. Coffin plus Warden and objective lifecycle: the most different clear condition.
5. DJ crab coordinated encounter and music timing.
6. Alpha hunt, charge timing and pack buffs.
7. Vent/slime event, debris pooling and mobile stress test.
8. Complete all remaining full-boss unique intros and tutorial/Endless entry coverage.
9. Full squad and device regression, polish, synchronized delivery and documented release readiness.

Each stage ends with a playable or reviewable result. Do not finish all sculpting before discovering whether the first rig survives import.

## Technical references

- [Roblox mesh specifications](https://create.roblox.com/docs/art/modeling/specifications): validate rig/mesh requirements, including maximum four bone influences per vertex.
- [Roblox rigging and skinning](https://create.roblox.com/docs/art/modeling/rigging): imported skeletal meshes and Bone representation.
- [Roblox mesh import](https://create.roblox.com/docs/parts/meshes): use the 3D Importer for rigged/skinned content; do not substitute bulk Asset Manager import for that path.
- [Blender smooth and flat shading](https://docs.blender.org/manual/en/4.2/modeling/meshes/editing/face/shading.html): normals affect shading, while bevel geometry changes silhouette. Check installed-version controls when implementing.

## Planning verification

For this plan, repository documentation and current files were inspected and MCP capabilities were discovered. No Blender models, Studio instances, combat code or live place were modified. No Blender export, Studio import, Play test or multiplayer test ran.
