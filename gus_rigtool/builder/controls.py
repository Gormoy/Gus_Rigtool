"""Controls for the builder: Shape Library shapes, offset groups, side colours, attributes, spaces."""

import maya.cmds as cmds

from gus_rigtool.builder import guides, mathx, names
from gus_rigtool.core import colors, curves, shape_data


def long(node):
    return cmds.ls(node, long=True)[0]


def group(name, parent=None, matrix=None):
    g = cmds.createNode("transform", name=name)
    if matrix is not None:
        cmds.xform(g, worldSpace=True, matrix=matrix)
    if parent:
        g = cmds.parent(g, parent)[0]
    return long(g)


def _is_world_aligned(m):
    return all(abs(m[r * 4 + c] - (1.0 if r == c else 0.0)) < 1e-4 for r in range(3) for c in range(3))


def make(side, part, shape="circle", size=1.0, matrix=None, parent=None, face="X", variant=None,
         rgb=None, lock=("sx", "sy", "sz", "v"), shape_offset=None, mirror="auto", shape_flip=None,
         shape_dir=None):
    """
    (offset, ctrl): a control at matrix, under parent, coloured by side.
    shape: a Shape Library name, or (name, [rx, ry, rz]): the shape turned in the control's axes.
    shape_offset: move the shape (in the control's axes) away from the pivot.
    shape_dir: turn the shape so its +Y (the way a pin points) goes along this direction (control's axes).
    mirror 'auto': a right-side control gets the mirror image of its left twin's shape - reflected
    across X when its axes are the world's, turned round (all axes) when they are behavior-mirrored.
    """
    s = names.settings()
    rotate = None
    if isinstance(shape, (tuple, list)):                   # (shape name, [rx, ry, rz]) from the settings
        shape, rotate = shape[0], shape[1]
    data = shape_data.scale(shape_data.face(guides.library_shape(shape), face.lstrip("-")), float(size))
    if rotate and any(abs(float(r)) > 1e-6 for r in rotate):
        from gus_rigtool.core import mirror_engine as me
        m = me.euler_matrix([float(r) for r in rotate], 0)        # turns the shape in the control's axes
        data = shape_data.map_points(data, lambda p: tuple(sum(p[k] * m[k * 4 + c] for k in range(3))
                                                           for c in range(3)))
    if shape_dir:
        r = mathx.rotation_between([0.0, 1.0, 0.0], shape_dir)
        data = shape_data.map_points(data, lambda p: tuple(sum(p[k] * r[k * 4 + c] for k in range(3))
                                                           for c in range(3)))
    if shape_flip:                                         # e.g. (-1, 1, 1): turn the shape along X
        f = shape_flip
        data = shape_data.map_points(data, lambda p: (p[0] * f[0], p[1] * f[1], p[2] * f[2]))
    if shape_offset:
        o = shape_offset
        data = shape_data.map_points(data, lambda p: (p[0] + o[0], p[1] + o[1], p[2] + o[2]))
    if mirror == "auto" and side == "R":
        if matrix is None or _is_world_aligned(matrix):
            data = shape_data.map_points(data, lambda p: (-p[0], p[1], p[2]))
        else:
            data = shape_data.map_points(data, lambda p: (-p[0], -p[1], -p[2]))
    rgb = rgb or colors.side_colors()[side]
    ctrl = curves.create_curve_control(names.make(side, part, "ctrl", variant, s), data, curves.rgb_style(rgb))
    offset = cmds.createNode("transform", name=names.make(side, part, "offset", variant, s))
    if matrix is not None:
        cmds.xform(offset, worldSpace=True, matrix=matrix)
    ctrl = cmds.parent(ctrl, offset, relative=True)[0]
    if parent:
        offset = cmds.parent(offset, parent)[0]
    offset = long(offset)
    ctrl = cmds.listRelatives(offset, children=True, type="transform", fullPath=True)[0]
    for attr in lock or ():
        cmds.setAttr(ctrl + "." + attr, lock=True, keyable=False, channelBox=False)
    return offset, ctrl


def add_float(node, attr, default=0.0, minimum=None, maximum=None, keyable=True):
    kw = {"longName": attr, "attributeType": "double", "defaultValue": default, "keyable": keyable}
    if minimum is not None:
        kw["minValue"] = minimum
    if maximum is not None:
        kw["maxValue"] = maximum
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, **kw)
    return node + "." + attr


def add_bool(node, attr, default=False):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, attributeType="bool", defaultValue=default, keyable=True)
    return node + "." + attr


def add_enum(node, attr, items, default=0):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, attributeType="enum", enumName=":".join(items),
                     defaultValue=default, keyable=True)
    return node + "." + attr


def separator(node, label):
    attr = "_" + label.replace(" ", "_")
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, niceName="------ %s" % label, attributeType="enum",
                     enumName="------", keyable=False)
        cmds.setAttr(node + "." + attr, channelBox=True, lock=True)


def add_string(node, attr, value):
    if not cmds.attributeQuery(attr, node=node, exists=True):
        cmds.addAttr(node, longName=attr, dataType="string")
    cmds.setAttr(node + "." + attr, value, type="string")


def get_string(node, attr):
    if cmds.objExists(node) and cmds.attributeQuery(attr, node=node, exists=True):
        return cmds.getAttr(node + "." + attr) or ""
    return ""


def add_spaces(side, part, ctrl, offset, targets, kind="parent", default=0):
    """
    Space switch: a 'space' group above the offset group follows one of the targets, picked by
    an enum attribute 'space' on the control. targets: [(label, node)]. kind 'parent' or 'orient'.
    Returns (space group or None, offset, ctrl) - the offset and control paths change.
    """
    targets = [(label, node) for label, node in targets if node and cmds.objExists(node)]
    if len(targets) < 2:
        return None, offset, ctrl
    ctrl_name = ctrl.split("|")[-1]
    parent = (cmds.listRelatives(offset, parent=True, fullPath=True) or [None])[0]
    m = cmds.xform(offset, query=True, worldSpace=True, matrix=True)
    if mathx.det3(m) < 0:                         # a mirrored control (scale -1): the space group stays unscaled
        m = mathx.translate_matrix(m[12:15])
    space = group(names.make(side, part, "grp", "space"), parent, m)
    offset = long(cmds.parent(offset, space)[0])
    ctrl = long(ctrl_name)                                        # its path changed
    nodes = [node for _l, node in targets]
    # a parent constraint even for 'orient' (rotation only): it keeps one offset PER target, so switching
    # never turns the control (an orient constraint keeps a single offset for all targets: the head twisted)
    kw = {"skipTranslate": ["x", "y", "z"]} if kind == "orient" else {}
    con = cmds.parentConstraint(nodes, space, maintainOffset=True, **kw)[0]
    cmds.setAttr(con + ".interpType", 2)
    plug = add_enum(ctrl, "space", [label for label, _n in targets], default)
    aliases = cmds.parentConstraint(con, query=True, weightAliasList=True) or []
    for i, alias in enumerate(aliases):
        cond = cmds.createNode("condition", name=names.make(side, part + "_space%d" % i, "grp")
                               .replace("_grp", "_cond"))
        cmds.connectAttr(plug, cond + ".firstTerm")
        cmds.setAttr(cond + ".secondTerm", i)
        cmds.setAttr(cond + ".colorIfTrueR", 1)
        cmds.setAttr(cond + ".colorIfFalseR", 0)
        cmds.connectAttr(cond + ".outColorR", con + "." + alias)
    return space, offset, ctrl
