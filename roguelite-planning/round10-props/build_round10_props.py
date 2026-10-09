"""Round 10 static props: upright sarcophagus (body + lid), broken-sarcophagus kit, volcanic vent, volcanic debris.

Self-contained generator (no imports from sibling folders). Blender 5.2, background only:

    blender -b --threads 4 --python-exit-code 1 --python build_round10_props.py              # build + export + manifest + .blend
    blender -b --threads 4 --python-exit-code 1 --python build_round10_props.py -- render     # previews from the exported FBX files

Units are studs at template scale 1 (import at 1:1, do not scale). Blender frame: +Z up, open face of the coffin toward -Y.
FBX: axis_forward='-Z', axis_up='Y' (Blender -Y front == Roblox -Z front).
Art brief: ../plans/2026-10-09-round10-art-brief.md  Reference sheets: ../art-references/round-10-modeling-pack-2026-10-09/
"""
import hashlib
import json
import math
import random
import shutil
import struct
import sys
import zlib
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT / "exports"
TEXTURES = ROOT / "textures"
PREVIEWS = ROOT / "previews"
REFS = ROOT.parent / "art-references" / "round-10-modeling-pack-2026-10-09"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = "render" if "render" in ARGS else "build"
ONLY = [a for a in ARGS if a in ("sarcophagus", "broken", "vent", "debris")]     # render only these sheets (default: all)

# ---------------------------------------------------------------------------------------------
# Dimensions (brief section 5). Coffin frame: x = width, y = depth (front/open face at -Y), z = up.
# ---------------------------------------------------------------------------------------------
Y_F = -2.25          # front rim plane of the body (the opening); cavity floor centre is (0, 0, 0.5)
Y_B = 2.95           # back face of the body (solid flat back)
Y_CB = 2.25          # inner face of the back wall (cavity depth 4.5)
T_SLAB = 0.85        # lid slab thickness (front plane of the slab is Y_F - T_SLAB)
Y_S = Y_F - T_SLAB
OUT_H = 11.0         # outer height (coordinator fix pass: taller, clearer anthropoid silhouette)
SHOULDER_X, SHOULDER_Z = 3.64, 7.70     # widest point (half-width, height ~70% of OUT_H)
HEAD_X = 2.05        # head half-width (head section is clearly narrower than the shoulders)
WALL = 0.50          # side wall thickness (outside tapers more than the cavity does)
WALL_DIAG = 0.40     # shoulder-diagonal wall (keeps the cavity 6.2+ wide at the shoulders)
FLOOR = 0.80         # floor thickness
CEIL = 0.80          # head-top thickness: cavity height = OUT_H - FLOOR - CEIL = 9.4
BEVEL = 0.14
NOTCH_Z = (4.9, 9.88)

# Atlas tiles for the coffin family (image px, top-left origin): rect x0,y0,x1,y1 and px-per-unit.
TILE_OUTER, TILE_CAVITY, TILE_FRACT, TILE_BAND, TILE_FACE, TILE_EYE = 0, 1, 2, 3, 4, 5
CO_ATLAS = 1024
CO_TILES = {
    TILE_OUTER: ((0, 0, 512, 512), 512 / 12.0),
    TILE_BAND: ((512, 0, 1024, 512), 512 / 12.0),
    TILE_CAVITY: ((0, 512, 512, 896), 33.0),
    TILE_FRACT: ((512, 512, 1024, 896), 33.0),
    TILE_FACE: ((0, 896, 256, 1024), 40.0),
    TILE_EYE: ((256, 896, 384, 1024), 60.0),
}
# per tile, per axis class (0 = X-dominant normal, 1 = Y, 2 = Z): (a0, b0) world offsets of the planar mapping
CO_ORIGIN = {
    TILE_OUTER: {1: (-6.0, -0.15), 0: (-4.0, -0.15), 2: (-6.0, -4.0)},
    TILE_BAND: {1: (-6.0, -0.15), 0: (-4.0, -0.15), 2: (-6.0, -4.0)},
    TILE_CAVITY: {1: (-6.0, -0.15), 0: (-3.0, -0.15), 2: (-6.0, -3.0)},
    TILE_FRACT: {1: (-6.0, -0.1), 0: (-4.0, -0.1), 2: (-6.0, -4.0)},
    TILE_FACE: {1: (-1.7, 8.0), 0: (-3.4, 8.0), 2: (-1.7, -3.4)},
    TILE_EYE: {1: (-1.0, 8.4), 0: (-3.5, 8.4), 2: (-1.0, -3.5)},
}

VENT_ATLAS = 512
V_ROCK, V_ROCKHOT, V_LAVA, V_EMBER = 0, 1, 2, 3
VENT_TILES = {
    V_ROCK: ((0, 0, 384, 384), 32.0),
    V_ROCKHOT: ((0, 384, 384, 512), 32.0),
    V_LAVA: ((384, 0, 512, 128), 12.8),
    V_EMBER: ((384, 128, 512, 256), 120.0),
}


def log(*a):
    print("[round10]", *a, flush=True)


