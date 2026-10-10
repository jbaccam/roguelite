# DJ Crab: Beach Cove round-10 leader ("CRAB RAVE")

One complete, assembled character with the DJ gear already fitted. It has a wide, low coral-red carapace with darker mottled patches, a scalloped front rim and a cream underside "smile" plate. It also has two short eyestalks with glossy black eyes, 8 short, stout walking legs arched out wide and low, and 2 big wedge-palmed crusher claws. Both fingers of each claw are thick and have cream serrated biting edges that close along their length. Big charcoal ear cups with thick teal rings sit on the front-sides behind the eyestalks, joined by a thick charcoal headband that arches 0.62 above the shell top, in front of the speakers. Two big speakers sit on a tan padded saddle on the rear deck. Their cones face backward, with teal LED strips on the outer sides and orange top lights. Tan harness straps with black buckles cross the shell, and two of them run forward so they read from the front.

**Status: Blender-verified, Studio untested.** Nothing has been imported into Studio or installed there.

Built with `build_dj_crab.py`, `animate_game.py` and `validate_exports.py` (Blender 5.2.1, headless).

## Files

| Path | What |
| --- | --- |
| `build_dj_crab.py` | Model, rig, UVs, atlas bake, rest renders and `manifest.json`. `DJ_QUICK=1` renders flat-colour shape checks only. |
| `animate_game.py` | Builds the 8 clips and the checks, then writes the game package, previews and actions in `DJCrab.blend`. `DJ_QUICK=1` runs the clips and checks only. |
| `motion_checks.py` | Shared checks: hinges, twist, rotation per frame, ground, tip drift, BVH overlaps. |
| `render_compare.py` | Renders `previews/Attack_ClawSlam_Impact.png` and our half of `previews/Reference_Compare.png` (the reference's first panel beside our front three-quarter view). |
| `validate_exports.py` | Re-imports the Studio FBX into a fresh scene and re-runs every check on it. Writes `validation-report.json`. |
| `DJCrab.blend` | The source file: rig, the 6 sections, the packed atlas and the 8 actions. The `REVIEW_ONLY` collection is never exported. |
| `textures/DJCrab_Atlas_BaseColor_{2048,1024}.png` | The master atlas and the 1024 delivery atlas. All six sections share one atlas. |
| `exports/game/` | `DJCrab_Studio.fbx` and `.fbm/`, `AnimationData.json`, `BossGameData.json`, `GameChecks.json`. |
| `previews/` | `Front`, `Back`, `Side`, `ThreeQuarter` (rest pose), `Hero` (Intro victory pose), `GameClips`, `Attack_ClawSlam`, `Attack_ClawSlam_Impact`, `Attack_BeatCommand`, `Intro`, `Reference_Compare`. All rendered in EEVEE with a light-blue sky fill (0.55, 0.70, 0.95) and a warm sun, to approximate the game lighting. |

Rebuild:

```
blender -b --factory-startup --python-exit-code 1 --python build_dj_crab.py
blender -b --factory-startup --python-exit-code 1 --python animate_game.py
blender -b --factory-startup --python-exit-code 1 --python validate_exports.py
```

## Provenance

- **Reference:** `art-references/round-10-modeling-pack-2026-10-09/02-dj-crab-complete.png`, SHA256 `F88D73B9A8BF25E0E36D9B698AFD45179436F720366BF5D023593AE1CA050D85`, together with the "Complete crab" prompt.
- **What came from it:** only eyedropped colours and proportions. All geometry is procedural, and the atlas is baked from procedural painterly shaders. No reference pixels, store assets or external models were used.
- **Palette:** warm hues are pushed slightly warmer, and the charcoal is kept neutral-warm. The eye highlight is ivory, not white. This keeps the colours from drifting under Studio's blue ambient and +0.3 saturation.

## Model

- **Units and axes:** 1 unit = 1 stud. The crab faces −Y, +Z is up, and the crab's left is +X. Studio = (−X, Z, Y), the same as `king-crab-boss`.
- **Size:** shell 4.23 wide and 3.72 long (1.55× the regular crab's 2.74). The body sits low: belly 0.97, rim 1.70, shell top 2.51, and the dome rises 0.86 above the rim. Speaker tops are at 3.82; each speaker box is 1.16 tall. bodyCentreHeight is 1.80 and rootHeight 0.
- **Footprint:** radius 4.85, set by the claws. Leg tips reach 3.4–3.6 from the centre.
- **Legs:** about 22% shorter than v1 and 1.3× thicker. Each is a long hidden coxa under the rim, a stout merus rising to a low knee, a carpus, and a dark-tipped dactyl.
- **Claw size:** each chela (palm plus fingers) is about 2.3 long, 0.55 of the shell width; with the arm it is about 0.75. Body centre at 2.15; the Root bone is on the ground (rootHeight 0).
- **Rigid sections:** every part is weighted 1.0 to exactly one bone. Exoskeleton segments overlap inside cream joint bands, so bending never opens a gap.
- **Gear fit:** the gear is ray-cast onto the carapace, and all of it is rigid on Body.
  - Strap and headband inner faces sit 0.02–0.03 inside the shell.
  - The saddle's underside is the shell surface, 0.04 inward. Its thinnest point is 0.11.
  - Each ear cup is 0.92 across, about 0.85 of the eyestalk height.
  - The speakers sit 0.02 into the saddle, and the ear cups 0.12 into the shell.
  - Strap ends finish on the rim and sink into the shell, so no straps hang loose.

| Mesh | Triangles |
| --- | --- |
| DJCrab_Shell (carapace, belly, smile plate, eyestalks) | 1,468 |
| DJCrab_Eyes (smooth-shaded) | 448 |
| DJCrab_Legs | 4,592 |
| DJCrab_Claws | 1,744 |
| DJCrab_Gear (headphones, speakers, saddle, straps, buckles) | 4,552 |
| DJCrab_Glow (teal LED strips, orange buttons; set Neon in Studio) | 264 |
| **Total** | **13,068** |

**Bones (46):**
- `Root` (zero influence) and `Body`.
- `EyeStalk_L` and `EyeStalk_R`.
- `Claw_{L,R}_{Coxa, Merus, Carpus, Propodus, Dactyl}`.
- `Leg_{L,R}{1–4}_{Coxa, Merus, Carpus, Dactyl}`.

Every hinge is on the bone's local X axis. No mesh shares a name with a bone.

## Clips (24 fps, 124 BPM, beat = 0.48387 s)

| Clip | Length | Key times |
| --- | --- | --- |
| Idle (loop) | 3.871 s = 8 beats | The body drops onto every beat and rises between beats. The claws pump alternately and strike down on the beat: the right claw on beats 1, 3, 5, 7, the left on 2, 4, 6, 8. Eyestalks sway. Frames 0–92 run at 1/24 s, then a closure frame at 3.8710 s, so the loop is exactly 8 beats. |
| Walk (loop) | 0.5 s (12 frames) | Fast forward scuttle with alternating tetrapod groups (L1 R2 L3 R4 / R1 L2 R3 L4), duty 0.5. The body bobs twice per cycle with a small yaw and roll sway. strideLength 1.40, nominalSpeed 2.80 studs/s. The stride is limited by neighbouring stout legs, so speed comes from cadence: the runtime's 2.6× cadence cap allows about 7.3 studs/s. |
| Hit | 0.458 s | Flinch, then back to the Idle start pose. |
| Death | 2.0 s | Stagger, then the legs buckle and splay, with the tips curling just off the sand. The body drops 0.50 until the coxae and shell rest 0.02 above the sand. The claws lie flat in front, the eyestalks droop, and a pincer twitches at 1.7 s. The speakers stay attached. |
| BeatCommand | 1.333 s | Conductor raise at 0.28, holds a beat, sweeps forward and **snaps shut at 0.75 (impact)**. warn 0.10, recovery ends 1.20. |
| ClawSlam | 1.625 s | Rears up with both claws high (windup 0.15–0.54). **Slams down at 0.833 (impact)**, rebounds, recovery ends 1.40. Arm reach at impact is 93%. |
| Bombard | 1.208 s | Pumps overhead at 0.25 and at **0.583 (signal / impact)**. Recovery ends 1.00. |
| Intro | 3.0 s | Crouched and still. The speakers thump (body pulses) at 0.40, 0.88, 1.37 and 1.85. Eyestalks pop up at 1.0. Both claws **snap shut at exactly 2.000 (impact)**. Victory pose at 2.4, then settles to the Idle start pose at 3.0. |

Points in BossGameData use root space at impact, Blender axes:
- **CommandClaw** (Claw_R_Propodus pincer tip): (−1.04, −4.92, 2.19). Its horizontal direction is (0.01, −1.0, 0).
- **ClawSlam LeftClaw / RightClaw:** (±0.98, −5.23, 0.27).
- **SlamCenter:** (0, −5.23, 0). Spawn the ground ring here.
- **SpeakerTop** (Body): (0, 0.66, 3.92) at the Bombard signal, (0, 0.46, 3.85) at the Intro snap.

How the motion is made:
- Legs are solved every frame by damped least squares, with joint limits and a rim-clearance term.
- Big claw gestures are keyposes. Each is solved once by IK with clearance from the front legs and from the shell-and-gear envelope, then interpolated in joint space. Each frame is then re-projected with the clearance active, so the IK cannot flip branches between frames. Every limb bone rotates as a pure swing.
- Attacks start and end on the Idle start pose (the rest pose). The Intro starts crouched by design and only ends on rest.

## Checks

These ran on the source rig (`GameChecks.json`) and again on the fresh FBX re-import (`validation-report.json`, **PASS**). Worst numbers across all clips and frames:

| Check | Result |
| --- | --- |
| Hinge directions | 0 violations. Knee 1.0–96.7°, ankle 0.8–66.1°, elbow 8.0–139.2°, pincer gape 0–45°, wrist −76.1–31.5° (inside rest ±75°), leg lift inside rest ±60°. |
| Twist | 0.0° (limit 70°) |
| Rotation between frames | 40.4° (limit 45°; the Walk loop-closure frame). No snaps needed an exception. |
| Ground | Lowest point 0.000 (limit −0.05) |
| Planted tip drift | 0.0000 studs (limit 0.05) |
| Overlaps | 0 frames in Idle, Hit, Death, BeatCommand, ClawSlam, Bombard and Intro, and none at rest. Walk has 1 frame with an 8-triangle graze: a rear leg against the rear belly. |
| Loop closure | Exact after the snap. The error before the snap was 0.064 (Idle) and 0.037 (Walk), in matrix units. |
| Re-import | 6 meshes, 46 bones, parents and rest matrices equal AnimationData (error < 1e-3). Rigid weights, no leaf bones, no animation, 1024 atlas loads. Faceting is kept and the eyes stay smooth. |
| Skinning truth | Posing the re-imported rig from AnimationData reproduces the source vertices within 0.00001 studs. |

## Known issues

- **Studio import untested.** Blender's FBX importer guesses bone tails and marks 31 bones "connected"; the validator un-connects them before posing. Roblox Bone CFrames should not be affected, but check this in Studio.
- **Footprint:** the footprint radius is 4.85 (brief: about 4.5). This comes from the bigger reference-style claws reaching forward.
- **Remaining differences from `02-dj-crab-complete.png`** (see `previews/Reference_Compare.png`):
  - The cream underside shows as a scalloped band rather than the reference's large plated smile.
  - The speaker casing backs are plain, with no panel screws.
- **Arm reach:** the arms are short relative to the claws. The conductor and windup poses raise the palms to about 3.0–3.7 studs.
- **Idle timing:** the closure frame's last interval is 0.038 s rather than 1/24. Any player that samples by time is exact; one that assumes uniform frames ends 4 ms short per loop.
- **Last-frame snap:** Hit and ClawSlam end 0.06–0.08 (matrix units) away from rest before the final-frame snap. The snap is covered by the 27° frame-to-frame limit.
- **Walk speed:** the walk is a fast 0.5 s scuttle at 2.80 studs/s with a short 1.40 stride; a longer stride made the stout neighbouring legs collide. At the DJ's 8 studs/s the runtime needs about 2.9× cadence, slightly above its 2.6× cap, so either the cap or the move speed needs a small adjustment. One Walk frame has a small rear-leg graze; see Checks.
- **Headband:** the arched headband is attached only at the cups and does not touch the shell between them, as in the reference.
