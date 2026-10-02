# Egg merchant kit

## Egg

The pet egg on its straw-nest pedestal, pre-broken so it can crack open in game. It is built from the
egg in `../art-references/egg-merchant/egg-merchant-concept-v1.png`
(SHA256 `9417e874af27600559c9b155b2796a6ef03737cff6414a58279d235634e0893f`). Per the owner, the belt
and the gold paw medallion are left out. **Blender-verified, Studio untested.**

Previews are real Blender renders (Eevee, bloom on the glow):
`previews/egg-closed.png`, `egg-cracked.png`, `egg-open.png`, `egg-front.png`, `egg-side.png` and
`egg-sheet.png` (all five, plus the icon). `previews/icon-egg.png` is a 512 px transparent UI icon
showing the egg and nest without the pedestal.

### Rebuild

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python build_egg.py
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python validate_egg.py
```

- `-- --quick [--quick-dir=<folder>]` paints the atlas and renders two shape checks, with no bake and no export.
- `-- --preview` bakes and renders without exporting.
- The generator is self-contained. It paints the atlas with Blender's own numpy, so system Python is not needed.
- It takes about 20 s.

### Parts

All parts are at final stud size: **import 1:1, do not scale**. Every origin is at the ground centre,
with identity transforms. Front is -Y in Blender and -Z in the FBX/Studio.

| Part | Kind | Tris | Roblox use |
|---|---|---|---|
| `Pedestal_Base` | textured | 6,172 | Two-tier wooden drum. Each tier has 2 rows of 8 long bevelled planks (45° each) with lined-up seams and painted horizontal grain. Dark rim lips have their joints under the brackets. 4 gold diagonal brackets, domed hex bolts on the plank corners |
| `Pedestal_Nest` | textured | 3,718 | Woven straw bird's nest: a thick rim of 54 twisted straw bundles spiralling round a torus, 11 irregular tufts of 2–4 thick blades, 6 loose strands draped over the drum edge, and a straw mound under the egg |
| `Egg_Bottom` | textured | 1,008 | Lower cup up to the zigzag break line, with a 0.12 shell, a pale inner surface and a jagged rim |
| `Egg_Top_1`…`Egg_Top_4` | textured | 176–228 | Side shards between the break line and the crown ring: front-left, front-right, back-right, back-left |
| `Egg_Top_5` | textured | 248 | Crown shard (the top of the egg) |
| `Egg_Crack_1` | glow | 116 | Tap 1: front zigzag of the break line plus one branch going up |
| `Egg_Crack_2` | glow | 596 | Tap 2: the rest of the break line, the crown ring and all shard lines |
| `Egg_Inner_Glow` | floor | 94 | Glowing dome inside the cup, shown when the top is gone |

The egg pieces total 2,866 tris and the pedestal plus nest 9,890. Exact counts and bounds are in
`polygon-report-egg.json`.

### Sizes (Blender z = Studio Y)

- **Drum:** about 5.68 studs across and 1.70 tall. The bracket tops reach 1.88.
- **Nest:** the woven rim tops out about 0.9 above the drum, with tufts up to about y 3.26. The draped strands hang down to y 1.36.
- **Egg:** 4.6 tall and 3.35 wide, wider at the bottom. Its bottom sits at y 1.80 inside the straw and its top is at 6.40.
- **Break line:** the mean is at y 4.43 (57.5% of the egg's height), with zigzag teeth about ±0.3 studs. The crown ring is at about 85%.

### How the break works

- **One surface, shared vertices.** The egg is a single faceted surface. The break lines are forced to be mesh edges, so every piece shares exact vertices and the intact egg has zero gap and no seams. The shading has no seams either, because custom normals come from the analytic egg.
- **Rims.** Each piece is its outer facets, an inner shell 0.12 studs in, and rim walls along its cut edges.
- **Spots.** The spots are painted in angle/arc space, so they run straight across the cracks.
- **Cracks.** The crack ribbons are 0.095–0.115 studs wide and sit 0.022 proud of the shell. Together, Crack_1 and Crack_2 trace every cut.

### Studio install (for the installer)

- Import `exports/fbx/egg-kit.fbx` with default settings. Axes follow the chest kit: studio = (-x, z, y) of Blender, front = -Z.
- **`studio-install-data-egg.json`** gives, for each part, its `kind`, bbox `centre`, `size` and `tris` in Studio axes. It also holds:
  - `egg`: centre, height, `break_height`, top and bottom;
  - `shards[Egg_Top_n]`: `centroid` and a unit `outward` fling vector (the crown flies straight up);
  - `glow_colour`: [255, 208, 118].
- **Textured parts:** MeshPart `TextureID` = `textures/egg-kit-baked.png` (1024², baked icon lighting, `UVMap`). They all share this one texture.
- **Sequence:**
  1. At rest, the cracks and the inner glow are hidden.
  2. Tap 1 shows `Egg_Crack_1` (Neon, glow colour).
  3. Tap 2 also shows `Egg_Crack_2`.
  4. At the burst, hide both cracks, fling `Egg_Top_1..5` along `outward` (a spin is optional) and show `Egg_Inner_Glow` (Neon).
- **Glow (optional):** the previews light the open cup with a warm PointLight (about 140 W, glow colour) at y ≈ 4.33. A matching PointLight in Studio would help sell the glow.

### Texture

- **Shipped texture:** `textures/egg-kit-baked.png` is the only texture that ships. It is 1024² on unique UVs. The bake follows the chest kit: painted atlas × per-facet key light (top-front-left) × AO × height gradient, plus a cool back-right rim and bright bevel-edge highlights.
- **Egg in the bake:**
  - The egg shell gets about 2× the texel density of the rest.
  - It gets a small per-facet value jitter, so its soft planar facets read.
  - Bevel highlights are masked off the egg, so the break lines never show at rest.
  - The inner shell is baked in the open pose.
- **Painted source:** `textures/egg-kit.png` is the unbaked painted atlas (2048²), kept for rebuilds only.

### Known limits

- Never tested in Studio. Roblox's own lighting adds to the baked lighting, so judge colour there. The game's +0.3 saturation will push the teal and straw further.
- About 40% of the baked atlas is empty space: Blender's packer left gaps around the irregular egg islands.
- The icon hides the pedestal, so the draped strands dangle below the nest there.
- Pedestal plus nest is 9,890 tris, close to the 10k budget.


## Merchant

Hooded travelling egg merchant NPC, a rigid-part Roblox blocky avatar (R15 blocky proportions x1.2)
built from `../art-references/egg-merchant/egg-merchant-concept-v1.png`
(SHA256 `9417e874af27600559c9b155b2796a6ef03737cff6414a58279d235634e0893f`, used as reference only).
Blender-verified, Studio untested.

- **Rebuild:** `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python build_merchant.py`
  (calls system Python itself to paint `textures/merchant.png`), then
  `... --python validate_merchant.py`. `-- --quick --out <dir>` renders flat-colour shaping views only;
  `-- --preview` bakes and renders without exporting.
- **Files:** `exports/fbx/merchant.fbx`, `exports/glb/merchant.glb`, `merchant.blend` (collection `Merchant`),
  `textures/merchant-baked.png` (1024, baked icon lighting, the only texture every part uses),
  `textures/merchant.png` (unbaked painted source), `previews/merchant-*.png`,
  `polygon-report-merchant.json`, `validation-report-merchant.json`, `studio-install-data-merchant.json`.
- **Size:** studs at final size, import 1:1. Soles at 0, hood top 6.38, egg basket top 7.532
  Every part has identity transforms with its origin at the world origin; place parts by the
  `centre` values in `studio-install-data-merchant.json` (studio = (-x, z, y) of Blender, front = -Z).
- **Parts (15,308 tris total):**

| Part | Tris |
|---|---|
| `Merchant_Head` | 1,140 |
| `Merchant_Torso` | 1,544 |
| `Merchant_Hips` | 1,932 |
| `Merchant_Pack` | 5,996 |
| `Merchant_UpperArm_L` | 472 |
| `Merchant_UpperArm_R` | 472 |
| `Merchant_LowerArm_L` | 1,224 |
| `Merchant_LowerArm_R` | 872 |
| `Merchant_Leg_L` | 744 |
| `Merchant_Leg_R` | 744 |
| `Merchant_HandEgg` | 168 |

- **Joints** (Motor6D pivots, Studio coords in `studio-install-data-merchant.json`): Neck, Waist (root is
  `Merchant_Hips`), Pack, Shoulder_L/R, Elbow_L/R, Hip_L/R, HandEgg. Rest pose: arms splayed 8 deg,
  elbows bent 22 deg (L, holding the egg forward) and 12 deg (R).
- **Joints are built to rotate:** the head sits in a chunky cowl, the shoulder caps and forearm tops are
  balls round their pivots, leg tops are domes inside the hips, the torso's lower edge tucks under the belt.
  AO is baked per part only, so no shadow is left behind when a part moves.
- **Pose check:** `previews/merchant-pose-check.png` is the re-imported GLB posed only with the recorded
  pivots: right arm raised 80 deg (out, 25 deg forward), elbow +70 deg twisted palm-up, head turned
  20 deg to his right. The exact rotations are in `validation-report-merchant.json`.
- **Pack:** square crate-basket from the shoulder blades (z 3.75) to a rim 0.3 above the hood (6.68):
  horizontal slats with gaps, chunky corner posts, two iron bands with steel bolts, two vertical leather
  straps with gold buckles on the back, six spotted eggs heaped in straw (top about 7.5), bedroll on his
  left, pouches on the lower sides. The collar sits below the head, so the whole face block is clear.
  Coat and hood greens are olive/moss (sRGB 95,120,55 mid) so the +0.3 Studio saturation stays clear of neon.
- **Sides:** the reference's image-left side is his LEFT throughout (egg hand, bedroll, front hip pouch,
  hood patch, tan cuff), a consistent mirror of the sheet. No egg in the hood, by request.
- **Known weaknesses:** the coat skirt is rigid on `Merchant_Hips`, so leg swings past about 25 deg poke
  through its front panels; the pack is rigid, so raising an arm straight out sideways meets the bedroll;
  the face reads best from the front (it is painted on the flat front only); colour should be judged in
  Studio, where the +0.3 saturation applies.
