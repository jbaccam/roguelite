# Weapon articulation preparation

These updates prepare the assets for later animation and gameplay. They do not add animation clips, keyframes, attacks, or Roblox physics. The saved rigged files open in their rest pose. `Rig_Pose_Check.png` files are temporary diagnostic poses used to check articulation, not animations.

## Chain weapons

Nunchucks, kusarigama, and the wrecking-ball weapon use exportable skeletons with a held root, successive chain joints, and a terminal baton or weight. Each metal link is assigned rigidly to one bone, so it rotates instead of stretching. Rotate the chain bones in Pose Mode to shape a swing; the downstream links and end weight follow. Per-asset `rig_validation.json` and README files give the exact controls and hierarchy.

Use the updated FBX for the later Studio rig import. Roblox supports imported skinning weights and represents the skeleton as Bones. Bone movement affects visual geometry, not the mesh's collision shape; combat hitboxes or a physical simulation can be added separately during gameplay implementation. [Roblox rigging and skinning](https://create.roblox.com/docs/art/modeling/rigging)

## Empty launcher and separate rocket

`11-rocket-launcher/Model.*` contains the empty launcher. `11-rocket-launcher/components/Rocket/Model.*` contains only the reusable rocket. The asset's alignment metadata describes its insertion position and axis. Neither file contains an animation or firing logic.

## Pandora's Box

The lid pivots on the rear hinge independently of the chest body. The body has a hollow interior and the lid has a finished underside so that the open state is usable. The primary file is saved closed; a diagnostic open-pose render demonstrates the rig.

## Yo-yo string decision

The rigid modeled string is removed. The yo-yo and finger ring are separate reusable models under `21-yo-yo/components/YoYo/` and `FingerRing/`. Blender markers and attachment metadata identify the string endpoints; these markers are preparation data, not an assertion that Roblox Attachments have already been created.

During Studio integration, create a Beam between hand/ring and axle Attachments. It follows their changing separation, and its curve controls allow a slack or taut appearance. Adjust the curve as the yo-yo moves; an unchanged curve does not calculate sag automatically. A light twisted-rope texture can retain the reference's string appearance. [Roblox Beams](https://create.roblox.com/docs/effects/beams)

If physical tether behavior is wanted, add a RopeConstraint separately. It limits maximum separation and can use its winch to change the target distance. For a controlled roguelite attack, a scripted yo-yo path plus the visual Beam is the recommended starting point. No string runtime or simulation has been installed in Studio in this art-preparation task. [Roblox RopeConstraint](https://create.roblox.com/docs/physics/constraints/rope)

## Delivery checks

`rig_audit.json` independently reopens the source blend and reimports FBX/GLB, checks rigid weights and absence of animation clips, and temporarily poses movable bones. It checks that descendants move, geometry outside the selected bone's descendants stays still, and within-piece distances remain unchanged. `export_audit.json` and `delivery_verification.json` cover file, texture, geometry and independent-component delivery checks. Studio import itself remains untested.
