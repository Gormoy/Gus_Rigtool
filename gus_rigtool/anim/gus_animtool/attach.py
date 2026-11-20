"""
Attach (5.6.41): something follows something else - a prop follows a hand, or a hand follows a prop - from a
frame on, with no jump; it can change what holds it over time, be held by two things at once, be handed over
smoothly, be released, or baked.

    Select what FOLLOWS, then what it holds on to (last), Attach.
        a box and then the hand : the box follows the hand
        the IK hand and then the box : the hand follows the box
    Hand-over   : from one holder to another over a few frames (both carry it in between)
    Both hands  : held by two at once (50 / 50)
    Release     : from this frame it stays where it is
    Bake        : plain keys every frame of the range, the attach setup goes

The values live on the follower, as keyable channels in the Channel Box: Hold Free, and one Hold <holder> per
holder (0 = not held by it, 1 = fully). Key them like any channel (Graph Editor, tween tools). Its own
Translate / Rotate still work on top - you can still move it while it's held.

How: the follower's offsetParentMatrix comes from a blendMatrix. Target 0 is "free" (a hidden locator keyed with
the pose it was released in); each holder is a target = grip x holder's world x the follower's PARENT's world
inverse (5.6.40 used the follower's own parentInverseMatrix: Maya's evaluation saw a loop and the follower lagged
and stuttered). The grip is a hidden locator keyed (stepped) with the offset taken when that holder takes it, so
nothing jumps. The hold channels are normalised (they don't have to add up to 1). Hidden nodes live in
gusAttach_grp.
"""

import json
import re

import maya.cmds as cmds

from gus_animtool import anim as A

META = "gusAttach"
VERSION = 2
GROUP = "gusAttach_grp"
FREE = "free"
SEP = "attachHold"
IDENTITY = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]
HANDOVER_FRAMES = 4
SAFE = 0.001          # the divider's floor: Maya counts anything under 0.00001 as zero (5.6.43)


def _short(n):
    return A.short(n)


def _bare(n):
    return _short(n).split(":")[-1]


# --------------------------------------------------------------------------- stored data
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


def is_old(data):
    """An attach made before 5.6.41 (no hold channels)."""
    return bool(data) and data.get("version", 1) < VERSION


def _m(node, plug):
    return list(cmds.getAttr("%s.%s" % (node, plug)))


def _now():
    return cmds.currentTime(query=True)


def _parent(node):
    return (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]


def _parent_world(node):
    p = _parent(node)
    return A.world(p) if p else list(IDENTITY)


# --------------------------------------------------------------------------- loops
def _holders_of(node):
    d = read(node)
    if not d:
        return []
    if is_old(d):
        return [t["holder"] for t in d.get("targets", []) if t.get("holder")]
    return [h["node"] for h in d.get("holders", []) if h.get("node")]


def depends_on(holder, follower, _seen=None):
    """True when the holder moves with the follower (its child, or held by it, directly or further away) - attaching
    the follower to it would be a loop."""
    seen = _seen if _seen is not None else set()
    fl = A.long_name(follower) or follower
    node = A.long_name(holder) or holder
    while node:
        if node == fl or node.startswith(fl + "|"):
            return True
        if node in seen:
            return False
        seen.add(node)
        for h in _holders_of(node):
            if depends_on(h, follower, seen):
                return True
        node = _parent(node)
    return False


# --------------------------------------------------------------------------- the setup
def _group():
    got = cmds.ls(GROUP, long=True)
    if got:
        return got[0]
    g = cmds.ls(cmds.createNode("transform", name=GROUP), long=True)[0]
    try:
        cmds.setAttr(g + ".visibility", False)
    except RuntimeError:
        pass
    return g


def _channel(f, attr, nice=None):
    if not cmds.attributeQuery(attr, node=f, exists=True):
        kw = {"niceName": nice} if nice else {}
        cmds.addAttr(f, longName=attr, attributeType="double", minValue=0.0, maxValue=1.0, defaultValue=0.0,
                     keyable=True, **kw)
    return f + "." + attr


