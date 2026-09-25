from pathlib import Path
import json,html,re
ROOT=Path(__file__).resolve().parent
notes={
'obsidian-ogre':'Rebuilt continuous torso and limbs: deeper chest and back, substantial traps, blended pectorals, solid mitten fists and integrated knees. Body geometry increased from 7,388 to 19,694 triangles.',
'snake':'Continuous transported body curve, modeled dorsal scales and belly scutes, separate head and fangs.',
'rock-throwing-crab':'Raised articulated claw encloses the rock between both pincers.',
'skeleton':'Four bent fingers extend from a defined palm behind the sword handle; the thumb closes across them.',
'bow-skeleton':'Straight drawing wrist: the hand stays aligned with the forearm through draw and release. The string follows the fingers, with a separate arrow asset and updated shooting preview.',
'fire-goblin':'Rebuilt both hands as continuous skin: tapered wrists, convex palms, curled finger pads and integrated opposing thumbs. The dagger fits across the right fist. Inspect the front, palm and side close-ups below.',
'lava-slime':'Asymmetric molten body with irregular basalt chunks instead of a grid of armor plates.',
'ash-shaman':'Rebuilt staff hand with a defined palm behind the shaft, four bent fingers and an opposing thumb.',
'spitter-zombie':'Heavy belly, swollen cheeks, open mouth, uneven teeth and clothing fitted to the body.'}
parts=[]
updated={'obsidian-ogre','skeleton','bow-skeleton','fire-goblin','ash-shaman'}
for mob,note in notes.items():
    rig=json.loads((ROOT/mob/'Rig.json').read_text()) if (ROOT/mob/'Rig.json').exists() else None
    check=json.loads((ROOT/mob/'ExchangeChecks.json').read_text()) if (ROOT/mob/'ExchangeChecks.json').exists() else None
    checks='Exchange checks passed' if check and check['passed'] else 'Exchange checks pending'
    count=f"{rig['totals']['triangles']:,} triangles across {len(rig['checks'])} meshes" if rig else 'Rig export pending'
    title=mob.replace('-',' ').title()
    parts.append(f'''<article id="{mob}"><div class="title"><h2>{title}</h2><span>Candidate • Studio test pending</span></div><p>{note}</p><div class="pair"><figure><a href="{mob}/Rigged.png" target="_blank"><img class="mesh" src="{mob}/Rigged.png" loading="lazy" alt="Actual baked Blender mesh of {title}"></a><figcaption class="viewlabel">Actual baked Blender mesh · rest pose</figcaption><div class="views">'''+''.join(f'<button data-view="{view}.png" data-caption="{caption}">{label}</button>' for view,label,caption in [('Rigged','Rest','Actual baked Blender mesh · rest pose'),('Front','Front','Procedural sculpture · front'),('Side','Side','Procedural sculpture · side'),('Back','Back','Procedural sculpture · back'),('Attack','Attack','Actual baked Blender mesh · attack frame 13')])+f'''</div></figure><figure><a href="../{mob}/Reference.png" target="_blank"><img src="../{mob}/Reference.png" loading="lazy" alt="AI target design of {title}"></a><figcaption>AI target design · image reference, not a mesh</figcaption></figure></div><p class="small">{count} · {checks}. Visual fidelity is still under review.</p><p class="links"><a href="{mob}/Model.blend">Rigged Blender</a><a href="{mob}/Sculpt.blend">Editable sculpture</a><a href="{mob}/Model.fbx">FBX mesh</a><a href="{mob}/Model.glb">Animated GLB</a><a href="{mob}/BaseColor.png">Baked texture</a><a href="{mob}/ExchangeChecks.json">Verification</a></p><details><summary>Earlier rejected mesh</summary><img class="old" src="../revisions/{mob}/Preview.png" loading="lazy" alt="Rejected previous mesh"></details></article>''')
