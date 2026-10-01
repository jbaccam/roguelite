# Poseidon's Trident (Godly)

Blender-verified, Studio untested.

**Ability (RARITY_GODLY_ARMOR.md section 9):** thrown and melee. Where it lands, a tidal wave rolls out and
washes enemies away. The colours, spawn point and ParticleEmitter values are in `vfx_notes` in
`studio-install-data.json`.

## Design (round 2, after "not sharp enough, edges too smooth")
- **Tines.** Three long, straight, parallel tines, each cut from one 2D outline: shank plus barbed spearhead.
  - Diamond cross-section: every outline vertex is joined to its own ridge point.
  - Needle points.
  - Big hooked barbs sweep back.
  - Raised teal enamel leaf inlays on both faces.
  - The centre tine is clearly the longest.
  - Bevels are small, 1–2 segments.
- **Waves.** Two gold breaking waves with sharp lens sections curl over the pearl and end in needles.
  - Claw spikes rake up each crest.
  - Teal under-waves curl down with their own claws.
  - Coral enamel inlays run along both wave faces.
- **Focal piece.** A sea-dragon head faces the viewer at the base of the head (25% bigger in the polish pass).
  - Open jaw with ivory fangs, glowing aqua eyes and gill-fin spikes.
  - Angry gold brows sweep up into horns that clasp the pearl's bezel.
  - The back of the skull has overlapping teal scale plates under a spiny gold fin crest.
- **Pearl.** A big aqua Neon pearl with a white-hot core showing through both faces.
- **Glow.** Long aqua Neon lines along every tine edge, barb, claw and wave lip, plus the pearl, the eyes and a ring on the butt.
  - Every render has a compositor Fog Glow halo grown from the emission pass only, so the glow radiates without washing out the darks.
- **Shaft.** Deep abyss navy with a painted fish-scale motif, about 1.5x thicker than round 1.
  - Tight criss-cross leather grip wrap (deep crimson over dark coral) on a crimson sleeve, split by gold bands, with a matching low wrap.
  - Weighted scalloped butt cap ending in a gold spike ringed with small down-swept spikes.
- **Gold.** Rich gold: brown-shaded lows, muted mids, pale warm-yellow highlights.
- **Grip and pivot.** The grip is the middle of the coral braid (`grip_point`).
  - The head-heavy balance point is exported separately as `throw_pivot`.
  - `tip_point` (centre needle) is the impact and tidal-wave spawn point.

## Numbers
- Height 6.4 studs, authored at hero size; set the play size in Studio by uniform scale.
- 18,268 triangles (scythe ~17k): textured 16,404, glow 1,552, cores 312. Every mesh is under 20k.
- One 1024 `BaseColor.png`, baked.
- Exports: `Model.fbx` (-Z forward, Y up, texture embedded) and `Model.glb`. Both re-imported with matching triangle counts, 0 loose vertices and 0 zero-area faces.

Rebuild: `blender -b --factory-startup --threads 2 --python build_poseidons_trident.py`. For flat shape shots, set `MODE=quick` and `OUT=<dir>`.
