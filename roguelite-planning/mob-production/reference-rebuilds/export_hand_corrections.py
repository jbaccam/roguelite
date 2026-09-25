from pathlib import Path
import subprocess,concurrent.futures,sys,json
ROOT=Path(__file__).resolve().parent
BLENDER='C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
def run(mob):
    for script in ['rig_export.py','polish_rig.py','verify_exports.py','render_details.py','render_motion_checks.py']:
        path=ROOT/(mob+'-'+script+'.log')
        with path.open('w') as log:
            result=subprocess.run([BLENDER,'--background','--threads','4','--python',str(ROOT/script),'--',mob],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        text=path.read_text(errors='replace')
        if result.returncode or 'Traceback (most recent call last)' in text:raise RuntimeError(mob+' '+script+' failed: '+text[-1500:])
        if script=='verify_exports.py' and not json.loads((ROOT/mob/'ExchangeChecks.json').read_text())['passed']:
            raise RuntimeError(mob+' exchange validation failed; see ExchangeChecks.json')
        print(mob,script,'complete',flush=True)
    print('FINISHED',mob,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    results=[pool.submit(run,mob) for mob in sys.argv[1:]]
    for result in results:result.result()
