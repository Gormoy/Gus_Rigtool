"""
5.6.24: more for the picker - plain Python, no Qt (the window is pickerqt.py, the page data pickmodel.py).

Sizes: normalize a page (sane units, the page fitted to what's on it), fit buttons to their text, the page's own
text size. Backgrounds: the meshes (any namespace) seen from the front, a picture captured from Maya's front
view (or your own), each with its place, size and opacity - kept IN the picker so the animators get it.
Pages made from the rig when you click: Switches (visibility, IK / FK, spaces) and Face sliders.
Space switch buttons (an enum: pick from a menu, no jump). Keyed state. Hierarchy lines (parent -> child).
Your quick sets, templates and style rules, chain numbers, arc / line, mirror the layout, one page to a file,
shortcuts. Mirror pairs: the controls whose twin isn't found, or isn't where it should be.
"""

import base64
import copy
import fnmatch
import json
import math
import re

import maya.cmds as cmds

from gus_animtool import anim as A
from gus_animtool import pickmodel as PM

strip = PM.strip


# ===========================================================================
# sizes and text
# ===========================================================================

def _scale_item(it, k, ox, oy):
    it["x"] = round((it["x"] - ox) * k + PM.MARGIN, 2)
    it["y"] = round((it["y"] - oy) * k + PM.MARGIN, 2)
    it["w"] = round(max(2.0, it["w"] * k), 2)
    it["h"] = round(max(2.0, it["h"] * k), 2)
    for key in ("text_size", "size"):
        if it.get(key):
            it[key] = round(float(it[key]) * k, 2)


def needs_normalize(page, usual=24.0):
    """Too big or too small: the usual button far from usual units, or the page much bigger than what's on it."""
    sel = [i for i in page.get("items", []) if i.get("kind") == "select" and not i.get("pin")]
    if not sel:
        return False
    med = PM.typical_size(sel)
    x0, y0, x1, y1 = PM.bounds([i for i in page["items"] if not i.get("pin")])
    pw, ph = page.get("width", PM.PAGE_W), page.get("height", PM.PAGE_W)
    empty = (pw * ph) > 2.5 * max((x1 - x0 + 2 * PM.MARGIN) * (y1 - y0 + 2 * PM.MARGIN), 1.0)
    return not (usual / 2.5 <= med <= usual * 2.5) or empty or x0 < -1 or y0 < -1


def normalize(page, usual=24.0):
    """The page in sane units: the usual button about usual units, everything moved to start at the margin, the
    page's size fitted to what's on it (so it opens big in the window); text sizes, the outline and the picture
    come along. Pinned buttons (window places) stay. Returns the factor."""
    items = [i for i in page.get("items", []) if not i.get("pin")]
    if not items:
        return 1.0
    sel = [i for i in items if i.get("kind") == "select"] or items
    k = usual / max(PM.typical_size(sel), 1e-6)
    if 0.9 < k < 1.1:
        k = 1.0
    x0, y0, _x1, _y1 = PM.bounds(items)
    for it in items:
        _scale_item(it, k, x0, y0)
    sil = page.get("outline")
    if sil:
        c = float(sil.get("cell", 4.0))
        sil["cell"] = round(c * k, 4)
        sil["ox"] = round((float(sil.get("ox", 0.0)) - x0) * k + PM.MARGIN, 3)
        sil["oy"] = round((float(sil.get("oy", 0.0)) - y0) * k + PM.MARGIN, 3)
    pic = page.get("picture")
    if pic:
        pic["x"] = round((pic["x"] - x0) * k + PM.MARGIN, 2)
        pic["y"] = round((pic["y"] - y0) * k + PM.MARGIN, 2)
        pic["w"], pic["h"] = round(pic["w"] * k, 2), round(pic["h"] * k, 2)
    _bx0, _by0, bx1, by1 = PM.bounds(items)
    page["width"] = round(bx1 + PM.MARGIN, 1)
    page["height"] = round(by1 + PM.MARGIN, 1)
    return k


def font_units(it):
    """The text's size in page units (what the window draws, before your Text slider)."""
    if PM.is_text(it):
        return float(it.get("size") or 14.0)
    return float(it.get("text_size") or 0.0) or it["h"] * 0.56


def fit_to_text(items, k=1.0):
    """Buttons as wide as their text (never narrower than they are). Returns how many grew."""
    n = 0
    for it in items:
        if PM.is_frame(it) or not it.get("label") or it.get("label_pos") not in (None, "center"):
            continue
        need = len(it["label"]) * font_units(it) * 0.6 * k + 8.0
        if need > it["w"]:
            c = it["x"] + it["w"] * 0.5
            it["w"] = round(need, 1)
            it["x"] = round(c - need * 0.5, 1)
            n += 1
    return n


def text_bigger(items, factor):
    """Text + / Text - on anything: buttons and frames (text_size), text items (their size)."""
    for i in items:
        if PM.is_text(i):
            i["size"] = round(max(3.0, float(i.get("size", 14.0)) * factor), 2)
            i.pop("text_size", None)
        else:
            base = float(i.get("text_size") or (TITLE_SIZE if PM.is_frame(i) else i["h"] * 0.56))
            i["text_size"] = round(max(3.0, base * factor), 2)


# frames: the title (pickmodel.title_rect / title_h / on_title)
TITLE_SIZE = PM.TITLE_SIZE
TITLE_PLACES = PM.TITLE_PLACES


# ===========================================================================
# backgrounds: the meshes from the front (any namespace), a picture
# ===========================================================================

def rig_meshes(ns=""):
    """The character's skinned meshes: in its namespace, or (5.6.24) skinned to its joints whatever their own
    namespace (a model referenced as Geo_Hare_07: into the rig)."""
    out = []
    for skin in cmds.ls(type="skinCluster") or []:
        try:
            infl = cmds.skinCluster(skin, query=True, influence=True) or []
        except (RuntimeError, ValueError):
            infl = []
        ours = any(A.namespace_of(j) == (ns or "") for j in infl[:8])
        for g in cmds.skinCluster(skin, query=True, geometry=True) or []:
            t = (cmds.listRelatives(g, parent=True, fullPath=True) or [g])[0]
            if (ours or A.namespace_of(t) == (ns or "")) and t not in out:
                out.append(t)
    return out


