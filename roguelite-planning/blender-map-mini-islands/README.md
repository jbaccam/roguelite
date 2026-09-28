# Map-select mini islands

There is one small floating island per map, used as a blurred background behind the map-select screen. The reference was a map selector from another Roblox game, supplied on 2026-09-27: a map name over a blurred floating island. Each island is a small version of its arena that carries the map's main props.

| Map | Script | Island mesh tris | Total tris | FBX |
|---|---|---|---|---|
| Pine Valley | `build_pine_valley.py` | 8,220 | 50,214 (15 evergreen + 3 log instances) | 11 MB |
| Beach Cove | `build_beach_cove.py` | 7,920 | 20,313 (beach-kit palms, rowboat, driftwood, tide pools) | 24 MB |
| Desert | `build_desert.py` | 16,070 | 16,070 | 4.3 MB |
| Frozen Pass | `build_frozen.py` | 16,134 | 63,024 (15 snow pines) | 6.5 MB |
| Volcanic Crater | `build_volcanic.py` | 12,114 | 13,710 (+ `Volcanic_Lava` glow mesh) | 4.1 MB |

## Shared rules

- `island_lib.py` is shared by all five scripts. It covers the painterly materials, the island body (top, soil/edge band, stepped rock underside, spires, drips), rocks and cliff blocks, master instancing, the atlas bake, the preview rig and export. Each map script imports it and does not exec sibling kits.
- 1 unit = 1 stud. Radius ≈ 30, depth ≈ 26, and the top is at z = 0.
- Every map uses the same three cameras (`hero`, `closeup`, `side`), so the islands line up in the menu.
- The procedural geometry is baked to one 2048 diffuse atlas per island (`textures/<map>-island-atlas.png`).
- Project masters are placed as separate meshes, each with its own mesh copy, because the FBX exporter drops the material on the second and later objects that share one mesh. The masters used are `Evergreen_Master`, `Log_Master` and the beach-kit palms, rowboat, driftwood and tide pools.
- The bake is diffuse-only, so emission is lost. Volcanic keeps everything that glows in `Volcanic_Lava` with its own 512 atlas; set it to Neon in Studio. The Pine Valley campfire and the Frozen Pass lantern are baked colour only.

## Build

```
blender --background --factory-startup --python build_<map>.py
python make_menu_mock.py <stem> "<TITLE>" [fog_hex]
```

Each build writes `previews/<stem>-{hero,closeup,side}.png`, `exports/{fbx,glb}/<stem>-mini-island.*`, `<stem>-report.json` and `<stem>-mini-island.blend`.

`make_menu_mock.py` blurs the hero render and adds a title, as a rough approximation of the menu. It is not UI.

## Verification status

All five were built, rendered and reviewed in Blender 5.2, with several look passes each. Pine Valley was approved by the user; the other four were built from it.

**Studio install (2026-09-27):** all five FBXs were imported with Studio's 3D Importer (default preset, scale 1, atlases on `MeshPart.TextureID`) into the roguelite place and normalized by `studio-install-islands.luau` into `ReplicatedStorage.MapSelectIslands.<MapId>` (PineValley, BeachCove, DesertBasin, FrozenPass, VolcanicCrater), each pivoted at its island origin (top at y = 0), anchored, non-colliding and non-queryable. `Volcanic_Lava` is Neon orange; the importer had put it on a SurfaceAppearance, which the installer replaces with `TextureID`. The importer turns the islands 180° about Y relative to the GLBs (bounds in `studio-island-bounds.json`), so the Blender front camera is at Studio (0, 34, −118). The run-setup screen shows them through `studio-prototype/ui/MapSelectBackdrop.luau`; all five were checked in a Play client (locked maps shown as grey silhouettes). Beach Cove's reused kit props are scaled 0.4–0.8, which breaks that kit's constant texture-density rule. That is acceptable for a blurred background, but don't reuse those scaled copies in gameplay.

## Provenance

All geometry is authored in these scripts or imported from the project's own exported masters: `blender-master-evergreen`, `blender-master-log` and `blender-beach-cove-kit/exports/glb`. There is no Creator Store content.

The layouts follow the user's arena screenshots, and the concepts are in `../map-concepts/`. For the desert, the user's screenshot with cacti, ribcages and an obelisk takes precedence over the older concept README note.
