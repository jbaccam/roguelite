"""Pizza Cutter (asset 42, Chef kitchen family) - self-contained Blender 5.2 generator.

Run from PowerShell (background only, never against an open interactive scene):
  & "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --threads 4 --python build_pizza_cutter.py

Output: ../../assets/42-pizza-cutter/ (Reference, Model.blend/.fbx/.glb, BaseColor, Preview, Alternate,
Spin_Check, validation.json, README.md).

Two export meshes share ONE 1024px base-colour atlas and one material:
  Handle - wood grip, lanyard hole, rivets, guard collar, single gunmetal arm, axle, both axle nuts.
           Origin = handhold centre (wood grip midpoint), same convention as the Frying Pan's pivot.
  Wheel  - regular 24-facet steel wheel with a two-facet sharpened rim. Origin = axle centre.
           Spin axis = local +Y in Blender (identity rotation) -> local Z of the MeshPart after FBX import.

Built upright like the Spatula: +Z = wheel end, handle at the bottom, wheel face in the XZ plane.
Blender (x, y, z) -> FBX/Roblox (x, z, -y) with axis_forward='-Z', axis_up='Y' (the siblings' settings).
"""
import bpy, bmesh, math, json, shutil, tempfile, os
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from bpy_extras.object_utils import world_to_camera_view
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]                     # weapon-models/
OUT = ROOT / 'assets' / '42-pizza-cutter'
CONCEPT = ROOT / 'concepts' / 'chef-2026-10-09' / 'pizza-cutter-concept.png'
GENERATOR = 'roguelite-planning/weapon-models/batches/chef/build_pizza_cutter.py'
TAU = math.tau

# ---------------------------------------------------------------- dimensions (Blender units)
# Concept FRONT view: 707 px from wheel top to handle bottom -> 4.2 BU (1 px = 0.00594 BU).
# The Pan is 4.55 BU long and the Spatula 3.74 BU tall, so the cutter sits between them.
GRIP_Z = 0.96                          # wood grip midpoint -> Handle origin, moved to world origin
GUARD_Z0, GUARD_Z1 = 1.92, 2.06        # guard collar slab
GUARD_W, GUARD_D = 0.80, 0.58
WHEEL_R, WHEEL_N = 1.04, 24            # diameter 2.08 = ~49% of total length
WHEEL_Z = GUARD_Z1 + 0.07 + WHEEL_R    # 0.07 BU of air between wheel edge and guard
HUB_HALF = 0.115                       # wheel half thickness at the hub (side view: 42 px)
GAP = 0.012                            # running clearance wheel <-> arm and wheel <-> far nut
ARM_Y1 = 0.005                         # arm inner face (towards the wheel)
ARM_Y0 = ARM_Y1 - 0.14                 # arm outer face; the arm is on the -Y (front camera) side
WHEEL_Y = ARM_Y1 + GAP + HUB_HALF      # 0.132: wheel rides beside the single arm, as in the SIDE view
AXLE_R, BORE_R = 0.055, 0.07
NUT_R, NUT_T = 0.15, 0.13
ARM_HALF_W = 0.18
RIVET_Z = (0.832, 1.586)               # concept front view rivet centres
HOLE_Z, HOLE_R = 0.28, 0.10            # octagonal lanyard hole
SPIN_TEST_DEG = 37.0
HERO_TILT_DEG = -38.0                  # review-only lean (wheel upper-left like the concept hero)

# ---------------------------------------------------------------- palette (sRGB, before the game's +0.3 saturation)
WOOD = (0.435, 0.265, 0.137)           # sibling walnut (.40,.245,.135) nudged warmer/lighter (concept 121,83,57 rendered)
WOOD_HOLE = (0.20, 0.12, 0.065)
GUNMETAL = (0.19, 0.188, 0.186)        # warm-neutral dark gunmetal (concept arm renders ~69)
HARDWARE = (0.40, 0.39, 0.375)         # nuts, rivets, axle: light steel like the concept
WHEEL_FACE = (0.445, 0.434, 0.416)     # concept face renders 139,135,131
WHEEL_BEVEL = (0.535, 0.53, 0.515)
WHEEL_HI = (0.70, 0.695, 0.68)         # rim edge highlight


def s2l(v):
    return ((v + .055) / 1.055) ** 2.4 if v > .04045 else v / 12.92


def col(rgb, k=1.0):
    return tuple(s2l(min(1.0, c * k)) for c in rgb) + (1.0,)


