from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parent/'supplied-textures'/'studio-native'
groups={'Torso':['UpperTorso','LowerTorso']}
for side in ['Left','Right']:
    groups[side+'Arm']=[side+s for s in ['UpperArm','LowerArm','Hand']]
    groups[side+'Leg']=[side+s for s in ['UpperLeg','LowerLeg','Foot']]
for group,parts in groups.items():
    atlas=Image.new('RGB',(1024,1024))
    for name in parts:
        im=Image.open(ROOT/(name+'.png')).convert('RGB')
        mask=im.convert('L').point(lambda x:255 if x>3 else 0)
        atlas.paste(im,(0,0),mask)
    atlas.save(ROOT/(group+'_NativeAtlas.png'))
print('Combined disjoint original stock UV islands; no repainting.')