# ---------------------------------------------------------------------------------------------
# PNG writing + procedural painting (numpy only, so the generator needs nothing outside Blender)
# ---------------------------------------------------------------------------------------------
def write_png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def ss(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def hash2(ix, iy, seed):
    n = (ix * 374761393 + iy * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n = n ^ (n >> 16)
    return (n & 0xFFFFFF) / float(0x1000000)


def vnoise(X, Y, seed):
    ix = np.floor(X).astype(np.int64)
    iy = np.floor(Y).astype(np.int64)
    fx = ss(X - ix, 0, 1)
    fy = ss(Y - iy, 0, 1)
    h00, h10 = hash2(ix, iy, seed), hash2(ix + 1, iy, seed)
    h01, h11 = hash2(ix, iy + 1, seed), hash2(ix + 1, iy + 1, seed)
    return (h00 * (1 - fx) + h10 * fx) * (1 - fy) + (h01 * (1 - fx) + h11 * fx) * fy


def fbm(X, Y, seed, octs=3):
    tot, amp, norm = 0.0, 1.0, 0.0
    for o in range(octs):
        tot = tot + amp * vnoise(X * 2 ** o, Y * 2 ** o, seed + 101 * o)
        norm += amp
        amp *= 0.5
    return tot / norm


def voronoi(X, Y, seed, jitter=0.85):
    ix = np.floor(X).astype(np.int64)
    iy = np.floor(Y).astype(np.int64)
    best = np.full(X.shape, 9.0)
    sec = np.full(X.shape, 9.0)
    val = np.zeros(X.shape)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            cx, cy = ix + dx, iy + dy
            px = cx + 0.5 + (hash2(cx, cy, seed) - 0.5) * jitter
            py = cy + 0.5 + (hash2(cx, cy, seed + 7) - 0.5) * jitter
            d = np.hypot(X - px, Y - py)
            closer = d < best
            sec = np.where(closer, best, np.minimum(sec, d))
            val = np.where(closer, hash2(cx, cy, seed + 13), val)
            best = np.where(closer, d, best)
    return best, sec, val


def paint_stone(w, h, ppu, seed, pal, terra_cov=0.34, light_cov=0.3, patch_wave=2.4, chip_cell=0.34,
                chip_amp=0.035, edge_amp=0.025, soft=0.028, rag=0.11):
    """Painterly mottled stone: broad patches with chip-ragged edges, 2-4 value ranges, faint chip facets.
    ppu = px per world unit."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    ux, uy = xs / ppu, ys / ppu
    wx = ux + 0.9 * (fbm(ux / 2.5, uy / 2.5, seed + 1) - 0.5) * 2
    wy = uy + 0.9 * (fbm(ux / 2.5 + 31, uy / 2.5 + 17, seed + 2) - 0.5) * 2
    best, sec, val = voronoi(ux / chip_cell, uy / chip_cell, seed + 5)
    n = fbm(wx / patch_wave, wy / patch_wave, seed + 3) + rag * (val - 0.5)
    thr = np.quantile(n, 1 - terra_cov)
    m1 = ss(n, thr - soft, thr + soft)
    deep = ss(n, thr + 0.07 - soft, thr + 0.07 + soft)
    n2 = fbm(wx / (patch_wave * 0.7) + 9, wy / (patch_wave * 0.7) + 5, seed + 4) + rag * (val - 0.5)
    q2 = np.quantile(n2, 1 - light_cov)
    l = ss(n2, q2 - soft, q2 + soft)
    base, light = np.array(pal["base"], float), np.array(pal["light"], float)
    terra, tdark = np.array(pal["terra"], float), np.array(pal["terra_dark"], float)
    col = base[None, None, :] * (1 - m1[..., None]) + terra[None, None, :] * m1[..., None]
    col = col * (1 - 0.6 * deep[..., None]) + tdark[None, None, :] * (0.6 * deep[..., None])
    lw = (0.6 * l * (1 - m1))[..., None]
    col = col * (1 - lw) + light[None, None, :] * lw
    col *= (1 + (val - 0.5) * 2 * chip_amp)[..., None]
    col *= (1 - edge_amp * (1 - ss(sec - best, 0.0, 0.10)))[..., None]
    col *= (1 + (fbm(ux / 4.0 + 3, uy / 4.0 + 8, seed + 6) - 0.5) * 0.10)[..., None]
    rng = np.random.default_rng(seed)
    col *= (1 + rng.normal(0, 0.006, (h, w, 1)))
    return np.clip(col, 0, 255)


STONE_OUTER = dict(base=(226, 184, 140), light=(240, 206, 166), terra=(204, 112, 68), terra_dark=(178, 90, 54))
STONE_CAVITY = dict(base=(190, 140, 98), light=(204, 154, 110), terra=(176, 108, 70), terra_dark=(150, 90, 58))
STONE_FRACT = dict(base=(176, 126, 84), light=(196, 148, 102), terra=(158, 96, 60), terra_dark=(136, 80, 50))
STONE_BAND = dict(base=(238, 206, 164), light=(248, 226, 190), terra=(224, 164, 116), terra_dark=(206, 140, 98))
BASALT = dict(base=(92, 78, 86), light=(130, 114, 122), terra=(70, 56, 68), terra_dark=(54, 42, 54))


def paste(atlas, rect, art):
    x0, y0, x1, y1 = rect
    atlas[y0:y1, x0:x1, :] = art[: y1 - y0, : x1 - x0, :]


def paint_soft(w, h, ppu, seed, pal, terra_cov=0.28, light_cov=0.30, patch_wave=3.4, soft=0.05):
    """Broad soft painterly stone for the coffin family: sandy base, a few large soft-edged terracotta mottles, one
    low-contrast lighter patch layer and a gentle large-scale value drift. No cells, no chips, no grain."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    ux, uy = xs / ppu, ys / ppu
    wx = ux + 1.1 * (fbm(ux / 3.0, uy / 3.0, seed + 1) - 0.5) * 2
    wy = uy + 1.1 * (fbm(ux / 3.0 + 31, uy / 3.0 + 17, seed + 2) - 0.5) * 2
    n = fbm(wx / patch_wave, wy / patch_wave, seed + 3, octs=2)
    thr = np.quantile(n, 1 - terra_cov)
    m1 = ss(n, thr - soft, thr + soft)
    deep = ss(n, thr + 0.09 - soft, thr + 0.09 + soft)
    n2 = fbm(wx / (patch_wave * 0.8) + 9, wy / (patch_wave * 0.8) + 5, seed + 4, octs=2)
    q2 = np.quantile(n2, 1 - light_cov)
    l = ss(n2, q2 - soft, q2 + soft)
    base, light = np.array(pal["base"], float), np.array(pal["light"], float)
    terra, tdark = np.array(pal["terra"], float), np.array(pal["terra_dark"], float)
    col = base[None, None, :] * (1 - m1[..., None]) + terra[None, None, :] * m1[..., None]
    col = col * (1 - 0.55 * deep[..., None]) + tdark[None, None, :] * (0.55 * deep[..., None])
    lw = (0.55 * l * (1 - m1))[..., None]
    col = col * (1 - lw) + light[None, None, :] * lw
    col *= (1 + (fbm(ux / 5.0 + 3, uy / 5.0 + 8, seed + 6, octs=2) - 0.5) * 0.10)[..., None]
    return np.clip(col, 0, 255)


def paint_coffin_atlas():
    atlas = np.zeros((CO_ATLAS, CO_ATLAS, 3), float)
    atlas[:] = (226, 184, 140)
    (r0, s0), (r3, s3) = CO_TILES[TILE_OUTER], CO_TILES[TILE_BAND]
    paste(atlas, r0, paint_soft(512, 512, s0, 11, STONE_OUTER, terra_cov=0.30, light_cov=0.30))
    paste(atlas, r3, paint_soft(512, 512, s3, 23, STONE_BAND, terra_cov=0.12, light_cov=0.35))
    r1, s1 = CO_TILES[TILE_CAVITY]
    paste(atlas, r1, paint_soft(512, 384, s1, 37, STONE_CAVITY, terra_cov=0.20))
    r2, s2 = CO_TILES[TILE_FRACT]
    paste(atlas, r2, paint_soft(512, 384, s2, 53, STONE_FRACT, terra_cov=0.24))
    # face plate: dark terracotta-brown, softly mottled; eyes: warm ochre with a soft top-left highlight
    rf, sf = CO_TILES[TILE_FACE]
    face = paint_soft(256, 128, sf, 61, dict(base=(158, 94, 58), light=(170, 104, 64), terra=(144, 82, 52),
                                             terra_dark=(128, 72, 46)), terra_cov=0.4, patch_wave=2.0)
    paste(atlas, rf, face)
    re_, se = CO_TILES[TILE_EYE]
    yy, xx = np.mgrid[0:128, 0:128].astype(float)
    hl = np.clip(1 - np.hypot(xx - 50, yy - 44) / 90.0, 0, 1)[..., None]
    eye = np.array((226, 176, 112))[None, None, :] * (0.92 + 0.14 * hl) + 0 * xx[..., None]
    paste(atlas, re_, eye)
    return np.clip(atlas, 0, 255).astype(np.uint8)


def paint_vent_atlas():
    atlas = np.zeros((VENT_ATLAS, VENT_ATLAS, 3), float)
    atlas[:] = (88, 74, 82)
    r, s = VENT_TILES[V_ROCK]
    paste(atlas, r, paint_stone(384, 384, s, 71, BASALT, terra_cov=0.34, light_cov=0.30, patch_wave=2.6,
                                chip_cell=0.6, chip_amp=0.07, edge_amp=0.07, rag=0.13))
    rh, sh = VENT_TILES[V_ROCKHOT]
    hot = paint_stone(384, 128, sh, 83, BASALT, terra_cov=0.34, light_cov=0.30, patch_wave=2.6, chip_cell=0.6,
                      chip_amp=0.07, edge_amp=0.07, rag=0.13)
    rows = np.arange(128)[:, None]
    z = (127 - rows) / 90.0                      # height above the tile bottom row (v = z * 90 px)
    heat = np.clip(1 - z / 1.0, 0, 1) ** 1.7
    glow = np.array((236, 98, 28), float)[None, None, :]
    hot = hot * (1 - 0.85 * heat[..., None]) + glow * 0.85 * heat[..., None]
    paste(atlas, rh, hot)
    rl, sl = VENT_TILES[V_LAVA]
    yy, xx = np.mgrid[0:128, 0:128].astype(float)
    X, Y = xx / sl - 5.0, yy / sl - 5.0
    r_ = np.hypot(X, Y)
    t = np.clip(r_, 0, 6)
    c0, c1, c2, c3 = (np.array(c, float) for c in ((255, 190, 66), (255, 138, 30), (246, 100, 22), (214, 62, 16)))
    lava = np.where((t < 0.9)[..., None], c0, 0)
    f1 = ss(t, 0.5, 1.6)[..., None]
    f2 = ss(t, 1.8, 3.0)[..., None]
    f3 = ss(t, 3.2, 5.0)[..., None]
    col = c0 * (1 - f1) + c1 * f1
    col = col * (1 - f2) + c2 * f2
    col = col * (1 - f3) + c3 * f3
    veins = (fbm(X * 1.1, Y * 1.1, 91) - 0.5)[..., None]
    col = col * (1 + 0.16 * veins)
    paste(atlas, rl, col)
    re_, se = VENT_TILES[V_EMBER]
    yy, xx = np.mgrid[0:128, 0:128].astype(float)
    n = fbm(xx / 24.0, yy / 24.0, 97)
    m = ss(n, 0.42, 0.58)[..., None]
    ember = np.array((190, 100, 42), float) * (1 - m) + np.array((128, 58, 32), float) * m
    hi = ss(fbm(xx / 18.0 + 5, yy / 18.0 + 3, 99), 0.58, 0.7)[..., None]
    ember = ember * (1 - 0.45 * hi) + np.array((236, 150, 64), float) * 0.45 * hi
    paste(atlas, re_, ember)
    return np.clip(atlas, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------------------------
def collection(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


SCRATCH = None


def scratch():
    global SCRATCH
    if SCRATCH is None:
        SCRATCH = collection("_scratch")
    return SCRATCH


def obj_from_bm(name, bm, coll=None, free=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    if free:
        bm.free()
    ob = bpy.data.objects.new(name, me)
    (coll or scratch()).objects.link(ob)
    return ob


def bm_from_obj(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    return bm


def remove_obj(ob):
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if me.users == 0:
        bpy.data.meshes.remove(me)


def apply_modifier_stack(ob):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    new = bpy.data.meshes.new_from_object(ev)
    old = ob.data
    for m in list(ob.modifiers):
        ob.modifiers.remove(m)
    ob.data = new
    if old.users == 0:
        bpy.data.meshes.remove(old)


def boolean(target, operand, op, collection_operand=None, use_self=False):
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = op
    m.solver = "EXACT"
    if collection_operand is not None:
        m.operand_type = "COLLECTION"
        m.collection = collection_operand
    else:
        m.operand_type = "OBJECT"
        m.object = operand
    m.use_self = use_self
    apply_modifier_stack(target)


def bevel(ob, width, segments=1, profile=0.5):
    m = ob.modifiers.new("bevel", "BEVEL")
    m.limit_method = "WEIGHT"
    m.edge_weight = "bevel_weight_edge"
    m.offset_type = "OFFSET"
    m.width = width
    m.segments = segments
    m.profile = profile
    m.use_clamp_overlap = True
    m.loop_slide = True
    apply_modifier_stack(ob)
    me = ob.data
    if "bevel_weight_edge" in me.attributes:
        me.attributes.remove(me.attributes["bevel_weight_edge"])


def set_weights(ob, fn):
    bm = bm_from_obj(ob)
    bm.edges.ensure_lookup_table()
    bm.normal_update()
    lay = bm.edges.layers.float.get("bevel_weight_edge") or bm.edges.layers.float.new("bevel_weight_edge")
    n = 0
    for e in bm.edges:
        w = fn(e, bm)
        e[lay] = w
        n += w > 0
    bm.to_mesh(ob.data)
    bm.free()
    return n


def clean(bm, merge=1e-5, dissolve=True):
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=merge)
    if dissolve:
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.4), use_dissolve_boundaries=False,
                                 verts=bm.verts[:], edges=bm.edges[:], delimit=set())
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()


def tri_count(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


def manifold_report(bm):
    bad = [e for e in bm.edges if len(e.link_faces) != 2]
    return len(bad)


def islands(bm):
    seen, out = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, comp = [f], []
        seen.add(f.index)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb.index not in seen:
                        seen.add(nb.index)
                        stack.append(nb)
        out.append(comp)
    return out


def keep_largest_island(bm):
    bm.faces.ensure_lookup_table()
    for i, f in enumerate(bm.faces):
        f.index = i
    comps = islands(bm)
    comps.sort(key=lambda c: -sum(f.calc_area() for f in c))
    dropped = comps[1:]
    if dropped:
        bmesh.ops.delete(bm, geom=[f for c in dropped for f in c], context="FACES")
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.normal_update()
    return len(dropped), [round(sum(f.calc_area() for f in c), 3) for c in dropped]


def volume_centroid_bbox(bm):
    lo = Vector((min(v.co.x for v in bm.verts), min(v.co.y for v in bm.verts), min(v.co.z for v in bm.verts)))
    hi = Vector((max(v.co.x for v in bm.verts), max(v.co.y for v in bm.verts), max(v.co.z for v in bm.verts)))
    return lo, hi


def offset_poly(pts, d):
    """Inset a CCW polygon (x,z) with a distance per edge (edge i goes pts[i] -> pts[i+1])."""
    n = len(pts)
    res = []
    for i in range(n):
        pa, pb, pc = pts[i - 1], pts[i], pts[(i + 1) % n]
        da = (pb[0] - pa[0], pb[1] - pa[1])
        la = math.hypot(*da)
        da = (da[0] / la, da[1] / la)
        db = (pc[0] - pb[0], pc[1] - pb[1])
        lb = math.hypot(*db)
        db = (db[0] / lb, db[1] / lb)
        na, nb = (-da[1], da[0]), (-db[1], db[0])
        ca = na[0] * pb[0] + na[1] * pb[1] + d[i - 1]
        cb = nb[0] * pb[0] + nb[1] * pb[1] + d[i]
        det = na[0] * nb[1] - na[1] * nb[0]
        res.append(((ca * nb[1] - cb * na[1]) / det, (na[0] * cb - nb[0] * ca) / det))
    return res


def prism_bm(poly, y0, y1):
    bm = bmesh.new()
    a = [bm.verts.new((x, y0, z)) for x, z in poly]
    b = [bm.verts.new((x, y1, z)) for x, z in poly]
    bm.faces.new(a)
    bm.faces.new(b)
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def jagged_prism_bm(poly, y_rings, jit, seed):
    """Prism through a polygon with independent vertex jitter per ring: non-planar side facets (triangulated)."""
    rng = random.Random(seed)
    bm = bmesh.new()
    rings = []
    for k, y in enumerate(y_rings):
        j = 0.0 if k in (0, len(y_rings) - 1) else 1.0
        rings.append([bm.verts.new((x + rng.uniform(-jit, jit) * j, y, z + rng.uniform(-jit, jit) * j))
                      for x, z in poly])
    n = len(poly)
    bm.faces.new(rings[0])
    bm.faces.new(rings[-1])
    for k in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            a, b, c, d = rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]
            if (i + k) % 2:
                bm.faces.new((a, b, c))
                bm.faces.new((a, c, d))
            else:
                bm.faces.new((a, b, d))
                bm.faces.new((b, c, d))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def poly_interp_halfwidth(poly, z):
    """Half-width (x>0 side) of a symmetric polygon at height z (largest crossing)."""
    best = 0.0
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        if min(z0, z1) - 1e-9 <= z <= max(z0, z1) + 1e-9 and abs(z1 - z0) > 1e-9:
            t = (z - z0) / (z1 - z0)
            best = max(best, x0 + t * (x1 - x0))
    return best


# ---------------------------------------------------------------------------------------------
# Surface index: tile classification by nearest source surface
# ---------------------------------------------------------------------------------------------
class SurfaceIndex:
    def __init__(self, sources):
        """sources: list of (bm, tiles list-per-face | int, sign). sign=-1 flips normals (cutter volumes)."""
        verts, tris, tiles, norms = [], [], [], []
        for bm, tl, sign in sources:
            b2 = bm.copy()
            lay = b2.faces.layers.int.new("tl")
            b2.faces.ensure_lookup_table()
            for i, f in enumerate(b2.faces):
                f[lay] = tl if isinstance(tl, int) else tl[i]
            bmesh.ops.triangulate(b2, faces=b2.faces[:])
            base = len(verts)
            b2.verts.ensure_lookup_table()
            verts.extend(v.co.copy() for v in b2.verts)
            idx = {v.index: v.index for v in b2.verts}
            for f in b2.faces:
                tris.append(tuple(base + v.index for v in f.verts))
                tiles.append(f[lay])
                norms.append(f.normal.copy() * sign)
            b2.free()
        self.tree = BVHTree.FromPolygons(verts, tris, all_triangles=True)
        self.tiles, self.norms = tiles, norms

    def classify(self, bm, tol, dotmin=0.3, default=None, prefer_high=True):
        bm.normal_update()
        out = []
        for f in bm.faces:
            c = f.calc_center_median()
            best = None
            for loc, nrm, idx, dist in self.tree.find_nearest_range(c, tol):
                if f.normal.dot(self.norms[idx]) < dotmin:
                    continue
                key = (round(dist, 4), -self.tiles[idx] if prefer_high else 0)
                if best is None or key < best[0]:
                    best = (key, self.tiles[idx])
            out.append(best[1] if best else default)
        return out


# ---------------------------------------------------------------------------------------------
# UV assignment: global planar projection by dominant normal axis into atlas tiles
# ---------------------------------------------------------------------------------------------
def dominant_axis(n):
    ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
    if ay >= ax and ay >= az:
        return 1
    return 0 if ax >= az else 2


def planar_ab(co, axis):
    if axis == 1:
        return co.x, co.z
    if axis == 0:
        return co.y, co.z
    return co.x, co.y


def atlas_uv(tile, a, b, tiles_def, atlas_px, origins, axis):
    (x0, y0, x1, y1), s = tiles_def[tile]
    a0, b0 = origins[tile][axis]
    px = x0 + (a - a0) * s
    py_up = (atlas_px - y1) + (b - b0) * s              # v in px measured from the atlas bottom
    px = min(max(px, x0 + 2), x1 - 2)
    py_up = min(max(py_up, atlas_px - y1 + 2), atlas_px - y0 - 2)
    return px / atlas_px, py_up / atlas_px


def assign_uv_coffin(bm, tiles):
    uv = bm.loops.layers.uv.verify()
    bm.normal_update()
    for f, t in zip(bm.faces, tiles):
        ax = dominant_axis(f.normal)
        for l in f.loops:
            a, b = planar_ab(l.vert.co, ax)
            l[uv].uv = atlas_uv(t, a, b, CO_TILES, CO_ATLAS, CO_ORIGIN, ax)


# ---------------------------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------------------------
def atlas_material(name, png_path, emission=0.0):
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    img = bpy.data.images.load(str(png_path), check_existing=False)
    img.colorspace_settings.name = "sRGB"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    for k in ("Specular IOR Level", "Specular"):
        if k in bsdf.inputs:
            bsdf.inputs[k].default_value = 0.05
    if emission > 0:                       # preview only: Studio makes this mesh Neon
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Strength"].default_value = emission
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
        out = nt.nodes.get("Material Output")
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def finish_mesh(ob, mat):
    me = ob.data
    for name in ("tile", "bevel_weight_edge", "tl"):
        if name in me.attributes:
            me.attributes.remove(me.attributes[name])
    me.materials.clear()
    me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = False
    me.update()


# =============================================================================================
# 1. SARCOPHAGUS
# =============================================================================================
def outline_polys():
    """Anthropoid coffin silhouette (x half-width, z up): narrow head, widest at the shoulders (~70% of the height),
    clear taper down to a stepped foot block. Returns outer (with grooves), base (no grooves), inner (cavity), panel."""
    R = [(2.50, 0.0), (2.50, 1.10), (2.28, 1.10), (SHOULDER_X, SHOULDER_Z), (HEAD_X, 9.45), (HEAD_X, 10.30), (1.45, OUT_H)]

    pts = list(R)
    outer = pts + [(-x, z) for x, z in reversed(pts)]
    x0 = 2.28 + (SHOULDER_X - 2.28) / (SHOULDER_Z - 1.10) * (0.0 - 1.10)
    half = [(x0, 0.0), (SHOULDER_X, SHOULDER_Z), (HEAD_X, 9.45), (HEAD_X, 10.30), (1.45, OUT_H)]
    base = half + [(-x, z) for x, z in reversed(half)]
    # edge order: taper, shoulder diagonal, head wall, top chamfer, top, then the mirror, then the floor
    dists = [WALL, WALL_DIAG, WALL, WALL, CEIL, WALL, WALL, WALL_DIAG, WALL, FLOOR]
    inner = offset_poly(base, dists)
    panel = offset_poly(base, [0.62] * 10)
    return outer, base, inner, panel


def silhouette_weight_fn(inner_poly=None, lo_angle=math.radians(22)):
    """Bevel every convex edge sharper than ~22 degrees."""
    def fn(e, bm_=None):
        if not e.is_convex:
            return 0.0
        try:
            return 1.0 if e.calc_face_angle() >= lo_angle else 0.0
        except ValueError:
            return 0.0
    return fn


def groove_cutter_bm(w=0.10, d=0.09):
    """Four V prisms (two per side) running through the depth: the stone-block grooves on the taper and the head wall."""
    R2, R3 = (2.28, 1.10), (SHOULDER_X, SHOULDER_Z)
    R4, R5 = (HEAD_X, 9.45), (HEAD_X, 10.30)
    bms = []
    for (p, q, z0) in ((R2, R3, NOTCH_Z[0]), (R4, R5, NOTCH_Z[1])):
        dx, dz = q[0] - p[0], q[1] - p[1]
        L = math.hypot(dx, dz)
        ux, uz = dx / L, dz / L
        t = (z0 - p[1]) / dz
        m = (p[0] + dx * t, z0)
        nx, nz = -uz, ux                      # inward normal (CCW polygon, right side)
        for sgn in (1, -1):
            def P(a_u, a_n):                   # a_u along the edge, a_n inward (negative = outside)
                x = m[0] + ux * a_u + nx * a_n
                z = m[1] + uz * a_u + nz * a_n
                return (sgn * x, z)
            tri = [P(-(w + 0.25), -0.25), P(0.0, d), P(w + 0.25, -0.25)]
            if sgn == -1:
                tri = tri[::-1]
            bms.append(prism_bm(tri, Y_S - 2.0, Y_B + 2.0))
    out = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new("tmp_g")
        b.to_mesh(me)
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
        b.free()
    bmesh.ops.recalc_face_normals(out, faces=out.faces[:])
    return out


def cut_grooves(ob):
    cut = obj_from_bm("grooves", groove_cutter_bm())
    boolean(ob, cut, "DIFFERENCE")
    remove_obj(cut)


def build_body(outer, inner):
    log("body: boolean")
    outer_bm = prism_bm(outer, Y_F, Y_B)
    cav_bm = prism_bm(inner, Y_F - 0.5, Y_CB)
    body = obj_from_bm("body_raw", outer_bm.copy(), free=True)
    cutter = obj_from_bm("body_cut", cav_bm.copy())
    boolean(body, cutter, "DIFFERENCE")
    bm = bm_from_obj(body)
    clean(bm)
    bm.to_mesh(body.data)
    bm.free()
    n = set_weights(body, silhouette_weight_fn(inner))
    log("body: bevel edges", n)
    bevel(body, BEVEL, 2)
    cut_grooves(body)
    bm = bm_from_obj(body)
    clean(bm, dissolve=False)
    # classify cavity vs outer by nearest source volume
    idx = SurfaceIndex([(outer_bm, TILE_OUTER, 1), (cav_bm, TILE_CAVITY, -1)])
    tiles = idx.classify(bm, tol=0.2, dotmin=0.25, default=TILE_OUTER, prefer_high=False)
    bm.to_mesh(body.data)
    outer_bm.free()
    cav_bm.free()
    remove_obj(cutter)
    return body, bm, tiles


def band_prism(cx, cz, ang_deg, width, y_front, y_back, length=16.0):
    a = math.radians(ang_deg)
    d = (math.cos(a), math.sin(a))
    n = (-d[1], d[0])
    h = length / 2
    w = width / 2
    poly = [(cx - d[0] * h - n[0] * w, cz - d[1] * h - n[1] * w), (cx + d[0] * h - n[0] * w, cz + d[1] * h - n[1] * w),
            (cx + d[0] * h + n[0] * w, cz + d[1] * h + n[1] * w), (cx - d[0] * h + n[0] * w, cz - d[1] * h + n[1] * w)]
    return prism_bm(poly, y_front, y_back)


def band_round(cx, cz, ang_deg, width, y_plane, y_back, height, length=18.0, m=4):
    """Rounded (pillow-profile) bandage band: half-ellipse cross-section rising `height` in front of y_plane,
    straight along its direction; the back sits embedded in the slab."""
    a = math.radians(ang_deg)
    d = (math.cos(a), math.sin(a))
    n = (-d[1], d[0])
    prof = [(-width / 2, y_back), (-width / 2, y_plane)]
    for k in range(1, m + 1):
        phi = math.pi * k / (m + 1)
        prof.append((-width / 2 * math.cos(phi), y_plane - height * math.sin(phi)))
    prof += [(width / 2, y_plane), (width / 2, y_back)]
    bm = bmesh.new()
    ends = []
    for sgn in (-1, 1):
        ring = []
        for s_, y_ in prof:
            ring.append(bm.verts.new((cx + d[0] * sgn * length / 2 + n[0] * s_, y_, cz + d[1] * sgn * length / 2 + n[1] * s_)))
        ends.append(ring)
    bm.faces.new(ends[0])
    bm.faces.new(ends[1])
    k_ = len(prof)
    for i in range(k_):
        j = (i + 1) % k_
        bm.faces.new((ends[0][i], ends[0][j], ends[1][j], ends[1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def eye_dome(cx, cz, r=0.31, n=12):
    """Round domed eye button (convex hull of stacked rings), base embedded in the lid."""
    pts = []
    for rr, y in ((r, Y_S + 0.10), (r, Y_S - 0.05), (r * 0.94, Y_S - 0.14), (r * 0.72, Y_S - 0.23), (r * 0.38, Y_S - 0.30)):
        for k in range(n):
            a = 2 * math.pi * k / n + 0.2
            pts.append(Vector((cx + rr * math.cos(a), y, cz + rr * math.sin(a))))
    return hull_bm(pts)


def disc_poly(cx, cz, r, n=10):
    return [(cx + r * math.cos(2 * math.pi * i / n + 0.2), cz + r * math.sin(2 * math.pi * i / n + 0.2)) for i in range(n)]


def octagon_poly(cx, cz, hw, hh, ch):
    return [(cx - hw + ch, cz - hh), (cx + hw - ch, cz - hh), (cx + hw, cz - hh + ch), (cx + hw, cz + hh - ch),
            (cx + hw - ch, cz + hh), (cx - hw + ch, cz + hh), (cx - hw, cz + hh - ch), (cx - hw, cz - hh + ch)]


def open_edges_of(ob, label):
    bm = bm_from_obj(ob)
    n = manifold_report(bm)
    if n:
        bad = [e for e in bm.edges if len(e.link_faces) != 2][:6]
        log("   bad edges", [(tuple(round(c, 3) for c in (e.verts[0].co + e.verts[1].co) / 2), len(e.link_faces)) for e in bad])
    bm.free()
    log("  stage", label, "open edges", n)
    return n


def build_lid(outer, inner, panel):
    log("lid: slab")
    rng = random.Random(5)
    slab_raw = prism_bm(outer, Y_S, Y_F)
    slab = obj_from_bm("lid_slab", slab_raw.copy())
    bm = bm_from_obj(slab)
    clean(bm, dissolve=False)
    bm.to_mesh(slab.data)
    bm.free()
    set_weights(slab, silhouette_weight_fn(inner))
    bevel(slab, BEVEL, 2)
    cut_grooves(slab)

    # relief components (raw prisms: also the sources for tile classification)
    emb = 0.10                                          # embed depth inside the slab
    comps = []                                          # (bm, tile)
    plate_t, eye_t = 0.12, 0.24
    comps.append((prism_bm(octagon_poly(0, 9.62, 1.30, 0.52, 0.24), Y_S + emb, Y_S - plate_t), TILE_FACE))
    for sx in (-0.60, 0.60):
        comps.append((eye_dome(sx, 9.62), TILE_EYE))
    # wrapped-mummy bands (rounded, pillow-profile): forehead pair, chin pair, a diamond lattice down the torso, ankle wrap
    bands = [(0, 10.22, 12, 0.46), (0, 10.22, -12, 0.46), (0, 8.55, 16, 0.62), (0, 8.55, -16, 0.62)]
    for zc in (7.05, 5.60, 4.15, 2.70):
        j = rng.uniform(-0.08, 0.08)
        bands.append((rng.uniform(-0.15, 0.15), zc + j, 33 + rng.uniform(-2, 2), rng.uniform(0.92, 1.0)))
        bands.append((rng.uniform(-0.15, 0.15), zc + j + rng.uniform(-0.05, 0.05), -33 + rng.uniform(-2, 2), rng.uniform(0.92, 1.0)))
    bands.append((0, 1.30, 0, 0.55))
    for cx, cz, ang, w in bands:
        t = 0.30 if ang >= 0 else 0.38
        comps.append((band_round(cx, cz, ang, w, Y_S - 0.05, Y_S + emb, t - 0.05), TILE_BAND if ang >= 0 else TILE_OUTER))
    # recessed panel floor: a thin plate over the inner panel so the gaps between bands read as darker stone
    floor_raw = prism_bm(panel, Y_S + emb, Y_S - 0.05)
    floor_ob = obj_from_bm("lid_floor", floor_raw.copy())

    def relief_weight(e, bm_=None):
        if not e.is_convex:
            return 0.0
        try:
            if e.calc_face_angle() < math.radians(30):
                return 0.0
        except ValueError:
            return 0.0
        return 1.0 if any(f.normal.y < -0.5 for f in e.link_faces) else 0.0
    set_weights(floor_ob, relief_weight)
    bevel(floor_ob, 0.03, 1)
    boolean(slab, floor_ob, "UNION")
    remove_obj(floor_ob)
    # union all relief components
    cmat = bpy.data.collections.new("_relief_ops")
    bpy.context.scene.collection.children.link(cmat)
    objs = []
    for i, (bmc, tile) in enumerate(comps):
        objs.append(obj_from_bm(f"rel_{i}", bmc.copy(), coll=cmat))
    head = objs[0]
    # the target must not be inside the operand collection
    cmat.objects.unlink(head)
    scratch().objects.link(head)
    boolean(head, None, "UNION", collection_operand=cmat, use_self=True)
    open_edges_of(head, "relief union")
    # clip to the panel
    panel_bm = prism_bm(panel, Y_S - 1.0, Y_S + 1.0)
    pan = obj_from_bm("panel_clip", panel_bm)
    boolean(head, pan, "INTERSECT")
    open_edges_of(head, "relief clipped")
    bm = bm_from_obj(head)
    clean(bm)
    bm.to_mesh(head.data)
    bm.free()

    nrel = set_weights(head, relief_weight)
    log("lid: relief bevel edges", nrel)
    bevel(head, 0.06, 1)
    open_edges_of(head, "relief bevelled")
    open_edges_of(slab, "slab+floor before relief")
    # union with slab
    boolean(slab, head, "UNION")
    open_edges_of(slab, "slab+relief")
    bm = bm_from_obj(slab)
    clean(bm)
    ref_sources = [(slab_raw, TILE_OUTER, 1), (floor_raw, TILE_CAVITY, 1)] + [(c[0], c[1], 1) for c in comps]
    idx = SurfaceIndex(ref_sources)
    tiles = idx.classify(bm, tol=0.12, dotmin=0.3, default=TILE_OUTER, prefer_high=True)
    bm.to_mesh(slab.data)
    for c in comps:
        c[0].free()
    slab_raw.free()
    floor_raw.free()
    for o in objs[1:]:
        remove_obj(o)
    bpy.data.collections.remove(cmat)
    remove_obj(head)
    remove_obj(pan)
    return slab, bm, tiles


# ---------------------------------------------------------------------------------------------
# Broken kit
# ---------------------------------------------------------------------------------------------
CUT_BASE = [(-7.0, -1.0), (7.0, -1.0), (7.0, 3.0), (5.6, 2.6), (4.1, 3.4), (2.8, 2.45), (1.5, 3.5), (0.2, 2.7),
            (-1.1, 3.45), (-2.4, 2.5), (-3.7, 3.3), (-5.2, 2.65), (-7.0, 3.1)]
CUT_LEFT = [(-7.0, 3.95), (-5.0, 4.55), (-3.6, 3.9), (-2.2, 4.4), (-1.2, 4.0), (-1.6, 5.4), (-0.8, 6.5),
            (-1.7, 7.7), (-0.9, 8.8), (-1.6, 10.0), (-0.9, 11.5), (-7.0, 12.2)]
CUT_RIGHT = [(7.0, 4.6), (5.2, 4.2), (3.8, 4.9), (2.7, 4.4), (1.8, 5.3), (2.6, 6.3), (1.7, 7.4), (2.4, 8.5),
             (1.9, 9.9), (3.3, 9.6), (4.7, 10.3), (6.0, 9.7), (7.0, 10.2)]
CUT_LID = [(-7.0, 6.4), (-5.4, 6.9), (-4.2, 6.0), (-2.9, 7.1), (-1.6, 6.3), (-0.2, 7.2), (1.2, 6.5), (2.3, 7.6),
           (3.1, 8.7), (3.9, 9.6), (7.0, 9.8), (7.0, 12.5), (-7.0, 12.5)]


def make_chunk(name, src_bm, cutter_poly, y_rings, seed, ref_index, dropped_log):
    log("chunk", name)
    src = obj_from_bm(name + "_src", src_bm.copy())
    cut = obj_from_bm(name + "_cut", jagged_prism_bm(cutter_poly, y_rings, 0.40, seed))
    boolean(src, cut, "INTERSECT")
    remove_obj(cut)
    bm = bm_from_obj(src)
    clean(bm)
    ndrop, areas = keep_largest_island(bm)
    dropped_log[name] = {"dropped_islands": ndrop, "areas": areas}
    tiles = ref_index.classify(bm, tol=1e-3, dotmin=0.5, default=TILE_FRACT, prefer_high=False)
    lay = bm.faces.layers.int.new("tile")
    for f, t in zip(bm.faces, tiles):
        f[lay] = t
    bm.to_mesh(src.data)
    bm.free()

    def fract_weight(e, bm_=None):
        if not e.is_convex:
            return 0.0
        try:
            if e.calc_face_angle() < math.radians(35):
                return 0.0
        except ValueError:
            return 0.0
        lay_ = bm_.faces.layers.int.get("tile")
        return 1.0 if any(f[lay_] == TILE_FRACT for f in e.link_faces) else 0.0
    n = set_weights(src, fract_weight)
    log("  fracture bevel edges", n)
    bevel(src, 0.07, 1)
    bm = bm_from_obj(src)
    clean(bm, dissolve=False)
    ndrop2, _ = keep_largest_island(bm)
    tiles = ref_index.classify(bm, tol=1e-3, dotmin=0.5, default=TILE_FRACT, prefer_high=False)
    remove_obj(src)
    return bm, tiles


# =============================================================================================
# 3. VOLCANIC VENT
# =============================================================================================
def pol(r, th, z=0.0):
    return Vector((r * math.cos(th), r * math.sin(th), z))


def hull_bm(points):
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:], use_existing_faces=False)
    junk = res.get("geom_interior", []) + res.get("geom_unused", [])
    junk_v = list({g for g in junk if isinstance(g, bmesh.types.BMVert)})
    if junk_v:
        bmesh.ops.delete(bm, geom=junk_v, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    return bm


def bevel_bm(bm, width, min_angle_deg=38, segments=1):
    ob = obj_from_bm("tmp_bevel", bm)
    def fn(e, bm_=None):
        if not e.is_convex:
            return 0.0
        try:
            return 1.0 if e.calc_face_angle() > math.radians(min_angle_deg) else 0.0
        except ValueError:
            return 0.0
    set_weights(ob, fn)
    bevel(ob, width, segments)
    out = bm_from_obj(ob)
    remove_obj(ob)
    bmesh.ops.recalc_face_normals(out, faces=out.faces[:])
    out.normal_update()
    return out


def join_bms(bms):
    out = bmesh.new()
    for b in bms:
        me = bpy.data.meshes.new("tmp_join")
        b.to_mesh(me)
        out.from_mesh(me)
        bpy.data.meshes.remove(me)
        b.free()
    return out


def build_vent():
    log("vent")
    rng = random.Random(14)
    N = 9
    r_in = 1.75
    gap = 0.30
    cracks = [2 * math.pi * (j + rng.uniform(-0.22, 0.22)) / N for j in range(N)]
    heights = [1.50, 1.20, 0.92, 1.12, 1.62, 1.28, 0.88, 1.42, 1.02]
    depths = [1.9, 2.2, 1.55, 2.0, 2.3, 1.65, 1.5, 2.1, 1.8]
    rocks = []
    for i in range(N):
        a0 = cracks[i]
        a1 = cracks[(i + 1) % N] + (2 * math.pi if i == N - 1 else 0.0)
        th, half = (a0 + a1) / 2, (a1 - a0) / 2
        hw = lambda r: half - (gap / 2) / r
        ri = r_in + rng.uniform(0.0, 0.14)
        ro = ri + depths[i]
        rm = (ri + ro) / 2
        base_pts = [pol(ri, th - hw(ri)), pol(ri, th + hw(ri)),
                    pol(rm, th + hw(rm) - rng.uniform(0, 0.03)), pol(ro, th + hw(ro) * 0.92),
                    pol(ro + 0.14, th + rng.uniform(-0.03, 0.03)), pol(ro, th - hw(ro) * 0.92),
                    pol(rm, th - hw(rm) + rng.uniform(0, 0.03))]
        for p in base_pts:
            p.z = -0.12
        cen = sum((p for p in base_pts), Vector()) / len(base_pts)
        h = heights[i]
        lean = Vector((math.cos(th), math.sin(th), 0)) * rng.uniform(-0.12, 0.10)
        k = rng.uniform(0.62, 0.78)
        top_pts = []
        for p in base_pts:
            q = cen + (p - cen) * k + lean
            q.z = h + rng.uniform(-0.10, 0.07)
            top_pts.append(q)
        peak = cen + lean * 0.5 + Vector((rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), 0))
        peak.z = h + rng.uniform(0.07, 0.15)
        rocks.append(bevel_bm(hull_bm(base_pts + top_pts + [peak]), 0.085, 36))
    # crater floor stones (flat chunky slabs sitting on the lava pool)
    for (cx, cy, rr, hh, rot) in ((0.30, 0.20, 0.52, 0.26, 0.3), (-0.72, -0.48, 0.42, 0.20, 1.1), (0.52, -0.80, 0.36, 0.22, 2.0)):
        pts = []
        for k in range(6):
            a = rot + 2 * math.pi * k / 6
            rad = rr * rng.uniform(0.85, 1.05)
            pts.append(Vector((cx + rad * math.cos(a), cy + rad * math.sin(a), 0.02)))
        top = [Vector((cx + (p.x - cx) * 0.78, cy + (p.y - cy) * 0.78, hh + rng.uniform(-0.02, 0.03))) for p in pts]
        rocks.append(bevel_bm(hull_bm(pts + top), 0.04, 38))
    # second-row boulders overlapping the outside of the ring (break up the symmetry)
    for (j, rr, sz, hh) in ((1, 3.80, 0.70, 0.78), (3, 3.95, 0.62, 0.56), (4, 3.70, 0.78, 0.88),
                            (6, 3.90, 0.66, 0.50), (8, 3.75, 0.72, 0.70)):
        c = pol(rr, cracks[j] + rng.uniform(-0.08, 0.08))
        pts, top = [], []
        for q in range(6):
            a = 2 * math.pi * q / 6 + rng.uniform(0, 0.4)
            pts.append(Vector((c.x + sz * math.cos(a) * rng.uniform(0.8, 1.1), c.y + sz * math.sin(a) * rng.uniform(0.8, 1.1), -0.10)))
        for q in range(5):
            a = 2 * math.pi * q / 5 + rng.uniform(0, 0.5)
            top.append(Vector((c.x + sz * 0.55 * math.cos(a), c.y + sz * 0.55 * math.sin(a), hh + rng.uniform(-0.08, 0.08))))
        rocks.append(bevel_bm(hull_bm(pts + top), 0.05, 38))
    # small loose rocks around the base
    for k in range(16):
        a = 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / 16
        rr = rng.uniform(4.05, 4.6)
        sz = rng.uniform(0.24, 0.5)
        c = pol(rr, a)
        pts = []
        for _ in range(9):
            v = Vector((rng.gauss(0, 1), rng.gauss(0, 1), abs(rng.gauss(0, 0.6))))
            v.normalize()
            v *= sz * rng.uniform(0.7, 1.0)
            pts.append(Vector((c.x + v.x, c.y + v.y, max(-0.08, v.z * 0.85 - 0.02))))
        rocks.append(hull_bm(pts))
    rock_bm = join_bms(rocks)

    # glow: lava pool + seams that sit in the cracks between the ring rocks
    pb = bmesh.new()
    ring_lo = [pb.verts.new((1.85 * math.cos(2 * math.pi * k / 12), 1.85 * math.sin(2 * math.pi * k / 12), -0.06)) for k in range(12)]
    ring_hi = [pb.verts.new((1.85 * math.cos(2 * math.pi * k / 12), 1.85 * math.sin(2 * math.pi * k / 12), 0.05)) for k in range(12)]
    pb.faces.new(ring_lo)
    pb.faces.new(ring_hi)
    for k in range(12):
        j = (k + 1) % 12
        pb.faces.new((ring_lo[k], ring_lo[j], ring_hi[j], ring_hi[k]))
    bmesh.ops.recalc_face_normals(pb, faces=pb.faces[:])
    glow_parts = [pb]
    for i in range(N):
        phi = cracks[i]
        r0, r1 = 1.2, r_in + rng.uniform(1.6, 2.0)
        w0, w1 = 0.22, 0.13
        za, zb = rng.uniform(0.30, 0.42), rng.uniform(0.10, 0.18)
        d = Vector((math.cos(phi), math.sin(phi), 0))
        n = Vector((-d.y, d.x, 0))
        sb = bmesh.new()
        lo_z = Vector((0, 0, -0.06))
        bot = [sb.verts.new(d * r0 - n * w0 / 2 + lo_z), sb.verts.new(d * r0 + n * w0 / 2 + lo_z),
               sb.verts.new(d * r1 + n * w1 / 2 + lo_z), sb.verts.new(d * r1 - n * w1 / 2 + lo_z)]
        top = [sb.verts.new(d * r0 - n * w0 / 2 + Vector((0, 0, za))), sb.verts.new(d * r0 + n * w0 / 2 + Vector((0, 0, za))),
               sb.verts.new(d * r1 + n * w1 / 2 + Vector((0, 0, zb))), sb.verts.new(d * r1 - n * w1 / 2 + Vector((0, 0, zb)))]
        sb.faces.new(bot)
        sb.faces.new(top)
        for k in range(4):
            j = (k + 1) % 4
            sb.faces.new((bot[k], bot[j], top[j], top[k]))
        bmesh.ops.recalc_face_normals(sb, faces=sb.faces[:])
        glow_parts.append(sb)
    # union the glow parts through the boolean so the interior faces vanish
    cglow = bpy.data.collections.new("_glow_ops")
    bpy.context.scene.collection.children.link(cglow)
    gobjs = [obj_from_bm(f"glow_{k}", b, coll=(scratch() if k == 0 else cglow)) for k, b in enumerate(glow_parts)]
    boolean(gobjs[0], None, "UNION", collection_operand=cglow, use_self=True)
    glow_bm = bm_from_obj(gobjs[0])
    clean(glow_bm)
    for o in gobjs[1:]:
        remove_obj(o)
    remove_obj(gobjs[0])
    bpy.data.collections.remove(cglow)
    return rock_bm, glow_bm


def assign_uv_vent(rock_bm, glow_bm):
    uv_r = rock_bm.loops.layers.uv.verify()
    uv_g = glow_bm.loops.layers.uv.verify()
    gidx = SurfaceIndex([(glow_bm, V_LAVA, 1)])
    rock_bm.normal_update()
    glow_bm.normal_update()
    tris = {V_ROCK: 0, V_ROCKHOT: 0}
    for f in rock_bm.faces:
        c = f.calc_center_median()
        near = gidx.tree.find_nearest(c)
        hot = near is not None and near[3] < 0.42 and c.z < 1.35 and c.length < 4.0
        tile = V_ROCKHOT if hot else V_ROCK
        tris[tile] += 1
        ax = dominant_axis(f.normal)
        (x0, y0, x1, y1), s = VENT_TILES[tile]
        for l in f.loops:
            co = l.vert.co
            if tile == V_ROCK:
                a, b = planar_ab(co, ax)
                if ax != 2:
                    b = b + 4.0
                u = x0 + (a + 6.0) * s
                vup = (VENT_ATLAS - y1) + (b + 6.0 if ax == 2 else b + 0.2) * s
            else:
                a = co.x if ax != 0 else co.y
                u = x0 + (a + 6.0) * s
                vup = (VENT_ATLAS - y1) + (co.z + 0.05) * 90.0
            u = min(max(u, x0 + 2), x1 - 2)
            vup = min(max(vup, VENT_ATLAS - y1 + 2), VENT_ATLAS - y0 - 2)
            l[uv_r].uv = (u / VENT_ATLAS, vup / VENT_ATLAS)
    (x0, y0, x1, y1), s = VENT_TILES[V_LAVA]
    for f in glow_bm.faces:
        for l in f.loops:
            u = x0 + (l.vert.co.x + 5.0) * s
            vup = (VENT_ATLAS - y1) + (l.vert.co.y + 5.0) * s
            u = min(max(u, x0 + 2), x1 - 2)
            vup = min(max(vup, VENT_ATLAS - y1 + 2), VENT_ATLAS - y0 - 2)
            l[uv_g].uv = (u / VENT_ATLAS, vup / VENT_ATLAS)
    return tris


# =============================================================================================
# 4. VOLCANIC DEBRIS
# =============================================================================================
def debris_fragment(kind, rng):
    if kind == 1:        # spike / faceted shard: hex base, narrower shoulder ring, small tip facet
        pts = []
        for k in range(6):
            a = 0.3 + k * 2 * math.pi / 6
            pts.append(Vector((0.2 * math.cos(a) * rng.uniform(0.9, 1.08), 0.17 * math.sin(a) * rng.uniform(0.9, 1.08), 0.0)))
        for k in range(5):
            a = 0.9 + k * 2 * math.pi / 5
            pts.append(Vector((0.125 * math.cos(a) * rng.uniform(0.9, 1.1), 0.105 * math.sin(a) * rng.uniform(0.9, 1.1), 0.22 + rng.uniform(-0.02, 0.02))))
        for a in (0.2, 2.3, 4.4):
            pts.append(Vector((0.03 * math.cos(a) + 0.015, 0.03 * math.sin(a), 0.43 + rng.uniform(-0.015, 0.015))))
        return bevel_bm(hull_bm(pts), 0.012, 30), Vector((0.8, 0.5, 0.1)).normalized(), 0.0
    if kind == 2:        # chunky irregular blob
        pts = []
        for _ in range(15):
            v = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)))
            v.normalize()
            pts.append(Vector((v.x * 0.23, v.y * 0.19, v.z * 0.17)) * rng.uniform(0.82, 1.0))
        return bevel_bm(hull_bm(pts), 0.018, 30), Vector((-0.6, 0.6, 0.5)).normalized(), 0.0
    if kind == 3:        # lumpy ball (low-poly icosphere pushed around)
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.19)
        for v in bm.verts:
            v.co *= rng.uniform(0.86, 1.14)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        return bm, Vector((0.3, -0.5, 0.8)).normalized(), 0.0
    if kind == 4:        # chunky bar
        pts = []
        for x, r in ((-0.225, 0.062), (-0.145, 0.105), (0.145, 0.105), (0.225, 0.062)):
            for k in range(6):
                a = 2 * math.pi * k / 6 + 0.35
                pts.append(Vector((x + rng.uniform(-0.01, 0.01), r * math.cos(a) * rng.uniform(0.9, 1.05), r * math.sin(a) * rng.uniform(0.9, 1.05))))
        return hull_bm(pts), Vector((1.0, 0.1, 0.25)).normalized(), 0.0
    pts = []             # flat slab
    for k in range(6):
        a = 2 * math.pi * k / 6 + 0.2
        r = rng.uniform(0.9, 1.08)
        pts.append(Vector((0.24 * r * math.cos(a), 0.19 * r * math.sin(a), 0.0)))
    top = [Vector((p.x * 0.8 + rng.uniform(-0.01, 0.01), p.y * 0.8, 0.12 + rng.uniform(-0.01, 0.015))) for p in pts]
    return bevel_bm(hull_bm(pts + top), 0.014, 30), Vector((0.2, -1.0, 0.25)).normalized(), 0.0


