"""Chest pipeline: build one tier's chest from tiers/<tier>.py, bake icon lighting, render, export.

    blender --background --python generate_chest.py -- <tier>
    blender --background --python generate_chest.py -- <tier> --preview   # renders only

Run author_textures.py <tier> first (system Python) to paint textures/chest-<tier>.png.

Every tier is a *different chest*: the tier file owns its whole shape (tiers/<tier>.py
`build(k)`), its palette, glow and how it opens. This file only supplies the shared
machinery so all five chests share one finish:

* a mesh builder (boxes, bands, prisms, bolts, lofts, free polygons) where every piece is
  welded and bevelled on its own before joining. Welding a whole part at once merges
  pieces that only touch at a corner, and the bevel's overlap clamp then shrinks every
  chamfer to nothing.
* the icon-lighting bake the user approved on the Wooden chest (2026-09-27): painted atlas
  x per-facet key light x AO x height gradient + cool rim light, with bright highlights
  on every bevelled edge, baked onto unique UVs so Roblox shows it on top of its lighting;
* preview renders, FBX/GLB export and polygon-report-<tier>.json.

Style: ../art-references/ART_DIRECTION_USER_2026-09-17.txt pushed toward the user's weapon
icons (studio-prototype/ui/assets/weapons): chunky, saturated, softly bevelled, faceted.
Self-contained on purpose (see the kit README).
"""
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Vector, Matrix

ROOT = Path(__file__).resolve().parent
TEX = ROOT / "textures"
for d in ("previews", "exports/glb", "exports/fbx"):
    (ROOT / d).mkdir(parents=True, exist_ok=True)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
TIER = next((a for a in ARGS if not a.startswith("--")), "wooden")
PREVIEW = "--preview" in ARGS


def load_tier(tier):
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"chest_tier_{tier}", ROOT / "tiers" / f"{tier}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = load_tier(TIER)
LOOK = {"glow": tuple(T.GLOW), "accent": tuple(getattr(T, "ACCENT", T.GLOW))}
CHAMFER = getattr(T, "CHAMFER", 0.06)                       # default soft edge, studs
SHARP = math.radians(getattr(T, "SHARP_DEG", 30))           # facets steeper than this stay crisp
BAKE_SIZE = 2048

# ---------------------------------------------------------------------------
# painted source atlas layout (must match author_textures.py)
#   u 0-0.75           primary surface: 16 horizontal bands (planks, panels, stone courses...)
#   u 0.75-1, v .375-1 metal / trim
#   u 0.75-1, v 0-.375 six flat swatches
# ---------------------------------------------------------------------------
BANDS = 16
WOOD_U = 0.75
METAL_U0, METAL_V0 = 0.75, 0.375
M_SPAN_V = 8.5
M_SPAN_U = M_SPAN_V * 0.4
SWATCHES = ("rivet", "keyhole", "gem", "swatch4", "swatch5", "swatch6")
ALIAS = {"dark": "keyhole"}


def primary_uv(a, b, band0, plank):
    """Planar primary surface: a along the band, b across (studs); band0 picks the band;
    plank is how many studs one band spans."""
    span_v = BANDS * plank
    span_u = span_v * WOOD_U
    return (WOOD_U * ((a + span_u / 2) / span_u), (band0 * plank + b) / span_v)


def band_uv(a, t, band, plank):
    """One board / panel: t 0..1 across it maps inside a single band."""
    span_u = BANDS * plank * WOOD_U
    v0, v1 = band / BANDS + 0.006, (band + 1) / BANDS - 0.006
    return (WOOD_U * ((a + span_u / 2) / span_u), v0 + (v1 - v0) * t)


def metal_uv(s, t):
    s %= M_SPAN_V
    t %= M_SPAN_U
    return (METAL_U0 + 0.25 * t / M_SPAN_U, METAL_V0 + (1 - METAL_V0) * s / M_SPAN_V)


def swatch_uv(name):
    i = SWATCHES.index(ALIAS.get(name, name))
    return (METAL_U0 + (i + 0.5) * 0.25 / len(SWATCHES), METAL_V0 * 0.5)


