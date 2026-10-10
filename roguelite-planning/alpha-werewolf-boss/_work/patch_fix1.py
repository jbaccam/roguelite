p = 'build_alpha_werewolf.py'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, a[:90]
    s = s.replace(a, b, 1)


def cut_between(a_mark, b_mark, new):
    global s
    a = s.index(a_mark)
    b = s.index(b_mark)
    s = s[:a] + new + s[b:]


# palette
rep("COL = {'fur': (134, 52, 42), 'mane': (60, 52, 56),", "COL = {'fur': (118, 46, 40), 'mane': (46, 40, 44),")
rep("'nose': (28, 26, 29), 'eye': (255, 172, 40),", "'nose': (28, 26, 29), 'eye': (255, 150, 30),")

cut_between("def paint(key, variation=.09, scale=.85):", "for k in COL:\n    paint(k)", '''def paint(key, layers=(), variation=.09, scale=.85):
    """Clean colour fields: the base colour and optional layers mixed by soft
    per-vertex masks (e.g. ManeMask, CreamMask), so boundaries are gradients, not
    per-face speckles. Then broad painterly value patches (object-space noise),
    the baked Cavity attribute, a per-lobe Clump tint and a little top light.
    Baked to the section's 1024 map later."""
    name = 'AW_' + key + ''.join('+' + k for k, a in layers)
    if name in MATS:
        return MATS[name]
    color = srgb(COL[key])
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (*color, 1)
    nt = m.node_tree
    n = nt.nodes
    l = nt.links
    p = n.get('Principled BSDF')
    p.inputs['Roughness'].default_value = .86
    p.inputs['Specular IOR Level'].default_value = .15

    def vm(op, a=None, b=None):
        v = n.new('ShaderNodeVectorMath')
        v.operation = op
        for i, x in ((0, a), (1, b)):
            if x is None:
                continue
            if isinstance(x, tuple):
                v.inputs[i].default_value = x
            else:
                l.new(x, v.inputs[i])
        return v

    def attr(name_):
        at = n.new('ShaderNodeAttribute')
        at.attribute_name = name_
        at.attribute_type = 'GEOMETRY'
        return at.outputs['Fac']

    cur = vm('ADD', tuple(color), (0, 0, 0)).outputs['Vector']
    for k, a in layers:
        diff = vm('SUBTRACT', tuple(srgb(COL[k])), cur)
        sc = vm('SCALE', diff.outputs['Vector'])
        l.new(attr(a), sc.inputs['Scale'])
        cur = vm('ADD', cur, sc.outputs['Vector']).outputs['Vector']

    def scaled(cur, fac):
        s_ = vm('SCALE', cur)
        l.new(fac, s_.inputs['Scale'])
        return s_.outputs['Vector']

    tc = n.new('ShaderNodeTexCoord')
    noise = n.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = scale
    noise.inputs['Detail'].default_value = 1.5
    noise.inputs['Roughness'].default_value = .5
    l.new(tc.outputs['Object'], noise.inputs['Vector'])
    for src, lo, hi, a, b in [(noise.outputs['Fac'], 1 - variation, 1 + variation, .32, .68),
                              (attr('Cavity'), .72, 1.0, 0, 1), (attr('Clump'), .93, 1.07, -1, 1)]:
        r = n.new('ShaderNodeMapRange')
        r.inputs['From Min'].default_value = a
        r.inputs['From Max'].default_value = b
        r.inputs['To Min'].default_value = lo
        r.inputs['To Max'].default_value = hi
        l.new(src, r.inputs['Value'])
        cur = scaled(cur, r.outputs['Result'])
    geo = n.new('ShaderNodeNewGeometry')
    sep = n.new('ShaderNodeSeparateXYZ')
    l.new(geo.outputs['Normal'], sep.inputs[0])
    r = n.new('ShaderNodeMapRange')
    r.inputs['From Min'].default_value = .25
    r.inputs['From Max'].default_value = 1
    r.inputs['To Min'].default_value = 1
    r.inputs['To Max'].default_value = 1.07
    l.new(sep.outputs['Z'], r.inputs['Value'])
    cur = scaled(cur, r.outputs['Result'])
    l.new(cur, p.inputs['Base Color'])
    MATS[name] = m
    return m


''')

