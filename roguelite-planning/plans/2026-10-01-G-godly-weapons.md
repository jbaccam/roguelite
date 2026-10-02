# Plan G: Godly weapons in the game (RARITY_GODLY_ARMOR.md step 4)

Status: the design was approved by the user on 2026-10-01. They answered the four questions and then said "make the VFX SICK AF on them and properly animated". Models and icons are done (see "Done").

## Decisions (user, 2026-10-01)

| Question | Decision |
|---|---|
| Where Godlies show up | **Live everywhere** once they're in: chests roll them, bundles unlock, owners see them in the Armory. |
| Scythe ghost rate | **1 in 3 kills**, **max 4** at once (6 at Tier IV), 6 s each. |
| Ghost look | **Custom crimson wraith**, modelled in Blender, low poly: hooded skull, glowing eyes, claws, ragged tail. Small from normal mobs, big from Heavy mobs. |
| Strength | "Strong because they're god tier, but not OP." Power 160 (RARITY_GODLY_ARMOR.md section 4), one per run. |
| Mjolnir | Attacks a little faster: cooldown 2.4 s → 2.0 s. |

## Done (2026-10-01)

- Models: `WeaponTemplates.36`–`41` are installed in Studio (`weapon-models/godly/studio-import/`).
- Icons: `ui/assets/weapons/36.png`–`41.png`, uploaded, in `WeaponInventoryUI.Icons`. They are the user's Astra renders.

## Numbers

Rarity power isn't in code yet (step 2), so the 160 is written directly into each Godly's own numbers.
- Target: about **24 damage per second on one enemy at Tier I**. For comparison: Frying Pan 15, Katana 19, Mjolnir 9 (11 after this change).
- The specials add power in crowds.
- Damage and cooldown by tier follow the catalog defaults: damage ×1.5 per tier, cooldown ×{1, .95, .9, .84}.

| Id | Weapon | Kind | Damage T1–T4 | Cooldown | Range | Special | Tier IV bump |
|---|---|---|---|---|---|---|---|
| 36 | Reaper's Scythe | Melee | 30/45/68/102 | 1.25 | 10 | **Reap**: a full 360° spin around the player. 1 in 3 of its kills raises a wraith. | 6 wraiths |
| 37 | Poseidon's Trident | Melee + throw | 34/51/77/115 | 1.5 | 9 (throw 36) | A throw lands with a **tidal wave**: a ring that grows to radius 10 over 0.5 s, does 60% damage and knocks enemies outward (push speed 32, bosses ×0.2). | radius 14 |
| 38 | Storm Bow | Ranged | 14/21/32/47 per arrow | 1.2 | 50 | The arrow **splits into 5** that rain onto 5 different enemies within 10 studs of the target. A lone enemy takes at most 2. | 7 arrows |
| 39 | Shadow Daggers | Melee | 16/24/36/54 per hit | 1.3 | 10 (chain hop 12) | The daggers **chain through up to 5 enemies**. A lone enemy takes both blades (2 hits). | chain of 7 |
| 40 | Vampire Blade | Melee | 32/48/72/108 | 1.3 | 9 | Heals **8% of damage dealt**. Each kill sends a wisp that heals 2 HP. All of it counts toward the normal `LifeStealCap` (10 HP/s). | 12%, cap +5 HP/s |
| 41 | Ray Gun | Ranged | 22/33/50/74 | 0.9 | 48 | A kill **disintegrates** the enemy: a 6-stud burst for 50% damage. Burst kills don't burst. | radius 9, 75% |

### Wraith (Scythe)

- **Spawning:**
  - A non-secondary Scythe kill has a 1 in 3 chance to raise one at the corpse. The roll is server-side.
  - The cap is 4 alive per player (6 at Tier IV). At the cap, the oldest wraith fades and the new one takes its place.
- **Lifetime:** 6 s. Every wraith fades when its owner dies or the run's enemies turn off.
- **Behaviour:**
  - It flies at 26 studs/s to the nearest living enemy within 40 studs.
  - Within 3 studs, it claws once per second for 25% of the scythe's current hit, as a secondary hit (no crit, chain or status).
  - Its kills never raise more wraiths.
- **Heavy mobs** raise a big wraith: 1.5× size, 2× claw damage.
- **Budget:** at most 24 wraiths per server, so the cost stays bounded.
- **Rendering:** the server simulates; clients render. The server sends spawn, target, claw and end events, and the client flies the model toward the enemy it was told to chase.

### Rules that keep it fair

- One Godly per player per run. The server enforces this on run setup and on every grant.
- Godlies are never in the run shop, level-up offers, drops or daily deals.
- Specials never chain: a wraith kill, burst kill, wave hit or wisp never triggers another special.
- Every special has a cap: wraiths, arrows, chain length, burst radius, heal per second.

## Animation and VFX

Every Godly gets the following:
- **Idle aura:**
  - an attachment-based ParticleEmitter haze in its colour;
  - a PointLight on the glow core;
  - slow embers or motes;
  - a soft breathing pulse on the Neon parts (Transparency).
- **Swing trails:** a thick two-layer ribbon (a hot core plus a wide coloured outer) in the weapon's colour.

The table lists each weapon's signature motion and VFX.

