# Lobby, Run, and Progression Structure

**Status:** Recommended structure; classes confirmed, exact roster and wave timings require approval  
**Goal:** Give every run a fresh build while preserving meaningful reasons to clear chapters, master weapons, unlock options, and return to the lobby.

## The three progression layers

### 1. Account and arsenal progression — permanent

This represents the player's overall game progress:

- account level and XP;
- unlocked chapters and map themes;
- unlocked difficulty levels;
- owned weapon blueprints and their capped Permanent Weapon Levels;
- weapons and items added to the possible run pool;
- unlocked classes/loadout perks, if approved;
- weapon and class mastery records;
- challenges, achievements, best clears, and collection completion;
- persistent earned currency;
- titles, pickup effects, defeat effects, UI themes, lobby poses, and emotes.

Account progression expands options and provides a modest head start. It should not become an uncapped damage tree that makes early chapters play themselves.

### Persistent weapon collection

Weapons are earnable, but they are not all granted automatically. Every weapon has three permanent records:

1. **Blueprint ownership:** allows the weapon to be selected as the guaranteed starting weapon and adds it to the normal run-shop pool.
2. **Permanent Weapon Level:** a capped Level 1–10 improvement purchased with Universal Parts plus persistent Coins.
3. **Mastery:** experience earned by actually using the weapon; unlocks Coins, Universal Parts, challenges, titles, badges, and profile records rather than another stacking damage track.

Permanent Weapon Level provides a real but bounded advantage. Initial target: approximately 1–1.5% base effectiveness per level, capped around 10–12% at maximum. The bonus applies whenever that weapon is used, including copies bought in the run shop. It does not grant permanent Run Tiers, additional projectiles, or extra weapon slots.

Cases earned after play can award a new blueprint or Universal Parts. A duplicate blueprint converts into Universal Parts. Players can also target a weapon through a deterministic Coin shop or mastery objective, so bad case luck never becomes the only route.

The player still brings only one guaranteed starting weapon into a chapter. Every additional weapon, duplicate, tier combination, passive item, and temporary stat must be rebuilt during that run.

### 2. Run progression — temporary

This exists only inside the current chapter:

- current run level and XP;
- weapons purchased during the run;
- weapon tiers and combinations;
- passive items, including items that modify the Armor stat;
- stat upgrades;
- run materials used in the shop;
- reroll prices and locked shop offers;
- temporary buffs, consumables, and evolution eligibility;
- current health and revive state.

These reset after victory, defeat, leaving the run, or starting another chapter.

### 3. Mastery progression — permanent record and sidegrades

Mastery rewards using different parts of the game without carrying the completed run build forward:

- Weapon mastery increases when that weapon is used, evolved, or clears a chapter.
- Class mastery increases when clearing chapters with that class/loadout perk.
- Mastery unlocks Coins, Universal Parts, titles, profile badges, challenges, and collection records.
- Raw permanent effectiveness comes from the separate capped Permanent Weapon Level; Mastery does not stack damage endlessly.

## What saves and what resets

| Data | Saved permanently? | Notes |
| --- | --- | --- |
| Account level | Yes | Main broad progression track |
| Chapter completion | Yes | Unlocks later chapters and difficulty |
| Earned persistent currency | Yes | Separate from run shop materials |
| Weapon blueprints | Yes | Determines starter availability and normal run-shop pool |
| Permanent Weapon Level and Universal Parts | Yes | Capped modest bonus; Run Tiers remain temporary |
| Weapon mastery | Yes | Milestone resources, challenges, titles, badges, and records |
| Classes/loadout perks | Yes | Same Roblox avatar; no authored character model required |
| Customization | Yes | Pickup/defeat effects, UI themes, emotes, titles, nameplates, and lobby poses |
| Run weapons | No | Reset after the chapter |
| Weapon tiers | No | Reset after the chapter |
| Run items/passives | No | Reset after the chapter |
| Run level and XP | No | Reset after the chapter |
| Run shop materials | No | Spent during the run and discarded afterward |
| Temporary stats | No | Reset after the chapter |
| Best score/time/stats | Yes | Historical record only |

## Recommended complete player flow

