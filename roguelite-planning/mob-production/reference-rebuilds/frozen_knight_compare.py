"""Compose the Frozen Knight review strips under the supplied sheet and probe colours.

System Python (needs Pillow + numpy):  python frozen_knight_compare.py
Reads frozen-knight/review/{Front,Side,Back,ThreeQuarter}.png written by
build_frozen_knight.py (0.0092 units per pixel, floor at row 764, like the
sheet). The pipeline rig puts Left at -X facing -Y, so the model is the mirror
image of the sheet: the strips are rendered from mirrored cameras and flipped
left-right here so each panel lines up with the sheet. The raw strips in
review/ are unflipped. Also joins GripOuter/GripInner into GripDetail.png.
"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageOps
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'frozen-knight';REVIEW=OUT/'review'
REF=ROOT.parents[1]/'art-references'/'frozen-knight-redesign'/'frozen-knight-turnaround-v1.png'
ref=Image.open(REF).convert('RGB')
canvas=Image.new('RGB',ref.size,(150,146,145))
for label,cx in [('Front',262),('Side',665),('Back',1065),('ThreeQuarter',1525)]:
    strip=ImageOps.mirror(Image.open(REVIEW/f'{label}.png').convert('RGBA'));canvas.paste(strip,(cx-strip.width//2,0),strip)
d=ImageDraw.Draw(canvas)
for label,cx in [('FRONT',262),('LEFT SIDE',665),('BACK',1065),('THREE-QUARTER',1525)]:d.text((cx-30,820),label,fill=(70,70,74))
d.text((12,866),'Blender render of the rebuilt mesh, strips mirrored left-right to the sheet (rig convention: Left at -X)',fill=(70,70,74))
canvas.save(OUT/'Turnaround.png')
sheet=Image.new('RGB',(ref.width,ref.height*2));sheet.paste(ref,(0,0));sheet.paste(canvas,(0,ref.height));sheet.save(OUT/'Compare.png')
if (REVIEW/'GripOuter.png').exists():
    a=Image.open(REVIEW/'GripOuter.png').convert('RGB');b=Image.open(REVIEW/'GripInner.png').convert('RGB')
    g=Image.new('RGB',(a.width+b.width,a.height));g.paste(a,(0,0));g.paste(b,(a.width,0));g.save(REVIEW/'GripDetail.png')
A=np.asarray(ref).astype(float);B=np.asarray(canvas).astype(float)
boxes={'helm front':(300,150),'helm side':(650,150),'breastplate':(318,330),'pauldron':(405,300),'snow cap':(150,245),'navy arm':(410,370),
       'belt':(205,425),'tasset':(330,495),'glove':(85,505),'knee cop':(345,600),'sabaton':(345,735),'back plate':(1065,300)}
gains=[]
for name,(x,y) in boxes.items():
    ra=np.median(A[y-5:y+6,x-5:x+6].reshape(-1,3),0);rb=np.median(B[y-5:y+6,x-5:x+6].reshape(-1,3),0);g=ra/np.maximum(rb,1);gains.append(g)
    print(f'{name:12s} ref {ra.astype(int).tolist()} ours {rb.astype(int).tolist()} gain {np.round(g,2).tolist()}')
print('median gain',np.round(np.median(np.array(gains),0),2).tolist())
