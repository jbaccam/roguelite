# Chest kit

Treasure chests for the lobby chest area and the chest-opening reveal
(see `../STORE_AND_CHESTS.md`). One shared shape, one look per chest tier.

Five chests, one per price (see `../STORE_AND_CHESTS.md`). Godly is a drop rarity, not a chest.
**Every tier keeps the Wooden chest's shape** (rectangular body, barrel lid, straps, bands, corner
guards, front lock, seam glow) and gets way cooler and nicer through richer materials and crafted
detail built into the chest, like Clash Royale chest tiers. The user rejected recolours with an
icon on top, and also rejected completely different silhouettes. Higher tiers start as a copy of
`tiers/wooden.py` and upgrade it.

| Tier | Emeralds | Chest | Status |
|---|---|---|---|
| Wooden | 60 | Orange planks, dark iron straps, hex lock, lantern glow | Built, Blender-verified, Studio untested |
| Silver | 160 | Cobalt boards, polished steel, ribbed straps, armoured corners with sapphires, shield lock, lid ridge rail | Built, Blender-verified, Studio untested |
| Gold | 300 | Walnut, heavy gold, double trims, ruby-studded straps, scroll corners, lion-paw feet, crest medallion, coins in the seam | Built, Blender-verified, Studio untested |
| Magical | 700 | Rebuilt 1:1 from the user's dark-fantasy reference: two big end arches on stacked-block legs, purple boards lit blue from the seams, a lock traced from the user's sketch, low horns with steel caps, a sculpted stitched skull (`Chest_LidSkull`), base rail on ball feet; the arch tops, horns and skull open with the lid | Built; **in Studio 2026-09-28** (ChestModels + chest island, checked in Play) |
| Legendary | Robux / rewards | Built on Gold's shape from the user's gold-crown reference: red-orange lacquer, mostly heavy gold, a solid crenellated crown rim around the lid, turquoise gems, an octagonal glowing-gem lock, scroll feet, a glowing treasure mound | Built, Blender-verified, Studio untested |

Previews are real Blender renders of the exported geometry (`previews/lineup-true-scale.png` shows all five in one scene at true size, rendered by `lineup.py`):
`previews/wooden-closed.png`, `previews/wooden-open.png`, `previews/wooden-front.png`.

## Shape and style

- **Shape reference:** the rounded-lid chests the user supplied on 2026-09-27. Those were screenshots
  from another Roblox game, used for silhouette only, and no files from it are kept here. The shape
  has a barrel lid, two straps over the lid lining up with straps on the body, a rim band at
  the seam, corner guards, chunky feet, a hex lock plate straddling the seam, and light leaking
  from the lid gap.
- **Style:** our brief (`../art-references/ART_DIRECTION_USER_2026-09-17.txt`), pushed toward the
  user's weapon icons (`studio-prototype/ui/assets/weapons/`). On 2026-09-27 he asked for the chest
  to be "a little more cartoony… like some of my assets". That means:
  - Chunky, oversized parts: thick bands, big domed bolts, a big hex lock, a proud domed lid.
  - Every plank is its own bevelled board, so the seams are real grooves.
  - **Baked icon lighting:** the painted atlas is combined with a per-facet key light
    (top-front-left), ambient occlusion, a height gradient, a cool back-right rim light and bright
    bevel-edge highlights. All of it is baked into `textures/chest-<tier>-baked.png` on unique UVs,
    so Roblox shows the icon look on top of its own lighting.
- Each box, band, board and bolt is welded and bevelled on its own before joining. Welding the
  whole part at once merges pieces that touch at a corner, and the bevel's overlap clamp then
  silently shrinks every chamfer to zero.

## Parts

All parts share one origin (ground centre, front faces -Y in Blender / -Z in the FBX).
Modelled at final Roblox stud size: **import at 1:1, do not scale**. The chest is about
6.5 × 5.2 × 5.4 studs.

