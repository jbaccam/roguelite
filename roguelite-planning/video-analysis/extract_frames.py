from pathlib import Path
import cv2, json
from PIL import Image, ImageDraw

source=Path('C:/Users/Jeremiah/Videos/attacks')
out=Path(__file__).resolve().parent
report=[]
for idx,p in enumerate(sorted(source.glob('*.mp4'))):
    cap=cv2.VideoCapture(str(p))
    fps=cap.get(cv2.CAP_PROP_FPS); count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration=count/fps
    sheet=Image.new('RGB',(1600,1000),'#ddd')
    draw=ImageDraw.Draw(sheet)
    for n in range(12):
        frame=min(count-1,int((n+.35)*count/12))
        cap.set(cv2.CAP_PROP_POS_FRAMES,frame)
        ok,raw=cap.read()
        if not ok:continue
        im=Image.fromarray(cv2.cvtColor(raw,cv2.COLOR_BGR2RGB))
        im.thumbnail((400,305))
        x=(n%4)*400;y=(n//4)*333
        sheet.paste(im,(x+(400-im.width)//2,y))
        draw.text((x+5,y+309),f'{frame/fps:.2f}s',fill='black')
    sheet.save(out/f'{idx+1:02d}-overview.jpg')
    report.append(dict(index=idx+1,file=p.name,fps=fps,frames=count,duration=duration,width=cap.get(cv2.CAP_PROP_FRAME_WIDTH),height=cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
(out/'clips.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
