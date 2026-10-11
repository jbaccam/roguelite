"""Paints the Molotov fire-pool ground decal (2026-10-10 rework). Run: python paint_molotov_vfx.py
-> textures/MolotovFirePool.png

MolotovFirePool  top-down painted puddle of fire: rim red, flame orange, flame yellow and a pale hot
                 core, each band a ring of pointed flame tongues. Coloured (not white-on-clear): the
                 colours are the boss kit's Flame_Flipbook4x4 bands, measured from its pixels.
                 The red tips reach the image edge, so a Decal on a part 2r wide shows the hit edge.
Reused, already uploaded (BossVfxAssets): Flame_Flipbook4x4 (the tongues), ScorchMark, Ember.
Design: https://claude.ai/artifact/NBgiUUT7Ee3gDMfwWhMEA8 (top-down panel). Seeded: same PNG each run.
"""
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent / "textures"
OUT.mkdir(exist_ok=True)
N = 512
SS = 2  # supersample for clean band edges

# Flame flipbook bands (boss-vfx-kit/textures/Flame_Flipbook4x4.png): rim red, orange, yellow, core.
# (colour, outer radius, tongue depth, tongue count, seed). Fewer, shallower tongues inward.
BANDS = [
    ((211, 58, 34), 0.98, 0.20, 11, 1),
    ((247, 128, 31), 0.80, 0.15, 9, 2),
    ((255, 201, 63), 0.58, 0.13, 7, 3),
    ((255, 232, 160), 0.33, 0.12, 5, 4),
]
SWIRL = 0.9  # tongues lean round the pool like licking flames instead of a sunburst


def band_radius(theta, r, outer, depth, lobes, seed):
    """Radius of one band at angle theta: rounded flame licks that lean with the swirl, an uneven
    puddle outline and per-tongue height variation, so it reads hand-painted rather than stamped."""
    rnd = np.random.default_rng(seed)
    heights = rnd.uniform(0.55, 1.0, lobes)
    p1, p2 = rnd.uniform(0, 2 * np.pi, 2)
    shifted = theta - SWIRL * r + seed * 0.4
    lobe = np.floor(shifted * lobes / (2 * np.pi) + 0.5).astype(int) % lobes
    tip = ((np.cos(lobes * shifted) + 1) / 2) ** 2
    blob = 1 + 0.05 * np.sin(2 * theta + p1) + 0.035 * np.sin(3 * theta + p2)
    return outer * blob * (1 - depth + depth * tip * heights[lobe])


def paint_pool():
    size = N * SS
    yy, xx = np.mgrid[0:size, 0:size] / (size - 1) * 2 - 1
    r = np.hypot(xx, yy)
    theta = np.arctan2(yy, xx)
    rgb = np.zeros((size, size, 3), np.float32)
    alpha = np.zeros((size, size), np.float32)
    previous = None
    for color, outer, depth, lobes, seed in BANDS:
        edge = band_radius(theta, r, outer, depth, lobes, seed)
        if previous is not None:
            edge = np.minimum(edge, previous - 0.05)  # each band stays inside the one around it
        previous = edge
        inside = r <= edge
        rgb[inside] = np.array(color, np.float32) / 255
        alpha[inside] = 1
    # Broad, low-noise painterly patches: +-6% value in big soft blobs (2-4 value ranges, no grit).
    rnd = np.random.default_rng(11)
    patches = np.zeros((size, size), np.float32)
    for _ in range(18):
        cx, cy = rnd.uniform(-0.8, 0.8, 2)
        s = rnd.uniform(0.18, 0.35)
        patches += rnd.uniform(-1, 1) * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * s * s))
    patches = patches / max(1e-6, np.abs(patches).max())
    rgb *= (1 + 0.06 * patches)[..., None]
    # A thin darker lip on the outer rim so the hit edge reads against light ground.
    rim = band_radius(theta, r, *BANDS[0][1:])
    lip = np.clip(1 - (rim - r) / 0.025, 0, 1) * (r <= rim)
    rgb *= (1 - 0.28 * lip)[..., None]
    img = np.concatenate([np.clip(rgb, 0, 1), alpha[..., None]], axis=-1)
    img = img.reshape(N, SS, N, SS, 4).mean(axis=(1, 3))  # downsample = antialiased edges
    # Outside pixels are black, so the averaged colour is premultiplied; divide alpha back out
    # (otherwise the antialiased rim goes dark).
    a = img[..., 3:4]
    img[..., :3] = np.where(a > 0, img[..., :3] / np.maximum(a, 1e-6), 0)
    Image.fromarray(np.uint8(np.clip(img, 0, 1) * 255), "RGBA").save(OUT / "MolotovFirePool.png")


if __name__ == "__main__":
    paint_pool()
    print("wrote", OUT / "MolotovFirePool.png")
