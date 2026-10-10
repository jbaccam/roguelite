# Tomb Warden: Desert Basin round-10 elite

A gorilla-built giant mummy, 10.20 studs tall (1 Blender unit = 1 stud), made procedurally. This is the third model pass: the v2 proportions scaled to designScale 1.18, with the wraps, shoulder cloth, belt, fists and mask reworked to match the sheet.

- **Build.** Massive upper body, raised traps, no visible neck. Legs are about 35% of his height, and the long arms hang the fists near the knees.
- **Wraps.** Wide bandage bands, one main diagonal direction per body part with a few crossing bands in broad patches. Each band is cream or sand, with sandy mottling, tea-brown stains and one clean overlap edge (a shade line under the band above). There is no fine line network.
- **Shoulders.** Torn linen strips hang from a short collar over each shoulder, four per side, with ragged ends that stand proud and darken.
- **Teal cloth.** A wide sash crosses from his left shoulder to his right hip. A separate darker belt wraps the waist, and a long torn front flap with folds hangs to the knees (plus a back flap). All of it is weathered: dye patches, faded blooms, sand dust heavier at the hem, grime stains and worn lighter edges.
- **Fists.** Stone fists with four separate blocky curled fingers, knuckle ridges, a thumb pressed over the fingers, and the Greek-key spiral carved on the back of the hand. The back of the hand faces outward, and the thumb and index finger face forward. They are chipped terracotta, each rigid on one bone.
- **Mask.** A solid carved stone block covers the face with glyph relief. The upper corner on his left is broken away, and his left eye glows in the dark gap. His right eye shows as a narrow carved slit. `EyeGlow` is a separate mesh, ready for Neon.

**Status: Blender-verified, Studio untested.** Nothing was imported into Roblox Studio.

## Files

| Path | What |
| --- | --- |
| `build_tomb_warden.py` | The generator: `blender -b --factory-startup --threads 4 --python-exit-code 1 --python build_tomb_warden.py` (about 105 s). `TW_STAGE=shape` builds geometry and rig with flat colours; `TW_STAGE=motion` adds clips and checks without the bake. `TW_SC` (default 1.18) is the design-to-stud scale. |
| `tw_sdf.py`, `tw_design.py` | SDF sculpting and surface nets. Also the joints, skeleton, body/cloth/wrap regions, fists, mask, shoulder strips, and the old coffin profile. Authored about 8.6 tall and scaled by `SC` at the Blender boundary. |
| `tw_motion.py`, `tw_solve.py` | Numpy FK and two-bone IK, the eight clips, and the solves (coffin start pose, fist ground and chest contacts, Death ground rest). |
| `tw_paint.py` | Painterly albedo from baked passes (position, normal, AO, bevel edge, facet). |
| `tw_deliver.py` | Actions, per-frame checks on Blender-evaluated meshes, game JSON, Studio FBX, previews. |
| `validate_exports.py` → `validation-report.json` | Fresh re-import of the Studio FBX plus data checks: **PASSED**. |
| `TombWarden.blend` | Rig, six sections, eight actions, and a `REVIEW_ONLY` collection (camera, lights, ground, the regular mummy for scale, and the fourth-pass coffin imported read-only from `round10-props/exports/Sarcophagus.fbx`: body 4.9 behind the final spot, lid fallen open in front). |
| `exports/game/` | `TombWarden_Studio.fbx` (+ `.fbm/TombWarden_BaseColor.png`), `AnimationData.json`, `BossGameData.json`, `GameChecks.json`. |
| `textures/` | `TombWarden_BaseColor.png` (1024² shared atlas) and its 2048² master. |
| `previews/` | Front, Back, Side, ThreeQuarter, Hero, `Comparison_Reference.png` (sheet panel 1 beside ThreeQuarter), GameClips, Attack_FistSlam, Attack_FistHook, Emerge (the real fourth-pass coffin body and open lid as wireframe). |
| `manifest.json` | Sections, triangles, bones, texture and export hashes. |

## Provenance

- Reference: `art-references/round-10-modeling-pack-2026-10-09/04-tomb-warden.png`, copied to `source/TombWarden_reference.png` (SHA256 `BBF190E20574356C4495B4B1017185374EC1118342FF1F8C0A1993007952D86C`).
- Geometry is procedural (signed-distance sculpt, surface nets, decimation). Textures are painted in numpy from baked geometric passes; no reference pixels are used.
- The palette is warm and saturated because Studio's blue sky cools pale tones. Previews use a blue-sky fill (0.55, 0.70, 0.95) with a warm sun.