```text
Lobby
  → form party or play solo
  → select unlocked chapter
  → select difficulty
  → select class
  → select starting weapon
  → enter reserved run
  → combat wave
  → automatic pickup + level choices + shop
  → repeat through elite/horde waves
  → final boss
  → victory or defeat results
  → grant permanent rewards once
  → return to lobby
```

## First-time player journey

### First join and tutorial

1. Load the player's normal Roblox avatar into a compact lobby.
2. Give three starter classes representing distinct styles: **Brawler**, **Gunner**, and **Mage**. Their included signature blueprints are **Frying Pan**, **Glock**, and **Magic Staff**.
3. Let the player choose a tutorial class; its signature weapon is automatically equipped. All three starter classes and blueprints remain owned.
4. Launch a short three-wave tutorial in Pine Valley rather than explaining every lobby station first.
5. Wave 1 teaches movement, automatic attacks, XP drops, and magnetic pickup.
6. The first banked level guarantees a simple choice between Power, attack speed, and movement speed.
7. Wave 2 ends with a scripted shop containing a second weapon, one passive item, and a duplicate of the starter so combining is demonstrated.
8. Wave 3 introduces one telegraphed stronger mob and a small tutorial boss.
9. Return to a result screen that grants Coins, account XP, a guaranteed starter case, and enough Parts to perform the first Permanent Weapon Level upgrade.

The shop is not shown until the player has experienced one wave. Monetization prompts do not appear during the tutorial.

### First lobby return

The result screen leads the player through only four actions:

1. Open the earned starter case.
2. Convert its result into a new blueprint or weapon Parts.
3. Upgrade one owned weapon from Permanent Weapon Level 1 to Level 2.
4. Select Chapter 1, a class, and the starting weapon, then launch the first full run.

After this guided sequence, the wider lobby exposes chapter selection, Arsenal/Weapon Upgrades, Classes, Cases, Quests, Cosmetics, and the Robux Shop. The player may ignore every station and use a quick-play panel.

### First full chapter

- Select a class, then choose one owned starting weapon assigned to that class. A newly unlocked class defaults to its signature weapon.
- Enter with that starting weapon at its saved Permanent Weapon Level.
- Fight eight waves. XP banks free end-of-wave stat choices; temporary materials fund the four-card shop.
- Hold up to five active weapons. Same-weapon, same-tier copies combine through four temporary tiers.
- Passive shop items do not use active-weapon slots; individual passives can have sensible copy caps.
- An elite can drop one free in-run item crate that resolves during intermission.
- Defeat the final boss or fail the chapter, then return to results.

### Results and the second run

The complete run build disappears: temporary weapon tiers, extra weapons, passives, chosen stats, XP, and run materials reset.

The account keeps:

- blueprint ownership and Permanent Weapon Levels;
- Weapon Parts and persistent Coins;
- account, weapon, and class XP;
- chapter/difficulty clears;
- case progress and unopened earned cases;
- quest, achievement, and challenge progress;
- cosmetics and settings.

A victory unlocks the next chapter and gives the full reward package. A defeat gives reduced account XP, Coins, mastery, and case-meter progress so the session is not wasted. The player can upgrade the starter, change class or weapon, open an earned case, and immediately retry or choose another chapter.

## Lobby functions

The lobby should let players:

- see chapter progress and rewards;
- select an available chapter and difficulty;
- select a starting weapon;
- select a class;
- inspect weapon and item unlocks;
- see mastery challenges and recent progress;
- equip pickup/defeat effects, UI themes, emotes, titles, nameplates, and lobby poses;
- form a party, ready up, or launch solo;
- revisit completed chapters for farming or challenges.

Do not force players to walk between many separate upgrade stations for basic actions. The lobby can be visually explorable while keeping chapter selection and ready-up quick.

## Recommended eight-wave chapter

The supplied Brotato structure is useful, but copying 20 waves would conflict with the preferred eight-minute chapter. A compact eight-wave structure can preserve the combat/shop rhythm:

