# Hammer Brute: reference notes

Source: `boss-reference.png`, 1086 × 1448 RGB, copied unchanged from `../hammer-boss/source/`, SHA256
`B401488FE31019B7D2179CBCF652D17082BA92E1B5ED7AD2BF2D5A64736CA6F6`.
Coordinates are reference pixels (x right, y down). "Right" and "left" are the character's own sides: his right is on the viewer's left. Landmarks were read off ruled, zoomed crops; the full table is in `reference_measurements.json` and drawn on `../_work/Reference_Landmarks.png` by `measure_reference.py` (a local diagnostic, not committed).

## Camera and figure

- A level, slightly high view from the front (`camera_solution.json`): f = 2238 px (55.6 mm on a 36 mm vertical sensor), pitch −0.14°, yaw 1.19°, camera height 6.7 studs, RMS reprojection 1.9 px. Absolute scale: the back edge of the crown is 13.7 studs above the ground.
- The figure's bounding box (mask) is x 31–1046, y 214–1278: the hammer reaches nearly the full width.
- Stance: wide. The right leg stands under the hip; the left leg is spread out and forward with the toes turned out. The left foot's sole edge is 38 px lower than the right's, which puts it about 1.9 studs closer to the camera.
- The head is tilted forward (its flat top shows), turned a little toward his right and rolled (his left eye is higher).

## Part inventory

| Part | Count / description |
| --- | --- |
| Head | A blocky skull with a flat top, about 2.15 studs wide; it sits low between the high traps. |
| Brow | A heavy angular ridge in an angry V, with forehead furrows and frown lines (painted). A scar crosses the brow. |
| Eyes | 2 white glowing discs (no pupils) in dark sockets. |
| Nose | A skull-like inverted-V nasal cavity, dark (painted). |
| Mouth | An open snarl, dark inside, about 60 % of the head width. About 3–4 square upper teeth and 2 lower, uneven and broken, with gaps. |
| Wounds | A bleeding gash on the upper forehead (his left) with blood running down the left side of the face; red wound patches on both deltoids, the left forearm, the right forearm and the belly (3). |
| Shoulders and arms | Huge segmented rounded blocks: deltoid, upper arm, elbow/upper forearm, lower forearm, then a big closed fist. The arms hang at the sides with the elbows out. |
| Fists | 2 closed fists (about 2.1 studs wide, 2.3 tall) on the haft, knuckles forward. The left fist holds the haft just short of the butt end. |
| Belly | One huge round projecting belly (about 6.4 studs wide) with a navel pit. |
| Tank top | Torn cream tank top over the chest; a V/scoop neckline between the suspenders; the ragged hem crosses the upper belly and drops down its sides. Blood stains with small holes on the chest. |
| Suspenders | 2 dark-brown straps from the shoulders down the chest and the sides of the belly, 2 square iron buckles at the upper chest (about 0.8 studs). |
| Sash | A maroon cloth band under the belly with a torn tail hanging at the front left. |
| Trousers | Ragged charcoal / blue-grey trousers to mid-calf with torn hems and holes showing green skin (left thigh/knee, right knee). |
| Feet | 2 green block feet, about 2.8 studs wide, no toes. |
| Hammer | A huge beveled dark-iron head (about 3.2 along the haft × 4.6 tall × 2.5 deep) with a raised square plate on the side face, a square boss on the outer cheek, chipped light edges and blood stains; a wooden haft (about 0.72 thick) with 3 dark iron bands near the left hand; total length about 13 studs. |

## Colours (sRGB, region box + colour rule; mid = 45–55th luminance percentile)

| Region | Mid | Pixels |
| --- | --- | --- |
| Skin, belly | 110, 152, 64 | 38149 |
| Skin, left deltoid | 104, 151, 54 | 20525 |
| Skin, right upper arm | 130, 178, 73 | 9238 |
| Skin, left forearm | 129, 177, 69 | 11521 |
| Skin, forehead | 169, 209, 97 | 6344 |
| Skin, left foot | 104, 153, 51 | 10178 |
| Tank top | 182, 156, 132 | 11822 |
| Suspender | 88, 72, 76 | 2351 |
| Buckle | 109, 100, 104 | 2476 |
| Sash (in the belly's shadow) | 37, 14, 22 | 1237 |
| Trousers, lit left thigh | 67, 59, 68 | 4919 |
| Hammer iron | 74, 66, 69 | 30338 |
| Haft wood | 67, 40, 28 | 3768 |
| Iron band | 73, 54, 58 | 1684 |
| Wound on the left deltoid | 165, 64, 58 | 2251 |
| Eye | 225, 228, 228 | 217 |
| Teeth | 210, 208, 189 | 291 |
| Lawn | 163, 234, 86 | 61600 |

The skin is a mottled yellow-green with three broad value ranges, lighter facets toward the light, and many clustered dark-green speckles (about 0.05–0.15 studs). The iron reads dark grey with clearly lighter chamfers.

## Silhouette mask (`reference_mask.png`)

Made by `measure_reference.py` with OpenCV GrabCut, because the green skin stands on a green lawn:
1. Initialise with a rectangle (x 20..1070, y 200..1280), 6 iterations.
2. Add hand-placed seed strokes: definite foreground down the body, limbs, fists, feet, hammer and haft; definite background on the open lawn below and between the feet, the sky, the far cliffs and a background log behind the hammer.
3. 6 more iterations with the mask, then islands under 400 px removed and holes under 400 px filled.

The RNG seed is fixed, so the mask is reproducible. It was checked against the reference at half scale (feet on the lawn, the gaps between arms and belly and between the legs, the haft and its butt end).
