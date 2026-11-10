"""
Gus Animtool - the engine: characters, controls, IK / FK, spaces, pose, teach a limb, picker, pose library.
The window is in ui.py; the newer tools in tween.py, keys.py, hotkeys.py. Works on any rig; with
Gus_Rigtool rigs it reads what the builder wrote (limbs, IK/FK, spaces) by itself.

    import gus_animtool; gus_animtool.show()

(the old  import gus_anim; gus_anim.show()  still works)
"""

import json
import math
import traceback

import maya.cmds as cmds

from gus_animtool import __version__ as VERSION
# the defaults below are written by Gus_Rigtool when it makes this file (Build tab, step 5)
DEFAULT_PAIRS = [("L_", "R_")]                    # left / right name tokens
DEFAULT_AXIS = 0                                  # mirror plane: 0 X, 1 Y, 2 Z
DEFAULT_CENTER = [0.0, 0.0, 0.0]
DEFAULT_SUFFIX = "_ctrl"                          # control names end with this ('' = any curve)


def _load_defaults():
    """Gus_Rigtool writes your naming (left / right tokens, mirror plane, control suffix) to defaults.json when
    it makes the animator tools (Build > 5)."""
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "defaults.json")
    if not os.path.isfile(path):
        return
    try:
        with open(path) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return
    g = globals()
    if d.get("pairs"):
        g["DEFAULT_PAIRS"] = [tuple(p) for p in d["pairs"]]
    for key, name in (("axis", "DEFAULT_AXIS"), ("center", "DEFAULT_CENTER"), ("suffix", "DEFAULT_SUFFIX")):
        if key in d:
            g[name] = d[key]


_load_defaults()

WINDOW = "gusAnimWorkspace"
P = "gusAnim_"                                    # UI names and optionVars
HEADER_BG = (0.17, 0.23, 0.29)
MAIN_BG = (0.26, 0.42, 0.56)
OK_BG, WARN_BG = (0.20, 0.36, 0.22), (0.52, 0.36, 0.10)
ROOT = "(no namespace)"
TWIN_ATTR = "rtMirrorTwin"


# ===========================================================================
# small helpers
# ===========================================================================

class Undo(object):
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        cmds.undoInfo(openChunk=True, chunkName=self.name)

    def __exit__(self, *exc):
        cmds.undoInfo(closeChunk=True)


class NoUndo(object):
    """Changes that shouldn't be undo steps (live previews); the undo state is put back as it was."""
    def __enter__(self):
        self.was = cmds.undoInfo(query=True, stateWithoutFlush=True)
        if self.was:
            cmds.undoInfo(stateWithoutFlush=False)

    def __exit__(self, *exc):
        if self.was:
            cmds.undoInfo(stateWithoutFlush=True)


def time_curves(nodes):
    """The animation curves of the nodes that run on time - not set driven keys (those would be moved / scaled
    by mistake). Each curve once, in order."""
    out = []
    if not nodes:                                      # an empty list would mean 'the selection' to Maya
        return out
    for c in cmds.keyframe(nodes, query=True, name=True) or []:
        if c in out:
            continue
        try:
            kind = cmds.nodeType(c) or ""
        except Exception:
            kind = ""
        if not kind or kind.startswith("animCurveT"):
            out.append(c)
    return out


def is_rotation(curve):
    """An angle curve (rotate), by its type - not by its name."""
    try:
        kind = cmds.nodeType(curve) or ""
    except Exception:
        kind = ""
    return kind == "animCurveTA" if kind else "rotate" in curve


def message(text, level="ok"):
    try:
        if cmds.text(P + "Status", exists=True):
            cmds.text(P + "Status", edit=True, label="  " + text, backgroundColor=OK_BG if level == "ok" else WARN_BG)
    except RuntimeError:
        pass
    if level == "ok":
        print("Gus Animtool: " + text)
    else:
        cmds.warning("Gus Animtool: " + text)


def guard(fn):
    """UI callbacks: expected problems in a window, others with the details in the Script Editor."""
    def run(*args):
        try:
            return fn(*args)
        except (RuntimeError, ValueError) as e:
            message(str(e), "warn")
            try:
                cmds.confirmDialog(title="Gus Animtool", message=str(e), button=["OK"])
            except RuntimeError:
                pass
        except Exception as e:
            print(traceback.format_exc())
            message("error: %s (details in the Script Editor)" % e, "warn")
    return run


def opt(key, default):
    name = P + key
    if not cmds.optionVar(exists=name):
        return default
    v = cmds.optionVar(query=name)
    return type(default)(v) if not isinstance(default, (list, tuple)) else v


def set_opt(key, value):
    name = P + key
    if isinstance(value, bool) or isinstance(value, int):
        cmds.optionVar(intValue=(name, int(value)))
    elif isinstance(value, float):
        cmds.optionVar(floatValue=(name, value))
    else:
        cmds.optionVar(stringValue=(name, str(value)))


def short(n):
    return n.split("|")[-1]


def namespace_of(n):
    s = short(n)
    return s.rsplit(":", 1)[0] + ":" if ":" in s else ""


def long_name(n):
    found = cmds.ls(n, long=True) or []
    return found[0] if len(found) == 1 else None


def resolve(name, ns):
    """A name stored by Gus_Rigtool (no namespace) in this character."""
    return long_name(ns + name) or long_name(name)


def track_selection_order():
    """Maya only remembers the order things were selected in when this is on (Gus_Rigtool turns it on too)."""
    try:
        if not cmds.selectPref(query=True, trackSelectionOrder=True):
            cmds.selectPref(trackSelectionOrder=True)
    except (RuntimeError, TypeError, AttributeError):
        pass


def selected():
    sel = cmds.ls(orderedSelection=True, long=True, objectsOnly=True) or \
        cmds.ls(selection=True, long=True, objectsOnly=True) or []
    out = []
    for n in sel:
        if cmds.objectType(n, isAType="shape"):
            n = (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]
        if n and cmds.objectType(n, isAType="transform") and n not in out:
            out.append(n)
    return out


def with_attr(attr, ns=None):
    nodes = cmds.ls("*." + attr, recursive=True, objectsOnly=True, long=True) or []
    out = []
    for n in nodes:
        if n not in out and (ns is None or namespace_of(n) == ns):
            out.append(n)
    return out


def meta(node, key):
    """A Gus_Rigtool list stored on a settings control, as nodes of this character."""
    try:
        text = cmds.getAttr(node + "." + key) if cmds.attributeQuery(key, node=node, exists=True) else ""
    except RuntimeError:
        text = ""
    return [x for x in (text or "").split() if x]


def meta_nodes(node, key, ns):
    return [r for r in (resolve(x, ns) for x in meta(node, key)) if r]


def meta_str(node, key):
    try:
        if cmds.attributeQuery(key, node=node, exists=True):
            return cmds.getAttr(node + "." + key) or ""
    except RuntimeError:
        pass
    return ""


# ===========================================================================
# matrices (plain lists of 16, Maya's layout)
# ===========================================================================

IDENTITY = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
ORDERS = [(0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1), (1, 0, 2), (2, 1, 0)]
ORDER_NAMES = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]


def mul(a, b):
    return [sum(a[r * 4 + k] * b[k * 4 + c] for k in range(4)) for r in range(4) for c in range(4)]


def inverse(m):
    a = [list(m[r * 4:r * 4 + 4]) + [1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]
    for col in range(4):
        piv = max(range(col, 4), key=lambda r: abs(a[r][col]))
        if abs(a[piv][col]) < 1e-12:
            raise ValueError("a matrix can't be inverted (zero scale?)")
        a[col], a[piv] = a[piv], a[col]
        p = a[col][col]
        a[col] = [v / p for v in a[col]]
        for r in range(4):
            if r != col and a[r][col]:
                f = a[r][col]
                a[r] = [v - f * w for v, w in zip(a[r], a[col])]
    return [a[r][4 + c] for r in range(4) for c in range(4)]


def reflection(axis, center):
    m = list(IDENTITY)
    m[axis * 4 + axis] = -1.0
    m[12 + axis] = 2.0 * center[axis]
    return m


def _axis_rot(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    m = list(IDENTITY)
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    m[i * 4 + i], m[i * 4 + j], m[j * 4 + i], m[j * 4 + j] = c, s, -s, c
    return m


def euler_matrix(r, order=0):
    i, j, k = ORDERS[order]
    return mul(mul(_axis_rot(i, r[i]), _axis_rot(j, r[j])), _axis_rot(k, r[k]))


def matrix_euler(m, order=0):
    i, j, k = ORDERS[order]
    par = 1.0 if (i, j, k) in ORDERS[:3] else -1.0
    n = [[m[c * 4 + r] for c in range(3)] for r in range(3)]
    sb = max(-1.0, min(1.0, -par * n[k][i]))
    b = math.asin(sb)
    if abs(math.cos(b)) > 1e-6:
        a = math.atan2(par * n[k][j], n[k][k])
        c = math.atan2(par * n[j][i], n[i][i])
    else:
        a = math.atan2(-par * n[j][k], n[j][j])
        c = 0.0
    out = [0.0, 0.0, 0.0]
    out[i], out[j], out[k] = math.degrees(a), math.degrees(b), math.degrees(c)
    return out


def compose(t, r, s, order=0, jo=None):
    m = [s[0], 0, 0, 0, 0, s[1], 0, 0, 0, 0, s[2], 0, 0, 0, 0, 1.0]
    m = mul(m, euler_matrix(r, order))
    if jo is not None:
        m = mul(m, euler_matrix(jo, 0))
    m[12:15] = [float(v) for v in t]
    return m


def decompose(m, order=0, jo=None):
    t = list(m[12:15])
    rs = list(m)
    rs[12:15] = [0.0, 0.0, 0.0]
    if jo is not None:
        rs = mul(rs, inverse(euler_matrix(jo, 0)))
    rows = [rs[r * 4:r * 4 + 3] for r in range(3)]
    s = [math.sqrt(sum(v * v for v in row)) or 1.0 for row in rows]
    rows = [[v / sc for v in row] for row, sc in zip(rows, s)]
    det = (rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
           - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
           + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0]))
    if det < 0:
        s[0] = -s[0]
        rows[0] = [-v for v in rows[0]]
    rot = list(IDENTITY)
    for r in range(3):
        rot[r * 4:r * 4 + 3] = rows[r]
    return t, matrix_euler(rot, order), s


def world(node):
    return list(cmds.getAttr(node + ".worldMatrix[0]"))


def position(m):
    return list(m[12:15])


def _norm(v):
    length = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / length for x in v]


def _det3(m):
    return (m[0] * (m[5] * m[10] - m[6] * m[9]) - m[1] * (m[4] * m[10] - m[6] * m[8]) +
            m[2] * (m[4] * m[9] - m[5] * m[8]))


def set_world(node, m, translate=True, rotate=True):
    """Put a control at world matrix m (translate / rotate; locked or connected channels are left).
    Works for mirrored controls too (a -1 scale above them)."""
    parent = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
    pw = world(parent) if parent else list(IDENTITY)
    if _det3(pw) < 0:
        rot = list(IDENTITY)
        for r in range(3):
            rot[r * 4:r * 4 + 3] = _norm(m[r * 4:r * 4 + 3])
        if _det3(rot) > 0:
            rot[0:3] = [-x for x in rot[0:3]]
        rot[12:15] = list(m[12:15])
        t, r_, _s = decompose(mul(rot, inverse(pw)), cmds.getAttr(node + ".rotateOrder"))
        for attrs, values, on in ((("tx", "ty", "tz"), t, translate), (("rx", "ry", "rz"), r_, rotate)):
            for a, v in zip(attrs, values):
                try:
                    if on and cmds.getAttr(node + "." + a, settable=True):
                        cmds.setAttr(node + "." + a, v)
                except RuntimeError:
                    pass
        return
    if rotate:
        order = cmds.getAttr(node + ".rotateOrder")
        rot = list(IDENTITY)
        for r in range(3):
            rot[r * 4:r * 4 + 3] = _norm(m[r * 4:r * 4 + 3])
        try:
            cmds.xform(node, worldSpace=True, rotation=matrix_euler(rot, order), rotateOrder=ORDER_NAMES[order])
        except RuntimeError:
            pass
    if translate:
        try:
            cmds.xform(node, worldSpace=True, translation=m[12:15])
        except RuntimeError:
            pass


def pole_position(a, b, c):
    sub = lambda p, q: [x - y for x, y in zip(p, q)]
    dot = lambda p, q: sum(x * y for x, y in zip(p, q))
    ac = sub(c, a)
    t = dot(sub(b, a), ac) / max(dot(ac, ac), 1e-9)
    on_line = [x + y * t for x, y in zip(a, ac)]
    out = sub(b, on_line)
    if math.sqrt(dot(out, out)) < 1e-6 * max(math.sqrt(dot(ac, ac)), 1e-6):
        out = [ac[2], 0.0, -ac[0]] if abs(_norm(ac)[1]) < 0.9 else [0.0, -ac[2], ac[1]]
    dist = (math.sqrt(dot(sub(b, a), sub(b, a))) + math.sqrt(dot(sub(c, b), sub(c, b)))) * 0.5
    n = _norm(out)
    return [x + y * dist for x, y in zip(b, n)]


# ===========================================================================
# characters and their controls
# ===========================================================================

# ===========================================================================
# rig profiles: how to read a rig (any rig), saved per rig in the shared folder - every scene uses it
# ===========================================================================

_profiles = {}


def rig_name(ns=None):
    """The rig's name for its profile: the namespace without ':' and its numbers (hare1: -> hare), or 'rig'."""
    import re
    ns = current_character() if ns is None else ns
    name = re.sub(r"\d+$", "", (ns or "").strip(":").split(":")[-1]) or "rig"
    return name


def profile_path(name):
    import os
    folder = os.path.join(library_root(), "profiles")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    return os.path.join(folder, name + ".json")


