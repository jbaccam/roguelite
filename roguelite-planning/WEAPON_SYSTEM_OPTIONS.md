# Weapon Acquisition and Upgrade System

**Status:** Reference comparison; continuous-draft recommendation superseded by the current eight-wave shop proposal  
**Question:** How does a player enter a chapter, acquire weapons, improve them, and evolve a build during an eight-minute run?

The current recommended direction is documented in `PROGRESSION_AND_SESSION_FLOW.md`: timed combat waves, end-of-wave level choices, a temporary-material shop, and same-tier weapon combining. The continuous system below is retained only so the tradeoff remains visible.

## Reference comparison

### Survivor.io pattern

- Persistent equipment includes a main weapon selected before the chapter.
- The equipped main weapon begins as an active skill during the run.
- Collecting XP triggers choices between new skills, upgrades to owned skills, and passive supplies.
- Active weapons and passive supplies use separate slot limits.
- Weapons gain multiple levels during the run.
- A maximum-level weapon can evolve when the player also owns its required passive and meets the evolution-award condition.
- The full combat build is temporary and resets after the chapter, while account equipment/progression persists.

### Brotato pattern

- The player selects a starting weapon before the run.
- Combat is divided into waves.
- Materials collected during a wave are spent in a four-slot shop between waves.
- The shop can be rerolled, and offers can be locked for later.
- Most characters can hold six weapons.
- Two identical weapons of the same tier combine into one weapon of the next tier, up to Tier 4.
- Items provide the remainder of the build while level-ups primarily provide stat choices.
- Weapons and items acquired during the run are temporary.

## Three possible directions

| Model | Strengths | Weaknesses |
| --- | --- | --- |
| Survivor-style level draft | Continuous, simple, mobile-friendly, and produces a build quickly | Familiar and potentially too close if copied without changes |
| Brotato-style wave shop | Strong economy decisions, reroll tension, and duplicate merging | Interrupts the eight-minute flow and requires discrete waves |
| Hybrid | Continuous XP choices with a starting weapon, compact slot limits, evolutions, and occasional elite loot | Needs disciplined rules so it does not feel like two systems stacked together |

## Earlier alternative: continuous hybrid

This was the initial recommendation before the user expressed a preference for Brotato-style intermissions. It is not the current direction.

### Before the chapter

1. The player chooses **one unlocked starting weapon**.
2. The weapon begins at Level 1 and occupies one active slot.
3. Selecting a weapon determines the first attack, not a permanent class or character identity.
4. Weapon unlocks grant access and variety. They should not create permanently stronger paid copies.

### During the chapter

Enemies drop XP. Filling the XP bar pauses or safely slows the action and presents three choices:

- acquire a new weapon if an active slot is open;
- raise the level of an owned weapon;
- acquire or improve a passive item/stat;
- rarely, take a run-changing special item.

The starting weapon follows the same upgrade rules as every weapon found during the run. It is guaranteed, not secretly stronger.

### Recommended slot limits

- **Five active weapon slots**, including the starting weapon.
- **Five passive/build-item slots.**
- Armor treatment remains a separate decision.

Five active slots should create the layered survivor-game spectacle while remaining more readable than six or more attack systems on a small phone screen. This number must be tested rather than treated as final.

### Weapon leveling

When an owned weapon appears again, choosing it upgrades that weapon directly. It does not create a second physical copy or require the player to combine two inventory icons.

Proposed five-level structure:

| Level | Typical improvement |
| --- | --- |
| 1 | Base weapon behavior |
| 2 | Damage, cooldown, or projectile improvement |
| 3 | First visible behavior change |
| 4 | Strong numerical improvement |
| 5 | Second behavior change and evolution readiness |

Examples:

- Bowling Ball gains another rebound or wider impact.
- Rubber Ducks gain another duck and a wider orbit.
- Katana stores more delayed slashes.
- Fart Gun clouds persist longer or spread once.
- Nail Gun requires fewer repeated hits to pin a target.

### Evolution

A Level 5 weapon plus a compatible passive makes an evolution **eligible**. The next appropriate elite or boss reward can evolve it.

