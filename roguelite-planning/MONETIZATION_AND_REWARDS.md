# Monetization, Crates, and Reward Economy

**Status:** Planning proposal  
**Confirmed direction:** Purchases may grant bounded gameplay advantages through faster persistent progression or early access to earnable sidegrades. They must not sell overwhelming, exclusive, or uncapped combat power.

## Product philosophy

The paid offer should feel helpful without making ordinary play feel pointless. A paying player may unlock build options sooner or progress an account somewhat faster, but a skilled free player must be able to access the same gameplay content, complete every chapter, and build equally powerful runs.

The dividing line is:

- **Acceptable:** “I reached this class or weapon sooner.”
- **Not acceptable:** “My paid version has higher damage,” “I bought better luck during the run,” or “this chapter effectively requires payment.”

## Hard boundaries

- All combat classes, weapons, and gameplay options are earnable through normal play. There is no armor-equipment system.
- Paid class and weapon unlocks grant the normal item early, never a stronger premium version.
- Paid Coins or universal Weapon Parts may shorten Permanent Weapon Level progression, but the same level cap and stats apply to everyone.
- Account boosts are modest, clearly disclosed, nonstacking, and capped.
- The one explicit active-chapter purchase is a death-screen revive. No other combat purchase is offered during a run.
- No paid run XP, run materials, shop rerolls, shop discounts, extra weapon slots, temporary stats, altered drops, or altered shop odds.
- No paid-exclusive combat content or uncapped permanent stat growth.
- No purchase is required to clear a chapter or participate meaningfully in co-op.
- Difficulty and grind cannot be deliberately worsened to pressure a purchase.

## Currency separation

| Currency/resource | Saved? | Purpose | Purchasable or boostable? |
| --- | --- | --- | --- |
| Run XP | No | End-of-wave stat choices | Never |
| Run materials | No | Intermission weapons and items | Never |
| Account XP | Yes | Account levels and unlock milestones | May receive a modest, nonstacking paid boost |
| Gameplay coins | Yes | Deterministic class, weapon, and feature unlocks | Fixed starter bundles or a modest earnings boost may be sold |
| Universal Parts | Yes | Upgrade any owned weapon's capped Permanent Weapon Level | Guaranteed Parts packs may be sold |
| Unlock token | Yes | Directly unlocks one eligible class or starter weapon | May be sold only for earnable sidegrades; player chooses the reward |
| Gems | Yes | Premium currency for guaranteed catalog offers and bundles | Sold directly; not used for undisclosed random rewards |
| Progression-track XP | Track record | Advances a visible free/premium reward track | May be boosted if the complete track is shown |

Persistent currency never converts into active-run materials. This keeps paid acceleration outside the eight-minute build and prevents someone from buying a winning shop sequence.

## Recommended paid advantages

### Supporter/VIP pass

A permanent, nonstacking pass could provide:

- **+20% account XP** from completed chapters;
- **+20% persistent Coin earnings**, calculated only after the run;
- one additional daily quest and a small daily Gem grant;
- two extra saved build/loadout presets;
- a supporter nameplate, lobby pose, and cosmetic set.

These percentages are initial balance targets, not confirmed values. The pass never changes run XP, enemy drops, shop inventory, damage, health, or luck.

### One-time starter pack

A fixed, guaranteed pack could contain:

- a disclosed amount of persistent Coins and Gems;
- one player-chosen class token;
- one player-chosen weapon blueprint token;
- a disclosed amount of Universal Parts;
- one exclusive nameplate or lobby pose.

The pack is a head start, not exclusive power. It cannot contain upgraded weapon tiers or random gameplay rewards.

### Direct early class unlock

- A player may buy immediate access to a specific class.
- The class remains unlockable through a clearly stated gameplay objective or coin price.
- Paid classes obey the same balance budget as free starting classes.
- Avoid advertising a class as the “best” or designing it to outperform the roster.

### Direct early starter-weapon unlock

- A player may unlock a specific weapon for the pre-run starting pool.
- The weapon is also earnable normally.
- The purchase grants its base version, not a permanent tier increase.
- The weapon must be a sidegrade that supports a build style, not a strict damage upgrade.

### Guaranteed Weapon Parts

- Sell a disclosed number of **Universal Parts** that the player assigns to an owned weapon.
- Parts accelerate the same capped Permanent Weapon Level 1–10 progression earned through play.
- A purchase never exceeds the ordinary rank cap or creates a paid version of the weapon.
- Show the exact resulting rank and stat change before confirmation.
- Offer small and medium packs rather than an unlimited ladder of escalating purchases.

### Persistent coin packs

- Coins may pay deterministic blueprint, class, and Permanent Weapon Level costs in the lobby.
- Coins cannot become run materials and cannot buy anything in an active chapter.
- The free earning rate must remain reasonable; paid Coins are a time skip, not access to a separate power system.

### Optional timed account booster

If repeatable boosters are used, one product may give roughly **+25% account XP and persistent coins** for a clearly stated duration. It must not stack with itself; use the larger of the timed boost or VIP boost rather than multiplying both.

This is more aggressive than the permanent VIP pass and should be tested carefully. It is not essential for launch.

### Buyable death-screen revive

- When the player dies, show **REVIVE** and **GIVE UP**.
- REVIVE opens a repeatable Developer Product purchase prompt; recommended initial price test is approximately **65 Robux**.
- Limit the launch version to one paid revive per player per chapter.
- A revive restores 50% health, grants three seconds of invulnerability, pushes nearby enemies away, and resumes the same wave and boss state.
- The server grants it only through validated `MarketplaceService.ProcessReceipt` handling.
- A revived victory counts, awards normal rewards, and records its revive count for challenge/leaderboard filtering.
- Do not sell damage, temporary stats, or another rescue offer alongside the revive.

