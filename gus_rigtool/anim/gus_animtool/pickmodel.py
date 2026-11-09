"""
The picker's data and layout - plain Python, no Qt (the window is pickerqt.py).

A picker: {"version": 2, "pages": [page...]}, saved in the rig profile (every scene with the rig gets it).
A page: {"name", "width", "height", "bg" (an image file or ""), "items": [item...]}
An item: {"id", "kind" ('select' | 'slider' | 'check' | 'command'), "nodes" (names without namespace),
          "x", "y", "w", "h" (page units, 0,0 = top left), "shape" ('round' | 'rect' | 'ellipse' | 'diamond' | 'poly'),
          "points" (poly: [[u, v] 0..1 in the box]), "rgb", "label", "twin" (id of the mirrored item),
          slider / check: "attr", "min", "max"; command: "code"}

Automatic layout (auto): the controls seen from the front, each button the size and outline of its curve, split
into pages (Body, Face, Hands, Tweaks), pushed apart until nothing overlaps - the two sides stay mirror images -
and the fingers as a grid (a column per finger, knuckle to tip).
"""

import copy
import json
import re

import maya.cmds as cmds

from gus_animtool import anim as A

VERSION = 2
PAGE_W = 400.0
MARGIN = 16.0
GAP = 3.0
MIN_SIZE = 16.0
MAX_W, MAX_H = 150.0, 110.0
FINGERS = ["thumb", "index", "middle", "ring", "pinky"]
FINGER_WORDS = FINGERS + ["finger", "fing", "digit", "pinkie"]
FACE_WORDS = ["eye", "lid", "brow", "lip", "mouth", "cheek", "nose", "nostril", "tongue", "teeth", "jaw", "chin",
              "squint", "smile", "pupil", "mouthcorner"]
TWEAK_WORDS = ["tweak", "twk", "bendy", "bend", "ribbon"]
# 5.6.21: clothes get their own page (the collar's front isn't the face because it's near the chin)
CLOTH_WORDS = ["collar", "cape", "sleeve", "pants", "trouser", "belt", "hood", "bandage", "shirt", "skirt", "scarf",
               "cloth", "coat", "jacket", "dress", "sock", "glove", "strap", "pouch"]
SHAPES = ["round", "rect", "ellipse", "diamond", "pill", "ring", "triangle", "hexagon", "star", "plus",
          "arrow up", "arrow down", "arrow left", "arrow right", "poly"]
TITLE_H = 16.0                                     # a frame's title bar (page units)
RIDER = "_squashRider"                             # the rig tool's head squash: a hidden copy of a face curve


def _star(n=5, inner=0.42):
    import math
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n - math.pi / 2
        r = 0.5 if i % 2 == 0 else 0.5 * inner
        pts.append([round(0.5 + r * math.cos(a), 4), round(0.5 + r * math.sin(a), 4)])
    return pts


SHAPE_POINTS = {                                   # 0..1 across and down
    "diamond": [[0.5, 0], [1, 0.5], [0.5, 1], [0, 0.5]],
    "triangle": [[0.5, 0], [1, 1], [0, 1]],
    "hexagon": [[0.25, 0], [0.75, 0], [1, 0.5], [0.75, 1], [0.25, 1], [0, 0.5]],
    "star": _star(),
    "plus": [[0.35, 0], [0.65, 0], [0.65, 0.35], [1, 0.35], [1, 0.65], [0.65, 0.65], [0.65, 1], [0.35, 1],
             [0.35, 0.65], [0, 0.65], [0, 0.35], [0.35, 0.35]],
    "arrow up": [[0.5, 0], [1, 0.5], [0.68, 0.5], [0.68, 1], [0.32, 1], [0.32, 0.5], [0, 0.5]],
    "arrow down": [[0.32, 0], [0.68, 0], [0.68, 0.5], [1, 0.5], [0.5, 1], [0, 0.5], [0.32, 0.5]],
    "arrow left": [[0, 0.5], [0.5, 0], [0.5, 0.32], [1, 0.32], [1, 0.68], [0.5, 0.68], [0.5, 1]],
    "arrow right": [[0, 0.32], [0.5, 0.32], [0.5, 0], [1, 0.5], [0.5, 1], [0.5, 0.68], [0, 0.68]],
}


def shape_points(item):
    """The outline (0..1) of a polygon shape - the item's own for 'poly' - or None (round, rect, ellipse, pill,
    ring are drawn as such)."""
    shape = item.get("shape", "round")
    if shape == "poly":
        return item.get("points") if len(item.get("points") or []) >= 3 else None
    return SHAPE_POINTS.get(shape)


# ===========================================================================
# reading the rig
# ===========================================================================

strip = A.bare


def label_of(node):
    """'L_arm_fk1_ctrl' -> 'arm fk1'."""
    base = strip(node)
    for sx in [s.strip() for s in A.suffix().split(",") if s.strip()]:
        if base.endswith(sx):
            base = base[:-len(sx)]
    for a, b in A.pairs():
        for t in (a, b):
            core = t.strip("_")
            if t and base.startswith(t):
                base = base[len(t):]
            elif core and base.endswith("_" + core):
                base = base[:-len(core) - 1]
    base = re.sub(r"(^|_)(L|R|l|r|Lf|Rt|left|right|Left|Right)(?=_|$)", "", base)
    return apply_rules(base.strip("_").replace("_", " ") or strip(node))


def _outline(node):
    """World positions of the control's curve points (CVs), or [] when unknown."""
    pts = []
    for s in cmds.listRelatives(node, shapes=True, type="nurbsCurve", fullPath=True, noIntermediate=True) or []:
        if RIDER in s.split("|")[-1]:                        # 5.6.23: the head squash's hidden copy
            continue
        try:
            flat = cmds.xform(s + ".cv[*]", query=True, worldSpace=True, translation=True) or []
        except (RuntimeError, ValueError, TypeError):
            continue
        pts += [flat[i:i + 3] for i in range(0, len(flat) - 2, 3)]
    return pts


def _depth(node):
    return len(A.long_name(node).split("|")) if A.long_name(node) else 0


def read_rig(ns=None):
    """[{'node', 'pos', 'pts' (front view: [(u, v)]), 'size', 'rgb', 'side', 'twin'}] of the character's controls."""
    ns = A.current_character() if ns is None else ns
    out = []
    for n in A.character_controls(ns):
        pos, size = A._bbox(n)
        pts3 = _outline(n) or [pos]
        out.append({"node": n, "pos": pos, "pts": [(p[0], p[1]) for p in pts3], "pts3": [tuple(p) for p in pts3],
                    "size": size, "rgb": A._colour(n),
                    "side": A.side_of(n), "twin": A.twin_of(n), "depth": _depth(n)})
    return out


def _has(name, words):
    low = name.lower()
    return any(w in low for w in words)


def _tweaks(ns):
    out = set()
    limbs = [s for s in A.with_attr("gusBlend", ns) if A.meta_str(s, "gusBlend")]
    for s in limbs:
        try:
            out.update(A.limb_controls(s, "tweaks"))
        except (RuntimeError, ValueError, TypeError):
            pass
    return out


def classify(rig, ns=""):
    """{'Body': [...], 'Face': [...], 'Hands': [...], 'Tweaks': [...]} (rig entries)."""
    tweaks = _tweaks(ns)
    ys = [r["pos"][1] for r in rig] or [0.0]
    tall = max(max(ys) - min(ys), 1e-6)
    near_head = A.face_controls([{"node": r["node"], "pos": r["pos"], "size": r["size"]} for r in rig], tall)
    pages = {"Body": [], "Face": [], "Hands": [], "Clothes": [], "Tweaks": []}
    for r in rig:
        name = strip(r["node"])
        if _has(name, CLOTH_WORDS):                             # 5.6.21: before 'near the head'
            pages["Clothes"].append(r)
        elif r["node"] in tweaks or _has(name, TWEAK_WORDS):
            pages["Tweaks"].append(r)
        elif _has(name, FINGER_WORDS):
            pages["Hands"].append(r)
        elif r["node"] in near_head or _has(name, FACE_WORDS):        # by name, whatever its curve's size
            pages["Face"].append(r)
        else:
            pages["Body"].append(r)
    return pages


# ===========================================================================
# geometry
# ===========================================================================

def hull(points):
    """Convex hull (Andrew's monotone chain), counter-clockwise."""
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _poly_inside(points, u, v):
    inside = False
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        if (y1 > v) != (y2 > v) and u < (x2 - x1) * (v - y1) / ((y2 - y1) or 1e-12) + x1:
            inside = not inside
    return inside


def _unrotate(item, x, y):
    """5.6.22: a point in the item's own (unturned) frame - a turned button is clicked on its turned shape."""
    import math
    rot = float(item.get("rot", 0.0) or 0.0)
    if not rot:
        return x, y
    cx, cy = item["x"] + item["w"] * 0.5, item["y"] + item["h"] * 0.5
    a = math.radians(-rot)
    dx, dy = x - cx, y - cy
    return cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)


def contains(item, x, y):
    x, y = _unrotate(item, x, y)
    if not (item["x"] <= x <= item["x"] + item["w"] and item["y"] <= y <= item["y"] + item["h"]):
        return False
    u, v = (x - item["x"]) / max(item["w"], 1e-6), (y - item["y"]) / max(item["h"], 1e-6)
    shape = item.get("shape", "round")
    if shape in ("ellipse", "ring"):
        return (u - 0.5) ** 2 + (v - 0.5) ** 2 <= 0.25
    pts = shape_points(item)
    if pts:
        return _poly_inside(pts, u, v)
    return True


def overlaps(a, b, gap=0.0):
    return (a["x"] < b["x"] + b["w"] + gap and b["x"] < a["x"] + a["w"] + gap and
            a["y"] < b["y"] + b["h"] + gap and b["y"] < a["y"] + a["h"] + gap)


