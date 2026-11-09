"""Draws Gus Animtool's icons (anim/gus_animtool/icons/ga_<key>.png, 32 px) - run: python3 make_anim_icons.py"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

S = 128                                      # drawn at 4x, scaled down
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "anim", "gus_animtool", "icons")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W = (240, 240, 240, 255)
DIM = (150, 155, 165, 255)
ACC = {"open": (74, 144, 226), "tween": (155, 110, 230), "keys": (235, 170, 50), "tangents": (235, 170, 50),
       "pose": (90, 190, 110), "anim": (50, 185, 175), "curves": (240, 120, 60), "space": (70, 190, 230),
       "view": (220, 90, 140), "misc": (140, 140, 150)}


def base(group):
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((4, 4, S - 5, S - 5), radius=22, fill=(40, 44, 52, 255))
    a = ACC[group]
    d.rounded_rectangle((4, S - 22, S - 5, S - 5), radius=12, fill=a + (255,))
    d.rectangle((4, S - 22, S - 5, S - 14), fill=a + (255,))
    return im, d, a + (255,)


def line(d, pts, c=W, w=9):
    d.line(pts, fill=c, width=w, joint="curve")
    r = w / 2.0
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)


def diamond(d, x, y, r=11, c=W):
    d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=c)


def arrow(d, x0, y0, x1, y1, c=W, w=9, head=16):
    line(d, [(x0, y0), (x1, y1)], c, w)
    ang = math.atan2(y1 - y0, x1 - x0)
    p = [(x1 + math.cos(ang) * 6, y1 + math.sin(ang) * 6)]
    for s in (2.5, -2.5):
        p.append((x1 + math.cos(ang + s) * head, y1 + math.sin(ang + s) * head))
    d.polygon(p, fill=c)


def curve(fn, x0=18, x1=110, n=40):
    return [(x0 + (x1 - x0) * i / n, fn(i / n)) for i in range(n + 1)]


def text(d, s, size, c=W, y=None):
    f = ImageFont.truetype(FONT, size)
    b = d.textbbox((0, 0), s, font=f)
    x = (S - (b[2] - b[0])) / 2 - b[0]
    y = ((S - 22) - (b[3] - b[1])) / 2 - b[1] if y is None else y
    d.text((x, y), s, font=f, fill=c)


def figure(d, cx, cy, sc=1.0, c=W):
    r = 9 * sc
    d.ellipse((cx - r, cy - 30 * sc - r, cx + r, cy - 30 * sc + r), fill=c)
    line(d, [(cx, cy - 18 * sc), (cx, cy + 12 * sc)], c, int(9 * sc))
    line(d, [(cx - 20 * sc, cy - 10 * sc), (cx, cy - 14 * sc), (cx + 20 * sc, cy - 10 * sc)], c, int(7 * sc))
    line(d, [(cx - 13 * sc, cy + 36 * sc), (cx, cy + 12 * sc), (cx + 13 * sc, cy + 36 * sc)], c, int(7 * sc))


def draw(key, group):
    im, d, a = base(group)
    m = 53                                                   # middle of the glyph area (above the band)
    if key == "main":
        text(d, "GA", 52)
    elif key == "picker":
        for box in ((52, 18, 76, 40), (44, 46, 84, 78), (22, 46, 38, 70), (90, 46, 106, 70), (46, 84, 62, 100),
                    (66, 84, 82, 100)):
            d.rounded_rectangle(box, radius=4, fill=W)
        d.rounded_rectangle((44, 46, 84, 78), radius=4, fill=a)
    elif key == "poses":
        for i, (x, y) in enumerate(((18, 14), (68, 14), (18, 60), (68, 60))):
            d.rounded_rectangle((x, y, x + 42, y + 40), radius=6, outline=W, width=5, fill=a if i == 0 else None)
            figure(d, x + 21, y + 22, 0.42, W)
    elif key in ("tween_prev", "tween_next"):
        line(d, [(18, m + 14), (110, m + 14)], DIM, 7)
        kx = 46 if key == "tween_prev" else 82
        d.rounded_rectangle((kx - 9, m - 2, kx + 9, m + 30), radius=5, fill=a)
        diamond(d, 18, m + 14, 10, W)
        diamond(d, 110, m + 14, 10, W)
        if key == "tween_prev":
            arrow(d, 80, m - 22, 34, m - 22)
        else:
            arrow(d, 48, m - 22, 94, m - 22)
    elif key in ("nudge_left", "nudge_right"):
        diamond(d, 64, m + 14, 18, a)
        if key == "nudge_left":
            arrow(d, 104, m - 22, 30, m - 22)
        else:
            arrow(d, 24, m - 22, 98, m - 22)
    elif key == "key":
        diamond(d, 64, m, 34, a)
        diamond(d, 64, m, 16, W)
    elif key.startswith("tan_"):
        kind = key[4:]
        if kind == "auto":
            pts = curve(lambda t: 90 - 60 * math.sin(math.pi * t))
        elif kind == "spline":
            pts = curve(lambda t: m + 34 * math.cos(math.pi * t))
        elif kind == "linear":
            pts = [(18, 92), (64, 22), (110, 92)]
        elif kind == "flat":
            pts = curve(lambda t: 90 - 64 * (1 - (2 * t - 1) ** 2) ** 1.6)
        else:
            pts = [(18, 92), (54, 92), (54, 56), (88, 56), (88, 22), (110, 22)]
        line(d, pts, W, 8)
        if kind == "flat":
            line(d, [(36, 26), (92, 26)], a, 6)
        if kind in ("auto", "spline"):
            diamond(d, 64, pts[20][1], 11, a)
        elif kind == "linear":
            diamond(d, 64, 22, 11, a)
        elif kind == "flat":
            diamond(d, 64, 26, 11, a)
        else:
            diamond(d, 54, 56, 10, a)
            diamond(d, 88, 22, 10, a)
    elif key == "mirror":
        figure(d, 40, m + 6, 0.9, W)
        figure(d, 88, m + 6, 0.9, DIM)
        for y in range(10, 104, 16):
            line(d, [(64, y), (64, y + 7)], a, 5)
    elif key == "flip":
        arrow(d, 26, m - 14, 102, m - 14, a)
        arrow(d, 102, m + 18, 26, m + 18, W)
    elif key == "reset":
        d.arc((26, 14, 102, 92), 40, 330, fill=W, width=10)
        ang = math.radians(330)
        x, y = 64 + 38 * math.cos(ang), 53 + 38 * math.sin(ang)
        d.polygon([(x + 16, y - 4), (x - 10, y - 14), (x - 2, y + 14)], fill=W)
        d.ellipse((56, 45, 72, 61), fill=a)
    elif key == "twin":
        figure(d, 38, m + 6, 0.85, W)
        figure(d, 90, m + 6, 0.85, a)
        arrow(d, 52, m + 34, 78, m + 34, W, 6, 12)
    elif key == "ikfk":
        text(d, "IK", 40, W, 10)
        text(d, "FK", 40, a, 52)
    elif key in ("copy_anim", "paste_anim"):
        if key == "copy_anim":
            d.rounded_rectangle((16, 26, 80, 100), radius=8, outline=DIM, width=6)
            d.rounded_rectangle((44, 10, 110, 84), radius=8, fill=(40, 44, 52, 255), outline=W, width=6)
            line(d, curve(lambda t: 64 - 20 * math.sin(math.pi * 2 * t), 54, 100, 20), a, 6)
        else:
            d.rounded_rectangle((24, 18, 104, 104), radius=8, outline=W, width=6)
            d.rounded_rectangle((46, 8, 82, 26), radius=5, fill=W)
            line(d, curve(lambda t: 64 - 22 * math.sin(math.pi * 2 * t), 36, 92, 20), a, 7)
    elif key == "reverse":
        line(d, curve(lambda t: 78 - 34 * math.sin(math.pi * t)), DIM, 7)
        arrow(d, 100, 24, 30, 24, a)
    elif key == "time_scale":
        for x in (24, 64, 104):
            diamond(d, x, m + 20, 11, W)
        arrow(d, 60, m - 16, 22, m - 16, a)
        arrow(d, 68, m - 16, 106, m - 16, a)
    elif key == "offset":
        for i in range(4):
            line(d, [(16, 24 + i * 20), (112, 24 + i * 20)], DIM, 3)
            diamond(d, 30 + i * 22, 24 + i * 20, 10, a if i == 3 else W)
    elif key in ("pull", "push"):
        line(d, [(18, m), (110, m)], DIM, 6)
        if key == "pull":
            arrow(d, 64, 12, 64, m - 12, a)
            arrow(d, 64, 96, 64, m + 12, a)
        else:
            arrow(d, 64, m - 8, 64, 12, a)
            arrow(d, 64, m + 8, 64, 96, a)
    elif key == "negate":
        line(d, curve(lambda t: m - 34 * math.sin(math.pi * t)), W, 8)
        line(d, curve(lambda t: m + 34 * math.sin(math.pi * t)), a, 6)
        line(d, [(18, m), (110, m)], DIM, 3)
    elif key == "smooth":
        line(d, curve(lambda t: m - 30 * math.sin(math.pi * 2 * t)), W, 8)
    elif key == "noise":
        pts = [(18 + i * 8.4, m + (18 if i % 2 else -18) * (0.6 + 0.4 * math.sin(i * 1.7))) for i in range(12)]
        line(d, pts, W, 7)
    elif key == "redundant":
        for i, x in enumerate((24, 64, 104)):
            diamond(d, x, m, 14, W if i != 1 else DIM)
        line(d, [(46, m - 22), (82, m + 22)], a, 8)
        line(d, [(46, m + 22), (82, m - 22)], a, 8)
    elif key == "euler":
        d.arc((22, 12, 106, 96), 200, 520, fill=W, width=9)
        text(d, "e", 46, a)
    elif key == "temp_world":
        d.ellipse((20, 10, 108, 98), outline=W, width=7)
        d.ellipse((44, 10, 84, 98), outline=a, width=6)
        line(d, [(20, 54), (108, 54)], a, 6)
    elif key == "temp_pivot":
        line(d, [(64, 14), (64, 94)], W, 6)
        line(d, [(24, 54), (104, 54)], W, 6)
        d.ellipse((52, 42, 76, 66), fill=a)
        d.arc((22, 12, 106, 96), 200, 320, fill=a, width=7)
    elif key == "bake_back":
        arrow(d, 64, 10, 64, 64, a)
        for x in (32, 64, 96):
            diamond(d, x, 88, 12, W)
    elif key == "arcs":
        for i in range(9):
            t = i / 8.0
            x, y = 18 + 92 * t, 92 - 70 * math.sin(math.pi * t)
            r = 4 + 3 * math.sin(math.pi * t)
            d.ellipse((x - r, y - r, x + r, y + r), fill=a if i == 4 else W)
    elif key == "hide_ctrls":
        d.ellipse((14, 30, 114, 78), outline=W, width=8)
        d.ellipse((50, 40, 78, 68), fill=a)
        line(d, [(24, 96), (104, 14)], W, 8)
    elif key == "isolate":
        for (x, y, dx, dy) in ((18, 12, 1, 1), (110, 12, -1, 1), (18, 96, 1, -1), (110, 96, -1, -1)):
            line(d, [(x + dx * 24, y), (x, y), (x, y + dy * 24)], W, 7)
        figure(d, 64, m + 4, 0.8, a)
    elif key == "playblast":
        d.rounded_rectangle((14, 16, 114, 92), radius=10, outline=W, width=7)
        d.polygon([(52, 34), (52, 74), (84, 54)], fill=a)
    elif key in ("copy_keys", "paste_keys"):
        if key == "copy_keys":
            d.rounded_rectangle((16, 30, 74, 100), radius=8, outline=DIM, width=6)
            d.rounded_rectangle((46, 10, 112, 82), radius=8, fill=(40, 44, 52, 255), outline=W, width=6)
            diamond(d, 79, 46, 16, a)
        else:
            d.rounded_rectangle((22, 18, 106, 104), radius=8, outline=W, width=6)
            d.rounded_rectangle((46, 8, 82, 26), radius=5, fill=W)
            diamond(d, 64, 62, 18, a)
    elif key in ("inbetween_add", "inbetween_remove"):
        add = key == "inbetween_add"
        diamond(d, 22, m + 18, 11, W)
        diamond(d, 106, m + 18, 11, W)
        line(d, [(36, m + 18), (92, m + 18)], DIM, 4)
        line(d, [(48, m - 22), (80, m - 22)], a, 9)
        if add:
            line(d, [(64, m - 38), (64, m - 6)], a, 9)
    elif key in ("offset_minus", "offset_plus"):
        for i in range(3):
            line(d, [(16, 22 + i * 26), (112, 22 + i * 26)], DIM, 3)
            diamond(d, 34 + i * 22, 22 + i * 26, 10, W)
        if key == "offset_plus":
            arrow(d, 60, 96, 106, 96, a, 7, 13)
        else:
            arrow(d, 106, 96, 60, 96, a, 7, 13)
    elif key == "offset_back":
        for i in range(3):
            diamond(d, 34 + i * 30, 76, 10, W)
        d.arc((30, 8, 98, 64), 180, 360, fill=a, width=8)
        d.polygon([(22, 34), (40, 34), (31, 50)], fill=a)
    elif key == "clips":
        d.rounded_rectangle((16, 22, 112, 88), radius=8, outline=W, width=6)
        for x in range(24, 110, 18):
            d.rectangle((x, 26, x + 8, 34), fill=W)
            d.rectangle((x, 76, x + 8, 84), fill=W)
        d.polygon([(54, 42), (54, 70), (78, 56)], fill=a)
    elif key == "mirror_cycle":
        figure(d, 40, m + 6, 0.8, W)
        figure(d, 88, m + 6, 0.8, a)
        d.arc((30, 66, 98, 106), 0, 180, fill=DIM, width=6)
        d.polygon([(28, 80), (40, 88), (26, 94)], fill=DIM)
    elif key == "cycle_place":
        figure(d, 64, m + 2, 0.8, W)
        d.arc((26, 78, 102, 108), 0, 330, fill=a, width=6)
        d.polygon([(100, 86), (110, 96), (94, 98)], fill=a)
    elif key == "cycle_forward":
        figure(d, 46, m + 2, 0.8, W)
        arrow(d, 70, 64, 116, 64, a, 7, 14)
        line(d, [(16, 96), (112, 96)], DIM, 5)
    elif key == "bake_keys":
        pts = curve(lambda t: 80 - 40 * math.sin(math.pi * t), 16, 112, 40)
        line(d, pts, DIM, 4)
        for i in range(0, 41, 5):
            diamond(d, pts[i][0], pts[i][1], 7, a)
    elif key == "reduce_keys":
        pts = curve(lambda t: 80 - 40 * math.sin(math.pi * t), 16, 112, 40)
        line(d, pts, W, 5)
        for i in (0, 20, 40):
            diamond(d, pts[i][0], pts[i][1], 10, a)
    elif key == "overlap":
        for i, (x0, y0) in enumerate(((20, 40), (48, 52), (74, 70), (96, 92))):
            if i:
                line(d, [prev, (x0, y0)], W if i < 3 else a, 7)
            d.ellipse((x0 - 7, y0 - 7, x0 + 7, y0 + 7), fill=W if i < 3 else a)
            prev = (x0, y0)
        d.arc((70, 60, 124, 114), 300, 60, fill=DIM, width=4)
    elif key == "blocking":
        line(d, [(14, 84), (40, 84), (40, 56), (64, 56), (64, 30)], W, 7)
        line(d, [(64, 30)] + [(64 + i * 6, 30 + 27 * (1 - math.cos(i / 8.0 * math.pi))) for i in range(1, 9)], a, 7)
    elif key == "stretch":
        line(d, [(16, 30), (16, 70)], W, 6)
        line(d, [(48, 30), (48, 70)], W, 6)
        line(d, [(80, 30), (80, 70)], a, 6)
        line(d, [(112, 30), (112, 70)], a, 6)
        arrow(d, 22, 88, 108, 88, a, 6, 12)
        arrow(d, 106, 88, 20, 88, a, 6, 12)
    elif key == "cycle_continue":
        figure(d, 30, m + 2, 0.7, DIM)
        figure(d, 64, m + 2, 0.7, W)
        figure(d, 98, m + 2, 0.7, a)
        arrow(d, 20, 96, 110, 96, W, 6, 12)
    elif key in ("attach", "release"):
        d.rounded_rectangle((14, 40, 60, 70), radius=14, outline=W, width=8)
        if key == "attach":
            d.rounded_rectangle((68, 40, 114, 70), radius=14, outline=a, width=8)
            line(d, [(44, 55), (84, 55)], W, 8)
        else:
            d.rounded_rectangle((76, 40, 114, 70), radius=14, outline=a, width=8)
            line(d, [(62, 30), (72, 20)], a, 5)
            line(d, [(64, 82), (74, 92)], a, 5)
    elif key == "hider":
        figure(d, 46, m + 6, 0.9, W)
        figure(d, 84, m + 6, 0.9, DIM)
        line(d, [(66, 100), (108, 14)], a, 7)
    elif key == "ghosts":
        for i, (x, c) in enumerate(((36, DIM), (64, W), (92, a))):
            figure(d, x, m + 6, 0.75, c)
    elif key == "update":
        arrow(d, 64, 96, 64, 22, a)
        line(d, [(26, 98), (102, 98)], W, 8)
    elif key == "reload":
        d.arc((24, 14, 104, 94), 300, 600, fill=W, width=9)
        d.polygon([(96, 18), (110, 44), (84, 44)], fill=a)
    elif key == "sets":
        for i, y in enumerate((18, 46, 74)):
            d.rounded_rectangle((16, y, 30, y + 14), radius=3, fill=a)
            line(d, [(42, y + 7), (108, y + 7)], W, 7)
    elif key == "edit":
        d.polygon([(30, 98), (36, 74), (90, 20), (108, 38), (54, 92)], fill=W)
        d.polygon([(30, 98), (36, 74), (54, 92)], fill=a)
    else:
        raise KeyError(key)
    return im.resize((32, 32), Image.LANCZOS)


def main():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "anim"))
    src = open(os.path.join(os.path.dirname(OUT), "actions.py")).read()
    start = src.index("ACTIONS = [")
    block = src[start:src.index("]\n", start) + 1]
    ns = {}
    exec(block, ns)
    keys = [(k, g) for k, _l, _t, g in ns["ACTIONS"]] + [("update", "misc"), ("reload", "misc"), ("sets", "pose"),
                                                         ("edit", "open")]
    os.makedirs(OUT, exist_ok=True)
    for k, g in keys:
        draw(k, g).save(os.path.join(OUT, "ga_%s.png" % k))
    sheet = Image.new("RGBA", (8 * 40, ((len(keys) + 7) // 8) * 40), (60, 60, 60, 255))
    for i, (k, g) in enumerate(keys):
        _ic = draw(k, g); sheet.paste(_ic, ((i % 8) * 40 + 4, (i // 8) * 40 + 4), _ic)
    sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
    return sheet, len(keys)


if __name__ == "__main__":
    sheet, n = main()
    sheet.save(os.environ.get("GA_SHEET", "ga_icons_sheet.png"))
    print(n, "icons")