def mesh_points(ns="", limit=30000):
    pts = []
    for m in rig_meshes(ns):
        try:
            flat = cmds.xform(m + ".vtx[*]", query=True, worldSpace=True, translation=True) or []
        except (RuntimeError, ValueError, TypeError):
            continue
        pts += [tuple(flat[i:i + 3]) for i in range(0, len(flat) - 2, 3)]
    step = max(1, len(pts) // limit)
    return pts[::step]


def page_outline(page, points, pos_of, cells=160):
    """The meshes seen from the front behind the page's buttons, on its scale - about cells squares across the
    page (never too small to see). True when made."""
    fit = PM.fit_view(page["items"], pos_of)
    if fit is None or not points:
        return False
    a, b, c = fit
    w, h = PM.page_size(page)
    cell = max(2.0, max(w, h) / float(cells))
    pad = cell * 6
    near = [p for p in points if -pad <= a * p[0] + b <= w + pad and -pad <= -a * p[1] + c <= h + pad]
    sil = PM.silhouette(near, "front", a, 0.0, 0.0, b, 0.0, c, cell)
    if not sil:
        return False
    sil["alpha"] = float((page.get("outline") or {}).get("alpha", 0.6))
    page["outline"] = sil
    return True


def outline_grid(sil):
    """(columns, rows, x0, y0, filled set) of an outline - for drawing it as one picture."""
    runs = sil.get("runs") or []
    if not runs:
        return None
    xs0 = min(r[1] for r in runs)
    xs1 = max(r[2] for r in runs)
    ys0 = min(r[0] for r in runs)
    ys1 = max(r[0] for r in runs)
    return xs1 - xs0 + 1, ys1 - ys0 + 1, xs0, ys0


def picture_rect_from_camera(fit, centre, width, height):
    """Where a front picture of the model sits on the page: the camera's frame (world centre, width, height)
    through the page's fit."""
    a, b, c = fit
    return {"x": round(a * (centre[0] - width * 0.5) + b, 2), "y": round(-a * (centre[1] + height * 0.5) + c, 2),
            "w": round(a * width, 2), "h": round(a * height, 2)}


def set_picture(page, data, rect, kind="picture", alpha=0.5):
    """A picture behind the page (PNG bytes kept in the picker: the animators get it too)."""
    page["picture"] = dict(rect, data=base64.b64encode(data).decode("ascii"), kind=kind, alpha=alpha)
    return page["picture"]


def picture_bytes(page):
    pic = page.get("picture") or {}
    try:
        return base64.b64decode(pic.get("data") or "")
    except (TypeError, ValueError):
        return b""


def mesh_box(ns=""):
    """World box (x0, y0, z0, x1, y1, z1) of the character's meshes, or None."""
    meshes = rig_meshes(ns)
    if not meshes:
        return None
    try:
        return cmds.exactWorldBoundingBox(meshes)
    except (RuntimeError, ValueError, TypeError):
        return None


KEY_RGB = (1.0, 0.0, 1.0)                           # the capture's background (taken out after)


def capture_front(path, ns="", height_px=640):
    """Maya: a flat picture of the character's meshes from the front (an orthographic camera, only the meshes,
    a plain background taken out after). Returns (path, centre, width, height) in the world."""
    box = mesh_box(ns)
    if not box:
        raise RuntimeError("no meshes found for this character (skinned to its joints).")
    cx, cy = (box[0] + box[3]) * 0.5, (box[1] + box[4]) * 0.5
    w, h = (box[3] - box[0]) * 1.06, (box[4] - box[1]) * 1.06
    ortho = max(w, h)
    cam, cam_shape = cmds.camera(orthographic=True, orthographicWidth=w)
    cmds.setAttr(cam_shape + ".filmFit", 1)                  # horizontal: across = exactly w
    cmds.xform(cam, worldSpace=True, translation=(cx, cy, box[5] + ortho * 2.0), rotation=(0, 0, 0))
    cmds.setAttr(cam_shape + ".farClipPlane", ortho * 10 + (box[5] - box[2]) * 4)
    win = cmds.window(widthHeight=(height_px, height_px))
    cmds.paneLayout()
    panel = cmds.modelPanel(camera=cam, menuBarVisible=False)
    cmds.showWindow(win)
    grad = cmds.displayPref(query=True, displayGradient=True)
    bg = cmds.displayRGBColor("background", query=True)
    try:
        cmds.displayPref(displayGradient=False)
        cmds.displayRGBColor("background", *KEY_RGB)
        cmds.modelEditor(panel, edit=True, allObjects=False, polymeshes=True, grid=False, headsUpDisplay=False,
                         displayAppearance="smoothShaded", displayLights="default", wireframeOnShaded=False,
                         selectionHiliteDisplay=False, manipulators=False)
        size = (max(16, int(round(height_px * w / max(h, 1e-6)))), height_px)    # the picture: w : h
        cmds.playblast(editorPanelName=panel, frame=[cmds.currentTime(query=True)], format="image",
                       compression="png", completeFilename=path, viewer=False, showOrnaments=False,
                       widthHeight=size, percent=100, forceOverwrite=True, offScreen=True)
    finally:
        cmds.displayRGBColor("background", *bg)
        cmds.displayPref(displayGradient=grad)
        try:
            cmds.deleteUI(win)
        except RuntimeError:
            pass
        cmds.delete(cam)
    return path, (cx, cy), w, h


# ===========================================================================
# pages made from the rig (when you click): Switches, Face sliders
# ===========================================================================

SWITCH_WORDS = r"vis|show|ctrls|_ctrls|display|geo|joints|ik_?fk|fk_?ik|ikfk|switch|blend|follow|space|parent|orient"
SPACE_WORDS = r"space|follow|parent|orient|align"
GEN = "gen"                                          # an item made by a 'made from the rig' page


def _attr_info(node, attr):
    """(type, min, max, enum names) of a user attribute, or None."""
    try:
        t = cmds.attributeQuery(attr, node=node, attributeType=True)
    except RuntimeError:
        return None
    lo = hi = None
    try:
        if cmds.attributeQuery(attr, node=node, minExists=True):
            lo = cmds.attributeQuery(attr, node=node, minimum=True)[0]
        if cmds.attributeQuery(attr, node=node, maxExists=True):
            hi = cmds.attributeQuery(attr, node=node, maximum=True)[0]
    except (RuntimeError, TypeError, IndexError):
        pass
    names = []
    if t == "enum":
        try:
            names = [x.split("=")[0] for x in (cmds.attributeQuery(attr, node=node, listEnum=True) or [""])[0]
                     .split(":") if x]
        except (RuntimeError, IndexError):
            names = []
    return t, lo, hi, names


def _user_attrs(node):
    out = []
    for a in cmds.listAttr(node, userDefined=True, keyable=True) or []:
        if "." in a:
            continue
        try:
            if cmds.getAttr(node + "." + a, lock=True):
                continue
        except (RuntimeError, ValueError):
            continue
        out.append(a)
    for a in cmds.listAttr(node, userDefined=True, channelBox=True) or []:
        if "." not in a and a not in out:
            try:
                if not cmds.getAttr(node + "." + a, lock=True):
                    out.append(a)
            except (RuntimeError, ValueError):
                pass
    return out


def switch_attrs(controls):
    """[(control, attr, kind)] - the switches on these controls: on / off (bool, a 2-value enum, a 0..1 named like
    a switch) -> 'toggle'; an enum with more values named like a space -> 'enum'."""
    out = []
    for c in controls:
        for a in _user_attrs(c):
            info = _attr_info(c, a)
            if not info:
                continue
            t, lo, hi, names = info
            low = a.lower()
            if t == "bool":
                out.append((c, a, "toggle"))
            elif t == "enum" and len(names) == 2:
                out.append((c, a, "toggle"))
            elif t == "enum" and len(names) > 2 and re.search(SPACE_WORDS, low):
                out.append((c, a, "enum"))
            elif t in ("double", "float", "long") and lo is not None and hi is not None and (lo, hi) == (0, 1) \
                    and re.search(SWITCH_WORDS, low):
                out.append((c, a, "toggle"))
    return out


def slider_attrs(controls):
    """[(control, attr, min, max)] - number attributes with both limits (expressions, amounts) - not switches."""
    out = []
    for c in controls:
        for a in _user_attrs(c):
            info = _attr_info(c, a)
            if not info:
                continue
            t, lo, hi, _names = info
            if t in ("double", "float", "doubleLinear", "doubleAngle") and lo is not None and hi is not None and \
                    hi > lo and not re.search(SWITCH_WORDS, a.lower()):
                out.append((c, a, lo, hi))
    return out


def _frame_grid(page, groups, make_item, cols=3, cell=(96.0, 22.0), gap=4.0, top=None):
    """Each group (title, [entries]) as a frame with its items in a grid, frames one under the other."""
    y = PM.MARGIN if top is None else top
    made = []
    for title, entries in groups:
        if not entries:
            continue
        rows = (len(entries) + cols - 1) // cols
        x0, y0 = PM.MARGIN + 8.0, y + PM.TITLE_H + 8.0
        its = []
        for k, e in enumerate(entries):
            it = make_item(e)
            it["x"] = x0 + (k % cols) * (cell[0] + gap)
            it["y"] = y0 + (k // cols) * (cell[1] + gap)
            it["w"], it["h"] = cell
            it[GEN] = True
            its.append(it)
        page["items"] += its
        fr = PM.group_frame(page, its, title)
        fr[GEN] = True
        made += its + [fr]
        y += PM.TITLE_H + 16.0 + rows * (cell[1] + gap) + 12.0
    return made


def _replace_page(picker, name):
    """The page called name, its made-from-the-rig items taken away (yours stay); made when missing."""
    page = PM.page_named(picker, name) or PM.add_page(picker, name)
    page["items"] = [i for i in page["items"] if not i.get(GEN)]
    return page


def switches_page(picker, ns="", controls=None):
    """The Switches page: every switch on the character's controls (visibility, IK / FK, spaces) as toggles and
    space menus, a frame per control. Made again on click (your own items on the page stay). Returns the page."""
    controls = A.character_controls(ns) if controls is None else controls
    found = switch_attrs(controls)
    by = {}
    order = []
    for c, a, kind in found:
        if c not in by:
            by[c] = []
            order.append(c)
        by[c].append((c, a, kind))
    page = _replace_page(picker, "Switches")
    top = (PM.bounds(page["items"])[3] + 20.0) if page["items"] else None

    def make(e):
        c, a, kind = e
        it = PM.add_widget({"items": []}, "toggle" if kind == "toggle" else "check", c, a, 0, 0)
        if kind == "enum":
            info = _attr_info(c, a) or (None, 0, 0, [])
            it.update({"kind": "enum", "choices": info[3], "shape": "rect", "rgb": [0.3, 0.42, 0.55]})
        it["label"] = PM.apply_rules(a.replace("_", " "))
        return it
    _frame_grid(page, [(PM.label_of(c), by[c]) for c in order], make, top=top)
    _fit_page(page)
    return page


def face_sliders_page(picker, ns="", controls=None):
    """The Face sliders page: the face controls' number attributes with limits (your expressions on
    Mouth_main_ctrl...) as sliders, a frame per control. Made again on click."""
    if controls is None:
        rig = PM.read_rig(ns)
        controls = [r["node"] for r in PM.classify(rig, ns).get("Face", [])]
        controls += [c for c in A.character_controls(ns) if c not in controls and
                     re.search(r"face|mouth_main|expression|poses?", strip(c).lower())]
    found = slider_attrs(controls)
    by, order = {}, []
    for c, a, lo, hi in found:
        if c not in by:
            by[c] = []
            order.append(c)
        by[c].append((c, a, lo, hi))
    page = _replace_page(picker, "Face sliders")
    top = (PM.bounds(page["items"])[3] + 20.0) if page["items"] else None

    def make(e):
        c, a, lo, hi = e
        it = PM.add_widget({"items": []}, "slider", c, a, 0, 0)
        it.update({"min": lo, "max": hi, "label": PM.apply_rules(a.replace("_", " ")), "rgb": [0.35, 0.37, 0.42]})
        return it
    _frame_grid(page, [(PM.label_of(c), by[c]) for c in order], make, cols=2, cell=(150.0, 18.0), top=top)
    _fit_page(page)
    return page


def _fit_page(page):
    if page["items"]:
        _x0, _y0, x1, y1 = PM.bounds(page["items"])
        page["width"] = round(max(PM.PAGE_W, x1 + PM.MARGIN), 1)
        page["height"] = round(max(200.0, y1 + PM.MARGIN), 1)


# ===========================================================================
# space switch (an enum: pick from a menu, no jump)
# ===========================================================================

def add_enum(page, node, attr, x=None, y=None):
    info = _attr_info(node, attr)
    if not info or info[0] != "enum":
        raise RuntimeError("%s isn't a list attribute (enum) - pick a space / follow attribute in the Channel Box."
                           % attr)
    it = PM.add_items(page, [node], x, y)[0]
    it.update({"kind": "enum", "attr": attr, "choices": info[3], "shape": "rect", "rgb": [0.3, 0.42, 0.55],
               "label": PM.apply_rules(attr.replace("_", " ")), "w": max(80.0, 7.5 * len(attr) + 30.0), "h": 20.0})
    return it


def enum_value(item, ns):
    nodes = PM.resolve(item, ns)
    if not nodes:
        return None
    try:
        return int(cmds.getAttr(nodes[0] + "." + item["attr"]))
    except (RuntimeError, ValueError, TypeError):
        return None


def set_enum(item, ns, index, keep_place=True):
    """The attribute to choice index; keep_place: each control stays where it is in the world (no jump)."""
    for n in PM.resolve(item, ns):
        plug = n + "." + item["attr"]
        if not A._settable(plug):
            continue
        before = cmds.xform(n, query=True, worldSpace=True, matrix=True) if keep_place else None
        cmds.setAttr(plug, int(index))
        if before:
            try:
                cmds.xform(n, worldSpace=True, matrix=before)
            except RuntimeError:
                pass


# ===========================================================================
# keyed state, hierarchy lines
# ===========================================================================

def keyed_state(node, t):
    """(keyed on frame t, animated at all)."""
    try:
        total = cmds.keyframe(node, query=True, keyframeCount=True) or 0
        if not total:
            return False, False
        now = cmds.keyframe(node, query=True, time=(t, t), keyframeCount=True) or 0
        return bool(now), True
    except (RuntimeError, TypeError):
        return False, False


def hierarchy_links(items, long_of):
    """[(parent item, child item)] - each single-control button linked to the button of its nearest parent
    control on the page (long_of: item -> its control's long name, or None)."""
    by_long = {}
    for it in items:
        if it.get("kind") != "select" or len(it.get("nodes") or []) != 1:
            continue
        ln = long_of(it)
        if ln:
            by_long[ln] = it
    out = []
    for ln, it in by_long.items():
        parts = ln.split("|")
        for k in range(len(parts) - 1, 1, -1):
            up = "|".join(parts[:k])
            if up in by_long:
                out.append((by_long[up], it))
                break
    return out


# ===========================================================================
# your quick sets (per animator), templates, style rules, chain numbers, arc / line, mirror layout
# ===========================================================================

def my_sets(rig):
    try:
        got = json.loads(A.opt("picker_mysets", "") or "{}")
    except ValueError:
        got = {}
    return dict(got.get(rig) or {}) if isinstance(got, dict) else {}


def save_my_set(rig, name, nodes):
    try:
        got = json.loads(A.opt("picker_mysets", "") or "{}")
    except ValueError:
        got = {}
    got = got if isinstance(got, dict) else {}
    mine = dict(got.get(rig) or {})
    if nodes is None:
        mine.pop(name, None)
    else:
        mine[name] = [strip(n) for n in nodes]
    got[rig] = mine
    A.set_opt("picker_mysets", json.dumps(got))
    return mine


BUILTIN_STYLES = {
    "FK dot": {"shape": "round", "rgb": [0.25, 0.45, 0.95], "w": 18.0, "h": 18.0},
    "IK box": {"shape": "rect", "rgb": [0.95, 0.55, 0.15], "w": 26.0, "h": 22.0, "corner": 0.2},
    "Tweak dot": {"shape": "ellipse", "rgb": [0.55, 0.85, 0.55], "w": 12.0, "h": 12.0},
    "Main ring": {"shape": "ring", "rgb": [0.95, 0.85, 0.2], "w": 60.0, "h": 40.0},
    "Settings": {"shape": "diamond", "rgb": [0.75, 0.75, 0.8], "w": 20.0, "h": 20.0},
    "Face pill": {"shape": "pill", "rgb": [0.9, 0.6, 0.75], "w": 30.0, "h": 14.0},
}


def all_styles():
    out = dict(BUILTIN_STYLES)
    out.update(PM.styles())
    return out


def style_rules():
    """[(name pattern, style)] - yours, in order (first match wins)."""
    try:
        got = json.loads(A.opt("picker_style_rules", "") or "[]")
    except ValueError:
        got = []
    return [tuple(x) for x in got if isinstance(x, (list, tuple)) and len(x) == 2]


def set_style_rules(rules):
    A.set_opt("picker_style_rules", json.dumps([list(r) for r in rules]))


def apply_style_rules(items, rules=None, styles=None):
    """Each single-control button whose control matches a rule gets that style. Returns how many."""
    rules = style_rules() if rules is None else rules
    styles = all_styles() if styles is None else styles
    n = 0
    for it in items:
        if it.get("kind") != "select" or len(it.get("nodes") or []) != 1:
            continue
        name = it["nodes"][0]
        for pat, st in rules:
            if st in styles and fnmatch.fnmatch(name.lower(), pat.lower()):
                PM.paste_style([it], styles[st])
                n += 1
                break
    return n


def chain_numbers(items):
    """Buttons of a chain (the same name but a number) labelled 1, 2, 3... ('Ear FK 1'). Returns how many."""
    groups = {}
    for it in items:
        if it.get("kind") != "select" or len(it.get("nodes") or []) != 1:
            continue
        name = it["nodes"][0]
        nums = re.findall(r"\d+", name)
        if not nums:
            continue
        key = re.sub(r"\d+(?!.*\d)", "#", name)
        groups.setdefault(key, []).append((int(nums[-1]), it))
    n = 0
    for key, members in groups.items():
        if len(members) < 2:
            continue
        base = PM.label_of(key.replace("#", "")).strip()
        for num, it in members:
            it["label"] = ("%s %d" % (base, num)).strip()
            n += 1
    return n


def _centre(it):
    return it["x"] + it["w"] * 0.5, it["y"] + it["h"] * 0.5


def _place(it, cx, cy):
    it["x"], it["y"] = round(cx - it["w"] * 0.5, 2), round(cy - it["h"] * 0.5, 2)


def on_line(items):
    """Evenly along the line from the first to the last (in the order picked: left to right / top down)."""
    its = sorted(items, key=lambda i: _centre(i))
    if len(its) < 3:
        return 0
    (ax, ay), (bx, by) = _centre(its[0]), _centre(its[-1])
    for k, it in enumerate(its):
        f = k / float(len(its) - 1)
        _place(it, ax + (bx - ax) * f, ay + (by - ay) * f)
    return len(its)


def on_arc(items, bulge=0.3):
    """Evenly on an arc from the first to the last, bowing out by bulge x the distance (fingers as a fan;
    negative: the other way)."""
    its = sorted(items, key=lambda i: _centre(i))
    if len(its) < 3:
        return 0
    (ax, ay), (bx, by) = _centre(its[0]), _centre(its[-1])
    dx, dy = bx - ax, by - ay
    chord = math.hypot(dx, dy)
    if chord < 1e-6:
        return 0
    nx, ny = -dy / chord, dx / chord                         # the bow's side
    for k, it in enumerate(its):
        f = k / float(len(its) - 1)
        h = 4.0 * bulge * chord * f * (1 - f)                # a parabola through both ends
        _place(it, ax + dx * f + nx * h * -1.0, ay + dy * f + ny * h * -1.0)
    return len(its)


def mirror_layout(page, from_side="L", mirror_name=None):
    """Every button of one side placed (and sized) as the mirror image of its twin across the page's middle (the
    middle of the centre buttons, else the page's). Returns how many moved."""
    mirror_name = mirror_name or A.mirror_name
    sel = [i for i in page["items"] if i.get("kind") == "select" and len(i.get("nodes") or []) == 1]
    by = dict((i["nodes"][0], i) for i in sel)
    sides = dict((i["id"], PM.side_of_item(i)) for i in sel)
    mids = [_centre(i)[0] for i in sel if sides[i["id"]] == "C"]
    mid = sum(mids) / len(mids) if mids else PM.page_size(page)[0] * 0.5
    n = 0
    for it in sel:
        if sides[it["id"]] != from_side:
            continue
        m = mirror_name(it["nodes"][0])
        other = by.get(strip(m)) if m else None
        if other is None or other is it or other.get("locked") or other.get("pin"):
            continue
        other["w"], other["h"] = it["w"], it["h"]
        cx, cy = _centre(it)
        _place(other, 2 * mid - cx, cy)
        n += 1
    return n


# ===========================================================================
# one page to a file and back; shortcuts; unsure curves
# ===========================================================================

def export_page(page, path):
    with open(path, "w") as f:
        json.dump({"gusPickerPage": 1, "page": page}, f, indent=1)
    return path


def import_page(picker, path):
    """A page from a file, added (new ids, its twins kept; a name already used gets a number)."""
    with open(path) as f:
        data = json.load(f)
    page = data.get("page") if isinstance(data, dict) else None
    if not isinstance(page, dict) or not isinstance(page.get("items"), list):
        raise RuntimeError("that file isn't a Gus Animtool picker page.")
    raw = copy.deepcopy(page)
    raw["name"] = "__importing__"
    picker["pages"].append(raw)
    PM._sync_ids(picker)
    i = PM.duplicate_page(picker, len(picker["pages"]) - 1, name=page.get("name") or "Imported")
    picker["pages"].pop(i - 1)                              # keep the copy (fresh ids), not the raw one
    return i - 1


DEFAULT_KEYS = {"copy": "Ctrl+C", "paste": "Ctrl+V", "paste in place": "Ctrl+Shift+V", "undo (Maya)": "Z",
                "redo (Maya)": "Shift+Z", "preview": "P", "rename": "F2",
                "frame": "F", "frame picked": "Shift+F", "find": "Ctrl+F", "help": "?", "group": "Ctrl+G",
                "ungroup": "Ctrl+Shift+G", "lock": "Ctrl+L", "duplicate": "Ctrl+D", "save": "Ctrl+S",
                "undo": "Ctrl+Z", "redo": "Ctrl+Y", "to front": "Ctrl+Shift+]", "to back": "Ctrl+Shift+[",
                "up one": "Ctrl+]", "down one": "Ctrl+[", "pick all": "Ctrl+A", "key": "S"}


def shortcuts():
    try:
        got = json.loads(A.opt("picker_keys", "") or "{}")
    except ValueError:
        got = {}
    out = dict(DEFAULT_KEYS)
    if isinstance(got, dict):
        out.update(dict((k, v) for k, v in got.items() if k in DEFAULT_KEYS))
    return out


def set_shortcuts(keys):
    A.set_opt("picker_keys", json.dumps(dict((k, v) for k, v in keys.items() if k in DEFAULT_KEYS)))


def norm_key(text):
    """'ctrl + shift + g' -> 'Ctrl+Shift+G' (modifiers in a fixed order)."""
    parts = [p.strip() for p in (text or "").replace(" ", "").split("+")]
    if text and text.strip().endswith("+") and text.strip() != "+":
        parts = [p for p in parts if p] + ["+"]
    mods = [m for m in ("Ctrl", "Shift", "Alt") if any(p.lower() == m.lower() for p in parts)]
    rest = [p for p in parts if p and p.lower() not in ("ctrl", "shift", "alt")]
    key = rest[-1].upper() if rest and len(rest[-1]) == 1 else (rest[-1].capitalize() if rest else "")
    return "+".join(mods + ([key] if key else []))


def action_for(key_text, keys=None):
    keys = shortcuts() if keys is None else keys
    want = norm_key(key_text)
    for action, k in keys.items():
        if norm_key(k) == want:
            return action
    return None


UNSURE_IGNORE = "*_line_crv, *_crv, *guide*, *_display*, *_curveShape*"


def unsure_ignore():
    return [p.strip() for p in (A.opt("picker_unsure_ignore", UNSURE_IGNORE) or "").split(",") if p.strip()]


def drop_ignored(nodes, patterns=None):
    patterns = unsure_ignore() if patterns is None else patterns
    out = []
    for n in nodes:
        b = strip(n).lower()
        if any(fnmatch.fnmatch(b, p.lower()) for p in patterns):
            continue
        try:
            if cmds.getAttr(n + ".template"):
                continue
        except (RuntimeError, ValueError, TypeError):
            pass
        out.append(n)
    return out


# ===========================================================================
# mirror pairs
# ===========================================================================

def pair_report(ns=""):
    """The controls whose twin isn't found, or isn't where it should be: [{'node', 'side', 'twin', 'how',
    'problem', 'suggest'}] - how: 'name' / 'link' / 'position' / None; problem: 'none' (no twin), 'off' (the
    named twin isn't at the mirrored place), 'position' (paired only by position - fine, but worth a link)."""
    ctrls = A.character_controls(ns)
    pos = {}
    for c in ctrls:
        try:
            pos[c] = A._rest_pos(c)
        except (RuntimeError, ValueError, TypeError):
            pass
    if not pos:
        return []
    ax = A.DEFAULT_AXIS
    centre = A.DEFAULT_CENTER[ax]
    ys = [p[1] for p in pos.values()]
    tall = max(max(ys) - min(ys), 1e-6)
    tol = max(0.01, tall * 0.002)
    off_tol = max(tol * 4, tall * 0.01)
    try:
        by_pos = A.position_twins(ns)
    except Exception:
        by_pos = {}

    def nearest(c):
        p = list(pos[c])
        p[ax] = 2 * centre - p[ax]
        best, dist = None, None
        for k, q in pos.items():
            if k == c:
                continue
            d = max(abs(x - y) for x, y in zip(p, q))
            if dist is None or d < dist:
                best, dist = k, d
        return best, dist
    out = []
    sided = re.compile(r"(^|_)(L|R|l|r|Lf|Rt|Left|Right|left|right)(_|\d|$)")
    for c in ctrls:
        if c not in pos or abs(pos[c][ax] - centre) <= tol:
            continue
        if not sided.search(strip(c)) and abs(pos[c][ax] - centre) <= tall * 0.03:
            continue                                    # 5.6.25: a middle control a little off the line
        named = A._name_twin(c)
        if named and named in pos:
            p = list(pos[c])
            p[ax] = 2 * centre - p[ax]
            d = max(abs(x - y) for x, y in zip(p, pos[named]))
            if d > off_tol:
                best, bd = nearest(c)
                out.append({"node": c, "twin": named, "how": "name", "problem": "off",
                            "suggest": best if (best and bd is not None and bd <= off_tol and best != named)
                            else None, "dist": round(d, 3)})
            continue
        if by_pos.get(c):
            out.append({"node": c, "twin": by_pos[c], "how": "position", "problem": "position",
                        "suggest": by_pos[c], "dist": 0.0})
            continue
        best, bd = nearest(c)
        out.append({"node": c, "twin": None, "how": None, "problem": "none",
                    "suggest": best if (best and bd is not None and bd <= off_tol) else None,
                    "dist": round(bd, 3) if bd is not None else None})
    return out


# ===========================================================================
# 5.6.25: one way to place text (buttons, frame titles, texts, notes)
# ===========================================================================

TEXT_PLACES = ("center", "top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right",
               "above", "below", "outside-left", "outside-right", "bar", "hidden")


def text_place(it):
    """Where the item's text goes - its own choice, else what the older settings said."""
    if it.get("tpos"):
        return it["tpos"]
    if PM.is_frame(it):
        old = it.get("title_pos") or "bar"
        if old == "inside":
            return {"center": "top", "right": "top-right"}.get(it.get("align") or "left", "top-left")
        return old
    if PM.is_text(it):
        if it.get("note"):
            return "top-left"
        return {"left": "left", "right": "right"}.get(it.get("align"), "center")
    return {"left": "outside-left", "right": "outside-right"}.get(it.get("label_pos") or "center",
                                                                  it.get("label_pos") or "center")


def text_box(place, x0, y0, x1, y1, tw, th, pad=3.0):
    """(left, top, alignment) of a text tw x th placed on the box (x0, y0)-(x1, y1); alignment: 'left' /
    'center' / 'right' (how its lines line up)."""
    cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
    if place in ("above", "bar"):
        return cx - tw * 0.5, y0 - th - pad * 0.5, "center"
    if place == "below":
        return cx - tw * 0.5, y1 + pad * 0.5, "center"
    if place == "outside-left":
        return x0 - tw - pad, cy - th * 0.5, "right"
    if place == "outside-right":
        return x1 + pad, cy - th * 0.5, "left"
    v = place.split("-") if "-" in place else [place]
    left = x0 + pad if "left" in v else (x1 - tw - pad if "right" in v else cx - tw * 0.5)
    top = y0 + pad if "top" in v else (y1 - th - pad if "bottom" in v else cy - th * 0.5)
    align = "left" if "left" in v else ("right" if "right" in v else "center")
    return left, top, align


def add_note(page, text="Note", x=None, y=None):
    """A sticky note: a coloured text you write on (several lines), text from the top-left."""
    it = PM.add_text(page, text, x, y)
    it.update({"note": True, "w": 130.0, "h": 90.0, "rgb": [0.98, 0.86, 0.38], "text_rgb": [0.12, 0.12, 0.12],
               "size": 11.0, "bold": False, "tpos": "top-left", "wrap": 1})
    return it


# ===========================================================================
# 5.6.25: connectors (Nuke / Miro style): an item to an item, straight / elbow / curved, bends, heads, a label
# ===========================================================================

LINK_STYLES = ("curved", "straight", "elbow")
LINK_DASHES = ("solid", "dash", "dot")
LINK_HEADS = ("none", "arrow", "open", "dot", "diamond")
LINK_SIDES = ("auto", "top", "bottom", "left", "right")


def links(page):
    return page.setdefault("links", [])


def add_link(page, a, b, **style):
    """A connector from item a to item b (ids). Not twice between the same two. Returns it."""
    if a == b:
        raise RuntimeError("a connector goes from one item to another.")
    for ln in links(page):
        if {ln["a"], ln["b"]} == {a, b}:
            return ln
    ln = {"id": PM.new_id(), "a": a, "b": b, "a_side": "auto", "b_side": "auto", "style": "curved",
          "rgb": [0.75, 0.78, 0.85], "width": 1.5, "dash": "solid", "head_a": "none", "head_b": "arrow",
          "label": "", "label_at": 0.5, "bends": []}
    ln.update(dict((k, v) for k, v in style.items() if v is not None))
    links(page).append(ln)
    return ln


def clean_links(page):
    """Connectors whose ends are gone, taken away. Returns how many."""
    ids = set(i["id"] for i in page.get("items", []))
    before = len(page.get("links") or [])
    if "links" in page:
        page["links"] = [ln for ln in page["links"] if ln["a"] in ids and ln["b"] in ids]
    return before - len(page.get("links") or [])


def _centre_of(it):
    return it["x"] + it["w"] * 0.5, it["y"] + it["h"] * 0.5


def side_point(it, side, toward):
    """(x, y, (nx, ny)) - where a connector leaves the item: the middle of a side (auto: the side facing
    toward), and that side's outward direction."""
    cx, cy = _centre_of(it)
    if side == "auto":
        dx, dy = toward[0] - cx, toward[1] - cy
        if abs(dx) * it["h"] >= abs(dy) * it["w"]:
            side = "right" if dx >= 0 else "left"
        else:
            side = "bottom" if dy >= 0 else "top"
    return {"top": (cx, it["y"], (0.0, -1.0)), "bottom": (cx, it["y"] + it["h"], (0.0, 1.0)),
            "left": (it["x"], cy, (-1.0, 0.0)), "right": (it["x"] + it["w"], cy, (1.0, 0.0))}[side]


def _ends(page, ln):
    by = dict((i["id"], i) for i in page.get("items", []))
    a, b = by.get(ln["a"]), by.get(ln["b"])
    if a is None or b is None:
        return None
    bends = [tuple(p) for p in ln.get("bends") or []]
    ta = bends[0] if bends else _centre_of(b)
    tb = bends[-1] if bends else _centre_of(a)
    pa = side_point(a, ln.get("a_side") or "auto", ta)
    pb = side_point(b, ln.get("b_side") or "auto", tb)
    return pa, pb, bends


def _bezier(p0, p1, p2, p3, n=16):
    out = []
    for k in range(n + 1):
        t = k / float(n)
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def _catmull(pts, n=10):
    if len(pts) < 3:
        return list(pts)
    ext = [pts[0]] + list(pts) + [pts[-1]]
    out = [pts[0]]
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(1, n + 1):
            t = k / float(n)
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j])
                                    * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    return out


