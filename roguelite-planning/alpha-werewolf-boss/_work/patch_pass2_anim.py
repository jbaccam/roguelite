s = open('build_alpha_werewolf.py', encoding='utf-8').read()
a = "for z in [1.40, 1.16, .92]:\n    cuff((.87, .02), z, 9, .48, .42, skip_inner=True)"
assert a in s
s = s.replace(a, "for z in [1.36, 1.08]:\n    cuff((.87, .02), z, 8, .50, .44, skip_inner=True)")
open('build_alpha_werewolf.py', 'w', encoding='utf-8').write(s)

p = 'animate_game.py'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, a[:100]
    s = s.replace(a, b, 1)


# ---- auto clavicle: big arm raises lift/protract the Shoulder bone so the deltoid keeps its mass
rep("""        el, pr = d['sh' + S]
        place(S + 'Shoulder', D['Chest'] @ rot((0, -s, 0), el) @ rot((0, 0, -s), pr))
        A = P[S + 'Shoulder'] @ LOC0[S + 'UpperArm'].translation
        a = d['arm' + S]""", """        el, pr = d['sh' + S]
        a = d['arm' + S]
        for it in range(2):
            place(S + 'Shoulder', D['Chest'] @ rot((0, -s, 0), el) @ rot((0, 0, -s), pr))
            A = P[S + 'Shoulder'] @ LOC0[S + 'UpperArm'].translation
            if it:
                break
            if a['mode'] == 'chest':
                Cp = Tc @ (WRIST0[S] + a['off'])
            elif a['mode'] == 'dir':
                Cp = A + Vector(a['dir']).normalized() * a['dist']
            else:
                Cp = Vector(a['w']) if a['mode'] == 'abs' else (Tc @ (WRIST0[S] + a['off'])).lerp(Vector(a['w']), a['k'])
            down = (D['Chest'] @ Vector((0, 0, -1)))
            raise_deg = math.degrees((Cp - A).angle(down)) if (Cp - A).length > 1e-6 else 0
            extra = max(0., raise_deg - 70.) * .45                       # clavicle helps above ~70 deg
            info.setdefault('autoClavicleMax', 0.)
            info['autoClavicleMax'] = max(info['autoClavicleMax'], extra)
            el += extra
            fwd = (D['Chest'] @ Vector((0, -1, 0))).dot((Cp - A).normalized())
            pr += max(0., fwd) * extra * .5""")
# ---- ClawRake: around-the-side windup (not overhead), arm never far above the shoulder line
rep("""      'sh': ch(KT, [(0, 0), (8, -2), (26, -10), (22, 0), (14, 12), (6, 15), (2, 12), (0, 10), (0, 4), (0, 1), (0, 0)]),""",
    """      'sh': ch(KT, [(0, 0), (6, -2), (12, -10), (10, 0), (8, 10), (4, 14), (2, 12), (0, 10), (0, 4), (0, 1), (0, 0)]),""")
rep("U(.70, .10, -.70), U(.80, .22, .55), U(.55, -.35, .75), U(.10, -.90, .25),",
    "U(.75, .12, -.65), U(.88, .30, .30), U(.72, -.45, .28), U(.25, -.90, .12),")
rep("'dist': ch(KT, [A0['Left'].length, 3.05, 2.45, 2.70, 3.10, 3.30,", "'dist': ch(KT, [A0['Left'].length, 3.05, 2.55, 2.80, 3.10, 3.30,")
# ---- sprint knees: lower heel kick / knee drive
rep("swing=[(.30, 1.35, 1.85), (.56, -.55, 1.55)],", "swing=[(.30, 1.20, 1.62), (.56, -.55, 1.42)],")
rep("swing=[(.28, 1.05, 1.70), (.56, -.80, 1.22)],", "swing=[(.28, .95, 1.50), (.56, -.78, 1.10)],")
# ---- Howl: head-back carried by the spine and chest, less by the neck
rep("'pelR': ch(HT, [0, 10, 2, -6, -6, 0]), 'spine': ch(HT, [0, 12, 2, -8, -8, 0]), 'chest': ch(HT, [0, 10, 0, -15, -16, 0]),\n      'neck': ch(HT, [0, 10, -4, -15, -16, 0]), 'head': ch(HT, [0, 14, -6, -24, -25, 0]),",
    "'pelR': ch(HT, [0, 10, 2, -7, -7, 0]), 'spine': ch(HT, [0, 12, 2, -11, -11, 0]), 'chest': ch(HT, [0, 10, 0, -18, -19, 0]),\n      'neck': ch(HT, [0, 8, -3, -9, -9, 0]), 'head': ch(HT, [0, 12, -6, -22, -23, 0]),")
