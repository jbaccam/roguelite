# Hammer Brute rebuild: design (2026-10-03)

Pine Valley's wave-20 boss (and the tutorial's wave-3 boss) gets a new model, new animations and the same runtime as the other four bosses. The current model was made by another agent. It is 16 rigid mesh pieces on a 17-bone rig, and it runs on its own runtime (`BossService` + `BossMotion` + `BossPresentation`). That runtime re-solves both arms every frame. Its README records the result: elbows hit their clamp, and the Charge→Slam blend failed (wrist bend 38.8°, forearm through the hammer head). The user rated it well below the King Crab, Pharaoh, Frost Cyclops and Dragon.

## Decisions (user, 2026-10-03)

- **Runtime:** move him onto the map-boss runtime (`MapBossService`, `MapBossPresentation`, `MapBossDefs`), the same as the other four.
- **Build:** a fresh rebuild. Nothing from the current model is reused. Time is not a constraint, so quality comes first.
- **Moves:** the same attacks (Slam, Swing, Spin, Charge) and the same movement (walk/chase, charge run). They should be more intense and more fluid.
- **More intensity:** all four options. Faster and heavier hits, enrage at half HP, combos, and follow-up hazards.
- **Kept as they are:**
  - the names: HUD "Hammer Brute"; the intro card and tutorial text "Hammer Zombie Boss";
  - Pine Valley wave 20, and 18,000 HP;
  - about the same height in game (13.7 studs);
  - the sky-drop entrance.
- **Build method:** built in Blender like the other four. No Toolbox or Creator Store model.

## 1. Model

New folder `roguelite-planning/hammer-brute-boss/`, structured like `frost-cyclops-boss/`:
- a generator plus pure-numpy modules for the sculpt, design, parts, grip, weights, paint, pose, motion and camera;
- `exports/`, `textures/`, `previews/`, `source/`, `manifest.json` and `validation-report.json`.

**Reference.** The reference is `hammer-boss/source/boss-reference.png`, copied unchanged into `source/`. It is the same image the user attached on 2026-10-03.

**Style.** Stylized low-poly and painterly, never realistic: signed-distance sculpting, then flat-shaded decimation. Textures are painted in numpy from baked geometric passes. No reference pixels go into the model or the textures.

**Parts, as read from the reference:**
- **Head:** blocky, with a heavy scarred brow and a bleeding forehead wound. White glowing eyes (a separate `EyeGlow` mesh, so Studio can set it to Neon), a snarling mouth and broken teeth.
- **Body:** huge segmented shoulders, upper arms and forearms, and big closed fists. A round projecting belly with a navel.
- **Skin:** mottled green with dark speckles and red wound patches.
- **Clothes:**
  - a torn cream tank top with blood stains;
  - dark-brown suspenders with square iron buckles;
  - a maroon waist sash;
  - ragged charcoal trousers with skin showing through the holes;
  - block feet.
- **Hammer:** a beveled dark-iron head with raised square plates and blood stains, on a wooden haft with dark iron bands. It is its own mesh section, `Hammer`.

**Size.** The top of the head is 13.7 studs, authored at final size (`MapBossDefs` scale 1), so the texture density holds in game.

**Reference match.** Render at the reference's exact solved camera, then compare silhouette IoU and the colour of each region. This is the same method as `frost-cyclops-boss/compare_reference.py` and `calibrate.py`. Targets: IoU ≥ 0.92, and region colours within about 10%. Where a target isn't reached, the README says so.

**Budget.** Every mesh section stays under 20k triangles.

## 2. Rig and skinning

**Bones.** About 65 deform bones, with R15 names:
- the spine: `Root → HumanoidRootPart → LowerTorso → UpperTorso → Head`;
- face bones `Jaw`, `Brow`, `EyelidUpper`;
- arms with `{Left,Right}LowerArmTwist` bones, so wrist roll spreads along the forearm instead of pinching at the wrist;
- hands with `{Index,Middle,Ring,Pinky,Thumb}1-3`;
- legs down to `Toes`;
- secondary bones `Belly`, `Shirt_Front_1/2` and `Shirt_Back`;
- `Hammer` under `RightHand`.

**Grip.**
- The right grip is exact, because the hammer is parented to the right hand.
- The left hand is posed with IK to its grip point on the shaft, and the result is baked.
- Grips slide along the shaft between the carry position and the attack positions, as now.
- The grip is solved like `fc_grip.py`: the haft runs across the palm, the fingers curl round it at contact distance, and the thumb closes over them.

