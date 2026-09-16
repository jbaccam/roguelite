# Place1 import evidence

Imported the latest 19 light-stone assets through Studio's standard File > Import multi-file FBX queue, using creator **Me**. The existing FBX files and embedded baked atlases were uploaded unchanged. No substitute geometry was generated. The complete asset-ID mapping is in `studio-import-manifest.json`.

All 19 models live under `Workspace.RogueliteCliffPack`, with one anchored MeshPart and its matching TextureID per model. Placement begins at X=160, Z=40 with 28-by-30-stud spacing, away from the existing spawn. Labels are removable BillboardGui children. Model pivots and MeshPart pivot offsets are ground-level. Baseplate and SpawnLocation were preserved; no gameplay scripts were added.

The importer interpreted FBX dimensions at 100 times authored size; two wide models also reached Studio's 2048 size limit. Each imported MeshPart Size was explicitly restored from `polygon-report.json`, mapping Blender XYZ to Roblox XZY. This avoids assuming a uniform post-import scale for the clamped models. Source textures remain correctly mapped by their existing UVs.

Verified in Edit mode: 19 models, 19 MeshParts, 19 nonempty uploaded mesh IDs, 19 matching nonempty atlas TextureIDs, and 19 anchored MeshParts. Actual viewport inspection confirmed light stone, grass tops, rounded contours, asymmetric terraces, and sparse moss-only variants. `studio-verified-lineup.png` is a real Studio viewport capture, not a Blender render or concept image.

`studio-organize-import.luau` documents the organization and normalization operation following the standard FBX imports. It deliberately refuses to run if the destination already exists. It is not a standalone mesh-upload script. The manifest records uploaded cloud mesh/texture IDs for subsequent authorized reuse; a different experience or owner may need asset-use permission from the owning account.

The current Place1 was not published, saved over an existing file, or closed. Save the place normally when ready. No multiplayer gameplay or published-permission testing was performed; this was an Edit-mode static asset import.
