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
band = [v for v in ut if 2.0 <= v.z <= 2.6]
belly_width = max(v.x for v in band) - min(v.x for v in band)
belly_depth = max(v.y for v in band) - min(v.y for v in band)
report['fbx'] = {'objects': per, 'total_triangles': total, 'height': round(height, 4), 'ground': round(ground, 6),
                 'belly_width_widest_band_z2.0_2.6': round(belly_width, 3), 'belly_depth_widest_band_z2.0_2.6': round(belly_depth, 3),
                 'upper_torso_bbox_width_incl_shoulders': round(max(v.x for v in ut) - min(v.x for v in ut), 3),
                 'import_data_part_bounds_max_error': round(part_err, 6)}

# ------------------------------------------------------------ triangle sets + clearance
def tris_of(name):
    me = objs[name].data; me.calc_loop_triangles()
    return [tuple(t.vertices) for t in me.loop_triangles]
TRIS = {n: tris_of(n) for n in objs}

# 2026-10-09 remodel: no neck. The head sits straight down in the shoulders: its lowest 0.30
# (underside and cheek bottoms) is the seat, meant to be buried in / resting on the UpperTorso.
# Everything above the seat (face, eyes, teeth, cheek sides) must stay clear of the body.
HEAD_SEAT = 0.30
head_floor = min(v.z for v in world['Head'])
SEAT = {i for i, v in enumerate(world['Head']) if v.z < head_floor + HEAD_SEAT}
ARM_SEAT = 0.45   # upper-arm fraction (from the shoulder joint) covered by the round deltoid mass

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
    face = [t for t in TRIS['Head'] if not any(i in SEAT for i in t)]
    need = 0.05 if state == 'rest' else 0.0
    r = clearance(transform('Head', state), face, vb, tb); overlap[f'{state}:Head(above the {HEAD_SEAT} seat)'] = r
    check(r['pairs'] == 0 and r['inside'] == 0 and r['min'] >= need, f'{state}: head above the seat not clear of the body by {need} {r}')
    # Seated: no neck gap. Some of the head's underside must be inside the body, rest and 1.3x.
    hv = transform('Head', state); bvh_s = BVHTree.FromPolygons(vb, tb, all_triangles=True)
    seated = sum(is_inside(bvh_s, hv[i]) for i in SEAT)
    overlap[f'{state}:Head seat vertices inside the body'] = f'{seated}/{len(SEAT)}'
    check(seated > 0.2 * len(SEAT), f'{state}: head is not seated in the shoulders ({seated}/{len(SEAT)})')
    for side in ('Left', 'Right'):
        n = side + 'UpperArm'; vs = transform(n, state)
        off = (jhead(n) - c_ut) * (INFLATE - 1) if state == 'inflated' else Vector()
        S = jhead(n) + off; E = jhead(side + 'LowerArm') + off; L = (E - S).length; W = (E - S) / L
        axial = [(v - S).dot(W) / L for v in vs]   # 0 at the shoulder joint, 1 at the elbow
        # Below the deltoid seat (axial > ARM_SEAT) the arm must hang clear: >=0.05 at rest, >=0 at 1.3x.
        free = [t for t in TRIS[n] if min(axial[i] for i in t) > ARM_SEAT]
        r = clearance(vs, free, vb, tb); overlap[f'{state}:{n}(below deltoid seat, axial>{ARM_SEAT})'] = r
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
                    if hit:
                        sweep.setdefault('colliding_poses', []).append(f'{state} {side} shoulder {a} elbow {b} roll {g}')
                    if dmin < sweep['min_clearance']:
                        sweep['min_clearance'] = round(dmin, 4); sweep['worst'] = f'{state} {side} shoulder {a} elbow {b} roll {g}'
check(sweep['colliding'] == 0, f'arm pose sweep: {sweep["colliding"]} colliding poses')
report['arm_pose_sweep'] = sweep

