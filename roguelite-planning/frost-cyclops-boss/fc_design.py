"""Frost Cyclops design: every volume, joint and accessory anchor.

Units: 1 = 1 Roblox stud. Blender world: Z up, the character faces -Y, +X is
the character's LEFT (viewer's right in the reference).

How numbers were chosen: each landmark was read in pixels off the reference
(see source/REFERENCE_NOTES.md), converted to studs through the solved camera
(fc_camera.RefCam.at(u, v, depth)) at a depth chosen from the stance, and then
adjusted by the compare -> fix passes logged in the README. Depths (Y) are the
only authored dimension a single view cannot supply.

The torso is yawed -15 deg (its front turns toward the character's right, which
is why the navel, sternum and buckle sit 1 stud right of the pelvis centre in
the image), the pelvis -10 deg, and the head faces the camera.

Two poses are described:
  REFERENCE  the image stance (fists closed, club gripped)
  REST       the same stance with both arms abducted a further REST_ABDUCT deg
             about the shoulder and the fingers relaxed, for clean skinning.
The sculpt is evaluated in REST; the ReferencePose action restores REFERENCE.
"""
import functools
import math

import numpy as np

from fc_sdf import (Ellipsoid, RoundBox, TaperBox, RoundCone, rot_xyz, axis_angle, frame_from)

REST_ABDUCT = 9.0       # extra shoulder abduction in the rest pose (deg)
TORSO_YAW = -15.0
PELVIS_YAW = -10.0
HEAD_YAW = 1.0          # faces the camera (camera yaw is +1.15 deg)
TORSO_O = np.array([-0.30, 0.0, 0.0])


def yawm(deg):
    return rot_xyz(0, 0, deg)


RT = yawm(TORSO_YAW)
RP = yawm(PELVIS_YAW)


def T(x, y, z):
    """Torso-local -> world (local: symmetric design, front = -Y)."""
    return RT @ np.array([x, y, z], float) + TORSO_O


def Pv(x, y, z):
    return RP @ np.array([x, y, z], float)


# ------------------------------------------------------------------- head frame
HEAD_C = np.array([-0.40, -0.72, 11.86])        # centre of the skull block
RH = yawm(HEAD_YAW)


def Hd(x, y, z):
    return RH @ np.array([x, y, z], float) + HEAD_C


# --------------------------------------------------------------- joints (REF pose)
J = {}
J['Root'] = np.array([0.0, 0.0, 0.0])
J['HumanoidRootPart'] = np.array([0.0, 0.05, 4.55])
J['LowerTorso'] = np.array([0.0, 0.05, 4.55])
J['UpperTorso'] = T(0.0, 0.10, 6.75)
J['UpperTorso_tail'] = T(0.0, 0.05, 10.05)
J['Head'] = Hd(0.0, 0.25, -1.05)
J['Head_tail'] = Hd(0.0, 0.05, 1.20)
J['Jaw'] = Hd(0.0, 0.05, -0.45)          # hinge below/behind the ears
J['Jaw_tail'] = Hd(0.0, -1.05, -1.00)
J['Eye'] = Hd(0.0, -0.66, -0.01)
J['EyelidUpper'] = Hd(0.0, -0.66, -0.01)
J['Brow'] = Hd(0.0, -0.80, 0.30)
J['Belly'] = T(0.0, -0.80, 7.30)
J['Belly_tail'] = T(0.0, -2.40, 7.10)

# Arms (reference pose), read off the image through the camera.
J['RightUpperArm'] = T(-3.02, 0.20, 9.55)
J['RightLowerArm'] = np.array([-4.62, 0.30, 7.35])
J['RightHand'] = np.array([-4.70, -0.90, 5.25])
J['LeftUpperArm'] = T(3.02, 0.20, 9.55)
J['LeftLowerArm'] = np.array([4.82, -0.05, 6.35])
J['LeftHand'] = np.array([4.45, -0.55, 4.12])

# Legs
J['RightUpperLeg'] = Pv(-1.48, 0.25, 4.45)
J['RightLowerLeg'] = np.array([-2.33, 0.25, 2.85])
J['RightFoot'] = np.array([-2.30, 0.62, 1.02])
J['LeftUpperLeg'] = Pv(1.48, 0.05, 4.45)
J['LeftLowerLeg'] = np.array([2.04, -1.12, 2.68])
J['LeftFoot'] = np.array([2.26, -1.02, 1.00])