## Gameplay crates

Gameplay cases may be earned from chapters, bosses, quests, or a visible repeat-clear meter. They can contain weapon blueprints, Weapon Parts, persistent Coins, unlock progress, or cosmetics.

Rules:

- Do not sell randomized gameplay crates for Robux at launch.
- Do not sell Robux keys for earned gameplay crates.
- Important classes and weapons must also have deterministic unlock paths.
- Show the reward pool, duplicate behavior, and progress meter.
- Duplicates convert into a useful deterministic currency.
- First-clear and major mastery rewards should usually be guaranteed rather than random.

This still allows fun earned loot without making paid power depend on gambling. If paid randomized cases are ever considered later, Roblox requires every final outcome and its actual numerical probability to be shown before purchase. The game must also check `PolicyService:GetPolicyInfoForPlayerAsync()` and block, hide, or replace paid random products when `ArePaidRandomItemsRestricted` is true. These rules also apply when Robux purchases keys, gems, rerolls, or another currency used for the random outcome. Guaranteed blueprint and Parts sales are therefore the preferred launch design.

## Earned crate ideas

### Chapter crate

- Earned for a first clear or by filling a repeat-clear meter.
- Contains persistent coins, cosmetic tickets, unlock fragments, or chapter-themed cosmetics.
- First-clear reward is shown before the chapter begins.

### Boss trophy crate

- Earned from boss or difficulty milestones.
- Contains boss cosmetics and a guaranteed amount of account progression.
- Major trophies are deterministic: Cyclops eye aura, Giant Crab shell shoulders, Pharaoh wrap trail, or Headless Knight title.

### Weapon or class mastery crate

- Earned through using that class or weapon.
- Mainly contains its skins, badges, banners, and mastery currency.
- If mastery unlocks gameplay, the required number of milestones is visible and does not rely solely on random drops.

## Direct customization

Customization remains valuable because players retain their Roblox avatar and repeatedly see pickup streams, enemy defeats, the HUD, the lobby, and result celebrations. The updated combat direction keeps equipped weapon models visible in a floating formation (see FLOATING_WEAPON_PRESENTATION.md), and some temporary passives appear as avatar accessories. Weapon skins remain outside the approved monetization scope; these presentation changes do not add paid skins or a separate armor-set system.

Good products include:

- defeat effects, pickup trails, magnetic stream styles, and short sound packs;
- emotes, lobby poses, spawn animations, nameplates, titles, banners, profile frames, UI themes, and victory celebrations;
- cosmetic class presentation bundles that do not change class stats.

Cosmetics cannot disguise weapon behavior, enlarge effective projectiles, obscure danger cues, or make paid sound effects louder than gameplay information.

## Cosmetic or progression track

A free-and-paid track may contain cosmetics, persistent coins, and deterministic unlock tokens. If gameplay progression appears on the paid lane:

- the same class or weapon must remain earnable outside the track;
- the paid lane accelerates access but does not grant stronger variants;
- the complete reward track is visible before purchase;
- ordinary play progresses at a reasonable rate;
- prefer permanent or returning tracks over harsh fear-of-missing-out pressure.

## Products not to sell

- Direct damage, health, armor, attack speed, movement speed, luck, or pickup-range upgrades
- Uncapped Permanent Weapon Levels or paid-only weapon-level bonuses
- Run XP, starting levels, or run materials
- Shop rerolls, locks, discounts, or improved rarity odds
- Extra active weapon or passive slots
- Unlimited/repeated revive chains, boss skips, or any emergency mid-run offer besides the approved revive
- Paid-only classes, weapons, evolutions, or maps
- Random paid gameplay crates at launch
- Boosts that stack without limit
- Any product framed or balanced as necessary for progression

## Technical and policy requirements

- Grant repeatable purchases only through validated `MarketplaceService.ProcessReceipt` handling.
- Store entitlements and receipt results idempotently.
- Never trust client claims that a purchase completed.
- Maintain a server-side product catalog with stable IDs and explicit grant behavior.
- Show the exact guaranteed reward and boost percentage before purchase.
- Paid randomized items, if ever introduced, require actual numerical outcome odds and per-player `PolicyService` eligibility handling.
- Studio purchase tests must never grant production entitlements or persistent rewards accidentally.

## Recommended launch catalog

Start small enough that we can evaluate whether the game is fun and the free progression rate is healthy:

1. Gem packs
2. VIP pass/subscription with account progression boosts, an extra daily quest, and daily Gems
3. One fixed starter pack with class and weapon choice tokens
4. Direct early unlocks for selected classes and weapons
5. Class Arsenal bundles containing one class and its six earnable blueprints
6. Small, medium, and large guaranteed Universal Parts and Coin packs
7. Rotating guaranteed daily deals
8. Defeat-effect, pickup-style, UI-theme, emote, and lobby-identity bundles
9. Premium progression track once enough finished content exists
10. One death-screen Revive Developer Product, initially limited to one per chapter

Do not launch with paid random gameplay crates or other mid-run purchases beyond the approved revive.

## Balance questions to test

- How many completed chapters does a free class or weapon unlock require?
- Does VIP save time without becoming the assumed baseline?
- Can a free player reach the full build pool in a satisfying timeframe?
- Are paid early-unlock weapons genuine sidegrades across multiple builds?
- Does co-op remain comfortable when paid and free accounts play together?
- Do players still value a purchase after all gameplay options are unlocked?

## Sources

- Roblox Creator Hub — Monetization: https://create.roblox.com/docs/production/monetization
- Roblox Creator Hub — Developer Products: https://create.roblox.com/docs/production/monetization/developer-products
- Roblox Creator Hub — Paid Random Items: https://create.roblox.com/docs/production/monetization/paid-random-items