rep("      'sh': ch(HT, [(0, 0), (-2, 8), (6, 0), (16, -14), (16, -14), (0, 0)]),",
    "      'sh': ch(HT, [(0, 0), (-2, 8), (6, 0), (10, -14), (10, -14), (0, 0)]),")
rep("Vector((.40, -.20, .60)), Vector((2.0, -.20, 1.85)), Vector((2.0, -.20, 1.95)), Vector((0, 0, 0))]),",
    "Vector((.40, -.20, .60)), Vector((2.0, -.20, 1.45)), Vector((2.0, -.20, 1.55)), Vector((0, 0, 0))]),")
# ---- Death: the released legs flop over 2-3 frames, not one (temporal filter on the leg rotations)
rep("sample('Death', 53, death_desc, ground=death_ground)", """sample('Death', 53, death_desc, ground=death_ground)


def smooth_released_legs(c, passes=6):
    for S, s in SIDES:
        fr = [f for f in range(c.frames + 1) if DEATH_FOOT[S].get(f, 0) > 0]
        if len(fr) < 3:
            continue
        lo, hi = max(1, fr[0] - 1), min(c.frames - 1, fr[-1])
        for b in (S + 'Thigh', S + 'Shin', S + 'Foot', S + 'Toes'):
            for _ in range(passes):
                q = [c.bases[f][b].to_quaternion() for f in range(c.frames + 1)]
                for f in range(lo, hi + 1):
                    a = q[f - 1].slerp(q[f + 1], .5)
                    m = q[f].slerp(a, .5).to_matrix().to_4x4()
                    m.translation = c.bases[f][b].translation
                    c.bases[f][b] = m


smooth_released_legs(CLIPS['Death'])""")
# ---- collision cores follow the build scale and the raised head
rep("TORSO_CORES = [('Pelvis', Vector((0, .05, 3.85)), Vector((1.10, .74, .62))), ('Spine', Vector((0, .02, 4.75)), Vector((1.08, .78, .55))),\n               ('Chest', Vector((0, -.08, 5.85)), Vector((1.40, .92, .80)))]\nHEAD_CORE = ('Head', Vector((0, -.82, 7.75)), Vector((.66, .60, .52)))\nLEG_CAPS = [(S + b, HEAD[S + b], HEAD[S + c], r) for S, s in SIDES for b, c, r in (('Thigh', 'Shin', .52), ('Shin', 'Foot', .42))]",
    "KF = json.loads((OUT / 'manifest.json').read_text())['scaleFromBaseUnits'] / 1.3\nTORSO_CORES = [('Pelvis', Vector((0, .05, 3.85)) * KF, Vector((1.10, .74, .62)) * KF), ('Spine', Vector((0, .02, 4.75)) * KF, Vector((1.08, .78, .55)) * KF),\n               ('Chest', Vector((0, -.08, 5.85)) * KF, Vector((1.40, .92, .80)) * KF)]\nHEAD_CORE = ('Head', Vector((0, -.692, 6.201)) * KF * 1.3, Vector((.66, .60, .52)) * KF)\nLEG_CAPS = [(S + b, HEAD[S + b], HEAD[S + c], r * KF) for S, s in SIDES for b, c, r in (('Thigh', 'Shin', .52), ('Shin', 'Foot', .42))]")
open(p, 'w', encoding='utf-8').write(s)
print('pass2 anim patch applied')