**Weights.**
- At most 4 influences per vertex, normalised.
- The clothes, buckles and teeth are rigid to their bones.
- The shirt follows the skin, with its hem on the shirt bones.
- The trousers follow the thighs and shins.

**Range-of-motion sheet.** A sheet of the most extreme poses the clips actually reach: overhead slam, full spin wind-up, charge crouch, death. Weights are tuned on it until the elbows, shoulders, knees and belly keep their volume and don't collapse.

## 3. Clips

Clips are authored in Blender with IK and joint limits, then baked to deform bones only.
- **Frame rate:** 24 fps. An attack can move up to 30 fps (EnemyMotion reads `clip.fps`) if the grip check at the client's in-between frames fails at 24.
- **Start and end pose:** every attack and combo starts and ends exactly on Idle frame 0.

| Clip | Length | Loop | Key times (s, rate 1) |
| --- | --- | --- | --- |
| Idle | 3.0 | yes | heavy breathing, a weight shift, one blink; the belly and shirt lag behind |
| Walk | about 0.65 s cycle | yes | a lumbering, stomping run authored at the chase speed (see below) |
| Hit | 0.45 | no | returns exactly to Idle frame 0 |
| Death | about 2.5 | no | drops the hammer, falls to his knees, collapses; nothing below ground by more than 0.05 |
| IntroLand | about 3.0 | no | airborne pose with the hammer overhead for 0.65 s, landing slam at 0.65, rises and roars, back to idle |
| Roar | 1.2 | no | enrage roar, no hit |
| Slam | about 1.45 | no | impact 0.70 |
| Swing | about 1.35 | no | sweep 0.50–0.70 (180°) |
| Spin | about 1.6 | no | sweep 0.50–0.95 (360°) |
| SwingSpin | about 1.9 | no | sweep 0.50–0.70, then sweep 0.80–1.25 |
| SpinSlam | about 2.1 | no | sweep 0.50–0.95, then slam impact 1.35 |
| ChargeStart | 0.5 | no | loads into a hunched sprint |
| ChargeRun | about 0.53 cycle | yes | stride tied to the charge speed (32) |
| ChargeSlam | about 1.2 | no | brakes from the run into an overhead slam; impact 0.40 |

**Walk.** The old walk was authored at 4.5 studs/s and played about 4× faster to keep up with an 18 studs/s chase, which looked like frantic shuffling. The new Walk is authored at the real chase speed, 20 studs/s. Its stride is about 13 studs per cycle, so the client plays it at about 1× (and 1.15× when enraged). `motion.strideLength` and `nominalSpeed` are recorded in `AnimationData.json`, and the plan checks how the client turns speed into playback rate.

**How the motion should feel.**
- **Wind-ups:** shorter than before, with a clear held anticipation pose of 2–3 frames.
- **Strikes:** fast, eased in.
- **Impacts:** the body compresses and the knees drop, and the hammer bounces a little.
- **Recovery:** settles with overlap. The belly and shirt lag, and the head trails.
- **Combos:** keep the momentum. The Swing's follow-through becomes the Spin's wind-up, and the Spin unwinds up into the Slam.

**Game package.** It follows `plans/BOSS_GAME_PACKAGE_SPEC.md`, with boss id `hammer-brute`:
- `AnimationData.json`, `BossGameData.json` and `HammerBrute_Studio.fbx` plus its `.fbm`;
- `validate_exports.py`;
- a `GameClips.png` contact sheet and one review mp4 per attack (normal speed, then half speed).

**Points.**
- `HammerFace` is the centre of the striking face, sampled across every attack.
- `HammerGrip` sits on the shaft between the hands, sampled; it is the sweep's `mid`.

**Combo timing.** Combo clips add a `phases` list to `BossGameData`. Each phase has its own warnStart, impact, activeEnd and points.

## 4. Gameplay

A new `MapBossDefs` entry. All numbers are starting points for the user's play-test.