def _separator(f):
    if not cmds.attributeQuery(SEP, node=f, exists=True):
        cmds.addAttr(f, longName=SEP, niceName="____ Attach ____", attributeType="enum", enumName="hold:")
        try:
            cmds.setAttr(f + "." + SEP, channelBox=True)
            cmds.setAttr(f + "." + SEP, lock=True)
        except RuntimeError:
            pass


def _setup(f):
    """The blendMatrix on the follower (made once), with the free target. Returns data."""
    data = read(f)
    if data and is_old(data):
        raise RuntimeError("%s has an attach from before 5.6.41: Bake it (or Remove it), then Attach again - or "
                           "Repair to just stop its stutter." % _short(f))
    if data and cmds.objExists(data["blend"]):
        _fix_safe(data)
        return data
    src = cmds.listConnections(f + ".offsetParentMatrix", source=True, destination=False)
    if src:
        raise RuntimeError("%s's offset parent matrix is already driven (%s) - attach its parent group instead."
                           % (_short(f), src[0]))
    base = _m(f, "offsetParentMatrix")
    name = _bare(f)
    sub = cmds.ls(cmds.createNode("transform", name=name + "_attach", parent=_group()), long=True)[0]
    bm = cmds.createNode("blendMatrix", name=name + "_attach_blend")
    cmds.setAttr(bm + ".inputMatrix", base, type="matrix")
    free = cmds.ls(cmds.createNode("transform", name=name + "_attach_free", parent=sub), long=True)[0]
    _set_matrix(free, base)
    cmds.connectAttr(free + ".matrix", bm + ".target[0].targetMatrix")
    _separator(f)
    _channel(f, "hold_free", "Hold Free")
    data = {"version": VERSION, "blend": bm, "base": base, "group": sub, "norm": [],
            "holders": [{"name": FREE, "node": None, "attr": "hold_free", "grip": free, "mm": None}]}
    cmds.connectAttr(bm + ".outputMatrix", f + ".offsetParentMatrix")
    _wire(f, data)
    _write(f, data)
    return data


def _attr_for(f, data, holder):
    base = "hold_" + re.sub(r"[^A-Za-z0-9_]", "_", _bare(holder))
    attr, n = base, 2
    taken = [h["attr"] for h in data["holders"]]
    while attr in taken:
        attr, n = "%s%d" % (base, n), n + 1
    return attr


def _holder_index(f, data, holder):
    """The target of this holder (made the first time it holds the follower)."""
    if holder == FREE:
        return 0
    hl = A.long_name(holder) or holder
    for i, h in enumerate(data["holders"]):
        if h["node"] and (A.long_name(h["node"]) or h["node"]) == hl:
            return i
    i = len(data["holders"])
    name = _bare(f)
    grip = cmds.ls(cmds.createNode("transform", name="%s_attach_grip%d" % (name, i), parent=data["group"]),
                   long=True)[0]
    mm = cmds.createNode("multMatrix", name="%s_attach_%d" % (name, i))
    cmds.connectAttr(grip + ".matrix", mm + ".matrixIn[0]")
    cmds.connectAttr(hl + ".worldMatrix[0]", mm + ".matrixIn[1]")
    parent = _parent(f)
    if parent:       # the PARENT's inverse - not the follower's own parentInverseMatrix (a loop for Maya)
        cmds.connectAttr(parent + ".worldInverseMatrix[0]", mm + ".matrixIn[2]")
    cmds.connectAttr(mm + ".matrixSum", "%s.target[%d].targetMatrix" % (data["blend"], i))
    attr = _attr_for(f, data, hl)
    _channel(f, attr)
    data["holders"].append({"name": _short(hl), "node": hl, "attr": attr, "grip": grip, "mm": mm})
    _wire(f, data)
    _write(f, data)
    return i


