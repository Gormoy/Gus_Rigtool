"""
Key tools: nudge, add / remove inbetweens, key without changing the curve, clean up, Euler filter, copy / paste
pose and keys, offset (back to original) - and space switch key cleanup (keyed space changes that make the control jump).
Every action is one undo. They work on the keys selected in the Graph Editor when there are some, else on the
selected controls (or their keys at the current frame).
"""

import math

import maya.cmds as cmds

from gus_animtool import anim as A

_clip = {"pose": None, "from": ""}
BIG = 1.0e6


def _nodes():
    nodes = A.selected()
    if not nodes:
        raise RuntimeError("select controls first.")
    return nodes


def _graph_keys():
    """Curves with keys selected in the Graph Editor."""
    return cmds.keyframe(query=True, selected=True, name=True) or []


def nudge(frames):
    """Selected Graph Editor keys - or the selection's keys at the current frame - move by frames; the
    current frame follows. Returns how many curves."""
    curves = _graph_keys()
    t = cmds.currentTime(query=True)
    with A.Undo("gusAnimtoolNudge"):
        if curves:
            cmds.keyframe(curves, edit=True, relative=True, timeChange=frames, option="over", animation="keys")
            n = len(curves)
        else:
            nodes = _nodes()
            if not cmds.keyframe(nodes, query=True, time=(t, t), keyframeCount=True):
                raise RuntimeError("no keys at frame %g on the selection (or select keys in the Graph Editor)." % t)
            cmds.keyframe(nodes, edit=True, relative=True, timeChange=frames, time=(t, t), option="over")
            n = len(nodes)
        cmds.currentTime(t + frames, update=True)
    return n


def key_keep_curve(nodes=None):
    """A key on every keyed attribute at the current frame without changing the curves' shape."""
    nodes = nodes or _nodes()
    keyed = [n for n in nodes if A.time_curves(n)]
    fresh = [n for n in nodes if n not in keyed]
    with A.Undo("gusAnimtoolInsertKey"):
        if keyed:
            cmds.setKeyframe(keyed, insert=True)            # keeps the curves' shape
        if fresh:
            cmds.setKeyframe(fresh)                         # nothing keyed yet: a normal key
    return len(nodes)


def clean(nodes=None, tolerance=1e-4):
    """Delete keys that change nothing (same value as the keys on both sides) and curves that never change
    (the value is kept). Returns (keys deleted, static curves deleted)."""
    nodes = nodes or _nodes()
    keys_gone = static = 0
    with A.Undo("gusAnimtoolClean"):
        for c in A.time_curves(nodes):
            times = cmds.keyframe(c, query=True, timeChange=True) or []
            vals = cmds.keyframe(c, query=True, valueChange=True) or []
            if not times:
                continue
            if max(vals) - min(vals) <= tolerance:
                plugs = cmds.listConnections(c + ".output", source=False, destination=True, plugs=True) or []
                cmds.delete(c)
                for p in plugs:
                    try:
                        cmds.setAttr(p, vals[0])
                    except RuntimeError:
                        pass
                static += 1
                continue
            drop = [times[i] for i in range(1, len(times) - 1)
                    if abs(vals[i] - vals[i - 1]) <= tolerance and abs(vals[i] - vals[i + 1]) <= tolerance]
            for t in drop:
                cmds.cutKey(c, time=(t, t), clear=True)
            keys_gone += len(drop)
    return keys_gone, static


def euler(nodes=None):
    nodes = nodes or _nodes()
    curves = [c for c in A.time_curves(nodes) if A.is_rotation(c)]
    if not curves:
        raise RuntimeError("no rotation keys on the selection.")
    with A.Undo("gusAnimtoolEuler"):
        cmds.filterCurve(curves, filter="euler")
    return len(curves)


def copy_pose(nodes=None):
    nodes = nodes or _nodes()
    _clip["pose"] = A.capture_pose(nodes)
    _clip["from"] = A.namespace_of(nodes[0])
    return len(_clip["pose"])


def paste_pose(nodes=None, amount=1.0):
    """On the selected controls with the same names (any character / namespace)."""
    if not _clip["pose"]:
        raise RuntimeError("copy a pose first.")
    nodes = nodes or _nodes()
    ns = A.namespace_of(nodes[0])
    with A.Undo("gusAnimtoolPaste"):
        n = A.apply_pose(_clip["pose"], ns, amount, only=set(nodes))
    if not n:
        raise RuntimeError("none of the selected controls is in the copied pose (names don't match).")
    return n


