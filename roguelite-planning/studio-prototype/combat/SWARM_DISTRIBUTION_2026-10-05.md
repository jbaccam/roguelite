# Continuous arrivals around the player — October 5, 2026

## Parent Studio integration

Applied to place 107877054949326. A fresh single-client Studio Play test requested 100 wave-20 Pine Valley slots with weapons disabled and God mode enabled. All 100 ordinary mobs arrived, plus the wave-20 boss. Observed ordinary groups contained 2–4 mobs; minimum interval between observed cohorts was 0.210 seconds and the full arrival span was 8.623 seconds. All eight measured sectors around the stationary player received arrivals (counts including boss: 8/17/12/16/8/16/9/15). This verifies runtime pacing and directional coverage, not sustained surrounding behavior while a player kites or mobile performance. Console output was empty after testing. Play was stopped afterward; test overrides were discarded.

The extracted director regression suite passed including paused tutorial recovery. The required combat Rojo build passed. All 18 manifest destinations matched Studio source after normalizing CRLF/LF. No published-place or production persistence tests ran.

This supersedes the group-size and cadence details in `SWARM_PRESSURE_2026-10-05.md`. Actual player feedback found the larger packets formed one dense jumble rather than surrounding the player. Increased population targets remain; distribution changes instead.

Normal waves now send 2–4 enemies every 0.22 seconds through one arrival queue shared by all refill batches. Each group advances its preferred heading by approximately 137.5 degrees, with only ±15 degrees of heading spread. Multiplayer groups rotate between living players. The director samples the chosen player's current position when the warning starts, so scheduled groups no longer use positions captured several seconds earlier.

A relative wait between starts prevents a server hitch from releasing all overdue groups simultaneously. Recently used centers remain excluded for 1.5 seconds across batches. When the preferred sector is blocked by arena geometry, the existing safe-ground fallback search can select another sector. A 100-slot refill takes approximately 5.3–10.8 seconds to start all warnings depending on packet sizes, then the last packet appears one second later; arrivals continue instead of one large burst.

The full one-second warning remains. Missing valid ground retries the group; it cannot create an unmarked fallback spawn at the arena center. If a player stands on a warning, that group retries at a new location with another full warning instead of instantly relocating. Each member's ground check also respects arena bounds. Generation cancellation, slot deduplication, the 100-slot ceiling, player minimum distance, tutorial count/no-respawn rules and explicit practice count overrides remain.

Existing movement already applies spatial-grid separation within 4.5 studs and adds that repulsion to chase steering. Movement and separation tuning were not changed: the reported issue was directly reproduced in the scheduling structure (large same-heading packets, per-flush timing and old player positions). Actual moving-crowd feel still requires Studio observation.

## Verification

`SpawnDirectorTests.py` extracts the actual Luau director and executes it with the official Luau CLI under a deterministic mocked task scheduler. Passed checks cover:

- overlapping refill batches retain the global start interval;
- moving players change subsequent spawn anchors;
- each group rotates sectors;
- a simulated scheduling hitch cannot dump all groups together;
- exactly 40 requested slots arrive once each;
- an in-flight warning cannot spawn after a generation reset;
- failed ground retries safely and eventually recovers;
- blocked warnings retry, and every eventual spawn has a complete warning interval.
- a fixed-count tutorial paused through several warning retries resumes with exactly its pending slot, without relying on normal-wave population repair.

Command: `python roguelite-planning/studio-prototype/combat/SpawnDirectorTests.py build/luau-validation/luau.exe`.

StyLua parsed the edited chase script without errors. `git diff --check` reported no whitespace errors. These checks mock Roblox geometry and do not prove actual crowd spacing, frame time or combat balance. The implementation agent ran no Studio Play test; parent integration handles source synchronization and actual runtime verification.
