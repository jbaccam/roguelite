# King Crab boss — progress log (resume point)

Folder: `roguelite-planning/king-crab-boss/`. Blender: `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python build_king_crab.py` (headless only; never the live Blender/Studio).

## State (pass 16) — the claw "gem" rewrite is long done; the full pipeline runs end to end

Done
- `source/king-crab-reference.webp` copied unchanged (SHA256 575CB191…A7C261 verified).
- `make_reference_mask.py` -> `source/reference_mask.png` (GrabCut + seeds; checked in zoomed crops).
- `solve_camera.py` -> `source/camera.json`: f = 1900 px (44.53 mm / 36 mm sensor), camera (-5.68, -30.67, 5.78), yaw 10.07°, pitch -2.17°, body roll 5.86° (right side up) about z = 5.
- `build_king_crab.py` (full mode, ~80 s): builds all parts, armature (Root/Body/eyes/brows/maxillipeds/claws/legs), ReferencePose action, ray-cast chips, per-section calibrated paint, joins 5 sections (Body, Eyes, ClawR, ClawL, Legs), smart-UV, bakes 2048 EMIT masters + 1024 delivery maps, final Principled materials, renders previews/Reference_Match.png (posed baked rig), Face_Closeup, Turnaround, Rig_Bones, RigTest_ROM sheet, exports FBX (mesh+rig, 2 clips) + GLB, writes manifest.json, polygon-report.json, saves KingCrab.blend (packed, REVIEW_ONLY collection).
- Probe mode (`KC_MODE=probe`) renders the unbaked posed rig + mask + ID pass + clay pass in ~10 s.
- Compare loop on the baked rig: `bash _work/loop.sh` (KC_STOP_AFTER_MATCH=1 + compare_reference.py).
- `calibrate.py` folds probe ratios into CALIBRATION (per material_section).
- Legs now fitted by least squares (`plan_legs`): shared lengths per index (mirror-symmetric rest skeleton), per-leg pose fit to traced knee/ankle/tip pixels, priors LEG_NOMINAL / LEG_LEN_SIGMA=0.15.

