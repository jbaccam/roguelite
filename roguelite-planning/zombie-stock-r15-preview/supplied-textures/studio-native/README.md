# Native Roblox R15 zombie comparison

## Latest head correction

The active comparison head now uses Roblox's original `rbxasset://avatar/heads/head.mesh` geometry with **full-head UVs assigned natively in Studio through EditableMesh**. The built-in classic head had UVs only for the front; six Decals did not wrap its curved sides. The faulty decal head is retained as `ServerStorage.ZombiePreviousDecalHead` for recovery, not rendered.

The newest supplied square image is retained as `Head_Latest_Original.png` and uploaded unchanged as `rbxassetid://117306049770322`. `ApplyFullHeadUV.luau` reproduces the UV correction, exact original head dimensions and Neck attachment. `CreateNativeZombie.luau` now includes this correction automatically. No Blender geometry was imported, and all 517 original native head vertices/846 faces remain unchanged.

Verified screenshots: `Head_Front_Wrapped.png`, `Head_Back_Wrapped.png`, `Head_Left_Wrapped.png`, and `Head_Top_Wrapped.png`. The face no longer loses its mouth at the rounded lower edge, and grime is visible on the side, back and top.

**Persistence limitation:** the head's MeshContent currently references a live EditableMesh. Uploading that mesh via AssetService failed with `CreateAssetAsync and CreateAssetVersionAsync are not available yet`. The source scripts reconstruct it, but this is not yet a published immutable mesh asset or a verified published-game NPC. Do not claim save/reopen or multiplayer replication was tested.

The older screenshot and six-decal notes below describe the superseded initial comparison.

Created in the open roguelite Studio session as `Workspace.Zombie_R15_ProvidedTextures_Studio`, separate from the existing gameplay enemy. It starts from `Players:CreateHumanoidModelFromDescriptionAsync` with an empty description, R15, body/proportion scales zero and all size scales one. Stock body meshes, dimensions and attachment positions are retained. The head uses Roblox's built-in `SpecialMesh.MeshType.Head`, not imported Blender geometry.

`CreateNativeZombie.luau` reconstructs this native comparison model in Edit mode. It intentionally refuses to overwrite an existing comparison. The root is anchored for inspection; this is not yet wired into the existing chase/spawn system.

The original supplied image pixels were resampled only for UV alignment. Native R15 shares one atlas across each three-part limb and one across the two torso parts. `*_NativeAtlas.png` combine the rebaked stock UV islands accordingly. No replacement art was painted. The head uses six crops from `ChatGPT Image Sep 17, 2026, 01_01_31 PM.png`, including the new supplied face. Brown shoulder tops use the supplied brown fabric region.

`Zombie_Studio_Native.png` is an actual Studio screenshot. A temporary neutral comparison stage and lighting adjustments were used for capture, then removed/restored. The comparison NPC remains beside the spawn area. The original enemy and game scripts were not replaced.

Verified in Studio: R15 Humanoid, 15 body sections plus HumanoidRootPart, 15 connected Motor6Ds, no accessories/hair, native stock proportions, original-image textures visibly applied and readable face. Animation playback, chase integration and multiplayer behavior have not been tested for this new comparison NPC.

The mesh part colors are white to avoid multiplying/tinting the supplied image colors. `ZombieBaseSkinRGB` records the intended 64,131,54 base skin; the supplied textures provide the actual visible skin variation.