def bounds(items):
    if not items:
        return 0.0, 0.0, PAGE_W, PAGE_W
    return (min(i["x"] for i in items), min(i["y"] for i in items), max(i["x"] + i["w"] for i in items),
            max(i["y"] + i["h"] for i in items))


# ===========================================================================
# automatic layout
# ===========================================================================

_ids = [0]


def new_id():
    _ids[0] += 1
    return "i%d" % _ids[0]


def _sync_ids(picker):
    for p in picker.get("pages", []):
        for it in p.get("items", []) + (p.get("links") or []):
            m = re.match(r"i(\d+)$", it.get("id", ""))
            if m:
                _ids[0] = max(_ids[0], int(m.group(1)))


# ===========================================================================
# views: front (bipeds), or a three-quarter side view (four-legged rigs: the legs don't hide each other)
# ===========================================================================

def project(p, view):
    """A 3D point on the page plane. 'side34': seen from the side (nose to the right), the character's left a bit
    up and to the right of its right side, as in a three-quarter view."""
    if view == "side34" and len(p) > 2:
        return (p[2] + 0.45 * p[0], p[1] + 0.25 * p[0])
    return (p[0], p[1])


def pick_view(rig):
    """'front' for an upright character, 'side34' for a long one (a quadruped: longer front to back than tall)."""
    pos = [r["pos"] for r in rig if len(r.get("pos") or []) > 2]
    if len(pos) < 3:
        return "front"
    ext = [max(p[k] for p in pos) - min(p[k] for p in pos) for k in range(3)]
    return "side34" if ext[2] > 0.8 * ext[1] and ext[2] > 1.2 * ext[0] else "front"


def _viewed(r, view):
    if view == "front" or not r.get("pts3"):
        return r
    v = dict(r)
    v["pts"] = [project(p, view) for p in r["pts3"]]
    return v


def _item(r, scale, cu, cv, center_x, max_w=MAX_W, max_h=MAX_H):
    us = [p[0] for p in r["pts"]]
    vs = [p[1] for p in r["pts"]]
    du, dv = (max(us) - min(us)) * scale, (max(vs) - min(vs)) * scale
    w = min(max_w, max(MIN_SIZE, du))
    h = min(max_h, max(MIN_SIZE, dv))
    mu, mv = (max(us) + min(us)) * 0.5, (max(vs) + min(vs)) * 0.5
    x = center_x + (mu - cu) * scale - w * 0.5
    y = -(mv - cv) * scale - h * 0.5
    shape, points = "round", []
    if du > MIN_SIZE * 1.2 and dv > MIN_SIZE * 1.2 and 0.35 < du / max(dv, 1e-6) < 2.8 and len(r["pts"]) >= 3:
        hl = hull(r["pts"])
        if len(hl) >= 3:
            shape = "poly"
            points = [[round((p[0] - min(us)) / max(max(us) - min(us), 1e-9), 3),
                       round(1.0 - (p[1] - min(vs)) / max(max(vs) - min(vs), 1e-9), 3)] for p in hl]
    return {"id": new_id(), "kind": "select", "nodes": [strip(r["node"])], "x": x, "y": y, "w": w, "h": h,
            "shape": shape, "points": points, "rgb": [round(c, 3) for c in r["rgb"]], "label": label_of(r["node"]),
            "twin": None, "_side": r["side"], "_twin_node": strip(r["twin"]) if r.get("twin") else None,
            "_area": w * h}


def _pair_up(items):
    by_node = {it["nodes"][0]: it for it in items}
    for it in items:
        other = by_node.get(it.get("_twin_node") or "")
        if other is not None and other is not it and it["_side"] == "L" and other["_side"] == "R":
            it["twin"], other["twin"] = other["id"], it["id"]


def relax(items, width, iterations=400, gap=GAP, symmetric=True):
    """Push overlapping buttons apart: the bigger one moves less, centre buttons only move up / down, a left button
    and its right twin move as mirror images (across width / 2). Returns how many overlaps are left."""
    by_id = {it["id"]: it for it in items}
    mid = width * 0.5
    left = [it for it in items if it.get("twin") and it["_side"] == "L" and it["twin"] in by_id] if symmetric else []
    rights = set(by_id[it["twin"]]["id"] for it in left)
    for it in left:                                         # start exactly symmetric
        _mirror_into(it, by_id[it["twin"]], width)
    for _ in range(iterations):
        moves = {it["id"]: [0.0, 0.0] for it in items}
        hits = 0
        order = sorted(items, key=lambda i: i["x"])
        for ai, a in enumerate(order):
            ar = a["x"] + a["w"] + gap
            for b in order[ai + 1:]:
                if b["x"] > ar:
                    break
                if not overlaps(a, b, gap):
                    continue
                hits += 1
                ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]) + gap
                oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) + gap
                wa = b["_area"] / (a["_area"] + b["_area"])
                a_center = symmetric and a["_side"] == "C" and not a.get("twin")
                b_center = symmetric and b["_side"] == "C" and not b.get("twin")
                if (ox < oy and not (a_center and b_center)) or oy <= 0:
                    sign = -1.0 if (a["x"] + a["w"] * 0.5) < (b["x"] + b["w"] * 0.5) else 1.0
                    if abs((a["x"] + a["w"] * 0.5) - (b["x"] + b["w"] * 0.5)) < 1e-6:
                        sign = -1.0 if (a["x"] + a["w"] * 0.5) < mid else 1.0
                    moves[a["id"]][0] += sign * ox * wa * 0.5
                    moves[b["id"]][0] -= sign * ox * (1 - wa) * 0.5
                else:
                    sign = -1.0 if (a["y"] + a["h"] * 0.5) <= (b["y"] + b["h"] * 0.5) else 1.0
                    moves[a["id"]][1] += sign * oy * wa * 0.5
                    moves[b["id"]][1] -= sign * oy * (1 - wa) * 0.5
        if not hits:
            return 0
        for it in items:
            if it["id"] in rights:
                continue
            dx, dy = moves[it["id"]]
            if symmetric and it.get("twin") and it["twin"] in by_id and it["_side"] == "L":
                tdx, tdy = moves[it["twin"]]
                dx, dy = (dx - tdx) * 0.5, (dy + tdy) * 0.5
                if dx == 0.0 and dy == 0.0 and (moves[it["id"]] != [0.0, 0.0] or moves[it["twin"]] != [0.0, 0.0]):
                    dx = 0.5                                    # pushed equally both ways: outwards
            elif symmetric and it["_side"] == "C" and not it.get("twin"):
                dx = 0.0
                if dy == 0.0 and moves[it["id"]][0]:
                    dy = abs(moves[it["id"]][0])               # a centre button blocked sideways goes down
            it["x"] += dx * 1.05
            it["y"] += dy * 1.05
        for it in left:
            _mirror_into(it, by_id[it["twin"]], width)
    return sum(1 for i, a in enumerate(items) for b in items[i + 1:] if overlaps(a, b))


def _mirror_into(src, dst, width):
    dst["w"], dst["h"] = src["w"], src["h"]
    dst["x"] = width - src["x"] - src["w"]
    dst["y"] = src["y"]
    if src.get("shape") == "poly":
        dst["shape"] = "poly"
        dst["points"] = [[round(1.0 - u, 3), v] for u, v in src.get("points") or []]


def _fit(items, width):
    """Shift everything so the page starts at the margin and stays centred on width / 2. Returns the page size."""
    w, h, _dx, _dy = _fit_shift(items, width)
    return w, h


def _fit_shift(items, width):
    """_fit, also returning how far everything moved (dx, dy)."""
    if not items:
        return width, width, 0.0, 0.0
    x0, y0, x1, y1 = bounds(items)
    half = max(width * 0.5 - x0, x1 - width * 0.5)
    new_w = max(width, 2 * half + 2 * MARGIN)
    dx = new_w * 0.5 - width * 0.5
    for it in items:
        it["x"] += dx
        it["y"] += MARGIN - y0
    return new_w, (y1 - y0) + 2 * MARGIN, dx, MARGIN - y0


def _clean(items):
    for it in items:
        for k in [k for k in it if k.startswith("_")]:
            del it[k]
        for k in ("x", "y", "w", "h"):
            it[k] = round(it[k], 1)


