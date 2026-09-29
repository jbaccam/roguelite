# Frost Cyclops: reference notes

Source: `FrostCyclops_reference.webp`, 1086 × 1448 RGB, unchanged, SHA256
`DAAFFA2AE07CF831D8F83242B9A5B72126C30F1AEFA1D2395112BC2B3F6F63A5`.
All coordinates below are reference pixels (x right, y down). "Right" and
"left" mean the character's own sides: the character's right is on the viewer's
left. Landmarks were read off gridded, zoomed crops. The full table is in
`reference_measurements.json` (`landmarks_px`, row spans of the mask, colour
probes), and they are drawn on `../previews/Reference_Landmarks.png`.

## Camera and figure

- The view is from the front and a little low. The horizon crosses near the image centre, so the pitch is about 0°. The camera solve is in `camera_solution.json`: f = 2077 px (51.6 mm on a 36 mm vertical sensor), yaw 1.15°, RMS reprojection 1.0 px.
- The figure's bounding box (mask) is x 49–1052, y 185–1307. The crown is at y 185; the soles are at y 1248 (right) and 1290 (left).
- The stance is wide. The left foot is about 2 studs further forward than the right, which is turned out about 50°. The torso is yawed about 15° toward the character's right, which puts the navel, sternum and buckle about 1 stud right of the pelvis centre. The head faces the camera.

## Part inventory (counts)

| Part | Count / description |
| --- | --- |
| Eye | 1. White sclera, cyan iris with a darker rim and a lighter lower half, black pupil, a small catch-light (upper left). A dark navy socket ring surrounds it. The eye is 50 px across (517–567) and the iris about 30 px. |
| Brow | 2 heavy slabs in an angry V that meet at a centre notch (x 539, y 240) above the eye. |
| Ears | 2. Small, pointed at the top, set at eye level (x 463 and 624). |
| Mouth | 1. An open grimace crescent (x 497–600, y 306–330). The lower jaw is a heavy shelf that juts past the upper lip. |
| Teeth | About 4 small upper teeth and 4 flat lower teeth are visible. |
| Tusks | 2. They rise from the lower-jaw corners and point up. The tips are at y 298 (right) and y 290 (left); the left tusk is larger. |
| Nose | None modelled; there is only a slight bump. |
| Fur mantle | 2 halves with a collar gap at the throat. Right shoulder: about 4 visible rows, 20–25 tufts. Left shoulder: a higher, fuller pile of about 5–6 rows, 35–40 tufts. It stands up behind the head. Tufts are leaf-shaped, pointed, faceted and thick, with warm grey shadows between rows. |
| Pecs | 2 heavy slabs with a crisp lower edge (y ~505). |
| Navel | 1 dark pit (487, 690). |
| Forearm wraps | Right: 3 stacked leather bands (y 621–778). Left: 2 wide bands plus a thin lip (y 740–900). Edges are rounded and slightly irregular, with scratch wear. |
| Fists | 2. Right: closed on the club haft. Left: a closed fist with the knuckles forward-down (bottom at y 1046). |
| Club | 1 dark wooden haft, thick (about 72 px at the fist exit, 90 px at the lashing). A faceted grey stone oval (x 52–338, y 995–1300), 2 straps crossing in an X on its front, 1 band round the top, and 2 lashing loops where the haft enters. |
| Belt | 1 brown leather belt (y ~690–740), 1 octagonal grey stone buckle (425–548 × 718–815), 2 rivets beside the buckle, and 2 hanging strap ends (right of the buckle long, left short). |
| Loincloth | A short dark purple-brown ragged skirt all round, with about 9–10 jagged hem points across the front. A long centre flap under the buckle ends in a point at (548, 1090) between the knees, with about 5 points. Cream fur tufts show at both hips. |
| Feet | 2, bare. 4 blocky toes each, and 4 blocky toenails each (big-toe nail about 55 px wide). |
| Ground | Snow. The cast shadows fall behind-right of the feet and club, so the sun is high and slightly front-left. |

## Colours (sRGB, eyedropped by region: lit 85–97th, mid 45–55th, shadow 3–15th luminance percentile)

