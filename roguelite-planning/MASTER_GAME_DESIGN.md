# Roblox Roguelite — Master Game Design

**Status:** Discovery / pre-production  
**Version:** 0.30 — six weapons per class  
**Updated:** 2026-09-15  
**Project name:** TBD

This is the living source of truth for the proposed Roblox roguelite inspired by the broad genre space occupied by *Survivor.io*, *Megabonk*, and *Brotato*. Inspiration describes useful patterns, not content to copy. Names, art, characters, maps, enemies, weapons, balance values, and progression will be original.

For a concise complete snapshot of the current game, see [CURRENT_GAME_STRUCTURE.md](CURRENT_GAME_STRUCTURE.md).

## How to read this document

| Label | Meaning |
| --- | --- |
| **Confirmed** | Explicit project direction or repository constraint |
| **Proposal** | Recommended starting point, awaiting approval or playtesting |
| **Open** | A meaningful decision still to make |
| **Later** | Intentionally outside the first playable scope |

When new reference material arrives, record what it teaches us in the reference ledger, then update only the affected proposals. Do not silently turn an inspiration-game behavior into a project requirement.

## 1. Product vision

### One-sentence pitch

**Open:** A concise original fantasy, theme, and player promise have not been chosen yet.

### Working experience

**Proposal:** A highly replayable Roblox action roguelite where players move freely through compact arenas, survive escalating enemy pressure, assemble a distinct build from weapons and modifiers, defeat a run-ending boss, and unlock more ways to play without purchasing power.

### Target experience

- **Confirmed:** Roblox; roguelite/roguelike survivor-style combat.
- **Proposal:** Ages 9+, readable on phone, controller, and keyboard/mouse.
- **Proposal:** Solo-first combat rules with co-op designed early enough that it is not bolted on later.
- **Confirmed:** Standard chapters target approximately eight minutes, not 15-minute sessions.
- **Confirmed:** Chapters have no mid-level checkpoints; an unsuccessful run restarts the chapter.
- **Confirmed:** The desired attention level supports listening to music or an audiobook. Movement and choices matter, but ordinary play should not demand constant laser focus.
- **Proposal:** Easy controls, meaningful build decisions, high spectacle, and strong replayability.
- **Confirmed:** Purchases may provide bounded progression acceleration, early access to earnable sidegrades, and a limited death-screen revive. They cannot provide paid-exclusive combat content, uncapped power, mid-run stat purchases, altered run RNG, or power required to clear content.

### Player embodiment

**Confirmed:** Players use their Roblox avatars. Equipped weapons are represented in the HUD and by their attacks, not continuously held or displayed on the avatar.

**Confirmed:** There is no separate playable-character, hero, or armor-equipment roster. All players use the same baseline avatar rules; classes, weapons, passives, stats, and combinations create mechanical identity during a run. Armor may exist as a defensive stat, not equippable gear.

**Confirmed:** Selectable classes provide mechanical rules without replacing or visually changing the Roblox avatar. Classes are permanent unlocks selected in the lobby; the exact class roster, bonuses, tradeoffs, and unlock order remain to be designed.

### Tone and content wrapper

**Confirmed:** The game should be funny and use comedic equipment rather than a conventional medieval arsenal. Chapter environments and mobs do not need to share a literal theme.

**Confirmed:** The arsenal mixes a small number of real weapons with absurd objects. The contrast between a Katana, Nunchucks, or Glock and something like a Steak or Fart Gun is part of the comedy. Avoid filling the roster with generic swords, spears, axes, and hammers.

**Confirmed:** Construction equipment, restrained mythology, and magic may contribute weapon families. Mythological weapons should feel like notable later unlocks rather than making the base arsenal predominantly fantasy-themed.

**Candidate wrapper — not confirmed:** An impossible odd-jobs agency sends Roblox avatars into eight-minute assignments that have gone catastrophically wrong. This supplies a consistent reason to visit unrelated chapters and face changing creature rosters. The recurring visual identity comes from ridiculous attack effects, strange assignments, and the agency presentation rather than one universal enemy faction.

### Design pillars

1. **Move first, aim less.** Positioning, pathing, dodging, and pickup decisions carry the action while most attacks automate or use simple inputs.
2. **Every run becomes a build.** A player should be able to describe what their build does and why its pieces work together.
3. **Readable pressure.** Enemy silhouettes and telegraphs remain understandable even when the screen is busy.
4. **Short decisions, long consequences.** Level-up choices are fast, but synergies and tradeoffs alter the rest of the run.
5. **Fair replayability.** Knowledge and execution drive success; persistent progression expands variety more than raw strength.

### Anti-pillars

- No direct clone of another game’s characters, item names, icons, maps, or formulas.
- No uncapped paid power, paid-exclusive combat gear, purchasable run currency, altered shop/drop odds, or mid-run Robux purchases other than the explicitly approved limited death-screen revive.
- No inventory screen that requires long reading while enemies continue attacking.
- No visual effects that hide hazards or enemy tells.
- No design that assumes a mouse, high-end device, or private server.

## 2. Core game loop

### Session loop

```text
Lobby → choose class/starter weapon → enter run → fight and collect XP
      → level-up choice → build grows → elite/boss test
      → victory or defeat → rewards/unlocks → inspect results → play again
```

### Moment-to-moment loop

1. Move to create safe lanes and group enemies.
2. Weapons attack automatically; limited active movement/combat abilities add timing skill.
3. Defeat enemies to release XP and occasional healing or event drops.
4. Decide whether to enter danger for pickups, objectives, or elite rewards.
5. Finish the wave, magnetically collect remaining drops, then resolve concise level-up and shop choices during intermission.
6. Adjust movement to exploit the build’s new strengths.

### Between-run loop

1. Receive account XP and a non-premium earnable currency.
2. Make progress on transparent challenges, classes/loadout perks if approved, and weapon unlocks.
3. Unlock new sidegrades, difficulty modifiers, cosmetics, and collection entries.
4. Select a different class/loadout perk if approved, starting weapon, map, or challenge.
5. Re-enter with more knowledge and more options—not an overwhelming permanent stat advantage.

