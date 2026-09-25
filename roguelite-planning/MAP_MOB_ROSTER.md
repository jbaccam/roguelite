# Map Mob Roster

Updated: 2026-09-24

This is the current planning roster and supersedes earlier map/mob assignments in CURRENT_GAME_STRUCTURE.md, MASTER_GAME_DESIGN.md, and BRAINSTORM_MOBS_BOSSES.md. It records future content, not a claim that every enemy is implemented.

The user approved the themed rosters, requested ranged enemies for Frozen Pass and Volcanic Crater, specified a very fast snake leap/lunge, and specified an enormous King Crab boss. Ash Shaman is the working design choice for the new volcanic ranged slot; its name and exact attack are provisional.

| Map | Regular mobs | Dedicated ranged mob | Boss |
| --- | --- | --- | --- |
| Pine Valley | Regular Zombie, Baby Zombie, Tank Zombie | Spitter Zombie (later addition) | Hammer Zombie Boss |
| Beach Cove | Crab, Snake, Hermit Crab, Rock-Throwing Crab | Rock-Throwing Crab | Giant King Crab |
| Desert Badlands / Desert Basin | Skeleton, Bow Skeleton, Mummy, Scorpion | Bow Skeleton | Pharaoh |
| Frozen Pass | Frost Ghost, Werewolf, Frozen Knight, Ice Elf | Ice Elf | Frost Cyclops |
| Volcanic Crater | Fire Goblin, Ember Spider, Lava Slime, Obsidian Ogre, Ash Shaman | Ash Shaman | Dragon |

## Behavior direction

- **Regular Zombie:** main slow melee crowd.
- **Baby Zombie:** fast, fragile melee pressure.
- **Tank Zombie:** slow, durable heavy with a warned attack.
- **Spitter Zombie:** future ranged projectile enemy; not required to finish Pine Valley's first version.
- **Crab:** basic short-range melee chaser.
- **Snake:** a brief readable windup followed by a very fast forward leap/lunge. Lock its direction before launching, avoid midair homing, and include recovery between attacks. Players should be wary of the burst even though the warning gives them a fair dodge opportunity. Exact timing is for playtesting.
- **Hermit Crab:** slow, tough melee enemy.
- **Rock-Throwing Crab:** stops, aims, and throws a visible dodgeable rock from range.
- **Skeleton:** basic melee chaser.
- **Bow Skeleton:** stops, aims, and fires a visible arrow from range.
- **Mummy:** slow, durable melee pressure.
- **Scorpion:** warned straight lunge with recovery.
- **Frost Ghost:** basic melee chaser; cosmetic fading must not hide attack cues.
- **Werewolf:** fast, tougher melee pursuer.
- **Frozen Knight:** slow armored melee threat.
- **Ice Elf:** dedicated ranged enemy that shoots visible icicles after a clear aim warning. Attacks from a distance; icicles must stay readable against snow and ice scenery.
- **Fire Goblin:** basic melee crowd.
- **Ember Spider:** fast, fragile melee pressure.
- **Lava Slime:** splits once into two smaller slimes; children do not split again.
- **Obsidian Ogre:** slow, durable heavy with a clearly warned attack.
- **Ash Shaman:** working volcanic ranged design; stops and fires a visible fireball after an aim warning. Keep projectiles distinguishable from background lava and friendly effects.

## Boss direction

- **Hammer Zombie Boss:** Pine Valley's existing user-created boss direction replaces Ogre Warlord.
- **Giant King Crab:** an enormous king crab, dramatically larger than players and regular crabs, with a broad body, long legs, and massive claws. It should dominate the arena visually while leaving navigable dodge space and readable attacks. Exact scale and attack kit still need testing.
- **Pharaoh:** Desert boss; full attack kit remains to be designed.
- **Frost Cyclops:** Frozen Pass boss; full attack kit remains to be designed.
- **Dragon:** Volcanic Crater boss; replaces the earlier undecided Dragon/Hydra slot. Full attack kit remains to be designed.

## Scope and implementation

Pine Valley starts with its three existing regular zombie types and hammer boss. Finish and test those before adding Spitter Zombie. Beach, Desert, and Frozen Pass each plan four regular types; Volcanic Crater plans five to preserve its accepted four and add a dedicated ranged enemy. The full future roster totals 21 regular types (including Spitter Zombie) and five bosses.

Castle Fields and the older mixed creature pool remain later-content ideas, outside these five maps. First-clear rosters establish each map's identity; later difficulties may remix enemies. Ordinary mobs reuse simple chaser, heavy, ranged, lunge, and splitter behaviors. Enemy simulation, attack validation, damage, and rewards remain server-owned.
