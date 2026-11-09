"""
Make controls (4.1.1): a control on each selected joint or object - a Shapes library shape, sized from the bone /
object, facing the joint's axis, coloured by side - in an offset group stack (your Groups stacks), driving the
joint by constraints (default), by parenting, or by direct connections. A chain gets an FK chain of controls.

    from gus_rigtool.core import make_controls as MC
    MC.make(cmds.ls(sl=True, long=True))

Names: L_arm_jnt -> L_arm_ctrl, L_arm_ctrl_offset (the type suffix is swapped).
Joints are never frozen: their orientation (and any skin) stays as it is.
"""

import math

import maya.cmds as cmds

from gus_rigtool.core import colors, curves, mirror_engine, naming, shape_data, sides, utils
from gus_rigtool.core import nodes as _nodes

DRIVE = ("constrain", "parent", "direct")
META = "gusMadeFor"                  # on the control: the node it drives


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_long = _nodes.long_name


_parent = _nodes.parent_of


_wm = _nodes.world_matrix


def match_matrix(node):
    """The node's world rotation (no scale, no -1) at its pivot."""
    _t, rot, _s = mirror_engine.decompose(_wm(node))
    return mirror_engine.compose(cmds.xform(node, query=True, worldSpace=True, rotatePivot=True), rot)


