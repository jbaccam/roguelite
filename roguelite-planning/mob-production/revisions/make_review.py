from pathlib import Path
import json,html,hashlib
root=Path(__file__).resolve().parent
ids=['ice-elf']+[x[0] for x in json.loads((root.parent/'briefs.json').read_text())]
cards=[]
for mob in ids:
    p=root/mob
    if not (p/'Preview.png').exists():continue
    manifest=json.loads((p/'manifest.json').read_text())
    validated=False
    if (p/'validation.json').exists():
        report=json.loads((p/'validation.json').read_text())
        hashes=report.get('fileHashes',{})
        validated=bool(hashes) and all(hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
    cards.append(f'''<article id="{mob}"><h2>{html.escape(mob.replace('-',' ').title())}</h2><p>{manifest['triangles']:,} triangles · {manifest['boneCount']} bones · {'Exchange-file checks passed' if validated else 'Exchange-file checks pending'} · Studio validation pending</p><div class="compare"><figure><img loading="lazy" src="../{mob}/Preview.png"><figcaption>Rejected first mesh pass</figcaption></figure><figure><img loading="lazy" src="{mob}/Preview.png"><figcaption>Revised Blender mesh</figcaption></figure><figure><img loading="lazy" src="{mob}/Reference.png"><figcaption>AI design reference — not a mesh render</figcaption></figure></div><details><summary>Back and attack poses</summary><div class="compare"><figure><img loading="lazy" src="{mob}/Back.png"><figcaption>Back</figcaption></figure><figure><img loading="lazy" src="{mob}/Windup.png"><figcaption>Attack anticipation</figcaption></figure><figure><img loading="lazy" src="{mob}/Impact.png"><figcaption>Attack release</figcaption></figure></div></details><p><a href="{mob}/Model.blend">Blender source</a> · <a href="{mob}/Model.fbx">Rest FBX</a> · <a href="{mob}/Model.glb">Animated GLB</a></p></article>''')
links=' '.join(f'<a href="#{x}">{x.replace("-"," ")}</a>' for x in ids)
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Mob mesh revisions</title><style>body{margin:0;background:#19212a;color:#ecf0f3;font:16px/1.5 system-ui}header,main{max-width:1500px;margin:auto;padding:28px}h1{margin:0;font-size:30px}h2{margin-bottom:4px}p{color:#b6c3d0}a{color:#aacfe7}nav{display:flex;gap:8px 18px;flex-wrap:wrap;margin-top:20px}article{padding:22px 0 34px;border-top:1px solid #46515d}.compare{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}figure{margin:0}img{display:block;width:100%;aspect-ratio:1;object-fit:contain;background:#303943}figcaption{padding:8px 0;color:#c6d1db}summary{cursor:pointer;margin:12px 0}@media(max-width:800px){.compare{grid-template-columns:1fr}}details .compare{max-width:1100px}</style><header><h1>Mob mesh revisions</h1><p>Actual Blender geometry compared with the rejected first pass. Bosses excluded. Existing user-made zombies preserved. Export checks are separate from visual approval and Roblox play testing.</p><nav>'''+links+'</nav></header><main>'+''.join(cards)+'</main></html>'
(root/'review.html').write_text(page,encoding='utf-8')
