"""
One control maker (5.6.45): every tool that makes a control - Make controls, Shapes (Create), the Builder, Ribbon,
IK spline, World levels, Group controls, the face sliders - makes it here, so they all work the same way:

- the curve (its shape data and style: colour, line width),
- its group stack (top first), placed at a world matrix, under a parent,
- tagged as a Maya controller (pick-walk, the animators' tools find it), linked to the nearest tagged control
  above it once the hierarchy is in place (link / link_all).

    from gus_rigtool.core import control_maker as CM
    top, ctrl = CM.new("L_arm_ctrl", data, style, groups=["L_arm_ctrl_offset"], matrix=m, parent=p)
    CM.tag_all()        # Checker > Tag all controls: a rig made before 5.6.45 (never automatic)
"""

import maya.cmds as cmds

from gus_rigtool.core import curves


def _long(n):
    got = cmds.ls(n, long=True) if n else []
    return got[0] if got else None


def new(name, data, style=None, groups=(), matrix=None, parent=None, tag=True):
    """The control `name` with this shape, in its groups (top first), the top at matrix (world) under parent.
    Returns (top, ctrl) - long names; top is the control itself when there are no groups."""
    stack = []
    for g in groups or ():
        grp = cmds.createNode("transform", name=g, skipSelect=True)
        if stack:
            grp = cmds.parent(grp, stack[-1], relative=True)[0]
        stack.append(_long(grp) or grp)
    ctrl = curves.create_curve_control(name, data, style or {})
    if stack:
        ctrl = _long(cmds.parent(ctrl, stack[-1], relative=True)[0])
        top_id = cmds.ls(stack[0], uuid=True)[0]
    else:
        top_id = cmds.ls(ctrl, uuid=True)[0]
    ctrl_id = cmds.ls(ctrl, uuid=True)[0]
    top = cmds.ls(top_id, long=True)[0]
    if matrix is not None:                       # placed in the world first, then parented (keeps its place) -
        cmds.xform(top, worldSpace=True, matrix=list(matrix))      # the Builder's order: the same numbers
    if parent:
        cmds.parent(top, parent)
        top = cmds.ls(top_id, long=True)[0]
    ctrl = cmds.ls(ctrl_id, long=True)[0]
    if tag:
        tag_one(ctrl)
    return top, ctrl


def is_tagged(node):
    try:
        return bool(cmds.listConnections(node + ".message", type="controller", source=False, destination=True))
    except (RuntimeError, ValueError, TypeError):
        return False


def tag_one(ctrl):
    """Tag a control as a Maya controller (once). False when this Maya can't (or it's not there)."""
    if not ctrl or is_tagged(ctrl):
        return bool(ctrl)
    try:
        cmds.controller(ctrl)
        return True
    except (RuntimeError, TypeError, AttributeError, ValueError):
        return False


def _tagged_above(ctrl):
    p = cmds.listRelatives(ctrl, parent=True, fullPath=True) or []
    while p:
        if is_tagged(p[0]):
            return p[0]
        p = cmds.listRelatives(p[0], parent=True, fullPath=True) or []
    return None


def link(ctrl):
    """Pick-walk: the control's controller parent = the nearest tagged control above it. Returns that or None."""
    up = _tagged_above(ctrl)
    if not up:
        return None
    try:
        cmds.controller(ctrl, up, parent=True)
        return up
    except (RuntimeError, TypeError, AttributeError, ValueError):
        return None


def link_all(ctrls):
    """Link each tagged control to the one above it (after a build: the hierarchy is in place). Returns linked."""
    n = 0
    for c in ctrls or []:
        if is_tagged(c) and link(c):
            n += 1
    return n


def tag_all(nodes=None):
    """Checker > Tag all controls: every control (default: the scene's) tagged and linked up the hierarchy - never
    automatic (a rig made before 5.6.45). 'Not a control' curves are left out. Returns (newly tagged, linked)."""
    from gus_rigtool.core import control_role, utils
    if nodes is None:
        from gus_rigtool.core import on_top
        nodes = on_top.controls()
    nodes = [n for n in nodes if not control_role.is_marked(n)]
    tagged = 0
    with utils.undo_chunk("gusrigTagControls"):
        for n in nodes:
            if not is_tagged(n) and tag_one(n):
                tagged += 1
        linked = link_all(nodes)
    return tagged, linked