def profile(ns=None):
    """{'suffix', 'left', 'right', 'control_set', 'control_group', 'picker'} of the rig (missing keys: the
    general options)."""
    import os
    name = rig_name(ns)
    try:
        path = profile_path(name)
        stamp = os.path.getmtime(path) if os.path.isfile(path) else None
    except Exception:                               # no Maya UI / folder: the general options
        return {}
    cached = _profiles.get(name)
    if cached and cached[0] == stamp:
        return cached[1]
    data = {}
    if stamp:
        try:
            with open(path) as f:
                data = json.load(f) or {}
        except (OSError, ValueError):
            data = {}
    _profiles[name] = (stamp, data)
    return data


def save_profile(data, ns=None):
    path = profile_path(rig_name(ns))
    with open(path, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    _profiles.pop(rig_name(ns), None)
    return path


def suffix():
    p = profile()
    return p["suffix"] if "suffix" in p else opt("suffix", DEFAULT_SUFFIX)


_members_cache = {}


def _profile_members(ns):
    """Controls named by the rig profile: a selection set's members, or the curves under a group (kept for a
    second: a picker / select-all asks for every curve in a row)."""
    import time
    hit = _members_cache.get(ns)
    if hit and time.time() - hit[0] < 1.0:
        return hit[1]
    out = _read_members(ns)
    _members_cache[ns] = (time.time(), out)
    return out


def _read_members(ns):
    p = profile(ns)
    out = set()
    if p.get("control_set"):
        found = cmds.ls(ns + p["control_set"]) or cmds.ls(p["control_set"]) or []
        if found:
            members = cmds.sets(found[0], query=True) or []
            if members:                                      # an empty list would list every node
                out.update(cmds.ls(members, long=True) or [])
    if p.get("control_group"):
        found = cmds.ls(ns + p["control_group"], long=True) or cmds.ls(p["control_group"], long=True) or []
        for g in found[:1]:
            for c in cmds.listRelatives(g, allDescendents=True, type="nurbsCurve", fullPath=True) or []:
                out.update(cmds.listRelatives(c, parent=True, fullPath=True) or [])
    return out if (p.get("control_set") or p.get("control_group")) else None


def named_suffix():
    """The control suffix you set yourself (rig profile or options), or None: then controls are found
    automatically (auto_controls)."""
    p = profile()
    if "suffix" in p:
        return p["suffix"]
    if cmds.optionVar(exists=P + "suffix"):
        v = cmds.optionVar(query=P + "suffix")
        if v != DEFAULT_SUFFIX:
            return v
    return None


def is_control(n):
    if cmds.attributeQuery("gusRole", node=n, exists=True):          # a Gus_Rigtool guide
        return False
    ns = namespace_of(n)
    members = _profile_members(ns)
    if members is not None:
        return n in members
    shapes = cmds.listRelatives(n, shapes=True, type="nurbsCurve", fullPath=True, noIntermediate=True) or []
    if not shapes:
        return False
    named = named_suffix()
    if named is not None:
        sx = [s.strip() for s in named.split(",") if s.strip()]
        return not sx or any(short(n).split(":")[-1].endswith(s) for s in sx)
    return long_name(n) in auto_controls(ns)


# ---------------------------------------------------------------------------
# finding the controls of any rig (no names needed)
# ---------------------------------------------------------------------------

AUTO_SUFFIXES = ("_ctrl", "_ctl", "_con", "_cntrl", "_control", "_anim", "_cc", "_ac", "ctrl", "ctl")
_FREE_SOURCES = ("animCurveTL", "animCurveTA", "animCurveTU", "animCurveTT", "pairBlend", "character")
_auto_cache = {}
_auto_info = {}


def _statically_hidden(node):
    """Hidden for good: it or a parent has visibility off with nothing driving it (an IK / FK switch drives the
    visibility of controls it hides - those still count), or it's templated / shown as reference."""
    n = node
    while n:
        try:
            if not cmds.getAttr(n + ".visibility") and not cmds.listConnections(n + ".visibility", source=True,
                                                                                   destination=False):
                return True
            if cmds.getAttr(n + ".template"):
                return True
            if cmds.attributeQuery("overrideEnabled", node=n, exists=True) and cmds.getAttr(n + ".overrideEnabled"):
                if cmds.getAttr(n + ".overrideDisplayType") in (1, 2):
                    return True
                if not cmds.getAttr(n + ".overrideVisibility") and not cmds.listConnections(
                        n + ".overrideVisibility", source=True, destination=False):
                    return True
        except (RuntimeError, ValueError, TypeError):
            pass
        n = (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]
    return False


def _free(plug):
    """Something an animator can key: keyable, unlocked, and only animation (or nothing) feeding it."""
    try:
        if cmds.getAttr(plug, lock=True):
            return False
        if not cmds.getAttr(plug, keyable=True):
            return False
    except (RuntimeError, ValueError, TypeError):
        return False
    src = cmds.listConnections(plug, source=True, destination=False, skipConversionNodes=True) or []
    return all(cmds.nodeType(x) in _FREE_SOURCES or cmds.nodeType(x).startswith("animCurve") for x in src)


def animatable(node):
    """A curve an animator would grab: a free translate / rotate / scale channel or a keyable attribute of its
    own, and not hidden for good."""
    attrs = [a + x for a in ("translate", "rotate", "scale") for x in "XYZ"]
    attrs += [a for a in cmds.listAttr(node, userDefined=True, keyable=True) or [] if "." not in a]
    if not any(_free(node + "." + a) for a in attrs):
        return False
    return not _statically_hidden(node)


def _how_found(t):
    base = short(t).split(":")[-1]
    low = base.lower()
    if DEFAULT_SUFFIX and base.endswith(DEFAULT_SUFFIX):
        return "name (%s)" % DEFAULT_SUFFIX
    if any(low.endswith(s) for s in AUTO_SUFFIXES) and not _statically_hidden(t):
        return "name (%s)" % next(s for s in AUTO_SUFFIXES if low.endswith(s))
    try:
        if cmds.listConnections(t + ".message", type="controller", source=False, destination=True):
            return "controller tag"
    except (RuntimeError, ValueError, TypeError):
        pass
    if animatable(t):
        return "channels"
    return None


SET_WORDS = ("control", "ctrl", "ctl")


def _control_set_members(ns):
    """Curves in the scene's controls sets (a set named like 'ControlSet', 'AllControls', 'ctrl_set')."""
    out = set()
    try:
        sets = cmds.ls(type="objectSet") or []
    except (RuntimeError, TypeError):
        return out
    for st in sets:
        if namespace_of(st) != ns or not any(w in short(st).split(":")[-1].lower() for w in SET_WORDS):
            continue
        try:
            members = cmds.sets(st, query=True) or []
        except (RuntimeError, TypeError, ValueError):
            continue
        for m in cmds.ls(members, long=True, type="transform") or []:
            if cmds.listRelatives(m, shapes=True, type="nurbsCurve", noIntermediate=True):
                out.add(m)
    return out


def auto_controls(ns="", curves=None):
    """{long name} of a character's controls, found without a set suffix: names ending like a control (_ctrl,
    _CTL, _con, ... any case), Maya controller tags, and any other curve an animator can key (free channels, not
    hidden for good). Kept until the curves in the scene change (or 10 seconds)."""
    import time
    now = time.time()
    hit = _auto_cache.get(ns)
    if hit and curves is None and now - hit[1] < 0.5:      # asked again straight away (one action, per curve)
        return hit[3]
    if curves is None:
        curves = cmds.ls(type="nurbsCurve", long=True, noIntermediate=True) or []
    if hit and hit[2] == len(curves) and now - hit[0] < 10.0:
        _auto_cache[ns] = (hit[0], now, hit[2], hit[3])
        return hit[3]
    out, how = set(), {}
    in_sets = _control_set_members(ns)
    for crv in curves:
        t = (cmds.listRelatives(crv, parent=True, fullPath=True) or [None])[0]
        if not t or t in out or namespace_of(t) != ns:
            continue
        if cmds.attributeQuery("gusRole", node=t, exists=True):
            continue
        found = "a controls set" if t in in_sets else _how_found(t)
        if found:
            out.add(t)
            how[found] = how.get(found, 0) + 1
    _auto_cache[ns] = (now, now, len(curves), out)
    _auto_info[ns] = how
    return out


def found_text(ns=""):
    """'142 controls found: 120 by name (_ctrl), 22 by their channels' - how the controls were found."""
    if _profile_members(ns) is not None:
        return "controls: the rig profile's set / group"
    named = named_suffix()
    if named is not None:
        return "controls: names ending in %s (your setting)" % named
    n = len(auto_controls(ns))
    how = _auto_info.get(ns, {})
    words = {"channels": "by their channels (hand-made)", "controller tag": "by Maya controller tags"}
    parts = ["%d %s" % (c, words.get(k, "by " + k)) for k, c in sorted(how.items(), key=lambda kv: -kv[1])]
    return "%d controls found automatically%s" % (n, (": " + ", ".join(parts)) if parts else "")


def characters():
    """[namespace] of every character in the scene ('' = no namespace)."""
    out = []
    for crv in cmds.ls(type="nurbsCurve", long=True, noIntermediate=True) or []:
        ns = namespace_of(cmds.listRelatives(crv, parent=True, fullPath=True)[0])
        if ns not in out:
            out.append(ns)
    return sorted(out)


def current_character():
    try:
        label = cmds.optionMenu(P + "Char", query=True, value=True)
    except (RuntimeError, AttributeError, TypeError):
        return ""
    label = (label or "").split("   ")[0]
    return "" if label in ("", ROOT) else label


def character_controls(ns=None):
    ns = current_character() if ns is None else ns
    curves = cmds.ls(type="nurbsCurve", long=True, noIntermediate=True) or []
    auto = None
    if _profile_members(ns) is None and named_suffix() is None:
        auto = auto_controls(ns, curves)                   # worked out once for the whole list
    out, seen = [], set()
    for crv in curves:
        t = cmds.listRelatives(crv, parent=True, fullPath=True)[0]
        if t in seen or namespace_of(t) != ns:
            continue
        seen.add(t)
        if (t in auto) if auto is not None else is_control(t):
            out.append(t)
    return out


# ===========================================================================
# IK / FK (Gus_Rigtool limbs and chains)
# ===========================================================================

def settings_of(node):
    """The IK/FK settings control of a selected control (or the settings control itself)."""
    if meta_str(node, "gusBlend"):
        return node
    ns = namespace_of(node)
    name = short(node).split(":")[-1]
    for s in with_attr("gusBlend", ns):
        if not meta_str(s, "gusBlend"):
            continue
        for key in ("gusFkCtrls", "gusIkCtrl", "gusPvCtrl", "gusIkCtrls", "gusTweaks", "gusHockCtrl"):
            if name in meta(s, key):
                return s
    return None


def limbs_of_selection():
    out = []
    for n in selected():
        s = settings_of(n) or taught_of(n)
        if s and s not in out:
            out.append(s)
    if not out:
        raise RuntimeError("select a control of a limb or chain with an IK/FK switch (a Gus_Rigtool rig, or a "
                           "limb you taught in 'Teach a limb').")
    return out


def blend_plug(s):
    return s + "." + meta_str(s, "gusBlend")


def limb_controls(s, which="all"):
    if isinstance(s, Taught):
        return s.controls(which)
    ns = namespace_of(s)
    fk = meta_nodes(s, "gusFkCtrls", ns)
    ik = meta_nodes(s, "gusIkCtrl", ns) + meta_nodes(s, "gusPvCtrl", ns) + meta_nodes(s, "gusIkCtrls", ns) + \
        meta_nodes(s, "gusHockCtrl", ns)
    tw = meta_nodes(s, "gusTweaks", ns)
    return {"fk": fk, "ik": ik, "tweaks": tw, "all": fk + ik + tw + [s]}[which]


def _scale(s, ns):
    plug = meta_str(s, "gusScalePlug")
    if plug:
        node, attr = plug.split(".", 1)
        node = resolve(node, ns)
        if node:
            try:
                return float(cmds.getAttr(node + "." + attr))
            except (RuntimeError, ValueError):
                pass
    return 1.0


def _in_fk(s):
    if isinstance(s, Taught):
        return s.in_fk()
    return cmds.getAttr(blend_plug(s)) < 0.5


def _switch_nodes(s):
    """The node(s) holding the IK/FK switch (keyed with the controls)."""
    if isinstance(s, Taught):
        return [s.switch_node()] if s.switch_node() else []
    return [s]


def _to_fk(s, exact=True):
    if isinstance(s, Taught):
        return s.to_fk()
    ns = namespace_of(s)
    if meta_str(s, "gusChain"):
        before = [world(b) for b in meta_nodes(s, "gusBind", ns)]
        ctrls, ikj = meta_nodes(s, "gusFkCtrls", ns), meta_nodes(s, "gusIkJoints", ns)
        rest = [float(r) for r in meta(s, "gusFkRest")]
        gs = _scale(s, ns)
        for k in range(len(ctrls) - 1):
            if k < len(rest) and rest[k] > 1e-9 and cmds.attributeQuery("length", node=ctrls[k], exists=True):
                a, b = position(world(ikj[k])), position(world(ikj[k + 1]))
                d = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
                try:
                    cmds.setAttr(ctrls[k] + ".length", d / (rest[k] * gs))
                except RuntimeError:
                    pass
        for c, j in zip(ctrls, ikj):
            set_world(c, world(j), translate=False)
        cmds.setAttr(blend_plug(s), 0)
        if exact:
            _exact(s, ns, before)
        return
    fk, ikj = meta_nodes(s, "gusFkCtrls", ns), meta_nodes(s, "gusIkJoints", ns)
    for c, j in zip(fk, ikj):
        set_world(c, world(j), translate=False)
    cmds.setAttr(blend_plug(s), 0)


def _to_ik(s, exact=True):
    if isinstance(s, Taught):
        return s.to_ik()
    ns = namespace_of(s)
    if meta_str(s, "gusChain"):
        before = [world(b) for b in meta_nodes(s, "gusBind", ns)]
        ctrls, fkj = meta_nodes(s, "gusIkCtrls", ns), meta_nodes(s, "gusFkJointsAtCtrls", ns)
        order = [0, len(ctrls) - 1] + list(range(1, len(ctrls) - 1)) if len(ctrls) > 1 else [0]
        for k in order:
            if k < len(fkj):
                set_world(ctrls[k], world(fkj[k]))
        cmds.setAttr(blend_plug(s), 1)
        if exact:
            _exact(s, ns, before)
        return
    ik = (meta_nodes(s, "gusIkCtrl", ns) or [None])[0]
    pv = (meta_nodes(s, "gusPvCtrl", ns) or [None])[0]
    ikj, fkj = meta_nodes(s, "gusIkJoints", ns), meta_nodes(s, "gusFkJoints", ns)
    for attr in meta(s, "gusFootAttrs"):
        if ik and cmds.objExists(ik + "." + attr):
            try:
                cmds.setAttr(ik + "." + attr, 0)
            except RuntimeError:
                pass
    try:
        end = int(meta_str(s, "gusEnd") or 2)
    except ValueError:
        end = 2
    if ik and len(ikj) > end and len(fkj) > end:
        offset = mul(world(ik), inverse(world(ikj[end])))
        set_world(ik, mul(offset, world(fkj[end])))
    if pv and len(fkj) >= 3:
        a, b, c = [position(world(j)) for j in fkj[:3]]
        try:
            cmds.xform(pv, worldSpace=True, translation=pole_position(a, b, c))
        except RuntimeError:
            pass
    hock = (meta_nodes(s, "gusHockCtrl", ns) or [None])[0]
    if hock and len(ikj) > 2 and len(fkj) > 2:                 # quadruped leg: the hock angle too
        _match_hock(hock, ikj[2], fkj[2])
    cmds.setAttr(blend_plug(s), 1)


def _rotation_between(a, b):
    """Row-vector rotation matrix turning direction a onto direction b."""
    a, b = _norm(a), _norm(b)
    axis = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    sn = math.sqrt(sum(v * v for v in axis))
    c = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
    if sn < 1e-9:
        return list(IDENTITY)
    x, y, z = [v / sn for v in axis]
    ang = math.atan2(sn, c)
    cs, si, t = math.cos(ang), math.sin(ang), 1 - math.cos(ang)
    col = [[t * x * x + cs, t * x * y - si * z, t * x * z + si * y],
           [t * x * y + si * z, t * y * y + cs, t * y * z - si * x],
           [t * x * z - si * y, t * y * z + si * x, t * z * z + cs]]
    m = list(IDENTITY)
    for r in range(3):
        for k in range(3):
            m[r * 4 + k] = col[k][r]
    return m


def _match_hock(hock, ik_hock, fk_hock, iterations=3):
    """Turn the hock control (pivot at the ball) so the IK hock goes where the FK hock is."""
    for _ in range(iterations):
        hm = world(hock)
        pivot = hm[12:15]
        cur = [x - y for x, y in zip(position(world(ik_hock)), pivot)]
        want = [x - y for x, y in zip(position(world(fk_hock)), pivot)]
        if max(map(abs, cur)) < 1e-9 or max(map(abs, want)) < 1e-9:
            return
        new = mul(hm, _rotation_between(cur, want))
        new[12:15] = pivot
        set_world(hock, new, translate=False)


def _exact(s, ns, before):
    tw = meta_nodes(s, "gusTweaks", ns)
    if meta_str(s, "gusExact") != "1" or not tw or len(tw) != len(before):
        return
    for c, m in zip(tw, before):
        set_world(c, m)


def _key(nodes, frame, insert=False):
    """Key every keyable channel of nodes at frame (insert: keep the curve's shape where animated)."""
    for n in nodes:
        attrs = cmds.listAttr(n, keyable=True, unlocked=True) or []
        for a in attrs:
            plug = n + "." + a
            try:
                animated = bool(cmds.listConnections(plug, source=True, destination=False, type="animCurve"))
                if insert and animated:
                    cmds.setKeyframe(plug, time=frame, insert=True)
                else:
                    cmds.setKeyframe(plug, time=frame)
            except RuntimeError:
                pass


def switch(to="toggle"):
    """IK/FK switch of the selected limbs / chains with no jump. to: 'fk', 'ik' or 'toggle'."""
    limbs = limbs_of_selection()
    keying = opt("key_switch", 1)
    frame = cmds.currentTime(query=True)
    with Undo("gusAnimSwitch"):
        for s in limbs:
            mode = to
            if to == "toggle":
                mode = "ik" if _in_fk(s) else "fk"
            nodes = limb_controls(s) + [x for x in _switch_nodes(s) if x not in limb_controls(s)]
            if keying:
                _key(nodes, frame - 1, insert=True)
            (_to_fk if mode == "fk" else _to_ik)(s)
            if keying:
                _key(nodes, frame)
    message("switched %d limb(s)%s%s." % (len(limbs), {"fk": " to FK", "ik": " to IK"}.get(to, ""),
                                          " (keyed)" if keying else ""))


def bake(to="fk"):
    """Switch every frame of the range and key it: the motion stays, the other mode holds it."""
    limbs = limbs_of_selection()
    start = int(cmds.intField(P + "Start", query=True, value=True))
    end = int(cmds.intField(P + "End", query=True, value=True))
    if end < start:
        raise ValueError("the end frame is before the start frame.")
    now = cmds.currentTime(query=True)
    fn = _to_fk if to == "fk" else _to_ik
    with Undo("gusAnimBake"):
        cmds.refresh(suspend=True)
        try:
            for f in range(start, end + 1):
                cmds.currentTime(f, update=True)
                for s in limbs:
                    fn(s, exact=False)
                    _key(limb_controls(s, to) + _switch_nodes(s), f)
        finally:
            cmds.refresh(suspend=False)
            cmds.currentTime(now, update=True)
    message("baked %d limb(s) to %s, frames %d-%d." % (len(limbs), to.upper(), start, end))


# ===========================================================================
# Teach a limb: IK/FK switch for rigs not made with Gus_Rigtool
# ===========================================================================
#   You pick the 3 FK controls, the 3 joints they move (upper, middle, end), the IK control, the pole
#   vector and the switch attribute, in a pose where FK and IK line up (the rest pose). Gus Anim saves
#   how each control sits on its joint, so later it can put the FK controls on the joints (to FK) or the
#   IK control and pole vector on them (to IK). Saved in the scene (node gusAnim_taught), per character,
#   and to a file to use in other scenes.

TAUGHT_NODE = "gusAnim_taught"


def bare(n):
    """'|grp|hare:L_arm_ctrl' -> 'L_arm_ctrl' (no path, no namespace)."""
    return short(n).split(":")[-1]


_strip = bare


def taught_data():
    if not cmds.objExists(TAUGHT_NODE):
        return {}
    try:
        return json.loads(cmds.getAttr(TAUGHT_NODE + ".limbs") or "{}")
    except (ValueError, RuntimeError):
        return {}


def _write_taught(data):
    if not cmds.objExists(TAUGHT_NODE):
        cmds.createNode("network", name=TAUGHT_NODE)
        cmds.addAttr(TAUGHT_NODE, longName="limbs", dataType="string")
    cmds.setAttr(TAUGHT_NODE + ".limbs", json.dumps(data, sort_keys=True), type="string")


class Taught(object):
    """A taught limb in one character (namespace)."""

    def __init__(self, name, data, ns):
        self.name, self.d, self.ns = name, data, ns

    def __eq__(self, other):
        return isinstance(other, Taught) and (self.name, self.ns) == (other.name, other.ns)

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.name, self.ns))

    def _n(self, name):
        return resolve(name, self.ns) if name else None

    def fk(self):
        return [self._n(x) for x in self.d["fk"]]

    def joints(self):
        return [self._n(x) for x in self.d["joints"]]

    def ik(self):
        return self._n(self.d["ik"])

    def pv(self):
        return self._n(self.d.get("pv"))

    def switch_node(self):
        node = self.d.get("switch", "").split(".")[0]
        return self._n(node) if node else None

    def switch_plug(self):
        node = self.switch_node()
        return node + "." + self.d["switch"].split(".", 1)[1] if node else None

    def controls(self, which="all"):
        fk = [x for x in self.fk() if x]
        ik = [x for x in (self.ik(), self.pv()) if x]
        return {"fk": fk, "ik": ik, "tweaks": [], "all": fk + ik}[which]

    def in_fk(self):
        plug = self.switch_plug()
        if not plug:
            return True
        v = cmds.getAttr(plug)
        return abs(v - float(self.d["fk_value"])) <= abs(v - float(self.d["ik_value"]))

    def _check(self):
        missing = [x for x in self.d["fk"] + self.d["joints"] + [self.d["ik"]] if not self._n(x)]
        if missing:
            raise RuntimeError("taught limb '%s': %s not found in this character." % (self.name, ", ".join(missing)))

    def to_fk(self):
        self._check()
        js = [world(j) for j in self.joints()]                 # read first: the joints follow the switch
        for c, j, off in zip(self.fk(), js, self.d["fk_off"]):
            set_world(c, mul(off, j), translate=False)
        if self.switch_plug():
            cmds.setAttr(self.switch_plug(), float(self.d["fk_value"]))

    def to_ik(self):
        self._check()
        js = [world(j) for j in self.joints()]
        set_world(self.ik(), mul(self.d["ik_off"], js[2]))
        if self.pv():
            a, b, c = [position(m) for m in js]
            try:
                cmds.xform(self.pv(), worldSpace=True, translation=pole_position(a, b, c))
            except RuntimeError:
                pass
        if self.switch_plug():
            cmds.setAttr(self.switch_plug(), float(self.d["ik_value"]))


