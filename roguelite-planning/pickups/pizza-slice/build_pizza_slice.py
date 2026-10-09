"""Chef pizza-slice pickup: builds the whole asset from scratch (self-contained).

Run (repo root, PowerShell):
  & "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --threads 4 --python roguelite-planning/pickups/pizza-slice/build_pizza_slice.py

Optional args after `--`:  --out <dir>  write everything to another folder (scratch tests)
                           --quick      one small low-sample hero render, no exports

Geometry notes
  * Blender is Z-up. The slice lies flat on Z=0, TIP toward +Y, CRUST toward -Y, top toward +Z.
    FBX/GLB export converts to Y-up with the tip toward -Z (Roblox "front").
  * Origin = area centroid of the slice's flat bottom footprint, on the ground plane (Z=0).
  * Bread, cheese, crust and all four cheese drips are ONE closed surface: a loft of rings around
    the slice outline. Drips are smooth bulges of the same sheet (no separate blobs, no seams).
  * The three pepperoni are closed bevelled discs sunk into the cheese (intentional overlap).
  * The shape is designed at ~2.1 long, then scaled uniformly by SCALE so the finished heights land at
    ~0.47 studs (bread + cheese) and ~0.77 studs (crust crest), 1 unit = 1 stud.
"""
import bpy, bmesh, math, json, random, shutil, hashlib, sys
import numpy as np
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ARGV = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK = "--quick" in ARGV
OUT = Path(ARGV[ARGV.index("--out") + 1]) if "--out" in ARGV else Path(__file__).resolve().parent
REF_SRC = Path(__file__).resolve().parents[2] / "weapon-models" / "concepts" / "chef-2026-10-09" / "optional-chef-pickup-concept.png"
OUT.mkdir(parents=True, exist_ok=True)
TEX = 512
SCALE = 1.9     # uniform scale applied to the finished mesh (design size x SCALE = delivered size)
RNG = random.Random(20261009)


# ---------------------------------------------------------------- small helpers
def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


def lerpc(a, b, t):
    return tuple(lerp(x, y, t) for x, y in zip(a, b))


def rgb(r, g, b):
    return (r / 255.0, g / 255.0, b / 255.0)  # authored directly in sRGB


# Palette: bright and saturated on purpose (the game adds +0.3 saturation).
CHEESE = rgb(250, 184, 36)
CHEESE_HI = rgb(255, 210, 72)
CHEESE_LO = rgb(240, 154, 30)
CHEESE_DEEP = rgb(222, 138, 28)
LIP = rgb(248, 176, 34)
CHEESE_BROWN = rgb(226, 134, 30)
CRUST_HI = rgb(232, 176, 98)
CRUST = rgb(206, 140, 62)
CRUST_MID = rgb(190, 122, 52)
CRUST_LO = rgb(160, 98, 44)
CRUST_DEEP = rgb(134, 80, 36)
BREAD = rgb(234, 192, 124)
BREAD_LO = rgb(208, 152, 84)
GROOVE = rgb(186, 126, 62)
BOTTOM = rgb(216, 154, 82)
BOTTOM_HI = rgb(230, 178, 106)
BOTTOM_EDGE = rgb(178, 118, 60)
PEP = rgb(198, 52, 42)
PEP_HI = rgb(216, 72, 56)
PEP_RIM = rgb(142, 34, 34)
PEP_SIDE = rgb(122, 28, 30)
FLECK = rgb(226, 104, 74)

# ---------------------------------------------------------------- shape parameters
ALPHA = math.radians(21.0)          # half angle of the wedge
SA, CA = math.sin(ALPHA), math.cos(ALPHA)
RB = 2.05                           # apex -> back arc radius
RT = 0.065                          # tip fillet radius
RC = 0.13                           # back corner fillet radius
R_TIP = RT / math.tan(ALPHA)        # side distance of the tip tangent point
A_END = math.sqrt((RB - RC) ** 2 - RC ** 2)   # side distance of the back-corner tangent point
MAXGAP = 0.24                       # max perimeter spacing outside the drip zones

# (side, centre r, half width, bottom z, front offset) - r is distance from the wedge apex along the side.
# Drips hang DOWN the bread wall: their front face sits `front offset` out from the outline (only just proud of
# the cheese lip above it), so from above the outline stays a clean triangle with slight soft bulges.
DRIPS = [
    ("R", 0.58, 0.115, 0.078, 0.056),   # short
    ("R", 1.20, 0.130, 0.012, 0.062),   # long
    ("L", 0.88, 0.120, 0.016, 0.060),   # long
    ("L", 1.38, 0.100, 0.052, 0.054),   # medium
]
DRIP_TOP = 0.205
DRIP_KT, DRIP_KS = 2.3, 4.5   # lateral roundness, vertical squareness (long flat run, then a rounded teardrop end)
DRIP_EXP = 0.55
RING_F = [0.0, 0.65, 0.92, 1.0, 1.0, 1.0, 0.95, 0.70, 0.0]   # how much of the drip front each ring takes

# Ring profiles around the outline, top to bottom: (outward offset d, height z)
BASE = [(-0.015, 0.222), (0.025, 0.210), (0.042, 0.186), (0.034, 0.156), (0.012, 0.124),
        (0.012, 0.092), (0.008, 0.058), (-0.008, 0.020), (-0.040, 0.000)]
# Puffy crust roll: P0 inner shoulder, P1 crest, P2 outer shoulder, P3 belly (widest, overhangs the sides)
CRUSTP = [(-0.075, 0.300), (0.010, 0.392), (0.100, 0.342), (0.150, 0.232), (0.130, 0.136),
          (0.085, 0.086), (0.045, 0.050), (0.005, 0.020), (-0.040, 0.000)]
BASE_COL = [CHEESE, CHEESE_HI, LIP, CHEESE_LO, GROOVE, BREAD_LO, BREAD, BREAD, BOTTOM_EDGE]
CRUST_COL = [CRUST, CRUST_HI, lerpc(CRUST_HI, CRUST, 0.5), CRUST_MID, CRUST_MID, CRUST_LO, CRUST_LO, CRUST_DEEP, CRUST_DEEP]
BASE_ZONE = [(1, 0, 0, 0)] * 4 + [(0.3, 0, 0.7, 0)] + [(0, 0, 1, 0)] * 4
DOME = 0.020
# broad soft rises (+) and dips (-) on the cheese: (x, y, height, sigma) in outline coordinates
HILLS = [(-0.20, -1.55, 0.026, 0.30), (0.22, -1.12, 0.024, 0.28), (-0.16, -0.66, 0.022, 0.26),
         (0.10, -0.30, 0.016, 0.20), (0.00, -1.32, -0.014, 0.20), (-0.22, -1.05, -0.010, 0.18)]