def link_points(page, ln):
    """The connector as a line through page points (curves sampled), or None when an end is gone."""
    got = _ends(page, ln)
    if not got:
        return None
    (ax, ay, na), (bx, by, nb), bends = got
    style = ln.get("style") or "curved"
    ctrl = [(ax, ay)] + bends + [(bx, by)]
    if style == "straight":
        return ctrl
    if style == "elbow":                                  # right angles: a step half way, or a corner a gap
        if not bends:
            if abs(na[0]) > 0:
                mx = (ax + bx) * 0.5
                return [(ax, ay), (mx, ay), (mx, by), (bx, by)]
            my = (ay + by) * 0.5
            return [(ax, ay), (ax, my), (bx, my), (bx, by)]
        out = [ctrl[0]]
        for q in ctrl[1:]:
            p = out[-1]
            out += [(q[0], p[1]), q]
        return out
    if bends:
        return _catmull(ctrl)
    dist = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    facing = na[0] * (bx - ax) + na[1] * (by - ay) > 0 and nb[0] * (ax - bx) + nb[1] * (ay - by) > 0
    if facing and dist < 60.0 and (abs(bx - ax) < 2.0 or abs(by - ay) < 2.0):
        return [(ax, ay), (bx, by)]                       # 5.6.26: close and in line: a straight line
    d = dist * 0.4                                        # (5.6.25 kept at least 20: close ones looped)
    return _bezier((ax, ay), (ax + na[0] * d, ay + na[1] * d), (bx + nb[0] * d, by + nb[1] * d), (bx, by))


