"""
Shape editing (5.6.47, the Controls tab's Edit shape page): every change moves the control's curve points only -
the control's own channels stay at zero, keys / constraints / connections stay.

- in_front(nodes, distance, axis): the shape moved away from the pivot along one of the control's axes
  (+X -X +Y -Y +Z -Z) - Ribbon's 'Distance in front' for any control.
- stretch(nodes, axis, factor) / resize(nodes, factor) / turn90(nodes, axis)
- preview(nodes, data) ... end_preview(keep): hovering a shape in the list shows it on the controls; nothing is
  an undo step until it's kept.
- handles_start(nodes) / handles_done() / handles_cancel(): a temporary handle on each control's shape - move /
  turn / size it; Done (or clicking something else) puts that into the curve, Cancel throws it away.
"""

import maya.cmds as cmds

from gus_rigtool.core import curves, shape_data, utils

AXES = {"+X": (1.0, 0.0, 0.0), "-X": (-1.0, 0.0, 0.0), "+Y": (0.0, 1.0, 0.0), "-Y": (0.0, -1.0, 0.0),
        "+Z": (0.0, 0.0, 1.0), "-Z": (0.0, 0.0, -1.0)}
HANDLE = "gusShapeHandle"
_preview = {}                       # control -> its shape and style before the preview
_handles = {"pairs": [], "job": None}


def controls(nodes):
    """The controls among nodes (transforms with curve shapes only)."""
    return [n for n in nodes or [] if curves.curve_shapes(n) and not curves.other_shapes(n)]


def _need(nodes):
    got = controls(nodes)
    if not got:
        raise RuntimeError("select one or more curve controls.")
    return got


# --------------------------------------------------------------------------- moving the points
def in_front(nodes, distance, axis="+Y"):
    """The shape moves `distance` along the control's own axis; the pivot stays. Returns the controls moved."""
    if axis not in AXES:
        raise ValueError("axis: one of %s" % ", ".join(AXES))
    d = [c * float(distance) for c in AXES[axis]]
    got = _need(nodes)
    with utils.undo_chunk("gusrigShapeInFront"):
        for n in got:
            curves.map_cvs_object(n, lambda p: (p[0] + d[0], p[1] + d[1], p[2] + d[2]))
    return got


def stretch(nodes, axis, factor):
    """The shape longer / shorter on one axis (X, Y or Z) - around the pivot."""
    i = "XYZ".index(axis.lstrip("+-").upper())
    f = float(factor)
    got = _need(nodes)
    with utils.undo_chunk("gusrigShapeStretch"):
        for n in got:
            curves.map_cvs_object(n, lambda p: tuple(v * f if k == i else v for k, v in enumerate(p)))
    return got


def resize(nodes, factor):
    f = float(factor)
    got = _need(nodes)
    with utils.undo_chunk("gusrigShapeSize"):
        for n in got:
            curves.map_cvs_object(n, lambda p: (p[0] * f, p[1] * f, p[2] * f))
    return got


def turn90(nodes, axis):
    func = {"X": lambda p: (p[0], -p[2], p[1]), "Y": lambda p: (p[2], p[1], -p[0]),
            "Z": lambda p: (-p[1], p[0], p[2])}[axis.upper()]
    got = _need(nodes)
    with utils.undo_chunk("gusrigShapeTurn"):
        for n in got:
            curves.map_cvs_object(n, func)
    return got


def use_shape(nodes, data, keep_size=True):
    """This shape on the controls (their colour / line width kept; their size kept too, by default)."""
    got = _need(nodes)
    with utils.undo_chunk("gusrigShapeUse"):
        for n in got:
            shape = data
            old = curves.read_shape(n)
            if keep_size and old:
                center, half = shape_data.bounds(old)
                shape = shape_data.fit(data, center, half)
            curves.set_shape(n, shape, curves.read_style(n) if old else None)
    return got


# --------------------------------------------------------------------------- hover preview
class _NoUndo(object):
    def __enter__(self):
        self.was = cmds.undoInfo(query=True, stateWithoutFlush=True)
        if self.was:
            cmds.undoInfo(stateWithoutFlush=False)

    def __exit__(self, *exc):
        if self.was:
            cmds.undoInfo(stateWithoutFlush=True)


