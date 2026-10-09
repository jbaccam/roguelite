# Roster balance: old vs new (October 9, 2026)

From `combat/RosterBalanceTests.luau`, run with `python roguelite-planning/studio-prototype/combat/run_roster_tests.py build/luau-validation/luau.exe`.

- **Old** is the math before the Chef change: class fit +15 / 0 / -5 / -10 / -15, plus each class's two / four bonuses.
- **New** is specialty +10% plus the reworked type sets. Every set gives its weapons +4 / 7 / 10 / 13 / 15% damage at 2 / 3 / 4 / 5 / 6 copies. A weapon with two types takes only the higher of its two. Each set also adds one flavor bonus.
- All numbers are single-target DPS with no items and gear power 1. An extra projectile counts as a full extra hit on both sides. Burn chance, projectile speed, armor and dodge are not counted as DPS.

## Full class rosters (the targets)

| Build | T1 new / old | T4 new / old |
|---|---:|---:|
| Brawler roster | 0.942 | 0.941 |
| Gunner roster (6 guns) | **1.100** | **1.100** |
| Juggler roster (its first 6 weapons) | 0.971 | 0.971 |
| Handyman roster | 0.990 | 0.990 |
| Mage roster | 0.982 | 0.982 |
| Chef roster (old column is Thrower's) | 1.343 | 1.345 |
| Gunner, 4 guns | 1.052 | 1.052 |
| Brawler, 6 Katanas | 1.025 | 1.025 |
| Mage, 6 Staffs | 0.982 | 0.982 |

Brawler, Juggler, Handyman and Mage all land inside -7% to +5%. The 4-gun Gunner is +5.2%, under the +6% target.

**The 6-gun Gunner misses: +10.0% at both tiers.** The cause: Gun 6 gives +15%, and with specialty that's x1.10 x 1.15 = x1.265. The old fit gave x1.15. Both sides get the extra projectile, so it cancels out. The test prints this as a TARGET MISS line but doesn't fail on it.

**Decision (Oct 9): keep it.** The old Gunner also got a free +1 Pierce from two Gunner weapons, and that is gone. Pierce does nothing in this single-target table, but it hit extra enemies in a crowd. So the +10% on one target makes up for the lost crowd damage.

Chef isn't held to the band, because Thrower had different stats: ranged +15% where Chef has melee +10%.

## One weapon, no sets

| Group | Rows | New / old |
|---|---:|---|
| Own class before and after | 58 | 0.957 |
| Off class before and after | 270 | 1.000 to 1.176 |
| Moved into the class | 4 | 1.100 to 1.158 |
| Moved out of the class | 28 | 0.870 |

Weapons that moved lose 13% for their old class:
- Brawler: Pan, Shovel, Excalibur, Bowling Pin
- Gunner: Nail Gun
- Juggler: Kusarigama, Spatula, Egg, Gloves
- Handyman: Spatula, Rocket, Cinder Block
- Mage: Fart Gun, Molotov

## Pizza Cutter vs Legendary melee (no class)

| Weapon | Reach | T1 DPS | T4 DPS |
|---|---:|---:|---:|
| Pizza Cutter | 10.0 | 22.3 | 87.0 |
| Katana | 13.0 | 22.7 | 89.7 |
| Steak (Rare) | 7.5 | 19.8 | 77.6 |
| Wrecking Ball | 14.0 | 21.0 | 82.7 |
| Excalibur | 10.0 | 23.1 | 90.6 |

The Pizza Cutter is 2% under the Katana at every tier. The test allows 10%.

## Other numbers that moved

- **Legendary shop offers:** with the Pizza Cutter as an eighth Legendary, they go from 10.2% to 11.5% at wave 1, and from 16.4% to 18.3% at wave 20.
- **Brawler starter:** the new starter, Boxing Gloves, does 10.6 per jab at Tier I. That is under a wave-5 regular zombie's 11 HP; the Pan did 21.6. `EnemyScalingTests` now checks jab weapons on time to kill instead. Example: 2 jabs x 0.42 s = 0.84 s, against the old Pan's one hit every 1.05 s.
- **Strong Tier IV Glock:** with no sets it does 81.7 per hit, down from 85.4, so a Nightmare tank takes 8 hits instead of 7. With six Glocks (Gun 6) it does 93.9 per hit, so a Hard tank takes 4 hits instead of 5. `EnemyScalingTests` now expects both. Its only remaining failure is the other session's bloater speed check.
- **Battery Pack fix:** a lightning weapon now adds 1 to Lightning targets. Example: a Mage's Crystal Ball chains 2 enemies, where it chained 1.
