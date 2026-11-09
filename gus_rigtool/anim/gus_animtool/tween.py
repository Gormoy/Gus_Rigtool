"""
Tween / pose slider (like tweenMachine and Animo's push / pull), on the selected controls at the current frame:

  Between keys : 0 = the previous key's pose, 100 = the next key's pose (below 0 / above 100: overshoot).
  From rest    : 0 = as it is, + pushes the pose further from rest, - pulls it towards rest (-100 = rest).
  Mirror       : 0 = as it is, 100 = the mirror of the twin's pose (centre controls: their own mirror).

The slider shows the result live while you drag (no undo steps); letting go applies it once (one undo) and
keys it when 'Key it' is on (or Maya's auto key is on).
"""

import maya.cmds as cmds

from gus_animtool import anim as A

MODES = ["Between keys", "From rest", "Mirror"]
NUMERIC = ("double", "float", "long", "short", "byte", "doubleLinear", "doubleAngle", "time")
_drag = {"start": None}


def _attrs(node):
    out = []
    for a in cmds.listAttr(node, keyable=True, unlocked=True) or []:
        plug = node + "." + a
        try:
            if "." in a or cmds.getAttr(plug, type=True) not in NUMERIC or not A._settable(plug):
                continue
        except (RuntimeError, ValueError):
            continue
        out.append(a)
    return out


def _keys(plug):
    return sorted(set(cmds.keyframe(plug, query=True, timeChange=True) or []))


def _between(plug, t):
    """(previous key value, next key value) around frame t, or None when the plug has no key on one side."""
    keys = _keys(plug)
    before = [k for k in keys if k < t - 1e-4]
    after = [k for k in keys if k > t + 1e-4]
    if not before or not after:
        return None
    return cmds.getAttr(plug, time=before[-1]), cmds.getAttr(plug, time=after[0])


def _rest(node, attr):
    try:
        saved = A.json.loads(A.meta_str(node, "gusDefaultPose") or "{}")
    except ValueError:
        saved = {}
    if attr in saved:
        return saved[attr]
    try:
        d = cmds.attributeQuery(attr, node=node, listDefault=True)
        return d[0] if d else (1.0 if attr.startswith("scale") else 0.0)
    except (RuntimeError, TypeError):
        return 1.0 if attr.startswith("scale") else 0.0


def _mirror_targets(nodes):
    out = {}
    for n in nodes:
        twin = A.twin_of(n)
        src = twin if twin else (n if A.side_of(n) == "C" else None)
        if not src:
            continue
        t, r, s = A.pose_target(src, n)
        vals = dict(zip(A._T + A._R + A._S, list(t) + list(r) + list(s)))
        vals.update(A._custom(src))
        out[n] = vals
    return out


def targets(nodes, mode, amount, t=None):
    """{plug: value} for the slider at 'amount' (a fraction: 0.5 = 50)."""
    t = cmds.currentTime(query=True) if t is None else t
    out = {}
    mirror = _mirror_targets(nodes) if mode == 2 else {}
    for n in nodes:
        for a in _attrs(n):
            plug = n + "." + a
            cur = cmds.getAttr(plug)
            if mode == 0:
                pn = _between(plug, t)
                if pn is None:
                    continue
                out[plug] = pn[0] + (pn[1] - pn[0]) * amount
            elif mode == 1:
                rest = _rest(n, a)
                out[plug] = rest + (cur - rest) * (1.0 + amount)
            else:
                if a not in mirror.get(n, {}):
                    continue
                out[plug] = cur + (mirror[n][a] - cur) * amount
    return out


def _set(values):
    for plug, v in values.items():
        try:
            if cmds.getAttr(plug, type=True) in ("long", "short", "byte"):
                v = int(round(v))
            cmds.setAttr(plug, v)
        except (RuntimeError, ValueError):
            pass


def _key_on():
    try:
        return bool(A.opt("tween_key", 1)) or bool(cmds.autoKeyframe(query=True, state=True))
    except RuntimeError:
        return True


def apply(nodes, mode, amount, key=None):
    """Put the tween on the nodes (one undo) and key the changed attributes. Returns how many attributes."""
    values = targets(nodes, mode, amount)
    if not values:
        raise RuntimeError({0: "no key before and after this frame on the selection (Between keys needs both).",
                            1: "nothing to push / pull on the selection.",
                            2: "no twins / centre controls to mirror in the selection."}[mode])
    with A.Undo("gusAnimtoolTween"):
        _set(values)
        if (_key_on() if key is None else key):
            for plug in values:
                node, attr = plug.split(".", 1)
                cmds.setKeyframe(node, attribute=attr)
    return len(values)


# live slider: values shown while dragging without undo steps, applied once on release

def drag(nodes, mode, amount):
    if _drag["start"] is None:
        _drag["start"] = {n + "." + a: cmds.getAttr(n + "." + a) for n in nodes for a in _attrs(n)}
        _drag["nodes"] = list(nodes)
    with A.NoUndo():
        _set(_original_then(lambda: targets(_drag["nodes"], mode, amount)))


def _original_then(fn):
    """Work out the targets from the pose before the drag (so dragging doesn't build on itself)."""
    now = {p: cmds.getAttr(p) for p in _drag["start"]}
    _set(_drag["start"])
    try:
        return fn()
    finally:
        _set(now)


def release(mode, amount):
    start = _drag.get("start")
    nodes = _drag.get("nodes") or []
    _drag["start"] = None
    if start is None:
        return 0
    with A.NoUndo():
        _set(start)
    return apply(nodes, mode, amount)


def step(direction, amount=0.33):
    """Hotkey: move the selection a third of the way to the previous (-1) / next (+1) key's pose."""
    nodes = [n for n in A.selected() if A._poseable(n)]
    if not nodes:
        raise RuntimeError("select controls first.")
    t = cmds.currentTime(query=True)
    values = {}
    for n in nodes:
        for a in _attrs(n):
            plug = n + "." + a
            pn = _between(plug, t)
            if pn is None:
                continue
            cur = cmds.getAttr(plug)
            values[plug] = cur + ((pn[1] if direction > 0 else pn[0]) - cur) * amount
    if not values:
        raise RuntimeError("no keys around this frame on the selection.")
    with A.Undo("gusAnimtoolTweenStep"):
        _set(values)
        if _key_on():
            for plug in values:
                node, attr = plug.split(".", 1)
                cmds.setKeyframe(node, attribute=attr)
    return len(values)
