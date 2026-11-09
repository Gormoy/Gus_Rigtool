"""
Pivot maths for the Pivots tool (4.1.0): bounding-box spots, handle orientation from geometry, remember / apply,
mirror to the twin, a spot along a chain. Objects never move: only pivots (and the Move / Rotate handles).
"""

import json
import math

import maya.cmds as cmds

from gus_rigtool.core import naming, utils

MEMORY_KEY = "pivotsMemory"

# ---------------------------------------------------------------------------
# small vector maths (row-vector matrices, like Maya)
# ---------------------------------------------------------------------------


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(v):
    n = math.sqrt(_dot(v, v))
    if n < 1e-9:
        raise RuntimeError("the points are on top of each other: no direction.")
    return [x / n for x in v]


def frame(aim, up):
    """Three unit rows (X along aim, Y as close to up as possible, Z = X x Y)."""
    x = _unit(aim)
    z = _cross(x, up)
    if math.sqrt(_dot(z, z)) < 1e-6:                      # up along aim: pick another
        z = _cross(x, [0.0, 1.0, 0.0] if abs(x[1]) < 0.9 else [0.0, 0.0, 1.0])
    z = _unit(z)
    y = _cross(z, x)
    return [x, y, z]


def euler_xyz(rows):
    """Degrees (rotate order xyz) of the rotation whose rows are rows (the shared mirror engine's maths)."""
    from gus_rigtool.core import mirror_engine
    m = list(rows[0]) + [0.0] + list(rows[1]) + [0.0] + list(rows[2]) + [0.0, 0.0, 0.0, 0.0, 1.0]
    return mirror_engine.matrix_euler(m, 0)


def rows_of(node):
    """The world axes of a node (unit rows)."""
    m = cmds.xform(node, query=True, worldSpace=True, matrix=True)
    return [_unit(m[0:3]), _unit(m[4:7]), _unit(m[8:11])]


# ---------------------------------------------------------------------------
# where
# ---------------------------------------------------------------------------

BOX = (0.0, 0.5, 1.0)      # min, centre, max along each axis


def box_point(bb, fx, fy, fz):
    """A point of an exactWorldBoundingBox [x0, y0, z0, x1, y1, z1] at fractions (0, 0.5, 1) per axis."""
    return [bb[0] + (bb[3] - bb[0]) * fx, bb[1] + (bb[4] - bb[1]) * fy, bb[2] + (bb[5] - bb[2]) * fz]


def box_label(fx, fy, fz):
    names = ({0.0: "-X", 0.5: "", 1.0: "+X"}, {0.0: "bottom", 0.5: "", 1.0: "top"},
             {0.0: "back", 0.5: "", 1.0: "front"})
    parts = [n[f] for n, f in zip(names, (fx, fy, fz)) if n[f]]
    return " ".join(parts) or "centre"


def bounding_box(nodes):
    return cmds.exactWorldBoundingBox(nodes)


def along(a, b, fraction):
    """The point fraction (0-1) of the way from a's pivot to b's pivot."""
    pa = cmds.xform(a, query=True, worldSpace=True, rotatePivot=True)
    pb = cmds.xform(b, query=True, worldSpace=True, rotatePivot=True)
    return [pa[i] + (pb[i] - pa[i]) * fraction for i in range(3)]


# ---------------------------------------------------------------------------
# orientation from components
# ---------------------------------------------------------------------------

def _flat_points(comps):
    flat = cmds.xform(comps, query=True, worldSpace=True, translation=True) or []
    return [flat[i:i + 3] for i in range(0, len(flat) - 2, 3)]


def _face_points(face):
    """The face's corners in their winding order (polyInfo), so its normal comes out right."""
    mesh = face.split(".")[0]
    try:
        info = (cmds.polyInfo(face, faceToVertex=True) or [""])[0]
        ids = [int(t) for t in info.split(":", 1)[1].split()]
        verts = ["%s.vtx[%d]" % (mesh, i) for i in ids]
    except (RuntimeError, ValueError, IndexError, TypeError):
        verts = cmds.ls(cmds.polyListComponentConversion(face, toVertex=True) or [], flatten=True) or []
    return _flat_points(verts)


def newell(points):
    """The normal of a polygon (works for any convex or concave face). Points out of order (a 'bow tie' cancels
    out): the biggest cross product round the centre instead."""
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    if math.sqrt(_dot(n, n)) > 1e-9:
        return _unit(n)
    c = [sum(p[i] for p in points) / float(len(points)) for i in range(3)]
    best = [0.0, 0.0, 0.0]
    for i, p in enumerate(points):
        for q in points[i + 1:]:
            x = _cross(_sub(p, c), _sub(q, c))
            if _dot(x, x) > _dot(best, best):
                best = x if _dot(x, best) >= 0 else [-v for v in x]
    return _unit(best)


