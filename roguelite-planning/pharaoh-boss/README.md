# Pharaoh boss (Desert Basin): faithful rebuild

This is the Desert Basin map boss: an undead mummy-pharaoh brute holding a heka crook.
It is a Blender asset that reconstructs the supplied reference image in 3D. The
model is textured and skinned to a 62-bone, R15-named, animation-ready skeleton,
and exported to FBX and GLB.

**It has not been imported into Roblox Studio and is not wired into gameplay.**

Units: 1 Blender unit = 1 stud. The model faces -Y with Z up; +X is the character's
left. The model is authored at final size, so the baked atlases do not stretch.
Do not rescale it in Studio. The Hammer boss is scaled 1.15× at runtime instead.

## Files

- **Scripts**
  - `build_pharaoh.py` is the whole generator: sculpt, materials, bake, rig, skin, actions, attack-pose solve, renders, exports and reports.
    - It is self-contained: it imports and `exec()`s no sibling kit.
    - Its random jitter uses a fixed `crc32` seed, so rebuilds are identical.
  - `camera_solve.py` (system Python) solves the reference camera and writes `source/camera_solve.json`.
  - `make_reference_mask.py` (system Python, OpenCV) builds `source/reference_mask.png`.
  - `compare_reference.py` (system Python) writes the comparison sheets, the silhouette IoU and the colour probes (`previews/compare_report.json`).
  - `validate_exports.py` (Blender) re-imports the FBX and GLB fresh and writes `validation-report.json`.
- **`source/`**
  - `Pharaoh_Reference.webp`: the reference, unchanged.
  - `reference_mask.png`.
  - `camera_solve.json`.
  - `REFERENCE_NOTES.md`: part inventory with counts, eyedropped colours and landmark pixels.
- **`Pharaoh.blend`**
  - Holds the rig, the six skinned sections and the actions `ReferencePose` and `RigTest_ROM`.
  - Textures are packed.
  - The `REVIEW_ONLY` collection (camera, sun, fill and sand floor) is not exported.
- **`exports/fbx/`**
  - `Pharaoh.fbx`: rest mesh + armature + embedded textures.
  - `Pharaoh_ReferencePose.fbx` and `Pharaoh_RigTest_ROM.fbx`: armature-only clips.
- **`exports/glb/Pharaoh.glb`**: meshes, armature and both actions.
- **`textures/`**
  - Per section, a 2048² `*_Color` / `*_Rough` master.
  - Per section, a 1024² `*_1024` Roblox delivery copy.
- **`previews/`** (all real Cycles renders of the mesh)
  - `Reference_Match.png`: posed rig at 1086×1448 through the solved camera.
  - `Comparison_SideBySide`, `Comparison_Overlay` and `Comparison_Silhouette`.
  - `Crop_*`: face/uraeus, nemes/collar, belt/gem, kilt/apron, both hands, staff hook and foot, feet, torso, left arm.
  - `Turnaround.png`: front, side, back, ¾.
  - `Face_CloseUp.png`.
  - `Rig_Bones.png`.
  - `RigTest_ROM.png`.
  - `AttackCheck_Staff.png`.
- **Reports**
  - `manifest.json`: dimensions, every bone and its parent, sections, textures and hashes, staff grip.
  - `polygon-report.json` and `validation-report.json`.
  - `GripChecks.json` and `AttackPoses.json`.
  - `build.log`.
- **`PROGRESS.md`**: the working log kept during the build.

## Rebuilding

```
python make_reference_mask.py        # only if the mask must be regenerated
python camera_solve.py               # only if the landmarks change
blender -b --factory-startup --python build_pharaoh.py      # STAGE=full, about 2 min on the RTX 2070
python compare_reference.py
blender -b --factory-startup --python validate_exports.py
```

Environment switches:

- **`STAGE=sculpt`** builds only the geometry and renders one reference frame (about 15 s).
  - Add `VIEWS=1` for orthographic views.
  - Add `ZOOM=face,fistR,handL,feet,torso,kilt` for 3× region renders.
  - Compare those with `python compare_reference.py _work/probe.png _work/probe_mask.png _work/cmp`.
