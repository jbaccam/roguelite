# Roster audit: items, shop offers and level-ups (economy facts for the weapon-type redesign)

Date: 2026-10-09. Read-only audit of `roguelite-planning/studio-prototype/`. Paths are relative to that folder. Line numbers are from the working tree on this date. No code, Studio or git state was changed. No Studio play test was run. Probabilities in section 2 come from a Python Monte Carlo copy of the shop roll (method at the end), not from live play.

Companion docs: `plans/2026-10-09-roster-audit-weapons.md` (weapons/classes/starters), `ROSTER_WEAPONS_CLASSES_MASTER_GUIDE.md` sections 6-7.

---

## 0. Findings that change the plan

1. **No direct Melee, Ranged or Elemental item exists.** The only family item is Toolbelt (+6 Utility Power, `combat/ShopCatalog.luau:93`). Toolbelt is offered to every build, even one with no utility weapon or turret, because `UtilityPower` is not a gated weapon stat (`combat/CharacterStats.luau:201`, `ShopCatalog.luau:112-120`).
2. **Two Straws and Bouncy Ball are effectively unobtainable.** Tier IV starts at wave 12 at 0.15% per offer and reaches 1.35% at wave 20 (`combat/EconomyConfig.luau:48`). Simulated chance of being offered at all in a run, without rerolls: Two Straws 4.2%, Bouncy Ball 4.4%. Sharp Pencil (Tier III): 11% by the shop before wave 11, 47% by wave 20.
3. **Every preference rule is class-based and has to be redesigned.**
   - Items: a 5% roll filters to a fixed per-class tag list (`combat/ShopService.luau:158-162,192-199`).
   - Weapons: 10% same weapon, 15% (+early bonus) a weapon sharing a class with a carried weapon (`ShopService.luau:166-175,189-191`).
   - Structures: Handyman, or anyone carrying a Handyman-class weapon, gets 15% (+early bonus) structure-only item rolls (`combat/HandymanTurret.luau:213-226`, `ShopService.luau:284`).
   - The item pool is built from the exact rolled tier first (`ShopService.luau:257-270`), so a Tier I family item can never appear on a Tier II roll. From wave 11 on, 60% of item rolls are Tier II or higher.
4. **Bouncy Ball says "Shots ... bounce", but guns never bounce** (`CharacterStats.luau:200,205`; `combat/StatProjectiles.luau:131`). Bowling Ball is listed as using Pierce and Bounce (`CharacterStats.luau:219`) but returns before either is read (`combat/SpecialWeapons.luau:105`). Pencil and Bouncy Ball are offered to a Bowling Ball build and do nothing.
5. **Battery Pack's first copy does nothing for Crystal Ball or Mjolnir.** The chain count is `max(ChainCount, 1 if lightning weapon)`, not a sum (`combat/CombatEffectsService.luau:185`). The Mage's own `ChainCount=1` is dead on those two weapons for the same reason.
6. **Duck and Washer cards claim bounce and pierce.** Their `trait` values are `'bounce'` and `'pierce'` (`combat/WeaponCatalog.luau:35,47`). So the Armory says "Bounces between enemies." / "Shots pierce through enemies." (`ui/ArmoryUI.luau:51-54,204`), and the shop trait line shows "Bounce: 1-3" / "Pierce: 1-2" at higher tiers (`ui/ShopUI.luau:379`). Neither spray nor stream reads them.
7. **Streams get all the generic upgrades, but no crowd scaling.** They use damage, attack speed, crit, range, procs and life steal. They use no projectile, pierce or bounce stats (`CharacterStats.luau:218`), and Area Size doesn't touch their cone or width. Hot Sauce does nothing for them unless lightning or burn spread is involved.
8. **Today's own-class package, measured on a focused build:**

   | Class | Package | What it includes |
   |---|---|---|
   | Brawler, Mage, Thrower | about x1.25-1.28 | 2-weapon bonus + class fit |
   | Juggler | x1.32 | Attack speed + class fit |
   | Handyman | x1.46-1.52 | Cooldown, Utility Power + class fit |
   | Gunner | up to x2.3 single-target | Class fit + 4-weapon `ProjectileCount+1` |

   A +10% specialty plus a 4-copy set worth about +15% reproduces the Brawler/Mage totals (section 5).
9. **"Utility" kind label clashes with Utility Power.** Six non-Utility-Power items have kind `'Utility'`, and the card prints it: "Utility · Health" on Bandage Roll (`ui/ShopUI.luau:589`). Meanwhile the real Utility Power item, Toolbelt, prints "Item · Structure".
10. **Stale icon comment.** `ShopCatalog.luau:71-73` says Banana, Cushion, Penny, Soup, Skates, Detector and Gummies use level-up art. Their asset ids differ from `LevelUpCatalog.IconIds` (`combat/LevelUpCatalog.luau:52-61`). Only Toolbelt reuses level-up art (`133538769433103` = UtilityPower), and Scrap Magnet reuses the Fridge Magnet image.

---

## 1. Item table

### 1a. Mechanics

All rows are from `combat/ShopCatalog.luau` unless noted.
- **Kind** defaults to `Item`; `cap` defaults to `EconomyConfig.MAX_ITEM_COPIES` = 5 (`EconomyConfig.luau:5`).
- **Pref tags** are the shop preference tags (`ShopCatalog.luau:96-107`). The card shows the first one next to the kind (`ShopUI.luau:589`).
- **Icon** is the `rbxassetid` number.
- **Percent** fields multiply the stat after flat bonuses (`CharacterStats.luau:175`).
- Handyman gains: every positive Damage bonus is halved, and every Utility Power bonus is x1.25 (`CharacterStats.luau:84,165-169`).

