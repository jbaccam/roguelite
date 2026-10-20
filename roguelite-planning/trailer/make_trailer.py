"""Wavebreaker trailer: cuts the gameplay clips to the music and adds the game's own text style.

Run:  python roguelite-planning/trailer/make_trailer.py [--preview]
Clips come from C:/Users/Jeremiah/Videos/attacks. Clips you record for the empty slots go in
C:/Users/Jeremiah/Videos/attacks/new/ under the names in USER_CLIPS; missing ones render as a
labelled placeholder card so the cut still plays.

Timing: the track is ~130.4 BPM and its drops land at 31.659 / 46.381 / 61.103 / 75.826 s.
The trailer starts at 30.2 s in the track, so the drops sit at t = 1.459, 16.181, 30.903, 45.626.
Every cut sits on the beat grid that starts at the first drop.
"""
import math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ROOT, '..', '..'))
CLIPS = 'C:/Users/Jeremiah/Videos/attacks'
NEW = CLIPS + '/new'
OUT_DIR = 'C:/Users/Jeremiah/Videos/trailer'
TRACK = 'C:/Users/Jeremiah/Downloads/boss/alex-morgan-gaming-stream-arcade-session-578484.mp3'
FONT = 'C:/Users/Jeremiah/AppData/Local/Roblox/Versions/version-11f155f3450f4c8e/content/fonts/FredokaOne-Regular.ttf'
UI = os.path.join(REPO, 'roguelite-planning/studio-prototype/ui/assets')

PREVIEW = '--preview' in sys.argv
W, H = (960, 540) if PREVIEW else (1920, 1080)
S = W / 1920  # overlay scale
FPS = 30
TRACK_START = 30.2
BEAT = (75.826 - 31.659) / 96
D1, D2, D3, D4 = (d - TRACK_START for d in (31.659, 46.381, 61.103, 75.826))
END = D4 + 4.0

# UITheme colours
LIME = (145, 239, 20); GOLD = (255, 203, 64); WHITE = (248, 249, 245); INK = (8, 10, 11)

C = {
    'shop': 'buying stuff and solo gameplay in game pov.mp4',
    'chests': 'chests opening not legendary.mp4',
    'crab': 'crab fght cinematic.mp4',
    'cyclops': 'cyclops boss fight in game pov.mp4',
    'pharaoh': 'desert boss cinematic.mp4',
    'dragon': 'dragon fight pov ingame.mp4',
    'egg': 'egg opening.mp4',
    'legendary': 'legendary chest opening only.mp4',
    'mobs': 'mobs in the desert cinematic.mp4',
    'wolf': 'moon wolf fight gameplay pov.mp4',
    # Recorded 2026-10-16: skill tree 1.4-13 s, Armory 14.4-26 s, Quests 27-44 s (CLAIM ALL at 42.4 s)
    'lobby': '../2026-10-16 21-06-20.mp4',
}
USER_CLIPS = {'skilltree': 'skill tree.mp4', 'armory': 'armory.mp4', 'mapselect': 'map select.mp4', 'quests': 'quests.mp4'}


def at(beats, base=D1):
    return base + beats * BEAT


