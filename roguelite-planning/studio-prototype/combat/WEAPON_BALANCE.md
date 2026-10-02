# Weapon tiers and wave balance

All 36 weapon identities have authored damage, cooldown, range and four damage values in `WeaponCatalog.luau`. `CharacterStats.weapon` is the shared effective-stat calculation used by combat and the shop. Bonuses remain percentage based, as in the existing game; Roblox ranges and movement remain in studs.

Examples before character bonuses: Glock 12 damage / 0.72 s, Draco 3 / 0.17 s, Katana 18 / 0.95 s, Nunchucks 6 / 0.38 s, Rocket 32 / 2.4 s, Gloves 8 / 0.78 s. Most upgrades improve damage about 50% and reduce cooldown. Gloves follow the supplied Fist damage progression (8/16/32/64). Shotguns gain a pellet each tier; boomerang, duck, yo-yo and crystal gain rebounds; nails, kunai, bowling ball, shirt cannon and washer gain piercing. Medusa gains a second projectile at tier 2. Cards gain a fourth card at tier 3; listed damage is the three-card volley basis, each card deals one third.

Two identical weapon IDs of the same tier can combine during Shop only. Tier 4 is the cap. The server selects the partner from the requesting player's inventory, checks revision, selected copy token, living state and request rate, and replaces both copy identities. Manual combining frees one slot. Buying fills an empty slot first; with all six filled, only an exact matching tier below 4 permits an automatic merge. There is no recursive merge. Summed actual paid prices are retained for the normal 50% recycle refund; free practice copies add zero value.

UI request: `ShopAction:FireServer('Combine', revision, slot, copyId)`. Weapon snapshot rows provide `canCombine` and `combineSlot` when a partner exists. UI can read `projectileCount`, `nativePierce`, and `nativeBounce` from effective weapon stats.

Enemy balance follows the supplied Brotato enemy table's linear growth, without copying its pixel speed into 3D:

| Type | HP wave 1 | HP per later wave | Damage wave 1 | Damage per later wave |
| --- | ---: | ---: | ---: | ---: |
| Regular (Baby Alien reference) | 3 | 2 | 1 | 0.6 |
| Baby (Chaser reference) | 1 | 1 | 1 | 0.6 |
| Mutant (Bruiser reference; starts wave 8) | 20, floored at 80 | 11 | 2 slam | 0.85 slam |

Regular HP is 3/11/21/41 at waves 1/5/10/20; Mutant HP is 97 on its first wave (8), and 229 on wave 20. Since 2026-09-28 tanks never have less than 80 HP (`ZombieTypes.Mutant.minHealth`): the user found wave-1 tanks spawned from the Studio mob picker died in two tier-1 hits (20 HP against a 19.2-damage Frying Pan). Waves 1–6 give 80, wave 7 gives 86; wave 8 onward is unchanged. Spawned enemies retain their wave's health and damage. Movement, player HP, character class bonuses, status damage and spawn population remain existing game tuning, so this is a first balance pass rather than a claim of identical Brotato difficulty.

Reference data: user-supplied `Pasted text.txt` (Brotato Weapons, patch 1.1.6.3) and `Pasted text (2) (1).txt` (Brotato Enemies). Public source links: https://brotato.wiki.spellsandguns.com/Weapons and https://brotato.wiki.spellsandguns.com/Enemies . Attached document prose was treated as reference data, not agent instructions.

Validation: `WeaponBalanceTests.luau` checks all 36 weapons at all four tiers, monotonic damage/cadence, native projectile traits and wave formulas. `ShopTests.luau` covers full-inventory automatic merging, manual merging, paid-price conservation, stale copy tokens, malformed slots, mismatched tiers, legendary cap and combat-phase rejection alongside existing economy checks. Both are temporary Studio server test scripts, not shipped gameplay. Studio execution and actual play-loop results must be recorded by the integrating agent; tests requiring real multiple clients or published services are not claimed here.