# ---------------------------------------------------------------------------
# space switch key cleanup
# ---------------------------------------------------------------------------

def _matrix_gap(a, b):
    import math
    pos = math.sqrt(sum((a[12 + i] - b[12 + i]) ** 2 for i in range(3)))
    rot = max(abs(a[i] - b[i]) for i in range(12))
    return pos, rot


def space_jumps(nodes, tolerance=1e-3):
    """[(node, attr, frame, old value, new value)]: keyed space changes where the control jumps (it was keyed
    without a no-jump switch)."""
    out = []
    now = cmds.currentTime(query=True)
    try:
        for n in nodes:
            for attr, _names in A.space_attrs(n):
                plug = n + "." + attr
                times = sorted(set(cmds.keyframe(plug, query=True, timeChange=True) or []))
                for t0, t1 in zip(times, times[1:]):
                    v0, v1 = int(round(cmds.getAttr(plug, time=t0))), int(round(cmds.getAttr(plug, time=t1)))
                    if v0 == v1:
                        continue
                    cmds.currentTime(t1, update=True)
                    after = A.world(n)
                    with A.NoUndo():
                        cmds.setAttr(plug, v0)
                        before = A.world(n)
                        cmds.setAttr(plug, v1)
                    pos, rot = _matrix_gap(before, after)
                    if pos > tolerance or rot > tolerance:
                        out.append((n, attr, t1, v0, v1))
    finally:
        cmds.currentTime(now, update=True)
    return out


def fix_space_jumps(jumps):
    """At each switch frame the control keeps the place it had in the old space (keyed), and the space key
    holds (stepped). Returns how many fixed."""
    now = cmds.currentTime(query=True)
    with A.Undo("gusAnimtoolSpaceFix"):
        try:
            for n, attr, t, v0, v1 in jumps:
                plug = n + "." + attr
                cmds.currentTime(t - 1, update=True)
                cmds.setKeyframe(n, attribute=A._T + A._R)            # the frame before keeps its pose
                cmds.currentTime(t, update=True)
                cmds.setAttr(plug, v0)
                keep = A.world(n)
                cmds.setAttr(plug, v1)
                A.set_world(n, keep)
                cmds.setKeyframe(n, attribute=A._T + A._R)
                cmds.setKeyframe(plug)
                try:
                    cmds.keyTangent(plug, time=(t, t), outTangentType="step")
                except RuntimeError:
                    pass
        finally:
            cmds.currentTime(now, update=True)
    return len(jumps)


# ---------------------------------------------------------------------------
# Graph Editor key tools (ideas from Aaron Koressel's ackPushPull / ackNegateKeys / ackDeleteRedundant)
# ---------------------------------------------------------------------------

PIVOTS = ["left", "right", "last"]


def _selected_curves():
    curves = cmds.keyframe(query=True, selected=True, name=True) or []
    if not curves:
        raise RuntimeError("select keys in the Graph Editor first.")
    return curves


def _pivot_value(curve, pivot, last=None):
    """The value the keys scale around: the key just left / right of the selection on this curve, or the last
    selected key (all curves)."""
    if pivot == "last" and last is not None:
        return last
    times = sorted(cmds.keyframe(curve, query=True, selected=True, timeChange=True) or [])
    every = sorted(cmds.keyframe(curve, query=True, timeChange=True) or [])
    if not times:
        return None
    if pivot == "right":
        later = [t for t in every if t > times[-1] + 1e-4]
        t = later[0] if later else times[-1]
    else:
        earlier = [t for t in every if t < times[0] - 1e-4]
        t = earlier[-1] if earlier else times[0]
    v = cmds.keyframe(curve, query=True, time=(t, t), valueChange=True) or [0.0]
    return v[0]


def _scale_selected(value_scale, pivot):
    curves = _selected_curves()
    last = None
    if pivot == "last":
        got = cmds.keyframe(query=True, lastSelected=True, valueChange=True) or []
        last = got[0] if got else None
    n = 0
    with A.Undo("gusAnimtoolScaleKeys"):
        for c in curves:
            pv = _pivot_value(c, pivot, last)
            if pv is None:
                continue
            for i in cmds.keyframe(c, query=True, selected=True, indexValue=True) or []:
                cmds.scaleKey(c, index=(i, i), valuePivot=pv, valueScale=value_scale)
                n += 1
    return n


