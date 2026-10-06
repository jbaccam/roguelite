# Multiplayer arrival scaling — October 6, 2026

Each additional living run member now contributes one full solo arrival budget. This replaces the timeline's previous 1 / 1.5 / 2 / 2.5 multipliers. Ordinary enemy HP is unchanged by this patch, so early one-shot thresholds remain intact; the separate shared boss-health correction scales boss HP linearly with encounter participants.

| Living players | 1 | 2 | 3 | 4 |
| --- | ---: | ---: | ---: | ---: |
| Wave-1 authored arrivals / 40 s | 42 | 84 | 126 | 168 |
| Ordinary wave-20 arrivals / 40 s | 180 | 360 | 540 | 720 |
| Boss arrivals / 40 s | 84 | 168 | 252 | 336 |
| Concurrent ordinary boss-add cap | 20 | 40 | 60 | 80 |
| Three-slot dispatch interval | .25 s | .125 s | .0833 s | .0625 s |
| Ordinary compact-group interval | .22 s | .11 s | .0733 s | .055 s |
| Boss compact-group interval | .65 s | .325 s | .2167 s | .1625 s |

Solo boss scheduling remains **six arrivals every three seconds**, including continued pulses while the boss holds the wave open. Groups remain two to four enemies; scaling increases delivery frequency instead of making larger clumps. A hitch still cannot trigger repeated same-time dispatches or a burst of overdue pulses.

Every individual warning marker takes a turn around a living member, including secondary markers within a group. The chosen member stays its anchor during safe-location retries. Candidate points still must clear every living player and the existing ground/blocker checks, preserve ten-stud spacing, and receive the full active warning. An unsafe mark restarts a full warning at fresh safe locations.

Both population scaling and spawn origins share the eligibility rule: a living character with a root, a confirmed RunMember, neither downed nor returning. Lobby players and spectators do not increase pressure or receive combat spawn origins. Sandbox practice retains its explicit nonmember exception. No living members freezes the arrival clock. Death/revive changes the next pulse amount without replaying missed pulses; boss counts trim to the current smaller cap after a member becomes ineligible.

Pending unissued orders are bounded to 36 per living player for ordinary waves or 20 per player for boss encounters, never above 100, with already-reserved warnings deducted. Sustained capacity/placement blockage replaces stale unissued pressure with the latest authored composition instead of accumulating an unlimited backlog. Normal unblocked delivery throughput exceeds scheduled demand and the dispatcher does not intentionally discard high-kill-rate budgets. Existing warnings are not silently cancelled by this queue bound.

The global **100 living-enemy ceiling** still counts bosses, elites and admin extras; protected rigs cannot be retired. Thus late four-player waves may saturate the cap, and calculated linear arrival budgets do not prove identical four-client perceived difficulty. Ordinary stale-rig retirement remains reward-free. Per-mob rewards are unchanged.

## Verification

- **WaveTimelineTests: 14,181 assertions**, including linear one-to-four-player budgets, every-member root rotation, zero-player pause, survivor/revive pulses, member filtering and bounded prolonged backlog.
- **SpawnDirectorTests** executes extracted production queue/warning functions and the actual reservation-dispatch block. At every party size, ordinary and boss group intervals match the table, groups stay at most four, each individual mark rotates player origins, all requested 20 × N test arrivals arrive with full warnings, and reservation dispatch scales linearly without same-time catch-up.
- **BossPressureTests:** 20 / 40 / 60 / 80 limits and protected, nonreward trimming pass.
- **TimelineLifecycleTests:** cap protection, pending reservations and synchronous exactly-once splitter behavior remain passing.
- Official Luau compilation of Chase passes. No production changes were made after the parent integration freeze.

This agent did not sync or run Studio. Parent integration independently reran the director/cap/lifecycle suites and recorded the single-client Studio smoke test, source synchronization and packaging in `COOP_AND_CURSOR_2026-10-06.md`. No four-real-client intensity test is claimed.

Production files changed: `WaveTimeline.luau`, `EnemyScheduler.luau`, `RogueliteZombieChase.server.luau`.
