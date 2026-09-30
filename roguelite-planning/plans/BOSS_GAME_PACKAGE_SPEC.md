# Boss game package spec (Blender side)

This is what each boss folder (`king-crab-boss`, `frost-cyclops-boss`, `pharaoh-boss`, `dragon-boss`) must deliver so Studio can import the boss, play its animations and time its attacks. The Studio pipeline it feeds is the regular-mob one:

1. Studio's 3D Importer takes in the FBX.
2. A receipt of the imported bones and meshes is dumped.
3. `retarget_studio.py`-style retargeting runs.
4. Sampled `Bone.Transform` modules are built.

Nothing here changes the approved model, textures or rig.

## 1. Clips

Author at **24 fps**. The attacks already authored at 30 or 24 fps are resampled to 24 without changing their timing in seconds. Every clip uses only the deform bones that are exported. The clips are the sampled `pose_bone.matrix_basis` of those bones.

Every boss needs:

| Clip | Loop | Guidance |
|---|---|---|
| `Idle` | yes | 2.5–4 s. Heavy breathing and a small weight shift. Secondary bones (belly, mantle, cloth, wings, tail) drift a little later than the body. Last frame equals the first. |
| `Walk` | yes | Heavy, readable gait. Planted feet must not slide: pin them with IK while planted and log the drift. Record `strideLength` (studs travelled per cycle) and `nominalSpeed`. The cycle is 1.2–1.6 s for bipeds and a 4-beat gait for quadrupeds. Weapon arms carry the weapon (Cyclops club, Pharaoh staff). |
| `Hit` | no | 0.4–0.5 s flinch that returns exactly to the Idle start pose. |
| `Death` | no | 1.8–2.6 s collapse onto the ground into a stable final pose. Nothing may pass through the ground plane at z=0 by more than 0.05. |
| attacks | no | The per-boss list below. Every attack starts and ends on the Idle start pose, so it can blend in and out. |

Per-boss attack clips (names exact):

- **FrostCyclops:** `GroundSlam`, `Stomp` (these exist; resample them).
- **Dragon:** `FireBreath`, `TailWhip`, `FrontStomp` (these exist; resample them).
- **Pharaoh:**
  - `CursedBolts`: he raises the crook and points the hook at the target. Energy gathers for about 0.6 s, then three bolts release in a fan. There's a small recoil, then he returns to idle.
  - `TombEruption`: he lifts the staff in both hands, then drives its foot down into the ground in front of him. He holds briefly while he "channels", then recovers.
- **KingCrab:**
  - `ClawCrush`: the crusher claw rises high and back, then smashes flat onto the ground in front of him. The body drops, then he recovers.
  - `RushStart`: he braces low, claws up, then turns his body sideways to the lane.
  - `RushLoop`: a fast sideways scuttle, looping, travelling along the crab's local ±X (his right). Record `rushStrideLength` for it.
  - `RushEnd`: a skid stop back to idle.
  - `BubbleBarrage`: the mouth plates open wide, and the body pumps 3 times as bubbles spray from the mouth. Then the plates close.

## 2. `exports/game/AnimationData.json`

Use exactly the schema that `mob-production/combat-ready/animate_mobs.py` writes (lines 321–336):

```
{"id": "<boss-id>", "fps": 24,
 "bones": {"<name>": {"parent": "<name>|null", "rest": [12]}},
 "clips": {"<Clip>": {"duration": s, "loop": bool,
           "frames": [{"time": s, "transforms": {"<bone>": [12]}}]}},
 "motion": {"strideLength": studs, "nominalSpeed": studs/s}}
```

- `rest` is the parent-relative rest matrix. For the root bone it's `matrix_local`.
- `transforms` is `matrix_basis`.
- Both are written through `cf(m) = S@m@S` with `S = ((1,0,0,0),(0,0,1,0),(0,1,0,0),(0,0,0,1))` (a Y/Z swap), as a 12-number list `[x,y,z,R00,R01,R02,R10,R11,R12,R20,R21,R22]` rounded to 7 places.
- Frames run from 0 to `duration*24` inclusive. For a looping clip the last frame equals the first.

Boss ids: `king-crab`, `frost-cyclops`, `pharaoh`, `dragon`.

## 3. `exports/game/BossGameData.json`

Per attack clip, times are in seconds from clip start:

```
{"attacks": {"<Clip>": {
   "duration": s,
   "warnStart": s,       // when the ground warning should appear (start of the readable windup)
   "impact": s,          // the frame the hit lands / projectile releases
   "activeEnd": s,       // last moment the hit shape is live (== impact for instant hits)
   "recoveryEnd": s,     // when the boss can move again
   "points": {"<pointName>": {"bone": "<deform bone>", "offset": [x,y,z],   // in that bone's local space, Blender axes, studs
                              "rootAtImpact": [x,y,z],                    // root space at the impact frame, Blender axes
                              "rootAtImpactStudio": [x,y,z]}},           // same point mapped to Studio axes (-X, Z, Y)
   "directionAtImpact": [x,y,z], "directionAtImpactStudio": [x,y,z]      // where relevant (breath, spikes, bolts, rush)
 }},
 "rootHeight": studs, "height": studs, "footprintRadius": studs}
```

Required points:

| Boss | Attack | Point(s) |
|---|---|---|
| Cyclops | GroundSlam | `ClubImpact` |
| Cyclops | Stomp | `StompImpact`, plus a spike direction |
| Dragon | FireBreath | `FireOrigin`, sampled every 2 frames over the hold as `samples: [{time, root, dir}]` |
| Dragon | TailWhip | `SpadeTip`, with its arc (pivot, start/end angle, radius) |
| Dragon | FrontStomp | `LeftFrontImpact`, `RightFrontImpact` |
| Pharaoh | CursedBolts | `BoltOrigin` in the crook hook, plus release direction |
| Pharaoh | TombEruption | `StaffImpact` |
| KingCrab | ClawCrush | `ClawImpact` |
| KingCrab | BubbleBarrage | `BubbleOrigin` at the mouth, plus direction, with the release window as `impact`..`activeEnd` |
| KingCrab | Rush | the Rush clips' strides |

## 4. `exports/game/<BossName>_Studio.fbx`

This is the import file for Studio's 3D Importer.

- **Contents:** the rest mesh and armature. Deform bones only, no leaf bones, no animation, and no IK or control bones.
- **Mesh objects:** one per material section, named after the section.
- **Materials:** each material is named `<BossName>_<Section>` and uses that section's **1024² delivery base-colour map** as its Image Texture. Export with `path_mode='COPY', embed_textures=True`, and also copy the PNGs into `exports/game/<BossName>_Studio.fbm/`.
- **Export settings:** `axis_forward='-Z', axis_up='Y', add_leaf_bones=False, use_armature_deform_only=True, bake_anim=False`, the same as the regular mobs.
- **Glow sections** (EyeGlow, LavaGlow) stay as separate meshes, so Studio can set them to Neon.

## 5. Validation and previews (small)

- Extend `validate_exports.py` to reimport `<BossName>_Studio.fbx` fresh. Check that each mesh is under 20k tris, the bone names match `AnimationData.json`, and textures load. Then check that every clip in `AnimationData.json` has the right frame count, has no NaNs, and that looping clips close (last frame equals first).
- Render one contact sheet, `previews/GameClips.png`: 4–6 frames each of Idle, Walk, Hit, Death and any new attack, front ¾ view, Workbench.
- Render one low-res Workbench mp4 per new attack. Nothing else.
- Update `README.md` with a short "Game package" section.
