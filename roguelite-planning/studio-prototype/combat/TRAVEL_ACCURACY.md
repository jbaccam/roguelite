# Projectile accuracy, close melee and utility streams

## Behavior

- ProjectileTarget now solves an intercept from the launch position, target velocity, actual flight-duration function and launch delay. It accounts for Pandora's opening delay and staggered throws, clamps implausible velocity/lead time, stops predicting through walls, and limits a pursuer's forecast at its stopping distance. Molotov/Pandora forecasts are projected to ground. Normal gun/rocket launches and replacement/bounce targeting use leading too; cards retain their existing curved tracking.
- Eggs and modeled throws use their own flight timing rather than a single generic lead constant. An abrupt turn after release can still dodge a committed throw; this is prediction, not guaranteed homing.
- Close melee pulls the weapon's arc inward using the target distance and physical weapon length. Blunt weapons select a compact horizontal stroke within three horizontal studs; attack height continues to align to the enemy, including babies and attacks while jumping. Shared server/client motion supplies the rendered pose and damage bounds.
- Gloves: base cooldown 0.62 -> 0.42 seconds; base animation rate 2.1 -> 2.7. Alternating hands and the existing stat/tier modifiers remain.
- Cards: flight timing approximately 11-12.5% longer. Fart gun projectile speed: 150 studs/second before modifiers; its lingering poison zone remains.
- Bowling ball: three native extra pierces at tier one (four at tiers three/four, total capped at four), with existing 70% successive-hit damage. It continues down the lane instead of ending at the first enemy, and prioritizes piercing before a bounce. Each enemy is hit at most once per ball.
- Vacuum: a widening triangular cone gathers enemies toward a point seven studs from the avatar (or farther for a larger contact radius). Pull speed is capped at 12; slow is 35%. A hold lasts at most 0.85 seconds, followed by 2.4 seconds of pull immunity shared across all vacuums/players. The force stops at the safe distance; enemies can then approach normally. Bosses resist the pull. Damage continues in the cone but ticks cannot recursively trigger statuses, knockback or chains.
- Power washer: a continuous blue/white water jet with moving droplets, with narrow stream damage. Both utility streams stop at walls, validate the owner/equipped slot/liveness, expire after firing stops and use server damage checks. The client only draws the flow. Utility damage per second follows each weapon's damage/cooldown rather than increasing with visual refresh rate.

## Verification

- Reviewed twelve sampled frames across the user's 22.23-second video.
- TravelAccuracyTests: 169 checks passed (intercept consistency, stationary/retreating pursuit stop, small close targets at multiple headings, cone geometry, safe pull distance, tuning). SpringComboTests: 15,069; WeaponBehaviorTests: 19,905; MeleeMotionTests: 20,024; WeaponFollowTests: 834 passed.
- Moving target/player test at 8 studs/second: eggs had six damage events in seven launches in a six-second window (last flight still pending); Molotov four launches/nine damage events including lingering fire; Pandora three launches/three damage events. A separate egg zigzag test hit five of eight throws; sudden reversals after launch can still evade a prediction.
- Bowling ball: all three aligned practice targets were hit twice during the test window. Bat: three hits on an actual baby-zombie template at 2.1 horizontal studs and a lower height.
- Vacuum: all three moving test enemies received damage and acquired release immunity; they subsequently reached 1.61-3.28 studs from the player under their own chase movement. Client vacuum-cone visuals were present. This verifies the vacuum does not permanently hold enemies outside contact range.
- Water: eight damage ticks in 1.3 seconds; three visible beams and sixteen droplets. A test wall stopped damage (practice counter stayed 144), and unequipping removed the stream. Viewport screenshot inspected: the jet leaves the washer nozzle and reaches the target.
- Gloves: five observed launches alternated left/right at rate 2.7, with four contacts in the 2.2-second sample. Actual cadence was about 0.45 seconds at the server's update frequency. Fart-gun flights at twenty studs took 0.16 seconds; cards took 0.54 seconds (previous minimum 0.48).
- Initial new-module sandbox mismatch was corrected by matching the existing modules' Studio sandbox/capability settings. Unrelated Roblox CoreGui timeouts and the pre-existing CardShowcase missing-part warning appeared during startup; they are not claimed as fixed here.
- Final test session had no combat errors (only the tool's camera-reset notice). Both Rojo packages built successfully. Final edited source modules were compared to Studio Edit. Temporary play sessions and test fixtures were stopped/removed.

No multiple-real-client, high-latency or prolonged performance tests were run. Practice targets did not award persistent currency or wins. Temporary runtime fixtures are discarded on stopping Play. Pre-change Studio sources are backed up in ServerStorage.BeforeTravelAccuracy_20260923.
