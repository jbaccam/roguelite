from pathlib import Path
from html.parser import HTMLParser
import json,hashlib,urllib.request
ROOT=Path(__file__).resolve().parent
ids=['obsidian-ogre','snake','rock-throwing-crab','skeleton','bow-skeleton','fire-goblin','lava-slime','ash-shaman','spitter-zombie']
result={'mobs':{},'errors':[],'studioVerified':False,'visualApproval':False}
for mob in ids:
    out=ROOT/mob;check=json.loads((out/'ExchangeChecks.json').read_text());rig=json.loads((out/'Rig.json').read_text())
    assert check['passed'] and not rig['failures'],mob
    for name,digest in check['sha256'].items():assert hashlib.sha256((out/name).read_bytes()).hexdigest()==digest,(mob,name,'changed after check')
    result['mobs'][mob]={'triangles':rig['totals']['triangles'],'bones':len(rig['bones'])+1,'clips':len(rig['actions']),'meshChecksPassed':True,'exchangeChecksPassed':True,'hashesCurrent':True}
class Resources(HTMLParser):
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ['src','href'] and value and not value.startswith(('#','http')):assert (ROOT/value.split('?')[0]).is_file(),value
Resources().feed((ROOT/'review.html').read_text(encoding='utf-8'))
for name in ['HandAnatomyChecks.json','GripMotionChecks.json']:
    path=ROOT/'fire-goblin'/name
    if path.exists():
        check=json.loads(path.read_text());assert check['passed'],name
        for file,digest in check.get('sha256',{}).items():assert hashlib.sha256((path.parent/file).read_bytes()).hexdigest()==digest,(name,file,'changed after check')
        result[name]={'passed':True,'hashesCurrent':True if check.get('sha256') else None}
for name in ['ArrowChecks.json','ShootingChecks.json']:
    path=ROOT/'bow-skeleton'/name
    if path.exists():
        check=json.loads(path.read_text());assert check['passed'],name
        for file,digest in check['sha256'].items():assert hashlib.sha256((path.parent/file).read_bytes()).hexdigest()==digest,(name,file,'changed after check')
        result[name]={'passed':True,'hashesCurrent':True}
try:
    with urllib.request.urlopen('http://127.0.0.1:8814/reference-rebuilds/review.html',timeout=5) as response:result['reviewHttpStatus']=response.status
except Exception as e:result['reviewHttpError']=str(e)
(ROOT/'DeliveryChecks.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
