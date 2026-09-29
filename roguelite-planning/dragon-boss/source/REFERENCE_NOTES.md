# Dragon reference: study notes

Reference: `source/4.webp`, 1536 × 1024 RGB, SHA256
`CD8ABD3A2B750906F0989BE291A6EE97732FDB4EBAA3234A8ACC884A12363006`, copied unchanged.
All pixel coordinates below are (u, v) in that image and were read off 2-4× gridded crops.
"Near" means the dragon's left side (viewer's right), "far" means the dragon's right side.

## Scene and camera

- Low front-¾ view on a cracked grey stone floor, lava falls and grey cliffs behind, dusky pink-lilac sky.
- The painted verticals (cliff pillars, lava falls) do not converge, but the horizon is low: the claw rows put it at
  v ≈ 818. That is a level camera with a vertical lens shift (see `solve_camera.py`, `source/camera.json`).
- Key light is warm and comes from camera-left and above: lit planes face the viewer's left, and cast shadows fall
  to the right and back. There is lilac sky fill on the upward faces, and an orange lava bounce on the tail and wing
  edges.

## Part inventory (counts)

| Part | Count / description |
| --- | --- |
| Horns | 4 visible, all charcoal obsidian and faceted. Per side there is one huge swept-back horn from the rear of the skull. The near one runs from base (575, 215) to tip (724, 91) and is about 80 px thick at the base. The far one runs from (450, 200) to (541, 94). There is also a smaller horn above the brow: near tip (560, 145), far tip (405, 160). Low crest scales sit between them. |
| Eyes | 1 visible (near): a glowing orange-yellow almond at (478, 240) with a dark rim, deep under a heavy brow block. |
| Brow | A heavy angry red block over each eye, sloping down toward the snout (V). |
| Snout | Long and blocky. It ends in a rounded nose knob with the nostril on its upper front at (358, 256) and (409, 252). The top plane is lit orange. |
| Lower jaw | Beige and massive (underbite). It is built from a front chin block (355-470) and a rear block reaching (565, 375), and continues into the throat plates. |
| Teeth | 3-4 visible on the near side: a big tusk (425-445, 270-318) standing up in front of the lip, a small tooth (455-470, 285-315), a tiny front tooth (385, 300) and one at the mouth corner. The mouth corner glows orange (fire inside). |
| Neck spikes | 3 big blocky obsidian spikes between the head and the wing root: (650-720, 200-300), (700-780, 270-345) and (760-820, 320-370). |
| Back and tail spikes | About 9 more down the hips and tail, shrinking toward the tip: (880-940, 455-510), (915-975, 465-520), (970-1030, 525-580), (1025-1090, 585-640), (1080-1140, 635-690), (1150-1200, 660-705), (1210-1260, 672-720), (1260-1310, 695-730), (1300-1345, 698-730). The dorsal row is 12 spikes visible in total. |
| Lava glow | Thin orange seams at the base of each dorsal spike, plus a hot orange edge on the red back plates next to the spikes. |
| Plastron | Beige chevron plates. There are 2 throat plates under the jaw, then 5 big chest chevrons (the V points down, with a clear crease on the midline) and 2-3 belly rows curving under the body. The tail underside carries about 12 visible segments that narrow toward the tip. |
| Wings | 2 bat wings, raised and spread; the near wing is larger in frame. Each wing has: a thick red humerus and forearm; a wrist knob with a black thumb claw (near tip (835, 27), far tip (411, 37)); **2 long fingers**, each ending in a black claw (near (1487, 468) and (1255, 530); far (42, 466) and (212, 499)); and a membrane in 3 panels (finger 1 to finger 2, finger 2 to the arm, and the arm to the flank). The trailing edge has **2 scallops** per wing, between the finger tips and between finger 2 and the flank, and is slightly ragged. |
| Front feet | 4 toes each. Each toe has a red knuckle plate and a broad, blunt black claw (claws per foot: 4). Near-front claw tips: (749, 928), (833, 936), (911, 934), (970, 928). Far-front claw tips: (198, 899), (240, 906), (310, 911), with a fourth partly hidden. |
| Hind feet | 4 toes and 4 claws each. Near-hind claws: (993, 887), (1037, 889), (1087, 889), (1130, 884). Far-hind (3 visible): (542, 873), (574, 877), (618, 879). |
| Tail | Long, curving to the viewer's right. The red top is plated, with beige segmented plates underneath. It ends in a big chunky obsidian arrowhead: point (1480, 685), upper barb (1325, 610), lower barb (1420, 790), tail entry (1390, 720). |
| Skin plates | Large faceted scale plates, about 0.6-1.0 studs per facet, over the shoulders, forelegs, haunches and neck. The legs are thick pillars: a huge rounded shoulder or thigh mass above a heavy column and a wide splayed foot. |

