# Shadow Daggers (Godly, melee), round 2

Ability (RARITY_GODLY_ARMOR.md section 9): twin daggers zip from enemy to enemy, hitting up to 5 in a chain.

**Status: Blender-verified, Studio untested.**

Round 2 is a full rebuild. The v1 violet moth daggers were rejected as flat, greyish, low on aura and too
flowery. The new design follows the owner's demon-dagger references in `reference/` (a matched but
distinct pair), translated into chunky stylised low poly.

## Design
- **Left hand, "Rend".** A near-black jagged blade with a crimson cast:
  - eight hooked serrations on the cutting edge;
  - four hooked back-spikes on the spine;
  - two jagged lightning cracks of crimson Neon, with spurs, on both faces;
  - a crimson Neon cutting edge with a hot rim line, and a Neon false edge on the spine near the needle tip.
- **Right hand, "Fang".** A dark blood-crimson broad blade with a near-black spine half:
  - asymmetric, crooked bone shards with broken edges climb mostly along the spine side, in varied sizes, with two
    small ones on the edge side by the guard. They are warm ivory with dark crevices;
  - three hooked teeth on the cutting edge;
  - a hooked tip with a spine barb behind it, plus a smaller barb lower down;
  - a hot Neon edge and a Neon line along the ridge.
- **Blades.** Both are long and sweeping, about 2x the hilt length (Rend's blade is about 3 studs), slimmer toward
  the needle points. They are diamond in section (a centre ridge plus a
  steeper edge bevel) with crisp 1-segment bevels.
- **Shared hilt.**
  - The focal piece is a demon eye guard on both faces: bone lids with flicked corners, angry bone brows, a
    crimson Neon eyeball, a hot iris and a black slit pupil.
  - Short gold claws grip the blade base. Big gold talons sweep out and down, and bone claw plates sweep up.
  - The grip is wrapped in dragon scales: seven overlapping rows, tips down, between gold collars.
  - A gold four-claw pommel grips a crimson Neon spike.
- **Palette.** Near-black with a crimson cast, deep blood crimson, warm bone/ivory, brown-shaded gold, and a
  purple-black scale grip. The Neon is (255, 14, 30) with a hot core of (255, 64, 48).
- **Aura.** Every render has an emission-driven compositor Glare (Bloom plus Fog Glow), so only the Neon
  radiates. `studio-install-data.json` `vfx_notes` cover the idle red aura haze ParticleEmitter and the ability:
  crimson afterimage chains between up to 5 enemies.

## Files
- `build_shadow_daggers.py` is the self-contained generator. `MODE=quick` makes flat-colour review renders into
  `wip/`.
- The model files are `Model.blend`, `Model.fbx` and `Model.glb`, plus the texture `BaseColor.png` (1024, baked).
  Both daggers share the one atlas, each on its own UV islands.
- There are six meshes: `ShadowDaggers_L` / `_L_Glow` / `_L_GlowCore` (Rend) and `ShadowDaggers_R` / `_R_Glow` /
  `_R_GlowCore` (Fang).
- `studio-install-data.json` uses the v1 schema: per-part centre and size, plus `daggers.left_hand` /
  `daggers.right_hand` grip points and blade axes.
- `validation.json` covers the triangle counts and the re-import of both exports.
- The renders are `Preview`, `Front`, `Back`, `Side`, `Hero`, `Scale`, `Compare_Catalog` and `Sheet`.

## Triangles
The pair totals 19,052 triangles: Rend (left) 9,542 and Fang (right) 9,510.
- Rend: 7,406 textured, 1,680 glow, 456 core.
- Fang: 8,386 textured, 698 glow, 426 core.

No mesh is over 20k. `validation.json` records no loose vertices or zero-area faces, and the GLB and FBX re-imports match the triangle count.

## Known limits
- At 19,052 triangles, the pair is over the brief's ~15k guideline (the scythe is ~17k). The longer blades added about 1.4k. Rend's crack veins and the eye lids are the easiest places to trim.
- Catalogue renders use AgX with the Punchy look, so the Neon stays deep red. Their backdrop is therefore slightly darker than the older catalogue tiles.
- Studio import, Neon look, hand attachment and play scale are untested.
