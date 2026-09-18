# Approved reference-to-Blender workflow: all remaining weapons

The user explicitly approved the Glock model and now requests every reference in `C:/Users/Jeremiah/Downloads/weapons`, modeled concurrently by five assigned subagents without duplicate work. The original one-item approval gate has been satisfied. Do not remodel the Glock.

## User's modeling requirements (preserved in full substance)

Recreate the **actual item model in Blender** as closely as possible. Ignore the blue background, lighting setup, camera framing, and presentation. Those are irrelevant. The user cares about the **3D asset itself**.

Match the reference in:

- silhouette
- proportions
- overall shape
- low-poly style
- faceting
- bevels
- material/color breakup
- important visual details
- overall level of complexity

Do not loosely reinterpret the design. Treat the image as a direct modeling reference.

Keep the model:

- stylized
- low-poly
- clean
- game-ready
- Roblox-friendly
- not overly realistic
- not unnecessarily high-poly

Use simple materials and match the visible colors in the reference. When the asset is complete, show the finished Blender model clearly so the user can compare it against the reference image.

The approved Glock is the quality/style bar: `../item-model-test-glock/Glock_Reference_Test.blend`, `Glock_Comparison.png`, and `build_glock.py`. Inspect the approved render and your assigned full-size source images before modeling. That Glock is 2,588 triangles with broad single-segment bevels, purposeful shape detail, and restrained color breakup baked into one texture. Do not mechanically enforce the same triangle count on more complex items. Prioritize faithful silhouette and important details; spend triangles where needed. Aim generally below 8,000 triangles per assembled item, with a documented reason if a complex chain/organic item needs more. No generic placeholder boxes or token primitives passed off as finished references.

## Ownership and execution

`inventory.json` assigns exactly one owner batch and output path per reference. Model only your assigned indices. Do not edit the inventory or other batches' outputs. Put your generator/helper scripts under your own `batches/<batch>/` folder. Do not spawn additional agents.

Work through a dedicated background Blender process so that other agents' files and the user's open scene are preserved. Executable: `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`. Use `--threads 4` to avoid resource contention; use roughly 24 Cycles samples and denoising for review renders. Use separate per-asset files; no shared scene or same output filename between processes. Commands run in PowerShell. Do not use Blender MCP to mutate an open scene shared by other work.

Do not import anything into Studio, change gameplay scripts, or upload game assets as part of this request. It is modeling and file delivery.

## Per-item deliverables in its assigned output directory

- `Reference.png`: unmodified local copy of its source image.
- `Model.blend`: real editable model, texture packed, clean names, useful pivot, review camera and lights in a separate non-exported collection.
- `Model.fbx` and `Model.glb`: only asset geometry, no camera, floor, or lights. Bake procedural/material colors into a portable base-color atlas where appropriate; no unsupported shader dependencies in exports.
- `BaseColor.png` when an atlas is used.
- `Preview.png`: actual Blender render, neutral background, item large and legible, roughly comparable reference angle.
- `Alternate.png`: side/opposite view revealing depth and craftsmanship.
- `validation.json`: actual vertices/triangles, mesh/material count, UV/texture status, topology checks, bounds, honest limitations.
- `README.md`: concise asset identity, reconstruction script, assumptions for unseen surfaces, and any limitations.

Latest user direction overrides the original posed-set requirement: repeated examples become ONE reusable model per item. Deliver one cinder block, duck, kunai, egg, and bowling pin. Boxing gloves are the exception: make distinct left/right models, independent objects with independent pivots and individual component exports. Cards require one deck and three individual cards, all independent and freely movable, with separate exports for each; no attached or joined cards. Keep the supplied Reference.png unchanged even when it shows multiple examples. The top-level glove/card files may present a review arrangement of independent objects, with individual reusable component files under components/<ComponentName>/Model.blend, Model.fbx, and Model.glb.

Use actual modeling, not raster images placed on billboards and not ImageGen to fake a completed Blender render. Stylized glow is appropriate where shown (crystal/staff/Pandora) but model its container, gemstone, and major swirls as geometry/portable textures; no lighting trick that hides missing asset geometry.

## Required checks and handoff

Render, inspect with view_image, and refine against the assigned reference before calling an item done. Run geometry and export checks appropriate to the model; no loose vertices, zero-area faces, missing textures, or accidentally exported staging. Report any intentional open surfaces or complex intersections truthfully. Reimport GLB/FBX if practical. Do not claim Studio validation.

Send the parent a progress message after the first completed item, and periodically at meaningful milestones. Final response: all assigned indices, output paths, triangle counts, validation summary, unresolved issues (if any). The parent owns the final consolidated gallery, coverage audit, and cross-batch review.

## Subsequent user articulation request

Preserve the completed designs while preparing them for later animation: the launcher must start empty, with its rocket in an additional standalone component; nunchucks, kusarigama and wrecking-ball chains need exported rigid bone rigs; Pandora's Box needs a rear-hinged lid and usable interior. Do not author animations or keyframes. Test temporary poses, restore the rest state, and include a diagnostic still and rig validation. The yo-yo should lose its fixed mesh string and provide independent yo-yo/finger-ring parts with endpoint markers for a later Roblox Beam. Rebuilding these assets must include their batch-owned articulation scripts after the original geometry generator. See RIGGING_GUIDE.md.
