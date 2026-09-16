# Current Game Structure

**Status:** Consolidated pre-production blueprint  
**Updated:** 2026-09-15  
**Scope:** What the game currently is, what content belongs to it, and what still needs design work.

This is the fastest document to read for the complete current plan. The master design and specialist documents contain the reasoning and deeper notes. Items marked **Confirmed** came directly from the project direction. Items marked **Proposed** are the strongest current recommendation and can still change.

## 1. Game identity

**Confirmed:** A funny, three-dimensional Roblox survivor roguelite played as the player's normal Roblox avatar. There is no roster of replacement heroes. A player chooses a mechanical class, enters a short chapter, automatically attacks crowds, creates a build through weapons and stats, defeats a boss, and returns to the lobby with permanent rewards.

The comedy comes from using serious and ridiculous equipment together: a Katana beside a Frying Pan, a Glock beside a Fart Gun, or Mjolnir beside a Spatula. Maps can have separate themes and enemy rosters; the whole game does not need one creature or museum gimmick.

**Session target:** Eight waves, approximately 6.5–7 minutes of combat and 8–10 minutes including choices and shops. It should be comfortable to play while listening to music or an audiobook. Ordinary enemies should not require constant precision aiming.

## 2. Complete player journey

```text
Join as Roblox avatar
  -> short guided lobby introduction
  -> choose a starter class and its signature weapon
  -> play a three-wave tutorial
  -> collect XP and drops through satisfying magnetic pickups
  -> choose banked stat upgrades between waves
  -> buy and combine weapons in the between-wave shop
  -> defeat the tutorial boss
  -> receive Coins, account XP, a starter case, and Weapon Parts
  -> return to lobby, open rewards, and upgrade a weapon
  -> select a chapter, class, and owned class starter weapon
  -> play an eight-wave chapter and defeat its boss
  -> return with persistent progression; the temporary run build resets
```

### First session

- The player initially owns **Brawler, Gunner, and Mage**.
- Their initial weapon blueprints are **Frying Pan, Glock, and Magic Staff**.
- The tutorial takes place in **Pine Valley** and teaches movement, automatic attacks, XP pickup, one stat choice, a scripted shop purchase, and combining two matching weapons.
- The first results screen grants enough Parts to demonstrate one Permanent Weapon Level.
- The remaining classes and weapons are earnable through account progression, chapter clears, quests, mastery, cases, or direct early-unlock purchases.

## 3. Run structure

### Before entering

The player selects:

1. A chapter.
2. A class.
3. One owned starter weapon from that class. A newly unlocked class includes its signature weapon.

### During a chapter

- The avatar moves freely in an open arena while weapons attack automatically.
- Enemies drop XP, run currency, and occasional temporary loot.
- Level-ups are recorded during combat but do not interrupt the action.
- At the end of each wave, all remaining drops vacuum to the player.
- Banked level-ups are resolved as quick stat-card choices.
- A four-card shop then offers weapons and passive items; the player may buy, reroll, lock, recycle, and combine.
- Horde and elite waves create variation. Wave 8 ends with the chapter boss.
- Death ends the chapter with partial persistent rewards. Victory awards full rewards and unlocks the next chapter where applicable.

### What resets after a run

- Run level and XP
- Temporary stat choices
- Extra weapons acquired in the run
- Weapon run tiers
- Passive items
- Run shop currency
- Temporary drops and boosts

### What saves permanently

- Classes and class mastery
- Weapon blueprints
- Permanent Weapon Levels
- Weapon Parts and persistent Coins
- Account level and XP
- Weapon mastery
- Chapter clears and difficulty progress
- Cases and case progress
- Quests, achievements, cosmetics, and settings

## 4. Classes and complete weapon roster

There are **six classes with six home weapons each**, for **36 launch weapons**. A class determines the first-weapon pool and affinity bonuses, but it does not lock the player out of other weapons.

### Starting access

Every new player immediately owns **three classes**:

- **Brawler** with Frying Pan
- **Gunner** with Glock
- **Mage** with Magic Staff

The tutorial asks the player to try one, but all three remain unlocked afterward. **Thrower, Juggler, and Handyman** begin locked and are earned through early account/chapter goals or purchased for immediate access. The intended free unlock pace is one new class within the first few successful runs, not a long grind.

