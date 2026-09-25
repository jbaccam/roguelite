"""Beach Cove modular kit.

    blender --background --python generate_beach_kit.py
    blender --background --python generate_beach_kit.py -- --preview

Built to the approved art brief in `../art-references/ART_DIRECTION_USER_2026-09-17.txt`.
The rules that shape this file, quoting the brief:

* "soft bevels instead of razor-sharp edges", "edges should usually be slightly
  softened" -- every asset gets a single-segment chamfer, the same treatment the
  lightstone revision calls Small_worn_edge_chamfer, scaled to this kit's size.
* "pure flat-shaded geometry" is on the AVOID list -- so faces are smooth shaded
  and only the major silhouette breaks are left sharp, via shade_smooth_by_angle.
* Cliffs are "rounded/cylindrical, chunky, modular, stackable, slightly
  irregular, low-poly, soft-edged" with "rounded or softly polygonal footprints",
  and explicitly not "perfect cylinders" or "perfect rectangles".
* "Grass should not abruptly stop at the cliff edge... The transition should
  occupy a noticeable band, not a tiny line." The rim is therefore large and its
  lower boundary is irregular, with the grass reaching further down in places.
* "Stacked cliffs must NOT look like layer cakes" -- combos use offset masses,
  unequal height zones and irregular widths, with one side reading as a single
  tall face.
* "Avoid huge triangular facets dominating surfaces" and "excessive tiny
  geometry" -- boulders are rounded and chamfered rather than raw icospheres,
  and ground decals are kept cheap.

Scale: every asset is modelled at its FINAL Roblox stud size, with the painted
repeat pinned to a constant studs-per-repeat, so the kit imports at 1:1 and is
not scaled. See README.md for why.

This script is self-contained. The sibling generators exec() slices of each
other's source text, which breaks as soon as any of them is edited.
"""
import json
import math
import time
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
TEX = ROOT / "textures"
for d in ("previews", "exports/glb", "exports/fbx"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)

PREVIEW = "--preview" in sys.argv
ATLAS = 2048

# Studs of model per one repeat of the painted sheet. Held constant across every
# asset size; this is what keeps the painted pattern the right size on a 50-stud
# cliff and an 8-stud rock alike.
# The painted sheets carry their own block/blade counts, so these are set from
# how big one painted feature should read in studs, not from a texel budget.
# The stone sheet holds roughly 16 blocks across, so 40 studs per repeat puts a
# stone block at about 2.5 studs -- chunky, like the reference. At the old 9 it
# was half a stud, which is what "too many rocks" meant.
D_ROCK = 40.0
D_GRASS = 18.0
D_BARK = 8.0
D_FROND = 7.0
D_WOOD = 5.0
D_SAND = 10.0
D_WATER = 12.0

# Sized for a 125-stud arena, so roughly 2x the sibling kits; their 0.10-unit
# worn chamfer scales to about 0.22 studs here.
CHAMFER = 0.07
SHARP = math.radians(40)   # facets steeper than this stay as readable breaks

ROCK, GRASS, TRANS, SAND, BARK, FROND, DRIFT, BOAT, WATER = range(9)
SHEETS = ["rock", "grass", "transition", "sand", "palm_bark", "frond", "driftwood", "boat_wood", "water"]


# ---------------------------------------------------------------------------
# scene + materials
# ---------------------------------------------------------------------------
def reset_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def build_materials():
    mats = []
    for name in SHEETS:
        path = TEX / f"{name}.png"
        if not path.exists():
            raise SystemExit(f"missing {path}; run author_textures.py first")
        m = bpy.data.materials.new("Beach_" + name)
        m.use_nodes = True
        bs = m.node_tree.nodes.get("Principled BSDF")
        bs.inputs["Roughness"].default_value = 0.85
        bs.inputs["Metallic"].default_value = 0.0
        bs.inputs["Specular IOR Level"].default_value = 0.12
        tx = m.node_tree.nodes.new("ShaderNodeTexImage")
        tx.image = bpy.data.images.load(str(path))
        tx.extension = "REPEAT"
        tx.interpolation = "Linear"
        uv = m.node_tree.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        m.node_tree.links.new(uv.outputs["UV"], tx.inputs["Vector"])
        m.node_tree.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
        mats.append(m)
    return mats


def new_mesh(name, verts, faces, uvs, roles):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for m in MATERIALS:
        mesh.materials.append(m)
    layer = mesh.uv_layers.new(name="UVMap")
    for poly, co, role in zip(mesh.polygons, uvs, roles):
        poly.material_index = role
        for li, uv in zip(poly.loop_indices, co):
            layer.data[li].uv = uv
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def finish(obj, chamfer=CHAMFER, sharp=SHARP):
    """The brief's finishing pass: soft bevel, then smooth with sharp breaks.

    "Soft bevels instead of razor-sharp edges" and, on the avoid list, "pure
    flat-shaded geometry". A single bevel segment keeps the form low-poly while
    catching a highlight along every silhouette edge; shade_smooth_by_angle then
    smooths the small chamfer facets but leaves the major planar breaks crisp,
    which is what "faceted geometry is visible" without "huge triangular facets".
    """
    activate(obj)
    bev = obj.modifiers.new("Soft_worn_edge_chamfer", "BEVEL")
    bev.width = chamfer
    bev.segments = 1
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(32)
    bev.harden_normals = False
    bpy.ops.object.modifier_apply(modifier=bev.name)
    # Bevelling can collapse geometry that is already thinner than the chamfer --
    # a boat's stem, a thin branch stub. Those become zero-area faces, which have
    # no normal and shade as black slivers in engine, so dissolve them here
    # rather than hand-tuning a chamfer width per asset.
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.dissolve_degenerate(threshold=1e-4)
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in obj.data.polygons:
        p.use_smooth = True
    bpy.ops.object.shade_smooth_by_angle(angle=sharp)
    return obj


