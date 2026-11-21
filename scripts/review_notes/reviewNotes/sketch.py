"""
The drawing you're making (not saved yet): strokes in gate space, and what each tool does with the mouse.
No Maya in here - the Maya tool (drawtool.py) feeds it mouse points already turned into gate space (0-1).

Tools:
  pen     press, drag, release: a free line
  curve   like Illustrator's pen: click = a corner point, click-drag = a smooth point (handles pulled out);
          click the first point to close it; drag a point or handle to adjust it, Ctrl-drag a handle breaks it
          (Alt is Maya's camera); End curve (or another tool, or Save) finishes it
  arrow   press = the tail, release = the head
  circle  press and release = two corners of the box it fits in
  eraser  rub over lines: only the part under it goes (Size = how big); saved notes too (drawtool.py)
Enter ends a curve (or saves the note), Esc throws the curve away, a double-click ends it too (drawtool.py).
"""

import math

from reviewNotes.draw import bezier, ellipse

TOOLS = ("pen", "curve", "arrow", "circle", "eraser")
HIT = 0.014              # how close (gate widths) a click must be to a point or handle
ASPECT = 16 / 9.0


def dist(a, b, aspect=ASPECT):
    """Distance on screen in gate widths (y is scaled: the gate is wider than tall)."""
    return math.hypot(a[0] - b[0], (a[1] - b[1]) / aspect)


def seg_dist(p, a, b, aspect=ASPECT):
    """Distance on screen from p to the line from a to b (gate widths)."""
    ax, ay, bx, by, px, py = a[0], a[1] / aspect, b[0], b[1] / aspect, p[0], p[1] / aspect
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


ERASE = 0.02             # how close (gate widths) the eraser must pass to a stroke


def stroke_points(stroke):
    """The points a stroke is drawn through (curves and circles sampled)."""
    if stroke.get("tool") == "bezier":
        return bezier(stroke.get("anchors", []), stroke.get("closed", False), steps=8)
    pts = [q[:2] for q in stroke.get("points", [])]
    if stroke.get("tool") == "circle" and len(pts) >= 2:
        return ellipse(pts[0], pts[-1], 24)
    return pts


def nearest(strokes, p, limit=ERASE):
    """(index, distance) of the stroke closest to p, if it's within `limit`; (None, None) otherwise."""
    best, best_d = None, limit
    for i, stroke in enumerate(strokes):
        pts = stroke_points(stroke)
        for q0, q1 in zip(pts, pts[1:] or pts):
            d = seg_dist(p, q0, q1)
            if d < best_d:
                best, best_d = i, d
    return (best, best_d) if best is not None else (None, None)


def eraser_radius(width):
    """How far (gate widths) the eraser reaches: the Size setting (3 = 0.018, about 18 px on a 1000 px gate)."""
    return 0.006 + 0.004 * max(1, int(width))


def cut(strokes, p, radius, aspect=ASPECT):
    """The strokes with what's within `radius` of p rubbed out, like a real eraser (0.2.2 - before, a whole
    stroke went: Gus "just delete everything"). A stroke the eraser touches becomes plain lines (pen strokes)
    without the rubbed part; untouched strokes stay as they are. Returns (strokes, changed)."""
    from reviewNotes.draw import polylines
    out, changed = [], False
    for stroke in strokes:
        lines = polylines(stroke, aspect)
        if not any(seg_dist(p, a, b, aspect) < radius for line in lines for a, b in zip(line, line[1:])):
            out.append(stroke)
            continue
        changed = True
        for line in lines:
            dense = [tuple(line[0])]
            for a, b in zip(line, line[1:]):                   # points close enough that the cut is clean
                n = max(1, int(dist(a, b, aspect) / (radius / 3.0)))
                dense += [(a[0] + (b[0] - a[0]) * i / float(n), a[1] + (b[1] - a[1]) * i / float(n))
                          for i in range(1, n + 1)]
            run = []
            for q in dense + [None]:
                if q is not None and dist(q, p, aspect) >= radius:
                    run.append([round(q[0], 4), round(q[1], 4)])
                    continue
                if len(run) >= 2:
                    out.append({"tool": "pen", "color": list(stroke.get("color") or (1.0, 0.3, 0.26)),
                                "width": stroke.get("width", 3), "points": run})
                run = []
    return out, changed