## 3. Run structure

### Recommended first prototype

| Element | Proposal |
| --- | --- |
| Format | One enclosed arena with eight combat waves and short shop intermissions |
| Duration | Approximately 8 minutes including the final boss window |
| Players | Solo initially; architecture supports 1–4 |
| Upgrade cadence | Level-up and shop decisions at the end of each wave |
| Elite cadence | Proposed wave 4; final schedule requires playtesting |
| Boss | Wave 8; ends immediately when the boss is defeated |
| Loss condition | All participating players down with no valid recovery |
| Win condition | Defeat the final boss |

This combines Brotato’s clear escalation and build decisions with the user's preferred Survivor.io-style chapter and map model. Exact encounter timing remains open.

### Proposed run phases

| Waves | Purpose | Pressure change |
| --- | --- | --- |
| 1–2 | Learn the starting weapon and establish direction | Swarm plus one standard behavior |
| 3–4 | Specialize the build and face an elite | First build check |
| 5–6 | Combine known enemy roles, including a horde wave | Positioning and crowd-clear check |
| 7–8 | Final shop payoff and boss | Survival and damage check |

### Difficulty

**Proposal:** Unlock named difficulty tiers after a win. Higher tiers add authored modifiers and new enemy combinations, not just inflated health. Examples: earlier ranged enemies, an extra elite, faster hazard cycles, or a boss phase. Rewards should emphasize unlock progress and cosmetics rather than permanent combat dominance.

**Later:** Endless mode, daily seeded challenge, mutators, and leaderboards after the standard run is fun and stable.

## 4. Player controls and moveset

### Baseline controls

| Action | Keyboard/mouse | Controller | Touch |
| --- | --- | --- | --- |
| Move | WASD | Left stick | Virtual stick |
| Aim active skill, if applicable | Cursor/camera direction | Right stick | Drag/aim region |
| Dash / mobility skill | Space or Shift | Face/shoulder button | Large action button |
| Character skill | Q/E | Shoulder button | Action button |
| Choose upgrade | Click/number | D-pad/face button | Tap card |

**Proposal:** Basic weapons auto-target or attack based on movement/facing. The player always owns movement. Manual aiming should be reserved for a small number of high-impact skills or weapon families.

### Weapon presentation

- **Confirmed:** Melee damage does not depend on the avatar performing a full physical swing that connects with a target.
- **Confirmed:** Melee auto-attacks may use slash arcs, thrust lines, spins, ground impacts, or other readable attack effects.
- **Confirmed:** Ranged attacks show their projectiles.
- **Proposal:** A melee weapon may remain visible in the avatar's hand, on the back, or floating beside the avatar, but the attack effect—not limb contact—is the authoritative visual cue.
- **Proposal:** This presentation avoids avatar-animation and body-proportion inconsistencies while preserving readable timing and weapon identity.

### Base moveset

- Run with immediate acceleration and predictable collision.
- One short dash with charges or cooldown; invulnerability, if any, must be explicit and short.
- One character-defining passive.
- Optional character active skill only if mobile UI remains clean.
- No paid extra dash or ability slot. A separately limited death-screen revive is approved.

### Combat feel targets

- Player and enemy hitboxes favor the player slightly.
- Contact damage uses a clear cooldown so overlap does not delete health in one frame.
- Damage feedback combines animation, sound, small numbers, and hit flash without screen-filling noise.
- Enemy attacks telegraph before damage; dangerous attacks use consistent shapes and colors.
- Knockback should create space without permanently trivializing bosses.

### Combat feedback and collection feel

**Confirmed:** High-quality sound and visual feedback are core product requirements. Destroying large groups and magnetically collecting their XP, coins, or loot should be one of the most satisfying repeated actions in the game.

- Enemy hits use short, crisp impact sounds appropriate to the weapon and creature material.
- Defeats use a clear burst/pop response with controlled fragments, squash, dissolve, or other readable animation rather than disappearing silently.
- Every defeated enemy produces its own short death-feedback event, so farming a large crowd creates a rapid satisfying sequence rather than one aggregated multikill sound.
- XP, coins, and ordinary drops accelerate toward the player along clean magnetic arcs.
- Pickup chains use a rising or rhythmically building sound sequence, with special accents for a completed level, rare drop, or large collection burst.
- Important rewards look and sound different from ordinary XP before collection.
- Attack animations and effects clearly communicate direction, range, cadence, and active hit area.
- Player effects must not cover most of the screen, hide enemies, obscure boss telegraphs, or make four-player combat unreadable.
- Enemy danger cues take visual and audio priority over player spectacle.
- Screen shake, flashes, damage numbers, and effect intensity need adjustable accessibility options.
- Effects, fragments, projectiles, pickups, and sounds require pooling, sensible voice limits, and lower-cost mobile fallbacks. Performance safeguards must preserve the perception of individual rapid defeats.

Detailed requirements and target behaviors are recorded in `COMBAT_FEEL_AUDIO_VFX.md`.

## 5. Build system

### Build grammar

Each build is assembled from four layers:

```text
Character rule + weapon behavior + stat direction + effect synergies = build identity
```

A healthy build system supports at least these identities:

- Rapid projectile / on-hit
- Heavy projectile / critical hit
- Close-range orbit or sweep
- Damage-over-time / elemental spread
- Explosive area damage
- Summons or deployables
- High-speed collision or movement scaling
- Defensive retaliation
- Pickup/luck proc build
- Economy risk/reward build

### What the Brotato references teach us

- Strong characters change rules, not merely base stats.
- Meaningful bonuses become more interesting when paired with a real constraint.
- Weapons need families/tags so collecting related gear creates an understandable direction.
- Weighted offers can support a character fantasy without guaranteeing the same run.
- Cross-stat scaling creates late-run discoveries: health can power attacks, speed can power damage, armor can power retaliation, and luck can power pickup effects.
- Economy can itself be a build when saving, rerolling, and spending have tension.
- Defensive, utility, and nontraditional win styles need actual support—not just lower damage.

