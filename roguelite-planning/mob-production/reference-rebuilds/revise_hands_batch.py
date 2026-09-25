from pathlib import Path
import subprocess,shutil,concurrent.futures
ROOT=Path(__file__).resolve().parent;BLENDER='C:/Program Files/Blender Foundation/Blender 5.2/blender.exe'
jobs={'obsidian-ogre':['build_ogre.py'],'skeleton':['build_skeletons.py','--','skeleton'],'bow-skeleton':['build_skeletons.py','--','bow-skeleton'],'fire-goblin':['build_goblin.py'],'ash-shaman':['build_shaman.py']}
def run(mob,args):
    archive=ROOT/'history'/'before-hand-stone-correction'/mob;archive.mkdir(parents=True,exist_ok=True)
    for name in ['Sculpt.blend','Model.blend','Preview.png','Rigged.png','RightHandGrip.png','LeftHandGrip.png']:
        src=ROOT/mob/name;dst=archive/name
        if src.exists() and not dst.exists():shutil.copy2(src,dst)
    with (ROOT/(mob+'-hand-shape.log')).open('w') as log:
        subprocess.run([BLENDER,'--background','--threads','4','--python',args[0],*args[1:]],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    print('SCULPT',mob,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    fs=[pool.submit(run,mob,args) for mob,args in jobs.items()]
    for f in fs:f.result()
