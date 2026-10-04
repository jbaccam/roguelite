# Hammer Brute Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Hammer Brute with a fresh Blender-built skinned boss. He runs on the map-boss runtime with the same moves, adding combos, enrage and follow-up cracks. This follows `plans/2026-10-03-hammer-brute-rebuild-design.md` (the spec).

**Architecture:** There are two independent tracks, run in parallel.
- **Track ART** (Blender, `roguelite-planning/hammer-brute-boss/`): model, rig, paint, then clips, then the game package. It follows the Frost Cyclops pipeline and `plans/BOSS_GAME_PACKAGE_SPEC.md`.
- **Track RUN** (Luau, `studio-prototype/`):
  - `MapBossService`, `MapBossPresentation`, `MapBossDefs` and `BossIntro` learn phases, the forward charge, lockout, intro, the tutorial variant and the roar;
  - a new `BossVfx/Hammer.luau`;
  - every consumer of the old Hammer runtime moves to the map-boss flags.
- **Where they meet:** the names, points and timing schema in "Shared interface" below. Track RUN tests use hand-made timing tables, as `MapBossServiceTests` already does.

**Studio:** nothing is written to Studio without the user's explicit "push it". The FBX import needs the user's one click in the 3D Importer. Read-only `execute_luau` (state checks, loadstring tests that create no instances) is fine.

**Tech stack:**
- Blender 5.2: `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python <script>`;
- numpy, Pillow and OpenCV under system Python 3.12;
- Luau (the Roblox runtime), Rojo 7, and Studio MCP `execute_luau`.

**Git rules:**
- Other sessions share this folder and its index. Stage only your own files: `git add -- <paths>` then `git commit -m "..." -- <paths>`.
- Shared scripts other sessions edit (RogueliteCombat, ShopService, RogueliteMeta, the HUD and others) change through anchored hunks: `studio-prototype/tools/hunks.py`, with a plan file `studio-prototype/combat/bosses/plan_hammer_brute_hunks.py`, staged with `--stage`.
- `git diff --cached --stat` before every commit, then push with `git push origin main` (by name).
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

## Shared interface (both tracks)

| Thing | Value |
| --- | --- |
| Asset folder | `roguelite-planning/hammer-brute-boss/` |
| Anim id (AnimationData `id`, BossAnimations folder, MapBossTiming key) | `hammer-brute` |
| MapBossDefs key / MapConfig boss / AdminConfig id | `Hammer` (unchanged id) |
| Template | `ServerStorage.RogueliteNPCs.Hammer_NPC` |
| Studio FBX | `hammer-brute-boss/exports/game/HammerBrute_Studio.fbx` + `.fbm/` |
| Mesh objects | `HammerBrute_Body`, `HammerBrute_Head`, `HammerBrute_Shirt`, `HammerBrute_Gear`, `HammerBrute_Trousers`, `HammerBrute_Hammer`, `HammerBrute_EyeGlow`. No mesh name equals a bone name. Each is under 20k triangles. |
| Bones (deform) | `Root → HumanoidRootPart → LowerTorso → UpperTorso → Head` (with `Jaw`, `Brow`, `EyelidUpper`); `Belly`, `Shirt_Front_1`, `Shirt_Front_2`, `Shirt_Back`; `{Left,Right}UpperArm → LowerArm → LowerArmTwist → Hand → {Index,Middle,Ring,Pinky,Thumb}1-3` (cyclops finger naming); `{Left,Right}UpperLeg → LowerLeg → Foot → Toes`; `Hammer` under `RightHand` |
| Points | `HammerFace`: bone `Hammer`, at the centre of the striking face (the face that lands flat in Slam). `HammerGrip`: bone `Hammer`, on the shaft axis halfway between the carry grips. |
| Clips | `Idle Walk Hit Death IntroLand Roar Slam Swing Spin SwingSpin SpinSlam ChargeStart ChargeRun ChargeSlam` |
| Attack entries in BossGameData | `Slam Swing Spin SwingSpin SpinSlam ChargeSlam IntroLand`. Each has `duration, warnStart, impact, activeEnd, recoveryEnd, points{HammerFace,HammerGrip}`. Combos also carry `phases: [{warnStart, impact, activeEnd}, ...]` in order. The top-level `impact` is the first phase's impact; the top-level `activeEnd` is the last phase's. |
| Motion | `motion.strideLength` (Walk, studs per cycle), `motion.nominalSpeed` = 20, `motion.chargeStrideLength` (ChargeRun) |
| Ground frame | Root height and ground offset in `BossGameData` (`rootHeight`, `height` ≈ 13.7, `footprintRadius`, `groundOffset`), as for the other four |