- **`PROBE_ONLY=1`** stops a full build after `Reference_Match`.
- **`SAMPLES`** and **`TEX`** set the render samples and atlas size.

Cycles uses OptiX, then CUDA, and falls back to the CPU with 5 threads when `FORCE_CPU=1`.

## Provenance

The reference is the user-supplied image:

- `source/Pharaoh_Reference.webp`, 1086 × 1448 RGB;
- SHA256 `BDB705682E45F1C0B2C9BF03BE73091A6C3202D56C4F90FA904E8B1E79253D8A`.

It is used only for measurement: landmark pixels, traced outlines unprojected
through the solved camera, the silhouette mask and eyedropped colours. **No reference
pixel is projected or pasted onto the model.** Every texture is baked from procedural
painterly shaders authored in `build_pharaoh.py`. No Creator Store or external model
is used.

## How it was measured

`camera_solve.py` runs a Gauss-Newton least-squares fit. It uses measured landmarks:

- uraeus top;
- both toe fronts;
- staff foot;
- both ankle-band centres and widths;
- eye midpoint.

It also uses weak documented priors (horizon row, depth layout), and anchors the
headdress top at 12.5 studs.

| Solved | Value |
| --- | --- |
| Focal length | 2232 px (55.5 mm on a 36 mm sensor, AUTO fit) |
| Camera | (-0.07, -24.02, 3.24), pitched up 7.06° (low front view) |
| Horizon row | 1000 |
| Residual RMS | 0.40 σ |

Most outlines were traced in reference pixels and unprojected onto chosen depth
planes through this camera: the nemes stripes, lappets, face, kilt panels, staff
axis and crook, and the hand key points. That makes the silhouette match by
construction while the depths keep it plausible from other angles.

The staff axis is a least-squares fit to the reference shaft centres (rms 1.8 px).

| Measure (studs) | Value |
| --- | --- |
| Uraeus top / nemes crown (just behind it) | 12.27 / 12.72 |
| Width in rest pose (arms spread 9°) | 10.98 |
| Depth | 5.56 |
| Staff length / section | 12.75 / 0.44 square, chamfered |
| Staff top | 12.71 (just under the crown, as in the image) |
| Right elbow at rest | 96° flexed |
| Left elbow at rest | 26° flexed |
| Upper arm / forearm (right) | 2.31 / 1.93 |

The camera prior placed the uraeus 0.95 studs in front of the pelvis axis. Once
modelled, it sits 1.4 studs in front, so the same image row lands 0.23 studs
lower. The crown behind it is the true highest point.

### Staff grip

The `Staff` bone is parented to `RightHand`. Its head is the grip point: the centre
of the finger tunnel, on the staff axis.

| Grip value | Coordinates |
| --- | --- |
| Reference-pose world position | (-3.68, -2.55, 7.02) |
| Offset in RightHand rest space | (-0.714, 0.935, 0.164) |
| Staff axis | (-0.069, -0.078, 0.995) |
| Staff foot on the ground | (-3.19, -2.00, 0) |

## Colour: measured, not eyeballed

`compare_reference.py` takes class-filtered pixels inside region boxes in both
images. The probe boxes are in `compare_reference.py`. It prints the mean sRGB and
the linear per-channel ratio. Those ratios were multiplied into `CALIBRATION` in
`build_pharaoh.py` over three passes.

Final values, from the baked, posed render:

| Material | Reference sRGB | Render sRGB | Worst channel |
| --- | --- | --- | --- |
| Skin (olive grey-green) | 128, 117, 85 | 129, 118, 85 | 0.9 % |
| Skull bone | 145, 133, 102 | 149, 136, 104 | 2.8 % |
| Bandage (cream) | 206, 177, 139 | 203, 174, 136 | 2.2 % |
| Gold | 194, 142, 61 | 195, 143, 62 | 1.6 % |
| Royal blue | 62, 78, 122 | 65, 79, 123 | 4.8 % |
| Belt brown | 148, 101, 45 | 149, 101, 44 | 2.2 % |
| Gem | 51, 99, 136 | 55, 101, 139 | 7.8 % |

