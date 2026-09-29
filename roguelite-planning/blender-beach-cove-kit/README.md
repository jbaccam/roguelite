# Beach Cove kit — map two

Twenty-five modular assets for the Beach Cove arena: grass-capped stone headlands,
bare shoreline rock, palms, driftwood, a wrecked rowboat, tide pools and grass
patches. Built to match the existing rounded cliff family, reskinned to the beach
palette from `map-concepts/beach-cove.png` and the September 22 reference sheet.

`previews/beach-cove-lineup.png` is an actual Blender render of the exported
geometry, as are the four closeups. Individual FBX and GLB files are in
`exports/`; per-asset colour atlases are in `textures/`.

## The scaling fix

**Import at 1:1 and do not scale these.** That is the whole point of the kit.

The sibling kits (`blender-rounded-lightstone-revision`, `blender-rounded-stackable-kit`)
author at roughly 8–18 units and are then scaled up in Studio. Their UVs pin the
painted rock at about 10.5 units per repeat *at authoring size*, so an 8-unit-wide
cliff carries barely 1.3 repeats across its face. Scale that MeshPart 4× and the
same single repeat now spans 32 studs: the painted cracks become four times too
large and four times softer. Baked atlases cannot re-tile, so nothing corrects it.
That is the stretched look.

Here every asset is modelled at the size it will actually be placed at, and the
painted repeat is held constant regardless of that size:

| surface | studs per repeat |
| --- | --- |
| cliff and boulder stone | 40.0 |
| grass cap | 18.0 |
| palm bark | 8.0 |
| fronds | 7.0 |
| driftwood and boat planking | 5.0 |
| sand rim | 10.0 |
| tide-pool water | 12.0 |

These are set from how big one *painted feature* should read in studs, not from a
texel budget. The stone sheet holds roughly 16 blocks across, so 40 studs per
repeat puts a stone block at about 2.5 studs. At the earlier 9 it was half a
stud, which is what "too many rocks" meant.

A 54-stud headland therefore carries about six vertical rock repeats rather than
one smeared one. `previews/cliff-closeup.png` shows the result.

If you need a size the kit does not cover, change the dimensions in
`generate_beach_kit.py` and rebuild rather than scaling in Studio — the density
constants do the rest. Scaling a piece by more than about ±15% starts to show.

## Assets

Sizes are the real export dimensions in studs (X x Y x Z), from `polygon-report.json`.
They are sized for a 125-stud arena: rim cliffs read 10-30 studs tall and palms
14-22, matching the reference's proportions against its cove.

**Headlands and plateaus** -- grass-capped, rounded chunky stone, ground-level pivot.

| asset | studs | tris |
| --- | --- | --- |
| 01 Headland Short | 19 x 15 x 10.1 | 336 |
| 02 Headland Medium | 21 x 15 x 17.2 | 344 |
| 03 Headland Tall | 17 x 14 x 27.4 | 354 |
| 04 Plateau Wide Low | 35 x 28 x 8.1 | 430 |
| 05 Plateau Broad | 31 x 27 x 15.2 | 386 |
| 06 Headland Tall Mass | 30 x 25 x 30.4 | 380 |
| 07 Headland Tapered | 21 x 16 x 19.2 | 324 |
| 08 Stack Double | 32 x 20 x 21.2 | 742 |
| 09 Stack Triple | 34 x 25 x 28.4 | 1084 |
| 10 Rim Corner Wedge | 25 x 14 x 17.2 | 328 |

**Bare shoreline rock** -- no grass cap, for the waterline and for hiding seams.

| asset | studs | tris |
| --- | --- | --- |
| 11 Boulder Medium | 5 x 4 x 3.6 | 212 |
| 12 Boulder Large | 11 x 9 x 6.5 | 206 |
| 13 Rock Cluster | 10 x 7 x 4.9 | 852 |
| 14 Standing Rock | 5 x 4 x 9.9 | 202 |
| 15 Shore Rock Low | 13 x 8 x 2.0 | 156 |

**Palms** -- solid geometry, no alpha cards, same as the evergreen master.

| asset | studs | tris |
| --- | --- | --- |
| 16 Palm Tall | 21 x 21 x 23.5 | 807 |
| 17 Palm Leaning | 18 x 18 x 19.2 | 739 |
| 18 Palm Short | 15 x 15 x 15.0 | 559 |

**Ground props**

| asset | studs | tris |
| --- | --- | --- |
| 19 Driftwood Log | 11 x 4 x 4.1 | 302 |
| 20 Driftwood Planks | 9 x 3 x 1.5 | 612 |
| 21 Wrecked Rowboat | 11 x 4 x 3.0 | 632 |
| 22 Tide Pool Small | 8 x 5 x 0.4 | 71 |
| 23 Tide Pool Large | 13 x 9 x 0.4 | 42 |
| 24 Grass Patch Small | 6 x 5 x 1.3 | 229 |
| 25 Grass Patch Large | 10 x 8 x 2.0 | 269 |

