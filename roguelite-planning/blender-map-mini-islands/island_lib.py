"""Shared helpers for the map-select mini islands.

Each map has its own build_<map>.py that imports this module. Everything here is
self-contained (no exec of sibling kits). The only outside inputs are exported
GLB masters (evergreen, log, palm, ...) which are imported as geometry.

Conventions
- 1 Blender unit = 1 Roblox stud. Island origin = centre of the top surface, z=0.
- Camera looks from -Y towards +Y, so "back" of the island is +Y.
- Every procedural object has its transform applied, so Object-space texture
  coordinates equal world coordinates and texel density matches across parts
  (and survives joining for the atlas bake).
"""
import bpy
import bmesh
import math
import random
import time
import json
from pathlib import Path
from mathutils import Vector, Matrix, noise

BLENDER_ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# scene
# ---------------------------------------------------------------------------
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "NONE"
    return scene


def link(obj, collection=None):
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def collection(name):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    return col


def srgb(hex_or_rgb):
    """'#aabbcc' or (r,g,b) 0-255 -> linear RGBA tuple for shader sockets."""
    if isinstance(hex_or_rgb, str):
        h = hex_or_rgb.lstrip("#")
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    else:
        rgb = [c / 255 for c in hex_or_rgb]

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (lin(rgb[0]), lin(rgb[1]), lin(rgb[2]), 1.0)


# ---------------------------------------------------------------------------
# painterly materials
# ---------------------------------------------------------------------------
PAINT_MATERIALS = []


def paint_mat(name, stops, blob=6.0, jitter=0.35, facing=0.8, rough=0.9,
              emission=None, emission_strength=0.0):
    """Stylised painterly material.

    `stops` is a list of (position, colour) for a colour ramp keyed on a mix of
    face orientation (down = 0, up = 1) and a broad, distorted noise. Result:
    broad 2-4 value patches, lighter tops, cooler undersides, no micro noise.
    `blob` is the patch size in studs; `facing` weights orientation vs noise.
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = 0.15

    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1 / blob, 1 / blob, 1 / blob)
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])

    nz = nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 1.5
    nz.inputs["Roughness"].default_value = 0.45
    nz.inputs["Distortion"].default_value = 0.9
    links.new(mapping.outputs["Vector"], nz.inputs["Vector"])

    geo = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Normal"], sep.inputs["Vector"])

    # facing term 0..1
    face = nodes.new("ShaderNodeMapRange")
    face.inputs["From Min"].default_value = -1.0
    face.inputs["From Max"].default_value = 1.0
    links.new(sep.outputs["Z"], face.inputs["Value"])

    # noise term centred on 0
    nsub = nodes.new("ShaderNodeMath")
    nsub.operation = "SUBTRACT"
    nsub.inputs[1].default_value = 0.5
    links.new(nz.outputs["Fac"], nsub.inputs[0])
    nmul = nodes.new("ShaderNodeMath")
    nmul.operation = "MULTIPLY"
    nmul.inputs[1].default_value = jitter * 2.0
    links.new(nsub.outputs[0], nmul.inputs[0])

    fmul = nodes.new("ShaderNodeMath")
    fmul.operation = "MULTIPLY"
    fmul.inputs[1].default_value = facing
    links.new(face.outputs["Result"], fmul.inputs[0])
    fadd = nodes.new("ShaderNodeMath")
    fadd.operation = "ADD"
    fadd.inputs[1].default_value = (1 - facing) * 0.5
    links.new(fmul.outputs[0], fadd.inputs[0])

    total = nodes.new("ShaderNodeMath")
    total.operation = "ADD"
    total.use_clamp = True
    links.new(fadd.outputs[0], total.inputs[0])
    links.new(nmul.outputs[0], total.inputs[1])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "EASE"
    els = ramp.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position = stops[0][0]
    els[0].color = srgb(stops[0][1])
    for pos, col in stops[1:]:
        e = els.new(pos)
        e.color = srgb(col)
    links.new(total.outputs[0], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = srgb(emission)
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    PAINT_MATERIALS.append(m)
    return m


# ---------------------------------------------------------------------------
# mesh helpers
# ---------------------------------------------------------------------------
def bm_to_obj(name, bm, mats, col=None, flat=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    if flat:
        for p in me.polygons:
            p.use_smooth = False
    obj = bpy.data.objects.new(name, me)
    link(obj, col)
    return obj


def transform_bm(bm, loc=(0, 0, 0), rot_z=0.0, scale=(1, 1, 1), rot=None):
    mat = Matrix.Translation(Vector(loc)) @ (rot or Matrix.Rotation(rot_z, 4, "Z")) @ \
        Matrix.Diagonal((*scale, 1.0))
    bmesh.ops.transform(bm, matrix=mat, verts=bm.verts)


def jitter_bm(bm, amount, seed, freq=0.35, axes=(1, 1, 1)):
    for v in bm.verts:
        p = v.co * freq + Vector((seed * 7.13, seed * 3.71, seed * 1.93))
        d = noise.noise_vector(p)
        v.co.x += d.x * amount * axes[0]
        v.co.y += d.y * amount * axes[1]
        v.co.z += d.z * amount * axes[2]


def join(name, objs, col=None):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    obj.data.name = name
    if col is not None:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        col.objects.link(obj)
    return obj


def faces_by_normal(bm, mat_index, min_z=0.7, above=None):
    """Re-assign material on upward faces (e.g. grass caps on rock)."""
    for f in bm.faces:
        if f.normal.z >= min_z and (above is None or f.calc_center_median().z >= above):
            f.material_index = mat_index


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------
def rock(name, size=(3, 3, 2), seed=0, subdiv=1, rough=0.22, mats=(), cap_index=None,
         loc=(0, 0, 0), rot_z=0.0, col=None, sink=0.25):
    """Faceted boulder. size = full extents. Optional grass cap on top faces."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=0.5)
    jitter_bm(bm, rough, seed, freq=1.3)
    # flatten the bottom so it sits on the ground
    for v in bm.verts:
        if v.co.z < -0.25:
            v.co.z = -0.25 + (v.co.z + 0.25) * 0.25
    transform_bm(bm, scale=size)
    zmin = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= zmin + size[2] * sink * 0.5
    bm.normal_update()
    if cap_index is not None:
        top = max(v.co.z for v in bm.verts)
        faces_by_normal(bm, cap_index, 0.72, above=top - size[2] * 0.35)
    transform_bm(bm, loc=loc, rot_z=rot_z)
    return bm_to_obj(name, bm, list(mats), col)


