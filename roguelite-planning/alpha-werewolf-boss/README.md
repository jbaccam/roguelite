# Blood Moon Alpha (alpha werewolf) - Frozen Pass round-10 leader

Status: **Blender-verified, Studio untested.** The package was re-imported into a fresh Blender scene and the clips were replayed on the re-imported rig. Nothing has been imported into Studio.

## Files

| Path | What |
| --- | --- |
| `build_alpha_werewolf.py` | Sculpt, colour masks, cavity, per-section 1024 bake, rig and weights, turnaround renders. Self-contained; the regular werewolf's helpers are copied, not imported. |
| `animate_game.py` | FK/IK pose solver, the 8 clips, all motion checks, `exports/game/*`, actions in the .blend, preview frames. |
| `compose_previews.py` | System Python + Pillow. Composes the preview sheets. |
| `validate_exports.py` | Fresh re-import and clip replay; writes `validation-report.json`. |
| `AlphaWolf.blend` | Rig `AlphaWolf_Rig`, 7 sections, packed maps, clip actions, and a `REVIEW_ONLY` collection (excluded from export). |
| `exports/game/` | `AlphaWolf_Studio.fbx` (+ `.fbm/`), `AnimationData.json`, `BossGameData.json`, `GameChecks.json`. |
| `textures/AlphaWolf_<Section>_BaseColor_1024.png` | One 1024 delivery map per section. |
| `previews/` | `Front`, `Back`, `Side`, `ThreeQuarter`, `Hero`, `ScaleCompare` (next to the regular werewolf), `GameClips`, `Attack_ClawRake`, `Attack_Howl`, `Charge`, `Compare_Reference` (sheet above, renders below). Renders use a blue sky fill and a warm sun. |
| `manifest.json`, `validation-report.json` | Dimensions, bones, triangle counts, texture hashes; check results. |

To rebuild, run these in order:

```
blender -b --factory-startup --python-exit-code 1 --python build_alpha_werewolf.py
blender -b --factory-startup --python-exit-code 1 --python animate_game.py
python compose_previews.py
blender -b --factory-startup --python-exit-code 1 --python validate_exports.py
```

## Provenance

The reference is `art-references/round-10-modeling-pack-2026-10-09/05-alpha-werewolf.png`, copied to `source/`. SHA256: `5b496e5a22b990b0128d17317480c078da023a4b51bdd57e4d1d71a198115b53`.

All geometry and textures are procedural. The reference supplied only the palette, which was sampled by k-means and then adjusted for Studio's lighting.

The base is the regular werewolf (`mob-production/reference-rebuilds/build_werewolf.py`). Shapes are authored at that werewolf's scale and multiplied by 1.27, so 1 unit = 1 stud. The alpha is 9.25 tall (ear tips), against 6.98 for the regular werewolf: **1.33x**.

## Model (third pass, 2026-10-09)

| Mesh | Triangles |
| --- | --- |
| `AlphaWolf_Body` | 11,000 |
| `AlphaWolf_Head` | 3,520 (Jaw and lower fangs weighted to `Jaw`) |
| `AlphaWolf_Hands` | 2,240 |
| `AlphaWolf_Shorts` | 1,984 |
| `AlphaWolf_Tail` | 1,600 |
| `AlphaWolf_Feet` | 1,576 |
| `AlphaWolf_EyeGlow` | 108 (separate, for Neon) |
| **Total** | **22,028** |

How it's made:

- **Fur:** the regular werewolf's fur language. Layered, leaf-shaped, soft-tipped clumps (its exact clump profile) are fused straight into the skin with its smoothing:
  - a charcoal mane shield flaring up behind the head and over the shoulders;
  - a cream chest bib;
  - russet layers on the shoulders and upper arms.
- **Limbs:** the forearms and calves are smooth painted fur, with tufts only at silhouette breaks:
  - 3 swept back along each outer forearm edge;
  - 2 at each elbow point;
  - 3 swept down the back of each calf;
  - one soft cuff ring at each wrist and ankle, with the hands and feet clear below.
