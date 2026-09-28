"""Particle / beam textures for the chest auras and the chest-opening burst (ChestFX.luau).

All white on transparent so Roblox tints them with ParticleEmitter.Color / Beam.Color. Soft,
broad shapes to match the stylized art direction (no noisy or photoreal detail).

  python make_chest_vfx.py        -> *.png next to this script (then upload; ids in asset-ids.json)
"""
from pathlib import Path
import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent
rng = np.random.default_rng(7)


def save(name, alpha, rgb=None):
    a = np.clip(alpha, 0, 1)
    h, w = a.shape
    img = np.zeros((h, w, 4), np.uint8)
    img[..., :3] = 255 if rgb is None else (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    img[..., 3] = (a * 255).astype(np.uint8)
    Image.fromarray(img, "RGBA").save(OUT / f"{name}.png")


def grid(n):
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    c = (n - 1) / 2
    return (x - c) / c, (y - c) / c


def smooth_noise(n, cells, octaves=3):
    """Tileable-enough value noise, broad patches."""
    out = np.zeros((n, n), np.float32)
    amp = 1.0
    for o in range(octaves):
        k = cells * 2 ** o
        g = rng.random((k + 1, k + 1)).astype(np.float32)
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((n, n), Image.BICUBIC)
        out += amp * np.asarray(img, np.float32) / 255
        amp *= 0.5
    return out / out.max()


# 1. glow: soft radial falloff with a slightly brighter core.
x, y = grid(256)
r = np.sqrt(x * x + y * y)
save("glow", np.exp(-(r * 2.2) ** 2) * 0.85 + np.exp(-(r * 6) ** 2) * 0.35)

# 2. star: four-point sparkle, long vertical/horizontal spikes, short diagonals, glowing core.
x, y = grid(256)
r = np.sqrt(x * x + y * y)
spike = lambda u, v, width, length: np.exp(-(u / width) ** 2) * np.clip(1 - np.abs(v) / length, 0, 1) ** 2.2
star = spike(x, y, 0.035, 1.0) + spike(y, x, 0.035, 1.0)
d1, d2 = (x + y) / np.sqrt(2), (x - y) / np.sqrt(2)
star += 0.45 * (spike(d1, d2, 0.03, 0.45) + spike(d2, d1, 0.03, 0.45))
star += np.exp(-(r * 7) ** 2) + 0.35 * np.exp(-(r * 2.6) ** 2)
save("star", star)

# 3. streak: thin vertical light streak (particles use VelocityParallel orientation).
x, y = grid(256)
streak = np.exp(-(x / 0.13) ** 2) * np.clip(1 - np.abs(y), 0, 1) ** 1.4
streak += 0.6 * np.exp(-(x / 0.05) ** 2) * np.clip(1 - np.abs(y) * 1.2, 0, 1) ** 2
save("streak", streak)

# 4. wisp: soft flame tongue with broad painterly breakup (aura rising off the chest).
n = 256
x, y = grid(n)
noise = smooth_noise(n, 3)
# teardrop: wide at the bottom, pointed at the top (y=-1 is the image top)
yy = (y + 1) / 2  # 0 top .. 1 bottom
width = 0.18 + 0.5 * yy ** 0.8
shape = np.exp(-(x / width) ** 2 * 1.6) * np.clip(yy * 1.6, 0, 1) * np.clip((1 - yy) * 4, 0, 1)
wisp = shape * (0.55 + 0.6 * noise)
save("wisp", wisp / wisp.max())

# 5. ring: shockwave ring with a bright inner edge and a soft outer fade.
x, y = grid(512)
r = np.sqrt(x * x + y * y)
ring = np.exp(-((r - 0.8) / 0.06) ** 2) + 0.5 * np.exp(-((r - 0.72) / 0.14) ** 2) * (r < 0.8)
save("ring", ring / ring.max())

# 6. rays: radial god rays with uneven widths, fading outwards (world burst billboards).
x, y = grid(512)
r = np.sqrt(x * x + y * y) + 1e-6
ang = np.arctan2(y, x)
rays = np.zeros_like(r)
for k in range(16):
    a0 = k / 16 * 2 * np.pi + rng.uniform(-0.12, 0.12)
    wdt = rng.uniform(0.05, 0.13)
    da = np.angle(np.exp(1j * (ang - a0)))
    rays += np.exp(-(da / wdt) ** 2) * rng.uniform(0.6, 1.0)
rays = np.clip(rays, 0, 1) * np.clip(1 - r, 0, 1) ** 1.3 * np.clip(r * 5, 0, 1)
rays += np.exp(-(r * 4) ** 2) * 0.8
save("rays", rays)

# 7. shaft: light shaft for Beams. Beam textures run along X (length), so this is 256 long x 64
#    across: bright core, soft edges, fading towards the far end.
u = np.linspace(0, 1, 256)[None, :]
v = np.linspace(-1, 1, 64)[:, None]
shaft = (np.exp(-(v / 0.45) ** 2) * 0.7 + np.exp(-(v / 0.14) ** 2) * 0.5) * (1 - u) ** 1.2 * np.clip(u * 12, 0, 1)
save("shaft", shaft / shaft.max())

# 8. mote: tiny soft dot with a hot core (dust and magic motes).
x, y = grid(64)
r = np.sqrt(x * x + y * y)
save("mote", np.exp(-(r * 2.4) ** 2) + np.exp(-(r * 7) ** 2))

print("wrote", sorted(p.name for p in OUT.glob("*.png")))
