# Owl pet (Epic, strong suit: bosses)

**Status:** verified in Blender 5.2, untested in Studio.

The Owl marks the toughest nearby enemy, and the player's hits on that enemy do +20% (the effect is game code).

## Design

The Owl is a chunky chibi owl, low-poly with painterly textures.

- **Body:** an egg body that is mostly head. The head is about as wide as the body.
- **Plumage:** warm tawny. The belly is cream with seven broad painted chevrons.
- **Face:** a flat cream two-ring/heart facial disc with radial brush strokes, a clear dark-brown rim line and a tawny V brow.
- **Ear tufts:** two soft feather tufts fused into the head. Each tapers from a thick base to a smaller tip and leans about 50° out and a little back.
- **Beak:** a small hooked warm-horn beak that flows out of the disc.
- **Eyes:** big glossy amber eyes with big pupils and two catchlights each.
- **Wings:** broad rounded fans, each its own part on a shoulder pivot. Each wing is one thick fused surface with a thicker leading edge, cupped along its length and across its chord, with three wide rounded scallops at the tip. The outside has large cream covert spots; the underside is pale.
- **Feet:** stubby orange-tan feet with three toes, feathered cream tops and dark claw tips.
- **Tail:** a short rounded fan fused into the body, with two brown bars.
- **Back:** a pale nape and a broad cream feather V on the back of the head.
- **Role prop:** a chunky brass monocle-scope over the owl's right eye (Blender −X). It has a knurled rim and a stitched leather strap that wraps around the back of the head to a small brass buckle.
- **Neon accent:** the lens reticle is a separate `Owl_Reticle_Glow` mesh: a thin ring plus four crosshair ticks. The painted eye shows through it. The glow is subtle and warm red-amber.

### Mesh

- Body, head, wings and feet are meshed straight from a coarse lattice and flat shaded. This gives broad, even facets like cut gemstone planes.
- The scope is decimated to 900 triangles.
- The texture is a single 1024 atlas. Its lighting is baked in:
  - AO;
  - a soft key light with clearly visible facets;
  - warm shadows;
  - a cool rim light.

### Presentation choice

The views are rendered **hovering 1.5 studs up with the wings mid-beat**: raised about 35° above horizontal and cupped 24° forward. Pets are always moving in game (following, flying to targets), so the flying state is the rest and presentation pose. The perch is only an occasional idle (a hop-turn and a head turn) and is shown in the pose check.

## Parts and pivots

Pivots are in Blender world coordinates, in studs. Studio = (−x, z, y).

| Part | Pivot (Blender) | Joint | Parent | Triangles |
|---|---|---|---|---|
| Owl_Body | (0, 0.03, 0.62) | root (belly centre) | none | 1,100 |
| Owl_Head | (0, 0, 1.00) | neck, hidden inside the head | Body | 1,796 |
| Owl_WingL / R | (±0.52, 0.10, 0.92) | shoulder (round root sunk in the body side) | Body | 1,308 each |
| Owl_FootL / R | (±0.22, −0.10, 0.24) | hip, inside the belly | Body | 496 each |
| Owl_Scope | rim centre, in front of the right eye | weld | Head | 900 |
| Owl_Reticle_Glow | reticle centre | weld, Material = Neon | Scope | 208 |

- **Total:** 7,612 triangles (the owner's target is about 6–8k; the Epic cap is 12k).
- **Size:** 1.65 wide × 1.48 long × 2.04 tall when perched.

## Studio data

`studio-install-data.json` contains the parts, pivots, joint parents and rest rotation, plus:

- `"locomotion": "fly"` and `locomotion_data`:
  - hover height 1.5 studs;
  - a bob of 0.12 studs over 1.6 s;
  - a slow wingbeat with a 0.6 s period:
    - WingL rotates between −112° (up) and −36° (down) in Blender Y, mirrored on the right;
    - a flap-flap-glide rhythm.
  - `frames`, with angles in both Blender and Studio axes:
    - `hover_mid`
    - `wings_up`
    - `wings_down`
    - `glide`
    - `mark_target` (head tilted 14° and yawed 20° so the scoped eye leads, wings half-spread)
    - `head_turn`
    - `perch_hop_turn`
- `"vfx"`:
  - a Neon reticle pulse on the `_Glow` part (Transparency sine, faster while marking, an optional PointLight);
  - a faint feather/sparkle ParticleEmitter trail from the back while flying;
  - optional wingtip Trails while gliding;
  - the mark colour on the target: a Highlight, a reticle Billboard and an optional Beam.

## Files

- `build_owl.py`: the generator. Use `-- --shape` for a quick flat-colour run.
- `validate_exports.py`: re-imports the FBX and GLB and writes the results to `validation-report.json`.
- `exports/fbx/owl.fbx` and `exports/glb/owl.glb`.
- `textures/owl.png`.
- `owl.blend`.
- `previews/`: the presentation renders and `sheet.png`.