def taught_of(node):
    """The taught limb a control belongs to (FK, IK, pole vector or the switch node), or None."""
    name, ns = _strip(node), namespace_of(node)
    for limb_name, d in taught_data().items():
        names = d["fk"] + [d["ik"], d.get("pv", ""), d.get("switch", "").split(".")[0]]
        if name in names:
            return Taught(limb_name, d, ns)
    return None


def teach(name, fk, joints, ik, pv, switch, fk_value, ik_value):
    """Save a limb. fk / joints: 3 nodes each (upper, middle, end). switch: 'node.attr'. The rig must be
    in a pose where FK and IK line up."""
    if len(fk) != 3 or len(joints) != 3:
        raise RuntimeError("pick 3 FK controls and 3 joints (upper, middle, end).")
    if not ik:
        raise RuntimeError("pick the IK control.")
    if switch and not cmds.objExists(switch):
        raise RuntimeError("the switch attribute '%s' doesn't exist." % switch)
    if abs(float(fk_value) - float(ik_value)) < 1e-9:
        raise RuntimeError("the FK and IK values of the switch must be different.")
    js = [world(j) for j in joints]
    d = {"fk": [_strip(x) for x in fk], "joints": [_strip(x) for x in joints], "ik": _strip(ik),
         "pv": _strip(pv) if pv else "", "switch": (_strip(switch.split(".")[0]) + "." + switch.split(".", 1)[1])
         if switch else "", "fk_value": float(fk_value), "ik_value": float(ik_value),
         "fk_off": [mul(world(c), inverse(j)) for c, j in zip(fk, js)],
         "ik_off": mul(world(ik), inverse(js[2]))}
    data = taught_data()
    data[name] = d
    with Undo("gusAnimTeach"):
        _write_taught(data)
    message("taught '%s': select one of its controls and use Switch / To FK / To IK / Bake." % name)


def forget(name):
    data = taught_data()
    if name in data:
        del data[name]
        _write_taught(data)
        message("forgot '%s'." % name)


def export_taught(path):
    with open(path, "w") as f:
        json.dump(taught_data(), f, indent=1, sort_keys=True)
    message("saved %d taught limb(s) to %s." % (len(taught_data()), path))


def import_taught(path):
    with open(path) as f:
        incoming = json.load(f)
    data = taught_data()
    data.update(incoming)
    _write_taught(data)
    message("loaded %d taught limb(s)." % len(incoming))


# ===========================================================================
# space switch with no jump (any rig)
# ===========================================================================

SPACE_WORDS = ("space", "follow", "parent", "orient", "align")


def space_attrs(node):
    """[(attr, [value names])]: enum attributes of a control, space-like names first."""
    out = []
    for a in cmds.listAttr(node, keyable=True, userDefined=True) or []:
        try:
            if cmds.getAttr(node + "." + a, type=True) == "enum":
                names = (cmds.attributeQuery(a, node=node, listEnum=True) or [""])[0].split(":")
                out.append((a, names))
        except RuntimeError:
            pass
    out.sort(key=lambda x: (0 if any(w in x[0].lower() for w in SPACE_WORDS) else 1))
    return out


def menu_select(menu, index):
    """Pick item number index (1 = first) of an option menu, only if it's there (Maya says 'Value is out of
    range' otherwise). True when picked."""
    try:
        n = cmds.optionMenu(menu, query=True, numberOfItems=True) or 0
        if 1 <= int(index) <= n:
            cmds.optionMenu(menu, edit=True, select=int(index))
            return True
    except (RuntimeError, TypeError, ValueError):
        pass
    return False


NO_NAME = "space %d (no name)"


def _space_index():
    """The space value the menu shows (its item number, or the number in 'space N (no name)')."""
    label = cmds.optionMenu(P + "SpaceValue", query=True, value=True) or ""
    if label.startswith("space ") and label.endswith("(no name)"):
        try:
            return int(label.split()[1])
        except (IndexError, ValueError):
            pass
    return cmds.optionMenu(P + "SpaceValue", query=True, select=True) - 1


