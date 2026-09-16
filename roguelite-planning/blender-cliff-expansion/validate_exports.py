"""Verify every new FBX/GLB using the v2 texture and mesh round-trip checks."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
source=(ROOT.parent/'blender-cliff-pillars-v2/validate_exports.py').read_text()
source=source.replace("ROOT=Path(__file__).resolve().parent", "ROOT=Path(__file__).resolve().parent")
source=source.replace("assert all(tuple(node.image.size)==(2048,2048) for node in textures)","assert all(tuple(node.image.size)==((4096,4096) if path.stem=='distant-mountain-backdrop' else (2048,2048)) for node in textures)")
exec(compile(source,str(ROOT/'validate_exports.py'),'exec'))