FACET_FLAT = 0.75    # how much each triangle keeps one flat colour (low-poly facet look)
F1, F2, FB = 0.64, 0.30, 0.55       # top ring fractions toward the centre; bottom ring fraction

# three pepperoni: (lateral x, distance from apex along the axis, radius)
PEPPERONI = [(0.15, 1.50, 0.205), (-0.14, 1.06, 0.195), (0.04, 0.64, 0.150)]


# ---------------------------------------------------------------- outline
def build_outline():
    """Closed CCW outline (tip first). Returns lists of points, normals, side, r, crust weight."""
    apex = np.array([0.0, 0.0])
    dirR, nR = np.array([SA, -CA]), np.array([CA, SA])
    dirL, nL = np.array([-SA, -CA]), np.array([-CA, SA])

    def side_rs(side):
        must = {round(R_TIP, 5), round(A_END, 5)}
        for sd, rc, w, zb, p in DRIPS:
            if sd == side:
                for k in (-2, -1, 0, 1, 2):
                    must.add(round(rc + k * w / 2, 5))
        rs = sorted(must)
        out = [rs[0]]
        for a, b in zip(rs[:-1], rs[1:]):
            n = int(math.ceil((b - a) / MAXGAP - 1e-9))
            for j in range(1, n):
                out.append(a + (b - a) * j / n)
            out.append(b)
        return out

    def side_xy(side, r):
        d, n = (dirR, nR) if side == "R" else (dirL, nL)
        env = math.sin(math.pi * (r - R_TIP) / (A_END - R_TIP))
        ph = 0.6 if side == "R" else 2.1
        off = 0.016 * env + 0.010 * math.sqrt(max(env, 0)) * math.sin(2 * math.pi * r / 0.85 + ph)
        return apex + r * d + off * n

    pts = []   # (xy, side, r, c)

    def crust_c(r):
        return smooth((r - 1.45) / 0.47)

    tip_c = np.array([0.0, -RT / SA])
    pts.append((tip_c + np.array([0.0, RT]), None, R_TIP - 0.08, 0.0))
    for r in side_rs("L"):
        pts.append((side_xy("L", r), "L", r, crust_c(r)))

    # back corner fillet (right), circle tangent to the right side and to the back arc
    cc = apex + A_END * dirR - RC * nR
    th0 = math.atan2(nR[1], nR[0])
    e = cc / np.linalg.norm(cc)
    th1 = math.atan2(e[1], e[0])
    right_arc = [cc + RC * np.array([math.cos(t), math.sin(t)])
                 for t in (lerp(th1, th0, k / 3.0) for k in (1, 2))]       # back -> side order
    for p in [np.array([-q[0], q[1]]) for q in reversed(right_arc)]:      # left corner, side -> back
        pts.append((p, None, A_END, 1.0))
    phi_e = math.atan2(cc[0], -cc[1])
    for k in range(7):
        phi = lerp(-phi_e, phi_e, k / 6.0)
        rad = RB + 0.008 * math.sin(k * 1.7 + 0.5) * (0 if k in (0, 6) else 1)
        pts.append((apex + rad * np.array([math.sin(phi), -math.cos(phi)]), None, A_END, 1.0))
    for p in right_arc:
        pts.append((p, None, A_END, 1.0))
    for r in reversed(side_rs("R")):
        pts.append((side_xy("R", r), "R", r, crust_c(r)))

    xy = np.array([p[0] for p in pts])
    n = len(pts)
    area = 0.5 * sum(xy[i][0] * xy[(i + 1) % n][1] - xy[(i + 1) % n][0] * xy[i][1] for i in range(n))
    assert area > 0, "outline must be CCW"
    normals = []
    for i in range(n):
        def en(a, b):
            d = xy[b] - xy[a]
            v = np.array([d[1], -d[0]])
            return v / np.linalg.norm(v)
        v = en((i - 1) % n, i) + en(i, (i + 1) % n)
        normals.append(v / np.linalg.norm(v))
    return xy, np.array(normals), [p[1] for p in pts], [p[2] for p in pts], [p[3] for p in pts]


def smax(a, b, k=0.006):
    return 0.5 * (a + b + math.sqrt((a - b) ** 2 + k * k))


def drip_front(side, r, z, k):
    """Outline offset of a drip's front face at this wall point (0 if no drip) and its 0..1 weight."""
    best, bestq = 0.0, 0.0
    for sd, rc, w, zb, dt in DRIPS:
        if sd != side:
            continue
        s = max(0.0, (DRIP_TOP - z) / (DRIP_TOP - zb))
        t = (r - rc) / (w * (1 - 0.18 * min(s, 1.0)))
        if abs(t) >= 1:
            continue
        base = 1 - abs(t) ** DRIP_KT - s ** DRIP_KS
        if base <= 0:
            continue
        q = base ** DRIP_EXP
        if dt * RING_F[k] * q > best:
            best, bestq = dt * RING_F[k] * q, q
    return best, bestq


def hill(p):
    """Broad soft rises/dips of the cheese top."""
    return sum(h * math.exp(-((p[0] - x) ** 2 + (p[1] - y) ** 2) / (2 * sg * sg)) for x, y, h, sg in HILLS)


# ---------------------------------------------------------------- mesh assembly
class MeshData:
    def __init__(self):
        self.v, self.tri, self.col, self.zone = [], [], [], []

    def vert(self, x, y, z):
        self.v.append((float(x), float(y), float(z)))
        return len(self.v) - 1

    def tri_add(self, ids, cols, zones, tone=1.0, flat=FACET_FLAT):
        self.tri.append(tuple(ids))
        if flat:
            mean = tuple(sum(c[k] for c in cols) / len(cols) for k in range(3))
            cols = [lerpc(c, mean, flat) for c in cols]
        self.col.append(tuple(tuple(min(1.0, c * tone) for c in col) for col in cols))
        self.zone.append(tuple(zones))

    def quad(self, ids, cols, zones, flat=FACET_FLAT):
        a, b, c, d = ids
        pa, pb, pc, pd = (np.array(self.v[i]) for i in ids)
        tone = 1.0 + RNG.uniform(-0.03, 0.03)
        mean = tuple(sum(c[k] for c in cols) / 4.0 for k in range(3))   # one flat colour per quad
        cols = [lerpc(c, mean, flat) for c in cols]
        if np.linalg.norm(pa - pc) <= np.linalg.norm(pb - pd):
            self.tri_add((a, b, c), (cols[0], cols[1], cols[2]), (zones[0], zones[1], zones[2]), tone, 0.0)
            self.tri_add((a, c, d), (cols[0], cols[2], cols[3]), (zones[0], zones[2], zones[3]), tone, 0.0)
        else:
            self.tri_add((a, b, d), (cols[0], cols[1], cols[3]), (zones[0], zones[1], zones[3]), tone, 0.0)
            self.tri_add((b, c, d), (cols[1], cols[2], cols[3]), (zones[1], zones[2], zones[3]), tone, 0.0)