- **Paint:** the skin carries directional fur strokes, and clump tips are about 18% lighter.
- **Head:** raised with a longer neck, and bigger ears (left ear notched).
- **Tail:** one bushy tapered tail of layered clumps with a cream tip.
- **Colour:** the sheet's brown-maroon. Whites are ivory/bone and the charcoals lean warm, for Studio's blue sky ambient, its +0.3 saturation and the Blood Moon red tint.
- **Axes:** faces −Y, +Z up, anatomical Left at +X (matching king-crab and frost-cyclops).

## Rig

39 deform bones. `Root` sits at the origin and has no weights.

- **Spine and head:** Pelvis, Spine, Chest, Neck, Head, Jaw, Mane.
- **Tail:** Tail1, Tail2, Tail3.
- **Per side (Left/Right):** Shoulder, UpperArm, Forearm, Hand, Fingers, Thigh, Shin, Foot, Toes.
- **Helpers (new):** per side, ShoulderHelper and ElbowHelper rotate halfway between their neighbours. KneeHelperA, KneeHelper and KneeHelperB rotate a quarter, half and three-quarters of the knee fold. Each carries its part of the skin blend band, so folds keep their mass.

Studio playback must apply all eight helper bones' transforms from `AnimationData.json` like any other bone. The animation solver also lifts the clavicle automatically when an arm rises above about 70°.

## Clips (24 fps)

| Clip | Duration | Notes |
| --- | --- | --- |
| Idle | 3.0 s loop | Starts on the rest pose. |
| Walk | 0.75 s loop | Chase run: strideLength 16.5, nominalSpeed 22. |
| Hit | 0.458 s | |
| Death | 2.208 s | Ends lying on its side; the lowest point is 0.00. |
| Howl | 2.208 s | Impact 1.0 s, held to 1.79 s, recovery ends 2.08 s. Point `Mouth`. |
| ChargeStart | 0.708 s | Ends exactly on ChargeRun frame 0. |
| ChargeRun | 0.5 s loop | chargeStrideLength 16, chargeSpeed 32. |
| ClawRake | 1.083 s | Warn 0.083 s, impact 0.5 s, activeEnd 0.667 s, recovery ends 0.958 s. Points LeftClaw, RightClaw, LeftForearm, RightForearm, plus per-frame sweep samples. Reach at impact is 98%. |

The attacks, Hit and Death all start on the Idle start pose. The attacks and Hit also end on it.

## Checks

These are the worst cases over all frames of all clips, from `GameChecks.json` and `validation-report.json` (PASSED).

**Passing:**
- **Hinges:** knee 3.6–131°, elbow 3.6–97°, fingers 0–39°, toes 0–60°, jaw 0–41°. Nothing reverses and nothing leaves its hinge plane.
- **Twist:** forearm and shin twist is 0°.
- **Per-frame rotation:** at most 42.5°, including the Death leg release, which is now a 2–3 frame flop.
- **Foot drift:** at most 0.006.
- **Ground:** the lowest point is −0.006.
- **Penetration:** at most 0.035.
- **Loops and poses:** loops close exactly, and starts/ends match within 4e-6.
- **Re-import:** rest matrices, bounds, weights, UVs and maps all match, and the attack points replay within 7e-5.

**Joint mass (band radius retention; 1 = no pinch):** this is the mean squared distance of the blend-band skin to the joint centre, posed / rest. It is rigid-invariant: either bone moving rigidly keeps it at 1, so only skinning pinch lowers it.

| Clip | Worst joint value |
| --- | --- |
| Idle | 1.00 |
| Hit | 0.99 |
| Howl | 0.94 |
| ClawRake | 0.93 |
| Death | 0.88 |
| Walk | 0.87 |
| ChargeStart | 0.84 |
| ChargeRun | 0.83 (hip; sprint knees 0.83 or better) |

An earlier distance-to-the-child-axis version also dropped for a perfectly rigid fold, so it was replaced. The legacy cone-volume number (worst 0.60 at the ChargeRun knee) is still in the reports for reference; it is unreliable around joints whose centre sits near the surface.

## Known issues and differences from the sheet

- **Mane:** slightly less tall and spiky than the sheet's.
- **Bones:** the 8 helper bones are additions. Existing bone names, clip timings and BossGameData points are unchanged.
- **Studio:** untested.
