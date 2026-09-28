"""Run: blender --background --python roguelite-planning/heart-pickup/generate_heart_pickup.py

Original faceted heart pickup built from the in-game HUD heart icon
(studio-prototype/ui/assets/heart.svg, asset 101432943753406): the same 12-point
silhouette, the same two interior facet vertices and the same facet colours,
pushed into a chunky double-sided gem. Self-contained; reads only heart.svg's
numbers (copied below) and writes only this folder.
"""
import bpy, bmesh, json, math, hashlib
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
SVG = OUT.parent / "studio-prototype" / "ui" / "assets" / "heart.svg"
(OUT / "exports" / "fbx").mkdir(parents=True, exist_ok=True)
(OUT / "exports" / "glb").mkdir(parents=True, exist_ok=True)
(OUT / "textures").mkdir(exist_ok=True)
(OUT / "previews").mkdir(exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# heart.svg red body polygon (px, 256 viewBox), clockwise from the top notch.
SILHOUETTE = [(127, 66), (164, 34), (196, 36), (219, 61), (228, 97), (207, 136),
              (129, 215), (50, 157), (28, 104), (37, 68), (58, 49), (88, 49)]
# Interior facet vertices: the svg's two shared corners plus the highlight lobe peak.
INTERIOR = {"P": ((105, 108), 0.40), "Q": ((180, 88), 0.36), "L": ((64, 70), 0.28)}
RIM_HALF = 0.07      # half thickness of the soft side band
BACK_DEPTH = 0.85    # back face is slightly flatter than the front

# heart.svg facet fills (sRGB hex).
COLORS = {"A": "ff5b57", "HL": "ffaaa0", "B": "ff4547", "C": "ff7771",
          "DARK": "c91721", "D": "ef2630", "E": "e03339"}
# Triangles per svg facet, using silhouette indices 0-11 and interior names.
FRONT = [
    ((9, 10, "L"), "HL"), ((10, 11, "L"), "A"), ((11, 0, "L"), "A"),
    ((0, "P", "L"), "A"), (("P", 8, "L"), "A"), ((8, 9, "L"), "A"),
    ((0, 1, "Q"), "B"), ((1, 2, "Q"), "B"), ((0, "Q", "P"), "B"),
    ((2, 3, "Q"), "C"), ((3, 4, "Q"), "C"),
    ((4, 5, "Q"), "DARK"),
    (("P", "Q", 5), "D"), (("P", 5, 6), "D"),
    ((8, "P", 7), "E"), (("P", 6, 7), "E"),
]


def svg_point(px, py):
    # 100 px -> 1 unit, centred on the viewBox, y up. Blender: X right, Z up, front is -Y.
    return (px - 128) / 100, (128 - py) / 100


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


verts, index = [], {}
for side, sign in (("F", -1), ("B", 1)):
    for i, (px, py) in enumerate(SILHOUETTE):
        x, z = svg_point(px, py)
        index[(side, i)] = len(verts)
        verts.append((x, sign * RIM_HALF, z))
    for name, ((px, py), depth) in INTERIOR.items():
        x, z = svg_point(px, py)
        index[(side, name)] = len(verts)
        verts.append((x, sign * (RIM_HALF + depth * (1 if side == "F" else BACK_DEPTH)), z))

faces, face_colors = [], []
for tri, color in FRONT:
    faces.append(tuple(index[("F", k)] for k in tri)); face_colors.append(color)
    faces.append(tuple(index[("B", k)] for k in reversed(tri))); face_colors.append(color)
n = len(SILHOUETTE)
for i in range(n):
    j = (i + 1) % n
    faces.append((index[("F", i)], index[("B", i)], index[("B", j)], index[("F", j)]))
    face_colors.append("DARK")

mesh = bpy.data.meshes.new("HeartPickupGeometry")
mesh.from_pydata(verts, [], faces)
mesh.update()
obj = bpy.data.objects.new("HeartPickup", mesh)
scene.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bm = bmesh.new(); bm.from_mesh(mesh)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(mesh); bm.free()

# Per-facet painted materials: broad low-noise value breakup, 2-3 value steps (art direction).
palette_names = list(COLORS)
for name in palette_names:
    lin = tuple(srgb_to_linear(c) for c in hex_rgb(COLORS[name]))
    mat = bpy.data.materials.new("HeartFacet_" + name)
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.inputs["Roughness"].default_value = 0.42
    noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 2.4; noise.inputs["Detail"].default_value = 1.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25; ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[0].color = tuple(c * 0.88 for c in lin) + (1,)
    ramp.color_ramp.elements[1].color = tuple(min(1, c * 1.05) for c in lin) + (1,)
    nt.links.new(noise.outputs["Fac"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    mesh.materials.append(mat)
for poly, color in zip(mesh.polygons, face_colors):
    poly.material_index = palette_names.index(color)

# Tiny chamfer keeps the facets crisp but catches a highlight on every edge.
bevel = obj.modifiers.new("Soft edge chamfer", "BEVEL"); bevel.width = 0.014; bevel.segments = 1
bpy.ops.object.modifier_apply(modifier=bevel.name)
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(island_margin=0.03); bpy.ops.object.mode_set(mode="OBJECT")
for poly in mesh.polygons:
    poly.use_smooth = False

# Bake the painted facets into one base-colour map (Roblox MeshPart.TextureID).
scene.render.engine = "CYCLES"; scene.cycles.samples = 1; scene.cycles.device = "CPU"
img = bpy.data.images.new("HeartPickup_BaseColor", width=512, height=512, alpha=False)
for mat in mesh.materials:
    node = mat.node_tree.nodes.new("ShaderNodeTexImage"); node.image = img
    mat.node_tree.nodes.active = node; node.select = True
bake = scene.render.bake
bake.use_pass_direct = False; bake.use_pass_indirect = False; bake.use_pass_color = True; bake.margin = 8
bpy.ops.object.bake(type="DIFFUSE")
texture_path = OUT / "textures" / "HeartPickup_BaseColor.png"
img.filepath_raw = str(texture_path); img.file_format = "PNG"; img.save()

final = bpy.data.materials.new("HeartPickup_Painted"); final.use_nodes = True
bsdf = final.node_tree.nodes.get("Principled BSDF"); bsdf.inputs["Roughness"].default_value = 0.42
tex = final.node_tree.nodes.new("ShaderNodeTexImage"); tex.image = img
final.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
mesh.materials.clear(); mesh.materials.append(final)
tri = obj.modifiers.new("Portable triangulation", "TRIANGULATE")
bpy.ops.object.modifier_apply(modifier=tri.name)

bpy.ops.object.select_all(action="DESELECT"); obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT / "exports" / "glb" / "HeartPickup.glb"), export_format="GLB", use_selection=True)
bpy.ops.export_scene.fbx(filepath=str(OUT / "exports" / "fbx" / "HeartPickup.fbx"), use_selection=True,
                         object_types={"MESH"}, apply_unit_scale=True, axis_forward="-Z", axis_up="Y",
                         path_mode="COPY", embed_textures=True)

# Upload-free Roblox fallback data (Y up, front -Z), unchamfered facets and exact svg colours.
data = {
    "source": "studio-prototype/ui/assets/heart.svg",
    "vertices": [[round(x, 5), round(z, 5), round(y, 5)] for x, y, z in verts],
    "faces": [[i + 1 for i in f] for f in faces],
    "colors": [list(int(COLORS[c][k:k + 2], 16) for k in (0, 2, 4)) for c in face_colors],
}
(OUT / "HeartPickupGeometry.json").write_text(json.dumps(data, indent=1))

# Validation: manifold, positive-area triangles, one material, one UV map.
bm = bmesh.new(); bm.from_mesh(mesh)
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
degenerate = sum(1 for f in bm.faces if f.calc_area() <= 1e-9)
bm.free()
dims = list(obj.dimensions)
report = {
    "vertices": len(mesh.vertices), "triangles": len(mesh.polygons),
    "fallback_triangles": sum(len(f) - 2 for f in faces),
    "dimensions_blender_units": [round(d, 4) for d in dims],
    "non_manifold_edges": non_manifold, "degenerate_faces": degenerate,
    "materials": len(mesh.materials), "uv_maps": len(mesh.uv_layers),
    "svg_sha256": hashlib.sha256(SVG.read_bytes()).hexdigest() if SVG.exists() else None,
}
report["passed"] = non_manifold == 0 and degenerate == 0 and report["materials"] == 1 and report["uv_maps"] == 1
(OUT / "validation-report.json").write_text(json.dumps(report, indent=2))


def aim(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


# Presentation only: camera, lights and the outline shell are never exported.
shell = obj.copy(); shell.data = obj.data.copy(); shell.name = "PreviewOutline"
scene.collection.objects.link(shell)
# One inverted layer pushed out along the normals (the classic inverted-hull outline).
sbm = bmesh.new(); sbm.from_mesh(shell.data)
for v in sbm.verts:
    v.co += v.normal * 0.055
bmesh.ops.reverse_faces(sbm, faces=sbm.faces)
sbm.to_mesh(shell.data); sbm.free()
# Cycles ignores backface culling, so hide the shell's near side in the shader:
# only its far, inward-facing side survives, peeking out as the icon's dark border.
black = bpy.data.materials.new("PreviewOutlineBlack"); black.use_nodes = True
bnt = black.node_tree; bnt.nodes.clear()
bout = bnt.nodes.new("ShaderNodeOutputMaterial")
dark = bnt.nodes.new("ShaderNodeEmission"); dark.inputs["Color"].default_value = (0.0027, 0.0030, 0.0033, 1)
clear = bnt.nodes.new("ShaderNodeBsdfTransparent")
geo = bnt.nodes.new("ShaderNodeNewGeometry")
mix = bnt.nodes.new("ShaderNodeMixShader")
bnt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
bnt.links.new(dark.outputs[0], mix.inputs[1]); bnt.links.new(clear.outputs[0], mix.inputs[2])
bnt.links.new(mix.outputs[0], bout.inputs[0])
shell.data.materials.clear(); shell.data.materials.append(black)
# Camera rays only, or the shell would shadow the heart it surrounds.
for flag in ("visible_shadow", "visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter"):
    setattr(shell, flag, False)

scene.world = bpy.data.worlds.new("PreviewWorld"); scene.world.color = (0.16, 0.16, 0.17)
bpy.ops.object.camera_add(location=(2.2, -6.5, 1.3)); cam = bpy.context.object; aim(cam, (0, 0, 0.05))
cam.data.type = "ORTHO"; cam.data.ortho_scale = 2.7; scene.camera = cam
for name, pos, power, size in [("Key", (-3, -4, 5), 420, 5), ("Fill", (4, -2, 2), 240, 4), ("Rim", (1, 4, 3), 380, 3)]:
    bpy.ops.object.light_add(type="AREA", location=pos); light = bpy.context.object
    light.name = name; light.data.energy = power; light.data.shape = "DISK"; light.data.size = size; aim(light, (0, 0, 0))
scene.cycles.samples = 64
scene.render.resolution_x = 900; scene.render.resolution_y = 900; scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.view_settings.view_transform = "Standard"
scene.render.image_settings.file_format = "PNG"


def render(path, cam_loc):
    cam.location = cam_loc; aim(cam, (0, 0, 0.05))
    scene.render.filepath = str(path); bpy.ops.render.render(write_still=True)


render(OUT / "previews" / "HeartPickup_Preview.png", (2.2, -6.5, 1.3))
render(OUT / "previews" / "HeartPickup_Front.png", (0, -7, 0.05))
shell.hide_render = True
render(OUT / "previews" / "HeartPickup_NoOutline.png", (2.2, -6.5, 1.3))
shell.hide_render = False

img.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "HeartPickup.blend"))
print("HEART_PICKUP_COMPLETE", json.dumps(report))
