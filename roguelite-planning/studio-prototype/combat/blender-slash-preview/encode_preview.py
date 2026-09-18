from pathlib import Path
import subprocess, cv2, imageio_ffmpeg
from PIL import Image
root=Path(__file__).parent
files=sorted((root/'frames').glob('frame_*.png'))
assert len(files)==135, len(files)
marked=root/'labelled';marked.mkdir(exist_ok=True)
gif=[]
for i,p in enumerate(files):
 im=cv2.imread(str(p));sec=i/30
 title='FRONT SLASH | normal speed' if sec<1.1 else 'REAR SLASH | normal speed' if sec<2.1 else 'REAR SLASH | 25% speed'
 cv2.rectangle(im,(0,0),(im.shape[1],46),(28,24,21),-1)
 cv2.putText(im,title,(16,30),cv2.FONT_HERSHEY_SIMPLEX,.62,(240,234,222),1,cv2.LINE_AA)
 cv2.imwrite(str(marked/p.name),im)
 gif.append(Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB)))
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-framerate','30','-i',str(marked/'frame_%04d.png'),'-c:v','libx264','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(root/'Katana_Outward_Slash.mp4')],check=True)
gif[0].save(root/'Katana_Outward_Slash.gif',save_all=True,append_images=gif[1:],duration=33,loop=0,optimize=False)
print('Encoded 135 frames, 4.5 seconds, H.264 MP4 plus GIF')