def build_slice(M):
    xy, nrm, side, rr, cc = build_outline()
    N = len(xy)
    crust_w = [smooth((c - 0.25) / 0.5) for c in cc]      # sharpened crust weight for colour
    tip_scale = []
    for i in range(N):
        rtip = rr[i] if side[i] else (R_TIP - 0.08 if i == 0 else A_END)
        tip_scale.append(0.3 + 0.7 * smooth((rtip - R_TIP) / 0.5) if (side[i] or i == 0) else 1.0)

    inward_cap = []        # keep inward offsets inside the local radius of curvature (no folded corners)
    for i in range(N):
        a_, b_ = xy[i] - xy[i - 1], xy[(i + 1) % N] - xy[i]
        ang = abs(math.atan2(a_[0] * b_[1] - a_[1] * b_[0], float(a_ @ b_)))
        L = 0.5 * (np.linalg.norm(a_) + np.linalg.norm(b_))
        inward_cap.append(0.6 * (L / ang if ang > 1e-3 else 9.0))

    P = [[None] * N for _ in range(9)]           # ring vertex ids
    Pxy = [[None] * N for _ in range(9)]
    ring_col = [[None] * N for _ in range(9)]
    ring_zone = [[None] * N for _ in range(9)]
    for i in range(N):
        cs = cc[i]
        for k in range(9):
            d = lerp(BASE[k][0], CRUSTP[k][0], cs)
            z = lerp(BASE[k][1], CRUSTP[k][1], cs)
            nb = 0.0
            if 1 <= k <= 7 and side[i]:
                front, nb = drip_front(side[i], rr[i], z, k)
                if front > 0:
                    d = smax(d, front)
            if d < 0:
                d = -min(-d * tip_scale[i], inward_cap[i])
            if k <= 3:        # softly faceted lip / crust roll
                d += RNG.uniform(-0.004, 0.004) + RNG.uniform(-0.007, 0.007) * cs
                z += RNG.uniform(-0.003, 0.003) * (k > 0) + RNG.uniform(-0.005, 0.005) * cs
            elif k <= 7:      # bread wall stays clean (no banding)
                d += RNG.uniform(-0.002, 0.002)
            p2 = xy[i] + nrm[i] * d
            Pxy[k][i] = p2
            P[k][i] = M.vert(p2[0], p2[1], z)
            # colour + zone weights
            col = lerpc(BASE_COL[k], CRUST_COL[k], crust_w[i])
            zn = np.array(lerpc(BASE_ZONE[k], (0, 1, 0, 0), crust_w[i]))
            if k == 0:
                col = lerpc(lerpc(CHEESE, CHEESE_LO, 0.3), CRUST_COL[0], crust_w[i])
            if 1 <= k <= 7 and nb > 0:
                nu = smooth(nb / 0.35)
                dcol = lerpc(LIP, CHEESE_HI, smooth(nb) * 0.8)
                col = lerpc(col, dcol, nu)
                zn = np.array(lerpc(tuple(zn), (1, 0, 0, 0), nu))
            ring_col[k][i] = col
            ring_zone[k][i] = tuple(zn)

    # top surface centre = area centroid of the P0 ring outline
    pol = np.array(Pxy[0])
    a2 = pol[:, 0] * np.roll(pol[:, 1], -1) - np.roll(pol[:, 0], -1) * pol[:, 1]
    cx = ((pol[:, 0] + np.roll(pol[:, 0], -1)) * a2).sum() / (3 * a2.sum())
    cy = ((pol[:, 1] + np.roll(pol[:, 1], -1)) * a2).sum() / (3 * a2.sum())
    Cxy = np.array([cx, cy])
    ZT = BASE[0][1]

    def top_cheese(f, h=0.0):
        """Cheese value ranges: lighter on the rises, deeper orange in the dips and toward the rim."""
        c = lerpc(CHEESE, CHEESE_HI, 0.30 * (1 - f))
        if h > 0:
            c = lerpc(c, CHEESE_HI, 0.85 * smooth(h / 0.030))
        else:
            c = lerpc(c, LIP, 0.85 * smooth(-h / 0.014))
        return lerpc(c, CHEESE_LO, 0.35 * smooth((f - 0.5) / 0.5))

    cs_w = list(cc)
    T1, T2, B1 = [], [], []
    t1_crust, t1_cheese, t2c = [], [], []
    for i in range(N):
        cs = crust_w[i]
        dist = float(np.linalg.norm(Pxy[0][i] - Cxy))
        f1 = lerp(F1, 1 - 0.14 / dist, cs_w[i]) + RNG.uniform(-0.03, 0.03) * (1 - 0.7 * cs_w[i])
        f2 = lerp(F2, 0.55, cs_w[i]) + RNG.uniform(-0.05, 0.05)
        p1 = Cxy + f1 * (Pxy[0][i] - Cxy)
        p2 = Cxy + f2 * (Pxy[0][i] - Cxy)
        h1, h2 = hill(p1), hill(p2)
        # T1 is the foot of the crust roll: lifted a little so the cheese rises into it with a soft fillet
        T1.append(M.vert(p1[0], p1[1], ZT + DOME * (1 - f1) + h1 + 0.026 * cs_w[i] + RNG.uniform(-0.010, 0.010) * (1 - 0.6 * cs_w[i])))
        T2.append(M.vert(p2[0], p2[1], ZT + DOME * (1 - f2) + h2 + RNG.uniform(-0.006, 0.006)))
        t1_crust.append(lerpc(top_cheese(f1, h1), CRUST, cs))
        t1_cheese.append(lerpc(top_cheese(f1, h1), CHEESE_DEEP, 0.22 * cs))
        t2c.append(lerpc(top_cheese(f2, h2), CHEESE_DEEP, 0.12 * cs))
    Ctop = M.vert(cx, cy, ZT + DOME + hill(Cxy))
    pb = Cxy + FB * (np.array(Pxy[8]) - Cxy)
    for i in range(N):
        B1.append(M.vert(pb[i][0], pb[i][1], 0.0))
    Cbot = M.vert(cx, cy, 0.0)

    CH = (1, 0, 0, 0)
    BO = (0, 0, 1, 0)
    for i in range(N):
        j = (i + 1) % N
        # top: P0 -> T1 (crust slope / cheese rim), T1 -> T2, fan
        z1 = lerpc(CH, (0, 1, 0, 0), crust_w[i]), lerpc(CH, (0, 1, 0, 0), crust_w[j])
        M.quad((P[0][i], P[0][j], T1[j], T1[i]),
               (ring_col[0][i], ring_col[0][j], t1_crust[j], t1_crust[i]),
               (ring_zone[0][i], ring_zone[0][j], z1[1], z1[0]))
        M.quad((T1[i], T1[j], T2[j], T2[i]),
               (t1_cheese[i], t1_cheese[j], t2c[j], t2c[i]), (CH,) * 4)
        cen = top_cheese(0.0, hill(Cxy))
        M.tri_add((Ctop, T2[i], T2[j]), (cen, t2c[i], t2c[j]), (CH,) * 3, 1.0 + RNG.uniform(-0.012, 0.012))
        # sides, top -> bottom
        for k in range(8):
            M.quad((P[k][i], P[k + 1][i], P[k + 1][j], P[k][j]),
                   (ring_col[k][i], ring_col[k + 1][i], ring_col[k + 1][j], ring_col[k][j]),
                   (ring_zone[k][i], ring_zone[k + 1][i], ring_zone[k + 1][j], ring_zone[k][j]),
                   0.45 if k >= 2 else FACET_FLAT)
        # bottom (finished): chamfer ring is P7->P8, then P8 -> B1 and a fan
        bcol = lerpc(BOTTOM, BOTTOM_EDGE, 0.5)
        M.quad((P[8][i], B1[i], B1[j], P[8][j]),
               (BOTTOM_EDGE, bcol, bcol, BOTTOM_EDGE), (BO,) * 4)
        M.tri_add((Cbot, B1[j], B1[i]), (BOTTOM_HI, bcol, bcol), (BO,) * 3, 1.0 + RNG.uniform(-0.012, 0.012))
    nmain = len(M.v)
    info = {"N": N, "crest_z": max(v[2] for v in M.v[:nmain]),
            "cheese_z": (min(M.v[t][2] for t in T1 + T2 + [Ctop]), max(M.v[t][2] for t in T1 + T2 + [Ctop])),
            "lip_z": ZT, "bottom_ring": [M.v[P[8][i]][:2] for i in range(N)], "top_centre": (cx, cy),
            "outline": xy.tolist(), "top_ring": [M.v[P[0][i]][:2] for i in range(N)]}
    return info


