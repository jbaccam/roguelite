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

## Wider rendered horizontal swings — September 28, 2026

User request: make horizontal strikes on all melee weapons wider for looks, even if they hit no more zombies. Re-checked against `example swinging.mp4` (17.9–18.35 s greatsword sweep): about a 200° arc, but a much bigger radius than ours. Ours already swept 210°, but close zombies pulled the blade in to 0.35–3 studs.

- `WeaponMotion.pose` / `ChainWeaponMotion.pose` take a trailing `visual` flag. Only `RogueliteCombat.client.luau` passes it. With it, horizontal cuts sweep ±120° (`WeaponMotion.VisualSweepHalfAngle`) instead of ±105°. Against close targets the blade sits farther out, with its inner quarter still on the target, and the reach pulse is softened to 40%. Both paths stay centred on the target, so the visible blade crosses the target when the hit lands.
- The server hit sampling omits the flag, so hit coverage, range and timing are unchanged. Diagonal, thrust, overhead and slap strokes are untouched.
- `SwingVisuals`: blade/blob trails last 0.22 s (heavy 0.25, katana 0.19) so most of the arc shows at once. Heavy-weapon ground crescents span ±115° to match. Crescents are still heavy-only, per the earlier decision.
- Verification (Studio Edit, fresh clones): MeleeMotionTests 20,064 (adds rendered-width, crossing and overlap checks); rendered-path checks 128,378 (every horizontal-capable weapon at 1.2–6 studs, both sides: identical damage window, no jumps over 0.6 studs, smooth recovery; chains start at 120°); unchanged SpringComboTests 15,069, TravelAccuracyTests 169, WeaponBehaviorTests 19,905. Single-client Play with a tier-1 Frying Pan against 8 regular zombies: live sweeps spanned 232–242° with the pan 4.0 studs out, against 1.9–3.1 studs on the hit path. A screenshot showed the wide white arc through the pack. The console was clean.

Not tested: multiple real clients, other weapons live in Play (covered by the module checks above), mobile.

## Legendary Tier IV moves and the gold aura — October 2, 2026 (plan J item 8, rarity step 3)

User: Legendary extra moves only at Tier IV; "make the vfx sick af and use blender if you need to model anything". Server: `LegendaryMoves` (ServerScriptService, sandboxed) owns every hit; numbers in `WeaponCatalog.Legendary`. Client: `LegendaryVisuals` (RogueliteCombat, sandboxed) draws from the `LegendaryFX` remote; sounds in `audio/RogueliteSounds.client.luau` (the existing kit, pitched). Meshes: `roguelite-planning/blender-legendary-vfx` (SlashCore, SlashGlow, ShockRing) built at runtime with EditableMesh from `LegendaryVisuals/MeshData`; Neon-part fallback if that fails.

| Weapon | Move (server) | What you see |
|---|---|---|
| Katana | Every 3rd swing: a flying slash, 30 studs at 78 studs/s, 3.4 wide, hits each enemy it passes once for 75% of a swing | A white-hot crescent with an amber glow and a fainter wake, wind streaks off both tips, star sparks, a thin slice scorched into the ground, a cut flash on every enemy it passes, sparks where it ends |
| Excalibur | Every swing: a golden beam slash, 22 studs at 56 studs/s, 4.4 wide, 45% | The same crescent in gold, broader, carrying its own gold light and rising holy motes |
| Rocket Launcher | Every 4th rocket flies ~0.3 s, then splits into 3 homing minis (target first, then the two nearest); each bursts for 45% (rocket falloff, 5.5 radius) | The real rocket model with a gold band, a wobble as it charges, a gold crack of light and puff at the split, three small rockets curving out on smoke trails, each with its own pop, flash, scorch and amber ring |
| Deck of Cards | Every 5th throw is a Royal Flush: 5 gold cards fanned over 26°, straight lines 1.25x the range, each piercing everything for 50% of the volley | "ROYAL FLUSH!" pops over your head; five gold cards reading 10, J, Q, K, A of spades fan open like a held hand, then spin out on gold trails, glinting past every enemy and bursting into glitter |
| Bowling Ball | A roll that hits 5+ enemies is a STRIKE!: a pin explosion where the ball stopped, radius 9, 100%, knocks enemies out | "STRIKE!" slams in; ten real bowling pins stand in their triangle for a blink, then blow outward spinning; a dust ring, an amber rim, dust puffs and a camera kick |
| Wrecking Ball | Each swing that connects sends a ground shockwave from under the first enemy hit: radius 11 over 0.42 s, 40% as it reaches each enemy, knocks them out | A dust shockwave band rolling outward with the amber dashed rim, cracked ground, rock chips, dust puffs as it passes, a small camera kick |
| Mjolnir | Every 4th throw: a lightning strike where it lands, 0.2 s later, radius 8, 120% | A crackling blue target ring closes in; a forked bolt (with one gold fork) drops from the sky, flickering; a flash, an electric ring, a scorch mark, sparks and small arcs to the enemies caught in it |

**Gold aura:** every Legendary floats with a faint gold glint. At Tier IV the full aura turns on (gold haze from the mesh, star motes, a light). It builds with the slot's `LegendaryCharge` (server-set count toward the move), shimmers faster when the next attack is the move, and flares when it fires.

**Rules kept:** every move hit is a secondary hit (no crits, chains, knockback or other specials), so a move can never start another move. Movers stop at walls. At most 48 slashes/cards in flight and 256 scheduled hits per server; effects are skipped beyond 170 studs from the camera, and the camera kick is only for the player who made the move (off with the Screen shake setting). Effects use existing textures only (Slash, Star, Glow, Lightning, Ring, Scorch, Cracks, Dust).

**Tests:** `LegendaryMovesTests` (pure helpers and the catalog: exactly the 7 Legendaries, moves only at Tier IV, the user's counts) PASS, 99 checks, Edit-mode harness, 2026-10-02. Not run yet: any Studio Play test of the moves or their visuals.