def assign_uv_debris(bm, ember_dir, rng, dot_cut=0.84):
    uv = bm.loops.layers.uv.verify()
    bm.normal_update()
    lo, hi = volume_centroid_bbox(bm)
    c = (lo + hi) / 2
    ox, oy = rng.uniform(16, 150), rng.uniform(16, 150)
    n_ember = 0
    (rx0, ry0, rx1, ry1), _ = VENT_TILES[V_ROCK]
    (ex0, ey0, ex1, ey1), _ = VENT_TILES[V_EMBER]
    ember_idx = []
    for f in bm.faces:
        is_e = f.normal.dot(ember_dir) > dot_cut
        ember_idx.append(is_e)
        n_ember += is_e
    if n_ember == 0:
        best = max(bm.faces, key=lambda f: f.normal.dot(ember_dir))
        ember_idx = [f is best for f in bm.faces]
        n_ember = 1
    for f, is_e in zip(bm.faces, ember_idx):
        ax = dominant_axis(f.normal)
        for l in f.loops:
            a, b = planar_ab(l.vert.co - c, ax)
            if is_e:
                u = ex0 + 64 + a * 120.0
                vup = (VENT_ATLAS - ey1) + 64 + b * 120.0
                u = min(max(u, ex0 + 2), ex1 - 2)
                vup = min(max(vup, VENT_ATLAS - ey1 + 2), VENT_ATLAS - ey0 - 2)
            else:
                u = rx0 + ox + a * 180.0 + 90
                vup = (VENT_ATLAS - ry1) + oy + b * 180.0 + 90
                u = min(max(u, rx0 + 2), rx1 - 2)
                vup = min(max(vup, VENT_ATLAS - ry1 + 2), VENT_ATLAS - ry0 - 2)
            l[uv].uv = (u / VENT_ATLAS, vup / VENT_ATLAS)
    return n_ember