rep("def loft(name, levels, key, side=1, exponent=.85, shape=None, n=48):", '''def lobe(b, root, normal, flow, L, W, sink=.16, lift=.10, droop=.05):
    """One SOFT fur lobe: a thick round-sectioned teardrop, mostly buried in the
    surface it grows from, with a broad rounded tip. Overlapping lobes are
    pre-fused and smoothed into one continuous mass: no slabs, no sheet edges.
    (Thin shards/locks read as blades, scales or feathers: rejected.)"""
    n = Vector(normal).normalized()
    d = Vector(flow)
    d = d - n * d.dot(n)
    if d.length < 1e-4:
        d = Vector((0, 0, -1)) - n * (-n.z)
    d.normalize()
    s = n.cross(d).normalized()
    base = Vector(root) - n * sink
    verts = []
    faces = []
    rings = []
    m = 8
    for t, wf in [(0, .55), (.16, .90), (.36, 1.0), (.58, .88), (.76, .66), (.89, .42), (.97, .18)]:
        c = base + d * (L * t) + n * (sink * min(1, t * 2.5) + L * (lift * t - droop * t * t))
        i = len(verts)
        for k in range(m):
            a = k * math.tau / m
            verts.append(c + s * math.cos(a) * W * .5 * wf + n * math.sin(a) * W * .36 * wf)
        rings.append(i)
    verts.append(base + d * L + n * (sink + L * (lift - droop)))
    tip = len(verts) - 1
    for a, c in zip(rings, rings[1:]):
        for k in range(m):
            faces.append((a + k, a + (k + 1) % m, c + (k + 1) % m, c + k))
    last = rings[-1]
    for k in range(m):
        faces.append((last + k, last + (k + 1) % m, tip))
    faces.append(tuple(rings[0] + k for k in range(m - 1, -1, -1)))
    b.add(verts, faces)
    CLUMPS.setdefault(id(b), []).append((Vector(root) + d * L * .4, rng.uniform(-1, 1)))


def prefuse(objects, name, voxel, iters, factor=.6):
    """Voxel union + strong relax, no decimation: one soft continuous mass."""
    o = join(objects, name)
    o.data.remesh_voxel_size = voxel * (1.3 if QUICK else 1)
    active(o)
    bpy.ops.object.voxel_remesh()
    mod = o.modifiers.new('Soft mass', 'SMOOTH')
    mod.factor = factor
    mod.iterations = iters
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return o


def relax_attr(o, vals, iters=2, keep=.5):
    import numpy as _np
    v = _np.asarray(vals, float)
    e = _np.array([list(ed.vertices) for ed in o.data.edges], dtype=int)
    src = _np.concatenate((e[:, 0], e[:, 1]))
    dst = _np.concatenate((e[:, 1], e[:, 0]))
    deg = _np.bincount(src, minlength=len(v))
    for _ in range(iters):
        acc = _np.zeros_like(v)
        _np.add.at(acc, src, v[dst])
        v = keep * v + (1 - keep) * acc / _np.maximum(1, deg)
    return [float(x) for x in v]


def loft(name, levels, key, side=1, exponent=.85, shape=None, n=48):''')

