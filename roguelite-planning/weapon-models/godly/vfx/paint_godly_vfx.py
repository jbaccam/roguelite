"""Paints the Godly weapon VFX textures (white on transparent, so ParticleEmitter/Beam Color tints
them). Run: python paint_godly_vfx.py  ->  textures/*.png

GodlySoftGlow   round soft glow for auras, motes and wisps
GodlySlash      crescent slash streak for claw and dagger hits
GodlyLightning  jagged bolt strip that tiles left-right, for Beams (storm arrows, sparks)
GodlyWisp       teardrop soul flame, tip up
GodlySkull      little skull mote (Reaper's Scythe)
GodlyPixel      soft-edged square for the Ray Gun's disintegration
Reused from BossVfxAssets: ShockwaveRing, ImpactStar, WaterSplash/SmokePuff flipbooks, Bubble, Ember.
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent / "textures"
OUT.mkdir(exist_ok=True)
N = 512


def save(name, alpha, rgb=1.0):
    alpha = np.clip(alpha, 0, 1)
    img = np.zeros((alpha.shape[0], alpha.shape[1], 4), np.uint8)
    img[..., :3] = np.uint8(np.clip(rgb, 0, 1) * 255)[..., None] if np.ndim(rgb) else int(rgb * 255)
    img[..., 3] = np.uint8(alpha * 255)
    Image.fromarray(img, "RGBA").save(OUT / f"{name}.png")


yy, xx = np.mgrid[0:N, 0:N] / (N - 1) * 2 - 1
r = np.hypot(xx, yy)

# Soft glow: hot centre, long falloff.
save("GodlySoftGlow", np.clip(1 - r, 0, 1) ** 2.2)

# Slash: a crescent between two offset circles, brightest on the outer edge, tapered ends.
outer = np.hypot(xx, yy + 0.2)
inner = np.hypot(xx * 1.1, yy + 0.75)
band = np.clip((0.95 - outer) * 10, 0, 1) * np.clip((inner - 0.82) * 6, 0, 1)
taper = np.clip(1 - np.abs(xx) / 0.97, 0, 1) ** 0.6
edge = np.clip(1 - np.abs(outer - 0.88) * 7, 0, 1)
save("GodlySlash", np.clip(band * taper * (0.75 + 0.6 * edge), 0, 1), rgb=0.8 + 0.2 * edge)

# Lightning: a jagged bolt across a 512x128 strip that wraps left-right, with a soft halo.
W, H = 512, 128
rng = np.random.default_rng(7)
canvas = Image.new("L", (W, H), 0)
draw = ImageDraw.Draw(canvas)
xs = np.linspace(0, W, 15)
ys = H / 2 + rng.uniform(-H * 0.3, H * 0.3, len(xs))
ys[0] = ys[-1] = H / 2
pts = list(zip(xs, ys))
draw.line(pts, fill=255, width=14, joint="curve")
for i in (3, 8, 11):  # forks
    fx, fy = pts[i]
    draw.line([(fx, fy), (fx + 34, fy + rng.uniform(-30, 30)), (fx + 60, fy + rng.uniform(-40, 40))], fill=220, width=6)
halo = canvas.filter(ImageFilter.GaussianBlur(14))
core = np.asarray(canvas, np.float32) / 255
glow = np.asarray(halo, np.float32) / 255
save("GodlyLightning", np.clip(core + glow * 2.4, 0, 1), rgb=np.clip(0.75 + core * 0.25, 0, 1))

# Wisp: a teardrop flame, tip up, soft edges.
u, v = xx, (yy + 1) / 2  # v: 0 top .. 1 bottom
width = np.clip(np.sin(np.clip(v, 0, 1) * np.pi * 0.92) ** 0.6 * (0.25 + 0.55 * v), 0.001, None)
body = np.clip(1 - np.abs(u) / width, 0, 1) * np.clip((1 - v) * 6, 0, 1) * np.clip(v * 3, 0, 1)
save("GodlyWisp", body ** 1.3, rgb=0.8 + 0.2 * body)

# Skull: round cranium + jaw, eye and nose holes cut out, softened.
skull = Image.new("L", (N, N), 0)
d = ImageDraw.Draw(skull)
d.ellipse([96, 60, 416, 360], fill=255)
d.rounded_rectangle([160, 300, 352, 430], 40, fill=255)
for x0 in (150, 278):
    d.ellipse([x0, 170, x0 + 86, 266], fill=0)
d.polygon([(256, 280), (232, 330), (280, 330)], fill=0)
for x in range(186, 340, 38):
    d.rectangle([x, 372, x + 10, 430], fill=0)
skull = skull.filter(ImageFilter.GaussianBlur(3))
save("GodlySkull", np.asarray(skull, np.float32) / 255)

# Pixel: a square with a soft rim and a brighter core.
sq = np.maximum(np.abs(xx), np.abs(yy))
save("GodlyPixel", np.clip((0.82 - sq) * 8, 0, 1), rgb=np.clip(0.75 + (0.6 - sq) * 0.5, 0, 1))
print("painted", sorted(p.name for p in OUT.glob("*.png")))
