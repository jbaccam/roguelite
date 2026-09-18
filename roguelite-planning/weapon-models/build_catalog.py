"""Audit asset coverage and generate an offline comparison catalog from real renders."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json, html, zipfile, sys

ROOT=Path(__file__).resolve().parent
items=[json.loads((ROOT/'approved-glock.json').read_text())]+json.loads((ROOT/'inventory.json').read_text())
required=['Model.blend','Model.fbx','Model.glb','Preview.png','Alternate.png','Reference.png','validation.json','README.md']
audit=[]
for item in items:
    folder=Path(item['output'])
    missing=[name for name in required if not (folder/name).is_file() or (folder/name).stat().st_size==0]
    stats={}
    if (folder/'validation.json').exists():
        try:stats=json.loads((folder/'validation.json').read_text(encoding='utf-8-sig'))
        except Exception as exc:missing.append('valid validation.json: '+str(exc))
    audit.append({'index':item['index'],'name':item['name'],'batch':item['batch'],'output':str(folder),'complete_files':not missing,'missing':missing,'validation':stats})
(ROOT/'coverage.json').write_text(json.dumps(audit,indent=2))
ready=[(item,row) for item,row in zip(items,audit) if row['complete_files']]
print(json.dumps({'complete':len(ready),'total':len(items),'missing':[r['name'] for r in audit if r['missing']]},indent=2))

cards=[]
for item,row in ready:
    rel='assets/'+item['slug']+'/'
    title=html.escape(item['name'])
    stats=row['validation']
    tri=stats.get('triangles',stats.get('triangle_count','See validation'))
    components=item.get('components',[])
    component_links=''
    if components:
        component_links='<details open><summary>Independent component files</summary>'+''.join(f'<p class="links"><b>{html.escape(c)}</b><a href="{rel}components/{c}/Model.blend">Blender</a><a href="{rel}components/{c}/Model.fbx">FBX</a><a href="{rel}components/{c}/Model.glb">GLB</a></p>' for c in components)+'</details>'
    note='One reusable model; the supplied reference shows multiple examples.' if item.get('representation')=='single_reusable' else 'Review arrangement only: each component is a separate movable mesh with its own pivot and files below.' if components else ''
    if item.get('component_mode')=='additional':note='Main files contain the empty launcher. The rocket is a separate reusable asset in the component files below.'
    if item.get('rigged'):note='Rigged for posing; saved at rest with no animation clips.'
    if item['index']==21:note='Separate yo-yo and finger ring. Static string removed; attachment markers prepare a future Roblox Beam.'
    rig_links=f'<p class="links"><a href="{rel}Rig_Pose_Check.png">Rig pose check</a><a href="{rel}rig_validation.json">Rig details</a></p>' if item.get('rigged') else ''
    cards.append(f'''<article data-name="{title.lower()}"><h2>{title}</h2>
    <div class="pair"><figure><img loading="lazy" src="{rel}Reference.png" alt="{title} supplied reference"><figcaption>Reference</figcaption></figure><figure><img loading="lazy" src="{rel}Preview.png" alt="{title} actual Blender render"><figcaption>Blender model</figcaption></figure></div>
    <p>{note}</p><p class="links"><a href="{rel}Model.blend">{'Review Blender file' if components and item.get('component_mode')!='additional' else 'Blender'}</a><a href="{rel}Model.fbx">FBX</a><a href="{rel}Model.glb">GLB</a><a href="{rel}Alternate.png">Alternate view</a><a href="{rel}validation.json">Checks</a><span>{html.escape(str(tri))} triangles</span></p>{rig_links}{component_links}</article>''')
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Weapon models — reference comparisons</title>
<style>*{box-sizing:border-box}body{margin:0;background:#eeedeb;color:#262524;font:16px system-ui,sans-serif}header,main{max-width:1440px;margin:auto;padding:26px}h1{font-size:28px;margin:0 0 10px}header p{max-width:850px;line-height:1.55;color:#57534f}input{font:inherit;padding:11px 14px;width:min(100%,450px);border:1px solid #aaa;border-radius:5px;background:white}main{padding-top:0;display:grid;grid-template-columns:1fr;gap:24px}article{background:#fff;border:1px solid #d7d4cf;padding:22px;border-radius:8px}h2{margin:0 0 16px;font-size:21px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}img{width:100%;aspect-ratio:1.1;object-fit:contain;background:#f1f0ed;display:block}figcaption{font-size:14px;color:#625c56;padding-top:8px}.links{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:0;align-items:center;font-size:14px}.links a{color:#28516b}.links span{margin-left:auto;color:#6b645e}[hidden]{display:none}@media(min-width:1200px){main{grid-template-columns:1fr 1fr}}@media(max-width:550px){header,main{padding:16px}article{padding:12px}.pair{gap:8px}.links{gap:12px}}</style>
<header><h1>Weapon models</h1><p>Supplied references beside actual Blender renders. The approved Glock is included with the remaining weapons. These are model deliverables; Roblox gameplay integration and Studio import are separate steps.</p><input id="search" type="search" placeholder="Find a weapon" aria-label="Find a weapon"></header><main>'''+''.join(cards)+'''</main><script>document.getElementById('search').addEventListener('input',e=>{let q=e.target.value.toLowerCase().trim();document.querySelectorAll('article').forEach(a=>a.hidden=!a.dataset.name.includes(q))})</script></html>'''
(ROOT/'Weapon_Catalog.html').write_text(page,encoding='utf-8')

try:font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',22)
except OSError:font=ImageFont.load_default()
for start in range(0,len(ready),6):
    group=ready[start:start+6]
    canvas=Image.new('RGB',(1200,3*470),(238,237,235));draw=ImageDraw.Draw(canvas)
    for slot,(item,row) in enumerate(group):
        x=(slot%2)*600;y=(slot//2)*470
        try:im=Image.open(Path(item['output'])/'Preview.png').convert('RGB')
        except OSError:continue # An agent may still be replacing a render during progress review.
        im.thumbnail((584,420))
        canvas.paste(im,(x+(600-im.width)//2,y+(420-im.height)//2))
        draw.text((x+20,y+429),item['name'],font=font,fill=(30,30,30))
    canvas.save(ROOT/f'Weapon_Review_{start//6+1:02d}.jpg',quality=93)
if '--zip' in sys.argv:
    assert len(ready)==len(items),'Do not package an incomplete weapon roster'
    verification=json.loads((ROOT/'delivery_verification.json').read_text())
    assert verification['passed_items']==len(items) and not verification['inventory_issues'],'Independent delivery verification must pass before packaging'
    overview=Image.new('RGB',(1800,6*330),(238,237,235));overview_draw=ImageDraw.Draw(overview)
    overview_font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
    for slot,(item,row) in enumerate(ready):
        x=(slot%6)*300;y=(slot//6)*330
        im=Image.open(Path(item['output'])/'Preview.png').convert('RGB');im.thumbnail((294,294))
        overview.paste(im,(x+(300-im.width)//2,y+(294-im.height)//2))
        overview_draw.text((x+10,y+300),item['name'],font=overview_font,fill=(30,30,30))
    overview.save(ROOT/'Weapon_Overview.jpg',quality=95)
    changes=[(11,'Preview.png','Empty launcher'),(11,'components/Rocket/Preview.png','Separate rocket'),(2,'Rig_Pose_Check.png','Nunchucks — pose check'),(4,'Rig_Pose_Check.png','Kusarigama — pose check'),(25,'Rig_Pose_Check.png','Wrecking ball — pose check'),(33,'Rig_Pose_Check.png','Pandora — opening check'),(21,'Preview.png','Yo-yo — separate pieces')]
    sheet=Image.new('RGB',(1600,880),(238,237,235));sd=ImageDraw.Draw(sheet)
    for slot,(idx,filename,label) in enumerate(changes):
        item=next(i for i in items if i['index']==idx)
        im=Image.open(Path(item['output'])/filename).convert('RGB');im.thumbnail((394,394))
        x=(slot%4)*400;y=(slot//4)*440
        sheet.paste(im,(x+(400-im.width)//2,y+(394-im.height)//2))
        sd.text((x+10,y+405),label,font=overview_font,fill=(30,30,30))
    sheet.save(ROOT/'Rig_Update_Review.jpg',quality=95)
    with zipfile.ZipFile(ROOT/'Weapon_Models_Complete.zip','w',zipfile.ZIP_DEFLATED,compresslevel=5) as archive:
        for item,row in ready:
            folder=Path(item['output'])
            for path in sorted(folder.rglob('*')):
                if path.is_file() and path.suffix not in ('.blend1','.blend2'):
                    archive.write(path,path.relative_to(ROOT))
        for name in ['Weapon_Catalog.html','Weapon_Overview.jpg','coverage.json','inventory.json','approved-glock.json','MODELING_BRIEF.md','README.md','ASSETS.md','RIGGING_GUIDE.md','rig_audit.json','audit_rigs.py','export_audit.json','delivery_verification.json','verify_delivery.py','audit_exports.py','build_catalog.py','clean_approved_copy.py']:
            archive.write(ROOT/name,name)
        for path in sorted((ROOT/'batches').rglob('*.py')):
            archive.write(path,path.relative_to(ROOT))
        archive.write(ROOT/'Rig_Update_Review.jpg','Rig_Update_Review.jpg')
        for path in sorted(ROOT.glob('Weapon_Review_*.jpg')):
            archive.write(path,path.name)
    print('BUNDLE_READY', (ROOT/'Weapon_Models_Complete.zip').stat().st_size)