def ground(obj):
    """Drop the mesh so its lowest point sits on z=0, pivot at the footprint centre."""
    lo = min(v.co.z for v in obj.data.vertices)
    for v in obj.data.vertices:
        v.co.z -= lo
    obj.data.update()
    return obj


def join(name, parts):
    bpy.ops.object.select_all(action="DESELECT")
    for obj, loc in parts:
        obj.location = loc
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0][0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return obj


# ---------------------------------------------------------------------------
# cliffs
# ---------------------------------------------------------------------------
def footprint(w, d, seed, n):
    """Rounded, softly polygonal, slightly irregular -- never a perfect cylinder.

    The brief asks for "circular-ish, oval, rounded square, irregular rounded
    shapes", so this is a circle with low-frequency wobble and a mild squared
    bias, not the boxy superellipse an angular concept sketch would suggest.
    """
    pts = []
    for i in range(n):
        a = i * math.tau / n
        # Mild squaring keeps broad planar faces without going rectangular.
        square = 1 + 0.085 * (abs(math.cos(2 * a)) ** 1.6)
        wob = (1
               + 0.062 * math.sin(3 * a + seed)
               + 0.038 * math.sin(5 * a + 0.7 * seed)
               + 0.021 * math.cos(7 * a + 1.3 * seed))
        pts.append((math.cos(a) * w * 0.5 * square * wob,
                    math.sin(a) * d * 0.5 * square * wob))
    return pts


def cliff(name, w, d, h, seed, taper=0.92, lean=0.0, grassy=True):
    """Rounded chunky headland with a wide, irregular grass-to-rock band."""
    n = 12 if w > 24 else 10
    pts = footprint(w, d, seed, n)

    # "The transition should occupy a noticeable band, not a tiny line."
    # The lightstone revision grew its rim to 45% of height on low pieces and
    # ~3.5 units on tall ones; at this kit's scale that is about 12 studs.
    rim = min(h * 0.45, 12.0) if grassy else 0.0
    wall_top = h - rim
    levels = max(2, min(4, round(wall_top / 8.0)))

    # Gentle per-column offset, constant down the cliff, so the form is "slightly
    # irregular" rather than channelled into hard slabs.
    column = [1
              + 0.080 * math.sin(2 * a + seed)
              + 0.050 * math.sin(3 * a + 1.3 * seed)
              for a in (i * math.tau / n for i in range(n))]

    rings = []
    for k in range(levels + 1):
        t = k / levels
        s = taper + (1 - taper) * t + 0.026 * math.sin(t * math.pi)
        # Aperiodic, shallow ledges. A single periodic term makes every cliff
        # step at the same rhythm, which is what reads as a layer cake.
        s += 0.026 * math.sin(k * 1.7 + seed) * math.cos(k * 0.93 + seed * 0.6) * (0.35 + 0.65 * t)
        if k == 0:
            s *= 1.05  # talus flare where the cliff meets the sand
        rings.append((wall_top * t, s, ROCK))
    if grassy:
        rings.append((wall_top, 1.004, TRANS))
        rings.append((h - rim * 0.42, 1.016, TRANS))
        rings.append((h - 0.30, 1.026, TRANS))
        rings.append((h, 1.008, TRANS))

    verts = []
    for z, s, role in rings:
        t = z / max(h, 1e-6)
        dx = lean * math.sin(t * math.pi * 0.85)
        dy = lean * 0.22 * math.sin(t * math.pi * 1.3)
        for i, (x, y) in enumerate(pts):
            a = i * math.tau / n
            c = 1 + (column[i] - 1) * (1.0 if role == ROCK else 0.45)
            zz = z
            if role == TRANS and z < h:
                # Irregular vegetation boundary: the grass hangs further down in
                # places instead of stopping on a level line.
                drop = 1 + 0.20 * math.sin(3 * a + seed) + 0.13 * math.cos(7 * a + seed)
                zz = h - (h - z) * drop
            else:
                zz = z + (0.26 * math.sin(3 * a + seed) + 0.15 * math.cos(7 * a + seed * 1.7)) * (t ** 1.3) * (h / 28)
            verts.append((x * s * c + dx, y * s * c + dy, zz))

    arcs = [0.0]
    for i in range(n):
        arcs.append(arcs[-1] + math.dist(pts[i], pts[(i + 1) % n]))

    faces, uvs, roles = [], [], []

    def add(ids, uv, role):
        faces.append(ids)
        uvs.append(uv)
        roles.append(role)

    for k in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            ids = (k * n + i, k * n + j, (k + 1) * n + j, (k + 1) * n + i)
            u0, u1 = arcs[i] / D_ROCK, arcs[i + 1] / D_ROCK
            if rings[k][2] == TRANS:
                # Band maps the transition sheet once, from its rock foot to its
                # dense green top, repeating only around the perimeter.
                v0 = min(1.0, max(0.0, (verts[k * n + i][2] - wall_top) / rim))
                v1 = min(1.0, max(0.0, (verts[(k + 1) * n + i][2] - wall_top) / rim))
                add(ids, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], TRANS)
            else:
                v0, v1 = rings[k][0] / D_ROCK, rings[k + 1][0] / D_ROCK
                add(ids, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)], ROCK)

    outer = (len(rings) - 1) * n
    cap_role = GRASS if grassy else ROCK
    cap_d = D_GRASS if grassy else D_ROCK
    for frac in (0.55,):
        start = len(verts)
        for x, y in pts:
            xx = x * frac + lean * math.sin(math.pi * 0.85)
            yy = y * frac + lean * 0.22 * math.sin(math.pi * 1.3)
            zz = h + (0.22 + 0.18 * math.sin(xx * 0.24 + seed) * math.cos(yy * 0.27)) * (1 - frac) * (h / 26)
            verts.append((xx, yy, zz))
        for i in range(n):
            j = (i + 1) % n
            ids = (outer + i, outer + j, start + j, start + i)
            add(ids, [(verts[q][0] / cap_d, verts[q][1] / cap_d) for q in ids], cap_role)
        outer = start
    centre = len(verts)
    verts.append((lean * math.sin(math.pi * 0.85), lean * 0.22 * math.sin(math.pi * 1.3), h + 0.30 * (h / 26)))
    for i in range(n):
        ids = (outer + i, outer + (i + 1) % n, centre)
        add(ids, [(verts[q][0] / cap_d, verts[q][1] / cap_d) for q in ids], cap_role)

    base = tuple(reversed(range(n)))
    add(base, [(verts[q][0] / D_ROCK, verts[q][1] / D_ROCK) for q in base], ROCK)

    return finish(ground(new_mesh(name, verts, faces, uvs, roles)))