| Wave | Combat target | Role |
| ---: | ---: | --- |
| 1 | 35 seconds | Establish basic mob and earn first shop budget |
| 2 | 40 seconds | Introduce second pressure type |
| 3 | 45 seconds | Build begins to specialize |
| 4 | 45 seconds | Elite wave |
| 5 | 50 seconds | Denser mixed wave |
| 6 | 50 seconds | Horde wave |
| 7 | 55 seconds | Final build check |
| 8 | Up to 70 seconds | Boss wave; ends immediately on boss defeat |

Seven intermissions at roughly 10–12 seconds place the normal wall-clock target near eight minutes. Pending level-up choices can extend that time, so multiplayer intermissions need a maximum timer and ready button.

These timings are a starting hypothesis. The target is a satisfying eight-minute experience, not loyalty to the table.

## End-of-wave intermission

**Design decision:** Leveling does not stop combat. XP earned during a wave fills the meter and queues level-up rewards, but stat cards appear only after that wave ends. This matches the selected wave/shop structure and avoids repeated menus while the player is dodging a dense swarm.

When a wave ends:

1. Remaining XP, run materials, consumables, and eligible loot pull magnetically into the player.
2. Every queued level-up resolves first, one concise stat choice at a time.
3. The shop opens with four weapons/items after all stat choices are complete.
4. Players may buy, sell/recycle, reroll, or lock an offer.
5. The next wave begins when everyone is ready or the timer expires.

### During-combat level feedback

- Crossing an XP threshold plays a short level-up sound and a compact `LEVEL UP — CHOICE BANKED` notification.
- The HUD shows the number of pending stat choices, such as `2 UPGRADES`.
- No selection window, slow motion, or full-screen overlay appears during combat.
- XP continues filling toward later levels normally.
- XP collected by the end-of-wave magnet can create additional queued choices before the intermission screen opens.

### Stat-choice step

- Each earned level grants one free stat increase; it does not spend shop materials.
- Show three large stat cards and choose one. Resolve multiple earned levels sequentially.
- Cards display the exact before-and-after value, rarity, and any cap.
- A limited stat refresh can replace all three cards. Its availability is separate from the shop reroll price.
- Offers include core stats such as Power, attack speed, critical chance, armor, dodge, speed, regeneration, pickup range, and luck.
- Weapon-specific behaviors such as extra bounce, piercing, or projectile count normally come from weapons and passive items in the shop rather than generic level-up cards.

### Shop screen structure

Use the supplied Brotato screenshot as information-architecture inspiration, not a screen to copy exactly:

- four large offer cards across the main area;
- item name, tags, important numerical changes, price, and lock control on each card;
- run-material total and reroll price kept visually prominent;
- current weapons and passive inventory visible along the bottom;
- a collapsible live-stat summary on the side;
- a large ready/next-wave control after the player finishes shopping.

The stat-choice step and shop are visually distinct. This prevents the player from mistaking a free level reward for a purchase.

### Multiplayer handling

- Each player receives a personal shop and build choices.
- Combat resumes only when all active players are ready or the timer ends.
- A player who times out keeps unspent materials and receives no automatic purchase.
- Any unresolved stat choices use the player's currently highlighted card or a safe valid default so the team cannot be held indefinitely.
- Other players can see ready status, not private shop details unless sharing is intentionally supported.

## Run currencies

Use different names and icons so players never confuse temporary and permanent money:

| Resource | Lifetime | Purpose |
| --- | --- | --- |
| XP | Current run | Produces stat/upgrade choices at intermission |
| Scrap, Materials, or another run currency | Current run | Purchases weapons and items in the intermission shop |
| Coins or another account currency | Permanent | Unlocks content or cosmetics in the lobby |
| Rare chapter reward | Permanent | Specific unlock recipes, cosmetics, or achievement progress |

Persistent coins should be granted at the result screen from server-calculated performance, not copied one-for-one from every temporary run material.

## Shop proposal

- Four offers per intermission.
- Mix of weapons and passive items.
- Early shops guarantee enough weapon offers to establish a build.
- Rerolls cost increasing amounts during that intermission and reset next wave.
- One offer may be locked for the next intermission.
- Every unlocked weapon remains eligible regardless of selected class unless an explicitly labeled challenge rule says otherwise.
- Equipped weapon types, shared combat tags, and selected class influence weapon weights without hard-locking the pool.
- Capped or unusable choices are removed from the pool.
- Run currency cannot be purchased with Robux.

