# Handyman turret (Tiers I–IV)

This is the turret the Handyman class can build. It is one stand-and-head design that gets more parts as it upgrades, like gear rarity. It belongs with the Nail Gun / Wrecking Ball toolbox weapons: a yellow nail-gun head, charcoal gunmetal, orange feet and pads, and hazard stripes. Each tier adds a stripe in its tier colour from `studio-prototype/ui/UITheme.luau` (`T.Tier`).

**Status: Blender-verified, Studio untested.** `validate_exports.py` passes all four tiers (`validation-report.json`). Nothing has been imported into Studio or play-tested.

| Tier | Design | Triangles (budget) | Height / radius |
|---|---|---|---|
| I | Plain tripod with orange feet. Single heavy nail-gun head with a nail magazine, power-tool battery, dark visor slits, a hazard band on top and cream tier stripes. | 2,144 (3,000) | 3.41 / 1.78 |
| II | Braced tripod with a hazard triangle. Armoured head with tilted side shields (blue top edge), twin barrels on a receiver, red toolbox ammo box with a nail-strip feed. | 3,388 (4,500) | 3.93 / 2.15 |
| III | Four hazard-striped outriggers on screw-jack pads. Quad barrels with a purple band, layered yellow shield armour, orange nail drum with a brass/steel belt, amber warning beacon, amber visor. | 5,568 (6,000) | 4.39 / 2.24 |
| IV | Outriggers with rebar spikes. Six-barrel gatling. Big swept shield wings with yellow leading edges, rebar spikes and Neon seams. Heavy brow with a red arrowhead, glowing eye slits, a Neon hex core on the deck, vented rear block with twin swept exhausts, drum and belt. | 7,886 (8,000) | 5.11 / 2.42 |

Previews: `previews/lineup.png` (all four tiers with a 5-stud block figure), `previews/HandymanTurret_T{n}_3q.png`, `previews/hero_T4.png`.
Shop/HUD icons: `previews/icon_T{n}.png`, 512 × 512, transparent, with the chest kit's icon lighting.

## Model contract

- **Files:** one FBX per tier, `exports/fbx/HandymanTurret_T{n}.fbx`, plus a GLB in `exports/glb/`.
- **Meshes:** each file holds the meshes `HandymanTurret_T{n}_Base`, `_Head` and `_Barrel`. T4 adds `HandymanTurret_T4_Glow`. Names are unique per tier and the meshes are not parented.
- **Transforms applied:** each mesh origin sits at its pivot.

| Part | Pivot | Moves |
|---|---|---|
| Base | Ground centre | Static |
| Head | On the yaw axis at the bearing top | Yaws |
| Barrel | Trunnion | Pitches about X and recoils toward +Z (backwards) |
| Glow (T4) | Same as Head | Weld it to the Head |

On T4 the whole Barrel spins about its own forward axis through the Barrel pivot (`spin: true`).

- **Axes:** a Blender point (x, y, z) lands in Roblox at (-x, z, y). At rest the barrels point to Roblox -Z, which is the model's LookVector.
  - The export settings are the same as the chest kit's: `axis_forward -Z`, `axis_up Y`, textures embedded.
  - In the raw file, each node carries the usual -90° X axis rotation. Studio's importer turned the chest, armory and island kits 180° about Y, which is what produces (-x, z, y).
  - `validate_exports.py` re-imports the FBX with no axis conversion and checks that the file is Y-up, with the barrel tips at the spec's muzzle Z after that turn.
- **Spec:** `exports/turret-spec.json` is in Roblox axes and studs, relative to the Base pivot. It has one entry per tier:
  - Per part: `pivot`, `center` and `size` (the part's bounding box) and `pivotOffset` (= pivot − centre).
  - `muzzles` (one per barrel tip), `muzzlesFromBarrelPivot` and `muzzleCentre`.
  - `height`, `radius`, `triangles`, `texture` and `spin`.
  - Glow carries `parent: "Head"`.
- **Textures:** `textures/HandymanTurret_T{n}.png` is a 1024 px baked colour map at 8 samples. Base, Head and Barrel share it on UV channel 1.
  - Put it on `MeshPart.TextureID`. SurfaceAppearance renders white in Play here.
  - `textures/source/*_paint.png` is only the painted atlas that the bake reads.

### Studio notes for the code agent

- **Import:** use File > Import 3D with default settings, at 1:1 scale.
  - Never scale more than ±15%. The baked 0–1 atlas cannot re-tile.
- **Normalise the import:** the importer has turned files before, and once laid one on its back. A MeshPart's CFrame sits at its bounding-box centre. So:
  - Match the imported parts against the spec's `center` and `size`, the same way `blender-chest-kit/studio-install-chests.luau` searches for the right turn.
  - Then set each part's pivot to `pivotOffset`.
- **Textures and Neon:**
  - If the importer adds a SurfaceAppearance, convert it to `TextureID`.
  - The Glow part becomes Neon in `glow_srgb` (248, 88, 99), the tier IV colour.
- **Muzzles:** to aim and fire, take `muzzlesFromBarrelPivot` in the Barrel's own frame. For T4, use `muzzleCentre`, or rotate the six muzzle points with the spin.

## Rebuild

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python generate_turret.py
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python validate_exports.py
```

- Options:
  - `-- --quick --out=<dir>` runs a flat-colour shaping pass: no bake, no exports, and four contact renders, including one at about in-game pixel size.
  - `-- --tiers=2,4` builds only those tiers.
- `generate_turret.py` is self-contained. It paints the atlas with numpy inside Blender, so it needs no system Python.
- How each piece is built:
  - Every piece is welded and bevelled on its own, with a 0.05-stud chamfer on edges sharper than 32°. Facets steeper than 30° stay crisp.
  - UVs are assigned after the bevel from each face's material tile, so the chamfers never smear across the atlas.
- The bake is the chest kit's icon lighting:
  - a top-front-left key light, AO and a height gradient;
  - a cool rim light;
  - warm highlights on the bevelled edges.
- No `.blend` is kept, because the script rebuilds everything. Outputs are deterministic.
