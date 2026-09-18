# Glock — one-item reference modeling trial

Status: **Awaiting the user's explicit visual approval.** No other item models or subagents were started.

The supplied `Reference.png` is the modeling reference. The asset was built directly in Blender from polygon profiles, a closed trigger-guard ring, single-segment bevels, a recessed octagonal muzzle, raised sights, rear serrations, and small side controls. The surfaces use restrained warm-charcoal color variation baked into one base-color texture. This is an external game prop with no functional internal mechanism.

## Review

- `Glock_Reference_Test.blend`: actual editable Blender file, with packed texture and three review cameras.
- `Glock_Comparison.png`: render of the model from a front three-quarter angle.
- `Glock_Side.png`: orthographic side profile for checking proportions and the trigger opening.
- `Glock_Reverse.png`: opposite three-quarter view.
- `Reference.png`: unmodified copy of the supplied reference.

The neutral review ground, lights, and cameras are in a separate collection and are excluded from asset exports. These are Blender renders, not generated images or a pasted reference.

## Asset exports

- `Glock_Reference_Test.fbx`: one mesh, one material, embedded base-color texture.
- `Glock_Reference_Test.glb`: portable one-mesh preview/export with embedded texture.
- `Glock_BaseColor.png`: 1024 x 1024 texture, packed into the blend file as well.
- `validation.json`: actual topology and dimension measurements from the final Blender build.

Coordinates: barrel points along Blender -X; Z is up. Grip-center pivot. These are stylized asset units, not real-world manufacturing dimensions; set the game scale when importing into Roblox. Separate closed component shells intentionally overlap as a normal game prop assembly; it is not a single Boolean solid.

The reverse side, top, and hidden depth are inferred from the one supplied image. No logos, text, realism details, or extra accessories were added. Roblox Studio import and in-game appearance have not been tested; this first task is the Blender visual-quality gate.

`build_glock.py` reproduces the model and exports using Blender 5.2 in a separate background process, without modifying another open Blender scene. Final GLB/FBX reimport results are in `export_validation.json`.
