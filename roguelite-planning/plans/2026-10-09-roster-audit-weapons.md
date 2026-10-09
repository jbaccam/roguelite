# Roster audit: weapons, classes, starters (source facts for the Chef redesign)

Date: 2026-10-09. Read-only audit of `roguelite-planning/studio-prototype/`. Paths below are relative to that folder unless they start with `plans/` or `..`. Line numbers are from the working tree on this date. Nothing was changed in code, Studio, or git.

Redesign being prepared for (user decision): Thrower removed, Chef added (Pan, Spatula, Steak, Egg, Molotov, new Pizza Cutter `'42'`). Every ordinary weapon gets one starter class. Godlies 36-41 stay any-class. Weapon TYPES become a separate tag/set system. ClassFit and the per-class 2/4 bonuses are replaced by a per-weapon specialty bonus. Elemental and Utility flags are authored per weapon.

---

## 0. Findings that change the plan

1. **Three weapons lose Utility Power if the flag stays derived.** `d.utility=C.inClass(d,'Handyman')` (`combat/WeaponCatalog.luau:267`). Today Spatula `05`, Rocket `11` and Cinder Block `20` are utility only because Handyman is their second class (`:197-199`). Under the new roster they would lose Utility Power scaling and stop counting for the `utilityKills` quest (`combat/RogueliteMeta.server.luau:265`). Elemental is safe: Fart Gun, Molotov, Duck, Storm Bow and Ray Gun are hard-coded (`WeaponCatalog.luau:266`), and every other elemental weapon stays Mage.
2. **Id `'42'` hits three numeric rules.**
   - `n>=36` makes a weapon Godly (`WeaponCatalog.luau:254`).
   - `n>=30` makes its home Mage (`:245`).
   - `InstallLoadout` asserts exactly 36 templates, then destroys the folder (`combat/InstallLoadout.luau:44-45`). Re-running it would wipe the Godly templates 36-41.
3. **The tutorial launch breaks if Pan leaves Brawler.** The tutorial is Brawler + Frying Pan (`combat/TutorialConfig.luau:7`). It launches through `Match.launch` (`combat/TutorialDirector.server.luau:40`), which runs `validLoadout` (`lobby/MatchService.luau:114`). With Pan as a Chef weapon that check refuses the tutorial. The tutorial also seeds two Pan copies (`TutorialConfig.luau:33-35`) and guides the Pan upgrade (`ui/TutorialGuide.client.luau:280-287`).
4. **The ClassThrower receipt must stay mapped.**
   - `ProcessReceipt` returns `NotProcessedYet` when `Config.byProductId` finds no key (`combat/RogueliteMeta.server.luau:1098-1099`).
   - Deleting `ClassThrower` (`combat/MonetizationConfig.luau:57`) would leave late or retried receipts stuck forever.
   - Granting `{class='Thrower'}` after the change would write a dead class (`combat/ProfileService.luau:271`).
5. **Some card text and offers describe stats that do nothing.**
   - Duck has trait `'bounce'` (`WeaponCatalog.luau:35`), and Washer has `'pierce'` (`:47`).
   - Their cards therefore say "Bounces between enemies." / "Shots pierce through enemies." (`WeaponCatalog.luau:184,214`; `ui/ArmoryUI.luau:204`).
   - Neither spray nor stream reads bounce or pierce (`combat/SpecialWeapons.luau:41-58`; `combat/UtilityWeapons.luau:128-189`).
   - Bowling Ball reports Pierce and Bounce as usable (`combat/CharacterStats.luau:219`), but its impact code returns before either is used (`SpecialWeapons.luau:105`). The shop can offer Pierce/Bounce items for a ball they don't help.
6. **Mjolnir and Trident throws scale with Ranged damage, not Melee.** The server swaps the multiplier when it throws: `d.damage/mult(MeleeDamage)*mult(RangedDamage)` (`combat/RogueliteCombat.server.luau:446-448`).
7. **Legendary Tier IV moves scale with Area Size, but the stat check misses most of them.** Slash, Beam, Shock, Split, Thunder and Strike all scale with Area Size (`combat/LegendaryMoves.luau:156,166,203,245,255`). `usesStat('AreaSize')` only counts blast, zone, lightning and Godly specials (`CharacterStats.luau:209-214`). So "works with" lists and shop filtering skip Katana, Cards, Bowling Ball, Wrecking Ball and Excalibur for Area items.
8. **Dead code and stale comments.**
   - `S.classFitText` has no callers (`CharacterStats.luau:127`).
   - The comment "LastContact only drives the Frying Pan's wobble" sits over code for Steak `'16'` (`RogueliteCombat.server.luau:286-287`; client `combat/RogueliteCombat.client.luau:178-181`).
   - The dash comments say "class or starter" (`RogueliteCombat.client.luau:420,690`; `RogueliteMeta.server.luau:716-717`), but the code is class-only.

---

## 1. Weapon matrix (ids 00-41)

### Legend

- **Classes now**: `home` first, then `AlsoClasses`. `home` comes from the id-range formula (`WeaponCatalog.luau:245`) plus `HOME_MOVED` (`:222,249`); `AlsoClasses` is `:197-199`. The list is confirmed by `combat/WeaponClassTagTests.luau:3-16`.
- **Kind**: `ranged` set (`:4`), Blast for 11/14/33 and Spread for 09 (`:226`), forced Ranged for 17/21/23 (`:252`).
- **Rarity**: C/R/E/L/G, from `:70-76`.
- **Families**: every weapon takes Damage. Then `kind=='Melee'` → MeleeDamage, otherwise RangedDamage (Blast and Spread included). Elemental if `elemental`, Utility if `utility`, Explosion if `kind=='Blast'`. Source: `CharacterStats.luau:231-234`, `:207`. Codes: M=Melee, R=Ranged, E=Elemental, U=Utility, X=Explosion.
- **PC / Pi / Bo** (extra projectiles / pierce / bounce): from `S.usesStat` (`CharacterStats.luau:203-223`), cross-checked against each launcher.
- **Area**: Area Size counts in `usesStat` (blast radius, thrown zone, lightning, Godly area special: `:209-214`).
- **E/U**: the current `elemental` / `utility` flags (`:266-267`).

### Attack implementations

| Code | What happens | Source |
|---|---|---|
| SWING | Server samples `WeaponMotion.pose` 120 times a second and box-queries the template bounds | `RogueliteCombat.server.luau:491-533` |
| CHAIN | SWING, but hit boxes come from the skinned chain rig | `:10,505-508` |
| GLOVES | Alternating fist boxes, plus a second target within 8 studs | `:436-439,509-518` |
| REAP | Full circle, judged by heading fraction | `:473-490` |
| BULLET | `StatProjectiles` swept straight shot | `RogueliteCombat.server.luau:235`; `combat/StatProjectiles.luau:115-133` |
| ROCKET | `RocketProjectile`, blast falloff `1-.65*d/r` | `RogueliteCombat.server.luau:234`; `combat/RocketProjectile.luau:20-22` |
| THROW | `SpecialWeapons` modeled flight on a `SpecialMotion.profiles` arc | `SpecialWeapons.luau:189-235`; `combat/SpecialMotion.luau:9-20` |
| RET | Returning throw: one copy, `busy` until it is back | `SpecialWeapons.luau:83-91,186,208` |
| ZONE | Throw that leaves a ground zone ticking at 0.4× damage every 0.4 s as secondary hits (3 per owner+weapon) | `SpecialWeapons.luau:59-71,165-178` |
| ROLL | Bowling lane: floor-following, ×0.7 per contact (min 0.2), 24 damaging contacts | `:102-105,143-147,222-230` |
| CARDS | `ArcProjectiles` curved homing volley, each card `damage/3`, up to 8 redirects | `combat/ArcProjectiles.luau:34-44,84-109` |
| MORTAR | `ArcProjectiles` committed landing point, full-damage blast | `:14-21,95-98` |
| SPRAY | Duck burst: 3 pulses, cone `dot>.84`, `damage×damageScale` | `SpecialWeapons.luau:41-58,192-204`; `SpecialMotion.luau:4-8` |
| STREAM | Vacuum or Washer cone, tick 0.12 s | `UtilityWeapons.luau:128-199` |
| HYBRID | Swings in reach; beyond reach it throws (RET) as `kind='Ranged'` | `RogueliteCombat.server.luau:446-449` |
| RAIN / DCHAIN | Godly scripted attacks | `combat/GodlyWeapons.luau:155-173,176-191`; `RogueliteCombat.server.luau:468` |

