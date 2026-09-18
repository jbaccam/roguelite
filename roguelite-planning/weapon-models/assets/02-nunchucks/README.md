# Nunchucks — rigid chain rig

Model.blend contains the unchanged reference asset plus an exportable armature. BaseColor.png remains packed. Model.fbx and Model.glb include one mesh and one skeleton, with no lights, camera, floor, animation clips, Actions, keyframes, or FBX leaf bones. Preview.png and Alternate.png still show the unchanged rest model. Rig_Pose_Check.png is a temporary posed diagnostic still only.

Controls: select Nunchucks_Rig, enter Pose Mode, and rotate `Chain_01` through `Chain_05` from the held end toward the moving end. `Handle_ROOT` is fixed at the handhold; move the entire armature object to place the weapon. `Baton_END` rotates the terminal payload. Chain rotations move all downstream links and the payload. Translation/scale controls are locked to discourage opening joints or stretching links. Each whole link uses one weight of 1.0, with no blended-metal deformation.

For nunchucks, the right baton in the reference rest pose is held, and the left baton is the terminal moving baton.

The FK rig supplies animation controls, not automatic swinging, physics, or collision avoidance. Avoid extreme rotations that make links intersect. Unseen surfaces are inferred from the reference. Original part vertex groups remain available. Geometry and color are preserved; rest and three temporary poses were numerically checked for rigid links, fixed held geometry, downstream motion and coincident joint anchors. Fresh FBX/GLB imports retained the complete skeleton and skin and passed pose-deformation checks. Studio import is still pending.

Reconstruction: ../../batches/melee_tools/build_melee.py; rig addition: ../../batches/melee_tools/rig_chains.py. Re-run rigging only on the unrigged build.
