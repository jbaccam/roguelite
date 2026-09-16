# Rounded stackable cliff kit — Astra replacement direction

Exactly 14 main modular assets, based on the latest rounded-cliff reference sheet. These are rounded grassy chunks, stacked formations and bare support rocks. Previous pillar and wall-expansion folders remain unchanged.

1. Short squat grassy cliff
2. Medium grassy cliff
3. Tall narrow grassy pillar
4. Wide low grassy plateau
5. Broad medium-height plateau
6. Tall wide cliff mass
7. Slightly tapered grassy cliff
8. Double-stack combo
9. Triple-stack combo
10. Bare low rock filler
11. Medium boulder
12. Large boulder
13. Four-rock cluster
14. Standing/narrow rock

Open `rounded-stackable-cliff-kit.blend` for the editable complete lineup with packed images. `previews/rounded-stackable-lineup.png` is an actual Blender render. `style-preview.png` records the first three-piece style study. Individual FBX and GLB files are in their `exports/` folders; color atlases and original sheets are in `textures/`.

## Shapes and assembly

Rounded, slightly asymmetrical footprints have softly scalloped grass lips and shallow side bends. Grass tops have modest undulation while retaining usable placement area. Taper remains moderate; no pointed floating-island bases. Wide plateaus and larger masses share the same art direction as the narrow pillars. Double and triple combos contain actual overlapping tiers, not wall/corner components. Bare rocks use irregular rounded volumes with moderately angular silhouettes.

Each main export has one mesh, one image material and a ground-level local origin. Stacked combos and the rock cluster are joined meshes with disconnected/overlapping closed shells. Their visual overlap is intentional. Place independent cliffs with small overlaps; rotate to vary silhouettes. Uniform scaling is usable but changes the apparent size of the painted texture pattern. Preserve original scale when exact texture density matching matters. Choose Roblox collision settings after import, particularly for stacked shells.

## Exact supplied textures

- Cliff rock: `C:/Users/Jeremiah/Downloads/ChatGPT Image Sep 16, 2026, 11_42_57 AM (1).png`
- Grass: `C:/Users/Jeremiah/Downloads/ChatGPT Image Sep 16, 2026, 11_42_57 AM (2).png`
- New transition: `C:/Users/Jeremiah/AppData/Local/Temp/codex-clipboard-1228ecae-c585-4927-89e1-31d682f938e9.png`

The three sheets are copied unchanged as `rock.png`, `grass.png` and `transition.png`. The new transition is used, not the earlier transition sheet. Its neutral-gray lower rock differs from the blue-gray cliff sheet, so its lower rim pixels blend into the supplied blue-gray rock during the color-atlas bake. No replacement rock art is generated, and the source images are not recolored or overwritten.

Source side UVs are upright with perimeter-distance U, approximately 10.5 model units per repeat. Top grass uses 9 units per repeat. Final export UVs are packed 0–1 coordinates for one 2048×2048 color atlas per asset. Atlas baking preserves the supplied image-based appearance and resolves the edge transition without a Blender-only shader at runtime. Final materials are image color into Principled Base Color, metallic 0 and roughness .85; no displacement, procedural detail, PBR map set or baked preview lighting.

## Import and validation

FBX and GLB embed their color atlas. If an importer does not attach it, use the matching numbered `<asset_name>-atlas.png` as the color texture and keep the mesh color white. Do not apply the repeating source sheets directly to the final packed UVs.

`validation-report.json` records round trips of all 28 exports into fresh Blender scenes. Checks cover triangle totals, one mesh/material per asset, finite nondegenerate 0–1 UVs, 2048px atlas images, connected image Base Color, zero metallic, and SHA256 matches for the exact three supplied original sheets. This is not a claim of Studio import or gameplay validation. No Studio content or unrelated project source was modified.

To rebuild, run `generate_stackable.py` with Blender 5.2 background mode, then `validate_exports.py`. Add `-- --preview` for the initial three-piece study only. The generator reuses read-only helper definitions from sibling v2 and expansion scripts. The saved blend and exports are self-contained.
