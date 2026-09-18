# Fallen log

One stylized reusable fallen log modeled in Blender from the supplied reference: a long irregular polygonal trunk, four short cut branch stubs, exposed muted wood rings and tapered splits at the ends.

- `Log_Master.blend`: editable mesh, packed color atlas, preview camera and lighting.
- `Log_Master.fbx` and `Log_Master.glb`: asset only, one mesh and one material, embedded texture.
- `Log_Preview.png`: actual Blender render.
- `textures/Log_Color.png`: 2048 × 2048 color atlas for the asset.
- `textures/Bark_Original.png`: unchanged user-supplied bark source.

The supplied bark image is mapped lengthwise along the trunk and each branch. Its colors are preserved; the atlas resamples it into a padded rectangle. Cut wood uses authored muted solid-color bands in the same atlas. Bark islands intentionally share texture space for reuse, so this UV map is not a unique lightmap.

The mesh is 1,518 triangles with 769 source vertices. It contains five closed intersecting shells (trunk and four stubs), joined into one mesh object; it is not a boolean-unioned solid. Flat normals retain the polygonal silhouette. The pivot is centered under the complete horizontal bounds at ground level. Intended dimensions are approximately 12.02 × 3.67 × 3.60 Roblox studs including branches, with a trunk diameter around 3 studs. One Blender unit represents one intended stud; confirm import scaling when importing into Roblox.

`verify_log.py` independently reopens the blend and imports both exports, checking one asset mesh/material, valid UVs, loaded atlas dimensions, closed manifold shells after UV-seam welding, nondegenerate triangles, dimensions and centered ground pivot. Full measured results are in `verification.json`. The preview has also been inspected visually. No Studio import or live Roblox test was performed for this Blender-only request.

Rebuild with Blender 5.2 in background mode using `--python build_log.py`, then validate using `--python verify_log.py`. Preview ground, camera and lamps are excluded from both exports.

Source provenance: geometry created for this asset using the user reference `ChatGPT Image Sep 16, 2026, 08_53_06 PM.png`; bark supplied by the user as `ChatGPT Image Sep 16, 2026, 11_42_59 AM (6).png`. No Creator Store content is included.
