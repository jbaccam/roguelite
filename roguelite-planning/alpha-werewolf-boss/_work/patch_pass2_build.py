p = 'build_alpha_werewolf.py'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, a[:100]
    s = s.replace(a, b, 1)


def cut(a_mark, b_mark, new, include_b=False):
    global s
    a = s.index(a_mark)
    b = s.index(b_mark, a)
    if include_b:
        b = s.index('\n', b) + 1
    s = s[:a] + new + s[b:]


rep("K = 1.3\n", "K = 1.27     # raised head + bigger ears keep the ear tips at ~1.3x the regular werewolf\n")
rep("COL = {'fur': (108, 50, 42),", "COL = {'fur': (104, 52, 44),")      # the sheet's brown-maroon, less red

# ---- paint: directional fur strokes + lighter clump tips
rep("""    for src, lo, hi, a, b in [(noise.outputs['Fac'], 1 - variation, 1 + variation, .32, .68),
                              (attr('Cavity'), .72, 1.0, 0, 1), (attr('Clump'), .93, 1.07, -1, 1)]:""",
    """    mp = n.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (7.0, 7.0, 1.4)          # strokes run down the body
    l.new(tc.outputs['Object'], mp.inputs['Vector'])
    stroke = n.new('ShaderNodeTexNoise')
    stroke.inputs['Scale'].default_value = 2.2
    stroke.inputs['Detail'].default_value = 2.0
    stroke.inputs['Roughness'].default_value = .55
    l.new(mp.outputs['Vector'], stroke.inputs['Vector'])
    for src, lo, hi, a, b in [(noise.outputs['Fac'], 1 - variation, 1 + variation, .32, .68),
                              (stroke.outputs['Fac'], .93, 1.07, .35, .65),
                              (attr('Cavity'), .72, 1.0, 0, 1), (attr('Clump'), .93, 1.07, -1, 1), (attr('Tip'), 1.0, 1.20, 0, 1)]:""")

# ---- clumps remember their tip (for the tip highlight)
assert s.count("CLUMPS.setdefault(id(b), []).append((Vector(root) + d * L * .4, rng.uniform(-1, 1)))") == 2
s = s.replace("CLUMPS.setdefault(id(b), []).append((Vector(root) + d * L * .4, rng.uniform(-1, 1)))",
              "CLUMPS.setdefault(id(b), []).append((Vector(root) + d * L * .4, rng.uniform(-1, 1), verts[tip]))")
cut("for sec, cl in [('Body', body_clumps), ('Head', head_clumps), ('Tail', tail_clumps)]:", "# ------------------------------------------------------------------ final scale", '''for sec, cl in [('Body', body_clumps), ('Head', head_clumps), ('Tail', tail_clumps)]:
    o = FINALS[sec]
    kd = KDTree(len(cl))
    kt = KDTree(len(cl))
    for i, (p, val, tip) in enumerate(cl):
        kd.insert(p, i)
        kt.insert(tip, i)
    kd.balance()
    kt.balance()
    vals = []
    tips = []
    for v in o.data.vertices:
        co, i, d = kd.find(v.co)
        vals.append(cl[i][1] * max(0, 1 - d / .55) if i is not None else 0)
        co, i, d = kt.find(v.co)
        tips.append(max(0., 1 - d / .24) if i is not None else 0)
    set_attr(o, 'Clump', vals)
    set_attr(o, 'Tip', tips)
for sec in ['EyeGlow', 'Hands', 'Feet', 'Shorts']:
    o = FINALS[sec]
    set_attr(o, 'Clump', [0.0] * len(o.data.vertices))
    set_attr(o, 'Tip', [0.0] * len(o.data.vertices))

''')

# ---- longer neck, raised head, mane flaring up behind it
rep("         (5.58, 0, -.26, .72, .52, .70), (5.80, 0, -.38, .46, .40, .46)]",
    "         (5.58, 0, -.26, .72, .52, .70), (5.80, 0, -.38, .50, .42, .48), (6.04, 0, -.50, .42, .36, .40)]")
