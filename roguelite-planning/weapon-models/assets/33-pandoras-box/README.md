# Pandora's Box — rigid opening rig

The approved exterior is preserved. The stone coffer and both seam caps now have a real hollow cavity, with a finished dark-stone floor/walls and inset lid underside. Hidden surfaces are inferred from the reference.

## Control
Select **Pandora_Chest_Rig**, enter Pose Mode, select **Lid_Hinge**, and rotate its **local Y axis from 0 degrees (closed) to -90 degrees (open)**. This is a rear-edge hinge parallel to model X at `(0, 1.105, 1.90)` in Blender coordinates. Root moves the entire chest. Lid, clasp, amethyst, top panel and all lid ornaments have full rigid weights to Lid_Hinge; body and rim geometry have full weights to Root. There are no constraints, actions, clips, keyframes or leaf bones.

Model.blend, Model.fbx and Model.glb are saved/exported in the closed rest pose. Rig_Pose_Check.png is a temporary 90-degree posed render, not an animation. Preview.png and Alternate.png show the closed rest model. Export payload contains only meshes and the two-bone armature. Textures are packed and embedded.

Rebuild with Blender background mode and `batches/magic/rig_pandora.py`; it uses the preserved approved static source when available. If that local backup is absent, the script automatically runs `build_magic.py -- 33` to regenerate only the static Pandora source first (the inventory reference image must be accessible). Fresh import tests use `--audit glb` and `--audit fbx`. Numerical motion/cavity checks are in rig_validation.json and rig_reimport_*.json. Blender's GLB importer may create a bone-display custom-shape Icosphere in glTF_not_exported; only the actual bone custom-shape helper is excluded from payload geometry checks.

Decorative components intentionally overlap supports. Closed components remain manifold. Keep the two skinning groups if combining meshes. Roblox Studio import, runtime controls and collision configuration have not been tested.
