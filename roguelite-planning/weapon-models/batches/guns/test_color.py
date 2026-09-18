import bpy
from pathlib import Path
p=Path(__file__).resolve().parents[2]/'assets'/'24-nail-gun'
bpy.ops.wm.open_mainfile(filepath=str(p/'Model.blend'))
s=bpy.context.scene;s.view_settings.view_transform='Standard';s.view_settings.exposure=-.65
s.render.resolution_percentage=65;s.cycles.samples=16;s.render.filepath=str(Path(__file__).parent/'ColorTest.png')
bpy.ops.render.render(write_still=True)