def _wire(f, data):
    """The hold channels -> the blend's weights, normalised: weight i = hold i / (hold 0 + ... + hold i), so the
    result is the holds' average and they don't have to add up to 1 (all 0: its own parent)."""
    for n in data.get("norm", []):
        if cmds.objExists(n):
            cmds.delete(n)
    data["norm"] = []
    bm, name = data["blend"], _bare(f)
    for i, h in enumerate(data["holders"]):
        hold = "%s.%s" % (f, h["attr"])
        total = cmds.createNode("plusMinusAverage", name="%s_attach_sum%d" % (name, i))
        for j in range(i + 1):
            cmds.connectAttr("%s.%s" % (f, data["holders"][j]["attr"]), "%s.input1D[%d]" % (total, j))
        safe = cmds.createNode("clamp", name="%s_attach_safe%d" % (name, i))
        cmds.setAttr(safe + ".minR", SAFE)
        cmds.setAttr(safe + ".maxR", 1e9)
        cmds.connectAttr(total + ".output1D", safe + ".inputR")
        div = cmds.createNode("multiplyDivide", name="%s_attach_w%d" % (name, i))
        cmds.setAttr(div + ".operation", 2)
        cmds.connectAttr(hold, div + ".input1X")
        cmds.connectAttr(safe + ".outputR", div + ".input2X")
        cmds.connectAttr(div + ".outputX", "%s.target[%d].weight" % (bm, i), force=True)
        data["norm"] += [total, safe, div]


def _fix_safe(data):
    """5.6.41-42 attaches: the divider's floor was 0.000001 - Maya counts anything under 0.00001 as zero, so it
    warned 'divide by zero' on every frame where nothing holds it (and its weight there was 'unpredictable').
    Raised to SAFE. Returns how many were fixed."""
    fixed = 0
    for n in data.get("norm", []):
        try:
            if cmds.objExists(n) and cmds.nodeType(n) == "clamp" and cmds.getAttr(n + ".minR") < SAFE * 0.5:
                cmds.setAttr(n + ".minR", SAFE)
                fixed += 1
        except (RuntimeError, ValueError, TypeError):
            pass
    return fixed


def _set_matrix(node, m):
    t, r, s = A.decompose(m, cmds.getAttr(node + ".rotateOrder"))
    for attrs, vals in ((("tx", "ty", "tz"), t), (("rx", "ry", "rz"), r), (("sx", "sy", "sz"), s)):
        for a, v in zip(attrs, vals):
            cmds.setAttr("%s.%s" % (node, a), v)


def _key_matrix(node, m, frame):
    """A hidden locator keyed (stepped) with a matrix from this frame on."""
    _set_matrix(node, m)
    attrs = ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"]
    for a in attrs:
        cmds.setKeyframe(node + "." + a, time=frame)
    try:
        cmds.keyTangent(node, attribute=attrs, time=(frame, frame), outTangentType="step")
    except RuntimeError:
        pass


def _holds(f, data, frame):
    """{target index: hold value} at a frame."""
    out = {}
    for i, h in enumerate(data["holders"]):
        try:
            out[i] = float(cmds.getAttr("%s.%s" % (f, h["attr"]), time=frame))
        except (RuntimeError, ValueError, TypeError):
            out[i] = 0.0
    return out


def _hold_until(f, data, before, frame):
    """What held it before keeps holding it up to this frame: the last key before it made stepped (no slide into
    the change); a channel with no key before gets a 0 one frame earlier (before its first change it's not held -
    not the value of a later key, which Maya would hold backwards)."""
    for i, h in enumerate(data["holders"]):
        plug = "%s.%s" % (f, h["attr"])
        prev = [t for t in (cmds.keyframe(plug, query=True, timeChange=True) or []) if t < frame - 1e-6]
        if prev:
            try:
                cmds.keyTangent(plug, time=(prev[-1], prev[-1]), outTangentType="step")
            except RuntimeError:
                pass
        else:
            cmds.setKeyframe(plug, time=frame - 1, value=0.0)      # before its first change: not held
            try:
                cmds.keyTangent(plug, time=(frame - 1, frame - 1), outTangentType="step")
            except RuntimeError:
                pass


