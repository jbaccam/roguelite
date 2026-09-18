# Boomerang

One curved solid boomerang. Cream bands and triangle motifs are closed shallow relief. The unseen back repeats the front decoration.

Model.blend contains editable geometry with named component vertex groups and a packed base-color atlas. Model.fbx and Model.glb contain geometry only with embedded texture. Preview.png and Alternate.png are actual Blender renders. Reference.png is an unchanged copy of the supplied image. Review cameras, lights and floor remain in a separate non-exported collection.

Reproduce from the repository root with:

```powershell
& "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --threads 4 --python roguelite-planning/weapon-models/batches/throwables/build_throwables.py -- 12
```

The shared helper base.py is copied into the same batch directory. audit.py verifies packed textures, unchanged reference hashes, closed topology, triangle counts and FBX/GLB reimports. See validation.json for measured results. Separate assembled pieces intentionally overlap. No rigging, gameplay, or Roblox/Studio import testing is claimed.