# Foot directions (unit vectors in XY): right foot turned well out, left mildly.
FOOT_DIR = {
    'Right': np.array([-math.sin(math.radians(52)), -math.cos(math.radians(52)), 0.0]),
    'Left': np.array([math.sin(math.radians(8)), -math.cos(math.radians(8)), 0.0]),
}
FOOT_LEN = 2.25        # ankle to toe front along the foot
TOE_LEN = 0.78


def rest_arm_rotation(side, degrees=None):
    """3x3 rotation taking the REFERENCE arm to the REST arm about the shoulder.

    Abducts outward in the torso's frontal plane (axis = torso forward): the
    hanging arm's lower end moves away from the body (-X for the right arm)."""
    a = REST_ABDUCT if degrees is None else degrees
    fwd = RT @ np.array([0.0, -1.0, 0.0])
    M = axis_angle(fwd, a)
    outward = -1.0 if side == 'Right' else 1.0
    if (M @ np.array([0.0, 0.0, -1.0]))[0] * outward < 0:
        M = axis_angle(fwd, -a)
    return M


def rest_joints():
    """Joint positions in the REST pose (arms abducted about the shoulder)."""
    R = dict(J)
    for side in ('Right', 'Left'):
        M = rest_arm_rotation(side)
        S = J[side + 'UpperArm']
        for b in ('LowerArm', 'Hand'):
            R[side + b] = (J[side + b] - S) @ M.T + S
    return R


# ----------------------------------------------------------------------- body
def torso_prims():
    P = []
    ut, lt, bl = 'UpperTorso', 'LowerTorso', 'Belly'
    # pelvis block and seat
    P.append(Ellipsoid(Pv(0.0, 0.25, 5.20), (2.45, 1.85, 1.45), R=RP, k=0.6, bone=lt, tag='pelvis'))
    P.append(Ellipsoid(Pv(0.0, 0.85, 4.95), (2.15, 1.45, 1.30), R=RP, k=0.6, bone=lt, tag='seat'))
    # belly: the dominant form
    P.append(Ellipsoid(T(0.10, -0.95, 7.35), (2.42, 2.30, 1.95), R=RT, k=0.7, bone=bl, tag='belly'))
    P.append(Ellipsoid(T(0.0, -1.55, 6.55), (2.05, 1.65, 1.30), R=RT, k=0.6, bone=bl, tag='belly_low'))
    # ribcage / chest
    P.append(Ellipsoid(T(0.0, 0.05, 8.95), (2.95, 1.95, 1.80), R=RT, k=0.7, bone=ut, tag='chest'))
    P.append(Ellipsoid(T(0.0, 0.85, 7.60), (2.55, 1.35, 1.90), R=RT, k=0.7, bone=ut, tag='back_low'))
    # pecs: heavy slabs with a crisp lower edge
    for s in (-1, 1):
        P.append(Ellipsoid(T(s * 1.22, -1.30, 9.30), (1.38, 0.78, 0.86),
                           R=RT @ rot_xyz(8, s * -12, s * 10), k=0.22, bone=ut, tag='pec'))
    # traps / upper back hump that rises into the neck
    P.append(Ellipsoid(T(0.0, 0.55, 10.05), (2.40, 1.45, 1.15), R=RT, k=0.6, bone=ut, tag='traps'))
    for s in (-1, 1):
        P.append(Ellipsoid(T(s * 1.55, 0.45, 10.35), (1.05, 1.05, 0.72), R=RT, k=0.5, bone=ut, tag='trap_side'))
        # shoulder mass (the socket the deltoid grows out of)
        P.append(Ellipsoid(T(s * 2.75, 0.20, 9.55), (1.25, 1.35, 1.20), R=RT, k=0.55, bone=ut, tag='shoulder'))
        # lats flaring under the arms
        P.append(Ellipsoid(T(s * 1.95, 0.60, 8.15), (0.95, 1.20, 1.45), R=RT, k=0.6, bone=ut, tag='lat'))
        # love handles over the hips
        P.append(Ellipsoid(Pv(s * (1.82 if s > 0 else 1.45), 0.20, 6.05), (0.90, 1.25, 1.00), R=RP, k=0.6, bone=lt, tag='flank'))
    # neck: short and thick, buried in the traps
    P.append(RoundCone(T(0.0, 0.05, 9.90), Hd(0.0, 0.20, -0.75), 1.00, 0.86, k=0.45, bone='Head', tag='neck'))
    # navel pit
    P.append(Ellipsoid(T(0.10, -3.22, 6.80), (0.13, 0.30, 0.16), R=RT, k=0.08, bone=bl, op='sub', tag='navel'))
    return P