def push_pull(direction, factor=None, pivot=None):
    """direction 'push' (away from the pivot key: bigger motion) or 'pull' (towards it: softer).
    factor (0.9 by default): pull multiplies by it, push divides by it."""
    factor = float(factor or A.opt("pushpull_factor", 0.9))
    pivot = pivot or PIVOTS[max(0, int(A.opt("pushpull_pivot", 1)) - 1)]
    return _scale_selected((1.0 / factor) if direction == "push" else factor, pivot)


def negate(pivot=None):
    """The selected keys flipped upside down around the pivot key (the opposite pose / motion)."""
    pivot = pivot or PIVOTS[max(0, int(A.opt("pushpull_pivot", 1)) - 1)]
    return _scale_selected(-1.0, pivot)


def delete_redundant(tolerance=1e-5):
    """Among the keys selected in the Graph Editor, delete the ones with the same value as both neighbours."""
    curves = _selected_curves()
    gone = 0
    with A.Undo("gusAnimtoolDeleteRedundant"):
        for c in curves:
            times = cmds.keyframe(c, query=True, timeChange=True) or []
            vals = cmds.keyframe(c, query=True, valueChange=True) or []
            chosen = set(cmds.keyframe(c, query=True, selected=True, timeChange=True) or [])
            drop = [times[i] for i in range(1, len(times) - 1)
                    if times[i] in chosen and abs(vals[i] - vals[i - 1]) <= tolerance and
                    abs(vals[i] - vals[i + 1]) <= tolerance]
            for t in drop:
                cmds.cutKey(c, time=(t, t), clear=True)
            gone += len(drop)
    return gone


# ---------------------------------------------------------------------------
# rotation order, without changing the motion
# ---------------------------------------------------------------------------

ORDERS = ["xyz", "yzx", "zxy", "xzy", "yxz", "zyx"]


def convert_rotate_order(nodes, order):
    """Change the controls' rotate order; their rotation keys are re-made so the motion doesn't change (at every
    rotation key; Euler filter after). Returns how many controls."""
    new = ORDERS.index(order)
    now = cmds.currentTime(query=True)
    done = 0
    with A.Undo("gusAnimtoolRotateOrder"):
        try:
            for n in nodes:
                if cmds.getAttr(n + ".rotateOrder") == new or not A._settable(n + ".rotateOrder"):
                    continue
                frames = sorted(set(cmds.keyframe(n, attribute=["rotateX", "rotateY", "rotateZ"], query=True,
                                                  timeChange=True) or []))
                worlds = []
                for f in frames or [now]:
                    cmds.currentTime(f, update=True)
                    worlds.append((f, A.world(n)))
                cmds.setAttr(n + ".rotateOrder", new)
                for f, m in worlds:
                    cmds.currentTime(f, update=True)
                    A.set_world(n, m, translate=False)
                    if frames:
                        cmds.setKeyframe(n, attribute=["rotateX", "rotateY", "rotateZ"], time=f)
                if frames:
                    curves = [c for c in A.time_curves(n) if A.is_rotation(c)]
                    if curves:
                        cmds.filterCurve(curves, filter="euler")
                done += 1
        finally:
            cmds.currentTime(now, update=True)
    return done


# ---------------------------------------------------------------------------
# copy / paste keys (the current frame, or the range shift-dragged in the Time Slider)
# ---------------------------------------------------------------------------

_keys_clip = {"data": None, "span": 0.0}


def slider_range():
    """(start, end) of the range highlighted in the Time Slider (shift-drag), else None."""
    try:
        import maya.mel as mel
        slider = mel.eval("$gusAnimtoolTmp = $gPlayBackSlider")
        if not cmds.timeControl(slider, query=True, rangeVisible=True):
            return None
        a, b = cmds.timeControl(slider, query=True, rangeArray=True)
        return float(a), float(b) - 1.0                      # the array's end is one past the last frame
    except (RuntimeError, TypeError, ValueError, ImportError, AttributeError):
        return None


_bare = A.bare


def _curve_attr(curve):
    plug = (cmds.listConnections(curve + ".output", plugs=True, source=False, destination=True) or [None])[0]
    return plug.split(".", 1)[1] if plug else None