```lua
D.Hammer={anim='hammer-brute',name='Hammer Brute',health=18000,scale=1,chaseSpeed=20,
 intro={drop=1.2,fall=.65,after=3.6,clip='IntroLand'},roar='Roar',
 enrage={cooldown=.6,chase=3,follow=2,order={'SwingSpin','Slam','Charge','SpinSlam','Swing','SpinSlam','Spin'}},
 tutorial={order={'Slam','Swing','Charge','Slam','Spin'},enrage=false,follow=false},
 attacks={
  Slam={clip='Slam',range={0,16},cooldown=.8,damage=26,shape='circle',point='HammerFace',radius=9.5,height=6,knockdown=.6,follow=CRACKS},
  Swing={clip='Swing',range={0,14},cooldown=.8,damage=20,shape='sweep',point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4},
  Spin={clip='Spin',range={0,14},cooldown=1,damage=22,shape='sweep',point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4},
  SwingSpin={clip='SwingSpin',range={0,14},cooldown=1,phases={
   {shape='sweep',damage=20,point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4},
   {shape='sweep',damage=22,point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4}}},
  SpinSlam={clip='SpinSlam',range={0,14},cooldown=1.1,phases={
   {shape='sweep',damage=22,point='HammerFace',mid='HammerGrip',radius=3.2,baseRadius=4},
   {shape='circle',damage=26,point='HammerFace',radius=9.5,height=6,knockdown=.6,follow=CRACKS}}},
  Charge={clips={'ChargeStart','ChargeRun','ChargeSlam'},facing='forward',range={22,70},lockout=5,cooldown=1,damage=24,
   shape='lane',length=75,width=9,speed=32,contact=4,knockdown=.6,
   finish={shape='circle',damage=26,point='HammerFace',radius=9.5,height=6,knockdown=.6,follow=CRACKS}},
 },order={'Slam','Swing','Charge','Slam','Spin','SwingSpin'}}
-- CRACKS={radius=5.5,delay=.85,maxTargets=3,range=40,damage=16}
```

Each phase's timing (warnStart, impact, activeEnd) comes from `BossGameData` `phases`, in order.

**Changes from today:**
- **Damage:** Slam 24 → 26 and Swing 18 → 20. Spin 22 and Charge 24 stay the same.
- **Speed:** chase 18 → 20, or 23 when enraged. Players run at 24, so a straight run still gets away. Charge 30 → 32.
- **Timing:** the old cooldowns counted from the start of an attack; the new ones count from the end of recovery (`MapBossService`). Today's Slam gap after recovery was about 1.0 s; now it is 0.8 s, and 0.48 s when enraged.

**Charge.** The Charge sits in the attack order, but its range starts at 22 studs, so the order walk only picks it when the nearest player is out of melee reach. Then it starts as soon as the cooldown allows, but never within 5 s of the last charge (`lockout`). This replaces today's separate 6 s `nextCharge` clock.

**Enrage, below 50% HP.**
- He roars once (the Roar clip, anchored, no hit). If he is mid-attack, the roar waits until that attack finishes.
- His eyes ignite red (`EyeGlow` tint) and the camera shakes.
- Cooldowns ×0.6, chase +3, follow-up cracks +2 spots, and he switches to `enrage.order`.

**Follow-up cracks.** After every slam (Slam, the SpinSlam slam, and the ChargeSlam), cracks open under players the hit missed and erupt 0.85 s later. This is the existing `follow` system.

**Tutorial.** When `TutorialBossHealth` is set, the boss uses that fixed HP (650, with no difficulty or party scaling) and `def.tutorial`. That means no enrage, no combos and no cracks. He keeps Slam, Swing, Spin and Charge (the tutorial boss charges today too). The tutorial fight teaches the moves; it doesn't punish.

**Fairness rules that stay:**
- Hit tests use `CharacterService.seen`.
- Every warning appears the moment he commits.
- Each player is hit at most once per attack phase.
- The Slam still hits up to 6 studs above the impact point, so a plain jump doesn't clear it (`height`).

## 5. Effects and sound

New file `combat/bosses/BossVfx/Hammer.luau`, built on `BossVfx/Common`. Effects stay flat: no shaded 3D effect meshes.
- **Slam:** dust shockwave rings (`ShockwaveRing`, `DustPuff` flipbook), an impact star, and a new painted `EarthCracks` ground decal.
- **Swing and Spin:** hammer trail crescents made from Neon segments along the `HammerFace` track.
- **Charge:** dust kicked up while running, and a skid trail at the stop.
- **Cracks:** each crack warning becomes a crack decal, then a dirt burst when it erupts.
- **Enrage:** a red eye glow, a roar shockwave and steam puffs.
- **Camera shake:** `C.shake`, scaled by distance. Strongest on slams, the landing and the roar.
- **Sound:** punchy, slightly cartoony, from the existing small kit, pitch-shifted (`impact_explosion_03` and others). Nothing realistic.