def head_prims():
    """Head-local layout measured off the reference face (84.7 px/stud at the face
    plane): crown front edge +0.94, brow +0.13..+0.47, eye centre 0, sclera
    bottom -0.21, mouth -0.47..-0.72, chin -1.24; half widths: crown 0.60,
    eye line 0.76, cheeks 0.78, jaw 0.77, ears 0.95."""
    P = []
    hb, jb = 'Head', 'Jaw'
    # cranium: short above the brow, narrower at the crown, top sloping back
    P.append(TaperBox(Hd(0.0, 0.10, 0.44), (0.70, 0.88, 0.66), R=RH @ rot_xyz(10, 0, 0), round_=0.42,
                      scale_bottom=1.26, k=0.22, bone=hb, tag='skull'))
    P.append(Ellipsoid(Hd(0.0, 0.42, 0.28), (0.74, 0.68, 0.84), R=RH, k=0.3, bone=hb, tag='occiput'))
    # mid-face block: widest at the cheeks
    P.append(RoundBox(Hd(0.02, -0.52, -0.34), (0.90, 0.44, 0.56), R=RH, round_=0.30, k=0.22, bone=hb, tag='face'))
    for s in (-1, 1):
        P.append(Ellipsoid(Hd(s * 0.56, -0.80, -0.30), (0.38, 0.29, 0.31), R=RH, k=0.15, bone=hb, tag='cheek'))
    # heavy brow: two slabs in an angry V, inner ends lower, meeting at a notch
    for s in (-1, 1):
        R = RH @ rot_xyz(-10, -s * 15, s * 12)
        P.append(RoundBox(Hd(s * 0.36, -1.00, 0.29), (0.38, 0.25, 0.17), R=R, round_=0.09,
                          k=0.16, bone='Brow', tag='brow'))
    P.append(Ellipsoid(Hd(0.0, -1.02, -0.26), (0.13, 0.10, 0.11), R=RH, k=0.08, bone=hb, tag='nose'))
    # upper lip
    P.append(RoundBox(Hd(0.05, -0.86, -0.40), (0.62, 0.21, 0.13), R=RH @ rot_xyz(0, -4, 0), round_=0.10,
                      k=0.12, bone=hb, tag='muzzle'))
    # lower jaw: wide, heavy and jutting past the upper lip
    P.append(RoundBox(Hd(0.07, -0.80, -0.98), (0.94, 0.52, 0.29), R=RH @ rot_xyz(-6, -4, 0), round_=0.20,
                      k=0.14, bone=jb, tag='jaw'))
    P.append(RoundBox(Hd(0.07, -0.20, -0.90), (0.86, 0.55, 0.32), R=RH, round_=0.22, k=0.25, bone=jb, tag='jaw_back'))
    # ears: small flattened lobes with a pointed top, set at eye level
    for s in (-1, 1):
        P.append(Ellipsoid(Hd(s * 0.84, -0.02, 0.04), (0.11, 0.20, 0.25), R=RH @ rot_xyz(0, s * 18, 0), k=0.08,
                           bone=hb, tag='ear'))
        P.append(RoundCone(Hd(s * 0.86, 0.0, 0.16), Hd(s * 0.99, 0.10, 0.42), 0.11, 0.025, k=0.06, bone=hb,
                           tag='ear', squash=(1.0, 0.5), x_hint=RH @ np.array([0, 1.0, 0])))
    # --- carving (applied last): brow notch, ear hollows, eye socket, mouth
    P.append(RoundBox(Hd(0.0, -1.16, 0.33), (0.025, 0.24, 0.14), R=RH, round_=0.02, k=0.03, bone='Brow', op='sub',
                      tag='notch'))
    for s in (-1, 1):
        P.append(Ellipsoid(Hd(s * 0.93, -0.06, 0.06), (0.05, 0.12, 0.17), R=RH @ rot_xyz(0, s * 18, 0), k=0.03,
                           bone=hb, op='sub', tag='ear_hollow'))
    P.append(Ellipsoid(Hd(0.0, -0.99, -0.01), (0.345, 0.34, 0.325), R=RH, k=0.04, bone=hb, op='sub', tag='socket'))
    # open grimace: a crescent - the upper edge arches up in the middle, the
    # heavy lower lip curls up toward the corners
    P.append(Ellipsoid(Hd(0.05, -1.12, -0.55), (0.56, 0.42, 0.13), R=RH @ rot_xyz(0, -4, 0), k=0.04, bone=jb,
                       op='sub', tag='mouth'))
    P.append(Ellipsoid(Hd(0.05, -1.10, -0.47), (0.30, 0.38, 0.08), R=RH, k=0.04, bone='Head', op='sub', tag='mouth'))
    return P