# ---------------------------------------------------------------- geometry helpers
def make_mesh(name, verts, faces, mats, face_mats, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    for m in mats:
        me.materials.append(m)
    for p, mi in zip(me.polygons, face_mats):
        p.material_index = mi
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    return o


def revolve_y(profile, n, closed=False, caps=True, phase=0.0, seg_mats=None, cap_mat=0, offset=(0, 0, 0)):
    """Revolve (radius, y) points about an axis parallel to Y. Angle 0 = +X, 90 deg = +Z."""
    ox, oy, oz = offset
    verts = [(ox + r * math.cos(phase + TAU * i / n), oy + y, oz + r * math.sin(phase + TAU * i / n))
             for r, y in profile for i in range(n)]
    m = len(profile); faces = []; fm = []
    for j in range(m if closed else m - 1):
        j2 = (j + 1) % m
        for i in range(n):
            i2 = (i + 1) % n
            faces.append((j * n + i, j * n + i2, j2 * n + i2, j2 * n + i))
            fm.append(seg_mats[j] if seg_mats else 0)
    if caps and not closed:
        faces.append(tuple(range(n))); fm.append(cap_mat)
        faces.append(tuple(range((m - 1) * n, m * n))); fm.append(cap_mat)
    return verts, faces, fm


def prism_y(outline, y0, y1):
    n = len(outline)
    verts = [(x, y0, z) for x, z in outline] + [(x, y1, z) for x, z in outline]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return verts, faces


def oct_ring(w, d, c):
    hw, hd = w / 2, d / 2
    return [(hw - c, -hd), (hw, -hd + c), (hw, hd - c), (hw - c, hd),
            (-hw + c, hd), (-hw, hd - c), (-hw, -hd + c), (-hw + c, -hd)]


def loft_z(sections):
    rings = [[(x, y, z) for x, y in oct_ring(w, d, c)] for z, w, d, c in sections]
    n = 8; verts = [v for r in rings for v in r]; faces = []
    for j in range(len(rings) - 1):
        for i in range(n):
            i2 = (i + 1) % n
            faces.append((j * n + i, j * n + i2, (j + 1) * n + i2, (j + 1) * n + i))
    faces.append(tuple(range(n)))
    faces.append(tuple(range((len(rings) - 1) * n, len(rings) * n)))
    return verts, faces


def activate(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def apply_mod(o, mod):
    activate(o)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def bevel(o, width, angle_deg=None):
    mod = o.modifiers.new('Broad single-segment bevel', 'BEVEL')
    mod.width = width; mod.segments = 1
    if angle_deg is None:
        mod.limit_method = 'NONE'
    else:
        mod.limit_method = 'ANGLE'; mod.angle_limit = math.radians(angle_deg)
    apply_mod(o, mod)


# ---------------------------------------------------------------- bake-only painterly materials
def node_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m, nt, em


def ramp(nt, stops, interp='LINEAR'):
    r = nt.nodes.new('ShaderNodeValToRGB'); cr = r.color_ramp; cr.interpolation = interp
    cr.elements[0].position = stops[0][0]; cr.elements[0].color = stops[0][1]
    cr.elements[1].position = stops[-1][0]; cr.elements[1].color = stops[-1][1]
    for pos, c in stops[1:-1]:
        e = cr.elements.new(pos); e.color = c
    return r


def patch_value(nt, scale, smooth=0.75):
    """Soft Voronoi patches -> 0..1 value; mapped to 2-3 flat plateaus (painterly, no noise)."""
    tc = nt.nodes.new('ShaderNodeTexCoord')
    vo = nt.nodes.new('ShaderNodeTexVoronoi'); vo.feature = 'SMOOTH_F1'
    vo.inputs['Scale'].default_value = scale
    vo.inputs['Smoothness'].default_value = smooth
    nt.links.new(tc.outputs['Object'], vo.inputs['Vector'])
    bw = nt.nodes.new('ShaderNodeRGBToBW'); nt.links.new(vo.outputs['Color'], bw.inputs[0])
    return bw.outputs[0], tc


def plateaus(base, lo, hi):
    """Three values (lo/base/hi multipliers) with short soft transitions."""
    return [(0.0, col(base, lo)), (0.40, col(base, lo)), (0.46, col(base)), (0.56, col(base)),
            (0.62, col(base, hi)), (1.0, col(base, hi))]


def mul(nt, a, b):
    vm = nt.nodes.new('ShaderNodeVectorMath'); vm.operation = 'MULTIPLY'
    nt.links.new(a, vm.inputs[0]); nt.links.new(b, vm.inputs[1])
    return vm.outputs[0]


def mat_patchy(name, base, lo, hi, scale):
    m, nt, em = node_mat(name)
    v, _ = patch_value(nt, scale)
    r = ramp(nt, plateaus(base, lo, hi)); nt.links.new(v, r.inputs[0])
    nt.links.new(r.outputs[0], em.inputs['Color'])
    return m


def mat_wood(name):
    """Long grain bands (darker) along the grip + very soft patches."""
    m, nt, em = node_mat(name)
    v, tc = patch_value(nt, 2.4)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['Object'], sep.inputs[0])
    u = nt.nodes.new('ShaderNodeMath'); u.operation = 'MULTIPLY_ADD'
    nt.links.new(sep.outputs['Y'], u.inputs[0]); u.inputs[1].default_value = 0.85
    nt.links.new(sep.outputs['X'], u.inputs[2])
    zz = nt.nodes.new('ShaderNodeMath'); zz.operation = 'MULTIPLY'
    nt.links.new(sep.outputs['Z'], zz.inputs[0]); zz.inputs[1].default_value = 0.12
    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(u.outputs[0], comb.inputs['X']); nt.links.new(zz.outputs[0], comb.inputs['Z'])
    wave = nt.nodes.new('ShaderNodeTexWave'); wave.wave_type = 'BANDS'; wave.bands_direction = 'X'
    wave.inputs['Scale'].default_value = 1.25
    wave.inputs['Distortion'].default_value = 3.0
    wave.inputs['Detail'].default_value = 1.0
    nt.links.new(comb.outputs[0], wave.inputs['Vector'])
    grain = ramp(nt, [(0.0, col(WOOD, 0.87)), (0.08, col(WOOD, 0.87)), (0.15, col(WOOD)),
                      (0.84, col(WOOD)), (0.90, col(WOOD, 1.05)), (1.0, col(WOOD, 1.05))])
    nt.links.new(wave.outputs['Fac'], grain.inputs[0])
    soft = ramp(nt, [(0.0, (0.95,) * 3 + (1,)), (0.40, (0.95,) * 3 + (1,)), (0.46, (1, 1, 1, 1)),
                     (0.56, (1, 1, 1, 1)), (0.62, (1.04,) * 3 + (1,)), (1.0, (1.04,) * 3 + (1,))])
    nt.links.new(v, soft.inputs[0])
    nt.links.new(mul(nt, grain.outputs[0], soft.outputs[0]), em.inputs['Color'])
    return m


def mat_wheel_bevel(name):
    """Light bevel band whose outer part brightens into the sharpened edge highlight."""
    m, nt, em = node_mat(name)
    v, tc = patch_value(nt, 3.0)
    flat = nt.nodes.new('ShaderNodeVectorMath'); flat.operation = 'MULTIPLY'
    nt.links.new(tc.outputs['Object'], flat.inputs[0]); flat.inputs[1].default_value = (1, 0, 1)
    ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'
    nt.links.new(flat.outputs[0], ln.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.inputs['From Min'].default_value = 0.86 * WHEEL_R; mr.inputs['From Max'].default_value = WHEEL_R
    nt.links.new(ln.outputs['Value'], mr.inputs['Value'])
    band = ramp(nt, [(0.0, col(WHEEL_BEVEL)), (0.62, col(WHEEL_BEVEL)), (0.80, col(WHEEL_HI)), (1.0, col(WHEEL_HI))])
    nt.links.new(mr.outputs['Result'], band.inputs[0])
    soft = ramp(nt, [(0.0, (0.96,) * 3 + (1,)), (0.40, (0.96,) * 3 + (1,)), (0.46, (1, 1, 1, 1)),
                     (0.56, (1, 1, 1, 1)), (0.62, (1.03,) * 3 + (1,)), (1.0, (1.03,) * 3 + (1,))])
    nt.links.new(v, soft.inputs[0])
    nt.links.new(mul(nt, band.outputs[0], soft.outputs[0]), em.inputs['Color'])
    return m


def mat_flat(name, rgb):
    m, nt, em = node_mat(name)
    em.inputs['Color'].default_value = col(rgb)
    return m


# ---------------------------------------------------------------- build
def build_handle(coll, M):
    parts = []

    def part(name, verts, faces, mats, fm):
        o = make_mesh(name, verts, faces, mats, fm, coll)
        parts.append(o)
        return o

    # Wood grip: chamfered-octagon loft, slight swell, chamfered butt, top tucked into the guard.
    v, f = loft_z([(0.00, 0.42, 0.31, 0.075), (0.12, 0.565, 0.41, 0.09), (1.00, 0.585, 0.425, 0.09),
                   (1.84, 0.595, 0.43, 0.09), (1.95, 0.55, 0.40, 0.08)])
    wood = part('Wood grip', v, f, [M['wood']], [0] * len(f))
    v, f, fm = revolve_y([(HOLE_R, -1.0), (HOLE_R, 1.0)], 8, phase=TAU / 16, offset=(0, 0, HOLE_Z))
    cutter = make_mesh('Lanyard hole cutter', v, f, [M['wood_hole']], fm, coll)
    mod = wood.modifiers.new('Lanyard hole', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'; mod.solver = 'EXACT'; mod.object = cutter
    try:
        mod.material_mode = 'TRANSFER'
    except Exception:
        pass
    apply_mod(wood, mod)
    bpy.data.objects.remove(cutter, do_unlink=True)
    bevel(wood, 0.012, 50)                 # softens the hole rim and butt, keeps octagon facets crisp

    # Guard collar slab with a broad single chamfer on every edge.
    x, y = GUARD_W / 2, GUARD_D / 2
    v = [(sx * x, sy * y, z) for z in (GUARD_Z0, GUARD_Z1) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    f = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    guard = part('Guard collar', v, f, [M['gunmetal']], [0] * 6)
    bevel(guard, 0.032)

    # Single gunmetal arm: flared base inside the guard, straight bar, round end concentric with the axle.
    outline = [(-0.20, 1.97), (0.20, 1.97), (ARM_HALF_W, 2.30)]
    outline += [(ARM_HALF_W * math.cos(a), WHEEL_Z + ARM_HALF_W * math.sin(a)) for a in np.linspace(0, math.pi, 9)]
    outline += [(-ARM_HALF_W, 2.30)]
    v, f = prism_y(outline, ARM_Y0, ARM_Y1)
    arm = part('Arm', v, f, [M['gunmetal']], [0] * len(f))
    bevel(arm, 0.022, 30)

    # Axle through arm, wheel bore and both nuts (all static: they stay on Handle).
    v, f, fm = revolve_y([(AXLE_R, -0.20), (AXLE_R, 0.33)], 12, offset=(0, 0, WHEEL_Z))
    part('Axle', v, f, [M['hardware']], fm)
    near = [(NUT_R, ARM_Y0 + 0.005), (NUT_R, ARM_Y0 + 0.005 - NUT_T + 0.029), (NUT_R * 0.79, ARM_Y0 + 0.005 - NUT_T)]
    v, f, fm = revolve_y(near, 6, offset=(0, 0, WHEEL_Z))
    part('Axle nut (arm side)', v, f, [M['hardware']], fm)
    y0 = WHEEL_Y + HUB_HALF + GAP
    far = [(NUT_R, y0), (NUT_R, y0 + NUT_T - 0.029), (NUT_R * 0.79, y0 + NUT_T)]
    v, f, fm = revolve_y(far, 6, offset=(0, 0, WHEEL_Z))
    part('Axle nut (far side)', v, f, [M['hardware']], fm)

    # Two through-rivets: hex heads on both faces of the grip.
    for z in RIVET_Z:
        for s in (-1, 1):
            prof = [(0.095, s * 0.195), (0.095, s * 0.238), (0.066, s * 0.262)]
            v, f, fm = revolve_y(prof, 6, phase=TAU / 12, offset=(0, 0, z))
            part('Rivet %s %.2f' % ('front' if s < 0 else 'back', z), v, f, [M['hardware']], fm)

    # Named vertex groups keep the assembled parts identifiable after the join.
    for o in parts:
        g = o.vertex_groups.new(name=o.name)
        g.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = wood
    bpy.ops.object.join()
    h = bpy.context.view_layer.objects.active
    h.name = 'Handle'; h.data.name = 'Handle'
    h.data.transform(Matrix.Translation((0, 0, -GRIP_Z)))   # grip centre -> origin
    h.location = (0, 0, 0)
    return h


def build_wheel(coll, M):
    R = WHEEL_R
    # Closed lathe loop (radius, y): bore, flat face, first rim facet, sharpened bevel, edge land, mirror.
    prof = [(BORE_R, -HUB_HALF), (BORE_R, HUB_HALF), (0.66 * R, 0.105), (0.86 * R, 0.075), (R, 0.014),
            (R, -0.014), (0.86 * R, -0.075), (0.66 * R, -0.105)]
    seg = [0, 0, 0, 1, 2, 1, 0, 0]   # face, face, face, bevel, edge, bevel, face, face
    v, f, fm = revolve_y(prof, WHEEL_N, closed=True, caps=False, seg_mats=seg)
    w = make_mesh('Wheel', v, f, [M['wheel_face'], M['wheel_bevel'], M['wheel_edge']], fm, coll)
    w.location = (0, WHEEL_Y, WHEEL_Z - GRIP_Z)
    return w


def finish_topology(o):
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:   # deterministic triangulation for importers; quads stay quads
        bmesh.ops.triangulate(bm, faces=ngons, quad_method='BEAUTY', ngon_method='BEAUTY')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data); bm.free()
    for p in o.data.polygons:
        p.use_smooth = False


# ---------------------------------------------------------------- checks
def topology(o):
    bm = bmesh.new(); bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    winding_bad = 0
    for e in bm.edges:
        if len(e.link_loops) == 2 and e.link_loops[0].vert == e.link_loops[1].vert:
            winding_bad += 1
    # Shell orientation: signed volume of each connected shell must be positive (outward normals).
    seen = set(); shells = []; inverted = 0
    for f in bm.faces:
        if f.index in seen:
            continue
        stack = [f]; shell = []; seen.add(f.index)
        while stack:
            g = stack.pop(); shell.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index); stack.append(h)
        vol = 0.0
        for g in shell:
            vs = [l.vert.co for l in g.loops]
            for i in range(1, len(vs) - 1):
                vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6
        shells.append(vol)
        inverted += vol <= 0
    r = {
        'vertices': len(bm.verts), 'faces': len(bm.faces),
        'triangles': sum(len(f.verts) - 2 for f in bm.faces),
        'max_face_sides': max(len(f.verts) for f in bm.faces),
        'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
        'boundary_edges': sum(e.is_boundary for e in bm.edges),
        'loose_vertices': sum(not v.link_edges for v in bm.verts),
        'loose_edges': sum(not e.link_faces for e in bm.edges),
        'zero_area_faces': sum(f.calc_area() < 1e-9 for f in bm.faces),
        'inconsistent_winding_edges': winding_bad,
        'closed_shells': len(shells), 'inward_facing_shells': inverted,
        'flat_shaded': all(not p.use_smooth for p in o.data.polygons),
    }
    bm.free()
    return r


def wheel_checks(o):
    co = np.array([v.co[:] for v in o.data.vertices])
    rad = np.hypot(co[:, 0], co[:, 2]); ang = np.degrees(np.arctan2(co[:, 2], co[:, 0])) % 360
    rings = {}
    for i in range(len(co)):
        rings.setdefault((round(rad[i], 4), round(co[i, 1], 4)), []).append(i)
    step = 360.0 / WHEEL_N; worst_step = 0.0; worst_r = 0.0
    for idx in rings.values():
        a = np.sort(ang[idx]); d = np.diff(np.concatenate([a, [a[0] + 360]]))
        worst_step = max(worst_step, float(np.abs(d - step).max()))
        worst_r = max(worst_r, float(rad[idx].max() - rad[idx].min()))
    c = co - co.mean(0); evals, evecs = np.linalg.eigh(c.T @ c)
    axis = evecs[:, 0]
    return {
        'facets_N': WHEEL_N, 'profile_rings': len(rings),
        'all_rings_have_N_vertices': all(len(v) == WHEEL_N for v in rings.values()),
        'max_angular_step_error_deg': worst_step, 'max_ring_radius_spread': worst_r,
        'local_vertex_centroid': [round(float(x), 7) for x in co.mean(0)],
        'local_bounds_center': [round(float(x), 7) for x in (co.min(0) + co.max(0)) / 2],
        'principal_axis_local': [round(float(x), 6) for x in axis],
        'principal_axis_is_local_Y': bool(abs(axis[1]) > 0.999999),
        'outer_radius': float(rad.max()), 'diameter': float(2 * rad.max()),
        'hub_thickness': float(co[:, 1].max() - co[:, 1].min()),
    }


def world_bvh(o, M=None):
    M = M if M is not None else o.matrix_world
    verts = [M @ v.co for v in o.data.vertices]
    return verts, BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in o.data.polygons])