def preview(nodes, data, keep_size=True):
    """Show this shape on the controls for a moment (hovering it in the list). Not an undo step. The controls'
    own shapes come back with end_preview()."""
    with _NoUndo():
        for n in controls(nodes):
            if n not in _preview:
                _preview[n] = (curves.read_shape(n), curves.read_style(n))
            old = _preview[n][0]
            shape = data
            if keep_size and old:
                center, half = shape_data.bounds(old)
                shape = shape_data.fit(data, center, half)
            curves.set_shape(n, shape, _preview[n][1])
    return list(_preview)


def end_preview():
    """The controls' own shapes back (the hover ended). Returns how many."""
    n = 0
    with _NoUndo():
        for node, (shape, style) in list(_preview.items()):
            try:
                if cmds.objExists(node) and shape:
                    curves.set_shape(node, shape, style)
                    n += 1
            except RuntimeError:
                pass
    _preview.clear()
    return n


# --------------------------------------------------------------------------- shape handles
def _matrix_of(handle):
    return cmds.xform(handle, query=True, matrix=True, objectSpace=True)


def _apply_matrix(m, p):
    x, y, z = p
    return (x * m[0] + y * m[4] + z * m[8] + m[12], x * m[1] + y * m[5] + z * m[9] + m[13],
            x * m[2] + y * m[6] + z * m[10] + m[14])


def handles_start(nodes):
    """A handle on each control's shape: move / turn / size it with Maya's tools. Selected for you. Done (or
    selecting something else) puts it into the curve; Cancel throws it away."""
    if _handles["pairs"]:
        handles_done()
    got = _need(nodes)
    pairs = []
    with _NoUndo():
        for n in got:
            h = cmds.createNode("transform", name=HANDLE, parent=n, skipSelect=True)
            h = cmds.ls(h, long=True)[0]
            loc = cmds.createNode("locator", name=HANDLE + "Shape", parent=h, skipSelect=True)
            try:                                       # about the shape's size, so you can see and click it
                _c, half = shape_data.bounds(curves.read_shape(n))
                cmds.setAttr(loc + ".localScale", half * 0.6, half * 0.6, half * 0.6)
            except (RuntimeError, ValueError, TypeError, ZeroDivisionError):
                pass
            cmds.setAttr(h + ".displayHandle", True)
            try:
                cmds.setAttr(h + ".displayLocalAxis", True)
            except RuntimeError:
                pass
            pairs.append((n, h))
        cmds.select([h for _n, h in pairs], replace=True)
    _handles["pairs"] = pairs
    _watch()
    return [h for _n, h in pairs]


def _watch():
    _unwatch()
    try:
        _handles["job"] = cmds.scriptJob(event=["SelectionChanged", _on_selection], killWithScene=True)
    except (RuntimeError, TypeError, AttributeError):
        _handles["job"] = None


def _unwatch():
    job = _handles.get("job")
    if job:
        try:
            if cmds.scriptJob(exists=job):
                cmds.scriptJob(kill=job, force=True)
        except (RuntimeError, TypeError):
            pass
    _handles["job"] = None


def _on_selection(*_):
    """You clicked something else: the handles' changes are kept (as with Done)."""
    hs = set(h for _n, h in _handles["pairs"])
    sel = set(cmds.ls(selection=True, long=True) or [])
    if hs and not (sel & hs):
        cmds.evalDeferred(handles_done)


def handles_active():
    return bool(_handles["pairs"])


def handles_done():
    """Each handle's move / turn / size put into its control's curve points; the handles go. One undo."""
    pairs = [(n, h) for n, h in _handles["pairs"] if cmds.objExists(n) and cmds.objExists(h)]
    _unwatch()
    _handles["pairs"] = []
    if not pairs:
        return 0
    mats = [(n, _matrix_of(h)) for n, h in pairs]
    with _NoUndo():
        cmds.delete([h for _n, h in pairs])
    with utils.undo_chunk("gusrigShapeHandles"):
        for n, m in mats:
            curves.map_cvs_object(n, lambda p, m=m: _apply_matrix(m, p))
    return len(mats)


def handles_cancel():
    """The handles go; the shapes stay as they were."""
    pairs = [(n, h) for n, h in _handles["pairs"] if cmds.objExists(h)]
    _unwatch()
    _handles["pairs"] = []
    with _NoUndo():
        if pairs:
            cmds.delete([h for _n, h in pairs])
    return len(pairs)
