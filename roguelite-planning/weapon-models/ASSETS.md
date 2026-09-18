# Asset provenance

The user supplied 35 generated item-reference PNGs in `C:/Users/Jeremiah/Downloads/weapons` and approved the previously completed Glock trial. `inventory.json` records every supplied reference, its exclusive modeling assignment, and its output directory. `approved-glock.json` records the separate approved reference.

All delivered mesh geometry was constructed locally in Blender from those visual references. Review images are renders of the actual mesh assets. No Creator Store models, downloaded meshes, image billboards, or generated substitutes for Blender renders were used.

Each asset directory includes an unmodified `Reference.png` for direct comparison. Unseen surfaces and depth were inferred from the single supplied image and are documented in each README.

Materials use simple colors and local base-color textures, packed into Blender and embedded in exports. Some magic items also use transparent/emissive materials; their final Roblox appearance may require import-side material setup. Staging lights, cameras and review floors are excluded from FBX/GLB exports.

The approved Glock's original trial is retained separately. The standardized delivery copy removes invisible degenerate faces without changing its approved appearance.
