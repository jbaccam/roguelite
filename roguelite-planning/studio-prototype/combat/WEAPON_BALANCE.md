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
| Mutant (Bruiser reference; starts wave 8) | 20 | 11 | 2 slam | 0.85 slam |

Regular HP is 3/11/21/41 at waves 1/5/10/20; Mutant HP is 97 on its first wave (8), and 229 on wave 20. Spawned enemies retain their wave's health and damage. Movement, player HP, character class bonuses, status damage and spawn population remain existing game tuning, so this is a first balance pass rather than a claim of identical Brotato difficulty.

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
