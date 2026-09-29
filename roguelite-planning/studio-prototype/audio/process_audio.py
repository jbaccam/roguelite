"""Prepare the roguelite's sound effects for Roblox upload.

source/     the user's picks, unchanged (see SLOTS for which file fills which slot)
processed/  <slot>.ogg, ready to upload

Every sound is trimmed so it starts instantly, cut short if it rings on too long, levelled
by category and limited to -1 dBFS. The wood crack is split into the two chest taps; its
style variants only go to the preview folder until CHEST_VARIANT names the chosen one.

Needs ffmpeg on PATH and numpy.  Run:  python process_audio.py [--preview DIR]
"""
import argparse, json, os, shutil, subprocess, tempfile, wave
import numpy as np

SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "source")
OUT = os.path.join(HERE, "processed")

# Category -> (loudness of the first 150 ms in dBFS RMS, longest allowed length in s,
# where the sound starts as a fraction of its peak). Hits start at -12 dB: several splats had a
# quiet 35-110 ms lead-in before the actual hit, which made them land late in game.
CATEGORY = {
    "swing": (-16, 0.6, 0.05), "hit": (-14, 0.5, 0.25), "shot": (-15, 1.0, 0.05),
    "mob": (-15, 0.55, 0.25), "ui": (-17, 1.5, 0.05), "reward": (-17, 4.0, 0.05),
    "player": (-15, 1.5, 0.05),
}

SLOTS = [
    # slot,            source file,                                        category
    ("swing_light",    "floraphonic-swing-whoosh-5-198498.mp3",            "swing"),
    ("swing_blade",    "floraphonic-swing-whoosh-weapon-1-189819.mp3",     "swing"),
    ("swing_pan",      "pan.mp3",                                          "swing"),
    ("swing_heavy",    "heavy swoosh 1.mp3",                               "swing"),
    ("swing_heaviest", "heavy swoosh 2.mp3",                               "swing"),
    ("swing_soft",     "quick soft swoosh.mp3",                            "swing"),
    ("hit_blunt",      "blunt attack.mp3",                                 "hit"),
    ("hit_thud",       "freesound_gamestudio-attack-match-1-394505.mp3",   "hit"),
    ("hit_punch",      "bodyShotOomph_C.ogg",                              "hit"),
    ("shot_pistol",    "pistol.mp3",                                       "shot"),
    ("shot_draco",     "draco.mp3",                                        "shot"),
    ("shot_shotgun",   "shotgun_shoot_B.ogg",                              "shot"),
    ("shot_rocket",    "rocket_shoot_B.ogg",                               "shot"),
    ("shot_magic_a",   "icegun_shoot_A.ogg",                               "shot"),
    ("shot_magic_b",   "icegun_shoot_B.ogg",                               "shot"),
    ("shot_magic_c",   "icegun_shoot_C.ogg",                               "shot"),
    ("zap",            "dragon-studio-electric-discharge-386160.mp3",      "shot"),
    ("shot_fart",      "apebble-fart-4-228244.mp3",                        "shot"),
    ("mob_zombie",     "zombies-slimes-spiders.mp3",                       "mob"),
    ("mob_crab",       "crabs-and-scorpions.mp3",                          "mob"),
    ("mob_skeleton",   "skeeltons.mp3",                                    "mob"),
    ("mob_ghost",      "ghost-mummies-shaman.mp3",                         "mob"),
    ("mob_goo",        "freesound_community-gooey-squish-14820.mp3",       "mob"),
    ("ui_click",       "ui click.ogg",                                     "ui"),
    ("ui_equip",       "equip.mp3",                                        "ui"),
    ("ui_error",       "soundshelfstudio-ui-error-pop-515668.mp3",         "ui"),
    ("ui_purchase",    "ingame-purchase.mp3",                              "ui"),
    ("ui_upgrade",     "upgrade.mp3",                                      "ui"),
    ("reward_gold",    "freesound_gamestudio-material-gold-394476.mp3",    "ui"),
    ("chest_opened",   "chest opened.mp3",                                 "reward"),
    ("player_damage",  "player damage.mp3",                                "player"),
    ("player_death",   "player death.mp3",                                 "player"),
]

# Wood crack: two cracks in one file (seconds in the source), one per chest tap.
CRACK_FILE = "freesound_community-wood-crack-1-105890.mp3"
CRACKS = {"chest_shake_1": (0.075, 0.95), "chest_shake_2": (1.025, 1.70)}
# Style variants: pitch (1 = unchanged, higher = smaller/snappier), bass boost, tail length.
CHEST_VARIANTS = {
    "clean":    dict(pitch=1.00, bass=0, tail=0.80),
    "cartoony": dict(pitch=1.25, bass=5, tail=0.30),
    "chunky":   dict(pitch=1.12, bass=8, tail=0.25),
    "tock":     dict(pitch=1.25, bass=5, tail=0.30, tock=True),  # cartoony + wood-block click on the hit
}
CHEST_VARIANT = "cartoony"  # the CHEST_VARIANTS key written as chest_shake_1/2.ogg (Gold chest only for now)

