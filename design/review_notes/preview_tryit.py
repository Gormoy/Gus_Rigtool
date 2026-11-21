"""
Preview of the Review Notes try-it without Maya: runs the try-it plugin's own drawing maths (build_items) on a fake
viewport and paints the result with Pillow, so Gus can compare it with his Maya screenshot.

    python3 design/review_notes/preview_tryit.py      # writes design/review_notes/expected_*.png
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))


def plugin_namespace():
    """The plugin source from the try-it file, run without Maya (only the maths gets defined)."""
    src = open(os.path.join(HERE, "tryit_review_draw.py")).read()
    start = src.index("PLUGIN_SOURCE = r'''") + len("PLUGIN_SOURCE = r'''")
    plugin = src[start:src.index("'''", start)]
    ns = {"__name__": "review_try_plugin"}
    exec(compile(plugin, "gusReviewNotesTry.py", "exec"), ns)
    sample = src[src.index("def _sample_notes"):src.index("def _active_camera")]
    exec(compile(sample, "sample", "exec"), ns)
    return ns


W, H = 1280, 760
VIEW_ASPECT = W / float(H)
RENDER = (-0.5, 0.5, -0.28125, 0.28125)                    # 1920x1080
HALF_W = 0.5 * 1.3                                          # horizontal fit, overscan 1.3
VIEW = (-HALF_W, HALF_W, -HALF_W / VIEW_ASPECT, HALF_W / VIEW_ASPECT)
F0 = 1012


def font(size):
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def background(gate, camera):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):                                      # Maya's default viewport gradient
        t = y / float(H)
        c = tuple(int(a + (b - a) * t) for a, b in zip((112, 124, 136), (44, 47, 51)))
        d.line([(0, y), (W, y)], fill=c)
    x0, y0, x1, y1 = gate
    top, bottom = H - y1, H - y0                            # y up -> image y down
    ground = top + (bottom - top) * 0.82
    for i in range(9):
        y = ground + i * i * 4 + i * 6
        d.line([(0, y), (W, y)], fill=(38, 40, 43), width=1)
    d.line([(0, ground), (W, ground)], fill=(25, 25, 25), width=2)
    # a simple stand-in character: body ball and a foot
    cx = x0 + (x1 - x0) * 0.46
    d.ellipse([cx - 40, top + (bottom - top) * 0.28, cx + 40, top + (bottom - top) * 0.28 + 80], fill=(196, 188, 170))
    d.rounded_rectangle([cx - 20, ground - 20, cx + 40, ground], 8, fill=(150, 142, 128))
    mask = Image.new("RGBA", (W, H), (0, 0, 0, 0))          # Maya's gate mask
    m = ImageDraw.Draw(mask)
    for box in ([0, 0, W, top], [0, bottom, W, H], [0, top, x0, bottom], [x1, top, W, bottom]):
        m.rectangle(box, fill=(0, 0, 0, 110))
    img = Image.alpha_composite(img.convert("RGBA"), mask)
    d = ImageDraw.Draw(img)
    d.rectangle([x0, top, x1, bottom], outline=(230, 230, 230))
    f = font(15)
    d.text((W / 2, top - 18), camera, fill=(235, 235, 235), font=f, anchor="mm")
    return img


def paint(img, items):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(14)
    for item in items:
        if item[0] == "line":
            _, rgba, width, pts = item
            col = tuple(int(c * 255) for c in rgba)
            d.line([(x, H - y) for x, y in pts], fill=col, width=max(1, int(round(width))), joint="curve")
        else:
            _, rgba, (x, y), text = item
            box = d.textbbox((x + 8, H - y - 16), text, font=f)
            d.rectangle([x, box[1] - 4, box[2] + 8, box[3] + 4], fill=(20, 20, 20, 190))
            d.text((x + 8, H - y - 16), text, fill=tuple(int(c * 255) for c in rgba), font=f)
    return Image.alpha_composite(img, layer)


def frame_label(img, frame):
    d = ImageDraw.Draw(img)
    d.text((W - 14, H - 14), str(frame), fill=(235, 235, 235), font=font(16), anchor="rb")
    return img


def main():
    ns = plugin_namespace()
    notes = ns["_sample_notes"]("shotCam", F0)["notes"]
    gate = ns["gate_rect"](VIEW, RENDER, W, H)
    shots = [("expected_1_arc", "shotCam", F0), ("expected_2_contact", "shotCam", F0 + 7),
             ("expected_3_nearby", "shotCam", F0 - 3), ("expected_4_top", "top", F0)]
    for name, cam, frame in shots:
        items = ns["build_items"](notes, {cam}, frame, gate)
        img = frame_label(paint(background(gate, cam), items), frame)
        img.convert("RGB").save(os.path.join(HERE, name + ".png"))
        print("wrote", name, len(items), "items, gate", [int(round(g)) for g in gate])
    assert math.isclose((gate[2] - gate[0]) / (gate[3] - gate[1]), 16 / 9.0, rel_tol=1e-6)


if __name__ == "__main__":
    main()