def boulder(name, w, d, h, seed, role=ROCK, density=4.5):
    """Chunky rounded boulder.

    Built from an icosphere but chamfered and smoothed by angle, because a raw
    flat-shaded icosphere is exactly the "huge triangular facets dominating
    surfaces" the brief rules out.
    """
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1)
    obj = bpy.context.object
    obj.name = name
    for v in obj.data.vertices:
        x, y, z = v.co
        f = (1
             + 0.14 * math.sin(x * 4 + y * 3 + seed)
             + 0.09 * math.cos(z * 5 + seed * 1.7)
             + 0.05 * math.sin(x * 9 - z * 7 + seed * 2.3))
        v.co = (
            math.copysign(abs(x) ** 0.85, x) * w * 0.5 * f + 0.08 * w * z,
            math.copysign(abs(y) ** 0.88, y) * d * 0.5 * f,
            max(0.0, (z + 1) * h * 0.5 * f),
        )
    obj.data.materials.clear()
    for m in MATERIALS:
        obj.data.materials.append(m)
    obj.data.update()
    layer = obj.data.uv_layers.new(name="UVMap")
    for p in obj.data.polygons:
        p.material_index = role
        axis = max(range(3), key=lambda i: abs(p.normal[i]))
        for li in p.loop_indices:
            co = obj.data.vertices[obj.data.loops[li].vertex_index].co
            layer.data[li].uv = ((co.y if axis == 0 else co.x) / density,
                                 (co.y if axis == 2 else co.z) / density)
    return finish(ground(obj), chamfer=min(CHAMFER, min(w, d, h) * 0.05))