def metal(p, f):
    """uvf for metal boxes/bands: planar by face, long axis along the metal block."""
    if f in ("-y", "+y"):
        a, b = p.x, p.z
    elif f in ("-x", "+x"):
        a, b = p.y, p.z
    else:
        a, b = p.x, p.y
    return metal_uv(a + 10, b + 10) if abs(a) >= abs(b) else metal_uv(b + 10, a + 10)


def swatch(name):
    """uvf that paints a whole piece one swatch colour."""
    uv = swatch_uv(name)
    return lambda p, f: uv


def offset_profile(pts, off):
    """Push (y, z) profile points out along their averaged normals (left of travel), mitred."""
    out = []
    for k, (y, z) in enumerate(pts):
        prev = pts[k - 1] if k > 0 else None
        nxt = pts[k + 1] if k < len(pts) - 1 else None
        normals = []
        for a, b in ((prev, (y, z)), ((y, z), nxt)):
            if a and b:
                dy, dz = b[0] - a[0], b[1] - a[1]
                ln = math.hypot(dy, dz)
                normals.append((-dz / ln, dy / ln))
        ny = sum(n[0] for n in normals) / len(normals)
        nz = sum(n[1] for n in normals) / len(normals)
        ln = math.hypot(ny, nz)
        ny, nz = ny / ln, nz / ln
        scale = 1.0
        if len(normals) == 2:
            dot = normals[0][0] * normals[1][0] + normals[0][1] * normals[1][1]
            scale = 1 / max(0.5, math.sqrt((1 + dot) / 2))
        out.append((y + ny * off * scale, z + nz * off * scale))
    return out


# ---------------------------------------------------------------------------
# mesh builder
# ---------------------------------------------------------------------------
FACES = {"-y": (0, 1, 5, 4), "+y": (2, 3, 7, 6), "-x": (3, 0, 4, 7), "+x": (1, 2, 6, 5), "-z": (3, 2, 1, 0), "+z": (4, 5, 6, 7)}