| Class | Play style | Signature starter | Other home weapons |
| --- | --- | --- | --- |
| **Brawler** | Close-range arcs, orbiting protection, durability | **Frying Pan** | Nunchucks, Katana, Kusarigama, Spatula, Baseball Bat |
| **Gunner** | Fast projectiles, magazines, piercing and spread | **Glock** | Draco, Fart Gun, Shotgun, T-Shirt Cannon, Rocket Launcher |
| **Thrower** | Returning projectiles, volleys, area denial | **Boomerang** | Kunais, Molotovs, Eggs, Steak, Deck of Cards |
| **Juggler** | Orbitals, rebounds, repeated contact and knockback | **Boxing Gloves** | Rubber Ducks, Cinder Blocks, Yo-Yo, Bowling Ball, Bowling Pins |
| **Handyman** | Construction tools, deployables, lanes and utility | **Nail Gun** | Wrecking Ball, Shovel, Paint Roller, Vacuum Cleaner, Power Washer |
| **Mage** | Elemental zones, chain effects, mythic late unlocks | **Magic Staff** | Mjolnir, Excalibur, Pandora's Box, Medusa's Head, Crystal Ball |

### Class and off-class rules

- A class supplies one always-active specialization, even when using off-class weapons.
- Every weapon has one **home class** and two or more **combat tags**.
- Any class may buy any unlocked weapon unless a future balance exception explicitly says otherwise.
- Off-class weapons retain their full base behavior and can receive bonuses through shared tags.
- Equipping **two** home-class weapons activates the class's first affinity bonus.
- Equipping **four** activates its stronger affinity bonus.
- The fifth slot remains flexible for a wildcard weapon.
- Example: Nail Gun belongs to Handyman but also has Gun, Rapid, and Projectile tags, so a Gunner can roll it and benefit from applicable Gunner/tag effects.

### Proposed class benefits

Exact percentages require playtesting, but each class has a defined mechanical lane:

| Class | Always-active specialization | Two home weapons | Four home weapons |
| --- | --- | --- | --- |
| **Brawler** | Better close-range knockback and reduced contact damage | More close-range damage and Armor | Close-range hits occasionally echo with a second smaller impact |
| **Gunner** | Faster projectiles and slightly faster ranged attacks | Gun/Rapid attacks gain improved piercing or magazine uptime | Every set number of projectiles produces a free bonus shot |
| **Thrower** | Returning and thrown projectiles travel farther and return faster | More thrown-projectile damage and bounce strength | Every few volleys throws one additional projectile at reduced damage |
| **Juggler** | Orbiting attacks rotate faster | Orbitals gain radius and knockback | Adds one reduced-damage copy to applicable orbital attacks |
| **Handyman** | Construction/Utility attacks gain area and knockback | Reduced cooldown for Construction/Utility weapons | Every set number of attacks repeats the attack at reduced power |
| **Mage** | Longer burn, poison, slow, and lightning-related effects | More Elemental damage | Enemies defeated while affected can spread that effect to one nearby enemy |

Classes do not need mandatory drawbacks. Their opportunity cost is that off-class-heavy builds do not activate the two- and four-weapon affinity bonuses.

Example: a Gunner using Glock, Draco, Shotgun, Fart Gun, and Kunais receives both Gunner affinities while keeping Kunais as a wildcard. A Gunner using five Thrower weapons can still use all of them normally, but receives only the Gunner's always-active specialization and would have been better served choosing Thrower for that run.

**Still to design:** Exact percentages, proc intervals, class unlock objectives/prices, and whether there is a universal dash or class active.

## 5. Weapon presentation, acquisition, and upgrades

### Presentation rule

Equipped weapons are build icons, not objects the avatar continuously holds. The world shows only the attack representation:

- Katana creates a clean slash effect near enemies.
- Boomerang/Kunai/Egg-style attacks show their actual projectile.
- Magic Staff calls lightning or another spell effect without placing a staff in the avatar's hand.
- Glock creates visible bullets, muzzle-like feedback, and impact effects without requiring a held gun model.

This matches the supplied reference screenshot and keeps the Roblox avatar readable. Because most weapon models are never visible, **weapon skins are removed from the core cosmetic and monetization plan**. A few future attack-effect variants could exist only if they preserve identical silhouettes, timing, color warnings, and readability, but they are not a launch priority.

### Temporary run progression

- Maximum **five active weapons**.
- Weapons have **four temporary run tiers**.
- Two copies of the same weapon and tier combine into the next tier.
- Combining improves numbers and visibly changes behavior, silhouette, projectile pattern, or utility.
- Run tiers disappear when the chapter ends.

The Glock is the approved model for upgrade quality:

