"""Hammer Brute design: every volume, joint and accessory anchor (pure numpy).

Units: 1 = 1 Roblox stud. Blender world: Z up, the character faces -Y, +X is the
character's LEFT (viewer's right in the reference).

How the numbers were chosen: each landmark was read in pixels off the reference
(source/REFERENCE_NOTES.md), converted to studs through the solved camera
(hb_camera.RefCam.at(u, v, depth)) at a depth chosen from the stance, and then
adjusted against the silhouette (hb_preview.py, then the Blender compare passes
logged in the README). Depths (Y) are the only dimension a single view cannot
supply.

Two poses exist:
  REST  the modelling / bind pose: torso, head and legs as in the reference
        stance but the head upright, both arms in a 40-degree A-pose with the
        elbows bent 25 degrees and the fingers relaxed. Every primitive is
        authored in its bone's REST frame.
  REF   the reference stance (idle frame 0): the head tilted, the hammer held
        low across the hips with both hands, the fists closed on the haft.
        REF = REST + bone rotations (hb_pose); the arms come from the grip
        solve in hb_grip.solve_reference().
"""
import functools
import math

import numpy as np

from hb_sdf import (Ellipsoid, RoundBox, TaperBox, RoundCone, rot_xyz, axis_angle, frame_from)


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# =============================================================== proportions
CROWN = 13.7                    # top of the head in REF (studs)
SHOULDER = np.array([3.05, 0.25, 10.60])       # left shoulder joint (right = mirrored x)
L_UPPER = 3.60                  # shoulder -> elbow
L_FORE = 3.50                   # elbow -> wrist (LowerArm 0..TWIST_AT, LowerArmTwist TWIST_AT..1)
TWIST_AT = 0.5
REST_ABDUCT = 40.0              # REST arm abduction from vertical (deg)
REST_FLEX = 8.0                 # REST shoulder forward flexion (deg)
REST_ELBOW = 25.0               # REST elbow flexion (deg)

# ----------------------------------------------------------------- spine
J = {}
J['Root'] = np.array([0.0, 0.0, 0.0])
J['HumanoidRootPart'] = np.array([0.0, 0.10, 4.70])
J['LowerTorso'] = np.array([0.0, 0.10, 4.70])
J['UpperTorso'] = np.array([0.0, 0.30, 7.10])
J['UpperTorso_tail'] = np.array([0.0, 0.25, 10.55])
J['Head'] = np.array([0.0, 0.25, 10.95])          # skull / neck joint
J['Head_tail'] = np.array([0.0, 0.25, 13.10])
J['Belly'] = np.array([0.0, -1.25, 6.55])
J['Belly_tail'] = np.array([0.0, -3.05, 6.35])

# ------------------------------------------------------------------ head
HEAD_C = np.array([0.0, -0.32, 12.22])              # centre of the skull block (REST, upright)
HEAD_REF = {'pitch': 8.0, 'yaw': -7.0, 'roll': -3.0}    # REF head tilt about J['Head'], after the hunch (deg)
REF_HUNCH = 5.0                 # REF: the upper torso leans forward about J['UpperTorso'] (deg)
REF_ROLL = 7.0                  # REF: the shoulder line tilts, his left shoulder up (deg, about Y)
REF_ROLL_PIVOT_Z = 10.9          # ... pivoting near the shoulders so the waist barely shears


def Hd(x, y, z):
    """Head-local design (front = -y, up = z) -> REST world."""
    return HEAD_C + np.array([x, y, z], float)


J['Jaw'] = Hd(0.0, 0.30, -0.55)
J['Jaw_tail'] = Hd(0.0, -1.05, -1.05)
J['Brow'] = Hd(0.0, -0.95, 0.42)
J['EyelidUpper'] = Hd(0.0, -0.95, 0.05)

# ------------------------------------------------------------------ legs
# Wide stance: the right leg stands under the hip, the left is spread out and
# forward (toes turned out 8 deg), as in the reference.
J['RightUpperLeg'] = np.array([-1.55, 0.20, 4.45])
J['RightLowerLeg'] = np.array([-1.62, -0.05, 2.45])
J['RightFoot'] = np.array([-1.72, 0.70, 1.02])
J['LeftUpperLeg'] = np.array([1.55, 0.20, 4.45])
J['LeftLowerLeg'] = np.array([3.05, -1.15, 2.45])
J['LeftFoot'] = np.array([3.62, -1.05, 1.02])
FOOT_YAW = {'Right': -4.0, 'Left': 8.0}           # toe-out (deg)


