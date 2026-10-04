# Shop gameplay readiness

Updated 2026-09-23; the 2026-10-03 play-test round is marked below (repo only, syntax-checked, not yet in Studio, not play-tested). The [Brotato shop reference](https://brotato.wiki.spellsandguns.com/Shop) informed the pacing and offer rules; this game keeps its own characters, weapons, items, shards, and combat values.

## Current shop rules

Some numbers in the first bullets are older than their code: the tier odds and the recycle refund were retuned later (now 25% of the current shop price). Current values: [WEAPON_BALANCE.md](WEAPON_BALANCE.md) and `EconomyConfig`.

- Four server-owned offers. Shops 1–2 have two weapons and two items. Shops 3–5 guarantee one weapon. Later slots roll 35% weapon and 65% item.
- Tier 2 starts on wave 2, Tier 3 on wave 4, Tier 4 on wave 8. The server checks Tier 4, then 3, then 2; Luck raises those chances within caps of 8%, 25%, and 60%. The underlying per-wave growth is 0.23%, 2%, and 6% respectively.
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

## Build paths supported by the catalog

| Build | Working ingredients |
| --- | --- |
| Burn spread | Molotov or Lighter, Microwaved Marshmallow, Grandma's Oven Mitt |
| Poison | Fart Gun or Toxic Barrel, Stinky Sock |
| Lightning | Magic Staff, Mjolnir, or Battery Pack; Tinfoil Antlers adds targets, Alien Battery boosts chain damage |
| Projectiles | Shotgun, Deck of Cards, Draco, or Nail Gun with Two Straws, Sharp Pencil, or Bouncy Ball where compatible |
| Critical hits | Fast direct-hit weapons, Broken Glasses, Tooth Fairy's Collection |
| Durable melee | Brawler weapons, Pot Lid or Safety Helmet, Cracked Burial Mask, Bandage Roll, Vampire Fang, Bubble Wrap Vest |

The server caps extra projectiles, bounce, pierce, lightning targets, and first-hit blocks. Since 2026-10-03 the status items cause their own status (above). Tinfoil Antlers still needs lightning (a lightning weapon, Battery Pack or the Mage class) and is offered only when you have it.

## Art roster decisions

- **Skip Manager Badge art.** It duplicated Bone Crown's elite/boss bonus and has been removed from the shop. The roster then had 37 passives; it has 44 items since 2026-10-03 (the seven player-buff items above reuse level-up stat icons, so no new art).
- **Keep all other item art in progress.** Bouncy Ball and Bubble Wrap Vest moved to Tier 4, giving the highest rarity three distinct items without asking for new art.
- Support Potato now adds a small pickup-radius bonus alongside health, separating it from cheap pure-HP Emergency Cheese. Cracked Burial Mask combines armor with contact resistance. Alien Battery combines a smaller attack-speed bonus with stronger lightning chains. Their images remain useful.
- No additional item images are needed for this shop pass. Distinct new effects should wait for play balance data, especially late-wave offer variety.

## Remaining game work

XP-earned stat selection is implemented and tested; see LEVEL_UP_READINESS.md for the upgrade flow and verification. Balance of offer prices and build power still needs multi-wave playtesting with real players. The shop itself does not grant persistent currency in Studio.