| Tier | Form | Behavioral upgrade |
| --- | --- | --- |
| I | Glock | Basic semiautomatic fire |
| II | Glock + Extended Clip | Larger magazine and less reload downtime |
| III | Glock with Switch | Automatic bursts and a denser firing stream |
| IV | Akimbo Switches | Two firing streams with improved crowd coverage |

All other weapons need similarly recognizable Tier I–IV chains. A tier cannot be only “+20% damage.”

### Permanent weapon progression

Permanent weapon progression is intentionally reduced to three understandable records:

- **Blueprint:** a one-time unlock. Owning it adds the weapon to shops and allows it to be selected as a starter for its home class. A blueprint does not increase damage.
- **Permanent Weapon Level:** approximately levels 1–10, upgraded with **Universal Parts plus persistent Coins**. It supplies a small shared cap, initially about 10–12% total effectiveness. It never carries temporary tiers between runs.
- **Mastery:** a use record earned by playing with the weapon. Milestones grant Coins, Universal Parts, profile badges, titles, and challenges. Mastery is not another endlessly stacking damage track.

Weapon-specific Parts are removed to avoid filling the inventory with 36 materials. All duplicates convert to Universal Parts. Players must also have deterministic unlock paths so bad case luck cannot permanently block a desired weapon.

## 6. Between-wave shop

The shop shows four cards and supports buy, reroll, lock, recycle, and automatic legal combinations.

- Shops 1 and 2 show exactly **two weapons and two passive items**.
- Shops after waves 3 and 4 guarantee at least one weapon.
- When a slot is a weapon, the current test weighting is:
  - 30% exact copy of an equipped weapon
  - 25% weapon sharing a combat tag
  - 20% selected class weapon
  - 25% any unlocked weapon
- A player can **Track** one equipped weapon. If it has not appeared for two completed intermissions, the next guaranteed weapon slot offers a legal copy. Rerolls do not advance this protection.
- Cards identify why they appeared: **DUPLICATE, CLASS, TAG MATCH,** or **WILDCARD**.
- Luck affects rarity and drop quality, not weapon identity weighting or tracking.

This permits creative mixed builds without making focused builds depend entirely on luck.

## 7. Stats and passive items

A **passive** is a temporary shop item that modifies the run without occupying one of the five weapon slots or performing its own repeating attack. It resets after the chapter. Passives are how the player specializes a build after choosing weapons.

Examples:

| Passive | Simple effect |
| --- | --- |
| Energy Drink | More attack speed, slightly less max health |
| Protein Shake | More damage |
| Running Shoes | More movement speed |
| Horseshoe | More luck |
| Fridge Magnet | Larger pickup radius |
| Bandage Roll | Health regeneration |
| Safety Helmet | More armor, slightly less speed |
| Hot Sauce | Larger explosions and status areas |
| Broken Glasses | More critical chance but less range |
| Coupon Book | Shop purchases cost less |
| Vampire Fang | A small percentage of damage heals the player, with a healing-per-second cap |
| Lighter | Hits can ignite enemies for short damage over time |
| Ice Cube | Hits can briefly slow enemies |
| Battery Pack | Every set number of hits releases a short lightning chain |
| Toxic Barrel | Hits can apply stacking poison damage |
| Charcoal | Increases burn damage and burn duration |
| Snow Globe | Increases slow strength and duration |
| Lightning Rod | Lightning chains can jump to one additional enemy |

Passives should mostly be readable stat changes, tradeoffs, and one-sentence triggers—not additional complicated weapons.

**Confirmed direction:** Stat choices happen between waves, not while enemies are moving. Combat remains uninterrupted and the end of each wave becomes the short decision phase.

Candidate run stats include:

- Damage
- Attack speed
- Critical chance and critical damage
- Projectile count, piercing, bounce, and area size
- Melee/close-range damage
- Ranged/projectile damage
- Elemental/status damage
- Max health, armor, dodge, regeneration, and life steal
- Movement speed
- Pickup radius
- Luck
- Knockback
- Deployable/utility power

**Armor decision:** There is no separate armor equipment, armor-set, or visible game-owned armor system. Players already bring their Roblox avatar appearance, and covering it with armor would fight that identity while duplicating Final Swarm. **Armor remains a numerical defensive stat** that classes, level-up cards, and passives such as Safety Helmet may increase.

The launch target is approximately 24–30 simple passives. The vertical slice needs about 12–15.

## 8. Maps, primary mobs, and bosses