def arm_prims(side, rest=True):
    """Upper arm, elbow, forearm (reference pose unless rest=True)."""
    s = -1 if side == 'Right' else 1
    S, E, W = J[side + 'UpperArm'], J[side + 'LowerArm'], J[side + 'Hand']
    ub, lb = side + 'UpperArm', side + 'LowerArm'
    P = []
    # deltoid cap grows out of the shoulder
    dout = 0.35 if side == 'Left' else 0.12
    P.append(Ellipsoid(S + (E - S) * 0.14 + np.array([s * dout, 0.0, 0.05]), (1.30, 1.35, 1.30) if side == 'Left' else (1.20, 1.30, 1.26),
                       R=RT, k=0.55, bone=ub, tag='deltoid'))
    P.append(RoundCone(S, E, 1.18, 0.98, k=0.5, bone=ub, tag='upperarm', squash=(1.0, 1.08)))
    # biceps (front) and triceps (back/outer) bellies
    fwd = RT @ np.array([0, -1.0, 0])
    P.append(Ellipsoid(S + (E - S) * 0.55 + fwd * 0.45, (0.95, 0.85, 1.05),
                       R=frame_from(E - S, fwd), k=0.45, bone=ub, tag='biceps'))
    P.append(Ellipsoid(S + (E - S) * 0.50 - fwd * 0.45 + np.array([s * (0.06 if side == 'Right' else 0.52), 0, 0]),
                       (0.95, 0.9, 1.10),
                       R=frame_from(E - S, fwd), k=0.45, bone=ub, tag='triceps'))
    # elbow
    P.append(Ellipsoid(E, (0.95, 0.95, 0.90), R=frame_from(W - E, fwd), k=0.4, bone=lb, tag='elbow'))
    # forearm: Popeye bulge high, taper to the wrist
    P.append(RoundCone(E, W, 1.04 if side == 'Right' else 1.10, 0.82 if side == 'Right' else 0.86, k=0.45, bone=lb, tag='forearm', squash=(1.05, 1.0)))
    P.append(Ellipsoid(E + (W - E) * 0.30, (1.12, 1.05, 0.95), R=frame_from(W - E, fwd), k=0.4,
                       bone=lb, tag='forearm_bulge'))
    if rest:
        M = rest_arm_rotation(side)
        for p in P:
            p.transformed(M, S)
    return P


