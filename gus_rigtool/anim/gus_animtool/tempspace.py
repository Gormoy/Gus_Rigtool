"""
Temporary spaces (like Animo's Spacify / World Space): animate a control from another space for a while, then
bake it back.

  World  : a locator per control follows it over the frame range (baked), then the control follows the
           locator - animate the locators in world space.
  Camera : the same, with the locators under a group that follows the camera you look through (motion as the
           camera sees it - arcs, screen spacing).
  Pivot  : a locator at the control (move it where you want the pivot), the control follows it - turn the
           locator to rotate around a new pivot (this pose; key the control as usual).
  Bake back : the controls get their motion back as keys over the range; locators and groups are deleted.
"""

import maya.cmds as cmds

from gus_animtool import anim as A

TOP = "gusAnimtool_temp_grp"
TAG = "gusTempFor"


def _top():
    found = cmds.ls(TOP, long=True) or []
    return found[0] if found else cmds.ls(cmds.createNode("transform", name=TOP), long=True)[0]


def _skips(node):
    st = [ax for ax in "xyz" if not A._settable("%s.t%s" % (node, ax))]
    sr = [ax for ax in "xyz" if not A._settable("%s.r%s" % (node, ax))]
    return st, sr


def _free(nodes):
    """Controls already in a temporary space can't take another (their channels are driven): say so."""
    busy = set(n for _loc, ns in temp_nodes() for n in ns)
    taken = [A.short(n) for n in nodes if A.long_name(A.short(n)) in busy]
    if taken:
        raise RuntimeError("%s already in a temporary space - Bake back first." % ", ".join(taken[:4]))
    return nodes


def _tag(loc, node):
    cmds.addAttr(loc, longName=TAG, dataType="string")
    cmds.setAttr(loc + "." + TAG, A.short(node), type="string")


def _camera():
    try:
        panel = cmds.getPanel(withFocus=True)
        if cmds.getPanel(typeOf=panel) != "modelPanel":
            panel = (cmds.getPanel(visiblePanels=True) or [""])[0]
        return cmds.modelPanel(panel, query=True, camera=True)
    except (RuntimeError, TypeError):
        return "persp"


def _follow(nodes, parent, label):
    """Locators under parent baked to the nodes over the range, then the nodes follow them."""
    _free(nodes)
    start, end = A.frame_range()
    locs = []
    for n in nodes:
        loc = cmds.spaceLocator(name=A.short(n).split(":")[-1] + "_" + label + "_loc")[0]
        loc = cmds.parent(loc, parent)[0]
        _tag(loc, n)
        cmds.parentConstraint(n, loc, maintainOffset=False)
        locs.append(cmds.ls(loc, long=True)[0])
    cmds.bakeResults(locs, time=(start, end), simulation=True, attribute=A._T[:] + A._R[:], preserveOutsideKeys=True)
    for loc in locs:
        cons = cmds.listRelatives(loc, type="constraint", fullPath=True) or []
        if cons:
            cmds.delete(cons)
    for n, loc in zip(nodes, locs):
        st, sr = _skips(n)
        if len(st) < 3 or len(sr) < 3:
            cmds.parentConstraint(loc, n, maintainOffset=False, skipTranslate=st or "none", skipRotate=sr or "none")
    return locs


def world(nodes=None):
    nodes = nodes or [n for n in A.selected() if A._poseable(n)]
    if not nodes:
        raise RuntimeError("select the controls.")
    with A.Undo("gusAnimtoolTempWorld"):
        locs = _follow(nodes, _top(), "world")
    cmds.select(locs, replace=True)
    return locs


def camera(nodes=None):
    nodes = nodes or [n for n in A.selected() if A._poseable(n)]
    if not nodes:
        raise RuntimeError("select the controls.")
    cam = _camera()
    with A.Undo("gusAnimtoolTempCamera"):
        grp = cmds.createNode("transform", name="camera_space_grp", parent=_top())
        cmds.parentConstraint(cam, grp, maintainOffset=False)
        locs = _follow(nodes, grp, "camera")
    cmds.select(locs, replace=True)
    return locs


def pivot(nodes=None):
    nodes = nodes or [n for n in A.selected() if A._poseable(n)]
    if not nodes:
        raise RuntimeError("select the controls.")
    _free(nodes)
    with A.Undo("gusAnimtoolTempPivot"):
        loc = cmds.spaceLocator(name="temp_pivot_loc")[0]
        loc = cmds.parent(loc, _top())[0]
        _tag(loc, ",".join(A.short(n) for n in nodes))
        cmds.xform(loc, worldSpace=True, translation=cmds.xform(nodes[0], query=True, worldSpace=True,
                                                                  rotatePivot=True))
        for n in nodes:
            st, sr = _skips(n)
            cmds.parentConstraint(loc, n, maintainOffset=True, skipTranslate=st or "none", skipRotate=sr or "none")
    cmds.select(loc, replace=True)
    return loc


def temp_nodes():
    """[(locator, [controls])] of every temporary space in the scene."""
    out = []
    for loc in cmds.ls("*." + TAG, objectsOnly=True, long=True) or []:
        names = (cmds.getAttr(loc + "." + TAG) or "").split(",")
        nodes = [A.long_name(x) for x in names if A.long_name(x)]
        out.append((loc, nodes))
    return out


def bake_back(*_):
    """Every control with a temporary space gets its motion as keys over the range; the helpers go."""
    items = temp_nodes()
    if not items:
        raise RuntimeError("no temporary spaces in the scene.")
    nodes = sorted(set(n for _l, ns in items for n in ns))
    start, end = A.frame_range()
    with A.Undo("gusAnimtoolBakeBack"):
        cmds.bakeResults(nodes, time=(start, end), simulation=True, attribute=A._T[:] + A._R[:],
                         preserveOutsideKeys=True)
        helpers = set(A.short(loc) for loc, _ns in items)
        for n in nodes:
            for c in cmds.listRelatives(n, type="parentConstraint", fullPath=True) or []:
                targets = cmds.parentConstraint(c, query=True, targetList=True) or []
                if any(A.short(t) in helpers for t in targets):
                    cmds.delete(c)
        top = cmds.ls(TOP, long=True)
        if top:
            cmds.delete(top)
    return len(nodes)