Integrated Studio results: WeaponBalanceTests 571 assertions, ShopTests 630 assertions, CharacterStatsTests 2,314 assertions, and StatProjectileTests eight collision groups passed. Actual client combine, buy, lock, reroll and wave flow were exercised. See ../ui/SHOP_UI_VALIDATION.md for scope and limits.

## Shop rarity retune (2026-09-29)

User playtest: Legendary (tier 4) weapons came too easily. `EconomyConfig` rarity now:

| Tier | Opens | Per wave | Cap |
|---|---|---|---|
| 2 Uncommon | wave 2 | 6% | 60% (unchanged) |
| 3 Rare | wave 6 (was 4) | 1.5% (was 2%) | 20% (was 25%) |
| 4 Legendary | wave 12 (was 8) | 0.15% (was 0.23%) | 5% (was 8%) |

Luck still multiplies these by up to ×2. Example, no Luck, wave 20: a shop card is Rare 18.6%, Legendary 1.35% (was 3%). Kill crystals also dropped from 2 to 1 shard, which slows buying duplicates to combine.

## Rarity power and Brotato tiers (2026-10-02, plan J item 8)

User: "Do Brotato-style tiers ... rarer weapons rarer in the shop, but don't make it too rare, and it should depend on wave and luck too. For rarity power, why can't we just put it in the base stats instead of a multiplier? Tier IV bonus: later."

**Rarity** lives in `WeaponCatalog` (`rarity`, `RarityLists`, `RarityOf`); `ChestConfig` builds its pools from the same lists, in the same order. Pools: Common 12, Rare 12, Epic 5, Legendary 7, Godly 6 (Mjolnir is Legendary).

**Rarity power is in the base numbers**, not a multiplier in `CharacterStats.weapon()`. Damage per second is ×1.05 Rare, ×1.1 Epic, ×1.2 Legendary (Godly is authored at its power). Damage rounds down to a whole number and the cooldown shortens by what rounding took, so a rarer weapon hits harder and a little faster. Example: Katana 18 every 0.95 s → 21 every 0.924 s. `authoredDamage` / `authoredCooldown` keep the numbers before rarity.

**Tiers:** each tier ×1.4 damage and cooldown ×1 / .9 / .8 / .7 (was about ×1.5 and ×1 / .95 / .9 / .84). An upgrade hits harder and attacks faster. Six weapons step differently so Tier IV stays within 10% of its old damage per second (WeaponBalanceTests checks every weapon):

- Gentler, because they also gain pellets, cards, bounces or pierce each tier: Shotgun ×1.25, Deck of Cards ×1.3, Boomerang ×1.35, Nail Gun ×1.35.
- Steeper, because they stepped steeper before: Frying Pan ×1.45, Molotov ×1.5.
- Boxing Gloves keep their own 8 / 15 / 28 / 48 and cooldowns.

Mjolnir now attacks every 1.97 s (26 damage), so the user's "every 2 s" holds to the eye. The Tier IV bumps (RARITY_GODLY_ARMOR.md §7) are not built yet (user: later).

