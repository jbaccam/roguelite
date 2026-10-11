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

User: Legendary extra moves only at Tier IV; "make the vfx sick af and use blender if you need to model anything". Server: `LegendaryMoves` (ServerScriptService, sandboxed) owns every hit; numbers in `WeaponCatalog.Legendary`. Client: `LegendaryVisuals` (RogueliteCombat, sandboxed) draws from the `LegendaryFX` remote; sounds in `audio/RogueliteSounds.client.luau` (the existing kit, pitched). Look: the game's own flat effect language. A first pass modelled a 3D slash crescent and shockwave band in Blender; the user said it looked "really 3d and model heavy unlike all the other vfx in the game", so it was dropped the same day. Crescents are flat Neon segments with the white/amber dashed rim (built like VfxKit.ring), rings are the painted ShockwaveRing texture on the ground (like the Trident's wave), dust is VfxKit.cloud plus the painted DustPuff flipbook, sparks and cuts are the painted Star and Slash textures. Cards, the rocket and the bowling pins are props.

| Weapon | Move (server) | What you see |
|---|---|---|
| Katana | Every 3rd swing: a flying slash, 30 studs at 78 studs/s, 3.4 wide, hits each enemy it passes once for 75% of a swing | A flat white crescent with the amber dashed rim (the swing crescent, set loose) and a soft glow under it, flying just off the ground; wind streaks off both tips, star sparks, a thin slice left on the ground, a cut flash on every enemy it passes |
| Excalibur | Every swing: a golden beam slash, 22 studs at 56 studs/s, 4.4 wide, 45% | The same flat crescent in pale gold with gold dashes, broader, carrying its own gold light and rising holy motes |
| Rocket Launcher | Every 4th rocket flies ~0.3 s, then splits into 3 homing minis (target first, then the two nearest); each bursts for 45% (rocket falloff, 5.5 radius) | The real rocket model with a gold band, a wobble as it charges, a gold crack of light and puff at the split, three small rockets curving out on smoke trails, each with its own pop, flash, scorch and amber ring |
| Deck of Cards | Every 5th throw is a Royal Flush: 5 gold cards fanned over 26°, straight lines 1.25x the range, each piercing everything for 50% of the volley | "ROYAL FLUSH!" pops over your head; five gold cards reading 10, J, Q, K, A of spades fan open like a held hand, then spin out on gold trails, glinting past every enemy and bursting into glitter |
| Bowling Ball | A roll that hits 5+ enemies is a STRIKE!: a pin explosion where the ball stopped, radius 9, 100%, knocks enemies out | "STRIKE!" slams in; ten real bowling pins stand in their triangle for a blink, then blow outward spinning; a dust ring, an amber rim, dust puffs and a camera kick |
| Wrecking Ball | Each swing that connects sends a ground shockwave from under the first enemy hit: radius 11 over 0.42 s, 40% as it reaches each enemy, knocks them out | The painted shockwave rolling out on the ground with the amber dashed rim, cracked ground, rock chips, dust as it passes, a small camera kick |
| Mjolnir | Every 4th throw: a lightning strike where it lands, 0.2 s later, radius 8, 120% | A crackling blue target ring closes in; a forked bolt (with one gold fork) drops from the sky, flickering; a flash, an electric blue painted ring and dashed rim, a scorch mark, sparks and small arcs to the enemies caught in it |

**Gold aura:** every Legendary floats with a faint gold glint. At Tier IV the full aura turns on (gold haze from the mesh, star motes, a light). It builds with the slot's `LegendaryCharge` (server-set count toward the move), shimmers faster when the next attack is the move, and flares when it fires.

**Rules kept:** every move hit is a secondary hit (no crits, chains, knockback or other specials), so a move can never start another move. Movers stop at walls. At most 48 slashes/cards in flight and 256 scheduled hits per server; effects are skipped beyond 170 studs from the camera, and the camera kick is only for the player who made the move (off with the Screen shake setting). Effects use existing textures only (Slash, Star, Glow, Lightning, Ring, Scorch, Cracks, Dust).

