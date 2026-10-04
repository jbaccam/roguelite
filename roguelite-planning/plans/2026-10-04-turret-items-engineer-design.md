# Turret items and the Engineer Handyman: design

Approved 2026-10-04 in chat. Brotato's turrets, adapted to our game. The user asked for:
- "make the turrets scale in the amount of them and don't have the player place them, let them be automatically placed";
- "take direct inspiration from Brotato";
- "a way to place multiple turrets".

Decisions: turrets come from shop items, and the Handyman is Brotato's Engineer.

This replaces the class-ability turret, the BUILD button and the shop's UPGRADE TURRET button. It keeps the destructible turret work (9f6e956): health per turret, mobs attacking turrets, the break burst, the HP bar.

## 1. Turret items

Four run-shop items, one per model (`ReplicatedStorage.RogueliteCombat.HandymanTurrets.T1-T4`). Every copy owned is one more turret. Any class can buy them. They use the uploaded icons in `HandymanTurret.Icons`.

| Item id | Name | Item tier | Turret | Damage × nails / cooldown | DPS | Pierce | Base price |
|---|---|---|---|---|---|---|---|
| `turret_nail` | Nail Turret | 1 | T1 | 4 × 1 / 0.80 s | 5.0 | 0 | 24 |
| `turret_twin` | Twin Nailer | 2 | T2 | 6 × 1 / 0.72 s | 8.3 | 1 | 46 |
| `turret_quad` | Quad Nailer | 3 | T3 | 8 × 1 / 0.64 s | 12.5 | 1 | 85 |
| `turret_gatling` | Gatling Rig | 4 | T4 | 3.67 × 3 / 0.56 s | 19.6 | 2 | 150 |

- **Shared values:** range 25 studs for every turret. Prices go through the normal `EconomyConfig.price` (wave inflation and discounts). Example: a Nail Turret costs 41 at wave 5.
- **Limit:** 10 turrets per player, 30 per server. At 10 owned, the shop stops offering turret items to that player.
- **Shop weighting:** turret items get the Handyman class weighting, like Handyman weapons do today.
- **Selling:** turret items sell like any item.

## 2. Automatic placement

At every wave start, each player's turrets are placed again:
- **Ring:** 8–14 studs around the player for every class except Handyman, whose ring is 4–8 studs ("Structures spawn close to each other").
- **Spacing:** even angles with a little jitter, at least 5 studs between turrets.
- **Ground:** each spot is ray-cast down to solid ground inside the arena box. If a spot fails, try a closer radius, then the player's position.
- **During a wave:** turrets never move. They face the player's facing at placement.
- **Removed:** BUILD (keys B / R1, the on-screen button, RunAction `BuildTurret`), the auto "one turret per Handyman", and the shop's `UpgradeTurret` action and button. Tier comes from which item you buy.

## 3. Scaling (Brotato structure rule)

- **Damage:** turret damage = base × (1 + Utility Power %). Example: +30% Utility Power on a Nail Turret gives 5.2 damage per nail.
- **Ignored:** Damage, Ranged damage, Attack speed, Cooldown reduction, Crit and Life steal. The class-fit +15% does not apply either.
- **Applied:**
  - Extra projectiles (Two Straws: +1 nail per shot)
  - Pierce and Bounce, through `CharacterStats.shotStat`
  - status procs on direct hits: burn, slow, poison, lightning
  - BossDamage
- **Incoming damage:** the owner's Armor and Contact resistance still reduce damage to the turret, as built in 9f6e956.

## 4. Health and breaking

Kept from 9f6e956:
- **Health:** a Tier I turret has 60 + 15 × (wave − 1), × 1.5 per tier above I. Mobs nearer to a turret than to any player attack it.
- **Breaking:** a broken turret stays down until the next wave's placement.
- **Removed:** the BROKEN countdown and the rebuild-with-BUILD path. The HP bar stays.

## 5. Support items

Base prices are in the normal item bands. Icons reuse existing stat or item icons.
- **Scrap Magnet** (tier 2, 40): every 40 crystals picked up this wave builds a temporary Nail Turret at the player's ring, up to 3 per wave per copy. Temporary turrets last until the wave ends, don't count toward the player's 10, and do count toward the server's 30.
- **Spare Parts** (tier 2, 38): a broken turret rebuilds at its spot after 10 s, with full health. One copy covers all of that player's turrets.
- **Duct Tape** (tier 1, 20): turret health +50% per copy.
- **Toolbelt** (tier 1, 18): +6 Utility Power.

## 6. Handyman = Engineer

Changes to the `CharacterStats` Handyman entry and class rules:
- **Utility Power:** +15 to start (unchanged). Every Utility Power gain from items, level-up cards and set bonuses counts × 1.25. Example: a +12 card gives him +15.
- **Free turret:** he starts every run owning 1 Nail Turret item, which counts toward his 10.
- **Ring:** his turret ring is 4–8 studs.
- **Price:** turret items (including Scrap Magnet, Spare Parts, Duct Tape and Toolbelt) cost him 20% less.
- **Damage:** positive Damage gains from items, level-ups and sets count × 0.5. His +5% Damage buff is removed. Example: an item giving +10% Damage gives him +5%.
- **Unchanged:** his other buffs and drawbacks (Area +20%, Regen +1, Max HP −10, the two/four set bonuses).
- **Class description:** "Engineer: starts with a Nail Turret. Turrets spawn close to you. Utility Power gains +25%. Damage gains halved."

## 7. Admin panel

- **Player tab, Turrets:**
  - Give Nail / Twin / Quad / Gatling: adds the item to your run inventory.
  - Break turret: breaks the one nearest to you.
  - Clear turrets.
- The old Give turret / Tier I–IV buttons are removed.

## 8. Worked example (Handyman)

| Wave | Turrets | Utility Power | Turret DPS (sum) |
|---|---|---|---|
| 1 | 1 Nail (free) | +15% | 5.75 |
| 5 | 3 Nail | +30% | 19.5 |
| 10 | 4 Nail + 1 Twin | +45% | ≈ 41 |
| 15 | 6 Nail + 2 Twin + 1 Quad | +70% | ≈ 100 |

A Gunner with 2 Nail Turrets and no Utility Power gets 10 DPS.

## 9. Tests and checks

`TurretTests` covers:
- item stats per tier, and the Utility Power scaling
- the Brotato stat rule: Damage, Attack speed and Crit ignored; Pierce and procs applied
- the ring placement maths: radius bands, spacing, fallback
- the 10 / 30 caps
- Scrap Magnet counting, Spare Parts timing, Duct Tape health
- the Handyman × 1.25 and × 0.5 rules, and his turret price

`ShopTests` covers turret items being offered, priced, discounted for Handyman and capped.

`HANDYMAN_TURRET.md` is rewritten for this version.