def foot_dir(side):
    a = math.radians(FOOT_YAW[side]) * (1 if side == 'Left' else -1)
    return np.array([math.sin(a), -math.cos(a), 0.0])


FOOT = {'half_w': 1.42, 'back': 1.45, 'front': 1.60, 'height': 1.28, 'ball': 0.62}   # block foot (ankle-relative)


# ================================================================== arms
def shoulder(side):
    s = SHOULDER.copy()
    if side == 'Right':
        s[0] = -s[0]
    return s


def ref_upper_torso():
    """4x4 world transform of the upper torso REST -> REF: the forward hunch about
    the UpperTorso joint, then the shoulder-line roll about a pivot at the shoulders."""
    def about(R, p):
        M = np.eye(4)
        M[:3, :3] = R
        M[:3, 3] = p - R @ p
        return M
    A = about(axis_angle([1.0, 0, 0], REF_HUNCH), J['UpperTorso'])
    piv = A[:3, :3] @ np.array([0.0, 0.2, REF_ROLL_PIVOT_Z]) + A[:3, 3]
    Bm = about(axis_angle([0, 1.0, 0], -REF_ROLL), piv)
    return Bm @ A


def ref_shoulder(side):
    """Shoulder joint in REF (after the hunch and the shoulder roll)."""
    M = ref_upper_torso()
    return M[:3, :3] @ shoulder(side) + M[:3, 3]


def rest_arm(side):
    """REST joints: (shoulder, elbow, twist joint, wrist) and the elbow hinge axis."""
    sx = -1.0 if side == 'Right' else 1.0
    a, f = math.radians(REST_ABDUCT), math.radians(REST_FLEX)
    u = _unit([sx * math.sin(a) * math.cos(f), -math.sin(f), -math.cos(a) * math.cos(f)])
    S = shoulder(side)
    E = S + u * L_UPPER
    fwd = np.array([0, -1.0, 0])
    w = _unit(fwd - u * (fwd @ u))
    e = math.radians(REST_ELBOW)
    fa = math.cos(e) * u + math.sin(e) * w
    Wr = E + fa * L_FORE
    hinge = _unit(np.cross(u, fa))
    return S, E, E + fa * L_FORE * TWIST_AT, Wr, hinge


def arm_frames_rest(side):
    """3x3 frames (columns X, Y, Z) of UpperArm and LowerArm in REST:
    Y along the bone, X = elbow hinge (+X rotation = flexion)."""
    S, E, T, Wr, hinge = rest_arm(side)
    yu = _unit(E - S)
    yf = _unit(Wr - E)
    Ru = np.stack([hinge, yu, np.cross(hinge, yu)], 1)
    Rf = np.stack([hinge, yf, np.cross(hinge, yf)], 1)
    return Ru, Rf


# ================================================================= hands
# Hand-local (right hand): +Y wrist -> knuckles, +Z back of the hand, the thumb
# on -X; origin at the wrist joint (the Hand bone head). The left hand mirrors
# x -> -x so both keep right-handed bone frames.
MIRROR = {'Right': 1.0, 'Left': -1.0}
FINGER_NAMES = ['Index', 'Middle', 'Ring', 'Pinky']
FINGER_X = (-0.74, -0.25, 0.24, 0.71)
FINGER_BASE = (1.38, -0.14)         # (y, z) of the finger roots
FINGER_BASE_OFF = ((0.0, 0.0), (0.02, 0.0), (-0.08, -0.03), (-0.22, -0.08))   # metacarpal arch (dy, dz)
FINGER_SPLAY = (-3.0, -1.0, 1.5, 4.0)
FINGER_SCALE = (1.0, 1.05, 0.98, 0.84)
SEG_LEN = (0.66, 0.52, 0.44)
SEG_RAD = (0.255, 0.245, 0.225)
FINGER_RAD_SCALE = (1.0, 1.02, 0.98, 0.88)
REST_CURL = (14.0, 18.0, 10.0)      # relaxed REST fingers
THUMB_BASE = (-0.68, 0.36, -0.34)
THUMB_DIR = (-0.45, 0.78, -0.42)
THUMB_LEN = (0.55, 0.44, 0.38)
THUMB_RAD = ((0.31, 0.29), (0.29, 0.26), (0.26, 0.21))
THUMB_REST = (6.0, 10.0, 6.0)
PALM_C = (0.0, 0.70, -0.02)
PALM_HALF = (1.00, 0.78, 0.42)

