"""
Built-in control shapes, as plain data (no Maya calls here).

A shape is a list of curves. A curve is a dict:
    degree : 1 or 3
    form   : 0 open, 2 periodic
    points : every CV as Maya counts them (a periodic curve repeats its first
             `degree` CVs at the end)
    knots  : Maya knot vector (len(points) + degree - 1 values)

All built-in shapes have a size of about 1, lie flat in the XZ plane
(facing +Y) and arrows point to +Z. The library turns and scales them.
"""

import math

# ---------------------------------------------------------------------------
# curve builders
# ---------------------------------------------------------------------------


def linear(points, closed=False):
    pts = [list(map(float, p)) for p in points]
    if closed and pts[0] != pts[-1]:
        pts.append(list(pts[0]))
    return {"degree": 1, "form": 0, "points": pts, "knots": [float(i) for i in range(len(pts))]}


def smooth(points):
    """Periodic cubic curve through (roughly) a closed loop of points."""
    pts = [list(map(float, p)) for p in points]
    pts = pts + [list(p) for p in pts[:3]]
    knots = [float(i) for i in range(-2, len(pts) + 2 - 2)]
    return {"degree": 3, "form": 2, "points": pts, "knots": knots}


def _ring(n, radius=1.0, start=0.0):
    """n points on a circle in XZ, as (x, z)."""
    out = []
    for i in range(n):
        a = math.radians(start + 360.0 * i / n)
        out.append((radius * math.sin(a), radius * math.cos(a)))
    return out


def _xz(pairs, y=0.0):
    return [(x, y, z) for x, z in pairs]


def circle_curve(radius=1.0, plane="xz", center=(0.0, 0.0, 0.0), sections=8):
    """Smooth circle whose curve passes through `radius` (CVs pushed out)."""
    push = 6.0 / (4.0 + 2.0 * math.cos(2.0 * math.pi / sections))
    pts = []
    for a, b in _ring(sections, radius * push):
        if plane == "xz":
            p = (a, 0.0, b)
        elif plane == "xy":
            p = (a, b, 0.0)
        else:  # yz
            p = (0.0, a, b)
        pts.append((p[0] + center[0], p[1] + center[1], p[2] + center[2]))
    return smooth(pts)


def _arc(r, a0, a1, steps):
    """Points (x, z) on an arc, angles in degrees, 0 = +Z."""
    out = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / float(steps))
        out.append((r * math.sin(a), r * math.cos(a)))
    return out


# ---------------------------------------------------------------------------
# shapes
# ---------------------------------------------------------------------------

def _basic():
    s = {}
    s["circle"] = [circle_curve()]
    s["half_circle"] = [linear(_xz(_arc(1.0, -90, 90, 16)), closed=True)]
    s["square"] = [linear(_xz([(-1, -1), (1, -1), (1, 1), (-1, 1)]), closed=True)]
    s["rectangle"] = [linear(_xz([(-1, -0.5), (1, -0.5), (1, 0.5), (-1, 0.5)]), closed=True)]
    s["diamond"] = [linear(_xz([(0, -1), (1, 0), (0, 1), (-1, 0)]), closed=True)]
    s["triangle"] = [linear(_xz([(0, 1), (0.866, -0.5), (-0.866, -0.5)]), closed=True)]
    s["octagon"] = [linear(_xz(_ring(8, 1.0, 22.5)), closed=True)]
    star = []
    for i, (x, z) in enumerate(_ring(10, 1.0)):
        r = 1.0 if i % 2 == 0 else 0.45
        star.append((x * r, z * r))
    s["star"] = [linear(_xz(star), closed=True)]

    t = 0.3
    plus = [(-t, 1), (t, 1), (t, t), (1, t), (1, -t), (t, -t), (t, -1), (-t, -1),
            (-t, -t), (-1, -t), (-1, t), (-t, t)]
    s["plus"] = [linear(_xz(plus), closed=True)]
    c45 = math.cos(math.radians(45))
    cross = [((x - z) * c45, (x + z) * c45) for x, z in plus]
    s["cross"] = [linear(_xz(cross), closed=True)]
    return s


def _three_d():
    s = {}
    p = [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1), (-1, -1, -1), (-1, 1, -1),
         (1, 1, -1), (1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1), (1, 1, 1),
         (-1, 1, 1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)]
    s["cube"] = [linear(p)]
    s["sphere"] = [circle_curve(plane="xz"), circle_curve(plane="xy"), circle_curve(plane="yz")]

    b = [(-1, -0.5, -1), (1, -0.5, -1), (1, -0.5, 1), (-1, -0.5, 1)]
    apex = (0, 1.0, 0)
    s["pyramid"] = [linear([b[0], b[1], b[2], b[3], b[0], apex, b[1], b[2], apex, b[3]])]

    s["cone"] = [circle_curve(center=(0, -0.5, 0)),
                 linear([(1, -0.5, 0), (0, 1.0, 0), (-1, -0.5, 0)]),
                 linear([(0, -0.5, 1), (0, 1.0, 0), (0, -0.5, -1)])]

    cyl = [circle_curve(center=(0, 1, 0)), circle_curve(center=(0, -1, 0))]
    for x, z in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        cyl.append(linear([(x, -1, z), (x, 1, z)]))
    s["cylinder"] = cyl

    s["diamond_3d"] = [
        linear([(1, 0, 0), (0, 0, 1), (-1, 0, 0), (0, 0, -1)], closed=True),
        linear([(1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)], closed=True),
        linear([(0, 1, 0), (0, 0, 1), (0, -1, 0), (0, 0, -1)], closed=True),
    ]
    s["locator"] = [linear([(-1, 0, 0), (1, 0, 0)]),
                    linear([(0, -1, 0), (0, 1, 0)]),
                    linear([(0, 0, -1), (0, 0, 1)])]
    return s