# (start, end, clip, src_start, speed, extras)
# extras: tr = transition into the shot (zoom / whip_l / whip_r / dissolve; default hard cut with a punch),
#         text / pill = overlays, flash = white hit on a drop.
SHOTS = [
    (0.0, D1, 'mobs', 0.0, 1.0, {}),
    # Section A: the swarm, the worlds, the shop
    (at(0), at(4), 'mobs', 1.6, 1.0, {'tr': 'zoom', 'flash': 1, 'text': ('SURVIVE THE ', 'SWARM', LIME)}),
    (at(4), at(8), 'crab', 1.2, 1.0, {'tr': 'whip_l'}),
    (at(8), at(12), 'shop', 16.0, 1.0, {}),
    (at(12), at(16), 'cyclops', 7.6, 1.0, {'tr': 'whip_r', 'text': ('1 VS ', '1000', GOLD)}),
    (at(16), at(20), 'pharaoh', 7.4, 1.0, {}),
    (at(20), at(24), 'shop', 0.0, 1.0, {'tr': 'whip_l', 'pill': ('store-bag', 'SHOP'), 'text': ('', '40+', GOLD, ' WEAPONS'), 'text_y': 0.695}),
    (at(24), at(28), 'shop', 24.0, 1.0, {}),
    (at(28), at(32), 'wolf', 0.4, 1.0, {'tr': 'whip_r'}),
    # Section B: everything between runs
    (at(32), at(36), 'chests', 1.3, 1.0, {'tr': 'zoom', 'flash': 1, 'pill': ('chest', 'CHESTS')}),
    (at(36), at(38), 'lobby', 1.40, 1.0, {'tr': 'whip_l', 'pill': ('skill-tree', 'SKILL TREE')}),  # nodes spring open
    (at(38), at(40), 'lobby', 3.25, 1.0, {'pill': ('skill-tree', 'SKILL TREE'), 'nopop': 1}),  # buys Max Health III
    (at(40), at(44), 'egg', 4.1, 1.0, {'tr': 'whip_r', 'pill': ('pet-egg', 'PETS')}),
    (at(44), at(46), 'lobby', 15.2, 1.0, {'pill': ('armory-anvil', 'ARMORY')}),
    (at(46), at(50), 'lobby', 41.75, 1.0, {'tr': 'whip_l', 'pill': ('quest-scroll', 'QUESTS')}),  # CLAIM ALL burst
    (at(50), at(54), 'chests', 15.4, 1.0, {'pill': ('chest', 'CHESTS')}),
    (at(54), at(58), 'egg', 10.9, 1.0, {'tr': 'whip_r', 'pill': ('pet-egg', 'PETS')}),
    (at(58), at(64), 'dragon', 2.0, 1.0, {'tr': 'zoom'}),
    # Section C: the bosses on the peak
    (at(64), at(68), 'crab', 14.4, 1.0, {'tr': 'zoom', 'flash': 1, 'text': ('GIANT ', 'BOSSES', GOLD)}),
    (at(68), at(70), 'pharaoh', 5.0, 1.0, {'tr': 'whip_l'}),
    (at(70), at(72), 'cyclops', 2.0, 1.0, {'tr': 'whip_r'}),
    (at(72), at(74), 'wolf', 3.4, 1.0, {'tr': 'whip_l'}),
    (at(74), at(76), 'dragon', 4.3, 1.0, {'tr': 'whip_r'}),
    (at(76), at(80), 'dragon', 9.6, 1.0, {}),
    # Section D: two more fights, then the legendary chest at full speed bursts on the last drop
    (at(80), at(84), 'cyclops', 11.0, 1.0, {'tr': 'whip_l'}),
    (at(84), D4 - 3.167, 'pharaoh', 15.0, 1.0, {'tr': 'whip_r'}),
    (D4 - 3.167, D4, 'legendary', 0.0, 1.0, {'tr': 'zoom', 'nopunch': 1}),
    (D4, END, 'legendary', 3.167, 1.0, {'nopunch': 1, 'title': 1}),
]

_font_cache = {}
def font(px):
    px = max(8, int(round(px)))
    if px not in _font_cache:
        _font_cache[px] = ImageFont.truetype(FONT, px)
    return _font_cache[px]


def styled_text(parts, px, stroke=None):
    """parts: list of (text, colour). White/accent Fredoka with a dark stroke and drop shadow, like the ads."""
    f = font(px); stroke = stroke or max(2, int(px * 0.11))
    widths = [f.getbbox(t, stroke_width=stroke)[2] - f.getbbox(t, stroke_width=stroke)[0] if t.strip() else f.getlength(t) for t, _ in parts]
    widths = [f.getlength(t) for t, _ in parts]
    asc, desc = f.getmetrics()
    w = int(sum(widths) + stroke * 2 + 4); h = int(asc + desc + stroke * 2 + px * 0.12)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    shadow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img); ds = ImageDraw.Draw(shadow)
    x = stroke + 2
    for (t, col), tw in zip(parts, widths):
        ds.text((x, stroke + px * 0.08), t, font=f, fill=(0, 0, 0, 150), stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
        d.text((x, stroke), t, font=f, fill=col + (255,), stroke_width=stroke, stroke_fill=INK + (255,))
        x += tw
    shadow = shadow.filter(ImageFilter.GaussianBlur(px * 0.05))
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0)); out.alpha_composite(shadow); out.alpha_composite(img)
    return out