def _seg_dist(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    L = vx * vx + vy * vy
    t = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L))
    qx, qy = a[0] + vx * t, a[1] + vy * t
    return ((p[0] - qx) ** 2 + (p[1] - qy) ** 2) ** 0.5


def hit_link(page, x, y, tol=4.0):
    """The connector under (x, y) (within tol page units), the nearest; or None."""
    best, bd = None, None
    for ln in page.get("links") or []:
        pts = link_points(page, ln)
        if not pts:
            continue
        d = min(_seg_dist((x, y), pts[i], pts[i + 1]) for i in range(len(pts) - 1)) if len(pts) > 1 else 1e9
        if d <= tol and (bd is None or d < bd):
            best, bd = ln, d
    return best


def add_bend(page, ln, x, y):
    """A bend point (a Nuke dot) at (x, y), in the gap of the connector it's nearest to. Returns its index."""
    got = _ends(page, ln)
    if not got:
        return None
    (ax, ay, _na), (bx, by, _nb), bends = got
    ctrl = [(ax, ay)] + bends + [(bx, by)]
    gap = min(range(len(ctrl) - 1), key=lambda i: _seg_dist((x, y), ctrl[i], ctrl[i + 1]))
    ln.setdefault("bends", []).insert(gap, [round(x, 2), round(y, 2)])
    return gap