## 6. Runtime changes

**`MapBossService`.** Each addition comes with tests in `MapBossServiceTests`.
1. **Multi-phase attacks (`phases`).** Each phase has its own shape, damage, timing and hit memory. The client draws every phase's warning at commit. A later phase's warning fills in as its hit approaches.
2. **A lane that keeps running.** `facing='forward'` means he runs straight down the lane instead of the crab's side-on run. `contact` means that while the target stays in the lane, the run continues until his body is `contact` studs from them, up to `length` or a wall (ported from `BossService.stepCharge`). The new length is published so the client re-times ChargeSlam. `finish` adds a circle hit, with its own follow-up, at the end clip's impact.
3. **`lockout`.** An attack's own minimum gap between starts. The order walk skips it while it's locked out.
4. **Intro (`def.intro`).** For wave bosses only (not practice ones). He gets the same attributes `BossService` sets today: `BossIntroStart`, `BossIntroLand`, `BossIntroUntil`, plus `CinematicUntil`. That makes him invulnerable through `CombatEffectsService`, freezes players and enemies, and holds him anchored until it ends.
5. **Fixed HP and tutorial variant.** Taken from `TutorialBossHealth`.
6. **Roar and `enrage.order`.**
7. **Full-circle sweeps.** A sweep turning 360° or more warns as a full ring (inner to outer) instead of an arc that wraps around.
8. **Circle `height`.** A circle hit only counts within `height` studs of the impact, vertically. The plan first checks whether `MapBossShapes.contains` already limits height for circles, and adds the rule only if it doesn't.

**`MapBossPresentation` and `BossIntro.client`.**
- Plays `IntroLand` timed to `BossIntroLand`. `BossIntro.client` also watches the `MapBoss` tag for bosses with an intro, and names the card from `BossName`, or "HAMMER ZOMBIE BOSS" for the Hammer.
- Draws the combo phases and re-times the charge lane.
- Plays the Roar on enrage.

**Template and timing.**
- `InstallMapBossTemplates`, `retarget_boss.py` and `build_boss_modules.py` run for `hammer-brute`, the same as for the other four.
- The template is `ServerStorage.RogueliteNPCs.Hammer_NPC`.
- The `Hammer` section is left out of the body "shell" that player weapons measure to, as it is today, so hitting the hammer doesn't count as hitting him.

**Retire the old runtime.**
- `BossService.luau`, `hammer-boss/BossMotion.luau`, `BossPresentation.client.luau` and `BossData` leave `default.project.json` and Studio.
- `BossEncounter`'s Hammer branch and `RogueliteZombieChase`'s Hammer admin-spawn branch go through `MapBossService`.
- The old template and modules are backed up to `ServerStorage.BeforeHammerBrute_20261003`.

**Scripts that check `IsHammerBoss` or the `HammerBoss` tag switch to `IsMapBoss` / the `MapBoss` tag:**
- `RogueliteCombat` (shell and melee aim);
- `LegendaryMoves`, `RogueliteMeta`, `ShardDropService`, `ShopService`, `ZombieDeath` and `RunAnalytics`;
- `RogueliteZombieAnimation`;
- `RogueliteHUD`, `TutorialGuide` and `BossIntro`;
- comments in `CharacterService`, `PetService` and `CombatEffectsService`;
- tests in `MapConfigTests`, `AdminConfigTests` and `EnemyTests`.

`MapConfig.PineValley.boss` stays `'Hammer'`, which is now a `MapBossDefs` id. `HammerBossWave` keeps its meaning.

**Migration order.** The new runtime pieces and every consumer update land together in one Studio sync (never break Studio between tasks).

## 7. Quality checks

**Blender, every authored frame of every clip:**
- **Elbows and knees:** one hinge axis (at most 2° off-axis). Elbow flex 0–140°; knees bend forward only, 0–150°.
- **Wrists:** flex and extension ≤ 35°, side-to-side bend ≤ 25°. Roll is shared between the twist bone and the hand.
- **Shoulders and spine:** no swivel step over 20° per frame (a spike check), and spine twist ≤ 45°.
- **Grip:** both palms within 0.05 studs of the shaft surface, with the fingers closed round it.
- **Hammer vs body:** mesh-against-mesh BVH overlap test, with nothing inside the body. The only contact allowed is the hands.
- **Body vs body:** the forearm against the upper arm, belly and chest, and the thigh against the belly. Slight muscle overlap is allowed; a pass-through is not.
- **Feet:** a planted foot drifts ≤ 0.01 studs per frame, and nothing goes below the ground by more than 0.05.
- **Clip ends:** loops close, and attacks start and end on Idle frame 0.