cut_between("fur = Builder()\nmane = Builder()\nbib = Builder()", "# ------------------------------------------------------------------ head", '''mane_b = Builder()
tuft_b = Builder()
chest_b = Builder()


def pair(fn):
    r = {'l': rng.uniform(-1, 1)}
    for s in [-1, 1]:
        fn(s, r)


def placed(b, origin, direction, flow, L, W, sink=.16, need=None, lift=.10):
    p, nrm = hit(origin, direction)
    if p is None or (need and not need(p)):
        return
    lobe(b, p, nrm, flow, L, W, sink, lift)


def VHW(z):
    """Half-width of the cream chest V."""
    return max(0, .80 * (z - 3.85) / 1.30)


# Back mane: overlapping rows of broad rounded lobes; each row's tips roll over the next.
for j, (z, hw) in enumerate([(6.25, .55), (5.92, 1.05), (5.58, 1.40), (5.24, 1.55), (4.90, 1.45), (4.56, 1.15), (4.24, .75)]):
    step = .60
    offset = 0 if j % 2 else step / 2
    for x in [x for x in [offset + k * step for k in range(5)] if x <= hw + .01]:
        L = 1.0 + .12 * min(1, (z - 4.2) / 1.6)
        r = rng.uniform(-1, 1)
        for s in ([1] if x < .01 else [-1, 1]):
            placed(mane_b, (s * x, 6, z), (0, -1, 0), (s * (.12 + x * .30), .40, -1), L * (1 + .10 * r), .78 * (1 + .08 * r), .18)
# Over the shoulders, rolling outward and down.
for x in [.70, 1.20]:
    for y in [-.05, .40]:
        pair(lambda s, r, x=x, y=y: placed(mane_b, (s * x, y, 9), (0, 0, -1), (s * .55, .3, -.8), .88 + .06 * r['l'], .74, .18,
                                          need=lambda p: p.z > 5.0))
# Collar: the ruff continues down the sides of the chest, framing the cream V.
for z in [5.15, 4.82]:
    pair(lambda s, r, z=z: placed(mane_b, (s * (VHW(z) + .30), -5, z), (0, 1, 0), (s * .25, -.2, -1), .80, .70, .18,
                                 need=lambda p: p.z > 4.5))
# Cream chest: three soft lobes under the chin; the rest is a clean colour field.
placed(chest_b, (0, -5, 5.02), (0, 1, 0), (0, -.25, -1), .80, .80, .20)
for s in [-1, 1]:
    placed(chest_b, (s * .36, -5, 4.92), (0, 1, 0), (s * .15, -.25, -1), .72, .70, .20)
# Russet: a few soft tufts at the shoulders and elbows, soft cuffs over wrists and ankles.
for y in [-.15, .22]:
    pair(lambda s, r, y=y: placed(tuft_b, (s * 6, y, 4.86), (-s, 0, 0), (s * .55, .05, -1), .66, .58, .16))
pair(lambda s, r: placed(tuft_b, (s * 1.98, 5, 3.86), (0, -1, 0), (s * .35, .8, -.6), .64, .56, .16))


def cuff(axis, z, count, L, W):
    for k in range(count):
        a = (k + .5) * math.tau / count
        for s in [-1, 1]:
            c = Vector((s * axis[0], axis[1], z))
            r = Vector((s * math.cos(a), math.sin(a), 0))
            placed(tuft_b, c + r * .9, -r, Vector((0, 0, -1)) + r * .3, L, W, .14)


cuff((2.16, -.05), 2.66, 6, .50, .52)
cuff((.88, .15), .64, 6, .46, .50)

mane_lobes = mane_b.make('Mane lobes', 'mane')
tuft_lobes = tuft_b.make('Fur tufts', 'fur')
chest_lobes = chest_b.make('Chest lobes', 'cream')
body_clumps = CLUMPS.get(id(mane_b), []) + CLUMPS.get(id(tuft_b), []) + CLUMPS.get(id(chest_b), [])
src_mane = copy_of(mane_base + [mane_lobes], 'SRC_mane')
src_other = copy_of(base + [tuft_lobes, chest_lobes], 'SRC_other')
log('pre-fusing fur add-ons')
addons = prefuse(mane_base + [mane_lobes, tuft_lobes, chest_lobes], 'Fur addons', .026, 10, .6)
log('fusing body skin')
skin = fuse_to(base + [addons], 'AlphaWolf_Body', 'fur', .024, 9200, 4, .55)
skin.data.materials.clear()
skin.data.materials.append(paint('fur', (('mane', 'ManeMask'), ('cream', 'CreamMask'))))
tm = bvh_of(src_mane)
to = bvh_of(src_other)
mane_m = []
cream_m = []
for v in skin.data.vertices:
    c = v.co
    nrm = v.normal
    mane_m.append(smooth01(.05, -.05, tm.find_nearest(c)[3] - to.find_nearest(c)[3]))
    cream_m.append(smooth01(-.07, .07, VHW(c.z) - abs(c.x)) * smooth01(-.02, -.30, nrm.y) * smooth01(3.80, 3.98, c.z) *
                   smooth01(5.45, 5.30, c.z))
mane_m = relax_attr(skin, mane_m, 2)
cream_m = [c * (1 - m_) for c, m_ in zip(relax_attr(skin, cream_m, 2), mane_m)]
set_attr(skin, 'ManeMask', mane_m)
set_attr(skin, 'CreamMask', cream_m)
for o in (src_mane, src_other, probe):
    bpy.data.objects.remove(o, do_unlink=True)
log('SKIN tris', len(skin.data.polygons))

''')

