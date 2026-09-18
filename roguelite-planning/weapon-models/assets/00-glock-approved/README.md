# Glock — one-item reference modeling trial

Status: **Visually approved by the user.** This standardized delivery copy preserves the approved appearance and removes invisible degenerate bevel faces. The original trial files remain untouched.

The supplied `Reference.png` is the modeling reference. The asset was built directly in Blender from polygon profiles, a closed trigger-guard ring, single-segment bevels, a recessed octagonal muzzle, raised sights, rear serrations, and small side controls. The surfaces use restrained warm-charcoal color variation baked into one base-color texture. This is an external game prop with no functional internal mechanism.

## Review

- `Model.blend`: actual editable Blender file, with packed texture and three review cameras.
- `Preview.png`: approved render of the model from a front three-quarter angle.
- `Alternate.png`: orthographic side profile for checking proportions and the trigger opening.
- `Reference.png`: unmodified copy of the supplied reference.

The neutral review ground, lights, and cameras are in a separate collection and are excluded from asset exports. These are Blender renders, not generated images or a pasted reference.

## Asset exports

- `Model.fbx`: one mesh, one material, embedded base-color texture.
- `Model.glb`: portable one-mesh preview/export with embedded texture.
- `BaseColor.png`: 1024 x 1024 texture, packed into the blend file as well.
- `validation.json`: actual topology and dimension measurements from the final Blender build.

Coordinates: barrel points along Blender -X; Z is up. Grip-center pivot. These are stylized asset units, not real-world manufacturing dimensions; set the game scale when importing into Roblox. Separate closed component shells intentionally overlap as a normal game prop assembly; it is not a single Boolean solid.

The reverse side, top, and hidden depth are inferred from the one supplied image. No logos, text, realism details, or extra accessories were added. Roblox Studio import and in-game appearance have not been tested; this first task is the Blender visual-quality gate.

The original reconstruction script is `../../../item-model-test-glock/build_glock.py`; the delivery cleanup is `../../clean_approved_copy.py`. Final GLB/FBX reimport results are in `../../export_audit.json` under index 0. The delivery mesh has 2,344 triangles.