| Line | id | Name | Kind | T | Base | Cap | modifiers | percent | Pref tags | Icon |
|---|---|---|---|---|---|---|---|---|---|---|
| 25 | `protein` | Protein Shake | Item | 1 | 14 | 5 | `Damage=8` | | Damage | 83194367813542 |
| 26 | `cheese` | Emergency Cheese | Item | 1 | 9 | 5 | `MaxHP=5` | | Health | 90250262957329 |
| 27 | `potato` | Support Potato | Item | 1 | 20 | 5 | `MaxHP=8` | `PickupRadius=10` | Health | 83830925182356 |
| 28 | `shoes` | Sport Shoes | Utility | 1 | 18 | 5 | | `MoveSpeed=6` | Mobility | 107662510054482 |
| 29 | `headband` | Sweaty Headband | Item | 1 | 18 | 5 | `AttackSpeed=8` | | AttackSpeed | 135907983584957 |
| 30 | `glasses` | Large Glasses | Item | 1 | 16 | 5 | `AttackRange=15` | | Range | 96052817991093 |
| 31 | `potlid` | Pot Lid | Item | 1 | 14 | 5 | `Armor=2` | | Armor | 95875975195945 |
| 32 | `sock` | Lucky Sock | Item | 1 | 18 | 5 | `Luck=10` | | Luck | 107984529281974 |
| 33 | `magnet` | Fridge Magnet | Utility | 1 | 12 | 5 | | `PickupRadius=25` | Economy | 79860440384816 |
| 34 | `coupons` | Grandma's Coupons | Utility | 2 | 35 | 5 | `ShopDiscount=5` | | Economy | 88520618235310 |
| 35 | `ketchup` | Support Ketchup | Item | 1 | 22 | 5 | `ExplosionDamage=15` | | Explosion | 131244011688920 |
| 36 | `hotsauce` | Hot Sauce | Item | 2 | 32 | 5 | `AreaSize=15` | | Explosion | 119160485990749 |
| 41 | `marshmallow` | Microwaved Marshmallow | Item | 1 | 20 | 5 | `BurnChance=5,BurnDamage=20` | | Burn | 126733361101751 |
| 42 | `peas` | Freezer-Burned Peas | Item | 1 | 16 | 5 | `SlowChance=5` | `SlowDuration=25` | Slow | 83565201991578 |
| 43 | `stinkysock` | Stinky Sock | Item | 1 | 19 | 5 | `PoisonChance=5,PoisonDamage=20` | | Poison | 92934200477984 |
| 44 | `energy` | Energy Drink | Item | 2 | 31 | 5 | `AttackSpeed=15,MaxHP=-3` | | AttackSpeed | 136079535507930 |
| 45 | `helmet` | Safety Helmet | Item | 2 | 34 | 5 | `Armor=3` | `MoveSpeed=-3` | Armor, Health | 73191633018679 |
| 46 | `broken` | Broken Glasses | Item | 2 | 38 | 5 | `CritChance=6,AttackRange=-10` | | Crit | 118717032933610 |
| 47 | `ballchain` | Literal Ball and Chain | Item | 2 | 39 | 5 | `Damage=15` | `MoveSpeed=-5` | Damage, Melee | 116486378397548 |
| 48 | `backpack` | Backpack of Rocks | Item | 2 | 36 | 5 | `MaxHP=12` | `MoveSpeed=-4` | Health | 72326129404039 |
| 49 | `straws` | Two Straws | Item | 4 | 145 | 1 | `ProjectileCount=1` | | Projectile | 103855013199609 |
| 50 | `bouncy` | Bouncy Ball | Item | 4 | 130 | 1 | `Bounce=1` | | Bounce, Projectile | 72472678515992 |
| 51 | `pencil` | Sharp Pencil | Item | 3 | 65 | 1 | `Pierce=1` | | Pierce, Projectile | 108647088361466 |
| 52 | `antlers` | Tinfoil Antlers | Item | 3 | 68 | 2 | `ChainBonus=1` | | Lightning | 90516946916091 |
| 54 | `mitt` | Grandma's Oven Mitt | Item | 3 | 62 | 1 | `BurnChance=10,BurnSpread=1` | | Burn | 140473103768001 |
| 55 | `bubble` | Bubble Wrap Vest | Item | 4 | 145 | 1 | `FirstHitBlock=1` | | Armor | 136728170000690 |
| 56 | `bandage` | Bandage Roll | Utility | 2 | 32 | 5 | `Regeneration=1` | | Health | 86023323568594 |
| 57 | `fang` | Vampire Fang | Item | 3 | 64 | 5 | `LifeSteal=3` | | Health, Damage | 93247265104136 |
| 58 | `lighter` | Lighter | Item | 2 | 42 | 5 | `BurnChance=15` | | Burn | 131511231922178 |
| 61 | `ice` | Ice Cube | Item | 2 | 37 | 5 | `SlowChance=15,SlowStrength=10` | | Slow | 107793797321617 |
| 62 | `battery` | Battery Pack | Item | 3 | 72 | 2 | `ChainCount=1` | | Lightning | 77920495517577 |
| 63 | `toxic` | Toxic Barrel | Item | 2 | 45 | 5 | `PoisonChance=15` | | Poison | 70439693967934 |
| 64 | `teeth` | Tooth Fairy's Collection | Item | 2 | 46 | 5 | `CritDamage=15` | | Crit | 138418894713581 |
| 65 | `nightmare` | Bottled Nightmare | Item | 2 | 33 | 5 | `Damage=12,MaxHP=-3` | | Damage | 131703819690946 |
| 66 | `mask` | Cracked Burial Mask | Item | 3 | 70 | 5 | `Armor=2,ContactReduction=10` | | Armor | 79342628709582 |
| 67 | `alien` | Alien Battery | Item | 2 | 38 | 5 | `AttackSpeed=6,ChainDamage=15` | | AttackSpeed | 96598846243561 |
| 70 | `crown` | Bone Crown | Item | 2 | 44 | 5 | `Damage=5,BossDamage=20` | | Damage, Boss | 121286333601812 |
| 74 | `banana` | Banana Peel | Item | 1 | 18 | 5 | `Dodge=5` | | Mobility | 91220324140044 |
| 75 | `cushion` | Couch Cushion | Item | 1 | 17 | 5 | `Armor=1,MaxHP=6` | | Armor, Health | 134119315378177 |
| 76 | `penny` | Lucky Penny | Item | 1 | 17 | 5 | `Luck=6,Dodge=3` | | Luck | 84866645691857 |
| 77 | `soup` | Chicken Soup | Item | 2 | 34 | 5 | `MaxHP=6,Recovery=15` | | Health | 134653604976810 |
| 78 | `skates` | Roller Skates | Utility | 2 | 38 | 5 | `Dodge=3` | `MoveSpeed=10` | Mobility | 84335919314680 |
| 79 | `detector` | Metal Detector | Utility | 2 | 36 | 5 | `Luck=8` | `PickupRadius=20` | Luck, Economy | 135461885570276 |
| 80 | `gummies` | Vitamin Gummies | Item | 3 | 66 | 5 | `Regeneration=2,MaxHP=10` | | Health | 96244325205305 |
| 92 | `scrap_magnet` | Scrap Magnet | Item (structure) | 2 | 40 | 5 | none (turret builder) | | Structure | 79860440384816 |
| 93 | `toolbelt` | Toolbelt | Item (structure) | 1 | 18 | 5 | `UtilityPower=6` | | Structure | 133538769433103 |
| HT 39 | `turret_nail` | Nail Turret | Turret | 1 | 24 | 10 | none (1 turret/copy) | | Structure | 100505469530773 |
| HT 40 | `turret_twin` | Twin Nailer | Turret | 2 | 46 | 10 | none | | Structure | 110375220181503 |
| HT 41 | `turret_quad` | Quad Nailer | Turret | 3 | 85 | 10 | none | | Structure | 112292832566551 |
| HT 42 | `turret_gatling` | Gatling Rig | Turret | 4 | 150 | 10 | none | | Structure | 78790900806318 |

HT = `combat/HandymanTurret.luau`. Turret rows are added at `ShopCatalog.luau:85-90`.
- **Cap:** `MAX_OWNED=10` total turrets (`HandymanTurret.luau:49,62`).
- **Damage:** 4 / 6 / 8 / 11 every 0.8 / 0.72 / 0.64 / 0.56 s, with native pierce 0 / 1 / 1 / 2 (`:28-30,81-91`).
- **Stats turrets ignore:** Damage, Melee, Ranged, Attack speed, CDR, Crit, Life steal, Knockback, Range and projectile stats (`:71`).
- **Stats turrets use:** Two Straws (+1 nail) and Pierce (`combat/HandymanTurretService.server.luau:348-352`), plus procs, Boss damage and gear power.
- **Handyman:** 20% off every structure item (`:203,208`).
- **Weapon offers:** they are also `ShopCatalog` entries (`:6-18`): every non-Godly weapon x 4 tiers. Price band by `TIER_PRICE_BANDS` x rarity (`EconomyConfig.luau:12,29`). Placeholder icon key `'pan'`/`'staff'`; the UI uses `WeaponIcons` instead (`ShopUI.luau:264`).

