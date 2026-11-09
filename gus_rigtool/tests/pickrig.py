# A synthetic biped (hare-like) as picker input: controls with their curve outlines seen from the front.
# Used by test_picker2.py and by render_picker() to look at the automatic layout.
import math


def circle(c, r, axis, n=12):
    """Points of a circle of radius r around c, its normal along axis ('x', 'y', 'z'); front view (x, y)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        u, v = math.cos(a) * r, math.sin(a) * r
        if axis == "y":
            p = (c[0] + u, c[1], c[2] + v)
        elif axis == "x":
            p = (c[0], c[1] + u, c[2] + v)
        else:
            p = (c[0] + u, c[1] + v, c[2])
        pts.append((p[0], p[1]))
    return pts


def box(c, sx, sy):
    return [(c[0] - sx, c[1] - sy), (c[0] + sx, c[1] - sy), (c[0] + sx, c[1] + sy), (c[0] - sx, c[1] + sy)]


RED, BLUE, YEL, PINK, CYAN = [1, .25, .25], [.2, .4, 1], [1, .85, .2], [1, .5, .8], [.4, .9, 1]


def rig():
    out = []

    def add(name, c, pts, rgb, side="C", twin=None, depth=3):
        size = max(max(p[0] for p in pts) - min(p[0] for p in pts), max(p[1] for p in pts) - min(p[1] for p in pts))
        out.append({"node": name, "pos": list(c) + [0.0] if len(c) == 2 else list(c), "pts": pts, "size": size,
                    "rgb": rgb, "side": side, "twin": twin, "depth": depth})

    def both(base, c, pts_fn, depth=4):
        for side, sgn, col in (("L", 1, BLUE), ("R", -1, RED)):
            cc = (c[0] * sgn, c[1], c[2])
            add("%s_%s_ctrl" % (side, base), cc, pts_fn(cc), col, side, "%s_%s_ctrl" % ("R" if side == "L" else "L",
                                                                                     base), depth)
    add("world_ctrl", (0, 0, 0), circle((0, 0, 0), 9, "y"), YEL, depth=1)
    add("main_ctrl", (0, 0, 0), circle((0, 0, 0), 7, "y"), YEL, depth=2)
    add("cog_ctrl", (0, 10, 0), circle((0, 10, 0), 4, "y"), YEL)
    add("hips_ctrl", (0, 9.5, 0), circle((0, 9.5, 0), 3, "y"), YEL)
    for i, y in enumerate((11, 12.2, 13.4)):
        add("spine_fk%d_ctrl" % (i + 1), (0, y, 0), circle((0, y, 0), 2.6, "y"), YEL, depth=4 + i)
    add("chest_ctrl", (0, 14.5, 0), circle((0, 14.5, 0), 3.2, "y"), YEL)
    add("spine_ik_mid_ctrl", (0, 12.5, 0), box((0, 12.5), 1.6, 0.3), YEL)
    add("neck_ctrl", (0, 16, 0), circle((0, 16, 0), 1.2, "y"), YEL)
    add("head_ctrl", (0, 18, 0), circle((0, 18, 0), 2.2, "y"), YEL)
    add("jaw_ctrl", (0, 17, 1), box((0, 16.9), 0.8, 0.3), YEL)
    both("eye", (0.6, 18.3, 1.2), lambda c: circle(c, 0.25, "z"))
    add("eyes_aim_ctrl", (0, 18.3, 5), box((0, 18.3), 1.2, 0.3), YEL)
    for i, x in enumerate((0.3, 0.7, 1.0)):
        both("brow%d" % (i + 1), (x, 18.8, 1.1), lambda c: box(c, 0.12, 0.08))
    both("lip_corner", (0.5, 17.3, 1.3), lambda c: box(c, 0.1, 0.1))
    add("lip_upper_ctrl", (0, 17.45, 1.4), box((0, 17.45), 0.15, 0.06), YEL)
    add("lip_lower_ctrl", (0, 17.15, 1.4), box((0, 17.15), 0.15, 0.06), YEL)
    for i, y in enumerate((19.5, 21, 22.5)):
        both("ear_fk%d" % (i + 1), (0.8 + i * 0.3, y, 0), lambda c: circle(c, 0.7, "y"), depth=5 + i)
    both("clavicle", (0.8, 15.2, 0), lambda c: box((c[0] + (0.6 if c[0] > 0 else -0.6), c[1]), 0.7, 0.3))
    for i, x in enumerate((2.2, 4.2, 6.0)):
        both("arm_fk%d" % (i + 1), (x, 15, 0), lambda c: circle(c, 0.9, "x"), depth=5 + i)
        both("arm_tweak%d" % (i + 1), (x + 1.0, 15, 0), lambda c: circle(c, 0.6, "x"), depth=5 + i)
    both("arm_ik", (6.0, 15, 0), lambda c: box(c, 0.7, 0.7))
    both("arm_pv", (4.2, 15, -3), lambda c: box(c, 0.3, 0.3))
    both("arm_settings", (6.4, 16.2, 0), lambda c: box(c, 0.25, 0.25))
    for fi, f in enumerate(("thumb", "index", "middle", "ring", "pinky")):
        for s in range(3):
            both("%s%d" % (f, s + 1), (6.8 + s * 0.4, 15 - fi * 0.15, 0.3 - fi * 0.15),
                 lambda c: circle(c, 0.12, "x"), depth=8 + s)
    both("fingers", (6.6, 15.5, 0), lambda c: box(c, 0.2, 0.2))
    for i, y in enumerate((8.5, 5, 1.5)):
        both("leg_fk%d" % (i + 1), (1.3, y, 0), lambda c: circle(c, 1.0, "y"), depth=5 + i)
        both("leg_tweak%d" % (i + 1), (1.3, y - 1.6, 0), lambda c: circle(c, 0.7, "y"), depth=5 + i)
    both("leg_ik", (1.3, 0.5, 0.5), lambda c: box(c, 0.8, 0.4))
    both("leg_pv", (1.3, 5, 4), lambda c: box(c, 0.3, 0.3))
    both("toe", (1.3, 0.3, 1.6), lambda c: box(c, 0.6, 0.2))
    both("leg_settings", (2.3, 1.2, 0), lambda c: box(c, 0.25, 0.25))
    add("tail_fk1_ctrl", (0, 9, -2), circle((0, 9, -2), 0.6, "z"), YEL)
    add("tail_fk2_ctrl", (0, 8.6, -3), circle((0, 8.6, -3), 0.5, "z"), YEL)
    return out


def render(picker, path, scale=1.5):
    from PIL import Image, ImageDraw
    pages = picker["pages"]
    ws = [int(p["width"] * scale) + 10 for p in pages]
    h = int(max(p["height"] for p in pages) * scale) + 30
    im = Image.new("RGB", (sum(ws), h), (45, 45, 48))
    d = ImageDraw.Draw(im)
    ox = 0
    for p, w in zip(pages, ws):
        d.rectangle((ox + 2, 22, ox + w - 4, h - 4), outline=(90, 90, 90))
        d.text((ox + 6, 4), p["name"], fill=(230, 230, 230))
        for it in p["items"]:
            x0, y0 = ox + it["x"] * scale, 24 + it["y"] * scale
            x1, y1 = x0 + it["w"] * scale, y0 + it["h"] * scale
            col = tuple(int(c * 200) for c in it["rgb"])
            if it["shape"] == "poly" and it.get("points"):
                d.polygon([(x0 + u * (x1 - x0), y0 + v * (y1 - y0)) for u, v in it["points"]], fill=col,
                          outline=(20, 20, 20))
            else:
                d.rounded_rectangle((x0, y0, x1, y1), radius=4, fill=col, outline=(20, 20, 20))
            if it["w"] * scale > 30 and it["h"] * scale > 11:
                d.text((x0 + 2, y0 + 1), it["label"][:int(it["w"] * scale / 6)], fill=(10, 10, 10))
        ox += w
    im.save(path)