### Proposed stat model

Keep the visible list smaller than Brotato’s first implementation. Stats should produce perceptible changes and have clear tooltips.

| Stat | Function | Notes |
| --- | --- | --- |
| Max Health | Increases survivable damage | Core defense |
| Power | Multiplies most player damage | General offense; tune carefully |
| Attack Speed | Reduces compatible weapon cooldowns | Hard cap and diminishing returns |
| Critical Chance | Chance for critical damage | Cap at 100% |
| Armor | Reduces incoming damage | Use diminishing returns |
| Recovery | Improves passive and pickup healing | One readable sustain stat |
| Move Speed | Increases movement speed | Cap for control and networking |
| Pickup Range | Pull radius for XP and drops | Strong quality-of-life/build stat |
| Luck | Improves proc/drop quality | Publish exact affected systems |
| Engineering | Powers summons/deployables | Include only if that archetype ships |

**Open:** Whether melee/ranged/elemental need separate flat-damage stats. Recommendation: begin with Power plus tags and conditional multipliers; split stats only if testing shows they create interesting choices rather than dead offers.

### Derived/hidden values

Projectile speed, size, piercing, bounce, knockback, area size, duration, cooldown, chain count, and boss damage should be weapon/effect modifiers rather than permanent top-level stats. Surface them on relevant tooltips.

### Upgrade offer rules

**Chosen direction:** Crossing an XP threshold during combat banks a level-up rather than opening a menu. At wave end, resolve each banked level through three stat choices before opening the weapon/item shop. The combat HUD provides a brief sound, notification, and pending-choice count without pausing or slowing the wave.

- Every offer has a rarity and tags.
- Class affinity modestly increases relevant tag weight; it never removes off-build possibilities.
- Duplicate weapons can merge or rank up according to one simple rule.
- New-player protection prevents three unusable or contradictory choices.
- The offer generator respects caps, exclusions, and prerequisites server-side.
- The UI explains the numerical before/after result.
- Level-up stats are free rewards; weapons and passive items are purchased separately with run materials.

### Weapon acquisition proposal

The current preferred direction is an eight-wave shop hybrid:

- Choose a class, then one owned starting weapon assigned to that class.
- Fight a short timed wave and collect XP plus temporary shop materials.
- At wave end, magnetically collect remaining drops, resolve level-up stat choices, and open a personal four-offer shop.
- Buy new weapons and passive items, reroll, recycle, or lock an offer.
- Every unlocked weapon can appear for every class. The selected class, equipped copies, and shared combat tags change probability rather than imposing restrictions.
- Weapon slots initially draw from explicit pools: 30% exact equipped weapon, 25% shared tag, 20% selected class, and 25% all unlocked weapons.
- A tracked-weapon protection system prevents more than two completed intermissions of duplicate starvation.
- Luck improves rarity, not weapon identity or class matching; the shop explains this directly.
- Two identical same-tier weapons automatically combine, up to Tier 4.
- Elite, horde, and boss waves break up the ordinary sequence.
- The entire combat build and run currency reset when the chapter ends.

This is a proposal based on the user's preferred Brotato-style intermission flow, adapted to an approximately eight-minute chapter. Details are documented in `WEAPON_SYSTEM_OPTIONS.md` and `PROGRESSION_AND_SESSION_FLOW.md`.

### Item design rules

Every modifier should fit at least one category:

| Category | Job | Example pattern, not final content |
| --- | --- | --- |
| Foundation | Establish a direction | More attack speed, less per-hit damage |
| Converter | Make one stat power another | Bonus damage from movement speed |
| Enabler | Unlock a behavior | Projectiles gain one bounce |
| Multiplier | Reward an established build | Critical hits trigger a small shockwave |
| Defense | Prevent or recover damage | Periodic shield or low-health recovery |
| Economy | Trade present power for future power | Save currency for compounding reward |
| Wildcard | Change a rule | Fewer weapons but each becomes stronger |

Avoid upgrades that are always correct, invisible in play, or useful only because the numbers are undertuned elsewhere. Powerful effects may carry a downside, cap, rarity, or mutually exclusive group.

### Synergy and tag system

**Proposal tags:** Projectile, Melee, Area, Elemental, Explosive, Summon, Deployable, Critical, On-Hit, Movement, Defense, Recovery, Pickup, Luck, Economy.

Each weapon has one home class and several combat tags. Equipped copies, shared combat tags, and the selected class feed separate visible shop pools while global rolls still permit discovery. Home-class weapon counts activate the selected class's 2-piece and 4-piece affinity bonuses; off-class weapons remain fully functional and may benefit from matching combat-tag bonuses. Exact weighting must be shown in the UI and tested for build completion rate.

## 6. Weapons

### Weapon data contract

Each weapon definition should contain:

- Stable ID, display name, rarity/availability, tags, and icon/model references
- Targeting rule and attack shape
- Base damage, cooldown, range, and knockback
- Scaling coefficients and compatible modifiers
- Projectile count/speed/lifetime or melee arc parameters
- Rank changes at every tier
- Proc rules, caps, and exclusions
- VFX/SFX budget and mobile fallback

### Proposed launch roster

The current plan contains six weapons for each of six classes, totaling 36. The complete allocation is maintained in [CURRENT_GAME_STRUCTURE.md](CURRENT_GAME_STRUCTURE.md) and [BRAINSTORM_FUNNY_GEAR.md](BRAINSTORM_FUNNY_GEAR.md).

**Proposal:** Prototype six mechanically distinct weapons—one signature weapon per class—before expanding. Do not build dozens of weapons before targeting, hit detection, tier transformations, and readability feel good.

## 7. Avatar and build identity

### Baseline avatar rules