## Model

| Mesh | Tris | Skinning |
| --- | --- | --- |
| `TombWarden_Body` | 7600 | skinned, ≤4 influences (shoulder strips, sash and belt are raised regions of this mesh) |
| `TombWarden_Cloth` | 1032 | front/back flaps on `SashFront1/2`, `SashBack1/2`, top on `LowerTorso` |
| `TombWarden_Mask` | 1300 | rigid `Head` 1.0 |
| `TombWarden_LeftFist` / `RightFist` | 1798 / 1798 | rigid `LeftHand` / `RightHand` 1.0 |
| `TombWarden_EyeGlow` | 200 | rigid `Head` 1.0 (set to Neon) |
| **Total** | **13728** | |

| Measure | Value |
| --- | --- |
| Height | 10.196 |
| rootHeight | 3.835 |
| footprintRadius | 4.774 |
| bodyCentreHeight | 5.246 |
| designScale | 1.18 |

**Bones (32, all deform).**

- Main chain: `Root` (zero weight) → `HumanoidRootPart` → `LowerTorso` → `UpperTorso` → `Head`.
- Arms, per side: `<Side>Shoulder` (clavicle helper) → `UpperArm` → `LowerArm` → `Hand`.
- Legs, per side: `UpperLeg` → `LowerLeg` → `Foot` → `Toes`.
- Cloth: `SashFront1/2`, `SashBack1/2`.
- Half-rotation helpers: `<Side>UpperArmHalf`, `<Side>LowerArmHalf`, `<Side>LowerLegHalf`, `HeadHalf`.

How the helpers and weights work:

- Each half helper is keyed to half its limb bone's rotation, and blend zones are split parent | helper | child.
- `Shoulder` takes 60% of the arm swing (capped at 78°) and the coffin shoulder roll.

## Clips (24 fps, timings unchanged)

| Clip | Duration | Key times |
| --- | --- | --- |
| Idle (loop) | 3.000 | Frame 0 = rest. |
| Walk (loop) | 1.167 | strideLength **5.4**, nominalSpeed **4.63** studs/s. Feet IK-planted, heel roll, heavy bob and sway, fists swing. |
| Hit | 0.458 | Returns to the Idle start. |
| Death | 2.208 | Knees, onto the fists, prone. |
| Emerge | 2.583 | Root travels 4.9 (emergeOut). eyesWake 0.5; steps 0.67–1.04 (R to the front of the cavity floor), 0.96–1.54 (L over the rim to the ground), 1.46–1.83 (R down beside it); warn 1.583, impact **1.917**. |
| FistSlam | 1.917 | warn 0.167, top 0.71, impact **1.083**, recovery end 1.875 |
| FistHook | 1.292 | warn 0.125, impact **0.583**, active to 0.708, recovery end 1.208 |
| Roar | 1.583 | Chest pounds 0.542 / 0.792, enrage. |

**Walk speed for the game.** The feet stay planted up to 2.6× playback, which is 2.6 × 4.63 = 12.0 studs/s. At chaseSpeed 12, playback is 12 / 4.63 = 2.59×.

**Impact points.** Root space, Blender axes. Studio vectors are also in `BossGameData.json`.

| Clip | Point | Position |
| --- | --- | --- |
| FistSlam | SlamCenter | (0, −6.58, 0) |
| FistSlam | Left / RightFist | (±1.52, −6.58, 0.02) |
| FistHook | HookFist | (−0.39, −6.39, 4.07) |
| FistHook | HookMid | (−0.79, −4.35, 4.88), capsuleRadius 1.003, per-frame `sweep` |
| Emerge | EmergeCenter | (0, −2.71, 0) |
| Emerge | Left / RightFist | (±3.15, −2.71, 0.02) |

Emerge positions:

- `emergeOut` = 4.9. `rootStart` = (0, 4.9, 0.8): the cavity floor centre, 0.8 above ground.
- `coffinOrigin` = (0, 4.9, 0).
- `rootEnd` = the origin.
- The fist points are unchanged by the longer travel, because they are measured from the final spot.

## Emerge start pose and the cavity it needs

