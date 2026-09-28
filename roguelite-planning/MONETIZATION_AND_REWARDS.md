# Monetization, Chests, and Reward Economy

**Status:** Planning proposal  
**Updated:** 2026-09-26  
**Confirmed direction:** Purchases may provide bounded, transparent convenience, early access to earnable sidegrades, expression, and the approved limited death-screen revive. They must not sell exclusive or uncapped combat power, and must not sell random gameplay rewards.

Progression itself is defined in [PROGRESSION_AND_SESSION_FLOW.md](PROGRESSION_AND_SESSION_FLOW.md): keys from waves survived, chests with weapon and armor copies, copies raising starting tiers, and achievement unlocks.

## Direction change — 2026-09-27 (user decision, implemented in Studio)

The user wants chests to be the main spend: **emeralds** (premium currency, sold for Robux) open chests, and in-run **shop and upgrade rerolls** are sold for Robux. This supersedes the "never sell keys/chests/rerolls" defaults below; keys themselves are still earned only.

Implemented (`studio-prototype/combat/MonetizationConfig.luau`, `ChestConfig.luau`, `ProfileService.luau`, `RogueliteMeta.server.luau`):

- Developer products: Revive 65, Shop Reroll 15, Upgrade Reroll 15, emerald packs 100/550/1200/2600 for 99/449/899/1799, Starter Pack 199 (300 emeralds + Royal Chest, once), early classes 149 each (or 400 emeralds). VIP game pass 399. Robux values are placeholders; Roblox charges the dashboard price.
- Chests: class chests (3 keys or 60 emeralds, 3 weapons) and a Royal Chest (250 emeralds, 8 weapons from all 36). Exact per-weapon odds are shown before opening. Pick-your-weapon every 10th chest per type.
- **Policy:** rerolls and emerald-opened chests are paid random items. `PolicyService.ArePaidRandomItemsRestricted` players never see or can use them (server-enforced); odds are always displayed.
- Receipts are idempotent (processed PurchaseIds stored in the profile). Grants happen only in `ProcessReceipt`; a revive bought after it is no longer usable is refunded as 50 emeralds.
- **Setup still required:** create each developer product/pass in the Creator Dashboard and paste its ID into `MonetizationConfig.luau` (ID 0 = not for sale in live servers; Studio simulates the grant in memory only). Enable Studio API access to DataStores only if you intend to test saving (`workspace:SetAttribute('EnableStudioDataStores',true)`).

## Store expansion — 2026-09-27 (inspired by the user's reference shop)

Store is now four tabs (DAILY, BUNDLES, CHESTS, EMERALDS) with key/emerald counters and **+** buttons. New in `MonetizationConfig.luau` (all prices placeholders):

| Tab | What | Price |
| --- | --- | --- |
| Daily | 5 deals per UTC day: 1 free (10 keys) + 4 weapon-upgrade deals for keys or emeralds; VIP daily free Royal Chest | keys / emeralds |
| Bundles | Starter Pack (150 emeralds, Royal Chest, 5 rerolls; once) | R$ 49 |
| Bundles | Arsenal Bundle (+3 upgrades to all 6 class starters, 500 emeralds) | R$ 499 |
| Bundles | VIP pass (+25% run keys, daily Royal Chest, open ×10) | R$ 499 |
| Bundles | Quick Open pass (open 10 chests at once) | R$ 149 |
| Bundles | Reroll packs 5 / 15, Banish packs 5 / 15 (saved, used in runs) | R$ 59 / 149, 79 / 199 |
| Chests | Royal Chest ×1 / ×5 / ×12; Mega Chest Bundle (15 Royal, 3000 emeralds, 25 rerolls, 10 banishes) | R$ 149 / 599 / 1299; 2999 |
| Emeralds | 100 / 550 / 1200 / 2600 (labelled +21% / +32% / +43% more) and a codes box | R$ 99–1799 |

In-run: level-up cards have **BANISH** (removes that stat for the run, replaces the card) and the reroll buttons use stored rerolls/banishes before prompting Robux. Single Banish R$ 19, single reroll R$ 15. Codes live server-side in `ProfileService.luau` (RELEASE, CHESTS, REROLL). Chest packs, rerolls and banishes are hidden where paid random items are restricted.

## Product philosophy

The paid offer should feel helpful without making ordinary play feel pointless. A paying player may unlock a class sooner or look different, but a free player must be able to reach the same weapons, armor, tiers and maps, win every map, and build equally powerful runs.

The dividing line is:

- **Acceptable:** "I reached this class sooner," or "my pickup effect looks cooler."
- **Not acceptable:** "I bought keys and got Tier IV first," "I bought better luck during the run," or "this map effectively requires payment."

## Why keys and chests aren't sold

Chests give **random** weapon and armor copies, and those copies raise starting power. Roblox's paid-random-item rules also cover Robux that indirectly buys the random outcome: keys, gems, rerolls or boosters used to open it. Selling keys (or a key multiplier) would mean:

- showing every outcome with its actual numerical odds before purchase;
- checking `PolicyService:GetPolicyInfoForPlayerAsync()` per player and hiding the product where `ArePaidRandomItemsRestricted` is true;
- selling random power, which conflicts with the project's fairness rules.

