"""Builds the Wavebreaker trailer from shots.json.

Every shot uses, in order of preference:
  1. clips/<shot id>.mp4 (your recorded gameplay; 'in' in shots.json picks the start second)
  2. its still from stills/raw/ (slow camera moves on real Studio captures)
  3. a placeholder card that says exactly what to record

Then it adds the kinetic text, map/boss labels, title and end cards, cut effects (flash,
punch, impact shake, whip blur) and the temp beat, and writes two files:
  build/wavebreaker_trailer_16x9.mp4   1920x1080 60 fps (YouTube, Roblox, Discord)
  build/wavebreaker_trailer_9x16.mp4   1080x1920 60 fps (TikTok, Shorts, Reels)

    python build_trailer.py               # both formats
    python build_trailer.py --only 16x9   # just one
    python build_trailer.py --frames 5    # a contact sheet of every shot instead of video
    python build_trailer.py --screenshots # graded 1920x1080 PNGs of every still

Needs Python 3 with numpy and Pillow, and ffmpeg (found on PATH or in the winget folder).
"""
import argparse
import glob
import json
import math
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import temp_beat

ROOT = os.path.dirname(os.path.abspath(__file__))
FPS = 60
W, H = 1920, 1080
VW, VH = 1080, 1920

# Palette: the game's lime UI accent on dark navy, so the trailer matches the HUD.
NAVY = (14, 22, 38)
LIME = (166, 230, 70)
AMBER = (255, 196, 64)
WHITE = (255, 255, 255)


def find_ffmpeg():
    p = shutil.which("ffmpeg")
    if p:
        return p
    hits = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*FFmpeg*\*\bin\ffmpeg.exe"))
    if hits:
        return sorted(hits)[-1]
    sys.exit("ffmpeg not found")


def find_font(name, fallback):
    hits = glob.glob(os.path.expandvars(rf"%LOCALAPPDATA%\Roblox\Versions\*\content\fonts\{name}"))
    if hits:
        return max(hits, key=os.path.getmtime)
    return os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", fallback)


FONT_BIG = find_font("LuckiestGuy-Regular.ttf", "impact.ttf")
FONT_UI = find_font("FredokaOne-Regular.ttf", "arialbd.ttf")
_font_cache = {}


def font(path, size):
    key = (path, int(size))
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, int(size))
    return _font_cache[key]


# ---------------------------------------------------------------------------------------------
# Easing


def ease_out(t, p=3):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** p