- The player's Roblox avatar is their character.
- Class choice changes mechanical affinities and determines which owned class weapon can be selected as the guaranteed starter; it never replaces the avatar.
- Six mechanical classes launch with equal weapon counts: Brawler, Gunner, Thrower, Juggler, Handyman, and Mage.
- Run choices remain the largest source of damage, defense, speed, luck, summons, and other specialties.
- Avatar scaling and accessories cannot alter combat hitboxes or grant an advantage.
- Attacks originate from standardized positions around common R6/R15 proportions; weapons do not need persistent held models.

### Class-guided build archetypes

Each class begins with one of its owned weapons and biases relevant shop offers, but it does not hard-lock the run. Off-class weapons can appear at a lower rate after their blueprints are owned, allowing hybrid builds. The production plan stays even: six signature weapons for the prototype, two weapons per class for the vertical slice, and six per class for a 36-weapon launch roster.

## 8. Enemies, elites, and bosses

### Enemy role roster

| Role | Purpose | Readability requirement |
| --- | --- | --- |
| Swarm chaser | Creates density | Small, simple silhouette |
| Fast flanker | Breaks circular kiting | Distinct movement tell |
| Charger | Forces a dodge lane | Long windup and path indicator |
| Ranged attacker | Denies safe stationary play | Visible shot tell/projectile |
| Zoner | Creates temporary unsafe ground | Clear duration and border |
| Tank | Holds space and shields softer threats | Large body, low speed |
| Buffer/support | Raises priority of a group | Visible link or aura |
| Summoner | Converts time into more pressure | Interruptible cast cue |
| Loot carrier | Offers optional risk/reward | Visually non-hostile until engaged |

### Encounter rules

- Introduce one new behavior at a time, then combine known behaviors.
- Difficulty comes from role composition and timing before raw stat multiplication.
- Spawn outside immediate attack distance and never on top of a player.
- Maintain a server-authoritative population budget and per-device visual budget.
- Culling visual bodies must not silently deny earned XP or trigger rewards incorrectly.
- Elite and boss attacks must remain readable in four-player effect density.

### Confirmed initial enemy roster

- Zombies: common slow chasers
- Slimes: common enemies that split once
- Mummies: durable enemies that briefly slow with thrown wraps
- Witches: ranged spellcasters
- Goblins: quick light enemies
- Assassins: rare flankers with a visible dash cue
- Ghosts: enemies with short phasing movement
- Skeletons: fragile ranged attackers
- Vampires: evasive attackers that retreat after striking
- Werewolves: pursuers that become faster over time
- Knights: armored enemies that resist frontal damage
- Garden gnomes: small ambushers that freeze briefly
- Crabs: sideways-moving enemies
- Ogres: rare heavy units with a slow warned slam
- Trolls: rare durable units with limited regeneration
- Snakes: curved movers with a short prepared lunge
- Spiders: zoners that place temporary webs

Each name represents one mob, not a family containing several production variants. Variants are deferred unless later playtesting demonstrates a specific encounter gap.

Confirmed boss directions are **Cyclops, Giant Crab, Ogre Warlord, Headless Knight, Pharaoh**, and a mythic reptile slot that may become a **Dragon or Hydra**. Bosses are scheduled encounters and are never selected by the ordinary mob spawn roll. Additional regular creatures and boss candidates are tracked separately in `BRAINSTORM_MOBS_BOSSES.md`.

### Spawn hierarchy

Regular mobs are not equal. The spawn director uses a threat budget rather than treating every creature as one spawn. Working categories:

| Category | Typical budget cost | Relative frequency | Purpose |
| --- | ---: | --- | --- |
| Swarm | 1 | Very common | Creates readable crowd density |
| Standard | 2 | Common | Adds one simple behavior |
| Specialist | 3–4 | Occasional | Forces a positioning response |
| Heavy | 6–10 | Rare | Creates a temporary priority or obstacle |
| Elite | 12–20 and scheduled | Very rare | Tests the build without being a chapter boss |
| Boss | Separate encounter | Never in normal rolls | Major timed fight with a dedicated pattern set |

Exact costs and frequencies depend on the chapter minute, difficulty, party size, and active population. A heavy unit such as an ogre or troll replaces several weaker spawns instead of simply being added on top of them.

### Mob and map separation

**Confirmed:** Map themes and mob types are selected separately. The environment controls geometry, landmarks, hazards, and presentation; the mob roster controls combat pressure. A beach can contain vampires, a graveyard can contain goblins, and crabs can appear away from water if the chapter combination calls for it.

Mob comedy should come from living or undead creatures, their proportions, equipment, animation, and behavior. Do not use ordinary animated appliances, furniture, office supplies, food, or construction objects as mobs.

### Boss principles

- A boss has two or three learnable patterns, not a giant health bar alone.
- Damage windows reward build strength without invalidating survival builds.
- Adds and hazards reinforce the boss fantasy.
- Phase changes are announced visually and audibly.
- One run should not fail due to an unavoidable attack or off-screen spawn.

## 9. Map and world

### Chapter and map model

**Confirmed direction:** Main progression follows a long sequence of authored chapters. Chapters reuse three readable geometry families inspired by Survivor.io's level-design structure while using original environments, encounters, and layouts:

| Family | Geometry | Gameplay effect |
| --- | --- | --- |
| Open | Wide space without enclosing walls | Maximum freedom to kite, explore, and approach spawns from many angles |
| Corridor | Long route constrained on two opposing sides | Funnels enemies, emphasizes forward/backward movement, and changes projectile value |
| Enclosed | Compact arena bounded on all sides | Higher encounter density and quick completion/farming potential |

All three families should target approximately eight minutes. Geometry cannot be purely cosmetic: it should change which weapons, movement patterns, enemy roles, and objectives are useful. Chapters do not contain mid-level checkpoints.

### Map goals

- Support looping, regrouping, and escape routes without making one path dominant.
- Provide recognizable landmarks so players can communicate in co-op.
- Preserve camera visibility near walls and props.
- Use collision shapes that match what players see.
- Keep traversal geometry simple enough for large enemy crowds.
- Place optional risk/reward events away from the safest route.

### Open-arena rule