class Sketch(object):
    def __init__(self):
        self.strokes = []
        self.curve = None            # the curve being drawn: {"tool": "bezier", ..., "anchors": [[p, in, out]]}
        self.drag = None             # (stroke, anchor index, part) while a curve point / handle is dragged
        self.current = None          # a pen / arrow / circle stroke while the mouse is down
        self.camera = None
        self.frame = None
        self.color = [1.0, 0.30, 0.26]
        self.width = 3
        self.tool = "pen"

    # ---------------- state ----------------
    def empty(self):
        return not self.strokes and not self.curve and not self.current

    def clear(self):
        self.strokes, self.curve, self.drag, self.current = [], None, None, None
        self.camera = self.frame = None

    def all_strokes(self):
        """What's drawn so far, the stroke in progress included."""
        out = list(self.strokes)
        if self.curve and len(self.curve["anchors"]) >= 1:
            out.append(self.curve)
        if self.current and len(self.current["points"]) >= 2:
            out.append(self.current)
        return out

    def set_tool(self, tool):
        if tool not in TOOLS:
            raise ValueError(tool)
        if tool != "curve":
            self.end_curve()
        self.tool = tool

    def start(self, camera, frame):
        """The drawing belongs to the camera and frame of its first stroke."""
        if self.camera is None:
            self.camera, self.frame = camera, frame

    def cancel_curve(self):
        """The curve in progress thrown away (Esc)."""
        self.curve, self.drag = None, None

    def end_curve(self):
        """The curve in progress is done (kept if it has 2 points or more)."""
        if self.curve and len(self.curve["anchors"]) >= 2:
            self.strokes.append(self.curve)
        self.curve, self.drag = None, None

    def finish(self):
        """Everything drawn, ready to save (a curve in progress is ended)."""
        self.end_curve()
        if self.current and len(self.current["points"]) >= 2:
            self.strokes.append(self.current)
        self.current = None
        return [dict(s) for s in self.strokes]

    # ---------------- the mouse ----------------
    def press(self, p, ctrl=False):
        p = [round(p[0], 4), round(p[1], 4)]
        if self.tool == "eraser":
            self._last_erase = p
            self._erase(p)
        elif self.tool == "curve":
            self._curve_press(p)
        else:
            self.current = {"tool": self.tool, "color": list(self.color), "width": self.width, "points": [p, p]}
            if self.tool == "pen":
                self.current["points"] = [p]

    def move(self, p, ctrl=False):
        p = [round(p[0], 4), round(p[1], 4)]
        if self.tool == "eraser":                         # dragging the eraser rubs out what it passes over
            for q in self._erase_path(p):
                self._erase(q)
        elif self.tool == "curve":
            self._curve_drag(p, ctrl)
        elif self.current is not None:
            if self.tool == "pen":
                if dist(self.current["points"][-1], p) > 0.0015:
                    self.current["points"].append(p)
            else:
                self.current["points"][-1] = p

    def release(self, p, ctrl=False):
        self.move(p, ctrl)
        if self.tool == "curve":
            self.drag = None
            return
        if self.current is not None:
            pts = self.current["points"]
            if len(pts) >= 2 and dist(pts[0], pts[-1]) > 0.002 or len(pts) > 2:
                self.strokes.append(self.current)
            self.current = None

    # ---------------- curve ----------------
    def _curve_press(self, p):
        c = self.curve
        if c and len(c["anchors"]) >= 2 and dist(c["anchors"][0][0], p) < HIT:
            c["closed"] = True
            self.end_curve()
            return
        hit = self._hit_handle(p)
        if hit:
            self.drag = hit
            return
        if c is None:
            c = self.curve = {"tool": "bezier", "color": list(self.color), "width": self.width, "closed": False,
                              "anchors": []}
        c["anchors"].append([list(p), list(p), list(p)])
        self.drag = (c, len(c["anchors"]) - 1, "new")

    def _hit_handle(self, p):
        """A point or handle of the curve in progress or of a finished curve of this drawing, under p."""
        curves = ([self.curve] if self.curve else []) + [s for s in self.strokes if s["tool"] == "bezier"]
        for c in reversed(curves):
            for i in range(len(c["anchors"]) - 1, -1, -1):
                a = c["anchors"][i]
                for part, k in (("out", 2), ("in", 1), ("point", 0)):
                    if k and dist(a[k], a[0]) < 0.002:
                        continue                          # a handle sitting on its point: grab the point
                    if dist(a[k], p) < HIT:
                        return (c, i, part)
        return None

    def _curve_drag(self, p, ctrl):
        if not self.drag:
            return
        c, i, part = self.drag
        a = c["anchors"][i]
        pt = a[0]
        if part == "new":                                  # pulling the handles of a new smooth point
            a[2] = list(p)
            if not ctrl:
                a[1] = [2 * pt[0] - p[0], 2 * pt[1] - p[1]]
        elif part == "point":                              # the point moves with its handles
            dx, dy = p[0] - pt[0], p[1] - pt[1]
            for k in range(3):
                a[k] = [a[k][0] + dx, a[k][1] + dy]
        else:                                              # one handle; the other stays opposite (Ctrl breaks)
            k, other = (2, 1) if part == "out" else (1, 2)
            a[k] = list(p)
            if not ctrl:
                vx, vy = p[0] - pt[0], p[1] - pt[1]
                length = math.hypot(vx, vy) or 1.0
                keep = math.hypot(a[other][0] - pt[0], a[other][1] - pt[1])
                if keep > 1e-4:
                    a[other] = [pt[0] - vx / length * keep, pt[1] - vy / length * keep]

    # ---------------- eraser ----------------
    def _erase_path(self, p):
        """Points every half eraser-width from the last eraser position to p (a fast drag skips nothing)."""
        last = getattr(self, "_last_erase", None) or p
        self._last_erase = p
        steps = max(1, int(dist(last, p) / (eraser_radius(self.width) / 2.0)))
        return [(last[0] + (p[0] - last[0]) * i / float(steps), last[1] + (p[1] - last[1]) * i / float(steps))
                for i in range(1, steps + 1)]

    def _erase(self, p):
        """Rubs out the part of this drawing under p. True if anything went."""
        self.strokes, changed = cut(self.strokes, p, eraser_radius(self.width))
        return changed

    # ---------------- what the node draws on top while you draw ----------------
    def handles(self):
        """Points and handles of the curves of this drawing (shown only while the Curve tool is on)."""
        if self.tool != "curve":
            return []
        curves = ([self.curve] if self.curve else []) + [s for s in self.strokes if s["tool"] == "bezier"]
        out = []
        for c in curves:
            for a in c["anchors"]:
                out.append((a[0], a[1] if dist(a[1], a[0]) > 0.002 else None,
                            a[2] if dist(a[2], a[0]) > 0.002 else None))
        return out


SKETCH = Sketch()          # the one drawing in progress (one Maya, one hand)
