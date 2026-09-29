# Samurai armor set (Epic)

**Blender-verified, Studio untested.** Built 2026-09-29 by `build_samurai.py`. It is self-contained:
the pipeline parts are copied from `../build_dragon_scale.py`, and it reads only `../r15-proxy/`.

```
blender -b --factory-startup --threads 2 --python build_samurai.py        # full: bake, export, previews, pose check
QUICK=1 NOPOSE=1 blender ... --python build_samurai.py                     # shapes only, flat colours, no files touched
blender -b --factory-startup --threads 2 --python validate_exports.py     # re-import FBX + GLB, write validation-report.json
```

## Design

An o-yoroi warlord in lacquered lamellar armour.

- **Colours:**
  - deep crimson lacquer with painted gold-cord lacing and raised gold cord knots;
  - black lacquer for the trims and top plates;
  - brown-shaded gold;
  - a dark navy cloth and mail undersuit that shows in every gap.
- **No glow:** no Neon, particles or lights.
- **Helmet (`"helmet": "full"`):** a kabuto.
  - A ribbed black dome on a gold band, with a gold rosette on the crown.
  - A black visor with a gold lip.
  - A flared four-lame crimson shikoro. Each lame tucks inside the one above.
  - Fukigaeshi: the front edges turn back into black flaps with a gold mon.
  - A chunky gold crescent maedate on a faceted gold boss.
  - A navy hood underneath, so no face or hair shows.
  - A crimson menpo with slanted scowling eye slits, a drooping black moustache ridge and a snarled mouth.
- **Chest:**
  - A barrel-fronted do: four kozane rows on the front and four on the back. Each row's lower edge lifts over the next row.
  - A black muna-ita with gold bands.
  - Watagami straps over the shoulders.
  - A gold agemaki bow on the back.
  - Belt with a gold knot.
  - Kusazuri: 3-row front and back panels, plus 3-row side panels that hang below the hands.
  - Sode: a black kanmuri-ita bent over the shoulder, then four laced lames flaring out to 0.31 studs past the arm.
  - Kote: a mail sleeve, a gold-banded cuff, three ikada plates down the outer forearm, and black front splints on the forearm and upper arm.
- **Legs:**
  - Haidate: 3 rows × 5 crimson tiles on navy cloth.
  - Suneate: three black splints over mail, and a crimson knee cop.
- **Boots:** black lacquer with a gold top band, a gold cord wrap and a bow on the outer side, a gold cord cross on the instep and a dark sole welt.
- **Fit:** the README fit rules of the kit apply.
  - Clearance: plates 0.028, undersuit 0.012.
  - Nothing beyond the torso side planes. Nothing on the inner leg faces.
  - Tassets flare 0.07–0.15. The sode stay outboard of the arm's inner face.
  - Knee cop and splints sit below the thigh tiles. Forearm plates sit below the elbow joint on the front.

## Numbers

- **Triangles:** 26,012 in total. The largest mesh is the helmet at 5,690. Every mesh is under 20k.

  | Mesh | Tris |
  |---|---|
  | Helmet_Head | 5,690 |
  | Chest_UpperTorso | 3,996 |
  | Chest_LowerTorso | 3,086 |
  | Chest_Left/RightUpperArm | 1,816 each |
  | Chest_Left/RightLowerArm | 1,152 each |
  | Legs_Left/RightUpperLeg | 1,226 each |
  | Legs_Left/RightLowerLeg | 848 each |
  | Boots_Left/RightLowerLeg (cuff) | 886 each |
  | Boots_Left/RightFoot | 692 each |

- **Atlases:** 4 at 1024 (`textures/samurai-{helmet,torso,arms,legs}.png`). Albedo and baked light are in one image; use `MeshPart.TextureID`.
- **Export check** (`validation-report.json`): FBX and GLB both OK.
  - 15/15 meshes, and triangle counts match the report.
  - No loose vertices, zero-area faces or vertex-colour layers.
  - UVs inside 0–1.
  - Four 1024×1024 images embedded.
- **Pose check** (`pose-check.json`, numbers only). Counts are intersecting triangle pairs.

  | Pose | Pairs | Main contributors |
  |---|---|---|
  | Idle | 805 | Static contact between boot cuff and foot wrap (the ankle never rotates); the shoulder cloth hidden inside the head |
  | Walk | 2,359 | Front kusazuri vs the swinging thighs |
  | Run | 3,200 | Front kusazuri vs the swinging thighs |
  | Jump | 1,998 | Raised thigh into the front kusazuri |
  | Fall (arms out 75°) | 2,938 | Sode tops swinging into the shikoro |

## Known issues

- **Body shows at the top edge of the torso.**
  - What: under the chin, the proxy torso's top chamfer pokes through the undersuit. It shows as a pale strip in front views; in game it would be the shirt colour.
  - Cause: in `build_upper_torso`, the undersuit `vs` jump from 0.6 to 0.9 across the rounded top edge.
  - Fix: use `[-0.8, -0.3, 0.2, 0.6, 0.68, 0.73, 0.78, 0.83, 0.887, 1.0]`, then run one more full build (about 65 s).
  - Not done: the brief allows one bake plus one fix run, and both were used.
- **Arm-raise clipping.** With the arms fully raised, the sode tops pass into the shikoro, like the Dragon Scale pauldrons do.
- **Previews.** The previews were re-rendered from `samurai.blend` with a matte material (a render only, no re-bake). The generator now sets the same material.
