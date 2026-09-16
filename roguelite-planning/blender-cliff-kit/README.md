# Roblox Modular Cliff Kit

This folder contains an original, low-poly cliff kit for assembling broad circular Roblox arenas. The meshes borrow only the general production idea of large stylized cliff modules; no geometry or textures were copied from the visual references.

## Start here

- `roblox-modular-cliff-kit.blend` — editable Blender source.
- `generate_cliff_kit.py` — fully reproducible generator, assembler, renderer, and exporter.
- `exports/fbx/` — individual Roblox-oriented FBX modules plus the sample ring.
- `exports/glb/` — matching GLB exports for quick inspection or alternative import.
- `previews/` — rendered overview images.
- `polygon-report.json` — dimensions and polygon counts produced by the generator.
- `validate_exports.py` / `validation-report.json` — headless round-trip import check for every FBX and GLB.

The source file is organized into exactly these working collections:

- `Modules` — the reusable authored pieces, arranged as a catalog.
- `SampleAssembly` — eight repeated 45-degree pieces around an open center.
- `CollisionGuides` — simple wireframe collision suggestions; these are excluded from exports and renders.

## Included pieces

| Piece | Intended use | Nominal dimensions |
| --- | --- | --- |
| `Cliff_Straight` | Straight borders or distant wall runs | 22 long × 8 deep × ~10 high |
| `Cliff_Curve45` | Main arena rim; eight copies complete a circle | 45°, inner radius 36, outer radius 44, ~10 high |
| `Cliff_Curve22` | Shorter curved filler and variation | 22.5°, inner radius 36, outer radius 44, ~7 high |
| `Cliff_PillarMesa` | Tall silhouette, seam cover, background mesa | ~14 diameter × ~17 high |
| `Cliff_SteppedTerrace` | Layered perimeter variation | Three connected levels, ~14 high maximum |
| `Cliff_Arch` | Scenic opening or interrupted wall section | 20 wide × 8 deep × ~14.7 high |

Each major module has separately named `Rock` and `TopCap` objects. The cap is deliberately separate so grass can become snow, sand, clay, or dark volcanic stone without remodeling the rock wall.

## Building a circular arena

`Cliff_Curve45` is authored around the world origin with its pivot at the center of the intended arena.

1. Import `cliff-curve45.fbx`.
2. Keep the imported model at the arena center.
3. Duplicate it seven times.
4. Rotate the copies around vertical Y in Studio by `0, 45, 90, 135, 180, 225, 270, 315` degrees.
5. The resulting visual wall leaves an approximately 71-stud-wide clear center (35.5-stud gameplay radius in the sample).
6. If a larger arena is needed, scale the entire ring uniformly. Do not move individual curved pieces radially unless you also accept small gaps.

The combined `sample-circular-arena.fbx` demonstrates the full eight-piece ring and includes a simple floor. It is a visual example, not a required production hierarchy.

The `Cliff_Curve22` piece uses the same center-pivot convention. Sixteen copies at 22.5-degree increments complete a ring. It can also be alternated with taller pieces as visual filler.

## Roblox Studio import notes

These exports were generated with Blender 5.2.1 LTS using FBX forward `-Z`, up `Y`, applied scale, and no armature data.

Recommended workflow:

1. Import one FBX through Studio's 3D Importer first and confirm scale against a Roblox avatar.
2. Treat one Blender unit as one nominal stud for layout, then apply one consistent import scale to the entire kit if Studio's unit conversion differs in your pipeline.
3. Preserve separate objects so `Rock` and `TopCap` arrive as independently recolorable MeshParts.
4. Set every visual MeshPart to `Anchored = true`, `CanCollide = false`, `CanTouch = false`, and `CanQuery = false` unless selection is needed.
5. Use automatic or box collision only for distant pieces if collision cannot be disabled.
6. Prefer the FBX files for Studio. GLB files are supplied as a convenient inspection/fallback format.

The meshes use only flat material colors and no external image textures. If Studio does not preserve Blender material colors in the desired way, assign Roblox `Color`/`Material` after import. Because the cap is a separate object, biome recoloring remains simple.

Suggested palettes:

- Pine Valley: slate gray rock + medium grass green cap.
- Desert: warm terracotta rock + pale clay/sand cap.
- Frozen Pass: blue-gray rock + off-white snow cap.
- Volcanic Crater: charcoal rock + near-black basalt cap.
- Beach Cove: desaturated tan rock + dry grass or sand cap.

## Collision recommendation

Do **not** use the detailed visual cliff mesh as the authoritative arena boundary.

- Build the real boundary from 16–24 invisible anchored Parts placed tangentially around the circle.
- Keep these Parts in a dedicated `BoundaryCollision` model.
- Use ordinary block collision so players and enemy navigation receive predictable results.
- Leave the visible cliff MeshParts non-collidable.
- Keep spawn regions and pathing limits several studs inside the collision boundary.

The Blender `CollisionGuides` collection shows the intended idea but is intentionally omitted from export. Recreate the boundary with native Parts in Studio so it remains easy to resize and debug.

## Editing the kit

- Recolor the `MAT_TopCap_Grass` material or replace each `TopCap` object's material.
- Edit rock materials `MAT_Rock_Base`, `MAT_Rock_LightFacet`, `MAT_Rock_MidFacet`, and `MAT_Rock_DarkFacet` for a biome palette.
- Keep the two radial ends of `Cliff_Curve45` unchanged if pieces must remain perfectly repeatable.
- Add silhouette variation toward the middle of a piece, not at its snap edges.
- Avoid applying subdivision or dense sculpting; the broad triangular planes are intentional.
- Hide seams with a few low-cost rocks, shrubs, logs, snow piles, or obsidian clusters placed outside the playable center.

## Regeneration

From PowerShell:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  --background `
  --python 'C:\Users\Jeremiah\Documents\ChatGPT\Roblox\roguelite-planning\blender-cliff-kit\generate_cliff_kit.py'
```

The generator replaces the generated `.blend`, exports, previews, and polygon report deterministically. It does not access or modify project content outside this folder.

## Validation status

- Generated and rendered headlessly in Blender 5.2.1 LTS.
- Individual FBX and GLB exports were produced for every module.
- Combined sample FBX and GLB exports were produced.
- Polygon counts are recorded in `polygon-report.json`.
- Roblox Studio import has **not** been tested yet. Scale, material transfer, and the final invisible Part boundary should be verified in Studio before production use.
