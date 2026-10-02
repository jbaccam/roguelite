#!/usr/bin/env python3
"""Build PetRigs.luau from the 12 blender-pet-kit/<kit>/studio-install-data.json files.

Run:  python build_pet_rigs.py
Reads  roguelite-planning/blender-pet-kit/<kit>/studio-install-data.json  (never edits them)
Writes roguelite-planning/studio-prototype/combat/PetRigs.luau

Each kit's JSON has a different schema (written by different agents); the per-pet
functions below map each one to the common schema documented in the Luau header.
Clips the kits did not provide are synthesised and flagged synth = true.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
COMBAT = os.path.dirname(HERE)
PLANNING = os.path.dirname(os.path.dirname(COMBAT))
KITS = os.path.join(PLANNING, "blender-pet-kit")
OUT = os.path.join(COMBAT, "PetRigs.luau")

WARN = []


def warn(msg):
    WARN.append(msg)
    print("WARN:", msg)


# --------------------------------------------------------------------------- clip helpers
def vec(v):
    return [float(x) for x in v]


def avg(a, b):
    """average two joint dicts {part:[rx,ry,rz]}; missing = rest (0)."""
    out = {}
    for k in set(a) | set(b):
        va = a.get(k, [0, 0, 0])
        vb = b.get(k, [0, 0, 0])
        out[k] = [(x + y) / 2 for x, y in zip(va, vb)]
    return out


def mk_frames(root, frames, duration, loop):
    """frames: list of dicts with keys
         j: {part:[rx,ry,rz]} (Studio deg)   o: {part:[x,y,z]} (studs, parent frame)
         lift, pitch, roll, yaw, name, and one of t (0-1) / at (seconds) (else evenly spaced).
       Root-part joint rotation becomes pitch/yaw/roll; root-part offset Y becomes lift."""
    n = len(frames)
    out = []
    for i, f in enumerate(frames):
        j = {k: vec(v) for k, v in (f.get("j") or {}).items()}
        o = {k: vec(v) for k, v in (f.get("o") or {}).items()}
        lift = f.get("lift", 0.0)
        pitch = f.get("pitch", 0.0)
        roll = f.get("roll", 0.0)
        yaw = f.get("yaw", 0.0)
        if root in j:
            rx, ry, rz = j.pop(root)
            pitch += rx
            yaw += ry
            roll += rz
        if root in o:
            ox, oy, oz = o.pop(root)
            lift += oy
            if abs(ox) > 1e-6 or abs(oz) > 1e-6:
                warn("root offset x/z dropped on frame %s" % f.get("name"))
        # drop all-zero offsets
        o = {k: v for k, v in o.items() if any(abs(x) > 1e-9 for x in v)}
        if "t" in f:
            t = f["t"]
        elif "at" in f:
            t = f["at"] / duration
        elif loop:
            t = i / n
        else:
            t = i / (n - 1) if n > 1 else 0.0
        fr = {}
        if f.get("name"):
            fr["name"] = f["name"]
        fr["t"] = t
        fr["joints"] = j
        if o:
            fr["offsets"] = o
        fr["lift"] = lift
        fr["pitch"] = pitch
        fr["roll"] = roll
        if abs(yaw) > 1e-9:
            fr["yaw"] = yaw
        out.append(fr)
    return out


def clip(root, frames, duration, loop, synth=False, **extra):
    c = {"loop": loop, "duration": duration}
    if synth:
        c["synth"] = True
    c.update(extra)
    c["frames"] = mk_frames(root, frames, duration, loop)
    return c


def pose_clip(root, joints, duration=0.4, lift=0.0, pitch=0.0, roll=0.0, offsets=None, synth=False, **extra):
    """rest -> pose, held at the pose (blend-in over `duration`)."""
    return clip(
        root,
        [dict(j={}, name="rest", t=0.0),
         dict(j=joints, o=offsets, lift=lift, pitch=pitch, roll=roll, name="pose", t=1.0)],
        duration, False, synth=synth, hold=True, **extra)


def synth_idle(root, sway, lift=0.02, dur=2.4):
    """2-frame idle. sway = list of (part, axis 0/1/2, amplitude deg): +amp then -amp."""
    f0 = {"j": {}, "lift": 0.0, "name": "idle_a", "t": 0.0}
    f1 = {"j": {}, "lift": lift, "name": "idle_b", "t": 0.5}
    for part, ax, amp in sway:
        f0["j"].setdefault(part, [0, 0, 0])[ax] += amp
        f1["j"].setdefault(part, [0, 0, 0])[ax] -= amp
    return clip(root, [f0, f1], dur, True, synth=True)


def synth_bob_idle(root, amp, pitch_amp, period, tail=None, tail_amp=0.0):
    """hover bob for flyers (additive on top of the wingbeat)."""
    def tj(s):
        return {tail: [0, s * tail_amp, 0]} if tail else {}
    fr = [dict(lift=0, pitch=0, name="mid", t=0.0),
          dict(j=tj(1), lift=amp, pitch=pitch_amp, name="up", t=0.25),
          dict(lift=0, pitch=0, name="mid2", t=0.5),
          dict(j=tj(-1), lift=-amp, pitch=-pitch_amp, name="down", t=0.75)]
    return clip(root, fr, period, True, synth=True, additive=True)


def synth_trot(root, legs, extra_a=None, extra_b=None, cycle=0.6, swing=28.0, bob=0.04):
    """legs = {'FL','FR','BL','BR'} -> part names; diagonal pairs swing +-swing."""
    a = {legs["FL"]: [swing, 0, 0], legs["BR"]: [swing, 0, 0],
         legs["FR"]: [-swing, 0, 0], legs["BL"]: [-swing, 0, 0]}
    b = {k: [-v[0], 0, 0] for k, v in a.items()}
    a.update(extra_a or {})
    b.update(extra_b or {})
    fr = [dict(j=a, roll=-2, name="step_a", t=0.0),
          dict(j={}, lift=bob, name="pass_a", t=0.25),
          dict(j=b, roll=2, name="step_b", t=0.5),
          dict(j={}, lift=bob, name="pass_b", t=0.75)]
    return clip(root, fr, cycle, True, synth=True)


# --------------------------------------------------------------------------- common part table
def part_table(d, neon_by_part=None):
    parts = {}
    for name, p in d["parts"].items():
        e = {
            "pivot": vec(p["pivot"]),
            "center": vec(p["center"]),
            "size": vec(p["size"]),
            "parent": p.get("joint_parent"),
            "glow": "_Glow" in name,
        }
        if neon_by_part and name in neon_by_part:
            e["neon"] = vec(neon_by_part[name])
        parts[name] = e
    return parts


def find_root(d):
    roots = [n for n, p in d["parts"].items() if p.get("joint_parent") is None]
    assert len(roots) == 1, roots
    return roots[0]


# --------------------------------------------------------------------------- vfx normalisation
def norm_vfx(vfx_list, d):
    """Copy verbatim, then add Studio-axis offsets relative to the named part's pivot:
       offset = {x,y,z}   (single attachment)   offsets = {...}  (several)."""
    piv = {n: p["pivot"] for n, p in d["parts"].items()}
    out = []
    for v in vfx_list:
        v = json.loads(json.dumps(v))
        part = v.get("part") if isinstance(v.get("part"), str) else None
        if "attachment_position_from_part_pivot" in v:
            v["offset"] = v["attachment_position_from_part_pivot"]
        elif "attachment_from_part_pivot" in v:
            v["offset"] = v["attachment_from_part_pivot"]
        elif "attachment_from_body_pivot" in v:
            v["offset"] = v["attachment_from_body_pivot"]
        elif v.get("kind") == "neon_pulse" and part in piv and "position" in v:
            v["offset"] = [round(a - b, 4) for a, b in zip(v["position"], piv[part])]
        if "attachment0_from_part_pivot" in v:
            v["offset0"] = v["attachment0_from_part_pivot"]
            v["offset1"] = v["attachment1_from_part_pivot"]
        if isinstance(v.get("attachments"), dict):
            v["offsets"] = {k: a["from_part_pivot"] for k, a in v["attachments"].items()}
        if isinstance(v.get("attachments_from_wing_pivot"), dict):
            v["offsets"] = v["attachments_from_wing_pivot"]
        if isinstance(v.get("parts"), dict):
            v["offsets"] = {k: a["attachment_from_part_pivot"] for k, a in v["parts"].items()
                            if "attachment_from_part_pivot" in a}
        out.append(v)
    return out


# --------------------------------------------------------------------------- per-pet builders
def load(kit):
    with open(os.path.join(KITS, kit, "studio-install-data.json"), encoding="utf-8") as f:
        return json.load(f)


def base(kit, name, suit, d, hover=0.0, locomotion=None, cycle=None, stride=None):
    root = find_root(d)
    pet = {
        "kit": kit, "name": name, "rarity": d.get("rarity", "Common"), "suit": suit,
        "root": root, "size": vec(d["overall_size"]),
        "hover": hover, "locomotion": locomotion, "cycle": cycle, "stride": stride,
    }
    return pet, root


def golden_retriever():
    d = load("golden-retriever")
    pet, r = base("golden-retriever", "Golden Retriever", "Loot", d, locomotion="trot", cycle=0.6, stride=4.0)
    P = lambda s: "Retriever_" + s
    legs = dict(FL=P("LegFL"), FR=P("LegFR"), BL=P("LegBL"), BR=P("LegBR"))
    move = synth_trot(r, legs, {P("Tail"): [0, 14, 0]}, {P("Tail"): [0, -14, 0]}, 0.6)
    idle = synth_idle(r, [(P("Head"), 0, 2), (P("Tail"), 1, 14), (P("EarL"), 2, 3), (P("EarR"), 2, -3)], 0.02, 2.4)
    action = clip(r, [
        dict(j={}, name="rest", t=0.0),
        dict(j={P("Head"): [-30, 0, 0], P("Body"): [-8, 0, 0], P("LegFL"): [35, 0, 0],
                P("LegFR"): [-10, 0, 0], P("Tail"): [0, 25, 0]}, name="sniff", t=0.25),
        dict(j={P("Head"): [-35, 0, 0], P("Body"): [-8, 0, 0], P("LegFL"): [-15, 0, 0],
                P("LegFR"): [35, 0, 0], P("Tail"): [0, -25, 0]}, name="dig_a", t=0.5),
        dict(j={P("Head"): [-35, 0, 0], P("Body"): [-8, 0, 0], P("LegFL"): [35, 0, 0],
                P("LegFR"): [-15, 0, 0], P("Tail"): [0, 25, 0]}, name="dig_b", t=0.75),
        dict(j={}, name="rest", t=1.0),
    ], 0.9, False, synth=True)
    pet["parts"] = part_table(d)
    pet["clips"] = {"move": move, "idle": idle, "action": action}
    pet["actionName"] = "fetch_dig"
    pet["vfx"] = []
    return pet


def bunny():
    d = load("bunny")
    h = d["hop"]
    pet, r = base("bunny", "Bunny", "Healing", d, locomotion=d["locomotion"], cycle=h["total_cycle_s"],
                  stride=h["suggested_hop_length_studs"])
    fr, at = [], 0.0
    for k in ["crouch", "launch", "airborne", "land"]:
        f = h["frames"][k]
        fr.append(dict(j={p: [v["studio_rx_deg"], 0, 0] for p, v in f["joints"].items()},
                       lift=f["body_up_studs"], name=k, at=at))
        at += f["duration_s"]
    assert abs(at - h["total_cycle_s"]) < 1e-6
    move = clip(r, fr, h["total_cycle_s"], True)
    P = lambda s: "Bunny_" + s
    idle = synth_idle(r, [(P("Head"), 0, 3), (P("Tail"), 1, 8), (P("EarL"), 2, 4), (P("EarR"), 2, -4)], 0.015, 2.4)
    action = clip(r, [
        dict(j={}, name="rest", t=0.0),
        dict(j={P("Head"): [-22, 0, 0], P("Body"): [-6, 0, 0], P("LegFL"): [30, 0, 0], P("LegFR"): [30, 0, 0],
                P("EarL"): [-12, 0, 0], P("EarR"): [-12, 0, 0]}, name="reach", t=0.3),
        dict(j={P("Head"): [8, 0, 0], P("Body"): [6, 0, 0]}, lift=0.1, name="toss", t=0.55),
        dict(j={}, name="rest", t=1.0),
    ], 0.7, False, synth=True)
    pet["parts"] = part_table(d)
    pet["clips"] = {"move": move, "idle": idle, "action": action}
    pet["actionName"] = "carrot_drop"
    pet["vfx"] = []
    return pet


def frog():
    d = load("frog")
    P = lambda s: "Frog_" + s
    hf = d["hop_frames"]
    recover = 0.25  # "recover eases back to rest over ~0.25 s"
    total = hf[-1]["time_s"] + recover
    pet, r = base("frog", "Frog", "Space", d, locomotion=d["locomotion"], cycle=round(total, 3), stride=3.0)

    def fj(f):
        return {P("Head"): [f["head_pitch_deg"], 0, 0],
                P("LegBL"): [f["hind_legs_pitch_deg"], 0, 0], P("LegBR"): [f["hind_legs_pitch_deg"], 0, 0],
                P("LegFL"): [f["front_legs_pitch_deg"], 0, 0], P("LegFR"): [f["front_legs_pitch_deg"], 0, 0]}
    fr = [dict(j=fj(f), lift=f["body_lift_studs"], pitch=f["body_pitch_deg"], name=f["frame"], at=f["time_s"])
          for f in hf]
    move = clip(r, fr, total, True)
    idle = synth_idle(r, [(P("Head"), 0, 3)], 0.02, 2.0)
    slam_f, apex_f = hf[-1], hf[2]
    action = clip(r, [
        dict(j=fj(apex_f), lift=apex_f["body_lift_studs"], pitch=apex_f["body_pitch_deg"], name="apex", at=0.0),
        dict(j=fj(slam_f), lift=slam_f["body_lift_studs"], pitch=slam_f["body_pitch_deg"], name="slam", at=0.22),
        dict(j={}, name="recover", at=0.47),
    ], 0.47, False)
    pet["parts"] = part_table(d)
    pet["clips"] = {"move": move, "idle": idle, "action": action}
    pet["actionName"] = "slam"
    pet["vfx"] = []
    return pet


def penguin():
    d = load("penguin")
    P = lambda s: "Penguin_" + s
    pet, r = base("penguin", "Penguin", "Slow", d, locomotion=d["locomotion"], cycle=1.0, stride=3.0)
    A = {P("Body"): [0, 0, 10], P("Head"): [0, 0, -4], P("FootL"): [24, 0, 0], P("FootR"): [-24, 0, 0],
         P("FlipperL"): [0, 0, -35], P("FlipperR"): [0, 0, 12]}
    B = {P("Body"): [0, 0, -10], P("Head"): [0, 0, 4], P("FootL"): [-24, 0, 0], P("FootR"): [24, 0, 0],
         P("FlipperL"): [0, 0, -12], P("FlipperR"): [0, 0, 35]}
    move = clip(r, [dict(j=A, name="step_a", t=0.0), dict(j=avg(A, B), lift=0.04, name="pass_a", t=0.25),
                    dict(j=B, name="step_b", t=0.5), dict(j=avg(A, B), lift=0.04, name="pass_b", t=0.75)],
                1.0, True)
    idle = synth_idle(r, [(P("Head"), 1, 8), (P("FlipperL"), 2, 5), (P("FlipperR"), 2, -5)], 0.015, 2.6)
    slide = {P("Head"): [45, 0, 0], P("FlipperL"): [0, 0, -30], P("FlipperR"): [0, 0, 30],
             P("FootL"): [20, 0, 0], P("FootR"): [20, 0, 0], P("Body"): [-78, 0, 0]}
    action = clip(r, [dict(j={}, name="rest", t=0.0), dict(j=slide, name="slide", t=0.2),
                      dict(j=slide, name="slide_hold", t=1.0)], 1.0, False, hold=True)
    pet["parts"] = part_table(d)
    pet["clips"] = {"move": move, "idle": idle, "action": action}
    pet["actionName"] = "belly_slide"
    pet["vfx"] = []
    return pet


def fox():
    d = load("fox")
    P = lambda s: "Fox_" + s
    pet, r = base("fox", "Fox", "Damage", d, locomotion="trot", cycle=0.5, stride=3.5)
    legs = dict(FL=P("LegFL"), FR=P("LegFR"), BL=P("LegBL"), BR=P("LegBR"))
    move = synth_trot(r, legs, {P("Tail"): [0, 16, 0], P("Scarf"): [0, 0, 8]},
                      {P("Tail"): [0, -16, 0], P("Scarf"): [0, 0, -8]}, 0.5)
    idle = synth_idle(r, [(P("Head"), 0, 2), (P("Tail"), 1, 16), (P("EarL"), 2, 3), (P("EarR"), 2, -3),
                          (P("Scarf"), 2, 6)], 0.02, 2.4)
    action = clip(r, [
        dict(j={}, name="rest", t=0.0),
        dict(j={P("Body"): [-10, 0, 0], P("LegFL"): [10, 0, 0], P("LegFR"): [10, 0, 0], P("LegBL"): [-15, 0, 0],
                P("LegBR"): [-15, 0, 0], P("Tail"): [-20, 0, 0], P("Head"): [-6, 0, 0]},
             lift=-0.15, name="windup", t=0.2),
        dict(j={P("Body"): [25, 0, 0], P("LegFL"): [55, 0, 0], P("LegFR"): [55, 0, 0], P("LegBL"): [-60, 0, 0],
                P("LegBR"): [-60, 0, 0], P("Tail"): [10, 0, 0], P("Head"): [-10, 0, 0]},
             lift=0.9, name="leap", t=0.4),
        dict(j={P("Body"): [-12, 0, 0], P("LegFL"): [30, 0, 0], P("LegFR"): [30, 0, 0], P("LegBL"): [10, 0, 0],
                P("LegBR"): [10, 0, 0], P("Tail"): [-10, 0, 0]}, lift=0.05, name="land", t=0.62),
        dict(j={}, name="recover", t=1.0),
    ], 0.75, False, synth=True)
    pet["parts"] = part_table(d)
    pet["clips"] = {"move": move, "idle": idle, "action": action}
    pet["actionName"] = "pounce"
    pet["vfx"] = []
    return pet


def bee():
    d = load("bee")
    h = d["hover"]
    H = h["hover_height_studs"]
    pet, r = base("bee", "Bee", "Poison", d, hover=H, locomotion=d["locomotion"], cycle=0.08, stride=0.8)

    def fj(name):
        f = h["frames"][name]
        return ({p: v["studio_rot_deg"] for p, v in f["joints"].items()}, round(f["body_up_studs"] - H, 4))
    ju, lu = fj("wings_up")
    jd, ld = fj("wings_down")
    # The wingbeat runs at 12-20 Hz: lifting the whole body with each stroke (the kit's +-0.07) made
    # the bee look shaky in flight (user, 2026-10-02). Only the wings beat; legs and jar flutter at
    # 40%, and the slow hover bob is halved so the up-and-down stays gentle.
    def calm(j):
        return {p: ([round(a * 0.4, 2) for a in v] if p in ("Bee_LegL", "Bee_LegR", "Bee_Jar") else v)
                for p, v in j.items()}
    move = clip(r, [dict(j=calm(ju), lift=0.0, name="wings_up", t=0.0),
                    dict(j=calm(jd), lift=0.0, name="wings_down", t=0.5)], 0.08, True)
    idle = synth_bob_idle(r, h["bob"]["amplitude_studs"] * 0.5, 4, h["bob"]["period_s"])
    jw, lw = fj("sting_windup")
    jdv, ldv = fj("sting_dive")
    rec = h["sting_dive"]["recover_time_s"]
    t0, t1 = h["frames"]["sting_windup"]["duration_s"], h["frames"]["sting_dive"]["duration_s"]
    total = t0 + t1 + rec
    action = clip(r, [
        dict(j=jw, lift=lw, name="sting_windup", at=0.0),
        dict(j=jdv, lift=ldv, name="sting_dive", at=t0),
        dict(j=jdv, lift=ldv, name="sting_hit", at=t0 + t1),
        dict(j={}, lift=0.0, name="recover_hover", at=total),
    ], round(total, 3), False, diveDistance=h["sting_dive"]["dive_distance_studs"])
    pet["parts"] = part_table(d)
    pet["clips"] = {"move": move, "idle": idle, "action": action}
    pet["actionName"] = "sting_dive"
    pet["vfx"] = []
    return pet


def turtle():
    d = load("turtle")
    L = d["locomotion_data"]
    pl = L["plod"]
    pet, r = base("turtle", "Turtle", "Defense", d, locomotion=d["locomotion"], cycle=pl["step_period_s"], stride=3.0)

    def fr(spec):
        return ({p: v["rot_deg_studio_xyz"] for p, v in spec.items()},
                {p: v["offset_studs_studio_xyz"] for p, v in spec.items()})
    frames = []
    for k in pl["loop"]:
        j, o = fr(pl["frames"][k])
        frames.append(dict(j=j, o=o, name=k))
    move = clip(r, frames, pl["step_period_s"], True)
    P = lambda s: "Turtle_" + s
    idle = synth_idle(r, [(P("Head"), 0, 3), (P("Tail"), 1, 8)], 0.015, 2.8)
    sj, so = fr(L["shield_up"]["pose"])
    action = clip(r, [
        dict(j={}, name="rest", t=0.0),
        dict(j=sj, o=so, name="shield_up", t=0.1875),
        dict(j=sj, o=so, name="shield_hold", t=0.6875),
        dict(j={}, name="ease_back", t=1.0),
    ], 0.8, False)
    pet["parts"] = part_table(d)
    pet["clips"] = {"move": move, "idle": idle, "action": action}
    pet["actionName"] = "shield_up"
    pet["vfx"] = []
    return pet


def monkey():
    d = load("monkey")
    L = d["locomotion_data"]
    sc = L["scamper"]
    cyc = round(2 * sc["step_period_s"], 3)
    pet, r = base("monkey", "Monkey", "Attack speed", d, locomotion=d["locomotion"], cycle=cyc, stride=5.0)
    A, B = sc["frame_A"]["studio_deg"], sc["frame_B"]["studio_deg"]
    bob = sc["body_bob_studs"]
    move = clip(r, [dict(j=A, name="step_a", t=0.0), dict(j=avg(A, B), lift=bob, name="pass_a", t=0.25),
                    dict(j=B, name="step_b", t=0.5), dict(j=avg(A, B), lift=bob, name="pass_b", t=0.75)],
                cyc, True)
    tc = L["tail_curl"]["studio_deg"]
    ta = tc["Monkey_Tail"]
    idle = clip(r, [
        dict(j={"Monkey_Tail": ta, "Monkey_Body": [-2, 0, 0]}, name="tail_curl_a", t=0.0),
        dict(j={"Monkey_Tail": [ta[0], -ta[1], ta[2]]}, lift=0.015, name="tail_curl_b", t=0.5),
    ], 2.2, True, synth=True)
    hy = L["hype_pose"]["studio_deg"]
    action = clip(r, [dict(j={}, name="rest", t=0.0), dict(j=hy, name="hype", t=0.2),
                      dict(j=hy, name="hype_hold", t=0.75), dict(j={}, name="rest", t=1.0)], 1.2, False)
    pet["parts"] = part_table(d)
    pet["clips"] = {"move": move, "idle": idle, "action": action,
                    "head_turn": pose_clip(r, L["head_turn"]["studio_deg"], 0.3),
                    "tail_curl": pose_clip(r, tc, 0.4)}
    pet["actionName"] = "hype"
    pet["vfx"] = []
    return pet


def lucky_cat():
    d = load("lucky-cat")
    L = d["locomotion_data"]
    pet, r = base("lucky-cat", "Lucky Cat", "Luck", d, locomotion=d["locomotion"], cycle=1.0, stride=4.0)
    fa, fb = L["frames"]
    move = clip(r, [
        dict(j=fa["studio_angles_deg"], lift=fa["body_offset_studs"][1], name="step_a", t=0.0),
        dict(j={}, lift=0.0, name="pass_a", t=0.25),
        dict(j=fb["studio_angles_deg"], lift=fb["body_offset_studs"][1], name="step_b", t=0.5),
        dict(j={}, lift=0.0, name="pass_b", t=0.75),
    ], 1.0, True)
    sw = d["extras"]["tail_swish"]["studio_angles_deg"]["LuckyCat_Tail"][1]
    idle = clip(r, [dict(j={"LuckyCat_Tail": [0, sw, 0]}, name="swish_l", t=0.0),
                    dict(j={"LuckyCat_Tail": [0, -sw, 0]}, name="swish_r", t=0.5)], 1.6, True)
    b = d["beckon_emote"]
    up, dn = b["frames"]
    frames = []
    for i, (f, nm) in enumerate([(up, "paw_up"), (dn, "paw_down"), (up, "paw_up"), (dn, "paw_down")]):
        frames.append(dict(j=f["studio_angles_deg"], lift=f["body_offset_studs"][1], name=nm, at=i * 0.5))
    frames.append(dict(j={}, name="lower_paw", at=b["duration_s"]))
    action = clip(r, frames, b["duration_s"], False, blendIn=b["blend_in_s"])
    ex = d["extras"]
    pet["parts"] = part_table(d, {"LuckyCat_CoinRim_Glow": d["glow_parts"]["LuckyCat_CoinRim_Glow"]["Color"]})
    pet["clips"] = {"move": move, "idle": idle, "action": action,
                    "head_tilt": pose_clip(r, ex["head_tilt"]["studio_angles_deg"], 0.4),
                    "tail_swish": pose_clip(r, ex["tail_swish"]["studio_angles_deg"], 0.4)}
    pet["actionName"] = "beckon_emote"
    pet["vfx"] = norm_vfx(d["vfx"], d)
    return pet


def owl():
    d = load("owl")
    L = d["locomotion_data"]
    H = L["hover_height_studs"]
    F = L["frames"]
    pet, r = base("owl", "Owl", "Bosses", d, hover=H, locomotion=d["locomotion"],
                  cycle=L["wingbeat"]["period_s"], stride=6.0)

    def fj(name):
        f = F[name]
        return {p: v["studio_rot_deg"] for p, v in f["joints"].items()}, round(f["body_up_studs"] - H, 4)
    ju, lu = fj("wings_up")
    jd, ld = fj("wings_down")
    move = clip(r, [dict(j=ju, lift=lu, name="wings_up", t=0.0), dict(j=jd, lift=ld, name="wings_down", t=0.5)],
                L["wingbeat"]["period_s"], True)
    idle = synth_bob_idle(r, L["bob"]["amplitude_studs"], 3, L["bob"]["period_s"])
    jm, lm = fj("mark_target")
    jh, lh = fj("hover_mid")
    action = clip(r, [dict(j=jh, lift=lh, name="hover_mid", t=0.0), dict(j=jm, lift=lm, name="mark_target", t=0.25),
                      dict(j=jm, lift=lm, name="mark_hold", t=0.6), dict(j=jh, lift=lh, name="hover_mid", t=1.0)],
                  0.6, False)
    jg, lg = fj("glide")
    ht, ph = F["head_turn"], F["perch_hop_turn"]
    sj = lambda f: {p: v["studio_rot_deg"] for p, v in f["joints"].items()}
    pet["parts"] = part_table(d, {"Owl_Reticle_Glow": [255, 116, 70]})
    pet["clips"] = {
        "move": move, "idle": idle, "action": action,
        "glide": pose_clip(r, jg, 0.25, lift=lg),
        # perched clips: lift is measured from the GROUND (grounded = true), not from hover
        "head_turn": pose_clip(r, sj(ht), ht["duration_s"], grounded=True),
        "perch_hop_turn": pose_clip(r, sj(ph), ph["duration_s"], lift=ph["body_up_studs"], grounded=True),
    }
    pet["actionName"] = "mark_target"
    pet["vfx"] = norm_vfx(d["vfx"], d)
    return pet


def cheetah():
    d = load("cheetah-cub")
    L = d["locomotion_data"]
    bob = L["body_bob_studs"]
    pet, r = base("cheetah-cub", "Cheetah Cub", "Speed", d, locomotion=d["locomotion"], cycle=L["period_s"], stride=5.0)
    fr = []
    for f in L["frames"]:
        nm = f["name"].split(":")[0]
        lift = -f["body_drop_studs"] + (bob if nm == "stretch" else 0.0)
        fr.append(dict(j=f["studio_deg"], lift=lift, name=nm, t=f["t"]))
    move = clip(r, fr, L["period_s"], True, walkScale={"below": 0.6, "angle": 0.6, "period": 1.2})
    P = lambda s: "CheetahCub_" + s
    idle = synth_idle(r, [(P("Head"), 0, 2), (P("Tail"), 1, 12), (P("EarL"), 2, 3), (P("EarR"), 2, -3),
                          (P("Scarf"), 0, 4)], 0.02, 2.2)
    z = L["zoom_sprint"]
    action = clip(r, [dict(j={}, name="rest", t=0.0),
                      dict(j=z["studio_deg"], lift=-z["body_drop_studs"], name="zoom", t=0.1),
                      dict(j=z["studio_deg"], lift=-z["body_drop_studs"], name="zoom_hold", t=0.9),
                      dict(j={}, name="rest", t=1.0)], 1.5, False, legOscillationDeg=12, legOscillationPeriod=0.25)
    pet["parts"] = part_table(d, {"CheetahCub_Scarf_Glow": d["glow_parts"]["CheetahCub_Scarf_Glow"]["Color"]})
    pet["clips"] = {"move": move, "idle": idle, "action": action,
                    "head_turn": pose_clip(r, L["head_turn"]["studio_deg"], 0.4),
                    "tail_flick": pose_clip(r, L["tail_flick"]["studio_deg"], 0.25)}
    pet["actionName"] = "zoom"
    pet["vfx"] = norm_vfx(d["vfx"], d)
    return pet


def baby_dragon():
    d = load("baby-dragon")
    L = d["locomotion_data"]
    H = L["hover_height_studs"]
    F = L["frames"]
    wb = L["wingbeat"]
    pet, r = base("baby-dragon", "Baby Dragon", "Fire", d, hover=H, locomotion=d["locomotion"],
                  cycle=wb["period_s"], stride=8.0)

    def fj(spec):
        return ({p: v["rot_deg_studio_xyz"] for p, v in spec.items()},
                {p: v["offset_studs_studio_xyz"] for p, v in spec.items()})

    def fr(name, spec, **kw):
        j, o = fj(spec)
        return dict(j=j, o=o, name=name, **kw)
    move = clip(r, [fr(n, F[n]) for n in wb["loop"]], wb["period_s"], True)
    sw = F["tail_swish"]["BabyDragon_Tail"]["rot_deg_studio_xyz"][1]
    idle = synth_bob_idle(r, 0.08, 2, 2.0, tail="BabyDragon_Tail", tail_amp=sw / 2)
    fb = F["fire_breath"]
    # fire breath: ease in 0.12 s, hold 0.6 s, ease out 0.2 s (kit's note)
    action = clip(r, [fr("hover_mid", F["hover_mid"], at=0.0), fr("fire_breath", fb, at=0.12),
                      fr("fire_breath_hold", fb, at=0.72), fr("hover_mid", F["hover_mid"], at=0.92)],
                  0.92, False)

    def pose(spec, dur):
        j, o = fj(spec)
        return pose_clip(r, j, dur, offsets=o)
    wd = L["landing_waddle_extra"]
    # root offset Y becomes lift, measured from the GROUND here (grounded = true)
    waddle = clip(r, [fr(k, wd["frames"][k]) for k in wd["loop"]], wd["step_period_s"], True, grounded=True)
    pet["parts"] = part_table(d, {n: [255, 150, 46] for n in d["parts"] if "_Glow" in n})
    pet["clips"] = {"move": move, "idle": idle, "action": action,
                    "glide": pose(F["glide"], 0.3), "tail_swish": pose(F["tail_swish"], 0.4),
                    "head_turn": pose(F["head_turn"], 0.4), "waddle": waddle}
    pet["actionName"] = "fire_breath"
    pet["vfx"] = norm_vfx(d["vfx"], d)
    return pet


PETS = [
    ("GoldenRetriever", golden_retriever), ("Bunny", bunny), ("Frog", frog), ("Penguin", penguin),
    ("Fox", fox), ("Bee", bee), ("Turtle", turtle), ("Monkey", monkey), ("LuckyCat", lucky_cat),
    ("Owl", owl), ("CheetahCub", cheetah), ("BabyDragon", baby_dragon),
]

# --------------------------------------------------------------------------- Luau writer
KEYWORDS = {"and", "break", "do", "else", "elseif", "end", "false", "for", "function", "if", "in", "local",
            "nil", "not", "or", "repeat", "return", "then", "true", "until", "while", "continue"}
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def num(x):
    x = round(float(x), 3)
    if x == 0:
        return "0"
    if x == int(x):
        return str(int(x))
    return ("%.3f" % x).rstrip("0").rstrip(".")


def key(k):
    if isinstance(k, str) and IDENT.match(k) and k not in KEYWORDS:
        return k
    return "[%s]" % json.dumps(str(k), ensure_ascii=False)


def inline(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "nil"
    if isinstance(v, (int, float)):
        return num(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        return "{" + ", ".join(inline(x) for x in v) + "}"
    if isinstance(v, dict):
        if not v:
            return "{}"
        return "{" + ", ".join("%s = %s" % (key(k), inline(x)) for k, x in v.items() if x is not None) + "}"
    raise TypeError(type(v))


def emit(v, ind=0, width=118):
    s = inline(v)
    if len(s) + ind * 4 <= width or not isinstance(v, (dict, list)):
        return s
    pad = "\t" * (ind + 1)
    end = "\t" * ind
    if isinstance(v, dict):
        lines = ["%s%s = %s," % (pad, key(k), emit(x, ind + 1)) for k, x in v.items() if x is not None]
    else:
        lines = ["%s%s," % (pad, emit(x, ind + 1)) for x in v]
    return "{\n" + "\n".join(lines) + "\n" + end + "}"


HEADER = """--!nonstrict
-- PetRigs: pure data for the 12 pets (no requires). Generated by tools/build_pet_rigs.py from
-- roguelite-planning/blender-pet-kit/<kit>/studio-install-data.json. Do not hand-edit; re-run the script.
--
-- AXES / UNITS. Everything is in STUDIO axes and studs (Blender (x, y, z) -> Studio (-x, z, y)).
--   The pet faces Studio -Z; its own LEFT is Studio -X. Meshes are at final size (import 1:1).
--   A rotation about Blender X is a rotation about Studio -X; Blender Z -> Studio Y; Blender Y -> Studio Z.
--   Rotation sign is the right-hand rule (CFrame.Angles): +rx on a hanging leg swings it FORWARD (-Z),
--   +rx on a head looks UP, +pitch on the root tips the nose UP (-pitch = nose down).
--
-- PER PET
--   kit, name, rarity, suit   display data (suit = strong-suit keyword from RARITY_GODLY_ARMOR.md section 11)
--   root          exact MeshPart name of the body/root part (all part names are the exact FBX/GLB mesh names)
--   size          overall size in studs at rest
--   hover         studs above ground the pet floats at (Bee 1.2, Owl 1.5, BabyDragon 1.5, others 0).
--                 All pivots/centers are the AT-REST model standing on y = 0 (ground point = origin);
--                 add `hover` to the Y of everything at runtime for flyers.
--   locomotion    the kit's gait name; cycle = seconds per loop of clips.move; stride = studs travelled per cycle
--   parts[name]   pivot (joint pivot), center (mesh bounding-box centre), size, parent (joint parent part name,
--                 nil for the root), glow (true for Neon `_Glow` parts), neon (r,g,b 0-255, glow parts only)
--   clips[name]   { loop, duration (s), synth?, hold?, additive?, grounded?, frames = {...} }
--     frame       { name?, t (0-1 along the clip; a looping clip wraps from the last frame back to the first),
--                   joints = { [PartName] = {rx, ry, rz} }  degrees about the part's own pivot, relative to rest,
--                                                           applied as CFrame.Angles(rad(rx), rad(ry), rad(rz));
--                                                           a part absent from `joints` is at rest (0, 0, 0)
--                   offsets? = { [PartName] = {x, y, z} }   studs, translation in the parent's frame (Motor6D C0)
--                   lift = studs +Y of the ROOT, pitch = deg about X of the ROOT, roll = deg about Z of the ROOT,
--                   yaw? = deg about Y of the ROOT }         (the root part is never listed in joints/offsets)
--                 Interpolate between frames (sine / cubic ease). For hover pets `lift` is RELATIVE to `hover`,
--                 except in clips with grounded = true (perched / landed): there lift is from the ground.
--     synth = true    the kit supplied no frames for this clip; it was synthesised by the script
--     hold = true     pose clip: blend rest -> pose over `duration`, then hold until released
--     additive = true flyer idle bob: play it ON TOP of clips.move (it carries lift / pitch / tail only)
--   Standard clips: move (locomotion / wingbeat), idle, action (the pet's ability pose); extra named clips
--   (glide, head_turn, tail_swish, waddle, perch_hop_turn, ...) use the same format.
--   actionName    the kit's name for the action pose
--   vfx           the kit's vfx entries copied verbatim, plus Studio-axis offsets from the named part's pivot:
--                 offset = {x,y,z} (one attachment), offsets = {...} (several), offset0 / offset1 (trail ends).
--                 `colour_rgb` / `color` are 0-255. `suggested` holds the particle / trail property values.
"""


def main():
    pets = {pid: fn() for pid, fn in PETS}
    # ------------------------------------------------------------------ validation
    for pid, p in pets.items():
        parts = p["parts"]
        roots = [n for n, e in parts.items() if e["parent"] is None]
        assert roots == [p["root"]], (pid, roots)
        for n, e in parts.items():
            assert len(e["pivot"]) == 3 and len(e["center"]) == 3 and len(e["size"]) == 3, (pid, n)
            if e["parent"] is not None:
                assert e["parent"] in parts, (pid, n, e["parent"])
        for cn, c in p["clips"].items():
            for f in c["frames"]:
                for pn in list(f["joints"]) + list(f.get("offsets", {})):
                    assert pn in parts, (pid, cn, pn)
                    assert pn != p["root"], (pid, cn, "root in joints")
                assert 0 <= f["t"] <= 1, (pid, cn, f)
        for need in ("move", "idle", "action"):
            assert need in p["clips"], (pid, need)
    out = [HEADER, "\nreturn {\n"]
    for pid, p in pets.items():
        out.append("\t%s = %s,\n" % (pid, emit(p, 1)))
    out.append("}\n")
    text = "".join(out)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", OUT, len(text), "bytes;", len(pets), "pets;", len(WARN), "warnings")


if __name__ == "__main__":
    main()
