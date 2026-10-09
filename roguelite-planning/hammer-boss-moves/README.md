# Hammer boss moves

The ORIGINAL Hammer boss model (`hammer-boss/finished`, the 16-part Motor6D template `HammerBoss_NPC`) with
his ORIGINAL attacks, baked for the map-boss runtime. Everything is authored at template scale 1.0; the
game scales him by 1.5.

**Status (2026-10-09): done.** User decisions (2026-10-04 review): keep the original model and attacks,
keep the new Idle and Walk ("fine"), drop the new Slam ("trash"), spin twice, chain attacks.

## Clips (`exports/game/PartPoses.json`)

| Clip | fps | Length | What |
| --- | --- | --- | --- |
| Idle | 24 | 3.0 s loop | The 2026-10-04 Idle (breathing, weight shift) holding the hammer in the original carry pose. Frame 0 IS the carry pose. |
| Walk | 24 | 0.667 s loop | The 2026-10-04 chase run. The fists now hold the haft in the carry grip; the hammer is carried 0.4 studs further out to his right with the head tipped up 6 deg (see Walk below). |
| Slam | 60 | 1.667 s | Original. Impact 23/30 s. |
| Swing | 60 | 1.8 s | Original. Active 19/30 to 25/30 s. |
| Spin | 60 | 2.283 s | Original wind-up, the original revolution twice, original recovery. Revolutions 21/36 to 37/36 and 37/36 to 53/36 s. |
| SwingSpin | 60 | 3.333 s | Swing, then the double Spin. |
| SpinSlam | 60 | 3.15 s | Double Spin, then the Slam (impact 2.25 s). |
| Hit, Death, ChargeStart, ChargeRun | 60 | 0.6 / 2.8 / 0.6 / 0.533 s | Original. ChargeRun loops. |

No IntroLand, Roar or ChargeSlam: the sky-drop lands on the Slam and the charge ends on the Slam.
Spin and SwingSpin end with 1/180 s held on the last pose (60 fps frame rounding).

### How the originals are baked (`hm_legacy.py`)

`Legacy` is a line-by-line port of `hammer-boss/BossMotion.luau` (`M.sample`, `M.blend`,
`M.constrainArms`, including the Death per-part lerp and the Swing/Spin head lift, which is zero in
this data). The bake samples it every 1/60 s, so each frame is what the legacy client showed at that
time.

Proof (`MotionChecks.json`):
- `legacyBake`: the exported PartPoses numbers against `BossMotion.sample` at the same time, as part
  CFrames (delta x BossRest from the template receipt), on each part's box corners: **7.6e-07 studs** on
  the 274 frames that land on original frames and on the 341 in-betweens (limit 1e-4). Excluded: the
  3 repaired frames below and the 6 frames of the Spin's seam fade.
- `portCrossCheck`: the port against `hammer-boss/charge_runtime.py` (an older, independent mathutils
  port): frame blend within 2.7e-04 and after constrainArms within 1.9e-03. mathutils is float32, and
  the nearly straight left arm amplifies that rounding at the elbow.
- `axisProof`: the template rest through the Blender to Studio mapping vs the installed template:
  4.8e-07 studs.

**One repair.** Between two original frames, BossMotion.blend lerps each fist in hammer space as a
root-space delta. If a fist rolls far on the haft in one source frame, the fist's hole cuts a chord off
the haft. Two places go past the 0.15 studs the user accepts: Swing frames 3 to 4 (0.40) and Spin frames
4 to 5 (0.48). That is the "grip slip at 0.125 s": the right fist rolls about 68 deg in one source
frame at the start of the wind-up. Inside those two intervals only, the fist slides and rolls along the
haft instead, then constrainArms solves the arms. Original frames never change.