rep("BONES = {'Pelvis': [(0, .06, 2.92), (0, .04, 3.45), 'Root'], 'Spine': [(0, .04, 3.45), (0, 0, 4.10), 'Pelvis'],\n         'Chest': [(0, 0, 4.10), (0, -.14, 5.18), 'Spine'], 'Neck': [(0, -.14, 5.18), (0, -.42, 5.62), 'Chest'],\n         'Head': [(0, -.42, 5.62), (0, -.70, 6.40), 'Neck'],",
    "BONES = {'Pelvis': [(0, .06, 2.92), (0, .04, 3.45), 'Root'], 'Spine': [(0, .04, 3.45), (0, 0, 4.10), 'Pelvis'],\n         'Chest': [(0, 0, 4.10), (0, -.14, 5.18), 'Spine'], 'Neck': [(0, -.14, 5.18), (0, -.48, 5.86), 'Chest'],\n         'Head': [(0, -.48, 5.86), (0, -.76, 6.64), 'Neck'],")
rep("mane_base = [ell('Mane crown', (0, .04, 5.80), (1.32, .84, .86), paint('mane'), 32, 20),\n             ell('Mane hump', (0, .52, 5.00), (1.48, .72, 1.05), paint('mane'), 32, 20)]",
    "mane_base = [ell('Mane crown', (0, .14, 5.84), (1.30, .74, .86), paint('mane'), 32, 20),\n             ell('Mane hump', (0, .52, 5.00), (1.48, .72, 1.05), paint('mane'), 32, 20),\n             ell('Mane flare', (0, .40, 6.30), (1.02, .50, .62), paint('mane'), 28, 16)]")