# =============================================================================================
# Export + manifest helpers
# =============================================================================================
def export_fbx(path, objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={"MESH"}, apply_unit_scale=True,
                             apply_scale_options="FBX_SCALE_NONE", axis_forward="-Z", axis_up="Y", path_mode="COPY",
                             embed_textures=True, add_leaf_bones=False, bake_anim=False, mesh_smooth_type="FACE",
                             use_triangles=True)


def bounds_of(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def r5(v):
    return [round(float(x), 5) for x in v]


def to_roblox(v):
    return [round(float(v[0]), 5), round(float(v[2]), 5), round(-float(v[1]), 5)]


def mesh_entry(ob):
    lo, hi = bounds_of(ob)
    return {"tris": tri_count(ob.data), "verts": len(ob.data.vertices),
            "boundsMinBlender": r5(lo), "boundsMaxBlender": r5(hi), "sizeBlender": r5(hi - lo),
            "originBlender": r5(ob.location), "originRoblox": to_roblox(ob.location)}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def is_sliver(f):
    """Near-degenerate triangle: tiny absolute area, or a hair-thin one (height < ~1e-4 of its longest edge)."""
    a = f.calc_area()
    return a < 1e-7 or a < 5e-5 * max(e.calc_length() for e in f.edges) ** 2


def tri_clean(bm, name=""):
    """Triangulate (beauty) and remove sliver triangles left by the booleans. Every repair step runs on a trial copy
    and is kept only if it does not open the mesh and does not add slivers. Returns the (possibly new) bmesh."""
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    n0 = sum(1 for f in bm.faces if is_sliver(f))

    def try_step(bm, fn):
        base_open, base_sl = manifold_report(bm), sum(1 for f in bm.faces if is_sliver(f))
        trial = bm.copy()
        fn(trial)
        bmesh.ops.recalc_face_normals(trial, faces=trial.faces[:])
        if manifold_report(trial) <= base_open and sum(1 for f in trial.faces if is_sliver(f)) < base_sl:
            bm.free()
            return trial
        trial.free()
        return bm

    def dissolve(t):
        bmesh.ops.dissolve_degenerate(t, dist=1e-4, edges=t.edges[:])
        bmesh.ops.triangulate(t, faces=t.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")

    def flip(t):
        t.faces.ensure_lookup_table()
        es = {max(f.edges, key=lambda e: e.calc_length()) for f in t.faces if is_sliver(f)}
        es = [e for e in es if len(e.link_faces) == 2]
        if es:
            bmesh.ops.rotate_edges(t, edges=es)

    def collapse(t):
        t.faces.ensure_lookup_table()
        es = list({min(f.edges, key=lambda e: e.calc_length()) for f in t.faces if is_sliver(f)})
        if es:
            bmesh.ops.collapse(t, edges=es, uvs=True)

    if n0:
        bm = try_step(bm, dissolve)
    for _ in range(4):
        if not any(is_sliver(f) for f in bm.faces):
            break
        bm = try_step(bm, flip)
    for _ in range(4):
        if not any(is_sliver(f) for f in bm.faces):
            break
        bm = try_step(bm, collapse)
    bm.normal_update()
    left = sum(1 for f in bm.faces if is_sliver(f))
    log("tri_clean", name, "slivers", n0, "->", left, "open edges", manifold_report(bm), "tris", len(bm.faces))
    return bm


def tri_clean_tiles(bm, tiles, name):
    """tri_clean a bmesh that carries per-face tiles (list); tiles are re-derived from the source surface."""
    new = tri_clean(bm.copy(), name)
    nt = SurfaceIndex([(bm, tiles, 1)]).classify(new, tol=0.09, dotmin=0.5, default=TILE_OUTER, prefer_high=False)
    bm.free()
    return new, nt


def finalize_object(name, bm, mat, location=(0, 0, 0), recenter=None):
    """Turn a world-space bm into the exported object. recenter = world point that becomes the object origin."""
    if recenter is not None:
        bmesh.ops.translate(bm, verts=bm.verts[:], vec=-Vector(recenter))
        location = tuple(recenter)
    bm = tri_clean(bm, name)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    collection("Round10").objects.link(ob)
    finish_mesh(ob, mat)
    return ob


# =============================================================================================
# BUILD
# =============================================================================================
def build():
    for d in (EXPORTS, TEXTURES, PREVIEWS):
        d.mkdir(exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    collection("Round10")

    log("painting atlases")
    sar_png = TEXTURES / "Sarcophagus_atlas.png"
    vol_png = TEXTURES / "Volcanic_atlas.png"
    write_png(sar_png, paint_coffin_atlas())
    write_png(vol_png, paint_vent_atlas())
    for p in (sar_png, vol_png):
        shutil.copy2(p, EXPORTS / p.name)
    mat_sar = atlas_material("SarcophagusAtlas", sar_png)
    mat_vol = atlas_material("VolcanicAtlas", vol_png)

    manifest = {"generator": "round10-props/build_round10_props.py", "blender": bpy.app.version_string,
                "units": "studs, template scale 1, import 1:1",
                "axes": {"blender": "+Z up, coffin open face toward -Y", "fbx": "axis_forward -Z, axis_up Y",
                         "roblox": "Blender (x, y, z) -> Roblox (x, z, -y); Blender -Y front == Roblox -Z front"},
                "referenceSheetsSha256": {p.name: sha256(p) for p in sorted(REFS.glob("*.png"))
                                          if p.name[:2] in ("03", "06", "07", "08", "09", "10")},
                "atlases": {"Sarcophagus_atlas.png": CO_ATLAS, "Volcanic_atlas.png": VENT_ATLAS}, "assets": {}}

    # ----- coffin body + lid -----
    outer, base, inner, panel = outline_polys()
    body_ob, body_bm, body_tiles = build_body(outer, inner)
    lid_ob, lid_bm, lid_tiles = build_lid(outer, inner, panel)
    # final intact meshes: triangulated + sliver-free; the broken kit is derived from exactly these
    body_bm, body_tiles = tri_clean_tiles(body_bm, body_tiles, "intact body")
    lid_bm, lid_tiles = tri_clean_tiles(lid_bm, lid_tiles, "intact lid")
    body_bm2 = body_bm.copy()
    lid_bm2 = lid_bm.copy()
    log("manifold body/lid", manifold_report(body_bm), manifold_report(lid_bm))
    ref_index = SurfaceIndex([(body_bm2, body_tiles, 1), (lid_bm2, lid_tiles, 1)])
    # intact meshes: UVs, then export objects
    assign_uv_coffin(body_bm, body_tiles)
    assign_uv_coffin(lid_bm, lid_tiles)
    y_hinge = min(v.co.y for v in lid_bm.verts)
    body = finalize_object("Sarcophagus_Body", body_bm.copy(), mat_sar)
    lid = finalize_object("Sarcophagus_Lid", lid_bm.copy(), mat_sar, recenter=(0.0, y_hinge, 0.0))
    manifest["assets"]["Sarcophagus.fbx"] = {
        "meshes": {"Sarcophagus_Body": mesh_entry(body), "Sarcophagus_Lid": mesh_entry(lid)},
        "revision": "2026-10-09 fix pass: taller anthropoid silhouette (11 tall), soft painterly texture, rounded bandage relief",
        "frame": "Body origin = floor centre of the cavity footprint at ground level; both meshes are placed closed "
                 "(identity transform of the FBX = assembled coffin).",
        "cavity": {"frontPlaneY": Y_F, "backInnerY": Y_CB, "floorZ": FLOOR, "ceilingZ": OUT_H - CEIL,
                   "depth": Y_CB - Y_F, "maxWidth": 2 * max(x for x, z in inner),
                   "height": OUT_H - FLOOR - CEIL, "box9_4x6_2x4_2": "extents check, see validation-report.json"},
        "lid": {"hingeLineBodySpaceBlender": r5((0, y_hinge, 0)), "hingeLineBodySpaceRoblox": to_roblox((0, y_hinge, 0)),
                "hingeAxis": "X (through the bottom front edge of the lid, z = 0)",
                "fallsForward": "rotate about +X by +90 deg in Blender (top moves toward -Y); relief face ends face-down, "
                                "underside up, lid resting on the ground",
                "closedFit": "underside plane y = %.3f == body front rim plane (gap 0, overlap 0)" % Y_F,
                "slabThickness": T_SLAB, "reliefDepthMax": round(Y_S - y_hinge, 3)},
    }

    # ----- broken kit -----
    dropped = {}
    chunks = {}
    for nm, cutter, src, rings, seed in (
        ("SarcophagusBroken_Base", CUT_BASE, body_bm2, [-3.8, -2.0, 0.0, 1.8, 3.8], 301),
        ("SarcophagusBroken_LeftWall", CUT_LEFT, body_bm2, [-3.8, -2.0, 0.0, 1.8, 3.8], 302),
        ("SarcophagusBroken_RightWall", CUT_RIGHT, body_bm2, [-3.8, -2.0, 0.0, 1.8, 3.8], 303),
        ("SarcophagusBroken_LidFragment", CUT_LID, lid_bm2, [-4.2, -3.3, -2.7, -1.8], 304),
    ):
        cbm, ctiles = make_chunk(nm, src, cutter, rings, seed, ref_index, dropped)
        assign_uv_coffin(cbm, ctiles)
        lo, hi = volume_centroid_bbox(cbm)
        chunks[nm] = (cbm, (lo + hi) / 2)
    broken_objs = []
    offsets = {}
    for nm, (cbm, cen) in chunks.items():
        ob = finalize_object(nm, cbm, mat_sar, recenter=cen)
        broken_objs.append(ob)
        offsets[nm] = {"offsetBodySpaceBlender": r5(cen), "offsetBodySpaceRoblox": to_roblox(cen)}
    manifest["assets"]["SarcophagusBroken.fbx"] = {
        "meshes": {o.name: dict(mesh_entry(o), **offsets[o.name]) for o in broken_objs},
        "frame": "Each mesh origin = its bounding-box centre; the object location in the FBX is that centre expressed in "
                 "the intact coffin's body-origin frame, so importing the FBX with an identity transform at the coffin "
                 "body origin reproduces the intact positions (the missing centre-back is the dust that was removed).",
        "fractureLog": dropped}
    (EXPORTS / "SarcophagusBroken-offsets.json").write_text(json.dumps(
        {"frame": "coffin body origin (Blender: +Z up, open face -Y; Roblox: x, z, -y)", "chunks": offsets}, indent=2))

    # ----- vent -----
    rock_bm, glow_bm = build_vent()
    log("manifold vent rock/glow", manifold_report(rock_bm), manifold_report(glow_bm))
    vent_tiles = assign_uv_vent(rock_bm, glow_bm)
    vrock = finalize_object("Vent_Rock", rock_bm, mat_vol)
    vglow = finalize_object("Vent_Glow", glow_bm, mat_vol)
    lo, hi = bounds_of(vrock)
    manifest["assets"]["VolcanicVent.fbx"] = {
        "meshes": {"Vent_Rock": mesh_entry(vrock), "Vent_Glow": mesh_entry(vglow)},
        "frame": "Origin = ground centre of the opening (0,0,0). Vent_Glow is the lava (Neon in Studio), Vent_Rock the basalt.",
        "heightMax": round(max(bounds_of(vrock)[1].z, bounds_of(vglow)[1].z), 4),
        "acrossX": round(hi.x - lo.x, 3), "acrossY": round(hi.y - lo.y, 3), "openingDiameterDesign": 2 * 1.75,
        "uvFaceSplit": vent_tiles}

    # ----- debris -----
    rng = random.Random(77)
    deb_objs = []
    for k in range(1, 6):
        bm, edir, _ = debris_fragment(k, rng)
        clean(bm, dissolve=False)
        n_e = assign_uv_debris(bm, edir, random.Random(500 + k))
        lo, hi = volume_centroid_bbox(bm)
        cen = (lo + hi) / 2
        ob = finalize_object(f"Debris_{k}", bm, mat_vol, recenter=cen)
        ob.location = ((k - 3) * 0.9, 0.0, 0.0)          # layout row only; every origin is the fragment's own centre
        deb_objs.append(ob)
    manifest["assets"]["VolcanicDebris.fbx"] = {
        "meshes": {o.name: mesh_entry(o) for o in deb_objs},
        "frame": "Five separate fragments, origin = each fragment's bounding-box centre; object locations are only a layout row."}

    # ----- export -----
    export_fbx(EXPORTS / "Sarcophagus.fbx", [body, lid])
    export_fbx(EXPORTS / "SarcophagusBroken.fbx", broken_objs)
    export_fbx(EXPORTS / "VolcanicVent.fbx", [vrock, vglow])
    export_fbx(EXPORTS / "VolcanicDebris.fbx", deb_objs)
    (EXPORTS / "props-manifest.json").write_text(json.dumps(manifest, indent=2))
    (ROOT / "props-manifest.json").write_text(json.dumps(manifest, indent=2))

    # ----- source .blend (laid out for viewing; export already done) -----
    for o in broken_objs:
        o.location.x += 16
    for o in (vrock, vglow):
        o.location.x += 34
    for o in deb_objs:
        o.location.x += 46
        o.location.y += 0
    for name in ("_scratch",):
        c = bpy.data.collections.get(name)
        if c:
            for o in list(c.objects):
                remove_obj(o)
            bpy.data.collections.remove(c)
    for im in bpy.data.images:
        if im.source == "FILE":
            im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "round10-props.blend"))
    for fbx, data in manifest["assets"].items():
        log(fbx, {n: m["tris"] for n, m in data["meshes"].items()})
    log("BUILD_DONE")


# =============================================================================================
# RENDER (previews from the exported FBX files, EEVEE, <= 1024 px)
# =============================================================================================
def read_png_rgb(path):
    img = bpy.data.images.load(str(path), check_existing=False)
    w, h = img.size
    arr = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1, :, :3]
    bpy.data.images.remove(img)
    return (np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)


