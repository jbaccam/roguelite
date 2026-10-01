# Dragon boss — progress log

## State: DELIVERED (Studio FBX size-cap fix, 2026-09-30)

- **Root cause:** Roblox caps a MeshPart at 2048 per axis, and this FBX imports at ×100. Five sections were over
  20.48 studs, so Studio scaled the import by 0.6815 and the meshes no longer lined up with their bones.
- **Fix:** `Dragon_Studio.fbx` now has 15 mesh pieces, each at most 15.4 studs (`exports/game/StudioMeshes.json`).
  Bones, rests, AnimationData and materials are unchanged.
- **Validation:** 57 / 57 checks pass. A posed re-import matches the source to 0.00005 stud (see
  `previews/StudioFBX_PoseCheck.png`).

## Earlier state (game package)

The game package follows `plans/BOSS_GAME_PACKAGE_SPEC.md`. Build it with `DRAGON_STAGE=game`. It produces:

- `exports/game/Dragon_Studio.fbx`, plus the `.fbm` folder of 1024 maps;
- `AnimationData.json`: 7 clips (Idle, Walk, Hit, Death, FireBreath, TailWhip, FrontStomp) at 24 fps over 90 bones;
- `BossGameData.json`;
- `previews/GameClips.png` and `previews/Clip_*.mp4`.

Results:

- **Walk:** stride 4.267 studs per cycle, speed 2.56 studs/s, planted drift 0.
- **Death:** minimum vertex z −0.05.
- **Attacks:** they start and end exactly on the Idle start pose. To get this, the front-foot IK pole was changed, and
  ReferencePose keeps its old pole.
- **Validation:** 46 / 46 checks pass.

## Earlier state (TailWhip v2)

- `validate_exports.py` passes 34 / 34 checks.
- Silhouette IoU is 0.852, accepted under the coordinator's wrap-up order (the target was 0.92).
- `_work/` was deleted at delivery.

The user-polish pass did two things:

- **Bigger teeth.** There are 14 chunky faceted beige fangs, with corner tusks overlapping the lips.
- **Attack kit.** It is `FireBreath`, `TailWhip` and `FrontStomp`:
  - Each attack has an `Impact` marker, and its gameplay data is in `manifest.json` → `attacks`.
  - Each attack is exported as an armature-only FBX clip and is also in the GLB.
  - `previews/AttackCheck.png` shows windup, impact and recovery, in front and ¾ views.
  - Each attack has a Workbench mp4 (`previews/Attack_*.mp4`).

TailWhip v2 answers the user's "more butt into it, wider AoE":

- The hips coil to 32° for the wind-up and swing to −46°/−48° through the whip, pivoting on the planted front feet.
- The hind feet step round with the body: an automatic step planner, plus a hop during the fast swing.
- The tail straightens through the swing, with the base leading and the spade trailing (3.5-frame lag), then snaps
  through.
- The spade sweeps 205° (−93.5° → +111.5° about the fitted pivot (1.86, 5.89)), radius ~16.6, impact f27.
- The action is 72 frames long and keyed every frame.
- Planted-foot drift is 0.000 studs.
- Capsule clearance to the legs is ≥ 1.8 studs, and to the wings ≥ 5.

See `README.md` for everything else: rebuild commands, measurements, colour table, pass log, and what was and was not
verified.

## To rebuild

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python build_dragon.py
python label_sheets.py
python compare_reference.py previews/Reference_Match.png _work/final_mask.png
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python validate_exports.py
```

To update one attack in the saved blend, set `DRAGON_STAGE=attack DRAGON_ATTACK=TailWhip`, then run
`label_sheets.py`.

## Pass log

| Pass | What changed | Silhouette IoU |
| --- | --- | --- |
| P0 | Reference mask; camera solved as a level camera with lens shift, f 1150. | — |
| P1 | Blockout. | 0.767 |
| P2 | Blender pipeline. | 0.769 |
| P3 | Wings. | 0.80–0.82 |
| P4 | Rest wing set from the reference spread. | 0.836 |
| P5 | Faceted SDF. | 0.845 |
| P6 | Textures and lighting. | 0.845 |
| P7–P9 | Head, neck, throat plates, pillar legs, plastron. | 0.85–0.86 |
| P10–P12 | Feet and claws, front IK, spade, horns, wing bones, colour calibration, mottling. | 0.852 |
| Final | Full build, validation and previews. | — |
| Polish | Teeth; attack kit replaced (FireBreath, TailWhip, FrontStomp) with videos. | 0.852 |
| TailWhip v2 | Hip swing, hind-foot stepping, 205° arc, impact f27, drift 0, validation 34 / 34. | 0.852 |
| Game package | Studio FBX, AnimationData (7 clips), BossGameData, GameClips sheet and mp4s; validation 46 / 46. | 0.852 |
| Studio fix | Mesh names `Dragon_<Section>`; oversize sections split under the 2048 MeshPart cap; posed re-import proof; validation 57 / 57. | 0.852 |