# ---- body fur: the regular werewolf's layered leaf clumps, fused straight into the skin
cut("mane_b = Builder()\ntuft_b = Builder()\nchest_b = Builder()", "log('SKIN tris', len(skin.data.polygons))", '''mane_b = Builder()
fur_b = Builder()
bib_b = Builder()


def pair(fn):
    r = {'l': rng.uniform(-1, 1)}
    for s in [-1, 1]:
        fn(s, r)


def placed(b, origin, direction, flow, L, W, T, lift=.2, bend=.16, need=None):
    p, nrm = hit(origin, direction)
    if p is None or (need and not need(p)):
        return
    clump(b, p, nrm, flow, L, W, T, lift, bend)


def VHW(z):
    """Half-width of the cream chest V."""
    return max(0, .80 * (z - 3.85) / 1.30)


# Mane: an inverted shield of layered leaf clumps from the crown to mid-back (regular
# werewolf language, bigger and fuller), flaring up behind the head and over the shoulders.
for j, (z, hw) in enumerate([(6.62, .40), (6.42, .78), (6.22, 1.05), (6.00, 1.26), (5.78, 1.42), (5.56, 1.52), (5.34, 1.55),
                             (5.12, 1.50), (4.90, 1.40), (4.68, 1.22), (4.46, 1.00), (4.24, .74), (4.04, .44)]):
    step = .34
    offset = 0 if j % 2 else step / 2
    for x in [x for x in [offset + k * step for k in range(7)] if x <= hw + .01]:
        L = .70 + .16 * min(1, max(0, (z - 4) / 1.8))
        r = rng.uniform(-1, 1)
        up = z > 6.1                                   # top rows flare up and back behind the head
        for s_ in ([1] if x < .01 else [-1, 1]):
            fl = (s_ * x * .3, .55, .45) if up else (s_ * x * .28, .40, -1)
            placed(mane_b, (s_ * x, 6, z), (0, -1, 0), fl, L * (1 + .08 * r), .54, .17, .24, .20)
for x in [.62, .98, 1.32]:
    for y in [-.12, .22, .55]:
        pair(lambda s, r, x=x, y=y: placed(mane_b, (s * x, y, 9), (0, 0, -1), (s * .75, .3, -.55), .68 + .05 * r['l'], .52, .17, .22, .18,
                                          need=lambda p: p.z > 5.0))
for z in [5.26, 5.04, 4.82, 4.62]:
    for dx in [.12, .40, .66]:
        x = VHW(z) + dx
        if x > 1.36:
            continue
        pair(lambda s, r, z=z, x=x: placed(mane_b, (s * x, -5, z), (0, 1, 0), (s * .30, -.25, -1), .60, .50, .16, .16, .14,
                                          need=lambda p: p.z > 4.45))
# Cream chest bib: broad pale clumps lying flat in a V, rows overlapping downward.
for j, z in enumerate([5.14, 4.90, 4.66, 4.42, 4.18, 3.98]):
    hw = VHW(z)
    step = .34
    offset = 0 if j % 2 == 0 or hw < .2 else step / 2
    for x in [x for x in [offset + k * step for k in range(5)] if x <= hw + .02]:
        for s in ([1] if x < .01 else [-1, 1]):
            placed(bib_b, (s * x, -5, z), (0, 1, 0), (s * x * .15, -.2, -1), .62, .56, .11, .08, .10)
# Russet: layered clumps over the shoulders and upper arms ...
for z in [5.00, 4.76, 4.52, 4.28]:
    for y in [-.30, -.02, .26]:
        pair(lambda s, r, z=z, y=y: placed(fur_b, (s * 6, y, z), (-s, 0, 0), (s * .45, .05 * y, -1), .52 + .04 * r['l'], .46, .15, .16, .14))
# ... tufts at the elbows and outer forearms ...
for z in [3.94, 3.72]:
    for o in [-.15, .15]:
        pair(lambda s, r, z=z, o=o: placed(fur_b, (s * (1.93 + o), 5, z), (0, -1, 0), (s * .35, .75, -.7), .54, .48, .15, .22, .18))
for z in [3.36, 3.04]:
    for y in [-.22, .14]:
        pair(lambda s, r, z=z, y=y: placed(fur_b, (s * 6, y, z), (-s, 0, 0), (s * .6, .1, -1), .66 + .05 * r['l'], .50, .15, .22, .17))


def cuff(axis, z, count, L, W, skip_inner=False):
    for k in range(count):
        a = (k + .5 * (round(z * 10) % 2)) * math.tau / count
        for s in [-1, 1]:
            c = Vector((s * axis[0], axis[1], z))
            r = Vector((s * math.cos(a), math.sin(a), 0))
            if skip_inner and r.x * s < -.75:
                continue
            placed(fur_b, c + r * .9, -r, Vector((0, 0, -1)) + r * .35, L, W, .13, .18, .14)


# ... shaggy forearm and calf cuffs (layered rings) ...
for z in [3.30, 3.02, 2.76]:
    cuff((2.06, -.03), z, 9, .52, .44)
cuff((2.16, -.05), 2.62, 9, .42, .40)
for z in [1.40, 1.16, .92]:
    cuff((.87, .02), z, 9, .48, .42, skip_inner=True)
cuff((.88, .15), .66, 9, .40, .38)
for o in [-.15, .15]:
    pair(lambda s, r, o=o: placed(fur_b, (s * (.84 + o), -5, 1.74), (0, 1, 0), (s * .2, -.2, -1), .42, .40, .12, .14, .12))
# ... and sparse locks on the back below the mane.
for x in [.30, .72]:
    pair(lambda s, r, x=x: placed(fur_b, (s * x, 5, 3.74), (0, -1, 0), (s * .3, .4, -1), .42, .40, .13, .14, .12))

mane_c = mane_b.make('Mane clumps', 'mane')
fur_c = fur_b.make('Fur clumps', 'fur')
bib_c = bib_b.make('Bib clumps', 'cream')
body_clumps = CLUMPS.get(id(mane_b), []) + CLUMPS.get(id(fur_b), []) + CLUMPS.get(id(bib_b), [])
src_mane = copy_of(mane_base + [mane_c], 'SRC_mane')
src_bib = copy_of([bib_c], 'SRC_bib')
src_other = copy_of(base + [fur_c], 'SRC_other')
log('fusing body skin')
skin = fuse_to(base + mane_base + [mane_c, fur_c, bib_c], 'AlphaWolf_Body', 'fur', .022, 11000, 4, .55)
skin.data.materials.clear()
skin.data.materials.append(paint('fur', (('mane', 'ManeMask'), ('cream', 'CreamMask'))))
tm = bvh_of(src_mane)
tb_ = bvh_of(src_bib)
to = bvh_of(src_other)
mane_m = []
cream_m = []
for v in skin.data.vertices:
    c = v.co
    nrm = v.normal
    dm = tm.find_nearest(c)[3]
    db = tb_.find_nearest(c)[3]
    do = to.find_nearest(c)[3]
    mane_m.append(smooth01(.02, -.02, dm - min(db, do)))
    vz = (smooth01(-.015, .015, VHW(c.z) - abs(c.x)) * smooth01(-.02, -.30, nrm.y) * smooth01(3.80, 3.98, c.z) *
          smooth01(5.45, 5.30, c.z))
    cream_m.append(max(vz, smooth01(.02, -.02, db - min(dm, do))))
cream_m = [c * (1 - m_) for c, m_ in zip(cream_m, mane_m)]
set_attr(skin, 'ManeMask', mane_m)
set_attr(skin, 'CreamMask', cream_m)
for o in (src_mane, src_bib, src_other, probe):
    bpy.data.objects.remove(o, do_unlink=True)
''')

