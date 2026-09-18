# Wrecking Ball — rigid swing rig

Model.blend, FBX and GLB contain one skinned mesh and the WreckingBall_Rig armature. Handle_ROOT holds the wooden stick; Chain_01 through Chain_07 run from the held end toward Weight_END (ball and socket). Each vertex has exactly one deform bone at weight 1.0, so every link stays rigid. Original part vertex groups remain for editing. Bone heads lie at connection anchors; chain hierarchy moves the downstream ball while the handle stays fixed.

No Actions, keyframes, animation clips, constraints or automatic swinging are included. Preview/Alternate show the unchanged rest geometry; Rig_Pose_Check.png is a temporary pose diagnostic, restored before saving/export. rig_validation.json records measured root stability, rigid distances, joint anchors, weights and fresh FBX/GLB skin roundtrips.

Exports contain only mesh+armature, no staging or leaf bones. Packed color atlas retained. No Studio edits or import tests. Hidden surfaces remain inferred; rigid components overlap at mechanical joints. Rebuild revision: Blender 5.2 --background --threads 4 --python ../../batches/juggler_utility/revise_motion.py -- wrecking. Run from the original static model when rebuilding rig.

Source Model.blend also contains only the skinned mesh and armature; the review stage was removed after rendering. For a full rebuild, first run build_utility.py -- 25, then revise_motion.py -- wrecking, verify_motion.py, finish_motion.py, and clean_rig_source.py (all under batches/juggler_utility). No animation is saved by any step.