# ================================================================ hammer
HAFT_R = 0.36                   # wooden haft radius (the fingers close round it)
HEAD_HALF = np.array([1.55, 2.18, 1.27])      # head half extents: along the haft, striking axis, side axis
HEAD_BEVEL = 0.46
EYE_OFFSET = 0.00               # the haft passes this far above the head centre (toward the top face)
S_RIGHT = 2.75                  # right carry grip: distance from the head centre along the haft
S_LEFT = 9.45                   # left carry grip
S_BUTT = 11.0                   # butt end (iron cap)
S_RIGHT_ATTACK_MAX = 7.35       # the right hand can slide down to here (fists 0.05 apart)
BANDS = (6.0, 6.88, 7.72)       # near-flush iron bands (reference positions)
BAND_HALF = 0.24
BAND_RAISE = 0.03               # raised only 0.03 so a sliding fist stays within the contact window
COLLAR = (1.57, 1.70)           # raised iron collar where the haft enters the head
BUTT_CAP = (10.62, 11.0)
CAP_RAISE = 0.09


def mirror_local(side, v):
    v = np.array(v, float)
    v[0] *= MIRROR[side]
    return v


# ================================================================= torso
def torso_prims():
    """The trunk. Big rounded masses with modest fillets (k) so the segmented
    low-poly muscle read survives, larger fillets where the belly meets the hips."""
    P = []
    ut, lt, bl, hb = 'UpperTorso', 'LowerTorso', 'Belly', 'Head'
    # pelvis / hips / seat
    P.append(Ellipsoid((0.0, 0.25, 4.95), (2.55, 1.85, 1.35), k=0.6, bone=lt, tag='pelvis'))
    P.append(Ellipsoid((0.0, 0.95, 4.70), (2.25, 1.35, 1.25), k=0.6, bone=lt, tag='seat'))
    for s in (-1, 1):
        P.append(Ellipsoid((s * 2.05, 0.35, 5.55), (1.05, 1.45, 1.05), k=0.6, bone=lt, tag='flank'))
    # the belly: the dominant form, round and projecting
    P.append(Ellipsoid((0.0, -1.30, 6.55), (3.15, 2.45, 2.05), k=0.65, bone=bl, tag='belly'))
    P.append(Ellipsoid((0.0, -1.85, 5.75), (2.55, 1.85, 1.20), k=0.6, bone=bl, tag='belly_low'))
    # ribcage / chest and back
    P.append(Ellipsoid((0.0, 0.10, 9.15), (2.85, 2.05, 1.95), k=0.65, bone=ut, tag='chest'))
    P.append(Ellipsoid((0.0, 0.95, 7.70), (2.55, 1.40, 1.90), k=0.65, bone=ut, tag='back_low'))
    # pecs: heavy slabs with a soft lower edge (mostly hidden by the shirt)
    for s in (-1, 1):
        P.append(Ellipsoid((s * 1.20, -1.30, 9.55), (1.35, 0.80, 0.90), R=rot_xyz(10, s * -10, s * 8), k=0.3,
                           bone=ut, tag='pec'))
    # traps: a big hump that rises beside the head almost to the jaw corners
    P.append(Ellipsoid((0.0, 0.70, 10.55), (2.35, 1.40, 1.05), k=0.55, bone=ut, tag='traps'))
    for s in (-1, 1):
        P.append(Ellipsoid((s * 1.55, 0.45, 11.20), (1.15, 1.05, 0.82), k=0.5, bone=ut, tag='trap_side'))
        # shoulder socket mass the deltoid grows out of
        P.append(Ellipsoid((s * 2.70, 0.25, 10.15), (1.15, 1.25, 1.10), k=0.5, bone=ut, tag='shoulder'))
        P.append(Ellipsoid((s * 2.00, 0.75, 8.35), (0.95, 1.20, 1.45), k=0.6, bone=ut, tag='lat'))
    # neck: short and thick, buried in the traps
    P.append(RoundCone((0.0, 0.20, 10.30), Hd(0.0, 0.25, -0.70), 1.05, 0.92, k=0.45, bone=hb, tag='neck'))
    # navel pit
    P.append(Ellipsoid((0.0, -3.72, 6.20), (0.15, 0.32, 0.17), k=0.08, bone=bl, op='sub', tag='navel'))
    return P


