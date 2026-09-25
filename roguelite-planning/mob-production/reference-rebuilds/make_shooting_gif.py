from pathlib import Path
from PIL import Image
import json,hashlib
root=Path(__file__).resolve().parent/'bow-skeleton'
frames=[Image.open(root/'shot-frames'/f'{i:03}.png').convert('RGB') for i in range(1,26)]
durations=[350]+[80]*23+[350]
frames[0].save(root/'Shooting.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=2,optimize=False)
check=json.loads((root/'ShootingChecks.json').read_text())
check['sha256']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['Model.blend','Model.glb','animations/Attack.fbx','ArrowProjectile.blend','ShootingDemo.blend','Shooting.gif']}
(root/'ShootingChecks.json').write_text(json.dumps(check,indent=2))
print('Shooting.gif:',(root/'Shooting.gif').stat().st_size,'bytes')