**Gaps kept as the user played them** (accepted up to 0.15): the other in-betweens reach 0.114
(Swing 11 to 12), 0.100 (Spin 16 to 17) and 0.079 (Slam 3 to 4). The game's own 120 Hz in-betweens
between the 60 fps frames reach 0.123 except in the slam drop: the hammer turns about 75 deg in 1/60 s
there, so halfway between two exact frames the fists sit 0.215 off the haft for 1/120 s (Slam 0.69 s,
SpinSlam 2.18 s). That is over 0.15. It is at full swing speed, so I left it; 120 fps for that one drop
would fix it.

### The carry pose and the Idle/attack seams

Every original attack starts and ends on the carry pose (legacy Idle frame 0): the hammer 1.4 studs
further forward than the template rest. The new Idle now starts on it exactly, so Idle to attack and
attack to Idle are seamless.

| Seam | Measured (mesh points) |
| --- | --- |
| Idle frame 0 vs Slam, Swing, Spin, SwingSpin, SpinSlam frame 0 | 3.9e-06 studs |
| Their last frame vs Idle frame 0 | 3.9e-06 studs |
| Idle frame 0 vs ChargeStart, Hit frame 0 | 0 |

The Idle keeps its motion; only the hammer hold changed. The fists stay in the carry grip on the haft
(exact on every frame), the arms use BossMotion.constrainArms like the attacks, and the knees bend about
the carry's own knee axes. The right fist slides up to 0.15 studs along the haft as he sinks, which
keeps the forearm cuff out of the hammer head.

### Walk

The run can't hold the hammer in the carry pose. He leans 19 deg forward and lifts his knees, so the
carried head would go 1.6 studs into the ground and the right foot through it. So the Walk keeps its
approved raised carry, which is about 3 studs from the carry pose in chest space. Walk to attack is
therefore not a 0.01 seam. It is the game's 0.12 s blend from the held run pose.

Two fixes for that blend:
- **Foot through the hammer (README 2026-10-04 note):** the hammer rides 0.4 studs further out to his
  right with the head tipped up 6 deg. The right foot now clears it by 0.44 in the run and by at least
  0.19 through every Walk to attack blend (16 run phases x every attack). The BVH test finds no foot or
  leg contact.
- **Fists slipping on the haft mid-blend:** the run's fists now use the carry grip, the same as the
  attacks. The worst in-blend slip falls from 0.66 to 0.37 studs (Walk to Slam).

The rest is the runtime. MapBossPresentation blends each joint on its own, so the hammer (a root joint)
and the fists (the arm chain) part for about 0.05 s. A tool-space blend like BossMotion.blend would
remove it. So would a 0.2 s blend into attacks from the Walk.

The cost: the left wrist bends 48 deg in the run (the carry pose itself bends 44).

### Double Spin

The original revolution turns at a constant 810 deg/s and covers exactly 360 deg in 16/36 s. Revolution
2 replays it. After 360 deg the pose is 0.17 studs from where the revolution started, so revolution 2
starts exactly on revolution 1's last pose and fades that small residual out over 0.1 s. The fastest
point moves 2.970 studs per 1/60 s at the seam vs 2.971 inside revolution 1, with the same
acceleration (0.706 vs 0.703), so there's no hitch.

### Combos

A plays to its cut, then over 0.2 s each part crossfades from A (still playing) into B (from its cut):
- the torso, head and arms lerp each joint's local transform (slerp rotation, lerp position);
- the legs lerp each part in root space, like BossMotion.blend, so the feet stay planted;
- the hammer lerps in chest space about the grip (BossMotion.blend);
- the fists slide and roll along the haft;
- then constrainArms solves the arms.