def fill_space_menus(*_):
    if not cmds.optionMenu(P + "SpaceAttr", exists=True):
        return
    sel = selected()
    old = cmds.optionMenu(P + "SpaceAttr", query=True, value=True) if \
        cmds.optionMenu(P + "SpaceAttr", query=True, numberOfItems=True) else None
    for item in cmds.optionMenu(P + "SpaceAttr", query=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    attrs = space_attrs(sel[0]) if sel else []
    for a, _names in attrs or [("(select a control with a space attribute)", [])]:
        cmds.menuItem(label=a, parent=P + "SpaceAttr")
    if old and old in [a for a, _n in attrs]:
        cmds.optionMenu(P + "SpaceAttr", edit=True, value=old)
    fill_space_values()


def fill_space_values(*_):
    if not cmds.optionMenu(P + "SpaceValue", exists=True):
        return
    for item in cmds.optionMenu(P + "SpaceValue", query=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    sel = selected()
    attr = cmds.optionMenu(P + "SpaceAttr", query=True, value=True)
    names = dict(space_attrs(sel[0])).get(attr, []) if sel else []
    for n in names or ["-"]:
        cmds.menuItem(label=n, parent=P + "SpaceValue")
    if sel and names and cmds.objExists(sel[0] + "." + attr):
        try:
            v = int(cmds.getAttr(sel[0] + "." + attr))
        except (RuntimeError, TypeError, ValueError):
            return
        if not 0 <= v < len(names):                        # a value past the names: show it, don't fail
            cmds.menuItem(label=NO_NAME % v, parent=P + "SpaceValue")
            menu_select(P + "SpaceValue", cmds.optionMenu(P + "SpaceValue", query=True, numberOfItems=True))
        else:
            menu_select(P + "SpaceValue", v + 1)


def space_switch(*_):
    sel = selected()
    if not sel:
        raise RuntimeError("select the controls to switch.")
    attr = cmds.optionMenu(P + "SpaceAttr", query=True, value=True)
    index = _space_index()
    nodes = [n for n in sel if cmds.attributeQuery(attr, node=n, exists=True)]
    if not nodes:
        raise RuntimeError("the selected controls have no '%s' attribute." % attr)
    keying = opt("key_switch", 1)
    frame = cmds.currentTime(query=True)
    worlds = [(n, world(n)) for n in nodes]
    with Undo("gusAnimSpace"):
        if keying:
            _key(nodes, frame - 1, insert=True)
        for n, m in worlds:
            cmds.setAttr(n + "." + attr, index)
            set_world(n, m)
        if keying:
            _key(nodes, frame)
    message("%s = %s on %d control(s), no jump%s." % (attr, cmds.optionMenu(P + "SpaceValue", query=True,
                                                                            value=True), len(nodes),
                                                     " (keyed)" if keying else ""))


def frame_range():
    """The window's frame range when it's open, else the Time Slider's."""
    if cmds.intField(P + "Start", exists=True):
        return _range()
    return int(cmds.playbackOptions(query=True, minTime=True)), int(cmds.playbackOptions(query=True, maxTime=True))


def _range():
    start = int(cmds.intField(P + "Start", query=True, value=True))
    end = int(cmds.intField(P + "End", query=True, value=True))
    if end < start:
        raise ValueError("the end frame is before the start frame.")
    return start, end


def _frames(nodes, start, end, keys_only):
    if not keys_only:
        return list(range(start, end + 1))
    keys = cmds.keyframe(nodes, query=True, time=(start, end), timeChange=True) or []
    return sorted(set([float(start), float(end)] + [float(k) for k in keys]))


def space_switch_range(*_):
    """The new space over the whole frame range: the controls keep their motion (keys only or every frame)."""
    sel = selected()
    if not sel:
        raise RuntimeError("select the controls to switch.")
    attr = cmds.optionMenu(P + "SpaceAttr", query=True, value=True)
    index = _space_index()
    nodes = [n for n in sel if cmds.attributeQuery(attr, node=n, exists=True)]
    if not nodes:
        raise RuntimeError("the selected controls have no '%s' attribute." % attr)
    start, end = _range()
    frames = _frames(nodes, start, end, opt("range_keys_only", 1))
    now = cmds.currentTime(query=True)
    with Undo("gusAnimSpaceRange"):
        cmds.refresh(suspend=True)
        try:
            _key(nodes, start - 1, insert=True)                 # outside the range nothing changes
            _key(nodes, end + 1, insert=True)
            worlds = []
            for f in frames:                                    # where they are, in the old space
                cmds.currentTime(f, update=True)
                worlds.append([(n, world(n)) for n in nodes])
            for f, ws in zip(frames, worlds):
                cmds.currentTime(f, update=True)
                for n, m in ws:
                    cmds.setKeyframe(n, attribute=attr, time=f, value=index)
                    cmds.setAttr(n + "." + attr, index)
                    set_world(n, m)
                _key(nodes, f)
        finally:
            cmds.refresh(suspend=False)
            cmds.currentTime(now, update=True)
    message("%s = %s on %d control(s), frames %d-%d, no jump." % (
        attr, cmds.optionMenu(P + "SpaceValue", query=True, value=True), len(nodes), start, end))


# ===========================================================================
# pose: mirror / flip / reset, twins (any rig)
# ===========================================================================

SIDE_CANDIDATES = [("L_", "R_"), ("_L", "_R"), ("Lf_", "Rt_"), ("_Lf", "_Rt"), ("l_", "r_"), ("_l", "_r"),
                   ("left_", "right_"), ("_left", "_right"), ("Left", "Right"), ("left", "right"), ("Lft", "Rgt")]
_pairs_cache = {}


def _sides_set_by_you():
    p = profile()
    if p.get("left") and p.get("right"):
        return True
    return any(cmds.optionVar(exists=P + k) and cmds.optionVar(query=P + k) != d
               for k, d in (("left", DEFAULT_PAIRS[0][0]), ("right", DEFAULT_PAIRS[0][1])))


def auto_pairs(ns=None):
    """Left / right name tokens this character really uses: a candidate counts when at least 2 controls swap to
    the name of another control. Most used first."""
    import time
    ns = current_character() if ns is None else ns
    hit = _pairs_cache.get(ns)
    if hit and time.time() - hit[0] < 10.0:
        return hit[1]
    _pairs_cache[ns] = (time.time(), [])                  # character_controls may ask for pairs meanwhile
    names = {short(c).split(":")[-1] for c in character_controls(ns)}
    found = []
    for a, b in SIDE_CANDIDATES:
        n = sum(1 for nm in names if any((_swap_token(nm, x, y) or nm) != nm and _swap_token(nm, x, y) in names
                                         for x, y in ((a, b), (b, a))))
        if n >= 2:
            found.append((n, (a, b)))
    out = [pair for _n, pair in sorted(found, key=lambda x: -x[0])]
    _pairs_cache[ns] = (time.time(), out)
    return out


def pairs():
    p = profile()
    left = p.get("left") or opt("left", DEFAULT_PAIRS[0][0])
    right = p.get("right") or opt("right", DEFAULT_PAIRS[0][1])
    out = [(left, right)] + [p for p in DEFAULT_PAIRS[1:]]
    if not _sides_set_by_you():                           # your own tokens only, when you set them
        try:
            out += [x for x in auto_pairs() if x not in out]
        except Exception:
            pass
    return [p for p in out if p[0] and p[1]]


def _swap_token(base, x, y):
    if x.endswith("_") and not x.startswith("_"):
        if base.startswith(x):
            return y + base[len(x):]
        if "_" + x in base:
            return base.replace("_" + x, "_" + y, 1)
        return None
    if x.startswith("_") and not x.endswith("_"):
        if base.endswith(x):
            return base[:-len(x)] + y
        if x + "_" in base:
            return base.replace(x + "_", y + "_", 1)
        return None
    if x and x in base:
        return base.replace(x, y, 1)
    return None


def mirror_name(node):
    ns = namespace_of(node)
    new, changed = short(node).split(":")[-1], False
    for a, b in pairs():
        for x, y in ((a, b), (b, a)):
            swapped = _swap_token(new, x, y)
            if swapped is not None:
                new, changed = swapped, True
                break
    return ns + new if changed else None


def side_of(node):
    base = short(node).split(":")[-1]
    for a, b in pairs():
        if _swap_token(base, a, b) is not None:
            return "L"
        if _swap_token(base, b, a) is not None:
            return "R"
    try:                                                  # no side in the name: the other side of a named twin
        twin = position_twins(namespace_of(node)).get(long_name(node) or node)
    except Exception:
        twin = None
    if twin:
        tb = short(twin).split(":")[-1]
        for a, b in pairs():
            if _swap_token(tb, a, b) is not None:
                return "R"
            if _swap_token(tb, b, a) is not None:
                return "L"
    p = cmds.xform(node, query=True, worldSpace=True, rotatePivot=True)
    d = p[DEFAULT_AXIS] - DEFAULT_CENTER[DEFAULT_AXIS]
    return "L" if d > 0.01 else ("R" if d < -0.01 else "C")


def _name_twin(node):
    """The linked twin, unless the node with the mirrored name exists and is another node (a wrong link)."""
    name = mirror_name(node)
    by_name = long_name(name) if name else None
    if cmds.attributeQuery(TWIN_ATTR, node=node, exists=True):
        found = cmds.listConnections(node + "." + TWIN_ATTR, source=True, destination=False) or []
        if found:
            linked = long_name(found[0])
            if by_name and linked and by_name != linked:
                # 5.6.24: a link you made wins when it's the one at the mirrored place (Cape01 <-> Cape02)
                try:
                    return linked if _mirrored_gap(node, linked) < _mirrored_gap(node, by_name) else by_name
                except (RuntimeError, ValueError, TypeError):
                    return by_name
            return linked or by_name
    return by_name


def _mirrored_gap(a, b):
    """How far b is from a's mirrored rest place."""
    pa, pb = list(_rest_pos(a)), _rest_pos(b)
    pa[DEFAULT_AXIS] = 2 * DEFAULT_CENTER[DEFAULT_AXIS] - pa[DEFAULT_AXIS]
    return max(abs(x - y) for x, y in zip(pa, pb))


def link_twins(a, b):
    """5.6.24: a and b are each other's twin (a link on both: mirror, the picker, select twin use it)."""
    for x, y in ((a, b), (b, a)):
        if not cmds.attributeQuery(TWIN_ATTR, node=y, exists=True):
            cmds.addAttr(y, longName=TWIN_ATTR, attributeType="message", hidden=True)
        cmds.connectAttr(x + ".message", y + "." + TWIN_ATTR, force=True)
    _position_cache.clear()


def unlink_twin(a):
    if cmds.attributeQuery(TWIN_ATTR, node=a, exists=True):
        for src in cmds.listConnections(a + "." + TWIN_ATTR, source=True, destination=False, plugs=True) or []:
            cmds.disconnectAttr(src, a + "." + TWIN_ATTR)
    _position_cache.clear()


_position_cache = {}


def _rest_pos(n):
    m = world_rest(n)
    return m[12], m[13], m[14]


def position_twins(ns=None):
    """{control: twin} found by position (5.0.6), for controls with no twin by name or link: the one sitting at
    the mirrored rest position (the Hare's mouth loop: L_Mouth_fol_02_ctrl's twin is Mouth_fol_26_ctrl).
    Controls on the centre line pair with nobody. Cached for 10 s per character."""
    import time
    ns = current_character() if ns is None else ns
    hit = _position_cache.get(ns)
    if hit and time.time() - hit[0] < 10.0:
        return hit[1]
    _position_cache[ns] = (time.time(), {})
    ctrls = character_controls(ns)
    pos = {}
    for c in ctrls:
        try:
            pos[c] = _rest_pos(c)
        except (RuntimeError, ValueError, TypeError):
            pass
    a = DEFAULT_AXIS
    ys = [p[1] for p in pos.values()] or [0.0]
    tol = max(0.01, (max(ys) - min(ys)) * 0.002)
    loose = [c for c in pos if abs(pos[c][a] - DEFAULT_CENTER[a]) > tol and not _name_twin(c) and not no_mirror(c)]
    gaps = []
    for c in loose:
        d = [max(abs(x - y) for x, y in zip(pos[c], pos[k])) for k in loose if k != c]
        if d:
            gaps.append(min(d))
    pair_tol = max(tol, (sorted(gaps)[len(gaps) // 2] if gaps else 0.0) * 0.25)
    out = {}
    for c in loose:
        if c in out:
            continue
        p = list(pos[c])
        p[a] = 2 * DEFAULT_CENTER[a] - p[a]
        best, dist = None, None
        for k in loose:
            if k == c or k in out:
                continue
            d = max(abs(x - y) for x, y in zip(p, pos[k]))
            if dist is None or d < dist:
                best, dist = k, d
        if best is not None and dist <= pair_tol:
            out[c], out[best] = best, c
    _position_cache[ns] = (time.time(), out)
    return out


def twin_of(node):
    """The twin by name (or link), else the control at the mirrored position (5.0.6). 5.6.27: nobody for a
    control on a ribbon marked not symmetric."""
    if no_mirror(node):
        return None
    found = _name_twin(node)
    if found:
        return found
    try:
        return position_twins(namespace_of(node)).get(long_name(node) or node)
    except Exception:
        return None


_T = ["translateX", "translateY", "translateZ"]
_R = ["rotateX", "rotateY", "rotateZ"]
_S = ["scaleX", "scaleY", "scaleZ"]


def _get3(n, attrs):
    return [cmds.getAttr(n + "." + a) for a in attrs]


def _parent(n):
    return (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]


def _jo(n):
    return _get3(n, ["jointOrientX", "jointOrientY", "jointOrientZ"]) if cmds.nodeType(n) == "joint" else None


def _poseable(n):
    return cmds.nodeType(n) == "joint" or bool(cmds.listRelatives(n, shapes=True, type="nurbsCurve"))


def local_now(n):
    return compose(_get3(n, _T), _get3(n, _R), _get3(n, _S), cmds.getAttr(n + ".rotateOrder"), _jo(n))


def local_rest(n):
    if cmds.nodeType(n) == "joint":
        return compose(_get3(n, _T), (0, 0, 0), _get3(n, _S), 0, _jo(n))
    if _poseable(n):
        return list(IDENTITY)
    return list(cmds.getAttr(n + ".matrix"))


REST_ATTR = "gusRestWorld"           # 5.6.27: the control's world matrix at rest, learned once (mirror table)
NO_MIRROR_ATTR = "rrbNotSymmetric"   # 5.6.27: a ribbon marked not symmetric (Gus_Rigtool): its controls pair with nobody


def stored_rest(n):
    """The world matrix learned at rest (learn_rest), or None."""
    try:
        if not cmds.attributeQuery(REST_ATTR, node=n, exists=True):
            return None
        vals = [float(x) for x in (cmds.getAttr(n + "." + REST_ATTR) or "").split()]
        return vals if len(vals) == 16 else None
    except (RuntimeError, ValueError, TypeError):
        return None


def no_mirror(n, levels=8):
    """True when a group above the control is marked not symmetric (the hood's collar)."""
    p = n
    for _ in range(levels):
        p = _parent(p)
        if not p:
            return False
        try:
            if cmds.attributeQuery(NO_MIRROR_ATTR, node=p, exists=True) and cmds.getAttr(p + "." + NO_MIRROR_ATTR):
                return True
        except (RuntimeError, ValueError):
            return False
    return False


def learn_rest(ns=None, nodes=None):
    """5.6.27: the mirror table. Every control is put at rest for a moment (translate / rotate 0, scale 1 on the
    channels that can be set), its world matrix is kept on it (gusRestWorld, hidden), then every value goes back.
    Mirror pose / flip / mirror animation work from it: a control whose parent follows something else (the
    cape's groups follow the arms) mirrors right however that something is posed. Nothing in the rig moves.
    Returns how many controls learned."""
    nodes = nodes if nodes is not None else character_controls(ns)
    nodes = [n for n in nodes if _poseable(n)]
    if not nodes:
        return 0
    with Undo("gusAnimLearnRest"):
        back = []
        try:
            for n in nodes:
                for plug, rest in _rest_values(n):
                    if _settable(plug):
                        v = cmds.getAttr(plug)
                        if isinstance(v, (int, float)) and abs(v - rest) > 1e-9:
                            back.append((plug, v))
                            cmds.setAttr(plug, rest)
            mats = {n: world(n) for n in nodes}
        finally:
            for plug, v in reversed(back):
                try:
                    cmds.setAttr(plug, v)
                except RuntimeError:
                    pass
        learned = 0
        for n, m in mats.items():
            try:
                if not cmds.attributeQuery(REST_ATTR, node=n, exists=True):
                    cmds.addAttr(n, longName=REST_ATTR, dataType="string", hidden=True)
                cmds.setAttr(n + "." + REST_ATTR, " ".join("%.9g" % x for x in m), type="string")
                learned += 1
            except RuntimeError:                            # 5.6.28: a locked reference - not counted
                pass
    _position_cache.clear()
    message("mirror table: %d control(s) learned at rest%s; nothing moved." % (
        learned, (" (%d couldn't be written - a locked reference?)" % (len(mats) - learned)) if learned < len(mats)
        else ""))
    return learned


def _rest_values(n):
    """5.6.28: [(plug, rest value)] for learn_rest: translate 0 (not on joints - a joint's translate is where it
    sits on its parent, as local_rest() keeps it), rotate 0, scale 1, and the control's own number attributes at
    their default value (finger curls, Bends, ikfk... - else a curled hand learns a curled rest)."""
    out = []
    joint = cmds.nodeType(n) == "joint"
    for attrs, rest in ((_T, 0.0), (_R, 0.0), (_S, 1.0)):
        if attrs is _T and joint:
            continue
        out += [(n + "." + a, rest) for a in attrs]
    for a in cmds.listAttr(n, keyable=True, userDefined=True) or []:
        try:
            if cmds.getAttr(n + "." + a, type=True) not in ("double", "float", "long", "short", "bool", "enum",
                                                            "doubleLinear", "doubleAngle", "byte"):
                continue
            d = cmds.attributeQuery(a, node=n, listDefault=True) or [0.0]
            out.append((n + "." + a, float(d[0])))
        except (RuntimeError, ValueError, TypeError):
            pass
    return out


def world_rest(n):
    got = stored_rest(n)
    if got is not None:
        return got
    m = local_rest(n)
    p = _parent(n)
    while p:
        m = mul(m, local_rest(p))
        p = _parent(p)
    return m


def pose_target(src, dst):
    q = mul(mul(world_rest(src), reflection(DEFAULT_AXIS, DEFAULT_CENTER)), inverse(world_rest(dst)))
    delta = mul(local_now(src), inverse(local_rest(src)))
    local = mul(mul(mul(inverse(q), delta), q), local_rest(dst))
    return decompose(local, cmds.getAttr(dst + ".rotateOrder"), _jo(dst))


def _settable(plug):
    try:
        return cmds.getAttr(plug, settable=True)
    except (RuntimeError, ValueError):
        return False


def _custom(n):
    out = {}
    for a in cmds.listAttr(n, keyable=True, userDefined=True) or []:
        try:
            if cmds.getAttr(n + "." + a, type=True) in ("double", "float", "long", "short", "bool", "enum",
                                                        "doubleLinear", "doubleAngle", "byte"):
                out[a] = cmds.getAttr(n + "." + a)
        except (RuntimeError, ValueError):
            pass
    return out


def _apply(dst, trs, custom):
    for attrs, values in zip((_T, _R, _S), trs):
        for a, v in zip(attrs, values):
            plug = dst + "." + a
            if _settable(plug) and abs(cmds.getAttr(plug) - (0.0 if abs(v) < 1e-6 else v)) > 1e-7:
                cmds.setAttr(plug, 0.0 if abs(v) < 1e-6 else v)
    for a, v in (custom or {}).items():
        plug = dst + "." + a
        if cmds.objExists(plug) and _settable(plug):
            try:
                cmds.setAttr(plug, v)
            except RuntimeError:
                pass


def _pose_sel():
    sel = [n for n in selected() if _poseable(n)]
    if not sel:
        raise RuntimeError("select controls first.")
    return sel


def mirror_pose(direction="L>R"):
    sel = _pose_sel()
    custom = opt("pose_custom", 1)
    jobs, done, missing = [], set(), []
    for n in sel:
        twin = twin_of(n)
        if not twin:
            if side_of(n) == "C" and not no_mirror(n):
                jobs.append((n, n))
            else:
                missing.append(n)
            continue
        side = side_of(n)
        src = n if side == direction[0] else twin
        dst = twin if src == n else n
        if dst not in done:
            done.add(dst)
            jobs.append((src, dst))
    results = [(d, pose_target(s, d), _custom(s) if custom else {}) for s, d in jobs]
    with Undo("gusAnimMirror"):
        for d, trs, values in results:
            _apply(d, trs, values)
    message("mirrored %d control(s) %s%s." % (len(results), direction.replace(">", " -> "),
                                              "; no twin for %d" % len(missing) if missing else ""))


def flip_pose(*_):
    sel = _pose_sel()
    custom = opt("pose_custom", 1)
    jobs, seen = [], set()
    for n in sel:
        if n in seen:
            continue
        twin = twin_of(n)
        if twin:
            seen.update([n, twin])
            jobs += [(n, twin), (twin, n)]
        elif side_of(n) == "C" and not no_mirror(n):
            seen.add(n)
            jobs.append((n, n))
    results = [(d, pose_target(s, d), _custom(s) if custom else {}) for s, d in jobs]
    with Undo("gusAnimFlip"):
        for d, trs, values in results:
            _apply(d, trs, values)
    message("flipped %d control(s)." % len(results))


def _mirror_jobs(sel, mode):
    jobs, done, missing = [], set(), []
    for n in sel:
        if n in done:
            continue
        twin = twin_of(n)
        if not twin:
            if side_of(n) == "C" and not no_mirror(n):
                jobs.append((n, n))
                done.add(n)
            else:
                missing.append(n)
            continue
        if mode == "flip":
            done.update([n, twin])
            jobs += [(n, twin), (twin, n)]
            continue
        src = n if side_of(n) == mode[0] else twin
        dst = twin if src == n else n
        if dst not in done:
            done.add(dst)
            jobs.append((src, dst))
    return jobs, missing


def _key_poses(data, dsts):
    """Key [(control, frame, (t, r, s), {custom attr: value})], then Euler-filter the controls' rotations."""
    for d, t, trs, values in data:
        for attrs, vals in zip((_T, _R, _S), trs):
            for a, v in zip(attrs, vals):
                if _settable(d + "." + a):
                    cmds.setKeyframe(d, attribute=a, time=t, value=0.0 if abs(v) < 1e-6 else v)
        for a, v in values.items():
            if cmds.objExists(d + "." + a) and _settable(d + "." + a):
                cmds.setKeyframe(d, attribute=a, time=t, value=v)
    curves = cmds.listConnections([d + "." + a for d in dsts for a in _R], source=True, destination=False,
                                  type="animCurve") or []
    if curves:
        try:
            cmds.filterCurve(curves, filter="euler")
        except RuntimeError:
            pass


def mirror_animation(mode="L>R"):
    """The selected controls' animation onto their twins (or flipped), over the frame range, with an offset."""
    sel = _pose_sel()
    start, end = _range()
    offset = int(cmds.intField(P + "AnimOffset", query=True, value=True))
    wrap = bool(opt("anim_wrap", 0))
    custom = opt("pose_custom", 1)
    jobs, missing = _mirror_jobs(sel, mode)
    if not jobs:
        raise RuntimeError("nothing to mirror (no twins in the selection).")
    sources = sorted(set(s for s, _d in jobs))
    frames = _frames(sources, start, end, opt("range_keys_only", 1))
    length = end - start
    if wrap and length > 0:
        frames = sorted(set([f for f in frames if f < end] + [float(start + ((-offset) % length))]))
    now = cmds.currentTime(query=True)
    data = []
    with Undo("gusAnimMirrorAnim"):
        cmds.refresh(suspend=True)
        try:
            for f in frames:
                cmds.currentTime(f, update=True)
                for s, d in jobs:
                    t = f + offset
                    if wrap and length > 0:
                        t = start + ((t - start) % length)
                    data.append((d, t, pose_target(s, d), _custom(s) if custom else {}))
        finally:
            cmds.refresh(suspend=False)
            cmds.currentTime(now, update=True)
        if wrap and length > 0:
            data += [(d, end, trs, v) for d, t, trs, v in data if abs(t - start) < 1e-6]
        dsts = sorted(set(d for _s, d in jobs))
        lo, hi = (start, end) if wrap else (start + offset, end + offset)
        for d in dsts:
            try:
                cmds.cutKey(d, time=(lo, hi), clear=True)
            except RuntimeError:
                pass
        _key_poses(data, dsts)
    message("%s the animation of %d control(s), frames %d-%d%s%s." % (
        "flipped" if mode == "flip" else "mirrored " + mode.replace(">", " -> "), len(jobs), start, end,
        ", offset %d" % offset if offset else "", "; no twin for %d" % len(missing) if missing else ""))


def flip_range(nodes, lo, hi):
    """Inside frames lo-hi the two sides swap animation (middle controls flipped) - keys at the same frames."""
    jobs, _missing = _mirror_jobs(nodes, "flip")
    if not jobs:
        return 0
    sources = sorted(set(s for s, _d in jobs))
    frames = _frames(sources, lo, hi, True)
    custom = opt("pose_custom", 1)
    now = cmds.currentTime(query=True)
    data = []
    cmds.refresh(suspend=True)
    try:
        for f in frames:
            cmds.currentTime(f, update=True)
            for s, d in jobs:
                data.append((d, f, pose_target(s, d), _custom(s) if custom else {}))
    finally:
        cmds.refresh(suspend=False)
        cmds.currentTime(now, update=True)
    dsts = sorted(set(d for _s, d in jobs))
    for d in dsts:
        try:
            cmds.cutKey(d, time=(lo, hi), clear=True)
        except RuntimeError:
            pass
    _key_poses(data, dsts)
    return len(dsts)


def mirror_half_cycle(nodes=None, start=None, end=None, loop=None):
    """A walk / run cycle from its first half: the range is the whole cycle with its loop frame (1-25 for a
    24-frame cycle). The first half's keys, mirrored (left <-> right, middle controls flipped), become the second
    half; the loop frame gets the first frame's pose; loop: the curves repeat (cycle infinity)."""
    sel = nodes or _pose_sel()
    if start is None:
        start, end = _range()
    length = end - start
    if length < 2:
        raise RuntimeError("set the frame range to the whole cycle (e.g. 1 to 25 for 24 frames).")
    if int(round(length)) % 2:                       # 1-24: the loop frame is the next one (25)
        end += 1
        length += 1
    half = length / 2.0
    loop = bool(opt("cycle_loop", 1)) if loop is None else loop
    custom = opt("pose_custom", 1)
    jobs, missing = _mirror_jobs(sel, "flip")
    if not jobs:
        raise RuntimeError("select the character's controls (or a limb and its twin).")
    sources = sorted(set(s for s, _d in jobs))
    frames = [f for f in _frames(sources, start, end, True) if f < start + half - 1e-6] or [float(start)]
    now = cmds.currentTime(query=True)
    data, first = [], {}
    with Undo("gusAnimMirrorCycle"):
        cmds.refresh(suspend=True)
        try:
            for f in frames:
                cmds.currentTime(f, update=True)
                for s, d in jobs:
                    data.append((d, f + half, pose_target(s, d), _custom(s) if custom else {}))
            cmds.currentTime(start, update=True)
            for n in sorted(set(d for _s, d in jobs)):
                first[n] = (_get3(n, _T), _get3(n, _R), _get3(n, _S), _custom(n) if custom else {})
        finally:
            cmds.refresh(suspend=False)
            cmds.currentTime(now, update=True)
        dsts = sorted(set(d for _s, d in jobs))
        for d in dsts:
            try:
                cmds.cutKey(d, time=(start + half - 1e-3, end), clear=True)
            except RuntimeError:
                pass
        data += [(n, float(end), (t, r, sc), v) for n, (t, r, sc, v) in first.items()]     # the loop frame
        _key_poses(data, dsts)
        if loop:
            every = time_curves(dsts)
            if every:
                cmds.setInfinity(every, preInfinite="cycle", postInfinite="cycle")
    message("cycle: frames %g-%g mirrored onto %g-%g for %d control(s)%s%s." % (
        start, start + half, start + half, end, len(dsts), ", looping" if loop else "",
        "; no twin for %d" % len(missing) if missing else ""))
    return len(dsts)


def reset_pose(scope="selection"):
    nodes = _pose_sel() if scope == "selection" else character_controls()
    if not nodes:
        raise RuntimeError("no controls found for this character.")
    custom = opt("pose_custom", 1)
    with Undo("gusAnimReset"):
        for n in nodes:
            if cmds.nodeType(n) == "joint":
                continue
            attrs = _T + _R + _S + (list(_custom(n)) if custom else [])
            try:
                saved = json.loads(meta_str(n, "gusDefaultPose") or "{}")    # the pose saved by Publish
            except ValueError:
                saved = {}
            for a in attrs:
                plug = n + "." + a
                if not cmds.objExists(plug) or not _settable(plug):
                    continue
                d = [saved[a]] if a in saved else \
                    (cmds.attributeQuery(a, node=n, listDefault=True) or [1.0 if a in _S else 0.0])
                try:
                    cmds.setAttr(plug, d[0])
                except RuntimeError:
                    pass
    message("reset %d control(s)." % len(nodes))


def select_twin(mode="other"):
    sel = selected()
    if not sel:
        raise RuntimeError("select something first.")
    twins = [t for t in (twin_of(n) for n in sel) if t]
    if mode == "other":
        result = twins + [n for n in sel if not twin_of(n)]
    else:
        result = sel + [t for t in twins if t not in sel]
    cmds.select(result, replace=True)
    message("selected %d twin(s)." % len(twins))


# ===========================================================================
# selection
# ===========================================================================

def select_set(which):
    if which == "all":
        nodes = character_controls()
    elif which == "limb":
        nodes = []
        for s in limbs_of_selection():
            nodes += [n for n in limb_controls(s) if n not in nodes]
    else:
        ns = current_character()
        nodes = []
        limbs = [s for s in with_attr("gusBlend", ns) if meta_str(s, "gusBlend")]
        for s in limbs:
            nodes += [n for n in limb_controls(s, which) if n not in nodes]
        if not limbs:                              # another rig: by name
            word = {"fk": "fk", "ik": "ik", "tweaks": "tweak"}[which]
            nodes = [n for n in character_controls() if word in short(n).split(":")[-1].lower()]
    if not nodes:
        raise RuntimeError("nothing found to select.")
    cmds.select(nodes, replace=True)
    message("selected %d control(s)." % len(nodes))


# ===========================================================================
# picker: a button per control, laid out from where the controls are (any rig)
# ===========================================================================

PICKER = "gusAnimPickerWorkspace"
PK = "gusAnimPk_"
PICK_W, PICK_H, PICK_MARGIN = 330, 440, 14
PICK_VIEWS = (("Body", "front"), ("Side", "side"), ("Face", "face"))
_pick = {"buttons": {}, "ns": None}


def _bbox(node):
    shapes = cmds.listRelatives(node, shapes=True, type="nurbsCurve", fullPath=True, noIntermediate=True) or []
    try:
        b = cmds.exactWorldBoundingBox(shapes or node)
        return [(b[0] + b[3]) * 0.5, (b[1] + b[4]) * 0.5, (b[2] + b[5]) * 0.5], max(b[3] - b[0], b[4] - b[1],
                                                                                     b[5] - b[2])
    except (RuntimeError, TypeError, ValueError):
        p = cmds.xform(node, query=True, worldSpace=True, rotatePivot=True)
        return p, 0.0


def _colour(node):
    for s in cmds.listRelatives(node, shapes=True, type="nurbsCurve", fullPath=True, noIntermediate=True) or []:
        for n in (s, node):
            try:
                if not cmds.getAttr(n + ".overrideEnabled"):
                    continue
                if cmds.getAttr(n + ".overrideRGBColors"):
                    return list(cmds.getAttr(n + ".overrideColorRGB")[0])
                return list(cmds.colorIndex(cmds.getAttr(n + ".overrideColor"), query=True))
            except (RuntimeError, ValueError, TypeError):
                continue
    side = side_of(node)
    return {"L": [0.2, 0.4, 1.0], "R": [1.0, 0.25, 0.25]}.get(side, [1.0, 0.85, 0.2])


def face_controls(items, height):
    """The controls around the head (face): near the head control, small ones."""
    heads = [it for it in items if "head" in short(it["node"]).split(":")[-1].lower()]
    if not heads:
        return set()
    hc = max(heads, key=lambda it: it["size"])
    out = set()
    for it in items:
        if it is hc:
            continue
        d = math.sqrt(sum((a - b) ** 2 for a, b in zip(it["pos"], hc["pos"])))
        if d < height * 0.14 and it["size"] < height * 0.06:
            out.add(it["node"])
    return out


def _project(p, view):
    if view == "side":
        return p[2], p[1]                       # nose (+Z) to the right
    return p[0], p[1]                           # front: the character's left on your right


def picker_layout(ns=None, width=PICK_W, height=PICK_H):
    """{view: [{'node', 'x', 'y', 'w', 'h', 'rgb'}]}: buttons in canvas pixels (0, 0 = top left)."""
    nodes = character_controls(ns)
    items = []
    for n in nodes:
        pos, size = _bbox(n)
        items.append({"node": n, "pos": pos, "size": size, "rgb": _colour(n)})
    if not items:
        return {}
    ys = [it["pos"][1] for it in items]
    tall = max(max(ys) - min(ys), 1e-6)
    face = face_controls(items, tall)
    out = {}
    for tab, view in PICK_VIEWS:
        chosen = [it for it in items if (it["node"] in face) == (view == "face")]
        if view == "face" and not chosen:
            out[tab] = []
            continue
        uv = [_project(it["pos"], "front" if view == "face" else view) for it in chosen]
        us, vs = [u for u, _v in uv], [v for _u, v in uv]
        du, dv = max(us) - min(us), max(vs) - min(vs)
        fits = [(width - 2 * PICK_MARGIN - 40) / du if du > 1e-6 else None,
                (height - 2 * PICK_MARGIN - 40) / dv if dv > 1e-6 else None]
        fits = [f for f in fits if f]
        scale = min(fits) if fits else 1.0
        cu, cv = (max(us) + min(us)) * 0.5, (max(vs) + min(vs)) * 0.5
        placed = []
        order = sorted(range(len(chosen)), key=lambda i: -chosen[i]["size"])
        for i in order:
            it, (u, v) = chosen[i], uv[i]
            px = max(12, min(40, int(it["size"] * scale * 0.5)))
            x = int(width * 0.5 + (u - cu) * scale - px * 0.5)
            y = int(height * 0.5 - (v - cv) * scale - px * 0.5)
            x, y = _free_spot(placed, x, y, px, width, height)
            x, y = max(0, min(width - px, x)), max(0, min(height - px, y))
            placed.append({"node": it["node"], "x": x, "y": y, "w": px, "h": px, "rgb": it["rgb"]})
        out[tab] = placed
    return out


def _free_spot(placed, x, y, px, width, height):
    """The nearest spot to (x, y) where a px button doesn't cover one already placed (rings around it)."""
    def ok(cx, cy):
        if cx < 0 or cy < 0 or cx + px > width or cy + px > height:
            return False
        return not any(cx < b["x"] + b["w"] + 1 and b["x"] < cx + px + 1 and cy < b["y"] + b["h"] + 1 and
                       b["y"] < cy + px + 1 for b in placed)
    x, y = max(0, min(width - px, x)), max(0, min(height - px, y))
    if ok(x, y):
        return x, y
    step = max(3, px // 2)
    for ring in range(1, 60):
        for dx in range(-ring, ring + 1):
            for dy in (-ring, ring) if abs(dx) != ring else range(-ring, ring + 1):
                if ok(x + dx * step, y + dy * step):
                    return x + dx * step, y + dy * step
    return x, y


def picker_click(node):
    mods = 0
    try:
        mods = cmds.getModifiers()
    except RuntimeError:
        pass
    if not cmds.objExists(node):
        raise RuntimeError("%s is gone - press Refresh." % short(node))
    if mods & 1:
        cmds.select(node, toggle=True)                  # Shift: add / take away
    elif mods & 4:
        cmds.select(node, deselect=True)                # Ctrl: take away
    else:
        cmds.select(node, replace=True)


def _picker_highlight(*_):
    sel = set(cmds.ls(selection=True, long=True) or [])
    for b, (node, rgb) in list(_pick["buttons"].items()):
        if not cmds.button(b, exists=True):
            continue
        on = node in sel
        col = [min(1.0, c * 0.5 + 0.5) for c in rgb] if on else [c * 0.75 for c in rgb]
        cmds.button(b, edit=True, label="o" if on else "", backgroundColor=col)


def _picker_char():
    try:
        label = cmds.optionMenu(PK + "Char", query=True, value=True) or ""
    except RuntimeError:
        return ""
    return "" if label in ("", ROOT) else label


def picker_fill(*_):
    if not cmds.tabLayout(PK + "Tabs", exists=True):
        return
    ns = _picker_char()
    layout = picker_layout(ns)
    _pick["buttons"].clear()
    for tab, _view in PICK_VIEWS:
        form = PK + "Form" + tab
        for c in cmds.formLayout(form, query=True, childArray=True) or []:
            cmds.deleteUI(c)
        attach = []
        for it in layout.get(tab, []):
            b = cmds.button(parent=form, label="", width=it["w"], height=it["h"], backgroundColor=it["rgb"],
                            annotation=short(it["node"]), command=guard(lambda *_, n=it["node"]: picker_click(n)))
            _pick["buttons"][b] = (it["node"], it["rgb"])
            attach += [(b, "top", it["y"]), (b, "left", it["x"])]
        if attach:
            cmds.formLayout(form, edit=True, attachForm=attach)
    _picker_highlight()
    message("picker: %d control(s)%s." % (len(_pick["buttons"]), (" in " + ns) if ns else ""))


def _picker_select(which):
    ns = _picker_char()
    nodes = character_controls(ns)
    if which in ("L", "R"):
        nodes = [n for n in nodes if side_of(n) == which]
    elif which == "tab":
        tab = cmds.tabLayout(PK + "Tabs", query=True, selectTab=True)
        nodes = [node for b, (node, _c) in _pick["buttons"].items()
                 if cmds.button(b, exists=True) and cmds.button(b, query=True, parent=True).endswith(tab)]
    if not nodes:
        raise RuntimeError("nothing to select.")
    cmds.select(nodes, replace=True)


def _picker_key(*_):
    sel = selected()
    if not sel:
        raise RuntimeError("select controls first.")
    cmds.setKeyframe(sel)
    message("keyed %d control(s)." % len(sel))


def _build_picker():
    if cmds.tabLayout(PK + "Tabs", exists=True):
        return
    cmds.setParent(PICKER)
    cmds.columnLayout(PK + "Root", adjustableColumn=True, rowSpacing=3)
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 2), (2, "both", 2),
                                                                        (3, "both", 2)])
    cmds.text(label="Character")
    cmds.optionMenu(PK + "Char", changeCommand=guard(picker_fill))
    for ns in characters() or [""]:
        cmds.menuItem(label=ns or ROOT)
    cmds.button(label="Refresh", command=guard(picker_fill), annotation="Read the rig again (new controls...).")
    cmds.setParent("..")
    cmds.text(label="Click: select   Shift: add / take away   Ctrl: take away", align="left",
              font="smallPlainLabelFont")
    cmds.tabLayout(PK + "Tabs", innerMarginWidth=2, innerMarginHeight=2)
    for tab, _view in PICK_VIEWS:
        cmds.formLayout(PK + "Form" + tab, width=PICK_W, height=PICK_H, backgroundColor=(0.2, 0.2, 0.2))
        cmds.setParent("..")
    cmds.tabLayout(PK + "Tabs", edit=True, tabLabel=[(PK + "Form" + t, t) for t, _v in PICK_VIEWS])
    cmds.setParent("..")
    for items in ((("All", lambda *_: _picker_select("all"), "Every control of the character."),
                   ("Left", lambda *_: _picker_select("L"), "Every left control."),
                   ("Right", lambda *_: _picker_select("R"), "Every right control."),
                   ("This tab", lambda *_: _picker_select("tab"), "Every control on this tab.")),
                  (("Twin", lambda *_: select_twin("other"), "The other side of the selection."),
                   ("IK / FK", lambda *_: switch("toggle"), "Switch the selected limbs, no jump."),
                   ("Reset", lambda *_: reset_pose("selection"), "The selection back to rest."),
                   ("Key", _picker_key, "Key the selection."))):
        _buttons(list(items), width=80)
    cmds.scriptJob(event=["SelectionChanged", guard(_picker_highlight)], parent=PK + "Root")
    picker_fill()


def show_picker(*_):
    """The picker (Qt: zoom, pan, drag-select, edit mode). Without Qt: the simple button picker."""
    try:
        from gus_animtool import pickerqt
    except ImportError:
        pickerqt = None
    if pickerqt is not None and not opt("simple_picker", 0):
        try:
            return pickerqt.show()
        except Exception:                                    # never leave the animator without a picker
            print(traceback.format_exc())
            message("the new picker failed (details in the Script Editor) - opening the simple one.", "warn")
    return show_simple_picker()


def show_simple_picker(*_):
    if cmds.workspaceControl(PICKER, exists=True):
        cmds.deleteUI(PICKER)
    cmds.workspaceControl(PICKER, label="Gus Animtool - Picker", floating=True, retain=False, initialWidth=PICK_W + 20,
                          minimumWidth=PICK_W, uiScript="import gus_animtool.anim as _a; _a._build_picker()")
    if not cmds.tabLayout(PK + "Tabs", exists=True):
        _build_picker()
    return PICKER


# ===========================================================================
# pose library: poses saved to files (one folder per character), applied fully, by side, mirrored, blended
# ===========================================================================

LIBRARY = "gusAnimLibraryWorkspace"
PL = "gusAnimLib_"
_lib = {"picked": None}


def library_root():
    import os
    got = opt("library", "")
    if got:
        return got
    try:
        base = cmds.internalVar(userAppDir=True)
    except (RuntimeError, AttributeError):
        base = os.path.expanduser("~")
    return os.path.join(base, "gus_anim_library")


def character_folder(ns=None):
    import os
    ns = current_character() if ns is None else ns
    name = (ns or "").strip(":").replace(":", "_") or "rig"
    path = os.path.join(library_root(), name)
    if not os.path.isdir(path):
        os.makedirs(path)
    if path not in _SEEDED and not os.path.exists(os.path.join(path, ".rig_poses_seeded")):
        _SEEDED.add(path)                               # 5.6.22: the rigger's poses, once (looked for once a session)
        try:
            _seed(path, rig_poses_folder(ns))
        except Exception:
            pass
    return path


_SEEDED = set()


def rig_poses_folder(ns=None):
    """5.6.22: the poses the rigger delivered with the rig: <the rig's file>_poses next to it (or None)."""
    import os
    ns = current_character() if ns is None else ns
    ctrls = character_controls(ns)
    if not ctrls:
        return None
    try:
        f = cmds.referenceQuery(ctrls[0], filename=True, withoutCopyNumber=True) if \
            cmds.referenceQuery(ctrls[0], isNodeReferenced=True) else cmds.file(query=True, sceneName=True)
    except RuntimeError:
        return None
    path = os.path.splitext(f)[0] + "_poses" if f else None
    return path if path and os.path.isdir(path) else None


def _seed(path, src, overwrite=False):
    """The rig's poses (and clips) into the library folder - the ones not there already. Returns how many."""
    import os
    import shutil
    n = 0
    if src and os.path.isdir(src):
        for root, _dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            to = path if rel == "." else os.path.join(path, rel)
            for f in files:
                if not f.endswith((".json", ".png")):
                    continue
                if not os.path.isdir(to):
                    os.makedirs(to)
                if overwrite or not os.path.exists(os.path.join(to, f)):
                    shutil.copy2(os.path.join(root, f), os.path.join(to, f))
                    n += f.endswith(".json")
    if src:
        open(os.path.join(path, ".rig_poses_seeded"), "w").close()
    return n


def get_rig_poses(ns=None):
    """Library > Get the rig's poses: the delivered ones not in your library yet (yours aren't touched)."""
    src = rig_poses_folder(ns)
    if not src:
        raise RuntimeError("no poses came with this rig (a <rig file>_poses folder next to it).")
    return _seed(character_folder(ns), src)


_bare = bare


def capture_pose(nodes):
    """{control name without namespace: {attr: value}}: translate / rotate / scale and number attributes."""
    out = {}
    for n in nodes:
        values = {}
        for a in _T + _R + _S:
            plug = n + "." + a
            if cmds.objExists(plug) and _settable(plug):
                values[a] = cmds.getAttr(plug)
        values.update(_custom(n))
        if values:
            out[_bare(n)] = values
    return out


ALL_FOLDERS, NO_FOLDER = "All folders", "(no folder)"
NOT_POSE_FOLDERS = ("clips",)                       # the clip library lives next to the poses


def _clean_name(text, fallback="pose"):
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in (text or "").strip()) or fallback


def _pose_path(name, ns=None, ext=".json"):
    """A pose name is 'fist' or 'Hands/fist' (in the folder Hands)."""
    import os
    return os.path.join(character_folder(ns), *name.split("/")) + ext


def pose_folders(ns=None):
    """The character's pose folders (sorted)."""
    import os
    root = character_folder(ns)
    return sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))
                  and d.lower() not in NOT_POSE_FOLDERS)


