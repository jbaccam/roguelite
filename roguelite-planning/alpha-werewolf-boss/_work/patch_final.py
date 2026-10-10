import sys
# ---------------------------------------------------------------- build weights
p = 'build_alpha_werewolf.py'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, a[:100]
    s = s.replace(a, b, 1)


rep("        if mane[v.index] > .5 and z > 4.9 and ax < 1.25:\n            arm_f *= .3",
    "        if mane[v.index] > .5 and z > 4.6:\n            arm_f *= .12          # the mane rides the shoulders/chest, never the raised arm")
rep("        trap = smooth01(.55, 1.10, ax) * smooth01(4.85, 5.30, z) * .5 * (1 - neck)",
    "        trap = smooth01(.55, 1.10, ax) * smooth01(4.85, 5.30, z) * .5 * (1 - neck)\n"
    "        if mane[v.index] > .5:\n"
    "            trap = max(trap, .6 * smooth01(.5, 1.0, ax) * smooth01(4.6, 5.0, z) * (1 - neck))")
rep("        knee = smooth01(1.63, 1.81, z)", "        knee = smooth01(1.67, 1.77, z)")
rep("        upper_t = smooth01(3.69, 3.87, z) * (1 - handw)", "        upper_t = smooth01(3.73, 3.83, z) * (1 - handw)")
rep("                side + 'Forearm': (1 - smooth01(3.69, 3.87, z)) * (1 - handw), side + 'Hand': handw}",
    "                side + 'Forearm': (1 - smooth01(3.73, 3.83, z)) * (1 - handw), side + 'Hand': handw}")
rep("        shoulder = upper_t * smooth01(4.78, 5.24, z) * .6", "        shoulder = upper_t * smooth01(4.78, 5.24, z) * .7")
rep("ARM_BLEND = [(2.2, .08), (4.4, .08), (5.1, .44)]", "ARM_BLEND = [(2.2, .08), (4.4, .08), (5.1, .26)]")
rep("    W = laplace(o, W, 2)\n    return W", "    W = laplace(o, W, 2, .6)\n    return W")
open(p, 'w', encoding='utf-8').write(s)

# ---------------------------------------------------------------- animation
p = 'animate_game.py'
s = open(p, encoding='utf-8').read()
# hands swing wider of the thighs
rep("armF=(-.30, -1.45, 1.15), armB=(-.05, 1.05, .55), armLift=-.15, shE=2, shP=7, fing=26, wrist=(-8, 0, 0),",
    "armF=(-.10, -1.45, 1.15), armB=(.18, 1.05, .55), armLift=-.15, shE=2, shP=7, fing=26, wrist=(-8, 0, 0),")
rep("armF=(-.40, -1.70, 1.00), armB=(0, 1.35, .85), armLift=-.15, shE=4, shP=10, fing=8, wrist=(-12, 0, 0),",
    "armF=(-.15, -1.70, 1.20), armB=(.20, 1.35, 1.00), armLift=-.15, shE=4, shP=10, fing=8, wrist=(-12, 0, 0),")
# Howl: more clavicle, arms clear of the knees in the crouch, head-back spread down the spine
rep("'chest': ch(HT, [0, 10, 0, -12, -13, 0]),\n      'neck': ch(HT, [0, 10, -4, -18, -19, 0]), 'head': ch(HT, [0, 14, -6, -24, -26, 0]),",
    "'chest': ch(HT, [0, 10, 0, -15, -16, 0]),\n      'neck': ch(HT, [0, 10, -4, -15, -16, 0]), 'head': ch(HT, [0, 14, -6, -24, -25, 0]),")
rep("      'sh': ch(HT, [(0, 0), (-2, 8), (4, 0), (10, -10), (10, -10), (0, 0)]),",
    "      'sh': ch(HT, [(0, 0), (-2, 8), (6, 0), (16, -14), (16, -14), (0, 0)]),")
rep("Vector((0, 0, 0)), Vector((-.30, -.45, .35)), Vector((.40, -.20, .60)), Vector((2.0, -.20, 1.85)),",
    "Vector((0, 0, 0)), Vector((-.05, -.55, .45)), Vector((.40, -.20, .60)), Vector((2.0, -.20, 1.85)),")
# ClawRake: clavicle takes more of the raise
rep("      'sh': ch(KT, [(0, 0), (6, -2), (20, -8), (16, 0), (8, 10), (4, 14), (2, 12), (0, 10), (0, 4), (0, 1), (0, 0)]),",
    "      'sh': ch(KT, [(0, 0), (8, -2), (26, -10), (22, 0), (14, 12), (6, 15), (2, 12), (0, 10), (0, 4), (0, 1), (0, 0)]),")
