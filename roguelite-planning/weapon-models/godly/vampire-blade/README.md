# Vampire Blade (Godly, melee)

Ability (RARITY_GODLY_ARMOR.md section 9): every hit heals you, and kills send red wisps flying into you for extra healing.

**Status: Blender-verified, Studio untested.**

## Design
- **Blade.** A big gothic longsword in blackened steel with a red cast.
  - Both cutting edges are hot crimson Neon, with four hooked barbs per edge that hook back toward the guard.
  - The tip is flared, notched and needle-pointed.
  - Each face has a deep-wine enamel panel framed by gold beads.
  - A glowing blood channel (Neon fuller with a hot core line) runs through three rune glyphs (fangs, eye, double chevron) and three branching blood veins.
- **Guard (focal piece).** A snarling bat skull on the front of a gold, fang-pointed shield boss:
  - bone skull, glowing slanted red eyes with hot slit pupils;
  - angry gold brows and an open jaw with bone fangs;
  - tall black ears with crimson inner ears.

  The back of the boss holds a Neon blood gem. Gold langets carry Neon blood drops on both blade faces.
- **Bat wings.** Thick crimson membranes with three scalloped lobes and glowing veins. Black finger bones run past the scallops into hooked claws. Gold arm bones end in inward-hooked talons, with gold shoulder spurs at the wing roots. The guard is mirror-built in x.
- **Grip and pommel.** Interleaved crimson and black leather straps with gold crown bands. A big faceted ruby sits in a gold four-claw setting and ends in a glowing crystal shard.
- **Palette.**
  - Near-black steel with a red cast, and deep wine.
  - Crimson enamel, and gold with brown shading.
  - Bone, and ruby.
  - Neon glow (255, 6, 36) and hot core (255, 72, 48).
- **Renders.** All renders use Khronos PBR Neutral, because AgX washed the crimson Neon out to salmon. Every render has a bloom pass for the red aura.

## Files
- `build_vampire_blade.py` is the self-contained generator. It uses the Reaper's Scythe pipeline copied in. `MODE=quick` makes flat review renders.
- The model files are `Model.blend`, `Model.fbx` and `Model.glb`, plus the texture `BaseColor.png` (1024, baked).
- There are three meshes: `VampireBlade` (textured), `VampireBlade_Glow` (Neon) and `VampireBlade_GlowCore` (Neon).
- `studio-install-data.json` holds the part centres and sizes, the grip point, the float pivot and the blade axis. Its `vfx_notes` cover:
  - the kill wisps;
  - the wisp arrival burst;
  - the hit-heal flash;
  - the swing trail;
  - the red aura haze;
  - the idle blood drips.
- `validation.json` holds the counts, the re-import of both exports, and a symmetry measure.
- The renders are `Preview`, `Front`, `Back`, `Side`, `Hero`, `Scale`, `Compare_Catalog` and `Sheet`.

## Triangles
The total is 17,276 triangles:

| Mesh | Triangles |
| --- | --- |
| Textured | 14,804 |
| Glow | 2,252 |
| Core | 220 |

That matches the scythe's ~17k. The validation checks found:
- no loose vertices and no zero-area faces;
- triangle counts that match on the GLB and FBX re-imports.

The hero size is 5.06 studs tall and 2.68 studs across the guard.

## Known imperfections
- **Symmetry.** Above the grip, the textured mesh is mirror-exact except for boolean and bevel triangulation around the rune cut-ins and the wing bevels, which is at most 0.025 studs and not visible. The glow meshes are exact. The helical grip wrap is chiral by design.
- **Bat skull.** In the catalogue 3/4 view, one bat ear partly overlaps the skull.
- **Ears from the side.** The ears read as flat plates in the side view.
- **Studio.** Studio import, the Neon look in Play and the in-game scale are untested.
