"""Turn held swords 90 degrees about their own long axis so the cutting edge,
not the flat, faces forward (the knuckle line of the grip) and leads a swing.

blender --background --python edge_forward_blades.py -- <id> [--apply]
Only the sword islands of the right-hand mesh move; the fist, UVs, weights,
rig and every other mesh are untouched. The previous source is preserved
under <source>/history/before-edge-forward/ before anything is written.
"""
import bpy, bmesh, sys, json, shutil, math
from pathlib import Path
import numpy as np
from mathutils import Vector, Matrix

HERE = Path(__file__).resolve().parent
args = sys.argv[sys.argv.index('--') + 1:]
ID = args[0]
APPLY = '--apply' in args
SOURCE = HERE / ({'skeleton': 'reference-rebuilds', 'frozen-knight': 'revisions'}[ID]) / ID
bpy.ops.wm.open_mainfile(filepath=str(SOURCE / 'Model.blend'))
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
wrist = rig.matrix_world @ rig.data.bones['RightHand'].head_local
hand = next(o for o in bpy.context.scene.objects if o.type == 'MESH' and o.vertex_groups.get('RightHand')
            and any(v.groups and o.vertex_groups[v.groups[0].group].name == 'RightHand' for v in o.data.vertices)
            and o.name.startswith('RightHand'))
bm = bmesh.new(); bm.from_mesh(hand.data); bm.verts.ensure_lookup_table()
seen, islands = set(), []
for v in bm.verts:
    if v.index in seen:
        continue
    stack, isl = [v], []
    seen.add(v.index)
    while stack:
        x = stack.pop(); isl.append(x.index)
        for e in x.link_edges:
            y = e.other_vert(x)
            if y.index not in seen:
                seen.add(y.index); stack.append(y)
    islands.append(isl)
mw = hand.matrix_world
info = []
for i, isl in enumerate(islands):
    P = np.array([list(mw @ bm.verts[j].co) for j in isl])
    d = np.linalg.norm(P - np.array(wrist), axis=1)
    info.append({'island': i, 'verts': len(isl), 'maxFromWrist': round(float(d.max()), 3), 'minFromWrist': round(float(d.min()), 3),
                 'min': P.min(0).round(3).tolist(), 'max': P.max(0).round(3).tolist()})
# Sword islands identified from the island report (blade, crossguard, grip,
# pommel); palm, fingers, thumb and knuckle details stay put.
BLADE, SWORD = {'skeleton': (8, [6, 7, 8, 9]), 'frozen-knight': (2, [0, 1, 2])}[ID]
report = {'id': ID, 'object': hand.name, 'islands': info, 'swordIslands': SWORD}
idx = sorted({j for i in SWORD for j in islands[i]})
P = np.array([list(mw @ bm.verts[j].co) for j in idx])
B = np.array([list(mw @ bm.verts[j].co) for j in islands[BLADE]])
c = B.mean(0); u, s, vt = np.linalg.svd(B - c)
axis = vt[0]
tip = P[np.argmax(np.linalg.norm(P - np.array(wrist), axis=1))]
if np.dot(axis, tip - c) < 0:
    axis = -axis
X = (P - c) - np.outer((P - c) @ axis, axis)
_, s2, vt2 = np.linalg.svd(X)
report.update({'axis': axis.round(4).tolist(), 'centre': c.round(4).tolist(), 'widthBefore': vt2[0].round(3).tolist()})
if APPLY:
    hist = SOURCE / 'history' / 'before-edge-forward'
    hist.mkdir(parents=True, exist_ok=True)
    for f in ['Model.blend', 'Model.fbx', 'Model.glb']:
        if (SOURCE / f).exists() and not (hist / f).exists():
            shutil.copy2(SOURCE / f, hist / f)
    R = Matrix.Rotation(math.radians(90), 4, Vector(axis.tolist()))
    world = Matrix.Translation(Vector(c.tolist())) @ R @ Matrix.Translation(-Vector(c.tolist()))
    local = mw.inverted() @ world @ mw
    for j in idx:
        bm.verts[j].co = local @ bm.verts[j].co
    bm.to_mesh(hand.data); hand.data.update()
    P2 = np.array([list(mw @ hand.data.vertices[j].co) for j in idx])
    X2 = (P2 - c) - np.outer((P2 - c) @ axis, axis)
    _, _, vt3 = np.linalg.svd(X2)
    report['widthAfter'] = vt3[0].round(3).tolist()
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE / 'Model.blend'))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers)]
    bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = rig
    common = dict(use_selection=True, object_types={'MESH', 'ARMATURE'}, add_leaf_bones=False, bake_anim=False,
                  path_mode='COPY', embed_textures=True, axis_forward='-Z', axis_up='Y')
    if ID == 'skeleton':
        common['use_armature_deform_only'] = False
    bpy.ops.export_scene.fbx(filepath=str(SOURCE / 'Model.fbx'), **common)
    (HERE / 'studio-import' / 'sources').mkdir(exist_ok=True)
    shutil.copy2(SOURCE / 'Model.fbx', HERE / 'studio-import' / 'sources' / (ID + '-edge-forward.fbx'))
print('EDGE_REPORT', json.dumps(report))
