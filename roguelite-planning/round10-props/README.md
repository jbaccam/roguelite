# Round 10 props

Static props for the five round-10 events (see `../ROUND_10_MASTER_SPEC.md`, art brief `../plans/2026-10-09-round10-art-brief.md`):
upright sarcophagus (body + lid), broken-sarcophagus kit, volcanic vent, volcanic debris.

**Status: Blender-verified, Studio untested.** No Roblox Studio import or Play test has been run.

Units are studs at template scale 1: import at 1:1, do not scale. Blender frame is +Z up with the coffin's open face toward -Y
(FBX `axis_forward='-Z', axis_up='Y'`, so Roblox front = -Z). Blender (x, y, z) maps to Roblox (x, z, -y).

## Files

| Path | What |
|---|---|
| `build_round10_props.py` | Self-contained generator: textures, geometry, FBX export, manifest, `.blend`, and previews (`-- render [sarcophagus broken vent debris]`) |
| `validate_props.py` | Fresh re-import of every FBX, checks, writes `validation-report.json` |
| `exports/` | `Sarcophagus.fbx`, `SarcophagusBroken.fbx`, `VolcanicVent.fbx`, `VolcanicDebris.fbx` (mesh-only, textures embedded), the two atlases next to them, `SarcophagusBroken-offsets.json`, `props-manifest.json` |
| `textures/` | `Sarcophagus_atlas.png` (1024², shared by the coffin family), `Volcanic_atlas.png` (512², vent + debris) |
| `previews/` | `Sarcophagus.png`, `Broken.png`, `Vent.png`, `Debris.png` (Blender renders of the exported FBX), `Compare_Assembly.png` (reference 03 left panel, then the same framing in neutral light and in game-like light) |
| `round10-props.blend` | Source scene (assets laid out side by side; export objects sit at their FBX positions before the layout shift) |

Rebuild (headless): `blender -b --python build_round10_props.py`, then `blender -b --python validate_props.py`, then `... build_round10_props.py -- render`
(optionally `-- render sarcophagus broken compare`). Coffin sheets use a game-like rig: light-blue world fill (0.55, 0.70, 0.95) at 0.85 plus a
warm sun (1.0, 0.93, 0.80), so they predict the in-game colour; vent and debris sheets keep the original rig.

## Meshes and triangles

| FBX | Mesh | Tris | Budget |
|---|---|---|---|
| Sarcophagus | `Sarcophagus_Body` / `Sarcophagus_Lid` | 368 / 1,886 (2,254 total) | <= 3,000 |
| SarcophagusBroken | `_Base` / `_LeftWall` / `_RightWall` / `_LidFragment` | 372 / 408 / 364 / 1,226 (2,370 total) | <= 3,000 |
| VolcanicVent | `Vent_Rock` / `Vent_Glow` | 1,252 / 260 (1,512 total) | <= 2,000 |
| VolcanicDebris | `Debris_1..5` | 64 / 80 / 80 / 44 / 68 | 30-150 each |

## Sarcophagus (fourth pass 2026-10-10: sized around the Tomb Warden)

The cavity is built around the Warden's real emergence pose, not a box: `../tomb-warden-boss/exports/game/GameChecks.json` ->
`coffinFit.requiredCavity` (per 0.5-stud band: half-width with left/right extents, front and back y, 0.12 clearance included; he is 10.29
tall above the floor, 5.29 deep, 6.64 wide at 6.5-8.5 above the floor). Within that, the shape stays as close to 03/08/09 as the fit allows.

- Outer 13.5 tall, 8.30 wide at the shoulders, 6.6 deep (about 1:1.6 width to height; the sheets are about 1:2.6, so it is stockier).
  - Head end: a 6.2-wide band (0.75 of the shoulders) from z 11.8 to 12.9, standing 0.15 proud of the angled shoulder line, then
    chamfered corners up to a 4.7-wide top.
  - Shoulders: widest at z 9.45 (70% of the height). Below them the sides run near-parallel down to z 6.6 (8.16 wide there), then
    taper to the foot band: 5.62 wide (0.68 of the shoulders), 1.4 tall, 0.15 proud.
  - Why the bend instead of one straight taper: his folded arms need 6.2+ of cavity width from 5.0 above the floor upward, and a single
    taper with a 0.65-0.68 foot would need a coffin about 9 wide.
  - Carved step notches low on the taper (z 3.1) and high on the head band (z 12.35). The base is flat.
- Chunky rim: side walls 0.65 (front rim face 0.66 wide), 0.55 on the shoulder diagonals, 0.8 back, 0.8 floor and ceiling. Every convex edge,
  outer and inner (rim to cavity), the proud bands included, has a one-segment 0.24 chamfer. Chamfer faces use the lighter worn-edge tile.