def add_pepperoni(M, tree, cx, cy, R, seed):
    rng = random.Random(seed)
    # ray-cast the cheese under the disc to find where to sit it
    hits = []
    for a in [None] + [k * math.tau / 8 for k in range(8)]:
        x = cx + (0 if a is None else 0.9 * R * math.cos(a))
        y = cy + (0 if a is None else 0.9 * R * math.sin(a))
        h = tree.ray_cast(Vector((x, y, 1.0)), Vector((0, 0, -1)))
        if h[0] is not None:
            hits.append(h[0].z)
    zmax, zmin = max(hits), min(hits)
    ztop, zbot = zmax + 0.040, zmin - 0.022
    n = 10
    rot = rng.uniform(0, math.tau)
    sx = 1.0 + rng.uniform(0.02, 0.07)
    ang = [rot + math.tau * k / n for k in range(n)]
    rj = [1 + rng.uniform(-0.035, 0.035) for _ in range(n)]

    def ring(scale, z, jz=0.0):
        return [M.vert(cx + scale * R * rj[k] * sx * math.cos(ang[k]),
                       cy + scale * R * rj[k] * math.sin(ang[k]),
                       z + rng.uniform(-jz, jz)) for k in range(n)]

    c_top = M.vert(cx, cy, ztop + 0.009)
    r_top = ring(0.90, ztop, 0.0015)
    r_bev = ring(1.00, ztop - 0.012)
    r_bot = ring(1.00, zbot)
    c_bot = M.vert(cx, cy, zbot)
    Z = (0, 0, 0, 1)
    for k in range(n):
        j = (k + 1) % n
        tone = 1.0 + (0.045 if k % 2 == 0 else -0.04) + rng.uniform(-0.02, 0.02)
        M.tri_add((c_top, r_top[k], r_top[j]), (PEP_HI, PEP, PEP), (Z,) * 3, tone, 0.5)
        M.quad((r_bev[k], r_bev[j], r_top[j], r_top[k]), (PEP_RIM, PEP_RIM, PEP, PEP), (Z,) * 4)
        M.quad((r_bev[k], r_bot[k], r_bot[j], r_bev[j]), (PEP_RIM, PEP_SIDE, PEP_SIDE, PEP_RIM), (Z,) * 4)
        M.tri_add((c_bot, r_bot[j], r_bot[k]), (PEP_SIDE,) * 3, (Z,) * 3)
    return {"center": (cx, cy), "radius": R, "z_top": ztop + 0.009, "z_base": zbot}


