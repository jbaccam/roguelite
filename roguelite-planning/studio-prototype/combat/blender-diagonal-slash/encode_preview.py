from pathlib import Path
import subprocess, shutil
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

root=Path(__file__).parent
frames=root/'frames'; labelled=root/'labelled';labelled.mkdir(exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',23)
small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
for n in range(1,11):shutil.copyfile(root/'check_001.png',frames/f'frame_{n:04}.png')
for n in range(66,83):shutil.copyfile(root/'check_066.png',frames/f'frame_{n:04}.png')
files=sorted(frames.glob('frame_*.png'))
assert len(files)==82,len(files)
def label(im,heading,subtitle=None):
    im=im.convert('RGB');d=ImageDraw.Draw(im)
    d.rectangle((0,0,im.width,52),fill=(24,29,35))
    d.text((18,10),heading,font=font,fill=(236,239,244))
    if subtitle:
        d.rectangle((0,im.height-36,im.width,im.height),fill=(24,29,35))
        d.text((18,im.height-30),subtitle,font=small,fill=(190,205,218))
    return im

ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
def encode(name,sequence,heading):
    proc=subprocess.Popen([ffmpeg,'-y','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s','960x720','-r','60','-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(root/name)],stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
    for f,slow in sequence:
        im=label(Image.open(files[f]),heading if not slow else 'DIAGONAL KATANA SLASH  |  25% speed', 'Above shoulder > across torso > opposite hip')
        proc.stdin.write(im.tobytes())
    proc.stdin.close();assert proc.wait()==0

encode('Katana_Diagonal_Slash.mp4',[(i,False) for _ in range(2) for i in range(82)]+[(i,True) for i in range(82) for _ in range(4)],'DIAGONAL KATANA SLASH  |  normal speed')
encode('Katana_Diagonal_Slash_Normal.mp4',[(i,False) for i in range(82)],'DIAGONAL KATANA SLASH  |  normal speed')
encode('Katana_Diagonal_Slash_Slow.mp4',[(i,True) for i in range(82) for _ in range(4)],'DIAGONAL KATANA SLASH  |  25% speed')

checks=[(1,'READY'),(17,'OUTWARD ANTICIPATION'),(20,'CUT: ACCELERATING'),(23,'CUT: ACROSS TORSO'),(27,'CUT: OPPOSITE HIP'),(33,'FOLLOW THROUGH'),(42,'OUTSIDE RECOVERY'),(54,'RECOVERY'),(66,'SAME READY POSE')]
sheet=Image.new('RGB',(1440,1170),(24,29,35));d=ImageDraw.Draw(sheet)
for i,(f,title) in enumerate(checks):
    x=(i%3)*480;y=(i//3)*390
    sheet.paste(Image.open(root/f'check_{f:03}.png').resize((480,360)),(x,y+30))
    d.text((x+12,y+5),f'{(f-1)/60:.2f}s  |  {title}',fill='white',font=small)
sheet.save(root/'Contact_Sheet.png')
label(Image.open(root/'check_027.png'),'DIAGONAL KATANA SLASH').save(root/'Preview.png')
print('Saved 8.2-second main preview, normal-speed clip, quarter-speed clip, and contact sheet.')
