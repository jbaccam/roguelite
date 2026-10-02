"""Humanoid attack choreography keyed for attack_design.Humanoid.

Wrist targets `w` are (lateral, forward, up) in units of that arm's reach
from its shoulder, measured in the chest frame; lateral is away from the body
on that arm's side. `pole` is the direction the elbow should point. `blade`
is where a held weapon points (lateral, forward, up). Pelvis and foot offsets
are (lateral, forward, up) in leg lengths. Chest/head are (pitch forward, yaw,
roll) degrees added to the idle posture; positive yaw turns the Right
shoulder back. `still` keys are velocity extremes (wind-up peak, follow-through
end). Right* bones carry the weapon for every armed humanoid.
"""
# Rest weapon directions measured from each model's hand-weighted geometry
# (grip centre to tip), the blade width axis, and the comfortable
# blade-to-forearm angle for that grip.
# Swords were turned 90 degrees in the hand (edge_forward_blades.py) so the
# edges run along the knuckle line; the second vector is that edge axis.
SWORD = ((-0.0015, -0.300, 0.954), (0, 0.954, 0.300), 80)
# Frozen Knight reference rebuild (2026-10-01, build_frozen_knight.py): the
# handle runs through the fist's finger tunnel in a diagonal hammer grip, 58
# degrees from the forearm (index side lower, wrist in line), so at rest the
# blade hangs forward and down. The edges lie in the blade/forearm plane (the
# punching line), so the flat faces the back of the hand. Measured on the built
# mesh: grip centre -> tip and blade width axis. The rest blade sits 58 degrees
# from the forearm; the comfortable strike grip is 50 (an 8-degree ulnar snap),
# which the preview solver measured as the best edge-first sweep for this grip.
KNIGHT_SWORD = ((-0.2226, -0.7477, -0.6256), (0.3747, 0.5229, -0.7656), 50)
DAGGER = ((0.895, -0.312, -0.318), (0.302, -0.1, 0.948), 85)
STAFF = ((0.01, 0, -1), (1, 0, 0), 57)
# Shaman's open casting hand: finger direction, palm normal (up at rest),
# rest wrist angle, and full orientation (the palm must face the target).
PALM = ((-0.11, -0.99, -0.03), (0, 0, 1), 25, True)