# ---------------------------------------------------------------------------
# palms
# ---------------------------------------------------------------------------
def palm(name, height, seed, lean=0.0, fronds=8, crown_r=1.0, coconuts=3):
    """Chunky palm with scalloped, drooping frond blades.

    The brief's foliage language is "chunky, layered, scalloped edges, slightly
    drooping, low-poly, soft silhouette", and it rules out "individual leaf
    cards" and "super spiky geometry". So each frond is one solid blade folded
    along its spine with a lobed outer edge, not a fan of thin pointed cards.
    """
    verts, faces, uvs, roles = [], [], [], []

    def add(ids, uv, role):
        faces.append(ids)
        uvs.append(uv)
        roles.append(role)

    sides = 7
    segs = 8
    r_base, r_top = height * 0.068, height * 0.040
    axis = []
    for k in range(segs + 1):
        t = k / segs
        x = lean * (t ** 1.7) * height * 0.5
        z = height * t
        r = (r_base + (r_top - r_base) * t) * (1 + 0.05 * math.sin(t * math.pi * 4 + seed))
        r *= 1 + 0.30 * max(0.0, 1 - t / 0.12) ** 2  # slightly widened foot
        axis.append((x, z, r))
        for i in range(sides):
            a = i * math.tau / sides
            verts.append((x + math.cos(a) * r, math.sin(a) * r, z))
    circ = math.tau * r_base
    for k in range(segs):
        for i in range(sides):
            j = (i + 1) % sides
            ids = (k * sides + i, k * sides + j, (k + 1) * sides + j, (k + 1) * sides + i)
            u0, u1 = i * circ / sides / D_BARK, (i + 1) * circ / sides / D_BARK
            add(ids, [(u0, axis[k][1] / D_BARK), (u1, axis[k][1] / D_BARK),
                      (u1, axis[k + 1][1] / D_BARK), (u0, axis[k + 1][1] / D_BARK)], BARK)
    top_ring = segs * sides
    cx, cz, _ = axis[-1]
    centre = len(verts)
    verts.append((cx, 0.0, cz))
    for i in range(sides):
        ids = (top_ring + i, top_ring + (i + 1) % sides, centre)
        add(ids, [(verts[q][0] / D_BARK, verts[q][1] / D_BARK) for q in ids], BARK)

    tip_x, tip_z, _ = axis[-1]
    blade = height * 0.50
    fseg = 7
    for f in range(fronds):
        yaw = f * math.tau / fronds + seed * 0.3
        droop = 0.58 + 0.34 * ((f * 7 + seed) % 5) / 4.0
        spine = []
        for k in range(fseg + 1):
            t = k / fseg
            reach = blade * t
            rise = blade * 0.34 * math.sin(t * math.pi * 0.55)
            drop = -droop * blade * (t ** 2.2)
            spine.append((tip_x + math.cos(yaw) * reach * crown_r,
                          math.sin(yaw) * reach * crown_r,
                          tip_z + rise + drop))
        base_i = len(verts)
        for k, (sx, sy, sz) in enumerate(spine):
            t = k / fseg
            # Broad blade that stays wide and ends blunt. Tapering the width to
            # zero at the tip is what produced spikes; the brief wants "chunky"
            # foliage with "scalloped edges" and rules out "super spiky geometry".
            # Widest about a third out, narrowing to a rounded tip: neither the
            # spike of a zero-width end nor the blunt strap of a constant one.
            taper = (math.sin(math.pi * (0.20 + 0.62 * t)) ** 0.8) * (1 - 0.55 * t ** 2)
            lobe = 1 + 0.18 * abs(math.sin(k * 1.9 + f))   # rounded lobes, not saw teeth
            half = blade * 0.095 * taper * lobe
            nx, ny = -math.sin(yaw) * half, math.cos(yaw) * half
            fold = -half * 0.34
            verts.append((sx + nx, sy + ny, sz + fold))
            verts.append((sx, sy, sz))
            verts.append((sx - nx, sy - ny, sz + fold))
        # Blunt tip cap so the blade closes instead of ending on an open edge.
        tip = base_i + fseg * 3
        add((tip, tip + 1, tip + 2), [(0.0, 0.0), (0.12, 0.0), (0.24, 0.0)], FROND)
        add((tip + 2, tip + 1, tip), [(0.24, 0.0), (0.12, 0.0), (0.0, 0.0)], FROND)
        run = 0.0
        for k in range(fseg):
            a = base_i + k * 3
            b = base_i + (k + 1) * 3
            step = math.dist(spine[k], spine[k + 1])
            for off in (0, 1):
                ids = (a + off, a + off + 1, b + off + 1, b + off)
                u0, u1 = off * blade * 0.095 / D_FROND, (off + 1) * blade * 0.095 / D_FROND
                co = [(u0, run / D_FROND), (u1, run / D_FROND),
                      (u1, (run + step) / D_FROND), (u0, (run + step) / D_FROND)]
                add(ids, co, FROND)
                # A frond is a thin blade, so its back face is visible whenever you
                # stand under the tree. Single-sided geometry gets backface-culled
                # and the leaves vanish from below, so emit the mirror face too.
                add(tuple(reversed(ids)), list(reversed(co)), FROND)
            run += step

    for c in range(coconuts):
        a = c * math.tau / max(1, coconuts) + seed
        r = height * 0.032
        cxx = tip_x + math.cos(a) * height * 0.038
        cyy = math.sin(a) * height * 0.038
        czz = tip_z - height * 0.028
        start = len(verts)
        band = 6
        for ring in range(3):
            zz = czz + (ring - 1) * r * 0.9
            rr = r * (0.55 if ring != 1 else 1.0)
            for i in range(band):
                aa = i * math.tau / band
                verts.append((cxx + math.cos(aa) * rr, cyy + math.sin(aa) * rr, zz))
        for ring in range(2):
            for i in range(band):
                j = (i + 1) % band
                ids = (start + ring * band + i, start + ring * band + j,
                       start + (ring + 1) * band + j, start + (ring + 1) * band + i)
                add(ids, [(verts[q][0] / D_BARK, verts[q][2] / D_BARK) for q in ids], BARK)

    return finish(ground(new_mesh(name, verts, faces, uvs, roles)), chamfer=0.10)


