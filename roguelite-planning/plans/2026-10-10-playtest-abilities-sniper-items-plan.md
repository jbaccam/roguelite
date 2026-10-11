# Play-test follow-up: class abilities, Sniper Rifle, Tier III items, Spellbook (2026-10-10)

Plan only. Nothing here is built yet. Paths are relative to `roguelite-planning/studio-prototype/` unless noted.

Decisions already made in the chat:
- Turrets are Handyman only.
- Mage gets a teleport (blink), but Mage is already the strongest class, so the blink must not make it stronger at killing.
- Chef food drops for every Chef weapon (done 2026-10-10 in `combat/ChefPizza.luau`; decided by the weapon's Chef class tag).
- Excalibur moved to Brawler (done 2026-10-10). The Spellbook takes its place in the Mage kit; Mage has 5 weapons and no Tier III weapon until then.
- Wave 50 Nightmare should stay hard.

## 1. Class abilities

### 1.1 What each class gets

| Class | Ability | Type | Input | Status |
|---|---|---|---|---|
| Brawler | Dash: 28 studs, 3 s cooldown, 0.35 s of no damage | Active | Q / gamepad X / button | Exists, no change |
| Mage | Blink: 18 studs, 8 s cooldown, no damage, no invulnerability | Active | Q / gamepad X / button | New (1.4) |
| Handyman | Turrets follow him (pack up and rebuild near him) | Passive | none | New (1.5) |
| Chef | Pizza drops (8% per kill with a Chef weapon, heals 10% max HP x Recovery) | Passive | none | Done (1.6) |
| Gunner | None for now. Later idea: Combat Roll, 12 studs, 5 s | - | - | Later |
| Juggler | None for now. Later idea: Double Jump | - | - | Later |

### 1.2 One framework, built from the dash

The dash already has a key, a button, a server check and a cooldown. Turn it into a general class ability instead of adding a second system.

- **New shared module `combat/ClassAbilities.luau`** (pure data and rules, like `HandymanTurret.luau`):
  - `A.of(class)` returns `{id, kind='active'|'passive', label, icon, cooldown, ...}` or nil.
  - `A.canUse(state)` holds the shared gate (1.3).
  - `A.blinkLanding(from, dir, probe)` returns the landing spot or nil.
  - `A.text(class)` gives the class screen row.
- **Server:** `dash(p)` in `RogueliteMeta.server.luau` becomes `ability(p, arg)`. It runs the gate, then sends Dash to today's code and Blink to a new `combat/ClassAbilityService.luau`. New RunAction `'Ability'`; `'Dash'` stays as an alias.
- **Attributes (server writes only):** `AbilityReadyAt` (server time, drives the button's cooldown ring); `DashAt` unchanged (MovementGuard and CharacterService read it); `BlinkAt`, `BlinkFrom`, `BlinkTo` for everyone's VFX.
- **Client:** the DASH section of `RogueliteCombat.client.luau` reads `A.of(class)` for label and icon (DASH or BLINK). Same keys, same button spot. Passive classes get no button.
- **Class screen:** `ui/RunSetupUI.luau` `M.ability(class)` reads `A.text(class)`.

### 1.3 Server validation (every active ability)

- Class comes from the server's character state, never the client.
- Same gate as the dash: living run member, not down, not in lobby preview, not paused, not in the shop, not frozen (includes boss intros, `CinematicUntil`), phase Combat or Practice.
- Cooldown on the server clock with 0.3 s grace. Example: a blink 7.8 s after the last passes; 7 s after does not.
- Direction: client sends one unit vector; the server keeps the flat part, and falls back to body facing if it isn't a finite unit vector.
- A refused use costs nothing (no cooldown, small fizzle sound).
- Abilities share the existing RunAction rate limit.

### 1.4 Mage Blink (defensive only)

| | Brawler Dash | Mage Blink |
|---|---|---|
| Distance | 28 studs | **18 studs** |
| Cooldown | 3 s | **8 s** |
| Invulnerable | 0.35 s | **none** |
| Damage | none | none |
| Cost | none | **Arcane Recoil: weapons hold fire 0.5 s after the blink** |
| Escape per minute | 560 studs | 135 studs |

- **Server does the teleport** from its own root position. One ray along the direction finds walls (ignores enemies and players); stops 2 studs short.
- **Landing needs** floor within 8 studs of current floor height, inside the arena circle (`SpawnAreaRadius` - 6), inside the MovementGuard box. If 18 fails try 12, then 6, then refuse.
- Server moves the body with `PivotTo`, keeps facing. MovementGuard already restarts its check on server CFrame writes, so no new allowance should be needed. Confirm in Play; if it snaps back, add a `BlinkAt` allowance like `DashAt`.
- **Hold fire:** server sets `HoldFireUntil` (+0.5 s); the weapon loop in `RogueliteCombat.server.luau` skips attacks until then. The Staff fires every 1.3 s, so a blink costs 0 or 1 Staff shot; at most 6% of Mage damage if used on every cooldown.
- Example: 6 zombies 3 studs around a Mage. She blinks 18 studs. At 12 studs/s they need about 1.25 s to reach her. Safe for a moment, no extra kills.
- Feel: client plays a 0.1 s flash at once; the real move follows one ping later.
- If play tests still show Mage on top: trim Mage's +25 Elemental damage to +20, not the blink.

### 1.5 Handyman turrets: Handyman only, and they follow him

**Handyman only.** Since 2026-10-04 turret items and Scrap Magnet are sold to anyone (`H.offerable` / `H.favoured`). Change: Nail Turret, Twin Nailer, Quad Nailer, Gatling Rig and Scrap Magnet are offered to and sold to Handyman only. Toolbelt stays for anyone with a utility weapon.
- `HandymanTurret.offerable(entry, owned, class)` checks class; `H.favoured` becomes class-only; `ShopService` passes class in and refuses the buy for others.
- Turret items last one run, so no save migration.

**Follow (friend's idea, on today's placement code).**
- Unchanged: wave-start ring 4-8 studs, 5 studs apart; 30-turret server cap; 500-stud re-place.
- New mid-wave: a turret more than **20 studs** (flat) from the Handyman is left behind (range 25, so it still covers 5 studs past him). It packs up for **0.3 s** (no fire), then rebuilds at a free ring spot, first spot along his move direction. The existing 0.35 s build pop runs, so a move costs about 0.65 s offline.
- Limits: at most **2** turrets moving at once; each waits **1.5 s** between moves; Scrap Magnet temporaries follow the same rule.
- Example: 5 turrets, he runs straight at 24 studs/s. A turret landing 8 studs ahead is 20 studs behind again ~1.2 s later, so each fires ~65% of the time (about 3 of 5 while he runs, all 5 when he stands). Plant and fight, or run and lose some turret damage.
- Server (`HandymanTurretService.server.luau`): `packing` state per turret (fire loop skips it); reuse `add()`'s free-spot search keeping Folder and Index (clients re-pose by Index already). One probe per move: up to 3 points, 2 rays each.
- Client (`HandymanTurret.client.luau`): new `PackAt` attribute plays a fold-down (head drops, scale to 0.6) and dust puff, then the existing pop-in at the new `Position` / `BuiltAt`.
- Pure helpers in `HandymanTurret.luau`: `FOLLOW_DISTANCE=20`, `PACK_TIME=.3`, `FOLLOW_AT_ONCE=2`, `FOLLOW_COOLDOWN=1.5`, `H.leftBehind(turrets, position, now)`; tested in `TurretTests`.
- Phase 2 option: Handyman active "Rally" (Q: every turret packs and rebuilds around him; 10 s cooldown).

### 1.6 Chef food (done)

`ChefPizza.luau`: 8% per kill with any Chef-class weapon, at most one drop per 1.5 s, heals 10% max HP x Recovery, at most 4 slices on the ground, 12 s each. The ability framework only shows it as the Chef passive row.

## 2. Sniper Rifle (Gunner)

"Really slow, hella damage, a piercing line across the map, the boss killer." It must not also be best at clearing swarms.

### 2.1 Catalog entry

- Id `'43'` (next free; ids are never reused). Gunner only. Types `{'Gun'}`, kind Ranged, `StraightGuns['43']=true`.
- Rarity Legendary (see question 1).
- Profile: `{60,3.4,110,nil,nil,'line'}, -- Sniper Rifle` -> after Legendary x1.2: 72 damage every 3.4 s.

| Tier | Damage | Cooldown | DPS vs mobs | DPS vs bosses (+50%) | Look |
|---|---|---|---|---|---|
| I | 72 | 3.40 s | 21.2 | 31.8 | Bolt-action, wood stock |
| II | 101 | 3.06 s | 33.0 | 49.5 | Bigger scope, sling |
| III | 141 | 2.72 s | 51.8 | 77.8 | Muzzle brake, bipod |
| IV | 198 | 2.38 s | 83.2 | 124.8 | Gold trim, Spotter's Mark |

Tier IV single target, no class bonuses: Katana 89.7, Excalibur 90.6, Poseidon's Trident 88.6, Rocket Launcher 55.6. So vs mobs it sits with other Legendaries; vs bosses it is the best single slot.

Gunner example: Tier III Sniper on a boss = 141 x 1.20 (Gunner ranged) x 1.10 (specialty) x 1.5 (boss) = 279 per shot, every 2.72 / 1.1 = 2.47 s = 113 boss DPS from one slot.

### 2.2 How it fires

- Aim 0.45 s: thin laser from barrel to target, follows it; then instant hitscan along the line.
- Line up to 300 studs, stops at the first wall/terrain; enemies and players never stop it (crosses Pine Valley, boundary 147 from center). 2.5 studs wide plus enemy body size, counting enemies within 8 studs above/below.
- Damage: first non-boss 100%, later non-boss 40%, bosses always 100% +50%.
- Boss bonus is +50 added to the Boss damage stat, not multiplied (with Bone Crown +20: x1.70).
- Targets up to 110 studs (Attack Range scales it). Never picks a target inside 6 studs, but the line still hits anything in its path.

### 2.3 Targeting (fits TargetGrid)

- New pure `TargetGrid.toughest(grid, origin, range, minRange, can, measure, clear)`: boss in range with clear line, then elite (`IsElite`), then most current HP, tie -> farther.
- `RogueliteCombat.server.luau` snapshot adds `hp` and `elite` per entry (it already has `hum`). Bosses keep nearest-body-box measuring.
- Hit test: one pass over `snap.list` with `LegendaryMoves.segmentDistance` plus one wall ray. One shot per 2.4-3.4 s is cheap even with 150 enemies.
- New server launcher `combat/SniperShots.luau`: aim delay, re-pick if the target died, hitscan, falloff. Hits use the normal damage path (crits, procs, life steal, kill credit). `shoot()` routes `d.id=='43'` to it.

### 2.4 What it uses and ignores

- Uses: Damage, Ranged damage, specialty, Gun set, crit, attack speed, Gunner +10% ranged attack speed, burn/poison/slow/lightning procs, life steal, Boss damage.
- Ignores: extra projectiles (Two Straws, Gun 4), Pierce, Bounce, Area Size, projectile size/speed. `CharacterStats.usesStat` returns false for these on `'43'`, so the shop won't push Straws/Pencil/Bouncy Ball for a lone Sniper and "Works with" stays true. (Otherwise Two Straws or Gun 4 would double its boss damage.)
- Tier IV move Spotter's Mark: `C.Legendary['43']={move='Mark',every=3,factor=.15,seconds=4}`. Every 3rd shot marks the first enemy/boss hit for 4 s: +15% from all your hits. Reuses the Owl pet mark attributes (`PetMark_<id>` / `PetMarkUntil_<id>`), keeping the larger mark and later expiry.

### 2.5 Why it isn't best at everything

Tier III, one copy, wave 15 Normal (regular zombie ~20 HP):

| Weapon | Boss DPS | Swarm kills/s | Close defense |
|---|---|---|---|
| Sniper | 77.8 | ~2.2 only when 6 line up; usually 1-3 | Poor: 2.7 s between shots, skips inside 6 studs, aims at tanks |
| Rocket Launcher | 34.6 | ~2.3 (5 in a 6-stud blast) | OK |
| Draco | ~48 | ~2.2 (3 bullets per kill) | Good |

Swarm clear drops as mob HP grows (40% follow-on hits stop killing).
Watch item: six Tier IV Snipers on a Gunner (Gun 6) ~1,250 boss DPS vs six Tier IV Katanas on a Brawler ~820. 1.5x on bosses, very weak to swarms. Check in play tests before capping.

### 2.6 Visuals

- Laser: thin red-orange, 50% transparent, during the 0.45 s aim. Tracer: white core, gold edge, 0.25 studs, fades 0.35 s.
- Muzzle flash (`MuzzleFlashVisuals`), sparks per hit (`BulletImpactVisuals`), small camera kick for the shooter only.
- Teammates' tracers at 50% transparency; enemy hazards stay most readable.
- Visuals ride `ShotBatch` as new kinds `SniperAim` and `SniperLine` (origin, end, hit points). Clients only draw.
- Sound: heavy crack with echo tail; soft tick at aim start.

## 3. Tier III items for melee and other classes

### 3.1 Audit (`combat/ShopCatalog.luau`)

| Item | Tier | Works with | Playstyle |
|---|---|---|---|
| Two Straws | III | guns, staffs, cards, throws, turrets | Ranged |
| Bouncy Ball | III | throws, cards, yo-yos, magic bolts | Ranged |
| Tinfoil Antlers | III | needs lightning | Elemental |
| Battery Pack | III | any | Proc (lightning) |
| Grandma's Oven Mitt | III | any | Proc (burn) |
| Vampire Fang | III | any | Sustain |
| Vitamin Gummies | III | any | Sustain |
| Cracked Burial Mask | III | any | Defense |
| Quad Nailer | III | turrets | Handyman |
| Bubble Wrap Vest | IV | any | Defense |
| Gatling Rig | IV | turrets | Handyman |

Attack-changing Tier III: 2 ranged, 1 elemental, 0 melee. A Katana build has no preferred item above Tier II; a Frying Pan build only gets Mask, Fang and Gummies; the only melee damage item in the shop is Knee of Justice (Tier I).

### 3.2 Eight new Tier III items (existing stat ids only)

| id | Name (working) | Base | Cap | modifiers | percent | Tags | Offered to | Card text |
|---|---|---|---|---|---|---|---|---|
| `cane` | Grandpa's Cane | 66 | 2 | MeleeDamage=10, AttackRange=20 | | Melee, Range | needs a melee weapon | Your weapons reach 20% farther, and melee weapons deal 10% more damage. |
| `steeltoe` | Steel-Toe Boots | 68 | 3 | MeleeDamage=18, Armor=2, Knockback=6 | MoveSpeed=-3 | Melee, Armor | needs a melee weapon | Melee weapons deal 18% more damage, +2 armor, your hits push harder. You move 3% slower. |
| `whetstone` | Whetstone | 70 | 2 | CritChance=6, CritDamage=25 | | Crit, Melee | anyone (Blade/melee prefer) | +6% crit chance, and crits hit harder: x1.5 becomes x1.75. |
| `knucklebone` | Giant's Knucklebone | 66 | 2 | MeleeDamage=8, BossDamage=25 | | Melee, Boss | needs a melee weapon | Melee weapons deal 8% more damage, and all your weapons deal 25% more to bosses and elites. |
| `apron` | Grease-Stained Apron | 70 | 2 | MeleeDamage=10, LifeSteal=2, LifeStealCap=4 | | Melee, Health | needs a melee weapon | Melee weapons deal 10% more damage. Heal 2% of damage dealt, up to 4 HP/s more. |
| `doggybag` | Doggy Bag | 64 | 3 | MaxHP=12, Recovery=30 | | Health | anyone (Culinary prefers) | +12 max health, and all healing heals 30% more: pizza, hearts, regen, life steal. |
| `jumprope` | Jump Rope | 66 | 3 | Dodge=6, AttackSpeed=6 | MoveSpeed=6 | Mobility, AttackSpeed | anyone (Trick prefers) | 6% of enemy hits miss you, weapons attack 6% faster, you move 6% faster. |
| `powerstrip` | Power Strip | 72 | 2 | UtilityPower=15, CooldownReduction=5 | | Utility, Structure | needs a utility weapon or turrets | Utility weapons and turrets deal 15% more damage. Weapon cooldowns 5% shorter (not turrets). |

Examples:
- Grandpa's Cane: Baseball Bat reach 9.5 -> 11.4 studs, 1.44x the ground.
- Doggy Bag on a Chef (115 max HP, Recovery +25): a pizza slice heals 11.5 x 1.55 = 17.8 HP (was 14.4).
- Power Strip on a Handyman: +18.75 Utility Power (his gains x1.25).
- Whetstone in a Blade 6 Katana build: crit chance 5 + 10 + 6 = 21%.

After this Tier III has 17 items, 5 for melee builds.

Code: `ShopCatalog.usable` gates items whose stats are all weapon-only; items mixing in a general stat need a new flag `entry.needs='Melee'` (offer only if a carried weapon has `kind=='Melee'` or `hybridRange`). `C.worksWith` uses the same flag. Add the 8 to `itemTags` (`TypeWants` already sends Crit to Blade, Armor to Blunt, Health to Culinary, Mobility to Trick). First-pass numbers: check with `RosterBalanceTests` and the shop Monte Carlo before shipping.

## 4. Spellbook (Mage, replaces Excalibur)

### 4.1 Catalog entry

- Id `'44'`. Mage. Types `{'Elemental'}`, add to `ElementalIds`, kind Ranged. Legendary (Mage keeps 2: Mjolnir and Spellbook).
- Profile: `{18,1.3,33,nil,nil,'spells'}, -- Spellbook` -> 21 damage every 1.264 s after rarity power.
- Mage starter list gains `'44'`.

| Tier | Damage | Cooldown | DPS | What changes |
|---|---|---|---|---|
| I | 21 | 1.264 s | 16.6 | Casts Fire, Frost, Spark in turn |
| II | 29 | 1.138 s | 25.5 | Bolts pierce 1 enemy (70%) |
| III | 41 | 1.011 s | 40.6 | Spark chains 1 more enemy |
| IV | 58 | 0.885 s | 65.5 | Pierce 2, plus Meteor Page every 6th cast |

Excalibur did 23.1 / 90.6 DPS (melee); Deck of Cards does 16.7 at Tier I. Mage loses raw damage and gains range, which fits "don't make Mage more OP".

### 4.2 Spells

Each attack flips a page and fires one Staff-style `StatProjectiles` bolt (33 studs). Spell order kept per slot on the server.
- Fire: this bolt burns (100% burn chance on it: 6/s for 3 s, scaled by Elemental damage).
- Frost: slows 25% for 1.5 s (bosses half). Medusa stays the main slow at 35%.
- Spark: chains lightning at 40%, always (ignores the every-5th counter). With Mage's +1 Lightning target, 2 enemies; Tier III adds `chainExtra=1` in `CharacterStats.chainTargets`.

Per-shot fields go on the shot table; `CombatEffectsService` already reads `d.burn`, `d.slow`, `d.slowStrength`, `d.slowFor`, `d.lightning`. Spark's "always chains" needs one small branch. Pierce, Bounce and Two Straws work like on the Staff. The new hit colours (fire orange, frost blue, lightning violet outlines) show each spell.

Tier IV: `C.Legendary['44']={move='Meteor',every=6,factor=1,radius=8,delay=.35}`, Mjolnir's Thunder code path with fire visuals: 8-stud blast for 100%, everything hit starts burning.

### 4.3 Migration

A saved Mage + Excalibur starter already falls back to the Magic Staff through the invalid-starter reset (ownership kept). Revert the 5-weapon Mage allowance in `WeaponTypeTests` when the Spellbook lands.

## 5. Wave 50 Nightmare (note only)

No change planned. Watch the maps with ranged mobs (Beach Cove Rock-Throwing Crab, Desert Basin Bow Skeleton, Frozen Pass Ice Elf, Volcanic Crater Ash Shaman) at wave 40+: enemy shots per second, the server projectile budget, deaths by source in `RunAnalytics`. If one map's late deaths are mostly projectiles, lower its ranged mob share before touching HP. Note the 2026-10-10 aim-line change (line fades before release) already makes shots harder to dodge. Blink has no invulnerability, so a Mage can't blink through a projectile wall (intended).

## 6. Art assets

Stylized low-poly painterly, chunky silhouettes, soft bevels, warm wood, muted gray metal. Both new weapons are Legendary, not Godly: grounded real objects.

| Asset | Kind | Notes |
|---|---|---|
| Sniper Rifle | New 3D model | Bolt-action, long barrel, wood stock, chunky scope with one bright lens face, ~5.5 studs. Root at grip, `Muzzle` attachment. Tiers: bigger scope (II), muzzle brake + bipod (III), gold trim (IV). Check `WeaponSpacing` so the barrel never clips the avatar. |
| Spellbook | New 3D model | Leather grimoire, brass corners and clasp, ~2.2 studs wide. 3 page parts for the flip, one rune plane on the open page recoloured per spell. Tiers: plain (I), clasp + ribbons (II), glowing cover runes (III), gilded edges + Legendary glow (IV). |
| Weapon icons x2 | 512 px renders | Same setup as existing weapon icons |
| Sniper laser + tracer | Beam textures | Laser red-orange; tracer white core, gold edge |
| Spell bolts | VFX recolours | Staff orb in 3 colours |
| Meteor Page | VFX | Pandora / rocket explosion + falling rock |
| Blink | VFX | Violet rune ring at start and end (0.3 s), dash ghosts tinted violet |
| Blink button icon | UI | Same frame as DASH |
| Turret pack-up | Animation only | No new model |
| 8 item icons | 512 px | Existing item icon style |
| Sounds | Audio | Sniper crack + echo, aim tick, blink whoosh, turret pack clank |

Minimum new 3D models: 2.

## 7. Files to change

| Feature | Files |
|---|---|
| Abilities + Blink | new `combat/ClassAbilities.luau`, `combat/ClassAbilityService.luau`, `combat/ClassAbilityTests.luau`; `RogueliteMeta.server.luau`, `RogueliteCombat.client.luau`, `RogueliteCombat.server.luau` (HoldFireUntil), `ui/RunSetupUI.luau`, `audio/RogueliteSounds.client.luau`, `RunAnalytics.luau`, `default.project.json`, `CHARACTER_STATS.md`; `MovementGuard.server.luau` only if Play shows a snap-back |
| Turrets | `HandymanTurret.luau`, `HandymanTurretService.server.luau`, `HandymanTurret.client.luau`, `ShopService.luau`, `ShopCatalog.luau`, `TurretTests.luau`, `HANDYMAN_TURRET.md` |
| Sniper | `WeaponCatalog.luau`, `CharacterStats.luau` (usesStat, StraightGuns, boss bonus), `TargetGrid.luau`, new `SniperShots.luau`, new `SniperVisuals.luau`, `RogueliteCombat.server.luau` (route, snapshot hp/elite), `CombatEffectsService.luau`, `LegendaryMoves.luau` + `LegendaryVisuals.luau` (Mark), `ShotBatch.luau`, template install, icons, Armory showcase, Journal, `WEAPON_BALANCE.md` |
| Items | `ShopCatalog.luau` (8 items, tags, `needs`), `ui/ShopUI.luau`, `ShopTests.luau`, `SHOP_GAMEPLAY_READINESS.md`, `PASSIVE_ITEM_MASTER_LIST.md` |
| Spellbook | `WeaponCatalog.luau`, `RogueliteCombat.server.luau` (spell index, shot fields), `CharacterStats.luau` (chainExtra), `CombatEffectsService.luau` (Spark always chains), `LegendaryMoves.luau` (Meteor), `ProjectileStyleVisuals.luau`, `WeaponMotion.luau` or `SpecialWeaponVisuals.luau` (page flip), template, icons, Journal |

## 8. Tests

- ClassAbilityTests (pure): gate cases, 0.3 s grace, landings 18 -> 12 -> 6 -> refused, 2 studs short of walls, refused use costs no cooldown.
- TurretTests: turret items + Scrap Magnet offered to Handyman only; left-behind at 20 studs; max 2 moving; 1.5 s between moves; new spots lead toward the move direction.
- TargetGridTests: `toughest()` order (boss, elite, most HP, farther); 6-stud minimum.
- Sniper line (pure): lane hit test, 100% / 40% falloff with bosses always full, line ends at the wall.
- WeaponBalanceTests: ids 43 and 44 at all tiers with exact rarity power; Legendary pool counts and shop share.
- RosterBalanceTests: Gunner with Sniper; Mage with Spellbook; six-Sniper boss row as a watch line.
- ShopTests: `needs='Melee'` gating, prices and caps for the 8 items.
- Play (the user's): Blink no snap-back + VFX on teammates' screens; turrets following on phone and PC; Sniper readability in a 4-player crowd.

## 9. Build order

1. Turrets: Handyman only + follow (small, reuses code, the friend's direct ask). Start Sniper and Spellbook concept art in parallel.
2. Ability framework + Mage Blink.
3. Tier III items (data, `needs` flag, icons).
4. Sniper Rifle (catalog, SniperShots, targeting, visuals, model).
5. Spellbook.
6. Play-test round: Mage strength, six-Sniper build, melee Tier III pick rates, late Nightmare deaths by source.

## 10. Open questions for the dev

1. Sniper rarity: Legendary (Tier IV move; Legendary share of shop weapon offers at wave 20 goes 18.3% -> 21.9% with the Spellbook) or Epic (no Tier IV move; 19.7%)?
2. Blink cost: keep the 0.5 s hold-fire, or drop it and use a 10 s cooldown?
3. Turret follow: leapfrog (up to 2 moving while the rest fire) or the whole set packs up and moves together?
4. Gunner and Juggler: no ability this round, or add Combat Roll / Double Jump now?
5. Items: all 8 Tier III, or the 5 melee ones first (Cane, Steel-Toe Boots, Whetstone, Knucklebone, Apron)?
