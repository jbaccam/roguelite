# Astra Execution Plan — Roblox Survivor Roguelite

**Status:** Approved implementation order  
**Updated:** 2026-09-15  
**Purpose:** Build the smallest complete version of the game in the correct dependency order. Do not begin by producing the full 36-weapon catalog or finished environment art.

## Core rule

Build and validate the combat loop in a graybox before investing in polished maps, models, icons, or lobby presentation.

The first useful playable is:

> A Roblox avatar with a Glock automatically shooting block Zombies in an empty circular arena while XP drops magnetically collect.

## Prototype content target

- One circular graybox arena that later becomes Pine Valley
- Regular Roblox camera with player-controlled zoom and rotation
- All six classes available for internal testing
- One signature weapon per class: Frying Pan, Glock, Boomerang, Boxing Gloves, Nail Gun, Magic Staff
- Four temporary combination tiers per prototype weapon
- Twelve prototype passives
- Eight combat waves
- Six basic enemy types using reusable behavior modules
- One elite configuration
- Ogre Warlord final boss
- Banked end-of-wave stat choices
- Four-card shop, reroll, lock, recycle, tracking, and duplicate combining
- Death, paid revive test, victory, defeat, and results
- Keyboard, controller, and mobile support
- Basic permanent save data only after the run loop works

## Phase 0 — Data and authority skeleton

**Required architecture (2026-09-17):** Follow [Enemy simulation and combat architecture](ENEMY_SIMULATION_ARCHITECTURE.md). Enemies are authoritative server records with client-rendered models, batched snapshots, smooth visual reconciliation, spatial queries, and budgeted shared navigation. Migrate the five-chaser prototype before building combat against it; replicated Humanoid NPCs are not the horde foundation.

Create server-owned definitions and services before content multiplication:

- Weapon definitions
- Class definitions
- Passive definitions
- Enemy definitions
- Wave definitions
- Stat/modifier pipeline
- Damage service
- Reward service
- Run state machine
- Validated remotes
- Object pools for enemies, projectiles, drops, and effects

The client owns presentation and input intent. The server owns damage, health, enemy state, shop results, inventory, combinations, drops, rewards, revive state, and victory.

### Exit check

Definitions load without circular dependencies, invalid IDs are rejected, and the server can start and terminate a test run deterministically.

## Phase 1 — Graybox movement and camera

1. Create a flat circular arena with a visible boundary.
2. Spawn the Roblox avatar near the center.
3. Keep the regular Roblox camera. Start base WalkSpeed testing at 18 studs/second; further speed modifiers come from classes and run builds.
4. Support keyboard, controller, and touch movement.
5. Prevent avatar scale/accessories from changing combat collision.
6. Add a temporary debug HUD for health, run time, enemy count, and FPS.

Use primitives and default materials. Do not build Pine Valley art yet.

### Exit check

Movement and camera feel comfortable on PC and touch across the entire arena, including near the perimeter.

## Phase 2 — Smallest combat toy

**2026-09-17 implementation checkpoint:** Approved native R15 zombie now replaces the imported prototype. Studio Play spawns five server-owned chasers at 15.2 studs/second with forward-arm running animation; one static display remains. Single-client movement, animation, head replication/orientation, and spawn count verified. Health/damage and automatic Glock combat are next; Phase 2 is not yet complete. See `studio-prototype/README.md` for sources and test limits.

Before step 1, complete the five-enemy simulation/presentation migration and validation in ENEMY_SIMULATION_ARCHITECTURE.md. The existing movement checkpoint does not satisfy this requirement.

1. Add server-owned player health and damage handling.
2. Add one block Zombie using the melee-chaser behavior.
3. Add Glock automatic target selection.
4. Add visible pooled bullets and impact feedback.
5. Add enemy death.
6. Add XP drops and magnetic collection.
7. Add one temporary level-up stat choice.

### Exit check

Moving through a crowd while automatically firing is readable and satisfying for five uninterrupted minutes.

## Phase 3 — Performance proof

Test successively with 25, 50, 75, and approximately 100 active enemies, plus projectiles and drops.

After those pass measured device and network budgets, attempt 250 and 500 as stress targets under ENEMY_SIMULATION_ARCHITECTURE.md. Do not claim those counts are supported until profiled with combat, multiple clients, and representative mobile hardware.

Record:

- Server frame time
- Client FPS on representative low, medium, and high devices
- Active enemy/projectile/drop counts
- Network traffic
- Pool reuse and memory growth
- Time spent in targeting, movement, hit detection, and effects

Create scalable quality settings before art multiplication. Lower-end modes may reduce cosmetic particles and dropped-object persistence, but cannot remove attack or danger telegraphs.

### Exit check

The target density is stable enough to justify producing enemy and weapon content.

## Phase 4 — Reusable enemy behaviors

Implement five modules:

1. Melee chaser with a basic swing/contact hit
2. Ranged shooter with a thin red aim line and visible projectile
3. Dasher with a red lane that locks before movement
4. Heavy chaser using the melee module with slower movement and attacks
5. Splitter that produces a fixed number of weaker enemies on death

Use these to create the first six test enemies. Keep animations to walk, short windup, attack, hit reaction, and death.

### Exit check

Every attack can be identified and dodged without reading enemy names or relying on sound alone.

## Phase 5 — Six signature weapons

Implement, in order:

1. Glock — targeted projectile
2. Frying Pan — close impact/slash
3. Boomerang — returning projectile
4. Boxing Gloves — orbital that punches outward
5. Nail Gun — rapid projectile/utility
6. Magic Staff — spell targeting and elemental hook