---

# Track ART

### Task A1: Model, rig, weights and paint (one subagent, Opus)

**Files:**
- Create in `roguelite-planning/hammer-brute-boss/`:
  - `README.md` and `PROGRESS.md`;
  - `build_hammer_brute.py` (the generator, with `HB_STAGE=probe|model|full`);
  - pure-numpy modules `hb_sdf.py`, `hb_design.py`, `hb_parts.py`, `hb_grip.py`, `hb_weights.py`, `hb_paint.py`, `hb_pose.py` and `hb_camera.py`;
  - bpy helpers `hb_blender.py`;
  - `measure_reference.py`, `solve_camera.py`, `compare_reference.py`, `calibrate.py` and `calibration.json`;
  - `source/` (the reference copied unchanged, `REFERENCE_NOTES.md`, `camera_solution.json`, `grip_solution.json`);
  - `textures/`, `previews/`, `HammerBrute.blend`, `manifest.json` and `polygon-report.json`.
- Modules are copied from `frost-cyclops-boss/fc_*.py` and adapted. Each file is self-contained; nothing imports from or `exec`s the cyclops folder.

**Steps:**
- [ ] **Reference.** Copy `hammer-boss/source/boss-reference.png` to `source/` and record its SHA256 in the README.
- [ ] **Measure.** Run `measure_reference.py` (landmarks, GrabCut mask, region colour probes) and `solve_camera.py` (least-squares camera, scale from the 13.7-stud crown).
- [ ] **Sculpt** with SDF, then voxel remesh and flat-shaded decimation, with every add-on fused through smooth fillets (no bolted-on pieces):
  - **Head:** blocky, with a heavy angular brow. Eyes, scar and wound are painted onto shallow relief; modelled sockets read as sunglasses.
  - **Mouth:** a snarl with modelled broken teeth.
  - **Body:** huge segmented shoulders, upper arms and forearms, and big fists. A round projecting belly with a navel.
  - **Legs:** stocky, ending in block feet.
- [ ] **Clothes**, fitted to the body surface by ray-casting:
  - a torn cream tank top with a ragged hem;
  - suspenders with square iron buckles;
  - a maroon sash;
  - ragged charcoal trousers with holes showing skin.
- [ ] **Hammer:** a beveled iron head with raised square plates, a flat striking face, and a banded wooden haft long enough for the sliding grips. The haft radius must let the fingers close round it.
- [ ] **Rig** with the bones in the Shared interface table:
  - roll aligned so +X rotation of each `LowerArm` and `LowerLeg` is flexion on both sides;
  - IK and pole helpers non-deform and excluded from export.
- [ ] **Grip** (`hb_grip.py`). Solve a real two-handed grip:
  - the haft passes through each finger tunnel, the fingers curl round it at contact distance (−0.03 to +0.02), and the thumb wraps opposite;
  - the wrist is in line with the forearm;
  - `Hammer` is a child of `RightHand`, and the left hand is IK'd to its grip point.
  - Record both carry grips and the attack grip range along the shaft in `grip_solution.json`.
- [ ] **Weights.** At most 4 influences per vertex, normalised. Clothes and buckles are rigid to their bones, the trousers follow the legs, and the shirt follows the skin with its hem on the `Shirt_*` bones. The forearm skin is split across `LowerArm` and `LowerArmTwist`.
- [ ] **Paint** (`hb_paint.py`) from baked passes (position, normal, AO, bevel edge, facet random, material id) into 2048 masters plus 1024 delivery maps.
  - **Skin:** mottled green with dark speckles and red wound patches.
  - **Values:** 2–4 per material, broad patches, no micro-noise.
  - **Glow:** eyes on the `EyeGlow` mesh (white, Neon in Studio).
  - **Colour:** comes from eyedropped values times the `CALIBRATION` gains.
