from PIL import Image
from pathlib import Path
p=Path('roguelite-planning/weapon-models/studio-import/textures')
a=Image.open(p/'W20_Cinder_Blocks_Texture0.png').convert('RGB')
# PNG rows are top-down; UV dark tile occupies column 1, bottom row.
concrete=a.getpixel((224,160))
a.paste(concrete,(64,256,128,320));a.save(p/'Cinder_Corrected.png')
b=Image.open(p/'W22_Bowling_Ball_Texture0.png').convert('RGB')
# Keep genuine dark finger sockets; only change the body tile.
b.paste((105,109,120),(128,128,192,192));b.save(p/'Bowling_Charcoal_Corrected.png')
print('concrete',concrete)