**Launch default:** Keys, chests, chest pity and key multipliers are earned only. Keeping all random rewards free keeps chests clear of those rules.

## Hard boundaries

- All classes, weapons, armor sets and passives are earnable through normal play.
- Paid class unlocks grant the normal class early, never a stronger version.
- No paid keys, chests, chest pity progress, or key/reward multipliers.
- No paid weapon or armor copies or starting tiers (**open question**; see below).
- The one active-run purchase is the death-screen revive.
- No paid run XP, shards, rerolls, shop discounts, extra weapon slots, temporary stats, altered drops or altered shop odds.
- No purchase is required to win a map or take part meaningfully in co-op.
- Difficulty and grind cannot be deliberately worsened to pressure a purchase.

## Currency separation

| Currency/resource | Saved? | Purpose | Purchasable? |
| --- | --- | --- | --- |
| Run XP | No | Level-up stat choices between waves | Never |
| Crystal shards | No | Run shop weapons, items and rerolls | Never |
| Keys | Yes | Open chests | Never (random outcome) |
| Gems | Yes | Premium currency for the guaranteed catalog | Sold directly; never spent on keys, chests or anything random |

## Recommended launch catalog

### Gem packs

Premium currency for the guaranteed catalog below. Contents and prices are always shown up front.

### VIP pass

- two extra saved loadout presets;
- a VIP nameplate, lobby pose and cosmetic set;
- a small daily Gem grant.

The pass never changes keys, chest odds, run XP, drops, shop inventory, damage, health or luck.

### Direct early class unlock

- Immediate access to Thrower, Juggler or Handyman.
- The same class stays unlockable through its achievement.
- Paid classes obey the same balance budget as free starting classes. Don't advertise one as "the best".

### One-time starter pack

A fixed, guaranteed pack: one early class unlock of the player's choice, a disclosed amount of Gems, and an exclusive nameplate or lobby pose. No keys, chests or copies.

### Buyable death-screen revive

- When the player dies, show **REVIVE** and **GIVE UP**.
- REVIVE opens a repeatable Developer Product prompt. The recommended first price test is about **65 Robux**.
- Limited to one paid revive per player per run.
- Restores 50% health, grants three seconds of invulnerability, pushes nearby enemies away, and resumes the same wave and boss state.
- The server grants it only through validated `MarketplaceService.ProcessReceipt` handling.
- A revived win counts, pays normal keys, and records its revive count for leaderboard filtering.
- Don't sell damage, temporary stats or another rescue offer alongside the revive.
- Never shown during the tutorial.

### Customization

Players keep their Roblox avatar and repeatedly see pickup streams, enemy defeats, the HUD, the lobby and result celebrations. Good products:

- defeat effects, pickup trails, magnetic stream styles and short sound packs;
- emotes, lobby poses, spawn animations, nameplates, titles, banners, profile frames, UI themes and victory celebrations;
- cosmetic armor *looks* that change appearance only, if they don't hide the armor set's identity or hitbox.

Cosmetics cannot disguise weapon behavior, enlarge projectiles, obscure danger cues, or make paid sound effects louder than gameplay information.

### Later: cosmetic progression track

A free-and-paid track with cosmetics only. The complete track is visible before purchase, and permanent or returning tracks are preferred over harsh fear-of-missing-out pressure.

## Open decision: selling copies or starting tiers

A direct, **non-random** purchase of a chosen weapon or armor copy is technically allowed by the project's "bounded acceleration" rule: the tier is capped at IV and everything stays earnable. It still sells the exact power the map ladder is balanced around, which would read as pay-to-win to players. **Default: don't sell at launch.** Revisit only after free pacing is measured.

## Products not to sell

- Keys, chests, pity progress, or key/reward multipliers
- Direct damage, health, armor, attack speed, movement speed, luck or pickup-range upgrades
- Run XP, starting levels or shards
- Shop rerolls, locks, discounts or improved rarity odds
- Extra weapon or passive slots
- Unlimited or repeated revive chains, boss skips, or any other mid-run offer
- Paid-only classes, weapons, armor sets or maps
- Any product framed or balanced as necessary for progression

## Technical and policy requirements

- Grant repeatable purchases only through validated `MarketplaceService.ProcessReceipt` handling.
- Store entitlements and receipt results idempotently.
- Never trust client claims that a purchase completed.
- Keep a server-side product catalog with stable IDs and explicit grant behavior.
- Show exact guaranteed contents before purchase.
- If any paid random item is ever introduced, show actual numerical odds and handle `PolicyService` eligibility per player.
- Studio purchase tests must never grant production entitlements or persistent rewards.

## Balance questions to test

- How many runs does each achievement-gated class take a free player?
- Does the chest pity interval stop bad luck from blocking a wanted starter?
- Are paid early classes genuine sidegrades?
- Does co-op stay comfortable when players with different starting tiers play together?
- Is the catalog valuable enough without selling progression? If not, prefer more cosmetics over selling power.

## Sources

- Roblox Creator Hub — Monetization: https://create.roblox.com/docs/production/monetization
- Roblox Creator Hub — Developer Products: https://create.roblox.com/docs/production/monetization/developer-products
- Roblox Creator Hub — Paid Random Items: https://create.roblox.com/docs/production/monetization/paid-random-items