Silhouette IoU against `source/reference_mask.png` is **0.921**.

The reference mask comes from OpenCV GrabCut, seeded by a hull plus foreground and
background scribbles. Small islands are dropped and holes under 1,500 px are filled;
this recovers the eye sockets that GrabCut marked as sky. The mask was checked in
zoomed contour overlays.

Review lighting approximates the reference:

- a warm sun from the upper right behind his left shoulder, read from the cast shadows;
- a soft front fill;
- sky ambient.

The view transform is Standard, so texture colours show as authored.

## Construction

- **Body.** Faceted icosphere muscle masses are *unioned* with a voxel remesh, not blended, so the deltoids, biceps, pecs and abs meet in creases. The mesh is then decimated.
  - Soft-facet split normals sit halfway between flat and smooth. They survive export: the validator measures 91–100 % split vertices after re-import.
  - A conform pass pushes skin under the collar, belt and kilt.
- **Bandages.** Ribbons are projected onto the skin from the limb axis.
  - They are taut: they bridge creases along the path and use an upper convex hull across their width.
  - Each strip gets a painted darker edge line from a per-vertex across-strip coordinate.
  - Chest X straps are sashes on tilted planes.
  - Arm, leg and foot wraps are tilted rings that cross each other.
  - Three torn ends hang free on their own bones: left shoulder, left wrist and left foot.
- **Skull.** Faceted lofted sections with boolean-carved sockets, nose and mouth.
  - Separate V brows and cheek plates.
  - 5 upper and 6 lower teeth; the lower row is on the `Jaw` bone.
  - The eyes are the `EyeGlow` section: an emissive white core plus a cyan halo.
- **Nemes.**
  - Wing stripes are lofted between traced rows.
  - The dome is 15 radial stripes with gold at the centre.
  - Lappets are four stripe blocks each.
  - A striped back flap and a banded tail.
- **Uraeus.** Relief: hood, rim, belly scutes, domed head, eyes.
- **Usekh collar.** Three rings of beveled tiles (gold / blue + slate / gold) with a raised rim, on a draped frame that rises over the shoulders.
- **Kilt.** Panels are traced in pixels and ray-cast onto a flared proxy, then meshed by constrained Delaunay.
  - Cream skirt with a torn hem.
  - Blue side panels with gold borders, blue inner panels with gold hems, and cream strips.
  - Centre apron: gold backing plus a blue panel.
  - Tattered under-apron.
  - Back tail, seen between the legs.
- **Staff.** Square chamfered bands in the reference's order.
  - The crook is a faceted sweep with bands G B G B G B G.
  - Gold frustum foot.
- **Bands.** The ankle bands, left bracer (alternating panels) and right cuff are chunky beveled rings.
- **Hands.** Changed at the user's request: a natural, animation-friendly grip instead of the reference's literal stacked bars.
  - **Right hand (staff grip)**
    - The wrist is solved so the hand continues straight out of the forearm.
    - The palm sits on the outer side of the shaft.
    - Four blocky fingers curl round the shaft, with a staggered knuckle row and a thumb closing over the index finger.
    - The fitted gold cuff sits behind the wrist.
    - The fingers' inner faces sit 0.022 studs off the shaft's chamfered corners (`GripChecks.json`).
  - **Left hand (open claw):** a palm continuous with the wrist, four spread, gently clawed fingers, and a separate thumb.

## Rig

The rig is one armature, `Pharaoh_Rig`, with 62 deform bones and no leaf bones. Its
origin is on the ground under the body.