def copy_keys(nodes=None):
    """The selection's keys at the current frame (with no key there: the pose, every keyable channel), or every
    key inside the Time Slider's highlighted range. Returns (controls, keys)."""
    nodes = nodes or _nodes()
    rng = slider_range()
    now = cmds.currentTime(query=True)
    start, end = rng if rng else (now, now)
    data, count = {}, 0
    for n in nodes:
        attrs = {}
        for c in A.time_curves(n):
            attr = _curve_attr(c)
            if not attr:
                continue
            times = cmds.keyframe(c, query=True, time=(start, end), timeChange=True) or []
            if not times:
                continue
            vals = cmds.keyframe(c, query=True, time=(start, end), valueChange=True) or []
            itt = cmds.keyTangent(c, query=True, time=(start, end), inTangentType=True) or ["auto"] * len(times)
            ott = cmds.keyTangent(c, query=True, time=(start, end), outTangentType=True) or ["auto"] * len(times)
            attrs[attr] = [[t - start, v, i, o] for t, v, i, o in zip(times, vals, itt, ott)]
            count += len(times)
        if not rng:                                          # one frame: the whole pose, keyed or not
            for attr in cmds.listAttr(n, keyable=True, scalar=True) or []:
                if attr in attrs or not A._settable(n + "." + attr):
                    continue
                try:
                    attrs[attr] = [[0.0, cmds.getAttr(n + "." + attr), "auto", "auto"]]
                    count += 1
                except (RuntimeError, ValueError, TypeError):
                    pass
        if attrs:
            data[_bare(n)] = attrs
    if not data:
        raise RuntimeError("no keys in %s on the selection." % ("the highlighted range" if rng else "this frame"))
    _keys_clip["data"], _keys_clip["span"] = data, end - start
    return len(data), count


def paste_keys(nodes=None, merge=None):
    """The copied keys from the current frame on, matched by control name (one control copied: on every
    selected one). merge False: the keys already in the pasted span go first. Returns how many keys."""
    data = _keys_clip["data"]
    if not data:
        raise RuntimeError("copy keys first.")
    merge = bool(A.opt("paste_merge", 0)) if merge is None else merge
    nodes = nodes or _nodes()
    t0 = cmds.currentTime(query=True)
    span = _keys_clip["span"]
    one = list(data.values())[0] if len(data) == 1 else None
    n_keys = 0
    with A.Undo("gusAnimtoolPasteKeys"):
        for n in nodes:
            attrs = data.get(_bare(n)) or one
            if not attrs:
                continue
            for attr, keys in attrs.items():
                plug = n + "." + attr
                if not cmds.objExists(plug) or not A._settable(plug):
                    continue
                if not merge and span > 0:
                    try:
                        cmds.cutKey(n, attribute=attr, time=(t0, t0 + span), clear=True)
                    except RuntimeError:
                        pass
                for dt, v, itt, ott in keys:
                    t = t0 + dt
                    cmds.setKeyframe(n, attribute=attr, time=t, value=v)
                    try:
                        cmds.keyTangent(n, attribute=attr, time=(t, t), inTangentType=itt, outTangentType=ott)
                    except RuntimeError:
                        pass
                    n_keys += 1
    if not n_keys:
        raise RuntimeError("no selected control matches the copied names (copy one control to paste on any).")
    return n_keys


# ---------------------------------------------------------------------------
# add / remove inbetweens (selection, the whole character, or everything animated)
# ---------------------------------------------------------------------------

SCOPES = ["selection", "character", "scene"]
SCOPE_LABELS = ["Selected controls", "The whole character", "Everything animated"]


def scope_curves(scope=None):
    scope = scope or SCOPES[max(0, min(2, int(A.opt("inbetween_scope", 1)) - 1))]
    if scope == "scene":
        curves = cmds.ls(type=("animCurveTL", "animCurveTA", "animCurveTU", "animCurveTT")) or []
        return [c for c in curves if not cmds.referenceQuery(c, isNodeReferenced=True)] if curves else []
    nodes = A.character_controls() if scope == "character" else _nodes()
    return A.time_curves(nodes)


