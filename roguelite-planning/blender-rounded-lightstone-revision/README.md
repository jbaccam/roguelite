# Rounded cliff kit — light-stone revision

Revision of the current rounded kit, with its original dimensions and footprint family retained. The new set has the 14 revised main assets plus five moss-only variants. Earlier folders are preserved.

## Requested changes

- All cliff and rock stone uses the new lighter cool-gray image. The dark blue/purple rock sheet is not used.
- Grass rims extend farther down, up to 3.5 model units on taller assets and 45% of height on low pieces. The lower band varies around the perimeter, and the supplied transition image supplies hanging vegetation detail. The center and lower side remain predominantly stone.
- Major abrupt edges receive a small 0.10-unit single-segment chamfer, preserving low-poly forms. Tops retain modest undulations and irregular lips.
- Double and triple formations use unequal, offset elevation zones. Taller masses extend down through lower masses, so one side reads as a continuous tall rock face rather than another centered tier. The triple has zones near 3.7, 7.7 and 14.1 units high, with different widths and off-center footprints.
- Moss-only short, medium, tall pillar, wide-low and boulder variants have exposed stone tops, no grass cap, and small selected patches of moss.

## Latest source images

`textures/rock.png` is copied unchanged from `02862eb3-b09f-4d03-8bc3-ad7b57fd49a7.png`: pale stone with subtle moss in some cracks. `textures/transition.png` is copied from `62c4effc-a3a8-48f1-a138-776cdb1d9a8e.png`, the grass-to-light-stone sheet. The existing grass top remains `ChatGPT Image Sep 16, 2026, 11_42_57 AM (2).png`.

The four moss overlays are copied unchanged as `moss-overlay-1.png` through `moss-overlay-4.png`, corresponding to the supplied `04_33_16 PM (1)`, `(2)`, `(3)` and `04_33_17 PM (4)` images. Their alpha channels were read directly: all have real transparency, with roughly 57–79% fully transparent pixels. `overlay-alpha-report.json` records alpha ranges and SHA256 hashes. Their black display background is not rendered or baked as black geometry.

Moss uses localized top-edge/upper-side UV placements, not a full repeated green coating. The temporary shader composites each overlay over the light stone using its alpha, suppressing faint alpha fringe pixels, then bakes to a fully opaque color atlas. Most of each moss-only asset remains light stone. The original source images are never modified. The moss-only reference sheet is used for form guidance, not pasted onto a model as a texture.

## Files and use

`rounded-lightstone-revision.blend` contains the complete editable lineup and packed images. Individual FBX and GLB assets are in `exports/`; matching 2048px color atlases are in `textures/`. Clean actual Blender renders include the 14 revised originals, the five moss-only variants, a complete 19-piece lineup, grass-rim closeup and asymmetrical-stack closeup.

Every export has one mesh, one image material and 0–1 atlas UVs, with its placement origin on the ground plane. The nominal source mapping remains approximately 10.5 model units per stone repeat and 9 units per grass repeat. Each final material is image color into Principled Base Color, metallic 0 and roughness .85. Temporary source composition is baked; no runtime procedural effects, displacement, normal maps, or baked scene lighting are required.

If Roblox does not attach an embedded atlas automatically, assign the matching numbered atlas image as the color texture and keep mesh color white. Do not assign a repeating original sheet to final packed atlas UVs. Terrain masses are designed to overlap; stacked formations and rock clusters contain joined overlapping/disconnected shells. Set collision behavior appropriately after import rather than assuming visual interior shells are an ideal collider.

`polygon-report.json` lists triangle totals and dimensions. `validation-report.json` records round trips of every FBX/GLB into empty Blender scenes, checking one mesh/material, triangle totals, finite nondegenerate 0–1 UVs, 2048px images, image-linked Base Color, metallic 0 and exact source texture hashes. This is Blender verification, not a Studio/playtest claim. Studio and unrelated game source are unchanged.

Rebuild with Blender 5.2 using `generate_revision.py`, then `validate_exports.py`. `-- --preview` builds only the representative material/rim, double terrace and moss-only study. Scripts reuse read-only shape helpers from the prior rounded kit and its siblings; the final blend and exports are self-contained.
