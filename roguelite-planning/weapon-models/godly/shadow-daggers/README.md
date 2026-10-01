# Shadow Daggers (Godly, melee)

Ability (RARITY_GODLY_ARMOR.md section 9): twin daggers zip from enemy to enemy, hitting up to 5 in a chain.

**Status: Blender-verified, Studio untested.**

## Design
- A mirrored pair, one per hand. They're oversized, chunky curved obsidian blades (about 3.3 studs at hero size) so they read at thumbnail size.
- **Blade.** The long convex edge glows violet Neon with a pale lavender core line. The concave spine has a gold strip and two swept back-hooks, and the spine glows near the tip as a false edge. Both faces carry gold-framed Neon moth-eye diamond runes.
- **Guard.** A death's-head moth sits in a gold socket collar:
  - a bone skull with glowing eyes on the thorax, on both faces;
  - violet enamel forewings with gold piping and Neon eye-spot gems;
  - smoky hindwings that curl into wisp tails.
- **Grip and pommel.** A dark wrapped grip with three gold bands. A gold claw pommel holds a violet Neon gem, with two curling smoke wisps.
- **Palette.** Obsidian violet-black, violet steel, enamel violet, gold with brown shading, bone. The glow is Neon (170, 64, 255) with core (232, 206, 255).

## Files
- `build_shadow_daggers.py` is the self-contained generator (pipeline copied from the Reaper's Scythe). `MODE=quick` makes flat review renders.
- The model files are `Model.blend`, `Model.fbx` and `Model.glb`, plus the texture `BaseColor.png` (1024, baked, shared by both daggers).
- There are six meshes: `ShadowDaggers_L` / `_L_Glow` / `_L_GlowCore` and the same three for `_R`. The right dagger is an exact x-mirror of the left, with the same UVs.
- `studio-install-data.json` gives each part's centre and size, plus per-hand `daggers.left_hand` / `daggers.right_hand` grip points and blade axes. It also holds the `vfx_notes` for the violet afterimage chain.
- `validation.json` covers the triangle counts, the re-import of both exports, and the mirror-exactness check.
- The renders are `Preview`, `Front`, `Back`, `Side`, `Hero`, `Scale`, `Compare_Catalog` and `Sheet`.

## Triangles
The pair totals 16,944 triangles, which is 8,472 per dagger. Each dagger splits into 7,546 textured, 706 glow and 220 core triangles. No mesh is over 20k.

`validation.json` records these checks:
- no loose vertices or zero-area faces;
- the GLB and FBX re-imports match the triangle count;
- the right dagger is an exact mirror of the left.

## Known limits
- The baked lighting is mirrored on the right dagger, because it shares the left dagger's texture. Its painted key light therefore comes from the upper right.
- Studio import, Neon look, hand attachment and play scale are untested.
