# Boxing Gloves

Two independent unparented meshes, LeftGlove and RightGlove, each with its own wrist pivot. The root files show the review pair. Use components/LeftGlove/Model.blend, Model.fbx, Model.glb and components/RightGlove/Model.blend, Model.fbx, Model.glb for individual imports. Each standalone file contains exactly one glove mesh with wrist center at the origin.

Editable low-poly reference reconstruction. Export files contain only asset geometry. Model.blend contains a packed 320px portable color atlas and a separate review collection. Preview.png and Alternate.png are real Blender Cycles renders. Named pieces or vertex groups retain editing access. Palette UV islands overlap intentionally by color.

Rebuild: Blender 5.2 --background --threads 4 --python ../../batches/juggler_utility/build_utility.py -- 19

Hidden surfaces and thickness inferred from the single view. Assembled parts intentionally overlap at joints. No rig or gameplay; no Roblox Studio import/validation. See validation.json for topology, texture, and actual FBX/GLB reimport checks.