def leg_prims(side):
    s = -1 if side == 'Right' else 1
    Hp, K, A = J[side + 'UpperLeg'], J[side + 'LowerLeg'], J[side + 'Foot']
    ub, lb, fb, tb = side + 'UpperLeg', side + 'LowerLeg', side + 'Foot', side + 'Toes'
    P = []
    fwd = FOOT_DIR[side]
    P.append(RoundCone(Hp + np.array([0, 0, 0.35]), K + np.array([-s * 0.12, 0, 0]), 1.45, 1.02, k=0.6, bone=ub, tag='thigh'))
    P.append(Ellipsoid(Hp + (K - Hp) * 0.40 + np.array([-s * 0.28, 0.1, 0]), (1.18, 1.30, 1.20),
                       R=frame_from(K - Hp, fwd), k=0.5, bone=ub, tag='thigh_bulk'))
    P.append(Ellipsoid(K + fwd * 0.20 + np.array([-s * 0.15, 0, 0.05]), (0.90, 0.95, 0.85), R=frame_from(A - K, fwd),
                       k=0.35, bone=lb, tag='knee'))
    P.append(RoundCone(K, A, 1.20, 1.00, k=0.45, bone=lb, tag='shin'))
    P.append(Ellipsoid(K + (A - K) * 0.35 - fwd * 0.30 + np.array([-s * 0.22, 0, 0]), (1.10, 1.05, 1.00),
                       R=frame_from(A - K, fwd), k=0.45, bone=lb, tag='calf'))
    P.append(Ellipsoid(A + np.array([0, 0, 0.15]), (0.92, 0.95, 0.70), R=frame_from((0, 0, 1), fwd), k=0.4,
                       bone=fb, tag='ankle'))
    # foot: a broad slab, toes separate blocks
    Rf = frame_from((0, 0, 1), np.cross(fwd, (0, 0, 1)))    # local x = foot's lateral axis
    # make local Y = forward
    Rf = np.stack([np.cross(fwd, (0, 0, 1)), fwd, np.array([0, 0, 1.0])], 1)
    heel = A - fwd * 0.75
    mid = A + fwd * 0.55
    P.append(RoundBox(np.array([mid[0], mid[1], 0.42]) - fwd * 0.12, (1.12, 1.10, 0.42), R=Rf, round_=0.26, k=0.35,
                      bone=fb, tag='foot'))
    P.append(Ellipsoid(np.array([heel[0], heel[1], 0.45]), (0.85, 0.75, 0.45), R=Rf, k=0.35, bone=fb, tag='heel'))
    P.append(TaperBox(np.array([A[0], A[1], 0.75]) + fwd * 0.45, (1.0, 1.05, 0.40), R=Rf, round_=0.25,
                      scale_bottom=1.15, k=0.4, bone=fb, tag='instep'))
    # toes: big toe medial, four blocks across the front
    lat = np.cross(fwd, (0, 0, 1)) * (1 if side == 'Left' else -1)   # points laterally (away from body)
    front = A + fwd * (FOOT_LEN - TOE_LEN * 0.5)
    widths = [0.41, 0.34, 0.31, 0.29]
    offs = [-0.80]
    for i in range(1, 4):
        offs.append(offs[-1] + widths[i - 1] + widths[i] + 0.05)
    lens = [1.0, 0.94, 0.88, 0.80]
    for i in range(4):
        c = front + lat * offs[i] - fwd * (1 - lens[i]) * TOE_LEN * 0.7
        P.append(RoundBox(np.array([c[0], c[1], 0.34 - 0.02 * i]), (widths[i], TOE_LEN * 0.55 * lens[i], 0.34 - 0.02 * i),
                          R=Rf @ rot_xyz(-6, 0, 0), round_=0.15, k=0.10, bone=tb, tag=f'toe{i}'))
    return P


def body_prims(rest=True):
    P = torso_prims() + head_prims()
    for side in ('Right', 'Left'):
        P += arm_prims(side, rest=rest)
    for side in ('Right', 'Left'):
        P += leg_prims(side)
    # carving operations must come last so they cut through blended volumes
    unions = [p for p in P if p.op == 'union']
    subs = [p for p in P if p.op != 'union']
    return unions + subs


# ------------------------------------------------------------------------ hands
# Hand-local layout (studs): +Y from the wrist toward the knuckles, +Z = back of
# the hand, X across the knuckles. Authored with the THUMB on -X (right hand);
# the left hand mirrors x -> -x (MIRROR), so both hands keep right-handed bone
# frames. Rotations mirror as R(Ma, -angle).
MIRROR = {'Right': 1.0, 'Left': -1.0}
FINGER_NAMES = ['Index', 'Middle', 'Ring', 'Pinky']
FINGER_X = [-0.76, -0.25, 0.25, 0.73]
FINGER_SPLAY = [-4, -1, 2, 6]
FINGER_SCALE = [0.97, 1.0, 0.96, 0.84]
SEG_LEN = [0.66, 0.52, 0.44]
SEG_RAD = [0.235, 0.225, 0.205]
REST_CURL = [16, 20, 10]
FIST_CURL = {'Left': [88, 98, 60], 'Right': [86, 100, 64]}
THUMB_BASE = np.array([-0.70, 0.0, -0.55])
THUMB_DIR = np.array([-0.45, 0.80, -0.40])
THUMB_AXIS = np.array([0.30, 0.20, 0.93])
THUMB_LEN = [0.55, 0.44, 0.36]
FINGER_BASE_YZ = (1.10, -0.20)     # must equal fc_grip.FINGER_BASE
THUMB_RAD = [(0.33, 0.30), (0.30, 0.27), (0.27, 0.22)]
THUMB_REST = [8, 10, 6]
THUMB_FIST = {'Left': [38, 30, 26], 'Right': [34, 32, 26]}

# Club (reference pose). The haft axis passes through the right fist and exits
# on the THUMB side, running forward-down to the stone, as in the reference.
CLUB_STONE_C = np.array([-4.34, -2.95, 1.68])


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


