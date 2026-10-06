# Hammer pursuit correction — October 5, 2026

**Latest movement feedback:** both legacy and rebuilt walking chase now use **24 studs/s** (previous pass22). Rebuilt enrage keeps +2, giving **26 studs/s**. Legacy Hammer now holds ground and attacks when melee players close rather than continually backing away. Rebuilt already holds within its stop range. Native ordinary zombies slow to14/17/11. All charge speed/travel, attack warnings, HP and damage remain unchanged. Historical chase-cycle estimates below predate this small walking change.

Parent baseline Studio inspection found the active boss uses legacy `BossService` / `BossMotion`: `IsHammerBoss=true`, no `MapBossId`, chase speed 18, charge speed 30, against a Brawler moving at 22. This matters because editing only `MapBossDefs` would not change that boss.

## Causes and corrections

- Legacy walking speed rises **18 → 22**. Rebuilt walking rises **20 → 22**, with enrage **23 → 24**. Walking still causes zero contact damage.
- Both versions now acquire a charge target out to **110 studs**, previously 70. The old cutoff let a faster player permanently disable the gap closer just by leaving that radius.
- Legacy charge speed rises **30 → 36** and maximum travel **75 → 90**. Its 0.6 s wind-up, fixed direction, wall clamp, 9-stud hit width, contact damage, brake, knockdown and six-second cooldown remain. Stepping sideways still avoids the fixed lane.
- Legacy charge previously always forced a 1.67 s Slam even with no player in reach. A braked miss now resumes pursuit instead of striking empty ground. Reachable players still receive the warned closing slam.
- Legacy warning now shows the entire wall-clamped possible charge corridor from the start, including the swept body's end caps. It no longer grows only as the target runs away. Client animation still uses the actual replicated `BossChargeSpeed` and `BossChargeLength`.
- Rebuilt charge retains **32 speed / 75 travel**: it already turns toward its target at 40 degrees/s and finishes with a Slam that can create delayed cracks under missed players. These extra pressure mechanics justify keeping its travel less aggressive than the straight legacy charge.

## Crowd pooling audit

Source collision policy already puts tagged bosses and regular mobs in `RogueliteZombies`, whose collision against itself is disabled. Regular enemy sight and ground rays exclude `RogueliteEnemies`. No boss-specific physical crowd barrier was identified here; regular swarm steering belongs to the separate crowd correction. Boss slow already has 50% resistance and knockback 75% resistance. Neither was changed without evidence that it caused the observed stall.

Boss health is unchanged in this patch. Normal difficulty's separate shared health/damage adjustment is owned by `RunSetupRules`.

## Verification

- Source assertions passed for legacy travel bounds, empty-slam guard and full-corridor warning.
- Calculated an unobstructed full six-second charge cycle (including warning/brake and remaining chase time): closes **15.2 studs** against a constant 22-speed player and **3.2 studs** against a constant 24-speed player. This is an ideal movement check, not a measured Studio chase result; walls and sidesteps can prevent closure.
- Added a `MapBossServiceTests` check for rebuilt pursuit values while preserving bounded charge travel.
- `git diff --check` passed (line-ending notices only).
- This agent ran no Studio Play tests. Parent owns sync and live validation, including distant charge acquisition, warning coverage, miss recovery and damage dodgeability.

Production files: `hammer-boss/BossMotion.luau`, `hammer-boss/BossPresentation.client.luau`, `combat/bosses/BossService.luau`, `combat/bosses/MapBossDefs.luau`. No `MapBossService` runtime edit.