# ---------------------------------------------------------------------------
# ground props
# ---------------------------------------------------------------------------
def driftwood(name, length, seed, radius=2.1):
    """Beach driftwood, following the brief's log rules.

    "Logs should be thick, chunky, faceted, slightly irregular, simple" and
    should "include cut circular ends, short broken branch stubs, visible bark
    variation, slightly uneven silhouette. Avoid smooth perfect cylinders."
    Distinct from blender-master-log by being bleached, flatter in section,
    bowed along its length and carrying two stubs rather than four.
    """
    verts, faces, uvs, roles = [], [], [], []

    def add(ids, uv, role=DRIFT):
        faces.append(ids)
        uvs.append(uv)
        roles.append(role)

    sides, segs = 7, 6
    for k in range(segs + 1):
        t = k / segs
        x = (t - 0.5) * length
        bow = math.sin(t * math.pi) * radius * 0.26
        twist = 0.32 * math.sin(t * math.pi * 2 + seed)
        r = radius * (0.76 + 0.30 * math.sin(t * math.pi))
        for i in range(sides):
            a = i * math.tau / sides + twist
            rr = r * (1 + 0.15 * math.sin(3 * a + seed) + 0.08 * math.cos(5 * a + t * 4))
            verts.append((x, math.cos(a) * rr * 1.05, bow + math.sin(a) * rr * 0.92))
    circ = math.tau * radius
    for k in range(segs):
        for i in range(sides):
            j = (i + 1) % sides
            ids = (k * sides + i, k * sides + j, (k + 1) * sides + j, (k + 1) * sides + i)
            u0, u1 = (k / segs) * length / D_WOOD, ((k + 1) / segs) * length / D_WOOD
            v0, v1 = i * circ / sides / D_WOOD, (i + 1) * circ / sides / D_WOOD
            add(ids, [(u0, v0), (u0, v1), (u1, v1), (u1, v0)])
    # Cut circular ends.
    for k, ring in ((0, 0), (segs, segs * sides)):
        centre = len(verts)
        verts.append(((k / segs - 0.5) * length, 0.0, math.sin(k / segs * math.pi) * radius * 0.26))
        order = list(range(sides)) if k == 0 else list(reversed(range(sides)))
        for idx in range(sides):
            i, j = order[idx], order[(idx + 1) % sides]
            ids = (ring + i, ring + j, centre)
            add(ids, [(verts[q][1] / D_WOOD, verts[q][2] / D_WOOD) for q in ids])

    # Two short broken branch stubs.
    for si, (along, yaw, pitch, slen) in enumerate((
            (0.34, 1.05, 0.55, radius * 1.9),
            (0.68, -1.35, 0.30, radius * 1.4))):
        t = along
        ox = (t - 0.5) * length
        oz = math.sin(t * math.pi) * radius * 0.26
        r0 = radius * 0.34
        direction = Vector((math.sin(pitch) * 0.35, math.cos(yaw), math.sin(yaw) * 0.5 + math.cos(pitch) * 0.6)).normalized()
        start = len(verts)
        stub_sides = 6
        for ring in range(2):
            rr = r0 * (1.0 if ring == 0 else 0.7)
            base = Vector((ox, 0, oz)) + direction * (slen * ring)
            for i in range(stub_sides):
                a = i * math.tau / stub_sides + si
                side = direction.cross(Vector((0, 0, 1)))
                if side.length < 1e-5:
                    side = Vector((1, 0, 0))
                side.normalize()
                up = direction.cross(side).normalized()
                pt = base + side * (math.cos(a) * rr) + up * (math.sin(a) * rr)
                verts.append((pt.x, pt.y, pt.z))
        for i in range(stub_sides):
            j = (i + 1) % stub_sides
            ids = (start + i, start + j, start + stub_sides + j, start + stub_sides + i)
            add(ids, [(verts[q][0] / D_WOOD, verts[q][2] / D_WOOD) for q in ids])
        cap = len(verts)
        tipc = Vector((ox, 0, oz)) + direction * slen
        verts.append((tipc.x, tipc.y, tipc.z))
        for i in range(stub_sides):
            ids = (start + stub_sides + i, start + stub_sides + (i + 1) % stub_sides, cap)
            add(ids, [(verts[q][0] / D_WOOD, verts[q][2] / D_WOOD) for q in ids])

    return finish(ground(new_mesh(name, verts, faces, uvs, roles)), chamfer=min(0.14, radius * 0.10))


def rowboat(name, length=15.0, beam=5.4, depth=2.6, seed=3.0):
    """Chunky wrecked rowboat: open hull, pointed bow, flat transom, two thwarts."""
    verts, faces, uvs, roles = [], [], [], []

    def add(ids, uv, role=BOAT):
        faces.append(ids)
        uvs.append(uv)
        roles.append(role)

    def box(cx, cy, cz, sx, sy, sz):
        start = len(verts)
        for dx in (-sx / 2, sx / 2):
            for dy in (-sy / 2, sy / 2):
                for dz in (-sz / 2, sz / 2):
                    verts.append((cx + dx, cy + dy, cz + dz))
        for q in ((0, 1, 3, 2), (6, 7, 5, 4), (0, 4, 5, 1),
                  (2, 3, 7, 6), (0, 2, 6, 4), (5, 7, 3, 1)):
            ids = tuple(start + n for n in q)
            add(ids, [(verts[n][0] / D_WOOD, verts[n][1] / D_WOOD) for n in ids])

    segs, arc = 10, 7
    thick = depth * 0.14

    def profile(t):
        body = math.sin(math.pi * (0.16 + 0.80 * t)) ** 0.6
        bow = 1.0 - 0.74 * max(0.0, t - 0.74) / 0.26
        # Floor the beam so the stem stays a thin wedge rather than a true point.
        return max(beam * 0.035, beam * 0.5 * body * bow), depth * (0.62 + 0.38 * body)

    def shell(inner):
        start = len(verts)
        for k in range(segs + 1):
            t = k / segs
            hw, dp = profile(t)
            sheer = 0.18 * depth * math.sin(t * math.pi * 1.05)
            if inner:
                hw = max(0.05, hw - thick)
                dp = max(0.05, dp - thick)
            for i in range(arc):
                a = math.pi * i / (arc - 1)
                z = (thick if inner else 0.0) + dp * (1 - math.sin(a))
                verts.append(((t - 0.5) * length, -math.cos(a) * hw, z + sheer))
        return start

    outer, inner = shell(False), shell(True)
    for k in range(segs):
        for i in range(arc - 1):
            for base, flip in ((outer, False), (inner, True)):
                ids = (base + k * arc + i, base + k * arc + i + 1,
                       base + (k + 1) * arc + i + 1, base + (k + 1) * arc + i)
                if flip:
                    ids = tuple(reversed(ids))
                u0, u1 = (k / segs) * length / D_WOOD, ((k + 1) / segs) * length / D_WOOD
                v0, v1 = i / (arc - 1) * beam / D_WOOD, (i + 1) / (arc - 1) * beam / D_WOOD
                add(ids, [(u0, v0), (u0, v1), (u1, v1), (u1, v0)])
    for i, flip in ((0, True), (arc - 1, False)):
        for k in range(segs):
            ids = (outer + k * arc + i, outer + (k + 1) * arc + i,
                   inner + (k + 1) * arc + i, inner + k * arc + i)
            if flip:
                ids = tuple(reversed(ids))
            u0, u1 = (k / segs) * length / D_WOOD, ((k + 1) / segs) * length / D_WOOD
            add(ids, [(u0, 0.0), (u1, 0.0), (u1, thick * 2 / D_WOOD), (u0, thick * 2 / D_WOOD)])
    for k, flip in ((0, False), (segs, True)):
        for i in range(arc - 1):
            ids = (outer + k * arc + i, outer + k * arc + i + 1,
                   inner + k * arc + i + 1, inner + k * arc + i)
            if flip:
                ids = tuple(reversed(ids))
            add(ids, [(verts[n][1] / D_WOOD, verts[n][2] / D_WOOD) for n in ids])
    for t in (0.34, 0.60):
        hw, dp = profile(t)
        box((t - 0.5) * length, 0.0, dp * 0.66, length * 0.06, (hw - thick) * 2, thick * 1.5)

    obj = ground(new_mesh(name, verts, faces, uvs, roles))
    obj.rotation_euler = (math.radians(15), math.radians(-5), 0)
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    return finish(ground(obj), chamfer=0.10)


