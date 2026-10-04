# Hammer boss moves

New moves for the ORIGINAL Hammer boss model (`hammer-boss/finished`): the 16-section Motor6D template
`HammerBoss_NPC`, with its mesh, textures and size unchanged. Only the motion is re-authored. It follows
`plans/2026-10-03-hammer-brute-rebuild-design.md` §3, §7 and "Change of plan (user, 2026-10-04)".

**Status: sample for review.** Idle, Walk and Slam are done and every check passes. The other 11 clips
(Hit, Death, IntroLand, Roar, Swing, Spin, SwingSpin, SpinSlam, ChargeStart, ChargeRun, ChargeSlam) wait
for the user's review of this sample.

## Files

| File | What |
| --- | --- |
| `HammerBoss.blend` | A copy of `hammer-boss/finished/HammerBoss.blend`. The build adds the actions `HB_Idle`, `HB_Walk` and `HB_Slam`; the old `Boss_*` actions are untouched. |
| `build_moves.py` | The generator (Blender 5.2, headless). Reads the model, builds the clips, runs the checks (with an exact mesh-against-mesh BVH test), writes the exports, keys the actions and renders the previews. |
| `hm_motion.py` | Pure numpy: rotations, Roblox `CFrame:Lerp`, keyed curves (Hermite, strike and hold segments, trapezoid path timing), the rig, the knee and elbow hinge IK, the two-hand haft constraint, whole-clip arm planning, and the client's per-joint lerp. |
| `hm_clips.py` | Pure numpy: `idle()`, `walk()` and `slam()`. Each design is a data table at the top of its section. |
| `hm_checks.py` | Pure numpy: every check, on authored frames, the client's 120 Hz in-betweens and the 0.12 s blends. |
| `exports/game/PartPoses.json` | The hand-off: each part's CFrame relative to HumanoidRootPart per frame (Studio axes, template scale 1.0, 12 numbers to 7 places). It also holds `motion` and `rootHeight`. |
| `exports/game/BossGameData.json` | Slam timings and points (`HammerFace`, `HammerGrip`), plus `rootHeight`, `height`, `footprintRadius` and `groundOffset`. |
| `MotionChecks.json` | Every check result: a summary table, worst values with the frame or sample they occur at, the axis proof and the definitions. |
| `previews/Idle.mp4`, `Walk.mp4`, `Slam.mp4` | Eevee renders with the real textures at 1280×720: normal speed, then half speed. The poses are the client's own in-betweens. |
| `previews/AttackCheck_Slam.png` | Wind-up top, mid-drop, impact and recovery: front ¾ plus a fist-on-haft close-up. It stays local (`previews/**/*.png` is gitignored). |

Run it with `"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python build_moves.py`.
Add `-- data` to skip the renders. A full run takes about 10 minutes.

## The clips

| Clip | fps | Frames | Length | Notes |
| --- | --- | --- | --- | --- |
| Idle | 24 | 73 | 3.0 s, loop | Frame 0 is the template rest pose exactly: the shared start pose. He breathes heavily twice per loop with a quick inhale and a slow exhale, and slowly sinks onto his left leg and back. The head and the hammer trail the body a beat late. |
| Walk | 24 | 17 | 0.667 s cycle, loop | A lumbering, stomping chase run. `strideLength` 11.594 and `nominalSpeed` 17.391 studs/s at template scale, so 20 studs/s at scale 1.15 plays at 1×. Each foot is planted 34% of the cycle, lands flat and rolls up onto its toe edge. The pelvis bobs and sways and the shoulders counter-rotate. The hammer is carried low across the front and bounces a beat after the body. |
| Slam | **30** | 45 | 1.467 s | Starts and ends exactly on Idle frame 0. The head of the hammer swings up from his right side while the right hand slides down the haft (2.72 → 6.55). He crouches as the hammer rises. There is a 3-frame hold (0.40–0.50 s) with the hammer straight up, then a 6-frame eased drop. The **lower striking face lands flat on z = 0 at 0.700 s**, 10.8 studs in front. His body compresses, the hammer bounces 0.28 studs and settles, then he recovers with overlap: the hammer lifts first, the torso follows, the head trails last. |

