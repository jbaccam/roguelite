# Standalone Modular Cliffs

## Current art direction — September 16 revision

The requested assets are **individual cliff pillars and platforms**, not a prebuilt circle or curved wall kit. Arena assembly is a separate later task. The straight/curve kit recommendations below are historical, not the current asset brief.

The revised asset set belongs in `blender-cliff-pillars-v2/`. Keep low-poly silhouettes but use moderate contour segments, softly clipped blocky corners, mild curvature, and subtle base tapering. Do not use pointed floating-spike undersides or giant contrasting triangle materials.

Use the supplied painterly image sheets unchanged: blue-gray rock on vertical walls, grass on top-facing surfaces, and grass-to-rock on a narrow upper-rim transition. UVs must preserve vertical rock direction and consistent texture scale. Top caps have small height variation and a slight lip; image texture provides the detail. Materials are simple image-textured Principled BSDF, nonmetallic, without procedural effects or displacement.

Target a short squarish pillar, medium mildly tapered pillar, tall gently curved cliff, broad low platform, and an asymmetric reusable cliff. Deliver individual exports, editable Blender source, textures, real mesh renders, and validation evidence. Studio import must be verified separately before claiming Roblox readiness.

## Historical assembly guidance

**Recommendation:** Build the perimeter cliffs as reusable imported MeshParts/models rather than Roblox Terrain. Use Terrain only where soft ground shaping or distant filler is useful.

## Why the supplied cliffs appear to be models

- Entire cliff sections are selected and moved with a standard transform gizmo.
- Their top edges and vertical faces have sharp authored silhouettes rather than voxel transitions.
- Floating chunks retain clean side walls and undersides.
- The grass cap and rock wall meet along a consistent designed edge.
- The same visual language repeats at different sizes and rotations.

These are typical signs of a modular MeshPart kit, commonly authored in Blender and assembled as anchored models in Studio.

## Minimum reusable kit

Create a small kit instead of modeling a unique arena wall:

1. Straight cliff segment
2. 30- or 45-degree inward curve
3. 30- or 45-degree outward curve
4. Inside corner
5. Outside corner
6. Short end cap
7. Low terrace/step
8. Tall pillar/mesa
9. Arch segment
10. Separate top-cap strip or slab
11. Background-only large silhouette chunk

The Pine Valley, Beach Cove, Desert Badlands, Frozen Pass, and Volcanic Crater arenas can reuse the same underlying proportions with different silhouettes, caps, palettes, and texture atlases.

## Blender workflow

1. Block each piece from a low-poly cube.
2. Keep the inner gameplay-facing wall relatively simple and readable.
3. Add only a few large vertical cuts or angled faces; avoid dense sculpting.
4. Use a tiny bevel on major silhouette edges if needed for lighting.
5. Keep the top flat enough to accept a separate grass, snow, sand, or basalt cap.
6. UV the vertical wall to a small hand-painted rock atlas.
7. UV the top cap separately or export it as a separate mesh so biomes can swap caps easily.
8. Put the object origin/pivot at the inner-bottom corner or center of the snap edge.
9. Apply transforms and export as FBX or glTF for Roblox import.
10. Import at consistent scale and save every chunk as an anchored reusable model.

## Texture approach

- Use simplified diffuse/color textures with large painted shapes.
- Avoid realistic high-frequency rock noise and heavy PBR detail.
- One 512–1024 texture atlas can serve several cliff chunks.
- Use broad light and dark vertical streaks to imply rock without modeling every crack.
- Keep top caps as separate geometry when possible:
  - grass for Pine Valley/Castle Fields;
  - pale sand or clay for Desert Badlands/Beach Cove;
  - snow for Frozen Pass;
  - dark cooled rock for Volcanic Crater.
- Slight color variation between reused chunks is enough to reduce repetition.

## Roblox Studio assembly

1. Set every visual cliff MeshPart to `Anchored = true`.
2. Disable collision on background and unreachable decorative chunks.
3. Create a simple invisible circular collision boundary from a small number of Parts or wedge segments.
4. Use the invisible boundary for reliable character/enemy collision rather than detailed mesh collision.
5. Set visual meshes to inexpensive collision fidelity when collision is unavoidable.
6. Place 8–16 large modules around the arena instead of hundreds of individual rocks.
7. Vary height, rotation, and neighboring modules, but preserve the circular gameplay boundary.
8. Hide seams with small separate rocks, shrubs, logs, snow piles, or obsidian clusters at the perimeter.
9. Keep the central 75–85% of the arena clear.
10. Treat the cliffs as scenery and boundary language, not platforming surfaces.

## Recommended hierarchy

```text
Workspace
└── RogueliteWorld
    └── ActiveArena
        ├── GameplayFloor
        ├── BoundaryCollision
        ├── CliffVisuals
        ├── PerimeterProps
        ├── SpawnRegions
        ├── BossSpawn
        └── LightingProfile
```

Visual cliff models should not own gameplay state. Spawn regions, arena radius, navigation limits, and collision boundaries remain separate authored data/objects.

## Performance rules

- Prefer several substantial MeshParts over hundreds of decorative Parts.
- Keep background cliffs non-collidable and non-touchable where possible.
- Use `StreamingEnabled` for larger worlds and lobbies.
- Use automatic/performance-friendly render fidelity on background pieces.
- Reuse meshes and atlases across chunks.
- Avoid unique 2K–4K textures per rock.
- Test the cliffs while 100 enemies, attacks, drops, and effects are active; scenery never gets the entire performance budget.

## Studio-only fallback

The cliffs can be prototyped using Parts, wedges, and simple unions, but this is best for grayboxing. It usually produces more seams, more instances, awkward texture stretching, and less consistent silhouettes. Once the arena size is locked, replace the visible perimeter with a small custom MeshPart kit while retaining simple invisible Part collision.

## Recommended production order

1. Graybox the arena radius with Parts.
2. Validate camera, movement, weapon ranges, and spawn distances.
3. Create three test cliff modules: straight, curve, and pillar.
4. Assemble one-quarter of Pine Valley's rim.
5. Test seams, scale, collision, and mobile performance.
6. Complete the core kit.
7. Reskin or lightly reshape it for later biomes.