**Confirmed visual reference:** Maps resemble a broad outdoor basin or clearing viewed from an elevated third-person camera. The floor can roll gently and contain sparse natural dressing, but it remains one continuous combat space rather than an intricate explorable level.

- Roughly 75–85% of the movement area stays open at a glance.
- Gentle hills and shallow dips are acceptable; cliffs, ledges, and elevation that interrupt movement are not.
- A small number of widely spaced rocks, grass clumps, logs, or trees can sit inside the arena as visual landmarks. They cannot form chokepoints or dense clusters.
- Terrain ridges, cliffs, tree lines, water, walls, or scenery form a readable outer rim like the supplied reference image.
- Most large trees and themed props sit on or beyond that outer rim, creating depth without filling the battlefield.
- No shelves, furniture layouts, small rooms, platforming, obstacle courses, mazes, required doors, or narrow gaps.
- Use few or no map hazards. Combat readability and room to kite matter more than environmental mechanics.

The three geometry families still work, but they describe only the arena's outer shape:

- **Open:** a wide field whose edges are distant or visually hidden;
- **Corridor:** a wide, long strip with two simple opposing boundaries;
- **Enclosed:** one open square or circle with four visible outer boundaries.

### Proposed map themes

Every theme uses the same sparse, wide-arena philosophy shown in the supplied reference.

| Map theme | Arena treatment | Outer rim and skyline | Natural boss pairing |
| --- | --- | --- | --- |
| **Pine Valley** | Rolling grass clearing with a few scattered stones and grass clumps | Rocky basin walls, pines, distant hills | Cyclops or Ogre Warlord |
| **Beach Cove** | Broad sand with a few tide pools and driftwood pieces | Ocean, rocky headlands, palms, distant boardwalk | Giant Crab |
| **Desert Basin** | Open sand with sparse cracked stone | Canyon walls, ruined columns, tents, distant pyramids | Pharaoh |
| **Castle Fields** | Open grass or packed earth with occasional worn stone patches | Castle walls, towers, banners, distant village | Headless Knight |
| **Frozen Pass** | Broad snowfield with sparse ice patches | Snowbanks, ice cliffs, pines, mountains | Dragon or remixed boss |
| **Volcanic Crater** | Dark open ground with nonblocking glowing cracks | Crater walls, smoke, distant lavafalls | Dragon or Hydra |

Build **Pine Valley** first because it most closely matches the approved spatial reference. The other maps should feel like environmental reskins and broad shape changes of that readable arena concept, not conventional Roblox adventure maps.

The supplied desert reference also confirms the target for **Desert Basin**: a large sandy bowl surrounded by oversized rock formations, with only widely spaced cacti, bones, dead trees, grass tufts, and low rocks inside. These props provide scale and atmosphere but never create corridors or complicated navigation.

### Future map variety

Different chapters primarily change arena dimensions, broad outer shape, mob composition, spawn script, boss, difficulty, ground treatment, and surrounding theme. Avoid procedural obstacle layouts, breakable shortcuts, moving physical obstacles, platforming, and gameplay-critical elevation; those work against the desired low-attention swarm combat.

## 10. Multiplayer

### Recommended direction

**Proposal:** Build the simulation for 1–4 players, ship and balance solo first, then enable co-op once performance and reward ownership are reliable.

- Enemies and rewards are authoritative on the server.
- XP can be shared within a generous radius or across the team; avoid last-hit competition.
- Level-up choices must not repeatedly freeze all players. Candidate: individual safe/slow choice with an auto-pick timeout.
- Enemy health and spawn pressure scale by active player count with diminishing per-player increases.
- Downed players may be revived through play where co-op rules allow it. A direct death-screen paid revive is approved, initially capped at one per player per chapter.
- Disconnect/rejoin policy must prevent reward duplication.
- Personal effects need visibility controls while enemy hazards remain visible.

**Open:** Shared versus individual build draft, camera independence, revive rules, and whether a run permits drop-in joining.

## 11. Progression and retention

### Account progression

**Chosen direction:** Persistent progression unlocks breadth plus a small, capped amount of weapon power:

- Starting weapon options
- Weapon blueprints, shared Universal Parts, and capped Permanent Weapon Levels 1–10
- Optional classes/loadout perks applied to the Roblox avatar
- New modifier pools and challenge modes
- Map/difficulty access
- Cosmetics, titles, banners, emotes, and collection entries
- Weapon and class mastery cosmetics, challenges, and selectable sidegrades

Permanent Weapon Level is the saved power track: approximately 10–12% maximum effectiveness per weapon as an initial target. It applies whenever that weapon is used, while all temporary Run Tiers, extra weapons, passive items, and level-up stats reset after every chapter. The player's first weapon must belong to the selected class; they do not carry a completed multi-weapon kit forward.

### Unlock philosophy

- Challenges teach playstyles: survive with a class, defeat an elite with a condition, reach a stat threshold, or win a difficulty.
- Requirements are visible before completion.
- A failed run still advances at least one understandable goal.
- New players start with enough variety to form several builds.
- Daily systems must not punish missed days or manufacture anxiety.

## 12. Economy and monetization

### Earned currencies

**Proposal:** Start with one earnable currency for unlocks and one account XP track. Add currencies only when each has a distinct, explainable job.

Run XP and run-only resources reset at the end of each run. Persistent rewards are granted once through an idempotent server receipt.

### Bounded monetization boundaries

Allowed candidates:

- Character skins with identical gameplay and hitboxes
- Weapon effect skins with equal or stricter readability budgets
- Emotes, lobby animations, titles, banners, and profile frames
- Cosmetic-only seasonal track with a permanent or returning acquisition path
- Private-server presentation/customization perks that do not affect public progression
- Earned gameplay crates containing cosmetics, with duplicate protection
- Modest account XP or persistent coin acceleration with a disclosed cap
- Direct early unlocks for classes or weapons that are also earnable through normal play and are designed as sidegrades
- Guaranteed persistent Coin and Universal Weapon Part packs that accelerate the ordinary capped Permanent Weapon Level progression
- One-time starter progression packs with fixed guaranteed contents
- Cosmetic-track XP boosts