- [ ] **Compare.** Run the `PROBE_ONLY` loop: `compare_reference.py`, with silhouette IoU ≥ 0.92 as the target and region colours within about 10%, then `calibrate.py`. At most 3 compare passes. Record anything that misses its target in the README.
- [ ] **Preview renders** (the small set only):
  - `Reference_Match.png` and `Comparison_SideBySide.png`;
  - `Turnaround.png` (front, ¾, side and back);
  - `Face_Closeup.png`;
  - `Grip_Closeup.png` (both hands, two angles);
  - `Rig_Bones.png`;
  - `RigTest_ROM.png`: overhead slam pose, full spin wind-up, charge crouch, deep squat, arms forward, twist, death kneel, fists open and closed.
- [ ] **Polygon report:** every mesh under 20k triangles.
- [ ] **Commit and push.** Commit the scripts, README, small JSONs and the 1024 textures. The `.blend` goes through LFS. `previews/` is gitignored. `git add -- hammer-brute-boss && git commit -m "Hammer Brute: model, rig, grip and paint" -- hammer-brute-boss`.

**Acceptance:**
- The generator runs end to end headless.
- The ROM sheet shows no collapsed elbows, knees or shoulders and no candy-wrapper wrists.
- Both hands genuinely grip the haft.
- Every mesh name differs from every bone name.

### Task A2: Motion library and the 14 clips (one subagent, Opus, after A1 is reviewed)

**Files:**
- Create `hb_motion.py`: IK, hinge solver, two-hand shaft constraint, foot planting, the easing and overlap helpers, and secondary bones.
- Create `hb_clips.py`: one function per clip, returning keyed poses.
- Create `hb_checks.py`: every check below, on the evaluated rig.
- Create `MotionChecks.json`.
- Modify `build_hammer_brute.py` to add `HB_STAGE=motion`.

**Clip targets** (24 fps; an attack may use 30 fps only if the 120 Hz grip check fails at 24, and the README says which):

| Clip | Length | Loop | Times / notes |
| --- | --- | --- | --- |
| Idle | 3.0 | yes | Breathing, weight shift, one blink. The belly and shirt lag. Frame 0 is the shared start pose for every attack. |
| Walk | about 0.65 cycle | yes | A lumbering stomping run at 20 studs/s, stride about 13 studs. The hammer is carried low. Feet planted with IK: drift ≤ 0.01 per frame. |
| Hit | 0.45 | no | Returns to Idle frame 0. |
| Death | about 2.5 | no | The hammer slips and thuds down, he drops to his knees, then collapses. Nothing is more than 0.05 below the ground. |
| IntroLand | about 3.0 | no | 0–0.65 airborne (hammer overhead, legs tucked). At 0.65 the feet and the hammer land together; then crouch, rise, a roar from about 1.4 to 2.4, and back to idle. impact = 0.65. |
| Roar | 1.2 | no | Chest out, arms wide with the hammer, jaw open. |
| Slam | about 1.45 | no | Hold the anticipation 2–3 frames with the hammer overhead, then a fast eased-in drop. The flat face lands; impact 0.70. The body compresses, the hammer bounces, then recovery with overlap. |
| Swing | about 1.35 | no | Loads onto the right shoulder, then a level 180° sweep; active 0.50–0.70. |
| Spin | about 1.6 | no | A 360° whirl, with the feet pivoting and the hammer level; active 0.50–0.95. |
| SwingSpin | about 1.9 | no | The Swing's follow-through becomes the Spin's wind-up. Phases 0.50–0.70 and 0.80–1.25. |
| SpinSlam | about 2.1 | no | The Spin unwinds up into the overhead; then the Slam. Phases 0.50–0.95 and impact 1.35. |
| ChargeStart | 0.5 | no | Loads into a hunched sprint. The last frame equals ChargeRun frame 0. |
| ChargeRun | about 0.53 | yes | A sprint whose stride matches speed 32. Record `chargeStrideLength`. |
| ChargeSlam | about 1.2 | no | Starts on ChargeRun frame 0, brakes into an overhead slam; impact 0.40; ends on Idle frame 0. |

