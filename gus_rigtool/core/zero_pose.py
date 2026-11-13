"""
Keep the pose, zero the control (5.5.1): a control moved to where it should rest (the Hare's cape ribbon controls,
Eyes_ctrl) - its values go into the group above it, so nothing moves and the control reads 0 there (the animator's
reset brings it back to this spot, not to the old one). 5.6.6: when that group can't take them (a constraint drives
it, it's locked, or other things are under it), a new group <control>_rest goes right above the control instead.

    from gus_rigtool.core import zero_pose
    done, skipped = zero_pose.apply(["Cape_Ribbon_fol_02_ctrl", "Eyes_ctrl"])
"""

import maya.cmds as cmds

from gus_rigtool.core import naming, utils
from gus_rigtool.core import world_turn as WT

REST = (("translate", 0.0), ("rotate", 0.0), ("scale", 1.0))


def _short(n):
    return naming.short_name(n)


def blocker(c):
    """Why the control's values can't go into its group, or None."""
    par = cmds.listRelatives(c, parent=True, fullPath=True)
    if not par:
        return "no group above it"
    p = par[0]
    others = [x for x in cmds.listRelatives(p, children=True, type="transform", fullPath=True) or [] if x != c and
              "constraint" not in cmds.nodeType(x).lower()]           # 5.6.6: its own constraint node isn't one
    if others:
        return "its group %s has other things under it (%s)" % (_short(p), ", ".join(_short(x) for x in others[:3]))
    for a, _v in REST:
        if cmds.listConnections("%s.%s" % (p, a), source=True, destination=False):
            return "%s.%s is driven" % (_short(p), a)
        for ax in "XYZ":
            plug = "%s.%s%s" % (p, a, ax)
            if cmds.getAttr(plug, lock=True):
                return "%s.%s%s is locked" % (_short(p), a, ax)
            if cmds.listConnections(plug, source=True, destination=False):
                return "%s.%s%s is driven" % (_short(p), a, ax)
    return None


def rest_group(c):
    """5.6.6: a new group <control>_rest right above the control (where it is now - nothing moves) when the group
    above can't take the pose (driven by a constraint, locked, or shared). Returns (group, control)."""
    p = (cmds.listRelatives(c, parent=True, fullPath=True) or [None])[0]
    name = _short(c) + "_rest"
    g = cmds.createNode("transform", name=name, parent=p, skipSelect=True) if p else \
        cmds.createNode("transform", name=name, skipSelect=True)
    g = (cmds.ls(g, long=True) or [g])[0]
    cmds.parent(c, g, relative=True)                    # its values stay; the new group is at the old group
    return g, g + "|" + _short(c)


def at_rest(c):
    for a, v in REST:
        for ax in "XYZ":
            plug = "%s.%s%s" % (c, a, ax)
            try:
                if cmds.getAttr(plug, settable=True) and abs(cmds.getAttr(plug) - v) > 1e-6:
                    return False
            except (RuntimeError, ValueError):
                continue
    return True


MOVABLE = ("parentConstraint", "pointConstraint", "orientConstraint", "scaleConstraint")


def constraints_on(c):
    """5.6.30: (constraints driving the control straight, why it can't be handled or None). The pupils: a
    constraint on the control itself - zeroing moved them, the constraint pulling them back."""
    cons = []
    for n in cmds.listConnections(c, source=True, destination=False) or []:
        if cmds.objectType(n, isAType="constraint") and n not in cons:
            cons.append(n)
    via = [pb for pb in set(cmds.listConnections(c, type="pairBlend", source=True, destination=False) or [])
           if cmds.listConnections(pb, type="constraint", source=True, destination=False)]
    if via:
        return cons, "keys and a constraint blended on it (pairBlend) - Repair the stray keys first"
    odd = [x for x in cons if cmds.nodeType(x) not in MOVABLE]
    if odd:
        return cons, "a %s on it - move that one by hand" % cmds.nodeType(odd[0])
    return cons, None


def _read_constraints(cons):
    from gus_rigtool.core import ribbon
    data = []
    for con in cons:
        kind = cmds.nodeType(con)
        fn = getattr(cmds, kind)
        data.append((fn, fn(con, query=True, targetList=True) or [],
                     [cmds.getAttr(con + "." + a) for a in fn(con, query=True, weightAliasList=True) or []],
                     ribbon._skip_flags(con, kind), _short(con)))
    return data


def _remake(data, driven):
    made = []
    for fn, targets, weights, flags, name in data:
        con = fn(targets, driven, maintainOffset=True, name=name, **flags)[0]
        for alias, w in zip(fn(con, query=True, weightAliasList=True) or [], weights):
            cmds.setAttr(con + "." + alias, w)
        made.append(con)
    return made


def apply(ctrls):
    """Every control: zeroed with its group taking the pose (nothing moves). One undo. Returns (done, [(control,
    why skipped)]). 5.6.30: a control driven by a constraint (the pupils) - the constraint goes onto the group
    (a <control>_rest group of its own when the one above can't take it), the control reads 0, nothing moves."""
    done, skipped = [], []
    with utils.undo_chunk("gusrigZeroPose"):
        for c in ctrls:
            c = (cmds.ls(c, long=True) or [c])[0]
            cons, why_not = constraints_on(c)
            if why_not:
                skipped.append((c, why_not))
                continue
            if at_rest(c) and not cons:
                continue
            data = None
            if cons:
                data = _read_constraints(cons)
                cmds.delete(cons)                       # the control keeps the values the constraint gave it
            why = blocker(c)
            if why:
                try:
                    _g, c = rest_group(c)               # 5.6.6: a group of its own takes the pose
                except RuntimeError as e:
                    if data:
                        _remake(data, c)                # 5.6.30: the constraint goes back where it was
                    skipped.append((c, "%s - and no group could go above it (%s)" % (why, e)))
                    continue
            m = cmds.xform(c, query=True, worldSpace=True, matrix=True)
            for a, v in REST:
                for ax in "XYZ":
                    plug = "%s.%s%s" % (c, a, ax)
                    if cmds.getAttr(plug, settable=True):
                        cmds.setAttr(plug, v)
            p = cmds.listRelatives(c, parent=True, fullPath=True)[0]
            local = cmds.xform(c, query=True, objectSpace=True, matrix=True)    # what's left (locked channels)
            cmds.xform(p, worldSpace=True, matrix=WT._mul(WT._inv(local), m))
            if data:
                _remake(data, p)                        # 5.6.30: the group follows what the control followed
            done.append(c)
    return done, skipped
