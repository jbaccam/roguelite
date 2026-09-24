# Level-up offers and shard bags

Updated 2026-09-24 to replace the rejected reel/serif design.

## Gameplay

Collected crystal XP queues earned levels. Between waves, each earned level grants one of four distinct server-generated stat upgrades. Pending choices block the next wave. Weapons remain in the shop. Bonuses accumulate for the run and survive item bonus recomputation; existing stat caps apply. Each offer rolls its own rarity. Rerolls cost shards, with a displayed price that increases per reroll and resets for the next earned level. The banish action is removed.

## Presentation

Four immediate cards match the shop: near-black common cards without outlines, dark blue/purple/red higher rarities with colored outlines, SourceSans stat text, Fredoka headings/buttons, icon at upper left, concise green stat gain, and Choose button. The next choice set replaces the previous one immediately after the server responds. No shuffle, reels, stagger, zoom, or reveal wait remains. A Primary/Secondary stats sidebar is available, with a Show Stats toggle on narrow screens. Small portrait screens use two rows.

## Shard bags

At a normal wave end, uncollected shard value goes into the owning player's bag balance. It grants no currency or XP at that time. Each collected shard unit in a later wave consumes at most one bagged unit, adding that unit to both currency and XP. Five one-unit shards left over therefore double the next five one-unit pickups. Multi-unit drops consume the corresponding number of bag units, and a partially covered pickup gets only the remaining bonus. Unused bags carry forward. New runs reset the balance. Practice aborts clear drops without adding bags. Unowned leftovers go to the nearest living player, once. All awards and ownership checks remain on the server.

## Icons

See ../../STAT_ICON_GENERATION_LIST.md for the complete set of 48 images: 16 level-up stats, 31 secondary stats, and one shard bag. Icon attributes on LevelUpCatalog are reused by offers, the stats panel, and the HUD. Assets are preloaded when configured. Neutral initials and the existing generic bag image are temporary placeholders.

## Damage feedback

Unchanged: confirmed damage adds a 0.95-second red edge flash, bounded 0.28-second camera shake, and a bold outlined negative damage number.

## Verification

- Rojo build and source whitespace checks pass; all changed gameplay/UI scripts are synchronized into Studio Edit.
- LevelUpTests: 211 server assertions passed, including fourth-slot selection, independent distinct stat offers, caps, stacking, paid rerolls, insufficient funds, stale/replayed choices, phase gating, and removed banish rejection.
- ShardBagTests: 23 assertions passed, including five actual magnetic pickups consuming five bagged units, double currency and XP, normal sixth pickup, multi-unit and partial-bonus pickups, repeated cleanup, abort behavior, wave carryover, invalid inputs, and HUD replication.
- Actual client: paid reroll charged 2 shards and advanced the next cost to 3; three successive Choose clicks reduced pending upgrades 3 to 2 to 1 to 0, then closed offers and opened Shop.
- Actual GUI geometry and TextFits checks passed at 1920x1080, 1280x720, 1024x768, 800x600, 640x360, and 390x844. These resize checks are not real-device input tests.
- Temporary server test Scripts were removed from Studio Edit. Tests are excluded from the shipping project.
- Multiple real clients and published sessions have not been tested. Cloud saving has not been confirmed.