10,598 triangles across the whole set. Each export is one mesh with one material,
one UV map and a ground-level local origin.

The driftwood keeps the brief's log rules -- cut circular ends, short broken
branch stubs, uneven silhouette -- while reading as a different piece from
`blender-master-log`: bleached, flatter in section, bowed along its length, and
carrying two stubs rather than four.

## The arena

`build_arena.py` assembles the cove and writes `arena-layout.json`;
`emit_studio_script.py` turns that into `BuildBeachCove.server.luau`.
`previews/arena-overview.png` and `arena-topdown.png` are real renders of it.

- **125 studs of clear sand**, inside face to inside face.
- The rim is walked round the circle **by angular coverage**, each piece advancing
  the cursor by 68% of its own angular width, so neighbours always overlap. A
  hand-written table of 20 fixed angles left about 70 studs of holes in a 470-stud
  circumference, which you could see straight through.
- Taller masses sit at the back, big framing blocks at the two front corners, and
  a second row behind fills the skyline.
- 116 instances: rim, back row, palms crowning the tops, and a sparse floor
  scatter. The middle stays open, per MODULAR_CLIFF_KIT.md's 75-85% rule.

To build it in Studio: import the 25 FBX files at scale 1.0, put the MeshParts in
`ServerStorage.BeachCoveKit` named `01_Headland_Short` and so on, then run
`BuildBeachCove.server.luau` once. It is idempotent and warns about any asset the
folder is missing.

Two things the script handles that are easy to get wrong by hand:

- **Roblox pivots a MeshPart at its bounding-box centre**, not at the ground origin
  the mesh was authored around, so each asset carries a `PIVOT` offset applied
  after the yaw.
- **Cliffs are scenery.** Collision comes from an invisible 32-segment
  `BoundaryWall` ring on the clear-floor circle, because the visual meshes contain
  overlapping and disconnected shells that make poor colliders.

## Art brief compliance

Built against `../art-references/ART_DIRECTION_USER_2026-09-17.txt`, which is the
approved art reference. The rules that actually shaped the geometry:

- **"Soft bevels instead of razor-sharp edges."** Every asset gets a
  single-segment chamfer in `finish()`, the same treatment the lightstone
  revision calls `Small_worn_edge_chamfer`, scaled from its 0.10 units to 0.35
  studs for this kit's larger assets.
- **"Pure flat-shaded geometry" is on the avoid list.** Faces are smooth shaded
  and `shade_smooth_by_angle` keeps only breaks steeper than 40 degrees sharp, so
  faceting stays visible without the surface reading as primitive.
- **Cliffs are "rounded/cylindrical, chunky... soft-edged"** with "rounded or
  softly polygonal footprints". `footprint()` is a circle with low-frequency
  wobble and a mild squared bias -- not a boxy superellipse, and not a perfect
  cylinder either.
- **"The transition should occupy a noticeable band, not a tiny line."** The rim
  runs to 45% of height, capped at 12 studs, and its lower boundary is pushed
  down irregularly per column so the grass hangs further in places instead of
  stopping on a level line.
- **"Stacked cliffs must NOT look like layer cakes."** Combos use offset masses,
  unequal height zones and irregular widths, with one side reading as a single
  tall face. Ledges on individual cliffs use two incommensurate frequencies, so
  no two pieces step at the same rhythm -- a single periodic term is what makes
  every cliff look like a stack of pancakes.
- **"Avoid huge triangular facets dominating surfaces."** Boulders are chamfered
  and smoothed rather than raw flat-shaded icospheres.
- **"Avoid excessive tiny geometry."** Tide pools are 42-47 triangles and grass
  patches 227-273, rather than the four-figure counts a stacked-disc construction
  produces.
- **Foliage is "chunky, layered, scalloped edges, slightly drooping"** and rules
  out "individual leaf cards" and "super spiky geometry". Each frond is one solid
  blade folded along its spine, widest about a third out and narrowing to a
  rounded tip, with lobed edges -- not a fan of thin pointed cards.

## Modelling notes

Bevelling can collapse geometry already thinner than the chamfer, such as a
boat's stem or a thin branch stub. Those become zero-area faces, which have no
normal and shade as black slivers in engine, so `finish()` dissolves degenerates
after the bevel rather than hand-tuning a chamfer width per asset.
`validate_exports.py` checks for exactly this, and caught three assets when the
bevel pass was first added.

The rim band maps the transition sheet once from its rock foot to its dense green
top, repeating only around the perimeter.

