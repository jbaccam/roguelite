# Heart pickup — rare healing drop

Original 3D model built on 2026-09-28 from the in-game HUD heart icon, `studio-prototype/ui/assets/heart.svg` (uploaded as asset 101432943753406; SVG SHA256 `ce42a2621cb9e0df6de3550eacaa739467ecbb22a115619dc3669c6b5e885036`). The generator copies that icon's 12-point silhouette, its two shared interior facet corners and its seven facet fills, then pushes the facets into a chunky double-sided gem with a soft side band. No third-party geometry or textures.

Follows `../art-references/ART_DIRECTION_USER_2026-09-17.txt`: simple silhouette, clean faceting, tiny chamfers, broad low-noise painted colour. The icon's black border is not modelled; in game a Roblox `Highlight` outline draws it, and the preview renders approximate it with a camera-only inverted shell.

## Files

- `generate_heart_pickup.py` — self-contained Blender 5.2 generator (mesh, bake, exports, previews, validation).
- `HeartPickup.blend` — editable mesh with the base-colour image packed.
- `exports/fbx/HeartPickup.fbx`, `exports/glb/HeartPickup.glb` — the mesh only (no preview shell, camera or lights), base colour embedded.
- `textures/HeartPickup_BaseColor.png` — 512 × 512 opaque base colour; use as `MeshPart.TextureID`, not a SurfaceAppearance.
- `previews/HeartPickup_Preview.png` (3/4 with outline), `HeartPickup_Front.png`, `HeartPickup_NoOutline.png` — real Blender renders.
- `HeartPickupGeometry.json` — unchamfered vertices (Roblox Y-up, front −Z), faces and exact svg colours.
- `HeartPickupVisual.luau` — upload-free WedgePart build from that JSON (mirrors `studio-prototype/combat/HeartPickupVisual.luau`).
- `validation-report.json` — manifold/degenerate/material/UV checks.

## Numbers

Mesh: 90 vertices / 176 triangles after chamfer and triangulation; 1.99 × 0.87 × 1.80 Blender units (width × depth × height). Validation: 0 non-manifold edges, 0 degenerate faces, 1 material, 1 UV map. The WedgePart fallback is 56 triangles → 112 WedgeParts at the default 1.8-stud width.

## Roblox integration

The game currently renders the WedgePart fallback (like the crystal shard): `HeartVisuals` clones `HeartPickupVisual.create(nil, 'HeartPickup', 1.8)`, adds a black `Highlight` outline and a small red `PointLight`. To switch to the textured mesh, import `exports/fbx/HeartPickup.fbx` with Studio's 3D Importer, set its `TextureID` to an upload of `textures/HeartPickup_BaseColor.png`, and swap the template in `HeartVisuals`.

## Reproduce

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python roguelite-planning/heart-pickup/generate_heart_pickup.py
```

Writes only this folder, in a fresh factory-settings Blender process.

## Verification scope

Blender-verified: generation, bake, both exports, validation report and visual review of the renders against the icon. The FBX/GLB have not been imported into Studio. The WedgePart fallback was built in Studio Edit mode (112 parts, 1.99 × 1.78 × 1.15 studs); its in-Play look is covered by the gameplay change's test notes.
