# Skill Tree

The lobby's permanent upgrade screen. Players spend **emeralds** on small stat bonuses that apply to every run.

- **Open it:** the SKILLS button on the right rail, or the **K** key.
- **Code:** `studio-prototype/combat/SkillTreeConfig.luau` holds the data and rules. `studio-prototype/ui/SkillTreeUI.luau` is the screen.
- **Where it plugs in:** `ProfileService.buySkill` validates and saves purchases. `CharacterService.refresh` applies the bonuses.

## Currency

Skills cost emeralds. Since 2026-09-27, emeralds are the game's only account currency; keys were dropped because two currencies were confusing (Final Swarm and Survive the Swarm each use one). You earn emeralds from runs, the daily free deal, codes and duplicate weapons, and you can also buy them with Robux. That makes the tree buyable, but at a heavy tax: the whole tree costs 35,600 emeralds, about the same as 14 of the biggest Robux packs.

Old saves convert each key to 20 emeralds, the old swap rate.

## Shape

The tree has 37 nodes. The centre star is free and already owned. Four arms go out from it, and each arm has:

- 4 main nodes
- 2 side branches of 2 nodes each, off the 2nd main node
- a capstone at the end

```
                     Pocket Clover
                         Luck IV
      Pickup II          Luck III          Range II
          Pickup I       Luck II      Range I
  Armor II                Luck I                  Crit II
      Armor I                                 Crit I
Tough Cookie … Max HP II  Max HP I ★ Damage I  Damage II … Sharp Stuff
      Regen I                                 Atk Speed I
  Regen II                Speed I                 Atk Speed II
          Dodge I        Speed II      Life Steal I
      Dodge II           Speed III          Life Steal II
                         Speed IV
                         Zoomies
```

| Arm | Main nodes (I–IV) | Side branch A | Side branch B | Capstone |
|---|---|---|---|---|
| Toughness (left) | Max Health +4 each | Armor +1, +1 | Regeneration +0.25 HP/s, +0.25 HP/s | **Tough Cookie**: +8 Max health |
| Offense (right) | Damage +2% each | Critical chance +2%, +2% | Attack speed +3%, +3% | **Sharp Stuff**: +4% Damage, +10% Crit damage |
| Fortune (up) | Luck +2 each | Pickup radius +1, +1 | Attack range +3%, +3% | **Pocket Clover**: +4 Luck, +1 Pickup radius |
| Agility (down) | Move speed +0.25 each | Dodge +1.5%, +1.5% | Life steal +0.5%, +0.5% | **Zoomies**: +0.5 Move speed, +2% Dodge |

## Prices

| Node | Emeralds |
|---|---|
| Main I / II / III / IV | 100 / 300 / 700 / 1,400 |
| Side branch I / II | 500 / 1,200 |
| Capstone | 3,000 |
| One whole arm | 8,900 |
| Whole tree | 35,600 |

**What that means in play time:**

- A Pine Valley win pays 80 emeralds, so a new player gets their first skill after about 2 runs.
- A Volcanic Crater win pays 400 emeralds. At that point a whole arm takes about 22 wins.
- The full tree is a long-term goal of about 25–60 hours, depending on which maps you farm.

Chests cost 60–250 emeralds, so skills compete with chests for the same emeralds. That trade-off is intentional.

## Balance ("not OP")

The whole tree maxed out gives:

| Stat | Total |
|---|---|
| Max health | +24 |
| Armor | +2 |
| Regeneration | +0.5 HP/s |
| Damage | +12% |
| Critical chance | +4% |
| Critical damage | +10% |
| Attack speed | +6% |
| Luck | +12 |
| Pickup radius | +3 |
| Attack range | +6% |
| Move speed | +1.5 (24 → 25.5) |
| Dodge | +5% |
| Life steal | +1% |

That adds up to about 8–10 common level-up cards. A single common card is +8 HP or +5% damage, and a 20-wave run gives far more cards than that. It's also about half a weapon tier: Tier II is +20% damage. Map 1 stays winnable with nothing bought, and no map needs the tree.

**Safety rules:**

- Bonuses enter `CharacterStats.resolve` as flat terms before the clamp, so no stat can pass its cap.
- Level-up cards stop offering a stat that the tree has already capped.
- None of the bonuses are weapon slots, projectile count, pierce or bounce, and nothing changes drop or shop odds.

## Server rules

`SkillTreeConfig.canBuy` enforces these rules for every purchase:

- the skill exists and isn't the centre star
- it isn't owned yet
- its parent is owned
- the player has enough emeralds

Purchases go through `ProfileAction('BuySkill', id)`, which is rate-limited like the other profile actions. The owned list saves as `profile.skills`, and old saves get an empty list automatically. The server publishes it to the `ProfileSkills` player attribute, which only the server can write, and `CharacterService` reads that attribute to apply the bonuses.

Studio only: the `DevEmeralds` (+200 emeralds) and `DevResetSkills` (refund everything) actions, shown as test buttons on the screen. Studio profiles are never saved.

## Presentation

- **Growing tree:** the whole tree is never shown. A new player sees 9 tiles: the star, the 4 skills they can buy, and one "?" past each. Buying a skill grows the tree outward, and the view eases out to fit it, so the tree gets bigger as you unlock more.
- **Opening:** the screen blurs and darkens. Two lime rings roll out from the star, and the visible nodes spring out from the centre in waves ordered by distance. Each link draws outward from its parent once its child lands, and there's a soft airy whoosh.
- **No spinning rays.** Those are kept for the store.
- **Node states:**
  - owned: lime tile
  - buyable: charcoal tile with lime corners; its glow breathes when you can afford it
  - next up: dark "?" tile, with its name hidden
  - further out: not drawn
  - Capstones and the star also get gold corners.
- **Buying:** a soft chime (pitched up slightly for deeper nodes). The node squashes and springs back with a white flash, a ripple ring and a few spark flecks. The links to its children charge with light. Then the "?" tiles flip into real skills, new "?" tiles grow in along new links, and the view zooms out if needed. The emerald counter ticks down with a "-300" drifting off it, and the changed rows in YOUR BONUSES flash lime.
- **Navigation:** drag to pan, scroll or pinch to zoom.
- **HUD badge:** the SKILLS button shows a red count of skills you can afford right now.

## Assets

| Asset | Source |
|---|---|
| Lobby SKILLS button | `rbxassetid://70956867630986`. User-supplied rune stone, `ui/assets/hud/skill-tree.png`. |
| Centre star icon | `rbxassetid://85339341316383`. Generated by `ui/assets/skills/make_skill_icon.py`; output `ui/assets/skills/skill-tree.png`. |
| Node icons | The existing level-up stat icons (`LevelUpCatalog.IconIds`). |
| Sounds | ProSoundEffects (Roblox library): 9120733055 "Whoosh Rising Swish Airy Various Pitches 1" (open), 9116394545 "Magic Glows Soft Clusters Of Chiming Hits 1" (buy). |
