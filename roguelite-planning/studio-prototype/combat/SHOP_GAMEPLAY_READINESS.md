October 4 squad feedback: [applied fixes and actual Studio test results](BUGFIX_REPORT_2026-10-04.md). Source and Studio are synchronized; multiplayer limits are recorded there.

# Shop gameplay readiness

Updated 2026-09-23; the 2026-10-03 play-test round is marked below (repo only, syntax-checked, not yet in Studio, not play-tested). The [Brotato shop reference](https://brotato.wiki.spellsandguns.com/Shop) informed the pacing and offer rules; this game keeps its own characters, weapons, items, shards, and combat values.

## Current shop rules

Some numbers in the first bullets are older than their code: the tier odds and the recycle refund were retuned later (now 25% of the current shop price). Current values: [WEAPON_BALANCE.md](WEAPON_BALANCE.md) and `EconomyConfig`.

- Four server-owned offers. Shops 1–2 have two weapons and two items. Shops 3–5 guarantee one weapon. Later slots roll 35% weapon and 65% item.
- Tier 2 starts on wave 2, Tier 3 on wave 6, Tier 4 on wave 12 (`EconomyConfig.rarityChance`). The server checks Tier 4, then 3, then 2, each with the buying player's own Luck. Per-wave growth is 6%, 1.5% and 0.15%, capped at 60%, 20% and 5%; Luck then multiplies the capped chance by (1 + Luck/100), with Tier 2 stopping at 90% so Tier 1 keeps 10%. Fix 2026-10-10 (play-test: Luck 40 and Luck 100 showed the same reroll odds): Luck used to multiply before the cap, so from about wave 15 every Luck read I 40% · II 40% · III ~19%. Wave 20 now: Luck 0 I 40% · II 40% · III 18.6% · IV 1.35% (unchanged); Luck 40 I 16% · II 56% · III 26.1% · IV 1.9%; Luck 100 I 10% · II 50% · III 37.3% · IV 2.7%. Level-up cards (`LevelUpCatalog.thresholds`) follow the same rule. `ShopPreferenceTests` checks it.
- Owned weapon identities get a 20% pool preference. Owned weapon home classes get a 15% preference plus an early-shop bonus. Items get a small 5% preference for class-appropriate build tags. The general pool always remains available.
- A reroll keeps locked offers and their price, avoids the previous four offers, and avoids duplicate catalog entries in the current set. Buying all four refills the shop for free. Reroll costs rise with the wave and each reroll, then reset the next wave.
- Shop inflation follows base price plus wave and 10% of base price per wave. Recycled weapons still return 50% of their actual purchase cost. This is intentionally more forgiving than the reference because this game has no crate item economy.
- Purchases, copy caps, weapons, combining, locks, prices, and the phase are validated on the server. No paid purchase changes shop odds. Studio practice does not write persistent rewards.
- Common shop cards have no rarity outline. Higher tiers use dark colored fills with an outline. The overall shop background and gray panels are darker.
- A run launched from a lobby pad opens on wave 1; the first shop comes after it (`ShopService.startFirstWave`, 2026-09-28).
- **Out of play between waves (2026-09-28).** While the run phase is Shop, a player in the arena can't be hurt, walk or jump, so nobody can die or wander around mid-shop. `CharacterService.inShop` drives both rules:
  - `contact` returns 0. Every player damage path goes through it: enemy melee and projectiles, contact damage, Tank slams and the boss.
  - The Humanoid gets WalkSpeed 0 and JumpHeight 0 on the server.
  - The server puts back anyone who drifts more than 3 studs. A jump over 25 studs is a server move (travel, respawn), so the hold restarts from there.
  - Players standing in the Studio lobby aren't in the run and move freely.
  - Verified in single-client Studio Play:
    - During the shop, 1.5 s of held forward and jump input moved 0.00 studs and rose 0.00.
    - A 6–7 stud client teleport snapped back within 0.3 s.
    - The admin 20-damage test hit dealt 0.
    - After Start, WalkSpeed went back to 22 and JumpHeight to 9.5, and the same hit dealt 13.4.
  - The very first teleport attempt, right after spawning, wasn't pulled back. Every later one was.
- **Every non-Godly weapon is offered (2026-10-03).** It used to be only weapons owned on the profile plus the ones carried. Owning a weapon still decides starters and the Armory. Mjolnir (an achievement unlock) now shows up in run shops. Carried weapons and their classes still get the preference above.
- **Items only offered when they work (2026-10-03).** One rule, `CharacterStats.usesStat` (via `ShopCatalog.worksWith`), says which weapons use the weapon-only stats:
  - extra shots: guns, staffs, cards, throws that don't come back, rockets, Pandora's Box, Storm Bow;
  - pierce and bounce: bullets, cards, throws that aren't fire or gas (Boomerang, Mjolnir and the Trident included);
  - none: melee, Rubber Duck, Vacuum, Power Washer.
  - extra swings (since 2026-10-10, Windshield Wiper): melee swings only, not the Shadow Daggers (below).
  - Two Straws, Bouncy Ball, Sharp Pencil, Support Ketchup, Hot Sauce and Tinfoil Antlers are offered only while a carried weapon uses them. Example: a Frying Pan + Boomerang build is never offered Two Straws; buying a Glock makes it possible again.
  - Their cards say "Works with: Glock, Magic Staff", or in red "None of your weapons use this" (after selling the last one).
- **Status items cause their own status (2026-10-03),** on any weapon's direct hit. Before, Marshmallow, Peas and Stinky Sock only boosted a status something else caused, so most builds got nothing from them.
  - Microwaved Marshmallow: +5% burn chance (plus +20% burn damage).
  - Freezer-Burned Peas: +5% slow chance (plus +25% slow duration).
  - Stinky Sock: +5% poison chance (plus +20% poison damage).
  - Grandma's Oven Mitt: +10% burn chance (plus burn spread).
  - Ice Cube: +10 slow strength, so its slow is 35% for 2 s like Medusa's Head (bosses half).
  - Bone Crown: +5% damage and +20% boss damage (was +15% boss damage only; there are no elite waves, so it did nothing until wave 20).
  - Every item card now says exactly what happens, in plain words ("All your weapons deal 8% more damage.").
- **Seven player-buff items (2026-10-03), 44 items in all.** User: more items that buff the player, not the weapons. Their icons are the matching level-up stat art.

  | Item | Tier | Base price | Effect |
  | --- | ---: | ---: | --- |
  | Banana Peel | 1 | 18 | 5% dodge |
  | Couch Cushion | 1 | 17 | +1 armor, +6 max HP |
  | Lucky Penny | 1 | 17 | +6 luck, 3% dodge |
  | Chicken Soup | 2 | 34 | +6 max HP, +15% recovery |
  | Roller Skates | 2 | 38 | +10% move speed, 3% dodge |
  | Metal Detector | 2 | 36 | +8 luck, +20% pickup radius |
  | Vitamin Gummies | 3 | 66 | +2 HP/s regeneration, +10 max HP |

- **Shop screen (2026-10-03).** A bag icon and amount sit beside the crystal count while the crystal bag holds any ([SHARD_CURRENCY.md](../../SHARD_CURRENCY.md)). In multiplayer, GO shows READY x/y (living run members who pressed GO). The weapon popup stacks stats, then traits, then the class row, so "Range" is no longer hidden; it scrolls on short screens. Since 2026-10-04 turrets are shop items and UPGRADE TURRET is gone ([HANDYMAN_TURRET.md](HANDYMAN_TURRET.md)).
- **Tests added (2026-10-03):** `ShopTests` (offerable weapons, usable items), `ShopLayoutTests`, `ShardBagTests`. Not run in Studio yet.

## Windshield Wiper and stronger coupons (2026-10-10)

Repo only. The pure shop tests ran (below); not synced to Studio, no Play test.

### Windshield Wiper: more swings for melee

Play-test: "Could maybe have an item that gives you multiple swings, like one of the ranged items gives you more projectiles." It is Two Straws for melee.

- `wiper`, Tier III, base 80, 2 copies. Each copy is +1 **Extra swings**, a new weapon-only stat (0 to 2, whole numbers) that works like Extra projectiles.
- Card: "Your melee weapons swing again after every swing, back the other way, for 60% damage. 2 copies: 2 extra swings (1 on very fast weapons)."
- Offered only while you carry a melee weapon (`CharacterStats.usesStat` through `ShopCatalog.usable`), and the card's "Works with" names them. That covers every melee swing, including Mjolnir and Trident swings (not their throws) and the Godly blades. Not the Shadow Daggers (their chain is the hit), guns, throws, the Rubber Duck, streams or turrets. Melee builds prefer it (tag Melee).
- How it plays: when a swing stops hitting (0.256 s into a normal-speed swing), the same weapon swings again, mirrored (the other glove for Boxing Gloves). It aims at the nearest enemy still in reach, or the same spot.
- Server checked (`RogueliteCombat.server`): the extra swing starts from where the player's own screen has them (`CharacterService.seen`). The normal melee sweep hit-tests it (same reach, walls, boss shell and enemy rules). It deals 60% of the swing's damage and can crit and cause statuses like any hit. It never triggers a Legendary Tier IV move, so no double shockwave or slash.
- Clients draw it from the slot's `Attack` attribute like any swing (existing poses and swing ribbons). No new remotes, no client change.
- Cadence: the next attack waits until the last extra swing stops hitting, plus one 1/30 s tick. On most weapons that fits inside the normal cooldown. On very fast weapons a 2nd extra swing would push back a full swing, so it isn't made (`CharacterStats.extraSwingTimes` keeps the count with the most damage per second). So a 2nd copy never lowers damage.

Damage per second, Tier I with the class specialty and no other bonuses, one target:

| Weapon | No Wiper | 1 Wiper | 2 Wipers |
| --- | ---: | ---: | ---: |
| Katana | 25.0 | 40.0 (+60%) | 55.0 (+120%) |
| Frying Pan | 17.1 | 27.4 (+60%) | 37.7 (+120%) |
| Baseball Bat | 17.6 | 28.2 (+60%) | 38.7 (+120%) |
| Pizza Cutter | 22.3 | 35.7 (+60%) | 41.2 (+85%) |
| Boxing Gloves | 22.0 | 35.2 (+60%) | 35.6 (+62%) |
| Spatula | 16.4 | 26.2 (+60%) | 26.2 (only 1 fits) |
| Nunchucks | 11.6 | 17.2 (+48%) | 17.2 (only 1 fits) |

Against Two Straws (Tier III, base 90, 1 copy): Glock 17.7 to 35.4 (+100% when both bullets hit), Shotgun 15.3 to 18.3 (+20%). One Wiper (+60%) is weaker per copy than Straws on a single-shot gun, but a swing hits everything in its arc, and the extra swing does too. Two Wipers (+120%) cost two Tier III buys: at wave 10 that is 170 + 170 shards against 190 for Straws. Prices for the Wiper at waves 5 / 10 / 15 / 20 / 25: 125 / 170 / 215 / 260 / 305 (Straws: 140 / 190 / 240 / 290 / 340).

### Grandma's Coupons: 10% a copy

Play-test: the coupon should be better.

- Was: Tier II, base 35, 5% off new offers per copy, up to 5 copies (25% at most).
- Now: **10% per copy, up to 3 copies (30% at most)**. Same tier and price.
- Cap: the Shop discount stat stops at 30%, and the shop multiplier never goes below x0.2, so stacking can't make anything free. Locked offers keep their price and rerolls aren't discounted, as before.

Prices of a base-90 Tier III item / a base-16 Tier I item:

| Wave | No coupon | Old: 1 (5%) | Old: 5 (25%) | New: 1 (10%) | New: 2 (20%) | New: 3 (30%) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 140 / 29 | 133 / 27 | 105 / 21 | 126 / 26 | 112 / 23 | 98 / 20 |
| 15 | 240 / 55 | 228 / 52 | 180 / 41 | 216 / 49 | 192 / 44 | 168 / 38 |
| 25 | 340 / 81 | 323 / 76 | 255 / 60 | 306 / 72 | 272 / 64 | 238 / 56 |

Why: one coupon costs 57 shards at wave 5 and 102 at wave 15. At 5% it saved 7 on a wave-5 Tier III item, so it paid for itself only after about 8 such buys. At 10% it saves 14 there (24 at wave 15), so it pays back in about 4. The 3-copy cap keeps the best case (30%) close to the old one (25%), and it takes 3 buys instead of 5.

### Tests

- `ShopPreferenceTests` (run with `run_shop_tests.py`, 5,611 to 5,979 checks): the Wiper's entry and text, who is offered it (13 melee weapons yes, 10 others no, turrets no), "Works with", preference weight, stacking (1, 2, and 5 copies resolve to 1, 2, 2; whole numbers only), what one attack gets (`extraSwings`: Katana 1 or 2, Glock, Shadow Daggers and a thrown hammer 0), the timing rule (start times, Katana keeps its cadence, Nunchucks and Spatula make 1, and more copies never lower damage for any melee timing), the coupon entry, its 30% cap and x0.2 floor, and the price table above.
- Every other runner still passes; `run_enemy_scaling_tests` and `run_wave_timeline_tests` already failed at HEAD. The server swing itself needs a Studio Play test (an Extra swings override in the practice editor works for that).

## Build paths supported by the catalog

| Build | Working ingredients |
| --- | --- |
| Burn spread | Molotov or Lighter, Microwaved Marshmallow, Grandma's Oven Mitt |
| Poison | Fart Gun or Toxic Barrel, Stinky Sock |
| Lightning | Magic Staff, Mjolnir, or Battery Pack; Tinfoil Antlers adds targets, Alien Battery boosts chain damage |
| Projectiles | Shotgun, Deck of Cards, Draco, or Nail Gun with Two Straws, Sharp Pencil, or Bouncy Ball where compatible |
| Critical hits | Fast direct-hit weapons, Broken Glasses, Tooth Fairy's Collection |
| Durable melee | Brawler weapons, Pot Lid or Safety Helmet, Cracked Burial Mask, Bandage Roll, Vampire Fang, Bubble Wrap Vest |
| Melee swings (2026-10-10) | Katana, Frying Pan, Baseball Bat or any slow-to-medium swing, with Windshield Wiper and Knee of Justice |

The server caps extra projectiles, bounce, pierce, lightning targets, and first-hit blocks. Since 2026-10-03 the status items cause their own status (above). Tinfoil Antlers still needs lightning (a lightning weapon, Battery Pack or the Mage class) and is offered only when you have it.

## Art roster decisions

- **Skip Manager Badge art.** It duplicated Bone Crown's elite/boss bonus and has been removed from the shop. The roster then had 37 passives; it has 44 items since 2026-10-03 (the seven player-buff items above reuse level-up stat icons, so no new art).
- **Keep all other item art in progress.** Bouncy Ball and Bubble Wrap Vest moved to Tier 4, giving the highest rarity three distinct items without asking for new art.
- Support Potato now adds a small pickup-radius bonus alongside health, separating it from cheap pure-HP Emergency Cheese. Cracked Burial Mask combines armor with contact resistance. Alien Battery combines a smaller attack-speed bonus with stronger lightning chains. Their images remain useful.
- No additional item images are needed for this shop pass. Distinct new effects should wait for play balance data, especially late-wave offer variety.

## Remaining game work

XP-earned stat selection is implemented and tested; see LEVEL_UP_READINESS.md for the upgrade flow and verification. Balance of offer prices and build power still needs multi-wave playtesting with real players. The shop itself does not grant persistent currency in Studio.
