# Pharaoh reference: study notes

The source image is `Pharaoh_Reference.webp`. It is 1086 × 1448 RGB, SHA256
`BDB705682E45F1C0B2C9BF03BE73091A6C3202D56C4F90FA904E8B1E79253D8A`, and is stored
unchanged. All pixel coordinates below are measured on it: x runs right, y runs
down, origin at the top-left.

"Viewer-left" is the character's **right** side. The staff hand is his right
hand.

## Camera and scale

The camera is a front view from a low position, looking slightly up.
`camera_solve.py` solves it from landmarks; see `camera_solve.json`.

| Quantity | Value | How it is known |
| --- | --- | --- |
| Focal length | 2232 px, which is 55.5 mm on a 36 mm sensor fitted to the 1448 px height | ground-contact rows and ankle-band size ratio, anchored by the 12.5-stud headdress |
| Camera height | 3.24 studs (about knee height) | ground points plus horizon prior |
| Pitch | 7.1° upward | horizon at row ~1000, just above the far sand line at ~1095 |
| Distance | 24.0 studs to the pelvis plane | depth priors; this is the least certain value (σ ≈ 7) |
| Scale at the pelvis plane | ≈ 94 px/stud | |

Evidence that the camera is low:

- The belt's top edge arches upward: row 662 at the centre, 672 at the ends.
- The left bracer's rims arch upward too.
- The undersides of the nemes wings are visible.
- The staff-foot block still shows a thin top sliver, so the camera is above 1.15 studs.

The left ankle band is 210 px wide and the right is 188 px, so the left foot is
about 11.7 % closer to the camera. The left sole is also 42 px lower in the
frame. Both mean the left foot is planted forward.

The pelvis is yawed about 13° toward his right. The gem sits at x = 524 while the
belt silhouette's midpoint is at 556. The chest and head face the camera; the
skull's midline is at 550.

The head is rolled about 1.5°. The viewer-right stripes and eye sit 3 to 12 px
higher than the viewer-left ones.

## Landmarks (px)

| Landmark | x | y |
| --- | --- | --- |
| Uraeus top (top of headdress) | 545 | 139 |
| Nemes crown (top of dome) | 548 | 156 |
| Nemes wing, outer-bottom corner L / R (viewer) | 353 / 751 | 378 / 372 |
| Brow band (gold) | 474–628 | 225–248 |
| Skull outer width at cheek | 474–628 | 300 |
| Brow slab tops, outer / inner | (486,244) (543,254) · (612,239) (555,253) | |
| Eye glow centres | 519.5 / 580 | 280.5 / 277 |
| Eye sockets | 496–539 / 560–605 | 264–292 / 261–290 |
| Nasal cavity | 538–562 | 278–302 |
| Upper teeth row | 522–583 | 317–329 |
| Lower teeth row | 522–583 | 329–339 |
| Chin bottom | 550 | 361 |
| Collar outer bottom (front centre) | 548 | 540 |
| Lappet bottoms L / R | 452 / 645 | 523 / 505 |
| Deltoid outer silhouette R / L | 237 / 930 | 470 / 450 |
| Chest-band crossing | 545 | 580 |
| Belt | 393–720 | 662–760 |
| Belt rims: top / brown band / bottom | | 662–688 / 688–735 / 735–760 |
| Gem centre, radius | 524, 713 | r ≈ 31 (setting ring r ≈ 44) |
| Medallion plate | 463–592 | 661–761 |
| Centre apron tip (gold chevron point) | 521 | 1052 |
| Cream under-apron tatters, lowest | ~515 | 1140 |
| Blue back tail tip (between legs) | 624 | 1146 |
| Right fist centre / thumb | 160, 612 / 228, 565 | |
| Right cuff front ellipse | 72–255 | 575–770 |
| Left bracer | 810–1025 | 660–870 |
| Left hand, fingertips lowest | 940 | 1031 |
| Ankle band L (centre, width) | 778, 1178 | 210 wide |
| Ankle band R (centre, width) | 377, 1162 | 188 wide |
| Toe fronts, bottom L / R | 843 / 300 | 1360 / 1318 |
| Staff foot, bottom centre | 207 | 1340 |
| Staff hook top / tip | 165 / 258 | 50 / 275 |

## Part inventory

### Head

- **Skull.** Bone-beige with a grey-green cast, carved as large planar facets.
  - Two heavy brow slabs slope down toward the centre in an angry V.
  - Deep dark sockets. Each holds a glowing eye: a white core (250, 252, 254) inside a cyan halo (138, 189, 198). Glow core is about 21 × 13 px.
  - Inverted-heart nasal cavity.
  - Angular cheekbones.
  - A chunky maxilla, and a separate jaw block with a squared chin.
  - 5 upper teeth (4 large, plus a small one on the viewer-right) and 6 lower teeth, set in a dark mouth frame.