def nine_slice(path, w, h, corner_src=64, corner_dst=None):
    src = Image.open(path).convert('RGBA'); sw, sh = src.size
    c = corner_src; cd = corner_dst or int(min(w, h) * 0.32)
    out = Image.new('RGBA', (w, h))
    xs = [(0, c, 0, cd), (c, sw - c, cd, w - cd), (sw - c, sw, w - cd, w)]
    ys = [(0, c, 0, cd), (c, sh - c, cd, h - cd), (sh - c, sh, h - cd, h)]
    for sx0, sx1, dx0, dx1 in xs:
        for sy0, sy1, dy0, dy1 in ys:
            if dx1 > dx0 and dy1 > dy0:
                out.paste(src.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.LANCZOS), (dx0, dy0))
    return out


def pill(icon, label):
    """Feature tag like the lobby HUD buttons: dark panel with lime rim, the HUD icon, white label."""
    hpx = int(78 * S); lab = styled_text([(label, WHITE)], 44 * S)
    ic = Image.open(os.path.join(UI, 'hud', icon + '.png')).convert('RGBA').resize((int(104 * S),) * 2, Image.LANCZOS)
    w = int(ic.width * 0.78 + lab.width + 40 * S)
    panel = nine_slice(os.path.join(UI, 'panel.png'), w, hpx)
    out = Image.new('RGBA', (w + int(16 * S), int(ic.height + 4)), (0, 0, 0, 0))
    py = (out.height - hpx) // 2
    out.alpha_composite(panel, (int(16 * S), py))
    out.alpha_composite(ic, (0, 0))
    out.alpha_composite(lab, (int(ic.width * 0.86), py + (hpx - lab.height) // 2 + int(2 * S)))
    return out


def title_card():
    big = styled_text([('WAVE', WHITE), ('BREAKER', LIME)], 190 * S, stroke=int(20 * S))
    sub_lab = styled_text([('SURVIVE THE SWARM', WHITE)], 52 * S)
    sub = nine_slice(os.path.join(UI, 'panel.png'), int(sub_lab.width + 70 * S), int(86 * S))
    sub.alpha_composite(sub_lab, ((sub.width - sub_lab.width) // 2, (sub.height - sub_lab.height) // 2 + int(2 * S)))
    return big, sub


def text_sprite(spec):
    parts = [(spec[0], WHITE), (spec[1], spec[2])] + ([(spec[3], WHITE)] if len(spec) > 3 else [])
    return styled_text([p for p in parts if p[0]], 112 * S)


def ease_back(x):
    x = min(max(x, 0), 1); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def place(frame, spr, cx, cy, t_in, t_out, t, pop=True):
    """Pop in (scale 0.7 -> 1 with overshoot) and fade out. cx, cy = centre in output pixels."""
    if t < t_in or t > t_out:
        return
    k = (t - t_in) / 0.22
    sc = 0.7 + 0.3 * ease_back(k) if pop else 1
    a = min(1, k * 1.6) * min(1, (t_out - t) / 0.18)
    if a <= 0:
        return
    s = spr if abs(sc - 1) < 1e-3 else spr.resize((max(1, int(spr.width * sc)), max(1, int(spr.height * sc))), Image.BILINEAR)
    if a < 1:
        s = s.copy(); s.putalpha(s.getchannel('A').point(lambda v: int(v * a)))
    frame.alpha_composite(s, (int(cx - s.width / 2), int(cy - s.height / 2)))


def placeholder(name, n):
    img = Image.new('RGB', (W, H), (22, 29, 32))
    d = ImageDraw.Draw(img)
    msg = styled_text([(f'{name.upper()} CLIP', WHITE)], 70 * S)
    hint = styled_text([(f'drop {USER_CLIPS[name]} in attacks/new', (174, 183, 185))], 34 * S)
    img = img.convert('RGBA'); img.alpha_composite(msg, ((W - msg.width) // 2, H // 2 - msg.height)); img.alpha_composite(hint, ((W - hint.width) // 2, H // 2 + int(10 * S)))
    a = np.asarray(img.convert('RGB'))
    return [a] * n


def read_frames(clip, src, speed, n):
    if clip.startswith('user:'):
        name = clip[5:]; path = os.path.join(NEW, USER_CLIPS[name])
        if not os.path.exists(path):
            return placeholder(name, n)
    else:
        path = os.path.join(CLIPS, C[clip])
    dur = n / FPS * speed + 0.5
    vf = f'setpts=PTS/{speed:.6f},fps={FPS},scale={W}:{H}:flags=lanczos'
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{src:.3f}', '-t', f'{dur:.3f}', '-i', path, '-vf', vf,
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    fs = np.frombuffer(raw, np.uint8)
    cnt = len(fs) // (W * H * 3)
    fs = fs[:cnt * W * H * 3].reshape(cnt, H, W, 3)
    out = [fs[min(i, cnt - 1)] for i in range(n)]
    return out


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def crop_zoom(arr, z, cx=0.5, cy=0.5):
    """Zoom z toward (cx, cy) in 0-1 screen coords; the crop box is clamped inside the frame."""
    im = Image.fromarray(arr)
    if z <= 1.0005:
        return im
    cw, ch = W / z, H / z
    x0 = min(max(cx * W - cw / 2, 0), W - cw); y0 = min(max(cy * H - ch / 2, 0), H - ch)
    return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))


# Transitions work on finished frames: the outgoing shot's last frames and the incoming shot's first ones.
def zoom_blur(arr, z, spread):
    """Radial streak: average a few copies zoomed slightly apart."""
    taps = 4; acc = np.zeros((H, W, 3), np.float32)
    for j in range(taps):
        acc += np.asarray(crop_zoom(arr, z * (1 + spread * j / (taps - 1))), np.float32)
    return (acc / taps).astype(np.uint8)


def whip_blur(arr, off, length):
    """Horizontal whip pan: shift by off pixels with a motion streak of length pixels."""
    taps = 7; acc = np.zeros((H, W, 3), np.float32)
    for j in range(taps):
        acc += np.roll(arr, int(off + length * (j / (taps - 1) - 0.5)), axis=1)
    return (acc / taps).astype(np.uint8)


def transition(kind, tail, head):
    if kind == 'zoom':
        for k, (z, sp) in enumerate([(1.08, 0.04), (1.2, 0.08), (1.42, 0.12)]):
            i = len(tail) - 3 + k
            if i >= 0: tail[i] = zoom_blur(tail[i], z, sp)
        for k, (z, sp) in enumerate([(1.42, 0.12), (1.24, 0.08), (1.12, 0.05), (1.05, 0.02), (1.02, 0.0)]):
            if k < len(head): head[k] = zoom_blur(head[k], z, sp) if sp else np.asarray(crop_zoom(head[k], z))
    elif kind in ('whip_l', 'whip_r'):
        d = -1 if kind == 'whip_l' else 1
        for k, (o, l) in enumerate([(0.05, 0.05), (0.18, 0.14), (0.42, 0.3)]):
            i = len(tail) - 3 + k
            if i >= 0: tail[i] = whip_blur(tail[i], d * o * W, l * W)
        for k, (o, l) in enumerate([(0.42, 0.3), (0.18, 0.14), (0.05, 0.05)]):
            if k < len(head): head[k] = whip_blur(head[k], -d * o * W, l * W)
    elif kind == 'dissolve':
        n = len(tail)
        for i in range(n):
            a = (i + 1) / (n + 1)
            tail[i] = (tail[i].astype(np.float32) * (1 - a) + head[0].astype(np.float32) * a).astype(np.uint8)


TAIL = 6  # frames held back from each shot so the next transition can touch them


def render_shot(t0, t1, clip, src, speed, ex, title_parts):
    f0 = int(round(t0 * FPS)); f1 = int(round(t1 * FPS)); n = f1 - f0
    frames = read_frames(clip, src, speed, n)
    txt = text_sprite(ex['text']) if 'text' in ex else None
    pl = pill(*ex['pill']) if 'pill' in ex else None
    fx, fy, z0, z1 = 0.5, 0.5, 1.0, 1.0
    punchy = False
    for i in range(n):
        lt = i / FPS
        z = z0 + (z1 - z0) * smooth(i / max(1, n - 1))
        if punchy:
            z *= 1 + 0.045 * math.exp(-i / 4.5)
        fr = crop_zoom(frames[i], z, fx, fy).convert('RGBA')
        if 'title' in ex:
            big, sub = title_parts
            k = min(1, max(0, (lt - 0.35) / 0.9))
            if k > 0:
                small = fr.resize((W // 8, H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1 + 2.5 * k)).resize((W, H), Image.BILINEAR)
                fr = Image.blend(fr, small, k)
                fr.alpha_composite(Image.new('RGBA', (W, H), (5, 9, 10, int(110 * k))))
            place(fr, big, W / 2, H * 0.44, 0.55, 99, lt)
            place(fr, sub, W / 2, H * 0.44 + big.height * 0.62, 0.85, 99, lt)
        if txt is not None:
            place(fr, txt, W / 2, H * ex.get('text_y', 0.80), 0.12, (t1 - t0) - 0.12, lt)
        if pl is not None:
            t_in = -1 if ex.get('nopop') else 0.08  # same tag carried over from the previous shot
            place(fr, pl, int(60 * S) + pl.width / 2, H - int(70 * S) - pl.height / 2, t_in, (t1 - t0) - 0.1, lt)
        if ex.get('flash'):
            a = 0.55 * math.exp(-i / 3.0)
            if a > 0.02:
                fr.alpha_composite(Image.new('RGBA', (W, H), (255, 255, 255, int(255 * a))))
        yield np.asarray(fr.convert('RGB'))


def main(shots=None, name='wavebreaker-trailer'):
    shots = shots or SHOTS
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, name + ('-preview' if PREVIEW else '') + '.mp4')
    total = int(round(END * FPS))
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-ss', f'{TRACK_START}', '-t', f'{END:.3f}', '-i', TRACK,
                            '-filter_complex', f'[1:a]afade=t=in:d=0.25,afade=t=out:st={END - 3.2:.3f}:d=3.2[a]',
                            '-map', '0:v', '-map', '[a]', '-c:v', 'libx264', '-preset', 'medium' if not PREVIEW else 'veryfast',
                            '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-shortest', out], stdin=subprocess.PIPE)
    title_parts = title_card()
    written = 0

    def write(arr):
        nonlocal written
        t = written / FPS
        fb = min(1, t / 0.45) * min(1, (END - t) / 0.6)  # fade from black at the start, to black at the end
        if fb < 1:
            arr = (arr * max(fb, 0)).astype(np.uint8)
        enc.stdin.write(arr.tobytes()); written += 1

    tail = []
    for (t0, t1, clip, src, speed, ex) in shots:
        gen = render_shot(t0, t1, clip, src, speed, ex, title_parts)
        head = []
        for fr in gen:
            head.append(fr)
            if len(head) == TAIL: break
        if 'tr' in ex and tail:
            transition(ex['tr'], tail, head)
        for fr in tail: write(fr)
        buf = head
        for fr in gen:
            buf.append(fr)
            if len(buf) > TAIL: write(buf.pop(0))
        tail = buf
        print(f'{t1:6.2f}s  {clip}', flush=True)
    for fr in tail: write(fr)
    enc.stdin.close(); enc.wait()
    print('wrote', out, written, 'frames of', total)


if __name__ == '__main__':
    main()