### 1b. Card text vs real behavior

| id | Description (exact source text) | Verdict |
|---|---|---|
| `protein` | All your weapons deal 8% more damage. | OK. Handyman gets 4%; turrets ignore Damage |
| `cheese` | +5 max health. | OK |
| `potato` | +8 max health, and you grab crystals from 10% farther away. | OK |
| `shoes` | You move 6% faster. | OK |
| `headband` | All your weapons attack 8% faster. | OK. Turrets ignore it |
| `glasses` | All your weapons reach 15% farther. | OK. Range scales reach and travel (`CharacterStats.luau:243-244`) |
| `potlid` | +2 armor: every hit you take does a bit less damage. | OK |
| `sock` | +10 luck: better shop offers and more heart drops. | **Minor:** Luck also raises level-up card tiers (`LevelUpCatalog.luau:34-36`) |
| `magnet` | Grab crystals from 25% farther away. | OK |
| `coupons` | New shop offers cost 5% less. Locked prices stay the same. | OK (`ShopService.luau:154-157`). Rerolls are not discounted |
| `ketchup` | Explosive weapons deal 15% more damage. | **Minor:** "explosive" here means Rocket Launcher, Pandora's Box **and Molotov** (`WeaponCatalog.luau:226`, `CharacterStats.luau:207`) |
| `hotsauce` | Explosions, fire and gas puddles and lightning chains reach 15% wider. | OK. It also widens burn-spread radius (`CombatEffectsService.luau:160`) and Legendary/Godly radii, but the shop only offers it to blast, zone and lightning weapons (`CharacterStats.luau:209-214`) |
| `marshmallow` | 5% of your hits set enemies on fire, and all your burns deal 20% more damage. | OK. The chance uses `max(stat, weapon native)`, so it adds nothing to Molotov (`CombatEffectsService.luau:177`) |
| `peas` | 5% of your hits slow enemies, and all your slows last 25% longer. | OK |
| `stinkysock` | 5% of your hits poison enemies, and all your poison deals 20% more damage. | OK |
| `energy` | All your weapons attack 15% faster, but you have 3 less max health. | OK |
| `helmet` | +3 armor, but you move 3% slower. | OK |
| `broken` | +6% chance of a critical hit, but your weapons reach 10% less far. | OK. Turrets never crit |
| `ballchain` | All your weapons deal 15% more damage, but you move 5% slower. | OK. Tagged `Melee` for shop preference, but the effect is general damage |
| `backpack` | +12 max health, but you move 4% slower. | OK |
| `straws` | +1 shot or throw every attack: guns, staffs, cards and throwing weapons. Not melee, boomerangs or sprays. | **Incomplete:** also rockets, Pandora, Molotov, Fart Gun, Storm Bow and turrets. Excludes every returning throw, Mjolnir and Trident included (`CharacterStats.luau:217-221`) |
| `bouncy` | Shots and throws bounce to 1 more enemy (60% damage). Not melee, explosives or sprays. | **WRONG.** Guns never bounce (Glock, Draco, Fart Gun, Shotgun, T-Shirt, Nail Gun, turrets). Neither do zone throws or the Bowling Ball. Thrown bounces deal 65%, not 60% (`SpecialWeapons.luau:109`) |
| `pencil` | Shots and throws go through 1 more enemy (70% damage). Not melee, explosives or sprays. | **Partly wrong:** the Fart Gun gas cloud and the Bowling Ball get nothing (`CharacterStats.luau:219`, `SpecialWeapons.luau:105`) |
| `antlers` | Your lightning chains jump to 1 more enemy. Needs lightning: a lightning weapon, Battery Pack or Mage. | OK |
| `mitt` | 10% of your hits set enemies on fire, and a burning enemy that dies passes its fire to 1 enemy nearby. | OK |
| `bubble` | Blocks the first hit you take each wave. | OK. **Dead** with the Spartan 4-piece, because `FirstHitBlock` caps at 1 (`CharacterStats.luau:68,300`) and the shop doesn't filter it |
| `bandage` | Heal 1 HP every second. | OK. Card label reads "Utility · Health" |
| `fang` | Heal 3% of the damage you deal (up to your healing cap each second). | OK. Turrets don't leech |
| `lighter` | 15% of your hits set enemies on fire: 6 damage a second for 3 s. Any weapon. | OK (base numbers) |
| `ice` | 15% of your hits slow enemies 35% for 2 s, like Medusa's Head (bosses half as much). Any weapon. | OK |
| `battery` | Every 5th hit zaps 1 more enemy nearby with lightning for 40% damage. Any weapon. | **Misleading:** gives Crystal Ball and Mjolnir nothing until a 2nd copy (`CombatEffectsService.luau:185`). "Every 5th hit" counts all your weapons together (`:184`) |
| `toxic` | 15% of your hits poison enemies: 3 damage a second for 4 s, stacking 3 times. Any weapon. | OK |
| `teeth` | Critical hits hit harder: x1.5 becomes x1.65. | OK |
| `nightmare` | All your weapons deal 12% more damage, but you have 3 less max health. | OK |
| `mask` | +2 armor, and enemy hits deal 10% less damage. | OK. It applies on every damage path (`combat/CharacterService.luau:256-281`) |
| `alien` | All your weapons attack 6% faster, and your lightning chains hit 15% harder. | OK |
| `crown` | All your weapons deal 5% more damage, and 20% more to bosses. | OK. Bosses and elites (`CombatEffectsService.luau:112`) |
| `banana` | 5% of enemy hits miss you completely. | OK |
| `cushion` | +1 armor and +6 max health. | OK |
| `penny` | +6 luck (better shop offers, more heart drops), and 3% of enemy hits miss you. | **Minor:** same Luck note as `sock` |
| `soup` | +6 max health, and all your healing heals 15% more. | OK |
| `skates` | You move 10% faster, and 3% of enemy hits miss you. | OK |
| `detector` | +8 luck, and you grab crystals from 20% farther away. | OK |
| `gummies` | Heal 2 HP every second, and +10 max health. | OK |
| `scrap_magnet` | Each 40 crystals you pick up in a wave builds a temporary Nail Turret near you, up to 3 a wave per copy. They go when the wave ends. | Matches the `HandymanTurret.luau:193-197` constants. Service not traced |
| `toolbelt` | +6% Utility Power: utility weapons and turrets deal more damage. | OK. Handyman gets 7.5. **Offered to builds with no utility weapon or turret** |
| `turret_nail` | One more turret, placed near you at every wave start. It shoots 4 damage every 0.8 s within 25 studs. Utility Power raises its damage. You can own 10. | OK (generated, `HandymanTurret.luau:101-106`) |
| `turret_twin` | ...shoots 6 damage every 0.72 s within 25 studs, through 1 enemy... | OK |
| `turret_quad` | ...shoots 8 damage every 0.64 s within 25 studs, through 1 enemy... | OK |
| `turret_gatling` | ...shoots 3 nails of 3.7 damage every 0.56 s within 25 studs, through 2 enemies... | OK |