def inbetween(frames, scope=None):
    """frames > 0: every key after the current frame moves later (frames added); < 0: the frames after the
    current one go (their keys too) and the rest moves earlier. Returns the curves changed."""
    curves = scope_curves(scope)
    if not curves:
        raise RuntimeError("no keys to move (%s)." % (scope or "selection"))
    t = cmds.currentTime(query=True)
    with A.Undo("gusAnimtoolInbetween"):
        if frames < 0:
            gone = (t + 0.001, t - frames)
            if cmds.keyframe(curves, query=True, time=gone, keyframeCount=True):
                cmds.cutKey(curves, time=gone, clear=True)
        cmds.keyframe(curves, edit=True, relative=True, timeChange=frames, time=(t + 0.001, BIG))
    return len(curves)


# ---------------------------------------------------------------------------
# offset (all the same, or cascading) and back to the original timing
# ---------------------------------------------------------------------------

OFFSET_NODE = "gusAnimtool_offsets"
OFFSET_MODES = ["same", "cascade"]


def _offsets():
    import json
    if not cmds.objExists(OFFSET_NODE) or not cmds.attributeQuery("data", node=OFFSET_NODE, exists=True):
        return {}
    try:
        return json.loads(cmds.getAttr(OFFSET_NODE + ".data") or "{}")
    except ValueError:
        return {}


def _save_offsets(data):
    import json
    if not cmds.objExists(OFFSET_NODE):
        cmds.createNode("network", name=OFFSET_NODE)
    if not cmds.attributeQuery("data", node=OFFSET_NODE, exists=True):
        cmds.addAttr(OFFSET_NODE, longName="data", dataType="string")
    cmds.setAttr(OFFSET_NODE + ".data", json.dumps(data), type="string")


def offset(step, mode=None, nodes=None):
    """Every key of the selected controls moves by step frames (cascade: the 1st stays, the 2nd moves step, the
    3rd 2 x step... - overlap down a chain).
    Remembered, so 'back to original' undoes all of it later. Returns how many controls moved."""
    nodes = nodes or _nodes()
    mode = mode or OFFSET_MODES[max(0, min(1, int(A.opt("offset_mode", 1)) - 1))]
    if mode == "cascade" and len(nodes) < 2:
        raise RuntimeError("cascade: select 2 controls or more, base to tip (the first stays).")
    data = _offsets()
    moved = 0
    with A.Undo("gusAnimtoolOffset"):
        for i, n in enumerate(nodes):
            d = step * (i if mode == "cascade" else 1)              # cascade: the first stays, base to tip
            curves = A.time_curves(n)
            if not curves or not d:
                continue
            cmds.keyframe(curves, edit=True, relative=True, timeChange=d, option="over")
            for c in curves:
                data[c] = data.get(c, 0.0) + d
            moved += 1
        _save_offsets({c: v for c, v in data.items() if abs(v) > 1e-6})
    if not moved:
        raise RuntimeError("the selection has no keys.")
    return moved


def back_to_original(nodes=None):
    """The offset curves (of the selection, or all) back to where they were before any offset. Returns how many."""
    data = _offsets()
    if not data:
        raise RuntimeError("nothing was offset (or it was kept as the original).")
    mine = None
    if nodes:
        mine = set(A.time_curves(nodes))
    done = 0
    with A.Undo("gusAnimtoolOffsetBack"):
        for c, d in list(data.items()):
            if mine is not None and c not in mine:
                continue
            if cmds.objExists(c):
                cmds.keyframe(c, edit=True, relative=True, timeChange=-d, option="over")
                done += 1
            del data[c]
        _save_offsets(data)
    return done


def keep_as_original(nodes=None):
    """Forget the offsets (of the selection, or all): the current timing is the new original."""
    data = _offsets()
    if nodes:
        mine = set(A.time_curves(nodes))
        data = {c: v for c, v in data.items() if c not in mine}
    else:
        data = {}
    _save_offsets(data)
    return True


# ---------------------------------------------------------------------------
# bake / reduce
# ---------------------------------------------------------------------------

def _plugs(curves):
    out = []
    for c in curves:
        for p in cmds.listConnections(c + ".output", source=False, destination=True, plugs=True) or []:
            if p not in out:
                out.append(p)
    return out


