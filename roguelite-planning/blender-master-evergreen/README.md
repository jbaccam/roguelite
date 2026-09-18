# Evergreen master asset

One reusable evergreen tree, created in Blender from the supplied reference. Four overlapping scalloped foliage tiers plus a small pointed crown, one straight tapered trunk with a restrained split/flared foot. Scale uniformly for size variation. The master has 1,260 vertices and 2,496 triangles, with one material and one UV map.

## Files

- `Evergreen_Master.blend` — editable master and preview studio. The color atlas is packed. The asset is the single mesh in `ASSET • one master tree`; preview ground, camera, and lights are separate.
- `Evergreen_Master.fbx` — one triangulated mesh with one material and embedded color atlas, ready for a Roblox 3D Importer workflow.
- `Evergreen_Master.glb` — the same single tree with embedded color texture.
- `Evergreen_Preview.png` — actual Blender render of the exported master geometry.
- `textures/Evergreen_Color.png` — 2048×1024 padded sRGB color atlas, assembled from the two provided textures without recoloring.
- `textures/foliage_original.png`, `textures/bark_original.png` — unchanged original source textures.
- `asset_stats.json`, `verification.json` — geometry and round-trip checks.
- `build_tree.py`, `verify_tree.py` — reproducible Blender generation and validation scripts.

## Use

The pivot is centered at ground level, the model has identity object scale, and its authoring height is 18 units. Width is approximately 10.55 units. In Blender, select `Evergreen_Master` and scale uniformly. In Roblox, import the FBX as one MeshPart and set its color to white; if texture transfer is unavailable in the importer, upload `textures/Evergreen_Color.png` and assign it as the mesh color texture. Choose the desired import scale, then scale the complete asset uniformly. Mesh geometry is opaque and needs no leaf-card transparency.

The single mesh contains six closed, intentionally overlapping shells (trunk, four skirts, crown). Vertex groups identify these sections for editing. The UVs use one cylindrical seam per shell and intentional reuse of the foliage atlas region across tiers. Caps are mapped within the corresponding image region. This is a color-textured prop, not a unique lightmap unwrap.

Verification includes reimporting both exported formats, checking one tree mesh, one material, UV bounds, nonzero triangle areas, bottom-center origin, and closed topology after merging export-split vertices. Roblox Studio import and gameplay behavior have not been tested or modified.

## Provenance

All geometry was authored for this request. The reference and two textures were supplied by the user:

- Reference: `ChatGPT Image Sep 16, 2026, 06_08_01 PM.png`
- Foliage: `ChatGPT Image Sep 16, 2026, 06_10_48 PM.png`
- Bark: `ChatGPT Image Sep 16, 2026, 06_07_54 PM.png`

No Creator Store geometry, generated texture replacements, or additional tree variants are included. The preview is a model render, not an AI-generated stand-in.