### 1c. Other player-facing text that misleads about items

| Where | Text | Problem |
|---|---|---|
| `WeaponCatalog.luau:35,184,214`; `ArmoryUI.luau:51-54,204` | Rubber Duck: "Bounces between enemies." | The spray never bounces (`SpecialWeapons.luau:41-58`) |
| same, `:47` | Power Washer: "Shots pierce through enemies." | The stream hits everything in its cone; `nativePierce` is never read (`combat/UtilityWeapons.luau:43-50`) |
| `ShopUI.luau:379` | Duck "Bounce: 1/2/3" at Tier II-IV; Washer "Pierce: 1/2" at Tier II-IV | Derived from those traits (`CharacterStats.luau:247-249`). Has no effect |
| `ShopUI.luau:589` | "Utility · Health" (Bandage), "Utility · Mobility" (Shoes, Skates), "Utility · Economy" (Magnet, Coupons), "Utility · Luck" (Detector) | Reads like Utility Power. Toolbelt itself reads "Item · Structure" |
| `LevelUpCatalog.luau:16` | Melee Damage: "Strengthens your close-range attacks." | Rubber Duck (12 studs) is close range but uses Ranged Damage (`CharacterStats.luau:231`) |
| `LevelUpCatalog.luau:17` | Ranged Damage: "Strengthens shots and thrown weapons." | Also explosives, sprays, streams and Mjolnir/Trident throws (`combat/RogueliteCombat.server.luau:446-447`) |
| `CharacterStats.luau:31,44,69` (stat help) | Dodge "contact attack"; ProjectileCount "maximum nine shotgun pellets"; ContactReduction "zombie contact" | Dodge and resistance apply on every damage path (`CharacterService.luau:258-278`). A Tier IV shotgun reaches 8 + 4 = 12 pellets (`RogueliteCombat.server.luau:226`). Internal/admin text only |

---

## 2. Availability

### 2a. How an offer is chosen

| Step | Rule | Source |
|---|---|---|
| Offers per shop | 4; initial roll at run start, refreshed after every wave | `EconomyConfig.luau:5`; `ShopService.luau:337,588-589` |
| Weapon or item | Waves 1-2: slots 1-2 weapons, 3-4 items. Waves 3-5: slot 1 weapon, slots 2-4 35% weapon. Wave 6+: each slot 35% weapon | `EconomyConfig.luau:71-75` |
| Tier roll | One draw per offer against IV, III, II chances. II from wave 2 (+6%/wave, cap 60%). III from wave 6 (+1.5%/wave, cap 20%). IV from wave 12 (+0.15%/wave, cap 5%). All x(1+Luck/100) | `EconomyConfig.luau:45-61` |
| Pool | Entries of **exactly** the rolled tier; falls to a lower tier only if that tier is empty. Items must be under their copy cap, "usable" (`worksWith`: needs a carried weapon that uses the stat) and turret-offerable. Excludes ids already in this shop and in the previous shop | `ShopService.luau:254-273,233-236,464,588` |
| Structure favour | Handyman, or anyone carrying a Handyman-class weapon (24-29, 05, 11, 20): 15% + early bonus of item rolls use only structure items of that tier | `HandymanTurret.luau:213-226`; `ShopService.luau:284` |
| Item class preference | 5%: filter to items with a tag in the class list. Brawler {Health, Armor, Melee}; Gunner {Projectile, Pierce, Crit, AttackSpeed}; Thrower {Projectile, Bounce, Pierce}; Juggler {Mobility, Bounce, Crit}; Handyman {Explosion, Economy, Armor}; Mage {Burn, Slow, Poison, Lightning}. Otherwise uniform | `ShopService.luau:158-162,192-199,213` |
| Weapon preference | 10%: an owned weapon id (merge bait). Else 15% + `classBonus`: weapons sharing **any class** (home + `AlsoClasses`) with a carried weapon. Then rarity weight Common 1, Rare 0.8-1, Epic 0.6-0.9, Legendary 0.4-0.8 over waves 1-20, x Luck | `ShopService.luau:166-191,202-212`; `EconomyConfig.luau:22-27` |
| Early bonus | `classBonus(wave)` = 0.15, 0.12, 0.09, 0.06, 0.03 for waves 1-5; 0 after | `EconomyConfig.luau:76` |
| Price | `floor((base + wave + base x wave x 0.10) x modifier)`. Modifier = 1 + ShopPricePercent - ShopDiscount (0.2-3), x0.8 on structures for Handyman | `EconomyConfig.luau:31-33,43`; `ShopService.luau:149-152` |
| Locks | Toggle. Locked offers survive rerolls and the next wave, and keep their old price (inflation dodge) | `ShopService.luau:729,154-157,465,589` |
| Rerolls | `floor(wave x .75) + max(1, floor(wave x .4)) x (n+1)`, resetting each wave. Buying all 4 refills them for free. Level-up rerolls are Robux/saved only | `EconomyConfig.luau:34-37`; `ShopService.luau:759-765,767-776,709-713` |
| Caps | 16 distinct items; per-item cap; 10 turrets | `EconomyConfig.luau:5`; `ShopService.luau:751-753` |

Price and reroll curve examples:

| Base | Wave 2 | Wave 5 | Wave 8 | Wave 11 | Wave 15 | Wave 20 |
|---|---|---|---|---|---|---|
| 14 (Protein) | 18 | 26 | 33 | 40 | 50 | 62 |
| 16 | 21 | 29 | 36 | 44 | 55 | 68 |
| 33 (Nightmare) | 41 | 54 | 67 | 80 | 97 | 119 |
| 65 (Pencil) | 80 | 102 | 125 | 147 | 177 | 215 |
| 90 | 110 | 140 | 170 | 200 | 240 | 290 |
| 145 (Straws) | 176 | 222 | 269 | 315 | 377 | 455 |
| Reroll 1st/2nd/3rd | 2/3/4 | 5/7/9 | 9/12/15 | 12/16/20 | 17/23/29 | 23/31/39 |
| Income from the wave just cleared (est.) | ~51 | ~78 | ~108 | ~144 | ~173 | ~214 |

Income assumptions:
- 85% of scheduled arrivals are collected as 1-shard crystals (`combat/WaveTimeline.luau:7-12`, `EconomyConfig.luau:11`).
- The wave reward is `12 + 3 x wave`.
- Start with 60 shards.
- Weapons compete for the same shards.

### 2b. Tier odds per offer (no Luck)

| Shop at wave | I | II | III | IV |
|---|---|---|---|---|
| 1 | 100 | 0 | 0 | 0 |
| 3 | 88 | 12 | 0 | 0 |
| 5 | 76 | 24 | 0 | 0 |
| 6 | 70 | 28.5 | 1.5 | 0 |
| 8 | 58 | 37.5 | 4.5 | 0 |
| 11 | 40 | 51 | 9 | 0 |
| 12 | 40 | 49.5 | 10.35 | 0.15 |
| 15 | 40 | 45 | 14.4 | 0.6 |
| 20 | 40 | 40 | 18.65 | 1.35 |