def pose_files(ns=None, folder=None, search=""):
    """Pose names ('fist', 'Hands/fist'). folder: None / ALL_FOLDERS every pose, '' or NO_FOLDER only the ones in
    no folder, else that folder's. search: part of the name (any case)."""
    import os
    root = character_folder(ns)
    out = [f[:-5] for f in os.listdir(root) if f.endswith(".json")]
    for d in pose_folders(ns):
        out += ["%s/%s" % (d, f[:-5]) for f in os.listdir(os.path.join(root, d)) if f.endswith(".json")]
    if folder not in (None, ALL_FOLDERS):
        want = "" if folder in ("", NO_FOLDER) else folder
        out = [n for n in out if (n.rsplit("/", 1)[0] if "/" in n else "") == want]
    text = (search or "").strip().lower()
    if text:
        out = [n for n in out if text in n.lower()]
    return sorted(out, key=lambda n: (n.count("/"), n.lower()))


def make_folder(name, ns=None):
    import os
    name = _clean_name(name, "folder")
    if name.lower() in NOT_POSE_FOLDERS:
        name += "_poses"
    path = os.path.join(character_folder(ns), name)
    if not os.path.isdir(path):
        os.makedirs(path)
    return name


def snap_picture(name, ns=None):
    """A picture of the viewport for the pose (replaces the old one). True when made."""
    import os
    path = _pose_path(name, ns, ".png")
    try:
        frame = cmds.currentTime(query=True)
        cmds.playblast(frame=[frame], format="image", compression="png", viewer=False, showOrnaments=False,
                       completeFilename=path, widthHeight=(120, 120), percent=100, forceOverwrite=True,
                       clearCache=True)
    except Exception:
        return False
    return os.path.exists(path)


