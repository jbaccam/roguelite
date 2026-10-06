# Stable crowd movement — October 5, 2026

The player reported large crowds twitching left and right. `EnemySpatialGrid:steer` previously recomputed a new direction from instantaneous neighbor positions each think, with no memory. Dense neighbors repeatedly crossed their separation equilibrium, reversing the requested direction. Pursuit also switched instantly between full speed and zero at attack range, and boss sidestepping could choose the opposite side after small changes in target direction.

The grid now retains a weakly held movement state per mob. Requested direction eases over 0.24 seconds and changes by at most 3.5 direction units per elapsed second. The approach to attack range eases across the final 2.5 studs. Boss passing sides remain stable until the mob passes the boss or clears a wider lateral release band. A long pause, teleport or large target jump clears stale state. Moderate hitch integration is capped; commands remain finite, flat and bounded to unit length.

Boss-body exclusion is applied **after** smoothing, so damping cannot push a mob through the boss. Existing overlap escape, corpse filtering, body radii, population and spawn behavior remain. No physical forces, collision changes or chase-script edits were introduced.

## Verification

Expanded `CrowdSteeringTests.py` executes the actual grid with an injected deterministic clock. Passed checks cover alternating neighbor pressure, per-tick movement-change bounds, moderate hitches, pause recovery, stable boss passing sides, exact overlaps, large body footprints, corpse removal and boss exclusion. The existing **25,956** legacy grid assertions also passed.

A 60-mob kinematic convergence comparison against the immediately preceding grid source measured **7,508 → 6 direction reversals**, **16 → 10 pairs closer than two studs**, and zero mobs inside the boss footprint after the same nine simulated seconds. Reversals count consecutive nontrivial movement requests more than 90 degrees apart. These are deterministic algorithm checks, not Roblox physics or frame-rate measurements.

Commands:

```
python roguelite-planning/studio-prototype/combat/CrowdSteeringTests.py build/luau-validation/luau.exe
python roguelite-planning/studio-prototype/combat/CrowdSteeringTests.py build/luau-validation/luau.exe build/luau-validation/crowd-before-smoothing.luau
```

The second command uses the local pre-change snapshot for comparison; the first runs the permanent regression suite without it. The implementation agent ran no Studio Play test. Parent integration owns synchronization and visual/runtime confirmation.