- **Neck.** Thick grey-green skin, visible between the jaw and the collar (y 360–420).
- **Uraeus.**
  - A gold cobra rising from the centre of the brow band.
  - Hood outline x 510–579, top at y 139.
  - Head with 2 dark eyes.
  - About 6 horizontal belly-scute ridges down the hood front.
  - The neck plugs into the brow band.
- **Nemes.**
  - **Dome.** 7 radial stripes: B G B **G (centre, under the cobra)** B G B.
  - **Brow band.** Gold, spanning the forehead.
  - **Wings.** Each flares from the temple to an outer-bottom corner. Each has a front face and an outer bevel face; the crease is at x ≈ 430 on the left.
    - Horizontal wing stripes below the corner blue: **G, B, G, B**.
    - Left wing (x = 420): G 243–276, B 280–311, G 315–349, B 353–377.
    - Right wing (x = 690): G 234–264, B 267–299, G 302–335, B 338–372.
    - A thin dark line separates every stripe. Wing undersides are visible.
  - **Lappets.** One hangs in front of each shoulder, each with 4 stripes: **G, B, G, B**.
    - Left (x = 452): G 383–411, B 414–443, G 447–481, B 484–520.
    - Right (x = 645): G 370–394, B 398–425, G 429–460, B 463–501.
    - The right lappet is shorter.
  - **Back.** Not visible; authored as a striped back flap plus a tapered tail (queue).

### Usekh collar

Three concentric segmented rings lie over the shoulders and chest, partly hidden
by the lappets:

1. **Inner gold ring** around the neck: about 16 tiles all the way round, 5 visible between the lappets.
2. **Middle ring**: tiles alternate royal blue and slate grey-blue (88, 95, 107). About 16 tiles round, 4 visible between the lappets.
3. **Outer gold ring**: wider, about 20 tiles round, 6 visible between the lappets. It sweeps up over both shoulders; its outer lip is a raised rim.

Dark grooves separate the tiles.

### Body

- **Skin.**
  - Olive grey-green stone-like skin: lit (180, 169, 132), mid (129, 117, 84), shadow (72, 64, 41).
  - Large soft planar facets, a few dark chips and scuffs, painterly low noise.
- **Build.** Hulking brute.
  - Very broad deltoids.
  - Huge pectorals under the chest X-bands.
  - A row of blocky abs between the bands and the belt.
  - Thick arms and legs.

### Bandages

Cream linen: lit (253, 232, 197), mid (206, 177, 138), shadow (162, 131, 90).
The strips have visible thickness, a soft dark overlap line along their edges,
faint lengthwise streaks and sparse dark flecks.

- **Chest.**
  - Two wide straps (about 50 px) cross in an X at (545, 580).
  - The "/" strap (upper-right to lower-left) lies on top.
- **Right shoulder and upper arm.**
  - About 3 wraps around the deltoid, running diagonally.
  - About 3 more around the upper arm and elbow.
- **Right wrist.**
  - One wrap inside the cuff.
  - One around the forearm behind the cuff.
- **Left shoulder.**
  - 2–3 wraps.
  - One torn end hangs from the shoulder wrap at about (808–892, 460–535). This is **trailing end #1**.
- **Left upper arm and elbow.** About 4 wraps, crossing diagonally.
- **Left hand.**
  - About 2 wraps over the wrist and palm, below the bracer.
  - A frayed end at the wrist (1000, 900). This is **trailing end #2**.
- **Thighs, knees and shins.**
  - Right leg: 3–4 crossing strips at y 1025–1140.
  - Left leg: an X of 2 diagonal strips plus 1 horizontal strip at y 990–1145.
- **Feet.**
  - Each foot has two strips crossing over the instep.
  - One horizontal strip runs across the toe roots.
  - Torn ends on the outer side of the left foot. This is **trailing end #3**, at the left heel.

### Belt

- A gold top rim, a brown recessed band (149, 103, 45), and a gold bottom rim.
- At the centre, a gold medallion plate shaped as an irregular octagon, wider than tall.
- A raised gold setting ring holds a round blue gem: mid (46, 95, 133), lit (90, 139, 179).
- The gem is cut as a low cone with about 10 radial facets. Its highlight is at the upper right.

### Shendyt kilt (layers, front to back)

1. **Centre apron.**
   - Royal blue, framed by thin gold side trims.
   - Ends in a gold chevron with engraved V lines; the point is at y 1052.
2. **Cream flanking strips.**
   - One each side of the apron, x 433–480 and 571–608.
   - Long, with pointed, torn ends reaching y ≈ 1140.