- Body origin: floor centre of the cavity footprint at ground level. Open face toward -Y, solid flat back (no relief).
- Cavity (measured by ray casts on the re-imported FBX): 11.9 tall (floor z 0.8 to ceiling z 12.7), 7.0 wide at most, 5.8 deep.
  The open front rim plane is 2.90 from the origin along -Y (Blender), the inner back face +2.90.
  `validate_props.py` tests every band of `requiredCavity` against ray casts (both sides at his front / middle / back y, the back wall,
  the front rim plane, the ceiling). Minimum margin 0.076, on the +x side at 5.0 above the floor, where his arm reaches 3.11. The other
  margins are front 0.256, back 0.256, and ceiling 1.61.
- Lid: same outline as the body (bands, chamfers and notches included), slab 0.85 thick plus relief up to 0.407 (1.257 total), flat underside.
  Closed, its underside plane is the body's front rim plane (gap 0.000, no overlap). Origin on its bottom front hinge line, body space
  (0, -4.157, 0) (the deeper coffin moved the front rim to y -2.90). This was -3.464 before the 2026-10-09 passes; the manifest `lid.hingeLineBodySpaceBlender` has the exact value and the installer reads it from there. The FBX location
  places the lid closed. It falls forward by rotating +90 degrees about X (relief face down, underside up).
- Lid front (matches 03/09): a raised mummy figure standing proud of a flat sandstone border frame. Rounded core: the torso is 3.2 wide at the feet
  and 6.6 at the shoulders since the fourth pass, with sloped shoulders into a 3.5-wide domed head; core relief 0.24. It is wrapped in 15 broad strips:
  - Body: 8 strips form 4 crossing X pairs (1.2-1.25 wide, +/-22-28 degrees), the top strip of each pair alternating.
  - Shoulders: 2 wraps.
  - Head: 4 near-horizontal bands with a warm-brown eye gap holding two round flat-topped eye studs.
  - Ankle: 1 band.

  Strips stand 0.08-0.17 proud. Overlapping strips never share a thickness (equal fronts were coplanar and broke the boolean), so every
  crossing is a real raised overlap edge. The diamonds between X pairs show
  the core, painted as subtle horizontal under-wraps. There is no relief bevel (it cost ~800 tris).
- Tomb-Warden clearance is a bounding-extent check only; no pose was fitted.

## Texture (`Sarcophagus_atlas.png`, repainted 2026-10-09)

Why: in Studio the coffins read pale grey-blue with dull brown blotches (warm sun + strong blue sky ambient, EnvironmentDiffuseScale 1,
ColorCorrection +0.3 saturation / +0.1 contrast turn pale low-saturation beige blue-grey), the soft camouflage blobs did not match the
reference's chipped stone, and the lid read as a lattice with gaps.

- Stone (`paint_chipped`): warmer, more saturated sandstone base (222, 170, 112) with a fine mosaic of painted chips (~0.19 studs, 3 values
  each, a soft one-sided facet shade and a light chipped outline); terracotta weathering (202, 116, 74) decided per chip, so patch edges are
  crisp and chip-ragged rather than blurry; a few lighter worn patches; gentle large-scale drift. No noise mush.
- Tiles: outer stone; inner cavity darker and warmer (198, 138, 86); fracture faces a fresher lighter sandstone (238, 196, 142) with dark grain
  lines so breaks read; worn-edge tile (lighter sand, every bevel face) and seam tile (dark (164, 106, 66), the carved groove faces) mapped per face;
  linen tile for the lid figure; warm-brown face recess; eye studs.
- Tile densities were lowered so the taller coffin (13.5 tall, 6.6 deep) fits without clamping: outer and linen 32.8 px/stud, cavity and fracture 26 px/stud.
- Linen (234, 202, 152; deliberately sandy-ivory, pure white went blue in game): the strip layout is painted in exactly (same planar x/z mapping
  as the geometry), so each strip has a pillow shade, dark seam lines along both edges and a cast shade beside any strip lying over it. Areas
  under no strip get tight horizontal under-wraps, the figure darkens toward its outline (painted form shade), plus light chip grain.
- Tile lookup fix: faces are classified at a point on the face (largest tessellation triangle), not the ngon median. The old median of the
  ring-shaped front rim fell in the opening, so the broken chunks' front rims and the lid fragment's frame wrongly used the fracture tile.

## Broken kit

