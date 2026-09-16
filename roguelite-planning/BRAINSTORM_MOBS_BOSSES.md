# Mob and Boss Roster

**Status:** Simplified planning roster  
**Rule:** Keep behaviors basic and reusable. Purposeful variants are allowed for foundational families, but do not create five versions of every mob. Zombies may have regular/crawler/large forms, Skeletons may have melee/bow forms, and Slimes may have small/big splitter forms.

## Basic behavior kit

- **Melee chaser:** walks to the player and uses a basic swing/contact hit.
- **Ranged shooter:** stops and shows a thin red aim line before launching one visible projectile.
- **Dasher:** pauses and shows a wide red lane before dashing through it.
- **Heavy chaser:** larger, slower, tougher version of the basic melee behavior.
- **Splitter:** produces a small fixed number of weaker enemies on death.

No ordinary mob needs a cinematic combo, elaborate phase, or large VFX sequence.

## Current simple mob assignments

| Mob | Basic behavior |
| --- | --- |
| Regular Zombie | Slow melee chaser |
| Crawler Zombie | Small, low-health fast melee chaser |
| Large Zombie | Heavy melee chaser; slower swing and lower spawn rate |
| Small Slime | Basic melee/contact chaser |
| Big Slime | Slow splitter; becomes two or three Small Slimes on death |
| Melee Skeleton | Basic melee chaser with a short sword swing |
| Bow Skeleton | Ranged shooter; thin red aim line, then one arrow |
| Goblin | Slightly fast melee chaser |
| Crab | Tough short-range melee chaser |
| Snake | Dasher; red lane, then one straight lunge |
| Spider | Fast melee chaser with low health |
| Ghost | Melee chaser; fading is cosmetic only and grants no invulnerability |
| Mummy | Slow, durable melee chaser |
| Witch | Ranged shooter; red line, then one magic projectile |
| Knight | Heavy melee chaser with a basic weapon swing |
| Vampire | Fast melee chaser; no complicated life-steal behavior required initially |
| Werewolf | Fast heavy melee chaser |
| Garden Gnome | Ranged shooter; red line, then one thrown garden object |
| Assassin | Dasher; red lane, then one quick dash |
| Ogre | Very slow heavy melee chaser |
| Troll | Slow ranged shooter that throws one visible rock after a red aim line |

These assignments are enough for the first implementation. A later playtest may add one small behavior only when two enemies feel functionally identical on screen.

## Map separation

Maps and mobs are independent. A map supplies geometry, visuals, landmarks, and hazards. The selected mob roster supplies combat behavior. Enemy types do not need to match the environment.

## Confirmed regular mobs

| Mob | Strength/frequency | Primary behavior |
| --- | --- | --- |
| Zombie | Weak; very common | Slow direct chaser |
| Slime | Weak; common | Splits once when defeated |
| Goblin | Weak; common | Quick direct chaser |
| Crab | Weak; common | Approaches with sideways movement |
| Skeleton | Standard; common | Fires slow visible projectiles |
| Snake | Standard; common | Curved movement followed by a short lunge |
| Spider | Standard; occasional | Places a temporary slowing web |
| Ghost | Standard; occasional | Briefly phases while repositioning |
| Mummy | Standard; occasional | Throws a wrap that briefly slows |
| Witch | Specialist; occasional | Casts a clearly telegraphed ranged spell |
| Knight | Specialist; occasional | Resists frontal damage |
| Vampire | Specialist; uncommon | Strikes quickly, then retreats |
| Werewolf | Specialist; uncommon | Gains speed while pursuing the player |
| Garden Gnome | Specialist; uncommon | Freezes briefly, then performs an ambush movement |
| Assassin | Specialist; rare | Circles, signals, then dashes through a line |
| Ogre | Heavy; rare | High health with one slow warned slam |
| Troll | Heavy; rare | Limited regeneration that stops while taking damage |

## Spawn weighting

Stronger mobs consume more threat budget and therefore appear less frequently:

| Category | Example | Working cost |
| --- | --- | ---: |
| Weak | Zombie, slime, goblin, crab | 1 point |
| Standard | Skeleton, snake, spider, ghost, mummy | 2 points |
| Specialist | Witch, knight, vampire, werewolf, gnome, assassin | 3–4 points |
| Heavy | Ogre, troll | 7–9 points |

If the director has 20 points, it might spawn 10 zombies, one witch, and one ogre. It does not spawn a full weak wave and then add stronger mobs for free.

Exact weights, active counts, and time windows will be established through playtesting.

## Possible additional regular mobs

Keep this shortlist small until the confirmed roster is tested:

- Bat — quick dive attacker
- Boar — straight-line charger
- Frog — marked leap attacker
- Scorpion — frontal armor with a tail-strike zone
- Raccoon — steals loose XP and runs away
- Chicken — erratic weak swarm mob

None of these are confirmed yet.

## Bosses

Bosses are fully separate from regular spawning. They receive a dedicated health bar, entrance, attack cycle, and reward.

### Confirmed

- **Cyclops:** Club slam, boulder throw, and sweeping eye beam.
- **Giant Crab:** Sideways charges, giant claw slams, and a shell-break phase.
- **Ogre Warlord:** Club shockwaves, thrown boulders, and a short enraged charge.
- **Headless Knight:** Mounted charge lanes followed by close-range spectral slashes.
- **Pharaoh:** Rotating curse attacks, summoned guards, and collapsing sand lanes.
- **Dragon or Hydra:** Confirmed mythic-reptile boss slot; exact creature remains open. A Dragon favors breath attacks and aerial passes, while a Hydra favors multiple aimed attacks and changing heads.

### Candidates

- Slime Monarch
- Bone Colossus
- Goblin King
- Grand Witch
- Vampire Count
- Alpha Werewolf
- Troll King
- Spider Queen
- Basilisk
- Lich
- Minotaur
- Gnome Giant

Boss candidates are names and broad directions only. Their full attack kits should be designed after choosing which ones will actually appear in the initial chapters.

## Scope recommendation

Do not build all 17 regular mobs for the first prototype. Start with approximately six:

- Zombie
- Skeleton
- Slime
- Witch
- Knight
- Ogre

This set tests chasers, projectiles, splitting, spell telegraphs, directional defense, and rare heavy pressure. Add other confirmed mobs only after those behaviors are readable and performant.