# Seamless loops for weapons that fire continuously. From the steady part of the source, take
# `length` seconds plus `crossfade`, and fade the extra tail into the head so the end runs
# straight back into the start. The file holds three copies; the game loops the middle one
# (Sound.LoopRegion = [length, 2*length]), so the loop point never touches the file's edges,
# where encoders add padding that clicks.
LOOPS = {
    # slot:         (source file,  start s, length s, crossfade s)
    "washer_loop": ("water.mp3", 0.10, 3.40, 0.40),
}


def ffmpeg(src, dst, filters=None, extra=()):
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", str(SR)]
    if filters:
        cmd += ["-af", filters]
    subprocess.run(cmd + list(extra) + [dst], check=True)


def load(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32768


def save(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def shape(x, max_len, start_at=0.05):
    """Start 4 ms before the sound first reaches start_at x peak; end at -50 dB or max_len, faded."""
    pk = np.abs(x).max()
    onset = int(np.argmax(np.abs(x) > pk * start_at))
    start = max(0, onset - int(0.004 * SR))
    natural_end = int(np.nonzero(np.abs(x) > pk * 0.003)[0][-1]) + 1
    end = min(natural_end, onset + int(max_len * SR))
    y = x[start:end].copy()
    # A sound that already died out only needs a tiny fade; a cut-short one needs a longer one.
    seconds = len(y) / SR
    fade = int(SR * (min(0.02, 0.25 * seconds) if end >= natural_end else min(0.15, 0.3 * seconds)))
    y[: int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    y[-fade:] *= np.linspace(1, 0, fade) ** 2
    return y


def level(y, target_db):
    head = y[: int(0.15 * SR)]
    return y * (10 ** (target_db / 20) / (np.sqrt((head ** 2).mean()) + 1e-9))


def finish(y, tmp, name, preview, ogg):
    raw = os.path.join(tmp, name + "_raw.wav")
    wav = os.path.join(tmp, name + ".wav")
    save(raw, y)
    ffmpeg(raw, wav, "alimiter=limit=0.89:attack=1:release=40:level=0:latency=1")
    if preview:
        shutil.copy(wav, os.path.join(preview, name + ".wav"))
    if ogg:
        ffmpeg(wav, os.path.join(OUT, name + ".ogg"), extra=["-c:a", "libvorbis", "-q:a", "6"])
    return wav


# Sound "sprites": one file holding several short variations, each in its own slot, so one upload
# covers them all; the game plays a slice with Sound.PlaybackRegion. Plops are found as bursts
# above -30 dB (ignoring blips under -15 dB), optionally dropping the last, sorted low to high
# pitch, levelled to match, and placed every `slot` seconds after a short lead-in.
SPRITES = {
    # slot:            (source file,    slot s, drop last burst)
    "crystal_pickup": ("pick up.mp3", 0.25, True),
}
SPRITE_LEAD = 0.05


def bursts(x):
    """(start, end) sample ranges of the separate sounds in a file."""
    step = int(0.005 * SR)
    env = np.array([np.abs(x[i:i + step]).max() for i in range(0, len(x) - step, step)])
    pk = env.max()
    on = env > pk * 10 ** (-30 / 20)
    found, i = [], 0
    while i < len(on):
        if not on[i]:
            i += 1
            continue
        j = i
        while j < len(on) and on[j:j + 3].any():  # bridge gaps under 15 ms
            j += 1
        if env[i:j].max() > pk * 10 ** (-15 / 20):
            found.append((i * step, j * step))
        i = j
    return found


def pitch(seg):
    X = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1 / SR)
    band = (f > 80) & (f < 4000)
    return f[band][np.argmax(X[band])]


def sprite(x, slot, drop_last):
    """Returns (audio, [(start s, end s, pitch Hz), ...]) with slots ordered low to high."""
    found = bursts(x)
    if drop_last:
        found = found[:-1]
    pieces = []
    for a, b in found:
        seg = x[max(0, a - int(0.004 * SR)): b + int(0.02 * SR)].copy()
        fade = int(0.015 * SR)
        seg[-fade:] *= np.linspace(1, 0, fade)
        head = seg[: int(0.04 * SR)]
        seg *= 0.1 / np.sqrt((head ** 2).mean())  # same loudness for every variation
        pieces.append((pitch(seg), seg))
    pieces.sort(key=lambda p: p[0])
    out = np.zeros(int((SPRITE_LEAD + slot * len(pieces)) * SR))
    regions = []
    for k, (hz, seg) in enumerate(pieces):
        start = SPRITE_LEAD + k * slot
        seg = seg[: int(slot * SR) - int(0.01 * SR)]
        i = int(start * SR)
        out[i: i + len(seg)] = seg
        regions.append((round(start, 4), round(start + len(seg) / SR, 4), round(float(hz))))
    return out * (0.89 / np.abs(out).max()), regions


def seamless(x, start, length, crossfade):
    """One loop body whose last sample runs straight into its first (equal-power crossfade)."""
    a, n, xf = int(start * SR), int(length * SR), int(crossfade * SR)
    seg = x[a: a + n + xf]
    body = seg[:n].copy()
    t = np.linspace(0, 1, xf, endpoint=False)
    body[:xf] = seg[:xf] * np.sin(t * np.pi / 2) + seg[n: n + xf] * np.cos(t * np.pi / 2)
    return body


def run(preview):
    os.makedirs(OUT, exist_ok=True)
    if preview:
        os.makedirs(preview, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for slot, src, cat in SLOTS:
            target, max_len, start_at = CATEGORY[cat]
            dec = os.path.join(tmp, slot + "_src.wav")
            ffmpeg(os.path.join(SRC, src), dec)
            finish(level(shape(load(dec), max_len, start_at), target), tmp, slot, preview, True)

        for slot, (src, start, length, crossfade) in LOOPS.items():
            dec = os.path.join(tmp, slot + "_src.wav")
            ffmpeg(os.path.join(SRC, src), dec)
            body = seamless(load(dec), start, length, crossfade)
            # Peak-normalise: spray spikes sit ~22 dB over the average, and clipping or a limiter
            # would crackle or pump. The in-game Volume sets the loudness instead.
            body *= 0.89 / np.abs(body).max()
            raw = os.path.join(tmp, slot + ".wav")
            save(raw, np.tile(body, 3))
            if preview:
                shutil.copy(raw, os.path.join(preview, slot + ".wav"))
            ffmpeg(raw, os.path.join(OUT, slot + ".ogg"), extra=["-c:a", "libvorbis", "-q:a", "6"])

        layout = {}
        for slot, (src, spacing, drop_last) in SPRITES.items():
            dec = os.path.join(tmp, slot + "_src.wav")
            ffmpeg(os.path.join(SRC, src), dec)
            audio, regions = sprite(load(dec), spacing, drop_last)
            raw = os.path.join(tmp, slot + ".wav")
            save(raw, audio)
            if preview:
                shutil.copy(raw, os.path.join(preview, slot + ".wav"))
            ffmpeg(raw, os.path.join(OUT, slot + ".ogg"), extra=["-c:a", "libvorbis", "-q:a", "6"])
            layout[slot] = regions
        with open(os.path.join(HERE, "sprites.json"), "w") as fh:
            json.dump(layout, fh, indent=1)

        # The click that the "tock" variant lays over each crack, pitched down to sound thicker.
        click = os.path.join(tmp, "tock.wav")
        ffmpeg(os.path.join(SRC, "ui click.ogg"), click, f"asetrate={SR}*0.8,aresample={SR}")
        tock = level(shape(load(click), 0.2), -20)

        whole = os.path.join(tmp, "crack.wav")
        ffmpeg(os.path.join(SRC, CRACK_FILE), whole)
        crack = load(whole)
        if preview:
            save(os.path.join(preview, "chest_crack_original.wav"), crack)
        for slot, (a, b) in CRACKS.items():
            seg = os.path.join(tmp, slot + "_seg.wav")
            save(seg, crack[int(a * SR): int(b * SR)])
            for name, v in CHEST_VARIANTS.items():
                styled = os.path.join(tmp, f"{slot}_{name}_styled.wav")
                filters = [f"asetrate={SR}*{v['pitch']},aresample={SR}"]
                if v["bass"]:
                    filters.append(f"bass=g={v['bass']}:f=150")
                ffmpeg(seg, styled, ",".join(filters))
                y = level(shape(load(styled), v["tail"]), -14)
                if v.get("tock"):
                    y[: len(tock)] += tock
                finish(y, tmp, f"{slot}_{name}", preview, CHEST_VARIANT == name)
                if CHEST_VARIANT == name:
                    os.replace(os.path.join(OUT, f"{slot}_{name}.ogg"), os.path.join(OUT, slot + ".ogg"))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--preview", help="also write WAVs here for the listening page")
    run(p.parse_args().preview)
    print("done:", len(os.listdir(OUT)), "files in processed/")