def ground_disc(name, w, d, seed, role, density, rim_role=None, thickness=0.28, dome=0.10, n=14):
    """Cheap scalloped ground piece for tide pools and grass patches.

    Kept deliberately low: the brief warns against "excessive tiny geometry", and
    a ground decal has no business carrying a four-figure triangle count.
    """
    verts, faces, uvs, roles = [], [], [], []

    def add(ids, r):
        faces.append(ids)
        uvs.append([(verts[q][0] / density, verts[q][1] / density) for q in ids])
        roles.append(r)

    pts = []
    for i in range(n):
        a = i * math.tau / n
        wob = 1 + 0.16 * math.sin(3 * a + seed) + 0.09 * math.sin(5 * a + seed * 1.4)
        pts.append((math.cos(a) * w * 0.5 * wob, math.sin(a) * d * 0.5 * wob))
    for x, y in pts:
        verts.append((x, y, 0.0))
    for x, y in pts:
        verts.append((x * 0.84, y * 0.84, thickness))
    centre = len(verts)
    verts.append((0.0, 0.0, thickness + dome))

    lip = rim_role if rim_role is not None else role
    for i in range(n):
        j = (i + 1) % n
        add((i, j, n + j, n + i), lip)
    for i in range(n):
        add((n + i, n + (i + 1) % n, centre), role)
    return finish(ground(new_mesh(name, verts, faces, uvs, roles)), chamfer=0.06)


def grass_patch(name, w, d, seed, clumps=4):
    """Low mound plus a few chunky clumps -- "sparse tiny grass clump shapes"."""
    parts = [(ground_disc(name, w, d, seed, GRASS, D_GRASS, thickness=0.22,
                          dome=min(w, d) * 0.10, n=12), (0, 0, 0))]
    for c in range(clumps):
        a = c * math.tau / clumps + seed
        r = min(w, d) * 0.30
        clump = ground_disc(f"{name}_Clump{c}", w * 0.26, d * 0.26, seed + c * 3,
                            GRASS, D_GRASS, thickness=0.18, dome=min(w, d) * 0.22, n=8)
        parts.append((clump, (math.cos(a) * r, math.sin(a) * r, 0.12)))
    return ground(join(name, parts))


# ---------------------------------------------------------------------------
# build the set
# ---------------------------------------------------------------------------
reset_scene()
MATERIALS = build_materials()

objects = []
if PREVIEW:
    objects.append(cliff("02_Headland_Medium", 18, 15, 17, 2))
    objects.append(palm("16_Palm_Tall", 22, 4.0, lean=0.10))
    objects.append(driftwood("19_Driftwood_Log", 11, 5.0, radius=1.45))
    objects.append(boulder("12_Boulder_Large", 10, 8, 6.5, 22))
else:
    objects.append(cliff("01_Headland_Short", 16, 14, 10, 1, 0.94))
    objects.append(cliff("02_Headland_Medium", 18, 15, 17, 2, 0.92))
    objects.append(cliff("03_Headland_Tall", 15, 13, 27, 3, 0.90, lean=0.7))
    objects.append(cliff("04_Plateau_Wide_Low", 32, 24, 8, 4, 0.95))
    objects.append(cliff("05_Plateau_Broad", 29, 23, 15, 5, 0.93))
    objects.append(cliff("06_Headland_Tall_Mass", 27, 22, 30, 6, 0.91))
    objects.append(cliff("07_Headland_Tapered", 18, 15, 19, 7, 0.85, lean=0.5))
    # "Stacked cliffs must NOT look like layer cakes": offset masses, unequal
    # height zones, irregular widths, one side reading as a single tall face.
    objects.append(join("08_Stack_Double", [
        (cliff("StackLowerA", 27, 19, 9, 8, 0.95), (0, 0, 0)),
        (cliff("StackUpperA", 15, 13, 21, 9, 0.90), (-7, 3.5, 0)),
    ]))
    objects.append(join("09_Stack_Triple", [
        (cliff("StackLowB", 31, 22, 7, 10, 0.96), (0, 0, 0)),
        (cliff("StackMidB", 18, 15, 15, 11, 0.93), (8, 2.5, 0)),
        (cliff("StackHighB", 14, 12, 28, 12, 0.90), (-7.5, 4.5, 0)),
    ]))
    objects.append(cliff("10_Rim_Corner_Wedge", 22, 13, 17, 13, 0.88, lean=1.2))

    objects.append(boulder("11_Boulder_Medium", 5.5, 4.8, 3.6, 21))
    objects.append(boulder("12_Boulder_Large", 10, 8, 6.5, 22))
    objects.append(join("13_Rock_Cluster", [
        (boulder("ClusterMain", 6, 4.8, 4.6, 24), (0, 0.9, 0)),
        (boulder("ClusterLeft", 3.6, 3.3, 2.7, 25), (-3.3, -0.9, 0)),
        (boulder("ClusterRight", 3.9, 3, 3.2, 26), (3.3, -0.6, 0)),
        (boulder("ClusterFront", 2.5, 2.4, 1.8, 27), (0.3, -3, 0)),
    ]))
    objects.append(boulder("14_Standing_Rock", 5, 4.2, 10, 28))
    objects.append(boulder("15_Shore_Rock_Low", 11, 7, 2.0, 29))

    objects.append(palm("16_Palm_Tall", 22, 4.0, lean=0.10, fronds=8))
    objects.append(palm("17_Palm_Leaning", 18, 5.0, lean=0.34, fronds=8, coconuts=2))
    objects.append(palm("18_Palm_Short", 14, 6.0, lean=0.06, fronds=7, crown_r=1.1, coconuts=0))

    objects.append(driftwood("19_Driftwood_Log", 11, 5.0, radius=1.45))
    objects.append(join("20_Driftwood_Planks", [
        (driftwood("PlankA", 8.5, 7.0, radius=0.55), (0, 0, 0)),
        (driftwood("PlankB", 7, 8.0, radius=0.45), (0.5, 1.4, 0.25)),
    ]))
    objects.append(rowboat("21_Wrecked_Rowboat", length=10.5, beam=3.8, depth=1.8))
    objects.append(ground_disc("22_Tide_Pool_Small", 7, 5.5, 31, WATER, D_WATER, rim_role=SAND))
    objects.append(ground_disc("23_Tide_Pool_Large", 12, 9, 32, WATER, D_WATER, rim_role=SAND))
    objects.append(ground_disc("26_Tide_Pool_Big", 21, 16, 35, WATER, D_WATER, rim_role=SAND))
    objects.append(grass_patch("24_Grass_Patch_Small", 6, 5, 33, clumps=4))
    objects.append(grass_patch("25_Grass_Patch_Large", 10, 8, 34, clumps=5))

