# Phoenix armor set (Godly)

**Blender-verified, Studio untested.** Built 2026-09-29 in Blender 5.2 (background mode).

## Design
A radiant firebird knight. It's the only set with VFX and lighting on the armor itself.
- **Materials:** ivory-white plates (cool lavender shadows, warm cream lights) with brown-shaded gold trims. The crimson undersuit shows in the gaps.
- **Feathers:** every feather is a thick, bevelled flame blade graded crimson → orange → gold at the tip, with a pale gold rachis. The feathers sit in clean, ordered rows with the roots sunk into the surface they grow from.
- **Helmet (`"full"`):** a phoenix head.
  - A hooked gold beak visor with a small lower mandible.
  - Glowing, fiercely angled eyes in a dark visor slit, under gold brow ridges.
  - A gold keel down the crown with a swept crest of 14 flame feathers in graded rows. The biggest feathers have Neon tips.
  - Swept plumes at each temple.
- **Chest:**
  - Ivory breastplate with gold rims, with crimson inlays of staggered plumage feathers.
  - A gold sternum keel with a thin glow seam.
  - The core: a round Neon sun gem in a domed gold rondel, gripped by four gold talons, with eight gold sunburst rays.
  - Ivory abdominal lames with gold lips.
- **Pauldrons:** an ivory dome with a gold rim, a mantle of 34 staggered feathers flowing down and out over the dome, and a crest of 5 big feathers sweeping up and back. The two rear crest feathers have Neon tips.
- **Back:** two folded wings on the backplate. Each has:
  - a gold wing-arm;
  - coverts over secondaries over primaries;
  - two alula flames rising at the wrist (the wing tip).

  The primaries and the alula have Neon tips.
- **LowerTorso:** crimson belt with gold lips and rivets, and a small gold sun buckle. Ivory tassets end in a hem of four flame feathers that flare away from the thighs.
- **Vambraces:** ivory, with gold wrist and top rims, gold ribs, a thin glow seam on the outer ridge and a three-feather flare.
- **Legs:** ivory thigh plates and greaves with a gold centre ridge, and ivory knee cops with gold rims and a three-feather flare.
- **Boots:** an ivory cuff with a two-feather ankle flare. The sabaton lames have gold edges, with three gold talons over the toe and a gold heel spur.
- **VFX (`studio-install-data.json` → `"vfx"`, part-local Studio axes):**
  - flames at the helm crest, both pauldrons and both wing tips;
  - embers rising between the wings and from the core;
  - one PointLight at the sun core.

  The hero render shows the flames as stylized emissive flame licks and lights the core. Neither is exported.

## Triangles (38,404 total, 5 atlases at 1024)
| Mesh | Tris |
|---|---|
| Helmet_Head / _Glow | 4,136 / 424 |
| Chest_UpperTorso / _Glow | 11,484 / 318 |
| Chest_LowerTorso | 4,360 |
| Chest_Left/RightUpperArm / _Glow | 4,344 / 52 each |
| Chest_Left/RightLowerArm / _Glow | 928 / 16 each |
| Legs_Left/RightUpperLeg | 708 each |
| Legs_Left/RightLowerLeg | 1,188 each |
| Boots_Left/RightLowerLeg | 682 / 680 |
| Boots_Left/RightFoot | 924 each |

By piece: Helmet 4,560 · Chest 26,842 · Legs 3,792 · Boots 3,210. The largest mesh is UpperTorso at 11,484, under the 20k limit.

## Files
- `build_phoenix.py`: a self-contained generator. The shared pipeline is copied from the Dragon Scale kit, not imported.
  - `QUICK=1`: flat colours, no bake.
  - `POSE_IMG=0`: numeric pose check only.
- Outputs:
  - `exports/fbx/phoenix.fbx` and `exports/glb/phoenix.glb`;
  - `textures/phoenix-{helmet,torso,arms,legs,boots}.png`.
- `previews/`: `front`, `back`, `side`, `threeq`, `close-helm` (Eevee), `hero` (Cycles) and `sheet.png`.
- `polygon-report.json`, `studio-install-data.json`, `pose-check.json`.
- `validate_exports.py` → `validation-report.json`. FBX, GLB and install data all pass.

## Pose check (intersecting triangle pairs; Dragon Scale in brackets)
| Pose | Pairs |
|---|---|
| idle | 1,148 (713) |
| walk | 2,537 (2,118) |
| run | 3,877 (2,722) |
| jump | 1,734 (1,467) |
| fall | 3,691 (2,809) |

The biggest pairs:
- **Fall (arms out 75°):** pauldron vs UpperTorso armour, about 700 per side. The pauldron feathers meet the wings and collar.
- **Run:** vambrace vs upper-arm lames, about 325 per side.
- **Walk/jump:** tassets vs thighs, up to 325.
- **Every pose, including rest:** the helm rim vs the breastplate collar, 155.