**Tests:** `LegendaryMovesTests` (pure helpers and the catalog: exactly the 7 Legendaries, moves only at Tier IV, the user's counts) PASS, 99 checks, Edit-mode harness, 2026-10-02. Not run yet: any Studio Play test of the moves or their visuals.

## Effects that stayed on screen: cleanup hardening, October 10, 2026

Play-testers saw some weapon effects stay for the whole run after about wave 40. Commit e595ffb fixed the shared `VfxKit` scheduler (each effect retires once, cleanups are pcalled, 30 s cap). This pass fixes the effect modules around it. Nothing looks different.

**Rule 1: destroy your own parts first, then start follow-ups.** A cleanup that started a landing burst and then destroyed its parts lost those parts if the burst threw (the pcall stops the rest of the cleanup). Reordered: Legendary Katana/Excalibur slash, Pizza Cutter roll, Royal Flush cards, Pharaoh charge. `check_vfx_cleanup_order.py` checks every `K.animate`/`C.follow` cleanup for this (it flags exactly those four on the old code).

**Rule 2: register the cleanup before anything that can throw.** Legendary/Godly bursts register before building the emitter; the Legendary split rockets are built right before their `K.animate`; Mjolnir's bolt draws after its cleanup is registered; a Reaper wraith's fade registers before its smoke burst; a rocket explosion is tracked before its parts are cloned.

**Rule 3: no orphans.** A repeated id used to replace an entry and leave the old model with nothing pointing at it: wraiths (by key), Ray Gun bolts (a second `first`, or no projectile id at all), rockets and arc cards (by id) now remove the old one first.

**Rule 4: loops that own parts can't fail forever.** `SpecialWeaponVisuals.endFlight` ran the landing impact before removing the flight; an impact that threw left the thrown model up and failed again every frame, which also stopped the zones and puffs after it in the same loop. It now removes the flight, then runs the impact. Projectile-style impacts (Staff, Crystal Ball, Medusa) are pcalled before the head is released. Rockets also end after 30 s of flight (a zero speed never reached its range).

**Backstops:** transient parts outside VfxKit get a `Debris:AddItem` well past their normal end, so they go even if their render loop stops: thrown flights 12 s (normal end by 9 s), poison puffs, rocket models 35 s and smoke 4 s, rocket bursts 5 s (normal 1.2 s), bullet and old-explosion sprites 2 to 3 s, projectile-style heads 12 s (normal 8 s), arc cards 30 s, shirt shots 15 s, wraiths life + 5 s, Ray Gun bolts 14 s. Example: a Bowling Ball flight launched at 0 s is ended by its loop at 9 s; if that loop had stopped, Debris removes it at 12 s.

**Not touched:** the Molotov/fire-zone code (another pass is reworking it). Known gap there: a `Zone` model is parented before it is registered in `zones`, and zones have no Debris backstop.

**Tests:** `run_vfxkit_tests.py` 90 checks PASS (new case 7: a follow-up that throws after the cleanup destroyed its parts leaves nothing behind); `check_vfx_cleanup_order.py` 22 files, 95 effect calls, 0 problems; every touched file compiles with luau-compile. No Studio Play test was run for this pass.

## Molotov fire, October 10, 2026

Play-test: the Molotov's fire "looks weird" (seven neon balls flattened to discs, each with a Roblox `Fire` instance: realistic smoke-fire, not our style) and its zone was too small. Design sheet first (Claude Design, one pass): https://claude.ai/artifact/NBgiUUT7Ee3gDMfwWhMEA8 (top-down and 3/4 views, the burn-down as four frames, colours, budget). Gameplay numbers: [WEAPON_BALANCE.md](WEAPON_BALANCE.md#molotov-fire-rework-2026-10-10).

**What you see** (`ThrownVisuals.fireZone`, called by `SpecialWeaponVisuals` on the `Zone` packet; flat and painted, no meshes):

| Layer | Built from | Behaviour |
|---|---|---|
| Scorch | `ScorchMark` decal (uploaded, BossVfxAssets) | 2.5x the start radius, fades in over 0.15 s, out over the last 0.6 s |
| Fire pool | new painted `MolotovFirePool.png` decal (rim red, orange, yellow, pale core, flame-lick edge) | sized to the server's radius every frame (`SpecialMotion.zoneRadius`), so the red rim is the hit edge; until the PNG is uploaded, three flat Neon discs in the same bands |
| Flame tongues | `Flame_Flipbook4x4` (uploaded), one emitter, `FacingCameraWorldUp` billboards | spawned on the rim and inside: 2.6 x r + 0.12 x r² a second x ClientQuality effects (about 16 alive at the start on Full, 11 Balanced, 6 Low/Lean); 2.2 studs tall at 7.2, 1.8 at 3.6 |
| Embers | `Ember` sprite (uploaded), one emitter | 4 a second x quality |
| Landing | `VfxKit.ring` (amber dashed rim, 0.35 -> 1x the start radius in 0.38 s), a burst of tongues, plus the existing glass shards, pop and flash | only when the camera is within 160 studs |

Colours are the flame flipbook's own bands, measured from its pixels: #D33A22, #F7801F, #FFC93F, #FFE8A0; LightInfluence 0 on the particles so the sky fill doesn't shift them. The fire is a budgeted VfxKit effect (category `fireZone`, 24 x quality), stops spawning past 160 studs, and is 3-5 parts + 2 emitters each (max 4 per player). The fire's model is registered in `zones` and given a Debris backstop (life + 5 s) before it is built, and the build is pcalled (closes the gap noted in the cleanup pass above). Poison clouds are unchanged.

Texture source: `roguelite-planning/weapon-models/assets/14-molotovs/vfx/paint_molotov_vfx.py` (numpy, seeded) writes `textures/MolotovFirePool.png` (512², coloured RGBA). Not uploaded yet.

Not tested: anything in Studio or Play (look in daylight, particle sizes on the real camera, mobile frame time, the sound mix).

### Follow-up: soft, grounded fire (same day)

Play-test of the version above (synced at 33124c1): "fire effects are hella 2D, especially on the floor, and clips hella". The screenshot showed the pool as a hard-edged opaque cutout lying flat on uneven grass (terrain and grass poking through it, reading as a sticker), and the flame tongues as flat cards (`FacingCameraWorldUp`) slicing into the ground from the 3/4 camera.

Rebuilt `ThrownVisuals.fireZone` (server, radius curve and counts unchanged). Nothing in it is a flat shape of its own any more. Every sprite sits on its own ground raycast (players, enemies and effect folders excluded):

| Layer | Now |
|---|---|
| Pool | **Dropped.** `MolotovFirePool.png` (rbxassetid://121830714730465) is no longer drawn; its id stays in `FireTextures` for reference |
| Heat glow | Soft additive glow sprites (GodlySoftGlow, tinted orange to red, LightEmission 1) lying flat on ground hits (`VelocityPerpendicular`), 0.7-1 s each, re-spawned inside the current radius at (2 + 0.8 r) a second x quality, about 0.55 transparent at their brightest. The glow flickers and shrinks with the fire, and a bump under one blob only dims a soft edge |
| Scorch | 7 small ScorchMark decals (1.05-1.3 x start radius) instead of one 2.5x plate, each on its own ground hit and tilted to its normal, 45% transparent at most |
| Flames | Same flipbook and the same counts by quality, now `FacingCamera`, so a tongue never shows an edge. Each is lifted so its painted base sits 0.15 stud above its own ground hit, with ZOffset 1.2 toward the camera so slopes and grass can't slice it. Size varies ±18% per tongue, the squash wobbles as it burns, and a glow blob under the base softens where it meets the ground |
| Height | Embers rise 3-5 studs (6 a second x quality), plus a little grey smoke (SmokePuff flipbook, 1.6 a second x quality) starting 2-3 studs up |
| Light | One warm PointLight per fire (brightness about 1.1 with a flicker, range 1.8 r + 2, shrinking with the fire). At most 3 fires are lit at once and none on Low/Lean (ClientQuality `lights` 0) |

The landing ring sits 0.2 stud up (was 0.08) and is drawn after the fire's cleanup is registered. Cost per fire: 8 parts (7 scorch + 1 anchor) and 4 emitters, plus about 40 short raycasts a second at Full on the camera's side only. Still a VfxKit `fireZone` effect (budget 24 x quality), skipped past 160 studs.

**Look at in Play:** (1) on bumpy grass and a slope, no flat edge or sticker shape should show and no tongue should be cut by the ground; (2) the glow reads as heat, not paint (if it is too faint or too strong, `glow.Transparency` 0.55 is the lever); (3) the tongues' bases from the normal 3/4 camera and from straight above; (4) the shrink is still easy to read from the ring of tongues; (5) with 4 fires down, the light count and frame time on Balanced and Low.

**Tests:** `run_fire_zone_tests.py` 453 PASS, `run_vfxkit_tests.py` 91 PASS, `check_vfx_cleanup_order.py` 22 files / 99 calls / 0 problems, luau-compile OK. Not run in Studio or Play.
