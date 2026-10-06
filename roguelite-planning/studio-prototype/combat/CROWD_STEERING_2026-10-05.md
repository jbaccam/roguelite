# Boss crowd separation — October 5, 2026

The follow-up report described regular enemies pooling inside/around the Hammer boss even after arrival distribution changed. Code inspection found four concrete causes: mob-to-mob collision is deliberately disabled, sight rays ignore the entire enemy folder, the old separation considers every mob (including bosses) a point inside a fixed 4.5-stud radius, and exactly overlapping centers contribute no repulsion. Normalizing the final steering vector also turns nearly cancelled directions into full-strength movement. Path waypoint following bypassed separation entirely.

`EnemySpatialGrid:steer` now uses regular-mob body radii and boss torso/root footprint estimates. Regular mobs begin steering around a boss before reaching its body. Inside its protected footprint they escape outward; ordinary crowd pressure cannot override that boundary and push them inward again. Exact overlaps use stable opposite escape directions. Body-aware regular separation keeps more room between neighboring mobs. Clear-path and waypoint movement both use the same steering, bounded to a unit movement request without normalizing tiny directions into full-strength commands. Boss damage/health/motion and spawn distribution are unchanged.

`RogueliteZombieChase` sets the regular `CrowdRadius` from its authoritative navigation radius (with split-child scaling), and calls the new steering. `EnemySpatialGrid` is now included in the combat Rojo project; the pre-existing Chase dependency was absent from that overlay declaration.

## Verification

Official Luau CLI, `CrowdSteeringTests.py`:

- Geometry-aware avoidance starts before contacting a legacy Hammer-sized torso; a mob inside its footprint escapes outward.
- Two mobs at exactly equal centers receive stable, opposite escape directions.
- Legacy large mobs use their own cached geometry footprint even without an explicit `CrowdRadius`; defeated cosmetic bodies are ignored both during rebuild and by already-cached steering queries.
- A deterministic 60-mob kinematic convergence test uses the actual old separation and new steering code: ordinary mobs inside the boss footprint decrease **8 → 0**, pairs closer than two studs decrease **28 → 16** after nine simulated seconds.
- All **25,956** existing `EnemySpatialGridTests` assertions passed; its legacy separation API remains compatible.
- Existing extracted spawn-director regressions passed, including paused tutorial recovery.
- Both edited runtime Luau files compiled with the official Luau compiler; whitespace checks passed.

The test models movement kinematically and does not simulate Roblox Humanoid physics, animation or network presentation. Parent integration recorded a pre-change single-client stationary-player baseline of 100 ordinary mobs, 83 pairs closer than two studs, and 18 ordinary mobs within eight studs of the boss. Those measurements are a different setup from the kinematic test and must not be compared as before/after results. The implementation agent ran no Studio Play test; parent integration owns live synchronization and controlled post-change verification.
