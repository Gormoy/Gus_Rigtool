"""
What Review Notes draws, worked out without Maya (so it is tested outside Maya too).

Points in the review file are in GATE SPACE: 0-1 across the camera's resolution gate, (0, 0) top-left. The node
turns them into screen pixels of the view (y up from the bottom, like Maya's 2D drawing) with the gate found
from the camera's frustums (proven by the try-it on Gus's Mac: MAYA_FACTS.md).

build_items() returns a plain list the plugin draws:
    ("line", (r, g, b, a), width, [(x, y), ...])
    ("text", (r, g, b, a), (x, y), text)
"""

import math

PAST = (0.16, 0.47, 1.0)        # the onion skin's colours: a note you've passed is blue,
NEXT = (1.0, 0.51, 0.08)        # one coming up is orange
NEARBY_ALPHA = 0.3
DONE_ALPHA = 0.45
TYPE_COLOURS = {"change": (1.0, 0.70, 0.68), "fix": (1.0, 0.85, 0.54), "add": (0.62, 0.89, 0.76),
                "idea": (0.70, 0.78, 1.0)}
LABEL_CHARS = 90


class Options(object):
    """The node's settings (its attributes in the Attribute Editor)."""

    def __init__(self, show_nearby=True, nearby_frames=6, only_open=False, show_text=True, opacity=1.0,
                 debug_gate=False, scale=1.0):
        self.show_nearby = show_nearby
        self.nearby_frames = nearby_frames
        self.only_open = only_open
        self.show_text = show_text
        self.opacity = opacity
        self.debug_gate = debug_gate
        self.scale = scale          # screen pixels per point: 2 on a Mac Retina screen


