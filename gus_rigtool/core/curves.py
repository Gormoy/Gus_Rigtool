"""
Curve control helpers: read and write shape data, colour, line width, CVs.

Shape data format: see core/shape_data.py.
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om

from gus_rigtool.core import naming

COLOR_ATTRS = ("overrideEnabled", "overrideRGBColors", "overrideColor", "overrideColorRGB")


# ---------------------------------------------------------------------------
# shapes
# ---------------------------------------------------------------------------

def curve_shapes(node):
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True, noIntermediate=True) or []
    return [s for s in shapes if cmds.nodeType(s) == "nurbsCurve"]


def other_shapes(node):
    """Non-curve shapes (mesh, surface...) under a transform."""
    shapes = cmds.listRelatives(node, shapes=True, fullPath=True, noIntermediate=True) or []
    return [s for s in shapes if cmds.nodeType(s) != "nurbsCurve"]


def read_shape(node):
    """Shape data of every curve shape under node, in the node's object space."""
    out = []
    for shape in curve_shapes(node):
        sel = om.MSelectionList()
        sel.add(shape)
        fn = om.MFnNurbsCurve(sel.getDagPath(0))
        pts = [[p.x, p.y, p.z] for p in fn.cvPositions(om.MSpace.kObject)]
        out.append({
            "degree": fn.degree,
            "form": 2 if fn.form == om.MFnNurbsCurve.kPeriodic else 0,
            "points": pts,
            "knots": list(fn.knots()),
        })
    return out


def _make_curve(data):
    return cmds.curve(degree=data["degree"], point=[tuple(p) for p in data["points"]],
                      knot=data["knots"], periodic=data["form"] == 2)


def read_style(node):
    """Colour and line width of a control (first curve shape, else the transform)."""
    shapes = curve_shapes(node)
    source = shapes[0] if shapes else node
    style = {}
    if shapes and not cmds.getAttr(source + ".overrideEnabled"):
        source = node                                  # colour may be set on the transform
    for attr in COLOR_ATTRS:
        if cmds.attributeQuery(attr, node=source, exists=True):
            value = cmds.getAttr(source + "." + attr)
            style[attr] = list(value[0]) if isinstance(value, list) else value
    if shapes and cmds.attributeQuery("lineWidth", node=shapes[0], exists=True):
        style["lineWidth"] = cmds.getAttr(shapes[0] + ".lineWidth")
    return style


def apply_style(shapes, style):
    for shape in shapes:
        for attr, value in style.items():
            if not cmds.attributeQuery(attr, node=shape, exists=True):
                continue
            try:
                if isinstance(value, list):
                    cmds.setAttr(shape + "." + attr, *value)
                else:
                    cmds.setAttr(shape + "." + attr, value)
            except RuntimeError:
                pass


def set_shape(node, curves, style=None):
    """
    Replace the curve shapes under node with new ones built from data.
    The transform is untouched, so keys, constraints and connections stay.
    style: colour/line width to put on the new shapes (default: the old ones').
    Returns the new shape names.
    """
    if style is None:
        style = read_style(node)
    old = curve_shapes(node)
    if old and any(_fixed(n) for n in [node] + old):
        return _set_in_place(node, curves, old, style)
    base = naming.split_namespace(node)[1]

    new_shapes = []
    for data in curves:
        temp = _make_curve(data)
        shape = cmds.listRelatives(temp, shapes=True, fullPath=True)[0]
        shape = cmds.parent(shape, node, relative=True, shape=True)[0]
        cmds.delete(temp)
        new_shapes.append(shape)

    if old:
        cmds.delete(old)

    shape_ids = [cmds.ls(s, uuid=True)[0] for s in new_shapes]
    for i, sid in enumerate(shape_ids):
        name = base + "Shape" + ("" if i == 0 else str(i))
        cmds.rename(cmds.ls(sid, long=True)[0], name)
    final = [cmds.ls(sid, long=True)[0] for sid in shape_ids]
    apply_style(final, style)
    return final


def _fixed(node):
    """A node Maya won't let us delete or rename: from a referenced file, or locked (lockNode)."""
    try:
        if cmds.referenceQuery(node, isNodeReferenced=True):
            return True
    except RuntimeError:
        pass
    try:
        return bool((cmds.lockNode(node, query=True, lock=True) or [False])[0])
    except RuntimeError:
        return False


def _set_in_place(node, curves, old, style):
    """5.6.48: a control from a referenced or locked rig - its curves can't be deleted, so each one is rebuilt where
    it is (curve -replace). A new shape with more curves than the control has: the extra ones are added; fewer: the
    curves left over are hidden. Returns the shapes."""
    final = []
    for i, data in enumerate(curves):
        if i < len(old):
            cmds.curve(old[i], replace=True, degree=data["degree"], point=[tuple(p) for p in data["points"]],
                       knot=data["knots"], periodic=data["form"] == 2)
            final.append(old[i])
        else:
            temp = _make_curve(data)
            shape = cmds.listRelatives(temp, shapes=True, fullPath=True)[0]
            final.append(cmds.parent(shape, node, relative=True, shape=True)[0])
            cmds.delete(temp)
    for extra in old[len(curves):]:
        cmds.setAttr(extra + ".visibility", False)
    apply_style(final, style)
    return final


def create_curve_control(name, curves, style=None):
    """New transform with the given shape. Returns the transform."""
    node = cmds.createNode("transform", name=name)
    set_shape(node, curves, style or {})
    return cmds.ls(node, long=True)[0]


# ---------------------------------------------------------------------------
# colour / line width
# ---------------------------------------------------------------------------

def rgb_style(rgb, line_width=None):
    style = {"overrideEnabled": 1, "overrideRGBColors": 1, "overrideColorRGB": list(rgb)}
    if line_width is not None:
        style["lineWidth"] = line_width
    return style


def set_color(node, rgb):
    apply_style(curve_shapes(node), rgb_style(rgb))


def set_line_width(node, width):
    apply_style(curve_shapes(node), {"lineWidth": float(width)})


# ---------------------------------------------------------------------------
# CVs
# ---------------------------------------------------------------------------

def cvs(shape):
    return cmds.ls(shape + ".cv[*]", flatten=True) or []


def map_cvs_object(node, func):
    """Move every CV of node: new object-space position = func(old position)."""
    for shape in curve_shapes(node):
        for cv in cvs(shape):
            p = cmds.xform(cv, query=True, objectSpace=True, translation=True)
            cmds.xform(cv, objectSpace=True, translation=list(func(p)))


def world_positions(node):
    """[[world position per CV] per curve shape]."""
    return [[cmds.xform(cv, query=True, worldSpace=True, translation=True) for cv in cvs(s)]
            for s in curve_shapes(node)]


def set_world_positions(node, positions):
    for shape, pts in zip(curve_shapes(node), positions):
        for cv, p in zip(cvs(shape), pts):
            cmds.xform(cv, worldSpace=True, translation=p)


# ---------------------------------------------------------------------------
# matching
# ---------------------------------------------------------------------------

def match_matrix(target):
    """World matrix at target's pivot with its rotation, no scale (16 values)."""
    world = om.MMatrix(cmds.getAttr(target + ".worldMatrix[0]"))
    rot = om.MTransformationMatrix(world).rotation(asQuaternion=True).asMatrix()
    pivot = cmds.xform(target, query=True, worldSpace=True, rotatePivot=True)
    vals = [rot.getElement(r, c) for r in range(4) for c in range(4)]
    vals[12:15] = pivot
    return vals