def cliff_block(name, w, d, h, seed=0, mats=(), cap_index=1, loc=(0, 0, 0), rot_z=0.0,
                col=None, taper=0.85, chamfer=0.18):
    """Chunky chamfered rock block (cliff wall piece) with an optional grass cap."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.5],
                              cuts=2, use_grid_fill=True)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=chamfer, segments=1, affect="EDGES",
                    profile=0.5)
    for v in bm.verts:
        t = v.co.z + 0.5
        k = 1.0 - (1.0 - taper) * t
        v.co.x *= k
        v.co.y *= k
    transform_bm(bm, loc=(0, 0, 0.5), scale=(1, 1, 1))
    transform_bm(bm, scale=(w, d, h))
    jitter_bm(bm, min(w, d, h) * 0.09, seed, freq=0.45)
    bm.normal_update()
    if cap_index is not None and len(mats) > cap_index:
        faces_by_normal(bm, cap_index, 0.75, above=h * 0.8)
    transform_bm(bm, loc=loc, rot_z=rot_z)
    return bm_to_obj(name, bm, list(mats), col)


def cyl_bm(bm, r1, r2, h, segs=8, matrix=None, mat_index=0, cap_tris=False, jitter=0.0, seed=0):
    """Add a cylinder/cone standing on z=0 (local), transformed by `matrix`.
    Returns its faces."""
    tmp = bmesh.new()
    bmesh.ops.create_cone(tmp, cap_ends=True, cap_tris=cap_tris, segments=segs,
                          radius1=r1, radius2=r2, depth=h,
                          matrix=Matrix.Translation((0, 0, h / 2)))
    if jitter:
        jitter_bm(tmp, jitter, seed, freq=0.9)
    if matrix is not None:
        bmesh.ops.transform(tmp, matrix=matrix, verts=tmp.verts)
    return merge_bm(bm, tmp, mat_index)


def trs(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    """Matrix from location, XYZ euler (radians) and scale."""
    from mathutils import Euler
    return (Matrix.Translation(Vector(loc)) @ Euler(rot, "XYZ").to_matrix().to_4x4()
            @ Matrix.Diagonal((*scale, 1.0)))


def box_bm(bm, size, loc=(0, 0, 0), rot=None, chamfer=0.0, mat_index=0):
    """Add a (optionally chamfered) box to an existing bmesh. Returns its faces."""
    tmp = bmesh.new()
    bmesh.ops.create_cube(tmp, size=1.0)
    if chamfer > 0:
        # chamfer in unit space relative to the smallest side
        c = min(0.45, chamfer / max(1e-4, min(size)))
        bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=c, segments=1, affect="EDGES", profile=0.5)
    mat = Matrix.Translation(Vector(loc)) @ (rot or Matrix()) @ Matrix.Diagonal((*size, 1.0))
    bmesh.ops.transform(tmp, matrix=mat, verts=tmp.verts)
    return merge_bm(bm, tmp, mat_index)


def merge_bm(bm, other, mat_index=0):
    """Append `other` into `bm` (frees other). Returns the new faces."""
    me = bpy.data.meshes.new("_tmp")
    other.to_mesh(me)
    other.free()
    before = set(bm.faces)
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    new = [f for f in bm.faces if f not in before]
    for f in new:
        f.material_index = mat_index
    return new


# ---------------------------------------------------------------------------
# the floating island body
# ---------------------------------------------------------------------------
def outline_radius(theta, radius, seed, wobble=0.07):
    p = Vector((math.cos(theta) * 1.1, math.sin(theta) * 1.1, seed * 0.37))
    q = Vector((math.cos(theta) * 2.6, math.sin(theta) * 2.6, seed * 0.91 + 5))
    return radius * (1 + wobble * noise.noise(p) + wobble * 0.45 * noise.noise(q))


def island_body(name, radius, depth, seed, top_mat, edge_mat, rock_mat, col=None,
                segs=64, top_rings=9, rock_rings=14, lip=1.4, edge_band=1.6,
                top_bumps=0.35, strata=0.07, spires=10, spire_len=(0.3, 0.8),
                drip_mat=None, drips=18, rim_raise=None, plates=0.2, plate_size=6.0):
    """Floating-island body: top surface, soil/edge band, faceted rock underside
    tapering to a main spire, plus hanging secondary spires and grass drips.

    Materials: 0 = top, 1 = edge band (soil/under-crust), 2 = rock, 3 = drip.
    `rim_raise(theta) -> dz` optionally lifts the outer top ring (bowl rim).
    Returns the object and the outline function for prop placement.
    """
    rng = random.Random(seed)
    bm = bmesh.new()

    def R(theta):
        return outline_radius(theta, radius, seed)

    rings = []
    # top surface rings (centre fan + rings)
    centre = bm.verts.new((0, 0, 0))
    for j in range(1, top_rings + 1):
        t = j / top_rings
        ring = []
        for i in range(segs):
            th = 2 * math.pi * i / segs
            r = R(th) * t
            z = top_bumps * noise.noise(Vector((math.cos(th) * r * 0.08, math.sin(th) * r * 0.08, seed)))
            if rim_raise is not None and t > 0.7:
                z += rim_raise(th) * ((t - 0.7) / 0.3) ** 2
            ring.append(bm.verts.new((math.cos(th) * r, math.sin(th) * r, z)))
        rings.append(("top", ring))
    top_z_edge = [v.co.z for v in rings[-1][1]]

    # lip: slight outward roll then the edge band
    band = []
    for i in range(segs):
        th = 2 * math.pi * i / segs
        r = R(th) * 1.012
        band.append(bm.verts.new((math.cos(th) * r, math.sin(th) * r, top_z_edge[i] - lip * 0.45)))
    rings.append(("edge", band))
    band2 = []
    for i in range(segs):
        th = 2 * math.pi * i / segs
        r = R(th) * 0.995
        band2.append(bm.verts.new((math.cos(th) * r, math.sin(th) * r, min(top_z_edge[i], 0) - lip - edge_band)))
    rings.append(("rock", band2))

    # rock underside
    body_top = -lip - edge_band
    for k in range(1, rock_rings + 1):
        t = k / rock_rings
        z = body_top - t * (depth - (lip + edge_band))
        shrink = 0.97 - 0.80 * t ** 1.25
        ledge = strata if k % 2 == 0 else -strata * 0.5
        ring = []
        for i in range(segs):
            th = 2 * math.pi * i / segs
            n = noise.noise(Vector((math.cos(th) * 2.2, math.sin(th) * 2.2, k * 0.55 + seed)))
            zz = z + 0.9 * noise.noise(Vector((math.cos(th) * 3, math.sin(th) * 3, k + seed * 2)))
            # cell noise pushes whole blocks in/out together -> stepped stone plates
            cp = Vector((math.cos(th) * R(th) / plate_size, math.sin(th) * R(th) / plate_size,
                         zz / (plate_size * 0.7) + seed))
            plate = noise.cell(cp) - 0.5
            r = R(th) * max(0.04, shrink * (1 + ledge + 0.07 * n + plates * plate))
            # never let a ledge poke out past the soil band above it
            r = min(r, R(th) * (0.975 - 0.25 * t))
            ring.append(bm.verts.new((math.cos(th) * r, math.sin(th) * r, zz)))
        rings.append(("rock", ring))
    tip = bm.verts.new((radius * 0.05, radius * -0.04, -depth - radius * 0.35))

    # faces
    for i in range(segs):
        f = bm.faces.new((centre, rings[0][1][i], rings[0][1][(i + 1) % segs]))
        f.material_index = 0
    for (kind_a, a), (kind_b, b) in zip(rings[:-1], rings[1:]):
        # top->top and top->edge (the rounded lip) are top; edge->rock is the
        # soil band; everything below is rock
        mat_idx = 0 if kind_a == "top" else 1 if kind_a == "edge" else 2
        for i in range(segs):
            i2 = (i + 1) % segs
            f = bm.faces.new((a[i], b[i], b[i2], a[i2]))
            f.material_index = mat_idx
    last = rings[-1][1]
    for i in range(segs):
        f = bm.faces.new((last[i], tip, last[(i + 1) % segs]))
        f.material_index = 2
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    # hanging spires
    for s in range(spires):
        th = rng.uniform(0, 2 * math.pi)
        rr = radius * rng.uniform(0.25, 0.55)
        L = depth * rng.uniform(*spire_len)
        base_r = radius * rng.uniform(0.10, 0.17)
        # start inside the underside so the join is hidden
        t_at = min(0.95, rr / radius)
        z_top = body_top - (depth - lip - edge_band) * max(0.0, (1 - rr / (radius * 0.97)) ** (1 / 1.25)) * 0.9 + 1.0
        z_top = min(z_top, body_top - 2.0)
        geom = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=6,
                                     radius1=base_r, radius2=0.0, depth=L,
                                     matrix=Matrix.Translation((math.cos(th) * rr, math.sin(th) * rr, z_top - L / 2))
                                     @ Matrix.Rotation(math.pi, 4, "X"))
        vs = geom["verts"]
        for v in vs:
            d = noise.noise_vector(v.co * 0.3 + Vector((s, seed, 0)))
            v.co.x += d.x * base_r * 0.25
            v.co.y += d.y * base_r * 0.25
        for f in {f for v in vs for f in v.link_faces}:
            f.material_index = 2

    # grass drips over the lip
    if drip_mat is not None and drips:
        for s in range(drips):
            th = 2 * math.pi * (s + rng.uniform(-0.3, 0.3)) / drips
            r = R(th) * 1.01
            L = rng.uniform(1.2, 2.8)
            w = rng.uniform(0.9, 1.8)
            # flattened downward cone hugging the band (thin radially, wide tangentially)
            m = (Matrix.Translation((math.cos(th) * r, math.sin(th) * r, -lip * 0.3 - L / 2))
                 @ Matrix.Rotation(th, 4, "Z")
                 @ Matrix.Rotation(math.pi, 4, "X")
                 @ Matrix.Diagonal((0.45, 1.0, 1.0, 1.0)))
            geom = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=4,
                                         radius1=w, radius2=0.0, depth=L, matrix=m)
            for f in {f for v in geom["verts"] for f in v.link_faces}:
                f.material_index = 3

    bm.normal_update()
    mats = [top_mat, edge_mat, rock_mat, drip_mat or top_mat]
    obj = bm_to_obj(name, bm, mats, col)
    return obj, R


def top_height(obj, x, y):
    """Ray-cast straight down onto an object's top to find its surface height."""
    deps = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(deps)
    hit, loc, nrm, idx = eo.ray_cast(Vector((x, y, 200)), Vector((0, 0, -1)))
    return loc.z if hit else 0.0


