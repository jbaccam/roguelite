from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'supplied-textures'/'studio-native'
im=Image.open('C:/Users/Jeremiah/AppData/Local/Temp/codex-clipboard-38985ec3-bc0d-4fac-80bd-3bd94573dcc2.png')
panels={'Front':(360,355,897,919),'Back':(20,355,345,880),'Left':(905,355,1235,880),'Right':(20,355,345,880),'Top':(95,25,1155,280),'Bottom':(80,930,1170,1225)}
for face,bounds in panels.items():
    im.crop(bounds).save(OUT/('Head_'+face+'.png'))
print('Cropped original head panels without painting or recoloring.')
