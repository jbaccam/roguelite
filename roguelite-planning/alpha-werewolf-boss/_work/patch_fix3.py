p = 'build_alpha_werewolf.py'
s = open(p, encoding='utf-8').read()
def rep(a, b):
    global s
    assert a in s, a[:90]
    s = s.replace(a, b, 1)
rep("    pair(lambda s, r, y=y: placed(tuft_b, (s * 6, y, 4.86), (-s, 0, 0), (s * .55, .05, -1), .66, .58, .16))",
    "    pair(lambda s, r, y=y: placed(tuft_b, (s * 6, y, 4.86), (-s, 0, 0), (s * .25, .05, -1), .88, .62, .20, lift=.02))")
rep("pair(lambda s, r: placed(tuft_b, (s * 1.98, 5, 3.86), (0, -1, 0), (s * .35, .8, -.6), .64, .56, .16))",
    "pair(lambda s, r: placed(tuft_b, (s * 1.98, 5, 3.90), (0, -1, 0), (s * .25, .5, -1), .80, .56, .18, lift=.03))")
rep("    mane_m.append(smooth01(.05, -.05, tm.find_nearest(c)[3] - to.find_nearest(c)[3]))",
    "    mane_m.append(smooth01(.025, -.025, tm.find_nearest(c)[3] - to.find_nearest(c)[3]))")
rep("    cream_m.append(smooth01(-.07, .07, VHW(c.z) - abs(c.x))", "    cream_m.append(smooth01(-.04, .04, VHW(c.z) - abs(c.x))")
rep("mane_m = relax_attr(skin, mane_m, 2)\ncream_m = [c * (1 - m_) for c, m_ in zip(relax_attr(skin, cream_m, 2), mane_m)]",
    "mane_m = relax_attr(skin, mane_m, 1)\ncream_m = [c * (1 - m_) for c, m_ in zip(relax_attr(skin, cream_m, 1), mane_m)]")
rep("    masks['ManeMask'].append(smooth01(.04, -.04, dr - min(dm, df)))", "    masks['ManeMask'].append(smooth01(.025, -.025, dr - min(dm, df)))")
rep("    masks[k] = relax_attr(head, masks[k], 1 if k in ('InnerMask', 'MouthMask') else 2)", "    masks[k] = relax_attr(head, masks[k], 1)")
rep("set_attr(tail, 'CreamMask', relax_attr(tail, [smooth01(.62, .76, chain_param(v.co, TP)) for v in tail.data.vertices], 1))",
    "set_attr(tail, 'CreamMask', [smooth01(.66, .72, chain_param(v.co, TP)) for v in tail.data.vertices])")
open(p, 'w', encoding='utf-8').write(s)
print('patched 3')