Exactly four chunks cut by exact boolean (jagged cutters, fracture edges bevelled 0.07) from the final intact body and lid meshes:
low base with the foot recess, left shoulder wall, right shoulder wall, cracked lid fragment with the head and shoulders of the figure. Cutter
outlines are the original ones scaled to the 13.5 height (lid cutter's lower edge raised 0.4 first, for the tri budget); the jagged cutter
rings span the 6.6 depth. After the fracture bevel, any vertex less than 0.05 outside the intact surface (ray-parity test, the same as the
validator) is snapped back onto it (2 vertices on the base chunk in this build), so every chunk stays inside the intact volume. Fracture faces use the fresh-break atlas tile (lighter sandstone,
dark grain lines); all other faces inherit the intact tile at that spot. Each mesh origin is its bounding-box centre; the FBX object location is that centre in the coffin body-origin frame, so an
identity placement at the coffin body origin reproduces the intact position (offsets in `exports/SarcophagusBroken-offsets.json`).
The validator confirms every chunk vertex lies on or inside the intact body or lid. The centre-back of the coffin is intentionally absent (dust).

## Vent and debris

Unchanged in this pass (reviewed good). Vent: ring of 9 basalt rocks plus second-row boulders and loose rocks, 8.9 across, 1.77 tall,
opening about 3.6 across at ground level, lava pool and seams in the cracks as the separate `Vent_Glow` mesh (set Neon in Studio).
Debris: five faceted basalt fragments 0.19-0.46 across with an ember patch on one face, origins at their centres.

## Checks (`validation-report.json`, 103 checks, all pass)

Names exact, no armature or animation, triangle budgets, every mesh a closed shell (0 open edges), no zero-area or sliver faces, UVs in 0-1,
atlases load at 1024 / 512, lid fit, cavity extents, Tomb Warden requiredCavity containment, silhouette proportions, chunk offsets, vent height <= 1.8, debris sizes 0.15-0.5.

## Provenance

Generated atlases (SHA256): `Sarcophagus_atlas.png` `9cd97029541fe9bc2257e44deeba5c2372619499f0327b533972d7ddb5c4c635` (2026-10-10 fourth pass; the linen tile follows the strip layout),
`Volcanic_atlas.png` `698a2fd960e619c7435b443d717559c635a0c76b3e45e2077a531392a035bc07` (unchanged).

Reference sheets in `../art-references/round-10-modeling-pack-2026-10-09/` (SHA256):

| Sheet | SHA256 |
|---|---|
| 03-sarcophagus-assembly.png | `e81d2885a853a85e68bae8d673f9744f5f7a2cbd4a252115c7d76bd5f6c9e32e` |
| 06-volcanic-vent.png | `22e7fa4b0a8ac0121d25ea12e2a04014ec294d78a99508540eca05fd0196691c` |
| 07-small-volcanic-debris.png | `49e280fd8395afe74066153a31fbe926a3d9907eaf39c55e1228d10b921ab7cc` |
| 08-sarcophagus-body.png | `9770b403b9673a8211d88afb26aefdddb86ffe946091527d95fcd2a869de5e45` |
| 09-sarcophagus-lid.png | `5d9371f86e186281b4454feab1807de463ed8f29736e6fb48042d9f3cdcd7fd3` |
| 10-broken-tomb-pieces.png | `1646c2eb35d19fb6770147edd18eaa9359afefe485ac58ef44fddbdd1cdc19fd` |

## Known issues

- Studio untested: pivot handling of the lid hinge and chunk offsets after the Roblox importer is unverified.
- Preview colours are Blender renders (Standard view transform) under a game-like blue-sky + warm-sun rig; no ColorCorrection is simulated, so
  in game the +0.3 saturation will push them warmer and more orange still. Studio colour after the 2026-10-09 repaint is unverified.
- Lid relief sticks out 0.407 from the slab, so a lid fallen face-down rests on the strips, not flat.
- At 13.5 x 8.3 the coffin is about 1:1.6 against the sheets' 1:2.6: the Warden (10.2 tall, 6.64 wide with the 0.12 clearance) plus a
  0.65 rim sets the width, and the art brief's section 5 numbers (10.4 tall, 7.4 wide) are superseded on the coordinator's instruction.
  The bend at z 6.6 makes the silhouette read slightly barrel-like compared with the sheets' single straight taper.
- Tightest Warden margin is 0.076 (his right arm at 5.0 above the floor), on top of his own 0.12 clearance. Any change to his start pose
  needs `validate_props.py` re-run.
- The figure has hard (unbevelled) strip edges to fit the triangle budget.
- Validator limits (fourth pass): outer ~13.5 tall, 8.1-8.4 wide, 6.6 deep, foot band ~5.6, widest at 65-75% of the height, head end
  0.70-0.80 and foot 0.62-0.70 of the shoulder width, height >= 1.55x width, and full containment of the Warden's requiredCavity table.
