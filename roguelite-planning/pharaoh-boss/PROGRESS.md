# Pharaoh boss: progress log

Agent working file. It lets the build resume if a session is cut off. The
README is the deliverable.

## State (update after every pass)

- **Pass:** 1 (blocking done; now the refinement loop)
- **Silhouette IoU:** 0.879, from `_work/probe.png` vs `source/reference_mask.png`.
- **Colour probes** (reference sRGB vs render, worst channel %):

  | Probe | Reference | Render | Worst channel |
  | --- | --- | --- | --- |
  | Skin | 128/117/85 | 134/117/84 | 4.7 % |
  | Bandage | 206/177/139 | 211/173/128 | 7.9 % |
  | Gold | 194/142/61 | 202/142/70 | 14.8 % |
  | Blue | 62/78/122 | 73/81/122 | 17.7 % |
  | Brown | 148/101/45 | 151/93/40 | 11.1 % |
  | Bone | — | — | 25 %, box contaminated by dark sockets and neck |

## Done

- **Reference study.** The reference is copied to `source/`. Also in `source/`:
  - `reference_mask.png`, from `make_reference_mask.py` using GrabCut;
  - `REFERENCE_NOTES.md`;
  - `camera_solve.json`, from `camera_solve.py`: f = 2232 px, lens 55.5 mm, camera at (-0.07, -24.0, 3.24), pitched up 7.06°.
- **Generator** `build_pharaoh.py`, run with `STAGE=sculpt`. It builds:
  - the metaball body with a conform pass under the garments, and soft-facet custom normals;
  - the skull, carved with booleans;
  - the nemes: striped wing bands, dome, lappets, back flap and tail;
  - the uraeus;
  - the collar tiles;
  - the belt, medallion and gem;
  - the kilt: traced panels on a cone proxy, meshed by CDT;
  - the staff: shaft bands, the crook as a mitred sweep, and the foot block;
  - the ankle bands, left bracer and right cuff;
  - both hands and both feet;
  - the bandage ribbons: limb helices and torso sash loops.
- **Comparison** `compare_reference.py`: side-by-side, overlay, silhouette, crops and probes.

## Open discrepancies (next passes)

1. **Colours.** Skin should read cool olive grey-green. Bandages should be clean cream with cool grey shadows. Bone should be greyer. Calibrate once the lighting is stable.
2. **Eyes.** Add the glow: a white-cyan core plus a cyan halo in dark sockets.
3. **Skull.** Make the V brow heavier, the cheekbones stronger and the teeth larger; give the uraeus hood relief.
4. **Left bracer.** It should sit higher and be a bit shorter, with a bandaged wrist visible below it before the hand.
5. **Viewer-left shoulder.** It needs a defined bandaged deltoid, not a lumpy mass. Check the torso yaw.
6. **Collar.** Widen the blue ring (more blue), and use rounder outer arcs.
7. **Bandages.** Make them wider and more numerous, matching the reference wrap patterns; add the torn shoulder flap.
8. **Kilt.** Make the hem teeth more irregular and check the cream strip shapes.
9. **Rig and export (not started).** Armature, weights, ReferencePose/RigTest_ROM, bake, exports, validate.

## Commands

    cd roguelite-planning/pharaoh-boss
    STAGE=sculpt "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python build_pharaoh.py
    #   VIEWS=1 also renders _work/view_*.png, orthographic front/side/back/3-4
    python compare_reference.py _work/probe.png _work/probe_mask.png _work/cmp

Patches are applied through small scripts in `_work/` (`patch*.py`, `chunk_*.py`).
The generator itself is always left runnable.

## Pass log

- **Blocking pass.** Every part was built. IoU went 0.63 (body only) → 0.87 → 0.879.
- **Pass 1.**
  - Body: metaballs replaced by faceted masses unioned with a voxel remesh.
  - Bandages: taut ribbons with a relaxed height field; tilted-ring wraps.
  - Chest: sash loops at the measured height.
  - Face: eye glow core plus halo; heavier brow; bigger teeth.
  - Collar: wider blue ring.
  - Cleaner cream bandage colour and cooler skin; two-tone backdrop.
  - IoU 0.895.
- **Full pipeline (probe) working.** Armature, heat and transfer weights, sections, bake, rest spread 9°, ReferencePose, and Reference_Match rendered from the posed rig.
  - Section tris: Body 16.2k, Bandages 16.5k, Head 14.0k, Waist 19.0k, Staff 2.2k, EyeGlow 0.2k.
  - Now reducing the total toward 60k.