# ---------------------------------------------------------------------------
# bake each asset down to one atlas / one material
# ---------------------------------------------------------------------------
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 1
scene.render.bake.use_pass_direct = False
scene.render.bake.use_pass_indirect = False

for obj in objects:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    atlas_uv = obj.data.uv_layers.new(name="AtlasUV")
    obj.data.uv_layers.active = atlas_uv
    atlas_uv.active_render = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(85), island_margin=0.006)
    bpy.ops.object.mode_set(mode="OBJECT")

    atlas = bpy.data.images.new(obj.name + "_Color", width=ATLAS, height=ATLAS, alpha=False)
    atlas.filepath_raw = str(TEX / (obj.name.lower() + "-atlas.png"))
    atlas.file_format = "PNG"
    for m in MATERIALS:
        node = m.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = atlas
        m.node_tree.nodes.active = node
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=16, use_clear=True)
    # Writing a freshly baked 2048px PNG intermittently fails on this machine
    # (a different asset each run), which looks like a scanner holding the new
    # file briefly. Retry rather than losing the whole build and the .blend save.
    for attempt in range(6):
        try:
            atlas.save()
            break
        except RuntimeError:
            if attempt == 5:
                raise
            time.sleep(1.0)

    baked = bpy.data.materials.new(obj.name + "_Atlas")
    baked.use_nodes = True
    bs = baked.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Roughness"].default_value = 0.85
    bs.inputs["Metallic"].default_value = 0.0
    bs.inputs["Specular IOR Level"].default_value = 0.12
    tx = baked.node_tree.nodes.new("ShaderNodeTexImage")
    tx.image = atlas
    uvn = baked.node_tree.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "AtlasUV"
    baked.node_tree.links.new(uvn.outputs["UV"], tx.inputs["Vector"])
    baked.node_tree.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    obj.data.materials.clear()
    obj.data.materials.append(baked)
    for p in obj.data.polygons:
        p.material_index = 0
    for layer in list(obj.data.uv_layers):
        if layer.name != "AtlasUV":
            obj.data.uv_layers.remove(layer)
    # Clean up the temporary bake targets so the next asset starts fresh.
    for m in MATERIALS:
        for node in [n for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image == atlas]:
            m.node_tree.nodes.remove(node)
    print("ATLAS_READY", obj.name, flush=True)

# ---------------------------------------------------------------------------
# previews
# ---------------------------------------------------------------------------
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 2400
scene.render.resolution_y = 1400
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.72, 0.80, 0.86, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.75
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"

bpy.ops.mesh.primitive_plane_add(size=900, location=(0, 0, -0.05))
floor = bpy.context.object
floor.name = "Preview_Sand"
fm = bpy.data.materials.new("Preview_Sand_Mat")
fm.use_nodes = True
fbs = fm.node_tree.nodes["Principled BSDF"]
fbs.inputs["Roughness"].default_value = 1.0
ftx = fm.node_tree.nodes.new("ShaderNodeTexImage")
ftx.image = bpy.data.images.load(str(TEX / "sand.png"))
ftx.extension = "REPEAT"
fmap = fm.node_tree.nodes.new("ShaderNodeMapping")
fcoord = fm.node_tree.nodes.new("ShaderNodeTexCoord")
fmap.inputs["Scale"].default_value = (90, 90, 90)
fm.node_tree.links.new(fcoord.outputs["Generated"], fmap.inputs["Vector"])
fm.node_tree.links.new(fmap.outputs["Vector"], ftx.inputs["Vector"])
fm.node_tree.links.new(ftx.outputs["Color"], fbs.inputs["Base Color"])
floor.data.materials.append(fm)

bpy.ops.object.light_add(type="SUN")
sun = bpy.context.object
sun.data.energy = 2.1
sun.rotation_euler = (0.55, -0.30, -0.65)
sun.data.angle = 0.25
bpy.ops.object.light_add(type="AREA", location=(-60, -80, 90))
fill = bpy.context.object
fill.data.energy = 55000
fill.data.size = 120