# ================================================================== head
def head_prims():
    """Head-local layout (REST, upright). A blocky skull with a flat top, a heavy
    angular brow, cheekbones, an open snarl with gum ridges and a heavy jaw.
    Eyes, scar and wound are PAINTED (hb_paint); the relief here is shallow on
    purpose: modelled sockets read as sunglasses."""
    P = []
    hb, jb, br = 'Head', 'Jaw', 'Brow'
    # skull: a rounded block, slightly narrower at the crown
    P.append(TaperBox(Hd(0.0, 0.0, 0.42), (1.02, 1.08, 0.80), round_=0.34, scale_bottom=1.04, k=0.2, bone=hb,
                      tag='skull'))
    P.append(RoundBox(Hd(0.0, 0.25, 0.10), (0.98, 0.92, 0.70), round_=0.40, k=0.25, bone=hb, tag='occiput'))
    # mid-face block
    P.append(RoundBox(Hd(0.0, -0.45, -0.30), (1.00, 0.62, 0.55), round_=0.30, k=0.22, bone=hb, tag='face'))
    # high, angular cheekbones (planes, not balls)
    for s in (-1, 1):
        P.append(RoundBox(Hd(s * 0.62, -0.98, -0.24), (0.30, 0.24, 0.17), R=rot_xyz(10, s * -18, s * 14),
                          round_=0.12, k=0.12, bone=hb, tag='cheek'))
    # heavy brow SHELF in an angry V: two slabs that overhang the eyes, inner ends
    # lower, meeting at a notch over the nose; the eyes sit in their shadow
    for s in (-1, 1):
        P.append(RoundBox(Hd(s * 0.47, -1.24, 0.30), (0.52, 0.30, 0.16), R=rot_xyz(-14, -s * 10, s * 24),
                          round_=0.07, k=0.10, bone=br, tag='brow'))
    P.append(RoundBox(Hd(0.0, -1.06, 0.72), (0.72, 0.22, 0.26), R=rot_xyz(-20, 0, 0), round_=0.10, k=0.22,
                      bone=br, tag='forehead'))
    # nose bridge (the skull-like nasal cavity is painted)
    P.append(RoundCone(Hd(0.0, -1.14, 0.12), Hd(0.0, -1.22, -0.30), 0.12, 0.16, k=0.10, bone=hb, tag='nose'))
    # snarling upper lip, raised and wide
    P.append(RoundBox(Hd(0.0, -1.00, -0.46), (0.86, 0.24, 0.13), R=rot_xyz(4, 0, 0), round_=0.10, k=0.12,
                      bone=hb, tag='muzzle'))
    # lower jaw: wide, heavy, under-bitten
    P.append(RoundBox(Hd(0.0, -0.84, -1.02), (0.98, 0.46, 0.25), R=rot_xyz(-8, 0, 0), round_=0.20, k=0.14,
                      bone=jb, tag='jaw'))
    P.append(RoundBox(Hd(0.0, -0.15, -0.92), (0.92, 0.62, 0.28), round_=0.24, k=0.25, bone=jb, tag='jaw_back'))
    P.append(Ellipsoid(Hd(0.0, -1.10, -1.10), (0.42, 0.20, 0.17), k=0.12, bone=jb, tag='chin'))
    # ---- carving (applied last)
    # the snarl: a wide blocky recess across most of the face (real geometry)
    P.append(RoundBox(Hd(0.02, -1.22, -0.73), (0.76, 0.42, 0.23), R=rot_xyz(0, -5, 0), round_=0.12, k=0.05,
                      bone=jb, op='sub', tag='mouth'))
    P.append(RoundBox(Hd(0.04, -1.22, -0.58), (0.66, 0.42, 0.10), R=rot_xyz(0, -5, 0), round_=0.08, k=0.05,
                      bone=hb, op='sub', tag='mouth'))
    # gaunt hollows under the cheekbones, beside the mouth corners
    for s in (-1, 1):
        P.append(Ellipsoid(Hd(s * 0.86, -1.02, -0.66), (0.20, 0.20, 0.30), k=0.10, bone=hb, op='sub', tag='hollow'))
    # shallow eye beds: the glow sits proud of them, the dark socket is painted
    for s in (-1, 1):
        P.append(Ellipsoid(Hd(s * 0.45, -1.18, -0.06), (0.25, 0.05, 0.19), k=0.04, bone=hb, op='sub', tag='socket'))
    P.append(RoundBox(Hd(0.0, -1.40, 0.24), (0.05, 0.30, 0.16), round_=0.03, k=0.05, bone=br, op='sub', tag='notch'))
    return P


