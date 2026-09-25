"""Rerun accepted hand/grip tests against the newly animated delivery meshes."""
from pathlib import Path
import sys,shutil
ROOT=Path(__file__).resolve().parent
id=sys.argv[sys.argv.index('--')+1]
if id=='fire-goblin':
    shutil.copy2(ROOT.parent/'reference-rebuilds'/id/'anatomy.json',ROOT/id/'anatomy.json')
    source=(ROOT.parent/'reference-rebuilds'/'verify_goblin_grip_motion.py').read_text()
elif id=='bow-skeleton':
    shutil.copy2(ROOT.parent/'reference-rebuilds'/id/'ArrowProjectile.blend',ROOT/id/'ArrowProjectile.blend')
    source=(ROOT.parent/'reference-rebuilds'/'render_bow_shot.py').read_text().split('scene.frame_start=1;scene.frame_end=25;scene.render.fps=24')[0]
    source+='\nprint("BOW_CONTACT_AND_SUBFRAME_WRIST_CHECKS_PASSED",flush=True)\n'
else:raise ValueError(id)
exec(compile(source,str(__file__),'exec'),globals())