def point_at(pts, t):
    """The point at fraction t along a polyline (and the direction there)."""
    lens = [((pts[i + 1][0] - pts[i][0]) ** 2 + (pts[i + 1][1] - pts[i][1]) ** 2) ** 0.5 for i in range(len(pts) - 1)]
    total = sum(lens) or 1.0
    want = max(0.0, min(1.0, t)) * total
    for i, L in enumerate(lens):
        if want <= L or i == len(lens) - 1:
            f = 0.0 if L < 1e-9 else min(1.0, want / L)
            a, b = pts[i], pts[i + 1]
            return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f), (b[0] - a[0], b[1] - a[1])
        want -= L
    return pts[-1], (1.0, 0.0)


def head_shape(tip, frm, kind, size):
    """A connector end's head: ('poly', [points]) filled, ('lines', [points]) open, ('dot', (c, r)), or None."""
    if kind in (None, "none"):
        return None
    dx, dy = tip[0] - frm[0], tip[1] - frm[1]
    L = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / L, dy / L
    px, py = -uy, ux
    if kind == "dot":
        return "dot", ((tip[0] - ux * size * 0.5, tip[1] - uy * size * 0.5), size * 0.5)
    back = (tip[0] - ux * size, tip[1] - uy * size)
    left = (back[0] + px * size * 0.5, back[1] + py * size * 0.5)
    right = (back[0] - px * size * 0.5, back[1] - py * size * 0.5)
    if kind == "open":
        return "lines", [left, tip, right]
    if kind == "diamond":
        far = (tip[0] - ux * size * 2, tip[1] - uy * size * 2)
        return "poly", [tip, left, far, right]
    return "poly", [tip, left, right]