| Weapon | Motion | Signature VFX |
|---|---|---|
| Scythe | Reap: winds up behind, spins 360° at full reach, recovers | A crimson spin ring on the ground, skull motes, and a soul-smoke puff on a raise. Each wraith rises out of smoke, flies with a ragged trail and claws with a red slash. |
| Trident | Thrust up close; spinning throw at range, flies back | A water spray trail on the throw. On landing: an expanding wave ring, a splash flipbook, bubbles and foam spray. |
| Storm Bow | Recoil pull. The arrow arcs up, then splits | Lightning bolt Beams from the split point to each target, a thunder flash, and a forked impact star. |
| Shadow Daggers | Both blades dash along the chain and return | Crimson afterimage Trails, a slash streak per hit, and a short screen-space-free red flash. |
| Vampire Blade | Big alternating horizontal and diagonal sweeps | A blood trail, wisps that curve back into the player, a heal pulse, and blood drips at idle. |
| Ray Gun | Recoil kick; green bolt with a spiral trail | A muzzle ring. A kill shrinks the enemy into green pixel cubes, plus a burst ring. |

- **Textures:** reuse `BossVfxAssets` (ShockwaveRing, ImpactStar, WaterSplash/SmokePuff flipbooks, Bubble, CurseOrb, Ember). New painted textures go in `weapon-models/godly/vfx/`: Lightning strip, SoulWisp, SlashArc, Pixel, SkullMote. Uploaded via Studio MCP.
- **Other players' Godlies:** effects are drawn only within 140 studs (`VfxKit.near`), with no idle particles beyond 60 studs.
- **Sound:** our punchy, cartoony kit. Library ids with pitch shifts, recorded in ASSETS.md.

## Code (where it goes)

| Piece | Change |
|---|---|
| `WeaponCatalog` | Ids 36–41: profile rows, `godly=true`, `home='Godly'`, `rarity='Godly'`. `C.isGodly(id)`. Mjolnir cooldown 2.0. |
| `CharacterStats.weapon` | Godly fields per tier: `ghostCap`, `waveRadius`, `arrowCount`, `chainCount`, `leechPercent`, `burstRadius`/`burstFactor`. |
| `WeaponMotion` | `Reap` style (36). The Trident alternates Thrust and Horizontal. The Vampire Blade alternates Horizontal and Diagonal. The Daggers have no box sampling (`M.ScriptedMelee`). |
| `SpecialMotion` | A '37' profile: returns, spins, no arc. |
| `GodlyWeapons` (new, server, **sandboxed**) | Wraith simulation, tidal wave, arrow rain, dagger chain, wisps, disintegrate burst. One `GodlyFX` RemoteEvent. |
| `CombatEffectsService` | `E.onHit` and `E.onKill` hooks, which GodlyWeapons sets. |
| `CharacterService` | `leechFlat(player, hp)`: healing under the same LifeStealCap. |
| `RogueliteCombat.server` | Routes Godly attacks; skips box sampling for scripted melee. |
| `GodlyVisuals` (new, client) | Auras, trails, `GodlyFX` effects, wraith rendering. |
| `RogueliteCombat.client` | Calls `GodlyVisuals.attach` and `GodlyVisuals.step` next to `Swing`. |
| Release | `ChestConfig.RARITY.Godly`; ShopCatalog, level-up and daily deals skip Godlies; Armory and RunSetup show owned Godlies under every class; `RunSetupRules` and the server enforce one per run. |
| Wraith model | `roguelite-planning/blender-godly-wraith/` (kit convention). Parts: Body, ArmL, ArmR, Glow, so claws animate without a rig. Imported like the weapons (one Import, then an installer). |

## Build notes (2026-10-01)

- **The Reap's hits.** The Reap hits every enemy in reach as the blade's heading passes it (`WeaponMotion.reapFractionOf`), not by box sampling. A plain box sweep at the nearest target's distance would miss the inner and outer parts of the disc.
- **Godly sounds.** They are in `RogueliteSounds`, which is unsandboxed: weapon rows plus a `GodlyFX` listener.
- **The chest odds panel.** It merges the six Godly weapons into one crimson "?" tile, so unowned Godlies stay secret. The Godly reveal gets a longer beat, a stronger flash and a harder shake than Legendary.
- **Studio sync.** `combat/SyncGodlyRuntime.luau` writes all or nothing, guarded by HEAD.
  - `RunSetupRules` was patched surgically in Studio. Its Studio copy predated another session's committed map-scaling change (1039ad9), so that change is not pushed by this sync.
- **Tests.**
  - `GodlyWeaponsTests`: 56 checks pass in Edit.
  - `ChestConfigTests` passes with 20,000 rolls.
  - An Edit-mode harness called every `GodlyVisuals` path (attach, step in all five styles, every GodlyFX event, the Ray Gun shot and dissolve, the Trident flight) with no errors, and every transient part cleaned itself up.
- **The wraith.** It uses a temporary Neon shade until `RogueliteCombat.GodlyAssets.Wraith` (from `blender-godly-wraith/`) is installed.

## Testing

**Edit mode (no Play; the user does the play-testing):**
- `WeaponCatalog`, `CharacterStats` and `ChestConfig` tests:
  - ids 36–41 exist, are Godly, and are not in any shop pool;
  - the T1 single-target DPS for each is within 22–26.
- Pure-function tests in GodlyWeapons:
  - the wraith cap and its oldest-first replacement;
  - arrow target picking (distinct targets; at most 2 on a lone enemy);
  - chain picking;
  - wave falloff;
  - a burst never chains.
- Every changed script parses (stylua).
- Studio Source matches the repo after the push.

**Play (the user):** each Godly from the admin panel against a pack, and the VFX at the game camera. Also:
- the chest Godly reveal;
- one-per-run;
- other players' effects (needs 2 real clients; not claimed).