Visual direction sheets for all six arenas are saved in [map-concepts/README.md](map-concepts/README.md).

All maps are broad outdoor arenas viewed from an elevated third-person camera. Approximately 75–85% of the playable surface remains open. Gentle slopes, sparse low props, and a scenery-heavy perimeter provide identity without creating intricate interiors, mazes, parkour, or constant collision traps.

The lists below are each map's **first-clear primary roster**, not a permanent lock. Later chapters and higher difficulties may remix mobs across maps. Strong enemies consume more of the spawn threat budget and therefore appear less often.

| Map | Shape and visual identity | Frequent mobs | Less-frequent threats | Boss |
| --- | --- | --- | --- | --- |
| **Pine Valley** | Open grassy basin, pine rim, scattered rocks and logs | Zombies, Slimes, Goblins | Garden Gnomes, Ogres | **Ogre Warlord** |
| **Beach Cove** | Open sand-and-grass coast with rock rim, tide pools and driftwood | Crabs, Slimes, Snakes | Ghosts, Trolls | **Giant Crab** |
| **Desert Basin** | Enclosed sand bowl, giant perimeter rocks, sparse cacti, bones and dead trees | Skeletons, Snakes, Mummies | Assassins, Witches | **Pharaoh** |
| **Castle Fields** | Open lawn outside distant walls and towers; broken carts and banners stay near the edges | Goblins, Skeletons, Knights | Vampires, Assassins | **Headless Knight** |
| **Frozen Pass** | Wide vertical corridor between snowy cliffs; sparse ice and ruined camp props | Werewolves, Ghosts, Knights | Trolls, Witches | **Cyclops** |
| **Volcanic Crater** | Enclosed dark-stone basin with lava scenery beyond safe edges and sparse vents | Spiders, Goblins, Slimes | Ogres, Vampires | **Dragon or Hydra** |

### Complete regular-mob pool

Zombie, Slime, Goblin, Crab, Skeleton, Snake, Spider, Ghost, Mummy, Witch, Knight, Vampire, Werewolf, Garden Gnome, Assassin, Ogre, and Troll.

Small purposeful variants are allowed when they reuse one of the basic behaviors below. Foundational families such as Zombies, Skeletons, and Slimes may have two or three recognizable forms; every creature does not need a full family.

### Basic enemy behavior kit

| Behavior | Rule | Telegraph |
| --- | --- | --- |
| **Melee chaser** | Walk toward the nearest player and perform a basic swing/contact hit | Short windup and small ground flash at close range |
| **Ranged shooter** | Stop briefly and fire one visible projectile | Thin red aim line appears before firing |
| **Dasher** | Pause, lock a direction, then dash through the lane | Wide red line/rectangle marks the entire dash path |
| **Heavy chaser** | Slower, larger, more health and damage; still uses a basic swing | Large silhouette and slower windup |
| **Splitter** | On death, produces a small fixed number of weaker enemies | Body swells/wobbles immediately before splitting |

Approved early variants:

- **Zombie:** regular chaser, fast low-health crawler, and large slow Zombie.
- **Skeleton:** melee Skeleton and Bow Skeleton with a red aim line.
- **Slime:** Small Slime and Big Slime; a Big Slime splits into two or three Small Slimes.
- Other mobs should initially use one behavior each. For example, Assassin can dash, Witch can shoot, Ogre can be a heavy chaser, and Spider can be a faster melee chaser.

The full initial assignment is intentionally plain: Goblin, Crab, Spider, Ghost, Mummy, Vampire, and Werewolf use melee-chaser variations; Witch, Garden Gnome, Bow Skeleton, and Troll use the red-line ranged shot; Snake and Assassin use the red-lane dash; Knight and Ogre are heavy melee enemies. Detailed values, not extra moves, distinguish most of them.

Their combat weight differs:

- **Weak swarmers:** threat cost 1; appear in large numbers.
- **Standard enemies:** threat cost 2; form the normal crowd.
- **Specialists:** threat cost 3–4; ranged attacks, ambushes, buffs, or area denial; appear less often.
- **Heavy enemies:** threat cost 7–9; large silhouettes and dangerous attacks; appear rarely.
- **Elites:** empowered encounters with unique telegraphs, not routine recolors of every mob.

### Complete boss pool

- Ogre Warlord
- Giant Crab
- Pharaoh
- Headless Knight
- Cyclops
- Dragon or Hydra — final selection still open

Each boss still needs a complete kit, telegraphs, phase rules, audio identity, and mobile-safe tuning.