cut_between("hb = Builder()     # russet cheek clumps", "# Lower jaw: a separate hinged solid", '''hb = Builder()     # russet cheek tufts
hm = Builder()     # charcoal face ruff + crown


def hplace(b, origin, direction, flow, L, W, sink=.14, need=None):
    loc, nor, i, d = hbv.ray_cast(Vector(origin), Vector(direction).normalized(), 10)
    if loc is None or (need and not need(loc)):
        return
    lobe(b, loc, nor, flow, L, W, sink)


for s in [-1, 1]:
    for root, flow, L in [((.55, -.82, 5.60), (.85, .35, -.35), .46), ((.50, -.72, 5.42), (.7, .35, -.7), .44),
                          ((.56, -.66, 5.80), (.8, .4, 0), .40)]:
        lobe(hb, Vector((s * root[0], root[1], root[2])), Vector((s, -.3, 0)), Vector((s * flow[0], flow[1], flow[2])), L, .40, .10)
    # Face ruff: broad rounded charcoal lobes around the face, ears to throat.
    for z in [6.08, 5.80, 5.52, 5.30]:
        for y in [-.46, -.14]:
            hplace(hm, (s * 3, y, z), (-s, 0, 0), (s * .85, .35, -.42), .80, .66, need=lambda p: abs(p.x) < 1.0)
    for y in [-.62, -.36]:
        lobe(hm, Vector((s * .30, y, 5.30)), Vector((s * .4, -.2, -1)), Vector((s * .25, .1, -1)), .66, .58, .12)
for y in [-.30, 0.0]:
    for x in [0, .30]:
        for s in ([1] if x < .01 else [-1, 1]):
            hplace(hm, (s * x, y, 9), (0, 0, -1), (s * x * .5, 1, -.25), .76, .64)
head_clumps = CLUMPS.get(id(hb), []) + CLUMPS.get(id(hm), [])
cheek_tufts = prefuse([hb.make('Cheek tufts', 'fur')], 'Cheek tufts', .016, 6)
ruff = prefuse([hm.make('Face ruff', 'mane')], 'Face ruff', .018, 8)
hp += [cheek_tufts, ruff]
muzzle_src = copy_of(muzzle_parts, 'SRC_muzzle')
ruff_src = copy_of([ruff], 'SRC_ruff')
fur_src = copy_of([o for o in hp if o not in muzzle_parts and o != ruff], 'SRC_headfur')
bpy.data.objects.remove(hprobe, do_unlink=True)
head = fuse_to(hp, 'AlphaWolf_Head', 'fur', .014, 2300, 2, .45)
head.data.materials.clear()
head.data.materials.append(paint('fur', (('mane', 'ManeMask'), ('cream', 'CreamMask'), ('inner', 'InnerMask'), ('mouth', 'MouthMask'))))
mt = bvh_of(muzzle_src)
rt = bvh_of(ruff_src)
ft = bvh_of(fur_src)


def inner_ear(c, nrm):
    for s, (B, up, side, fwd, h, hw) in EARS.items():
        if nrm.dot(fwd) < .35:
            continue
        rel = c - B
        u = rel.dot(side)
        v = rel.dot(up)
        dep = rel.dot(fwd)
        if dep < -.08 or v < .12 * h or v > .86 * h:
            continue
        tri = [Vector((-hw, 0)), Vector((hw, 0)), Vector((0, h))]
        cen = sum(tri, Vector((0, 0))) / 3
        tri = [cen + (t - cen) * .66 for t in tri]
        q = Vector((u, v))

        def sd(p1, p2):
            return (p2.x - p1.x) * (q.y - p1.y) - (p2.y - p1.y) * (q.x - p1.x)
        d1, d2, d3 = sd(tri[0], tri[1]), sd(tri[1], tri[2]), sd(tri[2], tri[0])
        if not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0)):
            return True
    return False


masks = {'ManeMask': [], 'CreamMask': [], 'InnerMask': [], 'MouthMask': []}
for v in head.data.vertices:
    c = v.co
    nrm = v.normal
    dm = mt.find_nearest(c)[3]
    dr = rt.find_nearest(c)[3]
    df = ft.find_nearest(c)[3]
    masks['InnerMask'].append(1.0 if inner_ear(c, nrm) else 0.0)
    masks['ManeMask'].append(smooth01(.04, -.04, dr - min(dm, df)))
    masks['CreamMask'].append(max(smooth01(.03, -.03, dm - df) * smooth01(-.74, -.86, c.y),
                                  smooth01(-.80, -.90, c.y) * smooth01(5.70, 5.60, c.z) * smooth01(.62, .50, abs(c.x))))
    masks['MouthMask'].append(smooth01(.20, .14, abs(c.x)) * smooth01(-.86, -.94, c.y) * smooth01(-.45, -.70, nrm.z) *
                              smooth01(5.42, 5.36, c.z))
for k in masks:
    masks[k] = relax_attr(head, masks[k], 1 if k in ('InnerMask', 'MouthMask') else 2)
masks['CreamMask'] = [c * (1 - r) * (1 - i) for c, r, i in zip(masks['CreamMask'], masks['ManeMask'], masks['InnerMask'])]
for k, vals in masks.items():
    set_attr(head, k, vals)
for o in (muzzle_src, ruff_src, fur_src):
    bpy.data.objects.remove(o, do_unlink=True)
set_attr(head, 'JawMask', [0.0] * len(head.data.vertices))
log('HEAD tris', len(head.data.polygons))

''')

