"""Final comparison sheets from the fitted-camera renders (run_ref.sh final) and the kit previews.
final_comparison.png  painting | ours closed | ours open (same fitted camera)
final_skull_closeup.png  skull close-up (painting vs ours, same camera, scaled to our skull) + mid distance
final_fixes.png  the user's feedback crops (29 lid in the air; 30/31 blocks on top) vs the fixed chest"""
from pathlib import Path
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
IMG = Path(r"C:/Users/Jeremiah/AppData/Local/Temp/claude/C--Users-Jeremiah-Documents-ChatGPT-Roblox/26e128a1-a54f-4e27-9b85-1ee1e3c3e2cf/images")
REF = Image.open(IMG / "19.webp").convert("RGB")


def row(ims, H, labels, gap=10):
    ims = [im.convert("RGB").resize((max(1, int(im.width * H / im.height)), H), Image.LANCZOS) for im in ims]
    out = Image.new("RGB", (sum(i.width for i in ims) + gap * (len(ims) - 1), H), (20, 20, 24))
    d = ImageDraw.Draw(out)
    x = 0
    for im, lb in zip(ims, labels):
        out.paste(im, (x, 0))
        d.rectangle((x, 0, x + 8 + 7 * len(lb), 22), fill=(20, 20, 24))
        d.text((x + 5, 5), lb, fill=(255, 255, 255))
        x += im.width + gap
    return out


def stack(rows, gap=10):
    W = max(r.width for r in rows)
    out = Image.new("RGB", (W, sum(r.height for r in rows) + gap * (len(rows) - 1)), (20, 20, 24))
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height + gap
    return out


Image.open(HERE / "cmp_final.png").save(HERE / "final_comparison.png")

sk = Image.open(HERE / "skull_final.png")
mid = row([REF.crop((760, 180, 1320, 620)), Image.open(HERE / "ref_final.png").crop((760, 120, 1320, 560))], 440,
          ["painting, mid distance", "ours, same camera"])
stack([sk, mid.resize((sk.width, int(mid.height * sk.width / mid.width)), Image.LANCZOS)]).save(HERE / "final_skull_closeup.png")

closed = Image.open(KIT / "previews/magical-closed.png")
opened = Image.open(KIT / "previews/magical-open.png")
r1 = row([Image.open(IMG / "29.png"), opened.crop((320, 250, 950, 800)), Image.open(HERE / "ref_final_open_side.png").crop((40, 80, 760, 660))], 420,
         ["before: lid in the air", "after: open (preview)", "after: open, side"])
r2 = row([Image.open(IMG / "30.png"), Image.open(IMG / "31.png"), closed.crop((300, 170, 720, 480)), closed.crop((760, 160, 1080, 480))], 420,
         ["before", "before (the line)", "after: left block", "after: right block"])
stack([r1, r2]).save(HERE / "final_fixes.png")
print("final sheets written")