class Builder:
    """Collects separate pieces; each is welded and bevelled alone, then all are joined.

    Every primitive starts a new piece. For a custom shape call begin() and then poly().
    uvf(point, tag) -> (u, v) for every vertex (tags: face names, "side", "cap0", "cap1").
    Coordinates are studs, Blender Z-up, ground at z=0, front faces -Y.
    """

    def __init__(self):
        self.pieces = []
        self.chamfers = []
        self.begin()

    def begin(self, chamfer=None):
        """Start a new piece; chamfer overrides the tier default for this piece."""
        self.verts, self.faces, self.uvs = [], [], []
        self.pieces.append((self.verts, self.faces, self.uvs))
        self.chamfers.append(chamfer)

    def poly(self, pts, uvs):
        base = len(self.verts)
        self.verts += [tuple(p) for p in pts]
        self.faces.append(list(range(base, base + len(pts))))
        self.uvs.append(list(uvs))

    def box(self, x0, x1, y0, y1, z0, z1, uvf, skip=(), chamfer=None):
        self.begin(chamfer)
        c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        for name, ids in FACES.items():
            if name not in skip:
                pts = [Vector(c[i]) for i in ids]
                self.poly(pts, [uvf(p, name) for p in pts])

    def ring(self, x0, x1, y0, y1, z0, z1, wall, uvf, chamfer=None):
        """Rectangular band / frame."""
        self.begin(chamfer)
        o = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        i = [(x0 + wall, y0 + wall), (x1 - wall, y0 + wall), (x1 - wall, y1 - wall), (x0 + wall, y1 - wall)]
        names = ["-y", "+x", "+y", "-x"]
        for k in range(4):
            a, b = o[k], o[(k + 1) % 4]
            pts = [Vector((a[0], a[1], z0)), Vector((b[0], b[1], z0)), Vector((b[0], b[1], z1)), Vector((a[0], a[1], z1))]
            self.poly(pts, [uvf(p, names[k]) for p in pts])
            a, b = i[k], i[(k + 1) % 4]
            pts = [Vector((b[0], b[1], z0)), Vector((a[0], a[1], z0)), Vector((a[0], a[1], z1)), Vector((b[0], b[1], z1))]
            self.poly(pts, [uvf(p, names[k]) for p in pts])
            for z, up in ((z1, True), (z0, False)):
                pts = [Vector((o[k][0], o[k][1], z)), Vector((o[(k + 1) % 4][0], o[(k + 1) % 4][1], z)),
                       Vector((i[(k + 1) % 4][0], i[(k + 1) % 4][1], z)), Vector((i[k][0], i[k][1], z))]
                if not up:
                    pts.reverse()
                self.poly(pts, [uvf(p, "+z") for p in pts])

    def prism(self, center, radius, sides, y_front, y_back, uvf, rot=0.0, chamfer=None):
        """Polygonal prism facing -Y, centred at (x, z)."""
        self.begin(chamfer)
        cx, cz = center
        ring = [(cx + radius * math.sin(rot + k * 2 * math.pi / sides), cz + radius * math.cos(rot + k * 2 * math.pi / sides)) for k in range(sides)]
        front = [Vector((x, y_front, z)) for x, z in ring]
        back = [Vector((x, y_back, z)) for x, z in ring]
        self.poly(list(reversed(front)), [uvf(p, "-y") for p in reversed(front)])
        for k in range(sides):
            a, b = k, (k + 1) % sides
            pts = [front[a], front[b], back[b], back[a]]
            self.poly(pts, [uvf(p, "side") for p in pts])

    def rivet(self, x, z, y_surface, size=1.0):
        """Chunky domed bolt head on a -Y facing surface."""
        sw = swatch("rivet")
        self.prism((x, z), 0.14 * size, 8, y_surface - 0.06 * size, y_surface + 0.01, sw, rot=math.pi / 8)
        self.prism((x, z), 0.09 * size, 8, y_surface - 0.10 * size, y_surface - 0.05 * size, sw, rot=math.pi / 8)

    def loft(self, rings, uvf, cap0=True, cap1=True, chamfer=None):
        """Skin a list of closed rings (lists of Vector, equal length, same winding) into a
        solid: tapered bodies, domes, crystals, horns, feet. Rings run from start to end;
        winding counter-clockwise when viewed from the end cap faces outward.
        A ring may collapse to a single repeated point for a pointed tip (skip that cap)."""
        self.begin(chamfer)
        n = len(rings[0])
        for r in range(len(rings) - 1):
            a, b = rings[r], rings[r + 1]
            for j in range(n):
                jj = (j + 1) % n
                pts = [a[j], a[jj], b[jj], b[j]]
                if (pts[0] - pts[1]).length < 1e-6 and (pts[2] - pts[3]).length < 1e-6:
                    continue
                if (pts[0] - pts[1]).length < 1e-6:
                    pts = [pts[0], pts[2], pts[3]]
                elif (pts[2] - pts[3]).length < 1e-6:
                    pts = [pts[0], pts[1], pts[2]]
                self.poly(pts, [uvf(p, "side") for p in pts])
        if cap0:
            pts = list(reversed(rings[0]))
            self.poly(pts, [uvf(p, "cap0") for p in pts])
        if cap1:
            pts = list(rings[-1])
            self.poly(pts, [uvf(p, "cap1") for p in pts])

    def build(self, name, material, bevel=True):
        objs = []
        for i, ((verts, faces, uvs), chamfer) in enumerate(zip(self.pieces, self.chamfers)):
            if not faces:
                continue
            mesh = bpy.data.meshes.new(f"{name}_{i}")
            mesh.from_pydata(verts, [], faces)
            mesh.update()
            mesh.materials.append(material)
            layer = mesh.uv_layers.new(name="UVMap")
            for poly, uv in zip(mesh.polygons, uvs):
                for li, u in zip(poly.loop_indices, uv):
                    layer.data[li].uv = u
            mesh.validate()
            obj = bpy.data.objects.new(f"{name}_{i}", mesh)
            bpy.context.collection.objects.link(obj)
            weld_and_bevel(obj, bevel, CHAMFER if chamfer is None else chamfer)
            objs.append(obj)
        select_only(objs)
        bpy.ops.object.join()
        obj = bpy.context.object
        obj.name = obj.data.name = name
        for p in obj.data.polygons:
            p.use_smooth = True
        bpy.ops.object.shade_smooth_by_angle(angle=SHARP)
        return obj


