"""Validate revised exports and the exact latest lighter source sheets."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
source=(ROOT.parent/'blender-cliff-pillars-v2/validate_exports.py').read_text()
source=source.replace('ChatGPT Image Sep 16, 2026, 11_42_57 AM (1).png','02862eb3-b09f-4d03-8bc3-ad7b57fd49a7.png')
source=source.replace('ChatGPT Image Sep 16, 2026, 11_42_58 AM (3).png','62c4effc-a3a8-48f1-a138-776cdb1d9a8e.png')
exec(compile(source,str(ROOT/'validate_exports.py'),'exec'))