# ------------------------------------------------------------- game pose sweep (ZombieMotion.bloater)
# The poses the game actually plays: Motor6D.Transform = CFrame.Angles(x, y, z) (Studio XYZ degrees)
# in each motor's axis-aligned frame, so a child turns about its joint in its parent's frame.
# The swell is applied the way Round10World does it: UpperTorso Size *= s with the Waist C1 and the
# Shoulder/Neck C0 positions scaled, which is a scale about the WAIST joint; Head x1.08 about its centre.
# Checks: arms vs belly skin and vest, head vs shoulders, thighs/shorts/shins vs the belly underside.
def rot_studio(x=0.0, y=0.0, z=0.0):
    r = Matrix.Rotation(math.radians(x), 3, 'X') @ Matrix.Rotation(math.radians(y), 3, 'Y') @ Matrix.Rotation(math.radians(z), 3, 'Z')
    return C @ r @ C   # same rotation expressed in Blender axes

def components(name):
    me = objs[name].data; n = len(me.vertices); parent = list(range(n))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    roots = [find(i) for i in range(n)]
    return roots

ut_roots = components('UpperTorso')
skin_root = max(set(ut_roots), key=ut_roots.count)
SKIN_T = [t for t in TRIS['UpperTorso'] if ut_roots[t[0]] == skin_root]
VEST_T = [t for t in TRIS['UpperTorso'] if ut_roots[t[0]] != skin_root]
WAIST = jhead('UpperTorso')

def torso_verts(state, waist_rot=None):
    s = INFLATE if state == 'inflated' else 1.0
    R = waist_rot or Matrix.Identity(3)
    return [WAIST + R @ ((v - WAIST) * s) for v in world['UpperTorso']]

def moved(name, fn):
    return [fn(v) for v in world[name]]

def pair_count(va, ta, bvh_b):
    if not ta:
        return 0
    return len(BVHTree.FromPolygons(va, ta, all_triangles=True).overlap(bvh_b))

def min_gap(va, idx, bvh_b):
    best = 9.0
    for i in idx:
        d = bvh_b.find_nearest(va[i])[3]
        if is_inside(bvh_b, va[i]):
            d = -d
        best = min(best, d)
    return best

game = {'arms': {'poses': 0, 'skin_pairs': 0, 'vest_pairs': 0, 'min_skin_gap': 9.0, 'min_vest_gap': 9.0, 'worst_skin': None, 'worst_vest': None, 'vest_hits': []},
        'head': {'poses': 0, 'pairs': 0, 'min_gap': 9.0, 'worst': None, 'min_seated': 999},
        'legs': {'poses': 0, 'poke_through': 0, 'shin_or_hem_inside': 0, 'exposed_tops': 0, 'min_hem_gap': 9.0, 'worst': None, 'hits': []}}
