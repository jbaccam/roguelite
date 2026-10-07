# Power Washer trigger bursts

Power Washer (29) now uses a fixed 1.4-second trigger cycle: 0.8 seconds full pressure, 0.2 seconds tapering to drips, and 0.4 seconds refill. Attack speed scales damage, not this visible refill interval. Vacuum (28) retains its continuous cone and bounded pull.

The server evaluates shared pressure for damage. A factor of 1.4 / 0.9 compensates for the integral of the burst envelope, preserving theoretical sustained DPS rather than silently nerfing the weapon. Actual 0.12-second damage ticks approximate that integral. Streams retain their cycle start across automatic attack refreshes.

Water has no persistent beam or moving modulo-pattern. Up to 40 pooled droplets per stream are born at the current nozzle position with fixed velocity, downward acceleration of 24 studs/s� and a maximum 0.48-second lifetime. Low pressure reduces emission rate, size and launch velocity. Old droplets keep their trajectory when the player turns and disappear by age; stopping the source does not clear airborne droplets. At most 24 washer visuals are live. One wall query per active stream frame bounds emission lifetime near scenery; no per-droplet frame raycasts. StreamEnd retains the existing immediate cleanup for Vacuum.

Validation: 304 pure envelope/integral checks passed. Luau compilation passed for UtilityWeapons, UtilityVisuals, UtilityMotion and WasherBurstTests. WasherBurstTests is an isolated client fixture for full/taper/refill phases, integrated DPS, post-shutoff travel, gravity and expiry. Parent integration records whether that fixture actually ran in Studio; this implementation task did not run a Studio play test.

## Parent integration status

Seven runtime sources synchronized to roguelite Studio place 107877054949326; a second source-sync pass reported zero differences. Required combat Rojo build passed. Studio Play-start and subsequent state requests stopped responding, so client visual fixtures have not yet run. Temporary DuckBurstTests and WasherBurstTests ModuleScripts remain installed for validation; neither is in the production Rojo build. No purchase, reward, or production DataStore action was used.