- **Spine and head:** `Root → HumanoidRootPart → LowerTorso → UpperTorso → Head → Jaw`.
- **Headdress** (under `Head`): `NemesLappet_L_1/2`, `NemesLappet_R_1/2`, `NemesTail`.
- **Arms:** `Left/RightUpperArm → LowerArm → Hand → {Index, Middle, Ring, Pinky}1–3, Thumb1–2`.
  - `Staff` is under `RightHand`.
  - `BandageEnd_ShoulderL` hangs from `LeftUpperArm` and `BandageEnd_WristL` from `LeftLowerArm`.
- **Legs:** `Left/RightUpperLeg → LowerLeg → Foot → Toes`, with `BandageEnd_FootL` on `LeftFoot`.
- **Kilt** (under `LowerTorso`): `Apron_1 → Apron_2`, `Kilt_L`, `Kilt_R`, `Kilt_Back`.

Bone rolls put local X on each joint's flexion axis, so +X closes the joint. Left
and right mirror each other.

### Weights

- The unioned skin uses bone heat on the 15 core bones only.
- Fingers and palms use preset chain weights, blended ±0.07 studs across each knuckle.
- Bandages transfer weights from the nearest skin surface. Trailing ends blend into their own bones.
- The kilt and apron use height-graded chain weights.
- Ornaments (collar tiles, bands, belt, gem, uraeus, staff) are rigid on their host bone.
- Every vertex is weighted, with at most 4 influences, and normalised. `validate_exports.py` checks this.

### Poses

- **Rest pose:** the reference stance with both upper arms spread 9° away from the body. The meshes were baked through the armature, then applied as rest.
- **`ReferencePose`** rotates the arms back. `Reference_Match` is rendered from that posed rig.
- **`RigTest_ROM`** runs at 24 fps, 22 keys (rest first and last), one every 12 frames:
  - arms overhead, forward and back;
  - elbows to 130° and back to about straight;
  - wrists with fist and open;
  - hip flex, and a high knee on each side;
  - torso twist, bend and side bend;
  - head turn with jaw open, and head nod;
  - lappet and tail swing;
  - kilt and trailing-end swing;
  - staff raise, slam and thrust.
- **Attack poses:** `solve_attacks` aims overhead raise, ground slam and crook thrust against the real rig, using only shoulder, elbow, wrist and torso within anatomical ranges. The Staff bone never rotates relative to the hand.
  - `AttackCheck_Staff.png` shows each pose front-on plus a grip close-up.
  - Finger drift in the staff frame is ≤ 3e-6 studs in every pose, so the hand stays closed on the shaft.
  - No staff vertex enters the body in any pose.
  - The minimum staff-to-body distances are 0.78 (rest), 2.63 (overhead), 0.95 (slam) and 1.27 (thrust) studs.

### Sections

| Section | Triangles |
| --- | --- |
| Body (skin, palms, fingers, feet) | 14,573 |
| Bandages | 16,424 |
| Head (skull, nemes, uraeus, collar) | 14,088 |
| Waist (belt, gem, kilt, bands) | 11,158 |
| Staff | 1,984 |
| EyeGlow | 320 |
| **Total** | **58,547** |

Every section is under Roblox's 20,000-triangle per-mesh limit.

## Roblox import notes

The export settings match the Hammer boss: `axis_forward='-Z'`, `axis_up='Y'`,
`add_leaf_bones=False`, `use_armature_deform_only=True`, and
`path_mode='COPY', embed_textures=True` for the rest mesh.

`mob-production/combat-ready/README.md` and the `studio-import/*-receipt.json` files
record two known issues with Studio's native FBX import:

- it expands the model 100× (normalised model scale 0.01);
- it produces different bone-local axes.

Handle them the same way the mob pipeline does:

- treat `GetScale() = 0.01` as the baseline, not an extra scale;
- record an import receipt of the actual imported bones;
- retarget clips against that rest hierarchy rather than assuming Blender's bone axes.

Upload the `textures/*_1024.png` maps, because Roblox caps uploads at 1024. The
hammer boss found SurfaceAppearance renders its atlases more cleanly than
TextureID. Set `Pharaoh_EyeGlow` to Neon or use an emissive treatment.

