# Deck and three independent cards

Four independent, unparented mesh objects: Deck, HeartCard, SpadeCard and DiamondCard. Each has its own geometry-centered pivot and can move freely. The review composition leaves space between them. Top-level Model.blend/FBX/GLB contain all four separated objects; the components/ subdirectories each contain a standalone centered Model.blend, Model.fbx, Model.glb, BaseColor.png and validation.json. Textures are packed in Blender and embedded in exports.

Reproduce with build_throwables.py -- 18, then split_cards.py. Both scripts are in ../../batches/throwables/. Reference.png is an unchanged copy. Preview.png and Alternate.png are actual Blender renders. The deck reverse and unobserved faces are inferred; single-card backs are plain cream. Geometry deliberately overlaps within the assembled deck sleeve/clasp. No rig, gameplay, or Roblox/Studio testing is claimed.