"Shop at wave N" means the shop rolled while `S.wave = N`, which is the shop before wave N starts (`ShopService.luau:580-589`).

### 2c. What can appear per band

| Band (shop at wave) | Tiers that can roll | Item pool |
|---|---|---|
| 1-5 | I, II (from wave 2, 6-24%) | Tier I: 16 passive + Toolbelt + Nail Turret. Tier II: 18 passive + Scrap Magnet + Twin Nailer |
| 6-11 | I, II, III (1.5-9%) | + Tier III: Pencil, Antlers, Mitt, Fang, Battery, Mask, Gummies, Quad Nailer |
| 12-20 | I-IV (IV 0.15-1.35%) | + Tier IV: Two Straws, Bouncy Ball, Bubble Wrap, Gatling Rig |

Conditionally offered items are shown only to a build that uses them (`ShopService.luau:233-236`):
- Ketchup: Blast weapon.
- Hot Sauce: blast, zone or lightning weapon, ChainCount or BurnSpread.
- Antlers: lightning source.
- Pencil, Straws, Bouncy Ball: per `usesStat`.

### 2d. Chance per shop to see at least one item of each family (simulated, 4 initial offers, no rerolls, no Luck, not structure-favoured)

Build assumed: carries a Kunai, so Pierce, Straws and Bouncy are usable; no explosive or lightning weapon.

| Family (members) | Shops 1-5 | Shops 6-11 | Shops 12-20 |
|---|---|---|---|
| General damage (Protein, Ball and Chain, Nightmare, Crown) | 13.7% | 23.1% | 22.3% |
| Melee damage | 0 | 0 | 0 |
| Ranged damage | 0 | 0 | 0 |
| Elemental damage | 0 | 0 | 0 |
| Utility Power (Toolbelt) | 10.2% | 8.6% | 6.1% |
| Attack speed (Headband, Energy, Alien) | 12.6% | 18.4% | 17.3% |
| Crit (Broken Glasses, Teeth) | 2.5% | 10.7% | 11.7% |
| Projectile mods (Pencil, Straws, Bouncy) | 0 | 1.9% | 6.6% |
| Healing (Bandage, Soup, Fang, Gummies) | 2.5% | 14.2% | 22.0% |
| Status/procs (Marshmallow, Peas, Stinky Sock, Lighter, Ice, Toxic, Alien, Mitt, Battery) | 32.5% | 42.9% | 44.9% |

The current 5% class filter moves these by a point or two. One reroll roughly doubles a per-shop number.

Chance of ever being offered across the shops at waves 2-11 and 2-20, with no rerolls:

| Item | Waves 2-11 | Waves 2-20 |
|---|---|---|
| Protein, Toolbelt, Headband | 61% | 78% |
| Broken Glasses | 33% | 62% |
| Sharp Pencil, Vampire Fang | 11% | 47-48% |
| Two Straws / Bouncy Ball | 0% | 4.2% / 4.4% |

### 2e. What the redesign must replace

- `wanted` (`ShopService.luau:158-162`) still lists Thrower and keys on class, not on what is equipped. Brawler's `Melee` tag matches only Ball and Chain, which gives general damage. Gunner, Thrower and Juggler prefer Projectile, Pierce and Bounce items that sit at Tier III-IV, but preference is applied inside the rolled tier, so it almost never fires for them.
- `sameClassPool` (`ShopService.luau:166-175`) and `Turret.favoured` (`HandymanTurret.luau:214-221`) read `w.classes`. With one home class per weapon and separate weapon types, both should read equipped weapon types or attack families, counting copies.

---

## 3. Level-ups

`LevelUpCatalog.luau:8-23`. Each pick adds a flat bonus to the stat (`ShopService.luau:721`, merged in `ShopService.luau:291`). Handyman gains apply (`CharacterStats.luau:165-169`).

| Line | id | Name | I / II / III / IV | Stat effect | Icon id | Legacy key |
|---|---|---|---|---|---|---|
| 8 | MaxHP | Vitality | 8/12/16/24 | Max health | 87748663271804 | heart |
| 9 | Damage | Damage | 5/8/12/18 % | Every weapon hit, plus burn/poison ticks (`CharacterStats.luau:231`; `CombatEffectsService.luau:176`) | 105663077535579 | sword |
| 10 | AttackSpeed | Attack Speed | 5/8/12/18 % | Cooldown (`CharacterStats.luau:238-239`) | 118215254503921 | speed |
| 11 | Armor | Armor | 1/2/3/4 | `incoming` (`:186`) | 80556274645944 | shield |
| 12 | Dodge | Dodge | 3/5/7/10 % | `CharacterService.luau:273` | 99124374960499 | wing |
| 13 | Regeneration | Regeneration | .5/1/1.5/2 HP/s | | 86810106921196 | cross |
| 14 | LifeSteal | Life Steal | 1/2/3/4 % | `CharacterService.luau:239-243` | 94341050485414 | heart |
| 15 | CritChance | Critical Chance | 3/5/7/10 % | `CombatEffectsService.luau:108` | 129045264697854 | spark |
| 16 | MeleeDamage | Melee Damage | 8/12/18/25 % | `kind=='Melee'` weapons | **95614914114816** | sword |
| 17 | RangedDamage | Ranged Damage | 8/12/18/25 % | Every non-melee weapon, plus Mjolnir/Trident throws | **79016661829505** | arrows |
| 18 | ElementalDamage | Elemental Damage | 8/12/18/25 % | Elemental weapons (`WeaponCatalog.luau:266`), plus all burn/poison ticks | **104925573900277** | spark |
| 19 | UtilityPower | Utility Power | 8/12/18/25 % | Utility weapons (`WeaponCatalog.luau:267`) and turrets | 133538769433103 (= Toolbelt) | cross |
| 20 | MoveSpeed | Movement Speed | .5/1/1.5/2 studs/s | Flat walk speed | 117216104224040 | wing |
| 21 | PickupRadius | Pickup Radius | 1/1.5/2/3 studs | | 133081616364253 | spark |
| 22 | Luck | Luck | 3/5/7/10 | Shop tiers, weapon rarity weight, level-up tiers, hearts | 136231704380505 | spark |
| 23 | AttackRange | Attack Range | 5/8/12/18 % | Reach and travel | 72729393219444 | arrows |

**How cards are drawn:**
- 4 cards are drawn uniformly from all 16 stats that are not capped or banished (`LevelUpCatalog.luau:24-30,39-50`).
- There is no class, weapon or family weighting, and no "usable" filter. An all-ranged build still sees Melee Damage.

**Card tier:** each card rolls its own tier (`:34-37`).

| Level | IV | III | II | I |
|---|---|---|---|---|
| 2 | 1% | 4% | 18% | 77% |
| 5 | 2.5% | 10% | 18% | 69.5% |
| 10 | 5% | 20% | 18% | 57% |
| 15 | 7.5% | 20.5% | 27.5% | 44.5% |
| 20 | 8% | 20% | 37% | 35% |

