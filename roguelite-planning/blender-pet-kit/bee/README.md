# Bee (Rare, strong suit: poison)

Chibi hovering bee: big round head with big glossy painted eyes (two catchlights), two short thick
antennae with round amber tips (fused into the head), a round fuzzy striped body (honey yellow and dark
brown, soft fuzzy stripe edges, a few broad fuzz lumps only), thick rounded pale wings that pivot at the
root, tiny stubby legs, a small rounded stinger and the Rare charm: a tiny honey jar with a painted green
(poison) honey drip, hung from a leather cord.

Style notes (owner feedback after the dog): coarse, even, flat-shaded facets (about 4.7k triangles total,
decimated to a uniform mesh, symmetric where the part is symmetric), painterly brush-stroke texture with
2-4 value ranges, baked AO + soft key + cool rim, warm shadows. No glow, no Neon (Rare).

`build_bee.py` is self-contained (adapted from the Bunny/Golden Retriever pipeline). Rebuild:
`"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --threads 2 --python build_bee.py`
(`-- --quick --out <dir>` for a fast iteration without exports). Check: `... --python validate_exports.py`.

## Rest pose and hover

The model is authored AT REST: lowest point (the jar) at Blender z about 0.02, facing -Y (Studio -Z), the bee's left
is Blender +X. The game lifts the Body root by `hover.hover_height_studs` = 1.2 (plus a 0.10 stud sine bob,
period 1.4 s). Body height 1.16 + hover 1.2 = 2.36 studs overall. Wings rest 38 deg above horizontal, swept back 22 deg.

## Parts (Studio axes = (-x, z, y) of Blender; pivots relative to the model origin)

| Part | Tris | Pivot (Studio) | Parent | Motion |
|---|---|---|---|---|
| Bee_Body | 1498 | (0, 0.52, 0.20) | root | lift + bob in Y, pitch about X for the dive |
| Bee_Head | 1500 | (0, 0.55, -0.10) | Body | nod / tilt / look through the neck |
| Bee_WingL | 340 | (-0.10, 0.80, 0.12) | Body | flap = rotate about Studio Z (+ = down) |
| Bee_WingR | 340 | (0.10, 0.80, 0.12) | Body | flap = rotate about Studio Z (+ = up, mirror) |
| Bee_Stinger | 88 | (0, 0.44, 0.74) | Body | pitch about X, -135 deg aims it down for the sting |
| Bee_LegL | 180 | (-0.20, 0.30, 0.10) | Body | dangle (three stubs move together) |
| Bee_LegR | 180 | (0.20, 0.30, 0.10) | Body | dangle |
| Bee_Jar | 620 | (0, 0.40, -0.12) | Body | pendulum about X through the cord top (inside the chest) |

Total 4746 triangles, one 1024 atlas (`textures/bee.png`), every mesh well under 20k. Width 1.31, length 1.73
(with stinger), height 1.16 at rest.

## Locomotion (in `studio-install-data.json`)

`"locomotion": "hover"` with `hover`: hover height, bob, wing flap (about 12 Hz; WingL up -30 / down +62,
WingR mirrored, as deltas from rest) and frames `hover_mid`, `wings_up`, `wings_down`, `sting_windup`,
`sting_dive` with Blender and Studio joint angles. Sting dive: body 38 deg nose-down, head -18, stinger -135,
wings swept back and up, legs tucked a little, jar swung forward; the stinger then points about 17 deg forward
of straight down.

`previews/pose-check.png` shows wings up, wings down, wind-up and dive: no gaps at the neck, wing roots,
stinger, legs or jar cord in any of them.

Blender-verified (FBX + GLB re-import, `validation-report.json`), Studio untested.
