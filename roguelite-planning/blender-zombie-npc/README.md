# First zombie NPC character

One segmented zombie based on the user's reference image `codex-clipboard-ab2be93a-8db7-4a6c-9c84-8b7182d7b537.png`. Original low-poly geometry and a baked, mottled color atlas evoke the painted environment style. The face includes recessed-looking eyes, pale irises, heavy brows, four teeth, and angular brown hair. The clothing includes collar panels, torn hems and sleeves, exposed knees, and chunky boots.

## Deliverables

- `Zombie_R15.blend`: editable character, 16-bone armature, packed texture, preview scene, and joint mobility check action.
- `Zombie_R15.fbx` / `Zombie_R15.glb`: 15 separately named, rigid-skinned meshes and armature; no final animation clips.
- `Zombie_R15_Parts.fbx`: separate unskinned sections for a Motor6D NPC assembly.
- `textures/Zombie_Color.png`: shared 2048 x 2048 color atlas.
- `Zombie_Preview.png`: actual Blender render.
- `rig_manifest.json`: exact geometry, joint locations, dimensions, and hierarchy.
- `verification.json`: independently reopened Blender/FBX/GLB results.
- `assemble_npc.luau`: Studio helper for a selected Parts FBX import. Creates a new `Zombie_NPC` with Humanoid, Animator, 15 Motor6Ds, and pelvis HumanoidRootPart. Root remains anchored for editing.

## Rig and animation

The 15 sections are Head, UpperTorso, LowerTorso, and left/right UpperArm, LowerArm, Hand, UpperLeg, LowerLeg, Foot. There is one rigid vertex group per section and a HumanoidRootPart root bone at the pelvis. Geometry height is approximately 6.79 authoring units. All section pivots are at their proximal joints. Internal detail shells are deliberately joined to their corresponding articulated section.

The Blender `Joint_Mobility_Check_NOT_FINAL_ANIMATION` action exercises joint rotation. It is a technical pose check, not a finished idle/walk/run/attack/hit/death set. Those six animations can now be authored on this rig. This is a custom NPC body; it is not certified as a Marketplace avatar or a drop-in fit for arbitrary stock R15 animations.

For a Motor6D NPC, import the Parts FBX upright and run the supplied assembly helper on that selected model. The helper accounts for standard importer scale, creates joints from the authoring coordinates, and leaves the NPC root anchored. Validate facing, joint axes, hip height, collisions, and Animation Editor playback in Studio before releasing the root and adding enemy behavior. The Studio helper and live character behavior have not yet been tested in Studio. No existing Studio scene was changed for this modeling request.

## Validation

Blender master and rigged FBX/GLB are checked for 15 meshes, 16 bones, loaded textures, bounded UVs, normalized weights, nonzero faces, closed detail shells, ground contact, and functioning elbow movement while the opposite foot remains still. See `verification.json` for actual results. Scripts rebuild and verify the asset using Blender 5.2.

Roblox references: https://create.roblox.com/docs/art/modeling/rigging and https://create.roblox.com/docs/reference/engine/classes/Humanoid