def ease_in_out(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def back_out(t, s=2.2):
    t = min(max(t, 0.0), 1.0) - 1
    return t * t * ((s + 1) * t + s) + 1


# ---------------------------------------------------------------------------------------------
# Stills: crop to 16:9, light grade, upscale once so slow moves stay sharp and jitter-free.

_still_cache = {}


def grade(img):
    img = ImageEnhance.Color(img).enhance(1.08)
    img = ImageEnhance.Contrast(img).enhance(1.05)
    return img


def load_still(name, scale=2):
    key = (name, scale)
    if key in _still_cache:
        return _still_cache[key]
    path = os.path.join(ROOT, "stills", "raw", name + ".jpg")
    img = Image.open(path).convert("RGB")
    w, h = img.size
    tw = min(w, round(h * 16 / 9))
    th = round(tw * 9 / 16)
    img = img.crop(((w - tw) // 2, (h - th) // 2, (w - tw) // 2 + tw, (h - th) // 2 + th))
    img = grade(img).resize((W * scale, H * scale), Image.LANCZOS)
    img = img.filter(ImageFilter.UnsharpMask(radius=2.2, percent=60, threshold=2))
    _still_cache[key] = img
    return img


def kenburns(img, move, u, size=(W, H)):
    """Crop window over the upscaled still for progress u (0..1). Bicubic with sub-pixel
    offsets, so the move glides instead of stepping. size (1080, 1920) cuts a tall window
    out of the same still for the vertical edit."""
    sw, sh = img.size
    e = ease_in_out(u)
    if move == "push":
        z, cx, cy = 1.0 + 0.10 * e, 0.5, 0.48
    elif move == "pushfast":
        z, cx, cy = 1.0 + 0.20 * ease_out(u, 2), 0.5, 0.5
    elif move == "pull":
        z, cx, cy = 1.14 - 0.14 * e, 0.5, 0.5
    elif move == "pan":
        z, cx, cy = 1.12, 0.5 - 0.035 + 0.07 * e, 0.5
    else:  # "hold"
        z, cx, cy = 1.0 + 0.03 * e, 0.5, 0.5
    ow, oh = size
    ch = sh / z
    cw = ch * ow / oh
    if cw > sw:  # a 16:9 window at z=1 is the whole still
        cw, ch = sw / z, sh / z
    x0 = min(max(cx * sw - cw / 2, 0), sw - cw)
    y0 = min(max(cy * sh - ch / 2, 0), sh - ch)
    a = cw / ow
    return img.transform((ow, oh), Image.AFFINE, (a, 0, x0, 0, a, y0), resample=Image.BICUBIC)


# ---------------------------------------------------------------------------------------------
# Clips: decode a recorded clip straight to 1920x1080 RGB frames at 60 fps.


class ClipReader:
    def __init__(self, ff, path, start, frames):
        vf = f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"
        cmd = [ff, "-v", "error", "-ss", str(start), "-i", path, "-frames:v", str(frames), "-vf", vf,
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        self.last = None

    def next(self):
        data = self.p.stdout.read(W * H * 3)
        if len(data) == W * H * 3:
            self.last = Image.frombuffer("RGB", (W, H), data, "raw", "RGB", 0, 1)
        return self.last if self.last is not None else Image.new("RGB", (W, H), NAVY)

    def close(self):
        self.p.stdout.close()
        self.p.wait()


# ---------------------------------------------------------------------------------------------
# Placeholder card: what to record, styled to sit in the edit without looking broken.

_placeholder_cache = {}


def wrap(draw, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if draw.textlength(test, font=fnt) <= width:
            cur = test
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def placeholder_base(shot):
    key = shot["id"]
    if key in _placeholder_cache:
        return _placeholder_cache[key]
    img = Image.new("RGB", (W, H), NAVY)
    px = np.array(img).astype(np.float32)
    yy = np.linspace(0, 1, H)[:, None, None]
    px = px * (1 - yy * 0.35) + np.array([30, 48, 76], np.float32) * (yy * 0.35)
    img = Image.fromarray(px.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((60, 60, W - 60, H - 60), radius=36, outline=(60, 82, 118), width=4)
    chip = "GAMEPLAY CLIP GOES HERE"
    f_chip = font(FONT_UI, 34)
    cw_ = d.textlength(chip, font=f_chip)
    d.rounded_rectangle((W / 2 - cw_ / 2 - 26, 120, W / 2 + cw_ / 2 + 26, 182), radius=31, fill=AMBER)
    d.text((W / 2, 151), chip, font=f_chip, fill=NAVY, anchor="mm")
    sid, _, rest = shot["id"].partition("_")
    d.text((W / 2, 300), sid, font=font(FONT_BIG, 150), fill=LIME, anchor="mm", stroke_width=6, stroke_fill=(8, 12, 22))
    d.text((W / 2, 420), rest.replace("_", " ").upper(), font=font(FONT_UI, 64), fill=WHITE, anchor="mm")
    f_rec = font(FONT_UI, 36)
    y = 520
    for line in wrap(d, shot.get("record", ""), f_rec, 1450):
        d.text((W / 2, y), line, font=f_rec, fill=(196, 208, 228), anchor="mm")
        y += 50
    file_hint = f"clips/{shot['id']}.mp4"
    d.text((W / 2, H - 150), file_hint, font=font(FONT_UI, 32), fill=(130, 150, 182), anchor="mm")
    _placeholder_cache[key] = img
    return img


def placeholder_frame(shot, u, seconds):
    img = placeholder_base(shot).copy()
    d = ImageDraw.Draw(img)
    # Progress bar so the length of the slot reads at a glance.
    x0, x1, y = 260, W - 260, H - 100
    d.rounded_rectangle((x0, y - 6, x1, y + 6), radius=6, fill=(40, 56, 84))
    d.rounded_rectangle((x0, y - 6, x0 + (x1 - x0) * u, y + 6), radius=6, fill=LIME)
    d.text((x1 + 30, y), f"{seconds:.1f}s", font=font(FONT_UI, 30), fill=(160, 176, 204), anchor="lm")
    return img


# ---------------------------------------------------------------------------------------------
# Text


def text_layer(text, size, fill=WHITE, stroke=10, shadow=True, gradient=None):
    """Renders a word or phrase to an RGBA image with outline and soft drop shadow."""
    f = font(FONT_BIG, size)
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = tmp.textbbox((0, 0), text, font=f, stroke_width=stroke)
    pad = stroke + 30
    w, h = r - l + pad * 2, b - t + pad * 2
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("L", (w, h), 0)
        ImageDraw.Draw(sh).text((pad - l, pad - t + size * 0.06), text, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
        sh = sh.filter(ImageFilter.GaussianBlur(size * 0.06))
        layer.paste((0, 0, 0, 160), (0, 0), sh.point(lambda v: v * 0.75))
    outline = Image.new("L", (w, h), 0)
    ImageDraw.Draw(outline).text((pad - l, pad - t), text, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
    layer.paste(NAVY + (255,), (0, 0), outline)
    face = Image.new("L", (w, h), 0)
    ImageDraw.Draw(face).text((pad - l, pad - t), text, font=f, fill=255)
    if gradient:
        g = np.zeros((h, w, 4), np.uint8)
        k = np.linspace(0, 1, h)[:, None]
        for c in range(3):
            g[..., c] = (gradient[0][c] * (1 - k) + gradient[1][c] * k).astype(np.uint8)
        g[..., 3] = 255
        layer.paste(Image.fromarray(g, "RGBA"), (0, 0), face)
    else:
        layer.paste(fill + (255,), (0, 0), face)
    return layer


_text_cache = {}


def cached_text(text, size, **kw):
    key = (text, size, tuple(sorted((k, str(v)) for k, v in kw.items())))
    if key not in _text_cache:
        _text_cache[key] = text_layer(text, size, **kw)
    return _text_cache[key]


def paste_center(base, layer, cx, cy, scale=1.0, alpha=1.0, maxw=None):
    if maxw and layer.width * scale > maxw:  # long words shrink to fit instead of running off
        scale *= maxw / (layer.width * scale)
    if scale != 1.0:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.BICUBIC)
    if alpha < 1.0:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer = layer.copy()
        layer.putalpha(a)
    base.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def label_layer(text, size):
    f = font(FONT_UI, size)
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    tw = tmp.textlength(text, font=f)
    w, h = int(tw + 64), int(size * 1.7)
    layer = Image.new("RGBA", (w, h + 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((0, 0, w, h), radius=h // 2, fill=NAVY + (225,))
    d.rounded_rectangle((0, h + 4, w * 0.55, h + 12), radius=4, fill=LIME + (255,))
    d.text((w / 2, h / 2), text, font=f, fill=WHITE, anchor="mm")
    return layer


# ---------------------------------------------------------------------------------------------
# Shot rendering


class Timeline:
    def __init__(self, cfg):
        self.beat = 60.0 / cfg["bpm"]
        self.shots = []
        b = 0.0
        for s in cfg["shots"]:
            start = round(b * self.beat * FPS)
            end = round((b + s["beats"]) * self.beat * FPS)
            self.shots.append((s, start, end))
            b += s["beats"]
        # The end card holds past the last beat so the music's final hit can ring out.
        s, start, end = self.shots[-1]
        self.shots[-1] = (s, start, end + round(cfg.get("tail", 0) * FPS))
        self.frames = self.shots[-1][2]


def source_for(shot):
    clip = os.path.join(ROOT, "clips", shot["id"] + ".mp4")
    if os.path.exists(clip):
        return "clip", clip
    if shot.get("still") and os.path.exists(os.path.join(ROOT, "stills", "raw", shot["still"] + ".jpg")):
        return "still", shot["still"]
    return "placeholder", None


def vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    v = 1 - 0.28 * np.clip((r - 0.55) / 0.85, 0, 1) ** 1.6
    return v[..., None]


VIGNETTE = None


def finish(img):
    """Shared look: a soft vignette pulls the eye to the middle."""
    global VIGNETTE
    if VIGNETTE is None:
        VIGNETTE = vignette()
    a = np.asarray(img, dtype=np.float32) * VIGNETTE
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def shake_offset(f, strength, frames, seed):
    if f >= frames:
        return 0, 0
    k = (1 - f / frames) ** 2
    rs = np.random.default_rng(seed * 1000 + f)
    return rs.normal(0, strength * k), rs.normal(0, strength * k)


def apply_zoom(img, z, dx=0.0, dy=0.0):
    if z == 1.0 and dx == 0 and dy == 0:
        return img
    a = 1 / z
    x0 = W / 2 - W * a / 2 + dx
    y0 = H / 2 - H * a / 2 + dy
    return img.transform((W, H), Image.AFFINE, (a, 0, x0, 0, a, y0), resample=Image.BICUBIC)


def whip_blur(img, amount):
    """Horizontal motion blur for whip-pan cuts (amount 0..1)."""
    if amount <= 0.02:
        return img
    a = np.asarray(img, dtype=np.float32)
    n = 6
    step = int(70 * amount)
    acc = np.zeros_like(a)
    for i in range(n):
        acc += np.roll(a, (i - n // 2) * step // n * 2, axis=1)
    return Image.fromarray((acc / n).clip(0, 255).astype(np.uint8))


def overlay_color(img, color, alpha):
    if alpha <= 0.003:
        return img
    return Image.blend(img, Image.new("RGB", img.size, color), min(alpha, 1.0))


def title_card(shot, u, local, still):
    bg = kenburns(load_still(still), "pull" if shot["kind"] == "title" else "push", u)
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(3 if shot["kind"] == "title" else 5))).enhance(0.62)
    base = bg.convert("RGBA")
    t_in = back_out(local / 14, 2.6)
    title = cached_text(shot["title"], 250, stroke=14, gradient=((255, 255, 255), (214, 244, 150)))
    paste_center(base, title, W / 2, H * 0.43, scale=0.6 + 0.4 * t_in, alpha=min(1, local / 6), maxw=W * 0.9 * (0.6 + 0.4 * t_in))
    sub_t = ease_out((local - 10) / 14)
    if sub_t > 0:
        sub = cached_text(shot["subtitle"], 96, fill=AMBER, stroke=9)
        paste_center(base, sub, W / 2, H * 0.62 + 30 * (1 - sub_t), alpha=sub_t)
    if shot.get("cta"):
        c = ease_out((local - 28) / 16)
        if c > 0:
            f = font(FONT_UI, 54)
            label = shot["cta"]
            d = ImageDraw.Draw(base)
            tw = d.textlength(label, font=f)
            pw, ph = tw + 110, 104
            cx, cy = W / 2, H * 0.80 + 20 * (1 - c)
            pill = Image.new("RGBA", (int(pw) + 20, ph + 20), (0, 0, 0, 0))
            pd = ImageDraw.Draw(pill)
            pd.rounded_rectangle((10, 14, pw + 10, ph + 14), radius=ph // 2, fill=(0, 0, 0, 120))
            pd.rounded_rectangle((10, 6, pw + 10, ph + 6), radius=ph // 2, fill=LIME + (255,), outline=NAVY + (255,), width=6)
            pd.text((pw / 2 + 10, ph / 2 + 6), label, font=f, fill=NAVY, anchor="mm")
            paste_center(base, pill, cx, cy, scale=0.85 + 0.15 * back_out(c), alpha=c)
    return base


def render_frame(tl, f, sources, readers):
    """One 1920x1080 frame of the 16:9 edit, plus the text layout for the vertical edit."""
    for shot, start, end in tl.shots:
        if start <= f < end:
            break
    local, n = f - start, end - start
    u = local / max(1, n - 1)
    kind, src = sources[shot["id"]]
    seconds = n / FPS

    if shot["kind"] in ("title", "end"):
        base = title_card(shot, u, local, shot["still"])
        frame = base.convert("RGB")
        texts = []
    else:
        if kind == "clip":
            frame = readers[shot["id"]].next()
        elif kind == "still":
            frame = kenburns(load_still(src), shot.get("move", "push"), u)
        else:
            frame = placeholder_frame(shot, u, seconds)
        texts = []
        beats = shot.get("textBeats") or [0]
        words = shot.get("text") or []
        for i, word in enumerate(words):
            t0 = round(beats[min(i, len(beats) - 1)] * tl.beat * FPS) if i < len(beats) else 0
            t1 = round(beats[i + 1] * tl.beat * FPS) if i + 1 < len(beats) and i + 1 < len(words) else n
            if t0 <= local < t1:
                texts.append(("word", word, local - t0))
        if shot.get("label"):
            texts.append(("label", shot["label"], local))

    # Cut effects at the start of each shot.
    tr = shot.get("transition", "cut")
    if shot.get("from") == "black":
        frame = overlay_color(frame, (0, 0, 0), 1 - ease_out(local / 14))
    if tr == "punch":
        frame = apply_zoom(frame, 1 + 0.10 * (1 - ease_out(local / 9)))
        frame = overlay_color(frame, WHITE, 0.55 * (1 - local / 5))
    elif tr == "impact":
        dx, dy = shake_offset(local, 16, 20, hash(shot["id"]) % 997)
        frame = apply_zoom(frame, 1 + 0.14 * (1 - ease_out(local / 11)), dx, dy)
        frame = overlay_color(frame, WHITE, 1.0 * (1 - local / 9))
    elif tr == "flash":
        frame = overlay_color(frame, WHITE, 0.8 * (1 - local / 6))
    elif tr == "whip":
        k = 1 - ease_out(local / 8)
        frame = whip_blur(apply_zoom(frame, 1 + 0.15 * k, -120 * k, 0), k)
    # A small push on every downbeat keeps long gameplay shots moving with the music.
    if kind == "clip":
        beat_frames = tl.beat * FPS
        ph = (local % (beat_frames * 2)) / (beat_frames * 2)
        frame = apply_zoom(frame, 1 + 0.012 * (1 - ease_out(ph * 4)))
    return finish(frame), texts, shot


def draw_texts(img, texts, layout):
    """Kinetic text and labels. layout: '16x9' or '9x16' (bigger, placed in the top band)."""
    base = img.convert("RGBA")
    for kind, text, local in texts:
        if kind == "word":
            pop = back_out(local / 9, 2.4)
            alpha = min(1, local / 4)
            if layout == "16x9":
                size = 168 if len(text) <= 10 else 140
                paste_center(base, cached_text(text, size), W / 2, H * 0.74, scale=0.55 + 0.45 * pop, alpha=alpha, maxw=W * 0.9 * (0.55 + 0.45 * pop))
            else:
                size = 150 if len(text) <= 9 else 118
                paste_center(base, cached_text(text, size), VW / 2, VH * 0.195, scale=0.55 + 0.45 * pop, alpha=alpha, maxw=VW * 0.92 * (0.55 + 0.45 * pop))
        else:
            s = ease_out(local / 12)
            lay = label_layer(text, 56 if layout == "16x9" else 58)
            if layout == "16x9":
                x = 90 + lay.width / 2 - 60 * (1 - s)
                paste_center(base, lay, x, H - 110, alpha=s)
            else:
                paste_center(base, lay, VW / 2, VH * 0.80 + 40 * (1 - s), alpha=s)
    return base.convert("RGB")


def to_vertical(frame16, shot):
    """1080x1920 from the clean 16:9 frame: blurred fill behind a large centre crop."""
    small = frame16.resize((W // 6, H // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6))
    scale = VH / small.height
    bg = small.resize((int(small.width * scale), VH), Image.BILINEAR)
    x = (bg.width - VW) // 2
    bg = ImageEnhance.Color(ImageEnhance.Brightness(bg.crop((x, 0, x + VW, VH))).enhance(0.68)).enhance(1.25)
    if shot["kind"] in ("title", "end"):
        # Title cards: fill the whole frame, the text was drawn at 16:9 size in the middle.
        fh = VH
        fw = int(W * VH / H)
        full = frame16.resize((fw, fh), Image.LANCZOS)
        x = (fw - VW) // 2
        crop = full.crop((x, 0, x + VW, VH))
        return crop
    fh = 900
    fw = int(W * fh / H)
    fg = frame16.resize((fw, fh), Image.LANCZOS)
    x = (fw - VW) // 2
    fg = fg.crop((x, 0, x + VW, fh))
    bg.paste(fg, (0, (VH - fh) // 2))
    return bg


def title_vertical(shot, u, local):
    """Title and end cards get their own vertical layout (the 16:9 one would crop the title)."""
    bg = kenburns(load_still(shot["still"]), "pull" if shot["kind"] == "title" else "push", u, size=(VW, VH))
    base = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(4))).enhance(0.6).convert("RGBA")
    t_in = back_out(local / 14, 2.6)
    title = cached_text(shot["title"], 170, stroke=12, gradient=((255, 255, 255), (214, 244, 150)))
    paste_center(base, title, VW / 2, VH * 0.40, scale=0.6 + 0.4 * t_in, alpha=min(1, local / 6), maxw=VW * 0.94 * (0.6 + 0.4 * t_in))
    sub_t = ease_out((local - 10) / 14)
    if sub_t > 0:
        paste_center(base, cached_text(shot["subtitle"], 84, fill=AMBER, stroke=8), VW / 2, VH * 0.47 + 30 * (1 - sub_t), alpha=sub_t, maxw=VW * 0.9)
    if shot.get("cta"):
        c = ease_out((local - 28) / 16)
        if c > 0:
            f = font(FONT_UI, 50)
            d = ImageDraw.Draw(base)
            tw = d.textlength(shot["cta"], font=f)
            pw, ph = tw + 90, 98
            pill = Image.new("RGBA", (int(pw) + 20, ph + 20), (0, 0, 0, 0))
            pd = ImageDraw.Draw(pill)
            pd.rounded_rectangle((10, 6, pw + 10, ph + 6), radius=ph // 2, fill=LIME + (255,), outline=NAVY + (255,), width=6)
            pd.text((pw / 2 + 10, ph / 2 + 6), shot["cta"], font=f, fill=NAVY, anchor="mm")
            paste_center(base, pill, VW / 2, VH * 0.60, scale=0.85 + 0.15 * back_out(c), alpha=c)
    return base.convert("RGB")


# ---------------------------------------------------------------------------------------------


def encoder(ff, out, w, h, audio):
    cmd = [ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
           "-i", audio, "-map", "0:v", "-map", "1:a",
           "-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq", "-rc", "vbr", "-cq", "17", "-b:v", "0",
           "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest",
           "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    return p


def encoder_x264(ff, out, w, h, audio):
    cmd = [ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
           "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-profile:v", "high",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["16x9", "9x16"])
    ap.add_argument("--frames", type=int, help="write a contact sheet with this many frames per shot")
    ap.add_argument("--screenshots", action="store_true")
    ap.add_argument("--nvenc", action="store_true", help="NVIDIA GPU encoder (needs driver 610+); default is libx264")
    args = ap.parse_args()

    if args.screenshots:
        out = os.path.join(ROOT, "screenshots")
        os.makedirs(out, exist_ok=True)
        for p in sorted(glob.glob(os.path.join(ROOT, "stills", "raw", "*.jpg"))):
            name = os.path.splitext(os.path.basename(p))[0]
            img = load_still(name, scale=1)
            img.save(os.path.join(out, name + ".png"), optimize=True)
            print("screenshot", name)
        return

    ff = find_ffmpeg()
    cfg = json.load(open(os.path.join(ROOT, "shots.json")))
    tl = Timeline(cfg)
    sources = {s["id"]: source_for(s) for s, _, _ in tl.shots}
    for sid, (k, _) in sources.items():
        print(f"{sid:24s} {k}")

    if args.frames:
        thumbs = []
        for shot, start, end in tl.shots:
            for i in range(args.frames):
                f = start + int((end - start - 1) * (i + 0.5) / args.frames)
                readers = {}
                if sources[shot["id"]][0] == "clip":
                    readers[shot["id"]] = ClipReader(ff, sources[shot["id"]][1], shot.get("in", 0) + (f - start) / FPS, 1)
                img, texts, sh = render_frame(tl, f, sources, readers)
                img = draw_texts(img, texts, "16x9")
                for r in readers.values():
                    r.close()
                thumbs.append(img.resize((384, 216), Image.LANCZOS))
        cols = args.frames
        rows = len(tl.shots)
        sheet = Image.new("RGB", (cols * 384, rows * 216), (0, 0, 0))
        for i, t in enumerate(thumbs):
            sheet.paste(t, ((i % cols) * 384, (i // cols) * 216))
        out = os.path.join(ROOT, "build", "contact_sheet.jpg")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        sheet.save(out, quality=88)
        print("wrote", out)
        return

    audio, _ = temp_beat.build()
    music = os.path.join(ROOT, "music.wav")
    if os.path.exists(music):
        audio = music
        print("using music.wav")
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    make = encoder if args.nvenc else encoder_x264
    outs = {}
    if args.only in (None, "16x9"):
        outs["16x9"] = make(ff, os.path.join(ROOT, "build", "wavebreaker_trailer_16x9.mp4"), W, H, audio)
    if args.only in (None, "9x16"):
        outs["9x16"] = make(ff, os.path.join(ROOT, "build", "wavebreaker_trailer_9x16.mp4"), VW, VH, audio)

    readers = {}
    current = None
    for f in range(tl.frames):
        shot = next(s for s, a, b in tl.shots if a <= f < b)
        if shot["id"] != current:
            for r in readers.values():
                r.close()
            readers = {}
            current = shot["id"]
            k, src = sources[shot["id"]]
            if k == "clip":
                start = next(a for s, a, b in tl.shots if s is shot)
                end = next(b for s, a, b in tl.shots if s is shot)
                readers[shot["id"]] = ClipReader(ff, src, shot.get("in", 0), end - start)
        frame, texts, shot = render_frame(tl, f, sources, readers)
        local = f - next(a for s, a, b in tl.shots if s is shot)
        n = next(b - a for s, a, b in tl.shots if s is shot)
        if "16x9" in outs:
            outs["16x9"].stdin.write(draw_texts(frame, texts, "16x9").tobytes())
        if "9x16" in outs:
            if shot["kind"] in ("title", "end"):
                v = title_vertical(shot, local / max(1, n - 1), local)
                tr = shot.get("transition", "cut")
                if tr == "impact":
                    v = overlay_color(v, WHITE, 1.0 * (1 - local / 9))
            else:
                v = draw_texts(to_vertical(frame, shot), texts, "9x16")
            outs["9x16"].stdin.write(v.tobytes())
        if f % 120 == 0:
            print(f"frame {f}/{tl.frames}", flush=True)
    for r in readers.values():
        r.close()
    for p in outs.values():
        p.stdin.close()
        p.wait()
    print("done:", ", ".join(outs))


if __name__ == "__main__":
    main()