**Steps:**
- [ ] Write `hb_motion.py`:
  - a two-bone IK with a fixed hinge axis;
  - a shaft constraint (the left palm stays on the haft axis at its grip parameter);
  - a planted-foot lock;
  - ease, overshoot and settle curves;
  - lagged secondary bones.
- [ ] Author all 14 clips in `hb_clips.py`.
- [ ] Write `hb_checks.py` covering every authored frame of every clip:
  - **Elbows and knees:** one hinge axis (≤ 2° off-axis). Elbow 0–140°; knees bend forward only, 0–150°.
  - **Wrists:** flex and extension ≤ 35°, side bend ≤ 25°.
  - **Spikes:** no shoulder or spine step over 20° per frame, and spine twist ≤ 45°.
  - **Grip:** both palms within 0.05 of the shaft surface.
  - **Hammer vs body:** BVH overlap, and no vertex inside except the hands.
  - **Body vs body:** forearm vs upper arm, belly and chest, and thigh vs belly. Slight overlap is allowed; a pass-through fails.
  - **Feet:** planted drift ≤ 0.01, and nothing more than 0.05 below the ground.
  - **Clip ends:** loops close, and attacks start and end on Idle frame 0.
- [ ] Add a client-blend check. Resample every clip at 120 Hz with a per-bone *local* matrix lerp (translation lerp plus rotation slerp; this matches `EnemyMotion.sample` `CFrame:Lerp`), and do the same for the 0.12 s blends Idle→attack, Walk→attack and attack→Idle. Rerun the grip (≤ 0.08), hammer-in-body and hinge checks. If the grip check fails at 24 fps for a clip, raise that clip to 30 fps.
- [ ] Renders:
  - `AttackCheck_<Clip>.png`: wind-up, impact and recovery, front ¾ and a grip close-up, for every attack and combo;
  - `<Clip>.mp4`: Workbench, ¾ plus side view, normal speed then half speed, one per clip.
- [ ] Commit: `git commit -m "Hammer Brute: 14 clips and motion checks" -- hammer-brute-boss`.

**Acceptance:** `MotionChecks.json` passes every check. The videos read as heavy, fast and fluid, with no pops.

### Task A3: Game package (after A2)

**Files:**
- Create `build_game_package.py`, adapted from `frost-cyclops-boss/build_game_package.py`.
- Create `snap_game_timings.py` and `validate_exports.py`.
- Outputs go to `exports/game/`.

**Steps:**
- [ ] Write `exports/game/AnimationData.json`, exactly the BOSS_GAME_PACKAGE_SPEC schema. Clips may carry `"fps": 30`, which `EnemyMotion` reads as `clip.fps`.
- [ ] Write `exports/game/BossGameData.json` with the attack entries and `phases` from the Shared interface. Times snap to whole frames, and `impact` is the frame the face actually touches down or the sweep starts.
- [ ] Export `exports/game/HammerBrute_Studio.fbx` plus `.fbm/`: `axis_forward='-Z', axis_up='Y', add_leaf_bones=False, use_armature_deform_only=True, bake_anim=False, mesh_smooth_type='OFF', path_mode='COPY', embed_textures=True`. Materials are named `HammerBrute_<Section>`.
- [ ] Write `validate_exports.py`. It reimports the FBX fresh and checks:
  - mesh counts under 20k triangles each;
  - bone names equal those in `AnimationData.json`;
  - no mesh name equals a bone name;
  - textures load;
  - per-vertex positions of the reimported rig, posed with AnimationData frames (with 4-influence truncation), match the `.blend` within 0.01 studs;
  - frame counts are right, there are no NaNs, and loops close.
- [ ] Render `previews/GameClips.png` (4–6 frames per clip).
- [ ] Update the README with a "Game package" section, phrased as "Verified in Blender; Studio untested".
- [ ] Commit `hammer-brute-boss/exports/game/*` (json, fbx, fbm) and the scripts.

---

# Track RUN

All work happens in `roguelite-planning/studio-prototype/`. Tests go in `combat/bosses/MapBossServiceTests.luau`, which already uses hand-made timing tables and only `M._shapes` in Edit. New pure logic goes into `X` (`M._shapes`), so it is testable the same way. Tests run read-only in Studio Edit through `execute_luau`, using `tools/FreshRequire.luau` or loadstring from the dev server (`tools/dev_server.py`, 127.0.0.1:8934). No instances are created and nothing is written.

