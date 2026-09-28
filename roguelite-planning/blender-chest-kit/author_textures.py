"""Paint the chest colour atlas for one tier.

    python author_textures.py            # every tier in tiers/
    python author_textures.py wooden     # one tier

System Python with numpy + Pillow (not Blender). Writes textures/chest-<tier>.png.

Art brief (../art-references/ART_DIRECTION_USER_2026-09-17.txt): painterly, soft,
low-noise, "2-4 main value ranges", broad colour patches, subtle grunge, no
micro-scratches. Wood is warm brown, metal charcoal/grey. The geometry makes the
shape; this sheet only adds tonal breakup.

Colours come from tiers/<tier>.py (PALETTE).

Atlas layout (UV space, v up), shared with generate_chest.py:

    u 0.00-0.75  wood: 16 horizontal plank bands, 1/16 of v each
    u 0.75-1.00  v 0.375-1.00  metal: broad painterly plate
    u 0.75-1.00  v 0.00-0.375  six swatches: rivet, keyhole (dark), gem, swatch4-6
"""
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
TEX = ROOT / "textures"
TEX.mkdir(exist_ok=True)

SIZE = 2048
BANDS = 16
WOOD_U = 0.75
METAL_V = 0.375

TIERS = ROOT / "tiers"


def load_tier(tier):
    """tiers/<tier>.py holds the tier's PALETTE (plain Python, no bpy)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"chest_tier_{tier}", TIERS / f"{tier}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def smooth_noise(h, w, cells_y, cells_x, rng):
    """Low-frequency value noise: a coarse random grid upsampled bicubically."""
    grid = rng.random((cells_y + 3, cells_x + 3)).astype(np.float32)
    img = Image.fromarray((grid * 255).astype(np.uint8), "L")
    big = img.resize((int(w * (cells_x + 3) / cells_x), int(h * (cells_y + 3) / cells_y)), Image.BICUBIC)
    arr = np.asarray(big, dtype=np.float32) / 255.0
    oy = (arr.shape[0] - h) // 2
    ox = (arr.shape[1] - w) // 2
    return arr[oy:oy + h, ox:ox + w] - 0.5


def col(c):
    return np.array(c, dtype=np.float32) / 255.0


def lerp(a, b, t):
    return a + (b - a) * t[..., None]


def paint_wood(p, rng, w, h):
    band_h = h / BANDS
    rows = np.arange(h, dtype=np.float32)
    cols = np.arange(w, dtype=np.float32)
    band = np.floor(rows / band_h).astype(int)
    within = (rows - band * band_h) / band_h           # 0 at a plank's top edge, 1 at bottom

    base = np.empty((h, w, 3), np.float32)
    # Per-plank value and warmth only: shifting channels independently turns planks olive.
    value = rng.uniform(-0.08, 0.08, BANDS)
    warmth = rng.uniform(-0.05, 0.05, BANDS)
    for k in range(BANDS):
        base[band == k] = col(p["wood"]) * (1 + value[k]) * np.array([1 + warmth[k], 1, 1 - warmth[k]])

    # Broad painterly patches, then long soft grain streaks along each plank.
    patches = smooth_noise(h, w, 10, 7, rng) * 0.16 + smooth_noise(h, w, 22, 14, rng) * 0.06
    grain = smooth_noise(h, w, 90, 6, rng) * 0.10
    shade = 1 + patches + grain
    base *= shade[..., None]

    # Hand-painted plank shading: lit top edge, shadowed lower edge, dark gap.
    top = (np.clip(1 - within / 0.16, 0, 1) ** 1.5)[:, None]
    bottom = (np.clip((within - 0.62) / 0.38, 0, 1) ** 1.6)[:, None]
    base = lerp(base, col(p["wood_light"]), top * 0.45)
    base = lerp(base, col(p["wood_dark"]), bottom * 0.55)
    gap = (within > 0.955) | (within < 0.012)
    base[gap] = col(p["gap"])

    # A few staggered board joints so long planks do not read as one strip.
    for k in range(BANDS):
        for _ in range(rng.integers(0, 2)):
            x = int(rng.uniform(0.15, 0.85) * w)
            y0, y1 = int(k * band_h + 2), int((k + 1) * band_h - 3)
            base[y0:y1, x:x + 7] = col(p["gap"])
            base[y0:y1, x + 7:x + 12] = lerp(base[y0:y1, x + 7:x + 12], col(p["wood_light"]), np.full((y1 - y0, 5), 0.35))

    # Sparse painted grain strokes (the bat icon's darker dashes), not fine noise.
    for _ in range(90):
        k = rng.integers(0, BANDS)
        y = int((k + rng.uniform(0.2, 0.8)) * band_h)
        x0 = int(rng.uniform(0, 0.9) * w)
        ln = int(rng.uniform(60, 220))
        t = np.linspace(0, np.pi, ln)
        a = (np.sin(t) * 0.35)[None, :, None]
        seg = base[y:y + 3, x0:x0 + ln]
        base[y:y + 3, x0:x0 + ln] = seg + (col(p["wood_dark"]) - seg) * a[:, :seg.shape[1]]

    # Broad knots: soft dark ovals with one lighter ring, a handful per sheet.
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for _ in range(7):
        k = rng.integers(0, BANDS)
        cy = (k + rng.uniform(0.35, 0.6)) * band_h
        cx = rng.uniform(0.08, 0.92) * w
        rx, ry = rng.uniform(26, 44), rng.uniform(12, 18)
        d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
        ring = np.clip(1 - np.abs(d - 1.25) / 0.35, 0, 1) * 0.25
        core = np.clip(1 - d, 0, 1) ** 0.8 * 0.6
        base = lerp(base, col(p["wood_dark"]), np.maximum(core, ring))
    return np.clip(base, 0, 1)


def paint_metal(p, rng, w, h):
    base = np.broadcast_to(col(p["metal"]), (h, w, 3)).copy()
    # Rounded patches only: long streaks read as wood grain on the iron bands.
    broad = smooth_noise(h, w, 8, 3, rng) * 0.9 + smooth_noise(h, w, 20, 8, rng) * 0.3
    t = np.clip(broad, -0.5, 0.5)
    base = lerp(base, col(p["metal_light"]), np.clip(t, 0, None) * 0.7)
    base = lerp(base, col(p["metal_dark"]), np.clip(-t, 0, None) * 0.8)
    return np.clip(base, 0, 1)


SWATCHES = ("rivet", "keyhole", "gem", "swatch4", "swatch5", "swatch6")   # matches generate_chest.py


def paint_swatches(p, w, h):
    """Six flat colours; a tier leaves swatch4-6 out to reuse its gem colour."""
    out = np.zeros((h, w, 3), np.float32)
    for i, key in enumerate(SWATCHES):
        out[:, int(i * w / len(SWATCHES)):int((i + 1) * w / len(SWATCHES))] = col(p.get(key, p["gem"]))
    return out


def author(tier):
    """Paint textures/chest-<tier>.png. A tier may replace the primary surface or the metal
    block with its own painter (enamel panels, enchanted stone, lacquer...):
        paint_primary(np, rng, w, h, p, tools) -> float32 (h, w, 3) in 0-1
        paint_metal(np, rng, w, h, p, tools)   -> float32 (h, w, 3) in 0-1
    tools: smooth_noise, col, lerp, BANDS. Keep 16 horizontal bands in the primary
    painter if the tier's boards/panels use band_uv."""
    mod = load_tier(tier)
    p = mod.PALETTE
    rng = np.random.default_rng(zlib.crc32(tier.encode()))   # stable per tier
    tools = {"smooth_noise": smooth_noise, "col": col, "lerp": lerp, "BANDS": BANDS}
    img = np.zeros((SIZE, SIZE, 3), np.float32)
    wu = int(SIZE * WOOD_U)
    img[:, :wu] = mod.paint_primary(np, rng, wu, SIZE, p, tools) if hasattr(mod, "paint_primary") else paint_wood(p, rng, wu, SIZE)
    mv = int(SIZE * (1 - METAL_V))                  # image rows run top-down; v runs bottom-up
    img[:mv, wu:] = mod.paint_metal(np, rng, SIZE - wu, mv, p, tools) if hasattr(mod, "paint_metal") else paint_metal(p, rng, SIZE - wu, mv)
    img[mv:, wu:] = paint_swatches(p, SIZE - wu, SIZE - mv)
    out = TEX / f"chest-{tier}.png"
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(out)
    print("wrote", out)


if __name__ == "__main__":
    for t in (sys.argv[1:] or sorted(f.stem for f in TIERS.glob("*.py"))):
        author(t)