def layout_view(rig, width=PAGE_W, fill=0.82, max_w=MAX_W, max_h=MAX_H, view="front", outline=None):
    """Buttons for these controls seen in the view, fitted to the width, sized alike, no overlaps.
    outline: 3D points of the character's meshes - a faint silhouette goes behind the buttons ('outline')."""
    if not rig:
        return [], width, width
    rig = [_viewed(r, view) for r in rig]
    us = [p[0] for r in rig for p in r["pts"]]
    vs = [p[1] for r in rig for p in r["pts"]]
    du, dv = max(us) - min(us), max(vs) - min(vs)
    scale = (width * fill - 2 * MARGIN) / du if du > 1e-6 else 1.0
    if dv > 1e-6:
        scale = min(scale, (width * 1.6) / dv)
    cu, cv = (max(us) + min(us)) * 0.5, (max(vs) + min(vs)) * 0.5
    # one big curve mustn't swamp the page: no button bigger than ~2.5x the usual one
    sizes = sorted(max(max(p[0] for p in r["pts"]) - min(p[0] for p in r["pts"]),
                       max(p[1] for p in r["pts"]) - min(p[1] for p in r["pts"])) * scale for r in rig)
    usual = sizes[len(sizes) // 2] if sizes else MIN_SIZE
    cap = max(MIN_SIZE * 1.6, usual * 2.5)
    max_w, max_h = min(max_w, cap), min(max_h, cap)
    items = [_item(r, scale, cu, cv, width * 0.5, max_w, max_h) for r in rig]
    _pair_up(items)
    relax(items, width, symmetric=(view == "front"))
    w, h, dx, dy = _fit_shift(items, width)
    sil = silhouette(outline, view, scale, cu, cv, width * 0.5, dx, dy) if outline else None
    if sil:
        _last_outline[0] = sil
    return items, w, h


_last_outline = [None]       # the last layout's silhouette (auto() puts it on the page)


def silhouette(points, view, scale, cu, cv, center_x, dx, dy, cell=4.0):
    """The meshes seen in the view as rows of filled cells on the page: {'cell', 'runs': [[y, x0, x1]...]}."""
    filled = set()
    for p in points:
        u, v = project(p, view)
        x = center_x + (u - cu) * scale + dx
        y = -(v - cv) * scale + dy
        filled.add((int(x // cell), int(y // cell)))
    if not filled:
        return None
    grown = set((x + a, y + b) for x, y in filled for a in (-1, 0, 1) for b in (-1, 0, 1))      # close small gaps
    shut = set(c for c in grown if all((c[0] + a, c[1] + b) in grown for a in (-1, 0, 1) for b in (-1, 0, 1)))
    shut |= filled
    runs = []
    for y in sorted(set(c[1] for c in shut)):
        xs = sorted(c[0] for c in shut if c[1] == y)
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            runs.append([y, start, prev])
            if x is not None:
                start = prev = x
    return {"cell": cell, "runs": runs}


def mesh_points(ns="", limit=20000):
    """World points of the character's skinned meshes (thinned out to about limit)."""
    pts = []
    meshes = []
    for skin in cmds.ls(type="skinCluster") or []:
        for g in cmds.skinCluster(skin, query=True, geometry=True) or []:
            t = (cmds.listRelatives(g, parent=True, fullPath=True) or [g])[0]
            if A.namespace_of(t) == (ns or "") and t not in meshes:
                meshes.append(t)
    for m in meshes:
        try:
            flat = cmds.xform(m + ".vtx[*]", query=True, worldSpace=True, translation=True) or []
        except (RuntimeError, ValueError, TypeError):
            continue
        pts += [tuple(flat[i:i + 3]) for i in range(0, len(flat) - 2, 3)]
    step = max(1, len(pts) // limit)
    return pts[::step]


def _inside(points, rig, grow=0.15):
    """The points inside the controls' 3D box (grown a little): the face's part of the meshes."""
    pos = [r["pos"] for r in rig if len(r.get("pos") or []) > 2]
    if not pos or not points:
        return []
    lo = [min(p[k] for p in pos) for k in range(3)]
    hi = [max(p[k] for p in pos) for k in range(3)]
    pad = [max((hi[k] - lo[k]) * grow, 1e-3) for k in range(3)]
    return [p for p in points if all(lo[k] - pad[k] <= p[k] <= hi[k] + pad[k] for k in range(3))]


def _finger_of(name):
    low = name.lower()
    for i, f in enumerate(FINGERS):
        if f in low or (f == "pinky" and "pinkie" in low):
            return i
    m = re.search(r"(finger|fing|digit)_?(\d+)", low)
    if m:
        return 5 + int(m.group(2))
    return 99                                                # a hand control (cup, spread...)


def layout_hands(rig, width=PAGE_W, cell=(34.0, 26.0)):
    """The fingers as a grid: a column per finger (thumb inside), knuckle at the top; the character's left hand on
    the right of the page (as seen from the front)."""
    cw, ch = cell
    items = []
    for side, x_mid, out in (("L", width * 0.75, 1), ("R", width * 0.25, -1)):
        mine = [r for r in rig if r["side"] == side] or ([r for r in rig if r["side"] == "C"] if side == "L" else [])
        columns = {}
        extras = []
        for r in mine:
            f = _finger_of(strip(r["node"]))
            if f == 99:
                extras.append(r)
            else:
                columns.setdefault(f, []).append(r)
        keys = sorted(columns)
        total = len(keys) * cw
        for ci, f in enumerate(keys):
            col = sorted(columns[f], key=lambda r: (r["depth"], strip(r["node"])))
            cx = x_mid - out * total * 0.5 + out * (ci + 0.5) * cw
            for ri, r in enumerate(col):
                y = MARGIN + 34 + (ri + (1 if f == 0 else 0)) * ch
                items.append({"id": new_id(), "kind": "select", "nodes": [strip(r["node"])], "x": cx - (cw - 4) / 2,
                              "y": y, "w": cw - 4, "h": ch - 4, "shape": "round", "points": [],
                              "rgb": [round(c, 3) for c in r["rgb"]], "label": label_of(r["node"]), "twin": None,
                              "_side": side, "_twin_node": strip(r["twin"]) if r.get("twin") else None,
                              "_area": cw * ch})
        for ei, r in enumerate(extras):
            x = x_mid - out * total * 0.5 + out * ei * (cw * 1.5)
            items.append({"id": new_id(), "kind": "select", "nodes": [strip(r["node"])],
                          "x": x if out > 0 else x - cw * 1.5 + 4, "y": MARGIN, "w": cw * 1.5 - 4, "h": ch - 4,
                          "shape": "round", "points": [], "rgb": [round(c, 3) for c in r["rgb"]],
                          "label": label_of(r["node"]), "twin": None, "_side": side,
                          "_twin_node": strip(r["twin"]) if r.get("twin") else None, "_area": cw * ch})
    _pair_up(items)
    relax(items, width)
    w, h = _fit(items, width)
    return items, w, h


def fingers_beside_hands(body_items, hands, scale=0.5):
    """Small copies of each hand's finger grid under that side's hand / wrist button on the Body page."""
    out = []
    for side in ("L", "R"):
        anchor = [i for i in body_items if i.get("_side") == side and _has(i["nodes"][0], ["hand", "wrist", "palm"])]
        mine = [r for r in hands if r["side"] == side]
        if not anchor or not mine:
            continue
        hand = [i for i in anchor if "hand" in i["nodes"][0].lower()]
        a = max(hand or anchor, key=lambda i: i["y"])           # the lowest: nearest the fingers
        grid, _w, _h = layout_hands(mine)
        grid = [g for g in grid if g.get("_side") == side]
        if not grid:
            continue
        x0, y0, x1, _y1 = bounds(grid)
        cx = a["x"] + a["w"] * 0.5
        for g in grid:
            g = dict(g)
            g["id"] = new_id()
            g["x"] = cx + (g["x"] - (x0 + x1) * 0.5) * scale
            g["y"] = a["y"] + a["h"] + 4 + (g["y"] - y0) * scale
            g["w"], g["h"] = g["w"] * scale, g["h"] * scale
            g["label"] = ""                                  # too small to read: the tooltip names it
            g["twin"] = None
            out.append(g)
    return out


def auto(ns=None, rig=None, points=None, exclude=None):
    """A new picker for the character, laid out automatically: front view for an upright character, a three-
    quarter side view for a four-legged one; the face from the front; the body's silhouette behind the buttons.
    exclude (5.6.23): control names left out (kept on the new picker)."""
    ns = A.current_character() if ns is None else ns
    rig = read_rig(ns) if rig is None else rig
    if exclude:
        rig = [r for r in rig if strip(r["node"]) not in set(exclude)]
    view = pick_view(rig)
    if points is None:
        try:
            points = mesh_points(ns)
        except Exception:
            points = []
    pages = []
    pages_in = classify(rig, ns)
    for name, group in ((n, g) for n, g in pages_in.items()):
        if not group and name != "Body":
            continue
        _last_outline[0] = None
        if name == "Hands":
            items, w, h = layout_hands(group)
        elif name in ("Body", "Clothes"):
            items, w, h = layout_view(group, view=view, outline=points if name == "Body" else None)
        elif name == "Face":                                # the face looks forward
            items, w, h = layout_view(group, max_w=PAGE_W * 0.2, max_h=PAGE_W * 0.12,
                                      outline=_inside(points, group))
        else:                                               # tweaks: small controls, smaller buttons
            items, w, h = layout_view(group, max_w=PAGE_W * 0.2, max_h=PAGE_W * 0.12, view=view)
        if name == "Body" and pages_in.get("Hands"):            # 5.6.21: small finger buttons beside each hand
            items += fingers_beside_hands(items, pages_in["Hands"])
            w, h = max(w, bounds(items)[2] + MARGIN), max(h, bounds(items)[3] + MARGIN)
        _clean(items)
        page = {"name": name, "width": round(w, 1), "height": round(h, 1), "bg": "", "items": items}
        if _last_outline[0]:
            page["outline"] = _last_outline[0]
        pages.append(page)
    out = {"version": VERSION, "pages": pages, "view": view}
    if exclude:
        out["exclude"] = sorted(set(exclude))
    return out


# ===========================================================================
# saved pickers (in the rig profile)
# ===========================================================================

RIG_ATTR = "gusPicker"


def rig_node(ns=None):
    """The node the rig's own picker is kept on: the rig's top group (the one most of its controls are under)."""
    ns = A.current_character() if ns is None else ns
    found = cmds.ls(ns + "rig_grp", long=True) or []
    if found:
        return found[0]
    tops = {}
    for c in A.character_controls(ns):
        top = "|" + c.strip("|").split("|")[0]
        tops[top] = tops.get(top, 0) + 1
    return max(tops, key=tops.get) if tops else None


def rig_editable(ns=None):
    """True in the rig's own file (its top group isn't referenced): Save keeps the picker IN the rig."""
    node = rig_node(ns)
    if not node:
        return False
    try:
        return not cmds.referenceQuery(node, isNodeReferenced=True)
    except RuntimeError:
        return True


def _valid(picker):
    return isinstance(picker, dict) and picker.get("version") == VERSION and bool(picker.get("pages"))


def rig_picker(ns=None):
    """The picker saved inside the rig (by the rigger), or None."""
    import json
    node = rig_node(ns)
    if not node or not cmds.attributeQuery(RIG_ATTR, node=node, exists=True):
        return None
    try:
        got = json.loads(cmds.getAttr(node + "." + RIG_ATTR) or "{}")
    except (ValueError, RuntimeError, TypeError):
        return None
    return got if _valid(got) else None


def own_picker(ns=None):
    """The picker you saved on this computer for this rig (your edits), or None."""
    saved = A.profile(ns).get("picker")
    return saved if _valid(saved) else None


def where_from(ns=None):
    """'yours' (saved on this computer), 'rig' (saved in the rig) or 'auto'."""
    return "yours" if own_picker(ns) else ("rig" if rig_picker(ns) else "auto")


def load(ns=None, make=True):
    """Your own saved picker for the rig, else the one saved in the rig, else (make) a new automatic one."""
    saved = own_picker(ns) or rig_picker(ns)
    if saved:
        picker = copy.deepcopy(saved)
        _sync_ids(picker)
        return picker
    return auto(ns) if make else None


def save_in_rig(picker, ns=None):
    """Keep the picker in the rig itself (its top group): every scene that references the rig gets it."""
    import json
    node = rig_node(ns)
    if not node:
        raise RuntimeError("no controls found for this character.")
    if not rig_editable(ns):
        raise RuntimeError("this rig is referenced: open the rig's own file to save the picker into it.")
    locked = cmds.lockNode(node, query=True, lock=True)[0]
    if locked:
        cmds.lockNode(node, lock=False)
    try:
        if not cmds.attributeQuery(RIG_ATTR, node=node, exists=True):
            cmds.addAttr(node, longName=RIG_ATTR, dataType="string")
        cmds.setAttr(node + "." + RIG_ATTR, json.dumps(picker), type="string")
    finally:
        if locked:
            cmds.lockNode(node, lock=True)
    return node


def save(picker, ns=None):
    """Save: in the rig's own file the picker goes INTO the rig (and any personal copy for it is dropped, so you
    see what everyone gets); with a referenced rig it's yours, on this computer. Returns 'rig' or 'yours'."""
    if rig_editable(ns):
        save_in_rig(picker, ns)
        if own_picker(ns):
            forget(ns)
        return "rig"
    data = dict(A.profile(ns))
    data["picker"] = copy.deepcopy(picker)
    A.save_profile(data, ns)
    return "yours"


def export_file(picker, path):
    import json
    with open(path, "w") as f:
        json.dump({"gusPickerFile": 1, "picker": picker}, f, indent=1)
    return path


def import_file(path):
    import json
    with open(path) as f:
        data = json.load(f)
    picker = data.get("picker") if isinstance(data, dict) else None
    if not _valid(picker):
        raise RuntimeError("that file isn't a Gus Animtool picker.")
    picker = copy.deepcopy(picker)
    _sync_ids(picker)
    return picker


NEW_PAGE = "New controls"


def missing(picker, ns=None):
    """The character's controls that no button selects (made after the picker was saved)."""
    ns = A.current_character() if ns is None else ns
    have = {n for page in picker.get("pages", []) for it in page.get("items", []) for n in it.get("nodes", [])}
    have |= set(excluded(picker))                       # 5.6.23: the ones you took out stay out
    return [c for c in A.character_controls(ns) if strip(c) not in have]


def add_missing(picker, ns=None):
    """A button for each missing control, laid out from the front on their own page ('New controls'); the
    pages you edited stay as they are. Returns how many were added."""
    ns = A.current_character() if ns is None else ns
    nodes = set(missing(picker, ns))
    if not nodes:
        return 0
    group = [r for r in read_rig(ns) if r["node"] in nodes]
    items, w, h = layout_view(group, view=picker.get("view", "front"))
    _clean(items)
    pages = [p for p in picker["pages"] if p["name"] == NEW_PAGE]
    if pages:
        page = pages[0]
        dy = (bounds(page["items"])[3] + 20.0) if page["items"] else 0.0
        for it in items:
            it["y"] += dy
        page["items"] += items
        page["height"] = round(max(page.get("height", 0.0), h + dy), 1)
        page["width"] = round(max(page.get("width", 0.0), w), 1)
    else:
        picker["pages"].append({"name": NEW_PAGE, "width": round(w, 1), "height": round(h, 1), "bg": "",
                                "items": items})
    return len(items)


def forget(ns=None):
    """Back to the automatic picker (the saved one is removed)."""
    data = dict(A.profile(ns))
    data.pop("picker", None)
    A.save_profile(data, ns)


def resolve(item, ns):
    """The item's controls in this character (long names that exist)."""
    out = []
    for n in item.get("nodes") or []:
        got = A.resolve(n, ns or "")
        if got:
            out.append(got)
    return out


# ===========================================================================
# finding / editing (the window calls these)
# ===========================================================================

def hit(page, x, y):
    """The top-most item at (x, y) (the last drawn), or None."""
    for it in reversed(page["items"]):
        if contains(it, x, y):
            return it
    return None


def in_rect(page, x0, y0, x1, y1):
    xa, xb, ya, yb = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    from gus_animtool import pickmore as PX
    off = PX.layer_off(page)
    return [it for it in page["items"] if it["x"] < xb and it["x"] + it["w"] > xa and it["y"] < yb and
            it["y"] + it["h"] > ya and it["id"] not in off]


def by_id(page, ids):
    ids = set(ids)
    return [it for it in page["items"] if it["id"] in ids]


def move(items, dx, dy, grid=0.0):
    for it in items:
        if it.get("locked"):                                # 5.6.21: locked against accidental moves
            continue
        it["x"] += dx
        it["y"] += dy
        if grid:
            it["x"] = round(it["x"] / grid) * grid
            it["y"] = round(it["y"] / grid) * grid


def resize(items, factor=None, w=None, h=None):
    for it in items:
        if it.get("locked"):
            continue
        if is_text(it) and factor:                          # text: the letters grow
            it["size"] = max(4.0, it.get("size", 14.0) * factor)
        cx, cy = it["x"] + it["w"] * 0.5, it["y"] + it["h"] * 0.5
        if factor:
            it["w"], it["h"] = max(6.0, it["w"] * factor), max(6.0, it["h"] * factor)
        if w:
            it["w"] = max(6.0, float(w))
        if h:
            it["h"] = max(6.0, float(h))
        it["x"], it["y"] = cx - it["w"] * 0.5, cy - it["h"] * 0.5


def set_value(items, key, value):
    for it in items:
        it[key] = copy.deepcopy(value)
        if key == "shape" and value != "poly":
            it["points"] = []


def align(items, how):
    """how: left, right, top, bottom, hcenter (one column), vcenter (one row)."""
    if len(items) < 2:
        return
    if how == "left":
        v = min(i["x"] for i in items)
        for i in items:
            i["x"] = v
    elif how == "right":
        v = max(i["x"] + i["w"] for i in items)
        for i in items:
            i["x"] = v - i["w"]
    elif how == "top":
        v = min(i["y"] for i in items)
        for i in items:
            i["y"] = v
    elif how == "bottom":
        v = max(i["y"] + i["h"] for i in items)
        for i in items:
            i["y"] = v - i["h"]
    elif how == "hcenter":
        v = sum(i["x"] + i["w"] * 0.5 for i in items) / len(items)
        for i in items:
            i["x"] = v - i["w"] * 0.5
    elif how == "vcenter":
        v = sum(i["y"] + i["h"] * 0.5 for i in items) / len(items)
        for i in items:
            i["y"] = v - i["h"] * 0.5


def distribute(items, axis="x"):
    """Even spacing between the first and the last (left to right, or top to bottom)."""
    if len(items) < 3:
        return
    key, size = ("x", "w") if axis == "x" else ("y", "h")
    order = sorted(items, key=lambda i: i[key])
    first = order[0][key] + order[0][size] * 0.5
    last = order[-1][key] + order[-1][size] * 0.5
    for n, it in enumerate(order):
        it[key] = first + (last - first) * n / (len(order) - 1) - it[size] * 0.5


def _edges(box, axis):
    """(start, centre, end) of a box (x0, y0, x1, y1) along x or y."""
    a, b = (box[0], box[2]) if axis == "x" else (box[1], box[3])
    return a, (a + b) * 0.5, b


def snap(moving, others, dx, dy, tol=6.0):
    """Moving buttons by (dx, dy): pull the move so their box lines up (edges or centres) with a nearby
    button's, when within tol. Returns (dx, dy, guides) - guides: [('v', x, y0, y1) | ('h', y, x0, x1)] to draw."""
    if not moving or not others:
        return dx, dy, []
    b = bounds(moving)
    box = (b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)
    out, guides = {"x": dx, "y": dy}, []
    for axis in ("x", "y"):
        best = None
        for o in others:
            ob = (o["x"], o["y"], o["x"] + o["w"], o["y"] + o["h"])
            for m in _edges(box, axis):
                for t in _edges(ob, axis):
                    d = t - m
                    if abs(d) <= tol and (best is None or abs(d) < abs(best[0])):
                        best = (d, t, ob)
        if best is not None:
            out[axis] += best[0]
            d, t, ob = best
            if axis == "x":
                guides.append(("v", t, min(box[1] + (out["y"] - dy), ob[1]), max(box[3] + (out["y"] - dy), ob[3])))
            else:
                guides.append(("h", t, min(box[0] + (out["x"] - dx), ob[0]), max(box[2] + (out["x"] - dx), ob[2])))
    return out["x"], out["y"], guides


def same_size(items, ref):
    """Every item the size of ref."""
    for it in items:
        it["w"], it["h"] = ref["w"], ref["h"]


def space(items, gap, axis="x"):
    """In a row (x) or a column (y), gap apart (page units), from the first one (left- / top-most); the other
    direction stays as it is."""
    if len(items) < 2:
        return
    key, size = ("x", "w") if axis == "x" else ("y", "h")
    order = sorted(items, key=lambda i: i[key])
    at = order[0][key] + order[0][size]
    for it in order[1:]:
        it[key] = at + gap
        at = it[key] + it[size]


def add_items(page, nodes, x=None, y=None, size=24.0):
    """A button per control (in a row from x, y). Returns the new items."""
    x0 = MARGIN if x is None else x
    y0 = (bounds(page["items"])[3] + 10) if (y is None and page["items"]) else (MARGIN if y is None else y)
    made = []
    for n in nodes:
        made.append({"id": new_id(), "kind": "select", "nodes": [strip(n)], "x": x0 + len(made) * (size + 4),
                     "y": y0, "w": size, "h": size, "shape": "round", "points": [], "rgb": A._colour(n),
                     "label": label_of(n), "twin": None})
    page["items"] += made
    return made


def add_group_button(page, nodes, label, x=None, y=None):
    """One button selecting several controls."""
    it = add_items(page, nodes[:1], x, y)[0]
    it["nodes"] = [strip(n) for n in nodes]
    it["label"] = label
    it["w"] = max(60.0, 8.0 * len(label))
    return it


def add_widget(page, kind, node, attr, x=None, y=None):
    """A slider (numbers) or a check box (on / off) driving node.attr."""
    it = add_items(page, [node], x, y)[0]
    lo, hi = 0.0, 1.0
    try:
        if cmds.attributeQuery(attr, node=node, minExists=True):
            lo = cmds.attributeQuery(attr, node=node, minimum=True)[0]
        if cmds.attributeQuery(attr, node=node, maxExists=True):
            hi = cmds.attributeQuery(attr, node=node, maximum=True)[0]
        elif kind == "slider":
            hi = 10.0
    except (RuntimeError, TypeError, IndexError):
        pass
    it.update({"kind": kind, "attr": attr, "min": lo, "max": hi, "shape": "rect", "label": attr,
               "w": 120.0 if kind == "slider" else 22.0, "h": 18.0 if kind == "slider" else 22.0})
    if kind == "toggle":                                # 5.6.23: one click flips it, the colour says on / off
        it.update({"shape": "pill", "w": max(56.0, 7.5 * len(attr) + 16.0), "h": 22.0,
                   "on_rgb": [0.36, 0.78, 0.45], "rgb": [0.32, 0.33, 0.36]})
    return it


def add_command(page, label, code, x=None, y=None):
    it = {"id": new_id(), "kind": "command", "nodes": [], "x": MARGIN if x is None else x,
          "y": (bounds(page["items"])[3] + 10) if (y is None and page["items"]) else (MARGIN if y is None else y),
          "w": max(60.0, 8.0 * len(label)), "h": 24.0, "shape": "rect", "points": [], "rgb": [0.35, 0.37, 0.4],
          "label": label, "twin": None, "code": code}
    page["items"].append(it)
    return it


# ===========================================================================
# 5.6.21: frames (groups with a title), text, order, lock, style
# ===========================================================================

def is_frame(it):
    return it.get("kind") == "frame"


def is_text(it):
    return it.get("kind") == "text"


def group_frame(page, items, title="Group", pad=8.0):
    """A frame round the items: a rounded panel with a title bar, behind every button."""
    items = [i for i in items if not is_frame(i)]
    if not items:
        raise RuntimeError("pick the buttons to group first.")
    x0, y0, x1, y1 = bounds(items)
    fr = {"id": new_id(), "kind": "frame", "nodes": [], "x": x0 - pad, "y": y0 - pad - TITLE_H,
          "w": x1 - x0 + pad * 2, "h": y1 - y0 + pad * 2 + TITLE_H, "shape": "rect", "points": [],
          "rgb": [0.33, 0.45, 0.6], "alpha": 0.35, "label": title or "Group", "twin": None, "hidden": False}
    page["items"].insert(0, fr)
    return fr


def frame_members(page, frame):
    """The buttons (not frames) whose middle is inside the frame."""
    out = []
    for it in page["items"]:
        if it is frame or is_frame(it):
            continue
        cx, cy = it["x"] + it["w"] * 0.5, it["y"] + it["h"] * 0.5
        if frame["x"] <= cx <= frame["x"] + frame["w"] and frame["y"] <= cy <= frame["y"] + frame["h"]:
            out.append(it)
    return out


TITLE_PLACES = ("bar", "above", "inside", "below", "hidden")      # 5.6.24: where a frame's title goes
TITLE_SIZE = 11.0


def title_h(frame):
    """5.6.24: the title bar's height - grows with the title's size."""
    ts = float(frame.get("text_size") or 0.0)
    return max(TITLE_H, ts * 1.5) if ts else TITLE_H


def title_rect(frame):
    """(x, y, w, h) of the frame's title on the page (where it's clicked), or None when hidden."""
    from gus_animtool import pickmore as PX              # 5.6.26: where the title is drawn (any place)
    place = PX.text_place(frame)
    h = title_h(frame)
    if place == "hidden":
        return None
    if place == "bar":
        return frame["x"], frame["y"], frame["w"], h
    size = float(frame.get("text_size") or TITLE_SIZE)
    tw = max(20.0, len(frame.get("label") or "") * size * 0.62 + 10.0)
    th = size * 1.5
    x0, y0, _a = PX.text_box(place, frame["x"], frame["y"], frame["x"] + frame["w"], frame["y"] + frame["h"],
                             tw, th, 3.0)
    return x0 + float(frame.get("tdx") or 0.0), y0 + float(frame.get("tdy") or 0.0), tw, th


def on_title(frame, x, y):
    r = title_rect(frame)
    return bool(r) and r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]


def hidden_ids(page):
    """Ids of hidden frames and of the buttons in them."""
    out = set()
    for fr in page["items"]:
        if is_frame(fr) and fr.get("hidden"):
            out.add(fr["id"])
            out.update(i["id"] for i in frame_members(page, fr))
    return out


def hit_any(page, x, y, editing=False):
    """5.6.21 hit: the top-most button / text; else a frame - in use only by its title bar (it selects its
    controls), in edit mode anywhere on it. Hidden frames (and their buttons) only in edit mode."""
    hidden = set() if editing else hidden_ids(page)
    from gus_animtool import pickmore as PX              # 5.6.25: hidden layers; locked ones while editing
    hidden = hidden | PX.layer_off(page) | (PX.layer_locked(page) if editing else set()) | PX.folded_ids(page)
    for it in reversed(page["items"]):                   # 5.6.26: buttons first - a text never blocks one
        if is_frame(it) or is_text(it) or it["id"] in hidden:
            continue
        if contains(it, x, y):
            return it
    if editing:                                          # texts: picked in Edit; animating, they do nothing
        for it in reversed(page["items"]):
            if is_text(it) and it["id"] not in hidden and contains(it, x, y):
                return it
    for it in reversed(page["items"]):
        if not is_frame(it) or it["id"] in hidden:
            continue
        if on_title(it, x, y) or (editing and contains(it, x, y)):
            return it
    return None


def ungroup(page, frames):
    gone = set(f["id"] for f in frames if is_frame(f))
    page["items"] = [i for i in page["items"] if i["id"] not in gone]
    if page.get("links"):
        page["links"] = [ln for ln in page["links"] if ln["a"] not in gone and ln["b"] not in gone]
    return len(gone)


def _frames_first(page):
    page["items"] = [i for i in page["items"] if is_frame(i)] + [i for i in page["items"] if not is_frame(i)]


def order(page, items, how):
    """how: front, back, up, down (one step). Frames stay behind the buttons."""
    ids = set(i["id"] for i in items)
    its = page["items"]
    if how in ("front", "back"):
        moving = [i for i in its if i["id"] in ids]
        rest = [i for i in its if i["id"] not in ids]
        page["items"] = rest + moving if how == "front" else moving + rest
    else:
        rng = range(len(its) - 2, -1, -1) if how == "up" else range(1, len(its))
        for k in rng:
            j = k + 1 if how == "up" else k - 1
            if its[k]["id"] in ids and its[j]["id"] not in ids:
                its[k], its[j] = its[j], its[k]
    _frames_first(page)


def add_text(page, text, x=None, y=None, size=14.0):
    w, h = max(20.0, len(text) * size * 0.62), size * 1.5
    it = {"id": new_id(), "kind": "text", "nodes": [], "x": MARGIN if x is None else x,
          "y": (bounds(page["items"])[3] + 10) if (y is None and page["items"]) else (MARGIN if y is None else y),
          "w": w, "h": h, "shape": "rect", "points": [], "rgb": [0.92, 0.92, 0.92], "label": text, "twin": None,
          "size": size, "bold": True, "align": "center"}
    page["items"].append(it)
    return it


STYLE_KEYS = ("shape", "points", "rgb", "w", "h", "size", "bold", "align", "alpha", "text_size", "text_rgb",
              "label_pos", "border_rgb", "border_w", "corner", "rot")


def copy_style(item):
    return dict((k, copy.deepcopy(item[k])) for k in STYLE_KEYS if k in item)


def paste_style(items, style):
    for it in items:
        for k, v in style.items():
            if k in ("w", "h") and is_text(it) != ("size" in style):
                continue
            if k in ("w", "h"):                              # keep the middle where it was
                c = it["x"] + it["w"] * 0.5 if k == "w" else it["y"] + it["h"] * 0.5
                it[k] = v
                if k == "w":
                    it["x"] = c - v * 0.5
                else:
                    it["y"] = c - v * 0.5
            else:
                it[k] = copy.deepcopy(v)


def centre_on_page(page, items):
    """The picked items, as a block, in the middle of the page (across)."""
    if not items:
        return
    x0, _y0, x1, _y1 = bounds(items)
    dx = page.get("width", PAGE_W) * 0.5 - (x0 + x1) * 0.5
    move(items, dx, 0)


def move_to_page(picker, src, items, name):
    """The items to the page called name (made when missing) - same place and look. Returns that page."""
    dst = [p for p in picker["pages"] if p["name"] == name]
    dst = dst[0] if dst else add_page(picker, name)
    if dst is src:
        return dst
    ids = set(i["id"] for i in items)
    moving = [i for i in src["items"] if i["id"] in ids]
    src["items"] = [i for i in src["items"] if i["id"] not in ids]
    for i in moving:
        if i.get("twin") and i["twin"] not in ids:
            i["twin"] = None
    dst["items"] += moving
    _frames_first(dst)
    return dst


def delete(page, items):
    gone = set(i["id"] for i in items)
    page["items"] = [i for i in page["items"] if i["id"] not in gone]
    for i in page["items"]:
        if i.get("twin") in gone:
            i["twin"] = None
    if page.get("links"):                                 # 5.6.25: their connectors go too
        page["links"] = [ln for ln in page["links"] if ln["a"] not in gone and ln["b"] not in gone]


def duplicate(page, items, dx=12.0, dy=12.0):
    made = []
    for it in items:
        new = copy.deepcopy(it)
        new["id"] = new_id()
        new["twin"] = None
        new["x"] += dx
        new["y"] += dy
        made.append(new)
    page["items"] += made
    _frames_first(page)
    return made


def mirror(page, items, ns=""):
    """Each item gets (or updates) its twin on the other side of the page: mirrored place and shape, the
    controls' mirrored names. Returns the twins."""
    width = page.get("width", PAGE_W)
    ids = {i["id"]: i for i in page["items"]}
    out = []
    for it in items:
        names = []
        for n in it.get("nodes") or []:
            m = A.mirror_name(n)
            if m and A.resolve(strip(m), ns or ""):
                names.append(strip(m))
                continue
            ln = A.resolve(n, ns or "")                 # 5.6.24: no mirrored name - its twin (link / position)
            tw = A.twin_of(ln) if ln else None
            names.append(strip(tw) if tw else (strip(m) if m else n))
        if it.get("nodes") and names == list(it["nodes"]):
            continue                              # 5.6.22: a middle control has no twin (5.6.21 made a second button)
        twin = ids.get(it.get("twin") or "")
        if twin is None:
            twin = copy.deepcopy(it)
            twin["id"] = new_id()
            page["items"].append(twin)
            ids[twin["id"]] = twin
        for k in ("kind", "shape", "label", "attr", "min", "max", "code"):
            if k in it:
                twin[k] = copy.deepcopy(it[k])
        twin["nodes"] = names
        _mirror_into(it, twin, width)
        twin["twin"], it["twin"] = it["id"], twin["id"]
        node = resolve(twin, ns)
        if node and twin.get("kind") == "select":
            twin["rgb"] = A._colour(node[0])
        out.append(twin)
    return out


def add_page(picker, name):
    name = (name or "").strip() or "Page %d" % (len(picker["pages"]) + 1)
    page = {"name": name, "width": PAGE_W, "height": PAGE_W * 1.4, "bg": "", "items": []}
    picker["pages"].append(page)
    return page


def page_size(page):
    """The page's size including every item (items moved past the edge grow it)."""
    x0, y0, x1, y1 = bounds(page["items"])
    return max(page.get("width", PAGE_W), x1 + MARGIN), max(page.get("height", PAGE_W), y1 + MARGIN)


class History(object):
    """Undo / redo for edit mode (whole picker snapshots)."""

    def __init__(self, limit=50):
        self.limit = limit
        self.undos, self.redos = [], []
        self.notes = []                                   # 5.6.26: (time, what) of each undo step

    def push(self, picker, note=""):
        import time
        self.undos.append(copy.deepcopy(picker))
        self.notes.append((time.strftime("%H:%M:%S"), note or "edit"))
        self.undos = self.undos[-self.limit:]
        self.notes = self.notes[-self.limit:]
        self.redos = []

    def steps(self):
        """[(time, what)] of the undo steps, the newest last."""
        return list(self.notes[-len(self.undos):]) if self.undos else []

    def back_to(self, picker, k):
        """Undo until k steps are left (k < len(undos)): the picker then, or None."""
        got = None
        while len(self.undos) > max(0, k):
            got = self.undo(picker if got is None else got)
        return got

    def undo(self, picker):
        if not self.undos:
            return None
        self.redos.append(copy.deepcopy(picker))
        if len(self.notes) >= len(self.undos):
            self.notes.pop()
        return self.undos.pop()

    def redo(self, picker):
        if not self.redos:
            return None
        import time
        self.undos.append(copy.deepcopy(picker))
        self.notes.append((time.strftime("%H:%M:%S"), "redo"))
        return self.redos.pop()


# ===========================================================================
# 5.6.22: clean-up, 2D sliders, pins, style presets
# ===========================================================================

def duplicates(picker):
    """[(page, item)] - a second button on the same page selecting exactly the same controls (the first stays)."""
    out = []
    for page in picker.get("pages", []):
        seen = set()
        for it in page.get("items", []):
            if it.get("kind") != "select" or not it.get("nodes"):
                continue
            key = tuple(sorted(it["nodes"]))
            if key in seen:
                out.append((page, it))
            seen.add(key)
    return out


def stale(picker, ns=""):
    """[(page, item)] - select buttons none of whose controls exist (a board taken away...)."""
    return [(page, it) for page in picker.get("pages", []) for it in page.get("items", [])
            if it.get("kind") == "select" and it.get("nodes") and not resolve(it, ns)]


def cleanup(picker, ns=""):
    """The duplicates and the stale buttons go. Returns (duplicates, stale) - how many."""
    dup, old = duplicates(picker), stale(picker, ns)
    gone = set(id(it) for _p, it in dup + old)
    for page in picker.get("pages", []):
        page["items"] = [i for i in page["items"] if id(i) not in gone]
    return len(dup), len(set(id(it) for _p, it in old) - set(id(it) for _p, it in dup))


def add_slider2d(page, node, attr_x, attr_y, x=None, y=None):
    """A square pad: its handle drives two attributes (across: attr_x, up: attr_y) - eyes, mouth corners."""
    it = add_items(page, [node], x, y)[0]
    rng = []
    for attr in (attr_x, attr_y):
        lo, hi = -1.0, 1.0
        try:
            if cmds.attributeQuery(attr, node=node, minExists=True):
                lo = cmds.attributeQuery(attr, node=node, minimum=True)[0]
            if cmds.attributeQuery(attr, node=node, maxExists=True):
                hi = cmds.attributeQuery(attr, node=node, maximum=True)[0]
        except (RuntimeError, TypeError, IndexError):
            pass
        rng.append((lo, hi))
    it.update({"kind": "slider2d", "attr_x": attr_x, "attr_y": attr_y, "min_x": rng[0][0], "max_x": rng[0][1],
               "min_y": rng[1][0], "max_y": rng[1][1], "shape": "rect", "label": "", "w": 60.0, "h": 60.0})
    return it


def slider2d_value(item, ns):
    """(fraction across, fraction up) 0..1, or None."""
    nodes = resolve(item, ns)
    if not nodes:
        return None
    out = []
    for k in ("x", "y"):
        try:
            v = float(cmds.getAttr(nodes[0] + "." + item["attr_" + k]))
        except (RuntimeError, ValueError, TypeError, KeyError):
            return None
        lo, hi = float(item.get("min_" + k, -1.0)), float(item.get("max_" + k, 1.0))
        out.append(0.0 if hi == lo else max(0.0, min(1.0, (v - lo) / (hi - lo))))
    return tuple(out)


def set_slider2d(item, ns, fx, fy):
    for n in resolve(item, ns):
        for k, f in (("x", fx), ("y", fy)):
            lo, hi = float(item.get("min_" + k, -1.0)), float(item.get("max_" + k, 1.0))
            plug = n + "." + item["attr_" + k]
            if A._settable(plug):
                cmds.setAttr(plug, lo + (hi - lo) * max(0.0, min(1.0, f)))


def reset_slider2d(item, ns):
    for n in resolve(item, ns):
        for k in ("x", "y"):
            plug = n + "." + item["attr_" + k]
            lo, hi = float(item.get("min_" + k, -1.0)), float(item.get("max_" + k, 1.0))
            if A._settable(plug):
                cmds.setAttr(plug, min(max(0.0, lo), hi))


def styles():
    """Saved style presets {name: style} (on this computer)."""
    try:
        return json.loads(A.opt("picker_styles", "") or "{}")
    except ValueError:
        return {}


def save_style(name, style):
    got = styles()
    got[name] = style
    A.set_opt("picker_styles", json.dumps(got))


def delete_style(name):
    got = styles()
    got.pop(name, None)
    A.set_opt("picker_styles", json.dumps(got))


def slider_value(item, ns):
    nodes = resolve(item, ns)
    if not nodes or not item.get("attr"):
        return None
    try:
        return float(cmds.getAttr(nodes[0] + "." + item["attr"]))
    except (RuntimeError, ValueError, TypeError):
        return None


def set_slider(item, ns, fraction):
    """Set the attribute at fraction (0..1) of the item's range. Returns the value."""
    nodes = resolve(item, ns)
    lo, hi = float(item.get("min", 0.0)), float(item.get("max", 1.0))
    value = lo + (hi - lo) * max(0.0, min(1.0, fraction))
    if item.get("kind") in ("check", "toggle"):
        value = hi if fraction >= 0.5 else lo
    for n in nodes:
        plug = n + "." + item["attr"]
        if A._settable(plug):
            cmds.setAttr(plug, value)
    return value


def toggle(item, ns):
    v = slider_value(item, ns)
    lo, hi = float(item.get("min", 0.0)), float(item.get("max", 1.0))
    return set_slider(item, ns, 0.0 if (v is not None and abs(v - hi) < abs(v - lo)) else 1.0)


# ===========================================================================
# 5.6.23: your preferences (on this computer, never in the rig), label rules, controls in / out, the front
# view, pages, sides, sets, pins
# ===========================================================================

PREFS = {"theme": "dark", "text_scale": 1.0, "compact": False, "sel_rgb": [1.0, 1.0, 1.0], "sel_width": 2.0,
         "sel_fill": True, "hover": "lighter", "hover_rgb": [0.55, 0.85, 1.0], "add_at": "front", "snap": True,
         "grid_size": 8.0, "silhouette": True, "silhouette_alpha": 0.6, "list_shown": False, "list_float": False,
         "lines": True, "keyed": True, "behind": False, "allow_edit": False, "badges": True, "ikfk_fade": True,
         "minimap": True, "shape_favs": [], "shape_recent": [], "panel_open": ["Place & size", "Text", "Connector"], "panel_float": False,
         "side_rgb": {"L": [0.2, 0.4, 1.0], "C": [1.0, 0.85, 0.2], "R": [1.0, 0.25, 0.25]}}
THEMES = {"dark": {"bg": [38, 39, 42], "page": [50, 52, 56], "grid": [90, 94, 102], "shade": [96, 101, 112],
                   "text": [225, 225, 230], "edge": [20, 20, 22]},
          "light": {"bg": [206, 208, 212], "page": [236, 237, 240], "grid": [160, 164, 172], "shade": [214, 217, 224],
                    "text": [30, 30, 34], "edge": [70, 70, 76]},
          "contrast": {"bg": [0, 0, 0], "page": [16, 16, 16], "grid": [130, 130, 130], "shade": [52, 52, 52],
                       "text": [255, 255, 255], "edge": [255, 255, 255]}}
HOVERS = ("lighter", "outline", "both", "none")


def prefs():
    """Your picker settings (text size, theme, toolbar, selected / hover look...): kept on this computer for you,
    never in the rig - every animator sets their own."""
    try:
        got = json.loads(A.opt("picker_prefs", "") or "{}")
    except ValueError:
        got = {}
    out = copy.deepcopy(PREFS)
    if isinstance(got, dict):
        out.update(dict((k, v) for k, v in got.items() if k in PREFS))
    return out


def pref(key):
    return prefs().get(key, PREFS.get(key))


def set_pref(key, value):
    got = prefs()
    got[key] = value
    A.set_opt("picker_prefs", json.dumps(got))


def theme(name=None):
    return THEMES.get(name or pref("theme"), THEMES["dark"])


# -- label rules ---------------------------------------------------------------

LABEL_RULES = {"words": "", "zeros": False, "caps": False}


def label_rules():
    """Your rules for new buttons' text: words taken out (comma list: 'fol, FK, ribbon'), '01' -> '1', Capitals."""
    try:
        got = json.loads(A.opt("picker_label_rules", "") or "{}")
    except ValueError:
        got = {}
    out = dict(LABEL_RULES)
    if isinstance(got, dict):
        out.update(dict((k, v) for k, v in got.items() if k in LABEL_RULES))
    return out


def set_label_rules(rules):
    A.set_opt("picker_label_rules", json.dumps(dict((k, rules.get(k, v)) for k, v in LABEL_RULES.items())))


def apply_rules(text, rules=None):
    """The label after your rules ('Eyelids fol 01' with words 'fol', 01 -> 1, Capitals: 'Eyelids 1')."""
    rules = label_rules() if rules is None else rules
    out = text or ""
    for w in [w.strip().strip("_").replace("_", " ") for w in (rules.get("words") or "").split(",")]:
        if w:
            out = re.sub(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(w), " ", out, flags=re.I)
    if rules.get("zeros"):
        out = re.sub(r"(?<!\d)0+(\d)", r"\1", out)
    out = " ".join(out.split())
    if rules.get("caps"):
        out = " ".join(t[:1].upper() + t[1:] for t in out.split())
    return out or text


def relabel(items):
    """Single-control buttons get their text again from the name (with your rules). Returns how many."""
    n = 0
    for it in items:
        if it.get("kind") == "select" and len(it.get("nodes") or []) == 1:
            it["label"] = label_of(it["nodes"][0])
            n += 1
    return n


# -- controls in / out ---------------------------------------------------------

def excluded(picker):
    """Controls you took out: no button, not counted as missing, left out by Auto layout."""
    return list((picker or {}).get("exclude") or [])


def exclude(picker, nodes):
    """Take controls out: their buttons go (a button for several keeps the others) and they stay out. Returns how
    many buttons went."""
    names = set(strip(n) for n in nodes if n)
    picker["exclude"] = sorted(set(excluded(picker)) | names)
    gone = 0
    for page in picker.get("pages", []):
        keep, ids = [], set()
        for it in page.get("items", []):
            if it.get("kind") == "select" and it.get("nodes"):
                left = [n for n in it["nodes"] if n not in names]
                if not left:
                    ids.add(it["id"])
                    gone += 1
                    continue
                it["nodes"] = left
            keep.append(it)
        page["items"] = keep
        for it in keep:
            if it.get("twin") in ids:
                it["twin"] = None
        if page.get("links"):
            page["links"] = [ln for ln in page["links"] if ln["a"] not in ids and ln["b"] not in ids]
    return gone


def include(picker, nodes):
    """Put taken-out controls back on the list (they show as missing again)."""
    names = set(strip(n) for n in nodes)
    picker["exclude"] = [n for n in excluded(picker) if n not in names]
    if not picker["exclude"]:
        picker.pop("exclude", None)


def on_picker(picker):
    return {n for page in picker.get("pages", []) for it in page.get("items", []) for n in it.get("nodes") or []}


def candidates(picker, ns=None):
    """Curves of the character that aren't found as controls and have no button - hidden for good, no control
    name, nothing to key... You may still want some of them."""
    ns = A.current_character() if ns is None else ns
    have = on_picker(picker) | set(excluded(picker))
    found = set(strip(c) for c in A.character_controls(ns))
    out, seen = [], set()
    for crv in cmds.ls(type="nurbsCurve", long=True, noIntermediate=True) or []:
        if RIDER in crv.split("|")[-1]:
            continue
        t = (cmds.listRelatives(crv, parent=True, fullPath=True) or [None])[0]
        if not t or t in seen or A.namespace_of(t) != ns:
            continue
        seen.add(t)
        b = strip(t)
        if b in have or b in found or cmds.attributeQuery("gusRole", node=t, exists=True):
            continue
        out.append(t)
    from gus_animtool import pickmore                    # 5.6.24: not the display lines (*_line_crv...)
    return pickmore.drop_ignored(out)


def guess_pages(nodes, rig, ns=""):
    """{node: 'Body' | 'Face' | 'Hands' | 'Clothes' | 'Tweaks'} - which page each control would go to."""
    by = classify(rig, ns)
    where = dict((strip(r["node"]), name) for name, g in by.items() for r in g)
    return dict((n, where.get(strip(n), "Body")) for n in nodes)


# -- the front view: where a control sits on a page ------------------------------

def entry_of(node):
    """A control as read_rig sees it (for one control)."""
    pos, size = A._bbox(node)
    pts3 = _outline(node) or [pos]
    return {"node": node, "pos": pos, "pts": [(p[0], p[1]) for p in pts3], "pts3": [tuple(p) for p in pts3],
            "size": size, "rgb": A._colour(node), "side": A.side_of(node), "twin": A.twin_of(node),
            "depth": _depth(node)}


def pos_finder(ns=""):
    """name -> its control's middle in the world (front view: x, y), or None."""
    def get(name):
        got = A.resolve(name, ns or "")
        return A._bbox(got)[0] if got else None
    return get


def fit_view(items, pos_of):
    """(a, b, c) with page x = a.X + b and page y = -a.Y + c: how the page's buttons sit compared with their
    controls seen from the front (least squares). None with fewer than two buttons to go by."""
    pairs = []
    for it in items:
        if it.get("kind") not in ("select", "toggle", "check", "slider") or len(it.get("nodes") or []) != 1 or \
                it.get("pin"):
            continue
        p = pos_of(it["nodes"][0])
        if p is None:
            continue
        pairs.append((p[0], p[1], it["x"] + it["w"] * 0.5, it["y"] + it["h"] * 0.5))
    if len(pairs) < 2:
        return None
    n = float(len(pairs))
    mx, my = sum(q[0] for q in pairs) / n, sum(q[1] for q in pairs) / n
    mpx, mpy = sum(q[2] for q in pairs) / n, sum(q[3] for q in pairs) / n
    den = sum((q[0] - mx) ** 2 + (q[1] - my) ** 2 for q in pairs)
    if den < 1e-12:
        return None
    a = sum((q[0] - mx) * (q[2] - mpx) - (q[1] - my) * (q[3] - mpy) for q in pairs) / den
    if a <= 1e-9:
        return None
    return a, mpx - a * mx, mpy + a * my


def typical_size(items):
    sizes = sorted(max(i["w"], i["h"]) for i in items if i.get("kind") == "select")
    return sizes[len(sizes) // 2] if sizes else 24.0


def settle(movers, fixed, gap=GAP, iterations=300):
    """Nudge the movers until none overlaps another or a fixed one (the fixed ones never move). Returns how many
    overlaps are left."""
    movers = [m for m in movers]
    ids = set(id(m) for m in movers)
    for _ in range(iterations):
        moved = False
        for m in movers:
            for o in fixed + movers:
                if o is m or not overlaps(m, o, gap):
                    continue
                share = 0.5 if id(o) in ids else 1.0
                ox = min(m["x"] + m["w"], o["x"] + o["w"]) - max(m["x"], o["x"]) + gap
                oy = min(m["y"] + m["h"], o["y"] + o["h"]) - max(m["y"], o["y"]) + gap
                if ox < oy:
                    sign = 1.0 if (m["x"] + m["w"] * 0.5) >= (o["x"] + o["w"] * 0.5) else -1.0
                    m["x"] += sign * ox * share
                else:
                    sign = 1.0 if (m["y"] + m["h"] * 0.5) >= (o["y"] + o["h"] * 0.5) else -1.0
                    m["y"] += sign * oy * share
                moved = True
        if not moved:
            return 0
    return sum(1 for m in movers for o in fixed + movers if o is not m and overlaps(m, o))


def _blocking(page, skip=()):
    skip = set(id(s) for s in skip)
    return [i for i in page["items"] if not is_frame(i) and not is_text(i) and id(i) not in skip and
            not i.get("pin")]


def place_front(page, entries, fit, typical=None):
    """Buttons for these controls where they sit seen from the front, on this page's scale (fit), nudged off the
    buttons already there. Returns the new items (added to the page)."""
    a, b, c = fit
    med = typical or typical_size(page["items"])
    cap = max(MIN_SIZE * 1.6, med * 2.5)
    made = []
    for r in entries:
        it = _item(r, a, 0.0, 0.0, b, cap, cap)
        it["y"] += c
        made.append(it)
    _pair_up(made)
    settle(made, _blocking(page))
    _clean(made)
    page["items"] += made
    return made


def add_controls(picker, page, nodes, ns="", at=None, pos_of=None, get_entry=None):
    """Buttons for these controls on the page: at (x, y) in a row, or (at None) where they sit seen from the
    front, on the page's own scale - worked out from the buttons already there. Controls already on the page are
    skipped; taken-out ones are put back. Returns the new items."""
    have = set(n for it in page["items"] for n in it.get("nodes") or [])
    todo, seen = [], set()
    for n in nodes:
        b = strip(n)
        if b not in have and b not in seen:
            todo.append(n)
            seen.add(b)
    if not todo:
        return []
    include(picker, todo)
    if at is not None:
        return add_items(page, todo, at[0], at[1])
    pos_of = pos_of or pos_finder(ns)
    get_entry = get_entry or entry_of
    entries = [get_entry(n) for n in todo]
    fit = fit_view(page["items"], pos_of)
    if fit is not None:
        return place_front(page, entries, fit)
    items, w, h = layout_view(entries, width=page.get("width", PAGE_W))   # an empty page: laid out on its own
    _clean(items)
    if page["items"]:
        dy = bounds(page["items"])[3] + 20.0
        for it in items:
            it["y"] += dy
    settle(items, _blocking(page))
    page["items"] += items
    page["width"] = round(max(page.get("width", 0.0), w), 1)
    return items


def page_named(picker, name):
    got = [p for p in picker.get("pages", []) if p["name"] == name]
    return got[0] if got else None


def add_to_pages(picker, nodes, ns="", rig=None, page=None, pos_of=None):
    """Missing controls onto their own page (Face, Clothes... found the way Auto layout finds them; fingers on
    Body when there's no Hands page; a page made when there's none) - or all onto page. Returns {page: n}."""
    if not nodes:
        return {}
    if page is not None:
        return {page["name"]: len(add_controls(picker, page, nodes, ns, pos_of=pos_of))}
    rig = read_rig(ns) if rig is None else rig
    by_name = dict((strip(r["node"]), r) for r in rig)
    where = guess_pages(nodes, rig, ns)
    groups = {}
    for n in nodes:
        groups.setdefault(where[n], []).append(n)
    out = {}
    for name in sorted(groups):
        pg = page_named(picker, name) or (page_named(picker, "Body") if name == "Hands" else None) or \
            add_page(picker, name)
        got = add_controls(picker, pg, groups[name], ns, pos_of=pos_of,
                           get_entry=lambda n: by_name.get(strip(n)) or entry_of(n))
        out[pg["name"]] = out.get(pg["name"], 0) + len(got)
    return out


def arrange_front(page, items, pos_of):
    """The buttons where their controls sit seen from the front - the page's scale kept (worked out from these
    buttons, else the page's) - then nudged apart; locked and pinned ones stay. Returns how many moved."""
    movable = [i for i in items if i.get("nodes") and not i.get("locked") and not i.get("pin") and
               i.get("kind") in ("select", "slider", "check", "toggle", "slider2d")]
    fit = fit_view(movable, pos_of) or fit_view(page["items"], pos_of)
    if fit is None:
        raise RuntimeError("the front view needs at least two buttons whose controls are in the scene.")
    a, b, c = fit
    done = []
    for it in movable:
        ps = [p for p in (pos_of(n) for n in it["nodes"]) if p is not None]
        if not ps:
            continue
        x = sum(p[0] for p in ps) / len(ps)
        y = sum(p[1] for p in ps) / len(ps)
        it["x"], it["y"] = round(a * x + b - it["w"] * 0.5, 1), round(-a * y + c - it["h"] * 0.5, 1)
        done.append(it)
    settle(done, _blocking(page, skip=done))
    for it in done:
        it["x"], it["y"] = round(it["x"], 1), round(it["y"], 1)
    return len(done)


def page_silhouette(page, points, pos_of, cell=4.0):
    """The meshes seen from the front, faint behind the page's buttons, on the page's scale. Returns True when
    there's one."""
    fit = fit_view(page["items"], pos_of)
    if fit is None or not points:
        return False
    a, b, c = fit
    w, h = page_size(page)
    pad = 40.0
    near = [p for p in points if -pad <= a * p[0] + b <= w + pad and -pad <= -a * p[1] + c <= h + pad]
    sil = silhouette(near, "front", a, 0.0, 0.0, b, 0.0, c, cell)
    if not sil:
        return False
    page["outline"] = sil
    return True


# -- pages, sides, sets, pins -------------------------------------------------------

def duplicate_page(picker, index, name=None):
    """A copy of the page right after it ('Face (copy)') - new ids, twins kept within the copy - to try things
    without touching the original. Returns the copy's index."""
    src = picker["pages"][index]
    new = copy.deepcopy(src)
    ids = {}
    for it in new["items"]:
        ids[it["id"]] = new_id()
        it["id"] = ids[it["id"]]
    for it in new["items"]:
        if it.get("twin"):
            it["twin"] = ids.get(it["twin"])
    for ln in new.get("links") or []:                    # 5.6.25: connectors between the copies
        ln["id"] = new_id()
        ln["a"], ln["b"] = ids.get(ln["a"], ln["a"]), ids.get(ln["b"], ln["b"])
    names = set(p["name"] for p in picker["pages"])
    base = (name or "").strip() or "%s (copy)" % src["name"]
    got, k = base, 2
    while got in names:
        got, k = "%s %d" % (base, k), k + 1
    new["name"] = got
    picker["pages"].insert(index + 1, new)
    return index + 1


def side_of_item(it):
    sides = set(A.side_of(n) for n in it.get("nodes") or [])
    return sides.pop() if len(sides) == 1 and None not in sides else "C"


def colour_by_side(items, colours=None):
    """Select buttons coloured by side (your left / middle / right colours). Returns how many."""
    colours = colours or pref("side_rgb")
    n = 0
    for it in items:
        if it.get("kind") != "select" or not it.get("nodes"):
            continue
        side = side_of_item(it)
        it["rgb"] = list(colours.get(side if side in ("L", "R") else "C") or [0.5, 0.5, 0.5])
        n += 1
    return n


def add_set_button(page, items, label):
    """A selection set: one pill-shaped button above the items that selects all their controls."""
    nodes = []
    for it in items:
        if it.get("kind") == "select":
            nodes += [n for n in it.get("nodes") or [] if n not in nodes]
    if not nodes:
        raise RuntimeError("pick the buttons whose controls the set selects.")
    label = (label or "").strip() or "Set"
    x0, y0, x1, _y1 = bounds(items)
    w, h = max(60.0, 7.5 * len(label) + 20.0), 18.0
    it = {"id": new_id(), "kind": "select", "nodes": nodes, "x": round((x0 + x1) * 0.5 - w * 0.5, 1),
          "y": round(y0 - h - 6.0, 1), "w": w, "h": h, "shape": "pill", "points": [], "rgb": [0.42, 0.47, 0.56],
          "label": label, "twin": None, "set": True}
    page["items"].append(it)
    settle([it], _blocking(page, skip=[it]))
    return it


def pinned(picker):
    """[(page, item)] - pinned buttons (they stay still in the window when you zoom or pan)."""
    return [(p, it) for p in picker.get("pages", []) for it in p.get("items", []) if it.get("pin")]


def unpin_all(picker, page=None):
    """Every pin off (on page, or every page): the buttons stay where they are on the page now. Returns how
    many."""
    n = 0
    for p in ([page] if page is not None else picker.get("pages", [])):
        for it in p.get("items", []):
            if it.get("pin"):
                for k in ("pin", "px", "py", "pw", "ph"):
                    it.pop(k, None)
                n += 1
    return n


def report(picker, ns=""):
    """What the picker has and lacks: {'pages': {name: n}, 'missing', 'unsure', 'excluded', 'pinned',
    'duplicates', 'gone'} (control names)."""
    out = {"pages": dict((p["name"], len(p.get("items", []))) for p in picker.get("pages", []))}
    out["missing"] = [strip(n) for n in missing(picker, ns)]
    try:
        out["unsure"] = [strip(n) for n in candidates(picker, ns)]
    except Exception:
        out["unsure"] = []
    out["excluded"] = excluded(picker)
    out["pinned"] = ["%s: %s" % (p["name"], it.get("label") or ", ".join(it.get("nodes") or []))
                     for p, it in pinned(picker)]
    out["duplicates"] = ["%s: %s" % (p["name"], ", ".join(it.get("nodes") or [])) for p, it in duplicates(picker)]
    out["gone"] = ["%s: %s" % (p["name"], ", ".join(it.get("nodes") or [])) for p, it in stale(picker, ns)]
    return out