# ---------------- strokes -> lines in gate space ----------------
def bezier(anchors, closed=False, steps=16):
    """anchors: [[point, handle in, handle out], ...] -> points along the curve (steps per span)."""
    pts = []
    anchors = [a for a in anchors if len(a) >= 3]
    if len(anchors) == 1:
        return [tuple(anchors[0][0][:2])]
    spans = list(zip(anchors[:-1], anchors[1:]))
    if closed and len(anchors) > 1:
        spans.append((anchors[-1], anchors[0]))
    for n, (a, b) in enumerate(spans):
        p0, p1, p2, p3 = a[0], a[2], b[1], b[0]
        for i in range(0 if n == 0 else 1, steps + 1):
            t = i / float(steps)
            u = 1 - t
            pts.append((u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                        u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
    return pts


def ellipse(a, b, n=48):
    """The ellipse inside the box from corner a to corner b."""
    cx, cy = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
    rx, ry = abs(b[0] - a[0]) / 2.0, abs(b[1] - a[1]) / 2.0
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def arrow(a, b, aspect=16 / 9.0, size=0.025):
    """Shaft and a head that looks the same on screen whatever the gate's shape (aspect = width / height)."""
    (x0, y0), (x1, y1) = a, b
    ang = math.atan2((y1 - y0) / aspect, x1 - x0)
    head = [(x1 - size * math.cos(ang + s), y1 - size * math.sin(ang + s) * aspect) for s in (-0.45, 0.45)]
    return [[(x0, y0), (x1, y1)], [head[0], (x1, y1), head[1]]]


def polylines(stroke, aspect=16 / 9.0):
    """A stroke as lists of points in gate space. Unknown tools draw as plain lines."""
    tool = stroke.get("tool", "pen")
    if tool == "bezier":
        pts = bezier(stroke.get("anchors", []), stroke.get("closed", False))
        return [pts] if len(pts) > 1 else []
    pts = [tuple(p[:2]) for p in stroke.get("points", []) if len(p) >= 2]
    if len(pts) < 2:
        return []
    if tool == "circle":
        return [ellipse(pts[0], pts[-1])]
    if tool == "arrow":
        return arrow(pts[0], pts[-1], aspect)
    return [pts]


# ---------------- where the gate is ----------------
def gate_rect(view, render, width, height):
    """The resolution gate in the view, in pixels (x0, y0, x1, y1), y up from the bottom.
    view / render = (left, right, bottom, top) of the camera's viewing and rendering frustums."""
    vl, vr, vb, vt = view
    rl, rr, rb, rt = render
    sx, sy = width / float(vr - vl), height / float(vt - vb)
    return ((rl - vl) * sx, (rb - vb) * sy, (rr - vl) * sx, (rt - vb) * sy)


def to_screen(p, gate):
    x0, y0, x1, y1 = gate
    return (x0 + p[0] * (x1 - x0), y1 - p[1] * (y1 - y0))


# ---------------- which notes show ----------------
def camera_names(*names):
    """The names a camera answers to: transform and shape, with and without namespace."""
    out = set()
    for n in names:
        if n:
            short = n.split("|")[-1]
            out.add(short)
            out.add(short.split(":")[-1])
    return out


def camera_matches(note_camera, names):
    want = (note_camera or "").split("|")[-1]
    return bool(want) and (want in names or want.split(":")[-1] in names)


def note_state(note, frame, nearby):
    """'now' (on its frames), 'coming' (within `nearby` frames before), 'passed' (within after), or None."""
    start = int(note.get("frame", 0))
    end = start + max(1, int(note.get("hold", 1))) - 1
    if start <= frame <= end:
        return "now"
    if nearby > 0 and start - nearby <= frame < start:
        return "coming"
    if nearby > 0 and end < frame <= end + nearby:
        return "passed"
    return None


def label_text(note):
    text = " ".join((note.get("text") or "").split())
    if len(text) > LABEL_CHARS:
        text = text[:LABEL_CHARS - 3].rstrip() + "..."
    status = note.get("status", "open")
    head = note.get("type", "note").upper() + ("  [%s]" % status if status != "open" else "")
    return "%s  %s" % (head, text) if text else head


def build_items(notes, names, frame, gate, options=None):
    """Everything to draw for one view: the notes of this camera on (or near) this frame."""
    o = options or Options()
    x0, y0, x1, y1 = gate
    aspect = (x1 - x0) / float(y1 - y0) if y1 != y0 else 16 / 9.0
    items = []
    if o.debug_gate:
        green = (0.35, 1.0, 0.45, 0.9)
        cx, cy, arm = (x0 + x1) / 2.0, (y0 + y1) / 2.0, 10 * o.scale
        items += [("line", green, 1.0, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]),
                  ("line", green, 1.0, [(cx - arm, cy), (cx + arm, cy)]),
                  ("line", green, 1.0, [(cx, cy - arm), (cx, cy + arm)])]
    row = 0
    for note in sorted(notes, key=lambda n: (n.get("frame", 0), n.get("id", ""))):
        done = note.get("status") == "done"
        if (o.only_open and done) or not camera_matches(note.get("camera"), names):
            continue
        state = note_state(note, frame, o.nearby_frames if o.show_nearby else 0)
        if state is None:
            continue
        tint = {"coming": NEXT, "passed": PAST}.get(state)
        alpha = (NEARBY_ALPHA if tint else 1.0) * (DONE_ALPHA if done else 1.0) * o.opacity
        for stroke in note.get("strokes", []):
            rgb = tint or tuple(float(c) for c in (list(stroke.get("color") or (1.0, 0.3, 0.26)) + [1, 1, 1])[:3])
            width = max(1.0, float(stroke.get("width", 3)))
            for line in polylines(stroke, aspect):
                items.append(("line", rgb + (alpha,), width, [to_screen(p, gate) for p in line]))
        if state == "now" and o.show_text:
            colour = TYPE_COLOURS.get(note.get("type"), (1.0, 1.0, 1.0))
            items.append(("text", colour + ((DONE_ALPHA if done else 1.0) * o.opacity,),
                          (x0 + 10 * o.scale, y1 - (24 + row * 24) * o.scale), label_text(note)))
            row += 1
    return items
