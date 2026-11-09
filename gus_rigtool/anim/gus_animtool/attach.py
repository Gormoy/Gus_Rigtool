"""
Attach props (like ZV Parent Master): something follows something else from a frame on, with no jump - and can
change what it follows over time (hand, table, other hand), or be released.

    Select what FOLLOWS, then what it holds on to (last), Attach.
        a box and then the hand : the box follows the hand
        the IK hand and then the box : the hand follows the box (more control on the box)
    Release : from this frame it stays where it is (follows its own parent again).
    Change the grip : Release at the frame, move the hand, Attach again at the same frame.
    Bake : the follower gets plain keys every frame of the range, the attach setup goes.

How: the follower's offsetParentMatrix comes from a blendMatrix; each thing it held on to is a target
(offset x target's world x follower's parent inverse) whose weight is keyed (stepped) on / off. Its own keys keep
working on top - you can still animate the box while it's in the hand. Fingers never move it (it follows the
control you picked).
"""

import json

import maya.cmds as cmds

from gus_animtool import anim as A

META = "gusAttach"
IDENTITY = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]


def _short(n):
    return A.short(n)


def read(node):
    try:
        if cmds.attributeQuery(META, node=node, exists=True):
            return json.loads(cmds.getAttr(node + "." + META) or "{}") or None
    except (RuntimeError, ValueError):
        pass
    return None


def _write(node, data):
    if not cmds.attributeQuery(META, node=node, exists=True):
        cmds.addAttr(node, longName=META, dataType="string")
    cmds.setAttr(node + "." + META, json.dumps(data), type="string")


def _m(node, plug):
    return list(cmds.getAttr("%s.%s" % (node, plug)))


def _now():
    return cmds.currentTime(query=True)


def _setup(f):
    """The blendMatrix on the follower's offsetParentMatrix (made once). Returns (data, blend)."""
    data = read(f)
    if data and cmds.objExists(data["blend"]):
        return data, data["blend"]
    src = cmds.listConnections(f + ".offsetParentMatrix", source=True, destination=False)
    if src:
        raise RuntimeError("%s's offset parent matrix is already driven (%s) - attach its parent group instead."
                           % (_short(f), src[0]))
    base = _m(f, "offsetParentMatrix")
    bm = cmds.createNode("blendMatrix", name=_short(f).split(":")[-1] + "_attach_blend")
    cmds.setAttr(bm + ".inputMatrix", base, type="matrix")
    cmds.connectAttr(bm + ".outputMatrix", f + ".offsetParentMatrix")
    data = {"blend": bm, "base": base, "targets": [], "events": []}
    _write(f, data)
    return data, bm


def _key_weights(bm, count, active, frame):
    """At frame: the active target's weight 1, the others 0 (stepped keys)."""
    for i in range(count):
        plug = "%s.target[%d].weight" % (bm, i)
        cmds.setKeyframe(plug, time=frame, value=1.0 if i == active else 0.0)
        try:
            cmds.keyTangent(plug, time=(frame, frame), outTangentType="step")
        except RuntimeError:
            pass


def _current_opm(f):
    return _m(f, "offsetParentMatrix")


def _new_target(f, data, bm, holder, frame):
    """A new target: holder (or None = stay where it is) with the offset that keeps the follower still now."""
    i = len(data["targets"])
    opm = _current_opm(f)
    if holder:
        p = _m(f, "parentMatrix[0]")
        offset = A.mul(A.mul(opm, p), A.inverse(_m(holder, "worldMatrix[0]")))
        mm = cmds.createNode("multMatrix", name="%s_attach_%d" % (_short(f).split(":")[-1], i))
        cmds.setAttr(mm + ".matrixIn[0]", offset, type="matrix")
        cmds.connectAttr(holder + ".worldMatrix[0]", mm + ".matrixIn[1]")
        cmds.connectAttr(f + ".parentInverseMatrix[0]", mm + ".matrixIn[2]")
        cmds.connectAttr(mm + ".matrixSum", "%s.target[%d].targetMatrix" % (bm, i))
        data["targets"].append({"holder": _short(holder), "node": mm})
    else:
        cmds.setAttr("%s.target[%d].targetMatrix" % (bm, i), opm, type="matrix")
        data["targets"].append({"holder": None, "node": None})
    plug = "%s.target[%d].weight" % (bm, i)
    cmds.setKeyframe(plug, time=frame - 1, value=0.0)               # off until now
    try:
        cmds.keyTangent(plug, time=(frame - 1, frame - 1), outTangentType="step")
    except RuntimeError:
        pass
    return i


def _record(f, data, frame, label):
    data["events"] = [e for e in data["events"] if abs(e[0] - frame) > 1e-6] + [[frame, label]]
    data["events"].sort()
    _write(f, data)
    _bookmarks(f, data)


