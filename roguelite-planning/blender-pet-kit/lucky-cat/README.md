# Lucky Cat pet

Epic pet, strong suit **Luck** (+Luck: the run shop rolls better tiers more often). A chibi calico maneki-neko.
**Blender-verified, Studio untested.** `validation-report.json`: PASS for FBX and GLB (Blender 5.2 re-import).

## Design
- **Rest pose:** standing on all four legs in a walk-ready chibi stance (pets are always moving), tail up. It is 2.06
  studs tall and 1.81 long, faces Blender -Y (Studio -Z), and its left is Blender +X.
- **Head:** a big round head, about 1.3 wide, on a small bean body with short chunky legs. It has big glossy green
  eyes with two catchlights, a pink nose, a "w" mouth, whisker dots and lines, blush and pink inner ears.
- **Coat:** warm cream-white with peach shadows, plus a few soft calico patches: orange on the left ear, back and tail,
  and charcoal on the right ear, right flank and tail tip. Pink paw beans are painted on every sole.
- **Collar and props:** a red collar fused into the body, a separate dangling gold bell, and a separate dangling koban
  coin. The coin is rich gold with a darker edge, horizontal ridges and two stamped seals.
- **Glow (Epic):** the coin is painted gold in the atlas. `LuckyCat_CoinRim_Glow` is a thin tube around the coin edge;
  in Studio it should be Neon, Color (255, 196, 92), welded to the coin.
- **Legs blend into the body:** shoulder and haunch masses are part of the BODY mesh (soft bulges filleted into the
  torso). Each leg starts as a wide ball centred on its pivot, hidden inside that mass at every rotation, and tapers to
  the paw. Legs use the same fur paint field as the body, so the coat colour is continuous across the join.
- **Low-poly method:** the same as the Penguin. SDF smooth unions are meshed on a coarse voxel lattice (broad even
  facets) and flat shaded, then baked into one 1024 painterly atlas.

## Parts and pivots
| Part | Tris | Pivot (Blender) | Parent |
|---|---|---|---|
| `LuckyCat_Body` | 872 | (0, 0.10, 0.62) | root |
| `LuckyCat_Head` | 1,700 | (0, -0.36, 0.93) | Body |
| `LuckyCat_FrontL` / `FrontR` | 588 each | (±0.22, -0.22, 0.50) | Body |
| `LuckyCat_HindL` / `HindR` | 604 each | (±0.25, 0.40, 0.52) | Body |
| `LuckyCat_Tail` | 352 | (0, 0.60, 0.74) | Body |
| `LuckyCat_Bell` | 312 | (-0.06, -0.55, 0.71) | Body |
| `LuckyCat_Coin` | 264 | coin eyelet on the collar | Body |
| `LuckyCat_CoinRim_Glow` | 288 | same as Coin | Coin (weld) |

Total 6,172 triangles.

## Motion data (`studio-install-data.json`)
- **`"locomotion": "cat_walk"`:** a four-legged walk in diagonal pairs (A = left front + right hind reach, B = right
  front + left hind reach), with a gentle body bob and roll.
- **`beckon_emote`:** a short emote while standing. The right front paw lifts beside the collar and cheek, beans facing
  forward, and waves at the shoulder.
- **`extras`:** a head tilt and a tail swish.
- **`vfx`:** CoinSparkle (always on) and WalkSparkleTrail (only while moving).
- **`previews/pose-check.png`:** walk A, walk B, beckon up and down, head tilt and tail swish. No gaps were seen at any
  joint.

## Open issues
- Not seen in Studio: import, texture colour, the Neon rim look and the pivots are unchecked.
- The legs are short (chibi), so the beckon paw reaches collar and lower-cheek height rather than true cheek height.
- The preview armature `LuckyCat_Rig` exists only in the .blend; the exports are plain rigid parts.

Rebuild: `blender -b --factory-startup --threads 2 --python build_lucky_cat.py` (about 6.5 min), then `--python validate_exports.py`.