## Colours (sRGB, eyedropped 7×7 medians and region means)

| Material | Lit | Midtone | Shadow | Region mean (probe box) |
| --- | --- | --- | --- | --- |
| Red skin (body) | 204, 67, 60 (shoulder) | 135, 38, 36 | 101, 30, 29 | lit 170, 55, 50; shade 121, 39, 37; tail 153, 51, 45 |
| Red skin (head) | 225, 97, 85 (brow) | 198, 62, 42 (snout) | — | 179, 63, 52 |
| Beige plates | 207, 139, 87 | 174, 110, 66 | seams ~120, 70, 44 | chest 189, 127, 83; jaw 192, 127, 80; tail underside 162, 98, 63 |
| Obsidian | 90, 69, 79 (claw facet) | 65, 48, 54 | 48, 34, 41 (horn) | claws 73, 46, 51; horns 80, 63, 73 |
| Wing membrane | 211, 93, 46 | 176, 70, 33 | 169, 63, 26 | 197, 86, 41 |
| Wing bones | 154, 62, 60 | — | — | 142, 52, 48 |
| Eye glow | 255, 206, 95 core | — | — | — |
| Lava seams | ~255, 140, 40 | — | — | — |
| Floor | far 158, 136, 142 | mid 127, 103, 109 | 79, 68, 78 | — |
| Sky | 194, 161, 167 | — | — | — |

## Landmarks used for the solves

- Camera (claw rows on the ground): see the claw tips above and `solve_camera.py` (`CLAWS`). The skull top
  (492, 198) is anchored at z = 11 studs.
- Head (`_work/head_rigid2.py`, reproduced in the README): nose top-front (362, 230), nostrils (358, 256) and
  (409, 252), near eye (478, 240), mouth corner (500, 300), chin bottom (362, 362), chin block corner (470, 365),
  jaw rear (570, 372), brow top (500, 192).
- Wings (`dragon_pose.WING_PIX`):
  - Near wing: elbow (942, 282), wrist (935, 82), thumb tip (835, 27), finger-1 knuckle (1236, 118), finger-1 tip
    (1447, 376), finger-2 knuckle (1135, 286), finger-2 tip (1240, 462).
  - Far wing: elbow (378, 445), wrist (348, 92), thumb (411, 37), finger-1 knuckle (172, 140), finger-1 tip
    (72, 392), finger-2 knuckle (257, 262), finger-2 tip (226, 428).
- Chest midline (chevron apexes): (470, 380) throat, (507, 463), (507, 552), (515, 640).

## Reference mask

`make_reference_mask.py` builds `source/reference_mask.png` (48 % of the frame) in five steps:

1. **Colour candidates:** crimson, membrane orange, and beige inside two plastron/jaw zones.
2. **Obsidian:** per-zone darkness rules, because obsidian shares its colour with the background rocks. There are
   three rules: against sky, against cliff, and against floor.
3. **Lava falls:** excluded behind both wing tips.
4. **Seeds:** hand-placed background and foreground seed polygons.
5. **GrabCut:** refines the edges. Pockets holding known background stay open.

It was checked in zoomed crops of the horns, feet, wing tips, the tail spade, the humerus gap and the gaps under the
belly (`reference_mask_review.png`).