## 9. Combat feel, drops, and readability

- Target approximately 100 active enemies during stress tests, adjusted for Roblox device performance.
- Each defeated enemy produces an immediate individual impact/death sound; there is no multikill-announcer aggregation.
- Enemies should burst, pop, crumble, or dissolve clearly according to creature type.
- XP, Coins, and loot remain visible briefly, then arc toward the player through a strong magnetic pickup effect.
- Pickup audio rises or varies subtly during a stream without becoming a spoken combo system.
- Attacks must have crisp anticipation, hit confirmation, and distinct silhouettes.
- Effects should remain close to the ground or weapon path and must not cover large portions of the screen.
- Enemy hazards always win the readability hierarchy over friendly spectacle.

## 10. Lobby structure

The lobby is a compact, readable home base rather than a giant social maze. Core stations can also be opened from a single menu on mobile.

### Required spaces

- **Play / chapter portal:** map, chapter, difficulty, class, and starter-weapon selection.
- **Class station:** view unlocked classes, bonuses, mastery, and unlock requirements.
- **Armory:** weapon blueprints, Permanent Weapon Levels, Universal Parts, mastery, and tier/attack previews.
- **Case station:** earned cases, transparent contents, duplicate conversion, and case progress.
- **Quest board:** daily, weekly, achievement, and progression objectives.
- **Customization:** pickup effects, enemy defeat effects, emotes, titles, nameplates, lobby poses, and UI themes. No weapon-skin or armor-set dependency.
- **Shop:** clearly separated Robux purchases and persistent-Coin purchases.
- **Practice area:** damage dummies and weapon previews with no persistent rewards.
- **Party area:** invite friends and queue together if co-op is included.
- **Results board:** last run, personal bests, mastery progress, and next unlock.

The player should be able to return from a run, understand every reward, make one meaningful upgrade, and launch the next chapter in roughly 30–60 seconds.

## 11. Progression outside runs

- **Account level:** unlocks systems, classes, chapters, and broader reward tracks.
- **Chapter progress:** first clears open later stages and difficulties.
- **Class mastery:** rewards using a class without changing the avatar.
- **Weapon ownership and levels:** expands possible starts and provides bounded permanent growth.
- **Weapon mastery:** rewards actual play with each weapon.
- **Cases and case meter:** provide earnable blueprints, Universal Parts, Coins, and customization rewards.
- **Quests and achievements:** give deterministic progress and reasons to try varied builds.
- **Customization collection:** emotes, titles, nameplates, lobby poses, pickup effects, defeat effects, and UI themes.

A defeat still grants reduced account XP, Coins, mastery, and case-meter progress, preventing an unsuccessful eight-minute session from feeling wasted.

## 12. Monetization and purchases

The commercial rule is **pay for meaningful acceleration, convenience, early access to earnable options, and expression—not exclusive or uncapped combat dominance**. Add one premium currency, **Gems**, so purchases lead into a clear rotating catalog rather than dozens of separate developer products.

### Recommended launch products

| Product | What it provides | Guardrail |
| --- | --- | --- |
| **Gem packs** | Premium currency for guaranteed catalog purchases | Never used for undisclosed random rolls |
| **VIP game pass/subscription** | Proposed +20% account XP, +20% persistent Coins, one extra daily quest, daily Gems, VIP nameplate | Multipliers do not stack with separate economy passes |
| **Starter Pack** | Class-choice token, blueprint-choice token, fixed Universal Parts, fixed Coins, Gems, exclusive nameplate | One-time, contents stated exactly, no random paid outcome |
| **Early Class Unlock** | Immediate access to an otherwise earnable class | Class remains a sidegrade and is earnable normally |
| **Early Weapon Blueprint** | Immediate access to a selected otherwise earnable weapon | Weapon is not paid-exclusive and still follows normal balance |
| **Class Arsenal Bundle** | One class plus its six weapon blueprints and upgrade materials | Everything remains separately earnable; bundle saves time rather than raising the cap |
| **Universal Weapon Parts** | Speeds Permanent Weapon Levels | Same low level cap and stats as earned Parts |
| **Persistent Coin Packs** | Speeds account/weapon progression | Cannot purchase run shop currency |
| **Premium Progression Track** | Extra Gems, Coins, Universal Parts, choice tokens, effects, emotes and titles | Gameplay resources accelerate the same capped systems |
| **Daily Deals** | Rotating guaranteed blueprints, class tokens, Parts and bundles | Exact contents shown; no paid rerolling for better odds |
| **Buyable Revive** | Direct death-screen Developer Product that immediately continues the current chapter | One paid revive per player per chapter at launch; recommended first price test around 65 Robux |
| **Customization** | Defeat effects, magnet/pickup styles, emotes, titles, nameplates, lobby poses and UI themes | No weapon skins or armor sets required |

