# King Crab reference — notes

`king-crab-reference.webp`: the user's image, copied unchanged. 1536 × 1024 RGB,
SHA256 `575CB191413641ADF4A03A39C19750BEDF81F21E1B5873E85A56B23E18A7C261`.
It shows a low front-three-quarter view of the crab on a beach, with cliffs
and sea behind. Everything below was read off the full-resolution image and
zoomed, gridded crops. Pixel coordinates are (x right, y down).

## Part inventory

| Part | What the image shows | Count |
| --- | --- | --- |
| Carapace | Broad faceted shield, roughly hexagonal in plan. Steep front face between the eyes and a large lit top plane sloping down toward the face. Thin rim band along the sides ending in pointed lateral corners | 1 |
| Spikes | Pyramidal, 4-sided: a tall pair, a small outer pair, one broad low spike on the midline behind them | 5 raised spikes + 2 pointed rim corners |
| Brows | Chunky blocky bars in an angry V. Each ends in a short drop at the inner end, like a hockey stick | 2 |
| Eyes | White spheres with round black pupils. The viewer-left eye is drawn larger (32.5 px vs 28 px radius at almost the same depth) and glances inward; the viewer-right eye looks at the camera | 2 |
| Eye stalks | Short red stalk, a red collar ring, a beige cup at the base, rising from a dark pit under the carapace edge | 2 |
| Central mouth plates (maxillipeds) | Heavy shield/tooth shapes hanging from under the front edge, a narrow gap between them. A small red nick on top of the viewer-left one | 2 |
| Flanking mouth plates | Trapezoids either side of the teeth, red carapace paint running down over their tops | 2 per side |
| Mouth cavity | Dark brown void behind the teeth | 1 |
| Sternum (belly) | Beige plates in arcs concentric with the mouth, rows smiling upward at the sides | 3 rows (about 5 / 4 / 3 plates) |
| Crusher claw (crab's right, viewer's left) | Giant rounded, faceted crescent palm nearest the camera. Heavy fixed finger sweeping round its lower lip. Big beige movable finger with a pointed tip. Large cream wear chips on the top edge, outer face and bottom | palm, 2 fingers, about 3 large chips |
| Cutter claw (crab's left, viewer's right) | Slimmer palm. Long curved red hooked fixed finger with small serrations on its inner edge. Beige movable finger with a serrated cutting edge | about 6 serrations on the hook, about 4 on the finger, 2 chips |
| Claw arms | Red merus and carpus, beige bands at the elbow and wrist | 2 bands per arm |
| Walking legs | Red merus, a beige joint ring, red carpus, a beige pointed dactyl planted in the sand. Far-side legs are drawn slimmer | 4 per side (anatomy). Visible: crab-right R1 fully, R2 tip only (under the crusher); crab-left L1, L2 fully and a rear leg (L4) under the belly |
| Ground | Warm sand, soft cast shadow falling to the viewer's left and back | — |

## Colours (sRGB, eyedropped in boxes: mean, and 10th/90th percentiles where useful)

| Material | Lit | Mid | Shadow |
| --- | --- | --- | --- |
| Carapace red-orange | 241,116,81 (p90 255,141,107) | 231,107,75 | 172,90,67 (p10 126,47,31) |
| Brow red | 239,111,98 (p90) | 187,75,66 | 107,38,36 (p10) |
| Crusher shell | 243,116,84 | 167,60,55 | 142,50,47 |
| Cutter hook | 220,82,67 (p90) | 198,73,56 | 147,62,33 (p10) |
| Leg shell | 215,87,74 | 192,76,66 | 138,48,43 (p10) |
| Beige fingers | 214,178,143 (p90 254,224,182) | 219,177,135 | 160,130,103 (p10) |
| Beige teeth | 217,168,124 | 208,158,110 | 151,108,74 (p10) |
| Sternum plates | 152,114,83 (p90) | 134,99,70 | 113,84,51 (p10) |
| Leg tips | 242,200,154 (p90) | 179,142,108 | 145,112,80 (p10) |
| Cream chips | 248,209,177 (p90) | 234,191,160 | 207,136,128 (p10) |
| Eye white (with shading) | 227,190,155 (p90) | 245,218,186 (bright-pixel mean) | 174,123,86 (p10) |
| Pupil | — | 45,33,30 | 24,16,9 (p10) |
| Mouth cavity | — | 99,76,56 | 50,39,32 (p10) |
| Sand | 249,217,174 | — | 160,146,133 (cast shadow) |
| Sky | 100,185,253 | — | — |

The generator's palette (`BASE_RED`, `BASE_BEIGE` in `build_king_crab.py`)
starts from these. The per-section `CALIBRATION` gains then close the gap left
by lighting; see the README.

## Landmarks (pixels) used by `solve_camera.py`

| Landmark | Crab right (viewer left) | Crab left (viewer right) |
| --- | --- | --- |
| Eye centre | 773.5, 352.5 | 933.0, 369.5 |
| Lateral rim corner | 427, 300 | 1142, 385 |
| Tall spike apex | 637, 168 | 962, 213 |
| Small spike apex | 536, 236 | 1050, 293 |
| Eye-stalk cup | 781, 428 | 920, 438 |
| Rear midline spike apex | 797, 186 | |
| Top of the tooth gap (midline) | 850, 433 | |
| Belly bottom (midline) | 800, 625 | |
| Sea horizon | v = 440 | |

Planted leg tips: R1 (665, 835), R2 (262, 803), L1 (1116, 815), L2 (1219, 780),
L4 (864, 765). Traced knees and ankles: R1 (584, 600) / (608, 726), L1
(1088, 590) / (1120, 706), L2 (1193, 652) / (1208, 730), L4 (912, 672) /
(897, 722). Brow ends: R outer (706, 290), R inner (826, 346), L outer
(984, 320), L inner (896, 350). Worn-chip positions on the carapace: (605, 395),
(1030, 345), (1095, 385).

## Camera solve (`camera.json`)

- Method: least squares over the symmetric landmark pairs and the midline
  points. Scale comes from two anchors: the tall-spike apex at 10 studs, and
  the ground under the body centre at v = 790. The horizon fixes pitch; roll
  is 0 because the background cliffs are vertical.
- Residual: RMS 1.69 px, max 2.75 px.
- The body leans 5.86° with its right side up. The rim corners rise 85 px,
  outer spikes 57, tall spikes 45 and eyes 17 px, in proportion to their
  distance from the midline; perspective alone cannot produce that.
- Focal length: the cost is flat from 900 to 3600 px. 1900 px (44.5 mm on a
  36 mm sensor) was chosen because it gives a 12 × 9.5-stud, roughly
  hexagonal carapace and a near-mirror leg footprint.
- Camera at (−5.68, −30.67, 5.78) studs, yaw 10.07°, pitch −2.17°.

## How `reference_mask.png` was made

`make_reference_mask.py` builds the mask in five steps:
1. A generous hand-traced outline marks everything that could be crab.
2. Saturated red pixels are marked definite foreground. Hand polygons add the
   beige parts, whose colour overlaps the sand (teeth, belly, fingers, tips).
3. Hand polygons mark sand, sea and sky visible through the claw openings and
   between the legs as definite background.
4. OpenCV GrabCut refines the edges.
5. Clean-up keeps the crab components and fills enclosed pockets. Two
   pockets are real see-through gaps and stay open.

`reference_mask_review.png` outlines the result on the image. It was checked
at full size and in zoomed crops of every leg tip and both claw openings.
