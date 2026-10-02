"""Legendary weapon VFX meshes (plan J item 8, rarity step 3: the Tier IV Legendary moves).

Run:
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --python generate_legendary_vfx.py

Builds three small vertex-coloured meshes and writes:
  exports/glb/<Name>.glb, exports/fbx/<Name>.fbx   reference exports (Blender-verified)
  ../studio-prototype/combat/LegendaryVisuals/MeshData.luau
      the same meshes as a Luau table in the RocketExplosionVisuals template format
      (v = vertices in Roblox space, f = 1-based triangles, c = one linear colour per face,
      a = alpha per vertex, size = bounds, glow = Neon). LegendaryVisuals builds them on the client
      with EditableMesh, so nothing is uploaded to Roblox.
  previews/legendary-vfx-hero.png, previews/legendary-vfx-top.png   Cycles renders with bloom
  polygon-report.json
Self-contained: no other kit's code is read.

Meshes (unit size; the game scales them):
  SlashCore  the white-hot cutting edge of a flying slash: a thin crescent, convex side forward (-Z)
  SlashGlow  the wide glow behind it, fading to nothing at the back and at both tips
  ShockRing  a ground shockwave: a short band that flares out, with a ragged dusty crown on top
Colour is mostly white so the game can tint per weapon (Katana white/amber, Excalibur gold).
"""
import bpy, json, math, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_LUAU = HERE.parent / "studio-prototype" / "combat" / "LegendaryVisuals" / "MeshData.luau"
for sub in ("exports/glb", "exports/fbx", "previews"):
    (HERE / sub).mkdir(parents=True, exist_ok=True)
OUT_LUAU.parent.mkdir(parents=True, exist_ok=True)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(a, b, t):
    return tuple(lerp(a[i], b[i], t) for i in range(3))


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------------------
# Geometry in Roblox space (X right, Y up, -Z forward). Each mesh: verts, rgba per vert, tris.
# ---------------------------------------------------------------------------
def crescent(segments, half_angle_deg, radius, width, ridge, lead, trail, alpha_lead, alpha_trail, power=1.25):
    """A crescent blade. Rows run from the leading (outer) edge to the trailing (inner) edge;
    a raised ridge on top and bottom gives the edge a faceted, bevelled blade section."""
    A = math.radians(half_angle_deg)
    rows = [(0.0, 0.0), (0.32, ridge), (1.0, 0.0), (0.32, -ridge)]  # (u across the blade, y)
    verts, cols, tris = [], [], []
    for i in range(segments + 1):
        th = -A + 2 * A * i / segments
        w = width * math.cos(th / A * math.pi / 2) ** power  # thick in the middle, a point at each tip
        tip = smooth((1 - abs(th) / A) / 0.28)  # the tips fade out
        for u, y in rows:
            r = radius - u * w
            verts.append((r * math.sin(th), y * (w / width), -r * math.cos(th)))
            c = lerp3(lead, trail, u)
            cols.append((*c, lerp(alpha_lead, alpha_trail, u) * tip))
    n = len(rows)
    for i in range(segments):
        for k in range(n):
            a, b = i * n + k, i * n + (k + 1) % n
            c, d = (i + 1) * n + k, (i + 1) * n + (k + 1) % n
            tris += [(a, c, b), (b, c, d)]
    return verts, cols, tris


def shock_ring(segments=48):
    """A ground shockwave band: radius 1 at the ground, flaring outward as it rises, with a ragged
    crown so it reads as kicked-up dust rather than a clean tube."""
    verts, cols, tris = [], [], []
    rows = [  # (height, radius, colour, alpha)
        (0.00, 1.00, (1.00, 0.95, 0.86), 0.95),
        (0.30, 1.04, (1.00, 0.96, 0.89), 0.80),
        (0.62, 1.10, (1.00, 0.98, 0.93), 0.42),
        (1.00, 1.17, (1.00, 1.00, 1.00), 0.00),
    ]
    for i in range(segments + 1):
        th = 2 * math.pi * i / segments
        crown = 1 + 0.30 * (0.6 * math.sin(5 * th) + 0.4 * math.sin(11 * th + 1.3))
        for k, (h, r, c, a) in enumerate(rows):
            hh = h * (crown if k == len(rows) - 1 else lerp(1, crown, h))
            verts.append((r * math.sin(th), hh, -r * math.cos(th)))
            cols.append((*c, a))
    n = len(rows)
    for i in range(segments):
        for k in range(n - 1):
            a, b = i * n + k, i * n + k + 1
            c, d = (i + 1) * n + k, (i + 1) * n + k + 1
            tris += [(a, c, b), (b, c, d)]
    return verts, cols, tris


