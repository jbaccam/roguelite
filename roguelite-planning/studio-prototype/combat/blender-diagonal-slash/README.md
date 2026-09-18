# Diagonal katana slash — Blender motion review

Open `Katana_Diagonal_Slash.blend` and play frames 1–82 at 60 fps. This contains the original user-scaled katana mesh and a static Roblox avatar reference. `Camera | front diagonal review` is active; `Camera | three quarter depth review` provides a depth view.

`Katana_Diagonal_Slash.mp4` plays the motion twice at normal speed and once at quarter speed. Separate normal/slow MP4s and a labeled contact sheet are included for review.

The cut accelerates from above the right shoulder into a continuous descending arc, across the front of the torso toward the opposite hip. It advances forward to extend reach. The blade rotates about one fixed axis with no axial spin. Recovery moves outside and upward before returning to exactly the initial position and quaternion, including the direction of blade curvature. Editable location and quaternion keys are stored on the katana object.

Timing: anticipation 0.16–0.27 s; cut 0.27–0.44 s; follow-through 0.44–0.53 s; recovery 0.53–1.08 s. The cycle includes short initial and final holds.

`validation.json` records 1,351 sampled poses of the entire sword mesh. An axis separating its bounding box from a conservative avatar enclosure exists at every sample; the blade also remains above the floor. Initial and final position and quaternion errors are zero.

This is an editable Blender motion preview. No Studio objects, gameplay code, or Roblox animation assets were changed. It is not an exported Roblox skeletal animation.

Rebuild with Blender 5.2: `blender -b --python build_diagonal.py -- checks`, then `-- render`; encode with `python encode_preview.py`.