def component_frame(comps):
    """(centre, rows) from a component selection:
       one or more faces : centre of the faces, Y = the (first) face normal, X along its first edge;
       edges            : centre, X along the first edge, Y towards world up;
       3+ vertices / CVs: the plane through the first three (selection order), X from the 1st to the 2nd,
                          Y = the plane's normal;
       2 vertices       : X from the 1st to the 2nd, Y towards world up."""
    comps = [c for c in comps if "." in c]
    if not comps:
        raise RuntimeError("select some faces, edges or vertices / CVs.")
    flat = cmds.ls(comps, flatten=True) or comps
    pts_all = _flat_points(flat) if ".f[" not in flat[0] else [p for f in flat for p in _face_points(f)]
    centre = [sum(p[i] for p in pts_all) / len(pts_all) for i in range(3)]
    first = flat[0]
    if ".f[" in first:
        pts = _face_points(first)
        if len(pts) < 3:
            raise RuntimeError("couldn't read the corners of %s (%d point(s))." % (first, len(pts)))
        normal = newell(pts)
        return centre, _rows_y(normal, _sub(pts[1], pts[0]))
    if ".e[" in first:
        pts = _flat_points(cmds.ls(cmds.polyListComponentConversion(first, toVertex=True), flatten=True))
        return centre, frame(_sub(pts[1], pts[0]), [0.0, 1.0, 0.0])
    pts = _flat_points(flat)
    if len(pts) >= 3:
        normal = _cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0]))
        return centre, _rows_y(_unit(normal), _sub(pts[1], pts[0]))
    if len(pts) == 2:
        return centre, frame(_sub(pts[1], pts[0]), [0.0, 1.0, 0.0])
    raise RuntimeError("one vertex has no direction: select a face, an edge, or 2-3 vertices.")


def _rows_y(normal, along_x):
    """Rows with Y = normal and X as close as possible to along_x."""
    y = _unit(normal)
    z = _cross(along_x, y)
    if math.sqrt(_dot(z, z)) < 1e-6:
        z = _cross([1.0, 0.0, 0.0] if abs(y[0]) < 0.9 else [0.0, 0.0, 1.0], y)
    z = _unit(z)
    x = _cross(y, z)
    return [x, y, z]


# ---------------------------------------------------------------------------
# applying
# ---------------------------------------------------------------------------

def editable(objs):
    """Objects whose pivots can move (joints never change)."""
    return [o for o in objs if cmds.nodeType(o) != "joint"]


def set_pivots(objs, position, rotation=None):
    """Move the pivots (objects stay); turn the Move / Rotate handles to rotation (degrees) if given.
    Returns how many changed."""
    done = 0
    original = cmds.ls(selection=True, long=True) or []
    for obj in editable(objs):
        try:
            cmds.xform(obj, worldSpace=True, pivots=position)
            done += 1
        except RuntimeError:
            continue
        if rotation is not None:
            try:
                cmds.select(obj, replace=True)
                cmds.manipPivot(orientation=rotation)
            except (RuntimeError, TypeError):
                pass
    if original:
        cmds.select(original, replace=True)
    return done


def handle_rotation(node):
    """The Move / Rotate handle orientation of a node (degrees), or None if Maya can't tell."""
    try:
        cmds.select(node, replace=True)
        got = cmds.manipPivot(query=True, orientation=True)
        if got and isinstance(got[0], (list, tuple)):
            got = got[0]
        return [float(v) for v in got][:3] if got else None
    except (RuntimeError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# remember / apply, mirror
# ---------------------------------------------------------------------------

def remember(node=None, position=None, rotation=None):
    """Remember a pivot spot (and handle orientation): from node's pivot, or given values. Returns it."""
    if node:
        position = cmds.xform(node, query=True, worldSpace=True, rotatePivot=True)
        rotation = handle_rotation(node) if rotation is None else rotation
        if rotation is None:
            rotation = euler_xyz(rows_of(node))
    mem = {"position": [float(v) for v in position], "rotation": [float(v) for v in (rotation or [0, 0, 0])],
           "from": naming.short_name(node) if node else "typed"}
    utils.save_setting(MEMORY_KEY, mem)
    return mem


def remembered():
    mem = utils.load_setting(MEMORY_KEY, {})
    return mem if mem.get("position") else None


def mirror_point(p, axis=0):
    """p reflected across the plane through the origin (the shared mirror engine)."""
    from gus_rigtool.core import mirror_engine
    return mirror_engine.reflect_point(p, axis)


def mirror_rotation(rot, axis=0):
    """Handle orientation of the mirror: the true mirror of the axes (the shared mirror engine), with Z made
    X x Y again so it stays a rotation - X still points outward, Y the same way up."""
    from gus_rigtool.core import mirror_engine
    m = mirror_engine.mirror_list(mirror_engine.euler_matrix(rot, 0), "true", axis)
    rows = [m[0:3], m[4:7], m[8:11]]
    rows[2] = _cross(rows[0], rows[1])
    return euler_xyz(rows)


def twin_of(node):
    """The other-side node by name (L_ <-> R_ and the other side patterns), or None."""
    from gus_rigtool.core import joint_labels
    other = joint_labels.twin_name(naming.short_name(node))
    if not other:
        return None
    found = cmds.ls(other, long=True) or []
    return found[0] if len(found) == 1 else None


def mirror_pivots(objs, axis=0, orient=False):
    """Each object's twin gets the mirrored pivot. Returns [(object, twin or None)]."""
    out = []
    for obj in objs:
        twin = twin_of(obj)
        out.append((obj, twin))
        if not twin or cmds.nodeType(twin) == "joint":
            continue
        pos = mirror_point(cmds.xform(obj, query=True, worldSpace=True, rotatePivot=True), axis)
        rot = None
        if orient:
            got = handle_rotation(obj)
            rot = mirror_rotation(got, axis) if got else None
        set_pivots([twin], pos, rot)
    return out


def dump(mem):
    return json.dumps(mem)