MESHES = {
    "SlashCore": dict(data=crescent(36, 78, 1.0, 0.24, 0.045, (1, 1, 1), (1.0, 0.94, 0.74), 1.0, 0.25), glow=True),
    "SlashGlow": dict(data=crescent(36, 86, 1.07, 0.58, 0.02, (1.0, 0.96, 0.80), (1.0, 0.66, 0.16), 0.85, 0.0, 1.05), glow=True),
    "ShockRing": dict(data=shock_ring(), glow=False),
}


# ---------------------------------------------------------------------------
# Luau export (per-face colour = the average of its corners, the template format's rule)
# ---------------------------------------------------------------------------
def f(x):
    return float(f"{x:.5f}")


def luau_table(name, verts, cols, tris, glow):
    xs, ys, zs = zip(*verts)
    size = [f(max(xs) - min(xs)), f(max(ys) - min(ys)), f(max(zs) - min(zs))]
    face_cols = []
    for t in tris:
        face_cols.append([f(sum(cols[i][k] for i in t) / 3) for k in range(3)])
    # The template format stores linear colour (RocketExplosionVisuals converts it to sRGB).
    def to_linear(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    face_cols = [[f(to_linear(c)) for c in fc] for fc in face_cols]
    data = {
        "v": [[f(x) for x in v] for v in verts],
        "f": [[i + 1 for i in t] for t in tris],
        "c": face_cols,
        "a": [f(c[3]) for c in cols],
        "size": size,
        "glow": glow,
    }
    return data


def write_luau():
    tables = {name: luau_table(name, *m["data"], m["glow"]) for name, m in MESHES.items()}

    def lua(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return repr(v) if isinstance(v, int) else (f"{v:.5f}".rstrip("0").rstrip(".") or "0")
        if isinstance(v, list):
            return "{" + ",".join(lua(x) for x in v) + "}"
        if isinstance(v, dict):
            return "{" + ",".join(f"{k}={lua(x)}" for k, x in v.items()) + "}"
        raise TypeError(v)

    lines = [
        "-- Generated by roguelite-planning/blender-legendary-vfx/generate_legendary_vfx.py. Do not edit by hand.",
        "-- Legendary move meshes in the RocketExplosionVisuals template format: v (Roblox space), f (1-based",
        "-- triangles), c (linear colour per face), a (alpha per vertex), size (bounds), glow (Neon).",
        "return {",
    ]
    for name, t in tables.items():
        lines.append(f" {name}={lua(t)},")
    lines.append("}")
    OUT_LUAU.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tables


# ---------------------------------------------------------------------------
# Blender objects, exports and previews
# ---------------------------------------------------------------------------
def to_blender(v):  # Roblox (x, y, z) -> Blender (x, -z, y)
    return (v[0], -v[2], v[1])


def build_object(name, verts, cols, tris):
    me = bpy.data.meshes.new(name)
    me.from_pydata([to_blender(v) for v in verts], [], [tuple(t) for t in tris])
    me.update()
    attr = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    for i, c in enumerate(cols):
        attr.data[i].color = c
    me.color_attributes.active_color = attr
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def glow_material(name, tint, strength, alpha_scale=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "Col"
    mul = nt.nodes.new("ShaderNodeVectorMath"); mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = tint
    emit = nt.nodes.new("ShaderNodeEmission"); emit.inputs["Strength"].default_value = strength
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    scale = nt.nodes.new("ShaderNodeMath"); scale.operation = "MULTIPLY"; scale.inputs[1].default_value = alpha_scale
    nt.links.new(attr.outputs["Color"], mul.inputs[0])
    nt.links.new(mul.outputs[0], emit.inputs["Color"])
    nt.links.new(attr.outputs["Alpha"], scale.inputs[0])
    nt.links.new(scale.outputs[0], mix.inputs["Fac"])
    nt.links.new(transp.outputs[0], mix.inputs[1])
    nt.links.new(emit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def dust_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    attr = nt.nodes.new("ShaderNodeAttribute"); attr.attribute_name = "Col"
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.9
    transp = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(attr.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(transp.outputs[0], mix.inputs[1])
    nt.links.new(bsdf.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def export(ob, name):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=str(HERE / "exports/glb" / f"{name}.glb"), use_selection=True, export_format="GLB")
    bpy.ops.export_scene.fbx(filepath=str(HERE / "exports/fbx" / f"{name}.fbx"), use_selection=True, apply_unit_scale=True)


def setup_render(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 32
    scene.render.resolution_x, scene.render.resolution_y = 1600, 900
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.render.image_settings.file_format = "PNG"
    w = bpy.data.worlds.new("Stage"); scene.world = w; w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.035, 0.04, 0.055, 1); bg.inputs["Strength"].default_value = 1.0
    tree = bpy.data.node_groups.new("LegendaryComp", "CompositorNodeTree")
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = tree.nodes.new("CompositorNodeRLayers")
    out = tree.nodes.new("NodeGroupOutput")
    g = tree.nodes.new("CompositorNodeGlare")
    g.inputs["Type"].default_value = "Bloom"
    g.inputs["Quality"].default_value = "High"
    g.inputs["Threshold"].default_value = 0.6
    g.inputs["Strength"].default_value = 0.6
    g.inputs["Size"].default_value = 0.6
    tree.links.new(rl.outputs["Image"], g.inputs["Image"])
    tree.links.new(g.outputs["Image"], out.inputs[0])
    scene.compositing_node_group = tree


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    tables = write_luau()
    report = {}
    objs = {}
    for name, m in MESHES.items():
        verts, cols, tris = m["data"]
        ob = build_object(name, verts, cols, tris)
        objs[name] = ob
        export(ob, name)
        report[name] = {"vertices": len(verts), "triangles": len(tris), "size_studs_at_scale_1": tables[name]["size"]}
    (HERE / "polygon-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Preview stage: the Katana slash (white core, amber glow), the Excalibur slash (gold) and the
    # shockwave ring, each at a size it has in game (slash 3.4-4.4 studs wide, ring 11 radius scaled down).
    setup_render(scene)
    ground = bpy.data.objects.new("Ground", bpy.data.meshes.new("Ground"))
    ground.data.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
    scene.collection.objects.link(ground)
    gm = bpy.data.materials.new("Ground"); gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.09, 0.13, 0.07, 1)
    ground.data.materials.append(gm)

    def place(name, mat, loc, scale, rot_z=0.0, height=1.0):
        ob = objs[name].copy(); ob.data = objs[name].data.copy()
        scene.collection.objects.link(ob)
        ob.data.materials.clear(); ob.data.materials.append(mat)
        ob.location = loc; ob.scale = (scale, scale, scale * height); ob.rotation_euler = (0, 0, rot_z)
        ob.hide_render = False  # the originals are hidden; a copy inherits that
        return ob

    katana_core = glow_material("KatanaCore", (1, 1, 1), 9)
    katana_glow = glow_material("KatanaGlow", (1.0, 0.78, 0.38), 5)
    exc_core = glow_material("ExcaliburCore", (1.0, 0.92, 0.62), 9)
    exc_glow = glow_material("ExcaliburGlow", (1.0, 0.70, 0.18), 6)
    dust = dust_material("Dust")
    for o in list(objs.values()):
        o.hide_render = True
    place("SlashGlow", katana_glow, (-6, 0, 1.0), 1.75)
    place("SlashCore", katana_core, (-6, 0, 1.0), 1.7)
    place("SlashGlow", exc_glow, (0, 0, 1.0), 2.25)
    place("SlashCore", exc_core, (0, 0, 1.0), 2.2)
    place("ShockRing", dust, (6.5, 0, 0.02), 2.6, height=0.45)

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.0; sun.rotation_euler = (math.radians(50), 0, math.radians(30))
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam); scene.camera = cam
    cam.data.lens = 40

    def shoot(path, loc, target):
        from mathutils import Vector
        cam.location = loc
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)

    shoot(HERE / "previews/legendary-vfx-hero.png", (0.5, -15, 9), (0.3, 0, 0.6))
    shoot(HERE / "previews/legendary-vfx-top.png", (0.3, -3, 21), (0.3, 0, 0))
    bpy.ops.wm.save_as_mainfile(filepath=str(HERE / "legendary-vfx.blend"))
    print("LEGENDARY_VFX_DONE", json.dumps(report))


main()
