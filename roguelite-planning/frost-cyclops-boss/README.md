# Frost Cyclops: Frozen Pass boss

This is a Blender reconstruction of the supplied Frost Cyclops concept image, built at final size (1 Blender unit = 1 stud). It includes:

- a stylized low-poly model: faceted skin, a thick leaf-tuft fur mantle, leather wraps, a belt with a stone buckle, a loincloth, and a stone club;
- six textured, skinned mesh sections on one R15-named armature (61 deform bones);
- four actions: `ReferencePose`, `RigTest_ROM`, `GroundSlam` and `Stomp`;
- FBX and GLB exports that are re-imported and checked by `validate_exports.py`.

Nothing has been imported into Roblox Studio.

## Files

| Path | What |
| --- | --- |
| `build_frost_cyclops.py` | The generator: `blender -b --factory-startup --python build_frost_cyclops.py` (about 5 min). `FC_STAGE=probe` builds the model, rig and textures and makes one reference render (the fast loop). |
| `fc_sdf.py`, `fc_design.py`, `fc_parts.py`, `fc_grip.py`, `fc_weights.py`, `fc_paint.py`, `fc_pose.py`, `fc_motion.py`, `fc_camera.py` | Pure-numpy modules for the sculpt primitives, body and joint layout, accessories, the club grip, skin weights, the painterly albedo, the skeleton and poses, and the attack motion. |
| `fc_blender.py`, `fc_deliver.py` | bpy helpers; review renders, motion checks and exports. |
| `fc_preview.py` | Fast silhouette loop (numpy and OpenCV, no Blender). A design aid only; every delivered preview is a Blender render. |
| `measure_reference.py`, `solve_camera.py` | Reference landmarks, mask and colour probes; camera solve. |
| `compare_reference.py`, `calibrate.py`, `calibration.json` | Render-versus-reference comparison, and the per-material colour gain table (`CALIBRATION`). |
| `validate_exports.py` → `validation-report.json` | Fresh FBX and GLB re-import checks. |
| `FrostCyclops.blend` | The rig, the six sections, all actions and the packed 2048 textures. The `REVIEW_ONLY` collection holds the camera, lights, ground and markers; it is excluded from exports. |
| `exports/fbx/FrostCyclops.fbx` | Rest mesh plus armature, with the 1024 textures embedded. |
| `exports/fbx/FrostCyclops_{ReferencePose,RigTest_ROM,GroundSlam,Stomp}.fbx` | Armature-only clips. |
| `exports/glb/FrostCyclops.glb` | Meshes, armature and all four actions. |
| `textures/FrostCyclops_<Section>_BaseColor_2048.png` / `_BaseColor.png` | Master maps (Eye is 1024) and 1024 Roblox delivery maps. |
| `manifest.json`, `polygon-report.json`, `AttackMotionChecks.json` | Dimensions, bones, sections, texture and export hashes, the club offsets and attack impact points; per-section triangle counts; per-frame motion checks. |
| `source/` | The unchanged reference, `reference_mask.png`, `REFERENCE_NOTES.md` (inventory, colours, landmarks), `camera_solution.json`, `grip_solution.json` and `club_strike.json`. |
| `previews/` | See "Previews" below. |

## Rebuilding

```
python measure_reference.py            # mask, landmarks, probes (system Python: Pillow, numpy, OpenCV)
python solve_camera.py                 # camera solution
python fc_motion.py strike             # solves the club's flat striking face (writes source/club_strike.json)
blender -b --factory-startup --python build_frost_cyclops.py
python compare_reference.py render=previews/Reference_Match.png mask=_work/render_mask.png
blender -b --factory-startup --python validate_exports.py
```

The build is deterministic: fixed seeds, the camera and grip solutions are cached in `source/`, and colour gains are read from `calibration.json`.

## Provenance

The reference is the user's image, kept unchanged at `source/FrostCyclops_reference.webp` (1086 × 1448, SHA256 `DAAFFA2AE07CF831D8F83242B9A5B72126C30F1AEFA1D2395112BC2B3F6F63A5`). No reference pixels are used anywhere in the model or textures:
- all geometry is procedural (signed-distance sculpting, then flat-shaded decimation);
- every texture is painted in numpy from baked geometric passes (position, normal, AO, bevel edge, per-facet random, material id);
- colours come from eyedropped values and measured gains.

No Creator Store or external models are used.

## Measurements

The camera was solved by least squares over landmark pixels: f = 2077 px (51.6 mm on a 36 mm vertical sensor), pitch 0°, yaw 1.15°, RMS 1.0 px. Absolute scale comes from the 13-stud target height (crown). Depths are stance priors, because a single view cannot recover them; they are listed in `solve_camera.py`.

