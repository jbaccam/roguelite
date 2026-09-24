# Shop gameplay readiness

Updated 2026-09-23. The [Brotato shop reference](https://brotato.wiki.spellsandguns.com/Shop) informed the pacing and offer rules; this game keeps its own characters, weapons, items, shards, and combat values.

## Current shop rules

- Four server-owned offers. Shops 1–2 have two weapons and two items. Shops 3–5 guarantee one weapon. Later slots roll 35% weapon and 65% item.
- Tier 2 starts on wave 2, Tier 3 on wave 4, Tier 4 on wave 8. The server checks Tier 4, then 3, then 2; Luck raises those chances within caps of 8%, 25%, and 60%. The underlying per-wave growth is 0.23%, 2%, and 6% respectively.
- Owned weapon identities get a 20% pool preference. Owned weapon home classes get a 15% preference plus an early-shop bonus. Items get a small 5% preference for class-appropriate build tags. The general pool always remains available.
- A reroll keeps locked offers and their price, avoids the previous four offers, and avoids duplicate catalog entries in the current set. Buying all four refills the shop for free. Reroll costs rise with the wave and each reroll, then reset the next wave.
- Shop inflation follows base price plus wave and 10% of base price per wave. Recycled weapons still return 50% of their actual purchase cost. This is intentionally more forgiving than the reference because this game has no crate item economy.
- Purchases, copy caps, weapons, combining, locks, prices, and the phase are validated on the server. No paid purchase changes shop odds. Studio practice does not write persistent rewards.
- Common shop cards have no rarity outline. Higher tiers use dark colored fills with an outline. The overall shop background and gray panels are darker.

## Build paths supported by the catalog

| Build | Working ingredients |
| --- | --- |
| Burn spread | Molotov or Lighter, Microwaved Marshmallow, Grandma's Oven Mitt |
| Poison | Fart Gun or Toxic Barrel, Stinky Sock |
| Lightning | Magic Staff, Mjolnir, or Battery Pack; Tinfoil Antlers adds targets, Alien Battery boosts chain damage |
| Projectiles | Shotgun, Deck of Cards, Draco, or Nail Gun with Two Straws, Sharp Pencil, or Bouncy Ball where compatible |
| Critical hits | Fast direct-hit weapons, Broken Glasses, Tooth Fairy's Collection |
| Durable melee | Brawler weapons, Pot Lid or Safety Helmet, Cracked Burial Mask, Bandage Roll, Vampire Fang, Bubble Wrap Vest |

The server caps extra projectiles, bounce, pierce, lightning targets, and first-hit blocks. Status boosters do not create their status: Tinfoil Antlers now requires a lightning source.

## Art roster decisions

- **Skip Manager Badge art.** It duplicated Bone Crown's elite/boss bonus and has been removed from the shop. The current roster has 37 passives.
- **Keep all other item art in progress.** Bouncy Ball and Bubble Wrap Vest moved to Tier 4, giving the highest rarity three distinct items without asking for new art.
- Support Potato now adds a small pickup-radius bonus alongside health, separating it from cheap pure-HP Emergency Cheese. Cracked Burial Mask combines armor with contact resistance. Alien Battery combines a smaller attack-speed bonus with stronger lightning chains. Their images remain useful.
- No additional item images are needed for this shop pass. Distinct new effects should wait for play balance data, especially late-wave offer variety.

## Remaining game work

XP-earned stat selection is implemented and tested; see LEVEL_UP_READINESS.md for the upgrade flow and verification. Balance of offer prices and build power still needs multi-wave playtesting with real players. The shop itself does not grant persistent currency in Studio.