def clearance(handle, wheel, deg):
    M = wheel.matrix_world @ Matrix.Rotation(math.radians(deg), 4, 'Y')
    hv, hb = world_bvh(handle); wv, wb = world_bvh(wheel, M)
    gap_w = min(hb.find_nearest(v)[3] for v in wv)
    gap_h = min(wb.find_nearest(v)[3] for v in hv)
    return {'wheel_rotation_deg': deg, 'intersecting_face_pairs': len(hb.overlap(wb)),
            'min_vertex_to_surface_gap': round(min(gap_w, gap_h), 5)}


# ---------------------------------------------------------------- review stage
def look(direction):
    f = Vector(direction).normalized()
    q = f.to_track_quat('-Z', 'Y'); R = q.to_matrix()
    return q, R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0)), f


def frame(cam, direction, pts, aspect, margin, drop=0.0):
    q, right, up, f = look(direction)
    pr = [p.dot(right) for p in pts]; pu = [p.dot(up) for p in pts]; pf = [p.dot(f) for p in pts]
    er, eu = max(pr) - min(pr), max(pu) - min(pu)
    scale = (max(er, eu * aspect) if aspect >= 1 else max(eu, er / aspect)) * margin
    cam.data.ortho_scale = scale
    cr, cu = (max(pr) + min(pr)) / 2, (max(pu) + min(pu)) / 2 - drop * scale
    cam.location = right * cr + up * cu + f * (min(pf) - 12.0)
    cam.rotation_euler = q.to_euler()