| Measure (studs) | Value |
| --- | --- |
| Top of head, reference pose | 13.09 (target ≈ 13; Hammer boss 11.92) |
| Width including club, reference pose | 12.38 |
| Depth including club | 7.86 |
| Eye centre height | 11.85 |
| Shoulder joint span | 6.04 |
| Club haft radius, grip / stone | 0.32 / 0.48 |
| Stone half extents | 1.62 × 1.36 × 1.86 |

The landmark pixel table and part inventory are in `source/REFERENCE_NOTES.md`.

## Colour: reference versus final render

Each probe is a region box plus a colour rule, compared on mid-luminance sRGB. The ratio is the mean-linear reference / render.

| Region | Reference mid | Render mid | Worst channel |
| --- | --- | --- | --- |
| Fur mantle | 221, 208, 195 | 218, 206, 193 | 3.8 % |
| Club stone | 145, 137, 139 | 152, 145, 146 | 2.4 % |
| Club haft | 98, 77, 72 | 104, 82, 75 | 3.0 % |
| Club strap | 77, 62, 62 | 81, 66, 66 | 5.6 % |
| Buckle stone | 102, 98, 104 | 121, 117, 123 | 1.5 % |
| Leather wrap | 93, 74, 73 | 100, 82, 82 | 8.8 % |
| Loincloth | 59, 58, 72 | 52, 51, 64 | 9.7 % |
| Toes / foot skin | 140, 160, 189 | 133, 150, 182 | 1.7 % |
| Skin, belly | 130, 153, 184 | 143, 160, 191 | 16.3 % |
| Skin, right upper arm | 139, 157, 203 | 145, 161, 191 | 13.5 % |
| Leather belt | 74, 61, 63 | 70, 57, 58 | 28.0 % |
| Tusk | 234, 221, 206 | 214, 205, 196 | 13.8 % |
| Iris | 70, 192, 219 | 77, 187, 204 | 20.3 % |
| Skin, left shin | 96, 121, 157 | 119, 136, 168 | 34.5 % (render too light) |
| Skin, left upper arm | 152, 170, 199 | 123, 139, 171 | 47.0 % (render too dark) |
| Skin, forehead | 165, 181, 209 | 132, 149, 181 | 48.7 % (render too dark) |

Eight regions are within the ~8–10 % target. The skin regions are not. The skin albedo is one calibrated colour; what differs is the lighting distribution. The reference lights the left upper arm and forehead strongly and keeps the shins in shadow, and the three-light review rig does not reproduce that. The belt probe box is small and partly catches the buckle's shadow. The sclera probe finds no pixels because the lowered eyelid covers the probe box.

## Silhouette

