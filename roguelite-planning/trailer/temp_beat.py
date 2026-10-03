"""Temp music for the trailer cut: a 128 BPM beat synthesised from scratch (no samples, no
licensed audio), with hits placed on the shot list's cuts. It exists so the edit can be timed
and judged with sound; swap in a licensed track (same BPM) before posting anywhere.

    python temp_beat.py            -> build/temp_beat.wav, length from shots.json
"""
import json
import math
import os
import wave

import numpy as np

SR = 48000
ROOT = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(128)


def one_pole_lp(x, cutoff):
    """Simple low-pass; cutoff may be a number or an array (a sweep)."""
    y = np.empty_like(x)
    c = np.broadcast_to(np.asarray(cutoff, dtype=np.float64), x.shape)
    a = 1 - np.exp(-2 * np.pi * c / SR)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def hp(x, cutoff):
    return x - one_pole_lp(x, cutoff)


def env_exp(n, rate):
    return np.exp(-np.arange(n) / SR * rate)


def kick():
    n = int(SR * 0.45)
    t = np.arange(n) / SR
    f = 46 + 130 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * env_exp(n, 6.5)
    click = hp(rng.standard_normal(n), 3000) * env_exp(n, 400) * 0.35
    return np.tanh((body + click) * 1.6) * 0.95


def clap():
    n = int(SR * 0.32)
    noise = rng.standard_normal(n)
    band = hp(one_pole_lp(noise, 2600), 900)
    e = np.zeros(n)
    for k, d in enumerate((0.0, 0.011, 0.022)):
        s = int(d * SR)
        e[s:] += env_exp(n - s, 220 if k < 2 else 16)
    return band * e * 0.55


def hat(open_=False):
    n = int(SR * (0.32 if open_ else 0.06))
    x = hp(rng.standard_normal(n), 7000) * env_exp(n, 9 if open_ else 70)
    return x * (0.22 if open_ else 0.16)


def saw(freq, n, detune=0.0):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for d in ((-detune, 0, detune) if detune else (0,)):
        out += 2 * ((t * freq * (1 + d)) % 1.0) - 1
    return out / (3 if detune else 1)


def bass_note(freq, length):
    n = int(SR * length)
    x = saw(freq, n) + 0.6 * np.sin(2 * np.pi * freq * np.arange(n) / SR)
    x = one_pole_lp(x, 380)
    a = np.minimum(1, np.arange(n) / (SR * 0.006))
    return np.tanh(x * a * env_exp(n, 7) * 2.2) * 0.42


def pluck(freq, length=0.16):
    n = int(SR * length)
    t = np.arange(n) / SR
    x = np.sign(np.sin(2 * np.pi * freq * t)) * 0.5 + saw(freq * 2, n) * 0.25
    x = one_pole_lp(x, 2400 * env_exp(n, 14) + 300)
    return x * env_exp(n, 16) * 0.16


def pad(freqs, length):
    n = int(SR * length)
    x = sum(saw(f, n, detune=0.004) for f in freqs) / len(freqs)
    x = one_pole_lp(x, 1400)
    a = np.minimum(1, np.arange(n) / (SR * 0.35))
    return x * a * np.minimum(1, (n - np.arange(n)) / (SR * 0.8)) * 0.22


def impact():
    n = int(SR * 2.2)
    t = np.arange(n) / SR
    f = 34 + 60 * np.exp(-t * 9)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 2.2)
    crash = one_pole_lp(rng.standard_normal(n), 5000) * env_exp(n, 3.2) * 0.45
    return np.tanh((boom * 1.4 + crash) * 1.3) * 0.9


def riser(length):
    n = int(SR * length)
    t = np.arange(n) / SR
    k = t / length
    noise = one_pole_lp(rng.standard_normal(n), 300 + 9000 * k ** 2)
    tone = np.sin(2 * np.pi * np.cumsum(180 + 1100 * k ** 2) / SR) * 0.25
    return (noise * 0.5 + tone) * k ** 1.6 * 0.5


