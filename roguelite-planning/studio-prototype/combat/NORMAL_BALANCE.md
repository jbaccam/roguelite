# Approachable Normal — October 5, 2026



Normal now applies **0.60 enemy HP and 0.75 enemy damage**, instead of 1.00 / 1.00, through the existing server-side RunSetupRules difficulty multiplier. This affects every regular enemy and boss on every map. It benefits the complete weapon roster without removing class debuffs, changing stat IDs/effects, or inflating all weapon damage. The previous Draco adjustment is retained. Rewards, gear-power curves, base wave formulas, movement, swarms and progression unlocks are unchanged.



Hard stays 1.60 HP / 1.30 damage; Nightmare stays 2.50 / 1.60. Relative to the easier Normal, Hard has **2.67 times HP and 1.73 times damage**; Nightmare has **4.17 times HP and 2.13 times damage**. These remain optional challenges; Normal is the approachable mode. The harder modes' absolute tuning did not increase, but the visible gap is deliberately larger.



## Progression benchmarks



Pine Valley Normal server-rounded HP:



| Enemy | Wave 1 | Wave 5 | Wave 10 | Wave 20 |

|---|---:|---:|---:|---:|

| Regular | 2 | 7 | 13 | 25 |

| Baby | 1 | 3 | 6 | 12 |

| Tank (natural from wave 8) | 30 | 39 | 72 | 138 |



The base practice catalog retains a 50 HP tank floor; actual Normal spawns apply difficulty afterward. Normal wave-20 regular / tank damage becomes 16.575 / 28.875 before armor. The boosted Tier IV Gunner benchmark (85.3875 damage) still one-shots regulars and now takes two tank hits. Even without run bonuses, T4 Pan/Katana/Gloves take two tank hits. Multi-hit and rapid-fire weapons retain their identities rather than being forced into the same per-bullet damage.



Normal boss HP also receives the same 40% reduction, with no duplicated boss-specific reduction: solo Hammer 18,000 authored becomes 10,800; solo Dragon at its recommended map power becomes 31,536. Existing boss/player-count rules still apply. Matching permanent gear power continues to cancel the map's gear multiplier; under-geared later-map runs remain tougher.



## Full roster audit



Actual WeaponCatalog + CharacterStats calculations, no run-item bonuses, criticals, armor bonuses, or permanent gear power. T1 has one equipped affinity weapon; T4 uses the four-affinity bonus available in a six-slot build. Every class weapon is evaluated in its home class, and every Godly is evaluated in all six classes. This preserves the real class debuffs.



The table counts **listed direct-damage units**, not guaranteed attack cycles or measured time-to-kill: Shotgun numbers are individual pellets (T4 fires eight), Molotov/streams involve repeat ticks, and Deck of Cards lists the volley damage basis while each card carries a fraction. Area attacks, piercing, status stacks, returns, extra projectiles and Godly specials are excluded. Do not interpret 17 shotgun damage units as 17 trigger pulls.



All 42 weapons clear first-wave ordinary fodder with one listed home-class damage unit. Without any run-item damage bonuses, 25/36 class weapons clear wave-20 ordinary fodder in one listed unit, and 35/36 in at most two; Shotgun is the multi-pellet exception. These are static breakpoints, not a substitute for live accuracy, targeting or crowd tests.



| Weapon | Class | T1 damage | T1 regular hits W1 / W5 | T4 damage | T4 W20 regular / tank hits |

|---|---|---:|---:|---:|---:|

| Glock | Gunner | 16.56 | 1 / 1 | 45.54 | 1 / 4 |

| Frying Pan | Brawler | 24.84 | 1 / 1 | 85.39 | 1 / 2 |

| Nunchucks | Brawler | 9.66 | 1 / 1 | 29.50 | 1 / 5 |

| Katana | Brawler | 28.98 | 1 / 1 | 90.05 | 1 / 2 |

| Kusarigama | Juggler | 17.59 | 1 / 1 | 48.65 | 1 / 3 |

| Spatula | Juggler | 9.31 | 1 / 1 | 25.87 | 1 / 6 |

| Baseball Bat | Brawler | 28.98 | 1 / 1 | 90.05 | 1 / 2 |

| Draco | Gunner | 4.14 | 1 / 2 | 15.18 | 2 / 10 |

| Fart Gun | Gunner | 5.52 | 1 / 2 | 15.18 | 2 / 10 |

| Shotgun | Gunner | 4.14 | 1 / 2 | 8.28 | 4 / 17 |

| T-Shirt Cannon | Gunner | 26.22 | 1 / 1 | 71.76 | 1 / 2 |

| Rocket Launcher | Gunner | 52.44 | 1 / 1 | 143.52 | 1 / 1 |

| Boomerang | Thrower | 9.26 | 1 / 1 | 25.41 | 1 / 6 |