rep("""jaw = fuse_to(jaw_parts, 'Jaw piece', 'cream', .012, 420, 2, .4)
slot_j = set_materials(jaw, ['cream', 'mouth', 'tongue'])
for p in jaw.data.polygons:
    c = p.center
    if p.normal.z > .4 and c.z > 5.25:
        p.material_index = slot_j['tongue' if abs(c.x) < .11 and c.y < -.85 else 'mouth']""",
    """jaw = fuse_to(jaw_parts, 'Jaw piece', 'cream', .012, 420, 2, .4)
jaw.data.materials.clear()
jaw.data.materials.append(paint('cream', (('mouth', 'MouthMask'), ('tongue', 'TongueMask'))))
mo = [smooth01(.30, .60, v.normal.z) * smooth01(5.24, 5.30, v.co.z) * smooth01(.24, .16, abs(v.co.x)) for v in jaw.data.vertices]
to_ = [m_ * smooth01(.13, .08, abs(v.co.x)) * smooth01(-.80, -.90, v.co.y) for m_, v in zip(mo, jaw.data.vertices)]
set_attr(jaw, 'MouthMask', relax_attr(jaw, mo, 1))
set_attr(jaw, 'TongueMask', relax_attr(jaw, to_, 1))""")
rep("features.append(almond('Eye socket', p + f * .002, f, .165, .098, .035, roll, 'brow', .2))",
    "features.append(almond('Eye socket', p + f * .002, f, .185, .110, .035, roll, 'brow', .2))")
rep("glow.append(almond('Eye glow', p + f * .019, f, .132, .074, .028, roll, 'eye', .45))",
    "glow.append(almond('Eye glow', p + f * .019, f, .152, .086, .028, roll, 'eye', .45))")
rep("features.append(almond('Pupil', p + f * .040 + Vector((-s * .014, 0, -.004)), f, .034, .062, .014, 0, 'pupil', .3))",
    "features.append(almond('Pupil', p + f * .042 + Vector((-s * .014, 0, -.004)), f, .036, .070, .014, 0, 'pupil', .3))")
rep("""tail = fuse_to(tail_parts, 'AlphaWolf_Tail', 'mane', .016, 1300, 4, .55)
slot = set_materials(tail, ['mane', 'cream'])""", """tail = fuse_to(tail_parts, 'AlphaWolf_Tail', 'mane', .016, 1300, 4, .55)
tail.data.materials.clear()
tail.data.materials.append(paint('mane', (('cream', 'CreamMask'),)))""")
cut_between("for p in tail.data.polygons:\n    p.material_index = slot['cream'] if chain_param(p.center, TP) > .70 else slot['mane']",
            "log('TAIL', len(tail.data.polygons))",
            "set_attr(tail, 'CreamMask', relax_attr(tail, [smooth01(.62, .76, chain_param(v.co, TP)) for v in tail.data.vertices], 1))\n")
rep("for pos, power, size, col in [((-6, -9, 11), 2600, 8, (1, .96, .9)),",
    "for pos, power, size, col in [((-6, -9, 11), 2200, 8, (1, .96, .9)),")
open(p, 'w', encoding='utf-8').write(s)
print('patched')
s = open(p, encoding='utf-8').read()
rep("        clump(tb, c + r * rad * .8, r, tan, .62, .56, .15, .14, .10)", "        lobe(tb, c + r * rad * .8, r, tan, .64, .58, .10)")
rep("    clump(tb, TP[-1] + Vector((0, -.02, .06)) + r * .05, r + Vector((0, .2, -1)), Vector((0, .25, -1)), .40, .36, .13, .12, .08)",
    "    lobe(tb, TP[-1] + Vector((0, -.02, .06)) + r * .05, r + Vector((0, .2, -1)), Vector((0, .25, -1)), .42, .40, .08)")
open(p, 'w', encoding='utf-8').write(s)
print('patched tail')