The expected value of a family card is +9.3% at level 2, +11.6% at level 10 and +12.8% at level 20.

**Icon reuse for new items:**
- Melee `95614914114816` ("Knee of Justice"), Ranged `79016661829505` ("Finger Cannon") and Elemental `104925573900277` ("Pocket Weather") are ready to reuse (`STAT_UPGRADE_ART_DIRECTION.md:19-21`). Toolbelt already shares the UtilityPower art ("Certified Duct Tape", `:22`). The skill tree reuses this art too (`combat/SkillTreeConfig.luau:11-20`; its AttackSpeed icon differs: 104227388119878).
- `C.icon` first reads an `Icon_<id>` attribute on the Studio module (`LevelUpCatalog.luau:62-65`). Check Studio for overrides before copying ids; not checked here.

---

## 4. Stream support: Rubber Duck (17), Power Washer (29), Vacuum (28)

How each one deals damage:

| | Rubber Duck | Power Washer | Vacuum |
|---|---|---|---|
| Attack | 3 pulses per cycle. Cycle is `max(0.78, 3 x cooldown)`. Each pulse is a full own hit, scaled so DPS = damage / cooldown (`combat/SpecialMotion.luau:4-8`; `SpecialWeapons.luau:41-58,192-203`) | Stream ticks every 0.12 s (`UtilityWeapons.luau:41-50`). Each tick is an own hit at a proc share of at most 1 | Same as Washer |
| Kind / flags | Ranged, elemental | Ranged, utility | Ranged, utility |

| Upgrade | Duck | Washer | Vacuum | Notes |
|---|---|---|---|---|
| Damage (Protein, Ball and Chain, Nightmare, Crown; level-up) | Yes | Yes | Yes | `CharacterStats.luau:231` |
| Ranged Damage (level-up) | Yes | Yes | Yes | All three are `kind='Ranged'` |
| Melee Damage | No | No | No | |
| Elemental Damage (level-up) | Yes | No direct | No direct | Burn/poison ticks from any weapon still scale |
| Utility Power (Toolbelt; level-up) | No | Yes | Yes | |
| Attack speed (Headband, Energy, Alien; level-up) | Yes | Yes | Yes | Duck pulse count stops rising at about +23% speed (0.78 s floor; already reached at Tier III-IV), but damage per pulse keeps scaling. Washer proc share caps at 1 at about +38%, Vacuum at about +173%. DPS keeps scaling for all three |
| Crit chance / damage (Broken Glasses, Teeth; level-up) | Yes | Yes | Yes | Pulses and ticks are own hits (`CombatEffectsService.luau:94,108`) |
| Attack Range (Large Glasses; level-up) | Yes | Yes | Yes | Duck cone length (`SpecialWeapons.luau:199`); stream length; Vacuum width = 0.48 x length (`UtilityWeapons.luau:31-34`). Broken Glasses' -10% hurts |
| Burn/poison/slow chance (Marshmallow, Peas, Stinky Sock, Lighter, Ice, Toxic, Mitt) | Yes | Yes | Yes | Duck rolls at full chance each pulse; streams roll at share x chance, so the per-second rate matches a normal weapon |
| Battery Pack (ChainCount) | Yes | Yes | Yes | The hit counter adds the share (`CombatEffectsService.luau:184`) |
| Antlers, Alien chain damage | Only with a chain source | Only with a chain source | Only with a chain source | |
| Vampire Fang / Life Steal | Yes | Yes | Yes | |
| Bone Crown boss part | Yes | Yes | Yes | |
| Knockback (no item) | Yes | No | No | Stream ticks are secondary (`CombatEffectsService.luau:172`) |
| Two Straws, Sharp Pencil, Bouncy Ball | No | No | No | `CharacterStats.luau:218` |
| Support Ketchup | No | No | No | Not Blast |
| Hot Sauce (Area Size) | No | No | No | Only widens chain/burn-spread radius. Cone and width ignore Area Size |
| Class 2/4 bonuses | Juggler four `Bounce` is wasted | Handyman two CDR 10 and four UP 20 help | Same as Washer | |

**Verdict:** each stream has about 20 working items and 8 working level-up stats. That is enough general support. What they lack is any crowd-scaling item; Projectile, Pierce and Bounce are their gap. The cheapest fix is to let Area Size widen the spray/stream (section 6.6), so Hot Sauce and an Area-type set bonus become meaningful.

---

## 5. Stacking today

### 5a. Every source of weapon damage

These are multiplied together per hit.

| # | Source | How it applies | Where |
|---|---|---|---|
| 1 | Rarity power | Built into base damage: Common x1, Rare x1.05, Epic x1.1, Legendary x1.2 DPS | `WeaponCatalog.luau:84,232-233` |
| 2 | Weapon tier | x1.4 per tier (some weapons x1.25-1.55), cooldown x1/.9/.8/.7 | `WeaponCatalog.luau:90-93,237` |
| 3 | Damage % | Items (Protein 8, Ball and Chain 15, Nightmare 12, Crown 5), level-ups 5-18, skill tree up to 12, Juggler -10. Handyman gains x0.5 | `CharacterStats.luau:231`; `SkillTreeConfig.luau:52,57` |
| 4 | Melee **or** Ranged % | By `kind`. Class buffs (Brawler +20/-15, Gunner +20/-15, Thrower +15/-10, Mage -10 melee), class two (Brawler Melee 15, Thrower Ranged 15), Viking 2-piece Melee 12 (tier-scaled), level-ups 8-25 | `CharacterStats.luau:77-85,231,298` |
| 5 | Elemental % (elemental weapons) | Mage +25 buff and two +15, level-ups. Also scales every burn/poison tick | `:232`; `CombatEffectsService.luau:176-178` |
| 6 | Utility Power % (utility weapons and turrets) | Handyman +15 and four +20 (x1.25 = 25), Toolbelt 6, level-ups | `:233`; `HandymanTurret.luau:85` |
| 7 | Explosion % (Blast) | Ketchup 15 | `:234` |
| 8 | Class fit | Own +15; others 0 / -5 / -10 / -15; best of the weapon's classes | `:97-120,235-236` |
| 9 | Gear power | x(1 + 0.12 x (power - 1)), on every hit. Maps scale enemies by the same curve | `:260-262`; `CombatEffectsService.luau:111` |
| 10 | Boss damage | Crown 20, vs boss/elite | `CombatEffectsService.luau:112` |
| 11 | Crit | 5% base + Gunner 5 + Broken 6 + Samurai 8 + skills 4 + level-ups; x1.5 base + Teeth 15 + Samurai 40 + skills 10 | `:108`; `CharacterStats.luau:28-29,299` |
| 12 | Owl pet mark | +mark% while marked | `CombatEffectsService.luau:114-115` |
| 13 | Cadence (DPS, not per hit) | Attack speed (items, level-ups, skills 6, Monkey pet, Juggler 15 + four 15, Viking rage 25), Gunner +10% non-melee, Handyman two CDR 10 | `CharacterStats.luau:238-239` |
| 14 | Shot count | Gunner/Thrower four `ProjectileCount+1`, Straws, Gunner two Pierce, Thrower +1 Bounce, Juggler four Bounce | `CharacterStats.luau:78-80` |

