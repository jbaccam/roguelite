# Standalone Roblox Cliff Pillars — replacement kit

This is the corrected asset set: **individual irregular cylindrical mountains/mesas**, not a circular wall, ring, or environment. The earlier `../blender-cliff-kit` ring kit is superseded for this request and remains untouched for reference only.

## Deliverables

- `standalone-cliff-pillars.blend` — editable source containing all six individual pieces.
- `generate_pillars.py` — reproducible Blender generator, preview renderer, and exporter.
- `previews/standalone-cliff-pillars.png` — a render of the actual Blender meshes, not an AI concept image.
- `exports/fbx/` — six individual FBX files for Studio import.
- `exports/glb/` — six matching GLB files.
- `polygon-report.json` — mesh counts.
- `validate_exports.py` / `validation-report.json` — round-trip Blender export validation.

## Pieces and dimensions

Dimensions are nominal Blender units. Start with 1 unit = 1 intended Roblox stud, then confirm the importer's scale against an avatar before using the whole kit.

| Piece | Approximate footprint | Height including grass lip | Pivot |
| --- | --- | --- | --- |
| Short Narrow | 6.6 × 6 | 7.55 | Bottom center |
| Medium Mesa | 10.4 × 9.2 | 11.55 | Bottom center |
| Tall Narrow | 7.4 × 7 | 22.55 | Bottom center |
| Tall Wide Mesa | 14 × 11.8 | 20.55 | Bottom center |
| Squat Broad Plateau | 17.4 × 13 | 8.55 | Bottom center |
| Floating Tapered | 12.4 × 10.4 | 15.55 total | Centered at z=0; underside z=-10, top z=+5.55 |

The slight irregular outline and 5% overhanging grass cap can extend the actual footprint slightly beyond nominal dimensions. All rock bodies have closed bottoms. The floating piece has a tapered, fully modeled underside and is displayed above the floor only in the preview.

Each exported module contains two separate objects: `Rock` and `GrassCap`. This preserves independent recoloring even if Studio does not reproduce Blender's material slots exactly.

## Placement in Roblox Studio

1. Import a single FBX through Studio's 3D Importer and verify its scale.
2. Preserve the separate rock and grass objects as MeshParts in a Model.
3. Set the Model pivot to the documented origin. Grounded pieces sit at their bottom-center origin; the floating piece uses a centered moving pivot.
4. Duplicate, rotate, uniformly scale, and scatter these standalone pieces freely. They do not require snap angles or a common arena center.
5. Put scenery around the outside of the playable space; avoid turning the open arena into a platforming course.
6. Set scenery MeshParts to `Anchored = true`, `CanCollide = false`, `CanTouch = false`, and optionally `CanQuery = false`.
7. If cliffs must block players, use a simple invisible native Part or small group of Parts rather than detailed triangle collision.

FBX exports use forward `-Z`, up `Y`, applied scale, no armatures, and Blender 5.2.1 LTS. Every object uses original low-poly geometry and flat colors, with no copied assets or textures.

## Recoloring

- Grass cap: change `Grass_Top` and `Grass_Lip` in Blender, or recolor the separate cap MeshPart after Studio import.
- Rock body: change the four broad facet materials, keeping their light/dark relationships.
- Snow biome: off-white cap, blue-gray rock.
- Desert biome: clay/sand cap, warm terracotta rock.
- Volcanic biome: dark basalt cap, charcoal rock.

## Regenerate or validate

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python 'C:\Users\Jeremiah\Documents\ChatGPT\Roblox\roguelite-planning\blender-cliff-pillars\generate_pillars.py'
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python 'C:\Users\Jeremiah\Documents\ChatGPT\Roblox\roguelite-planning\blender-cliff-pillars\validate_exports.py'
```

Regeneration replaces only this folder's generated source, exports, preview, and report. It does not touch the prior kit or unrelated project assets.

## Validation

Source and previews were produced in Blender 5.2.1 LTS. Every individual FBX and GLB was re-imported into Blender and checked for nonempty mesh geometry; see `validation-report.json`. Roblox Studio import has **not** been tested, so scale, material transfer, and collision settings still need a Studio check.
