"""Find longer planted strides that stay inside the accepted rigs' leg reach."""
from pathlib import Path
import json
import sys
from mathutils import Vector

root = Path(__file__).resolve().parent
source = (root/'animate_mobs.py').read_text().split('S=Matrix(((1,0,0,0)')[0]
ids = ['ash-shaman','bow-skeleton','crab','ember-spider','fire-goblin','frozen-knight','hermit-crab','ice-elf','mummy','obsidian-ogre','rock-throwing-crab','scorpion','skeleton','spitter-zombie','werewolf']
result = {}
for id in ids:
    sys.argv=['probe','--',id]
    ns={'__file__':str(root/'animate_mobs.py')}
    # Slightly lower moving hips provide reach while retaining knee bend.
    probe_source=source.replace("lower=leg_length*(.13 if HEAVY else .12 if FAST else .11)","lower=leg_length*((.17 if HEAVY else .17 if FAST else .15) if moving else (.13 if HEAVY else .12 if FAST else .11))")
    exec(compile(probe_source,str(root/'animate_mobs.py'),'exec'),ns)
    records=[]
    for amount in ([.4,.42,.44,.46,.48,.50] if ns['HUM'] else [.45,.5,.55,.6,.65,.7,.75,.8]):
        ns['stride_amp']=amount*ns['leg_length'] if ns['HUM'] else amount
        errors=[]
        for step in range(49):
            t=step/48;ns['pose']('Move',t)
            if ns['HUM']:
                for side,offset in [('Left',0),('Right',.5)]:
                    y,z,planted=ns['footpath'](t+offset)
                    if planted:
                        p=ns['pb'][side+'Foot'];target=p.bone.head_local+Vector((0,y,0))
                        errors.append((p.head-target).length)
            else:
                for lower,tip in ns['leg_tips'].items():
                    j=int(lower.split('Leg')[1][0]);side=-1 if lower.startswith('Left') else 1
                    y,z,planted=ns['footpath'](t+(j%2)*.5+(.5 if side>0 else 0))
                    if planted:
                        p=ns['pb'][lower];actual=p.matrix@p.bone.matrix_local.inverted()@tip
                        errors.append((actual-(tip+Vector((0,y,0)))).length)
        records.append({'amplitude':amount,'maxError':max(errors),'stride':2*ns['stride_amp']/ns['stance_fraction']})
    result[id]=records
    print('STRIDE_REACH',id,records,flush=True)
(root/'StrideReachProbe.json').write_text(json.dumps(result,indent=2))
