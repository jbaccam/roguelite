# Crystal pickup XP and HUD

September 22, 2026. RunXP contains tunable thresholds and pure overflow arithmetic. ShopService owns each player's level, XP and pending level-ups, publishing RunLevel, RunXP, RunXPRequired and PendingLevelUps. ShardDropService marks the successful arrival callback as a physical pickup; only that path awards XP. No client reward remote, persistent storage, paid progression or changes to combat stats.

UI uses original uploaded references via ImageRect atlas cropping. Runtime texture sizes were verified with EditableImage readback: shard 1024×1024, XP reference 1023×341. The baked sample XP and level are covered by a dynamic track and live text; the original faceted green region supplies the fill. No generated replacement image is used. Shop and test buttons moved below the HUD; narrow-screen timer placed below the XP area.

## XP Gain (2026-10-12)

The `XPGain` stat (0% base, -50% to +200%) raises run XP per crystal. Shards never change. `RunXP.gain(total, xpGainPercent, carry)` returns whole XP and keeps the fraction in `s.xpCarry` (set to 0 in ShopService's `newState`, so a new run or reset starts clean, and the rejoin stash keeps it). `ShopService.creditShards` reads `Characters.states[p].stats.XPGain`.

- +15%: 1 crystal = 1.15 XP, 20 crystals = 23 XP and 20 shards.
- Seven single crystals at +15% give 1, 1, 1, 1, 1, 1, 2 = 8 XP, with 0.05 carried.
- Sources: the XP Gain level-up card (+8 / 12 / 18 / 25 by tier) and three shop items: Homework Flashcards (Tier I, +10%), Participation Trophy (Tier II, +20%), Gold Star Stickers (Tier III, +35%, -5% damage). Icons are placeholders (the XP quest icon) until the user's art is uploaded.
- Offline checks: `run_shop_tests.py` (ShopPreferenceTests). Not play-tested in Studio yet.

## Verified

- RunXPTests.luau: 22 assertions passed in Studio using actual server-created death drops, magnetic pickup and ShopService reward callback.
- Exact rollover, multiple-level overflow, invalid amounts, max level, zero XP for starting/debug currency, no XP at spawn or before resting, both rewards on arrival, no duplicate reward, ten pickups to level 2, subsequent pickup progression, replicated attributes, no pickup XP from uncollected banking, spending preserves XP and no out-of-combat drops.
- Client confirmed 2/30 XP, LV.2, ratio 0.0666667, correct fill size, and both uploaded images loaded.
- Studio visual inspection at low and half fill: original green potion, faceted fill, live numbers, shard icon, and unobstructed HUD. Half-fill state was a temporary display test, not an earned progression claim.
- Root and roguelite Rojo packages built successfully after final sync.
- Fresh Play startup had no console errors and reset to level 1, 0/20 XP. A 390-pixel-wide HUD-layout check found no timer/XP overlap; the XP bar stayed inside the viewport. This is a layout check, not full device emulation. Test fixtures were removed by ending Play.

Tests are disposable Play fixtures, excluded from Rojo mappings. Multiplayer contention, published-asset permissions, full phone device emulation and intermission upgrade-choice resolution are not covered. Pending levels are recorded only; this change does not implement stat-choice rewards.
