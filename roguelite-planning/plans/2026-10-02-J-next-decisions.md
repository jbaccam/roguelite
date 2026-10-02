# Plan J: the user's answers after plan I (handoff, 2026-10-02)

The previous chat built and synced plan I (results screen, Leave Run, spectating, last stand, starter tiers in runs, Gear Power, analytics). See [plan I](2026-10-02-I-run-end-gear-power-analytics.md), [GEAR_POWER.md](../GEAR_POWER.md), [PLAYTEST_ANALYTICS.md](../PLAYTEST_ANALYTICS.md) and [LOBBY_AND_MATCH_SERVERS.md](../LOBBY_AND_MATCH_SERVERS.md) "Plan B built". It then asked the user some questions; their answers are below. Build these next.

Ground rules (also in memory): repo first, then ask "push it to Studio?" before any Studio write; no Play sessions without asking; other Claude sessions edit the same files, so make anchored edits and commit HEAD + your own hunks only; new ModuleScripts need the right Sandboxed setting for whatever requires them; commit often to main and push to `origin`.

## Answers to build

| # | Question | User's answer | What to do |
|---|---|---|---|
| 6 | Revive prices that double (65 → 130 → 260 R$) and more than one revive per run | Listed with no comment | Build it per LOBBY_AND_MATCH_SERVERS.md §4: products Revive1…Revive5 (65/130/260/520/1040 R$), count resets each run, drop `ReviveLimitPerRun`. Product IDs stay 0 until the user creates them (Studio simulates). Confirm in one line if unsure. |
| 7 | Missing analytics: damage by weapon, shop buys and rerolls, passive picks, frame rate | Listed with no comment | Add to `combat/RunAnalytics.luau` (custom events, ≤3 fields, keep combinations low). Shop events come from ShopService, which is sandboxed and can't require RunAnalytics: pass them through an unsandboxed hook or a BindableEvent. |
| 8 | Rarity step 2 (RARITY_GODLY_ARMOR.md §4–7) | "Do Brotato-style tiers. Rarer weapons rarer in the shop, sure, since we have an even amount of weapons across rarities, but don't make it too rare, and it should depend on wave and luck too. For rarity power, why can't we just put it in the base stats instead of a multiplier? Tier IV bonus: later." | (a) Tiers: damage ×1.4 per tier, cooldowns {1, .9, .8, .7}; Boxing Gloves keep theirs. (b) Shop: rarity-weighted offers, gentler than the §5 table (e.g. Legendary not ¼), scaling up with wave and Luck. (c) Rarity power goes into each weapon's own base damage in WeaponCatalog (Rare +5%, Epic +10%, Legendary +20%), not a multiplier in `CharacterStats.weapon()`. It's the same effect and shows in the weapon's stats. (d) Skip the Tier IV bumps (§7) for now. Update WeaponBalanceTests, ShopTests and WEAPON_BALANCE.md. |
| — | Rarity step 3, Legendary extra moves (§8) | "Do this on Tier IV Legendary weapons." | A Legendary gets its move only at Tier IV: Katana every 3rd swing throws a flying slash; Rocket Launcher every 4th rocket splits into 3; Deck of Cards every 5th throw is a Royal Flush of 5 piercing gold cards; Bowling Ball 5+ enemies in one roll = STRIKE! with a pin explosion; Wrecking Ball heavy hits send a shockwave ring; Excalibur swings shoot golden beam slashes; Mjolnir every 4th throw calls a lightning strike. Server owns every hit; visuals client-only; gold aura. One at a time. |
| 9 | Play Again with the same party, and rejoining a match after disconnecting | Listed with no comment | Build per LOBBY_AND_MATCH_SERVERS.md (both were "out of scope" there). Play Again: a button on the results screen that sends the same party into a new match. Rejoin: a player who disconnects mid-run can get back into that match server while it runs. |
| 10 | Do the Power numbers feel right (+12% damage, +6% health per point, +4 per map)? | "Do our players have a power number that shows how strong they are?" | Yes: Gear Power shows on the Armory's POWER plate, on map select ("Your power n · recommended m") and in the in-run Stats tab. Numbers stay as they are until play-test data says otherwise. |
| 11 | Is 10 s too short for a solo kid to decide on a revive? | "Fine if there's a timer or indicator showing the countdown; if not, give me 20 seconds." | The death screen shows "REVIVE OR THE RUN ENDS · n", but not during the 2.3 s YOU DIED splash. Show the countdown from the first moment (on the splash too). If it can't be visible the whole time, set `LAST_STAND` in RogueliteMeta to 20. |
| 12 | The Highest Wave leaderboard counts any map. One per map? | "Have the leaderboard cycle through all maps, and have one for total too. Same with top kills." | `combat/LeaderboardService.server.luau`: Highest Wave and Kills each per map plus a Total, and the lobby boards cycle through them (Total, Pine Valley … Volcanic Crater). Per-map stats need new saved fields and OrderedDataStores; keep the existing totals. Time Played stays one board. |

## Noted, no change now

- **Emeralds per run are low** (user, 2026-10-02): a Pine Valley win pays 80 (+100 the first time), half a Silver Chest. Keep the run payouts as they are; quests, dailies and other sources should make up the pace. Revisit with play-test data: the analytics economy source `RunWaves` against the other sources.
- **Gear Power only recommends** a map; it never locks one. Unlocks stay win-based (Normal win opens Hard, Hard win opens Nightmare and the next map).

## Still open from the first playtest list (not answered here)

- Push to Studio: done for plan I. Run the plan I play-test checklist.
- Published-game test with 2 accounts: teleports, saving between servers, spectating, group return (LOBBY_AND_MATCH_SERVERS.md §7).
- Robux product IDs are all 0 (MonetizationConfig): create them in the Creator Dashboard or hide the store before outside testers.
- No tutorial.
- Phone check of the run HUD, shop, death and results screens (`UILayoutAudit.sweep`).