def world_pts(objs):
    return [o.matrix_world @ v.co for o in objs for v in o.data.vertices]


def render(scene, path, w, h):
    scene.render.resolution_x = w; scene.render.resolution_y = h
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def load_px(path):
    img = bpy.data.images.load(str(path)); w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)


def save_px(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new('composite', w, h, alpha=False)
    img.pixels.foreach_set(arr.astype(np.float32).ravel())
    img.filepath_raw = str(path); img.file_format = 'PNG'; img.save()
    bpy.data.images.remove(img)


# ---------------------------------------------------------------- reimport
def reimport(path, kind, expect):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if kind == 'fbx':
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.view_layer.update()
    objs = list(bpy.context.scene.objects)
    meshes = [o for o in objs if o.type == 'MESH']
    res = {'mesh_objects': len(meshes), 'mesh_names': sorted(o.name for o in meshes),
           'non_mesh_objects': sorted(o.type for o in objs if o.type != 'MESH'), 'objects': {}}
    for o in meshes:
        me = o.data
        imgs = [n.image for m in me.materials if m and m.node_tree for n in m.node_tree.nodes
                if n.type == 'TEX_IMAGE' and n.image]
        W = np.array([(o.matrix_world @ v.co)[:] for v in me.vertices])
        res['objects'][o.name] = {
            'vertices': len(me.vertices), 'triangles': sum(len(p.vertices) - 2 for p in me.polygons),
            'uv_layers': len(me.uv_layers), 'materials': len(me.materials),
            'image_texture': bool(imgs), 'image_size': list(imgs[0].size) if imgs else None,
            'world_bounds_min': [round(float(x), 4) for x in W.min(0)],
            'world_bounds_max': [round(float(x), 4) for x in W.max(0)],
            'origin_world': [round(float(x), 4) for x in o.matrix_world.translation],
        }
    h = next((o for o in meshes if o.name.startswith('Handle')), None)
    w = next((o for o in meshes if o.name.startswith('Wheel')), None)
    if h and w:
        hb = res['objects'][h.name]
        scale = (hb['world_bounds_max'][2] - hb['world_bounds_min'][2]) / expect['handle_height']
        W = np.array([(w.matrix_world @ v.co)[:] for v in w.data.vertices]) / scale
        c = W - W.mean(0); evals, evecs = np.linalg.eigh(c.T @ c); axis = evecs[:, 0]
        origin = np.array(w.matrix_world.translation[:]) / scale
        res['unit_scale_vs_source'] = round(scale, 5)
        res['wheel_origin_error_vs_axle'] = round(float(np.linalg.norm(origin - expect['axle'])), 6)
        res['wheel_centroid_error_vs_axle'] = round(float(np.linalg.norm(W.mean(0) - expect['axle'])), 6)
        res['wheel_world_axis'] = [round(float(x), 5) for x in axis]
        res['wheel_axis_is_blender_Y'] = bool(abs(axis[1]) > 0.99999)
        res['handle_origin_at_grip'] = bool(np.linalg.norm(np.array(h.matrix_world.translation[:]) / scale) < 1e-4)
    res['all_have_uv'] = all(v['uv_layers'] > 0 for v in res['objects'].values())
    res['all_have_image'] = all(v['image_texture'] for v in res['objects'].values())
    return res


# ---------------------------------------------------------------- main
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CONCEPT, OUT / 'Reference.png')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    asset = bpy.data.collections.new('Pizza Cutter | Export geometry')
    scene.collection.children.link(asset)

    M = {'wood': mat_wood('bake Wood grip'), 'wood_hole': mat_flat('bake Wood hole', WOOD_HOLE),
         'gunmetal': mat_patchy('bake Gunmetal arm', GUNMETAL, 0.92, 1.08, 3.0),
         'hardware': mat_patchy('bake Light steel hardware', HARDWARE, 0.94, 1.06, 6.0),
         'wheel_face': mat_patchy('bake Wheel face', WHEEL_FACE, 0.965, 1.03, 2.2),
         'wheel_bevel': mat_wheel_bevel('bake Wheel bevel'),
         'wheel_edge': mat_flat('bake Wheel edge', WHEEL_HI)}

    handle = build_handle(asset, M)
    wheel = build_wheel(asset, M)
    for o in (handle, wheel):
        finish_topology(o)

    # One shared UV layout for both meshes (multi-object edit packs them together), one atlas.
    bpy.ops.object.select_all(action='DESELECT')
    handle.select_set(True); wheel.select_set(True); bpy.context.view_layer.objects.active = handle
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.012)
    bpy.ops.object.mode_set(mode='OBJECT')

    atlas = bpy.data.images.new('PizzaCutter_BaseColor', 1024, 1024, alpha=False)
    atlas.colorspace_settings.name = 'sRGB'
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 1
    scene.render.bake.margin = 6; scene.render.bake.use_clear = True
    for m in M.values():
        tex = m.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = atlas; m.node_tree.nodes.active = tex
    bpy.ops.object.bake(type='EMIT')
    atlas.filepath_raw = str(OUT / 'BaseColor.png'); atlas.file_format = 'PNG'; atlas.save(); atlas.pack()

    final = bpy.data.materials.new('PizzaCutter | portable baked base color'); final.use_nodes = True
    bsdf = final.node_tree.nodes.get('Principled BSDF')
    tex = final.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = atlas
    final.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.78
    for o in (handle, wheel):
        o.data.materials.clear(); o.data.materials.append(final)
        for p in o.data.polygons:
            p.material_index = 0
    for m in M.values():
        bpy.data.materials.remove(m)

    handle['pivot'] = 'Handhold center (wood grip midpoint), same convention as the Frying Pan'
    wheel['pivot'] = 'Axle center'
    wheel['spin_axis_blender'] = 'local +Y (object rotation is identity)'
    wheel['spin_axis_roblox'] = 'MeshPart local Z (Blender +Y -> Roblox -Z with axis_forward=-Z, axis_up=Y)'
    for o in (handle, wheel):
        o['generator'] = GENERATOR; o['source_reference'] = 'Reference.png'

    # ---- exports: asset geometry only
    bpy.ops.object.select_all(action='DESELECT')
    handle.select_set(True); wheel.select_set(True); bpy.context.view_layer.objects.active = handle
    bpy.ops.export_scene.fbx(filepath=str(OUT / 'Model.fbx'), use_selection=True, object_types={'MESH'},
                             bake_anim=False, add_leaf_bones=False, axis_forward='-Z', axis_up='Y',
                             path_mode='COPY', embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / 'Model.glb'), use_selection=True, export_format='GLB',
                              export_animations=False)

    # ---- checks on the authored meshes
    axle_world = np.array(wheel.matrix_world.translation[:])
    stats = {'Handle': topology(handle), 'Wheel': topology(wheel)}
    wcheck = wheel_checks(wheel)
    clear = [clearance(handle, wheel, 0.0), clearance(handle, wheel, SPIN_TEST_DEG)]
    hb = np.array(world_pts([handle])); wb = np.array(world_pts([wheel])); allb = np.vstack([hb, wb])
    bounds = {'assembly_size': [round(float(x), 4) for x in allb.max(0) - allb.min(0)],
              'assembly_min': [round(float(x), 4) for x in allb.min(0)],
              'assembly_max': [round(float(x), 4) for x in allb.max(0)],
              'handle_size': [round(float(x), 4) for x in hb.max(0) - hb.min(0)],
              'wheel_size': [round(float(x), 4) for x in wb.max(0) - wb.min(0)]}
    handle_center = (hb.min(0) + hb.max(0)) / 2
    total_len = float(allb[:, 2].max() - allb[:, 2].min())

    # ---- review stage (not exported)
    stage = bpy.data.collections.new('REVIEW | not exported'); scene.collection.children.link(stage)
    if scene.world is None:
        scene.world = bpy.data.worlds.new('Review world')
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background') or scene.world.node_tree.nodes.new('ShaderNodeBackground')
    if not bg.outputs[0].is_linked:
        wo = scene.world.node_tree.nodes.get('World Output') or scene.world.node_tree.nodes.new('ShaderNodeOutputWorld')
        scene.world.node_tree.links.new(bg.outputs[0], wo.inputs['Surface'])
    bg.inputs[0].default_value = (.4, .4, .4, 1); bg.inputs[1].default_value = .6

    def stage_obj(name, data):
        o = bpy.data.objects.new(name, data); stage.objects.link(o); return o

    fm = bpy.data.materials.new('Neutral review floor'); fm.use_nodes = True
    fm.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = col((.48, .48, .48))
    fme = bpy.data.meshes.new('Review floor')
    fme.from_pydata([(-100, -100, 0), (100, -100, 0), (100, 100, 0), (-100, 100, 0)], [], [(0, 1, 2, 3)])
    fme.materials.append(fm); floor = stage_obj('Review floor', fme)

    target = Vector((0, 0.05, (allb[:, 2].max() + allb[:, 2].min()) / 2))
    for pos, power, size in [((-4, -6, 8), 950, 6), ((5, -4, 6), 700, 5), ((1, 5, 8), 1200, 5)]:
        ld = bpy.data.lights.new('Review area', 'AREA'); ld.energy = power; ld.shape = 'DISK'; ld.size = size
        lo = stage_obj('Review area light', ld); lo.location = pos
        lo.rotation_euler = (target - lo.location).to_track_quat('-Z', 'Y').to_euler()

    def camera(name):
        cd = bpy.data.cameras.new(name); cd.type = 'ORTHO'; cd.clip_start = 0.1; cd.clip_end = 100
        return stage_obj(name, cd)

    cam_hero = camera('Hero 3-4 camera (generator applies a -38 deg review lean)')
    cam_side = camera('Side camera')
    cam_front = camera('Front spin-check camera')

    # Spin-check helpers: a red stripe that turns with the wheel and a fixed ring at the rim radius.
    red = bpy.data.materials.new('Spin marker red'); red.use_nodes = True
    red.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = col((.85, .10, .08))
    ring_mat = bpy.data.materials.new('Fixed rim ring'); ring_mat.use_nodes = True
    ring_mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = col((.05, .35, .55))
    yv = -HUB_HALF - 0.008
    me = bpy.data.meshes.new('Spin marker')
    me.from_pydata([(0.42, yv, -0.035), (0.86, yv, -0.035), (0.86, yv, 0.035), (0.42, yv, 0.035)], [], [(0, 1, 2, 3)])
    me.materials.append(red); marker = stage_obj('Spin marker (child of Wheel, review only)', me)
    marker.parent = wheel; marker.matrix_parent_inverse = Matrix.Identity(4)
    n = 64; r0, r1 = WHEEL_R + 0.012, WHEEL_R + 0.04; wl = wheel.matrix_world.translation; ry = ARM_Y0 - 0.20
    v = [(wl.x + r * math.cos(TAU * i / n), ry, wl.z + r * math.sin(TAU * i / n)) for r in (r0, r1) for i in range(n)]
    f = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    me = bpy.data.meshes.new('Fixed rim ring'); me.from_pydata(v, [], f); me.materials.append(ring_mat)
    ring = stage_obj('Fixed rim ring (review only)', me)
    labels = []
    for text in ('REST', 'WHEEL +37 DEG'):
        cu = bpy.data.curves.new('Label ' + text, 'FONT'); cu.body = text; cu.align_x = 'CENTER'; cu.size = 0.24
        lm = bpy.data.materials.new('Label ' + text); lm.use_nodes = True
        lm.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = col((.12, .12, .12))
        cu.materials.append(lm)
        lo = stage_obj('Label ' + text, cu); lo.rotation_euler = (math.radians(90), 0, 0)
        lo.location = (0, ARM_Y0 - 0.3, allb[:, 2].min() - 0.42); labels.append(lo)
    helpers = [marker, ring] + labels

    def show(objs_on):
        for o in helpers:
            o.hide_render = o not in objs_on; o.hide_viewport = o not in objs_on

    scene.render.engine = 'CYCLES'; scene.cycles.samples = 24; scene.cycles.use_denoising = True
    scene.render.resolution_percentage = 100; scene.view_settings.view_transform = 'AgX'
    scene.render.image_settings.file_format = 'PNG'; scene.render.film_transparent = False

    rest = {o: o.matrix_world.copy() for o in (handle, wheel)}

    def pose(Mx):
        for o, mw in rest.items():
            o.matrix_world = Mx @ mw
        bpy.context.view_layer.update()

    # Preview: 3/4 hero, leaning like the concept.
    show([])
    pose(Matrix.Rotation(math.radians(HERO_TILT_DEG), 4, 'Y'))
    pts = world_pts([handle, wheel])
    floor.location.z = min(p.z for p in pts) - 0.02; floor.hide_render = False
    frame(cam_hero, (-0.45, 0.85, -0.30), pts, 1.0, 1.12, drop=0.03)
    scene.camera = cam_hero; render(scene, OUT / 'Preview.png', 1000, 1000)

    # Alternate: upright side view from the arm side, showing the rim bevel, arm offset and both nuts.
    pose(Matrix.Identity(4))
    pts = world_pts([handle, wheel])
    floor.location.z = min(p.z for p in pts) - 0.02
    frame(cam_side, (0.985, 0.09, -0.15), pts, 1.0, 1.08, drop=0.03)
    scene.camera = cam_side; render(scene, OUT / 'Alternate.png', 1000, 1000)

    # Spin check: identical front camera, wheel at rest vs turned 37 deg about its own axle.
    floor.hide_render = True
    pts = world_pts([handle, wheel]) + [Vector((s * 1.1, 0, labels[0].location.z + dz)) for s in (-1, 1) for dz in (-0.08, 0.26)]
    frame(cam_front, (0, 1, 0), pts, 0.8, 1.05)
    scene.camera = cam_front
    tmp = Path(tempfile.mkdtemp(prefix='pizza_spin_'))
    show([marker, ring, labels[0]]); render(scene, tmp / 'rest.png', 800, 1000)
    wheel.rotation_euler = (0, math.radians(SPIN_TEST_DEG), 0); bpy.context.view_layer.update()
    spun_axle = list(wheel.matrix_world.translation)
    show([marker, ring, labels[1]]); render(scene, tmp / 'spun.png', 800, 1000)
    a, b = load_px(tmp / 'rest.png'), load_px(tmp / 'spun.png')
    # Pixel proof: outside the wheel disk (and above the labels) the two frames should match.
    hgt, wid = a.shape[:2]
    cpx = world_to_camera_view(scene, cam_front, wheel.matrix_world.translation)
    epx = world_to_camera_view(scene, cam_front, wheel.matrix_world.translation + Vector((WHEEL_R + 0.08, 0, 0)))
    lpx = world_to_camera_view(scene, cam_front, Vector((0, 0, allb[:, 2].min() - 0.05)))
    yy, xx = np.mgrid[0:hgt, 0:wid]
    rows_up = yy / hgt                                     # Blender pixels: row 0 = bottom
    rad_px = (epx.x - cpx.x) * wid
    outside = ((xx - cpx.x * wid) ** 2 + (yy - cpx.y * hgt) ** 2 > rad_px ** 2) & (rows_up > lpx.y)
    inside = ((xx - cpx.x * wid) ** 2 + (yy - cpx.y * hgt) ** 2 <= rad_px ** 2)
    diff = np.abs(a[..., :3] - b[..., :3]).max(-1) > 6 / 255
    spin_pixels = {'changed_fraction_outside_wheel_disk': round(float(diff[outside].mean()), 5),
                   'changed_fraction_inside_wheel_disk': round(float(diff[inside].mean()), 4),
                   'threshold': '6/255 per channel'}
    gap = np.full((hgt, 8, 4), 0.25, dtype=np.float32); gap[..., 3] = 1
    save_px(np.concatenate([a, gap, b], axis=1), OUT / 'Spin_Check.png')
    shutil.rmtree(tmp, ignore_errors=True)

    # Restore the rest state; save an editable, texture-packed file.
    wheel.rotation_euler = (0, 0, 0); pose(Matrix.Identity(4)); show([])
    floor.location.z = float(allb[:, 2].min()) - 0.02; floor.hide_render = False
    scene.camera = cam_side
    bpy.ops.object.select_all(action='DESELECT'); handle.select_set(True); bpy.context.view_layer.objects.active = handle
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / 'Model.blend'))

    # ---- reimport both exports in clean scenes
    vgroups = [g.name for g in handle.vertex_groups]
    before = set(os.listdir(OUT))
    expect = {'handle_height': float(hb[:, 2].max() - hb[:, 2].min()), 'axle': axle_world}
    fbx = reimport(OUT / 'Model.fbx', 'fbx', expect)
    glb = reimport(OUT / 'Model.glb', 'glb', expect)
    stray = sorted(set(os.listdir(OUT)) - before)

    to_rbx = lambda p: [round(float(p[0]), 4), round(float(p[2]), 4), round(float(-p[1]), 4)]
    hsize = hb.max(0) - hb.min(0)
    grip_off = -handle_center; axle_off = axle_world - handle_center
    validation = {
        'index': 42, 'name': 'Pizza Cutter', 'family': 'Chef kitchen (Frying Pan, Spatula)',
        'generator': GENERATOR,
        'objects': {
            'Handle': dict(stats['Handle'], origin=[0.0, 0.0, 0.0],
                           pivot='Handhold center (wood grip midpoint) at world origin',
                           parts=['Wood grip + lanyard hole', 'Guard collar', 'Arm', 'Axle', 'Axle nut (arm side)',
                                  'Axle nut (far side)', '2 rivets x 2 faces'],
                           vertex_groups=vgroups),
            'Wheel': dict(stats['Wheel'], origin=[round(float(x), 4) for x in axle_world], pivot='Axle center'),
        },
        'triangles_total': stats['Handle']['triangles'] + stats['Wheel']['triangles'],
        'materials': 1, 'material_name': 'PizzaCutter | portable baked base color (shared by both meshes)',
        'uv': 'one UV layer per mesh, both packed into one shared 0-1 layout (smart project, 0.012 margin)',
        'texture': 'BaseColor.png 1024x1024 sRGB, packed in Model.blend, embedded in FBX and GLB',
        'bounds': bounds, 'total_length': round(total_len, 4),
        'wheel_diameter_fraction_of_length': round(wcheck['diameter'] / total_len, 4),
        'wheel': dict(wcheck, spin_axis_blender='Wheel local +Y (identity rotation); world +Y',
                      spin_axis_roblox_expected='MeshPart local Z axis: Blender +Y maps to Roblox -Z with '
                                                'axis_forward=-Z, axis_up=Y. Spin with CFrame.Angles(0, 0, angle).',
                      bounds_center_equals_axle='yes (rotationally symmetric 24-gon, mirror-symmetric profile)',
                      axle_world_after_37deg_spin=[round(float(x), 6) for x in spun_axle]),
        'clearance': clear,
        'spin_check_pixels': spin_pixels,
        'roblox_import_expectation': {
            'axis_mapping': 'Blender (x, y, z) -> Roblox (x, z, -y); long axis Blender +Z -> Roblox +Y, wheel face in Roblox XY, thin axis Roblox Z',
            'raw_fbx_scale': 'same export settings as the Pan/Spatula: raw import = 100 x Blender units (Pan MeshSize 454.6 for 4.546 BU); templates rescale per item',
            'handle_bbox_size_blender': [round(float(x), 4) for x in hsize],
            'grip_offset_from_handle_bbox_center_roblox_axes_BU': to_rbx(grip_off),
            'grip_offset_fraction_of_handle_bbox_roblox_axes': to_rbx(grip_off / np.array([hsize[0], hsize[1], hsize[2]])),
            'axle_offset_from_handle_bbox_center_roblox_axes_BU': to_rbx(axle_off),
            'note': 'Roblox centres each imported MeshPart on its bounding box; the Wheel box centre IS the axle. '
                    'Add a Grip attachment at the listed offset on Handle (as the Godly templates do).',
        },
        'fbx_reimport': fbx, 'glb_reimport': glb,
        'stray_files_created_by_reimport': stray,
        'studio_status': 'Blender-verified, Studio untested',
        'notes': ['Single gunmetal arm on the -Y side, as drawn in the concept SIDE and 3/4 views (not a two-sided fork).',
                  'Handle parts intentionally intersect where assembled (closed shells); nothing intersects the Wheel.',
                  'Wood back face and far nut are inferred from the side view; rivets are through-rivets with heads on both faces.',
                  'Review renders use a temporary -38 deg lean (Preview) and a temporary 37 deg wheel turn (Spin_Check); Model.blend is saved at rest.'],
    }
    (OUT / 'validation.json').write_text(json.dumps(validation, indent=2))
    rx = validation['roblox_import_expectation']
    (OUT / 'README.md').write_text(f'''# Pizza Cutter (42, Chef kitchen family)

Stylized low-poly pizza wheel built to sit beside the Frying Pan and Spatula. Matches `Reference.png`
(unmodified copy of `concepts/chef-2026-10-09/pizza-cutter-concept.png`). Generated by
`{GENERATOR}` (self-contained; run with Blender 5.2 `--background --factory-startup --threads 4`).

**Status: Blender-verified, Studio untested.**

## Objects (both share one material and one 1024px `BaseColor.png` atlas)

| Object | Triangles | Origin | Contents |
| --- | --- | --- | --- |
| `Handle` | {stats['Handle']['triangles']} | handhold centre (wood grip midpoint), world origin | wood grip + lanyard hole, 2 through-rivets, guard collar, arm, axle, both axle nuts |
| `Wheel` | {stats['Wheel']['triangles']} | axle centre {[round(float(x), 3) for x in axle_world]} | regular {WHEEL_N}-facet steel wheel, two-facet sharpened rim |

Total {validation['triangles_total']} triangles. Length {round(total_len, 2)} BU (Pan 4.55, Spatula 3.74); wheel
diameter {round(wcheck['diameter'], 2)} BU = {round(100 * wcheck['diameter'] / total_len)}% of length.

## Pivots and spin axis

- Built upright like the Spatula: Blender +Z = wheel end, handle at the bottom, wheel face in the XZ plane.
- `Wheel` spins about its **local +Y** in Blender (identity rotation). FBX/GLB use Blender (x, y, z) -> Roblox (x, z, -y),
  so in Roblox the wheel spins about the **MeshPart's local Z axis**: `wheel.CFrame = wheel.CFrame * CFrame.Angles(0, 0, a)`.
  The wheel's bounding-box centre is exactly the axle, so Roblox's bbox-centred MeshPart already pivots correctly.
- Axle nuts and the axle stay on `Handle`, so a spinning wheel never moves the grip. Running clearance 0.012 BU to the arm
  and far nut; no wheel/handle intersections at rest or turned 37 deg (validation.json, Spin_Check.png).
- Roblox centres `Handle` on its bbox too. Grip offset from that centre (Roblox axes, BU): {rx['grip_offset_from_handle_bbox_center_roblox_axes_BU']};
  axle offset: {rx['axle_offset_from_handle_bbox_center_roblox_axes_BU']}. Add a `Grip` attachment there (as the Godly templates do).

## Studio convention matched (read-only check of the place)

`ReplicatedStorage.RogueliteCombat.WeaponTemplates` keeps each weapon's long axis on +Y and its thin axis on Z. `01` Frying Pan:
2.38 x 3.79 x 0.58 studs, one MeshPart with TextureID, but its raw import lay along X and needed a WeaponPresentation rotation.
`05` Spatula: 1.31 x 2.65 x 0.22 studs, built upright, no rotation. This cutter is built upright like the Spatula, so a raw import
already has long axis +Y and thin axis Z. Export settings match the siblings (FBX axis_forward -Z, axis_up Y, embedded texture),
so it imports at the same raw scale as the Pan (100 x Blender units); at the Pan's template ratio it would be about 3.5 studs long.

## Assumptions and limitations

- Single gunmetal arm on the front (-Y) side, as drawn in the concept SIDE and 3/4 views, not a two-sided fork.
- Back of the grip, far nut and rivet backs are inferred from the side view.
- Handle parts are closed shells that intentionally intersect where assembled; named vertex groups identify them.
- Known Roblox multi-mesh FBX behaviour (one TextureID applied to every mesh) is why both meshes share one atlas.
- Not imported into Studio; MeshPart sizes, the Grip attachment and the spin script are integration work.
''')
    print('PIZZA_CUTTER_DONE', json.dumps({'tris': validation['triangles_total'], 'handle': stats['Handle'],
                                          'wheel': stats['Wheel'], 'fbx': fbx['mesh_objects'], 'glb': glb['mesh_objects']}), flush=True)


if __name__ == '__main__':
    main()