### Task R1: Multi-phase attacks (`def.phases`)

**Files:** modify `combat/bosses/MapBossService.luau`, `combat/bosses/MapBossDefs.luau` (the `timing()` scaling of `at.phases[i]` times) and `combat/bosses/MapBossServiceTests.luau`.

- [ ] **Failing tests** with a hand-made `SwingSpin` timing (`phases={{warnStart=0,impact=.5,activeEnd=.7},{warnStart=0,impact=.8,activeEnd=1.25}}`, samples for `HammerFace` and `HammerGrip`):
  - `X.phaseWindows(def,at)` returns two windows with the scaled times;
  - phase 1 builds a sweep arc;
  - phase 2 builds a full ring;
  - a player hit in phase 1 can still be hit in phase 2;
  - but only once per phase.
- [ ] Implement:
  - `A.phases`, a list of `{def=merged(attackDef,phaseDef), at=phaseTiming, hits={}, fired=false}`;
  - `stepAttack` loops the phases with the existing per-shape code, each phase with its own `hits`;
  - `A.data.phases` is a list of `{shape=encoded, warnStart, impact, activeEnd}`;
  - `follow` per phase;
  - `MapBossDefs.timing` divides phase times by `rate`.
- [ ] Run the tests (all PASS) and commit.

### Task R2: Forward charge lane with `contact`, `finish` and `lockout`

**Files:** `MapBossService.luau` and `MapBossServiceTests.luau`.

- [ ] **Failing tests:**
  - `facing='forward'`: the lane direction equals the flat direction to the target, and the root faces along it.
  - `X.contactLength(def,cf,dir,targetPos,wallLength)`: with the target 40 studs down the lane and `contact=4`, it returns 36. With the target 2 studs off the lane centre, it still tracks. With the target outside `width/2`, it keeps the previous length. It is capped by `length` and the wall.
  - `finish`: the circle centre is `HammerFace` at the end clip's impact, measured from the root at the end of travel.
  - `lockout`: the order walk skips `Charge` within 5 s of its last start.
- [ ] Implement:
  - `def.facing`;
  - `def.contact`: recompute the length each step while the target is in the lane, never below the distance already travelled, and republish `A.data.length` (the client re-times ChargeSlam);
  - `def.finish`: timing `rs + length/speed + T.attacks[endClip].impact`, using the circle hit and `queueFollow`;
  - `s.lastStart[kind]` for `def.lockout`.
- [ ] Run the tests and commit.

### Task R3: Intro, tutorial variant, roar, enrage order, full ring and circle height

**Files:** `MapBossService.luau`, `MapBossShapes.luau` (circle `height`; check `S.contains` line 18 first, since a height band is mentioned in its header), `MapBossDefs.luau`, `bosses/BossEncounter.server.luau`, `RogueliteZombieChase.server.luau` (the Hammer admin-spawn branch at about line 705 goes through `MapBossService.practice`/`spawn`) and the tests.

- [ ] **Failing tests:**
  - **Sweep arc:** turning ≥ 2π gives `from=-π, to=π` (a full ring).
  - **Circle height:** a circle with `height=6` rejects a point 7 above and accepts one 5 above.
  - **Tutorial:** `X.orderFor(s)` returns `def.tutorial.order` when `s.tutorial`, otherwise `enrage.order` when `s.enraged` and present, otherwise `def.order`.
  - **Roar:** `X.roarDue(s)` is true once after enrage, when no attack is running.
- [ ] Implement:
  - `M.spawn(id,cf,practice,opts)`. With `opts.intro` and `def.intro`, set the same attributes `BossService` sets today: `BossIntroStart`, `BossIntroLand`, `BossIntroUntil`, `combat.CinematicUntil`, `BossAttack='IntroLand'`, `BossStart=land - T.attacks.IntroLand.impact`, `BossFrame`, `BossGroundY`, `BossSerial`, `Attacking`. Anchor the root and hold until done. `s.next=done+.6`.
  - Fixed HP: `TutorialBossHealth` when not practice, which sets `s.tutorial=true`.
  - The roar as an anchored pseudo-attack with no hit shape; `BossAttack='Roar'`, duration `T.clips.Roar`.
  - `BossEncounter` passes `{intro=true}` for wave bosses and drops its `'Hammer'` branch.
  - `RogueliteZombieChase` routes 'Hammer' like the other map-boss ids.