Disallowed:

- Mid-run paid damage, health, speed, luck, rerolls, materials, weapon slots, or starting levels; the limited revive is the sole exception
- Paid-only combat characters or weapons
- Paid random gameplay cases at launch; use earned cases and guaranteed paid unlocks/Parts instead
- Energy systems that sell the right to keep playing
- Purchases that influence competitive leaderboards or challenge validity
- Uncapped stacking XP/currency multipliers or uncapped Permanent Weapon Level power
- Paid changes to shop offers, weapon evolution odds, boss drops, or crate rarity

### Monetization decision gate

Do not finalize products until the core loop retains players without rewards. Before adding a product, document its player value, price range, age-appropriateness, effect on clarity/performance, maximum gameplay advantage, free acquisition time, and why the advantage remains bounded.

The proposed currency boundaries, earned crate types, direct cosmetic catalog, capped progression boosts, prohibited power products, and Roblox policy requirements are detailed in `MONETIZATION_AND_REWARDS.md`.

## 13. Interface and onboarding

### HUD priorities

1. Health and immediate danger
2. Level/XP progress
3. Run timer and boss/elite timing
4. Equipped weapons and cooldown/level state
5. Character skill and dash state
6. Earned run resources and objective status

### Upgrade cards

Cards show the icon, short name, rarity, relevant tags, one-sentence behavior, and exact numerical change. Highlight synergy with the current build without labeling a choice as mandatory. Allow inspect/compare, but keep the primary decision readable in seconds.

### Onboarding

- First run teaches movement, XP pickup, level choice, damage tells, and boss objective through play.
- Use a shortened forgiving run rather than a long text tutorial.
- Preserve normal rewards but exclude the tutorial from competitive records.
- Test touch targets, text scale, color contrast, and controller focus from the beginning.

## 14. Roblox technical architecture

### Authority boundary

The server owns:

- Run state, timers, RNG seed, difficulty, and encounter schedule
- Enemy state and legal damage outcomes
- Player stats, build inventory, upgrade offers, and choice validation
- XP, drops, currency, rewards, unlocks, and persistence
- Revives, deaths, wins, and leaderboard eligibility

The client owns presentation, input intent, camera, local animation, sound, and non-authoritative prediction. A client may request an action; it may not declare damage, drops, inventory, currency, a level-up, or victory.

### Remote validation checklist

Validate player identity, phase, alive/downed state, cooldown, position/range, finite numeric values, allowed IDs, offer ownership, prerequisites, inventory caps, request rate, duplicate request IDs, and server-calculated results. Reject silently abusive traffic and log aggregate signals without leaking secrets.

### Data-driven modules

Recommended domains:

```text
Shared definitions: characters, weapons, upgrades, enemies, maps, difficulties
Server services: run, combat, spawn, upgrade draft, rewards, persistence
Client controllers: input, camera, HUD, effects, audio, accessibility
Tests: formulas, catalogs, RNG determinism, remote rejection, reward idempotency
```

Definitions should use stable IDs and pure data. Runtime state should never mutate the shared definition tables.

### Performance budgets to establish in prototype

- Maximum active logical enemies and separately rendered enemies
- Stress target of approximately 100 simultaneously active enemies, based on the supplied Brotato reference; the final cap must be validated on Roblox servers, low-end phones, and multiplayer
- Maximum projectiles/effects per player and per server
- Server simulation time under four-player peak load
- Network bytes/events per second during densest minute
- Lowest target phone frame time and memory use
- Object pooling behavior and cleanup after every run

Use simplified server hit tests and pooled presentation where appropriate. Never make the client authoritative merely to reach a performance target.

### Persistence

- Studio DataStores remain disabled by default.
- Use versioned schemas, retry/backoff, session-safe updates, and idempotent reward receipts.
- Practice/testing cannot grant persistent currency, unlocks, or wins.
- A failed load must not be overwritten by default data.
- Published DataStore behavior requires a documented real-environment test.

## 15. Balance framework

### Balance goals

- A focused build should feel substantially stronger than random choices.
- Several archetypes should defeat the same content through different strengths.
- Early offers should rarely end a run before player skill can matter.
- Defense and recovery have an opportunity cost but remain valid.
- Boss health must not make slow/defensive builds mathematically impossible.
- No single upgrade should be the best choice for almost every build.

### Metrics to log during development

- Win rate by character, weapon, map, difficulty, party size, and device
- Pick rate and offered-to-picked rate for each upgrade
- Build completion and synergy-tag counts
- Damage/healing by source and overkill
- Death time and damage source
- XP curve and levels reached per minute
- Rerolls spent and dead-choice offer frequency
- Enemy population, server frame time, and network load
- Tutorial completion, second-run rate, and session length

### Testing invariants

- Same seed and inputs produce the same server draft/encounter sequence where intended.
- Capped stats never exceed caps through stacking order.
- Additive and multiplicative modifiers resolve in a documented order.
- Removing/merging an upgrade recalculates from definitions, avoiding drift.
- Damage cannot be negative, NaN, infinite, or client-authored.
- A reward receipt can be retried without duplicating rewards.
- No purchase creates a paid-only combat formula, bypasses the shared Permanent Weapon Level cap, or changes run reward probability. Paid acceleration reaches only the same bounded progression available through play.

## 16. Production roadmap

### Phase 0 — Vision lock

- Choose original theme, tone, title direction, and one-sentence pitch.
- Decide solo/co-op launch intent and the exact attack-control model. The standard chapter duration and elevated third-person camera direction are selected.
- Approve the initial stat list and build grammar.
- Incorporate Survivor.io and Megabonk reference intake.

**Exit:** A player promise and prototype hypothesis we can test.

### Phase 1 — Graybox combat toy

- One arena, the Roblox avatar, three initial classes, six signature/demo weapons, six enemy types, XP, and banked level-up cards.
- Server-authoritative damage and upgrades.
- Touch/controller/keyboard movement and one mobility action.
- Performance telemetry from the start.