Latest numbers (baked, 128 spp) after leg refit
- Silhouette IoU 0.9182 (was 0.9216 before the leg refit; target >= 0.92).
- Colour probes within 5 % except red_Legs 8.6 % and beige_Legs 60 % (leg tips moved by the refit -> recalibrate / recheck probe box).
- Total 15,362 tris (Body/Eyes/ClawR/ClawL/Legs all < 20k). Brief aims 25k–60k total: consider 2-segment bevels.
- Spike top 10.16 studs; claw-to-claw span 19.1 studs in ReferencePose (brief's 24 conflicts with reference proportions at 10-stud height — report honestly).

Open items
1. Recheck turnaround after leg refit (rest-pose legs were stubby before).
2. Recalibrate legs (beige_Legs), get IoU back >= 0.92.
3. Inspect RigTest_ROM sheet, Rig_Bones, Face_Closeup, Turnaround for gaps/tearing.
4. Write validate_exports.py, run it (validation-report.json).
5. REFERENCE_NOTES.md, README.md (measurements, colour table, pass log, verified/not verified), final manifest.
6. Delete `_work/` at the end; keep make_reference_mask.py, solve_camera.py, compare_reference.py, calibrate.py, build_king_crab.py, validate_exports.py.

## Commands
- Probe: `KC_MODE=probe "<blender>" -b --factory-startup --python build_king_crab.py` then `python compare_reference.py _work/probe_render.png _work/probe_mask.png --out=_work`
- Baked loop: `bash _work/loop.sh`; calibrate: `python calibrate.py _work/final/compare-report.json --damp=0.9`
- Full: `"<blender>" -b --factory-startup --python build_king_crab.py` then `python compare_reference.py` (writes previews/Comparison_*).

## Pass log
- P1 blockout: IoU 0.847 (roll sign bug found: body roll must lift -X).
- P2 roll fixed: 0.876.
- P3 steep-front carapace, face rebuilt: 0.893.
- P4 painterly materials, cutter hook retraced, mask tip fix: 0.909.
- P5 gem claws, eye pupils, hidden legs rerouted, arc belly: 0.918.
- P6 leg attaches from pixels, per-leg scale, spikes widened: 0.927.
- P7 coordinator review: paint -> crimson with up-facing orange (restN bias), worn chips (bevel-mask + ray-cast CHIP_PX blobs, dark rims), eyes/brows bigger, legs chunkier: 0.922.
- P8 lighting study (spread.py percentiles vs reference): paint cells bigger (0.8/stud).
- P9 crusher rebuilt as depth-sculpted hulls (upper palm with knuckle, lower palm, pollex) with planar-dissolved facets; dactyl widened: 0.918.
- P10 cutter hook grows out of palm (tapered thickness), bands slimmer: 0.915.
- P11 front coxae moved onto belly flank, far legs slimmer: 0.920.
- P12 leg target tweaks (C, E), spike bases: 0.922.
- P13 full pipeline in place (join, UV, 2048 bake, final materials); loop runs on the baked posed rig.
- P14 lighting: high front-top sun (el 70, az 175, 4.0) + sky 0.35 + fill 0.3; calibration reset and re-converged: all probes within 5.3 %.
- P15 brows raised/pulled forward, steeper V; paint up_bias 0.32; recalibrated: IoU 0.9216, worst probe 5.1 % (eye).
- P16 first full build (previews/exports OK). Turnaround showed stubby rest-pose legs -> least-squares leg fit with symmetric lengths: IoU 0.918.

## PRIORITY (user, via coordinator) — in progress
Crusher (and cutter for consistency) must be re-oriented to a natural guard: chela long axis forward+down ~35–50° off vertical, gape opening forward/inward, rounded faceted crescent palm, beige fingers curling toward each other, dactyl hinging cleanly on the propodus and closing onto the fixed finger without passing through. Deviating from the reference here is approved (document IoU loss).
Deliverable: previews/AttackCheck_Claws.png (front + 3/4: rest guard, windup, slam/jab impact, pincer open, snapped shut), claws clear of body/face in every pose (BVH overlap check).
Plan: replace build_crusher/build_cutter with build_chela() authored in a chela-local frame (F forward, U dactyl side, S side normal = dactyl hinge axis), world-oriented per side; attack poses as an extra action; BVH overlap report.
- P17 (priority) claws rebuilt: build_chela() authors each chela in a local frame (F forward/in/down ~45°, U dactyl side, S hinge), crusher = thick club palm + red pollex with beige bite edge + beige dactyl; cutter = slim palm, serrated fingers. ReferencePose opens fingers 8°. attack_check() renders previews/AttackCheck_Claws.png (front, 3/4, crusher close-up x guard/windup/impact/open/shut) and writes attack-check.json (BVH overlaps; coxa/merus excluded as they sit in the shoulder socket). Result so far: all poses clean except cutter windup (fixing). IoU drops to ~0.80 in the crusher region (approved deviation).
- P18 attack check clean (0 overlaps in all 5 poses; cutter windup candidate chosen by BVH search). Claw probes recalibrated: all 10 colour probes within 4.3 %. Region IoU: overall 0.797, excluding crusher 0.827, excluding both claws 0.913. validate_exports.py written; first run: 3 failures (eyes smooth by design -> shading-aware check; ReferencePose 1-frame clip exported as rest -> now 2-frame hold; maxilliped ROM phase sampled at zeros -> fixed). Rerunning full build + validation.
- P19 validation PASSED (clip poses reproduce to 0.0001 studs by joint heads; eyes smooth by design; GLB importer 'Icosphere' helper ignored). ROM clearance check added: cutter hit the front-left leg at frame 65 -> claw hand now pitches up while same-side front leg lifts; ROM clean. Chips made ragged. Remaining: REFERENCE_NOTES.md, README.md, annotate sheets, cleanup _work.
- P20 FINAL: dead claw helpers removed; final full build + validation PASSED; sheets labelled (label_sheets.py); README.md and source/REFERENCE_NOTES.md written; _work/ deleted. Final: IoU 0.797 whole / 0.827 excl. crusher / 0.913 excl. both claws; all 10 colour probes within 4.4 %; 52 deform bones; 19,668 tris in 5 sections; attack check and ROM clearance clean. DONE — report sent to coordinator.

## GAME PACKAGE (new task, one focused pass) — in progress
Spec: roguelite-planning/plans/BOSS_GAME_PACKAGE_SPEC.md. Clips (24 fps): Idle, Walk, Hit, Death, ClawCrush, RushStart, RushLoop, RushEnd, BubbleBarrage.
Plan: new self-contained `animate_game.py` (Blender -b) opens KingCrab.blend (model/rig unchanged), authors clips procedurally with analytic FK + damped-least-squares IK (legs pinned while planted; crusher IK for the ClawCrush arc and flat impact), writes exports/game/AnimationData.json, BossGameData.json, GameChecks.json, KingCrab_Studio.fbx (+ .fbm PNGs), adds actions to KingCrab.blend, renders previews/GameClips.png + ClawCrush.mp4 / Rush.mp4 / BubbleBarrage.mp4 (Workbench, low-res). Then extend validate_exports.py and README.
- (running) animate_game.py first run
- game pass: IK fixes (per-leg joint floor, rush turn steps, death floor/drop); all clips clean except Death ground check (iterating)
- GAME PACKAGE DONE: animate_game.py writes exports/game/{AnimationData.json, BossGameData.json, GameChecks.json, KingCrab_Studio.fbx, KingCrab_Studio.fbm/}; clips saved as actions in KingCrab.blend; previews/GameClips.png + ClawCrush.mp4, Rush.mp4, BubbleBarrage.mp4. validate_exports.py extended and PASSED. README "Game package" section added. _work/ deleted.
- Final: README restored after an encoding mishap (rewritten in full with the Game package section); KingCrab.blend verified: 12 actions (9 game clips + ReferencePose, RigTest_ROM, ClawAttack_Check), 5 packed textures. Report sent.
- Studio FBX re-exported with mesh objects named KingCrab_<Section> (Body mesh collided with Body bone in Roblox); validator asserts no mesh/bone name clash; PASSED.
