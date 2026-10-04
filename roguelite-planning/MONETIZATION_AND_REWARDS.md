# Monetization, Chests, and Reward Economy

**Status:** Planning proposal  
**Updated:** 2026-09-26  
**Confirmed direction:** Purchases may provide bounded, transparent convenience, early access to earnable sidegrades, expression, and the approved death-screen revive (unlimited uses, the price doubling each time up to 1040 R$). They must not sell exclusive or uncapped combat power, and must not sell random gameplay rewards.

Progression itself is defined in [PROGRESSION_AND_SESSION_FLOW.md](PROGRESSION_AND_SESSION_FLOW.md): keys from waves survived, chests with weapon and armor copies, copies raising starting tiers, and achievement unlocks.

## Direction change — 2026-09-27 (user decision, implemented in Studio)

The user wants chests to be the main spend: **emeralds** (premium currency, sold for Robux) open chests, and in-run **shop and upgrade rerolls** are sold for Robux. This supersedes the "never sell keys/chests/rerolls" defaults below; keys themselves are still earned only.

Implemented (`studio-prototype/combat/MonetizationConfig.luau`, `ChestConfig.luau`, `ProfileService.luau`, `RogueliteMeta.server.luau`):

- Developer products: Revive 65 / 130 / 260 / 520 / 1040 (one product per price step), Shop Reroll 15, Upgrade Reroll 15, emerald packs 100/550/1200/2600 for 99/449/899/1799, Starter Pack 199 (300 emeralds + Royal Chest, once), early classes 149 each (or 400 emeralds). VIP game pass 399. Robux values are placeholders; Roblox charges the dashboard price.
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

## Gifting — 2026-10-04 (user: "add gifting to the store, like be able to buy stuff for other people")

You pay, someone else gets it. Example: Ben gifts Ana a Starter Pack: Ben pays 49 R$ and sees "Gift sent to Ana!"; Ana gets 1,500 emeralds, 2 Legendary Chests and 5 rerolls with a **GIFT FROM BEN** popup.

- **Who:** anyone in your server, or any Roblox friend (online or not). Never yourself (Studio allows it for testing).
- **What:** every developer product in the store, including one-time packs, classes and Godly bundles (the Godly Starter carries your pick). Not revives, in-run rerolls or banish (`noGift` in `MonetizationConfig`), and not game passes: Roblox can't gift those, so VIP and Quick Open have no GIFT button.
- **Store:** GIFT next to BUY (in the corner of class cards) opens a picker: players here first, then friends (online first), headshots and a search box, then "Gift Starter Pack to Ana?" with what they get and the price. Players here who already own that one-time pack, Godly bundle or class are greyed out.
- **Delivery:** right away if they're in the lobby of any server; in a run, when they're back in the lobby; offline, on their next join. A gift they can't receive as itself (e.g. a second Starter Pack, which we can't check for offline friends) pays its Robux value in emeralds, as receipts already do (49 R$ → 502).
- **Server (`RogueliteMeta`, "Gifting"):** GIFT saves an intent (`RogueliteGiftIntent_v1`, key `u_<buyer>`, 10 minutes to pay), then opens the buyer's normal prompt. The receipt binds that intent to its PurchaseId, writes the gift to `RogueliteGiftInbox_v1` (key `u_<recipient>`, once per receipt) and only then grants the receipt, so failures retry. The recipient's server grants each gift, records `gift:<PurchaseId>` with the receipts, saves, and only then removes it from the inbox: a crash delivers again and the record stops a second grant. MessagingService (`Gift:<userId>`) only speeds it up; without it, gifts arrive on the next join.
- **Studio:** intents and inboxes stay in memory (the profile rule: `EnableStudioDataStores`). The admin panel's Waves tab has **Simulate gift to me** (a fake Starter Pack from "Studio test"; the second one pays emeralds). Pure checks: `combat/GiftTests.luau`.

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

- When the player dies, show **REVIVE** and **LEAVE RUN**.
- REVIVE opens a Developer Product prompt. **No limit per run, and the price doubles each time** (user, 2026-09-28; built 2026-10-02): the nth revive in a run uses product `Revive1`…`Revive5` = 65 / 130 / 260 / 520 / 1040 R$, and from the 5th on it stays 1040. The count resets each run. The death screen shows this revive's price and the next one's ("next one R$ 130").
- The client only asks for "a revive"; the server picks the price step from its own count, so a client can't ask for a cheaper one.
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
- Boss skips, or any mid-run offer other than the doubling-price revive (capped at 1040 R$ each)
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
