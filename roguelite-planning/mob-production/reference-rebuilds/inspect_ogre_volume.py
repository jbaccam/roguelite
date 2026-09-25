import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
paths={'previous':ROOT/'history/before-ogre-volume-rebuild/obsidian-ogre/Sculpt.blend','revised':ROOT/'obsidian-ogre/Sculpt.blend'}
report={}
for label,path in paths.items():
    bpy.ops.wm.open_mainfile(filepath=str(path))
    body=bpy.data.objects['Continuous muscular body'];body.data.calc_loop_triangles()
    points=[body.matrix_world@v.co for v in body.data.vertices]
    sections={}
    for height in [4.6,5.05,5.6]:
        sample=[p for p in points if abs(p.z-height)<.09 and abs(p.x)<1.2]
        sections[str(height)]={'front':min(p.y for p in sample),'back':max(p.y for p in sample),'depth':max(p.y for p in sample)-min(p.y for p in sample)}
    report[label]={'bodyTriangles':len(body.data.loop_triangles),'torsoSections':sections}
    if label=='revised':
        fists=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('Solid mitten fist')]
        assert len(fists)==2
        assert not any(o.name.startswith(('Squared knuckle','Folded finger','Stone fist palm')) for o in bpy.data.objects)
        report[label]['solidMittenMeshes']=len(fists)
assert report['revised']['torsoSections']['5.05']['depth']>report['previous']['torsoSections']['5.05']['depth']*1.2
report['chestDepthIncreasePercent']=(report['revised']['torsoSections']['5.05']['depth']/report['previous']['torsoSections']['5.05']['depth']-1)*100
report['passed']=True
(ROOT/'obsidian-ogre/VolumeChecks.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