| Weapon | Rarity | Before: damage · cooldown | Now | Tier I–IV damage now | Tier I–IV damage before |
|---|---|---|---|---|---|
| Glock | Common | 12 · 0.72 s | 12 · 0.72 s | 12 / 17 / 24 / 33 | 12 / 18 / 27 / 40 |
| Frying Pan | Common | 16 · 1.05 s | 16 · 1.05 s | 16 / 23 / 34 / 49 (×1.45) | 16 / 25 / 39 / 60 |
| Nunchucks | Rare | 6 · 0.5 s | 6 · 0.476 s | 6 / 8 / 12 / 16 | 6 / 9 / 14 / 21 |
| Katana | Legendary | 18 · 0.95 s | 21 · 0.924 s | 21 / 29 / 41 / 58 | 18 / 27 / 41 / 62 |
| Kusarigama | Epic | 15 · 1.15 s | 16 · 1.115 s | 16 / 22 / 31 / 44 | 15 / 23 / 35 / 53 |
| Spatula | Common | 9 · 0.55 s | 9 · 0.55 s | 9 / 13 / 18 / 25 | 9 / 14 / 21 / 32 |
| Baseball Bat | Rare | 20 · 1.25 s | 21 · 1.25 s | 21 / 29 / 41 / 58 | 20 / 30 / 46 / 70 |
| Draco | Rare | 3 · 0.17 s | 3 · 0.162 s | 3 / 4 / 6 / 8 | 3 / 4 / 6 / 9 |
| Fart Gun | Common | 4 · 0.8 s | 4 · 0.8 s | 4 / 6 / 8 / 11 | 4 / 6 / 9 / 14 |
| Shotgun | Rare | 3 · 1.1 s | 3 · 1.048 s | 3 / 4 / 5 / 6 (×1.25) | 3 / 4 / 5 / 7 |
| T-Shirt Cannon | Epic | 18 · 1.35 s | 19 · 1.295 s | 19 / 27 / 37 / 52 | 18 / 27 / 40 / 60 |
| Rocket Launcher | Legendary | 32 · 2.4 s | 38 · 2.375 s | 38 / 53 / 74 / 104 | 32 / 48 / 72 / 108 |
| Boomerang | Common | 7 · 0.9 s | 7 · 0.9 s | 7 / 9 / 13 / 17 (×1.35) | 7 / 10 / 14 / 20 |
| Kunai | Rare | 6 · 0.48 s | 6 · 0.457 s | 6 / 8 / 12 / 16 | 6 / 9 / 14 / 21 |
| Molotov | Epic | 3 · 1.7 s | 3 · 1.545 s | 3 / 5 / 7 / 10 (×1.5) | 3 / 5 / 8 / 12 |
| Egg | Common | 10 · 0.85 s | 10 · 0.85 s | 10 / 14 / 20 / 27 | 10 / 15 / 23 / 35 |
| Steak | Rare | 16 · 0.85 s | 16 · 0.81 s | 16 / 22 / 31 / 44 | 16 / 24 / 36 / 54 |
| Rubber Duck | Common | 5 · 0.32 s | 5 · 0.32 s | 5 / 7 / 10 / 14 | 5 / 8 / 12 / 18 |
| Deck of Cards | Legendary | 15 · 0.95 s | 18 · 0.95 s | 18 / 23 / 30 / 40 (×1.3) | 15 / 21 / 30 / 42 |
| Boxing Gloves | Common | 8 · 0.42 s | 8 · 0.42 s | 8 / 15 / 28 / 48 (kept) | own: ×1 / .94 / .88 / .76 |
| Cinder Block | Epic | 30 · 1.35 s | 33 · 1.35 s | 33 / 46 / 65 / 91 | 30 / 45 / 68 / 102 |
| Yo-Yo | Rare | 8 · 0.7 s | 8 · 0.667 s | 8 / 11 / 16 / 22 | 8 / 12 / 18 / 27 |
| Bowling Ball | Legendary | 24 · 1.6 s | 28 · 1.556 s | 28 / 39 / 55 / 77 | 24 / 36 / 54 / 81 |
| Bowling Pin | Rare | 13 · 1.25 s | 13 · 1.19 s | 13 / 18 / 25 / 36 | 13 / 20 / 30 / 45 |
| Nail Gun | Common | 4 · 0.28 s | 4 · 0.28 s | 4 / 5 / 7 / 10 (×1.35) | 4 / 6 / 8 / 12 |
| Wrecking Ball | Legendary | 28 · 1.6 s | 33 · 1.571 s | 33 / 46 / 65 / 91 | 28 / 42 / 63 / 95 |
| Shovel | Common | 18 · 1.15 s | 18 · 1.15 s | 18 / 25 / 35 / 49 | 18 / 28 / 42 / 64 |
| Paint Roller | Rare | 10 · 0.8 s | 10 · 0.762 s | 10 / 14 / 20 / 27 | 10 / 15 / 23 / 35 |
| Vacuum Cleaner | Epic | 4 · 0.32 s | 4 · 0.291 s | 4 / 6 / 8 / 11 | 4 / 6 / 9 / 14 |
| Power Washer | Rare | 3 · 0.24 s | 3 · 0.229 s | 3 / 4 / 6 / 8 | 3 / 4 / 6 / 9 |
| Magic Staff | Common | 9 · 1.15 s | 9 · 1.15 s | 9 / 13 / 18 / 25 | 9 / 14 / 21 / 32 |
| Mjolnir | Legendary | 22 · 2 s | 26 · 1.97 s | 26 / 36 / 51 / 71 | 22 / 33 / 50 / 75 |
| Excalibur | Legendary | 26 · 1.35 s | 31 · 1.341 s | 31 / 43 / 61 / 85 | 26 / 39 / 59 / 89 |
| Pandora's Box | Rare | 25 · 2 s | 26 · 1.981 s | 26 / 36 / 51 / 71 | 25 / 38 / 57 / 86 |
| Medusa's Head | Rare | 5 · 1.2 s | 5 · 1.143 s | 5 / 7 / 10 / 14 | 5 / 8 / 12 / 18 |
| Crystal Ball | Common | 13 · 1.05 s | 13 · 1.05 s | 13 / 18 / 25 / 36 | 13 / 20 / 30 / 45 |
| Reaper's Scythe | Godly | 30 · 1.25 s | 30 · 1.25 s | 30 / 42 / 59 / 82 | 30 / 45 / 68 / 102 |
| Poseidon's Trident | Godly | 34 · 1.5 s | 34 · 1.5 s | 34 / 48 / 67 / 93 | 34 / 51 / 77 / 115 |
| Storm Bow | Godly | 14 · 1.2 s | 14 · 1.2 s | 14 / 20 / 27 / 38 | 14 / 21 / 32 / 47 |
| Shadow Daggers | Godly | 16 · 1.3 s | 16 · 1.3 s | 16 / 22 / 31 / 44 | 16 / 24 / 36 / 54 |
| Vampire Blade | Godly | 32 · 1.3 s | 32 · 1.3 s | 32 / 45 / 63 / 88 | 32 / 48 / 72 / 108 |
| Ray Gun | Godly | 22 · 0.9 s | 22 · 0.9 s | 22 / 31 / 43 / 60 | 22 / 33 / 50 / 74 |