def save_pose(name, nodes, ns=None, thumbnail=True, folder=""):
    import os
    name = _clean_name(name)
    if folder and folder not in (ALL_FOLDERS, NO_FOLDER):
        name = make_folder(folder, ns) + "/" + name
    data = {"version": VERSION, "controls": capture_pose(nodes)}
    path = _pose_path(name, ns)
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with open(path, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    if thumbnail:
        snap_picture(name, ns)
    return name, len(data["controls"])


def load_pose(name, ns=None):
    with open(_pose_path(name, ns)) as f:
        return json.load(f).get("controls", {})


def delete_pose(name, ns=None):
    import os
    for ext in (".json", ".png"):
        p = _pose_path(name, ns, ext)
        if os.path.exists(p):
            os.remove(p)


def _move_files(old, new, ns):
    import os
    if os.path.exists(_pose_path(new, ns)):
        raise RuntimeError("there's already a pose '%s'." % new)
    d = os.path.dirname(_pose_path(new, ns))
    if not os.path.isdir(d):
        os.makedirs(d)
    for ext in (".json", ".png"):
        if os.path.exists(_pose_path(old, ns, ext)):
            os.rename(_pose_path(old, ns, ext), _pose_path(new, ns, ext))
    return new


def rename_pose(name, new_name, ns=None):
    """Same folder, new name. Returns the new pose name."""
    folder = name.rsplit("/", 1)[0] + "/" if "/" in name else ""
    return _move_files(name, folder + _clean_name(new_name), ns)


def move_pose(name, folder, ns=None):
    """Into folder ('' / NO_FOLDER: out of any folder). Returns the new pose name."""
    base = name.rsplit("/", 1)[-1]
    target = "" if folder in ("", NO_FOLDER, ALL_FOLDERS) else make_folder(folder, ns) + "/"
    return name if target + base == name else _move_files(name, target + base, ns)


def update_pose(name, ns=None, nodes=None):
    """The pose takes the controls' values now (the same controls it had, or nodes). Its picture stays.
    Returns how many controls were saved."""
    ns = current_character() if ns is None else ns
    if nodes is None:
        nodes = [x[0] for x in (cmds.ls((ns + k) if ns else k, long=True) for k in load_pose(name, ns))
                 if len(x) == 1]
    if not nodes:
        raise RuntimeError("none of the pose's controls are in the scene.")
    data = {"version": VERSION, "controls": capture_pose(nodes)}
    with open(_pose_path(name, ns), "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)
    return len(data["controls"])


def _set_value(plug, cur, target, amount):
    if isinstance(target, bool) or cmds.getAttr(plug, type=True) in ("bool", "enum", "long", "short", "byte"):
        v = target if amount >= 0.5 else cur
    else:
        v = cur + (target - cur) * amount
    if abs(v - cur) > 1e-7:
        cmds.setAttr(plug, v)


def apply_pose(pose, ns=None, amount=1.0, side=None, mirrored=False, only=None):
    """Put a saved pose on the character. amount 0-1 blends from the current pose; side 'L' / 'R': only
    that side's controls (and the centre ones); mirrored: each control's values go to its twin; only: a set
    of controls (long names) - the selection. Returns how many controls changed."""
    ns = current_character() if ns is None else ns
    nodes = {}
    for name in pose:
        found = cmds.ls((ns + name) if ns else name, long=True) or []
        if len(found) == 1:
            nodes[name] = found[0]
    targets = {}                                    # node -> {attr: value}
    if mirrored:
        involved = set(nodes.values()) | set(t for t in (twin_of(n) for n in nodes.values()) if t)
        before = {n: capture_pose([n]).get(_bare(n), {}) for n in involved}
        for name, n in nodes.items():               # the pose on its own controls first (to read it back)
            for a, v in pose[name].items():
                if cmds.objExists(n + "." + a) and _settable(n + "." + a):
                    cmds.setAttr(n + "." + a, v)
        for name, n in nodes.items():
            dst = twin_of(n) or (n if side_of(n) == "C" else None)
            if not dst:
                continue
            t, r, s = pose_target(n, dst)
            vals = dict(zip(_T + _R + _S, list(t) + list(r) + list(s)))
            vals.update({a: v for a, v in pose[name].items() if a not in vals})
            targets[dst] = vals
        for n, vals in before.items():               # back to how it was, then blend into the result
            for a, v in vals.items():
                try:
                    cmds.setAttr(n + "." + a, v)
                except RuntimeError:
                    pass
    else:
        targets = {n: pose[name] for name, n in nodes.items()}
    count = 0
    for n, vals in targets.items():
        if side and side_of(n) not in (side, "C"):
            continue
        if only is not None and n not in only:
            continue
        for a, v in vals.items():
            plug = n + "." + a
            if not cmds.objExists(plug) or not _settable(plug):
                continue
            try:
                _set_value(plug, cmds.getAttr(plug), v, amount)
            except (RuntimeError, TypeError):
                pass
        count += 1
    return count


def _lib_char():
    try:
        label = cmds.optionMenu(PL + "Char", query=True, value=True) or ""
    except RuntimeError:
        return current_character()
    return "" if label in ("", ROOT) else label


def _lib_get_rig_poses(*_):
    n = get_rig_poses(_lib_char())
    library_fill()
    message("%d pose(s) from the rig added to your library." % n if n else "you have every pose of the rig already.")


def _lib_filter():
    """(folder, search) chosen in the library window."""
    folder, search = ALL_FOLDERS, ""
    try:
        folder = cmds.optionMenu(PL + "Folders", query=True, value=True) or ALL_FOLDERS
        search = cmds.textField(PL + "Search", query=True, text=True) or ""
    except RuntimeError:
        pass
    return folder, search


def _lib_fill_folders(ns, keep=None):
    menu = PL + "Folders"
    if not cmds.optionMenu(menu, exists=True):
        return
    keep = keep or cmds.optionMenu(menu, query=True, value=True) or ALL_FOLDERS
    for item in cmds.optionMenu(menu, query=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    labels = [ALL_FOLDERS, NO_FOLDER] + pose_folders(ns)
    for label in labels:
        cmds.menuItem(label=label, parent=menu)
    cmds.optionMenu(menu, edit=True, select=(labels.index(keep) + 1) if keep in labels else 1)


def library_fill(*_):
    import os
    grid = PL + "Grid"
    if not cmds.gridLayout(grid, exists=True):
        return
    for c in cmds.gridLayout(grid, query=True, childArray=True) or []:
        cmds.deleteUI(c)
    ns = _lib_char()
    _lib_fill_folders(ns)
    folder, search = _lib_filter()
    names = pose_files(ns, folder, search)
    for name in names:
        img = _pose_path(name, ns, ".png")
        cmds.iconTextButton(parent=grid, style="iconAndTextVertical", label=name.rsplit("/", 1)[-1],
                            annotation=name, image=img if os.path.exists(img) else "pose.png", width=90,
                            height=100, command=guard(lambda *_, x=name: _lib_pick(x)))
    cmds.text(PL + "Folder", edit=True, label="  %s   (%d pose(s) shown)" % (character_folder(ns), len(names)))
    _lib_pick(_lib["picked"] if _lib["picked"] in pose_files(ns) else None)


def _lib_pick(name):
    _lib["picked"] = name
    if cmds.text(PL + "Picked", exists=True):
        cmds.text(PL + "Picked", edit=True, label="  Pose: " + (name or "(click a pose)"))


def _lib_save(*_):
    ns = _lib_char()
    sel = [n for n in selected() if _poseable(n)]
    nodes = sel or character_controls(ns)
    if not nodes:
        raise RuntimeError("no controls found for this character.")
    if cmds.promptDialog(title="Save pose", message="Pose name (%s):" % ("the %d selected controls" % len(sel)
                                                                       if sel else "the whole character"),
                         button=["Save", "Cancel"], defaultButton="Save", cancelButton="Cancel",
                         dismissString="Cancel") != "Save":
        return
    folder, _search = _lib_filter()
    name, n = save_pose(cmds.promptDialog(query=True, text=True), nodes, ns, folder=folder)
    _lib["picked"] = name
    library_fill()
    message("pose '%s' saved (%d controls)." % (name, n))


def _lib_apply(mirrored=False):
    name = _lib["picked"]
    if not name:
        raise RuntimeError("click a pose first.")
    ns = _lib_char()
    amount = cmds.intSliderGrp(PL + "Amount", query=True, value=True) / 100.0
    side = {1: None, 2: "L", 3: "R"}[cmds.optionMenu(PL + "Side", query=True, select=True)]
    only = None
    if cmds.optionMenu(PL + "Scope", query=True, select=True) == 2:
        only = set(cmds.ls(selection=True, long=True) or [])
        if not only:
            raise RuntimeError("'Selected controls' is on: select the controls to change.")
    with Undo("gusAnimPose"):
        n = apply_pose(load_pose(name, ns), ns, amount, side, mirrored, only)
    message("pose '%s'%s on %d control(s) at %d%%." % (name, " mirrored" if mirrored else "", n, amount * 100))


def _lib_select(*_):
    name = _lib["picked"]
    if not name:
        raise RuntimeError("click a pose first.")
    ns = _lib_char()
    nodes = [x for x in (cmds.ls((ns + k) if ns else k, long=True) for k in load_pose(name, ns)) if len(x) == 1]
    cmds.select([x[0] for x in nodes], replace=True)


def _lib_delete(*_):
    name = _lib["picked"]
    if not name:
        raise RuntimeError("click a pose first.")
    if cmds.confirmDialog(title="Delete pose", message="Delete the pose '%s' (its file)?" % name,
                          button=["Delete", "Cancel"], defaultButton="Cancel", cancelButton="Cancel",
                          dismissString="Cancel") != "Delete":
        return
    delete_pose(name, _lib_char())
    _lib["picked"] = None
    library_fill()


def _lib_need():
    if not _lib["picked"]:
        raise RuntimeError("click a pose first.")
    return _lib["picked"]


def _ask(title, message_, text=""):
    if cmds.promptDialog(title=title, message=message_, text=text, button=["OK", "Cancel"], defaultButton="OK",
                         cancelButton="Cancel", dismissString="Cancel") != "OK":
        return None
    return (cmds.promptDialog(query=True, text=True) or "").strip()          # "" = OK with nothing typed


def _lib_new_folder(*_):
    name = _ask("New folder", "Folder name (e.g. Hands, Face, Expressions):")
    if name:
        made = make_folder(name, _lib_char())
        _lib_fill_folders(_lib_char(), keep=made)
        library_fill()
        message("folder '%s' made: new poses go in it while it's picked." % made)


def _lib_rename(*_):
    name = _lib_need()
    new = _ask("Rename pose", "New name:", name.rsplit("/", 1)[-1])
    if new:
        _lib["picked"] = rename_pose(name, new, _lib_char())
        library_fill()


def _lib_move(*_):
    name = _lib_need()
    ns = _lib_char()
    target = _ask("Move to folder", "Folder (existing or new; empty = out of any folder). Folders: %s"
                  % (", ".join(pose_folders(ns)) or "none yet"))
    if target is None:
        return
    _lib["picked"] = move_pose(name, target, ns)
    library_fill()
    message("pose moved: %s" % _lib["picked"])


def _lib_update(*_):
    name = _lib_need()
    if cmds.confirmDialog(title="Update pose", message="Save the current values into '%s'?\n(The same controls; "
                          "its picture stays - Update picture retakes it.)" % name, button=["Update", "Cancel"],
                          defaultButton="Update", cancelButton="Cancel", dismissString="Cancel") != "Update":
        return
    n = update_pose(name, _lib_char())
    message("pose '%s' updated (%d controls)." % (name, n))


def _lib_picture(*_):
    name = _lib_need()
    if snap_picture(name, _lib_char()):
        library_fill()
        message("new picture for '%s'." % name)
    else:
        raise RuntimeError("couldn't take the picture (is a viewport open?).")


def _lib_preview(mirrored=False):
    """Try the pose on (one undo): Keep leaves it, Back takes it off."""
    if _lib.get("preview"):
        _lib_back()
    _lib_apply(mirrored)
    _lib["preview"] = True
    message("previewing - Keep or Back.")


def _lib_back(*_):
    if not _lib.get("preview"):
        raise RuntimeError("nothing is being previewed.")
    _lib["preview"] = False
    cmds.undo()
    message("preview taken off.")


def _lib_keep(*_):
    _lib["preview"] = False
    message("kept.")


def _lib_folder(*_):
    got = cmds.fileDialog2(fileMode=3, dialogStyle=2, startingDirectory=library_root(),
                           caption="Pose library folder (shared by every scene)")
    if got:
        set_opt("library", got[0])
        library_fill()


def _build_library():
    if cmds.gridLayout(PL + "Grid", exists=True):
        return
    cmds.setParent(LIBRARY)
    cmds.columnLayout(PL + "Root", adjustableColumn=True, rowSpacing=3)
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 2), (2, "both", 2),
                                                                        (3, "both", 2)])
    cmds.text(label="Character")
    cmds.optionMenu(PL + "Char", changeCommand=guard(library_fill))
    for ns in characters() or [""]:
        cmds.menuItem(label=ns or ROOT)
    cmds.button(label="Folder...", command=guard(_lib_folder), annotation="Where the poses are saved (one shared "
                "folder; a sub-folder per character).")
    cmds.setParent("..")
    cmds.text(PL + "Folder", label="", align="left", font="smallPlainLabelFont")
    cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 2), (2, "both", 2),
                                                                        (3, "both", 2)])
    cmds.optionMenu(PL + "Folders", changeCommand=guard(library_fill),
                    annotation="Show one folder's poses (new poses are saved in it).")
    cmds.menuItem(label=ALL_FOLDERS)
    cmds.textField(PL + "Search", placeholderText="search poses", textChangedCommand=guard(library_fill),
                   annotation="Part of a pose's name.")
    cmds.button(label="New folder", command=guard(_lib_new_folder))
    cmds.setParent("..")
    cmds.button(label="Get the rig's poses", command=guard(_lib_get_rig_poses),
                annotation="The poses the rigger delivered with the rig (a folder next to the rig file) - the ones "
                           "you don't have yet. They came in by themselves the first time.")
    cmds.button(label="Save pose (selection, or the whole character)", height=28, backgroundColor=MAIN_BG,
                command=guard(_lib_save), annotation="Saves the values and a picture of the viewport (in the "
                "folder picked above).")
    cmds.scrollLayout(height=230, childResizable=True)
    cmds.gridLayout(PL + "Grid", numberOfColumns=3, cellWidthHeight=(96, 104), autoGrow=True)
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.text(PL + "Picked", label="  Pose: (click a pose)", align="left", font="boldLabelFont")
    cmds.intSliderGrp(PL + "Amount", label="Amount %", field=True, minValue=0, maxValue=100, value=100,
                      columnWidth3=(60, 40, 200), annotation="100: the pose; 50: half way from the current pose.")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(40, 90, 50, 130), columnAttach=[(i + 1, "both", 2)
                                                                                    for i in range(4)])
    cmds.text(label="Side")
    cmds.optionMenu(PL + "Side")
    for x in ("Both", "Left only", "Right only"):
        cmds.menuItem(label=x)
    cmds.text(label="On")
    cmds.optionMenu(PL + "Scope")
    for x in ("Whole pose", "Selected controls"):
        cmds.menuItem(label=x)
    cmds.setParent("..")
    _buttons([("Apply", lambda *_: _lib_apply(False), "The pose on the character (one undo)."),
              ("Apply mirrored", lambda *_: _lib_apply(True), "Left and right swapped (needs twin names)."),
              ("Select its controls", _lib_select, "The controls the pose has.")], width=110)
    _buttons([("Preview", lambda *_: _lib_preview(False), "Try the pose on: Keep or Back."),
              ("Preview mirrored", lambda *_: _lib_preview(True), "Try it on mirrored: Keep or Back."),
              ("Back", _lib_back, "Take the preview off."),
              ("Keep", _lib_keep, "Leave the preview on.")])
    _buttons([("Rename...", _lib_rename, "A new name (same folder)."),
              ("Move to folder...", _lib_move, "Into a folder (new or existing)."),
              ("Update pose", _lib_update, "The current values into this pose (asks first)."),
              ("Update picture", _lib_picture, "A new picture from the viewport.")])
    _buttons([("Refresh", library_fill, "Read the folder again."),
              ("Delete pose", _lib_delete, "Delete the picked pose's files (asks first).")], width=165)
    library_fill()


