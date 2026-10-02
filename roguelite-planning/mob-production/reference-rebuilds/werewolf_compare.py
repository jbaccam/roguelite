"""Compose the werewolf review strips beside the supplied sheet and probe colours.

System Python (needs Pillow + numpy):  python werewolf_compare.py
Reads werewolf/review/{Front,Side,Back,ThreeQuarter}.png written by
build_werewolf.py (0.01 units per pixel, ground at y=770, like the sheet).
"""
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'werewolf';REVIEW=OUT/'review'
REF=ROOT.parents[1]/'art-references'/'werewolf-redesign'/'werewolf-turnaround-v1.png'
ref=Image.open(REF).convert('RGB')
canvas=Image.new('RGB',ref.size,(160,157,156))
for label,cx in [('Front',258),('Side',695),('Back',1075),('ThreeQuarter',1515)]:
    strip=Image.open(REVIEW/f'{label}.png').convert('RGBA');canvas.paste(strip,(cx-strip.width//2,0),strip)
canvas.save(OUT/'Turnaround.png')
sheet=Image.new('RGB',(ref.width,ref.height*2));sheet.paste(ref,(0,0));sheet.paste(canvas,(0,ref.height));sheet.save(OUT/'Compare.png')
a=np.asarray(ref).astype(float);b=np.asarray(canvas).astype(float)
boxes={'arm grey':(105,330),'shin grey':(175,660),'mane front':(150,235),'mane back':(1075,300),'bib':(258,330),
       'muzzle':(240,240),'shorts':(200,520),'belt':(200,437)}
for name,(x,y) in boxes.items():
    ra=np.median(a[y-5:y+6,x-5:x+6].reshape(-1,3),0);rb=np.median(b[y-5:y+6,x-5:x+6].reshape(-1,3),0)
    print(f'{name:11s} ref {ra.astype(int).tolist()} ours {rb.astype(int).tolist()} gain {np.round(ra/np.maximum(rb,1),2).tolist()}')