### Weapon-slot selection pools

First decide whether an offer slot contains a weapon or passive item. The first two shops contain exactly two weapons and two passive items. Shops after Waves 3 and 4 guarantee at least one weapon. Later slots use the ordinary weapon/item rate.

Whenever a slot is designated as a weapon, choose its source pool first:

| Source pool | Initial weight | Purpose |
| --- | ---: | --- |
| Exact equipped weapon | 30% | Makes duplicate combining achievable in an eight-wave run |
| Shared combat tag | 25% | Supports related weapons, including cross-class combinations |
| Selected class | 20% | Reinforces class identity without enforcing it |
| All unlocked weapons | 25% | Preserves experimentation and unexpected hybrid builds |

These are starting test values, not copied Brotato numbers. Pool selection occurs before choosing an individual weapon, so unlocking additional blueprints does not reduce the 30% exact-weapon share; it only expands the relevant pool.

Examples for a Gunner holding a Glock:

- Another Glock can roll from the exact-weapon pool.
- Draco or Fart Gun can roll from Gunner or shared `Gun` tags.
- Nail Gun can roll through shared `Gun`, `Rapid`, or `Projectile` tags even though its home class is Handyman.
- Kunais can roll through their projectile/critical tags or from the global pool.
- Any other unlocked weapon can roll from the global pool.

### Build protection and transparency

- The player may mark one equipped weapon as **Tracked** in the shop.
- If the tracked weapon fails to appear across two completed intermissions, the next intermission's guaranteed weapon slot offers a legal copy unless that weapon is already max Run Tier.
- Rerolls do not advance this protection counter.
- Each weapon card displays why it was eligible: `DUPLICATE`, `CLASS`, `TAG MATCH`, or `WILDCARD`.
- An `Odds & Pools` panel shows the current source weights and every eligible unlocked weapon.
- Luck affects offer rarity and disclosed reward-drop chances; it does **not** affect weapon identity, class matching, tag matching, or tracked-weapon protection.
- Newly unlocked weapons never silently make exact duplicates less likely.

### Class affinity without restrictions

Every weapon has one **home class** plus multiple **combat tags**. Home class determines starting-weapon eligibility and class-affinity count. Combat tags determine which weapon and item bonuses can affect it.

- Two equipped home-class weapons activate the class's first affinity bonus.
- Four activate its stronger affinity bonus.
- Five is not required, deliberately leaving one flex slot for an off-class weapon.
- An off-class weapon works at full base strength and receives all applicable ordinary stats and tag bonuses.
- It simply does not add a point toward the selected class's 2-piece/4-piece affinity milestones.
- A cross-class weapon can still benefit from the class's tag-specific passive. For example, Gunner bonuses affecting `Gun` weapons also affect the Handyman Nail Gun.

Affinity bonuses should strengthen a style rather than be generic damage taxes. Candidate directions include magazine/reload behavior for Gunner, orbit rhythm for Juggler, deployable uptime for Handyman, returning/splash behavior for Thrower, close-range cadence for Brawler, and status/echo behavior for Mage.

### Launch pool size

A reroll shop needs variety, but too many unweighted weapons make duplicate combining frustrating. Equal class pools and class weighting let the total roster grow without ruining merges. Target:

- **36 launch weapons: six classes with six weapons each**;
- **30–40 passive items** so shop decisions are not mostly weapon cards;
- five active weapon slots and four temporary tiers;
- at least one weapon offer in ordinary early shops and two in the first shop;
- explicit source-pool weights that prioritize exact equipped copies, then shared tags, class affinity, and finally the full unlocked pool.

Keep development even: six signature weapons in the prototype, 12 weapons in the vertical slice, and 30 at launch. Later updates add the same number of weapons to every class before changing the advertised class counts.

### Weapon combining

If the Brotato-style system is approved:

- Two identical weapons of the same tier automatically combine into the next tier.
- Combining is free.
- A duplicate purchased while slots are full may auto-combine if a legal pair exists.
- Four tiers are enough for an eight-wave run.
- Every higher tier changes at least one visible behavior, not only damage.
- Example: two Glocks become **Glock + Extended Clip**; two Extended Clip Glocks become **Glock with Switch**; two Switch Glocks become **Akimbo Switches**.
- All tiers reset after the chapter.

