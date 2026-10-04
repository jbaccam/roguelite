# Hammer boss moves: progress

## 2026-10-04: sample (Idle, Walk, Slam), waiting for the user's review

- [x] Folder scaffold. `HammerBoss.blend` copied unchanged from `hammer-boss/finished/` (SHA-256 `aca526bf…157fa6`);
  the build only adds the `HB_*` actions.
- [x] Motion library (`hm_motion.py`), clips (`hm_clips.py`), checks (`hm_checks.py`), generator (`build_moves.py`).
- [x] Idle (24 fps, 3.0 s loop), Walk (24 fps, 0.667 s loop), Slam (30 fps, 1.467 s, impact 0.700 s).
- [x] All 95 checks pass (`MotionChecks.json`), including the 120 Hz client in-betweens and the 0.12 s
  Idle→Slam / Slam→Idle blends. Axis proof: Idle frame 0 = template rest within 5.1e-07 studs.
- [x] `exports/game/PartPoses.json` and `BossGameData.json`. The Studio-side `partposes_to_motor6d.convert`
  accepts them (round trip 1.1e-06).
- [x] Previews: `Idle.mp4`, `Walk.mp4`, `Slam.mp4`, `AttackCheck_Slam.png` (the PNG is local, gitignored).
- [ ] User review of the sample.
- [ ] The other 11 clips: Hit, Death, IntroLand, Roar, Swing, Spin, SwingSpin, SpinSlam, ChargeStart,
  ChargeRun and ChargeSlam (the last two record `chargeStrideLength`).

Notes for the next batch:
- Attacks that turn the hammer fast should be 30 fps, or torso-driven like the Slam's drop. The hammer's
  Motor6D pivot is its head centre, so arm-driven turns above ~15–20° per frame pull the haft off the fists
  between frames.
- Check Walk→attack blends (Walk→Slam drifts 0.124 today, see README) and add a transition if the runtime
  blends straight from the chase.
- The Slam's two wind-up keys and speed ramps came from a one-off coordinate search against the 120 Hz
  drift and the Idle→Slam blend. That search is not part of the build; the values are fixed in `SLAM_DESIGN`.
  Repeat it only where a clip needs it.
