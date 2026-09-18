# Katana outward horizontal slash preview

Independent Blender motion study requested alongside the Studio implementation. Open `Katana_Outward_Slash.blend` and play the timeline, or view the MP4/GIF. The first cut attacks the front target, the second attacks the rear target, and the final replay shows the rear cut at 25% speed.

Uses the actual approved katana mesh and measured user-adjusted play scale, with its materials packed into the Blender file. Blue proxy is the avatar; green proxies are targets. Avatar faces the front target. This is a motion study, not an exported Roblox animation or a claim that Blender drives the gameplay implementation.

- Fixed right-side idle grip, no orbit.
- Outward windup: 0.09 seconds.
- Horizontal slash: 115 degrees in 0.11 seconds, mirrored for front versus rear.
- Grip extends 0.85 studs farther right and 1.1 studs toward the front/rear during the attack.
- Recovery: first lift the blade upright, then retract the grip; 0.16 seconds total.
- Rear full-mesh vertex samples across 1,001 poses remained at least 2.039 studs from the avatar center at body height, outside the 1.8-stud guide circle. This sampling is a preview check, not a continuous collision proof or a substitute for Studio hit testing.

Rebuild with Blender 5.2 using `build_preview.py`; encode its rendered frames with `encode_preview.py` (Python, OpenCV, Pillow, imageio-ffmpeg).
