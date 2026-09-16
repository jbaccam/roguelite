# Textured cliff variations — Astra revision

Five independent low-poly cliffs with rounded box corners, moderate silhouette subdivisions, small grass overhangs, gently uneven tops, and image-driven rock detail. Original pillar assets are preserved in the sibling v1 folder.

| Model | Triangles | Form |
| --- | ---: | --- |
| Short_Blocky | 574 | Short squarish pillar |
| Medium_Subtle_Taper | 574 | Broad base at 84% of upper outline |
| Tall_Curved | 862 | Vertical cliff with a mild curved axis |
| Wide_Platform | 718 | Wide low platform |
| Shoulder_Cliff | 718 | Asymmetric rounded shoulder |

Open `textured-cliff-variations.blend` for the complete editable lineup with packed textures. Actual Blender renders are in `previews/`. Individual origin-centered FBX and GLB files are under `exports/`. Model bases sit at local Z=0; lineup translations are preview placement only.

## Supplied texture roles

The three original image sheets are copied byte-for-byte to `textures/rock.png`, `grass.png`, and `transition.png`. Rock is the blue-gray source ending `11_42_57 AM (1).png`; grass is `(2).png`; transition is `11_42_58 AM (3).png`. SHA256 comparisons are recorded in `validation-report.json`. No bark, roof, water, foliage, or dirt textures are used.

The cliff sides use arc-length horizontal UVs and upright vertical UVs at a consistent nominal 10.5 model units per source image repeat. Top surfaces use planar grass UVs. The beveled upper rim uses the supplied transition image upright, with grass at its upper edge. Its lower pixels are blended into the side rock over the lower half of the rim so the two different source sheets do not create an abrupt horizontal texture seam.

Each final game mesh uses one 2048×2048 color atlas baked from those three supplied images. This derived image is color only: no baked scene lighting, generated replacement art, procedural rock detail, normal map, metallic map, or displacement. Atlas UVs stay within 0–1. Final materials are a single image feeding Principled Base Color, metallic 0, roughness .85. The low polygon geometry determines silhouette; the sheets provide the painted rock detail. Small segments use smooth shading to avoid oversized triangular lighting patches.

## Roblox import

FBX and GLB both contain one mesh and one material per variant, avoiding the problem of three Blender material slots on one MeshPart. Each has its own embedded atlas; the same atlas is also provided as a PNG in `textures/`. If the importer does not attach the color texture automatically, assign the matching `<model_name>-atlas.png` as its color texture. Keep the imported mesh color white to preserve the painted colors. Do not assign the original repeating source sheets to the final packed UVs.

No assets have been uploaded or inserted into Studio. Import scale, collision settings, and the visual result under your game's lighting still need an actual Studio check. This folder is an art deliverable and does not change gameplay or the generated world.

## Reproduction and checks

Run `generate_pillars.py` with Blender 5.2 in background mode to rebuild meshes, bake the atlases, render previews, and export. Run `validate_exports.py` afterward. Validation re-imports all five GLB and all five FBX files into empty Blender scenes, checking triangle totals, one mesh/material per file, finite nondegenerate 0–1 UVs, 2048px texture image availability, linked Base Color, and zero metallic. Original texture hash comparisons are included. These checks verify Blender round trips; they are not a claim of Roblox Studio validation.
