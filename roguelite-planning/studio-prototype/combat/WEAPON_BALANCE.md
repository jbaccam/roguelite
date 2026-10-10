# Weapon tiers and wave balance

All 36 weapon identities have authored damage, cooldown, range and four damage values in `WeaponCatalog.luau`. `CharacterStats.weapon` is the shared effective-stat calculation used by combat and the shop. Bonuses remain percentage based, as in the existing game; Roblox ranges and movement remain in studs.

Examples before character bonuses (first pass; current numbers in [Melee vs ranged](#melee-vs-ranged-2026-10-03)): Glock 12 damage / 0.72 s, Draco 3 / 0.17 s, Katana 18 / 0.95 s, Nunchucks 6 / 0.38 s, Rocket 32 / 2.4 s, Gloves 8 / 0.78 s. Most upgrades improve damage about 50% and reduce cooldown. Gloves follow the supplied Fist damage progression (8/16/32/64). Shotguns gain a pellet each tier; boomerang, duck, yo-yo and crystal gain rebounds; nails, kunai, bowling ball, shirt cannon and washer gain piercing. Medusa gains a second projectile at tier 2. Cards gain a fourth card at tier 3; listed damage is the three-card volley basis, each card deals one third.

Two identical weapon IDs of the same tier can combine during Shop only. Tier 4 is the cap. The server selects the partner from the requesting player's inventory, checks revision, selected copy token, living state and request rate, and replaces both copy identities. Manual combining frees one slot. Buying fills an empty slot first; with all six filled, only an exact matching tier below 4 permits an automatic merge. There is no recursive merge. Summed actual paid prices are retained for the normal 50% recycle refund; free practice copies add zero value.

UI request: `ShopAction:FireServer('Combine', revision, slot, copyId)`. Weapon snapshot rows provide `canCombine` and `combineSlot` when a partner exists. UI can read `projectileCount`, `nativePierce`, and `nativeBounce` from effective weapon stats.

Current enemy scaling is documented in [Enemy scaling � October 5](ENEMY_SCALING.md). Final native HP retains Brotato-style pacing: Regular 3 + 2 per wave, Baby 1 + 1, Tank max(50, 20 + 11). Wave-20 HP is 41 / 20 / 229. All three starting classes one-shot ordinary mobs through wave 5; a strong Tier IV Gunner one-shots wave-20 regulars and takes two tank hits on Normal after the 0.60 HP difficulty multiplier ([full-roster Normal audit](NORMAL_BALANCE.md)). Imported enemies use matching role-based growth. Damage grows more gently alongside larger swarms; regular speed stays constant through wave 20. The earlier proposed HP inflation was rejected and is not the final implementation.

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
- 2026-10-10 (the table below is older): Baseball Bat and Boxing Gloves swapped rarities, so Brawler starts with a Common. Bat, now Common: 20 · 1.25 s, 20 / 28 / 39 / 55. Gloves, now Rare: 8 · 0.4 s (Rare power takes the cooldown from 0.42), still 8 / 15 / 28 / 48.

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

## Melee vs ranged (2026-10-03)

Play-test: "ranged weapons are dominating and there's no pressure when you have a ton of ranged weapons, mobs never get close"; "increase range on most melee weapons"; "bhopping melee weapons won't hit at max height of jump"; "add weapon with slowing effect".

**Rules** (`WeaponCatalog` profiles; tier steps and rarity power are unchanged, so every tier moves by the same share):

- **Ranged:** range about −22% and cooldown ×1.13 (about −12% attacks a second).
  - Godly ranged (Storm Bow, Ray Gun) lose range only. Their ~24 DPS is their identity (`GodlyWeaponsTests`).
  - Rubber Duck is unchanged: at 12 studs it already works at melee distance.
  - Medusa keeps its rate: it is the slowing weapon (below).
  - Nail Gun stays under 0.3 s, so `ShopCatalog` keeps its fast-weapon price band. It loses more range instead (−25%).
- **Melee:** reach about +20% (+15–25%).
  - The five weakest also hit 10–20% harder: Frying Pan, Nunchucks, Kusarigama, Shovel, Paint Roller. Before this they did 12.6–15.7 damage a second, under a Common Glock's 16.7.
  - Godly melee gain reach only.

Tier I numbers before character bonuses. The cooldown includes rarity power. DPS is single target, one copy.

| Weapon | Kind | Range (studs) | Cooldown (s) | Damage | DPS |
|---|---|---|---|---|---|
| Glock | Ranged | 45 → **35** | 0.72 → **0.82** | 12 | 16.7 → 14.6 |
| Frying Pan | Melee | 6 → **7.5** | 1.05 | 16 → **18** | 15.2 → 17.1 |
| Nunchucks | Melee | 6 → **7.5** | 0.48 | 6 → **7** | 12.6 → 14.7 |
| Katana | Melee | 11 → **13** | 0.92 | 21 | 22.7 |
| Kusarigama | Melee | 12 → **14** | 1.115 → 1.107 | 16 → **18** | 14.3 → 16.3 |
| Spatula | Melee | 6 → **7.5** | 0.55 | 9 | 16.4 |
| Baseball Bat | Melee | 8 → **9.5** | 1.25 | 21 | 16.8 |
| Draco | Ranged | 42 → **33** | 0.16 → **0.18** | 3 | 18.5 → 16.6 |
| Fart Gun | Ranged | 28 → **22** | 0.80 → **0.90** | 4 + poison | 5.0 → 4.4 |
| Shotgun | Ranged | 24 → **19** | 1.05 → **1.19** | 3 × 5 pellets | 14.3 → 12.6 |
| T-Shirt Cannon | Ranged | 40 → **31** | 1.29 → **1.49** | 19 | 14.7 → 12.8 |
| Rocket Launcher | Ranged | 70 → **55** | 2.38 → **2.67** | 38 | 16.0 → 14.2 |
| Boomerang | Ranged | 35 → **27** | 0.90 → **1.02** | 7 | 7.8 → 6.9 |
| Kunai | Ranged | 38 → **30** | 0.46 → **0.52** | 6 | 13.1 → 11.5 |
| Molotov | Ranged | 38 → **30** | 1.54 → **1.73** | 3 + burn | 1.9 → 1.7 |
| Egg | Ranged | 32 → **25** | 0.85 → **0.96** | 10 | 11.8 → 10.4 |
| Steak | Melee | 6 → **7.5** | 0.81 | 16 | 19.8 |
| Rubber Duck | Ranged | 12 | 0.32 | 5 | 15.6 |
| Deck of Cards | Ranged | 42 → **33** | 0.95 → **1.08** | 18 | 18.9 → 16.7 |
| Boxing Gloves | Melee | 6.5 → **7.5** | 0.42 | 8 | 19.0 |
| Cinder Block | Melee | 7 → **8.5** | 1.35 | 33 | 24.4 |
| Yo-Yo | Ranged | 28 → **22** | 0.67 → **0.76** | 8 | 12.0 → 10.5 |
| Bowling Ball | Ranged | 35 → **27** | 1.56 → **1.75** | 28 | 18.0 → 16.0 |
| Bowling Pin | Ranged | 28 → **22** | 1.19 → **1.35** | 13 | 10.9 → 9.6 |
| Nail Gun | Ranged | 40 → **30** | 0.28 → **0.295** | 4 | 14.3 → 13.6 |
| Wrecking Ball | Melee | 12 → **14** | 1.57 | 33 | 21.0 |
| Shovel | Melee | 8 → **9.5** | 1.15 | 18 → **20** | 15.7 → 17.4 |
| Paint Roller | Melee | 9 → **10.5** | 0.76 | 10 → **12** | 13.1 → 15.7 |
| Vacuum Cleaner | Ranged | 20 → **16** | 0.29 → **0.33** | 4 | 13.7 → 12.2 |
| Power Washer | Ranged | 30 → **23** | 0.23 → **0.26** | 3 | 13.1 → 11.7 |
| Magic Staff | Ranged | 45 → **35** | 1.15 → **1.30** | 9 | 7.8 → 6.9 |
| Mjolnir | Melee | 8 → **9.5** | 1.97 | 26 | 13.2 |
| Excalibur | Melee | 8.5 → **10** | 1.34 | 31 | 23.1 |
| Pandora's Box | Ranged | 50 → **39** | 1.98 → **2.23** | 26 | 13.1 → 11.7 |
| Medusa's Head | Ranged | 38 → **30** | 1.14 | 5 + slow | 4.4 |
| Crystal Ball | Ranged | 48 → **37** | 1.05 → **1.19** | 13 | 12.4 → 10.9 |
| Reaper's Scythe | Melee | 10 → **12** | 1.25 | 30 | 24.0 |
| Poseidon's Trident | Melee | 9 → **10.5** | 1.50 | 34 | 22.7 |
| Storm Bow | Ranged | 50 → **39** | 1.20 | 14 × 2 on one enemy | 23.3 |
| Shadow Daggers | Melee | 10 → **12** | 1.30 | 16 × 2 on one enemy | 24.6 |
| Vampire Blade | Melee | 9 → **10.5** | 1.30 | 32 | 24.6 |
| Ray Gun | Ranged | 48 → **37** | 0.90 | 22 | 24.4 |

**Worked example.** A zombie walks at a Tier I Glock at 12 studs/s.
- Before, it took 45 / 12 = 3.75 s to cross the Glock's range, taking 3.75 × 16.7 ≈ 63 damage on the way.
- Now it takes 35 / 12 ≈ 2.9 s and takes 2.9 × 14.6 ≈ 43 damage: about a third less before it reaches you.
- A Tier I Frying Pan now hits 18 (was 16) every 1.05 s out to 7.5 studs (was 6). That reach covers (7.5 / 6)² ≈ 1.56 times the ground.

**Melee from a jump** (`RogueliteCombat.server`, `TargetGrid.distance`). Melee reach is now flat within a full jump above or below: the jump height plus 4 studs of body.
- Example: JumpHeight 9.5 at gravity 150 gives a 13.5-stud allowance. From a jump's peak, a zombie 5 studs out counts as 5 (it was 10.7, past every reach).
- Melee also swings from the body where the player's own screen has it (`CharacterService.seen`). A bunny-hopping player was ~7 studs behind on the server.
- That lead is capped at 1.5 studs + 0.3 s of the body's speed, so standing still can't stretch reach.
- Chain weapons (Nunchucks, Kusarigama, Wrecking Ball) now pull their swing in for a close target, so the longer reach leaves no gap beside the player.

**Floating ring** (`WeaponMotion.SlotLayout`). The weapons float on a wider ring: 6.2 studs plus 0.36 per extra weapon (was 4.2 + 0.24), with slots at 0 / 70 / 140 / 210 / 280 / 320° (was every 60°). Slot order is the same.
- Example: 4 weapons sit 7.28 studs out, 8.4 studs apart (was 4.92 and 4.9).
- Melee reach is measured from the player's centre, not the slot, so the ring doesn't change it.

**The slowing weapon: Medusa's Head** (Rare, Mage). It always had a 100% slow on hit, but nobody noticed it. The slow was the default 25% for 2 s, and nothing showed it.
- It now slows 35% for 2 s (`WeaponCatalog.SlowById`; bosses take half), and its card says "Slows enemies 35% for 2 s."
- Slowed enemies get an ice-blue tint, a flat frost patch at their feet, and a frost ring when the slow lands (`HitFeedbackVisuals`).
- Example: a zombie walking 12 studs/s crawls at 7.8 for 2 s after each hit.
- It drops from chests (Rare pool) and daily deals. The run shop offers it to everyone: since db71be9 (same day) run shops offer every non-Godly weapon, owned or not.
- Ice Cube now slows the same way (35% for 2 s, bosses half) on 15% of hits from any weapon (`SlowStrength` 10 on top of the base 25%; [SHOP_GAMEPLAY_READINESS.md](SHOP_GAMEPLAY_READINESS.md)).

Tests: `WeaponBalanceTests` (every weapon's range and rate against its old numbers, the Glock and Pan examples, Medusa's slow and card text; the Tier IV check scales the five buffed melee weapons' old Tier IV by their damage change), `MeleeSweepTests` (jump allowance), `WeaponFollowTests` (ring), `WeaponBehaviorTests` (chain pull-in). Not yet run in Studio.
