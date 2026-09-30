# Boss VFX kit

This kit holds the meshes and textures behind four boss attacks: Frost Cyclops (Stomp ice wall, Ground Slam), Dragon (Fire Breath, Tail Whip, Front Stomp), Pharaoh (Cursed Bolts, Tomb Eruption) and King Crab (Claw Crush, Sideways Rush, Bubble Barrage). It also includes three shared sprites.

**Status: Blender-verified, Studio untested.** Every FBX was re-imported into Blender. Each one has the expected triangle count and size, plus an embedded PNG. None of it has been imported into Roblox Studio yet.

- `previews/Kit.png`: the contact sheet. It shows every mesh in an EEVEE ¾ view and every texture on a mid-grey checker.
- `manifest.json`: one entry per asset, with its type, file, stud or pixel size, flipbook layout, triangle count, boss and attack, and the FBX re-import check.
- `exports/fbx/<Asset>.fbx`: one mesh per file with its atlas embedded. A `<Asset>.fbm/` folder next to each file holds a plain copy of the same PNG.
- `exports/fbx/AllMeshes.fbx`: all 19 meshes spaced out in family rows, each named after its asset, for a single Studio import.
- `textures/`: every PNG. All are square and power-of-two, with 1024 px at most.

## Style

The kit follows `art-references/ART_DIRECTION_USER_2026-09-17.txt`: chunky low-poly shapes, visible flat facets with a one-segment soft chamfer on real creases, and painterly textures in 2–4 soft value bands. Glow is kept to the magic and lava pieces. The palettes were sampled by eye from the four `*-boss/previews/Comparison_SideBySide.png` sheets:

- **Ice** runs from pale white-cyan tips to deeper blue at the base, with white chamfer highlights, darker facet cores and faint lengthwise crack streaks.
- **Obsidian** is charcoal with cool-grey chamfers, like the Dragon's horns, cut by thin orange-yellow seams that fade to red.
- **Sandstone** is warm beige with carved hieroglyph bands. `Obelisk_C` has the gold pyramidion cap.
- **Crab shell** is the crab's reds with worn beige patches, beige broken edges and a beige underside.

## Conventions

- 1 Blender unit is 1 stud, Z is up, and the front faces −Y. Meshes are authored at final size, so **import at scale 1.0** and don't rescale by more than about ±15%, or the painted detail will stretch.
- The origin is at the base centre and z = 0 is the ground line. Glaciers and obelisks extend a little below z = 0 (up to 0.19 × their height) so they can rise out of the floor by tweening position or size without showing a gap. `manifest.json` lists `below_ground_studs` for each mesh.
- The FBX files were written with `axis_forward='-Z'`, `axis_up='Y'`, `path_mode='COPY'` and `embed_textures=True`, the same settings as `blender-beach-cove-kit`.
- Flipbooks are 4×4 grids of 256 px frames in one 1024² PNG, read left to right and then top to bottom (Roblox `Grid4x4`). `Hieroglyphs_Flipbook4x4` is meant for `FlipbookMode = Random`. The other flipbooks play once, from birth to fade.
- `SandBurst` and `WaterSplash` are anchored to the bottom of each frame (they erupt from the ground), so place the emitter slightly above the floor. `SandSpray` sweeps to the right; mirror it with particle rotation.
- `ShockwaveRing`, `ImpactStar` and `DustPuff` are white or light grey so they can be tinted with `ParticleEmitter.Color`.
- `MoltenRock_EmissiveMask.png` is optional and not embedded: white marks the glowing seams. The orange seams are already painted into the base colour, so the rocks read without it.

## Meshes

| asset | height × width (studs) | tris | boss / attack |
| --- | --- | --- | --- |
| IceSpike_A–E | 3.0, 5.0, 7.0, 10.0, 13.0 tall × 2.7–11.9 wide | 448, 541, 589, 735, 825 | Frost Cyclops / Stomp ice wall |
| IceShard_A–C | 0.5, 0.8, 1.2 | 74, 96, 174 | Frost Cyclops debris |
| MoltenRock_A–C | 0.8, 1.4, 2.1 wide | 192, 200, 176 | Dragon / Front Stomp, Tail Whip |
| Obelisk_A–C | 4.3, 5.8, 7.7 tall (leaning) | 818, 836, 856 | Pharaoh / Tomb Eruption |
| SandstoneRubble_A–B | 1.4, 2.2 wide | 164, 156 | Pharaoh / Tomb Eruption |
| ShellChip_A–C | 0.5, 0.8, 1.1 wide | 128, 132, 132 | King Crab / Claw Crush, Sideways Rush |

The whole kit is 7,272 triangles, and no single mesh goes over 856. There are four shared atlases: `IceSpikes_BaseColor` (1024), `Obelisk_BaseColor` (1024, which also covers the rubble), `MoltenRock_BaseColor` (512) and `ShellChip_BaseColor` (512).

## Rebuild

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python build_vfx_kit.py
```

A full run takes about 35 seconds. It repaints every texture, rebuilds and UV-maps the meshes, paints the atlases, exports and re-checks the FBX files, and renders `Kit.png` and `manifest.json`. Everything is seeded, so repeated runs give the same result. Add `-- --skip-sprites` or `-- --skip-render` to skip those steps. To repaint only the sprites without Blender, run `python paint_textures.py` (it needs only numpy).

- `paint_textures.py` holds the numpy-only painters (noise, 2D SDF shapes, 16 simplified hieroglyphs, crack trees, cartoon puff shading) and its own zlib PNG writer.
- `build_vfx_kit.py` is self-contained and doesn't `exec()` any sibling kit. It builds the meshes with bmesh (crystal prisms, convex-hull rocks, chipped blocks, obelisk and shell shapes), uses Blender Smart UV Project across each texture family together, and paints each atlas with a small numpy rasteriser. The rasteriser works from 3D position, normal and per-face tags (chamfer, gold, outer/inner/edge), so there's no Cycles bake. It then exports and re-imports the FBX files and renders the EEVEE thumbnails.

## Provenance

The kit was authored entirely inside this folder by the two scripts above: no downloads, no Creator Store models and no AI-generated images. The only inputs were the art-direction text and the four boss comparison sheets, which were used as colour and facet-size references and aren't copied here.

## Not yet verified

- Nothing has been imported into Studio yet, so the Roblox FBX import scale, the embedded-texture pickup, the MeshPart pivot (Roblox may re-centre the pivot on the bounding box instead of the base origin) and the decal and particle look in real daylight are all untested.
- Whether the emissive mask works needs a SurfaceAppearance emissive setup to be tested in Play mode. Earlier work in this project found that SurfaceAppearance images can render blank in Play, so the painted base colour is the safe default.
