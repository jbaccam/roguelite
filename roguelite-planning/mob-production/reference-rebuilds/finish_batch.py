from pathlib import Path
import subprocess,concurrent.futures
ROOT=Path(__file__).resolve().parent;BLENDER='C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
def run(mob,scripts):
    for script in scripts:
        with (ROOT/(mob+'-'+script+'.log')).open('w') as log:
            result=subprocess.run([BLENDER,'--background','--threads','4','--python',str(ROOT/script),'--',mob],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        text=(ROOT/(mob+'-'+script+'.log')).read_text(errors='replace')
        if result.returncode or 'Traceback (most recent call last)' in text:raise RuntimeError(mob+' '+script+' failed')
    print('FINISHED',mob,flush=True)
jobs={
'fire-goblin':['rig_export.py','polish_rig.py','verify_exports.py','render_details.py'],
'ash-shaman':['rig_export.py','polish_rig.py','verify_exports.py','render_details.py'],
'rock-throwing-crab':['polish_rig.py','verify_exports.py'],
'bow-skeleton':['render_details.py','render_motion_checks.py'],
}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    results=[pool.submit(run,mob,scripts) for mob,scripts in jobs.items()]
    for result in results:result.result()
