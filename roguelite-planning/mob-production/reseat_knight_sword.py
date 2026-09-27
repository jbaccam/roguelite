"""Seat the Frozen Knight's sword in its fist.

blender --background --python reseat_knight_sword.py

The original model passed the handle diagonally across the fist, nearly
perpendicular to the curled fingers, so the knight never looked like it was
gripping the sword and the blade swept through the forearm. The four fingers
sit side by side along X and curl around one tunnel (measured circle fit:
y -0.185, z 2.468, radius 0.17). This moves the sword's islands rigidly so the
handle runs along that tunnel, the crossguard sits just past the thumb and
index finger, the pommel shows past the little finger, and the edges run
along the forearm: in a hammer grip the true edge faces where the fist
punches, so a horizontal sweep leads with the edge, never the flat.

Starts from history/before-edge-forward (the untouched original) and writes
the source Model.blend/.fbx; the previous source goes to history/edge-forward-v1.
"""
import bpy, bmesh, shutil, json
from pathlib import Path
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
SRC = HERE / 'revisions' / 'frozen-knight'
keep = SRC / 'history' / 'edge-forward-v1'
keep.mkdir(parents=True, exist_ok=True)
for f in ['Model.blend', 'Model.fbx']:
    if not (keep / f).exists():
        shutil.copy2(SRC / f, keep / f)
bpy.ops.wm.open_mainfile(filepath=str(SRC / 'history' / 'before-edge-forward' / 'Model.blend'))
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
hand = bpy.data.objects['RightHand']
bm = bmesh.new(); bm.from_mesh(hand.data); bm.verts.ensure_lookup_table()
seen, islands = set(), []
for v in bm.verts:
    if v.index in seen:
        continue
    st, cur = [v], []; seen.add(v.index)
    while st:
        x = st.pop(); cur.append(x.index)
        for e in x.link_edges:
            y = e.other_vert(x)
            if y.index not in seen:
                seen.add(y.index); st.append(y)
    islands.append(cur)
GRIP, GUARD, BLADE = 0, 1, 2
mw = hand.matrix_world
pts = lambda isl: np.array([list(mw @ bm.verts[j].co) for j in isl])
grip = pts(islands[GRIP]); g0 = grip.mean(0)
blade = pts(islands[BLADE]); a0 = blade.mean(0) - g0; a0 /= np.linalg.norm(a0)
w0 = np.array([1.0, 0, 0])                       # original edge axis (edges faced sideways)
guard_s = float((pts(islands[GUARD]).mean(0) - g0) @ a0)
# New frame: handle along -X (blade exits on the thumb/index side), edges
# along the forearm (+-Z at rest), flats facing forward and back.
a1 = np.array([-1.0, 0, 0]); w1 = np.array([0, 0, 1.0])
tunnel = np.array([0.0, -0.185, 2.468])
GUARD_X = 0.74                                    # clear of the thumb (0.905) and gauntlet cuff (0.846)
origin = tunnel + np.array([GUARD_X + guard_s, 0, 0])
F0 = np.c_[a0, w0 - a0 * (w0 @ a0), np.cross(a0, w0)]; F0 /= np.linalg.norm(F0, axis=0)
F1 = np.c_[a1, w1, np.cross(a1, w1)]
R = F1 @ F0.T
inv = np.linalg.inv(np.array(mw)[:3, :3]); t_inv = np.array(mw)[:3, 3]
moved = 0
for isl in (GRIP, GUARD, BLADE):
    for j in islands[isl]:
        p = np.array(mw @ bm.verts[j].co)
        q = origin + R @ (p - g0)
        bm.verts[j].co = Vector(inv @ (q - t_inv))
        moved += 1
bm.to_mesh(hand.data); hand.data.update()
bpy.ops.wm.save_as_mainfile(filepath=str(SRC / 'Model.blend'))
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers)]
bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.fbx(filepath=str(SRC / 'Model.fbx'), use_selection=True, object_types={'MESH', 'ARMATURE'},
                         add_leaf_bones=False, bake_anim=False, path_mode='COPY', embed_textures=True, axis_forward='-Z', axis_up='Y')
shutil.copy2(SRC / 'Model.fbx', HERE / 'studio-import' / 'sources' / 'frozen-knight-gripped.fbx')
new_blade = origin + R @ (blade.mean(0) - g0)
tip = max((origin + R @ (p - g0) for p in blade), key=lambda q: np.linalg.norm(q - origin))
print('RESEAT', json.dumps({'moved': moved, 'guardX': GUARD_X, 'gripCentre': (origin).round(3).tolist(),
                            'bladeCentre': new_blade.round(3).tolist(), 'tip': np.round(tip, 3).tolist()}))