def _key_holds(f, data, values, frame, tangent):
    for i, h in enumerate(data["holders"]):
        plug = "%s.%s" % (f, h["attr"])
        cmds.setKeyframe(plug, time=frame, value=values.get(i, 0.0))
        try:
            if tangent == "step":
                cmds.keyTangent(plug, time=(frame, frame), outTangentType="step")
            else:
                cmds.keyTangent(plug, time=(frame, frame), inTangentType="flat", outTangentType="flat")
        except RuntimeError:
            pass


# --------------------------------------------------------------------------- the one action under all others
def set_hold(follower, weights, frame=None, over=0):
    """From frame on, the follower is held by these {holder (or FREE): amount}; the others let go. over = 0: at
    once (no jump); over > 0: a hand-over across that many frames (both carry it in between). Returns data."""
    frame = _now() if frame is None else float(frame)
    now = _now()
    for h in weights:
        if h != FREE:
            if (A.long_name(h) or h) == (A.long_name(follower) or follower):
                raise RuntimeError("it can't hold on to itself.")
            if depends_on(h, follower):
                raise RuntimeError("%s moves with %s (it's under it, or attached to it - even if released, its "
                                   "setup still listens to it) - holding on to it would be a loop. Bake %s first "
                                   "(right-click Release > Bake), then attach." % (_short(h), _short(follower),
                                                                                  _short(h)))
    with A.Undo("gusAnimtoolAttach"):
        data = _setup(follower)
        new = {_holder_index(follower, data, h): float(w) for h, w in weights.items()}
        try:
            cmds.currentTime(frame, update=True)
            before = _holds(follower, data, frame - 1)
            at = _holds(follower, data, frame)
            opm = _m(follower, "offsetParentMatrix")
            pw = _parent_world(follower)
            for i, w in new.items():
                if w <= 0:
                    continue
                if over and at.get(i, 0.0) > 0:
                    continue                      # already carrying it during a hand-over: keep its grip
                h = data["holders"][i]
                if i == 0:
                    _key_matrix(h["grip"], opm, frame)
                else:
                    grip = A.mul(A.mul(opm, pw), A.inverse(A.world(h["node"])))
                    _key_matrix(h["grip"], grip, frame)
            values = {i: new.get(i, 0.0) for i in range(len(data["holders"]))}
            if over:
                _key_holds(follower, data, at, frame, "flat")
                _key_holds(follower, data, values, frame + over, "flat")
            else:
                _hold_until(follower, data, before, frame)
                _key_holds(follower, data, values, frame, "step")
        finally:
            cmds.currentTime(now, update=True)
        _bookmarks(follower)
    return data


# --------------------------------------------------------------------------- the actions
def _pair(follower, holder):
    if follower is None or holder is None:
        sel = A.selected()
        if len(sel) != 2:
            raise RuntimeError("select what follows, then what it holds on to (2 things).")
        follower, holder = sel
    return follower, holder


def attach(follower=None, holder=None, frame=None):
    """From frame (now) on, follower follows holder, with no jump."""
    follower, holder = _pair(follower, holder)
    frame = _now() if frame is None else frame
    set_hold(follower, {holder: 1.0}, frame)
    A.message("%s follows %s from frame %g (you can still move it: its own channels work on top)."
              % (_short(follower), _short(holder), frame))
    return follower


def hand_over(follower=None, holder=None, frames=HANDOVER_FRAMES, frame=None):
    """From frame (now), over a few frames, from what holds it now to holder (both carry it in between)."""
    follower, holder = _pair(follower, holder)
    if not read(follower):
        raise RuntimeError("%s isn't held by anything yet - Attach it first." % _short(follower))
    frame = _now() if frame is None else frame
    set_hold(follower, {holder: 1.0}, frame, over=int(frames))
    A.message("%s goes to %s over %d frames, from frame %g." % (_short(follower), _short(holder), frames, frame))
    return follower