# ChargeStart: slower reach to the ground, the hand arcs outward/up while blending into the run
rep("      'kR': ch(CT, [0, .55, 1, 1]),", "      'kR': ch([0, .18, .36, .50], [0, .45, 1, 1]),")
rep("    return blend_desc(crouch_desc(.50), RUN0, sm(.50, CS_END, t), lift={'Left': .45})",
    "    return blend_desc(crouch_desc(.50), RUN0, sm(.50, CS_END, t), lift={'Left': .45}, arc={'Right': Vector((-.75, 0, .65))})")
rep("def blend_desc(d1, d2, w, lift=None):", "def blend_desc(d1, d2, w, lift=None, arc=None):")
rep("            d[k] = {'mode': 'abs', 'w': i1['wrist'][S].lerp(i2['wrist'][S], w), 'pole': i1['pole'][S].lerp(i2['pole'][S], w)}",
    "            d[k] = {'mode': 'abs', 'w': i1['wrist'][S].lerp(i2['wrist'][S], w), 'pole': i1['pole'][S].lerp(i2['pole'][S], w)}\n"
    "            if arc and S in arc:\n"
    "                d[k]['w'] = d[k]['w'] + arc[S] * math.sin(math.pi * w)")
# Death: hands clear of the knees in the slump; legs lift before they roll; knee pole carried by the pelvis
rep("'armL': ch(DT, [Vector(v) for v in [(0, 0, 0), (.5, .3, 1.2), (.2, -.3, .3), (-.2, -.6, .4), (.3, -1.4, 1.0),",
    "'armL': ch(DT, [Vector(v) for v in [(0, 0, 0), (.5, .3, 1.2), (.3, -.3, .4), (.4, -.6, .6), (.4, -1.4, 1.0),")
rep("'armR': ch(DT, [Vector(v) for v in [(0, 0, 0), (-.6, .4, 1.0), (-.3, -.2, .4), (0, -.4, .2), (-.2, -.2, .7),",
    "'armR': ch(DT, [Vector(v) for v in [(0, 0, 0), (-.6, .4, 1.0), (-.4, -.2, .5), (-.4, -.4, .4), (-.3, -.2, .7),")
rep("    planted = {'Left': foot_ball('Left', BALL['Left']), 'Right': step('Right', t, .12, .38, BALL['Right'], BALL['Right'] + Vector((-.15, .95, 0)), .30, 8)}",
    "    planted = {'Left': foot_ball('Left', BALL['Left']), 'Right': step('Right', t, .12, .38, BALL['Right'], BALL['Right'] + Vector((-.15, .95, 0)), .30, 8)}\n"
    "    for S, s in SIDES:\n"
    "        planted[S]['pole'] = E(d['pelR']) @ LIMBS[S + 'Thigh']['p0']")
rep("            d['foot' + S] = {'ankle': p['ankle'].lerp(Tp @ relax[S], w), 'R': slerp3(p['R'], Rr, w), 'toe': slerp3(p['toe'], Rr, w), 'yaw': 0,\n                             'pole': E((pr[0] * w, pr[1] * w, pr[2] * w)) @ LIMBS[S + 'Thigh']['p0']}",
    "            d['foot' + S] = {'ankle': p['ankle'].lerp(Tp @ relax[S], w) + Vector((0, 0, .55 * math.sin(math.pi * w))),\n"
    "                             'R': slerp3(p['R'], Rr, w * w), 'toe': slerp3(p['toe'], Rr, w * w), 'yaw': 0,\n"
    "                             'pole': E(pr) @ LIMBS[S + 'Thigh']['p0']}")
# ground check names the section
rep("        zm = zmin(V)\n        if zm < gmin[0]:\n            gmin = (zm, f)",
    "        zm, zsec = min((float(v[:, 2].min()), k) for k, v in V.items())\n        if zm < gmin[0]:\n            gmin = (zm, f, zsec)")
rep("    gmin = (9, 0)", "    gmin = (9, 0, '')")
rep("    cm['groundLowest'] = {'z': round(gmin[0], 4), 'frame': gmin[1], 'ok': gmin[0] >= -.05}",
    "    cm['groundLowest'] = {'z': round(gmin[0], 4), 'frame': gmin[1], 'section': gmin[2], 'ok': gmin[0] >= -.05}")
open(p, 'w', encoding='utf-8').write(s)
print('final patch applied')
