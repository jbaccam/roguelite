"""Package every built chest tier into ONE FBX for a single Studio 3D Import, and render the
transparent UI icons used by the chest screen.

Reads only the saved per-tier files (`chest-<tier>.blend`, `polygon-report-<tier>.json`); it never
edits them. Writes:
  exports/fbx/chest-kit-studio.fbx   one Empty per tier (Chest_<Tier>), parts renamed <Tier>_<Part>
  studio-install-data.json           per part: kind, glow colour, bbox centre from the tier origin in
                                     Studio axes, plus the lid hinge in Studio axes
  previews/icon-<tier>.png           512x512 transparent 3/4 icon (Studio UI)

Axis note: Blender (x, y, z) -> Studio (-x, z, y). Blender front is -Y, Studio front is -Z. The FBX
importer turns models 180 degrees about Y relative to glTF (see blender-map-mini-islands), which is
what makes x flip here.

  blender --background --python package_studio.py [-- --icons-only]
  blender --background --python package_studio.py -- magical     # just these tiers

With tier names, only those tiers are packaged, into exports/fbx/chest-kit-studio-<tiers>.fbx; their
entries are merged into studio-install-data.json (other tiers' entries are kept), and only their
icons are re-rendered. Re-install them in Studio with the installer's ONLY set to the tier.
"""
import bpy, json, math, sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
ALL_TIERS = ["wooden", "silver", "gold", "magical", "legendary"]
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PICKED = [a for a in ARGS if a in ALL_TIERS]
TIERS = PICKED or ALL_TIERS
FBX_NAME = "chest-kit-studio" + ("-" + "-".join(PICKED) if PICKED else "") + ".fbx"
SPACING = 18.0
ICONS_ONLY = "--icons-only" in ARGS


def studio(v):
    return [round(-v[0], 4), round(v[2], 4), round(v[1], 4)]


def tier_kinds(tier):
    """Map part name -> kind from the report roles (textured/glow/floor/accent)."""
    rep = json.loads((ROOT / f"polygon-report-{tier}.json").read_text())
    kinds = {}
    for name, p in rep["parts"].items():
        role = p["role"]
        if role.startswith("MeshPart"):
            kinds[name] = "textured"
        elif "seen when open" in role:
            kinds[name] = "floor"
        elif "fade" in role or "hidden" in role:
            kinds[name] = "glow"
        else:
            kinds[name] = "accent"
    return rep, kinds


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
data = {"axis": "studio = (-x, z, y) of blender; front = -Z", "tiers": {}}
groups = {}

for i, tier in enumerate(TIERS):
    rep, kinds = tier_kinds(tier)
    with bpy.data.libraries.load(str(ROOT / f"chest-{tier}.blend"), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in kinds]
    Tier = tier.capitalize()
    empty = bpy.data.objects.new(f"Chest_{Tier}", None)
    scene.collection.objects.link(empty)
    empty.location = (i * SPACING, 0, 0)
    parts = {}
    for ob in dst.objects:
        if ob is None:
            continue
        base = ob.name.split(".")[0]
        scene.collection.objects.link(ob)
        ob.name = f"{Tier}_{base}"
        ob.data.name = ob.name
        ob.parent = empty
        ob.matrix_parent_inverse.identity()
        parts[base] = ob
    bpy.context.view_layer.update()
    info = {"hinge": studio(rep["hinge_studs"]) if rep.get("hinge_studs") else None,
            "rotate_x_deg": rep["open"].get("rotate_x_deg", 105), "lift": rep["open"].get("lift", 0),
            "moves": rep["moves_when_opening"], "glow": rep["glow_srgb"], "accent": rep["accent_srgb"],
            "parts": {}}
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for base, ob in parts.items():
        cs = [ob.matrix_basis @ Vector(c) for c in ob.bound_box]  # local to the tier origin
        mn = Vector((min(c[k] for c in cs) for k in range(3)))
        mx = Vector((max(c[k] for c in cs) for k in range(3)))
        lo = Vector((min(lo[k], mn[k]) for k in range(3))); hi = Vector((max(hi[k], mx[k]) for k in range(3)))
        size = mx - mn
        info["parts"][base] = {"kind": kinds[base], "center": studio((mn + mx) / 2),
                               "size": [round(size.x, 4), round(size.z, 4), round(size.y, 4)]}
    info["bounds_size"] = [round(hi.x - lo.x, 3), round(hi.z - lo.z, 3), round(hi.y - lo.y, 3)]
    info["bounds_center"] = studio((lo + hi) / 2)
    data["tiers"][Tier] = info
    groups[Tier] = (empty, parts)

if not ICONS_ONLY:
    out = ROOT / "studio-install-data.json"
    if PICKED and out.exists():
        merged = json.loads(out.read_text())
        merged["tiers"].update(data["tiers"])   # keep the tiers we didn't repackage
        data = merged
    out.write_text(json.dumps(data, indent=2))
    bpy.ops.object.select_all(action="DESELECT")
    for empty, parts in groups.values():
        empty.select_set(True)
        for ob in parts.values():
            ob.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(groups.values()))[0]
    bpy.ops.export_scene.fbx(filepath=str(ROOT / "exports/fbx" / FBX_NAME), use_selection=True,
                             object_types={"MESH", "EMPTY"}, axis_forward="-Z", axis_up="Y", path_mode="COPY",
                             embed_textures=True, add_leaf_bones=False)
    print("PACKAGED", {t: sorted(v["parts"]) for t, v in data["tiers"].items()}, flush=True)

# ---- icons: one tier visible at a time, same camera angle, framed on that tier's bounds ----
scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "BLENDER_EEVEE"
scene.render.film_transparent = True
scene.render.resolution_x = scene.render.resolution_y = 512
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("IconWorld"); scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.8, 0.85, 0.95, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 1.2; sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
scene.collection.objects.link(sun)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.data.type = "ORTHO"
scene.collection.objects.link(cam); scene.camera = cam

for tier_name, (empty, parts) in groups.items():
    for other, (e2, p2) in groups.items():
        for ob in p2.values():
            ob.hide_render = other != tier_name or data["tiers"][other]["parts"][ob.name.split("_", 1)[1]]["kind"] == "floor"
    info = data["tiers"][tier_name]
    sx, sy, sz = info["bounds_size"]  # studio axes: x width, y height, z depth
    centre = empty.location + Vector((0, 0, sy / 2))
    d = Vector((-0.55, -1.0, 0.55)).normalized()  # front-left, above (Blender axes)
    cam.location = centre + d * 40
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam.data.ortho_scale = max(sx, sy, sz) * 1.45
    scene.render.filepath = str(ROOT / "previews" / f"icon-{tier_name.lower()}.png")
    bpy.ops.render.render(write_still=True)
print("ICONS_DONE", flush=True)