def whoosh(length=0.42):
    n = int(SR * length)
    k = np.arange(n) / n
    bell = np.sin(np.pi * k) ** 2
    x = one_pole_lp(rng.standard_normal(n), 400 + 5000 * np.sin(np.pi * k))
    return x * bell * 0.5


def add(buf, snd, at, gain=1.0):
    s = int(at * SR)
    if s >= len(buf):
        return
    e = min(len(buf), s + len(snd))
    buf[s:e] += snd[: e - s] * gain


def build(shots_path=os.path.join(ROOT, "shots.json"), out=os.path.join(ROOT, "build", "temp_beat.wav")):
    cfg = json.load(open(shots_path))
    beat = 60.0 / cfg["bpm"]
    starts, b = [], 0.0
    for s in cfg["shots"]:
        starts.append((b, s))
        b += s["beats"]
    total_beats = b
    length = total_beats * beat + cfg.get("tail", 1.5)  # same length as the video
    buf = np.zeros(int(SR * length))

    K, C, H, O = kick(), clap(), hat(), hat(True)
    title_beat = next(bt for bt, s in starts if s["kind"] == "title")
    end_beat = next(bt for bt, s in starts if s["kind"] == "end")
    roots = [55.0, 43.65, 65.41, 49.0]  # A1 F1 C2 G1: Am - F - C - G
    chords = [[220, 261.63, 329.63], [174.61, 220, 261.63], [261.63, 329.63, 392], [196, 246.94, 293.66]]

    # Intro: sparse kicks that tighten, a snare roll and a riser into the title hit.
    for i in range(int(title_beat)):
        if i < title_beat - 8:
            if i % 2 == 0:
                add(buf, K, i * beat, 0.9)
        else:
            add(buf, K, i * beat, 0.95)
        if i % 4 == 0:
            add(buf, bass_note(roots[0], beat * 3.5), i * beat, 0.7)
    for j in range(16):  # 16th roll over the last bar before the title
        t = (title_beat - 4) * beat + j * beat / 4
        add(buf, C, t, 0.25 + 0.6 * j / 16)
    add(buf, riser(beat * 8), (title_beat - 8) * beat, 0.9)

    # Main groove from the title to the end card.
    for i in range(int(title_beat), int(end_beat)):
        t = i * beat
        bar = int((i - title_beat) // 4) % 4
        add(buf, K, t)
        if i % 2 == 1:
            add(buf, C, t, 0.9)
        add(buf, O, t + beat / 2, 0.8)
        for q in range(4):
            add(buf, H, t + q * beat / 4, 0.7 if q % 2 else 0.45)
        add(buf, bass_note(roots[bar], beat * 0.45), t + beat / 2)
        ch = chords[bar]
        for q in range(2):
            add(buf, pluck(ch[(i * 2 + q) % 3] * 2), t + q * beat / 2)

    # End card: hit, a held chord, then silence to the tail.
    add(buf, pad([110, 220, 261.63, 329.63], beat * 5), end_beat * beat, 1.0)
    add(buf, K, end_beat * beat)

    # Hits and swooshes on the cuts.
    for bt, s in starts:
        tr = s.get("transition", "cut")
        t = bt * beat
        if tr == "impact" or s["kind"] in ("title", "end"):
            add(buf, impact(), t, 0.85)
        elif tr == "whip":
            add(buf, whoosh(), max(0, t - 0.22), 0.9)
        elif tr in ("punch", "flash"):
            add(buf, whoosh(0.25), max(0, t - 0.12), 0.45)

    # Master: gentle glue, soft clip, normalise, stereo with a little width on the hats/plucks.
    buf = np.tanh(buf * 1.1)
    buf /= max(1e-6, np.max(np.abs(buf))) / 0.89
    fade = int(SR * 0.9)
    buf[-fade:] *= np.linspace(1, 0, fade)
    left = buf
    right = np.roll(buf, int(SR * 0.0006))
    st = np.stack([left, right], axis=1)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())
    return out, length


if __name__ == "__main__":
    path, length = build()
    print(f"wrote {path} ({length:.1f} s)")
