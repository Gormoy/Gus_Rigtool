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


def apply(ctrls):
    """Every control: zeroed with its group taking the pose (nothing moves). One undo. Returns (done, [(control,
    why skipped)])."""
    done, skipped = [], []
    with utils.undo_chunk("gusrigZeroPose"):
        for c in ctrls:
            c = (cmds.ls(c, long=True) or [c])[0]
            if at_rest(c):
                continue
            why = blocker(c)
            if why:
                try:
                    _g, c = rest_group(c)               # 5.6.6: a group of its own takes the pose
                except RuntimeError as e:
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
            done.append(c)
    return done, skipped