page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Reference rebuilds • Mob review</title><style>
*{box-sizing:border-box}body{margin:0;background:#151b20;color:#e9e9e5;font:16px/1.55 system-ui}header,main{max-width:1550px;margin:auto;padding:28px 40px}header{padding-bottom:16px}h1{font-size:32px;letter-spacing:-.8px;margin:0}h2{font-size:25px;margin:0}.intro{max-width:960px;color:#bcc4c8}nav{display:flex;gap:10px 20px;flex-wrap:wrap;padding:20px 0}a{color:#bed5e0;text-underline-offset:4px}article{padding:28px 0 42px;border-top:1px solid #465159;scroll-margin-top:16px}.title{display:flex;gap:16px;align-items:center;justify-content:space-between}.title span,.small{font-size:13px;color:#acb8bf}article>p{color:#c2c9cc}.pair{display:grid;grid-template-columns:1fr 1.3fr;gap:20px}figure{margin:0;min-width:0}img{display:block;width:100%;background:#303337;object-fit:contain}figure img{height:min(45vw,660px)}figcaption{font-size:13px;color:#b7c0c5;margin-top:8px}.views{display:flex;gap:8px;margin-top:12px}button{font:inherit;font-size:13px;color:#e1e6e8;background:#2b3740;border:1px solid #52616b;border-radius:4px;padding:7px 12px;cursor:pointer}button:hover,button.active{background:#516570}.links{display:flex;gap:10px 22px;flex-wrap:wrap;font-size:14px}.old{max-width:450px;margin-top:14px}summary{cursor:pointer;color:#aeb8bf;font-size:14px}.notice{border-left:3px solid #ba9668;padding:10px 16px;background:#242a2e;color:#d2d5d5;max-width:1100px}@media(max-width:760px){header,main{padding:20px}.pair{grid-template-columns:1fr}figure img{height:auto}.title{display:block}.title span{display:block;margin-top:4px}}
</style></head><body><header><h1>Reference rebuilds</h1><p class="intro">Nine separate Blender reconstructions of the mobs flagged in your feedback. Compare their actual geometry with the original AI designs. Bosses are excluded.</p><p class="notice">These are revised candidates, not a claim of identical reproduction or game readiness. Each rig includes five basic clips. Studio import, gameplay timing, projectile release and visual acceptance remain unverified. The archer has an aim gesture; a complete nocked bow draw is still unfinished.</p><nav>'''+''.join(f'<a href="#{m}">{m.replace("-"," ").title()}</a>' for m in notes)+'</nav></header><main>'+''.join(parts)+'''</main><script>document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{const a=b.closest('article'),img=a.querySelector('.mesh');img.src=a.id+'/'+b.dataset.view;img.parentElement.href=img.src;a.querySelector('.viewlabel').textContent=b.dataset.caption;a.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b));});</script></body></html>'''
page=page.replace('The archer has an aim gesture; a complete nocked bow draw is still unfinished.','The archer’s drawing hand is empty; spawning an arrow remains a game integration step.')
for mob in notes:
    extras=[]
    for p in sorted([*(ROOT/mob).glob('*Grip.png'),*(ROOT/mob).glob('*Detail.png')]):
        extras.append(f'<figure><a href="{mob}/{p.name}" target="_blank"><img src="{mob}/{p.name}" loading="lazy" alt="{mob} grip close-up"></a><figcaption>{p.stem.replace("Hand", " hand ")} · actual mesh</figcaption></figure>')
    if extras:
        start=page.index(f'<article id="{mob}">');end=page.index('</article>',start)
        block=page[start:end];block=block.replace('<details><summary>Earlier rejected mesh</summary>','<details'+(' open' if mob in updated else '')+'><summary>Hands and anatomy close-ups</summary><div class="pair">'+''.join(extras)+'</div></details><details><summary>Earlier rejected mesh</summary>')
        page=page[:start]+block+page[end:]
page=page.replace('<h1>Reference rebuilds</h1>','<h1>Reference rebuilds</h1><p class="notice">Latest correction: Bow Skeleton drawing wrist. Hand and forearm stay aligned through the draw and release. <a href="#bow-skeleton">Inspect the updated shot</a> · <a href="#fire-goblin">Goblin hands</a> · <a href="#obsidian-ogre">Ogre volume rebuild</a></p>')
start=page.index('<article id="bow-skeleton">');end=page.index('</article>',start)
block=page[start:end]
shooting='''<div class="pair"><figure><img src="bow-skeleton/Shooting.gif" alt="Actual Blender shooting animation with separate arrow"><figcaption>Actual rig and separate arrow · slowed for inspection</figcaption></figure><div><h3>Draw → release → flight</h3><p>The string follows the drawing hand and snaps back at release. The arrow is a separate asset, shown here during draw and flight.</p><p class="links"><a href="bow-skeleton/ShootingDemo.blend">Shooting demo · Blender</a><a href="bow-skeleton/ArrowProjectile.fbx">Arrow · FBX</a><a href="bow-skeleton/ArrowProjectile.glb">Arrow · GLB</a><a href="bow-skeleton/ArrowBaseColor.png">Arrow texture</a><a href="bow-skeleton/ShootingChecks.json">Motion checks</a></p><p class="small">Source: 24 fps. Release: frame 15. Gameplay integration is outside this animation-and-asset correction.</p></div></div>'''
block=block.replace('<div class="pair">',shooting+'<div class="pair">',1)
page=page[:start]+block+page[end:]
start=page.index('<article id="obsidian-ogre">');end=page.index('</article>',start)
block=page[start:end]
views='<h3>Torso depth and upper back</h3><div class="pair">'+''.join(f'<figure><a href="obsidian-ogre/{v}.png" target="_blank"><img src="obsidian-ogre/{v}.png" loading="lazy" alt="Revised Ogre {v.lower()} view"></a><figcaption>{v} · actual sculpture</figcaption></figure>' for v in ['Side','Back'])+'</div>'
block=block.replace('<details open>',views+'<details open>',1)
page=page[:start]+block+page[end:]
page=re.sub(r'((?:src|href)="[^"?]+\.(?:png|gif))"',r'\1?v=bow-wrist-7"',page)
page=page.replace("img.src=a.id+'/'+b.dataset.view;","img.src=a.id+'/'+b.dataset.view+'?v=bow-wrist-7';")
(ROOT/'review.html').write_text(page,encoding='utf-8')
old=ROOT.parent/'revisions'/'review.html';text=old.read_text(encoding='utf-8')
if 'superseded-banner' not in text:
    text=text.replace('<header>','<header><p id="superseded-banner" style="background:#482d25;padding:18px;color:#fff">This pass was rejected. <a href="../reference-rebuilds/review.html">Open the new reference rebuild candidates.</a></p>',1)
    old.write_text(text,encoding='utf-8')