### Rules that apply to every weapon (not repeated per row)

- **Attack Range** scales range and target range (`CharacterStats.luau:243-244`).
- **Attack Speed and Cooldown Reduction** scale cooldown, with a floor of 0.18 s melee and 0.08 s other (`:238-239`). Gunner's +10% applies to non-melee only (`:78,238`).
- **Crit** rolls on every "own" hit (`combat/CombatEffectsService.luau:94,103-109`). These don't crit: zone ticks, status ticks, chain bolts, Legendary and Godly secondary hits, chicken pecks (`combat/EggChickens.luau:4,127`).
- **Burn, poison, slow and chain** roll on own hits (`CombatEffectsService.luau:176-193`). Status tick damage uses `Damage×Elemental` for every weapon, not only elemental ones (`:176`).
- **Knockback** applies to own, non-secondary hits (`:171-175`). Stream ticks are sent as secondary (`UtilityWeapons.luau:162`), so the Vacuum and Washer never knock back. Native knockback: Spatula 14, Shovel 20, Cinder Block 16 (`WeaponCatalog.luau:259`).

### Matrix

| id | Name | Rar | Classes now | New starter | Kind | Attack | Families | PC/Pi/Bo | Area | E/U | Tier IV special |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 00 | Glock | C | Gunner | Gunner | Ranged | BULLET (straight gun) | R | PC Pi — | — | –/– | — |
| 01 | Frying Pan | C | Brawler | Chef | Melee | SWING, Downward set | M | — | — | –/– | — |
| 02 | Nunchucks | R | Brawler | Brawler | Melee | CHAIN, FigureEight/Spin (`combat/WeaponMotion.luau:237`), `motionRate` 1.35 | M | — | — | –/– | — |
| 03 | Katana | L | Brawler | Brawler | Melee | SWING, Diagonal/Thrust/Horizontal (`:238-241`) | M | — | — | –/– | Flying slash every 3rd swing, 75% (`WeaponCatalog.luau:117`) |
| 04 | Kusarigama | E | Juggler, Thrower | Brawler | Melee | CHAIN | M | — | — | –/– | — |
| 05 | Spatula | C | Juggler, Handyman | Chef | Melee | SWING, Downward set, KB 14 | M U | — | — | –/**U** | — |
| 06 | Baseball Bat | R | Brawler | Brawler | Melee | SWING, Downward set | M | — | — | –/– | — |
| 07 | Draco | R | Gunner | Gunner | Ranged | BULLET (straight gun) | R | PC Pi — | — | –/– | — |
| 08 | Fart Gun | C | Gunner, Mage | Gunner | Ranged | ZONE: poison cloud, native poison 100% (`:268`) | R E | PC — — | yes | E/– | — |
| 09 | Shotgun | R | Gunner | Gunner | Spread | BULLET, 4+tier pellets 5° apart (`CharacterStats.luau:246`; server `:232`) | R | PC Pi — | — | –/– | — |
| 10 | T-Shirt Cannon | E | Gunner, Thrower | Gunner | Ranged | BULLET, native pierce ⌊t/2⌋, marks DesignerShirt (`CombatEffectsService.luau:101`) | R | PC Pi — | — | –/– | — |
| 11 | Rocket Launcher | L | Gunner, Handyman | Gunner | Blast | ROCKET, radius 6 | R U X | PC — — | yes | –/**U** | Split every 4th: 3 minis at 40% (`WeaponCatalog.luau:118`) |
| 12 | Boomerang | C | Thrower, Juggler | Juggler | Ranged | RET, `flat` spin, native bounce min(4, t+1) | R | — Pi Bo | — | –/– | — |
| 13 | Kunai | R | Thrower | Juggler | Ranged | THROW, `point`, native pierce ⌊t/2⌋ | R | PC Pi Bo | — | –/– | — |
| 14 | Molotov | E | Thrower, Mage | Chef | Blast | ZONE: fire, native burn 100%; ExplosionDamage applies to impact and ticks | R E X | PC — — | yes | E/– | — |
| 15 | Egg | C | Thrower, Juggler | Chef | Ranged | THROW, tumble, 3-egg reserve; landing hatches chickens (`SpecialWeapons.luau:95`) | R | PC Pi Bo | — | –/– | — |
| 16 | Steak | R | Thrower | Chef | Melee | SWING, Slap/Diagonal, hit wobble | M | — | — | –/– | — |
| 17 | Rubber Duck | C | Juggler, Thrower | Juggler | Ranged | **SPRAY**: 3 pulses 0.12 s apart, cycle ≥ 0.78 s, length min(range, 14×AR), direction fixed per burst; `nativeBounce` is computed but unused | R E | none (`CharacterStats.luau:218`) | — | E/– | — |
| 18 | Deck of Cards | L | Thrower, Juggler | Juggler | Ranged | CARDS: 3 (4 at T3+), each `dmg/3` | R | PC Pi Bo | — | –/– | Royal Flush every 5th throw (`WeaponCatalog.luau:119`) |
| 19 | Boxing Gloves | C | Brawler, Juggler | Brawler | Melee | GLOVES, `motionRate` 2.7, own tier table (`:37`) | M | — | — | –/– | — |
| 20 | Cinder Block | E | Brawler, Handyman | Brawler | Melee | SWING, D/H/D/Downward cycle, KB 16 | M U | — | — | –/**U** | — |
| 21 | Yo-Yo | R | Juggler | Juggler | Ranged | BULLET with yo-yo string visual (`combat/ProjectileStyleVisuals.luau:142-174`), native bounce t−1 | R | PC Pi Bo | — | –/– | — |
| 22 | Bowling Ball | L | Juggler, Thrower | Juggler | Ranged | ROLL; `nativePierce` and item Pierce/Bounce have no effect (`SpecialWeapons.luau:105`) | R | effective: PC only | — | –/– | STRIKE! at 5+ hits (`WeaponCatalog.luau:120`) |
| 23 | Bowling Pin | R | Juggler, Brawler | Juggler | Ranged | THROW, tumble, 3-pin reserve | R | PC Pi Bo | — | –/– | — |
| 24 | Nail Gun | C | Handyman, Gunner | Handyman | Ranged | BULLET (straight gun), native pierce ⌊t/2⌋ | R U | PC Pi — | — | –/U | — |
| 25 | Wrecking Ball | L | Handyman | Handyman | Melee | CHAIN | M U | — | — | –/U | Shockwave when a swing connects, 40% (`:121`) |
| 26 | Shovel | C | Handyman, Brawler | Handyman | Melee | SWING, Downward/Diagonal, KB 20 | M U | — | — | –/U | — |
| 27 | Paint Roller | R | Handyman | Handyman | Melee | SWING, Downward set; native slow 30% for 2 s (`:66`) | M U | — | — | –/U | — |
| 28 | Vacuum Cleaner | E | Handyman | Handyman | Ranged | **STREAM, continuous**: wide cone (0.48×length), tick 0.12 s × `.12/cd` share, pull and 35% slow, no knockback | R U | none | — | –/U | — |
| 29 | Power Washer | R | Handyman | Handyman | Ranged | **STREAM, pulsed**: narrow cone (0.6), pressure 0.8 full / 0.2 trickle / 0.4 refill (`UtilityMotion.luau:45-56`), × `WashDamageScale`; server re-aims each tick at the live target (`UtilityWeapons.luau:134-138`); trait `pierce` unused | R U | none | — | –/U | — |
| 30 | Magic Staff | C | Mage | Mage | Ranged | BULLET (orb) | R E | PC Pi Bo | — | E/– | — |
| 31 | Mjolnir | L | Mage, Thrower | Mage | Melee | HYBRID: Downward-set swing; beyond reach a RET `rock` throw; lightning (`:268`) | M E (swing) / R E (throw) | — Pi Bo (thrown only) | yes | E/– | Lightning strike every 4th throw, 120% (`:123`) |
| 32 | Excalibur | L | Mage, Brawler | Mage | Melee | SWING | M E | — | — | E/– | Beam slash every swing, 45% (`:122`) |
| 33 | Pandora's Box | R | Mage | Mage | Blast | MORTAR, radius 7, lid bone | R E X | PC — — | yes | E/– | — |
| 34 | Medusa's Head | R | Mage | Mage | Ranged | BULLET, 2 shots at T2+ (`CharacterStats.luau:246`), native slow 35% for 2 s | R E | PC Pi Bo | — | E/– | — |
| 35 | Crystal Ball | C | Mage | Mage | Ranged | BULLET, native bounce t−1, lightning | R E | PC Pi Bo | yes | E/– | — |
| 36 | Reaper's Scythe | G | — (Godly) | any | Melee | REAP; kills raise wraiths | M | — | — | –/– | Godly special every tier; Tier IV wraith cap 6 (`WeaponCatalog.luau:97`) |
| 37 | Poseidon's Trident | G | — | any | Melee | HYBRID: Thrust/Horizontal; beyond reach a RET `spear` throw plus tidal wave (`GodlyWeapons.luau:133-152`) | M / R | — Pi Bo (thrown only) | yes | –/– | Wave 14 at Tier IV |
| 38 | Storm Bow | G | — | any | Ranged | RAIN on n targets, +0-2 from PC (`GodlyWeapons.luau:160`) | R E | PC only | yes | E/– | 7 arrows at Tier IV |
| 39 | Shadow Daggers | G | — | any | Melee | DCHAIN, scripted, no swing box (`WeaponCatalog.luau:257`) | M | — | yes | –/– | Chain 7 at Tier IV |
| 40 | Vampire Blade | G | — | any | Melee | SWING, Diagonal/Horizontal; heals (`GodlyWeapons.luau:194-198`) | M | — | — | –/– | 12% leech and higher heal cap at Tier IV |
| 41 | Ray Gun | G | — | any | Ranged | BULLET (straight gun) plus splash on every impact (`StatProjectiles.luau:45-57`) | R E | PC Pi — | yes | E/– | Burst radius 9 at Tier IV |

### Notes on the matrix

- **Melee styles** come from `WeaponMotion.MeleeStyles`, `DownwardWeapons` and `chooseStyle` (`WeaponMotion.luau:17-18,227-249`). Downward strokes get ×1.25 reach (`:79-82`).
- **Tiers** multiply damage by 1.4 per tier, or by a per-id growth (`WeaponCatalog.luau:90,93`). Cooldown goes ×{1, .9, .8, .7}. Only the 7 Legendaries listed have a Tier IV move (`:116-126`). Godly specials run at every tier.
- **Native pierce and bounce**: `trait=='pierce'` gives ⌊tier/2⌋; Bowling Ball gets 3+⌊tier/3⌋. Boomerang bounce is min(4, tier+1); other `bounce` traits give tier−1 (`CharacterStats.luau:247-249`).
- **Duck pacing**: a busy burst blocks the next attack (`SpecialWeapons.luau:183-188`). Damage per pulse is `cycle/(3×cd)`, so nominal DPS stays `damage/cooldown` (`SpecialMotion.luau:4-8`).
- **Streams**: the server keeps a stream alive for min(1.5, cd+0.12) s after each launch (`UtilityWeapons.luau:191-198`). The Washer's falling-water look is client-only. Server damage is the instant cone above.

---

## 2. Damage pipeline (in order)

| # | Step | Formula | Source |
|---|---|---|---|
| 1 | Authored base | `profiles[i]={damage,cooldown,range,...}` | `combat/WeaponCatalog.luau:17-61` |
| 2 | Rarity power | `damage=floor(authored×RarityPower)`; cooldown shortened by what rounding took (Common 1, Rare 1.05, Epic 1.1, Legendary 1.2) | `:84,232-233` |
| 3 | Tier | `tierDamage[t]=floor(damage×growth^(t-1)+.5)`, cooldown ×`TierCooldown[t]` | `:90,93,234-239` |
| 4 | Stat resolve | `value = base + class buffs + gained(two/four set bonus + item, level-up, skill, armor and pet flat) × (1+percent)`; set count = equipped weapons `inClass(class)`; Handyman `gain` ×1.25 Utility, ×0.5 Damage; GearPower comes from starter tier + armor + pet | `combat/CharacterStats.luau:170-181,165-169`; `combat/CharacterService.luau:119-153` |
| 5 | General damage | `×mult(Damage)` | `CharacterStats.luau:231` |
| 6 | Family | `×mult(MeleeDamage)` if Melee, else `×mult(RangedDamage)` | `:231` |
| 7 | Elemental / Utility / Explosion | `×mult(Elemental)` if flagged, `×mult(UtilityPower)` if flagged, `×mult(ExplosionDamage)` if Blast | `:232-234` |
| 8 | Class fit | `×mult(classFitPercent)`: +15 own class, 0/−5/−10/−15 matrix, best of the weapon's classes, Godly 0 | `:97-120,235-236` |
| 9 | Hybrid throw | Mjolnir and Trident: `÷mult(Melee)×mult(Ranged)` | `RogueliteCombat.server.luau:446-448` |
| 10 | Launcher share | cards ÷3; pierce ×0.7 each; bounce ×0.65 (throws) or ×0.6 (bullets, cards); ball ×0.7 per contact; rocket falloff; Duck `damageScale`; stream `.12/cd×pressure×WashDamageScale`; zone ×0.4; Legendary and Godly factors | `ArcProjectiles.luau:59,70,90`; `SpecialWeapons.luau:54,105,109,114,175`; `StatProjectiles.luau:93,105`; `RocketProjectile.luau:21`; `UtilityWeapons.luau:162` |
| 11 | Crit (own hits) | `×CritDamage/100` at `CritChance`; Ninja dodge-crit is guaranteed | `combat/CombatEffectsService.luau:103-109` |
| 12 | Gear power | `×(1+0.12×(GearPower−1))` on every hit, including status and secondary | `:111`; `CharacterStats.luau:260-262` |
| 13 | Boss / elite | `×mult(BossDamage)` | `CombatEffectsService.luau:112` |
| 14 | Pet mark | `×(1+mark/100)` | `:114-115` |
| 15 | Procs | Burn 6/s × `Damage×Elemental×BurnDamage`; poison 3/s per stack; slow; chain lightning 40% × `ChainDamage` every `ChainEvery` hits | `:176-193` |

Cooldown: `base.cooldown × tierCooldown / (mult(AttackSpeed) × Gunner ranged 1.1) × (1−CDR)`, floored (`CharacterStats.luau:238-239`). The Brawler's class "buffs" are stats inside step 4, for example `MeleeDamage=20, RangedDamage=-15` (`:77`).

### Worked example: Brawler, Tier I, no items, GearPower 1, one weapon equipped (set count ≤1, so no two/four bonus)

| | Katana `03` | Glock `00` |
|---|---|---|
| Catalog base | Legendary: 18×1.2=21.6 → **21** dmg; cd .95×21/21.6 = **.924** | Common: **12** dmg, **.82** cd |
| ×Damage (0) | 21 | 12 |
| ×family | Melee +20 → ×1.20 = 25.2 | Ranged −15 → ×0.85 = 10.2 |
| ×class fit | Brawler home +15 → ×1.15 = **28.98** | Brawler vs Gunner −15 → ×0.85 = **8.67** |
| Cooldown | .924 s (no ranged speed for Brawler) | .82 s |
| Per hit / crit hit | 28.98 / 43.47 (5% at ×1.5) | 8.67 / 13.0 |
| DPS (no crit / expected) | 31.4 / 32.1 | 10.6 / 10.8 |

So the Katana does about **3.0×** the Glock's DPS for a Brawler. For reference, a Gunner's Glock does 12×1.2×1.15 = 16.56 per hit at .82/1.1 = .745 s, about 22.2 DPS.

The Glock's −28% comes from two places: the class drawback (RangedDamage −15) and class fit (−15). This is the double penalty described at `CharacterStats.luau:95-96`. Removing ClassFit removes only the second one.

---

## 3. Class-membership consumers (implementation checklist)

Grep covered: `home`, `classes`, `AlsoClasses`, `inClass`, `classNames`, `tags`, `Signature`, `ClassOrder`, `ClassFit`, `classFit`, `classFitText`, `build`, `two`, `four`, `HOME_MOVED`, `homeWeapons`/`classWeapons`, `AffinityCount`, `Classes`, the class-name strings, and the `elemental`/`utility` flags. It ran over every `.luau` and `.py` file under `studio-prototype/`.

**False positives excluded:** the `home`/`build` fields in `combat/bosses/*`, `trailer/*`, `ProjectileStyleVisuals` (yo-yo `s.home`), `GodlyVisuals:444`, `SkillTreeUI`, `CleanupPlace`, `ChickenTemplate.build` and `EnemyProjectileVisuals.build`; the `two`/`four` locals in `LevelUpCatalog:42` and `TutorialTests:33`; `ArmorSets.two/four` (armor sets, not classes); and "Flamethrower" (`ui/WeaponShowcaseCatalog.luau:21`).

### Data definitions

| File:line | What it does | Must change |
|---|---|---|
| `combat/WeaponCatalog.luau:3,4,17-61,70-76` | Names, ranged set, profiles, rarity lists | Append `'Pizza Cutter'` (`'42'`): profile, rarity list, not ranged |
| `WeaponCatalog.luau:190-199` | `AlsoClasses` | Delete; replace with a per-id `Starter` map (37 ordinary entries) |
| `:200-204` | `inClass(w,class)` (any listed class) | Becomes `w.starter==class` (or rename), with Godly still false |
| `:205-210` | `classNames` | One name; callers below show starter class plus types |
| `:211-221` | `describe`: "Home weapon of the X class(es)." | New wording (specialty plus types); drop misleading Duck/Washer traits |
| `:222,245,249-250` | `HOME_MOVED`, id-range home formula, `d.classes` | Replace with authored map; remove the `n>=30` Mage rule |
| `:254` | `n>=36` makes it Godly | Explicit Godly set {36..41} |
| `:266-267` | `elemental`/`utility` derived from Mage/Handyman membership | Author explicitly: keep U on 05/11/20 (or decide otherwise), keep E list |
| `:270-273` | `d.tags = {Melee/Projectile, classes..., Elemental, Utility}` | Rebuild as weapon-type tags; only `WeaponClassTagTests:28` reads class tags |
| `combat/CharacterStats.luau:2` | `ClassOrder` with Thrower | Thrower → Chef (position decides UI order) |
| `:20` | `dashes(class)` | Decide Chef (proposal: yes) |
| `:76-86` | `Classes` (description, buffs, `build`, `two`, `four`, Handyman `gain`) | Remove Thrower, add Chef; drop `two`/`four`; `build` is used only by admin Build and starter fallbacks |
| `:87-90` | `Signature` | Thrower→Chef; Brawler can no longer be `'01'` |
| `:91-120` | `ClassFit` and `classFit` | Replace with a specialty function (same call shape helps UI) |
| `:121-125` | `S.inClass` (duplicate of the catalog's) | Point at the new starter rule |
| `:126-134` | `classFitText` | Dead (no callers); delete |
| `:149-154` | `bonusText` (formats `two`/`four`) | Unused once sets go; type-set bonuses may reuse it |
| `:170-181` | `resolve(class,count,...)` adds `two`/`four` when `count>=2/4` | Remove `count` term (or feed type-set bonuses here) |
| `:235-236` | `S.weapon` applies `classFit` | Swap in specialty `+%` when `w.starter==class` |
| `combat/ProfileService.luau:55` | `SIGNATURE` copy (not loaded from CharacterStats) | Keep in sync with Chef; keep a `Thrower` key only if the migration needs it |
| `combat/HandymanTurret.luau:12,26-27,203-221` | `Class='Handyman'`, `Base.home`/`tags`; `favoured()` scans `w.classes` | Use the starter rule; structure weighting follows new Handyman membership |
| `combat/MonetizationConfig.luau:57-59` | `ClassThrower`/`Juggler`/`Handyman` products (`class=`) | Keep the `ClassThrower` product id mapped (see §4); add a Chef product if it will be sold |
| `combat/QuestConfig.luau:201-203` | Class unlock rewards (WaveRider→Thrower) | WaveRider reward → Chef (or new rule); migrate claimed-WaveRider players |
| `QuestConfig.luau:220,227` | Win with 3 / all 6 classes | Still 6; old `classWins.Thrower` would count (see §4) |
| `combat/ChestConfig.luau:113` | `Legacy` chest names include Thrower | Keep (old chest conversion only) |
| `lobby/RunSetupRules.luau:85-86` | `Signature`, `ClassUnlock` (Thrower text) | Chef unlock text |
| `combat/TutorialConfig.luau:6-7,33-35,56` | Brawler + `'01'`, Pan seed copies, "Your pan swings" | Pick a valid class/weapon pair (Chef+Pan or Brawler+new starter) |

### Server logic

| File:line | What it does | Must change |
|---|---|---|
| `combat/CharacterService.luau:119-122,154` | Set count = equipped `inClass`, published as `AffinityCount` | Replace with type-set counts (count copies) |
| `CharacterService.luau:149` | GearPower fallback `Classes.Brawler.build[1]` | Constant starter id |
| `:171,212` | Unknown `RunClass` → Brawler | Keep; Thrower saves fall back here |
| `:305-315` | Admin `Class`/`Build` (`Classes[class].build` preset) | Keep or replace `build` with a test preset per class |
| `combat/RogueliteCombat.server.luau:21-26` | Starter fallback `Classes.Brawler.build[1]` | New constant; consider a class check |
| `:64-65` | `RunClass` → `setClass`; `RunWeapon` → `Shop.setStarter` | No change |
| `:235-236,241-249` | Builds definitions via `Stats.weapon(base,stats,class,tier)` | Specialty enters here automatically |
| `combat/ShopService.luau:158-162` | `wanted` item tags per class (incl. Thrower) | Chef row; Thrower out |
| `ShopService.luau:163-176,188-191` | `sameClassPool` from `w.classes`; 15% (+early bonus) same-class weapon offers | Decide: same starter class and/or same weapon type |
| `:284,313-327` | Turret weighting and free turret by class | Follows `HandymanTurret` |
| `combat/ShopCatalog.luau:16` | Weapon entry `description=w.home..' · '..kind`; icon by `w.home=='Mage'` | Use starter/type |
| `combat/ProfileService.luau:59,71` | Fresh profile: Brawler, Gunner, Mage plus their signatures | Decide default classes; new Brawler signature |
| `:133-142` | `setLoadout`: owned class + `inClass` or Godly | New rule |
| `:202-204` | Every owned class gets its signature weapon | Gives Chef owners the Chef signature automatically |
| `:271,283-286` | `grant{class}` adds signature; `signatureUpgrades` loops `SIGNATURE` | Removing the Thrower key changes the Arsenal bundle payout (6 entries still) |
| `:492-499` | `buyClass` requires `SIGNATURE[class]` | Chef purchasable; Thrower refused |
| `:646-653,674-686` | `claimUnlock`/`claimAll` grant `{class=}` | Follows QuestConfig |
| `combat/QuestService.luau:133,164-166,275-277` | `classWins[class]`; unlock class or refund `ClassRefund` 400 | Migrate `classWins.Thrower`; refund logic is reused |
| `combat/RogueliteMeta.server.luau:239` | Records the win class for feats | No change |
| `:265` | `weapon.utility` counts `utilityKills` | Depends on the explicit utility flag (§0.1) |
| `:714-729` | Dash approval `Stats.dashes(s.class)` | Follows `dashes` |
| `:843-863,880-892,897-905,1096-1106` | Product class eligibility, grant, receipt problems | ClassThrower policy (§4) |
| `:1337` | `BuyClass` emerald unlock | No change |
| `lobby/RunSetupRules.luau:100-104` | Pre-load defaults {Brawler, Gunner, Mage} + signatures | Match ProfileService defaults |
| `:119-129` | `classOrder`, `classWeapons` (= `homeWeapons`), `ownedGodlies` | `classWeapons` returns 6-7 per class |
| `:145-157` | `validLoadout` | New starter rule (§5) |
| `:71,75` | Gear power fallback `Signature.Brawler` | OK if Brawler keeps a signature |
| `lobby/RogueliteLobbyPreview.server.luau:343-348,362,414,428,446,509-519` | Loadout pick, validation, restore with signature fallback | No code change; behaviour follows `validLoadout` |
| `lobby/MatchService.luau:113-115,249-261` | Launch and match-server loadout validation | Same |
| `combat/TutorialDirector.server.luau:40,127-136` | Tutorial launch with `Config.Class`/`Weapon`; Studio path sets attributes directly | Valid pair (§0.3) |

### Client UI

| File:line | What it does | Must change |
|---|---|---|
| `ui/ArmoryUI.luau:197-224` | Local `describe` ("Home weapon of …") | New text |
| `:370-383` | `loadout()` fallback: `inClass` or Godly, else `Signature[class]` | New rule |
| `:806-823` | Classes tab: one card per `ClassOrder`, `Signature` icon | Chef icon |
| `:824-895` | Weapons tab grouped by `classWeapons(c)` / `w.home`; Godly group first; drives arrow order | Group by starter class; arrow order follows (ARMORY_NAVIGATION) |
| `:1134-1138` | Detail header class text | Starter plus types |
| `:1174-1188` | EQUIP chooses the start class from `w.classes` | One class |
| `:1232-1240` | "Starts runs as a X or Y." note | One class |
| `:1484-1530` | Class detail: Signature, dash, `classLines`, HOME WEAPON BONUS (`two`/`four`), WEAPON DAMAGE BY CLASS (`classFit` rows) | Replace bonus and fit sections with specialty and types |
| `ui/RunSetupUI.luau:21-30` | `dashDescription` (Brawler text), `classDamageText` | Chef dash text; specialty sentence |
| `:271-279` | Starter list: `classWeapons(class)` owned, then owned Godlies, then unowned | Same code, fewer tiles |
| `:313-336` | Class cards with fit badge `classFit({home=c},class)` | Remove or replace badge |
| `:344-350,429-437` | Pick = owned starter else `Signature` | No change |
| `:366-395` | Fit sentence chips per class | Replace |
| `:396-399` | Home-bonus rows (`two`/`four`) | Replace |
| `:401-411` | Locked class: `ClassUnlock`, `Class<name>` product, emerald buy | Chef product/unlock |
| `:522,546-549` | Fallback to Brawler / Signature | OK |
| `ui/LobbyUI.luau:38-39,53-57,88,117-123` | Signature/unlock tables; pre-load defaults; `homeWeapons` alias | Defaults |
| `LobbyUI.luau:304,442` | Class count shown as "/ 6" | OK for 6 classes |
| `ui/ItemCardUI.luau:385,390-392` | Kind line and class tag (`classNames`, `Signature[w.home]` icon) | Starter plus types |
| `:476-484` | `describe` plus "Starts runs as a …" | Wording |
| `:486-498` | DAMAGE BY CLASS tiles (`classFit` per `ClassOrder`, `own=inClass`) | Replace with specialty line |
| `ui/ShopUI.luau:12` | `Signature` local (unused) | Remove |
| `:331-362,589-593,755` | Class tag, fit badge and fit sentence ("Best matching class applies.") | Specialty plus type set progress |
| `:365,378` | `Stats.weapon(base,s,Class,tier)` previews | Automatic |
| `ui/StoreUI.luau:41,337-350,564` | Class product cards {Thrower,'12','ClassThrower'}, … | Chef card |
| `StoreUI.luau:297,514` | Arsenal reward icons per `ClassOrder` × `signature` | Automatic once Signature changes |
| `ui/CharacterStatsUI.luau:30-44` | Admin class buttons per `ClassOrder`, `AffinityCount` "home weapons · Bonuses at 2 and 4" | Text |
| `:147` | Weapon line via `Stats.weapon` | Automatic |
| `ui/UITheme.luau:256-263,331-358,360-404` | `fitColor`/`fitText`, `homeRows`, `fitTiles`, `fitBadge` | Retire or repurpose |
| `ui/WeaponJournalPresentation.luau:77-91` | Stat support from `utility`/`elemental` flags and kind | Follows explicit flags |
| `:93-115` | Journal groups by `w.home` in `ClassOrder` order plus Godly | Starter class |
| `:158` | Search category `classNames` | Starter/types |
| `ui/WeaponJournalUI.luau:335,398` | Class line, `describe` | Wording |
| `ui/WeaponShowcaseUI.luau:523` | Subtitle `classNames` | Wording |
| `ui/QuestsUI.luau:815` | "N classes" progress | No change |
| `combat/RogueliteCombat.client.luau:690-697` | Dash button from `Class`/`RunClass` | Follows `dashes` |

### Tests, tools and historical scripts

| File:line | Reads | Action |
|---|---|---|
| `combat/WeaponClassTagTests.luau:3-16,25,28,31,34` | Full 00-35 class roster, six names, class tags, `#List==42` | Rewrite for the starter map and type tags; 43 weapons |
| `combat/WeaponBalanceTests.luau:153-170` | `OLD_HOME`, 1-3 classes, utility==Handyman listed, Mage⇒elemental, Thrower names | Rewrite; assert the explicit E/U table |
| `WeaponBalanceTests.luau:11-24,88,96,101,141` | Per-id `OLD_T4`/`BEFORE`, rarity pool sizes | Add `'42'` |
| `combat/CharacterStatsTests.luau:22-32,42-44,51,55-72` | Class counts `WANT`, Signature home, ClassFit symmetry, AffinityCount, best-fit, utility from Handyman | Rewrite |
| `combat/ShopTests.luau:68-69,182,204-212,251-286` | Same-class pool via Thrower, Handyman turret by class | Update |
| `combat/TurretTests.luau:129,229-246` | No classFit on turret; Handyman rules | Mostly unchanged |
| `combat/NormalBalanceTests.luau:19,28` | `w.home` per weapon, Godly over `ClassOrder` | `home` → starter |
| `combat/EnemyScalingTests.luau:46-55` | Brawler `'01'` starter | Update starter pairs |
| `combat/QuestTests.luau:225,423,439` | WaveRider → Thrower | Chef |
| `combat/GiftTests.luau:26,53-56` | `ClassThrower` | Chef/legacy |
| `lobby/RunSetupValidationTests.luau:7,22-29` | Brawler+`'01'` accepted, Thrower locked | New pairs; add Godly, unknown-class and Chef cases |
| `ui/RunSetupLayoutTests.luau:18-27,55,96-101,119-128,140-146` | Thrower profile with 11 weapons, fit rows, dash Brawler-only | Rewrite around Chef or Juggler (7) |
| `ui/ShopLayoutTests.luau:75` | Class tag == `classNames` | Update |
| `ui/ArmoryExperienceTests.luau:13,75` | Brawler/`'01'` default, `classOrder` | Update default |
| `combat/BuildStatistics.py:20-21,27,96` | `w.home` and hard-coded six classes with Thrower | Update |
| `combat/SyncGodlyRuntime.luau:47-50` | Old patch strings for `homeWeapons`/`validLoadout` (`w.home==class`) | Stale sync script: do not re-run |
| `combat/plan_k_hunks.py:42,66` | Historical hunks (`weapon.utility`, `Signature.Brawler`) | Historical; leave |
| `ui/assets/store-products/make_product_images.py:157-159` | ClassThrower product art | Chef art if sold |

---

## 4. Thrower references (case-insensitive, whole `studio-prototype/`)

The only false positive is "Flamethrower duck" (`ui/WeaponShowcaseCatalog.luau:21`).

| Area | Occurrences |
|---|---|
| Catalog and stats | `combat/WeaponCatalog.luau:197-199,205,245`; `combat/CharacterStats.luau:2,79,90,98-103,126` |
| Server services | `combat/CharacterService.luau:121` (comment); `combat/ShopService.luau:160,164`; `combat/ChestConfig.luau:113` (legacy chests) |
| Profile | `combat/ProfileService.luau:55` (`SIGNATURE.Thrower='12'`) |
| Products and receipts | `combat/MonetizationConfig.luau:57,150`; `combat/RogueliteMeta.server.luau:1150` (comment); `ui/StoreUI.luau:41,564`; `ui/assets/store-products/make_product_images.py:157`; `ui/assets/store-products/products.md:42` |
| Quests | `combat/QuestConfig.luau:201` (WaveRider reward) |
| Run setup | `lobby/RunSetupRules.luau:86,124`; `ui/RunSetupUI.luau:274,369` (comments) |
| Armory and cards | `ui/ArmoryUI.luau:201,853-854,1137,1233` (comments); `ui/ItemCardUI.luau:390` (comment) |
| Tests | `combat/WeaponClassTagTests.luau:5-14,25`; `combat/CharacterStatsTests.luau:25,62-63,65,68`; `combat/WeaponBalanceTests.luau:153,169-170`; `combat/QuestTests.luau:225,423,439`; `combat/GiftTests.luau:26,53,55`; `combat/ShopTests.luau:204-205`; `lobby/RunSetupValidationTests.luau:25`; `ui/RunSetupLayoutTests.luau:3,6,18,20,27,55` |
| Tools | `combat/BuildStatistics.py:96` |
| Docs (not code) | `combat/NORMAL_BALANCE.md` (12), `combat/CHARACTER_STATS.md` (9), `ui/README.md` (5), `ui/assets/chests-pet-egg-2026-10-02-v1/README.txt:21` |
| Not referenced | Tutorial, admin panel and journal code (they use `ClassOrder`/`classNames` generically) |

### How saves store classes (`combat/ProfileService.luau`)

- **Owned classes:** `d.classes` is a set `{Brawler=true,...}`. A fresh save has Brawler, Gunner and Mage (`:59`). It is saved in DataStore `RogueliteProfile_v1`, key `u_<UserId>` (`:43,48`), and published as the CSV attribute `ProfileClasses` (`:83`).
- **Selected class and starter:** `d.loadout={class,weapon}` (`:64,133-147`). The per-server `RunClass`/`RunWeapon`/`LoadoutClass`/`LoadoutWeapon` attributes are set only after validation (`lobby/RogueliteLobbyPreview.server.luau:343-348,517-519`).
- **Quest records:** `st.classWins[class]=true` (`combat/QuestService.luau:62,133`), and `st.unlocks[questId]` for claimed unlocks (`:59,273`).

### How existing migrations are written

There is no schema version: `version=1` is a constant (`:59`). Migrations are idempotent fix-ups in `P.load` after the new-key backfill `for k,v in fresh() do if data[k]==nil ...` (`:181`):

- **Rename map:** `Chests.Legacy` renames old class chests to Wooden (`:184-186`; map at `combat/ChestConfig.luau:113`).
- **One-time conversion that clears the old field:** `keys` → emeralds (`:200-201`).
- **Backfill that follows a changed rule:** "Every owned class owns its starting weapon", added when Juggler's signature changed (`:202-204`).
- **Invalid-entry cleanup:** pets (`:198-199`).
- **Versioned conversion inside QuestService:** `RoadsVersion`/`convertRoads` (`combat/QuestService.luau:58`).

A Thrower→Chef migration fits the same place:

- Map or compensate `data.classes.Thrower`.
- Rewrite `data.loadout.class=='Thrower'`.
- Handle `quests.classWins.Thrower` and `quests.unlocks.WaveRider`.
- Then let `:204` grant Chef's signature.

Without it:
- `ProfileClasses` keeps publishing "Thrower", which inflates LobbyUI's "/ 6" count (`ui/LobbyUI.luau:304,442`).
- `validLoadout` says "Unknown class", so the restore silently drops the pick (`lobby/RogueliteLobbyPreview.server.luau:515-516`).

Fixtures are needed, because Studio always loads `fresh()` (`ProfileService.luau:177`). There is no ProfileService migration test today. QuestTests' old-save conversion (`combat/QuestTests.luau:189-210`) is the pattern to copy.

### Studio data isolation

- **Profiles:** `useStore=not IsStudio()`, so Studio uses an in-memory `fresh()` profile and `save` returns true without writing (`ProfileService.luau:6-7,44-45,177,216`). Studio also grants sample armor and pets (`:191-197`).
- **Other stores:** the leaderboard (`combat/LeaderboardService.server.luau:33-40`), gift stores (`RogueliteMeta.server.luau:931,938`) and the match trip log (`lobby/MatchService.luau:37`) are all skipped in Studio.
- **Purchases:** a Studio purchase is a simulation, "granted (not saved)" (`RogueliteMeta.server.luau:1232,1277`).
- **Test runs:** admin test runs are marked (`RogueliteCombat.server.luau:91`), and their quest wins are skipped (`ProfileService.luau:659`).

---

## 5. Starter rules

### `validLoadout` (`lobby/RunSetupRules.luau:145-157`)

1. The profile must be loaded.
2. The class must be a key of `Stats.Classes`.
3. The class must be owned (`progress().classes`, from `ProfileClasses`).
4. The weapon must be owned (`ProfileWeapons`).
5. `Weapons.inClass(w,class)` (any listed class) **or** `w.godly` (any class).

The Godly exception is repeated in four other places: `ProfileService.setLoadout` (`combat/ProfileService.luau:139`), Armory `loadout()` (`ui/ArmoryUI.luau:379`), EQUIP (`:1176`), and the RunSetup starter list via `ownedGodlies` (`lobby/RunSetupRules.luau:129`; `ui/RunSetupUI.luau:277`).

### Where the server enforces it

| Step | Location |
|---|---|
| Lobby Start/Play | `lobby/RogueliteLobbyPreview.server.luau:362` |
| Ready | `:414` (then `ProfileService.setLoadout`, `:343-348`) |
| Loadout change | `:428` |
| Pad launch re-check | `:446` |
| Restore after rejoin (falls back to `Signature[class]`) | `:509-519` |
| Match launch, per player | `lobby/MatchService.luau:113-115` |
| Match-server apply | `MatchService.luau:249-261` |

The combat server trusts `RunWeapon`. It checks only that the id exists in the catalog and has a template, otherwise it uses `Classes.Brawler.build[1]` = `'01'` (`combat/RogueliteCombat.server.luau:23-26`). `RunClass` → `CharacterService.setClass` checks only that the class exists (`combat/CharacterService.luau:201-205`).

### Defaults

| Default | Location |
|---|---|
| `Signature={Brawler='01',Gunner='00',Thrower='12',Juggler='17',Handyman='24',Mage='30'}` | `combat/CharacterStats.luau:90`; copy at `ProfileService.luau:55`; alias `RunSetupRules.luau:85` |
| Fresh and pre-load profile: Brawler, Gunner, Mage owned with Pan, Glock, Staff | `ProfileService.luau:59,71`; `RunSetupRules.luau:100-103`; `ui/LobbyUI.luau:53-57` |
| UI falls back to Brawler | `ui/ArmoryUI.luau:371-374`; `ui/RunSetupUI.luau:522`; `ui/LobbyUI.luau:117` |

### Tutorial

- `TutorialConfig.Class='Brawler'`, `Weapon='01'` (Frying Pan) (`combat/TutorialConfig.luau:7`).
- **Published:** `Match.launch` validates the pair (`combat/TutorialDirector.server.luau:40` → `lobby/MatchService.luau:114`).
- **Studio Combined:** sets `RunClass`/`RunWeapon` directly without validation (`TutorialDirector.server.luau:136`).
- If the Pan moves to Chef, either the tutorial plays Chef (and fresh profiles must own Chef), or Brawler gets a new starter and the seeded chest and guide move with it (`TutorialConfig.luau:33-35`; `ui/TutorialGuide.client.luau:280-287`; `combat/TutorialTests.luau:45`).

---

## 6. Dash eligibility

| Side | Location |
|---|---|
| Rule | `CharacterStats.dashes(class)` = `class=='Brawler'` (`combat/CharacterStats.luau:18-20`); tuning `S.Dash` (`:17`) |
| Server approval | `RunAction 'Dash'` → `dash(p)`: run member, alive, Combat/Practice phase, not paused/frozen/in shop, `Stats.dashes(Characters.states[p].class)`, cooldown 3−0.3 s; stamps `DashAt` (`combat/RogueliteMeta.server.luau:720-729,764`) |
| Server effects | MovementGuard allowance (`combat/MovementGuard.server.luau:94-99`); i-frames 0.35 s (`combat/CharacterService.luau:262-265`); seen-position lead (`:77-80`) |
| Client | Button and input gate `allowed()` reads state folder `Class`, else `RunClass` (`combat/RogueliteCombat.client.luau:690-697`); dash fired at `:733` |
| UI text | `RunSetupUI.dashDescription` hard-codes "Brawler class ability" (`ui/RunSetupUI.luau:21-27`); Armory class detail (`ui/ArmoryUI.luau:1505-1509`) |
| Test | `ui/RunSetupLayoutTests.luau:140-146` asserts Brawler-only for every class and weapon |

Adding Chef means changing `dashes` and the hard-coded text. Server and client follow automatically.

---

## 7. Tests and how they are run

### Relevant tests

| Test | Covers | Mode |
|---|---|---|
| `combat/WeaponClassTagTests.luau` | Class roster, tags, `#List==42` | Pure `function(Weapons)` |
| `combat/WeaponBalanceTests.luau` | Per-id tiers, rarity pools, homes, E/U | Script with `Result` attribute; Edit (`ui/README.md:39`) |
| `combat/CharacterStatsTests.luau` | Class counts, Signature, ClassFit, AffinityCount | Play server |
| `combat/ShopTests.luau` | Same-class pools, turret by class | Play server (`:307` sets `Result`) |
| `combat/NormalBalanceTests.luau`, `combat/EnemyScalingTests.luau`, `combat/GearPowerTests.luau` | One-hit fodder by home, starter pairs | Pure via `combat/run_enemy_scaling_tests.py` |
| `combat/GodlyWeaponsTests.luau`, `LegendaryMovesTests.luau`, `ChestConfigTests.luau`, `TurretTests.luau` | Godly ids, 7 Legendaries, rarity pool sizes, turret vs ranged average | Pure |
| `combat/QuestTests.luau`, `combat/GiftTests.luau` | WaveRider→Thrower, ClassThrower gifting | Pure |
| `combat/WeaponJournalTests.luau` (`#WeaponIds==42`, `:19`), `WeaponJournalPlayTests.server.luau` | Journal | Pure / Play |
| `combat/ArcAttackTests.luau`, `CommittedThrowTests.luau`, `WeaponBehaviorTests.luau`, `MeleeMotionTests.luau`, `SwingArcTests.luau`, `DuckBurstTests.luau`, `WasherBurstTests.luau`, `StatProjectileTests.luau`, `TravelAccuracyTests.luau` | Attack behaviour | Mostly pure; ArcAttack is Play |
| `lobby/RunSetupValidationTests.luau` | `validLoadout` | Pure `T.run(RunSetupRules)` |
| `ui/RunSetupLayoutTests.luau`, `ArmoryExperienceTests.luau`, `ShopLayoutTests.luau`, `WeaponJournalLayoutTests.luau`, `ReportedBugfixTests.luau` | Menus | Play client |
| `ui/WeaponShowcaseTests.luau` (`#recipes.List==42`, `:11`), `WeaponShowcaseBrowserTests.luau`, `WeaponShowcaseLiveEffectsTests.luau`, `WeaponJournalPresentationTests.luau` | Showcase and journal | Pure `.run` / client |
| `ui/ArmoryNavigationTests.py`, `ui/DailyDealRewardTests.py` | Extracted UI code (mocked ids) | Luau CLI |

No `*Tests`/`*QA` file is in the Rojo build. Several headers say so (`combat/WeaponJournalPlayTests.server.luau:1`).

### Ways to run them

**A. Luau CLI (pure)**
- `build/luau-validation/luau.exe` (untracked; `.gitignore` ignores `build/`).
- Python runners inline the sources and replace Roblox requires by exact anchor strings:
  - `python roguelite-planning/studio-prototype/combat/run_enemy_scaling_tests.py build/luau-validation/luau.exe` (`combat/ENEMY_SCALING.md:33`; anchors at `combat/run_enemy_scaling_tests.py:15-45`, which include `CharacterStats.luau:3,198` and `RunSetupRules.luau:6,8`)
  - `run_wave_timeline_tests.py`
  - `CrowdSteeringTests.py`, `SpawnDirectorTests.py` (`combat/CROWD_STABILITY_2026-10-05.md:18`; `combat/SWARM_DISTRIBUTION_2026-10-05.md:33`)
  - `BuildStatistics.py build/luau-validation/luau.exe` (`combat/BuildStatistics.py:2`)
- Editing the anchor lines breaks these runners.
- WeaponClassTagTests' 547-check run (`ui/WEAPON_CLASS_TAG_AUDIT_2026-10-05.md:11`) used a hand-assembled `build/luau-validation/weapon-class-audit.luau`. It is now stale and needs regenerating.

**B. Studio Edit from the repo**
- Start the dev server: `python ".../studio-prototype/tools/dev_server.py" 8934` (`plans/2026-10-02-K-build-steps.md:63-65`).
- Then in `execute_luau`:
  ```lua
  local HS=game:GetService('HttpService');local base='http://127.0.0.1:8934/studio-prototype/'
  local Fresh=loadstring(HS:GetAsync(base..'tools/FreshRequire.luau?t='..os.clock(),true))()(base)
  print(Fresh.require('GiftTests')(Fresh.require('MonetizationConfig')))
  ```
  (`tools/FreshRequire.luau:6-10`; `combat/GiftTests.luau:6-7`).
- Generic loader (`plans/2026-10-02-K-build-steps.md:69-79`): `local function load(p) local src=HS:GetAsync(base..p..'?t='..os.clock(),true):gsub('\r\n','\n');local fn,err=loadstring(src,'='..p);assert(fn,err);return fn() end` then `pcall(load('combat/QuestTests.luau'),S,C)`.
- `tools/RepoRequire.luau:12-15` covers map-boss modules only.

**C. Play server**
- Use the `serverCheck` wrapper (`plans/2026-09-28-D-admin-panel.md:126-138`). It installs a temporary Script and polls its `Result` attribute.
- Never require stateful services from `execute_luau` (`:124`).
- Per project memory, a Play session needs the user's okay first.

**D. Play client**
- Install a temporary ModuleScript, then `require(...)()`, e.g. `require(game.ReplicatedStorage.DuckBurstTests)()` (`combat/DUCK_BURSTS_2026-10-06.md:22`).

**Build**
- `rojo build roguelite-planning/studio-prototype/combat/default.project.json -o build/RogueliteKatanaCombat.rbxlx` (`combat/README.md:68`).
- Modules land in `ReplicatedStorage.RogueliteCombat` and services in `ServerScriptService`. `WeaponTemplates` is a Studio-only instance; Rojo keeps unknown instances (`combat/default.project.json:15`).

### Hard-coded values that break

**Adding a non-Godly `'42'`:**
- `WeaponClassTagTests:31,34`
- `WeaponBalanceTests:88,96,101,160`
- `WeaponJournalTests:19`
- `WeaponShowcaseTests:11` (plus the allowed mode list at `:12-35`)
- `ChestConfigTests:23-26`
- `CharacterStatsTests:25`
- Possibly `LegendaryMovesTests:64` (if Legendary), `NormalBalanceTests:28`, `TurretTests:91,94` (if ranged)

**Thrower → Chef:**
- `WeaponClassTagTests:4-16,25`
- `WeaponBalanceTests:153,169-170`
- `CharacterStatsTests:25,62-63,68`
- `RunSetupLayoutTests:18,55`
- `QuestTests:225,439`
- `GiftTests:26,55`
- `ShopTests:209`
- `RunSetupValidationTests:25` still passes, but now for "Unknown class" rather than "locked".

---

## 8. Held weapon pipeline

### Id → model

- **Held templates:** `ReplicatedStorage.RogueliteCombat.WeaponTemplates.<id>`. They are built from `workspace.RogueliteWeaponShowcase_PlaySize` children `NN_Name`, with identity pivot (`combat/InstallLoadout.luau:5-10,32,42-46`).
- **Katana** comes from `KatanaTemplate` (`combat/InstallKatana.luau:6-22`).
- **Rocket** is split into `RocketTemplate` (`InstallLoadout.luau:47-55`).
- **Godlies** come from `../weapon-models/godly/studio-import/studio-install-godly-weapons.luau:65-144`.
- **Required attributes:** only `BoundsSize`/`BoundsCenter`, in the pivot frame. There are no grip attributes; the grip is derived from bounds (`combat/WeaponMotion.luau:151,195-196`).
- **Who reads the bounds:**
  - server hit boxes (`combat/RogueliteCombat.server.luau:494,508`)
  - spacing (`combat/RogueliteCombat.client.luau:104-105`)
  - swing ribbons (`combat/SwingVisuals.luau:53-54`)
  - Armory recentring (`ui/ArmoryStage.luau:191-209`)
- **Orientation:** melee striking end on +Y; guns point −Z (`InstallLoadout.luau:24-31`).
- **Optional per-id presentation fixes:** `combat/WeaponPresentation.luau:4-35`, e.g. the Pan stands bowl-up at `:11`.
- **Offline helpers:** `measure_*.py` → `weapon-presentation-bounds.json` and `ChainWeaponGeometry.luau`. `FixWeaponRendering.luau:14-35` only sets RenderFidelity and anchoring.

### Client per slot

1. Clone the template, anchor it, turn off collision (`RogueliteCombat.client.luau:81-100`).
2. Place it on the ring: radius `6.2+0.36×(n−1)` (`WeaponMotion.luau:40-44`); slot angles `SlotLayout` (`:49-56`); `origin()` (`:70-74`); follow-spring `floatPose`.
3. Melee swings start at `combatOrigin` (player centre +0.25 Y).
4. `PivotTo(pose)` (client `:160`), then the overlap solver nudges weapons apart (`:219-233`).

### Armory and showcase

- `ArmoryStage.display` clones the same template (`ui/ArmoryStage.luau:159-213`).
- `WeaponShowcaseStage` clones it (`ui/WeaponShowcaseStage.luau:317-325`) and reuses `Motion`/`Chains` (`:477-569`).
- `WeaponShowcaseCatalog.build` asserts a recipe exists for every id (`ui/WeaponShowcaseCatalog.luau:107`).

### Melee animation

All melee is CFrame-scripted. No weapon uses AnimationTracks.

- **One shared pose function:** `WeaponMotion.pose` (`:123-222`) drives both rendering and server hit sampling. Style branches: Diagonal `:169-178`, Thrust `:179-190`, Downward `:191-210`, Slap `:211-213`, Chain `:215`.
- **Timing:** hit window 0.12-0.46 of a 0.9 animation-time swing (`:2-5,75-78`). It runs at `motionRate` = 1.8 × attack speed (Nunchucks 1.35, Gloves 2.7) (`combat/CharacterStats.luau:242`).
- **Entry and return:** blends in from the previous pose (client `:150`), then eases back with one elastic rebound (`WeaponMotion.luau:95-121,255-264`).
- **Unused module:** `KatanaMotion.luau` is not used at runtime.

### Pan, Spatula and Steak (templates for Pizza Cutter)

| | Pan `01` | Spatula `05` | Steak `16` |
|---|---|---|---|
| dmg / cd / reach | 18 / 1.05 / 7.5 (`WeaponCatalog.luau:19`) | 9 / .55 / 7.5, KB 14 (`:23,259`) | 16 / .85 / 7.5 (`:34`) |
| Styles | `DownwardWeapons` (`WeaponMotion.luau:18`): under 3 studs → Horizontal (`:228`); beyond base reach → Downward ×1.25 reach (`:231`); crowd → Horizontal; else Horizontal → Diagonal → Downward (`:245-246`) | Same as Pan | Odd swings Slap, even Diagonal (`:242`) |
| Downward / Slap motion | Grip at `BoundsCenter.Y−0.42×length`; pitch −10° → +35° windup → −135° strike; hand advances up to 4 studs (`:191-210`) | Same | Slap slides +2.5 → −2.8 studs × side, yaw −25° → +30°, roll 65° (`:211-213`) |
| Swing ribbon | blade, inner .05 (`combat/SwingVisuals.luau:14`) | blade, inner .15 (`:18`) | blob, width 1.1 (`:20`) |
| Extra | Presentation fix (`WeaponPresentation.luau:11`) | — | `LastContact` wobble: `sin(t·80)×.24` rad for 0.3 s (client `:178-181`; server `:287`) |

### Checklist for a new melee id `'42'`

1. **Catalog:** `names`/`profiles`/`RarityLists`, kept out of `ranged`, with the `n>=30`/`n>=36` rules fixed (§0.2).
2. **Motion:** add it to `DownwardWeapons` or `MeleeStyles`, or give it a `chooseStyle` branch. Otherwise it swings Horizontal.
3. **Template:** `WeaponTemplates['42']` with bounds, striking end on +Y. Install it the way the Godly installer does, not via `InstallLoadout`.
4. **Swing ribbon:** a `SwingVisuals.Profiles` entry; without one there is no swoosh (`SwingVisuals.luau:52`).
5. **Showcase:** a `WeaponShowcaseCatalog` recipe (required).
6. **Icon:** `Icons['42']` in `ui/WeaponInventoryUI.luau:8-51`. Most screens index it directly (e.g. `ui/ArmoryUI.luau:24`, `ui/ShopUI.luau:11`, `ui/RunSetupUI.luau:18`).

### Separately moving parts

| Weapon | Mechanism | Source |
|---|---|---|
| Nunchucks `02`, Kusarigama `04`, Wrecking Ball `25` | Skinned bones (`W<id>_Handle_ROOT`, `Chain_N`, `*_END`) driven by `bone.Transform` every frame | `combat/ChainWeaponMotion.luau:6-10,17-157`; client `:84,141-143,182`; server rigs `:8-10` |
| Pandora lid `33` | Bone `W33_Lid_Hinge` via `.Transform` | client `:95,184`; showcase `:351,571-572` |
| Gloves `19` | Each part's CFrame set every frame | client `:85-90,161-173` |
| Egg / pin reserves | Extra clones moved with `PivotTo` | client `:91-94,175-177` |
| Yo-yo `21` | Held disc hidden; a cloned disc flies spinning about Z; a Beam string runs to the finger loop; 0.16 s reel-in | `combat/ProjectileStyleVisuals.luau:142-174,225-250` |
| Thrown weapons | Clone flown and spun per `SpecialMotion.rotation` | `combat/SpecialMotion.luau:27-41`; `combat/SpecialWeaponVisuals.luau:109-153` |
| Rocket `11` | Rocket removed from the held launcher; a `RocketTemplate` clone flies | `InstallLoadout.luau:18-20`; `combat/RocketVisuals.luau:112-132` |

**Pizza Cutter wheel:** the closest precedent is the Pandora lid: a bone such as `W42_Wheel` driven by `.Transform`. A per-part CFrame like the gloves also works. Either way it needs code in both `RogueliteCombat.client` (next to `:182-184`) and `WeaponShowcaseStage` (next to `:569-572`). The server needs nothing, because hits use the single bounds box. If the spin should react to hits, widen `contact()` at `server:287`.
