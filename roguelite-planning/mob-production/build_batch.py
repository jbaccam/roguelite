"""Run isolated Blender processes, at most two at once. No open UI scene is touched."""
from pathlib import Path
import concurrent.futures, json, subprocess, sys, time
root=Path(__file__).resolve().parent
blender='C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
ids=sys.argv[1:] or [x[0] for x in json.loads((root/'briefs.json').read_text())]+['ice-elf']
def run(mob):
    out=root/mob;out.mkdir(exist_ok=True)
    with (out/'build.log').open('w') as log:
        result=subprocess.run([blender,'-b','--threads','4','--python-exit-code','1','--python',str(root/'build_mobs.py'),'--',mob],stdout=log,stderr=subprocess.STDOUT)
    print(mob,'PASS' if result.returncode==0 else 'FAILED',flush=True)
    return mob,result.returncode
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    results=dict(pool.map(run,ids))
(root/'build-results.json').write_text(json.dumps(results,indent=2))
sys.exit(1 if any(results.values()) else 0)