# ---------------------------------------------------------------- texture painting
class Noise:
    def __init__(self, seed, n=32):
        self.t = np.random.RandomState(seed).rand(n, n, n).astype(np.float32)
        self.n = n

    def __call__(self, p):
        n = self.n
        x = np.floor(p).astype(np.int64)
        f = (p - x).astype(np.float32)
        f = f * f * (3 - 2 * f)
        i0, i1 = x % n, (x + 1) % n
        t = self.t

        c000 = t[i0[:, 0], i0[:, 1], i0[:, 2]]
        c100 = t[i1[:, 0], i0[:, 1], i0[:, 2]]
        c010 = t[i0[:, 0], i1[:, 1], i0[:, 2]]
        c110 = t[i1[:, 0], i1[:, 1], i0[:, 2]]
        c001 = t[i0[:, 0], i0[:, 1], i1[:, 2]]
        c101 = t[i1[:, 0], i0[:, 1], i1[:, 2]]
        c011 = t[i0[:, 0], i1[:, 1], i1[:, 2]]
        c111 = t[i1[:, 0], i1[:, 1], i1[:, 2]]
        fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]
        return (((c000 * (1 - fx) + c100 * fx) * (1 - fy) + (c010 * (1 - fx) + c110 * fx) * fy) * (1 - fz) +
                ((c001 * (1 - fx) + c101 * fx) * (1 - fy) + (c011 * (1 - fx) + c111 * fx) * fy) * fz)


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def shade(col, zone, pos, noises):
    n1 = noises[0](pos * 2.6)
    n2 = noises[1](pos * 7.5 + 3.1)
    n3 = noises[2](pos * 4.2 + 9.7)
    n4 = noises[3](pos * 24.0 + 1.3)
    lo = 0.6 * n1 + 0.4 * n2
    amp = zone[:, 0] * 0.05 + zone[:, 1] * 0.075 + zone[:, 2] * 0.06 + zone[:, 3] * 0.045
    col = col * (1.0 + amp * (2 * lo - 1))[:, None]
    drift = (n3 - 0.5) * 0.03
    col = col + np.stack([drift, drift * 0.3, -drift], 1)
    cz = zone[:, 0]
    b = (sstep(0.60, 0.80, 0.65 * n3 + 0.35 * n2) * cz * 0.40)[:, None]       # toasted cheese blotches
    col = col * (1 - b) + np.array(CHEESE_BROWN) * b
    h = (sstep(0.68, 0.88, n1) * cz * 0.25)[:, None]                         # lighter cheese patches
    col = col * (1 - h) + np.array(CHEESE_HI) * h
    k = (sstep(0.66, 0.88, n2) * zone[:, 1] * 0.28)[:, None]                 # darker baked crust patches
    col = col * (1 - k) + np.array(CRUST_LO) * k
    f = (sstep(0.78, 0.90, n4) * zone[:, 3] * 0.5)[:, None]                  # pepperoni fat flecks
    col = col * (1 - f) + np.array(FLECK) * f
    return np.clip(col, 0, 1)


def paint_atlas(tri_uv, tri_pos, tri_col, tri_zone, size):
    noises = [Noise(s) for s in (11, 23, 37, 53)]
    img = np.zeros((size, size, 3), np.float32)
    count = np.zeros((size, size), np.uint8)
    for t in range(len(tri_uv)):
        p = tri_uv[t] * size
        x0, x1 = int(max(0, math.floor(p[:, 0].min()))), int(min(size - 1, math.ceil(p[:, 0].max())))
        y0, y1 = int(max(0, math.floor(p[:, 1].min()))), int(min(size - 1, math.ceil(p[:, 1].max())))
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(d) < 1e-12:
            continue
        w0 = ((p[1, 1] - p[2, 1]) * (X - p[2, 0]) + (p[2, 0] - p[1, 0]) * (Y - p[2, 1])) / d
        w1 = ((p[2, 1] - p[0, 1]) * (X - p[2, 0]) + (p[0, 0] - p[2, 0]) * (Y - p[2, 1])) / d
        w2 = 1 - w0 - w1
        m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if m.any():
            W = np.stack([w0[m], w1[m], w2[m]], 1)
            yy, xx = np.nonzero(m)
        else:   # sub-pixel sliver: paint the pixel under its centroid so it never goes empty
            W = np.array([[1 / 3, 1 / 3, 1 / 3]])
            cxp, cyp = p[:, 0].mean(), p[:, 1].mean()
            xx, yy = np.array([int(min(size - 1, max(0, cxp))) - x0]), np.array([int(min(size - 1, max(0, cyp))) - y0])
        col = shade(W @ tri_col[t], W @ tri_zone[t], W @ tri_pos[t], noises)
        img[y0 + yy, x0 + xx] = col
        count[y0 + yy, x0 + xx] += 1
    mask = count > 0
    overlap = int((count > 1).sum())
    # dilate colours past island borders (mip/filter bleed), then fill any leftover with the mean
    cur, m = img.copy(), mask.copy()
    for _ in range(4):
        acc = np.zeros_like(cur)
        cnt = np.zeros(m.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            sm, si = np.roll(m, (dy, dx), (0, 1)), np.roll(cur, (dy, dx), (0, 1))
            use = sm & ~m
            acc[use] += si[use]
            cnt[use] += 1
        new = cnt > 0
        cur[new] = acc[new] / cnt[new][:, None]
        m = m | new
    cur[~m] = img[mask].mean(0)
    return cur, mask, overlap


# ---------------------------------------------------------------- scene / render helpers
def make_camera(scene, coll, name, loc, target, lens=85, ortho=None, up_hint=(0, 0, 1)):
    cd = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cd)
    coll.objects.link(cam)
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
    else:
        cd.lens = lens
    cd.clip_start, cd.clip_end = 0.05, 100
    f = (Vector(target) - Vector(loc)).normalized()
    right = f.cross(Vector(up_hint)).normalized()
    up = right.cross(f)
    rot = Matrix(((right.x, up.x, -f.x), (right.y, up.y, -f.y), (right.z, up.z, -f.z))).to_4x4()
    cam.matrix_world = Matrix.Translation(Vector(loc)) @ rot
    return cam


def area_light(coll, loc, energy, size, target):
    ld = bpy.data.lights.new("Review light", "AREA")
    ld.energy, ld.shape, ld.size = energy, "DISK", size
    lo = bpy.data.objects.new("Review light", ld)
    coll.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return lo