**Why the Slam is 30 fps.** At 24 fps the in-between grip check failed. The wind-up turns the hammer about
125–140° in 0.42 s, which is 14–26° per frame. The client lerps the `Hammer` joint about its own pivot, the
head centre on the HumanoidRootPart, while the fists follow the arm chain. So mid-frame the haft left the fists
by 0.14–0.22 studs; the limit is 0.08. Meeting it at 24 fps needed a near-constant-speed wind-up, which looked
robotic. At 30 fps the impact also lands on a whole frame (frame 21 = 0.700 s).

Three things keep the Slam inside the in-between limits:
- **The drop is torso-driven.** The arms reach their impact pose in chest space one frame early. For the last
  frames the torso whips about 70° forward and carries hands and hammer together, so the lerp error lies
  along the haft. That reads as a harmless slide.
- **The wind-up path was tuned numerically.** A one-off coordinate search (not part of the build; the values are
  fixed in `SLAM_DESIGN`) over the two wind-up keys and the trapezoid
  speed ramps minimized the worst 120 Hz grip drift. It covered both the Slam's own in-betweens and the
  Idle→Slam blend from every idle phase, with arm comfort and body clearance as penalties.
- **The arm planner** chooses each hand's roll on the haft and each elbow's swivel for the whole clip at
  once (dynamic programming), so elbows never pop and wrists stay straight.

## Checks (all pass; details in `MotionChecks.json`)

Every authored frame, the 120 Hz client in-betweens (per-joint `CFrame:Lerp`, like `EnemyMotion.sample`) and
the 0.12 s Idle→Slam and Slam→Idle blends were checked. Idle→Slam was tested from 12 idle phases.

| Check | Limit | Idle | Walk | Slam |
| --- | --- | --- | --- | --- |
| Elbow flex (deg) | 12–130 | 54.6–65.4 | 64.5–82.7 | 30.9–126.5 |
| Elbow / knee off-axis (deg) | ≤ 2 | 0 / 0 | 0 / 0 | 0 / 0 |
| Knee hinge (deg), forward only | 0–150 | 0–30.3 | 18.3–126.6 | 0–80.5 |
| Wrist bend / twist (deg) | ≤ 35 | 1.3 / 1.0 | 12.8 / 6.2 | 27.5 / 13.8 |
| Shoulder swivel (deg) | ≤ 75 | 0.5 | 13.0 | 68.0 |
| Swivel / spine step per frame (deg) | ≤ 20 | 0.5 / 0.5 | 1.0 / 3.6 | 14.5 / 16.5 |
| Grip, authored (studs) | ≤ 0.05 | 0 | 0 | 0 |
| Grip, 120 Hz in-betweens (studs) | ≤ 0.08 | 0.000 | 0.004 | 0.053 |
| Grip, Idle→Slam / Slam→Idle blend | ≤ 0.08 | | | 0.053 / 0.005 |
| Hammer vs body, BVH (bad frames or samples) | 0 | 0 | 0 | 0 |
| Shaft vs torso core (min) | ≥ 1 | 3.80 | 5.78 | 2.49 |
| Planted-foot drift per frame (studs) | ≤ 0.01 | 0 | 0 | 0 |
| Lowest point (studs) | ≥ −0.05 | 0.000 | −0.017 | −0.025 |
| Impact face corners \|z\| | ≤ 0.03 | | | 0.000 |
| Loop closes / Slam starts and ends on Idle 0 | exact | 0 | 0 | 0 / 0 |
| Joint gaps (studs) | ≤ 1e-4 | 0 | 0 | 0 |

