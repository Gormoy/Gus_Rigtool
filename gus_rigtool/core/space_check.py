"""
Space switches and turns, measured (5.6.7) - for Check this scene.

    from gus_rigtool.core import space_check
    space_check.run()          # every space switch: each space at rest (no jump) and at the rig's scale x2
    space_check.turn_test()    # the head turned 30 degrees: what turns about twice as much (the Hare's eyeballs: 72)
"""

import math

import maya.cmds as cmds

from gus_rigtool.core import naming
from gus_rigtool.core import world_turn as WT

JUMP = 0.01
OFF = 0.05
WORDS = ("space", "follow")


def _short(n):
    return naming.short_name(n)


def _pos(m):
    return m[12:15]


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def switches():
    """[(control, attribute, [labels])]: controls with a space / follow menu (made by the builder, the Spaces page
    or by hand)."""
    from gus_rigtool.tools import checker
    out = []
    for c in checker.transforms(None):
        if not checker.is_control(c):
            continue
        for a in cmds.listAttr(c, userDefined=True) or []:
            if not any(w in a.lower() for w in WORDS):
                continue
            try:
                labels = (cmds.attributeQuery(a, node=c, listEnum=True) or [""])[0].split(":")
            except (RuntimeError, TypeError):
                continue                                    # not a menu
            if len(labels) > 1 and not cmds.listConnections(c + "." + a, source=True, destination=False):
                out.append((c, a, labels))
    return out


def run(factor=2.0):
    """{'switches': n, 'jumps': [(control, label, distance)], 'scale': [(control, label, distance)], 'plug'}:
    each space chosen at rest - the control should stay put (made with no jump); then the rig scaled x factor -
    it should go where the scale takes it. Everything put back."""
    from gus_rigtool.core import scale_check as SC
    sw = switches()
    out = {"switches": len(sw), "jumps": [], "scale": [], "plug": None}
    if not sw:
        return out
    ctrl, plug = SC.scale_control()
    out["plug"] = plug
    undo = cmds.undoInfo(query=True, state=True)
    try:
        cmds.undoInfo(stateWithoutFlush=False)
        for c, a, labels in sw:
            old = cmds.getAttr(c + "." + a)
            rest = WT._wm(c)
            for v, label in enumerate(labels):
                cmds.setAttr(c + "." + a, v)
                WT._settle()
                m0 = WT._wm(c)
                d = _dist(_pos(m0), _pos(rest))
                if d > JUMP:
                    out["jumps"].append((c, label, d))
                if plug:
                    g0 = WT._wm(ctrl)
                    was = cmds.getAttr(plug)
                    cmds.setAttr(plug, was * factor)
                    WT._settle()
                    want = WT._mul(m0, WT._mul(WT._inv(g0), WT._wm(ctrl)))
                    off = _dist(_pos(WT._wm(c)), _pos(want))
                    cmds.setAttr(plug, was)
                    WT._settle()
                    if off > OFF:
                        out["scale"].append((c, label, off))
            cmds.setAttr(c + "." + a, old)
            WT._settle()
    finally:
        cmds.undoInfo(stateWithoutFlush=undo)
    return out


def head_control():
    from gus_rigtool.builder import names
    from gus_rigtool.tools import checker
    want = [x.lower() for x in ("Head_ctrl", names.make("C", "head", "ctrl"), "C_head_ctrl", "Head_CTRL")]
    found = [c for c in checker.transforms(None) if checker.is_control(c) and _short(c).lower() in want]
    found.sort(key=lambda c: want.index(_short(c).lower()))
    return found[0] if found else None


def _angle(m0, m1):
    """Degrees between two world matrices' rotations (scale taken out)."""
    def axes(m):
        out = []
        for r in range(3):
            v = m[r * 4:r * 4 + 3]
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out
    a, b = axes(m0), axes(m1)
    trace = sum(sum(a[r][k] * b[r][k] for k in range(3)) for r in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))


def turn_test(ctrl=None, angle=30.0):
    """{'control', 'axis', 'twice': [(node, degrees)]}: the head turned by angle (its first free rotate axis of
    Y, X, Z); joints and controls that turn 1.5x as much or more - something gives them the head's turn twice. Put
    back."""
    ctrl = ctrl or head_control()
    out = {"control": ctrl, "axis": None, "twice": []}
    if not ctrl:
        return out
    axis = None
    for ax in "YXZ":
        plug = "%s.rotate%s" % (ctrl, ax)
        try:
            if cmds.getAttr(plug, settable=True):
                axis = ax
                break
        except (RuntimeError, ValueError):
            continue
    if not axis:
        return out
    out["axis"] = axis
    from gus_rigtool.tools import checker
    nodes = (cmds.ls(type="joint", long=True) or []) + [c for c in checker.transforms(None) if checker.is_control(c)]
    nodes = [n for n in nodes if n != ctrl]
    before = dict((n, WT._wm(n)) for n in nodes)
    plug = "%s.rotate%s" % (ctrl, axis)
    old = cmds.getAttr(plug)
    undo = cmds.undoInfo(query=True, state=True)
    try:
        cmds.undoInfo(stateWithoutFlush=False)
        cmds.setAttr(plug, old + angle)
        WT._settle()
        for n in nodes:
            try:
                d = _angle(before[n], WT._wm(n))
            except (RuntimeError, ValueError):
                continue
            if d > angle * 1.5:
                out["twice"].append((n, d))
    finally:
        cmds.setAttr(plug, old)
        WT._settle()
        cmds.undoInfo(stateWithoutFlush=undo)
    out["twice"].sort(key=lambda x: -x[1])
    return out