def links_from_hierarchy(page, long_of, **style):
    """Connectors made from the rig's hierarchy (parent button -> child button) - editable after; made again
    replaces the ones made before (yours stay). Returns how many."""
    page["links"] = [ln for ln in links(page) if not ln.get("hier")]
    n = 0
    for parent, child in hierarchy_links(page["items"], long_of):
        ln = add_link(page, parent["id"], child["id"], hier=True, head_b="none", width=1.2,
                      rgb=[0.6, 0.62, 0.68], **style)
        ln["hier"] = True
        n += 1
    return n


# ===========================================================================
# 5.6.25: layers (show / hide, lock)
# ===========================================================================

def layers(page):
    return page.setdefault("layers", [])


def layer(page, name):
    for L in page.get("layers") or []:
        if L["name"] == name:
            return L
    return None


def add_layer(page, name):
    name = (name or "").strip() or "Layer"
    if layer(page, name) is None:
        layers(page).append({"name": name, "shown": True, "locked": False})
    return layer(page, name)


def set_layer(items, name):
    for it in items:
        if name:
            it["layer"] = name
        else:
            it.pop("layer", None)


def remove_layer(page, name):
    page["layers"] = [L for L in page.get("layers") or [] if L["name"] != name]
    for it in page.get("items", []):
        if it.get("layer") == name:
            it.pop("layer", None)


SWITCH_READER = [None]                                   # 5.6.26: the window sets it: 'node.attr' -> value


def layer_off(page):
    """Ids on hidden layers (5.6.26: a layer that follows a rig switch hides when it's off)."""
    read = SWITCH_READER[0]
    off = set(L["name"] for L in page.get("layers") or [] if not L.get("shown", True) or
              (L.get("switch") and read is not None and read(L["switch"]) < 0.5))
    return set(i["id"] for i in page.get("items", []) if i.get("layer") in off) if off else set()


def layer_locked(page):
    """Ids on locked layers (not picked in Edit)."""
    lk = set(L["name"] for L in page.get("layers") or [] if L.get("locked"))
    return set(i["id"] for i in page.get("items", []) if i.get("layer") in lk) if lk else set()


# ===========================================================================
# 5.6.25: your toolbar (on this computer): sections in your order, tools where you put them, hidden ones
# ===========================================================================

def toolbar_saved():
    try:
        got = json.loads(A.opt("picker_toolbar", "") or "{}")
    except ValueError:
        got = {}
    return got if isinstance(got, dict) else {}


def set_toolbar(saved):
    A.set_opt("picker_toolbar", json.dumps(saved or {}))


def toolbar_layout(spec, saved=None):
    """[(section, [tool ids])] - your sections and order; tools you haven't placed go to their usual section
    (made when you took it away), hidden ones left out. spec: [(section, [ids])], the usual layout."""
    saved = toolbar_saved() if saved is None else saved
    known = [t for _s, ids in spec for t in ids]
    hidden = set(saved.get("hidden") or [])
    out, placed = [], set()
    for sec in saved.get("sections") or []:
        if not isinstance(sec, (list, tuple)) or len(sec) != 2:
            continue
        ids = [t for t in sec[1] if t in known and t not in placed]
        placed.update(ids)
        out.append([sec[0], ids])
    for s, ids in spec:
        rest = [t for t in ids if t not in placed]
        if not rest:
            if not any(o[0] == s for o in out) and not saved.get("sections"):
                out.append([s, []])
            continue
        got = [o for o in out if o[0] == s]
        if got:
            got[0][1] += rest
        else:
            out.append([s, rest])
        placed.update(rest)
    return [(s, [t for t in ids if t not in hidden]) for s, ids in out if [t for t in ids if t not in hidden]]


def toolbar_state(spec, saved=None):
    """Everything placed (hidden ones too) - what the Customize window edits: ([[section, [ids]]], hidden)."""
    saved = toolbar_saved() if saved is None else saved
    full = toolbar_layout(spec, dict(saved, hidden=[]))
    return [[s, list(ids)] for s, ids in full], list(saved.get("hidden") or [])


def toolbar_move(state, tool, step=0, to_section=None):
    """Move a tool up / down (step) in its section, or to another section (the end of it). In place."""
    for sec in state:
        if tool in sec[1]:
            i = sec[1].index(tool)
            if to_section is not None and to_section != sec[0]:
                sec[1].pop(i)
                dest = [s for s in state if s[0] == to_section]
                if not dest:
                    state.append([to_section, []])
                    dest = [state[-1]]
                dest[0][1].append(tool)
            elif step:
                j = max(0, min(len(sec[1]) - 1, i + step))
                sec[1].insert(j, sec[1].pop(i))
            return state
    return state


def section_move(state, name, step):
    names = [s[0] for s in state]
    if name in names:
        i = names.index(name)
        j = max(0, min(len(state) - 1, i + step))
        state.insert(j, state.pop(i))
    return state


# ===========================================================================
# 5.6.25: the silhouette picture from the meshes' triangles (no playblast)
# ===========================================================================

def mesh_triangles(ns="", limit=400000):
    """[((x, y), (x, y), (x, y))] - the character's meshes' triangles seen from the front (world x, y)."""
    import maya.api.OpenMaya as om
    out = []
    for m in rig_meshes(ns):
        shapes = cmds.listRelatives(m, shapes=True, type="mesh", noIntermediate=True, fullPath=True) or []
        if not shapes:
            continue
        try:
            if not cmds.getAttr(m + ".visibility") or not cmds.getAttr(shapes[0] + ".visibility"):
                continue
            sel = om.MSelectionList()
            sel.add(shapes[0])
            fn = om.MFnMesh(sel.getDagPath(0))
            pts = fn.getPoints(om.MSpace.kWorld)
            _counts, idx = fn.getTriangles()
        except (RuntimeError, ValueError, TypeError):
            continue
        xy = [(p.x, p.y) for p in pts]
        out += [(xy[idx[k]], xy[idx[k + 1]], xy[idx[k + 2]]) for k in range(0, len(idx) - 2, 3)]
        if len(out) > limit:
            break
    return out


def tri_box(tris):
    xs = [q[0] for t in tris for q in t]
    ys = [q[1] for t in tris for q in t]
    return min(xs), min(ys), max(xs), max(ys)


# ===========================================================================
# 5.6.26: renaming many at once
# ===========================================================================

