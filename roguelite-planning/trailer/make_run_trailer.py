"""Wavebreaker run trailer: one solo Pine Valley Normal run, wave 1 to the Hammer Brute win.

Run:  python roguelite-planning/trailer/make_run_trailer.py [--preview]
Same track, beat grid, text and transitions as make_trailer.py; every shot comes from the
2026-10-20 recording (C:/Users/Jeremiah/Videos/2026-10-20 09-44-04.mp4). Shot sources are seconds
into that recording: wave 1 0-30, first shop 30-39, Katana merges to Tier III 243-249, Pop Goes
the Zombie 380-448, Hammer Brute 542-650, YOU WON at 650.
"""
import make_trailer as M
from make_trailer import at, D1, D4, END, GOLD, LIME

M.C['run'] = '../2026-10-20 09-44-04.mp4'
R = 'run'

SHOTS = [
    (0.0, D1, R, 1.0, 1.0, {}),
    # Section A: wave 1, level up, shop, merge, the swarm grows
    (at(0), at(4), R, 3.0, 1.0, {'tr': 'zoom', 'flash': 1, 'text': ('SURVIVE THE ', 'SWARM', LIME)}),
    (at(4), at(8), R, 30.3, 1.0, {'tr': 'whip_l', 'pill': ('power-bicep', 'LEVEL UP')}),
    (at(8), at(12), R, 33.0, 1.0, {'pill': ('store-bag', 'SHOP')}),
    (at(12), at(16), R, 186.0, 1.0, {'tr': 'whip_r'}),
    (at(16), at(20), R, 242.4, 1.0, {'tr': 'whip_l', 'pill': ('store-bag', 'SHOP')}),
    (at(20), at(24), R, 247.0, 1.0, {'pill': ('store-bag', 'SHOP'), 'nopop': 1, 'text': ('MERGE TO ', 'TIER III', GOLD), 'text_y': 0.695}),
    (at(24), at(28), R, 275.5, 1.0, {'tr': 'whip_r'}),
    (at(28), at(32), R, 358.5, 1.0, {'tr': 'whip_l'}),
    # Section B: wave 10, Pop Goes the Zombie
    (at(32), at(36), R, 382.6, 1.0, {'tr': 'zoom', 'flash': 1}),
    (at(36), at(40), R, 397.0, 1.0, {'tr': 'whip_r'}),
    (at(40), at(44), R, 405.5, 1.0, {}),
    (at(44), at(48), R, 417.5, 1.0, {'tr': 'whip_l'}),
    (at(48), at(52), R, 429.5, 1.0, {'tr': 'whip_r'}),
    (at(52), at(56), R, 444.5, 1.0, {}),
    (at(56), at(60), R, 316.5, 1.0, {'tr': 'whip_l'}),
    (at(60), at(64), R, 342.5, 1.0, {'tr': 'whip_r'}),
    # Section C: the Hammer Brute
    (at(64), at(68), R, 542.3, 1.0, {'tr': 'zoom', 'flash': 1}),
    (at(68), at(70), R, 552.2, 1.0, {'tr': 'whip_l', 'text': ('BEAT THE ', 'BOSS', GOLD)}),
    (at(70), at(72), R, 562.0, 1.0, {'tr': 'whip_r'}),
    (at(72), at(74), R, 566.0, 1.0, {'tr': 'whip_l'}),
    (at(74), at(76), R, 588.0, 1.0, {'tr': 'whip_r'}),
    (at(76), at(80), R, 596.0, 1.0, {}),
    # Section D: the finish, the win screen lands on the last drop
    (at(80), at(84), R, 628.0, 1.0, {'tr': 'whip_l'}),
    (at(84), D4 - 3.167, R, 631.5, 1.0, {'tr': 'whip_r'}),
    (D4 - 3.167, D4, R, 646.9, 1.0, {'tr': 'zoom', 'nopunch': 1}),
    (D4, END, R, 650.07, 1.0, {'nopunch': 1, 'title': 1}),
]

if __name__ == '__main__':
    M.main(SHOTS, 'wavebreaker-run-trailer')