def _four_way_points():
    arm = [(0.2, 0.2), (0.2, 0.6), (0.4, 0.6), (0.0, 1.0), (-0.4, 0.6), (-0.2, 0.6)]
    pts = []
    for k in range(4):
        for x, z in arm:
            for _ in range(k):
                x, z = -z, x
            pts.append((x, z))
    return pts


def _curved_band(r=0.9, width=0.22, a0=-50.0, a1=50.0, head_len=14.0, head_w=0.48, both=True, steps=12):
    """A thick arrow bent along an arc (x, z), heads at one or both ends, centred on the arc."""
    def at(rad, ang):
        a = math.radians(ang)
        return (rad * math.sin(a), rad * math.cos(a))
    ro, ri = r + width / 2.0, r - width / 2.0
    ho, hi = r + head_w / 2.0, r - head_w / 2.0
    s0 = a0 + (head_len if both else 0.0)
    s1 = a1 - head_len
    pts = [at(ro, s0 + (s1 - s0) * i / float(steps)) for i in range(steps + 1)]
    pts += [at(ho, s1), at(r, a1), at(hi, s1)]                       # end head
    pts += [at(ri, s1 + (s0 - s1) * i / float(steps)) for i in range(steps + 1)]
    if both:
        pts += [at(hi, s0), at(r, a0), at(ho, s0)]                   # start head
    return pts


def _arrows():
    s = {}
    s["arrow"] = [linear(_xz([(-0.3, -1), (0.3, -1), (0.3, 0.2), (0.7, 0.2), (0, 1),
                              (-0.7, 0.2), (-0.3, 0.2)]), closed=True)]
    s["double_arrow"] = [linear(_xz([(0, 1), (0.6, 0.4), (0.25, 0.4), (0.25, -0.4), (0.6, -0.4),
                                     (0, -1), (-0.6, -0.4), (-0.25, -0.4), (-0.25, 0.4),
                                     (-0.6, 0.4)]), closed=True)]

    curved = _curved_band()
    cz = (max(z for _, z in curved) + min(z for _, z in curved)) / 2.0
    s["curved_arrow"] = [linear(_xz([(x, z - cz) for x, z in curved]), closed=True)]
    one = _curved_band(a0=-55.0, a1=55.0, both=False)
    cz = (max(z for _, z in one) + min(z for _, z in one)) / 2.0
    s["curved_arrow_single"] = [linear(_xz([(x, z - cz) for x, z in one]), closed=True)]

    four = _four_way_points()
    s["four_way_arrow"] = [linear(_xz(four), closed=True)]
    s["curved_four_way"] = [linear([(x, -0.35 * (x * x + z * z), z) for x, z in four], closed=True)]

    arc = _arc(1.0, 0, 300, 25)
    a = math.radians(300)
    tip_a = math.radians(325)
    ex, ez = arc[-1]
    head = [(1.2 * math.sin(a), 1.2 * math.cos(a)),
            (1.0 * math.sin(tip_a), 1.0 * math.cos(tip_a)),
            (0.8 * math.sin(a), 0.8 * math.cos(a)),
            (ex, ez)]
    s["rotate_arrow"] = [linear(_xz(arc + head))]
    return s


