"""Contact and continuous-skin checks, plus source inspection renders."""
import bpy,bmesh,json,sys,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from goblin_hands import GRIP_CENTER as c, GRIP_AXIS as a
out=ROOT/'fire-goblin'
bpy.ops.wm.open_mainfile(filepath=str(out/'Sculpt.blend'))
body=next(o for o in bpy.context.scene.objects if o.get('smooth_skin'))
bm=bmesh.new();bm.from_mesh(body.data)
unseen=set(bm.verts);components=[]
while unseen:
    seed=unseen.pop();stack=[seed];count=0
    while stack:
        v=stack.pop();count+=1
        for e in v.link_edges:
            n=e.other_vert(v)
            if n in unseen:unseen.remove(n);stack.append(n)
    components.append(count)
tree=BVHTree.FromBMesh(bm)
b=Vector((0,-1,0));b=(b-a*a.dot(b)).normalized();d=a.cross(b)
samples=[]
for along in [-.18,0,.18]:
    for k in range(16):
        direction=b*math.cos(k*math.tau/16)+d*math.sin(k*math.tau/16)
        hit,n,idx,dist=tree.ray_cast(c+a*along,direction,.60)
        samples.append({'along':along,'angle':k*22.5,'distance':dist if hit is not None else None})
report={'connectedSkinComponents':len(components),'componentVertexCounts':components,
        'nonManifoldEdges':sum(not e.is_manifold for e in bm.edges),
        'gripChannelSamples':samples,'wrappedHandleRadius':.134,
        'minimumChannelRadius':min(s['distance'] for s in samples if s['distance'] is not None)}
report['contactRaysPerSection']=[sum(s['distance'] is not None for s in samples if s['along']==along) for along in [-.18,0,.18]]
# An opposing thumb leaves an open web; require enclosing contact over a
# majority of directions, not an anatomically incorrect closed ring of skin.
report['passed']=len(components)==1 and report['nonManifoldEdges']==0 and min(report['contactRaysPerSection'])>=9 and all(s['distance'] is None or .133<s['distance']<.48 for s in samples)
(out/'HandAnatomyChecks.json').write_text(json.dumps(report,indent=2));bm.free()
print('HAND_ANATOMY',report['passed'],report['connectedSkinComponents'],report['minimumChannelRadius'],flush=True)
scene=bpy.context.scene;camera=scene.camera
scene.render.resolution_x=800;scene.render.resolution_y=800;scene.cycles.samples=24
for name,center,offset in [('SculptHands',Vector((0,-.10,2.10)),Vector((0,-3,.6))),('SculptRightHand',c,Vector((-.7,-3,.6))),('SculptPalm',c,Vector((1,2,-.4)))]:
    span=4.45 if name=='SculptHands' else 1.55
    camera.location=center+offset*span;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=span
    scene.render.filepath=str(out/(name+'.png'));bpy.ops.render.render(write_still=True)
assert report['passed'],report
