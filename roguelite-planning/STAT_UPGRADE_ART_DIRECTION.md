# Roguelite stat upgrade art direction

This page is for the **roguelite**. It does not describe Copy The Scene. The live level-up catalog has 16 stat choices; its IDs and numbers remain authoritative in `studio-prototype/combat/LevelUpCatalog.luau`. This is a concept shortlist for their names and icons, before image generation. It does not change gameplay.

## The joke

Treat each upgrade as something an overconfident Roblox avatar found in a gym locker, garage, or backpack and decided was a legitimate training method. The object should be funny at card size, while the stat line states the exact effect. Use one icon per stat across all tiers; rarity belongs to the card frame, not the image.

| Stat ID | Card nickname | Image subject | Why it reads |
| --- | --- | --- | --- |
| MaxHP | Spare Heart | Cartoon heart in a labeled spare-parts pouch | Extra capacity without looking like healing over time |
| Damage | Brick Workout | Flexing arm curling a single brick | Absurd strength training; broad damage stat |
| AttackSpeed | Wind-Up Elbow | Bent arm with a large toy wind-up key and speed lines | Faster attacks, clearly different from movement speed |
| Armor | Traffic Cone Helmet | Scuffed orange traffic cone worn as a helmet | Improvised protection with a strong silhouette |
| Dodge | Cardboard Decoy | Flat avatar cutout with an attack whizzing past | Avoided hit, rather than defense or speed |
| Regeneration | Self-Fixing Bandage | Bandage rolling itself back onto a small heart | Health coming back over time |
| LifeSteal | Vampire Lunchbox | Lunchbox with tiny fangs and a heart-shaped clasp | Health gained by attacking; no blood imagery |
| CritChance | Bullseye Knuckle | Fist stamping a small star into the center of a target | Occasional especially good hit |
| MeleeDamage | Knee of Justice | Bent knee striking a small impact star | Close-range hits, comedic and distinct from general damage |
| RangedDamage | Finger Cannon | Cartoon finger-gun hand launching a chunky foam dart | Stronger shots and throws, without copying a real firearm |
| ElementalDamage | Pocket Weather | Tiny storm cloud, flame, and spark crammed into a jar | One shared elemental stat instead of only fire |
| UtilityPower | Certified Duct Tape | Roll of duct tape stamped with a ridiculous approval seal | Improvised engineering and gadget power |
| MoveSpeed | Wheelie Sneakers | Pair of worn sneakers with small wheels and motion arcs | Movement, not attack cadence |
| PickupRadius | Crystal Lasso | Wide rope loop pulling in three blue shards | The pickup behavior at a glance |
| Luck | Suspicious Penny | Bent copper penny with a tiny good-luck sparkle | Funny superstition; separate from critical hits |
| AttackRange | Telescoping Arms | Spring-loaded extending arm reaching toward a target | Longer reach for any weapon type |

## Best four to sample first

Generate **Brick Workout**, **Traffic Cone Helmet**, **Vampire Lunchbox**, and **Telescoping Arms** first. They test the joke, material variety, readability, and the more unusual stat concepts. If those four feel right together at 64 px and 24 px, generate the rest as a matching family.

## Image generation rules

- Use the existing 512×512 transparent PNG specification in `STAT_ICON_GENERATION_LIST.md`.
- Each icon is a single centered object or tight two-object action, with a bold dark outline and generous clear padding.
- Keep the base palette consistent with the roguelite's existing item art. Save rarity colors and borders for the UI.
- Put no words, numerical values, card frame, or tiny detail in the image. Nicknames are UI text only.
- Avoid repeating passive-item art: Lucky Sock, Fridge Magnet, and Grandma's Oven Mitt are already shop items.
- Preserve the stat ID and plain-language effect on the card, for example **Brick Workout — Damage +8%**.
- The 31 secondary stats and shard bag in `STAT_ICON_GENERATION_LIST.md` can stay literal. Their job is fast recognition in a dense stats panel.

## Roblox content boundary

Do not name or depict the upgrade as **Steroids**, a syringe, pills, or a performance enhancer. Roblox's [Community Standards](https://en.help.roblox.com/hc/en-us/articles/203313410-Roblox-Community-Standards) explicitly prohibit depiction or promotion of dietary supplements and enhancers such as steroids. Cartoon improvised training props carry the same joke without that content.