def rename_labels(labels, prefix="", suffix="", find="", replace="", cut_start=0, cut_end=0, case=None,
                  number=None, sep=" "):
    """New texts for these labels: find -> replace, cut characters off the start / end, case ('upper', 'lower',
    'title'), a prefix and a suffix, numbered (start, step, padding, 'start' | 'end')."""
    out = []
    for i, t in enumerate(labels):
        s = t or ""
        if find:
            s = s.replace(find, replace or "")
        if cut_start:
            s = s[int(cut_start):]
        if cut_end:
            s = s[:-int(cut_end)] if int(cut_end) < len(s) else ""
        if case == "upper":
            s = s.upper()
        elif case == "lower":
            s = s.lower()
        elif case == "title":
            s = " ".join(w[:1].upper() + w[1:] for w in s.split(" "))
        s = (prefix or "") + s + (suffix or "")
        if number:
            start, step, pad, where = (list(number) + [1, 1, 1, "end"][len(number):])[:4]
            n = str(int(start) + i * int(step)).zfill(int(pad))
            s = (n + sep + s) if where == "start" else (s + sep + n)
        out.append(s.strip() if sep == " " else s)
    return out


def reading_order(items):
    """Top to bottom, then left to right (rows a little loose)."""
    return sorted(items, key=lambda i: (round(i["y"] / 12.0), i["x"]))


# ===========================================================================
# 5.6.26: shapes - the rig tool's library, a control's own curve, the closest ones
# ===========================================================================

def library():
    """[(category, [(name, points, height / width)])] - the picker's shapes and the rig tool's."""
    from gus_animtool import pickshapes
    own = [(s, PM.SHAPE_POINTS.get(s), 1.0) for s in PM.SHAPES if s not in ("poly",)]
    return [("Picker", own)] + [(c, [(n, p, a) for n, p, a in items]) for c, items in pickshapes.LIBRARY]


def find_shape(name):
    for _c, items in library():
        for n, p, a in items:
            if n == name:
                return n, p, a
    return None


def apply_shape(items, name, keep_size=True):
    """A shape by name onto the items: the picker's own by name, the rig tool's as an outline (poly)."""
    got = find_shape(name)
    if not got:
        raise RuntimeError("no shape called %s." % name)
    n, pts, aspect = got
    for it in items:
        if PM.is_frame(it) or PM.is_text(it):
            continue
        if n in PM.SHAPES:
            it["shape"] = n
            it.pop("points", None) if n != "poly" else None
        else:
            it["shape"] = "poly"
            it["points"] = [list(p) for p in pts]
            it["shape_name"] = n
            if not keep_size:
                it["h"] = round(it["w"] * aspect, 2)
    return len(items)


def view_points(pts3, view="front"):
    """Points seen from front (x, -y), side (z, -y) or top (x, z) - 0..1 across and down, and height / width."""
    if not pts3 or len(pts3) < 3:
        return None, 1.0
    if view == "side":
        pp = [(p[2], -p[1]) for p in pts3]
    elif view == "top":
        pp = [(p[0], p[2]) for p in pts3]
    else:
        pp = [(p[0], -p[1]) for p in pts3]
    xs, ys = [q[0] for q in pp], [q[1] for q in pp]
    dx, dy = max(xs) - min(xs), max(ys) - min(ys)
    if dx < 1e-9 or dy < 1e-9:
        return None, 1.0
    return [[round((q[0] - min(xs)) / dx, 4), round((q[1] - min(ys)) / dy, 4)] for q in pp], dy / dx


def best_view(pts3):
    """The view that sees the curve flattest-on (the biggest area)."""
    areas = {}
    for v in ("front", "side", "top"):
        if v == "side":
            pp = [(p[2], p[1]) for p in pts3]
        elif v == "top":
            pp = [(p[0], p[2]) for p in pts3]
        else:
            pp = [(p[0], p[1]) for p in pts3]
        xs, ys = [q[0] for q in pp], [q[1] for q in pp]
        areas[v] = (max(xs) - min(xs)) * (max(ys) - min(ys)) if pp else 0.0
    return max(("front", "side", "top"), key=lambda v: areas[v])


def _signature(pts, bins=36):
    """How far the outline reaches from its middle, round the circle (0..1)."""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    dense = []
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        for k in range(6):
            t = k / 6.0
            dense.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    reach = [0.0] * bins
    for x, y in dense:
        ang = math.atan2(y - cy, x - cx)
        k = int((ang + math.pi) / (2 * math.pi) * bins) % bins
        reach[k] = max(reach[k], math.hypot(x - cx, y - cy))
    for k in range(bins):                                   # gaps: the neighbours'
        if reach[k] == 0.0:
            reach[k] = max(reach[(k - 1) % bins], reach[(k + 1) % bins])
    top = max(reach) or 1.0
    return [r / top for r in reach]


def similar(points, n=6):
    """The library's shapes closest to an outline (0..1 points): [(name, score)] best first (turned / flipped
    don't count against)."""
    if not points or len(points) < 3:
        return []
    sig = _signature(points)
    out = []
    for _c, items in library():
        for name, pts, _a in items:
            if not pts or len(pts) < 3:
                if name in ("round", "ellipse", "ring", "pill", "rect"):
                    pts = {"rect": [[0, 0], [1, 0], [1, 1], [0, 1]]}.get(name) or \
                        [[0.5 + 0.5 * math.cos(a / 16.0 * 2 * math.pi), 0.5 + 0.5 * math.sin(a / 16.0 * 2 * math.pi)]
                         for a in range(16)]
                else:
                    continue
            other = _signature(pts)
            best = None
            for flip in (False, True):
                o = other[::-1] if flip else other
                for sh in range(len(o)):
                    d = sum(abs(a - b) for a, b in zip(sig, o[sh:] + o[:sh])) / len(sig)
                    best = d if best is None or d < best else best
            out.append((name, round(best, 4)))
    out.sort(key=lambda x: x[1])
    seen, res = set(), []
    for name, d in out:
        if name not in seen:
            seen.add(name)
            res.append((name, d))
    return res[:n]


# ===========================================================================
# 5.6.26: colours (the control's own; Maya's palette), groups by limb, badges, folding
# ===========================================================================

MAYA_PALETTE = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25], [0.6, 0.6, 0.6], [0.61, 0.0, 0.16], [0.0, 0.02, 0.38],
                [0.0, 0.0, 1.0], [0.0, 0.27, 0.1], [0.15, 0.0, 0.26], [0.78, 0.0, 0.78], [0.54, 0.28, 0.2],
                [0.25, 0.14, 0.12], [0.6, 0.15, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.25, 0.6],
                [1.0, 1.0, 1.0], [1.0, 1.0, 0.0], [0.39, 0.86, 1.0], [0.26, 1.0, 0.64], [1.0, 0.69, 0.69],
                [0.89, 0.67, 0.47], [1.0, 1.0, 0.39], [0.0, 0.6, 0.33], [0.63, 0.41, 0.19], [0.62, 0.63, 0.19],
                [0.41, 0.63, 0.19], [0.19, 0.63, 0.36], [0.19, 0.63, 0.63], [0.19, 0.4, 0.63], [0.44, 0.19, 0.63],
                [0.63, 0.19, 0.41]]


def match_colours(items, colour_of):
    """Each single-control button the colour of its control (colour_of: name -> rgb or None). Returns how
    many."""
    n = 0
    for it in items:
        if it.get("kind") != "select" or not it.get("nodes"):
            continue
        rgb = colour_of(it["nodes"][0])
        if rgb:
            it["rgb"] = [round(c, 3) for c in rgb]
            n += 1
    return n


def limb_title(settings):
    t = strip(settings)
    while True:
        t2 = re.sub(r"(?i)_?(settings|setting|switch|ctrl|ctl|crv)$", "", t)
        if t2 == t:
            break
        t = t2
    t = re.sub(r"(?i)_?(settings|setting|switch)(?=_)", "", t)
    return t.replace("_", " ").strip().upper() or strip(settings)


def group_by_limb(page, limbs):
    """A frame round each limb's buttons on the page (limbs: [(title, [control names])]) - not round buttons
    already in a frame. Returns the frames made."""
    inside = set()
    for fr in [i for i in page["items"] if PM.is_frame(i)]:
        inside.update(m["id"] for m in PM.frame_members(page, fr))
    made = []
    for title, names in limbs:
        want = set(strip(n) for n in names)
        its = [i for i in page["items"] if i.get("kind") == "select" and i["id"] not in inside and
               any(n in want for n in i.get("nodes") or [])]
        if len(its) >= 2:
            made.append(PM.group_frame(page, its, title))
            inside.update(i["id"] for i in its)
    return made


def badge_of(it):
    """The little letters in a button's corner: its own, else IK / FK / PV / gear from the name ('' = none)."""
    if "badge" in it:
        return it.get("badge") or ""
    if it.get("kind") != "select" or len(it.get("nodes") or []) != 1:
        return ""
    low = "_" + it["nodes"][0].lower() + "_"
    if re.search(r"_(pv|pole|polevector)[_\d]", low):
        return "PV"
    if re.search(r"_ik[_\d]", low):
        return "IK"
    if re.search(r"_fk[_\d]", low):
        return "FK"
    if re.search(r"_(settings?|switch)[_\d]", low):
        return "S"
    return ""