The start pose has the arms folded high and tight on the chest: the right fist is at the left shoulder and the left fist is high on the right pec. The shoulders are rolled forward (about 57°) and up (24°), the feet are together, and the head is bowed and turned slightly away from the top fist.

**Start-pose bounds** (final-spot space): min (−3.14, 0.98, 0.79), max (3.20, 6.02, 10.97). That is 6.34 wide × 5.05 deep × 10.18 tall.

**`requiredCavity`** (in `GameChecks.json` → `coffinFit`):

- Measured in cavity space: the origin is the root start (cavity floor centre), +X is his left, −Y is the open front, and Z is height above the cavity floor.
- Each value is the start pose plus 0.12 clearance, in 0.5-stud bands.
- Overall: height **10.29**, depth **5.29** (front −2.64, back +2.64), max half-width **3.32** (6.64 wide).

| Height above floor | Half-width | Front Y | Back Y | Depth |
| --- | --- | --- | --- | --- |
| 0.0–0.5 | 1.86 | −0.87 | 1.98 | 2.86 |
| 0.5–1.0 | 1.88 | −0.49 | 1.98 | 2.47 |
| 1.0–1.5 | 1.98 | −0.34 | 1.89 | 2.23 |
| 1.5–2.0 | 2.15 | −1.14 | 1.88 | 3.02 |
| 2.0–2.5 | 2.16 | −1.10 | 2.64 | 3.74 |
| 2.5–3.0 | 2.34 | −1.06 | 2.61 | 3.67 |
| 3.0–3.5 | 2.43 | −0.98 | 2.53 | 3.51 |
| 3.5–4.0 | 2.44 | −0.90 | 2.46 | 3.36 |
| 4.0–4.5 | 2.29 | −0.86 | 2.40 | 3.25 |
| 4.5–5.0 | 2.79 | −2.03 | 2.33 | 4.35 |
| 5.0–5.5 | 3.11 | −2.38 | 2.31 | 4.69 |
| 5.5–6.0 | 3.14 | −2.41 | 2.44 | 4.85 |
| 6.0–6.5 | 3.20 | −2.46 | 2.49 | 4.95 |
| 6.5–7.0 | 3.32 | −2.51 | 2.57 | 5.08 |
| 7.0–7.5 | 3.25 | −2.54 | 2.64 | 5.19 |
| 7.5–8.0 | 3.32 | −2.64 | 2.63 | 5.27 |
| 8.0–8.5 | 3.28 | −2.63 | 2.58 | 5.21 |
| 8.5–9.0 | 3.20 | −2.58 | 2.38 | 4.95 |
| 9.0–9.5 | 2.99 | −2.51 | 1.93 | 4.44 |
| 9.5–10.0 | 2.73 | −2.45 | 1.65 | 4.10 |
| 10.0–10.5 | 1.05 | −1.46 | 1.22 | 2.68 |

The JSON also has `minX` and `maxX` per band; the pose is not symmetric because the arms are folded.

Two further constraints for the coffin builder:

- **Idle back.** At the final spot his back reaches y **+1.68** (`idleBackYFromFinalSpot`). The coffin's front face must sit at y ≥ 1.80 in final-spot space, or he overlaps it after stepping out. With the fourth-pass coffin at emergeOut 4.9, the front rim face is at +2.00.
- **Front opening.** He steps out through the front, so the opening must be at least as wide as the bands above.

## Emerge against the rebuilt coffin (fourth pass)

The coffin is checked against the real mesh, `round10-props/exports/Sarcophagus.fbx`, imported read-only.

- **Placement:** the body sits with its origin 4.9 behind the final spot. The lid is fallen open about its hinge: rotated 90° about X at coffin-space y −4.157, flat on the ground in front, top 1.257 high.
- **Method:** signed distance (BVH nearest point plus a ray-parity inside test) for every evaluated vertex of all six meshes, every frame (63 frames).
- **Start pose:** unchanged, identical to the one the cavity was built from.
- **Footfalls:** clean, with 0.00001 planted drift.
  - The right foot steps to the front of the cavity floor (ball just behind the rim).
  - The left foot swings over the rim. It stays above floor height until its heel clears the rim, then lands on the ground at the final spot.
  - The right foot follows it down.
  - The fists plant at 1.917, and the clip length is unchanged.
- **Arms:** the arm keys were re-tuned so the elbows stay inside the rim while unfolding, without pressing into the belly.