WRIST_BEND_MAX = 32.0     # deg: the right wrist may cock this far toward the club
TUNNEL = np.array([0.0, 0.60, -0.76])   # centre of the curled-finger tunnel, hand local


GRIP_PX = (185, 835)          # fist centre on the reference (pixels)
WRIST_PX = (177, 772)         # bottom of the right wrap
ELBOW_PX = (224, 606)


FOREARM_LEN_R = 2.2


@functools.lru_cache(maxsize=None)
def right_arm_from_reference():
    """Elbow and wrist of the right arm from the reference wrap (top/bottom),
    the wrist depth chosen so the forearm keeps FOREARM_LEN_R."""
    from fc_camera import RefCam
    cam = RefCam()
    E = cam.at(*ELBOW_PX, 0.2)
    best = None
    for wd in np.linspace(-2.5, 0.8, 133):
        W = cam.at(*WRIST_PX, wd)
        err = abs(np.linalg.norm(W - E) - FOREARM_LEN_R)
        if best is None or err < best[0]:
            best = (err, W)
    return E, best[1]


# ---- right-hand grip on the club ------------------------------------------
# A real hammer grip: the palm sits behind the handle, the four fingers curl
# round its front, the thumb closes over the index finger from the other side,
# and the handle crosses the palm on a diagonal (index knuckle -> heel of the
# hand), leaving the fist on the thumb side toward the stone and on the pinky
# side as a short butt with a pommel. The wrist stays close to the forearm line.
GRIP_BEND_MAX = 28.0                          # wrist deviation allowed from the forearm line (deg)
CLUB_AIM_PX = (160, 1143)                     # the haft is aimed here; the lashed stone sits a little right of its line
FIST_PX = (162, 835)


def grip_local():
    """The canonical closed grip (fc_grip): haft centre/direction and every digit
    joint in scaled right-hand-local coordinates."""
    import fc_grip
    return fc_grip.solve(HS_SIDE['Right'], HAFT_R[0], tuple(FINGER_X), tuple(FINGER_SPLAY), tuple(FINGER_SCALE), tuple(SEG_LEN),
                         tuple(SEG_RAD), tuple(THUMB_BASE), tuple(THUMB_LEN), THUMB_RAD[0][0])


@functools.lru_cache(maxsize=None)
def solve_right_grip():
    """Place the gripping hand in the world: search the elbow depth (the image
    fixes only its pixel), the wrist deviation (<= GRIP_BEND_MAX) and the hand
    roll so the held haft points at the reference's haft line, the fist lands on
    the reference fist and the back of the hand faces outward."""
    from fc_camera import RefCam
    cam = RefCam()
    aim = cam.at(*CLUB_AIM_PX, -2.95)
    out_dir = _unit([-1.0, -0.3, 0.0])
    tun, hl, _, _ = grip_local()
    rolls = np.radians(np.arange(0, 360, 2.0))
    best = None
    # The image fixes only the pixels of the elbow and wrist. Their depths are
    # chosen so the arm bends the natural way: the elbow level with or behind
    # the shoulder, the forearm reaching FORWARD to the fist (a hanging arm whose
    # elbow points back), never the hyperextended reverse.
    for ed in (1.3, 1.1, 0.9, 0.7):
        E = cam.at(*ELBOW_PX, ed)
        bw = None
        for wd in np.linspace(-2.5, ed - 0.3, 160):
            Wc = cam.at(*WRIST_PX, wd)
            e = abs(np.linalg.norm(Wc - E) - FOREARM_LEN_R)
            if bw is None or e < bw[0]:
                bw = (e, Wc)
        W = bw[1]
        F = _unit(W - E)
        a0 = _unit(np.cross(F, [0, 0, 1.0]))
        b0 = np.cross(F, a0)
        for bend in np.arange(0, GRIP_BEND_MAX + 0.1, 2.0):
            for az in range(0, 360, 10):
                ax = math.cos(math.radians(az)) * a0 + math.sin(math.radians(az)) * b0
                y = axis_angle(ax, bend) @ F
                ref = _unit(np.cross(y, [0, 0, 1.0]))
                ref2 = np.cross(y, ref)
                Z = np.cos(rolls)[:, None] * ref[None] + np.sin(rolls)[:, None] * ref2[None]
                X = np.cross(y[None], Z)
                T = W[None] + X * tun[0] + y[None] * tun[1] + Z * tun[2]
                hh = X * hl[0] + y[None] * hl[1] + Z * hl[2]
                need = aim[None] - T
                need /= np.linalg.norm(need, axis=1, keepdims=True)
                err = np.degrees(np.arccos(np.clip(np.sum(hh * need, 1), -1, 1)))
                uv, _ = cam.project(T)
                pd = np.hypot(uv[:, 0] - FIST_PX[0], uv[:, 1] - FIST_PX[1])
                ok = Z @ out_dir >= 0.15
                cost = err + 0.35 * bend + 0.12 * pd + np.where(ok, 0, 1e3)
                i = int(np.argmin(cost))
                if best is None or cost[i] < best[0]:
                    Rh = np.stack([X[i], y, Z[i]], 1)
                    best = (float(cost[i]), Rh, W, T[i], hh[i], E, bend, float(err[i]), ed)
    return best