def folded_ids(page):
    """Ids of the buttons inside folded frames (only the title shows)."""
    out = set()
    for fr in [i for i in page.get("items", []) if PM.is_frame(i) and i.get("folded")]:
        out.update(m["id"] for m in PM.frame_members(page, fr))
    return out


# ===========================================================================
# 5.6.26: copy / paste, find across pages, page templates, picker backups
# ===========================================================================

def copy_items(page, items):
    """What Ctrl+C keeps: the items and the connectors between them."""
    ids = set(i["id"] for i in items)
    return {"items": copy.deepcopy(items),
            "links": copy.deepcopy([ln for ln in page.get("links") or [] if ln["a"] in ids and ln["b"] in ids])}


def paste_items(page, clip, dx=12.0, dy=12.0):
    """The copied items onto the page (new ids, moved by dx, dy; their connectors and twins between them kept).
    Returns the new items."""
    if not clip or not clip.get("items"):
        return []
    ids = {}
    made = []
    for it in copy.deepcopy(clip["items"]):
        ids[it["id"]] = PM.new_id()
        it["id"] = ids[it["id"]]
        it["x"] += dx
        it["y"] += dy
        made.append(it)
    for it in made:
        it["twin"] = ids.get(it.get("twin")) if it.get("twin") else None
        it.pop("pin", None)
    page["items"] += made
    for ln in copy.deepcopy(clip.get("links") or []):
        ln["id"], ln["a"], ln["b"] = PM.new_id(), ids[ln["a"]], ids[ln["b"]]
        links(page).append(ln)
    PM._frames_first(page)
    return made


def find_all(picker, text):
    """{page index: [ids]} - buttons whose text or control has text in it, on every page."""
    text = (text or "").strip().lower()
    out = {}
    if not text:
        return out
    for i, pg in enumerate(picker.get("pages", [])):
        got = [it["id"] for it in pg.get("items", []) if text in (it.get("label") or "").lower() or
               any(text in n.lower() for n in it.get("nodes") or [])]
        if got:
            out[i] = got
    return out


def templates():
    try:
        got = json.loads(A.opt("picker_templates", "") or "{}")
    except ValueError:
        got = {}
    return got if isinstance(got, dict) else {}


def save_template(page, name):
    got = templates()
    got[name] = copy.deepcopy(page)
    A.set_opt("picker_templates", json.dumps(got))
    return name


def delete_template(name):
    got = templates()
    got.pop(name, None)
    A.set_opt("picker_templates", json.dumps(got))


def page_from_template(picker, name):
    """A new page made from your template (its buttons find this character's controls by name)."""
    tpl = templates().get(name)
    if not tpl:
        raise RuntimeError("no template called %s." % name)
    raw = copy.deepcopy(tpl)
    raw["name"] = "__template__"
    picker["pages"].append(raw)
    i = PM.duplicate_page(picker, len(picker["pages"]) - 1, name=name)
    picker["pages"].pop(i - 1)
    return i - 1


def backup_dir(rig, base=None):
    import os
    import tempfile
    if base is None:
        try:
            base = cmds.internalVar(userAppDir=True)
        except Exception:
            base = tempfile.gettempdir()
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", rig or "rig")
    return os.path.join(base, "gus_animtool", "picker_history", safe)


def save_backup(rig, picker, base=None, keep=30, stamp=None):
    """A copy of the picker as it's saved (the last keep kept). Returns the file."""
    import os
    import time
    folder = backup_dir(rig, base)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(folder, "picker_%s.json" % stamp)
    k = 2
    while os.path.exists(path):
        path = os.path.join(folder, "picker_%s_%d.json" % (stamp, k))
        k += 1
    with open(path, "w") as f:
        json.dump(picker, f)
    files = sorted(x for x in os.listdir(folder) if x.startswith("picker_") and x.endswith(".json"))
    for old in files[:-keep]:
        try:
            os.remove(os.path.join(folder, old))
        except OSError:
            pass
    return path


def backups(rig, base=None):
    """[(file, 'YYYY-MM-DD HH:MM:SS', pages, buttons)] newest first."""
    import os
    folder = backup_dir(rig, base)
    if not os.path.isdir(folder):
        return []
    out = []
    for x in sorted(os.listdir(folder), reverse=True):
        if not (x.startswith("picker_") and x.endswith(".json")):
            continue
        path = os.path.join(folder, x)
        try:
            with open(path) as f:
                pk = json.load(f)
        except (IOError, OSError, ValueError):
            continue
        s = x[7:22]
        when = "%s-%s-%s %s:%s:%s" % (s[0:4], s[4:6], s[6:8], s[9:11], s[11:13], s[13:15]) if len(s) >= 15 else s
        out.append((path, when, len(pk.get("pages", [])), sum(len(p.get("items", [])) for p in pk.get("pages", []))))
    return out


def load_backup(path):
    with open(path) as f:
        pk = json.load(f)
    if not isinstance(pk, dict) or not isinstance(pk.get("pages"), list):
        raise RuntimeError("that file isn't a picker backup.")
    return pk


# ===========================================================================
# 5.6.26: smart guides - the page's / frames' middles to snap to, the gaps to the neighbours
# ===========================================================================

def centre_targets(page):
    """Thin items on the page's middle lines and each frame's, for snapping."""
    w, h = PM.page_size(page)
    out = [{"id": "_pc", "x": w * 0.5, "y": 0.0, "w": 0.0, "h": h}, {"id": "_pm", "x": 0.0, "y": h * 0.5, "w": w,
                                                                       "h": 0.0}]
    for fr in [i for i in page["items"] if PM.is_frame(i)]:
        cx, cy = fr["x"] + fr["w"] * 0.5, fr["y"] + fr["h"] * 0.5
        out += [{"id": "_fc", "x": cx, "y": fr["y"], "w": 0.0, "h": fr["h"]},
                {"id": "_fm", "x": fr["x"], "y": cy, "w": fr["w"], "h": 0.0}]
    return out


def gaps(box, others, reach=200.0):
    """The nearest neighbour on each side of box (x0, y0, x1, y1) with the gap: [(side, gap, (x0, y0, x1, y1)
    line to draw)] - a neighbour counts when it overlaps the box across (for left / right) or down."""
    x0, y0, x1, y1 = box
    best = {}
    for o in others:
        ox0, oy0, ox1, oy1 = o["x"], o["y"], o["x"] + o["w"], o["y"] + o["h"]
        if oy1 > y0 and oy0 < y1:
            if ox1 <= x0 and x0 - ox1 <= reach and ("left" not in best or x0 - ox1 < best["left"][0]):
                y = (max(y0, oy0) + min(y1, oy1)) * 0.5
                best["left"] = (x0 - ox1, (ox1, y, x0, y))
            if ox0 >= x1 and ox0 - x1 <= reach and ("right" not in best or ox0 - x1 < best["right"][0]):
                y = (max(y0, oy0) + min(y1, oy1)) * 0.5
                best["right"] = (ox0 - x1, (x1, y, ox0, y))
        if ox1 > x0 and ox0 < x1:
            if oy1 <= y0 and y0 - oy1 <= reach and ("up" not in best or y0 - oy1 < best["up"][0]):
                x = (max(x0, ox0) + min(x1, ox1)) * 0.5
                best["up"] = (y0 - oy1, (x, oy1, x, y0))
            if oy0 >= y1 and oy0 - y1 <= reach and ("down" not in best or oy0 - y1 < best["down"][0]):
                x = (max(x0, ox0) + min(x1, ox1)) * 0.5
                best["down"] = (oy0 - y1, (x, y1, x, oy0))
    return [(k, round(v[0], 1), v[1]) for k, v in sorted(best.items())]


def equal_nudge(box, others, tol=4.0):
    """(dx, dy) that puts the box half way between its left / right (or up / down) neighbours when it's nearly
    there - equal spacing."""
    g = dict((k, (d, ln)) for k, d, ln in gaps(box, others))
    dx = dy = 0.0
    if "left" in g and "right" in g and abs(g["left"][0] - g["right"][0]) <= tol * 2:
        dx = (g["right"][0] - g["left"][0]) * 0.5
    if "up" in g and "down" in g and abs(g["up"][0] - g["down"][0]) <= tol * 2:
        dy = (g["down"][0] - g["up"][0]) * 0.5
    return dx, dy