def both(follower=None, holder=None, frame=None):
    """Held by what holds it now AND holder, 50 / 50, from frame (now) on."""
    follower, holder = _pair(follower, holder)
    data = read(follower)
    frame = _now() if frame is None else frame
    if not data or is_old(data):
        raise RuntimeError("%s isn't held by anything yet - Attach it to the first one first." % _short(follower))
    holds = _holds(follower, data, frame)
    cur = [data["holders"][i]["node"] for i, w in holds.items() if w > 0 and i > 0]
    if not cur:
        raise RuntimeError("nothing holds %s at this frame - Attach it to the first one first." % _short(follower))
    weights = {cur[0]: 0.5, holder: 0.5}
    set_hold(follower, weights, frame)
    A.message("%s held by %s and %s (50 / 50) from frame %g." % (_short(follower), _short(cur[0]), _short(holder),
                                                                  frame))
    return follower


def release(follower=None, frame=None):
    """From frame (now) on, the follower stays where it is."""
    follower = follower or (A.selected() or [None])[0]
    data = read(follower) if follower else None
    if not data:
        raise RuntimeError("select something attached.")
    if is_old(data):
        raise RuntimeError("%s has an attach from before 5.6.41: Bake it (or Remove it), then Attach again."
                           % _short(follower))
    frame = _now() if frame is None else frame
    set_hold(follower, {FREE: 1.0}, frame)
    A.message("%s released at frame %g (it stays where it is)." % (_short(follower), frame))
    return follower


# --------------------------------------------------------------------------- over time
def _key_times(f, data):
    times = set()
    for h in data["holders"]:
        times.update(cmds.keyframe("%s.%s" % (f, h["attr"]), query=True, timeChange=True) or [])
    return sorted(times)


def _label(data, holds):
    on = [(i, w) for i, w in sorted(holds.items()) if w > 1e-4]
    if not on:
        return "its own parent"
    total = sum(w for _i, w in on)
    names = ["stays where it is" if i == 0 else _short(data["holders"][i]["name"]) for i, _w in on]
    if len(on) == 1:
        return names[0]
    return " + ".join("%s %d%%" % (n, round(100 * w / total)) for n, (_i, w) in zip(names, on))


def timeline(follower):
    """[{start, end, label, holds {index: amount}, handover (bool), main (index or None)}] - who holds it from when
    to when (end None = to the end)."""
    data = read(follower)
    if not data or is_old(data):
        return []
    times = _key_times(follower, data)
    out = []
    for k, t in enumerate(times):
        nxt = times[k + 1] if k + 1 < len(times) else None
        holds = _holds(follower, data, t)
        moving = nxt is not None and holds != _holds(follower, data, nxt - 1e-3) and nxt - t > 1.0 + 1e-6
        if out and not moving and not out[-1]["handover"] and out[-1]["holds"] == holds:
            out[-1]["end"] = nxt
            continue
        main = max(holds, key=holds.get) if any(w > 1e-4 for w in holds.values()) else None
        label = _label(data, holds)
        if moving:
            label = "hand-over to " + _label(data, _holds(follower, data, nxt))
        out.append({"start": t, "end": nxt, "label": label, "holds": holds, "handover": moving, "main": main})
    return out


def events(follower):
    """[(frame, what holds it from there)] in time order (the changes; the first 'own parent' stretch left out)."""
    data = read(follower)
    if data and is_old(data):
        return [tuple(e) for e in data.get("events", [])]
    out = []
    for seg in timeline(follower):
        if not out and seg["label"] == "its own parent":
            continue
        out.append((seg["start"], seg["label"]))
    return out


def next_change(follower, frame=None, backwards=False):
    frame = _now() if frame is None else frame
    times = [t for t, _l in events(follower)]
    if backwards:
        before = [t for t in times if t < frame - 1e-6]
        return before[-1] if before else None
    after = [t for t in times if t > frame + 1e-6]
    return after[0] if after else None