def auto_size(node):
    """Half the bone length (to the first child joint), else the joint radius x 2, else 0.6 x the object's
    size; never 0."""
    if cmds.nodeType(node) == "joint":
        kids = cmds.listRelatives(node, children=True, type="joint", fullPath=True) or []
        p = cmds.xform(node, query=True, worldSpace=True, translation=True)
        if kids:
            q = cmds.xform(kids[0], query=True, worldSpace=True, translation=True)
            d = math.sqrt(sum((a - b) ** 2 for a, b in zip(p, q)))
            if d > 1e-4:
                return d * 0.5
        try:
            return max(cmds.getAttr(node + ".radius") * 2.0, 0.1)
        except (RuntimeError, ValueError):
            return 1.0
    try:
        bb = cmds.exactWorldBoundingBox(node)
        size = max(bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
        return size * 0.6 if size > 1e-4 else 1.0
    except (RuntimeError, ValueError, TypeError):
        return 1.0


def base_name(node):
    """'L_arm_jnt' -> 'L_arm'."""
    return naming.strip_type_suffix(naming.short_name(node).split(":")[-1])


def names_for(node, stack):
    base = base_name(node)
    ctrl = base + "_ctrl"
    return ctrl, [ctrl + sfx for sfx in stack]


def control_of(node):
    """The control this tool made for node, or None."""
    short = naming.short_name(node)
    for c in cmds.ls("*." + META, objectsOnly=True, long=True, recursive=True) or []:
        try:
            if cmds.getAttr(c + "." + META) == short:
                return c
        except (RuntimeError, ValueError):
            continue
    return None


def _depth_sorted(nodes):
    return sorted(dict.fromkeys(nodes), key=lambda n: n.count("|"))


def _nearest_made_ancestor(node, made):
    """The control made for the closest ancestor of node (in this run, or before)."""
    p = _parent(node)
    while p:
        if p in made:
            return made[p]
        c = control_of(p)
        if c:
            return c
        p = _parent(p)
    return None


def _shape(name, face, size):
    from gus_rigtool.builder import guides
    data = guides.library_shape(name)
    if not data:
        raise RuntimeError("shape '%s' isn't in the Shapes library." % name)
    return shape_data.scale(shape_data.face(data, face.lstrip("-")), float(size))


def _set3(node, attr, v):
    for a, x in zip("XYZ", v):
        plug = "%s.%s%s" % (node, attr, a)
        try:
            if cmds.getAttr(plug, settable=True):
                cmds.setAttr(plug, x)
        except (RuntimeError, ValueError):
            pass


def _zero_joint_under(joint):
    """A joint just parented under its control (same place): translate / rotate -> 0, the rotation kept in
    Joint Orient (the joint's world matrix doesn't change, so the skin doesn't move)."""
    w = _wm(joint)
    par = _parent(joint)
    pm = _wm(par) if par else list(mirror_engine.IDENTITY)
    local = mirror_engine.mul(w, mirror_engine.inverse(pm))
    t, r, s = mirror_engine.decompose(local)
    if max(abs(v) for v in t) < 1e-4:
        _set3(joint, "translate", [0.0, 0.0, 0.0])
    if cmds.nodeType(joint) == "joint" and all(abs(v) < 1e-6 for v in cmds.getAttr(joint + ".rotateAxis")[0]):
        _set3(joint, "rotate", [0.0, 0.0, 0.0])
        _set3(joint, "jointOrient", r)
    else:
        _set3(joint, "rotate", r)


def _direct(ctrl, node):
    """node = its rest values + the control's (translate, rotate); scale x the control's."""
    base = naming.strip_type_suffix(naming.short_name(node))
    for ch in ("translate", "rotate"):
        rest = list(cmds.getAttr("%s.%s" % (node, ch))[0])
        if max(abs(v) for v in rest) < 1e-6:
            cmds.connectAttr("%s.%s" % (ctrl, ch), "%s.%s" % (node, ch), force=True)
            continue
        pma = cmds.createNode("plusMinusAverage", name=base + "_" + ch + "_add")
        cmds.connectAttr("%s.%s" % (ctrl, ch), pma + ".input3D[0]")
        cmds.setAttr(pma + ".input3D[1]", *rest, type="double3")
        cmds.connectAttr(pma + ".output3D", "%s.%s" % (node, ch), force=True)
    rest = list(cmds.getAttr(node + ".scale")[0])
    if max(abs(v - 1.0) for v in rest) < 1e-6:
        cmds.connectAttr(ctrl + ".scale", node + ".scale", force=True)


# ---------------------------------------------------------------------------
# the tool
# ---------------------------------------------------------------------------

def plan(nodes, stack=("_offset",), hierarchy=True, both_sides=False):
    """[(node, control name, [group names], parent control or None, note)] - what make() will do."""
    from gus_rigtool.core import joint_labels
    nodes = [n for n in (_long(x) for x in nodes) if n]
    if both_sides:
        extra = []
        for n in nodes:
            other = joint_labels.twin_name(naming.short_name(n))
            t = _long(other) if other else None
            if t and t not in nodes and t not in extra:
                extra.append(t)
        nodes += extra
    nodes = _depth_sorted(nodes)
    rows, chosen = [], set(nodes)
    for n in nodes:
        ctrl, groups = names_for(n, stack)
        note = ""
        if control_of(n):
            note = "already has a control (%s), skipped" % naming.short_name(control_of(n))
        par = None
        if hierarchy:
            p = _parent(n)
            while p and p not in chosen and not control_of(p):
                p = _parent(p)
            if p:
                par = names_for(p, stack)[0] if p in chosen else naming.short_name(control_of(p))
        rows.append((n, ctrl, groups, par, note))
    return rows


def make(nodes, shape="circle", size=None, face="X", stack=("_offset",), drive="constrain", scale=True,
         hierarchy=True, lock=True, tag=True, side_colour=True, both_sides=False, size_factor=1.0):
    """Make the controls; returns [(node, control)]. size None = auto per node (x size_factor)."""
    if drive not in DRIVE:
        raise ValueError(drive)
    stack = [s for s in stack if s] or ["_offset"]
    rows = plan(nodes, stack, hierarchy, both_sides)
    if not rows:
        raise RuntimeError("select the joints or objects to put controls on.")
    made, out = {}, []
    with utils.undo_chunk("gusrigMakeControls"):
        for node, ctrl_name, group_names, _par, note in rows:
            node = _long(naming.short_name(node)) or node
            if note:
                continue
            sz = (float(size) if size else auto_size(node)) * float(size_factor)
            side = sides.side_of_node(node)
            style = curves.rgb_style(colors.side_colors()[side]) if side_colour else {}
            data = _shape(shape, face, sz)
            if side == "R" and cmds.nodeType(node) != "joint":
                data = shape_data.map_points(data, lambda p: (-p[0], p[1], p[2]))
            ctrl = curves.create_curve_control(naming.unique(ctrl_name), data, style)
            mat = match_matrix(node)
            groups = []
            for g in group_names:
                grp = cmds.createNode("transform", name=naming.unique(g))
                if groups:
                    grp = cmds.parent(grp, groups[-1])[0]
                grp = cmds.ls(grp, long=True)[0]
                cmds.xform(grp, worldSpace=True, matrix=mat)
                groups.append(grp)
            gids = [utils.uuid(g) for g in groups]
            cid = utils.uuid(ctrl)
            cmds.parent(ctrl, utils.path(gids[-1]), relative=True)
            ctrl = utils.path(cid)
            # where the stack goes
            up = None
            if drive == "direct":
                up = _parent(node)                        # same space as the node: channels line up
            elif hierarchy:
                up = _nearest_made_ancestor(node, made)
            if up:
                cmds.parent(utils.path(gids[0]), up)
            ctrl = utils.path(cid)
            cmds.addAttr(ctrl, longName=META, dataType="string")
            cmds.setAttr(ctrl + "." + META, naming.short_name(node), type="string")
            nid = utils.uuid(node)
            if drive == "constrain":
                cmds.parentConstraint(ctrl, node, maintainOffset=True)
                if scale:
                    cmds.scaleConstraint(ctrl, node, maintainOffset=True)
            elif drive == "parent":
                cmds.parent(node, ctrl)
                _zero_joint_under(utils.path(nid))
            else:
                _direct(ctrl, node)
            if lock:
                attrs = ["v"] + ([] if scale else ["sx", "sy", "sz"])
                for a in attrs:
                    try:
                        cmds.setAttr("%s.%s" % (ctrl, a), lock=True, keyable=False, channelBox=False)
                    except RuntimeError:
                        pass
            if tag:
                try:
                    cmds.controller(ctrl)
                    if up and cmds.objExists(up) and cmds.listConnections(up, type="controller"):
                        cmds.controller(ctrl, up, parent=True)
                except (RuntimeError, TypeError, AttributeError):
                    pass
            made[utils.path(nid)] = ctrl
            out.append((utils.path(nid), utils.path(cid)))
    cmds.select([c for _n, c in out], replace=True)
    return out