HUMANOIDS = {
    # Forward diagonal chop: sword cocked high behind the sword shoulder, then
    # brought over the top and driven forward and down at the target while
    # the off foot steps in, finishing low across the body. The swing plane
    # faces the target, so the leading edge (never the flat) meets it.
    'skeleton': {'weapon': {'Right': SWORD}, 'bladeLength': 1.2, 'rollWeight': 1.5, 'carryGrip': 80, 'clearWeight': 400, 'strikeWindow': (0, .66), 'settle': .24, 'keys': [
        {'t': 0},
        {'t': .16, 'pelvis': (0, -.02, -.02), 'chest': (-3, 12, 0),
         'Right': {'w': (.30, .05, .15), 'pole': (.6, -.5, -.6), 'blade': (.05, -.3, .95)}},
        {'t': .36, 'still': True, 'pelvis': (0, -.06, -.03), 'chest': (-8, 26, -3), 'head': (6, -18, 0),
         'Right': {'w': (.36, -.18, .72), 'pole': (1, .1, .35), 'blade': (-.05, -.88, .45)},
         'Left': {'w': (.30, .45, -.45), 'pole': (.3, -.6, -.7)}},
        {'t': .45, 'pelvis': (0, .08, -.06), 'chest': (2, 10, -2), 'head': (0, -8, 0),
         'Right': {'w': (.26, .40, .78), 'pole': (1, -.2, 0), 'blade': (-.02, .30, .95)},
         'Left': {'w': (.25, .30, -.55), 'pole': (.3, -.7, -.6)}, 'LeftFoot': (0, .30, .12)},
        {'t': .50, 'pelvis': (0, .16, -.09), 'chest': (14, -4, 2), 'head': (-10, 4, 0),
         'Right': {'w': (.08, .95, .18), 'pole': (1, -.3, -.4), 'blade': (-.10, .86, -.50)},
         'Left': {'w': (.25, -.05, -.70), 'pole': (.2, -.8, -.4)}, 'LeftFoot': (0, .42, 0)},
        # Follow-through stays in the cutting line, low and forward across the
        # body, instead of dropping the point straight down.
        {'t': .60, 'still': True, 'pelvis': (0, .17, -.11), 'chest': (12, -12, 4), 'head': (-8, 9, 0),
         'Right': {'w': (-.12, .74, -.22), 'pole': (1, -.2, -.5), 'blade': (-.36, .82, -.45)},
         'Left': {'w': (.30, -.20, -.75), 'pole': (.2, -.8, -.4)}, 'LeftFoot': (0, .42, 0)},
        # Recovery brings the sword back up the front to guard; routing the
        # point forward keeps it from flipping over.
        {'t': .72, 'pelvis': (0, .10, -.07), 'chest': (9, -6, 2), 'head': (-5, 5, 0),
         'Right': {'w': (.10, .55, -.25), 'pole': (1, -.3, -.5), 'blade': (-.08, .96, .20)},
         'LeftFoot': (0, .24, .06)},
        # Then settle straight into the ready carry.
        {'t': .86, 'pelvis': (0, .04, -.03), 'chest': (4, -3, 1), 'head': (-2, 2, 0), 'LeftFoot': (0, .08, .05)},
        {'t': 1},
    ]},
    # Heavy horizontal sweep: the knight hauls the sword back behind the
    # sword hip at chest height, then cuts flat across the front with the
    # whole torso while stepping in, finishing wrapped around the far side.
    # Rebuilt knight (2026-10-01): the cut keeps wrist, elbow and blade level
    # so the blade/forearm plane that holds the edges stays horizontal and the
    # edge leads. The palm stays up through the cut, so the forearm may roll
    # past the default 90 degrees, and the elbow follows its hints closely.
    'frozen-knight': {'weapon': {'Right': KNIGHT_SWORD}, 'bladeLength': 2.6, 'clearWeight': 400, 'strikeWindow': (.40, .70),
                      'tauLimit': 150, 'poleWeight': 3, 'keys': [
        {'t': 0},
        {'t': .18, 'pelvis': (0, -.03, -.03), 'chest': (0, 22, 0),
         'Right': {'w': (.45, -.05, -.35), 'pole': (.5, -.7, -.5), 'blade': (.4, -.3, .85)},
         'Left': {'w': (-.05, .45, -.50), 'pole': (-.4, -.6, -.6)}},
        {'t': .40, 'still': True, 'pelvis': (0, -.08, -.10), 'chest': (-4, 55, -4), 'head': (4, -42, 0),
         'Right': {'w': (.62, -.35, -.05), 'pole': (.3, -.9, 0), 'blade': (.3, -.95, 0)},
         'Left': {'w': (-.10, .70, .05), 'pole': (-.5, -.4, -.8)}, 'RightFoot': (0, -.05, 0)},
        {'t': .49, 'pelvis': (0, .10, -.12), 'chest': (6, 15, -2), 'head': (0, -12, 0),
         'Right': {'w': (.60, .50, -.05), 'pole': (.8, -.6, 0), 'blade': (.55, .83, 0)},
         'Left': {'w': (.15, .40, -.40), 'pole': (-.3, -.6, -.7)}, 'LeftFoot': (0, .30, .12)},
        {'t': .54, 'pelvis': (0, .18, -.14), 'chest': (10, -16, 2), 'head': (-4, 14, 0),
         'Right': {'w': (.10, .85, -.05), 'pole': (1, 0, 0), 'blade': (.15, .99, 0)},
         'Left': {'w': (.30, .05, -.55), 'pole': (0, -.8, -.5)}, 'LeftFoot': (0, .40, 0)},
        {'t': .64, 'still': True, 'pelvis': (0, .18, -.15), 'chest': (10, -44, 4), 'head': (-4, 36, 0),
         'Right': {'w': (-.55, .70, -.08), 'pole': (.6, .8, 0), 'blade': (-.80, .60, 0)},
         'Left': {'w': (.35, -.30, -.60), 'pole': (0, -.8, -.4)}, 'LeftFoot': (0, .40, 0)},
        # Recovery brings the sword round the front, point forward and rising,
        # so it never passes back through the knight's own chest or head.
        {'t': .74, 'pelvis': (0, .12, -.09), 'chest': (6, -22, 2), 'head': (-2, 16, 0),
         'Right': {'w': (.05, .80, -.18), 'pole': (.4, -.2, -1), 'blade': (.10, .92, .38)},
         'Left': {'w': (.25, -.10, -.55), 'pole': (0, -.8, -.5)}, 'LeftFoot': (0, .28, .04)},
        {'t': .86, 'pelvis': (0, .05, -.04), 'chest': (3, -8, 0), 'head': (0, 6, 0),
         'Right': {'w': (.25, .30, -.50), 'pole': (.4, -.6, -.6), 'blade': (.05, .55, .83)},
         'LeftFoot': (0, .10, .06)},
        {'t': 1},
    ]},
    # Reverse-grip dagger: the goblin rears up with its fist raised over its
    # head, blade pointing down, then drives it down and forward into the
    # target with its whole weight, hopping in on the off foot. The raise
    # leads with the elbow forward so the skinned shoulder does not roll.
    'fire-goblin': {'weapon': {'Right': DAGGER}, 'rollWeight': 3, 'keys': [
        {'t': 0},
        {'t': .16, 'pelvis': (0, -.02, .02), 'chest': (-4, 8, 0),
         'Right': {'w': (.30, .35, .30), 'pole': (.5, -.3, -.8), 'blade': (.35, .3, -.9)}},
        {'t': .36, 'still': True, 'pelvis': (0, -.05, .06), 'chest': (-12, 14, -4), 'head': (-10, -8, 0),
         'Right': {'w': (.18, .20, .92), 'pole': (.4, .9, 0), 'blade': (.05, .40, -.92)},
         'Left': {'w': (.45, .45, -.10), 'pole': (.4, -.5, -.7)}, 'LeftFoot': (0, .05, .10)},
        {'t': .46, 'pelvis': (0, .14, -.04), 'chest': (4, 4, 0), 'head': (0, -2, 0),
         'Right': {'w': (.12, .70, .45), 'pole': (.4, .4, -.8), 'blade': (0, .55, -.84)},
         'Left': {'w': (.40, .20, -.25), 'pole': (.3, -.7, -.6)}, 'LeftFoot': (0, .30, .14)},
        {'t': .50, 'pelvis': (0, .24, -.10), 'chest': (12, -4, 0), 'head': (-8, 4, 0),
         'Right': {'w': (.05, .96, .16), 'pole': (.4, -.2, -.9), 'blade': (0, .70, -.72)},
         'Left': {'w': (.45, -.15, -.35), 'pole': (.3, -.8, -.5)}, 'LeftFoot': (0, .40, 0)},
        {'t': .60, 'still': True, 'pelvis': (0, .24, -.13), 'chest': (18, -6, 0), 'head': (-12, 6, 0),
         'Right': {'w': (.04, .90, -.05), 'pole': (.4, -.3, -.9), 'blade': (0, .55, -.84)},
         'Left': {'w': (.50, -.20, -.35), 'pole': (.3, -.8, -.5)}, 'LeftFoot': (0, .40, 0)},
        {'t': .82, 'pelvis': (0, .08, -.04), 'chest': (6, 0, 0),
         'Right': {'w': (.30, .35, -.30), 'pole': (.4, -.6, -.6), 'blade': (.8, -.2, -.5)},
         'LeftFoot': (0, .12, .08)},
        {'t': 1},
    ]},
    # Wide hook: the mummy lurches, loads the fist out to the side with the
    # elbow up at shoulder height, then swings it round at head height with
    # the elbow still out, the torso whipping through.
    'mummy': {'weapon': {}, 'keys': [
        {'t': 0},
        {'t': .20, 'pelvis': (0, -.02, -.02), 'chest': (0, 18, 2),
         'Right': {'w': (.55, .05, -.25), 'pole': (.3, -.8, -.4)}},
        {'t': .40, 'still': True, 'pelvis': (-.02, -.06, -.07), 'chest': (-2, 42, 6), 'head': (4, -30, 0),
         'Right': {'w': (.60, .25, .05), 'pole': (.6, -.8, .1)},
         'Left': {'w': (.15, .40, .20), 'pole': (.2, -.5, -.8)}},
        {'t': .49, 'pelvis': (.02, .08, -.09), 'chest': (6, 10, 0), 'head': (0, -8, 0),
         'Right': {'w': (.50, .60, .08), 'pole': (.7, -.6, .1)},
         'Left': {'w': (.15, .35, .25), 'pole': (.2, -.5, -.8)}, 'LeftFoot': (0, .28, .10)},
        {'t': .54, 'pelvis': (.03, .14, -.10), 'chest': (10, -22, -4), 'head': (-4, 16, 0),
         'Right': {'w': (.05, .72, .10), 'pole': (.9, -.2, .1)},
         'Left': {'w': (.15, .30, .20), 'pole': (.2, -.5, -.8)}, 'LeftFoot': (0, .36, 0)},
        {'t': .64, 'still': True, 'pelvis': (.03, .15, -.11), 'chest': (12, -36, -6), 'head': (-6, 28, 0),
         'Right': {'w': (-.30, .60, .02), 'pole': (.9, .2, .1)},
         'Left': {'w': (.20, .20, .10), 'pole': (.2, -.5, -.8)}, 'LeftFoot': (0, .36, 0)},
        {'t': .84, 'pelvis': (0, .05, -.04), 'chest': (4, -8, 0),
         'Right': {'w': (.30, .25, -.55), 'pole': (.3, -.8, -.4)}, 'LeftFoot': (0, .12, .08)},
        {'t': 1},
    ]},
    # Straight cross from the rear hand: fist chambered by the jaw, then
    # driven straight out as the hip and shoulder rotate through and the
    # front foot steps; the lead hand pulls back to guard the chin.
    'obsidian-ogre': {'weapon': {}, 'rollWeight': 3, 'keys': [
        {'t': 0},
        {'t': .20, 'pelvis': (0, -.02, -.03), 'chest': (-2, 16, 0),
         'Right': {'w': (0, .25, .15), 'pole': (.3, -.4, -1)}, 'Left': {'w': (0, .45, .25), 'pole': (.2, -.3, -1)}},
        {'t': .40, 'still': True, 'pelvis': (0, -.08, -.08), 'chest': (-5, 32, 0), 'pyaw': 10, 'head': (4, -26, 0),
         'Right': {'w': (-.02, .25, .30), 'pole': (.3, -.5, -1)},
         'Left': {'w': (.02, .75, .30), 'pole': (.2, -.2, -1)}},
        {'t': .48, 'pelvis': (0, .10, -.10), 'chest': (4, 4, 0), 'head': (0, -4, 0),
         'Right': {'w': (-.02, .65, .28), 'pole': (.4, -.3, -1), 'twist': 30},
         'Left': {'w': (.02, .45, .30), 'pole': (.2, -.3, -1)}, 'LeftFoot': (0, .30, .12)},
        {'t': .52, 'pelvis': (0, .18, -.12), 'chest': (10, -26, 0), 'pyaw': -10, 'head': (-4, 22, 0),
         'Right': {'w': (-.10, 1.0, .25), 'pole': (.8, -.2, -.6), 'twist': 70},
         'Left': {'w': (.05, .20, .30), 'pole': (.2, -.4, -1)}, 'LeftFoot': (0, .40, 0)},
        {'t': .62, 'still': True, 'pelvis': (0, .19, -.13), 'chest': (12, -30, 0), 'pyaw': -12, 'head': (-6, 25, 0),
         'Right': {'w': (-.12, .98, .22), 'pole': (.8, -.2, -.6), 'twist': 75},
         'Left': {'w': (.05, .15, .28), 'pole': (.2, -.4, -1)}, 'LeftFoot': (0, .40, 0)},
        {'t': .82, 'pelvis': (0, .06, -.05), 'chest': (4, -8, 0),
         'Right': {'w': (.25, .40, -.30), 'pole': (.4, -.5, -.8)}, 'LeftFoot': (0, .12, .08)},
        {'t': 1},
    ]},
    # Pouncing double claw rake: the werewolf rears with both arms spread
    # wide and high, claws cocked, then drives in and rakes both down across.
    'werewolf': {'weapon': {}, 'keys': [
        {'t': 0},
        {'t': .18, 'pelvis': (0, -.03, .02), 'chest': (-8, 0, 0), 'head': (-8, 0, 0),
         'Right': {'w': (.55, .15, .35), 'pole': (.6, -.6, -.5)}, 'Left': {'w': (.55, .15, .35), 'pole': (.6, -.6, -.5)}},
        {'t': .36, 'still': True, 'pelvis': (0, -.07, .07), 'chest': (-18, 8, 0), 'head': (-18, -6, 0),
         'Right': {'w': (.50, .10, .80), 'pole': (.9, -.3, -.2), 'flex': (-35, 0, 0)},
         'Left': {'w': (.50, .20, .72), 'pole': (.9, -.3, -.2), 'flex': (-35, 0, 0)}, 'RightFoot': (0, -.05, .06)},
        {'t': .46, 'pelvis': (0, .18, -.02), 'chest': (10, 2, 0),
         'Right': {'w': (.35, .80, .50), 'pole': (.8, -.2, -.4), 'flex': (-25, 0, 0)},
         'Left': {'w': (.40, .75, .45), 'pole': (.8, -.2, -.4), 'flex': (-25, 0, 0)}, 'LeftFoot': (0, .35, .16)},
        {'t': .50, 'pelvis': (0, .30, -.12), 'chest': (28, -4, 0), 'head': (-22, 2, 0),
         'Right': {'w': (.05, .88, .18), 'pole': (.8, -.3, -.4), 'flex': (20, 0, 0)},
         'Left': {'w': (.12, .84, .26), 'pole': (.8, -.3, -.4), 'flex': (20, 0, 0)}, 'LeftFoot': (0, .45, 0)},
        {'t': .60, 'still': True, 'pelvis': (0, .30, -.16), 'chest': (34, -6, 0), 'head': (-26, 4, 0),
         'Right': {'w': (-.30, .55, -.45), 'pole': (.8, .1, -.5), 'flex': (30, 0, 0)},
         'Left': {'w': (-.20, .60, -.35), 'pole': (.8, .1, -.5), 'flex': (30, 0, 0)}, 'LeftFoot': (0, .45, 0)},
        {'t': .82, 'pelvis': (0, .10, -.05), 'chest': (10, 0, 0), 'LeftFoot': (0, .15, .08)},
        {'t': 1},
    ]},
    # Icicle throw: the elf lifts the conjured icicle behind its head with the
    # elbow up, sights along the extended off hand, then whips it overhand.
    'ice-elf': {'weapon': {}, 'keys': [
        {'t': 0},
        {'t': .18, 'chest': (-2, 14, 0), 'Right': {'w': (.35, .05, .35), 'pole': (.6, -.5, -.6), 'flex': (-20, 0, 0)}},
        {'t': .40, 'still': True, 'pelvis': (0, -.06, -.02), 'chest': (-8, 34, -6), 'head': (6, -30, 0),
         'Right': {'w': (.25, -.25, .75), 'pole': (1, .2, 0), 'flex': (-50, 0, 0)},
         'Left': {'w': (-.15, .95, .15), 'pole': (-.3, -.3, -1)}, 'RightFoot': (0, -.05, 0)},
        {'t': .48, 'pelvis': (0, .08, -.06), 'chest': (4, 6, -2), 'head': (0, -6, 0),
         'Right': {'w': (.30, .50, .70), 'pole': (1, -.1, -.1), 'flex': (-20, 0, 0)},
         'Left': {'w': (-.05, .60, 0), 'pole': (-.2, -.5, -.8)}, 'LeftFoot': (0, .25, .10)},
        {'t': .52, 'pelvis': (0, .14, -.09), 'chest': (12, -18, 2), 'head': (-6, 16, 0),
         'Right': {'w': (.10, .95, .25), 'pole': (.8, -.2, -.5), 'flex': (10, 0, 0)},
         'Left': {'w': (.20, .15, -.30), 'pole': (.3, -.8, -.5)}, 'LeftFoot': (0, .32, 0)},
        {'t': .64, 'still': True, 'pelvis': (0, .14, -.10), 'chest': (18, -30, 4), 'head': (-10, 24, 0),
         'Right': {'w': (-.45, .55, -.45), 'pole': (.8, .2, -.5), 'flex': (25, 0, 0)},
         'Left': {'w': (.30, -.15, -.40), 'pole': (.3, -.8, -.5)}, 'LeftFoot': (0, .32, 0)},
        {'t': .84, 'pelvis': (0, .05, -.03), 'chest': (4, -6, 0), 'LeftFoot': (0, .10, .08)},
        {'t': 1},
    ]},
    # Fireball cast: the staff stays upright in the right hand while the open
    # left palm draws back to the hip to gather the fireball, then thrusts
    # it forward at chest height.
    'ash-shaman': {'weapon': {'Right': STAFF, 'Left': PALM}, 'rollWeight': 2, 'keys': [
        {'t': 0},
        {'t': .18, 'chest': (0, -10, 0),
         'Left': {'w': (.35, .10, -.60), 'pole': (.4, -.7, -.6), 'blade': (0, 1, 0), 'edge': (0, 0, 1)}},
        {'t': .40, 'still': True, 'pelvis': (0, -.06, -.05), 'chest': (-6, -30, 4), 'head': (6, 24, 0),
         'Left': {'w': (.30, -.20, -.55), 'pole': (.3, -.8, -.4), 'blade': (0, 1, .1), 'edge': (0, -.1, 1)},
         'Right': {'w': (.38, .40, -.62), 'pole': (.5, -.6, -.6), 'blade': (.05, .1, -1)}},
        {'t': .48, 'pelvis': (0, .08, -.07), 'chest': (4, -4, 0), 'head': (0, 4, 0),
         'Left': {'w': (.15, .55, -.25), 'pole': (.3, -.5, -.8), 'blade': (0, .7, .7), 'edge': (0, .7, -.7)},
         'Right': {'w': (.38, .35, -.65), 'pole': (.5, -.6, -.6), 'blade': (.05, .1, -1)}, 'LeftFoot': (0, .25, .10)},
        {'t': .52, 'pelvis': (0, .15, -.09), 'chest': (10, 18, -2), 'head': (-6, -16, 0),
         'Left': {'w': (.02, .95, .10), 'pole': (.4, -.3, -.9), 'blade': (-.1, .2, 1), 'edge': (0, 1, -.2)},
         'Right': {'w': (.40, .25, -.68), 'pole': (.5, -.6, -.6), 'blade': (.05, .05, -1)}, 'LeftFoot': (0, .32, 0)},
        {'t': .64, 'still': True, 'pelvis': (0, .15, -.10), 'chest': (12, 22, -2), 'head': (-8, -18, 0),
         'Left': {'w': (.02, .93, .08), 'pole': (.4, -.3, -.9), 'blade': (-.1, .25, 1), 'edge': (0, 1, -.25)},
         'Right': {'w': (.40, .22, -.68), 'pole': (.5, -.6, -.6), 'blade': (.05, .05, -1)}, 'LeftFoot': (0, .32, 0)},
        {'t': .84, 'pelvis': (0, .05, -.03), 'chest': (3, 6, 0), 'LeftFoot': (0, .10, .08)},
        {'t': 1},
    ]},
    # Spit: rear back gulping with the arms swinging behind, then lurch the
    # head and chest forward to spit, arms flung forward.
    'spitter-zombie': {'weapon': {}, 'rollWeight': 3, 'keys': [
        {'t': 0},
        {'t': .22, 'chest': (-8, 0, 0), 'head': (-6, 0, 0)},
        {'t': .42, 'still': True, 'pelvis': (0, -.08, -.03), 'chest': (-20, 0, 0), 'head': (-22, 0, 0),
         'Right': {'w': (.25, -.45, -.65), 'pole': (.3, -.8, -.5)}, 'Left': {'w': (.25, -.45, -.65), 'pole': (.3, -.8, -.5)}},
        {'t': .52, 'pelvis': (0, .12, -.08), 'chest': (18, 0, 0), 'head': (-12, 0, 0),
         'Right': {'w': (.25, .45, -.60), 'pole': (.3, -.8, -.5)}, 'Left': {'w': (.25, .45, -.60), 'pole': (.3, -.8, -.5)},
         'LeftFoot': (0, .20, 0)},
        {'t': .64, 'still': True, 'pelvis': (0, .13, -.10), 'chest': (22, 0, 0), 'head': (-6, 0, 0),
         'Right': {'w': (.28, .55, -.55), 'pole': (.3, -.8, -.5)}, 'Left': {'w': (.28, .55, -.55), 'pole': (.3, -.8, -.5)},
         'LeftFoot': (0, .20, 0)},
        {'t': .86, 'pelvis': (0, .04, -.03), 'chest': (6, 0, 0), 'LeftFoot': (0, .06, .06)},
        {'t': 1},
    ]},
}
# Authored impact/release as a fraction of each attack clip.
IMPACT = {'skeleton': .50, 'frozen-knight': .54, 'fire-goblin': .50, 'mummy': .54, 'obsidian-ogre': .52,
          'werewolf': .50, 'ice-elf': .52, 'ash-shaman': .52, 'spitter-zombie': .52}
