# Yo-Yo — dynamic-string preparation

The baked static cord is removed. Model.blend and root FBX/GLB contain two independent unparented meshes: YoYo (spool/body center pivot) and FingerRing (finger loop center pivot, including the red connector). Use components/YoYo/Model.blend, Model.fbx or Model.glb for the body alone; components/FingerRing provides the same three standalone files for the hand piece. Each standalone file has exactly one unparented mesh at the origin, with a packed/embedded atlas.

The Blender-only attachment guide collection contains String_Axle and String_Hand Empty markers parented to their respective mesh. attachment_points.json records local positions, orientations and coordinate conventions. They are excluded from FBX/GLB. Later in Studio, a Beam between corresponding Attachments can display a taut/slack/extending string; an optional RopeConstraint can impose a physical maximum length. No Beam, constraint, gameplay, rig or animation is created here.

Preview and Alternate are real Blender renders. Source reference unchanged. Intentional component intersections and palette UV overlap retained; back geometry inferred from the source. No Studio changes or import testing. Revision script: ../../batches/juggler_utility/revise_motion.py -- yoyo; start from original static model to rebuild.
