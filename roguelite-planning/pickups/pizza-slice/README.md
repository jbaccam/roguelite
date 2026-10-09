# Pizza Slice (Chef pickup)

Blender-verified, Studio untested. Not imported into Roblox Studio, not uploaded, no gameplay wiring.

One low-poly pepperoni slice for the Chef class: kills sometimes drop it and walking over it heals. It lies flat on
the ground and is meant to bob and spin from script. Matches `Reference.png` (the unmodified concept): golden crust
roll at the back, yellow cheese with soft drips over the sides, three raised flat pepperoni, tapered tip.

## Files
- `Model.blend`: editable mesh `PizzaSlice` in collection `PizzaSlice | Export geometry`, base colour packed. Camera,
  lights and floor live in `REVIEW | not exported`.
- `Model.fbx`, `Model.glb`: the mesh only (no camera, floor or lights), base colour embedded.
- `BaseColor.png`: 512x512 atlas, painted straight from the mesh (painterly low-noise breakup).
- `Preview.png`: 3/4 hero. `Alternate.png`: left, top-down as the high gameplay camera sees it; top right, side view;
  bottom right, the same top view shrunk to roughly in-game pixel sizes (112 px and 56 px) to prove it reads as pizza.
- `validation.json`: measured checks. `build_pizza_slice.py`: self-contained generator.

## Orientation and pivot
- Blender is Z-up. The slice lies on Z = 0 with the TIP toward +Y, the CRUST toward -Y and the toppings toward +Z.
- FBX/GLB export converts to Y-up, tip toward -Z (Roblox front), same convention as the weapon set.
- Origin is the area centroid of the flat bottom footprint, at ground level, so the slice sits on the floor and spins
  about its own middle. Bounds: 3.203 x 4.0397 x 0.7517 units (X wide, Y long, Z tall); lowest Z is 0.
- 1 unit = 1 stud. Designed about 2.1 long, then uniformly scaled x1.9 so the heights land at the requested
  stud values: bread + cheese about 0.4449 to 0.5102, crust crest
  0.7517 (1.574x the cheese height). Change `SCALE` in the script to rescale; scaling the MeshPart in Studio
  keeps the proportions.

## Build
1236 triangles, 626 vertices, 1 material, 1 UV map, one 512 px atlas. Bread layer, cheese, crust
roll and all four drips are one closed surface (no seams). The crust is a puffy faceted roll that overhangs the sides
at the back and takes the cheese up into it with a soft fillet. The drips hang down the bread wall (two on one long edge,
two on the other, four different lengths) as part of the same sheet, ending in rounded teardrop tips; seen from above
the outline stays a clean triangle with only slight soft bulges. The cheese top has a few broad rises and dips. The three pepperoni are separate closed bevelled discs sunk into the
cheese (intentional overlap, 180 triangles). The underside is finished (toasted bread colour,
chamfered edge). Flat shading, no normal maps, no vertex colours in the export.

Rebuild: `& "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --threads 4 --python roguelite-planning/pickups/pizza-slice/build_pizza_slice.py`

## Limitations
- Studio import, scale, texture upload and in-game look are untested.
- Colours are bright on purpose (the game adds +0.3 saturation); judge them in Play, not in Blender.
- The pepperoni overlap the cheese as separate shells rather than being welded to it.
- The cheese-top fan facets converge on the tip as long thin triangles (worst aspect about 38.8:1); flat shading hides it, but it is not an even triangulation.
- The 512 px atlas is about 47.9% used (unwrap packing); fine for a pickup this small, shrinkable to 256 px if memory ever matters.