def show_library(*_):
    if cmds.workspaceControl(LIBRARY, exists=True):
        cmds.deleteUI(LIBRARY)
    cmds.workspaceControl(LIBRARY, label="Gus Animtool - Poses", floating=True, retain=False, initialWidth=340,
                          minimumWidth=320, uiScript="import gus_animtool.anim as _a; _a._build_library()")
    if not cmds.gridLayout(PL + "Grid", exists=True):
        _build_library()
    return LIBRARY


# ===========================================================================
# window
# ===========================================================================

def _end():
    cmds.setParent("..")
    cmds.setParent("..")


def _buttons(items, width=None):
    """A row of buttons sharing the width evenly (they stretch with the window). width: ignored (old calls)."""
    form = cmds.formLayout(height=28, numberOfDivisions=1000)
    n = len(items)
    attach = []
    for i, (label, fn, tip) in enumerate(items):
        b = cmds.button(label=label, command=guard(fn), annotation=tip, height=26)
        attach += [(b, "left", 2, int(1000 * i / n)), (b, "right", 2, int(1000 * (i + 1) / n))]
    cmds.formLayout(form, edit=True, attachPosition=attach)
    cmds.setParent("..")


def fill_characters(*_):
    menu = P + "Char"
    if not cmds.optionMenu(menu, exists=True):
        return
    keep = current_character()
    for item in cmds.optionMenu(menu, query=True, itemListLong=True) or []:
        cmds.deleteUI(item)
    chars = characters() or [""]
    for ns in chars:
        gus = " (Gus rig)" if with_attr("gusBlend", ns) else ""
        cmds.menuItem(label=(ns or ROOT) + ("   " + gus.strip() if gus else ""), parent=menu)
    if keep in chars:
        menu_select(menu, chars.index(keep) + 1)


