p = 'build_alpha_werewolf.py'
s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:90]
    s = s.replace(a, b, 1)
rep("    for t, wf in [(0, .55), (.16, .90), (.36, 1.0), (.58, .88), (.76, .66), (.89, .42), (.97, .18)]:",
    "    for t, wf in [(0, .60), (.18, .92), (.40, 1.0), (.62, .95), (.80, .78), (.92, .52), (.985, .22)]:")
rep("def lobe(b, root, normal, flow, L, W, sink=.16, lift=.10, droop=.05):", "def lobe(b, root, normal, flow, L, W, sink=.16, lift=.10, droop=.03):")
rep("mane_base = [ell('Mane crown', (0, .02, 5.80), (1.25, .78, .82), paint('mane'), 32, 20),\n             ell('Mane hump', (0, .50, 5.00), (1.42, .66, 1.0), paint('mane'), 32, 20)]",
    "mane_base = [ell('Mane crown', (0, .04, 5.80), (1.32, .84, .86), paint('mane'), 32, 20),\n             ell('Mane hump', (0, .52, 5.00), (1.48, .72, 1.05), paint('mane'), 32, 20)]")
rep("            placed(mane_b, (s * x, 6, z), (0, -1, 0), (s * (.12 + x * .30), .40, -1), L * (1 + .10 * r), .78 * (1 + .08 * r), .18)",
    "            placed(mane_b, (s * x, 6, z), (0, -1, 0), (s * (.12 + x * .30), .40, -1), 1.2 * L * (1 + .10 * r), 1.0 * (1 + .08 * r), .12)")
rep("(s * .55, .3, -.8), .88 + .06 * r['l'], .74, .18,", "(s * .55, .3, -.8), 1.05 + .06 * r['l'], .95, .12,")
rep("(0, 1, 0), (s * .25, -.2, -1), .80, .70, .18,", "(0, 1, 0), (s * .25, -.2, -1), .92, .86, .13,")
rep("addons = prefuse(mane_base + [mane_lobes, tuft_lobes, chest_lobes], 'Fur addons', .026, 10, .6)",
    "addons = prefuse(mane_base + [mane_lobes, tuft_lobes, chest_lobes], 'Fur addons', .026, 6, .55)")
rep("            hplace(hm, (s * 3, y, z), (-s, 0, 0), (s * .85, .35, -.42), .80, .66, need=lambda p: abs(p.x) < 1.0)",
    "            hplace(hm, (s * 3, y, z), (-s, 0, 0), (s * .85, .35, -.42), .92, .80, .11, need=lambda p: abs(p.x) < 1.0)")
rep("        lobe(hm, Vector((s * .30, y, 5.30)), Vector((s * .4, -.2, -1)), Vector((s * .25, .1, -1)), .66, .58, .12)",
    "        lobe(hm, Vector((s * .30, y, 5.30)), Vector((s * .4, -.2, -1)), Vector((s * .25, .1, -1)), .74, .70, .10)")
rep("            hplace(hm, (s * x, y, 9), (0, 0, -1), (s * x * .5, 1, -.25), .76, .64)",
    "            hplace(hm, (s * x, y, 9), (0, 0, -1), (s * x * .5, 1, -.25), .86, .78, .11)")
rep("ruff = prefuse([hm.make('Face ruff', 'mane')], 'Face ruff', .018, 8)", "ruff = prefuse([hm.make('Face ruff', 'mane')], 'Face ruff', .018, 5)")
# QUICK: low-sample Cycles so the colour masks show
a = s.index("if QUICK:\n    # Shape check only")
b = s.index("    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / '_work' / 'quick.blend'))")
s = s[:a] + '''if QUICK:
    # Shape + colour-field check: low-sample Cycles (shows the mask-mixed colours).
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 12
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = 'Standard'
    scene.world = bpy.data.worlds.new('Quick sky')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (*srgb((176, 186, 200)), 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .8
    bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
    sun = staged(bpy.context.object)
    sun.data.energy = 3.2
    sun.rotation_euler = (math.radians(50), 0, math.radians(-30))
    bpy.ops.object.camera_add()
    cam = staged(bpy.context.object)
    scene.camera = cam
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = 10.5
    scene.render.resolution_x = 520
    scene.render.resolution_y = 600
    for label, ang in [('Front', 0), ('Side', 90), ('ThreeQuarter', 30), ('Back', 180)]:
        R = Matrix.Rotation(math.radians(ang), 3, 'Z')
        cam.location = R @ Vector((0, -20, 4.6))
        aim(cam, (0, 0, 4.6))
        scene.render.filepath = str(OUT / '_work' / f'quick_{label}.png')
        bpy.ops.render.render(write_still=True)
''' + s[b:]
open(p, 'w', encoding='utf-8').write(s)
print('patched 2')