**Axis mapping proof.** Idle frame 0 from `PartPoses.json` against the template's part CFrames relative to
its HumanoidRootPart (`studio-asset-manifest.json`): max position error 5.1e-07 studs, rotation error 0.
The Studio-side converter `studio-prototype/combat/bosses/partposes_to_motor6d.py` also accepts the file.
I ran it as a pure function with a receipt built from the manifest, and nothing was written: round trip
1.1e-06 studs (limit 1e-4), root height 4.45, and Idle frame 0 gives identity `Motor6D.Transform`s
within 8e-07.

**Definitions** (rest-relative, because the template rest is how the sections were sculpted to meet):
- **Wrist bend:** the swing of the hand relative to the forearm, measured from the rest relation. Twist is
  the turn about the forearm axis.
- **Shoulder swivel:** the turn of the elbow plane about the shoulder→wrist line, measured from its rest
  direction carried by the chest.
- **Knee hinge:** the turn about the pelvis X axis carried by the thigh, so knees only bend forward from
  the straight-legged rest.
- **Grip:** the distance from the haft axis to both ends of each fist's grip hole (hole centre ±0.8 along
  the hole). Hands may slide along the haft between 2.45 and 8.10.
- **Hammer vs body:** an exact triangle–triangle BVH overlap between the hammer and every section except the
  two fists. There is one exception: the template's own contact. At rest (Idle frame 0, which must equal the
  template) the lower edge of the right forearm's cuff is already 0.095 studs inside the hammer head beside
  the fist. That contact is allowed up to its rest depth + 0.05. It peaks at 0.138 in the Slam's last
  frames, where the hand rolls back onto the carry grip.

**For information only (not a required check):** a Walk→Slam 0.12 s blend (the slam starting mid-stride)
drifts 0.124 studs. For about 1/30 s the swinging right foot passes through the hammer head while the blend
pulls the hammer toward its rest position. If the runtime blends straight from the chase into attacks, a
short settle (or starting attacks from Idle) avoids it. A dedicated transition can come with the next batch.

## What the model's proportions limit

- **Straight legs at rest.** Hip to ankle is 3.884 of a possible 3.887, so any hip drop bends the knees a
  lot: 0.05 studs gives about 19°. The idle's sink is only 0.1 studs, which is already 30° of knee.
- **Shin edge.** The shin mesh reaches below and behind the ankle. More than about 31° of ankle bend
  pushes its back edge into the ground, so the slam crouch keeps the hips back (0.95) as they drop (1.0).
  The run's heel rolls up early to protect the same edge.
- **Asymmetric forearms.** The right forearm is 3.82 long and the left 2.70. The left arm reaches 5.04 at
  most, so landing the face flat 10.8 studs ahead needs a deep bow: the torso leans 60° with the hips 1.0
  down.
- **Fists fixed across the haft.** The forearms stay roughly perpendicular to the haft (wrist ≤ 35°), so a
  vertical hammer held overhead puts the long right forearm across the face. The hold therefore keeps the
  haft 1.6 studs to his right: from the front his face shows between the arms, but seen from his right
  side the right arm still covers it.
- **The hammer's Motor6D pivot is the head centre** on the HumanoidRootPart, not the grip. Fast arm-driven
  hammer turns (above about 15–20° per frame) pull the haft off the fists between frames, which is why the
  Slam is 30 fps and its drop is torso-driven. If the Studio side ever moved `Boss_Hammer`'s C0/C1 pivot to
  the grip midpoint (rest pose unchanged), fast hammer moves would get much more freedom. This is only a
  suggestion: the template is kept as is.

## Previews

Eevee with the model's own textures, on a grass ground under a soft sky, with a key and a fill light. The
camera is front ¾ from his right for the Idle and Slam, and from his left for the Walk so the hammer doesn't
hide the legs. The Walk camera follows the root at the chase speed. Each mp4 plays
normal speed, then half speed, at 30 fps from 60 Hz client-interpolated poses. The Slam video includes the
in-game 0.12 s blends from Idle and back.