This replaces the earlier direct Level 1–5 weapon proposal. Do not run both systems simultaneously.

## Confirmed class direction

Different authored characters are unnecessary. A compact class system provides long-term unlocks while everyone keeps their Roblox avatar.

Classes are data rules, not new models, dialogue, or animation sets.

| Class | Direction | Signature weapon |
| --- | --- | --- |
| Brawler | Close-range, rapid melee, and critical attacks | Frying Pan |
| Gunner | Fire rate, magazines, piercing, and ranged attacks | Glock |
| Thrower | Returning projectiles, splash, and status effects | Boomerang |
| Juggler | Orbiting objects, movement, and collision effects | Boxing Gloves |
| Handyman | Construction tools, deployables, and control | Nail Gun |
| Mage | Magic, elemental effects, and rare mythological weapons | Magic Staff |

Each class receives exactly five launch weapons. The detailed proposed allocation lives in `BRAINSTORM_FUNNY_GEAR.md`. Exact class bonuses and tradeoffs remain to be balanced.

### Unlocking classes

Do not require every player to grind a class they dislike just to reach another one. Prefer multiple transparent unlock paths:

- account-level milestone;
- complete a chapter or difficulty;
- evolve a related weapon;
- achieve a build milestone;
- reach modest mastery with a neighboring class.

Start with Brawler, Gunner, and Mage. Thrower, Juggler, and Handyman unlock through play or direct early purchase without forming one mandatory linear ladder.

### Class mastery

Mastery can unlock:

- class badge/title;
- lobby pose or aura;
- class-themed title, profile badge, lobby pose, or UI theme;
- alternate starting-weapon choices;
- new related item added to the global run pool;
- a challenge variant.

Avoid permanent percentage bonuses at every mastery level. Otherwise longtime players and new friends cannot meaningfully play the same chapter together.

## Chapter progression

- Clearing a chapter unlocks the next chapter.
- Higher chapters provide more account XP and persistent reward progress.
- Previously cleared chapters remain replayable.
- Open, corridor, and enclosed maps rotate independently from mob rosters.
- Difficulty levels unlock after milestone clears.
- Optional completion goals can reward mastery or cosmetics without blocking the next normal chapter.
- Failure still grants reduced account XP and valid mastery progress, but not a victory reward.

## Returning to the lobby

At the result screen, the server commits one idempotent reward receipt containing:

- victory/defeat;
- chapter and difficulty;
- account XP earned;
- persistent currency earned;
- weapon/class mastery earned;
- challenge and unlock progress;
- newly unlocked content;
- run summary statistics.

The player can replay, choose another chapter, or return to the lobby. Starting a new chapter creates a completely fresh run build.

## Endless mode

Endless mode should be deferred until the standard eight-wave chapter works. When added:

- it branches after the normal boss victory so the chapter clear is already secured;
- run build and shop economy continue;
- bosses return at authored intervals;
- leaderboard eligibility uses a fixed difficulty/ruleset;
- permanent reward farming receives diminishing or capped returns;
- leaving endless preserves the already-earned normal clear and valid rewards.

## Recommended decision package

1. Keep Roblox avatars; do not add authored character models.
2. Use a small class/loadout-perk system for replayability and unlock progression.
3. Use eight combat waves with short intermission shops.
4. Use XP for end-of-wave stat choices and temporary materials for shop purchases.
5. Choose a class, then one owned starting weapon belonging to that class.
6. Use Brotato-style automatic same-tier weapon combining, capped at four tiers.
7. Reset the complete combat build after every chapter.
8. Save chapters, unlocks, mastery, currency, achievements, and cosmetics.
9. Keep permanent progression mostly horizontal so old and new players can still play together.

## Open decisions

- Does armor provide temporary run power, permanent power, or persistent appearance only?
- Does XP produce stat upgrades only, or can level-ups also grant passive items?
- Is the eight-minute target measured including intermissions or only combat time?
- How many players can join one run?