- **Full pipeline run OK** (`STAGE=full`, about 90 s).
  - **Outputs:**
    - `Pharaoh.blend`;
    - exports: FBX, the two clip FBXs, and GLB;
    - previews: Turnaround, Face_CloseUp, Rig_Bones and RigTest_ROM;
    - `manifest.json` and `polygon-report.json`.
  - **Rig:** 62 deform bones.
  - **Tris per section:**

    | Section | Tris |
    | --- | --- |
    | Head | 12.9k |
    | Bandages | 16.5k |
    | Body | 14.2k |
    | Waist | 12.9k |
    | Staff | 2.2k |
    | EyeGlow | 0.2k |
    | **Total** | **58.9k** |

  - **Validation:** 21/26 checks passed.
    - Fixed in the validator: the ReferencePose check (it now looks for a held pose), the GLB `Icosphere` bone shape, and GLB motion sampling.
    - Fixed in the generator: export frame ranges, and degenerate geometry cleaned per section.
    - These fixes have not yet been re-run.
  - **Colour:** CALIBRATION pass 2 applied (gains from the baked render).
- **Pass 2 (detail) in progress:**
  - eyes: almond core plus halo, set at the socket front;
  - sockets: rounder;
  - bone: greyer;
  - uraeus: relief rebuilt;
  - fist: compacted, thumb lowered;
  - cuff: smaller and centred;
  - left hand: wraps over the back of the hand;
  - feet: bigger toes, wraps on a vertical axis.
  - Zoom tool: `ZOOM=face,fistR,handL,feet STAGE=sculpt ...`, then `python _work/zoomcmp.py face ...`.

## Next steps

1. Check the feet and fist zooms, then do one full build.
2. `python compare_reference.py previews/Reference_Match.png _work/ref_match_mask.png` (outputs go to previews/).
3. Run `blender -b --factory-startup --python validate_exports.py`.
4. Update CALIBRATION from the probe ratios and repeat compare passes until IoU ≥ 0.92 and every channel is within ~8 %. The main IoU losses are the torso and shoulder widths, the kilt hem and the feet.
5. Write the README, then delete `_work/` at the end (keep nothing needed there).
- 04:02 GPU: full build with new natural hands + attack check sheet

- **User PRIORITY done: natural hands.**
  - **Right fist:**
    - `solve_right_grip` derives the wrist so the hand stays in line with the forearm.
    - The palm is on the outer side of the shaft.
    - The four fingers are continuous blocky curved tubes round the shaft, with inner faces sized to shaft corner radius + 0.022.
    - The knuckle row is staggered by start angle, and the thumb closes over the index.
    - Finger weights are preset along the joint chains.
    - The Staff bone head sits at the tunnel centre.
    - The cuff is fitted round the forearm behind the wrist.
  - **Left hand:** palm loft continuous with the wrist, four spread, gently clawed fingers, and a separate thumb.
  - **`previews/AttackCheck_Staff.png`:** rest, overhead, slam and thrust poses, each with a grip close-up. The poses are solved against the rig with anatomical ranges and saved to `AttackPoses.json`.
  - **`GripChecks.json`:**
    - finger surface clearance +0.022 on all four fingers;
    - finger drift in the Staff frame 2e-6;
    - no staff vertex inside the body in any pose;
    - min staff-to-body distance 0.84 / 2.80 / 0.84 / 0.85.
  - The ROM now uses the solved staff poses, and the Staff bone is never rotated relative to the hand.
- **Silhouette pass (sculpt IoU 0.9219).**
  - Staff axis refit to the reference shaft centres (least squares, rms 1.8 px).
  - Crook retraced as a coarse faceted sweep with the reference band order G B G B G B G.
  - Back tail traced so it shows between the legs.
  - Deltoids placed in world space.
  - Lats are asymmetric (the torso is yawed).
  - Left arm and hand widened and shifted.
  - Fixed `fill_unweighted`.
  - Actions are bound through their slots (bind_action), which fixes the empty ReferencePose clip.
  - Next: full build, validation, colour probes, README.
- **Detail pass.**
  - Bandages: taut across the width (upper hull); darker edge line painted along every strip.
  - Deltoid wraps: sleeve around the deltoid ball.
  - Collar: rounded U.
  - Skull: faceted sections, chunkier V brows, cheek plates, tighter mouth.
  - Full-build IoU before this pass: 0.921. Validation 26/26. All colour probes within 8 %.
- 04:48 ROM overhead uses the solved right-arm pose (no staff through the head). Next: final build, README, cleanup.
- 04:56 Deterministic rock jitter (crc32, not hash()); ROM elbows limited to 0-130 deg total flex; left-hand scale test reverted (1.0). Final full build next, then README.

## FINAL (complete)

- **Final full build.**
  - IoU 0.921.
  - Every colour probe within 8 % (worst: gem 7.8 %).
  - Validation 26/26.
  - GripChecks: finger clearance +0.022; drift ≤ 3e-6; no staff-in-body in any of the four poses.
- **Cleanup.** The README is written. `_work/` and `Pharaoh.blend1` are deleted. `_work` is regenerated by `STAGE=sculpt` runs.
- **Remaining known differences:** see the README.
