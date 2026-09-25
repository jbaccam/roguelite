"""Check world-space foot contact and swing clearance on exported crawler rigs."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
for id in ['crab','ember-spider','hermit-crab','rock-throwing-crab','scorpion']:
    out=ROOT/id;bpy.ops.wm.open_mainfile(filepath=str(out/'Model.blend'))
    rig=bpy.data.objects['Rig'];pb=rig.pose.bones;scene=bpy.context.scene
    meshes=[o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
    for tr in rig.animation_data.nla_tracks:tr.mute=True
    action=bpy.data.actions['Move'];rig.animation_data.action=action
    if action.slots:rig.animation_data.action_slot=action.slots[0]
    meta=json.loads((out/'AnimationData.json').read_text());duration=meta['clips']['Move']['duration'];frames=round(duration*24)
    fraction=.62 if id=='hermit-crab' else .54 if id=='ember-spider' else .58
    amplitude=meta['motion']['strideLength']*fraction/2
    tips={}
    for n in pb.keys():
        if 'Leg' not in n or not n.endswith('Lower'):continue
        bone=pb[n].bone
        if bone.tail_local.z<bone.head_local.z-.1:tips[n]=bone.tail_local.copy();continue
        points=[]
        for o in meshes:
            group=o.vertex_groups.get(n)
            if group:points.extend(o.matrix_world@v.co for v in o.data.vertices if any(g.group==group.index and g.weight>.5 for g in v.groups))
        low=min(p.z for p in points);bottom=[p for p in points if p.z<low+.035];tips[n]=sum(bottom,Vector())/len(bottom)
    errors=[];clearance=[]
    for f in range(frames+1):
        scene.frame_set(f+1)
        for n,tip in tips.items():
            j=int(n.split('Leg')[1][0]);phase=(f/frames+(j%2)*.5+(.5 if n.startswith('Right') else 0))%1
            actual=pb[n].matrix@pb[n].bone.matrix_local.inverted()@tip
            if phase<fraction:
                expected=tip+Vector((0,-amplitude+2*amplitude*phase/fraction,0));errors.append((actual-expected).length)
            else:clearance.append(actual.z-tip.z)
    report={'id':id,'plantedSamples':len(errors),'maxPlantedTipError':max(errors),'minimumSwingClearance':min(clearance),'maximumSwingClearance':max(clearance),'passed':max(errors)<.005 and min(clearance)>-.005}
    (out/'FootContactChecks.json').write_text(json.dumps(report,indent=2));print('CRAWLER_CONTACTS',json.dumps(report),flush=True)