| Weapon | Example required passive | Evolution concept |
| --- | --- | --- |
| Bowling Ball | Knockback or movement passive | Perfect Game |
| Rubber Ducks | Luck passive | Quack Attack |
| Cinder Blocks | Armor/heavy passive | Concrete Evidence |
| Fart Gun | Area-size passive | Industrial Windbreaker |
| Katana | Critical-chance passive | Stored slashes release in crossing patterns |
| Nail Gun | Attack-speed passive | Automatic construction-grade burst system |

The final pairing list should be small and intentional. Not every passive needs to evolve every weapon.

### Elite and boss rewards

Elite/boss drops should not be ordinary random XP choices. A reward chest can prioritize:

1. an eligible weapon evolution;
2. a high-rarity upgrade to the current build;
3. a new run-changing item when no evolution is eligible.

Exact elite timing remains part of encounter pacing.

### Coins and loot

Recommended initial separation:

- **XP:** Temporary, collected magnetically, drives in-run level choices.
- **Coins:** Persistent earned currency, collected magnetically, spent outside the chapter on unlock breadth or cosmetics.
- **Elite/boss loot:** Immediate in-run upgrade/evolution reward.
- **Rare persistent drop:** Optional later system; should unlock content or cosmetics rather than create an uncapped power grind.

Do not add an in-run material shop to the first prototype. XP drafts already interrupt the action enough, and the game is intended to remain relaxed and continuous.

## Why not copy Brotato's duplicate combining directly?

Pairwise combining works naturally in Brotato because the player visits a shop after every wave and manages six visible weapon slots. In a continuous eight-minute Roblox chapter, forcing players to collect two Level 1 copies, manually combine inventory icons, and manage empty slots adds menu work without necessarily adding a better decision.

Direct weapon leveling preserves the satisfying “I found my weapon again” moment while remaining faster on touch devices.

We can still borrow the useful part of Brotato's system: once the player owns a blueprint, that weapon enters the normal shop pool, and weapons already used in the current build receive increased offer weight so duplicate combining remains practical.

## Persistent blueprint and Weapon Level layer

- Cases, deterministic coin unlocks, mastery objectives, or direct purchases can permanently unlock a weapon blueprint.
- An owned blueprint can be selected as the one guaranteed starter and can appear in normal run shops.
- Weapon Parts plus persistent Coins raise that weapon through a capped Permanent Weapon Level 1–10 track.
- Permanent Weapon Level adds only a modest effectiveness bonus, initially targeted around 10–12% total at the cap.
- The run's Tier 1–4 combining system remains temporary and resets after the chapter.
- The player never carries the previous run's five-weapon inventory into a new chapter.

## Avoiding a forced build

- The first few levels should offer enough weapons to establish a direction.
- Owned weapon tags slightly influence later offers.
- The system should never guarantee the exact same build every run.
- Full weapon slots remove unrelated new-weapon offers unless a clear swap feature exists.
- Max-level weapons stop appearing except when an evolution is available.
- Offer generation prevents three choices that are capped or unusable.
- Limited rerolls may exist, but Robux purchases cannot add rerolls or alter a run's shop RNG.

## Armor decision

**Chosen:** There is no separate armor equipment, armor-set, or game-owned visible armor system. The player's Roblox avatar remains their appearance. Armor continues only as a defensive number modified by classes, level-up cards, and temporary passive items such as Safety Helmet.

## Decisions to confirm

1. **Chosen:** Discrete combat waves with banked end-of-wave stat choices and a shop.
2. **Chosen:** Bring one owned starting weapon.
3. **Chosen for prototype:** Five active weapon slots; passive copy limits still need testing.
4. **Chosen:** Capped Permanent Weapon Level plus temporary same-tier duplicate combining during the run.
5. Decide whether maximum-tier weapons require a paired passive for a final evolution.
6. **Chosen:** No armor equipment system; Armor remains a stat.

## Sources reviewed

- Survivor.io Wiki, Weapon Skill Evolution Guide: https://survivorio.fandom.com/wiki/Weapon_Skill_Evolution_Guide
- Brotato Wiki, Shop: https://brotato.wiki.spellsandguns.com/Shop
- Brotato Wiki, Weapons: https://brotato.wiki.spellsandguns.com/Weapons