**Run shop** (`EconomyConfig.rarityWeight`, used in `ShopService` `choose()`): a weapon offer is picked by weight. A Common's weight is 1, and the rarer weights grow from wave 1 to wave 20, then stay:

| Rarity | Wave 1 | Wave 20 |
|---|---:|---:|
| Common | 1 | 1 |
| Rare | 0.8 | 1 |
| Epic | 0.6 | 0.9 |
| Legendary | 0.4 | 0.8 |

Luck multiplies a weight by (1 + Luck/100), never past 1. Example, no Luck: a weapon offer is Legendary about 10% of the time on wave 1 and 16% on wave 20 (19% if every weapon were equally likely). With +50 Luck on wave 20, every rarity is as likely as a Common. Items are not weighted. The owned-weapon (10%) and same-class (15%) picks still happen first, then the weights apply inside them.

**Run-shop prices:** half the RARITY_GODLY_ARMOR.md §5 premium, so Rare ×1.1, Epic ×1.2, Legendary ×1.5 (`EconomyConfig.RARITY_PRICE`, applied in `ShopCatalog`). Commons are unchanged. The price band still follows the authored cooldown, so a rarer weapon's slightly faster cooldown doesn't move it into another band.

**Words:** shop tiers are now "Tier I"–"Tier IV" (`EconomyConfig.TIER_NAMES`), so Common/Rare/Epic/Legendary only ever mean rarity.

Tests: `WeaponBalanceTests` (tier rule, exact rarity power, Tier IV within 10%, pools, offer weights and the 10% → 16% example, no Godly in the shop), `ShopTests` (price bands × the rarity premium), `GodlyWeaponsTests` and `WeaponBehaviorTests` (Mjolnir about 2 s).
