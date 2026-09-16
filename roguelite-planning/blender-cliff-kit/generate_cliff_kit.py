"""Generate an original low-poly modular cliff kit for Roblox.

Run with Blender 5.2+:
    blender --background --python generate_cliff_kit.py

The script creates the .blend source, individual FBX/GLB exports, a combined
sample arena export, preview renders, and a machine-readable polygon report.
No external textures or copied reference geometry are used.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
EXPORT_FBX = ROOT / "exports" / "fbx"
EXPORT_GLB = ROOT / "exports" / "glb"
PREVIEWS = ROOT / "previews"
for directory in (EXPORT_FBX, EXPORT_GLB, PREVIEWS):
    directory.mkdir(parents=True, exist_ok=True)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        # Materials are rebuilt below, so clear everything for deterministic runs.
        if datablocks == bpy.data.materials:
            continue


def material(name: str, color: tuple[float, float, float, float], roughness: float = 0.86):
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def ensure_collection(name: str):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    return col


def link_object(obj, collection) -> None:
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    collection.objects.link(obj)


def create_mesh_object(name, verts, faces, collection, materials, face_materials=None):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.validate(verbose=False)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    for mat in materials:
        mesh.materials.append(mat)
    if face_materials:
        for index, poly in enumerate(mesh.polygons):
            poly.material_index = face_materials[index % len(face_materials)]
    for poly in mesh.polygons:
        poly.use_smooth = False
    return obj


def quad_as_tris(faces, a, b, c, d, flip=False):
    if flip:
        faces.extend([(a, b, d), (b, c, d)])
    else:
        faces.extend([(a, b, c), (a, c, d)])


def annular_piece(name, angle_deg=45.0, inner=36.0, depth=8.0, height=10.0, cap=0.65, segments=4):
    """Return rock and cap objects centered on +Y, pivoting around world origin."""
    rock_verts = []
    cap_verts = []
    rock_faces = []
    cap_faces = []
    angles = [math.radians(-angle_deg / 2 + angle_deg * i / segments) for i in range(segments + 1)]
    # Shared endpoint heights make rotated copies join cleanly.
    profile = [0.0, 0.55, -0.25, 0.4, 0.0]
    if segments != 4:
        profile = [0.35 * math.sin(math.pi * i / segments) for i in range(segments + 1)]

    for i, ang in enumerate(angles):
        top = height + profile[i]
        for radius in (inner, inner + depth):
            x, y = radius * math.sin(ang), radius * math.cos(ang)
            rock_verts.extend([(x, y, 0.0), (x, y, top)])
            cap_verts.extend([(x, y, top), (x, y, top + cap)])

    # Vertex indices per angular sample: inner bottom/top, outer bottom/top.
    for i in range(segments):
        a = i * 4
        b = (i + 1) * 4
        quad_as_tris(rock_faces, a, b, b + 1, a + 1, flip=i % 2 == 0)  # inner wall
        quad_as_tris(rock_faces, a + 2, a + 3, b + 3, b + 2, flip=i % 2 == 1)  # outer wall
        quad_as_tris(rock_faces, a, a + 2, b + 2, b, flip=i % 2 == 0)  # bottom
        quad_as_tris(rock_faces, a + 1, b + 1, b + 3, a + 3, flip=i % 2 == 1)  # rock top

        ca = i * 4
        cb = (i + 1) * 4
        quad_as_tris(cap_faces, ca, cb, cb + 1, ca + 1, flip=i % 2 == 1)  # inner lip
        quad_as_tris(cap_faces, ca + 2, ca + 3, cb + 3, cb + 2, flip=i % 2 == 0)  # outer lip
        quad_as_tris(cap_faces, ca + 1, cb + 1, cb + 3, ca + 3, flip=i % 2 == 0)  # top

    # Close both radial ends.
    last = segments * 4
    quad_as_tris(rock_faces, 0, 1, 3, 2)
    quad_as_tris(rock_faces, last, last + 2, last + 3, last + 1)
    quad_as_tris(cap_faces, 0, 2, 3, 1)
    quad_as_tris(cap_faces, last, last + 1, last + 3, last + 2)

    rock = create_mesh_object(f"{name}_Rock", rock_verts, rock_faces, MODULES, ROCK_MATS, [0, 1, 2, 1, 3, 0, 2])
    top = create_mesh_object(f"{name}_TopCap", cap_verts, cap_faces, MODULES, [TOP_MAT, TOP_DARK], [1, 1, 0, 0, 0, 0])
    rock["module"] = name
    top["module"] = name
    return [rock, top]


def straight_piece(name="Cliff_Straight", length=22.0, depth=8.0, height=10.0, cap=0.65):
    xs = [-length / 2, -length / 4, 0.0, length / 4, length / 2]
    tops = [height, height + 0.5, height - 0.2, height + 0.35, height]
    verts, faces = [], []
    cap_verts, cap_faces = [], []
    for x, z in zip(xs, tops):
        verts.extend([(x, -depth / 2, 0), (x, -depth / 2, z), (x, depth / 2, 0), (x, depth / 2, z)])
        cap_verts.extend([(x, -depth / 2, z), (x, -depth / 2, z + cap), (x, depth / 2, z), (x, depth / 2, z + cap)])
    for i in range(4):
        a, b = i * 4, (i + 1) * 4
        quad_as_tris(faces, a, b, b + 1, a + 1, i % 2 == 0)
        quad_as_tris(faces, a + 2, a + 3, b + 3, b + 2, i % 2 == 1)
        quad_as_tris(faces, a, a + 2, b + 2, b)
        quad_as_tris(faces, a + 1, b + 1, b + 3, a + 3, i % 2 == 1)
        ca, cb = i * 4, (i + 1) * 4
        quad_as_tris(cap_faces, ca, cb, cb + 1, ca + 1)
        quad_as_tris(cap_faces, ca + 2, ca + 3, cb + 3, cb + 2)
        quad_as_tris(cap_faces, ca + 1, cb + 1, cb + 3, ca + 3, i % 2 == 0)
    last = 16
    quad_as_tris(faces, 0, 1, 3, 2)
    quad_as_tris(faces, last, last + 2, last + 3, last + 1)
    quad_as_tris(cap_faces, 0, 2, 3, 1)
    quad_as_tris(cap_faces, last, last + 1, last + 3, last + 2)
    return [
        create_mesh_object(f"{name}_Rock", verts, faces, MODULES, ROCK_MATS, [0, 1, 2, 3, 1, 0]),
        create_mesh_object(f"{name}_TopCap", cap_verts, cap_faces, MODULES, [TOP_MAT, TOP_DARK], [1, 0, 0, 0]),
    ]


def cylinder_cliff(name, radius=7.0, height=17.0, sides=10, cap=0.65):
    verts, faces, cap_verts, cap_faces = [], [], [], []
    for i in range(sides):
        a = 2 * math.pi * i / sides
        wobble = 1.0 + 0.06 * math.sin(i * 2.37)
        r = radius * wobble
        z = height + 0.6 * math.sin(i * 1.71)
        verts.extend([(r * math.cos(a), r * math.sin(a), 0), (r * math.cos(a), r * math.sin(a), z)])
        cap_verts.extend([(r * math.cos(a), r * math.sin(a), z), (r * math.cos(a), r * math.sin(a), z + cap)])
    for i in range(sides):
        j = (i + 1) % sides
        quad_as_tris(faces, i * 2, j * 2, j * 2 + 1, i * 2 + 1, i % 2 == 0)
        quad_as_tris(cap_faces, i * 2, j * 2, j * 2 + 1, i * 2 + 1, i % 2 == 1)
    # Triangle fans use centers.
    bottom_center = len(verts)
    top_center = bottom_center + 1
    verts.extend([(0, 0, 0), (0, 0, height)])
    cap_bottom_center = len(cap_verts)
    cap_top_center = cap_bottom_center + 1
    cap_verts.extend([(0, 0, height), (0, 0, height + cap)])
    for i in range(sides):
        j = (i + 1) % sides
        faces.extend([(bottom_center, j * 2, i * 2), (top_center, i * 2 + 1, j * 2 + 1)])
        cap_faces.extend([(cap_bottom_center, j * 2, i * 2), (cap_top_center, i * 2 + 1, j * 2 + 1)])
    return [
        create_mesh_object(f"{name}_Rock", verts, faces, MODULES, ROCK_MATS, [0, 1, 2, 3]),
        create_mesh_object(f"{name}_TopCap", cap_verts, cap_faces, MODULES, [TOP_MAT, TOP_DARK], [1, 0, 0]),
    ]


def box_mesh(name, size, location, collection, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    link_object(obj, collection)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("TinySilhouetteBevel", "BEVEL")
        mod.width = bevel
        mod.segments = 1
    return obj


def terrace_piece():
    objs = []
    specs = [((-5.0, 0, 2.5), (10, 9, 5)), ((2.5, 0.5, 5.0), (8, 8, 10)), ((7.0, 1.0, 7.0), (5, 7, 14))]
    for i, (loc, size) in enumerate(specs, 1):
        rock = box_mesh(f"Cliff_SteppedTerrace_Rock_{i}", size, loc, MODULES, ROCK_MATS[(i - 1) % len(ROCK_MATS)], 0.18)
        cap = box_mesh(f"Cliff_SteppedTerrace_TopCap_{i}", (size[0] + 0.15, size[1] + 0.15, 0.65), (loc[0], loc[1], loc[2] + size[2] / 2 + 0.325), MODULES, TOP_MAT, 0.1)
        objs.extend([rock, cap])
    return objs


def arch_piece():
    objs = []
    for side in (-1, 1):
        x = side * 7.25
        objs.append(box_mesh(f"Cliff_Arch_Rock_Pillar_{'L' if side < 0 else 'R'}", (5.5, 8, 10), (x, 0, 5), MODULES, ROCK_MATS[1 if side < 0 else 2], 0.25))
    objs.append(box_mesh("Cliff_Arch_Rock_Beam", (20, 8, 4.5), (0, 0, 11.75), MODULES, ROCK_MATS[0], 0.25))
    objs.append(box_mesh("Cliff_Arch_TopCap", (20.2, 8.2, 0.65), (0, 0, 14.325), MODULES, TOP_MAT, 0.1))
    return objs


def set_module_layout(groups):
    offsets = {
        "Cliff_Straight": (-43, -70, 0),
        # Curves pivot at the arena center, so their display offsets account for
        # the 36-stud inner radius while preserving export pivots at the origin.
        "Cliff_Curve45": (-15, -106, 0),
        "Cliff_Curve22": (17, -106, 0),
        "Cliff_PillarMesa": (43, -70, 0),
        "Cliff_SteppedTerrace": (-20, -92, 0),
        "Cliff_Arch": (20, -94, 0),
    }
    for module_name, objs in groups.items():
        offset = Vector(offsets[module_name])
        for obj in objs:
            obj.location += offset
            obj["display_offset"] = list(offset)


def duplicate_for_assembly(source_objs, index, rotation):
    duplicates = []
    for src in source_objs:
        dup = src.copy()
        # Unique mesh datablocks avoid material-slot ambiguity in FBX while the
        # geometry remains tiny (the complete ring is still well under 1k tris).
        dup.data = src.data.copy()
        dup.name = f"Assembly_Rim_{index:02d}_{src.name.split('_', 2)[-1]}"
        dup.location = (0, 0, 0)
        dup.rotation_euler[2] = rotation
        SAMPLE.objects.link(dup)
        duplicates.append(dup)
    return duplicates


def build_sample_assembly(curve45):
    assembly = []
    for i in range(8):
        assembly.extend(duplicate_for_assembly(curve45, i + 1, math.radians(i * 45)))
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=35.6, depth=0.5, location=(0, 0, -0.25))
    floor = bpy.context.object
    floor.name = "Assembly_GameplayFloor"
    link_object(floor, SAMPLE)
    floor.data.materials.append(FLOOR_MAT)
    assembly.append(floor)

    # Collision is intentionally simple and separate from visible mesh geometry.
    guide_mat = material("MAT_CollisionGuide", (0.9, 0.1, 0.08, 0.2))
    for i in range(16):
        a = math.radians(i * 22.5)
        r = 35.5
        chord = 2 * r * math.sin(math.radians(11.25)) + 0.5
        obj = box_mesh(f"CollisionGuide_{i + 1:02d}", (chord, 1.2, 8), (r * math.sin(a), r * math.cos(a), 4), COLLISION, guide_mat)
        obj.rotation_euler[2] = -a
        obj.display_type = "WIRE"
        obj.hide_render = True
    return assembly


def setup_scene():
    scene = bpy.context.scene
    # Blender 5.2 exposes Eevee under the BLENDER_EEVEE identifier.
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.18, 0.42, 0.72)
    scene.view_settings.look = "AgX - Medium High Contrast"

    world = scene.world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.12, 0.42, 0.78, 1)
    bg.inputs["Strength"].default_value = 0.55

    bpy.ops.object.light_add(type="SUN", location=(20, -30, 55))
    sun = bpy.context.object
    sun.name = "Preview_Sun"
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(28), math.radians(-22), math.radians(-28))

    bpy.ops.object.light_add(type="AREA", location=(-25, -20, 40))
    area = bpy.context.object
    area.name = "Preview_Fill"
    area.data.energy = 1200
    area.data.shape = "DISK"
    area.data.size = 35


def point_camera(location, target=(0, 0, 4), lens=52):
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.object
    cam.name = "Preview_Camera"
    cam.data.lens = lens
    direction = Vector(target) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def hide_collection_for_render(collection, hidden):
    collection.hide_render = hidden


def render_previews():
    scene = bpy.context.scene
    cam = point_camera((88, -112, 76), (0, 0, 4), 58)
    hide_collection_for_render(MODULES, True)
    hide_collection_for_render(SAMPLE, False)
    scene.render.filepath = str(PREVIEWS / "cliff-kit-arena-preview.png")
    bpy.ops.render.render(write_still=True)

    cam.location = (0, -180, 66)
    cam.rotation_euler = (Vector((0, -80, 7)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 38
    hide_collection_for_render(MODULES, False)
    hide_collection_for_render(SAMPLE, True)
    scene.render.filepath = str(PREVIEWS / "cliff-kit-modules-preview.png")
    bpy.ops.render.render(write_still=True)
    hide_collection_for_render(MODULES, False)
    hide_collection_for_render(SAMPLE, False)


def export_selection(filepath, objects, kind):
    bpy.ops.object.select_all(action="DESELECT")
    saved = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        saved.append((obj, obj.location.copy()))
        offset = Vector(obj.get("display_offset", (0, 0, 0)))
        obj.location -= offset
        obj.select_set(True)
    bpy.context.view_layer.objects.active = next((obj for obj, _ in saved), None)
    if kind == "FBX":
        bpy.ops.export_scene.fbx(
            filepath=str(filepath),
            use_selection=True,
            object_types={"MESH"},
            apply_scale_options="FBX_SCALE_ALL",
            axis_forward="-Z",
            axis_up="Y",
            add_leaf_bones=False,
            use_mesh_modifiers=True,
        )
    else:
        bpy.ops.export_scene.gltf(
            filepath=str(filepath),
            export_format="GLB",
            use_selection=True,
            export_apply=True,
        )
    for obj, location in saved:
        obj.location = location
    bpy.ops.object.select_all(action="DESELECT")


def mesh_stats(objects):
    verts = sum(len(o.data.vertices) for o in objects if o.type == "MESH")
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objects if o.type == "MESH")
    return {"objects": len([o for o in objects if o.type == "MESH"]), "vertices": verts, "triangles": tris}


def export_all(groups, sample_objects):
    report = {"blender_version": bpy.app.version_string, "modules": {}}
    for name, objects in groups.items():
        slug = name.lower().replace("cliff_", "cliff-").replace("_", "-")
        export_selection(EXPORT_FBX / f"{slug}.fbx", objects, "FBX")
        export_selection(EXPORT_GLB / f"{slug}.glb", objects, "GLB")
        report["modules"][name] = mesh_stats(objects)
    export_selection(EXPORT_FBX / "sample-circular-arena.fbx", sample_objects, "FBX")
    export_selection(EXPORT_GLB / "sample-circular-arena.glb", sample_objects, "GLB")
    report["sample_assembly"] = mesh_stats(sample_objects)
    report["dimensions_blender_units"] = {
        "arena_clear_radius": 35.5,
        "curve45_inner_radius": 36.0,
        "curve45_outer_radius": 44.0,
        "nominal_cliff_height": 10.0,
        "top_cap_thickness": 0.65,
    }
    (ROOT / "polygon-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


clear_scene()
MODULES = ensure_collection("Modules")
SAMPLE = ensure_collection("SampleAssembly")
COLLISION = ensure_collection("CollisionGuides")

ROCK_MATS = [
    material("MAT_Rock_Base", (0.33, 0.39, 0.47, 1)),
    material("MAT_Rock_LightFacet", (0.42, 0.49, 0.57, 1)),
    material("MAT_Rock_MidFacet", (0.28, 0.34, 0.42, 1)),
    material("MAT_Rock_DarkFacet", (0.21, 0.27, 0.34, 1)),
]
TOP_MAT = material("MAT_TopCap_Grass", (0.24, 0.58, 0.25, 1))
TOP_DARK = material("MAT_TopCap_Edge", (0.16, 0.43, 0.18, 1))
FLOOR_MAT = material("MAT_ArenaFloor", (0.31, 0.66, 0.29, 1))

groups = {
    "Cliff_Straight": straight_piece(),
    "Cliff_Curve45": annular_piece("Cliff_Curve45", 45.0, segments=4),
    "Cliff_Curve22": annular_piece("Cliff_Curve22", 22.5, inner=36.0, depth=8.0, height=7.0, segments=4),
    "Cliff_PillarMesa": cylinder_cliff("Cliff_PillarMesa"),
    "Cliff_SteppedTerrace": terrace_piece(),
    "Cliff_Arch": arch_piece(),
}
for module_name, objects in groups.items():
    for obj in objects:
        obj["module"] = module_name
set_module_layout(groups)

sample_objects = build_sample_assembly(groups["Cliff_Curve45"])
setup_scene()
render_previews()
export_all(groups, sample_objects)

bpy.context.scene["kit_note"] = "Original low-poly modular cliff kit; visual collision is intentionally separate."
bpy.context.scene["roblox_scale_note"] = "Start with 1 Blender unit = 1 Roblox stud; adjust import scale only as a whole kit."
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "roblox-modular-cliff-kit.blend"))
print(f"Generated modular cliff kit at {ROOT}")
