from pathlib import Path
source=(Path(__file__).resolve().parent/'animate_mobs.py').read_text().split('S=Matrix(((1,0,0,0)')[0]
exec(compile(source,str(__file__),'exec'),globals())
for t in [.375,.4166667,.4583333,.5]:
    pose('Attack',t)
    for n in ['Chest','LeftUpperArm','LeftForearm','LeftHand']:
        p=pb[n];parent=p.parent
        predicted=parent.matrix@parent.bone.matrix_local.inverted()@p.bone.matrix_local@p.matrix_basis if parent else p.bone.matrix_local@p.matrix_basis
        print('PROBE',t,n,'actual',list(p.matrix.translation),'basis',list(p.matrix_basis.translation),'predicted',list(predicted.translation),'inherit',p.bone.inherit_scale,p.bone.use_inherit_rotation,p.bone.use_local_location,flush=True)
