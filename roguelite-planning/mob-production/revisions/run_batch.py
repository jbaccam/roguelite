from pathlib import Path
import concurrent.futures,json,subprocess,sys
root=Path(__file__).resolve().parent
ids=sys.argv[1:] or [x[0] for x in json.loads((root.parent/'briefs.json').read_text())]
def run(mob):
    out=root/mob;out.mkdir(exist_ok=True)
    with (out/'build.log').open('w') as log:
        p=subprocess.run(['C:/Program Files/Blender Foundation/Blender 5.2/blender.exe','-b','--threads','4','--python-exit-code','1','--python',str(root/'build_revisions.py'),'--',mob],stdout=log,stderr=subprocess.STDOUT)
    print(mob,p.returncode,flush=True)
    return mob,p.returncode
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:r=dict(pool.map(run,ids))
(root/'build-results.json').write_text(json.dumps(r,indent=2))
sys.exit(int(any(r.values())))
