"""
Walk / run cycles: find the cycle from your keys, mirror its first half, continue it.

    Animate the first half (contact to the other side's contact, e.g. 1-13), then:
      Mirror cycle    -> the second half (13-25) is the first one mirrored; 25 = frame 1 (loop frame).
      Continue cycle  -> the cycle repeats N more times, as keys; controls that travel (the root / COG going
                         forward) keep going forward instead of jumping back.

Which frames: a range highlighted in the Time Slider (shift-drag) wins; otherwise your keys say it.
"""

import maya.cmds as cmds

from gus_animtool import anim as A

INFO = "gusAnimtoolCycle"          # fileInfo: 'start half' of the last mirrored cycle (re-running doesn't double it)
TRAVEL = ("translateX", "translateY", "translateZ")


def _highlight():
    from gus_animtool import keys as K
    return K.slider_range()


def _keys(nodes):
    return sorted(set(float(k) for k in (cmds.keyframe(nodes, query=True, timeChange=True) or [])))


def _remembered():
    try:
        got = cmds.fileInfo(INFO, query=True)
        start, half = [float(x) for x in got[0].split()]
        return start, half
    except (RuntimeError, TypeError, ValueError, IndexError):
        return None


def _remember(start, half):
    try:
        cmds.fileInfo(INFO, "%g %g" % (start, half))
    except (RuntimeError, TypeError):
        pass


def half_range(nodes):
    """(start, half length): the first half you animated - highlighted range, else your keys."""
    hl = _highlight()
    if hl and hl[1] - hl[0] >= 1:
        return hl[0], hl[1] - hl[0]
    keys = _keys(nodes)
    if len(keys) < 2:
        raise RuntimeError("key the first half of the cycle (e.g. 1 = left contact, 13 = right contact), "
                           "or highlight it in the Time Slider (shift-drag).")
    start, last = keys[0], keys[-1]
    mem = _remembered()
    if mem and abs(mem[0] - start) < 1e-3 and abs(start + 2 * mem[1] - last) < 1e-3:
        return mem                                    # already mirrored once: same half again, not double
    return start, last - start


def cycle_range(nodes):
    """(start, end) of the whole cycle, loop frame included - highlighted range, else the keys."""
    hl = _highlight()
    if hl and hl[1] - hl[0] >= 1:
        return hl
    keys = _keys(nodes)
    if len(keys) < 2:
        raise RuntimeError("no cycle found: key it (or highlight it in the Time Slider).")
    return keys[0], keys[-1]


def show_range(start, end):
    """The Time Slider (and the window's range) on the cycle: start to the frame before the loop frame."""
    try:
        cmds.playbackOptions(minTime=start, maxTime=end - 1, animationStartTime=min(
            start, cmds.playbackOptions(query=True, animationStartTime=True)), animationEndTime=max(
            end, cmds.playbackOptions(query=True, animationEndTime=True)))
    except (RuntimeError, TypeError):
        pass
    for field, v in (("Start", start), ("End", end)):
        try:
            if cmds.intField(A.P + field, exists=True):
                cmds.intField(A.P + field, edit=True, value=int(v))
        except (RuntimeError, TypeError):
            pass


def mirror(nodes=None, loop=None):
    """Mirror cycle: the half found from the keys (or the highlighted range), the Time Slider set to the cycle."""
    sel = nodes or A._pose_sel()
    start, half = half_range(sel)
    end = start + 2 * half
    n = A.mirror_half_cycle(sel, start, end, loop)
    _remember(start, half)
    show_range(start, end)
    return n


# ---------------------------------------------------------------------------
# continue
# ---------------------------------------------------------------------------

def _scope(nodes):
    if nodes:
        return nodes
    sel = A._pose_sel()
    if int(A.opt("cycle_scope", 1)) == 1:                 # the whole character (a walk is every control)
        every = A.character_controls(A.namespace_of(sel[0]))
        return every or sel
    return sel


def _curves(nodes):
    return A.time_curves(nodes)


def _attr(curve):
    plugs = cmds.listConnections(curve + ".output", source=False, destination=True, plugs=True) or []
    return plugs[0].split(".")[-1] if plugs else ""


def _value(curve, t):
    got = cmds.keyframe(curve, query=True, eval=True, time=(t, t), valueChange=True) or [0.0]
    return float(got[0])


def travel(curve, start, end):
    """How far a translate curve goes in one cycle (0 for the rest)."""
    if _attr(curve) not in TRAVEL:
        return 0.0
    d = _value(curve, end) - _value(curve, start)
    return d if abs(d) > 1e-4 else 0.0