## Textures

`textures/*.png` are 1024px tiling sheets. **Stone, grass, the grass-to-stone
transition, fronds, palm bark and water are hue/value regrades of the user's own
hand-painted mountain sheets**, supplied 2026-09-23 as the quality bar for this
kit. They are recoloured — warmer sun-bleached stone, lighter yellower grass,
shallower pool water — so the beach rim does not read as the mountain cliffs in a
different place. Originals are copied unchanged into `textures/source/` with
SHA256 in `textures/texture-provenance.json`. Sand and boat planking are authored
procedurally; driftwood is a regrade of the existing log bark sheet.

Two earlier approaches were tried and rejected, recorded here so they are not
repeated:

1. **Regrading the older cobble stone sheet.** Its motif is dozens of small
   blocks, so a cliff face carried hundreds of little rocks at any density.
2. **Authoring stone and grass procedurally.** Smooth value noise has no hard
   edges, so the first attempt came out smeared. A second attempt using Voronoi
   cells and stamped blades got the structure right but not the craft: cells too
   small and even read as cobblestone, and small evenly-scattered blades read as
   confetti. The helpers are still in `author_textures.py`
   (`cell_noise`, `author_rock_faceted`, `author_grass_painted`) if a fully
   original sheet is ever needed, but they do not match hand-painted work.

Sheets that already tile are left alone. `make_seamless()` only runs when a sheet
has a real seam (error above 0.020), because offset-healing one that does not need
it smears a band of crisp painted detail across the middle.
`previews/texture-tiling-proof.png` is a 3x3 tile of each.

The transition sheet is healed **horizontally only**. It is a vertical gradient
band, not a repeating surface — healing it vertically folds the grass into the
middle and produces a visible repeating grid.

Each asset then bakes its sheets down to one 2048px atlas, so every export stays a
single-mesh, single-material MeshPart. Roblox documents support up to 4096 with
compression applied, and recommends 1024 for a 20x20 stud object, so 2048 suits
these assets. If an atlas comes back downscaled, the density-based authoring still
holds the *pattern scale* correct; only sharpness changes.

## Studio import

1. Import the FBX through **File > Import** (or the 3D Importer) at scale 1.0.
2. Keep the MeshPart colour white. If the embedded atlas does not transfer, upload
   the matching `textures/<name>-atlas.png` and assign it as the colour texture.
   Do not assign a repeating source sheet to the packed atlas UVs.
3. Anchor everything. Set background and unreachable pieces non-collidable.
4. Stacked combos and the rock cluster are joined meshes containing overlapping
   and disconnected closed shells; their interior walls are not a good collider.
   Choose collision fidelity after import rather than assuming the visual mesh works.
5. Follow the arena rules in `../MODULAR_CLIFF_KIT.md`: a simple invisible boundary
   for collision, 8–16 large modules around the rim, central 75–85% kept clear.

Tide pools and grass patches sit slightly proud of the floor with a thin chamfered
lip, so they read as placed pieces without z-fighting against the sand.

## Rebuilding

```
python author_textures.py
blender --background --python generate_beach_kit.py
blender --background --python validate_exports.py
blender --background --python build_arena.py
python emit_studio_script.py
```

Blender 5.2 for the last two; `author_textures.py` needs system Python with numpy
and Pillow. Add `-- --preview` to the generator for a three-piece style study only.
Unlike the sibling generators, this script is self-contained — it does not `exec()`
slices of its neighbours' source text, which breaks as soon as any of them is edited.

## Notes

- Rebuilding `BeachCoveArena` deletes `NoClimb`. Re-run `studio-prototype/ApplyPropCollision.luau` afterwards.
- The spawn markers and hand-placed props live in `Workspace.BeachCoveExtras` and survive a rebuild.

## Validation

`validation-report.json` records every FBX and GLB reimported into an empty scene:
one mesh, one material, one UV map, finite 0–1 UVs, no degenerate triangles,
metallic 0, an image reaching Base Color, a 2048px atlas, and FBX/GLB triangle
agreement. All 25 assets pass, and all seven source sheets hash-match their
recorded originals.

This is Blender-side verification only. **No Roblox Studio import or in-game test
has been performed for this kit** — that still needs doing before calling it
Roblox-ready. No Studio content or unrelated project source was modified.

## Provenance

All geometry was authored for this request. No Creator Store content is included.
Reference: `textures/source/beach-cove-reference.png`, supplied by the user
(`ChatGPT Image Sep 22, 2026, 07_47_05 PM.png`), used for composition, palette and
prop vocabulary. Source painted sheets are the user's existing supplied textures,
listed with hashes in `textures/texture-provenance.json`; none were modified.