def bake(step=None, scope=None, start=None, end=None):
    """A key every 'step' frames over the frame range on every animated channel (scope as inbetweens: selection,
    character, scene); keys outside the range stay. Returns how many channels."""
    step = max(1, int(step or A.opt("bake_step", 1)))
    curves = scope_curves(scope)
    if not curves:
        raise RuntimeError("no animation to bake.")
    if start is None:
        start, end = A.frame_range()
    plugs = _plugs(curves)
    with A.Undo("gusAnimtoolBake"):
        cmds.bakeResults(plugs, time=(start, end), sampleBy=step, preserveOutsideKeys=True, simulation=False,
                         minimizeRotation=True, disableImplicitControl=True, sparseAnimCurveBake=False)
    A.message("baked %d channel(s), a key every %d frame(s) over %g-%g." % (len(plugs), step, start, end))
    return len(plugs)


def _extremes(vals):
    """Indexes of the highs / lows (the curve turns there)."""
    out = set()
    for i in range(1, len(vals) - 1):
        a, b, c = vals[i - 1], vals[i], vals[i + 1]
        if (b - a) * (c - b) < 0:
            out.add(i)
    return out


def _evaluator(curve):
    """A fast f(time) for the curve: the API when there is one, else cmds."""
    try:
        import maya.api.OpenMaya as om
        import maya.api.OpenMayaAnim as oma
        sel = om.MSelectionList()
        sel.add(curve)
        fn = oma.MFnAnimCurve(sel.getDependNode(0))
        unit = om.MTime.uiUnit()
        f = lambda t: fn.evaluate(om.MTime(t, unit))           # noqa: E731
        if isinstance(f(0.0), float):
            return f
    except Exception:
        pass
    return lambda t: _eval(curve, t)


def reduce_curve(curve, tolerance):
    """Delete the keys whose removal changes the curve by less than tolerance (a share of its range) at any
    frame; the first, last, highs and lows always stay. Returns how many keys went."""
    times = cmds.keyframe(curve, query=True, timeChange=True) or []
    if len(times) < 3:
        return 0
    vals = cmds.keyframe(curve, query=True, valueChange=True) or []
    ev = _evaluator(curve)                                      # the API gives angles in radians: compare
    frames = [float(f) for f in range(int(math.floor(times[0])), int(math.ceil(times[-1])) + 1)]
    before = dict((f, ev(f)) for f in frames)                   # like with like, the range from it too
    limit = tolerance * ((max(before.values()) - min(before.values())) or 1.0)
    keep = {0, len(times) - 1} | _extremes(vals)
    alive = list(times)                                         # the keys left, kept here (no re-query)
    gone = 0
    for i in range(1, len(times) - 1):
        if i in keep:
            continue
        t = times[i]
        itt = (cmds.keyTangent(curve, query=True, time=(t, t), inTangentType=True) or ["auto"])[0]
        ott = (cmds.keyTangent(curve, query=True, time=(t, t), outTangentType=True) or ["auto"])[0]
        cmds.cutKey(curve, time=(t, t), clear=True)
        k = alive.index(t)
        left, right = alive[k - 1], alive[k + 1]
        worst = max([abs(ev(f) - before[f]) for f in frames if left <= f <= right] or [0.0])
        if worst > limit:                                   # it mattered: back it goes
            cmds.setKeyframe(curve, time=t, value=vals[i])
            try:
                cmds.keyTangent(curve, time=(t, t), inTangentType=itt, outTangentType=ott)
            except RuntimeError:
                pass
        else:
            alive.pop(k)
            gone += 1
    return gone


def _eval(curve, t):
    return float((cmds.keyframe(curve, query=True, eval=True, time=(t, t), valueChange=True) or [0.0])[0])


def reduce_keys(tolerance=None, scope=None):
    """Fewer keys, same motion: on every curve of the scope. tolerance: a share of each curve's range
    (0.01 = 1%). Returns (keys removed, keys before)."""
    tolerance = float(tolerance if tolerance is not None else A.opt("reduce_tolerance", 0.01))
    curves = scope_curves(scope)
    if not curves:
        raise RuntimeError("no animation to reduce.")
    before = sum(len(cmds.keyframe(c, query=True, timeChange=True) or []) for c in curves)
    gone = 0
    cmds.refresh(suspend=True)
    try:
        with A.Undo("gusAnimtoolReduce"):
            for c in curves:
                gone += reduce_curve(c, tolerance)
    finally:
        cmds.refresh(suspend=False)
    A.message("reduced: %d of %d key(s) removed (within %g%% of each curve's range)." % (gone, before,
                                                                                         tolerance * 100))
    return gone, before