**Exit:** Five minutes of combat is readable and fun without persistent rewards.

### Phase 2 — Vertical slice

- Two complete chapter arenas, 12 weapons split evenly across six classes, roughly 15 passive items, 8–10 enemies, elites, and two final bosses.
- Results screen, basic unlock path, tutorial, and save schema.
- Original visual/audio direction and mobile optimization.

**Exit:** Players can form at least four recognizable builds and want another run.

### Phase 3 — Alpha

- A broader weapon/modifier pool, additional chapter factions, difficulty tiers, and co-op if validated.
- Full remote abuse review, analytics, accessibility, and device testing.
- Cosmetic prototype only after retention evidence.

### Phase 4 — Content and launch readiness

- Additional map/content chosen from playtest demand.
- Economy and ethical cosmetic store review.
- Localization, moderation surfaces, crash recovery, load testing, and live-ops tools.

## 17. Decisions needed next

These are ordered by how strongly they affect everything downstream:

1. What are the exact passive, drawback, 2-piece affinity, and 4-piece affinity for all six classes?
2. Which six weapons enter the prototype, and what are all four behavioral tiers for each?
3. Is co-op required for initial launch, or should the first public version be solo?
4. Does the player have only movement and automatic weapons, or also one universal dash/class active?
5. What are the first passive-item catalog and exact shop/economy values?
6. What final price, timer, and co-op rules should the approved death-screen revive use, and should testing ever allow a second revive?
7. Is the “impossible odd-jobs agency” a good wrapper, or should funny avatar gear use a different premise?

## 18. Current hypothesis to test

The first prototype should test one question: **Is freely moving through a bounded Roblox arena while an original multi-weapon build grows for five minutes readable, satisfying, low-stress, and controllable on both PC and touch?**

Everything not needed to answer that question—large catalogs, monetization, elaborate persistence, procedural maps, seasons, and endless mode—waits.

## 19. Reference ledger

| Intake | What it currently contributes | Confidence/status |
| --- | --- | --- |
| Brotato item list | Rarity, tradeoffs, caps, converters, effects, economy, and synergy tags | Source snapshot; extract patterns only |
| Brotato stats page | Offense/defense/economy stat taxonomy and cap considerations | Source snapshot; formulas are not project specs |
| Brotato enemies/waves page | Role-based enemies, escalation, elites/boss, population cap concept | Source snapshot; do not reuse exact tuning |
| Brotato characters page | Rule-changing passives, constraints, affinities, and playstyle unlocks | Source snapshot; do not copy character packages |
| Brotato build summary | Strength/weakness/signature-build framing for 17 characters | Partial reference; file explicitly says more entries remain |
| “Best Brotato Items (2026 Meta)” screenshot | Four useful evaluation lenses: peak rarity, scaling, defense, and economy | Unverified editorial summary, not balance evidence |
| Survivor.io chapter/map notes and supplied Reddit snapshot | Eight-minute chapter target; open, corridor, and enclosed geometry families; sequential chapter progression; no mid-level checkpoint | Direction confirmed; exact cadence and rewards still open |
| Megabonk | Awaiting intake | Open |

Detailed source notes are kept in `REFERENCE_NOTES_BROTATO.md` so this master document stays focused on our game.

## 20. Change log