The reference mask was made with OpenCV GrabCut, seeded by a rectangle, with the eye forced to foreground and small islands and holes cleaned. The method is described in `source/REFERENCE_NOTES.md`. The final silhouette IoU against `source/reference_mask.png` is **0.9156**, below the 0.92 target. The pass limit was reached and this value is accepted as final. The largest remaining differences are the fur around the neck (the reference's collar stands higher beside the head), the right fist and forearm outline, and the loincloth's centre-flap outline.

## Compare-pass log

| Pass | Change | IoU |
| --- | --- | --- |
| P0 | First posed-rig render: mitten hands, boxy head, thin card-like tufts, smooth skin | 0.877 |
| P1 | Head rebuilt from the measured face layout; thick seven-sided leaf tufts on a pelt; 30-plane stone; separated toes; wraps down to the wrist | 0.878 |
| P2 | Row-by-row silhouette fixes to the torso, legs and mantle extents; gravity-draped tufts; hand scale | 0.904 |
| P3 | Key and fill lights plus sky; colour calibration pass 1 | 0.904 |
| P4 | Grip rework (see below); club haft through the fist; the ClubImpact point; natural-bending right elbow depth | 0.916 |
| P5 (final) | New Ground Slam motion; Stomp; teeth, head width, loincloth, hip fur, wrap paint; calibration pass 2 | 0.9156 |

## Rig

- **Deform bones (61, R15 names):**
  - Spine: `Root → HumanoidRootPart → LowerTorso → UpperTorso → Head`, with `Jaw`, `Eye`, `EyelidUpper` and `Brow` under the head.
  - Arms: `{Left,Right}UpperArm → LowerArm → Hand`, each hand carrying `{Index,Middle,Ring,Pinky,Thumb}1-3`.
  - Club: `Club` under `RightHand`.
  - Legs: `{Left,Right}UpperLeg → LowerLeg → Foot → Toes`.
  - Secondary: `Belly`, `Mantle_L/R`, `Loincloth_Front_1/2` and `Loincloth_Back_1/2`.
- **Non-deform helpers.** These are kept in the .blend and excluded from exports (`use_armature_deform_only=True`): IK hand, IK foot and pole targets with IK constraints at influence 0, `EyeTarget` (damped track, influence 0) and `ClubImpact`.
- **Rest pose.** This is the image stance with both arms abducted a further 9° and the fingers relaxed. `ReferencePose` restores the image stance and the closed fists. In the rest pose the stone dips 0.10 stud below the ground plane, because the abducted arm lowers it; none of the actions do.
- **Elbow hinges.** Arm bone rolls are aligned to each arm's plane, so +X rotation of a `LowerArm` is flexion on both sides.
- **Weights.** Weights come from primitive ownership, arm and leg chain splits with blended joints, graph smoothing, a limit of 4 influences, and normalisation. Accessories follow explicit rules:
  - wraps, belt, buckle, teeth and tusks are rigid;
  - the club is 100 % `Club`;
  - the mantle follows the skin, with its torso share moved to `Mantle_L/R`, and is inverse-skinned so that it sits exactly in the reference pose;
  - the loincloth uses the pelvis, the loincloth bones and 50 % of the thighs at the sides.

## Club and grip

- **Hammer grip.** `fc_grip.py` solves a real hammer grip in hand space, and the result is cached in `source/grip_solution.json`:
  - the haft (radius 0.32) runs across the palm on a 28° diagonal, from the index knuckle to the heel of the hand, and passes right through the fist;
  - a pommel stub sits past the pinky side;
  - the four fingers curl round the front of the haft at contact distance, with a clearance of −0.03 to +0.02 at the closest point of each finger;
  - the thumb closes over the index finger from the other side.
- **Grip offset.** The `Club` bone head is the centre of the finger tunnel. It sits at hand-local `(0, 0.486, −0.652)` studs, with the haft direction `(−0.883, 0.469, 0)` in the hand bone's frame. The full `Club` in `RightHand` 4×4 is in `manifest.json → club`. To detach or throw the club, unparent `Club` and keep that transform.
- **ClubImpact.** This is the centre of the stone's flat striking face, at `(0.933, 5.938, −0.270)` in `Club` bone space with face normal `(0.901, 0.434, 0)`. The face is oriented so that it points straight down at the Ground Slam impact frame.

## Attacks

These are the user's kit: the club never swings at players. Every frame of both attacks is keyed at 30 fps, and each action has an `Impact` marker. Checks run on the Blender-evaluated rig (`AttackMotionChecks.json`) and all asserted limits passed.

**GroundSlam** (60 frames, impact at frame 29, strike window 21–29):
- **Windup.** The arm rises out to the side, then overhead, and cocks the club behind the head at frame 21, with the stone back and down behind him. The torso leans back, twists toward the club side and shifts its weight back.
- **Strike.** The shoulder drives a near-vertical arc in a fixed swing plane. The elbow straightens by mid-swing, the club accelerates (ease-in), and the torso crunches and the knees drop into the hit. The flat face lands on the ground in front of him and to his right.
- **Follow-through.** A bounce, a settle and a recovery back to the carry.
- **Checks:**
  - strike wrist bend ≤ 18.0°;
  - elbow out of the swing plane 0.0;
  - elbow flex ≤ 6.0° from mid-swing to impact;
  - reach ≥ 99.86 %;
  - club-to-body clearance ≥ 0.128 stud;
  - lowest club point ≥ 0.0, touching z = 0 at impact;
  - grip digit drift ≤ 3e-6.
- **Impact point:** `ClubImpact_root` = Blender `(−3.451, −8.164, 0.001)` = Roblox `(3.451, 0.001, −8.164)`.

**Stomp** (80 frames, impact at frame 50):
- **Weight shift.** The pelvis moves toward the right (standing) foot.
- **Slow raise (frames 10–44).** The left thigh rises sumo-style, out and forward, to horizontal with the knee at 99°. A slight extra rise gives anticipation.
- **Slam (frames 44–50).** The foot drives straight down and lands sole-flat a little forward, toes along the facing direction. The body drops, and the Belly and Mantle bounce. Then it recovers.
- **Checks:**
  - standing-foot drift 1e-6;
  - knee twist ≤ 0.07° (one hinge axis);
  - thigh-to-gut clearance ≥ 0.208;
  - the club never touches the ground (min z 0.089).
- **Impact:** `StompImpact_root` = Blender `(2.317, −2.941, 0)` = Roblox `(−2.317, 0, −2.941)`. `StompSpikeDirection` = Blender `(0, −1, 0)` = Roblox `(0, 0, −1)`.

The Roblox vectors use the axis mapping observed in `../mob-production` imports, `(−X, Z, Y)`, and are not verified for this asset.

## Previews

All previews are real Blender renders of the posed, skinned rig.

- `Reference_Match.png`: 1086 × 1448, reference framing, from `ReferencePose`.
- `Comparison_SideBySide.png`, `Comparison_Overlay.png`, `Comparison_Silhouette.png`: comparisons, with the silhouette image also showing a diff.
- `Comparison_{Face,MantleL,MantleR,HandR,FistL,Club,Belt,Feet}.png` and `Detail_*.png`: zoomed crop comparisons and 3× close-ups from the reference camera.
- `Turnaround.png` and `Turnaround_*.png`: front, ¾, side and back.
- `Face_Closeup.png`.
- `Rig_Bones.png`: the deform skeleton over the model.
- `RigTest_ROM.png`: 16 poses, including arms overhead, forward and back, elbows, open hands, a high knee, deep squat, forward lean, twist, side bend, head turn and nod, jaw, eye and blink, secondary bones, overhead club and toes.
- `AttackCheck_Club.png`: Ground Slam carry, windup, mid-swing, impact and recovery, in front, ¾ and grip close-up views. A cyan ring marks the impact point.
- `AttackCheck_Stomp.png`: weight shift, top of raise, mid-slam, impact and recovery, in front, ¾ and side views.
- `SwingArc_GroundSlam.png` and `SwingArc_Stomp.png`: side-view ghosted frames from windup to impact.
- `GroundSlam.mp4` and `Stomp.mp4`: Workbench, ¾ plus side view, at normal speed then half speed.

## Roblox import notes

- **Exports.** Exports use `axis_forward='-Z'`, `axis_up='Y'`, `add_leaf_bones=False`, `use_armature_deform_only=True`, `mesh_smooth_type='OFF'` (faceting is kept as flat corner normals) and embedded 1024 textures. These are the same axis settings as the Hammer boss.
- **Known importer behaviour.** `../mob-production/combat-ready/README.md` records that Roblox's native FBX import expands the model 100× (`GetScale() = 0.01` after normalisation) and produces different bone-local axes. Animation for these mobs is therefore retargeted from global transforms (`retarget_studio.py`), not copied from bone-local FBX curves. The same approach should be used here, because the clips are delivered as armature-only FBX files and as GLB actions.
- **Size.** The asset is authored at final size (13.09 studs). The texture density assumes that size, so do not rescale the mesh in Studio.

## Verified in Blender

The following were checked in Blender 5.2.1, headless:

- **Build.** The generator runs clean end to end, including textures, rig, actions, renders, checks and exports.
- **Validation.** `validate_exports.py` passes on fresh re-imports:
  - both the FBX and the GLB contain 6 skinned meshes, each under 20k triangles (33,591 in total);
  - 61 bones, with names and hierarchy matching `manifest.json`;
  - every vertex weighted, at most 4 influences, weights normalised;
  - UVs present and 1024 textures loading;
  - flat faceting kept (FBX 100 %, GLB ≥ 99.4 % of faces);
  - all four actions present, with bone motion in every non-static clip;
  - the head top at 13.09 studs, and the face on the −Y side.
- **Motion checks.** The checks in `AttackMotionChecks.json`, computed on the evaluated rig, all pass.
- **Visual review.** Every preview listed above was inspected.

## Not verified

- **Roblox.** Studio import, in-game look and scale, the axis mapping of the Roblox vectors above, and texture upload.
- **Animation.** The attacks' look at game speed with VFX, and blending into idle or walk clips (none are authored). Animations beyond the ROM and the two attacks.
- **Loincloth.** During the Stomp raise the loincloth passes into the raised thigh: the minimum loincloth-to-thigh clearance is −0.58 stud, and cloth collision is not simulated.
- **ROM extremes.** The extreme ROM poses show some fur-to-head intersection on the head turn and club-to-head proximity at 130° elbow flex. These are ROM probes, not authored motion.

## Known differences from the reference

- **Silhouette.** IoU is 0.9156 (target 0.92).
  - The fur collar beside and behind the head is lower than in the reference, so the head looks less framed by fur.
  - The right forearm and fist outline is slightly narrower.
- **Skin.**
  - The skin is a lighter, more uniform periwinkle with a small-triangle facet pattern from decimation. The reference has broader planar facets with stronger painted light and shadow variation.
  - The forehead and left arm read darker and the shins lighter than in the reference (a lighting difference; see the colour table).
- **Face.** The eye socket and brow are less sculpted. The brow reads as a smooth ridge rather than the reference's heavy, angular V, and the upper lid covers more of the sclera.
- **Loincloth.** It is flatter and darker, with fewer lighter worn patches. The centre flap is broader and less ragged than the reference's layered torn leather.
- **Club.** The haft is thinner than the reference's (0.32 radius at the grip, chosen so the fingers can close round it). The straps are a plain X plus two bands; the reference's lashing is more layered and worn.
- **Belt.** A thin belt tail hangs at his right hip and reads as a stick in the front view.
- **Back and underside.** These are authored, not recovered: back fur rows, the loincloth back flap and the soles.