## Compare-pass log

IoU is measured against `source/reference_mask.png`. The worst colour channel is
from the probe table.

| # | Pass | Main changes | IoU / worst colour |
| --- | --- | --- | --- |
| 0 | Blocking | The body alone was 0.63. Adding the head, nemes, collar, belt, kilt, staff, hands and feet brought it to 0.87. | 0.87 / — |
| 1 | Anatomy and bandages | Metaballs replaced by unioned faceted masses, taut bandage ribbons, chest X at the measured height. | 0.894 / 18 % |
| 2 | Coordinator review | Cooler skin and clean cream bandage, glowing eye core and halo, heavier brow, shorter bracer, wider blue collar ring. First full rig/bake/export run; calibration from the baked render. | 0.893 / 22 % (gem, blue) |
| 3 | Detail | Rounder sockets, uraeus relief, bigger toes, foot wraps, compact fist. Calibration pass 2. | 0.893 / 22 % (gem) |
| 4 | User priority | Natural right grip and left hand rebuilt, fitted cuff, attack-pose solver, AttackCheck sheet and grip clearance checks. | — |
| 5 | Silhouette | Staff axis refit, crook retraced, visible back tail, world-placed deltoids, asymmetric lats, left arm and hand refit. Clip export rest-frame fix. Validation 26/26. | 0.921 / 7.8 % |
| 6 | Detail | Taut-across bandages with painted edge lines, deltoid sleeves, round U collar, faceted skull with chunkier V brows and cheek plates. Deterministic jitter. ROM elbow range limited to 130°. | **0.921 / 7.8 %** |

## Skull pass (2026-09-29, user review: "not as chiselled and detailed")

This was one focused pass. Only the skull changed; the rest of the model is unchanged.

`build_head()` was rebuilt from carved blocks traced off a 6× zoom of the reference face:

- **Brows:** heavy angular V brows proud of the skull, with a glabella ridge down to the nose.
- **Sockets:** deep, angular boolean pits. The cyan EyeGlow (core plus halo) now sits inside them, 0.14–0.20 studs behind the face.
- **Cheeks:** angular cheekbone blocks, lower orbital ledges, and a maxilla with two side planes angled back, so the cheek hollows fall into shadow.
- **Nose:** an inverted-heart nasal cavity.
- **Teeth:** a clenched, uneven grimace: 6 upper teeth with a wide gap, 8 lower teeth, and a dark mouth line between the rows.
- **Jaw:** a heavier, squarer stepped jaw (shelf plus chin) on the `Jaw` bone.
- **Construction:** face blocks and pits are extruded along the reference camera's rays, so they image exactly as traced while keeping real depth from other angles.
- **Paint:** the bone paint now has stronger cavity darkening, lighter worn ridges and more chips.

Results:

- **Jaw:** jaw-open was checked in the ROM head-turn and nod frames. The lower teeth and chin drop cleanly and the mouth interior reads dark.
- **Head texture:** re-baked.
- **Exports:** FBX and GLB re-exported. `validate_exports.py` passes 26/26.
- **Fit:** silhouette IoU 0.921, unchanged. The bone colour probe is 4.9 %, and all probes stay within 8 %.
- **Previews:** only `Reference_Match`, `Comparison_SideBySide`, `Face_CloseUp` and `Turnaround` were refreshed, using `PREVIEWS=subset`. `Rig_Bones`, `RigTest_ROM`, `AttackCheck_Staff` and the `Crop_*`/overlay sheets still show the previous skull.

## Game package (2026-09-29)

This follows `plans/BOSS_GAME_PACKAGE_SPEC.md`. The model, textures and rig are unchanged; only the clips were added to `Pharaoh.blend`.

**Rebuild:** `blender -b --factory-startup --python build_game_package.py` (about 15 s), then `validate_exports.py`.

### Outputs

**`exports/game/AnimationData.json`**