def render(scene, cam, path, w, h, samples):
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.cycles.samples = samples
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def load_pixels(path):
    im = bpy.data.images.load(str(path))
    w, h = im.size
    a = np.array(im.pixels[:], np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    return a


def save_array(arr, path):
    h, w = arr.shape[:2]
    im = bpy.data.images.new("tmp_" + Path(path).stem, w, h, alpha=False)
    im.colorspace_settings.name = "sRGB"
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = arr[..., :3]
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def box_down(a, f):
    h, w = a.shape[0] // f * f, a.shape[1] // f * f
    return a[:h, :w].reshape(h // f, f, w // f, f, a.shape[2]).mean((1, 3))


# ---------------------------------------------------------------- main
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"

    # ---- geometry
    M = MeshData()
    info = build_slice(M)
    tree = BVHTree.FromPolygons([Vector(v) for v in M.v], M.tri, epsilon=0.0)
    n_main_tris = len(M.tri)
    pep_info = []
    for s, (px, pr, rad) in enumerate(PEPPERONI):
        pep_info.append(add_pepperoni(M, tree, px, -pr, rad, 100 + s))

    # recentre: origin = area centroid of the flat bottom footprint, on the ground plane
    foot = np.array(info["bottom_ring"])
    a2 = foot[:, 0] * np.roll(foot[:, 1], -1) - np.roll(foot[:, 0], -1) * foot[:, 1]
    fx = ((foot[:, 0] + np.roll(foot[:, 0], -1)) * a2).sum() / (3 * a2.sum())
    fy = ((foot[:, 1] + np.roll(foot[:, 1], -1)) * a2).sum() / (3 * a2.sum())
    verts = [(SCALE * (x - fx), SCALE * (y - fy), SCALE * z) for x, y, z in M.v]
    for pi in pep_info:
        pi["center"] = (SCALE * (pi["center"][0] - fx), SCALE * (pi["center"][1] - fy))
        pi["radius"] = round(SCALE * pi["radius"], 4)
        pi["z_top"] *= SCALE
        pi["z_base"] *= SCALE

    me = bpy.data.meshes.new("PizzaSlice")
    me.from_pydata(verts, [], M.tri)
    me.update()
    obj = bpy.data.objects.new("PizzaSlice", me)
    export_coll = bpy.data.collections.new("PizzaSlice | Export geometry")
    scene.collection.children.link(export_coll)
    export_coll.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    # shell orientation: outward normals everywhere (flip a shell if its signed volume is negative)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    # recalc may have reordered nothing, but make sure triangle order is unchanged for colour lookup
    assert len(me.polygons) == len(M.tri)

    # ---- UVs
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.006, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.shade_flat()

    # polygon vertex order may differ from the build order after recalc: rebuild colours by vertex id
    uvs = np.zeros(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get("uv", uvs)
    uvs = uvs.reshape(-1, 2)
    tri_uv, tri_pos, tri_col, tri_zone = [], [], [], []
    for pi_, poly in enumerate(me.polygons):
        ids = tuple(poly.vertices)
        src = M.tri[pi_]
        assert sorted(ids) == sorted(src), "triangle order changed"
        # map this polygon's corner order onto the source corner order
        order = [src.index(v) for v in ids]
        tri_uv.append(uvs[poly.loop_start:poly.loop_start + 3])
        tri_pos.append(np.array([verts[v] for v in ids]))
        tri_col.append(np.array([M.col[pi_][o] for o in order]))
        tri_zone.append(np.array([M.zone[pi_][o] for o in order], np.float64))
    tri_uv = np.array(tri_uv)
    atlas_arr, uv_mask, uv_overlap = paint_atlas(tri_uv, tri_pos, tri_col, tri_zone, TEX)

    # ---- image + material
    atlas = bpy.data.images.new("PizzaSlice_BaseColor", TEX, TEX, alpha=False)
    atlas.colorspace_settings.name = "sRGB"
    rgba = np.ones((TEX, TEX, 4), np.float32)
    rgba[..., :3] = atlas_arr
    atlas.pixels.foreach_set(rgba.ravel())
    atlas.filepath_raw = str(OUT / "BaseColor.png")
    atlas.file_format = "PNG"
    atlas.save()
    atlas.pack()
    mat = bpy.data.materials.new("PizzaSlice | baked base color")
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image, tex.interpolation = atlas, "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.72
    obj.data.materials.append(mat)
    obj["pivot"] = "Footprint (bottom face) area centroid, on the ground plane"
    obj["orientation"] = "Z up; tip toward +Y (Roblox front -Z after FBX/GLB export); crust toward -Y"

    # ---- review stage (never exported)
    stage = bpy.data.collections.new("REVIEW | not exported")
    scene.collection.children.link(stage)
    dims = obj.dimensions
    S = SCALE
    target = Vector((0, 0.0, 0.14 * S))
    fl_mat = bpy.data.materials.new("Neutral review floor")
    try:
        fl_mat.use_nodes = True
    except Exception:
        pass
    fl_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.36, 0.36, 1)
    fl_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
    bpy.ops.mesh.primitive_plane_add(size=160, location=(0, 0, -0.004))
    floor = bpy.context.object
    floor.name = "Review floor"
    floor.data.materials.append(fl_mat)
    for c in list(floor.users_collection):
        c.objects.unlink(floor)
    stage.objects.link(floor)
    world = bpy.data.worlds.new("Review world")
    scene.world = world
    try:
        world.use_nodes = True
    except Exception:
        pass
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.30, 0.30, 0.30, 1)
    bg.inputs[1].default_value = 0.9
    for loc, en, sz in [((-3.4, 3.0, 5.2), 330, 4.0), ((4.2, 2.0, 3.4), 170, 4.0), ((-1.0, -4.6, 3.6), 210, 3.0)]:
        area_light(stage, tuple(c * S for c in loc), en * S * S, sz * S, target)

    scene.render.engine = "CYCLES"
    cy = scene.cycles
    cy.device = "CPU"
    cy.use_denoising = True
    cy.denoiser = "OPENIMAGEDENOISE"
    cy.max_bounces = 4
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False

    hero = make_camera(scene, stage, "Hero camera (3/4)", (2.5 * S, 3.1 * S, 2.65 * S), (0.0, -0.1 * S, 0.12 * S), lens=65)
    top = make_camera(scene, stage, "Gameplay top camera", (0.0, 2.1 * S, 5.9 * S), (0, -0.05 * S, 0.12 * S), lens=70,
                      up_hint=(0, -1, 0))
    side = make_camera(scene, stage, "Side camera", (7.0 * S, -0.05 * S, 1.9 * S), (0, -0.05 * S, 0.17 * S), lens=85)

    if QUICK:
        render(scene, hero, OUT / "quick_hero.png", 640, 640, 10)
        render(scene, top, OUT / "quick_top.png", 560, 560, 10)
        close = make_camera(scene, stage, "Close camera", (3.4 * S, 0.2 * S, 0.62 * S), (0.4 * S, 0.2 * S, 0.09 * S), lens=100)
        render(scene, close, OUT / "quick_close.png", 900, 450, 12)
        floor.hide_render = True
        under = make_camera(scene, stage, "Underside camera", (0.2 * S, 0.3 * S, -5.4 * S), (0, 0, 0.1 * S), lens=70, up_hint=(0, 1, 0))
        render(scene, under, OUT / "quick_under.png", 520, 520, 8)
        print("QUICK_DONE")
        return

    # ---- save blend, renders
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Model.blend"))
    render(scene, hero, OUT / "Preview.png", 1000, 1000, 24)
    tmp = OUT / "_tmp"
    tmp.mkdir(exist_ok=True)
    render(scene, top, tmp / "top.png", 700, 700, 24)
    render(scene, side, tmp / "side.png", 700, 350, 24)
    t_img, s_img = load_pixels(tmp / "top.png"), load_pixels(tmp / "side.png")
    crop = t_img[70:630, 70:630, :3]
    bgc = np.median(crop.reshape(-1, 3), axis=0)   # floor colour, so the shrunken reads sit on a matching panel
    sheet = np.ones((700, 1400, 3), np.float32) * bgc
    sheet[:, :700] = t_img[..., :3]
    sheet[350:, 700:] = s_img[..., :3]          # arrays are bottom-up: this is the TOP-right panel
    th1, th2 = box_down(crop, 5), box_down(crop, 10)       # 112 px and 56 px "gameplay size" reads
    sheet[120:232, 800:912] = th1               # bottom-right panel
    sheet[120:176, 1010:1066] = th2
    save_array(sheet, OUT / "Alternate.png")
    shutil.rmtree(tmp, ignore_errors=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "Model.blend"))

    # ---- exports (asset only)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(filepath=str(OUT / "Model.fbx"), use_selection=True, object_types={"MESH"},
                             bake_anim=False, axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "Model.glb"), export_format="GLB", use_selection=True,
                              export_animations=False)

    # ---- validation of the authored mesh
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    nonman = sum(not e.is_manifold for e in bm.edges)
    boundary = sum(e.is_boundary for e in bm.edges)
    loose = sum(not v.link_edges for v in bm.verts)
    zero_area = sum(f.calc_area() < 1e-9 for f in bm.faces)
    min_area = min(f.calc_area() for f in bm.faces)
    inconsistent = sum(1 for e in bm.edges if len(e.link_loops) == 2 and e.link_loops[0].vert == e.link_loops[1].vert)
    # shells + signed volume (outward normals => positive)
    seen, shells = set(), []
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        stack, comp = [f0], []
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            comp.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        vol = sum(f.verts[0].co.dot(f.verts[1].co.cross(f.verts[2].co)) / 6.0 for f in comp)
        shells.append({"faces": len(comp), "signed_volume": round(vol, 5)})
    kd_min = 1e9
    from mathutils.kdtree import KDTree
    kd = KDTree(len(bm.verts))
    for v in bm.verts:
        kd.insert(v.co, v.index)
    kd.balance()
    for v in bm.verts:
        for co, idx, dist in kd.find_n(v.co, 2):
            if idx != v.index:
                kd_min = min(kd_min, dist)
    # texel density
    dens = []
    for p, uv in zip(me.polygons, tri_uv):
        ua = abs((uv[1][0] - uv[0][0]) * (uv[2][1] - uv[0][1]) - (uv[2][0] - uv[0][0]) * (uv[1][1] - uv[0][1])) / 2
        if p.area > 1e-8 and ua > 0:
            dens.append(math.sqrt(ua * TEX * TEX / p.area))
    dens = np.array(dens)
    ar = []
    for f in bm.faces:
        ls = sorted((f.verts[i].co - f.verts[(i + 1) % 3].co).length for i in range(3))
        ar.append(ls[2] / max(2 * f.calc_area() / ls[2], 1e-9))
    bm.free()
    bb = [Vector(c) for c in obj.bound_box]
    mn = Vector((min(c.x for c in bb), min(c.y for c in bb), min(c.z for c in bb)))
    mx = Vector((max(c.x for c in bb), max(c.y for c in bb), max(c.z for c in bb)))
    # pivot check: area centroid of faces lying on the bottom plane
    tot, cxs, cys = 0.0, 0.0, 0.0
    for p in me.polygons:
        if all(abs(me.vertices[v].co.z) < 1e-6 for v in p.vertices):
            tot += p.area
            cxs += p.center.x * p.area
            cys += p.center.y * p.area
    stats = {
        "name": "PizzaSlice",
        "vertices": len(me.vertices),
        "triangles": sum(len(p.vertices) - 2 for p in me.polygons),
        "mesh_objects": 1,
        "materials": len(me.materials),
        "uv_layers": len(me.uv_layers),
        "uv_range": [float(tri_uv.min()), float(tri_uv.max())],
        "uv_overlap_pixels": uv_overlap,
        "uv_coverage_pct": round(100.0 * float(uv_mask.mean()), 1),
        "texel_density_px_per_unit": {"min": round(float(dens.min()), 1), "median": round(float(np.median(dens)), 1),
                                      "max": round(float(dens.max()), 1)},
        "texture": f"{TEX}x{TEX} base color, packed in Model.blend, embedded in FBX/GLB",
        "nonmanifold_edges": nonman,
        "boundary_edges": boundary,
        "loose_vertices": loose,
        "zero_area_faces": zero_area,
        "smallest_face_area": round(min_area, 7),
        "worst_triangle_aspect": round(float(max(ar)), 1),
        "inconsistent_winding_edges": inconsistent,
        "closed_shells": shells,
        "min_vertex_distance": round(kd_min, 6),
        "bounds_min": [round(c, 4) for c in mn],
        "bounds_max": [round(c, 4) for c in mx],
        "dimensions_xyz": [round(c, 4) for c in obj.dimensions],
        "pivot": {"origin": [0, 0, 0], "bottom_face_centroid_xy": [round(cxs / tot, 5), round(cys / tot, 5)],
                  "lowest_z": round(mn.z, 6), "note": "origin is the area centroid of the flat bottom face on Z=0"},
        "orientation": "Blender Z up, tip +Y, crust -Y. Exports: Y up, tip toward -Z (Roblox front).",
        "design_scale": SCALE,
        "heights": {
            "bread_plus_cheese_top_min": round(SCALE * info["cheese_z"][0], 4),
            "bread_plus_cheese_top_max": round(SCALE * info["cheese_z"][1], 4),
            "bread_plus_cheese_lip": round(SCALE * info["lip_z"], 4),
            "crust_crest_max": round(SCALE * info["crest_z"], 4),
            "crust_to_cheese_ratio": round(info["crest_z"] / (0.5 * (info["cheese_z"][0] + info["cheese_z"][1])), 3),
            "pepperoni_top_max": round(max(p["z_top"] for p in pep_info), 4),
        },
        "main_surface_triangles": n_main_tris,
        "pepperoni_triangles": len(M.tri) - n_main_tris,
        "pepperoni": [{"center_xy": [round(v, 3) for v in p["center"]], "radius": p["radius"],
                       "top_z": round(p["z_top"], 4)} for p in pep_info],
        "reference_sha256_matches": None,
    }
    # reference copy
    dst = OUT / "Reference.png"
    shutil.copyfile(REF_SRC, dst)
    stats["reference_sha256_matches"] = hashlib.sha256(REF_SRC.read_bytes()).hexdigest() == hashlib.sha256(dst.read_bytes()).hexdigest()
    stats["blend_packed_texture"] = atlas.packed_file is not None

    # ---- reimport checks (fresh empty scenes)
    def inspect(label):
        ms = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        pts = [o.matrix_world @ v.co for o in ms for v in o.data.vertices]
        dim = [max(p[a] for p in pts) - min(p[a] for p in pts) for a in range(3)]
        return {
            "mesh_objects": len(ms),
            "triangles": sum(len(p.vertices) - 2 for o in ms for p in o.data.polygons),
            "has_uv": all(len(o.data.uv_layers) > 0 for o in ms),
            "has_image_texture": all(any(n.type == "TEX_IMAGE" and n.image for m in o.data.materials if m and m.use_nodes
                                         for n in m.node_tree.nodes) for o in ms),
            "texture_pixels_loaded": all(n.image.size[0] > 0 for o in ms for m in o.data.materials if m and m.use_nodes
                                         for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image),
            "unexpected_stage_objects": sum(o.type != "MESH" for o in bpy.context.scene.objects),
            "dimensions_xyz": [round(d, 4) for d in dim],
            "all_faces_triangular": all(len(p.vertices) == 3 for o in ms for p in o.data.polygons),
        }
    ref_dims = [round(c, 4) for c in obj.dimensions]
    for ext in ("glb", "fbx"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if ext == "glb":
            bpy.ops.import_scene.gltf(filepath=str(OUT / "Model.glb"))
        else:
            bpy.ops.import_scene.fbx(filepath=str(OUT / "Model.fbx"))
        r = inspect(ext)
        r["triangle_count_matches"] = r["triangles"] == stats["triangles"]
        # exported files are Y-up (tip toward -Z): sorted extents must match the Blender asset
        r["dimensions_match_source"] = sorted(r["dimensions_xyz"]) == sorted(ref_dims) or all(
            abs(a - b) < 2e-3 * max(1, b) for a, b in zip(sorted(r["dimensions_xyz"]), sorted(ref_dims)))
        stats[ext + "_reimport"] = r
    (OUT / "validation.json").write_text(json.dumps(stats, indent=2))
    write_readme(stats)
    print("ASSET_COMPLETE", json.dumps({k: stats[k] for k in ("vertices", "triangles", "nonmanifold_edges",
                                                              "zero_area_faces", "dimensions_xyz")}), flush=True)


def write_readme(s):
    d = s["dimensions_xyz"]
    (OUT / "README.md").write_text(f"""# Pizza Slice (Chef pickup)

Blender-verified, Studio untested. Not imported into Roblox Studio, not uploaded, no gameplay wiring.

One low-poly pepperoni slice for the Chef class: kills sometimes drop it and walking over it heals. It lies flat on
the ground and is meant to bob and spin from script. Matches `Reference.png` (the unmodified concept): golden crust
roll at the back, yellow cheese with soft drips over the sides, three raised flat pepperoni, tapered tip.

## Files
- `Model.blend`: editable mesh `PizzaSlice` in collection `PizzaSlice | Export geometry`, base colour packed. Camera,
  lights and floor live in `REVIEW | not exported`.
- `Model.fbx`, `Model.glb`: the mesh only (no camera, floor or lights), base colour embedded.
- `BaseColor.png`: {s['texture'].split(' base')[0]} atlas, painted straight from the mesh (painterly low-noise breakup).
- `Preview.png`: 3/4 hero. `Alternate.png`: left, top-down as the high gameplay camera sees it; top right, side view;
  bottom right, the same top view shrunk to roughly in-game pixel sizes (112 px and 56 px) to prove it reads as pizza.
- `validation.json`: measured checks. `build_pizza_slice.py`: self-contained generator.

## Orientation and pivot
- Blender is Z-up. The slice lies on Z = 0 with the TIP toward +Y, the CRUST toward -Y and the toppings toward +Z.
- FBX/GLB export converts to Y-up, tip toward -Z (Roblox front), same convention as the weapon set.
- Origin is the area centroid of the flat bottom footprint, at ground level, so the slice sits on the floor and spins
  about its own middle. Bounds: {d[0]} x {d[1]} x {d[2]} units (X wide, Y long, Z tall); lowest Z is 0.
- 1 unit = 1 stud. Designed about 2.1 long, then uniformly scaled x{s['design_scale']:g} so the heights land at the requested
  stud values: bread + cheese about {s['heights']['bread_plus_cheese_top_min']} to {s['heights']['bread_plus_cheese_top_max']}, crust crest
  {s['heights']['crust_crest_max']} ({s['heights']['crust_to_cheese_ratio']}x the cheese height). Change `SCALE` in the script to rescale; scaling the MeshPart in Studio
  keeps the proportions.

## Build
{s['triangles']} triangles, {s['vertices']} vertices, 1 material, 1 UV map, one 512 px atlas. Bread layer, cheese, crust
roll and all four drips are one closed surface (no seams). The crust is a puffy faceted roll that overhangs the sides
at the back and takes the cheese up into it with a soft fillet. The drips hang down the bread wall (two on one long edge,
two on the other, four different lengths) as part of the same sheet, ending in rounded teardrop tips; seen from above
the outline stays a clean triangle with only slight soft bulges. The cheese top has a few broad rises and dips. The three pepperoni are separate closed bevelled discs sunk into the
cheese (intentional overlap, {s['pepperoni_triangles']} triangles). The underside is finished (toasted bread colour,
chamfered edge). Flat shading, no normal maps, no vertex colours in the export.

Rebuild: `& "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --threads 4 --python roguelite-planning/pickups/pizza-slice/build_pizza_slice.py`

## Limitations
- Studio import, scale, texture upload and in-game look are untested.
- Colours are bright on purpose (the game adds +0.3 saturation); judge them in Play, not in Blender.
- The pepperoni overlap the cheese as separate shells rather than being welded to it.
- The cheese-top fan facets converge on the tip as long thin triangles (worst aspect about {s['worst_triangle_aspect']}:1); flat shading hides it, but it is not an even triangulation.
- The 512 px atlas is about {s['uv_coverage_pct']}% used (unwrap packing); fine for a pickup this small, shrinkable to 256 px if memory ever matters.
""", encoding="utf-8")


main()
