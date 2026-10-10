p = 'build_alpha_werewolf.py'
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert a in s, a[:100]
    s = s.replace(a, b, 1)


# mane: no rows above the ears
rep("for j, (z, hw) in enumerate([(6.62, .40), (6.42, .78),", "for j, (z, hw) in enumerate([(6.42, .70),")
rep("            fl = (s_ * x * .3, .55, .45) if up else (s_ * x * .28, .40, -1)", "            fl = (s_ * x * .3, .60, .20) if up else (s_ * x * .28, .40, -1)")
rep("ell('Mane flare', (0, .40, 6.30), (1.02, .50, .62)", "ell('Mane flare', (0, .40, 6.16), (1.00, .50, .52)")
# half-angle helper bones (volume keepers) at shoulders, elbows, knees
rep("# Toe-out of the paws (8 deg about the ankle) also turns the Foot/Toes bones.",
    """# Half-angle helpers: each sits on its joint and rotates halfway between its two
# neighbours; the middle of each skin blend band rides it, so a 120 deg bend becomes
# two 60 deg blends and the joint keeps its mass (no collapse, no candy wrapper).
for side, s in [('Left', 1), ('Right', -1)]:
    for hname, joint, child, parent in (('ShoulderHelper', 'UpperArm', 'UpperArm', 'Shoulder'), ('ElbowHelper', 'Forearm', 'Forearm', 'UpperArm'),
                                        ('KneeHelper', 'Shin', 'Shin', 'Thigh')):
        h, t, _ = BONES[side + joint]
        d = (Vector(t) - Vector(h)).normalized()
        BONES[side + hname] = [h, tuple(Vector(h) + d * .30), side + parent]
# Toe-out of the paws (8 deg about the ankle) also turns the Foot/Toes bones.""")
rep("        knee = smooth01(1.67, 1.77, z)", "        knee = smooth01(1.58, 1.86, z)")
rep("        upper_t = smooth01(3.73, 3.83, z) * (1 - handw)", "        upper_t = smooth01(3.64, 3.92, z) * (1 - handw)")
rep("                side + 'Forearm': (1 - smooth01(3.73, 3.83, z)) * (1 - handw), side + 'Hand': handw}",
    "                side + 'Forearm': (1 - smooth01(3.64, 3.92, z)) * (1 - handw), side + 'Hand': handw}")
rep("ARM_BLEND = [(2.2, .08), (4.4, .08), (5.1, .26)]", "ARM_BLEND = [(2.2, .08), (4.2, .10), (5.1, .40)]")
rep("""        for k, val in row.items():
            W[v.index, IDX[k]] += val
    W = laplace(o, W, 2, .6)""", """        def split(a_set, b, helper, mask=1.):
            wa = sum(row.get(a, 0) for a in a_set)
            wb = row.get(b, 0)
            tot = wa + wb
            if tot < 1e-6 or mask <= 0:
                return
            u = wb / tot
            h = 4 * u * (1 - u) * tot * .85 * mask
            for a in a_set:
                row[a] = row.get(a, 0) * (1 - h / tot)
            row[b] = wb * (1 - h / tot)
            row[helper] = row.get(helper, 0) + h
        split([side + 'Thigh'], side + 'Shin', side + 'KneeHelper')
        split([side + 'UpperArm'], side + 'Forearm', side + 'ElbowHelper')
        split(['Chest', 'Spine', 'Neck', 'Mane', side + 'Shoulder'], side + 'UpperArm', side + 'ShoulderHelper', smooth01(4.2, 4.6, z))
        for k, val in row.items():
            W[v.index, IDX[k]] += val
    W = laplace(o, W, 2, .6)""")
open(p, 'w', encoding='utf-8').write(s)

p = 'animate_game.py'
s = open(p, encoding='utf-8').read()
rep("        place(S + 'UpperArm', Q1)\n        place(S + 'Forearm', Q2)",
    "        place(S + 'UpperArm', Q1)\n        place(S + 'Forearm', Q2)\n"
    "        place(S + 'ShoulderHelper', slerp3(D[S + 'Shoulder'], Q1, .5))\n"
    "        place(S + 'ElbowHelper', slerp3(Q1, Q2, .5))")
rep("        place(S + 'Thigh', Q1)\n        place(S + 'Shin', Q2)",
    "        place(S + 'Thigh', Q1)\n        place(S + 'Shin', Q2)\n        place(S + 'KneeHelper', slerp3(Q1, Q2, .5))")
# swing foot clears the ground
rep("    ks = [(0, to.y, to.z), (.10, to.y + .30, to.z + .55)]", "    ks = [(0, to.y, to.z), (.10, to.y + .30, to.z + .72)]")
rep("swing=[(.28, .95, 1.50), (.56, -.78, 1.10)],", "swing=[(.28, .95, 1.62), (.56, -.78, 1.20)],")
# Death: smooth only fully released frames, then re-seat the body on the ground
rep("        lo, hi = max(1, fr[0] - 1), min(c.frames - 1, fr[-1])\n        for b in (S + 'Thigh', S + 'Shin', S + 'Foot', S + 'Toes'):",
    "        lo, hi = fr[0] + 1, min(c.frames - 1, fr[-1])\n        for b in (S + 'Thigh', S + 'Shin', S + 'KneeHelper', S + 'Foot', S + 'Toes'):")
rep("smooth_released_legs(CLIPS['Death'])", """smooth_released_legs(CLIPS['Death'])
for f in range(1, CLIPS['Death'].frames + 1):        # nothing below the ground after the smoothing
    B = CLIPS['Death'].bases[f]
    for _ in range(3):
        set_pose(B)
        zm = zmin(eval_verts())
        if zm >= -.004:
            break
        lift = R3['Pelvis'].transposed() @ Vector((0, 0, -zm))
        B['Pelvis'] = Matrix.Translation(lift) @ B['Pelvis']""")
open(p, 'w', encoding='utf-8').write(s)
print('helpers patch applied')