def continue_cycle(times=None, nodes=None, forward=None):
    """The cycle repeats 'times' more times, as keys. forward: controls that travel keep going (root / COG)."""
    times = int(A.opt("cycle_times", 3)) if times is None else int(times)
    forward = bool(A.opt("cycle_forward", 1)) if forward is None else forward
    if times < 1:
        raise RuntimeError("repeat at least once.")
    nodes = _scope(nodes)
    start, end = cycle_range(nodes)
    length = end - start
    if length < 2:
        raise RuntimeError("the cycle is too short: key it, or highlight it in the Time Slider.")
    curves = _curves(nodes)
    if not curves:
        raise RuntimeError("no animation on these controls.")
    last = end + times * length
    after = max(_keys(nodes) + [last])                     # keys after the cycle (an earlier Continue) are replaced
    moved = 0
    with A.Undo("gusAnimContinueCycle"):
        for c in curves:
            d = travel(c, start, end) if forward else 0.0
            try:
                cmds.cutKey(c, time=(end + 1e-3, after), clear=True)
                cmds.copyKey(c, time=(start, end))
            except RuntimeError:
                continue
            for i in range(1, times + 1):
                at = start + i * length
                cmds.pasteKey(c, time=(at, at), option="merge")
                if d:
                    cmds.keyframe(c, edit=True, relative=True, valueChange=i * d, time=(at, at + length))
            if d:
                moved += 1
                cmds.setInfinity(c, postInfinite="cycleRelative", preInfinite="cycleRelative")
        show_range(start, last)
    A.message("cycle %g-%g repeated %d more time(s): now %g-%g, %d curve(s)%s." % (
        start, end, times, start, last, len(curves), ", %d moving forward" % moved if moved else ""))
    return len(curves)


def continue_with_curves(nodes=None):
    """No new keys: the curves repeat after the cycle; travelling ones keep going (cycle with offset)."""
    nodes = _scope(nodes)
    start, end = cycle_range(nodes)
    curves = _curves(nodes)
    if not curves:
        raise RuntimeError("no animation on these controls.")
    moved = 0
    with A.Undo("gusAnimCycleCurves"):
        for c in curves:
            kind = "cycleRelative" if travel(c, start, end) else "cycle"
            moved += kind == "cycleRelative"
            cmds.setInfinity(c, postInfinite=kind, preInfinite=kind)
    A.message("%d curve(s) loop after the cycle%s - no new keys (Graph Editor > View > Infinity to see them)."
              % (len(curves), ", %d moving forward" % moved if moved else ""))
    return len(curves)


# ---------------------------------------------------------------------------
# in place <-> moving forward
# ---------------------------------------------------------------------------

TRAVEL_NODE = "gusAnimtool_cycleTravel"           # {curve: [start, length, distance]} - for the way back


def _travel_data():
    import json
    if not cmds.objExists(TRAVEL_NODE) or not cmds.attributeQuery("data", node=TRAVEL_NODE, exists=True):
        return {}
    try:
        return json.loads(cmds.getAttr(TRAVEL_NODE + ".data") or "{}")
    except ValueError:
        return {}


def _save_travel(data):
    import json
    if not cmds.objExists(TRAVEL_NODE):
        cmds.createNode("network", name=TRAVEL_NODE)
    if not cmds.attributeQuery("data", node=TRAVEL_NODE, exists=True):
        cmds.addAttr(TRAVEL_NODE, longName="data", dataType="string")
    cmds.setAttr(TRAVEL_NODE + ".data", json.dumps(data), type="string")


def _ramp(curve, start, length, distance, sign):
    """Every key's value +/- distance x (time - start) / length: the steady travel taken out / put back."""
    times = cmds.keyframe(curve, query=True, timeChange=True) or []
    for t in times:
        cmds.keyframe(curve, edit=True, time=(t, t), relative=True,
                      valueChange=sign * distance * (t - start) / float(length))


def in_place(nodes=None):
    """The walk loops on the spot: controls that travel in the cycle (root / COG translate) lose the steady
    forward motion (their bounce and sway stay). Remembered, so Forward puts it back exactly."""
    nodes = _scope(nodes)
    start, end = cycle_range(nodes)
    length = end - start
    if length < 2:
        raise RuntimeError("no cycle found: key it, or highlight it in the Time Slider.")
    data = _travel_data()
    done = 0
    with A.Undo("gusAnimCycleInPlace"):
        for c in _curves(nodes):
            d = travel(c, start, end)
            if not d or c in data:
                continue
            _ramp(c, start, length, d, -1)
            data[c] = [start, length, d]
            cmds.setInfinity(c, preInfinite="cycle", postInfinite="cycle")
            done += 1
        _save_travel(data)
    if not done:
        raise RuntimeError("nothing travels in this cycle (already in place?).")
    A.message("cycle in place: %d curve(s) lost their forward travel (Forward puts it back)." % done)
    return done


def forward(nodes=None):
    """Put back the travel taken out by In place (the same distance per cycle)."""
    data = _travel_data()
    if not data:
        raise RuntimeError("nothing was put in place (In place first).")
    mine = set(_curves(_scope(nodes))) if nodes or A.selected() else None
    done = 0
    with A.Undo("gusAnimCycleForward"):
        for c, (start, length, d) in list(data.items()):
            if mine is not None and c not in mine:
                continue
            if cmds.objExists(c):
                _ramp(c, start, length, d, 1)
                cmds.setInfinity(c, preInfinite="cycleRelative", postInfinite="cycleRelative")
                done += 1
            del data[c]
        _save_travel(data)
    A.message("cycle moving forward again: %d curve(s)." % done)
    return done