def fresh_render_scene(world=(0.70, 0.80, 0.95), floor=(0.30, 0.31, 0.32), floor_size=80):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    try:
        scene.eevee.taa_render_samples = 48
    except Exception:
        pass
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "PNG"
    w = bpy.data.worlds.new("sky")
    scene.world = w
    try:
        w.use_nodes = True
    except Exception:
        pass
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*world, 1)
    bg.inputs["Strength"].default_value = 0.40
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 2.1
    sun.angle = math.radians(14)
    sun.color = (1.0, 0.96, 0.88)
    so = bpy.data.objects.new("sun", sun)
    scene.collection.objects.link(so)
    so.rotation_euler = (math.radians(50), 0, math.radians(-36))
    fill = bpy.data.lights.new("fill", "SUN")
    fill.energy = 0.55
    fill.color = (0.85, 0.9, 1.0)
    fo = bpy.data.objects.new("fill", fill)
    scene.collection.objects.link(fo)
    fo.rotation_euler = (math.radians(58), 0, math.radians(142))
    bm = bmesh.new()
    s = floor_size
    vs = [bm.verts.new(p) for p in ((-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0))]
    bm.faces.new(vs)
    fl = obj_from_bm("floor", bm, coll=scene.collection)
    fm = bpy.data.materials.new("floor")
    try:
        fm.use_nodes = True
    except Exception:
        pass
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*floor, 1)
    fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
    fl.data.materials.append(fm)
    cam_d = bpy.data.cameras.new("cam")
    cam_d.lens = 50
    cam = bpy.data.objects.new("cam", cam_d)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene, cam