# ================================================================= arms
def arm_prims(side):
    """Segmented muscle masses in the REST arm frames: a big deltoid cap, the
    upper-arm block, an elbow/upper-forearm block and the lower forearm. The
    segments meet in soft creases (small k) as in the reference."""
    lat = -1.0 if side == 'Right' else 1.0           # world X of 'outward'
    S, E, T, Wr, hinge = rest_arm(side)
    Ru, Rf = arm_frames_rest(side)
    ub, lb, tb = side + 'UpperArm', side + 'LowerArm', side + 'LowerArmTwist'

    def U(x, y, z):
        """Upper-arm local: x outward, y down the arm, z = forward (bone Z sign-fixed)."""
        o = np.array([1.0, 0, 0]) * lat
        xo = _unit(o - Ru[:, 1] * (o @ Ru[:, 1]))
        zf = _unit(np.cross(xo, Ru[:, 1])) * lat
        if zf[1] > 0:
            zf = -zf
        return S + xo * x + Ru[:, 1] * y + zf * z, np.stack([xo, Ru[:, 1], zf], 1)

    def F(x, y, z):
        o = np.array([1.0, 0, 0]) * lat
        xo = _unit(o - Rf[:, 1] * (o @ Rf[:, 1]))
        zf = _unit(np.cross(xo, Rf[:, 1])) * lat
        if zf[1] > 0:
            zf = -zf
        return E + xo * x + Rf[:, 1] * y + zf * z, np.stack([xo, Rf[:, 1], zf], 1)

    P = []
    c, R = U(0.32, 0.62, 0.02)
    # segmented BLOCKS with plane changes: rounded boxes, small fillets between them
    P.append(RoundBox(c, (1.26, 1.24, 1.26), R=R, round_=0.62, k=0.30, bone=ub, tag='deltoid'))
    c, R = U(0.18, 2.12, 0.08)
    P.append(RoundBox(c, (1.24, 0.98, 1.16), R=R, round_=0.50, k=0.10, bone=ub, tag='upperarm'))
    c, R = U(-0.05, 2.0, 0.52)
    P.append(Ellipsoid(c, (0.96, 0.88, 0.82), R=R, k=0.12, bone=ub, tag='biceps'))
    c, R = U(0.10, 2.05, -0.47)
    P.append(Ellipsoid(c, (1.00, 0.96, 0.82), R=R, k=0.12, bone=ub, tag='triceps'))
    P.append(RoundCone(S, E, 1.05, 0.95, k=0.3, bone=ub, tag='humerus'))
    # elbow / upper forearm block
    c, R = F(-0.02, 0.58, 0.02)
    P.append(RoundBox(c, (1.40, 1.00, 1.20), R=R, round_=0.52, k=0.10, bone=lb, tag='elbow'))
    # massive lower forearm (barely tapering), the last block owned by the twist bone
    c, R = F(0.06, 1.80, 0.04)
    P.append(RoundBox(c, (1.18, 0.92, 1.08), R=R, round_=0.50, k=0.10, bone=lb, tag='forearm'))
    c, R = F(0.0, 2.74, 0.0)
    P.append(RoundBox(c, (1.02, 0.72, 0.94), R=R, round_=0.44, k=0.12, bone=tb, tag='forearm_low'))
    P.append(RoundCone(E, Wr, 0.95, 0.80, k=0.3, bone=lb, tag='ulna'))
    return P


