# Reachable boss targeting for melee — October 5, 2026

Ready melee weapons now prefer a reachable boss over nearer ordinary mobs. Dense adds previously won the nearest-target comparison every swing, so pans could keep aiming away from the boss even when standing beside it.

`RogueliteCombat.server` opts into the new optional `TargetGrid.nearest` boss priority only when the weapon is melee and its attack cooldown has expired. Cooling weapons and ranged weapons keep their existing target policy. Among eligible bosses, the nearest measured surface wins, with existing stable tag-order ties.

Eligibility does not change: targetability, living target checks, actual boss shell measurement (excluding Hammer's held weapon), existing range and vertical allowance, and unobstructed wall sight must all pass. An out-of-range, blocked, dead or disallowed boss falls back to an ordinary enemy. Weapon reach, hit volumes, swing collision, damage and server validation remain unchanged.

Added TargetGridTests regression checks for boss-over-add selection, nearest eligible boss, unchanged nonpriority selection, blocked/dead/disallowed fallback, exclusive range boundary and vertical allowance. Existing randomized nearest-target regressions still exercise the default path. `git diff --check` passed (line-ending notices only). This agent ran no Studio tests; parent integration owns fresh-module test execution and actual six-pan boss/add Play validation.

Production sync: `TargetGrid` and `RogueliteCombat` server script. No boss-service or movement edits in this targeting change.