| Part | Roblox use |
|---|---|
| `Chest_Base` | MeshPart, TextureID = `textures/chest-<tier>-baked.png` |
| `Chest_Lid` | MeshPart, same baked texture. Opens by rotating about the hinge (see `polygon-report.json` `hinge_studs`), X axis, up to about 105°, front lifting |
| `Chest_Glow` | Seam light and keyhole. Neon, colour = tier `glow` (sRGB). Fade it out as the lid opens |
| `Chest_Inner` | Glowing floor seen when open. Neon, same colour |

The Wooden tier is 3,956 triangles in total. Exact counts per part are in `polygon-report.json`.

## Rebuild

```
python author_textures.py wooden
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python generate_chest.py -- wooden
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python validate_exports.py
```

- `author_textures.py` needs system Python with numpy and Pillow.
- Add `--preview` after the tier to render without exporting.
- `validation-report.json`: FBX and GLB re-imported. Four parts each, triangle counts and
  dimensions match the report, UVs inside 0–1, no zero-area faces.

## Adding a tier

Everything tier-specific lives in **one file, `tiers/<tier>.py`**, including the entire shape.
`tiers/wooden.py` is the worked example. The shared scripts (`generate_chest.py`,
`author_textures.py`, `validate_exports.py`) are **not edited per tier**, so tiers can be built
in parallel. Each tier writes only:
- `tiers/<tier>.py`
- `textures/chest-<tier>*.png`
- `previews/<tier>-*.png`
- `exports/*/chest-<tier>.*`
- `polygon-report-<tier>.json` and `validation-report-<tier>.json`
- `chest-<tier>.blend`

A tier file is plain Python at the top level (no `bpy`, `mathutils` or numpy imports). It defines:

- `NAME`, `GLOW` (sRGB; the Roblox Neon colour of the seam/keyhole light and the open floor)
  and optionally `ACCENT` (sRGB for always-on Neon accents; defaults to `GLOW`).
- `PALETTE`, painted by `author_textures.py`:
  - Primary surface: `wood`, `wood_dark`, `wood_light`, `gap`.
  - Metal/trim: `metal`, `metal_dark`, `metal_light`.
  - Flat swatches: `rivet`, `keyhole` (dark), `gem`, plus optional `swatch4`–`swatch6`.
- Optionally `paint_primary(np, rng, w, h, p, tools)` and/or `paint_metal(...)`, to paint your own
  primary surface (enamel panels, enchanted stone, lacquer…) or metal instead of planks and iron.
  - Return a float32 `(h, w, 3)` array in 0–1.
  - `tools` has `smooth_noise`, `col`, `lerp` and `BANDS`.
  - Keep 16 horizontal bands if you use `band_uv`.
- Optionally `CHAMFER` (default 0.06 studs), `SHARP_DEG` (default 30) and `BAKE` (a dict of
  overrides of `BAKE_DEFAULTS` in `generate_chest.py`).
- **`build(k)`** returns `{"parts": {name: (builder, kind)}, "hinge": (x, y, z) or None, "open": {...}}`.
  - Kinds:
    - `"textured"`: bevelled and baked; all textured parts share one texture.
    - `"glow"`: Neon in `GLOW`, hidden when the chest is open.
    - `"floor"`: Neon in `GLOW`, seen when open.
    - `"accent"`: Neon in `ACCENT`, always on.
  - Parts named `Chest_Lid…` move together when opening. With a hinge, they rotate about X by
    `open.rotate_x_deg` (default 105, front lifts). `open.lift` (studs) raises them straight
    up, for a floating lid.
  - Use at least `Chest_Base` (textured) and `Chest_Lid…` (textured). Add glow, floor and accent
    parts as the design needs.
  - Builder (`k.Builder()`):
    - `box(x0, x1, y0, y1, z0, z1, uvf)`
    - `ring(...)` for a rectangular band
    - `prism((x, z), r, sides, y_front, y_back, uvf)`, facing -Y
    - `rivet(x, z, y_surface, size)`
    - `loft(rings, uvf)` to skin rings of points into a solid: tapered bodies, domes, crystals,
      horns, claws, wings
    - `begin()` + `poly(points, uvs)` for anything else
    - Every primitive is its own bevelled piece; `chamfer=` overrides the bevel per piece.
  - `k` also gives:
    - `Vector`, `math`, `offset_profile`
    - uv functions `k.metal`, `k.dark`, `k.gem`, `k.swatch(name)` (pass as `uvf`)
    - `k.primary_uv(a, b, band, plank)` and `k.band_uv(a, t, band, plank)` for primary-surface
      faces, and `k.metal_uv(s, t)`
  - Coordinates are studs: Blender Z-up, ground at z=0, front faces -Y. Model at final size.
  - **Full Blender modelling:** inside `build(k)` a tier may `import bpy, bmesh` and put a
    finished mesh **object** in the parts dict instead of a Builder. The object must:
    - be at final size with its bevels applied;
    - carry a `"UVMap"` layer addressing the painted atlas.

    The pipeline assigns the material and bakes it like any textured part.
