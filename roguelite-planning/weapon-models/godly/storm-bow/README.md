# Storm Bow (Godly, round 2)

Ranged Godly: each arrow splits into 5 mid-air and rains down on a group with lightning trails
(RARITY_GODLY_ARMOR.md section 9). Rebuilt from scratch after the round 1 rejection.
Status: **Blender-verified, Studio untested.**

## Design
The bow is a thunderbird; its limbs are the wings.
- **Silhouette:** a big aggressive recurve, 5.0 studs tall, 1.78 studs deep. Limbs, plates, collars, tip bolts and
  string are one authored half mirrored about the grip.
- **Limbs:** dark gunmetal diamond-section core. The belly half of each face carries a long gold-framed zig-zag Neon
  bolt inlay. The back half carries four overlapping storm-slate armour plates; each has a gold back edge and tapers
  into a hooked barb with a silver tip, so the back reads as a serrated row of wing-bone spikes.
- **Tips:** thick three-stroke Z lightning bolts with a diamond section, gold chamfer edge, Neon body and a white-hot
  zig spine, rising out of gold crown collars.
- **Focal piece:** a silver storm-eagle head on the riser front: gold hooked, open beak with a blue glow inside, glowing
  slanted eyes with white-hot pupils, angry brow blades, a swept feather-blade crest and ear tufts. Below it, gold talons
  clutch a big faceted storm crystal (blue Neon facets around a white-hot belt). A silver tail plume and mirrored tail
  feathers balance the head below the grip.
- **Grip:** dark brown leather wrap between gold crown bands; one-sided Neon arrow rest on a gold bracket.
- **String:** a white-hot Neon core inside a jagged electric-blue Neon ribbon, with crackle kinks and small forks near
  each nock, and a white-hot nocking bead between gold rings.

Palette: near-black gunmetal and storm slate (cool shadows, warm highlights), silver steel on the head and barb tips,
brown-shaded gold, dark leather. The only bright colour is the glow: Neon electric blue `RGB(18,108,255)` and white-hot
`RGB(214,240,255)`.

## Numbers
- **Triangles:** 17,546 in total (the scythe is about 17k).
  - Textured mesh: 14,057.
  - Glow: 2,225.
  - Core: 1,264.
- **Texture:** one 1024 `BaseColor.png` with baked painterly lighting. Use `MeshPart.TextureID`.
- **Grip, nocking point, arrow rest, arrow direction and VFX notes (5-way split, lightning trails):** see
  `studio-install-data.json`.
- **Validation:** see `validation.json`. 0 loose vertices and 0 zero-area faces; GLB and FBX re-imports match the
  triangle count; texture embedded.

## Render notes
Renders use the Khronos PBR Neutral view transform (AgX turns saturated Neon pastel) with exposure -0.55, which
matches the mid-tone of the AgX catalogue backdrop. The far backdrop is a little darker and the floor a little
brighter than in the AgX catalogue tiles. Every render has a bloom pass plus a Neon-only fog-glow halo.

Rebuild: `blender -b --factory-startup --threads 2 --python build_storm_bow.py` (`MODE=quick` for flat-colour shape
shots, `OUT=<dir>` for where they go).