SH_X = (-6, 10, 28); SH_Z = (22.4, 29.6, 72.4, 75.6); EL_X = (8, 17, 26); WR_X = (-4, 10)
for state in ('rest', 'inflated'):
    s = INFLATE if state == 'inflated' else 1.0
    tv = torso_verts(state)
    bvh_skin = BVHTree.FromPolygons(tv, SKIN_T, all_triangles=True)
    bvh_vest = BVHTree.FromPolygons(tv, VEST_T, all_triangles=True)
    bvh_body = BVHTree.FromPolygons(tv, TRIS['UpperTorso'], all_triangles=True)
    # --- arms (they ride on the UpperTorso, so the waist pose does not change arm-vs-torso geometry)
    for side, sg in (('Left', 1), ('Right', -1)):
        S0, E0, W0 = jhead(side + 'UpperArm'), jhead(side + 'LowerArm'), jhead(side + 'Hand')
        S = WAIST + (S0 - WAIST) * s; off = S - S0
        ua = world[side + 'UpperArm']
        axial = [(v - S0).dot((E0 - S0).normalized()) / (E0 - S0).length for v in ua]
        ua_roots = components(side + 'UpperArm'); ua_main = ua_roots[max(range(len(ua)), key=lambda i: axial[i])]   # the block reaching the elbow
        arm_skin = [t for t in TRIS[side + 'UpperArm'] if ua_roots[t[0]] == ua_main]
        cap = [t for t in TRIS[side + 'UpperArm'] if ua_roots[t[0]] != ua_main]
        free = [t for t in arm_skin if min(axial[i] for i in t) > ARM_SEAT]
        for sx in SH_X:
            for sz in SH_Z:
                R1 = rot_studio(sx, 0, sg * -sz)
                for ex in EL_X:
                    R2 = rot_studio(ex)
                    for wx in WR_X:
                        R3 = rot_studio(wx)
                        up = lambda v: S + R1 @ (v + off - S)
                        fo = lambda v: up(E0 + R2 @ (v - E0))
                        ha = lambda v: fo(W0 + R3 @ (v - W0))
                        uav = moved(side + 'UpperArm', up)
                        cp = pair_count(uav, cap, bvh_vest)
                        game['arms']['cap_vs_vest_pairs_info'] = game['arms'].get('cap_vs_vest_pairs_info', 0) + cp
                        parts = [(uav, arm_skin, free),
                                 (moved(side + 'LowerArm', fo), TRIS[side + 'LowerArm'], TRIS[side + 'LowerArm']),
                                 (moved(side + 'Hand', ha), TRIS[side + 'Hand'], TRIS[side + 'Hand'])]
                        tag = f'{state} {side} shoulder X{sx} Z{sg * -sz:+.1f} elbow {ex} wrist {wx}'
                        game['arms']['poses'] += 1
                        sp = vp = 0; sg_gap = vg_gap = 9.0
                        for va, all_t, chk_t in parts:
                            sp += pair_count(va, chk_t, bvh_skin); vp += pair_count(va, all_t, bvh_vest)
                            idx = {i for t in chk_t for i in t}
                            sg_gap = min(sg_gap, min(bvh_skin.find_nearest(va[i])[3] for i in idx))
                            vg_gap = min(vg_gap, min(bvh_vest.find_nearest(va[i])[3] for i in {i for t in all_t for i in t}))
                        A = game['arms']; A['skin_pairs'] += sp; A['vest_pairs'] += vp
                        if vp and len(A['vest_hits']) < 12:
                            A['vest_hits'].append(f'{tag}: {vp} pairs')
                        if sp:
                            A.setdefault('skin_hits', []).append(f'{tag}: {sp} pairs')
                        if sg_gap < A['min_skin_gap']:
                            A['min_skin_gap'] = round(sg_gap, 4); A['worst_skin'] = tag
                        if vg_gap < A['min_vest_gap']:
                            A['min_vest_gap'] = round(vg_gap, 4); A['worst_vest'] = tag
    # --- head on the neck (rides on the UpperTorso)
    N0 = jhead('Head'); N = WAIST + (N0 - WAIST) * s; off = N - N0; hc = c_head + off
    hs = HEAD_INFLATE if state == 'inflated' else 1.0
    face = [t for t in TRIS['Head'] if not any(i in SEAT for i in t)]
    fidx = {i for t in face for i in t}
    for nx in (0, 8, 16):
        for nz in (-4, 0, 4):
            Rn = rot_studio(nx, 0, nz)
            hv = [N + Rn @ (hc + (v + off - hc) * hs - N) for v in world['Head']]
            pairs = pair_count(hv, face, bvh_body)
            gap = min(bvh_body.find_nearest(hv[i])[3] * (-1 if is_inside(bvh_body, hv[i]) else 1) for i in fidx)
            seated = sum(is_inside(bvh_skin, hv[i]) for i in SEAT)
            H = game['head']; H['poses'] += 1; H['pairs'] += pairs
            H['min_seated'] = min(H['min_seated'], seated)
            if gap < H['min_gap']:
                H['min_gap'] = round(gap, 4); H['worst'] = f'{state} neck X{nx} Z{nz}'
    # --- legs under the belly (LowerTorso is the parent; the belly moves on the waist)
    for wx, wy, wz in ((0, 0, 0), (9, 3, 8), (9, -3, -8), (-4, 3, -8), (-4, -3, 8)):
        Rw = rot_studio(wx, wy, wz)
        bv = torso_verts(state, Rw)
        bvh_b = BVHTree.FromPolygons(bv, SKIN_T, all_triangles=True)
        lt = world['LowerTorso']; lt_top = max(v.z for v in lt)
        for side, sg in (('Left', 1), ('Right', -1)):
            H0, K0 = jhead(side + 'UpperLeg'), jhead(side + 'LowerLeg')
            ul = world[side + 'UpperLeg']; top_z = max(v.z for v in ul); hem_z = min(v.z for v in ul)
            for hx in (-18, 4, 26):
                for hz in (1, -7):
                    Rh = rot_studio(hx, 0, sg * hz)
                    for kx in (0, -36):
                        Rk = rot_studio(kx)
                        th = lambda v: H0 + Rh @ (v - H0)
                        sh = lambda v: th(K0 + Rk @ (v - K0))
                        thv = moved(side + 'UpperLeg', th); shv = moved(side + 'LowerLeg', sh)
                        tag = f'{state} waist ({wx},{wy},{wz}) {side} hip X{hx} Z{sg * hz} knee {kx}'
                        L = game['legs']; L['poses'] += 1
                        poke = exposed = inside_low = 0; hem_gap = 9.0
                        for i, v in enumerate(thv):
                            ins = is_inside(bvh_b, v)
                            if not ins and bvh_b.ray_cast(v + Vector((0, 0, -1e-4)), Vector((0, 0, -1)))[0] is not None:
                                poke += 1   # outside the belly yet above belly surface: shows through
                            if ul[i].z > top_z - 0.02 and not ins:
                                exposed += 1   # the shorts' top rim must stay tucked under the belly
                            if ul[i].z < hem_z + 0.25:
                                d = bvh_b.find_nearest(v)[3]
                                if ins:
                                    inside_low += 1; d = -d
                                hem_gap = min(hem_gap, d)
                        where = None
                        bvh_th = BVHTree.FromPolygons(thv, TRIS[side + 'UpperLeg'], all_triangles=True)
                        for v in shv:   # shin points tucked inside the shorts tube are hidden
                            if is_inside(bvh_b, v) and not is_inside(bvh_th, v):
                                inside_low += 1; where = where or tuple(round(c, 2) for c in v)
                        L['poke_through'] += poke; L['exposed_tops'] += exposed; L['shin_or_hem_inside'] += inside_low
                        if (poke or exposed or inside_low) and len(L['hits']) < 12:
                            L['hits'].append(f'{tag}: poke {poke} exposed {exposed} low-inside {inside_low}' + (f' shin at {where}' if where else ''))
                        if hem_gap < L['min_hem_gap']:
                            L['min_hem_gap'] = round(hem_gap, 4); L['worst'] = tag
        # LowerTorso top must stay under the belly too
        exp_lt = sum(1 for v in lt if v.z > lt_top - 0.02 and not is_inside(bvh_b, v))
        game['legs']['exposed_tops'] += exp_lt
        if exp_lt:
            game['legs']['hits'].append(f'{state} waist ({wx},{wy},{wz}): LowerTorso top exposed {exp_lt}')
report['game_pose_sweep'] = game
A, Hd, L = game['arms'], game['head'], game['legs']
check(A['skin_pairs'] == 0, f'game sweep: arms cut the belly skin ({A["skin_pairs"]} pairs) {A.get("skin_hits", [])[:4]}')
check(A['vest_pairs'] == 0, f'game sweep: arms cut the vest ({A["vest_pairs"]} pairs) {A["vest_hits"][:4]}')
check(Hd['pairs'] == 0 and Hd['min_gap'] >= 0, f'game sweep: head above the seat touches the shoulders {Hd}')
check(Hd['min_seated'] > 0, f'game sweep: head lifts off its seat {Hd}')
check(L['poke_through'] == 0 and L['exposed_tops'] == 0 and L['shin_or_hem_inside'] == 0, f'game sweep: legs vs belly {L["hits"][:4]}')

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
check(visible / total_rays >= 0.6, f'eyes mostly hidden ({visible}/{total_rays})')

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
print('VERIFY', report['status'], json.dumps({k: report[k] for k in ('failures', 'known_issues', 'arm_pose_sweep', 'game_pose_sweep', 'eyes_visible_from_front')}))
assert not fails, fails