- Optionally `LIGHTS = [((x, y, z), (r, g, b), watts), …]`: point lights for the Blender previews,
  such as a magic chest's blue glow. They're recorded in the report so matching PointLights can
  be placed in Studio.

To re-send one tier to Studio: `blender --background --python package_studio.py -- <tier>` writes
`exports/fbx/chest-kit-studio-<tier>.fbx` and merges its entry into `studio-install-data.json`;
update that tier's entry in `studio-install-chests.luau`, import the FBX (Studio defaults), run the
installer with `ONLY = "<Tier>"`, then re-run `studio-prototype/lobby/InstallChestIsland.luau`.

Build and check:

```
python author_textures.py <tier>
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python generate_chest.py -- <tier>
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python validate_exports.py -- <tier>
```

- Add `--preview` after the tier to render without exporting.
- The camera pulls back automatically for bigger chests.

**Style bar.** Compare the three previews with `previews/wooden-*.png`:
- It must be the *same chest shape*, but clearly more lavish than the tier below. A recolour
  with an ornament on top fails, and so does a different silhouette.
- It must share the finish: chunky readable forms, soft bevels, visible facets, baked icon
  lighting, and colour as rich as the weapon icons (`studio-prototype/ui/assets/weapons/`).
- Use Neon only for glows and a few accents.
- No fine filigree.

`textures/chest-<tier>.png` is only the painted *source* the bake reads. Its layout is shared by
both scripts:
- u 0–0.75: 16 plank bands
- u 0.75–1, v 0.375–1: metal
- u 0.75–1, v 0–0.375: swatches for rivet, dark and gem

The body shows exactly four planks per face (`PLANK = HB / 4`).

## Studio install (all tiers at once)

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python package_studio.py
```

- Reads the saved `chest-<tier>.blend` files and writes:
  - `exports/fbx/chest-kit-studio.fbx`: every tier in one file (Empty `Chest_<Tier>`, parts `<Tier>_Chest_Base` …).
  - `studio-install-data.json`: each part's kind, centre and size in Studio axes, and the hinge.
  - `previews/icon-<tier>.png`: the transparent UI icons (uploaded ids in `../studio-prototype/ASSETS.md`).
- In Studio: **File > Import 3D** `exports/fbx/chest-kit-studio.fbx` (default settings), then run
  `studio-install-chests.luau`. It builds `ReplicatedStorage.ChestModels.<Tier>`:
  - pivot at the ground centre, front along the pivot's LookVector;
  - part attributes `Kind` (textured / glow / floor / accent) and `Lid` (swings open);
  - model attributes `Hinge` (CFrame in pivot space) and `OpenDeg`;
  - textured parts on `TextureID`, glow parts Neon in the ChestConfig colours.
- Then run `../studio-prototype/lobby/InstallChestIsland.luau` to put them on the chest island.
- Re-doing one tier (e.g. Magical): rebuild it, re-run `package_studio.py`, import the FBX, set
  `ONLY = "Magical"` in the installer, run it, then re-run the island installer.