def import_props(fbx, atlas_png):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(EXPORTS / fbx))
    objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    mat = atlas_material("prev_" + fbx, TEXTURES / atlas_png)
    glow = atlas_material("prev_glow_" + fbx, TEXTURES / atlas_png, emission=0.85)
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(glow if o.name.startswith("Vent_Glow") else mat)
    return {o.name.split(".")[0]: o for o in objs}


def aim(cam, target, az, el, radius, aspect=1.0, lens=50.0, margin=1.12):
    half = math.atan(18.0 / lens)
    if aspect < 1:
        half = math.atan(math.tan(half) * aspect)
    dist = radius / math.sin(half) * margin if False else radius / math.tan(half) * margin
    a, e = math.radians(az), math.radians(el)
    cam.location = Vector(target) + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()


def shoot(scene, cam, out, res, target, az, el, radius):
    scene.render.resolution_x, scene.render.resolution_y = res
    aim(cam, target, az, el, radius, aspect=res[0] / res[1] if res[0] < res[1] else 1.0)
    scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    return read_png_rgb(out)


def sheet(path, rows):
    rows = [np.concatenate(r, axis=1) for r in rows]
    write_png(path, np.concatenate(rows, axis=0))


def render_all():
    PREVIEWS.mkdir(exist_ok=True)
    tmp = PREVIEWS / "_tmp.png"
    want = lambda n: not ONLY or n in ONLY
    if want("sarcophagus"):          # front 3/4, side, back (lid closed) + lid fallen forward
        sc, cam = fresh_render_scene()
        o = import_props("Sarcophagus.fbx", "Sarcophagus_atlas.png")
        T = (0, -0.7, 5.6)
        p1 = shoot(sc, cam, tmp, (512, 512), T, 34, 13, 7.5)
        p2 = shoot(sc, cam, tmp, (512, 512), T, 90, 6, 7.5)
        p3 = shoot(sc, cam, tmp, (512, 512), T, 180, 12, 7.5)
        o["Sarcophagus_Lid"].rotation_euler = (math.radians(90), 0, 0)
        p4 = shoot(sc, cam, tmp, (512, 512), (0, -5.0, 4.0), 24, 30, 11.2)
        sheet(PREVIEWS / "Sarcophagus.png", [[p1, p2], [p3, p4]])
    if want("broken"):               # pieces in place (identity transform) and exploded
        sc, cam = fresh_render_scene()
        o = import_props("SarcophagusBroken.fbx", "Sarcophagus_atlas.png")
        q1 = shoot(sc, cam, tmp, (512, 512), (0, -0.4, 5.6), 30, 14, 7.5)
        push = {"SarcophagusBroken_Base": (0, -0.6, -0.3), "SarcophagusBroken_LeftWall": (-4.0, 0.0, 0.0),
                "SarcophagusBroken_RightWall": (4.2, 0.0, 0.5), "SarcophagusBroken_LidFragment": (0.0, -0.8, 2.3)}
        for n, d in push.items():
            o[n].location = o[n].location + Vector(d)
        q2 = shoot(sc, cam, tmp, (512, 512), (0, -0.8, 5.9), 20, 15, 9.8)
        sheet(PREVIEWS / "Broken.png", [[q1, q2]])
    if want("vent"):
        sc, cam = fresh_render_scene(floor=(0.30, 0.29, 0.28))
        o = import_props("VolcanicVent.fbx", "Volcanic_atlas.png")
        v1 = shoot(sc, cam, tmp, (512, 512), (0, 0, 0.5), 28, 36, 5.0)
        v2 = shoot(sc, cam, tmp, (512, 512), (0, 0, 0.6), 90, 7, 5.0)
        sheet(PREVIEWS / "Vent.png", [[v1, v2]])
    if want("debris"):
        sc, cam = fresh_render_scene(floor=(0.30, 0.29, 0.28))
        o = import_props("VolcanicDebris.fbx", "Volcanic_atlas.png")
        for ob in o.values():
            ob.location.z = ob.dimensions.z / 2
        d1 = shoot(sc, cam, tmp, (1024, 400), (0, 0, 0.12), 16, 26, 2.0)
        sheet(PREVIEWS / "Debris.png", [[d1]])
    tmp.unlink(missing_ok=True)
    log("RENDER_DONE")


if MODE == "build":
    build()
else:
    render_all()