def hand_frame_ref(side):
    """(Rh, wrist) in the REFERENCE pose. Rh columns = hand local X, Y, Z.

    Right: the solved grip. Left: a closed fist with the knuckles forward-down
    and the back of the hand toward the camera and up, as in the reference."""
    if side == 'Right':
        g = solve_right_grip()
        return g[1], g[2]
    y = _unit([0.30, -0.55, -0.80])
    z = np.array([0.35, -0.60, 0.70])
    W = J['LeftHand']
    z = _unit(z - y * (z @ y))
    x = np.cross(y, z)
    return np.stack([x, y, z], 1), W


def club_axis():
    """(grip point = centre of the finger tunnel, unit haft direction toward the stone)."""
    g = solve_right_grip()
    return g[3], _unit(g[4])


def club_stone_center():
    """The lashed stone's centre (reference), slightly off the haft line."""
    return CLUB_STONE_C.copy()


def hand_frame(side, pose='REF'):
    Rh, W = hand_frame_ref(side)
    if pose == 'REST':
        M = rest_arm_rotation(side)
        S = J[side + 'UpperArm']
        return M @ Rh, (W - S) @ M.T + S
    return Rh, W


HS = 1.08        # hand scale (left); the right fist is seen edge-on in the reference and is a little smaller
HS_SIDE = {'Left': 1.08, 'Right': 1.08}


def _hand_local(side, v):
    v = np.array(v, float) * HS_SIDE[side]
    v[0] *= MIRROR[side]
    return v


def _rot_local(side, axis, deg):
    """Rotation in hand-local space, mirrored for the left hand."""
    a = np.array(axis, float)
    a[0] *= MIRROR[side]
    return axis_angle(a, deg * MIRROR[side])


HAFT_R = (0.32, 0.48)     # haft radius at the grip and at the stone


def _chain(p0, Rh, side, d0, axis, curls, lens, sign=-1.0):
    pts = [p0]
    tot = 0.0
    for k in range(3):
        tot += curls[k]
        d = axis_angle(axis, sign * tot) @ d0
        pts.append(pts[-1] + Rh @ _hand_local(side, d * lens[k]))
    return pts


def _dist_to_line(P, o, h):
    v = P - o
    return np.linalg.norm(v - np.outer(v @ h, h), axis=1)


def finger_points(side, pose):
    """Joint positions (world) for all digits: {bone: (head, tail)}."""
    Rh, W = hand_frame(side, pose)
    L = lambda v: Rh @ _hand_local(side, v) + W
    out = {}
    if side == 'Right' and pose == 'REF':
        _, _, GJ, _ = grip_local()
        for nm in FINGER_NAMES + ['Thumb']:
            pts = [Rh @ np.asarray(p) + W for p in GJ[nm]]
            for k in range(3):
                out[f'{side}{nm}{k + 1}'] = (pts[k], pts[k + 1])
        return out, Rh, W
    for i, nm in enumerate(FINGER_NAMES):
        curls = REST_CURL if pose == 'REST' else FIST_CURL[side]
        p0 = L([FINGER_X[i], FINGER_BASE_YZ[0], FINGER_BASE_YZ[1]])
        d0 = axis_angle((0, 0, 1), FINGER_SPLAY[i]) @ np.array([0, 1.0, 0])   # authoring space
        pts = _chain(p0, Rh, side, d0, (1, 0, 0), curls, [l * FINGER_SCALE[i] for l in SEG_LEN])
        for k in range(3):
            out[f'{side}{nm}{k + 1}'] = (pts[k], pts[k + 1])
    tc = THUMB_REST if pose == 'REST' else THUMB_FIST[side]
    pts = _chain(L(THUMB_BASE), Rh, side, _unit(THUMB_DIR), _unit(THUMB_AXIS), tc, THUMB_LEN, sign=-1.0)
    for k in range(3):
        out[f'{side}Thumb{k + 1}'] = (pts[k], pts[k + 1])
    return out, Rh, W