def go_change(backwards=False):
    """The time to the selection's next (or previous) attach change."""
    nodes = [n for n in A.selected() if read(n)] or attached()
    if not nodes:
        raise RuntimeError("nothing is attached.")
    found = [t for t in (next_change(n, backwards=backwards) for n in nodes) if t is not None]
    if not found:
        raise RuntimeError("no %s change." % ("earlier" if backwards else "later"))
    t = max(found) if backwards else min(found)
    cmds.currentTime(t)
    return t


def describe(follower):
    lines = []
    segs = timeline(follower)
    for seg in segs:
        end = "end" if seg["end"] is None else "%g" % (seg["end"] - 1)
        lines.append("  %g-%s: %s" % (seg["start"], end, seg["label"]))
    if not segs:
        lines = ["  %g: %s" % e for e in events(follower)]
    return "%s\n%s" % (_short(follower), "\n".join(lines))


def delete_change(follower, frame):
    """Take one change away (its keys); the other frames keep what they had."""
    data = read(follower)
    if not data or is_old(data):
        raise RuntimeError("select something attached (made with 5.6.41 or later).")
    seg = next((s for s in timeline(follower) if abs(s["start"] - frame) < 1e-6), None)
    frames = [frame] + ([seg["end"]] if seg and seg["handover"] and seg["end"] is not None else [])
    with A.Undo("gusAnimtoolAttachDelete"):
        for h in data["holders"]:                     # the key one frame before a first change goes with it
            plug = "%s.%s" % (follower, h["attr"])
            times = cmds.keyframe(plug, query=True, timeChange=True) or []
            if (frame - 1) in times and not [t for t in times if t < frame - 1 - 1e-6]:
                try:
                    cmds.cutKey(plug, time=(frame - 1, frame - 1), clear=True)
                except RuntimeError:
                    pass
        for t in frames:
            for h in data["holders"]:
                for plug in ["%s.%s" % (follower, h["attr"])] + ["%s.%s" % (h["grip"], a) for a in
                                                               ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz")]:
                    try:
                        cmds.cutKey(plug, time=(t, t), clear=True)
                    except RuntimeError:
                        pass
        _bookmarks(follower)
    return len(frames)


def move_change(follower, frame, new_frame):
    """A change moved to another frame (taken again there: no jump)."""
    seg = next((s for s in timeline(follower) if abs(s["start"] - frame) < 1e-6), None)
    if not seg:
        raise RuntimeError("no change at frame %g." % frame)
    data = read(follower)
    target = seg["holds"]
    over = 0
    if seg["handover"] and seg["end"] is not None:
        target = _holds(follower, data, seg["end"])
        over = int(round(seg["end"] - seg["start"]))
    weights = {}
    for i, w in target.items():
        if w > 1e-4:
            weights[FREE if i == 0 else data["holders"][i]["node"]] = w
    with A.Undo("gusAnimtoolAttachMove"):
        delete_change(follower, frame)
        if weights:
            set_hold(follower, weights, new_frame, over=over)
    return new_frame


def attached():
    return cmds.ls("*." + META, objectsOnly=True, long=True, recursive=True) or []


# --------------------------------------------------------------------------- repair / bake / remove
def repair(follower=None):
    """5.6.40's attaches: the follower's own parentInverseMatrix taken out of its setup (Maya saw a loop: the
    follower lagged and stuttered) - the parent's inverse instead, the same value. 5.6.41-42's: the divide-by-zero
    floor raised (_fix_safe). Returns how many were fixed."""
    nodes = [follower] if follower else attached()
    fixed = 0
    for f in nodes:
        data = read(f)
        if not data:
            continue
        mms = [t.get("node") for t in data.get("targets", [])] if is_old(data) else \
            [h.get("mm") for h in data.get("holders", [])]
        if not is_old(data):
            fixed += _fix_safe(data)
        parent = _parent(f)
        for mm in [m for m in mms if m and cmds.objExists(m)]:
            src = cmds.listConnections(mm + ".matrixIn[2]", source=True, destination=False, plugs=True) or []
            if src and src[0].split(".")[-1].startswith("parentInverseMatrix"):
                cmds.disconnectAttr(src[0], mm + ".matrixIn[2]")
                if parent:
                    cmds.connectAttr(parent + ".worldInverseMatrix[0]", mm + ".matrixIn[2]")
                else:
                    cmds.setAttr(mm + ".matrixIn[2]", IDENTITY, type="matrix")
                fixed += 1
    return fixed


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


def bake_all(start=None, end=None):
    """5.6.46: finish a shot - every attach in the scene baked to plain keys over the range (the motion kept, the
    setups gone), one undo. Returns [(follower, frames)]."""
    nodes = [n for n in attached() if read(n)]
    if not nodes:
        raise RuntimeError("nothing is attached in this scene.")
    if start is None:
        start, end = A.frame_range()
    done = []
    with A.Undo("gusAnimtoolAttachBakeAll"):
        for n in nodes:                     # any order: each one keeps its world motion, so what holds on to
            if read(n):                     # it (or what it holds) moves the same afterwards
                done.append((n, bake(n, start, end)))
    return done


def remove(follower):
    """The attach setup off (no baking): the follower goes back to its own parent."""
    data = read(follower)
    if not data:
        return False
    nodes = [data.get("blend")] + list(data.get("norm", []))
    if is_old(data):
        nodes += [t.get("node") for t in data.get("targets", [])]
    else:
        nodes += [h.get("mm") for h in data.get("holders", [])] + [data.get("group")]
    for n in nodes:
        if n and cmds.objExists(n):
            cmds.delete(n)
    try:
        cmds.setAttr(follower + ".offsetParentMatrix", data.get("base") or IDENTITY, type="matrix")
    except RuntimeError:
        pass
    if not is_old(data):
        for h in data.get("holders", []):
            if cmds.attributeQuery(h["attr"], node=follower, exists=True):
                cmds.deleteAttr(follower + "." + h["attr"])
        if cmds.attributeQuery(SEP, node=follower, exists=True):
            try:
                cmds.setAttr(follower + "." + SEP, lock=False)
            except RuntimeError:
                pass
            cmds.deleteAttr(follower + "." + SEP)
    cmds.deleteAttr(follower + "." + META)
    _bookmarks(follower, clear=True)
    return True


# ---------------------------------------------------------------------------
# the Time Slider (bookmarks)
# ---------------------------------------------------------------------------

COLORS = [(0.25, 0.55, 0.95), (0.95, 0.45, 0.25), (0.4, 0.8, 0.4), (0.85, 0.35, 0.75), (0.9, 0.8, 0.3)]


def colour(index):
    return COLORS[(index - 1) % len(COLORS)] if index else (0.45, 0.45, 0.45)


def _bookmark_plugin():
    """Maya's Time Slider bookmarks are a plugin - loaded first (5.6.40 didn't: no bookmarks showed)."""
    try:
        if not cmds.pluginInfo("timeSliderBookmark", query=True, loaded=True):
            cmds.loadPlugin("timeSliderBookmark", quiet=True)
        import maya.plugin.timeSliderBookmark.timeSliderBookmark as tsb
        return tsb
    except Exception:
        return None


def _bookmarks(follower, clear=False):
    """One coloured Time Slider bookmark per stretch the follower is held (named after what holds it)."""
    tsb = _bookmark_plugin()
    if tsb is None:
        return False
    tag = "gusAttach_" + _bare(follower)
    try:
        for b in cmds.ls(type="timeSliderBookmark") or []:
            if (cmds.getAttr(b + ".name") or "").startswith(tag):
                cmds.delete(b)
        if clear:
            return True
        end = int(cmds.playbackOptions(query=True, maxTime=True))
        for seg in timeline(follower):
            if seg["main"] in (None, 0) and not seg["handover"]:
                continue                                    # free / its own parent: no stretch
            stop = int(seg["end"] - 1) if seg["end"] is not None else end
            if stop < seg["start"]:
                continue
            tsb.createBookmark(name="%s: %s on %s" % (tag, _bare(follower), seg["label"]), start=seg["start"],
                               stop=stop, color=colour(seg["main"] or 1))
        return True
    except Exception:
        return False