- Schema: `animate_mobs.py`, id `pharaoh`, 24 fps, all 62 deform bones.
- Transforms: `matrix_basis` through the Y/Z swap.
- Motion: `strideLength` 4.2 studs per cycle, `nominalSpeed` 2.8 studs/s.

| Clip | Length | Loop | Content |
| --- | --- | --- | --- |
| Idle | 3.0 s | yes | Breathing and weight shift. Cloth, lappets and bandage ends drift later. |
| Walk | 1.5 s | yes | Heavy stomp with a 62 % stance and a body drop at each foot strike. The staff is carried off the ground and swings with the right arm. |
| Hit | 0.458 s | no | Flinch back, then back to the Idle start pose. |
| Death | 2.25 s | no | Staggers, buckles to a crouch and falls face down. The staff is released and topples flat beside him. |
| CursedBolts | 2.125 s | no | Staff lifts clear, then the crook is raised and aimed. Gathers from 0.45 s, releases at 1.042 s (frame 25), small recoil, back to idle. |
| TombEruption | 2.5 s | no | Staff lifted in both hands, then its foot driven into the ground in front at 0.792 s (frame 19). Channels while planted until 1.6 s, then recovers. |

**`exports/game/BossGameData.json`**

| Attack | warnStart | impact | activeEnd | recoveryEnd |
| --- | --- | --- | --- | --- |
| CursedBolts | 0.30 | 1.042 | 1.042 | 2.125 |
| TombEruption | 0.35 | 0.792 | 1.60 | 2.30 |

- **`BoltOrigin`:** on the `Staff` bone at offset (0.32, 4.52, 0.00), the centre of the crook's curl.
  - At release it is at root (-2.17, -7.40, 10.19), Studio (2.17, 10.19, -7.40).
  - Release direction is (0.14, -0.78, -0.61), Studio (-0.14, -0.61, -0.78). This aims at a point 16 studs ahead at chest height; the game re-aims at the real target.
  - Three fan directions at ±15° are listed as well.
- **`StaffImpact`:** on the `Staff` bone at offset (0, -7.06, 0), the bottom of the staff foot.
  - At impact it is at root (-1.53, -3.99, 0.02), Studio (1.53, 0.02, -3.99).
- **Body:** `rootHeight` 5.2, `height` 12.72, `footprintRadius` 5.90. The footprint is the widest horizontal extent of the body in the rest pose, without the staff.

**`exports/game/Pharaoh_Studio.fbx`**

- Rest mesh and armature: deform bones only, no leaf bones, no animation.
- Six meshes, each named `Pharaoh_<Section>` so no mesh shares a name with a bone (Roblox merges a same-named mesh and bone).
  - The materials are `Pharaoh_<Section>` on the 1024² base-colour maps.
  - The textures are embedded and also copied to `Pharaoh_Studio.fbm/`.
  - EyeGlow stays a separate mesh so Studio can set it to Neon.
- Export settings: `axis_forward='-Z', axis_up='Y'`.

**Previews:** `previews/GameClips.png` (Workbench, ¾ view; 4–6 frames per clip) and low-res Workbench `previews/CursedBolts.mp4` and `previews/TombEruption.mp4`.

### Motion discipline

These results are recorded in `exports/game/GameMotionChecks.json`.

- **Grip:** the right fist never opens, and the `Staff` bone never moves relative to the hand in any clip except Death, where it is released. The measured offset is 0 and finger rotation is 0.
- **Aiming:** attack poses are solved against the rig with capped joints. Only the shoulder (flexion, abduction, cross-body swing, humeral twist), elbow, wrist (capped at ≤ 18°) and torso move.
  - CursedBolts: the elbow flexes 32° at release, which is close to straight, and the wrist is 0°.
  - TombEruption: the wrist peaks at 17.9°. The left hand reaches across and closes on the shaft 0.95 studs above the right hand; the chest turns 30° to make that reach possible.
