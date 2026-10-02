"""Creator Hub images for the roguelite's developer products and game passes (2026-10-02).

Run: python make_product_images.py  ->  writes NN-key.png (512x512) next to this script.
Each image reuses the game's own icons (UI assets, the user's chest icons, weapon and armor
icons) on a coloured tile, with a count where the product has one. Names, descriptions and
prices for the Creator Hub form are in products.md (same order).
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
UI = HERE.parent  # ui/assets
PLAN = HERE.parents[3]  # roguelite-planning
SIZE = 512
FONT = "C:/Windows/Fonts/ariblk.ttf"

ART = {
    "revive": UI / "supplemental-v1/Revive.png",
    "reroll": UI / "hud/quest-scroll.png",
    "banish": UI / "hud/armory-anvil.png",
    "emerald": UI / "hud/emerald.png",
    "legendary": UI / "chests-pet-egg-2026-10-02-v1/chest-legendary.png",
    "gold": UI / "chests-pet-egg-2026-10-02-v1/chest-gold.png",
    "w00": UI / "weapons/00.png",
    "w12": UI / "weapons/12.png",
    "w19": UI / "weapons/19.png",
    "w24": UI / "weapons/24.png",
    "w36": UI / "weapons/36.png",
    "w39": UI / "weapons/39.png",
    "w40": UI / "weapons/40.png",
    "phoenix": PLAN / "blender-armor-kit/icons/Phoenix.Chest.png",
    "dragonscale": PLAN / "blender-armor-kit/icons/DragonScale.Chest.png",
}

# Tile colours (top, bottom), in the store's card families.
THEME = {
    "red": ((214, 72, 72), (96, 18, 30)),
    "blue": ((70, 150, 230), (20, 46, 110)),
    "purple": ((150, 96, 230), (52, 24, 110)),
    "green": ((96, 206, 96), (18, 92, 46)),
    "gold": ((246, 190, 70), (150, 74, 14)),
    "teal": ((60, 196, 186), (14, 84, 92)),
    "obsidian": ((90, 70, 120), (18, 12, 30)),
    "crimson": ((190, 40, 60), (40, 6, 18)),
    "shadow": ((110, 80, 170), (20, 10, 40)),
}


def art(key, size):
    im = Image.open(ART[key]).convert("RGBA")
    box = im.getbbox()  # trim transparent margins so every icon fills its slot the same way
    if box:
        im = im.crop(box)
    # Scale to fit `size` both ways (small 256 px HUD icons are scaled up too).
    r = size / max(im.width, im.height)
    return im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)


def paste(canvas, im, cx, cy, angle=0):
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    x, y = int(cx - im.width / 2), int(cy - im.height / 2)
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    shadow.putalpha(im.getchannel("A").point(lambda a: a * 0.55))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    canvas.alpha_composite(shadow, (x + 6, y + 12))
    canvas.alpha_composite(im, (x, y))


def tile(theme):
    top, bottom = THEME[theme]
    grad = Image.new("RGBA", (SIZE, SIZE))
    d = ImageDraw.Draw(grad)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        d.line([(0, y), (SIZE, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((86, 60, 426, 400), fill=(255, 255, 255, 70))
    grad.alpha_composite(glow.filter(ImageFilter.GaussianBlur(50)))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=72, fill=255)
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    ImageDraw.Draw(out).rounded_rectangle((6, 6, SIZE - 7, SIZE - 7), radius=66, outline=(255, 255, 255, 90), width=5)
    return out


def badge(canvas, text, size=92):
    d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, size)
    while d.textlength(text, font=font) > SIZE - 60 and size > 40:
        size -= 4
        font = ImageFont.truetype(FONT, size)
    w = d.textlength(text, font=font)
    d.text(((SIZE - w) / 2, SIZE - size - 44), text, font=font, fill=(255, 255, 255), stroke_width=9, stroke_fill=(20, 16, 24))


def single(theme, key, text=None, scale=330):
    c = tile(theme)
    paste(c, art(key, scale), SIZE / 2, SIZE / 2 - (34 if text else 0))
    if text:
        badge(c, text)
    return c


def pair(theme, main, extra, text=None):
    c = tile(theme)
    paste(c, art(main, 300), SIZE / 2 - 34, SIZE / 2 - (40 if text else 6))
    paste(c, art(extra, 190), SIZE / 2 + 118, SIZE / 2 + (40 if text else 96), angle=-10)
    if text:
        badge(c, text)
    return c


def emeralds(count_index, amount):
    # Bigger packs show a bigger pile, like the store: pack i has i gems fanned behind the main one.
    c = tile("green")
    size = max(210, 150 + count_index * 22)
    for k in range(1, count_index):
        side = -1 if k % 2 == 1 else 1
        row = (k - 1) // 2
        paste(c, art("emerald", int(size * 0.72)), SIZE / 2 + side * (size * 0.34 + row * size * 0.22), SIZE / 2 - 20 + row * 10, angle=-side * (14 + row * 10))
    paste(c, art("emerald", size), SIZE / 2, SIZE / 2 - 34)
    badge(c, amount)
    return c


PRODUCTS = [
    ("Revive1", lambda: single("red", "revive", scale=340)),
    ("Revive2", lambda: single("red", "revive", scale=340)),
    ("Revive3", lambda: single("red", "revive", scale=340)),
    ("Revive4", lambda: single("red", "revive", scale=340)),
    ("Revive5", lambda: single("red", "revive", scale=340)),
    ("ShopReroll", lambda: single("blue", "reroll")),
    ("UpgradeReroll", lambda: single("blue", "reroll")),
    ("Banish", lambda: single("purple", "banish")),
    ("Rerolls5", lambda: single("blue", "reroll", "×5")),
    ("Rerolls15", lambda: single("blue", "reroll", "×15")),
    ("Banishes5", lambda: single("purple", "banish", "×5")),
    ("Banishes15", lambda: single("purple", "banish", "×15")),
    ("Emeralds1", lambda: emeralds(1, "400")),
    ("Emeralds2", lambda: emeralds(2, "1,700")),
    ("Emeralds3", lambda: emeralds(3, "4,200")),
    ("Emeralds4", lambda: emeralds(4, "10,500")),
    ("Emeralds5", lambda: emeralds(5, "22,000")),
    ("Emeralds6", lambda: emeralds(6, "52,000")),
    ("Royal1", lambda: single("gold", "legendary", "×1")),
    ("Royal5", lambda: single("gold", "legendary", "×5")),
    ("Royal12", lambda: single("gold", "legendary", "×12")),
    ("StarterPack", lambda: pair("gold", "legendary", "emerald", "STARTER")),
    ("ArsenalBundle", lambda: pair("teal", "w00", "emerald", "+3")),
    ("MegaBundle", lambda: single("gold", "legendary", "×30")),
    ("UltimateBundle", lambda: single("obsidian", "legendary", "×100")),
    ("BloodPhoenixBundle", lambda: pair("crimson", "w40", "phoenix")),
    ("ShadowDragonBundle", lambda: pair("shadow", "w39", "dragonscale")),
    ("GodlyStarter", lambda: pair("obsidian", "w36", "legendary")),
    ("ClassThrower", lambda: single("red", "w12", "THROWER")),
    ("ClassJuggler", lambda: single("purple", "w19", "JUGGLER")),
    ("ClassHandyman", lambda: single("blue", "w24", "HANDYMAN")),
    # Game passes
    ("PassVIP", lambda: pair("gold", "gold", "emerald", "VIP")),
    ("PassQuickOpen", lambda: single("gold", "gold", "×10")),
]

if __name__ == "__main__":
    for old in HERE.glob("[0-9][0-9]-*.png"):
        old.unlink()
    for i, (key, make) in enumerate(PRODUCTS, 1):
        path = HERE / f"{i:02d}-{key}.png"
        make().save(path, optimize=True)
        print(path.name)
