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
| `previews/` | `Sarcophagus.png`, `Broken.png`, `Vent.png`, `Debris.png` (Blender renders of the exported FBX) |
| `round10-props.blend` | Source scene (assets laid out side by side; export objects sit at their FBX positions before the layout shift) |

Rebuild (headless): `blender -b --python build_round10_props.py`, then `blender -b --python validate_props.py`, then `... build_round10_props.py -- render`.

## Meshes and triangles

| FBX | Mesh | Tris | Budget |
|---|---|---|---|
| Sarcophagus | `Sarcophagus_Body` / `Sarcophagus_Lid` | 550 / 2,278 (2,828 total) | <= 3,000 |
| SarcophagusBroken | `_Base` / `_LeftWall` / `_RightWall` / `_LidFragment` | 436 / 514 / 544 / 1,396 (2,890 total) | <= 3,000 |
| VolcanicVent | `Vent_Rock` / `Vent_Glow` | 1,252 / 260 (1,512 total) | <= 2,000 |
| VolcanicDebris | `Debris_1..5` | 64 / 80 / 80 / 44 / 68 | 30-150 each |

## Sarcophagus (fix pass 2026-10-09)

- Outer 11.0 tall, 7.24 wide at the shoulders (widest at 66% of the height), head 4.1 wide, foot block 5.0 wide (4.6 above the step), 5.2 deep.
  Stepped foot block, two stone-block grooves (taper and head wall), chamfered and bevelled edges, flat stable base.
- Body origin: floor centre of the cavity footprint at ground level. Open face toward -Y, solid flat back (no relief).
- Cavity (measured by ray casts on the re-imported FBX): 9.4 tall (floor z 0.8 to ceiling z 10.2), 6.25 wide at the shoulders, 4.5 deep.
  Walls 0.51 at the sides, 0.7 at the back, 0.8 floor and ceiling. The coffin is anthropoid, so 9.4 x 6.2 x 4.2 are the cavity's bounding extents:
  3.1 wide at the head, 6.2 only at the shoulders (height available at width >= 3.4 / 4.4 / 5.2 / 6.2: 8.3 / 5.5 / 3.1 / 0.1).
- Lid: same outline as the body, slab 0.85 thick plus relief up to 0.36 (1.21 total), flat underside. Closed, its underside plane is the body's
  front rim plane (gap 0.000, no overlap; worst outline vertex offset 0.04). Origin on its bottom front hinge line, body space
  (0, -3.464, 0); the FBX location places it closed. It falls forward by rotating +90 degrees about X (relief face down, underside up).
- Relief: rounded pillow-profile bandage bands (forehead pair, chin pair, diamond lattice down the torso, ankle wrap) over a recessed panel floor,
  dark face plate and two domed round eyes. Texture: broad soft painterly patches only (sandy beige, a few large terracotta mottles, 2-4 values).
- Tomb-Warden clearance is a bounding-extent check only; no pose was fitted.

## Broken kit

Exactly four chunks cut by exact boolean (jagged cutters, fracture edges bevelled 0.07) from the final intact body and lid meshes:
low base with the foot recess, left shoulder wall, right shoulder wall, cracked lid fragment with part of the relief. Interior faces use a darker
sandstone atlas tile. Each mesh origin is its bounding-box centre; the FBX object location is that centre in the coffin body-origin frame, so an
identity placement at the coffin body origin reproduces the intact position (offsets in `exports/SarcophagusBroken-offsets.json`).
The validator confirms every chunk vertex lies on or inside the intact body or lid. The centre-back of the coffin is intentionally absent (dust).

## Vent and debris

Unchanged in this pass (reviewed good). Vent: ring of 9 basalt rocks plus second-row boulders and loose rocks, 8.9 across, 1.77 tall,
opening about 3.6 across at ground level, lava pool and seams in the cracks as the separate `Vent_Glow` mesh (set Neon in Studio).
Debris: five faceted basalt fragments 0.19-0.46 across with an ember patch on one face, origins at their centres.

## Checks (`validation-report.json`, 102 checks, all pass)

Names exact, no armature or animation, triangle budgets, every mesh a closed shell (0 open edges), no zero-area or sliver faces, UVs in 0-1,
atlases load at 1024 / 512, lid fit, cavity extents, silhouette proportions, chunk offsets, vent height <= 1.8, debris sizes 0.15-0.5.

## Provenance

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
- Preview colours are Blender renders (Standard view transform); the game's +0.3 saturation ColorCorrection will push them warmer.
- Lid relief sticks out 0.36 from the slab, so a lid fallen face-down rests on the bands, not flat.