- [ ] Run the tests and commit.

### Task R4: Presentation and intro client

**Files:** `combat/bosses/MapBossPresentation.client.luau` and `combat/BossIntro.client.luau`.

- [ ] Phases: draw each phase's warning at commit. A later phase starts at 35% alpha and fills to full at its `impact − 0.35 s`.
- [ ] Charge: read `data.length` updates (BossAttack data republish) and re-time ChargeRun→ChargeSlam. ChargeRun cadence follows ground distance, `chargeStrideLength`.
- [ ] Play the `IntroLand` clip timed by `BossStart`, as BossService did with Slam. Play the `Roar` clip when `BossAttack=='Roar'`.
- [ ] Walk playback rate: actual speed ÷ `nominalSpeed` (check what the client already does and keep it consistent with `strideLength`).
- [ ] `BossIntro.client`: watch the `MapBoss` tag as well as `HammerBoss`; run only when `BossIntroStart` is set. The card name is `NAMES[npc.Name]` or `npc:GetAttribute('BossIntroName')` or `string.upper(BossName)`. MapBossService sets `BossIntroName` from `def.introName = 'HAMMER ZOMBIE BOSS'`.
- [ ] Compile check (read-only loadstring compile in Studio), then commit.

### Task R5: `BossVfx/Hammer.luau` and the EarthCracks texture

**Files:**
- Create `combat/bosses/BossVfx/Hammer.luau`, following the pattern of `BossVfx/FrostCyclops.luau` (hooks `windup`, `impact`, `active`, `enrage`, `intro`, `follow`).
- Modify `boss-vfx-kit/paint_textures.py` to add `EarthCracks.png` (white-on-clear, painterly, tinted in game).
- Modify `combat/bosses/BossVfxAssets.luau` to register the new texture name (its asset id is filled in at upload time; until then `C.texture` returns nil and the effect skips the decal).

**Effects:**
- **Slam / phase circle:** `C.ring` ShockwaveRing plus a DustPuff flipbook, `C.star`, an EarthCracks `C.decal` for 2.5 s, and `C.shake` with strength by distance.
- **Sweeps:** Neon-segment crescents following the `HammerFace` samples.
- **Charge:** run dust every stride and a skid streak at the stop.
- **Follow-up cracks:** a crack decal that grows during the delay, then a dirt burst.
- **Enrage:** EyeGlow tinted red (`C.setGlow`), a roar ring and steam puffs.
- **Intro:** a landing ring and shake.
- **Sounds:** the existing kit, pitch-shifted (`impact_explosion_03` and the others the map bosses use).

- [ ] Commit.

### Task R6: Defs entry and the build pipeline

**Files:**
- `combat/bosses/MapBossDefs.luau`:
  - add `D.Hammer` exactly as in spec §4 (with `CRACKS`), `introName`, and `ATTACK_CLIPS['hammer-brute']`;
  - `D.Order` gains `'Hammer'` first.
- `combat/bosses/build_boss_modules.py`: `FOLDERS['hammer-brute']='hammer-brute-boss'`; `ATTACKS['hammer-brute']`; `phases` passed through into MapBossTiming; `chargeStrideLength` passed through.
- `combat/bosses/InstallMapBossTemplates.luau`: add `Hammer = "hammer-brute-boss/exports/game/HammerBrute_Studio.fbx"`. The Hammer mesh is excluded from the body shell (see R7).

- [ ] Commit.

### Task R7: Consumers and retiring the old runtime