Status ticks use only 3, 5, burn/poison damage % and 9. Chains use 40% of the hit's own damage x ChainDamage (`CombatEffectsService.luau:191`).

### 5b. Typical totals for a focused build

**Assumptions:**
- 85% crystal pickup gives level 6 after wave 5, level 13 after wave 12, and level 19 after wave 20 (`combat/RunXP.luau:3`).
- On each level-up, the player takes their family stat when it is offered (25%), else Damage (20%). That gives family +12.3 / +32.5 / +51.4 and Damage +6.4 / +16.9 / +27.0.
- Items: Protein after wave 5; 2 Protein + Nightmare after wave 12; 3 Protein + Nightmare + Ball and Chain + Crown after wave 20.
- No skill tree, gear power 1.

**Brawler on own melee weapons:**

| After wave | Melee pool | Damage pool | Class fit | Total x | Same build without class fit and two | Class package |
|---|---|---|---|---|---|---|
| 5 | 20 + 15 + 12 = +47 | +14 | x1.15 | **1.93** | 1.50 | **x1.28** |
| 12 | 20 + 15 + 32.5 = +67.5 | +45 | x1.15 | **2.79** | 2.21 | **x1.26** |
| 20 | 20 + 15 + 51.4 = +86.4 | +83 | x1.15 | **3.92** | 3.14 | **x1.25** |

Weapon tier (up to x2.74), gear power (x1.6 at power 6) and crit (about x1.03 at 5%) multiply on top.

**Own-class package by class, after wave 12** (class fit, two and four only; the buffs stay):

| Class | Package |
|---|---|
| Brawler | x1.26 |
| Mage | x1.26 |
| Thrower | x1.27 |
| Juggler | x1.32 (cadence) plus +1 bounce |
| Handyman | x1.48 (UP 25 + CDR 10 + fit) |
| Gunner | x1.15 fit, then x2 single-target on single-shot guns from four `ProjectileCount+1`, plus two Pierce +1 |

### 5c. Worked example (wave 12, numbers per hit, no crit)

Brawler with 4 Katana (Legendary, 21 damage at Tier I, 29 at Tier II) plus Nunchucks and Bat. That is 6 Brawler copies, so two and four are both active.

- **Today:** 29 x 1.45 (Damage) x 1.675 (Melee 20 + 15 + 32.5) x 1.15 (fit) = **80.9**.
- **Remove fit and two:** 29 x 1.45 x 1.525 = 64.1.
- **Add a specialty x1.10:** 70.5. A Blade 4-copy set worth **x1.148** brings it back to 80.9. At wave 20 (Tier IV, 58 damage) the needed set factor is x1.137.
- **Off-class Glock** (Tier II, 17) in the same Brawler build:
  - Today: 17 x 1.45 x 0.85 (Ranged -15) x 0.85 (fit -15) = **17.8**.
  - Proposed: 17 x 1.45 x 0.85 = **20.9** (+17%; only the family drawback stays).
- **Gunner's own Glock:** today 34.0 per bullet, and two bullets with 4 Gunner weapons. With a x1.10 specialty and no two/four it is 32.5 per bullet, one bullet, until a Gun set or Straws restores the count.

### 5d. Replacement budget (proposal input)

- If specialty is x1.10 on the class's own weapons, a full-set damage bonus of about +15% (6 copies) keeps own-class totals at today's x1.25-1.28 for Brawler, Mage and Thrower-like classes.
- Cumulative set curve that fits: **+4 / +7 / +10 / +13 / +15%** at 2 / 3 / 4 / 5 / 6 copies, as a separate multiplier on set members only. At 4 copies, x1.10 x 1.10 = 1.21; at 6, x1.265.
- A weapon in two damage sets would stack two curves. Either give each weapon only its best damage-set bonus, or make the second tag's bonus non-damage (range, speed, procs).
- Not covered by a % budget:
  - Gunner's `ProjectileCount+1` (x2 single-target).
  - Handyman's Utility Power gain x1.25. It is class identity (`gain`), not class fit, and can stay.
  - Juggler's attack speed.
  - Decide those explicitly, for example a Gun 6-set +1 projectile.

---

## 6. Recommendations (PROPOSALS, not implemented)

### 6.1 Three new family items

These follow the existing curves:
- Level-up family values are 1.5x the Damage values (8 vs 5 ... 25 vs 18). Protein is 8 Damage for 14, so 12 family for 16 keeps that ratio.
- Tier I keeps them reachable from the first shop.

| Proposed id | Working name (matches art) | T | Base | Cap | modifiers | Pref tags | Icon | Card text |
|---|---|---|---|---|---|---|---|---|
| `knee` | Knee of Justice | 1 | 16 | 5 | `MeleeDamage=12` | Melee, Damage | 95614914114816 | Your melee weapons (swings, stabs and punches) deal 12% more damage. |
| `fingercannon` | Finger Cannon | 1 | 16 | 5 | `RangedDamage=12` | Ranged, Projectile | 79016661829505 | Your ranged weapons deal 12% more damage: guns, throws, explosives, sprays and streams. |
| `pocketweather` | Pocket Weather | 1 | 16 | 5 | `ElementalDamage=10` | Elemental, Burn, Poison | 104925573900277 | Elemental weapons deal 10% more damage, and all your burns and poison deal 10% more. |

- **Prices:** 21 / 29 / 36 / 44 / 55 / 68 at shop waves 2 / 5 / 8 / 11 / 15 / 20.
- **Elemental gets 10, not 12,** because it also scales every burn and poison tick from any weapon.
- **Value check, Brawler at wave 12 (Melee +67.5, Damage +45):**
  - Knee: x1.072. Protein: x1.055.
  - So the family item is better for a focused build, and Protein stays better for mixed builds.
  - Five copies give +60 family, versus +40 for five Protein.
- **Gating (recommended):** add usesStat rules so the card shows "Works with" and dead offers stop.

  | Stat | Counts as usable when |
  |---|---|
  | `MeleeDamage` | `kind=='Melee'` |
  | `RangedDamage` | `kind~='Melee'`, or a throwing hybrid (`'31'`, `throwable`) |
  | `ElementalDamage` | `base.elemental`, or the player has BurnChance/PoisonChance > 0 |

  This touches `CharacterStats.luau:201-223` and `ShopCatalog.luau:112-135`.
- **Names are placeholders** taken from the level-up art concepts. The user picks final names.

### 6.2 Toolbelt verdict: keep, as the Utility family item

- Change `UtilityPower` 6 to **10** (Handyman 12.5), and price 18 to **16**. Stays Tier I, cap 5.
- Text: "Utility weapons and turrets deal 10% more damage (+10% Utility Power)."
- Gate it to players carrying a utility weapon or owning a turret item. Today it is offered to everyone; `worksWith` needs the turret count added.
- Keep the structure discount and weighting until the Tool type replaces `Turret.favoured`.
- Utility Power is the turrets' only scaling besides gear and boss damage, so this matters most for turret builds.

### 6.3 Overlapping general-damage items

