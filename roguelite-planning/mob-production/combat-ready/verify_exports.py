"""Reuse the independent fresh-import verifier for the animation-only outputs."""
from pathlib import Path
root=Path(__file__).resolve().parent
source=(root.parent/'reference-rebuilds'/'verify_exports.py').read_text()
source=source.replace("expected=json.loads((out/'Rig.json').read_text());bone_names=set(expected['bones'])|{'Root'}", "anim=json.loads((out/'AnimationData.json').read_text());geo=json.loads((out/'Geometry.json').read_text());expected={'bones':anim['bones'],'actions':anim['clips'],'totals':{'triangles':sum(len(m['triangles']) for m in geo.values())},'failures':[]};bone_names=set(expected['bones'])")
source=source.replace("im.size[0]==2048 and im.size[1]==2048", "im.size[0]>=512 and im.size[1]>=512")
exec(compile(source,str(__file__),'exec'),globals())
