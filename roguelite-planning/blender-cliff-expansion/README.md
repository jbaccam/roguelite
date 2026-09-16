# Modular cliff expansion — Astra

26 additional modules for building a broad mountain-ring arena. The approved five-piece v2 kit is preserved. This deliverable supplies modular terrain assets and presentation lineups; it does not assemble or alter a Roblox map.

## Contents

| Category | New modules |
| --- | --- |
| Grassy walls and terrain | Long wall, concave wall, convex wall, inward corner, outward corner, sloped height wall, stepped height wall, broad platform, moderate overhang wall |
| Exposed rock | Long wall, concave wall, convex wall, organic corner, vertical buttress, eroded notch wall |
| Scatter and seam fillers | Low base filler, small boulder, medium boulder, large boulder, standing rock, four-rock cluster, broken rubble |
| Special modules | Shelf wall, tree shelf wall, path cut-through, distant mountain backdrop |

Open `modular-cliff-expansion.blend` for the complete editable collection. Grouped, labeled actual Blender renders are in `previews/`. Every piece has an individual FBX and GLB under `exports/`, a color atlas under `textures/`, and dimensions, triangle counts and usage notes in `polygon-report.json`.

## Matching the existing kit

Primary rock remains the blue-gray sheet from `ChatGPT Image Sep 16, 2026, 11_42_57 AM (1).png`. Grass remains `(2).png`; the original transition remains `11_42_58 AM (3).png`. All three are copied unchanged and SHA256 checked against the user-supplied originals. The additional neutral-gray rock sheet and the newly supplied transition were inspected; they are references/alternatives, not silent replacements for the explicitly requested existing blue-gray palette.

Nominal source UV scale matches v2: side rock 10.5 model units per repeat, grass 9 model units per repeat. Side U follows perimeter arc length and V stays upright. The grass-edge transition uses the existing sheet with its lower part color-blended into side rock, then baked into the final atlas. No procedural detail, new generated textures, baked lighting, displacement, normal or metallic textures are used. The final material has one color image feeding Principled Base Color, metallic 0 and roughness .85. Geometry has moderately subdivided profiles and subtly irregular grass tops; texture supplies most detail.

Every final export has one mesh, one material and 0–1 atlas UVs. Most color atlases are 2048×2048; the much larger distant backdrop uses 4096×4096. These atlas resolutions change image sampling quality, not the nominal world size of the painted rock pattern. Atlas files are derived from the supplied sheets; originals are retained untouched.

## Assembly conventions

All exports use a local ground-level origin and Blender Z-up modeling coordinates. Intended front faces point toward negative Y before export axis conversion. Rotate modules to follow the perimeter. Most gameplay walls are approximately 24–26 wide, 7–8 deep and 10–12 high. Sloped and stepped pieces connect lower and upper tiers. Corners and wall ends are deliberately organic overlap modules, not precision sockets: overlap ends by roughly 1–2 model units and cover junctions with buttresses, low fillers or rock clusters. Avoid nonuniform scaling when matching source texture scale.

Shelf Wall combines a high wall with a 13×8 lower ledge; Tree Shelf has an 8×8 lower ledge. Place props only on the exposed shelf area, allowing space for the rear wall overlap and grass lip. Path Cut Through provides a ground-level opening between two cliff shoulders, approximately 6.5 units clear; it leaves space for your own dirt path. It does not include a dirt texture or a sloped path mesh. The slope wall supplies a continuous top elevation grade, while the stepped wall is a ledge transition, not a walking ramp.

Cluster, rubble, shelf, step and path modules can contain joined overlapping or disconnected closed shells. This is intentional for static environment dressing. Choose appropriate Roblox collision behavior after import; detailed collisions around rubble or composite shelf interiors should not be assumed from visual geometry alone. The distant backdrop is intended behind the playable perimeter, not as a walkable mountain.

## Roblox import and verification

FBX and GLB each embed the matching atlas. If the importer does not attach the image, use the corresponding `<model_name>-atlas.png` as the color texture and keep mesh color white. Do not apply the original repeating sheets to final packed atlas UVs. Each file uses one material, avoiding multiple Blender material slots on a single MeshPart.

`validate_exports.py` reimports all 52 FBX/GLB files into fresh Blender scenes and checks triangle totals, one mesh/material, finite nondegenerate 0–1 UVs, atlas pixel dimensions, available texture images, linked Base Color and zero metallic. `validation-report.json` records results and original-source SHA256 checks. Source textures and every atlas are packed into the blend. These are Blender round-trip checks, not a claim of Studio import or gameplay testing. No Studio content, uploads, trees, props, or gameplay source files were modified.

To regenerate, run `generate_expansion.py` in Blender 5.2 background mode, then `validate_exports.py`. The scripts reuse the approved sibling v2 material setup and validation logic, so retain `blender-cliff-pillars-v2` alongside this folder when rebuilding. The blend and exports themselves are self-contained.
