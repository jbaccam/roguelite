# Character stats and Studio practice editor

Implemented September 17, 2026. This is the authoritative prototype stat/class implementation; numeric values remain balance tuning. Non-weapon shop passives and purchases are outside this change.

## Controls

- **Stats / Test [P]** opens the character editor; the Stats tab is also available from Inventory and Shop.
- Select one of six classes. Class selection clears manual overrides. Equip class build fills four slots with a suggested loadout; other weapons still work.
- Edit effective stat values with minus/plus or type a value and press Enter. An asterisk marks an override. Reset stat edits restores class and affinity values. Heal and Test 20 contact damage exercise sustain and defenses.
- Zombie buttons change the shared practice target by 1 or 10, from 0 to 100. Z toggles spawning. Changing target replaces the wave; killed enemies return after three seconds. Zero clears it without stale replacements.
- Changes are server validated, rate limited, living-player and Studio Practice only. Nothing awards persistent currency or wins.

## Stats and weapon integration

CharacterStats.luau now defines 46 visible attributes with defaults, caps, descriptions and calculation rules. Shop Discount and Shop Price Modifier are active in the server-owned economy. Purchased passive/utility items contribute bonuses and penalties before debug overrides and safety caps. See the SHOP / ECONOMY SYSTEM section in the master design document.

CharacterService mirrors effective values as `Stat_<id>` on the avatar and its replicated player-state folder. Humanoid MaxHealth and WalkSpeed receive actual values. Armor/contact reduction/dodge/first-hit blocking modify incoming zombie attacks. An empty StarterCharacterScripts.Health prevents Roblox default regeneration from bypassing our regeneration and Recovery rules. Life steal uses actual damage and a per-second healing cap.

All 36 weapons consume general damage, compatible melee/ranged/elemental/utility damage, critical chance/multiplier, attack cadence and range. Elemental and Utility tags come from WeaponCatalog. Projectiles use server swept collision and bounded travel, size, extra shot counts, unique-target piercing and bounces. Added piercing hits multiply damage by 0.7; bounces multiply it by 0.6. Explosives use area and explosion bonuses; piercing/bounce do not apply to explosions. Lightning never recursively triggers itself. Burn/poison/slow have bounded durations and stacking; burn spreading cannot propagate a second generation. Boss/elite damage requires the relevant enemy attribute. Slow and knockback have reduced boss effects.

Attack range moves melee reach without rescaling the equipped mesh. Authored model sizes, including the katana scale 0.013698526658117772, are preserved. Projectile Size changes projectile collision/visuals, not the equipped weapon model.

Pickup Radius and Luck apply to temporary owner-only health drops. Drop chance is 15% plus Luck/500, capped at 35%; drops heal 8 HP before Recovery. XP, currency, shop odds and purchases remain deferred. Utility Power applies to existing Handyman weapons; there is no new summon system in this change.

## Classes

Every class retains access to every weapon. Six home weapons belong to each class. Two/four home weapons grant additive affinity bonuses, subject to caps. Duplicate home weapons count toward affinity.

| Class | Base buffs | Base drawbacks | 2 home weapons | 4 home weapons (additional) |
| --- | --- | --- | --- | --- |
| Brawler | +25 HP, +4 Armor, +20% melee, +8 knockback, 15% contact resistance | −2 movement speed, −15% ranged | +15% melee, +2 Armor | 5% life steal |
| Gunner | +20% ranged, +35% projectile speed, +5 critical points, 10% faster ranged cadence | −15 HP, −15% melee | +1 pierce | +1 projectile |
| Thrower | +25% range, +1 bounce, +10% ranged | −10% attack speed, −2 Armor | +15% ranged | +1 projectile |
| Juggler | +3 movement speed, +15% attack speed, +12 knockback | −15% general damage | +15% range, +5 knockback | +1 bounce, +15% attack speed |
| Handyman | +25% utility, +20% area, +1 HP/s regeneration | −2 movement speed, −5 critical points | 10% cooldown reduction | +20% utility |
| Mage | +25% elemental, +30% duration, 15% burn chance, +1 chain target | −20 HP, −2 Armor, −10% melee | +15% elemental | +1 burn-spread target |

These prototype choices supersede the older proposal that classes need no drawbacks. Distinct orbital/return animations and deployables remain separate weapon-kit work; this change applies class statistics to the existing attack styles.

## Verification

- CharacterStatsTests.luau: **2,283 assertions passed** in an actual server Script during Studio Play, covering all classes/weapons, avatar application, affinity calculations, invalid/nonfinite/fractional inputs, phase and rate rejection, defenses, regeneration, Recovery, life-steal caps, critical/boss damage, status ticks, poison caps, chains, burn spread, reset and healing.
- StatProjectileTests.luau: actual swept-projectile tests passed for piercing and bounce falloff, unique targets, wall occlusion, projectile size, travel speed and rocket splash.
- Actual client controls: class selection changed Gunner HP to 85 and ranged bonus to 20%; Damage plus updated the UI and avatar attribute to 10. A client remote set Damage to 40; malformed requests were exercised separately.
- Zombie target 25 produced 25 enemies; zero cleared them and remained empty after replacement delay.
- Practice health-drop checks passed for Recovery healing and in-range/out-of-range pickup behavior.
- Authored katana scale verified after removing an erroneous ScaleTo call. RPG render fidelity is handled separately by FixRocketMuzzle.luau.
- Rojo combat and root packaging passed. Studio source and repository are synchronized.

Tests execute in the normal server Script context. Requiring stateful modules directly from the Studio assistant execution context gives a separate module cache and cannot inspect the live CharacterService state. Initial test-harness failures were corrected (a status threshold and a test-target folder outside the normal enemy occlusion exclusion).

Multiple real clients, published-game access restrictions, high-latency stress, final class balance, and maximum-population device performance remain unverified. Studio testing does not demonstrate those passed.