### Never sell

- Mid-run purchases other than the explicitly approved revive
- Run XP, run shop currency, rerolls, weapon slots, or stronger shop odds
- Unlimited or repeatedly escalating revive chains
- Raw permanent damage/health entitlements beyond the normal earnable capped systems
- Paid-exclusive classes or combat weapons
- Loot boxes with hidden odds

If paid random items are ever added, Roblox requires disclosure of actual numerical odds and policy checks for each player. The launch recommendation remains guaranteed paid contents and earnable random cases.

### Buyable revive flow

When a solo player dies, the run pauses and the death screen shows **REVIVE** and **GIVE UP**. Selecting REVIVE opens the Roblox purchase prompt. The server grants the revive only after a validated developer-product receipt.

- One paid revive per player per chapter at launch.
- Restore 50% max health.
- Grant three seconds of invulnerability.
- Push nearby enemies outward so the player does not instantly die again.
- Resume the same wave, timer, boss health, build, currency, and drops.
- A cancelled or failed purchase returns to the death choice without granting anything.
- Revived victories still clear the chapter and earn normal rewards, but the result records the revive count for challenge and leaderboard filtering.
- Co-op behavior remains to be decided; the clean proposal is to show the purchase only when that player cannot be rescued normally or the entire team is down.

## 13. Launch-scope recommendation

The **prototype** should contain one map, three classes, six signature/demo weapons, six regular mobs, one boss, the eight-wave loop, banked level-ups, and the shop/combine flow.

The **vertical slice** should contain two maps, all six classes, 12 weapons (two per class), approximately 15 passive items, 8–10 mobs, two bosses, the complete lobby loop, saving, one earned case, and bounded weapon leveling.

The **content launch target** is six maps, six classes, 36 weapons, 30–40 passives, all 17 core mobs, six bosses, chapter progression, quests, cases, mastery, cosmetics, and the approved monetization catalog. This is a target to produce toward, not a promise that everything must ship before the first public test.

## 14. What is still missing

### Must be decided before the prototype

1. Exact Brawler, Gunner, and Mage class rules.
2. The six prototype weapons and their complete four-tier chains.
3. Assign the basic behavior kit, threat costs, health, speed, damage, and drop values to the six prototype mobs.
4. Pine Valley wave-by-wave spawn script and tutorial boss choice.
5. Base stat formulas, damage calculation, attack targeting, and defensive rules.
6. Shop prices, starting currency, reroll escalation, recycle value, and wave income.
7. The first 10–15 passive items.
8. Exact keyboard, controller, and mobile controls, including whether there is a dash or class active.
9. Final revive price, purchase timeout, co-op behavior, and whether a second revive is ever permitted.
10. Performance budgets for enemies, projectiles, drops, VFX, and audio voices.

### Must be decided before the vertical slice

1. Exact rules for all six classes and their 2-/4-weapon affinities.
2. Tier chains for all 12 slice weapons.
3. Permanent Weapon Level cost curve and reward pacing.
4. Account, class, and weapon mastery unlock pacing.
5. Enemy behaviors, elites, boss kits, and difficulty scaling.
6. Solo-only launch versus 1–4 player co-op, plus scaling, revives, loot ownership, and drop-in rules.
7. Case tables, duplicate conversion, pity/deterministic unlock paths, and quest rewards.
8. Lobby layout and full UI wireframes.
9. Product prices, Gem pricing, regional/platform policy handling, analytics, and purchase receipt validation.

### Important but not blocking the first build

- Final game title
- Optional odd-jobs-agency story wrapper
- Dragon versus Hydra selection
- Endless mode
- Seasonal events and progression track cadence
- Advanced difficulty modifiers and later cross-map enemy remixes

## 15. Immediate next design order

1. Lock class kits.
2. Lock the six prototype weapons and design all 24 tier forms.
3. Design the first 15 passive items.
4. Specify Pine Valley's six mobs, Ogre Warlord kit, and eight-wave script.
5. Build the economy sheet and run simulator.
6. Wireframe the run HUD, stat choice, shop, results, and lobby armory.
7. Create the Roblox technical architecture and prototype milestone plan.