# ---- head: bigger ears; face ruff and cheek fur as leaf clumps (no lobes)
rep("    hw = .31\n", "    hw = .37\n")
rep("    T = Vector((s * .72, -.62, 6.96))", "    T = Vector((s * .76, -.62, 7.00))")
cut("hb = Builder()     # russet cheek tufts", "mt = bvh_of(muzzle_src)", '''hb = Builder()     # russet cheek clumps
hm = Builder()     # charcoal face ruff + crown


def hplace(b, origin, direction, flow, L, W, T, lift=.2, bend=.14, need=None):
    loc, nor, i, d = hbv.ray_cast(Vector(origin), Vector(direction).normalized(), 10)
    if loc is None or (need and not need(loc)):
        return
    clump(b, loc, nor, flow, L, W, T, lift, bend)


for s in [-1, 1]:
    for root, flow, L in [((.55, -.80, 5.62), (.85, .35, -.35), .44), ((.52, -.72, 5.44), (.7, .35, -.7), .42),
                          ((.56, -.66, 5.80), (.8, .4, 0), .38), ((.46, -.90, 5.33), (.5, .2, -.9), .36)]:
        clump(hb, Vector((s * root[0], root[1], root[2])), Vector((s, -.3, 0)), Vector((s * flow[0], flow[1], flow[2])), L, .34, .14, .15, .12)
    # Face ruff: layered charcoal leaf clumps flaring out and back from behind the cheeks.
    for z in [6.14, 5.92, 5.70, 5.48, 5.28]:
        for y in [-.50, -.28, -.06]:
            big = 1.12 if 5.5 < z < 6.0 else .96
            hplace(hm, (s * 3, y, z), (-s, 0, 0), (s * .80, .35, -.45), .62 * big, .50, .17, .2, .15, need=lambda p: abs(p.x) < 1.0)
    for y in [-.66, -.42]:
        clump(hm, Vector((s * .30, y, 5.30)), Vector((s * .4, -.2, -1)), Vector((s * .25, .1, -1)), .56, .46, .16, .15, .12)
for y in [-.30, -.04]:
    for x in [0, .28]:
        for s in ([1] if x < .01 else [-1, 1]):
            hplace(hm, (s * x, y, 9), (0, 0, -1), (s * x * .5, 1, .1), .60, .48, .16, .3, .15)
hplace(hb, (0, -.76, 9), (0, 0, -1), (0, 1, .1), .38, .34, .13, .25, .12)
head_clumps = CLUMPS.get(id(hb), []) + CLUMPS.get(id(hm), [])
cheek_c = hb.make('Cheek clumps', 'fur')
ruff = hm.make('Face ruff', 'mane')
hp += [cheek_c, ruff]
muzzle_src = copy_of(muzzle_parts, 'SRC_muzzle')
ruff_src = copy_of([ruff], 'SRC_ruff')
fur_src = copy_of([o for o in hp if o not in muzzle_parts and o != ruff], 'SRC_headfur')
bpy.data.objects.remove(hprobe, do_unlink=True)
head = fuse_to(hp, 'AlphaWolf_Head', 'fur', .014, 2500, 2, .45)
head.data.materials.clear()
head.data.materials.append(paint('fur', (('mane', 'ManeMask'), ('cream', 'CreamMask'), ('inner', 'InnerMask'), ('mouth', 'MouthMask'))))
''')
# raise the head (and its jaw hinge) above the mane line
rep("BONES['Jaw'] = [tuple(HP + (Vector(p) - HP) * HS) for p in BONES['Jaw'][:2]] + ['Head']",
    """BONES['Jaw'] = [tuple(HP + (Vector(p) - HP) * HS) for p in BONES['Jaw'][:2]] + ['Head']
HO = Vector((0, -.06, .24))          # more face and neck above the shoulders (sheet)
for o in (head, eyeglow):
    o.data.transform(Matrix.Translation(HO))
    o.data.update()
BONES['Jaw'] = [tuple(Vector(p) + HO) for p in BONES['Jaw'][:2]] + ['Head']""")

