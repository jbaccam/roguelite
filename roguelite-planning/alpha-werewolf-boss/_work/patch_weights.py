p = 'build_alpha_werewolf.py'
s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:90]
    s = s.replace(a, b, 1)
# Narrow hinge blends (crease instead of linear-blend collapse) and less weight smoothing.
rep("        leg = 1 - smooth01(2.80, 3.22, z)", "        leg = 1 - smooth01(2.84, 3.10, z)")
rep("        knee = smooth01(1.52, 1.92, z)", "        knee = smooth01(1.63, 1.81, z)")
rep("        hip_blend = smooth01(2.62, 3.05, z) * .5", "        hip_blend = smooth01(2.62, 3.05, z) * .3")
rep("        upper_t = smooth01(3.58, 4.02, z) * (1 - handw)", "        upper_t = smooth01(3.69, 3.87, z) * (1 - handw)")
rep("                side + 'Forearm': (1 - smooth01(3.58, 4.02, z)) * (1 - handw), side + 'Hand': handw}",
    "                side + 'Forearm': (1 - smooth01(3.69, 3.87, z)) * (1 - handw), side + 'Hand': handw}")
rep("    W = laplace(o, W, 6)\n    return W", "    W = laplace(o, W, 2)\n    return W")
open(p, 'w', encoding='utf-8').write(s)
print('weights patched')