bpy.ops.object.camera_add()
cam = bpy.context.object
cam.data.type = "ORTHO"
scene.camera = cam

labels = []
lm = bpy.data.materials.new("Preview_Label")
lm.use_nodes = True
lm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.05, 0.09, 0.14, 1)


def label(obj, size=1.9):
    bpy.ops.object.text_add(location=obj.location + Vector((0, -obj.dimensions.y * 0.5 - 4, 0.05)))
    t = bpy.context.object
    t.name = "Label_" + obj.name
    t.data.body = obj.name.replace("_", " ")
    t.data.align_x = "CENTER"
    t.data.size = size
    t.data.materials.append(lm)
    t.rotation_euler = (0, 0, 0)
    labels.append(t)
    return t


def render(filename, target, scale, vector=(0, -150, 120)):
    target = Vector(target)
    cam.location = target + Vector(vector)
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = scale
    scene.render.filepath = str(ROOT / "previews" / filename)
    bpy.ops.render.render(write_still=True)


def fit(group, vector=(0, -200, 190), pad=1.12):
    """Frame a whole group: returns (target, ortho_scale) with nothing cropped.

    An ortho camera's ortho_scale is its horizontal extent, so the vertical need
    has to be converted through the aspect ratio. Ground depth and object height
    both project onto screen-Y foreshortened by the camera's tilt, which for this
    rig is close to 45 degrees.
    """
    xs, ys, zs = [], [], []
    for o in group:
        c = o.location
        xs += [c.x - o.dimensions.x / 2, c.x + o.dimensions.x / 2]
        ys += [c.y - o.dimensions.y / 2, c.y + o.dimensions.y / 2]
        zs += [0.0, o.dimensions.z]
    tilt = math.cos(math.atan2(Vector(vector).z, abs(Vector(vector).y)))
    aspect = scene.render.resolution_x / scene.render.resolution_y
    wide = (max(xs) - min(xs))
    tall = ((max(ys) - min(ys)) + max(zs)) * tilt
    target = Vector(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, max(zs) * 0.35))
    return target, max(wide, tall * aspect) * pad


report = {"blender_version": bpy.app.version_string, "authoring": "final Roblox stud size; import at 1:1", "density_studs_per_repeat": {"rock": D_ROCK, "grass": D_GRASS, "bark": D_BARK, "frond": D_FROND, "wood": D_WOOD, "sand": D_SAND, "water": D_WATER}, "modules": {}}

if PREVIEW:
    for obj, x in zip(objects, (-55, -18, 18, 48)):
        obj.location = (x, 0, 0)
        label(obj)
    render("beach-style-preview.png", (0, 0, 14), 130, vector=(10, -150, 95))
else:
    rows = [objects[0:4], objects[4:8], objects[8:11],
            objects[11:16], objects[16:19], objects[19:25]]
    y = 0.0
    for group in rows:
        span = sum(o.dimensions.x for o in group) + 20 * (len(group) - 1)
        x = -span / 2
        depth = max(o.dimensions.y for o in group)
        y -= depth / 2
        for o in group:
            x += o.dimensions.x / 2
            o.location = (x, y, 0)
            label(o, size=2.4)
            x += o.dimensions.x / 2 + 20
        y -= depth / 2 + 26
    tgt, sc = fit(objects)
    render("beach-cove-lineup.png", tgt, sc)

    for lab in labels:
        lab.hide_render = True
    for o in objects:
        o.hide_render = True
    for name, filename, scale in (
        ("06_Headland_Tall_Mass", "cliff-closeup.png", 78),
        ("16_Palm_Tall", "palm-closeup.png", 52),
        ("21_Wrecked_Rowboat", "boat-closeup.png", 22),
        ("23_Tide_Pool_Large", "tidepool-closeup.png", 26),
    ):
        o = next(x for x in objects if x.name == name)
        o.hide_render = False
        render(filename, o.location + Vector((0, 0, o.dimensions.z * 0.45)), scale, vector=(34, -70, 46))
        o.hide_render = True
    for o in objects:
        o.hide_render = False
    for lab in labels:
        lab.hide_render = False

    # ---- export ----
    for obj in objects:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        old = obj.location.copy()
        obj.location = (0, 0, 0)
        obj.data.name = obj.name
        stem = obj.name.lower().replace("_", "-")
        bpy.ops.export_scene.gltf(filepath=str(ROOT / "exports/glb" / f"{stem}.glb"), export_format="GLB",
                                  use_selection=True, export_apply=True)
        bpy.ops.export_scene.fbx(filepath=str(ROOT / "exports/fbx" / f"{stem}.fbx"), use_selection=True,
                                 object_types={"MESH"}, axis_forward="-Z", axis_up="Y", path_mode="COPY",
                                 embed_textures=True, add_leaf_bones=False)
        obj.data.calc_loop_triangles()
        report["modules"][obj.name] = {
            "file_stem": stem,
            "triangles": len(obj.data.loop_triangles),
            "vertices": len(obj.data.vertices),
            "materials": 1,
            "dimensions_studs": [round(v, 3) for v in obj.dimensions],
            "atlas_size": ATLAS,
            "pivot": "ground-level local origin",
        }
        obj.location = old
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2))
    tgt, sc = fit(objects)
    render("beach-cove-lineup.png", tgt, sc)

for im in bpy.data.images:
    if im.source == "FILE":
        im.pack()
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / ("beach-style-preview.blend" if PREVIEW else "beach-cove-kit.blend")))
print("KIT_READY", ROOT, flush=True)