# ================================================================== legs
def leg_prims(side):
    s = -1 if side == 'Right' else 1
    Hp, K, A = J[side + 'UpperLeg'], J[side + 'LowerLeg'], J[side + 'Foot']
    ub, lb, fb, tb = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot', side + 'Toes'
    fwd = foot_dir(side)
    P = []
    P.append(RoundCone(Hp + np.array([0, 0, 0.30]), K, 1.50, 1.12, k=0.6, bone=ub, tag='thigh'))
    P.append(Ellipsoid(Hp + (K - Hp) * 0.42 + np.array([s * 0.22, 0.05, 0]), (1.30, 1.40, 1.25),
                       R=frame_from(K - Hp, fwd), k=0.45, bone=ub, tag='thigh_bulk'))
    P.append(Ellipsoid(K + fwd * 0.25 + np.array([0, 0, 0.05]), (0.95, 0.95, 0.85), R=frame_from(A - K, fwd),
                       k=0.3, bone=lb, tag='knee'))
    # calf block: the reference shows a big green block between hem and foot
    P.append(RoundCone(K, A + np.array([0, 0, 0.25]), 1.10, 0.92, k=0.30, bone=lb, tag='shin'))
    P.append(Ellipsoid(K + (A - K) * 0.45 - fwd * 0.15, (1.15, 1.12, 0.95), R=frame_from(A - K, fwd), k=0.3,
                       bone=lb, tag='calf'))
    P.append(Ellipsoid(A + np.array([0, 0, 0.18]), (0.90, 0.90, 0.60), R=frame_from((0, 0, 1), fwd), k=0.18,
                       bone=fb, tag='ankle'))
    # block foot: a chamfered slab, the front third owned by the Toes bone
    lat = np.cross(fwd, (0, 0, 1.0))
    Rf = np.stack([lat, fwd, np.array([0, 0, 1.0])], 1)
    Fh = FOOT
    back, front = -Fh['back'], Fh['front']
    mid = A + fwd * ((back + front) / 2)
    mid[2] = Fh['height'] / 2 + 0.035          # the smooth union bulges ~0.035 below the boxes
    P.append(RoundBox(mid - fwd * 0.30, (Fh['half_w'], (front - back) / 2 - 0.30, Fh['height'] / 2), R=Rf,
                      round_=0.12, k=0.16, bone=fb, tag='foot'))
    toe_c = A + fwd * (front - Fh['ball'] / 2 - 0.15)
    toe_c[2] = Fh['height'] * 0.42 + 0.035
    P.append(RoundBox(toe_c, (Fh['half_w'] * 0.98, Fh['ball'] / 2 + 0.15, Fh['height'] * 0.42), R=Rf,
                      round_=0.12, k=0.14, bone=tb, tag='toes'))
    return P


# =============================================================== hands
def finger_root(i):
    return np.array([FINGER_X[i], FINGER_BASE[0] + FINGER_BASE_OFF[i][0], FINGER_BASE[1] + FINGER_BASE_OFF[i][1]])


def finger_rest_points(side):
    """REST digit joints in hand-local coords: {bone: [p0, p1, p2, p3]}."""
    out = {}
    for i, nm in enumerate(FINGER_NAMES):
        p = [finger_root(i)]
        d0 = axis_angle((0, 0, 1), FINGER_SPLAY[i]) @ np.array([0, 1.0, 0])
        tot = 0.0
        for k in range(3):
            tot += REST_CURL[k]
            d = axis_angle((1, 0, 0), -tot) @ d0
            p.append(p[-1] + d * SEG_LEN[k] * FINGER_SCALE[i])
        out[nm] = [mirror_local(side, q) for q in p]
    p = [np.array(THUMB_BASE, float)]
    d0 = _unit(THUMB_DIR)
    ax = _unit((0.30, 0.20, 0.93))
    tot = 0.0
    for k in range(3):
        tot += THUMB_REST[k]
        p.append(p[-1] + (axis_angle(ax, -tot) @ d0) * THUMB_LEN[k])
    out['Thumb'] = [mirror_local(side, q) for q in p]
    return out


