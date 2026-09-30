# Boss VFX kit - progress

2026-09-29: complete (one build + one targeted fix pass).

- [x] Read ART_DIRECTION + 4 boss comparison sheets
- [x] paint_textures.py (numpy-only sprites, flipbooks, decals + shared helpers)
- [x] build_vfx_kit.py (meshes, joint smart-UV, numpy atlas paint, FBX + reimport check, EEVEE thumbs, Kit.png, manifest.json)
- [x] Fix pass after first Kit.png: bigger puff frames, thinner lava seams, softer ice-base chamfers, beige shell patches, height labels
- [x] README.md

Open: Studio import untested (scale, embedded texture pickup, pivot, emissive mask).

Rebuild: "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python build_vfx_kit.py