Each weapon needs four temporary tiers. A tier must change coverage, cadence, projectile pattern, orbit count, magazine behavior, or utility—not only increase damage.

### Exit check

Each signature weapon has a recognizable silhouette and produces a meaningfully different movement/build preference.

## Phase 6 — Complete eight-wave run

Build the state sequence:

```text
Wave combat
→ vacuum remaining drops
→ resolve banked stat choices
→ intermission shop
→ next wave
→ boss
→ victory or defeat
→ results
```

Implement:

- Wave director and threat budget
- Run XP and levels
- Run materials
- Five active weapon slots
- Passive inventory
- Four-card shop
- Buy, reroll, lock, recycle, and Track
- Same-weapon/same-tier combining
- Horde and elite flags
- Pause/state protections during intermission
- Clean run teardown

### Exit check

A player can complete, lose, retry, and complete another run without server reset or corrupted state.

## Phase 7 — Prototype passives and class rules

Add the first twelve passives:

- Protein Shake
- Energy Drink
- Running Shoes
- Horseshoe
- Fridge Magnet
- Bandage Roll
- Safety Helmet
- Vampire Fang
- Lighter
- Ice Cube
- Battery Pack
- Toxic Barrel

Implement each class's always-active specialization plus two- and four-home-weapon affinity checks. Use test values in data rather than hardcoding them.

### Exit check

At least four visibly different effective builds can emerge from the six signature weapons and passive pool.

## Phase 8 — Pine Valley encounter design

After movement speed, attack range, and camera height are stable:

- Lock arena diameter
- Lock spawn regions and minimum off-camera spawn distance
- Author the eight-wave Pine Valley schedule
- Add its first-clear roster
- Add the elite encounter
- Add Ogre Warlord with basic swing, red-line charge, telegraphed ground slam, and limited add summon
- Tune XP, materials, prices, and spawn budgets together

### Exit check

The chapter lasts approximately 8–10 real minutes including intermissions and has a readable escalation curve.

## Phase 9 — Functional UI

Build practical UI before decorative styling:

- Run HUD
- Health, XP, wave, timer, currency, and inventory
- Stat-choice cards
- Shop cards and offer-source labels
- Weapon combination feedback
- Pause/settings
- Death screen with REVIVE and GIVE UP
- Results screen
- Touch controls

UI must scale across desktop, tablet, and phone. Do not create final icons until content identity is stable.

### Exit check

A new tester can finish a run without developer explanation.

## Phase 10 — Models, VFX, SFX, and Pine Valley art

Replace placeholders only after gameplay dimensions are stable:

1. Enemy models and basic animations
2. Weapon attack representations and projectiles
3. XP, Coin, and loot models
4. Death bursts and magnetic pickup effects
5. Attack, hit, death, and pickup audio
6. Red attack telegraphs
7. Pine Valley terrain and perimeter dressing
8. Final lighting and performance variants

The arena remains 75–85% open. Trees, rocks, logs, and cliffs should concentrate around the outer rim, with only sparse low obstacles inside the playable area.

### Exit check

Art improves identity without hiding enemies, drops, projectiles, or red warning shapes.

## Phase 11 — Icons and content images

Create final icons only after models/effects and names are stable:

- Classes
- Weapons and tiers
- Passives
- Stats
- Currencies and cases
- Revive
- Shop categories

Icons need strong silhouettes at mobile size and should be derived from the actual in-game attack/object identity.

## Phase 12 — Lobby and permanent progression

Add:

- Chapter/class/starter selection
- Armory
- Blueprints
- Universal Parts
- Permanent Weapon Levels
- Mastery
- Earned cases
- Quests
- Account progression
- Tutorial
- DataStore schema, versioning, retries, and failure handling

The player must be able to return from results, understand rewards, perform one upgrade, and launch the next run within 30–60 seconds.

## Phase 13 — Monetization

Implement only after run state, saving, and receipts are reliable:

- Death-screen paid revive
- Gem products
- VIP
- Starter Pack
- Class and weapon early unlocks
- Universal Parts and Coin packs
- Class Arsenal bundles
- Premium progression track when content exists

For the revive, test with a Studio-only fake grant first. Production grant logic must use idempotent server-side `MarketplaceService.ProcessReceipt`. Never grant production rewards from a client claim.

## Phase 14 — Expansion

Only after the Pine Valley vertical slice tests well:

- Complete the 36-weapon roster
- Add remaining passives
- Beach Cove
- Desert Basin
- Castle Fields
- Frozen Pass
- Volcanic Crater
- Remaining mobs and bosses
- Co-op, if approved
- Endless mode, if approved

## Do not front-load

- All 36 weapons
- Finished map art
- Final item icons
- Full lobby architecture
- Battle pass content
- All six bosses
- Co-op
- Seasonal content
- Final monetization prices

## Prototype analytics

Track from the first external test:

- Tutorial and first-run completion
- Wave reached and death cause
- Class and starter choice
- Damage contribution by weapon
- Passive selection
- Shop rerolls and purchases
- Enemy count and performance
- Revive prompt, purchase initiation, and validated completion
- Chapter duration
- Immediate retry and next-run rate

## Definition of prototype success

The prototype is successful when testers can understand it without explanation, performance remains stable at intended crowd density, every signature weapon feels distinct, red telegraphs remain readable, the shop produces recognizable builds, and players voluntarily start another run.
