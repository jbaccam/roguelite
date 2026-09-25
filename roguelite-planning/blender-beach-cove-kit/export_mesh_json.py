"""Dump the kit's geometry as JSON for Studio to rebuild via EditableMesh.

    blender --background beach-cove-kit.blend --python export_mesh_json.py

Roblox can build a real MeshPart from geometry supplied in Luau
(AssetService:CreateEditableMesh + CreateMeshPartAsync), so the 3D Importer and
its upload step can be skipped entirely. This writes one JSON per asset plus a
manifest, ready to be served over localhost and fetched by Studio.

Axes: Blender is Z-up, Roblox is Y-up, matching the kit's FBX export settings
(axis_up='Y', axis_forward='-Z'). So a Roblox position is (x, z, -y).
"""
import json
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "studio-mesh-json"
OUT.mkdir(parents=True, exist_ok=True)


def to_roblox(v):
    return [round(v.x, 4), round(v.z, 4), round(-v.y, 4)]


def dump(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    uv_layer = mesh.uv_layers.active

    # EditableMesh wants one vertex id per unique (position, uv) corner, because
    # UVs are per-face-corner in Blender but attached per vertex id here. Welding
    # on that key keeps the vertex count near Blender's while preserving seams.
    verts, index_of = [], {}
    uvs, uv_index_of = [], {}
    tris = []

    for tri in mesh.loop_triangles:
        corner_v, corner_uv = [], []
        for li in tri.loops:
            vi = mesh.loops[li].vertex_index
            co = mesh.vertices[vi].co
            uv = uv_layer.data[li].uv if uv_layer else (0.0, 0.0)
            # Weld on (position, uv), NOT position alone. A vertex carries a
            # single UV, so welding purely by position collapses the two sides of
            # a UV seam onto one coordinate and the atlas smears across the face.
            uvkey = (round(uv[0], 5), round(1.0 - uv[1], 5))
            vkey = (round(co.x, 4), round(co.y, 4), round(co.z, 4)) + uvkey
            if vkey not in index_of:
                index_of[vkey] = len(verts)
                verts.append(to_roblox(co))
            corner_v.append(index_of[vkey])

            # Blender's UV origin is bottom-left, Roblox's is top-left, so V is
            # flipped (done in uvkey above).
            ukey = uvkey
            if ukey not in uv_index_of:
                uv_index_of[ukey] = len(uvs)
                uvs.append([ukey[0], ukey[1]])
            corner_uv.append(uv_index_of[ukey])
        tris.append(corner_v + corner_uv)

    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return {
        "name": obj.name,
        "vertices": verts,
        "uvs": uvs,
        # each entry: v0, v1, v2, uv0, uv1, uv2
        "triangles": tris,
        "size_studs": [round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4), round(max(zs) - min(zs), 4)],
        "bbox_centre": [round((max(xs) + min(xs)) / 2, 4),
                        round((max(ys) + min(ys)) / 2, 4),
                        round((max(zs) + min(zs)) / 2, 4)],
    }


manifest = {"assets": {}}
for obj in sorted(bpy.data.objects, key=lambda o: o.name):
    if obj.type != "MESH":
        continue
    if not obj.name[:2].isdigit():      # skip preview ground, labels, helpers
        continue
    data = dump(obj)
    stem = obj.name.lower().replace("_", "-")
    (OUT / f"{stem}.json").write_text(json.dumps(data, separators=(",", ":")))
    manifest["assets"][stem] = {
        "name": obj.name,
        "vertices": len(data["vertices"]),
        "triangles": len(data["triangles"]),
        "size_studs": data["size_studs"],
        "bbox_centre": data["bbox_centre"],
        "json": f"{stem}.json",
        "atlas": f"{obj.name.lower()}-atlas.png",
    }
    print(f"{stem:26s} {len(data['vertices']):5d} verts  {len(data['triangles']):5d} tris")

(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
print("ASSETS", len(manifest["assets"]))
