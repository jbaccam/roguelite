"""Apply the final mesh budget to a saved sculpture and refresh its views."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from meshlib import *
from goblin_hands import finish_skin
out=ROOT/'fire-goblin'
bpy.ops.wm.open_mainfile(filepath=str(out/'Sculpt.blend'))
body=next(o for o in bpy.context.scene.objects if o.get('smooth_skin'))
finish_skin(body)
stage=bpy.data.collections['REVIEW_ONLY']
for o in list(stage.objects):bpy.data.objects.remove(o,do_unlink=True)
bpy.data.collections.remove(stage)
render(out,[o for o in bpy.context.scene.objects if o.type=='MESH'])
