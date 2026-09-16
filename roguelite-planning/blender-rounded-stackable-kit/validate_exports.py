"""Round-trip geometry, atlas UV/material and exact supplied texture checks."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
source=(ROOT.parent/'blender-cliff-pillars-v2/validate_exports.py').read_text()
source=source.replace("'ChatGPT Image Sep 16, 2026, 11_42_58 AM (3).png'","'C:/Users/Jeremiah/AppData/Local/Temp/codex-clipboard-1228ecae-c585-4927-89e1-31d682f938e9.png'")
exec(compile(source,str(ROOT/'validate_exports.py'),'exec'))
