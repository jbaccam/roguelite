# Hammer boss moves: progress

## 2026-10-04: sample (Idle, Walk, Slam) for review
- Done; the user kept Idle and Walk ("fine"), rejected the new Slam ("trash"), and asked for the
  original model and attacks, a double Spin and chained attacks.

## 2026-10-09: original clips, double Spin, combos (done)
- [x] Originals baked at 60 fps exactly as BossMotion.sample showed them (constrainArms included):
  Slam, Swing, Spin, Hit, Death, ChargeStart, ChargeRun. Export vs legacy: 7.6e-07 studs (limit 1e-4).
- [x] One repair: Swing frames 3-4 (0.40) and Spin 4-5 (0.48) fist-off-haft in-betweens; other original
  gaps (up to 0.114) kept as played.
- [x] Idle frame 0 = the original carry pose (seams 3.9e-06). Walk keeps its raised carry (it can't
  ride in the carry pose), now with the carry grip and a foot-clear hammer; Walk -> attack is the
  runtime's 0.12 s blend (no contact, fists slip up to 0.37 mid-blend).
- [x] Spin = two revolutions (seam step 2.970 vs 2.971 studs/frame). SwingSpin and SpinSlam crossfades.
- [x] BossGameData with phases for Slam, Spin, SwingSpin, SpinSlam; HammerFace = legacy head point.
- [x] MotionChecks.json: 257 rows, every failure documented; partposes_to_motor6d.convert() passes.
- [ ] Previews skipped (user tests in game).
- [ ] Studio side: MapBossDefs phases (Slam 2, SpinSlam 4), rubble-wave phase behaviour, and maybe a
  tool-space or longer Walk -> attack blend (README "Walk").