# ---------------------------------------------------------------------------
# materials, finishing, bake
# ---------------------------------------------------------------------------
def srgb_to_linear(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def atlas_material():
    m = bpy.data.materials.new(f"Chest_{TIER}")
    m.use_nodes = True
    if not (TEX / f"chest-{TIER}.png").exists():
        raise SystemExit(f"missing textures/chest-{TIER}.png; run author_textures.py {TIER} first")
    return m


def glow_material(key):
    m = bpy.data.materials.new(f"Chest_{TIER}_{key}")
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (0, 0, 0, 1)   # emission alone = exact Neon colour
    bs.inputs["Emission Color"].default_value = (*[srgb_to_linear(c) for c in LOOK[key]], 1)
    bs.inputs["Emission Strength"].default_value = 1.0
    return m


def select_only(objs, active=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def weld_and_bevel(obj, bevel, chamfer):
    """Weld one piece, then give it a soft chamfer scaled to its size."""
    select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=1e-5)
    bpy.ops.object.mode_set(mode="OBJECT")
    if not bevel or chamfer <= 0:
        return
    xs = [v.co for v in obj.data.vertices]
    span = min(max(c[i] for c in xs) - min(c[i] for c in xs) for i in range(3))
    width = min(chamfer, 0.3 * span) if span > 1e-3 else chamfer   # flat pieces: edges only
    bev = obj.modifiers.new("Soft_worn_edge_chamfer", "BEVEL")
    bev.width = width
    bev.segments = 1
    bev.limit_method = "ANGLE"
    bev.angle_limit = math.radians(32)
    bpy.ops.object.modifier_apply(modifier=bev.name)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.dissolve_degenerate(threshold=1e-5)
    bpy.ops.object.mode_set(mode="OBJECT")


# Tier files may override any of these in a BAKE dict.
BAKE_DEFAULTS = {
    "key_dir": (-0.45, -0.6, 0.75), "key_lo": 0.62, "key_hi": 1.18,   # per-facet key light
    "ao_distance": 0.45, "ao_lo": 0.42,                                # crease darkening
    "height_lo": 0.80, "height_hi": 1.06,                              # darker toward the ground
    "rim_dir": (0.75, 0.55, 0.15), "rim": 0.16, "rim_color": (0.45, 0.62, 1.0),
    "edge": 0.62, "edge_radius": 0.07, "edge_tint": (1.0, 0.93, 0.8), "edge_tint_mix": 0.55,
}


def bake(mat, objs, top):
    """Paint icon-style lighting into a texture on fresh unique UVs (see module docstring)."""
    P = dict(BAKE_DEFAULTS, **getattr(T, "BAKE", {}))
    for o in objs:
        uv = o.data.uv_layers.new(name="BakeUV")
        o.data.uv_layers.active = uv
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.004, correct_aspect=True)
    bpy.ops.uv.pack_islands(rotate=True, margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")

    nt = mat.node_tree
    nt.nodes.clear()
    N = nt.nodes.new
    L = nt.links.new
    uvsrc = N("ShaderNodeUVMap"); uvsrc.uv_map = "UVMap"
    tex = N("ShaderNodeTexImage"); tex.image = bpy.data.images.load(str(TEX / f"chest-{TIER}.png")); tex.interpolation = "Linear"
    L(uvsrc.outputs["UV"], tex.inputs["Vector"])
    geo = N("ShaderNodeNewGeometry")

    def dot_light(direction):
        d = N("ShaderNodeVectorMath"); d.operation = "DOT_PRODUCT"
        L(geo.outputs["True Normal"], d.inputs[0])
        d.inputs[1].default_value = Vector(direction).normalized()
        c = N("ShaderNodeClamp")
        L(d.outputs["Value"], c.inputs["Value"])
        return c.outputs["Result"]

    def remap(sock, a, b, lo, hi):
        r = N("ShaderNodeMapRange")
        r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = a, b
        r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = lo, hi
        L(sock, r.inputs["Value"])
        return r.outputs["Result"]

    key = remap(dot_light(P["key_dir"]), 0, 1, P["key_lo"], P["key_hi"])
    ao = N("ShaderNodeAmbientOcclusion"); ao.samples = 16; ao.inputs["Distance"].default_value = P["ao_distance"]
    aof = remap(ao.outputs["AO"], 0.15, 1.0, P["ao_lo"], 1.0)
    sep = N("ShaderNodeSeparateXYZ"); L(geo.outputs["Position"], sep.inputs["Vector"])
    height = remap(sep.outputs["Z"], 0.0, max(top, 1.0), P["height_lo"], P["height_hi"])
    shade = N("ShaderNodeMath"); shade.operation = "MULTIPLY"; L(key, shade.inputs[0]); L(aof, shade.inputs[1])
    shade2 = N("ShaderNodeMath"); shade2.operation = "MULTIPLY"; L(shade.outputs[0], shade2.inputs[0]); L(height, shade2.inputs[1])
    lit = N("ShaderNodeMix"); lit.data_type = "RGBA"; lit.blend_type = "MULTIPLY"; lit.inputs["Factor"].default_value = 1.0
    L(tex.outputs["Color"], lit.inputs[6])
    grey = N("ShaderNodeCombineColor")
    for i in range(3):
        L(shade2.outputs[0], grey.inputs[i])
    L(grey.outputs["Color"], lit.inputs[7])
    rim = remap(dot_light(P["rim_dir"]), 0.2, 1.0, 0.0, P["rim"])
    rimadd = N("ShaderNodeMix"); rimadd.data_type = "RGBA"; rimadd.blend_type = "ADD"
    L(rim, rimadd.inputs["Factor"]); L(lit.outputs[2], rimadd.inputs[6]); rimadd.inputs[7].default_value = (*P["rim_color"], 1)
    bev = N("ShaderNodeBevel"); bev.samples = 8; bev.inputs["Radius"].default_value = P["edge_radius"]
    ed = N("ShaderNodeVectorMath"); ed.operation = "DOT_PRODUCT"
    L(bev.outputs["Normal"], ed.inputs[0]); L(geo.outputs["True Normal"], ed.inputs[1])
    edge = remap(ed.outputs["Value"], 0.985, 0.80, 0.0, P["edge"])
    edge_up = N("ShaderNodeMath"); edge_up.operation = "MULTIPLY"
    L(edge, edge_up.inputs[0]); L(remap(dot_light((-0.3, -0.35, 0.9)), 0, 1, 0.45, 1.0), edge_up.inputs[1])
    tint = N("ShaderNodeMix"); tint.data_type = "RGBA"; tint.inputs["Factor"].default_value = P["edge_tint_mix"]
    L(tex.outputs["Color"], tint.inputs[6]); tint.inputs[7].default_value = (*P["edge_tint"], 1)
    final = N("ShaderNodeMix"); final.data_type = "RGBA"
    L(edge_up.outputs[0], final.inputs["Factor"]); L(rimadd.outputs[2], final.inputs[6]); L(tint.outputs[2], final.inputs[7])
    em = N("ShaderNodeEmission"); L(final.outputs[2], em.inputs["Color"])
    out = N("ShaderNodeOutputMaterial"); L(em.outputs["Emission"], out.inputs["Surface"])

    img = bpy.data.images.new(f"chest-{TIER}-baked", BAKE_SIZE, BAKE_SIZE, alpha=False)
    target = N("ShaderNodeTexImage"); target.image = img
    nt.nodes.active = target
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 32
    scene.render.bake.margin = 12
    select_only(objs)
    bpy.ops.object.bake(type="EMIT")
    path = TEX / f"chest-{TIER}-baked.png"
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()

    # Final material: the baked texture only, on the unique UVs (Roblox reads UV channel 1).
    nt.nodes.clear()
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Roughness"].default_value = 0.78
    bs.inputs["Specular IOR Level"].default_value = 0.15
    tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = img
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    for o in objs:
        o.data.uv_layers.remove(o.data.uv_layers["UVMap"])
        o.data.uv_layers["BakeUV"].name = "UVMap"
    return path


def set_origin(obj, point):
    offset = Vector(point)
    obj.data.transform(Matrix.Translation(-offset))
    obj.location = offset


# ---------------------------------------------------------------------------
# what a tier's build(k) gets
# ---------------------------------------------------------------------------
K = SimpleNamespace(
    Builder=Builder, Vector=Vector, math=math, offset_profile=offset_profile,
    primary_uv=primary_uv, band_uv=band_uv, metal_uv=metal_uv, swatch_uv=swatch_uv,
    metal=metal, swatch=swatch, dark=swatch("keyhole"), gem=swatch("gem"),
    BANDS=BANDS,
)

# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
KINDS = ("textured", "glow", "floor", "accent")
bpy.ops.wm.read_factory_settings(use_empty=True)
atlas = atlas_material()
mats = {"glow": glow_material("glow"), "accent": glow_material("accent")}
spec = T.build(K)
parts, kinds = {}, {}
for name, (builder, kind) in spec["parts"].items():
    assert kind in KINDS, f"{name}: kind must be one of {KINDS}"
    mat = atlas if kind == "textured" else mats["accent" if kind == "accent" else "glow"]
    if isinstance(builder, bpy.types.Object):
        # Escape hatch: a tier may model a part with full Blender tools (bmesh, modifiers,
        # curves...) and hand over a finished mesh object. It must carry a "UVMap" layer
        # addressing the painted atlas (primary_uv / band_uv / metal_uv / swatch_uv) and
        # be modelled at final size with its bevels already applied.
        obj = builder
        obj.name = obj.data.name = name
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        if "UVMap" not in obj.data.uv_layers:
            raise SystemExit(f"{name}: hand-built part needs a 'UVMap' layer")
        parts[name] = obj
    else:
        parts[name] = builder.build(name, mat, bevel=(kind == "textured"))
    kinds[name] = kind
textured = [o for n, o in parts.items() if kinds[n] == "textured"]
bpy.context.view_layer.update()
TOP = max((o.matrix_world @ Vector(c)).z for o in parts.values() for c in o.bound_box)
baked_path = bake(atlas, textured, TOP)

# Opening: every part whose name starts with Chest_Lid moves together. A hinge rotates
# them about X (front lifts); a lift raises them straight up (floating lids); both may combine.
HINGE = spec.get("hinge")
OPEN = dict({"rotate_x_deg": 105.0, "lift": 0.0}, **spec.get("open", {}))
movers = [o for n, o in parts.items() if n.startswith("Chest_Lid")]
if HINGE:
    for o in movers:
        set_origin(o, HINGE)
home = {o.name: o.location.copy() for o in movers}


def pose(open_):
    for o in movers:
        o.rotation_euler = (math.radians(-OPEN["rotate_x_deg"]) if open_ and HINGE else 0.0, 0, 0)
        o.location = home[o.name] + Vector((0, 0, OPEN["lift"] if open_ else 0.0))
    for n, o in parts.items():
        if kinds[n] == "glow":
            o.hide_render = open_          # the seam light fades out as the chest opens in game


# ---------------------------------------------------------------------------
# preview renders (Eevee, bright soft daylight like the lobby)
# ---------------------------------------------------------------------------
scene = bpy.context.scene
for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.render.resolution_x, scene.render.resolution_y = 1400, 1050
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("Sky")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.52, 0.70, 0.92, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
scene.world = world
bpy.ops.object.light_add(type="SUN", location=(0, 0, 20))
sun = bpy.context.object
sun.data.energy = 3.2
sun.data.angle = math.radians(12)
sun.data.color = (1.0, 0.96, 0.88)
sun.rotation_euler = (math.radians(48), 0, math.radians(-38))
bpy.ops.mesh.primitive_circle_add(vertices=48, radius=14, fill_type="NGON", location=(0, 0, 0))
floor = bpy.context.object
floor.name = "Preview_Floor"
fm = bpy.data.materials.new("Preview_Floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.44, 0.45, 1)
floor.data.materials.append(fm)
# Optional tier preview lights, e.g. the blue glow spilling from a magic chest. Blender
# preview only; the report lists them so the same PointLights can be placed in Studio.
for pos, col, watts in getattr(T, "LIGHTS", []):
    bpy.ops.object.light_add(type="POINT", location=pos)
    L_ = bpy.context.object
    L_.data.energy = watts
    L_.data.color = tuple(c / 255 for c in col)
    L_.data.shadow_soft_size = 0.4
bpy.ops.object.camera_add()
cam = bpy.context.object
cam.data.lens = 50
scene.camera = cam


def shoot(filename, location, target=(0, 0, 2.5), open_=False):
    """Camera framed for the Wooden chest (6.5 wide, 5.4 tall); pulls back in proportion
    for bigger chests so wings, crowns and floating crystals stay in frame."""
    pose(open_)
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in parts.values() for c in o.bound_box]
    top = max(p.z for p in pts)
    wide = max(max(abs(p.x) for p in pts) * 2, max(abs(p.y) for p in pts) * 2)
    grow = max(1.0, top / 5.4, wide / 6.8)
    target = Vector(target) * Vector((1, 1, max(1.0, top / 5.4)))
    location = target + (Vector(location) - Vector((0, 0, 2.5))) * grow
    cam.location = Vector(location)
    cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(ROOT / "previews" / filename)
    bpy.ops.render.render(write_still=True)


shoot(f"{TIER}-closed.png", (-9.0, -14.5, 7.8))
shoot(f"{TIER}-open.png", (-9.0, -14.5, 8.8), open_=True)
shoot(f"{TIER}-front.png", (0, -16, 3.4), target=(0, 0, 2.6))
pose(False)

# ---------------------------------------------------------------------------
# export + report
# ---------------------------------------------------------------------------
roles = {
    "textured": f"MeshPart, TextureID = textures/{baked_path.name}",
    "glow": "Neon, GLOW colour; fade out as the chest opens",
    "floor": "Neon, GLOW colour; seen when open",
    "accent": "Neon, ACCENT colour; always on",
}
report = {"tier": TIER, "name": getattr(T, "NAME", TIER), "blender_version": bpy.app.version_string,
          "authoring": "final Roblox stud size; import at 1:1, do not scale",
          "hinge_studs": [round(v, 3) for v in HINGE] if HINGE else None,
          "open": OPEN, "moves_when_opening": [o.name for o in movers],
          "glow_srgb": list(LOOK["glow"]), "accent_srgb": list(LOOK["accent"]),
          "texture": f"textures/{baked_path.name} ({BAKE_SIZE}x{BAKE_SIZE}, baked lighting)",
          "preview_lights": [{"pos": list(p_), "srgb": list(c_), "watts": w_} for p_, c_, w_ in getattr(T, "LIGHTS", [])],
          "parts": {}}
for n, o in parts.items():
    o.data.calc_loop_triangles()
    uv = o.data.uv_layers.active.data
    us = [d.uv.x for d in uv]
    vs = [d.uv.y for d in uv]
    report["parts"][n] = {
        "role": roles[kinds[n]],
        "triangles": len(o.data.loop_triangles), "vertices": len(o.data.vertices),
        "dimensions_studs": [round(v, 3) for v in o.dimensions],
        "uv_range": [round(min(us), 4), round(max(us), 4), round(min(vs), 4), round(max(vs), 4)],
    }
report["total_triangles"] = sum(p["triangles"] for p in report["parts"].values())

if not PREVIEW:
    stem = f"chest-{TIER}"
    select_only(list(parts.values()), textured[0])
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "exports/glb" / f"{stem}.glb"), export_format="GLB",
                              use_selection=True, export_apply=True)
    bpy.ops.export_scene.fbx(filepath=str(ROOT / "exports/fbx" / f"{stem}.fbx"), use_selection=True,
                             object_types={"MESH"}, axis_forward="-Z", axis_up="Y", path_mode="COPY",
                             embed_textures=True, add_leaf_bones=False)
    (ROOT / f"polygon-report-{TIER}.json").write_text(json.dumps(report, indent=2))
    floor.hide_render = True
    for im in bpy.data.images:
        if im.source == "FILE" or im.is_dirty:
            im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / f"chest-{TIER}.blend"))

print("CHEST_READY", TIER, report["total_triangles"], json.dumps({n: p["triangles"] for n, p in report["parts"].items()}), flush=True)
