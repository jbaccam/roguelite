"""Export unchanged Roblox native head geometry with the approved UV projection."""
from pathlib import Path
import struct
import numpy as np

root = Path(__file__).resolve().parent
source = Path('C:/Users/Jeremiah/AppData/Local/Roblox/Versions/version-4310300497aa4917/content/avatar/heads/head.mesh')
raw = source.read_bytes()
offset = raw.index(b'\n') + 1
hs, vs, fs, nv, nf = struct.unpack_from('<HBBII', raw, offset)
vertices = [struct.unpack_from('<fff', raw, offset + hs + i * vs) for i in range(nv)]
normals = [struct.unpack_from('<fff', raw, offset + hs + i * vs + 12) for i in range(nv)]
faces = [struct.unpack_from('<III', raw, offset + hs + nv * vs + i * fs) for i in range(nf)]
points = np.array(vertices)
lo, hi = points.min(axis=0), points.max(axis=0)
panels = {'Front':(360,355,897,919), 'Back':(20,355,345,880), 'Left':(905,355,1235,880), 'Right':(20,355,345,880), 'Top':(95,25,1155,280), 'Bottom':(80,930,1170,1225)}
lines = ['o ZombieHead_NativeUV']
lines += ['v %.9f %.9f %.9f' % tuple(p) for p in points]
lines += ['vn %.9f %.9f %.9f' % tuple(p) for p in normals]
for face in faces:
    a,b,c = points[list(face)]
    n = np.cross(b-a,c-a)
    axis = np.abs(n).argmax()
    panel = ('Right' if n[0]>0 else 'Left') if axis==0 else ('Top' if n[1]>0 else 'Bottom') if axis==1 else ('Back' if n[2]>0 else 'Front')
    rect = panels[panel]
    for idx in face:
        q=points[idx]; x,y,z=(q-lo)/(hi-lo)
        if panel=='Front': u,v=np.clip((q[0]+.4251213)/.8502426,0,1),np.clip(1-(q[1]+.5131668)/1.0263336,0,1)
        elif panel=='Back': u,v=1-x,1-y
        elif panel=='Left': u,v=1-z,1-y
        elif panel=='Right': u,v=z,1-y
        elif panel=='Top': u,v=x,1-z
        else: u,v=x,z
        lines.append('vt %.9f %.9f' % ((rect[0]+u*(rect[2]-rect[0]))/1254, 1-(rect[1]+v*(rect[3]-rect[1]))/1254))
for i,face in enumerate(faces):
    lines.append('f ' + ' '.join('%d/%d/%d' % (v+1,i*3+j+1,v+1) for j,v in enumerate(face)))
(root/'ZombieHead_NativeUV.obj').write_text('\n'.join(lines)+'\n')
print({'vertices':nv,'triangles':nf,'output':str(root/'ZombieHead_NativeUV.obj')})
