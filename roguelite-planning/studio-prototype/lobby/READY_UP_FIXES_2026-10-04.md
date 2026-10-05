Integration: synced to Studio; 37 queue and 17 validation checks passed. See [final integration report](../combat/BUGFIX_REPORT_2026-10-04.md) for Play coverage and limits.

# Party readiness and saved starters — October 4, 2026

The host selects a map, difficulty, class and starting weapon and presses **READY UP**. Every other queued player receives class selection for that map and must press **READY UP** themselves. An unready player holds the queue indefinitely. Full/private groups count down for three seconds after the last confirmation; partially filled open portals count down for ten seconds. Joining, pressing **UNREADY**, or changing a loadout cancels the countdown. Re-readying starts a fresh countdown.

The portal HUD lists each queued player's display name with their server-confirmed ready state. The class screen shows the ready count. The host cannot choose a map/difficulty any member of the queued group or party has not unlocked, cannot silently omit a party member on another portal or away from the lobby, and cannot launch a partial group after final validation fails. Map and owned class/weapon checks run again at launch and on the match server. Queued players must unready before changing armor or pets.

Starting weapon fixes: tapping the already-selected class no longer clears its starter; switching between classes remembers the choices browsed in this screen. Confirmed class/weapon preferences are published by the server and stored only after a real profile has loaded. A rejected/loading choice stays visible instead of closing as though it saved. Match arrival no longer silently substitutes the Frying Pan if the save failed to load. Studio profiles always stay in memory, including places with the obsolete `EnableStudioDataStores` attribute set.

Final review follow-up: an already-open setup refreshes after the deferred profile attribute batch, so loading completion updates owned choices and enables READY/CONFIRM without closing and reopening the screen. This follow-up was source-checked; its Studio sync and Play coverage are recorded in the integration report.

Source validation during implementation: StyLua parsed the changed modules successfully (existing compact formatting is retained; its formatting check reports style differences). `git diff --check` passed. `QueueStateTests.run(QueueState)` contains 37 deterministic readiness checks; `RunSetupValidationTests.run(RunSetupRules)` contains 17 profile validation checks. Studio execution and actual Play results belong in the parent integration report; no Studio Play test was run by this subagent.

Related combat tuning: `RunSetupRules.BossPlayerHp` is 1.35 extra health per additional player (four players: ×5.05, before map/difficulty scaling).