- **Keep all four** (Protein, Nightmare, Ball and Chain, Crown). They are what make off-class and mixed builds work, which the redesign wants. None is strictly redundant: one is Tier I, the two Tier II items have different drawbacks, and Crown is a boss item.
- **Retag Ball and Chain** from {Damage, Melee} to {Damage}, so Melee preference goes to Knee of Justice.
- **Optional, only if play tests show no Tier II melee option:** Ball and Chain becomes `MeleeDamage=20` with -5% move speed.

### 6.4 Description fixes (exact replacement text)

| Where | Replace with |
|---|---|
| `bouncy` (`ShopCatalog.luau:50`) | Throws, cards, yo-yos and magic bolts bounce to 1 more enemy (60-65% damage). Not guns, melee, explosives, fire or gas throws, bowling balls or sprays. |
| `pencil` (`:51`) | Bullets, throws, cards and magic bolts go through 1 more enemy (70% damage). Not melee, explosives, gas clouds, bowling balls or sprays. |
| `straws` (`:49`) | +1 shot or throw every attack: guns, rockets, staffs, cards, throws and turrets. Not melee, returning throws (Boomerang, Mjolnir) or sprays. |
| `battery` (`:62`) | Every 5th hit you land zaps 1 enemy nearby with lightning for 40% damage. Any weapon. Lightning weapons zap 1 more. *(Needs a code fix: `sourceCount = s.ChainCount + (d.lightning and 1 or 0)` at `CombatEffectsService.luau:185`. Alternative without the code fix: "...Any weapon. Crystal Ball and Mjolnir already chain; for them only a 2nd copy adds a target.")* |
| `ketchup` (`:35`) | Rocket Launcher, Pandora's Box and Molotov deal 15% more damage. |
| `sock` (`:32`) | +10 luck: better shop offers and level-up cards, and more heart drops. |
| `penny` (`:76`) | +6 luck (better shop offers and level-up cards, more heart drops), and 3% of enemy hits miss you. |
| `toolbelt` (`:93`) | (with 6.2) Utility weapons and turrets deal 10% more damage (+10% Utility Power). |
| Duck/Washer traits (`WeaponCatalog.luau:35,47`) | Set `trait` to `''`, or add traits `spray` = "Sprays short bursts of fire in a cone." and `stream` = "Sprays a steady stream that hits everything in its path." Also stop `ShopUI.luau:379` from printing Bounce/Pierce for 17 and 29. Removing the trait changes no damage, because the native values are unused |
| Card kind label (`ShopCatalog.luau:28,33,34,56,78,79`) | Change kind `'Utility'` to `'Item'` (or `'Support'`) so cards don't read "Utility · ..." |
| `LevelUpCatalog.luau:16` | Strengthens melee weapons: swings, stabs and punches. |
| `LevelUpCatalog.luau:17` | Strengthens every non-melee attack: shots, throws, explosives, sprays and streams. |
| `ShopCatalog.luau:71-73` comment | Say only Toolbelt reuses level-up art |

Logic fixes these texts depend on:
- `usesStat('22', Pierce/Bounce)` must return false (`CharacterStats.luau:219`).
- Don't offer Bubble Wrap when `FirstHitBlock >= 1`.

### 6.5 Availability, so a build works before wave 12

1. **Move the projectile mods down a tier:**
   - Sharp Pencil: Tier III 65 to **Tier II, base 42**.
   - Two Straws: Tier IV 145 to **Tier III, base 90**.
   - Bouncy Ball: Tier IV 130 to **Tier III, base 80**.
   - All stay cap 1. Bubble Wrap and Gatling Rig stay Tier IV.
   - Two Straws at Tier III is still weaker access than Gunner's current free 4-weapon `ProjectileCount+1`.
2. **Replace class preference with build preference.**
   - Remove `wanted`.
   - Give 15% of item rolls to items whose tags match the equipped weapons' attack family and weapon types (counted by copies), plus a small class identity list.
   - Let that preferred pool use **tiers at or below the rolled tier**.
   - Do the same for weapon offers: replace `sameClassPool` with "shares a weapon type with an equipped copy", and keep the 10% same-weapon merge roll.
   - Fold `Turret.favoured` into the Tool type.
3. **Simulated effect (per-shop chance of seeing at least one family item, waves 1-5 / 6-11 / 12-20):**

   | Setup | Melee item | Projectile mods (Kunai build) |
   |---|---|---|
   | Today | 0 / 0 / 0 | 0 / 1.9 / 6.6% |
   | 6.1 + 6.5.1 only | 8.7 / 7.3 / 5.2% | 1.2 / 8.4 / 15.1% |
   | + 15% build preference, tier at or below | **32.8 / 38.1 / 37.1%** | higher still |
   | 20% build preference | 39.9 / 46.3 / 45.5% | |

   - 15% is recommended. 20% risks every shop showing the same item.
   - Chance of ever seeing the item by the shop at wave 11 (no rerolls):

     | Item | Today | Proposed |
     |---|---|---|
     | Pencil | 11% | 31.5% |
     | Straws | 0% | 9.8% |
     | Bouncy Ball | 0% | 10.0% |
     | Knee of Justice / Finger Cannon | (new) | about 55% before weighting |

4. **Optional:** let the level-up pool skip family stats no equipped weapon uses, or weight toward used ones. Today a Gunner can be offered Melee Damage with no melee weapon.

### 6.6 Stream support

- Make `AreaSize` scale the Duck cone (dot 0.84, `SpecialWeapons.luau:53`), the Washer width (0.6, `UtilityWeapons.luau:34`) and the Vacuum width factor (0.48). Then extend `usesStat('AreaSize')` to 17, 28 and 29.
- That gives Hot Sauce and any Area-themed set bonus a real effect on sprays.
- With 6.1 and 6.2, each stream also gains a direct family item:
  - Duck: Finger Cannon and Pocket Weather.
  - Washer and Vacuum: Finger Cannon and Toolbelt.
- Set bonuses for the types these belong to (Tool, Elemental, Trick) should use damage, attack speed, range or area, never projectiles, pierce or bounce.

### 6.7 Set and specialty budget

- Use 5d: specialty x1.10, and a damage set curve of +4 / 7 / 10 / 13 / 15% at 2-6 copies, applied to set members.
- Remove class fit and two/four in the same change.
- Decide Gunner's projectile bonus, Juggler's attack speed and Handyman's CDR explicitly instead of carrying them over.

---

## Method and what was not run

- **Shop simulation:** Python Monte Carlo (20,000 shops per wave). It copies `rarityChance`/`rollTier`/`weaponSlot` (`EconomyConfig.luau:45-75`) and the exact-tier pool with in-shop exclusion (`ShopService.luau:257-273`). Not modelled: Luck, previous-shop exclusion and the 5% class filter.
  - Build assumed: carries a Kunai (Pencil, Straws and Bouncy usable; Ketchup, Hot Sauce and Antlers not), and is not structure-favoured.
  - Proposed-preference runs pick the preferred pool before the normal pool.
- **Level and income estimates:** 85% of `WaveTimeline` scheduled arrivals collected, and `RunXP.required`. Boss waves would lower waves 10 and 20.
- **Not run:** no Studio, no Play test, no Luau tests. The Scrap Magnet service and the `Icon_` attribute overrides in Studio were not checked.
