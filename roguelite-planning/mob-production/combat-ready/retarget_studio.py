"""Retarget sampled deformations to the actual FBX-imported Roblox bone axes.

Run after native Studio import receipts exist. Never assume bone-local rotations
survive FBX conversion. Reconstruct the deformation in common world coordinates.
"""
import json, sys, hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
RECEIPTS=ROOT.parent/'studio-import'
def mat(v):
    m=np.eye(4);m[:3,3]=v[:3];m[:3,:3]=np.asarray(v[3:]).reshape(3,3);return m
def cf(m):return [round(float(x),7) for x in [*m[:3,3],*m[:3,:3].flatten()]]
def worlds(bones,transforms=None):
    result={}
    def rec(n):
        if n in result:return result[n]
        b=bones[n];parent=b['parent'];base=rec(parent) if parent in bones else np.eye(4)
        result[n]=base@mat(b['rest'])@(mat(transforms[n]) if transforms else np.eye(4))
        return result[n]
    for n in bones:rec(n)
    return result
def retarget(id):
    out=ROOT/id;source=out/'AnimationData.json';receipt=RECEIPTS/(id+'-receipt.json')
    if not source.exists() or not receipt.exists():return None
    data=json.loads(source.read_text());imported=json.loads(receipt.read_text())
    bones={b['name']:{'parent':b['parent'] if b['parent'] in data['bones'] else None,'rest':b['cframe']} for b in imported['bones']}
    original_rest=worlds(data['bones']);actual_rest=worlds(bones)
    driven_motors={m['name'].removesuffix('Motor6D'):m for m in imported.get('motors',[]) if m['name'].removesuffix('Motor6D') in data['bones'] and m['name'].removesuffix('Motor6D') not in bones}
    motor_mode=bool(driven_motors)
    if motor_mode:
        parts={p['name']:mat(p['cframe']) for p in imported['parts']}
        motors=driven_motors
        part_to_bone={m['part1']:n for n,m in motors.items()}
        for n,m in motors.items():actual_rest[n]=parts[m['part0']]@mat(m['c0'])
        # Motor frame = Part0*C0 = Part1*C1. Its logical local rest equals
        # parentJoint^-1*childJoint (or parent C1^-1*child C0), so the same
        # hierarchy math produces exactly the native Motor6D.Transform.
        for n,m in motors.items():
            parent=part_to_bone.get(m['part0'],'Root')
            bones[n]={'parent':parent,'rest':cf(np.linalg.inv(actual_rest[parent])@actual_rest[n]),'jointType':'Motor6D','motorName':m['name'],'partName':m['part1'],'c1':m['c1']}
    missing=set(data['bones'])-set(bones)
    if missing:raise ValueError(f'{id}: missing imported joints {sorted(missing)}')
    original_inv={n:np.linalg.inv(m) for n,m in original_rest.items()}
    local_inv={n:np.linalg.inv(mat(b['rest'])) for n,b in bones.items()}
    # Original sample basis(x,z,y) -> confirmed native import basis(-x,z,y).
    reflect=np.diag([-1.,1.,1.,1.]);maximum=0.;engine_maximum=0.;errors=[]
    for name,clip in data['clips'].items():
        for frame in clip['frames']:
            original_pose=worlds(data['bones'],frame['transforms'])
            desired={n:reflect@original_pose[n]@original_inv[n]@reflect@actual_rest[n] for n in bones}
            if motor_mode:
                # The zero-influence Root Bone does not move RootPart. Bake root
                # motion into its top-level motors once instead of applying twice.
                desired['Root']=actual_rest['Root']
            frame['transforms']={n:cf(local_inv[n]@(np.linalg.inv(desired[b['parent']]) if b['parent'] else np.eye(4))@desired[n]) for n,b in bones.items()}
            actual=worlds(bones,frame['transforms'])
            error=max(np.abs(actual[n]-desired[n]).max() for n in bones);maximum=max(maximum,error)
            if motor_mode:
                native_parts={}
                def native_part(part_name):
                    if part_name in native_parts:return native_parts[part_name]
                    bone=part_to_bone.get(part_name)
                    if bone:
                        m=motors[bone]
                        value=native_part(m['part0'])@mat(m['c0'])@mat(frame['transforms'][bone])@np.linalg.inv(mat(m['c1']))
                    else:value=parts[part_name]
                    native_parts[part_name]=value;return value
                for n,m in motors.items():
                    expected=reflect@original_pose[n]@original_inv[n]@reflect@parts[m['part1']]
                    engine_maximum=max(engine_maximum,np.abs(native_part(m['part1'])-expected).max())
    data['bones']=bones
    data['coordinateSpace']='Actual Roblox FBX import joint-local Transform; derived from receipt'
    data['rigType']='Motor6D' if motor_mode else 'Bone'
    data['sourceAnimationHash']=hashlib.sha256(source.read_bytes()).hexdigest()
    data['importReceiptHash']=hashlib.sha256(receipt.read_bytes()).hexdigest()
    data['baselineModelScale']=imported['scale']
    if id=='bow-skeleton':
        bow=np.array([-1.44,-.40,2.72]);back=np.array([.55,.835,0]);back/=np.linalg.norm(back)
        right=np.array([back[1],-back[0],0]);convert=np.array([[-1,0,0],[0,0,1],[0,1,0]])
        upper=bow+back*.42+np.array([0,0,1.5]);rest=bow+right*.18+np.array([0,0,.34])
        hand_inverse=np.linalg.inv(actual_rest['LeftHand'])
        def hand_point(p):return [float(v) for v in (hand_inverse@np.r_[convert@p,1])[:3]]
        data['projectile']={'kind':'Arrow','forward':[0,0,-1],'origin':'nock','length':1.9,'bowHandBone':'LeftHand','drawBone':'BowDraw','upperStringInHand':hand_point(upper),'arrowRestInHand':hand_point(rest),'nockFractionAlongUpperString':.22,'showStart':6/24,'releaseTime':14/24,'attackFacingYaw':float(np.arctan2(.9,np.sqrt(.19)))}
        release_pose=worlds(bones,data['clips']['Attack']['frames'][14]['transforms'])
        upper_world=(release_pose['LeftHand']@np.r_[data['projectile']['upperStringInHand'],1])[:3]
        rest_world=(release_pose['LeftHand']@np.r_[data['projectile']['arrowRestInHand'],1])[:3]
        nock=release_pose['BowDraw'][:3,3]*.78+upper_world*.22
        direction=rest_world-nock;direction/=np.linalg.norm(direction)
        data['projectile']['releaseDirectionLocal']=[float(v) for v in direction]
        data['projectile']['attackFacingYaw']=float(np.arctan2(direction[0],-direction[2]))
    elif id=='rock-throwing-crab':
        contact=json.loads((ROOT.parent/'reference-rebuilds'/id/'anatomy.json').read_text())['rockContact']
        p=contact['rockCenter'];center=np.array([-p[0],p[2],p[1],1.]);bone=contact['heldBone']
        local=np.linalg.inv(actual_rest[bone])@center
        data['projectile']={'kind':'Rock','origin':'center','heldBone':bone,'centerInBone':[float(v) for v in local[:3]],'releaseTime':data['motion']['attackImpact']}
    elif id in {'ice-elf','ash-shaman','spitter-zombie'}:
        # Authored geometry locations: the centre of the throwing fist that
        # holds the conjured icicle, the fireball resting just above the open
        # casting palm (palm normal is +Z at rest, so it stays in front of the
        # palm as it thrusts), and the open mouth cavity. Conversion uses the
        # actual imported joint frame, including Motor6D C1 for the rigid Ice Elf.
        kind,bone,p,origin={
            'ice-elf':('Icicle','RightHand',(1.44,-.12,2.85),'throwing-fist'),
            'ash-shaman':('Fireball','LeftHand',(-1.52,-.88,3.36),'above-casting-palm'),
            'spitter-zombie':('Spit','Head',(0,-.85,4.99),'mouth'),
        }[id]
        center=np.array([-p[0],p[2],p[1],1.])
        local=np.linalg.inv(actual_rest[bone])@center
        data['projectile']={'kind':kind,'origin':origin,'heldBone':bone,'centerInBone':[float(v) for v in local[:3]],'releaseTime':data['motion']['attackImpact'],'sourcePointBlender':list(p)}
    # Relative-to-authoring scale; original FBX import was centimeter-expanded.
    data['authoringScale']=1
    (out/'StudioAnimationData.json').write_text(json.dumps(data,separators=(',',':')))
    result={'id':id,'boneCount':len(bones),'rigType':data['rigType'],'maxWorldMatrixReconstructionError':float(maximum),'maxNativeMotorPartError':float(engine_maximum),'passed':bool(maximum<.00002 and engine_maximum<.00002),'sourceAnimationHash':data['sourceAnimationHash'],'importReceiptHash':data['importReceiptHash'],'outputHash':hashlib.sha256((out/'StudioAnimationData.json').read_bytes()).hexdigest()}
    (out/'StudioRetargetChecks.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
    if not result['passed']:raise ValueError(result)
    return result
if __name__=='__main__':
    ids=sys.argv[1:] or [p.name for p in ROOT.iterdir() if p.is_dir()]
    for id in ids:retarget(id)
