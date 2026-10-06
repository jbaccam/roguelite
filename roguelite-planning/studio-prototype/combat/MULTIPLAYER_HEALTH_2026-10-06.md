# Multiplayer health policy — October 6, 2026

Each additional participant can bring six more weapons. Regular enemies retain their exact solo HP, damage and speed: the coordinated spawn policy supplies N times the authored arrivals for N active players, and boss-add capacity grows to 20N (20/40/60/80). Applying N times HP to those N times arrivals would create N-squared total health and erase the early fodder one-shot pacing. Spawn controls and their live tests are owned by the separate timeline/cap integration.

Bosses are one shared target, so `RunSetupRules.bossScale` now uses **1/2/3/4 times solo HP** for 1–4 encounter participants. Previously it used 1/2.35/3.7/5.05. Against equal per-player DPS, ideal boss kill time now matches solo. There is no multiplayer damage or speed increase. Map gear power, Normal/Hard/Nightmare, and Endless continue to apply exactly once as before.

| Players | Weapons at six slots each | Previous boss HP factor | New factor | Normal Pine Hammer HP |
|---|---:|---:|---:|---:|
| 1 | 6 | 1.00 | 1 | 10,800 |
| 2 | 12 | 2.35 | 2 | 21,600 |
| 3 | 18 | 3.70 | 3 | 32,400 |
| 4 | 24 | 5.05 | 4 | 43,200 |

The solo column is unchanged. All five maps and all three difficulties share this rule; no weapon inventory, rarity, stat roll, or current build is inspected. `partySize` floors and clamps the server count to 1–4, with safe missing/NaN inputs.

## Encounter participation and caps

Both legacy and rebuilt boss spawners snapshot `RunMember` players at encounter creation, including temporarily downed run members. Lobby spectators are excluded. HP does not change during the fight as somebody dies, revives or leaves. Regular arrivals use living/up players, so they adjust to the active team. This distinction preserves the existing stable boss encounter health instead of encouraging deaths to reduce boss HP. Tutorial fixed boss health remains fixed. Endless bosses first spawn through these same boss services, then apply their existing Endless factor without another player multiplier.

The 100-enemy global safety cap remains. Four-player arrivals may saturate it, particularly if the squad stops killing. Exact equal intensity cannot be guaranteed at that cap or against unequal build strength; that is an explicit performance constraint, not a claim of measured four-client parity.

## Economy audit — unchanged

Ordinary shards are owned by `LastDamageUserId`; more total arrivals provide more total drops, but rewards can concentrate on the player landing final hits. Bosses still produce a fixed 50 crystals split evenly among living run members, so each player receives a smaller boss-crystal share in a larger squad. That is existing behavior and was not silently retuned. Emerald milestone/win formulas are per-player and do not divide by party size. No persistent reward, DataStore, or shop changes were made by this policy.

## Verification

Local actual-source Luau runner passed **4,261 EnemyScalingTests + 942 NormalBalanceTests + 265 GearPowerTests = 5,468 assertions**. Added checks cover all five maps, three difficulties and four party sizes: linear boss HP, unchanged ideal per-player health budget, unchanged incoming damage, and malformed/out-of-range counts. Runtime and tests compile. No Studio sync or Play test was performed by this agent for this pass; parent integration records actual multiplayer checks separately.

Changed implementation: `lobby/RunSetupRules.luau`. Changed tests: `combat/GearPowerTests.luau`. Ordinary enemy catalogs were not edited for party size.