**Files:** these scripts change through `combat/bosses/plan_hammer_brute_hunks.py` (tools/hunks.py) where another session also edits them:
- `RogueliteCombat.server.luau` (the `shelled` function and `hammer` branches at about lines 162, 179 and 428: the map-boss path, with the `Hammer` section left out of the shell);
- `LegendaryMoves.luau`, `RogueliteMeta.server.luau`, `ShardDropService.luau`, `ShopService.luau`, `ZombieDeath.luau` and `RunAnalytics.luau`;
- `RogueliteZombieAnimation.client.luau`, `ui/RogueliteHUD.client.luau` and `ui/TutorialGuide.client.luau`;
- `MapConfigTests.luau`, `AdminConfigTests.luau` and `EnemyTests.luau`;
- `combat/default.project.json`: remove the BossData, BossMotion, BossPresentation, BossService and HammerBoss_NPC entries.

- [ ] Every `IsHammerBoss` check is either removed (where `IsMapBoss`/`IsBoss` is already checked) or replaced. `HammerBoss` tag watchers watch `MapBoss`.
- [ ] Old files stay on disk in `hammer-boss/` as history. They leave the project only.
- [ ] Run `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx` (from the repo root). Expected: success.
- [ ] Grep check: `grep -rn "IsHammerBoss\|BossMotion\|'HammerBoss'" studio-prototype --include=*.luau` finds only comments and history, none in live code paths.
- [ ] Commit through `plan_hammer_brute_hunks.py --stage` for the shared files, plus `git add` for whole files this plan owns.

### Studio record (2026-10-03)

- **Runtime pushed at ad37f52** (R1-R7 and both review rounds), in one guarded write. Record: `studio-prototype/combat/bosses/hammer-brute-runtime-sync-2026-10-03.json`.
  - Whole files written as HEAD: MapBossShapes, MapBossDefs, BossVfxAssets, BossVfx/Common, BossEncounter, MapBossService and MapBossPresentation. BossVfx/Hammer was created, unsandboxed like the other BossVfx modules.
  - Our hunks went onto Studio's own text: RogueliteZombieChase, RogueliteCombat, HandymanTurretService, PetService, TutorialGuide and BossIntro.
- **The Hammer is still the old one in Studio** (`MapBossDefs.legacy('Hammer') == true`). Studio has no hammer-brute timing, BossAnimations or `Hammer_NPC` yet. The four other bosses are ready.
- **Checked in Edit:** the three boss suites against Studio's own module sources (47, 26 and 16 PASS, 0 FAIL). No Play test has run.

### Task R8: Studio sync package (prepared, not run)

**Files:** extend `combat/bosses/SyncMapBossRuntime.luau` for Hammer. Add `combat/bosses/HAMMER_BRUTE_INSTALL.md` with the exact order:
1. The user imports `HammerBrute_Studio.fbx` into `ServerStorage.MapBossRawImports` with "Keep Zero Influence Bones" ticked.
2. `DumpBossReceipt` → `receipts/hammer-brute-receipt.json`.
3. `python retarget_boss.py hammer-brute-boss hammer-brute`.
4. `python build_boss_modules.py hammer-brute`.
5. Guarded MCP push of the runtime modules, hunks and BossAnimations (Studio Source must equal the committed base; write all or none).
6. `InstallMapBossTemplates` (Hammer only), which backs up the old `HammerBoss_NPC` and modules to `ServerStorage.BeforeHammerBrute_20261003`.
7. Edit-mode tests and a plain screen capture of the template, captured twice.
8. The user play-tests.

- [ ] Commit.

### Task R9: the original model on the map-boss runtime (2026-10-04)

R8 is replaced: no FBX import. The Hammer keeps the 16-part Motor6D template `HammerBoss_NPC`, and his clips are re-authored in `hammer-boss-moves/` (design doc, "Change of plan").

**Done in the repo (R9, 8e838ed, plus the review fixes):**
- `combat/bosses/DumpMotorReceipt.luau`: a read-only Studio dump of a Motor6D template, for `receipts/hammer-old-receipt.json`.
  - **Not run yet.** Studio stayed in Play through R9, so the receipt doesn't exist.
  - Until it does, the converter tests use a receipt made from `hammer-boss/finished/studio-asset-manifest.json`. In that receipt the joints are `Boss_<Part>`, which is the name `EnemyMotion.bind` gives them.