def _rig():
    s = {}
    cog = []
    for i, (x, z) in enumerate(_ring(16, 1.0)):
        r = 1.0 if i % 2 == 0 else 0.78
        cog.append((x * r, 0.0, z * r))
    s["cog"] = [smooth(cog)]

    gear = []
    for t in range(8):
        base = t * 45.0
        for ang, r in ((base, 0.8), (base + 5, 1.0), (base + 17.5, 1.0), (base + 22.5, 0.8)):
            a = math.radians(ang)
            gear.append((r * math.sin(a), r * math.cos(a)))
    s["gear"] = [linear(_xz(gear), closed=True), circle_curve(radius=0.4)]

    s["pin"] = [linear([(0, 0, 0), (0, 1.5, 0)]), circle_curve(radius=0.3, plane="xy", center=(0, 1.8, 0))]
    s["square_pin"] = [linear([(0, 0, 0), (0, 1.5, 0)]),
                       linear([(-0.3, 1.5, 0), (0.3, 1.5, 0), (0.3, 2.1, 0), (-0.3, 2.1, 0)], closed=True)]

    foot = [(0, -1), (0.3, -0.9), (0.4, -0.4), (0.35, 0.2), (0.5, 0.7), (0.35, 1.0),
            (0, 1.05), (-0.35, 0.95), (-0.4, 0.5), (-0.3, 0.0), (-0.3, -0.6), (-0.25, -0.9)]
    s["foot"] = [smooth(_xz(foot))]

    # palm down, fingers to +Z, thumb on +X (CVs of a smooth curve)
    hand = [(-0.48, -1.0), (0.36, -1.0), (0.44, -0.55),
            (0.6, -0.36), (0.86, -0.08), (0.96, 0.14), (0.82, 0.24), (0.56, 0.02), (0.42, 0.1)]
    fingers = [(0.29, 0.92), (0.04, 1.08), (-0.21, 1.0), (-0.45, 0.78)]   # (centre x, tip z)
    w = 0.085
    for k, (c, tip) in enumerate(fingers):
        hand += [(c + w, 0.42), (c + w, tip - 0.1), (c, tip + 0.06), (c - w, tip - 0.1), (c - w, 0.42)]
        if k < len(fingers) - 1:
            hand.append(((c - w + fingers[k + 1][0] + w) / 2.0, 0.3))     # gap between fingers
    hand += [(-0.58, 0.1), (-0.56, -0.5)]
    s["hand"] = [smooth(_xz(hand))]

    eye = [(-1, 0), (-0.5, 0.45), (0.5, 0.45), (1, 0), (0.5, -0.45), (-0.5, -0.45)]
    s["eye"] = [smooth(_xz(eye)), circle_curve(radius=0.28)]

    root = [circle_curve(radius=1.0)]
    for k in range(4):
        tri = [(-0.15, 1.02), (0.0, 1.35), (0.15, 1.02)]
        rot = []
        for x, z in tri:
            for _ in range(k):
                x, z = -z, x
            rot.append((x, z))
        root.append(linear(_xz(rot), closed=True))
    s["root"] = root

    s["toggle"] = [linear(_xz([(-1, -0.4), (1, -0.4), (1, 0.4), (-1, 0.4)]), closed=True),
                   circle_curve(radius=0.3, center=(0.55, 0, 0))]
    return s


# ---------------------------------------------------------------------------
# public
# ---------------------------------------------------------------------------

CATEGORIES = [
    ("Basic", _basic, ["circle", "half_circle", "square", "rectangle", "diamond", "triangle",
                       "octagon", "star", "plus", "cross"]),
    ("3D", _three_d, ["cube", "sphere", "pyramid", "cone", "cylinder", "diamond_3d", "locator"]),
    ("Arrows", _arrows, ["arrow", "double_arrow", "curved_arrow", "curved_arrow_single",
                         "four_way_arrow", "curved_four_way", "rotate_arrow"]),
    ("Rig", _rig, ["cog", "gear", "pin", "square_pin", "foot", "hand", "eye", "root", "toggle"]),
]


def builtin_shapes():
    """[(category, [(name, curves), ...]), ...] in display order."""
    out = []
    for category, maker, order in CATEGORIES:
        shapes = maker()
        out.append((category, [(name, shapes[name]) for name in order]))
    return out


def label(name):
    """'four_way_arrow' -> 'Four Way Arrow'."""
    return name.replace("_", " ").title().replace("3D", "3D").replace("3d", "3D")


# ---------------------------------------------------------------------------
# transforms on shape data (pure maths)
# ---------------------------------------------------------------------------

def map_points(curves, func):
    """New shape with func applied to every point."""
    out = []
    for c in curves:
        new = dict(c)
        new["points"] = [list(func(p)) for p in c["points"]]
        new["knots"] = list(c["knots"])
        out.append(new)
    return out


def face(curves, axis):
    """Turn a shape that faces +Y so it faces the given axis ('X', 'Y' or 'Z')."""
    if axis == "X":
        return map_points(curves, lambda p: (p[1], -p[0], p[2]))
    if axis == "Z":
        return map_points(curves, lambda p: (p[0], -p[2], p[1]))
    return map_points(curves, lambda p: p)


def scale(curves, factor):
    return map_points(curves, lambda p: (p[0] * factor, p[1] * factor, p[2] * factor))


def bounds(curves):
    """(center, half size) of all points: half size is the biggest half extent."""
    pts = [p for c in curves for p in c["points"]]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    center = [(lo[i] + hi[i]) / 2.0 for i in range(3)]
    half = max((hi[i] - lo[i]) / 2.0 for i in range(3)) or 1.0
    return center, half


def fit(curves, center, half):
    """Scale and move a shape so its bounds match center / half size."""
    c0, h0 = bounds(curves)
    f = half / h0
    return map_points(curves, lambda p: tuple((p[i] - c0[i]) * f + center[i] for i in range(3)))