**The client's own in-between frames.** The same grip, hammer and joint checks run on poses blended the way `EnemyMotion.sample` and `blend` do it: a per-bone `CFrame:Lerp`, sampled at 120 Hz. The limit is grip drift ≤ 0.08 studs. Clip-to-clip blends are checked too.

**Studio:**
- **Import receipt:** bone names and count match `AnimationData.json`, the scale is right, and the meshes and textures are present.
- **Visuals:** checked in Play, not just Edit. Textures go on via `TextureID`, because `SurfaceAppearance` comes up blank in Play.
- **Server tests:** extended `MapBossServiceTests`. Each attack phase hits once, with no early hits. The slam hits inside its radius and misses outside it. The charge reaches a player who stands still, and a player who side-steps escapes it. Combos hit per phase. Enrage triggers at 50%. The tutorial variant has no enrage and no combos.

## 8. Checkpoints with the user

1. **Model:** `Reference_Match` side by side with the reference, plus a turnaround, before the animation work.
2. **Animation:** review mp4s of every clip at normal and half speed, plus an attack-check sheet with grip close-ups.
3. **Studio:** the FBX import may need one click in the 3D Importer. The runtime and template push waits for an explicit go-ahead, and the user does the play-test.

## Out of scope

- The other four bosses and their numbers.
- Balance beyond the starting numbers above.
- Multiplayer behaviour on live servers. The user tests that.
- Deleting the old `hammer-boss/`, `hammer-boss-faithful/` and `hammer-boss-rebuild/` folders. They stay as history.

## Change of plan (user, 2026-10-04): keep the original model

The user rejected the fresh remodel ("bring back the old hammer boss and just make his attacks better like how we discussed his move sets"). The remodel work-in-progress stays in `hammer-brute-boss/` (commit 74b0021) as history only. What changes:

- **Model.** The original `hammer-boss/finished` model, the 16-section Motor6D template `ServerStorage.RogueliteNPCs.HammerBoss_NPC`, keeps its mesh, textures and in-game size: the template is authored at 1.0, and the map-boss def uses `scale=1.15`. No re-import is needed.
- **Runtime.** It runs on the map-boss runtime that is already in Studio (§4–§6 unchanged): combos, the forward charge with a finish slam, follow-up cracks, enrage with a roar, the sky-drop intro and the tutorial variant. `EnemyMotion.bind` drives Motor6D rigs by joint name, so the old template plays sampled `Motor6D.Transform` clips.
- **Animation.** All 14 clips in §3 are re-authored in Blender on the old rig in a new self-contained folder, `roguelite-planning/hammer-boss-moves/`:
  - the same names, timings and feel targets;
  - the same §7 joint, grip, hammer-clearance and foot checks, adapted to rigid sections;
  - no finger, jaw or twist bones (the old rig has none).
  - The old model's measured limits are in `hammer-boss/README.md`, and the new clips must respect them: elbow hinge 12–130°, wrist bend ≤ 35°, shoulder swivel ≤ 75°, the shaft kept outside the torso core, and the carry grips at 2.72 / 8.05 along the haft.
- **Hand-off format.** `hammer-boss-moves/exports/game/PartPoses.json` holds, per clip and frame, each Studio part's CFrame relative to HumanoidRootPart (Studio axes, template scale 1.0). Alongside it go `BossGameData.json` (§3 attack timings and phases; `HammerFace`/`HammerGrip` given as offsets in the `Hammer` part's space) and `motion` (`strideLength`, `nominalSpeed`, `chargeStrideLength`). The Studio side converts part poses to `Motor6D.Transform = C0⁻¹ · P0⁻¹ · P1 · C1`, using a read-only dump of the template's Motor6Ds.
- **Template.** `Hammer_NPC` is installed as a copy of `HammerBoss_NPC` with map-boss attributes, plus two small Neon eye plates named `HammerBrute_EyeGlow` welded to the head (white, red when enraged). Weapon, turret and pet reach skip the `Hammer` part and the hands, as the legacy runtime did.