def hand_prims_local(side, joints, bone_prefix=None):
    """Hand primitives in HAND-LOCAL coordinates (origin = wrist), given the digit
    joints {name: [p0..p3]} (hand-local). Fingers are separate segments with
    clear creases between them; knuckles are distinct bumps."""
    hb = side + 'Hand'
    M = lambda v: mirror_local(side, v)
    P = []
    P.append(RoundBox(M(PALM_C), PALM_HALF, round_=0.30, k=0.10, bone=hb, tag='palm'))
    # thick back of the hand (dorsal side only, so the solved grip is untouched)
    P.append(RoundBox(M((0.0, 0.66, 0.22)), (1.04, 0.72, 0.30), round_=0.26, k=0.12, bone=hb, tag='backhand'))
    P.append(RoundCone(M((0.0, -0.55, 0.0)), M((0.0, 0.25, -0.02)), 0.80, 0.88, k=0.25, bone=hb, tag='wrist',
                       squash=(1.25, 0.80), x_hint=(1, 0, 0)))
    P.append(Ellipsoid(M((-0.62, 0.42, -0.36)), (0.46, 0.62, 0.36), k=0.14, bone=hb, tag='thenar'))
    P.append(Ellipsoid(M((0.62, 0.42, -0.30)), (0.40, 0.64, 0.32), k=0.14, bone=hb, tag='hypothenar'))
    for i, nm in enumerate(FINGER_NAMES):
        p0 = joints[nm][0]
        rk = 0.31 * FINGER_RAD_SCALE[i]
        P.append(Ellipsoid(p0 + np.array([0, 0, 0.10]), (rk, rk * 1.05, rk * 0.92), k=0.08, bone=hb, tag='knuckle'))
    for i, nm in enumerate(FINGER_NAMES):
        pts = joints[nm]
        for k in range(3):
            b = f'{side}{nm}{k + 1}'
            r0 = SEG_RAD[k] * FINGER_RAD_SCALE[i]
            r1 = SEG_RAD[min(k + 1, 2)] * FINGER_RAD_SCALE[i] * (0.92 if k == 2 else 1.0)
            P.append(RoundCone(pts[k], pts[k + 1], r0, r1, k=0.07, bone=b, tag=f'finger{i}{k}'))
    pts = joints['Thumb']
    for k in range(3):
        P.append(RoundCone(pts[k], pts[k + 1], THUMB_RAD[k][0], THUMB_RAD[k][1], k=0.05, bone=f'{side}Thumb{k + 1}',
                           tag=f'thumb{k}'))
    return P


def place_prims(prims, R, t):
    """Rigidly move hand-local primitives into the world (R columns = local axes)."""
    for p in prims:
        p.c = R @ p.c + t
        p.R = R @ p.R
    return prims


@functools.lru_cache(maxsize=None)
def rest_hand_frame(side):
    """(R, wrist) in REST: the hand continues the REST forearm with the same roll
    about the forearm that the REF grip needs (so the REF forearm is untwisted)."""
    import hb_grip
    ref = hb_grip.solve_reference()
    S, E, T, Wr, hinge = rest_arm(side)
    Ru, Rf = arm_frames_rest(side)
    Rf_ref = np.array(ref['forearm_frame_' + side])
    Rh_ref = np.array(ref['hand_frame_' + side])
    rel = Rf_ref.T @ Rh_ref                       # hand in forearm frame (REF)
    # remove the wrist swing: keep only the twist about the forearm Y
    y = rel[:, 1]
    sw = _min_rot(y, np.array([0, 1.0, 0]))
    twist_only = sw @ rel
    return Rf @ twist_only, Wr


def _min_rot(a, b):
    a = _unit(a)
    b = _unit(b)
    v = np.cross(a, b)
    c = float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1 / (1 + c))


def hand_prims(side, pose='REST'):
    """Hand primitives in the world. REST: relaxed fingers on the REST hand frame.
    REF: the solved grip (hb_grip) on the REF hand frame."""
    import hb_grip
    if pose == 'REST':
        R, W = rest_hand_frame(side)
        joints = finger_rest_points(side)
    else:
        ref = hb_grip.solve_reference()
        R = np.array(ref['hand_frame_' + side])
        W = np.array(ref['wrist_' + side])
        joints = hb_grip.grip_joints_local(side)
    return place_prims(hand_prims_local(side, joints), R, W)


# ============================================================== assembly
def body_prims():
    """REST skin primitives (without hands), carving last."""
    P = torso_prims() + head_prims()
    for side in ('Right', 'Left'):
        P += arm_prims(side) + leg_prims(side)
    unions = [p for p in P if p.op == 'union']
    subs = [p for p in P if p.op != 'union']
    return unions + subs


def skin_prims(with_hands=True):
    P = body_prims()
    if with_hands:
        for side in ('Right', 'Left'):
            P = P + hand_prims(side, 'REST')
    unions = [p for p in P if p.op == 'union']
    subs = [p for p in P if p.op != 'union']
    return unions + subs
