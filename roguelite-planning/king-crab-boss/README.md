# Giant King Crab — Beach Cove boss

A Blender rebuild of the supplied king-crab reference: textured, skinned to a
52-bone animation-ready skeleton, and exported as FBX and GLB. Everything is
authored at final size (1 Blender unit = 1 Roblox stud). The game clips,
timing data and the Studio import FBX are described under
[Game package](#game-package). Nothing is installed in Studio.

The claws deliberately differ from the reference. On the user's instruction,
both claws were re-oriented from the reference's upright, shield-like carry
into an animation-friendly guard: the pincers point forward, inward and down,
about 45° off vertical. The rest of the crab follows the reference.

## Files

| Path | What |
| --- | --- |
| `build_king_crab.py` | The whole generator (Blender 5.2, headless). Self-contained; reads only `source/camera.json` and the reference. |
| `animate_game.py` | Authors the game clips and writes the game package (`exports/game/`); see **Game package**. |
| `solve_camera.py` | Solves the reference camera from landmark pixels and writes `source/camera.json` (system python + numpy). |
| `make_reference_mask.py` | Builds `source/reference_mask.png` (system python + OpenCV). |
| `compare_reference.py` | Side-by-side, overlay, silhouette IoU, region IoUs, colour probes and crops (system python). |
| `calibrate.py` | Folds the colour-probe ratios into the generator's `CALIBRATION` table. |
| `label_sheets.py` | Adds labels to the contact sheets. |
| `validate_exports.py` | Re-imports the FBX and GLB exports and the game package fresh and checks them; writes `validation-report.json`. |
| `KingCrab.blend` | Rig, 5 skinned sections, packed textures, the actions below, and a `REVIEW_ONLY` collection (camera, lights, ground) that is excluded from export. |
| `exports/fbx/KingCrab.fbx` | Rest mesh, armature and embedded 1024 textures. |
| `exports/fbx/KingCrab_ReferencePose.fbx`, `KingCrab_RigTest_ROM.fbx` | Armature-only clips. |
| `exports/glb/KingCrab.glb` | Meshes, skin, textures, plus the actions `ReferencePose`, `RigTest_ROM` and `ClawAttack_Check`. |
| `exports/game/` | The game package: `AnimationData.json`, `BossGameData.json`, `GameChecks.json`, `KingCrab_Studio.fbx` and `KingCrab_Studio.fbm/`. |
| `textures/KingCrab_<Section>_BaseColor_2048.png` | Master base-colour maps, one per section. |
| `textures/KingCrab_<Section>_BaseColor_1024.png` | Roblox delivery maps (Roblox caps uploads at 1024). |
| `source/` | The unchanged reference, `REFERENCE_NOTES.md` (inventory, colours, landmarks), `camera.json`, the mask and its review image. |
| `previews/` | Real Blender renders and comparisons (below). |
| `manifest.json` | Measured dimensions, bones and parents, sections, triangle counts, texture hashes, calibration, lighting, and recorded pose samples. |
| `polygon-report.json`, `validation-report.json`, `attack-check.json` | Reports. |

Previews:
- `Reference_Match.png`: the posed, skinned, baked rig at the reference framing, 1536 × 1024.
- `Comparison_SideBySide.png`, `Comparison_Overlay.png`, `Comparison_Silhouette.png`, and crops `Crop_*.png` (eyes/brows, mouth, both claws, both leg groups, rim spikes).
- `Turnaround.png`: front, three-quarter, side, back and top, rest pose.
- `Face_Closeup.png`, `Rig_Bones.png`, `RigTest_ROM.png`, `RigTest_Joints.png`.
- `AttackCheck_Claws.png`: rest guard, windup, impact, pincer open and snapped shut, from the front, three-quarter and a crusher close-up.
- `GameClips.png`, `ClawCrush.mp4`, `Rush.mp4`, `BubbleBarrage.mp4`: game clips (see below).

## Rebuilding

```
python solve_camera.py                 # only if landmarks change -> source/camera.json
python make_reference_mask.py          # only if the mask changes
blender -b --factory-startup --python build_king_crab.py        # ~2.5 min on the RTX 2070
blender -b --factory-startup --python animate_game.py           # game clips + package, ~30 s
python label_sheets.py
python compare_reference.py previews/Reference_Match.png _work/final_mask.png
blender -b --factory-startup --python validate_exports.py
```

The build has three modes:
- `KC_MODE=probe`: renders the unbaked posed rig, its mask, an ID pass and a clay pass in about 10 s.
- `KC_STOP_AFTER_MATCH=1`: bakes and stops after `Reference_Match`.
- `KC_ATTACK_ONLY=1`: bakes and renders the attack check.

`build_king_crab.py` rewrites `KingCrab.blend` without the game clips, so
re-run `animate_game.py` after it.

Colour loop: `python calibrate.py <compare-report.json>`, then rebuild.
`_work/` holds intermediates and is deleted after delivery. Re-running
`compare_reference.py` or `label_sheets.py` needs a fresh build first.

## Provenance

The reference is the user's own image, supplied in this session and preserved
unchanged as `source/king-crab-reference.webp`, SHA256
`575CB191413641ADF4A03A39C19750BEDF81F21E1B5873E85A56B23E18A7C261`.

No reference pixels are used in any texture or render. The reference
contributed only four kinds of data: eyedropped colours, measured landmark
positions, traced outlines (back-projected into 3D through the solved camera),
and wear-chip positions. All geometry is procedural, and every texture is
baked from procedural shaders written here. No Creator Store or external
models were used.

## How it was measured

`solve_camera.py` fits the camera to symmetric landmark pairs by least
squares. The result: 44.5 mm lens (1900 px), camera at (−5.68, −30.67, 5.78)
studs, yaw 10.1°, pitch −2.2°. It also found the body leaning 5.86° with its
right side up, and fitted 1.69 px RMS. Absolute scale comes from the brief:
the tall-spike tips sit 10 studs above the ground.

Every other dimension follows from the reference through that camera.
Outlines, joints and leg tips are back-projected from pixels, and the walking
legs are least-squares fitted to the traced knee, ankle and tip pixels. The
fit shares lengths between each L/R pair, so the skeleton is exactly
mirror-symmetric. Full details are in `source/REFERENCE_NOTES.md`.

| Measure (studs) | ReferencePose | Rest pose |
| --- | --- | --- |
| Top of the tall spikes | 10.16 | 10.09 |
| Carapace width × length | 11.96 × 10.28 | 12.03 × 10.28 |
| Claw-to-claw span (x) | 17.88 | 17.79 |
| Leg span (x) | 16.22 | 16.80 |
| Crusher claw bounds (x, y, z) | 6.68 × 8.29 × 6.18 | 6.63 × 8.26 × 6.29 |
| Cutter claw bounds | 5.00 × 6.50 × 4.79 | 5.15 × 6.39 × 5.22 |
| Eye radius R / L | 0.475 / 0.435 (the reference draws them unequal) | |

The brief suggested a claw-to-claw span of about 24 studs. The reference's
own proportions, at a 10-stud spike height, give about 19 studs in its pose,
and 17.9 after the guard re-pose. The generator follows the reference. If the
arena needs a wider threat, lengthen the claw arm bones: the geometry is
authored per chela and scales cleanly.

## Colour: measured, not eyeballed

`compare_reference.py` samples each material in a box that picks it out
independently in the reference and in the render, using a colour rule and
the figure mask. It compares linear-light means. `calibrate.py` multiplies
each ratio into that section's `CALIBRATION` gain. Final agreement, as sRGB
of the linear mean (target within 8% per channel):

| Probe | Reference | Render | Worst channel |
| --- | --- | --- | --- |
| Carapace top (red_Body) | 229, 95, 71 | 228, 95, 71 | 1.7% |
| Crusher shell (red_ClawR) | 181, 71, 58 | 181, 71, 58 | 0.3% |
| Cutter shell (red_ClawL) | 200, 81, 64 | 200, 81, 64 | 0.3% |
| Leg shell (red_Legs) | 169, 69, 52 | 171, 71, 53 | 4.4% |
| Teeth / mouth plates (beige_Body) | 211, 164, 119 | 211, 164, 119 | 0.2% |
| Sternum (beige_Belly) | 152, 112, 76 | 151, 112, 76 | 0.2% |
| Crusher fingers (beige_ClawR) | 218, 180, 142 | 218, 180, 142 | 0.2% |
| Cutter fingers (beige_ClawL) | 200, 159, 124 | 201, 159, 124 | 0.5% |
| Leg tips (beige_Legs) | 194, 153, 115 | 194, 153, 115 | 0.4% |
| Eye whites | 245, 218, 186 | 245, 218, 186 | 0.7% |

The probes match means. They do not prove the pattern matches.

Two claw probes need caveats because the claws no longer sit where the
reference's are. The crusher and cutter shell probes compare whatever claw
surface falls in the reference claw's box. The two leg probe boxes were
narrowed so they no longer take in the re-posed cutter and its cast shadow,
which now hangs in front of the crab's front-left leg.

Lighting in the review scene: a high sun from behind the camera (elevation
70°), a sky fill split from the visible backdrop, and a weak warm fill, all
rendered with the Standard view transform. The reference's cast shadows fall
back-left; the render's fall back-right. A separate lighting study
(percentile spreads per region) chose this setup for colour and value
agreement over a literal shadow direction.

## Silhouette

| Region | IoU vs `source/reference_mask.png` |
| --- | --- |
| Whole figure | 0.797 |
| Excluding the crusher's region | 0.827 |
| Excluding both claw regions | 0.913 |

Before the claw re-pose, the whole figure reached 0.927 (pass 6) and 0.922
on the baked rig (pass 15). The drop is the approved claw change. The
remaining non-claw misses are the leg-join details and the far-side legs,
which the reference draws slimmer than perspective explains.

## Construction

- **Carapace**: a steep-fronted convex hull, planar-dissolved into broad hewn
  facets, plus 5 pyramidal spikes. The reference shows the top as a big lit
  plane even though the camera sits below it. That only works if the top
  slopes down toward the face at about 25°, so it is built that way.
- **Face**: blocky hockey-stick brows (own bones), and white eyes whose pupils
  are painted about each Eye bone's forward axis. Stalks have a red collar
  and a beige cup, set in dark pits. Two shield-shaped maxilliped plates have
  their own bones, flanked by trapezoid plates with the red paint running
  over their tops.
- **Sternum**: three arcs of chamfered beige plates, concentric with the
  mouth, wrapped onto a bowl.
- **Claws**: `build_chela()` authors each claw in a local frame: F forward,
  U toward the dactyl, and S the finger hinge axis.
  - The crusher is a thick club-like palm hull. Its red fixed finger has a
    beige bite edge, and its big beige movable finger closes onto it.
  - The cutter has a slimmer palm and serrated fingers.
  - Both arms have beige bands at the elbow and wrist.
  - The movable finger's bone sits on the hinge with local X = S, so opening
    and closing is a single-axis rotation. It closes onto the fixed finger
    without passing through (BVH bisection: 0.9° / 6.2° more closure would
    touch).
- **Legs**: 4 per side, each 4 rigid segments. Beige coxa rings and knee
  bands hide the joints; flat outer faces keep the facets readable.
- **Paint**: procedural, driven by rest-space attributes (`restP`, `restN`,
  per-face `facet`), so the posed render and the rest-pose bake agree.
  - Cellular painterly patches in crimson, maroon and orange, with up-facing
    planes leaning orange.
  - Small darker dabs, per-facet tone shifts and a cavity shade.
  - Worn cream chips from a convex-edge mask, broken by ragged noise, plus
    chips placed where the reference shows them (ray-cast from measured
    pixels) and chips on both claw faces. Each chip has a thin darker rim.
- **Bake**: EMIT bake at 96 spp into 2048 masters with a 16 px extend margin
  (8 px at 1024), then downscaled 1024 delivery maps. Soft bevels are
  2-segment on the chunky shells.

## Rig

`KingCrab_Rig` sits at the origin on the ground, faces −Y with Z up, and has
**52 deform bones and no leaf bones**:

```
Root
└ Body
  ├ Brow_R, Brow_L
  ├ EyeStalk_R → Eye_R,  EyeStalk_L → Eye_L
  ├ Maxilliped_R, Maxilliped_L
  ├ Claw_R_Coxa → _Merus → _Carpus → _Propodus → _Dactyl      (same for Claw_L)
  └ Leg_{L,R}{1..4}_Coxa → _Merus → _Carpus → _Dactyl         (8 legs)
```

Bone rolls are mirror-consistent (L/R hinge axes are mirrored, which is what
Blender's pose-flip expects). Every exoskeleton piece is weighted 100% to one
bone, and joints hide behind overlapping cuffs and bands.

Rest pose: level body, a symmetric planted stance (the averaged reference leg
poses, re-solved so the tips sit on the sand), and the claws in guard, 14°
more relaxed than ReferencePose.

Actions:
- `ReferencePose` (2-frame hold): body rolled 5.86°, legs on the traced
  contacts, eyes aimed, fingers 8° open.
- `RigTest_ROM` (144 frames, 24 fps): body bob and tilt, tripod stepping on
  all 8 legs, both claws swinging with their hands pitching and opening, eye
  stalks and eyes looking around, brows, and the mouth plates chewing.
- `ClawAttack_Check`: guard, windup, impact, open and shut.
- The nine game clips (see **Game package**).

There are no IK or control bones; the rig is FK only. The game clips were
solved with scripted IK and baked to the deform bones.

| Section | Triangles | Vertices | Material / map |
| --- | --- | --- | --- |
| KingCrab_Body (carapace, face, mouth, sternum) | 6,460 | 3,316 | KingCrab_Body, 2048 + 1024 |
| KingCrab_Eyes (smooth-shaded spheres) | 1,248 | 628 | KingCrab_Eyes |
| KingCrab_ClawR (crusher) | 2,316 | 1,176 | KingCrab_ClawR |
| KingCrab_ClawL (cutter) | 2,428 | 1,256 | KingCrab_ClawL |
| KingCrab_Legs | 7,216 | 3,688 | KingCrab_Legs |
| **Total** | **19,668** | | 5 × 2048 masters, 5 × 1024 delivery |

The total is below the 25k–60k the brief suggested. That is deliberate: the
look is broad low-poly facets, and more triangles would only soften them.

## Game package

Built by `animate_game.py`, per `../plans/BOSS_GAME_PACKAGE_SPEC.md`, after
the build:
`blender -b --factory-startup --python animate_game.py`, then
`python label_sheets.py` and `validate_exports.py`. It opens `KingCrab.blend`
and leaves the model, textures and rig unchanged. It adds the clips as actions
and writes these files to `exports/game/`:

- `AnimationData.json` uses the regular-mob schema, id `king-crab`, 24 fps,
  52 bones: parent-relative rest, and `matrix_basis` per frame through the
  Y/Z-swap `cf()`.
- `BossGameData.json` holds attack timings, hit points and strides.
- `GameChecks.json` holds foot drift, IK error and ground clearance.
- `KingCrab_Studio.fbx` is the rest mesh plus the deform armature, with no
  animation. It has 5 mesh objects named `KingCrab_<Section>` (never a bone
  name: Roblox's importer merges a mesh and a bone that share a name), and
  materials with the same names on the 1024² maps (embedded and copied to
  `KingCrab_Studio.fbm/`).

| Clip | Length | Loop | What it does |
| --- | --- | --- | --- |
| Idle | 3.0 s | yes | Two slow breaths and a weight shift; claws, mouth plates and eyes drift a beat behind the body |
| Walk | 1.5 s | yes | Heavy forward scuttle; two alternating leg groups (L1 R2 L3 R4 / R1 L2 R3 L4), duty 0.55; body dips each step. Stride 2.73 studs per cycle, speed 1.82 studs/s |
| Hit | 0.46 s | no | Shoved back and up, claws flinch, brows drop; returns exactly to the Idle start |
| Death | 2.25 s | no | Staggers, legs splay, the body collapses onto the sand, claws lie flat, eye stalks droop, small settle |
| ClawCrush | 2.25 s | no | Crusher rises high and back (body leans back), then drives down a wide arc and lands flat in front; the body lunges forward and drops at impact; the front-right leg steps back out of the way |
| RushStart | 0.875 s | no | Braces low, claws up, turns 90° with four quick steps so his right side leads; ends on RushLoop's first frame |
| RushLoop | 0.5 s | yes | Fast low sideways scuttle along his local −X (his right); alternating groups. Stride 2.2 studs per cycle, speed 4.4 studs/s |
| RushEnd | 0.875 s | no | Skids, then turns back with four steps and returns to the Idle start; starts on RushLoop's first frame |
| BubbleBarrage | 2.5 s | no | Mouth plates swing wide open, the body pumps three times while spraying, then the plates close |

Timings (seconds from clip start):

| Attack | warnStart | impact | activeEnd | recoveryEnd |
| --- | --- | --- | --- | --- |
| ClawCrush | 0.25 | 1.208 (frame 29) | 1.25 | 1.95 |
| BubbleBarrage | 0.20 | 0.60 (spray starts) | 2.00 | 2.35 |

Points and directions:

- **ClawCrush `ClawImpact`**: the palm centre on `Claw_R_Propodus` at offset
  (0, 2.6, 0). At impact it is at (−3.2, −10.0, 1.87) in root space, Studio
  (3.2, 1.87, −10.0). The ground point directly below it is also given.
- **BubbleBarrage `BubbleOrigin`**: on `Body`, at the mouth, root (0, −4.94,
  5.45). Direction at impact (0, −0.98, 0.20), Studio (0, 0.20, −0.98), 10° up
  from the body's forward. The pump times are included.
- **Rush**: `rushStrideLength` 2.2 and `rushSpeed` 4.4. After RushStart the
  travel direction is the model's forward (Blender −Y, Studio −Z), with the
  crab turned sideways.
- **Whole boss**: `rootHeight` 0 (the Root bone is on the ground under the
  body centre), height 10.08, footprint radius 11.5.

How the motion is made:
- Every leg is solved every frame by damped least squares on an analytic FK
  of its 4-bone chain, warm-started from the previous frame.
- The IK keeps each leg's knee and ankle above a per-leg floor so the shells
  stay out of the sand.
- Locomotion is in place: planted feet move backward at the travel speed, so
  with the model moving at `nominalSpeed` or `rushSpeed` they stay put.
- The crusher's arc is IK on the hand's position and orientation, so the palm
  lands flat. Its height was measured and corrected so the lowest point
  touches at z ≈ 0.
- Looping clips are solved over primed cycles, so they close; the last frame
  equals the first.

Checks (`GameChecks.json`, `validate_exports.py` passes):
- Planted-foot drift: 0.0000 studs on Idle, Walk and Hit; 0.0001 on RushLoop;
  0.017 on BubbleBarrage; 0.022 on RushEnd; 0.051 on ClawCrush (the pinned
  legs are at full stretch in the lunge).
- Ground: Death's lowest point is −0.044 at frame 36 (limit −0.05), and
  ClawCrush's is +0.006.
- In ClawCrush, the crusher's forearm, hand and finger never overlap the
  body, eyes or legs at any frame (BVH).
- `KingCrab_Studio.fbx` reimports with 5 meshes under 20k triangles, the
  right materials with 1024 maps, 52 bones whose names and parents equal
  `AnimationData.json`, and no animation.
- Every clip has duration×24+1 frames and no NaNs. Loops close exactly;
  attacks, Hit and Death start on the Idle start pose, and the attacks and Hit
  also end on it; the rush chain joins RushLoop exactly.

Previews:
- `previews/GameClips.png`: 6 frames of each clip, Workbench, front ¾.
- `previews/ClawCrush.mp4`, `Rush.mp4` (RushStart, four RushLoop cycles with
  the model travelling at rush speed, then RushEnd), `BubbleBarrage.mp4`:
  480×320 Workbench.

Not verified: Studio import and retargeting, the look in game, attack timing
feel, and hit shapes. No bubble or impact VFX are authored; the timings and
points are for Studio to spawn them.

## Roblox import notes (not tested in Studio)

- **Scale**: the FBX exports use `axis_forward='-Z', axis_up='Y'`,
  `add_leaf_bones=False`, `use_armature_deform_only=True` and embedded
  textures, matching the shipped hammer boss. Native Roblox FBX import has
  been observed to expand these rigs 100× (`mob-production/studio-import`
  receipts: `GetScale() = 0.01` is the baseline).
- **Bone axes**: bone-local axes differ after import. Retarget from global
  transforms as `mob-production/combat-ready/retarget_studio.py` does,
  mapping `(-X, Z, Y)`, rather than copying local rotations.
- **Clip FBXs**: the armature-only clips carry no mesh bind pose. Blender's
  importer, and likely others, adopt the first animated frame as the bone
  rest. The clips are correct in armature space (joints match the recorded
  poses to 0.0001 studs), but any importer that reads local rotations needs
  the rest skeleton from `KingCrab.fbx`.
- **Limits**: each mesh is under Roblox's 20k-triangle limit, and the delivery
  maps are 1024².

## Compare-pass log

| Pass | Change | IoU |
| --- | --- | --- |
| 1 | Blockout from the solved camera. The body-roll sign was wrong. | 0.847 |
| 2 | Roll fixed | 0.876 |
| 3 | Steep-front carapace, face rebuilt from back-projected landmarks | 0.893 |
| 4 | Painterly materials, cutter hook re-traced on the mask, mask tip fix | 0.909 |
| 5 | Gem-cut claws, painted pupils, hidden legs rerouted behind the crusher, arc-tiled sternum | 0.918 |
| 6 | Leg attachments back-projected, per-leg thickness, spikes widened | 0.927 |
| 7 | Coordinator review: paint to deep crimson with orange only on up-facing planes, worn cream chips, bigger eyes and brows, chunkier legs | 0.922 |
| 8 | Lighting study against reference value percentiles; larger paint cells | — |
| 9 | Crusher as depth-sculpted hulls (knuckle, lower palm, pollex), planar facets | 0.918 |
| 10–12 | Cutter hook grows from the palm; front coxae moved onto the belly flank; leg-target tweaks | 0.922 |
| 13–15 | Full bake pipeline; front-top sun; calibration converged; brows raised to overhang the eyes | 0.9216 (baked) |
| 16 | Least-squares leg fit with symmetric lengths (fixed stubby rest legs) | 0.918 |
| 17–19 | **User priority**: both claws rebuilt as `build_chela()` in a natural guard; attack check with BVH clearance; claws recalibrated; ROM clearance check (fixed a cutter-to-leg contact); two-frame ReferencePose export | 0.797 whole / 0.913 excl. claws |

## Verified in Blender

- The generator runs clean under Blender 5.2.1 headless (OptiX), end to end
  in about 2.5 minutes.
- `validate_exports.py` passes on fresh re-imports:
  - KingCrab.fbx: 5 meshes, each under 20k triangles; 52 bones whose names
    and parents equal the manifest; no leaf bones.
  - Every vertex is weighted, with at most 4 influences, normalized, and only
    to bones.
  - UVs are present and the embedded 1024 textures load.
  - Faceted normals survive: ≥ 99.9% of corners are flat on the faceted
    sections, and the eyes stay smooth.
  - Rest dimensions in studs match the manifest (scale and axes).
  - Clip FBXs are armature-only, contain only deform bones, and reproduce the
    recorded ReferencePose and ROM frame-37 joint positions to 0.0001 studs.
    Every bone moves in the ROM.
  - GLB: 5 skinned, textured meshes; ReferencePose poses 39 bones; ROM moves
    51 bones.
  - The game package; see **Game package**.
- Attack check (`attack-check.json`), sampled BVH overlaps: in all five
  poses, zero overlapping triangles between the swinging claw parts (carpus,
  hand, finger) and the body, eyes or legs. The movable fingers never
  intersect their hands.
- ROM clearance: no claw overlaps at any 4th frame of RigTest_ROM.
- All renders listed above were produced and inspected, including every
  crop, the ROM and joint sheets, the atlases and the game-clip sheet.

These are sampled geometric checks, not an exhaustive intersection proof.
The claw coxa and merus sit inside the shoulder socket by design and are
excluded from the overlap test.

## Not verified

- Roblox Studio import: scale, bone axes, skinning, SurfaceAppearance or
  TextureID display, and the in-game look.
- Gameplay readability at arena distance, attack timing feel, and hitboxes.
- Multi-client and published asset access.

## Known differences from the reference

1. **Both claws are re-posed** into a forward-down guard (approved). The
   crusher also has a longer, club-like palm than the reference's tall
   crescent, so the pincer reads in motion. Its fixed finger is red with a
   beige bite edge rather than the reference's beige lower jaw.
2. The painted pattern is cellular and more regular than the reference's
   hand-painted strokes. The orange patches on the carapace top are a little
   more uniform, and the chips are procedural and roughly placed.
3. The ground shadow falls back-right, not back-left (lighting chosen for
   colour agreement).
4. Far-side legs are thinner and leg joints are simpler than the painting.
   Front-leg knees differ by a few pixels from the traced positions.
5. The crab-right eye glance is approximated with a 20° bone yaw, and the
   eyes carry a small catchlight.
6. The back, underside and inner surfaces are authored continuations; the
   reference shows one view only.