# ---- tail: one bushy tapered tail of layered leaf clumps, cream tip
cut("tb = Builder()\nfor i in range(1, len(TP)):", "tail_clumps = CLUMPS.get(id(tb), [])", '''tb = Builder()
for i in range(1, len(TP)):
    tan = (TP[i] - TP[i - 1]).normalized()
    u = Vector((1, 0, 0))
    w = tan.cross(u)
    for k, t in enumerate((.25, .75)):
        c = TP[i - 1].lerp(TP[i], t)
        rad = TR[i - 1] * (1 - t) + TR[i] * t
        L = .52 + .22 * math.sin(math.pi * min(1, (i - 1 + t) / 4.2))
        for a in range(6):
            ang = math.radians(a * 60 + 30 * ((i * 2 + k) % 2))
            r = u * math.cos(ang) + w * math.sin(ang)
            clump(tb, c + r * rad * .8, r, tan + r * .15, L, .50, .14, .14, .10)
for a in [0, 120, 240]:
    r = Vector((math.cos(math.radians(a)), 0, math.sin(math.radians(a))))
    clump(tb, TP[-1] + Vector((0, -.02, .06)) + r * .05, r + Vector((0, .2, -1)), Vector((0, .25, -1)), .40, .36, .13, .12, .08)
''')
rep("tail = fuse_to(tail_parts, 'AlphaWolf_Tail', 'mane', .016, 1300, 4, .55)", "tail = fuse_to(tail_parts, 'AlphaWolf_Tail', 'mane', .016, 1600, 3, .5)")
# shoulder bone carries more of the deltoid in big raises
rep("        shoulder = upper_t * smooth01(4.78, 5.24, z) * .7", "        shoulder = upper_t * smooth01(4.70, 5.24, z) * .85")
open(p, 'w', encoding='utf-8').write(s)
print('pass2 build patch applied')