| Combo | A cut | B cut | Fade | Shift | Hammer head nearest the carry spot | Fastest point in the fade |
| --- | --- | --- | --- | --- | --- | --- |
| SwingSpin | Swing 1.300 s (recovery) | Spin 0.250 s (wind-up) | 0.2 s | +1.050 s | 7.7 studs | 2.71 studs/frame (Spin's own: 2.97) |
| SpinSlam | double Spin 1.600 s (after revolution 2) | Slam 0.117 s (wind-up) | 0.2 s | +1.483 s | 5.3 studs | 3.13 studs/frame (Slam drop: 2.99) |

The cuts came from a search over A's recovery and B's wind-up for the smallest pose difference. Two
limits applied: the hammer head stays at least 3 studs from its carry spot, so the combo never passes
through idle, and the crossfade is no faster than the attacks' own sweeps. In SwingSpin the hammer comes
back across the front and up into the spin's wind-up. In SpinSlam the spin's recovery flows into the
slam's lift. During the SwingSpin fade the right shin's back edge dips 0.08 into the ground for a few
frames. The feet stay on the ground.

## Timing (`exports/game/BossGameData.json`)

Every warning starts at commit (warnStart 0). Multi-hit attacks list their hits in `phases`, in order.
The top-level impact is the first phase's impact and activeEnd is the last phase's activeEnd.

| Attack | Phases (impact to activeEnd, seconds) |
| --- | --- |
| Slam | slam circle 0.767 to 0.767; rubble wave 0.767 to 0.767 |
| Swing | single hit 0.633 to 0.833 |
| Spin | spin 1 0.583 to 1.028; spin 2 1.028 to 1.472 |
| SwingSpin | swing 0.633 to 0.833; spin 1 1.633 to 2.078; spin 2 2.078 to 2.522 |
| SpinSlam | spin 1 0.583 to 1.028; spin 2 1.028 to 1.472; slam circle 2.250; rubble wave 2.250 |

**Points:**
- `HammerFace` is the legacy head point (BossMotion.head, `hammerHeadRest`: the head centre). It is
  stored as `{"bone":"Hammer","offset":[3.21533, 0, 0.05625]}` in the Hammer part's Studio space.
- `HammerGrip` is the haft axis midway between the carry grips: `[-2.03165, 1.21136, 0.05625]`.
- Each attack and phase gives `rootAtImpactStudio` at its own impact, y up from the soles. Example:
  the Slam's head lands at [-0.758, 2.215, -11.405].

**Body:** rootHeight 4.45, height 11.922, footprintRadius 5.184 (body sections only).

**Motion:** strideLength 11.594, nominalSpeed 17.391 (Walk), chargeStrideLength 8.533. The ChargeRun's
planted feet move back at 16 studs per clip second, which matches the legacy chargeSpeed.

All values are at scale 1.0.

## Checks (`MotionChecks.json`)

Every clip was checked on its frames and on the game's 120 Hz in-betweens (per-joint lerp). Every seam
was checked too: Idle/attack junctions, the Spin's revolution seam, the combo fades, and the runtime's
held-pose blends. Those blends are Idle (12 phases) and Walk (16 phases) into every attack and
ChargeStart, and every attack back to Idle. Hammer vs body is an exact mesh BVH test.

The summary has 257 rows. 133 pass; the other 124 fail with a written reason (`exception`), and none fail
without one. Most failures are the originals measured against this folder's strict comfort limits: the
same value is in BossMotion.sample's own output for that clip. Examples are knee off-axis up to 47 deg,
wrist twist near 180 deg, original joint gaps up to 0.29 (Swing's hip in its recovery), the Swing/Spin
wind-up's forearm cuff in the hammer head, and Death's hammer through the body.

`*` = fails with a documented exception, `-` = not applicable.

| Check | Idle | Walk | Slam | Swing | Spin | SwingSpin | SpinSlam | Hit | Death | ChargeStart | ChargeRun |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Grip, frames (≤ 0.05) | 0 | 0 | 0.079* | 0.114* | 0.064* | 0.114* | 0.073* | 0.004 | - | 0.029 | 0.000 |
| Grip, 120 Hz (≤ 0.08) | 0.001 | 0.004 | 0.215* | 0.114* | 0.123* | 0.114* | 0.215* | 0.004 | - | 0.029 | 0.001 |
| Hammer vs body, 120 Hz samples (0) | 0 | 0 | 0 | 9* | 10* | 9* | 10* | 0 | 328* | 0 | 0 |
| Elbow off-axis (≤ 2 deg) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Knee off-axis (≤ 2 deg) | 2.8* | 0 | 10.3* | 12.2* | 29.2* | 22.9* | 29.2* | 2.8* | 29.2* | 47.2* | 22.8* |
| Elbow flex (12 to 130 deg) | 12.0 to 42.3 | 65.8 to 84.6 | 12.1 to 44.3 | 12 to 84.0 | 12 to 86.5 | 12 to 85.3 | 12.0 to 86.5 | 12.1 to 36.0 | 12.1 to 60.7 | 12.1 to 130.0 | 15.8 to 129.5 |
| Lowest point (≥ -0.05) | 0 | -0.017 | -0.059* | 0 | -0.028 | -0.082* | -0.059* | 0 | -1.435* | -0.228* | -0.210* |
| Joint gap (≤ 1e-4) | 0 | 0 | 0.025* | 0.295* | 0.039* | 0.414* | 0.039* | 0.0001 | 0.010* | 0.075* | 0.066* |
| Loop closes | 0 | 0 | - | - | - | - | - | - | - | - | 0 |
| Planted-foot drift (≤ 0.01) | 0 | 0 | - | - | - | - | - | - | - | - | - |

| Seam / blend | Result |
| --- | --- |
| Idle frame 0 = attack first/last frame | 3.9e-06 studs |
| Spin revolution 1 to 2 | step 2.970 vs 2.971 studs/frame, 0.17 residual faded over 0.1 s |
| SwingSpin / SpinSlam fade | grip 0.064 (Spin's own in-between at the fade end) / 0.004; no BVH contact; head 7.7 / 5.3 studs from the carry spot |
| Attack to Idle (0.16 s) | grip 0.0001, no contact |
| Idle to attack (0.12 s) | grip 0.082 to 0.124 (0.25 into ChargeStart); contact is only the Swing/Spin wind-up's own forearm cuff (0.30 vs 0.275 alone; ChargeStart 0.18 vs 0.13) |
| Walk to attack (0.12 s) | no foot or leg contact; grip 0.27 to 0.37 (runtime per-joint blend, see Walk) |

`MotionChecks.json` also has: every row with where it happens, the legacy reference values, the
seam details, and `studioConvert`, which is `partposes_to_motor6d.convert()` run on this output with
the real receipt. It writes nothing. Results: 11 clips, 1105 frames, 16 joints, round trip 1.4e-06
studs (limit 1e-4), passed.

## Previews

None this round (user, 2026-10-09: skip renders, he tests in game). The old `Idle.mp4`, `Walk.mp4` and
`Slam.mp4` showed the previous carry and the rejected new Slam, so they were removed. `build_moves.py
-- render` still holds an untested preview stage (Slam, Spin, SwingSpin and SpinSlam with the game's
blends, plus a rubble-wave mock: 9 faceted dirt and rock bursts racing 26 studs ahead of the slam,
knee height to 1.5x his height); it was stopped before it finished and has never produced a video.

## Files and running

| File | What |
| --- | --- |
| `build_moves.py` | The generator (Blender 5.2, headless). Clips, timing, proofs, checks (with the BVH test), exports, `HB_<clip>` actions in `HammerBoss.blend`, previews. |
| `hm_legacy.py` | BossMotion port, the 60 fps baker with the one repair, the crossfade, `DoubleSpin` and `Combo`. |
| `hm_clips.py` | Idle and Walk on the carry pose (`Carry`). |
| `hm_motion.py`, `hm_checks.py` | Rig maths and the checks (unchanged). |

`"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python build_moves.py -- data`
builds the clips, checks, exports and actions in about 5 minutes. `-- render` is the untested preview stage.
