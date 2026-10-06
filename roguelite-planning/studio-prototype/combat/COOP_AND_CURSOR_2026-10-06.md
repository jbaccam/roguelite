# Multiplayer pressure and results cursor — October 6, 2026

Applied to Wavebreaker Studio place **107877054949326**. Seven runtime scripts changed; all **29** manifest destinations matched source afterward. The combat Rojo overlay built. Studio was returned to Edit and the temporary cursor QA module was removed. No publishing, production DataStores, rewards or real lobby teleport were used.

## Cooperative combat policy

An extra player can bring six more weapons. Ordinary arrival budgets now grow linearly with active players, without multiplying ordinary HP again. Boss HP scales linearly with run participants at encounter creation. These are analytical parity targets, not a guarantee that coordinated area damage, builds or positioning produce identical difficulty.

| Players | Potential weapon slots | Arrival budget | Boss HP versus solo | Boss-add pulse / 3 seconds | Concurrent boss adds |
| --- | --- | --- | --- | --- | --- |
| 1 | 6 | 1x | 1x | 6 | 20 |
| 2 | 12 | 2x | 2x | 12 | 40 |
| 3 | 18 | 3x | 3x | 18 | 60 |
| 4 | 24 | 4x | 4x | 24 | 80 |

At equal damage per player, `team damage / ordinary incoming HP` and `boss HP / team damage` stay approximately constant before capacity and terrain limits. Wave 1 schedules 42/84/126/168 ordinary arrivals; an ordinary late wave schedules 180/360/540/720. Boss encounters schedule 84/168/252/336 adds in their first 40 seconds before limits. This describes scheduled arrivals, not simultaneous mobs or guaranteed realized spawns.

The warning dispatcher and small-group launch cadence also scale with active players so the server does not funnel four players through a solo arrival queue. Individual marks rotate around living run members. Full spawn warnings, safe relocation, crowd smoothing, immediate ordinary death cleanup and Normal's slower movement apply across all map rosters. Dead, downed, returning and lobby players do not drive new arrival pressure. Boss HP is fixed when the encounter begins and includes downed run members who can revive; it is not healed or rescaled when someone dies.

The **100-enemy global ceiling remains**. Boss-add caps leave room for the boss; queued pressure is bounded and stale unscheduled arrivals can be discarded under persistent blockage. Terrain, warning relocation and that ceiling can reduce actual arrivals. No extra enemy damage or speed is added for teammates, and no scaling reads weapon upgrades to cancel player progression. Existing crystal ownership/sharing and emerald rewards are unchanged; boss crystals still share a fixed total among living members.

## Cursor correction

The results screen now owns a free cursor after the Roblox camera render step while visible, then releases its render callback and its own gamepad selection on hide, removal or destruction. A one-time mouse reset could previously be overwritten by first-person/shift-lock camera input after the shop closed. Shop UI also closes when run membership ends or the lobby activates, preventing stale shop state during return.

## Verification actually performed

- Source equality: **29/29** installed scripts, no mismatches; required Rojo build passed.
- Rules/scaling: **5,468 assertions**, including all five maps, three difficulties and parties of one through four; solo ordinary HP and incoming damage retained.
- Wave timeline: **14,181 assertions**, including linear party budgets, participation, capacity, queue bounds and all-map rosters.
- Extracted production SpawnDirector tests passed actual one-to-four-player normal/boss group cadence, individual root rotation and linear reservation dispatch without hitch bursts. BossPressure passed caps **20/40/60/80**, trimming and override exclusions. TimelineLifecycle passed protected capacity, pending reservations, no retirement rewards and once-only slime splitting.
- Extracted production cursor helper tests passed show/hide/reopen/reparent/destroy, render ordering and scoped selection.
- Fresh Studio Play: **five cursor lifecycle checks** against the installed production helper and **three checks on the actual mounted results UI**. A temporary camera callback forced LockCenter; visible results restored a free cursor and the lobby transition released ownership. Client-only fixture attributes were restored; no server action or teleport was invoked.
- Fresh Studio Play solo boss smoke test: Pine Valley wave 20, admin test run, God enabled, weapons disabled. Three samples over eight seconds observed ordinary counts **17, 16, 17**, one boss and timeline pulses at **9.018, 12.018, 15.017 seconds**. Hammer retained **10,800 HP / speed 24**. This checks the live solo cadence and existing balance, not multiplayer balance.
- Console inspection showed only the Studio Assistant camera-restoration diagnostic.

Not measured: a real two-to-four-client run, end-to-end boss Continue then successful lobby teleport, sustained four-player frame time, or complete-run economy/difficulty. Related detail: [health policy](MULTIPLAYER_HEALTH_2026-10-06.md) and [cursor lifecycle](../ui/RESULTS_CURSOR_2026-10-06.md).