def _follow_selection(*_):
    sel = selected()
    if sel and cmds.optionMenu(P + "Char", exists=True):
        ns = namespace_of(sel[0])
        chars = characters() or [""]
        if ns in chars and ns != current_character():
            listed = cmds.optionMenu(P + "Char", query=True, numberOfItems=True) or 0
            if listed != len(chars):                       # a rig referenced after the window opened
                fill_characters()
            menu_select(P + "Char", chars.index(ns) + 1)
    fill_space_menus()


SWITCH_VALUES = [(0.0, 1.0), (1.0, 0.0), (0.0, 10.0), (10.0, 0.0)]


def _range_from_slider(*_):
    cmds.intField(P + "Start", edit=True, value=int(cmds.playbackOptions(query=True, minTime=True)))
    cmds.intField(P + "End", edit=True, value=int(cmds.playbackOptions(query=True, maxTime=True)))


def _teach_take(key):
    if key == "TSwitch":
        sel = selected()
        attrs = cmds.channelBox("mainChannelBox", query=True, selectedMainAttributes=True) or []
        if not sel or not attrs:
            raise RuntimeError("select the control, click the switch attribute in the channel box, then <.")
        node = sel[0]
        long_attr = cmds.attributeQuery(attrs[0], node=node, longName=True)
        cmds.textField(P + key, edit=True, text=short(node) + "." + long_attr)
        return
    sel = selected()
    if not sel:
        raise RuntimeError("select something first.")
    cmds.textField(P + key, edit=True, text=" ".join(short(n) for n in sel))


def _field_nodes(key):
    out = []
    for n in cmds.textField(P + key, query=True, text=True).split():
        found = long_name(n)
        if not found:
            raise RuntimeError("'%s' not found." % n)
        out.append(found)
    return out


def _teach(*_):
    name = cmds.textField(P + "TName", query=True, text=True).strip()
    if not name:
        raise RuntimeError("give the limb a name (e.g. L_arm).")
    ik = _field_nodes("TIk")
    pv = _field_nodes("TPv")
    sw = cmds.textField(P + "TSwitch", query=True, text=True).strip()
    if sw and "." in sw:
        node = long_name(sw.split(".")[0])
        sw = (node + "." + sw.split(".", 1)[1]) if node else sw
    a, b = SWITCH_VALUES[cmds.optionMenu(P + "TValues", query=True, select=True) - 1]
    teach(name, _field_nodes("TFk"), _field_nodes("TJoints"), ik[0] if ik else None, pv[0] if pv else None,
          sw, a, b)
    cmds.text(P + "TList", edit=True, label=_taught_label())


def _forget(*_):
    forget(cmds.textField(P + "TName", query=True, text=True).strip())
    cmds.text(P + "TList", edit=True, label=_taught_label())


def _taught_label():
    names = sorted(taught_data())
    return "Taught: " + (", ".join(names) if names else "none yet")


def _export_taught(*_):
    got = cmds.fileDialog2(fileFilter="Gus Anim limbs (*.json)", dialogStyle=2, fileMode=0)
    if got:
        export_taught(got[0])


def _import_taught(*_):
    got = cmds.fileDialog2(fileFilter="Gus Anim limbs (*.json)", dialogStyle=2, fileMode=1)
    if got:
        import_taught(got[0])
        cmds.text(P + "TList", edit=True, label=_taught_label())


def _save_options(*_):
    if cmds.checkBox(P + "KeysOnly", exists=True):
        set_opt("range_keys_only", cmds.checkBox(P + "KeysOnly", query=True, value=True))
    if cmds.checkBox(P + "Wrap", exists=True):
        set_opt("anim_wrap", cmds.checkBox(P + "Wrap", query=True, value=True))
        set_opt("anim_offset", cmds.intField(P + "AnimOffset", query=True, value=True))
    set_opt("key_switch", cmds.checkBox(P + "KeySwitch", query=True, value=True))
    set_opt("pose_custom", cmds.checkBox(P + "Custom", query=True, value=True))
    set_opt("left", cmds.textField(P + "Left", query=True, text=True))
    set_opt("right", cmds.textField(P + "Right", query=True, text=True))
    set_opt("suffix", cmds.textField(P + "Suffix", query=True, text=True))


def show(*_):
    """The Gus Animtool window."""
    from gus_animtool import ui
    return ui.show()
