"""Shorten the Skeleton's crossguard so its rear quillon clears the forearm.

blender --background --python shorten_skeleton_guard.py

Turning the sword edge-forward (edge_forward_blades.py) put the crossguard
fore-and-aft; this model's fist is bent back at the wrist, so the rear quillon
sank up to 0.11 units into the forearm. The guard island is scaled to 60% of
its length about its own centre (width and thickness unchanged). The previous
source is kept in history/before-guard-trim/.
"""
import bpy, bmesh, shutil
from pathlib import Path
import numpy as np
from mathutils import Vector
HERE = Path(__file__).resolve().parent
SRC = HERE / 'reference-rebuilds' / 'skeleton'
keep = SRC / 'history' / 'before-guard-trim'; keep.mkdir(parents=True, exist_ok=True)
for f in ['Model.blend', 'Model.fbx']:
    if not (keep / f).exists(): shutil.copy2(SRC / f, keep / f)
bpy.ops.wm.open_mainfile(filepath=str(SRC / 'Model.blend'))
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
hand = bpy.data.objects['RightHand_Geometry']
bm = bmesh.new(); bm.from_mesh(hand.data); bm.verts.ensure_lookup_table()
seen, isl = set(), []
for v in bm.verts:
    if v.index in seen: continue
    st, cur = [v], []; seen.add(v.index)
    while st:
        x = st.pop(); cur.append(x.index)
        for e in x.link_edges:
            y = e.other_vert(x)
            if y.index not in seen: seen.add(y.index); st.append(y)
    isl.append(cur)
GUARD = 7
P = np.array([list(bm.verts[j].co) for j in isl[GUARD]]); c = P.mean(0)
u, s, vt = np.linalg.svd(P - c); axis = vt[0]
span0 = float(np.ptp((P - c) @ axis))
for j in isl[GUARD]:
    p = np.array(bm.verts[j].co); d = (p - c) @ axis
    bm.verts[j].co = Vector(p - axis * d * 0.4)
bm.to_mesh(hand.data); hand.data.update()
bpy.ops.wm.save_as_mainfile(filepath=str(SRC / 'Model.blend'))
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers)]
bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.fbx(filepath=str(SRC / 'Model.fbx'), use_selection=True, object_types={'MESH', 'ARMATURE'}, add_leaf_bones=False,
                         bake_anim=False, path_mode='COPY', embed_textures=True, axis_forward='-Z', axis_up='Y', use_armature_deform_only=False)
shutil.copy2(SRC / 'Model.fbx', HERE / 'studio-import' / 'sources' / 'skeleton-guard-trim.fbx')
print('GUARD', 'span %.3f -> %.3f' % (span0, span0 * .6), 'axis', np.round(axis, 3).tolist())