- **Feet:** planted feet are pinned by analytic two-bone leg IK. Drift is 0 in Idle, Hit and both attacks. In Walk, the planted feet move back at exactly `nominalSpeed`, so the world-space slip is ≤ 1e-6 studs per frame.
- **Loops and blending:** Idle and Walk close exactly. Hit and both attacks start and end exactly on the Idle start pose.
- **Ground:**
  - The planted staff foot rests on the sand; a 2° elbow lift seats it at z ≥ 0.006.
  - During TombEruption the foot is driven 0.03–0.07 studs into the ground while planted.
  - Walk carries the staff ≥ 0.84 studs clear of the ground.
  - Death stays within the ground rule: its lowest point over the whole clip is z = -0.01, and the final pose rests at z = 0.01.

### Validation

`validate_exports.py` passes 39/39. It re-imports the Studio FBX and checks the section meshes, triangle counts, materials, 1024 maps, the `.fbm` copy, bones against `AnimationData.json`, the absence of animation, and the weights. It then checks every clip's frame count, NaNs, bone coverage and loop closure, plus the attack timings and points in `BossGameData.json`.

### Not verified

- Studio import.
- The retarget receipt.
- In-game playback of the clips.
- VFX: the bolt gather and fan, and the hieroglyph circles.


## Verified in Blender (Blender 5.2.1 LTS, headless)

- The generator runs clean end to end (`build.log`).
- Silhouette IoU and the colour-probe table above come from the actual baked, posed render against the actual reference.
- `validate_exports.py` passes 26/26 on fresh re-imports of the FBX, both clip FBXs and the GLB. The checks cover:
  - section count, and every mesh under 20k triangles;
  - 62 bones with matching names and hierarchy, and no leaf bones;
  - every vertex weighted, ≤ 4 influences, normalised;
  - UVs present and textures loading;
  - split normals preserved;
  - both actions present with bone motion (the ReferencePose clip's arms rotated);
  - height in studs, and facing -Y.
- The ROM, attack poses and grip were inspected in renders.
- Grip contact and staff clearance were measured in four poses (`GripChecks.json`). These are sampled checks, not an exhaustive intersection proof across every ROM frame.

## Not verified

- Roblox Studio import, the 100× scale and bone-axis behaviour on import, and the in-game look (SurfaceAppearance, Neon eyes, lighting).
- Performance in the arena.
- Animations beyond the ROM and the three sampled attack poses. No gameplay clips (idle, walk, attacks, hit, death) were authored.
- Multi-client behaviour and published asset access.
- Deformation quality was inspected at the ROM key poses only, not in every in-between frame.

## Known differences from the reference

- **Chest.** The chest X straps are broader and softer than the reference's crisp straps. Less bare pec and six-pack shows between them, and the strips have some soft crumples where the reference's are perfectly flat.
- **Skull (after the skull pass).** The brows are still a little slimmer than the reference's, and the eye glow is partly shaded by the brow from above-eye-level views. The cheekbone blocks read slightly separate from the skull.
- **Uraeus.** Flatter, with less crisp hood and scute detail.
- **Right hand.** Deliberately changed. The reference shows three stacked finger bars with the thumb on top and a large foreshortened cuff; this uses a natural wrapped grip with a fitted cuff, at the user's request.
- **Left hand.** Slightly more closed and a little smaller than the reference's claw. The wrist wrap is thinner.
- **Kilt.** The gold chevron has no engraved V lines, and the hem teeth are more regular than the reference's torn edges.
- **Legs and feet.**
  - There are fewer crossing leg wraps.
  - The foot straps read more as ankle wraps than the reference's instep X.
  - The toes are more uniform blocks.
  - The left foot is slightly narrower than the reference.
- **Crook.** Band boundaries follow the reference's order, but the profile is slightly less tapered.
- **Scene.** The review scene is a plain sky and sand backdrop with no cliffs or obelisk, which is expected.
- **Hidden sides.** The back, sides and underside are authored continuations: back of the nemes and tail, back collar, kilt back, and wrap continuations.