def hand_prims(side, pose='REST'):
    joints, Rh, W = finger_points(side, pose)
    HS = HS_SIDE[side]
    hb = side + 'Hand'
    L = lambda v: Rh @ _hand_local(side, v) + W
    xh = Rh[:, 0]
    P = []
    P.append(RoundBox(L([0.0, 0.52, 0.03]), np.array((1.02, 0.66, 0.43)) * HS, R=Rh, round_=0.26 * HS, k=0.10,
                      bone=hb, tag='palm'))
    P.append(RoundCone(L([0.0, -0.60, 0.0]), L([0.0, 0.20, 0.0]), 0.74 * HS, 0.82 * HS, k=0.22, bone=hb,
                       tag='wrist', squash=(1.22, 0.74), x_hint=xh))
    P.append(RoundBox(L([0.0, 0.98, 0.06]), np.array((0.94, 0.20, 0.32)) * HS, R=Rh, round_=0.16 * HS, k=0.12,
                      bone=hb, tag='knuckles'))
    P.append(Ellipsoid(L([-0.60, 0.18, -0.36]), np.array((0.44, 0.55, 0.36)) * HS, R=Rh, k=0.12, bone=hb,
                       tag='thenar'))
    # one knuckle per finger (heads of the metacarpals), staggered by the finger roots
    for i, nm in enumerate(FINGER_NAMES):
        h0, h1 = joints[f'{side}{nm}1']
        rk = 0.27 * HS * (0.88 if i == 3 else 1.0)
        P.append(Ellipsoid(h0 + Rh[:, 2] * 0.10 * HS, (rk, rk * 1.05, rk * 0.95), R=Rh, k=0.09, bone=hb,
                           tag='knuckle'))
    for i, nm in enumerate(FINGER_NAMES):
        for k in range(3):
            b = f'{side}{nm}{k + 1}'
            h0, h1 = joints[b]
            sc = (0.9 if i == 3 else 1.0) * HS
            r0 = SEG_RAD[k] * sc
            r1 = SEG_RAD[min(k + 1, 2)] * sc * (0.9 if k == 2 else 1.0)
            P.append(RoundCone(h0, h1, r0, r1, k=0.05, bone=b, tag=f'finger{i}{k}', squash=(1.0, 1.0), x_hint=xh))
    for k in range(3):
        b = f'{side}Thumb{k + 1}'
        h0, h1 = joints[b]
        P.append(RoundCone(h0, h1, THUMB_RAD[k][0] * HS, THUMB_RAD[k][1] * HS, k=0.06, bone=b, tag=f'thumb{k}',
                           x_hint=xh))
    return P


# the right forearm ends where the solved grip puts the wrist
_G = solve_right_grip()
J['RightLowerArm'], J['RightHand'] = _G[5], _G[2]



# ------------------------------------------------------------------ landmarks
# Design points that must project onto the reference landmarks (pixel targets).
def design_landmarks():
    return {
        'head_top': (Hd(0.0, -0.40, 1.06), (541, 185)),
        'eye_center': (Hd(0.0, -1.00, 0.02), (542, 263)),
        'chin_bottom': (Hd(0.07, -1.10, -1.24), (545, 371)),
        'brow_notch': (Hd(0.0, -1.05, 0.30), (539, 240)),
        'sternum_top': (T(0.0, -2.05, 9.95), (505, 420)),
        'navel': (T(0.10, -3.22, 6.80), (487, 690)),
        'wrapR_center': ((J['RightLowerArm'] + J['RightHand']) / 2, (190, 705)),
        'wrapL_center': ((J['LeftLowerArm'] + J['LeftHand']) / 2 + np.array([0, -0.3, 0]), (947, 815)),
        'kneeR': (J['RightLowerLeg'] + np.array([0, -1.0, 0]), (400, 1010)),
        'kneeL': (J['LeftLowerLeg'] + np.array([0, -1.0, 0]), (745, 1040)),
    }
