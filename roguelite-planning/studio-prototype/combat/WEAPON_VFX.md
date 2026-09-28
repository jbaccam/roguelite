# Weapon VFX and weapon contact — September 27, 2026

Client-only presentation pass over every equipped weapon, guided by the user's `C:/Users/Jeremiah/Videos/attacks/example swinging.mp4` (thin white blade swooshes; big white crescents with an amber dashed rim). Everything is driven by the existing server packets (`Shot`, `SpecialFX`, `ArcShot`) and replicated slot attributes. No effect changes targeting, hits, damage or timing. The one gameplay-data change is listed under "Catalog change".

User decisions (asked first):
- **Power Washer:** keeps its nonstop stream and low damage. Only the look changed.
- **Crystal Ball:** gets lightning. The Magic Staff shoots an energy orb.
- **Melee:** blade trails on every swing. Heavy weapons only also get ground crescents.
- **Pandora:** shoots a cursed spirit skull on its mortar arc. A follow-up asked for souls escaping the box, and for a purple smoke splash on impact instead of orbiting balls.

## Modules (ReplicatedStorage.RogueliteCombat)

| Module | Role |
| --- | --- |
| `VfxKit` | Shared helpers: one budgeted animation loop, 3-lobe clouds (rocket-smoke style), shards, flat ring/crescent segments, brief point lights, pops, jagged bolts, particle bursts, camera-facing trails. Everything is anchored, non-colliding and non-queryable, and distance-culled at 140–160 studs from the camera. |
| `WeaponSpacing` | Capsule contact solver that keeps floating weapons from passing through each other. |
| `SwingVisuals` | Melee swooshes, heavy crescents, overhead slam rings. |
| `ProjectileStyleVisuals` | Per-weapon heads/trails for StatProjectiles weapons, plus chain lightning. |
| `PandoraVisuals` | Pandora idle glow, lid burst with escaping souls, spirit skull, purple smoke splash. |
| `ThrownVisuals` | Trails/landing effects for modeled throws. |

All six new modules must be `Sandboxed=true` with the same Capabilities as `ArcVisuals`. Otherwise the sandboxed combat LocalScript cannot require them. Rojo does not carry these properties, so set them in Studio.

## Per weapon

| Weapon | Effect |
| --- | --- |
| Katana, Spatula, Pan | White blade swoosh from mid-blade to tip during the active cut. |
| Bat, Shovel, Mjolnir (melee), Excalibur | Swoosh plus a flat ground crescent that reveals with the sweep, then widens and fades (white body, amber dashed rim). Downward strokes instead make a ground slam ring and dust puffs. Excalibur's swoosh/crescent is tinted pale gold. |
| Cinder Block, Wrecking Ball | Camera-facing swoosh at the striking head; heavy crescent/slam as above. |
| Nunchucks, Kusarigama | Swoosh follows the swinging baton / sickle through the chain rig. |
| Steak | Camera-facing swoosh at the slapping face. |
| Paint Roller | Blue paint-coloured swoosh. |
| Boxing Gloves | Short punch streak on the punching fist only. |
| Magic Staff | Energy orb (white core, blue glow, violet halo, sparkles, small light). Flare at the staff crystal on cast; layered pop, shards and light on impact. Its chain-lightning trait moved to the Crystal Ball. |
| Crystal Ball | Violet-white lightning from the crystal core to a travelling spark. Each bounce leaves a flickering strike and restarts from the hit enemy. |
| Medusa's Head | Green gaze bolt fading to stone grey; stone dust and grey chips on impact. |
| Nail Gun | Small steel nail with a short bright streak. Existing world-impact sprites remain. Point-blank hits resolve in one server step, so no flight is drawn then. |
| Yo-Yo | The disc flies out on a string drawn from its finger loop, spins, then reels back. The resting disc hides while it is out. |
| Chain lightning (any source) | Two-flicker jagged bolt plus sparks. Crystal Ball uses violet; Mjolnir and items use blue-white. |
| Kunai | Thin white streak. |
| Boomerang | Wing-tip ribbon that sweeps a soft spinning disc. |
| Egg | Faint trail; yolk splat and shell bits on landing. |
| Bowling Pin | Faint trail; white/red chips and dust on landing. |
| Bowling Ball | Dust puffs while rolling; dust burst at the end. |
| Molotov | Flame trail; glass shards, fire pop and light on impact (existing fire zone unchanged). |
| Mjolnir (thrown) | Blue-white trail with small crackling sparks. |
| Power Washer | Nonstop stream unchanged (damage unchanged). Adds nozzle mist, plus splash mist and droplets where the jet actually hits (client raycast; falling droplets at the tip when nothing is hit). |
| Deck of Cards | Faint white streak on flying cards. |
| Pandora's Box | Faint purple light and wisps leak from the closed lid. On opening: a light column, dark smoke, sparks and five souls spiralling up out of the box. Projectile: a part-built spirit skull (glowing eyes, chattering jaw, violet aura, wispy tail) that rises out of the lid onto the existing high mortar arc. Impact: low purple smoke puff, smoke rolling outward, violet droplets splashing out under gravity, and a soft ground ripple. `ReplaceableProjectile` is still the cranium part if a skull mesh is approved later. |

