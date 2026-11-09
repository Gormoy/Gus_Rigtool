"""Make the Home icon and the Guide's step pictures (run from tests/: python3 make_rig_guide_images.py)."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.dirname(ROOT))
from gus_rigtool import registry  # noqa: E402

ICONS = os.path.join(ROOT, "icons")
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(size):
    try:
        return ImageFont.truetype(BOLD, size)
    except OSError:
        return ImageFont.load_default()


def home_icon():
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((1, 1, 30, 30), 5, fill=(66, 120, 160, 255), outline=(40, 80, 110, 255))
    d.polygon([(16, 6), (27, 16), (5, 16)], fill=(240, 240, 240, 255))           # roof
    d.rectangle((9, 16, 23, 26), fill=(240, 240, 240, 255))                       # walls
    d.rectangle((14, 19, 18, 26), fill=(66, 120, 160, 255))                       # door
    im.save(os.path.join(ICONS, "gr_home.png"))


def letter_icon(name, letters, colour):
    """A tile like the other tool icons: two letters on a colour."""
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((1, 1, 30, 30), 4, fill=colour + (255,), outline=tuple(int(c * 0.75) for c in colour) + (255,))
    f = font(13)
    w = d.textlength(letters, font=f)
    d.text(((32 - w) / 2, 7), letters, font=f, fill=(250, 250, 250, 255))
    im.save(os.path.join(ICONS, "gr_%s.png" % name))


def stage_picture(index):
    """The five steps as boxes and arrows, this one lit."""
    w, h = 520, 70
    im = Image.new("RGB", (w, h), (43, 43, 43))
    d = ImageDraw.Draw(im)
    n = len(registry.STAGES)
    box, gap = 84, (w - 20 - 84 * n) / (n - 1)
    f = font(12)
    for i, (_k, title, _t, _tool, _s) in enumerate(registry.STAGES):
        x = 10 + i * (box + gap)
        lit = i == index
        done = i < index
        fill = (66, 120, 160) if lit else ((56, 107, 64) if done else (70, 70, 70))
        d.rounded_rectangle((x, 14, x + box, 56), 6, fill=fill, outline=(220, 220, 220) if lit else (90, 90, 90),
                            width=2 if lit else 1)
        label = "%d %s" % (i + 1, title if len(title) < 10 else title.split()[0])
        tw = d.textlength(label, font=f)
        d.text((x + (box - tw) / 2, 28), label, font=f, fill=(245, 245, 245))
        if i < n - 1:
            ax = x + box + 4
            d.line((ax, 35, ax + gap - 10, 35), fill=(160, 160, 160), width=2)
            d.polygon([(ax + gap - 8, 35), (ax + gap - 14, 30), (ax + gap - 14, 40)], fill=(160, 160, 160))
    im.save(os.path.join(ICONS, "guide_%s.png" % registry.STAGES[index][0]))


if __name__ == "__main__":
    home_icon()
    letter_icon("fixes", "Fx", (205, 120, 140))
    letter_icon("face", "Fa", (196, 120, 60))
    for i in range(len(registry.STAGES)):
        stage_picture(i)
    print("ok")
