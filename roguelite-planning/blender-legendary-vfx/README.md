# Legendary VFX meshes (plan J item 8, rarity step 3)

Three small vertex-coloured meshes for the Tier IV Legendary moves. The game never imports them as
assets: `generate_legendary_vfx.py` writes them as a Luau table
(`studio-prototype/combat/LegendaryVisuals/MeshData.luau`), and `LegendaryVisuals` builds them on
the client with `EditableMesh`, the way `RocketExplosionVisuals` builds the cartoon explosion.

| Mesh | Used by | Shape | Triangles |
|---|---|---|---:|
| `SlashCore` | Katana flying slash, Excalibur beam slash | thin crescent, convex side forward (-Z), white-hot, faceted ridge | 288 |
| `SlashGlow` | the same, the glow behind it (and a wider, fainter wake) | wide crescent fading to clear at the back and both tips | 288 |
| `ShockRing` | Wrecking Ball shockwave, bowling STRIKE, Mjolnir's lightning ring | short band flaring outward with a ragged dust crown | 288 |

Colours are mostly white so the game tints per weapon (`MeshPart.Color`): Katana steel-white with an
amber glow, Excalibur gold, the shockwave dust beige, Mjolnir's ring electric blue.

## Run

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python generate_legendary_vfx.py
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python validate_exports.py
```

Outputs: `exports/glb`, `exports/fbx` (reference), `previews/legendary-vfx-hero.png` and
`legendary-vfx-top.png` (Cycles, bloom; left to right: Katana slash, Excalibur slash, shockwave
ring), `polygon-report.json`, `validation-report.json`, `legendary-vfx.blend`.

The generator is self-contained (it reads no other kit's code). No user-supplied images were used.

## Status

- Blender-verified 2026-10-02: generator run, previews rendered, `validate_exports.py` PASS (GLB
  triangle counts and colour attributes; the Luau data's indices, one alpha per vertex, one colour
  per triangle, bounds equal to `size`).
- Studio: not yet built in Studio. If `EditableMesh` isn't available, every effect falls back to
  Neon parts (`LegendaryVisuals` warns once).
