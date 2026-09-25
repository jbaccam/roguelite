"""Embed content hashes so a cached review page cannot reuse superseded clips."""
import hashlib
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent
assets = {}
for directory in sorted(root.iterdir()):
    if not (directory / 'AnimationData.json').is_file():
        continue
    assets[directory.name] = {
        file.name: hashlib.sha256(file.read_bytes()).hexdigest()
        for file in sorted(directory.iterdir())
        if file.is_file() and file.suffix in {'.glb', '.blend', '.fbx', '.png', '.json'}
    }
page = root / 'review.html'
text = page.read_text(encoding='utf-8')
declaration = 'const assetHashes=' + json.dumps(assets, separators=(',', ':')) + ';'
if 'const assetHashes=' in text:
    text = re.sub(r'const assetHashes=.*?;\n', declaration + '\n', text)
else:
    text = text.replace('<script>\n', '<script>\n' + declaration + '\n')
text = text.replace("id+'/Model.glb?v=combat-animation-1'", "assetURL(id,'Model.glb')")
text = text.replace('${id}/${f}', '${assetURL(id,f)}')
text = text.replace('${id}/${n}.png?v=combat-animation-1', "${assetURL(id,n+'.png')}")
text = text.replace("fetch(id+'/manifest.json')", "fetch(assetURL(id,'manifest.json'))")
if 'function assetURL(' not in text:
    text = text.replace('async function load()', "function assetURL(id,file){return id+'/'+file+'?sha256='+assetHashes[id][file];}\nasync function load()")
page.write_text(text, encoding='utf-8')
(root / 'ReviewAssetHashes.json').write_text(json.dumps(assets, indent=2), encoding='utf-8')
print(f'Review hashes refreshed for {len(assets)} models; bow GLB {assets["bow-skeleton"]["Model.glb"]}')
