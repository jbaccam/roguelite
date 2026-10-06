"""Execute actual pure timeline/catalog/map sources with official Luau CLI; no Studio services."""
from pathlib import Path
import subprocess
import sys
import tempfile

base=Path(__file__).resolve().parent
def wrap(name,file,replacements=()):
    source=(base/file).read_text(encoding='utf-8-sig')
    for old,new in replacements:
        assert old in source, old
        source=source.replace(old,new)
    return f'local {name}=(function()\n{source}\nend)()\n'
source=wrap('Types','ZombieTypes.luau')
source+=wrap('Catalog','EnemyCatalog.luau',[("local Types = require(script.Parent.ZombieTypes)",''),("local MotionTuning = require(script.Parent.EnemyMotionTuning)",'local MotionTuning = {}')])
source+=wrap('Maps','MapConfig.luau')+wrap('Timeline','WaveTimeline.luau')+wrap('Tests','WaveTimelineTests.luau')
source+="local result=Tests(Timeline,Catalog,Maps);print('WaveTimelineTests: '..result.checks..' assertions passed')\n"
with tempfile.TemporaryDirectory(prefix='roguelite-timeline-') as directory:
    path=Path(directory)/'tests.luau';path.write_text(source,encoding='utf-8')
    subprocess.run([str(Path(sys.argv[1]).resolve()),str(path)],check=True)