- `combat/bosses/partposes_to_motor6d.py` (tests: `test_partposes_to_motor6d.py`):
  - It reads `PartPoses.json` and writes `StudioAnimationData.json` (rigType Motor6D, `T = C0⁻¹·P0⁻¹·P1·C1` per joint) and `AnimationData.json` (one bone per part under Root at the root height, in the build's basis).
  - BossGameData point offsets are in the part's own Studio space.
  - The receipt's model scale must be 1.0.
  - A supplied rotation may be off a true rotation by 2e-6 at most.
  - Every frame is rebuilt within 1e-4 studs of the poses as supplied (on the legacy clips: 4.6e-6), and nothing is written unless all of it passes.
- `build_boss_modules.py`: `FOLDERS['hammer-brute']='hammer-boss-moves'`.
  - It converts `PartPoses.json` in memory and writes the derived files with the rest of its output.
  - A plain run skips hammer-brute while the receipt or the clips are incomplete. Naming it (`python build_boss_modules.py hammer-brute`) stops the run instead.
  - The other four bosses stay byte-identical.
- `MapBossDefs`: `D.Hammer.scale=1.15` (the old `BossMotion.SCALE`). The client scales the Transforms' translations by `GetScale()/EnemyBaselineModelScale` (1.15/1), the same factor `ScaleTo` gives C0/C1.
- `InstallMapBossTemplates`: `Hammer_NPC` is a copy of `HammerBoss_NPC` (`COPY`), which stays in place for the legacy runtime.
  - The meshes, textures and SurfaceAppearances are kept as they are.
  - The legacy attributes are removed and the map-boss attributes added.
  - Two Neon `HammerBrute_EyeGlow` plates are welded to the Head.
  - An existing `Hammer_NPC` goes to a new `BeforeMapBoss_<yyyymmdd_hhmmss>` folder each run.
- `plan_hammer_brute_hunks.py` R9: the shell in RogueliteCombat, HandymanTurretService and PetService skips the `Hammer` part and the hands for `MapBossId=='Hammer'` too.
  - The turret and pet loops read `MapBossId` once per enemy.
  - `--from-r7` is the list for Studio's text.
- `BossService.practice`: Spawn boss goes to `MapBossService.practice(player,'Hammer')` once `MapBossDefs.ready('Hammer')`.
  - If that throws, the half-built boss is removed and the status shows the error. The old Hammer spawns instead.
  - Remove boss removes either Hammer.

**Still to do in Studio (Edit only):**
1. Dump the receipt with `DumpMotorReceipt.luau`, rerun the tests on it, and compare it with `studio-asset-manifest.json`.
2. Run the Studio compile checks and the three boss suites.
3. Do the guarded push of MapBossDefs, BossService and the three shell hunks.
4. Check that `legacy('Hammer')` is still true.

**Final install, once the clips land (gate still closed until step 4):**
1. **Package** in `hammer-boss-moves/exports/game/`:
   - `PartPoses.json`: all 14 clips and all 16 parts per frame.
   - `BossGameData.json`, containing:
     - `attacks` with the §3 timings and `phases`; `HammerFace`/`HammerGrip` as `{"bone":"Hammer","offset":[Studio Hammer-part space]}` plus `rootAtImpactStudio` (the build warns past 0.25 studs);
     - `height`, `footprintRadius` and `bodyCentreHeight` = 4.45 (authored scale);
     - `motion` {`strideLength`, `nominalSpeed`, `chargeStrideLength`}.
2. **Build:** run `python build_boss_modules.py hammer-brute`, then both Python test files.
3. **Guarded push** of `MapBossTiming` and the new `BossAnimations/hammer-brute` modules, made unsandboxed like the other bosses' animation folders.
4. **Template:** `ONLY={'Hammer'}` plus `InstallMapBossTemplates` in Edit. This opens the gate: check `ready('Hammer')==true`.
5. **Checks:** the three boss suites, then a plain capture of `Hammer_NPC`.
6. **Play-test:** the user play-tests: the wave-20 sky drop, the tutorial, the Spawn boss button, and enrage turning the eyes red.

---

# Final

- [ ] **Self-check against the spec**, section by section.
- [ ] **Report to the user** what was verified (Blender checks, tests, Rojo build) and what was not (Studio import, Play).
- [ ] **Ask for the import click and "push it"** to finish.
