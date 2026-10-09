"""Independent re-open of the Bloater package. Dedicated background Blender 5.2 only:
  & 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' -b --threads 4 --python-exit-code 1 --python roguelite-planning/bloater-zombie/verify_bloater.py

Imports BloaterZombie_Import.fbx into a fresh file and reopens Model.blend, then checks names,
closed geometry, bounded UVs, texture load, ground alignment, origins vs joints, import-data
consistency, triangle budget, eye visibility, and belly clearance of head/hands/forearms at rest
and at the runtime's 1.3x inflation, plus an arm pose sweep. Writes verification.json.
"""
import bpy, bmesh, json, math, hashlib
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

OUT = Path(__file__).resolve().parent
DATA = json.loads((OUT / 'bloater-import-data.json').read_text())['Bloater']
C = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0)))   # Studio <-> Blender (involution)
SECTIONS = list(DATA['parts'])
EXPECTED = set(SECTIONS) | {'EyeGlow'}
INFLATE, HEAD_INFLATE = 1.3, 1.08
fails, known, report = [], [], {}

def check(ok, msg):
    if not ok:
        fails.append(msg)
    return bool(ok)

def jhead(name):
    return C @ Vector(DATA['joints'][name]['head'])

# ------------------------------------------------------------------ FBX in a fresh file
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(OUT / 'BloaterZombie_Import.fbx'))
objs = {o.name: o for o in bpy.context.scene.objects}
check(set(objs) == EXPECTED, f'object names {sorted(objs)}')
check(all(o.type == 'MESH' for o in objs.values()), 'non-mesh object in FBX')
check(len(DATA['parts']) == 15, 'import data must list exactly 15 sections')
per, world = {}, {}
for name, o in sorted(objs.items()):
    me = o.data
    world[name] = [o.matrix_world @ v.co for v in me.vertices]
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    uvs = me.uv_layers.active.data if me.uv_layers else []
    uv_ok = bool(me.uv_layers) and all(math.isfinite(c) and 0 <= c <= 1 for d in uvs for c in d.uv)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    open_edges = sum(not e.is_manifold for e in bm.edges)
    degenerate = sum(f.calc_area() < 1e-10 for f in bm.faces)
    bm.free()
    imgs = [n.image for m in me.materials if m and m.node_tree for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
    for im in imgs:
        _ = im.pixels[0]
    tex_ok = bool(imgs) and all(im.has_data and tuple(im.size) == (1024, 1024) for im in imgs)
    origin_err = (o.matrix_world.translation - jhead('Head' if name == 'EyeGlow' else name)).length
    per[name] = {'triangles': tris, 'materials': len(me.materials), 'uv_layer': me.uv_layers.active.name if me.uv_layers else None,
                 'uv_in_0_1': uv_ok, 'open_edges': open_edges, 'degenerate_faces': degenerate,
                 'texture_1024_loaded': tex_ok, 'origin_vs_joint_error': round(origin_err, 6)}
    check(len(me.materials) == 1, f'{name}: material count {len(me.materials)}')
    check(per[name]['uv_layer'] == 'PaintedAtlas', f'{name}: UV layer name')
    check(uv_ok, f'{name}: UVs outside 0..1')
    check(open_edges == 0, f'{name}: {open_edges} open edges')
    check(degenerate == 0, f'{name}: {degenerate} degenerate faces')
    check(tex_ok, f'{name}: texture did not load at 1024')
    check(origin_err < 1e-3, f'{name}: origin {origin_err:.4f} from joint head')
    check(tris < 20000, f'{name}: {tris} tris over the Roblox limit')
total = sum(p['triangles'] for p in per.values())
check(4000 <= total <= 8000, f'total triangles {total} outside 4-8k')
allz = [v.z for vs in world.values() for v in vs]
height, ground = max(allz), min(allz)
check(abs(ground) < 1e-3, f'ground {ground}')
check(abs(height - 6.0) < 0.05, f'height {height}')
check(abs(DATA['height'] - height) < 1e-3, 'import data height mismatch')
# Import data parts match the exported geometry (Studio space).
part_err = 0.0
for name in SECTIONS:
    pts = [C @ v for v in world[name]]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    part_err = max(part_err, ((lo + hi) / 2 - Vector(DATA['parts'][name]['center'])).length, ((hi - lo) - Vector(DATA['parts'][name]['size'])).length)
check(part_err < 2e-3, f'import data part bounds differ by {part_err}')
ut = world['UpperTorso']
band = [v for v in ut if 2.6 <= v.z <= 3.4]
belly_width = max(v.x for v in band) - min(v.x for v in band)
belly_depth = max(v.y for v in band) - min(v.y for v in band)
report['fbx'] = {'objects': per, 'total_triangles': total, 'height': round(height, 4), 'ground': round(ground, 6),
                 'belly_width_at_equator': round(belly_width, 3), 'belly_depth_at_equator': round(belly_depth, 3),
                 'upper_torso_bbox_width_incl_shoulders': round(max(v.x for v in ut) - min(v.x for v in ut), 3),
                 'import_data_part_bounds_max_error': round(part_err, 6)}

# ------------------------------------------------------------ triangle sets + clearance
def tris_of(name):
    me = objs[name].data; me.calc_loop_triangles()
    return [tuple(t.vertices) for t in me.loop_triangles]
TRIS = {n: tris_of(n) for n in objs}

def neck_island():
    """The Head's hidden neck seat: the shell holding Head's lowest vertex."""
    me = objs['Head'].data; vs = world['Head']
    adj = {i: set() for i in range(len(vs))}
    for e in me.edges:
        a, b = e.vertices; adj[a].add(b); adj[b].add(a)
    start = min(range(len(vs)), key=lambda i: vs[i].z)
    seen, stack = {start}, [start]
    while stack:
        for w in adj[stack.pop()]:
            if w not in seen:
                seen.add(w); stack.append(w)
    return seen
NECK = neck_island()

RAYS = (Vector((0, 0, 1)), Vector((0.3, 0.2, 1)).normalized(), Vector((-0.2, 0.4, 1)).normalized())
def is_inside(bvh, p):
    """Ray parity (majority of 3 rays): robust for the closed belly + vest shells, unlike nearest-face normals."""
    odd = 0
    for d in RAYS:
        o, c = p, 0
        while True:
            hit = bvh.ray_cast(o + d * 1e-5, d)
            if hit[0] is None:
                break
            c += 1; o = hit[0]
        odd += c % 2
    return odd >= 2

def clearance(va, ta, vb, tb):
    """Intersecting triangle pairs, vertices inside B, signed min distance of A's vertices to B."""
    if not ta:
        return {'pairs': 0, 'inside': 0, 'min': None}
    ba = BVHTree.FromPolygons(va, ta, all_triangles=True); bb = BVHTree.FromPolygons(vb, tb, all_triangles=True)
    pairs = len(ba.overlap(bb)); inside = 0; best = 1e9
    for i in {i for t in ta for i in t}:
        d = bb.find_nearest(va[i])[3]
        if is_inside(bb, va[i]):
            inside += 1; d = -d
        best = min(best, d)
    return {'pairs': pairs, 'inside': inside, 'min': round(best, 4)}

ut_pts = world['UpperTorso']
c_ut = Vector([(min(v[i] for v in ut_pts) + max(v[i] for v in ut_pts)) / 2 for i in range(3)])
hd = world['Head']
c_head = Vector([(min(v[i] for v in hd) + max(v[i] for v in hd)) / 2 for i in range(3)])
def transform(name, state):
    """Runtime inflation: UpperTorso x1.3 about its part centre, shoulder and neck joints moved by
    the same factor from that centre (arms/head ride along rigidly), Head (and its welded EyeGlow) x1.08."""
    vs = world[name]
    if state == 'rest':
        return vs
    if name == 'UpperTorso':
        return [c_ut + (v - c_ut) * INFLATE for v in vs]
    for side in ('Left', 'Right'):
        if name.startswith(side) and ('Arm' in name or 'Hand' in name):
            off = (jhead(side + 'UpperArm') - c_ut) * (INFLATE - 1)
            return [v + off for v in vs]
    if name in ('Head', 'EyeGlow'):
        off = (jhead('Head') - c_ut) * (INFLATE - 1); hc = c_head + off
        return [hc + (v + off - hc) * HEAD_INFLATE for v in vs]
    return vs

overlap = {}
for state in ('rest', 'inflated'):
    vb = transform('UpperTorso', state); tb = TRIS['UpperTorso']
    for n in ('LeftHand', 'RightHand', 'LeftLowerArm', 'RightLowerArm', 'EyeGlow'):
        r = clearance(transform(n, state), TRIS[n], vb, tb); overlap[f'{state}:{n}'] = r
        check(r['pairs'] == 0 and r['inside'] == 0, f'{state}: {n} touches the belly {r}')
    face = [t for t in TRIS['Head'] if not all(i in NECK for i in t)]
    r = clearance(transform('Head', state), face, vb, tb); overlap[f'{state}:Head(excluding hidden neck seat)'] = r
    check(r['pairs'] == 0 and r['inside'] == 0 and r['min'] >= 0.05, f'{state}: head not clear of the belly by 0.05 {r}')
    for side in ('Left', 'Right'):
        n = side + 'UpperArm'; vs = transform(n, state)
        off = (jhead(n) - c_ut) * (INFLATE - 1) if state == 'inflated' else Vector()
        S = jhead(n) + off; E = jhead(side + 'LowerArm') + off; L = (E - S).length; W = (E - S) / L
        axial = [(v - S).dot(W) / L for v in vs]   # 0 at the shoulder joint, 1 at the elbow
        # Below the fused shoulder seat (axial > 0.3) the arm must hang clear: >=0.05 at rest, >=0 at 1.3x.
        free = [t for t in TRIS[n] if min(axial[i] for i in t) > 0.3]
        r = clearance(vs, free, vb, tb); overlap[f'{state}:{n}(below shoulder seat, axial>0.3)'] = r
        need = 0.05 if state == 'rest' else 0.0
        check(r['pairs'] == 0 and r['inside'] == 0 and r['min'] >= need, f'{state}: {n} below the seat is not clear by {need}: {r}')
        bvh_p = BVHTree.FromPolygons(vb, tb, all_triangles=True); prof = {}
        for i, v in enumerate(vs):
            if axial[i] > 0:
                d = bvh_p.find_nearest(v)[3]; d = -d if is_inside(bvh_p, v) else d
                k = f'{min(int(axial[i] * 10), 10) / 10:.1f}'; prof[k] = round(min(prof.get(k, 9.0), d), 3)
        overlap[f'{state}:{n}(clearance by tenth of arm, 0=shoulder joint)'] = dict(sorted(prof.items()))
        seat = clearance(vs, TRIS[n], vb, tb)
        bvh = BVHTree.FromPolygons(vb, tb, all_triangles=True); deep = -1.0
        for i, v in enumerate(vs):
            if is_inside(bvh, v):
                deep = max(deep, axial[i])
        seat['deepest_contact_along_arm'] = round(deep, 3)
        overlap[f'{state}:{n}(shoulder seat, info)'] = seat
    for n in ('LeftUpperLeg', 'RightUpperLeg', 'LowerTorso'):   # hips are meant to sit under/inside the belly
        overlap[f'{state}:{n}(info)'] = clearance(transform(n, state), TRIS[n], vb, tb)
report['belly_clearance'] = overlap

# Arm pose sweep: ZombieMotion swings hanging arms about X (forward), small rolls, elbow flex.
def rx(deg):
    return Matrix.Rotation(math.radians(deg), 3, 'X')
def ry(deg):
    return Matrix.Rotation(math.radians(deg), 3, 'Y')
sweep = {'poses': 0, 'colliding': 0, 'min_clearance': 1e9, 'worst': None}
for state in ('rest', 'inflated'):
    vb = transform('UpperTorso', state); tb = TRIS['UpperTorso']; bvh_b = BVHTree.FromPolygons(vb, tb, all_triangles=True)
    for side in ('Left', 'Right'):
        off = (jhead(side + 'UpperArm') - c_ut) * (INFLATE - 1) if state == 'inflated' else Vector()
        S = jhead(side + 'UpperArm') + off; E = jhead(side + 'LowerArm') + off
        fa, hand = transform(side + 'LowerArm', state), transform(side + 'Hand', state)
        verts = fa + hand; tris = TRIS[side + 'LowerArm'] + [tuple(i + len(fa) for i in t) for t in TRIS[side + 'Hand']]
        for a in (-30, -15, 0, 15, 30, 45, 92, 110):
            for b in (0, 20, 40):
                for g in (-7, 0, 7):
                    Rs = rx(-a) @ ry(g); Re = rx(-b)
                    moved = [S + Rs @ (E - S + Re @ (v - E)) for v in verts]
                    bvh_a = BVHTree.FromPolygons(moved, tris, all_triangles=True)
                    hit = len(bvh_a.overlap(bvh_b)) > 0
                    dmin = min(bvh_b.find_nearest(v)[3] for v in moved[::3])
                    sweep['poses'] += 1; sweep['colliding'] += hit
                    if dmin < sweep['min_clearance']:
                        sweep['min_clearance'] = round(dmin, 4); sweep['worst'] = f'{state} {side} shoulder {a} elbow {b} roll {g}'
check(sweep['colliding'] == 0, f'arm pose sweep: {sweep["colliding"]} colliding poses')
report['arm_pose_sweep'] = sweep

# Eyes read from the front: rays straight in hit EyeGlow before Head.
bh = BVHTree.FromPolygons(world['Head'], TRIS['Head'], all_triangles=True)
be = BVHTree.FromPolygons(world['EyeGlow'], TRIS['EyeGlow'], all_triangles=True)
eg = world['EyeGlow']; visible = total_rays = 0
for s in (1, -1):
    pts = [v for v in eg if v.x * s > 0]
    cx = sum(v.x for v in pts) / len(pts); cz = sum(v.z for v in pts) / len(pts)
    for dx in (-0.08, -0.04, 0, 0.04, 0.08):
        for dz in (-0.05, -0.025, 0, 0.025):
            o = Vector((cx + dx, -5, cz + dz)); total_rays += 1
            he = be.ray_cast(o, Vector((0, 1, 0))); hh = bh.ray_cast(o, Vector((0, 1, 0)))
            if he[0] is not None and (hh[0] is None or he[3] <= hh[3] + 1e-6):
                visible += 1
report['eyes_visible_from_front'] = round(visible / total_rays, 3)
check(visible / total_rays >= 0.3, f'eyes mostly hidden ({visible}/{total_rays})')

# ------------------------------------------------------------------------ Model.blend
fbx_counts = {n: len(o.data.vertices) for n, o in objs.items()}
bpy.ops.wm.open_mainfile(filepath=str(OUT / 'Model.blend'))
rigs = [o for o in bpy.data.objects if o.type == 'ARMATURE']
blend = {'rigs': len(rigs)}
if check(len(rigs) == 1, 'Model.blend needs one preview rig'):
    rig = rigs[0]
    bones = set(rig.data.bones.keys())
    check(bones == set(SECTIONS) | {'HumanoidRootPart'}, f'rig bones {sorted(bones)}')
    blend['bones'] = len(bones)
    meshes = {o.name: o for o in bpy.data.objects if o.type == 'MESH' and o.parent == rig}
    check(set(meshes) == EXPECTED, f'rigged meshes {sorted(meshes)}')
    for n, o in meshes.items():
        group = 'Head' if n == 'EyeGlow' else n
        ok = (len(o.vertex_groups) == 1 and o.vertex_groups[0].name == group and
              all(len(v.groups) == 1 and abs(v.groups[0].weight - 1) < 1e-6 for v in o.data.vertices) and
              any(m.type == 'ARMATURE' and m.object == rig for m in o.modifiers))
        check(ok, f'{n}: rigid weight / armature modifier')
        check(len(o.data.vertices) == fbx_counts.get(n), f'{n}: blend vs FBX vertex count')
    imgs = [i for i in bpy.data.images if i.packed_file]
    for im in imgs:
        _ = im.pixels[0]
    blend['packed_textures'] = [i.name for i in imgs]
    check(imgs and all(i.has_data for i in imgs), 'Model.blend texture not packed/loaded')
report['model_blend'] = blend

tex = OUT / 'textures' / 'BaseColor.png'; fbm = OUT / 'BloaterZombie_Import.fbm' / 'BaseColor.png'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
report['files'] = {'BaseColor.png_sha256': sha(tex), 'fbm_copy_matches': fbm.exists() and sha(fbm) == sha(tex),
                   'BloaterZombie_Import.fbx_sha256': sha(OUT / 'BloaterZombie_Import.fbx')}
check(report['files']['fbm_copy_matches'], '.fbm texture copy missing or different')
report['status'] = 'PASS' if not fails else 'FAIL'
report['failures'] = fails
report['known_issues'] = known
report['studio'] = 'Blender-verified, Studio untested'
(OUT / 'verification.json').write_text(json.dumps(report, indent=1))
print('VERIFY', report['status'], json.dumps({k: report[k] for k in ('failures', 'known_issues', 'arm_pose_sweep', 'eyes_visible_from_front')}))
assert not fails, fails