| Kunai | Thrower | 7.93 | 1 / 1 | 23.92 | 2 / 6 |

| Molotov | Thrower | 3.97 | 1 / 2 | 14.95 | 2 / 10 |

| Egg | Thrower | 13.22 | 1 / 1 | 40.37 | 1 / 4 |

| Steak | Thrower | 16.56 | 1 / 1 | 45.54 | 1 / 4 |

| Rubber Duck | Juggler | 5.17 | 1 / 2 | 14.49 | 2 / 10 |

| Deck of Cards | Thrower | 23.80 | 1 / 1 | 59.80 | 1 / 3 |

| Boxing Gloves | Brawler | 11.04 | 1 / 1 | 74.52 | 1 / 2 |

| Cinder Block | Brawler | 45.54 | 1 / 1 | 141.28 | 1 / 1 |

| Yo-Yo | Juggler | 8.28 | 1 / 1 | 22.77 | 2 / 7 |

| Bowling Ball | Juggler | 28.98 | 1 / 1 | 79.69 | 1 / 2 |

| Bowling Pin | Juggler | 13.46 | 1 / 1 | 37.26 | 1 / 4 |

| Nail Gun | Handyman | 5.29 | 1 / 2 | 16.10 | 2 / 9 |

| Wrecking Ball | Handyman | 43.64 | 1 / 1 | 146.51 | 1 / 1 |

| Shovel | Handyman | 26.45 | 1 / 1 | 88.55 | 1 / 2 |

| Paint Roller | Handyman | 15.87 | 1 / 1 | 53.13 | 1 / 3 |

| Vacuum Cleaner | Handyman | 5.29 | 1 / 2 | 17.71 | 2 / 8 |

| Power Washer | Handyman | 3.97 | 1 / 2 | 12.88 | 2 / 11 |

| Magic Staff | Mage | 12.94 | 1 / 1 | 40.25 | 1 / 4 |

| Mjolnir | Mage | 33.64 | 1 / 1 | 102.88 | 1 / 2 |

| Excalibur | Mage | 40.11 | 1 / 1 | 123.16 | 1 / 2 |

| Pandora's Box | Mage | 37.38 | 1 / 1 | 114.31 | 1 / 2 |

| Medusa's Head | Mage | 7.19 | 1 / 1 | 22.54 | 2 / 7 |

| Crystal Ball | Mage | 18.69 | 1 / 1 | 57.96 | 1 / 3 |

| Reaper's Scythe | Brawler | 36.00 | 1 / 1 | 110.70 | 1 / 2 |

| Reaper's Scythe | Gunner | 25.50 | 1 / 1 | 69.70 | 1 / 2 |

| Reaper's Scythe | Thrower | 27.00 | 1 / 1 | 73.80 | 1 / 2 |

| Reaper's Scythe | Juggler | 27.00 | 1 / 1 | 73.80 | 1 / 2 |

| Reaper's Scythe | Handyman | 30.00 | 1 / 1 | 82.00 | 1 / 2 |

| Reaper's Scythe | Mage | 27.00 | 1 / 1 | 73.80 | 1 / 2 |

| Poseidon's Trident | Brawler | 40.80 | 1 / 1 | 125.55 | 1 / 2 |

| Poseidon's Trident | Gunner | 28.90 | 1 / 1 | 79.05 | 1 / 2 |

| Poseidon's Trident | Thrower | 30.60 | 1 / 1 | 83.70 | 1 / 2 |

| Poseidon's Trident | Juggler | 30.60 | 1 / 1 | 83.70 | 1 / 2 |

| Poseidon's Trident | Handyman | 34.00 | 1 / 1 | 93.00 | 1 / 2 |

| Poseidon's Trident | Mage | 30.60 | 1 / 1 | 83.70 | 1 / 2 |

| Storm Bow | Brawler | 11.90 | 1 / 1 | 32.30 | 1 / 5 |

| Storm Bow | Gunner | 16.80 | 1 / 1 | 45.60 | 1 / 4 |

| Storm Bow | Thrower | 16.10 | 1 / 1 | 49.40 | 1 / 3 |

| Storm Bow | Juggler | 12.60 | 1 / 1 | 34.20 | 1 / 5 |

| Storm Bow | Handyman | 14.00 | 1 / 1 | 38.00 | 1 / 4 |

| Storm Bow | Mage | 17.50 | 1 / 1 | 53.20 | 1 / 3 |

| Shadow Daggers | Brawler | 19.20 | 1 / 1 | 59.40 | 1 / 3 |

| Shadow Daggers | Gunner | 13.60 | 1 / 1 | 37.40 | 1 / 4 |

| Shadow Daggers | Thrower | 14.40 | 1 / 1 | 39.60 | 1 / 4 |