Unchanged: Glock/Draco/Shotgun (tracers, muzzle flashes, impact sprites), rocket, T-shirt cannon, fart gun, rubber duck flame, vacuum.

## Weapons are solid to each other

After each frame's poses, the client builds one capsule per visible weapon from its reviewed `BoundsSize`/`BoundsCenter`. The capsule runs along the longest axis, with a radius of 0.82× the larger cross-section. Egg/pin capsules are widened over their side reserves. Overlapping capsules are pushed apart with a 4-iteration solver. Weapons in an active melee attack weigh 6×, so idle neighbours make room instead of blocking the cut. The push applies immediately, and only the drift back home is eased (rate 9/s). Offsets cap at 3.2 studs, and sideways separation is preferred. This is cosmetic only; server hit poses and damage are unchanged. Muzzles, trails and flashes follow the displaced model.

## Catalog change

`WeaponCatalog`: `d.lightning` moved from Magic Staff (30) to Crystal Ball (35). Mjolnir keeps it. The shop's "Lightning" trait tag moves with it. The staff loses its every-5th-hit chain proc (roughly 8% of its damage at base stats), and the Crystal Ball gains it.

## Verification (single client, Studio Play, practice target, Studio-only loadouts)

- `WeaponSpacingTests.luau` (disposable, not in Rojo): 1,808 checks passed. Across 300 random dense six-weapon clusters, the worst leftover overlap was 0.016 studs. Heavy-mass, coincident-axis, cap and smoothing cases are included.
- Live six-weapon loadout (katana, bat, Excalibur, staff, crystal ball, Pandora), 8 s:
  - Before the instant push, summed overlap was 35.7 stud-frames, with 77 pair-frames deeper than 0.15 studs (worst 1.10).
  - After: 0.78 stud-frames, 2 pair-frames deeper than 0.15 (worst 0.43).
  - Swooshes, crescents, orbs, lightning, the skull, escaping souls and smoke bursts were all observed. No old orbiting impact wisps appeared.
- Direct client harness: every style/impact function (skull, lid open, impact, idle glow, 7 thrown ids, 5 projectile styles, chain lightning, crescent and slam) ran without errors. All effect parts cleaned themselves up within 1.5 s.
- Second live loadout (yo-yo, nails, washer, Medusa, gloves, wrecking ball): string yo-yo with the hidden resting disc, washer splash mist, glove streaks, wrecking-ball swoosh and Medusa gaze were observed. Nails were observed in flight from 15 studs.
- Thrown loadout (boomerang, kunai, Molotov, egg, ball, pin): all six flights carried their trails. The first live run had the camera about 14,000 studs away on the shop/armory screens, so distance culling correctly skipped the landings. A rerun with the camera on the player (kunai, Molotov, egg, ball, pin, Pandora; 7 s) observed shards, dust clouds, pops, flashes, escaping souls, the skull and smoke bursts, with no orbiting impact wisps.
- Screenshots confirmed: the white/amber crescent and white katana swoosh, the open Pandora box with souls and the rising skull, and Crystal Ball lightning. The first Pandora screenshot looked too strong (bright soul beams, a tall smoke column, strong purple floor light). These were toned down, and a follow-up screenshot showed thin violet soul wisps alongside the rolling-ball dust, pin/egg trails and Molotov flame.
- The console showed no errors from these modules after two fixes: the Sandboxed flags, and an invalid `BlockMesh.Bevel` property.
- Both Rojo packages build.

Not tested: multiple real clients, latency, mobile performance with four players' effects, and every stat-scaled size.