| Clearance (studs, negative = inside the stone) | Value |
| --- | --- |
| Walls, rim and ceiling, every frame | **+0.050** minimum (frame 30, his right shoulder passing the rim edge) |
| Overall, every frame | −0.029 (frame 31): the right sole standing on the cavity floor, which is contact (−0.010 in the start pose) |
| Gate | body ≥ −0.03 every frame: **PASSED** |
| Open lid | **−0.60** (frames 31–62), see below |

**The open lid cannot be cleared by any root path that ends on the ground.**

- The fallen lid is a slab whose top is 1.257 above the ground, and it covers final-spot y +0.74 to −12.76.
- The final spot (4.9 in front of the cavity centre, 2.0 past the rim) is on it.
- Emerge ends in the Idle pose with the feet on the ground (root at the origin), so from frame 31 on, the landing feet and the planted fists sit inside the slab. −0.60 is the deepest a point can read inside a 1.257 slab.
- The same applies to everything that walks there afterwards, since the open lid is non-colliding in `Round10Service`.
- **Fix on the game side:** lower the open lid by 1.257 so its top is flush with the ground (or swing it clear of the exit path). The body numbers above do not change.
- This is also recorded in `GameChecks.json` → `coffinFit.lidNote`.

## Checks (worst values; `exports/game/GameChecks.json`, every frame, Blender-evaluated meshes): **PASSED**

| Check | Result |
| --- | --- |
| Hinge (knee/elbow) | 1.19° to 130.8°, no negatives |
| Twist | ≤ 50° (Emerge unfold) |
| Max bone change per frame | 44.7° (FistHook RightUpperArm) |
| Ground | −0.047 (FistSlam) |
| Planted-foot drift | 0.000 |
| Loop closure / Idle start-end | 0.0 error |
| Fist / arm-on-arm / forearm through body | 0.000 / 0.023 / 0.033 (tolerance 0.05) |
| Joint sections | ≥ 0.853 (Emerge neck in the start pose); FistHook elbow 0.863; hips ≥ 0.855 |
| Body volume | 0.880 to 1.039 of rest |
| Strike reach | FistSlam 0.960, FistHook 0.960, wrist bend 0° |
| Fresh re-import | 6 meshes, 32 bones match AnimationData, weights normalised ≤4, rigid parts single-bone, 1024 maps, no name clashes: **PASSED** |

**Section-metric changes this pass, with reasons.** No gate value changed.

1. **Cut points, not whole triangles.** The section now keeps every cut point within the joint radius, instead of only triangles lying wholly inside it.
   - Why: with the wider, smoother bands, the decimator left long triangles behind the knee. They fell outside the radius, so the rest slice of the left knee lost a quarter of its outline (rest areas L 3.07 vs R 2.49; now 3.19 vs 3.21).
   - Effect: the walk knee read 0.78 under the old rule and 0.90 under the new one. The posed areas are unchanged; only the rest reference was wrong.
2. **The neck takes the whole trap ring.** It uses radius 1.6 on the chest/head bisector, instead of radius 0.9 on the head axis.
   - Why: the gorilla build has no neck. At the head joint the surface is the trap mass, so the old slice caught only a front sliver (rest area 0.46), and its size swung with the plane's tilt.
3. **Elbow radius 0.95 → 0.80** (the forearm radius 0.66 plus relief).
   - Why: the hanging elbow sits 0.13 from the flank, and the smooth union fuses them at rest, so part of the flank counted as elbow at rest only.
   - Effect: small. The rest area went from 2.30 to 2.25, and the hook elbow from 0.83 to 0.86.

## Known issues

- **Open lid:** the final spot is on the fallen lid (top 1.257 above ground). See the Emerge section; it needs a game-side change.
- **Slam fist speed** peaks at frame 22 (the overhead arc), not at contact (frame 26).
- **Tightest passing values:** the Emerge neck section (0.853 in the folded start pose), the FistHook per-frame bone change (44.7° of a 45° gate), and the right sole on the cavity floor (−0.029 against a −0.03 contact gate).
- **Differences from the sheet** (`Comparison_Reference.png`):
  - The sheet's mask sits lower, between the traps, and its glyph is one big "R" shape.
  - Our wraps read lighter under the preview sun, and the sheet's tan bands are browner.
  - The sheet's front flap is a muted grey-teal; ours is a little brighter.
- **Studio untested:** the 32-bone rig, Neon EyeGlow and root motion in the Roblox importer are unverified.
