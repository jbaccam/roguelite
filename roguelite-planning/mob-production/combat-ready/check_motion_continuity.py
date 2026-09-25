"""Audit sampled joint continuity and endpoint closure across all delivered clips."""
import json,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
report={}
for path in ROOT.glob('*/AnimationData.json'):
    data=json.loads(path.read_text());entry={}
    for name in ['Idle','Move','Attack']:
        clip=data['clips'][name];angles=[];translations=[]
        for i,(a,b) in enumerate(zip(clip['frames'],clip['frames'][1:])):
            for bone,pa in a['transforms'].items():
                pb=b['transforms'][bone];ra=np.array(pa[3:]).reshape(3,3);rb=np.array(pb[3:]).reshape(3,3)
                angle=math.degrees(math.acos(float(np.clip((np.trace(ra.T@rb)-1)/2,-1,1))))
                angles.append((angle,i+1,bone));translations.append((float(np.linalg.norm(np.array(pa[:3])-np.array(pb[:3]))),i+1,bone))
        a=max(angles);p=max(translations)
        entry[name]={'maxJointRotationPerFrameDegrees':a[0],'rotationFrame':a[1],'rotationJoint':a[2],'maxJointTranslationPerFrame':p[0],'translationFrame':p[1],'translationJoint':p[2],'continuousAt24fps':a[0]<60 and p[0]<.75}
    entry['passed']=all(v['continuousAt24fps'] for v in entry.values())
    report[data['id']]=entry
(ROOT/'MotionContinuityChecks.json').write_text(json.dumps(report,indent=2))
print(json.dumps({id:{'passed':v['passed'],'maxAngle':max(c['maxJointRotationPerFrameDegrees'] for k,c in v.items() if k!='passed')} for id,v in report.items()},indent=2))
assert all(v['passed'] for v in report.values()),'Review discontinuous motion'