# ---------------------------------------------------------------------------
# imported masters (trees, logs, ...)
# ---------------------------------------------------------------------------
def import_master(glb_path, name, hide=True):
    """Import a single-mesh GLB master and return its object (kept out of render)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    assert meshes, f"no mesh in {glb_path}"
    master = meshes[0] if len(meshes) == 1 else join(name, meshes)
    master.name = name
    master.parent = None
    bpy.context.view_layer.update()
    master.matrix_world = Matrix()
    for o in new:
        if o is not master and o.name in bpy.data.objects and o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    if hide:
        master.hide_render = True
        master.hide_viewport = True
    return master


def place_instance(master, name, loc, rot_z=0.0, scale=1.0, col=None, tilt=(0.0, 0.0)):
    inst = master.copy()
    # own mesh datablock (same material + texture): the FBX exporter drops the
    # material from every object after the first that shares one mesh
    inst.data = master.data.copy()
    inst.name = name
    inst.data.name = name
    inst.hide_render = False
    inst.hide_viewport = False
    inst.location = loc
    inst.rotation_euler = (tilt[0], tilt[1], rot_z)
    inst.scale = (scale, scale, scale)
    for c in list(inst.users_collection):
        c.objects.unlink(inst)
    link(inst, col)
    return inst


# ---------------------------------------------------------------------------
# bake procedural parts to one atlas
# ---------------------------------------------------------------------------
def bake_atlas(obj, image_path, size=2048, margin=12):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    scene.cycles.device = "CPU"
    scene.render.bake.use_pass_direct = False
    scene.render.bake.use_pass_indirect = False

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    uv = obj.data.uv_layers.new(name="AtlasUV")
    obj.data.uv_layers.active = uv
    uv.active_render = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")

    img = bpy.data.images.new(obj.name + "_Color", width=size, height=size, alpha=False)
    img.filepath_raw = str(image_path)
    img.file_format = "PNG"
    used = [m for m in obj.data.materials if m is not None]
    for m in used:
        node = m.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        m.node_tree.nodes.active = node
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=margin, use_clear=True)
    for attempt in range(6):
        try:
            img.save()
            break
        except RuntimeError:
            if attempt == 5:
                raise
            time.sleep(1.0)
    # Emission (e.g. fire) is lost in a DIFFUSE bake; keep a per-face emissive
    # flag so the baked material can still glow in previews.
    baked = bpy.data.materials.new(obj.name + "_Atlas")
    baked.use_nodes = True
    bs = baked.node_tree.nodes["Principled BSDF"]
    bs.inputs["Roughness"].default_value = 0.9
    bs.inputs["Specular IOR Level"].default_value = 0.12
    tx = baked.node_tree.nodes.new("ShaderNodeTexImage")
    tx.image = img
    uvn = baked.node_tree.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "AtlasUV"
    baked.node_tree.links.new(uvn.outputs["UV"], tx.inputs["Vector"])
    baked.node_tree.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    for m in used:
        for n in [n for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image == img]:
            m.node_tree.nodes.remove(n)
    obj.data.materials.clear()
    obj.data.materials.append(baked)
    for p in obj.data.polygons:
        p.material_index = 0
    for layer in list(obj.data.uv_layers):
        if layer.name != "AtlasUV":
            obj.data.uv_layers.remove(layer)
    return img


# ---------------------------------------------------------------------------
# preview rendering
# ---------------------------------------------------------------------------
def setup_preview(sky_top="#78aee0", sky_horizon="#cfe3f1", sun_energy=3.6,
                  sun_rot=(0.75, -0.25, -0.55), sun_color="#fff1dc", fill=0.62):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    try:
        scene.eevee.taa_render_samples = 64
    except AttributeError:
        pass

    world = bpy.data.worlds.new("PreviewSky")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sepx = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = srgb(sky_horizon)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = srgb(sky_top)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1
    mr.inputs["From Max"].default_value = 1
    nt.links.new(tc.outputs["Generated"], sepx.inputs["Vector"])
    nt.links.new(sepx.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = fill
    # camera sees the sky at full brightness; lighting uses the dimmer `fill`
    cam_bg = nt.nodes.new("ShaderNodeBackground")
    cam_bg.inputs["Strength"].default_value = 1.0
    nt.links.new(ramp.outputs["Color"], cam_bg.inputs["Color"])
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg.outputs["Background"], mix.inputs[1])
    nt.links.new(cam_bg.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], nt.nodes["World Output"].inputs["Surface"])

    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = sun_energy
    sun_data.angle = math.radians(8)
    sun_data.color = srgb(sun_color)[:3]
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = sun_rot
    link(sun)
    return scene


def camera(name, loc, target, lens=50):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam_data.clip_end = 4000
    cam = bpy.data.objects.new(name, cam_data)
    link(cam)
    cam.location = loc
    direction = Vector(target) - Vector(loc)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return cam


def render(cam, path):
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


# ---------------------------------------------------------------------------
# reports / export
# ---------------------------------------------------------------------------
def tri_count(obj):
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)


def export(objs, fbx_path, glb_path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_viewport = False
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB",
                              use_selection=True, export_apply=True)
    bpy.ops.export_scene.fbx(filepath=str(fbx_path), use_selection=True,
                             object_types={"MESH"}, axis_forward="-Z", axis_up="Y",
                             path_mode="COPY", embed_textures=True, add_leaf_bones=False,
                             apply_scale_options="FBX_SCALE_ALL")
