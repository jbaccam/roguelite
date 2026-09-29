# Spartan armor set (Epic)

**Blender-verified, Studio untested.**

A hoplite hero in polished bronze and crimson, built in Blender 5.2 by `build_spartan.py`. The
generator is self-contained: its pipeline is copied from `build_dragon_scale.py`, never imported. It
fits the normalized R15 body in `../r15-proxy`.

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 --python build_spartan.py
QUICK=1 ...   flat colours, no bake or export (shape checks)
```

## Design

- **Helmet (`"full"`).** A Corinthian bronze helm:
  - cheek guards with a sculpted bulge, T-shaped eye openings and a mouth slit, with a dark liner behind them;
  - a nose guard with a centre ridge, and a heavy brow band arching over the eyes;
  - a notch under each ear, a flared neck guard and temple rivets;
  - a tall, chunky, rounded crimson horsehair crest running front to back. It has 5 ridges and
    4 broad combed grooves, and is fused into a bronze crest holder.
- **Chest.**
  - A cartoon muscle cuirass: pecs, 2×3 abs, a centre groove, and rolled neck and waist beads.
    A dark crimson tunic shows at the neckline.
  - A short rigid crimson cape. It runs over the shoulder tops, down to the lower back, and has
    broad folds and a scalloped hem. It stays inside the torso side planes and keeps clear of the
    helm, with bronze disc clasps on the shoulders.
  - Rounded bronze shoulder domes with a raised ring and rolled rims. Under them sit a leather arm
    band and 8 pteruges strips.
  - A leather belt with bronze studs and a bronze boss carrying a small painted crimson lambda.
  - 8 front and 8 back pteruges with rounded ends. They flare 0.07 → 0.14 studs away from the thighs.
  - Bronze vambraces with an outer ridge, a wrist flare and rolled ends.
- **Legs.** Bronze greaves with a knee dome, a shin ridge and a sculpted calf. The back stops well
  below the knee joint. Each thigh has a leather band with a bronze boss and studs, over a tunic layer.
- **Boots.** Sandal-boots:
  - a cuff band and 5 criss-cross strap Xs on the lower leg, plus an ankle strap;
  - a dark leather sole band and a bronze toe plate;
  - a heel strap and an X on the outer side.
- **Craft.** 2-segment bevels on the bronze and 1-segment bevels on the leather and cloth. The bake
  adds a painted, broad hammered-bronze gradient with brown shading, cool shadows and warm edge
  highlights, plus AO under the strips, cape and crest. No Neon, particles or lights.

## Numbers

- **Triangles (exported):** 24,100 in total.

  | Piece | Triangles |
  |---|---|
  | Helmet | 4,136 |
  | Chest | 12,864 |
  | Legs | 3,596 |
  | Boots | 3,504 |

  The largest mesh is `Spartan_Chest_UpperTorso` at 5,516. Per-mesh counts are in `polygon-report.json`.
- **Atlases:** 4 at 1024², in `textures/spartan-{helmet,torso,arms,legs}.png`. The Legs and Boots
  pieces share `legs`. Baked directly at 1024 with 8 samples.
- **Meshes:** 15, named `Spartan_<Piece>_<BodyPart>`. Install data is in `studio-install-data.json`
  (`"helmet": "full"`, no glow).

## Fit notes

- Plates sit 0.028 studs off the body and the tunic 0.012.
- Nothing is on the inner leg faces or the LowerTorso sides.
- The shoulder domes stay outboard of the arm's inner face.
- The measured rig overlaps matter:
  - the lower leg covers the thigh's bottom 0.42 studs, so the thigh band sits just under the pteruges;
  - the foot's top is at lower-leg z −0.50, so the sandal straps end there.

## Verification (Blender only)

- **Exports** (`validation-report.json`): FBX and GLB both OK.
  - 15/15 meshes, with triangle counts matching the report;
  - no loose vertices, zero-area faces or vertex colours;
  - UVs inside 0–1;
  - 4 images at 1024².
- **Pose check** (`pose-check.json`): intersecting triangle pairs, with part groups rotated about
  their rig joints.

  | Pose | Pairs |
  |---|---|
  | Idle | 126 |
  | Walk | 994 |
  | Run | 2,311 |
  | Jump | 810 |
  | Fall | 1,268 |

  The main contributors are:
  - helm rim against the cuirass neck in idle;
  - bracer tops under the arm pteruges as the elbow bends;
  - front pteruges against swinging thighs;
  - the run pose's kicked-back heel reaching the cape hem;
  - shoulder domes against the cape and cuirass with the arms raised to the side.

## Known gaps

- The bronze reads a little bright and gold in the Eevee preview, where the sun adds to the baked
  light. Check it in Studio.
- Small bare-body slivers show at the elbows, the backs of the knees and the torso sides. These are
  hand-swing and joint zones, left open by the fit rules.
- Not tested in Roblox Studio.
