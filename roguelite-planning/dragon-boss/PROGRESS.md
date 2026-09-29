# Dragon boss — progress log

## State: DELIVERED (user polish pass done)

- The final full build ran on 2026-09-29.
- `validate_exports.py` passes 34 / 34 checks.
- Silhouette IoU is 0.852, accepted under the coordinator's wrap-up order (the target was 0.92).
- `_work/` was deleted at delivery.

The user-polish pass did two things:

- **Bigger teeth.** There are 14 chunky faceted fangs. Big corner tusks overlap the lips, and the fangs are a warmer
  beige.
- **Attack kit.** It is replaced by `FireBreath`, `TailWhip` and `FrontStomp`:
  - Each attack has an `Impact` marker, and its gameplay data is in `manifest.json` → `attacks`.
  - Each attack is exported as an armature-only FBX clip and is also in the GLB.
  - `previews/AttackCheck.png` shows windup, impact and recovery, in front and ¾ views.
  - Each attack has a Workbench mp4 (`previews/Attack_*.mp4`).
  - Planted-foot drift is ≤ 0.0053 studs.

See `README.md` for everything else: rebuild commands, measurements, colour table, pass log, and what was and was not
verified.

## To rebuild

```
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python build_dragon.py
python label_sheets.py
python compare_reference.py previews/Reference_Match.png _work/final_mask.png
"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python validate_exports.py
```

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
