# Supplied-texture R15 zombie comparison

`Zombie_Blender_Provided_Textures.blend` contains the Blender comparison model, packed original head/torso/limb images, neutral preview scene, 15 body mesh objects, and a 16-bone hierarchy including HumanoidRootPart.

Run `../apply_supplied_textures.py` in Blender to rebuild from the preserved stock-rig preview. It uses the stock mesh geometry/dimensions and attachment-based joint locations recorded in `../stock_r15.json`. The head is a lightly beveled block using the recorded stock head bounds.

## Texture handling

The three user-supplied raster images are used directly, without repainting or procedural color replacement. UVs target the illustrated panel interiors, excluding background and border lines. Torso coordinates span UpperTorso and LowerTorso continuously; limb coordinates span each complete arm/leg chain. Feet sample an existing brown area of the limb image for simple shoes. The composite is a consistency reference rather than an additional material.

No separate mesh/UV template file accompanied the four supplied PNG files. Accordingly this is an explicit panel alignment, not a claim that the illustrated raster nets are unmodified official stock mesh UVs.

Follow-up corrections: upper-arm and torso shoulder tops now sample existing brown fabric panels. The head now uses a 0.23-unit, eight-segment rounded bevel within its unchanged stock bounds, per the requested classic rounded Roblox look. Its neck joint and rigid head weights are retained.

Skin coloring comes from the supplied image, including its painted variation. It has not been recolored to make every texel RGB(64,131,54).

## Verification and limits

The build asserts 16 bones, unchanged recorded stock dimensions, armature modifiers, named rigid vertex groups, and UV/material assignments on all 15 body sections. The rendered image was visually checked for readable face, supplied grime/fabric detail, intact limbs, and no hair.

This Blender file is not an already validated Roblox animation import. In-engine animation compatibility must be verified separately. No Blender NPC has been imported over the existing game zombie by this script.
