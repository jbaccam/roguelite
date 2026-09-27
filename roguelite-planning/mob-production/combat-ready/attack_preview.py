"""Fast Workbench review strips for authored clips. Never saves the blend.

blender -b --python animate_mobs.py -- <id> --preview <outdir> [clip] [frames]
Writes <outdir>/<id>_<clip>_<view>_<frame>.png with a camera fixed per view so
motion reads across frames, plus <id>_<clip>_trace.json with tracked points.
"""
import json, math
from pathlib import Path
from mathutils import Vector


def run(g, out, clip, count, frames, track):
    bpy, scene, rig, meshes, pose = g['bpy'], g['scene'], g['rig'], g['meshes'], g['pose']
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = 'TEXTURE'
    scene.display.shading.show_cavity = True
    scene.render.resolution_x = scene.render.resolution_y = 320
    cam = bpy.data.objects.new('PreviewCam', bpy.data.cameras.new('PreviewCam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = 'ORTHO'
    # Fixed framing from the swept bounds of every sampled pose.
    samples = sorted(set(frames) | set(range(0, count + 1, max(1, count // 12))))
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3); trace = {}
    for f in samples:
        pose(clip, f / count)
        dg = bpy.context.evaluated_depsgraph_get()
        for o in meshes:
            e = o.evaluated_get(dg); m = e.to_mesh()
            for i, v in enumerate(m.vertices):
                if i % 5: continue
                p = o.matrix_world @ v.co
                lo = Vector(map(min, lo, p)); hi = Vector(map(max, hi, p))
            e.to_mesh_clear()
        trace[f] = {k: list(fn()) for k, fn in track.items()}
    center = (lo + hi) / 2
    size = max(hi - lo) * 1.08
    views = {'side': Vector((1, 0, 0)), 'front': Vector((0, -1, 0)), 'q34': Vector((.75, -.6, .35)), 'top': Vector((0, 0, 1))}
    for f in frames:
        pose(clip, f / count)
        for name, d in views.items():
            d = d.normalized()
            cam.location = center + d * 40
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler() if name != 'top' else (0, 0, 0)
            cam.data.ortho_scale = size
            scene.render.filepath = str(out / f"{g['ID']}_{clip}_{name}_{f:03d}.png")
            bpy.ops.render.render(write_still=True)
    (out / f"{g['ID']}_{clip}_trace.json").write_text(json.dumps(trace, indent=1))