3. **Cream under-apron tatters.** These hang below the chevron to y ≈ 1140.
4. **Blue side panels.**
   - Left: x 299–455, y 752–896. Right: x 617–799, y 746–915.
   - The lower edge of each is framed by a diagonal gold border.
5. **Cream linen skirt.**
   - Under the side panels, with a saw-tooth torn hem.
   - Its teeth reach y ≈ 960 at the sides.
6. **Inner blue panels.**
   - Between the cream strips: left x 380–461, right x 599–667.
   - Each has a gold hem; they end at y ≈ 1003 and 1015.
7. **Dark-blue back tail.** Visible between the legs; its tip is at (624, 1146).

### Arm bands

- **Right wrist cuff.**
  - A big gold ring cuff seen almost end-on, with the forearm pointing at the camera.
  - About 4 segment lines are visible on its outer cylinder.
  - Slate-blue inlay shows only at its far outer edge.
- **Left forearm bracer.**
  - A tapered gold cylinder with a top rim and a bottom rim.
  - The middle band has alternating gold and royal-blue vertical panels, 2 blue visible, so about 6 all round.

### Ankle bands

Plain chunky gold rings. The right one is in shade.

### Hands

- **Right fist**, gripping the staff:
  - Three chunky finger rows, each a knuckle block plus a middle-phalanx bar across the front of the shaft.
  - The thumb wraps over the top (228, 565) and shows a square nail.
  - A 4th finger is not visible.
- **Left hand**, open and clawed, fingers curled down:
  - The thumb points down and out on its own, with 2 segments.
  - 3 fingers are visible, each with 2–3 blocky segments. A 4th is hidden behind.

### Feet

- Wrapped, with blocky toes.
- Left foot: 3 large toes visible, plus a 4th partly under the wrap. The toe tops show a rectangular nail groove.
- Right foot: turned out, with 2–3 toes visible.

### Staff (heka crook)

The staff has a square section with chamfered edges, about 56 px wide (≈ 0.55
studs) and constant along its length. It leans outward at the top by about 3.5°
in the image.

- **Shaft bands, top to bottom (y px):**

  | From | To | Band |
  | --- | --- | --- |
  | … | 296 | G |
  | 298 | 344 | B |
  | 347 | 413 | G |
  | 415 | 464 | B |
  | 467 | 532 | G, running into the fist |
  | 687 | 739 | G |
  | 742 | 797 | B |
  | 800 | 939 | G |
  | 942 | 996 | B |
  | 998 | 1228 | G |

  The foot block follows at 1228–1340.
- **Crook.** A polygonal arc from (55, 165) over a top at about (165, 50) down to the tip at (258, 275).
  - Band sequence up the arc: gold, blue, gold, gold, blue, gold, blue, then a gold tip.
- **Foot block.** A square gold frustum, rotated about 40° about vertical. Top 172–247, bottom 155–260, height 1228–1340. It has a chamfered top and faint engraved V marks.

### Ground

Sand: (251, 200, 129). The cast shadows fall toward the lower-left and slightly
toward the camera, so the sun is high and to the upper right, behind the
character's left shoulder, and a little in front.

## Colour table (sRGB, eyedropped)

Pixels were class-filtered inside region boxes (`eyedrop` rules in
`compare_reference.py`). Lit = the top 8 %, mid = the 25–75 % luminance band,
shadow = the bottom 10 %.

| Material | Lit | Mid | Shadow |
| --- | --- | --- | --- |
| Skin | 180, 169, 132 | 129, 117, 84 | 72, 64, 41 |
| Skull bone | 222, 205, 167 | 146, 135, 104 | 72, 62, 40 |
| Bandage | 253, 232, 197 | 206, 177, 138 | 162, 131, 90 |
| Gold | 253, 211, 110 | 196, 141, 59 | 129, 84, 28 |
| Royal blue | 101, 114, 171 | 62, 79, 123 | 30, 46, 74 |
| Belt brown | 186, 133, 61 | 149, 103, 45 | 103, 65, 24 |
| Gem | 90, 139, 179 | 46, 95, 133 | 36, 75, 102 |
| Slate collar tile | 126, 138, 138 | 88, 95, 107 | 44, 47, 61 |
| Eye glow core / halo | 250, 252, 254 | — | 138, 189, 198 |
| Teeth | 217, 194, 153 | — | — |
| Sand | 254, 214, 147 | 251, 200, 129 | 245, 194, 124 |

## Reference mask

`reference_mask.png` is built by `../make_reference_mask.py`. It uses OpenCV
GrabCut seeded with a hull and scribbles, drops small islands, and fills small
enclosed holes. Contour overlays were inspected at 1.1–1.8× zoom on every edge
region. The figure plus the staff covers 754,737 px.
