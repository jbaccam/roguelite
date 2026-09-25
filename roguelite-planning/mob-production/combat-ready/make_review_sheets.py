from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
ids=sorted(p.name for p in ROOT.iterdir() if p.is_dir() and (p/'Stance.png').exists())
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
for view in ['Stance','Walk','Anticipation','Impact']:
    image=Image.new('RGB',(1200,6*240),(25,33,39));draw=ImageDraw.Draw(image)
    for i,id in enumerate(ids):
        x=i%5*240;y=i//5*360
        # Four columns keep silhouettes large enough for articulation inspection.
        x=i%4*300;y=i//4*288
        render=Image.open(ROOT/id/(view+'.png')).convert('RGB');render.thumbnail((268,260))
        image.paste(render,(x+16,y));draw.text((x+12,y+262),id.replace('-',' ').title(),font=font,fill=(225,233,237))
    image.crop((0,0,1200,((len(ids)+3)//4)*288)).save(ROOT/(view+'Sheet.jpg'),quality=94)