- **0.1 (2026-09-14):** Created initial discovery document from the user’s goal and supplied Brotato references. Added proposals for loop, run structure, combat, builds, stats, weapons, enemies, map, multiplayer, progression, fair monetization, Roblox authority, balance, testing, and production phases. No theme or major format decision has been treated as confirmed.
- **0.2 (2026-09-15):** Corrected the unsupported assumption that players would use Roblox avatars. Recorded avatar use as one open option. Confirmed the approximate eight-minute chapter target, no mid-level checkpoints, low-attention play, sequential chapters, and three Survivor.io-inspired geometry families. Removed the 12-minute run proposal.
- **0.3 (2026-09-15):** Confirmed Roblox avatars and a funny equipment direction. Recorded that each chapter can have its own map-specific mob theme. Added the impossible odd-jobs agency as a candidate wrapper and replaced generic prototype weapon placeholders with comedic everyday equivalents.
- **0.4 (2026-09-15):** Clarified that the arsenal mixes a small number of real weapons with a larger absurd pool. Added Fart Gun, Frying Pan, Nunchucks, Steak, Bowling Ball, Katana, Boomerang, Kunais, Glock, Draco, Molotovs, Yo-Yo, Excalibur, and Eggs to the working pool. Removed generic Sword, Spear, Axe, and Great Hammer concepts. Confirmed abstract melee effects without contact-dependent swing animation and visible ranged projectiles.
- **0.5 (2026-09-15):** Added construction, restrained mythology, and magic as candidate weapon families. Confirmed Mjölnir as a later weapon and recorded a flexible Magic Staff direction. Used the supplied Brotato weapon catalog to identify overlap risks rather than importing its roster.
- **0.6 (2026-09-15):** Confirmed Nail Gun, Spatula, Boomerang, Bowling Ball, and Kusarigama in the working weapon pool. Added abstract melee behaviors for Spatula and Kusarigama.
- **0.7 (2026-09-15):** Confirmed Boxing Gloves, Rubber Ducks, and Cinder Blocks as orbiting weapons with distinct rapid, outward-strike, and heavy-knockback behaviors.
- **0.8 (2026-09-15):** Removed the playable-character roster direction. Confirmed that Roblox avatars share baseline rules and derive all mechanical identity from builds. Added the initial zombie, slime, mummy, witch, goblin, assassin, ghost, and skeleton pool plus Cyclops as a boss candidate.
- **0.9 (2026-09-15):** Confirmed vampires, werewolves, knights, living garden gnomes, and crabs. Rejected animated-object mobs. Separated map theme/geometry from mob-family selection so chapters can remix the two independently.
- **0.10 (2026-09-15):** Confirmed ogres, trolls, snakes, and spiders. Separated ordinary spawns, rare/heavy mobs, elites, and bosses. Added a threat-budget model so stronger mobs appear less frequently and replace several weak spawns.
- **0.11 (2026-09-15):** Simplified every confirmed enemy to one mob entry with one primary role. Removed the five-variant-per-family direction and deferred variants until playtesting identifies a real need.
- **0.12 (2026-09-15):** Confirmed Giant Crab, Ogre Warlord, Headless Knight, Pharaoh, and a Dragon-or-Hydra mythic boss direction alongside Cyclops.
- **0.13 (2026-09-15):** Made satisfying combat audio, enemy bursts, magnetic reward collection, clean attack animation, and strict screen-readability budgets core requirements rather than late-stage polish.
- **0.14 (2026-09-15):** Rejected multikill audio aggregation. Each enemy defeat now produces an individual short feedback event even during mass farming. Added approximately 100 simultaneous active enemies as a prototype stress target, with final limits pending Roblox performance tests.
- **0.15 (2026-09-15):** Added a proposed continuous weapon system: one selected starter, five temporary active slots, direct in-run leveling, five passive slots, and passive-paired evolutions from elite/boss rewards. Kept the design unconfirmed pending discussion, especially armor's persistent versus temporary role.
- **0.16 (2026-09-15):** Replaced the continuous level-draft recommendation with a proposed eight-wave combat/shop loop based on the user's preferred structure. Documented lobby flow, saved versus temporary data, run and account currencies, chapter progression, results, mastery, and an optional class/loadout-perk system that preserves Roblox avatars.
- **0.17 (2026-09-15):** Confirmed selectable classes that do not alter Roblox avatars. Added an earned cosmetic-crate system and a direct-purchase cosmetic catalog. Limited purchasable boosts to cosmetic-only progress because the project prohibits paid gameplay advantages.
- **0.18 (2026-09-15):** Changed the project monetization rule at the user's direction. Purchases may now provide bounded progression acceleration and direct early access to earnable sidegrades, while paid-exclusive combat content, uncapped power, altered run RNG, and mid-run rescue purchases remain prohibited.
- **0.19 (2026-09-15):** Proposed six launch maps across the open, corridor, and enclosed families, plus three expansion candidates. Established that numbered chapters remix maps rather than requiring a new environment every time, and kept hazards slow enough for low-attention play.
- **0.20 (2026-09-15):** Corrected the map proposal: combat spaces are broad, flat, and almost entirely unobstructed rather than intricate environments with internal props or navigation. Themes now come from floor treatment, outer boundaries, and background scenery.
- **0.21 (2026-09-15):** Incorporated the supplied visual reference. Maps are now defined as broad outdoor basins or clearings with gentle terrain, sparse natural landmarks, scenery-heavy outer rims, and an elevated third-person view. Proposed Pine Valley, Beach Cove, Desert Basin, Castle Fields, Frozen Pass, and Volcanic Crater as the initial environment set.
- **0.22 (2026-09-15):** Chose end-of-wave stat decisions for the wave/shop structure. Combat level-ups now bank free stat choices, which resolve before a separate four-card weapon/item shop. Added the supplied desert arena as the specific Desert Basin visual reference.
- **0.23 (2026-09-15):** Added permanent weapon blueprints, Parts, capped Weapon Levels, and deterministic acquisition alongside earned cases. Defined the tutorial, first lobby return, first full eight-wave chapter, result transfer, second-run loop, an initial weapon/passive pool target, and paid Coin/Universal Parts shortcuts.
- **0.24 (2026-09-15):** Renamed the unclear persistent upgrade terminology to Permanent Weapon Level. Required starting weapons to match the selected class, established equal class weapon counts at every production milestone, raised the launch target to 30 weapons across six classes, and required each temporary combination tier to add a visible mechanical upgrade rather than only stats.
- **0.25 (2026-09-15):** Made all unlocked weapons available to every class while retaining soft class, tag, and duplicate weighting. Added 2-piece/4-piece class-affinity bonuses, cross-class tag synergy, visible offer-source labels, explicit Luck behavior, and tracked-weapon protection against duplicate starvation. Incorporated current Brotato shop mechanics and the complete supplied 2022 feedback thread as reference evidence rather than instructions.
- **0.26 (2026-09-15):** Added a consolidated full-game blueprint covering the player journey, all six classes and 30 proposed weapons, map-specific first-clear mob rosters and bosses, lobby stations, permanent and temporary progression, monetization, recommended content scope, and an explicit missing-design checklist. Reconciled the prototype and camera language with current decisions.
- **0.27 (2026-09-15):** Confirmed that equipped weapons are not continuously visible and removed weapon skins from the core plan. Removed armor as a separate equipment system while retaining Armor as a combat stat. Defined passives, reduced weapon progression to Blueprint, Universal Parts/Permanent Level, and non-power Mastery, approved simple telegraphed enemy behaviors plus limited Zombie/Skeleton/Slime variants, and strengthened the monetization proposal with Gems, bundles, VIP benefits, daily deals, a premium progression track, and a test-only pre-equipped Continue Ticket.
- **0.28 (2026-09-15):** Replaced the tentative pre-equipped Continue Ticket with a confirmed direct death-screen paid revive. Proposed one revive per chapter, approximately 65 Robux, 50% restored health, three seconds of invulnerability, nearby-enemy pushback, receipt validation, and recorded revive counts. Removed Protein Shake's movement penalty and added life-steal, burn, ice, lightning, and poison passive concepts.
- **0.29 (2026-09-15):** Confirmed that new accounts begin with Brawler, Gunner, and Mage while Thrower, Juggler, and Handyman are early earnable or purchasable unlocks. Defined the class value structure as an always-active specialization plus two- and four-home-weapon affinities, with no mandatory class drawbacks and one wildcard weapon slot preserved.
- **0.30 (2026-09-15):** Added Bowling Pins as a Juggler orbital and Deck of Cards as a Thrower projectile. Expanded every class evenly from five to six launch weapons by adding Baseball Bat, Rocket Launcher, Power Washer, and Crystal Ball, raising the launch roster from 30 to 36.
