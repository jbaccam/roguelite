# Dragon boss (Volcanic Crater)

This folder holds a Blender rebuild of the supplied dragon reference, `source/4.webp`. The model is:

- a stylized low-poly quadruped in faceted crimson scale plates;
- a beige chevron plastron;
- charcoal obsidian horns, spikes, claws and tail spade;
- orange bat-wing membranes, with emissive lava seams and eyes.

It is skinned to a 90-bone deform rig and has five actions:

- `ReferencePose`;
- `RigTest_ROM`;
- the three boss attacks, `FireBreath`, `TailWhip` and `FrontStomp`.

It is exported as FBX and GLB.

Scale: 1 Blender unit = 1 Roblox stud. The model is authored at final size, faces −Y with Z up, and its origin is
on the ground under the body centre.

Nothing here is installed in Roblox Studio or wired into gameplay.

## Rebuild

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python build_dragon.py
python label_sheets.py                                  # captions on Turnaround / RigTest_ROM / AttackCheck
python compare_reference.py previews/Reference_Match.png _work/final_mask.png
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python validate_exports.py
```

The full build takes about 4 minutes on an RTX 2070 (Cycles OPTIX). Other entry points:

- `DRAGON_STAGE=probe` gives a flat-colour silhouette probe.
- `DRAGON_LOOP=1` stops after `Reference_Match`.
- `DRAGON_STAGE=previews` re-renders the review sheets from the saved `Dragon.blend`.
- `DRAGON_STAGE=attack DRAGON_ATTACK=TailWhip` rebuilds one attack in the saved `Dragon.blend`. It re-delivers only
  that clip FBX, the GLB, `manifest.attacks.<name>`, that attack's AttackCheck row and its mp4.
- `DRAGON_TEX` / `DRAGON_SAMPLES` / `DRAGON_FINAL_SAMPLES` set the texture size and the preview and final sample
  counts.

The `_work/` scratch folder is recreated on each build and deleted at delivery.

| File | Role |
| --- | --- |
| `make_reference_mask.py` | Builds `source/reference_mask.png` from colour zones, obsidian darkness rules, seeds and GrabCut. |
| `solve_camera.py` | Solves the reference camera into `source/camera.json`. |
| `dragon_camera.py` | Projection, back-projection and Blender camera settings. |
| `dragon_mesh.py` | SDF primitives (including the faceted `FacetBall` / `FacetCone`), surface nets, quickhull, thick sheets. |
| `dragon_rig.py` | Skeleton, numpy FK (matches Blender to 2e-5), head/wing/toe layout. |
| `dragon_design.py` | Every part in the rest pose. |
| `dragon_pose.py` | ReferencePose solve, ROM keys, attack actions and attack gameplay data. |
| `dragon_paint.py` | Painterly albedo from baked passes (no reference pixels). |
| `build_dragon.py` | The Blender generator: geometry, rig, weights, bake/paint, actions, renders, exports, manifest. |
| `compare_reference.py`, `calibrate.py` | IoU, colour probes and crops; folding probe ratios into `CALIBRATION`. |
| `fast_preview.py` | numpy silhouette preview (iteration only). |
| `label_sheets.py` | Caption bars on the contact sheets. |
| `validate_exports.py` | Fresh re-import checks; writes `validation-report.json`. |

## Provenance

The reference is the user's image, copied unchanged to `source/4.webp` (1536 × 1024, SHA256
`CD8ABD3A2B750906F0989BE291A6EE97732FDB4EBAA3234A8ACC884A12363006`).

No reference pixels are used in the model or its textures:

- Geometry is procedural.
- Colours are eyedropped values (`source/REFERENCE_NOTES.md`) times the fitted `CALIBRATION` gains.
- Every texture is painted in numpy from baked geometric passes.

No Creator Store assets are used.

## Camera and measurements

The painted verticals do not converge, but the horizon is low. `solve_camera.py` therefore solves:

- a **level camera with a vertical lens shift**;
- all four claw rows resting on the ground, as a mirror-symmetric stance with per-foot splay;
- the skull top anchored at z = 11 (brief).

The claw tips fit to 2.8 px rms at every focal length tried. f = 1150 px (27 mm on a 36 mm sensor) was chosen from
anatomy: it gives a front-to-hind stance of 10.7 studs, which fits the brief's 30-stud dragon.

- Camera: (10.92, −19.62, 1.56); yaw −24.7°; principal point v = 817.6 (Blender `shift_y` +0.199).
- Head: placed by a rigid 9-landmark fit, centred on the midline (19 px rms).
- Wings: each wing bone is aimed at its measured joint pixel. The reference raises the wings asymmetrically.

| Measure (studs) | Brief / reference | Rebuild |
| --- | --- | --- |
| Top of head (skull, ReferencePose) | ≈ 11 | ≈ 10.6 (the landmark fit puts the head a little lower and forward) |
| Raised wing tips | 16–17 | thumb tips 16.6 (near wing), 14.7 (far wing); highest point 16.7 |
| Nose to tail tip along the body | ≈ 30 | rest pose: 32.0 long overall (−9.0 to +22.9 in Y) |
| Rest bounding box (W × L × H) | — | 22.0 × 32.0 × 16.4 |
| Stance: front / hind claw rows | camera solve | (±5.5, −5.3) / (±5.85, 4.3) |
| Player / King Crab (for scale) | 5 / ~10 tall | the head is ≈ 2× player height; the dragon is ≈ 1.6× the crab |

## Model

| Section | Triangles | Contents |
| --- | --- | --- |
| Body | 18,370 | Faceted SDF skin: torso barrel, thick neck, pillar legs (shoulder or thigh mass → column → wide palm), tail. Also toe knuckle plates. |
| Head | 8,012 | Lumpy beveled chunks: snout, nose knob, heavy brows, cheeks and jowls, lips, crest, a three-block beige lower jaw, and 14 chunky faceted fangs (big corner tusks overlap the lips). |
| Wings | 7,636 | Seven-sided tapered beveled bones with knuckles. The membranes are closed thick sheets (0.16 studs), with scalloped, slightly ragged trailing edges. |
| Belly | 6,988 | 11 chest/throat chevron plates (roof-like midline crease, shingled) and 15 tail-underside plates. |
| Obsidian | 5,272 | Horns (2 big swept-back horns and 2 brow horns), 16 dorsal block spikes, 16 foot claws (blunt wedges), 6 wing claws, the crystal tail spade. |
| LavaGlow | 936 | Glow slivers at the spike roots and the glowing mouth interior (for Neon). |
| EyeGlow | 40 | Eyes (for Neon). |
| **Total** | **47,254** | Every mesh is < 20k tris. |

- **Faceting:** the body masses are intersections of tangent planes, so the facets are truly planar. Shading uses
  custom split normals from the SDF gradient, so facets stay flat and their edges read as soft bevels. The
  re-import check confirms the split normals survive the FBX.
- **Textures:** each section has a 2048² master (`*_BaseColor_2048.png`, packed in the .blend and embedded in the
  FBX) and a 1024² Roblox delivery map (`*_BaseColor.png`). The UV islands have 16 px bake margins. There are no
  normal maps.

## Rig

`Dragon_Rig` has 90 deform bones:

| Chain | Bones |
| --- | --- |
| Spine and head | `Root` → `Hips` → `Spine_1..3` → `Chest` → `Neck_1..3` → `Head` (with `Jaw`, `Brow_L/R`, `Eyelid_L/R`) |
| Front legs (per side) | `Shoulder` → `UpperArm` → `Forearm` → `Hand` → `Hand_*_Toe1..4_1/2` |
| Hind legs (per side) | `Thigh` → `Shin` → `Ankle` → `Foot` → `Foot_*_Toe1..4_1/2` |
| Wings (per side) | `Wing_*_1` → `_2` → `_3` / `_Thumb` / `Finger1_1/2` / `Finger2_1/2`, parented to `Spine_2` |
| Tail | `Tail_1..10` → `TailTip` (the spade) |

- **Symmetry:** L/R rolls are mirrored, and the rig has no leaf bones.
- **IK controls:** 8 non-deform bones (`IK_*` and `Pole_*`). The IK constraints are driven by the rig property
  `ik_legs` (default 0 = FK as keyed). Control bones are excluded from every export.
- **Weights:** every vertex has ≤ 4 normalised influences.
  - Horns, spikes, claws, spade, eyes and teeth are 100 % on one bone.
  - Body skin blends between neighbouring bones: soft ownership of the SDF primitives, then 4 graph-smoothing
    passes.
  - Membranes interpolate between their leading and trailing finger/arm chains, so they fold and spread without
    twisting.
- **Rest pose:** the reference spread, with the wings 12° lower and the fingers folded 14°; the head faces forward.
- **ReferencePose:**
  - rear body bent 30° left, with the chest held;
  - all four feet IK-planted onto the camera-solved claw rows;
  - far clavicle rotated in and back;
  - head turned 12.5° toward the camera and 17° nose-down;
  - wings aimed at the measured pixels.

## Actions

| Action | Frames at 24 fps | Content |
| --- | --- | --- |
| `ReferencePose` | 1–2 | Held reference pose. |
| `RigTest_ROM` | 1–369 | Each leg lifted, neck sweep L/R/up/down, fire-breath jaw, wings fold → spread → flap ×3, tail sweep L/R/up, toes curl/spread, 2 blinks. |
| `FireBreath` | 1–60, **Impact 25** | Head rears back and inhales (f1–16, jaw cracks, wings lift a little). The neck then strikes forward and low with the jaw wide open (f16–24). The breath is held f25–48 with a small left/right sweep, then he recovers. |
| `TailWhip` | 1–72, **Impact 27** | v2, "more butt into it". Wind-up f1–20: the hindquarters coil 32° to his right, the tail curls the same way and the wings lift clear. The fast swing, f20–31, pivots on the planted front legs: the hips yaw round to −46° while the hind feet hop round with the body. The tail straightens to full reach with the base leading and the spade trailing, then snaps through. Follow-through f31–38 reaches −48°, and the recovery f38–72 steps the hind feet back to the rest stance. |
| `FrontStomp` | 1–48, **Impact 27** | He rears on his hind legs (hips pitched 26°, root up 0.3), with the front legs up and folded and the wings flared. At f22–26 he slams both front feet down together, sole-flat; the body drops 0.4 and he recovers. |

Each attack has an `Impact` pose marker in the .blend. FBX and GLB do not carry markers, so the gameplay data sits
in `manifest.json` → `attacks`. It is given in Blender world studs (Z up, dragon faces −Y):

- **FireBreath:**
  - `FireOrigin` is on the `Head` bone at local (0, 1.952, −0.411), which is (0, −8.38, 8.65) in the rest pose.
  - `breath` lists the world origin and direction for every second frame of the hold (f25–48).
  - The direction is the bisector of the open jaws, e.g. (0, −0.746, −0.666) at f25. The flame comes down and
    forward and reaches the ground ~8 studs ahead.
- **TailWhip:** the spade sweeps **205°**, from −93.5° (f21, wind-up side) to +111.5° (f37, follow-through).
  - Angles are measured about the fitted pivot (1.86, 5.89) of the spade's path, about +Z from straight back,
    positive toward the dragon's left. About the rest tail base (0, 6.7, 6.1) the sweep is −97.0° to +111.8°
    (208.7°).
  - Radius: 16.6 fitted, 15.7–17.8 through the fast swing, 19.1 at most.
  - The spade point stays at 2.0–3.3 studs high; peak speed is 33°/frame at the impact frame.
  - The manifest also lists `hind_steps` (lift and land frames), `planted_intervals` and tip samples.
- **FrontStomp:** the impact points at f27 are the front toe centres (±5.29, −4.30) on the ground, with palms at
  (±5.20, −4.05, 0.70).

**Planted feet** are re-planted by IK at every key: every 2 frames, and every frame for TailWhip. They were measured on
the evaluated rig at every frame of each planted interval:

- **Drift:** 0.000 studs for FireBreath and TailWhip, and 0.005 for FrontStomp. The FrontStomp front feet count from
  impact on.
- **TailWhip steps:** the hind feet lift and re-plant between intervals, so they step instead of sliding.
- **TailWhip clearance:** a capsule check keeps the tail and spade at least 1.8 studs from the legs and 5 studs from
  the wings on every frame.
- **Joints:** all joint motion is bone rotation (plus the stomp's root lift and drop).

## Colour and silhouette (final Reference_Match, 128 spp)

`previews/Reference_Match.png` is rendered from the posed, skinned rig (`ReferencePose` action) at 1536 × 1024 in
the solved camera. Lighting:

- a warm key sun from camera-left;
- lilac sky fill;
- an orange rim;
- a grey-mauve ground plane and a flat dusk backdrop ("Standard" view transform).

**Silhouette IoU: 0.852** (target 0.92, not reached).

| Probe | Reference sRGB | Render sRGB | Worst channel |
| --- | --- | --- | --- |
| Belly plates | 189, 127, 83 | 182, 124, 81 | 9 % |
| Jaw | 192, 127, 80 | 184, 123, 79 | 10 % |
| Wing bones | 142, 52, 48 | 138, 49, 46 | 16 % |
| Membrane | 197, 86, 41 | 200, 88, 47 | 20 % (blue) |
| Tail skin | 153, 51, 45 | 169, 58, 45 | 22 % |
| Obsidian claws | 73, 46, 51 | 79, 56, 61 | 29 % |
| Obsidian horns | 80, 63, 73 | 75, 53, 62 | 38 % |
| Head skin | 179, 63, 52 | 174, 51, 43 | 54 % |
| Body skin, lit | 170, 55, 50 | 146, 44, 45 | 54 % |
| Body skin, shade | 121, 39, 37 | 112, 29, 28 | 66 % |

Ratios are per channel in linear light. The red skin is still too saturated and dark in G/B (the reference's red is
warmer and greyer), and the horns are too dark.

## Compare-pass log

| Pass | Change | IoU |
| --- | --- | --- |
| P0 | Mask, camera solve (level + shift, f 1150). | — |
| P1 | numpy blockout, fast preview. | 0.767 |
| P2 | Blender pipeline; lens-shift sign fix. | 0.769 |
| P3 | Wings re-interpreted (long forearm, panel to the flank, pixel-aimed bones, 2^7 search). | 0.80–0.82 |
| P4 | Rest wing = the measured spread, relaxed. | 0.836 |
| P5 | Faceted SDF masses, SDF-gradient facet normals. | 0.845 |
| P6 | Texture bake/paint pipeline; lighting fixed; spikes, glow, spade and plates rebuilt. | 0.845 |
| P7–P9 | Head refits, neck, throat plates, pillar legs, plastron widened. | 0.85–0.86 |
| P10–P12 | Toes and claws, front-foot IK plant, far-clavicle pose, crystal spade, horns, wing bones, two calibration passes, mottled red. | 0.852 |
| Final | Coordinator wrap-up. | 0.852 |
| User polish | Bigger teeth; attack kit replaced with FireBreath, TailWhip and FrontStomp. | 0.852 |
| TailWhip v2 | Hip swing, hind-foot stepping, 205° spade arc. Updated with `DRAGON_STAGE=attack DRAGON_ATTACK=TailWhip`, which re-delivers only the clip, the GLB, `manifest.attacks.TailWhip`, the AttackCheck row and the mp4. | 0.852 |

## Deliberate deviations (animation-friendly construction)

- **Head:** turned by the rig (Neck and Head bones), not modelled twisted. The rest head faces straight ahead. The
  jaw hinges on `Jaw`, which opens 40° for the breath.
- **Wings:** the rest wing is a relaxed version of the reference spread, so ReferencePose, fold, spread and flap
  are small clean rotations. The far wing uses the same bones aimed at its own pixels; the reference raises it
  differently.
- **Feet:** toes are fanned hinge chains with claws rigid on the last segment; feet are planted by IK. The far
  front leg's clavicle is rotated in and back to match the reference lean, instead of modelling an asymmetric
  body.
- **Scale:** the head top sits at ≈ 10.6, not 11. The camera/landmark fit places the head slightly forward and
  lower; the whole model was not rescaled to force 11.

## Remaining known differences from the reference

- **Silhouette (0.852):**
  - The far (dragon's right) wing's upper edge and fingertip claws are thinner and lower.
  - The horns are narrower. The big horn tips land ~70 px from the reference's: the reference horns sweep back
    further than a rigid head in this camera allows.
  - The far front leg is still slightly wide at the top.
  - The tail spade is oriented ~40 px off.
  - The lower belly and far hind leg region differs.
  - The claws are a little smaller than the painted ones.
- **Colour:** the red skin is more saturated and darker than the reference. The obsidian on the horns reads darker
  and less lilac. There is no painted background: the render uses a flat dusk backdrop and a flat floor.
- **Head:** the painted head has more small lumps, and a brighter orange-lit nose top. The eye is smaller and less
  almond-shaped. The rebuilt head is somewhat smaller in frame.
- **Belly plates:** narrower than the reference plastron on the lower belly. The reference plates have more
  pronounced dark seams.

## Verified in Blender

- The generator runs clean headless (Blender 5.2.1 LTS).
- `validate_exports.py`: **34 / 34 checks pass** (`validation-report.json`). It re-imports the FBX, all five clip
  FBXs and the GLB fresh, and checks:
  - 7 sections, each < 20k tris;
  - 90 deform bones with names and hierarchy matching the manifest, and no leaf/control bones;
  - every vertex weighted, ≤ 4 influences, normalised;
  - UVs present and embedded textures loading;
  - split (faceted) normals preserved;
  - dimensions in studs and axes preserved;
  - ReferencePose differs from rest, and the ROM and attacks move the bones;
  - GLB carries all 5 actions;
  - the manifest attack data is present;
  - planted-foot drift < 0.05 studs.
- Blender FK matches the numpy skeleton to 2e-5. Silhouette IoU and colour probes come from the actual render
  versus the actual reference.
- Review renders were all inspected:
  - `previews/`: Reference_Match, Comparison_*, Crop_*, Turnaround, Rig_Bones, RigTest_ROM, AttackCheck,
    Head_Closeup;
  - `Attack_*.mp4`: Workbench, 640 × 360.

## Not verified

- **Roblox Studio:** import, in-engine look and scale, Neon on the glow sections, and whether the attack clips
  retarget correctly onto the imported rig.
  - Known FBX gotchas from `../mob-production/combat-ready/README.md` apply: 100× import scale, and bone-local axes
    that differ after import.
  - The exports use `axis_forward='-Z'`, `axis_up='Y'`, `apply_unit_scale`, `FBX_SCALE_NONE`,
    `add_leaf_bones=False` and deform bones only.
  - The armature-only clip FBXs carry no bind pose; their node rest equals the exported frame. Retarget them by
    bone name against `Dragon.fbx`, as the combat-ready kit's `retarget_studio.py` does.
- **Motion beyond the sheets:** deformation under motion beyond the rendered ROM, AttackCheck frames and videos.
- **Collisions:** interpenetration was checked by eye in those renders only, not by a collision test.
- **Gameplay:** hitboxes and timing.

## Outputs

| Kind | Files |
| --- | --- |
| Blend | `Dragon.blend` (packed textures, `REVIEW_ONLY` collection with the camera, lights and ground) |
| FBX | `exports/fbx/Dragon.fbx`, plus `Dragon_ReferencePose.fbx`, `Dragon_RigTest_ROM.fbx`, `Dragon_FireBreath.fbx`, `Dragon_TailWhip.fbx`, `Dragon_FrontStomp.fbx` |
| GLB | `exports/glb/Dragon.glb` |
| Textures | `textures/` |
| Previews | `previews/` |
| Reports | `manifest.json`, `polygon-report.json`, `validation-report.json` |
| Source | `source/` (reference, mask and review, `camera.json`, `REFERENCE_NOTES.md`) |