| Region | Lit | Mid | Shadow | Pixels |
| --- | --- | --- | --- | --- |
| Skin, belly | 162, 180, 204 | 130, 153, 184 | 98, 122, 157 | 31115 |
| Skin, left upper arm | 187, 199, 224 | 152, 170, 199 | 111, 137, 172 | 29670 |
| Skin, right upper arm | 180, 198, 237 | 139, 157, 203 | 69, 98, 142 | 15576 |
| Skin, left shin | 123, 145, 177 | 96, 121, 157 | 72, 98, 135 | 22560 |
| Skin, forehead | 180, 196, 219 | 165, 181, 209 | 93, 121, 164 | 5966 |
| Fur mantle | 244, 234, 224 | 221, 208, 195 | 176, 162, 148 | 59300 |
| Leather wrap | 120, 97, 92 | 93, 74, 73 | 67, 53, 54 | 14039 |
| Leather belt | 114, 99, 95 | 74, 61, 63 | 59, 47, 50 | 2196 |
| Loincloth | 67, 68, 85 | 59, 58, 72 | 40, 40, 52 | 17725 |
| Buckle stone | 175, 167, 169 | 102, 98, 104 | 92, 90, 97 | 3880 |
| Club stone | 202, 192, 189 | 145, 137, 139 | 105, 102, 110 | 31295 |
| Club haft | 123, 97, 87 | 98, 77, 72 | 70, 54, 51 | 6984 |
| Club strap | 109, 91, 89 | 77, 62, 62 | 67, 53, 53 | 9610 |
| Eye sclera | 248, 254, 255 | 234, 248, 254 | 213, 228, 243 | 448 |
| Iris | 117, 229, 244 | 70, 192, 219 | 21, 93, 121 | 187 |
| Tusk | 248, 237, 224 | 234, 221, 206 | 185, 173, 166 | 247 |
| Foot skin and nails | 172, 186, 209 | 140, 160, 189 | 76, 101, 139 | 17022 |
| Snow ground | 238, 241, 252 | 231, 235, 249 | 215, 224, 247 | 52800 |

The skin reads cool periwinkle-slate throughout. The texture carries broad
painterly patches: each planar facet has its own tone, with lighter dabs and
soft cavity shadows. Fur is warm off-white with grey-brown shadow. Leather is a
warm dark brown with light worn scratches on the edges. The loincloth is a
cooler, darker purple-brown.

## Key landmarks (pixels)

| Landmark | x, y | Landmark | x, y |
| --- | --- | --- | --- |
| Head top | 541, 185 | Chin bottom | 545, 371 |
| Eye centre | 542, 263 | Brow notch | 539, 240 |
| Ear R / L | 463, 266 / 624, 252 | Mouth corners R / L | 497, 330 / 600, 322 |
| Tusk tips R / L | 508, 298 / 583, 290 | Sternum top | 505, 420 |
| Navel | 487, 690 | Buckle centre | 487, 766 |
| Right elbow / wrist | 224, 606 / 177, 781 | Right fist centre | 180, 835 |
| Left wrap centre | 947, 810 | Left fist centre / bottom | 928, 960 / 960, 1046 |
| Knee R / L | 400, 1010 / 745, 1040 | Loincloth flap tip | 548, 1090 |
| Club stone centre | 193, 1143 | Club stone bottom | 215, 1300 |
| Toe front R / L | 395, 1248 / 760, 1290 | Mantle outer tips R / L | 222, 405 / 981, 440 |

## Silhouette mask (`reference_mask.png`)

Made by `measure_reference.py` with OpenCV GrabCut:
1. Initialise with a rectangle (x 40..1065, y 175..1310) and run 8 iterations.
2. Force the eye to foreground (GrabCut otherwise classes the white sclera as snow), then run 4 more iterations.
3. Remove islands under 400 px and fill holes under 400 px.

The RNG seed is fixed, so the mask is reproducible. The edges were checked in zoomed overlays: the gaps between the arms and torso, the crotch gap, the feet, the club and the far arm.
