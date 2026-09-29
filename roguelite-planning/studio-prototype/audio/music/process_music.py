"""Prepare the roguelite's music for Roblox upload.

source/regular/, source/boss/  the user's Pixabay tracks, unchanged (not kept in git: see .gitignore)
processed/<playlist>_<n>.ogg   ready to upload

Every track is measured and normalised to the same loudness (EBU R128, two-pass, linear gain so
nothing pumps), so one song is never suddenly louder than the last. Stereo Ogg Vorbis ~128 kbps.
Needs ffmpeg on PATH.  Run:  python process_music.py
"""
import json, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET_LUFS, TRUE_PEAK, RANGE = -16.0, -1.5, 11.0


def measure(path):
    """First loudnorm pass: returns the measured values ffmpeg prints as JSON."""
    af = f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK}:LRA={RANGE}:print_format=json"
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", af, "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err).group(0))


def render(path, out, m):
    af = (f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK}:LRA={RANGE}:linear=true"
          f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
          f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-af", af, "-ar", "44100", "-ac", "2",
                    "-c:a", "libvorbis", "-q:a", "4", out], check=True)


def run():
    """Tracks keep the slot they were first given (tracks.json); new files get the next free
    number, so adding a song never renumbers ones already uploaded. Done slots are skipped."""
    os.makedirs(os.path.join(HERE, "processed"), exist_ok=True)
    path = os.path.join(HERE, "tracks.json")
    listing = json.load(open(path)) if os.path.exists(path) else {}
    for playlist in ("regular", "boss"):
        folder = os.path.join(HERE, "source", playlist)
        known = {name: slot for slot, name in listing.items() if slot.startswith(playlist + "_")}
        used = [int(slot.split("_")[1]) for slot in known.values()]
        for name in sorted(os.listdir(folder)):
            slot = known.get(name)
            if not slot:
                used.append(max(used, default=0) + 1)
                slot = f"{playlist}_{used[-1]:02d}"
                listing[slot] = name
            out = os.path.join(HERE, "processed", slot + ".ogg")
            if os.path.exists(out):
                continue
            m = measure(os.path.join(folder, name))
            render(os.path.join(folder, name), out, m)
            print(f"{slot}  {name}  was {float(m['input_i']):.1f} LUFS")
    with open(path, "w") as fh:
        json.dump(dict(sorted(listing.items())), fh, indent=2)


if __name__ == "__main__":
    run()