def attach(follower=None, holder=None, frame=None):
    """From frame (now) on, follower follows holder with no jump. Returns the target index."""
    if follower is None or holder is None:
        sel = A.selected()
        if len(sel) != 2:
            raise RuntimeError("select what follows, then what it holds on to (2 things).")
        follower, holder = sel
    frame = _now() if frame is None else frame
    if A.long_name(follower) == A.long_name(holder):
        raise RuntimeError("it can't hold on to itself.")
    with A.Undo("gusAnimtoolAttach"):
        data, bm = _setup(follower)
        i = _new_target(follower, data, bm, holder, frame)
        _key_weights(bm, len(data["targets"]), i, frame)
        _record(follower, data, frame, _short(holder))
    A.message("%s follows %s from frame %g." % (_short(follower), _short(holder), frame))
    return i


def release(follower=None, frame=None):
    """From frame (now) on, the follower stays where it is (back with its own parent)."""
    follower = follower or (A.selected() or [None])[0]
    if not follower or not read(follower):
        raise RuntimeError("select something attached.")
    frame = _now() if frame is None else frame
    with A.Undo("gusAnimtoolRelease"):
        data, bm = _setup(follower)
        i = _new_target(follower, data, bm, None, frame)
        _key_weights(bm, len(data["targets"]), i, frame)
        _record(follower, data, frame, "released")
    A.message("%s released at frame %g (it stays where it is)." % (_short(follower), frame))
    return i


def events(follower):
    """[(frame, 'holder name' or 'released')] in time order."""
    d = read(follower)
    return [tuple(e) for e in d["events"]] if d else []


def attached():
    return cmds.ls("*." + META, objectsOnly=True, long=True, recursive=True) or []


def bake(follower=None, start=None, end=None):
    """Plain keys every frame of the range (the motion kept), and the attach setup goes."""
    follower = follower or (A.selected() or [None])[0]
    data = read(follower) if follower else None
    if not data:
        raise RuntimeError("select something attached.")
    if start is None:
        start, end = A.frame_range()
    now = _now()
    worlds = []
    with A.Undo("gusAnimtoolAttachBake"):
        try:
            for f in range(int(start), int(end) + 1):
                cmds.currentTime(f, update=True)
                worlds.append((f, list(cmds.getAttr(follower + ".worldMatrix[0]"))))
            remove(follower)
            for f, m in worlds:
                cmds.currentTime(f, update=True)
                A.set_world(follower, m)
                cmds.setKeyframe(follower, attribute=A._T + A._R, time=f)
            curves = [c for c in A.time_curves(follower) if A.is_rotation(c)]
            if curves:
                try:
                    cmds.filterCurve(curves, filter="euler")
                except RuntimeError:
                    pass
        finally:
            cmds.currentTime(now, update=True)
    A.message("%s baked, frames %d-%d." % (_short(follower), start, end))
    return len(worlds)


def remove(follower):
    """The attach setup off (no baking): the follower goes back to its own parent."""
    data = read(follower)
    if not data:
        return False
    for t in data["targets"]:
        if t.get("node") and cmds.objExists(t["node"]):
            cmds.delete(t["node"])
    if cmds.objExists(data["blend"]):
        cmds.delete(data["blend"])
    try:
        cmds.setAttr(follower + ".offsetParentMatrix", data.get("base") or IDENTITY, type="matrix")
    except RuntimeError:
        pass
    cmds.deleteAttr(follower + "." + META)
    _bookmarks(follower, None)
    return True


# ---------------------------------------------------------------------------
# the Time Slider (bookmarks, when this Maya has them)
# ---------------------------------------------------------------------------

COLORS = [(0.25, 0.55, 0.95), (0.95, 0.6, 0.2), (0.4, 0.8, 0.4), (0.85, 0.35, 0.75)]


def _bookmarks(follower, data):
    """One coloured Time Slider bookmark per attached stretch (Maya 2020+); silently skipped otherwise."""
    try:
        import maya.plugin.timeSliderBookmark.timeSliderBookmark as tsb
    except Exception:
        return False
    tag = "gusAttach_" + _short(follower).split(":")[-1]
    try:
        for b in cmds.ls(type="timeSliderBookmark") or []:
            if cmds.getAttr(b + ".name").startswith(tag):
                cmds.delete(b)
        if not data:
            return True
        end = int(cmds.playbackOptions(query=True, maxTime=True))
        ev = data["events"]
        for k, (frame, label) in enumerate(ev):
            stop = ev[k + 1][0] - 1 if k + 1 < len(ev) else end
            if label == "released" or stop < frame:
                continue
            tsb.createBookmark(name="%s: %s on %s" % (tag, _short(follower).split(":")[-1], label), start=frame,
                               stop=stop, color=COLORS[k % len(COLORS)])
        return True
    except Exception:
        return False