| Shadow Daggers | Juggler | 14.40 | 1 / 1 | 39.60 | 1 / 4 |

| Shadow Daggers | Handyman | 16.00 | 1 / 1 | 44.00 | 1 / 4 |

| Shadow Daggers | Mage | 14.40 | 1 / 1 | 39.60 | 1 / 4 |

| Vampire Blade | Brawler | 38.40 | 1 / 1 | 118.80 | 1 / 2 |

| Vampire Blade | Gunner | 27.20 | 1 / 1 | 74.80 | 1 / 2 |

| Vampire Blade | Thrower | 28.80 | 1 / 1 | 79.20 | 1 / 2 |

| Vampire Blade | Juggler | 28.80 | 1 / 1 | 79.20 | 1 / 2 |

| Vampire Blade | Handyman | 32.00 | 1 / 1 | 88.00 | 1 / 2 |

| Vampire Blade | Mage | 28.80 | 1 / 1 | 79.20 | 1 / 2 |

| Ray Gun | Brawler | 18.70 | 1 / 1 | 51.00 | 1 / 3 |

| Ray Gun | Gunner | 26.40 | 1 / 1 | 72.00 | 1 / 2 |

| Ray Gun | Thrower | 25.30 | 1 / 1 | 78.00 | 1 / 2 |

| Ray Gun | Juggler | 19.80 | 1 / 1 | 54.00 | 1 / 3 |

| Ray Gun | Handyman | 22.00 | 1 / 1 | 60.00 | 1 / 3 |

| Ray Gun | Mage | 27.50 | 1 / 1 | 84.00 | 1 / 2 |



## Verification



`run_enemy_scaling_tests.py` runs real pure source functions with only Roblox module wiring and unused motion dependencies adapted. The final run passed EnemyScalingTests **2,496**, NormalBalanceTests **942**, and GearPowerTests **74** assertions. Checks cover the whole roster, all map gear-power mappings, Normal easing, unchanged challenge settings/reward value, early/mid/late progression, and boss scaling relations. Full Studio physics, attack delivery, swarm performance and a naturally completed six-slot run are outside this numerical audit; the parent integration report records any actual Studio tests.


## Normal movement across all maps

Latest feedback: all ordinary enemies now chase at **85% of their catalog speed on Normal**, applied once by the server when they spawn. Hard and Nightmare keep the catalog speed. This is independent of wave number and map gear power, so waves 1–20 never accelerate. Existing Endless adjustment follows it after wave 20. Hammer and all other bosses are excluded; Hammer retains 24 walking speed (rebuilt 26 enraged).

| Enemy | Previous Normal / current Hard and Nightmare | Current Normal (studs/s) |
|---|---:|---:|
| Regular Zombie | 14 | 11.90 |
| Baby Zombie | 17 | 14.45 |
| Tank Zombie | 11 | 9.35 |
| Spitter Zombie | 13 | 11.05 |
| Crab | 16 | 13.60 |
| Snake | 15 | 12.75 |
| Hermit Crab | 12 | 10.20 |
| Rock-Throwing Crab | 13 | 11.05 |
| Skeleton | 17 | 14.45 |
| Bow Skeleton | 14 | 11.90 |
| Mummy | 13 | 11.05 |
| Scorpion | 15 | 12.75 |
| Frost Ghost | 16 | 13.60 |
| Werewolf | 21 | 17.85 |
| Frozen Knight | 12 | 10.20 |
| Ice Elf | 14 | 11.90 |
| Fire Goblin | 18 | 15.30 |
| Ember Spider | 20 | 17.00 |
| Lava Slime | 13 | 11.05 |
| Obsidian Ogre | 12 | 10.20 |
| Ash Shaman | 13 | 11.05 |

`RunSetupRules.enemyMoveScale` reads the server-selected difficulty; missing/unknown difficulty uses Normal. HP, damage, reward values, player movement, boss movement, attack telegraphs and attack lunge/projectile speeds do not change in this pass. These are chase-speed changes, not a general slow-motion effect.

Local numerical verification passed **4,261 enemy scaling**, **942 Normal balance** and **74 gear-power** assertions: every enemy and difficulty through all 20 regular waves has a constant expected speed; every Normal enemy stays below 18 studs/s; difficulty fallback is safe. Changed source compiled. Parent owns the Chase application hook, Studio sync and live movement validation; no new Studio Play test was run by this agent.

## Multiplayer health follow-up — October 6

[Shared multiplayer health policy](MULTIPLAYER_HEALTH_2026-10-06.md): ordinary HP stays at the solo baseline while authored arrivals scale with active players. Boss HP now scales linearly 1/2/3/4 instead of 1/2.35/3.7/5.05; solo and incoming damage remain unchanged. The global cap and existing shard-sharing limitations are documented there.
