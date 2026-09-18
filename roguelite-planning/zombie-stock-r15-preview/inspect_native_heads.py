from pathlib import Path
import struct
root=Path('C:/Users/Jeremiah/AppData/Local/Roblox/Versions/version-4310300497aa4917/content/avatar/heads')
for p in root.glob('*.mesh'):
 raw=p.read_bytes();e=raw.index(b'\n')+1;h,v,f,n,t=struct.unpack_from('<HBBII',raw,e)
 uv=[struct.unpack_from('<ff',raw,e+h+i*v+24) for i in range(n)]
 print(p.name,n,len(set(uv)),sum(x==0 and y==0 for x,y in uv))
